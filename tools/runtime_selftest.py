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

    @property
    def description(self) -> Optional[Tuple[Any, ...]]:
        """DB-API 2.0 mirror for the adapter's conditional fetch
        (None when the last statement produced no result set — the DDL
        shape; a truthy descriptor tuple when it did — the SELECT
        shape).  Mirrors the persistence battery's FakeCursor so the
        adapter's conditional fetch is exercised on both branches
        offline, exactly as the real pg8000 cursor behaves."""
        if self._rows:
            return (("<column>",),)
        return None

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


def case_25_coordination_fallback(results: List[Result]) -> None:
    """Criterion: the DESIGN-AUTHORIZED coordination fallback — an
    unreachable Upstash at assembly degrades to the accepted
    in-process limiter WITH THE DISCLOSURE (readiness
    ``degraded-ok`` + the fallback detail); a healthy Upstash wires
    as ``ready``; the demo runs in the degraded posture."""
    import tempfile

    import backends.upstash as upstash_mod
    from runtime.wiring import build_production_services

    env = dict(_PRODUCTION_ENV)
    env["ADCOS_REDIS_REST_URL"] = "https://adcos-battery.upstash.io"
    env["ADCOS_REDIS_REST_TOKEN"] = "adcos-battery-token"

    def _pong(method, url, headers, body):
        return 200, json.dumps({"result": "PONG"}).encode("utf-8")

    def _dead(method, url, headers, body):
        raise OSError("connection reset by battery")

    original = upstash_mod._urllib_transport
    try:
        # -- healthy Upstash: wired as ready --------------------------
        database = _FakeDatabase()
        upstash_mod._urllib_transport = _pong
        healthy = build_production_services(
            environ=env,
            journal_dir=Path(tempfile.gettempdir())
            / "adcos-runtime-battery-cf-healthy",
            connection_factory=_fake_factory(database),
        )
        app_h = build_app(healthy)
        status_h, payload_h, _ = drive(app_h, "GET", "/readyz")
        doc_h = json.loads(payload_h)
        backends_h = doc_h.get("backends") or {}
        # -- unreachable Upstash: the disclosed fallback --------------
        upstash_mod._urllib_transport = _dead
        degraded = build_production_services(
            environ=env,
            journal_dir=Path(tempfile.gettempdir())
            / "adcos-runtime-battery-cf-degraded",
            connection_factory=_fake_factory(_FakeDatabase()),
        )
        app_d = build_app(degraded)
        status_d, payload_d, _ = drive(app_d, "GET", "/readyz")
        doc_d = json.loads(payload_d)
        backends_d = doc_d.get("backends") or {}
        status_demo, payload_demo = _app_post_demo(app_d)
        doc_demo = json.loads(payload_demo) if status_demo == 200 else {}
    finally:
        upstash_mod._urllib_transport = original

    problems: List[str] = []
    if status_h != 200 or doc_h.get("ok") is not True:
        problems.append("healthy readyz %d %r" % (status_h, doc_h.get("ok")))
    if backends_h.get("upstash", {}).get("state") != "ready":
        problems.append("healthy upstash %r" % backends_h.get("upstash"))
    if status_d != 200 or doc_d.get("ok") is not True:
        problems.append("degraded readyz %d ok=%r" % (status_d, doc_d.get("ok")))
    upstash_entry = backends_d.get("upstash", {})
    if upstash_entry.get("state") != "degraded-ok":
        problems.append("fallback state %r" % upstash_entry)
    if "coordination fallback active" not in str(
        upstash_entry.get("detail", "")
    ):
        problems.append("fallback detail not disclosed: %r" % upstash_entry)
    if backends_d.get("postgres", {}).get("state") != "ready":
        problems.append("postgres %r" % backends_d.get("postgres"))
    if backends_d.get("evidence_store", {}).get("state") != "ready":
        problems.append("evidence_store %r" % backends_d.get("evidence_store"))
    if status_demo != 200 or doc_demo.get("evidence_class") != "SOFTWARE":
        problems.append(
            "degraded demo %d %r" % (status_demo, doc_demo.get("evidence_class"))
        )
    if problems:
        results.append(fail("25 coordination fallback", "; ".join(problems)))
    else:
        results.append(
            ok(
                "25 coordination fallback",
                "unreachable Upstash -> the in-process limiter with the "
                "degraded-ok disclosure (readiness 200, demo 200); healthy "
                "Upstash wires ready",
            )
        )


