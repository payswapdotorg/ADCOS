"""ADCOS COMOS vertical-proof harness (M012 — Vertical Proofs:
COMOS, R7-CORE-001 child, DEC-0101; dependency M013 satisfied by
DEC-0113; M009 accepted DEC-0109).

The M012 mandate: prove the FROZEN 6-step COMOS flow of
``spec/integration/vertical-proof.md`` (ACR-014) as a SOFTWARE-class
deterministic vertical proof — communication-gateway connectivity —
with COMOS's application semantics staying COMOS's (LOCK-120: a
compatibility proof, never an ownership transfer).

**Composition map (the authoritative disclosure):**

REAL accepted authorities composed through their public surfaces
ONLY (never modified, never re-implemented):

- ``contracts`` — M002 Connectivity Contract Core (DEC-0102): the
  canonical ``ContractStore``/command vocabulary.  Every contract
  mutation of the vertical flow goes through this authority.
- ``offers`` — M003 Offers and Provider Capability Exchange
  (DEC-0103): the canonical provider-domain offer model, exchange
  and bridges.  Both provider domains advertise through it; offer
  references ride its bridge shapes.
- ``developerapi`` — M013 Developer Connectivity API (DEC-0113): the
  canonical application boundary.  COMOS is modeled as an EXTERNAL
  application over the SDK client + public request surface; it
  holds no other ADCOS dependency.
- ``commercial`` — M009 Usage and Commercial Reconciliation
  (DEC-0109): the commercial-terms surface.  The REAL
  ``CommercialCore`` runs in bound mode — the reconciliation
  account cites THE canonical contract, and the forward actions
  respect the canonical-state floors (the walk never runs ahead of
  the contract; LOCK-113).
- ``usage`` — M009 Usage and Commercial Reconciliation
  (DEC-0109): the usage evidence attribution.  The REAL
  ``UsageLedger`` admits the delivered-traffic evidence against a
  contract-cited index — every usage record is bound to THE
  contract by construction, and the sealed statement consumes the
  tariff resolved from the offer pricing DATA (LOCK-113).

DETERMINISTIC SIMULATION SEAMS (disclosed, pending children — DATA
producers, never authorities, never canonical mutations):

- M004 Eligibility and Policy (constraint-aware selection) ->
  ``comos.seams.SelectionSeam``
- M005 Evidence and Assurance -> ``comos.seams.AssuranceSeam``
- M006 Execution Plan -> ``comos.seams.ExecutionPlanSeam``
- M007 Provider/Standard Adapters (realization + delivered facts)
  -> ``comos.seams.ProviderRealizationSeam``

M008 (Replan and Failover) has NO step in the frozen 6-step COMOS
flow (the flow carries no degradation/failure/replan step) and is
deliberately NOT represented by a seam: the pending M008 child is
never composed, never exercised, never claimed (disclosed in
``docs/M012-evidence.md``).  M009 is NOT a seam here — it is
ACCEPTED (DEC-0109) and composed as real authority.

The single seam registry is :data:`comos.seams.SIMULATION_SEAMS`.

Harness surfaces:

- :class:`comos.vertical.ComosVertical` — one golden scenario
  driven through the frozen 6-step flow (three scenarios:
  dual-provider-delivery, constraint-exclusion,
  requirements-unsatisfied).
- :class:`comos.evidence.EvidenceLedger` — the fail-closed
  attributable evidence ledger.
- :class:`comos.application.ComosApplication` — the external
  COMOS boundary (LOCK-120) over the M013 public surface.

Determinism (LOCK-119): injected instants only, content-derived
scenario digests, sorted iteration, no wall clock, no randomness, no
UUIDs, no network, no secrets.
"""

from __future__ import annotations

