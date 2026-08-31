#!/usr/bin/env python3
"""WORK-042 platform-integration battery (deterministic, stdlib
only).

End-to-end verification of the event-driven platform integration
and journal-first recovery boundary (ACR-006, authorization
WORK-042-CORE-001 / DEC-0055) composing the accepted WORK-033 Linux
reference agent, WORK-035 mobile platform seams, and WORK-041
NetworkPath:

- frozen vocabularies: the platform-event kinds
  (interface-observation / interface-removal /
  platform-state-observation), ingestion outcomes, journal record
  kinds (observations vs honest outcomes), and the reason
  vocabulary;
- value model: content-derived event/record/checkpoint ids
  (tamper-evident content binding at construction AND on
  deserialization), round-trips, deterministic ordering;
- reconciliation (criterion 2): the event->snapshot fold is
  deterministic and idempotent (two folds byte-identical; replays
  and duplicates are no-ops; stale observations are inert; equal-
  instant conflicting observations fail closed);
- journal (criterion 3): append-only discipline (the file only
  grows; no mutation API), persist-then-ack (a store failure
  leaves no phantom state), hash-chain + sequence + duplicate +
  collision verification (byte tamper, reorder, truncation, and
  sequence-gap journals all fail closed);
- checkpoints (criterion 3): journal-tail binding (prefix digest),
  state == fold(prefix) verification, schema/content tamper
  detection, ahead-of-journal rejection;
- recovery (criterion 4): process-death restart reconstructs state
  deterministically (full journal AND checkpoint + tail replay
  agree byte-for-byte), one fresh authoritative platform
  observation is reconciled through the ordinary boundary with
  honest divergence reporting, and session loss is recorded
  HONESTLY and DURABLY (the killed process's transport state
  cannot survive; a still-present interface never resurrects a
  session; no session is ever recreated during recovery -- the
  successor re-establishes through the ordinary authority path
  with a NEW session id and exactly one created event);
- event-first (criterion 1): the primary ingestion path is push
  (one host-pushed observation -> one event); the polling fallback
  is change-detected (an unchanged sweep emits NOTHING);
- evidence: the recovery evidence chain is explicit, deterministic
  (two fresh runs byte-identical; PYTHONHASHSEED 0/1/7919/unset
  subprocesses agree), replay-safe, independently verifiable
  (digests recompute from recorded facts), and secret-free;
- architectural integrity (criterion 5): structural audits -- no
  second authority (construction/mutation call-token discipline),
  no authority parameters in recovery (it cannot touch session/
  routing/identity state by construction), sanctioned imports
  only, no vendor tokens, no stdlib ``platform`` shadowing
  hazards, frozen public API, frozen spec surfaces intact, PR
  delta confined to the authorized W042 scope (+ the sanctioned
  additive-only CI wiring), and the honest two-track evidence
  disclosure (software verified; PHYSICAL device evidence OPEN
  and W040-owned -- no synthetic physical claims).

The battery exercises the PUBLIC production path only: the
ordinary AgentRuntime session establishment chain, the
NetworkPathManager public lifecycle, and the PlatformIntegrator
public surface.  No private method is called to manufacture a
PASS.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import py_compile
import shutil
import subprocess  # noqa: S404 - deterministic child processes of this repo's own tools
import sys
import tempfile
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
)
from agent.interfaces import InterfaceSource  # noqa: E402

from mobile.model import (  # noqa: E402
    MobilePhase,
    NetworkKind,
    PlatformSnapshot,
    PowerState,
)
from mobile.platform import (  # noqa: E402
    MobilePlatformSource,
    StaticPlatformSource,
)

from networkpath import NetworkPath, NetworkPathManager  # noqa: E402

from platform import (  # noqa: E402
    DIVERGENCE_APPEARED,
    DIVERGENCE_CHANGED,
    DIVERGENCE_REMOVED,
    EventKind,
    IngestionStatus,
    JournalRecordKind,
    MemoryPlatformStore,
    PLATFORM_EVIDENCE_STATUS,
    PlatformCheckpoint,
    PlatformError,
    PlatformIntegrator,
    PlatformReasonCode,
    PlatformStore,
    ReconciledState,
    SESSION_LOSS_CAUSE,
    assemble_recovery_evidence,
    derive_platform_event_id,
    event_from_redelivery,
    fold_state,
    fold_state_from,
    interface_event,
    journal_bytes_for,
    load_verified_checkpoint,
    record_list_digest,
    session_bindings_from_manager,
    verify_recovery_evidence,
)
from platform.journal import AppendOnlyJournal  # noqa: E402

Result = Tuple[str, bool, str]

_FAMILY_FILES = sorted((REPO_ROOT / "platform").rglob("*.py"))

_T0 = "2025-06-01T00:00:00Z"
_T_RECOVERY = "2025-06-01T06:00:00Z"
_FRESH = "2026-06-01T00:00:00Z"
_SECRET_A = b"w042-battery-secret-A"
_SECRET_B = b"w042-battery-secret-B"
_PROFILE_ID = "identity.sha256-hmac-dev.v1"
_KEY_A = b"w042-battery-key-A"
_KEY_B = b"w042-battery-key-B"

WIFI_IF = "wlan0"
ETH_IF = "eth0"
USB_IF = "usb0"
CELL_IF = "cellular0"
VPN_IF = "vpn0"

#: The frozen platform public API surface (case on the frozen API).
_EXPECTED_API = [
    "CHECKPOINT_SCHEMA",
    "DIVERGENCE_APPEARED",
    "DIVERGENCE_CHANGED",
    "DIVERGENCE_REMOVED",
    "DEFAULT_INTERFACE_SOURCE",
    "DEFAULT_PLATFORM_SOURCE",
    "AppendOnlyJournal",
    "Divergence",
    "EventKind",
    "FilePlatformStore",
    "IngestionOutcome",
    "IngestionStatus",
    "JournalRecord",
    "JournalRecordKind",
    "MemoryPlatformStore",
    "ObservationRecord",
    "PLATFORM_EVIDENCE_STATUS",
    "PLATFORM_STATE_REF",
    "PlatformCheckpoint",
    "ReconciledState",
    "PlatformError",
    "PlatformEvent",
    "PlatformIntegrator",
    "PlatformReasonCode",
    "PlatformStore",
    "ReconciledInterfaceSource",
    "ReconciledPlatformSource",
    "RecoveryEvidenceRecord",
    "RecoveryReport",
    "SESSION_LOSS_CAUSE",
    "SessionBindingRef",
    "apply_record",
    "assemble_recovery_evidence",
    "build_checkpoint",
    "derive_checkpoint_id",
    "derive_platform_event_id",
    "derive_record_id",
    "divergences_from_fresh_events",
    "evidence_digest",
    "event_from_redelivery",
    "event_list_digest",
    "events_from_sources",
    "fold_state",
    "fold_state_from",
    "interface_event",
    "interface_removal_event",
    "journal_bytes_for",
    "load_verified_checkpoint",
    "path_supports_state",
    "perform_recovery",
    "platform_event_content",
    "platform_state_event",
    "record_list_digest",
    "session_bindings_from_manager",
    "verify_recovery_evidence",
]

#: The authorized W042 delta surface (scope of WORK-042-CORE-001)
#: plus the sanctioned additive CI-wiring path (the W033/W035/W041
#: battery precedent: batteries explicitly allow an ADDITIVE
#: .github delta in the implementation PR and check it never
#: weakens a step).
_AUTHORIZED_PATHS = (
    "platform/",
    "tools/platform_selftest.py",
    "docs/WORK-042-handoff.md",
    "docs/WORK-042-evidence.md",
)
AUTHORIZED_CI_WIRING = ".github/workflows/spec-check.yml"

#: Vendor/platform tokens the platform family must never encode
#: (technology-neutral representation; the OS vocabularies belong
#: to the accepted agent/mobile families).
_VENDOR_TOKENS = (
    "android", "rndis", "qualcomm", "mediatek", "samsung", "broadcom",
    "huawei", "apple", "google", "windows", "darwin", "ios_",
    "open5gs", "ocudu", "openairinterface",
)

#: Forbidden authority-construction/mutation tokens: the platform
#: family must never build or drive a second authority (isinstance
#: checks and type annotations against the composed public classes
#: are fine -- the scan targets CONSTRUCTION and MUTATION calls).
_FORBIDDEN_TOKENS = (
    "RoutingEngine(", "PolicyEngine(", "TransportManager(",
    "TopologyGraph(", "SessionStore(", "IdentityService(",
    "NetworkPathManager(", "AgentRuntime(", "MobileAgent(",
    "MultipathSessionManager(", "MobilityController(",
    "sessions.create", "sessions.transition", "sessions.reconnect",
    "sessions.terminate", "sessions.suspend", "sessions.append_event",
    "derive_session_id", "establish_session(", "accept_session(",
    "complete_session(", "finalize_session(", "bind_session(",
    "register_peer(", "expose_interfaces(", "send_datagram(",
)

#: The sanctioned absolute-import allowlist for the platform family
#: (stdlib types + the composed accepted families + the WORK-003
#: canonicalization/profile seams).
_ALLOWED_IMPORT_PREFIXES = (
    "protocol.",
    "agent.",
    "mobile.",
    "networkpath.",
)
_ALLOWED_IMPORT_MODULES = {
    "__future__",
    "hashlib",
    "json",
    "dataclasses",
    "pathlib",
    "typing",
    # bare family roots (``from networkpath import ...``)
    "protocol",
    "agent",
    "mobile",
    "networkpath",
}


def ok(name: str, detail: str = "") -> Result:
    return (name, True, detail)


def fail(name: str, detail: str) -> Result:
    return (name, False, detail)


def _ids() -> Tuple[str, str]:
    """The deterministic node ids for the battery keys (derived
    through the genuine identity machinery)."""
    from identity.model import NodeIdentity
    from identity.profiles import ProfileSet

    profiles = ProfileSet.load_default()
    profile = profiles.get(_PROFILE_ID)
    identity_a = NodeIdentity.create(profile, _KEY_A, _T0)
    identity_b = NodeIdentity.create(profile, _KEY_B, _T0)
    return identity_a.node_id.text, identity_b.node_id.text


def _snap(*, name: str, kind: str, up: bool = True, addresses: Tuple[str, ...] = (),
           mtu: int = 1500, speed: int = 100, rx: int = 7, tx: int = 9) -> InterfaceSnapshot:
    return InterfaceSnapshot(
        name=name, link_kind=kind, state_up=up, mtu=mtu, speed_mbps=speed,
        rx_bytes=rx, tx_bytes=tx, rx_errors=0, tx_errors=0,
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


def _fresh_snapshots() -> Tuple[InterfaceSnapshot, ...]:
    """The post-downtime platform drift: wlan0's link went DOWN
    (payload change), usb0 disappeared (removal), vpn0 appeared
    (new reference), eth0/cellular0 unchanged (no events)."""
    return (
        _snap(name=WIFI_IF, kind="wireless", up=False, addresses=("fd00::a:1",), rx=57, tx=61),
        _snap(name=ETH_IF, kind="ethernet", addresses=("fd00::a:2",), speed=1000),
        _snap(name=CELL_IF, kind="other", addresses=(), mtu=1300, speed=50),
        _snap(name=VPN_IF, kind="other", addresses=("fd00::a:9",), mtu=1280, speed=200),
    )


def _platform_snapshot(*, background: bool = False) -> PlatformSnapshot:
    return PlatformSnapshot(
        app_phase=(
            MobilePhase.BACKGROUND if background else MobilePhase.FOREGROUND
        ),
        power_state=(
            PowerState.ON_BATTERY if background else PowerState.CHARGING
        ),
        network_kind=NetworkKind.WIFI,
        metered=False,
        background_restricted=background,
    )


class MutableInterfaceSource(InterfaceSource):
    """A battery fixture: an interface source whose snapshot set can
    change between reads (post-downtime drift scenarios).
    Deterministic for a fixed script of set_snapshots calls."""

    def __init__(self, snapshots: Tuple[InterfaceSnapshot, ...] = ()) -> None:
        self._snapshots: Tuple[InterfaceSnapshot, ...] = tuple(snapshots)

    def set_snapshots(self, snapshots: Tuple[InterfaceSnapshot, ...]) -> None:
        self._snapshots = tuple(snapshots)

    def discover(self) -> Tuple[InterfaceSnapshot, ...]:
        return self._snapshots


class FailingPlatformStore(PlatformStore):
    """A battery fixture: a store whose journal append fails (the
    persist-then-ack discipline: no phantom in-memory state)."""

    def __init__(self) -> None:
        self._lines: List[bytes] = []
        self._checkpoint = b""

    def append_journal_line(self, line: bytes) -> None:
        raise PlatformError(
            PlatformReasonCode.STORE_FAILED,
            "battery fixture: simulated durable-append failure",
        )

    def journal_bytes(self) -> bytes:
        return b"".join(self._lines)

    def write_checkpoint(self, payload: bytes) -> None:
        self._checkpoint = payload

    def read_checkpoint(self) -> bytes:
        return self._checkpoint


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
            role_id="w042-battery-operator",
            capabilities=(
                ManagementCapability.SESSION_READ,
                ManagementCapability.SESSION_CONTROL,
                ManagementCapability.POLICY_READ,
            ),
            description="operator role (battery fixture)",
        ),
    )


def _config(
    label: str = "platform-node",
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


def _establish_session(
    runtime: AgentRuntime, peer: AgentRuntime, clock: StepClock
) -> str:
    """The ordinary public production session handshake."""
    request = runtime.establish_session(peer.node_id)
    accept = peer.accept_session(request)
    confirm = runtime.complete_session(accept)
    peer.finalize_session(confirm)
    return confirm.session_id


def _world(
    snapshots: Optional[Tuple[InterfaceSnapshot, ...]] = None,
) -> Tuple[AgentRuntime, AgentRuntime, str, StepClock]:
    """One booted node + one booted peered peer runtime with one
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
    session_id = _establish_session(runtime, peer, shared)
    return runtime, peer, session_id, shared


