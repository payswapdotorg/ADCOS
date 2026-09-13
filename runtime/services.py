"""The injected-services carrier of the ADCOS deployment runtime.

:class:`RuntimeServices` is the ONE composition root the ASGI boundary
hands to every handler. It carries ONLY references to already-composed
ACCEPTED authorities plus the deployment-mode flags — the module
contains NO domain logic and NO HTTP semantics:

- ``environment`` / ``mode`` — the environment name bound at the
  developer API gateway (sandbox|production) and the deployment mode
  (``"sandbox"`` = in-memory authorities, ``"production"`` =
  Neon-backed durable authorities);
- ``contracts`` — the canonical :class:`~contracts.store.ContractStore`
  (LOCK-101/LOCK-117: the ONLY contract-state authority; the journal
  fold is the state, construction is recovery);
- ``api_store`` — the developer-API persistence seam
  (:class:`~developerapi.journal.ApiStore`: the idempotency ledger +
  webhook record journal);
- ``evidence`` — the append-only typed
  :class:`~evidence.store.EvidenceStore`;
- ``gateway`` — the accepted request boundary
  (:class:`~developerapi.gateway.DeveloperApiService`; the seam the
  runtime-inventory calls the developerapi gateway);
- ``rate_limiter`` — the ephemeral coordination seam
  (:class:`~developerapi.ratelimit.RateLimiter` or a worker-2 Upstash
  adapter with the same ``check(application_id)`` surface; ``None``
  disables admission throttling);
- ``clock`` — the injected :class:`~agent.clock.AgentClock` (the ONLY
  time source the boundary ever reads; never a wall clock);
- ``sandbox_execution`` — whether the execution leg of the
  contract-fulfillment demonstration runs the deterministic sandbox
  provider composition (the DEC-0126 first-deployment posture: the
  deployed surface is software-only);
- ``execution_factory`` — a zero-argument deterministic builder that
  mounts one fresh sandbox execution provider composition per
  demonstration run (the adapter activation ledger is LOCK-117
  execution bookkeeping — data, never authority — so a fresh
  composition per run is the honest deterministic shape);
- ``backends`` — the configured infrastructure adapters this runtime
  surface CONSUMES, by name (``"postgres"``, ``"upstash"``, ...),
  each exposing a ``health() -> Mapping`` probe for the readiness
  surface;
- ``delegated_backends`` — infrastructure configured in the
  environment but consumed by ANOTHER worker's integration (the R2
  evidence/artifact adapter): reported in readiness as delegated,
  never counted against this surface's readiness;
- ``demo_application_id`` / ``demo_credential`` — the platform-held
  application credential the demonstration drives the gateway request
  boundary with (out-of-band issuance; the secret NEVER enters a
  journal line, a response body, or a log — the journals carry only
  its digest).

Everything else the demonstration needs is derived BY REFERENCE from
these carriers inside :mod:`runtime.demo`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional

from agent.clock import AgentClock

from contracts import ContractStore

from developerapi.gateway import DeveloperApiService
from developerapi.journal import ApiStore
from developerapi.ratelimit import RateLimiter

from evidence import EvidenceStore

__all__ = [
    "RuntimeServices",
    "SANDBOX_MODE",
    "PRODUCTION_MODE",
]

#: The deployment modes (readiness carries the mode; sandbox never
#: claims production).
SANDBOX_MODE = "sandbox"
PRODUCTION_MODE = "production"


@dataclass
class RuntimeServices:
    """The injected-services carrier (see the module docstring)."""

    environment: str
    mode: str
    contracts: ContractStore
    api_store: ApiStore
    evidence: EvidenceStore
    gateway: DeveloperApiService
    clock: AgentClock
    rate_limiter: Optional[RateLimiter]
    sandbox_execution: bool
    execution_factory: Optional[Callable[[], Any]] = None
    issuance_key: bytes = b""
    backends: Mapping[str, Any] = field(default_factory=dict)
    delegated_backends: Mapping[str, str] = field(default_factory=dict)
    demo_application_id: str = ""
    demo_credential: str = ""

    def __post_init__(self) -> None:
        if self.mode not in (SANDBOX_MODE, PRODUCTION_MODE):
            raise ValueError(
                "runtime mode %r must be %r or %r"
                % (self.mode, SANDBOX_MODE, PRODUCTION_MODE)
            )
        if not isinstance(self.contracts, ContractStore):
            raise ValueError("contracts must be a contracts.ContractStore")
        if not isinstance(self.gateway, DeveloperApiService):
            raise ValueError(
                "gateway must be a developerapi.gateway.DeveloperApiService"
            )
        if not isinstance(self.api_store, ApiStore):
            raise ValueError("api_store must be a developerapi.journal.ApiStore")
        if not isinstance(self.evidence, EvidenceStore):
            raise ValueError("evidence must be an evidence.EvidenceStore")
        if not isinstance(self.clock, AgentClock):
            raise ValueError("clock must be an agent.clock.AgentClock")
        if self.execution_factory is not None and not callable(self.execution_factory):
            raise ValueError("execution_factory must be callable or None")
