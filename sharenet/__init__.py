"""ADCOS ShareNet vertical-proof harness (M010 — Vertical Proofs:
ShareNet, R7-CORE-001 child, DEC-0101; dependency M013 satisfied by
DEC-0113).

The M010 mandate: prove the FROZEN 8-step ShareNet flow of
``spec/integration/vertical-proof.md`` (ACR-014) as a SOFTWARE-class
deterministic vertical proof — application-funded connectivity and
failure recovery — with ShareNet's application semantics staying
ShareNet's (LOCK-120: compatibility proof, never an ownership
transfer).

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
  canonical application boundary.  ShareNet is modeled as an
  EXTERNAL application over the SDK client + public request surface;
  it holds no other ADCOS dependency.

DETERMINISTIC SIMULATION SEAMS (disclosed, pending children — DATA
producers, never authorities, never canonical mutations):

- M004 Eligibility and Policy -> ``sharenet.seams.EligibilitySeam``
- M005 Evidence and Assurance -> ``sharenet.seams.AssuranceSeam``
- M006 Execution Plan -> ``sharenet.seams.ExecutionPlanSeam``
- M007 Provider/Standard Adapters (realization) ->
  ``sharenet.seams.ProviderRealizationSeam``
- M008 Replan and Failover -> ``sharenet.seams.ReplanEngine``
  (LOCK-108 fail-closed)
- M009 Usage and Commercial Reconciliation ->
  ``sharenet.seams.UsageObservationSeam``

The single seam registry is :data:`sharenet.seams.SIMULATION_SEAMS`.

Harness surfaces:

- :class:`sharenet.vertical.ShareNetVertical` — one golden scenario
  driven through the frozen 8-step flow (three scenarios:
  degraded-recovery, failed-recovery, terminal-failure).
- :class:`sharenet.evidence.EvidenceLedger` — the fail-closed
  attributable evidence ledger (step 8).
- :class:`sharenet.application.ShareNetApplication` — the external
  ShareNet boundary (LOCK-120) over the M013 public surface.

Determinism (LOCK-119): injected instants only, content-derived
scenario digests, sorted iteration, no wall clock, no randomness, no
UUIDs, no network, no secrets.
"""

from __future__ import annotations

from .application import (
    FORBIDDEN_MEMBER_STEMS,
    INTENT_MEMBER_VOCABULARY,
    REASON_BOUNDARY,
    REASON_FAIL_CLOSED,
    REASON_INVALID_INPUT,
    REASON_MEMBER_AUDIT,
    REASON_NOT_BOUND,
    REASON_VOCABULARY,
    SHARENET_APPLICATION_NAME,
    SHARENET_DEVELOPER_ID,
    ShareNetApplication,
    ShareNetError,
    ShareNetIntentSpec,
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
    CandidateRejection,
    ConstraintEvaluation,
    EligibilityDecision,
    EligibilitySeam,
    ExecutionPlanSeam,
    FailureSchedule,
    FailoverDecision,
    PlanSegment,
    ProviderRealizationSeam,
    RealizationEvent,
    ReplanEngine,
    SeamDisclosure,
    SimulatedExecutionPlan,
    UsageObservation,
    UsageObservationSeam,
    evaluate_constraint,
    evaluate_offer_against_constraints,
)
from .vertical import (
    FROZEN_FLOW,
    OBSERVATION_EVENT_TYPES,
    OBSERVATION_ENDPOINT_KEY,
    OBSERVATION_ENDPOINT_URL,
    PROVIDER_A,
    PROVIDER_A_MATERIAL,
    PROVIDER_B,
    SCENARIOS,
    SCENARIO_DEGRADED_RECOVERY,
    SCENARIO_FAILED_RECOVERY,
    SCENARIO_TERMINAL_FAILURE,
    SHARENET_RETAINED_AUTHORITY,
    ShareNetVertical,
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
    ),
    "simulation_seams": SEAM_IDS,
    "boundary": (
        "ShareNet is an EXTERNAL application over the M013 public "
        "surface only (LOCK-120)"
    ),
}

__all__ = [
    # composition disclosure
    "COMPOSITION_MAP",
    "SEAM_IDS",
    "SIMULATION_SEAMS",
    "SeamDisclosure",
    # application boundary
    "FORBIDDEN_MEMBER_STEMS",
    "INTENT_MEMBER_VOCABULARY",
    "REASON_BOUNDARY",
    "REASON_FAIL_CLOSED",
    "REASON_INVALID_INPUT",
    "REASON_MEMBER_AUDIT",
    "REASON_NOT_BOUND",
    "REASON_VOCABULARY",
    "SHARENET_APPLICATION_NAME",
    "SHARENET_DEVELOPER_ID",
    "ShareNetApplication",
    "ShareNetError",
    "ShareNetIntentSpec",
    "audit_member_name",
    # evidence
    "EVIDENCE_ISSUERS",
    "EVIDENCE_KINDS",
    "Attribution",
    "EvidenceEntry",
    "EvidenceLedger",
    # seams
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
    "SimulatedExecutionPlan",
    "UsageObservation",
    "UsageObservationSeam",
    "evaluate_constraint",
    "evaluate_offer_against_constraints",
    # the vertical driver
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
