"""WORK-033 agent runtime: the Linux reference node's composition root.

The runtime OWNS isolated instances of the accepted authorities and
drives them exclusively through their public instant-injected
contracts.  It is a composition root, never a second authority:

- policy decisions are minted by the real WORK-010 engine;
- route decisions by the real WORK-011 engine;
- sessions by the real WORK-012 store;
- secure transport by the real WORK-017 manager;
- interfaces become adapters through the real WORK-016 SDK;
- IP integration through the real WORK-018 manager;
- metrics through the real WORK-026 store;
- version/capability truth through the real WORK-029 manager;
- privileged operations through the real WORK-030 API;
- contract self-verification through the real WORK-032 suite.

Time is injected through the clock seam; every authority call takes
explicit instants.  The append-only agent event log, the per-command
integrity ledger, and the trace digest make every headless run
replayable and byte-verifiable.
"""

from __future__ import annotations

import hashlib
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from protocol import canonical_json_bytes

from adapters import AdapterRuntime, derive_adapter_id
from adapters.ip import (
    IPIntegrationManager,
    SessionReader as IPSessionReader,
    SessionView as IPSessionView,
    TopologyReader as IPTopologyReader,
    IPv6Address,
)
from federation import FederationStore
from identity import (
    CredentialRecord,
    DevHmacSha256Provider,
    IdentityService,
    InMemoryCredentialStore,
    LifecycleState,
    NodeIdentity,
    ProfileSet,
)
from management import AuditLedger, ManagementAPI, RoleAssignmentStore
from policy import (
    DecisionCode,
    Effect,
    Operation,
    PolicyContext,
    PolicyDecision,
    PolicyEngine,
    PolicySet,
    PolicyStore,
)
from resources import ResourceStore
from routing import LinkMetrics, RouteDecision, RoutingContext, RoutingEngine
from sessions import SessionState
from sessions.store import SessionStore
from telemetry.store import TelemetryStore
from topology import TopologyGraph, make_link_subject
from transport import (
    SECURABLE_SESSION_STATES,
    ModeledTransportEngine,
    TransportManager,
    TransportSecurityPolicy,
    Work004IdentityAuthority,
    Work012SessionReader,
    default_profile_offers,
)
from upgrade.compatibility import coexistence_report
from upgrade.manager import UpgradeManager
from upgrade.migrations import MigrationRegistry
from upgrade.model import ProtocolProfile, SoftwareVersion, VersionInventory
from upgrade.serialization import version_inventory_from_dict

from conformance import (
    ConformanceWorld,
    Verdict,
    build_default_registry,
    report_digest,
    run_matrix,
)

from .bridge import InterfaceTechnologyAdapter, interface_descriptor, technology_for_snapshot
from .clock import AgentClock, add_seconds, parse_utc
from .errors import AgentError, AgentReasonCode
from .interfaces import InterfaceSource
from .model import (
    AgentCommand,
    AgentConfig,
    AgentEvent,
    AgentEventType,
    AgentRunResult,
    AgentStatus,
    CommandKind,
    CommandOutcome,
    CommandVerdict,
    DatagramArtifact,
    MonitoringReport,
    MutationRecord,
    SessionAcceptArtifact,
    SessionConfirmArtifact,
    SessionRequestArtifact,
    agent_events_canonical_bytes,
)

_BLOCKING_POLICY_CODES = frozenset(
    {
        DecisionCode.DENY,
        DecisionCode.FAIL_CLOSED,
        DecisionCode.CONFLICT,
        DecisionCode.INVALID_POLICY,
        DecisionCode.INVALID_SUBJECT,
        DecisionCode.UNSUPPORTED_PREDICATE,
    }
)

IP_INTEGRATION_ID = "adcos:ipint:agent"


