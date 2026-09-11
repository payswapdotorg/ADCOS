"""ADCOS replan validation (M008 — Replan and Failover).

The LOCK-108 enforcement core: the pure gates that keep replanning
from silently weakening hard contract constraints.

- :func:`validate_constraints_preserved` — the per-candidate gate:
  fail-closed (raising the typed ``replan-constraint-weakened``
  reason citing the specific constraint kinds) unless the candidate's
  claimed constraint set equals the contract's hard-constraint set
  VERBATIM by canonical content in BOTH directions (dropped, relaxed,
  re-interpreted or invented constraints all fail), then the
  LOCK-108 fingerprint agreement (``replan-constraint-mismatch`` —
  reordered or tampered material fails closed).
- :func:`candidate_verdict` — the non-raising twin used by the
  engine: the same gate expressed as a typed :class:`CandidateVerdict`
  (a rejected candidate carries the reason code and the kind-citing
  detail — LOCK-108 is enforced, never silently swallowed).
- :func:`verify_decision_preserves_contract` — the pure
  cross-authority gate over a finished decision record (the M006
  ``verify_plan_preserves_contract`` discipline applied to replan):
  verbatim constraint-set equality both directions, fingerprint
  agreement, attribution, adopted-candidate consistency, and the
  no-silent-downgrade shape (degraded/failed/renegotiate decisions
  carry their explicit states and the renegotiation notice where the
  frozen shape requires it).

The gates are pure, deterministic and offline: same inputs -> same
verdict, same reasons (LOCK-111); no wall clock, no randomness, no
network (LOCK-119).
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from protocol.canonicalization import canonical_json_bytes

from contracts import ConnectivityContract, HardConstraint

from .errors import ReplanError, ReplanReason
from .model import (
    CandidateVerdict,
    ReplanCandidate,
    ReplanDecision,
    VERDICT_ACCEPTED,
    _constraints_fingerprint,
)


def _constraint_digest_map(
    constraints: Sequence[HardConstraint],
) -> Dict[str, str]:
    """Map canonical-content digest -> kind (order-insensitive set
    equality material; the digest is over each constraint's full
    canonical dict — a relaxed param or a re-interpreted kind produces
    a different digest)."""
    return {
        canonical_json_bytes(constraint.to_dict()).decode("utf-8"): constraint.kind
        for constraint in constraints
    }


def validate_constraints_preserved(
    claimed: Sequence[HardConstraint],
    contract_constraints: Sequence[HardConstraint],
    contract_fingerprint: str,
    *,
    label: str,
) -> None:
    """Fail closed unless the claimed constraint set preserves the
    contract's hard constraints VERBATIM (LOCK-108).

    Checks (ordered so the verdict cites the specific constraint
    kinds):

    1. constraint-set equality by canonical content, both directions
       (dropped, relaxed, re-interpreted or invented constraints all
       fail with ``replan-constraint-weakened``);
    2. LOCK-108 fingerprint agreement over the claimed set
       (``replan-constraint-mismatch`` — the claimed set must hash to
       the contract's own fingerprint, so a reordered lookalike set
       also fails closed).
    """
    if not isinstance(label, str) or not label:
        raise ReplanError(ReplanReason.INVALID_INPUT, "label must be a non-empty string")
    claimed_map = _constraint_digest_map(claimed)
    contract_map = _constraint_digest_map(contract_constraints)
    if set(claimed_map) != set(contract_map):
        missing = sorted(
            {contract_map[text] for text in contract_map if text not in claimed_map}
        )
        added = sorted({claimed_map[text] for text in claimed_map if text not in contract_map})
        detail = "%s does not preserve the contract hard constraints verbatim" % label
        if missing:
            detail += (
                " — contract constraint(s) of kind %s dropped, relaxed or "
                "re-interpreted" % ", ".join(missing)
            )
        if added:
            detail += (
                "; constraint(s) of kind %s carried on %s are not on the contract"
                % (", ".join(added), label)
            )
        raise ReplanError(
            ReplanReason.CONSTRAINT_WEAKENED,
            detail + " (LOCK-108: no silent contract weakening — the candidate "
            "is rejected)",
        )
    if not isinstance(contract_fingerprint, str) or not contract_fingerprint:
        raise ReplanError(
            ReplanReason.INVALID_INPUT, "contract_fingerprint must be non-empty"
        )
    claimed_fingerprint = _constraints_fingerprint(claimed)
    if claimed_fingerprint != contract_fingerprint:
        raise ReplanError(
            ReplanReason.CONSTRAINT_MISMATCH,
            "the claimed constraint set does not reproduce the contract's "
            "LOCK-108 fingerprint (reordered or tampered constraint material "
            "fails closed; %s claimed %s, the contract carries %s)"
            % (label, claimed_fingerprint[:23], contract_fingerprint[:23]),
        )


def candidate_verdict(
    candidate: ReplanCandidate, contract: ConnectivityContract
) -> CandidateVerdict:
    """The LOCK-108 gate as a typed verdict (the engine's form).

    A candidate that weakens/drops ANY hard contract constraint is
    REJECTED with the typed ``replan-constraint-weakened`` reason
    citing the specific kinds; a tampered/reordered claimed set is
    rejected with ``replan-constraint-mismatch``; an accepted candidate
    carries ``replan-candidate-accepted``.  Never silent, never an
    exception across the engine boundary (the verdict IS the record).
    """
    if not isinstance(candidate, ReplanCandidate):
        raise ReplanError(
            ReplanReason.INVALID_INPUT,
            "candidate_verdict requires a ReplanCandidate (got %s)"
            % type(candidate).__name__,
        )
    if not isinstance(contract, ConnectivityContract):
        raise ReplanError(
            ReplanReason.INVALID_INPUT,
            "candidate_verdict requires a contracts.ConnectivityContract",
        )
    # attribution: a candidate for another contract is not a candidate
    # for THIS replan (fail-closed verdict, cited)
    if candidate.contract_id != contract.contract_id:
        return CandidateVerdict(
            candidate_id=candidate.candidate_id,
            accepted=False,
            code=ReplanReason.ID_MISMATCH,
            detail="candidate is attributable to contract %s, not %s"
            % (candidate.contract_id[:23], contract.contract_id[:23]),
        )
    try:
        validate_constraints_preserved(
            candidate.hard_constraints,
            contract.hard_constraints,
            contract.hard_constraint_fingerprint(),
            label="candidate %s" % candidate.candidate_id[:23],
        )
    except ReplanError as error:
        return CandidateVerdict(
            candidate_id=candidate.candidate_id,
            accepted=False,
            code=error.code,
            detail=error.detail,
        )
    return CandidateVerdict(
        candidate_id=candidate.candidate_id,
        accepted=True,
        code=VERDICT_ACCEPTED,
        detail="candidate %s preserves the contract hard constraints verbatim "
        "(LOCK-108 fingerprint %s agrees)"
        % (candidate.candidate_id[:23], contract.hard_constraint_fingerprint()[:23]),
    )


def verify_decision_preserves_contract(
    decision: ReplanDecision, contract: ConnectivityContract
) -> None:
    """Fail closed unless the decision preserves the contract's hard
    constraints verbatim and stays within the contract authority
    (the pure cross-authority LOCK-108 gate over the finished record).

    Checks (ordered so the verdict cites the specific kinds):

    1. constraint-set equality by canonical content, both directions
       (``replan-constraint-weakened``);
    2. LOCK-108 fingerprint agreement with the CONTRACT's own
       fingerprint (``replan-constraint-mismatch``);
    3. attribution: the decision references exactly this contract
       (``replan-id-mismatch``);
    4. the adopted candidate (if any) is an ACCEPTED verdict on this
       decision (``replan-vocabulary``);
    5. the no-silent-downgrade shape: a degraded/failed/renegotiate
       decision carries the explicit realization state and the
       renegotiation notice the frozen shape requires
       (``replan-vocabulary``).
    """
    if not isinstance(decision, ReplanDecision):
        raise ReplanError(
            ReplanReason.INVALID_INPUT,
            "verify_decision_preserves_contract requires a ReplanDecision",
        )
    if not isinstance(contract, ConnectivityContract):
        raise ReplanError(
            ReplanReason.INVALID_INPUT,
            "verify_decision_preserves_contract requires a contracts.ConnectivityContract",
        )

    # 1. verbatim set equality (LOCK-108 — the kind-citing gate)
    validate_constraints_preserved(
        decision.hard_constraints,
        contract.hard_constraints,
        contract.hard_constraint_fingerprint(),
        label="decision %s" % decision.decision_id[:23],
    )

    # 2. fingerprint agreement with the CONTRACT's own (the M002
    #    LOCK-108 evidence convention, re-verified here)
    if decision.constraint_fingerprint != contract.hard_constraint_fingerprint():
        raise ReplanError(
            ReplanReason.CONSTRAINT_MISMATCH,
            "the decision's LOCK-108 constraint fingerprint does not match the "
            "contract's (tampered or forged decision material fails closed)",
        )

    # 3. attribution
    if decision.contract_id != contract.contract_id:
        raise ReplanError(
            ReplanReason.ID_MISMATCH,
            "the decision is attributable to contract %s, not %s"
            % (decision.contract_id[:23], contract.contract_id[:23]),
        )

    # 4. adopted-candidate consistency
    if decision.decision == "adopt-alternative":
        accepted_ids = {
            v.candidate_id for v in decision.verdicts if v.accepted
        }
        if decision.adopted_candidate_id not in accepted_ids:
            raise ReplanError(
                ReplanReason.VOCABULARY,
                "the adopted candidate %s is not an accepted verdict on this "
                "decision (LOCK-108: only a constraint-preserving candidate "
                "may be adopted)" % decision.adopted_candidate_id[:23],
            )

    # 5. the no-silent-downgrade shape (the frozen §9 discipline)
    if decision.decision == "degraded" and decision.realization_state != "DEGRADED":
        raise ReplanError(
            ReplanReason.VOCABULARY,
            "a degraded decision must enter the explicit DEGRADED realization "
            "state (never a silent downgrade)",
        )
    if decision.decision in ("failed", "renegotiate"):
        if decision.realization_state != "FAILED":
            raise ReplanError(
                ReplanReason.VOCABULARY,
                "a %s decision must enter the explicit FAILED realization state"
                % decision.decision,
            )
        if decision.renegotiation is None:
            raise ReplanError(
                ReplanReason.VOCABULARY,
                "a %s decision must carry the explicit renegotiation notice "
                "(the renegotiation trigger path)" % decision.decision,
            )
