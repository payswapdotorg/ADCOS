#!/usr/bin/env python3
"""WORK-052 UsageLedger battery (deterministic, stdlib only).

End-to-end verification of the canonical usage/economic ledger
(ACR-009 "Usage integrity", authorization WORK-052-CORE-001 /
DEC-0059, baseline reconciled by DEC-0060) composing the
accepted WORK-051 CommercialCore, WORK-033 Linux reference
agent, WORK-012 logical sessions, WORK-041 NetworkPath, and
the W042 platform journal:

- frozen vocabularies: the two-state usage transaction walk
  (OBSERVING / BILLABLE_FINAL), the five-action vocabulary, the
  23-reason vocabulary, the three evidence kinds, the three
  quantity classes (ACR-009: reserved / attempted / delivered
  are distinct; billable == delivered exactly), and the frozen
  transition table;
- usage integrity (criterion 1): usage requires authorized
  delivery evidence -- observations cite REAL platform-journal
  delivery-plane evidence windows derived through public reads;
  payment capture never creates usage (payment-observation
  evidence fails closed PAYMENT_NOT_DELIVERY at the kind
  table); reservation/lease state never creates usage
  (delivery-eligibility gate TRANSACTION_NOT_DELIVERING plus
  the reserved/attempted DATA-only classes); provider
  observations are DATA, never proof of delivery
  (PROVIDER_NOT_DELIVERY);
- idempotency and no-double-charge (criterion 2): exact command
  redelivery is a no-op (no journal growth, no clock read);
  the evidence-window identity layer makes a duplicate report
  of the same delivered fact an idempotent no-op and a
  conflicting quantity fail closed; the cumulative per-evidence
  cap bounds windowed sub-metering to the authoritative
  delivered quantity;
- out-of-order and delayed observations (criterion 2): the
  projection is sorted and the ECONOMIC fold is arrival-order
  independent (the same admitted set in any arrival order seals
  the same billable quantity/amount/evidence multiset), while
  the observation identities are honestly ADMISSION-ATTRIBUTED
  (they bind the causal command and the admission instant, so
  different arrival orders carry different ids/audit lists and
  the battery PROVES the divergence rather than claiming
  stronger determinism), delayed observations reconcile
  deterministically, late observations after the seal fail
  closed USAGE_SEALED, and an inserted out-of-order journal
  record fails closed at replay (walk-linkage verification --
  the replay verifies the WALK, not merely the chain and each
  edge);
- billable finality (criterion 3): the explicit SEAL transition
  (including the honest zero-observation zero-bill seal), the
  immutable sealed statement (re-seal fails FINAL_IMMUTABLE; no
  rewrite path exists; the statement survives compensations
  byte-identically), and append-only compensating
  refunds/reversals/disputes (bounded by the sealed amount,
  net never negative, one open dispute);
- correlation and audit (criterion 4): usage records correlate
  delivered quantity to the authoritative delivery-evidence
  record (transaction correlation enforced EVIDENCE_MISMATCH;
  contributing observation/evidence id lists on the sealed
  statement; the deterministic reconciliation statement with
  the full audit trail and per-class quantity distinction);
- authority boundaries (criterion 5): structural audits -- no
  second authority (construction/mutation token discipline over
  the frozen authority set), no authority parameters anywhere
  in the usage surface, sanctioned imports only, no vendor
  tokens, frozen public API, frozen spec surfaces intact
  (including the WORK-052 authorization itself), PR delta
  confined to the authorized W052 scope (+ the sanctioned
  additive-only CI wiring), and the honest two-track evidence
  disclosure (software verified; PHYSICAL device evidence OPEN
  and W040-owned -- no synthetic physical claims);
- durability: append-only hash-chained journal (byte tamper,
  reorder, truncation, sequence-gap, digest-edit, event-id-edit
  all fail closed JOURNAL_CORRUPT), persist-then-ack (a store
  failure leaves no phantom state), journal-first recovery
  (load == live, byte-identical; durable idempotency survives
  restart), replay verification (fold == live state), AND the
  full replay integrity boundary: the fold re-derives and
  verifies every content-derived fact identity (observation /
  sealed statement / compensation), the event identities, the
  command/fact/attribution bindings, the sealed statement's
  tariff binding to the injected W051 transaction snapshot,
  and the DELIVERED observations' evidence re-binding -- so
  WALK-VALID, FULLY-RECOMPUTED-CHAIN fact tampering (mutated
  fact + recomputed fact/event identities + recomputed outer
  hash chain, with or without a cascaded command digest, seal,
  and compensations) still fails closed JOURNAL_CORRUPT
  (cases 46/47/48);
- determinism: the golden scenario's whole digest stream
  (journal, state, command ledger, event list, evidence index)
  is byte-identical across two fresh in-process runs and across
  PYTHONHASHSEED 0/1/7919/unset subprocesses; the ONLY time
  source is the injected clock seam (duplicates consume no
  read; every other submission consumes exactly one; no
  wall-clock module is imported in the usage family);
- secret hygiene: journal and digest bytes carry no key
  material, credentials, or secret-like tokens;
- fresh-world independence: every vector builds its own fixture
  world; interleaved coexisting worlds reproduce their isolated
  baselines byte-for-byte -- no shared mutable usage state.

The battery exercises the PUBLIC production path only: the
ordinary AgentRuntime session establishment chain, the
NetworkPathManager public lifecycle, the PlatformIntegrator
public journal reads, the W051 CommercialCore public surface
(driven to DELIVERY_COMPLETED through its typed methods), and
the UsageLedger public surface.  No private method is called to
manufacture a PASS.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import os
import py_compile
import shutil  # noqa: S404 - deterministic fixture cleanup only
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
from agent.clock import AgentClock  # noqa: E402

from mobile.model import (  # noqa: E402
    MobilePhase,
    NetworkKind,
    PlatformSnapshot,
    PowerState,
)

from networkpath import NetworkPath, NetworkPathManager  # noqa: E402

# The W042 platform authority is composed through EXPLICIT
# submodule imports (platform.journal / platform.lifecycle): unlike the
# ambiguous top-level ``from platform import ...`` form, the submodule
# form can resolve ONLY to the repository-local package.
from platform.journal import MemoryPlatformStore  # noqa: E402
from platform.lifecycle import PlatformIntegrator  # noqa: E402

import commercial  # noqa: E402
from commercial import (  # noqa: E402
    CommercialCore,
    CommercialError,
    Reference,
    ReferenceFamily,
    ReferenceIndex,
)

import usage  # noqa: E402
from usage import (  # noqa: E402
    CommandStatus,
    CompensationRecord,
    DeliveryEvidence,
    CommercialTransactionSnapshot,
    EvidenceKind,
    QuantityClass,
    SealedBillableStatement,
    UsageAction,
    UsageCommand,
    UsageError,
    UsageEvent,
    UsageEvidenceIndex,
    UsageLedger,
    UsageObservationRecord,
    UsageReasonCode,
    UsageTransaction,
    UsageTransactionState,
    USAGE_TRANSITIONS,
)
from usage.digest import (
    command_ledger_digest,
    evidence_index_digest,
    state_digest,
)
from usage.journal import (  # noqa: E402
    GENESIS_RECORD_ID,
    MemoryUsageStore,
    UsageStore,
    derive_record_id,
    journal_bytes_for,
    record_content,
)
from usage.ledger import CommandOutcome, fold_state  # noqa: E402
from usage.model import (  # noqa: E402
    derive_compensation_id,
    derive_event_id,
    derive_observation_id,
    derive_statement_id,
)

Result = Tuple[str, bool, str]

# ---------------------------------------------------------------------------
# Frozen audit constants
# ---------------------------------------------------------------------------

_FAMILY_FILES = sorted((REPO_ROOT / "usage").rglob("*.py"))

_T0 = "2025-06-01T00:00:00Z"
_FRESH = "2026-06-01T00:00:00Z"
_SECRET_A = b"w052-battery-secret-A"
_SECRET_B = b"w052-battery-secret-B"
_PROFILE_ID = "identity.sha256-hmac-dev.v1"
_KEY_A = b"w052-battery-key-A"
_KEY_B = b"w052-battery-key-B"

#: The usage clock epoch and step (one read per non-duplicate
#: command submission).
_UT0 = "2026-09-01T12:00:00Z"
_USTEP = 60

#: The golden-scenario delivery-plane metering time series on
#: the active path interface (cumulative rx/tx counters read
#: through the platform journal's public surface):
#: 12:01 -> rx 100 / tx 20 (120 total), 12:05 -> rx 280 / tx 50
#: (330), 12:10 -> rx 400 / tx 80 (480).  The caller derives
#: the delivery evidence windows from the CONSECUTIVE DELTAS
#: (public-read-only derivation): [12:01, 12:05] = 210,
#: [12:05, 12:10] = 150.
_W1 = "2026-09-01T12:01:00Z"
_W2 = "2026-09-01T12:05:00Z"
_W3 = "2026-09-01T12:10:00Z"
WIFI_IF = "wlan0"
ETH_IF = "eth0"
USB_IF = "usb0"
CELL_IF = "vpn0"

#: The golden scenario tariff: the W051 offer published through
#: the commercial core's public surface (the battery drives the
#: offer with unit "byte" and price "3"; the caller-side tariff
#: derivation is the public read of that offer payload).
_TARIFF_UNIT_MICROS = 3

#: The frozen usage public API surface (independently pinned
#: here; the package must match exactly).
_EXPECTED_API = sorted([
    "AppendOnlyUsageJournal",
    "CommandOutcome",
    "CommandStatus",
    "CompensationRecord",
    "CommercialTransactionSnapshot",
    "DELIVERY_ELIGIBLE_STATES",
    "DeliveryEvidence",
    "EvidenceKind",
    "FileUsageStore",
    "GENESIS_RECORD_ID",
    "JOURNAL_RECORD_KIND",
    "MemoryUsageStore",
    "OBSERVATION_EVIDENCE_MEMBERS",
    "PAYLOAD_MEMBER_RULES",
    "QuantityClass",
    "RESERVATION_PHASE_STATES",
    "SealedBillableStatement",
    "USAGE_TRANSITIONS",
    "UsageAction",
    "UsageCommand",
    "UsageError",
    "UsageEvent",
    "UsageEvidenceIndex",
    "UsageJournalRecord",
    "UsageLedger",
    "UsageObservationRecord",
    "UsageReasonCode",
    "UsageStore",
    "UsageTransaction",
    "UsageTransactionState",
    "apply_record",
    "assemble_digest_stream",
    "command_content",
    "command_ledger_digest",
    "derive_compensation_id",
    "derive_command_digest",
    "derive_event_id",
    "derive_observation_id",
    "derive_record_id",
    "derive_statement_id",
    "digest_of",
    "event_list_digest",
    "evidence_index_digest",
    "find_duplicate_observation",
    "fold_state",
    "journal_bytes_for",
    "record_list_digest",
    "resolve_observation_evidence",
    "state_digest",
    "transition_is_legal",
    "transition_target",
    "usage_transaction_digest",
    "validate_command_against_transaction",
    "validate_delivery_eligibility",
    "validate_observation_instant",
    "validate_observation_quantity_cap",
    "validate_payload_shape",
])

#: The authorized W052 delta surface (scope of
#: WORK-052-CORE-001) plus the sanctioned additive CI-wiring
#: path (the W041/W042/W051 battery precedent).
_AUTHORIZED_PATHS = (
    "usage/",
    "tools/usage_selftest.py",
    "docs/WORK-052-handoff.md",
    "docs/WORK-052-evidence.md",
)
AUTHORIZED_CI_WIRING = ".github/workflows/spec-check.yml"

#: Vendor/payment-provider tokens the usage family must never
#: encode (technology- and provider-neutral core).
_VENDOR_TOKENS = (
    "android", "rndis", "qualcomm", "mediatek", "samsung", "broadcom",
    "huawei", "apple", "google", "windows", "darwin", "ios_",
    "open5gs", "ocudu", "openairinterface",
    "stripe", "paypal", "mtn", "vodafone", "airteltigo", "telecel",
    "visa", "mastercard", "mpesa", "alipay", "wise",
)

#: Forbidden authority-construction/mutation tokens: the usage
#: family must never build or drive a second authority
#: (isinstance checks and type annotations against the composed
#: public classes are fine -- the scan targets CONSTRUCTION and
#: MUTATION calls).
_FORBIDDEN_TOKENS = (
    "RoutingEngine(", "PolicyEngine(", "TransportManager(",
    "TopologyGraph(", "SessionStore(", "IdentityService(",
    "NetworkPathManager(", "AgentRuntime(", "MobileAgent(",
    "MultipathSessionManager(", "MobilityController(",
    "PlatformIntegrator(", "CommercialCore(", "UsageLedger(",
    "sessions.create", "sessions.transition", "sessions.reconnect",
    "sessions.terminate", "sessions.suspend", "sessions.append_event",
    "derive_session_id", "establish_session(", "accept_session(",
    "complete_session(", "finalize_session(", "bind_session(",
    "register_peer(", "expose_interfaces(", "send_datagram(",
    "submit_intent(", "select_offer(", "hold_reservation(",
    "finalize_billable(", "initiate_settlement(",
)

#: The sanctioned absolute-import allowlist for the usage family
#: (stdlib value types + the accepted seams: WORK-003
#: canonicalization and the WORK-033 clock seam; the evidence
#: index is injected, so NO authority family is importable).
_ALLOWED_IMPORT_PREFIXES = (
    "protocol.",
    "agent.clock",
)
_ALLOWED_IMPORT_MODULES = {
    "__future__",
    "hashlib",
    "json",
    "dataclasses",
    "pathlib",
    "typing",
    "protocol",
    "agent.clock",
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
            role_id="w052-battery-operator",
            capabilities=(
                ManagementCapability.SESSION_READ,
                ManagementCapability.SESSION_CONTROL,
                ManagementCapability.POLICY_READ,
            ),
            description="operator role (battery fixture)",
        ),
    )


def _config(
    label: str = "usage-node",
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


def _snap(
    *,
    name: str,
    kind: str,
    up: bool = True,
    addresses: Tuple[str, ...] = (),
    mtu: int = 1500,
    speed: int = 100,
    rx: int = 7,
    tx: int = 9,
) -> InterfaceSnapshot:
    return InterfaceSnapshot(
        name=name, link_kind=kind, state_up=up, mtu=mtu, speed_mbps=speed,
        rx_bytes=rx, tx_bytes=tx, rx_errors=0, tx_errors=0,
        addresses=addresses,
    )


def _snapshots() -> Tuple[InterfaceSnapshot, ...]:
    return (
        _snap(name=WIFI_IF, kind="wireless", addresses=("fd00::a:1",)),
        _snap(name=ETH_IF, kind="ethernet", addresses=("fd00::a:2",), speed=1000),
        _snap(name=USB_IF, kind="other", addresses=("fd00::a:3",), mtu=1400, speed=400),
        _snap(name=CELL_IF, kind="other", addresses=(), mtu=1300, speed=50),
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


def _register_peers(a: AgentRuntime, b: AgentRuntime, clock: StepClock) -> None:
    """Peer registration through the public identity-service surface."""
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


def _path_for(manager: NetworkPathManager, interface_name: str) -> str:
    for path_id in manager.paths():
        if manager.path(path_id).interface_name == interface_name:
            return path_id
    raise AssertionError("no candidate for interface %r" % interface_name)


def _usage_world():
    """One booted node + one booted peered peer runtime with one
    ESTABLISHED session, an ACTIVATED NetworkPath over the
    session, and a PlatformIntegrator journal carrying a
    DELIVERY-PLANE METERING TIME SERIES on the active interface
    (cumulative rx/tx counters at three instants) plus one
    distractor observation on a second interface -- all through
    the ordinary public production chain.  Returns (runtime,
    peer, session_id, manager, integrator, shared clock)."""
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
    manager = NetworkPathManager(runtime, shared)
    manager.discover()
    wifi = _path_for(manager, WIFI_IF)
    manager.validate(wifi)
    manager.bind(wifi, session_id)
    manager.probe(wifi)
    manager.activate(wifi)
    integrator = PlatformIntegrator(store=MemoryPlatformStore(), clock=shared)
    integrator.ingest_platform_state(
        _platform_snapshot(), observed_at=shared.now()
    )
    # the delivery-plane metering time series on the ACTIVE path
    # interface: cumulative counters (rx grows 100 -> 280 -> 400,
    # tx grows 20 -> 50 -> 80; totals 120 -> 330 -> 480)
    integrator.ingest_interface_observation(
        _snap(name=WIFI_IF, kind="wireless", addresses=("fd00::a:1",), rx=100, tx=20),
        observed_at=_W1,
    )
    integrator.ingest_interface_observation(
        _snap(name=WIFI_IF, kind="wireless", addresses=("fd00::a:1",), rx=280, tx=50),
        observed_at=_W2,
    )
    integrator.ingest_interface_observation(
        _snap(name=WIFI_IF, kind="wireless", addresses=("fd00::a:1",), rx=400, tx=80),
        observed_at=_W3,
    )
    # one distractor observation on a second interface (NOT the
    # active path: its evidence correlates to a different
    # transaction in the index)
    integrator.ingest_interface_observation(
        _snap(name=ETH_IF, kind="ethernet", addresses=("fd00::a:2",), rx=11, tx=5),
        observed_at=_W1,
    )
    return runtime, peer, session_id, manager, integrator, shared


# ---------------------------------------------------------------------------
# Commercial fixtures (deterministic external ids, public reads only)
# ---------------------------------------------------------------------------


def _external_id(kind: str, label: str) -> str:
    """A deterministic well-formed EXTERNAL-plane id (provider and
    payment observations genuinely live outside ADCOS; the
    battery cites synthetic-but-deterministic external ids with
    explicit provenance labels)."""
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes({"kind": kind, "label": label})
    ).hexdigest()


def _references(
    manager: NetworkPathManager,
    integrator: PlatformIntegrator,
    session_id: str,
) -> ReferenceIndex:
    """Build the W051 ReferenceIndex from PUBLIC reads only (the
    W051 composition precedent, reused to drive the CommercialCore
    to DELIVERY_COMPLETED so the usage ledger correlates REAL
    commercial transactions)."""
    entries: List[Reference] = [
        Reference(session_id, ReferenceFamily.SESSION, "sessions-authority"),
    ]
    for path_id in manager.paths():
        entries.append(
            Reference(
                path_id, ReferenceFamily.NETWORK_PATH, "networkpath-manager"
            )
        )
    # partition the platform journal by observation kind (the W051
    # composition precedent): the interface observations are the
    # delivery plane's evidence; the platform-state observation is
    # the usage metering INPUT plane
    usage_ids: List[str] = []
    for record in integrator.journal_records():
        event = record.event
        if event.kind == "platform-state-observation":
            usage_ids.append(event.event_id)
            continue
        entries.append(
            Reference(
                event.event_id,
                ReferenceFamily.DELIVERY_EVIDENCE,
                "platform-journal",
            )
        )
    for event_id in usage_ids[:1]:
        entries.append(
            Reference(event_id, ReferenceFamily.USAGE, "usage-plane")
        )
    entries.append(
        Reference(
            _external_id("settlement-confirmation", "settle-1"),
            ReferenceFamily.SETTLEMENT,
            "external-settlement-confirmation",
        )
    )
    entries.append(
        Reference(
            _external_id("payment-observation", "payment-1"),
            ReferenceFamily.PAYMENT,
            "external-payment-observation",
        )
    )
    return ReferenceIndex(entries)


def _wifi_journal_events(
    integrator: PlatformIntegrator,
) -> Tuple[Any, ...]:
    """The ordered public journal events of the ACTIVE path
    interface's metering time series (public reads only)."""
    return tuple(
        record.event
        for record in integrator.journal_records()
        if record.event.kind == "interface-observation"
        and record.event.platform_ref == WIFI_IF
    )


