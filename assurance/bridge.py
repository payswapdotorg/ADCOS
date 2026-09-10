"""ADCOS assurance -> contract bridge (M005 — Evidence and Assurance).

The explicit, sole recording path from an assurance evaluation back
into the canonical contract (the closed loop of LOCK-107):

    evidence/ (typed records) -> evaluate_contract (pure verdict)
        -> THIS BRIDGE -> contracts.RecordAssurance (the accepted
           M002 command vocabulary — consumed, never extended)

Mapping (deterministic, closed against the CONSUMED contracts
vocabulary — there is no second state model):

- ``compliant``   -> ``RecordAssurance("compliant")``
- ``degraded``    -> ``RecordAssurance("degraded")``
- ``violated``    -> ``RecordAssurance("violated")``
- ``unknown``     -> ``RecordAssurance("unknown-stale")``
- ``failed``      -> NO command (the contract is already FAILED and
  terminal — terminal contracts reject all commands; the honest
  no-op with an explicit result, never a silent write attempt)
- ``deliberately_terminated`` -> NO command (the contract is already
  TERMINATED — same terminal honesty)

The evaluation id rides the command's ``decision``-kinded evidence
reference (the M002 ``record-assurance`` discipline: assurance
decisions enter as opaque decision references with provenance —
LOCK-117/LOCK-118).  The bridge is fail-closed and typed: bridging a
contract outside the assurance-eligible lifecycle states
(DELIVERY/ASSURED/DEGRADED — the states with legal assurance
transitions in the frozen M002 transition table) raises
BRIDGE_NOT_APPLICABLE before any submission; genuine contract-authority
errors (typed ``ContractError``) propagate unchanged — the contract
store stays the sole writer of contract state (LOCK-101).
"""

from __future__ import annotations

from typing import Optional

from contracts import (
    ASSURANCE_STATES as CONTRACT_ASSURANCE_STATES,
    CONTRACT_STATES,
    CONTRACT_TRANSITIONS,
    OpaqueReference,
    Provenance,
    RecordAssurance,
)

from .errors import AssuranceError, AssuranceReasonCode
from .model import AssuranceEvaluation, ASSURANCE_STATES

#: The evaluation states that map onto a contracts-domain
#: ``record-assurance`` command (the four-state recorded vocabulary
#: the accepted M002 surface carries — the frozen §9 subset it
#: records; ``failed``/``deliberately_terminated`` are contract
#: lifecycle terminal states, not recordable assurance verdicts).
EVALUATION_TO_RECORDED_STATE = {
    "compliant": "compliant",
    "degraded": "degraded",
    "violated": "violated",
    "unknown": "unknown-stale",
}

#: The contract lifecycle states where a ``record-assurance`` command
#: is legal (derived from the frozen M002 transition table: the
#: states with assurance transitions — DELIVERY, ASSURED, DEGRADED).
CONTRACT_RECORDABLE_STATES = tuple(
    sorted(
        state
        for state, targets in CONTRACT_TRANSITIONS.items()
        if "ASSURED" in targets or "DEGRADED" in targets
    )
)

#: The default issuer recorded on the decision reference (LOCK-118).
DEFAULT_BRIDGE_ISSUER = "assurance:m005"


def _check_bridge_consistency() -> None:
    """Import-time consistency guard: every mapped recorded state must
    exist in the CONSUMED contracts assurance vocabulary, and every
    recordable state in the consumed contract lifecycle vocabulary
    (fail loud on drift — never silently mis-bridge)."""
    for recorded in EVALUATION_TO_RECORDED_STATE.values():
        if recorded not in CONTRACT_ASSURANCE_STATES:
            raise AssuranceError(
                AssuranceReasonCode.VOCABULARY,
                "bridge maps to recorded state %r outside the consumed "
                "contracts assurance vocabulary — the frozen vocabularies "
                "have drifted" % recorded,
            )
    known = set(CONTRACT_STATES)
    for state in CONTRACT_RECORDABLE_STATES:
        if state not in known:
            raise AssuranceError(
                AssuranceReasonCode.VOCABULARY,
                "bridge references contract state %r outside the consumed "
                "contracts lifecycle vocabulary" % state,
            )


_check_bridge_consistency()


def bridge_command(
    evaluation: AssuranceEvaluation, issuer: str = DEFAULT_BRIDGE_ISSUER
) -> Optional[RecordAssurance]:
    """Build the contracts-domain command for one evaluation (or None
    for the terminal no-op states).

    The evaluation id rides a ``decision``-kinded opaque reference
    with provenance — exactly the ``record-assurance`` evidence
    discipline of the accepted M002 surface.
    """
    if not isinstance(evaluation, AssuranceEvaluation):
        raise AssuranceError(
            AssuranceReasonCode.INVALID_INPUT,
            "bridge_command requires an AssuranceEvaluation (got %s)"
            % type(evaluation).__name__,
        )
    if evaluation.state not in ASSURANCE_STATES:
        # unreachable post-construction; kept as a closed guard
        raise AssuranceError(
            AssuranceReasonCode.VOCABULARY,
            "evaluation state %r is outside the frozen §9 vocabulary"
            % evaluation.state,
        )
    recorded = EVALUATION_TO_RECORDED_STATE.get(evaluation.state)
    if recorded is None:
        # failed / deliberately_terminated: terminal contracts reject
        # all commands — the honest no-op (never a silent write attempt)
        return None
    return RecordAssurance(
        recorded_at=evaluation.evaluated_at,
        assurance_state=recorded,
        evidence_refs=(
            OpaqueReference(
                ref_kind="decision",
                value=evaluation.evaluation_id,
                provenance=Provenance(issuer=issuer),
            ),
        ),
    )


def record_into_contract(
    store: object,
    evaluation: AssuranceEvaluation,
    contract_id: str,
    issuer: str = DEFAULT_BRIDGE_ISSUER,
):
    """Bridge one evaluation into a live ``ContractStore`` and submit
    the command (the closed loop).  Returns the ``MergeResult`` for
    recorded states, or None for the terminal no-op states.

    Fail-closed: an evaluation whose bridge targets a contract outside
    the assurance-eligible lifecycle states raises
    BRIDGE_NOT_APPLICABLE before any submission (the contract's own
    typed errors propagate unchanged where they apply — the contract
    store stays the sole writer of contract state)."""
    command = bridge_command(evaluation, issuer=issuer)
    if command is None:
        return None
    contract = store.contract(contract_id)
    if contract.state not in CONTRACT_RECORDABLE_STATES:
        raise AssuranceError(
            AssuranceReasonCode.BRIDGE_NOT_APPLICABLE,
            "contract state %r has no legal assurance transition (the "
            "recordable states are %s) — the evaluation is a pure "
            "verdict; recording happens at the delivery/assurance "
            "lifecycle stages"
            % (contract.state, list(CONTRACT_RECORDABLE_STATES)),
        )
    return store.submit(command, recorded_at=evaluation.evaluated_at, contract_id=contract_id)


__all__ = [
    "EVALUATION_TO_RECORDED_STATE",
    "CONTRACT_RECORDABLE_STATES",
    "DEFAULT_BRIDGE_ISSUER",
    "bridge_command",
    "record_into_contract",
]
