"""ADCOS resilience mobility handover engine (M015 — Execution
Resilience Runtime).

The mobility handover with hard-constraint preservation (the R8
charter M015 scope; the WORK-035/WORK-014 handover semantics harvested
as SOURCE MATERIAL and re-expressed on the Architecture 1.1 authority
— the legacy ``mobility/`` package is not imported and not modified):

A handover moves the runtime session to a NEW realization (adapter/
segment/path) while the contract's hard-constraint set is preserved
VERBATIM (LOCK-108).  The engine:

1. **Validates every handover candidate against the contract's full
   hard-constraint set** — through the ACCEPTED M008 gates, consumed
   BY REFERENCE (never duplicated): :func:`handover_verdict` wraps the
   consumed ``replan.candidate_verdict`` (the typed verdict twin), and
   :func:`validate_handover_preserves_contract` wraps the consumed
   raising gate ``replan.validate_constraints_preserved`` (the typed
   rejection surfaces on this surface's own vocabulary with the
   deterministic text preserved — a candidate that weakens/drops ANY
   hard constraint is REJECTED with ``resilience-constraint-weakened``
   citing the specific kinds);
2. **Drives the accepted replan kernel** (:func:`perform_handover` ->
   ``replan.decide_replan``): the handover candidates are M008
   ``ReplanCandidate`` records (the harvested mobility-handover
   alternative kind); the kernel validates every candidate (LOCK-108),
   orders them by the DECLARED injected tie-break (LOCK-111), and
   produces the typed decision;
3. **Applies the decision through the runtime journal**
   (:func:`resilience.runtime.drive_replan_decision`): an adopted
   handover lands through the EXPLICIT reconnect pair (old AND new
   references recorded — the WORK-012 discipline); an impossible
   handover enters the EXPLICIT degraded/failed state or triggers the
   EXPLICIT renegotiation path (the typed notice rides the decision;
   the successor contract is created through the accepted M002
   ``superseded-contract`` reference path by the principal-side flow —
   never a silent downgrade).

LOCK-117: the handover candidate, its realization references and the
adopted artifacts ride as opaque ``execution-artifact`` data; the
contract stays the sole authority (the runtime session carries no
constraint material at all — the constraint model is consumed from
``contracts/`` through the replan gates).

Determinism (LOCK-111/LOCK-119): same inputs -> same decision, same
reasons; tie-breaking rules are DECLARED and injected (content keys
only, never wall-clock); injected instants only; no randomness, no
network, no secrets.
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

from contracts import ConnectivityContract, HardConstraint, OpaqueReference, Provenance

from replan import (
    DEFAULT_TIE_BREAK,
    CandidateVerdict,
    ReplanCandidate,
    ReplanDecision,
    ReplanError,
    ReplanTrigger,
    TRIGGER_KINDS,
    candidate_verdict as _consumed_candidate_verdict,
    decide_replan as _consumed_decide_replan,
    validate_constraints_preserved as _consumed_validate_constraints,
)

from resilience.errors import ResilienceError, ResilienceReason
from resilience.model import (
    RUNTIME_ISSUER,
    _normalize_tie_break,
    check_realization_surface,
    runtime_realization_snapshot,
)
from resilience.runtime import DriveResult, RuntimeStore, drive_replan_decision

__all__ = [
    "HANDOVER_CANDIDATE_KIND",
    "handover_candidate",
    "handover_verdict",
    "validate_handover_preserves_contract",
    "perform_handover",
]


#: The harvested alternative kind a handover candidate rides on (the
#: M008-owned frozen candidate-kind vocabulary, consumed BY REFERENCE —
#: the WORK-014 mobility-handover alternative shape).
HANDOVER_CANDIDATE_KIND = "mobility-handover"


def handover_candidate(
    contract: ConnectivityContract,
    *,
    route_decision_id: str,
    path_id: str,
    hard_constraints: Sequence[HardConstraint],
    provenance: Optional[Provenance] = None,
) -> ReplanCandidate:
    """Construct one mobility-handover candidate (the new realization
    the handover proposes, as DATA — LOCK-111: the proposal can never
    override the authority-true constraint set).

    ``route_decision_id`` / ``path_id`` name the proposed new
    realization (opaque references, LOCK-117 — the WORK-012 member
    shape).  ``hard_constraints`` is the constraint set the alternative
    CLAIMS to satisfy — optimizer-supplied DATA, re-validated against
    the contract's full hard-constraint set by the consumed kernel
    (LOCK-108: a weakening claim is rejected, never silently adopted).
    """
    if not isinstance(contract, ConnectivityContract):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "handover_candidate requires a contracts.ConnectivityContract (got %s)"
            % type(contract).__name__,
        )
    if not isinstance(route_decision_id, str) or not route_decision_id:
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "handover_candidate requires the proposed route_decision_id",
        )
    if not isinstance(path_id, str) or not path_id:
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "handover_candidate requires the proposed path_id",
        )
    if provenance is None:
        provenance = Provenance(
            issuer="resilience:handover",
            decision_refs=(route_decision_id, path_id, contract.contract_id),
        )
    elif not isinstance(provenance, Provenance):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT, "provenance must be a Provenance record"
        )
    issuer = "resilience:handover"
    try:
        return ReplanCandidate(
            kind=HANDOVER_CANDIDATE_KIND,
            contract_id=contract.contract_id,
            hard_constraints=tuple(hard_constraints),
            artifact_refs=(
                OpaqueReference(
                    ref_kind="execution-artifact",
                    value=route_decision_id,
                    provenance=Provenance(
                        issuer=issuer,
                        decision_refs=(path_id, contract.contract_id),
                    ),
                ),
                OpaqueReference(
                    ref_kind="execution-artifact",
                    value=path_id,
                    provenance=Provenance(
                        issuer=issuer,
                        decision_refs=(route_decision_id, contract.contract_id),
                    ),
                ),
            ),
            provenance=provenance,
        )
    except ReplanError as error:
        raise ResilienceError(
            ResilienceReason.REPLAN_COMPOSITION,
            "the handover candidate was rejected by the consumed M008 candidate "
            "model: %s" % error.detail,
        ) from None


def handover_verdict(
    candidate: ReplanCandidate, contract: ConnectivityContract
) -> CandidateVerdict:
    """The LOCK-108 gate for one handover candidate, as a typed verdict
    — the CONSUMED ``replan.candidate_verdict`` (BY REFERENCE, never
    duplicated): a candidate that weakens/drops ANY hard contract
    constraint is REJECTED with the typed ``replan-constraint-weakened``
    reason citing the specific kinds (surfaced verbatim on this
    surface); an accepted candidate carries the accepted code."""
    if not isinstance(candidate, ReplanCandidate):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "handover_verdict requires a replan.ReplanCandidate (got %s)"
            % type(candidate).__name__,
        )
    if not isinstance(contract, ConnectivityContract):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "handover_verdict requires a contracts.ConnectivityContract (got %s)"
            % type(contract).__name__,
        )
    try:
        return _consumed_candidate_verdict(candidate, contract)
    except ReplanError as error:
        raise ResilienceError(
            ResilienceReason.REPLAN_COMPOSITION,
            "the consumed M008 verdict gate rejected the input: %s" % error.detail,
        ) from None


def validate_handover_preserves_contract(
    hard_constraints: Sequence[HardConstraint], contract: ConnectivityContract
) -> None:
    """Fail closed unless the claimed handover constraint set preserves
    the contract's hard constraints VERBATIM (LOCK-108) — the CONSUMED
    raising gate ``replan.validate_constraints_preserved`` (BY
    REFERENCE), with the typed rejection surfaced on this surface's own
    vocabulary: ``resilience-constraint-weakened`` (a dropped, relaxed
    or re-interpreted constraint, citing the kinds) or
    ``resilience-constraint-mismatch`` (a reordered/tampered set)."""
    if not isinstance(contract, ConnectivityContract):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "validate_handover_preserves_contract requires a "
            "contracts.ConnectivityContract (got %s)" % type(contract).__name__,
        )
    try:
        _consumed_validate_constraints(
            tuple(hard_constraints),
            contract.hard_constraints,
            contract.hard_constraint_fingerprint(),
            label="the handover candidate realization",
        )
    except ReplanError as error:
        if error.code == "replan-constraint-weakened":
            raise ResilienceError(
                ResilienceReason.CONSTRAINT_WEAKENED,
                "%s (LOCK-108: no silent contract weakening — the handover "
                "candidate is rejected)" % error.detail,
            ) from None
        if error.code == "replan-constraint-mismatch":
            raise ResilienceError(
                ResilienceReason.CONSTRAINT_MISMATCH,
                "the handover candidate %s" % error.detail,
            ) from None
        raise ResilienceError(
            ResilienceReason.REPLAN_COMPOSITION,
            "the consumed M008 constraint gate rejected the input: %s" % error.detail,
        ) from None


def perform_handover(
    store: RuntimeStore,
    runtime_id: object,
    contract: ConnectivityContract,
    candidates: Sequence[ReplanCandidate],
    *,
    trigger_kind: str,
    recorded_at: str,
    tie_break: Sequence[str] = DEFAULT_TIE_BREAK,
    provenance: Optional[Provenance] = None,
) -> DriveResult:
    """Perform one mobility handover: validate every candidate against
    the contract's full hard-constraint set (LOCK-108, through the
    consumed kernel), select deterministically (LOCK-111, the declared
    injected tie-break), and apply the outcome through the runtime
    journal (the explicit reconnect pair on adoption; the EXPLICIT
    degraded/failed state or renegotiation trigger otherwise — never a
    silent downgrade).

    Fail-closed gates: the store/session/contract inputs (typed,
    attributed); the runtime session must be a replan surface
    (ACTIVE/RECONNECTING/DEGRADED — PENDING fails closed as
    not-established, terminal runtimes never transition); the trigger
    kind must be in the CONSUMED M008 trigger vocabulary; the
    candidates must be non-empty M008 ``ReplanCandidate`` records.
    Every consumed-kernel rejection surfaces as a typed
    ``resilience-replan-composition`` error with its deterministic
    text preserved (exception isolation).
    """
    if not isinstance(store, RuntimeStore):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "perform_handover requires a resilience RuntimeStore (got %s)"
            % type(store).__name__,
        )
    if not isinstance(contract, ConnectivityContract):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "perform_handover requires a contracts.ConnectivityContract (got %s)"
            % type(contract).__name__,
        )
    session = store.session(runtime_id)
    if session.contract_id != contract.contract_id:
        raise ResilienceError(
            ResilienceReason.ID_MISMATCH,
            "runtime session %s rides contract %s, not %s — a handover "
            "realizes exactly its owning contract"
            % (
                session.runtime_id[:23],
                session.contract_id[:23],
                contract.contract_id[:23],
            ),
        )
    check_realization_surface(session.state)
    if trigger_kind not in TRIGGER_KINDS:
        raise ResilienceError(
            ResilienceReason.VOCABULARY,
            "trigger_kind must be one of the consumed M008 trigger kinds %s "
            "(found %r)" % (", ".join(TRIGGER_KINDS), trigger_kind),
        )
    if isinstance(candidates, (str, bytes)) or not isinstance(candidates, (tuple, list)):
        raise ResilienceError(
            ResilienceReason.INVALID_INPUT,
            "perform_handover requires a sequence of ReplanCandidate records",
        )
    if not candidates:
        raise ResilienceError(
            ResilienceReason.NO_CANDIDATES,
            "a handover evaluation requires at least one candidate "
            "realization (fail-closed: there is nothing to select silently — "
            "the caller asserts the available handover alternatives, empty "
            "or not)",
        )
    for i, candidate in enumerate(candidates):
        if not isinstance(candidate, ReplanCandidate):
            raise ResilienceError(
                ResilienceReason.INVALID_INPUT,
                "candidates[%d] must be a replan.ReplanCandidate record (got %s)"
                % (i, type(candidate).__name__),
            )
    normalized_tie_break = _normalize_tie_break(tie_break, "perform_handover.tie_break", complete=True)

    snapshot = runtime_realization_snapshot(
        session, observed_at=recorded_at, provenance=provenance
    )
    try:
        trigger = ReplanTrigger(
            kind=trigger_kind,
            contract_id=contract.contract_id,
            recorded_at=recorded_at,
            realization_ref=session.runtime_id,
        )
        decision = _consumed_decide_replan(
            contract,
            trigger,
            snapshot,
            tuple(candidates),
            tie_break=normalized_tie_break,
        )
    except ReplanError as error:
        raise ResilienceError(
            ResilienceReason.REPLAN_COMPOSITION,
            "the consumed M008 replan kernel rejected the handover drive: %s"
            % error.detail,
        ) from None

    sequence_before = session.sequence
    new_route = None
    new_path = None
    if decision.decision == "adopt-alternative":
        adopted = None
        for candidate in candidates:
            if candidate.candidate_id == decision.adopted_candidate_id:
                adopted = candidate
                break
        if adopted is None:  # pragma: no cover - the kernel guarantees this
            raise ResilienceError(
                ResilienceReason.REPLAN_COMPOSITION,
                "internal: the adopted candidate vanished from the input set",
            )
        new_route = adopted.artifact_refs[0].value
        new_path = adopted.artifact_refs[1].value
    after, reconnect = drive_replan_decision(
        store,
        session.runtime_id,
        contract,
        decision,
        recorded_at=recorded_at,
        new_route_decision_id=new_route,
        new_path_id=new_path,
        provenance=Provenance(
            issuer=RUNTIME_ISSUER,
            decision_refs=(decision.decision_id, session.runtime_id),
        ),
    )
    appended = store.events(session.runtime_id)[sequence_before:]
    return DriveResult(
        decision=decision,
        session=after,
        reconnect=reconnect,
        event_ids=tuple(event.event_id for event in appended),
    )