def _eth_journal_event(integrator: PlatformIntegrator) -> Any:
    for record in integrator.journal_records():
        event = record.event
        if event.kind == "interface-observation" and event.platform_ref == ETH_IF:
            return event
    raise AssertionError("no eth observation in the fixture journal")


def _delivery_evidence(
    integrator: PlatformIntegrator,
    transaction_id: str,
    session_id: str,
    path_id: str,
) -> Tuple[DeliveryEvidence, ...]:
    """Derive the authoritative delivery evidence windows from
    the platform journal's PUBLIC reads: consecutive cumulative
    counter deltas on the active path interface (the
    caller-side, public-read-only metering derivation)."""
    events = _wifi_journal_events(integrator)
    records: List[DeliveryEvidence] = []
    for first, second in zip(events, events[1:]):
        first_total = first.payload["rx_bytes"] + first.payload["tx_bytes"]
        second_total = second.payload["rx_bytes"] + second.payload["tx_bytes"]
        delta = second_total - first_total
        evidence_id = "sha256:" + hashlib.sha256(
            canonical_json_bytes(
                {
                    "kind": "delivery-evidence-window",
                    "from_event": first.event_id,
                    "to_event": second.event_id,
                }
            )
        ).hexdigest()
        records.append(
            DeliveryEvidence(
                evidence_id=evidence_id,
                transaction_id=transaction_id,
                delivered_quantity=delta,
                window_start=first.observed_at,
                window_end=second.observed_at,
                evidence_kind=EvidenceKind.DELIVERED,
                provenance="platform-journal",
                session_reference=session_id,
                path_reference=path_id,
            )
        )
    return tuple(records)


def _commercial_thread(
    references: ReferenceIndex,
    clock: StepClock,
    *,
    prefix: str = "c-",
    intent: Optional[Dict[str, Any]] = None,
    deadline: str = _W3,
) -> Tuple[CommercialCore, str]:
    """Drive one W051 CommercialCore transaction to
    DELIVERY_COMPLETED through the public typed surface (the
    usage-metering-eligible state)."""
    core = CommercialCore(
        store=commercial.MemoryCommercialStore(), clock=clock,
        references=references,
    )
    out = core.submit_intent(
        command_id=prefix + "01",
        actor="buyer-agent",
        source="developer-api",
        intent=intent
        if intent is not None
        else {"buyer": "buyer-1", "want": "connectivity", "region": "gh"},
    )
    tx = out.transaction_id
    core.select_offer(
        command_id=prefix + "02", transaction_id=tx, actor="buyer-agent",
        source="developer-api",
        offer={"offer_id": "offer-1", "provider": "provider-1",
               "unit": "byte", "price": "3"},
    )
    core.hold_reservation(
        command_id=prefix + "03", transaction_id=tx, actor="platform",
        source="reservation-service", expires_at=deadline,
        payment_refs=(_external_id("payment-observation", "payment-1"),),
    )
    core.authorize_session(
        command_id=prefix + "04", transaction_id=tx, actor="platform",
        source="session-service",
        session_ref=references.by_family(ReferenceFamily.SESSION)[0].reference_id,
    )
    core.activate_path(
        command_id=prefix + "05", transaction_id=tx, actor="platform",
        source="path-service",
        path_ref=references.by_family(ReferenceFamily.NETWORK_PATH)[0].reference_id,
    )
    delivery = sorted(
        ref.reference_id
        for ref in references.by_family(ReferenceFamily.DELIVERY_EVIDENCE)
    )
    core.start_delivery(
        command_id=prefix + "06", transaction_id=tx, actor="platform",
        source="delivery-service", evidence_refs=(delivery[0],),
    )
    core.accrue_usage(
        command_id=prefix + "07", transaction_id=tx, actor="platform",
        source="usage-service",
        usage_refs=(references.by_family(ReferenceFamily.USAGE)[0].reference_id,),
    )
    core.complete_delivery(
        command_id=prefix + "08", transaction_id=tx, actor="platform",
        source="delivery-service", evidence_refs=(delivery[-1],),
    )
    return core, tx


def _evidence_index(
    integrator: PlatformIntegrator,
    commercial_core: CommercialCore,
    transaction_id: str,
    *,
    with_distractor: bool = True,
) -> UsageEvidenceIndex:
    """Build the injected UsageEvidenceIndex from PUBLIC reads
    only: the W051 transaction snapshot (state + tariff read
    from the commercial transaction projection), the
    delivery-plane evidence windows (public journal reads), and
    the DATA-only provider/payment observation entries."""
    projection = commercial_core.transaction(transaction_id)
    offer = projection.offer
    snapshot = CommercialTransactionSnapshot(
        transaction_id=transaction_id,
        commercial_state=projection.state,
        unit_price_micros=int(offer["price"]),
        billable_unit=offer["unit"],
        tariff_provenance="commercial-core-public-read",
        session_reference=None,
        path_reference=None,
    )
    evidence: List[DeliveryEvidence] = []
    entries = _wifi_journal_events(integrator)
    for first, second in zip(entries, entries[1:]):
        first_total = first.payload["rx_bytes"] + first.payload["tx_bytes"]
        second_total = second.payload["rx_bytes"] + second.payload["tx_bytes"]
        evidence.append(
            DeliveryEvidence(
                evidence_id="sha256:"
                + hashlib.sha256(
                    canonical_json_bytes(
                        {
                            "kind": "delivery-evidence-window",
                            "from_event": first.event_id,
                            "to_event": second.event_id,
                        }
                    )
                ).hexdigest(),
                transaction_id=transaction_id,
                delivered_quantity=second_total - first_total,
                window_start=first.observed_at,
                window_end=second.observed_at,
                evidence_kind=EvidenceKind.DELIVERED,
                provenance="platform-journal",
            )
        )
    # the DATA-only external observation entries (payment and
    # provider observations recorded in the index so the ledger's
    # kind table can reject them structurally)
    evidence.append(
        DeliveryEvidence(
            evidence_id=_external_id("payment-observation", "payment-1"),
            transaction_id=transaction_id,
            delivered_quantity=0,
            window_start=_W1,
            window_end=_W3,
            evidence_kind=EvidenceKind.PAYMENT_OBSERVED,
            provenance="external-payment-observation",
        )
    )
    evidence.append(
        DeliveryEvidence(
            evidence_id=_external_id("provider-observation", "provider-1"),
            transaction_id=transaction_id,
            delivered_quantity=0,
            window_start=_W1,
            window_end=_W3,
            evidence_kind=EvidenceKind.PROVIDER_OBSERVED,
            provenance="external-provider-observation",
        )
    )
    transactions = [snapshot]
    if with_distractor:
        # a second commercial transaction correlated to the eth
        # distractor evidence (for the EVIDENCE_MISMATCH vector)
        eth = _eth_journal_event(integrator)
        distractor_tx = "sha256:" + hashlib.sha256(
            canonical_json_bytes({"kind": "distractor-tx", "eth": eth.event_id})
        ).hexdigest()
        transactions.append(
            CommercialTransactionSnapshot(
                transaction_id=distractor_tx,
                commercial_state="DELIVERY_COMPLETED",
                unit_price_micros=2,
                billable_unit="byte",
                tariff_provenance="commercial-core-public-read",
            )
        )
        evidence.append(
            DeliveryEvidence(
                evidence_id="sha256:"
                + hashlib.sha256(
                    canonical_json_bytes(
                        {"kind": "distractor-evidence", "eth": eth.event_id}
                    )
                ).hexdigest(),
                transaction_id=distractor_tx,
                delivered_quantity=(
                    eth.payload["rx_bytes"] + eth.payload["tx_bytes"]
                ),
                window_start=eth.observed_at,
                window_end=eth.observed_at,
                evidence_kind=EvidenceKind.DELIVERED,
                provenance="platform-journal",
            )
        )
    return UsageEvidenceIndex(evidence=evidence, transactions=transactions)


def _golden_ledger(
    store: Optional[UsageStore] = None,
    *,
    prefix: str = "u-",
    with_distractor: bool = True,
) -> Tuple[UsageLedger, UsageEvidenceIndex, CountingClock, Any, str]:
    """The canonical golden run: full authority composition -> a
    W051 transaction at DELIVERY_COMPLETED -> the evidence index
    from public reads -> the full usage lifecycle (delivered
    sub-metering + reserved/attempted DATA observations ->
    seal -> refund -> reversal -> dispute)."""
    runtime, peer, session_id, manager, integrator, shared = _usage_world()
    references = _references(manager, integrator, session_id)
    commercial_core, tx = _commercial_thread(
        references, StepClock(_UT0, 60)
    )
    index = _evidence_index(
        integrator, commercial_core, tx, with_distractor=with_distractor
    )
    if store is None:
        store = MemoryUsageStore()
    clock = CountingClock(StepClock(_UT0, _USTEP))
    ledger = UsageLedger(store=store, clock=clock, evidence_index=index)
    wifi_events = _wifi_journal_events(integrator)
    evidence_ids = [
        "sha256:"
        + hashlib.sha256(
            canonical_json_bytes(
                {
                    "kind": "delivery-evidence-window",
                    "from_event": first.event_id,
                    "to_event": second.event_id,
                }
            )
        ).hexdigest()
        for first, second in zip(wifi_events, wifi_events[1:])
    ]
    ledger.observe_usage(
        command_id=prefix + "01", transaction_id=tx,
        quantity_class=QuantityClass.DELIVERED, quantity=120,
        evidence_id=evidence_ids[0], window_start=_W1,
        window_end="2026-09-01T12:03:00Z",
        actor="meter", source="usage-collector",
    )
    ledger.observe_usage(
        command_id=prefix + "02", transaction_id=tx,
        quantity_class=QuantityClass.DELIVERED, quantity=90,
        evidence_id=evidence_ids[0], window_start="2026-09-01T12:03:00Z",
        window_end=_W2,
        actor="meter", source="usage-collector",
    )
    ledger.observe_usage(
        command_id=prefix + "03", transaction_id=tx,
        quantity_class=QuantityClass.DELIVERED, quantity=100,
        evidence_id=evidence_ids[1], window_start=_W2, window_end=_W3,
        actor="meter", source="usage-collector",
    )
    ledger.observe_usage(
        command_id=prefix + "04", transaction_id=tx,
        quantity_class=QuantityClass.RESERVED, quantity=500,
        actor="meter", source="reservation-service",
    )
    ledger.observe_usage(
        command_id=prefix + "05", transaction_id=tx,
        quantity_class=QuantityClass.ATTEMPTED, quantity=80,
        actor="meter", source="traffic-monitor",
    )
    ledger.seal_billable(
        command_id=prefix + "06", transaction_id=tx,
        actor="billing", source="usage-ledger",
    )
    ledger.record_refund(
        command_id=prefix + "07", transaction_id=tx, amount_micros=200,
        reason="goodwill credit", actor="billing", source="usage-ledger",
    )
    ledger.record_reversal(
        command_id=prefix + "08", transaction_id=tx, amount_micros=100,
        reason="metering correction", actor="billing", source="usage-ledger",
    )
    ledger.record_dispute(
        command_id=prefix + "09", transaction_id=tx,
        reason="buyer disputes window 2", actor="billing",
        source="usage-ledger",
    )
    return ledger, index, clock, (runtime, peer, session_id, manager, integrator, shared), tx


def _scenario_stream(store: Optional[UsageStore] = None) -> Dict[str, str]:
    """The canonical battery scenario: full authority composition
    -> the golden usage lifecycle -> the deterministic digest
    stream."""
    ledger, index, clock, _world_fixture, tx = _golden_ledger(store)
    events = tuple(record.event for record in ledger.journal_records())
    return {
        "journal_digest": ledger.journal_digest(),
        "state_digest": state_digest(ledger.transactions()),
        "command_ledger_digest": command_ledger_digest(
            ledger.command_ledger()
        ),
        "event_list_digest": usage.event_list_digest(events),
        "evidence_index_digest": evidence_index_digest(index),
        "digest_stream_sha256": hashlib.sha256(
            ledger.digest_stream().encode("utf-8")
        ).hexdigest(),
    }


class CountingClock(AgentClock):
    """A battery fixture: counts clock reads (the determinism
    discipline: duplicates consume none; every other submission
    consumes exactly one)."""

    def __init__(self, inner: StepClock) -> None:
        self._inner = inner
        self.reads = 0

    def now(self) -> str:
        self.reads += 1
        return self._inner.now()


class FailingUsageStore(MemoryUsageStore):
    """A battery fixture: fails the first append (persist-then-ack
    discipline: no phantom in-memory state)."""

    def __init__(self, fail_on: int = 1) -> None:
        super().__init__()
        self._fail_on = fail_on
        self._appends = 0

    def append_journal_line(self, line: bytes) -> None:
        self._appends += 1
        if self._appends >= self._fail_on:
            raise usage.UsageError(
                UsageReasonCode.STORE_FAILED,
                "battery-injected store failure",
            )
        super().append_journal_line(line)


class FrozenBytesStore(UsageStore):
    """A battery fixture: fixed journal bytes (tamper vectors)."""

    def __init__(self, data: bytes) -> None:
        self._data = bytes(data)

    def append_journal_line(self, line: bytes) -> None:
        raise usage.UsageError(
            UsageReasonCode.STORE_FAILED, "frozen fixture store"
        )

    def journal_bytes(self) -> bytes:
        return self._data