def _expect_error(name: str, reason: str, func, *args, **kwargs) -> Optional[str]:
    """Run func; PASS iff it raised PlatformError with the reason."""
    try:
        func(*args, **kwargs)
    except PlatformError as error:
        if error.reason == reason:
            return None
        return "expected %s, got %s (%s)" % (reason, error.reason, error.detail)
    except Exception as error:  # noqa: BLE001 - wrong exception type is a failure
        return "wrong exception type %s" % type(error).__name__
    return "no error raised (expected %s)" % reason


def _ingest_all(
    integrator: PlatformIntegrator,
    snapshots: Tuple[InterfaceSnapshot, ...],
    clock: StepClock,
    *,
    with_platform_state: bool = True,
) -> None:
    """The event-first primary path: one host-pushed observation per
    interface plus one platform-state observation (host instants
    read from the shared injected clock)."""
    for snapshot in snapshots:
        integrator.ingest_interface_observation(
            snapshot, observed_at=clock.now()
        )
    if with_platform_state:
        integrator.ingest_platform_state(
            _platform_snapshot(), observed_at=clock.now()
        )


# ---------------------------------------------------------------------------
# The canonical golden scenario (determinism stream + composition)
# ---------------------------------------------------------------------------


def _scenario_stream(store: Optional[PlatformStore] = None) -> Dict[str, str]:
    """The canonical battery scenario: full production composition
    -> process death -> journal-first recovery -> successor
    re-establishment, returning the deterministic digest stream."""
    if store is None:
        store = MemoryPlatformStore()
    # ---- epoch 1: the production process -----------------------------
    runtime, peer, session_id, shared = _world()
    integrator = PlatformIntegrator(store=store, clock=shared)
    _ingest_all(integrator, _snapshots(), shared)
    manager = NetworkPathManager(runtime, shared)
    manager.discover()
    wifi = _path_for(manager, WIFI_IF)
    manager.validate(wifi)
    manager.bind(wifi, session_id)
    manager.probe(wifi)
    manager.activate(wifi)
    bindings = session_bindings_from_manager(manager)
    checkpoint = integrator.checkpoint(session_bindings=bindings)

    # ---- process death: ALL in-memory state is dropped ---------------
    del integrator, manager, runtime, peer, shared

    # ---- epoch 2: journal-first recovery ------------------------------
    clock2 = StepClock(_T_RECOVERY, 60)
    integrator2, report = PlatformIntegrator.recover(
        store=store,
        clock=clock2,
        interface_source=MutableInterfaceSource(_fresh_snapshots()),
        platform_source=StaticPlatformSource(
            _platform_snapshot(background=True)
        ),
    )
    evidence = assemble_recovery_evidence(report)

    # ---- epoch 3: the successor process (ordinary paths only) ---------
    peer2 = AgentRuntime(
        _peer_config(), clock=clock2,
        interface_source=integrator2.reconciled_interface_source(),
    )
    peer2.boot(_SECRET_B)
    peer2.expose_interfaces()
    runtime2 = AgentRuntime(
        _config(), clock=clock2,
        interface_source=integrator2.reconciled_interface_source(),
    )
    runtime2.boot(_SECRET_A)
    runtime2.expose_interfaces()
    _register_peers(runtime2, peer2, clock2)
    successor_session = _establish_session(runtime2, peer2, clock2)
    manager2 = NetworkPathManager(runtime2, clock2)
    manager2.discover()

    return {
        "session_id": session_id,
        "successor_session_id": successor_session,
        "checkpoint_id": checkpoint.checkpoint_id,
        "journal_digest": integrator2.journal_digest(),
        "state_digest": integrator2.state().state_digest(),
        "recovery_digest": report.recovery_digest(),
        "evidence_digest": evidence.record_digest(),
        "lost_sessions": ",".join(report.lost_sessions),
        "divergences": ",".join(
            sorted(
                "%s:%s" % (item.kind, item.platform_ref)
                for item in report.divergences
            )
        ),
        "content_digest": integrator2.content_digest(),
        "successor_paths": str(len(manager2.paths())),
        "bindings": str(len(bindings)),
    }


def _path_for(manager: NetworkPathManager, interface_name: str) -> str:
    for path_id in manager.paths():
        if manager.path(path_id).interface_name == interface_name:
            return path_id
    raise AssertionError("no candidate for interface %r" % interface_name)


# ---------------------------------------------------------------------------
# Vocabulary and value model
# ---------------------------------------------------------------------------


