"""The deterministic sandbox services builder of the ADCOS runtime.

:func:`build_sandbox_services` composes the COMPLETE in-memory runtime —
every ACCEPTED authority instantiated with its deterministic in-process
default — plus the platform-held demonstration credential. It is the
mode used when no durable backend is configured (``mode = "sandbox"``)
and the deterministic test world of the runtime batteries.

DETERMINISM (the demonstration mandate): every instant is a fixed
constant; the only clock is the injected
:class:`~agent.clock.FixedClock`; nothing reads a wall clock, nothing
is random, nothing touches the network. Identical inputs produce
byte-identical responses.

DEMO-ONLY ISSUANCE MATERIAL: the sandbox issuance key is a FIXED
content-derived constant (``sha256`` over a public constant string).
It exists so the deterministic world can issue the demonstration
application credential WITHOUT any secret. It MUST NEVER be used in
production mode — :mod:`runtime.wiring` requires the real
``ADCOS_ISSUANCE_KEY`` there (fail closed, never a silent default).

The execution providers are the ACCEPTED reference adapters
(:mod:`adapters.reference.ran` — the M007 deterministic reference
composition over the WORK-016 sandboxed runtime): the reference
adapters ARE the deterministic sandbox providers of the DEC-0126
software-only first deployment. :func:`build_sandbox_execution` mounts
ONE fresh composition per call (a fresh WORK-012 session + a fresh
adapter runtime): the adapter activation ledger is LOCK-117 execution
bookkeeping — DATA, never authority — so a fresh deterministic
composition per demonstration run is the honest shape (the canonical
durable state lives in the contract journal, the API journal and the
evidence store, never in the adapter runtime).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from agent.clock import FixedClock

from contracts import ContractStore

from developerapi import Capability
from developerapi.gateway import DeveloperApiService
from developerapi.journal import MemoryApiStore
from developerapi.ratelimit import RateLimiter

from evidence import EvidenceStore

from policy.model import PolicyDecision
from routing import LinkMetrics, RoutingContext, RoutingEngine
from sessions import SessionState, SessionStore
from topology import (
    ClaimType,
    SourceClass,
    TopologyClaim,
    TopologyGraph,
    make_link_subject,
)
from resources import ResourceStore

from adapters.capability import CapabilityAdapter
from adapters.runtime import AdapterRuntime

from .services import RuntimeServices

__all__ = [
    "SandboxExecution",
    "build_sandbox_execution",
    "build_sandbox_services",
    "SANDBOX_ISSUANCE_KEY",
    "SANDBOX_SERVICE_INSTANT",
]


#: The single fixed service instant of the deterministic sandbox world
#: (the injected FixedClock never advances; every gateway-internal
#: timestamp is this instant).
SANDBOX_SERVICE_INSTANT = "2026-09-13T00:00:00Z"

#: The fixed topology-freshness window of the sandbox execution session
#: composition (WORK-011 route validity; strictly around the service
#: instant — the session establishment discipline).
_TOPOLOGY_FRESH_UNTIL = "2026-09-14T00:00:00Z"

#: The fixed session-establishment instant (inside the freshness
#: window; the session transition table requires REQUESTED ->
#: AUTHORIZED -> ESTABLISHED in order).
_SESSION_INSTANT = "2026-09-13T12:00:00Z"

#: The sandbox execution endpoints (the deterministic two-node world).
_NODE_A = "adcos:node:runtime.sandbox.v1:" + "a" * 64
_NODE_B = "adcos:node:runtime.sandbox.v1:" + "b" * 64

#: The demonstration application's fixed issuance material (platform
#: out-of-band issuance; the credential secret is DERIVED from the
#: issuance key, returned once at issuance, and only its digest is
#: journaled). Production wiring RE-DERIVES the secret on recovery
#: (the application id is content-derived; the secret is a function
#: of the issuance key — deterministic, never stored).
DEMO_DEVELOPER_ID = "adcos:runtime:demo-developer"
DEMO_APPLICATION_NAME = "adcos:runtime:contract-fulfillment-demo"
DEMO_KEY_MATERIAL = "adcos-runtime-demo-application-key-v1"
DEMO_VALID_UNTIL = "2036-09-13T00:00:00Z"

#: DEMO-ONLY issuance key (see the module docstring): a fixed digest
#: over a PUBLIC constant — deliberately not a secret, deliberately
#: never acceptable in production mode.
SANDBOX_ISSUANCE_KEY = hashlib.sha256(
    b"adcos:runtime:sandbox:issuance-key:demo-only:v1"
).digest()


@dataclass(frozen=True)
class SandboxExecution:
    """One mounted deterministic sandbox execution provider composition.

    Carries the live capability adapter (the accepted M007 boundary),
    the WORK-012 session id the activation binds to, and the reference
    composition's declared reserve coordinates — the demo reads the
    concrete parameters from HERE (single site of truth), never from
    its own constants.
    """

    adapter: CapabilityAdapter
    session_id: str
    adapter_id: str
    access_technology_id: str
    standard_mechanisms: Tuple[str, ...]
    reserve_kind: str
    reserve_quantity: int
    reserve_unit: str


# ---------------------------------------------------------------------------
# The deterministic sandbox execution composition
# ---------------------------------------------------------------------------


def _sandbox_policy_decision(instant: str) -> PolicyDecision:
    """A deterministic allow PolicyDecision (the WORK-004 record shape,
    content-derived id — exactly the accepted battery idiom)."""
    probe = PolicyDecision(
        decision_id="0" * 64,
        effect="allow",
        code="allow",
        detail="adcos-runtime-sandbox",
        matched_rule_ids=("sandbox-allow",),
        policy_set_id="adcos:runtime:sandbox",
        policy_set_version=1,
        evaluation_instant=instant,
    )
    digest = hashlib.sha256(probe.canonical_bytes()).hexdigest()
    return PolicyDecision(
        decision_id=digest,
        effect="allow",
        code="allow",
        detail="adcos-runtime-sandbox",
        matched_rule_ids=("sandbox-allow",),
        policy_set_id="adcos:runtime:sandbox",
        policy_set_version=1,
        evaluation_instant=instant,
    )


def _sandbox_topology() -> TopologyGraph:
    """The deterministic two-node topology (link up + reachable)."""
    graph = TopologyGraph()
    graph.merge(
        TopologyClaim(
            subject=make_link_subject(_NODE_A, _NODE_B),
            reporter=_NODE_A,
            claim_type=ClaimType.LINK_STATE,
            value="up",
            source_class=SourceClass.SELF_ADVERTISEMENT,
            issued_at=SANDBOX_SERVICE_INSTANT,
            freshness_until=_TOPOLOGY_FRESH_UNTIL,
            sequence=1,
            provenance="",
        )
    )
    graph.merge(
        TopologyClaim(
            subject=_NODE_B,
            reporter=_NODE_A,
            claim_type=ClaimType.REACHABLE,
            value="true",
            source_class=SourceClass.DIRECT_OBSERVATION,
            issued_at=SANDBOX_SERVICE_INSTANT,
            freshness_until=_TOPOLOGY_FRESH_UNTIL,
            sequence=1,
            provenance="",
        )
    )
    return graph


def _sandbox_route(instant: str):
    """One deterministic accepted route decision (the WORK-011 engine
    over the sandbox topology; the accepted public evaluation path)."""
    context = RoutingContext(
        source_node_id=_NODE_A,
        destination_node_id=_NODE_B,
        topology=_sandbox_topology(),
        resources=ResourceStore(),
        evaluation_instant=instant,
        policy_decision=_sandbox_policy_decision(instant),
        link_metrics={
            make_link_subject(_NODE_A, _NODE_B): LinkMetrics(
                latency_ms=10,
                loss_basis_points=0,
                capacity_bps=1_000_000,
                energy_cost_millijoules=100,
                confidence_basis_points=10_000,
                observed_at=SANDBOX_SERVICE_INSTANT,
                freshness_until=_TOPOLOGY_FRESH_UNTIL,
            ),
        },
    )
    result = RoutingEngine().evaluate(context)
    if result.decision is None or result.decision.selected is None:
        raise RuntimeError("the deterministic sandbox route evaluation failed")
    return result.decision


def _established_sandbox_session() -> Tuple[SessionStore, str]:
    """One WORK-012 session in ESTABLISHED state (the bindable state
    the adapter runtime's read-only verification requires)."""
    store = SessionStore()
    created = store.create(
        _sandbox_route(_SESSION_INSTANT),
        _sandbox_policy_decision(_SESSION_INSTANT),
        source_node_id=_NODE_A,
        destination_node_id=_NODE_B,
        creation_instant=_SESSION_INSTANT,
    )
    if not created.ok or created.session is None:
        raise RuntimeError("the deterministic sandbox session creation failed")
    session_id = created.session.session_id
    store.transition(session_id, SessionState.AUTHORIZED, event_instant=_SESSION_INSTANT)
    store.transition(session_id, SessionState.ESTABLISHED, event_instant=_SESSION_INSTANT)
    return store, session_id


def build_sandbox_execution() -> SandboxExecution:
    """Mount ONE fresh deterministic sandbox execution composition.

    Composes the accepted M007 RAN reference adapter (the deterministic
    reference engine behind the WORK-016 sandboxed runtime) over a
    fresh established session — the exact accepted composition idioms
    (``adapters.reference.ran.mount_reference`` -> ``AdapterRuntime``
    -> ``CapabilityAdapter``), fully deterministic, offline.
    """
    from adapters.reference.ran import (
        STANDARD_MECHANISMS as RAN_MECHANISMS,
        mount_reference as mount_ran_reference,
    )

    session_store, session_id = _established_sandbox_session()
    implementation, descriptor, _binding = mount_ran_reference(
        now=SANDBOX_SERVICE_INSTANT
    )
    runtime = AdapterRuntime(session_store=session_store)
    runtime.register(descriptor, implementation, now=SANDBOX_SERVICE_INSTANT)
    opened = runtime.open_adapter(
        descriptor.adapter_id, now=_SESSION_INSTANT
    )
    if not opened.ok:
        raise RuntimeError("the deterministic sandbox adapter failed to open")
    adapter = CapabilityAdapter(
        runtime, descriptor.adapter_id, standard_mechanisms=RAN_MECHANISMS
    )
    return SandboxExecution(
        adapter=adapter,
        session_id=session_id,
        adapter_id=descriptor.adapter_id,
        access_technology_id=descriptor.access_technology_id,
        standard_mechanisms=tuple(RAN_MECHANISMS),
        reserve_kind="bandwidth",
        reserve_quantity=10,
        reserve_unit="mbps",
    )


# ---------------------------------------------------------------------------
# The complete deterministic sandbox services composition
# ---------------------------------------------------------------------------


def build_sandbox_services(
    *,
    environment: str = "sandbox",
    issuance_key: bytes = SANDBOX_ISSUANCE_KEY,
    rate_limiter: Optional[Any] = None,
) -> RuntimeServices:
    """Compose the complete deterministic in-memory runtime.

    Every authority is the accepted in-process deterministic default:
    ``ContractStore()`` (no journal path — in-memory fold),
    ``MemoryApiStore()`` (in-process API journal),
    ``EvidenceStore()`` (in-memory records) and the deterministic
    token-bucket ``RateLimiter`` over the fixed clock (or an injected
    coordination adapter with the same ``check(application_id)``
    surface — the Upstash seam). The execution factory mounts a fresh
    deterministic sandbox provider composition per demonstration run
    (see :func:`build_sandbox_execution`).
    """
    clock = FixedClock(SANDBOX_SERVICE_INSTANT)
    contracts = ContractStore()
    api_store = MemoryApiStore()
    evidence = EvidenceStore()
    limiter = rate_limiter or RateLimiter(
        capacity=1000, refill_per_second=100, clock=clock
    )
    gateway = DeveloperApiService(
        environment=environment,
        contracts=contracts,
        store=api_store,
        clock=clock,
        issuance_key=issuance_key,
        rate_limiter=limiter,
    )
    issued = gateway.issue_application_credential(
        developer_id=DEMO_DEVELOPER_ID,
        application_name=DEMO_APPLICATION_NAME,
        capabilities=Capability.values(),
        valid_until=DEMO_VALID_UNTIL,
        key_material=DEMO_KEY_MATERIAL,
        actor="platform",
    )
    return RuntimeServices(
        environment=environment,
        mode="sandbox",
        contracts=contracts,
        api_store=api_store,
        evidence=evidence,
        gateway=gateway,
        clock=clock,
        rate_limiter=limiter,
        sandbox_execution=True,
        execution_factory=build_sandbox_execution,
        issuance_key=issuance_key,
        backends={},
        demo_application_id=issued.record.application_id,
        demo_credential=issued.secret,
    )