# ---------------------------------------------------------------------------
# The developer API request boundary (DEC-0127 console era): the generic
# /api/{version}/* TRANSPORT-ONLY translation onto the accepted gateway
# ---------------------------------------------------------------------------


def _boundary_headers(
    services: Any,
    *extra: Tuple[str, str],
) -> List[Tuple[bytes, bytes]]:
    """The developer credential headers (plus optional extras) for a
    boundary request (lower-case names — the ASGI header convention)."""
    headers = [
        (b"x-adcos-application", services.demo_application_id.encode("utf-8")),
        (b"x-adcos-credential", services.demo_credential.encode("utf-8")),
    ]
    for name, value in extra:
        headers.append((name.encode("utf-8"), value.encode("utf-8")))
    return headers


def _boundary_intent_body(base: str) -> Dict[str, Any]:
    """The canonical intent-creation body (the demonstration's own
    idiom — every semantics-bearing member rides its frozen reference
    kind; the boundary never invents a schema)."""
    from runtime.demo import _intent_body

    return _intent_body(base)


def _response_headers(sent: List[Mapping[str, Any]]) -> Dict[str, str]:
    start = next(
        (m for m in sent if m.get("type") == "http.response.start"), None
    )
    if start is None:
        return {}
    return {
        name.decode("latin-1"): value.decode("latin-1")
        for name, value in start.get("headers") or ()
    }


def case_26_boundary_application_self(results: List[Result]) -> None:
    """Criterion: the versioned boundary translates the application
    self read onto the gateway — the boundary's own envelope verbatim,
    its response headers forwarded, and the route-prefix version used
    when the version header is absent."""
    problems: List[str] = []
    services = build_sandbox_services()
    app = build_app(services)
    status, payload, sent = drive(
        app, "GET", "/api/2.0/application", headers=_boundary_headers(services)
    )
    document = json.loads(payload)
    if status != 200:
        problems.append("status %d" % status)
    if document.get("api_version") != "2.0":
        problems.append("api_version %r" % document.get("api_version"))
    if document.get("environment") != services.environment:
        problems.append("environment %r" % document.get("environment"))
    data = document.get("data") or {}
    if data.get("application_id") != services.demo_application_id:
        problems.append("application_id %r" % data.get("application_id"))
    if not data.get("capabilities"):
        problems.append("capabilities %r" % data.get("capabilities"))
    headers = _response_headers(sent)
    if not headers.get("X-ADCOS-Request-Id"):
        problems.append("no X-ADCOS-Request-Id forwarded")
    if headers.get("X-ADCOS-API-Version") != "2.0":
        problems.append("X-ADCOS-API-Version %r" % headers.get("X-ADCOS-API-Version"))
    if headers.get("X-ADCOS-Environment") != services.environment:
        problems.append(
            "X-ADCOS-Environment %r" % headers.get("X-ADCOS-Environment")
        )
    if headers.get("content-type") != "application/json":
        problems.append("content-type %r" % headers.get("content-type"))
    if canonical_json_bytes(document) != payload:
        problems.append("body is not canonical bytes")
    if problems:
        results.append(fail("26 boundary application self", "; ".join(problems)))
    else:
        results.append(
            ok(
                "26 boundary application self",
                "200; the boundary envelope verbatim + its headers forwarded "
                "(request-id/api-version/environment)",
            )
        )


