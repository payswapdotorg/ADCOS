"""WORK-036 Network-in-a-Box frozen vocabularies and value records.

Everything here is DATA with validation (the WORK-033 ``agent.model``
style): frozen vocabularies with ``values()`` classmethods, immutable
records with content-derived ids/digests, and canonical bytes that
make every value replayable.  The manifest entries reuse the ACCEPTED
WORK-024/W025 domain objects (descriptors, advertisements, evidence,
paths) as DATA -- no second authority, no re-declared vocabulary.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Tuple

from protocol.canonicalization import canonical_json_bytes

from .errors import ApplianceError, ApplianceReasonCode

_DETAIL_LIMIT = 200


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _bounded_detail(value: str) -> str:
    text = str(value)
    if len(text) <= _DETAIL_LIMIT:
        return text
    return text[: _DETAIL_LIMIT - 3] + "..."


# ----------------------------------------------------------------------
# Frozen vocabularies
# ----------------------------------------------------------------------


class UpstreamMode:
    """The appliance's upstream-Internet posture.

    ``ISOLATED`` is the appliance's design center (community /
    emergency deployment): the box and its local fabric operate with
    NO upstream Internet.  ``CONNECTED`` merely records that an
    operator declared upstream availability; it grants no new
    authority and never weakens the local-first behavior.
    """

    ISOLATED = "isolated"
    CONNECTED = "connected"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.ISOLATED, cls.CONNECTED)


class ProvisionState:
    """The operator-provisioning lifecycle of the local fabric."""

    UNPROVISIONED = "unprovisioned"
    PROVISIONED = "provisioned"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.UNPROVISIONED, cls.PROVISIONED)


class ApplianceVerdict:
    """One appliance command's verdict.

    The union is honest by construction: passthrough commands inherit
    the WORK-034 scheduler verdicts (``deferred`` / ``shed``) verbatim;
    appliance-native commands use ``executed`` / ``rejected`` /
    ``failed``.  Nothing is silently remapped.
    """

    EXECUTED = "executed"
    DEFERRED = "deferred"
    SHED = "shed"
    REJECTED = "rejected"
    FAILED = "failed"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.EXECUTED,
            cls.DEFERRED,
            cls.SHED,
            cls.REJECTED,
            cls.FAILED,
        )


class ApplianceCommandKind:
    """The frozen headless command vocabulary.

    ``boot`` / ``expose-interfaces`` / ``monitor`` are passthrough:
    they are re-wrapped as genuine ``AgentCommand`` values and flow
    through the UNCHANGED WORK-034 ``EdgeGateway.run_edge`` scheduling
    path (which itself flows through the unchanged WORK-033
    ``AgentRuntime.execute``).  The appliance-native kinds operate the
    local fabric surfaces (provisioning, upstream posture, services).
    """

    BOOT = "boot"
    EXPOSE_INTERFACES = "expose-interfaces"
    PROVISION_FABRIC = "provision-fabric"
    SET_UPSTREAM = "set-upstream"
    DISCOVER_SERVICES = "discover-services"
    LOOKUP_SERVICE = "lookup-service"
    SERVICE_REQUEST = "service-request"
    OBSERVE_FABRIC = "observe-fabric"
    MONITOR = "monitor"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.BOOT,
            cls.EXPOSE_INTERFACES,
            cls.PROVISION_FABRIC,
            cls.SET_UPSTREAM,
            cls.DISCOVER_SERVICES,
            cls.LOOKUP_SERVICE,
            cls.SERVICE_REQUEST,
            cls.OBSERVE_FABRIC,
            cls.MONITOR,
        )


class ProvisionStepKind:
    """The frozen provisioning step vocabulary (application order:
    gateways, then paths, then services -- a path terminates at a
    gateway, and services are independent)."""

    REGISTER_GATEWAY = "register-gateway"
    REGISTER_PATH = "register-path"
    REGISTER_SERVICE = "register-service"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.REGISTER_GATEWAY,
            cls.REGISTER_PATH,
            cls.REGISTER_SERVICE,
        )


class ApplianceEventType:
    """The frozen appliance decision-journal vocabulary."""

    UPSTREAM_CHANGED = "upstream-changed"
    UPSTREAM_REJECTED = "upstream-rejected"
    FABRIC_PROVISIONED = "fabric-provisioned"
    FABRIC_PROVISION_REJECTED = "fabric-provision-rejected"
    FABRIC_OBSERVED = "fabric-observed"
    SERVICE_DISCOVERED = "service-discovered"
    SERVICE_LOOKUP_FAILED = "service-lookup-failed"
    SERVICE_REQUESTED = "service-requested"
    SERVICE_REQUEST_REJECTED = "service-request-rejected"
    COMMAND_REJECTED = "command-rejected"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.UPSTREAM_CHANGED,
            cls.UPSTREAM_REJECTED,
            cls.FABRIC_PROVISIONED,
            cls.FABRIC_PROVISION_REJECTED,
            cls.FABRIC_OBSERVED,
            cls.SERVICE_DISCOVERED,
            cls.SERVICE_LOOKUP_FAILED,
            cls.SERVICE_REQUEST_REJECTED,
            cls.SERVICE_REQUESTED,
            cls.COMMAND_REJECTED,
        )


# ----------------------------------------------------------------------
# Fabric manifest (the operator's declarative provisioning document)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class GatewayEntry:
    """One fabric gateway declaration: the ACCEPTED WORK-024
    ``GatewayDescriptor`` plus its binding ``GatewayEvidence`` (the
    claim digest must bind the whole descriptor -- validated by the
    pure provisioning check before anything is applied)."""

    descriptor: Any
    evidence: Any

    def __post_init__(self) -> None:
        from adapters.distcore import GatewayDescriptor, GatewayEvidence

        if not isinstance(self.descriptor, GatewayDescriptor):
            raise ApplianceError(
                ApplianceReasonCode.MANIFEST_INVALID,
                "gateway entry requires a genuine WORK-024 "
                "GatewayDescriptor (got %s)"
                % (type(self.descriptor).__name__,),
            )
        if not isinstance(self.evidence, GatewayEvidence):
            raise ApplianceError(
                ApplianceReasonCode.MANIFEST_INVALID,
                "gateway entry requires a genuine WORK-024 "
                "GatewayEvidence (got %s)"
                % (type(self.evidence).__name__,),
            )

    def to_dict(self) -> dict:
        return {
            "descriptor": self.descriptor.to_dict(),
            "claim_digest": self.evidence.claim_digest,
        }


@dataclass(frozen=True)
class ServiceEntry:
    """One local service declaration: the ACCEPTED WORK-025
    ``ServiceAdvertisement`` plus its binding
    ``AdvertisementEvidence`` (the claim digest must bind the whole
    advertisement claim)."""

    advertisement: Any
    evidence: Any

    def __post_init__(self) -> None:
        from services import (
            AdvertisementEvidence,
            ServiceAdvertisement,
        )

        if not isinstance(self.advertisement, ServiceAdvertisement):
            raise ApplianceError(
                ApplianceReasonCode.MANIFEST_INVALID,
                "service entry requires a genuine WORK-025 "
                "ServiceAdvertisement (got %s)"
                % (type(self.advertisement).__name__,),
            )
        if not isinstance(self.evidence, AdvertisementEvidence):
            raise ApplianceError(
                ApplianceReasonCode.MANIFEST_INVALID,
                "service entry requires a genuine WORK-025 "
                "AdvertisementEvidence (got %s)"
                % (type(self.evidence).__name__,),
            )

    def to_dict(self) -> dict:
        return {
            "service_ref": self.advertisement.service_ref,
            "claim_digest": self.evidence.claim_digest,
        }


@dataclass(frozen=True)
class FabricManifest:
    """The operator's complete local-fabric declaration.

    Pure DATA composed of ACCEPTED domain objects: WORK-024 gateway
    descriptors + evidence, WORK-011 paths, and WORK-025 service
    advertisements + evidence.  ``content_digest`` is the canonical
    fingerprint over the site label and every entry's claim identity;
    two manifests with the same digest provision the same fabric.
    The manifest carries no secrets and no policy semantics.
    """

    site_label: str
    gateways: Tuple[GatewayEntry, ...] = ()
    paths: Tuple[Any, ...] = ()
    services: Tuple[ServiceEntry, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.site_label, str) or not self.site_label:
            raise ApplianceError(
                ApplianceReasonCode.MANIFEST_INVALID,
                "site_label must be a non-empty string",
            )
        if len(self.site_label) > 64:
            raise ApplianceError(
                ApplianceReasonCode.MANIFEST_INVALID,
                "site_label must be at most 64 characters",
            )
        if not isinstance(self.gateways, tuple):
            raise ApplianceError(
                ApplianceReasonCode.MANIFEST_INVALID,
                "gateways must be a tuple of GatewayEntry values",
            )
        for gateway_entry in self.gateways:
            if not isinstance(gateway_entry, GatewayEntry):
                raise ApplianceError(
                    ApplianceReasonCode.MANIFEST_INVALID,
                    "gateways must contain genuine GatewayEntry values",
                )
        if not isinstance(self.paths, tuple):
            raise ApplianceError(
                ApplianceReasonCode.MANIFEST_INVALID,
                "paths must be a tuple of WORK-011 Path values",
            )
        from routing import Path as RoutingPath

        for path in self.paths:
            if not isinstance(path, RoutingPath):
                raise ApplianceError(
                    ApplianceReasonCode.MANIFEST_INVALID,
                    "paths must contain genuine WORK-011 Path values "
                    "(got %s)" % (type(path).__name__,),
                )
        if not isinstance(self.services, tuple):
            raise ApplianceError(
                ApplianceReasonCode.MANIFEST_INVALID,
                "services must be a tuple of ServiceEntry values",
            )
        for service_entry in self.services:
            if not isinstance(service_entry, ServiceEntry):
                raise ApplianceError(
                    ApplianceReasonCode.MANIFEST_INVALID,
                    "services must contain genuine ServiceEntry values",
                )

    def canonical_bytes(self) -> bytes:
        from adapters.distcore import derive_gateway_ref

        content: Dict[str, Any] = {
            "site_label": self.site_label,
            "gateways": [
                {
                    "gateway_ref": derive_gateway_ref(
                        entry.descriptor.name,
                        entry.descriptor.gateway_id,
                        entry.descriptor.node_id,
                        entry.descriptor.role_class,
                    ),
                    "claim_digest": entry.evidence.claim_digest,
                }
                for entry in self.gateways
            ],
            "paths": [path.path_id for path in self.paths],
            "services": [
                {
                    "service_ref": entry.advertisement.service_ref,
                    "claim_digest": entry.evidence.claim_digest,
                }
                for entry in self.services
            ],
        }
        return canonical_json_bytes(content)

    def content_digest(self) -> str:
        return "sha256:" + _sha256_hex(self.canonical_bytes())

    def to_dict(self) -> dict:
        return {
            "site_label": self.site_label,
            "gateways": [entry.to_dict() for entry in self.gateways],
            "paths": [path.path_id for path in self.paths],
            "services": [entry.to_dict() for entry in self.services],
            "content_digest": self.content_digest(),
        }


# ----------------------------------------------------------------------
# Provisioning steps
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ProvisionStep:
    """One planned manifest application step (kind + the entry's
    content-derived reference + a bounded detail)."""

    kind: str
    ref: str
    detail: str = ""

    def __post_init__(self) -> None:
        if self.kind not in ProvisionStepKind.values():
            raise ApplianceError(
                ApplianceReasonCode.INVALID_INPUT,
                "provision step kind %r not in the frozen vocabulary"
                % (self.kind,),
            )
        if not isinstance(self.ref, str) or not self.ref:
            raise ApplianceError(
                ApplianceReasonCode.INVALID_INPUT,
                "provision step requires a non-empty reference",
            )

    def to_dict(self) -> dict:
        return {"kind": self.kind, "ref": self.ref, "detail": self.detail}


# ----------------------------------------------------------------------
# Commands (data-driven, content-derived ids)
# ----------------------------------------------------------------------


def _param_projection(value: Any) -> Any:
    """Reduce one command-parameter value to the canonical subset.

    Canonical-subset values pass through; ``bytes`` become hex text;
    objects carrying ``content_digest()`` (the manifest) or
    ``canonical_bytes()`` (a genuine WORK-010 decision) reduce to
    their content digests -- transitively content-derived, so command
    ids remain tamper-evident fingerprints.  Anything else fails
    closed (no silent stringification of arbitrary objects).
    """
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex()}
    if isinstance(value, Mapping):
        return {str(key): _param_projection(value[key]) for key in value}
    if isinstance(value, (tuple, list)):
        return [_param_projection(item) for item in value]
    digest = getattr(value, "content_digest", None)
    if callable(digest):
        return {"content_digest": digest()}
    canonical = getattr(value, "canonical_bytes", None)
    if callable(canonical):
        return {"canonical_digest": _sha256_hex(canonical())}
    raise ApplianceError(
        ApplianceReasonCode.PARAMS_INVALID,
        "command parameter of type %s is not projectable to the "
        "canonical subset (carries neither content_digest() nor "
        "canonical_bytes())" % (type(value).__name__,),
    )


def derive_appliance_command_id(kind: str, params: Mapping[str, Any]) -> str:
    """Content-derived command id over (kind, projected params)."""
    content = {"kind": kind, "params": _param_projection(dict(params))}
    return "sha256:" + _sha256_hex(canonical_json_bytes(content))


@dataclass(frozen=True)
class ApplianceCommand:
    """One data-driven appliance command: a kind plus DATA params."""

    kind: str
    params: Mapping[str, Any] = field(default_factory=dict)
    command_id: str = ""

    def __post_init__(self) -> None:
        if self.kind not in ApplianceCommandKind.values():
            raise ApplianceError(
                ApplianceReasonCode.COMMAND_UNKNOWN,
                "unknown appliance command kind %r" % (self.kind,),
            )
        if not isinstance(self.params, Mapping):
            raise ApplianceError(
                ApplianceReasonCode.PARAMS_INVALID,
                "command params must be a mapping",
            )
        # Fail closed on non-projectable params at construction.
        _param_projection(dict(self.params))
        object.__setattr__(
            self,
            "command_id",
            self.command_id
            or derive_appliance_command_id(self.kind, self.params),
        )

    def to_dict(self) -> dict:
        return {
            "command_id": self.command_id,
            "kind": self.kind,
            "params": _param_projection(dict(self.params)),
        }


# ----------------------------------------------------------------------
# Appliance events (append-only decision journal)
# ----------------------------------------------------------------------


def derive_appliance_event_id(
    kind: str, sequence: int, instant: str, subject: str,
    detail: str, ref: str,
) -> str:
    content = {
        "kind": kind,
        "sequence": sequence,
        "instant": instant,
        "subject": subject,
        "detail": detail,
        "ref": ref,
    }
    return "sha256:" + _sha256_hex(canonical_json_bytes(content))


@dataclass(frozen=True)
class ApplianceEvent:
    """One append-only appliance-layer decision record."""

    kind: str
    sequence: int
    instant: str
    subject: str = ""
    detail: str = ""
    ref: str = ""
    event_id: str = ""

    def __post_init__(self) -> None:
        if self.kind not in ApplianceEventType.values():
            raise ApplianceError(
                ApplianceReasonCode.INVALID_INPUT,
                "appliance event kind %r not in the frozen vocabulary"
                % (self.kind,),
            )
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int):
            raise ApplianceError(
                ApplianceReasonCode.INVALID_INPUT,
                "event sequence must be an integer",
            )
        if self.sequence < 1:
            raise ApplianceError(
                ApplianceReasonCode.INVALID_INPUT,
                "event sequence must be >= 1",
            )
        for name in ("instant", "subject", "detail", "ref"):
            if not isinstance(getattr(self, name), str):
                raise ApplianceError(
                    ApplianceReasonCode.INVALID_INPUT,
                    "event %s must be a string" % (name,),
                )
        object.__setattr__(self, "detail", _bounded_detail(self.detail))
        object.__setattr__(
            self,
            "event_id",
            self.event_id
            or derive_appliance_event_id(
                self.kind, self.sequence, self.instant,
                self.subject, self.detail, self.ref,
            ),
        )

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "sequence": self.sequence,
            "instant": self.instant,
            "subject": self.subject,
            "detail": self.detail,
            "ref": self.ref,
            "event_id": self.event_id,
        }

    @classmethod
    def from_dict(cls, data: object) -> "ApplianceEvent":
        if not isinstance(data, Mapping):
            raise ApplianceError(
                ApplianceReasonCode.INVALID_INPUT,
                "appliance event must be a mapping",
            )
        return cls(
            kind=str(data.get("kind", "")),
            sequence=int(data.get("sequence", 0)),
            instant=str(data.get("instant", "")),
            subject=str(data.get("subject", "")),
            detail=str(data.get("detail", "")),
            ref=str(data.get("ref", "")),
            event_id=str(data.get("event_id", "")),
        )


def appliance_events_canonical_bytes(
    events: Tuple[ApplianceEvent, ...],
) -> bytes:
    return canonical_json_bytes(
        [event.to_dict() for event in events],
    )


def appliance_event_list_digest(
    events: Tuple[ApplianceEvent, ...],
) -> str:
    return "sha256:" + _sha256_hex(
        appliance_events_canonical_bytes(events),
    )


# ----------------------------------------------------------------------
# Outcomes and run results
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ApplianceOutcome:
    """One appliance command's verdict.  ``detail`` carries digests
    and references only (never payload CONTENT, never secrets)."""

    command_id: str
    kind: str
    verdict: str
    reason: str = ""
    detail: str = ""

    def __post_init__(self) -> None:
        if self.verdict not in ApplianceVerdict.values():
            raise ApplianceError(
                ApplianceReasonCode.INVALID_INPUT,
                "appliance verdict must be one of %s (got %r)"
                % (ApplianceVerdict.values(), self.verdict),
            )
        if self.verdict == ApplianceVerdict.EXECUTED and self.reason:
            raise ApplianceError(
                ApplianceReasonCode.INVALID_INPUT,
                "an executed outcome carries no rejection reason",
            )
        if not self.command_id:
            raise ApplianceError(
                ApplianceReasonCode.INVALID_INPUT,
                "an appliance outcome requires a command id",
            )
        object.__setattr__(self, "detail", _bounded_detail(self.detail))

    def to_dict(self) -> dict:
        return {
            "command_id": self.command_id,
            "kind": self.kind,
            "verdict": self.verdict,
            "reason": self.reason,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, data: object) -> "ApplianceOutcome":
        if not isinstance(data, Mapping):
            raise ApplianceError(
                ApplianceReasonCode.INVALID_INPUT,
                "appliance outcome must be a mapping",
            )
        return cls(
            command_id=str(data.get("command_id", "")),
            kind=str(data.get("kind", "")),
            verdict=str(data.get("verdict", "")),
            reason=str(data.get("reason", "")),
            detail=str(data.get("detail", "")),
        )


@dataclass(frozen=True)
class ApplianceRunResult:
    """The deterministic result of one appliance epoch: the agent's
    own status, the appliance verdicts, the fabric posture, and the
    digests that make the whole scenario replayable."""

    status: str
    executed: int
    rejected: int
    failed: int
    deferred: int
    shed: int
    outcomes: Tuple[ApplianceOutcome, ...] = ()
    upstream_mode: str = ""
    provision_state: str = ""
    agent_trace_digest: str = ""
    edge_event_digest: str = ""
    appliance_event_digest: str = ""
    appliance_digest: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "executed": self.executed,
            "rejected": self.rejected,
            "failed": self.failed,
            "deferred": self.deferred,
            "shed": self.shed,
            "outcomes": [outcome.to_dict() for outcome in self.outcomes],
            "upstream_mode": self.upstream_mode,
            "provision_state": self.provision_state,
            "agent_trace_digest": self.agent_trace_digest,
            "edge_event_digest": self.edge_event_digest,
            "appliance_event_digest": self.appliance_event_digest,
            "appliance_digest": self.appliance_digest,
        }


__all__ = [
    "UpstreamMode",
    "ProvisionState",
    "ApplianceVerdict",
    "ApplianceCommandKind",
    "ProvisionStepKind",
    "ApplianceEventType",
    "GatewayEntry",
    "ServiceEntry",
    "FabricManifest",
    "ProvisionStep",
    "ApplianceCommand",
    "ApplianceEvent",
    "ApplianceOutcome",
    "ApplianceRunResult",
    "derive_appliance_command_id",
    "derive_appliance_event_id",
    "appliance_events_canonical_bytes",
    "appliance_event_list_digest",
]