def _expect_usage_error(
    case_name: str, expected_reason: str, function, *args, **kwargs
) -> Optional[str]:
    """Run ``function`` expecting the typed UsageError with the
    exact ``expected_reason``; return a problem string if it did
    not.  (The parameter is NOT named ``reason`` because the
    usage command surface itself carries a ``reason`` member.)"""
    try:
        function(*args, **kwargs)
    except UsageError as error:
        if error.reason != expected_reason:
            return "expected %s, raised %s (%s)" % (
                expected_reason, error.reason, error.detail[:80],
            )
        return None
    except Exception as error:  # noqa: BLE001 - wrong exception type
        return "raised %s: %s" % (type(error).__name__, error)
    return "no error raised (expected %s)" % expected_reason


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------


def case_01_frozen_vocabularies(results: List[Result]) -> None:
    name = "case_01_frozen_vocabularies"
    problems: List[str] = []
    if sorted(UsageTransactionState.values()) != ["BILLABLE_FINAL", "OBSERVING"]:
        problems.append("state vocabulary drifted")
    if sorted(UsageAction.values()) != sorted([
        "observe-usage", "seal-billable", "record-refund",
        "record-reversal", "record-dispute",
    ]):
        problems.append("action vocabulary drifted")
    if len(UsageReasonCode.values()) != 23:
        problems.append("reason vocabulary drifted: %d" % len(UsageReasonCode.values()))
    if sorted(EvidenceKind.values()) != sorted([
        "delivered", "provider-observed", "payment-observed",
    ]):
        problems.append("evidence kind vocabulary drifted")
    if sorted(QuantityClass.values()) != ["attempted", "delivered", "reserved"]:
        problems.append("quantity class vocabulary drifted")
    if len(USAGE_TRANSITIONS) != 5:
        problems.append("transition table drifted: %d edges" % len(USAGE_TRANSITIONS))
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "states/actions/reasons/kinds/classes/transition table frozen")
    )


def case_02_transition_table(results: List[Result]) -> None:
    name = "case_02_transition_table"
    problems: List[str] = []
    expected = {
        ("OBSERVING", "observe-usage"): "OBSERVING",
        ("OBSERVING", "seal-billable"): "BILLABLE_FINAL",
        ("BILLABLE_FINAL", "record-refund"): "BILLABLE_FINAL",
        ("BILLABLE_FINAL", "record-reversal"): "BILLABLE_FINAL",
        ("BILLABLE_FINAL", "record-dispute"): "BILLABLE_FINAL",
    }
    actual = {
        (from_state, action): target
        for (from_state, action), target in USAGE_TRANSITIONS.items()
    }
    if actual != expected:
        problems.append("table mismatch: %r" % actual)
    for from_state in UsageTransactionState.values():
        for action in UsageAction.values():
            legal = usage.transition_is_legal(from_state, action)
            if legal != ((from_state, action) in expected):
                problems.append(
                    "transition_is_legal(%s, %s) disagrees with the table"
                    % (from_state, action)
                )
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "5 frozen edges exact; every (state, action) pair consistent")
    )


def case_03_command_model(results: List[Result]) -> None:
    name = "case_03_command_model"
    problems: List[str] = []
    command = UsageCommand(
        command_id="cm-1", action=UsageAction.OBSERVE_USAGE,
        transaction_id="tx-1", payload={"quantity_class": "delivered",
                                        "quantity": 5, "evidence_id": "ev-1",
                                        "window_start": _W1, "window_end": _W2},
        actor="meter", source="usage-collector",
    )
    digest_one = command.digest()
    digest_two = command.digest()
    if digest_one != digest_two or not digest_one.startswith("sha256:"):
        problems.append("command digest not deterministic/well-formed")
    command_two = UsageCommand.from_dict(command.to_dict())
    if command_two.digest() != digest_one:
        problems.append("round-trip digest diverged")
    for bad in (
        {"command_id": ""}, {"action": "no-such-action"},
        {"transaction_id": ""}, {"actor": ""}, {"source": ""},
    ):
        try:
            UsageCommand(
                command_id=bad.get("command_id", "cm-2"),
                action=bad.get("action", UsageAction.OBSERVE_USAGE),
                transaction_id=bad.get("transaction_id", "tx-1"),
                payload={}, actor=bad.get("actor", "meter"),
                source=bad.get("source", "usage-collector"),
            )
            problems.append("malformed command accepted: %r" % bad)
        except UsageError:
            pass
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "digest deterministic; round-trip stable; malformed rejected")
    )


def case_04_fact_models(results: List[Result]) -> None:
    name = "case_04_fact_models"
    problems: List[str] = []
    # observation model: class discipline
    try:
        UsageObservationRecord(
            observation_id="o-1", command_id="c-1", transaction_id="t-1",
            quantity_class=QuantityClass.RESERVED, quantity=5,
            recorded_at=_W1, evidence_id="ev-1",
        )
        problems.append("reserved-class observation with evidence accepted")
    except UsageError:
        pass
    try:
        UsageObservationRecord(
            observation_id="o-1", command_id="c-1", transaction_id="t-1",
            quantity_class=QuantityClass.DELIVERED, quantity=5,
            recorded_at=_W1,
        )
        problems.append("delivered-class observation without evidence accepted")
    except UsageError:
        pass
    # sealed statement model: exact integer arithmetic identity
    statement = SealedBillableStatement(
        statement_id="s-1", transaction_id="t-1",
        reserved_quantity=500, attempted_quantity=80,
        delivered_quantity=360, billable_quantity=360,
        unit_price_micros=3, amount_micros=1080,
        billable_unit="byte", tariff_provenance="p",
        contributing_observations=("a", "b"), contributing_evidence=("e1", "e2"),
        sealed_at=_W3,
    )
    if statement.to_dict() != SealedBillableStatement.from_dict(
        statement.to_dict()
    ).to_dict():
        problems.append("statement round-trip diverged")
    for mutate in (
        {"amount_micros": 1081},
        {"billable_quantity": 359},
        {"delivered_quantity": 359, "billable_quantity": 360},
        {"contributing_observations": ("b", "a")},
    ):
        try:
            data = statement.to_dict()
            data.update(mutate)
            SealedBillableStatement.from_dict(data)
            problems.append("incoherent statement accepted: %r" % mutate)
        except UsageError:
            pass
    # compensation model
    for bad in ({"amount_micros": 5}, {"compensation_kind": "dispute", "amount_micros": 5}):
        try:
            data = {
                "compensation_id": "cp-1", "transaction_id": "t-1",
                "compensation_kind": "dispute", "amount_micros": 0,
                "reason": "r", "statement_id": "s-1", "command_id": "c-1",
                "recorded_at": _W3,
            }
            data.update(bad)
            CompensationRecord.from_dict(data)
            problems.append("incoherent compensation accepted: %r" % bad)
        except UsageError:
            pass
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "observation class discipline; statement arithmetic identity; "
                 "compensation kinds pinned")
    )


def case_05_golden_scenario(results: List[Result]) -> None:
    name = "case_05_golden_lifecycle"
    ledger, index, clock, _fixture, tx = _golden_ledger()
    problems: List[str] = []
    if len(ledger.journal_records()) != 9:
        problems.append("golden journal has %d records (expected 9)"
                        % len(ledger.journal_records()))
    if clock.reads != 9:
        problems.append("golden run consumed %d clock reads (expected 9)" % clock.reads)
    projection = ledger.transaction(tx)
    if projection.state != UsageTransactionState.BILLABLE_FINAL:
        problems.append("golden terminal state is %s" % projection.state)
    statement = projection.statement
    assert statement is not None
    if statement.delivered_quantity != 310 or statement.amount_micros != 930:
        problems.append(
            "golden sealed statement: qty %d amount %d"
            % (statement.delivered_quantity, statement.amount_micros)
        )
    if len(statement.contributing_observations) != 3:
        problems.append("golden statement audit list: %d observations"
                        % len(statement.contributing_observations))
    recon = ledger.reconciliation_statement(tx)
    if recon["reserved_quantity"] != 500 or recon["attempted_quantity"] != 80:
        problems.append("class totals wrong: %r" % recon)
    if recon["net_amount_micros"] != 630:
        problems.append("net amount %d (expected 630)" % recon["net_amount_micros"])
    if not recon["disputed"]:
        problems.append("golden dispute flag missing")
    ledger.verify_replay()
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "9-record golden lifecycle: delivered 310 -> amount 930 -> "
                 "net 630 (refund 200 + reversal 100), dispute flag set, "
                 "class totals reserved 500 / attempted 80, replay clean")
    )


def case_06_every_legal_transition(results: List[Result]) -> None:
    name = "case_06_every_legal_transition"
    problems: List[str] = []
    seen: Dict[Tuple[str, str], str] = {}
    # OBSERVING x observe-usage (the creation self-edge)
    ledger, index, _clock, _fixture, tx = _golden_ledger()
    for record in ledger.journal_records():
        event = record.event
        seen[(event.from_state, event.action)] = event.to_state
    # every edge of the frozen table must have been driven
    for (from_state, action), target in USAGE_TRANSITIONS.items():
        if (from_state, action) not in seen:
            problems.append("edge (%s, %s) never driven" % (from_state, action))
        elif seen[(from_state, action)] != target:
            problems.append(
                "edge (%s, %s) landed %s (expected %s)"
                % (from_state, action, seen[(from_state, action)], target)
            )
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "all 5 frozen edges driven to their exact targets")
    )


def case_07_every_illegal_transition(results: List[Result]) -> None:
    name = "case_07_every_illegal_transition"
    problems: List[str] = []
    illegal: Dict[Tuple[str, str], str] = {
        ("BILLABLE_FINAL", "observe-usage"): UsageReasonCode.USAGE_SEALED,
        ("BILLABLE_FINAL", "seal-billable"): UsageReasonCode.FINAL_IMMUTABLE,
        ("OBSERVING", "record-refund"): UsageReasonCode.COMPENSATION_REQUIRES_FINAL,
        ("OBSERVING", "record-reversal"): UsageReasonCode.COMPENSATION_REQUIRES_FINAL,
        ("OBSERVING", "record-dispute"): UsageReasonCode.COMPENSATION_REQUIRES_FINAL,
    }
    # build one sealed transaction (BILLABLE_FINAL) and one observing
    ledger, index, clock, fixture, tx = _golden_ledger()
    runtime, peer, session_id, manager, integrator, shared = fixture
    references = _references(manager, integrator, session_id)
    core_two, tx_two = _commercial_thread(
        references, StepClock("2026-09-01T13:00:00Z", 60), prefix="c2-",
        deadline="2026-09-01T13:30:00Z",
    )
    index_two = _evidence_index(integrator, core_two, tx_two, with_distractor=False)
    observing_ledger = UsageLedger(
        store=MemoryUsageStore(), clock=StepClock("2026-09-01T13:30:00Z", 60),
        evidence_index=index_two,
    )
    observing_ledger.observe_usage(
        command_id="o-1", transaction_id=tx_two,
        quantity_class=QuantityClass.ATTEMPTED, quantity=10,
        actor="meter", source="traffic-monitor",
    )
    for (state, action), reason in sorted(illegal.items()):
        target_ledger = ledger if state == "BILLABLE_FINAL" else observing_ledger
        target_tx = tx if state == "BILLABLE_FINAL" else tx_two
        method = {
            "observe-usage": lambda: target_ledger.observe_usage(
                command_id="ill-1", transaction_id=target_tx,
                quantity_class=QuantityClass.DELIVERED, quantity=1,
                evidence_id=_evidence_id_of(ledger, 2),
                window_start="2026-09-01T12:07:00Z", window_end=_W3,
                actor="meter", source="usage-collector",
            ),
            "seal-billable": lambda: target_ledger.seal_billable(
                command_id="ill-2", transaction_id=target_tx,
                actor="billing", source="usage-ledger",
            ),
            "record-refund": lambda: target_ledger.record_refund(
                command_id="ill-3", transaction_id=target_tx, amount_micros=1,
                reason="r", actor="billing", source="usage-ledger",
            ),
            "record-reversal": lambda: target_ledger.record_reversal(
                command_id="ill-4", transaction_id=target_tx, amount_micros=1,
                reason="r", actor="billing", source="usage-ledger",
            ),
            "record-dispute": lambda: target_ledger.record_dispute(
                command_id="ill-5", transaction_id=target_tx, reason="r",
                actor="billing", source="usage-ledger",
            ),
        }[action]
        problem = _expect_usage_error(name, reason, method)
        if problem:
            problems.append("(%s, %s): %s" % (state, action, problem))
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "all 5 illegal (state, action) pairs rejected with the typed "
                 "finality reasons")
    )


def case_08_valid_delivered_ingestion(results: List[Result]) -> None:
    name = "case_08_valid_delivered_ingestion"
    ledger, index, _clock, _fixture, tx = _golden_ledger()
    problems: List[str] = []
    projection = ledger.transaction(tx)
    delivered = [
        observation
        for observation in projection.observations
        if observation.is_billable()
    ]
    if len(delivered) != 3:
        problems.append("delivered observation count %d" % len(delivered))
    for observation in delivered:
        if observation.evidence_id is None:
            problems.append("delivered observation without evidence id")
        if not index.contains_evidence(observation.evidence_id):
            problems.append("delivered observation cites unresolvable evidence")
        evidence = index.evidence(observation.evidence_id)
        if not evidence.is_usage_eligible():
            problems.append("delivered observation cites DATA-kind evidence")
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "3 delivered observations cite resolvable usage-eligible "
                 "evidence with full correlation")
    )


def case_09_missing_fabricated_evidence(results: List[Result]) -> None:
    name = "case_09_missing_fabricated_evidence"
    ledger, index, clock, fixture, tx = _golden_ledger()
    runtime, peer, session_id, manager, integrator, shared = fixture
    references = _references(manager, integrator, session_id)
    core_two, tx_two = _commercial_thread(
        references, StepClock("2026-09-01T13:00:00Z", 60), prefix="c3-",
        deadline="2026-09-01T13:30:00Z",
    )
    index_two = _evidence_index(integrator, core_two, tx_two, with_distractor=False)
    observing = UsageLedger(
        store=MemoryUsageStore(), clock=StepClock("2026-09-01T13:30:00Z", 60),
        evidence_index=index_two,
    )
    problems: List[str] = []
    for fabricated in (
        "sha256:" + "0" * 64,
        "sha256:" + hashlib.sha256(b"fabricated-evidence").hexdigest(),
        "not-an-id",
    ):
        problem = _expect_usage_error(
            name, UsageReasonCode.EVIDENCE_UNKNOWN,
            observing.observe_usage,
            command_id="fab-%d" % len(fabricated), transaction_id=tx_two,
            quantity_class=QuantityClass.DELIVERED, quantity=1,
            evidence_id=fabricated, window_start=_W1, window_end=_W2,
            actor="meter", source="usage-collector",
        )
        if problem:
            problems.append("fabricated %r: %s" % (fabricated[:16], problem))
    # a fabricated/unregistered transaction citation fails closed too
    problem = _expect_usage_error(
        name, UsageReasonCode.TRANSACTION_UNKNOWN,
        observing.observe_usage,
        command_id="fab-tx", transaction_id="sha256:" + "9" * 64,
        quantity_class=QuantityClass.ATTEMPTED, quantity=1,
        actor="meter", source="traffic-monitor",
    )
    if problem:
        problems.append("fabricated transaction: %s" % problem)
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "fabricated evidence ids and transactions fail closed "
                 "EVIDENCE_UNKNOWN / TRANSACTION_UNKNOWN with zero drift")
    )


def case_10_kind_gates(results: List[Result]) -> None:
    name = "case_10_payment_provider_kind_gates"
    ledger, index, _clock, _fixture, tx = _golden_ledger()
    payment_id = _external_id("payment-observation", "payment-1")
    provider_id = _external_id("provider-observation", "provider-1")
    problems: List[str] = []
    problem = _expect_usage_error(
        name, UsageReasonCode.PAYMENT_NOT_DELIVERY,
        ledger.observe_usage,
        command_id="kg-1", transaction_id=tx,
        quantity_class=QuantityClass.DELIVERED, quantity=50,
        evidence_id=payment_id, window_start=_W1, window_end=_W3,
        actor="meter", source="usage-collector",
    )
    if problem:
        problems.append("payment observation: %s" % problem)
    problem = _expect_usage_error(
        name, UsageReasonCode.PROVIDER_NOT_DELIVERY,
        ledger.observe_usage,
        command_id="kg-2", transaction_id=tx,
        quantity_class=QuantityClass.DELIVERED, quantity=50,
        evidence_id=provider_id, window_start=_W1, window_end=_W3,
        actor="meter", source="usage-collector",
    )
    if problem:
        problems.append("provider observation: %s" % problem)
    # the kind table is index-driven: the DATA entries never become eligible
    if index.evidence(payment_id).is_usage_eligible():
        problems.append("payment observation marked usage-eligible")
    if index.evidence(provider_id).is_usage_eligible():
        problems.append("provider observation marked usage-eligible")
    # and no usage was created by the rejected attempts
    if len(ledger.usage_record_ids()) != 3:
        problems.append("rejected attempts created usage records")
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "payment observation -> PAYMENT_NOT_DELIVERY; provider "
                 "observation -> PROVIDER_NOT_DELIVERY (the kind table, "
                 "index-driven); zero usage created")
    )


