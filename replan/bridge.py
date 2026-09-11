"""ADCOS replan -> contract bridge (M008 — Replan and Failover).

The explicit, sole recording path from a replan decision back into
the canonical contract (the closed loop of frozen 1.1 §9):

    replan decision (typed record) -> THIS BRIDGE -> the accepted
    M002 command vocabulary (consumed, never extended)

Mapping (deterministic, closed against the CONSUMED contracts
vocabulary — there is no second state model):

- ``adopt-alternative`` -> one ``BindExecutionArtifact`` per adopted
  artifact reference (the alternative realization rides onto the
  contract as opaque execution-artifact DATA — LOCK-117: binding
  changes no identity, no state, no constraint);
- ``degraded``         -> ``RecordAssurance("degraded")`` (the
  contract enters its own explicit DEGRADED state through its own
  frozen transition table — never a silent downgrade);
- ``failed``           -> ``RecordAssurance("violated")`` (the
  contract FAILS with the constraint-violated termination reason
  through its own frozen transition table);
- ``renegotiate``      -> ``RecordAssurance("violated")`` plus the
  typed renegotiation notice (the successor contract is created
  through the M002 ``superseded-contract`` reference path by the
  principal-side flow — ``renegotiation_create_command`` builds that
  creation core helper shape; contracts/ stays the sole authority,
  LOCK-101).

The decision id rides the command's ``decision``-kinded evidence
reference (the M002 ``record-assurance`` discipline: decisions enter
as opaque decision references with provenance — LOCK-117/LOCK-118).
The bridge is fail-closed and typed: bridging a decision whose
recording edge is not legal in the contract's own frozen transition
table raises ``replan-bridge-inapplicable`` BEFORE any submission
(mirrors the M005 ``BRIDGE_NOT_APPLICABLE`` honesty); genuine
contract-authority errors (typed ``ContractError``) are surfaced as
typed replan errors with their deterministic text — the contract
store stays the sole writer of contract state (LOCK-101).
"""

from __future__ import annotations

from typing import Optional, Tuple

from contracts import (
    CONTRACT_STATES,
    CONTRACT_TRANSITIONS,
    BindExecutionArtifact,
    ConnectivityContract,
    OpaqueReference,
    Provenance,
    RecordAssurance,
)

from .errors import ReplanError, ReplanReason
from .model import ReplanDecision

#: The contract lifecycle states where a ``record-assurance``
#: (``degraded``) command is legal (derived from the frozen M002
#: transition table — the states with the DEGRADED edge).
_DEGRADED_RECORDABLE_STATES: Tuple[str, ...] = tuple(
    sorted(
        state
        for state, targets in CONTRACT_TRANSITIONS.items()
        if "DEGRADED" in targets
    )
)

#: The contract lifecycle states where a ``record-assurance``
#: (``violated``) command is legal (derived from the frozen M002
#: transition table — the states with the FAILED edge).
_FAILED_RECORDABLE_STATES: Tuple[str, ...] = tuple(
    sorted(state for state, targets in CONTRACT_TRANSITIONS.items() if "FAILED" in targets)
)

#: The default issuer recorded on the bridged decision reference
#: (LOCK-118).
DEFAULT_BRIDGE_ISSUER = "replan:m008"


def _check_bridge_consistency() -> None:
    """Import-time consistency guard: every bridge-relevant derived
    state set must exist in the CONSUMED contracts lifecycle
    vocabulary (fail loud on drift — never silently mis-bridge)."""
    known = set(CONTRACT_STATES)
    for state in _DEGRADED_RECORDABLE_STATES + _FAILED_RECORDABLE_STATES:
        if state not in known:
            raise ReplanError(
                ReplanReason.VOCABULARY,
                "the bridge references contract state %r outside the consumed "
                "contracts lifecycle vocabulary — the frozen vocabularies "
                "have drifted" % (state,),
            )


_check_bridge_consistency()


def _decision_reference(decision: ReplanDecision) -> OpaqueReference:
    """The decision's own opaque ``decision``-kinded reference (the
    M002 record-assurance evidence discipline)."""
    return OpaqueReference(
        ref_kind="decision",
        value=decision.decision_id,
        provenance=Provenance(
            issuer=DEFAULT_BRIDGE_ISSUER,
            decision_refs=(decision.trigger_id, decision.contract_id),
        ),
    )


