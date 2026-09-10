"""ADCOS RoamLink vertical-proof harness (M011 — Vertical Proof:
RoamLink; R7-CORE-001 child, DEC-0101).

The deterministic, offline, seeded simulation harness proving the
6-step RoamLink flow of the FROZEN vertical-proof boundary
(``spec/integration/vertical-proof.md``, ACR-014) as a
SOFTWARE-class proof: the vertical composes through the ACCEPTED
canonical surfaces with correct attribution and constraint
preservation, using injected instants and deterministic
provider-change injection.

THE COMPOSITION MAP (pinned by the battery, disclosed here):

REAL AUTHORITY — the accepted canonical domains, composed by
reference through their PUBLIC surfaces only, never modified,
never re-implemented:

- ``contracts`` (M002, DEC-0102) — step 3 and the whole flow's
  durable authority: the real ``ContractStore`` journal fold, the
  real ``CreateContract``/``SelectOffers``/``ActivateContract``/
  ``RecordExecutionActivation``/``BindExecutionArtifact``/
  ``RecordDelivery``/``RecordAssurance``/``RecordUsageFinal``/
  ``RecordSettlementPending``/``RecordSettled`` commands.
- ``offers`` (M003, DEC-0103) — step 2: the real
  ``OfferExchange``, ``build_advertisement``/``build_offer``,
  the real bridge reference shapes (``offer_reference``) and the
  fail-closed resolution discipline.
- ``commercial`` + ``usage`` (M009, DEC-0109) — the
  commercial-terms surface (the real ``OfferPricing`` terms and
  the contract's opaque usage-pricing-terms reference) and the
  usage evidence attribution: the real contract-cited
  ``ContractCommercialSnapshot``, ``UsageEvidenceIndex`` and
  ``UsageLedger`` (the account key IS the contract citation,
  LOCK-113) plus the real bound ``CommercialCore``
  reconciliation walk.
- ``developerapi`` (M013, DEC-0113) — the application-facing
  route surface the whole vertical composes through: the real
  ``DeveloperApiService`` route table (create intents, accept
  offers, activate, inspect execution status/assurance/usage),
  the real signed webhook observation channel, and the real SDK
  client the RoamLink boundary drives.

DETERMINISTIC SIMULATION SEAMS — the NOT-YET-ACCEPTED children's
mechanics represented as clearly-labeled TEST DOUBLES of their
future domains (``roamlink/simulation.py``): M004
eligibility/policy evaluation, M005 evidence/assurance
evaluation, M006 execution plans, M007 realization/path segments,
M008 replan/failover.  Every seam-produced reference carries its
seam label as the provenance issuer; the seams are never
imported as authority, never claim the real children are
delivered, and LOCK-108 is enforced INSIDE the replan seam (a
weakening realization can never be bound behind the contract).

LOCK-120 (the vertical boundary): ``roamlink/cohort.py`` models
RoamLink as an EXTERNAL application boundary — opaque subscriber
cohort, technology-neutral request, SDK-only composition — and
the harness NEVER implements RoamLink's mobile observation,
device context, eSIM product behavior or mobile UX.  ADCOS
supplies connectivity for the cohort only.

Determinism discipline (LOCK-119): injected instants only, no
wall clock, no randomness, no UUIDs, no network, no secrets;
content-derived ids over canonical JSON; sorted iteration
everywhere; every check fails closed with typed errors.
"""

from __future__ import annotations

from .errors import RoamLinkError, RoamLinkReason
from .cohort import (
    COHORT_HANDLE_PATTERN,
    COHORT_MEMBER_PATTERN,
    ROAMLINK_CAPABILITIES,
    CohortConnectivityRequest,
    RoamLinkBoundary,
    SubscriberCohort,
)
from .simulation import (
    AUTHORITY_DOMAINS,
    OBSERVATION_STATES,
    PROVIDER_CHANGE_KINDS,
    REALIZATION_STATES,
    SIMULATION_SEAMS,
    ProviderChange,
    ProviderWorld,
    SimulatedAssuranceEvaluation,
    SimulatedAssuranceEvaluator,
    SimulatedExecutionPlanner,
    SimulatedPolicyDecision,
    SimulatedPolicyGate,
    SimulatedRealization,
    SimulatedReplanOutcome,
    SimulatedReplanner,
    SimulatedSegment,
    build_provider_world,
    build_weakened_successor_offer,
    hard_constraint_fingerprint,
)
from .flow import (
    APPLICATION_STATE_BLOB,
    COHORT,
    ISSUANCE_KEY,
    OBSERVED_EVENT_TYPES,
    OFFER_VALIDITY,
    PROVIDER_A,
    PROVIDER_B,
    T0,
    T_ACTIVATE,
    T_ASSURANCE,
    T_CHANGE,
    T_DEGRADED,
    T_DELIVERY,
    T_EXEC,
    T_EXPOSE,
    T_RECOVER,
    T_REPLAN,
    T_REQUEST,
    T_SELECT,
    T_SETTLED,
    T_SETTLEMENT_PENDING,
    T_USAGE_FINAL,
    USAGE_WINDOWS,
    VALIDITY_NOT_AFTER,
    WEAKENED_LATENCY_MS,
    FlowResult,
    RoamLinkVerticalFlow,
)

__all__ = [
    # error model
    "RoamLinkError",
    "RoamLinkReason",
    # the external application boundary (LOCK-120)
    "COHORT_HANDLE_PATTERN",
    "COHORT_MEMBER_PATTERN",
    "ROAMLINK_CAPABILITIES",
    "CohortConnectivityRequest",
    "RoamLinkBoundary",
    "SubscriberCohort",
    # the simulation seams (the pending children's doubles)
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
    # the vertical flow
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
