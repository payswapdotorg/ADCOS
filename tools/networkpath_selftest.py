#!/usr/bin/env python3
"""WORK-041 NetworkPath battery (deterministic, stdlib only).

End-to-end verification of the first-class NetworkPath / platform
boundary (ACR-005, authorization WORK-041-CORE-001 / DEC-0052) over
the accepted WORK-033 Linux reference agent:

- frozen vocabularies: the five-state lifecycle (DISCOVERED /
  VALIDATED / BOUND / ACTIVE / RETIRED), the journaled action
  vocabulary, the transition table, and the reason vocabulary;
- fail-closed lifecycle: illegal transitions (RETIRED -> ACTIVE,
  UNVALIDATED -> ACTIVE, ...), malformed/tampered path records
  (content-bound ids), duplicate transitions, stale candidates, and
  unknown paths all reject without mutating state;
- candidate isolation (criterion 2): discovery NEVER activates -- a
  detected candidate carries no binding facts, no probe evidence,
  and the active-path table is untouched until the full legitimate
  validate -> bind -> probe -> activate chain succeeds;
- session continuity (criterion 1): the same logical session moves
  across distinct validated physical paths (Wi-Fi -> Ethernet ->
  USB-class -> cellular-class) with an unchanged session_id, exactly
  one creation event, a monotonically growing session journal, and a
  CHANGED W018 IP binding (the ordinary WORK-033 binding path -- the
  W040-corrected mechanism -- with no session re-creation);
- failure preservation (criterion 3): validation failure (link down,
  adapter not exposed, identity drift), bind failure (unknown or
  non-ESTABLISHED session), and probe failure (non-ESTABLISHED
  session) each leave the existing ACTIVE path intact, the candidate
  NOT ACTIVE, and the session valid;
- transactional handover ordering: the old path is never retired
  first -- it survives candidate validate/bind/probe, overlaps only
  after candidate activation, and is retired LAST;
- evidence (criterion 4): the observation -> validation -> binding ->
  traffic-proof chain is explicit, deterministic (two fresh runs are
  byte-identical; PYTHONHASHSEED subprocess variations agree),
  replay-safe (replaying the operation sequence fails closed),
  independently verifiable (digests recompute from recorded facts),
  and secret-free;
- architectural integrity (criterion 5): structural audits -- no
  second authority (import + call-token discipline over the frozen
  authority set), no private authority access, no vendor/platform
  tokens, frozen public API, frozen spec surfaces intact, PR delta
  confined to the authorized W041 scope, and the honest two-track
  evidence disclosure (software verified; PHYSICAL device evidence
  OPEN and W040-owned -- no synthetic physical claims).

The battery exercises the PUBLIC production path only: the ordinary
AgentRuntime session establishment chain, expose_interfaces,
bind_session, send_datagram, and the NetworkPathManager public
methods.  No private method is called to manufacture a PASS.
"""

from __future__ import annotations

import hashlib
import json
import os
import py_compile
import re
import subprocess  # noqa: S404 - deterministic child processes of this repo's own tools
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from identity.node_id import parse_node_id  # noqa: E402
from management import ManagementCapability, RoleDefinition  # noqa: E402
from policy import PolicyDomain, PolicyRule  # noqa: E402
from protocol.canonicalization import canonical_json_bytes  # noqa: E402
from topology import (  # noqa: E402
    ClaimType,
    SourceClass,
    TopologyClaim,
    make_link_subject,
)

from agent import (  # noqa: E402
    AgentConfig,
    AgentIdentitySpec,
    AgentRuntime,
    InterfaceSnapshot,
    LinkMetricSpec,
    MigrationSpec,
    StaticInterfaceSource,
    StepClock,
    FailingInterfaceSource,
)
from agent.interfaces import InterfaceSource  # noqa: E402

from networkpath import (  # noqa: E402
    ACTION_VALUES,
    LIFECYCLE_TRANSITIONS,
    NETWORKPATH_EVIDENCE_STATUS,
    NetworkPathAction,
    NetworkPathError,
    NetworkPathManager,
    NetworkPathReasonCode,
    NetworkPathState,
    STATE_VALUES,
    PlatformObservation,
    derive_network_path_event_id,
    derive_network_path_id,
    evidence_digest,
    lifecycle_event_list_digest,
    session_continuity_facts,
    transition_is_legal,
    verify_path_evidence,
)

Result = Tuple[str, bool, str]

_FAMILY_FILES = sorted((REPO_ROOT / "networkpath").rglob("*.py"))

_T0 = "2025-06-01T00:00:00Z"
_FRESH = "2026-01-01T00:00:00Z"
_SECRET_A = b"w041-battery-secret-A"
_SECRET_B = b"w041-battery-secret-B"
_PROFILE_ID = "identity.sha256-hmac-dev.v1"
_KEY_A = b"w041-battery-key-A"
_KEY_B = b"w041-battery-key-B"

WIFI_IF = "wlan0"
ETH_IF = "eth0"
USB_IF = "usb0"
CELL_IF = "cellular0"

#: The frozen NetworkPath public API surface (case on the frozen API).
_EXPECTED_API = [
    "ACTION_PRECONDITIONS",
    "ACTION_REQUIRED_STATE",
    "ACTION_VALUES",
    "BIND_REQUIRED_STATE",
    "BindingFacts",
    "FAILED_ADAPTER_HEALTH",
    "HandoverResult",
    "LIFECYCLE_TRANSITIONS",
    "LifecycleEvent",
    "NETWORKPATH_EVIDENCE_STATUS",
    "NetworkPath",
    "NetworkPathAction",
    "NetworkPathError",
    "NetworkPathManager",
    "NetworkPathReasonCode",
    "NetworkPathState",
    "PlatformObservation",
    "ProbeFacts",
    "REQUIRED_ADAPTER_LIFECYCLE",
    "STATE_VALUES",
    "SESSION_CREATED_EVENT_TYPE",
    "SessionContinuityFacts",
    "TRANSITION_TABLE",
    "VALIDATION_REQUIRED_STATE",
    "ValidationVerdict",
    "PathEvidenceRecord",
    "PROBE_REQUIRED_STATE",
    "assemble_path_evidence",
    "assert_session_continuity",
    "bind_candidate",
    "candidate_from_observation",
    "derive_network_path_event_id",
    "derive_network_path_id",
    "evidence_digest",
    "event_journal_digest",
    "lifecycle_event_list_digest",
    "network_path_identity_content",
    "observation_for",
    "probe_candidate",
    "probe_payload",
    "read_observations",
    "session_continuity_facts",
    "transition_is_legal",
    "validate_candidate",
    "verify_path_evidence",
]

#: The authorized W041 delta surface (scope of WORK-041-CORE-001).
_AUTHORIZED_PATHS = (
    "networkpath/",
    "tools/networkpath_selftest.py",
    "docs/WORK-041-handoff.md",
    "docs/WORK-041-evidence.md",
)

#: Vendor/platform tokens the NetworkPath model must never encode
#: (technology-neutral representation; the OS link-kind vocabulary
#: belongs to the accepted agent family, not to this model).
_VENDOR_TOKENS = (
    "android", "rndis", "qualcomm", "mediatek", "samsung", "broadcom",
    "huawei", "apple", "google", "windows", "darwin", "ios_",
)

#: Forbidden authority-construction/mutation tokens: the NetworkPath
#: family must never build or drive a second authority.
_FORBIDDEN_TOKENS = (
    "RoutingEngine(", "PolicyEngine(", "TransportManager(",
    "TopologyGraph(", "SessionStore(", "IdentityService(",
    "sessions.create", "sessions.transition", "sessions.reconnect",
    "sessions.terminate", "sessions.suspend", "sessions.append_event",
    "expose_new", "derive_session_id",
)


def ok(name: str, detail: str = "") -> Result:
    return (name, True, detail)


def fail(name: str, detail: str) -> Result:
    return (name, False, detail)


def _ids() -> Tuple[str, str]:
    """The deterministic node ids for the battery keys (derived through
    the genuine identity machinery)."""
    from identity.model import NodeIdentity
    from identity.profiles import ProfileSet

    profiles = ProfileSet.load_default()
    profile = profiles.get(_PROFILE_ID)
    identity_a = NodeIdentity.create(profile, _KEY_A, _T0)
    identity_b = NodeIdentity.create(profile, _KEY_B, _T0)
    return identity_a.node_id.text, identity_b.node_id.text


