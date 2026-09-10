"""The M011 RoamLink vertical-proof flow (R7-CORE-001 child M011,
DEC-0101): the deterministic, offline, seeded simulation battery
harness proving the 6-step RoamLink flow of the FROZEN
vertical-proof boundary (spec/integration/vertical-proof.md,
ACR-014):

1. RoamLink requests connectivity for a defined subscriber
   cohort (the external application boundary, technology-neutral
   request over the accepted developer API; LOCK-102/LOCK-120).
2. ADCOS exposes provider offers and commercial terms (the REAL
   M003 offers/exchange surface: capability advertisements,
   offers with explicit bounded commitments, integer-minor-unit
   pricing, service boundaries; LOCK-118 provenance).
3. A contract is accepted (the REAL M002 contract domain: the
   offer references bind through the canonical
   ``SelectOffers``/``ActivateContract`` commands driven through
   the accepted developer API routes; the M004 seam's simulated
   eligibility verdict is recorded as labeled decision data).
4. RoamLink receives execution status and assurance events (the
   platform advances the REAL contract through
   ``RecordExecutionActivation``/``BindExecutionArtifact``/
   ``RecordDelivery``/``RecordAssurance``; the boundary observes
   execution status and assurance through the developer API
   reads and receives SIGNED observation events through the
   M013 webhook channel; usage evidence is attributed to the one
   contract through the REAL M009 usage ledger bound by the
   contract-cited commercial snapshot, and the commercial
   reconciliation walk mirrors the contract's settlement states
   through the REAL M009 commercial core; LOCK-106/LOCK-113).
5. Provider changes are absorbed behind the ADCOS contract (the
   deterministic provider-change injection: a weakened successor
   offer supersedes provider A's listing and provider A's
   realization fails; the contract records the honest DEGRADED
   assurance state; the M008 seam's replan binds provider B's
   admissible realization behind the SAME contract -- the hard
   constraint set stays byte-identical (LOCK-108), the accepted
   offers stay bound, the identity never changes; a weakening
   alternate is REJECTED at the change seam and recorded).
6. RoamLink retains authority over mobile observation, device
   context, eSIM product behavior and mobile UX (LOCK-120: the
   boundary's opaque application-owned state never crosses into
   any ADCOS surface; the cohort stays opaque; ADCOS supplies
   connectivity for the cohort only).

COMPOSITION MAP (the disclosure the battery pins):

- REAL AUTHORITY (accepted canonical domains, composed through
  their PUBLIC surfaces only): ``contracts`` (M002, DEC-0102),
  ``offers`` (M003, DEC-0103), ``commercial`` + ``usage`` (M009,
  DEC-0109), ``developerapi`` (M013, DEC-0113).
- DETERMINISTIC SIMULATION SEAMS (clearly labeled test doubles
  of the NOT-YET-ACCEPTED children; never authority, never
  claimed delivered): M004 eligibility/policy, M005
  evidence/assurance, M006 execution plan, M007 realization/
  adapter, M008 replan/failover (roamlink/simulation.py).

The proof is SOFTWARE-class: the sandbox environment's honest
evidence classification; no physical connectivity claim is made
anywhere.  Deterministic, offline, seeded: injected instants
only, no wall clock, no randomness, no network, no secrets
(LOCK-119); canonical-JSON round-trips; every check fails
closed.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

from protocol.canonicalization import canonical_json_bytes

from agent.clock import FixedClock, StepClock

from contracts import (
    BindExecutionArtifact,
    ContractStore,
    RecordAssurance,
    RecordDelivery,
    RecordExecutionActivation,
    RecordSettled,
    RecordSettlementPending,
    RecordUsageFinal,
)
from contracts import HardConstraint as ContractHardConstraint

from offers import OfferExchange, offer_reference
from offers.errors import OfferError

from developerapi import (
    DeveloperApiClient,
    DeveloperApiService,
    MemoryApiStore,
    derive_resource_id,
)
from developerapi import webhooks as webhook_platform

from usage import (
    ContractCommercialSnapshot,
    DeliveryEvidence,
    EvidenceKind,
    MemoryUsageStore,
    QuantityClass,
    UsageEvidenceIndex,
    UsageLedger,
)

from commercial import (
    CommercialCore,
    ContractCitation,
    ContractReferenceIndex,
    MemoryCommercialStore,
    Reference,
    ReferenceFamily,
    ReferenceIndex,
)

from .cohort import (
    CohortConnectivityRequest,
    RoamLinkBoundary,
    SubscriberCohort,
)
from .errors import RoamLinkError, RoamLinkReason
from .simulation import (
    ProviderChange,
    ProviderWorld,
    SimulatedAssuranceEvaluator,
    SimulatedExecutionPlanner,
    SimulatedPolicyGate,
    SimulatedReplanner,
    build_provider_world,
    build_weakened_successor_offer,
    hard_constraint_fingerprint,
)

# ---------------------------------------------------------------------------
# The frozen scenario timeline (injected instants; T0-style
# constants; no wall clock anywhere)
# ---------------------------------------------------------------------------

T0 = "2026-10-01T00:00:00Z"
T_REQUEST = "2026-10-02T00:00:00Z"
T_EXPOSE = "2026-10-03T00:00:00Z"
T_SELECT = "2026-10-04T00:00:00Z"
T_ACTIVATE = "2026-10-05T00:00:00Z"
T_EXEC = "2026-10-06T00:00:00Z"
T_DELIVERY = "2026-10-07T00:00:00Z"
T_ASSURANCE = "2026-10-08T00:00:00Z"
T_CHANGE = "2026-10-10T00:00:00Z"
T_DEGRADED = "2026-10-10T06:00:00Z"
T_REPLAN = "2026-10-11T00:00:00Z"
T_RECOVER = "2026-10-12T00:00:00Z"
T_USAGE_FINAL = "2026-10-13T00:00:00Z"
T_SETTLEMENT_PENDING = "2026-10-14T00:00:00Z"
T_SETTLED = "2026-10-15T00:00:00Z"
VALIDITY_NOT_AFTER = "2026-11-03T00:00:00Z"
OFFER_VALIDITY = (T0, "2026-11-05T00:00:00Z")

#: The deterministic provider-domain identities (the M003
#: provider NodeID grammar; fixture material).
PROVIDER_A = "adcos:node:identity.sha256-hmac-dev.v1:" + "a" * 64
PROVIDER_B = "adcos:node:identity.sha256-hmac-dev.v1:" + "b" * 64

#: The weakened successor's latency commitment (VIOLATES the
#: contract's 100 ms latency bound: the LOCK-108 change-seam
#: rejection fixture).
WEAKENED_LATENCY_MS = 150

#: The subscriber cohort fixture: a defined, bounded, opaque
#: cohort (three enumerated opaque member handles).
COHORT = SubscriberCohort(
    cohort_handle="roamlink-cohort:v1:gh-accra:0007", member_count=3
)

#: The deterministic usage-evidence windows (delivered quantities
#: in canonical units; simulated delivery-plane facts, labeled
#: with the M006 seam provenance).
USAGE_WINDOWS: Tuple[Tuple[str, str, int], ...] = (
    (T_EXEC, T_DELIVERY, 120),
    (T_DELIVERY, T_ASSURANCE, 90),
    (T_CHANGE, T_DEGRADED, 45),
    (T_REPLAN, T_RECOVER, 60),
)

#: The seeded issuance key of the harness platform (test-only
#: fixture bytes; secrets are derived, never journaled).
ISSUANCE_KEY = b"m011-roamlink-issuance-key"

#: The RoamLink application's opaque owned state (LOCK-120: the
#: product/UX material that never crosses into ADCOS).
APPLICATION_STATE_BLOB = b"roamlink-product-ux-state-v1-opaque"

#: The webhook event types RoamLink subscribes to (the frozen
#: M013 observation vocabulary).
OBSERVED_EVENT_TYPES: Tuple[str, ...] = (
    "connectivity_intent.created",
    "connectivity_contract.offers_selected",
    "connectivity_contract.activated",
    "connectivity_contract.state_changed",
)


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise RoamLinkError(
            RoamLinkReason.INVALID_INPUT,
            "%s must be a non-empty string" % label,
        )
    return value


@dataclass
class FlowResult:
    """The vertical-flow result: the transcript (typed step
    records), the deterministic digest, and the composed world
    (for battery inspection through public surfaces only)."""

    transcript: Dict[str, Any]
    digest: str
    store: ContractStore
    exchange: OfferExchange
    service: DeveloperApiService
    boundary: RoamLinkBoundary
    ledger: UsageLedger
    commercial: CommercialCore
    contract_id: str
    world: ProviderWorld

    def contract(self) -> Any:
        return self.store.contract(self.contract_id)


class RoamLinkVerticalFlow:
    """The deterministic 6-step RoamLink vertical (M011).

    Constructs the composed world fresh (real accepted
    authorities + the labeled simulation seams), runs the full
    6-step flow with the step-5 provider-change absorption, and
    produces the typed transcript + digest.  Identical runs
    produce byte-identical digests (the battery's determinism
    case)."""

    def __init__(
        self,
        *,
        issuance_key: bytes = ISSUANCE_KEY,
        application_state_blob: bytes = APPLICATION_STATE_BLOB,
    ) -> None:
        self._issuance_key = issuance_key
        self._application_state_blob = application_state_blob
        # the REAL canonical authorities (composed, never
        # re-implemented; injected already-composed by the
        # platform exactly as the M013 boundary requires)
        self.store = ContractStore()
        self.world = build_provider_world(
            provider_a=PROVIDER_A, provider_b=PROVIDER_B,
            validity=OFFER_VALIDITY,
        )
        self.exchange = self.world.exchange
        # the deterministic webhook endpoint id (derived from the
        # fixed idempotency key; the signing secret is derived
        # from the issuance key -- never journaled, handed to the
        # application boundary through the platform's secure
        # channel in the harness)
        self.endpoint_id = derive_resource_id(
            "sandbox", "webhook_endpoint",
            "roamlink-developer", "roamlink-endpoint-key",
        )
        endpoint_secret = webhook_platform.derive_endpoint_signing_secret(
            issuance_key, self.endpoint_id
        )
        # the recording delivery transport (RoamLink's webhook
        # receiver fixture: records every signed delivery for the
        # boundary's consumer-side verification; deterministic)
        self.received_deliveries: List[Tuple[Dict[str, str], Dict[str, Any]]] = []

        def transport(
            endpoint_id: str,
            url: str,
            event: Mapping[str, Any],
            headers: Mapping[str, str],
        ) -> Tuple[bool, int]:
            self.received_deliveries.append((dict(headers), dict(event)))
            return True, 200

        # the application-facing route surface (M013): sandbox
        # environment -- SOFTWARE-class evidence, honestly
        # classified; never production or physical claims
        self.service = DeveloperApiService(
            environment="sandbox",
            contracts=self.store,
            store=MemoryApiStore(),
            clock=StepClock(T0, 60),
            issuance_key=issuance_key,
            delivery_transports={self.endpoint_id: transport},
        )
        # the RoamLink application credential (the platform's
        # out-of-band issuance surface)
        self.credential = self.service.issue_application_credential(
            developer_id="roamlink-developer",
            application_name="roamlink-cohort-app",
            capabilities=(
                "intents:read", "intents:write", "usage:read",
                "assurance:read", "webhooks:read", "webhooks:write",
            ),
            valid_until="2030-01-01T00:00:00Z",
            key_material="roamlink-developer-key",
            actor="platform",
        )
        self.client = DeveloperApiClient(
            transport=self._transport,
            application_id=self.credential.record.application_id,
            secret=self.credential.secret,
            api_version="2.0",
            environment="sandbox",
        )
        # the EXTERNAL application boundary (LOCK-120)
        self.boundary = RoamLinkBoundary(
            client=self.client,
            webhook_secret=endpoint_secret,
            verifier_clock=FixedClock(T0),
            verifier_tolerance=86400,
            application_state_blob=application_state_blob,
        )
        # the labeled simulation seams (M004/M005/M006/M007/M008)
        self.policy_gate = SimulatedPolicyGate()
        self.assurance_evaluator = SimulatedAssuranceEvaluator()
        self.planner = SimulatedExecutionPlanner()
        self.replanner = SimulatedReplanner()
        # the M009 surfaces (composed at the usage/settlement
        # phase from public reads)
        self.ledger: Optional[UsageLedger] = None
        self.commercial: Optional[CommercialCore] = None

    def _transport(self, request: Any) -> Any:
        return self.service.handle(request)

    # ------------------------------------------------------------------
    # The request (LOCK-102/LOCK-120): technology-neutral creation core
    # ------------------------------------------------------------------

    def cohort_request(self) -> CohortConnectivityRequest:
        return CohortConnectivityRequest(
            cohort=COHORT,
            requirement_values=("roamlink-req:cohort-data-v1",),
            hard_constraints=(
                {"kind": "latency-bound", "params": {"max_ms": 100}},
                {"kind": "throughput-floor", "params": {"min_kbps": 2048}},
                {"kind": "geography", "params": {"region": "GH"}},
            ),
            validity={
                "not_before": T_REQUEST,
                "not_after": VALIDITY_NOT_AFTER,
            },
            termination={
                "conditions": ("principal-requested", "validity-expired"),
                "compensation": {
                    "ref_kind": "compensation",
                    "value": "roamlink:compensation:cohort-v1",
                },
            },
            recorded_at=T_REQUEST,
            usage_pricing_terms_value="roamlink:envelope:cohort-data-v1",
            assurance_obligation_values=("roamlink:obligation:sla-v1",),
            execution_scope_values=("roamlink:scope:cohort-data-v1",),
        )

    # ------------------------------------------------------------------
    # The 6-step flow
    # ------------------------------------------------------------------

    def run(self) -> FlowResult:
        transcript: Dict[str, Any] = {"steps": [], "environment": "sandbox"}

        # the boundary registers its observation endpoint FIRST
        # (before every mutation whose observations it must
        # receive: admission-time audience resolution is frozen)
        self.boundary.register_observation_endpoint(
            idempotency_key="roamlink-endpoint-key",
            url="https://roamlink.example/hooks/adcos",
            event_types=OBSERVED_EVENT_TYPES,
        )

        # -- STEP 1: the cohort connectivity request --------------------
        request = self.cohort_request()
        intent = self.boundary.request_cohort_connectivity(
            idempotency_key="roamlink-intent-1", request=request
        )
        contract_id = intent.id
        contract = self.store.contract(contract_id)
        if contract.state != "INTENT":
            raise RoamLinkError(
                RoamLinkReason.STEP_INVALID,
                "step 1: the cohort request did not create an INTENT "
                "contract (found %s)" % contract.state,
            )
        if contract.principal.principal_kind != "APPLICATION":
            raise RoamLinkError(
                RoamLinkReason.STEP_INVALID,
                "step 1: the contracting principal must be the "
                "APPLICATION (LOCK-103: application purchasing)",
            )
        self._boundary_receives()
        transcript["steps"].append(
            {
                "step": 1,
                "kind": "cohort-connectivity-request",
                "at": T_REQUEST,
                "contract_id": contract_id,
                "contract_state": contract.state,
                "principal_kind": contract.principal.principal_kind,
                "beneficiaries": [b.to_dict() for b in contract.beneficiaries],
                "requirements": [r.to_dict() for r in contract.requirements],
                "opaque_cohort": True,
            }
        )

        # -- STEP 2: ADCOS exposes provider offers + commercial terms ---
        exposed = self.exchange.active_offers(at_instant=T_EXPOSE)
        if len(exposed) < 2:
            raise RoamLinkError(
                RoamLinkReason.STEP_INVALID,
                "step 2: expected both providers' live listings at the "
                "exposure instant (found %d)" % len(exposed),
            )
        terms = [
            {
                "offer_id": offer.offer_id,
                "provider": offer.provider,
                "pricing": offer.pricing.to_dict(),
                "commitments": [c.to_dict() for c in offer.commitments],
                "service_boundaries": [
                    b.to_dict() for b in offer.service_boundaries
                ],
            }
            for offer in sorted(exposed, key=lambda o: o.provider_offer_key)
        ]
        policy_decision = self.policy_gate.evaluate(
            constraints=tuple(
                ContractHardConstraint.from_dict(c) for c in request.hard_constraints
            ),
            offers=exposed,
        )
        if policy_decision.verdict != "eligible":
            raise RoamLinkError(
                RoamLinkReason.STEP_INVALID,
                "step 2: the simulated policy gate did not find an "
                "eligible offer for the cohort request",
            )
        transcript["steps"].append(
            {
                "step": 2,
                "kind": "provider-offers-and-terms-exposed",
                "at": T_EXPOSE,
                "contract_id": contract_id,
                "exposed_offer_count": len(exposed),
                "terms": terms,
                "policy_decision": policy_decision.to_dict(),
            }
        )

        # -- STEP 3: the contract is accepted ---------------------------
        accepted_references = tuple(
            offer_reference(offer).to_dict()
            for offer in sorted(exposed, key=lambda o: o.provider_offer_key)
        )
        selected = self.boundary.accept_provider_offers(
            idempotency_key="roamlink-offers-1",
            intent_id=contract_id,
            offer_references=accepted_references,
            recorded_at=T_SELECT,
        )
        if selected.get("state") != "OFFER_SELECTED":
            raise RoamLinkError(
                RoamLinkReason.STEP_INVALID,
                "step 3: offer acceptance did not select offers (found %s)"
                % selected.get("state"),
            )
        active = self.boundary.activate_acceptance(
            idempotency_key="roamlink-activate-1",
            intent_id=contract_id,
            activated_at=T_ACTIVATE,
            signature_value="roamlink:acceptance-signature:v1",
        )
        if active.get("state") != "CONTRACT_ACTIVE":
            raise RoamLinkError(
                RoamLinkReason.STEP_INVALID,
                "step 3: the acceptance did not activate the contract "
                "(found %s)" % active.get("state"),
            )
        self._boundary_receives()
        # the recorded policy decision rides as labeled decision
        # data in the flow record (a typed decision reference;
        # the seam label is its provenance issuer)
        transcript["steps"].append(
            {
                "step": 3,
                "kind": "contract-accepted",
                "at": T_ACTIVATE,
                "contract_id": contract_id,
                "contract_state": "CONTRACT_ACTIVE",
                "accepted_offers": [
                    r.to_dict()
                    for r in self.store.contract(contract_id).accepted_offers
                ],
                "policy_decision_ref": policy_decision.decision_reference().to_dict(),
            }
        )

        # -- STEP 4: execution status + assurance events + attribution ---
        contract = self.store.contract(contract_id)
        # the platform advances the REAL contract through its
        # public command surface (exactly how the platform-side
        # execution/assurance authorities drive it)
        self.store.submit(
            RecordExecutionActivation(recorded_at=T_EXEC), T_EXEC,
            contract_id=contract_id,
        )
        realization = self.planner.plan(
            contract=self.store.contract(contract_id), offers=exposed
        )
        segment_a = realization.segments[0]
        self.store.submit(
            BindExecutionArtifact(artifact=segment_a.artifact_reference()),
            T_EXEC, contract_id=contract_id,
        )
        self.store.submit(
            RecordDelivery(recorded_at=T_DELIVERY), T_DELIVERY,
            contract_id=contract_id,
        )
        assurance = self.assurance_evaluator.evaluate(
            contract_id=contract_id, observed="nominal"
        )
        self.store.submit(
            RecordAssurance(
                recorded_at=T_ASSURANCE,
                assurance_state=assurance.assurance_state,
                evidence_refs=(assurance.evidence_reference(),),
            ),
            T_ASSURANCE, contract_id=contract_id,
        )
        # the platform observes the contract; the signed events
        # flow to the boundary's endpoint; the boundary verifies
        self.service.observe_contract(contract_id)
        self._boundary_receives()
        lifecycle = self.boundary.read_execution_status(contract_id)
        assurance_read = self.boundary.read_assurance(contract_id)
        usage_read = self.boundary.read_usage_semantics(contract_id)
        if lifecycle.get("execution_status") != "delivered-assured":
            raise RoamLinkError(
                RoamLinkReason.STEP_INVALID,
                "step 4: the boundary did not observe the assured "
                "execution status (found %s)" % lifecycle.get("execution_status"),
            )
        transcript["steps"].append(
            {
                "step": 4,
                "kind": "execution-status-and-assurance-events",
                "at": T_ASSURANCE,
                "contract_id": contract_id,
                "contract_state": self.store.contract(contract_id).state,
                "execution_status": lifecycle.get("execution_status"),
                "execution_artifact_refs": [
                    r.to_dict()
                    for r in self.store.contract(contract_id).execution_artifacts
                ],
                "assurance_state": assurance.assurance_state,
                "assurance_decision_ref": assurance.evidence_reference().to_dict(),
                "boundary_assurance_state": assurance_read.get("contract_state"),
                "boundary_usage_terms": usage_read.get("usage_pricing_terms"),
                "received_event_count": len(
                    self.boundary.observations_for(contract_id)
                ),
            }
        )

        # -- STEP 5: provider changes absorbed behind the contract ------
        constraint_fingerprint_before = hard_constraint_fingerprint(
            self.store.contract(contract_id)
        )
        accepted_before = tuple(
            r.to_dict()
            for r in self.store.contract(contract_id).accepted_offers
        )
        # the deterministic change injection: provider A
        # supersedes its listing with WEAKENED commitments and
        # its realization fails
        weakened_v2 = build_weakened_successor_offer(
            self.world, validity=OFFER_VALIDITY, latency_ms=WEAKENED_LATENCY_MS
        )
        self.exchange.register_offer(weakened_v2)
        change = ProviderChange(
            kind="offer-superseded",
            instant=T_CHANGE,
            provider=PROVIDER_A,
            detail="provider A superseded the cohort-data listing with a "
            "weakened latency commitment and its realization failed",
        )
        # provider A's ORIGINAL listing is no longer resolvable
        # for new realization at the change instant (superseded);
        # the exchange fails closed at resolution time
        unabsorbable: List[str] = []
        for reference in self.store.contract(contract_id).accepted_offers:
            if reference.value == self.world.offer_a_v1.offer_id:
                try:
                    self.exchange.resolve(reference, at_instant=T_CHANGE)
                except OfferError:
                    unabsorbable.append(reference.value)
        # the honest degraded state: the realization failed; the
        # assurance seam records the degraded evaluation
        degraded = self.assurance_evaluator.evaluate(
            contract_id=contract_id, observed="degraded-realization"
        )
        self.store.submit(
            RecordAssurance(
                recorded_at=T_DEGRADED,
                assurance_state=degraded.assurance_state,
                evidence_refs=(degraded.evidence_reference(),),
            ),
            T_DEGRADED, contract_id=contract_id,
        )
        self.service.observe_contract(contract_id)
        self._boundary_receives()
        degraded_status = self.boundary.read_execution_status(contract_id)
        if degraded_status.get("execution_status") != "degraded":
            raise RoamLinkError(
                RoamLinkReason.STEP_INVALID,
                "step 5: the boundary did not observe the honest degraded "
                "status (found %s)" % degraded_status.get("execution_status"),
            )
        # the replan: the weakened successor is REJECTED at the
        # change seam (LOCK-108); provider B's realization is
        # admissible and binds behind the SAME contract
        alternates = (
            self.exchange.offer(weakened_v2.offer_id),
            self.exchange.offer(self.world.offer_b_v1.offer_id),
        )
        outcome = self.replanner.absorb(
            contract=self.store.contract(contract_id),
            change=change,
            alternate_offers=alternates,
            failed_segment=segment_a,
        )
        if outcome.verdict != "absorbed":
            raise RoamLinkError(
                RoamLinkReason.STEP_INVALID,
                "step 5: the replan did not absorb the change behind the "
                "contract (verdict %s)" % outcome.verdict,
            )
        if outcome.rejected_realizations != (weakened_v2.offer_id,):
            raise RoamLinkError(
                RoamLinkReason.CONSTRAINT_VIOLATION,
                "step 5: the weakened successor was not rejected at the "
                "change seam (LOCK-108): rejected=%r"
                % (outcome.rejected_realizations,),
            )
        replacement = self.replanner.replacement_segment(
            contract=self.store.contract(contract_id),
            change=change,
            offer=self.exchange.offer(self.world.offer_b_v1.offer_id),
            failed_segment=segment_a,
        )
        self.store.submit(
            BindExecutionArtifact(artifact=replacement.artifact_reference()),
            T_REPLAN, contract_id=contract_id,
        )
        # LOCK-108 verification at the change seam: the constraint
        # set, the accepted offers and the identity are
        # byte-identical across the absorption
        contract_after = self.store.contract(contract_id)
        constraint_fingerprint_after = hard_constraint_fingerprint(contract_after)
        if constraint_fingerprint_after != constraint_fingerprint_before:
            raise RoamLinkError(
                RoamLinkReason.CONSTRAINT_VIOLATION,
                "step 5: the hard-constraint fingerprint changed across "
                "the provider-change absorption (LOCK-108 violated)",
            )
        accepted_after = tuple(r.to_dict() for r in contract_after.accepted_offers)
        if accepted_after != accepted_before:
            raise RoamLinkError(
                RoamLinkReason.CONSTRAINT_VIOLATION,
                "step 5: the accepted-offer set changed across the "
                "absorption (offers bind exactly once; the change is "
                "absorbed BEHIND the contract)",
            )
        if contract_after.contract_id != contract_id:
            raise RoamLinkError(
                RoamLinkReason.CONSTRAINT_VIOLATION,
                "step 5: the contract identity changed across the "
                "absorption",
            )
        # recovery: the assurance seam evaluates the replacement
        # realization as nominal; the contract walks to ASSURED
        recovered = self.assurance_evaluator.evaluate(
            contract_id=contract_id, observed="nominal"
        )
        self.store.submit(
            RecordAssurance(
                recorded_at=T_RECOVER,
                assurance_state=recovered.assurance_state,
                evidence_refs=(recovered.evidence_reference(),),
            ),
            T_RECOVER, contract_id=contract_id,
        )
        self.service.observe_contract(contract_id)
        self._boundary_receives()
        recovered_status = self.boundary.read_execution_status(contract_id)
        if recovered_status.get("execution_status") != "delivered-assured":
            raise RoamLinkError(
                RoamLinkReason.STEP_INVALID,
                "step 5: the boundary did not observe the recovered "
                "status (found %s)" % recovered_status.get("execution_status"),
            )
        transcript["steps"].append(
            {
                "step": 5,
                "kind": "provider-change-absorbed-behind-contract",
                "at": T_RECOVER,
                "contract_id": contract_id,
                "change": change.to_dict(),
                "unabsorbable_realizations": sorted(unabsorbable),
                "degraded_assurance": degraded.to_dict(),
                "replan_outcome": outcome.to_dict(),
                "replacement_segment": replacement.to_dict(),
                "constraint_fingerprint_before": constraint_fingerprint_before,
                "constraint_fingerprint_after": constraint_fingerprint_after,
                "constraints_preserved": True,
                "accepted_offers_unchanged": True,
                "recovered_execution_status": recovered_status.get(
                    "execution_status"
                ),
            }
        )

        # -- usage attribution + the settlement walk (the vertical's
        # closing, still behind the ONE contract) ------------------------
        usage_result = self._usage_attribution(contract_id)
        self.store.submit(
            RecordUsageFinal(recorded_at=T_USAGE_FINAL), T_USAGE_FINAL,
            contract_id=contract_id,
        )
        self.ledger.seal_billable(
            command_id="roamlink-seal-1",
            transaction_id=contract_id,
            actor="billing",
            source="usage-ledger",
        )
        # the sealed statement's attribution (LOCK-113): the
        # statement materializes at the explicit seal command and
        # cites the ONE contract as its account key
        statement = self.ledger.transaction(contract_id).statement
        if statement is None or statement.transaction_id != contract_id:
            raise RoamLinkError(
                RoamLinkReason.ATTRIBUTION_INVALID,
                "the sealed usage statement is not attributed to the "
                "one contract through the account-key citation",
            )
        usage_result = dict(usage_result)
        usage_result.update(
            {
                "statement_id": statement.statement_id,
                "contract_citation": statement.transaction_id,
                "billable_quantity": statement.billable_quantity,
                "billable_amount_micros": statement.amount_micros,
                "unit_price_micros": statement.unit_price_micros,
            }
        )
        self.store.submit(
            RecordSettlementPending(recorded_at=T_SETTLEMENT_PENDING),
            T_SETTLEMENT_PENDING, contract_id=contract_id,
        )
        self.store.submit(
            RecordSettled(recorded_at=T_SETTLED), T_SETTLED,
            contract_id=contract_id,
        )
        self.service.observe_contract(contract_id)
        self._boundary_receives()
        commercial_result = self._commercial_reconciliation(contract_id)
        transcript["steps"].append(
            {
                "step": 5,
                "kind": "usage-attribution-and-settlement",
                "at": T_SETTLED,
                "contract_id": contract_id,
                "contract_state": self.store.contract(contract_id).state,
                "usage": usage_result,
                "commercial": commercial_result,
            }
        )

        # -- STEP 6: the boundary authority audit record -----------------
        observations = self.boundary.observations_for(contract_id)
        for record in self.boundary.received_observations():
            if record["resource_id"] != contract_id:
                raise RoamLinkError(
                    RoamLinkReason.ATTRIBUTION_INVALID,
                    "step 6: an observation not attributable to the one "
                    "contract crossed the boundary (%s)"
                    % record["resource_id"][:24],
                )
        transcript["steps"].append(
            {
                "step": 6,
                "kind": "application-authority-retained",
                "at": T_SETTLED,
                "contract_id": contract_id,
                "opaque_cohort": COHORT.to_dict(),
                "application_state_digest": self.boundary.application_state_digest(),
                "received_observation_count": len(observations),
                "all_observations_attributed": True,
                "vertical_semantics_in_adcos": False,
            }
        )

        digest = self._transcript_digest(transcript)
        return FlowResult(
            transcript=transcript,
            digest=digest,
            store=self.store,
            exchange=self.exchange,
            service=self.service,
            boundary=self.boundary,
            ledger=self.ledger,
            commercial=self.commercial,
            contract_id=contract_id,
            world=self.world,
        )

    # ------------------------------------------------------------------
    # The usage evidence attribution (M009 composition)
    # ------------------------------------------------------------------

    def _usage_attribution(self, contract_id: str) -> Dict[str, Any]:
        """Build the contract-cited evidence index from PUBLIC
        reads, admit the delivered observations, and return the
        observation attribution facts (the account key IS the
        contract citation -- LOCK-113; the sealed statement
        materializes at the explicit ``seal_billable`` command,
        exactly as the M009 usage domain requires -- the flow
        seals after ``RecordUsageFinal`` and verifies the
        statement attribution there)."""
        contract = self.store.contract(contract_id)
        # the tariff DATA resolved from the contract's opaque
        # usage-pricing-terms reference through the accepted
        # offers' PUBLIC pricing reads (the offers authority
        # owns the terms; the ledger consumes the resolved
        # integer tariff as DATA)
        accepted = sorted(
            (self.exchange.offer(reference.value)
             for reference in contract.accepted_offers),
            key=lambda o: o.offer_id,
        )
        lead_offer = accepted[0]
        tariff = {
            "unit_price_micros": lead_offer.pricing.price_minor,
            "billable_unit": lead_offer.pricing.billing_mode,
            "tariff_provenance": "offer-pricing-public-read",
        }
        evidence: List[DeliveryEvidence] = []
        for window_start, window_end, quantity in USAGE_WINDOWS:
            evidence_id = "sha256:" + hashlib.sha256(
                canonical_json_bytes(
                    {
                        "kind": "delivery-evidence-window",
                        "contract_id": contract_id,
                        "from": window_start,
                        "to": window_end,
                    }
                )
            ).hexdigest()
            evidence.append(
                DeliveryEvidence(
                    evidence_id=evidence_id,
                    transaction_id=contract_id,
                    delivered_quantity=quantity,
                    window_start=window_start,
                    window_end=window_end,
                    evidence_kind=EvidenceKind.DELIVERED,
                    provenance="simulation-seam:m006-execution-plan",
                )
            )
        index = UsageEvidenceIndex(
            evidence=evidence,
            transactions=[
                ContractCommercialSnapshot(
                    transaction_id=contract_id,
                    commercial_state=contract.state,
                    unit_price_micros=tariff["unit_price_micros"],
                    billable_unit=tariff["billable_unit"],
                    tariff_provenance=tariff["tariff_provenance"],
                )
            ],
        )
        self.ledger = UsageLedger(
            store=MemoryUsageStore(),
            clock=StepClock(T0, 60),
            evidence_index=index,
        )
        # each observation cites its OWN evidence record (the
        # record's quantity + window bounds; deterministic)
        for position, record in enumerate(evidence, start=1):
            self.ledger.observe_usage(
                command_id="roamlink-obs-%02d" % position,
                transaction_id=contract_id,
                quantity_class=QuantityClass.DELIVERED,
                quantity=record.delivered_quantity,
                evidence_id=record.evidence_id,
                window_start=record.window_start,
                window_end=record.window_end,
                actor="meter",
                source="usage-collector",
            )
        # the account-key attribution check (LOCK-113): the
        # ledger account key IS the contract citation, and every
        # admitted observation record cites the one contract
        account = self.ledger.transaction(contract_id)
        if account.transaction_id != contract_id:
            raise RoamLinkError(
                RoamLinkReason.ATTRIBUTION_INVALID,
                "the usage account key is not the contract citation "
                "(LOCK-113: %s != %s)"
                % (account.transaction_id[:24], contract_id[:24]),
            )
        for observation in account.observations:
            if observation.transaction_id != contract_id:
                raise RoamLinkError(
                    RoamLinkReason.ATTRIBUTION_INVALID,
                    "a usage observation is not attributed to the one "
                    "contract through the account-key citation",
                )
        return {
            "account_key": account.transaction_id,
            "observation_count": len(USAGE_WINDOWS),
            "attributed_observation_count": len(account.observations),
            "tariff": tariff,
        }

    # ------------------------------------------------------------------
    # The commercial reconciliation walk (M009 composition)
    # ------------------------------------------------------------------

    def _commercial_reconciliation(self, contract_id: str) -> Dict[str, Any]:
        """Drive the bound commercial reconciliation account of
        the ONE contract (the settlement walk mirroring the
        contract's canonical states; every forward action gated
        by the canonical-state floor; LOCK-113)."""
        contract_state = self.store.contract(contract_id).state
        session_ref = "simseam:session:roamlink-1"
        path_ref = "simseam:path:roamlink-1"
        payment_ref = "simseam:payment-observation:external-1"
        settlement_ref = "simseam:settlement-confirmation:external-1"
        usage_ref = self.ledger.transaction(contract_id).statement.statement_id
        evidence_ids = sorted(self.ledger.evidence_index().evidence_ids())
        references = ReferenceIndex(
            [
                Reference(
                    reference_id=session_ref,
                    family=ReferenceFamily.SESSION,
                    provenance="simulation-seam:m006-execution-plan",
                ),
                Reference(
                    reference_id=path_ref,
                    family=ReferenceFamily.NETWORK_PATH,
                    provenance="simulation-seam:m006-execution-plan",
                ),
                Reference(
                    reference_id=evidence_ids[0],
                    family=ReferenceFamily.DELIVERY_EVIDENCE,
                    provenance="usage-evidence-index-public-read",
                ),
                Reference(
                    reference_id=evidence_ids[-1],
                    family=ReferenceFamily.DELIVERY_EVIDENCE,
                    provenance="usage-evidence-index-public-read",
                ),
                Reference(
                    reference_id=usage_ref,
                    family=ReferenceFamily.USAGE,
                    provenance="usage-ledger-public-read",
                ),
                Reference(
                    reference_id=payment_ref,
                    family=ReferenceFamily.PAYMENT,
                    provenance="simulation-seam:external-payment-rail",
                ),
                Reference(
                    reference_id=settlement_ref,
                    family=ReferenceFamily.SETTLEMENT,
                    provenance="simulation-seam:external-settlement-rail",
                ),
            ]
        )
        self.commercial = CommercialCore(
            store=MemoryCommercialStore(),
            clock=StepClock(T0, 60),
            references=references,
            contract_references=ContractReferenceIndex(
                [
                    ContractCitation(
                        contract_id=contract_id,
                        contract_state=contract_state,
                        provenance="contract-store-public-read",
                    )
                ]
            ),
        )
        core = self.commercial
        outcome = core.submit_intent(
            command_id="roamlink-comm-01",
            actor="platform",
            source="vertical-harness",
            intent={
                "buyer": "roamlink-cohort-app",
                "want": "cohort-connectivity",
                "region": "gh",
                "contract_id": contract_id,
            },
        )
        transaction_id = outcome.transaction_id
        core.select_offer(
            command_id="roamlink-comm-02", transaction_id=transaction_id,
            actor="platform", source="vertical-harness",
            offer={
                "offer_id": self.world.offer_b_v1.offer_id,
                "provider": PROVIDER_B,
                "unit": "megabyte",
                "price": "190",
            },
        )
        core.hold_reservation(
            command_id="roamlink-comm-03", transaction_id=transaction_id,
            actor="platform", source="vertical-harness",
            expires_at=T_SETTLEMENT_PENDING,
            payment_refs=(payment_ref,),
        )
        core.authorize_session(
            command_id="roamlink-comm-04", transaction_id=transaction_id,
            actor="platform", source="vertical-harness",
            session_ref=session_ref,
        )
        core.activate_path(
            command_id="roamlink-comm-05", transaction_id=transaction_id,
            actor="platform", source="vertical-harness",
            path_ref=path_ref,
        )
        core.start_delivery(
            command_id="roamlink-comm-06", transaction_id=transaction_id,
            actor="platform", source="vertical-harness",
            evidence_refs=(evidence_ids[0],),
        )
        core.accrue_usage(
            command_id="roamlink-comm-07", transaction_id=transaction_id,
            actor="platform", source="vertical-harness",
            usage_refs=(usage_ref,),
        )
        core.complete_delivery(
            command_id="roamlink-comm-08", transaction_id=transaction_id,
            actor="platform", source="vertical-harness",
            evidence_refs=(evidence_ids[-1],),
        )
        core.finalize_billable(
            command_id="roamlink-comm-09", transaction_id=transaction_id,
            actor="platform", source="vertical-harness",
        )
        core.initiate_settlement(
            command_id="roamlink-comm-10", transaction_id=transaction_id,
            actor="platform", source="vertical-harness",
            payment_refs=(payment_ref,),
        )
        core.settle(
            command_id="roamlink-comm-11", transaction_id=transaction_id,
            actor="platform", source="vertical-harness",
            settlement_refs=(settlement_ref,),
        )
        projection = core.transaction(transaction_id)
        if projection.contract_id != contract_id:
            raise RoamLinkError(
                RoamLinkReason.ATTRIBUTION_INVALID,
                "the commercial reconciliation account lost the "
                "contract binding through the walk",
            )
        return {
            "transaction_id": transaction_id,
            "contract_binding": projection.contract_id,
            "final_state": projection.state,
            "command_count": 11,
        }

    # ------------------------------------------------------------------
    # The boundary's event reception
    # ------------------------------------------------------------------

    def _boundary_receives(self) -> None:
        """Deliver every pending signed observation to the
        boundary's receiver (deterministic order) and let the
        boundary verify them (signature + duplicate detection +
        attribution)."""
        self.service.process_due_deliveries()
        pending = list(self.received_deliveries)
        self.received_deliveries.clear()
        for headers, payload in pending:
            self.boundary.receive_observation(headers, payload)

    # ------------------------------------------------------------------
    # The deterministic transcript digest
    # ------------------------------------------------------------------

    def _transcript_digest(self, transcript: Dict[str, Any]) -> str:
        """The deterministic digest over the whole vertical run:
        the transcript, the canonical contract journal, the offer
        catalog, the boundary journal, the usage ledger stream
        and the commercial journal (byte-identical across two
        fresh runs -- the battery's determinism substrate)."""
        document = {
            "transcript": transcript,
            "contract_journal_digest": self.store.journal_digest(),
            "offer_catalog_digest": self.exchange.catalog_digest(),
            "api_journal_digest": self.service.journal_digest(),
        }
        if self.ledger is not None:
            document["usage_digest_stream"] = self.ledger.digest_stream()
        if self.commercial is not None:
            document["commercial_journal_digest"] = self.commercial.journal_digest()
        document["boundary_observations"] = [
            dict(record) for record in self.boundary.received_observations()
        ]
        return "sha256:" + hashlib.sha256(
            canonical_json_bytes(document)
        ).hexdigest()


__all__ = [
    "APPLICATION_STATE_BLOB",
    "COHORT",
    "ISSUANCE_KEY",
    "OBSERVED_EVENT_TYPES",
    "OFFER_VALIDITY",
    "PROVIDER_A",
    "PROVIDER_B",
    "T0",
    "T_ACTIVATE",
    "T_ASSURANCE",
    "T_CHANGE",
    "T_DEGRADED",
    "T_DELIVERY",
    "T_EXEC",
    "T_EXPOSE",
    "T_RECOVER",
    "T_REPLAN",
    "T_REQUEST",
    "T_SELECT",
    "T_SETTLED",
    "T_SETTLEMENT_PENDING",
    "T_USAGE_FINAL",
    "USAGE_WINDOWS",
    "VALIDITY_NOT_AFTER",
    "WEAKENED_LATENCY_MS",
    "FlowResult",
    "RoamLinkVerticalFlow",
]