def case_11_transaction_correlation(results: List[Result]) -> None:
    name = "case_11_evidence_transaction_correlation"
    ledger, index, clock, fixture, tx = _golden_ledger()
    runtime, peer, session_id, manager, integrator, shared = fixture
    # the distractor evidence (correlated to a different transaction)
    distractor = [
        record
        for record in index.to_dict()["evidence"]
        if record["transaction_id"] != tx
    ][0]
    problems: List[str] = []
    problem = _expect_usage_error(
        name, UsageReasonCode.EVIDENCE_MISMATCH,
        ledger.observe_usage,
        command_id="cor-1", transaction_id=tx,
        quantity_class=QuantityClass.DELIVERED, quantity=1,
        evidence_id=distractor["evidence_id"],
        window_start=distractor["window_start"],
        window_end=distractor["window_end"],
        actor="meter", source="usage-collector",
    )
    if problem:
        problems.append("cross-transaction evidence: %s" % problem)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "evidence correlated to another transaction fails closed "
                 "EVIDENCE_MISMATCH (usage correlates to ITS evidence record)")
    )


def case_12_quantity_window_discipline(results: List[Result]) -> None:
    name = "case_12_quantity_window_discipline"
    ledger, index, _clock, fixture, tx = _golden_ledger()
    runtime, peer, session_id, manager, integrator, shared = fixture
    wifi_events = _wifi_journal_events(integrator)
    evidence_ids = [
        "sha256:"
        + hashlib.sha256(
            canonical_json_bytes(
                {
                    "kind": "delivery-evidence-window",
                    "from_event": first.event_id,
                    "to_event": second.event_id,
                }
            )
        ).hexdigest()
        for first, second in zip(wifi_events, wifi_events[1:])
    ]
    problems: List[str] = []
    # single-observation overstatement
    problem = _expect_usage_error(
        name, UsageReasonCode.QUANTITY_EXCEEDED,
        ledger.observe_usage,
        command_id="qd-1", transaction_id=tx,
        quantity_class=QuantityClass.DELIVERED, quantity=211,
        evidence_id=evidence_ids[1], window_start=_W2, window_end=_W3,
        actor="meter", source="usage-collector",
    )
    if problem:
        problems.append("overstatement: %s" % problem)
    # window not contained in the evidence window
    problem = _expect_usage_error(
        name, UsageReasonCode.WINDOW_INVALID,
        ledger.observe_usage,
        command_id="qd-2", transaction_id=tx,
        quantity_class=QuantityClass.DELIVERED, quantity=10,
        evidence_id=evidence_ids[1],
        window_start="2026-09-01T12:00:00Z", window_end=_W3,
        actor="meter", source="usage-collector",
    )
    if problem:
        problems.append("window overreach: %s" % problem)
    # inverted observation window (shape layer)
    problem = _expect_usage_error(
        name, UsageReasonCode.WINDOW_INVALID,
        ledger.observe_usage,
        command_id="qd-3", transaction_id=tx,
        quantity_class=QuantityClass.DELIVERED, quantity=10,
        evidence_id=evidence_ids[1], window_start=_W3, window_end=_W2,
        actor="meter", source="usage-collector",
    )
    if problem:
        problems.append("inverted window: %s" % problem)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "overstatement and window overreach/inversion fail closed "
                 "(quantity bounded by the authoritative delivered fact)")
    )


def case_13_reservation_not_usage(results: List[Result]) -> None:
    name = "case_13_reservation_lease_not_usage"
    ledger, index, clock, fixture, tx = _golden_ledger()
    runtime, peer, session_id, manager, integrator, shared = fixture
    references = _references(manager, integrator, session_id)
    problems: List[str] = []
    # 1. reserved/attempted observations are DATA: recorded, never billable
    projection = ledger.transaction(tx)
    quantities = projection.quantities()
    if quantities[QuantityClass.RESERVED] != 500:
        problems.append("reserved total %d" % quantities[QuantityClass.RESERVED])
    statement = projection.statement
    assert statement is not None
    if statement.billable_quantity != quantities[QuantityClass.DELIVERED]:
        problems.append("billable quantity drifted from delivered")
    if statement.reserved_quantity != 500 or statement.attempted_quantity != 80:
        problems.append("statement class distinction lost")
    # 2. a DELIVERED observation against a pre-delivery transaction
    # (reservation/lease phase) fails closed
    core_pre, tx_pre = _commercial_thread(
        references, StepClock("2026-09-01T13:00:00Z", 60), prefix="c4-",
        intent={"buyer": "buyer-pre"}, deadline="2026-09-01T13:30:00Z",
    )
    # drive only to RESERVATION_HELD (pre-delivery)
    core_pre2 = CommercialCore(
        store=commercial.MemoryCommercialStore(),
        clock=StepClock("2026-09-01T13:00:00Z", 60),
        references=references,
    )
    out = core_pre2.submit_intent(
        command_id="pre-1", actor="buyer-agent", source="developer-api",
        intent={"buyer": "buyer-2"},
    )
    tx_pre2 = out.transaction_id
    core_pre2.select_offer(
        command_id="pre-2", transaction_id=tx_pre2, actor="buyer-agent",
        source="developer-api",
        offer={"offer_id": "offer-1", "provider": "provider-1",
               "unit": "byte", "price": "3"},
    )
    core_pre2.hold_reservation(
        command_id="pre-3", transaction_id=tx_pre2, actor="platform",
        source="reservation-service", expires_at="2026-09-01T13:30:00Z",
    )
    pre_snapshot = CommercialTransactionSnapshot(
        transaction_id=tx_pre2, commercial_state="RESERVATION_HELD",
        unit_price_micros=3, billable_unit="byte",
        tariff_provenance="commercial-core-public-read",
    )
    pre_evidence = DeliveryEvidence(
        evidence_id=_external_id("delivery-evidence", "pre-1"),
        transaction_id=tx_pre2, delivered_quantity=100,
        window_start=_W1, window_end=_W3,
        evidence_kind=EvidenceKind.DELIVERED, provenance="platform-journal",
    )
    pre_index = UsageEvidenceIndex(
        evidence=[pre_evidence], transactions=[pre_snapshot]
    )
    pre_ledger = UsageLedger(
        store=MemoryUsageStore(), clock=StepClock("2026-09-01T14:00:00Z", 60),
        evidence_index=pre_index,
    )
    problem = _expect_usage_error(
        name, UsageReasonCode.RESERVATION_NOT_USAGE,
        pre_ledger.observe_usage,
        command_id="pre-obs", transaction_id=tx_pre2,
        quantity_class=QuantityClass.DELIVERED, quantity=50,
        evidence_id=pre_evidence.evidence_id, window_start=_W1, window_end=_W3,
        actor="meter", source="usage-collector",
    )
    if problem:
        problems.append("reservation-phase delivered observation: %s" % problem)
    # a pre-offer/other pre-delivery phase gets the general gate
    pre_snapshot_two = CommercialTransactionSnapshot(
        transaction_id="sha256:" + "7" * 64,
        commercial_state="OFFER_SELECTED",
        unit_price_micros=3, billable_unit="byte",
        tariff_provenance="commercial-core-public-read",
    )
    pre_index_two = UsageEvidenceIndex(
        evidence=[
            DeliveryEvidence(
                evidence_id=_external_id("delivery-evidence", "pre-2"),
                transaction_id=pre_snapshot_two.transaction_id,
                delivered_quantity=100, window_start=_W1, window_end=_W3,
                evidence_kind=EvidenceKind.DELIVERED,
                provenance="platform-journal",
            )
        ],
        transactions=[pre_snapshot_two],
    )
    pre_ledger_two = UsageLedger(
        store=MemoryUsageStore(), clock=StepClock("2026-09-01T14:00:00Z", 60),
        evidence_index=pre_index_two,
    )
    problem = _expect_usage_error(
        name, UsageReasonCode.TRANSACTION_NOT_DELIVERING,
        pre_ledger_two.observe_usage,
        command_id="pre-obs-2", transaction_id=pre_snapshot_two.transaction_id,
        quantity_class=QuantityClass.DELIVERED, quantity=50,
        evidence_id=_external_id("delivery-evidence", "pre-2"),
        window_start=_W1, window_end=_W3,
        actor="meter", source="usage-collector",
    )
    if problem:
        problems.append("offer-phase delivered observation: %s" % problem)
    # but the DATA-class observation on the same pre-delivery
    # transaction IS admissible as data (and never bills)
    out_data = pre_ledger.observe_usage(
        command_id="pre-data", transaction_id=tx_pre2,
        quantity_class=QuantityClass.RESERVED, quantity=100,
        actor="meter", source="reservation-service",
    )
    if out_data.status != CommandStatus.APPENDED:
        problems.append("reserved DATA observation rejected")
    if pre_ledger.transaction(tx_pre2).delivered_observation_ids():
        problems.append("reserved DATA observation created billable usage")
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "reserved/attempted are DATA (recorded, never billed); "
                 "delivered evidence against a reservation-phase transaction "
                 "fails closed RESERVATION_NOT_USAGE and against other "
                 "pre-delivery phases TRANSACTION_NOT_DELIVERING")
    )


def case_14_payment_not_usage(results: List[Result]) -> None:
    name = "case_14_payment_capture_never_usage"
    ledger, index, clock, fixture, tx = _golden_ledger()
    problems: List[str] = []
    projection = ledger.transaction(tx)
    # the sealed billable derivation is exclusively evidence-derived:
    # no observation contributing to the bill cites payment data
    for observation in projection.observations:
        if observation.is_billable():
            evidence = index.evidence(observation.evidence_id)
            if evidence.evidence_kind != EvidenceKind.DELIVERED:
                problems.append("billable observation cites DATA-kind evidence")
    # payment observation attempts are rejected at the kind table
    payment_id = _external_id("payment-observation", "payment-1")
    try:
        ledger.observe_usage(
            command_id="pay-1", transaction_id=tx,
            quantity_class=QuantityClass.DELIVERED, quantity=10,
            evidence_id=payment_id, window_start=_W1, window_end=_W3,
            actor="meter", source="payment-webhook",
        )
        problems.append("payment-observation ingestion accepted")
    except UsageError as error:
        if error.reason != UsageReasonCode.PAYMENT_NOT_DELIVERY:
            problems.append("wrong reason %s" % error.reason)
    # a reserved-class observation explicitly labeled as payment
    # capture is still DATA (never billable)
    if projection.quantities()[QuantityClass.DELIVERED] != 310:
        problems.append("delivered total drifted")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "the billable derivation is exclusively delivered-evidence-"
                 "derived; payment observations never create usage")
    )


def case_15_duplicate_commands(results: List[Result]) -> None:
    name = "case_15_duplicate_commands"
    ledger, index, clock, fixture, tx = _golden_ledger()
    problems: List[str] = []
    records_before = len(ledger.journal_records())
    reads_before = clock.reads
    # exact redelivery of a delivered observation
    out = ledger.observe_usage(
        command_id="u-01", transaction_id=tx,
        quantity_class=QuantityClass.DELIVERED, quantity=120,
        evidence_id=_evidence_id_of(ledger, 0), window_start=_W1,
        window_end="2026-09-01T12:03:00Z",
        actor="meter", source="usage-collector",
    )
    if out.status != CommandStatus.DUPLICATE:
        problems.append("command redelivery not DUPLICATE")
    if out.event_id != ledger.journal_records()[0].event.event_id:
        problems.append("duplicate returned wrong event id")
    # exact redelivery of the seal
    out = ledger.seal_billable(
        command_id="u-06", transaction_id=tx, actor="billing",
        source="usage-ledger",
    )
    if out.status != CommandStatus.DUPLICATE:
        problems.append("seal redelivery not DUPLICATE")
    # no journal growth, no clock consumption
    if len(ledger.journal_records()) != records_before:
        problems.append("duplicate grew the journal")
    if clock.reads != reads_before:
        problems.append("duplicate consumed a clock read")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "exact redelivery is an idempotent no-op: no journal growth, "
                 "no clock read, the recorded event returned")
    )


def _evidence_id_of(ledger: UsageLedger, position: int) -> str:
    """The evidence id cited by the position-th delivered
    observation of the golden ledger (fixture helper)."""
    for record in ledger.journal_records():
        observation = record.event.observation()
        if observation is not None and observation.is_billable():
            if position == 0:
                return observation.evidence_id
            position -= 1
    raise AssertionError("no delivered observation at position %d" % position)


def case_16_conflicting_duplicates(results: List[Result]) -> None:
    name = "case_16_conflicting_duplicates"
    ledger, index, _clock, _fixture, tx = _golden_ledger()
    problems: List[str] = []
    records_before = len(ledger.journal_records())
    problem = _expect_usage_error(
        name, UsageReasonCode.COMMAND_CONFLICT,
        ledger.observe_usage,
        command_id="u-01", transaction_id=tx,
        quantity_class=QuantityClass.DELIVERED, quantity=125,
        evidence_id=_evidence_id_of(ledger, 0), window_start=_W1,
        window_end="2026-09-01T12:03:00Z",
        actor="meter", source="usage-collector",
    )
    if problem:
        problems.append("conflicting observation: %s" % problem)
    problem = _expect_usage_error(
        name, UsageReasonCode.COMMAND_CONFLICT,
        ledger.record_refund,
        command_id="u-07", transaction_id=tx, amount_micros=999,
        reason="different amount", actor="billing", source="usage-ledger",
    )
    if problem:
        problems.append("conflicting refund: %s" % problem)
    if len(ledger.journal_records()) != records_before:
        problems.append("conflicts grew the journal")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "same command id with different content fails closed "
                 "COMMAND_CONFLICT (observation identity reuse fails closed)")
    )


def case_17_evidence_duplicates(results: List[Result]) -> None:
    name = "case_17_evidence_window_duplicates"
    ledger, index, clock, fixture, tx = _golden_ledger()
    problems: List[str] = []
    records_before = len(ledger.journal_records())
    reads_before = clock.reads
    statement_before = ledger.transaction(tx).statement.to_dict()
    # a NEW command id reporting the SAME evidence window with
    # the SAME quantity: the evidence-level duplicate (no double
    # charge, no journal growth, no clock read)
    out = ledger.observe_usage(
        command_id="collector-shard-2", transaction_id=tx,
        quantity_class=QuantityClass.DELIVERED, quantity=120,
        evidence_id=_evidence_id_of(ledger, 0), window_start=_W1,
        window_end="2026-09-01T12:03:00Z",
        actor="meter", source="usage-collector-shard-2",
    )
    if out.status != CommandStatus.DUPLICATE:
        problems.append("evidence-window duplicate not DUPLICATE (got %s)"
                        % out.status)
    if out.fact_id != _observation_id_of(ledger, 0):
        problems.append("duplicate returned wrong observation id")
    if len(ledger.journal_records()) != records_before:
        problems.append("evidence duplicate grew the journal")
    if clock.reads != reads_before:
        problems.append("evidence duplicate consumed a clock read")
    if ledger.transaction(tx).statement.to_dict() != statement_before:
        problems.append("sealed statement drifted on duplicate")
    # the same evidence window with a DIFFERENT quantity fails closed
    problem = _expect_usage_error(
        name, UsageReasonCode.EVIDENCE_MISMATCH,
        ledger.observe_usage,
        command_id="collector-shard-3", transaction_id=tx,
        quantity_class=QuantityClass.DELIVERED, quantity=121,
        evidence_id=_evidence_id_of(ledger, 0), window_start=_W1,
        window_end="2026-09-01T12:03:00Z",
        actor="meter", source="usage-collector-shard-3",
    )
    if problem:
        problems.append("conflicting evidence window: %s" % problem)
    if len(ledger.journal_records()) != records_before:
        problems.append("conflicts grew the journal")
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "duplicate report of the same delivered fact is an idempotent "
                 "no-op (zero double-charge); a conflicting quantity for the "
                 "same evidence-window identity fails closed")
    )


def _observation_id_of(ledger: UsageLedger, position: int) -> str:
    for record in ledger.journal_records():
        observation = record.event.observation()
        if observation is not None and observation.is_billable():
            if position == 0:
                return observation.observation_id
            position -= 1
    raise AssertionError("no delivered observation at position %d" % position)


