"""ADCOS service registry / edge runtime manager (WORK-025).

:class:`ServiceRegistry` is the composition root of the WORK-025
service layer -- the "ServiceRegistry / EdgeRuntime" box of the
frozen WORK-025 handoff diagram.  It owns EXACTLY the service-layer
facts and composes every other authority through its public seams:

- **Advertisement lifecycle** -- evidence-verified, deterministic,
  repeat-safe registration; withdrawal tombstones with replay
  protection; explicit, auditable placement transitions (the
  ServiceID stays stable while the host changes).
- **Discovery** -- local-first lookup/claim mechanism: freshness,
  visibility, tenant isolation, policy filtering, capability /
  intent compatibility.  Discovery returns candidate service
  LOCATIONS and never computes, scores, or enumerates network routes
  (routing authority remains WORK-011; connectivity to a selected
  service composes ordinary WORK-011 paths / WORK-024 breakout
  semantics at the composition root).
- **Policy** -- :meth:`apply_policy_decision` consumes a REAL
  tamper-evident ``policy.model.PolicyDecision`` (the WORK-010
  authority); the registry never evaluates policy, never invents
  trust, and never overrides a deny (denied decisions fail closed
  with DECISION_DENIED).  The authorized (service, session, caller,
  tenant) scope is EXTRACTED FROM THE DECISION'S OWN digest-covered
  invocation binding -- apply accepts no scope parameters, so the
  service layer can never wrap a valid ALLOW around a different
  authorization scope (the PR #26 Architect-review authority
  boundary).  A discovered service is never implicitly authorized
  to execute merely because it was advertised.
- **Execution** -- :meth:`admit_execution` / :meth:`execute_request`
  / :meth:`release_execution` compose the provider-neutral edge
  execution seam behind a sandboxed provider: authorization is
  verified BEFORE any provider-side effect; provider faults are
  isolated typed failure values; data-path executions append no
  canonical events.
- **Capacity** -- advertisement capacity is WORK-008 DATA (an
  offer); the explicit resource-admission path (admission and
  allocation ledgers) is the reservation; exhaustion fails closed
  leaving authoritative state unchanged (the WORK-022 lesson:
  existence of a service record is not evidence that its resource
  reservation exists).
- **Federation** -- exposure application/removal consumes the
  read-only WORK-015 scope-check projection as DATA; peer claims are
  imported as federation-scoped remote-claim records; removing an
  exposure never deletes the local service record.
- **Local-first resilience** -- the registry is local, deterministic
  state: with upstream connectivity unavailable, local records stay
  registered, local discovery keeps working, local execution keeps
  working, and the outage is REPORTED (observation) without being
  mistaken for local state corruption (LOCK-012; WORK-025
  invariant 7).

Identity: the derivation nonce for allocation refs advances ONLY
inside commit phases (the WORK-023/024 candidate-sequence
discipline); admission refs derive inside the provider under the
same discipline.  Failed operations consume no derivation state and
never partially mutate canonical state (WORK-025 invariant 13).

Canonical state contains authoritative service facts only: no
sockets, process ids, implementation labels, filesystem paths,
secrets, stack traces, or implicitly generated timestamps
(WORK-025 invariant 14).  Determinism: identical inputs and injected
instants produce byte-identical canonical bytes across runs and
hash seeds (WORK-025 invariant 17).
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Tuple

from intent.model import ConnectivityIntent as _RealConnectivityIntent
from policy.model import PolicyDecision
from protocol.temporal import TemporalError, parse_instant

from .contract import (
    DEFAULT_STEP_BUDGET,
    ExecutionProviderContract,
    FederationReader,
    SessionReader,
)
from .authorization import (
    extract_invocation_binding,
)
from .errors import ServiceError, ServiceFailure, ServiceReasonCode
from .execution import MAX_REQUEST_BYTES
from .federation import SERVICE_DISCOVER_SCOPE, validate_federation_scope
from .model import (
    AdmissionState,
    AdvertisementEvidence,
    AllocationState,
    CapacityAllocation,
    EvidenceSourceClass,
    ExecutionOutcome,
    FederationExposure,
    InvocationDecision,
    PlacementTransition,
    ServiceAdmission,
    ServiceAdvertisement,
    ServiceCandidate,
    ServiceCapacity,
    ServiceEvent,
    ServiceEventType,
    ServiceLifecycle,
    ServiceMetricName,
    ServiceObservation,
    ServiceTombstone,
    VisibilityScope,
    derive_advertisement_claim_digest,
    derive_allocation_ref,
    derive_decision_ref,
    derive_exposure_ref,
    derive_integration_id,
    derive_service_ref,
)
from .sandbox import (
    SandboxedExecutionProvider,
    ServiceOpResult,
)
from .serialization import to_canonical_bytes as _bytes
from .validation import (
    SERVICE_CAPACITY_KINDS,
    reject_credential_like_text,
    validate_capacity_kind,
    validate_capacity_quantity,
    validate_instant,
    validate_node_id,
    validate_opaque_ref,
    validate_session_ref,
    validate_tenant_domain,
)

#: Default integration label (the instance identity input).
DEFAULT_INTEGRATION_ID = "services-integration"

#: Requirement keys that carry identity material: requirements are
#: opaque operational hints ONLY (never a second identity channel).
_FORBIDDEN_REQUIREMENT_KEYS = (
    "node_id", "session_id", "service_ref", "decision_ref",
    "admission_ref", "path_ref", "gateway_ref", "breakout_ref",
    "resource_id", "capability_id", "federation_id", "caller_node_id",
)

#: Intent dimensions the service layer evaluates deterministically
#: against declared service DATA (label dimensions).  Numeric
#: dimensions (latency, bandwidth, ...) are connectivity concerns
#: delegated to the WORK-011/W024 composition -- the service layer
#: neither scores nor filters them.
_LABEL_DIMENSIONS = ("locality", "service", "privacy")


class _ServiceEntry:
    """Internal registration bookkeeping."""

    __slots__ = ("candidate", "claim_digest")

    def __init__(self, candidate: ServiceCandidate, claim_digest: str) -> None:
        self.candidate = candidate
        self.claim_digest = claim_digest


class _ProviderRegistration:
    """Internal provider registration bookkeeping (diagnostics only --
    labels and sandboxes never enter canonical state)."""

    __slots__ = ("label", "sandbox")

    def __init__(self, label: str, sandbox: SandboxedExecutionProvider) -> None:
        self.label = label
        self.sandbox = sandbox


class _AdmissionEntry:
    """Internal admission bookkeeping: the admission record plus the
    OWNING provider sandbox (a provider swap never rebinds existing
    admissions -- the WORK-024 B2 discipline)."""

    __slots__ = ("admission", "sandbox")

    def __init__(
        self, admission: ServiceAdmission, sandbox: SandboxedExecutionProvider
    ) -> None:
        self.admission = admission
        self.sandbox = sandbox


class _AllocationEntry:
    """Internal allocation bookkeeping."""

    __slots__ = ("allocation",)

    def __init__(self, allocation: CapacityAllocation) -> None:
        self.allocation = allocation


class ServiceRegistry:
    """The WORK-025 service registry / edge runtime composition root."""

    def __init__(
        self,
        *,
        integration_id: Optional[str] = None,
        step_budget: int = DEFAULT_STEP_BUDGET,
        session_reader: Optional[SessionReader] = None,
        federation_reader: Optional[FederationReader] = None,
    ) -> None:
        label = integration_id if integration_id is not None else DEFAULT_INTEGRATION_ID
        if not isinstance(label, str) or not label:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "integration_id must be a non-empty str",
            )
        if isinstance(step_budget, bool) or not isinstance(step_budget, int):
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "step_budget must be an int",
            )
        if step_budget <= 0:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "step_budget must be positive",
            )
        if session_reader is not None and not isinstance(
            session_reader, SessionReader
        ):
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "session_reader must implement the SessionReader ABC",
            )
        if federation_reader is not None and not isinstance(
            federation_reader, FederationReader
        ):
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "federation_reader must implement the FederationReader ABC",
            )
        self._integration_id = derive_integration_id(label)
        self._step_budget = step_budget
        self._session_reader = session_reader
        self._federation_reader = federation_reader
        # Deterministic, insertion-ordered state.
        self._providers: List[_ProviderRegistration] = []
        self._default_sandbox: Optional[SandboxedExecutionProvider] = None
        self._services: Dict[str, _ServiceEntry] = {}
        self._tombstones: List[ServiceTombstone] = []
        self._placements: List[PlacementTransition] = []
        self._decisions: Dict[str, InvocationDecision] = {}
        self._exposures: Dict[str, FederationExposure] = {}
        self._admissions: Dict[str, _AdmissionEntry] = {}
        self._allocations: Dict[str, _AllocationEntry] = {}
        self._events: List[ServiceEvent] = []
        # Reference-model control (NOT canonical): upstream
        # connectivity availability for federated discovery.
        self._upstream_available = True
        # The registry-side derivation nonce for allocation refs:
        # advances ONLY inside commit phases.
        self._sequence = 0
        # Data-path counters (observation only, never canonical).
        self._executed_total = 0
        self._execution_failures = 0
        self._closed = False

    # ------------------------------------------------------------------ #
    # Guards and helpers
    # ------------------------------------------------------------------ #

    def _require_not_closed(self) -> None:
        if self._closed:
            raise ServiceError(
                ServiceReasonCode.ILLEGAL_STATE,
                "service registry is closed",
            )

    def _require_now(self, now: object) -> str:
        return validate_instant(now, label="now")

    def _append_event(
        self,
        event_type: str,
        now: str,
        *,
        service_ref: str = "",
        admission_ref: str = "",
        detail: str = "",
    ) -> None:
        self._events.append(
            ServiceEvent(
                event_type=event_type,
                instant=now,
                service_ref=service_ref,
                admission_ref=admission_ref,
                detail=detail,
            )
        )

    def _reject_identity_smuggling(self, requirements: Any) -> None:
        if requirements is None:
            return
        if not isinstance(requirements, dict):
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "requirements must be a mapping of opaque operational hints",
            )
        for key in requirements:
            if isinstance(key, str) and key in _FORBIDDEN_REQUIREMENT_KEYS:
                raise ServiceError(
                    ServiceReasonCode.INVALID_INPUT,
                    "requirements key %r carries identity material -- "
                    "requirements are opaque operational hints only" % (key,),
                )

    def _record_is_fresh(self, candidate: ServiceCandidate, now: str) -> bool:
        try:
            return parse_instant(now) < parse_instant(candidate.expires_at)
        except TemporalError:
            return False

    def _require_service_record(
        self, service_ref: str, now: str
    ) -> ServiceCandidate:
        entry = self._services.get(service_ref)
        if entry is None:
            if any(t.service_ref == service_ref for t in self._tombstones):
                raise ServiceError(
                    ServiceReasonCode.SERVICE_WITHDRAWN,
                    "service %r was withdrawn (tombstoned record; replay "
                    "protection active)" % (service_ref,),
                )
            raise ServiceError(
                ServiceReasonCode.SERVICE_UNKNOWN,
                "service %r is not registered" % (service_ref,),
            )
        if not self._record_is_fresh(entry.candidate, now):
            raise ServiceError(
                ServiceReasonCode.SERVICE_STALE,
                "service %r advertisement expired at %s (stale "
                "advertisements fail closed)" % (service_ref, entry.candidate.expires_at),
            )
        return entry.candidate

    def _decision_scope(
        self, decision: InvocationDecision
    ) -> Tuple[str, str, str, str]:
        return (
            decision.service_ref,
            decision.session_id,
            decision.caller_node_id,
            decision.tenant_domain,
        )

    def _latest_decision_for_scope(
        self, scope: Tuple[str, str, str, str]
    ) -> Optional[InvocationDecision]:
        latest: Optional[InvocationDecision] = None
        for decision in self._decisions.values():
            if self._decision_scope(decision) != scope:
                continue
            if latest is None or decision.applied_instant > latest.applied_instant:
                latest = decision
        return latest

    def _latest_placement_for_service(
        self, service_ref: str
    ) -> Optional[PlacementTransition]:
        latest: Optional[PlacementTransition] = None
        for placement in self._placements:
            if placement.service_ref != service_ref:
                continue
            if latest is None or placement.transitioned_at > latest.transitioned_at:
                latest = placement
        return latest

    def _decision_is_current(self, decision: InvocationDecision) -> bool:
        """A decision is current iff it is the latest applied decision
        for its scope AND no placement transition for the service
        occurred at or after its applied instant (relocation forces
        re-authorization under current policy -- WORK-025
        'Authorization is re-evaluated under current policy')."""
        latest = self._latest_decision_for_scope(self._decision_scope(decision))
        if latest is None or latest.decision_ref != decision.decision_ref:
            return False
        placement = self._latest_placement_for_service(decision.service_ref)
        if placement is not None and placement.transitioned_at >= decision.applied_instant:
            return False
        return True

    def _declared_capacity(
        self, service_ref: str, kind: str, *, now: str
    ) -> int:
        entry = self._services.get(service_ref)
        if entry is None or not self._record_is_fresh(entry.candidate, now):
            return 0
        total = 0
        for capacity in entry.candidate.capacity:
            if capacity.kind == kind:
                total += capacity.quantity_base
        return total

    def _active_admission_count(self, service_ref: str) -> int:
        return sum(
            1
            for entry in self._admissions.values()
            if entry.admission.service_ref == service_ref
            and entry.admission.state == AdmissionState.ACTIVE
        )

    def _available_capacity(self, kind: str, *, now: str) -> int:
        declared = sum(
            self._declared_capacity(service_ref, kind, now=now)
            for service_ref in self._services
        )
        reserved = sum(
            entry.allocation.quantity_base
            for entry in self._allocations.values()
            if entry.allocation.kind == kind
            and entry.allocation.state == AllocationState.RESERVED
        )
        return declared - reserved

    # ------------------------------------------------------------------ #
    # Execution providers
    # ------------------------------------------------------------------ #

    def register_execution_provider(
        self,
        implementation: ExecutionProviderContract,
        *,
        label: str,
        make_default: bool = False,
        now: str,
    ) -> ServiceOpResult:
        """Register (and open) an execution provider behind the
        sandbox.  The label is diagnostic only and never enters
        canonical state."""
        self._require_not_closed()
        self._require_now(now)
        if not isinstance(implementation, ExecutionProviderContract):
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "implementation must implement the "
                "ExecutionProviderContract ABC (isinstance-enforced)",
            )
        if not isinstance(label, str) or not label:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "provider label must be a non-empty str",
            )
        reject_credential_like_text(label, label="provider label")
        sandbox = SandboxedExecutionProvider(
            implementation,
            integration_id=self._integration_id,
            step_budget=self._step_budget,
            session_reader=self._session_reader,
        )
        opened = sandbox.open(now=now)
        if not opened.ok:
            return opened
        probed = sandbox.health(now=now)
        if not probed.ok:
            return probed
        if probed.value == "NOT_RUNNING":
            return ServiceOpResult(
                ok=False,
                failure=ServiceFailure(
                    reason_code=ServiceReasonCode.CONTRACT_VIOLATION,
                    integration_id=self._integration_id,
                    operation="register_execution_provider",
                ),
                detail="provider reported NOT_RUNNING after open",
            )
        registration = _ProviderRegistration(label, sandbox)
        self._providers.append(registration)
        if make_default or self._default_sandbox is None:
            self._default_sandbox = sandbox
        self._append_event(ServiceEventType.PROVIDER_REGISTERED, now)
        return ServiceOpResult(ok=True, value=sandbox)

    def _require_default(self) -> SandboxedExecutionProvider:
        if self._default_sandbox is None:
            raise ServiceError(
                ServiceReasonCode.SERVICE_UNAVAILABLE,
                "no execution provider is registered (fail closed)",
            )
        return self._default_sandbox

    def computed_health(self) -> str:
        if self._default_sandbox is None:
            return "NOT_RUNNING"
        return self._default_sandbox.computed_health()

    def health(self, *, now: str) -> ServiceOpResult:
        self._require_not_closed()
        self._require_now(now)
        return self._require_default().health(now=now)

    def capabilities(self) -> Tuple[str, ...]:
        caps: List[str] = []
        if self._default_sandbox is not None:
            caps.append("capability.profile.service.edge-execution")
        caps.append("capability.profile.service.registry")
        caps.append("capability.profile.service.local-first-discovery")
        if self._federation_reader is not None:
            caps.append("capability.profile.service.federation-exposure")
        return tuple(caps)

    # ------------------------------------------------------------------ #
    # Advertisement lifecycle
    # ------------------------------------------------------------------ #

    def register_service(
        self,
        *,
        now: str,
        label: Optional[str] = None,
        advertisement: ServiceAdvertisement,
        evidence: AdvertisementEvidence,
    ) -> ServiceOpResult:
        """Register (or idempotently re-register) a service
        advertisement.

        Evidence discipline (fail closed, BEFORE any state change):
        the evidence must be a genuine ``AdvertisementEvidence`` whose
        claim digest binds the WHOLE advertisement claim.  Remote-claim
        evidence imports a federation-scoped peer record; the peer
        claim must carry the relationship it arrived on and be
        federated-visible.  A re-registration of the same claim is
        repeat-safe (no state change); a conflicting claim fails with
        SERVICE_CONFLICT (deterministic conflict behavior); host
        changes must use :meth:`relocate_service` (never a silent
        host mutation).
        """
        self._require_not_closed()
        self._require_now(now)
        if not isinstance(advertisement, ServiceAdvertisement):
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "advertisement must be a ServiceAdvertisement (got %s)"
                % (type(advertisement).__name__,),
            )
        if not isinstance(evidence, AdvertisementEvidence):
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "evidence must be an AdvertisementEvidence (got %s)"
                % (type(evidence).__name__,),
            )
        claim_digest = derive_advertisement_claim_digest(advertisement)
        if evidence.claim_digest != claim_digest:
            raise ServiceError(
                ServiceReasonCode.ADVERTISEMENT_UNEVIDENCED,
                "advertisement evidence does not bind to the "
                "advertisement claim (unevidenced or tampered claim "
                "rejected)",
            )
        if evidence.source_class == EvidenceSourceClass.REMOTE_CLAIM:
            if not advertisement.federation_relationship_id:
                raise ServiceError(
                    ServiceReasonCode.INVALID_INPUT,
                    "a peer-imported claim must carry the federation "
                    "relationship it arrived on",
                )
            if advertisement.visibility != VisibilityScope.FEDERATED:
                raise ServiceError(
                    ServiceReasonCode.INVALID_INPUT,
                    "a peer-imported claim must be federated-visible",
                )
        else:
            if advertisement.federation_relationship_id:
                raise ServiceError(
                    ServiceReasonCode.INVALID_INPUT,
                    "a locally observed advertisement must not carry a "
                    "federation relationship id",
                )
        service_ref = advertisement.service_ref
        validate_opaque_ref(service_ref, "service")
        # Tombstone replay protection: a withdrawn record can only be
        # re-registered by a STRICTLY later advertisement.
        for tombstone in self._tombstones:
            if tombstone.service_ref != service_ref:
                continue
            if advertisement.registered_at <= tombstone.withdrawn_at:
                raise ServiceError(
                    ServiceReasonCode.ADVERTISEMENT_REPLAY,
                    "advertisement for %r is a replay of the withdrawn "
                    "record (registered_at %s is not after the tombstone "
                    "instant %s)" % (
                        service_ref, advertisement.registered_at,
                        tombstone.withdrawn_at,
                    ),
                )
        existing = self._services.get(service_ref)
        if existing is not None:
            if existing.claim_digest == claim_digest:
                # Repeat-safe registration: identical claim, no state
                # change, no duplicate record.
                return ServiceOpResult(ok=True, value=service_ref)
            if existing.candidate.host_node_id != advertisement.host_node_id:
                raise ServiceError(
                    ServiceReasonCode.SERVICE_CONFLICT,
                    "advertisement host differs from the registered "
                    "record; placement changes must use relocate_service "
                    "(never a silent host mutation)",
                )
            candidate = _candidate_from(advertisement, evidence)
            self._services[service_ref] = _ServiceEntry(candidate, claim_digest)
            event_type = (
                ServiceEventType.PEER_SERVICE_REGISTERED
                if evidence.source_class == EvidenceSourceClass.REMOTE_CLAIM
                else ServiceEventType.SERVICE_UPDATED
            )
            self._append_event(event_type, now, service_ref=service_ref)
            return ServiceOpResult(ok=True, value=service_ref)
        candidate = _candidate_from(advertisement, evidence)
        self._services[service_ref] = _ServiceEntry(candidate, claim_digest)
        event_type = (
            ServiceEventType.PEER_SERVICE_REGISTERED
            if evidence.source_class == EvidenceSourceClass.REMOTE_CLAIM
            else ServiceEventType.SERVICE_REGISTERED
        )
        self._append_event(event_type, now, service_ref=service_ref)
        return ServiceOpResult(ok=True, value=service_ref)

    def withdraw_service(
        self, *, now: str, service_ref: str, reason: str = ""
    ) -> ServiceOpResult:
        """Withdraw a service: the record is tombstoned (explicit,
        ordered, replay protecting), active admissions are superseded,
        and standing decisions stop being current.  Local service
        state is never erased by anything but this explicit owner
        operation."""
        self._require_not_closed()
        self._require_now(now)
        validate_opaque_ref(service_ref, "service")
        reject_credential_like_text(reason, label="withdrawal reason")
        entry = self._services.pop(service_ref, None)
        if entry is None:
            if any(t.service_ref == service_ref for t in self._tombstones):
                raise ServiceError(
                    ServiceReasonCode.SERVICE_WITHDRAWN,
                    "service %r is already withdrawn" % (service_ref,),
                )
            raise ServiceError(
                ServiceReasonCode.SERVICE_UNKNOWN,
                "service %r is not registered" % (service_ref,),
            )
        # Supersede active admissions (best-effort provider release,
        # exactly the WORK-024 post-commit discipline).
        for admission_ref in sorted(self._admissions):
            adm_entry = self._admissions[admission_ref]
            if adm_entry.admission.service_ref != service_ref:
                continue
            if adm_entry.admission.state != AdmissionState.ACTIVE:
                continue
            superseded = _replace_admission_state(
                adm_entry.admission, AdmissionState.SUPERSEDED
            )
            adm_entry.admission = superseded
            self._append_event(
                ServiceEventType.ADMISSION_SUPERSEDED, now,
                service_ref=service_ref, admission_ref=admission_ref,
            )
            try:
                adm_entry.sandbox.release(now=now, admission_ref=admission_ref)
            except BaseException:  # noqa: BLE001
                pass
        self._tombstones.append(
            ServiceTombstone(
                service_ref=service_ref, withdrawn_at=now, reason=reason
            )
        )
        self._append_event(
            ServiceEventType.SERVICE_WITHDRAWN, now, service_ref=service_ref
        )
        return ServiceOpResult(ok=True, value=service_ref)

    def relocate_service(
        self,
        *,
        now: str,
        service_ref: str,
        target_host_node_id: str,
        target_endpoint_ref: str = "",
    ) -> ServiceOpResult:
        """Relocate a service to a new hosting node.

        Semantics (WORK-025 'Service placement and relocation'): the
        ServiceID stays stable, the host changes, the transition is
        recorded (auditable), active admissions are superseded, and
        standing decisions stop being current -- authorization is
        re-evaluated under current policy (a new invocation decision
        is required after the transition)."""
        self._require_not_closed()
        self._require_now(now)
        validate_opaque_ref(service_ref, "service")
        validate_node_id(target_host_node_id, label="target host node id")
        entry = self._services.get(service_ref)
        if entry is None:
            raise ServiceError(
                ServiceReasonCode.SERVICE_UNKNOWN,
                "service %r is not registered" % (service_ref,),
            )
        if not self._record_is_fresh(entry.candidate, now):
            raise ServiceError(
                ServiceReasonCode.SERVICE_STALE,
                "service %r advertisement is stale; refresh it before "
                "relocating" % (service_ref,),
            )
        if entry.candidate.host_node_id == target_host_node_id:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "service %r is already hosted by the target node"
                % (service_ref,),
            )
        transition = PlacementTransition(
            service_ref=service_ref,
            from_host_node_id=entry.candidate.host_node_id,
            to_host_node_id=target_host_node_id,
            transitioned_at=now,
            endpoint_ref=target_endpoint_ref,
        )
        candidate = _replace_candidate_host(
            entry.candidate, target_host_node_id, target_endpoint_ref
        )
        entry.candidate = candidate
        self._placements.append(transition)
        # Supersede active admissions (best-effort provider release).
        for admission_ref in sorted(self._admissions):
            adm_entry = self._admissions[admission_ref]
            if adm_entry.admission.service_ref != service_ref:
                continue
            if adm_entry.admission.state != AdmissionState.ACTIVE:
                continue
            superseded = _replace_admission_state(
                adm_entry.admission, AdmissionState.SUPERSEDED
            )
            adm_entry.admission = superseded
            self._append_event(
                ServiceEventType.ADMISSION_SUPERSEDED, now,
                service_ref=service_ref, admission_ref=admission_ref,
            )
            try:
                adm_entry.sandbox.release(now=now, admission_ref=admission_ref)
            except BaseException:  # noqa: BLE001
                pass
        self._append_event(
            ServiceEventType.SERVICE_RELOCATED, now, service_ref=service_ref
        )
        return ServiceOpResult(ok=True, value=service_ref)

    # ------------------------------------------------------------------ #
    # Lookup and discovery
    # ------------------------------------------------------------------ #

    def lookup_service(
        self,
        *,
        now: str,
        service_ref: str,
        tenant_domain: str,
        session_id: str = "",
        caller_node_id: str = "",
        decision_ref: str = "",
        include_federated: bool = False,
    ) -> ServiceCandidate:
        """Look up one service, distinguishing every frozen discovery
        state: unknown / withdrawn / stale / hidden (peer claim not
        federated) / tenant-isolated / unauthorized / eligible.

        Tenant scope is REQUIRED and fail-closed (PR #26 review,
        blocker 1): every queryable service record belongs to exactly
        one tenant, so a caller must always state its tenant scope --
        omitting it is a structural TypeError and an empty scope
        fails closed with TENANT_ISOLATION.  There is no unscoped
        query path.

        A policy-controlled service requires a CURRENT invocation
        decision: a discovered service is never implicitly authorized
        merely because it was advertised."""
        self._require_not_closed()
        self._require_now(now)
        validate_opaque_ref(service_ref, "service")
        if not isinstance(tenant_domain, str) or not tenant_domain:
            raise ServiceError(
                ServiceReasonCode.TENANT_ISOLATION,
                "tenant scope is required and fail-closed: an empty or "
                "omitted tenant_domain can never observe another "
                "tenant's service records (WORK-025 invariant 12)",
            )
        validate_tenant_domain(tenant_domain)
        if session_id:
            validate_session_ref(session_id)
        if caller_node_id:
            validate_node_id(caller_node_id, label="caller node id")
        if decision_ref:
            validate_opaque_ref(decision_ref, "decision")
        candidate = self._require_service_record(service_ref, now)
        if (
            candidate.source_class == EvidenceSourceClass.REMOTE_CLAIM
            and not include_federated
        ):
            raise ServiceError(
                ServiceReasonCode.VISIBILITY_HIDDEN,
                "service %r is a peer claim visible only through "
                "federated discovery" % (service_ref,),
            )
        if candidate.tenant_domain != tenant_domain:
            raise ServiceError(
                ServiceReasonCode.TENANT_ISOLATION,
                "service %r belongs to tenant %r; tenant/domain "
                "boundaries are explicit (no cross-boundary lookup "
                "without a federation path)" % (
                    service_ref, candidate.tenant_domain,
                ),
            )
        if candidate.policy_controlled:
            if not decision_ref:
                raise ServiceError(
                    ServiceReasonCode.DECISION_DENIED,
                    "service %r is policy-controlled: an authorization "
                    "decision is required (a discovered service is never "
                    "implicitly authorized to execute)" % (service_ref,),
                )
            decision = self._decisions.get(decision_ref)
            if decision is None:
                raise ServiceError(
                    ServiceReasonCode.DECISION_UNKNOWN,
                    "invocation decision %r is unknown" % (decision_ref,),
                )
            if (
                decision.service_ref != service_ref
                or decision.session_id != session_id
                or decision.caller_node_id != caller_node_id
            ):
                raise ServiceError(
                    ServiceReasonCode.DECISION_SCOPE_MISMATCH,
                    "invocation decision %r was issued for another "
                    "service/caller/session scope" % (decision_ref,),
                )
            if not self._decision_is_current(decision):
                raise ServiceError(
                    ServiceReasonCode.REAUTHORIZATION_REQUIRED,
                    "invocation decision %r is no longer current (a newer "
                    "decision or a placement transition requires "
                    "re-authorization under current policy)" % (decision_ref,),
                )
        return candidate

    def _intent_label_constraint_allows(
        self, record: ServiceCandidate, constraint: Any
    ) -> bool:
        value = constraint.value
        if not isinstance(value, str):
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "label-dimension constraint values must be strings "
                "(got %s)" % (type(value).__name__,),
            )
        if constraint.operator not in ("=", "!="):
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "label-dimension operator %r is not service-layer "
                "semantics (only = / != are evaluated against declared "
                "service DATA; ordering is connectivity semantics)"
                % (constraint.operator,),
            )
        if constraint.dimension == "locality":
            member = value in record.locality_labels
        elif constraint.dimension == "service":
            member = value in record.service_labels
        else:
            member = value in record.privacy_labels
        return member if constraint.operator == "=" else not member

    def _intent_allows(self, record: ServiceCandidate, intent: Any) -> bool:
        """Deterministic compatibility filtering against DECLARED
        service DATA (label dimensions only).  Numeric dimensions
        (latency, bandwidth, ...) are connectivity concerns delegated
        to the WORK-011/W024 composition: the service layer neither
        scores nor filters them.  Soft preferences never filter
        (selection remains the caller's)."""
        for constraint in intent.requirements:
            if constraint.dimension in _LABEL_DIMENSIONS:
                if not self._intent_label_constraint_allows(record, constraint):
                    return False
        for constraint in intent.privacy_requirements:
            if constraint.dimension in _LABEL_DIMENSIONS:
                if not self._intent_label_constraint_allows(record, constraint):
                    return False
        for constraint in intent.service_constraints:
            if constraint.dimension in _LABEL_DIMENSIONS:
                if not self._intent_label_constraint_allows(record, constraint):
                    return False
        return True

    def _federation_relationship_allowed(
        self, relationship_id: str, now: str
    ) -> bool:
        """Federated visibility is scoped: the read-only WORK-015
        projection must authorize ``service.discover`` for the
        relationship at the injected instant.  No reader or no
        upstream -> fail closed (excluded), never a crash."""
        if not self._upstream_available:
            return False
        if self._federation_reader is None:
            return False
        try:
            allowed, _code = self._federation_reader.check_scope(
                relationship_id, SERVICE_DISCOVER_SCOPE, evaluation_instant=now
            )
        except BaseException:  # noqa: BLE001
            return False
        return bool(allowed)

    def discover_services(
        self,
        *,
        now: str,
        tenant_domain: str,
        host_node_id: str = "",
        intent: Any = None,
        capability_ref: str = "",
        include_federated: bool = False,
        decision_refs: Tuple[str, ...] = (),
    ) -> Tuple[ServiceCandidate, ...]:
        """Discover candidate service locations (local-first).

        The pipeline (the frozen WORK-025 discovery flow): validation
        + freshness -> policy / visibility filtering -> capability /
        intent compatibility -> candidate service locations ->
        caller/composition-root selection -> ordinary WORK-011 /
        WORK-024 connectivity.  This method NEVER computes, scores,
        or enumerates network routes.

        Tenant scope is REQUIRED and fail-closed (PR #26 review,
        blocker 1): discovery is always scoped to exactly one tenant
        domain -- omitting the scope is a structural TypeError and an
        empty scope fails closed with TENANT_ISOLATION.  There is no
        cross-tenant or unscoped enumeration path.

        Local-first selection: candidates hosted by the discovering
        node come first (each group sorted by service_ref).  Local
        discovery never requires upstream connectivity; federated
        (peer-claim) visibility requires it AND a currently
        scope-authorized relationship."""
        self._require_not_closed()
        self._require_now(now)
        if not isinstance(tenant_domain, str) or not tenant_domain:
            raise ServiceError(
                ServiceReasonCode.TENANT_ISOLATION,
                "tenant scope is required and fail-closed: an empty or "
                "omitted tenant_domain can never enumerate services "
                "across tenants (WORK-025 invariant 12)",
            )
        validate_tenant_domain(tenant_domain)
        if host_node_id:
            validate_node_id(host_node_id, label="host node id")
        if capability_ref:
            from .validation import validate_capability_ref as _vcr

            _vcr(capability_ref)
        if intent is not None and not isinstance(
            intent, _RealConnectivityIntent
        ):
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "intent must be a genuine intent.model.ConnectivityIntent "
                "(WORK-009 DATA; no second intent grammar)",
            )
        if not isinstance(decision_refs, tuple):
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "decision_refs must be a tuple of opaque decision refs",
            )
        for ref in decision_refs:
            validate_opaque_ref(ref, "decision")
        # Pre-validate label-dimension operators once (fail closed on
        # non-service-layer semantics before any filtering).
        if intent is not None:
            for bucket in (
                intent.requirements, intent.privacy_requirements,
                intent.service_constraints,
            ):
                for constraint in bucket:
                    if constraint.dimension in _LABEL_DIMENSIONS:
                        self._intent_label_constraint_allows(
                            _DUMMY_RECORD, constraint
                        )
        local: List[ServiceCandidate] = []
        remote: List[ServiceCandidate] = []
        for service_ref in sorted(self._services):
            entry = self._services[service_ref]
            record = entry.candidate
            if not self._record_is_fresh(record, now):
                continue
            if (
                record.source_class == EvidenceSourceClass.REMOTE_CLAIM
                and not include_federated
            ):
                continue
            if (
                record.source_class == EvidenceSourceClass.REMOTE_CLAIM
                and not self._federation_relationship_allowed(
                    record.federation_relationship_id, now
                )
            ):
                continue
            if record.tenant_domain != tenant_domain:
                continue
            if (
                record.visibility == VisibilityScope.LOCAL
                and host_node_id
                and record.host_node_id != host_node_id
            ):
                continue
            if capability_ref and capability_ref not in record.capability_refs:
                continue
            if intent is not None and not self._intent_allows(record, intent):
                continue
            if record.policy_controlled:
                authorized = False
                for ref in decision_refs:
                    decision = self._decisions.get(ref)
                    if decision is None:
                        continue
                    if decision.service_ref != service_ref:
                        continue
                    if self._decision_is_current(decision):
                        authorized = True
                        break
                if not authorized:
                    continue
            if host_node_id and record.host_node_id == host_node_id:
                local.append(record)
            else:
                remote.append(record)
        return tuple(local + remote)

    # ------------------------------------------------------------------ #
    # Policy
    # ------------------------------------------------------------------ #

    def apply_policy_decision(
        self,
        *,
        now: str,
        policy_decision: PolicyDecision,
    ) -> ServiceOpResult:
        """Apply a REAL WORK-010 policy decision as the invocation
        authorization for the scope THE DECISION ITSELF authorizes.

        Authority boundary (PR #26 review, blocker 2): this method
        accepts NO scope parameters.  The authorized (service,
        session, caller, tenant) scope is extracted from the
        decision's OWN ``extensions`` invocation binding, which is
        covered by the decision's content digest -- so a valid ALLOW
        can never be re-wrapped around a different authorization
        scope: rebinding the extension breaks the digest, and a
        decision without a binding fails closed.

        Verification (fail closed, the WORK-024 discipline plus the
        PR #26 binding discipline):
        isinstance a genuine ``policy.model.PolicyDecision``; the
        decision id MUST bind to the decision's own canonical bytes
        (tampered -- or rebound -- decision rejected); the decision
        MUST carry exactly one invocation binding for the frozen
        WORK-010 ``service.invoke`` operation; the effect MUST be
        ``allow`` (deny fails closed and never becomes
        authorization); the decision MUST NOT be future-dated (stale
        fails closed); the bound tenant MUST match the registered
        service record's tenant (cross-tenant authorization fails
        closed); and per-scope application instants MUST advance
        monotonically (re-applying the identical decision fails with
        DECISION_EXISTS; the exact same derived ref is never
        re-minted)."""
        self._require_not_closed()
        self._require_now(now)
        if not isinstance(policy_decision, PolicyDecision):
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "policy_decision must be a genuine policy.model."
                "PolicyDecision (WORK-010 authority; the service layer "
                "never evaluates policy)",
            )
        # Tamper evidence: the decision id MUST equal the digest of
        # the decision's own canonical bytes -- extensions included,
        # so the invocation binding below is digest-covered.
        expected_id = hashlib.sha256(
            policy_decision.canonical_bytes()
        ).hexdigest()
        if policy_decision.decision_id != expected_id:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "policy decision id does not bind to the decision's "
                "canonical bytes (tampered or rebound decision "
                "rejected)",
            )
        # The authorized scope comes from the decision itself --
        # never from separately supplied parameters.
        binding = extract_invocation_binding(policy_decision)
        service_ref = binding.service_ref
        session_id = binding.session_id
        caller_node_id = binding.caller_node_id
        tenant_domain = binding.tenant_domain
        # The authorized scope must reference THIS registry's state:
        # an unknown service cannot be authorized, and the bound
        # tenant must be the service record's tenant (fail closed --
        # a tenant-A authorization can never reach a tenant-B
        # service).
        candidate = self._require_service_record(service_ref, now)
        if candidate.tenant_domain != tenant_domain:
            raise ServiceError(
                ServiceReasonCode.TENANT_ISOLATION,
                "invocation decision binds tenant %r but service %r "
                "belongs to tenant %r (cross-tenant authorization "
                "fails closed)" % (
                    tenant_domain, service_ref, candidate.tenant_domain,
                ),
            )
        if policy_decision.effect != "allow":
            raise ServiceError(
                ServiceReasonCode.DECISION_DENIED,
                "policy DENIED the invocation -- deny never becomes "
                "service-layer authorization (fail closed)",
            )
        try:
            evaluated_at = parse_instant(policy_decision.evaluation_instant)
            applied_at = parse_instant(now)
        except TemporalError as exc:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "policy decision instant is not parseable: %s" % (exc,),
            )
        if evaluated_at > applied_at:
            raise ServiceError(
                ServiceReasonCode.DECISION_STALE,
                "policy decision is future-dated relative to the applied "
                "instant (stale decision fails closed)",
            )
        decision_ref = derive_decision_ref(
            service_ref, session_id, caller_node_id, tenant_domain,
            policy_decision.decision_id, now,
        )
        existing = self._decisions.get(decision_ref)
        if existing is not None:
            raise ServiceError(
                ServiceReasonCode.DECISION_EXISTS,
                "invocation decision %r was already applied (deterministic "
                "conflict behavior)" % (decision_ref,),
            )
        latest = self._latest_decision_for_scope(
            (service_ref, session_id, caller_node_id, tenant_domain)
        )
        if latest is not None and now <= latest.applied_instant:
            raise ServiceError(
                ServiceReasonCode.DECISION_STALE,
                "decision application instants must advance monotonically "
                "per scope (latest applied instant is %s)"
                % (latest.applied_instant,),
            )
        decision = InvocationDecision(
            decision_ref=decision_ref,
            service_ref=service_ref,
            session_id=session_id,
            caller_node_id=caller_node_id,
            tenant_domain=tenant_domain,
            policy_decision_id=policy_decision.decision_id,
            policy_effect=policy_decision.effect,
            matched_rule_ids=policy_decision.matched_rule_ids,
            applied_instant=now,
        )
        self._decisions[decision_ref] = decision
        self._append_event(
            ServiceEventType.DECISION_APPLIED, now, service_ref=service_ref
        )
        return ServiceOpResult(ok=True, value=decision_ref)

    def _require_secureable_session(self, session_id: str) -> None:
        """Fail closed without the session authority; require a
        secureable (ESTABLISHED/DEGRADED) session with it."""
        if not session_id:
            return
        if self._session_reader is None:
            raise ServiceError(
                ServiceReasonCode.SESSION_NOT_SECUREABLE,
                "no session authority was injected (fail closed)",
            )
        view = self._session_reader.lookup(session_id)
        if view is None or not view.secureable:
            raise ServiceError(
                ServiceReasonCode.SESSION_NOT_SECUREABLE,
                "session %r is not secureable (session authority remains "
                "WORK-012)" % (session_id,),
            )

    # ------------------------------------------------------------------ #
    # Execution (the edge seam)
    # ------------------------------------------------------------------ #

    def _validate_admit_execution(
        self,
        *,
        now: str,
        service_ref: str,
        decision_ref: str,
        session_id: str,
        caller_node_id: str,
        requirements: Any,
    ) -> ServiceCandidate:
        validate_opaque_ref(service_ref, "service")
        validate_opaque_ref(decision_ref, "decision")
        if session_id:
            validate_session_ref(session_id)
        if caller_node_id:
            validate_node_id(caller_node_id, label="caller node id")
        self._reject_identity_smuggling(requirements)
        candidate = self._require_service_record(service_ref, now)
        decision = self._decisions.get(decision_ref)
        if decision is None:
            raise ServiceError(
                ServiceReasonCode.DECISION_UNKNOWN,
                "invocation decision %r is unknown" % (decision_ref,),
            )
        if (
            decision.service_ref != service_ref
            or decision.session_id != session_id
            or decision.caller_node_id != caller_node_id
        ):
            raise ServiceError(
                ServiceReasonCode.DECISION_SCOPE_MISMATCH,
                "invocation decision %r was issued for another "
                "service/caller/session scope" % (decision_ref,),
            )
        # The decision's authorized tenant must still be the service
        # record's tenant (belt-and-braces: the service_ref structurally
        # fixes the tenant, so a mismatch means corrupted or rebound
        # state -- fail closed either way).
        if decision.tenant_domain != candidate.tenant_domain:
            raise ServiceError(
                ServiceReasonCode.TENANT_ISOLATION,
                "invocation decision %r authorizes tenant %r but "
                "service %r belongs to tenant %r (cross-tenant "
                "authorization fails closed)" % (
                    decision_ref, decision.tenant_domain,
                    service_ref, candidate.tenant_domain,
                ),
            )
        if not self._decision_is_current(decision):
            raise ServiceError(
                ServiceReasonCode.REAUTHORIZATION_REQUIRED,
                "invocation decision %r is no longer current "
                "(re-authorization under current policy is required)"
                % (decision_ref,),
            )
        self._require_secureable_session(session_id)
        # Capacity admission over WORK-008 DATA: an execution
        # admission consumes one base unit of edge-service-capacity
        # from the service's DECLARED capacity.  An advertisement is
        # an offer, not a reservation: a service that declares no
        # (or zero) edge-service-capacity contributes NO allocatable
        # capacity and admission fails closed (the WORK-022 lesson).
        declared = self._declared_capacity(
            service_ref, "edge-service-capacity", now=now
        )
        active = self._active_admission_count(service_ref)
        if declared - active < 1:
            raise ServiceError(
                ServiceReasonCode.CAPACITY_EXHAUSTED,
                "declared edge-service-capacity for %r is exhausted "
                "(declared %d, active admissions %d) -- advertisement is "
                "an offer, admission is the reservation"
                % (service_ref, declared, active),
            )
        return candidate

    def admit_execution(
        self,
        *,
        now: str,
        service_ref: str,
        decision_ref: str,
        session_id: str = "",
        caller_node_id: str = "",
        requirements: Any = None,
        label: Optional[str] = None,
    ) -> ServiceOpResult:
        """Admit one standing execution (the prepare/admit hook):
        authorization is verified BEFORE any provider-side effect, and
        the provider confirms externally before the registry commits
        the admission record (external-confirm-then-commit with
        compensation -- the WORK-024 failover discipline)."""
        self._require_not_closed()
        self._require_now(now)
        if label is not None:
            reject_credential_like_text(label, label="label")
        candidate = self._validate_admit_execution(
            now=now,
            service_ref=service_ref,
            decision_ref=decision_ref,
            session_id=session_id,
            caller_node_id=caller_node_id,
            requirements=requirements,
        )
        sandbox = self._require_default()
        result = sandbox.admit(
            now=now,
            service_ref=service_ref,
            host_node_id=candidate.host_node_id,
            tenant_domain=candidate.tenant_domain,
            session_id=session_id,
            decision_ref=decision_ref,
            requirements=requirements,
        )
        if not result.ok:
            return result
        admission = result.value
        if admission.service_ref != service_ref:
            return ServiceOpResult(
                ok=False,
                failure=ServiceFailure(
                    reason_code=ServiceReasonCode.CONTRACT_VIOLATION,
                    integration_id=self._integration_id,
                    operation="admit_execution",
                ),
                detail="provider admission binds a different service",
            )
        try:
            self._commit_admission(admission, sandbox, now=now)
        except BaseException:
            # Compensation: release the provider-side admission
            # best-effort, then re-raise (authoritative state was
            # never mutated).
            try:
                sandbox.release(now=now, admission_ref=admission.admission_ref)
            except BaseException:  # noqa: BLE001
                pass
            raise
        return ServiceOpResult(ok=True, value=admission)

    def _commit_admission(
        self,
        admission: ServiceAdmission,
        sandbox: SandboxedExecutionProvider,
        *,
        now: str,
    ) -> None:
        if admission.admission_ref in self._admissions:
            raise ServiceError(
                ServiceReasonCode.ILLEGAL_STATE,
                "admission ref collision -- derivation state is corrupt",
            )
        self._admissions[admission.admission_ref] = _AdmissionEntry(
            admission, sandbox
        )
        self._append_event(
            ServiceEventType.ADMISSION_ESTABLISHED, now,
            service_ref=admission.service_ref,
            admission_ref=admission.admission_ref,
        )

    def execute_request(
        self,
        *,
        now: str,
        admission_ref: str,
        request_payload: bytes,
        requirements: Any = None,
        label: Optional[str] = None,
    ) -> ServiceOpResult:
        """Execute one request under a standing admission (the
        execute hook).  Data-path: no canonical mutation, no events
        (the WORK-024 egress discipline); provider faults are
        returned as typed failure values."""
        self._require_not_closed()
        self._require_now(now)
        if label is not None:
            reject_credential_like_text(label, label="label")
        validate_opaque_ref(admission_ref, "admission")
        if not isinstance(request_payload, bytes):
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "request payload must be bytes (got %s)"
                % (type(request_payload).__name__,),
            )
        if not request_payload:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "request payload must be non-empty",
            )
        if len(request_payload) > MAX_REQUEST_BYTES:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "request payload exceeds %d bytes" % (MAX_REQUEST_BYTES,),
            )
        self._reject_identity_smuggling(requirements)
        entry = self._admissions.get(admission_ref)
        if entry is None:
            raise ServiceError(
                ServiceReasonCode.ADMISSION_UNKNOWN,
                "admission %r is unknown" % (admission_ref,),
            )
        if entry.admission.state != AdmissionState.ACTIVE:
            raise ServiceError(
                ServiceReasonCode.ADMISSION_STATE,
                "admission %r is %r, not active" % (
                    admission_ref, entry.admission.state,
                ),
            )
        # The service record must still be fresh and the session still
        # secureable at execution time ("known but unavailable at
        # execution time" fails closed).
        self._require_service_record(entry.admission.service_ref, now)
        self._require_secureable_session(entry.admission.session_id)
        result = entry.sandbox.execute(
            now=now,
            admission_ref=admission_ref,
            request_payload=request_payload,
            requirements=requirements,
        )
        if result.ok:
            self._executed_total += 1
        else:
            self._execution_failures += 1
        return result

    def release_execution(
        self,
        *,
        now: str,
        admission_ref: str,
        label: Optional[str] = None,
    ) -> ServiceOpResult:
        """Release a standing admission (the cancel/release hook):
        external confirm (provider release) then registry commit."""
        self._require_not_closed()
        self._require_now(now)
        if label is not None:
            reject_credential_like_text(label, label="label")
        validate_opaque_ref(admission_ref, "admission")
        entry = self._admissions.get(admission_ref)
        if entry is None:
            raise ServiceError(
                ServiceReasonCode.ADMISSION_UNKNOWN,
                "admission %r is unknown" % (admission_ref,),
            )
        if entry.admission.state != AdmissionState.ACTIVE:
            raise ServiceError(
                ServiceReasonCode.ADMISSION_STATE,
                "admission %r is %r, not active" % (
                    admission_ref, entry.admission.state,
                ),
            )
        result = entry.sandbox.release(now=now, admission_ref=admission_ref)
        if not result.ok:
            return result
        entry.admission = _replace_admission_state(
            entry.admission, AdmissionState.RELEASED
        )
        self._append_event(
            ServiceEventType.ADMISSION_RELEASED, now,
            service_ref=entry.admission.service_ref,
            admission_ref=admission_ref,
        )
        return ServiceOpResult(ok=True, value=admission_ref)

    # ------------------------------------------------------------------ #
    # Capacity allocation (the explicit resource-admission path)
    # ------------------------------------------------------------------ #

    def _validate_allocate(
        self, *, kind: str, quantity_base: int, purpose: str, now: str
    ) -> Tuple[CapacityAllocation, int]:
        validate_capacity_kind(kind)
        validate_capacity_quantity(quantity_base)
        if quantity_base < 1:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "allocation quantity must be at least 1 base unit",
            )
        if not isinstance(purpose, str) or not purpose:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "allocation purpose must be a non-empty str",
            )
        reject_credential_like_text(purpose, label="allocation purpose")
        available = self._available_capacity(kind, now=now)
        if quantity_base > available:
            raise ServiceError(
                ServiceReasonCode.CAPACITY_EXHAUSTED,
                "declared %s capacity is exhausted (available %d base "
                "units, requested %d) -- capacity exhaustion fails closed "
                "and leaves authoritative state unchanged"
                % (kind, available, quantity_base),
            )
        # Derive from a CANDIDATE sequence: the nonce advances only
        # in the commit phase (the PR #24 architectural-review
        # discipline).
        candidate_sequence = self._sequence + 1
        allocation_ref = derive_allocation_ref(
            kind, quantity_base, purpose, candidate_sequence
        )
        allocation = CapacityAllocation(
            allocation_ref=allocation_ref,
            kind=kind,
            quantity_base=quantity_base,
            purpose=purpose,
            state=AllocationState.RESERVED,
        )
        return allocation, candidate_sequence

    def _commit_allocate(
        self, allocation: CapacityAllocation, candidate_sequence: int
    ) -> None:
        if allocation.allocation_ref in self._allocations:
            raise ServiceError(
                ServiceReasonCode.ILLEGAL_STATE,
                "allocation ref collision -- derivation state is corrupt",
            )
        # The sequence advances ONLY here, in the commit phase.
        self._sequence = candidate_sequence
        self._allocations[allocation.allocation_ref] = _AllocationEntry(
            allocation
        )

    def allocate(
        self,
        *,
        now: str,
        kind: str,
        quantity_base: int,
        purpose: str,
        label: Optional[str] = None,
    ) -> ServiceOpResult:
        """Reserve declared service capacity explicitly (WORK-008
        DATA kinds and base units; the advertisement is the offer,
        this is the reservation)."""
        self._require_not_closed()
        self._require_now(now)
        if label is not None:
            reject_credential_like_text(label, label="label")
        allocation, candidate_sequence = self._validate_allocate(
            kind=kind, quantity_base=quantity_base, purpose=purpose, now=now
        )
        self._commit_allocate(allocation, candidate_sequence)
        self._append_event(
            ServiceEventType.ALLOCATION_RESERVED, now,
            detail="kind=%s quantity=%d" % (kind, quantity_base),
        )
        return ServiceOpResult(ok=True, value=allocation.allocation_ref)

    def release(
        self,
        *,
        now: str,
        allocation_ref: str,
        label: Optional[str] = None,
    ) -> ServiceOpResult:
        self._require_not_closed()
        self._require_now(now)
        if label is not None:
            reject_credential_like_text(label, label="label")
        validate_opaque_ref(allocation_ref, "allocation")
        entry = self._allocations.get(allocation_ref)
        if entry is None:
            raise ServiceError(
                ServiceReasonCode.ALLOCATION_UNKNOWN,
                "allocation %r is unknown" % (allocation_ref,),
            )
        if entry.allocation.state != AllocationState.RESERVED:
            raise ServiceError(
                ServiceReasonCode.ILLEGAL_STATE,
                "allocation %r is already %r" % (
                    allocation_ref, entry.allocation.state,
                ),
            )
        entry.allocation = CapacityAllocation(
            allocation_ref=entry.allocation.allocation_ref,
            kind=entry.allocation.kind,
            quantity_base=entry.allocation.quantity_base,
            purpose=entry.allocation.purpose,
            state=AllocationState.RELEASED,
        )
        self._append_event(ServiceEventType.ALLOCATION_RELEASED, now)
        return ServiceOpResult(ok=True, value=allocation_ref)

    # ------------------------------------------------------------------ #
    # Federation exposure
    # ------------------------------------------------------------------ #

    def apply_federation_exposure(
        self,
        *,
        now: str,
        service_ref: str,
        relationship_id: str,
        scope: str = SERVICE_DISCOVER_SCOPE,
    ) -> ServiceOpResult:
        """Expose one local service to one federation relationship
        under one frozen scope.  The read-only WORK-015 projection
        must authorize the scope for the relationship at the injected
        instant (federation authority remains WORK-015; the service
        layer carries the result as DATA).  Re-application is
        idempotent (same exposure identity -> no state change)."""
        self._require_not_closed()
        self._require_now(now)
        validate_opaque_ref(service_ref, "service")
        validate_federation_scope(scope)
        from .validation import validate_federation_ref as _vfr

        _vfr(relationship_id, label="relationship id")
        entry = self._services.get(service_ref)
        if entry is None:
            raise ServiceError(
                ServiceReasonCode.SERVICE_UNKNOWN,
                "service %r is not registered" % (service_ref,),
            )
        if entry.candidate.visibility != VisibilityScope.FEDERATED:
            raise ServiceError(
                ServiceReasonCode.VISIBILITY_HIDDEN,
                "service %r visibility %r does not permit federation "
                "exposure (exposure requires federated visibility)"
                % (service_ref, entry.candidate.visibility),
            )
        if entry.candidate.source_class != EvidenceSourceClass.DIRECT_OBSERVATION:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "only locally observed services may be exposed (a peer "
                "claim is not re-exported)",
            )
        if self._federation_reader is None:
            raise ServiceError(
                ServiceReasonCode.FEDERATION_SCOPE_DENIED,
                "no federation authority was injected (fail closed -- "
                "membership in a federation never implies service trust)",
            )
        try:
            allowed, code = self._federation_reader.check_scope(
                relationship_id, scope, evaluation_instant=now
            )
        except BaseException as exc:  # noqa: BLE001
            raise ServiceError(
                ServiceReasonCode.FEDERATION_SCOPE_DENIED,
                "federation authority fault isolated (class %s)"
                % (type(exc).__name__,),
            )
        if not allowed:
            raise ServiceError(
                ServiceReasonCode.FEDERATION_SCOPE_DENIED,
                "federation authority denied scope %r for the "
                "relationship (%s)" % (scope, code),
            )
        exposure_ref = derive_exposure_ref(service_ref, relationship_id, scope)
        existing = self._exposures.get(exposure_ref)
        if existing is not None:
            return ServiceOpResult(ok=True, value=exposure_ref)
        self._exposures[exposure_ref] = FederationExposure(
            exposure_ref=exposure_ref,
            service_ref=service_ref,
            relationship_id=relationship_id,
            scope=scope,
            exposed_at=now,
        )
        self._append_event(
            ServiceEventType.EXPOSURE_APPLIED, now, service_ref=service_ref
        )
        return ServiceOpResult(ok=True, value=exposure_ref)

    def remove_federation_exposure(
        self,
        *,
        now: str,
        service_ref: str,
        relationship_id: str,
        scope: str = SERVICE_DISCOVER_SCOPE,
    ) -> ServiceOpResult:
        """Remove one federation exposure.  The LOCAL SERVICE RECORD
        IS NEVER DELETED (WORK-025 invariant: removing federation
        exposure preserves local service state)."""
        self._require_not_closed()
        self._require_now(now)
        validate_opaque_ref(service_ref, "service")
        validate_federation_scope(scope)
        from .validation import validate_federation_ref as _vfr

        _vfr(relationship_id, label="relationship id")
        exposure_ref = derive_exposure_ref(service_ref, relationship_id, scope)
        removed = self._exposures.pop(exposure_ref, None)
        if removed is None:
            raise ServiceError(
                ServiceReasonCode.FEDERATION_UNKNOWN,
                "federation exposure for %r under the relationship is "
                "not active" % (service_ref,),
            )
        self._append_event(
            ServiceEventType.EXPOSURE_REMOVED, now, service_ref=service_ref
        )
        return ServiceOpResult(ok=True, value=exposure_ref)

    # ------------------------------------------------------------------ #
    # Observation and canonical state
    # ------------------------------------------------------------------ #

    def observe(
        self, *, now: str, label: Optional[str] = None
    ) -> ServiceObservation:
        """Honest observation at the injected instant.  An upstream
        outage is REPORTED (upstream_available=0) without ever being
        declared remote-service-loss-as-local-corruption: local
        records stay registered and locally discoverable regardless
        of upstream state (LOCK-012)."""
        self._require_not_closed()
        self._require_now(now)
        if label is not None:
            reject_credential_like_text(label, label="label")
        registered = len(self._services)
        available = sum(
            1
            for entry in self._services.values()
            if self._record_is_fresh(entry.candidate, now)
        )
        expired = registered - available
        active = self._active_admission_count_all()
        return ServiceObservation(
            samples=(
                (ServiceMetricName.REGISTERED_SERVICES, registered),
                (ServiceMetricName.AVAILABLE_SERVICES, available),
                (ServiceMetricName.WITHDRAWN_SERVICES, len(self._tombstones)),
                (ServiceMetricName.EXPIRED_SERVICES, expired),
                (ServiceMetricName.FEDERATED_EXPOSURES, len(self._exposures)),
                (ServiceMetricName.ACTIVE_ADMISSIONS, active),
                (ServiceMetricName.EXECUTED_REQUESTS, self._executed_total),
                (ServiceMetricName.FAILED_REQUESTS, self._execution_failures),
            ),
            registered_services=registered,
            available_services=available,
            withdrawn_services=len(self._tombstones),
            expired_services=expired,
            federated_exposures=len(self._exposures),
            active_admissions=active,
            executed_requests=self._executed_total,
            failed_requests=self._execution_failures,
            upstream_available=1 if self._upstream_available else 0,
        )

    def _active_admission_count_all(self) -> int:
        return sum(
            1
            for entry in self._admissions.values()
            if entry.admission.state == AdmissionState.ACTIVE
        )

    def set_upstream_state(self, *, available: bool) -> None:
        """Reference-model control (NOT canonical): upstream
        connectivity availability for federated discovery.  Strict
        toggling (re-applying the current state raises ILLEGAL_STATE),
        mirroring the WORK-024 ``set_gateway_state`` discipline.  The
        upstream outage never erases or corrupts local service
        state."""
        if isinstance(available, bool) is False:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "available must be a bool",
            )
        if available == self._upstream_available:
            raise ServiceError(
                ServiceReasonCode.ILLEGAL_STATE,
                "upstream availability is already %r" % (available,),
            )
        self._upstream_available = available

    def snapshot(self) -> dict:
        """ACCESS-STATE-IN canonical snapshot: authoritative service
        facts only.  Provider labels, sandboxes, health ladders,
        upstream reference state, step budgets, execution counters,
        and derivation nonces are ACCESS-STATE-OUT (never
        canonical)."""
        return {
            "integration_id": self._integration_id,
            "closed": self._closed,
            "registered_count": len(self._services),
            "admission_count": self._active_admission_count_all(),
            "services": [
                self._services[service_ref].candidate.to_dict()
                for service_ref in sorted(self._services)
            ],
            "tombstones": [t.to_dict() for t in self._tombstones],
            "placements": [p.to_dict() for p in self._placements],
            "decisions": [
                self._decisions[decision_ref].to_dict()
                for decision_ref in sorted(self._decisions)
            ],
            "exposures": [
                self._exposures[exposure_ref].to_dict()
                for exposure_ref in sorted(self._exposures)
            ],
            "admissions": [
                self._admissions[admission_ref].admission.to_dict()
                for admission_ref in sorted(self._admissions)
            ],
            "allocations": [
                self._allocations[allocation_ref].allocation.to_dict()
                for allocation_ref in sorted(self._allocations)
            ],
            "events": [event.to_dict() for event in self._events],
        }

    def to_canonical_bytes(self) -> bytes:
        return _bytes(self.snapshot())

    def content_digest(self) -> str:
        return hashlib.sha256(self.to_canonical_bytes()).hexdigest()

    def diagnostic_state(self) -> dict:
        return {
            "integration_id": self._integration_id,
            "closed": self._closed,
            "providers": [
                {"label": registration.label,
                 "health": registration.sandbox.computed_health()}
                for registration in self._providers
            ],
            "default_health": self.computed_health(),
            "upstream_available": self._upstream_available,
            "sequence": self._sequence,
            "executed_total": self._executed_total,
            "execution_failures": self._execution_failures,
        }

    def close(self) -> None:
        """Close the registry (best-effort provider close)."""
        self._require_not_closed()
        self._closed = True
        for registration in self._providers:
            try:
                registration.sandbox.close(now="1970-01-01T00:00:00Z")
            except BaseException:  # noqa: BLE001
                pass

    # ---- # properties --------------------------------------------------- #

    @property
    def integration_id(self) -> str:
        return self._integration_id

    @property
    def registered_count(self) -> int:
        return len(self._services)

    @property
    def closed(self) -> bool:
        return self._closed