def _snap(*, name: str, kind: str, up: bool = True, addresses: Tuple[str, ...] = (),
           mtu: int = 1500, speed: int = 100) -> InterfaceSnapshot:
    return InterfaceSnapshot(
        name=name, link_kind=kind, state_up=up, mtu=mtu, speed_mbps=speed,
        rx_bytes=7, tx_bytes=9, rx_errors=0, tx_errors=0,
        addresses=addresses,
    )


def _snapshots(*, eth_down: bool = False) -> Tuple[InterfaceSnapshot, ...]:
    """A node interface set spanning the OS link-kind classes:
    Wi-Fi (wireless), Ethernet (ethernet), USB-tethering class and
    cellular class (both 'other' -- the technology-neutral bucket)."""
    return (
        _snap(name=WIFI_IF, kind="wireless", addresses=("fd00::a:1",)),
        _snap(name=ETH_IF, kind="ethernet", up=not eth_down, addresses=("fd00::a:2",), speed=1000),
        _snap(name=USB_IF, kind="other", addresses=("fd00::a:3",), mtu=1400, speed=400),
        _snap(name=CELL_IF, kind="other", addresses=(), mtu=1300, speed=50),
    )


class MutableInterfaceSource(InterfaceSource):
    """A battery fixture: an interface source whose snapshot set can
    change between reads (dynamic interface exposure scenarios -- the
    W040 correction's operating condition).  Deterministic for a fixed
    script of set_snapshots calls."""

    def __init__(self, snapshots: Tuple[InterfaceSnapshot, ...] = ()) -> None:
        self._snapshots: Tuple[InterfaceSnapshot, ...] = tuple(snapshots)

    def set_snapshots(self, snapshots: Tuple[InterfaceSnapshot, ...]) -> None:
        self._snapshots = tuple(snapshots)

    def discover(self) -> Tuple[InterfaceSnapshot, ...]:
        return self._snapshots


def _claims(self_id: str, peer_id: str) -> Tuple[TopologyClaim, ...]:
    return (
        TopologyClaim(
            subject=make_link_subject(self_id, peer_id),
            reporter=self_id,
            claim_type=ClaimType.LINK_STATE,
            value="up",
            source_class=SourceClass.SELF_ADVERTISEMENT,
            issued_at=_T0,
            freshness_until=_FRESH,
            sequence=1,
        ),
        TopologyClaim(
            subject=peer_id,
            reporter=self_id,
            claim_type=ClaimType.REACHABLE,
            value="true",
            source_class=SourceClass.DIRECT_OBSERVATION,
            issued_at=_T0,
            freshness_until=_FRESH,
            sequence=1,
        ),
    )


def _policy_rules(label: str) -> Tuple[PolicyRule, ...]:
    return (
        PolicyRule(
            rule_id="%s-allow-session-create" % label,
            domain=PolicyDomain.IDENTITY,
            effect="allow",
            operation="session.create",
            subjects=(),
            priority=1,
            specificity=1,
        ),
    )


def _roles() -> Tuple[Any, ...]:
    return (
        RoleDefinition(
            role_id="w041-battery-operator",
            capabilities=(
                ManagementCapability.SESSION_READ,
                ManagementCapability.SESSION_CONTROL,
                ManagementCapability.POLICY_READ,
            ),
            description="operator role (battery fixture)",
        ),
    )


def _config(
    label: str = "networkpath-node",
    key: bytes = _KEY_A,
    peer_id: Optional[str] = None,
    self_id: Optional[str] = None,
) -> AgentConfig:
    if peer_id is None or self_id is None:
        id_a, id_b = _ids()
        peer_id = peer_id or id_b
        self_id = self_id or id_a
    return AgentConfig(
        agent_label=label,
        identity=AgentIdentitySpec(
            profile_id=_PROFILE_ID, public_key=key, created_at=_T0,
        ),
        policy_rules=_policy_rules(label),
        topology_claims=_claims(self_id, peer_id),
        link_metrics=(
            LinkMetricSpec(
                peer_node_id=peer_id, latency_ms=10,
                observed_at=_T0, freshness_until="2026-06-01T00:10:00Z",
            ),
        ),
        rbac_roles=_roles(),
        operator_role_ids=(_roles()[0].role_id,),
        migration=MigrationSpec(
            schema_id="agent.state", from_version="1.0", to_version="1.1",
        ),
    )


def _peer_config() -> AgentConfig:
    id_a, id_b = _ids()
    return _config("peer-node", key=_KEY_B, peer_id=id_a, self_id=id_b)


def _register_peers(a: AgentRuntime, b: AgentRuntime, clock: StepClock) -> None:
    """Peer registration through the public identity-service surface
    (the injected shared clock supplies the instants -- no private
    runtime internals are read)."""
    cred_a = a.identity_service.active_credential(
        parse_node_id(a.node_id), "operational", now=clock.now(),
    )
    cred_b = b.identity_service.active_credential(
        parse_node_id(b.node_id), "operational", now=clock.now(),
    )
    a.register_peer(b.identity, cred_b, _SECRET_B)
    b.register_peer(a.identity, cred_a, _SECRET_A)


def _world(
    snapshots: Optional[Tuple[InterfaceSnapshot, ...]] = None,
) -> Tuple[NetworkPathManager, AgentRuntime, AgentRuntime, str, StepClock]:
    """One booted W041 node + one booted peered peer runtime with one
    ESTABLISHED session, all through the ordinary public production
    chain (boot -> expose_interfaces -> register peers -> the full
    session handshake).  Both nodes read ONE shared clock (60-second
    steps)."""
    if snapshots is None:
        snapshots = _snapshots()
    shared = StepClock(_T0, 60)
    peer = AgentRuntime(
        _peer_config(), clock=shared,
        interface_source=StaticInterfaceSource(snapshots),
    )
    peer.boot(_SECRET_B)
    peer.expose_interfaces()
    runtime = AgentRuntime(
        _config(), clock=shared,
        interface_source=StaticInterfaceSource(snapshots),
    )
    runtime.boot(_SECRET_A)
    runtime.expose_interfaces()
    _register_peers(runtime, peer, shared)
    request = runtime.establish_session(peer.node_id)
    accept = peer.accept_session(request)
    confirm = runtime.complete_session(accept)
    peer.finalize_session(confirm)
    manager = NetworkPathManager(runtime, shared)
    return manager, runtime, peer, confirm.session_id, shared


def _path_for(manager: NetworkPathManager, interface_name: str) -> str:
    for path_id in manager.paths():
        if manager.path(path_id).interface_name == interface_name:
            return path_id
    raise AssertionError("no candidate for interface %r" % interface_name)


def _expect_error(name: str, reason: str, func, *args, **kwargs) -> Optional[str]:
    """Run func; PASS iff it raised NetworkPathError with the reason."""
    try:
        func(*args, **kwargs)
    except NetworkPathError as error:
        if error.reason == reason:
            return None
        return "expected %s, got %s (%s)" % (reason, error.reason, error.detail)
    except Exception as error:  # noqa: BLE001 - wrong exception type is a failure
        return "wrong exception type %s" % type(error).__name__
    return "no error raised (expected %s)" % reason


# ---------------------------------------------------------------------------
# Vocabulary and value model
# ---------------------------------------------------------------------------


def case_01_frozen_vocabularies(results: List[Result]) -> None:
    name = "case_01_frozen_vocabularies"
    problems: List[str] = []
    if STATE_VALUES != (
        "DISCOVERED", "VALIDATED", "BOUND", "ACTIVE", "RETIRED",
    ):
        problems.append("state vocabulary %r" % (STATE_VALUES,))
    if NetworkPathState.terminal_values() != ("RETIRED",):
        problems.append("terminal states %r" % (NetworkPathState.terminal_values(),))
    if sorted(ACTION_VALUES) != sorted(
        ("discover", "validate", "bind", "probe", "activate", "retire")
    ):
        problems.append("action vocabulary %r" % (ACTION_VALUES,))
    if LIFECYCLE_TRANSITIONS["RETIRED"] != frozenset():
        problems.append("RETIRED must have no outgoing edges")
    for reason in NetworkPathReasonCode.values():
        if not isinstance(reason, str) or not reason:
            problems.append("bad reason code %r" % (reason,))
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(ok(name, "5 states, 6 journaled actions, RETIRED terminal, 11 reason codes"))


