"""The M012 deterministic simulation seams (the disclosed NOT-YET-
DELIVERED mechanics of the frozen COMOS flow).

The frozen 6-step COMOS flow
(``spec/integration/vertical-proof.md``, ACR-014 FROZEN) routes
through mechanics owned by R7 children that are NOT yet accepted:

- step 2 (ADCOS selects suitable offers) needs M004 (Eligibility
  and Policy) — the constraint-aware selection evaluation;
- step 5 (ADCOS supplies connectivity execution) needs M006
  (Execution Plan) — the LOCK-109 bridge from contract to
  provider mechanisms; M007 (Provider/Standard Adapters) — the
  realization plane that delivers the communication traffic and
  reports delivered facts; and M005 (Evidence and Assurance) —
  the assurance observation of the realized connectivity.

NONE of those children is delivered at this head.  This module
therefore provides FOUR clearly-labeled deterministic SIMULATION
SEAMS — one per pending mechanic — so the vertical proof can
compose the flow end-to-end TODAY without ever pretending the
real children exist:

    SEAM != AUTHORITY.  Every seam is deterministic (injected
    instants, injected schedules, no randomness, no wall clock,
    no network, no secrets — LOCK-119), produces DATA only, and
    NEVER mutates the canonical contract.  Canonical mutations
    always go through the real ``ContractStore`` command surface.
    The seam registry (:data:`SIMULATION_SEAMS`) is the single
    disclosure point: every seam declares the M-item it stands in
    for and that the M-item is PENDING DELIVERY.

M008 (Replan and Failover) has NO step in the frozen 6-step
COMOS flow (the flow carries no degradation/failure/replan step
— that is the ShareNet flow's material).  It is therefore NOT
represented by a seam here: there is no M008 mechanic for the
COMOS vertical to double, and the pending M008 child is never
composed, never exercised, and never claimed (disclosed in
``docs/M012-evidence.md``).

The M009 mechanics (usage evidence attribution and the
commercial-terms surface) are NOT seams either: M009 is ACCEPTED
(DEC-0109) and the harness composes the REAL ``usage`` ledger
and the REAL ``commercial`` core (bound mode) as authorities.

The constraint kernel (:func:`evaluate_constraint` /
:func:`evaluate_offer_against_constraints` /
:func:`evaluate_requirements_against_commitments`) is the
LOCK-108/LOCK-102 heart of the harness: it evaluates an offer's
explicit bounded commitments — and the COMOS application's
technology-neutral communication requirements — against a
contract's hard constraints UNCHANGED, returning True (satisfied)
/ False (present-and-violating — the rejection trail) / None
(dimension uncommitted — no information, neither satisfied nor
violated).  A present-and-violating evaluation rejects the
candidate fail-closed; an uncommitted dimension abstains and is
disclosed, never converted into a pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

from contracts import (
    ConnectivityContract,
    HardConstraint,
    OpaqueReference,
    Provenance,
)
from offers import OfferExchange, OfferRecord

from .application import ComosError, REASON_FAIL_CLOSED, REASON_INVALID_INPUT

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


#: The frozen seam registry (FOUR seams; the disclosure the evidence
#: doc and the battery both re-assert).  Every entry names a PENDING
#: M-item — if any of these children is ACCEPTED, the seam is no
#: longer the stand-in and must be re-composed (fail-loud by review,
#: not silently).  M008 (replan/failover) is deliberately ABSENT:
#: the frozen 6-step COMOS flow carries no replan step (disclosed
#: in docs/M012-evidence.md).
SIMULATION_SEAMS: Tuple[SeamDisclosure, ...] = (
    SeamDisclosure(
        seam_id="seam:m004-selection",
        stands_in_for="M004 — Eligibility and Policy (constraint-aware selection)",
        authority_status=(
            "PENDING DELIVERY: deterministic simulation seam; the M004 "
            "eligibility/policy authority does not exist at this head"
        ),
        exported_symbol="comos.seams.SelectionSeam",
    ),
    SeamDisclosure(
        seam_id="seam:m005-assurance",
        stands_in_for="M005 — Evidence and Assurance",
        authority_status=(
            "PENDING DELIVERY: deterministic simulation seam; the M005 "
            "evidence/assurance authority does not exist at this head"
        ),
        exported_symbol="comos.seams.AssuranceSeam",
    ),
    SeamDisclosure(
        seam_id="seam:m006-execution-plan",
        stands_in_for="M006 — Execution Plan",
        authority_status=(
            "PENDING DELIVERY: deterministic simulation seam; the M006 "
            "execution-plan bridge (LOCK-109) does not exist at this head"
        ),
        exported_symbol="comos.seams.ExecutionPlanSeam",
    ),
    SeamDisclosure(
        seam_id="seam:m007-realization",
        stands_in_for="M007 — Provider/Standard Adapters (realization plane)",
        authority_status=(
            "PENDING DELIVERY: deterministic simulation seam; the M007 "
            "provider realization plane does not exist at this head"
        ),
        exported_symbol="comos.seams.ProviderRealizationSeam",
    ),
)

SEAM_IDS: Tuple[str, ...] = tuple(entry.seam_id for entry in SIMULATION_SEAMS)


# ----------------------------------------------------------------------
# The constraint kernel (LOCK-108/LOCK-102: hard constraints and
# communication requirements evaluated UNCHANGED — never weakened,
# never reinterpreted)
# ----------------------------------------------------------------------

#: The frozen mapping from contract hard-constraint kinds (and the
#: COMOS requirement dimensions) to the offer commitment kinds that
#: speak to the same dimension (the M002 <-> M003 vocabulary pairs).
_CONSTRAINT_TO_COMMITMENT: Dict[str, str] = {
    "latency-bound": "latency-bound-ms",
    "throughput-floor": "throughput-floor-kbps",
    "availability-floor": "availability-floor-nine",
    "loss-bound": "loss-bound-pct",
    "jitter-bound": "jitter-bound-ms",
    "capacity-floor": "capacity-floor-kbps",
}

#: How each dimension compares a bound against a commitment value
#: ("upper" = commitment must be <= bound; "floor" = commitment must
#: be >= bound).
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

#: The frozen constraint/requirement bound parameter name per
#: constraint kind (the family convention: ms / bps / pct / nines
#: scalars).
_CONSTRAINT_PARAM: Dict[str, str] = {
    "latency-bound": "ms",
    "throughput-floor": "bps",
    "availability-floor": "nines",
    "loss-bound": "pct",
    "jitter-bound": "ms",
    "capacity-floor": "bps",
}

#: The frozen mapping from the COMOS requirement-dimension names
#: (the step-4 submission vocabulary) to the contract constraint
#: kinds of the same dimension (the requirement envelope speaks the
#: same dimension families as the contract's hard constraints).
_REQUIREMENT_TO_CONSTRAINT: Dict[str, str] = {
    "latency_bound_ms": "latency-bound",
    "jitter_bound_ms": "jitter-bound",
    "throughput_floor_bps": "throughput-floor",
    "availability_floor_nines": "availability-floor",
    "loss_bound_pct": "loss-bound",
}

#: The frozen bound parameter name per requirement dimension (the
#: step-4 document's scalar members).
_REQUIREMENT_PARAM: Dict[str, str] = {
    "latency_bound_ms": "ms",
    "jitter_bound_ms": "ms",
    "throughput_floor_bps": "bps",
    "availability_floor_nines": "nines",
    "loss_bound_pct": "pct",
}


def _commitment_value(
    offer: OfferRecord, commitment_kind: str, param_name: str
) -> Optional[int]:
    """The scalar commitment value an offer carries on one dimension
    (None when the offer commits nothing on it)."""
    values: List[int] = []
    for commitment in offer.commitments:
        if commitment.kind != commitment_kind:
            continue
        value = commitment.params.get(param_name)
        if value is not None:
            values.append(value)
    if not values:
        return None
    return values[0]


def evaluate_constraint(
    constraint: HardConstraint, offer: OfferRecord
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
        raise ComosError(
            REASON_INVALID_INPUT,
            "evaluate_constraint requires a contracts.HardConstraint",
        )
    if not isinstance(offer, OfferRecord):
        raise ComosError(
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
    bound = constraint.params.get(_CONSTRAINT_PARAM.get(constraint.kind, ""))
    if bound is None:
        # the constraint is dimension-kind without its bound:
        # nothing to enforce (kernel abstains)
        return None
    value = _commitment_value(offer, expected_kind, param_name)
    if value is None:
        # the offer commits nothing on the dimension: no information
        return None
    satisfied = value <= bound if sense == "upper" else value >= bound
    return satisfied


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


@dataclass(frozen=True)
class RequirementVerdict:
    """One requirement dimension's verdict against one offer's
    committed terms (the step-4 evaluation trail)."""

    dimension: str
    constraint_kind: str
    committed_value: Optional[int]
    required_bound: int
    verdict: Optional[bool]


@dataclass(frozen=True)
class RequirementsEvaluation:
    """The deterministic evaluation of the COMOS communication
    requirements against one offer's explicit bounded commitments
    (the step-4 satisfaction trail: satisfied, violated, and
    uncommitted dimensions)."""

    offer_id: str
    verdicts: Tuple[RequirementVerdict, ...]

    @property
    def satisfied(self) -> Tuple[str, ...]:
        return tuple(
            verdict.dimension
            for verdict in self.verdicts
            if verdict.verdict is True
        )

    @property
    def violated(self) -> Tuple[str, ...]:
        return tuple(
            verdict.dimension
            for verdict in self.verdicts
            if verdict.verdict is False
        )

    @property
    def uncommitted(self) -> Tuple[str, ...]:
        return tuple(
            verdict.dimension
            for verdict in self.verdicts
            if verdict.verdict is None
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "offer_id": self.offer_id,
            "satisfied": list(self.satisfied),
            "violated": list(self.violated),
            "uncommitted": list(self.uncommitted),
            "verdicts": [
                {
                    "dimension": verdict.dimension,
                    "constraint_kind": verdict.constraint_kind,
                    "committed_value": verdict.committed_value,
                    "required_bound": verdict.required_bound,
                    "verdict": verdict.verdict,
                }
                for verdict in self.verdicts
            ],
        }


def evaluate_requirements_against_offer(
    *,
    requirements: Mapping[str, Any],
    offer: OfferRecord,
) -> RequirementsEvaluation:
    """Evaluate the step-4 technology-neutral communication
    requirements against ONE offer's explicit bounded commitments.

    The requirement document's scalar bounds are compared against
    the offer's commitments dimension-by-dimension with the same
    True/False/None kernel semantics (present-and-violating is a
    violation; uncommitted abstains).  Requirements NEVER mutate
    the contract — this is an evaluation, not a command.
    """
    if not isinstance(offer, OfferRecord):
        raise ComosError(
            REASON_INVALID_INPUT,
            "evaluate_requirements_against_offer requires an "
            "offers.OfferRecord",
        )
    verdicts: List[RequirementVerdict] = []
    for dimension in sorted(requirements):
        if dimension not in _REQUIREMENT_TO_CONSTRAINT:
            continue
        constraint_kind = _REQUIREMENT_TO_CONSTRAINT[dimension]
        expected_kind = _CONSTRAINT_TO_COMMITMENT[constraint_kind]
        param_name = _COMMITMENT_PARAM[expected_kind]
        sense = _DIMENSION_SENSE[constraint_kind]
        required_bound = requirements[dimension]
        if isinstance(required_bound, bool) or not isinstance(
            required_bound, int
        ):
            raise ComosError(
                REASON_INVALID_INPUT,
                "requirement dimension %r must carry an integer scalar "
                "bound" % dimension,
            )
        committed = _commitment_value(offer, expected_kind, param_name)
        if committed is None:
            verdict: Optional[bool] = None
        else:
            verdict = (
                committed <= required_bound
                if sense == "upper"
                else committed >= required_bound
            )
        verdicts.append(
            RequirementVerdict(
                dimension=dimension,
                constraint_kind=constraint_kind,
                committed_value=committed,
                required_bound=required_bound,
                verdict=verdict,
            )
        )
    return RequirementsEvaluation(
        offer_id=offer.offer_id, verdicts=tuple(verdicts)
    )


# ----------------------------------------------------------------------
# Seam: M004 — constraint-aware selection (step 2)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class CandidateDecision:
    """One offer's selection decision (M004 seam output: DATA with
    the full evaluation trail; never a contract mutation)."""

    offer_id: str
    provider: str
    selected: bool
    evaluation: ConstraintEvaluation
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "offer_id": self.offer_id,
            "provider": self.provider,
            "selected": self.selected,
            "satisfied": list(self.evaluation.satisfied),
            "violated": list(self.evaluation.violated),
            "uncommitted": list(self.evaluation.uncommitted),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class SelectionDecision:
    """The ADCOS-side selection outcome for one scenario (step 2's
    proof artifact): the SELECTED offer set plus the per-candidate
    rejection trail, all deterministic DATA."""

    decisions: Tuple[CandidateDecision, ...]

    @property
    def selected_ids(self) -> Tuple[str, ...]:
        return tuple(
            decision.offer_id
            for decision in self.decisions
            if decision.selected
        )

    @property
    def rejected_ids(self) -> Tuple[str, ...]:
        return tuple(
            decision.offer_id
            for decision in self.decisions
            if not decision.selected
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "selected": list(self.selected_ids),
            "rejected": list(self.rejected_ids),
            "candidates": [
                decision.to_dict() for decision in self.decisions
            ],
        }


class SelectionSeam:
    """The M004 stand-in: deterministic constraint-aware selection
    over the REAL offer records and the REAL contract hard
    constraints (frozen flow step 2: "ADCOS selects suitable
    offers").

    Fail-closed rule (LOCK-108 adjacent): an offer is NOT SELECTED
    iff any evaluated dimension is present-and-violating, or the
    offer carries no provenance decision refs (LOCK-118: an
    un-provenanced offer is unsuitable — evidence sufficiency).
    Uncommitted dimensions abstain (the selection does not convert
    absent evidence into suitability or unsuitability — the
    M005-era evidence-honesty discipline).  When NO offer is
    suitable, the decision carries zero selected ids and the
    caller fail-closes (never a weakened constraint).
    """

    def evaluate(
        self,
        *,
        offer: OfferRecord,
        constraints: Tuple[HardConstraint, ...],
        at_instant: str,
    ) -> CandidateDecision:
        evaluation = evaluate_offer_against_constraints(offer, constraints)
        if evaluation.violated:
            return CandidateDecision(
                offer_id=offer.offer_id,
                provider=offer.provider,
                selected=False,
                evaluation=evaluation,
                reason="hard-constraint-violation:%s"
                % "+".join(sorted(evaluation.violated)),
            )
        if not offer.provenance.decision_refs:
            return CandidateDecision(
                offer_id=offer.offer_id,
                provider=offer.provider,
                selected=False,
                evaluation=evaluation,
                reason="insufficient-evidence:no-decision-refs",
            )
        return CandidateDecision(
            offer_id=offer.offer_id,
            provider=offer.provider,
            selected=True,
            evaluation=evaluation,
            reason="suitable:%d-dimensions-satisfied+%d-abstain"
            % (len(evaluation.satisfied), len(evaluation.uncommitted)),
        )

    def select(
        self,
        *,
        offers: Tuple[OfferRecord, ...],
        constraints: Tuple[HardConstraint, ...],
        at_instant: str,
    ) -> SelectionDecision:
        """Evaluate every advertised candidate (deterministic
        order: the exchange's sorted order)."""
        return SelectionDecision(
            decisions=tuple(
                self.evaluate(
                    offer=offer,
                    constraints=constraints,
                    at_instant=at_instant,
                )
                for offer in offers
            )
        )


# ----------------------------------------------------------------------
# Seam: M005 — evidence and assurance (step 5)
# ----------------------------------------------------------------------


class AssuranceSeam:
    """The M005 stand-in: deterministic assurance observation of one
    realization against the contract's assurance obligations.

    The observation state vocabulary is the canonical one
    (``compliant`` / ``degraded`` / ``violated`` / ``unknown-stale``);
    the seam derives the state from the realization status the M007
    seam reports, and always emits an evidence token (the M005
    evidence typing: an assurance evaluation is an OBSERVATION,
    never a claim or an attestation).
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
            raise ComosError(
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
    provider, the grounding offer id, the artifact token to bind
    as contract DATA, and the correlation tokens the commercial
    walk cites — LOCK-109's bridge, simulated)."""

    provider: str
    offer_id: str
    artifact_token: str
    session_token: str
    path_token: str
    role: str  # "primary" | "secondary"

    def artifact_reference(self) -> OpaqueReference:
        """The opaque execution-artifact reference for this segment
        (LOCK-117: an artifact binds as DATA, never authority)."""
        return OpaqueReference(
            ref_kind="execution-artifact",
            value=self.artifact_token,
            provenance=Provenance(
                issuer="m006-seam:execution-plan",
                decision_refs=("comos:plan:%s" % self.role,),
            ),
        )


@dataclass(frozen=True)
class SimulatedExecutionPlan:
    """The simulated contract-to-mechanisms translation (M006 seam
    output): segments in deterministic (provider, offer id) order."""

    segments: Tuple[PlanSegment, ...]


class ExecutionPlanSeam:
    """The M006 stand-in: translate a contract into a simulated
    execution plan over its ACCEPTED offers (LOCK-109: the plan is
    the bridge from contract to provider mechanisms; here the
    mechanisms are simulated, the contract is real and read-only).

    The primary segment is the first accepted offer in deterministic
    (provider, offer id) order; every further accepted offer becomes
    a secondary segment (LOCK-116: multiple providers may compose
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
            raise ComosError(
                REASON_INVALID_INPUT,
                "build_plan requires a contracts.ConnectivityContract",
            )
        if not isinstance(exchange, OfferExchange):
            raise ComosError(
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
            role = "primary" if position == 0 else "secondary"
            segments.append(
                PlanSegment(
                    provider=offer.provider,
                    offer_id=offer.offer_id,
                    artifact_token="m006-seam:realization:%s:seg-%d"
                    % (role, position + 1),
                    session_token="m007-seam:gateway-session:seg-%d"
                    % (position + 1,),
                    path_token="m006-seam:plan-segment:seg-%d"
                    % (position + 1,),
                    role=role,
                )
            )
        if not segments:
            raise ComosError(
                REASON_FAIL_CLOSED,
                "the contract carries no accepted offer references; an "
                "execution plan cannot be built (fail-closed)",
            )
        return SimulatedExecutionPlan(segments=tuple(segments))


# ----------------------------------------------------------------------
# Seam: M007 — provider realization and delivered facts (step 5)
# ----------------------------------------------------------------------

#: The deterministic realization-event kinds the injected schedule
#: may script (the frozen COMOS flow scripts a HEALTHY delivery —
#: its steps carry no degradation/failure; the vocabulary exists
#: so the schedule type stays honest about what it can express).
REALIZATION_EVENT_KINDS: Tuple[str, ...] = ("degraded", "failed")


@dataclass(frozen=True)
class RealizationEvent:
    """One scripted realization event (deterministic, injected): the
    provider whose realization changes, the kind of change, the
    instant it becomes effective, and a detail token.  The golden
    COMOS scenarios script NO events (a healthy delivery)."""

    provider: str
    kind: str
    effective_at: str
    detail: str

    def __post_init__(self) -> None:
        if self.kind not in REALIZATION_EVENT_KINDS:
            raise ComosError(
                REASON_INVALID_INPUT,
                "realization event kind %r is outside the frozen schedule "
                "vocabulary %s" % (self.kind, list(REALIZATION_EVENT_KINDS)),
            )


@dataclass(frozen=True)
class FailureSchedule:
    """The injected deterministic realization schedule (LOCK-119: no
    randomness anywhere — realization changes are SCRIPTED, and the
    same schedule reproduces the same vertical byte-for-byte)."""

    events: Tuple[RealizationEvent, ...] = ()


@dataclass(frozen=True)
class DeliveredFact:
    """One delivered-traffic fact the realization plane reports
    (M007 seam output: the DATA the real M009 usage authority's
    evidence index is built from — quantity in canonical units,
    bounded by an injected window; pure DATA, never a contract
    mutation, never authority)."""

    evidence_id: str
    provider: str
    segment_token: str
    delivered_quantity: int
    window_start: str
    window_end: str


class ProviderRealizationSeam:
    """The M007-adjacent stand-in: the simulated provider
    realization plane.  Each segment's realization status at an
    instant is a pure function of the injected schedule (healthy
    until a scripted event takes effect); the delivered facts are
    caller-injected quantities over injected windows (the harness
    scripts them; no measurement, no wall clock)."""

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

    def delivered_facts(
        self,
        *,
        segments: Tuple[PlanSegment, ...],
        quantities: Tuple[int, ...],
        windows: Tuple[Tuple[str, str], ...],
    ) -> Tuple[DeliveredFact, ...]:
        """The delivered-traffic facts for the planned segments (one
        per (segment, quantity, window) triple, deterministic
        order).  These facts feed the REAL M009 usage evidence
        index — the seam produces DATA, the authority admits it."""
        if len(quantities) != len(windows):
            raise ComosError(
                REASON_INVALID_INPUT,
                "delivered_facts requires matching quantities and windows",
            )
        if len(quantities) > len(segments) or not quantities:
            raise ComosError(
                REASON_INVALID_INPUT,
                "delivered_facts requires at least one fact and at most "
                "one per planned segment",
            )
        facts: List[DeliveredFact] = []
        for index, (quantity, (start, end)) in enumerate(
            zip(quantities, windows)
        ):
            if quantity < 1:
                raise ComosError(
                    REASON_INVALID_INPUT,
                    "delivered facts carry non-empty delivered quantities",
                )
            segment = segments[index]
            facts.append(
                DeliveredFact(
                    evidence_id="m007-seam:delivered:%s:fact-%d"
                    % (segment.role, index + 1),
                    provider=segment.provider,
                    segment_token=segment.artifact_token,
                    delivered_quantity=quantity,
                    window_start=start,
                    window_end=end,
                )
            )
        return tuple(facts)


__all__ = [
    "AssuranceSeam",
    "CandidateDecision",
    "ConstraintEvaluation",
    "DeliveredFact",
    "ExecutionPlanSeam",
    "FailureSchedule",
    "PlanSegment",
    "ProviderRealizationSeam",
    "REALIZATION_EVENT_KINDS",
    "RealizationEvent",
    "RequirementsEvaluation",
    "RequirementVerdict",
    "SEAM_IDS",
    "SIMULATION_SEAMS",
    "SelectionDecision",
    "SelectionSeam",
    "SeamDisclosure",
    "SimulatedExecutionPlan",
    "evaluate_constraint",
    "evaluate_offer_against_constraints",
    "evaluate_requirements_against_offer",
]