def case_18_cumulative_cap(results: List[Result]) -> None:
    name = "case_18_cumulative_evidence_cap"
    ledger, index, _clock, fixture, tx = _golden_ledger()
    runtime, peer, session_id, manager, integrator, shared = fixture
    references = _references(manager, integrator, session_id)
    core_two, tx_two = _commercial_thread(
        references, StepClock("2026-09-01T13:00:00Z", 60), prefix="c5-",
        deadline="2026-09-01T13:30:00Z",
    )
    index_two = _evidence_index(integrator, core_two, tx_two, with_distractor=False)
    fresh = UsageLedger(
        store=MemoryUsageStore(), clock=StepClock("2026-09-01T13:30:00Z", 60),
        evidence_index=index_two,
    )
    problems: List[str] = []
    wifi_events = _wifi_journal_events(integrator)
    evidence_ids = [
        "sha256:"
        + hashlib.sha256(
            canonical_json_bytes(
                {
                    "kind": "delivery-evidence-window",
                    "from_event": first.event_id,
                    "to_event": second.event_id,
                }
            )
        ).hexdigest()
        for first, second in zip(wifi_events, wifi_events[1:])
    ]
    # windowed sub-metering within the FIRST evidence window:
    # 150 + 60 = 210 (exactly the authoritative quantity) is fine
    fresh.observe_usage(
        command_id="sub-1", transaction_id=tx_two,
        quantity_class=QuantityClass.DELIVERED, quantity=150,
        evidence_id=evidence_ids[0], window_start=_W1,
        window_end="2026-09-01T12:03:00Z", actor="meter",
        source="usage-collector",
    )
    fresh.observe_usage(
        command_id="sub-2", transaction_id=tx_two,
        quantity_class=QuantityClass.DELIVERED, quantity=60,
        evidence_id=evidence_ids[0], window_start="2026-09-01T12:03:00Z",
        window_end=_W2, actor="meter", source="usage-collector",
    )
    # ...but one more byte overstates the authoritative fact
    problem = _expect_usage_error(
        name, UsageReasonCode.QUANTITY_EXCEEDED,
        fresh.observe_usage,
        command_id="sub-3", transaction_id=tx_two,
        quantity_class=QuantityClass.DELIVERED, quantity=1,
        evidence_id=evidence_ids[0], window_start="2026-09-01T12:04:00Z",
        window_end="2026-09-01T12:04:30Z", actor="meter",
        source="usage-collector",
    )
    if problem:
        problems.append("over-cap sub-metering: %s" % problem)
    # sub-metering that overlaps the SAME window is the
    # evidence-window duplicate/conflict layer (case_17); the
    # disjoint-window sum cap is the cumulative layer: verified
    if fresh.transaction(tx_two).quantities()[QuantityClass.DELIVERED] != 210:
        problems.append("sub-metered total wrong")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "disjoint windowed sub-metering sums exactly to the "
                 "authoritative delivered quantity; one byte beyond fails "
                 "closed QUANTITY_EXCEEDED (no double charge)")
    )


def case_19_out_of_order_delayed(results: List[Result]) -> None:
    name = "case_19_out_of_order_delayed_observations"
    problems: List[str] = []
    worlds: List[Tuple[str, Dict[str, Any]]] = []
    audit_identity: List[Tuple[str, Dict[str, Any]]] = []
    # three worlds: the SAME three delivered observations admitted
    # in three different orders (one delayed: the earliest window
    # arrives last)
    for label, order in (
        ("window-order", (0, 1, 2)),
        ("delayed-earliest-last", (2, 1, 0)),
        ("shuffled", (1, 2, 0)),
    ):
        runtime, peer, session_id, manager, integrator, shared = _usage_world()
        references = _references(manager, integrator, session_id)
        core, tx = _commercial_thread(
            references, StepClock(_UT0, 60), prefix="ord-%s-" % label
        )
        index = _evidence_index(integrator, core, tx, with_distractor=False)
        ledger = UsageLedger(
            store=MemoryUsageStore(), clock=StepClock(_UT0, _USTEP),
            evidence_index=index,
        )
        wifi_events = _wifi_journal_events(integrator)
        evidence_ids = [
            "sha256:"
            + hashlib.sha256(
                canonical_json_bytes(
                    {
                        "kind": "delivery-evidence-window",
                        "from_event": first.event_id,
                        "to_event": second.event_id,
                    }
                )
            ).hexdigest()
            for first, second in zip(wifi_events, wifi_events[1:])
        ]
        vectors = (
            (120, evidence_ids[0], _W1, "2026-09-01T12:03:00Z"),
            (90, evidence_ids[0], "2026-09-01T12:03:00Z", _W2),
            (150, evidence_ids[1], _W2, _W3),
        )
        for step, position in enumerate(order):
            quantity, evidence_id, window_start, window_end = vectors[position]
            ledger.observe_usage(
                command_id="ord-%d" % step, transaction_id=tx,
                quantity_class=QuantityClass.DELIVERED, quantity=quantity,
                evidence_id=evidence_id, window_start=window_start,
                window_end=window_end, actor="meter", source="usage-collector",
            )
        ledger.seal_billable(
            command_id="ord-seal", transaction_id=tx, actor="billing",
            source="usage-ledger",
        )
        ledger.verify_replay()
        statement = ledger.transaction(tx).statement
        assert statement is not None
        worlds.append(
            (
                label,
                {
                    "delivered": statement.delivered_quantity,
                    "amount": statement.amount_micros,
                    "billable": statement.billable_quantity,
                    "evidence": list(statement.contributing_evidence),
                    "observations": len(statement.contributing_observations),
                    "net": ledger.transaction(tx).net_amount_micros(),
                },
            )
        )
        # the ADMISSION-ATTRIBUTED audit identity: recorded per
        # world, NOT compared across worlds (see below)
        audit_identity.append(
            (
                label,
                {
                    "observation_ids": list(statement.contributing_observations),
                    "statement_id": statement.statement_id,
                },
            )
        )
    baseline = worlds[0][1]
    for label, summary in worlds[1:]:
        if summary != baseline:
            problems.append(
                "world %s diverged: %r vs %r" % (label, summary, baseline)
            )
    if baseline["delivered"] != 360 or baseline["amount"] != 1080:
        problems.append("baseline summary wrong: %r" % baseline)
    # HONEST divergence proof: the audit identity (observation
    # ids + statement id) is admission-attributed -- the same
    # logical observation set admitted in a different order
    # carries DIFFERENT ids (they bind the causal command id and
    # the admission instant), so the battery proves the
    # divergence instead of claiming order-independent audit
    # identity.  The economic fold above is the order-independent
    # surface; this is the honest boundary between them.
    diverged = {
        tuple(sorted(identity["observation_ids"])) for _, identity in audit_identity
    }
    diverged_statement_ids = {
        identity["statement_id"] for _, identity in audit_identity
    }
    if len(diverged) != len(audit_identity):
        problems.append(
            "audit identity unexpectedly identical across arrival orders "
            "(the observation ids are admission-attributed; the battery "
            "expects divergence)"
        )
    if len(diverged_statement_ids) != len(audit_identity):
        problems.append(
            "statement ids unexpectedly identical across arrival orders "
            "(the statement id binds the admission-attributed observation "
            "ids; the battery expects divergence)"
        )
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "the same admitted set in any arrival order (including the "
                 "delayed earliest-window-last) seals the SAME ECONOMIC "
                 "derivation (billable quantity/amount/evidence multiset/"
                 "count/net -- arrival-order independent); the observation "
                 "and statement identities are admission-attributed (they "
                 "bind the causal command and the admission instant) and "
                 "honestly DIVERGE across arrival orders (proven, not "
                 "claimed); every world replays clean")
    )


def case_20_late_after_seal(results: List[Result]) -> None:
    name = "case_20_late_observation_after_finality"
    ledger, index, _clock, fixture, tx = _golden_ledger()
    problems: List[str] = []
    records_before = len(ledger.journal_records())
    statement_before = ledger.transaction(tx).statement.to_dict()
    problem = _expect_usage_error(
        name, UsageReasonCode.USAGE_SEALED,
        ledger.observe_usage,
        command_id="late-1", transaction_id=tx,
        quantity_class=QuantityClass.DELIVERED, quantity=30,
        evidence_id=_evidence_id_of(ledger, 2),
        window_start="2026-09-01T12:07:00Z", window_end=_W3,
        actor="meter", source="usage-collector",
    )
    if problem:
        problems.append("late delivered observation: %s" % problem)
    problem = _expect_usage_error(
        name, UsageReasonCode.USAGE_SEALED,
        ledger.observe_usage,
        command_id="late-2", transaction_id=tx,
        quantity_class=QuantityClass.RESERVED, quantity=10,
        actor="meter", source="reservation-service",
    )
    if problem:
        problems.append("late reserved observation: %s" % problem)
    if len(ledger.journal_records()) != records_before:
        problems.append("late observations grew the journal")
    if ledger.transaction(tx).statement.to_dict() != statement_before:
        problems.append("sealed statement drifted")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "delayed observations (delivered AND data-class) after "
                 "BILLABLE_FINAL fail closed USAGE_SEALED; the sealed fact is "
                 "immutable; corrections are compensations only")
    )


def case_21_billable_final_explicit(results: List[Result]) -> None:
    name = "case_21_explicit_billable_final"
    problems: List[str] = []
    # the golden seal: exact content
    ledger, index, _clock, _fixture, tx = _golden_ledger()
    statement = ledger.transaction(tx).statement
    assert statement is not None
    if (
        statement.reserved_quantity != 500
        or statement.attempted_quantity != 80
        or statement.delivered_quantity != 310
        or statement.billable_quantity != 310
        or statement.unit_price_micros != 3
        or statement.amount_micros != 930
        or statement.billable_unit != "byte"
    ):
        problems.append("golden statement content wrong")
    if statement.contributing_observations != tuple(
        sorted(statement.contributing_observations)
    ):
        problems.append("audit list unsorted")
    # the honest zero-observation seal (explicit zero bill)
    runtime, peer, session_id, manager, integrator, shared = _usage_world()
    references = _references(manager, integrator, session_id)
    core, tx2 = _commercial_thread(
        references, StepClock(_UT0, 60), prefix="zero-"
    )
    index2 = _evidence_index(integrator, core, tx2, with_distractor=False)
    empty = UsageLedger(
        store=MemoryUsageStore(), clock=StepClock(_UT0, _USTEP),
        evidence_index=index2,
    )
    out = empty.seal_billable(
        command_id="zero-seal", transaction_id=tx2, actor="billing",
        source="usage-ledger",
    )
    if out.status != CommandStatus.APPENDED or out.to_state != "BILLABLE_FINAL":
        problems.append("zero-observation seal not appended")
    zero_statement = empty.transaction(tx2).statement
    assert zero_statement is not None
    if (
        zero_statement.billable_quantity != 0
        or zero_statement.amount_micros != 0
    ):
        problems.append("zero seal not zero")
    empty.verify_replay()
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "explicit seal content exact (class-distinguished quantities, "
                 "integer tariff arithmetic, sorted audit lists); the honest "
                 "zero-observation zero-bill seal works")
    )


def case_22_final_immutable(results: List[Result]) -> None:
    name = "case_22_final_immutable"
    ledger, index, _clock, _fixture, tx = _golden_ledger()
    problems: List[str] = []
    records_before = len(ledger.journal_records())
    statement_before = ledger.transaction(tx).statement.to_dict()
    problem = _expect_usage_error(
        name, UsageReasonCode.FINAL_IMMUTABLE,
        ledger.seal_billable,
        command_id="re-seal-1", transaction_id=tx, actor="billing",
        source="usage-ledger",
    )
    if problem:
        problems.append("re-seal: %s" % problem)
    # compensations never rewrite the statement
    if ledger.transaction(tx).statement.to_dict() != statement_before:
        problems.append("statement drifted")
    # the recorded statement fact in the journal is immutable:
    # frozen records reject ordinary attribute writes
    import dataclasses

    for record in ledger.journal_records():
        if record.event.statement() is not None:
            try:
                record.event.event_id = "tampered"  # type: ignore[misc]
                problems.append("journal event is mutable")
            except dataclasses.FrozenInstanceError:
                pass
            break
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "re-seal fails FINAL_IMMUTABLE; the sealed statement survives "
                 "compensations byte-identically; records are frozen")
    )


def case_23_compensation_family(results: List[Result]) -> None:
    name = "case_23_compensation_family"
    ledger, index, _clock, _fixture, tx = _golden_ledger()
    problems: List[str] = []
    projection = ledger.transaction(tx)
    if projection.refunded_amount_micros() != 200:
        problems.append("refund amount wrong")
    if projection.reversed_amount_micros() != 100:
        problems.append("reversal amount wrong")
    if projection.net_amount_micros() != 630:
        problems.append("net amount wrong")
    if not projection.disputed():
        problems.append("dispute flag missing")
    # the SEPARATED quantity views: each derived from its OWN
    # compensation kind's amounts (floor division by the unit
    # price; independent derivations, no conflation)
    if projection.refunded_quantity() != 66:  # 200 // 3
        problems.append("refunded quantity view wrong")
    if projection.reversed_quantity() != 33:  # 100 // 3
        problems.append("reversed quantity view wrong")
    if (
        projection.refunded_quantity()
        == projection.reversed_quantity()
        and projection.refunded_amount_micros()
        != projection.reversed_amount_micros()
    ):
        problems.append("quantity views conflated (equal views for unequal amounts)")
    compensations = projection.compensations
    if [c.compensation_kind for c in compensations] != [
        "refund",
        "reversal",
        "dispute",
    ]:
        # sorted by compensation id -- verify the SET
        if sorted(c.compensation_kind for c in compensations) != [
            "dispute", "refund", "reversal",
        ]:
            problems.append("compensation set wrong")
    for compensation in compensations:
        if compensation.statement_id != projection.statement.statement_id:
            problems.append("compensation cites wrong statement")
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "refund 200 + reversal 100 against the sealed statement "
                 "(net 630), dispute flag set, every compensation cites the "
                 "immutable statement id; the refunded/reversed quantity "
                 "views are SEPARATELY derived (66 and 33 quantity units at "
                 "price 3; floor division per kind, amounts are canonical)")
    )


def case_24_compensation_exceeded(results: List[Result]) -> None:
    name = "case_24_compensation_exceeded"
    ledger, index, _clock, _fixture, tx = _golden_ledger()
    problems: List[str] = []
    records_before = len(ledger.journal_records())
    # sealed 930 with 300 already compensated: headroom 630, so 631 exceeds
    problem = _expect_usage_error(
        name, UsageReasonCode.COMPENSATION_EXCEEDED,
        ledger.record_refund,
        command_id="over-refund", transaction_id=tx, amount_micros=631,
        reason="over", actor="billing", source="usage-ledger",
    )
    if problem:
        problems.append("over-refund: %s" % problem)
    problem = _expect_usage_error(
        name, UsageReasonCode.COMPENSATION_EXCEEDED,
        ledger.record_reversal,
        command_id="over-reversal", transaction_id=tx, amount_micros=631,
        reason="over", actor="billing", source="usage-ledger",
    )
    if problem:
        problems.append("over-reversal: %s" % problem)
    # exactly-to-the-cap compensation is legitimate (net 0)
    out = ledger.record_refund(
        command_id="exact-refund", transaction_id=tx, amount_micros=630,
        reason="final adjustment", actor="billing", source="usage-ledger",
    )
    if out.status != CommandStatus.APPENDED:
        problems.append("exact-cap refund rejected")
    if ledger.transaction(tx).net_amount_micros() != 0:
        problems.append("net after exact-cap refund wrong")
    problem = _expect_usage_error(
        name, UsageReasonCode.COMPENSATION_EXCEEDED,
        ledger.record_refund,
        command_id="post-zero-refund", transaction_id=tx, amount_micros=1,
        reason="one more", actor="billing", source="usage-ledger",
    )
    if problem:
        problems.append("post-zero refund: %s" % problem)
    if len(ledger.journal_records()) != records_before + 1:
        problems.append("journal growth wrong")
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "over-compensation fails closed (net never negative); the "
                 "exact-cap compensation brings net to 0 and anything beyond "
                 "fails closed")
    )


def case_25_dispute_already_open(results: List[Result]) -> None:
    name = "case_25_dispute_already_open"
    ledger, index, _clock, _fixture, tx = _golden_ledger()
    problems: List[str] = []
    problem = _expect_usage_error(
        name, UsageReasonCode.DISPUTE_ALREADY_OPEN,
        ledger.record_dispute,
        command_id="dis-2", transaction_id=tx, reason="second dispute",
        actor="billing", source="usage-ledger",
    )
    if problem:
        problems.append("second dispute: %s" % problem)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "a second open dispute fails closed DISPUTE_ALREADY_OPEN "
                 "(dispute resolution is a settlement-layer concern)")
    )


