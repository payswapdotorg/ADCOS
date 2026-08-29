"""WORK-039 integration leg: multi-domain federation over the ACCEPTED
W033 Linux-agent and W036 Network-in-a-Box composition surfaces.

Three REAL participants -- two booted WORK-033 ``AgentRuntime``
instances and one booted WORK-036 ``NetworkAppliance`` (whose gateway
owns exactly one agent runtime) -- federate through their OWN REAL
``FederationStore`` instances (``runtime.federation()``):

1. each participant's domain is registered in every participant's
   store, with the domain's operator NodeID bound to the
   participant's REAL agent node id (the honest binding: the agent
   that operates the domain);
2. three relationships are established (both sides, through the
   stores' public contracts);
3. grants are published and capability/route declarations flow
   through the real ``apply_exchange`` contract;
4. one participant revokes its relationship with the appliance; the
   declaration is delivered to the appliance's federation store and
   applied there; the OTHER relationship is digest-proven untouched
   (isolation);
5. the whole integration run is journaled, digested, and replayable.

The harness modifies NOTHING in ``agent/`` or ``appliance/``: it
composes their public construction surfaces exactly the way the
accepted batteries construct them (StepClock + StaticInterfaceSource
+ StaticHardwareSource + boot commands).  The appliance is
constructed in its ISOLATED upstream posture (no upstream Internet
assumption anywhere).
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Mapping, Tuple

from agent import (
    AgentConfig,
    AgentIdentitySpec,
    AgentRuntime,
    InterfaceSnapshot,
    StepClock,
    StaticInterfaceSource,
)
from appliance import (
    ApplianceCommand,
    ApplianceCommandKind,
    NetworkAppliance,
    UpstreamMode,
)
from edge import HardwareInventory, StaticHardwareSource, board_for
from federation import (
    DomainLifecycle,
    ExchangeKind,
    FederationExchange,
    RelationshipState,
    Scope,
    derive_domain_id,
)
from protocol import canonical_json_bytes

from .errors import ScaleError, ScaleReasonCode
from .model import ScaleEvent, ScaleEventType, scale_event_list_digest

__all__ = [
    "IntegrationResult",
    "run_integration_scenario",
    "verify_integration_replay",
]


_T0 = "2026-06-01T00:00:00Z"
_T1 = "2026-06-01T00:01:00Z"
_VALID_UNTIL = "2026-07-01T00:00:00Z"
_PROFILE_ID = "identity.sha256-hmac-dev.v1"
_DECLARED_SCOPES = (
    Scope.ROUTE_IMPORT,
    Scope.ROUTE_EXPORT,
    Scope.CAPABILITY_READ,
    Scope.CAPABILITY_OFFER,
    Scope.SERVICE_DISCOVER,
    Scope.RESOURCE_READ,
)
_GRANT_SCOPES = (
    Scope.ROUTE_IMPORT,
    Scope.CAPABILITY_READ,
)

_INTEGRATION_KEYS = {
    "agent-alpha": b"scale-integration-key-agent-alpha-01",
    "agent-beta": b"scale-integration-key-agent-beta-002",
    "appliance-gamma": b"scale-integration-key-appliance-3",
}
_INTEGRATION_SECRETS = {
    "agent-alpha": b"scale-integration-secret-alpha-01",
    "agent-beta": b"scale-integration-secret-beta-002",
    "appliance-gamma": b"scale-integration-secret-gamma-3",
}
_INTEGRATION_LABELS = ("agent-alpha", "agent-beta", "appliance-gamma")


def _operator_key(label: str) -> str:
    return hashlib.sha256(
        ("scale-integration-operator:%s" % label).encode("utf-8")
    ).hexdigest()


def _interface_snapshots() -> Tuple[InterfaceSnapshot, ...]:
    return (
        InterfaceSnapshot(
            name="eth0", link_kind="ethernet", state_up=True, mtu=1500,
            speed_mbps=1000, rx_bytes=100, tx_bytes=200, rx_errors=0,
            tx_errors=0, addresses=("fd00::a:1",),
        ),
    )


def _hardware_source() -> StaticHardwareSource:
    board = board_for("raspberry-pi-4b")
    return StaticHardwareSource(
        HardwareInventory(
            board_id=board.board_id, arch=board.arch,
            cpu_cores=board.cpu_cores, memory_total_mib=board.memory_mib,
            memory_available_mib=board.memory_mib,
            storage_total_mib=board.storage_mib,
            storage_available_mib=board.storage_mib,
        )
    )


def _agent_config(label: str) -> AgentConfig:
    return AgentConfig(
        agent_label=label,
        identity=AgentIdentitySpec(
            profile_id=_PROFILE_ID,
            public_key=_INTEGRATION_KEYS[label],
            created_at=_T0,
        ),
    )


def _build_agent(label: str) -> AgentRuntime:
    runtime = AgentRuntime(
        _agent_config(label),
        clock=StepClock(_T0, 60),
        interface_source=StaticInterfaceSource(_interface_snapshots()),
    )
    runtime.boot(_INTEGRATION_SECRETS[label])
    runtime.expose_interfaces()
    return runtime


def _build_appliance(label: str) -> NetworkAppliance:
    appliance = NetworkAppliance(
        config=_agent_config(label),
        clock=StepClock(_T0, 60),
        interface_source=StaticInterfaceSource(_interface_snapshots()),
        hardware_source=_hardware_source(),
        access_plan={"eth0": "ethernet"},
        upstream_mode=UpstreamMode.ISOLATED,
    )
    appliance.run_appliance(
        (
            ApplianceCommand(ApplianceCommandKind.BOOT),
            ApplianceCommand(ApplianceCommandKind.EXPOSE_INTERFACES),
        ),
        boot_secret=_INTEGRATION_SECRETS[label],
    )
    return appliance


class IntegrationResult:
    """The journaled, digestable outcome of the integration run."""

    def __init__(
        self,
        journal: Tuple[ScaleEvent, ...],
        store_digests: Tuple[Tuple[str, str], ...],
        checks: Tuple[Tuple[str, bool, str], ...],
        relationship_count: int,
        grant_count: int,
        exchange_count: int,
    ) -> None:
        self._journal = journal
        self._store_digests = store_digests
        self._checks = checks
        self._relationship_count = relationship_count
        self._grant_count = grant_count
        self._exchange_count = exchange_count

    @property
    def journal(self) -> Tuple[ScaleEvent, ...]:
        return self._journal

    @property
    def store_digests(self) -> Tuple[Tuple[str, str], ...]:
        return self._store_digests

    @property
    def checks(self) -> Tuple[Tuple[str, bool, str], ...]:
        return self._checks

    @property
    def relationship_count(self) -> int:
        return self._relationship_count

    @property
    def grant_count(self) -> int:
        return self._grant_count

    @property
    def exchange_count(self) -> int:
        return self._exchange_count

    def content_dict(self) -> Dict[str, Any]:
        return {
            "journal_digest": scale_event_list_digest(self._journal),
            "store_digests": [
                [label, digest] for label, digest in self._store_digests
            ],
            "checks": [
                [label, ok_flag, detail] for label, ok_flag, detail in self._checks
            ],
            "relationship_count": self._relationship_count,
            "grant_count": self._grant_count,
            "exchange_count": self._exchange_count,
        }

    def run_digest(self) -> str:
        return "sha256:" + hashlib.sha256(
            canonical_json_bytes(self.content_dict())
        ).hexdigest()

    def all_checks_pass(self) -> bool:
        return all(ok_flag for _, ok_flag, _ in self._checks)


class _IntegrationJournal:
    def __init__(self) -> None:
        self._events: List[ScaleEvent] = []
        self._sequence = 0

    def append(self, kind: str, payload: Mapping[str, Any]) -> None:
        self._sequence += 1
        self._events.append(
            ScaleEvent(
                at_tick=self._sequence, sequence=self._sequence, kind=kind,
                payload=dict(payload),
            )
        )

    @property
    def events(self) -> Tuple[ScaleEvent, ...]:
        return tuple(self._events)


def run_integration_scenario() -> IntegrationResult:
    """Run the three-participant integration scenario deterministically."""

    journal = _IntegrationJournal()
    checks: List[Tuple[str, bool, str]] = []
    exchange_count = 0

    # -- 1. three REAL participants ----------------------------------
    agent_a = _build_agent("agent-alpha")
    agent_b = _build_agent("agent-beta")
    appliance_c = _build_appliance("appliance-gamma")
    journal.append(
        ScaleEventType.SCENARIO_STARTED,
        {
            "participants": list(_INTEGRATION_LABELS),
            "surfaces": "2x WORK-033 AgentRuntime + 1x WORK-036 NetworkAppliance",
        },
    )
    checks.append((
        "agents-booted",
        agent_a.status == "online" and agent_b.status == "online",
        "both agent runtimes booted online through the public boot contract",
    ))
    checks.append((
        "appliance-booted",
        appliance_c.runtime.status == "online",
        "the appliance gateway runtime booted online (isolated posture)",
    ))

    # -- 2. domain material: operator = the REAL agent node id -------
    stores = {
        "agent-alpha": agent_a.federation,
        "agent-beta": agent_b.federation,
        "appliance-gamma": appliance_c.runtime.federation,
    }
    node_ids = {
        "agent-alpha": agent_a.node_id,
        "agent-beta": agent_b.node_id,
        "appliance-gamma": appliance_c.runtime.node_id,
    }
    domain_ids: Dict[str, str] = {}
    for label in _INTEGRATION_LABELS:
        operator_reference = "operator-integration-%s" % label
        identity_public_key = _operator_key(label)
        domain_ids[label] = derive_domain_id(
            operator_reference, identity_public_key
        )
    # register every participant's domain in every store + activate
    for label in _INTEGRATION_LABELS:
        for owner in _INTEGRATION_LABELS:
            result = stores[owner].create_domain(
                "operator-integration-%s" % label,
                _operator_key(label),
                operator_node_id=node_ids[label],
                created_at=_T0,
            )
            if not result.ok and result.code != "replayed":
                raise ScaleError(
                    ScaleReasonCode.INTEGRATION_INVALID,
                    "integration domain registration failed: %s" % result.detail,
                )
        for owner in _INTEGRATION_LABELS:
            store_domain = next(
                (
                    domain
                    for domain in stores[owner].get_domains()
                    if domain.domain_id == domain_ids[label]
                ),
                None,
            )
            if store_domain is None:  # pragma: no cover - registered above
                raise ScaleError(
                    ScaleReasonCode.INTEGRATION_INVALID,
                    "integration domain missing after registration",
                )
            if store_domain.lifecycle_state != DomainLifecycle.ACTIVE:
                result = stores[owner].transition_domain(
                    domain_ids[label],
                    DomainLifecycle.ACTIVE,
                    event_instant=_T1,
                )
                if not result.ok and result.code != "replayed":
                    raise ScaleError(
                        ScaleReasonCode.INTEGRATION_INVALID,
                        "integration domain activation failed: %s" % result.detail,
                    )
    journal.append(
        ScaleEventType.WORLD_BUILT,
        {
            "domains": len(_INTEGRATION_LABELS),
            "operator_binding": "domain operator NodeID = the real agent node id",
        },
    )

    # -- 3. three relationships, both sides ---------------------------
    pairs = (
        ("agent-alpha", "agent-beta"),
        ("agent-alpha", "appliance-gamma"),
        ("agent-beta", "appliance-gamma"),
    )
    relationship_ids: Dict[Tuple[str, str], str] = {}
    for local, peer in pairs:
        key: Tuple[str, str] = (
            (local, peer) if local < peer else (peer, local)
        )
        from federation import derive_relationship_id
        relationship_ids[key] = derive_relationship_id(
            domain_ids[key[0]], domain_ids[key[1]]
        )
        for side, other in ((local, peer), (peer, local)):
            result = stores[side].establish_relationship(
                domain_ids[side],
                domain_ids[other],
                peer_identity_reference=node_ids[other],
                declared_scopes=_DECLARED_SCOPES,
                valid_from=_T0,
                valid_until=_VALID_UNTIL,
                event_instant=_T1,
            )
            if not result.ok and result.code != "replayed":
                raise ScaleError(
                    ScaleReasonCode.INTEGRATION_INVALID,
                    "integration relationship failed: %s" % result.detail,
                )
    journal.append(
        ScaleEventType.WORLD_BUILT,
        {"relationships": len(pairs), "sides": 2 * len(pairs)},
    )

    # -- 4. grants on both sides --------------------------------------
    grant_count = 0
    for key in sorted(relationship_ids):
        for side in key:
            for scope in _GRANT_SCOPES:
                result = stores[side].publish_grant(
                    relationship_ids[key],
                    scope,
                    valid_from=_T0,
                    valid_until=_VALID_UNTIL,
                    event_instant=_T1,
                )
                if result.ok:
                    grant_count += 1
    journal.append(
        ScaleEventType.GRANT_PUBLISHED,
        {"grants": grant_count, "scopes": list(_GRANT_SCOPES)},
    )

    # -- 5. capability + route exchange between the two agents --------
    rel_ab = relationship_ids[("agent-alpha", "agent-beta")]
    next_slot = stores["agent-beta"].get_relationship(rel_ab).last_event_sequence + 1
    capability_exchange = FederationExchange(
        exchange_id="",
        exchange_kind=ExchangeKind.CAPABILITY_EXPORT,
        local_domain_id=domain_ids["agent-alpha"],
        peer_domain_id=domain_ids["agent-beta"],
        sequence=next_slot,
        declared_at=_T1,
        effective_at=_T1,
        peer_identity_reference=node_ids["agent-alpha"],
        capability_refs=("capability.profile.scale.integration",),
    )
    applied_capability = stores["agent-beta"].apply_exchange(
        capability_exchange, event_instant=_T1
    )
    exchange_count += 1
    journal.append(
        ScaleEventType.EXCHANGE_DECLARED,
        {
            "kind": "capability-export",
            "from": "agent-alpha",
            "to": "agent-beta",
            "exchange_id": capability_exchange.exchange_id,
        },
    )
    if applied_capability.ok:
        exchange_count = exchange_count  # applied
        journal.append(
            ScaleEventType.EXCHANGE_APPLIED,
            {"kind": "capability-export", "at": "agent-beta",
             "code": str(applied_capability.code)},
        )

    rel_ac = relationship_ids[("agent-alpha", "appliance-gamma")]
    next_slot = stores["appliance-gamma"].get_relationship(rel_ac).last_event_sequence + 1
    route_exchange = FederationExchange(
        exchange_id="",
        exchange_kind=ExchangeKind.ROUTE_EXPORT,
        local_domain_id=domain_ids["agent-alpha"],
        peer_domain_id=domain_ids["appliance-gamma"],
        sequence=next_slot,
        declared_at=_T1,
        effective_at=_T1,
        peer_identity_reference=node_ids["agent-alpha"],
        route_refs=("route.scale.integration",),
    )
    applied_route = stores["appliance-gamma"].apply_exchange(
        route_exchange, event_instant=_T1
    )
    exchange_count += 1
    journal.append(
        ScaleEventType.EXCHANGE_DECLARED,
        {
            "kind": "route-export",
            "from": "agent-alpha",
            "to": "appliance-gamma",
            "exchange_id": route_exchange.exchange_id,
        },
    )
    if applied_route.ok:
        journal.append(
            ScaleEventType.EXCHANGE_APPLIED,
            {"kind": "route-export", "at": "appliance-gamma",
             "code": str(applied_route.code)},
        )
    checks.append((
        "capability-exchange-applied",
        applied_capability.ok,
        "capability declaration applied at the peer agent store",
    ))
    checks.append((
        "route-exchange-applied",
        applied_route.ok,
        "route declaration applied at the appliance federation store",
    ))

    # -- 6. revocation: agent-alpha revokes the appliance relationship
    #        (isolation: the agent-beta relationship stays untouched).
    digests_before = {
        label: _store_digest(stores[label]) for label in _INTEGRATION_LABELS
    }
    revoke_result = stores["agent-alpha"].revoke_relationship(
        rel_ac, event_instant=_T1, reason="integration-revocation"
    )
    checks.append((
        "authoritative-revocation",
        revoke_result.ok,
        "the appliance relationship revoked at the issuing agent store",
    ))
    next_slot = stores["appliance-gamma"].get_relationship(rel_ac).last_event_sequence + 1
    revocation_exchange = FederationExchange(
        exchange_id="",
        exchange_kind=ExchangeKind.REVOCATION,
        local_domain_id=domain_ids["agent-alpha"],
        peer_domain_id=domain_ids["appliance-gamma"],
        sequence=next_slot,
        declared_at=_T1,
        effective_at=_T1,
        peer_identity_reference=node_ids["agent-alpha"],
        reason="integration-revocation",
    )
    applied_revocation = stores["appliance-gamma"].apply_exchange(
        revocation_exchange, event_instant=_T1
    )
    exchange_count += 1
    journal.append(
        ScaleEventType.REVOCATION_ISSUED,
        {"revoking": "agent-alpha", "subject": "appliance-gamma"},
    )
    checks.append((
        "revocation-propagated",
        applied_revocation.ok,
        "the revocation declaration applied at the appliance federation store",
    ))
    appliance_relationship = stores["appliance-gamma"].get_relationship(rel_ac)
    checks.append((
        "appliance-relationship-revoked",
        appliance_relationship is not None
        and appliance_relationship.state == RelationshipState.REVOKED,
        "the appliance store observes the terminal REVOKED state",
    ))
    scope_check = stores["appliance-gamma"].check_scope(
        rel_ac, Scope.CAPABILITY_READ, evaluation_instant=_T1
    )
    checks.append((
        "appliance-scope-closed",
        not scope_check.ok and str(scope_check.code) == "relationship-terminal",
        "scope evaluation fails closed at the appliance store after revocation",
    ))
    journal.append(
        ScaleEventType.SCOPE_CLOSED,
        {"at": "appliance-gamma", "code": str(scope_check.code)},
    )

    # isolation: agent-beta's store is byte-identical across the
    # revocation window; agent-alpha changed ONLY through its own
    # authoritative operations.
    digests_after = {
        label: _store_digest(stores[label]) for label in _INTEGRATION_LABELS
    }
    beta_unchanged = digests_before["agent-beta"] == digests_after["agent-beta"]
    checks.append((
        "isolation-agent-beta",
        beta_unchanged,
        "the unrelated agent store is digest-identical across the revocation",
    ))
    journal.append(
        ScaleEventType.ISOLATION_PROVEN,
        {"failed": [], "holds": beta_unchanged, "note": "revocation isolation"},
    )

    # idempotent replay of the revocation declaration
    replay = stores["appliance-gamma"].apply_exchange(
        revocation_exchange, event_instant=_T1
    )
    checks.append((
        "revocation-replay-idempotent",
        replay.ok and str(replay.code) == "replayed",
        "re-delivering the revocation is an idempotent replay",
    ))

    journal.append(
        ScaleEventType.SCENARIO_COMPLETED,
        {"exchanges": exchange_count, "checks": len(checks)},
    )

    store_digests = tuple(
        (label, _store_digest(stores[label])) for label in _INTEGRATION_LABELS
    )
    return IntegrationResult(
        journal=journal.events,
        store_digests=store_digests,
        checks=tuple(checks),
        relationship_count=len(pairs),
        grant_count=grant_count,
        exchange_count=exchange_count,
    )


def _store_digest(store: Any) -> str:
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes(store.snapshot())
    ).hexdigest()


def verify_integration_replay(*, expected_digest: str) -> Dict[str, Any]:
    """TRUE replay verification: re-run the integration scenario and
    compare the complete run digest."""
    replay = run_integration_scenario()
    digest = replay.run_digest()
    return {
        "verified": digest == expected_digest,
        "expected_digest": expected_digest,
        "observed_digest": digest,
    }
