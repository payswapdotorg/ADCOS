#!/usr/bin/env python3
"""ADCOS deployment runtime battery (DEC-0126 bounded scope) — the
pure-stdlib ASGI surface (deterministic, stdlib only, NO network).

Hand-rolled ASGI test driver (``asyncio.run`` over mock
``receive``/``send`` callables — no third-party test framework, no
HTTP server) verifying the ``runtime/`` surface end to end:

- **liveness** (``GET /healthz``): always 200, the constant
  ``{"ok": true, "service": "adcos-runtime"}`` document, canonical
  JSON, ``content-type: application/json``;
- **readiness** (``GET /readyz``): per-mode body (the deployment
  mode + environment + the consumed backends' own probe states);
  200 when every backend is ready, 503 with per-backend detail when
  one is not (verified over a fake postgres backend: healthy ->
  200/ready, dead probe -> 503/unavailable with the backend named);
  delegated R2 coordinates are reported but never counted;
- **the deterministic contract-fulfillment demonstration**
  (``POST``/``GET /demo/contract-fulfillment``): POST and the GET
  form return byte-identical bodies; three FRESH app instances
  return byte-identical bodies; the evidence-chain shape is
  complete (contract/plan/execution/evidence), the response is
  canonical-JSON-serializable, ``evidence_class == "SOFTWARE"``
  and the created ``contract_id`` sits at the stable
  ``contract.contract_id`` path; the optional ``instant`` member
  drives a genuinely new demonstration; sandbox mode NEVER claims
  production anywhere;
- **the contract read** (``GET /api/contracts/{id}``): the
  platform-side public store read, the gateway boundary read with
  the developer credential headers, and the unknown-contract typed
  404 envelope (the accepted domain's reason preserved verbatim);
- **error discipline**: every error is the typed envelope
  ``{"error": {"reason_code", "message", "backend"}}`` — 404
  not-found, 400 malformed-json, 400 invalid-request-body, 413
  payload-too-large (both the content-length pre-check and the
  streamed-body cap), 400 on an invalid demo instant — and NO
  stack trace, NO raw exception text ever escapes;
- **serialization discipline**: every response body IS canonical
  JSON (sorted keys, compact separators — re-serializing the parsed
  body reproduces the exact bytes) with an exact content-length;
- **the ASGI protocol surface**: the lifespan
  startup/shutdown acknowledgements;
- **cross-process determinism**: the demonstration body digest is
  byte-identical across ``PYTHONHASHSEED`` 0/1/7919 subprocesses,
  each assembling a FRESH app from the environment.

The production-mode cases run against a deterministic FAKE pg
connection (the same minimal DB-API seam as the persistence
battery) — no Postgres, no network, no third-party imports.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from protocol.canonicalization import canonical_json_bytes  # noqa: E402

from runtime.asgi import MAX_BODY_BYTES, build_app  # noqa: E402
from runtime.demo import DEFAULT_DEMO_INSTANT  # noqa: E402
from runtime.sandbox import build_sandbox_services  # noqa: E402
from runtime.services import RuntimeServices  # noqa: E402
from runtime.wiring import build_production_services  # noqa: E402

Result = Tuple[str, bool, str]

_T0 = "2026-09-13T00:00:00Z"


def ok(name: str, detail: str = "") -> Result:
    return (name, True, detail)


def fail(name: str, detail: str) -> Result:
    return (name, False, detail)


# ---------------------------------------------------------------------------
# The hand-rolled ASGI test driver (mock receive/send; asyncio.run)
# ---------------------------------------------------------------------------


def drive(
    app: Callable[..., Any],
    method: str,
    path: str,
    *,
    body: bytes = b"",
    headers: Sequence[Tuple[bytes, bytes]] = (),
) -> Tuple[int, bytes, List[Mapping[str, Any]]]:
    """Drive ONE request through the ASGI callable; returns
    ``(status, body_bytes, sent_messages)``."""

    async def _run() -> Tuple[int, bytes, List[Mapping[str, Any]]]:
        sent: List[Mapping[str, Any]] = []
        requested = {"done": False}

        async def receive() -> Mapping[str, Any]:
            if not requested["done"]:
                requested["done"] = True
                return {
                    "type": "http.request",
                    "body": body,
                    "more_body": False,
                }
            return {"type": "http.disconnect"}

        async def send(message: Mapping[str, Any]) -> None:
            sent.append(message)

        scope: Dict[str, Any] = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": b"",
            "headers": list(headers),
        }
        await app(scope, receive, send)
        start = next(
            (m for m in sent if m.get("type") == "http.response.start"), None
        )
        payload = b"".join(
            bytes(m.get("body") or b"")
            for m in sent
            if m.get("type") == "http.response.body"
        )
        status = int(start["status"]) if start else -1
        return status, payload, sent

    return asyncio.run(_run())


def drive_lifespan(app: Callable[..., Any]) -> List[Mapping[str, Any]]:
    """Drive the ASGI lifespan protocol; returns the sent messages."""

    async def _run() -> List[Mapping[str, Any]]:
        sent: List[Mapping[str, Any]] = []
        queue: List[Mapping[str, Any]] = [
            {"type": "lifespan.startup"},
            {"type": "lifespan.shutdown"},
        ]

        async def receive() -> Mapping[str, Any]:
            if queue:
                return queue.pop(0)
            return {"type": "lifespan.shutdown"}

        async def send(message: Mapping[str, Any]) -> None:
            sent.append(message)

        await app({"type": "lifespan"}, receive, send)
        return sent

    return asyncio.run(_run())


def _json_headers(body: bytes = b"") -> List[Tuple[bytes, bytes]]:
    headers = [(b"content-type", b"application/json")]
    if body:
        headers.append((b"content-length", str(len(body)).encode("latin-1")))
    return headers


def _demo_body(instant: Optional[str] = None) -> bytes:
    if instant is None:
        return b"{}"
    return json.dumps({"instant": instant}).encode("utf-8")


# ---------------------------------------------------------------------------
# The deterministic fake pg connection (the minimal DB-API seam)
# ---------------------------------------------------------------------------


class _FakeCursor:
    def __init__(self, connection: "_FakeConnection") -> None:
        self._connection = connection
        self._rows: List[Tuple[Any, ...]] = []
        self.closed = False

    def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        if self.closed:
            raise RuntimeError("cursor is closed")
        if self._connection.fail_probe and sql.strip() == "SELECT 1":
            raise RuntimeError("injected probe failure")
        self._connection._apply(sql, tuple(params), self._rows)

    def fetchall(self) -> List[Tuple[Any, ...]]:
        return list(self._rows)

    def close(self) -> None:
        self.closed = True


class _FakeConnection:
    """The minimal fake: CREATE TABLE / INSERT / SELECT ... ORDER BY seq
    / SELECT 1, per-connection transaction buffering, an injectable
    probe failure (exactly the statements the adapter emits)."""

    def __init__(self, database: "_FakeDatabase") -> None:
        self._database = database
        self._pending: List[Tuple[str, str, str]] = []
        self.fail_probe = False

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self)

    def commit(self) -> None:
        for table, namespace, line in self._pending:
            self._database.append_row(table, namespace, line)
        self._pending = []

    def rollback(self) -> None:
        self._pending = []

    def _apply(
        self, sql: str, params: Tuple[Any, ...], rows: List[Tuple[Any, ...]]
    ) -> None:
        normalized = " ".join(sql.split()).strip().rstrip(";")
        if normalized.startswith("CREATE TABLE"):
            self._database.tables.add(normalized.split()[5])
            return
        if normalized == "SELECT 1":
            rows.append((1,))
            return
        if normalized.startswith("INSERT INTO adcos_"):
            table = normalized.split()[2]
            if table not in self._database.tables:
                raise RuntimeError("table %s does not exist" % table)
            if table == "adcos_api_journal":
                self._pending.append((table, "default", params[0]))
            else:
                self._pending.append((table, params[0], params[1]))
            return
        if normalized.startswith("SELECT line FROM "):
            table = normalized.split()[3]
            if table not in self._database.tables:
                raise RuntimeError("table %s does not exist" % table)
            if "ORDER BY seq" not in normalized:
                raise RuntimeError("the adapter must order journal reads by seq")
            for namespace, _seq, line in self._database.rows(table):
                if "WHERE namespace = %s" in normalized and namespace != params[0]:
                    continue
                rows.append((line,))
            return
        raise RuntimeError("unexpected SQL: %r" % normalized)


class _FakeDatabase:
    def __init__(self) -> None:
        self.tables = set()
        self._rows: Dict[str, List[Tuple[str, int, str]]] = {}
        self._seq: Dict[str, int] = {}

    def append_row(self, table: str, namespace: str, line: str) -> None:
        seq = self._seq.get(table, 0) + 1
        self._seq[table] = seq
        self._rows.setdefault(table, []).append((namespace, seq, line))

    def rows(self, table: str) -> List[Tuple[str, int, str]]:
        return sorted(self._rows.get(table, ()), key=lambda row: row[1])

    def count(self, table: str) -> int:
        return len(self._rows.get(table, ()))


def _fake_factory(
    database: _FakeDatabase, *, fail_probe: bool = False
) -> Callable[[], _FakeConnection]:
    def _factory() -> _FakeConnection:
        connection = _FakeConnection(database)
        connection.fail_probe = fail_probe
        return connection

    return _factory


_PRODUCTION_ENV: Dict[str, str] = {
    "ADCOS_ENVIRONMENT": "production",
    "ADCOS_DATABASE_URL": "postgresql://user:pw@neon.example/db?sslmode=require",
    "ADCOS_ISSUANCE_KEY": "00" * 32,
}


def _production_services(
    database: _FakeDatabase, *, fail_probe: bool = False, tmp: str = "."
) -> RuntimeServices:
    import tempfile

    return build_production_services(
        environ=dict(_PRODUCTION_ENV),
        journal_dir=Path(tempfile.gettempdir()) / ("adcos-runtime-battery-%s" % tmp),
        connection_factory=_fake_factory(database, fail_probe=fail_probe),
    )


def _app_post_demo(app: Callable[..., Any]) -> Tuple[int, bytes]:
    return drive(
        app,
        "POST",
        "/demo/contract-fulfillment",
        body=_demo_body(),
        headers=_json_headers(_demo_body()),
    )[:2]


# ---------------------------------------------------------------------------
# The cases
# ---------------------------------------------------------------------------


def case_01_liveness_shape(results: List[Result]) -> None:
    """Criterion: GET /healthz is always 200 with the constant
    liveness document (canonical JSON, JSON content type)."""
    problems: List[str] = []
    app = build_app(build_sandbox_services())
    status, payload, sent = drive(app, "GET", "/healthz")
    if status != 200:
        problems.append("status %d" % status)
    if payload != b'{"ok":true,"service":"adcos-runtime"}':
        problems.append("body %r" % payload)
    start = sent[0]
    header_map = {
        name.decode("latin-1").lower(): value.decode("latin-1")
        for name, value in start.get("headers") or ()
    }
    if header_map.get("content-type") != "application/json":
        problems.append("content-type %r" % header_map.get("content-type"))
    if int(header_map.get("content-length", "-1")) != len(payload):
        problems.append("content-length mismatch")
    if problems:
        results.append(fail("01 liveness shape", "; ".join(problems)))
    else:
        results.append(
            ok("01 liveness shape", "200 constant document; canonical JSON headers")
        )


def case_02_readiness_sandbox(results: List[Result]) -> None:
    """Criterion: sandbox readiness is trivially green, carries the
    mode, and never claims production."""
    problems: List[str] = []
    app = build_app(build_sandbox_services())
    status, payload, _ = drive(app, "GET", "/readyz")
    document = json.loads(payload)
    if status != 200 or document.get("ok") is not True:
        problems.append("status %d body %r" % (status, document))
    if document.get("mode") != "sandbox":
        problems.append("mode %r" % document.get("mode"))
    if document.get("environment") != "sandbox":
        problems.append("environment %r" % document.get("environment"))
    if document.get("backends") != {}:
        problems.append("sandbox carries backends %r" % document.get("backends"))
    if "production" in payload.decode("utf-8"):
        problems.append("sandbox readiness claims production")
    if problems:
        results.append(fail("02 readiness sandbox", "; ".join(problems)))
    else:
        results.append(
            ok("02 readiness sandbox", "200; mode=sandbox; no backend; no production claim")
        )


def case_03_readiness_production_ready(results: List[Result]) -> None:
    """Criterion: production readiness reports the postgres backend's
    own probe state (ready -> 200, mode=production)."""
    problems: List[str] = []
    database = _FakeDatabase()
    services = _production_services(database)
    app = build_app(services)
    status, payload, _ = drive(app, "GET", "/readyz")
    document = json.loads(payload)
    if status != 200 or document.get("ok") is not True:
        problems.append("status %d body %r" % (status, document))
    if document.get("mode") != "production":
        problems.append("mode %r" % document.get("mode"))
    backends = document.get("backends") or {}
    if backends.get("postgres", {}).get("state") != "ready":
        problems.append("postgres state %r" % backends.get("postgres"))
    if problems:
        results.append(fail("03 readiness production ready", "; ".join(problems)))
    else:
        results.append(
            ok("03 readiness production ready", "200; mode=production; postgres=ready")
        )


def case_04_readiness_production_unavailable(results: List[Result]) -> None:
    """Criterion: a failing backend probe is explicit — 503 with the
    per-backend detail and the backend named (never a silent green)."""
    problems: List[str] = []
    database = _FakeDatabase()
    services = _production_services(database)
    app = build_app(services)
    # the shared connection the adapter holds: fail its next probe
    connection = services.api_store._connect()
    connection.fail_probe = True
    status, payload, _ = drive(app, "GET", "/readyz")
    document = json.loads(payload)
    if status != 503:
        problems.append("status %d" % status)
    if document.get("ok") is not False:
        problems.append("ok %r" % document.get("ok"))
    state = (document.get("backends") or {}).get("postgres", {})
    if state.get("state") != "unavailable":
        problems.append("postgres state %r" % state)
    if "detail" not in state:
        problems.append("no per-backend detail")
    if problems:
        results.append(fail("04 readiness production unavailable", "; ".join(problems)))
    else:
        results.append(
            ok(
                "04 readiness production unavailable",
                "503; postgres=unavailable with detail (explicit, observable)",
            )
        )


def case_05_readiness_delegated_r2(results: List[Result]) -> None:
    """Criterion: R2 coordinates are reported as DELEGATED and never
    counted against this surface's readiness."""
    problems: List[str] = []
    database = _FakeDatabase()
    environ = dict(_PRODUCTION_ENV)
    environ.update(
        {
            "ADCOS_R2_ACCOUNT_ID": "account",
            "ADCOS_R2_ACCESS_KEY_ID": "key-id",
            "ADCOS_R2_SECRET_ACCESS_KEY": "secret",
            "ADCOS_R2_BUCKET": "bucket",
        }
    )
    import tempfile

    services = build_production_services(
        environ=environ,
        journal_dir=Path(tempfile.gettempdir()) / "adcos-runtime-battery-r2",
        connection_factory=_fake_factory(database),
    )
    app = build_app(services)
    status, payload, _ = drive(app, "GET", "/readyz")
    document = json.loads(payload)
    if status != 200 or document.get("ok") is not True:
        problems.append("status %d ok %r" % (status, document.get("ok")))
    delegated = document.get("delegated_backends") or {}
    if delegated.get("r2", {}).get("state") != "delegated":
        problems.append("delegated %r" % delegated)
    if "r2" in (document.get("backends") or {}):
        problems.append("delegated backend counted as consumed")
    if problems:
        results.append(fail("05 readiness delegated r2", "; ".join(problems)))
    else:
        results.append(
            ok("05 readiness delegated r2", "delegated reported; not counted; 200")
        )


