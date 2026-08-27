"""ADCOS service registry / edge compute (WORK-025).

The technology-neutral service layer: local service advertisement,
discovery, policy-consumed authorization, provider-neutral edge
execution, and federation-scoped visibility -- one coherent fabric
with connectivity while service semantics stay independent of access
technology.

Boundary block (the frozen WORK-025 invariants):

- SERVICE IDENTITY != NODE IDENTITY != SESSION ID != PATH ID !=
  CAPABILITY ID != RESOURCE ID != FEDERATION ID != provider
  identity.  A service may move between edge nodes without becoming
  a different service identity.
- An advertisement is attributable DATA, never a capability claim,
  availability fact, or capacity reservation.
- Policy authority remains WORK-010 (REAL PolicyDecision consumed);
  federation authority remains WORK-015 (scope checks consumed as
  DATA); routing authority remains WORK-011 (discovery returns
  locations, never routes); session authority remains WORK-012
  (opaque authorized refs only); resource vocabulary remains
  WORK-008 (kinds and base units as DATA).
- Local-first resilience is normative: upstream failure never erases
  valid local service state (LOCK-012).
- Execution is a seam, not an application platform (LOCK-016/017);
  least authority applies to every execution context; secrets never
  become service-registry DATA (LOCK-023).
"""

from __future__ import annotations

from .contract import (
    CONTEXT_SURFACE,
    CONTRACT_OPERATIONS,
    DEFAULT_STEP_BUDGET,
    ExecutionProviderContract,
    FederationReader,
    ServiceContext,
    SessionReader,
    SessionView,
)
from .errors import (
    SERVICES_PREFIX,
    ServiceError,
    ServiceFailure,
    ServiceReasonCode,
)
from .execution import (
    MAX_CONCURRENT_ADMISSIONS,
    MAX_REQUEST_BYTES,
    ReferenceEdgeExecutor,
)
from .federation import (
    SERVICE_DISCOVER_SCOPE,
    SERVICE_FEDERATION_SCOPES,
    SERVICE_INVOKE_SCOPE,
    export_service_exposures,
    peer_claim_fingerprint,
    validate_federation_scope,
)
from .model import (
    AdmissionState,
    AdvertisementEvidence,
    AllocationState,
    CapacityAllocation,
    EvidenceSourceClass,
    ExecutionOutcome,
    ExecutionStatus,
    ExposureState,
    FederationExposure,
    InvocationDecision,
    PlacementTransition,
    ServiceAdmission,
    ServiceAdvertisement,
    ServiceCandidate,
    ServiceCapacity,
    ServiceDescriptor,
    ServiceEvent,
    ServiceEventType,
    ServiceLifecycle,
    ServiceMetricName,
    ServiceObservation,
    ServiceTombstone,
    VisibilityScope,
    derive_admission_ref,
    derive_advertisement_claim_digest,
    derive_allocation_ref,
    derive_decision_ref,
    derive_execution_ref,
    derive_exposure_ref,
    derive_integration_id,
    derive_service_ref,
)
from .registry import DEFAULT_INTEGRATION_ID, ServiceRegistry
from .sandbox import (
    FAILURE_THRESHOLD_DEGRADED,
    FAILURE_THRESHOLD_FAILED,
    STEP_CHARGES,
    SandboxedExecutionProvider,
    ServiceOpResult,
)
from .serialization import to_canonical_bytes, to_canonical_dict
from .validation import (
    SERVICE_CAPACITY_KINDS,
    assert_ref_session_separation,
    assert_service_node_separation,
    reject_credential_like_text,
)

__all__ = [
    # contract
    "CONTEXT_SURFACE",
    "CONTRACT_OPERATIONS",
    "DEFAULT_STEP_BUDGET",
    "ExecutionProviderContract",
    "FederationReader",
    "ServiceContext",
    "SessionReader",
    "SessionView",
    # errors
    "SERVICES_PREFIX",
    "ServiceError",
    "ServiceFailure",
    "ServiceReasonCode",
    # execution
    "MAX_CONCURRENT_ADMISSIONS",
    "MAX_REQUEST_BYTES",
    "ReferenceEdgeExecutor",
    # federation DATA translation
    "SERVICE_DISCOVER_SCOPE",
    "SERVICE_FEDERATION_SCOPES",
    "SERVICE_INVOKE_SCOPE",
    "export_service_exposures",
    "peer_claim_fingerprint",
    "validate_federation_scope",
    # model
    "AdmissionState",
    "AdvertisementEvidence",
    "AllocationState",
    "CapacityAllocation",
    "EvidenceSourceClass",
    "ExecutionOutcome",
    "ExecutionStatus",
    "ExposureState",
    "FederationExposure",
    "InvocationDecision",
    "PlacementTransition",
    "ServiceAdmission",
    "ServiceAdvertisement",
    "ServiceCandidate",
    "ServiceCapacity",
    "ServiceDescriptor",
    "ServiceEvent",
    "ServiceEventType",
    "ServiceLifecycle",
    "ServiceMetricName",
    "ServiceObservation",
    "ServiceTombstone",
    "VisibilityScope",
    "derive_admission_ref",
    "derive_advertisement_claim_digest",
    "derive_allocation_ref",
    "derive_decision_ref",
    "derive_execution_ref",
    "derive_exposure_ref",
    "derive_integration_id",
    "derive_service_ref",
    # registry
    "DEFAULT_INTEGRATION_ID",
    "ServiceRegistry",
    # sandbox
    "FAILURE_THRESHOLD_DEGRADED",
    "FAILURE_THRESHOLD_FAILED",
    "STEP_CHARGES",
    "SandboxedExecutionProvider",
    "ServiceOpResult",
    # serialization
    "to_canonical_bytes",
    "to_canonical_dict",
    # validation
    "SERVICE_CAPACITY_KINDS",
    "assert_ref_session_separation",
    "assert_service_node_separation",
    "reject_credential_like_text",
]
