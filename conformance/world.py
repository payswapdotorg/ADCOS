"""WORK-032 conformance suite -- the deterministic fixture world.

The world composes the ACCEPTED, in-repo authorities (WORK-003 through
W017) exactly through their public contracts, and exposes narrow
per-area *surfaces* that conformance vectors call.  The surfaces are
composition helpers only: every method delegates to a genuine authority
and returns the authority's own result unchanged -- no surface ever
re-decides, repairs, or reinterprets an authority verdict (the
no-second-authority rule).

Composition note (transitive inputs): RoutingContext requires a genuine
``ResourceStore`` (WORK-008) and ``PolicyDecision`` (WORK-010), and
SessionStore.create requires a genuine RouteDecision + PolicyDecision.
These are INPUT surfaces of the declared W011/W012 contracts themselves;
importing them here is sanctioned transitive composition, not a hidden
dependency edge.  W013 (multipath) and every other non-dependency family
are NOT imported (see conformance/vectors/structure.py, which audits
this).

Determinism: fixed instants, fixed key material, no wall clock, no
randomness, no network.  The harness builds one fresh world per vector,
so vectors are isolated and order-independent.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from adapters import (
    AdapterDescriptor,
    AdapterRuntime,
    AdapterSecurityState,
    ResourceMappingEntry,
    derive_adapter_id,
)
from capabilities import (
    CapabilityStatement,
    NegotiationSpec,
    negotiate,
    sign_statement,
    verify_statement,
)
from federation import FederationStore, Scope
from identity import (
    CredentialReference,
    DevHmacSha256Provider,
    IdentityService,
    InMemoryCredentialStore,
    NodeID,
    NodeIdentity,
    ProfileSet,
    derive_node_id,
    parse_node_id,
    public_metadata_from_bytes,
    public_metadata_to_bytes,
)
from policy.model import PolicyDecision
from protocol import (
    Envelope,
    ParsePolicy,
    UnknownTypePolicy,
    accept,
    canonical_json_bytes,
    envelope_from_mapping,
    get_codec,
    signature_input_bytes,
    validate,
)
from resources import ResourceStore
from routing import (
    LinkMetrics,
    RouteDecision,
    RouteEvaluationResult,
    RoutingContext,
    RoutingEngine,
)
from sessions import SessionStore, SessionResult, SessionState
from topology import (
    ClaimType,
    MergeOutcome,
    SourceClass,
    TopologyClaim,
    TopologyGraph,
    make_link_subject,
)
from transport import (
    ModeledTransportEngine,
    TransportAcceptance,
    TransportConfirmation,
    TransportManager,
    TransportOffer,
    TransportSecurityPolicy,
    Work004IdentityAuthority,
    Work012SessionReader,
    default_profile_offers,
    negotiate_transport_profiles,
)

from conformance.doubles import ReferenceAdapter

import hashlib

__all__ = [
    "ConformanceWorld",
    "EnvelopeSurface",
    "IdentitySurface",
    "CapabilitySurface",
    "TopologySurface",
    "RoutingSurface",
    "SessionSurface",
    "FederationSurface",
    "AdapterSurface",
    "TransportSurface",
    "T0",
    "T1",
    "NOW",
    "LATER",
    "EVEN_LATER",
    "PAST",
    "FUTURE",
]

# ---------------------------------------------------------------------------
# Frozen fixture instants (injected time only)
# ---------------------------------------------------------------------------

T0 = "2026-06-01T00:00:00Z"
T1 = "2026-12-31T23:59:59Z"
NOW = "2026-06-01T12:00:00Z"
LATER = "2026-06-01T13:00:00Z"
EVEN_LATER = "2026-06-01T14:00:00Z"
PAST = "2026-01-01T00:00:00Z"
FUTURE = "2027-06-01T00:00:00Z"

_KNOWN_TECH = "access.generic.experimental"


# ---------------------------------------------------------------------------
# Envelope surface (WORK-003)
# ---------------------------------------------------------------------------


class EnvelopeSurface:
    """Thin delegation to the WORK-003 envelope/serialization contract."""

    def accept_bytes(self, data: Any, *, now: Any, policy: Any,
                     replay: Any = None) -> Any:
        return accept(data, now=now, policy=policy, replay=replay)

    def validate_envelope(self, envelope: Any, *, now: Any,
                          policy: Any, replay: Any = None) -> Any:
        return validate(envelope, now=now, policy=policy, replay=replay)

    def canonical(self, value: Any) -> bytes:
        return canonical_json_bytes(value)

    def signature_input(self, envelope: Envelope) -> bytes:
        return signature_input_bytes(envelope)

    def from_mapping(self, data: Any) -> Envelope:
        return envelope_from_mapping(data)

    def codec(self, name: str) -> Any:
        return get_codec(name)

    def policy(self, unknown_type: str = "reject") -> ParsePolicy:
        return ParsePolicy(
            unknown_type=(
                UnknownTypePolicy.REJECT
                if unknown_type == "reject"
                else UnknownTypePolicy.FORWARD_OPAQUE
            )
        )


# ---------------------------------------------------------------------------
# Identity surface (WORK-004)
# ---------------------------------------------------------------------------


class IdentitySurface:
    """The composed WORK-004 identity stack of the fixture world."""

    def __init__(self) -> None:
        self.store = InMemoryCredentialStore()
        self.provider = DevHmacSha256Provider()
        self.profiles = ProfileSet.load_default()
        self.service = IdentityService(self.store, self.provider, self.profiles)
        self.profile = self.profiles.get("identity.sha256-hmac-dev.v1")
        self.node_a = NodeIdentity.create(self.profile, b"conformance-key-A", T0)
        self.node_b = NodeIdentity.create(self.profile, b"conformance-key-B", T0)
        self.node_c = NodeIdentity.create(self.profile, b"conformance-key-C", T0)
        # Node A carries identity+operational credentials (rotation vectors
        # need identity-role authorization); B and C carry operational ones.
        self.identity_ref_a = self.service.provision(
            self.node_a, "identity", b"identity-role-secret-A", now=NOW
        )
        self.service.activate(self.identity_ref_a, now=NOW)
        self.operational_refs: Dict[str, CredentialReference] = {}
        for identity in (self.node_a, self.node_b, self.node_c):
            ref = self.service.provision(
                identity,
                "operational",
                b"op-secret-" + identity.node_id.text.encode(),
                now=NOW,
            )
            self.service.activate(ref, now=NOW)
            self.operational_refs[identity.node_id.text] = ref

    # -- delegation --------------------------------------------------------

    def derive(self, profile_id: str, key: bytes, rule: str, domain: str) -> NodeID:
        return derive_node_id(profile_id, key, rule, domain)

    def parse(self, text: str) -> NodeID:
        return parse_node_id(text)

    def provision(self, identity: Any, role: str, secret: bytes, *,
                  now: str,
                  expires_at: Optional[str] = None) -> Any:
        return self.service.provision(
            identity, role, secret, now=now, expires_at=expires_at
        )

    def activate(self, reference: Any, *, now: str) -> Any:
        return self.service.activate(reference, now=now)

    def rotate(self, reference: Any, *, node_id: Any, role: str,
               new_secret: bytes, authorization: bytes,
               rotated_at: str) -> Any:
        return self.service.rotate(
            reference,
            node_id=node_id,
            role=role,
            new_secret=new_secret,
            authorization=authorization,
            rotated_at=rotated_at,
        )

    def rotation_statement(self, node_id: Any, role: str,
                           from_generation: int,
                           to_generation: int, new_public_material: bytes,
                           rotated_at: str) -> bytes:
        return self.service.rotation_statement(
            node_id, role, from_generation, to_generation,
            new_public_material, rotated_at,
        )

    def sign(self, reference: Any, data: bytes) -> bytes:
        return self.provider.sign(self.store, reference, data)

    def revoke(self, reference: Any, *, reason: str, now: str) -> Any:
        return self.service.revoke(reference, reason=reason, now=now)

    def active(self, node_id: Any, role: str, *, now: str) -> Any:
        return self.service.active_credential(node_id, role, now=now)

    def metadata_bytes(self, identity: Any) -> bytes:
        return public_metadata_to_bytes(self.service.public_metadata(identity))

    def metadata_from_bytes(self, data: bytes) -> Any:
        return public_metadata_from_bytes(data)

    def public_material(self, secret: bytes) -> bytes:
        return self.provider.public_material(secret)


# ---------------------------------------------------------------------------
# Capability surface (WORK-005)
# ---------------------------------------------------------------------------


class CapabilitySurface:
    """Thin delegation to the WORK-005 capability contract."""

    def __init__(self, identity: IdentitySurface) -> None:
        self.identity = identity

    def statement(self, *, capability_id: str, provider: str,
                  valid_from: str = T0, expires_at: str = T1,
                  schema_version: str = "1.0",
                  parameters: Any = None,
                  constraints: Any = None) -> CapabilityStatement:
        return CapabilityStatement(
            capability_id=capability_id,
            schema_version=schema_version,
            provider_identity=provider,
            valid_from=valid_from,
            expires_at=expires_at,
            parameters=parameters or {},
            constraints=constraints or {},
        )

    def sign(self, statement: CapabilityStatement,
             credential: CredentialReference) -> CapabilityStatement:
        return sign_statement(
            statement,
            store=self.identity.store,
            provider=self.identity.provider,
            credential=credential,
        )

    def verify(self, statement: CapabilityStatement,
               credential: CredentialReference, *, now: Any) -> bool:
        return verify_statement(
            statement,
            store=self.identity.store,
            provider=self.identity.provider,
            credential=credential,
            now=now,
        )

    def negotiate(self, spec: NegotiationSpec,
                  requirements: Any = ()) -> Any:
        return negotiate(spec, requirements=requirements)

    def to_bytes(self, statement: CapabilityStatement) -> bytes:
        from capabilities import statement_to_bytes

        return statement_to_bytes(statement)

    def from_bytes(self, data: bytes) -> CapabilityStatement:
        from capabilities import statement_from_bytes

        return statement_from_bytes(data)


# ---------------------------------------------------------------------------
# Topology surface (WORK-007)
# ---------------------------------------------------------------------------


class TopologySurface:
    """A fresh WORK-007 TopologyGraph with merge/query delegation."""

    def __init__(self) -> None:
        self.graph = TopologyGraph()

    def merge(self, claim: TopologyClaim) -> MergeOutcome:
        return self.graph.merge(claim)

    def authoritative(self, subject: str, *, now: Any) -> Tuple[Any, ...]:
        return self.graph.get_authoritative_claims(subject, now=now)

    def claims_for(self, subject: str, *, now: Any) -> Tuple[Any, ...]:
        return self.graph.get_claims_for_subject(subject, now=now)

    def identity_state(self, subject: str, *, now: Any) -> str:
        return self.graph.get_identity_state(subject, now=now)

    def link_state(self, endpoint_a: str, endpoint_b: str, *,
                   now: Any) -> str:
        return self.graph.get_link_state(endpoint_a, endpoint_b, now=now)

    def claim(self, *, subject: str, reporter: str, claim_type: str,
              value: Any, source_class: str, issued_at: str = T0,
              freshness_until: str = T1, sequence: int = 1,
              provenance: str = "", claim_id: str = ""
              ) -> TopologyClaim:
        return TopologyClaim(
            subject=subject,
            reporter=reporter,
            claim_type=claim_type,
            value=value,
            source_class=source_class,
            issued_at=issued_at,
            freshness_until=freshness_until,
            sequence=sequence,
            provenance=provenance,
            claim_id=claim_id,
        )


# ---------------------------------------------------------------------------
# Routing surface (WORK-011)
# ---------------------------------------------------------------------------


class RoutingSurface:
    """The composed WORK-011 routing fixture (policy -> routing chain)."""

    def __init__(self) -> None:
        self.engine = RoutingEngine()

    def policy(self, instant: str = NOW, *, effect: str = "allow",
               code: str = "allow") -> PolicyDecision:
        """A tamper-evident PolicyDecision (content-derived decision id)."""
        placeholder = PolicyDecision(
            decision_id="0" * 64,
            effect=effect,
            code=code,
            detail="conformance fixture",
            matched_rule_ids=("conformance-rule-1",),
            policy_set_id="conformance-set-1",
            policy_set_version=2,
            evaluation_instant=instant,
        )
        digest = hashlib.sha256(placeholder.canonical_bytes()).hexdigest()
        return PolicyDecision(
            decision_id=digest,
            effect=effect,
            code=code,
            detail="conformance fixture",
            matched_rule_ids=("conformance-rule-1",),
            policy_set_id="conformance-set-1",
            policy_set_version=2,
            evaluation_instant=instant,
        )

    def tampered_policy(self, instant: str = NOW) -> PolicyDecision:
        """A structurally valid but NON-tamper-evident decision (forged id)."""
        genuine = self.policy(instant)
        return PolicyDecision(
            decision_id="f" * 64,
            effect=genuine.effect,
            code=genuine.code,
            detail=genuine.detail,
            matched_rule_ids=genuine.matched_rule_ids,
            policy_set_id=genuine.policy_set_id,
            policy_set_version=genuine.policy_set_version,
            evaluation_instant=genuine.evaluation_instant,
        )

    def graph(self, source: str, destination: str) -> TopologyGraph:
        graph = TopologyGraph()
        graph.merge(TopologyClaim(
            subject=make_link_subject(source, destination),
            reporter=source,
            claim_type=ClaimType.LINK_STATE,
            value="up",
            source_class=SourceClass.SELF_ADVERTISEMENT,
            issued_at=T0,
            freshness_until=T1,
            sequence=1,
        ))
        graph.merge(TopologyClaim(
            subject=destination,
            reporter=source,
            claim_type=ClaimType.REACHABLE,
            value="true",
            source_class=SourceClass.DIRECT_OBSERVATION,
            issued_at=T0,
            freshness_until=T1,
            sequence=1,
        ))
        return graph

    def metrics(self, *, latency_ms: int = 10,
                confidence: int = 10_000,
                observed_at: str = T0,
                freshness_until: str = T1,
                properties: Tuple[Any, ...] = ()) -> LinkMetrics:
        return LinkMetrics(
            latency_ms=latency_ms,
            loss_basis_points=0,
            capacity_bps=1_000_000,
            energy_cost_millijoules=100,
            confidence_basis_points=confidence,
            observed_at=observed_at,
            freshness_until=freshness_until,
            properties=properties,
        )

    def context(self, source: str, destination: str, instant: str = NOW, *,
                policy: Optional[PolicyDecision] = None,
                graph: Optional[TopologyGraph] = None,
                link_metrics: Optional[Dict[str, LinkMetrics]] = None,
                expected_topology_digest: str = "",
                min_confidence: int = 0,
                max_hops: int = 8) -> RoutingContext:
        return RoutingContext(
            source_node_id=source,
            destination_node_id=destination,
            topology=graph if graph is not None else self.graph(source, destination),
            resources=ResourceStore(),
            evaluation_instant=instant,
            policy_decision=policy if policy is not None else self.policy(instant),
            link_metrics=link_metrics if link_metrics is not None else {
                make_link_subject(source, destination): self.metrics()
            },
            expected_topology_digest=expected_topology_digest,
            min_confidence_basis_points=min_confidence,
            max_hops=max_hops,
        )

    def evaluate(self, context: RoutingContext) -> RouteEvaluationResult:
        return self.engine.evaluate(context)

    def decision(self, source: str, destination: str,
                 instant: str = NOW) -> RouteDecision:
        result = self.evaluate(self.context(source, destination, instant))
        if result.decision is None or result.decision.selected is None:
            raise RuntimeError(
                "fixture route evaluation failed: %s" % result.code
            )
        return result.decision


# ---------------------------------------------------------------------------
# Session surface (WORK-012)
# ---------------------------------------------------------------------------


class SessionSurface:
    """The composed WORK-012 session fixture over a genuine route chain."""

    def __init__(self, routing: RoutingSurface) -> None:
        self.routing = routing
        self.store = SessionStore()

    def create(self, route: RouteDecision, policy: PolicyDecision, *,
               source: str, destination: str, instant: str = NOW,
               intent_digest: str = "",
               extensions: Tuple[Any, ...] = ()) -> SessionResult:
        result: SessionResult = self.store.create(
            route,
            policy,
            source_node_id=source,
            destination_node_id=destination,
            creation_instant=instant,
            intent_digest=intent_digest,
            extensions=extensions,
        )
        return result

    def transition(self, session_id: str, new_state: str, *,
                   instant: str = NOW,
                   metadata: Tuple[Tuple[str, str], ...] = ()
                   ) -> SessionResult:
        result: SessionResult = self.store.transition(
            session_id, new_state, event_instant=instant, metadata=metadata
        )
        return result

    def established(self, source: str, destination: str,
                    instant: str = NOW) -> str:
        """A genuine ESTABLISHED session id (policy -> route -> session)."""
        route = self.routing.decision(source, destination, instant)
        policy = self.routing.policy(instant)
        result = self.create(
            route, policy, source=source, destination=destination,
            instant=instant,
        )
        if not result.ok or result.session is None:
            raise RuntimeError("fixture session create failed: %s" % result.code)
        session_id = result.session.session_id
        self.transition(session_id, SessionState.AUTHORIZED, instant=instant)
        self.transition(session_id, SessionState.ESTABLISHED, instant=instant)
        return session_id

    def requested(self, source: str, destination: str,
                  instant: str = LATER) -> str:
        """A session left in REQUESTED state (not yet bindable).

        Distinct binding material (later creation instant) so the
        session is genuinely new, never the world's established one.
        """
        route = self.routing.decision(source, destination, instant)
        policy = self.routing.policy(instant)
        result = self.create(
            route, policy, source=source, destination=destination,
            instant=instant,
        )
        if not result.ok or result.session is None:
            raise RuntimeError("fixture session create failed: %s" % result.code)
        return result.session.session_id

    def reconnect(self, session_id: str, new_route: RouteDecision, *,
                  instant: str = NOW,
                  new_policy_decision: Any = None) -> SessionResult:
        result: SessionResult = self.store.reconnect(
            session_id, new_route, reconnect_instant=instant,
            new_policy_decision=new_policy_decision,
        )
        return result

    def terminate(self, session_id: str, *,
                  instant: str = NOW) -> SessionResult:
        result: SessionResult = self.store.terminate(
            session_id, event_instant=instant
        )
        return result

    def get(self, session_id: str) -> Any:
        return self.store.get(session_id)

    def events(self, session_id: str) -> Any:
        return self.store.get_events(session_id)


# ---------------------------------------------------------------------------
# Federation surface (W015)
# ---------------------------------------------------------------------------


class FederationSurface:
    """A fresh WORK-015 FederationStore with narrow helpers."""

    def __init__(self, node_a: str, node_b: str) -> None:
        self.store = FederationStore()
        self.operator_a = node_a
        self.operator_b = node_b
        self.domain_operator_ids: Dict[str, str] = {}

    def create_domain(self, operator_node_id: str,
                      identity_public_key: str, *,
                      created_at: str = NOW,
                      activate: bool = True) -> Any:
        result = self.store.create_domain(
            "operator-reference",
            identity_public_key,
            operator_node_id=operator_node_id,
            created_at=created_at,
        )
        if result.ok and result.domain is not None and activate:
            activated = self.store.transition_domain(
                result.domain.domain_id, "active", event_instant=created_at
            )
            if not activated.ok:
                raise RuntimeError(
                    "fixture domain activation failed: %s" % activated.code
                )
            self.domain_operator_ids[result.domain.domain_id] = operator_node_id
        return result

    def two_domains(self, *, created_at: str = NOW) -> Tuple[str, str]:
        result_a = self.create_domain(self.operator_a, "aa" * 32, created_at=created_at)
        result_b = self.create_domain(self.operator_b, "bb" * 32, created_at=created_at)
        if not (result_a.ok and result_b.ok):
            raise RuntimeError("fixture domain creation failed")
        return result_a.domain.domain_id, result_b.domain.domain_id

    def establish(self, local_domain_id: str, peer_domain_id: str, *,
                  scopes: Tuple[str, ...] = (Scope.CAPABILITY_READ,),
                  valid_from: str = T0, valid_until: str = T1,
                  event_instant: str = NOW) -> Any:
        return self.store.establish_relationship(
            local_domain_id,
            peer_domain_id,
            peer_identity_reference=self.domain_operator_ids.get(
                peer_domain_id, ""
            ),
            declared_scopes=scopes,
            valid_from=valid_from,
            valid_until=valid_until,
            event_instant=event_instant,
        )

    def established_pair(self, *,
                         scopes: Tuple[str, ...] = (
                             Scope.CAPABILITY_READ,
                         )) -> Tuple[str, str, str]:
        """(domain_a, domain_b, relationship_id) with an established link."""
        domain_a, domain_b = self.two_domains()
        result = self.establish(domain_a, domain_b, scopes=scopes)
        if not result.ok or result.relationship is None:
            raise RuntimeError("fixture relationship failed: %s" % result.code)
        return domain_a, domain_b, result.relationship.relationship_id

    def publish_grant(self, relationship_id: str, scope: str, *,
                      valid_from: str = T0, valid_until: str = T1,
                      event_instant: str = NOW) -> Any:
        return self.store.publish_grant(
            relationship_id,
            scope,
            valid_from=valid_from,
            valid_until=valid_until,
            event_instant=event_instant,
        )

    def check_scope(self, relationship_id: str, scope: str, *,
                    evaluation_instant: str = NOW) -> Any:
        return self.store.check_scope(
            relationship_id, scope, evaluation_instant=evaluation_instant
        )

    def revoke_grant(self, grant_id: str, *, event_instant: str = NOW,
                     reason: str = "") -> Any:
        return self.store.revoke_grant(
            grant_id, event_instant=event_instant, reason=reason
        )

    def apply_exchange(self, exchange: Any, *,
                       event_instant: str = NOW) -> Any:
        return self.store.apply_exchange(exchange, event_instant=event_instant)

    def replay_event(self, subject_id: str, event: Any) -> Any:
        return self.store.replay_event(subject_id, event)

    def events_for(self, subject_id: str) -> Any:
        return self.store.get_events(subject_id)


# ---------------------------------------------------------------------------
# Adapter surface (W016)
# ---------------------------------------------------------------------------


class AdapterSurface:
    """The composed WORK-016 runtime fixture (real session store bound)."""

    def __init__(self, session_store: SessionStore, session_id: str) -> None:
        self.session_store = session_store
        self.session_id = session_id
        self.runtime, self.adapter_id = self._build(ReferenceAdapter())

    def descriptor(self, label: str = "conformance-0") -> AdapterDescriptor:
        return AdapterDescriptor(
            adapter_id=derive_adapter_id(_KNOWN_TECH, label),
            access_technology_id=_KNOWN_TECH,
            supported_profile_versions=("v1-0-0",),
            capabilities=("capability.core.store-and-forward",),
            resource_mapping=(
                ResourceMappingEntry(
                    technology_resource="link-bandwidth",
                    kind="bandwidth",
                    unit="mbps",
                    quantity=100,
                    availability="reservation-based",
                ),
            ),
            security_state=AdapterSecurityState(
                profile="baseline",
                credential_slots=("technology-credential",),
                attested=False,
            ),
        )

    def _build(self, implementation: Any, *,
               label: str = "conformance-0") -> Tuple[Any, str]:
        runtime = AdapterRuntime(session_store=self.session_store)
        descriptor = self.descriptor(label)
        runtime.register(descriptor, implementation, now=T0)
        runtime.open_adapter(descriptor.adapter_id, now=NOW)
        self.implementation = implementation
        return runtime, descriptor.adapter_id

    def runtime_with(self, implementation: Any, *,
                     label: str = "conformance-x") -> Tuple[Any, str]:
        """A fresh registered+opened runtime around a chosen subject double."""
        return self._build(implementation, label=label)

    # -- delegation over the default reference adapter ---------------------

    def allocate(self, *, kind: str = "bandwidth", quantity: int = 10,
                 unit: str = "mbps", purpose: str = "conformance",
                 now: str = NOW,
                 expires_at: Optional[str] = None) -> Any:
        return self.runtime.allocate(
            self.adapter_id,
            kind=kind,
            quantity=quantity,
            unit=unit,
            purpose=purpose,
            now=now,
            expires_at=expires_at,
        )

    def release(self, allocation_id: str, *, now: str = NOW) -> Any:
        return self.runtime.release(allocation_id, now=now)

    def bind(self, session_id: Optional[str] = None, *,
             now: str = NOW) -> Any:
        return self.runtime.bind_session(
            self.adapter_id,
            session_id=session_id if session_id is not None else self.session_id,
            now=now,
        )

    def unbind(self, binding_id: str, *, now: str = NOW) -> Any:
        return self.runtime.unbind_session(binding_id, now=now)

    def capabilities(self, *, now: str = NOW) -> Tuple[str, ...]:
        exposed: Tuple[str, ...] = self.runtime.capabilities(
            self.adapter_id, now=now
        )
        return exposed

    def observe(self, *, now: str = NOW) -> Any:
        return self.runtime.observe(self.adapter_id, now=now)

    def health(self, *, now: str = NOW) -> Any:
        return self.runtime.health(self.adapter_id, now=now)

    def close(self, *, now: str = NOW) -> Any:
        return self.runtime.close_adapter(self.adapter_id, now=now)


# ---------------------------------------------------------------------------
# Transport surface (W017)
# ---------------------------------------------------------------------------


class TransportSurface:
    """The composed WORK-017 fixture: two managers, full 4-step handshake."""

    def __init__(self, identity: IdentitySurface, session_store: SessionStore,
                 session_id: str) -> None:
        self.identity = identity
        self.session_store = session_store
        self.session_id = session_id
        self.identity_authority = Work004IdentityAuthority(
            identity.service, identity.provider, identity.store
        )

    def manager(self) -> TransportManager:
        return TransportManager(
            session_reader=Work012SessionReader(self.session_store),
            identity=self.identity_authority,
            implementation=ModeledTransportEngine(),
        )

    def default_policy(self) -> TransportSecurityPolicy:
        return TransportSecurityPolicy(
            require_confidentiality=True, require_forward_secrecy=True
        )

    def establish_pair(self, *, policy: Any = None, offers: Any = None,
                       now: str = NOW, label: str = "pair",
                       session_id: Optional[str] = None) -> Tuple[Any, ...]:
        """The full handshake between two independent managers.

        Returns (initiator_manager, responder_manager, transport_id,
        offer, acceptance, confirmation).
        """
        manager_i = self.manager()
        manager_r = self.manager()
        policy = policy if policy is not None else self.default_policy()
        offers = offers if offers is not None else list(default_profile_offers())
        result = manager_i.establish_initiator(
            session_id if session_id is not None else self.session_id,
            policy=policy,
            offered_profiles=offers,
            now=now,
            instance_label=label + "-initiator",
        )
        if not result.ok or result.value is None:
            raise RuntimeError("fixture handshake failed: %s" % result.detail)
        offer = result.value
        handle = manager_i.pending_handles()[0]
        result = manager_r.respond(
            offer, now=now, instance_label=label + "-responder"
        )
        if not result.ok or result.value is None:
            raise RuntimeError("fixture respond failed: %s" % result.detail)
        acceptance = result.value
        result = manager_i.complete_initiator(handle, acceptance, now=now)
        if not result.ok or result.value is None:
            raise RuntimeError("fixture complete failed: %s" % result.detail)
        confirmation = result.value
        result = manager_r.confirm(acceptance.transport_id, confirmation, now=now)
        if not result.ok:
            raise RuntimeError("fixture confirm failed: %s" % result.detail)
        return (
            manager_i,
            manager_r,
            acceptance.transport_id,
            offer,
            acceptance,
            confirmation,
        )

    def negotiate(self, local: Any, remote: Any, policy: Any, *,
                   profile_set: Any = None) -> Any:
        return negotiate_transport_profiles(
            local, remote, policy, profile_set=profile_set
        )

    # -- step-level delegations (sabotage interception points) -------------

    def begin(self, *, policy: Any = None, offers: Any = None,
              now: str = NOW, label: str = "pair",
              session_id: Optional[str] = None) -> Tuple[Any, Any, str]:
        """Initiator side of a handshake: (manager, offer, handle)."""
        manager = self.manager()
        policy = policy if policy is not None else self.default_policy()
        offers = offers if offers is not None else list(default_profile_offers())
        result = manager.establish_initiator(
            session_id if session_id is not None else self.session_id,
            policy=policy, offered_profiles=offers, now=now,
            instance_label=label + "-initiator",
        )
        if not result.ok or result.value is None:
            raise RuntimeError("fixture establish failed: %s" % result.detail)
        handle = manager.pending_handles()[0]
        return manager, result.value, handle

    def respond(self, offer: Any, *, now: str = NOW,
                label: str = "pair") -> Tuple[Any, Any]:
        """Responder side of a handshake: (manager, acceptance)."""
        manager = self.manager()
        result = manager.respond(offer, now=now,
                                 instance_label=label + "-responder")
        if not result.ok or result.value is None:
            raise RuntimeError("fixture respond failed: %s" % result.detail)
        return manager, result.value

    def complete_initiator(self, manager: Any, handle: Any,
                           acceptance: Any, *,
                           now: str = NOW) -> Any:
        return manager.complete_initiator(handle, acceptance, now=now)

    def confirm(self, manager: Any, transport_id: str,
                confirmation: Any, *, now: str = NOW) -> Any:
        return manager.confirm(transport_id, confirmation, now=now)


# ---------------------------------------------------------------------------
# The world
# ---------------------------------------------------------------------------


class ConformanceWorld:
    """One fresh, fully composed fixture world (one per vector).

    All authorities are the accepted in-repo implementations composed
    through their public contracts.  Nothing here mutates any authority
    outside this world instance.
    """

    def __init__(self) -> None:
        self.envelope = EnvelopeSurface()
        self.identity = IdentitySurface()
        self.capability = CapabilitySurface(self.identity)
        self.topology = TopologySurface()
        self.routing = RoutingSurface()
        self.session = SessionSurface(self.routing)
        # One session store shared by the adapter runtime and the transport
        # managers (both verify sessions read-only through W012).
        self.node_a = self.identity.node_a.node_id.text
        self.node_b = self.identity.node_b.node_id.text
        self.node_c = self.identity.node_c.node_id.text
        self.established_session_id = self.session.established(
            self.node_a, self.node_b
        )
        self.federation = FederationSurface(self.node_a, self.node_b)
        self.adapter = AdapterSurface(
            self.session.store, self.established_session_id
        )
        self.transport = TransportSurface(
            self.identity, self.session.store, self.established_session_id
        )
