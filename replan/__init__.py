"""ADCOS replan package (M008 — Replan and Failover).

The closed-loop replan domain of Architecture 1.1 §9: when an active
contract's realization becomes unsatisfiable (adapter failure,
segment loss, assurance degradation/violation, route expiry, or the
constraint set becoming unsatisfiable with the available
alternatives), the replan engine computes an ALTERNATIVE realization
that still satisfies the SAME contract.

Public surface:

- the frozen vocabularies (:data:`TRIGGER_KINDS`,
  :data:`REALIZATION_STATES`, :data:`REALIZATION_TRANSITIONS`,
  :data:`REALIZATION_TERMINAL_STATES`, :data:`REALIZATION_SURFACES`,
  :data:`CANDIDATE_KINDS`, :data:`DECISION_KINDS`,
  :data:`SOFT_TRIGGER_KINDS`, :data:`RENEGOTIATION_TRIGGER_KINDS`,
  :data:`TIE_BREAK_KEYS`, :data:`DEFAULT_TIE_BREAK`,
  :data:`REPLANNABLE_CONTRACT_STATES`);
- the typed records: :class:`ReplanTrigger` (what failed),
  :class:`RealizationSnapshot` (the execution-state view being
  replanned), :class:`ReplanCandidate` (one alternative, as DATA),
  :class:`CandidateVerdict` (the typed per-candidate LOCK-108
  verdict), :class:`ReplanDecision` (the closed-loop decision
  record), :class:`RenegotiationNotice` (the explicit renegotiation
  trigger), :class:`ReconnectRecord` (the harvested WORK-012
  reconnect discipline, as typed evidence);
- the pure kernels :func:`check_realization_transition` /
  :func:`apply_realization_transition` (the M008-owned explicit
  realization-state machine);
- the LOCK-108 gates: :func:`validate_constraints_preserved` (the
  raising per-candidate gate), :func:`candidate_verdict` (the typed
  verdict twin), :func:`verify_decision_preserves_contract` (the
  pure cross-authority gate over a finished decision);
- the deterministic engine :func:`decide_replan` (trigger ->
  candidates -> constraint re-validation -> decision; LOCK-111: a
  deterministic strategy with injected tie-breaking, never an
  authority);
- the disclosed harvest seam (:mod:`replan.execution_state`):
  :func:`session_realization_snapshot` (the WORK-012 session
  lifecycle discipline as the execution-state surface replan
  operates over), :func:`reconnect_history` (the explicit-reconnect
  discipline — old AND new route references, never a silent
  replacement — enforced fail-closed), :func:`handover_surface` /
  :func:`multipath_surface` (the WORK-014/WORK-013 alternative
  models the engine selects among, by reference);
- the alternative constructors (:mod:`replan.alternatives`):
  :func:`plan_candidate` (a new M006 plan from the SAME contract),
  :func:`route_candidate` (a mobility-handover / multipath-path
  alternative), :func:`capability_candidate` (an available M007
  offer-view alternative);
- the contract bridge (:mod:`replan.bridge`):
  :func:`bridge_commands` (the explicit, sole recording path back
  into the accepted contracts/ domain via its own command
  vocabulary) and :func:`renegotiation_reference` (the successor
  contract's ``superseded-contract`` reference — the explicit
  renegotiation trigger path).

Authority boundaries (the layering contract, frozen 1.1):

- **LOCK-101/LOCK-117**: contracts/ stays the sole authority; the
  decision, the candidates, the plans, the paths and the offer views
  are DATA (opaque references); effects enter the contract only
  through its own frozen command vocabulary.
- **LOCK-108 (the core discipline)**: replanning MUST NOT silently
  weaken hard contract constraints.  Every candidate is validated
  against the contract's full hard-constraint set; a weakening
  candidate is REJECTED with the typed reason citing the kinds; an
  impossible realization enters an EXPLICIT degraded/failed state or
  triggers EXPLICIT renegotiation — never a silent downgrade.
- **LOCK-111**: the engine is a deterministic strategy, not an
  authority; tie-breaking rules are injected (content keys only,
  never wall-clock); same inputs -> same decision, same reasons.
- **LOCK-119**: no wall clock, no randomness, no network, no
  secrets; content-derived ids over canonical JSON; canonical-JSON
  round-trips with tamper-evident ids.

Harvest disclosure (R7 charter M008 scope: ``mobility/``,
``multipath/``, ``sessions/`` (harvest)): the WORK-era execution
packages are harvested onto the 1.1 authority THROUGH this package —
their public APIs are consumed by reference (one-way; the packages
are preserved verbatim for their existing consumers — the
minimal-consistent-refactor discipline, the M006 composition-harvest
precedent).  The WORK-012 explicit-reconnect authority rules are
PRESERVED and mechanically enforced (``replan-silent-replacement``).
"""

