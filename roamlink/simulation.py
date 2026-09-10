"""The M011 DETERMINISTIC SIMULATION SEAMS (R7-CORE-001 child
M011, DEC-0101).

*** SIMULATION SEAMS -- NOT DELIVERED CHILDREN ***

The RoamLink vertical proof composes the ACCEPTED canonical
domains as real authority (contracts/ M002, offers/ M003,
commercial/ + usage/ M009, developerapi/ M013).  The
NOT-YET-ACCEPTED children's mechanics are represented here as
DETERMINISTIC TEST DOUBLES of their FUTURE domains:

- ``M004_SIMULATION`` -- the eligibility/policy evaluation
  double (:class:`SimulatedPolicyGate`): a deterministic
  constraint-matching verdict over the exposed offers.
- ``M005_SIMULATION`` -- the evidence/assurance evaluation
  double (:class:`SimulatedAssuranceEvaluator`): deterministic
  assurance verdicts in the frozen contracts.ASSURANCE_STATES
  vocabulary, feeding the REAL ``RecordAssurance`` command.
- ``M006_SIMULATION`` -- the execution-plan double
  (:class:`SimulatedExecutionPlanner`): deterministic segments
  under the contract's permitted execution scope.
- ``M007_SIMULATION`` -- the realization/adapter double
  (:class:`SimulatedRealization`/:class:`SimulatedSegment`):
  provider-scoped segment realizations that ride the REAL
  ``BindExecutionArtifact`` command as opaque execution-artifact
  references (LOCK-117: data, never authority).
- ``M008_SIMULATION`` -- the replan/failover double
  (:class:`SimulatedReplanner`): the provider-change absorption
  path.  LOCK-108 is enforced INSIDE the seam: a realization
  that violates any hard constraint of the contract can never
  be bound (fail closed CONSTRAINT_VIOLATION); the only honest
  outcomes are absorption behind the unchanged contract or an
  EXPLICIT unrecoverable verdict (the caller then fails or
  renegotiates the contract -- never a silent weakening).

Every seam-produced reference carries its seam label as the
provenance issuer (``simulation-seam:m0XX-...``) so no composed
surface can mistake seam material for a delivered child's
authority material.  The seams never import the pending
children's real domains (policy/, eligibility/, telemetry/,
executionplans/, composition/, adapters/, sessions/,
mobility/, multipath/, replan/) -- their mechanics are
simulated here, and the real children are NOT claimed as
delivered anywhere in this package.

The provider world (advertisements, offers, commercial terms)
is REAL M003 material: records built through the accepted
``offers`` builders and registered in a real
``OfferExchange``.  The deterministic provider-change
injection (:class:`ProviderChange`) is vertical-battery
fixture DATA: the change events are injected at fixed instants
(never observed from the outside world).

Determinism: injected instants only, no wall clock, no
randomness, no UUIDs, no network, content-derived ids over
canonical JSON, sorted iteration everywhere, fail-closed typed
errors.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from protocol.canonicalization import canonical_json_bytes

from contracts import (
    ASSURANCE_STATES,
    ConnectivityContract,
    HardConstraint,
    OpaqueReference,
    Provenance,
)
from offers import (
    AdvertisementEntry,
    AdvertisementRef,
    CapabilityAdvertisement,
    OfferCommitment,
    OfferExchange,
    OfferPricing,
    OfferRecord,
    ServiceBoundary,
    build_advertisement,
    build_offer,
)

from .errors import RoamLinkError, RoamLinkReason

#: The frozen simulation-seam registry: every pending child
#: represented in the harness, with its label.  This registry IS
#: the composition disclosure -- the battery pins it exactly.
SIMULATION_SEAMS: Tuple[Tuple[str, str], ...] = (
    ("M004", "simulation-seam:m004-eligibility-policy"),
    ("M005", "simulation-seam:m005-evidence-assurance"),
    ("M006", "simulation-seam:m006-execution-plan"),
    ("M007", "simulation-seam:m007-realization-adapter"),
    ("M008", "simulation-seam:m008-replan-failover"),
)

#: The accepted canonical domains composed as REAL authority
#: (the composition map's authority half).
AUTHORITY_DOMAINS: Tuple[Tuple[str, str], ...] = (
    ("M002", "contracts"),
    ("M003", "offers"),
    ("M009", "commercial+usage"),
    ("M013", "developerapi"),
)

#: The frozen provider-change vocabulary (the deterministic
#: injection kinds).
PROVIDER_CHANGE_KINDS: Tuple[str, ...] = (
    "offer-superseded",
    "offer-withdrawn",
    "realization-degraded",
    "realization-failed",
)

#: The frozen simulated-realization state vocabulary.
REALIZATION_STATES: Tuple[str, ...] = ("planned", "active", "degraded", "failed")

#: The frozen simulated observation states (what the assurance
#: seam observes about a realization; mapped onto the frozen
#: contracts ASSURANCE_STATES vocabulary).
OBSERVATION_STATES: Tuple[str, ...] = (
    "nominal",
    "degraded-realization",
    "violated-realization",
)


def _seam_label(child: str) -> str:
    for key, label in SIMULATION_SEAMS:
        if key == child:
            return label
    raise RoamLinkError(
        RoamLinkReason.SEAM_MISUSED,
        "no simulation seam is registered for %r (the seam registry "
        "is the composition disclosure; fail closed)" % (child,),
    )


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise RoamLinkError(
            RoamLinkReason.INVALID_INPUT,
            "%s must be a non-empty string" % label,
        )
    return value


# ---------------------------------------------------------------------------
# The provider world (REAL M003 material: advertisements, offers,
# commercial terms -- built through the accepted public builders)
# ---------------------------------------------------------------------------


def _digest(document: Mapping[str, Any], label: str) -> str:
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes(dict(document))
    ).hexdigest()


@dataclass(frozen=True)
class ProviderWorld:
    """The deterministic two-provider world of the vertical
    proof: REAL capability advertisements + REAL offers (with
    explicit bounded commitments, integer-minor-unit pricing and
    declared service boundaries) registered in a REAL
    ``OfferExchange``.

    The providers are fixture NodeID-shaped domain identities
    (the M003 battery's provider grammar); their behavior (the
    deterministic change injection) is vertical-battery fixture
    DATA, clearly labeled."""

    provider_a: str
    provider_b: str
    exchange: OfferExchange
    advertisement_a: CapabilityAdvertisement
    advertisement_b: CapabilityAdvertisement
    offer_a_v1: OfferRecord
    offer_b_v1: OfferRecord


def build_provider_world(
    *,
    provider_a: str,
    provider_b: str,
    validity: Tuple[str, str],
    issuer_a: str = "provider:roamlink-netpro-a",
    issuer_b: str = "provider:roamlink-netpro-b",
) -> ProviderWorld:
    """Build the two-provider world over the accepted M003
    builders (deterministic, offline, seeded by the fixed
    fixture values)."""
    not_before, not_after = validity

    def prov(issuer: str) -> Provenance:
        return Provenance(issuer=issuer, decision_refs=("roamlink-vertical",))

    advertisement_a = build_advertisement(
        provider=provider_a,
        entries=(
            AdvertisementEntry(
                capability_id="capability.core.ip-data-cohort",
                schema_version="1.2",
                statement_digest=_digest(
                    {"capability": "ip-data-cohort", "provider": provider_a},
                    "statement-a",
                ),
                classification="known",
            ),
        ),
        validity=_interval(not_before, not_after),
        provenance=prov(issuer_a),
    )
    advertisement_b = build_advertisement(
        provider=provider_b,
        entries=(
            AdvertisementEntry(
                capability_id="capability.core.ip-data-cohort",
                schema_version="1.2",
                statement_digest=_digest(
                    {"capability": "ip-data-cohort", "provider": provider_b},
                    "statement-b",
                ),
                classification="known",
            ),
        ),
        validity=_interval(not_before, not_after),
        provenance=prov(issuer_b),
    )
    offer_a_v1 = build_offer(
        provider=provider_a,
        provider_offer_key="roamlink:cohort-data-a",
        schema_version=1,
        advertisements=(
            AdvertisementRef(
                advertisement_id=advertisement_a.advertisement_id,
                provenance=prov(issuer_a),
            ),
        ),
        commitments=(
            OfferCommitment(
                kind="latency-bound-ms",
                params={"max_ms": 80},
                window=_interval(not_before, not_after),
                provenance=prov(issuer_a),
            ),
            OfferCommitment(
                kind="throughput-floor-kbps",
                params={"min_kbps": 5120},
                window=_interval(not_before, not_after),
                provenance=prov(issuer_a),
            ),
        ),
        pricing=OfferPricing(
            currency="USD",
            price_minor=250,
            price_exponent=2,
            billing_mode="per-megabyte",
            provenance=prov(issuer_a),
        ),
        service_boundaries=(
            ServiceBoundary(
                jurisdiction="GH",
                geography_refs=("mpcell:v1:coarse-50000m:12:-1",),
                provenance=prov(issuer_a),
            ),
        ),
        validity=_interval(not_before, not_after),
        provenance=prov(issuer_a),
    )
    offer_b_v1 = build_offer(
        provider=provider_b,
        provider_offer_key="roamlink:cohort-data-b",
        schema_version=1,
        advertisements=(
            AdvertisementRef(
                advertisement_id=advertisement_b.advertisement_id,
                provenance=prov(issuer_b),
            ),
        ),
        commitments=(
            OfferCommitment(
                kind="latency-bound-ms",
                params={"max_ms": 95},
                window=_interval(not_before, not_after),
                provenance=prov(issuer_b),
            ),
            OfferCommitment(
                kind="throughput-floor-kbps",
                params={"min_kbps": 4096},
                window=_interval(not_before, not_after),
                provenance=prov(issuer_b),
            ),
        ),
        pricing=OfferPricing(
            currency="USD",
            price_minor=190,
            price_exponent=2,
            billing_mode="per-megabyte",
            provenance=prov(issuer_b),
        ),
        service_boundaries=(
            ServiceBoundary(
                jurisdiction="GH",
                geography_refs=("mpcell:v1:coarse-50000m:12:-2",),
                provenance=prov(issuer_b),
            ),
        ),
        validity=_interval(not_before, not_after),
        provenance=prov(issuer_b),
    )
    exchange = OfferExchange()
    exchange.register_advertisement(advertisement_a)
    exchange.register_advertisement(advertisement_b)
    exchange.register_offer(offer_a_v1)
    exchange.register_offer(offer_b_v1)
    return ProviderWorld(
        provider_a=provider_a,
        provider_b=provider_b,
        exchange=exchange,
        advertisement_a=advertisement_a,
        advertisement_b=advertisement_b,
        offer_a_v1=offer_a_v1,
        offer_b_v1=offer_b_v1,
    )


def build_weakened_successor_offer(
    world: ProviderWorld,
    *,
    validity: Tuple[str, str],
    latency_ms: int,
    issuer: str = "provider:roamlink-netpro-a",
) -> OfferRecord:
    """Build provider A's v2 successor listing with WEAKENED
    commitments (the deterministic provider-change payload: the
    successor violates the contract's latency bound; registering
    it supersedes v1 in the exchange)."""
    not_before, not_after = validity

    def prov(issuer_name: str) -> Provenance:
        return Provenance(issuer=issuer_name, decision_refs=("roamlink-vertical",))

    return build_offer(
        provider=world.provider_a,
        provider_offer_key="roamlink:cohort-data-a",
        schema_version=2,
        advertisements=(
            AdvertisementRef(
                advertisement_id=world.advertisement_a.advertisement_id,
                provenance=prov(issuer),
            ),
        ),
        commitments=(
            OfferCommitment(
                kind="latency-bound-ms",
                params={"max_ms": latency_ms},
                window=_interval(not_before, not_after),
                provenance=prov(issuer),
            ),
            OfferCommitment(
                kind="throughput-floor-kbps",
                params={"min_kbps": 5120},
                window=_interval(not_before, not_after),
                provenance=prov(issuer),
            ),
        ),
        pricing=OfferPricing(
            currency="USD",
            price_minor=250,
            price_exponent=2,
            billing_mode="per-megabyte",
            provenance=prov(issuer),
        ),
        service_boundaries=(
            ServiceBoundary(
                jurisdiction="GH",
                geography_refs=("mpcell:v1:coarse-50000m:12:-1",),
                provenance=prov(issuer),
            ),
        ),
        validity=_interval(not_before, not_after),
        provenance=prov(issuer),
    )


def _interval(not_before: str, not_after: str):
    from contracts import ValidityInterval

    return ValidityInterval(not_before=not_before, not_after=not_after)


# ---------------------------------------------------------------------------
# The M004 seam: simulated eligibility/policy evaluation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SimulatedPolicyDecision:
    """The deterministic M004 double's verdict: eligible iff at
    least one exposed offer can satisfy every hard constraint of
    the cohort request (pure constraint matching; no policy
    semantics are claimed -- the real M004 child owns them)."""

    decision_id: str
    verdict: str
    eligible_offer_ids: Tuple[str, ...]
    evaluated_offer_ids: Tuple[str, ...]
    seam: str

    def __post_init__(self) -> None:
        if self.verdict not in ("eligible", "rejected"):
            raise RoamLinkError(
                RoamLinkReason.VOCABULARY,
                "policy verdict %r must be eligible or rejected" % (self.verdict,),
            )

    def decision_reference(self) -> OpaqueReference:
        """The typed ``decision`` reference the flow records
        (labeled with the seam issuer: simulation material,
        never a delivered child's authority material)."""
        return OpaqueReference(
            ref_kind="decision",
            value=self.decision_id,
            provenance=Provenance(issuer=self.seam),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "verdict": self.verdict,
            "eligible_offer_ids": list(self.eligible_offer_ids),
            "evaluated_offer_ids": list(self.evaluated_offer_ids),
            "seam": self.seam,
        }


class SimulatedPolicyGate:
    """The M004 simulation seam (eligibility/policy evaluation
    double).  Deterministic: a pure function of the request's
    hard constraints and the exposed offers' commitments.  FAILS
    CLOSED: no satisfiable offer -> verdict ``rejected``."""

    SEAM = _seam_label("M004")

    def evaluate(
        self,
        *,
        constraints: Sequence[HardConstraint],
        offers: Sequence[OfferRecord],
    ) -> SimulatedPolicyDecision:
        evaluated = tuple(sorted(offer.offer_id for offer in offers))
        eligible: List[str] = []
        for offer in sorted(offers, key=lambda o: o.offer_id):
            if _offer_satisfies(offer, constraints):
                eligible.append(offer.offer_id)
        verdict = "eligible" if eligible else "rejected"
        document = {
            "seam": self.SEAM,
            "verdict": verdict,
            "constraints": [c.to_dict() for c in constraints],
            "evaluated_offer_ids": list(evaluated),
            "eligible_offer_ids": sorted(eligible),
        }
        return SimulatedPolicyDecision(
            decision_id=_digest(document, "policy decision"),
            verdict=verdict,
            eligible_offer_ids=tuple(sorted(eligible)),
            evaluated_offer_ids=evaluated,
            seam=self.SEAM,
        )


def _offer_satisfies(offer: OfferRecord, constraints: Sequence[HardConstraint]) -> bool:
    """Deterministic constraint matching: every request
    constraint must be satisfied by the offer's commitment set
    (latency bound <= request max, throughput floor >= request
    min, geography included).  Fail closed on any miss or any
    unmatched constraint kind."""
    for constraint in constraints:
        kind = constraint.kind
        if kind == "latency-bound":
            bound = int(constraint.params.get("max_ms", 0))
            if not _commitment_within(offer, "latency-bound-ms", "max_ms", bound, "le"):
                return False
        elif kind == "throughput-floor":
            floor = int(constraint.params.get("min_kbps", 0))
            if not _commitment_within(
                offer, "throughput-floor-kbps", "min_kbps", floor, "ge"
            ):
                return False
        elif kind == "geography":
            wanted = str(constraint.params.get("region", ""))
            jurisdictions = tuple(
                boundary.jurisdiction for boundary in offer.service_boundaries
            )
            if wanted not in jurisdictions:
                return False
        else:
            # unknown-to-the-seam constraint kinds fail closed
            return False
    return True


def _commitment_within(
    offer: OfferRecord, kind: str, param: str, value: int, direction: str
) -> bool:
    for commitment in offer.commitments:
        if commitment.kind == kind:
            committed = int(commitment.params.get(param, 0))
            if direction == "le" and committed <= value:
                return True
            if direction == "ge" and committed >= value:
                return True
    return False


# ---------------------------------------------------------------------------
# The M005 seam: simulated evidence/assurance evaluation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SimulatedAssuranceEvaluation:
    """The deterministic M005 double's verdict: the observed
    realization state mapped onto the frozen
    ``contracts.ASSURANCE_STATES`` vocabulary, with the typed
    ``decision`` evidence references the REAL ``RecordAssurance``
    command requires."""

    decision_id: str
    assurance_state: str
    observed: str
    contract_id: str
    seam: str

    def __post_init__(self) -> None:
        if self.assurance_state not in ASSURANCE_STATES:
            raise RoamLinkError(
                RoamLinkReason.VOCABULARY,
                "assurance_state %r must be one of the frozen "
                "contracts.ASSURANCE_STATES vocabulary" % (self.assurance_state,),
            )

    def evidence_reference(self) -> OpaqueReference:
        return OpaqueReference(
            ref_kind="decision",
            value=self.decision_id,
            provenance=Provenance(issuer=self.seam),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "assurance_state": self.assurance_state,
            "observed": self.observed,
            "contract_id": self.contract_id,
            "seam": self.seam,
        }


class SimulatedAssuranceEvaluator:
    """The M005 simulation seam (evidence/assurance evaluation
    double).  Deterministic: the observed realization state maps
    one-to-one onto the frozen assurance vocabulary
    (nominal -> compliant, degraded-realization -> degraded,
    violated-realization -> violated).  The evaluation decision
    id is content-derived over the contract citation + the
    observed state (typed-reference attribution to the one
    contract)."""

    SEAM = _seam_label("M005")

    def evaluate(
        self, *, contract_id: str, observed: str
    ) -> SimulatedAssuranceEvaluation:
        if observed not in OBSERVATION_STATES:
            raise RoamLinkError(
                RoamLinkReason.VOCABULARY,
                "observed state %r must be one of %s"
                % (observed, list(OBSERVATION_STATES)),
            )
        mapping = {
            "nominal": "compliant",
            "degraded-realization": "degraded",
            "violated-realization": "violated",
        }
        document = {
            "seam": self.SEAM,
            "contract_id": contract_id,
            "observed": observed,
            "assurance_state": mapping[observed],
        }
        return SimulatedAssuranceEvaluation(
            decision_id=_digest(document, "assurance decision"),
            assurance_state=mapping[observed],
            observed=observed,
            contract_id=_require_text(contract_id, "contract id"),
            seam=self.SEAM,
        )


# ---------------------------------------------------------------------------
# The M006/M007 seams: simulated execution plan + realization
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SimulatedSegment:
    """One simulated realization segment (the M006/M007
    doubles): a provider-scoped realization of the contract
    under one accepted offer.  A segment is DATA: its binding
    rides the REAL ``BindExecutionArtifact`` command as an
    opaque ``execution-artifact`` reference (LOCK-117: data,
    never authority)."""

    segment_id: str
    provider: str
    offer_id: str
    state: str
    seam: str

    def __post_init__(self) -> None:
        if self.state not in REALIZATION_STATES:
            raise RoamLinkError(
                RoamLinkReason.VOCABULARY,
                "segment state %r must be one of %s"
                % (self.state, list(REALIZATION_STATES)),
            )

    def artifact_reference(self) -> OpaqueReference:
        """The opaque execution-artifact reference for the REAL
        bind command (labeled with the M007 seam issuer)."""
        return OpaqueReference(
            ref_kind="execution-artifact",
            value="simseam:segment:%s" % self.segment_id,
            provenance=Provenance(issuer=self.seam),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "provider": self.provider,
            "offer_id": self.offer_id,
            "state": self.state,
            "seam": self.seam,
        }


@dataclass(frozen=True)
class SimulatedRealization:
    """The simulated realization set (the M006/M007 doubles'
    plan output): the segments realizing the contract, each
    verified against the contract's hard constraints at
    construction (a plan may never weaken them -- LOCK-108)."""

    plan_id: str
    contract_id: str
    segments: Tuple[SimulatedSegment, ...]
    seam: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "contract_id": self.contract_id,
            "segments": [s.to_dict() for s in self.segments],
            "seam": self.seam,
        }