def case_06_demo_post_get_byte_identical(results: List[Result]) -> None:
    """Criterion: the demonstration is idempotent — the GET form and
    the default POST return byte-identical bodies."""
    problems: List[str] = []
    app = build_app(build_sandbox_services())
    status_post, payload_post, _ = drive(
        app,
        "POST",
        "/demo/contract-fulfillment",
        body=_demo_body(),
        headers=_json_headers(_demo_body()),
    )
    status_get, payload_get, _ = drive(app, "GET", "/demo/contract-fulfillment")
    if status_post != 200 or status_get != 200:
        problems.append("statuses %d/%d" % (status_post, status_get))
    if payload_post != payload_get:
        problems.append("POST and GET bodies diverge")
    if problems:
        results.append(fail("06 demo post/get byte-identical", "; ".join(problems)))
    else:
        results.append(
            ok(
                "06 demo post/get byte-identical",
                "%d bytes; POST == GET" % len(payload_post),
            )
        )


def case_07_demo_three_fresh_instances_identical(results: List[Result]) -> None:
    """Criterion: determinism across FRESH app instances — three
    separately assembled runtimes return the byte-identical body."""
    payloads = []
    for _ in range(3):
        app = build_app(build_sandbox_services())
        status, payload, _ = drive(
            app,
            "POST",
            "/demo/contract-fulfillment",
            body=_demo_body(),
            headers=_json_headers(_demo_body()),
        )
        if status != 200:
            results.append(
                fail("07 demo three fresh instances", "status %d" % status)
            )
            return
        payloads.append(payload)
    if payloads[0] != payloads[1] or payloads[1] != payloads[2]:
        digests = [
            hashlib.sha256(payload).hexdigest()[:16] for payload in payloads
        ]
        results.append(
            fail("07 demo three fresh instances", "digests %s" % digests)
        )
        return
    results.append(
        ok(
            "07 demo three fresh instances",
            "3/3 byte-identical (%d bytes; sha256 %s)"
            % (len(payloads[0]), hashlib.sha256(payloads[0]).hexdigest()[:16]),
        )
    )