def _plain(value: Any) -> Any:
    """Convert snapshot trees into canonical-JSON-safe structures."""
    if isinstance(value, dict):
        return {
            str(key): _plain(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    if hasattr(value, "to_dict"):
        return _plain(value.to_dict())
    return repr(value)


# ---------------------------------------------------------------------------
# WORK-018 reader adapters (the least-authority projections the agent owns)
# ---------------------------------------------------------------------------


class _AgentIPSessionReader(IPSessionReader):
    """Project the agent's real session store to the W018 view."""

    __slots__ = ("_store",)

    def __init__(self, store: SessionStore) -> None:
        self._store = store

    def lookup(self, session_id: str) -> Optional[IPSessionView]:
        session = self._store.get(session_id)
        if session is None:
            return None
        return IPSessionView(
            session_id=session.session_id,
            secureable=session.state in SECURABLE_SESSION_STATES,
            initiator_node_id=session.binding.source_node_id,
            responder_node_id=session.binding.destination_node_id,
        )


class _AgentIPTopologyReader(IPTopologyReader):
    """The agent's topology gateway view.

    The reference agent declares NO external gateway claims: unevidenced
    gateway authority is never minted (R3).  A deployment with evidenced
    gateway claims subclasses this reader.
    """

    __slots__ = ()

    def gateway_for(self, destination: IPv6Address) -> Optional[Any]:
        return None


# ---------------------------------------------------------------------------
# Agent-owned schema state migrations (pure dict-in/dict-out)
# ---------------------------------------------------------------------------


def _agent_state_forward(state: Mapping[str, Any]) -> Dict[str, Any]:
    out = dict(state)
    out["interface-accounting"] = True
    return out


def _agent_state_backward(state: Mapping[str, Any]) -> Dict[str, Any]:
    out = dict(state)
    out.pop("interface-accounting", None)
    return out


# ---------------------------------------------------------------------------
# The runtime
# ---------------------------------------------------------------------------


class AgentRuntime:
    """One ADCOS node as a Linux process: headless, data-driven,
    composed exclusively of accepted authorities."""

    def __init__(
        self,
        config: AgentConfig,
        *,
        clock: AgentClock,
        interface_source: InterfaceSource,
    ) -> None:
        if not isinstance(config, AgentConfig):
            raise AgentError(AgentReasonCode.INVALID_INPUT, "config must be an AgentConfig")
        self._config = config
        self._clock = clock
        self._interface_source = interface_source
        self._status = AgentStatus.OFFLINE

        # -- identity (WORK-004, transitive input of W017/W012) --------
        self._credential_store: InMemoryCredentialStore = InMemoryCredentialStore()
        self._provider: DevHmacSha256Provider = DevHmacSha256Provider()
        self._profiles: ProfileSet = ProfileSet.load_default()
        self._identity_service: IdentityService = IdentityService(
            self._credential_store, self._provider, self._profiles
        )
        profile = self._profiles.get(config.identity.profile_id)
        self._identity: NodeIdentity = NodeIdentity.create(
            profile, config.identity.public_key, config.identity.created_at
        )
        self._node_id = self._identity.node_id.text

        # -- isolated REAL authorities ----------------------------------
        self._topology: TopologyGraph = TopologyGraph()
        self._resources: ResourceStore = ResourceStore()
        self._policy_store: PolicyStore = PolicyStore()
        self._policy_engine: PolicyEngine = PolicyEngine()
        self._routing_engine: RoutingEngine = RoutingEngine()
        self._sessions: SessionStore = SessionStore()
        self._telemetry: TelemetryStore = TelemetryStore()
        self._federation: FederationStore = FederationStore()
        self._adapters_runtime: AdapterRuntime = AdapterRuntime(session_store=self._sessions)
        self._transport: TransportManager = TransportManager(
            session_reader=Work012SessionReader(self._sessions),
            identity=Work004IdentityAuthority(
                self._identity_service, self._provider, self._credential_store
            ),
            implementation=ModeledTransportEngine(),
        )
        self._ip: IPIntegrationManager = IPIntegrationManager(
            session_reader=_AgentIPSessionReader(self._sessions),
            topology_reader=_AgentIPTopologyReader(),
            integration_id=IP_INTEGRATION_ID,
        )
        self._ip_opened = False

        self._migration_registry: MigrationRegistry = MigrationRegistry()
        if config.migration is not None:
            self._migration_registry.register_step(
                config.migration.schema_id,
                config.migration.from_version,
                config.migration.to_version,
                reversible=config.migration.reversible,
                breaking=config.migration.breaking,
                forward=_agent_state_forward,
                backward=_agent_state_backward,
            )
        self._upgrade: UpgradeManager = UpgradeManager(
            node_id=self._node_id,
            software_version=SoftwareVersion(*config.software_version),
            protocol_profile=ProtocolProfile(*config.protocol_profile),
            schema_versions=dict(config.schema_versions),
            schema_state={
                schema_id: dict(state)
                for schema_id, state in config.schema_state.items()
            },
            migration_registry=self._migration_registry,
            telemetry_store=self._telemetry,
        )

        self._role_store: RoleAssignmentStore = RoleAssignmentStore(roles=tuple(config.rbac_roles))
        self._audit: AuditLedger = AuditLedger()
        self._management: ManagementAPI = ManagementAPI(
            policy_store=self._policy_store,
            session_store=self._sessions,
            federation_store=self._federation,
            telemetry_store=self._telemetry,
            role_store=self._role_store,
            audit=self._audit,
            routing_engine=self._routing_engine,
        )

        # -- runtime state ----------------------------------------------
        self._events: List[AgentEvent] = []
        self._event_sequence = 0
        self._adapter_interfaces: Dict[str, str] = {}
        self._telemetry_sequences: Dict[Tuple[str, str, str], int] = {}
        self._session_transports: Dict[str, str] = {}
        self._session_routes: Dict[str, RouteDecision] = {}
        self._pending_handles: Dict[str, str] = {}
        self._credential_active = False

    # ------------------------------------------------------------------
    # Read-only composition surface
    # ------------------------------------------------------------------

    @property
    def config(self) -> AgentConfig:
        return self._config

    @property
    def status(self) -> str:
        return self._status

    @property
    def node_id(self) -> str:
        return self._node_id

    @property
    def identity(self) -> NodeIdentity:
        """The local node's public identity material (no secrets)."""
        return self._identity

    @property
    def identity_service(self) -> IdentityService:
        return self._identity_service

    @property
    def sessions(self) -> SessionStore:
        return self._sessions

    @property
    def policy_store(self) -> PolicyStore:
        return self._policy_store

    @property
    def topology(self) -> TopologyGraph:
        return self._topology

    @property
    def resources(self) -> ResourceStore:
        return self._resources

    @property
    def telemetry(self) -> TelemetryStore:
        return self._telemetry

    @property
    def federation(self) -> FederationStore:
        return self._federation

    @property
    def adapters_runtime(self) -> AdapterRuntime:
        return self._adapters_runtime

    @property
    def transport_manager(self) -> TransportManager:
        return self._transport

    @property
    def ip_manager(self) -> IPIntegrationManager:
        return self._ip

    @property
    def upgrade_manager(self) -> UpgradeManager:
        return self._upgrade

    @property
    def management_api(self) -> ManagementAPI:
        return self._management

    @property
    def interface_source(self) -> InterfaceSource:
        return self._interface_source

    def events(self) -> Tuple[AgentEvent, ...]:
        return tuple(self._events)

    def event_log_digest(self) -> str:
        return "sha256:" + hashlib.sha256(
            agent_events_canonical_bytes(self._events)
        ).hexdigest()

    def snapshot(self) -> Dict[str, Any]:
        """A secret-free deterministic snapshot of the composed node."""
        return {
            "agent_label": self._config.agent_label,
            "node_id": self._node_id,
            "status": self._status,
            "config_digest": self._config.content_digest(),
            "event_count": len(self._events),
            "event_log_digest": self.event_log_digest(),
            "adapter_interfaces": dict(self._adapter_interfaces),
            "session_transports": dict(self._session_transports),
            "authority_digests": self._authority_digests(),
        }

    def content_digest(self) -> str:
        return "sha256:" + hashlib.sha256(
            canonical_json_bytes(self.snapshot())
        ).hexdigest()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _now(self) -> str:
        return self._clock.now()

    def _instant_after(self, instant: str, seconds: int) -> str:
        return add_seconds(instant, seconds)

    def _next_sequence(self, subject_kind: str, subject_ref: str, metric: str) -> int:
        key = (subject_kind, subject_ref, metric)
        self._telemetry_sequences[key] = self._telemetry_sequences.get(key, 0) + 1
        return self._telemetry_sequences[key]

    def _interface_for_adapter(self, adapter_id: str) -> str:
        return self._adapter_interfaces.get(adapter_id, adapter_id)

    def _record_event(
        self, kind: str, subject: str, detail: str, command_ref: str = ""
    ) -> AgentEvent:
        self._event_sequence += 1
        event = AgentEvent(
            kind=kind,
            sequence=self._event_sequence,
            instant=self._now(),
            subject=subject,
            detail=detail,
            command_ref=command_ref,
        )
        self._events.append(event)
        return event

    def _require_online(self) -> None:
        if self._status == AgentStatus.OFFLINE:
            raise AgentError(AgentReasonCode.NOT_BOOTED, "the agent has not booted")
        if self._status == AgentStatus.SHUTDOWN:
            raise AgentError(AgentReasonCode.ALREADY_SHUTDOWN, "the agent has shut down")

    def _authority_digests(self) -> Dict[str, str]:
        def _digest_bytes(payload: bytes) -> str:
            return "sha256:" + hashlib.sha256(payload).hexdigest()

        def _digest_snapshot(payload: Any) -> str:
            return "sha256:" + hashlib.sha256(
                canonical_json_bytes(_plain(payload))
            ).hexdigest()

        return {
            "sessions": _digest_bytes(self._sessions.to_canonical_bytes()),
            "topology": _digest_snapshot(self._topology.snapshot()),
            "resources": _digest_snapshot(self._resources.snapshot()),
            "policy": _digest_snapshot(self._policy_store.snapshot()),
            "telemetry": _digest_snapshot(self._telemetry.snapshot()),
            "federation": _digest_snapshot(self._federation.snapshot()),
            "adapters": _digest_bytes(self._adapters_runtime.to_canonical_bytes()),
            "transport": _digest_bytes(self._transport.to_canonical_bytes()),
            "ip": _digest_bytes(self._ip.to_canonical_bytes()),
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def boot(self, secret: bytes) -> None:
        """Provision the node credential and publish configured policy.

        The credential secret enters ONLY the WORK-004 credential store;
        it never appears in configuration, events, or snapshots.
        """
        if self._status != AgentStatus.OFFLINE:
            raise AgentError(AgentReasonCode.ALREADY_BOOTED, "the agent already booted")
        now = self._now()
        reference = self._identity_service.provision(
            self._identity,
            self._config.identity.credential_role,
            secret,
            now=now,
            expires_at=self._config.credential_expires_at,
            provenance="local",
        )
        self._identity_service.activate(reference, now=now)
        self._credential_active = True

        policy_set = PolicySet(
            set_id=self._config.policy_set_id,
            version=self._config.policy_set_version,
            rules=tuple(self._config.policy_rules),
            default_effect=(
                Effect.ALLOW
                if self._config.policy_default_effect == "allow"
                else Effect.DENY
            ),
            issuer_node_id=self._node_id,
        )
        self._policy_store.publish(policy_set)

        for claim in self._config.topology_claims:
            self._topology.merge(claim)

        for role_id in self._config.operator_role_ids:
            self._role_store.grant(
                self._node_id,
                role_id,
                instant=now,
                actor_node_id=self._node_id,
                reason="agent boot operator role",
            )

        self._status = AgentStatus.ONLINE
        self._record_event(
            AgentEventType.BOOTED,
            self._node_id,
            "credential provisioned; policy published; %d topology claims merged"
            % len(self._config.topology_claims),
        )
        self._record_event(
            AgentEventType.POLICY_PUBLISHED,
            self._config.policy_set_id,
            "version %d, %d rules, default %s"
            % (
                self._config.policy_set_version,
                len(self._config.policy_rules),
                self._config.policy_default_effect,
            ),
        )

    def register_peer(
        self,
        peer_identity: NodeIdentity,
        credential_record: CredentialRecord,
        verification_material: Optional[bytes] = None,
    ) -> None:
        """Install a peer's public identity + credential as a trust anchor.

        ``verification_material`` is the out-of-band verification secret
        required by the symmetric development identity profile (a PSK-
        shaped deployment); asymmetric production providers verify with
        public material alone and pass ``None``.
        """
        self._require_online()
        if not isinstance(peer_identity, NodeIdentity):
            raise AgentError(AgentReasonCode.PEER_INVALID, "peer identity must be a NodeIdentity")
        if not isinstance(credential_record, CredentialRecord):
            raise AgentError(
                AgentReasonCode.PEER_INVALID, "credential record must be a CredentialRecord"
            )
        if credential_record.node_id.text != peer_identity.node_id.text:
            raise AgentError(
                AgentReasonCode.PEER_INVALID,
                "credential record does not belong to the peer identity",
            )
        if peer_identity.node_id.text == self._node_id:
            raise AgentError(
                AgentReasonCode.PEER_INVALID, "the local node is not a peer"
            )
        if credential_record.status is not LifecycleState.ACTIVE:
            raise AgentError(
                AgentReasonCode.PEER_INVALID,
                "peer credential record must be ACTIVE (status %s)"
                % getattr(credential_record.status, "value", str(credential_record.status)),
            )
        self._credential_store.put_record(credential_record)
        if verification_material is not None:
            self._credential_store.put_secret(
                credential_record.reference, verification_material
            )
        self._record_event(
            AgentEventType.PEER_REGISTERED,
            peer_identity.node_id.text,
            "peer credential installed (role %s, generation %d)"
            % (credential_record.role, credential_record.key_version),
        )

    def expose_interfaces(self) -> Tuple[str, ...]:
        """Discover network interfaces and expose each as an adapter."""
        self._require_online()
        now = self._now()
        try:
            snapshots = self._interface_source.discover()
        except Exception as error:
            raise AgentError(
                AgentReasonCode.INTERFACE_SOURCE_FAILED,
                "interface discovery failed (%s)" % type(error).__name__,
            ) from error
        registered: List[str] = []
        for snapshot in snapshots:
            self._record_event(
                AgentEventType.INTERFACE_DISCOVERED,
                snapshot.name,
                "kind %s, up=%s, mtu %d"
                % (snapshot.link_kind, snapshot.state_up, snapshot.mtu),
            )
            adapter_id = derive_adapter_id(
                technology_for_snapshot(snapshot), snapshot.name
            )
            if adapter_id in self._adapter_interfaces:
                continue  # idempotent re-exposure
            descriptor = interface_descriptor(snapshot, adapter_id)
            implementation = InterfaceTechnologyAdapter(self._interface_source, snapshot.name)
            self._adapters_runtime.register(descriptor, implementation, now=now)
            self._adapter_interfaces[adapter_id] = snapshot.name
            self._record_event(
                AgentEventType.ADAPTER_REGISTERED,
                adapter_id,
                "interface %s as %s" % (snapshot.name, descriptor.access_technology_id),
            )
            open_result = self._adapters_runtime.open_adapter(adapter_id, now=now)
            if not open_result.ok:
                raise AgentError(
                    AgentReasonCode.ADAPTER_CONFLICT,
                    "adapter open failed for %s: %s"
                    % (adapter_id, getattr(open_result.failure, "reason", "unknown")),
                )
            self._record_event(AgentEventType.ADAPTER_OPENED, adapter_id, "interface adapter open")
            registered.append(adapter_id)
        return tuple(registered)

    def shutdown(self) -> None:
        """Close transports and adapters; the node goes offline."""
        self._require_online()
        now = self._now()
        for transport_id in self._transport.transports():
            self._transport.close(transport_id, now=now, reason="agent shutdown")
            self._record_event(AgentEventType.TRANSPORT_CLOSED, transport_id, "agent shutdown")
        self._adapters_runtime.reconcile_sessions(now=now)
        for adapter_id in self._adapters_runtime.adapter_ids():
            close_result = self._adapters_runtime.close_adapter(adapter_id, now=now)
            if not close_result.ok:
                raise AgentError(
                    AgentReasonCode.ADAPTER_CONFLICT,
                    "adapter close failed for %s (outstanding state): %s"
                    % (adapter_id, getattr(close_result.failure, "reason", "unknown")),
                )
            self._record_event(AgentEventType.ADAPTER_CLOSED, adapter_id, "agent shutdown")
        if self._ip_opened:
            for session_id in sorted(self._session_transports):
                self._close_ip_binding(session_id, now)
            self._ip.close(now=now)
            self._ip_opened = False
        self._status = AgentStatus.SHUTDOWN
        self._record_event(AgentEventType.SHUTDOWN, self._node_id, "agent shutdown complete")

    # ------------------------------------------------------------------
    # Session establishment (the genuine chain, composed)
    # ------------------------------------------------------------------

    def _policy_gate(self, operation: str, requester_node_id: str, now: str) -> PolicyDecision:
        """Evaluate the REAL policy engine (deny-by-default)."""
        context = PolicyContext(
            operation=operation,
            requester_node_id=requester_node_id,
            credential_active=True,
            evaluation_instant=now,
        )
        applicable = self._policy_store.list_applicable(now)
        if not applicable:
            raise AgentError(
                AgentReasonCode.POLICY_REJECTED,
                "deny-by-default: no applicable policy set",
            )
        allow_decision: Optional[PolicyDecision] = None
        for policy_set in applicable:
            result = self._policy_engine.evaluate(policy_set, context)
            if result.code in _BLOCKING_POLICY_CODES:
                raise AgentError(
                    AgentReasonCode.POLICY_REJECTED,
                    "policy %s@%d blocks (%s)"
                    % (policy_set.set_id, policy_set.version, result.code),
                )
            if result.code == DecisionCode.ALLOW and allow_decision is None:
                if result.decision is not None:
                    allow_decision = result.decision
        if allow_decision is None:
            raise AgentError(
                AgentReasonCode.POLICY_REJECTED,
                "deny-by-default: no explicit allow decision",
            )
        return allow_decision

    def _link_metrics(self, now: str) -> Dict[str, LinkMetrics]:
        metrics: Dict[str, LinkMetrics] = {}
        for spec in self._config.link_metrics:
            subject = make_link_subject(self._node_id, spec.peer_node_id)
            metrics[subject] = LinkMetrics(
                latency_ms=spec.latency_ms,
                loss_basis_points=spec.loss_basis_points,
                capacity_bps=spec.capacity_bps,
                energy_cost_millijoules=spec.energy_cost_millijoules,
                confidence_basis_points=spec.confidence_basis_points,
                observed_at=spec.observed_at or now,
                freshness_until=spec.freshness_until
                or self._instant_after(now, self._config.telemetry_freshness_seconds),
                provenance=spec.provenance,
            )
        return metrics

    def _evaluate_route(
        self, source: str, destination: str, decision: PolicyDecision, now: str
    ) -> RouteDecision:
        context = RoutingContext(
            source_node_id=source,
            destination_node_id=destination,
            topology=self._topology,
            resources=self._resources,
            evaluation_instant=now,
            policy_decision=decision,
            link_metrics=self._link_metrics(now),
        )
        result = self._routing_engine.evaluate(context)
        if result.decision is None or result.decision.selected is None:
            raise AgentError(
                AgentReasonCode.ROUTE_UNAVAILABLE,
                "no feasible route %s -> %s (%s)"
                % (source, destination, getattr(result, "code", "unavailable")),
            )
        return result.decision

    def establish_session(
        self, destination_node_id: str, *, intent_digest: str = ""
    ) -> SessionRequestArtifact:
        """The initiator chain: policy -> route -> session -> transport offer."""
        self._require_online()
        now = self._now()
        decision = self._policy_gate(Operation.SESSION_CREATE, self._node_id, now)
        route = self._evaluate_route(self._node_id, destination_node_id, decision, now)
        created = self._sessions.create(
            route,
            decision,
            source_node_id=self._node_id,
            destination_node_id=destination_node_id,
            creation_instant=now,
            intent_digest=intent_digest,
            actor_reference="agent:%s" % self._config.agent_label,
        )
        if not created.ok or created.session is None:
            raise AgentError(
                AgentReasonCode.SESSION_REJECTED,
                "session create rejected: %s" % created.code,
            )
        session_id = created.session.session_id
        self._sessions.transition(session_id, SessionState.AUTHORIZED, event_instant=now)
        self._sessions.transition(session_id, SessionState.ESTABLISHED, event_instant=now)
        self._session_routes[session_id] = route

        transport_policy = TransportSecurityPolicy(
            require_integrity=True,
            require_confidentiality=True,
            require_forward_secrecy=True,
        )
        offer_result = self._transport.establish_initiator(
            session_id,
            policy=transport_policy,
            offered_profiles=list(default_profile_offers()),
            now=now,
            instance_label="agent-%s" % self._config.agent_label,
            offer_expires_at=self._instant_after(now, self._config.offer_expiry_seconds),
        )
        if not offer_result.ok or offer_result.value is None:
            raise AgentError(
                AgentReasonCode.TRANSPORT_REJECTED,
                "transport initiation rejected: %s" % offer_result.reason,
            )
        offer = offer_result.value
        handles = self._transport.pending_handles()
        if handles:
            self._pending_handles[session_id] = handles[-1]
        self._record_event(
            AgentEventType.SESSION_REQUESTED,
            session_id,
            "initiator -> %s under policy %s" % (destination_node_id, decision.decision_id[:16]),
        )
        return SessionRequestArtifact(
            session_id=session_id,
            source_node_id=self._node_id,
            destination_node_id=destination_node_id,
            creation_instant=now,
            intent_digest=intent_digest,
            route_decision=route,
            policy_decision=decision,
            offer=offer,
        )

    def accept_session(self, request: SessionRequestArtifact) -> SessionAcceptArtifact:
        """The responder chain: local policy gate -> mirrored session ->
        transport acceptance.  Fail-closed on any gate."""
        self._require_online()
        if not isinstance(request, SessionRequestArtifact):
            raise AgentError(
                AgentReasonCode.INVALID_INPUT, "request must be a SessionRequestArtifact"
            )
        if request.destination_node_id != self._node_id:
            raise AgentError(
                AgentReasonCode.INVALID_INPUT,
                "this node is not the requested destination",
            )
        if request.source_node_id == self._node_id:
            raise AgentError(
                AgentReasonCode.INVALID_INPUT, "session endpoints must differ"
            )
        now = self._now()
        decision = self._policy_gate(
            Operation.SESSION_CREATE, request.source_node_id, now
        )
        del decision  # the responder gate is allow-only: a DENY/invalid
        # policy raises above; the mirrored session references the
        # INITIATOR's accepted decisions, per the WORK-012 reference
        # contract (sessions never re-decide policy).

        mirrored = self._sessions.create(
            request.route_decision,
            request.policy_decision,
            source_node_id=request.source_node_id,
            destination_node_id=self._node_id,
            creation_instant=request.creation_instant,
            intent_digest=request.intent_digest,
            actor_reference="agent:%s" % self._config.agent_label,
        )
        if not mirrored.ok or mirrored.session is None:
            raise AgentError(
                AgentReasonCode.SESSION_REJECTED,
                "mirror session rejected: %s" % mirrored.code,
            )
        session_id = mirrored.session.session_id
        if session_id != request.session_id:
            raise AgentError(
                AgentReasonCode.SESSION_REJECTED,
                "mirrored session id diverged from the request",
            )
        self._sessions.transition(session_id, SessionState.AUTHORIZED, event_instant=now)
        self._sessions.transition(session_id, SessionState.ESTABLISHED, event_instant=now)
        self._session_routes[session_id] = request.route_decision

        acceptance_result = self._transport.respond(
            request.offer,
            now=now,
            instance_label="agent-%s" % self._config.agent_label,
        )
        if not acceptance_result.ok or acceptance_result.value is None:
            raise AgentError(
                AgentReasonCode.TRANSPORT_REJECTED,
                "transport respond rejected: %s" % acceptance_result.reason,
            )
        acceptance = acceptance_result.value
        self._record_event(
            AgentEventType.SESSION_ACCEPTED,
            session_id,
            "mirrored session accepted from %s" % request.source_node_id,
        )
        return SessionAcceptArtifact(session_id=session_id, acceptance=acceptance)

    def complete_session(self, accept: SessionAcceptArtifact) -> SessionConfirmArtifact:
        """Initiator leg 3: verify the responder, complete the handshake."""
        self._require_online()
        if not isinstance(accept, SessionAcceptArtifact):
            raise AgentError(
                AgentReasonCode.INVALID_INPUT, "accept must be a SessionAcceptArtifact"
            )
        now = self._now()
        handle = self._pending_handles.get(accept.session_id)
        if handle is None:
            raise AgentError(
                AgentReasonCode.TRANSPORT_REJECTED,
                "no pending handshake for session %s" % accept.session_id,
            )
        confirmation_result = self._transport.complete_initiator(
            handle, accept.acceptance, now=now
        )
        if not confirmation_result.ok or confirmation_result.value is None:
            raise AgentError(
                AgentReasonCode.TRANSPORT_REJECTED,
                "transport completion rejected: %s" % confirmation_result.reason,
            )
        confirmation = confirmation_result.value
        transport_id = getattr(accept.acceptance, "transport_id", "")
        self._session_transports[accept.session_id] = transport_id
        self._pending_handles.pop(accept.session_id, None)
        self._record_event(
            AgentEventType.TRANSPORT_ESTABLISHED,
            transport_id,
            "initiator confirmed session %s" % accept.session_id,
        )
        return SessionConfirmArtifact(
            session_id=accept.session_id,
            transport_id=transport_id,
            confirmation=confirmation,
        )

    def finalize_session(self, confirm: SessionConfirmArtifact) -> None:
        """Responder leg 4: mutual authentication complete."""
        self._require_online()
        if not isinstance(confirm, SessionConfirmArtifact):
            raise AgentError(
                AgentReasonCode.INVALID_INPUT, "confirm must be a SessionConfirmArtifact"
            )
        now = self._now()
        confirmation_result = self._transport.confirm(
            confirm.transport_id, confirm.confirmation, now=now
        )
        if not confirmation_result.ok:
            raise AgentError(
                AgentReasonCode.TRANSPORT_REJECTED,
                "transport confirm rejected: %s" % confirmation_result.reason,
            )
        self._session_transports[confirm.session_id] = confirm.transport_id
        self._record_event(
            AgentEventType.SESSION_ESTABLISHED,
            confirm.session_id,
            "responder confirmed transport %s" % confirm.transport_id,
        )

    def bind_session(
        self, session_id: str, *, interface_name: Optional[str] = None
    ) -> Dict[str, str]:
        """Bind an established session to an interface adapter + IP flow."""
        self._require_online()
        now = self._now()
        if session_id not in self._session_transports:
            raise AgentError(
                AgentReasonCode.BINDING_REJECTED,
                "no established transport for session %s" % session_id,
            )
        route = self._session_routes.get(session_id)
        if route is None:
            raise AgentError(
                AgentReasonCode.BINDING_REJECTED,
                "no retained route decision for session %s" % session_id,
            )
        adapter_id = self._select_adapter(interface_name)
        binding = self._adapters_runtime.bind_session(
            adapter_id, session_id=session_id, now=now
        )
        if not binding.ok or binding.value is None:
            raise AgentError(
                AgentReasonCode.BINDING_REJECTED,
                "adapter bind rejected: %s"
                % getattr(binding.failure, "reason", "unknown"),
            )
        if not self._ip_opened:
            opened = self._ip.open(now=now)
            if not opened.ok:
                raise AgentError(
                    AgentReasonCode.BINDING_REJECTED,
                    "ip integration open failed: %s" % opened.reason,
                )
            self._ip_opened = True
        ip_binding = self._ip.bind_session(
            session_id=session_id,
            transport_ref=self._session_transports[session_id],
            route_ref=route.decision_id,
            now=now,
        )
        if not ip_binding.ok or ip_binding.value is None:
            raise AgentError(
                AgentReasonCode.BINDING_REJECTED,
                "ip binding rejected: %s" % ip_binding.reason,
            )
        self._record_event(
            AgentEventType.SESSION_BOUND,
            session_id,
            "bound to adapter %s (bearer %s)"
            % (adapter_id, binding.value.bearer_ref),
        )
        return {
            "adapter_id": adapter_id,
            "binding_id": binding.value.binding_id,
            "bearer_ref": binding.value.bearer_ref,
            "ip_binding_id": ip_binding.value.binding_id,
        }

    def _select_adapter(self, interface_name: Optional[str]) -> str:
        if interface_name is not None:
            for adapter_id, name in sorted(self._adapter_interfaces.items()):
                if name == interface_name:
                    return adapter_id
            raise AgentError(
                AgentReasonCode.BINDING_REJECTED,
                "no adapter exposed for interface %r" % interface_name,
            )
        for adapter_id in self._adapters_runtime.adapter_ids():
            if self._adapters_runtime.lifecycle(adapter_id) == "OPEN":
                return adapter_id
        raise AgentError(
            AgentReasonCode.BINDING_REJECTED, "no open adapter available"
        )

    def send_datagram(self, session_id: str, payload: bytes) -> DatagramArtifact:
        """Protect and send one datagram over the session's transport."""
        self._require_online()
        transport_id = self._session_transports.get(session_id)
        if transport_id is None:
            raise AgentError(
                AgentReasonCode.TRANSPORT_REJECTED,
                "no transport for session %s" % session_id,
            )
        now = self._now()
        result = self._transport.send(transport_id, payload, now=now)
        if not result.ok or result.value is None:
            raise AgentError(
                AgentReasonCode.TRANSPORT_REJECTED,
                "send rejected: %s" % result.reason,
            )
        return DatagramArtifact(
            session_id=session_id, transport_id=transport_id, frame=result.value
        )

    def receive_datagram(self, artifact: DatagramArtifact) -> bytes:
        """Receive and unprotect one datagram from the peer."""
        self._require_online()
        if not isinstance(artifact, DatagramArtifact):
            raise AgentError(
                AgentReasonCode.INVALID_INPUT, "artifact must be a DatagramArtifact"
            )
        now = self._now()
        result = self._transport.receive(artifact.transport_id, artifact.frame, now=now)
        if not result.ok or result.value is None:
            raise AgentError(
                AgentReasonCode.TRANSPORT_REJECTED,
                "receive rejected: %s" % result.reason,
            )
        payload = result.value
        if not isinstance(payload, (bytes, bytearray)):
            raise AgentError(
                AgentReasonCode.TRANSPORT_REJECTED,
                "unprotected payload is not bytes",
            )
        return bytes(payload)

    def suspend_session(self, session_id: str) -> None:
        self._require_online()
        now = self._now()
        transport_id = self._session_transports.get(session_id)
        if transport_id is not None:
            result = self._transport.suspend(transport_id, now=now, reason="agent suspend")
            if not result.ok:
                raise AgentError(
                    AgentReasonCode.TRANSPORT_REJECTED,
                    "transport suspend rejected: %s" % result.reason,
                )
        suspended = self._sessions.suspend(
            session_id, event_instant=now, actor_reference="agent:%s" % self._config.agent_label
        )
        if not suspended.ok:
            raise AgentError(
                AgentReasonCode.SESSION_REJECTED,
                "session suspend rejected: %s" % suspended.code,
            )
        self._adapters_runtime.reconcile_sessions(now=now)
        self._record_event(AgentEventType.SESSION_SUSPENDED, session_id, "suspended")

    def _close_ip_binding(self, session_id: str, now: str) -> None:
        """Release the session's IP flow binding (if any)."""
        binding = self._ip.binding_for_session(session_id)
        if binding is None:
            return
        result = self._ip.close_binding(ip_binding_ref=binding.binding_id, now=now)
        if not result.ok:
            raise AgentError(
                AgentReasonCode.BINDING_REJECTED,
                "ip binding close rejected: %s" % result.reason,
            )

    def terminate_session(self, session_id: str) -> None:
        self._require_online()
        now = self._now()
        transport_id = self._session_transports.get(session_id)
        if transport_id is not None:
            result = self._transport.close(transport_id, now=now, reason="agent terminate")
            if not result.ok:
                raise AgentError(
                    AgentReasonCode.TRANSPORT_REJECTED,
                    "transport close rejected: %s" % result.reason,
                )
            self._record_event(AgentEventType.TRANSPORT_CLOSED, transport_id, "session terminated")
        terminated = self._sessions.terminate(
            session_id, event_instant=now, actor_reference="agent:%s" % self._config.agent_label
        )
        if not terminated.ok:
            raise AgentError(
                AgentReasonCode.SESSION_REJECTED,
                "session terminate rejected: %s" % terminated.code,
            )
        self._adapters_runtime.reconcile_sessions(now=now)
        self._close_ip_binding(session_id, now)
        self._record_event(AgentEventType.SESSION_TERMINATED, session_id, "terminated")

    # ------------------------------------------------------------------
    # Monitoring (logs/metrics by composition)
    # ------------------------------------------------------------------

    def monitor(self, *, record: bool = True) -> MonitoringReport:
        self._require_online()
        from .monitoring import collect_monitoring_report

        now = self._now()
        report = collect_monitoring_report(self, now, record=record)
        if record and report.recorded_observation_ids:
            self._record_event(
                AgentEventType.OBSERVATION_RECORDED,
                self._node_id,
                "%d observations recorded" % len(report.recorded_observation_ids),
            )
        return report

    # ------------------------------------------------------------------
    # Version/capability negotiation (WORK-029 composition)
    # ------------------------------------------------------------------

    def negotiate_peer(
        self,
        peer_inventory: VersionInventory,
        *,
        peer_statements: Sequence[Any] = (),
        requirements: Sequence[Any] = (),
    ) -> Any:
        """Fail-closed capability negotiation with a peer inventory."""
        self._require_online()
        if not isinstance(peer_inventory, VersionInventory):
            raise AgentError(
                AgentReasonCode.INVALID_INPUT,
                "peer_inventory must be a VersionInventory",
            )
        return coexistence_report(
            self._upgrade.inventory(),
            peer_inventory,
            peer_statements=tuple(peer_statements),
            requirements=tuple(requirements),
            now=parse_utc(self._now()),
        )

    # ------------------------------------------------------------------
    # Conformance self-test (WORK-032 composition)
    # ------------------------------------------------------------------

    def self_test(self) -> Dict[str, Any]:
        """Run the accepted conformance matrix against the frozen contracts.

        The agent is a VERIFIER here, never an authority: the matrix and
        its world come entirely from the accepted WORK-032 suite.
        """
        self._require_online()
        registry = build_default_registry()
        report = run_matrix(registry.canonical_vectors(), ConformanceWorld)
        digest = report_digest(report)
        summary = {
            "verdict": report.verdict.value
            if hasattr(report.verdict, "value")
            else str(report.verdict),
            "total": report.total,
            "conformant": report.conformant,
            "nonconformant": report.nonconformant,
            "digest": digest,
        }
        self._record_event(
            AgentEventType.SELF_TEST_COMPLETED,
            self._node_id,
            "conformance matrix %s (%d vectors, digest %s)"
            % (summary["verdict"], report.total, digest[:23]),
        )
        if report.verdict is not Verdict.CONFORMANT:
            raise AgentError(
                AgentReasonCode.CONFORMANCE_FAILED,
                "conformance self-test nonconformant (%d vectors)" % report.nonconformant,
            )
        return summary

    # ------------------------------------------------------------------
    # Headless command execution
    # ------------------------------------------------------------------

    def execute(
        self, commands: Sequence[AgentCommand], *, boot_secret: Optional[bytes] = None
    ) -> AgentRunResult:
        """Execute a headless command batch with an integrity ledger."""
        outcomes: List[CommandOutcome] = []
        applied = rejected = failed = 0
        for command in commands:
            if not isinstance(command, AgentCommand):
                raise AgentError(
                    AgentReasonCode.INVALID_INPUT, "commands must be AgentCommand values"
                )
            before = self._authority_digests()
            command_now = self._now()
            try:
                value = self._dispatch(command, boot_secret)
                after = self._authority_digests()
                mutations = tuple(
                    MutationRecord(
                        authority=authority,
                        operation=command.kind,
                        instant=command_now,
                        before_digest=before[authority],
                        after_digest=after[authority],
                    )
                    for authority in sorted(before)
                    if before[authority] != after[authority]
                )
                outcomes.append(
                    CommandOutcome(
                        command_id=command.command_id,
                        kind=command.kind,
                        verdict=CommandVerdict.APPLIED,
                        detail="ok",
                        value=value,
                        mutations=mutations,
                    )
                )
                applied += 1
                self._record_event(
                    AgentEventType.COMMAND_APPLIED,
                    command.command_id,
                    "%s applied (%d authority mutations)"
                    % (command.kind, len(mutations)),
                    command_ref=command.command_id,
                )
            except AgentError as error:
                outcomes.append(
                    CommandOutcome(
                        command_id=command.command_id,
                        kind=command.kind,
                        verdict=CommandVerdict.REJECTED,
                        detail="%s: %s" % (error.reason, error.detail),
                    )
                )
                rejected += 1
                self._record_event(
                    AgentEventType.COMMAND_REJECTED,
                    command.command_id,
                    "%s rejected (%s)" % (command.kind, error.reason),
                    command_ref=command.command_id,
                )
            except Exception as error:  # LOCK-023: class name only
                outcomes.append(
                    CommandOutcome(
                        command_id=command.command_id,
                        kind=command.kind,
                        verdict=CommandVerdict.FAILED,
                        detail=type(error).__name__,
                    )
                )
                failed += 1
                self._record_event(
                    AgentEventType.COMMAND_FAILED,
                    command.command_id,
                    "%s failed (%s)" % (command.kind, type(error).__name__),
                    command_ref=command.command_id,
                )
        trace_digest = "sha256:" + hashlib.sha256(
            canonical_json_bytes(
                {
                    "config_digest": self._config.content_digest(),
                    "outcomes": [outcome.to_dict() for outcome in outcomes],
                    "event_log_digest": self.event_log_digest(),
                }
            )
        ).hexdigest()
        return AgentRunResult(
            status=self._status,
            config_digest=self._config.content_digest(),
            outcomes=tuple(outcomes),
            event_digest=self.event_log_digest(),
            trace_digest=trace_digest,
            applied=applied,
            rejected=rejected,
            failed=failed,
        )

    def _dispatch(
        self, command: AgentCommand, boot_secret: Optional[bytes]
    ) -> Optional[Any]:
        params = command.params
        kind = command.kind
        if kind == CommandKind.BOOT:
            if boot_secret is None:
                raise AgentError(
                    AgentReasonCode.INVALID_INPUT,
                    "BOOT requires an injected boot secret (never command data)",
                )
            self.boot(boot_secret)
            return None
        if kind == CommandKind.EXPOSE_INTERFACES:
            return list(self.expose_interfaces())
        if kind == CommandKind.REGISTER_PEER:
            raise AgentError(
                AgentReasonCode.COMMAND_REJECTED,
                "peer registration is a direct method operation "
                "(object artifacts, not command data)",
            )
        if kind == CommandKind.MONITOR:
            report = self.monitor()
            return report.to_dict()
        if kind == CommandKind.SEND_DATAGRAM:
            session_id = str(params.get("session_id", ""))
            payload = bytes.fromhex(str(params.get("payload_hex", "")))
            artifact = self.send_datagram(session_id, payload)
            return {
                "session_id": artifact.session_id,
                "transport_id": artifact.transport_id,
                "frame": dict(artifact.frame),
            }
        if kind == CommandKind.RECEIVE_DATAGRAM:
            frame = params.get("frame", {})
            if not isinstance(frame, Mapping):
                raise AgentError(
                    AgentReasonCode.INVALID_INPUT, "frame must be a mapping"
                )
            artifact = DatagramArtifact(
                session_id=str(params.get("session_id", "")),
                transport_id=str(params.get("transport_id", "")),
                frame=frame,
            )
            payload = self.receive_datagram(artifact)
            return {"payload_hex": payload.hex()}
        if kind == CommandKind.SUSPEND_SESSION:
            self.suspend_session(str(params.get("session_id", "")))
            return None
        if kind == CommandKind.TERMINATE_SESSION:
            self.terminate_session(str(params.get("session_id", "")))
            return None
        if kind == CommandKind.NEGOTIATE_PEER:
            inventory_data = params.get("peer_inventory", {})
            if not isinstance(inventory_data, Mapping):
                raise AgentError(
                    AgentReasonCode.INVALID_INPUT, "peer_inventory must be a mapping"
                )
            peer_inventory = version_inventory_from_dict(dict(inventory_data))
            report = self.negotiate_peer(peer_inventory)
            return {
                "coexist": bool(getattr(report, "coexist", False)),
                "profile": str(getattr(getattr(report, "profile", None), "selected", "")),
            }
        if kind == CommandKind.SELF_TEST:
            return self.self_test()
        if kind == CommandKind.SHUTDOWN:
            self.shutdown()
            return None
        raise AgentError(
            AgentReasonCode.COMMAND_REJECTED, "unknown command kind %r" % kind
        )


def run_headless(
    config: AgentConfig,
    commands: Sequence[AgentCommand],
    *,
    clock: AgentClock,
    interface_source: InterfaceSource,
    boot_secret: Optional[bytes] = None,
) -> AgentRunResult:
    """Construct a runtime and execute one headless command batch."""
    runtime = AgentRuntime(config, clock=clock, interface_source=interface_source)
    return runtime.execute(commands, boot_secret=boot_secret)


def verify_agent_replay(
    config: AgentConfig,
    commands: Sequence[AgentCommand],
    *,
    clock_factory: Callable[[], AgentClock],
    interface_source_factory: Callable[[], InterfaceSource],
    boot_secret: Optional[bytes] = None,
    expected_trace_digest: str = "",
) -> Tuple[bool, str]:
    """Re-run a headless scenario and verify byte-identical replay."""
    result = run_headless(
        config,
        commands,
        clock=clock_factory(),
        interface_source=interface_source_factory(),
        boot_secret=boot_secret,
    )
    if expected_trace_digest and result.trace_digest != expected_trace_digest:
        return False, "trace digest diverged on replay"
    return True, result.trace_digest
