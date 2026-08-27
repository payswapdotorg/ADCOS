"""ADCOS service registry / edge compute domain model (WORK-025).

Technology-neutral service concepts (mirrors the WORK-022/023/024
model discipline):

- ``ServiceRef`` -- opaque, content-derived service identity, STABLE
  under host/access-path changes.  Identity material is
  service-owned only: (name, service_kind, tenant_domain).  The
  hosting node, endpoint reference, declared capacity, labels, and
  visibility are deliberately EXCLUDED from identity so a service may
  move between edge nodes without becoming a different service
  identity when the service authority (the owning tenant domain)
  permits continuity (WORK-025 invariant 1).
- ``ServiceAdvertisement`` / ``AdvertisementEvidence`` -- registration
  is attributable DATA with explicit validity and provenance: the
  evidence claim digest binds the WHOLE advertisement claim, and a
  registered advertisement is never itself a capability claim, an
  availability fact, or a capacity reservation (WORK-025 invariants
  2, 8; the WORK-022 lesson).
- ``InvocationDecision`` -- a session/caller/service-scoped record of
  a REAL WORK-010 :class:`policy.model.PolicyDecision` that ALLOWED
  an invocation.  The service layer never evaluates policy and never
  invents trust (WORK-025 invariant 3).
- ``ServiceAdmission`` / ``CapacityAllocation`` -- explicit resource
  admission over WORK-008 capacity DATA (advertisement is an offer;
  admission is the reservation).
- ``ExecutionOutcome`` -- provider-neutral execution result with an
  explicit status and partial-failure detail.
- ``PlacementTransition`` / ``ServiceTombstone`` -- auditable
  lifecycle facts (placement changes are recorded, never silent).
- ``FederationExposure`` -- federation-scoped visibility DATA (the
  WORK-015 relationship reference and scope are carried as DATA; no
  federation trust state is imported).

Every dataclass re-validates its fields in ``__post_init__`` (frozen
workaround via ``object.__setattr__``) and the identity-carrying
records re-derive their refs (tamper-evident constructors: a tampered
or miscomputed ref is rejected at construction).  ``to_dict`` emits
only canonical-JSON primitives.

Determinism: all derivations are SHA-256 over
``protocol.canonicalization.canonical_json_bytes`` of nested identity
material; no randomness, no wall clock (instants are injected DATA),
no hash-seed-dependent iteration.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Tuple

from protocol.canonicalization import canonical_json_bytes

from .errors import ServiceError, ServiceReasonCode
from .validation import (
    assert_ref_session_separation,
    assert_service_node_separation,
    reject_credential_like_text,
    validate_capability_ref,
    validate_capacity_kind,
    validate_capacity_quantity,
    validate_claim_digest,
    validate_evidence_source,
    validate_endpoint_ref,
    validate_federation_ref,
    validate_instant,
    validate_label,
    validate_node_id,
    validate_opaque_ref,
    validate_policy_decision_id,
    validate_service_kind,
    validate_service_name,
    validate_session_ref,
    validate_tenant_domain,
    validate_visibility,
)

#: Maximum capacity quantity in base units (mirrors WORK-022/024).
MAX_CAPACITY_QUANTITY = 2 ** 40


# ---- # Frozen vocabularies --------------------------------------------- #

class ServiceKind:
    """Technology-neutral semantic service kinds (frozen)."""

    CACHE = "cache"
    COMPUTE = "compute"
    STORAGE = "storage"
    RELAY = "relay"
    ANALYTICS = "analytics"
    GATEWAY = "gateway"
    OTHER = "other"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.CACHE, cls.COMPUTE, cls.STORAGE, cls.RELAY,
            cls.ANALYTICS, cls.GATEWAY, cls.OTHER,
        )


class VisibilityScope:
    """Advertisement visibility scopes (frozen)."""

    LOCAL = "local"
    TENANT = "tenant"
    FEDERATED = "federated"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.LOCAL, cls.TENANT, cls.FEDERATED)


class ServiceLifecycle:
    """Service record lifecycle states (frozen).  ``REGISTERED`` is the
    active advertisement state; ``WITHDRAWN`` is an explicit
    tombstone; ``EXPIRED`` is a derived freshness lapse (a registered
    record whose ``expires_at`` has passed is reported stale at
    lookup/discovery time -- deterministically, given the injected
    instant)."""

    REGISTERED = "registered"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.REGISTERED, cls.WITHDRAWN, cls.EXPIRED)


class EvidenceSourceClass:
    """Advertisement evidence source classes (frozen; mirrors the
    WORK-024 gateway-evidence vocabulary -- a remote claim remains a
    claim until accepted under the appropriate authority/policy,
    LOCK-008)."""

    DIRECT_OBSERVATION = "direct-observation"
    REMOTE_CLAIM = "remote-claim"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.DIRECT_OBSERVATION, cls.REMOTE_CLAIM)


class AdmissionState:
    """Execution admission states (frozen)."""

    ACTIVE = "active"
    RELEASED = "released"
    SUPERSEDED = "superseded"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.ACTIVE, cls.RELEASED, cls.SUPERSEDED)


class AllocationState:
    """Capacity allocation states (frozen)."""

    RESERVED = "reserved"
    RELEASED = "released"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.RESERVED, cls.RELEASED)


class ExecutionStatus:
    """Execution outcome statuses (frozen; partial failures are
    explicit -- a completed run may still report ``failed`` with a
    detail)."""

    COMPLETED = "completed"
    FAILED = "failed"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.COMPLETED, cls.FAILED)


class ExposureState:
    """Federation exposure states (frozen)."""

    ACTIVE = "active"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.ACTIVE,)


class ServiceMetricName:
    """Frozen service-layer observation metric names (the registry /
    executor observation surface; not an adapter metric vocabulary --
    this is a core-module observation domain)."""

    REGISTERED_SERVICES = "registered-services"
    AVAILABLE_SERVICES = "available-services"
    WITHDRAWN_SERVICES = "withdrawn-services"
    EXPIRED_SERVICES = "expired-services"
    FEDERATED_EXPOSURES = "federated-exposures"
    ACTIVE_ADMISSIONS = "active-admissions"
    EXECUTED_REQUESTS = "executed-requests"
    FAILED_REQUESTS = "failed-requests"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.REGISTERED_SERVICES, cls.AVAILABLE_SERVICES,
            cls.WITHDRAWN_SERVICES, cls.EXPIRED_SERVICES,
            cls.FEDERATED_EXPOSURES, cls.ACTIVE_ADMISSIONS,
            cls.EXECUTED_REQUESTS, cls.FAILED_REQUESTS,
        )


class ServiceEventType:
    """Frozen registry event types (append-only audit; data-path
    execution requests append NO events, mirroring the WORK-024
    egress discipline)."""

    SERVICE_REGISTERED = "service-registered"
    SERVICE_UPDATED = "service-updated"
    SERVICE_WITHDRAWN = "service-withdrawn"
    SERVICE_RELOCATED = "service-relocated"
    PEER_SERVICE_REGISTERED = "peer-service-registered"
    DECISION_APPLIED = "decision-applied"
    EXPOSURE_APPLIED = "exposure-applied"
    EXPOSURE_REMOVED = "exposure-removed"
    PROVIDER_REGISTERED = "provider-registered"
    ADMISSION_ESTABLISHED = "admission-established"
    ADMISSION_RELEASED = "admission-released"
    ADMISSION_SUPERSEDED = "admission-superseded"
    ALLOCATION_RESERVED = "allocation-reserved"
    ALLOCATION_RELEASED = "allocation-released"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.SERVICE_REGISTERED, cls.SERVICE_UPDATED,
            cls.SERVICE_WITHDRAWN, cls.SERVICE_RELOCATED,
            cls.PEER_SERVICE_REGISTERED, cls.DECISION_APPLIED,
            cls.EXPOSURE_APPLIED, cls.EXPOSURE_REMOVED,
            cls.PROVIDER_REGISTERED, cls.ADMISSION_ESTABLISHED,
            cls.ADMISSION_RELEASED, cls.ADMISSION_SUPERSEDED,
            cls.ALLOCATION_RESERVED, cls.ALLOCATION_RELEASED,
        )


# ---- # Content-derived id derivation (deterministic; no randomness) ---- #

def _sha256_hex(material: dict) -> str:
    return hashlib.sha256(canonical_json_bytes(material)).hexdigest()


def derive_service_ref(
    name: str, service_kind: str, tenant_domain: str
) -> str:
    """Derive the opaque service identity ref from SERVICE-OWNED
    identity material only: (name, service_kind, tenant_domain).

    The hosting node, endpoint reference, declared capacity, labels,
    and visibility are deliberately excluded: a service hosted by
    node A may later be hosted by node B without becoming a different
    service identity (WORK-025 invariant 1)."""
    for scalar, label in (
        (name, "name"), (service_kind, "service_kind"),
        (tenant_domain, "tenant_domain"),
    ):
        if not isinstance(scalar, str) or not scalar:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "derive_service_ref %s must be a non-empty str" % (label,),
            )
    material = {
        "service": {
            "name": name,
            "service_kind": service_kind,
            "tenant_domain": tenant_domain,
        }
    }
    return "%s:service:%s" % (
        "services", _sha256_hex(material)[:32]
    )


def derive_advertisement_claim_digest(advertisement: "ServiceAdvertisement") -> str:
    """Derive the evidence claim digest binding the WHOLE advertisement
    claim (descriptor + hosting + validity + visibility + capacity).
    Advertisement evidence is attributable DATA (WORK-025 invariant 2)."""
    if not isinstance(advertisement, ServiceAdvertisement):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "derive_advertisement_claim_digest requires a "
            "ServiceAdvertisement (got %s)" % (type(advertisement).__name__,),
        )
    return _sha256_hex({"claim": advertisement.to_dict()})


def derive_decision_ref(
    service_ref: str,
    session_id: str,
    caller_node_id: str,
    tenant_domain: str,
    policy_decision_id: str,
    applied_instant: str,
) -> str:
    """Derive the invocation-decision ref, scoped by construction to
    (service, session, caller, tenant).  The tenant domain is derivation
    material (PR #26 review, blocker 1/2: tenant isolation is never
    optional on the authorization path); the WORK-010 policy decision
    id is a HASH INPUT only, never ref TEXT."""
    material = {
        "decision": {
            "service_ref": service_ref,
            "session_id": session_id,
            "caller_node_id": caller_node_id,
            "tenant_domain": tenant_domain,
            "policy_decision_id": policy_decision_id,
            "applied_instant": applied_instant,
        }
    }
    return "%s:decision:%s" % ("services", _sha256_hex(material)[:32])


def derive_admission_ref(service_ref: str, sequence: int) -> str:
    """Derive an execution-admission ref.  ``sequence`` is a derivation
    nonce input: it advances ONLY inside provider commit phases (the
    WORK-023/024 candidate-sequence discipline; a failed validation
    consumes no derivation state)."""
    if isinstance(sequence, bool) or not isinstance(sequence, int):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "derive_admission_ref sequence must be an int",
        )
    material = {
        "admission": {"service_ref": service_ref, "sequence": sequence}
    }
    return "%s:admission:%s" % ("services", _sha256_hex(material)[:32])


def derive_allocation_ref(
    kind: str, quantity_base: int, purpose: str, sequence: int
) -> str:
    """Derive a capacity-allocation ref (registry-side derivation
    nonce; same candidate-sequence discipline)."""
    for scalar, label in (
        (kind, "kind"), (purpose, "purpose"),
    ):
        if not isinstance(scalar, str):
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "derive_allocation_ref %s must be a str" % (label,),
            )
    if isinstance(quantity_base, bool) or not isinstance(quantity_base, int):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "derive_allocation_ref quantity_base must be an int",
        )
    if isinstance(sequence, bool) or not isinstance(sequence, int):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "derive_allocation_ref sequence must be an int",
        )
    material = {
        "allocation": {
            "kind": kind,
            "quantity_base": quantity_base,
            "purpose": purpose,
            "sequence": sequence,
        }
    }
    return "%s:allocation:%s" % ("services", _sha256_hex(material)[:32])


def derive_execution_ref(
    admission_ref: str, executed_at: str, request_digest: str
) -> str:
    """Derive a content-derived execution ref from the admission, the
    injected execution instant, and the SHA-256 digest of the request
    payload the executor actually executed."""
    if not isinstance(request_digest, str):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "derive_execution_ref request_digest must be a str",
        )
    if not re.fullmatch(r"[0-9a-f]{64}", request_digest):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "derive_execution_ref request_digest must be 64 lowercase "
            "hex characters",
        )
    material = {
        "execution": {
            "admission_ref": admission_ref,
            "executed_at": executed_at,
            "request_sha256": request_digest,
        }
    }
    return "%s:execution:%s" % ("services", _sha256_hex(material)[:32])


def derive_exposure_ref(
    service_ref: str, relationship_id: str, scope: str
) -> str:
    """Derive a federation-exposure ref (identity = service +
    relationship + scope; re-application is idempotent)."""
    material = {
        "exposure": {
            "service_ref": service_ref,
            "relationship_id": relationship_id,
            "scope": scope,
        }
    }
    return "%s:exposure:%s" % ("services", _sha256_hex(material)[:32])


def derive_integration_id(instance_label: str) -> str:
    """Derive the canonical integration id for a registry instance
    (mirrors the WORK-024 derive_integration_id discipline)."""
    if not isinstance(instance_label, str) or not instance_label:
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "instance_label must be a non-empty str",
        )
    material = {"integration": {"instance_label": instance_label}}
    return "%s:%s" % ("services", _sha256_hex(material)[:16])


# ---- # Canonical records ------------------------------------------------ #

def _string_tuple(value: object, *, label: str) -> Tuple[str, ...]:
    if not isinstance(value, tuple):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "%s must be a tuple (got %s)" % (label, type(value).__name__),
        )
    for item in value:
        if not isinstance(item, str):
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "%s entries must be str (got %s)" % (label, type(item).__name__),
            )
    return value


@dataclass(frozen=True)
class ServiceCapacity:
    """A declared capacity OFFER in WORK-008 resource vocabulary and
    base units (DATA).  A declaration is not a reservation: admission
    is the reservation, and a zero quantity is a valid declaration
    that contributes NO allocatable capacity (the WORK-022 lesson)."""

    kind: str
    quantity_base: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "kind", validate_capacity_kind(self.kind)
        )
        object.__setattr__(
            self, "quantity_base",
            validate_capacity_quantity(self.quantity_base),
        )

    def to_dict(self) -> dict:
        return {"kind": self.kind, "quantity_base": self.quantity_base}


@dataclass(frozen=True)
class ServiceDescriptor:
    """Service-owned semantic DATA: name, kind, owning tenant domain
    (the service authority), capability references (WORK-002
    open-world grammar), and the label tuples used for deterministic
    intent compatibility filtering.  Hosting, validity, visibility,
    and capacity live on the advertisement, not the descriptor."""

    name: str
    service_kind: str
    tenant_domain: str
    capability_refs: Tuple[str, ...] = ()
    service_labels: Tuple[str, ...] = ()
    locality_labels: Tuple[str, ...] = ()
    privacy_labels: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", validate_service_name(self.name))
        object.__setattr__(
            self, "service_kind", validate_service_kind(self.service_kind)
        )
        object.__setattr__(
            self, "tenant_domain", validate_tenant_domain(self.tenant_domain)
        )
        caps = _string_tuple(
            self.capability_refs, label="capability_refs"
        )
        for cap in caps:
            validate_capability_ref(cap)
        object.__setattr__(self, "capability_refs", caps)
        for field_name, pretty in (
            ("service_labels", "service label"),
            ("locality_labels", "locality label"),
            ("privacy_labels", "privacy label"),
        ):
            labels = _string_tuple(
                getattr(self, field_name), label=field_name
            )
            for item in labels:
                validate_label(item, label=pretty)
            object.__setattr__(self, field_name, labels)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "service_kind": self.service_kind,
            "tenant_domain": self.tenant_domain,
            "capability_refs": list(self.capability_refs),
            "service_labels": list(self.service_labels),
            "locality_labels": list(self.locality_labels),
            "privacy_labels": list(self.privacy_labels),
        }


@dataclass(frozen=True)
class ServiceAdvertisement:
    """A registration claim: descriptor + hosting node + validity
    window + visibility scope + endpoint reference + declared
    capacity (+, for peer-imported claims, the federation
    relationship the claim arrived on).  The whole advertisement is
    bound by its evidence claim digest."""

    descriptor: ServiceDescriptor
    host_node_id: str
    registered_at: str
    expires_at: str
    visibility: str
    endpoint_ref: str = ""
    capacity: Tuple[ServiceCapacity, ...] = ()
    policy_controlled: bool = False
    federation_relationship_id: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.descriptor, ServiceDescriptor):
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "advertisement descriptor must be a ServiceDescriptor "
                "(got %s)" % (type(self.descriptor).__name__,),
            )
        object.__setattr__(
            self, "host_node_id", validate_node_id(self.host_node_id)
        )
        object.__setattr__(
            self, "registered_at", validate_instant(
                self.registered_at, label="registered_at"
            )
        )
        object.__setattr__(
            self, "expires_at", validate_instant(
                self.expires_at, label="expires_at"
            )
        )
        object.__setattr__(
            self, "visibility", validate_visibility(self.visibility)
        )
        object.__setattr__(
            self, "endpoint_ref", validate_endpoint_ref(self.endpoint_ref)
        )
        if not isinstance(self.capacity, tuple):
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "advertisement capacity must be a tuple of "
                "ServiceCapacity (got %s)" % (type(self.capacity).__name__,),
            )
        for entry in self.capacity:
            if not isinstance(entry, ServiceCapacity):
                raise ServiceError(
                    ServiceReasonCode.INVALID_INPUT,
                    "advertisement capacity entries must be "
                    "ServiceCapacity (got %s)" % (type(entry).__name__,),
                )
        if isinstance(self.policy_controlled, bool) is False:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "policy_controlled must be a bool",
            )
        if self.federation_relationship_id:
            validate_federation_ref(
                self.federation_relationship_id,
                label="federation_relationship_id",
            )

    @property
    def service_ref(self) -> str:
        return derive_service_ref(
            self.descriptor.name,
            self.descriptor.service_kind,
            self.descriptor.tenant_domain,
        )

    def to_dict(self) -> dict:
        return {
            "descriptor": self.descriptor.to_dict(),
            "host_node_id": self.host_node_id,
            "registered_at": self.registered_at,
            "expires_at": self.expires_at,
            "visibility": self.visibility,
            "endpoint_ref": self.endpoint_ref,
            "capacity": [entry.to_dict() for entry in self.capacity],
            "policy_controlled": self.policy_controlled,
            "federation_relationship_id": self.federation_relationship_id,
        }


@dataclass(frozen=True)
class AdvertisementEvidence:
    """Attributable evidence binding an advertisement claim (mirrors
    the WORK-024 gateway-evidence discipline): observer/reporter
    nodes, source class, observed instant, the claim digest, and
    optional secret-free provenance text."""

    observer_node_id: str
    reporter_node_id: str
    source_class: str
    observed_at: str
    claim_digest: str
    provenance: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "observer_node_id",
            validate_node_id(self.observer_node_id, label="observer node id"),
        )
        object.__setattr__(
            self, "reporter_node_id",
            validate_node_id(self.reporter_node_id, label="reporter node id"),
        )
        object.__setattr__(
            self, "source_class", validate_evidence_source(self.source_class)
        )
        object.__setattr__(
            self, "observed_at", validate_instant(
                self.observed_at, label="observed_at"
            )
        )
        object.__setattr__(
            self, "claim_digest", validate_claim_digest(self.claim_digest)
        )
        object.__setattr__(
            self, "provenance", reject_credential_like_text(
                self.provenance, label="provenance"
            )
        )

    def to_dict(self) -> dict:
        return {
            "observer_node_id": self.observer_node_id,
            "reporter_node_id": self.reporter_node_id,
            "source_class": self.source_class,
            "observed_at": self.observed_at,
            "claim_digest": self.claim_digest,
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class ServiceCandidate:
    """The registry's view of a service record: the discovery /
    lookup result.  Carries service identity, hosting location, and
    declared DATA -- never a computed route (connectivity to a
    selected service composes ordinary WORK-011 paths / WORK-024
    breakout semantics at the composition root)."""

    service_ref: str
    name: str
    service_kind: str
    tenant_domain: str
    host_node_id: str
    capability_refs: Tuple[str, ...]
    service_labels: Tuple[str, ...]
    locality_labels: Tuple[str, ...]
    privacy_labels: Tuple[str, ...]
    visibility: str
    registered_at: str
    expires_at: str
    endpoint_ref: str = ""
    capacity: Tuple[ServiceCapacity, ...] = ()
    state: str = ServiceLifecycle.REGISTERED
    source_class: str = EvidenceSourceClass.DIRECT_OBSERVATION
    policy_controlled: bool = False
    federation_relationship_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "service_ref",
            validate_opaque_ref(self.service_ref, "service"),
        )
        object.__setattr__(self, "name", validate_service_name(self.name))
        object.__setattr__(
            self, "service_kind", validate_service_kind(self.service_kind)
        )
        object.__setattr__(
            self, "tenant_domain", validate_tenant_domain(self.tenant_domain)
        )
        object.__setattr__(
            self, "host_node_id", validate_node_id(self.host_node_id)
        )
        for field_name, pretty in (
            ("capability_refs", "capability ref"),
            ("service_labels", "service label"),
            ("locality_labels", "locality label"),
            ("privacy_labels", "privacy label"),
        ):
            entries = _string_tuple(
                getattr(self, field_name), label=field_name
            )
            for item in entries:
                if field_name == "capability_refs":
                    validate_capability_ref(item)
                else:
                    validate_label(item, label=pretty)
            object.__setattr__(self, field_name, entries)
        object.__setattr__(
            self, "visibility", validate_visibility(self.visibility)
        )
        object.__setattr__(
            self, "registered_at", validate_instant(
                self.registered_at, label="registered_at"
            )
        )
        object.__setattr__(
            self, "expires_at", validate_instant(
                self.expires_at, label="expires_at"
            )
        )
        object.__setattr__(
            self, "endpoint_ref", validate_endpoint_ref(self.endpoint_ref)
        )
        if not isinstance(self.capacity, tuple):
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "candidate capacity must be a tuple of ServiceCapacity",
            )
        for entry in self.capacity:
            if not isinstance(entry, ServiceCapacity):
                raise ServiceError(
                    ServiceReasonCode.INVALID_INPUT,
                    "candidate capacity entries must be ServiceCapacity",
                )
        if self.state not in ServiceLifecycle.values():
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "candidate state %r is not a frozen lifecycle state"
                % (self.state,),
            )
        object.__setattr__(
            self, "source_class", validate_evidence_source(self.source_class)
        )
        if isinstance(self.policy_controlled, bool) is False:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "policy_controlled must be a bool",
            )
        if self.federation_relationship_id:
            validate_federation_ref(
                self.federation_relationship_id,
                label="federation_relationship_id",
            )
        assert_service_node_separation(self.service_ref, self.host_node_id)

    def to_dict(self) -> dict:
        return {
            "service_ref": self.service_ref,
            "name": self.name,
            "service_kind": self.service_kind,
            "tenant_domain": self.tenant_domain,
            "host_node_id": self.host_node_id,
            "capability_refs": list(self.capability_refs),
            "service_labels": list(self.service_labels),
            "locality_labels": list(self.locality_labels),
            "privacy_labels": list(self.privacy_labels),
            "visibility": self.visibility,
            "registered_at": self.registered_at,
            "expires_at": self.expires_at,
            "endpoint_ref": self.endpoint_ref,
            "capacity": [entry.to_dict() for entry in self.capacity],
            "state": self.state,
            "source_class": self.source_class,
            "policy_controlled": self.policy_controlled,
            "federation_relationship_id": self.federation_relationship_id,
        }


@dataclass(frozen=True)
class InvocationDecision:
    """A session/caller/service-scoped record of a REAL WORK-010
    policy decision that ALLOWED an invocation (tamper-evident by
    construction: the decision_ref must equal the content-derived
    ref; the policy effect must be ``allow``; a DENY never becomes an
    InvocationDecision -- it fails closed at apply time).

    The scope (service, session, caller, tenant) is EXTRACTED FROM
    THE DECISION'S OWN digest-covered invocation binding (PR #26
    review, blocker 2): the registry never accepts scope parameters
    on apply, so this record can only ever restate the scope the
    WORK-010 decision itself authorized."""

    decision_ref: str
    service_ref: str
    session_id: str
    caller_node_id: str
    tenant_domain: str
    policy_decision_id: str
    policy_effect: str
    matched_rule_ids: Tuple[str, ...]
    applied_instant: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "decision_ref",
            validate_opaque_ref(self.decision_ref, "decision"),
        )
        object.__setattr__(
            self, "service_ref",
            validate_opaque_ref(self.service_ref, "service"),
        )
        if self.session_id:
            validate_session_ref(self.session_id)
        if self.caller_node_id:
            validate_node_id(
                self.caller_node_id, label="caller node id"
            )
        object.__setattr__(
            self, "tenant_domain", validate_tenant_domain(self.tenant_domain)
        )
        if not self.tenant_domain:
            raise ServiceError(
                ServiceReasonCode.TENANT_ISOLATION,
                "an invocation decision must carry an explicit tenant "
                "domain (tenant-scoped authorization is never optional)",
            )
        object.__setattr__(
            self, "policy_decision_id",
            validate_policy_decision_id(self.policy_decision_id),
        )
        if self.policy_effect != "allow":
            raise ServiceError(
                ServiceReasonCode.DECISION_DENIED,
                "an InvocationDecision records an ALLOW effect only -- "
                "policy DENY never becomes service-layer authorization "
                "(WORK-025 invariant 3)",
            )
        rules = _string_tuple(
            self.matched_rule_ids, label="matched_rule_ids"
        )
        object.__setattr__(self, "matched_rule_ids", rules)
        object.__setattr__(
            self, "applied_instant", validate_instant(
                self.applied_instant, label="applied_instant"
            )
        )
        if self.session_id:
            assert_ref_session_separation(self.decision_ref, self.session_id)
        expected = derive_decision_ref(
            self.service_ref, self.session_id, self.caller_node_id,
            self.tenant_domain, self.policy_decision_id,
            self.applied_instant,
        )
        if self.decision_ref != expected:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "decision_ref must equal the content-derived "
                "derive_decision_ref(...) -- a tampered or miscomputed "
                "ref is rejected (the decision is attributable DATA)",
            )

    def to_dict(self) -> dict:
        return {
            "decision_ref": self.decision_ref,
            "service_ref": self.service_ref,
            "session_id": self.session_id,
            "caller_node_id": self.caller_node_id,
            "tenant_domain": self.tenant_domain,
            "policy_decision_id": self.policy_decision_id,
            "policy_effect": self.policy_effect,
            "matched_rule_ids": list(self.matched_rule_ids),
            "applied_instant": self.applied_instant,
        }


@dataclass(frozen=True)
class ServiceAdmission:
    """A standing execution admission (the prepare/admit hook result):
    reserves execution capacity for a service invocation.  Carries the
    governing decision ref and -- only as opaque authorized DATA --
    the session id."""

    admission_ref: str
    service_ref: str
    host_node_id: str
    tenant_domain: str
    session_id: str
    decision_ref: str
    admitted_at: str
    state: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "admission_ref",
            validate_opaque_ref(self.admission_ref, "admission"),
        )
        object.__setattr__(
            self, "service_ref",
            validate_opaque_ref(self.service_ref, "service"),
        )
        object.__setattr__(
            self, "host_node_id", validate_node_id(self.host_node_id)
        )
        object.__setattr__(
            self, "tenant_domain", validate_tenant_domain(self.tenant_domain)
        )
        if self.session_id:
            validate_session_ref(self.session_id)
            assert_ref_session_separation(self.admission_ref, self.session_id)
        object.__setattr__(
            self, "decision_ref",
            validate_opaque_ref(self.decision_ref, "decision"),
        )
        object.__setattr__(
            self, "admitted_at", validate_instant(
                self.admitted_at, label="admitted_at"
            )
        )
        if self.state not in AdmissionState.values():
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "admission state %r is not a frozen admission state"
                % (self.state,),
            )
        assert_service_node_separation(self.service_ref, self.host_node_id)

    def to_dict(self) -> dict:
        return {
            "admission_ref": self.admission_ref,
            "service_ref": self.service_ref,
            "host_node_id": self.host_node_id,
            "tenant_domain": self.tenant_domain,
            "session_id": self.session_id,
            "decision_ref": self.decision_ref,
            "admitted_at": self.admitted_at,
            "state": self.state,
        }


@dataclass(frozen=True)
class CapacityAllocation:
    """An explicit capacity reservation over WORK-008 DATA (the
    registry-side allocation ledger entry)."""

    allocation_ref: str
    kind: str
    quantity_base: int
    purpose: str
    state: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "allocation_ref",
            validate_opaque_ref(self.allocation_ref, "allocation"),
        )
        object.__setattr__(
            self, "kind", validate_capacity_kind(self.kind)
        )
        object.__setattr__(
            self, "quantity_base",
            validate_capacity_quantity(self.quantity_base),
        )
        if not isinstance(self.purpose, str) or not self.purpose:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "allocation purpose must be a non-empty str",
            )
        if self.state not in AllocationState.values():
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "allocation state %r is not a frozen allocation state"
                % (self.state,),
            )

    def to_dict(self) -> dict:
        return {
            "allocation_ref": self.allocation_ref,
            "kind": self.kind,
            "quantity_base": self.quantity_base,
            "purpose": self.purpose,
            "state": self.state,
        }


@dataclass(frozen=True)
class ExecutionOutcome:
    """A provider-neutral execution result: explicit status, explicit
    partial-failure detail, deterministic response payload.  The
    execution ref is content-derived (admission + injected instant +
    request digest) and is re-derived at construction (tamper
    evident)."""

    admission_ref: str
    service_ref: str
    execution_ref: str
    status: str
    executed_at: str
    request_bytes: int
    request_digest: str
    response_payload: bytes
    detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "admission_ref",
            validate_opaque_ref(self.admission_ref, "admission"),
        )
        object.__setattr__(
            self, "service_ref",
            validate_opaque_ref(self.service_ref, "service"),
        )
        object.__setattr__(
            self, "execution_ref",
            validate_opaque_ref(self.execution_ref, "execution"),
        )
        if self.status not in ExecutionStatus.values():
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "execution status %r is not a frozen execution status"
                % (self.status,),
            )
        object.__setattr__(
            self, "executed_at", validate_instant(
                self.executed_at, label="executed_at"
            )
        )
        if isinstance(self.request_bytes, bool) or not isinstance(
            self.request_bytes, int
        ):
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "request_bytes must be an int",
            )
        if not isinstance(self.request_digest, str) or not re.fullmatch(
            r"[0-9a-f]{64}", self.request_digest
        ):
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "request_digest must be 64 lowercase hex characters "
                "(the SHA-256 of the executed request payload)",
            )
        if not isinstance(self.response_payload, bytes):
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "response_payload must be bytes",
            )
        object.__setattr__(
            self, "detail", reject_credential_like_text(
                self.detail, label="execution detail"
            )
        )
        expected = derive_execution_ref(
            self.admission_ref, self.executed_at, self.request_digest
        )
        if self.execution_ref != expected:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "execution_ref must equal the content-derived "
                "derive_execution_ref(...) -- a tampered or miscomputed "
                "ref is rejected",
            )

    def to_dict(self) -> dict:
        return {
            "admission_ref": self.admission_ref,
            "service_ref": self.service_ref,
            "execution_ref": self.execution_ref,
            "status": self.status,
            "executed_at": self.executed_at,
            "request_bytes": self.request_bytes,
            "request_digest": self.request_digest,
            "response_payload_hex": self.response_payload.hex(),
            "detail": self.detail,
        }


@dataclass(frozen=True)
class PlacementTransition:
    """An auditable placement/relocation fact: the ServiceID stays
    stable, the host changes, the transition is recorded (never a
    silent host mutation), and authorization is re-evaluated under
    current policy afterwards (standing decisions stop being current
    at the transition instant)."""

    service_ref: str
    from_host_node_id: str
    to_host_node_id: str
    transitioned_at: str
    endpoint_ref: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "service_ref",
            validate_opaque_ref(self.service_ref, "service"),
        )
        object.__setattr__(
            self, "from_host_node_id",
            validate_node_id(
                self.from_host_node_id, label="from host node id"
            ),
        )
        object.__setattr__(
            self, "to_host_node_id",
            validate_node_id(self.to_host_node_id, label="to host node id"),
        )
        object.__setattr__(
            self, "transitioned_at", validate_instant(
                self.transitioned_at, label="transitioned_at"
            )
        )
        object.__setattr__(
            self, "endpoint_ref", validate_endpoint_ref(self.endpoint_ref)
        )
        assert_service_node_separation(self.service_ref, self.to_host_node_id)

    def to_dict(self) -> dict:
        return {
            "service_ref": self.service_ref,
            "from_host_node_id": self.from_host_node_id,
            "to_host_node_id": self.to_host_node_id,
            "transitioned_at": self.transitioned_at,
            "endpoint_ref": self.endpoint_ref,
        }


@dataclass(frozen=True)
class ServiceTombstone:
    """A withdrawal tombstone: explicit, ordered, and replay
    protecting -- a re-registration whose ``registered_at`` is not
    strictly AFTER the tombstone instant is rejected as a replay of
    the withdrawn advertisement."""

    service_ref: str
    withdrawn_at: str
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "service_ref",
            validate_opaque_ref(self.service_ref, "service"),
        )
        object.__setattr__(
            self, "withdrawn_at", validate_instant(
                self.withdrawn_at, label="withdrawn_at"
            )
        )
        object.__setattr__(
            self, "reason", reject_credential_like_text(
                self.reason, label="withdrawal reason"
            )
        )

    def to_dict(self) -> dict:
        return {
            "service_ref": self.service_ref,
            "withdrawn_at": self.withdrawn_at,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class FederationExposure:
    """Federation-scoped visibility DATA: the service is exposed to
    one WORK-015 relationship under one frozen federation scope.
    Carries federation REFERENCES as DATA only -- no federation trust
    state is imported (WORK-025 invariant 4); removing an exposure
    never deletes the local service record."""

    exposure_ref: str
    service_ref: str
    relationship_id: str
    scope: str
    exposed_at: str
    state: str = ExposureState.ACTIVE

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "exposure_ref",
            validate_opaque_ref(self.exposure_ref, "exposure"),
        )
        object.__setattr__(
            self, "service_ref",
            validate_opaque_ref(self.service_ref, "service"),
        )
        object.__setattr__(
            self, "relationship_id", validate_federation_ref(
                self.relationship_id, label="relationship id"
            )
        )
        if not isinstance(self.scope, str) or not self.scope:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "exposure scope must be a non-empty str (federation "
                "scope DATA)",
            )
        object.__setattr__(
            self, "exposed_at", validate_instant(
                self.exposed_at, label="exposed_at"
            )
        )
        if self.state not in ExposureState.values():
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "exposure state %r is not a frozen exposure state"
                % (self.state,),
            )
        expected = derive_exposure_ref(
            self.service_ref, self.relationship_id, self.scope
        )
        if self.exposure_ref != expected:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "exposure_ref must equal the content-derived "
                "derive_exposure_ref(...) -- a tampered or miscomputed "
                "ref is rejected",
            )

    def to_dict(self) -> dict:
        return {
            "exposure_ref": self.exposure_ref,
            "service_ref": self.service_ref,
            "relationship_id": self.relationship_id,
            "scope": self.scope,
            "exposed_at": self.exposed_at,
            "state": self.state,
        }


@dataclass(frozen=True)
class ServiceObservation:
    """An honest, deterministic observation of service-layer state
    (registry or executor).  Counts are facts at the injected
    instant; the upstream flag reports upstream connectivity WITHOUT
    declaring remote service loss to be local state corruption
    (WORK-025 invariant 7: an upstream outage is an upstream
    outage)."""

    samples: Tuple[Tuple[str, int], ...] = ()
    registered_services: int = 0
    available_services: int = 0
    withdrawn_services: int = 0
    expired_services: int = 0
    federated_exposures: int = 0
    active_admissions: int = 0
    executed_requests: int = 0
    failed_requests: int = 0
    upstream_available: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.samples, tuple):
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "observation samples must be a tuple",
            )
        for sample in self.samples:
            if (
                not isinstance(sample, tuple)
                or len(sample) != 2
                or not isinstance(sample[0], str)
                or sample[0] not in ServiceMetricName.values()
                or isinstance(sample[1], bool)
                or not isinstance(sample[1], int)
            ):
                raise ServiceError(
                    ServiceReasonCode.INVALID_INPUT,
                    "observation samples must be (frozen metric name, int) "
                    "pairs (got %r)" % (sample,),
                )
        for field_name in (
            "registered_services", "available_services", "withdrawn_services",
            "expired_services", "federated_exposures", "active_admissions",
            "executed_requests", "failed_requests", "upstream_available",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ServiceError(
                    ServiceReasonCode.INVALID_INPUT,
                    "observation %s must be an int" % (field_name,),
                )
            if value < 0:
                raise ServiceError(
                    ServiceReasonCode.INVALID_INPUT,
                    "observation %s must be non-negative" % (field_name,),
                )

    def to_dict(self) -> dict:
        return {
            "samples": [[name, value] for name, value in self.samples],
            "registered_services": self.registered_services,
            "available_services": self.available_services,
            "withdrawn_services": self.withdrawn_services,
            "expired_services": self.expired_services,
            "federated_exposures": self.federated_exposures,
            "active_admissions": self.active_admissions,
            "executed_requests": self.executed_requests,
            "failed_requests": self.failed_requests,
            "upstream_available": self.upstream_available,
        }


@dataclass(frozen=True)
class ServiceEvent:
    """An append-only registry audit event (canonical; data-path
    execution requests append NO events, mirroring the WORK-024
    egress discipline)."""

    event_type: str
    instant: str
    service_ref: str = ""
    admission_ref: str = ""
    detail: str = ""

    def __post_init__(self) -> None:
        if self.event_type not in ServiceEventType.values():
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "event type %r is not a frozen service event type"
                % (self.event_type,),
            )
        object.__setattr__(
            self, "instant", validate_instant(self.instant, label="instant")
        )
        if self.service_ref:
            validate_opaque_ref(self.service_ref, "service")
        if self.admission_ref:
            validate_opaque_ref(self.admission_ref, "admission")
        object.__setattr__(
            self, "detail", reject_credential_like_text(
                self.detail, label="event detail"
            )
        )

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "instant": self.instant,
            "service_ref": self.service_ref,
            "admission_ref": self.admission_ref,
            "detail": self.detail,
        }


__all__ = [
    "MAX_CAPACITY_QUANTITY",
    "ServiceKind",
    "VisibilityScope",
    "ServiceLifecycle",
    "EvidenceSourceClass",
    "AdmissionState",
    "AllocationState",
    "ExecutionStatus",
    "ExposureState",
    "ServiceMetricName",
    "ServiceEventType",
    "derive_service_ref",
    "derive_advertisement_claim_digest",
    "derive_decision_ref",
    "derive_admission_ref",
    "derive_allocation_ref",
    "derive_execution_ref",
    "derive_exposure_ref",
    "derive_integration_id",
    "ServiceCapacity",
    "ServiceDescriptor",
    "ServiceAdvertisement",
    "AdvertisementEvidence",
    "ServiceCandidate",
    "InvocationDecision",
    "ServiceAdmission",
    "CapacityAllocation",
    "ExecutionOutcome",
    "PlacementTransition",
    "ServiceTombstone",
    "FederationExposure",
    "ServiceObservation",
    "ServiceEvent",
]
