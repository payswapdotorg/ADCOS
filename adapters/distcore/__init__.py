"""ADCOS distributed-core adapter family (WORK-024): distributed
user-plane / local breakout / UPF placement behind the frozen
``/adapters`` boundary.

Implements the frozen WORK-024 backlog entry (spec/work-items.md)
behind the frozen ``/adapters`` module boundary
(spec/architecture.md §29): distributed user-plane and local-service
placement -- keep local traffic local, fail over remote gateways,
coexist with real 5G UPF and generic IP gateway adapters, and choose
local versus remote breakout through policy.  Peers: ``adapters.ip``
(WORK-018), ``adapters.fivegc`` (WORK-019), ``adapters.wifi``
(WORK-021), ``adapters.backhaul`` (WORK-022), ``adapters.mesh``
(WORK-023) -- all accepted on this branch (peers are CONSUMED
through their public manager APIs at the composition root, never
imported by this family).

The boundary (WORK-024 -- the architect-anchored handoff):

    +----------------------------------------------+
    |  ADCOS core (policy/routing/session auth.)   |
    |        | breakout decisions as policy DATA   |
    |        | ordinary Path objects + path refs    |
    |        | sacred session_id (WORK-012)        |
    |        v                                     |
    |  DistributedCoreManager  --mediated-->       |
    |        SandboxedBreakoutProvider             |
    |        |                          |          |
    |        |        BreakoutProviderContract(ABC)|
    |        |                     /        \\     |
    |        |     ReferenceIPGateway-  Reference- |
    |        |     Engine (local)        UPFEngine |
    |        |                            (remote) |
    |        v                                     |
    |  DistCoreTechnologyAdapter (WORK-016 bridge)|
    +----------------------------------------------+

Discipline carried by the whole family:

* **Composition, not competition.**  The distributed core COMPOSES
  existing authorities: session authority stays WORK-012 (the
  sacred ``session_id`` is consulted read-only and never
  reinterpreted), routing authority stays WORK-011 (ordinary ``Path``
  objects consumed as DATA; no second routing authority -- the
  local-first choice among registered paths is the caller's, driven
  by the policy-determined mode), policy authority stays WORK-010
  (``apply_policy_decision`` verifies a REAL tamper-evident
  ALLOW-effect ``PolicyDecision``; a denied decision never
  authorizes a breakout), and ordinary IP semantics stay WORK-018
  (the family composes IP paths and recreates no IPv6/NAT/routing
  primitive).
* **A gateway is a role, not an identity.**  Gateway registration is
  evidence-bearing DATA (reporter identity + provenance class + a
  claim digest binding the evidence to the whole claim);
  unevidenced registration fails closed (``GATEWAY_UNEVIDENCED``);
  a ``remote-claim`` gateway never silently becomes direct-observed.
* **UPF and IP-gateway state stay adapter-owned.**  Provider state
  (gateway tables, N6/N4 anchors, delivery logs) lives behind the
  sandboxed contract; no Open5GS, N3IWF, vendor, or gateway
  implementation type crosses into core authority (LOCK-016/017).
* **Graceful degradation and explicit failover.**  An unavailable
  local gateway fails closed (``GATEWAY_UNAVAILABLE``) while
  alternate remote paths remain establishable; failover is an
  EXPLICIT recorded transition that preserves the logical session
  identity (the supersedes chain; no retroactive rebinding), and a
  partitioned OLD provider never blocks the failover (post-commit
  best-effort cleanup).
* **Transactional discipline.**  Validation is side-effect free;
  the identity-derivation nonce advances ONLY in commit phases
  (candidate-sequence pattern); externally confirmed operations
  commit local state only after success, with compensation for
  partially completed external operations.
* **Replaceability.**  ``ReferenceIPGatewayEngine`` and
  ``ReferenceUPFEngine`` are independent implementations behind the
  SAME contract; swapping the default provider preserves live
  gateways/breakouts (B2 per-record ownership) and canonical state.

Module catalog (the family surface; later WORK-024 tasks extend
these exports -- never narrow them):

- contract.py      BreakoutProviderContract ABC (11 operations) +
                   BreakoutContext least-authority facade +
                   SessionReader/SessionView
- model.py         frozen vocabularies + GatewayDescriptor/Evidence/
                   Candidate, BreakoutDecision (policy DATA),
                   BreakoutBinding, BreakoutAllocation, EgressOutcome,
                   BreakoutEgress, DistCoreObservation, DistCoreEvent +
                   the deterministic derive_* family
- validation.py    opaque-ref grammar, ref/session separation,
                   credential-like rejection, NodeID/path/session
                   shapes, external-gateway-id DATA validation
- errors.py        DistCoreError/DistCoreReasonCode/DistCoreFailure
                   (typed, isolated, secret-free)
- sandbox.py       SandboxedBreakoutProvider (exception isolation,
                   contract enforcement, deterministic budget) +
                   STEP_CHARGES
- engine.py        ReferenceIPGatewayEngine -- the LOCAL breakout
                   reference implementation (validate/commit split,
                   candidate-sequence discipline)
- upf.py           ReferenceUPFEngine -- the INDEPENDENT remote
                   breakout (5G-UPF-shaped) reference implementation
- manager.py       DistributedCoreManager -- the mediated
                   composition service (B2 ownership, policy
                   decision verification, path/gateway resolution,
                   failover with compensation, canonical state)
- bridge.py        DistCoreTechnologyAdapter -- the WORK-016 nine-op
                   SDK bridge over the manager
- serialization.py canonical-JSON reduction helpers

Verification: ``python3 tools/distcore_selftest.py`` (the WORK-024
selftest battery: local-traffic-local, remote gateway failover and
partition recovery, UPF/IP-gateway coexistence, policy-determined
breakout, session identity across gateway changes, real WORK-018
IP-seam and WORK-019 5GC-seam composition, determinism, frozen-spec
identity, and validate/commit sequence discipline -- failed
operations consume no identity-derivation state).
"""