class SimulatedExecutionPlanner:
    """The M006/M007 simulation seam (execution-plan +
    realization/adapter doubles).  Deterministic: one segment
    per (offer, provider) pair the caller selects.  FAILS
    CLOSED (LOCK-108): a segment whose offer does not satisfy
    every hard constraint of the contract can never be planned
    -- the seam raises CONSTRAINT_VIOLATION instead of binding
    a weakening realization."""

    SEAM_PLAN = _seam_label("M006")
    SEAM_REALIZATION = _seam_label("M007")

    def plan(
        self,
        *,
        contract: ConnectivityContract,
        offers: Sequence[OfferRecord],
    ) -> SimulatedRealization:
        eligible: List[SimulatedSegment] = []
        for offer in sorted(offers, key=lambda o: o.provider_offer_key):
            if not _offer_satisfies(offer, contract.hard_constraints):
                raise RoamLinkError(
                    RoamLinkReason.CONSTRAINT_VIOLATION,
                    "offer %s violates the contract's hard constraints "
                    "(LOCK-108: a plan may never weaken them; the seam "
                    "fails closed instead of planning the realization)"
                    % offer.offer_id[:24],
                )
            document = {
                "seam": self.SEAM_REALIZATION,
                "contract_id": contract.contract_id,
                "provider": offer.provider,
                "offer_id": offer.offer_id,
                "constraints": [c.to_dict() for c in contract.hard_constraints],
            }
            segment_id = _digest(document, "segment id")
            eligible.append(
                SimulatedSegment(
                    segment_id=segment_id,
                    provider=offer.provider,
                    offer_id=offer.offer_id,
                    state="planned",
                    seam=self.SEAM_REALIZATION,
                )
            )
        plan_document = {
            "seam": self.SEAM_PLAN,
            "contract_id": contract.contract_id,
            "execution_scope": [s.to_dict() for s in contract.execution_scope],
            "segments": [s.to_dict() for s in eligible],
        }
        return SimulatedRealization(
            plan_id=_digest(plan_document, "plan id"),
            contract_id=contract.contract_id,
            segments=tuple(sorted(eligible, key=lambda s: s.segment_id)),
            seam=self.SEAM_PLAN,
        )