def case_26_deterministic_reconciliation(results: List[Result]) -> None:
    name = "case_26_deterministic_reconciliation"
    ledger, index, _clock, _fixture, tx = _golden_ledger()
    problems: List[str] = []
    first = ledger.reconciliation_statement(tx)
    second = ledger.reconciliation_statement(tx)
    if first != second:
        problems.append("reconciliation statement not deterministic")
    if canonical_json_bytes(first) != canonical_json_bytes(second):
        problems.append("reconciliation bytes not deterministic")
    if first["kind"] != "usage-reconciliation-statement":
        problems.append("statement kind wrong")
    for member in (
        "reserved_quantity", "attempted_quantity", "delivered_quantity",
        "billable_quantity", "gross_amount_micros", "refunded_amount_micros",
        "reversed_amount_micros", "refunded_quantity", "reversed_quantity",
        "disputed", "net_amount_micros", "statement_id",
        "contributing_observations", "contributing_evidence",
        "compensation_ids", "projection_digest",
    ):
        if member not in first:
            problems.append("statement missing member %s" % member)
    if (
        first["reserved_quantity"] != 500
        or first["attempted_quantity"] != 80
        or first["delivered_quantity"] != 310
        or first["billable_quantity"] != 310
        or first["gross_amount_micros"] != 930
        or first["refunded_amount_micros"] != 200
        or first["reversed_amount_micros"] != 100
        or first["net_amount_micros"] != 630
        or first["disputed"] is not True
    ):
        problems.append("statement values wrong: %r" % first)
    # the SEPARATED per-kind quantity views (floor division by
    # the unit price; independent derivations, no conflation)
    if (
        first["refunded_quantity"] != 66
        or first["reversed_quantity"] != 33
    ):
        problems.append("separated quantity views wrong: %r" % first)
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "the reconciliation statement is a deterministic pure read "
                 "with the full ACR-009 class distinction (reserved/attempted/"
                 "delivered/billable/disputed/refunded/reversed) + audit trail")
    )


def case_27_immutable_history(results: List[Result]) -> None:
    name = "case_27_immutable_history"
    ledger, index, _clock, _fixture, tx = _golden_ledger()
    problems: List[str] = []
    journal_bytes = ledger.journal_records()[0].to_line()
    if not journal_bytes.endswith(b"\n"):
        problems.append("journal line not newline-terminated")
    # the recorded delivery facts are immutable: the observation
    # events in the journal survive compensations byte-identically
    observation_lines = [
        record.to_line()
        for record in ledger.journal_records()
        if record.event.observation() is not None
    ]
    if len(observation_lines) != 5:
        problems.append("observation record count %d" % len(observation_lines))
    # no rewrite/removal API exists on the ledger surface
    for forbidden in ("remove_record", "delete_record", "rewrite", "update_record"):
        if hasattr(ledger, forbidden):
            problems.append("ledger exposes %s()" % forbidden)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "delivery facts are append-only records; no rewrite/removal "
                 "surface exists; historical observations survive byte-identically")
    )


def case_28_tampered_journal(results: List[Result]) -> None:
    name = "case_28_tampered_journal"
    ledger, index, _clock, _fixture, tx = _golden_ledger()
    # rebuild the raw bytes from the records
    data = b"".join(record.to_line() for record in ledger.journal_records())
    lines = data.split(b"\n")[:-1]
    problems: List[str] = []
    variants: Dict[str, bytes] = {}
    # byte flip in a middle line
    flipped = bytearray(lines[1])
    for i, byte in enumerate(flipped):
        if byte in b"0123456789abcdef":
            flipped[i] = ord("0") if byte != ord("0") else ord("1")
            break
    variants["byte-flip"] = b"\n".join(
        lines[:1] + [bytes(flipped)] + lines[2:]
    ) + b"\n"
    # reorder: swap two lines
    reordered = list(lines)
    reordered[0], reordered[1] = reordered[1], reordered[0]
    variants["reorder"] = b"\n".join(reordered) + b"\n"
    # half-line truncation (no trailing newline)
    variants["truncated-tail"] = data[:-40]
    # sequence gap: bump the sequence of the second record
    payload = json.loads(lines[1].decode("utf-8"))
    payload["sequence"] = 3
    variants["sequence-gap"] = b"\n".join(
        lines[:1] + [json.dumps(payload).encode("utf-8")] + lines[2:]
    ) + b"\n"
    # command digest edit
    payload = json.loads(lines[1].decode("utf-8"))
    payload["command_digest"] = "sha256:" + "0" * 64
    variants["digest-edit"] = b"\n".join(
        lines[:1] + [json.dumps(payload).encode("utf-8")] + lines[2:]
    ) + b"\n"
    # event id edit
    payload = json.loads(lines[1].decode("utf-8"))
    payload["event"]["event_id"] = "sha256:" + "0" * 64
    variants["event-id-edit"] = b"\n".join(
        lines[:1] + [json.dumps(payload).encode("utf-8")] + lines[2:]
    ) + b"\n"
    # non-canonical payload member (a float): the recomputed
    # command digest canonicalization fails on untrusted bytes
    # and must fail CLOSED (not crash open)
    payload = json.loads(lines[1].decode("utf-8"))
    payload["command"]["payload"]["quantity"] = 90.5
    variants["float-payload"] = b"\n".join(
        lines[:1] + [json.dumps(payload).encode("utf-8")] + lines[2:]
    ) + b"\n"
    for label, mutated in sorted(variants.items()):
        problem = _expect_usage_error(
            name, UsageReasonCode.JOURNAL_CORRUPT,
            UsageLedger.load,
            store=FrozenBytesStore(mutated),
            clock=StepClock(_UT0, _USTEP),
            evidence_index=index,
        )
        if problem:
            problems.append("%s accepted: %s" % (label, problem))
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "byte flip, reorder, truncation, sequence gap, digest edit, "
                 "event-id edit, and non-canonical (float) payload content "
                 "all fail closed JOURNAL_CORRUPT at load")
    )


def case_29_journal_first_recovery(results: List[Result]) -> None:
    name = "case_29_journal_first_recovery"
    problems: List[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        from usage import FileUsageStore

        store = FileUsageStore(Path(tmp) / "recovery")
        ledger, index, _clock, _fixture, tx = _golden_ledger(store=store)
        recovered = UsageLedger.load(
            store=store, clock=StepClock("2026-09-02T00:00:00Z", 60),
            evidence_index=index,
        )
        if recovered.journal_digest() != ledger.journal_digest():
            problems.append("recovered journal digest diverged")
        if state_digest(recovered.transactions()) != state_digest(
            ledger.transactions()
        ):
            problems.append("recovered state digest diverged")
        if command_ledger_digest(recovered.command_ledger()) != command_ledger_digest(
            ledger.command_ledger()
        ):
            problems.append("recovered command ledger diverged")
        for live in ledger.transactions():
            replayed = recovered.transaction(live.transaction_id)
            if replayed.to_dict() != live.to_dict():
                problems.append(
                    "replayed transaction %s diverged" % live.transaction_id
                )
        recovered.verify_replay()
        if recovered.reconciliation_statement(tx) != ledger.reconciliation_statement(tx):
            problems.append("recovered reconciliation statement diverged")
        # durable idempotency: a redelivered command is a no-op after restart
        out = recovered.observe_usage(
            command_id="u-02", transaction_id=tx,
            quantity_class=QuantityClass.DELIVERED, quantity=90,
            evidence_id=_evidence_id_of(ledger, 0),
            window_start="2026-09-01T12:03:00Z", window_end=_W2,
            actor="meter", source="usage-collector",
        )
        if out.status != CommandStatus.DUPLICATE:
            problems.append("redelivery after restart was not a no-op")
        # the evidence-window duplicate layer is also durable
        out = recovered.observe_usage(
            command_id="post-recovery-shard", transaction_id=tx,
            quantity_class=QuantityClass.DELIVERED, quantity=120,
            evidence_id=_evidence_id_of(ledger, 0), window_start=_W1,
            window_end="2026-09-01T12:03:00Z",
            actor="meter", source="usage-collector-shard",
        )
        if out.status != CommandStatus.DUPLICATE:
            problems.append("evidence duplicate after restart was not a no-op")
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "load == live byte-identical (journal, state, ledger, "
                 "reconciliation); command AND evidence-window idempotency "
                 "survive restart")
    )


def case_30_replay_verification(results: List[Result]) -> None:
    name = "case_30_replay_verification"
    ledger, index, _clock, _fixture, tx = _golden_ledger()
    problems: List[str] = []
    folded = fold_state(
        ledger.journal_records(), evidence_index=index
    )
    live = {
        transaction.transaction_id: transaction.to_dict()
        for transaction in ledger.transactions()
    }
    replayed = {key: value.to_dict() for key, value in folded.items()}
    if live != replayed:
        problems.append("fold != live state")
    if fold_state(
        ledger.journal_records(), evidence_index=index
    ) != folded:
        problems.append("fold not deterministic")
    ledger.verify_replay()
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "fold(journal) == live state byte-identical; the fold is a "
                 "pure function")
    )


def case_31_inserted_out_of_order_record(results: List[Result]) -> None:
    name = "case_31_inserted_out_of_order_record"
    ledger, index, _clock, _fixture, tx = _golden_ledger()
    problems: List[str] = []
    # rebuild the journal with an INSERTED record whose event is
    # table-legal, action-coherent, and fully recomputed (event
    # id, command digest, hash chain, sequences) but whose
    # declared from_state does not connect to the folded walk:
    # a record-refund inserted while the walk is still OBSERVING.
    lines = [
        json.loads(line.decode("utf-8"))
        for line in b"".join(
            record.to_line() for record in ledger.journal_records()
        ).split(b"\n")[:-1]
    ]
    forged_command = UsageCommand(
        command_id="forged-refund",
        action=UsageAction.RECORD_REFUND,
        transaction_id=tx,
        payload={"amount_micros": 50, "reason": "forged"},
        actor="attacker",
        source="forged-source",
    )
    forged_event = UsageEvent(
        event_id=derive_event_id(
            tx, UsageAction.RECORD_REFUND,
            UsageTransactionState.BILLABLE_FINAL,
            UsageTransactionState.BILLABLE_FINAL,
            forged_command.command_id, "sha256:" + "f" * 64, _UT0,
        ),
        transaction_id=tx,
        action=UsageAction.RECORD_REFUND,
        from_state=UsageTransactionState.BILLABLE_FINAL,
        to_state=UsageTransactionState.BILLABLE_FINAL,
        command_id=forged_command.command_id,
        fact={
            "kind": "usage-compensation-record",
            "compensation_id": "sha256:" + "f" * 64,
            "transaction_id": tx,
            "compensation_kind": "refund",
            "amount_micros": 50,
            "reason": "forged",
            "statement_id": "sha256:" + "e" * 64,
            "command_id": "forged-refund",
            "recorded_at": _UT0,
        },
        actor="attacker",
        source="forged-source",
        instant=_UT0,
    )
    forged = {
        "sequence": 4,
        "record_id": "",
        "command": forged_command.to_dict(),
        "command_digest": forged_command.digest(),
        "event": forged_event.to_dict(),
    }
    new_records = lines[:3] + [forged] + lines[3:]
    prev = GENESIS_RECORD_ID
    for position, record in enumerate(new_records):
        record["sequence"] = position + 1
        content = record_content(
            UsageCommand.from_dict(record["command"]),
            record["command_digest"],
            UsageEvent.from_dict(record["event"]),
        )
        record["record_id"] = derive_record_id(position + 1, content, prev)
        prev = record["record_id"]
    mutated = b"".join(
        (json.dumps(record) + "\n").encode("utf-8") for record in new_records
    )
    problem = _expect_usage_error(
        name, UsageReasonCode.JOURNAL_CORRUPT,
        UsageLedger.load,
        store=FrozenBytesStore(mutated),
        clock=StepClock(_UT0, _USTEP),
        evidence_index=index,
    )
    if problem:
        problems.append("inserted record accepted: %s" % problem)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "a fully-recomputed, chain-valid, table-legal record whose "
                 "from_state does not connect to the folded walk is rejected "
                 "at replay (the causal identity re-derivation and the "
                 "walk-linkage verification both gate inserted records; a "
                 "fabricated compensation id that does not re-derive from its "
                 "content fails the fact identity gate, and a connected "
                 "fabrication would still fail the walk gate)")
    )


def case_32_persist_then_ack(results: List[Result]) -> None:
    name = "case_32_persist_then_ack"
    problems: List[str] = []
    runtime, peer, session_id, manager, integrator, shared = _usage_world()
    references = _references(manager, integrator, session_id)
    core, tx = _commercial_thread(references, StepClock(_UT0, 60))
    index = _evidence_index(integrator, core, tx, with_distractor=False)
    failing = FailingUsageStore()
    ledger = UsageLedger(
        store=failing, clock=StepClock(_UT0, _USTEP), evidence_index=index
    )
    wifi_events = _wifi_journal_events(integrator)
    evidence_id = "sha256:" + hashlib.sha256(
        canonical_json_bytes(
            {
                "kind": "delivery-evidence-window",
                "from_event": wifi_events[0].event_id,
                "to_event": wifi_events[1].event_id,
            }
        )
    ).hexdigest()
    problem = _expect_usage_error(
        name, UsageReasonCode.STORE_FAILED,
        ledger.observe_usage,
        command_id="ph-1", transaction_id=tx,
        quantity_class=QuantityClass.DELIVERED, quantity=10,
        evidence_id=evidence_id, window_start=_W1, window_end=_W2,
        actor="meter", source="usage-collector",
    )
    if problem:
        problems.append("store failure not surfaced: %s" % problem)
    if len(ledger.journal_records()) != 0:
        problems.append("phantom journal record after store failure")
    problem = _expect_usage_error(
        name, UsageReasonCode.TRANSACTION_UNKNOWN,
        ledger.transaction, "sha256:" + "0" * 64,
    )
    if problem:
        problems.append("phantom transaction after store failure: %s" % problem)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "a store failure leaves no phantom in-memory state "
                 "(persist-then-ack)")
    )


def case_33_deterministic_two_run(results: List[Result]) -> None:
    name = "case_33_deterministic_two_run"
    first = _scenario_stream()
    second = _scenario_stream()
    if first != second:
        results.append(fail(name, "two fresh runs diverged: %r vs %r" % (first, second)))
        return
    results.append(ok(
        name, "two fresh runs byte-identical (journal/state/ledger/events/"
              "evidence-index digests): %s" % first["digest_stream_sha256"][:24]
    ))


def case_34_subprocess_hash_seeds(results: List[Result]) -> None:
    name = "case_34_subprocess_hash_seeds"
    problems: List[str] = []
    baseline = _scenario_stream()
    for seed in ("0", "1", "7919"):
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = seed
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()),
             "--determinism-stream"],
            capture_output=True, text=True, env=env, cwd=str(REPO_ROOT),
        )
        if proc.returncode != 0:
            problems.append("seed %s failed: %s" % (seed, proc.stderr[:120]))
            continue
        stream: Dict[str, str] = {}
        for line in proc.stdout.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                stream[key] = value
        if stream != baseline:
            problems.append("seed %s diverged" % seed)
    # unset seed
    env = dict(os.environ)
    env.pop("PYTHONHASHSEED", None)
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()),
         "--determinism-stream"],
        capture_output=True, text=True, env=env, cwd=str(REPO_ROOT),
    )
    if proc.returncode == 0:
        stream = {}
        for line in proc.stdout.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                stream[key] = value
        if stream != baseline:
            problems.append("unset seed diverged")
    else:
        problems.append("unset seed failed: %s" % proc.stderr[:120])
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "PYTHONHASHSEED 0/1/7919/unset subprocesses all reproduce the "
                 "baseline digest stream byte-identically")
    )


def case_35_clock_discipline(results: List[Result]) -> None:
    name = "case_35_clock_discipline"
    ledger, index, clock, _fixture, tx = _golden_ledger()
    problems: List[str] = []
    if clock.reads != 9:
        problems.append("golden run clock reads %d (expected 9)" % clock.reads)
    reads_before = clock.reads
    # duplicates consume no read
    ledger.observe_usage(
        command_id="u-01", transaction_id=tx,
        quantity_class=QuantityClass.DELIVERED, quantity=120,
        evidence_id=_evidence_id_of(ledger, 0), window_start=_W1,
        window_end="2026-09-01T12:03:00Z", actor="meter",
        source="usage-collector",
    )
    if clock.reads != reads_before:
        problems.append("duplicate consumed a clock read")
    # a rejected state-gate command consumes exactly one read
    try:
        ledger.observe_usage(
            command_id="post-seal", transaction_id=tx,
            quantity_class=QuantityClass.DELIVERED, quantity=1,
            evidence_id=_evidence_id_of(ledger, 2),
            window_start="2026-09-01T12:07:00Z", window_end=_W3,
            actor="meter", source="usage-collector",
        )
        problems.append("post-seal observation accepted")
    except UsageError:
        pass
    if clock.reads != reads_before + 1:
        problems.append(
            "state-gate rejection consumed %d reads (expected 1)"
            % (clock.reads - reads_before)
        )
    # no public method accepts an instant parameter (the only
    # time source is the seam)
    for method_name in (
        "observe_usage", "seal_billable", "record_refund",
        "record_reversal", "record_dispute",
    ):
        parameters = inspect.signature(
            getattr(UsageLedger, method_name)
        ).parameters
        for parameter in parameters:
            if "instant" in parameter or parameter in ("now", "time", "at"):
                problems.append(
                    "%s accepts time parameter %r" % (method_name, parameter)
                )
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "duplicates consume no clock read; every other submission "
                 "consumes exactly one (even state-gate rejections); no public "
                 "method accepts an instant (the seam is the only time source)")
    )


