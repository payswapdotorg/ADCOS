"""ADCOS resilience package (M015 — Execution Resilience Runtime).

The execution-runtime resilience domain of the R8 charter (R8-CORE-001,
DEC-0114; the FIRST R8 child, composing the accepted R7 authorities
BY REFERENCE — import and compose, never reimplement, weaken, fork,
or bypass):

- **The session-runtime lifecycle** (:mod:`resilience.model`,
  :mod:`resilience.journal`, :mod:`resilience.runtime`): deterministic
  lifecycle states, typed transition records, content-derived ids,
  canonical-JSON round-trips, fail-closed transitions; every
  route/realization change is an EXPLICIT recorded reconnect event
  naming BOTH the old AND the new references (the WORK-012
  explicit-reconnect discipline re-expressed on the 1.1 authority and
  functionally enforced — never a silent replacement); the runtime
  journal is deterministic and replayable (construction-is-recovery);
  degraded-mode entry/exit is explicit, journaled and evidence-visible
  (the accepted ``evidence/`` LOCK-106 typing consumed for the
  evidence kinds).
- **The mobility handover engine** (:mod:`resilience.handover`):
  handover with hard-constraint preservation (LOCK-108 — every
  candidate validated against the contract's full hard-constraint set
  through the ACCEPTED M008 gates, consumed BY REFERENCE; a weakening
  candidate is REJECTED with the typed reason; an impossible handover
  enters the EXPLICIT degraded/failed state or triggers the EXPLICIT
  renegotiation path — never a silent downgrade).
- **The multipath failover orchestrator** (:mod:`resilience.failover`):
  failover orchestration with deterministic declared recorded
  tie-breaking (LOCK-111) over the accepted ``executionplans/``
  alternative segments and the accepted M008 replan kernel — the
  runtime DRIVES the kernel rather than duplicating it.
- **The replan-kernel composition core**
  (:func:`resilience.runtime.drive_replan_decision`): the sole path
  from a consumed M008 decision onto the runtime journal — the
  realization-state vocabulary (REALIZING/DEGRADED/FAILED/SUPERSEDED)
  stays M008-owned and is projected onto, NEVER redefined and never
  extended (no extension was needed).

Authority boundaries (the layering contract, frozen 1.1):

- **LOCK-101/LOCK-117**: contracts/ stays the sole authority; the
  runtime session rides the contract as an opaque reference, carries
  NO constraint material, and never becomes a second contract
  authority.  Imports flow one way: ``resilience/`` imports the
  accepted authorities (contracts, executionplans, replan, evidence);
  NO accepted authority imports ``resilience/``.
- **LOCK-108 (the core discipline)**: every resilience transition
  (handover, failover, reconnect) preserves the contract's
  hard-constraint set VERBATIM — enforced structurally (no constraint
  material on the runtime surface) and through the consumed M008 gates
  (typed weakened-constraint rejection citing the kinds).
- **LOCK-111**: failover selection is deterministic with DECLARED
  injected recorded tie-breaking (content keys only, never wall-clock,
  never random); same inputs -> the byte-identical decision record.
- **LOCK-119**: no wall clock, no randomness, no network, no secrets;
  content-derived ids over canonical JSON; canonical-JSON round-trips
  with tamper-evident ids.

Harvest disclosure (R8 charter M015 scope): the legacy 1.0 reservoir
(``sessions/``, ``mobility/``, ``multipath/``, ``edge/``,
``appliance/``) is SOURCE MATERIAL ONLY — the WORK-012 reconnect
discipline, the WORK-035/WORK-014 handover semantics and the WORK-013
multipath failover models are studied and RE-EXPRESSED on the 1.1
authority inside this package; the legacy packages are NOT imported,
NOT modified (their M008 docstring disclosures stay byte-identical),
and remain their own authorities for their existing consumers.
"""

from __future__ import annotations

from .errors import ResilienceError, ResilienceReason
from .model import (
    ROUTE_MEMBER_NAMES,
    RUNTIME_EVENT_KINDS,
    RUNTIME_ISSUER,
    RUNTIME_REALIZATION_MAP,
    RUNTIME_RECONNECTABLE_STATES,
    RUNTIME_STATES,
    RUNTIME_TERMINAL_STATES,
    RUNTIME_TRANSITIONS,
    RuntimeEvent,
    RuntimeReconnect,
    RuntimeSession,
    check_realization_surface,
    check_runtime_transition,
    derive_runtime_id,
    runtime_realization_snapshot,
)
from .journal import (
    EVENT_TARGET_STATES,
    fold_events,
    reconnect_evidence,
)
from .runtime import (
    DRIVE_OUTCOME_KINDS,
    RUNTIME_DRIVEN_ISSUER,
    DriveResult,
    RuntimeStore,
    drive_replan_decision,
)
from .handover import (
    HANDOVER_CANDIDATE_KIND,
    handover_candidate,
    handover_verdict,
    perform_handover,
    validate_handover_preserves_contract,
)
from .failover import (
    FAILOVER_CANDIDATE_KIND,
    FAILOVER_TRIGGER_KINDS,
    FAILOVER_TRIGGER_MAP,
    failover_alternatives,
    orchestrate_failover,
)

__all__ = [
    # typed errors
    "ResilienceError",
    "ResilienceReason",
    # frozen vocabularies
    "RUNTIME_STATES",
    "RUNTIME_TERMINAL_STATES",
    "RUNTIME_TRANSITIONS",
    "RUNTIME_RECONNECTABLE_STATES",
    "RUNTIME_REALIZATION_MAP",
    "RUNTIME_EVENT_KINDS",
    "ROUTE_MEMBER_NAMES",
    "EVENT_TARGET_STATES",
    "DRIVE_OUTCOME_KINDS",
    "HANDOVER_CANDIDATE_KIND",
    "FAILOVER_CANDIDATE_KIND",
    "FAILOVER_TRIGGER_KINDS",
    "FAILOVER_TRIGGER_MAP",
    # typed records
    "RuntimeSession",
    "RuntimeEvent",
    "RuntimeReconnect",
    "DriveResult",
    # the pure kernels
    "check_runtime_transition",
    "check_realization_surface",
    "derive_runtime_id",
    "runtime_realization_snapshot",
    "fold_events",
    "reconnect_evidence",
    # the runtime store (the journal fold is the sole state writer)
    "RuntimeStore",
    "RUNTIME_ISSUER",
    "RUNTIME_DRIVEN_ISSUER",
    # the replan-kernel composition core
    "drive_replan_decision",
    # the mobility handover engine (LOCK-108)
    "handover_candidate",
    "handover_verdict",
    "validate_handover_preserves_contract",
    "perform_handover",
    # the multipath failover orchestrator (LOCK-111)
    "failover_alternatives",
    "orchestrate_failover",
]