def case_27_boundary_intent_contract_journey(results: List[Result]) -> None:
    """Criterion: the FULL intent -> offer -> activation -> contract
    read/usage/assurance journey rides the versioned boundary (each
    leg the gateway's own admission: idempotency key required on
    mutations; every body the canonical envelope)."""
    problems: List[str] = []
    services = build_sandbox_services()
    app = build_app(services)
    base = "2026-09-14T03:00:00Z"
    intent_body = _boundary_intent_body(base)

    status, payload, _ = drive(
        app,
        "POST",
        "/api/2.0/intents",
        body=json.dumps(intent_body).encode("utf-8"),
        headers=_boundary_headers(services, ("x-adcos-idempotency-key", "b27:create")),
    )
    document = json.loads(payload)
    if status != 200:
        problems.append("intent create status %d" % status)
    contract_id = (document.get("data") or {}).get("id", "")
    if not contract_id:
        problems.append("intent create returned no id")
    if (document.get("data") or {}).get("contract_id") != contract_id:
        problems.append("intent contract_id mismatch")

    offers_body = {
        "offers": [
            {
                "ref_kind": "offer",
                "value": "demo:boundary:offer:v1",
                "provenance": {
                    "issuer": "demo:boundary:offer-issuer",
                    "decision_refs": ["demo:boundary:offer:v1"],
                },
            }
        ],
        "recorded_at": "2026-09-14T03:00:10Z",
    }
    status, payload, _ = drive(
        app,
        "POST",
        "/api/2.0/intents/%s/offers" % contract_id,
        body=json.dumps(offers_body).encode("utf-8"),
        headers=_boundary_headers(services, ("x-adcos-idempotency-key", "b27:offers")),
    )
    if status != 200:
        problems.append("offers accept status %d: %s" % (status, payload[:120]))

    activation_body = {
        "activated_at": "2026-09-14T03:00:20Z",
        "signature_refs": [
            {"ref_kind": "signature", "value": "demo:boundary:signature:v1"}
        ],
    }
    status, payload, _ = drive(
        app,
        "POST",
        "/api/2.0/intents/%s/activation" % contract_id,
        body=json.dumps(activation_body).encode("utf-8"),
        headers=_boundary_headers(
            services, ("x-adcos-idempotency-key", "b27:activate")
        ),
    )
    if status != 200:
        problems.append("activation status %d: %s" % (status, payload[:120]))

    for route in (
        "/api/2.0/intents",
        "/api/2.0/intents/%s" % contract_id,
        "/api/2.0/intents/%s/lifecycle" % contract_id,
        "/api/2.0/contracts",
        "/api/2.0/contracts/%s" % contract_id,
        "/api/2.0/contracts/%s/usage" % contract_id,
        "/api/2.0/contracts/%s/assurance" % contract_id,
    ):
        status, payload, _ = drive(
            app, "GET", route, headers=_boundary_headers(services)
        )
        document = json.loads(payload)
        if status != 200 or "data" not in document:
            problems.append(
                "%s -> %d %s"
                % (route, status, (document.get("error") or {}).get("reason", "?"))
            )
        elif canonical_json_bytes(document) != payload:
            problems.append("%s -> not canonical bytes" % route)

    if problems:
        results.append(
            fail("27 boundary intent/contract journey", "; ".join(problems))
        )
    else:
        results.append(
            ok(
                "27 boundary intent/contract journey",
                "intent -> offers -> activation -> list/get/usage/assurance "
                "all 200 through the boundary (idempotency keys on every "
                "mutation)",
            )
        )