def case_01_frozen_vocabularies(results: List[Result]) -> None:
    name = "case_01_frozen_vocabularies"
    problems: List[str] = []
    if EventKind.values() != (
        "interface-observation",
        "interface-removal",
        "platform-state-observation",
    ):
        problems.append("event kinds drifted")
    if IngestionStatus.values() != ("appended", "stale", "duplicate"):
        problems.append("ingestion statuses drifted")
    if JournalRecordKind.values() != ("platform-event", "session-loss"):
        problems.append("journal record kinds drifted")
    if PlatformReasonCode.values() != (
        "invalid-input",
        "observation-invalid",
        "observation-source-failed",
        "event-invalid",
        "event-contradictory",
        "journal-corrupt",
        "journal-append-rejected",
        "checkpoint-invalid",
        "checkpoint-mismatch",
        "state-invalid",
        "store-failed",
        "recovery-rejected",
    ):
        problems.append("reason codes drifted")
    if SESSION_LOSS_CAUSE != "process-restart":
        problems.append("session-loss cause drifted")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(ok(name, "event kinds / outcomes / record kinds / reasons frozen"))


def case_02_event_schema_round_trip(results: List[Result]) -> None:
    name = "case_02_event_schema_round_trip"
    snapshot = _snap(name=WIFI_IF, kind="wireless", addresses=("fd00::a:1",))
    event = interface_event(
        snapshot, observed_at="2025-06-01T00:00:00Z", source="battery-push"
    )
    payload = event.to_dict()
    rebuilt = event_from_redelivery(payload)
    problems: List[str] = []
    if rebuilt.to_dict() != payload:
        problems.append("round trip mutated the record")
    if rebuilt.event_id != event.event_id:
        problems.append("event id not stable across round trip")
    # malformed events fail closed
    for bad in (
        None,
        [],
        "not-a-mapping",
        {"kind": "interface-observation"},  # missing fields
        dict(payload, event_id="sha256:deadbeef"),
        dict(payload, kind="not-a-kind"),
        dict(payload, observed_at="not-an-instant"),
        dict(payload, payload={"name": WIFI_IF}),
    ):
        try:
            event_from_redelivery(bad)
            problems.append("malformed payload %r accepted" % (bad,))
            break
        except PlatformError:
            continue
        except Exception as error:  # noqa: BLE001
            problems.append("wrong exception type %s" % type(error).__name__)
            break
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(ok(name, "round-trip stable; 8 malformed shapes fail closed"))


def case_03_content_derived_event_ids(results: List[Result]) -> None:
    name = "case_03_content_derived_event_ids"
    snapshot = _snap(name=ETH_IF, kind="ethernet", addresses=("fd00::a:2",))
    other = _snap(name=ETH_IF, kind="ethernet", addresses=("fd00::a:2",), rx=99)
    problems: List[str] = []
    if not derive_platform_event_id(
        "interface-observation", "src", ETH_IF,
        snapshot.to_dict(), "2025-06-01T00:00:00Z",
    ).startswith("sha256:"):
        problems.append("id is not a sha256 fingerprint")
    # same content -> same id
    if interface_event(snapshot, observed_at="2025-06-01T00:00:00Z").event_id != (
        interface_event(snapshot, observed_at="2025-06-01T00:00:00Z").event_id
    ):
        problems.append("identical content produced different ids")
    # any content difference changes the id
    if interface_event(other, observed_at="2025-06-01T00:00:00Z").event_id == (
        interface_event(snapshot, observed_at="2025-06-01T00:00:00Z").event_id
    ):
        problems.append("payload difference not reflected in the id")
    if interface_event(snapshot, observed_at="2025-06-01T00:01:00Z").event_id == (
        interface_event(snapshot, observed_at="2025-06-01T00:00:00Z").event_id
    ):
        problems.append("instant difference not reflected in the id")
    # tampered id rejected at construction
    try:
        event_from_redelivery({
            "event_id": "sha256:" + "0" * 64,
            "kind": "interface-observation",
            "source": "battery-push",
            "platform_ref": ETH_IF,
            "payload": snapshot.to_dict(),
            "observed_at": "2025-06-01T00:00:00Z",
        })
        problems.append("tampered event id accepted")
    except PlatformError as error:
        if error.reason != PlatformReasonCode.EVENT_INVALID:
            problems.append("tampered id raised %s" % error.reason)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "ids are content fingerprints; tampered ids fail closed")
    )


def case_04_event_ordering(results: List[Result]) -> None:
    name = "case_04_event_ordering"
    store = MemoryPlatformStore()
    clock = StepClock(_T0, 60)
    integrator = PlatformIntegrator(store=store, clock=clock)
    for snapshot in _snapshots():
        integrator.ingest_interface_observation(
            snapshot, observed_at=clock.now()
        )
    records = integrator.journal_records()
    sequences = [record.sequence for record in records]
    problems: List[str] = []
    if sequences != list(range(1, len(sequences) + 1)):
        problems.append("journal sequence not contiguous from 1")
    if len(set(sequences)) != len(sequences):
        problems.append("duplicate sequences")
    # RFC 3339 UTC instants are monotonic-orderable DATA (lexicographic
    # order == chronological order for the fixed-width form)
    instants = [
        record.event.observed_at
        for record in records
        if record.record_kind == JournalRecordKind.PLATFORM_EVENT
    ]
    if instants != sorted(instants):
        problems.append("observation instants not monotonic in journal order")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "sequences 1..N contiguous; instants monotonic-orderable")
    )


def case_05_snapshot_round_trip(results: List[Result]) -> None:
    name = "case_05_snapshot_round_trip"
    store = MemoryPlatformStore()
    clock = StepClock(_T0, 60)
    integrator = PlatformIntegrator(store=store, clock=clock)
    _ingest_all(integrator, _snapshots(), clock)
    state = integrator.state()
    problems: List[str] = []
    rebuilt = ReconciledState.from_dict(state.to_dict())
    if not rebuilt.state_equal(state):
        problems.append("round trip mutated the state")
    if state.state_digest() != rebuilt.state_digest():
        problems.append("state digest not stable across round trip")
    try:
        ReconciledState.from_dict({"interface_records": "not-a-list"})
        problems.append("malformed state accepted")
    except PlatformError:
        pass
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(ok(name, "state round-trip stable; malformed state rejected"))


# ---------------------------------------------------------------------------
# Deterministic reconciliation (criterion 2)
# ---------------------------------------------------------------------------


def case_06_event_to_snapshot_reconciliation(results: List[Result]) -> None:
    name = "case_06_event_to_snapshot_reconciliation"
    store = MemoryPlatformStore()
    clock = StepClock(_T0, 60)
    integrator = PlatformIntegrator(store=store, clock=clock)
    _ingest_all(integrator, _snapshots(), clock)
    records = list(integrator.journal_records())
    folded = fold_state(records)
    problems: List[str] = []
    if not folded.state_equal(integrator.state()):
        problems.append("fold disagrees with the incremental state")
    if folded.present_interface_names() != (
        CELL_IF, ETH_IF, USB_IF, WIFI_IF
    ):
        problems.append("present interfaces wrong: %r" % (folded.present_interface_names(),))
    if folded.platform_record is None:
        problems.append("platform-state observation missing")
    # the fold IS the journal: replay reproduces the same state
    if fold_state(records).state_digest() != folded.state_digest():
        problems.append("fold not deterministic")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "fold == incremental state; deterministic replay identical")
    )


def case_07_idempotent_replay(results: List[Result]) -> None:
    name = "case_07_idempotent_replay"
    store = MemoryPlatformStore()
    clock = StepClock(_T0, 60)
    integrator = PlatformIntegrator(store=store, clock=clock)
    _ingest_all(integrator, _snapshots(), clock)
    digest_before = integrator.journal_digest()
    state_before = integrator.state().state_digest()
    # replay the WHOLE event sequence through the boundary: every
    # event is a duplicate (idempotent no-op)
    global replay_outcomes
    replay_outcomes = []
    for record in list(integrator.journal_records()):
        if record.record_kind != JournalRecordKind.PLATFORM_EVENT:
            continue
        outcome = integrator.ingest_event(record.event)
        replay_outcomes.append(outcome.status)
    problems: List[str] = []
    if set(replay_outcomes) != {IngestionStatus.DUPLICATE}:
        problems.append("replay not fully duplicate: %r" % (sorted(set(replay_outcomes)),))
    if integrator.journal_digest() != digest_before:
        problems.append("journal mutated during replay")
    if integrator.state().state_digest() != state_before:
        problems.append("state mutated during replay")
    # pure-fold idempotence: fold(fold inputs) twice identical
    records = list(integrator.journal_records())
    if fold_state(records).state_digest() != fold_state(records).state_digest():
        problems.append("pure fold not idempotent")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "replay is a full no-op (journal + state byte-stable)")
    )


