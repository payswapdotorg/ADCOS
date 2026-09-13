"""ADCOS deployment runtime package (DEC-0126 bounded scope).

The thin HTTP/runtime boundary + the injected-services carrier around
the ACCEPTED ADCOS 1.1 domains (consumed BY REFERENCE — never forked,
never rewritten, never weakened):

- :mod:`runtime.services` — the :class:`RuntimeServices` carrier (the
  one composition root handed to every handler; NO domain logic);
- :mod:`runtime.asgi` — the pure-stdlib ASGI application (thin HTTP
  translation only; every typed error is a canonical-JSON envelope);
- :mod:`runtime.sandbox` — the deterministic sandbox services builder
  (in-memory authorities + the deterministic sandbox execution
  providers; DEMO-ONLY issuance material, documented);
- :mod:`runtime.health` — the liveness/readiness handlers (per-backend
  state; 503 with detail when a configured backend is not ready);
- :mod:`runtime.demo` — the deterministic contract-fulfillment
  demonstration (intent -> offer -> activation -> plan -> sandbox
  execution -> SOFTWARE-class evidence; byte-identical for identical
  inputs);
- :mod:`runtime.wiring` — the env-based assembly
  (:func:`build_app_from_env` — Neon-backed production mode when
  ``ADCOS_DATABASE_URL`` is present, deterministic sandbox mode
  otherwise; a database failure NEVER silently becomes in-memory
  canonical state).

The runtime owns NO domain semantics: every command flows through the
accepted authorities (the ``contracts`` store fold, the ``developerapi``
request boundary, the ``executionplans`` bridge, the ``adapters``
capability seam, the ``evidence`` store). Provider infrastructure lives
behind the :mod:`backends` adapters.
"""

from __future__ import annotations

__all__ = [
    "asgi",
    "demo",
    "health",
    "sandbox",
    "services",
    "wiring",
]