def case_28_boundary_lease_journey(results: List[Result]) -> None:
    """Criterion: the lease lifecycle rides the versioned boundary —
    grant -> list -> get for both leases, RENEWAL on one (the accepted
    lease state machine moves it to renewed) and REVOCATION on the
    other (only granted/active leases revoke — the domain's own
    transition rule, exercised through the boundary)."""
    problems: List[str] = []
    services = build_sandbox_services()
    app = build_app(services)
    base = "2026-09-14T04:00:00Z"
    status, payload, _ = drive(
        app,
        "POST",
        "/api/2.0/intents",
        body=json.dumps(_boundary_intent_body(base)).encode("utf-8"),
        headers=_boundary_headers(services, ("x-adcos-idempotency-key", "b28:create")),
    )
    contract_id = (json.loads(payload).get("data") or {}).get("id", "")
    if not contract_id:
        results.append(
            fail("28 boundary lease journey", "intent create returned no id")
        )
        return

    def _grant(key: str, granted_at: str, not_before: str, not_after: str) -> str:
        lease_body = {
            "granted_at": granted_at,
            "not_before": not_before,
            "not_after": not_after,
        }
        status, payload, _ = drive(
            app,
            "POST",
            "/api/2.0/contracts/%s/leases" % contract_id,
            body=json.dumps(lease_body).encode("utf-8"),
            headers=_boundary_headers(services, ("x-adcos-idempotency-key", key)),
        )
        document = json.loads(payload)
        if status != 200:
            problems.append(
                "lease grant(%s) %d: %s" % (key, status, payload[:140])
            )
            return ""
        return (document.get("data") or {}).get("id", "")

    # lease A: granted, then REVOKED (granted/active -> revoked)
    lease_a = _grant(
        "b28:lease-a",
        "2026-09-14T04:00:30Z",
        "2026-09-14T04:00:30Z",
        "2026-09-14T05:00:30Z",
    )
    # lease B: granted, then RENEWED (the renewal window strictly after)
    lease_b = _grant(
        "b28:lease-b",
        "2026-09-14T04:01:00Z",
        "2026-09-14T04:01:00Z",
        "2026-09-14T05:01:00Z",
    )
    if problems:
        results.append(fail("28 boundary lease journey", "; ".join(problems)))
        return

    for route in ("/api/2.0/leases", "/api/2.0/leases/%s" % lease_a):
        status, payload, _ = drive(
            app, "GET", route, headers=_boundary_headers(services)
        )
        if status != 200:
            problems.append(
                "%s -> %d %s"
                % (
                    route,
                    status,
                    (json.loads(payload).get("error") or {}).get("reason", "?"),
                )
            )

    renew_body = {
        "granted_at": "2026-09-14T04:30:00Z",
        "not_before": "2026-09-14T05:01:00Z",
        "not_after": "2026-09-14T06:01:00Z",
    }
    status, payload, _ = drive(
        app,
        "POST",
        "/api/2.0/leases/%s/renewal" % lease_b,
        body=json.dumps(renew_body).encode("utf-8"),
        headers=_boundary_headers(services, ("x-adcos-idempotency-key", "b28:renew")),
    )
    if status != 200:
        problems.append("lease renewal %d: %s" % (status, payload[:140]))

    revoke_body = {
        "recorded_at": "2026-09-14T04:45:00Z",
        "reason": "battery: deterministic lease revocation",
    }
    status, payload, _ = drive(
        app,
        "POST",
        "/api/2.0/leases/%s/revocation" % lease_a,
        body=json.dumps(revoke_body).encode("utf-8"),
        headers=_boundary_headers(services, ("x-adcos-idempotency-key", "b28:revoke")),
    )
    if status != 200:
        problems.append("lease revocation %d: %s" % (status, payload[:140]))

    status, payload, _ = drive(
        app, "GET", "/api/2.0/leases/%s" % lease_a, headers=_boundary_headers(services)
    )
    if status == 200:
        state = ((json.loads(payload).get("data") or {}).get("state")) or ""
        if state != "revoked":
            problems.append("revoked lease state %r" % state)

    if problems:
        results.append(fail("28 boundary lease journey", "; ".join(problems)))
    else:
        results.append(
            ok(
                "28 boundary lease journey",
                "grant -> list/get for both leases; renewal (granted -> "
                "renewed) and revocation (granted -> revoked, the domain's "
                "own transition rule) all 200 through the boundary",
            )
        )


def case_29_boundary_webhook_journey(results: List[Result]) -> None:
    """Criterion: the webhook endpoint surface (register -> list -> get
    -> deliveries) rides the versioned boundary."""
    problems: List[str] = []
    services = build_sandbox_services()
    app = build_app(services)
    register_body = {
        "url": "https://console.example/adcos/webhook",
        "event_types": [
            "connectivity_intent.created",
            "connectivity_lease.granted",
            "webhook_endpoint.registered",
        ],
    }
    status, payload, _ = drive(
        app,
        "POST",
        "/api/2.0/webhook-endpoints",
        body=json.dumps(register_body).encode("utf-8"),
        headers=_boundary_headers(
            services, ("x-adcos-idempotency-key", "b29:register")
        ),
    )
    document = json.loads(payload)
    if status != 200:
        results.append(
            fail(
                "29 boundary webhook journey",
                "register %d: %s" % (status, payload[:160]),
            )
        )
        return
    endpoint_id = (document.get("data") or {}).get("id", "")
    if not endpoint_id:
        results.append(
            fail("29 boundary webhook journey", "register returned no id")
        )
        return

    for route in (
        "/api/2.0/webhook-endpoints",
        "/api/2.0/webhook-endpoints/%s" % endpoint_id,
        "/api/2.0/webhook-endpoints/%s/deliveries" % endpoint_id,
    ):
        status, payload, _ = drive(
            app, "GET", route, headers=_boundary_headers(services)
        )
        if status != 200:
            problems.append(
                "%s -> %d %s"
                % (
                    route,
                    status,
                    (json.loads(payload).get("error") or {}).get("reason", "?"),
                )
            )
    if problems:
        results.append(fail("29 boundary webhook journey", "; ".join(problems)))
    else:
        results.append(
            ok(
                "29 boundary webhook journey",
                "register -> list -> get -> deliveries all 200 through the "
                "boundary",
            )
        )