def case_08_demo_evidence_chain_shape(results: List[Result]) -> None:
    """Criterion: the full software-class evidence chain — the
    contract/plan/execution/evidence members, the observation +
    attestation records, evidence_class == SOFTWARE, and the created
    contract_id at the stable contract.contract_id path."""
    problems: List[str] = []
    app = build_app(build_sandbox_services())
    status, payload, _ = drive(
        app,
        "POST",
        "/demo/contract-fulfillment",
        body=_demo_body(),
        headers=_json_headers(_demo_body()),
    )
    if status != 200:
        results.append(fail("08 demo evidence chain shape", "status %d" % status))
        return
    document = json.loads(payload)
    contract = document.get("contract") or {}
    contract_id = contract.get("contract_id")
    if not isinstance(contract_id, str) or not contract_id.startswith("sha256:"):
        problems.append("contract_id %r" % (contract_id,))
    if contract.get("state") != "CONTRACT_ACTIVE":
        problems.append("contract state %r" % contract.get("state"))
    if not contract.get("accepted_offers"):
        problems.append("no accepted offers")
    if not contract.get("execution_artifacts"):
        problems.append("no bound execution artifact")
    plan = document.get("plan") or {}
    if not plan.get("plan_id"):
        problems.append("no plan_id")
    if not plan.get("segments"):
        problems.append("no plan segments")
    if plan["segments"][0].get("state") != "RELEASED":
        problems.append("segment state %r" % plan["segments"][0].get("state"))
    execution = document.get("execution") or {}
    for member in (
        "activation_id",
        "reservation_id",
        "measurement_id",
        "release_id",
        "adapter_id",
        "session_id",
    ):
        if not execution.get(member):
            problems.append("execution missing %s" % member)
    if execution.get("sandbox") is not True:
        problems.append("execution not marked sandbox")
    evidence = document.get("evidence") or []
    if len(evidence) != 2:
        problems.append("evidence records %d" % len(evidence))
    kinds = sorted(record.get("record_type", "?") for record in evidence)
    if kinds != ["attestation", "observation"]:
        problems.append("evidence kinds %r" % kinds)
    for record in evidence:
        if record.get("contract_ref") != contract_id:
            problems.append("evidence contract_ref %r" % record.get("contract_ref"))
        if not str(record.get("record_id", "")).startswith("evidence:"):
            problems.append("evidence id %r" % record.get("record_id"))
    if document.get("evidence_class") != "SOFTWARE":
        problems.append("evidence_class %r" % document.get("evidence_class"))
    if document.get("instant") != DEFAULT_DEMO_INSTANT:
        problems.append("instant %r" % document.get("instant"))
    if problems:
        results.append(fail("08 demo evidence chain shape", "; ".join(problems)))
    else:
        results.append(
            ok(
                "08 demo evidence chain shape",
                "contract/plan/execution + observation+attestation; "
                "evidence_class=SOFTWARE; contract_id stable",
            )
        )


