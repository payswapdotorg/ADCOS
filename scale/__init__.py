"""ADCOS federation-at-scale harness (WORK-039).

The deterministic multi-domain federation verification layer over the
ACCEPTED authorities:

- **one real WORK-015 ``FederationStore`` per domain** -- the
  horizontal-scale unit is the per-domain real authority; the harness
  never builds a second, centralized federation authority, never
  duplicates identity/session/routing/policy semantics, and never
  modifies a frozen protocol semantic;
- **WORK-031 simulator primitives** -- the injected
  :class:`~simulator.time.ScenarioClock` and the documented
  :class:`~simulator.random.DeterministicStream` (deterministic time
  and key material; no wall clock, no ``random`` module anywhere in
  the family);
- **WORK-033 / WORK-036 composition surfaces** -- the integration leg
  federates two real booted ``AgentRuntime`` instances and one real
  booted ``NetworkAppliance`` through their own federation stores,
  constructing them exactly the way the accepted batteries do.

What the harness proves (the frozen WORK-039 acceptance criteria):

- **federation scales horizontally** -- deterministic multi-domain
  scenarios over frozen topology shapes with EXACT predicted object
  counts (relationships, grants, events) and a bounded-resource
  envelope (``scale.topology`` / ``scale.world`` / ``scale.scenario``);
- **failure domains remain isolated** -- failures partition DELIVERY
  only (transport-plane simulation, never protocol state); isolation
  is proven by byte-identical store digests across failure windows,
  fail-closed foreign/identity-confused declarations, and LOCK-012
  local-first survival (``scale.partition``);
- **revocation propagates predictably** -- the authoritative store
  revokes; declarations propagate in explicit rounds bounded by the
  computed graph distance; idempotency and post-recovery convergence
  are observed and journaled; observation is checked against the
  bound and any divergence fails closed (``scale.revocation``).

Simulation never becomes protocol truth: every protocol mutation
flows through a real store's public contract, and the journal is
evidence only.  Real-deployment evidence is NOT part of the frozen
W039 acceptance criterion; nothing in this package can claim it
(``scale.evidence`` enforces the anti-promotion rule in code).

The frozen public API surface is asserted by the battery.
"""

from __future__ import annotations

from .errors import SCALE_PREFIX, ScaleError, ScaleReasonCode
from .model import (
    SCALE_EVIDENCE_CLASS_MAP,
    ConvergenceRecord,
    IsolationProof,
    ScaleEvent,
    ScaleEventType,
    ScaleRunResult,
    TopologyShape,
    scale_event_list_digest,
    scale_events_canonical_bytes,
)
from .topology import (
    CLIQUE_SIZE,
    FULL_MESH_MAX_DOMAINS,
    DomainMaterial,
    build_domain_materials,
    delivery_distances,
    delivery_paths,
    expected_edge_count,
    neighbor_map,
    topology_edges,
    validate_topology,
)
from .world import ScaleWorld, build_world, world_summary
from .partition import (
    PartitionState,
    check_isolation,
    foreign_declaration_rejected,
    local_first_survives,
    up_edges,
)
from .revocation import (
    RELAY_MESSAGE_TYPE,
    RevocationOutcome,
    convergence_record,
    propagate_revocation,
)
from .scenario import (
    ExportPlan,
    FailurePlan,
    RevocationPlan,
    ScaleScenarioSpec,
    run_scale_scenario,
    scenario_summary,
    verify_scale_replay,
)
from .integration import (
    IntegrationResult,
    run_integration_scenario,
    verify_integration_replay,
)
from .evidence import (
    DEPLOYMENT_EVIDENCE_STATEMENT,
    SCALE_EVIDENCE_STATUS,
    assert_no_deployment_claim,
    classify_scale_evidence,
)

__all__ = [
    # errors
    "SCALE_PREFIX",
    "ScaleError",
    "ScaleReasonCode",
    # vocabularies and value records
    "ScaleEventType",
    "TopologyShape",
    "SCALE_EVIDENCE_CLASS_MAP",
    "ScaleEvent",
    "scale_events_canonical_bytes",
    "scale_event_list_digest",
    "ConvergenceRecord",
    "IsolationProof",
    "ScaleRunResult",
    # topology (pure DATA)
    "CLIQUE_SIZE",
    "FULL_MESH_MAX_DOMAINS",
    "DomainMaterial",
    "build_domain_materials",
    "topology_edges",
    "expected_edge_count",
    "neighbor_map",
    "delivery_distances",
    "delivery_paths",
    "validate_topology",
    # the multi-domain world over real stores
    "ScaleWorld",
    "build_world",
    "world_summary",
    # partition / failure-domain isolation
    "PartitionState",
    "up_edges",
    "check_isolation",
    "foreign_declaration_rejected",
    "local_first_survives",
    # revocation propagation (hop-by-hop relay delivery)
    "RELAY_MESSAGE_TYPE",
    "RevocationOutcome",
    "propagate_revocation",
    "convergence_record",
    # the deterministic scale scenario (class B)
    "ExportPlan",
    "FailurePlan",
    "RevocationPlan",
    "ScaleScenarioSpec",
    "run_scale_scenario",
    "verify_scale_replay",
    "scenario_summary",
    # the agent/appliance integration leg (class B)
    "IntegrationResult",
    "run_integration_scenario",
    "verify_integration_replay",
    # the three-class evidence model
    "SCALE_EVIDENCE_STATUS",
    "DEPLOYMENT_EVIDENCE_STATEMENT",
    "classify_scale_evidence",
    "assert_no_deployment_claim",
]