# ---------------------------------------------------------------------- #
# Internal helpers
# ---------------------------------------------------------------------- #

def _candidate_from(
    advertisement: ServiceAdvertisement, evidence: AdvertisementEvidence
) -> ServiceCandidate:
    return ServiceCandidate(
        service_ref=advertisement.service_ref,
        name=advertisement.descriptor.name,
        service_kind=advertisement.descriptor.service_kind,
        tenant_domain=advertisement.descriptor.tenant_domain,
        host_node_id=advertisement.host_node_id,
        capability_refs=advertisement.descriptor.capability_refs,
        service_labels=advertisement.descriptor.service_labels,
        locality_labels=advertisement.descriptor.locality_labels,
        privacy_labels=advertisement.descriptor.privacy_labels,
        visibility=advertisement.visibility,
        registered_at=advertisement.registered_at,
        expires_at=advertisement.expires_at,
        endpoint_ref=advertisement.endpoint_ref,
        capacity=advertisement.capacity,
        state=ServiceLifecycle.REGISTERED,
        source_class=evidence.source_class,
        policy_controlled=advertisement.policy_controlled,
        federation_relationship_id=advertisement.federation_relationship_id,
    )


def _replace_admission_state(
    admission: ServiceAdmission, state: str
) -> ServiceAdmission:
    return ServiceAdmission(
        admission_ref=admission.admission_ref,
        service_ref=admission.service_ref,
        host_node_id=admission.host_node_id,
        tenant_domain=admission.tenant_domain,
        session_id=admission.session_id,
        decision_ref=admission.decision_ref,
        admitted_at=admission.admitted_at,
        state=state,
    )


