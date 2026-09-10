"""The M010 deterministic simulation seams (the disclosed NOT-YET-
DELIVERED mechanics of the frozen ShareNet flow).

The frozen 8-step ShareNet flow
(``spec/integration/vertical-proof.md``, ACR-014 FROZEN) routes
through mechanics owned by R7 children that are NOT yet accepted:

- step 3 (eligibility and evidence evaluation) needs M004
  (Eligibility and Policy) and M005 (Evidence and Assurance);
- step 5 (execution via providers) needs M006 (Execution Plan) and
  the provider realization plane of M007 (Provider/Standard
  Adapters);
- step 6 (a provider realization degrades or fails) needs the same
  realization plane plus M005 assurance observation;
- step 7 (replan/failover without weakening hard constraints) needs
  M008 (Replan and Failover) — LOCK-108 is the hard gate;
- step 8 (usage and assurance evidence attributable to the contract)
  needs M009 (Usage and Commercial Reconciliation).

NONE of those children is delivered at this head.  This module
therefore provides SIX clearly-labeled deterministic SIMULATION
SEAMS — one per pending mechanic — so the vertical proof can compose
the flow end-to-end TODAY without ever pretending the real children
exist:

    SEAM != AUTHORITY.  Every seam is deterministic (injected
    instants, injected failure schedules, no randomness, no wall
    clock, no network, no secrets — LOCK-119), produces DATA only,
    and NEVER mutates the canonical contract.  Canonical mutations
    always go through the real ``ContractStore`` command surface.
    The seam registry (:data:`SIMULATION_SEAMS`) is the single
    disclosure point: every seam declares the M-item it stands in
    for and that the M-item is PENDING DELIVERY.

The constraint kernel (:func:`evaluate_constraint` /
:func:`evaluate_offer_against_constraints`) is the LOCK-108 heart of
the harness: it evaluates an offer's explicit bounded commitments
against a contract's hard constraints UNCHANGED, returning True
(satisfied) / False (present-and-violating — the rejection trail) /
None (dimension uncommitted — no information, neither satisfied nor
violated).  Failover candidates that evaluate False are rejected
fail-closed; a "no candidate remains" outcome is a rejection trail,
never a weakened constraint.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from contracts import (
    ConnectivityContract,
    ContractError,
    HardConstraint,
    OpaqueReference,
    Provenance,
)
from offers import OfferExchange, OfferRecord

from .application import REASON_FAIL_CLOSED, REASON_INVALID_INPUT, ShareNetError

# ----------------------------------------------------------------------
# The disclosure registry (the single seam disclosure point)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class SeamDisclosure:
    """One registry entry: a seam, the M-item it stands in for, and
    the delivery status of that M-item at this head."""

    seam_id: str
    stands_in_for: str
    authority_status: str
    exported_symbol: str


#: The frozen seam registry (SIX seams; the disclosure the evidence
#: doc and the battery both re-assert).  Every entry names a PENDING
#: M-item — if any of these children is ACCEPTED, the seam is no
#: longer the stand-in and must be re-composed (fail-loud by review,
#: not silently).
SIMULATION_SEAMS: Tuple[SeamDisclosure, ...] = (
    SeamDisclosure(
        seam_id="seam:m004-eligibility",
        stands_in_for="M004 — Eligibility and Policy",
        authority_status=(
            "PENDING DELIVERY: deterministic simulation seam; the M004 "
            "eligibility/policy authority does not exist at this head"
        ),
        exported_symbol="sharenet.seams.EligibilitySeam",
    ),
    SeamDisclosure(
        seam_id="seam:m005-assurance",
        stands_in_for="M005 — Evidence and Assurance",
        authority_status=(
            "PENDING DELIVERY: deterministic simulation seam; the M005 "
            "evidence/assurance authority does not exist at this head"
        ),
        exported_symbol="sharenet.seams.AssuranceSeam",
    ),
    SeamDisclosure(
        seam_id="seam:m006-execution-plan",
        stands_in_for="M006 — Execution Plan",
        authority_status=(
            "PENDING DELIVERY: deterministic simulation seam; the M006 "
            "execution-plan bridge (LOCK-109) does not exist at this head"
        ),
        exported_symbol="sharenet.seams.ExecutionPlanSeam",
    ),
    SeamDisclosure(
        seam_id="seam:m007-realization",
        stands_in_for="M007 — Provider/Standard Adapters (realization plane)",
        authority_status=(
            "PENDING DELIVERY: deterministic simulation seam; the M007 "
            "provider realization plane does not exist at this head"
        ),
        exported_symbol="sharenet.seams.ProviderRealizationSeam",
    ),
    SeamDisclosure(
        seam_id="seam:m008-replan",
        stands_in_for="M008 — Replan and Failover",
        authority_status=(
            "PENDING DELIVERY: deterministic simulation seam; the M008 "
            "closed-loop replan authority does not exist at this head "
            "(LOCK-108 stays the hard gate)"
        ),
        exported_symbol="sharenet.seams.ReplanEngine",
    ),
    SeamDisclosure(
        seam_id="seam:m009-usage",
        stands_in_for="M009 — Usage and Commercial Reconciliation",
        authority_status=(
            "PENDING DELIVERY: deterministic simulation seam; the M009 "
            "usage/reconciliation authority does not exist at this head"
        ),
        exported_symbol="sharenet.seams.UsageObservationSeam",
    ),
)

SEAM_IDS: Tuple[str, ...] = tuple(entry.seam_id for entry in SIMULATION_SEAMS)


# ----------------------------------------------------------------------
# The constraint kernel (LOCK-108: hard constraints evaluated
# UNCHANGED — never weakened, never reinterpreted)
# ----------------------------------------------------------------------

#: The frozen mapping from contract hard-constraint kinds to the
#: offer commitment kinds that speak to the same dimension (the M002
#: <-> M003 vocabulary pairs).
_CONSTRAINT_TO_COMMITMENT: Dict[str, str] = {
    "latency-bound": "latency-bound-ms",
    "throughput-floor": "throughput-floor-kbps",
    "availability-floor": "availability-floor-nine",
    "loss-bound": "loss-bound-pct",
    "jitter-bound": "jitter-bound-ms",
    "capacity-floor": "capacity-floor-kbps",
}

#: How each dimension compares a constraint bound against a
#: commitment value ("upper" = commitment must be <= bound; "floor" =
#: commitment must be >= bound).
_DIMENSION_SENSE: Dict[str, str] = {
    "latency-bound": "upper",
    "throughput-floor": "floor",
    "availability-floor": "floor",
    "loss-bound": "upper",
    "jitter-bound": "upper",
    "capacity-floor": "floor",
}

#: The frozen commitment parameter name each commitment kind carries
#: its scalar bound in.
_COMMITMENT_PARAM: Dict[str, str] = {
    "latency-bound-ms": "max_ms",
    "throughput-floor-kbps": "min_kbps",
    "availability-floor-nine": "min_nines",
    "loss-bound-pct": "max_pct",
    "jitter-bound-ms": "max_ms",
    "capacity-floor-kbps": "min_kbps",
}

_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9._:+/-]{1,128}$")


def evaluate_constraint(
    constraint: HardConstraint, commitment: OfferRecord
) -> Optional[bool]:
    """Evaluate one hard constraint against one offer's explicit
    bounded commitments (LOCK-108, the kernel).

    Returns:

    - ``True`` — the offer carries the dimension and its commitment
      satisfies the constraint bound;
    - ``False`` — the offer carries the dimension and its commitment
      VIOLATES the bound (the rejection trail: present-and-violating
      is a violation, not an abstention);
    - ``None`` — the offer commits nothing on the dimension (no
      information; eligibility abstains, it does not pass).
    """
    if not isinstance(constraint, HardConstraint):
        raise ShareNetError(
            REASON_INVALID_INPUT,
            "evaluate_constraint requires a contracts.HardConstraint",
        )
    if not isinstance(commitment, OfferRecord):
        raise ShareNetError(
            REASON_INVALID_INPUT,
            "evaluate_constraint requires an offers.OfferRecord",
        )
    expected_kind = _CONSTRAINT_TO_COMMITMENT.get(constraint.kind)
    if expected_kind is None:
        # a constraint dimension with no offer-side vocabulary: no
        # offer can speak to it; the kernel abstains (policy and
        # trust constraints are M004 material, not offer commitments)
        return None
    param_name = _COMMITMENT_PARAM[expected_kind]
    sense = _DIMENSION_SENSE[constraint.kind]
    bound = constraint.params.get(_constraint_param_name(constraint.kind))
    if bound is None:
        # the constraint is dimension-kind without its bound:
        # nothing to enforce (kernel abstains)
        return None
    matching = tuple(
        offer_commitment
        for offer_commitment in commitment.commitments
        if offer_commitment.kind == expected_kind
    )
    if not matching:
        # the offer commits nothing on the dimension: no information
        return None
    verdict: Optional[bool] = None
    for offer_commitment in matching:
        value = offer_commitment.params.get(param_name)
        if value is None:
            # the commitment kind exists without its bound parameter:
            # abstain on THIS entry (fail-open on ABSENT data, never
            # on violating data)
            continue
        satisfied = value <= bound if sense == "upper" else value >= bound
        if not satisfied:
            # fail-closed: ANY present-and-violating commitment on the
            # dimension rejects the offer (the LOCK-108 trail)
            return False
        verdict = True
    return verdict


def _constraint_param_name(constraint_kind: str) -> str:
    """The canonical bound parameter of each constraint kind (the
    family convention: ms / bps / pct / nines scalars)."""
    names = {
        "latency-bound": "ms",
        "throughput-floor": "bps",
        "availability-floor": "nines",
        "loss-bound": "pct",
        "jitter-bound": "ms",
        "capacity-floor": "bps",
    }
    return names.get(constraint_kind, "")


@dataclass(frozen=True)
class ConstraintEvaluation:
    """The deterministic per-dimension evaluation of one offer
    against a constraint set (the LOCK-108 record: satisfied,
    violated, and uncommitted dimensions — the full trail)."""

    offer_id: str
    satisfied: Tuple[str, ...]
    violated: Tuple[str, ...]
    uncommitted: Tuple[str, ...]


def evaluate_offer_against_constraints(
    offer: OfferRecord, constraints: Tuple[HardConstraint, ...]
) -> ConstraintEvaluation:
    """Evaluate every hard constraint against one offer (sorted by
    constraint kind for determinism)."""
    satisfied: List[str] = []
    violated: List[str] = []
    uncommitted: List[str] = []
    for constraint in sorted(constraints, key=lambda item: item.kind):
        verdict = evaluate_constraint(constraint, offer)
        if verdict is True:
            satisfied.append(constraint.kind)
        elif verdict is False:
            violated.append(constraint.kind)
        else:
            uncommitted.append(constraint.kind)
    return ConstraintEvaluation(
        offer_id=offer.offer_id,
        satisfied=tuple(satisfied),
        violated=tuple(violated),
        uncommitted=tuple(uncommitted),
    )


# ----------------------------------------------------------------------
# Seam: M004 — eligibility and policy (step 3)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class EligibilityDecision:
    """One offer's eligibility decision (M004 seam output: DATA with
    the full evaluation trail; never a contract mutation)."""

    offer_id: str
    provider: str
    eligible: bool
    evaluation: ConstraintEvaluation
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "offer_id": self.offer_id,
            "provider": self.provider,
            "eligible": self.eligible,
            "satisfied": list(self.evaluation.satisfied),
            "violated": list(self.evaluation.violated),
            "uncommitted": list(self.evaluation.uncommitted),
            "reason": self.reason,
        }


class EligibilitySeam:
    """The M004 stand-in: deterministic eligibility evaluation over
    the REAL offer records and the REAL contract hard constraints.

    Fail-closed rule (LOCK-108 adjacent): an offer is INELIGIBLE iff
    any evaluated dimension is present-and-violating; uncommitted
    dimensions abstain (eligibility does not convert absent evidence
    into a pass or a fail — the M005-era evidence-honesty
    discipline).  The seam also requires every candidate offer to
    carry provenance with at least one decision reference (LOCK-118:
    no un-provenanced offer is eligible — evidence sufficiency).
    """

    def evaluate(
        self,
        *,
        offer: OfferRecord,
        constraints: Tuple[HardConstraint, ...],
        at_instant: str,
    ) -> EligibilityDecision:
        evaluation = evaluate_offer_against_constraints(offer, constraints)
        if evaluation.violated:
            return EligibilityDecision(
                offer_id=offer.offer_id,
                provider=offer.provider,
                eligible=False,
                evaluation=evaluation,
                reason="hard-constraint-violation:%s"
                % "+".join(sorted(evaluation.violated)),
            )
        if not offer.provenance.decision_refs:
            return EligibilityDecision(
                offer_id=offer.offer_id,
                provider=offer.provider,
                eligible=False,
                evaluation=evaluation,
                reason="insufficient-evidence:no-decision-refs",
            )
        return EligibilityDecision(
            offer_id=offer.offer_id,
            provider=offer.provider,
            eligible=True,
            evaluation=evaluation,
            reason="eligible:%d-dimensions-satisfied+%d-abstain"
            % (len(evaluation.satisfied), len(evaluation.uncommitted)),
        )

    def evaluate_all(
        self,
        *,
        offers: Tuple[OfferRecord, ...],
        constraints: Tuple[HardConstraint, ...],
        at_instant: str,
    ) -> Tuple[EligibilityDecision, ...]:
        """Evaluate every offered candidate (deterministic order:
        the exchange's sorted order)."""
        return tuple(
            self.evaluate(offer=offer, constraints=constraints, at_instant=at_instant)
            for offer in offers
        )


# ----------------------------------------------------------------------
# Seam: M005 — evidence and assurance (steps 3/6/8)
# ----------------------------------------------------------------------


class AssuranceSeam:
    """The M005 stand-in: deterministic assurance observation of one
    realization against the contract's assurance obligations.

    The observation state vocabulary is the canonical one
    (``compliant`` / ``degraded`` / ``violated`` / ``unknown-stale``);
    the seam derives the state from the realization status the M007
    seam reports, and always emits an evidence token (the M005
    evidence typing: an assurance evaluation is an OBSERVATION, never
    a claim or an attestation).
    """

    def observe(
        self,
        *,
        realization_status: str,
        obligations: Tuple[str, ...],
        at_instant: str,
        sequence: int,
    ) -> Tuple[str, str]:
        """Observe one realization: returns the canonical assurance
        state token and the evidence token (deterministic)."""
        if realization_status == "healthy":
            state = "compliant"
        elif realization_status == "degraded":
            state = "degraded"
        elif realization_status == "failed":
            # a dead realization reports NO evidence: the honest
            # observation is unknown-stale (never compliant by
            # inference — the evidence-class honesty rule)
            state = "unknown-stale"
        else:
            raise ShareNetError(
                REASON_INVALID_INPUT,
                "realization_status %r is outside the seam vocabulary "
                "(healthy/degraded/failed)" % (realization_status,),
            )
        token = "m005-seam:assurance:%s:seq-%d" % (state, sequence)
        return state, token


# ----------------------------------------------------------------------
# Seam: M006 — execution plan (step 5)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class PlanSegment:
    """One execution segment of the simulated plan (DATA: the
    provider, the grounding offer id, and the artifact token to bind
    as contract DATA — LOCK-109's bridge, simulated)."""

    provider: str
    offer_id: str
    artifact_token: str
    role: str  # "primary" | "failover"

    def artifact_reference(self) -> OpaqueReference:
        """The opaque execution-artifact reference for this segment
        (LOCK-117: an artifact binds as DATA, never authority)."""
        return OpaqueReference(
            ref_kind="execution-artifact",
            value=self.artifact_token,
            provenance=Provenance(
                issuer="m006-seam:execution-plan",
                decision_refs=("sharenet:plan:%s" % self.role,),
            ),
        )


@dataclass(frozen=True)
class SimulatedExecutionPlan:
    """The simulated contract-to-mechanisms translation (M006 seam
    output): segments in deterministic (provider, offer) order."""

    segments: Tuple[PlanSegment, ...]


class ExecutionPlanSeam:
    """The M006 stand-in: translate a contract into a simulated
    execution plan over its ACCEPTED offers (LOCK-109: the plan is
    the bridge from contract to provider mechanisms; here the
    mechanisms are simulated, the contract is real and read-only).

    The primary segment is the first accepted offer in deterministic
    (provider, offer id) order; every further accepted offer becomes
    a failover segment (LOCK-116: multiple providers may compose
    under one contract).
    """

    def build_plan(
        self,
        *,
        contract: ConnectivityContract,
        exchange: OfferExchange,
        at_instant: str,
    ) -> SimulatedExecutionPlan:
        if not isinstance(contract, ConnectivityContract):
            raise ShareNetError(
                REASON_INVALID_INPUT,
                "build_plan requires a contracts.ConnectivityContract",
            )
        if not isinstance(exchange, OfferExchange):
            raise ShareNetError(
                REASON_INVALID_INPUT,
                "build_plan requires an offers.OfferExchange",
            )
        segments: List[PlanSegment] = []
        references = sorted(
            (ref for ref in contract.accepted_offers if ref.ref_kind == "offer"),
            key=lambda ref: ref.value,
        )
        for position, reference in enumerate(references):
            offer = exchange.offer(reference.value)
            role = "primary" if position == 0 else "failover"
            segments.append(
                PlanSegment(
                    provider=offer.provider,
                    offer_id=offer.offer_id,
                    artifact_token="m006-seam:realization:%s:seg-%d"
                    % (role, position + 1),
                    role=role,
                )
            )
        if not segments:
            raise ShareNetError(
                REASON_FAIL_CLOSED,
                "the contract carries no accepted offer references; an "
                "execution plan cannot be built (fail-closed)",
            )
        return SimulatedExecutionPlan(segments=tuple(segments))


# ----------------------------------------------------------------------
# Seam: M007 — provider realization (steps 5/6)
# ----------------------------------------------------------------------

#: The deterministic realization-event kinds of the injected failure
#: schedule (frozen flow step 6: a provider realization DEGRADES or
#: FAILS — nothing else is scripted).
REALIZATION_EVENT_KINDS: Tuple[str, ...] = ("degraded", "failed")


@dataclass(frozen=True)
class RealizationEvent:
    """One scripted realization event (deterministic, injected): the
    provider whose realization changes, the kind of change, the
    instant it becomes effective, and a detail token."""

    provider: str
    kind: str
    effective_at: str
    detail: str

    def __post_init__(self) -> None:
        if self.kind not in REALIZATION_EVENT_KINDS:
            raise ShareNetError(
                REASON_INVALID_INPUT,
                "realization event kind %r is outside the frozen schedule "
                "vocabulary %s" % (self.kind, list(REALIZATION_EVENT_KINDS)),
            )


@dataclass(frozen=True)
class FailureSchedule:
    """The injected deterministic failure schedule (LOCK-119: no
    randomness anywhere — degradation and failure are SCRIPTED, and
    the same schedule reproduces the same vertical byte-for-byte)."""

    events: Tuple[RealizationEvent, ...] = ()


class ProviderRealizationSeam:
    """The M007-adjacent stand-in: the simulated provider realization
    plane.  Each segment's realization status at an instant is a
    pure function of the injected schedule: healthy until the
    provider's scripted event takes effect, degraded/failed from the
    effective instant onward."""

    def status_at(
        self, *, provider: str, schedule: FailureSchedule, at_instant: str
    ) -> str:
        """The realization status of one provider's segment at the
        injected instant (deterministic: the LATEST event whose
        effective_at <= the instant wins)."""
        status = "healthy"
        for event in schedule.events:
            if event.provider != provider:
                continue
            if event.effective_at <= at_instant:
                status = event.kind
        return status

    def events_for(self, *, schedule: FailureSchedule) -> Tuple[RealizationEvent, ...]:
        """The full scripted schedule (deterministic order: as
        injected)."""
        return tuple(schedule.events)


# ----------------------------------------------------------------------
# Seam: M008 — replan and failover (step 7, LOCK-108's hard gate)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class CandidateRejection:
    """One failover candidate's LOCK-108 rejection trail entry."""

    provider: str
    offer_id: str
    violated: Tuple[str, ...]
    detail: str


@dataclass(frozen=True)
class FailoverDecision:
    """The replan outcome: a failover PLAN (the segment to execute
    next under the SAME contract — never a new contract, never a
    weakened constraint) or a REJECTION TRAIL (every candidate
    evaluated, each failure recorded; fail-closed).

    Exactly one of ``plan`` / ``rejections`` is set; ``weakened`` is
    always False (LOCK-108: the decision carries the constraint set
    hash BEFORE and AFTER evaluation to prove byte-identity)."""

    plan: Optional[PlanSegment]
    rejections: Tuple[CandidateRejection, ...]
    constraints_before: Tuple[Tuple[str, Tuple[Tuple[str, Any], ...]], ...]
    constraints_after: Tuple[Tuple[str, Tuple[Tuple[str, Any], ...]], ...]
    weakened: bool

    @property
    def rejected(self) -> bool:
        return self.plan is None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rejected": self.rejected,
            "plan": (
                None
                if self.plan is None
                else {
                    "provider": self.plan.provider,
                    "offer_id": self.plan.offer_id,
                    "artifact_token": self.plan.artifact_token,
                    "role": self.plan.role,
                }
            ),
            "rejections": [
                {
                    "provider": entry.provider,
                    "offer_id": entry.offer_id,
                    "violated": list(entry.violated),
                    "detail": entry.detail,
                }
                for entry in self.rejections
            ],
            "constraints_before": [
                {"kind": kind, "params": dict(params)}
                for kind, params in self.constraints_before
            ],
            "constraints_after": [
                {"kind": kind, "params": dict(params)}
                for kind, params in self.constraints_after
            ],
            "weakened": self.weakened,
        }