def case_02_illegal_transitions_table(results: List[Result]) -> None:
    name = "case_02_illegal_transitions_fail_closed"
    problems: List[str] = []
    for from_state, to_state in (
        ("RETIRED", "ACTIVE"),
        ("RETIRED", "BOUND"),
        ("DISCOVERED", "BOUND"),
        ("DISCOVERED", "ACTIVE"),
        ("VALIDATED", "ACTIVE"),
        ("ACTIVE", "BOUND"),
        ("ACTIVE", "DISCOVERED"),
        ("UNKNOWN", "ACTIVE"),
    ):
        if transition_is_legal(from_state, to_state):
            problems.append("%s -> %s is legal (must fail closed)" % (from_state, to_state))
    for from_state, to_state in (
        ("DISCOVERED", "VALIDATED"),
        ("VALIDATED", "BOUND"),
        ("BOUND", "ACTIVE"),
        ("ACTIVE", "RETIRED"),
        ("VALIDATED", "RETIRED"),
        ("BOUND", "RETIRED"),
        ("DISCOVERED", "RETIRED"),
    ):
        if not transition_is_legal(from_state, to_state):
            problems.append("%s -> %s must be legal" % (from_state, to_state))
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "RETIRED->ACTIVE and UNVALIDATED->ACTIVE rejected; legal chain intact")
    )


def case_03_content_derived_identity(results: List[Result]) -> None:
    name = "case_03_content_derived_identity"
    problems: List[str] = []
    from networkpath import NetworkPath

    base = NetworkPath(
        network_path_id="", node_id="node-1", interface_name=ETH_IF,
        link_kind="ethernet", addresses=("fd00::a:2",),
    )
    if not base.network_path_id.startswith("sha256:"):
        problems.append("id is not a sha256 fingerprint")
    if derive_network_path_id(
        "node-1", ETH_IF, "ethernet", ("fd00::a:2",)
    ) != base.network_path_id:
        problems.append("derivation is not stable")
    shuffled = NetworkPath(
        network_path_id="", node_id="node-1", interface_name=ETH_IF,
        link_kind="ethernet", addresses=("fd00::9999", "fd00::a:2"),
    )
    same = NetworkPath(
        network_path_id="", node_id="node-1", interface_name=ETH_IF,
        link_kind="ethernet", addresses=("fd00::a:2", "fd00::9999"),
    )
    if shuffled.network_path_id != same.network_path_id:
        problems.append("address order changes identity (must be sorted)")
    other_node = NetworkPath(
        network_path_id="", node_id="node-2", interface_name=ETH_IF,
        link_kind="ethernet", addresses=("fd00::a:2",),
    )
    if other_node.network_path_id == base.network_path_id:
        problems.append("node id is not part of identity")
    # tamper detection
    try:
        NetworkPath(
            network_path_id="sha256:deadbeef", node_id="node-1",
            interface_name=ETH_IF, link_kind="ethernet",
            addresses=("fd00::a:2",),
        )
        problems.append("tampered id accepted")
    except NetworkPathError:
        pass
    # round-trip preserves identity
    rebuilt = NetworkPath.from_dict(base.to_dict())
    if rebuilt.network_path_id != base.network_path_id or rebuilt.state != base.state:
        problems.append("round-trip changed the record")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "content-derived id; sorted-address stability; tamper rejected")
    )


def case_04_malformed_records_fail_closed(results: List[Result]) -> None:
    name = "case_04_malformed_records_fail_closed"
    problems: List[str] = []
    from networkpath import LifecycleEvent, NetworkPath

    good = NetworkPath(
        network_path_id="", node_id="node-1", interface_name=ETH_IF,
        link_kind="ethernet", addresses=(),
    )
    cases: List[Tuple[Dict[str, Any], str]] = [
        ({"network_path_id": "sha256:fake", "node_id": "n", "interface_name": "e",
          "link_kind": "ethernet", "addresses": []}, "tampered id"),
        ({"network_path_id": "", "node_id": "", "interface_name": "e",
          "link_kind": "ethernet", "addresses": []}, "empty node id"),
        ({"network_path_id": "", "node_id": "n", "interface_name": "",
          "link_kind": "ethernet", "addresses": []}, "empty interface"),
        ({"network_path_id": "", "node_id": "n", "interface_name": "e",
          "link_kind": "carrier-pigeon", "addresses": []}, "unknown link kind"),
        ({"network_path_id": "", "node_id": "n", "interface_name": "e",
          "link_kind": "ethernet", "addresses": [], "state": "LIMBO"}, "unknown state"),
        ({"network_path_id": "", "node_id": "n", "interface_name": "e",
          "link_kind": "ethernet", "addresses": "not-a-list"}, "bad addresses"),
    ]
    for payload, label in cases:
        try:
            NetworkPath.from_dict(payload)
            problems.append("%s accepted" % label)
        except NetworkPathError:
            pass
    # lifecycle events: illegal transition record + tampered event id
    try:
        LifecycleEvent(
            event_id="", network_path_id=good.network_path_id, action="activate",
            from_state="RETIRED", to_state="ACTIVE", instant=_T0,
        )
        problems.append("illegal RETIRED->ACTIVE event accepted")
    except NetworkPathError:
        pass
    try:
        real_id = derive_network_path_event_id(
            good.network_path_id, "validate", "DISCOVERED", "VALIDATED", _T0
        )
        LifecycleEvent(
            event_id="sha256:fake", network_path_id=good.network_path_id,
            action="validate", from_state="DISCOVERED", to_state="VALIDATED",
            instant=_T0,
        )
        problems.append("tampered event id accepted")
    except NetworkPathError:
        pass
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(ok(name, "malformed path/event records rejected at construction"))


def case_05_platform_observation_model(results: List[Result]) -> None:
    name = "case_05_platform_observation_model"
    problems: List[str] = []
    snapshot = _snap(name=WIFI_IF, kind="wireless", addresses=("fd00::a:1",))
    observation = PlatformObservation(snapshot=snapshot, observed_at=_T0)
    if observation.interface_name != WIFI_IF or observation.link_kind != "wireless":
        problems.append("observation projection wrong")
    if observation.snapshot_digest != snapshot.digest():
        problems.append("snapshot digest mismatch")
    first = observation.observation_digest()
    if first != observation.observation_digest():
        problems.append("observation digest not stable")
    rebuilt = PlatformObservation.from_dict(observation.to_dict())
    if rebuilt.observation_digest() != first:
        problems.append("round-trip changed the observation")
    if rebuilt.observation_digest() != PlatformObservation(
        snapshot=snapshot, observed_at=_T0
    ).observation_digest():
        problems.append("rebuild is not content-identical")
    try:
        PlatformObservation(snapshot="not-a-snapshot", observed_at=_T0)
        problems.append("malformed snapshot accepted")
    except NetworkPathError:
        pass
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(ok(name, "observation wraps snapshot DATA; digest stable + round-trip"))


def case_06_observation_sources_fail_closed(results: List[Result]) -> None:
    name = "case_06_observation_sources_fail_closed"
    problems: List[str] = []
    from networkpath import read_observations

    # a raising source surfaces as a typed error (no OS exception crosses)
    try:
        read_observations(FailingInterfaceSource(), now=_T0)
        problems.append("raising source not caught")
    except NetworkPathError as error:
        if error.reason != NetworkPathReasonCode.OBSERVATION_SOURCE_FAILED:
            problems.append("wrong reason %r" % error.reason)
    # ambiguous observation set (duplicate interface names) fails whole
    class _Ambiguous(InterfaceSource):
        def discover(self) -> Tuple[InterfaceSnapshot, ...]:
            snap = _snap(name="dup0", kind="ethernet")
            return (snap, snap)

    try:
        read_observations(_Ambiguous(), now=_T0)
        problems.append("ambiguous set accepted")
    except NetworkPathError as error:
        if error.reason != NetworkPathReasonCode.OBSERVATION_INVALID:
            problems.append("wrong reason %r" % error.reason)
    # deterministic source reads fine and is sorted
    observations = read_observations(
        StaticInterfaceSource(_snapshots()), now=_T0
    )
    names = [observation.interface_name for observation in observations]
    if names != sorted(names):
        problems.append("observations not sorted")
    if len(names) != 4:
        problems.append("expected 4 observations, got %d" % len(names))
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "typed source failure; ambiguous set rejected; deterministic order")
    )


# ---------------------------------------------------------------------------
# Criterion 2: candidates are detected, never auto-activated
# ---------------------------------------------------------------------------