def case_08_duplicate_and_contradiction_rejection(results: List[Result]) -> None:
    name = "case_08_duplicate_and_contradiction_rejection"
    store = MemoryPlatformStore()
    clock = StepClock(_T0, 60)
    integrator = PlatformIntegrator(store=store, clock=clock)
    snapshot = _snap(name=WIFI_IF, kind="wireless", addresses=("fd00::a:1",))
    conflict = _snap(
        name=WIFI_IF, kind="wireless", up=False,
        addresses=("fd00::a:1",), rx=57, tx=61,
    )
    integrator.ingest_interface_observation(snapshot, observed_at="2025-06-01T00:00:00Z")
    length_before = len(integrator.journal_records())
    problems: List[str] = []
    # duplicate: identical event, idempotent no-op, no new record
    outcome = integrator.ingest_interface_observation(
        snapshot, observed_at="2025-06-01T00:00:00Z"
    )
    if outcome.status != IngestionStatus.DUPLICATE:
        problems.append("identical redelivery not reported duplicate")
    if len(integrator.journal_records()) != length_before:
        problems.append("duplicate appended a record")
    # duplicate event id with CONFLICTING payload fails at event
    # construction (content binding)
    try:
        event_from_redelivery({
            "event_id": integrator.journal_records()[0].event.event_id,
            "kind": "interface-observation",
            "source": "battery-push",
            "platform_ref": WIFI_IF,
            "payload": conflict.to_dict(),
            "observed_at": "2025-06-01T00:00:00Z",
        })
        problems.append("conflicting payload under a reused id accepted")
    except PlatformError as error:
        if error.reason != PlatformReasonCode.EVENT_INVALID:
            problems.append("conflicting payload raised %s" % error.reason)
    # same reference + instant, different content: contradiction
    problem = _expect_error(
        name, PlatformReasonCode.EVENT_CONTRADICTORY,
        integrator.ingest_interface_observation,
        conflict, observed_at="2025-06-01T00:00:00Z",
    )
    if problem:
        problems.append(problem)
    if len(integrator.journal_records()) != length_before:
        problems.append("rejected contradiction mutated the journal")
    # same reference + instant + kind MISMATCH (observation vs removal)
    problem = _expect_error(
        name, PlatformReasonCode.EVENT_CONTRADICTORY,
        integrator.ingest_interface_removal,
        WIFI_IF, observed_at="2025-06-01T00:00:00Z",
    )
    if problem:
        problems.append(problem)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "duplicate no-op; conflicting payload/id and equal-instant "
                 "conflicts fail closed without mutation")
    )


# ---------------------------------------------------------------------------
# Append-only journal (criterion 3)
# ---------------------------------------------------------------------------


def case_09_journal_append_only(results: List[Result]) -> None:
    name = "case_09_journal_append_only"
    with tempfile.TemporaryDirectory() as tmp:
        store = platform_file_store(tmp)
        clock = StepClock(_T0, 60)
        integrator = PlatformIntegrator(store=store, clock=clock)
        _ingest_all(integrator, _snapshots(), clock)
        size_after_first = store.journal_path.stat().st_size
        records_before = list(integrator.journal_records())
        # a duplicate does not grow the file (idempotent no-op)
        integrator.ingest_event(records_before[0].event)
        size_after_duplicate = store.journal_path.stat().st_size
        problems: List[str] = []
        if size_after_duplicate != size_after_first:
            problems.append("duplicate ingestion grew the journal file")
        # one more append grows the file by exactly one line
        snapshot = _snap(name=VPN_IF, kind="other", addresses=("fd00::a:9",))
        integrator.ingest_interface_observation(
            snapshot, observed_at="2025-06-01T01:00:00Z"
        )
        raw = store.journal_bytes()
        if len(raw.split(b"\n")) - 1 != len(integrator.journal_records()):
            problems.append("file line count != record count")
        if store.journal_path.stat().st_size <= size_after_first:
            problems.append("append did not grow the journal file")
        # the medium bytes ARE the canonical record serialization
        if raw != journal_bytes_for(list(integrator.journal_records())):
            problems.append("journal bytes are not the canonical serialization")
        # there is no mutation API: the surface exposes no
        # remove/rewrite/replace method
        journal = AppendOnlyJournal(store=MemoryPlatformStore())
        public = [
            attr for attr in dir(journal)
            if not attr.startswith("_")
        ]
        for forbidden in ("remove", "rewrite", "replace", "update", "delete", "pop", "insert", "set"):
            if any(forbidden in attr for attr in public):
                problems.append("journal exposes a mutation method %r" % attr)
        if problems:
            results.append(fail(name, "; ".join(problems)))
            return
        results.append(
            ok(name, "file only grows; bytes == canonical records; no mutation API")
        )


def case_10_journal_tamper_detection(results: List[Result]) -> None:
    name = "case_10_journal_tamper_detection"
    with tempfile.TemporaryDirectory() as tmp:
        store = platform_file_store(tmp)
        clock = StepClock(_T0, 60)
        integrator = PlatformIntegrator(store=store, clock=clock)
        _ingest_all(integrator, _snapshots(), clock)
        raw = store.journal_bytes()
        lines = [line for line in raw.split(b"\n") if line]

        problems: List[str] = []
        # byte flip inside the first record's payload
        tampered_store = MemoryPlatformStore()
        tampered_store.append_journal_line(
            raw.replace(b'"mtu":1500', b'"mtu":1501', 1)
        )
        problem = _expect_error(
            name, PlatformReasonCode.JOURNAL_CORRUPT,
            AppendOnlyJournal.load, tampered_store,
        )
        if problem:
            problems.append("byte flip: %s" % problem)
        # reordering two lines breaks the chain
        reordered = MemoryPlatformStore()
        reordered.append_journal_line(b"\n".join([lines[1], lines[0]] + lines[2:]) + b"\n")
        problem = _expect_error(
            name, PlatformReasonCode.JOURNAL_CORRUPT,
            AppendOnlyJournal.load, reordered,
        )
        if problem:
            problems.append("reorder: %s" % problem)
        # truncating a HALF line (crash mid-append) fails closed
        truncated = MemoryPlatformStore()
        truncated.append_journal_line(b"\n".join(lines) + b"\n" + lines[0][:20])
        problem = _expect_error(
            name, PlatformReasonCode.JOURNAL_CORRUPT,
            AppendOnlyJournal.load, truncated,
        )
        if problem:
            problems.append("truncation: %s" % problem)
        # a sequence gap (impossible journal transition) fails closed:
        # rebuild records with sequence 3 dropped
        crafted = _rebuild_without_index(list(lines), 2)
        gapped = MemoryPlatformStore()
        for line in crafted:
            gapped.append_journal_line(line + b"\n")
        problem = _expect_error(
            name, PlatformReasonCode.JOURNAL_CORRUPT,
            AppendOnlyJournal.load, gapped,
        )
        if problem:
            problems.append("sequence gap: %s" % problem)
        # removing the LAST line (whole-record truncation) breaks the
        # checkpoint binding but the journal itself stays chain-valid:
        # verify_integrity on the shorter journal still passes and
        # only recovery's checkpoint gate fails (covered in case_24)
        if problems:
            results.append(fail(name, "; ".join(problems)))
            return
        results.append(
            ok(name, "byte flip / reorder / half-line truncation / sequence "
                     "gap all fail closed (JOURNAL_CORRUPT)")
        )


def _rebuild_without_index(lines: List[bytes], skip_index: int) -> List[bytes]:
    """Re-serialize the record list with one record REMOVED and the
    remaining sequence numbers left as-is (a hand-crafted gap)."""
    out: List[bytes] = []
    for index, line in enumerate(lines):
        if index == skip_index:
            continue
        data = json.loads(line.decode("utf-8"))
        out.append(canonical_json_bytes(data))
    return out


def platform_file_store(tmp: str):
    from platform import FilePlatformStore

    return FilePlatformStore(Path(tmp) / "store")


def case_11_snapshot_journal_consistency(results: List[Result]) -> None:
    name = "case_11_snapshot_journal_consistency"
    store = MemoryPlatformStore()
    clock = StepClock(_T0, 60)
    integrator = PlatformIntegrator(store=store, clock=clock)
    _ingest_all(integrator, _snapshots(), clock)
    checkpoint = integrator.checkpoint(session_bindings=())
    journal = AppendOnlyJournal(store=MemoryPlatformStore())
    # rebuild a journal view over the same records via a fresh store
    mirror = MemoryPlatformStore()
    for record in integrator.journal_records():
        mirror.append_journal_line(
            canonical_json_bytes(record.to_dict()) + b"\n"
        )
    loaded = AppendOnlyJournal.load(mirror)
    problems: List[str] = []
    verified = load_verified_checkpoint(loaded, checkpoint.to_bytes())
    if verified.checkpoint_id != checkpoint.checkpoint_id:
        problems.append("verified checkpoint identity drifted")
    # a fabricated checkpoint state (content-valid: its own derived
    # id) that is NOT the fold of its prefix fails closed at the
    # state/prefix consistency gate
    fabricated = ReconciledState(
        interface_records=checkpoint.reconciled_state.interface_records,
        platform_record=checkpoint.reconciled_state.platform_record,
        lost_sessions=("sha256:fabricated",),
    )
    fabricated_checkpoint = PlatformCheckpoint(
        checkpoint_id="",
        schema=checkpoint.schema,
        reconciled_state=fabricated,
        journal_tail_sequence=checkpoint.journal_tail_sequence,
        journal_tail_digest=checkpoint.journal_tail_digest,
        session_bindings=checkpoint.session_bindings,
        produced_at=checkpoint.produced_at,
    )
    problem = _expect_error(
        name, PlatformReasonCode.CHECKPOINT_MISMATCH,
        load_verified_checkpoint, loaded,
        fabricated_checkpoint.to_bytes(),
    )
    if problem:
        problems.append(problem)
    # a tampered checkpoint id fails content verification
    tampered_id = dict(checkpoint.to_dict())
    tampered_id["produced_at"] = "2027-01-01T00:00:00Z"
    problem = _expect_error(
        name, PlatformReasonCode.CHECKPOINT_INVALID,
        load_verified_checkpoint, loaded,
        canonical_json_bytes(tampered_id),
    )
    if problem:
        problems.append(problem)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "checkpoint == fold(prefix); fabricated state and tampered "
                 "content fail closed")
    )


# ---------------------------------------------------------------------------
# Recovery (criteria 3 + 4)
# ---------------------------------------------------------------------------