def _constraint_snapshot(
    contract: ConnectivityContract,
) -> Tuple[Tuple[str, Tuple[Tuple[str, Any], ...]], ...]:
    """The deterministic hard-constraint snapshot (kind + params,
    sorted) — the LOCK-108 before/after equality proof."""
    return tuple(
        (constraint.kind, tuple(sorted(constraint.params.items())))
        for constraint in sorted(
            contract.hard_constraints, key=lambda item: item.kind
        )
    )


class ReplanEngine:
    """The M008 stand-in: closed-loop replan/failover for one
    contract whose realization degraded or failed.

    The LOCK-108 discipline is structural here:

    - the constraint set is read from the REAL contract and is NEVER
      mutated (there is no code path that could weaken it);
    - candidates are the contract's ACCEPTED offers first (same
      contract, failover within the accepted composition), then the
      remaining LIVE advertised offers in the exchange (an M008-era
      replan may consider newly advertised material — but only the
      canonical command surface could ever bind it, and binding
      happens under the UNCHANGED constraint set);
    - any candidate that evaluates present-and-violating on any
      dimension is REJECTED with the trail; if no candidate remains,
      the decision is a rejection trail (fail-closed — the caller
      fails the contract, never weakens the constraints).

    The engine returns :class:`FailoverDecision` (the value form);
    :meth:`require_failover` is the raising form for callers that
    need a typed failure when no plan is possible.
    """

    def replan(
        self,
        *,
        contract: ConnectivityContract,
        exchange: OfferExchange,
        failed_provider: str,
        schedule: FailureSchedule,
        at_instant: str,
    ) -> FailoverDecision:
        if not isinstance(contract, ConnectivityContract):
            raise ShareNetError(
                REASON_INVALID_INPUT,
                "replan requires a contracts.ConnectivityContract",
            )
        if not isinstance(exchange, OfferExchange):
            raise ShareNetError(
                REASON_INVALID_INPUT,
                "replan requires an offers.OfferExchange",
            )
        constraints = contract.hard_constraints
        snapshot_before = _constraint_snapshot(contract)
        rejections: List[CandidateRejection] = []
        plan: Optional[PlanSegment] = None

        accepted_ids = tuple(
            ref.value for ref in contract.accepted_offers if ref.ref_kind == "offer"
        )
        accepted_offers = tuple(
            exchange.offer(offer_id) for offer_id in sorted(accepted_ids)
        )
        other_live = tuple(
            offer
            for offer in exchange.offers()
            if offer.offer_id not in accepted_ids
        )
        # deterministic candidate order: accepted (sorted) then other
        # live advertised offers (the exchange's sorted order)
        candidates = accepted_offers + other_live
        for index, offer in enumerate(candidates):
            if offer.provider == failed_provider:
                rejections.append(
                    CandidateRejection(
                        provider=offer.provider,
                        offer_id=offer.offer_id,
                        violated=(),
                        detail="failed-realization:provider-down",
                    )
                )
                continue
            evaluation = evaluate_offer_against_constraints(offer, constraints)
            if evaluation.violated:
                rejections.append(
                    CandidateRejection(
                        provider=offer.provider,
                        offer_id=offer.offer_id,
                        violated=evaluation.violated,
                        detail="lock-108:hard-constraint-violation:%s"
                        % "+".join(sorted(evaluation.violated)),
                    )
                )
                continue
            plan = PlanSegment(
                provider=offer.provider,
                offer_id=offer.offer_id,
                artifact_token="m008-seam:failover:%s:seg-%d"
                % (offer.provider, index + 1),
                role="failover",
            )
            break
        snapshot_after = _constraint_snapshot(contract)
        return FailoverDecision(
            plan=plan,
            rejections=tuple(rejections),
            constraints_before=snapshot_before,
            constraints_after=snapshot_after,
            weakened=snapshot_before != snapshot_after,
        )

    def require_failover(
        self,
        *,
        contract: ConnectivityContract,
        exchange: OfferExchange,
        failed_provider: str,
        schedule: FailureSchedule,
        at_instant: str,
    ) -> PlanSegment:
        """The raising form: a plan or a typed fail-closed error
        (never a weakened constraint, never a silent pass)."""
        decision = self.replan(
            contract=contract,
            exchange=exchange,
            failed_provider=failed_provider,
            schedule=schedule,
            at_instant=at_instant,
        )
        if decision.plan is not None:
            return decision.plan
        raise ShareNetError(
            REASON_FAIL_CLOSED,
            "lock-108 fail-closed: no failover candidate satisfies the "
            "UNCHANGED hard constraints (rejections: %s)"
            % "; ".join(
                "%s/%s %s" % (entry.provider, entry.offer_id[:24], entry.detail)
                for entry in decision.rejections
            ),
        )