def case_30_boundary_error_discipline(results: List[Result]) -> None:
    """Criterion: the boundary's ERROR discipline — the gateway's own
    canonical reasons preserved verbatim (authentication-invalid,
    route-unknown, version-unsupported), the runtime's typed envelopes
    for transport-level failures (malformed JSON), and every body
    canonical JSON."""
    problems: List[str] = []
    services = build_sandbox_services()
    app = build_app(services)

    status, payload, sent = drive(app, "GET", "/api/2.0/application")
    document = json.loads(payload)
    error = document.get("error") or {}
    if status != 401 or error.get("reason") != "authentication-invalid":
        problems.append(
            "unauthenticated %d %r" % (status, error.get("reason"))
        )
    headers = _response_headers(sent)
    if not headers.get("X-ADCOS-Request-Id"):
        problems.append("unauthenticated error carries no request id header")

    status, payload, _ = drive(
        app, "GET", "/api/2.0/application", headers=_boundary_headers(services)
    )
    if status != 200:
        problems.append("credentialed prelude %d" % status)

    status, payload, _ = drive(
        app,
        "GET",
        "/api/2.0/application",
        headers=_boundary_headers(services, ("x-adcos-api-version", "3.0")),
    )
    error = (json.loads(payload).get("error")) or {}
    if status != 400 or error.get("reason") != "version-unsupported":
        problems.append(
            "version disagreement %d %r" % (status, error.get("reason"))
        )

    status, payload, _ = drive(
        app, "GET", "/api/2.0/unknown", headers=_boundary_headers(services)
    )
    error = (json.loads(payload).get("error")) or {}
    if status != 404 or error.get("reason") != "route-unknown":
        problems.append("unknown route %d %r" % (status, error.get("reason")))

    status, payload, _ = drive(
        app,
        "POST",
        "/api/2.0/intents",
        body=b"{bad",
        headers=_boundary_headers(services),
    )
    error = (json.loads(payload).get("error")) or {}
    if status != 400 or error.get("reason_code") != "malformed-json":
        problems.append(
            "malformed boundary body %d %r" % (status, error.get("reason_code"))
        )

    for method, path, body, headers in (
        ("GET", "/api/2.0/application", b"", ()),
        ("GET", "/api/2.0/unknown", b"", _boundary_headers(services)),
        ("POST", "/api/2.0/intents", b"{bad", _boundary_headers(services)),
    ):
        _s, payload, _sent = drive(app, method, path, body=body, headers=headers)
        try:
            document = json.loads(payload)
        except ValueError:
            problems.append("%s %s: body is not JSON" % (method, path))
            continue
        if canonical_json_bytes(document) != payload:
            problems.append("%s %s: not canonical bytes" % (method, path))

    if problems:
        results.append(fail("30 boundary error discipline", "; ".join(problems)))
    else:
        results.append(
            ok(
                "30 boundary error discipline",
                "401 authentication-invalid / 400 version-unsupported / 404 "
                "route-unknown / 400 malformed-json — canonical reasons "
                "preserved verbatim; bodies canonical",
            )
        )


