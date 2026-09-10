"""The M010 ShareNet vertical proof driver (the frozen 8-step flow
plus the three golden scenarios).

This module is the COMPOSITION POINT of the M010 delivery.  It wires
the frozen ``spec/integration/vertical-proof.md`` ShareNet flow onto
the ACCEPTED canonical authorities — nothing else:

- the real ``ContractStore`` (M002, DEC-0102) — the sole contract
  authority; every lifecycle mutation goes through its public command
  surface;
- the real ``OfferExchange`` / offer model / bridges (M003,
  DEC-0103) — the sole offer authority; both provider domains
  advertise through it;
- the real ``DeveloperApiService`` + ``DeveloperApiClient`` (M013,
  DEC-0113) — the sole application boundary; ShareNet speaks ONLY
  through this surface (the SDK client plus the raw request form for
  webhook endpoint registration).

The pending mechanics (M004 eligibility, M005 assurance, M006
execution plan, M007 realization, M008 replan/failover, M009 usage)
are driven through the disclosed deterministic simulation seams
(:mod:`sharenet.seams`) — DATA-producing stand-ins, never
authorities, never mutating the canonical contract.

The three golden scenarios (all deterministic, offline, byte-stable):

- ``degraded-recovery`` — step 6 degrades the primary realization;
  step 7 fails over to the second provider UNDER THE SAME CONTRACT;
  the lifecycle completes to SETTLED.
- ``failed-recovery`` — step 6 kills the primary realization; step 7
  fails over to the second provider; the lifecycle completes to
  SETTLED (the dead realization is honestly observed as
  unknown-stale, never as compliant).
- ``terminal-failure`` — the second provider's offer VIOLATES the
  hard latency constraint (ineligible at step 3); when the primary
  fails at step 6, step 7 fail-closes: no candidate satisfies the
  UNCHANGED constraints (LOCK-108), the contract FAILS with the
  rejection trail, and usage/assurance evidence REMAINS attributable
  (step 8 holds after terminal failure).

Determinism (LOCK-119): every instant is a module constant; the
failure schedule is injected; runs are byte-identical in-process and
cross-process.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

from agent.clock import StepClock
from contracts import (
    BindExecutionArtifact,
    ContractStore,
    FailContract,
    OpaqueReference,
    Provenance,
    RecordAssurance,
    RecordDelivery,
    RecordExecutionActivation,
    RecordSettled,
    RecordSettlementPending,
    RecordUsageFinal,
    ValidityInterval,
)
from developerapi import (
    Capability,
    DeveloperApiClient,
    DeveloperApiService,
    MemoryApiStore,
    derive_resource_id,
)
from offers import (
    AdvertisementEntry,
    AdvertisementRef,
    OfferCommitment,
    OfferExchange,
    OfferPricing,
    ServiceBoundary,
    build_advertisement,
    build_offer,
)
from offers.bridge import offer_reference
from protocol.canonicalization import canonical_json_bytes

from .application import (
    REASON_FAIL_CLOSED,
    SHARENET_APPLICATION_NAME,
    SHARENET_DEVELOPER_ID,
    ShareNetApplication,
    ShareNetError,
    ShareNetIntentSpec,
)
from .evidence import EvidenceEntry, EvidenceLedger
from .seams import (
    AssuranceSeam,
    EligibilitySeam,
    ExecutionPlanSeam,
    FailureSchedule,
    FailoverDecision,
    ProviderRealizationSeam,
    RealizationEvent,
    ReplanEngine,
    UsageObservation,
    UsageObservationSeam,
)

# ----------------------------------------------------------------------
# The frozen 8-step flow (the exact ACR-014 text)
# ----------------------------------------------------------------------

FROZEN_FLOW: Tuple[str, ...] = (
    "ShareNet submits a technology-neutral connectivity intent for gateway/relay nodes.",
    "At least two provider domains advertise offers.",
    "ADCOS evaluates eligibility and evidence.",
    "ADCOS creates one connectivity contract.",
    "ADCOS executes via one or more providers.",
    "A provider realization degrades or fails.",
    "ADCOS replans/fails over without weakening hard contract constraints.",
    "Usage and assurance evidence remain attributable to the contract.",
)

#: The ShareNet compatibility statement that closes the frozen spec
#: section (LOCK-120 — asserted by the battery, carried here so the
#: harness self-describes its boundary).
SHARENET_RETAINED_AUTHORITY = (
    "ShareNet retains authority over content, P2P distribution, "
    "publisher trust and its own application economics."
)

# ----------------------------------------------------------------------
# Injected deterministic instants (LOCK-119: no wall clock anywhere)
# ----------------------------------------------------------------------

T_VALID_FROM = "2026-10-01T00:00:00Z"
T_VALID_TO = "2026-11-01T00:00:00Z"
T_INTENT = "2026-10-01T00:01:00Z"
T_ELIGIBILITY = "2026-10-01T00:02:00Z"
T_ADVERTISE = "2026-10-01T00:02:30Z"
T_ACCEPT = "2026-10-01T00:03:00Z"
T_ACTIVATE = "2026-10-01T00:04:00Z"
T_EXEC = "2026-10-01T00:05:00Z"
T_DELIVERY = "2026-10-01T00:06:00Z"
T_ASSURANCE = "2026-10-01T00:07:00Z"
T_INCIDENT = "2026-10-01T00:08:00Z"
T_REPLAN = "2026-10-01T00:09:00Z"
T_FAILOVER_ASSURANCE = "2026-10-01T00:10:00Z"
T_USAGE_FINAL = "2026-10-01T00:11:00Z"
T_SETTLEMENT = "2026-10-01T00:12:00Z"

CREDENTIAL_VALID_UNTIL = "2030-01-01T00:00:00Z"
SERVICE_CLOCK_ORIGIN = "2026-10-01T00:00:30Z"
ISSUANCE_KEY = b"m010-sharenet-issuance-key"

#: The two canonical provider domains (the frozen flow requires at
#: least two DISTINCT provider domains advertising offers).
PROVIDER_A = "adcos:node:identity.sha256-hmac-dev.v1:" + "1" * 64
PROVIDER_B = "adcos:node:identity.sha256-hmac-dev.v1:" + "2" * 64

#: The ShareNet observation endpoint registration (the deterministic
#: idempotency key predicts the endpoint id — the transport is
#  injected through the service's public constructor).
OBSERVATION_ENDPOINT_KEY = "sharenet-observation-endpoint"
OBSERVATION_ENDPOINT_URL = "https://sharenet-app.test/connectivity-observations"
OBSERVATION_EVENT_TYPES = ("connectivity_contract.state_changed",)


# ----------------------------------------------------------------------
# Scenario material
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ProviderMaterial:
    """One provider domain's deterministic advertisement material
    (the M003 real model; the numbers are the scenario's dials)."""

    provider: str
    issuer: str
    offer_key: str
    latency_ms: int
    throughput_kbps: int
    price_minor: int
    advertisement_digest: str
    advertisement_classification: str = "known"
    capability_id: str = "capability.core.multipath"
    schema_version: str = "1.2"
    jurisdiction: str = "GH"
    geography_ref: str = "mpcell:v1:coarse-50000m:12:-1"


@dataclass(frozen=True)
class VerticalScenario:
    """One golden scenario: the intent's hard constraints, the two
    providers' material, the injected failure schedule, and the
    expected terminal shape."""

    name: str
    latency_bound_ms: int
    throughput_floor_bps: int
    providers: Tuple[ProviderMaterial, ...]
    schedule: FailureSchedule
    expected_final_state: str
    expected_failover: str  # "recovered" | "fail-closed"


#: Provider A — the primary realization (fast, well-provisioned).
PROVIDER_A_MATERIAL = ProviderMaterial(
    provider=PROVIDER_A,
    issuer="provider:sharenet-primary",
    offer_key="sharenet:relay:primary",
    latency_ms=120,
    throughput_kbps=1000,
    price_minor=250,
    advertisement_digest="sha256:" + "a" * 64,
)

#: Provider B — the failover realization; the latency dial differs
#: per scenario (satisfying or violating the frozen intent bound).
def _provider_b_material(latency_ms: int) -> ProviderMaterial:
    return ProviderMaterial(
        provider=PROVIDER_B,
        issuer="provider:sharenet-secondary",
        offer_key="sharenet:relay:secondary",
        latency_ms=latency_ms,
        throughput_kbps=800,
        price_minor=180,
        advertisement_digest="sha256:" + "b" * 64,
    )


#: The three golden scenarios.
SCENARIO_DEGRADED_RECOVERY = "degraded-recovery"
SCENARIO_FAILED_RECOVERY = "failed-recovery"
SCENARIO_TERMINAL_FAILURE = "terminal-failure"

SCENARIOS: Tuple[VerticalScenario, ...] = (
    VerticalScenario(
        name=SCENARIO_DEGRADED_RECOVERY,
        latency_bound_ms=200,
        throughput_floor_bps=500,
        providers=(
            PROVIDER_A_MATERIAL,
            _provider_b_material(latency_ms=180),
        ),
        schedule=FailureSchedule(
            events=(
                RealizationEvent(
                    provider=PROVIDER_A,
                    kind="degraded",
                    effective_at=T_INCIDENT,
                    detail="primary-realization:latency-erosion",
                ),
            )
        ),
        expected_final_state="SETTLED",
        expected_failover="recovered",
    ),
    VerticalScenario(
        name=SCENARIO_FAILED_RECOVERY,
        latency_bound_ms=200,
        throughput_floor_bps=500,
        providers=(
            PROVIDER_A_MATERIAL,
            _provider_b_material(latency_ms=180),
        ),
        schedule=FailureSchedule(
            events=(
                RealizationEvent(
                    provider=PROVIDER_A,
                    kind="failed",
                    effective_at=T_INCIDENT,
                    detail="primary-realization:dead",
                ),
            )
        ),
        expected_final_state="SETTLED",
        expected_failover="recovered",
    ),
    VerticalScenario(
        name=SCENARIO_TERMINAL_FAILURE,
        latency_bound_ms=150,
        throughput_floor_bps=500,
        providers=(
            PROVIDER_A_MATERIAL,
            _provider_b_material(latency_ms=180),
        ),
        schedule=FailureSchedule(
            events=(
                RealizationEvent(
                    provider=PROVIDER_A,
                    kind="failed",
                    effective_at=T_INCIDENT,
                    detail="primary-realization:dead",
                ),
            )
        ),
        expected_final_state="FAILED",
        expected_failover="fail-closed",
    ),
)


# ----------------------------------------------------------------------
# Step records (canonical round-trip data)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class StepRecord:
    """One frozen-flow step's deterministic record (the evidence the
    battery and the evidence doc verify against)."""

    step: int
    title: str
    instant: str
    outcome: str
    detail: str
    contract_id: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "title": self.title,
            "instant": self.instant,
            "outcome": self.outcome,
            "detail": self.detail,
            "contract_id": self.contract_id,
        }

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "StepRecord":
        return StepRecord(
            step=data.get("step"),
            title=data.get("title"),
            instant=data.get("instant"),
            outcome=data.get("outcome"),
            detail=data.get("detail"),
            contract_id=data.get("contract_id"),
        )