def case_09_demo_canonical_serializable(results: List[Result]) -> None:
    """Criterion (worker 3's harness contract): the demonstration
    response is canonical-JSON-serializable — re-serializing the
    parsed body reproduces the exact response bytes."""
    app = build_app(build_sandbox_services())
    status, payload, _ = drive(
        app,
        "POST",
        "/demo/contract-fulfillment",
        body=_demo_body(),
        headers=_json_headers(_demo_body()),
    )
    if status != 200:
        results.append(fail("09 demo canonical serializable", "status %d" % status))
        return
    try:
        document = json.loads(payload)
    except ValueError as error:
        results.append(fail("09 demo canonical serializable", "unparsable: %s" % error))
        return
    if canonical_json_bytes(document) != payload:
        results.append(
            fail(
                "09 demo canonical serializable",
                "the response bytes are not the canonical serialization",
            )
        )
        return
    results.append(
        ok("09 demo canonical serializable", "bytes == canonical_json_bytes(body)")
    )


def case_10_demo_custom_instant(results: List[Result]) -> None:
    """Criterion: the optional request instant drives a genuinely NEW
    demonstration; the same instant replays byte-identically."""
    problems: List[str] = []
    app = build_app(build_sandbox_services())
    default_status, default_payload, _ = drive(
        app,
        "POST",
        "/demo/contract-fulfillment",
        body=_demo_body(),
        headers=_json_headers(_demo_body()),
    )
    custom = _demo_body("2027-01-01T00:00:00Z")
    first_status, first_payload, _ = drive(
        app,
        "POST",
        "/demo/contract-fulfillment",
        body=custom,
        headers=_json_headers(custom),
    )
    second_status, second_payload, _ = drive(
        app,
        "POST",
        "/demo/contract-fulfillment",
        body=custom,
        headers=_json_headers(custom),
    )
    if first_status != 200 or second_status != 200:
        problems.append("statuses %d/%d" % (first_status, second_status))
        results.append(fail("10 demo custom instant", "; ".join(problems)))
        return
    if first_payload != second_payload:
        problems.append("same-instant replays diverge")
    if first_payload == default_payload:
        problems.append("a different instant reproduced the default demo")
    first = json.loads(first_payload)
    if first.get("instant") != "2027-01-01T00:00:00Z":
        problems.append("instant %r" % first.get("instant"))
    if first["contract"]["contract_id"] == json.loads(default_payload)["contract"][
        "contract_id"
    ]:
        problems.append("a new instant did not create a new contract")
    if problems:
        results.append(fail("10 demo custom instant", "; ".join(problems)))
    else:
        results.append(
            ok(
                "10 demo custom instant",
                "new instant -> new contract; same instant -> byte-identical replay",
            )
        )


