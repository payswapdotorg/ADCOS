"""The pure-stdlib ASGI application of the ADCOS deployment runtime.

A single async callable ``app(scope, receive, send)`` (the deployment
entrypoint — Vercel's Python runtime imports it from ``api/index.py``)
plus the factory :func:`build_app` (``build_app(services) -> app``).

The HTTP layer is a THIN TRANSLATION only — NO domain logic lives
here. Every semantic flows through the injected
:class:`~runtime.services.RuntimeServices` (the accepted authorities,
composed by :mod:`runtime.sandbox` or :mod:`runtime.wiring`).

Routes (canonical-JSON in/out, ``content-type: application/json``):

- ``GET /healthz`` — liveness: always 200
  ``{"ok": true, "service": "adcos-runtime"}``;
- ``GET /readyz`` — readiness: the deployment mode + every consumed
  backend's state; 200 when all ready, 503 with per-backend detail
  when not;
- ``POST /demo/contract-fulfillment`` — the deterministic
  contract-fulfillment demonstration (optional JSON body member
  ``"instant"``; default the fixed constant);
- ``GET /demo/contract-fulfillment`` — the same demonstration,
  idempotently (the GET form; byte-identical body to the default
  POST);
- ``GET /api/contracts/{contract_id}`` — the canonical contract read.
  WITH the developer credential headers (``X-ADCOS-Application`` /
  ``X-ADCOS-Credential`` [/ ``X-ADCOS-API-Version``]) the request is
  translated onto the accepted ``developerapi`` request boundary
  (route ``/api/2.0/contracts/{id}``) and the boundary's own canonical
  envelope is returned verbatim; WITHOUT them the platform-side public
  read of the canonical authority is served (the store's
  ``contract()`` read — the runtime holds the composed authority, so
  this is the operator's diagnostic view);
- everything else — 404.

ERROR DISCIPLINE: EVERY error response is the typed envelope
``{"error": {"reason_code": ..., "message": ..., "backend": ...}}``
with an appropriate HTTP status. Domain errors surface their own
frozen machine-readable reason codes (preserved verbatim — the
developerapi boundary's reason-preservation discipline); backend
failures name the backend; NO stack trace, NO raw exception text ever
escapes (``detail``/``message`` strings are the domains' own
deterministic, secret-free texts; unexpected failures collapse to
``"internal-error"`` with no detail). Request bodies are capped at
1 MiB (``413 payload-too-large``); malformed JSON is ``400
malformed-json``.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

from protocol.canonicalization import (
    CanonicalizationError,
    canonical_json_bytes,
)

from developerapi.errors import (
    CANONICAL_REASON_HTTP_STATUS,
    DeveloperApiError,
    DeveloperApiReasonCode,
)
from developerapi.gateway import ApiRequest
from developerapi.schema import API_VERSION_HEADER
from developerapi.sdk import APPLICATION_HEADER, CREDENTIAL_HEADER

from contracts.model import ContractError, ContractReason

from agent.errors import AgentError

from executionplans.errors import ExecutionPlanError

from evidence.errors import EvidenceError

from adapters.errors import AdapterError

from .demo import DEFAULT_DEMO_INSTANT, run_contract_fulfillment_demo
from .health import liveness_body, readiness
from .services import RuntimeServices

try:  # pragma: no cover - the postgres adapter is stdlib-only; the
    # guard exists so the ASGI layer never hard-depends on the
    # backends package being importable in exotic embeds
    from backends.postgres import PostgresBackendError
except ImportError:  # pragma: no cover
    class PostgresBackendError(Exception):  # type: ignore[no-redef]
        """Placeholder never raised (the real adapter is stdlib-only)."""

        reason_code = "backend-unavailable"
        backend = "postgres"


__all__ = [
    "RuntimeBoundaryError",
    "MAX_BODY_BYTES",
    "app",
    "build_app",
]

#: The request-body cap (1 MiB).
MAX_BODY_BYTES = 1024 * 1024


class RuntimeBoundaryError(Exception):
    """A typed runtime-boundary failure (the HTTP envelope's own error
    class): a machine-readable ``reason_code``, a deterministic
    human ``message``, the failing ``backend`` name (``None`` when the
    failure is not backend-attributable) and the HTTP ``status``."""

    def __init__(
        self,
        reason_code: str,
        message: str,
        *,
        backend: Optional[str] = None,
        status: int = 500,
    ) -> None:
        super().__init__("%s: %s" % (reason_code, message))
        self.reason_code = reason_code
        self.message = message
        self.backend = backend
        self.status = status


# ---------------------------------------------------------------------------
# The request/response translation (thin; NO domain logic)
# ---------------------------------------------------------------------------


def _error_document(
    reason_code: str, message: str, backend: Optional[str] = None
) -> Dict[str, Any]:
    return {
        "error": {
            "reason_code": reason_code,
            "message": message,
            "backend": backend,
        }
    }


def _domain_status(code: str, default: int = 400) -> int:
    """The HTTP status of a domain reason code (the frozen
    developerapi canonical-reason table reused BY REFERENCE for
    contract-surface reasons; a small suffix rule for the other
    accepted domains' frozen codes)."""
    if code in CANONICAL_REASON_HTTP_STATUS:
        return CANONICAL_REASON_HTTP_STATUS[code]
    if "unknown" in code:
        return 404
    if "conflict" in code:
        return 409
    if "terminal" in code or "expired" in code:
        return 409
    return default


def _translate_domain_error(error: BaseException) -> Tuple[int, Dict[str, Any]]:
    """Translate one ACCEPTED domain's typed error into the HTTP
    envelope (reason preserved verbatim; deterministic detail)."""
    if isinstance(error, DeveloperApiError):
        reason = error.canonical_reason or error.reason
        return (
            error.http_status,
            _error_document(reason, error.detail),
        )
    if isinstance(error, PostgresBackendError):
        status = 503 if error.reason_code == "backend-unavailable" else 500
        return (
            status,
            _error_document(error.reason_code, str(error), backend=error.backend),
        )
    if isinstance(error, ContractError):
        return (_domain_status(error.code), _error_document(error.code, error.detail))
    if isinstance(error, AgentError):
        return (_domain_status(error.reason), _error_document(error.reason, error.detail))
    if isinstance(error, (ExecutionPlanError, EvidenceError)):
        return (_domain_status(error.code), _error_document(error.code, error.detail))
    if isinstance(error, AdapterError):
        return (
            _domain_status(error.reason),
            _error_document(error.reason, error.detail),
        )
    # the boundary's own typed errors
    if isinstance(error, RuntimeBoundaryError):
        return (
            error.status,
            _error_document(error.reason_code, error.message, backend=error.backend),
        )
    if isinstance(error, (ValueError, TypeError)):
        return (400, _error_document("invalid-input", str(error)))
    # NEVER leak internals: unexpected failures collapse to a bare
    # internal-error envelope with no detail.
    return (500, _error_document("internal-error", "unexpected runtime failure"))


async def _read_body(
    receive: Callable[[], Any], content_length: Optional[int]
) -> bytes:
    """Read the request body with the size cap (fail closed 413)."""
    if content_length is not None and content_length > MAX_BODY_BYTES:
        raise RuntimeBoundaryError(
            "payload-too-large",
            "request body exceeds the %d-byte cap" % MAX_BODY_BYTES,
            status=413,
        )
    chunks = []
    total = 0
    while True:
        message = await receive()
        if message.get("type") != "http.request":
            break
        chunk = message.get("body", b"") or b""
        total += len(chunk)
        if total > MAX_BODY_BYTES:
            raise RuntimeBoundaryError(
                "payload-too-large",
                "request body exceeds the %d-byte cap" % MAX_BODY_BYTES,
                status=413,
            )
        chunks.append(chunk)
        if not message.get("more_body", False):
            break
    return b"".join(chunks)


def _headers(scope: Mapping[str, Any]) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    for name, value in scope.get("headers") or ():
        if isinstance(name, bytes) and isinstance(value, bytes):
            headers[name.decode("latin-1").lower()] = value.decode("latin-1")
    return headers


def _json_body(raw: bytes) -> Dict[str, Any]:
    """Parse the optional JSON request body into a mapping (empty body
    = no members; malformed JSON / non-mapping bodies fail closed)."""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as error:
        raise RuntimeBoundaryError(
            "malformed-json",
            "request body is not valid JSON: %s" % error,
            status=400,
        ) from None
    if not isinstance(parsed, dict):
        raise RuntimeBoundaryError(
            "invalid-request-body",
            "request body must be a JSON object",
            status=400,
        )
    return parsed


def _contract_read(
    services: RuntimeServices,
    contract_id: str,
    headers: Mapping[str, str],
) -> Tuple[int, Mapping[str, Any]]:
    """The canonical contract read (gateway boundary when the
    developer credential headers are present; the platform-side store
    public read otherwise)."""
    application_id = headers.get(APPLICATION_HEADER.lower(), "")
    credential = headers.get(CREDENTIAL_HEADER.lower(), "")
    if application_id and credential:
        request = ApiRequest(
            method="GET",
            route="/api/2.0/contracts/%s" % contract_id,
            body={},
            api_version=headers.get(API_VERSION_HEADER.lower(), "2.0"),
            application_id=application_id,
            secret=credential,
        )
        response = services.gateway.handle(request)
        return response.status, dict(response.body)
    contract = services.contracts.contract(contract_id)
    return 200, contract.to_dict()


def _demo_document(
    services: RuntimeServices, instant: Optional[str]
) -> Tuple[int, Dict[str, Any]]:
    document = run_contract_fulfillment_demo(services, instant)
    return 200, document


# ---------------------------------------------------------------------------
# The ASGI application
# ---------------------------------------------------------------------------


def build_app(services: RuntimeServices) -> Callable[..., Any]:
    """Build the ASGI application over one injected-services carrier.

    The returned callable is the ASGI ``app(scope, receive, send)``.
    """

    async def _app(scope: Mapping[str, Any], receive: Callable[[], Any], send: Callable[..., Any]) -> None:
        if scope.get("type") == "lifespan":
            await _handle_lifespan(receive, send)
            return
        if scope.get("type") != "http":
            return
        method = scope.get("method", "GET")
        path = scope.get("path", "/")
        headers = _headers(scope)
        content_length: Optional[int] = None
        raw_content_length = headers.get("content-length")
        if raw_content_length is not None:
            try:
                content_length = int(raw_content_length)
            except ValueError:
                content_length = None
        try:
            status, body = await _dispatch(
                services, method, path, headers, receive, content_length
            )
        except Exception as error:  # noqa: BLE001 - the typed envelope only
            status, body = _translate_domain_error(error)
        try:
            payload = canonical_json_bytes(body)
        except (CanonicalizationError, TypeError, ValueError):
            status = 500
            payload = canonical_json_bytes(
                _error_document("internal-error", "response serialization failed")
            )
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(payload)).encode("latin-1")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": payload})

    return _app