def case_12_restart_recovery(results: List[Result]) -> None:
    name = "case_12_restart_recovery"
    with tempfile.TemporaryDirectory() as tmp:
        store = platform_file_store(tmp)
        clock = StepClock(_T0, 60)
        integrator = PlatformIntegrator(store=store, clock=clock)
        _ingest_all(integrator, _snapshots(), clock)
        checkpoint = integrator.checkpoint(session_bindings=())
        digest_before = integrator.journal_digest()
        state_digest_before = integrator.state().state_digest()
        # process death: all in-memory state is gone
        del integrator
        # restart WITHOUT fresh sources: pure durable reconstruction
        integrator2, report = PlatformIntegrator.recover(
            store=store, clock=StepClock(_T_RECOVERY, 60),
        )
        problems: List[str] = []
        if integrator2.journal_digest() != digest_before:
            problems.append("journal digest changed across restart")
        if integrator2.state().state_digest() != state_digest_before:
            problems.append("state changed across restart (no drift source)")
        if report.checkpoint_id != checkpoint.checkpoint_id:
            problems.append("recovered from a different checkpoint")
        if report.journal_records_replayed != 0:
            problems.append("replayed records although the tail was empty")
        if report.lost_sessions != ():
            problems.append("session loss recorded with no bindings")
        # the journal CONTINUES (the successor's appends extend it)
        snapshot = _snap(name=VPN_IF, kind="other", addresses=("fd00::a:9",))
        integrator2.ingest_interface_observation(
            snapshot, observed_at="2025-06-01T07:00:00Z"
        )
        if len(integrator2.journal_records()) != 6:
            problems.append("journal continuation failed")
        integrator2.verify_integrity()
        if problems:
            results.append(fail(name, "; ".join(problems)))
            return
        results.append(
            ok(name, "durable restart reconstructs state + journal exactly; "
                     "journal continues from the tail")
        )


def case_13_journal_tail_replay(results: List[Result]) -> None:
    name = "case_13_journal_tail_replay"
    store = MemoryPlatformStore()
    clock = StepClock(_T0, 60)
    integrator = PlatformIntegrator(store=store, clock=clock)
    _ingest_all(integrator, _snapshots(), clock)
    # checkpoint at position 5 (after the 5 epoch-1 events)
    checkpoint = integrator.checkpoint(session_bindings=())
    # more events land AFTER the checkpoint
    integrator.ingest_interface_removal(
        USB_IF, observed_at="2025-06-01T02:00:00Z"
    )
    snapshot = _snap(name=VPN_IF, kind="other", addresses=("fd00::a:9",))
    integrator.ingest_interface_observation(
        snapshot, observed_at="2025-06-01T03:00:00Z"
    )
    integrator.ingest_platform_state(
        _platform_snapshot(background=True), observed_at="2025-06-01T04:00:00Z"
    )
    records = list(integrator.journal_records())
    problems: List[str] = []
    # tail replay on the checkpoint == full fold (the deterministic
    # equivalence the contract requires)
    full = fold_state(records)
    tail = fold_state_from(checkpoint.reconciled_state, records[checkpoint.journal_tail_sequence:])
    if not full.state_equal(tail):
        problems.append("tail replay disagrees with the full fold")
    # recovery from the mid-journal checkpoint replays exactly the tail
    integrator2, report = PlatformIntegrator.recover(
        store=store, clock=StepClock(_T_RECOVERY, 60),
    )
    if report.journal_records_replayed != 3:
        problems.append("replayed %d records, expected the 3-record tail"
                        % report.journal_records_replayed)
    if not integrator2.state().state_equal(full):
        problems.append("recovered state != full fold")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "checkpoint + tail replay == full fold (byte-identical)")
    )


def case_14_fresh_observation_reconciliation(results: List[Result]) -> None:
    name = "case_14_fresh_observation_reconciliation"
    store = MemoryPlatformStore()
    clock = StepClock(_T0, 60)
    integrator = PlatformIntegrator(store=store, clock=clock)
    _ingest_all(integrator, _snapshots(), clock)
    integrator.checkpoint(session_bindings=())
    del integrator
    fresh = MutableInterfaceSource(_fresh_snapsets())
    fresh_platform = StaticPlatformSource(
        _platform_snapshot(background=True)
    )
    integrator2, report = PlatformIntegrator.recover(
        store=store, clock=StepClock(_T_RECOVERY, 60),
        interface_source=fresh, platform_source=fresh_platform,
    )
    got = set(
        "%s:%s" % (item.kind, item.platform_ref) for item in report.divergences
    )
    expected = {
        "%s:%s" % (DIVERGENCE_CHANGED, WIFI_IF),
        "%s:%s" % (DIVERGENCE_REMOVED, USB_IF),
        "%s:%s" % (DIVERGENCE_APPEARED, VPN_IF),
        "%s:%s" % (DIVERGENCE_CHANGED, "platform"),
    }
    problems: List[str] = []
    if got != expected:
        problems.append("divergences %r != expected %r" % (sorted(got), sorted(expected)))
    if len(report.fresh_event_ids) != 4:
        problems.append("expected 4 fresh events (3 interface + 1 platform), got %d"
                        % len(report.fresh_event_ids))
    state = integrator2.state()
    if WIFI_IF not in state.present_interface_names():
        problems.append("wlan0 lost after reconciliation")
    if USB_IF in state.present_interface_names():
        problems.append("usb0 still present after removal divergence")
    if VPN_IF not in state.present_interface_names():
        problems.append("vpn0 not reconciled in")
    # the reconciled seams reflect the POST-divergence state
    discovered = integrator2.reconciled_interface_source().discover()
    names = tuple(sorted(snapshot.name for snapshot in discovered))
    if names != (CELL_IF, ETH_IF, VPN_IF, WIFI_IF):
        problems.append("reconciled source shows %r" % (names,))
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "changed/removed/appeared divergences reported honestly and "
                 "reconciled through the ordinary boundary")
    )


def _fresh_snapsets() -> Tuple[InterfaceSnapshot, ...]:
    return _fresh_snapshots()


def case_15_stale_state_handling(results: List[Result]) -> None:
    name = "case_15_stale_state_handling"
    store = MemoryPlatformStore()
    clock = StepClock(_T0, 60)
    integrator = PlatformIntegrator(store=store, clock=clock)
    snapshot = _snap(name=WIFI_IF, kind="wireless", addresses=("fd00::a:1",))
    integrator.ingest_interface_observation(
        snapshot, observed_at="2025-06-01T00:02:00Z"
    )
    # a STALE observation (older instant) is journaled but inert
    outcome = integrator.ingest_interface_observation(
        snapshot, observed_at="2025-06-01T00:01:00Z"
    )
    problems: List[str] = []
    if outcome.status != IngestionStatus.STALE:
        problems.append("stale observation not reported stale")
    if outcome.sequence != 2:
        problems.append("stale observation not journaled (no forensic record)")
    if integrator.state().present_interface_names() != (WIFI_IF,):
        problems.append("state changed on a stale observation")
    record = integrator.state().interface_map()[WIFI_IF]
    if record.observed_at != "2025-06-01T00:02:00Z":
        problems.append("stale observation moved the state backward")
    # the fold agrees: the stale record is inert
    folded = fold_state(list(integrator.journal_records()))
    if not folded.state_equal(integrator.state()):
        problems.append("fold disagrees about staleness")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "stale observation journaled for forensics, deterministically "
                 "inert (no transition, ACR-006 s2)")
    )


def case_16_session_loss_honesty(results: List[Result]) -> None:
    name = "case_16_session_loss_honesty"
    runtime, peer, session_id, shared = _world()
    store = MemoryPlatformStore()
    integrator = PlatformIntegrator(store=store, clock=shared)
    _ingest_all(integrator, _snapshots(), shared)
    manager = NetworkPathManager(runtime, shared)
    manager.discover()
    wifi = _path_for(manager, WIFI_IF)
    manager.validate(wifi)
    manager.bind(wifi, session_id)
    manager.probe(wifi)
    manager.activate(wifi)
    bindings = session_bindings_from_manager(manager)
    checkpoint = integrator.checkpoint(session_bindings=bindings)
    # process death
    del integrator, manager, runtime, peer
    # recovery where the platform is COMPLETELY unchanged (wlan0
    # still up): the session is STILL lost honestly -- a present
    # interface never resurrects transport state
    integrator2, report = PlatformIntegrator.recover(
        store=store, clock=StepClock(_T_RECOVERY, 60),
        interface_source=MutableInterfaceSource(_snapshots()),
        platform_source=StaticPlatformSource(_platform_snapshot()),
    )
    problems: List[str] = []
    if report.lost_sessions != (session_id,):
        problems.append("lost sessions %r != the held session" % (report.lost_sessions,))
    if report.divergences != ():
        problems.append("divergences reported on an unchanged platform")
    loss_records = [
        record for record in integrator2.journal_records()
        if record.record_kind == JournalRecordKind.SESSION_LOSS
    ]
    if len(loss_records) != 1:
        problems.append("expected exactly one durable session-loss record")
    else:
        loss = loss_records[0].session_loss
        if loss.get("session_id") != session_id:
            problems.append("loss record session id mismatch")
        if loss.get("cause") != SESSION_LOSS_CAUSE:
            problems.append("loss record cause not process-restart")
        if loss.get("checkpoint_id") != checkpoint.checkpoint_id:
            problems.append("loss record not bound to the checkpoint")
        if loss.get("network_path_id") != bindings[0].network_path_id:
            problems.append("loss record path reference mismatch")
    if session_id not in integrator2.lost_session_refs():
        problems.append("lost-session reference not derivable from the journal")
    # idempotent re-recovery (crash during recovery + retry) does not
    # double-journal the loss
    integrator3, report3 = PlatformIntegrator.recover(
        store=store, clock=StepClock(_T_RECOVERY, 60),
        interface_source=MutableInterfaceSource(_snapshots()),
    )
    if len(integrator3.journal_records()) != len(integrator2.journal_records()):
        problems.append("re-recovery double-journaled the session loss")
    if report3.lost_sessions != (session_id,):
        problems.append("re-recovery lost-session set changed")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "session loss recorded durably (idempotently); a present "
                 "interface never fabricates transport liveness")
    )