from .application import (
    COMOS_APPLICATION_NAME,
    COMOS_DEVELOPER_ID,
    COMOS_OWNED_DOMAINS,
    FORBIDDEN_MEMBER_STEMS,
    INTENT_MEMBER_VOCABULARY,
    REASON_BOUNDARY,
    REASON_FAIL_CLOSED,
    REASON_INVALID_INPUT,
    REASON_MEMBER_AUDIT,
    REASON_NOT_BOUND,
    REASON_VOCABULARY,
    REQUIREMENT_DIMENSIONS,
    REQUIREMENTS_MEMBER_VOCABULARY,
    ComosApplication,
    ComosError,
    ComosIntentSpec,
    ComosRequirementsSpec,
    audit_member_name,
)
from .evidence import (
    EVIDENCE_ISSUERS,
    EVIDENCE_KINDS,
    Attribution,
    EvidenceEntry,
    EvidenceLedger,
)
from .seams import (
    REALIZATION_EVENT_KINDS,
    SEAM_IDS,
    SIMULATION_SEAMS,
    AssuranceSeam,
    CandidateDecision,
    ConstraintEvaluation,
    DeliveredFact,
    ExecutionPlanSeam,
    FailureSchedule,
    PlanSegment,
    ProviderRealizationSeam,
    RealizationEvent,
    RequirementsEvaluation,
    RequirementVerdict,
    SelectionDecision,
    SelectionSeam,
    SeamDisclosure,
    SimulatedExecutionPlan,
    evaluate_constraint,
    evaluate_offer_against_constraints,
    evaluate_requirements_against_offer,
)
from .vertical import (
    BILLABLE_UNIT,
    FROZEN_FLOW,
    OBSERVATION_ENDPOINT_KEY,
    OBSERVATION_ENDPOINT_URL,
    OBSERVATION_EVENT_TYPES,
    PROVIDER_ALPHA,
    PROVIDER_ALPHA_MATERIAL,
    PROVIDER_BETA,
    SCENARIOS,
    SCENARIO_CONSTRAINT_EXCLUSION,
    SCENARIO_DUAL_PROVIDER_DELIVERY,
    SCENARIO_REQUIREMENTS_UNSATISFIED,
    SETTLEMENT_CONFIRMATION_REF,
    ComosVertical,
    StepRecord,
    VerticalResult,
    VerticalScenario,
    run_scenario,
)

#: The composition map (machine-readable; the battery re-asserts it).
COMPOSITION_MAP = {
    "real_authorities": (
        "contracts (M002, DEC-0102)",
        "offers (M003, DEC-0103)",
        "developerapi (M013, DEC-0113)",
        "commercial (M009, DEC-0109, bound mode)",
        "usage (M009, DEC-0109)",
    ),
    "simulation_seams": SEAM_IDS,
    "boundary": (
        "COMOS is an EXTERNAL application over the M013 public "
        "surface only (LOCK-120); ADCOS supplies gateway "
        "connectivity only"
    ),
}

__all__ = [
    # composition disclosure
    "COMPOSITION_MAP",
    "SEAM_IDS",
    "SIMULATION_SEAMS",
    "SeamDisclosure",
    # application boundary
    "COMOS_APPLICATION_NAME",
    "COMOS_DEVELOPER_ID",
    "COMOS_OWNED_DOMAINS",
    "ComosApplication",
    "ComosError",
    "ComosIntentSpec",
    "ComosRequirementsSpec",
    "FORBIDDEN_MEMBER_STEMS",
    "INTENT_MEMBER_VOCABULARY",
    "REASON_BOUNDARY",
    "REASON_FAIL_CLOSED",
    "REASON_INVALID_INPUT",
    "REASON_MEMBER_AUDIT",
    "REASON_NOT_BOUND",
    "REASON_VOCABULARY",
    "REQUIREMENT_DIMENSIONS",
    "REQUIREMENTS_MEMBER_VOCABULARY",
    "audit_member_name",
    # evidence
    "EVIDENCE_ISSUERS",
    "EVIDENCE_KINDS",
    "Attribution",
    "EvidenceEntry",
    "EvidenceLedger",
    # seams
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
    "SelectionDecision",
    "SelectionSeam",
    "SimulatedExecutionPlan",
    "evaluate_constraint",
    "evaluate_offer_against_constraints",
    "evaluate_requirements_against_offer",
    # the vertical driver
    "BILLABLE_UNIT",
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