def case_11_demo_invalid_instant(results: List[Result]) -> None:
    """Criterion: a malformed instant fails closed with the typed
    envelope (400, invalid-input)."""
    problems: List[str] = []
    app = build_app(build_sandbox_services())
    for raw, expected in (
        (json.dumps({"instant": "not-a-time"}), 400),
        (json.dumps({"instant": 123}), 400),
    ):
        body = raw.encode("utf-8")
        status, payload, _ = drive(
            app,
            "POST",
            "/demo/contract-fulfillment",
            body=body,
            headers=_json_headers(body),
        )
        document = json.loads(payload)
        if status != expected:
            problems.append("status %d for %s" % (status, raw))
        if (document.get("error") or {}).get("reason_code") != "invalid-input":
            problems.append("reason %r" % (document.get("error"),))
    if problems:
        results.append(fail("11 demo invalid instant", "; ".join(problems)))
    else:
        results.append(
            ok("11 demo invalid instant", "400 invalid-input for bad instant values")
        )


def case_12_malformed_json_envelope(results: List[Result]) -> None:
    """Criterion: malformed JSON is 400 malformed-json with the exact
    envelope shape and no leaked internals."""
    problems: List[str] = []
    app = build_app(build_sandbox_services())
    body = b"{not-json"
    status, payload, _ = drive(
        app,
        "POST",
        "/demo/contract-fulfillment",
        body=body,
        headers=_json_headers(body),
    )
    document = json.loads(payload)
    error = document.get("error") or {}
    if status != 400:
        problems.append("status %d" % status)
    if error.get("reason_code") != "malformed-json":
        problems.append("reason %r" % error.get("reason_code"))
    if not isinstance(error.get("message"), str) or not error.get("message"):
        problems.append("message %r" % error.get("message"))
    if error.get("backend") is not None:
        problems.append("backend %r" % error.get("backend"))
    if sorted(error) != ["backend", "message", "reason_code"]:
        problems.append("envelope members %r" % sorted(error))
    if problems:
        results.append(fail("12 malformed json envelope", "; ".join(problems)))
    else:
        results.append(
            ok("12 malformed json envelope", "400 {reason_code,message,backend:null}")
        )


def case_13_non_object_body_envelope(results: List[Result]) -> None:
    """Criterion: a non-object JSON body fails closed 400
    invalid-request-body."""
    app = build_app(build_sandbox_services())
    body = b"[1,2,3]"
    status, payload, _ = drive(
        app,
        "POST",
        "/demo/contract-fulfillment",
        body=body,
        headers=_json_headers(body),
    )
    error = (json.loads(payload).get("error")) or {}
    if status != 400 or error.get("reason_code") != "invalid-request-body":
        results.append(
            fail(
                "13 non object body envelope",
                "status %d reason %r" % (status, error.get("reason_code")),
            )
        )
        return
    results.append(
        ok("13 non object body envelope", "400 invalid-request-body")
    )