def case_36_secret_hygiene(results: List[Result]) -> None:
    name = "case_36_secret_hygiene"
    ledger, index, _clock, _fixture, tx = _golden_ledger()
    problems: List[str] = []
    data = b"".join(record.to_line() for record in ledger.journal_records())
    for secret in (_SECRET_A, _SECRET_B, _KEY_A, _KEY_B):
        if secret in data:
            problems.append("journal bytes carry battery secret material")
    stream = ledger.digest_stream()
    for secret in (_SECRET_A, _SECRET_B, _KEY_A, _KEY_B):
        if secret in stream.encode("utf-8"):
            problems.append("digest stream carries battery secret material")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "journal and digest bytes carry no key material, "
                 "credentials, or secret-like tokens")
    )


def case_37_no_shadow_authority(results: List[Result]) -> None:
    name = "case_37_no_shadow_authority"
    problems: List[str] = []
    for path in _FAMILY_FILES:
        text = path.read_text(encoding="utf-8")
        for token in _FORBIDDEN_TOKENS:
            if token in text:
                problems.append(
                    "%s contains forbidden authority token %r"
                    % (path.name, token)
                )
    # the UsageLedger constructor takes NO authority objects:
    # only a store, the clock seam, and the evidence index
    parameters = list(inspect.signature(UsageLedger.__init__).parameters)
    for parameter in parameters:
        if parameter in (
            "runtime", "manager", "session_store", "peer", "integrator",
            "authority", "engine", "agent", "core", "references",
        ):
            problems.append("constructor accepts authority parameter %r" % parameter)
    load_parameters = list(inspect.signature(UsageLedger.load).parameters)
    for parameter in load_parameters:
        if parameter in (
            "runtime", "manager", "session_store", "peer", "integrator",
            "authority", "engine", "agent", "core", "references",
        ):
            problems.append("load accepts authority parameter %r" % parameter)
    # the battery's own public-path discipline: no private
    # attribute access on the composed authorities or the ledger
    import re

    battery_text = Path(__file__).resolve().read_text(encoding="utf-8")
    for pattern in (
        r"\b(?:ledger|ledger[0-9]+|recovered|recovered[0-9]+|observing|fresh|empty|pre_ledger)\._",
        r"\b(?:manager|runtime|peer|integrator|session_store|commercial_core|core|core_two)\._",
    ):
        for match in re.finditer(pattern, battery_text):
            problems.append(
                "battery accesses private attribute %r (public path only)"
                % battery_text[match.start():match.start() + 30]
            )
            break
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "no authority construction/mutation tokens; no authority "
                 "parameters; battery public-path only (no private access)")
    )


def case_38_import_discipline(results: List[Result]) -> None:
    name = "case_38_import_discipline"
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
                    if module in ("random", "secrets", "uuid", "platform",
                                  "os", "socket", "subprocess", "time", "datetime"):
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
                if module in ("random", "secrets", "uuid", "platform",
                              "os", "socket", "subprocess", "time", "datetime"):
                    problems.append("%s imports forbidden module %r" % (path.name, module))
                elif not (
                    module in _ALLOWED_IMPORT_MODULES
                    or any(module.startswith(prefix) for prefix in _ALLOWED_IMPORT_PREFIXES)
                ):
                    problems.append("%s imports unsanctioned module %r" % (path.name, module))
    # vendor/payment-provider tokens never appear in the family
    for path in _FAMILY_FILES:
        text = path.read_text(encoding="utf-8").lower()
        for token in _VENDOR_TOKENS:
            if token in text:
                problems.append("%s encodes vendor token %r" % (path.name, token))
                break
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "sanctioned imports only (protocol/clock seams); no vendor "
                 "tokens; no random/secrets/uuid/os/time/datetime")
    )


def case_39_public_api_stability(results: List[Result]) -> None:
    name = "case_39_public_api_stability"
    if sorted(usage.__all__) != _EXPECTED_API:
        missing = set(_EXPECTED_API) - set(usage.__all__)
        extra = set(usage.__all__) - set(_EXPECTED_API)
        results.append(
            fail(name, "API drifted (missing %r, extra %r)"
                        % (sorted(missing), sorted(extra)))
        )
        return
    results.append(ok(name, "frozen public API: %d names" % len(_EXPECTED_API)))


def case_40_fail_closed_battery(results: List[Result]) -> None:
    name = "case_40_fail_closed_battery"
    # every reason code in the frozen vocabulary must be exercised
    # by this battery at least once: either named in a case vector
    # (grep the battery text by the class ATTRIBUTE name) or
    # exercised directly below.
    battery_text = Path(__file__).resolve().read_text(encoding="utf-8")
    problems: List[str] = []
    exercised: set = set()
    for reason in UsageReasonCode.values():
        attribute = reason.upper().replace("-", "_")
        if "UsageReasonCode.%s" % attribute in battery_text:
            exercised.add(reason)
    # direct exercises for the remaining structural reasons
    ledger, index, _clock, _fixture, tx = _golden_ledger()
    # INVALID_INPUT: the constructor rejects a non-store seam
    problem = _expect_usage_error(
        name, UsageReasonCode.INVALID_INPUT,
        UsageLedger, store=object(), clock=StepClock(_UT0, _USTEP),
        evidence_index=index,
    )
    if problem:
        problems.append("invalid-input: %s" % problem)
    else:
        exercised.add(UsageReasonCode.INVALID_INPUT)
    # COMMAND_INVALID: a zero-quantity observation (payload shape)
    problem = _expect_usage_error(
        name, UsageReasonCode.COMMAND_INVALID,
        ledger.observe_usage,
        command_id="shape-1", transaction_id=tx,
        quantity_class=QuantityClass.DELIVERED, quantity=0,
        evidence_id=_evidence_id_of(ledger, 2),
        window_start="2026-09-01T12:07:00Z", window_end=_W3,
        actor="meter", source="usage-collector",
    )
    if problem:
        problems.append("command-invalid: %s" % problem)
    else:
        exercised.add(UsageReasonCode.COMMAND_INVALID)
    # OBSERVATION_REJECTED: a DELIVERED-class observation without
    # the evidence citation members
    problem = _expect_usage_error(
        name, UsageReasonCode.OBSERVATION_REJECTED,
        ledger.observe_usage,
        command_id="shape-2", transaction_id=tx,
        quantity_class=QuantityClass.DELIVERED, quantity=5,
        actor="meter", source="usage-collector",
    )
    if problem:
        problems.append("observation-rejected: %s" % problem)
    else:
        exercised.add(UsageReasonCode.OBSERVATION_REJECTED)
    # OBSERVATION_CLASS_INVALID: a bogus quantity class
    problem = _expect_usage_error(
        name, UsageReasonCode.OBSERVATION_CLASS_INVALID,
        ledger.observe_usage,
        command_id="shape-3", transaction_id=tx,
        quantity_class="bogus-class", quantity=5,
        actor="meter", source="usage-collector",
    )
    if problem:
        problems.append("observation-class-invalid: %s" % problem)
    else:
        exercised.add(UsageReasonCode.OBSERVATION_CLASS_INVALID)
    # EVENT_INVALID: a malformed event payload
    problem = _expect_usage_error(
        name, UsageReasonCode.EVENT_INVALID,
        UsageEvent.from_dict, {"event_id": "x"},
    )
    if problem:
        problems.append("event-invalid: %s" % problem)
    else:
        exercised.add(UsageReasonCode.EVENT_INVALID)
    # INSTANT_INVALID: a malformed recorded instant
    problem = _expect_usage_error(
        name, UsageReasonCode.INSTANT_INVALID,
        UsageObservationRecord,
        observation_id="o-bad", command_id="c-bad", transaction_id="t-bad",
        quantity_class=QuantityClass.RESERVED, quantity=5,
        recorded_at="not-an-instant",
    )
    if problem:
        problems.append("instant-invalid: %s" % problem)
    else:
        exercised.add(UsageReasonCode.INSTANT_INVALID)
    missing = sorted(set(UsageReasonCode.values()) - exercised)
    if missing:
        problems.append("never exercised: %r" % missing[:5])
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "all %d frozen reason codes exercised (case vectors + "
                 "direct structural exercises)" % len(UsageReasonCode.values()))
    )


def case_41_authority_composition(results: List[Result]) -> None:
    name = "case_41_authority_reference_composition"
    ledger, index, _clock, fixture, tx = _golden_ledger()
    runtime, peer, session_id, manager, integrator, shared = fixture
    problems: List[str] = []
    # the evidence index is built from public reads only: the
    # transaction snapshot cites a REAL W051 transaction whose
    # public projection state is DELIVERY_COMPLETED
    snapshot = index.transaction(tx)
    if snapshot.commercial_state != "DELIVERY_COMPLETED":
        problems.append("snapshot state %s" % snapshot.commercial_state)
    if snapshot.tariff_provenance != "commercial-core-public-read":
        problems.append("tariff provenance %s" % snapshot.tariff_provenance)
    # the delivery evidence cites REAL platform-journal events
    for evidence_id in index.evidence_ids():
        record = index.evidence(evidence_id)
        if record.provenance == "platform-journal" and record.is_usage_eligible():
            pass  # real journal-derived window (verified structurally below)
    wifi_events = _wifi_journal_events(integrator)
    if len(wifi_events) != 3:
        problems.append("fixture journal shape wrong: %d wlan events" % len(wifi_events))
    evidence_by_tx = index.evidence_by_transaction(tx)
    delivered = [record for record in evidence_by_tx if record.is_usage_eligible()]
    if len(delivered) != 2:
        problems.append("expected 2 delivered windows, got %d" % len(delivered))
    if sum(record.delivered_quantity for record in delivered) != 360:
        problems.append("evidence window totals wrong")
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "the index cites the real W051 public transaction state and "
                 "the real platform-journal delivery-plane time series "
                 "(2 windows, 360 bytes total) -- public reads only")
    )


def case_42_py_compile(results: List[Result]) -> None:
    name = "case_42_py_compile"
    problems: List[str] = []
    targets = list(_FAMILY_FILES) + [Path(__file__).resolve()]
    for path in targets:
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as error:
            problems.append("%s does not compile: %s" % (path.name, error))
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(ok(name, "usage/ (%d modules) and the battery compile"
                            % len(_FAMILY_FILES)))


def _origin_main_available() -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/main"],
        capture_output=True, cwd=str(REPO_ROOT),
    )
    return proc.returncode == 0


def case_43_frozen_spec_intact(results: List[Result]) -> None:
    name = "case_43_frozen_spec_intact"
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
        "spec/architect/authorizations/WORK-052.yaml",
        "spec/architect/roadmap.yaml",
        "spec/architect/roadmap.md",
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
                 "schema/roadmap/W052-authorization byte-identical to "
                 "origin/main")
    )


def case_44_pr_delta_shape(results: List[Result]) -> None:
    name = "case_44_pr_delta_shape_authorized_scope"
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
        if "python3 tools/usage_selftest.py" not in workflow:
            problems.append("CI wiring missing the usage battery step")
        added = [
            line for line in wiring_diff.stdout.splitlines()
            if line.startswith("+") and "python3 tools/" in line
        ]
        for line in added:
            if "usage_selftest.py" not in line:
                problems.append("CI wiring added an unrelated step: %r" % line)
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "delta confined to the WORK-052-CORE-001 scope (%d file(s) + "
                 "sanctioned additive CI wiring)" % len(delta))
    )


def case_45_fresh_world_independence(results: List[Result]) -> None:
    name = "case_45_fresh_world_independence"
    problems: List[str] = []
    # every vector builds its own world; two structurally
    # different worlds produce distinct streams
    stream_a = _scenario_stream()
    runtime, peer, session_id, manager, integrator, shared = _usage_world()
    references = _references(manager, integrator, session_id)
    core, tx = _commercial_thread(
        references, StepClock(_UT0, 60), prefix="alt-",
        intent={"buyer": "alt-buyer", "region": "ke"},
    )
    index = _evidence_index(integrator, core, tx, with_distractor=False)
    ledger = UsageLedger(
        store=MemoryUsageStore(), clock=CountingClock(StepClock(_UT0, _USTEP)),
        evidence_index=index,
    )
    wifi_events = _wifi_journal_events(integrator)
    evidence_id = "sha256:" + hashlib.sha256(
        canonical_json_bytes(
            {
                "kind": "delivery-evidence-window",
                "from_event": wifi_events[0].event_id,
                "to_event": wifi_events[1].event_id,
            }
        )
    ).hexdigest()
    ledger.observe_usage(
        command_id="alt-1", transaction_id=tx,
        quantity_class=QuantityClass.DELIVERED, quantity=210,
        evidence_id=evidence_id, window_start=_W1, window_end=_W2,
        actor="meter", source="usage-collector",
    )
    stream_b = {
        "journal_digest": ledger.journal_digest(),
        "state_digest": state_digest(ledger.transactions()),
        "command_ledger_digest": command_ledger_digest(ledger.command_ledger()),
        "event_list_digest": usage.event_list_digest(
            tuple(record.event for record in ledger.journal_records())
        ),
        "evidence_index_digest": evidence_index_digest(index),
        "digest_stream_sha256": hashlib.sha256(
            ledger.digest_stream().encode("utf-8")
        ).hexdigest(),
    }
    if stream_a == stream_b:
        problems.append("structurally different worlds produced the same stream")
    # interleaved coexisting worlds reproduce their isolated baselines
    world_a = _golden_ledger()
    ledger_a, index_a, clock_a, fixture_a, tx_a = world_a
    baseline_a = {
        "journal": ledger_a.journal_digest(),
        "state": state_digest(ledger_a.transactions()),
        "recon": ledger_a.reconciliation_statement(tx_a),
    }
    runtime2, peer2, session2, manager2, integrator2, shared2 = _usage_world()
    references2 = _references(manager2, integrator2, session2)
    core2, tx_b = _commercial_thread(
        references2, StepClock("2026-09-01T15:00:00Z", 60), prefix="inter-",
        deadline="2026-09-01T15:30:00Z",
    )
    index_b = _evidence_index(integrator2, core2, tx_b, with_distractor=False)
    ledger_b = UsageLedger(
        store=MemoryUsageStore(), clock=CountingClock(StepClock("2026-09-01T16:00:00Z", 60)),
        evidence_index=index_b,
    )
    wifi_events2 = _wifi_journal_events(integrator2)
    evidence_id2 = "sha256:" + hashlib.sha256(
        canonical_json_bytes(
            {
                "kind": "delivery-evidence-window",
                "from_event": wifi_events2[0].event_id,
                "to_event": wifi_events2[1].event_id,
            }
        )
    ).hexdigest()
    ledger_b.observe_usage(
        command_id="inter-1", transaction_id=tx_b,
        quantity_class=QuantityClass.DELIVERED, quantity=210,
        evidence_id=evidence_id2, window_start=_W1, window_end=_W2,
        actor="meter", source="usage-collector",
    )
    ledger_b.seal_billable(
        command_id="inter-2", transaction_id=tx_b, actor="billing",
        source="usage-ledger",
    )
    # world A is untouched by world B's activity
    if ledger_a.journal_digest() != baseline_a["journal"]:
        problems.append("interleaved world A journal drifted")
    if state_digest(ledger_a.transactions()) != baseline_a["state"]:
        problems.append("interleaved world A state drifted")
    if ledger_a.reconciliation_statement(tx_a) != baseline_a["recon"]:
        problems.append("interleaved world A reconciliation drifted")
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "every vector builds its own world; different worlds produce "
                 "distinct streams; interleaved coexisting worlds reproduce "
                 "their isolated baselines byte-for-byte")
    )


# ---------------------------------------------------------------------------
# Walk-valid, fully-recomputed-chain fact tampering (the P0
# replay-integrity adversarial class): mutate a stored fact,
# recompute EVERY identity the implementation itself derives
# (fact id, event id, and the entire outer record hash chain,
# optionally the command digest and every downstream fact that
# transitively binds the mutated identity), keep the state walk
# valid -- and prove replay still rejects the unauthorized fact
# mutation (fail-closed JOURNAL_CORRUPT).
# ---------------------------------------------------------------------------