# ----------------------------------------------------------------------
# Seam: M009 — usage and commercial reconciliation (step 8)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class UsageObservation:
    """One usage observation (M009 seam output): pure DATA — the
    observed usage scalars plus the settlement REFERENCE read
    opaquely from the contract's usage-pricing-terms (LOCK-113: the
    money movement stays external; the seam moves no money)."""

    contract_id: str
    recorded_at: str
    bytes_transferred: int
    active_seconds: int
    settlement_reference: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "recorded_at": self.recorded_at,
            "bytes_transferred": self.bytes_transferred,
            "active_seconds": self.active_seconds,
            "settlement_reference": self.settlement_reference,
        }


class UsageObservationSeam:
    """The M009 stand-in: deterministic usage observation for one
    contract.  The observed scalars are caller-injected (the harness
    scripts them; no measurement, no wall clock); the settlement
    reference is read from the contract's opaque usage-pricing-terms
    reference — referenced, never interpreted."""

    def observe(
        self,
        *,
        contract: ConnectivityContract,
        bytes_transferred: int,
        active_seconds: int,
        recorded_at: str,
    ) -> UsageObservation:
        if not isinstance(contract, ConnectivityContract):
            raise ShareNetError(
                REASON_INVALID_INPUT,
                "observe requires a contracts.ConnectivityContract",
            )
        if bytes_transferred < 0 or active_seconds < 0:
            raise ShareNetError(
                REASON_INVALID_INPUT,
                "usage scalars must be non-negative",
            )
        terms = contract.usage_pricing_terms
        settlement_reference = (
            terms.value if terms is not None else "settlement:external"
        )
        return UsageObservation(
            contract_id=contract.contract_id,
            recorded_at=recorded_at,
            bytes_transferred=bytes_transferred,
            active_seconds=active_seconds,
            settlement_reference=settlement_reference,
        )


__all__ = [
    "AssuranceSeam",
    "CandidateRejection",
    "ConstraintEvaluation",
    "EligibilityDecision",
    "EligibilitySeam",
    "ExecutionPlanSeam",
    "FailureSchedule",
    "FailoverDecision",
    "PlanSegment",
    "ProviderRealizationSeam",
    "REALIZATION_EVENT_KINDS",
    "RealizationEvent",
    "ReplanEngine",
    "SEAM_IDS",
    "SIMULATION_SEAMS",
    "SeamDisclosure",
    "SimulatedExecutionPlan",
    "UsageObservation",
    "UsageObservationSeam",
    "evaluate_constraint",
    "evaluate_offer_against_constraints",
]
