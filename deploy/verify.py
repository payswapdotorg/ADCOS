#!/usr/bin/env python3
"""ADCOS deployment live-acceptance harness (T8) — standard library only.

Exercises the DEPLOYED control plane (Vercel + Neon + Upstash + R2 wiring)
against the T8 acceptance checklist and prints one table row per check:

    [ok]/[FAIL]/[skip] <name> — <detail>

Usage:

    python3 deploy/verify.py --base-url https://<production-domain> \
        [--expect-mode production|sandbox]

Checks
------
1.  GET  /healthz                    — 200, ok:true, service name reported
2.  GET  /readyz                     — 200 (or 503 with the per-backend
                                        detail captured in the output);
                                        reported mode matches --expect-mode
3.  POST /demo/contract-fulfillment  — 200, evidence_class == "SOFTWARE",
                                        contract/plan/execution/evidence
                                        chain shape non-empty
4.  DETERMINISM                      — the demo run twice must produce
                                        byte-identical bodies
5.  PERSISTENCE (production only)    — GET /api/contracts/<id-from-demo>
                                        returns the same canonical contract
                                        across separate serverless
                                        invocations (cold-start proof)
6.  COORDINATION (production only)   — /readyz sub-check: the coordination
                                        backend is configured-healthy
7.  ARTIFACTS (production only)      — /readyz sub-check: the artifact
                                        backend is configured-healthy
8.  ERROR SURFACES                   — GET /nonexistent returns a typed
                                        404 envelope
                                        {"error": {"reason_code": "not-found"}}

Checks 5-7 are mode-conditional: in sandbox mode they are skipped with
[skip] rows (no durable/coordination/artifact backends exist to prove).
Rollback verification is a Vercel-side procedure documented in
docs/deployment/runbook.md (instant alias switch) — deliberately NOT
automated here.

Transient network failures (connection reset, timeout, DNS) are retried
exactly once per request and every retry is printed. HTTP error statuses
are NOT transient: they are real responses and are evaluated as such.

Exit code: 0 when every executed check passes, 1 on any failure, 2 on
usage errors. The final line is `Result: PASS (N/N checks)` (skips
reported separately).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

DEFAULT_TIMEOUT = 20.0  # seconds; generous enough for cold starts + lazy schema bootstrap

# ---------------------------------------------------------------- constants

SERVICE_NAME_KEYS = ("service", "service_name", "name")
MODE_KEYS = ("mode", "environment", "service_mode", "runtime_mode")
EVIDENCE_CLASS_KEYS = (
    "evidence_class",
    "evidence.evidence_class",
    "chain.evidence_class",
    "result.evidence_class",
)
CHAIN_KEYS = ("contract", "plan", "execution", "evidence")
CHAIN_CONTAINERS = ("", "chain", "result", "demo", "data")  # "" = payload root
CONTRACT_ID_KEYS = (
    "contract.id",
    "contract_id",
    "id",
    "chain.contract.id",
    "result.contract.id",
    "demo.contract_id",
    "demo.id",
)
READ_CONTRACT_CONTAINERS = ("", "contract", "result", "data", "record")

COORDINATION_BACKEND_KEYS = (
    "coordination",
    "redis",
    "upstash",
    "rate_limiter",
    "ratelimit",
    "rate-limit",
    "lock",
    "locks",
    "cache",
)
ARTIFACT_BACKEND_KEYS = (
    "artifacts",
    "artifact_store",
    "artifact",
    "r2",
    "object_store",
    "storage",
    "evidence_store",
)
BACKEND_SECTION_KEYS = ("backends", "backend_status", "components", "services_state")

HEALTHY_TOKENS = frozenset(
    {"ok", "healthy", "ready", "up", "configured", "available", "degraded-ok"}
)
UNHEALTHY_TOKENS = frozenset(
    {
        "down",
        "unavailable",
        "error",
        "unconfigured",
        "missing",
        "disabled",
        "unhealthy",
        "not-configured",
        "not_configured",
        "exhausted",
        "degraded",
        "failing",
        "backend-unavailable",
    }
)

_MISSING = object()

# ------------------------------------------------------------------- output


class Row:
    """One acceptance-table row."""

    def __init__(self, tag: str, name: str, detail: str) -> None:
        self.tag = tag
        self.name = name
        self.detail = detail

    def render(self) -> str:
        return f"[{self.tag:<4}] {self.name:<24} — {self.detail}"


def note(message: str) -> None:
    """Print an interleaved operational note (retries, captured detail)."""
    print(f"       {message}")


def snippet(raw: bytes, limit: int = 200) -> str:
    text = raw.decode("utf-8", "replace").strip().replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 3] + "..."


def sha12(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()[:12]


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


# ------------------------------------------------------------------- http


class Response:
    def __init__(
        self,
        status: int,
        body: bytes,
        content_type: str = "",
        error: str | None = None,
    ) -> None:
        self.status = status
        self.body = body
        self.content_type = content_type
        self.error = error

    @property
    def payload(self) -> Any:
        if self.error is not None or not self.body:
            return None
        try:
            return json.loads(self.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

    def describe(self) -> str:
        if self.error is not None:
            return f"network error: {self.error}"
        return (
            f"status={self.status} content-type={self.content_type or 'none'} "
            f"body[:{len(self.body)}]={snippet(self.body)}"
        )


def _open_once(
    method: str,
    url: str,
    data: bytes | None,
    timeout: float,
) -> Response:
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as handle:
            return Response(
                handle.status,
                handle.read(),
                handle.headers.get("content-type", ""),
            )
    except urllib.error.HTTPError as exc:
        # An HTTP error status is a REAL response — never retried.
        try:
            body = exc.read()
        except Exception:  # pragma: no cover - defensive read
            body = b""
        return Response(exc.code, body, exc.headers.get("content-type", "") if exc.headers else "")


def http(method: str, url: str, data: bytes | None = None) -> Response:
    """Perform one HTTP request with retry-once on TRANSIENT network errors.

    Every retry is printed so the operator sees it in the evidence output.
    """
    transient = (urllib.error.URLError, socket.timeout, ConnectionError, TimeoutError)
    try:
        return _open_once(method, url, data, DEFAULT_TIMEOUT)
    except transient as exc:
        reason = getattr(exc, "reason", exc)
        note(f"[retry] {method} {url} — transient network error ({reason}); retrying once")
        try:
            return _open_once(method, url, data, DEFAULT_TIMEOUT)
        except urllib.error.HTTPError as exc:  # pragma: no cover - defensive
            try:
                body = exc.read()
            except Exception:
                body = b""
            return Response(exc.code, body, "")
        except transient as exc:
            reason = getattr(exc, "reason", exc)
            return Response(0, b"", "", error=str(reason))


def get(base_url: str, path: str) -> Response:
    return http("GET", base_url + path)


def post(base_url: str, path: str) -> Response:
    return http("POST", base_url + path, data=b"{}")


# ------------------------------------------------------- payload extraction


def dig(payload: Any, *paths: str) -> Any:
    """Return the value at the first dotted key-path that resolves.

    ``dig(payload, "a.b", "c")`` tries payload["a"]["b"], then payload["c"].
    Returns the _MISSING sentinel when nothing resolves.
    """
    if not isinstance(payload, dict):
        return _MISSING
    for path in paths:
        node: Any = payload
        resolved = True
        for key in path.split("."):
            if isinstance(node, dict) and key in node:
                node = node[key]
            else:
                resolved = False
                break
        if resolved:
            return node
    return _MISSING


def first_present(payload: Any, *keys: str) -> tuple[str, Any]:
    """Return (key, value) for the first key present at payload root."""
    for key in keys:
        if isinstance(payload, dict) and key in payload:
            return key, payload[key]
    return "", _MISSING


def non_empty(value: Any) -> bool:
    if value is _MISSING or value is None:
        return False
    if isinstance(value, (dict, list, str, bytes)):
        return len(value) > 0
    return bool(value)


# ------------------------------------------------- backend state assessment


def backend_state(entry: Any) -> str:
    """Render a compact state token for one backend readiness entry."""
    if isinstance(entry, bool):
        return "ok" if entry else "not-ok"
    if isinstance(entry, dict):
        for key in ("ok", "healthy", "ready", "configured"):
            value = entry.get(key)
            if isinstance(value, bool):
                return "ok" if value else "not-ok"
        for key in ("status", "state"):
            value = entry.get(key)
            if isinstance(value, str) and value:
                return value
        return "unknown"
    return "unknown"


def backend_healthy(entry: Any) -> bool:
    if isinstance(entry, bool):
        return entry
    if not isinstance(entry, dict):
        return False
    booleans = [entry.get(key) for key in ("ok", "healthy", "ready", "configured")]
    explicit = [value for value in booleans if isinstance(value, bool)]
    if explicit:
        return all(explicit)
    for key in ("status", "state"):
        value = entry.get(key)
        if isinstance(value, str) and value:
            lowered = value.strip().lower()
            if lowered in HEALTHY_TOKENS:
                return True
            if lowered in UNHEALTHY_TOKENS:
                return False
    return False


def find_backend_section(readiness: Any) -> tuple[str, Any]:
    """Locate the per-backend state mapping inside the readiness payload."""
    section_key, section = first_present(readiness, *BACKEND_SECTION_KEYS)
    if isinstance(section, dict):
        return section_key, section
    # Fall back to the readiness root when it directly carries backend keys.
    if isinstance(readiness, dict):
        known = set(COORDINATION_BACKEND_KEYS) | set(ARTIFACT_BACKEND_KEYS) | {"database"}
        if known & set(readiness):
            return "", readiness
    return section_key, _MISSING


def describe_backends(section: Any, limit: int = 6) -> str:
    if not isinstance(section, dict) or not section:
        return "none reported"
    parts = [
        f"{name}={backend_state(entry)}"
        for name, entry in list(section.items())[:limit]
    ]
    suffix = "" if len(section) <= limit else f" (+{len(section) - limit} more)"
    return "{" + ", ".join(parts) + suffix + "}"


# ------------------------------------------------------------------- checks


class Harness:
    def __init__(self, base_url: str, expect_mode: str) -> None:
        self.base_url = base_url
        self.expect_mode = expect_mode
        self.rows: list[Row] = []
        self.demo_contract: Any = _MISSING
        self.demo_contract_id: Any = _MISSING
        self.readiness: Any = _MISSING
        self.readiness_note = ""

    # -- plumbing

    def record(self, tag: str, name: str, detail: str) -> Row:
        row = Row(tag, name, detail)
        self.rows.append(row)
        print(row.render())
        return row

    def run(self, name: str, body: Callable[[], Row]) -> None:
        try:
            body()
        except Exception as exc:  # defensive: the harness must never crash
            self.record("FAIL", name, f"harness error: {exc!r}")

    # -- checks 1 + 2

    def check_healthz(self) -> None:
        response = get(self.base_url, "/healthz")
        if response.error is not None:
            self.record("FAIL", "healthz", response.describe())
            return
        payload = response.payload
        if response.status != 200:
            self.record("FAIL", "healthz", response.describe())
            return
        if not isinstance(payload, dict):
            self.record("FAIL", "healthz", f"non-JSON payload — {response.describe()}")
            return
        problems: list[str] = []
        ok_value = dig(payload, "ok")
        if ok_value is not True:
            found = "missing" if ok_value is _MISSING else repr(ok_value)
            problems.append(f"ok is {found}, expected true")
        service_name = dig(payload, *SERVICE_NAME_KEYS)
        if not (isinstance(service_name, str) and service_name.strip()):
            problems.append(f"service name missing (searched: {', '.join(SERVICE_NAME_KEYS)})")
        if problems:
            self.record("FAIL", "healthz", "; ".join(problems))
        else:
            self.record("ok", "healthz", f"200 ok=true service={service_name}")

    def check_readyz(self) -> None:
        response = get(self.base_url, "/readyz")
        if response.error is not None:
            self.record("FAIL", "readyz", response.describe())
            return
        payload = response.payload
        if not isinstance(payload, dict):
            self.record("FAIL", "readyz", f"non-JSON payload — {response.describe()}")
            return
        # Capture the per-backend detail whatever the status code is.
        section_key, section = find_backend_section(payload)
        self.readiness = payload
        if section is not _MISSING:
            self.readiness_note = f"backends: {describe_backends(section)}"
        problems: list[str] = []
        if response.status == 200:
            pass  # healthy aggregate
        elif response.status == 503:
            problems.append(
                "readiness reported 503 (not ready); per-backend detail captured above"
                if section is not _MISSING
                else "readiness reported 503 (not ready); no per-backend detail in payload"
            )
        else:
            problems.append(f"unexpected status {response.status}")
        mode_value = dig(payload, *MODE_KEYS)
        if mode_value is _MISSING:
            problems.append(f"mode missing (searched: {', '.join(MODE_KEYS)})")
        elif str(mode_value).strip().lower() != self.expect_mode:
            problems.append(f"mode={mode_value!r}, expected {self.expect_mode!r}")
        if response.status != 200:
            note(f"[readyz] payload detail: {snippet(response.body, 400)}")
        if problems:
            detail = "; ".join(problems)
            if self.readiness_note:
                detail = f"{detail}; {self.readiness_note}"
            self.record("FAIL", "readyz", detail)
        else:
            detail = f"200 mode={self.expect_mode}"
            if self.readiness_note:
                detail = f"{detail}; {self.readiness_note}"
            self.record("ok", "readyz", detail)

    # -- checks 3 + 4

    def check_demo(self) -> None:
        response = post(self.base_url, "/demo/contract-fulfillment")
        if response.error is not None:
            self.record("FAIL", "demo-fulfillment", response.describe())
            return
        payload = response.payload
        if response.status != 200:
            self.record("FAIL", "demo-fulfillment", response.describe())
            return
        if not isinstance(payload, dict):
            self.record("FAIL", "demo-fulfillment", f"non-JSON payload — {response.describe()}")
            return
        problems: list[str] = []
        evidence_class = dig(payload, *EVIDENCE_CLASS_KEYS)
        if evidence_class is _MISSING:
            problems.append(f"evidence_class missing (searched: {', '.join(EVIDENCE_CLASS_KEYS)})")
        elif evidence_class != "SOFTWARE":
            problems.append(f"evidence_class={evidence_class!r}, expected 'SOFTWARE'")
        found_chain: list[str] = []
        for key in CHAIN_KEYS:
            value = dig(payload, *(f"{container}.{key}" if container else key for container in CHAIN_CONTAINERS))
            if non_empty(value):
                found_chain.append(key)
            else:
                problems.append(f"chain member {key!r} missing/empty")
        # Remember the canonical contract for the persistence check.
        self.demo_contract = dig(
            payload,
            *(f"{container}.contract" if container else "contract" for container in CHAIN_CONTAINERS)
        )
        self.demo_contract_id = dig(payload, *CONTRACT_ID_KEYS)
        if problems:
            self.record("FAIL", "demo-fulfillment", "; ".join(problems))
        else:
            self.record(
                "ok",
                "demo-fulfillment",
                "200 evidence_class=SOFTWARE chain: " + "/".join(found_chain) + " non-empty",
            )

    def check_determinism(self) -> None:
        first = post(self.base_url, "/demo/contract-fulfillment")
        second = post(self.base_url, "/demo/contract-fulfillment")
        if first.error is not None or second.error is not None:
            failed = first if first.error is not None else second
            self.record("FAIL", "determinism", failed.describe())
            return
        if first.status != 200 or second.status != 200:
            self.record(
                "FAIL",
                "determinism",
                f"unexpected statuses {first.status}/{second.status}",
            )
            return
        if first.body == second.body:
            self.record(
                "ok",
                "determinism",
                f"two runs byte-identical (sha256:{sha12(first.body)}, {len(first.body)} bytes)",
            )
        else:
            self.record(
                "FAIL",
                "determinism",
                f"bodies differ (run1 sha256:{sha12(first.body)} {len(first.body)}B, "
                f"run2 sha256:{sha12(second.body)} {len(second.body)}B)",
            )

    # -- check 5 (production)

    def check_persistence(self) -> None:
        if self.demo_contract_id is _MISSING:
            self.record(
                "FAIL",
                "persistence",
                f"no contract id in demo payload (searched: {', '.join(CONTRACT_ID_KEYS)})",
            )
            return
        contract_id = str(self.demo_contract_id)
        path = "/api/contracts/" + urllib.parse.quote(contract_id, safe="")
        response = get(self.base_url, path)
        if response.error is not None:
            self.record("FAIL", "persistence", response.describe())
            return
        if response.status != 200:
            hint = ""
            if response.status == 404 and "application/json" not in response.content_type:
                hint = (
                    "; platform-level 404 (non-JSON) — the request never reached the "
                    "app: see the routing note in docs/deployment/runbook.md "
                    "(the vercel.json rewrite excludes /api/* by design)"
                )
            self.record("FAIL", "persistence", response.describe() + hint)
            return
        payload = response.payload
        if not isinstance(payload, dict):
            self.record("FAIL", "persistence", f"non-JSON payload — {response.describe()}")
            return
        read_id = dig(payload, "id", "contract.id", "contract_id", "data.id", "result.id")
        if read_id is _MISSING or str(read_id) != contract_id:
            self.record(
                "FAIL",
                "persistence",
                f"read payload does not carry the demo contract id {contract_id!r}",
            )
            return
        # Strong form: the canonical contract mapping round-trips identically.
        if isinstance(self.demo_contract, dict):
            for container in READ_CONTRACT_CONTAINERS:
                candidate = payload if not container else payload.get(container)
                if isinstance(candidate, dict) and candidate is not payload:
                    if canonical(candidate) == canonical(self.demo_contract):
                        self.record(
                            "ok",
                            "persistence",
                            f"GET {path} → 200 canonical contract round-trip identical "
                            f"({len(self.demo_contract)} fields, cold-start-spanning)",
                        )
                        return
            # Superset projection: every canonical field round-trips unchanged.
            if all(
                key in payload and canonical(payload[key]) == canonical(value)
                for key, value in self.demo_contract.items()
            ):
                extra = len(payload) - len(self.demo_contract)
                self.record(
                    "ok",
                    "persistence",
                    f"GET {path} → 200 canonical fields round-trip identically "
                    f"(read projection adds {extra} envelope field(s))",
                )
                return
            differing = [
                key
                for key, value in self.demo_contract.items()
                if key not in payload or canonical(payload[key]) != canonical(value)
            ]
            self.record(
                "FAIL",
                "persistence",
                f"canonical contract mismatch on read (fields differing/missing: "
                f"{', '.join(map(str, differing[:5])) or 'shape'})",
            )
            return
        self.record(
            "ok",
            "persistence",
            f"GET {path} → 200 contract id round-trip verified across invocations "
            "(demo payload carried no comparable contract mapping)",
        )

    # -- checks 6 + 7 (production): readiness sub-checks

    def check_backend(self, name: str, candidate_keys: tuple[str, ...]) -> None:
        if not isinstance(self.readiness, dict):
            self.record(
                "FAIL",
                name,
                "readiness payload unavailable — cannot assess backend state",
            )
            return
        section_key, section = find_backend_section(self.readiness)
        if section is _MISSING:
            self.record(
                "FAIL",
                name,
                "readiness payload carries no per-backend state "
                f"(searched sections: {', '.join(BACKEND_SECTION_KEYS)})",
            )
            return
        for key in candidate_keys:
            if key in section:
                entry = section[key]
                state = backend_state(entry)
                if backend_healthy(entry):
                    where = f"readiness[{section_key or 'root'}.{key}]" if section_key else f"readiness[{key}]"
                    self.record("ok", name, f"configured-healthy ({where}: {state})")
                else:
                    self.record(
                        "FAIL",
                        name,
                        f"backend not configured-healthy (state: {state}; "
                        f"entry: {json.dumps(entry, sort_keys=True)[:200]})",
                    )
                return
        self.record(
            "FAIL",
            name,
            f"no {name.split('-')[0]} backend entry in readiness payload "
            f"(searched: {', '.join(candidate_keys)}; present: "
            f"{', '.join(section) if isinstance(section, dict) else 'n/a'}) — "
            "reconcile the readiness payload schema with runtime/wiring.py",
        )

    # -- check 8

    def check_error_surface(self) -> None:
        response = get(self.base_url, "/nonexistent")
        if response.error is not None:
            self.record("FAIL", "error-surface", response.describe())
            return
        payload = response.payload
        if response.status != 404:
            self.record(
                "FAIL",
                "error-surface",
                f"expected 404, got {response.status} — {snippet(response.body, 120)}",
            )
            return
        if not isinstance(payload, dict):
            self.record(
                "FAIL",
                "error-surface",
                f"404 without a typed JSON envelope — {response.describe()}",
            )
            return
        error = payload.get("error")
        if not isinstance(error, dict):
            self.record("FAIL", "error-surface", "404 envelope has no error object")
            return
        reason = error.get("reason_code")
        if reason != "not-found":
            self.record(
                "FAIL",
                "error-surface",
                f"reason_code={reason!r}, expected 'not-found' (envelope: {snippet(response.body, 160)})",
            )
            return
        message = error.get("message") or error.get("detail") or ""
        suffix = f"; message={message!r}" if message else ""
        self.record("ok", "error-surface", f"404 typed envelope reason_code=not-found{suffix}")

    # -- orchestration

    def execute(self) -> int:
        print(f"ADCOS live acceptance — {self.base_url} (expect-mode: {self.expect_mode})")
        print()
        self.run("healthz", self.check_healthz)
        self.run("readyz", self.check_readyz)
        self.run("demo-fulfillment", self.check_demo)
        self.run("determinism", self.check_determinism)
        if self.expect_mode == "production":
            self.run("persistence", self.check_persistence)
            self.run(
                "coordination-backend",
                lambda: self.check_backend("coordination-backend", COORDINATION_BACKEND_KEYS),
            )
            self.run(
                "artifact-backend",
                lambda: self.check_backend("artifact-backend", ARTIFACT_BACKEND_KEYS),
            )
        else:
            self.record(
                "skip",
                "persistence",
                "sandbox mode — no durable backend to round-trip",
            )
            self.record(
                "skip",
                "coordination-backend",
                "sandbox mode — no coordination backend configured",
            )
            self.record(
                "skip",
                "artifact-backend",
                "sandbox mode — no artifact backend configured",
            )
        self.run("error-surface", self.check_error_surface)

        executed = [row for row in self.rows if row.tag != "skip"]
        skipped = [row for row in self.rows if row.tag == "skip"]
        passed = [row for row in executed if row.tag == "ok"]
        failures = [row for row in executed if row.tag == "FAIL"]
        print()
        if failures:
            print(f"Result: FAIL ({len(passed)}/{len(executed)} checks; {len(failures)} failing)")
            return 1
        suffix = f"; {len(skipped)} skipped" if skipped else ""
        print(f"Result: PASS ({len(passed)}/{len(executed)} checks{suffix})")
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="deploy/verify.py",
        description=(
            "ADCOS T8 live-acceptance harness: exercises the deployed control "
            "plane (health, readiness, deterministic contract-fulfillment demo, "
            "durable persistence, coordination/artifact backends, typed error "
            "surfaces) and exits non-zero on any failure."
        ),
    )
    parser.add_argument(
        "--base-url",
        required=True,
        help="the deployed service origin, e.g. https://adcos.example.com",
    )
    parser.add_argument(
        "--expect-mode",
        choices=("production", "sandbox"),
        default="production",
        help=(
            "the mode /readyz must report (default: production; use sandbox "
            "for preview/deterministic-demo deployments — checks 5-7 are "
            "skipped with [skip] rows)"
        ),
    )
    args = parser.parse_args(argv)
    base_url = args.base_url.strip().rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        parser.error("--base-url must be an absolute http(s) URL")
    return Harness(base_url, args.expect_mode).execute()


if __name__ == "__main__":
    sys.exit(main())