def case_17_no_session_recreation(results: List[Result]) -> None:
    name = "case_17_no_session_recreation"
    runtime, peer, session_id, shared = _world()
    store = MemoryPlatformStore()
    integrator = PlatformIntegrator(store=store, clock=shared)
    _ingest_all(integrator, _snapshots(), shared)
    manager = NetworkPathManager(runtime, shared)
    manager.discover()
    wifi = _path_for(manager, WIFI_IF)
    manager.validate(wifi)
    manager.bind(wifi, session_id)
    manager.probe(wifi)
    manager.activate(wifi)
    integrator.checkpoint(
        session_bindings=session_bindings_from_manager(manager)
    )
    # process death
    del integrator, manager, runtime, peer
    # STRUCTURAL: recovery takes NO authority parameters at all -- it
    # cannot touch session/routing/identity state by construction
    import inspect

    signature = inspect.signature(PlatformIntegrator.recover)
    params = set(signature.parameters)
    expected = {"store", "clock", "interface_source", "platform_source"}
    if params != expected:
        results.append(
            fail(name, "recover() parameters %r exceed the sanctioned set %r"
                       % (sorted(params), sorted(expected)))
        )
        return
    # no session store exists during recovery; no session id is minted
    integrator2, report = PlatformIntegrator.recover(
        store=store, clock=StepClock(_T_RECOVERY, 60),
    )
    journal_text = json.dumps(
        [record.to_dict() for record in integrator2.journal_records()]
    )
    if "created" in journal_text:
        results.append(
            fail(name, "journal mentions a session created event")
        )
        return
    # the successor re-establishes through the ORDINARY authority path:
    # new session id, exactly one created event, OLD id never resurrected
    clock2 = StepClock(_T_RECOVERY, 60)
    peer2 = AgentRuntime(
        _peer_config(), clock=clock2,
        interface_source=integrator2.reconciled_interface_source(),
    )
    peer2.boot(_SECRET_B)
    peer2.expose_interfaces()
    runtime2 = AgentRuntime(
        _config(), clock=clock2,
        interface_source=integrator2.reconciled_interface_source(),
    )
    runtime2.boot(_SECRET_A)
    runtime2.expose_interfaces()
    _register_peers(runtime2, peer2, clock2)
    successor_session = _establish_session(runtime2, peer2, clock2)
    problems: List[str] = []
    if successor_session == session_id:
        problems.append("successor session id equals the dead session id")
    events = runtime2.sessions.get_events(successor_session)
    created = [
        event for event in events if event.event_type == "created"
    ]
    if len(created) != 1:
        problems.append("successor session has %d created events" % len(created))
    if runtime2.sessions.get(session_id) is not None:
        problems.append("the dead session id exists in the successor store")
    if report.lost_sessions != (session_id,):
        problems.append("recovery did not record the dead session as lost")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "recovery has no authority parameters; successor establishes "
                 "a NEW session through the ordinary path (one created event)")
    )


# ---------------------------------------------------------------------------
# Determinism (criterion 2 / verification class)
# ---------------------------------------------------------------------------


def case_18_deterministic_multi_run(results: List[Result]) -> None:
    name = "case_18_deterministic_multi_run"
    first = _scenario_stream()
    second = _scenario_stream()
    problems: List[str] = []
    for key in first:
        if first[key] != second.get(key):
            problems.append("%s diverged" % key)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "two fresh full-scenario runs: identical session ids, "
                 "checkpoint/journal/state/recovery/evidence digests")
    )


def case_19_subprocess_hash_seeds(results: List[Result]) -> None:
    name = "case_19_subprocess_hash_seeds"
    digests: Dict[str, str] = {}
    seeds = ("0", "1", "7919", None)
    for seed in seeds:
        env = dict(os.environ)
        if seed is None:
            env.pop("PYTHONHASHSEED", None)
        else:
            env["PYTHONHASHSEED"] = seed
        env.pop("PYTHONDONTWRITEBYTECODE", None)
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--determinism-stream"],
            capture_output=True, text=True, env=env, cwd=str(REPO_ROOT), timeout=300,
        )
        if proc.returncode != 0:
            results.append(
                fail(name, "seed %s exited %d: %s"
                          % (seed, proc.returncode, proc.stderr[-200:]))
            )
            return
        digests[str(seed)] = proc.stdout.strip()
    unique = set(digests.values())
    if len(unique) != 1:
        results.append(fail(name, "hash seeds diverged: %r" % digests))
        return
    results.append(
        ok(name, "PYTHONHASHSEED 0/1/7919/unset subprocesses agree "
                 "byte-for-byte on the whole digest stream")
    )


# ---------------------------------------------------------------------------
# Hygiene and structural audits (criterion 5)
# ---------------------------------------------------------------------------


def case_20_secret_hygiene(results: List[Result]) -> None:
    name = "case_20_secret_hygiene"
    stream = _scenario_stream()
    runtime, peer, session_id, shared = _world()
    store = MemoryPlatformStore()
    integrator = PlatformIntegrator(store=store, clock=shared)
    _ingest_all(integrator, _snapshots(), shared)
    manager = NetworkPathManager(runtime, shared)
    manager.discover()
    wifi = _path_for(manager, WIFI_IF)
    manager.validate(wifi)
    manager.bind(wifi, session_id)
    manager.probe(wifi)
    manager.activate(wifi)
    checkpoint = integrator.checkpoint(
        session_bindings=session_bindings_from_manager(manager)
    )
    blob = b"\n".join([
        store.journal_bytes(),
        checkpoint.to_bytes(),
        json.dumps(stream).encode("utf-8"),
    ]).decode("utf-8")
    problems: List[str] = []
    for secret in (_SECRET_A, _SECRET_B, _KEY_A, _KEY_B):
        if secret.decode("utf-8", errors="ignore") in blob:
            problems.append("secret material %r leaked into durable state" % secret)
    for token in (
        "secret", "password", "credential", "private_key", "token_hex",
        "hmac-key", "bootstrap",
    ):
        if token in blob.lower():
            problems.append("secret-like token %r in durable state" % token)
    # events themselves cannot carry arbitrary payloads: the typed
    # boundary only accepts genuine accepted snapshot models
    problem = _expect_error(
        name, PlatformReasonCode.OBSERVATION_INVALID,
        integrator.ingest_interface_observation,
        _platform_snapshot(), observed_at="2025-06-01T05:00:00Z",
    )
    if problem:
        problems.append("platform snapshot accepted as interface payload: %s" % problem)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "journal/checkpoint/report bytes secret-free; typed payloads "
                 "only (no arbitrary event payloads)")
    )


def case_21_no_shadow_authority(results: List[Result]) -> None:
    name = "case_21_no_shadow_authority"
    problems: List[str] = []
    for path in _FAMILY_FILES:
        text = path.read_text(encoding="utf-8")
        for token in _FORBIDDEN_TOKENS:
            if token in text:
                problems.append("%s contains forbidden authority token %r"
                                % (path.name, token))
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "no authority construction/mutation tokens in platform/ "
                 "(composition only; recovery has no authority parameters)")
    )


def case_22_import_discipline(results: List[Result]) -> None:
    name = "case_22_import_discipline"
    problems: List[str] = []
    for path in _FAMILY_FILES:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as error:
            problems.append("%s does not parse: %s" % (path.name, error))
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.lower()
                    if module in ("random", "secrets", "uuid", "platform", "os", "socket", "subprocess", "time"):
                        problems.append("%s imports forbidden module %r" % (path.name, module))
                    elif not (
                        module in _ALLOWED_IMPORT_MODULES
                        or any(module.startswith(prefix) for prefix in _ALLOWED_IMPORT_PREFIXES)
                    ):
                        problems.append("%s imports unsanctioned module %r" % (path.name, module))
            elif isinstance(node, ast.ImportFrom):
                module = (node.module or "").lower()
                if node.level and node.level > 0:
                    continue  # relative imports stay inside the package
                if module in ("random", "secrets", "uuid", "platform", "os", "socket", "subprocess", "time"):
                    problems.append("%s imports forbidden module %r" % (path.name, module))
                elif not (
                    module in _ALLOWED_IMPORT_MODULES
                    or any(module.startswith(prefix) for prefix in _ALLOWED_IMPORT_PREFIXES)
                ):
                    problems.append("%s imports unsanctioned module %r" % (path.name, module))
    # vendor tokens never appear in the family
    for path in _FAMILY_FILES:
        text = path.read_text(encoding="utf-8").lower()
        for token in _VENDOR_TOKENS:
            if token in text:
                problems.append("%s encodes vendor token %r" % (path.name, token))
                break
    # stdlib platform shadowing hazard: NO repository module (outside
    # the platform family and this battery) imports the stdlib
    # ``platform`` module while the repository-local package owns the
    # name
    for path in sorted(REPO_ROOT.rglob("*.py")):
        rel = str(path.relative_to(REPO_ROOT))
        if rel.startswith("platform/") or rel == "tools/platform_selftest.py":
            continue
        if path.parts[:1] == (".git",):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, OSError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.lower() == "platform":
                        problems.append("%s imports stdlib platform (shadowing hazard)" % rel)
            elif isinstance(node, ast.ImportFrom) and not node.level:
                if (node.module or "").lower() == "platform":
                    problems.append("%s imports stdlib platform (shadowing hazard)" % rel)
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "sanctioned imports only; no vendor tokens; no "
                 "random/secrets/uuid/os/time; stdlib-platform shadowing pinned")
    )