@dataclass(frozen=True)
class VerticalResult:
    """The full deterministic outcome of one scenario run."""

    scenario: str
    steps: Tuple[StepRecord, ...]
    contract_id: str
    final_state: str
    failover: Optional[FailoverDecision]
    attribution: Mapping[str, Any]
    observation_deliveries: Tuple[Mapping[str, Any], ...]
    journal_digest: str
    offer_ids: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario": self.scenario,
            "steps": [record.to_dict() for record in self.steps],
            "contract_id": self.contract_id,
            "final_state": self.final_state,
            "failover": None if self.failover is None else self.failover.to_dict(),
            "attribution": dict(self.attribution),
            "observation_deliveries": [
                dict(delivery) for delivery in self.observation_deliveries
            ],
            "journal_digest": self.journal_digest,
            "offer_ids": list(self.offer_ids),
        }

    def digest(self) -> str:
        """The scenario digest (cross-process determinism proof):
        the canonical JSON of the whole result, hashed."""
        return "sha256:" + hashlib.sha256(
            canonical_json_bytes(self.to_dict())
        ).hexdigest()


# ----------------------------------------------------------------------
# The vertical harness
# ----------------------------------------------------------------------

#: The canonical ShareNet intent spec of one scenario (the frozen
#: technology-neutral creation core: WHAT ShareNet needs, never HOW).
def _intent_spec(scenario: VerticalScenario) -> ShareNetIntentSpec:
    return ShareNetIntentSpec(
        purpose="sharenet:relay-gateway-connectivity",
        requirements=(
            "req:sharenet:relay-backhaul",
            "req:sharenet:bounded-cohort",
        ),
        validity=(T_VALID_FROM, T_VALID_TO),
        termination_conditions=(
            "principal-requested",
            "validity-expired",
            "constraint-violated",
        ),
        compensation="comp:sharenet:prorated-v1",
        beneficiaries=(
            ("DEVICE", "sharenet:gateway:gw-1"),
            ("DEVICE", "sharenet:relay:relay-1"),
        ),
        hard_constraints=(
            ("latency-bound", (("ms", scenario.latency_bound_ms),)),
            ("throughput-floor", (("bps", scenario.throughput_floor_bps),)),
        ),
        service_properties=("prop:sharenet:relay-class-v1",),
        usage_pricing_terms="sharenet:sponsorship:terms-v1",
        assurance_obligations=("oblig:sharenet:continuity-v1",),
        execution_scope=("scope:sharenet:relay-egress-v1",),
    )


