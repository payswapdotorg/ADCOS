"""The health/readiness handlers of the ADCOS runtime.

Liveness (:func:`liveness_body`) is unconditional — the process is
alive; it says NOTHING about backends.

Readiness (:func:`readiness`) reports the deployment mode and the
state of every backend the runtime surface CONSUMES
(``services.backends``): each adapter's own ``health()`` probe is
driven, and the response is 200 only when no backend reports
``"unavailable"``. A backend failure is EXPLICIT and OBSERVABLE
(per-backend state + detail; HTTP 503 with the full per-backend
detail) — never a silent fallback and never a lie about readiness.

Backends configured in the environment but consumed by ANOTHER
worker's integration (the R2 evidence/artifact adapter, worker 2's
scope) are reported under ``delegated_backends`` as a note: they are
NOT probed here and do NOT count against this surface's readiness
(the worker-2/worker-3 integration wires their own probes).

Sandbox mode has NO configured backend (the authorities are the
deterministic in-process defaults), so readiness is trivially green
with ``"mode": "sandbox"`` — a sandbox runtime NEVER claims to be
production.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from .services import RuntimeServices

__all__ = [
    "LIVENESS_BODY",
    "SERVICE_NAME",
    "liveness_body",
    "readiness",
]

#: The service identity carried by every health response.
SERVICE_NAME = "adcos-runtime"

#: The liveness body (always 200; a constant document).
LIVENESS_BODY: Dict[str, Any] = {
    "ok": True,
    "service": SERVICE_NAME,
}


def liveness_body() -> Dict[str, Any]:
    """The liveness document (constant; no backend knowledge)."""
    return dict(LIVENESS_BODY)


def _backend_state(backend: Any) -> Dict[str, Any]:
    """One backend's probe result (the adapter's own ``health()``
    mapping; a missing probe surface is reported as ``"wired"``, a
    raising probe as ``"unavailable"`` with its detail)."""
    probe = getattr(backend, "health", None)
    if probe is None:
        return {"state": "wired", "detail": "configured; no probe surface"}
    try:
        result = probe()
    except Exception as error:  # noqa: BLE001 - explicit, never silent
        return {
            "state": "unavailable",
            "detail": "backend probe failed: %s" % error,
        }
    if isinstance(result, dict):
        state = result.get("state", "wired")
        return {
            "state": state,
            "detail": result.get("detail", ""),
        }
    return {"state": "wired", "detail": str(result)}


def readiness(services: RuntimeServices) -> Tuple[int, Dict[str, Any]]:
    """The readiness document: ``(http_status, body)``.

    200 when no consumed backend reports ``"unavailable"``; 503 with
    the per-backend detail otherwise. The body always carries the
    deployment mode and the environment name.
    """
    backends = {
        name: _backend_state(services.backends[name])
        for name in sorted(services.backends)
    }
    ready = all(
        state.get("state") != "unavailable" for state in backends.values()
    )
    body: Dict[str, Any] = {
        "ok": ready,
        "service": SERVICE_NAME,
        "mode": services.mode,
        "environment": services.environment,
        "backends": backends,
    }
    if services.delegated_backends:
        body["delegated_backends"] = {
            name: {
                "state": "delegated",
                "detail": services.delegated_backends[name],
            }
            for name in sorted(services.delegated_backends)
        }
    return (200 if ready else 503), body