def case_31_boundary_idempotent_replay(results: List[Result]) -> None:
    """Criterion: the durable idempotency replay through the boundary —
    the SAME mutation with the SAME key replays byte-identically with
    the X-ADCOS-Idempotent-Replay header; a DIFFERENT key is a NEW
    admission (a distinct resource identity)."""
    problems: List[str] = []
    services = build_sandbox_services()
    app = build_app(services)
    body = json.dumps(_boundary_intent_body("2026-09-14T05:00:00Z")).encode("utf-8")

    status_a, payload_a, sent_a = drive(
        app,
        "POST",
        "/api/2.0/intents",
        body=body,
        headers=_boundary_headers(services, ("x-adcos-idempotency-key", "b31:one")),
    )
    status_b, payload_b, sent_b = drive(
        app,
        "POST",
        "/api/2.0/intents",
        body=body,
        headers=_boundary_headers(services, ("x-adcos-idempotency-key", "b31:one")),
    )
    if status_a != 200 or status_b != 200:
        problems.append("statuses %d/%d" % (status_a, status_b))
    if payload_a != payload_b:
        problems.append("replay body not byte-identical")
    headers_b = _response_headers(sent_b)
    if headers_b.get("X-ADCOS-Idempotent-Replay") != "true":
        problems.append(
            "replay marker %r" % headers_b.get("X-ADCOS-Idempotent-Replay")
        )
    headers_a = _response_headers(sent_a)
    if headers_a.get("X-ADCOS-Idempotent-Replay") is not None:
        problems.append("first admission carries a replay marker")

    status_c, payload_c, sent_c = drive(
        app,
        "POST",
        "/api/2.0/intents",
        body=body,
        headers=_boundary_headers(services, ("x-adcos-idempotency-key", "b31:two")),
    )
    if status_c != 200:
        problems.append("second key status %d" % status_c)
    document_c = json.loads(payload_c)
    id_b = (json.loads(payload_b).get("data") or {}).get("id", "")
    id_c = (document_c.get("data") or {}).get("id", "")
    if id_b != id_c:
        problems.append(
            "the content-derived contract identity changed across keys "
            "(%r vs %r)" % (id_b[:24], id_c[:24])
        )
    idem_b = (json.loads(payload_b).get("idempotency") or {}).get("key", "")
    idem_c = (document_c.get("idempotency") or {}).get("key", "")
    if idem_c != "b31:two" or idem_b != "b31:one":
        problems.append(
            "per-key admission ledger wrong (%r / %r)" % (idem_b, idem_c)
        )
    if (document_c.get("idempotency") or {}).get("replayed") is not False:
        problems.append("the different-key admission claims a replay")
    headers_c = _response_headers(sent_c)
    if headers_c.get("X-ADCOS-Idempotent-Replay") is not None:
        problems.append("the different-key admission carries a replay marker")
    if payload_c == payload_b:
        problems.append(
            "the different-key admission body is byte-identical to the "
            "first (the idempotency block must name its own key)"
        )

    if problems:
        results.append(fail("31 boundary idempotent replay", "; ".join(problems)))
    else:
        results.append(
            ok(
                "31 boundary idempotent replay",
                "same key -> byte-identical replay + the replay header; "
                "different key -> the SAME content-derived contract identity "
                "through a DISTINCT per-key admission (its own idempotency "
                "block, no replay marker)",
            )
        )


def case_32_boundary_platform_read_preserved(results: List[Result]) -> None:
    """Criterion: the UNVERSIONED platform-side contract read keeps its
    accepted semantics beside the versioned boundary — the same
    contract read through /api/contracts/{id} (the platform dict, no
    credentials required) and through /api/2.0/contracts/{id} (the
    boundary envelope, credentials required) — and an undeclared
    version segment never collides with the platform namespace."""
    problems: List[str] = []
    services = build_sandbox_services()
    app = build_app(services)
    status, payload, _ = drive(
        app,
        "POST",
        "/api/2.0/intents",
        body=json.dumps(_boundary_intent_body("2026-09-14T06:00:00Z")).encode(
            "utf-8"
        ),
        headers=_boundary_headers(services, ("x-adcos-idempotency-key", "b32:create")),
    )
    contract_id = (json.loads(payload).get("data") or {}).get("id", "")
    if not contract_id:
        results.append(
            fail("32 platform read preserved", "intent create returned no id")
        )
        return

    status, payload, _ = drive(
        app, "GET", "/api/contracts/%s" % contract_id
    )
    platform = json.loads(payload)
    if status != 200 or platform.get("contract_id") != contract_id:
        problems.append(
            "platform read %d contract_id %r"
            % (status, platform.get("contract_id"))
        )
    if canonical_json_bytes(platform) != payload:
        problems.append("platform read not canonical bytes")

    status, payload, _ = drive(
        app,
        "GET",
        "/api/2.0/contracts/%s" % contract_id,
        headers=_boundary_headers(services),
    )
    boundary = json.loads(payload)
    if status != 200:
        problems.append("boundary read %d" % status)
    elif (boundary.get("data") or {}).get("id") != contract_id:
        problems.append("boundary read id mismatch")

    status, payload, _ = drive(
        app, "GET", "/api/2.0/contracts/%s" % contract_id
    )
    error = (json.loads(payload).get("error")) or {}
    if status != 401 or error.get("reason") != "authentication-invalid":
        problems.append(
            "unauthenticated boundary read %d %r" % (status, error.get("reason"))
        )

    if problems:
        results.append(fail("32 platform read preserved", "; ".join(problems)))
    else:
        results.append(
            ok(
                "32 platform read preserved",
                "the unversioned platform read (200, no credentials) and the "
                "versioned boundary read (200, credentials / 401 without) "
                "coexist with their accepted semantics",
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
    case_25_coordination_fallback,
    case_26_boundary_application_self,
    case_27_boundary_intent_contract_journey,
    case_28_boundary_lease_journey,
    case_29_boundary_webhook_journey,
    case_30_boundary_error_discipline,
    case_31_boundary_idempotent_replay,
    case_32_boundary_platform_read_preserved,
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