# ---------------------------------------------------------------------------
# The M008 seam: simulated replan/failover (the step-5
# provider-change absorption path)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProviderChange:
    """The deterministic provider-change injection (vertical
    fixture DATA: a change event at a fixed injected instant).
    The kinds cover the frozen vocabulary: an offer superseded
    by a weakened successor, an offer withdrawn, a realization
    degraded, a realization failed."""

    kind: str
    instant: str
    provider: str
    detail: str

    def __post_init__(self) -> None:
        if self.kind not in PROVIDER_CHANGE_KINDS:
            raise RoamLinkError(
                RoamLinkReason.VOCABULARY,
                "provider change kind %r must be one of %s"
                % (self.kind, list(PROVIDER_CHANGE_KINDS)),
            )
        _require_text(self.instant, "change.instant")
        _require_text(self.provider, "change.provider")
        _require_text(self.detail, "change.detail")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "instant": self.instant,
            "provider": self.provider,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class SimulatedReplanOutcome:
    """The deterministic M008 double's verdict: ``absorbed``
    (alternate segments satisfy every hard constraint; they ride
    the REAL bind command behind the SAME contract) or
    ``unrecoverable`` (no alternate satisfies -- the caller fails
    or renegotiates the contract explicitly; never a silent
    weakening)."""

    outcome_id: str
    verdict: str
    change: Dict[str, Any]
    new_segment_ids: Tuple[str, ...]
    rejected_realizations: Tuple[str, ...]
    contract_id: str
    seam: str

    def __post_init__(self) -> None:
        if self.verdict not in ("absorbed", "unrecoverable"):
            raise RoamLinkError(
                RoamLinkReason.VOCABULARY,
                "replan verdict %r must be absorbed or unrecoverable"
                % (self.verdict,),
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outcome_id": self.outcome_id,
            "verdict": self.verdict,
            "change": dict(self.change),
            "new_segment_ids": list(self.new_segment_ids),
            "rejected_realizations": list(self.rejected_realizations),
            "contract_id": self.contract_id,
            "seam": self.seam,
        }