async def _dispatch(
    services: RuntimeServices,
    method: str,
    path: str,
    headers: Mapping[str, str],
    receive: Callable[[], Any],
    content_length: Optional[int],
) -> Tuple[int, Any]:
    """Route one HTTP request to its handler (thin translation)."""
    if method == "GET" and path == "/healthz":
        return 200, liveness_body()

    if method == "GET" and path == "/readyz":
        return readiness(services)

    if path == "/demo/contract-fulfillment":
        if method == "POST":
            raw = await _read_body(receive, content_length)
            body = _json_body(raw)
            instant = body.get("instant")
            if instant is not None and not isinstance(instant, str):
                raise RuntimeBoundaryError(
                    "invalid-input",
                    "the demo instant must be an RFC 3339 UTC string",
                    status=400,
                )
            return _demo_document(services, instant)
        if method == "GET":
            return _demo_document(services, DEFAULT_DEMO_INSTANT)
        raise RuntimeBoundaryError(
            "not-found", "no route matches %s %s" % (method, path), status=404
        )

    if method == "GET" and path.startswith("/api/contracts/"):
        contract_id = path[len("/api/contracts/"):]
        if not contract_id or "/" in contract_id:
            raise RuntimeBoundaryError(
                "not-found", "no route matches %s" % path, status=404
            )
        return _contract_read(services, contract_id, headers)

    raise RuntimeBoundaryError(
        "not-found", "no route matches %s %s" % (method, path), status=404
    )