from __future__ import annotations

from .errors import ReplanError, ReplanReason
from .model import (
    CANDIDATE_KINDS,
    DECISION_KINDS,
    DEFAULT_TIE_BREAK,
    REALIZATION_STATES,
    REALIZATION_SURFACES,
    REALIZATION_TERMINAL_STATES,
    REALIZATION_TRANSITIONS,
    RENEGOTIATION_TRIGGER_KINDS,
    SOFT_TRIGGER_KINDS,
    TIE_BREAK_KEYS,
    TRIGGER_KINDS,
    CandidateVerdict,
    RealizationSnapshot,
    RenegotiationNotice,
    ReconnectRecord,
    ReplanCandidate,
    ReplanDecision,
    ReplanTrigger,
    VERDICT_ACCEPTED,
    apply_realization_transition,
    check_realization_transition,
)
from .validation import (
    candidate_verdict,
    validate_constraints_preserved,
    verify_decision_preserves_contract,
)
from .engine import REPLANNABLE_CONTRACT_STATES, decide_replan
from .execution_state import (
    HARVEST_VIEW_ISSUER,
    SESSION_STATE_MAP,
    handover_surface,
    multipath_surface,
    reconnect_history,
    session_realization_snapshot,
)
from .alternatives import (
    capability_candidate,
    plan_candidate,
    route_candidate,
)
from .bridge import (
    DEFAULT_BRIDGE_ISSUER,
    bridge_commands,
    renegotiation_reference,
)

__all__ = [
    # typed errors
    "ReplanError",
    "ReplanReason",
    # frozen vocabularies
    "TRIGGER_KINDS",
    "REALIZATION_STATES",
    "REALIZATION_TRANSITIONS",
    "REALIZATION_TERMINAL_STATES",
    "REALIZATION_SURFACES",
    "CANDIDATE_KINDS",
    "DECISION_KINDS",
    "SOFT_TRIGGER_KINDS",
    "RENEGOTIATION_TRIGGER_KINDS",
    "TIE_BREAK_KEYS",
    "DEFAULT_TIE_BREAK",
    "REPLANNABLE_CONTRACT_STATES",
    # typed records
    "ReplanTrigger",
    "RealizationSnapshot",
    "ReplanCandidate",
    "CandidateVerdict",
    "ReplanDecision",
    "RenegotiationNotice",
    "ReconnectRecord",
    "VERDICT_ACCEPTED",
    # pure kernels
    "check_realization_transition",
    "apply_realization_transition",
    # LOCK-108 gates
    "validate_constraints_preserved",
    "candidate_verdict",
    "verify_decision_preserves_contract",
    # the deterministic engine
    "decide_replan",
    # the disclosed harvest seam
    "SESSION_STATE_MAP",
    "HARVEST_VIEW_ISSUER",
    "session_realization_snapshot",
    "reconnect_history",
    "handover_surface",
    "multipath_surface",
    # alternative constructors
    "plan_candidate",
    "route_candidate",
    "capability_candidate",
    # the contract bridge
    "DEFAULT_BRIDGE_ISSUER",
    "bridge_commands",
    "renegotiation_reference",
]