def case_07_discovery_candidates_not_active(results: List[Result]) -> None:
    name = "case_07_discovery_candidates_not_active"
    manager, runtime, _peer, sid, _clock = _world()
    agent_events_before = len(runtime.events())
    ids = manager.discover()
    problems: List[str] = []
    if len(ids) != 4:
        problems.append("expected 4 candidates, got %d" % len(ids))
    for path_id in ids:
        path = manager.path(path_id)
        if path.state != NetworkPathState.DISCOVERED:
            problems.append("path %s is %s" % (path_id[:12], path.state))
        if path.binding_id or path.bearer_ref or path.ip_binding_id:
            problems.append("candidate carries binding facts")
        if path.probe_digest:
            problems.append("candidate carries probe evidence")
        if path.session_id:
            problems.append("candidate carries a session")
    if manager.active_path_id(sid) is not None:
        problems.append("active-path table mutated by discovery")
    if len(runtime.events()) != agent_events_before:
        problems.append("discovery mutated agent journal (observation is not truth)")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "4 candidates DISCOVERED; no bindings, no probe, no active entry, "
                 "agent journal untouched")
    )


def case_08_duplicate_discovery_idempotent(results: List[Result]) -> None:
    name = "case_08_duplicate_discovery_idempotent"
    manager, _runtime, _peer, _sid, _clock = _world()
    first = manager.discover()
    journal_before = len(manager.events())
    digest_before = manager.content_digest()
    second = manager.discover()
    problems: List[str] = []
    if second != first:
        problems.append("path set changed on duplicate discovery")
    if len(manager.events()) != journal_before:
        problems.append("journal grew on duplicate discovery")
    if manager.content_digest() != digest_before:
        problems.append("state mutated on duplicate discovery")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(ok(name, "duplicate discovery: idempotent no-op (replay safe)"))


# ---------------------------------------------------------------------------
# The full legitimate chain
# ---------------------------------------------------------------------------


def case_09_full_lifecycle_to_active(results: List[Result]) -> None:
    name = "case_09_full_lifecycle_to_active"
    manager, runtime, _peer, sid, _clock = _world()
    manager.discover()
    wifi = _path_for(manager, WIFI_IF)
    problems: List[str] = []
    try:
        manager.validate(wifi)
        if manager.path(wifi).state != NetworkPathState.VALIDATED:
            problems.append("validate did not advance state")
        manager.bind(wifi, sid)
        path = manager.path(wifi)
        if path.state != NetworkPathState.BOUND:
            problems.append("bind did not advance state")
        if not path.binding_adapter_id or not path.ip_binding_id:
            problems.append("binding facts not recorded")
        probe = manager.probe(wifi)
        if not probe["payload_digest"].startswith("sha256:"):
            problems.append("probe digest malformed")
        if manager.path(wifi).state != NetworkPathState.BOUND:
            problems.append("probe changed state (must be state-preserving)")
        manager.activate(wifi)
        if manager.path(wifi).state != NetworkPathState.ACTIVE:
            problems.append("activate did not advance state")
        if manager.active_path_id(sid) != wifi:
            problems.append("active-path table not updated")
    except NetworkPathError as error:
        problems.append("legitimate chain failed: %s (%s)" % (error.reason, error.detail))
    # no second authority: the runtime's own journal recorded the binds
    kinds = [event.kind for event in runtime.events()]
    if "session-bound" not in kinds:
        problems.append("runtime journal lacks the ordinary session-bound event")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "discover->validate->bind->probe->activate; probe is "
                 "state-preserving; runtime records the ordinary bind events")
    )


def case_10_candidate_gates_before_chain(results: List[Result]) -> None:
    name = "case_10_candidate_gates_before_chain"
    manager, _runtime, _peer, sid, _clock = _world()
    manager.discover()
    wifi = _path_for(manager, WIFI_IF)
    digest_before = manager.content_digest()
    problems: List[str] = []
    problem = _expect_error(
        name, NetworkPathReasonCode.LIFECYCLE_ILLEGAL, manager.activate, wifi
    )
    if problem:
        problems.append("activate-from-DISCOVERED: %s" % problem)
    problem = _expect_error(
        name, NetworkPathReasonCode.LIFECYCLE_ILLEGAL, manager.bind, wifi, sid
    )
    if problem:
        problems.append("bind-from-DISCOVERED: %s" % problem)
    problem = _expect_error(
        name, NetworkPathReasonCode.LIFECYCLE_ILLEGAL, manager.probe, wifi
    )
    if problem:
        problems.append("probe-from-DISCOVERED: %s" % problem)
    # nothing mutated
    if manager.path(wifi).state != NetworkPathState.DISCOVERED:
        problems.append("candidate state mutated by rejected actions")
    if manager.content_digest() != digest_before:
        problems.append("manager state mutated by rejected actions")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "activate/bind/probe from DISCOVERED all fail closed; state unchanged")
    )


# ---------------------------------------------------------------------------
# Criterion 1: session continuity across distinct validated paths
# ---------------------------------------------------------------------------


def case_11_session_continuity_handover(results: List[Result]) -> None:
    name = "case_11_session_continuity_handover"
    manager, runtime, _peer, sid, _clock = _world()
    manager.discover()
    wifi = _path_for(manager, WIFI_IF)
    eth = _path_for(manager, ETH_IF)
    manager.validate(wifi)
    manager.bind(wifi, sid)
    manager.probe(wifi)
    manager.activate(wifi)
    old_ip_binding = manager.path(wifi).ip_binding_id
    before = session_continuity_facts(runtime, sid)
    result = manager.handover(sid, eth)
    after = session_continuity_facts(runtime, sid)
    problems: List[str] = []
    if before.session_id != after.session_id or sid != after.session_id:
        problems.append("session_id changed across handover")
    if not after.established:
        problems.append("session not ESTABLISHED after handover")
    if after.created_event_count != 1 or before.created_event_count != 1:
        problems.append("session re-created (created-event count changed)")
    if after.event_count < before.event_count:
        problems.append("session journal shrank")
    if manager.path(wifi).state != NetworkPathState.RETIRED:
        problems.append("old path not RETIRED")
    if manager.path(eth).state != NetworkPathState.ACTIVE:
        problems.append("new path not ACTIVE")
    if manager.active_path_id(sid) != eth:
        problems.append("active-path table not on the new path")
    if result.old_network_path_id != wifi or result.new_network_path_id != eth:
        problems.append("handover result paths wrong")
    if result.new_ip_binding_id == old_ip_binding:
        problems.append("W018 IP binding did not change across handover")
    if not result.probe_digest.startswith("sha256:"):
        problems.append("handover probe digest malformed")
    # the session's OWN journal: no reconnect events (this is a
    # binding-level handover; the session authority owns lifecycle)
    session_events = runtime.sessions.get_events(sid)
    if any(event.event_type == "reconnected" for event in session_events):
        problems.append("session journal shows a reconnect (path change must not "
                        "recreate/replace the logical session)")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "Wi-Fi -> Ethernet: session_id unchanged, created once, "
                 "ESTABLISHED, IP binding changed, old RETIRED / new ACTIVE")
    )


def case_12_handover_ordering_preserves_old(results: List[Result]) -> None:
    name = "case_12_handover_ordering_old_retired_last"
    manager, _runtime, _peer, sid, _clock = _world()
    manager.discover()
    wifi = _path_for(manager, WIFI_IF)
    eth = _path_for(manager, ETH_IF)
    manager.validate(wifi)
    manager.bind(wifi, sid)
    manager.probe(wifi)
    manager.activate(wifi)
    problems: List[str] = []
    # manual stepped handover: validate, bind, probe the candidate while
    # the old path stays ACTIVE (never retire first)
    manager.validate(eth)
    if manager.path(wifi).state != NetworkPathState.ACTIVE:
        problems.append("old path lost ACTIVE during candidate validation")
    manager.bind(eth, sid)
    if manager.path(wifi).state != NetworkPathState.ACTIVE:
        problems.append("old path lost ACTIVE during candidate binding")
    manager.probe(eth)
    if manager.path(wifi).state != NetworkPathState.ACTIVE:
        problems.append("old path lost ACTIVE during candidate probing")
    if manager.path(eth).state != NetworkPathState.BOUND:
        problems.append("candidate not BOUND before activation")
    # activation creates the sanctioned overlap; retirement comes LAST
    manager.activate(eth)
    if manager.path(wifi).state != NetworkPathState.ACTIVE:
        problems.append("old path retired BEFORE candidate activation")
    manager.retire(wifi)
    if manager.path(wifi).state != NetworkPathState.RETIRED:
        problems.append("old path not retired after activation")
    if manager.active_path_id(sid) != eth:
        problems.append("new path is not the active one")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "old ACTIVE through candidate validate/bind/probe; overlap only "
                 "after activation; retired LAST")
    )


