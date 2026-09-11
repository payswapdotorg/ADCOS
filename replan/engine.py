"""ADCOS replan engine (M008 — Replan and Failover).

The deterministic replan decision procedure — trigger -> candidates
-> constraint re-validation -> decision:

1. **Trigger gate** (fail-closed): the trigger must be typed, must
   cite THIS contract, must carry an injected instant inside the
   contract validity, and the contract must be in a replannable
   lifecycle state (an ACTIVE realization exists);
2. **Realization gate** (fail-closed): the realization snapshot must
   be attributable to this contract and must not be terminal
   (FAILED/SUPERSEDED realizations never replan);
3. **Candidate evaluation** (LOCK-108, deterministic): every
   candidate is validated against the contract's full hard-constraint
   set — a candidate that weakens/drops ANY hard constraint is
   REJECTED with the typed ``replan-constraint-weakened`` reason
   citing the specific kinds.  Candidates are considered in the
   declared tie-break order (LOCK-111: injected, content-key rules
   only, never wall-clock) and every verdict is recorded;
4. **Decision** (deterministic): the first constraint-preserving
   candidate in the declared order is adopted
   (``adopt-alternative``); with NO acceptable candidate the decision
   is explicit per the trigger class — ``degraded`` for a soft
   (assurance-degraded) trigger (the realization enters the EXPLICIT
   degraded state — the closed loop keeps observing), ``renegotiate``
   for the impossible-realization class (constraint-unsatisfiable),
   and ``failed`` for every other hard trigger — the failed and
   renegotiate decisions carry the typed EXPLICIT renegotiation
   notice (frozen §9: never a silent downgrade).

Determinism discipline (LOCK-111): the engine is a DETERMINISTIC
STRATEGY, not an authority — the same (contract, trigger, snapshot,
candidates, tie-break, provenance) always produce the byte-identical
decision record with the same reasons; tie-breaking rules are
injected and declared (content keys only); no wall clock, no
randomness, no network (LOCK-119).

The engine never writes contract state: its effects enter the
contract only through the contract's own frozen command vocabulary
(``replan.bridge`` — LOCK-101).
"""

from __future__ import annotations

from typing import Any, Optional, Sequence, Tuple

from protocol.temporal import parse_instant

from contracts import ConnectivityContract, Provenance

from .errors import ReplanError, ReplanReason
from .model import (
    CANDIDATE_KINDS,
    DEFAULT_TIE_BREAK,
    REALIZATION_TERMINAL_STATES,
    RENEGOTIATION_TRIGGER_KINDS,
    SOFT_TRIGGER_KINDS,
    RealizationSnapshot,
    RenegotiationNotice,
    ReplanCandidate,
    ReplanDecision,
    ReplanTrigger,
    _normalize_tie_break,
)
from .validation import candidate_verdict

#: The contract lifecycle states from which a replan evaluation may
#: run (the active-realization states): CONTRACT_ACTIVE (the plan is
#: engaged-but-not-yet-recorded — the M006 plannable shape),
#: EXECUTION_ACTIVE, DELIVERY, ASSURED, and DEGRADED (the LOCK-116
#: failover-for-a-degraded-realization shape).  INTENT/OFFER_SELECTED
#: carry no engaged realization; the post-execution commercial walk
#: and terminal states never replan.
REPLANNABLE_CONTRACT_STATES: Tuple[str, ...] = (
    "CONTRACT_ACTIVE",
    "EXECUTION_ACTIVE",
    "DELIVERY",
    "ASSURED",
    "DEGRADED",
)


def _candidate_sort_key(tie_break: Sequence[str]) -> Any:
    """The deterministic candidate ordering key (content keys only —
    LOCK-111; the declared rule always ends with the candidate-id
    total order)."""
    kind_rank = {kind: index for index, kind in enumerate(CANDIDATE_KINDS)}

    def key(candidate: ReplanCandidate) -> Tuple[Any, ...]:
        parts = []
        for entry in tie_break:
            if entry == "candidate-kind":
                parts.append(kind_rank.get(candidate.kind, len(CANDIDATE_KINDS)))
            elif entry == "candidate-id":
                parts.append(candidate.candidate_id)
        return tuple(parts)

    return key