def case_14_payload_too_large(results: List[Result]) -> None:
    """Criterion: the 1 MiB body cap — both the content-length
    pre-check and the streamed-body accounting fail closed 413."""
    problems: List[str] = []
    app = build_app(build_sandbox_services())
    oversized = b"x" * (MAX_BODY_BYTES + 1)
    # (a) declared content-length over the cap
    status, payload, _ = drive(
        app,
        "POST",
        "/demo/contract-fulfillment",
        body=oversized,
        headers=[(b"content-type", b"application/json"),
                 (b"content-length", str(len(oversized)).encode("latin-1"))],
    )
    if status != 413:
        problems.append("declared-length status %d" % status)
    if (json.loads(payload).get("error") or {}).get("reason_code") != (
        "payload-too-large"
    ):
        problems.append("declared-length reason %r" % payload[:80])
    # (b) no content-length; the streamed accounting trips the cap
    status, payload, _ = drive(
        app,
        "POST",
        "/demo/contract-fulfillment",
        body=oversized,
        headers=[(b"content-type", b"application/json")],
    )
    if status != 413:
        problems.append("streamed status %d" % status)
    if (json.loads(payload).get("error") or {}).get("reason_code") != (
        "payload-too-large"
    ):
        problems.append("streamed reason %r" % payload[:80])
    if problems:
        results.append(fail("14 payload too large", "; ".join(problems)))
    else:
        results.append(
            ok("14 payload too large", "413 payload-too-large (declared + streamed)")
        )


def case_15_not_found_envelope(results: List[Result]) -> None:
    """Criterion: every unrouted request is the typed 404 envelope —
    and no stack trace or raw exception text ever escapes."""
    problems: List[str] = []
    app = build_app(build_sandbox_services())
    for method, path in (
        ("GET", "/nope"),
        ("POST", "/healthz"),
        ("DELETE", "/demo/contract-fulfillment"),
        ("GET", "/api/contracts/"),
        ("GET", "/api/contracts/a/b"),
        ("PUT", "/"),
    ):
        status, payload, _ = drive(app, method, path)
        document = json.loads(payload)
        error = document.get("error") or {}
        if status != 404:
            problems.append("%s %s -> %d" % (method, path, status))
        if error.get("reason_code") != "not-found":
            problems.append("%s %s reason %r" % (method, path, error.get("reason_code")))
        if sorted(error) != ["backend", "message", "reason_code"]:
            problems.append("%s %s members %r" % (method, path, sorted(error)))
        text = payload.decode("utf-8")
        if "Traceback" in text or "raise " in text or "__" in text:
            problems.append("%s %s leaks internals" % (method, path))
    if problems:
        results.append(fail("15 not found envelope", "; ".join(problems)))
    else:
        results.append(
            ok("15 not found envelope", "6 unrouted requests -> typed 404 envelopes")
        )


def case_16_contract_read_platform(results: List[Result]) -> None:
    """Criterion: GET /api/contracts/{id} serves the platform-side
    public store read (the composed canonical authority)."""
    problems: List[str] = []
    services = build_sandbox_services()
    app = build_app(services)
    _status, demo_payload, _ = drive(
        app,
        "POST",
        "/demo/contract-fulfillment",
        body=_demo_body(),
        headers=_json_headers(_demo_body()),
    )
    contract_id = json.loads(demo_payload)["contract"]["contract_id"]
    status, payload, _ = drive(app, "GET", "/api/contracts/%s" % contract_id)
    document = json.loads(payload)
    if status != 200:
        problems.append("status %d" % status)
    if document.get("contract_id") != contract_id:
        problems.append("contract_id %r" % document.get("contract_id"))
    if document.get("state") != "CONTRACT_ACTIVE":
        problems.append("state %r" % document.get("state"))
    if canonical_json_bytes(document) != payload:
        problems.append("not canonical bytes")
    if problems:
        results.append(fail("16 contract read platform", "; ".join(problems)))
    else:
        results.append(
            ok("16 contract read platform", "200; the store's public read, canonical")
        )


def case_17_contract_read_gateway(results: List[Result]) -> None:
    """Criterion: WITH the developer credential headers the contract
    read rides the accepted developerapi boundary (its own canonical
    envelope, verbatim)."""
    problems: List[str] = []
    services = build_sandbox_services()
    app = build_app(services)
    _status, demo_payload, _ = drive(
        app,
        "POST",
        "/demo/contract-fulfillment",
        body=_demo_body(),
        headers=_json_headers(_demo_body()),
    )
    contract_id = json.loads(demo_payload)["contract"]["contract_id"]
    status, payload, _ = drive(
        app,
        "GET",
        "/api/contracts/%s" % contract_id,
        headers=[
            (b"x-adcos-application", services.demo_application_id.encode("utf-8")),
            (b"x-adcos-credential", services.demo_credential.encode("utf-8")),
            (b"x-adcos-api-version", b"2.0"),
        ],
    )
    document = json.loads(payload)
    if status != 200:
        problems.append("status %d" % status)
    if document.get("api_version") != "2.0":
        problems.append("api_version %r" % document.get("api_version"))
    if (document.get("data") or {}).get("id") != contract_id:
        problems.append("data.id %r" % (document.get("data") or {}).get("id"))
    if problems:
        results.append(fail("17 contract read gateway", "; ".join(problems)))
    else:
        results.append(
            ok("17 contract read gateway", "200; the boundary envelope verbatim")
        )