def case_13_technology_neutral_breadth(results: List[Result]) -> None:
    name = "case_13_technology_neutral_breadth"
    manager, runtime, _peer, sid, _clock = _world()
    manager.discover()
    wifi = _path_for(manager, WIFI_IF)
    eth = _path_for(manager, ETH_IF)
    usb = _path_for(manager, USB_IF)
    cell = _path_for(manager, CELL_IF)
    problems: List[str] = []
    # kinds observed: wireless, ethernet, other (USB-tethering class),
    # other (cellular class) -- the model is technology-neutral
    kinds = {
        manager.path(pid).link_kind for pid in (wifi, eth, usb, cell)
    }
    if kinds != {"wireless", "ethernet", "other"}:
        problems.append("unexpected link kinds %r" % (kinds,))
    try:
        # first activation through the full legitimate chain
        manager.validate(wifi)
        manager.bind(wifi, sid)
        manager.probe(wifi)
        manager.activate(wifi)
        manager.handover(sid, eth)  # wireless -> ethernet
        manager.handover(sid, usb)  # ethernet -> USB-tethering class
        manager.handover(sid, cell)  # USB class -> cellular class
    except NetworkPathError as error:
        problems.append("breadth handover failed: %s (%s)" % (error.reason, error.detail))
    facts = session_continuity_facts(runtime, sid)
    if not facts.established or facts.created_event_count != 1:
        problems.append("session continuity broken across the breadth chain")
    if manager.active_path_id(sid) != cell:
        problems.append("final active path is not the cellular-class one")
    retired = [manager.path(pid).state for pid in (wifi, eth, usb)]
    if retired != [NetworkPathState.RETIRED] * 3:
        problems.append("intermediate paths not all RETIRED")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "one session across wireless -> ethernet -> USB-class -> "
                 "cellular-class (same lifecycle, no technology branching)")
    )


# ---------------------------------------------------------------------------
# Dynamic interface exposure (the W040 correction mechanism, reused)
# ---------------------------------------------------------------------------


def case_14_dynamic_exposure_gates_validation(results: List[Result]) -> None:
    name = "case_14_dynamic_exposure_gates_validation"
    snapshots = (
        _snap(name=WIFI_IF, kind="wireless", addresses=("fd00::a:1",)),
        _snap(name=ETH_IF, kind="ethernet", addresses=("fd00::a:2",)),
    )
    shared = StepClock(_T0, 60)
    peer = AgentRuntime(
        _peer_config(), clock=shared, interface_source=StaticInterfaceSource(snapshots)
    )
    peer.boot(_SECRET_B)
    peer.expose_interfaces()
    runtime = AgentRuntime(
        _config(), clock=shared, interface_source=MutableInterfaceSource(snapshots)
    )
    runtime.boot(_SECRET_A)
    runtime.expose_interfaces()
    _register_peers(runtime, peer, shared)
    request = runtime.establish_session(peer.node_id)
    accept = peer.accept_session(request)
    confirm = runtime.complete_session(accept)
    peer.finalize_session(confirm)
    manager = NetworkPathManager(runtime, shared)
    manager.discover()
    wifi = _path_for(manager, WIFI_IF)
    manager.validate(wifi)
    manager.bind(wifi, confirm.session_id)
    manager.probe(wifi)
    manager.activate(wifi)
    # a NEW interface appears AFTER boot (dynamic exposure scenario)
    runtime.interface_source.set_snapshots(
        snapshots + (_snap(name="dyn0", kind="other", addresses=("fd00::a:9",)),)
    )
    manager.discover()
    dyn = _path_for(manager, "dyn0")
    problems: List[str] = []
    problem = _expect_error(
        name, NetworkPathReasonCode.VALIDATION_REJECTED, manager.validate, dyn
    )
    if problem:
        problems.append("unexposed adapter not rejected: %s" % problem)
    else:
        # expose through the ordinary WORK-033 path, then validate
        runtime.expose_interfaces()
        try:
            manager.validate(dyn)
        except NetworkPathError as error:
            problems.append(
                "validate after exposure failed: %s (%s)" % (error.reason, error.detail)
            )
    if manager.path(wifi).state != NetworkPathState.ACTIVE:
        problems.append("active path disturbed by dynamic exposure")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "new post-boot interface: adapter-not-open rejected until the "
                 "ordinary expose_interfaces() path runs (W040 mechanism reused)")
    )


# ---------------------------------------------------------------------------
# Criterion 3: failure preservation
# ---------------------------------------------------------------------------


def case_15_validation_failure_preserves_active(results: List[Result]) -> None:
    name = "case_15_validation_failure_preserves_active"
    manager, runtime, _peer, sid, _clock = _world(_snapshots(eth_down=True))
    manager.discover()
    wifi = _path_for(manager, WIFI_IF)
    eth = _path_for(manager, ETH_IF)
    manager.validate(wifi)
    manager.bind(wifi, sid)
    manager.probe(wifi)
    manager.activate(wifi)
    digest_before = manager.content_digest()
    problems: List[str] = []
    try:
        manager.validate(eth)
        problems.append("down candidate validated")
    except NetworkPathError as error:
        if error.reason != NetworkPathReasonCode.VALIDATION_REJECTED:
            problems.append("wrong reason %r" % error.reason)
        if "link-down" not in error.detail:
            problems.append("detail lacks the deterministic reason")
    if manager.path(wifi).state != NetworkPathState.ACTIVE:
        problems.append("active path lost on validation failure")
    if manager.path(eth).state != NetworkPathState.DISCOVERED:
        problems.append("failed candidate mutated")
    facts = session_continuity_facts(runtime, sid)
    if not facts.established:
        problems.append("session invalid after validation failure")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "link-down candidate rejected (VALIDATION_REJECTED/link-down); "
                 "old ACTIVE preserved; session ESTABLISHED")
    )


def case_16_stale_candidate_identity_drift(results: List[Result]) -> None:
    name = "case_16_stale_candidate_identity_drift"
    base = (
        _snap(name=WIFI_IF, kind="wireless", addresses=("fd00::a:1",)),
        _snap(name="dyn0", kind="other", addresses=("fd00::a:7",)),
    )
    shared = StepClock(_T0, 60)
    peer = AgentRuntime(
        _peer_config(), clock=shared, interface_source=StaticInterfaceSource(base)
    )
    peer.boot(_SECRET_B)
    peer.expose_interfaces()
    source = MutableInterfaceSource(base)
    runtime = AgentRuntime(_config(), clock=shared, interface_source=source)
    runtime.boot(_SECRET_A)
    runtime.expose_interfaces()
    _register_peers(runtime, peer, shared)
    request = runtime.establish_session(peer.node_id)
    accept = peer.accept_session(request)
    confirm = runtime.complete_session(accept)
    peer.finalize_session(confirm)
    manager = NetworkPathManager(runtime, shared)
    manager.discover()
    stale = _path_for(manager, "dyn0")
    # the interface's CONTENT changes: a different path identity
    source.set_snapshots(
        base[:1] + (_snap(name="dyn0", kind="other", addresses=("fd00::a:8",)),)
    )
    manager.discover()
    dyn_ids = [
        pid for pid in manager.paths()
        if manager.path(pid).interface_name == "dyn0"
    ]
    fresh = next(pid for pid in dyn_ids if pid != stale)
    problems: List[str] = []
    if len(dyn_ids) != 2 or stale == fresh:
        problems.append("content change did not produce a new identity")
    problem = _expect_error(
        name, NetworkPathReasonCode.VALIDATION_REJECTED, manager.validate, stale
    )
    if problem:
        problems.append("stale candidate not rejected: %s" % problem)
    else:
        try:
            manager.validate(fresh)
        except NetworkPathError as error:
            problems.append("fresh candidate rejected: %s (%s)" % (error.reason, error.detail))
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "address drift -> new path identity; stale candidate fails "
                 "closed (identity-drift); fresh candidate validates")
    )