from __future__ import annotations

from .contract import (
    CONTEXT_SURFACE,
    CONTRACT_OPERATIONS,
    BreakoutContext,
    BreakoutProviderContract,
    SessionReader,
    SessionView,
)
from .errors import (
    DISTCORE_PREFIX,
    DistCoreError,
    DistCoreFailure,
    DistCoreReasonCode,
)
from .model import (
    AllocationState,
    BreakoutAllocation,
    BreakoutBinding,
    BreakoutDecision,
    BreakoutEgress,
    BreakoutMode,
    BreakoutState,
    DistCoreObservation,
    DistCoreEvent,
    EvidenceSourceClass,
    GatewayCandidate,
    GatewayDescriptor,
    GatewayEvidence,
    GatewayRoleClass,
    GatewayState,
    LinkMetricName,
    derive_allocation_ref,
    derive_binding_id,
    derive_breakout_ref,
    derive_decision_ref,
    derive_gateway_claim_digest,
    derive_gateway_ref,
    derive_integration_id,
    EgressOutcome,
)
from .sandbox import (
    DEFAULT_STEP_BUDGET,
    FAILURE_THRESHOLD_DEGRADED,
    FAILURE_THRESHOLD_FAILED,
    DistCoreOpResult,
    SandboxedBreakoutProvider,
    STEP_CHARGES,
)
from .engine import (
    MAX_EGRESS_BYTES,
    RATE_KINDS_BPS,
    ReferenceIPGatewayEngine,
)
from .upf import ReferenceUPFEngine
from .manager import DEFAULT_INTEGRATION_ID, DistributedCoreManager
from .bridge import DistCoreTechnologyAdapter
from .serialization import (
    canonical_json_bytes,
    to_canonical_bytes,
    to_canonical_dict,
)
from .validation import (
    assert_ref_session_separation,
    reject_credential_like_text,
    validate_breakout_mode,
    validate_capacity_bps,
    validate_claim_digest,
    validate_credential_slot_name,
    validate_evidence_source,
    validate_external_gateway_id,
    validate_gateway_name,
    validate_gateway_role,
    validate_instant,
    validate_locality_label,
    validate_node_id,
    validate_opaque_ref,
    validate_path_ref,
    validate_policy_decision_id,
    validate_session_ref,
)

__all__ = [
    # Contract surface
    "CONTEXT_SURFACE",
    "CONTRACT_OPERATIONS",
    "BreakoutContext",
    "BreakoutProviderContract",
    "SessionReader",
    "SessionView",
    # Errors
    "DISTCORE_PREFIX",
    "DistCoreError",
    "DistCoreFailure",
    "DistCoreReasonCode",
    # Model
    "AllocationState",
    "BreakoutAllocation",
    "BreakoutBinding",
    "BreakoutDecision",
    "BreakoutEgress",
    "BreakoutMode",
    "BreakoutState",
    "DistCoreObservation",
    "DistCoreEvent",
    "EvidenceSourceClass",
    "GatewayCandidate",
    "GatewayDescriptor",
    "GatewayEvidence",
    "GatewayRoleClass",
    "GatewayState",
    "LinkMetricName",
    "derive_allocation_ref",
    "derive_binding_id",
    "derive_breakout_ref",
    "derive_decision_ref",
    "derive_gateway_claim_digest",
    "derive_gateway_ref",
    "derive_integration_id",
    "EgressOutcome",
    # Sandbox
    "DEFAULT_STEP_BUDGET",
    "FAILURE_THRESHOLD_DEGRADED",
    "FAILURE_THRESHOLD_FAILED",
    "DistCoreOpResult",
    "SandboxedBreakoutProvider",
    "STEP_CHARGES",
    # Implementations
    "MAX_EGRESS_BYTES",
    "RATE_KINDS_BPS",
    "ReferenceIPGatewayEngine",
    "ReferenceUPFEngine",
    # Manager + bridge
    "DEFAULT_INTEGRATION_ID",
    "DistributedCoreManager",
    "DistCoreTechnologyAdapter",
    # Serialization
    "canonical_json_bytes",
    "to_canonical_bytes",
    "to_canonical_dict",
    # Validators
    "assert_ref_session_separation",
    "reject_credential_like_text",
    "validate_breakout_mode",
    "validate_capacity_bps",
    "validate_claim_digest",
    "validate_credential_slot_name",
    "validate_evidence_source",
    "validate_external_gateway_id",
    "validate_gateway_name",
    "validate_gateway_role",
    "validate_instant",
    "validate_locality_label",
    "validate_node_id",
    "validate_opaque_ref",
    "validate_path_ref",
    "validate_policy_decision_id",
    "validate_session_ref",
]