def _replace_candidate_host(
    candidate: ServiceCandidate, host_node_id: str, endpoint_ref: str
) -> ServiceCandidate:
    return ServiceCandidate(
        service_ref=candidate.service_ref,
        name=candidate.name,
        service_kind=candidate.service_kind,
        tenant_domain=candidate.tenant_domain,
        host_node_id=host_node_id,
        capability_refs=candidate.capability_refs,
        service_labels=candidate.service_labels,
        locality_labels=candidate.locality_labels,
        privacy_labels=candidate.privacy_labels,
        visibility=candidate.visibility,
        registered_at=candidate.registered_at,
        expires_at=candidate.expires_at,
        endpoint_ref=endpoint_ref if endpoint_ref else candidate.endpoint_ref,
        capacity=candidate.capacity,
        state=candidate.state,
        source_class=candidate.source_class,
        policy_controlled=candidate.policy_controlled,
        federation_relationship_id=candidate.federation_relationship_id,
    )


#: A structurally valid dummy record used ONLY to pre-validate intent
#: label-constraint operators before filtering (the record is never
#: returned; the operator check is what runs).
_DUMMY_RECORD = ServiceCandidate(
    service_ref=derive_service_ref(
        "operator-precheck", "other", "operator-precheck-domain"
    ),
    name="operator-precheck",
    service_kind="other",
    tenant_domain="operator-precheck-domain",
    host_node_id="adcos:node:validation.dummy.v1:" + "0" * 64,
    capability_refs=(),
    service_labels=(),
    locality_labels=(),
    privacy_labels=(),
    visibility=VisibilityScope.TENANT,
    registered_at="1970-01-01T00:00:00Z",
    expires_at="9999-12-31T23:59:59Z",
)


__all__ = [
    "DEFAULT_INTEGRATION_ID",
    "ServiceRegistry",
    "ServiceOpResult",
    "SERVICE_CAPACITY_KINDS",
]