def case_23_public_api_stability(results: List[Result]) -> None:
    name = "case_23_public_api_stability"
    import platform as _pkg

    if sorted(_pkg.__all__) != sorted(_EXPECTED_API):
        missing = set(_EXPECTED_API) - set(_pkg.__all__)
        extra = set(_pkg.__all__) - set(_EXPECTED_API)
        results.append(
            fail(name, "API drifted (missing %r, extra %r)"
                        % (sorted(missing), sorted(extra)))
        )
        return
    results.append(ok(name, "frozen public API: %d names" % len(_EXPECTED_API)))


def case_24_fail_closed_battery(results: List[Result]) -> None:
    name = "case_24_fail_closed_battery"
    problems: List[str] = []
    snapshot = _snap(name=WIFI_IF, kind="wireless", addresses=("fd00::a:1",))

    # (a) malformed event record in a store
    corrupt = MemoryPlatformStore()
    corrupt.append_journal_line(b"{not json}\n")
    problem = _expect_error(
        name, PlatformReasonCode.JOURNAL_CORRUPT,
        AppendOnlyJournal.load, corrupt,
    )
    if problem:
        problems.append("(a) %s" % problem)

    # (b) invalid platform observation (bad link kind)
    try:
        InterfaceSnapshot(
            name=WIFI_IF, link_kind="quantum", state_up=True, mtu=1500,
            speed_mbps=1, rx_bytes=0, tx_bytes=0, rx_errors=0, tx_errors=0,
        )
        problems.append("(b) bad link kind accepted by the model")
    except Exception:  # noqa: BLE001 - the accepted model rejects it
        pass
    problem = _expect_error(
        name, PlatformReasonCode.EVENT_INVALID,
        event_with_bad_payload,
    )
    if problem:
        problems.append("(b2) %s" % problem)

    # (c) tampered journal bytes at RECOVERY time
    with tempfile.TemporaryDirectory() as tmp:
        store = platform_file_store(tmp)
        clock = StepClock(_T0, 60)
        integrator = PlatformIntegrator(store=store, clock=clock)
        _ingest_all(integrator, _snapshots(), clock)
        integrator.checkpoint(session_bindings=())
        del integrator
        raw = store.journal_bytes()
        store.journal_path.write_bytes(
            raw.replace(b'"mtu":1500', b'"mtu":1599', 1)
        )
        problem = _expect_error(
            name, PlatformReasonCode.JOURNAL_CORRUPT,
            PlatformIntegrator.recover, store=store,
            clock=StepClock(_T_RECOVERY, 60),
        )
        if problem:
            problems.append("(c) %s" % problem)

    # (d) checkpoint ahead of the journal (impossible durable state)
    store = MemoryPlatformStore()
    clock = StepClock(_T0, 60)
    integrator = PlatformIntegrator(store=store, clock=clock)
    _ingest_all(integrator, _snapshots(), clock)
    checkpoint = integrator.checkpoint(session_bindings=())
    ahead = PlatformCheckpoint(
        checkpoint_id="",
        schema=checkpoint.schema,
        reconciled_state=checkpoint.reconciled_state,
        journal_tail_sequence=checkpoint.journal_tail_sequence + 1,
        journal_tail_digest=checkpoint.journal_tail_digest,
        session_bindings=checkpoint.session_bindings,
        produced_at=checkpoint.produced_at,
    )
    problem = _expect_error(
        name, PlatformReasonCode.CHECKPOINT_MISMATCH,
        load_verified_checkpoint, AppendOnlyJournal.load(store),
        ahead.to_bytes(),
    )
    if problem:
        problems.append("(d) %s" % problem)

    # (e) incompatible checkpoint schema
    old_schema = dict(checkpoint.to_dict())
    old_schema["schema"] = "adcos.platform.checkpoint.v0"
    problem = _expect_error(
        name, PlatformReasonCode.CHECKPOINT_INVALID,
        load_verified_checkpoint, AppendOnlyJournal.load(store),
        canonical_json_bytes(old_schema),
    )
    if problem:
        problems.append("(e) %s" % problem)

    # (f) persist-then-ack: a store failure leaves NO phantom state
    failing = FailingPlatformStore()
    clock = StepClock(_T0, 60)
    integrator = PlatformIntegrator(store=failing, clock=clock)
    problem = _expect_error(
        name, PlatformReasonCode.STORE_FAILED,
        integrator.ingest_interface_observation,
        snapshot, observed_at="2025-06-01T00:00:00Z",
    )
    if problem:
        problems.append("(f) %s" % problem)
    if len(integrator.journal_records()) != 0:
        problems.append("(f) phantom record after store failure")
    if integrator.state().present_interface_names() != ():
        problems.append("(f) phantom state after store failure")

    # (g) silent adoption of durable state is impossible: a fresh
    # integrator requires an EMPTY store (recover() is the only path)
    problem = _expect_error(
        name, PlatformReasonCode.RECOVERY_REJECTED,
        PlatformIntegrator, store=store, clock=StepClock(_T0, 60),
    )
    if problem:
        problems.append("(g) %s" % problem)

    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "corrupt journal/invalid observation/tampered bytes/ahead "
                 "checkpoint/old schema/store failure/stale adoption all "
                 "fail closed; no partial state")
    )


def event_with_bad_payload() -> None:
    event_from_redelivery({
        "event_id": "",
        "kind": "interface-observation",
        "source": "battery-push",
        "platform_ref": WIFI_IF,
        "payload": {"name": WIFI_IF, "link_kind": "quantum-link"},
        "observed_at": "2025-06-01T00:00:00Z",
    })


# ---------------------------------------------------------------------------
# Composition with existing authorities (criterion 1/5)
# ---------------------------------------------------------------------------


def case_25_composition_reconciled_sources(results: List[Result]) -> None:
    name = "case_25_composition_reconciled_sources"
    store = MemoryPlatformStore()
    clock = StepClock(_T0, 60)
    integrator = PlatformIntegrator(store=store, clock=clock)
    _ingest_all(integrator, _snapshots(), clock)
    interface_source = integrator.reconciled_interface_source()
    platform_source = integrator.reconciled_platform_source()
    problems: List[str] = []
    # the reconciled views implement the FROZEN accepted seams
    if not isinstance(interface_source, InterfaceSource):
        problems.append("reconciled interface source is not an InterfaceSource")
    if not isinstance(platform_source, MobilePlatformSource):
        problems.append("reconciled platform source is not a MobilePlatformSource")
    discovered = tuple(
        sorted(interface_source.discover(), key=lambda item: item.name)
    )
    expected = tuple(
        sorted(_snapshots(), key=lambda item: item.name)
    )
    if discovered != expected:
        problems.append("reconciled discovery != the accepted snapshot set")
    read = platform_source.read()
    if read != _platform_snapshot():
        problems.append("reconciled platform read != the accepted snapshot")
    # removals are reflected in the seam
    integrator.ingest_interface_removal(
        USB_IF, observed_at="2025-06-01T01:00:00Z"
    )
    names = tuple(sorted(item.name for item in interface_source.discover()))
    if USB_IF in names:
        problems.append("removed interface still discovered")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "reconciled views implement the frozen WORK-033/W035 seams "
                 "over event-reconstructed state")
    )


def case_26_full_integration_scenario(results: List[Result]) -> None:
    name = "case_26_full_integration_scenario"
    stream = _scenario_stream()
    problems: List[str] = []
    if not stream["session_id"]:
        problems.append("no production session in epoch 1")
    if stream["session_id"] == stream["successor_session_id"]:
        problems.append("successor re-used the dead session id")
    if stream["lost_sessions"] != stream["session_id"]:
        problems.append("recovery did not honestly lose the held session")
    if stream["bindings"] != "1":
        problems.append("expected exactly one binding reference")
    expected_divergences = sorted([
        "%s:%s" % (DIVERGENCE_CHANGED, WIFI_IF),
        "%s:%s" % (DIVERGENCE_REMOVED, USB_IF),
        "%s:%s" % (DIVERGENCE_APPEARED, VPN_IF),
        "%s:%s" % (DIVERGENCE_CHANGED, "platform"),
    ])
    if sorted(stream["divergences"].split(",")) != expected_divergences:
        problems.append("divergence stream mismatch: %r" % stream["divergences"])
    if stream["successor_paths"] != "4":
        problems.append(
            "successor manager discovered %s paths (expected 4 post-drift)"
            % stream["successor_paths"]
        )
    for key in ("checkpoint_id", "journal_digest", "state_digest",
                "recovery_digest", "evidence_digest", "content_digest"):
        if not stream[key].startswith("sha256:"):
            problems.append("%s is not a sha256 digest" % key)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "golden path: production -> death -> recovery -> successor; "
                 "divergences + loss honest; digests content-derived")
    )


def case_27_honest_evidence_disclosure(results: List[Result]) -> None:
    name = "case_27_honest_evidence_disclosure"
    expected = {
        "software_deterministic_event_journal": "supported-verified",
        "software_deterministic_recovery": "supported-verified",
        "physical_device": "open",
    }
    if PLATFORM_EVIDENCE_STATUS != expected:
        results.append(
            fail(name, "evidence disclosure drifted: %r" % PLATFORM_EVIDENCE_STATUS)
        )
        return
    results.append(
        ok(name, "two-track disclosure pinned: software verified; PHYSICAL "
                 "device evidence OPEN and W040-owned (no synthetic claim)")
    )