async def _handle_lifespan(receive: Callable[..., Any], send: Callable[..., Any]) -> None:
    """The ASGI lifespan protocol (startup/shutdown acknowledgements)."""
    while True:
        message = await receive()
        message_type = message.get("type")
        if message_type == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
        elif message_type == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            return


# ---------------------------------------------------------------------------
# The deployment entrypoint (lazy env-wired singleton)
# ---------------------------------------------------------------------------

_default_app: Optional[Callable[..., Any]] = None


async def app(scope: Mapping[str, Any], receive: Callable[[], Any], send: Callable[..., Any]) -> None:
    """The module-level ASGI application.

    Lazily assembles the env-wired runtime on the first request
    (:func:`runtime.wiring.build_app_from_env`) and caches it —
    importing :mod:`runtime.asgi` stays side-effect-free (the
    Vercel entrypoint ``from runtime.asgi import app`` composes the
    production/sandbox mode from the environment at request time).

    A FAILED assembly (a dead durable backend in production mode)
    answers with the SAME typed error envelope as every other
    failure — the error is explicit and names the backend; no stack
    trace ever escapes the callable. The failed assembly is not
    cached, so a recovered backend is picked up on the next request.
    """
    global _default_app
    if _default_app is None:
        try:
            from .wiring import build_app_from_env

            _default_app = build_app_from_env()
        except Exception as error:  # noqa: BLE001 - the typed envelope only
            if scope.get("type") == "lifespan":
                # the lifespan protocol has no error envelope; the
                # failure stays explicit (the server logs it)
                raise
            status, body = _translate_domain_error(error)
            try:
                payload = canonical_json_bytes(body)
            except (CanonicalizationError, TypeError, ValueError):
                status = 500
                payload = canonical_json_bytes(
                    _error_document("internal-error", "response serialization failed")
                )
            await send(
                {
                    "type": "http.response.start",
                    "status": status,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(payload)).encode("latin-1")),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": payload})
            return
    await _default_app(scope, receive, send)