def _require_bridge_inputs(
    decision: ReplanDecision, contract: ConnectivityContract
) -> None:
    if not isinstance(decision, ReplanDecision):
        raise ReplanError(
            ReplanReason.INVALID_INPUT,
            "the bridge requires a ReplanDecision (got %s)" % type(decision).__name__,
        )
    if not isinstance(contract, ConnectivityContract):
        raise ReplanError(
            ReplanReason.INVALID_INPUT,
            "the bridge requires a contracts.ConnectivityContract (got %s)"
            % type(contract).__name__,
        )
    if decision.contract_id != contract.contract_id:
        raise ReplanError(
            ReplanReason.ID_MISMATCH,
            "the decision is attributable to contract %s, not %s"
            % (decision.contract_id[:23], contract.contract_id[:23]),
        )


def bridge_commands(
    decision: ReplanDecision, contract: ConnectivityContract
) -> Tuple[object, ...]:
    """Build the contracts-domain commands for one replan decision
    (the explicit, sole recording path back into the contract).

    Fail-closed: the contract must be attributable and NON-TERMINAL
    (terminal contracts reject all commands — the honest typed error,
    never a silent write attempt), and the decision's recording edge
    must exist in the contract's own frozen transition table for the
    contract's current state (``replan-bridge-inapplicable``
    otherwise).  The commands are BUILT, not submitted: the caller
    submits them through the contract store (the sole writer).
    """
    _require_bridge_inputs(decision, contract)
    if contract.is_terminal:
        raise ReplanError(
            ReplanReason.BRIDGE_INAPPLICABLE,
            "contract is terminal in %s; terminal contracts reject all "
            "commands — the replan decision is recorded evidence, not a "
            "contract mutation" % contract.state,
        )
    reference = _decision_reference(decision)
    if decision.decision == "adopt-alternative":
        # LOCK-117: the adopted artifacts ride as opaque data at any
        # non-terminal state (the contract's own bind-artifact
        # discipline — binding changes no identity/state/constraint)
        return tuple(
            BindExecutionArtifact(artifact=artifact) for artifact in decision.adopted_artifacts
        )
    if decision.decision == "degraded":
        if contract.state not in _DEGRADED_RECORDABLE_STATES:
            raise ReplanError(
                ReplanReason.BRIDGE_INAPPLICABLE,
                "the contract's frozen transition table has no DEGRADED edge "
                "from %s (recordable: %s) — the degraded decision stays "
                "recorded evidence, never a silent downgrade"
                % (contract.state, ", ".join(_DEGRADED_RECORDABLE_STATES)),
            )
        return (
            RecordAssurance(
                recorded_at=decision.recorded_at,
                assurance_state="degraded",
                evidence_refs=(reference,),
            ),
        )
    # failed / renegotiate: the realization cannot satisfy the hard
    # constraints — the contract records the violation through its own
    # frozen vocabulary (FAILED with the constraint-violated reason)
    if contract.state not in _FAILED_RECORDABLE_STATES:
        raise ReplanError(
            ReplanReason.BRIDGE_INAPPLICABLE,
            "the contract's frozen transition table has no FAILED edge from "
            "%s (recordable: %s)" % (contract.state, ", ".join(_FAILED_RECORDABLE_STATES)),
        )
    return (
        RecordAssurance(
            recorded_at=decision.recorded_at,
            assurance_state="violated",
            evidence_refs=(reference,),
        ),
    )


def renegotiation_reference(decision: ReplanDecision) -> OpaqueReference:
    """The opaque ``superseded-contract`` reference for the successor
    contract's creation core (the explicit renegotiation trigger
    path: the successor contract cites the superseded one through the
    accepted M002 ``superseded-contract`` reference kind — the
    successor creation itself happens through ``CreateContract`` with
    this reference, by the principal-side flow; the replan domain
    never creates contracts, LOCK-101)."""
    if not isinstance(decision, ReplanDecision):
        raise ReplanError(
            ReplanReason.INVALID_INPUT,
            "renegotiation_reference requires a ReplanDecision (got %s)"
            % type(decision).__name__,
        )
    if decision.renegotiation is None:
        raise ReplanError(
            ReplanReason.BRIDGE_INAPPLICABLE,
            "only a failed/renegotiate decision carries the renegotiation "
            "notice (an adopt-alternative/degraded decision does not trigger "
            "renegotiation)",
        )
    return OpaqueReference(
        ref_kind="superseded-contract",
        value=decision.renegotiation.superseded_contract_id,
        provenance=Provenance(
            issuer=DEFAULT_BRIDGE_ISSUER,
            decision_refs=(decision.renegotiation.notice_id, decision.trigger_id),
        ),
    )