def case_28_py_compile(results: List[Result]) -> None:
    name = "case_28_py_compile"
    problems: List[str] = []
    for path in _FAMILY_FILES + [Path(__file__).resolve()]:
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as error:
            problems.append("%s: %s" % (path.name, error))
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(ok(name, "platform/ family + battery compile cleanly"))


def _origin_main_available() -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/main"],
        capture_output=True, cwd=str(REPO_ROOT),
    )
    return proc.returncode == 0


def case_29_frozen_spec_intact(results: List[Result]) -> None:
    name = "case_29_frozen_spec_intact"
    frozen = (
        "spec/architecture.md",
        "spec/architecture-lock.md",
        "spec/mission.md",
        "spec/governance.md",
        "spec/change-control.md",
        "spec/workflow.md",
        "spec/work-items.md",
        "spec/dependency-graph.md",
        "spec/schemas/protocol.json",
        "spec/architect/authorizations/WORK-042.yaml",
    )
    if not _origin_main_available():
        results.append(
            ok(name, "skipped (no origin/main ref; CI enforces the frozen surfaces)")
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
        ok(name, "frozen architecture/lock/mission/governance/workflow/backlog/"
                 "schema/authorization byte-identical to origin/main")
    )


def case_30_pr_delta_shape(results: List[Result]) -> None:
    name = "case_30_pr_delta_shape_authorized_scope"
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
        if path.startswith("spec/"):
            problems.append("delta touches frozen spec/: %s" % path)
            continue
        if path == AUTHORIZED_CI_WIRING:
            continue  # sanctioned additive CI wiring (checked below)
        if not any(
            path == scope or path.startswith(scope) for scope in _AUTHORIZED_PATHS
        ):
            problems.append("delta outside authorized scope: %s" % path)
    # the CI wiring delta must be purely ADDITIVE and never weaken a step
    if AUTHORIZED_CI_WIRING in delta:
        workflow = (REPO_ROOT / AUTHORIZED_CI_WIRING).read_text(encoding="utf-8")
        wiring_diff = subprocess.run(
            ["git", "diff", "origin/main", "--", AUTHORIZED_CI_WIRING],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        removed = [
            line for line in wiring_diff.stdout.splitlines()
            if line.startswith("-") and "python3 tools/" in line
        ]
        if removed:
            problems.append("CI wiring removed an existing step: %r" % removed[:3])
        if "python3 tools/platform_selftest.py" not in workflow:
            problems.append("CI wiring missing the platform battery step")
        added = [
            line for line in wiring_diff.stdout.splitlines()
            if line.startswith("+") and "python3 tools/" in line
        ]
        for line in added:
            if "platform_selftest.py" not in line:
                problems.append("CI wiring added an unrelated step: %r" % line)
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "delta confined to the WORK-042-CORE-001 scope (%d file(s) + "
                 "sanctioned additive CI wiring)" % len(delta))
    )


def case_31_evidence_chain_verification(results: List[Result]) -> None:
    name = "case_31_evidence_chain_verification"
    stream = _scenario_stream()
    runtime, peer, session_id, shared = _world()
    store = MemoryPlatformStore()
    integrator = PlatformIntegrator(store=store, clock=shared)
    _ingest_all(integrator, _snapshots(), shared)
    manager = NetworkPathManager(runtime, shared)
    manager.discover()
    wifi = _path_for(manager, WIFI_IF)
    manager.validate(wifi)
    manager.bind(wifi, session_id)
    manager.probe(wifi)
    manager.activate(wifi)
    integrator.checkpoint(
        session_bindings=session_bindings_from_manager(manager)
    )
    del integrator, manager, runtime, peer
    integrator2, report = PlatformIntegrator.recover(
        store=store, clock=StepClock(_T_RECOVERY, 60),
    )
    evidence = assemble_recovery_evidence(report)
    problems: List[str] = []
    if not verify_recovery_evidence(evidence):
        problems.append("evidence record failed independent verification")
    # the record digest recomputes from the recorded facts
    recomputed = "sha256:" + hashlib.sha256(
        canonical_json_bytes(evidence.to_dict())
    ).hexdigest()
    if recomputed != evidence.record_digest():
        problems.append("record digest not recomputable")
    # the journal digest recomputes from the journal records
    recomputed_journal = record_list_digest(list(integrator2.journal_records()))
    if recomputed_journal != evidence.journal_digest:
        problems.append("journal digest not recomputable from the records")
    # honest loss is always recorded with loss record ids
    if report.lost_sessions and not report.session_loss_record_ids:
        problems.append("lost sessions without durable loss records")
    # a fabricated record (resurrection claim) fails verification
    fabricated = dict(evidence.to_dict())
    fabricated["lost_sessions"] = []
    if verify_recovery_evidence_type(fabricated):
        problems.append("fabricated no-loss record verified")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "recovery evidence independently verifiable; digests "
                 "recompute; fabricated records fail")
    )


def verify_recovery_evidence_type(payload: dict) -> bool:
    """Re-verify a fabricated payload through the public API."""
    from platform.evidence import RecoveryEvidenceRecord

    try:
        record = RecoveryEvidenceRecord(
            checkpoint_id=str(payload.get("checkpoint_id", "")),
            journal_digest=str(payload.get("journal_digest", "")),
            state_digest=str(payload.get("state_digest", "")),
            recovery_digest=str(payload.get("recovery_digest", "")),
            journal_records_replayed=int(
                payload.get("journal_records_replayed", 0)
            ),
            fresh_event_ids=tuple(payload.get("fresh_event_ids", ())),
            divergences=tuple(payload.get("divergences", ())),
            lost_sessions=tuple(payload.get("lost_sessions", ())),
            session_loss_record_ids=tuple(
                payload.get("session_loss_record_ids", ())
            ),
        )
    except Exception:  # noqa: BLE001
        return False
    from platform import verify_recovery_evidence as _verify

    return _verify(record)


def case_32_polling_fallback_change_detection(results: List[Result]) -> None:
    name = "case_32_polling_fallback_change_detection"
    store = MemoryPlatformStore()
    clock = StepClock(_T0, 60)
    integrator = PlatformIntegrator(store=store, clock=clock)
    snapshots = _snapshots()
    # first sweep ingests everything (all references are new)
    outcomes = integrator.ingest_from_sources(
        interface_source=MutableInterfaceSource(snapshots),
        platform_source=StaticPlatformSource(_platform_snapshot()),
        observed_at="2025-06-01T00:00:00Z",
    )
    first_count = len(outcomes)
    problems: List[str] = []
    if first_count != 5:
        problems.append("first sweep ingested %d events (expected 5)" % first_count)
    # an UNCHANGED platform emits NOTHING (polling is change-detected,
    # never a polling-only semantic)
    outcomes = integrator.ingest_from_sources(
        interface_source=MutableInterfaceSource(snapshots),
        platform_source=StaticPlatformSource(_platform_snapshot()),
        observed_at="2025-06-01T00:01:00Z",
    )
    if len(outcomes) != 0:
        problems.append("unchanged sweep emitted %d events" % len(outcomes))
    # a changed sweep emits ONLY the changes (ACR-006 s2: no
    # transition inferred from stale re-reads)
    outcomes = integrator.ingest_from_sources(
        interface_source=MutableInterfaceSource(_fresh_snapshots()),
        platform_source=StaticPlatformSource(
            _platform_snapshot(background=True)
        ),
        observed_at="2025-06-01T00:02:00Z",
    )
    changed_refs = sorted(
        record.event.platform_ref
        for record in integrator.journal_records()
        if record.sequence > first_count
    )
    if changed_refs != sorted([WIFI_IF, USB_IF, VPN_IF, "platform"]):
        problems.append("change-detected refs %r" % changed_refs)
    # the event-first PRIMARY path is push (the boundary accepts one
    # host-pushed observation at a time -- exercised throughout)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "fallback is change-detected (unchanged sweep emits nothing); "
                 "primary path is event-first push")
    )


def main() -> int:
    results: List[Result] = []
    for case in (
        case_01_frozen_vocabularies,
        case_02_event_schema_round_trip,
        case_03_content_derived_event_ids,
        case_04_event_ordering,
        case_05_snapshot_round_trip,
        case_06_event_to_snapshot_reconciliation,
        case_07_idempotent_replay,
        case_08_duplicate_and_contradiction_rejection,
        case_09_journal_append_only,
        case_10_journal_tamper_detection,
        case_11_snapshot_journal_consistency,
        case_12_restart_recovery,
        case_13_journal_tail_replay,
        case_14_fresh_observation_reconciliation,
        case_15_stale_state_handling,
        case_16_session_loss_honesty,
        case_17_no_session_recreation,
        case_18_deterministic_multi_run,
        case_19_subprocess_hash_seeds,
        case_20_secret_hygiene,
        case_21_no_shadow_authority,
        case_22_import_discipline,
        case_23_public_api_stability,
        case_24_fail_closed_battery,
        case_25_composition_reconciled_sources,
        case_26_full_integration_scenario,
        case_27_honest_evidence_disclosure,
        case_28_py_compile,
        case_29_frozen_spec_intact,
        case_30_pr_delta_shape,
        case_31_evidence_chain_verification,
        case_32_polling_fallback_change_detection,
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