def case_18_contract_read_unknown(results: List[Result]) -> None:
    """Criterion: an unknown contract id is the accepted domain's own
    typed 404 envelope (reason preserved verbatim)."""
    app = build_app(build_sandbox_services())
    status, payload, _ = drive(
        app, "GET", "/api/contracts/sha256:%s" % ("ab" * 32)
    )
    error = (json.loads(payload).get("error")) or {}
    if status != 404 or error.get("reason_code") != "unknown-contract":
        results.append(
            fail(
                "18 contract read unknown",
                "status %d reason %r" % (status, error.get("reason_code")),
            )
        )
        return
    results.append(
        ok("18 contract read unknown", "404 unknown-contract (domain reason kept)")
    )


def case_19_canonical_json_responses(results: List[Result]) -> None:
    """Criterion: EVERY response body is canonical JSON with an exact
    content-length (healthz, readyz, demo, and every error)."""
    problems: List[str] = []
    services = build_sandbox_services()
    app = build_app(services)
    requests = [
        ("GET", "/healthz", b"", ()),
        ("GET", "/readyz", b"", ()),
        ("GET", "/demo/contract-fulfillment", b"", ()),
        ("GET", "/nope", b"", ()),
        ("POST", "/demo/contract-fulfillment", b"{bad", _json_headers(b"{bad")),
        ("GET", "/api/contracts/sha256:%s" % ("cd" * 32), b"", ()),
    ]
    for method, path, body, headers in requests:
        status, payload, sent = drive(app, method, path, body=body, headers=headers)
        try:
            document = json.loads(payload)
        except ValueError:
            problems.append("%s %s: body is not JSON" % (method, path))
            continue
        if canonical_json_bytes(document) != payload:
            problems.append("%s %s: not canonical bytes" % (method, path))
        start = sent[0]
        header_map = {
            name.decode("latin-1").lower(): value.decode("latin-1")
            for name, value in start.get("headers") or ()
        }
        if header_map.get("content-type") != "application/json":
            problems.append("%s %s: content-type" % (method, path))
        if int(header_map.get("content-length", "-1")) != len(payload):
            problems.append("%s %s: content-length" % (method, path))
    if problems:
        results.append(fail("19 canonical json responses", "; ".join(problems)))
    else:
        results.append(
            ok("19 canonical json responses", "6/6 canonical bodies + exact headers")
        )


def case_20_lifespan_protocol(results: List[Result]) -> None:
    """Criterion: the ASGI lifespan protocol is acknowledged."""
    app = build_app(build_sandbox_services())
    sent = drive_lifespan(app)
    types = [message.get("type") for message in sent]
    if types != ["lifespan.startup.complete", "lifespan.shutdown.complete"]:
        results.append(fail("20 lifespan protocol", "messages %r" % types))
        return
    results.append(
        ok("20 lifespan protocol", "startup + shutdown acknowledged")
    )


def case_21_sandbox_never_claims_production(results: List[Result]) -> None:
    """Criterion (the DEC-0126 honesty mandate): the sandbox runtime
    never claims production — the mode is reported as sandbox
    everywhere and no production claim appears in any body."""
    problems: List[str] = []
    services = build_sandbox_services()
    app = build_app(services)
    for method, path in (
        ("GET", "/healthz"),
        ("GET", "/readyz"),
        ("GET", "/demo/contract-fulfillment"),
    ):
        _status, payload, _ = drive(app, method, path)
        text = payload.decode("utf-8")
        if "production" in text:
            problems.append("%s claims production: %r" % (path, text[:80]))
    document = json.loads(drive(app, "GET", "/demo/contract-fulfillment")[1])
    if document.get("mode") != "sandbox":
        problems.append("demo mode %r" % document.get("mode"))
    if document.get("environment") != "sandbox":
        problems.append("demo environment %r" % document.get("environment"))
    if document.get("execution", {}).get("sandbox") is not True:
        problems.append("execution not marked sandbox")
    if problems:
        results.append(fail("21 sandbox never claims production", "; ".join(problems)))
    else:
        results.append(
            ok("21 sandbox never claims production", "mode=sandbox everywhere")
        )


def case_22_demo_evidence_class_is_software(results: List[Result]) -> None:
    """Criterion (EVID-002..EVID-008 honesty): the demonstration is
    SOFTWARE-class only — no physical connectivity claim is made."""
    problems: List[str] = []
    app = build_app(build_sandbox_services())
    _status, payload, _ = drive(
        app,
        "POST",
        "/demo/contract-fulfillment",
        body=_demo_body(),
        headers=_json_headers(_demo_body()),
    )
    text = payload.decode("utf-8")
    document = json.loads(payload)
    if document.get("evidence_class") != "SOFTWARE":
        problems.append("evidence_class %r" % document.get("evidence_class"))
    for forbidden in (
        "physical connectivity",
        "physical-connectivity",
        "EVID-00",
        "radio",
        "gNB",
    ):
        if forbidden in text:
            problems.append("forbidden claim %r present" % forbidden)
    if problems:
        results.append(fail("22 demo evidence class is software", "; ".join(problems)))
    else:
        results.append(
            ok(
                "22 demo evidence class is software",
                "evidence_class=SOFTWARE; no physical claim vocabulary",
            )
        )