class ShareNetVertical:
    """The M010 vertical proof harness: one scenario, composed over
    the REAL accepted authorities, driven through the frozen 8-step
    flow with the disclosed deterministic seams.

    Construction composes (all real, all public-surface):

    - ``ContractStore`` — the canonical contract authority (M002);
    - ``OfferExchange`` — the canonical offer authority (M003), with
      the scenario's provider material registered as real
      capability advertisements and offers;
    - ``DeveloperApiService`` (sandbox) over the store, with the
      deterministic StepClock, the platform issuance key, and the
      ShareNet observation transport injected through the public
      constructor;
    - ``ShareNetApplication`` — the external boundary over the M013
      SDK client;
    - ``EvidenceLedger`` bound to the real store;
    - the six disclosed simulation seams.
    """

    def __init__(
        self,
        *,
        scenario: VerticalScenario,
        issuance_key: bytes = ISSUANCE_KEY,
    ) -> None:
        self._scenario = scenario
        # the REAL canonical contract authority
        self._contracts = ContractStore()
        # the REAL canonical offer authority with the scenario's
        # provider material registered
        self._exchange = OfferExchange()
        self._offer_ids: List[str] = []
        for material in scenario.providers:
            self._register_provider(material)
        # the REAL developer API boundary (M013) over the store
        self._clock = StepClock(SERVICE_CLOCK_ORIGIN, 60)
        endpoint_id = derive_resource_id(
            "sandbox",
            "webhook_endpoint",
            SHARENET_DEVELOPER_ID,
            OBSERVATION_ENDPOINT_KEY,
        )
        self._received: List[Dict[str, Any]] = []

        def _transport(endpoint: str, url: str, payload: Mapping[str, Any],
                       headers: Mapping[str, str]) -> Tuple[bool, int]:
            self._received.append(dict(payload))
            return (True, 200)

        self._service = DeveloperApiService(
            environment="sandbox",
            contracts=self._contracts,
            store=MemoryApiStore(),
            clock=self._clock,
            issuance_key=issuance_key,
            delivery_transports={endpoint_id: _transport},
        )
        # the ShareNet application credential (platform out-of-band
        # issuance; LOCK-103: an APPLICATION principal may sponsor)
        issued = self._service.issue_application_credential(
            developer_id=SHARENET_DEVELOPER_ID,
            application_name=SHARENET_APPLICATION_NAME,
            capabilities=Capability.values(),
            valid_until=CREDENTIAL_VALID_UNTIL,
            key_material="m010-sharenet-application-key",
            actor="platform",
        )
        client = DeveloperApiClient(
            transport=self._service.handle,
            application_id=issued.record.application_id,
            secret=issued.secret,
            api_version="2.0",
            environment="sandbox",
        )
        self._app = ShareNetApplication(
            client=client,
            application_id=issued.record.application_id,
            secret=issued.secret,
            transport=self._service.handle,
        )
        # the observation endpoint is registered BEFORE the flow so
        # the channel observes the whole lifecycle (the endpoint id
        # was predicted above; the idempotency key is the same)
        self._app.register_observation_endpoint(
            url=OBSERVATION_ENDPOINT_URL,
            event_types=OBSERVATION_EVENT_TYPES,
            idempotency_key=OBSERVATION_ENDPOINT_KEY,
        )
        # the disclosed deterministic seams
        self._eligibility = EligibilitySeam()
        self._assurance = AssuranceSeam()
        self._planner = ExecutionPlanSeam()
        self._realization = ProviderRealizationSeam()
        self._replan = ReplanEngine()
        self._usage = UsageObservationSeam()
        self._ledger = EvidenceLedger(contracts=self._contracts)
        self._assurance_sequence = 0

    # -- provider material registration (the real M003 model) ------

    def _register_provider(self, material: ProviderMaterial) -> None:
        advertisement = build_advertisement(
            provider=material.provider,
            entries=(
                AdvertisementEntry(
                    capability_id=material.capability_id,
                    schema_version=material.schema_version,
                    statement_digest=material.advertisement_digest,
                    classification=material.advertisement_classification,
                ),
            ),
            validity=ValidityInterval(
                not_before=T_VALID_FROM, not_after=T_VALID_TO
            ),
            provenance=Provenance(
                issuer=material.issuer,
                decision_refs=("sharenet:provider:v1",),
            ),
        )
        self._exchange.register_advertisement(advertisement)
        offer = build_offer(
            provider=material.provider,
            provider_offer_key=material.offer_key,
            schema_version=1,
            advertisements=(
                AdvertisementRef(
                    advertisement_id=advertisement.advertisement_id,
                    provenance=Provenance(
                        issuer=material.issuer,
                        decision_refs=("sharenet:provider:v1",),
                    ),
                ),
            ),
            commitments=(
                OfferCommitment(
                    kind="latency-bound-ms",
                    params={"max_ms": material.latency_ms},
                    window=ValidityInterval(
                        not_before=T_VALID_FROM, not_after=T_VALID_TO
                    ),
                    provenance=Provenance(
                        issuer=material.issuer,
                        decision_refs=("sharenet:commitment:latency",),
                    ),
                ),
                OfferCommitment(
                    kind="throughput-floor-kbps",
                    params={"min_kbps": material.throughput_kbps},
                    window=ValidityInterval(
                        not_before=T_VALID_FROM, not_after=T_VALID_TO
                    ),
                    provenance=Provenance(
                        issuer=material.issuer,
                        decision_refs=("sharenet:commitment:throughput",),
                    ),
                ),
            ),
            pricing=OfferPricing(
                currency="USD",
                price_minor=material.price_minor,
                price_exponent=2,
                billing_mode="flat",
                provenance=Provenance(
                    issuer=material.issuer,
                    decision_refs=("sharenet:pricing:v1",),
                ),
            ),
            service_boundaries=(
                ServiceBoundary(
                    jurisdiction=material.jurisdiction,
                    geography_refs=(material.geography_ref,),
                    provenance=Provenance(
                        issuer=material.issuer,
                        decision_refs=("sharenet:boundary:v1",),
                    ),
                ),
            ),
            validity=ValidityInterval(
                not_before=T_VALID_FROM, not_after=T_VALID_TO
            ),
            provenance=Provenance(
                issuer=material.issuer,
                decision_refs=("sharenet:offer:v1",),
            ),
        )
        self._exchange.register_offer(offer)
        self._offer_ids.append(offer.offer_id)

    # -- evidence helpers --------------------------------------------

    def _next_assurance_sequence(self) -> int:
        self._assurance_sequence += 1
        return self._assurance_sequence

    def _record_assurance_evidence(
        self,
        *,
        contract_id: str,
        state: str,
        token: str,
        recorded_at: str,
    ) -> None:
        self._ledger.record(
            EvidenceEntry(
                kind="assurance-evaluation",
                contract_id=contract_id,
                recorded_at=recorded_at,
                token=token,
                issuer="m005-seam:assurance-observation",
                decision_refs=(token,),
                payload={"assurance_state": state},
            )
        )

    def _record_usage_evidence(
        self, *, observation: UsageObservation
    ) -> None:
        self._ledger.record(
            EvidenceEntry(
                kind="usage-observation",
                contract_id=observation.contract_id,
                recorded_at=observation.recorded_at,
                token="m009-seam:usage:%s" % observation.recorded_at,
                issuer="m009-seam:usage-observation",
                decision_refs=(observation.settlement_reference,),
                payload={
                    "bytes_transferred": observation.bytes_transferred,
                    "active_seconds": observation.active_seconds,
                },
            )
        )

    def _observe(self, contract_id: str) -> None:
        """Push the canonical current state through the observation
        channel and pump the deterministic deliveries."""
        self._service.observe_contract(contract_id)
        self._service.process_due_deliveries()

    # -- the frozen 8-step flow --------------------------------------

    def run(self) -> VerticalResult:
        scenario = self._scenario
        steps: List[StepRecord] = []
        contract_id: Optional[str] = None

        # STEP 1 — the technology-neutral intent (ShareNet -> ADCOS
        # through the M013 surface ONLY)
        intent = self._app.submit_intent(
            spec=_intent_spec(scenario),
            idempotency_key="sharenet-intent",
            recorded_at=T_INTENT,
        )
        contract_id = intent.id
        contract = self._contracts.contract(contract_id)
        if contract.state != "INTENT":
            raise ShareNetError(
                REASON_FAIL_CLOSED,
                "step 1: the canonical contract must be created in INTENT "
                "state (found %s)" % contract.state,
            )
        steps.append(
            StepRecord(
                step=1,
                title=FROZEN_FLOW[0],
                instant=T_INTENT,
                outcome="intent-submitted",
                detail="technology-neutral creation core accepted through "
                "the M013 SDK surface; principal=APPLICATION:%s"
                % self._app.application_id[:24],
                contract_id=contract_id,
            )
        )
        self._observe(contract_id)

        # STEP 2 — at least two provider domains advertise offers
        advertised = self._exchange.offers()
        providers = tuple(
            sorted({offer.provider for offer in advertised})
        )
        if len(providers) < 2:
            raise ShareNetError(
                REASON_FAIL_CLOSED,
                "step 2: the frozen flow requires at least two distinct "
                "provider domains advertising (found %d)" % len(providers),
            )
        steps.append(
            StepRecord(
                step=2,
                title=FROZEN_FLOW[1],
                instant=T_ADVERTISE,
                outcome="providers-advertising",
                detail="%d provider domains advertising %d live offers "
                "(real M003 exchange)" % (len(providers), len(advertised)),
                contract_id=contract_id,
            )
        )

        # STEP 3 — ADCOS evaluates eligibility and evidence (the M004
        # seam over the REAL constraints and REAL offers)
        contract = self._contracts.contract(contract_id)
        decisions = self._eligibility.evaluate_all(
            offers=advertised,
            constraints=contract.hard_constraints,
            at_instant=T_ELIGIBILITY,
        )
        eligible = tuple(
            decision for decision in decisions if decision.eligible
        )
        if not eligible:
            raise ShareNetError(
                REASON_FAIL_CLOSED,
                "step 3: no advertised offer is eligible; the vertical "
                "cannot proceed (fail-closed)",
            )
        rejected_trail = "; ".join(
            "%s->%s" % (decision.offer_id[:24], decision.reason)
            for decision in decisions
            if not decision.eligible
        )
        steps.append(
            StepRecord(
                step=3,
                title=FROZEN_FLOW[2],
                instant=T_ELIGIBILITY,
                outcome="eligibility-evaluated",
                detail="%d eligible, %d rejected (seam: M004 pending)%s"
                % (
                    len(eligible),
                    len(decisions) - len(eligible),
                    "; %s" % rejected_trail if rejected_trail else "",
                ),
                contract_id=contract_id,
            )
        )

        # STEP 4 — ONE connectivity contract (the eligible offers
        # bind through the M013 surface; activation completes the
        # contract formation)
        eligible_offers = tuple(
            self._exchange.offer(decision.offer_id) for decision in eligible
        )
        references = tuple(
            offer_reference(offer) for offer in eligible_offers
        )
        self._app.accept_eligible_offers(
            intent_id=contract_id,
            offer_references=tuple(ref.to_dict() for ref in references),
            idempotency_key="sharenet-offers",
            recorded_at=T_ACCEPT,
        )
        self._app.activate_contract(
            intent_id=contract_id,
            activated_at=T_ACTIVATE,
            signature_token="sig:sharenet:sponsorship-v1",
            idempotency_key="sharenet-activate",
        )
        contract = self._contracts.contract(contract_id)
        if contract.state != "CONTRACT_ACTIVE":
            raise ShareNetError(
                REASON_FAIL_CLOSED,
                "step 4: the contract must be CONTRACT_ACTIVE after offer "
                "binding and activation (found %s)" % contract.state,
            )
        if len(self._contracts.contracts()) != 1:
            raise ShareNetError(
                REASON_FAIL_CLOSED,
                "step 4: the frozen flow creates exactly ONE contract "
                "(found %d)" % len(self._contracts.contracts()),
            )
        steps.append(
            StepRecord(
                step=4,
                title=FROZEN_FLOW[3],
                instant=T_ACTIVATE,
                outcome="contract-created",
                detail="exactly one contract; %d eligible offer references "
                "bound (offers bind once: INTENT->OFFER_SELECTED->ACTIVE)"
                % len(references),
                contract_id=contract_id,
            )
        )
        self._observe(contract_id)

        # STEP 5 — ADCOS executes via one or more providers (the M006
        # seam plans; the canonical store records; artifacts are DATA)
        plan = self._planner.build_plan(
            contract=contract,
            exchange=self._exchange,
            at_instant=T_EXEC,
        )
        primary = plan.segments[0]
        self._contracts.submit(
            BindExecutionArtifact(artifact=primary.artifact_reference()),
            T_EXEC,
            contract_id=contract_id,
        )
        self._contracts.submit(
            RecordExecutionActivation(recorded_at=T_EXEC),
            T_EXEC,
            contract_id=contract_id,
        )
        self._contracts.submit(
            RecordDelivery(recorded_at=T_DELIVERY),
            T_DELIVERY,
            contract_id=contract_id,
        )
        contract = self._contracts.contract(contract_id)
        primary_status = self._realization.status_at(
            provider=primary.provider,
            schedule=scenario.schedule,
            at_instant=T_ASSURANCE,
        )
        state, token = self._assurance.observe(
            realization_status=primary_status,
            obligations=contract.assurance_obligations
            and tuple(ref.value for ref in contract.assurance_obligations)
            or (),
            at_instant=T_ASSURANCE,
            sequence=self._next_assurance_sequence(),
        )
        if state != "compliant":
            raise ShareNetError(
                REASON_FAIL_CLOSED,
                "step 5: the primary realization must be healthy at "
                "execution start (observed %s)" % state,
            )
        self._record_assurance_evidence(
            contract_id=contract_id, state=state, token=token,
            recorded_at=T_ASSURANCE,
        )
        self._contracts.submit(
            RecordAssurance(
                recorded_at=T_ASSURANCE,
                assurance_state="compliant",
                evidence_refs=(
                    OpaqueReference(
                        ref_kind="decision",
                        value=token,
                        provenance=Provenance(
                            issuer="m005-seam:assurance-observation",
                            decision_refs=(token,),
                        ),
                    ),
                ),
            ),
            T_ASSURANCE,
            contract_id=contract_id,
        )
        usage = self._usage.observe(
            contract=self._contracts.contract(contract_id),
            bytes_transferred=900_000_000,
            active_seconds=3600,
            recorded_at=T_ASSURANCE,
        )
        self._record_usage_evidence(observation=usage)
        contract = self._contracts.contract(contract_id)
        if contract.state != "ASSURED":
            raise ShareNetError(
                REASON_FAIL_CLOSED,
                "step 5: execution must reach ASSURED (found %s)"
                % contract.state,
            )
        steps.append(
            StepRecord(
                step=5,
                title=FROZEN_FLOW[4],
                instant=T_EXEC,
                outcome="executing",
                detail="plan over %d segment(s); primary provider realized; "
                "execution-activation, delivery, compliant assurance and "
                "usage recorded on the canonical journal; artifact bound "
                "as DATA (LOCK-117)" % len(plan.segments),
                contract_id=contract_id,
            )
        )
        self._observe(contract_id)

        # STEP 6 — a provider realization degrades or fails (the
        # injected deterministic schedule decides which)
        incident = scenario.schedule.events[0]
        incident_status = self._realization.status_at(
            provider=primary.provider,
            schedule=scenario.schedule,
            at_instant=T_INCIDENT,
        )
        if incident_status != incident.kind:
            raise ShareNetError(
                REASON_FAIL_CLOSED,
                "step 6: the schedule must take effect at the incident "
                "instant (expected %s, observed %s)"
                % (incident.kind, incident_status),
            )
        state, token = self._assurance.observe(
            realization_status=incident_status,
            obligations=(),
            at_instant=T_INCIDENT,
            sequence=self._next_assurance_sequence(),
        )
        self._record_assurance_evidence(
            contract_id=contract_id, state=state, token=token,
            recorded_at=T_INCIDENT,
        )
        # the canonical lifecycle consequence: degraded is an explicit
        # contract state; a dead realization reports honestly as
        # unknown-stale (recorded, no state change — never compliant
        # by inference)
        if state == "degraded":
            self._contracts.submit(
                RecordAssurance(
                    recorded_at=T_INCIDENT,
                    assurance_state="degraded",
                    evidence_refs=(
                        OpaqueReference(
                            ref_kind="decision",
                            value=token,
                            provenance=Provenance(
                                issuer="m005-seam:assurance-observation",
                                decision_refs=(token,),
                            ),
                        ),
                    ),
                ),
                T_INCIDENT,
                contract_id=contract_id,
            )
        else:
            self._contracts.submit(
                RecordAssurance(
                    recorded_at=T_INCIDENT,
                    assurance_state="unknown-stale",
                    evidence_refs=(
                        OpaqueReference(
                            ref_kind="decision",
                            value=token,
                            provenance=Provenance(
                                issuer="m005-seam:assurance-observation",
                                decision_refs=(token,),
                            ),
                        ),
                    ),
                ),
                T_INCIDENT,
                contract_id=contract_id,
            )
        steps.append(
            StepRecord(
                step=6,
                title=FROZEN_FLOW[5],
                instant=T_INCIDENT,
                outcome="realization-%s" % incident.kind,
                detail="primary realization %s at %s (injected schedule; "
                "honest assurance observation: %s)"
                % (incident.kind, incident.effective_at, state),
                contract_id=contract_id,
            )
        )
        self._observe(contract_id)

        # STEP 7 — replan/failover WITHOUT weakening hard constraints
        # (LOCK-108: the M008 seam evaluates candidates against the
        # UNCHANGED constraint set; fail-closed when none qualifies)
        contract = self._contracts.contract(contract_id)
        decision = self._replan.replan(
            contract=contract,
            exchange=self._exchange,
            failed_provider=primary.provider,
            schedule=scenario.schedule,
            at_instant=T_REPLAN,
        )
        if decision.weakened:
            raise ShareNetError(
                REASON_FAIL_CLOSED,
                "step 7: LOCK-108 violated — the decision reports a "
                "weakened constraint set",
            )
        if decision.plan is not None:
            # failover under the SAME contract: the new segment's
            # artifact binds as DATA and the closed-loop assurance
            # continues (LOCK-107)
            self._contracts.submit(
                BindExecutionArtifact(
                    artifact=decision.plan.artifact_reference()
                ),
                T_REPLAN,
                contract_id=contract_id,
            )
            failover_status = self._realization.status_at(
                provider=decision.plan.provider,
                schedule=scenario.schedule,
                at_instant=T_FAILOVER_ASSURANCE,
            )
            state, token = self._assurance.observe(
                realization_status=failover_status,
                obligations=(),
                at_instant=T_FAILOVER_ASSURANCE,
                sequence=self._next_assurance_sequence(),
            )
            self._record_assurance_evidence(
                contract_id=contract_id, state=state, token=token,
                recorded_at=T_FAILOVER_ASSURANCE,
            )
            if state == "compliant":
                # the canonical command applies exactly where the
                # lifecycle admits it (DELIVERY/DEGRADED -> ASSURED);
                # from ASSURED the closed-loop observation continues
                # as LEDGER EVIDENCE (LOCK-107: continuous
                # evaluation — an already-assured contract keeps
                # accumulating assurance observations without a
                # no-op state command)
                pre_state = self._contracts.contract(contract_id).state
                if pre_state in ("DELIVERY", "DEGRADED"):
                    self._contracts.submit(
                        RecordAssurance(
                            recorded_at=T_FAILOVER_ASSURANCE,
                            assurance_state="compliant",
                            evidence_refs=(
                                OpaqueReference(
                                    ref_kind="decision",
                                    value=token,
                                    provenance=Provenance(
                                        issuer="m005-seam:assurance-observation",
                                        decision_refs=(token,),
                                    ),
                                ),
                            ),
                        ),
                        T_FAILOVER_ASSURANCE,
                        contract_id=contract_id,
                    )
            steps.append(
                StepRecord(
                    step=7,
                    title=FROZEN_FLOW[6],
                    instant=T_REPLAN,
                    outcome="failover-executed",
                    detail="failover to provider %s under the SAME "
                    "contract; hard constraints byte-identical "
                    "(LOCK-108 clean)" % decision.plan.provider[:48],
                    contract_id=contract_id,
                )
            )
        else:
            # LOCK-108 fail-closed: no candidate satisfies the
            # UNCHANGED constraints — the contract fails with the
            # rejection trail (never a weakened constraint)
            self._contracts.submit(
                FailContract(
                    recorded_at=T_REPLAN,
                    reason="lock-108:fail-closed:no-failover-candidate-"
                    "satisfies-the-hard-constraints",
                ),
                T_REPLAN,
                contract_id=contract_id,
            )
            steps.append(
                StepRecord(
                    step=7,
                    title=FROZEN_FLOW[6],
                    instant=T_REPLAN,
                    outcome="failover-fail-closed",
                    detail="LOCK-108: %d candidate(s) rejected against the "
                    "UNCHANGED constraints; contract FAILED with the "
                    "rejection trail" % len(decision.rejections),
                    contract_id=contract_id,
                )
            )
        self._observe(contract_id)

        # STEP 8 — usage and assurance evidence remain attributable
        # to THE contract (even after terminal failure)
        contract = self._contracts.contract(contract_id)
        usage = self._usage.observe(
            contract=contract,
            bytes_transferred=1_500_000_000,
            active_seconds=7200,
            recorded_at=T_USAGE_FINAL,
        )
        self._record_usage_evidence(observation=usage)
        if contract.state == "ASSURED":
            self._contracts.submit(
                RecordUsageFinal(recorded_at=T_USAGE_FINAL),
                T_USAGE_FINAL,
                contract_id=contract_id,
            )
            self._contracts.submit(
                RecordSettlementPending(recorded_at=T_USAGE_FINAL),
                T_USAGE_FINAL,
                contract_id=contract_id,
            )
            self._contracts.submit(
                RecordSettled(recorded_at=T_SETTLEMENT),
                T_SETTLEMENT,
                contract_id=contract_id,
            )
        contract = self._contracts.contract(contract_id)
        if contract.state != scenario.expected_final_state:
            raise ShareNetError(
                REASON_FAIL_CLOSED,
                "scenario %s: expected terminal state %s, found %s"
                % (scenario.name, scenario.expected_final_state, contract.state),
            )
        attribution = self._ledger.attribution(contract_id)
        steps.append(
            StepRecord(
                step=8,
                title=FROZEN_FLOW[7],
                instant=T_USAGE_FINAL,
                outcome="evidence-attributed",
                detail="%d usage and %d assurance evidence entries "
                "attributable to the contract in state %s; settlement "
                "reference %s (LOCK-113: external)"
                % (
                    len(attribution.usage_entries),
                    len(attribution.assurance_entries),
                    contract.state,
                    usage.settlement_reference,
                ),
                contract_id=contract_id,
            )
        )
        self._observe(contract_id)

        return VerticalResult(
            scenario=scenario.name,
            steps=tuple(steps),
            contract_id=contract_id,
            final_state=contract.state,
            failover=decision,
            attribution=attribution.to_dict(),
            observation_deliveries=tuple(self._received),
            journal_digest=self._contracts.journal_digest(),
            offer_ids=tuple(sorted(self._offer_ids)),
        )


def run_scenario(scenario: VerticalScenario) -> VerticalResult:
    """Run one golden scenario (the module-level convenience)."""
    return ShareNetVertical(scenario=scenario).run()


__all__ = [
    "FROZEN_FLOW",
    "OBSERVATION_EVENT_TYPES",
    "OBSERVATION_ENDPOINT_KEY",
    "OBSERVATION_ENDPOINT_URL",
    "PROVIDER_A",
    "PROVIDER_A_MATERIAL",
    "PROVIDER_B",
    "SCENARIOS",
    "SCENARIO_DEGRADED_RECOVERY",
    "SCENARIO_FAILED_RECOVERY",
    "SCENARIO_TERMINAL_FAILURE",
    "SHARENET_RETAINED_AUTHORITY",
    "ShareNetVertical",
    "StepRecord",
    "VerticalResult",
    "VerticalScenario",
    "run_scenario",
]
