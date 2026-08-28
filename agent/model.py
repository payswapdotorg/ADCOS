"""WORK-033 agent value model.

Pure data types for the Linux reference agent: interface snapshots,
the append-only agent event log records, the headless command model,
run/integrity results, configuration, and the cross-agent session
establishment artifacts.

Everything here is DATA.  The agent never mints authoritative objects
(policy decisions, route decisions, sessions) -- those come exclusively
from the composed authorities.  All identifiers are content-derived
over WORK-003 canonical JSON; all instants are injected RFC 3339 UTC
strings.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from protocol import canonical_json_bytes

from .errors import AgentError, AgentReasonCode


# ---------------------------------------------------------------------------
# Interface snapshots (the Linux network-interface projection)
# ---------------------------------------------------------------------------

LINK_KINDS: Tuple[str, ...] = ("ethernet", "loopback", "wireless", "other")


@dataclass(frozen=True)
class InterfaceSnapshot:
    """A discovered network interface, projected as adapter DATA.

    ``link_kind`` is the agent's local classification of the OS link
    layer; it maps to a registered access technology id at the adapter
    boundary (never into core semantics).  Counters are cumulative
    integers (monotonic OS counters; negative values are rejected).
    """

    name: str
    link_kind: str
    state_up: bool
    mtu: int
    speed_mbps: int
    rx_bytes: int
    tx_bytes: int
    rx_errors: int
    tx_errors: int
    addresses: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise AgentError(
                AgentReasonCode.INTERFACE_INVALID, "interface name must be a non-empty string"
            )
        if self.link_kind not in LINK_KINDS:
            raise AgentError(
                AgentReasonCode.INTERFACE_INVALID,
                "link_kind %r must be one of %s" % (self.link_kind, list(LINK_KINDS)),
            )
        for label, value in (
            ("mtu", self.mtu),
            ("speed_mbps", self.speed_mbps),
            ("rx_bytes", self.rx_bytes),
            ("tx_bytes", self.tx_bytes),
            ("rx_errors", self.rx_errors),
            ("tx_errors", self.tx_errors),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise AgentError(
                    AgentReasonCode.INTERFACE_INVALID,
                    "%s must be a non-negative integer (integer discipline)" % label,
                )
        if not isinstance(self.addresses, tuple) or any(
            not isinstance(item, str) for item in self.addresses
        ):
            raise AgentError(
                AgentReasonCode.INTERFACE_INVALID, "addresses must be a tuple of strings"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "link_kind": self.link_kind,
            "state_up": self.state_up,
            "mtu": self.mtu,
            "speed_mbps": self.speed_mbps,
            "rx_bytes": self.rx_bytes,
            "tx_bytes": self.tx_bytes,
            "rx_errors": self.rx_errors,
            "tx_errors": self.tx_errors,
            "addresses": list(self.addresses),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "InterfaceSnapshot":
        if not isinstance(data, Mapping):
            raise AgentError(
                AgentReasonCode.SERIALIZATION_INVALID, "interface snapshot must be a mapping"
            )
        return cls(
            name=data.get("name", ""),
            link_kind=data.get("link_kind", ""),
            state_up=bool(data.get("state_up", False)),
            mtu=int(data.get("mtu", 0)),
            speed_mbps=int(data.get("speed_mbps", 0)),
            rx_bytes=int(data.get("rx_bytes", 0)),
            tx_bytes=int(data.get("tx_bytes", 0)),
            rx_errors=int(data.get("rx_errors", 0)),
            tx_errors=int(data.get("tx_errors", 0)),
            addresses=tuple(str(item) for item in data.get("addresses", ())),
        )

    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(
            canonical_json_bytes(self.to_dict())
        ).hexdigest()


# ---------------------------------------------------------------------------
# Agent event log ("logs")
# ---------------------------------------------------------------------------

class AgentEventType:
    """Frozen agent event-kind vocabulary (append-only log records)."""

    BOOTED = "booted"
    SHUTDOWN = "shutdown"
    INTERFACE_DISCOVERED = "interface-discovered"
    ADAPTER_REGISTERED = "adapter-registered"
    ADAPTER_OPENED = "adapter-opened"
    ADAPTER_CLOSED = "adapter-closed"
    PEER_REGISTERED = "peer-registered"
    POLICY_PUBLISHED = "policy-published"
    SESSION_REQUESTED = "session-requested"
    SESSION_ACCEPTED = "session-accepted"
    SESSION_ESTABLISHED = "session-established"
    SESSION_BOUND = "session-bound"
    SESSION_SUSPENDED = "session-suspended"
    SESSION_TERMINATED = "session-terminated"
    TRANSPORT_ESTABLISHED = "transport-established"
    TRANSPORT_CLOSED = "transport-closed"
    OBSERVATION_RECORDED = "observation-recorded"
    SELF_TEST_COMPLETED = "self-test-completed"
    COMMAND_APPLIED = "command-applied"
    COMMAND_REJECTED = "command-rejected"
    COMMAND_FAILED = "command-failed"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.BOOTED,
            cls.SHUTDOWN,
            cls.INTERFACE_DISCOVERED,
            cls.ADAPTER_REGISTERED,
            cls.ADAPTER_OPENED,
            cls.ADAPTER_CLOSED,
            cls.PEER_REGISTERED,
            cls.POLICY_PUBLISHED,
            cls.SESSION_REQUESTED,
            cls.SESSION_ACCEPTED,
            cls.SESSION_ESTABLISHED,
            cls.SESSION_BOUND,
            cls.SESSION_SUSPENDED,
            cls.SESSION_TERMINATED,
            cls.TRANSPORT_ESTABLISHED,
            cls.TRANSPORT_CLOSED,
            cls.OBSERVATION_RECORDED,
            cls.SELF_TEST_COMPLETED,
            cls.COMMAND_APPLIED,
            cls.COMMAND_REJECTED,
            cls.COMMAND_FAILED,
        )


@dataclass(frozen=True)
class AgentEvent:
    """One append-only agent log record with a content-derived id."""

    kind: str
    sequence: int
    instant: str
    subject: str = ""
    detail: str = ""
    command_ref: str = ""
    event_id: str = ""

    def __post_init__(self) -> None:
        if self.kind not in AgentEventType.values():
            raise AgentError(
                AgentReasonCode.INVALID_INPUT, "unknown agent event kind %r" % self.kind
            )
        object.__setattr__(
            self, "event_id", self.event_id or derive_agent_event_id(self)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "kind": self.kind,
            "sequence": self.sequence,
            "instant": self.instant,
            "subject": self.subject,
            "detail": self.detail,
            "command_ref": self.command_ref,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AgentEvent":
        if not isinstance(data, Mapping):
            raise AgentError(
                AgentReasonCode.SERIALIZATION_INVALID, "agent event must be a mapping"
            )
        return cls(
            kind=str(data.get("kind", "")),
            sequence=int(data.get("sequence", 0)),
            instant=str(data.get("instant", "")),
            subject=str(data.get("subject", "")),
            detail=str(data.get("detail", "")),
            command_ref=str(data.get("command_ref", "")),
        )


def derive_agent_event_id(event: AgentEvent) -> str:
    content = {
        "kind": event.kind,
        "sequence": event.sequence,
        "instant": event.instant,
        "subject": event.subject,
        "detail": event.detail,
        "command_ref": event.command_ref,
    }
    return "sha256:" + hashlib.sha256(canonical_json_bytes(content)).hexdigest()


def agent_events_canonical_bytes(events: Sequence[AgentEvent]) -> bytes:
    return canonical_json_bytes([event.to_dict() for event in events])


# ---------------------------------------------------------------------------
# Headless command model
# ---------------------------------------------------------------------------

class CommandKind:
    """Frozen headless command vocabulary.

    A run is a data-driven command sequence: no interactive operator
    input exists anywhere in the agent.  Commands dispatch to the same
    public runtime methods an operator would call through the
    management surface.
    """

    BOOT = "boot"
    EXPOSE_INTERFACES = "expose-interfaces"
    REGISTER_PEER = "register-peer"
    MONITOR = "monitor"
    SEND_DATAGRAM = "send-datagram"
    RECEIVE_DATAGRAM = "receive-datagram"
    SUSPEND_SESSION = "suspend-session"
    TERMINATE_SESSION = "terminate-session"
    NEGOTIATE_PEER = "negotiate-peer"
    SELF_TEST = "self-test"
    SHUTDOWN = "shutdown"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.BOOT,
            cls.EXPOSE_INTERFACES,
            cls.REGISTER_PEER,
            cls.MONITOR,
            cls.SEND_DATAGRAM,
            cls.RECEIVE_DATAGRAM,
            cls.SUSPEND_SESSION,
            cls.TERMINATE_SESSION,
            cls.NEGOTIATE_PEER,
            cls.SELF_TEST,
            cls.SHUTDOWN,
        )


@dataclass(frozen=True)
class AgentCommand:
    """One headless command: a kind plus DATA parameters."""

    kind: str
    params: Mapping[str, Any] = field(default_factory=dict)
    command_id: str = ""

    def __post_init__(self) -> None:
        if self.kind not in CommandKind.values():
            raise AgentError(
                AgentReasonCode.INVALID_INPUT, "unknown agent command kind %r" % self.kind
            )
        if not isinstance(self.params, Mapping):
            raise AgentError(
                AgentReasonCode.INVALID_INPUT, "command params must be a mapping"
            )
        object.__setattr__(
            self, "command_id", self.command_id or derive_command_id(self)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {"command_id": self.command_id, "kind": self.kind, "params": dict(self.params)}


def derive_command_id(command: AgentCommand) -> str:
    content = {
        "kind": command.kind,
        "params": dict(command.params),
    }
    return "sha256:" + hashlib.sha256(canonical_json_bytes(content)).hexdigest()


# ---------------------------------------------------------------------------
# Integrity ledger and run results
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MutationRecord:
    """One authority mutation with before/after digests.

    Integrity is recorded around every mutating command so a run can be
    replayed and verified byte-for-byte (the WORK-031 discipline
    applied to a real node's runtime).
    """

    authority: str
    operation: str
    instant: str
    before_digest: str
    after_digest: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "authority": self.authority,
            "operation": self.operation,
            "instant": self.instant,
            "before_digest": self.before_digest,
            "after_digest": self.after_digest,
        }


class CommandVerdict:
    """Frozen command-outcome verdicts."""

    APPLIED = "applied"
    REJECTED = "rejected"
    FAILED = "failed"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.APPLIED, cls.REJECTED, cls.FAILED)


@dataclass(frozen=True)
class CommandOutcome:
    """The result envelope of one headless command."""

    command_id: str
    kind: str
    verdict: str
    detail: str = ""
    value: Optional[Any] = None
    mutations: Tuple[MutationRecord, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "kind": self.kind,
            "verdict": self.verdict,
            "detail": self.detail,
            "mutations": [record.to_dict() for record in self.mutations],
        }


@dataclass(frozen=True)
class AgentRunResult:
    """The result of one headless command-batch run."""

    status: str
    config_digest: str
    outcomes: Tuple[CommandOutcome, ...]
    event_digest: str
    trace_digest: str
    applied: int
    rejected: int
    failed: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "config_digest": self.config_digest,
            "outcomes": [outcome.to_dict() for outcome in self.outcomes],
            "event_digest": self.event_digest,
            "trace_digest": self.trace_digest,
            "applied": self.applied,
            "rejected": self.rejected,
            "failed": self.failed,
        }


class AgentStatus:
    """Frozen agent lifecycle status."""

    OFFLINE = "offline"
    ONLINE = "online"
    SHUTDOWN = "shutdown"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.OFFLINE, cls.ONLINE, cls.SHUTDOWN)


# ---------------------------------------------------------------------------
# Configuration (pure DATA)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AgentIdentitySpec:
    """Public identity material for the local node.

    The credential secret is NEVER part of configuration; it is injected
    separately at boot (LOCK-023 secret hygiene).
    """

    profile_id: str
    public_key: bytes
    created_at: str
    credential_role: str = "operational"

    def __post_init__(self) -> None:
        if not isinstance(self.public_key, (bytes, bytearray)) or not self.public_key:
            raise AgentError(
                AgentReasonCode.INVALID_INPUT, "public_key must be non-empty bytes"
            )
        if not isinstance(self.profile_id, str) or not self.profile_id:
            raise AgentError(
                AgentReasonCode.INVALID_INPUT, "profile_id must be a non-empty string"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "public_key_hex": bytes(self.public_key).hex(),
            "created_at": self.created_at,
            "credential_role": self.credential_role,
        }


@dataclass(frozen=True)
class LinkMetricSpec:
    """Explicit link metrics toward one peer (routing input DATA)."""

    peer_node_id: str
    latency_ms: int
    loss_basis_points: int = 0
    capacity_bps: int = 1_000_000
    energy_cost_millijoules: int = 100
    confidence_basis_points: int = 10_000
    observed_at: str = ""
    freshness_until: str = ""
    provenance: str = "agent:local-observation"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "peer_node_id": self.peer_node_id,
            "latency_ms": self.latency_ms,
            "loss_basis_points": self.loss_basis_points,
            "capacity_bps": self.capacity_bps,
            "energy_cost_millijoules": self.energy_cost_millijoules,
            "confidence_basis_points": self.confidence_basis_points,
            "observed_at": self.observed_at,
            "freshness_until": self.freshness_until,
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class MigrationSpec:
    """Declared reversible migration for agent-owned schema state."""

    schema_id: str
    from_version: str
    to_version: str
    reversible: bool = True
    breaking: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "reversible": self.reversible,
            "breaking": self.breaking,
        }


@dataclass(frozen=True)
class AgentConfig:
    """The full, pure-DATA configuration of one agent node.

    Family value objects carried here (policy rules, topology claims,
    role definitions) are frozen DATA of the composed authorities; the
    runtime publishes them through the owning authorities' contracts.
    """

    agent_label: str
    identity: AgentIdentitySpec
    policy_rules: Tuple[Any, ...] = ()
    policy_set_id: str = "agent-policy"
    policy_set_version: int = 1
    policy_default_effect: str = "deny"
    topology_claims: Tuple[Any, ...] = ()
    link_metrics: Tuple[LinkMetricSpec, ...] = ()
    rbac_roles: Tuple[Any, ...] = ()
    operator_role_ids: Tuple[str, ...] = ()
    software_version: Tuple[int, int, int] = (1, 0, 0)
    protocol_profile: Tuple[int, int] = (1, 0)
    schema_versions: Mapping[str, str] = field(default_factory=lambda: {"agent.state": "1.0"})
    schema_state: Mapping[str, Mapping[str, Any]] = field(
        default_factory=lambda: {"agent.state": {"format": 1}}
    )
    migration: Optional[MigrationSpec] = None
    credential_expires_at: Optional[str] = None
    telemetry_freshness_seconds: int = 600
    offer_expiry_seconds: int = 300

    def __post_init__(self) -> None:
        if not isinstance(self.agent_label, str) or not self.agent_label:
            raise AgentError(
                AgentReasonCode.INVALID_INPUT, "agent_label must be a non-empty string"
            )
        if len(self.software_version) != 3 or any(
            not isinstance(part, int) or part < 0 for part in self.software_version
        ):
            raise AgentError(
                AgentReasonCode.INVALID_INPUT,
                "software_version must be a (major, minor, patch) integer tuple",
            )
        if len(self.protocol_profile) != 2 or any(
            not isinstance(part, int) or part < 0 for part in self.protocol_profile
        ):
            raise AgentError(
                AgentReasonCode.INVALID_INPUT,
                "protocol_profile must be a (major, max_minor) integer tuple",
            )
        if self.telemetry_freshness_seconds <= 0 or self.offer_expiry_seconds <= 0:
            raise AgentError(
                AgentReasonCode.INVALID_INPUT, "expiry windows must be positive"
            )

    def to_dict(self) -> Dict[str, Any]:
        claims: List[Dict[str, Any]] = []
        for claim in self.topology_claims:
            to_dict = getattr(claim, "to_dict", None)
            claims.append(to_dict() if callable(to_dict) else {"claim_id": str(claim)})
        rules: List[Dict[str, Any]] = []
        for rule in self.policy_rules:
            to_dict = getattr(rule, "to_dict", None)
            rules.append(to_dict() if callable(to_dict) else {"rule_id": str(rule)})
        roles: List[Dict[str, Any]] = []
        for role in self.rbac_roles:
            to_dict = getattr(role, "to_dict", None)
            roles.append(to_dict() if callable(to_dict) else {"role_id": str(role)})
        return {
            "agent_label": self.agent_label,
            "identity": self.identity.to_dict(),
            "policy_rules": rules,
            "policy_set_id": self.policy_set_id,
            "policy_set_version": self.policy_set_version,
            "policy_default_effect": self.policy_default_effect,
            "topology_claims": claims,
            "link_metrics": [spec.to_dict() for spec in self.link_metrics],
            "rbac_roles": roles,
            "operator_role_ids": list(self.operator_role_ids),
            "software_version": list(self.software_version),
            "protocol_profile": list(self.protocol_profile),
            "schema_versions": dict(self.schema_versions),
            "schema_state": {
                key: dict(value) for key, value in self.schema_state.items()
            },
            "migration": self.migration.to_dict() if self.migration else None,
            "credential_expires_at": self.credential_expires_at,
            "telemetry_freshness_seconds": self.telemetry_freshness_seconds,
            "offer_expiry_seconds": self.offer_expiry_seconds,
        }

    def content_digest(self) -> str:
        return "sha256:" + hashlib.sha256(
            canonical_json_bytes(self.to_dict())
        ).hexdigest()


# ---------------------------------------------------------------------------
# Cross-agent session establishment artifacts (DATA handed between nodes)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SessionRequestArtifact:
    """Initiator -> responder session establishment request.

    Carries the initiator's accepted route decision and the policy
    decision it was computed under (both non-secret DATA), plus the
    transport offer.  The responder re-verifies through its own
    authorities before mirroring anything.
    """

    session_id: str
    source_node_id: str
    destination_node_id: str
    creation_instant: str
    intent_digest: str
    route_decision: Any
    policy_decision: Any
    offer: Any


@dataclass(frozen=True)
class SessionAcceptArtifact:
    """Responder -> initiator acceptance (session mirror + transport)."""

    session_id: str
    acceptance: Any


@dataclass(frozen=True)
class SessionConfirmArtifact:
    """Initiator -> responder confirmation (mutual authentication)."""

    session_id: str
    transport_id: str
    confirmation: Any


@dataclass(frozen=True)
class DatagramArtifact:
    """One protected transport frame handed between nodes as DATA."""

    session_id: str
    transport_id: str
    frame: Mapping[str, Any]


# ---------------------------------------------------------------------------
# Monitoring report ("metrics")
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MonitoringReport:
    """A composed, derived observability snapshot of one agent node.

    Assembled exclusively by reading the composed authorities (session
    store, transport manager, adapter runtime, telemetry store); the
    monitoring path never mutates authority state except by recording
    explicit telemetry observations through the W026 store contract.
    """

    generated_at: str
    sessions: Tuple[Dict[str, Any], ...]
    transports: Tuple[Dict[str, Any], ...]
    adapters: Tuple[Dict[str, Any], ...]
    recorded_observation_ids: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "sessions": [dict(item) for item in self.sessions],
            "transports": [dict(item) for item in self.transports],
            "adapters": [dict(item) for item in self.adapters],
            "recorded_observation_ids": list(self.recorded_observation_ids),
        }