def case_23_production_mode_demo(results: List[Result]) -> None:
    """Criterion: the production mode (fake durable backend) serves
    the same demonstration through the HTTP surface with
    mode=production — and the writes landed in the durable tables."""
    problems: List[str] = []
    database = _FakeDatabase()
    services = _production_services(database, tmp="prod-demo")
    app = build_app(services)
    status, payload, _ = drive(
        app,
        "POST",
        "/demo/contract-fulfillment",
        body=_demo_body(),
        headers=_json_headers(_demo_body()),
    )
    if status != 200:
        problems.append("status %d" % status)
        results.append(fail("23 production mode demo", "; ".join(problems)))
        return
    document = json.loads(payload)
    if document.get("mode") != "production":
        problems.append("mode %r" % document.get("mode"))
    if document.get("evidence_class") != "SOFTWARE":
        problems.append("evidence_class %r" % document.get("evidence_class"))
    for table in (
        "adcos_api_journal",
        "adcos_contract_journal",
        "adcos_evidence_journal",
    ):
        if database.count(table) == 0:
            problems.append("no durable rows in %s" % table)
    if problems:
        results.append(fail("23 production mode demo", "; ".join(problems)))
    else:
        results.append(
            ok(
                "23 production mode demo",
                "200 mode=production; rows in all three durable journals",
            )
        )


def case_24_cross_process_determinism(results: List[Result]) -> None:
    """Criterion: the demonstration body digest is byte-identical
    across PYTHONHASHSEED subprocesses, each assembling a FRESH app
    from the environment (the deployment entrypoint shape)."""
    script = (
        "import sys, hashlib; sys.path.insert(0, %r); "
        "from runtime.sandbox import build_sandbox_services; "
        "from runtime.asgi import build_app; "
        "from runtime.demo import run_contract_fulfillment_demo; "
        "from protocol.canonicalization import canonical_json_bytes; "
        "services = build_sandbox_services(); "
        "document = run_contract_fulfillment_demo(services); "
        "print(hashlib.sha256(canonical_json_bytes(document)).hexdigest())"
        % str(REPO_ROOT)
    )
    digests = []
    for seed in ("0", "1", "7919"):
        probe = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            env={"PYTHONHASHSEED": seed, "PATH": ""},
        )
        if probe.returncode != 0:
            results.append(
                fail(
                    "24 cross process determinism",
                    "seed %s failed: %s" % (seed, probe.stderr[:200]),
                )
            )
            return
        digests.append(probe.stdout.strip())
    if len(set(digests)) != 1:
        results.append(
            fail("24 cross process determinism", "digests %s" % digests)
        )
        return
    results.append(
        ok(
            "24 cross process determinism",
            "byte-identical across PYTHONHASHSEED 0/1/7919 (%s)"
            % digests[0][:16],
        )
    )


_CASES = (
    case_01_liveness_shape,
    case_02_readiness_sandbox,
    case_03_readiness_production_ready,
    case_04_readiness_production_unavailable,
    case_05_readiness_delegated_r2,
    case_06_demo_post_get_byte_identical,
    case_07_demo_three_fresh_instances_identical,
    case_08_demo_evidence_chain_shape,
    case_09_demo_canonical_serializable,
    case_10_demo_custom_instant,
    case_11_demo_invalid_instant,
    case_12_malformed_json_envelope,
    case_13_non_object_body_envelope,
    case_14_payload_too_large,
    case_15_not_found_envelope,
    case_16_contract_read_platform,
    case_17_contract_read_gateway,
    case_18_contract_read_unknown,
    case_19_canonical_json_responses,
    case_20_lifespan_protocol,
    case_21_sandbox_never_claims_production,
    case_22_demo_evidence_class_is_software,
    case_23_production_mode_demo,
    case_24_cross_process_determinism,
)


def main() -> int:
    print("ADCOS deployment runtime self-test (pure-stdlib ASGI surface)")
    print("=" * 78)
    results: List[Result] = []
    for case in _CASES:
        try:
            case(results)
        except Exception as error:  # noqa: BLE001 - the battery never crashes silently
            results.append(fail(case.__name__, "raised: %r" % (error,)))
    width = max(len(name) for name, _ok, _detail in results)
    passed = 0
    for name, is_ok, detail in results:
        marker = "ok  " if is_ok else "FAIL"
        print("[%s] %-*s %s" % (marker, width, name, detail))
        if is_ok:
            passed += 1
    print("-" * 78)
    passed_count = sum(1 for _, is_ok, _ in results if is_ok)
    if passed_count == len(results):
        print("Result: PASS (%d/%d cases)" % (passed_count, len(results)))
        return 0
    print("Result: FAIL (%d/%d cases passed)" % (passed_count, len(results)))
    return 1


if __name__ == "__main__":
    sys.exit(main())