class SimulatedReplanner:
    """The M008 simulation seam (replan/failover double): the
    provider-change absorption path behind the ADCOS contract.

    LOCK-108 discipline at the change seam: an alternate
    realization is admitted ONLY when its offer satisfies EVERY
    hard constraint of the (immutable) contract constraint set;
    a weakening alternate (e.g. the superseded successor's
    degraded commitments) is REJECTED and recorded as a rejected
    realization -- it can never be bound behind the contract.
    With no admissible alternate the verdict is ``unrecoverable``
    (the honest outcome: explicit failure or renegotiation,
    never a silent constraint weakening)."""

    SEAM = _seam_label("M008")

    def absorb(
        self,
        *,
        contract: ConnectivityContract,
        change: ProviderChange,
        alternate_offers: Sequence[OfferRecord],
        failed_segment: SimulatedSegment,
    ) -> SimulatedReplanOutcome:
        """Evaluate the alternate realizations for the change.

        The caller passes ALREADY-RESOLVED alternate offers (the
        flow resolves usability through the real exchange first:
        superseded/withdrawn listings fail closed at resolution
        time and are recorded as unabsorbable).  Every alternate
        is then evaluated against the contract's IMMUTABLE hard
        constraints: a weakening alternate is REJECTED and
        recorded (it can never be bound); an admissible alternate
        produces a replacement segment behind the SAME
        contract."""
        new_segments: List[str] = []
        rejected: List[str] = []
        for offer in sorted(alternate_offers, key=lambda o: o.provider_offer_key):
            if not _offer_satisfies(offer, contract.hard_constraints):
                rejected.append(offer.offer_id)
                continue
            document = {
                "seam": _seam_label("M007"),
                "contract_id": contract.contract_id,
                "provider": offer.provider,
                "offer_id": offer.offer_id,
                "replan_of": failed_segment.segment_id,
                "change": change.to_dict(),
            }
            new_segments.append(_digest(document, "replan segment id"))
        verdict = "absorbed" if new_segments else "unrecoverable"
        document = {
            "seam": self.SEAM,
            "contract_id": contract.contract_id,
            "change": change.to_dict(),
            "verdict": verdict,
            "new_segment_ids": sorted(new_segments),
            "rejected_realizations": sorted(rejected),
        }
        return SimulatedReplanOutcome(
            outcome_id=_digest(document, "replan outcome"),
            verdict=verdict,
            change=change.to_dict(),
            new_segment_ids=tuple(sorted(new_segments)),
            rejected_realizations=tuple(sorted(rejected)),
            contract_id=contract.contract_id,
            seam=self.SEAM,
        )

    def replacement_segment(
        self,
        *,
        contract: ConnectivityContract,
        change: ProviderChange,
        offer: OfferRecord,
        failed_segment: SimulatedSegment,
    ) -> SimulatedSegment:
        """Build the replacement segment for an absorbed change
        (FAILS CLOSED when the alternate offer violates the
        constraint set: LOCK-108 at the change seam)."""
        if not _offer_satisfies(offer, contract.hard_constraints):
            raise RoamLinkError(
                RoamLinkReason.CONSTRAINT_VIOLATION,
                "the alternate realization (%s) violates the contract's "
                "hard constraints; replanning may never weaken them "
                "(LOCK-108; the change must be absorbed by an "
                "admissible realization or fail explicitly)"
                % offer.offer_id[:24],
            )
        document = {
            "seam": _seam_label("M007"),
            "contract_id": contract.contract_id,
            "provider": offer.provider,
            "offer_id": offer.offer_id,
            "replan_of": failed_segment.segment_id,
            "change": change.to_dict(),
        }
        return SimulatedSegment(
            segment_id=_digest(document, "replan segment id"),
            provider=offer.provider,
            offer_id=offer.offer_id,
            state="planned",
            seam=_seam_label("M007"),
        )


def hard_constraint_fingerprint(contract: ConnectivityContract) -> str:
    """The canonical fingerprint of a contract's hard-constraint
    set (LOCK-108 verification substrate: byte-identical
    fingerprints prove the constraint set was NOT weakened
    across a provider-change absorption)."""
    document = {"constraints": [c.to_dict() for c in contract.hard_constraints]}
    return _digest(document, "constraint set")


__all__ = [
    "AUTHORITY_DOMAINS",
    "OBSERVATION_STATES",
    "PROVIDER_CHANGE_KINDS",
    "REALIZATION_STATES",
    "SIMULATION_SEAMS",
    "ProviderChange",
    "ProviderWorld",
    "SimulatedAssuranceEvaluation",
    "SimulatedAssuranceEvaluator",
    "SimulatedExecutionPlanner",
    "SimulatedPolicyDecision",
    "SimulatedPolicyGate",
    "SimulatedRealization",
    "SimulatedReplanOutcome",
    "SimulatedReplanner",
    "SimulatedSegment",
    "build_provider_world",
    "build_weakened_successor_offer",
    "hard_constraint_fingerprint",
]