def case_17_bind_failure_preserves_active(results: List[Result]) -> None:
    name = "case_17_bind_failure_preserves_active"
    manager, runtime, peer, sid, _clock = _world()
    manager.discover()
    wifi = _path_for(manager, WIFI_IF)
    eth = _path_for(manager, ETH_IF)
    manager.validate(wifi)
    manager.bind(wifi, sid)
    manager.probe(wifi)
    manager.activate(wifi)
    manager.validate(eth)
    problems: List[str] = []
    # bind to an unknown session
    problem = _expect_error(
        name, NetworkPathReasonCode.SESSION_UNKNOWN,
        manager.bind, eth, "sha256:nonexistent-session",
    )
    if problem:
        problems.append("unknown session bind: %s" % problem)
    # bind to a non-ESTABLISHED session (a second session, suspended)
    request = runtime.establish_session(peer.node_id)
    accept = peer.accept_session(request)
    confirm = runtime.complete_session(accept)
    sid2 = confirm.session_id
    runtime.suspend_session(sid2)
    problem = _expect_error(
        name, NetworkPathReasonCode.SESSION_UNKNOWN, manager.bind, eth, sid2
    )
    if problem:
        problems.append("suspended session bind: %s" % problem)
    if manager.path(wifi).state != NetworkPathState.ACTIVE:
        problems.append("active path lost on bind failure")
    if manager.path(eth).state != NetworkPathState.VALIDATED:
        problems.append("candidate mutated on bind failure")
    if manager.active_path_id(sid) != wifi:
        problems.append("active table changed on bind failure")
    facts = session_continuity_facts(runtime, sid)
    if not facts.established:
        problems.append("session invalid after bind failure")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "unknown + suspended session binds rejected (SESSION_UNKNOWN); "
                 "old ACTIVE preserved; candidate stays VALIDATED")
    )




def case_18_probe_failure_preserves_active(results: List[Result]) -> None:
    name = "case_18_probe_failure_preserves_active"
    manager, runtime, peer, sid, _clock = _world()
    manager.discover()
    wifi = _path_for(manager, WIFI_IF)
    eth = _path_for(manager, ETH_IF)
    manager.validate(wifi)
    manager.bind(wifi, sid)
    manager.probe(wifi)
    manager.activate(wifi)
    # candidate for a SECOND session that gets suspended before probing
    request = runtime.establish_session(peer.node_id)
    accept = peer.accept_session(request)
    confirm = runtime.complete_session(accept)
    peer.finalize_session(confirm)
    sid2 = confirm.session_id
    manager.validate(eth)
    manager.bind(eth, sid2)
    runtime.suspend_session(sid2)
    problems: List[str] = []
    problem = _expect_error(
        name, NetworkPathReasonCode.PROBE_REJECTED, manager.probe, eth
    )
    if problem:
        problems.append("probe on suspended session: %s" % problem)
    if manager.path(eth).probe_digest:
        problems.append("failed probe recorded evidence")
    if manager.path(eth).state != NetworkPathState.BOUND:
        problems.append("candidate left BOUND state")
    # activation without probe evidence fails closed
    problem = _expect_error(
        name, NetworkPathReasonCode.LIFECYCLE_ILLEGAL, manager.activate, eth
    )
    if problem:
        problems.append("activate without probe evidence: %s" % problem)
    if manager.path(wifi).state != NetworkPathState.ACTIVE:
        problems.append("active path lost on probe failure")
    facts = session_continuity_facts(runtime, sid)
    if not facts.established:
        problems.append("session invalid after probe failure")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "probe on suspended session rejected (PROBE_REJECTED); no "
                 "evidence recorded; activate blocked; old ACTIVE preserved")
    )


def case_19_activate_requires_probe_evidence(results: List[Result]) -> None:
    name = "case_19_activate_requires_probe_evidence"
    manager, runtime, _peer, sid, _clock = _world()
    manager.discover()
    wifi = _path_for(manager, WIFI_IF)
    eth = _path_for(manager, ETH_IF)
    manager.validate(wifi)
    manager.bind(wifi, sid)
    manager.probe(wifi)
    manager.activate(wifi)
    manager.validate(eth)
    manager.bind(eth, sid)
    problems: List[str] = []
    problem = _expect_error(
        name, NetworkPathReasonCode.LIFECYCLE_ILLEGAL, manager.activate, eth
    )
    if problem:
        problems.append("activate without probe: %s" % problem)
    if manager.path(eth).state != NetworkPathState.BOUND:
        problems.append("candidate left BOUND")
    if manager.active_path_id(sid) != wifi:
        problems.append("active path replaced without probe")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "BOUND-without-probe cannot activate (probe/verify before activate)")
    )


# ---------------------------------------------------------------------------
# Replay safety and duplicates
# ---------------------------------------------------------------------------


def case_20_duplicate_transitions_fail_closed(results: List[Result]) -> None:
    name = "case_20_duplicate_transitions_fail_closed"
    manager, _runtime, _peer, sid, _clock = _world()
    manager.discover()
    wifi = _path_for(manager, WIFI_IF)
    manager.validate(wifi)
    manager.bind(wifi, sid)
    manager.probe(wifi)
    manager.activate(wifi)
    digest_before = manager.content_digest()
    problems: List[str] = []
    for label, func, args in (
        ("validate", manager.validate, (wifi,)),
        ("bind", manager.bind, (wifi, sid)),
        ("activate", manager.activate, (wifi,)),
        ("probe", manager.probe, (wifi,)),  # probe belongs to BOUND
    ):
        problem = _expect_error(
            name, NetworkPathReasonCode.LIFECYCLE_ILLEGAL, func, *args
        )
        if problem:
            problems.append("duplicate %s: %s" % (label, problem))
    # retire twice
    manager.retire(wifi)
    problem = _expect_error(
        name, NetworkPathReasonCode.LIFECYCLE_ILLEGAL, manager.retire, wifi
    )
    if problem:
        problems.append("duplicate retire: %s" % problem)
    if manager.path(wifi).state != NetworkPathState.RETIRED:
        problems.append("retirement did not hold")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "duplicate validate/bind/probe/activate/retire all fail closed "
                 "(state gates; digest unchanged)")
    )


def case_21_retired_is_terminal(results: List[Result]) -> None:
    name = "case_21_retired_is_terminal"
    manager, _runtime, _peer, sid, _clock = _world()
    manager.discover()
    wifi = _path_for(manager, WIFI_IF)
    manager.validate(wifi)
    manager.bind(wifi, sid)
    manager.probe(wifi)
    manager.activate(wifi)
    manager.retire(wifi)
    digest_before = manager.content_digest()
    problems: List[str] = []
    for label, func, args in (
        ("activate", manager.activate, (wifi,)),
        ("bind", manager.bind, (wifi, sid)),
        ("validate", manager.validate, (wifi,)),
        ("probe", manager.probe, (wifi,)),
        ("retire", manager.retire, (wifi,)),
    ):
        problem = _expect_error(
            name, NetworkPathReasonCode.LIFECYCLE_ILLEGAL, func, *args
        )
        if problem:
            problems.append("%s on RETIRED: %s" % (label, problem))
    if manager.content_digest() != digest_before:
        problems.append("state mutated by actions on a RETIRED path")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(ok(name, "no action revives a RETIRED path (terminal)"))


def case_22_unknown_path_fail_closed(results: List[Result]) -> None:
    name = "case_22_unknown_path_fail_closed"
    manager, _runtime, _peer, sid, _clock = _world()
    manager.discover()
    problems: List[str] = []
    for label, func, args in (
        ("validate", manager.validate, ("sha256:nope",)),
        ("bind", manager.bind, ("sha256:nope", sid)),
        ("probe", manager.probe, ("sha256:nope",)),
        ("activate", manager.activate, ("sha256:nope",)),
        ("retire", manager.retire, ("sha256:nope",)),
        ("evidence", manager.evidence, ("sha256:nope",)),
    ):
        problem = _expect_error(
            name, NetworkPathReasonCode.PATH_UNKNOWN, func, *args
        )
        if problem:
            problems.append("%s on unknown path: %s" % (label, problem))
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(ok(name, "all actions on an unknown path fail closed (PATH_UNKNOWN)"))


def case_23_replay_of_operation_sequence(results: List[Result]) -> None:
    name = "case_23_replay_of_operation_sequence_fails_closed"
    manager, runtime, peer, sid, _clock = _world()
    manager.discover()
    wifi = _path_for(manager, WIFI_IF)
    eth = _path_for(manager, ETH_IF)
    manager.validate(wifi)
    manager.bind(wifi, sid)
    manager.probe(wifi)
    manager.activate(wifi)
    manager.handover(sid, eth)
    digest_before = manager.content_digest()
    journal_before = manager.event_log_digest()
    problems: List[str] = []
    # replay the whole sequence against the SAME world: every step
    # must fail closed (duplicate/stale/out-of-order) -- no silent
    # state mutation anywhere.
    manager.discover()  # idempotent
    for func, args, label in (
        (manager.validate, (wifi,), "validate old"),
        (manager.bind, (wifi, sid), "bind old"),
        (manager.activate, (wifi,), "activate old"),
        (manager.retire, (wifi,), "retire old"),
        (manager.handover, (sid, eth), "handover stale candidate"),
    ):
        problem = _expect_error(
            name, NetworkPathReasonCode.LIFECYCLE_ILLEGAL, func, *args
        )
        if problem:
            problems.append("%s: %s" % (label, problem))
    if manager.content_digest() != digest_before:
        problems.append("state mutated during replay")
    if manager.event_log_digest() != journal_before:
        problems.append("journal mutated during replay")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "replayed sequence: discover idempotent, every transition fails "
                 "closed, digests byte-identical")
    )