def decide_replan(
    contract: ConnectivityContract,
    trigger: ReplanTrigger,
    snapshot: RealizationSnapshot,
    candidates: Sequence[ReplanCandidate],
    *,
    provenance: Optional[Any] = None,
    tie_break: Sequence[str] = DEFAULT_TIE_BREAK,
) -> ReplanDecision:
    """Compute the deterministic replan decision (the closed-loop
    record; pure — no store writes, no contract mutation).

    Fail-closed gates, in order: the contract input (a canonical
    ``contracts.ConnectivityContract`` in a replannable lifecycle
    state), the trigger (typed, attributed to THIS contract, injected
    instant inside the contract validity), the realization snapshot
    (attributed, non-terminal), and the candidate list (non-empty).
    Then every candidate is constraint-validated (LOCK-108) and the
    decision is selected deterministically (see the module docstring).

    ``provenance`` is the caller-supplied decision provenance
    (LOCK-118; recorded verbatim).  When omitted, a deterministic
    default referencing the trigger and the contract is used — the
    engine is a strategy, so its default issuer is the replan domain
    itself, never an authority claim.
    """
    if not isinstance(contract, ConnectivityContract):
        raise ReplanError(
            ReplanReason.INVALID_INPUT,
            "decide_replan requires a contracts.ConnectivityContract (got %s)"
            % type(contract).__name__,
        )
    if contract.is_terminal:
        raise ReplanError(
            ReplanReason.CONTRACT_TERMINAL,
            "contract is terminal in %s; terminal contracts never replan"
            % contract.state,
        )
    if contract.state not in REPLANNABLE_CONTRACT_STATES:
        raise ReplanError(
            ReplanReason.NOT_REPLANNABLE,
            "contract state %s carries no active realization to replan "
            "(replannable: %s)" % (contract.state, ", ".join(REPLANNABLE_CONTRACT_STATES)),
        )
    if not isinstance(trigger, ReplanTrigger):
        raise ReplanError(
            ReplanReason.INVALID_INPUT,
            "decide_replan requires a ReplanTrigger (got %s)" % type(trigger).__name__,
        )
    if trigger.contract_id != contract.contract_id:
        raise ReplanError(
            ReplanReason.ID_MISMATCH,
            "trigger is attributable to contract %s, not %s"
            % (trigger.contract_id[:23], contract.contract_id[:23]),
        )
    trigger_at = parse_instant(trigger.recorded_at)
    if trigger_at < parse_instant(contract.validity.not_before) or trigger_at > parse_instant(
        contract.validity.not_after
    ):
        raise ReplanError(
            ReplanReason.TEMPORAL_INVALID,
            "trigger instant %s escapes the contract validity [%s, %s]"
            % (
                trigger.recorded_at,
                contract.validity.not_before,
                contract.validity.not_after,
            ),
        )
    if not isinstance(snapshot, RealizationSnapshot):
        raise ReplanError(
            ReplanReason.INVALID_INPUT,
            "decide_replan requires a RealizationSnapshot (got %s)"
            % type(snapshot).__name__,
        )
    if snapshot.contract_id != contract.contract_id:
        raise ReplanError(
            ReplanReason.ID_MISMATCH,
            "realization snapshot is attributable to contract %s, not %s"
            % (snapshot.contract_id[:23], contract.contract_id[:23]),
        )
    if snapshot.state in REALIZATION_TERMINAL_STATES:
        raise ReplanError(
            ReplanReason.REALIZATION_TERMINAL,
            "realization is terminal in %s; terminal realizations never replan "
            "(a superseded realization was already failed-over; a failed "
            "realization enters renegotiation or a new acquisition)" % snapshot.state,
        )
    if not isinstance(candidates, (tuple, list)) or isinstance(candidates, (str, bytes)):
        raise ReplanError(
            ReplanReason.INVALID_INPUT,
            "decide_replan requires a sequence of ReplanCandidate records",
        )
    if not candidates:
        raise ReplanError(
            ReplanReason.NO_CANDIDATES,
            "a replan evaluation requires at least one candidate realization "
            "(fail-closed: there is nothing to decide silently — the "
            "caller asserts the available-alternatives surface, empty or not)",
        )
    for i, candidate in enumerate(candidates):
        if not isinstance(candidate, ReplanCandidate):
            raise ReplanError(
                ReplanReason.CANDIDATE_INVALID,
                "candidates[%d] must be a ReplanCandidate record (got %s)"
                % (i, type(candidate).__name__),
            )

    normalized_tie_break = _normalize_tie_break(tie_break, complete=True)

    # deterministic candidate order (declared, injected — LOCK-111)
    ordered = sorted(candidates, key=_candidate_sort_key(normalized_tie_break))
    # duplicate candidate ids fail closed (two records claiming one id)
    seen_ids = set()
    for candidate in ordered:
        if candidate.candidate_id in seen_ids:
            raise ReplanError(
                ReplanReason.CANDIDATE_INVALID,
                "two candidates share the content-derived id %s (duplicate "
                "candidate material fails closed)" % candidate.candidate_id[:23],
            )
        seen_ids.add(candidate.candidate_id)

    # LOCK-108: validate every candidate against the contract's full
    # hard-constraint set (weakening candidates REJECTED, typed, cited)
    verdicts = tuple(candidate_verdict(candidate, contract) for candidate in ordered)

    # decision selection (deterministic)
    contract_fingerprint = contract.hard_constraint_fingerprint()
    replaces = _replaces_material(snapshot, trigger)
    if provenance is None:
        decision_provenance = Provenance(
            issuer="replan:engine",
            decision_refs=(trigger.trigger_id, contract.contract_id),
        )
    elif not isinstance(provenance, Provenance):
        raise ReplanError(
            ReplanReason.INVALID_INPUT,
            "provenance must be a contracts.Provenance record (got %s)"
            % type(provenance).__name__,
        )
    else:
        decision_provenance = provenance

    accepted = [v for v in verdicts if v.accepted]
    if accepted:
        adopted_verdict = accepted[0]  # the declared tie-break order
        adopted = _find_candidate(ordered, adopted_verdict.candidate_id)
        return ReplanDecision(
            trigger_id=trigger.trigger_id,
            contract_id=contract.contract_id,
            decision="adopt-alternative",
            realization_state="SUPERSEDED",
            recorded_at=trigger.recorded_at,
            hard_constraints=contract.hard_constraints,
            constraint_fingerprint=contract_fingerprint,
            verdicts=verdicts,
            provenance=decision_provenance,
            tie_break=normalized_tie_break,
            adopted_candidate_id=adopted.candidate_id,
            adopted_artifacts=adopted.artifact_refs,
            replaces=replaces,
        )

    # no acceptable alternative: the EXPLICIT outcome per trigger class
    notice = RenegotiationNotice(
        superseded_contract_id=contract.contract_id,
        trigger_id=trigger.trigger_id,
        recorded_at=trigger.recorded_at,
        reason=trigger.kind,
    )
    if trigger.kind in SOFT_TRIGGER_KINDS:
        return ReplanDecision(
            trigger_id=trigger.trigger_id,
            contract_id=contract.contract_id,
            decision="degraded",
            realization_state="DEGRADED",
            recorded_at=trigger.recorded_at,
            hard_constraints=contract.hard_constraints,
            constraint_fingerprint=contract_fingerprint,
            verdicts=verdicts,
            provenance=decision_provenance,
            tie_break=normalized_tie_break,
            replaces=replaces,
        )
    if trigger.kind in RENEGOTIATION_TRIGGER_KINDS:
        return ReplanDecision(
            trigger_id=trigger.trigger_id,
            contract_id=contract.contract_id,
            decision="renegotiate",
            realization_state="FAILED",
            recorded_at=trigger.recorded_at,
            hard_constraints=contract.hard_constraints,
            constraint_fingerprint=contract_fingerprint,
            verdicts=verdicts,
            provenance=decision_provenance,
            tie_break=normalized_tie_break,
            replaces=replaces,
            renegotiation=notice,
        )
    return ReplanDecision(
        trigger_id=trigger.trigger_id,
        contract_id=contract.contract_id,
        decision="failed",
        realization_state="FAILED",
        recorded_at=trigger.recorded_at,
        hard_constraints=contract.hard_constraints,
        constraint_fingerprint=contract_fingerprint,
        verdicts=verdicts,
        provenance=decision_provenance,
        tie_break=normalized_tie_break,
        replaces=replaces,
        renegotiation=notice,
    )


def _find_candidate(
    ordered: Sequence[ReplanCandidate], candidate_id: str
) -> ReplanCandidate:
    for candidate in ordered:
        if candidate.candidate_id == candidate_id:
            return candidate
    raise ReplanError(
        ReplanReason.CANDIDATE_INVALID,
        "internal: accepted candidate %s vanished from the ordered set"
        % candidate_id[:23],
    )


def _replaces_material(
    snapshot: RealizationSnapshot, trigger: ReplanTrigger
) -> Tuple[str, ...]:
    """The provenance material referencing the realization being
    replaced: the snapshot id (the execution-state view), the session
    reference when the surface is the harvested session discipline,
    and the trigger's realization reference."""
    material = [snapshot.realization_id]
    if snapshot.session_ref:
        material.append(snapshot.session_ref)
    if trigger.realization_ref:
        material.append(trigger.realization_ref)
    return tuple(material)
