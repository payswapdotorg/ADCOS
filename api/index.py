"""ADCOS Vercel entry — the thinnest possible serverless function.

D2 ROLLBACK-PROOF MARKER (runbook §8, 2026-09-13T18:05Z): this build exists
solely as the deliberately-distinguishable, docstring-only D2 of the staged
rollback proof — identical code semantics to D1 (the accepted 73856f1
build), this paragraph is the only difference. Expect the production alias
to return to D1 within minutes.

ASGI export convention
======================

Vercel's zero-config Python runtime serves files under ``api/`` as serverless
functions and looks for a top-level callable named ``app`` in the entrypoint
file — the same detection that serves FastAPI/Starlette (ASGI) and Flask
(WSGI) applications. This module exports exactly one such callable, produced
by the runtime wiring layer:

    app = build_app_from_env()

``runtime.wiring.build_app_from_env`` (worker 1's T2 delivery) returns a
pure-stdlib ASGI application that reads the ``ADCOS_*`` environment contract
documented in ``docs/deployment/runtime-inventory.md`` and
``docs/deployment/runbook.md``. ``runtime.wiring.build_sandbox_app`` is the
deterministic demo mode used where no backends are configured.

The import below is deliberately REAL and at module top level: Vercel's
build-time import tracing walks it so the stdlib-only domain graph
(``runtime/``, ``backends/``, ``contracts/``, ``developerapi/``, ``agent/``,
``protocol/``, ``evidence/``, ``executionplans/``, ``adapters/``,
``offers/``, ``capabilities/``, ``policy/``, ``eligibility/``,
``assurance/``, ``replan/``, ``resilience/``) is bundled with the function.
Nothing else may live in this file — HTTP semantics belong to the runtime
boundary (T2), never to the deployment entry.
"""
from runtime.wiring import build_app_from_env

app = build_app_from_env()