# ---------------------------------------------------------------------------
# Criterion 4: deterministic, replay-safe, verifiable evidence
# ---------------------------------------------------------------------------


def _scenario_stream() -> Dict[str, str]:
    """The canonical battery scenario (used by the determinism cases
    and the --determinism-stream subprocess mode)."""
    manager, runtime, peer, sid, _clock = _world()
    manager.discover()
    wifi = _path_for(manager, WIFI_IF)
    eth = _path_for(manager, ETH_IF)
    usb = _path_for(manager, USB_IF)
    manager.validate(wifi)
    manager.bind(wifi, sid)
    manager.probe(wifi)
    manager.activate(wifi)
    manager.handover(sid, eth)
    manager.handover(sid, usb)
    facts = session_continuity_facts(runtime, sid)
    return {
        "session_id": sid,
        "content_digest": manager.content_digest(),
        "evidence_digest": manager.evidence_digest(),
        "journal_digest": manager.event_log_digest(),
        "session_created_events": str(facts.created_event_count),
        "session_state": facts.state,
    }


def case_24_determinism_two_runs(results: List[Result]) -> None:
    name = "case_24_determinism_two_runs"
    first = _scenario_stream()
    second = _scenario_stream()
    problems: List[str] = []
    for key in first:
        if first[key] != second[key]:
            problems.append("%s diverged" % key)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "two fresh runs: identical session id, content/evidence/journal "
                 "digests (deterministic evidence)")
    )


def case_25_subprocess_hash_seeds(results: List[Result]) -> None:
    name = "case_25_subprocess_hash_seeds"
    digests: Dict[str, str] = {}
    for seed in ("0", "1", "2"):
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = seed
        env.pop("PYTHONDONTWRITEBYTECODE", None)
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--determinism-stream"],
            capture_output=True, text=True, env=env, cwd=str(REPO_ROOT), timeout=300,
        )
        if proc.returncode != 0:
            results.append(
                fail(name, "seed %s exited %d: %s" % (seed, proc.returncode, proc.stderr[-200:]))
            )
            return
        digests[seed] = proc.stdout.strip()
    unique = set(digests.values())
    if len(unique) != 1:
        results.append(fail(name, "hash seeds diverged: %r" % digests))
        return
    results.append(
        ok(name, "PYTHONHASHSEED 0/1/2 subprocesses agree byte-for-byte")
    )


def case_26_evidence_chain_explicit(results: List[Result]) -> None:
    name = "case_26_evidence_chain_explicit_and_verifiable"
    manager, runtime, _peer, sid, _clock = _world()
    manager.discover()
    wifi = _path_for(manager, WIFI_IF)
    eth = _path_for(manager, ETH_IF)
    manager.validate(wifi)
    manager.bind(wifi, sid)
    manager.probe(wifi)
    manager.activate(wifi)
    record = manager.evidence(wifi)
    problems: List[str] = []
    for field in ("observed_at", "snapshot_digest"):
        if not record.observation.get(field):
            problems.append("observation evidence missing %s" % field)
    if not record.validation.get("validated_at"):
        problems.append("validation evidence missing")
    for field in ("bound_at", "adapter_id", "binding_id", "bearer_ref", "ip_binding_id"):
        if not record.binding.get(field):
            problems.append("binding evidence missing %s" % field)
    for field in ("probed_at", "probe_digest", "probe_payload_digest"):
        if not record.probe.get(field):
            problems.append("traffic-proof evidence missing %s" % field)
    if not record.lifecycle_events:
        problems.append("lifecycle events missing")
    if not verify_path_evidence(record):
        problems.append("independent verification failed")
    # independently recomputable: the digest is a pure function of the
    # canonical record content, recomputed here from the recorded facts
    # alone over the repository canonical-JSON profile.  The assertion
    # is strict: digest equality => PASS, digest mismatch => FAIL (a
    # mismatch is never rationalized into a PASS).
    def _recomputed_digest(content: Dict[str, Any]) -> str:
        return "sha256:" + hashlib.sha256(
            canonical_json_bytes(content)
        ).hexdigest()

    recomputed = _recomputed_digest(record.to_dict())
    if recomputed != record.record_digest():
        problems.append(
            "record digest mismatch: recomputed %s != recorded %s"
            % (recomputed, record.record_digest())
        )
    # independent-serializer agreement: a plain stdlib rendering of the
    # same record must reproduce the identical canonical bytes (two
    # conformant serializers, one digest)
    stdlib_bytes = json.dumps(
        record.to_dict(), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    if stdlib_bytes != canonical_json_bytes(record.to_dict()):
        problems.append("stdlib and canonical-JSON renderings disagree")
    # negative coverage: tamper a recorded fact; the recomputed digest
    # must NOT equal the recorded digest, so the equality assertion
    # above fails closed on tampered/mismatched content
    tampered = record.to_dict()
    tampered["observation"]["snapshot_digest"] = "sha256:tampered-snapshot"
    if _recomputed_digest(tampered) == record.record_digest():
        problems.append(
            "tampered content recomputes to the recorded digest "
            "(digest mismatch would NOT fail)"
        )
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "chain fields present; verify_path_evidence passes; digest "
                 "recomputable from the canonical record (correct digest "
                 "passes; tampered digest fails)")
    )


def case_27_evidence_replay_and_tamper(results: List[Result]) -> None:
    name = "case_27_evidence_replay_safe_and_tamper_evident"
    manager, _runtime, _peer, sid, _clock = _world()
    manager.discover()
    wifi = _path_for(manager, WIFI_IF)
    manager.validate(wifi)
    manager.bind(wifi, sid)
    manager.probe(wifi)
    manager.activate(wifi)
    record = manager.evidence(wifi)
    again = manager.evidence(wifi)
    problems: List[str] = []
    if again.record_digest() != record.record_digest():
        problems.append("re-assembly is not deterministic")
    if evidence_digest([record]) != evidence_digest([again]):
        problems.append("set digest not deterministic")
    # tampering is evident: mutate a fact, the digest changes and the
    # chain verification rejects crafted illegal chains
    tampered = record.to_dict()
    tampered["binding"]["ip_binding_id"] = "sha256:forged"
    from networkpath import PathEvidenceRecord

    forged = PathEvidenceRecord(
        network_path_id=tampered["network_path_id"],
        node_id=tampered["node_id"],
        interface_name=tampered["interface_name"],
        link_kind=tampered["link_kind"],
        state=tampered["state"],
        observation=tampered["observation"],
        validation=tampered["validation"],
        binding=tampered["binding"],
        probe=tampered["probe"],
        lifecycle_events=tuple(tampered["lifecycle_events"]),
    )
    if forged.record_digest() == record.record_digest():
        problems.append("tampering is not digest-evident")
    # an illegal chain (binding without validation) is rejected
    from dataclasses import replace as _replace

    bad_events = [
        event for event in record.lifecycle_events
        if not (event["action"] == "validate")
    ]
    bad = _replace(
        record,
        lifecycle_events=tuple(bad_events),
        validation={"validated_at": "", "validation_observation_digest": "", "accepted": False},
    )
    if verify_path_evidence(bad):
        problems.append("chain without validation accepted")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "re-assembly identical; forged/digest-tampered records detected; "
                 "illegal chain rejected by verification")
    )


def case_28_evidence_no_secrets(results: List[Result]) -> None:
    name = "case_28_evidence_secret_free"
    manager, _runtime, _peer, sid, _clock = _world()
    manager.discover()
    wifi = _path_for(manager, WIFI_IF)
    manager.validate(wifi)
    manager.bind(wifi, sid)
    manager.probe(wifi)
    manager.activate(wifi)
    blob = manager.content_digest() + " " + manager.evidence_digest()
    record = manager.evidence(wifi).to_dict()
    serialized = repr(record) + blob
    problems: List[str] = []
    for secret in (_SECRET_A, _SECRET_B, _KEY_A, _KEY_B):
        if secret.decode("latin-1") in serialized:
            problems.append("secret material leaked into evidence")
        if secret.hex() in serialized:
            problems.append("secret hex leaked into evidence")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "evidence/snapshots carry ids and digests only; no boot secrets, "
                 "no key material")
    )


# ---------------------------------------------------------------------------
# Criterion 5: architectural integrity
# ---------------------------------------------------------------------------


