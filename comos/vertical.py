"""The M012 COMOS vertical proof driver (the frozen 6-step flow
plus the three golden scenarios).

This module is the COMPOSITION POINT of the M012 delivery.  It
wires the frozen ``spec/integration/vertical-proof.md`` COMOS flow
onto the ACCEPTED canonical authorities — nothing else:

- the real ``ContractStore`` (M002, DEC-0102) — the sole contract
  authority; every lifecycle mutation goes through its public
  command surface;
- the real ``OfferExchange`` / offer model / bridges (M003,
  DEC-0103) — the sole offer authority; both provider domains
  advertise through it;
- the real ``DeveloperApiService`` + ``DeveloperApiClient`` (M013,
  DEC-0113) — the sole application boundary; COMOS speaks ONLY
  through this surface (the SDK client plus the raw request form
  for webhook endpoint registration);
- the real ``CommercialCore`` in M009 BOUND MODE (DEC-0109) — the
  commercial-terms surface: the commercial reconciliation account
  is bound to THE canonical contract citation (the intent payload
  carries the contract id; every command resolves the citation
  against the injected ``ContractReferenceIndex`` built from the
  ``ContractStore`` public surface; the forward actions respect
  the canonical-state floors — the walk never runs ahead of the
  contract);
- the real ``UsageLedger`` (M009, DEC-0109) — the usage evidence
  attribution: the evidence index is built by the CALLER from the
  realization plane's delivered facts and the contract-cited
  commercial snapshot (``transaction_id`` IS the contract id —
  every usage record is bound to THE contract by construction;
  the sealed statement consumes the tariff resolved from the
  offer's pricing DATA, LOCK-113).

The pending mechanics (M004 constraint-aware selection, M005
assurance, M006 execution plan, M007 realization) are driven
through the disclosed deterministic simulation seams
(:mod:`comos.seams`) — DATA-producing stand-ins, never
authorities, never mutating the canonical contract.  M008
(replan/failover) has NO step in the frozen COMOS flow and is
deliberately absent (disclosed).  M009 is NOT a seam here: it is
accepted (DEC-0109) and composed as real authority.

The three golden scenarios (all deterministic, offline,
byte-stable):

- ``dual-provider-delivery`` — both provider offers satisfy the
  contract's hard constraints; ADCOS selects BOTH (LOCK-116
  composition under one contract); COMOS's step-4 communication
  requirements are satisfied by every committed leg; the
  lifecycle completes to SETTLED with usage evidence attributed
  to the contract and the commercial walk settled.
- ``constraint-exclusion`` — the second provider's offer VIOLATES
  the hard latency constraint; the step-2 selection excludes it
  with the rejection trail (constraint-aware selection); the
  contract binds exactly the one suitable offer; the lifecycle
  completes to SETTLED.
- ``requirements-unsatisfied`` — both offers are contract-suitable
  and selected, but COMOS's step-4 requirements carry a latency
  demand no committed leg satisfies; the evaluation fail-closes,
  the contract FAILS under the typed reason, the commercial
  account compensates (cancel), no usage exists (delivery never
  began), and the submission/selection evidence REMAINS
  attributable to the contract (attribution survives terminal
  failure).

Determinism (LOCK-119): every instant is a module constant; the
delivered-quantity schedule is injected; runs are byte-identical
in-process and cross-process.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

from agent.clock import StepClock
from commercial import (
    CommercialCore,
    ContractCitation,
    ContractReferenceIndex,
    MemoryCommercialStore,
    Reference,
    ReferenceFamily,
    ReferenceIndex,
)
from contracts import (
    ActivateContract,
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
    SelectOffers,
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
from usage import (
    ContractCommercialSnapshot,
    DeliveryEvidence,
    EvidenceKind,
    MemoryUsageStore,
    UsageLedger,
    UsageEvidenceIndex,
)

from .application import (
    COMOS_APPLICATION_NAME,
    COMOS_DEVELOPER_ID,
    COMOS_OWNED_DOMAINS,
    REASON_FAIL_CLOSED,
    ComosApplication,
    ComosError,
    ComosIntentSpec,
)
from .evidence import EvidenceEntry, EvidenceLedger
from .seams import (
    AssuranceSeam,
    DeliveredFact,
    ExecutionPlanSeam,
    FailureSchedule,
    ProviderRealizationSeam,
    SelectionSeam,
)

# ----------------------------------------------------------------------
# The frozen 6-step flow (the exact ACR-014 text)
# ----------------------------------------------------------------------

FROZEN_FLOW: Tuple[str, ...] = (
    "COMOS requests gateway connectivity for communication traffic.",
    "ADCOS selects suitable offers.",
    "A contract is created.",
    "COMOS sends technology-neutral communication requirements.",
    "ADCOS supplies connectivity execution.",
    "COMOS retains authority over identity, communication bundles, "
    "channel semantics and delivery semantics.",
)

#: The COMOS retained-authority statement that closes the frozen
#: spec section (LOCK-120 — asserted by the battery, carried here so
#: the harness self-describes its boundary).
COMOS_RETAINED_AUTHORITY = (
    "COMOS retains authority over identity, communication bundles, "
    "channel semantics and delivery semantics."
)

# ----------------------------------------------------------------------
# Injected deterministic instants (LOCK-119: no wall clock anywhere)
# ----------------------------------------------------------------------

T_VALID_FROM = "2027-01-01T00:00:00Z"
T_VALID_TO = "2027-02-01T00:00:00Z"
T_REQUEST = "2027-01-01T00:01:00Z"
T_ADVERTISE = "2027-01-01T00:02:00Z"
T_SELECTION = "2027-01-01T00:03:00Z"
T_BIND = "2027-01-01T00:04:00Z"
T_ACTIVATE = "2027-01-01T00:05:00Z"
T_REQUIREMENTS = "2027-01-01T00:06:00Z"
T_EXEC = "2027-01-01T00:07:00Z"
T_DELIVERY = "2027-01-01T00:08:00Z"
T_ASSURANCE = "2027-01-01T00:09:00Z"
T_USAGE_FINAL = "2027-01-01T00:10:00Z"
T_SETTLEMENT = "2027-01-01T00:11:00Z"

CREDENTIAL_VALID_UNTIL = "2030-01-01T00:00:00Z"
SERVICE_CLOCK_ORIGIN = "2027-01-01T00:00:30Z"
COMMERCIAL_CLOCK_ORIGIN = "2027-01-01T01:30:00Z"
USAGE_CLOCK_ORIGIN = "2027-01-01T02:00:00Z"
COMMERCIAL_RESERVATION_DEADLINE = "2027-03-01T00:00:00Z"
DELIVERY_WINDOW = (T_DELIVERY, T_ASSURANCE)
ISSUANCE_KEY = b"m012-comos-issuance-key"

#: The two canonical provider domains (the frozen flow composes
#: gateway connectivity over distinct provider domains).
PROVIDER_ALPHA = "adcos:node:identity.sha256-hmac-dev.v1:" + "3" * 64
PROVIDER_BETA = "adcos:node:identity.sha256-hmac-dev.v1:" + "4" * 64

#: The COMOS observation endpoint registration (the deterministic
#: idempotency key predicts the endpoint id — the transport is
#: injected through the service's public constructor).
OBSERVATION_ENDPOINT_KEY = "comos-observation-endpoint"
OBSERVATION_ENDPOINT_URL = "https://comos-app.test/connectivity-observations"
OBSERVATION_EVENT_TYPES = ("connectivity_contract.state_changed",)

#: The external settlement confirmation reference (LOCK-113: the
#: money movement stays on the external rail; ADCOS records the
#: settlement reference only — a deterministic DATA token here).
SETTLEMENT_CONFIRMATION_REF = (
    "m012:settlement:external-rail:confirmation:v1"
)

#: The canonical billable unit of the delivered communication
#: traffic (the usage ledger's canonical quantity unit; the
#: delivered quantities are integers in this unit).
BILLABLE_UNIT = "canonical-traffic-unit"


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
    jitter_ms: int
    price_minor: int
    advertisement_digest: str
    advertisement_classification: str = "known"
    capability_id: str = "capability.core.gateway-transit"
    schema_version: str = "1.2"
    jurisdiction: str = "GH"
    geography_ref: str = "mpcell:v1:coarse-50000m:14:-2"


@dataclass(frozen=True)
class VerticalScenario:
    """One golden scenario: the request's hard constraints, the two
    providers' material, the step-4 requirement envelope, the
    injected delivered-quantity schedule, and the expected terminal
    shape."""

    name: str
    latency_bound_ms: int
    throughput_floor_bps: int
    jitter_bound_ms: int
    providers: Tuple[ProviderMaterial, ...]
    requirements_latency_ms: int
    requirements_throughput_bps: int
    requirements_jitter_ms: int
    delivered_quantities: Tuple[int, ...]
    expected_final_state: str
    expected_selected: int
    expected_rejected: int


#: Provider ALPHA — the primary realization (fast, well-provisioned).
PROVIDER_ALPHA_MATERIAL = ProviderMaterial(
    provider=PROVIDER_ALPHA,
    issuer="provider:comos-primary",
    offer_key="comos:gateway:primary",
    latency_ms=120,
    throughput_kbps=1000,
    jitter_ms=30,
    price_minor=250,
    advertisement_digest="sha256:" + "c" * 64,
)


def _provider_beta_material(latency_ms: int) -> ProviderMaterial:
    return ProviderMaterial(
        provider=PROVIDER_BETA,
        issuer="provider:comos-secondary",
        offer_key="comos:gateway:secondary",
        latency_ms=latency_ms,
        throughput_kbps=800,
        jitter_ms=45,
        price_minor=180,
        advertisement_digest="sha256:" + "d" * 64,
    )


#: The three golden scenarios.
SCENARIO_DUAL_PROVIDER_DELIVERY = "dual-provider-delivery"
SCENARIO_CONSTRAINT_EXCLUSION = "constraint-exclusion"
SCENARIO_REQUIREMENTS_UNSATISFIED = "requirements-unsatisfied"

SCENARIOS: Tuple[VerticalScenario, ...] = (
    VerticalScenario(
        name=SCENARIO_DUAL_PROVIDER_DELIVERY,
        latency_bound_ms=200,
        throughput_floor_bps=500,
        jitter_bound_ms=50,
        providers=(
            PROVIDER_ALPHA_MATERIAL,
            _provider_beta_material(latency_ms=180),
        ),
        requirements_latency_ms=190,
        requirements_throughput_bps=500,
        requirements_jitter_ms=50,
        delivered_quantities=(400, 350),
        expected_final_state="SETTLED",
        expected_selected=2,
        expected_rejected=0,
    ),
    VerticalScenario(
        name=SCENARIO_CONSTRAINT_EXCLUSION,
        latency_bound_ms=150,
        throughput_floor_bps=500,
        jitter_bound_ms=50,
        providers=(
            PROVIDER_ALPHA_MATERIAL,
            _provider_beta_material(latency_ms=180),
        ),
        requirements_latency_ms=160,
        requirements_throughput_bps=500,
        requirements_jitter_ms=50,
        delivered_quantities=(750,),
        expected_final_state="SETTLED",
        expected_selected=1,
        expected_rejected=1,
    ),
    VerticalScenario(
        name=SCENARIO_REQUIREMENTS_UNSATISFIED,
        latency_bound_ms=200,
        throughput_floor_bps=500,
        jitter_bound_ms=50,
        providers=(
            PROVIDER_ALPHA_MATERIAL,
            _provider_beta_material(latency_ms=180),
        ),
        requirements_latency_ms=100,
        requirements_throughput_bps=500,
        requirements_jitter_ms=50,
        delivered_quantities=(),
        expected_final_state="FAILED",
        expected_selected=2,
        expected_rejected=0,
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
    offer_ids: Tuple[str, ...]
    selected_offer_ids: Tuple[str, ...]
    selection: Mapping[str, Any]
    requirements: Mapping[str, Any]
    plan_segments: Tuple[Mapping[str, Any], ...]
    usage: Mapping[str, Any]
    commercial: Mapping[str, Any]
    attribution: Mapping[str, Any]
    observation_deliveries: Tuple[Mapping[str, Any], ...]
    journal_digest: str
    usage_ledger_digest: str
    commercial_journal_digest: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario": self.scenario,
            "steps": [record.to_dict() for record in self.steps],
            "contract_id": self.contract_id,
            "final_state": self.final_state,
            "offer_ids": list(self.offer_ids),
            "selected_offer_ids": list(self.selected_offer_ids),
            "selection": dict(self.selection),
            "requirements": dict(self.requirements),
            "plan_segments": [dict(segment) for segment in self.plan_segments],
            "usage": dict(self.usage),
            "commercial": dict(self.commercial),
            "attribution": dict(self.attribution),
            "observation_deliveries": [
                dict(delivery) for delivery in self.observation_deliveries
            ],
            "journal_digest": self.journal_digest,
            "usage_ledger_digest": self.usage_ledger_digest,
            "commercial_journal_digest": self.commercial_journal_digest,
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

#: The canonical COMOS connectivity request of one scenario (the
#: frozen technology-neutral creation core: WHAT COMOS needs, never
#: HOW — LOCK-102/LOCK-114; the beneficiaries ride OPAQUE identity
#: references — LOCK-120).
def _intent_spec(
    scenario: VerticalScenario, beneficiaries: Tuple[Tuple[str, str], ...]
) -> ComosIntentSpec:
    return ComosIntentSpec(
        purpose="comos:gateway-connectivity:communication-traffic",
        requirements=(
            "req:comos:gateway-backhaul",
            "req:comos:communication-traffic",
        ),
        validity=(T_VALID_FROM, T_VALID_TO),
        termination_conditions=(
            "principal-requested",
            "validity-expired",
            "constraint-violated",
        ),
        compensation="comp:comos:prorated-v1",
        beneficiaries=beneficiaries,
        hard_constraints=(
            ("latency-bound", (("ms", scenario.latency_bound_ms),)),
            ("throughput-floor", (("bps", scenario.throughput_floor_bps),)),
            ("jitter-bound", (("ms", scenario.jitter_bound_ms),)),
        ),
        service_properties=("prop:comos:gateway-class-v1",),
        usage_pricing_terms="comos:commercial:terms-v1",
        assurance_obligations=("oblig:comos:continuity-v1",),
        execution_scope=("scope:comos:gateway-egress-v1",),
    )


def _tariff_micros(price: OfferPricing) -> int:
    """The integer tariff (micro currency units per canonical
    billable unit) resolved deterministically from the REAL offer
    pricing DATA read through the exchange public surface (the
    M009 caller-resolution discipline: the tariff is DATA the
    caller resolves; LOCK-113 — a reference to terms, never
    payment authority)."""
    return price.price_minor * (10 ** (6 - price.price_exponent))


class ComosVertical:
    """The M012 vertical proof harness: one scenario, composed over
    the REAL accepted authorities, driven through the frozen 6-step
    flow with the disclosed deterministic seams.

    Construction composes (all real, all public-surface):

    - ``ContractStore`` — the canonical contract authority (M002);
    - ``OfferExchange`` — the canonical offer authority (M003), with
      the scenario's provider material registered as real
      capability advertisements and offers;
    - ``DeveloperApiService`` (sandbox) over the store, with the
      deterministic StepClock, the platform issuance key, and the
      COMOS observation transport injected through the public
      constructor;
    - ``ComosApplication`` — the external boundary over the M013
      SDK client;
    - ``EvidenceLedger`` bound to the real store;
    - the four disclosed simulation seams.

    The commercial core (M009 bound mode) and the usage ledger
    (M009) are composed DURING ``run()`` at the flow points where
    their inputs exist (the commercial citation snapshots and the
    delivered facts) — both through their public constructors only.
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
            COMOS_DEVELOPER_ID,
            OBSERVATION_ENDPOINT_KEY,
        )
        self._received: List[Dict[str, Any]] = []

        def _transport(endpoint: str, url: str, payload: Mapping[str, Any],
                       headers: Mapping[str, str]) -> Tuple[bool, int]:
            self._received.append(dict(payload))
            # the COMOS application is the endpoint consumer (it
            # observes; it never decides — LOCK-120)
            app = getattr(self, "_app", None)
            if app is not None:
                app.receive_observation(payload, headers)
            return (True, 200)

        self._service = DeveloperApiService(
            environment="sandbox",
            contracts=self._contracts,
            store=MemoryApiStore(),
            clock=self._clock,
            issuance_key=issuance_key,
            delivery_transports={endpoint_id: _transport},
        )
        # the COMOS application credential (platform out-of-band
        # issuance; LOCK-103: an APPLICATION principal may sponsor)
        issued = self._service.issue_application_credential(
            developer_id=COMOS_DEVELOPER_ID,
            application_name=COMOS_APPLICATION_NAME,
            capabilities=Capability.values(),
            valid_until=CREDENTIAL_VALID_UNTIL,
            key_material="m012-comos-application-key",
            actor="platform",
        )
        client = DeveloperApiClient(
            transport=self._service.handle,
            application_id=issued.record.application_id,
            secret=issued.secret,
            api_version="2.0",
            environment="sandbox",
        )
        self._app = ComosApplication(
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
        self._selection = SelectionSeam()
        self._assurance = AssuranceSeam()
        self._planner = ExecutionPlanSeam()
        self._realization = ProviderRealizationSeam()
        self._ledger = EvidenceLedger(contracts=self._contracts)
        self._assurance_sequence = 0
        # the M009 authorities composed during run()
        self._usage_ledger: Optional[UsageLedger] = None
        self._commercial: Optional[CommercialCore] = None
        self._commercial_transaction_id = ""
        self._commercial_chain: List[str] = []
        # the injected deterministic realization schedule (the
        # frozen COMOS flow scripts a HEALTHY delivery)
        self._schedule = FailureSchedule(events=())

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
                decision_refs=("comos:provider:v1",),
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
                        decision_refs=("comos:provider:v1",),
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
                        decision_refs=("comos:commitment:latency",),
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
                        decision_refs=("comos:commitment:throughput",),
                    ),
                ),
                OfferCommitment(
                    kind="jitter-bound-ms",
                    params={"max_ms": material.jitter_ms},
                    window=ValidityInterval(
                        not_before=T_VALID_FROM, not_after=T_VALID_TO
                    ),
                    provenance=Provenance(
                        issuer=material.issuer,
                        decision_refs=("comos:commitment:jitter",),
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
                    decision_refs=("comos:pricing:v1",),
                ),
            ),
            service_boundaries=(
                ServiceBoundary(
                    jurisdiction=material.jurisdiction,
                    geography_refs=(material.geography_ref,),
                    provenance=Provenance(
                        issuer=material.issuer,
                        decision_refs=("comos:boundary:v1",),
                    ),
                ),
            ),
            validity=ValidityInterval(
                not_before=T_VALID_FROM, not_after=T_VALID_TO
            ),
            provenance=Provenance(
                issuer=material.issuer,
                decision_refs=("comos:offer:v1",),
            ),
        )
        self._exchange.register_offer(offer)
        self._offer_ids.append(offer.offer_id)

    # -- evidence helpers --------------------------------------------

    def _next_assurance_sequence(self) -> int:
        self._assurance_sequence += 1
        return self._assurance_sequence

    def _observe(self, contract_id: str) -> None:
        """Push the canonical current state through the observation
        channel and pump the deterministic deliveries."""
        self._service.observe_contract(contract_id)
        self._service.process_due_deliveries()

    def _decision_reference(self, token: str, issuer: str) -> OpaqueReference:
        return OpaqueReference(
            ref_kind="decision",
            value=token,
            provenance=Provenance(
                issuer=issuer,
                decision_refs=(token,),
            ),
        )

    # -- the M009 commercial composition (bound mode) ----------------

    def _commercial_citation_index(self) -> ContractReferenceIndex:
        """The immutable citation index snapshot built from the REAL
        ``ContractStore`` public surface (the caller reads the
        contract identity + CURRENT state; the commercial walk
        never runs ahead of the contract)."""
        contract = self._contracts.contract(self._contract_id)
        return ContractReferenceIndex(
            [
                ContractCitation(
                    contract_id=contract.contract_id,
                    contract_state=contract.state,
                    provenance="contracts.ContractStore:public-read",
                )
            ]
        )

    def _commercial_reference_index(
        self,
        *,
        session_refs: Tuple[str, ...],
        path_refs: Tuple[str, ...],
        evidence_refs: Tuple[str, ...] = (),
        usage_refs: Tuple[str, ...] = (),
        settlement_refs: Tuple[str, ...] = (),
    ) -> ReferenceIndex:
        """The injected external-reference index: the causal
        citations the commercial walk resolves (the seam-produced
        realization session/path tokens, the delivered-fact evidence
        ids, the REAL usage observation ids, and the external
        settlement confirmation — all DATA)."""
        entries: List[Reference] = []
        entries.extend(
            Reference(
                reference_id=ref,
                family=ReferenceFamily.SESSION,
                provenance="m007-seam:realization-session",
            )
            for ref in session_refs
        )
        entries.extend(
            Reference(
                reference_id=ref,
                family=ReferenceFamily.NETWORK_PATH,
                provenance="m006-seam:plan-segment",
            )
            for ref in path_refs
        )
        entries.extend(
            Reference(
                reference_id=ref,
                family=ReferenceFamily.DELIVERY_EVIDENCE,
                provenance="m007-seam:delivered-fact",
            )
            for ref in evidence_refs
        )
        entries.extend(
            Reference(
                reference_id=ref,
                family=ReferenceFamily.USAGE,
                provenance="usage.UsageLedger:public-read",
            )
            for ref in usage_refs
        )
        entries.extend(
            Reference(
                reference_id=ref,
                family=ReferenceFamily.SETTLEMENT,
                provenance="external-settlement-rail:confirmation",
            )
            for ref in settlement_refs
        )
        return ReferenceIndex(entries)

    def _commercial_submit(self, action: str, outcome) -> None:
        """Record one commercial command outcome (deterministic
        chain + state) — the outcome objects are the authority's
        own public values."""
        self._commercial_chain.append(action)
        if outcome.to_state == "CONNECTIVITY_INTENT" and action == "submit_intent":
            self._commercial_transaction_id = outcome.transaction_id

    def _commercial_walk_pre_execution(
        self, *, session_refs: Tuple[str, ...], path_refs: Tuple[str, ...]
    ) -> None:
        """Compose the REAL M009 commercial core (bound mode) and
        mirror the canonical contract's pre-execution lifecycle:
        submit_intent -> select_offer -> hold_reservation ->
        authorize_session -> activate_path.

        The citation snapshot is taken at the contract's CURRENT
        (CONTRACT_ACTIVE) state: every forward action's canonical
        floor is satisfied, so the commercial walk runs strictly
        behind the contract (LOCK-113/LOCK-101)."""
        self._commercial_clock = StepClock(COMMERCIAL_CLOCK_ORIGIN, 60)
        self._commercial_store = MemoryCommercialStore()
        self._commercial = CommercialCore(
            store=self._commercial_store,
            clock=self._commercial_clock,
            references=self._commercial_reference_index(
                session_refs=session_refs, path_refs=path_refs
            ),
            contract_references=self._commercial_citation_index(),
        )
        cid = self._contract_id
        out = self._commercial.submit_intent(
            command_id="m012-commercial-01",
            actor="adcos:m012-vertical",
            source="comos-vertical-harness",
            intent={
                "buyer": "comos-application",
                "want": "gateway-connectivity",
                "traffic": "communication",
                "purpose": "comos:gateway-connectivity:communication-traffic",
                "contract_id": cid,
            },
        )
        self._commercial_submit("submit_intent", out)
        tx = self._commercial_transaction_id
        primary = self._selected_offers[0]
        out = self._commercial.select_offer(
            command_id="m012-commercial-02",
            transaction_id=tx,
            actor="adcos:m012-vertical",
            source="comos-vertical-harness",
            offer={
                "offer_id": primary.offer_id,
                "provider": primary.provider,
                "pricing_currency": primary.pricing.currency,
                "price_minor": primary.pricing.price_minor,
                "billable_unit": BILLABLE_UNIT,
            },
        )
        self._commercial_submit("select_offer", out)
        out = self._commercial.hold_reservation(
            command_id="m012-commercial-03",
            transaction_id=tx,
            actor="adcos:m012-vertical",
            source="comos-vertical-harness",
            expires_at=COMMERCIAL_RESERVATION_DEADLINE,
        )
        self._commercial_submit("hold_reservation", out)
        out = self._commercial.authorize_session(
            command_id="m012-commercial-04",
            transaction_id=tx,
            actor="adcos:m012-vertical",
            source="comos-vertical-harness",
            session_ref=session_refs[0],
        )
        self._commercial_submit("authorize_session", out)
        out = self._commercial.activate_path(
            command_id="m012-commercial-05",
            transaction_id=tx,
            actor="adcos:m012-vertical",
            source="comos-vertical-harness",
            path_ref=path_refs[0],
        )
        self._commercial_submit("activate_path", out)

    def _commercial_walk_post_execution(
        self,
        *,
        session_refs: Tuple[str, ...],
        path_refs: Tuple[str, ...],
        evidence_refs: Tuple[str, ...],
        usage_refs: Tuple[str, ...],
    ) -> None:
        """Continue the mirroring walk after the canonical contract
        reached SETTLED: reload the REAL commercial core
        (journal-first recovery over the SAME store — the sanctioned
        continuation path) with the citation snapshot advanced to
        the contract's current state, then mirror the execution
        lifecycle: start_delivery -> accrue_usage ->
        complete_delivery -> finalize_billable ->
        initiate_settlement -> settle.

        The reload demonstrates the frozen-index discipline: the
        citation snapshot is rebuilt from the contract's CURRENT
        public state; the walk never runs ahead of the contract."""
        self._commercial = CommercialCore.load(
            store=self._commercial_store,
            clock=self._commercial_clock,
            references=self._commercial_reference_index(
                session_refs=session_refs,
                path_refs=path_refs,
                evidence_refs=evidence_refs,
                usage_refs=usage_refs,
                settlement_refs=(SETTLEMENT_CONFIRMATION_REF,),
            ),
            contract_references=self._commercial_citation_index(),
        )
        tx = self._commercial_transaction_id
        out = self._commercial.start_delivery(
            command_id="m012-commercial-06",
            transaction_id=tx,
            actor="adcos:m012-vertical",
            source="comos-vertical-harness",
            evidence_refs=evidence_refs,
        )
        self._commercial_submit("start_delivery", out)
        out = self._commercial.accrue_usage(
            command_id="m012-commercial-07",
            transaction_id=tx,
            actor="adcos:m012-vertical",
            source="comos-vertical-harness",
            usage_refs=usage_refs,
        )
        self._commercial_submit("accrue_usage", out)
        out = self._commercial.complete_delivery(
            command_id="m012-commercial-08",
            transaction_id=tx,
            actor="adcos:m012-vertical",
            source="comos-vertical-harness",
            evidence_refs=evidence_refs,
        )
        self._commercial_submit("complete_delivery", out)
        out = self._commercial.finalize_billable(
            command_id="m012-commercial-09",
            transaction_id=tx,
            actor="adcos:m012-vertical",
            source="comos-vertical-harness",
        )
        self._commercial_submit("finalize_billable", out)
        out = self._commercial.initiate_settlement(
            command_id="m012-commercial-10",
            transaction_id=tx,
            actor="adcos:m012-vertical",
            source="comos-vertical-harness",
        )
        self._commercial_submit("initiate_settlement", out)
        out = self._commercial.settle(
            command_id="m012-commercial-11",
            transaction_id=tx,
            actor="adcos:m012-vertical",
            source="comos-vertical-harness",
            settlement_refs=(SETTLEMENT_CONFIRMATION_REF,),
        )
        self._commercial_submit("settle", out)

    def _commercial_cancel(self) -> None:
        """The compensating path when the contract fails before
        execution: cancel the commercial account (pre-delivery
        compensating record; the citation resolves — the commercial
        domain never runs ahead, and settles nothing when nothing
        was delivered)."""
        out = self._commercial.cancel(
            command_id="m012-commercial-cancel",
            transaction_id=self._commercial_transaction_id,
            actor="adcos:m012-vertical",
            source="comos-vertical-harness",
        )
        self._commercial_submit("cancel", out)

    # -- the M009 usage composition -----------------------------------

    def _usage_walk(
        self, facts: Tuple[DeliveredFact, ...]
    ) -> Dict[str, Any]:
        """Compose the REAL M009 usage ledger and observe the
        delivered communication traffic.

        The evidence index is built by the CALLER (this harness)
        from the realization plane's delivered facts (mapped onto
        the real ``DeliveryEvidence`` values — transaction_id IS
        the contract id) and the contract-cited commercial
        snapshot (the tariff resolved from the REAL offer pricing
        DATA; the contract state read through the store's public
        surface).  Every observation admitted against the index is
        bound to THE contract by construction (the account key is
        the contract citation — LOCK-113)."""
        contract = self._contracts.contract(self._contract_id)
        primary = self._selected_offers[0]
        snapshot = ContractCommercialSnapshot(
            transaction_id=contract.contract_id,
            commercial_state=contract.state,
            unit_price_micros=_tariff_micros(primary.pricing),
            billable_unit=BILLABLE_UNIT,
            tariff_provenance=(
                "offers.OfferExchange:offer.pricing+comos-harness-"
                "tariff-resolution"
            ),
        )
        evidence_records = tuple(
            DeliveryEvidence(
                evidence_id=fact.evidence_id,
                transaction_id=contract.contract_id,
                delivered_quantity=fact.delivered_quantity,
                window_start=fact.window_start,
                window_end=fact.window_end,
                evidence_kind=EvidenceKind.DELIVERED,
                provenance="m007-seam:realization-delivery",
            )
            for fact in facts
        )
        index = UsageEvidenceIndex(
            evidence=evidence_records, transactions=(snapshot,)
        )
        self._usage_ledger = UsageLedger(
            store=MemoryUsageStore(),
            clock=StepClock(USAGE_CLOCK_ORIGIN, 60),
            evidence_index=index,
        )
        observation_ids: List[str] = []
        for position, fact in enumerate(facts, start=1):
            outcome = self._usage_ledger.observe_usage(
                command_id="m012-usage-observation-%d" % position,
                transaction_id=contract.contract_id,
                quantity_class="delivered",
                quantity=fact.delivered_quantity,
                evidence_id=fact.evidence_id,
                window_start=fact.window_start,
                window_end=fact.window_end,
                actor="adcos:m012-vertical",
                source="comos-vertical-harness",
            )
            observation_ids.append(outcome.fact_id)
            # the typed attribution record: the entry token IS the
            # observation id the REAL authority derived (DATA read
            # through the authority's public surface)
            self._ledger.record(
                EvidenceEntry(
                    kind="usage-observation",
                    contract_id=contract.contract_id,
                    recorded_at=outcome.instant,
                    token=outcome.fact_id,
                    issuer="m009-authority:usage-observation",
                    decision_refs=(fact.evidence_id,),
                    payload={
                        "delivered_quantity": fact.delivered_quantity,
                        "command_id": outcome.command_id,
                    },
                )
            )
        seal = self._usage_ledger.seal_billable(
            command_id="m012-usage-seal",
            transaction_id=contract.contract_id,
            actor="adcos:m012-vertical",
            source="comos-vertical-harness",
        )
        statement = self._usage_ledger.reconciliation_statement(
            contract.contract_id
        )
        return {
            "observation_ids": observation_ids,
            "sealed": seal.to_state == "BILLABLE_FINAL",
            "billable_quantity": statement["billable_quantity"],
            "unit_price_micros": statement["unit_price_micros"],
            "gross_amount_micros": statement["gross_amount_micros"],
            "statement_id": statement["statement_id"],
            "usage_state": statement["usage_state"],
        }

    # -- the frozen 6-step flow --------------------------------------

    def run(self) -> VerticalResult:
        scenario = self._scenario
        steps: List[StepRecord] = []
        contract_id: Optional[str] = None

        # STEP 1 — COMOS requests gateway connectivity for
        # communication traffic (through the M013 surface ONLY)
        intent = self._app.submit_connectivity_request(
            spec=_intent_spec(scenario, self._app.opaque_beneficiaries()),
            idempotency_key="comos-connectivity-request",
            recorded_at=T_REQUEST,
        )
        contract_id = intent.id
        self._contract_id = contract_id
        contract = self._contracts.contract(contract_id)
        if contract.state != "INTENT":
            raise ComosError(
                REASON_FAIL_CLOSED,
                "step 1: the canonical contract must be created in INTENT "
                "state (found %s)" % contract.state,
            )
        steps.append(
            StepRecord(
                step=1,
                title=FROZEN_FLOW[0],
                instant=T_REQUEST,
                outcome="request-submitted",
                detail="technology-neutral request accepted through the "
                "M013 SDK surface; principal=APPLICATION:%s; "
                "beneficiaries=opaque-identity-refs"
                % self._app.application_id[:24],
                contract_id=contract_id,
            )
        )
        self._observe(contract_id)

        # STEP 2 — ADCOS selects suitable offers (the M004 seam over
        # the REAL offers and the REAL hard constraints)
        advertised = self._exchange.offers()
        if len(advertised) < 2:
            raise ComosError(
                REASON_FAIL_CLOSED,
                "step 2: the frozen flow requires at least two advertised "
                "offers (found %d)" % len(advertised),
            )
        contract = self._contracts.contract(contract_id)
        selection = self._selection.select(
            offers=advertised,
            constraints=contract.hard_constraints,
            at_instant=T_SELECTION,
        )
        if not selection.selected_ids:
            raise ComosError(
                REASON_FAIL_CLOSED,
                "step 2: no advertised offer is suitable; the vertical "
                "cannot proceed (fail-closed)",
            )
        self._selected_offers = tuple(
            self._exchange.offer(offer_id)
            for offer_id in selection.selected_ids
        )
        # the typed selection evidence (attributed to THE contract)
        self._ledger.record(
            EvidenceEntry(
                kind="selection-decision",
                contract_id=contract_id,
                recorded_at=T_SELECTION,
                token="m004-seam:selection:%s" % T_SELECTION,
                issuer="m004-seam:selection",
                decision_refs=tuple(selection.selected_ids),
                payload={
                    "advertised": len(selection.decisions),
                    "selected": len(selection.selected_ids),
                    "rejected": len(selection.rejected_ids),
                },
            )
        )
        steps.append(
            StepRecord(
                step=2,
                title=FROZEN_FLOW[1],
                instant=T_SELECTION,
                outcome="offers-selected",
                detail="%d suitable of %d advertised (seam: M004 pending); "
                "constraint-aware selection over the real M003 exchange"
                % (len(selection.selected_ids), len(selection.decisions)),
                contract_id=contract_id,
            )
        )

        # STEP 3 — a contract is created (ADCOS binds the selected
        # offers and activates through the canonical command
        # surface; exactly ONE contract identity carries the flow)
        references = tuple(
            offer_reference(offer) for offer in self._selected_offers
        )
        self._contracts.submit(
            SelectOffers(offers=references),
            T_BIND,
            contract_id=contract_id,
        )
        self._contracts.submit(
            ActivateContract(
                activated_at=T_ACTIVATE,
                signature_refs=(
                    OpaqueReference(
                        ref_kind="signature",
                        value="sig:comos:application-sponsorship:v1",
                        provenance=Provenance(
                            issuer="comos-application-sponsorship",
                            decision_refs=("comos:sponsorship:v1",),
                        ),
                    ),
                ),
            ),
            T_ACTIVATE,
            contract_id=contract_id,
        )
        contract = self._contracts.contract(contract_id)
        if contract.state != "CONTRACT_ACTIVE":
            raise ComosError(
                REASON_FAIL_CLOSED,
                "step 3: the contract must be CONTRACT_ACTIVE after offer "
                "binding and activation (found %s)" % contract.state,
            )
        if len(self._contracts.contracts()) != 1:
            raise ComosError(
                REASON_FAIL_CLOSED,
                "step 3: the frozen flow creates exactly ONE contract "
                "(found %d)" % len(self._contracts.contracts()),
            )
        # the execution plan (the M006 seam over the accepted
        # offers — the LOCK-109 bridge, simulated)
        plan = self._planner.build_plan(
            contract=contract,
            exchange=self._exchange,
            at_instant=T_BIND,
        )
        session_refs = tuple(
            segment.session_token for segment in plan.segments
        )
        path_refs = tuple(segment.path_token for segment in plan.segments)
        # the M009 commercial mirroring walk (pre-execution phase)
        self._commercial_walk_pre_execution(
            session_refs=session_refs, path_refs=path_refs
        )
        steps.append(
            StepRecord(
                step=3,
                title=FROZEN_FLOW[2],
                instant=T_ACTIVATE,
                outcome="contract-created",
                detail="exactly one contract; %d selected offer references "
                "bound (typed references via the M003 bridge); plan over "
                "%d segment(s); commercial account opened against the "
                "contract citation (M009 real)"
                % (len(references), len(plan.segments)),
                contract_id=contract_id,
            )
        )
        self._observe(contract_id)

        # STEP 4 — COMOS sends technology-neutral communication
        # requirements; ADCOS evaluates them against the contract's
        # committed terms (the requirements NEVER mutate the
        # contract)
        requirements_spec = self._app.derive_requirements(
            latency_bound_ms=scenario.requirements_latency_ms,
            jitter_bound_ms=scenario.requirements_jitter_ms,
            throughput_floor_bps=scenario.requirements_throughput_bps,
        )
        requirements_document = self._app.submit_communication_requirements(
            spec=requirements_spec, recorded_at=T_REQUIREMENTS
        )
        from .seams import evaluate_requirements_against_offer

        evaluations = tuple(
            evaluate_requirements_against_offer(
                requirements=requirements_document, offer=offer
            )
            for offer in self._selected_offers
        )
        violated_dimensions = sorted(
            {
                dimension
                for evaluation in evaluations
                for dimension in evaluation.violated
            }
        )
        requirements_satisfied = not violated_dimensions
        # the typed requirements-submission evidence (the submission
        # itself is attributable DATA — satisfied or not)
        self._ledger.record(
            EvidenceEntry(
                kind="requirements-submission",
                contract_id=contract_id,
                recorded_at=T_REQUIREMENTS,
                token="m012:requirements:%s" % T_REQUIREMENTS,
                issuer="comos-application:communication-requirements",
                decision_refs=(requirements_spec.purpose,),
                payload={
                    "latency_bound_ms": scenario.requirements_latency_ms,
                    "jitter_bound_ms": scenario.requirements_jitter_ms,
                    "throughput_floor_bps": (
                        scenario.requirements_throughput_bps
                    ),
                    "violated_dimensions": len(violated_dimensions),
                    "satisfied": 1 if requirements_satisfied else 0,
                },
            )
        )
        if requirements_satisfied:
            steps.append(
                StepRecord(
                    step=4,
                    title=FROZEN_FLOW[3],
                    instant=T_REQUIREMENTS,
                    outcome="requirements-satisfied",
                    detail="technology-neutral requirements submitted; "
                    "every committed leg satisfies the envelope "
                    "(%d evaluation(s), 0 violated; the requirements "
                    "mutate nothing — evaluation only)"
                    % len(evaluations),
                    contract_id=contract_id,
                )
            )
        else:
            # LOCK-108-adjacent fail-closed: the committed terms
            # violate the stated envelope; the contract fails under
            # the typed reason (never a weakened requirement, never
            # a silent pass)
            failure_reason = "m012:requirements-unsatisfied:%s" % (
                "+".join(violated_dimensions)
            )
            self._contracts.submit(
                FailContract(
                    recorded_at=T_REQUIREMENTS, reason=failure_reason
                ),
                T_REQUIREMENTS,
                contract_id=contract_id,
            )
            steps.append(
                StepRecord(
                    step=4,
                    title=FROZEN_FLOW[3],
                    instant=T_REQUIREMENTS,
                    outcome="requirements-unsatisfied",
                    detail="technology-neutral requirements submitted; "
                    "the committed legs violate the envelope (%s); the "
                    "contract FAILED under the typed reason (fail-closed)"
                    % "+".join(violated_dimensions),
                    contract_id=contract_id,
                )
            )
            self._observe(contract_id)
            # the commercial account compensates: nothing was
            # delivered, nothing settles (the M009 discipline)
            self._commercial_cancel()

        # STEP 5 — ADCOS supplies connectivity execution
        usage_outcome: Dict[str, Any] = {
            "observation_ids": [],
            "sealed": 0,
            "billable_quantity": 0,
            "unit_price_micros": 0,
            "gross_amount_micros": 0,
            "statement_id": "",
            "usage_state": "",
        }
        if requirements_satisfied:
            for segment in plan.segments:
                self._contracts.submit(
                    BindExecutionArtifact(
                        artifact=segment.artifact_reference()
                    ),
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
            primary = plan.segments[0]
            primary_status = self._realization.status_at(
                provider=primary.provider,
                schedule=self._schedule,
                at_instant=T_ASSURANCE,
            )
            state, token = self._assurance.observe(
                realization_status=primary_status,
                obligations=tuple(
                    ref.value for ref in contract.assurance_obligations
                ),
                at_instant=T_ASSURANCE,
                sequence=self._next_assurance_sequence(),
            )
            if state != "compliant":
                raise ComosError(
                    REASON_FAIL_CLOSED,
                    "step 5: the primary realization must be healthy at "
                    "execution (observed %s)" % state,
                )
            self._ledger.record(
                EvidenceEntry(
                    kind="assurance-evaluation",
                    contract_id=contract_id,
                    recorded_at=T_ASSURANCE,
                    token=token,
                    issuer="m005-seam:assurance-observation",
                    decision_refs=(token,),
                    payload={"assurance_state": 1},
                )
            )
            requirements_decision = (
                "m012-decision:requirements:satisfied"
                if requirements_satisfied
                else "m012-decision:requirements:unsatisfied"
            )
            self._contracts.submit(
                RecordAssurance(
                    recorded_at=T_ASSURANCE,
                    assurance_state="compliant",
                    evidence_refs=(
                        self._decision_reference(
                            requirements_decision,
                            "m012:requirements-evaluation",
                        ),
                        self._decision_reference(
                            token, "m005-seam:assurance-observation"
                        ),
                    ),
                ),
                T_ASSURANCE,
                contract_id=contract_id,
            )
            # the delivered facts -> the REAL M009 usage ledger
            facts = self._realization.delivered_facts(
                segments=plan.segments,
                quantities=scenario.delivered_quantities,
                windows=(DELIVERY_WINDOW,) * len(
                    scenario.delivered_quantities
                ),
            )
            usage_outcome = self._usage_walk(facts)
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
            # the M009 commercial mirroring walk (post-execution
            # phase: reload with the advanced citation snapshot)
            self._commercial_walk_post_execution(
                session_refs=session_refs,
                path_refs=path_refs,
                evidence_refs=tuple(fact.evidence_id for fact in facts),
                usage_refs=tuple(usage_outcome["observation_ids"]),
            )
            steps.append(
                StepRecord(
                    step=5,
                    title=FROZEN_FLOW[4],
                    instant=T_EXEC,
                    outcome="connectivity-executed",
                    detail="plan over %d segment(s); artifacts bound as "
                    "DATA (LOCK-117); execution-activation, delivery, "
                    "compliant assurance recorded; %d usage observation(s) "
                    "admitted by the REAL M009 ledger and sealed "
                    "(billable %d %s); commercial walk settled (M009 real)"
                    % (
                        len(plan.segments),
                        len(usage_outcome["observation_ids"]),
                        usage_outcome["billable_quantity"],
                        BILLABLE_UNIT,
                    ),
                    contract_id=contract_id,
                )
            )
            self._observe(contract_id)
        else:
            steps.append(
                StepRecord(
                    step=5,
                    title=FROZEN_FLOW[4],
                    instant=T_REQUIREMENTS,
                    outcome="execution-not-supplied",
                    detail="the contract failed at step 4; no execution "
                    "commands exist on the journal (honest termination)",
                    contract_id=contract_id,
                )
            )

        # STEP 6 — the LOCK-120 boundary record: COMOS retains
        # authority over identity, communication bundles, channel
        # semantics and delivery semantics (a standing boundary,
        # asserted in every scenario — including terminal failure)
        contract = self._contracts.contract(contract_id)
        if contract.state != scenario.expected_final_state:
            raise ComosError(
                REASON_FAIL_CLOSED,
                "scenario %s: expected terminal state %s, found %s"
                % (scenario.name, scenario.expected_final_state, contract.state),
            )
        if len(selection.selected_ids) != scenario.expected_selected:
            raise ComosError(
                REASON_FAIL_CLOSED,
                "scenario %s: expected %d selected offers, found %d"
                % (
                    scenario.name,
                    scenario.expected_selected,
                    len(selection.selected_ids),
                ),
            )
        if len(selection.rejected_ids) != scenario.expected_rejected:
            raise ComosError(
                REASON_FAIL_CLOSED,
                "scenario %s: expected %d rejected offers, found %d"
                % (
                    scenario.name,
                    scenario.expected_rejected,
                    len(selection.rejected_ids),
                ),
            )
        attribution = self._ledger.attribution(contract_id)
        commercial_state = (
            self._commercial.transaction(
                self._commercial_transaction_id
            ).state
            if self._commercial is not None
            and self._commercial_transaction_id
            else ""
        )
        steps.append(
            StepRecord(
                step=6,
                title=FROZEN_FLOW[5],
                instant=T_REQUIREMENTS
                if not requirements_satisfied
                else T_SETTLEMENT,
                outcome="boundary-retained",
                detail="COMOS retains %s; the application spoke only "
                "through the M013 public surface and holds no ADCOS "
                "authority; ADCOS supplied gateway connectivity only "
                "(state %s; commercial %s)"
                % (
                    "/".join(COMOS_OWNED_DOMAINS),
                    contract.state,
                    commercial_state,
                ),
                contract_id=contract_id,
            )
        )
        self._observe(contract_id)

        requirements_summary: Dict[str, Any] = {
            "document": dict(requirements_document),
            "satisfied": 1 if requirements_satisfied else 0,
            "violated_dimensions": list(violated_dimensions),
            "evaluations": [
                evaluation.to_dict() for evaluation in evaluations
            ],
        }
        plan_segments = tuple(
            {
                "provider": segment.provider,
                "offer_id": segment.offer_id,
                "artifact_token": segment.artifact_token,
                "session_token": segment.session_token,
                "path_token": segment.path_token,
                "role": segment.role,
            }
            for segment in plan.segments
        )
        commercial_summary: Dict[str, Any] = {
            "transaction_id": self._commercial_transaction_id,
            "state": commercial_state,
            "chain": list(self._commercial_chain),
            "contract_binding": contract_id,
        }
        usage_ledger_digest = (
            self._usage_ledger.digest_stream()
            if self._usage_ledger is not None
            else ""
        )
        commercial_journal_digest = (
            self._commercial.journal_digest()
            if self._commercial is not None
            else ""
        )
        return VerticalResult(
            scenario=scenario.name,
            steps=tuple(steps),
            contract_id=contract_id,
            final_state=contract.state,
            offer_ids=tuple(sorted(self._offer_ids)),
            selected_offer_ids=tuple(selection.selected_ids),
            selection=selection.to_dict(),
            requirements=requirements_summary,
            plan_segments=plan_segments,
            usage=usage_outcome,
            commercial=commercial_summary,
            attribution=attribution.to_dict(),
            observation_deliveries=tuple(self._received),
            journal_digest=self._contracts.journal_digest(),
            usage_ledger_digest=usage_ledger_digest,
            commercial_journal_digest=commercial_journal_digest,
        )


def run_scenario(scenario: VerticalScenario) -> VerticalResult:
    """Run one golden scenario (the module-level convenience)."""
    return ComosVertical(scenario=scenario).run()


__all__ = [
    "BILLABLE_UNIT",
    "COMOS_RETAINED_AUTHORITY",
    "FROZEN_FLOW",
    "OBSERVATION_ENDPOINT_KEY",
    "OBSERVATION_ENDPOINT_URL",
    "OBSERVATION_EVENT_TYPES",
    "PROVIDER_ALPHA",
    "PROVIDER_ALPHA_MATERIAL",
    "PROVIDER_BETA",
    "SCENARIOS",
    "SCENARIO_CONSTRAINT_EXCLUSION",
    "SCENARIO_DUAL_PROVIDER_DELIVERY",
    "SCENARIO_REQUIREMENTS_UNSATISFIED",
    "SETTLEMENT_CONFIRMATION_REF",
    "ComosVertical",
    "StepRecord",
    "VerticalResult",
    "VerticalScenario",
    "run_scenario",
]