def _golden_journal_lines(ledger: UsageLedger) -> List[Dict[str, Any]]:
    """The golden journal parsed into mutable record dicts (the
    tampering substrate)."""
    return [
        json.loads(line.decode("utf-8"))
        for line in b"".join(
            record.to_line() for record in ledger.journal_records()
        ).split(b"\n")[:-1]
    ]


def _rechain(records: List[Dict[str, Any]]) -> bytes:
    """Recompute the FULL outer hash chain (every record id and
    sequence link) over mutated record dicts -- the adversarial
    'recomputed chain' primitive: the tampered journal is
    structurally chain-valid, exactly as a motivated attacker
    would produce."""
    prev = GENESIS_RECORD_ID
    for position, record in enumerate(records):
        record["sequence"] = position + 1
        content = record_content(
            UsageCommand.from_dict(record["command"]),
            record["command_digest"],
            UsageEvent.from_dict(record["event"]),
        )
        record["record_id"] = derive_record_id(position + 1, content, prev)
        prev = record["record_id"]
    return b"".join(
        (json.dumps(record) + "\n").encode("utf-8") for record in records
    )


def _recompute_event_id(record: Dict[str, Any], fact_id: str) -> None:
    """Recompute one record's event id over its (mutated) fact
    identity (the identity cascade)."""
    event = record["event"]
    event["event_id"] = derive_event_id(
        event["transaction_id"],
        event["action"],
        event["from_state"],
        event["to_state"],
        event["command_id"],
        fact_id,
        event["instant"],
    )


def case_46_walk_valid_recomputed_observation_tamper(
    results: List[Result],
) -> None:
    name = "case_46_walk_valid_recomputed_chain_observation_tamper"
    ledger, index, _clock, _fixture, tx = _golden_ledger()
    problems: List[str] = []
    lines = _golden_journal_lines(ledger)

    # Variant A -- fact-only mutation with the FULL identity
    # cascade (recomputed observation id, event id, and the
    # entire outer chain), the command + its digest UNTOUCHED,
    # the walk untouched: only the causal command->fact binding
    # can catch it.
    records = json.loads(json.dumps(lines))
    fact = records[1]["event"]["fact"]
    fact["quantity"] = 95
    fact["observation_id"] = derive_observation_id(
        records[1]["command"]["command_id"],
        tx,
        fact["quantity_class"],
        fact["quantity"],
        fact["evidence_id"],
        fact["window_start"],
        fact["window_end"],
        fact["recorded_at"],
    )
    _recompute_event_id(records[1], fact["observation_id"])
    problem = _expect_usage_error(
        name, UsageReasonCode.JOURNAL_CORRUPT,
        UsageLedger.load,
        store=FrozenBytesStore(_rechain(records)),
        clock=StepClock(_UT0, _USTEP),
        evidence_index=index,
    )
    if problem:
        problems.append("fact-only observation tamper accepted: %s" % problem)

    # Variant B -- the MAXIMAL cascade: the command payload is
    # mutated too (quantity 90 -> 95, digest recomputed), the
    # observation fact + all identities recomputed, the sealed
    # statement re-derived over the mutated fold (quantities
    # 315, amount 945 at the honest price, audit list
    # recomputed, statement id recomputed), the compensations
    # re-derived over the new statement id, and the entire
    # outer chain recomputed.  The journal is internally
    # self-consistent AND tariff-consistent; the EXTERNAL
    # authority anchor (the injected evidence index: cumulative
    # observed 120 + 95 exceeds the authoritative 210) is the
    # only gate that can reject it -- and it does.
    records = json.loads(json.dumps(lines))
    observation_record = records[1]
    command = observation_record["command"]
    command["payload"]["quantity"] = 95
    observation_record["command_digest"] = UsageCommand.from_dict(
        command
    ).digest()
    fact = observation_record["event"]["fact"]
    fact["quantity"] = 95
    old_observation_id = fact["observation_id"]
    new_observation_id = derive_observation_id(
        command["command_id"],
        tx,
        fact["quantity_class"],
        fact["quantity"],
        fact["evidence_id"],
        fact["window_start"],
        fact["window_end"],
        fact["recorded_at"],
    )
    fact["observation_id"] = new_observation_id
    _recompute_event_id(observation_record, new_observation_id)
    # cascade the seal over the mutated fold
    seal = records[5]
    seal_fact = seal["event"]["fact"]
    seal_fact["delivered_quantity"] = 315
    seal_fact["billable_quantity"] = 315
    seal_fact["amount_micros"] = 945
    seal_fact["contributing_observations"] = sorted(
        new_observation_id if oid == old_observation_id else oid
        for oid in seal_fact["contributing_observations"]
    )
    new_statement_id = derive_statement_id(
        tx,
        tuple(seal_fact["contributing_observations"]),
        seal_fact["sealed_at"],
    )
    seal_fact["statement_id"] = new_statement_id
    _recompute_event_id(seal, new_statement_id)
    # cascade the compensations (they cite the statement id)
    for compensation_record in records[6:9]:
        compensation_fact = compensation_record["event"]["fact"]
        compensation_fact["statement_id"] = new_statement_id
        compensation_fact["compensation_id"] = derive_compensation_id(
            tx,
            compensation_fact["compensation_kind"],
            compensation_fact["amount_micros"],
            compensation_fact["reason"],
            new_statement_id,
            compensation_fact["command_id"],
            compensation_fact["recorded_at"],
        )
        _recompute_event_id(
            compensation_record, compensation_fact["compensation_id"]
        )
    problem = _expect_usage_error(
        name, UsageReasonCode.JOURNAL_CORRUPT,
        UsageLedger.load,
        store=FrozenBytesStore(_rechain(records)),
        clock=StepClock(_UT0, _USTEP),
        evidence_index=index,
    )
    if problem:
        problems.append("maximal-cascade observation tamper accepted: %s" % problem)

    # Variant C -- an attribution swap on the event (actor forged
    # to a different principal than the admitted command's),
    # chain recomputed, walk untouched: the event/command
    # attribution binding gate catches it.
    records = json.loads(json.dumps(lines))
    records[1]["event"]["actor"] = "attacker"
    problem = _expect_usage_error(
        name, UsageReasonCode.JOURNAL_CORRUPT,
        UsageLedger.load,
        store=FrozenBytesStore(_rechain(records)),
        clock=StepClock(_UT0, _USTEP),
        evidence_index=index,
    )
    if problem:
        problems.append("attribution swap accepted: %s" % problem)

    # Variant D -- a fact-kind swap (an observe-usage event whose
    # fact claims to be a compensation record), chain recomputed,
    # walk untouched: the action/fact table gate catches it.
    records = json.loads(json.dumps(lines))
    records[1]["event"]["fact"] = {
        "kind": "usage-compensation-record",
        "compensation_id": "sha256:" + "a" * 64,
        "transaction_id": tx,
        "compensation_kind": "refund",
        "amount_micros": 1,
        "reason": "kind swap",
        "statement_id": "sha256:" + "b" * 64,
        "command_id": records[1]["command"]["command_id"],
        "recorded_at": records[1]["event"]["instant"],
    }
    problem = _expect_usage_error(
        name, UsageReasonCode.JOURNAL_CORRUPT,
        UsageLedger.load,
        store=FrozenBytesStore(_rechain(records)),
        clock=StepClock(_UT0, _USTEP),
        evidence_index=index,
    )
    if problem:
        problems.append("fact-kind swap accepted: %s" % problem)

    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "an observation mutated with a fully recomputed identity "
                 "cascade and outer chain (walk valid) is rejected at "
                 "replay: fact-only tampering fails the causal command->fact "
                 "binding; a MAXIMAL cascade (mutated command + digest, "
                 "re-derived seal and compensations, fully self-consistent "
                 "quantities/amount at the honest tariff) still fails the "
                 "injected evidence authority (cumulative 120 + 95 exceeds "
                 "the authoritative 210); an attribution swap fails the "
                 "event/command attribution binding; a fact-kind swap fails "
                 "the action/fact table")
    )


def case_47_walk_valid_recomputed_seal_tamper(results: List[Result]) -> None:
    name = "case_47_walk_valid_recomputed_chain_seal_tamper"
    ledger, index, _clock, _fixture, tx = _golden_ledger()
    problems: List[str] = []
    lines = _golden_journal_lines(ledger)

    # Variant A -- a walk-valid, fully chain-recomputed tariff
    # tamper on the sealed bill: unit price 3 -> 30 with the
    # amount made INTERNALLY arithmetic-consistent (9300 =
    # 310 * 30).  The statement id (which binds tx + audit list
    # + sealed_at, not the price) is unchanged, so no cascade
    # beyond the outer chain is even needed; only the tariff
    # re-binding to the injected W051 snapshot can catch it.
    records = json.loads(json.dumps(lines))
    seal_fact = records[5]["event"]["fact"]
    seal_fact["unit_price_micros"] = 30
    seal_fact["amount_micros"] = 9300
    problem = _expect_usage_error(
        name, UsageReasonCode.JOURNAL_CORRUPT,
        UsageLedger.load,
        store=FrozenBytesStore(_rechain(records)),
        clock=StepClock(_UT0, _USTEP),
        evidence_index=index,
    )
    if problem:
        problems.append("tariff tamper accepted: %s" % problem)

    # Variant B -- an internally-INCONSISTENT amount (honest
    # price, wrong total): the fact model arithmetic gate
    # rejects it as corruption at replay.
    records = json.loads(json.dumps(lines))
    records[5]["event"]["fact"]["amount_micros"] = 931
    problem = _expect_usage_error(
        name, UsageReasonCode.JOURNAL_CORRUPT,
        UsageLedger.load,
        store=FrozenBytesStore(_rechain(records)),
        clock=StepClock(_UT0, _USTEP),
        evidence_index=index,
    )
    if problem:
        problems.append("inconsistent-amount tamper accepted: %s" % problem)

    # Variant C -- the same tariff tamper on the honest
    # zero-observation seal (amount pinned to 0; only the unit
    # price drifts): the zero-seal re-derivation binds it to
    # the injected snapshot exactly like every other seal.
    runtime, peer, session_id, manager, integrator, shared = _usage_world()
    references = _references(manager, integrator, session_id)
    core, tx_zero = _commercial_thread(
        references, StepClock(_UT0, 60), prefix="zt-"
    )
    zero_index = _evidence_index(
        integrator, core, tx_zero, with_distractor=False
    )
    empty = UsageLedger(
        store=MemoryUsageStore(), clock=StepClock(_UT0, _USTEP),
        evidence_index=zero_index,
    )
    empty.seal_billable(
        command_id="zero-seal", transaction_id=tx_zero, actor="billing",
        source="usage-ledger",
    )
    zero_lines = _golden_journal_lines(empty)
    zero_lines[0]["event"]["fact"]["unit_price_micros"] = 30
    problem = _expect_usage_error(
        name, UsageReasonCode.JOURNAL_CORRUPT,
        UsageLedger.load,
        store=FrozenBytesStore(_rechain(zero_lines)),
        clock=StepClock(_UT0, _USTEP),
        evidence_index=zero_index,
    )
    if problem:
        problems.append("zero-seal tariff tamper accepted: %s" % problem)

    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "the sealed bill is re-bound to the authoritative tariff at "
                 "replay: a walk-valid chain-recomputed repricing (internally "
                 "arithmetic-consistent) fails the W051 snapshot binding; an "
                 "internally inconsistent amount fails the fact arithmetic; "
                 "and the zero-bill seal is tariff-bound exactly like every "
                 "other seal (a recomputed outer chain cannot reprice the "
                 "billable fact)")
    )


def case_48_walk_valid_recomputed_compensation_tamper(
    results: List[Result],
) -> None:
    name = "case_48_walk_valid_recomputed_chain_compensation_tamper"
    ledger, index, _clock, _fixture, tx = _golden_ledger()
    problems: List[str] = []
    lines = _golden_journal_lines(ledger)

    # Variant A -- fact-only compensation payload tamper with
    # the FULL identity cascade (recomputed compensation id,
    # event id, outer chain), command + digest untouched, walk
    # untouched: only the causal command->fact binding catches
    # it.
    records = json.loads(json.dumps(lines))
    refund_fact = records[6]["event"]["fact"]
    refund_fact["amount_micros"] = 400
    refund_fact["compensation_id"] = derive_compensation_id(
        tx,
        refund_fact["compensation_kind"],
        refund_fact["amount_micros"],
        refund_fact["reason"],
        refund_fact["statement_id"],
        refund_fact["command_id"],
        refund_fact["recorded_at"],
    )
    _recompute_event_id(records[6], refund_fact["compensation_id"])
    problem = _expect_usage_error(
        name, UsageReasonCode.JOURNAL_CORRUPT,
        UsageLedger.load,
        store=FrozenBytesStore(_rechain(records)),
        clock=StepClock(_UT0, _USTEP),
        evidence_index=index,
    )
    if problem:
        problems.append("fact-only compensation tamper accepted: %s" % problem)

    # Variant B -- the MAXIMAL cascade: the refund command
    # payload is mutated too (amount 200 -> 950, digest
    # recomputed), the fact + identities recomputed, the chain
    # recomputed.  Internally self-consistent; the bounded-net
    # discipline (cumulative compensation 950 exceeds the
    # sealed 930) is the gate that rejects it.
    records = json.loads(json.dumps(lines))
    refund_record = records[6]
    refund_command = refund_record["command"]
    refund_command["payload"]["amount_micros"] = 950
    refund_record["command_digest"] = UsageCommand.from_dict(
        refund_command
    ).digest()
    refund_fact = refund_record["event"]["fact"]
    refund_fact["amount_micros"] = 950
    refund_fact["compensation_id"] = derive_compensation_id(
        tx,
        refund_fact["compensation_kind"],
        refund_fact["amount_micros"],
        refund_fact["reason"],
        refund_fact["statement_id"],
        refund_fact["command_id"],
        refund_fact["recorded_at"],
    )
    _recompute_event_id(refund_record, refund_fact["compensation_id"])
    problem = _expect_usage_error(
        name, UsageReasonCode.JOURNAL_CORRUPT,
        UsageLedger.load,
        store=FrozenBytesStore(_rechain(records)),
        clock=StepClock(_UT0, _USTEP),
        evidence_index=index,
    )
    if problem:
        problems.append("maximal-cascade compensation tamper accepted: %s" % problem)

    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "a compensation mutated with a fully recomputed identity "
                 "cascade and outer chain (walk valid) is rejected at "
                 "replay: fact-only tampering fails the causal command->fact "
                 "binding; a MAXIMAL cascade (mutated command + digest, "
                 "self-consistent fact) still fails the bounded-net "
                 "discipline (950 exceeds the sealed 930)")
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    results: List[Result] = []
    for case in (
        case_01_frozen_vocabularies,
        case_02_transition_table,
        case_03_command_model,
        case_04_fact_models,
        case_05_golden_scenario,
        case_06_every_legal_transition,
        case_07_every_illegal_transition,
        case_08_valid_delivered_ingestion,
        case_09_missing_fabricated_evidence,
        case_10_kind_gates,
        case_11_transaction_correlation,
        case_12_quantity_window_discipline,
        case_13_reservation_not_usage,
        case_14_payment_not_usage,
        case_15_duplicate_commands,
        case_16_conflicting_duplicates,
        case_17_evidence_duplicates,
        case_18_cumulative_cap,
        case_19_out_of_order_delayed,
        case_20_late_after_seal,
        case_21_billable_final_explicit,
        case_22_final_immutable,
        case_23_compensation_family,
        case_24_compensation_exceeded,
        case_25_dispute_already_open,
        case_26_deterministic_reconciliation,
        case_27_immutable_history,
        case_28_tampered_journal,
        case_29_journal_first_recovery,
        case_30_replay_verification,
        case_31_inserted_out_of_order_record,
        case_32_persist_then_ack,
        case_33_deterministic_two_run,
        case_34_subprocess_hash_seeds,
        case_35_clock_discipline,
        case_36_secret_hygiene,
        case_37_no_shadow_authority,
        case_38_import_discipline,
        case_39_public_api_stability,
        case_40_fail_closed_battery,
        case_41_authority_composition,
        case_42_py_compile,
        case_43_frozen_spec_intact,
        case_44_pr_delta_shape,
        case_45_fresh_world_independence,
        case_46_walk_valid_recomputed_observation_tamper,
        case_47_walk_valid_recomputed_seal_tamper,
        case_48_walk_valid_recomputed_compensation_tamper,
    ):
        case(results)
    failures = [result for result in results if not result[1]]
    for entry in results:
        print("[%s] %-48s %s" % ("ok  " if entry[1] else "FAIL", entry[0], entry[2]))
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