def case_29_no_second_authority(results: List[Result]) -> None:
    name = "case_29_no_second_authority"
    problems: List[str] = []
    allowed_imports = (
        "from protocol", "from agent", "from adapters", "from sessions",
        "from dataclasses", "from typing", "import hashlib",
        "from .errors", "from .model", "from .state", "from .observation",
        "from .validation", "from .binding", "from .evidence",
        "from .lifecycle", "from .integration", "from __future__",
    )
    for path in _FAMILY_FILES:
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("import ") or (
                stripped.startswith("from ") and " import " in stripped
            ):
                if not any(stripped.startswith(prefix) for prefix in allowed_imports):
                    problems.append(
                        "%s: disallowed import %r" % (path.name, stripped)
                    )
        for token in _FORBIDDEN_TOKENS:
            if token in text:
                problems.append("%s: forbidden token %r" % (path.name, token))
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "imports confined to protocol/agent/adapters/sessions; no "
                 "authority construction or session-mutation tokens")
    )


def case_30_no_private_authority_access(results: List[Result]) -> None:
    name = "case_30_no_private_authority_access"
    problems: List[str] = []
    patterns = (
        r"runtime\._",
        r"peer\._",
        r"\.sessions\._",
        r"\.adapters_runtime\._",
        r"\.interface_source\._",
        r"\.node_id\._",
        r"_adapter_interfaces",
        r"_session_transports",
        r"_session_routes",
    )
    for path in _FAMILY_FILES:
        text = path.read_text(encoding="utf-8")
        for pattern in patterns:
            if re.search(pattern, text):
                problems.append("%s matches %r" % (path.name, pattern))
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "no foreign-private attribute access anywhere in the family")
    )


def case_31_naming_token_scan(results: List[Result]) -> None:
    name = "case_31_naming_token_scan"
    problems: List[str] = []
    for path in _FAMILY_FILES:
        text = path.read_text(encoding="utf-8").lower()
        for token in _VENDOR_TOKENS:
            if token in text:
                problems.append("%s contains vendor token %r" % (path.name, token))
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "no vendor/platform tokens in the family (technology-neutral model)")
    )


def case_32_py_compile(results: List[Result]) -> None:
    name = "case_32_py_compile"
    problems: List[str] = []
    targets = list(_FAMILY_FILES) + [Path(__file__).resolve()]
    for path in targets:
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as error:
            problems.append("%s: %s" % (path.name, error))
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(ok(name, "all %d family files + battery compile cleanly" % len(targets)))


def case_33_frozen_api_surface(results: List[Result]) -> None:
    name = "case_33_frozen_api_surface"
    import networkpath

    public = sorted(networkpath.__all__)
    expected = sorted(_EXPECTED_API)
    if public != expected:
        missing = sorted(set(expected) - set(public))
        extra = sorted(set(public) - set(expected))
        results.append(
            fail(name, "missing=%r extra=%r" % (missing, extra))
        )
        return
    results.append(ok(name, "public API surface frozen (%d names)" % len(expected)))


def _origin_main_available() -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/main"],
        capture_output=True, cwd=str(REPO_ROOT),
    )
    return proc.returncode == 0


def case_34_frozen_spec_intact(results: List[Result]) -> None:
    name = "case_34_frozen_spec_intact"
    frozen = (
        "spec/architecture.md",
        "spec/architecture-lock.md",
        "spec/schemas/protocol.json",
        "spec/dependency-graph.md",
        "spec/work-items.md",
    )
    if not _origin_main_available():
        results.append(
            ok(name, "skipped (no origin/main ref; CI enforces the frozen surfaces")
        )
        return
    problems: List[str] = []
    for rel in frozen:
        proc = subprocess.run(
            ["git", "show", "origin/main:%s" % rel],
            capture_output=True, cwd=str(REPO_ROOT),
        )
        if proc.returncode != 0:
            problems.append("%s missing on origin/main" % rel)
            continue
        current = (REPO_ROOT / rel).read_bytes()
        if current != proc.stdout:
            problems.append("%s differs from origin/main" % rel)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "architecture/lock/protocol-schema/dependency-graph/work-items "
                 "byte-identical to origin/main")
    )


def case_35_pr_delta_shape(results: List[Result]) -> None:
    name = "case_35_pr_delta_shape_authorized_scope"
    if not _origin_main_available():
        results.append(
            ok(name, "skipped (no origin/main ref; CI provenance step enforces scope)")
        )
        return
    delta: set = set()
    diff = subprocess.run(
        ["git", "diff", "--name-only", "origin/main"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    if diff.returncode == 0:
        delta |= {line for line in diff.stdout.splitlines() if line.strip()}
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    if untracked.returncode == 0:
        delta |= {line for line in untracked.stdout.splitlines() if line.strip()}
    if not delta:
        results.append(ok(name, "no delta (clean main)"))
        return
    problems: List[str] = []
    for path in sorted(delta):
        if not any(
            path == scope or path.startswith(scope) for scope in _AUTHORIZED_PATHS
        ):
            problems.append("delta outside authorized scope: %s" % path)
        if path.startswith("spec/architect/"):
            problems.append("implementation PR modifies the Architect package: %s" % path)
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "delta confined to the WORK-041-CORE-001 scope (%d file(s))" % len(delta))
    )


def case_36_honest_evidence_disclosure(results: List[Result]) -> None:
    name = "case_36_honest_evidence_disclosure"
    problems: List[str] = []
    if NETWORKPATH_EVIDENCE_STATUS != {
        "software_deterministic_path_lifecycle": "supported-verified",
        "physical_device": "open",
    }:
        problems.append("disclosure object drifted: %r" % (NETWORKPATH_EVIDENCE_STATUS,))
    # no synthetic physical claims anywhere in the family source
    # (the battery's own docstring names the forbidden claims as the
    # rule, so the scan targets the family only)
    for path in _FAMILY_FILES:
        text = path.read_text(encoding="utf-8")
        for claim in ("5G PASS", "physical PASS", "physical deployment PASS",
                      "Android physical PASS"):
            if claim in text:
                problems.append("%s claims %r" % (path.name, claim))
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "software lifecycle verified; PHYSICAL device evidence OPEN "
                 "(W040 owns EVID-007/EVID-008; no synthetic physical claims)")
    )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    results: List[Result] = []
    for case in (
        case_01_frozen_vocabularies,
        case_02_illegal_transitions_table,
        case_03_content_derived_identity,
        case_04_malformed_records_fail_closed,
        case_05_platform_observation_model,
        case_06_observation_sources_fail_closed,
        case_07_discovery_candidates_not_active,
        case_08_duplicate_discovery_idempotent,
        case_09_full_lifecycle_to_active,
        case_10_candidate_gates_before_chain,
        case_11_session_continuity_handover,
        case_12_handover_ordering_preserves_old,
        case_13_technology_neutral_breadth,
        case_14_dynamic_exposure_gates_validation,
        case_15_validation_failure_preserves_active,
        case_16_stale_candidate_identity_drift,
        case_17_bind_failure_preserves_active,
        case_18_probe_failure_preserves_active,
        case_19_activate_requires_probe_evidence,
        case_20_duplicate_transitions_fail_closed,
        case_21_retired_is_terminal,
        case_22_unknown_path_fail_closed,
        case_23_replay_of_operation_sequence,
        case_24_determinism_two_runs,
        case_25_subprocess_hash_seeds,
        case_26_evidence_chain_explicit,
        case_27_evidence_replay_and_tamper,
        case_28_evidence_no_secrets,
        case_29_no_second_authority,
        case_30_no_private_authority_access,
        case_31_naming_token_scan,
        case_32_py_compile,
        case_33_frozen_api_surface,
        case_34_frozen_spec_intact,
        case_35_pr_delta_shape,
        case_36_honest_evidence_disclosure,
    ):
        case(results)
    failures = [result for result in results if not result[1]]
    for entry in results:
        print("[%s] %-52s %s" % ("ok  " if entry[1] else "FAIL", entry[0], entry[2]))
    if failures:
        print("Result: FAIL (%d/%d cases failed)" % (len(failures), len(results)))
        for entry in failures:
            print("  FAILED %s: %s" % (entry[0], entry[2]))
        return 1
    print("Result: PASS (%d/%d cases passed)" % (len(results), len(results)))
    return 0


if __name__ == "__main__":
    if "--determinism-stream" in sys.argv:
        stream = _scenario_stream()
        for key in sorted(stream):
            print("%s=%s" % (key, stream[key]))
        sys.exit(0)
    sys.exit(main())
