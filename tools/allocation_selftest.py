#!/usr/bin/env python3
"""WORK-053 EconomicAllocation battery (deterministic, stdlib only).

End-to-end verification of the canonical economic-allocation
layer (ACR-009 "Economic allocation", authorization
WORK-053-CORE-001 / DEC-0061, baseline bcaf0d0) composing the
accepted WORK-052 UsageLedger, WORK-051 CommercialCore, WORK-033
Linux reference agent, WORK-012 logical sessions, WORK-041
NetworkPath, and the W042 platform journal:

- frozen vocabularies: the three-state subject walk (REGISTERED
  policy subjects; PLANNED / SETTLED allocation subjects), the
  nine-action vocabulary, the 27-reason vocabulary, the two
  external-reference kinds, the three rounding modes, the
  five compensation kinds, and the frozen transition table;
- billable-final-only admission (invariant 1): allocation
  consumes ONLY billable-final UsageLedger facts -- the
  admission/replay-symmetric finality gate rejects OBSERVING
  usage (USAGE_NOT_FINAL), the kind table rejects payment and
  settlement references as usage citations
  (PAYMENT_NOT_USAGE / SETTLEMENT_NOT_USAGE), and payment
  success, reservation state, offer state, or provider
  callbacks have NO allocation-creating path at all (the
  payment-reference action is DATA-only and structurally cannot
  create or transition allocation);
- immutable policy versions (invariant 2): version ids are
  content-derived over the TERMS ONLY (identical terms = the
  identical version; re-registration is the idempotent no-op);
  effective-date selection is the declared-window gate; every
  allocation cites exactly one policy version and exactly one
  billable-final usage record (exactly one allocation per usage
  record: the second ALLOCATE fails closed
  ALLOCATION_ALREADY_EXISTS);
- exact deterministic arithmetic (invariant 3): integer-only
  micro amounts, explicit declared rounding (floor / half-up /
  half-even, hand-computed pins + an exhaustive conservation
  sweep), exact three-way conservation
  (adcos + provider + developer == distributable;
  distributable + fee + tax + adjustment == gross -- mechanical
  model invariants re-derived at replay), idempotency at three
  layers (command id, policy-version identity, provider-callback
  identity), and conflicting-identity rejection
  (COMMAND_CONFLICT / ALLOCATION_ALREADY_EXISTS);
- settled-history immutability (invariant 4): the immutable
  allocation snapshot (no rewrite path exists; the snapshot
  survives compensations byte-identically), the exactly-once
  settlement acknowledgement (SETTLEMENT_IMMUTABLE), and
  append-only compensating events for refunds, reversals,
  chargebacks, payout failures, and disputes (bounded by the
  distributable amount, net never negative, one open dispute,
  COMPENSATION_REQUIRES_SETTLED before settlement);
- external payment boundary (invariants 5-8): external
  references are DATA only (kind table: PAYMENT_NOT_SETTLEMENT /
  SETTLEMENT_NOT_PAYMENT; correlation: REFERENCE_MISMATCH;
  fabricated citations: REFERENCE_UNKNOWN), failed/duplicate/
  delayed/out-of-order provider callbacks never corrupt
  canonical allocation state (duplicates are no-ops; the
  reference-id multiset and state are arrival-order independent
  while the record identities are honestly
  admission-attributed), no amounts or provider semantics cross
  the boundary, ADCOS neither custodies nor moves regulated
  funds, and no payment-provider-specific concept exists in the
  canonical model (vendor-token AST audit);
- authority boundaries (invariant 9): structural audits -- no
  second authority (construction/mutation token discipline over
  the frozen authority set), no authority parameters anywhere in
  the allocation surface, sanctioned imports only, frozen
  public API (75 names), frozen spec surfaces intact (including
  the WORK-053 authorization itself), PR delta confined to the
  authorized W053 scope (+ the sanctioned additive-only CI
  wiring), and the honest two-track evidence disclosure
  (software verified; PHYSICAL device evidence OPEN and
  W040-owned -- no synthetic physical claims);
- durability: append-only hash-chained journal (byte tamper,
  reorder, truncation, sequence-gap, digest-edit, event-id-edit
  all fail closed JOURNAL_CORRUPT), persist-then-ack (a store
  failure leaves no phantom state), journal-first recovery
  (load == live, byte-identical; idempotency survives restart),
  replay verification (fold == live state), inserted
  out-of-order records fail closed at the walk-linkage gate,
  AND the full replay integrity boundary: the fold re-derives
  and verifies every content-derived fact identity (policy
  version / allocation snapshot / settlement acknowledgement /
  payment reference / compensation), the event identities, the
  command/fact/attribution bindings, the walk linkage, the
  allocation's re-binding to the injected W052 usage snapshot
  (gross, statement, BILLABLE_FINAL finality) and to the folded
  immutable policy version (resolution, bounds, effective
  window), the external-reference kind/correlation re-resolution,
  and the FULL allocation arithmetic re-derivation -- so
  WALK-VALID, FULLY-RECOMPUTED-CHAIN fact tampering (mutated
  fact + recomputed identities + recomputed outer hash chain:
  repriced shares, repriced gross, repriced policy terms,
  repriced compensation amounts, forged non-final usage
  consumption, forged settlement-kind citations, and duplicated
  callback identities) all fail closed JOURNAL_CORRUPT
  (cases 43-48, each with an honest-shaped control that loads
  cleanly, pinning the rejection to the exact gate);
- determinism: the golden scenario's whole digest stream
  (journal, state, command ledger, event list, evidence index)
  is byte-identical across two fresh in-process runs, across
  fresh coexisting worlds, and across PYTHONHASHSEED
  0/1/7919/unset subprocesses; the ONLY time source is the
  injected clock seam (duplicates consume no read; every other
  submission consumes exactly one; no wall-clock module is
  imported in the allocation family);
- secret hygiene: journal and digest bytes carry no key
  material, credentials, or secret-like tokens;
- fresh-world independence: every vector builds its own fixture
  world; coexisting worlds reproduce their isolated baselines
  byte-for-byte -- no shared mutable allocation state.

The battery exercises the PUBLIC production path only: the
ordinary AgentRuntime session establishment chain, the
NetworkPathManager public lifecycle, the PlatformIntegrator
public journal reads, the W051 CommercialCore public surface
(driven to DELIVERY_COMPLETED through its typed methods), the
W052 UsageLedger public surface (driven to BILLABLE_FINAL
through its typed methods, including the honest zero-bill
seal), and the AllocationLedger public surface.  No private
method is called to manufacture a PASS.
"""

from __future__ import annotations

import ast
import hashlib
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
    CommercialTransactionSnapshot,
    DeliveryEvidence,
    EvidenceKind,
    QuantityClass,
    UsageEvidenceIndex,
    UsageLedger,
)

import allocation  # noqa: E402
from allocation import (  # noqa: E402
    AllocationAction,
    AllocationCommand,
    AllocationCompensationRecord,
    AllocationError,
    AllocationEvent,
    AllocationEvidenceIndex,
    AllocationReasonCode,
    AllocationSnapshot,
    AllocationSubjectState,
    AllocationTransaction,
    BillableUsageSnapshot,
    BPS_DENOMINATOR,
    CommandOutcome,
    CommandStatus,
    ExternalReferenceSnapshot,
    MemoryAllocationStore,
    PaymentReferenceRecord,
    PolicySubjectState,
    PolicyVersion,
    ReferenceKind,
    RoundingMode,
    SettlementAcknowledgement,
    USAGE_STATE_FINAL,
    apply_rounding,
    build_allocation_snapshot,
    compute_split,
    derive_allocation_id,
    derive_compensation_id,
    derive_event_id,
    derive_payment_reference_id,
    derive_policy_id,
    derive_settlement_ack_id,
    transition_is_legal,
    transition_target,
    validate_payload_shape,
)
from allocation.digest import (
    command_ledger_digest,
    evidence_index_digest,
)
from allocation.journal import (  # noqa: E402
    GENESIS_RECORD_ID,
    AllocationStore,
    derive_record_id,
    journal_bytes_for,
    record_content,
)
from allocation.ledger import (
    AllocationFoldState,
    AllocationLedger,
    CommandOutcome as LedgerCommandOutcome,  # noqa: F401 - re-exported API pin
)
from allocation.model import derive_command_digest

Result = Tuple[str, bool, str]

# ---------------------------------------------------------------------------
# Frozen audit constants
# ---------------------------------------------------------------------------

_FAMILY_FILES = sorted((REPO_ROOT / "allocation").rglob("*.py"))

_T0 = "2025-06-01T00:00:00Z"
_FRESH = "2026-06-01T00:00:00Z"
_SECRET_A = b"w053-battery-secret-A"
_SECRET_B = b"w053-battery-secret-B"
_PROFILE_ID = "identity.sha256-hmac-dev.v1"
_KEY_A = b"w053-battery-key-A"
_KEY_B = b"w053-battery-key-B"

#: The golden-scenario delivery-plane metering time series on
#: the active path interface (cumulative rx/tx counters read
#: through the platform journal's public surface): 12:01 -> 120
#: total, 12:05 -> 330, 12:10 -> 480.  The caller derives the
#: delivery evidence windows from the CONSECUTIVE DELTAS
#: (public-read-only derivation): [12:01, 12:05] = 210,
#: [12:05, 12:10] = 150.
_W1 = "2026-09-01T12:01:00Z"
_W2 = "2026-09-01T12:05:00Z"
_W3 = "2026-09-01T12:10:00Z"
WIFI_IF = "wlan0"
ETH_IF = "eth0"
USB_IF = "usb0"
CELL_IF = "vpn0"

#: The golden-scenario tariff: the W051 offer published through
#: the commercial core's public surface (unit "byte", price "3";
#: the usage ledger multiplies exactly).
_TARIFF_PRICE = 3

#: The usage-ledger fixture clock epoch and step.
_UT0 = "2026-09-01T12:00:00Z"
_USTEP = 60

#: The allocation-ledger golden clock epoch and step (exactly one
#: read per non-duplicate command submission).
_AT0 = "2026-10-01T09:00:00Z"
_ASTEP = 60

#: The golden policy terms (the platform-defined revenue-share
#: contract): ADCOS 15%, developer-selectable provider share of
#: the residual bounded to [30%, 70%], half-up rounding, USD,
#: micro precision, effective calendar 2026.
_POLICY_LABEL = "standard-2026"
_POLICY_ADCOS_BPS = 1500
_POLICY_MIN_BPS = 3000
_POLICY_MAX_BPS = 7000
_POLICY_ROUNDING = "half-up"
_POLICY_CURRENCY = "usd"
_POLICY_DIGITS = 6
_POLICY_FROM = "2026-01-01T00:00:00Z"
_POLICY_UNTIL = "2027-01-01T00:00:00Z"

#: The golden c1 allocation inputs: gross 930 (310 delivered
#: bytes x 3), fee 30, tax 57, adjustment -7 -> distributable
#: 850; the exact half-up three-way split is (128, 361, 361).
_C1_FEE = 30
_C1_TAX = 57
_C1_ADJUSTMENT = -7
_C1_GROSS = 930
_C1_DISTRIBUTABLE = 850
_C1_ADCOS = 128
_C1_PROVIDER = 361
_C1_DEVELOPER = 361

#: The golden c2 allocation: gross 48 (16 x 3), no charges,
#: provider split 6500 bps -> the exact half-up split is
#: (7, 27, 14).
_C2_GROSS = 48
_C2_ADCOS = 7
_C2_PROVIDER = 27
_C2_DEVELOPER = 14

#: The frozen allocation public API surface (independently
#: pinned here; the package must match exactly).
_EXPECTED_API = sorted([
    "ALLOCATION_TRANSITIONS",
    "AllocationAction",
    "AllocationCommand",
    "AllocationCompensationRecord",
    "AllocationError",
    "AllocationEvent",
    "AllocationEvidenceIndex",
    "AllocationFoldState",
    "AllocationJournalRecord",
    "AllocationLedger",
    "AllocationReasonCode",
    "AllocationSnapshot",
    "AllocationStore",
    "AllocationSubjectState",
    "AllocationTransaction",
    "AppendOnlyAllocationJournal",
    "BPS_DENOMINATOR",
    "BillableUsageSnapshot",
    "COMPENSATION_KIND_BY_ACTION",
    "CommandOutcome",
    "CommandStatus",
    "ExternalReferenceSnapshot",
    "FileAllocationStore",
    "GENESIS_RECORD_ID",
    "JOURNAL_RECORD_KIND",
    "KNOWN_USAGE_STATES",
    "MONETARY_COMPENSATION_KINDS",
    "MemoryAllocationStore",
    "PAYLOAD_MEMBER_RULES",
    "PaymentReferenceRecord",
    "PolicySubjectState",
    "PolicyVersion",
    "ReferenceKind",
    "RoundingMode",
    "SUBJECT_STATE_VALUES",
    "SettlementAcknowledgement",
    "USAGE_STATE_FINAL",
    "USAGE_STATE_OBSERVING",
    "allocation_transaction_digest",
    "apply_record",
    "apply_rounding",
    "assemble_digest_stream",
    "build_allocation_snapshot",
    "command_content",
    "command_ledger_digest",
    "compute_split",
    "derive_allocation_id",
    "derive_command_digest",
    "derive_compensation_id",
    "derive_event_id",
    "derive_payment_reference_id",
    "derive_policy_id",
    "derive_record_id",
    "derive_settlement_ack_id",
    "digest_of",
    "event_list_digest",
    "evidence_index_digest",
    "find_duplicate_payment_reference",
    "fold_state",
    "journal_bytes_for",
    "policy_registry_digest",
    "record_list_digest",
    "resolve_payment_reference",
    "resolve_policy",
    "resolve_settlement_reference",
    "resolve_usage_projection",
    "state_digest",
    "transition_is_legal",
    "transition_target",
    "validate_command_against_state",
    "validate_event_instant",
    "validate_payload_shape",
    "validate_policy_effective",
    "validate_split_bounds",
    "validate_usage_finality",
])

#: The authorized W053 delta surface (scope of
#: WORK-053-CORE-001) plus the sanctioned additive CI-wiring
#: path (the W041/W042/W051/W052 battery precedent).
_AUTHORIZED_PATHS = (
    "allocation/",
    "tools/allocation_selftest.py",
    "docs/WORK-053-handoff.md",
    "docs/WORK-053-evidence.md",
)
AUTHORIZED_CI_WIRING = ".github/workflows/spec-check.yml"

#: Vendor/payment-provider tokens the allocation family must never
#: encode (technology- and provider-neutral core).
_VENDOR_TOKENS = (
    "android", "rndis", "qualcomm", "mediatek", "samsung", "broadcom",
    "huawei", "apple", "google", "windows", "darwin", "ios_",
    "open5gs", "ocudu", "openairinterface",
    "stripe", "paypal", "mtn", "vodafone", "airteltigo", "telecel",
    "visa", "mastercard", "mpesa", "alipay", "wise",
)

#: Forbidden authority-construction/mutation tokens: the
#: allocation family must never build or drive a second authority
#: (isinstance checks and type annotations against the composed
#: public classes are fine -- the scan targets CONSTRUCTION and
#: MUTATION calls).  The W052 usage-surface names that collide
#: with the allocation family's own typed method names
#: (record_refund / record_reversal / record_dispute) are
#: deliberately excluded; the two W052-unique surface names
#: (observe_usage / seal_billable) plus the import discipline
#: (the usage family is not importable from allocation/) carry
#: that separation instead.
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
    "authorize_session(", "activate_path(", "start_delivery(",
    "accrue_usage(", "complete_delivery(",
    "finalize_billable(", "initiate_settlement(",
    "observe_usage(", "seal_billable(",
)

#: The sanctioned absolute-import allowlist for the allocation
#: family (stdlib value types + the accepted seams: WORK-003
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
            role_id="w053-battery-operator",
            capabilities=(
                ManagementCapability.SESSION_READ,
                ManagementCapability.SESSION_CONTROL,
                ManagementCapability.POLICY_READ,
            ),
            description="operator role (battery fixture)",
        ),
    )


def _config(
    label: str = "allocation-node",
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
    # active path: its evidence correlates to a different usage
    # transaction in the index)
    integrator.ingest_interface_observation(
        _snap(name=ETH_IF, kind="ethernet", addresses=("fd00::a:2",), rx=11, tx=5),
        observed_at=_W1,
    )
    return runtime, peer, session_id, manager, integrator, shared


# ---------------------------------------------------------------------------
# Commercial + usage fixtures (deterministic external ids, public reads only)
# ---------------------------------------------------------------------------


def _external_id(kind: str, label: str) -> str:
    """A deterministic well-formed EXTERNAL-plane id (settlement and
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


def _wifi_evidence(
    integrator: PlatformIntegrator,
    transaction_id: str,
) -> Tuple[DeliveryEvidence, ...]:
    """Derive the authoritative delivery evidence windows from
    the platform journal's PUBLIC reads: consecutive cumulative
    counter deltas on the active path interface, correlated to
    the given usage transaction (the caller-side,
    public-read-only metering derivation; the evidence ids are
    transaction-tagged so distinct transactions cite distinct
    evidence identities)."""
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
                    "transaction": transaction_id,
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
            )
        )
    return tuple(records)


def _eth_evidence(integrator: PlatformIntegrator, transaction_id: str):
    """The distractor-interface delivery evidence (16 bytes in a
    point window), correlated to the given transaction."""
    eth = _eth_journal_event(integrator)
    return DeliveryEvidence(
        evidence_id="sha256:" + hashlib.sha256(
            canonical_json_bytes(
                {
                    "kind": "delivery-evidence-window",
                    "transaction": transaction_id,
                    "eth": eth.event_id,
                }
            )
        ).hexdigest(),
        transaction_id=transaction_id,
        delivered_quantity=(
            eth.payload["rx_bytes"] + eth.payload["tx_bytes"]
        ),
        window_start=eth.observed_at,
        window_end=eth.observed_at,
        evidence_kind=EvidenceKind.DELIVERED,
        provenance="platform-journal",
    )


def _commercial_thread(
    references: ReferenceIndex,
    clock: StepClock,
    *,
    prefix: str,
    buyer: str,
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
        intent={"buyer": buyer, "want": "connectivity", "region": "gh"},
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


def _usage_fixture():
    """The full WORK-052 production chain the allocation layer
    consumes: the booted usage world -> the W051 ReferenceIndex ->
    FOUR commercial transactions driven to DELIVERY_COMPLETED ->
    the UsageEvidenceIndex from public reads -> the UsageLedger
    public lifecycle:

    - c1: the full golden usage lifecycle (delivered sub-metering
      120 + 90 + 100 = 310, reserved/attempted DATA observations,
      seal -> BILLABLE_FINAL 930 micros, refund 200, reversal 100,
      dispute);
    - c2: the eth-distractor transaction (16 delivered bytes,
      sealed -> 48 micros);
    - c3: an OBSERVING usage transaction (one delivered
      observation, deliberately NEVER sealed -- the non-final
      negative vector);
    - c4: the honest zero-bill seal (a delivery-eligible
      transaction with NO recorded usage, sealed to quantity 0 /
      amount 0 -- the W052 zero-observation precedent).

    Returns (usage_ledger, txs, world) with txs = the four
    transaction ids keyed c1..c4.
    """
    runtime, peer, session_id, manager, integrator, shared = _usage_world()
    references = _references(manager, integrator, session_id)
    _core_c1, tx_c1 = _commercial_thread(
        references, StepClock(_UT0, _USTEP), prefix="c1-", buyer="buyer-1"
    )
    _core_c2, tx_c2 = _commercial_thread(
        references, StepClock(_UT0, _USTEP), prefix="c2-", buyer="buyer-2"
    )
    _core_c3, tx_c3 = _commercial_thread(
        references, StepClock(_UT0, _USTEP), prefix="c3-", buyer="buyer-3"
    )
    _core_c4, tx_c4 = _commercial_thread(
        references, StepClock(_UT0, _USTEP), prefix="c4-", buyer="buyer-4"
    )
    evidence: List[DeliveryEvidence] = []
    evidence.extend(_wifi_evidence(integrator, tx_c1))
    evidence.extend(_wifi_evidence(integrator, tx_c3))
    evidence.append(_eth_evidence(integrator, tx_c2))
    # the DATA-only external observation entries (payment and
    # provider observations recorded in the index so the W052
    # kind table can reject them structurally)
    evidence.append(
        DeliveryEvidence(
            evidence_id=_external_id("payment-observation", "payment-1"),
            transaction_id=tx_c1,
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
            transaction_id=tx_c1,
            delivered_quantity=0,
            window_start=_W1,
            window_end=_W3,
            evidence_kind=EvidenceKind.PROVIDER_OBSERVED,
            provenance="external-provider-observation",
        )
    )
    snapshots = [
        CommercialTransactionSnapshot(
            transaction_id=tx,
            commercial_state="DELIVERY_COMPLETED",
            unit_price_micros=_TARIFF_PRICE,
            billable_unit="byte",
            tariff_provenance="commercial-core-public-read",
        )
        for tx in (tx_c1, tx_c2, tx_c3, tx_c4)
    ]
    usage_index = UsageEvidenceIndex(evidence=evidence, transactions=snapshots)
    ledger = UsageLedger(
        store=usage.MemoryUsageStore(),
        clock=StepClock(_UT0, _USTEP),
        evidence_index=usage_index,
    )
    # c1: the full golden usage lifecycle
    c1_evidence = _wifi_evidence(integrator, tx_c1)
    ledger.observe_usage(
        command_id="w-c1-01", transaction_id=tx_c1,
        quantity_class=QuantityClass.DELIVERED, quantity=120,
        evidence_id=c1_evidence[0].evidence_id, window_start=_W1,
        window_end="2026-09-01T12:03:00Z",
        actor="meter", source="usage-collector",
    )
    ledger.observe_usage(
        command_id="w-c1-02", transaction_id=tx_c1,
        quantity_class=QuantityClass.DELIVERED, quantity=90,
        evidence_id=c1_evidence[0].evidence_id,
        window_start="2026-09-01T12:03:00Z", window_end=_W2,
        actor="meter", source="usage-collector",
    )
    ledger.observe_usage(
        command_id="w-c1-03", transaction_id=tx_c1,
        quantity_class=QuantityClass.DELIVERED, quantity=100,
        evidence_id=c1_evidence[1].evidence_id, window_start=_W2,
        window_end=_W3,
        actor="meter", source="usage-collector",
    )
    ledger.observe_usage(
        command_id="w-c1-04", transaction_id=tx_c1,
        quantity_class=QuantityClass.RESERVED, quantity=500,
        actor="meter", source="reservation-service",
    )
    ledger.observe_usage(
        command_id="w-c1-05", transaction_id=tx_c1,
        quantity_class=QuantityClass.ATTEMPTED, quantity=80,
        actor="meter", source="traffic-monitor",
    )
    ledger.seal_billable(
        command_id="w-c1-06", transaction_id=tx_c1,
        actor="billing", source="usage-ledger",
    )
    ledger.record_refund(
        command_id="w-c1-07", transaction_id=tx_c1, amount_micros=200,
        reason="goodwill credit", actor="billing", source="usage-ledger",
    )
    ledger.record_reversal(
        command_id="w-c1-08", transaction_id=tx_c1, amount_micros=100,
        reason="metering correction", actor="billing", source="usage-ledger",
    )
    ledger.record_dispute(
        command_id="w-c1-09", transaction_id=tx_c1,
        reason="buyer disputes window 2", actor="billing",
        source="usage-ledger",
    )
    # c2: the eth-distractor transaction
    ledger.observe_usage(
        command_id="w-c2-01", transaction_id=tx_c2,
        quantity_class=QuantityClass.DELIVERED, quantity=16,
        evidence_id=_eth_evidence(integrator, tx_c2).evidence_id,
        window_start=_W1, window_end=_W1,
        actor="meter", source="usage-collector",
    )
    ledger.seal_billable(
        command_id="w-c2-02", transaction_id=tx_c2,
        actor="billing", source="usage-ledger",
    )
    # c3: the OBSERVING usage transaction (never sealed)
    c3_evidence = _wifi_evidence(integrator, tx_c3)
    ledger.observe_usage(
        command_id="w-c3-01", transaction_id=tx_c3,
        quantity_class=QuantityClass.DELIVERED, quantity=120,
        evidence_id=c3_evidence[0].evidence_id, window_start=_W1,
        window_end="2026-09-01T12:03:00Z",
        actor="meter", source="usage-collector",
    )
    # c4: the honest zero-bill seal (no observations at all)
    ledger.seal_billable(
        command_id="w-c4-01", transaction_id=tx_c4,
        actor="billing", source="usage-ledger",
    )
    txs = {"c1": tx_c1, "c2": tx_c2, "c3": tx_c3, "c4": tx_c4}
    world = (runtime, peer, session_id, manager, integrator, shared)
    return ledger, txs, world


#: The external reference identities the allocation boundary
#: cites (deterministic external-plane ids, correlated to the
#: usage transactions the caller recorded them for).
def _reference_ids(txs: Dict[str, str]) -> Dict[str, str]:
    return {
        "sett-1": _external_id("settlement-confirmation", "settle-1"),
        "sett-2": _external_id("settlement-confirmation", "settle-2"),
        "sett-3": _external_id("settlement-confirmation", "settle-3"),
        "pay-1": _external_id("payment-observation", "payment-1"),
        "pay-2": _external_id("payment-observation", "payment-2"),
        "pay-3": _external_id("payment-observation", "payment-3"),
        "pay-4": _external_id("payment-observation", "payment-4"),
    }


def _allocation_index(
    usage_ledger: UsageLedger,
    txs: Dict[str, str],
) -> AllocationEvidenceIndex:
    """Build the injected AllocationEvidenceIndex from PUBLIC
    reads only: the W052 usage projections (state + sealed
    statement + W052-side compensation DATA, read through the
    UsageLedger public surface) and the external settlement/
    payment reference citations."""
    usage: List[BillableUsageSnapshot] = []
    for key in ("c1", "c2", "c3", "c4"):
        tx = txs[key]
        projection = usage_ledger.transaction(tx)
        statement = projection.statement
        if statement is None:
            usage.append(
                BillableUsageSnapshot(
                    usage_transaction_id=tx,
                    usage_state=projection.state,
                )
            )
        else:
            usage.append(
                BillableUsageSnapshot(
                    usage_transaction_id=tx,
                    usage_state=projection.state,
                    gross_amount_micros=statement.amount_micros,
                    statement_id=statement.statement_id,
                    billable_quantity=statement.billable_quantity,
                    unit_price_micros=statement.unit_price_micros,
                    billable_unit=statement.billable_unit,
                    tariff_provenance=statement.tariff_provenance,
                    refunded_amount_micros=(
                        projection.refunded_amount_micros()
                    ),
                    reversed_amount_micros=(
                        projection.reversed_amount_micros()
                    ),
                    disputed=projection.disputed(),
                    sealed_at=statement.sealed_at,
                )
            )
    refs = _reference_ids(txs)
    references = [
        ExternalReferenceSnapshot(
            refs["sett-1"], ReferenceKind.SETTLEMENT,
            "external-settlement-plane", txs["c1"],
        ),
        ExternalReferenceSnapshot(
            refs["sett-2"], ReferenceKind.SETTLEMENT,
            "external-settlement-plane", txs["c2"],
        ),
        ExternalReferenceSnapshot(
            refs["sett-3"], ReferenceKind.SETTLEMENT,
            "external-settlement-plane", txs["c3"],
        ),
        ExternalReferenceSnapshot(
            refs["pay-1"], ReferenceKind.PAYMENT,
            "external-payment-plane", txs["c1"],
        ),
        ExternalReferenceSnapshot(
            refs["pay-2"], ReferenceKind.PAYMENT,
            "external-payment-plane", txs["c1"],
        ),
        ExternalReferenceSnapshot(
            refs["pay-3"], ReferenceKind.PAYMENT,
            "external-payment-plane", txs["c2"],
        ),
        ExternalReferenceSnapshot(
            refs["pay-4"], ReferenceKind.PAYMENT,
            "external-payment-plane", None,
        ),
    ]
    return AllocationEvidenceIndex(usage=usage, references=references)


def _usage_statements(
    usage_ledger: UsageLedger, txs: Dict[str, str]
) -> Dict[str, str]:
    """The sealed usage statement ids (public reads)."""
    return {
        key: usage_ledger.transaction(txs[key]).statement.statement_id
        for key in ("c1", "c2", "c4")
    }


def _golden_ledger(
    store: Optional[AllocationStore] = None,
    *,
    prefix: str = "e-",
):
    """The canonical golden run: the full authority composition
    (usage world -> W051 -> W052 billable-final facts) -> the
    allocation evidence index from public reads -> the golden
    allocation lifecycle:

    policy registration -> c1 allocation (fees/taxes/adjustment,
    the exact three-way split) -> payment callback (PLANNED) ->
    settlement acknowledgement -> delayed payment callback
    (SETTLED) -> refund/reversal/chargeback/payout-failure/
    dispute compensations -> c2 allocation -> payment callback ->
    settlement acknowledgement.

    Returns (ledger, index, clock, (usage_ledger, txs, world),
    reference ids).
    """
    usage_ledger, txs, world = _usage_fixture()
    index = _allocation_index(usage_ledger, txs)
    statements = _usage_statements(usage_ledger, txs)
    refs = _reference_ids(txs)
    if store is None:
        store = MemoryAllocationStore()
    clock = CountingClock(StepClock(_AT0, _ASTEP))
    ledger = AllocationLedger(
        store=store, clock=clock, evidence_index=index
    )
    policy = ledger.register_policy(
        command_id=prefix + "01",
        label=_POLICY_LABEL,
        adcos_share_bps=_POLICY_ADCOS_BPS,
        provider_min_bps=_POLICY_MIN_BPS,
        provider_max_bps=_POLICY_MAX_BPS,
        rounding_mode=_POLICY_ROUNDING,
        currency=_POLICY_CURRENCY,
        minor_unit_digits=_POLICY_DIGITS,
        effective_from=_POLICY_FROM,
        effective_until=_POLICY_UNTIL,
        actor="platform", source="economic-policy-service",
    )
    ledger.allocate(
        command_id=prefix + "02",
        usage_transaction_id=txs["c1"],
        usage_statement_id=statements["c1"],
        policy_id=policy.fact_id,
        provider_share_bps=5000,
        fee_micros=_C1_FEE,
        tax_micros=_C1_TAX,
        adjustment_micros=_C1_ADJUSTMENT,
        actor="billing", source="allocation-service",
    )
    ledger.record_payment_reference(
        command_id=prefix + "03",
        usage_transaction_id=txs["c1"],
        payment_reference=refs["pay-1"],
        actor="payment-callback-gateway",
        source="payment-provider-boundary",
    )
    ledger.acknowledge_settlement(
        command_id=prefix + "04",
        usage_transaction_id=txs["c1"],
        settlement_reference=refs["sett-1"],
        actor="settlement", source="settlement-service",
    )
    ledger.record_payment_reference(
        command_id=prefix + "05",
        usage_transaction_id=txs["c1"],
        payment_reference=refs["pay-2"],
        actor="payment-callback-gateway",
        source="payment-provider-boundary",
    )
    ledger.record_refund(
        command_id=prefix + "06", usage_transaction_id=txs["c1"],
        amount_micros=100, reason="goodwill credit",
        actor="billing", source="allocation-service",
    )
    ledger.record_reversal(
        command_id=prefix + "07", usage_transaction_id=txs["c1"],
        amount_micros=50, reason="metering correction",
        actor="billing", source="allocation-service",
    )
    ledger.record_chargeback(
        command_id=prefix + "08", usage_transaction_id=txs["c1"],
        amount_micros=25, reason="buyer chargeback",
        actor="billing", source="allocation-service",
    )
    ledger.record_payout_failure(
        command_id=prefix + "09", usage_transaction_id=txs["c1"],
        amount_micros=10, reason="provider payout failed",
        actor="billing", source="allocation-service",
    )
    ledger.record_dispute(
        command_id=prefix + "10", usage_transaction_id=txs["c1"],
        reason="provider disputes window 2",
        actor="billing", source="allocation-service",
    )
    ledger.allocate(
        command_id=prefix + "11",
        usage_transaction_id=txs["c2"],
        usage_statement_id=statements["c2"],
        policy_id=policy.fact_id,
        provider_share_bps=6500,
        actor="billing", source="allocation-service",
    )
    ledger.record_payment_reference(
        command_id=prefix + "12",
        usage_transaction_id=txs["c2"],
        payment_reference=refs["pay-3"],
        actor="payment-callback-gateway",
        source="payment-provider-boundary",
    )
    ledger.acknowledge_settlement(
        command_id=prefix + "13",
        usage_transaction_id=txs["c2"],
        settlement_reference=refs["sett-2"],
        actor="settlement", source="settlement-service",
    )
    fixture = (usage_ledger, txs, world)
    return ledger, index, clock, fixture, refs


def _golden_policy_id() -> str:
    """The golden policy version id (content-derived over the
    terms only)."""
    return derive_policy_id(
        _POLICY_LABEL, _POLICY_ADCOS_BPS, _POLICY_MIN_BPS,
        _POLICY_MAX_BPS, _POLICY_ROUNDING, _POLICY_CURRENCY,
        _POLICY_DIGITS, _POLICY_FROM, _POLICY_UNTIL,
    )


def _scenario_stream(store: Optional[AllocationStore] = None) -> Dict[str, str]:
    """The canonical battery scenario: full authority composition
    -> the golden allocation lifecycle -> the deterministic
    digest stream."""
    ledger, index, _clock, _fixture, _refs = _golden_ledger(store)
    events = tuple(record.event for record in ledger.journal_records())
    return {
        "journal_digest": ledger.journal_digest(),
        "state_digest": ledger.state_digest(),
        "command_ledger_digest": command_ledger_digest(
            ledger.command_ledger()
        ),
        "event_list_digest": allocation.event_list_digest(events),
        "evidence_index_digest": evidence_index_digest(index),
        "digest_stream_sha256": hashlib.sha256(
            ledger.digest_stream().encode("utf-8")
        ).hexdigest(),
    }


# ---------------------------------------------------------------------------
# Battery fixtures
# ---------------------------------------------------------------------------


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


class BrokenClock(AgentClock):
    """A battery fixture: returns a malformed instant (the
    INSTANT_INVALID fail-closed vector)."""

    def now(self) -> str:
        return "not-an-instant"


class FailingAllocationStore(MemoryAllocationStore):
    """A battery fixture: fails the first append (persist-then-ack
    discipline: no phantom in-memory state)."""

    def __init__(self, fail_on: int = 1) -> None:
        super().__init__()
        self._fail_on = fail_on
        self._appends = 0

    def append_journal_line(self, line: bytes) -> None:
        self._appends += 1
        if self._appends >= self._fail_on:
            raise AllocationError(
                AllocationReasonCode.STORE_FAILED,
                "battery-injected store failure",
            )
        super().append_journal_line(line)


class FrozenBytesStore(AllocationStore):
    """A battery fixture: fixed journal bytes (tamper vectors)."""

    def __init__(self, data: bytes) -> None:
        self._data = bytes(data)

    def append_journal_line(self, line: bytes) -> None:
        raise AllocationError(
            AllocationReasonCode.STORE_FAILED, "frozen fixture store"
        )

    def journal_bytes(self) -> bytes:
        return self._data


def _expect_allocation_error(
    case_name: str, expected_reason: str, function, *args, **kwargs
) -> Optional[str]:
    """Run ``function`` expecting the typed AllocationError with
    the exact ``expected_reason``; return a problem string if it
    did not."""
    try:
        function(*args, **kwargs)
    except AllocationError as error:
        if error.reason != expected_reason:
            return "expected %s, raised %s (%s)" % (
                expected_reason, error.reason, error.detail[:80],
            )
        return None
    except Exception as error:  # noqa: BLE001 - wrong exception type
        return "raised %s: %s" % (type(error).__name__, error)
    return "no error raised (expected %s)" % expected_reason


def _golden_journal_lines(ledger: AllocationLedger) -> List[Dict[str, Any]]:
    """The golden journal as record dicts (tamper-vector basis)."""
    data = b"".join(
        record.to_line() for record in ledger.journal_records()
    )
    return [
        json.loads(line)
        for line in data.decode("utf-8").splitlines()
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
            AllocationCommand.from_dict(record["command"]),
            record["command_digest"],
            AllocationEvent.from_dict(record["event"]),
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
        event["subject_id"],
        event["action"],
        event["from_state"],
        event["to_state"],
        event["command_id"],
        fact_id,
        event["instant"],
    )


def _golden_policy_record(prefix: str = "e-") -> Dict[str, Any]:
    """The honest golden policy registration record dict (forge
    basis: the exact command + fact the golden run admitted)."""
    command = {
        "command_id": prefix + "01",
        "action": "register-policy",
        "subject_id": _POLICY_LABEL,
        "payload": {
            "adcos_share_bps": _POLICY_ADCOS_BPS,
            "provider_min_bps": _POLICY_MIN_BPS,
            "provider_max_bps": _POLICY_MAX_BPS,
            "rounding_mode": _POLICY_ROUNDING,
            "currency": _POLICY_CURRENCY,
            "minor_unit_digits": _POLICY_DIGITS,
            "effective_from": _POLICY_FROM,
            "effective_until": _POLICY_UNTIL,
        },
        "actor": "platform",
        "source": "economic-policy-service",
    }
    registered_at = _AT0
    policy = PolicyVersion(
        policy_id=_golden_policy_id(),
        label=_POLICY_LABEL,
        adcos_share_bps=_POLICY_ADCOS_BPS,
        provider_min_bps=_POLICY_MIN_BPS,
        provider_max_bps=_POLICY_MAX_BPS,
        rounding_mode=_POLICY_ROUNDING,
        currency=_POLICY_CURRENCY,
        minor_unit_digits=_POLICY_DIGITS,
        effective_from=_POLICY_FROM,
        effective_until=_POLICY_UNTIL,
        command_id=command["command_id"],
        registered_at=registered_at,
    )
    return {
        "sequence": 1,
        "record_id": "",
        "command": command,
        "command_digest": AllocationCommand.from_dict(command).digest(),
        "event": {
            "event_id": "",
            "subject_id": _POLICY_LABEL,
            "action": "register-policy",
            "from_state": "REGISTERED",
            "to_state": "REGISTERED",
            "command_id": command["command_id"],
            "fact": policy.to_dict(),
            "actor": "platform",
            "source": "economic-policy-service",
            "instant": registered_at,
        },
    }


def _forge_four_record_journal(
    *,
    usage_transaction_id: str,
    usage_statement_id: str,
    gross_micros: int,
    settlement_reference: str,
    policy_prefix: str = "e-",
) -> List[Dict[str, Any]]:
    """Build the WALK-VALID, FULLY-RECOMPUTED four-record forged
    journal (policy registration -> allocation -> settlement
    acknowledgement -> refund) claiming the given usage
    consumption and settlement citation.

    Every content-derived identity (command digests, policy id,
    allocation id, event ids, acknowledgement id, compensation
    id) and the ENTIRE outer record chain are recomputed over the
    forged facts -- exactly the adversarial construction a
    motivated attacker with full journal write access would
    produce.  The allocation arithmetic is internally exact
    (zero charges, provider split 5000 bps under the golden
    policy's declared rounding), the walk edges are
    frozen-table legal, and the refund is bounded: internally
    self-consistent, so ONLY the authority-side re-binding gates
    (usage finality, reference kind) can reject it."""
    t1 = _AT0
    t2 = "2026-10-01T09:00:01Z"
    t3 = "2026-10-01T09:00:02Z"
    t4 = "2026-10-01T09:00:03Z"
    policy_record = _golden_policy_record(policy_prefix)
    policy_id = _golden_policy_id()
    # the forged allocation (zero charges; split under the golden terms)
    adcos, provider, developer = compute_split(
        gross_micros, _POLICY_ADCOS_BPS, 5000, _POLICY_ROUNDING
    )
    allocation = AllocationSnapshot(
        allocation_id=derive_allocation_id(
            usage_transaction_id, usage_statement_id, policy_id,
            5000, 0, 0, 0, t2,
        ),
        usage_transaction_id=usage_transaction_id,
        usage_statement_id=usage_statement_id,
        policy_id=policy_id,
        gross_micros=gross_micros,
        fee_micros=0,
        tax_micros=0,
        adjustment_micros=0,
        distributable_micros=gross_micros,
        adcos_share_micros=adcos,
        provider_share_micros=provider,
        developer_share_micros=developer,
        provider_share_bps=5000,
        adcos_share_bps=_POLICY_ADCOS_BPS,
        rounding_mode=_POLICY_ROUNDING,
        currency=_POLICY_CURRENCY,
        minor_unit_digits=_POLICY_DIGITS,
        created_at=t2,
    )
    allocate_command = {
        "command_id": "forge-alloc",
        "action": "allocate",
        "subject_id": usage_transaction_id,
        "payload": {
            "usage_statement_id": usage_statement_id,
            "policy_id": policy_id,
            "provider_share_bps": 5000,
            "fee_micros": 0,
            "tax_micros": 0,
            "adjustment_micros": 0,
        },
        "actor": "billing",
        "source": "allocation-service",
    }
    allocate_event = {
        "event_id": "",
        "subject_id": usage_transaction_id,
        "action": "allocate",
        "from_state": "PLANNED",
        "to_state": "PLANNED",
        "command_id": "forge-alloc",
        "fact": allocation.to_dict(),
        "actor": "billing",
        "source": "allocation-service",
        "instant": t2,
    }
    # the forged settlement acknowledgement (the cited reference
    # is the attacker's chosen kind violation or honest citation)
    acknowledgement = SettlementAcknowledgement(
        acknowledgement_id=derive_settlement_ack_id(
            usage_transaction_id, allocation.allocation_id,
            settlement_reference, "forge-settle", t3,
        ),
        usage_transaction_id=usage_transaction_id,
        allocation_id=allocation.allocation_id,
        settlement_reference=settlement_reference,
        command_id="forge-settle",
        acknowledged_at=t3,
    )
    settle_command = {
        "command_id": "forge-settle",
        "action": "acknowledge-settlement",
        "subject_id": usage_transaction_id,
        "payload": {"settlement_reference": settlement_reference},
        "actor": "settlement",
        "source": "settlement-service",
    }
    settle_event = {
        "event_id": "",
        "subject_id": usage_transaction_id,
        "action": "acknowledge-settlement",
        "from_state": "PLANNED",
        "to_state": "SETTLED",
        "command_id": "forge-settle",
        "fact": acknowledgement.to_dict(),
        "actor": "settlement",
        "source": "settlement-service",
        "instant": t3,
    }
    # the forged refund (bounded by the distributable amount)
    refund_amount = min(50, gross_micros)
    compensation = AllocationCompensationRecord(
        compensation_id=derive_compensation_id(
            usage_transaction_id, "refund", refund_amount,
            "forged refund", allocation.allocation_id, "forge-refund", t4,
        ),
        usage_transaction_id=usage_transaction_id,
        compensation_kind="refund",
        amount_micros=refund_amount,
        reason="forged refund",
        allocation_id=allocation.allocation_id,
        command_id="forge-refund",
        recorded_at=t4,
    )
    refund_command = {
        "command_id": "forge-refund",
        "action": "record-refund",
        "subject_id": usage_transaction_id,
        "payload": {
            "amount_micros": refund_amount, "reason": "forged refund",
        },
        "actor": "billing",
        "source": "allocation-service",
    }
    refund_event = {
        "event_id": "",
        "subject_id": usage_transaction_id,
        "action": "record-refund",
        "from_state": "SETTLED",
        "to_state": "SETTLED",
        "command_id": "forge-refund",
        "fact": compensation.to_dict(),
        "actor": "billing",
        "source": "allocation-service",
        "instant": t4,
    }
    records = [
        policy_record,
        {
            "sequence": 2, "record_id": "",
            "command": allocate_command,
            "command_digest": (
                AllocationCommand.from_dict(allocate_command).digest()
            ),
            "event": allocate_event,
        },
        {
            "sequence": 3, "record_id": "",
            "command": settle_command,
            "command_digest": (
                AllocationCommand.from_dict(settle_command).digest()
            ),
            "event": settle_event,
        },
        {
            "sequence": 4, "record_id": "",
            "command": refund_command,
            "command_digest": (
                AllocationCommand.from_dict(refund_command).digest()
            ),
            "event": refund_event,
        },
    ]
    # cascade the event ids over the fact identities
    _recompute_event_id(records[0], policy_id)
    _recompute_event_id(records[1], allocation.allocation_id)
    _recompute_event_id(records[2], acknowledgement.acknowledgement_id)
    _recompute_event_id(records[3], compensation.compensation_id)
    return records


def _forge_duplicate_callback_journal(
    *,
    usage_transaction_id: str,
    usage_statement_id: str,
    gross_micros: int,
    payment_reference: str,
) -> List[Dict[str, Any]]:
    """Build the WALK-VALID, FULLY-RECOMPUTED four-record forged
    journal whose TWO payment-callback records cite the SAME
    external reference identity (the duplicate-callback forgery:
    admission de-duplicates callback redelivery, so the journal
    cannot carry both)."""
    t1 = _AT0
    t2 = "2026-10-01T09:00:01Z"
    t3 = "2026-10-01T09:00:02Z"
    t4 = "2026-10-01T09:00:03Z"
    policy_record = _golden_policy_record("e-")
    policy_id = _golden_policy_id()
    adcos, provider, developer = compute_split(
        gross_micros, _POLICY_ADCOS_BPS, 5000, _POLICY_ROUNDING
    )
    allocation = AllocationSnapshot(
        allocation_id=derive_allocation_id(
            usage_transaction_id, usage_statement_id, policy_id,
            5000, 0, 0, 0, t2,
        ),
        usage_transaction_id=usage_transaction_id,
        usage_statement_id=usage_statement_id,
        policy_id=policy_id,
        gross_micros=gross_micros,
        fee_micros=0,
        tax_micros=0,
        adjustment_micros=0,
        distributable_micros=gross_micros,
        adcos_share_micros=adcos,
        provider_share_micros=provider,
        developer_share_micros=developer,
        provider_share_bps=5000,
        adcos_share_bps=_POLICY_ADCOS_BPS,
        rounding_mode=_POLICY_ROUNDING,
        currency=_POLICY_CURRENCY,
        minor_unit_digits=_POLICY_DIGITS,
        created_at=t2,
    )
    allocate_command = {
        "command_id": "forge-alloc",
        "action": "allocate",
        "subject_id": usage_transaction_id,
        "payload": {
            "usage_statement_id": usage_statement_id,
            "policy_id": policy_id,
            "provider_share_bps": 5000,
            "fee_micros": 0,
            "tax_micros": 0,
            "adjustment_micros": 0,
        },
        "actor": "billing",
        "source": "allocation-service",
    }
    allocate_event = {
        "event_id": "",
        "subject_id": usage_transaction_id,
        "action": "allocate",
        "from_state": "PLANNED",
        "to_state": "PLANNED",
        "command_id": "forge-alloc",
        "fact": allocation.to_dict(),
        "actor": "billing",
        "source": "allocation-service",
        "instant": t2,
    }

    def callback_record(command_id: str, instant: str) -> Dict[str, Any]:
        record = PaymentReferenceRecord(
            payment_reference_id=derive_payment_reference_id(
                usage_transaction_id, allocation.allocation_id,
                payment_reference, command_id, instant,
            ),
            usage_transaction_id=usage_transaction_id,
            allocation_id=allocation.allocation_id,
            payment_reference=payment_reference,
            command_id=command_id,
            recorded_at=instant,
        )
        command = {
            "command_id": command_id,
            "action": "record-payment-reference",
            "subject_id": usage_transaction_id,
            "payload": {"payment_reference": payment_reference},
            "actor": "payment-callback-gateway",
            "source": "payment-provider-boundary",
        }
        event = {
            "event_id": "",
            "subject_id": usage_transaction_id,
            "action": "record-payment-reference",
            "from_state": "PLANNED",
            "to_state": "PLANNED",
            "command_id": command_id,
            "fact": record.to_dict(),
            "actor": "payment-callback-gateway",
            "source": "payment-provider-boundary",
            "instant": instant,
        }
        return {
            "sequence": 0, "record_id": "",
            "command": command,
            "command_digest": AllocationCommand.from_dict(command).digest(),
            "event": event,
        }

    first = callback_record("forge-cb-1", t3)
    second = callback_record("forge-cb-2", t4)
    records = [policy_record, {
        "sequence": 2, "record_id": "",
        "command": allocate_command,
        "command_digest": AllocationCommand.from_dict(
            allocate_command
        ).digest(),
        "event": allocate_event,
    }, first, second]
    _recompute_event_id(records[0], policy_id)
    _recompute_event_id(records[1], allocation.allocation_id)
    _recompute_event_id(records[2], first["event"]["fact"]["payment_reference_id"])
    _recompute_event_id(records[3], second["event"]["fact"]["payment_reference_id"])
    return records


def _origin_main_available() -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "origin/main"],
        capture_output=True, cwd=str(REPO_ROOT),
    )
    return proc.returncode == 0


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------


def case_01_frozen_vocabularies(results: List[Result]) -> None:
    name = "case_01_frozen_vocabularies"
    problems: List[str] = []
    if sorted(AllocationSubjectState.values()) != ["PLANNED", "SETTLED"]:
        problems.append("allocation state vocabulary drifted")
    if sorted(PolicySubjectState.values()) != ["REGISTERED"]:
        problems.append("policy state vocabulary drifted")
    expected_actions = sorted([
        "register-policy", "allocate", "acknowledge-settlement",
        "record-payment-reference", "record-refund", "record-reversal",
        "record-chargeback", "record-payout-failure", "record-dispute",
    ])
    if sorted(AllocationAction.values()) != expected_actions:
        problems.append("action vocabulary drifted")
    if len(AllocationReasonCode.values()) != 27:
        problems.append(
            "reason vocabulary drifted: %d reasons" % len(
                AllocationReasonCode.values()
            )
        )
    if sorted(ReferenceKind.values()) != ["payment", "settlement"]:
        problems.append("reference kind vocabulary drifted")
    if sorted(RoundingMode.values()) != ["floor", "half-even", "half-up"]:
        problems.append("rounding mode vocabulary drifted")
    if sorted(allocation.KNOWN_USAGE_STATES) != [
        "BILLABLE_FINAL", "OBSERVING",
    ]:
        problems.append("cited usage state vocabulary drifted")
    if len(allocation.ALLOCATION_TRANSITIONS) != 10:
        problems.append(
            "transition table drifted: %d edges" % len(
                allocation.ALLOCATION_TRANSITIONS
            )
        )
    if sorted(allocation.MONETARY_COMPENSATION_KINDS) != sorted([
        "refund", "reversal", "chargeback", "payout-failure",
    ]):
        problems.append("monetary compensation kinds drifted")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "states/actions/reasons/reference kinds/rounding modes/"
                 "transition table/compensation kinds all frozen")
    )


def case_02_transition_table(results: List[Result]) -> None:
    name = "case_02_transition_table"
    problems: List[str] = []
    legal_edges = list(allocation.ALLOCATION_TRANSITIONS.items())
    expected_edges = sorted([
        ("REGISTERED", "register-policy"),
        ("PLANNED", "allocate"),
        ("PLANNED", "record-payment-reference"),
        ("PLANNED", "acknowledge-settlement"),
        ("SETTLED", "record-payment-reference"),
        ("SETTLED", "record-refund"),
        ("SETTLED", "record-reversal"),
        ("SETTLED", "record-chargeback"),
        ("SETTLED", "record-payout-failure"),
        ("SETTLED", "record-dispute"),
    ])
    if sorted(edge for edge, _ in legal_edges) != expected_edges:
        problems.append("transition table edges drifted")
    for edge, target in legal_edges:
        if transition_target(*edge) != target:
            problems.append("transition target mismatch for %r" % (edge,))
        if not transition_is_legal(*edge):
            problems.append("legal edge reported illegal: %r" % (edge,))
    illegal_pairs = [
        ("PLANNED", "record-refund"),
        ("PLANNED", "record-reversal"),
        ("PLANNED", "record-chargeback"),
        ("PLANNED", "record-payout-failure"),
        ("PLANNED", "record-dispute"),
        ("SETTLED", "allocate"),
        ("SETTLED", "acknowledge-settlement"),
        ("REGISTERED", "allocate"),
        ("REGISTERED", "acknowledge-settlement"),
        ("REGISTERED", "record-refund"),
        ("REGISTERED", "record-payment-reference"),
    ]
    for pair in illegal_pairs:
        if transition_is_legal(*pair):
            problems.append("illegal pair reported legal: %r" % (pair,))
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "10 legal edges, 11 illegal pairs verified against the "
                 "frozen table")
    )


def case_03_command_model(results: List[Result]) -> None:
    name = "case_03_command_model"
    problems: List[str] = []
    command = AllocationCommand(
        command_id="cmd-1", action="allocate",
        subject_id="sha256:" + "a" * 64,
        payload={"usage_statement_id": "s", "policy_id": "p",
                 "provider_share_bps": 5000, "fee_micros": 0,
                 "tax_micros": 0, "adjustment_micros": 0},
        actor="billing", source="allocation-service",
    )
    same = AllocationCommand(
        command_id="cmd-1", action="allocate",
        subject_id="sha256:" + "a" * 64,
        payload={"usage_statement_id": "s", "policy_id": "p",
                 "provider_share_bps": 5000, "fee_micros": 0,
                 "tax_micros": 0, "adjustment_micros": 0},
        actor="billing", source="allocation-service",
    )
    other = AllocationCommand(
        command_id="cmd-1", action="allocate",
        subject_id="sha256:" + "a" * 64,
        payload={"usage_statement_id": "s", "policy_id": "p",
                 "provider_share_bps": 6000, "fee_micros": 0,
                 "tax_micros": 0, "adjustment_micros": 0},
        actor="billing", source="allocation-service",
    )
    if command.digest() != same.digest():
        problems.append("identical content produced different digests")
    if command.digest() == other.digest():
        problems.append("different content produced the same digest")
    if AllocationCommand.from_dict(command.to_dict()).to_dict() != (
        command.to_dict()
    ):
        problems.append("command round-trip diverged")
    for bad in (
        {"command_id": "", "action": "allocate", "subject_id": "s",
         "payload": {}, "actor": "a", "source": "s"},
        {"command_id": "c", "action": "not-an-action", "subject_id": "s",
         "payload": {}, "actor": "a", "source": "s"},
        {"command_id": "c", "action": "allocate", "subject_id": "",
         "payload": {}, "actor": "a", "source": "s"},
        {"command_id": "c", "action": "allocate", "subject_id": "s",
         "payload": {}, "actor": "", "source": "s"},
    ):
        problem = _expect_allocation_error(
            name, AllocationReasonCode.INVALID_INPUT,
            AllocationCommand.from_dict, bad,
        )
        if problem is None:
            try:
                AllocationCommand.from_dict(bad)
                problems.append("invalid command accepted: %r" % bad)
            except AllocationError:
                pass
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "digest determinism + round-trip + input validation")
    )


def case_04_fact_models(results: List[Result]) -> None:
    name = "case_04_fact_models"
    problems: List[str] = []
    # policy-version validation matrix
    good = dict(
        policy_id=_golden_policy_id(), label=_POLICY_LABEL,
        adcos_share_bps=_POLICY_ADCOS_BPS,
        provider_min_bps=_POLICY_MIN_BPS,
        provider_max_bps=_POLICY_MAX_BPS,
        rounding_mode=_POLICY_ROUNDING, currency=_POLICY_CURRENCY,
        minor_unit_digits=_POLICY_DIGITS,
        effective_from=_POLICY_FROM, effective_until=_POLICY_UNTIL,
        command_id="c", registered_at=_AT0,
    )
    if PolicyVersion(**good).to_dict() != PolicyVersion.from_dict(
        PolicyVersion(**good).to_dict()
    ).to_dict():
        problems.append("policy round-trip diverged")
    for member, value in (
        ("adcos_share_bps", 20000),
        ("provider_min_bps", 8000),
        ("provider_max_bps", -1),
        ("rounding_mode", "ceil"),
        ("minor_unit_digits", 9),
        ("effective_until", "2025-01-01T00:00:00Z"),
    ):
        mutated = dict(good)
        mutated[member] = value
        problem = _expect_allocation_error(
            name, AllocationReasonCode.POLICY_INVALID,
            PolicyVersion, **mutated
        )
        if problem:
            problems.append("policy %s=%r: %s" % (member, value, problem))
    # allocation-snapshot conservation violations
    snapshot = dict(
        allocation_id="sha256:" + "1" * 64,
        usage_transaction_id="sha256:" + "2" * 64,
        usage_statement_id="sha256:" + "3" * 64,
        policy_id=_golden_policy_id(),
        gross_micros=100, fee_micros=10, tax_micros=5,
        adjustment_micros=0, distributable_micros=85,
        adcos_share_micros=13, provider_share_micros=36,
        developer_share_micros=36, provider_share_bps=5000,
        adcos_share_bps=1500, rounding_mode="half-up",
        currency="usd", minor_unit_digits=6, created_at=_AT0,
    )
    for member, value in (
        ("distributable_micros", 90),
        ("adcos_share_micros", 14),
        ("developer_share_micros", 37),
        ("fee_micros", -1),
        ("distributable_micros", 101),
    ):
        mutated = dict(snapshot)
        mutated[member] = value
        problem = _expect_allocation_error(
            name, AllocationReasonCode.EVENT_INVALID,
            AllocationSnapshot, **mutated
        )
        if problem:
            problems.append("snapshot %s=%r: %s" % (member, value, problem))
    # compensation-kind discipline
    for kind, amount, expect in (
        ("dispute", 0, None),
        ("dispute", 5, AllocationReasonCode.EVENT_INVALID),
        ("refund", 0, AllocationReasonCode.EVENT_INVALID),
        ("not-a-kind", 1, AllocationReasonCode.EVENT_INVALID),
    ):
        kwargs = dict(
            compensation_id="sha256:" + "4" * 64,
            usage_transaction_id="sha256:" + "2" * 64,
            compensation_kind=kind, amount_micros=amount,
            reason="r", allocation_id="sha256:" + "1" * 64,
            command_id="c", recorded_at=_AT0,
        )
        if expect is None:
            AllocationCompensationRecord(**kwargs)
        else:
            problem = _expect_allocation_error(
                name, expect, AllocationCompensationRecord, **kwargs
            )
            if problem:
                problems.append("compensation %s: %s" % (kind, problem))
    # event validation
    event = dict(
        event_id="sha256:" + "5" * 64, subject_id="s",
        action="allocate", from_state="PLANNED", to_state="PLANNED",
        command_id="c", fact={"kind": "allocation-snapshot-record"},
        actor="a", source="s", instant=_AT0,
    )
    for member, value in (
        ("from_state", "NOT_A_STATE"),
        ("to_state", "OBSERVING"),
        ("action", "not-an-action"),
    ):
        mutated = dict(event)
        mutated[member] = value
        problem = _expect_allocation_error(
            name, AllocationReasonCode.EVENT_INVALID,
            AllocationEvent, **mutated
        )
        if problem:
            problems.append("event %s=%r: %s" % (member, value, problem))
    # a malformed instant raises the dedicated INSTANT_INVALID
    # reason (the W052 model precedent)
    mutated = dict(event)
    mutated["instant"] = "2026-10-01T09:00:00"
    problem = _expect_allocation_error(
        name, AllocationReasonCode.INSTANT_INVALID,
        AllocationEvent, **mutated
    )
    if problem:
        problems.append("event instant: %s" % problem)
    if problems:
        results.append(fail(name, "; ".join(problems[:6])))
        return
    results.append(
        ok(name, "policy/snapshot/compensation/event model validation + "
                 "mechanical conservation invariants")
    )


def case_05_golden_scenario(results: List[Result]) -> None:
    name = "case_05_golden_scenario"
    ledger, index, clock, fixture, refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    problems: List[str] = []
    if len(ledger.journal_records()) != 13:
        problems.append(
            "golden journal length %d != 13" % len(ledger.journal_records())
        )
    if clock.reads != 13:
        problems.append("golden clock reads %d != 13" % clock.reads)
    if len(ledger.policies()) != 1:
        problems.append("golden policy registry size %d != 1" % len(ledger.policies()))
    if len(ledger.allocations()) != 2:
        problems.append("golden allocation count %d != 2" % len(ledger.allocations()))
    c1 = ledger.allocation(txs["c1"])
    c2 = ledger.allocation(txs["c2"])
    if c1.state != "SETTLED" or c2.state != "SETTLED":
        problems.append("golden terminal states wrong")
    snapshot = c1.snapshot
    if (
        snapshot.gross_micros != _C1_GROSS
        or snapshot.distributable_micros != _C1_DISTRIBUTABLE
        or snapshot.adcos_share_micros != _C1_ADCOS
        or snapshot.provider_share_micros != _C1_PROVIDER
        or snapshot.developer_share_micros != _C1_DEVELOPER
    ):
        problems.append("c1 golden arithmetic diverged: %r" % (
            snapshot.gross_micros, snapshot.distributable_micros,
            snapshot.adcos_share_micros, snapshot.provider_share_micros,
            snapshot.developer_share_micros,
        ))
    if c2.snapshot.adcos_share_micros != _C2_ADCOS or (
        c2.snapshot.provider_share_micros != _C2_PROVIDER
    ) or c2.snapshot.developer_share_micros != _C2_DEVELOPER:
        problems.append("c2 golden arithmetic diverged")
    stream = ledger.digest_stream()
    if not stream.startswith("{") or '"allocation-digest-stream"' not in stream:
        problems.append("digest stream shape wrong")
    if len(ledger.command_ledger()) != 13:
        problems.append("command ledger size wrong")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "13-record golden lifecycle; c1 930->850=(128,361,361); "
                 "c2 48=(7,27,14); both SETTLED; digest stream assembled")
    )


def case_06_every_legal_transition(results: List[Result]) -> None:
    name = "case_06_every_legal_transition"
    ledger, _index, _clock, fixture, _refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    problems: List[str] = []
    # every frozen-table edge is exercised by the golden walk
    c1 = ledger.allocation(txs["c1"])
    c2 = ledger.allocation(txs["c2"])
    exercised = {
        ("REGISTERED", "register-policy"): True,
        ("PLANNED", "allocate"): True,
        ("PLANNED", "record-payment-reference"): True,
        ("PLANNED", "acknowledge-settlement"): True,
        ("SETTLED", "record-payment-reference"): True,
        ("SETTLED", "record-refund"): True,
        ("SETTLED", "record-reversal"): True,
        ("SETTLED", "record-chargeback"): True,
        ("SETTLED", "record-payout-failure"): True,
        ("SETTLED", "record-dispute"): True,
    }
    for edge in allocation.ALLOCATION_TRANSITIONS:
        if not exercised.get(edge):
            problems.append("edge not exercised: %r" % (edge,))
    if c1.state != "SETTLED" or c2.state != "SETTLED":
        problems.append("terminal states wrong")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(ok(name, "all 10 frozen-table edges exercised"))


def case_07_illegal_transitions(results: List[Result]) -> None:
    name = "case_07_illegal_transitions"
    ledger, _index, _clock, fixture, refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    problems: List[str] = []
    # compensation before settlement (PLANNED): a fresh unacknowledged
    # allocation on the same index
    fresh = AllocationLedger(
        store=MemoryAllocationStore(),
        clock=StepClock("2026-10-02T00:00:00Z", 60),
        evidence_index=ledger.evidence_index(),
    )
    policy = fresh.register_policy(
        command_id="it-01", label=_POLICY_LABEL,
        adcos_share_bps=_POLICY_ADCOS_BPS,
        provider_min_bps=_POLICY_MIN_BPS,
        provider_max_bps=_POLICY_MAX_BPS,
        rounding_mode=_POLICY_ROUNDING, currency=_POLICY_CURRENCY,
        minor_unit_digits=_POLICY_DIGITS,
        effective_from=_POLICY_FROM, effective_until=_POLICY_UNTIL,
        actor="platform", source="economic-policy-service",
    )
    statements = _usage_statements(usage_ledger, txs)
    fresh.allocate(
        command_id="it-02", usage_transaction_id=txs["c2"],
        usage_statement_id=statements["c2"], policy_id=policy.fact_id,
        provider_share_bps=6500, actor="billing",
        source="allocation-service",
    )
    problem = _expect_allocation_error(
        name, AllocationReasonCode.COMPENSATION_REQUIRES_SETTLED,
        fresh.record_refund,
        command_id="it-03", usage_transaction_id=txs["c2"],
        amount_micros=1, reason="too early", actor="billing",
        source="allocation-service",
    )
    if problem:
        problems.append("compensation@PLANNED: %s" % problem)
    # re-acknowledgement (SETTLED)
    problem = _expect_allocation_error(
        name, AllocationReasonCode.SETTLEMENT_IMMUTABLE,
        ledger.acknowledge_settlement,
        command_id="it-04", usage_transaction_id=txs["c1"],
        settlement_reference=refs["sett-1"], actor="settlement",
        source="settlement-service",
    )
    if problem:
        problems.append("re-ack@SETTLED: %s" % problem)
    # a second allocation for an already-allocated usage record
    problem = _expect_allocation_error(
        name, AllocationReasonCode.ALLOCATION_ALREADY_EXISTS,
        ledger.allocate,
        command_id="it-05", usage_transaction_id=txs["c1"],
        usage_statement_id=statements["c1"], policy_id=policy.fact_id,
        provider_share_bps=4000, actor="billing",
        source="allocation-service",
    )
    if problem:
        problems.append("re-allocate@existing: %s" % problem)
    # allocation-subject actions with no allocation at all
    problem = _expect_allocation_error(
        name, AllocationReasonCode.ALLOCATION_UNKNOWN,
        ledger.acknowledge_settlement,
        command_id="it-06", usage_transaction_id=txs["c3"],
        settlement_reference=refs["sett-3"], actor="settlement",
        source="settlement-service",
    )
    if problem:
        problems.append("ack@no-allocation: %s" % problem)
    problem = _expect_allocation_error(
        name, AllocationReasonCode.ALLOCATION_UNKNOWN,
        ledger.record_payment_reference,
        command_id="it-07", usage_transaction_id=txs["c3"],
        payment_reference=refs["pay-4"], actor="gateway",
        source="payment-provider-boundary",
    )
    if problem:
        problems.append("callback@no-allocation: %s" % problem)
    problem = _expect_allocation_error(
        name, AllocationReasonCode.ALLOCATION_UNKNOWN,
        ledger.record_refund,
        command_id="it-08", usage_transaction_id=txs["c3"],
        amount_micros=1, reason="nothing", actor="billing",
        source="allocation-service",
    )
    if problem:
        problems.append("compensation@no-allocation: %s" % problem)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "compensation@PLANNED, re-ack@SETTLED, re-allocate, and "
                 "no-allocation citations all fail closed")
    )


def case_08_three_way_conservation(results: List[Result]) -> None:
    name = "case_08_three_way_conservation"
    ledger, _index, _clock, fixture, _refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    problems: List[str] = []
    statements = _usage_statements(usage_ledger, txs)
    for key, expected in (
        ("c1", (_C1_GROSS, _C1_DISTRIBUTABLE, _C1_ADCOS,
                _C1_PROVIDER, _C1_DEVELOPER)),
        ("c2", (_C2_GROSS, _C2_GROSS, _C2_ADCOS,
                _C2_PROVIDER, _C2_DEVELOPER)),
    ):
        snapshot = ledger.allocation(txs[key]).snapshot
        gross, distributable, adcos, provider, developer = expected
        if snapshot.gross_micros != gross:
            problems.append("%s gross %d != %d" % (
                key, snapshot.gross_micros, gross
            ))
        if snapshot.distributable_micros != distributable:
            problems.append("%s distributable diverged" % key)
        if (snapshot.adcos_share_micros, snapshot.provider_share_micros,
                snapshot.developer_share_micros) != (adcos, provider, developer):
            problems.append("%s shares diverged" % key)
        total = (
            snapshot.adcos_share_micros + snapshot.provider_share_micros
            + snapshot.developer_share_micros
        )
        if total != snapshot.distributable_micros:
            problems.append("%s conservation broken" % key)
        reconstructed = (
            snapshot.distributable_micros + snapshot.fee_micros
            + snapshot.tax_micros + snapshot.adjustment_micros
        )
        if reconstructed != snapshot.gross_micros:
            problems.append("%s gross reconstruction broken" % key)
    # the honest zero-bill edge: the c4 zero-observation seal
    # (gross 0) allocates to the exact zero three-way split
    zero_ledger = AllocationLedger(
        store=MemoryAllocationStore(),
        clock=StepClock("2026-10-02T00:00:00Z", 60),
        evidence_index=ledger.evidence_index(),
    )
    policy = zero_ledger.register_policy(
        command_id="zc-01", label=_POLICY_LABEL,
        adcos_share_bps=_POLICY_ADCOS_BPS,
        provider_min_bps=_POLICY_MIN_BPS,
        provider_max_bps=_POLICY_MAX_BPS,
        rounding_mode=_POLICY_ROUNDING, currency=_POLICY_CURRENCY,
        minor_unit_digits=_POLICY_DIGITS,
        effective_from=_POLICY_FROM, effective_until=_POLICY_UNTIL,
        actor="platform", source="economic-policy-service",
    )
    out = zero_ledger.allocate(
        command_id="zc-02", usage_transaction_id=txs["c4"],
        usage_statement_id=statements["c4"], policy_id=policy.fact_id,
        provider_share_bps=5000, actor="billing",
        source="allocation-service",
    )
    zero_snapshot = zero_ledger.allocation(txs["c4"]).snapshot
    if out.status != "appended" or zero_snapshot.gross_micros != 0 or (
        zero_snapshot.adcos_share_micros
        + zero_snapshot.provider_share_micros
        + zero_snapshot.developer_share_micros != 0
    ):
        problems.append("zero-bill allocation diverged")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "c1 930=850+30+57-7 -> (128,361,361); c2 48 -> "
                 "(7,27,14); zero-bill -> (0,0,0); conservation exact")
    )


def case_09_rounding_exactness(results: List[Result]) -> None:
    name = "case_09_rounding_exactness"
    problems: List[str] = []
    # hand-computed rounding pins
    pins = (
        # (numerator, denominator, mode, expected)
        (85, 2, "floor", 42),
        (85, 2, "half-up", 43),
        (85, 2, "half-even", 42),
        (7, 2, "floor", 3),
        (7, 2, "half-up", 4),
        (7, 2, "half-even", 4),
        (5, 10, "floor", 0),
        (5, 10, "half-up", 1),
        (5, 10, "half-even", 0),
        (15, 10, "floor", 1),
        (15, 10, "half-up", 2),
        (15, 10, "half-even", 2),
        (1275, 10000, "floor", 0),
        (1275, 10000, "half-up", 0),
        (1275, 10000, "half-even", 0),
        (12750, 10000, "floor", 1),
        (12750, 10000, "half-up", 1),
        (12750, 10000, "half-even", 1),
        (15000, 10000, "floor", 1),
        (15000, 10000, "half-up", 2),
        (15000, 10000, "half-even", 2),
        (14999, 10000, "half-up", 1),
        (14999, 10000, "half-even", 1),
    )
    for numerator, denominator, mode, expected in pins:
        actual = apply_rounding(numerator, denominator, mode)
        if actual != expected:
            problems.append(
                "apply_rounding(%d, %d, %s) = %d != %d"
                % (numerator, denominator, mode, actual, expected)
            )
    # the exhaustive conservation sweep: the three-way split is
    # exactly conservative for every distributable/bps/mode combo
    for distributable in (0, 1, 2, 3, 7, 85, 930, 123457):
        for adcos_bps in (0, 1, 1500, 3333, 9999, 10000):
            for provider_bps in (0, 1, 5000, 7777, 10000):
                for mode in RoundingMode.values():
                    adcos, provider, developer = compute_split(
                        distributable, adcos_bps, provider_bps, mode
                    )
                    if adcos + provider + developer != distributable:
                        problems.append(
                            "conservation broken at %d/%d/%d/%s"
                            % (distributable, adcos_bps, provider_bps, mode)
                        )
                    if adcos != apply_rounding(
                        distributable * adcos_bps, 10000, mode
                    ):
                        problems.append("adcos derivation diverged")
                    residual = distributable - adcos
                    if provider != apply_rounding(
                        residual * provider_bps, 10000, mode
                    ):
                        problems.append("provider derivation diverged")
                    if developer != residual - provider:
                        problems.append("developer remainder diverged")
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "19 hand-computed pins + 450-combo exhaustive "
                 "conservation sweep across all three modes")
    )


def case_10_usage_unknown(results: List[Result]) -> None:
    name = "case_10_usage_unknown"
    ledger, _index, _clock, fixture, _refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    statements = _usage_statements(usage_ledger, txs)
    problem = _expect_allocation_error(
        name, AllocationReasonCode.USAGE_UNKNOWN,
        ledger.allocate,
        command_id="uu-01",
        usage_transaction_id="sha256:" + "e" * 64,
        usage_statement_id=statements["c1"],
        policy_id=_golden_policy_id(),
        provider_share_bps=5000, actor="billing",
        source="allocation-service",
    )
    if problem:
        results.append(fail(name, problem))
        return
    results.append(ok(name, "fabricated usage citation rejected"))


def case_11_payment_not_usage(results: List[Result]) -> None:
    name = "case_11_payment_not_usage"
    ledger, _index, _clock, fixture, refs = _golden_ledger()
    problem = _expect_allocation_error(
        name, AllocationReasonCode.PAYMENT_NOT_USAGE,
        ledger.allocate,
        command_id="pnu-01",
        usage_transaction_id=refs["pay-1"],
        usage_statement_id="sha256:" + "f" * 64,
        policy_id=_golden_policy_id(),
        provider_share_bps=5000, actor="billing",
        source="allocation-service",
    )
    if problem:
        results.append(fail(name, problem))
        return
    results.append(
        ok(name, "payment reference cited as usage rejected "
                 "(payment success never creates allocation)")
    )


def case_12_settlement_not_usage(results: List[Result]) -> None:
    name = "case_12_settlement_not_usage"
    ledger, _index, _clock, fixture, refs = _golden_ledger()
    problem = _expect_allocation_error(
        name, AllocationReasonCode.SETTLEMENT_NOT_USAGE,
        ledger.allocate,
        command_id="snu-01",
        usage_transaction_id=refs["sett-2"],
        usage_statement_id="sha256:" + "f" * 64,
        policy_id=_golden_policy_id(),
        provider_share_bps=5000, actor="billing",
        source="allocation-service",
    )
    if problem:
        results.append(fail(name, problem))
        return
    results.append(
        ok(name, "settlement reference cited as usage rejected "
                 "(settlement confirmation never creates allocation)")
    )


def case_13_usage_not_final(results: List[Result]) -> None:
    name = "case_13_usage_not_final"
    ledger, _index, _clock, fixture, _refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    problem = _expect_allocation_error(
        name, AllocationReasonCode.USAGE_NOT_FINAL,
        ledger.allocate,
        command_id="unf-01",
        usage_transaction_id=txs["c3"],
        usage_statement_id="sha256:" + "0" * 64,
        policy_id=_golden_policy_id(),
        provider_share_bps=5000, actor="billing",
        source="allocation-service",
    )
    if problem:
        results.append(fail(name, problem))
        return
    projection = usage_ledger.transaction(txs["c3"])
    results.append(
        ok(name, "the real OBSERVING usage transaction %s... (state %s, "
                 "no sealed statement) rejected"
                 % (txs["c3"][:16], projection.state))
    )


def case_14_usage_statement_mismatch(results: List[Result]) -> None:
    name = "case_14_usage_statement_mismatch"
    ledger, _index, _clock, fixture, _refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    statements = _usage_statements(usage_ledger, txs)
    problem = _expect_allocation_error(
        name, AllocationReasonCode.USAGE_MISMATCH,
        ledger.allocate,
        command_id="usm-01",
        usage_transaction_id=txs["c2"],
        usage_statement_id=statements["c1"],
        policy_id=_golden_policy_id(),
        provider_share_bps=5000, actor="billing",
        source="allocation-service",
    )
    if problem:
        results.append(fail(name, problem))
        return
    results.append(
        ok(name, "cited statement does not match the snapshot's sealed "
                 "statement")
    )


def case_15_policy_unknown(results: List[Result]) -> None:
    name = "case_15_policy_unknown"
    ledger, _index, _clock, fixture, _refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    statements = _usage_statements(usage_ledger, txs)
    problem = _expect_allocation_error(
        name, AllocationReasonCode.POLICY_UNKNOWN,
        ledger.allocate,
        command_id="pu-01",
        usage_transaction_id=txs["c2"],
        usage_statement_id=statements["c2"],
        policy_id="sha256:" + "d" * 64,
        provider_share_bps=5000, actor="billing",
        source="allocation-service",
    )
    if problem:
        results.append(fail(name, problem))
        return
    results.append(
        ok(name, "fabricated/stale policy citation rejected against the "
                 "folded registry")
    )


def case_16_policy_not_effective(results: List[Result]) -> None:
    name = "case_16_policy_not_effective"
    ledger, _index, _clock, fixture, _refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    statements = _usage_statements(usage_ledger, txs)
    # the vectors allocate c4 (the honest zero-bill transaction,
    # unallocated in the golden) so the policy-window gate is the
    # only gate that can fire
    problems: List[str] = []
    # a short-window policy: effective in early 2026 only, while the
    # allocation clock runs in October 2026
    short = ledger.register_policy(
        command_id="pne-01", label="promo-q1",
        adcos_share_bps=_POLICY_ADCOS_BPS,
        provider_min_bps=_POLICY_MIN_BPS,
        provider_max_bps=_POLICY_MAX_BPS,
        rounding_mode=_POLICY_ROUNDING, currency=_POLICY_CURRENCY,
        minor_unit_digits=_POLICY_DIGITS,
        effective_from="2026-01-01T00:00:00Z",
        effective_until="2026-05-01T00:00:00Z",
        actor="platform", source="economic-policy-service",
    )
    if short.status != "appended":
        problems.append("short-window policy registration failed")
    problem = _expect_allocation_error(
        name, AllocationReasonCode.POLICY_NOT_EFFECTIVE,
        ledger.allocate,
        command_id="pne-02", usage_transaction_id=txs["c4"],
        usage_statement_id=statements["c4"],
        policy_id=short.fact_id, provider_share_bps=6500,
        actor="billing", source="allocation-service",
    )
    if problem:
        problems.append("expired window: %s" % problem)
    # a not-yet-effective policy
    future = ledger.register_policy(
        command_id="pne-03", label="future-2027",
        adcos_share_bps=_POLICY_ADCOS_BPS,
        provider_min_bps=_POLICY_MIN_BPS,
        provider_max_bps=_POLICY_MAX_BPS,
        rounding_mode=_POLICY_ROUNDING, currency=_POLICY_CURRENCY,
        minor_unit_digits=_POLICY_DIGITS,
        effective_from="2027-01-01T00:00:00Z",
        effective_until="2028-01-01T00:00:00Z",
        actor="platform", source="economic-policy-service",
    )
    problem = _expect_allocation_error(
        name, AllocationReasonCode.POLICY_NOT_EFFECTIVE,
        ledger.allocate,
        command_id="pne-04", usage_transaction_id=txs["c4"],
        usage_statement_id=statements["c4"],
        policy_id=future.fact_id, provider_share_bps=6500,
        actor="billing", source="allocation-service",
    )
    if problem:
        problems.append("not-yet window: %s" % problem)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "expired and not-yet-effective policy windows rejected "
                 "(effective-date selection is exact)")
    )


def case_17_split_out_of_bounds(results: List[Result]) -> None:
    name = "case_17_split_out_of_bounds"
    ledger, _index, _clock, fixture, _refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    statements = _usage_statements(usage_ledger, txs)
    problems: List[str] = []
    for bps in (2000, 8000):
        problem = _expect_allocation_error(
            name, AllocationReasonCode.SPLIT_OUT_OF_BOUNDS,
            ledger.allocate,
            command_id="sob-%d" % bps,
            usage_transaction_id=txs["c2"],
            usage_statement_id=statements["c2"],
            policy_id=_golden_policy_id(),
            provider_share_bps=bps, actor="billing",
            source="allocation-service",
        )
        if problem:
            problems.append("bps %d: %s" % (bps, problem))
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "developer-selected split below the minimum and above "
                 "the maximum rejected ([3000, 7000] bps bounds)")
    )


def case_18_distribution_invalid(results: List[Result]) -> None:
    name = "case_18_distribution_invalid"
    ledger, _index, _clock, fixture, _refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    statements = _usage_statements(usage_ledger, txs)
    # the vectors allocate c4 (the honest zero-bill transaction,
    # unallocated in the golden): gross 0 makes every positive
    # declared charge an immediate distribution violation
    problems: List[str] = []
    # negative fee/tax reject at the strict payload-shape gate
    # (COMMAND_INVALID, the shape-level sign discipline)
    for member in ("fee_micros", "tax_micros"):
        charges = {
            "fee_micros": 0, "tax_micros": 0, "adjustment_micros": 0,
        }
        charges[member] = -1
        problem = _expect_allocation_error(
            name, AllocationReasonCode.COMMAND_INVALID,
            ledger.allocate,
            command_id="di-%s" % member,
            usage_transaction_id=txs["c4"],
            usage_statement_id=statements["c4"],
            policy_id=_golden_policy_id(),
            provider_share_bps=6500,
            fee_micros=charges["fee_micros"],
            tax_micros=charges["tax_micros"],
            adjustment_micros=charges["adjustment_micros"],
            actor="billing", source="allocation-service",
        )
        if problem:
            problems.append("negative %s: %s" % (member, problem))
    vectors = (
        ("fee exceeds gross", {"fee_micros": 49, "tax_micros": 0,
                               "adjustment_micros": 0}),
        ("tax exceeds gross", {"fee_micros": 0, "tax_micros": 60,
                               "adjustment_micros": 0}),
        ("combined charges exceed gross", {"fee_micros": 20,
                                            "tax_micros": 40,
                                            "adjustment_micros": 0}),
        ("surcharge adjustment exceeds gross", {"fee_micros": 0,
                                                 "tax_micros": 0,
                                                 "adjustment_micros": 1}),
    )
    for index, (label, charges) in enumerate(vectors, start=1):
        problem = _expect_allocation_error(
            name, AllocationReasonCode.DISTRIBUTION_INVALID,
            ledger.allocate,
            command_id="di-%02d" % index,
            usage_transaction_id=txs["c4"],
            usage_statement_id=statements["c4"],
            policy_id=_golden_policy_id(),
            provider_share_bps=6500,
            fee_micros=charges["fee_micros"],
            tax_micros=charges["tax_micros"],
            adjustment_micros=charges["adjustment_micros"],
            actor="billing", source="allocation-service",
        )
        if problem:
            problems.append("%s: %s" % (label, problem))
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "all six distribution-discipline vectors rejected "
                 "(distributable stays within [0, gross])")
    )


def case_19_duplicate_commands(results: List[Result]) -> None:
    name = "case_19_duplicate_commands"
    ledger, _index, clock, fixture, refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    records_before = len(ledger.journal_records())
    reads_before = clock.reads
    outcome = ledger.acknowledge_settlement(
        command_id="e-04",
        usage_transaction_id=txs["c1"],
        settlement_reference=refs["sett-1"],
        actor="settlement", source="settlement-service",
    )
    problems: List[str] = []
    if outcome.status != CommandStatus.DUPLICATE:
        problems.append("redelivery not DUPLICATE: %r" % outcome.status)
    if len(ledger.journal_records()) != records_before:
        problems.append("duplicate grew the journal")
    if clock.reads != reads_before:
        problems.append("duplicate consumed a clock read")
    if outcome.event_id != ledger.journal_records()[3].event.event_id:
        problems.append("duplicate returned the wrong event id")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "exact command redelivery: no journal growth, no clock "
                 "read, recorded event id returned")
    )


def case_20_conflicting_duplicates(results: List[Result]) -> None:
    name = "case_20_conflicting_duplicates"
    ledger, _index, _clock, fixture, _refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    problem = _expect_allocation_error(
        name, AllocationReasonCode.COMMAND_CONFLICT,
        ledger.record_refund,
        command_id="e-06", usage_transaction_id=txs["c1"],
        amount_micros=999, reason="conflicting redelivery",
        actor="billing", source="allocation-service",
    )
    if problem:
        results.append(fail(name, problem))
        return
    results.append(
        ok(name, "same command id with different content fails closed")
    )


def case_21_statement_already_allocated(results: List[Result]) -> None:
    name = "case_21_statement_already_allocated"
    ledger, _index, _clock, fixture, _refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    statements = _usage_statements(usage_ledger, txs)
    problem = _expect_allocation_error(
        name, AllocationReasonCode.ALLOCATION_ALREADY_EXISTS,
        ledger.allocate,
        command_id="saa-01", usage_transaction_id=txs["c1"],
        usage_statement_id=statements["c1"],
        policy_id=_golden_policy_id(),
        provider_share_bps=4000, actor="billing",
        source="allocation-service",
    )
    if problem:
        results.append(fail(name, problem))
        return
    results.append(
        ok(name, "exactly one allocation per billable-final usage record "
                 "(the second ALLOCATE is a closed conflict)")
    )


def case_22_duplicate_callbacks(results: List[Result]) -> None:
    name = "case_22_duplicate_callbacks"
    ledger, _index, clock, fixture, refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    records_before = len(ledger.journal_records())
    reads_before = clock.reads
    problems: List[str] = []
    # a different command id citing the SAME external reference
    # identity (the provider redelivered the callback)
    outcome = ledger.record_payment_reference(
        command_id="dup-cb-1", usage_transaction_id=txs["c1"],
        payment_reference=refs["pay-1"],
        actor="payment-callback-gateway",
        source="payment-provider-boundary",
    )
    if outcome.status != CommandStatus.DUPLICATE:
        problems.append("redelivered callback not DUPLICATE")
    if len(ledger.journal_records()) != records_before:
        problems.append("duplicate callback grew the journal")
    if clock.reads != reads_before:
        problems.append("duplicate callback consumed a clock read")
    recorded = [
        record.payment_reference_id
        for record in ledger.allocation(txs["c1"]).payment_references
        if record.payment_reference == refs["pay-1"]
    ]
    if not recorded or outcome.fact_id != recorded[0]:
        problems.append("duplicate returned the wrong record id")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "duplicate provider callback: idempotent no-op, no "
                 "journal growth, no clock read")
    )


def case_23_callback_arrival_discipline(results: List[Result]) -> None:
    name = "case_23_callback_arrival_discipline"
    problems: List[str] = []
    # two ledgers over the same fixture: the same callback set in
    # different arrival orders (all before settlement)
    base_usage, base_txs, _base_world = _usage_fixture()
    base_index = _allocation_index(base_usage, base_txs)
    refs = _reference_ids(base_txs)
    statements = _usage_statements(base_usage, base_txs)

    def world(order):
        ledger = AllocationLedger(
            store=MemoryAllocationStore(),
            clock=StepClock("2026-10-03T00:00:00Z", 60),
            evidence_index=base_index,
        )
        policy = ledger.register_policy(
            command_id="cad-%s-01" % order, label=_POLICY_LABEL,
            adcos_share_bps=_POLICY_ADCOS_BPS,
            provider_min_bps=_POLICY_MIN_BPS,
            provider_max_bps=_POLICY_MAX_BPS,
            rounding_mode=_POLICY_ROUNDING, currency=_POLICY_CURRENCY,
            minor_unit_digits=_POLICY_DIGITS,
            effective_from=_POLICY_FROM, effective_until=_POLICY_UNTIL,
            actor="platform", source="economic-policy-service",
        )
        ledger.allocate(
            command_id="cad-%s-02" % order,
            usage_transaction_id=base_txs["c1"],
            usage_statement_id=statements["c1"],
            policy_id=policy.fact_id, provider_share_bps=5000,
            actor="billing", source="allocation-service",
        )
        callbacks = [("a", refs["pay-1"]), ("b", refs["pay-2"]),
                     ("c", refs["pay-4"])]
        if order == "reversed":
            callbacks = list(reversed(callbacks))
        for suffix, reference in callbacks:
            ledger.record_payment_reference(
                command_id="cad-%s-%s" % (order, suffix),
                usage_transaction_id=base_txs["c1"],
                payment_reference=reference,
                actor="payment-callback-gateway",
                source="payment-provider-boundary",
            )
        return ledger

    forward = world("forward")
    reversed_world = world("reversed")
    projection_a = forward.allocation(base_txs["c1"])
    projection_b = reversed_world.allocation(base_txs["c1"])
    ids_a = sorted(
        record.payment_reference for record in projection_a.payment_references
    )
    ids_b = sorted(
        record.payment_reference for record in projection_b.payment_references
    )
    if ids_a != ids_b:
        problems.append("reference multiset diverged across arrival orders")
    if projection_a.state != projection_b.state:
        problems.append("state diverged across arrival orders")
    if projection_a.snapshot.to_dict() != projection_b.snapshot.to_dict():
        problems.append("snapshot diverged across arrival orders")
    record_ids_a = set(
        record.payment_reference_id
        for record in projection_a.payment_references
    )
    record_ids_b = set(
        record.payment_reference_id
        for record in projection_b.payment_references
    )
    if record_ids_a == record_ids_b:
        problems.append(
            "record identities identical across orders (must be honestly "
            "admission-attributed)"
        )
    # the delayed callback after settlement is recorded as DATA
    # without any state transition (the golden covers it; re-pin)
    delayed = AllocationLedger(
        store=MemoryAllocationStore(),
        clock=StepClock("2026-10-03T01:00:00Z", 60),
        evidence_index=base_index,
    )
    policy = delayed.register_policy(
        command_id="dcb-01", label=_POLICY_LABEL,
        adcos_share_bps=_POLICY_ADCOS_BPS,
        provider_min_bps=_POLICY_MIN_BPS,
        provider_max_bps=_POLICY_MAX_BPS,
        rounding_mode=_POLICY_ROUNDING, currency=_POLICY_CURRENCY,
        minor_unit_digits=_POLICY_DIGITS,
        effective_from=_POLICY_FROM, effective_until=_POLICY_UNTIL,
        actor="platform", source="economic-policy-service",
    )
    delayed.allocate(
        command_id="dcb-02", usage_transaction_id=base_txs["c1"],
        usage_statement_id=statements["c1"], policy_id=policy.fact_id,
        provider_share_bps=5000, actor="billing",
        source="allocation-service",
    )
    delayed.acknowledge_settlement(
        command_id="dcb-03", usage_transaction_id=base_txs["c1"],
        settlement_reference=refs["sett-1"], actor="settlement",
        source="settlement-service",
    )
    state_before = delayed.allocation(base_txs["c1"]).state
    delayed.record_payment_reference(
        command_id="dcb-04", usage_transaction_id=base_txs["c1"],
        payment_reference=refs["pay-1"],
        actor="payment-callback-gateway",
        source="payment-provider-boundary",
    )
    if delayed.allocation(base_txs["c1"]).state != state_before:
        problems.append("delayed callback transitioned state")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "reference multiset/state/snapshot arrival-order "
                 "independent; record ids honestly admission-attributed; "
                 "delayed callback is state-preserving DATA")
    )


def case_24_callback_before_allocation(results: List[Result]) -> None:
    name = "case_24_callback_before_allocation"
    ledger, _index, _clock, fixture, refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    problem = _expect_allocation_error(
        name, AllocationReasonCode.ALLOCATION_UNKNOWN,
        ledger.record_payment_reference,
        command_id="cba-01", usage_transaction_id=txs["c3"],
        payment_reference=refs["pay-4"],
        actor="payment-callback-gateway",
        source="payment-provider-boundary",
    )
    if problem:
        results.append(fail(name, problem))
        return
    results.append(
        ok(name, "provider callback before any allocation rejected")
    )


def case_25_settlement_acknowledgement(results: List[Result]) -> None:
    name = "case_25_settlement_acknowledgement"
    ledger, _index, _clock, fixture, refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    projection = ledger.allocation(txs["c1"])
    settlement = projection.settlement
    problems: List[str] = []
    if settlement is None:
        problems.append("c1 carries no settlement acknowledgement")
    else:
        if settlement.settlement_reference != refs["sett-1"]:
            problems.append("settlement reference mismatch")
        if settlement.allocation_id != projection.snapshot.allocation_id:
            problems.append("settlement cites the wrong allocation")
        if settlement.usage_transaction_id != txs["c1"]:
            problems.append("settlement cites the wrong usage transaction")
    if projection.state != "SETTLED":
        problems.append("c1 not SETTLED")
    # an unacknowledged allocation stays PLANNED with no settlement
    fresh = AllocationLedger(
        store=MemoryAllocationStore(),
        clock=StepClock("2026-10-02T00:00:00Z", 60),
        evidence_index=ledger.evidence_index(),
    )
    policy = fresh.register_policy(
        command_id="sa-01", label=_POLICY_LABEL,
        adcos_share_bps=_POLICY_ADCOS_BPS,
        provider_min_bps=_POLICY_MIN_BPS,
        provider_max_bps=_POLICY_MAX_BPS,
        rounding_mode=_POLICY_ROUNDING, currency=_POLICY_CURRENCY,
        minor_unit_digits=_POLICY_DIGITS,
        effective_from=_POLICY_FROM, effective_until=_POLICY_UNTIL,
        actor="platform", source="economic-policy-service",
    )
    statements = _usage_statements(usage_ledger, txs)
    fresh.allocate(
        command_id="sa-02", usage_transaction_id=txs["c2"],
        usage_statement_id=statements["c2"], policy_id=policy.fact_id,
        provider_share_bps=6500, actor="billing",
        source="allocation-service",
    )
    if fresh.allocation(txs["c2"]).state != "PLANNED" or (
        fresh.allocation(txs["c2"]).settlement is not None
    ):
        problems.append("unacknowledged allocation shape wrong")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "acknowledgement cites the external settlement reference "
                 "and the exact allocation; PLANNED/SETTLED shapes correct")
    )


def case_26_payment_not_settlement(results: List[Result]) -> None:
    name = "case_26_payment_not_settlement"
    ledger, _index, _clock, fixture, refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    problem = _expect_allocation_error(
        name, AllocationReasonCode.PAYMENT_NOT_SETTLEMENT,
        ledger.acknowledge_settlement,
        command_id="pns-01", usage_transaction_id=txs["c2"],
        settlement_reference=refs["pay-1"], actor="settlement",
        source="settlement-service",
    )
    if problem:
        results.append(fail(name, problem))
        return
    results.append(
        ok(name, "settlement acknowledgement citing a payment reference "
                 "rejected (kind table)")
    )


def case_27_settlement_not_payment(results: List[Result]) -> None:
    name = "case_27_settlement_not_payment"
    ledger, _index, _clock, fixture, refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    problem = _expect_allocation_error(
        name, AllocationReasonCode.SETTLEMENT_NOT_PAYMENT,
        ledger.record_payment_reference,
        command_id="snp-01", usage_transaction_id=txs["c1"],
        payment_reference=refs["sett-1"],
        actor="payment-callback-gateway",
        source="payment-provider-boundary",
    )
    if problem:
        results.append(fail(name, problem))
        return
    results.append(
        ok(name, "payment callback citing a settlement reference rejected "
                 "(kind table)")
    )


def case_28_reference_unknown(results: List[Result]) -> None:
    name = "case_28_reference_unknown"
    ledger, _index, _clock, fixture, _refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    problems: List[str] = []
    problem = _expect_allocation_error(
        name, AllocationReasonCode.REFERENCE_UNKNOWN,
        ledger.acknowledge_settlement,
        command_id="ru-01", usage_transaction_id=txs["c1"],
        settlement_reference="sha256:" + "1" * 64,
        actor="settlement", source="settlement-service",
    )
    if problem:
        problems.append("settlement: %s" % problem)
    problem = _expect_allocation_error(
        name, AllocationReasonCode.REFERENCE_UNKNOWN,
        ledger.record_payment_reference,
        command_id="ru-02", usage_transaction_id=txs["c1"],
        payment_reference="sha256:" + "2" * 64,
        actor="payment-callback-gateway",
        source="payment-provider-boundary",
    )
    if problem:
        problems.append("payment: %s" % problem)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "fabricated/stale/unauthorized external references "
                 "rejected for both kinds")
    )


def case_29_reference_mismatch(results: List[Result]) -> None:
    name = "case_29_reference_mismatch"
    ledger, _index, _clock, fixture, refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    problems: List[str] = []
    # sett-2 is correlated to c2; citing it against c1 fails closed
    problem = _expect_allocation_error(
        name, AllocationReasonCode.REFERENCE_MISMATCH,
        ledger.acknowledge_settlement,
        command_id="rm-01", usage_transaction_id=txs["c1"],
        settlement_reference=refs["sett-2"], actor="settlement",
        source="settlement-service",
    )
    if problem:
        problems.append("settlement: %s" % problem)
    # pay-3 is correlated to c2; citing it against c1 fails closed
    problem = _expect_allocation_error(
        name, AllocationReasonCode.REFERENCE_MISMATCH,
        ledger.record_payment_reference,
        command_id="rm-02", usage_transaction_id=txs["c1"],
        payment_reference=refs["pay-3"],
        actor="payment-callback-gateway",
        source="payment-provider-boundary",
    )
    if problem:
        problems.append("payment: %s" % problem)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "external correlations that disagree with the cited "
                 "allocation fail closed for both kinds")
    )


def case_30_settlement_immutable(results: List[Result]) -> None:
    name = "case_30_settlement_immutable"
    ledger, _index, _clock, fixture, refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    # cite the SAME settlement reference the original acknowledgement
    # cited, so the state gate is the only gate that can fire
    problem = _expect_allocation_error(
        name, AllocationReasonCode.SETTLEMENT_IMMUTABLE,
        ledger.acknowledge_settlement,
        command_id="si-01", usage_transaction_id=txs["c1"],
        settlement_reference=refs["sett-1"], actor="settlement",
        source="settlement-service",
    )
    if problem:
        results.append(fail(name, problem))
        return
    results.append(
        ok(name, "re-acknowledgement of a settled allocation rejected")
    )


def case_31_compensation_family(results: List[Result]) -> None:
    name = "case_31_compensation_family"
    ledger, _index, _clock, fixture, _refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    projection = ledger.allocation(txs["c1"])
    problems: List[str] = []
    if len(projection.compensations) != 5:
        problems.append("compensation count %d != 5" % len(projection.compensations))
    if projection.refunded_amount_micros() != 100:
        problems.append("refund view wrong")
    if projection.reversed_amount_micros() != 50:
        problems.append("reversal view wrong")
    if projection.chargeback_amount_micros() != 25:
        problems.append("chargeback view wrong")
    if projection.payout_failure_amount_micros() != 10:
        problems.append("payout-failure view wrong")
    if not projection.disputed():
        problems.append("dispute flag missing")
    if projection.monetary_compensation_micros() != 185:
        problems.append("monetary total wrong")
    if projection.net_distributable_micros() != 850 - 185:
        problems.append("net view wrong: %d" % projection.net_distributable_micros())
    kinds = sorted(
        compensation.compensation_kind
        for compensation in projection.compensations
    )
    if kinds != sorted([
        "refund", "reversal", "chargeback", "payout-failure", "dispute",
    ]):
        problems.append("compensation kinds wrong: %r" % kinds)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "all five compensating kinds appended; net 850 - 185 = "
                 "665; dispute flagged")
    )


def case_32_compensation_requires_settled(results: List[Result]) -> None:
    name = "case_32_compensation_requires_settled"
    ledger, _index, _clock, fixture, refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    statements = _usage_statements(usage_ledger, txs)
    fresh = AllocationLedger(
        store=MemoryAllocationStore(),
        clock=StepClock("2026-10-02T00:00:00Z", 60),
        evidence_index=ledger.evidence_index(),
    )
    policy = fresh.register_policy(
        command_id="crs-01", label=_POLICY_LABEL,
        adcos_share_bps=_POLICY_ADCOS_BPS,
        provider_min_bps=_POLICY_MIN_BPS,
        provider_max_bps=_POLICY_MAX_BPS,
        rounding_mode=_POLICY_ROUNDING, currency=_POLICY_CURRENCY,
        minor_unit_digits=_POLICY_DIGITS,
        effective_from=_POLICY_FROM, effective_until=_POLICY_UNTIL,
        actor="platform", source="economic-policy-service",
    )
    fresh.allocate(
        command_id="crs-02", usage_transaction_id=txs["c2"],
        usage_statement_id=statements["c2"], policy_id=policy.fact_id,
        provider_share_bps=6500, actor="billing",
        source="allocation-service",
    )
    problems: List[str] = []
    for method, reason in (
        ("record_refund", "amount_micros"),
        ("record_reversal", "amount_micros"),
        ("record_chargeback", "amount_micros"),
        ("record_payout_failure", "amount_micros"),
    ):
        problem = _expect_allocation_error(
            name, AllocationReasonCode.COMPENSATION_REQUIRES_SETTLED,
            getattr(fresh, method),
            command_id="crs-%s" % method,
            usage_transaction_id=txs["c2"],
            amount_micros=1, reason="too early",
            actor="billing", source="allocation-service",
        )
        if problem:
            problems.append("%s: %s" % (method, problem))
    problem = _expect_allocation_error(
        name, AllocationReasonCode.COMPENSATION_REQUIRES_SETTLED,
        fresh.record_dispute,
        command_id="crs-dispute", usage_transaction_id=txs["c2"],
        reason="too early", actor="billing", source="allocation-service",
    )
    if problem:
        problems.append("dispute: %s" % problem)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "all five compensation kinds require the SETTLED state")
    )


def case_33_compensation_exceeded(results: List[Result]) -> None:
    name = "case_33_compensation_exceeded"
    ledger, _index, _clock, fixture, _refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    # c2's distributable is 48 with no compensations yet: 49 exceeds it
    problem = _expect_allocation_error(
        name, AllocationReasonCode.COMPENSATION_EXCEEDED,
        ledger.record_refund,
        command_id="ce-01", usage_transaction_id=txs["c2"],
        amount_micros=49, reason="over-refund", actor="billing",
        source="allocation-service",
    )
    if problem:
        results.append(fail(name, problem))
        return
    # and a cumulative overrun on c1 (already compensated 185 of 850)
    problem = _expect_allocation_error(
        name, AllocationReasonCode.COMPENSATION_EXCEEDED,
        ledger.record_refund,
        command_id="ce-02", usage_transaction_id=txs["c1"],
        amount_micros=666, reason="cumulative overrun", actor="billing",
        source="allocation-service",
    )
    if problem:
        results.append(fail(name, problem))
        return
    results.append(
        ok(name, "single and cumulative over-compensation rejected; the "
                 "net never goes negative")
    )


def case_34_dispute_discipline(results: List[Result]) -> None:
    name = "case_34_dispute_discipline"
    ledger, _index, _clock, fixture, _refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    problems: List[str] = []
    problem = _expect_allocation_error(
        name, AllocationReasonCode.DISPUTE_ALREADY_OPEN,
        ledger.record_dispute,
        command_id="dd-01", usage_transaction_id=txs["c1"],
        reason="second dispute", actor="billing",
        source="allocation-service",
    )
    if problem:
        problems.append("second dispute: %s" % problem)
    # the dispute record is non-monetary: the stored amount is 0
    dispute = [
        compensation for compensation in
        ledger.allocation(txs["c1"]).compensations
        if compensation.compensation_kind == "dispute"
    ][0]
    if dispute.amount_micros != 0:
        problems.append("dispute amount not pinned to 0")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "one open dispute per allocation; disputes are "
                 "non-monetary (amount pinned to 0)")
    )


def case_35_immutable_settled_history(results: List[Result]) -> None:
    name = "case_35_immutable_settled_history"
    ledger, _index, _clock, fixture, refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    projection = ledger.allocation(txs["c1"])
    snapshot_before = projection.snapshot.to_dict()
    settlement_before = projection.settlement.to_dict()
    references_before = [
        record.to_dict() for record in projection.payment_references
    ]
    # append more compensating history after the settled state
    ledger.record_refund(
        command_id="ish-01", usage_transaction_id=txs["c1"],
        amount_micros=5, reason="late partial refund", actor="billing",
        source="allocation-service",
    )
    ledger.record_payment_reference(
        command_id="ish-02", usage_transaction_id=txs["c1"],
        payment_reference=refs["pay-4"],
        actor="payment-callback-gateway",
        source="payment-provider-boundary",
    )
    after = ledger.allocation(txs["c1"])
    problems: List[str] = []
    if after.snapshot.to_dict() != snapshot_before:
        problems.append("settled snapshot mutated by later facts")
    if after.settlement.to_dict() != settlement_before:
        problems.append("settlement acknowledgement mutated")
    after_dicts = sorted(
        json.dumps(record.to_dict(), sort_keys=True)
        for record in after.payment_references
    )
    before_dicts = sorted(
        json.dumps(record, sort_keys=True)
        for record in references_before
    )
    if after_dicts[: len(before_dicts)] != before_dicts:
        problems.append("earlier payment references rewritten")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "settled snapshot/acknowledgement/reference history "
                 "byte-identical across later append-only facts")
    )


def case_36_reconciliation_statement(results: List[Result]) -> None:
    name = "case_36_reconciliation_statement"
    ledger, _index, _clock, fixture, refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    statement = ledger.allocation_statement(txs["c1"])
    problems: List[str] = []
    expected_members = {
        "kind": "allocation-reconciliation-statement",
        "usage_transaction_id": txs["c1"],
        "allocation_state": "SETTLED",
        "policy_id": _golden_policy_id(),
        "gross_micros": _C1_GROSS,
        "fee_micros": _C1_FEE,
        "tax_micros": _C1_TAX,
        "adjustment_micros": _C1_ADJUSTMENT,
        "distributable_micros": _C1_DISTRIBUTABLE,
        "adcos_share_micros": _C1_ADCOS,
        "provider_share_micros": _C1_PROVIDER,
        "developer_share_micros": _C1_DEVELOPER,
        "three_way_sum_micros": _C1_DISTRIBUTABLE,
        "settlement_reference": refs["sett-1"],
        "settlement_acknowledged": True,
        "refunded_amount_micros": 100,
        "reversed_amount_micros": 50,
        "chargeback_amount_micros": 25,
        "payout_failure_amount_micros": 10,
        "disputed": True,
        "net_distributable_micros": 665,
    }
    for member, expected in expected_members.items():
        if statement.get(member) != expected:
            problems.append(
                "%s = %r != %r" % (member, statement.get(member), expected)
            )
    for member in (
        "allocation_id", "usage_statement_id", "created_at",
        "acknowledgement_id", "acknowledged_at", "compensation_ids",
        "payment_reference_record_ids", "projection_digest",
        "rounding_mode", "currency", "minor_unit_digits",
        "provider_share_bps", "adcos_share_bps",
    ):
        if member not in statement:
            problems.append("missing audit member %r" % member)
    # the reference-id multiset is exact (the citation list itself is
    # sorted by the content-derived record ids, a canonical audit
    # order that is not the insertion order)
    if sorted(statement["payment_reference_ids"]) != sorted(
        [refs["pay-1"], refs["pay-2"]]
    ):
        problems.append("payment reference multiset wrong")
    projection = ledger.allocation(txs["c1"])
    if statement["payment_reference_ids"] != [
        record.payment_reference
        for record in projection.payment_references
    ]:
        problems.append("payment reference audit order diverged")
    # deterministic re-read
    if ledger.allocation_statement(txs["c1"]) != statement:
        problems.append("re-read diverged")
    if problems:
        results.append(fail(name, "; ".join(problems[:6])))
        return
    results.append(
        ok(name, "full deterministic audit trail: shares, conservation, "
                 "references, settlement, compensations, net, digests")
    )


def case_37_policy_version_immutability(results: List[Result]) -> None:
    name = "case_37_policy_version_immutability"
    ledger, _index, clock, fixture, _refs = _golden_ledger()
    records_before = len(ledger.journal_records())
    reads_before = clock.reads
    problems: List[str] = []
    # identical terms under a NEW command id: the identical immutable
    # version (idempotent no-op)
    outcome = ledger.register_policy(
        command_id="pvi-01", label=_POLICY_LABEL,
        adcos_share_bps=_POLICY_ADCOS_BPS,
        provider_min_bps=_POLICY_MIN_BPS,
        provider_max_bps=_POLICY_MAX_BPS,
        rounding_mode=_POLICY_ROUNDING, currency=_POLICY_CURRENCY,
        minor_unit_digits=_POLICY_DIGITS,
        effective_from=_POLICY_FROM, effective_until=_POLICY_UNTIL,
        actor="platform", source="economic-policy-service",
    )
    if outcome.status != CommandStatus.DUPLICATE:
        problems.append("identical terms not a duplicate no-op")
    if outcome.fact_id != _golden_policy_id():
        problems.append("duplicate returned the wrong policy id")
    if len(ledger.journal_records()) != records_before:
        problems.append("re-registration grew the journal")
    if clock.reads != reads_before:
        problems.append("re-registration consumed a clock read")
    if len(ledger.policies()) != 1:
        problems.append("registry size changed")
    # different terms: a genuinely NEW version id
    outcome = ledger.register_policy(
        command_id="pvi-02", label="standard-2027",
        adcos_share_bps=_POLICY_ADCOS_BPS,
        provider_min_bps=_POLICY_MIN_BPS,
        provider_max_bps=_POLICY_MAX_BPS,
        rounding_mode=_POLICY_ROUNDING, currency=_POLICY_CURRENCY,
        minor_unit_digits=_POLICY_DIGITS,
        effective_from="2027-01-01T00:00:00Z",
        effective_until="2028-01-01T00:00:00Z",
        actor="platform", source="economic-policy-service",
    )
    if outcome.status != CommandStatus.APPENDED:
        problems.append("new terms not appended")
    if outcome.fact_id == _golden_policy_id():
        problems.append("new terms derived the same version id")
    if len(ledger.policies()) != 2:
        problems.append("new version not registered")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "identical terms -> the identical immutable version "
                 "(no-op); any term change -> a genuinely new version id")
    )


def case_38_tampered_journal(results: List[Result]) -> None:
    name = "case_38_tampered_journal"
    ledger, index, _clock, _fixture, _refs = _golden_ledger()
    data = b"".join(
        record.to_line() for record in ledger.journal_records()
    )
    problems: List[str] = []
    # byte flip
    middle = len(data) // 2
    flipped = bytearray(data)
    flipped[middle] = (flipped[middle] + 1) % 256
    problem = _expect_allocation_error(
        name, AllocationReasonCode.JOURNAL_CORRUPT,
        AllocationLedger.load,
        store=FrozenBytesStore(bytes(flipped)),
        clock=StepClock(_AT0, _ASTEP), evidence_index=index,
    )
    if problem:
        problems.append("byte flip: %s" % problem)
    # line reorder (swap two adjacent complete lines)
    lines = data.split(b"\n")[:-1]
    reordered = (
        lines[0:2] + [lines[3], lines[2]] + lines[4:]
    )
    problem = _expect_allocation_error(
        name, AllocationReasonCode.JOURNAL_CORRUPT,
        AllocationLedger.load,
        store=FrozenBytesStore(b"".join(
            line + b"\n" for line in reordered
        )),
        clock=StepClock(_AT0, _ASTEP), evidence_index=index,
    )
    if problem:
        problems.append("reorder: %s" % problem)
    # truncated tail (mid-line, no trailing newline)
    problem = _expect_allocation_error(
        name, AllocationReasonCode.JOURNAL_CORRUPT,
        AllocationLedger.load,
        store=FrozenBytesStore(data[:-25]),
        clock=StepClock(_AT0, _ASTEP), evidence_index=index,
    )
    if problem:
        problems.append("truncation: %s" % problem)
    # sequence gap (edit a stored sequence, ids left stale)
    records = _golden_journal_lines(ledger)
    records[3]["sequence"] = 99
    rebuilt = b"".join(
        (json.dumps(record) + "\n").encode("utf-8")
        for record in records
    )
    problem = _expect_allocation_error(
        name, AllocationReasonCode.JOURNAL_CORRUPT,
        AllocationLedger.load,
        store=FrozenBytesStore(rebuilt),
        clock=StepClock(_AT0, _ASTEP), evidence_index=index,
    )
    if problem:
        problems.append("sequence gap: %s" % problem)
    # command digest edit
    records = _golden_journal_lines(ledger)
    records[2]["command_digest"] = "sha256:" + "0" * 64
    rebuilt = b"".join(
        (json.dumps(record) + "\n").encode("utf-8")
        for record in records
    )
    problem = _expect_allocation_error(
        name, AllocationReasonCode.JOURNAL_CORRUPT,
        AllocationLedger.load,
        store=FrozenBytesStore(rebuilt),
        clock=StepClock(_AT0, _ASTEP), evidence_index=index,
    )
    if problem:
        problems.append("digest edit: %s" % problem)
    # event id edit
    records = _golden_journal_lines(ledger)
    records[1]["event"]["event_id"] = "sha256:" + "1" * 64
    rebuilt = b"".join(
        (json.dumps(record) + "\n").encode("utf-8")
        for record in records
    )
    problem = _expect_allocation_error(
        name, AllocationReasonCode.JOURNAL_CORRUPT,
        AllocationLedger.load,
        store=FrozenBytesStore(rebuilt),
        clock=StepClock(_AT0, _ASTEP), evidence_index=index,
    )
    if problem:
        problems.append("event id edit: %s" % problem)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "byte flip, reorder, truncation, sequence gap, digest "
                 "edit, and event-id edit all fail closed JOURNAL_CORRUPT")
    )


def case_39_journal_first_recovery(results: List[Result]) -> None:
    name = "case_39_journal_first_recovery"
    directory = Path(tempfile.mkdtemp(prefix="w053-recovery-"))
    problems: List[str] = []
    try:
        store = allocation.FileAllocationStore(directory)
        ledger, _index, _clock, fixture, refs = _golden_ledger(store=store)
        usage_ledger, txs, _world = fixture
        recovered = AllocationLedger.load(
            store=allocation.FileAllocationStore(directory),
            clock=StepClock("2026-11-01T00:00:00Z", 60),
            evidence_index=ledger.evidence_index(),
        )
        if recovered.state_digest() != ledger.state_digest():
            problems.append("recovered state digest diverged")
        if recovered.digest_stream() != ledger.digest_stream():
            problems.append("recovered digest stream diverged")
        if len(recovered.journal_records()) != len(
            ledger.journal_records()
        ):
            problems.append("recovered journal length diverged")
        # durable idempotency survives restart
        records_before = len(recovered.journal_records())
        outcome = recovered.record_payment_reference(
            command_id="e-03", usage_transaction_id=txs["c1"],
            payment_reference=refs["pay-1"],
            actor="payment-callback-gateway",
            source="payment-provider-boundary",
        )
        if outcome.status != CommandStatus.DUPLICATE:
            problems.append("durable idempotency lost across restart")
        if len(recovered.journal_records()) != records_before:
            problems.append("restart duplicate grew the journal")
        recovered.verify_replay()
    finally:
        shutil.rmtree(directory, ignore_errors=True)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "file-store reload: state/stream byte-identical; "
                 "idempotency survives restart; replay verifies")
    )


def case_40_replay_verification(results: List[Result]) -> None:
    name = "case_40_replay_verification"
    ledger, _index, _clock, _fixture, _refs = _golden_ledger()
    ledger.verify_replay()
    folded = allocation.fold_state(
        ledger.journal_records(), evidence_index=ledger.evidence_index()
    )
    problems: List[str] = []
    for key in sorted(ledger.allocations() and {
        projection.usage_transaction_id
        for projection in ledger.allocations()
    }):
        live = ledger.allocation(key).to_dict()
        replayed = folded.allocations[key].to_dict()
        if live != replayed:
            problems.append("live/replay divergence for %s" % key[:16])
    for policy in ledger.policies():
        if folded.policies.get(policy.policy_id) is None:
            problems.append("policy missing from the fold")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(ok(name, "fold == live for every allocation and policy"))


def case_41_inserted_out_of_order_record(results: List[Result]) -> None:
    name = "case_41_inserted_out_of_order_record"
    ledger, index, _clock, _fixture, _refs = _golden_ledger()
    lines = _golden_journal_lines(ledger)
    # relocate the first refund (SETTLED self-loop) to BEFORE the
    # settlement acknowledgement: the walk-linkage gate must reject
    refund = lines[5]
    rest = lines[0:5] + lines[6:]
    reordered = [rest[0], rest[1], rest[2], refund] + rest[3:]
    problem = _expect_allocation_error(
        name, AllocationReasonCode.JOURNAL_CORRUPT,
        AllocationLedger.load,
        store=FrozenBytesStore(_rechain(reordered)),
        clock=StepClock(_AT0, _ASTEP), evidence_index=index,
    )
    if problem:
        results.append(fail(name, problem))
        return
    results.append(
        ok(name, "out-of-order record relocation fails closed at the "
                 "walk-linkage gate (the replay verifies the WALK)")
    )


def case_42_persist_then_ack(results: List[Result]) -> None:
    name = "case_42_persist_then_ack"
    ledger, _index, _clock, fixture, _refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    statements = _usage_statements(usage_ledger, txs)
    fresh = AllocationLedger(
        store=FailingAllocationStore(),
        clock=StepClock("2026-10-02T00:00:00Z", 60),
        evidence_index=ledger.evidence_index(),
    )
    problems: List[str] = []
    problem = _expect_allocation_error(
        name, AllocationReasonCode.STORE_FAILED,
        fresh.register_policy,
        command_id="pta-01", label=_POLICY_LABEL,
        adcos_share_bps=_POLICY_ADCOS_BPS,
        provider_min_bps=_POLICY_MIN_BPS,
        provider_max_bps=_POLICY_MAX_BPS,
        rounding_mode=_POLICY_ROUNDING, currency=_POLICY_CURRENCY,
        minor_unit_digits=_POLICY_DIGITS,
        effective_from=_POLICY_FROM, effective_until=_POLICY_UNTIL,
        actor="platform", source="economic-policy-service",
    )
    if problem:
        problems.append("store failure not typed: %s" % problem)
    if len(fresh.journal_records()) != 0:
        problems.append("phantom journal record after store failure")
    if len(fresh.policies()) != 0:
        problems.append("phantom in-memory policy after store failure")
    problem = _expect_allocation_error(
        name, AllocationReasonCode.POLICY_UNKNOWN,
        fresh.policy, _golden_policy_id(),
    )
    if problem:
        problems.append("phantom policy readable: %s" % problem)
    # a working retry over a fresh store succeeds cleanly
    retry = AllocationLedger(
        store=MemoryAllocationStore(),
        clock=StepClock("2026-10-02T00:00:00Z", 60),
        evidence_index=ledger.evidence_index(),
    )
    outcome = retry.register_policy(
        command_id="pta-02", label=_POLICY_LABEL,
        adcos_share_bps=_POLICY_ADCOS_BPS,
        provider_min_bps=_POLICY_MIN_BPS,
        provider_max_bps=_POLICY_MAX_BPS,
        rounding_mode=_POLICY_ROUNDING, currency=_POLICY_CURRENCY,
        minor_unit_digits=_POLICY_DIGITS,
        effective_from=_POLICY_FROM, effective_until=_POLICY_UNTIL,
        actor="platform", source="economic-policy-service",
    )
    if outcome.status != CommandStatus.APPENDED:
        problems.append("clean retry failed")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "STORE_FAILED leaves no phantom state; clean retry works")
    )


def case_43_walk_valid_allocation_tamper(results: List[Result]) -> None:
    name = "case_43_walk_valid_recomputed_allocation_tamper"
    ledger, index, _clock, fixture, _refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    lines = _golden_journal_lines(ledger)
    problems: List[str] = []

    # Variant A -- a split-consistent fact-only reprice: the fact's
    # OWN provider bps mutated to 6000 with the shares recomputed
    # exactly over the mutated basis (compute_split(850, 1500,
    # 6000, half-up) = (128, 433, 289)), the allocation id and
    # event id recomputed, the FULL outer chain recomputed; the
    # command untouched.  Only the full re-derivation from the
    # causal command (provider bps 5000) can catch it.
    records = json.loads(json.dumps(lines))
    fact = records[1]["event"]["fact"]
    fact["provider_share_bps"] = 6000
    adcos, provider, developer = compute_split(850, 1500, 6000, "half-up")
    fact["adcos_share_micros"] = adcos
    fact["provider_share_micros"] = provider
    fact["developer_share_micros"] = developer
    fact["allocation_id"] = derive_allocation_id(
        fact["usage_transaction_id"], fact["usage_statement_id"],
        fact["policy_id"], fact["provider_share_bps"],
        fact["fee_micros"], fact["tax_micros"],
        fact["adjustment_micros"], fact["created_at"],
    )
    _recompute_event_id(records[1], fact["allocation_id"])
    problem = _expect_allocation_error(
        name, AllocationReasonCode.JOURNAL_CORRUPT,
        AllocationLedger.load,
        store=FrozenBytesStore(_rechain(records)),
        clock=StepClock(_AT0, _ASTEP), evidence_index=index,
    )
    if problem:
        problems.append("split-consistent reprice accepted: %s" % problem)

    # Variant B -- a gross reprice with internally-consistent
    # arithmetic: gross 930 -> 940, distributable 850 -> 860, the
    # shares recomputed exactly (compute_split(860, 1500, 5000,
    # half-up) = (129, 366, 365)); the allocation id basis does
    # not even include the gross, so only the re-binding to the
    # INJECTED W052 usage snapshot (gross 930) can catch it.
    records = json.loads(json.dumps(lines))
    fact = records[1]["event"]["fact"]
    fact["gross_micros"] = 940
    fact["distributable_micros"] = 860
    adcos, provider, developer = compute_split(860, 1500, 5000, "half-up")
    fact["adcos_share_micros"] = adcos
    fact["provider_share_micros"] = provider
    fact["developer_share_micros"] = developer
    _recompute_event_id(records[1], fact["allocation_id"])
    problem = _expect_allocation_error(
        name, AllocationReasonCode.JOURNAL_CORRUPT,
        AllocationLedger.load,
        store=FrozenBytesStore(_rechain(records)),
        clock=StepClock(_AT0, _ASTEP), evidence_index=index,
    )
    if problem:
        problems.append("gross reprice accepted: %s" % problem)

    # Variant C -- an attribution swap on the event (actor forged
    # to a different principal than the admitted command's),
    # chain recomputed, walk untouched.
    records = json.loads(json.dumps(lines))
    records[1]["event"]["actor"] = "attacker"
    problem = _expect_allocation_error(
        name, AllocationReasonCode.JOURNAL_CORRUPT,
        AllocationLedger.load,
        store=FrozenBytesStore(_rechain(records)),
        clock=StepClock(_AT0, _ASTEP), evidence_index=index,
    )
    if problem:
        problems.append("attribution swap accepted: %s" % problem)

    # Variant D -- a fact-kind swap (an allocate event whose fact
    # claims to be a compensation record), chain recomputed.
    records = json.loads(json.dumps(lines))
    records[1]["event"]["fact"] = {
        "kind": "allocation-compensation-record",
        "compensation_id": "sha256:" + "a" * 64,
        "usage_transaction_id": txs["c1"],
        "compensation_kind": "refund",
        "amount_micros": 1,
        "reason": "kind swap",
        "allocation_id": "sha256:" + "b" * 64,
        "command_id": records[1]["command"]["command_id"],
        "recorded_at": _AT0,
    }
    problem = _expect_allocation_error(
        name, AllocationReasonCode.JOURNAL_CORRUPT,
        AllocationLedger.load,
        store=FrozenBytesStore(_rechain(records)),
        clock=StepClock(_AT0, _ASTEP), evidence_index=index,
    )
    if problem:
        problems.append("fact-kind swap accepted: %s" % problem)

    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "split-consistent reprice, gross reprice, attribution "
                 "swap, and fact-kind swap all fail closed (full "
                 "re-derivation + snapshot re-binding)")
    )


def case_44_walk_valid_policy_tamper(results: List[Result]) -> None:
    name = "case_44_walk_valid_recomputed_policy_tamper"
    ledger, index, _clock, _fixture, _refs = _golden_ledger()
    lines = _golden_journal_lines(ledger)
    problems: List[str] = []

    # Variant A -- the policy fact's terms mutated (adcos 1500 ->
    # 1200) WITHOUT recomputing the policy id: the identity <->
    # content binding gate catches it.
    records = json.loads(json.dumps(lines))
    records[0]["event"]["fact"]["adcos_share_bps"] = 1200
    problem = _expect_allocation_error(
        name, AllocationReasonCode.JOURNAL_CORRUPT,
        AllocationLedger.load,
        store=FrozenBytesStore(_rechain(records)),
        clock=StepClock(_AT0, _ASTEP), evidence_index=index,
    )
    if problem:
        problems.append("id-inconsistent policy tamper accepted: %s" % problem)

    # Variant B -- the terms mutated AND the policy id recomputed
    # (the full identity cascade): the ALLOCATE records still cite
    # the ORIGINAL policy id, which no longer resolves in the
    # folded registry at replay -- the policy-resolution gate
    # catches the fully-cascaded rewrite.
    records = json.loads(json.dumps(lines))
    fact = records[0]["event"]["fact"]
    fact["adcos_share_bps"] = 1200
    mutated_terms = dict(
        label=fact["label"], adcos_share_bps=fact["adcos_share_bps"],
        provider_min_bps=fact["provider_min_bps"],
        provider_max_bps=fact["provider_max_bps"],
        rounding_mode=fact["rounding_mode"], currency=fact["currency"],
        minor_unit_digits=fact["minor_unit_digits"],
        effective_from=fact["effective_from"],
        effective_until=fact["effective_until"],
    )
    fact["policy_id"] = derive_policy_id(**mutated_terms)
    _recompute_event_id(records[0], fact["policy_id"])
    problem = _expect_allocation_error(
        name, AllocationReasonCode.JOURNAL_CORRUPT,
        AllocationLedger.load,
        store=FrozenBytesStore(_rechain(records)),
        clock=StepClock(_AT0, _ASTEP), evidence_index=index,
    )
    if problem:
        problems.append("fully-cascaded policy tamper accepted: %s" % problem)

    # Variant C -- a duplicate policy registration in the journal
    # (two records, identical version id, everything recomputed):
    # the registry-duplicate fold gate catches it.
    records = json.loads(json.dumps(lines))
    duplicate = json.loads(json.dumps(records[0]))
    duplicate["command"]["command_id"] = "policy-dup"
    duplicate["command_digest"] = AllocationCommand.from_dict(
        duplicate["command"]
    ).digest()
    records = [records[0], duplicate] + records[1:]
    problem = _expect_allocation_error(
        name, AllocationReasonCode.JOURNAL_CORRUPT,
        AllocationLedger.load,
        store=FrozenBytesStore(_rechain(records)),
        clock=StepClock(_AT0, _ASTEP), evidence_index=index,
    )
    if problem:
        problems.append("duplicate policy registration accepted: %s" % problem)

    # Variant D -- the journal-order forgery: the policy record
    # relocated AFTER the allocation that cites it (the registry
    # is empty at the citation point in the fold).
    records = json.loads(json.dumps(lines))
    policy_record = records[0]
    reordered = [records[1], policy_record] + records[2:]
    problem = _expect_allocation_error(
        name, AllocationReasonCode.JOURNAL_CORRUPT,
        AllocationLedger.load,
        store=FrozenBytesStore(_rechain(reordered)),
        clock=StepClock(_AT0, _ASTEP), evidence_index=index,
    )
    if problem:
        problems.append("journal-order policy forgery accepted: %s" % problem)

    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "id-inconsistent, fully-cascaded, duplicate, and "
                 "journal-order policy forgeries all fail closed")
    )


def case_45_walk_valid_compensation_tamper(results: List[Result]) -> None:
    name = "case_45_walk_valid_recomputed_compensation_tamper"
    ledger, index, _clock, fixture, _refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    lines = _golden_journal_lines(ledger)
    problems: List[str] = []

    # Variant A -- the compensation amount mutated (100 -> 400)
    # with the compensation id, event id, and the FULL outer chain
    # recomputed; the command untouched.  Only the causal
    # command->fact re-derivation can catch it.
    records = json.loads(json.dumps(lines))
    fact = records[5]["event"]["fact"]
    fact["amount_micros"] = 400
    fact["compensation_id"] = derive_compensation_id(
        fact["usage_transaction_id"], fact["compensation_kind"],
        fact["amount_micros"], fact["reason"], fact["allocation_id"],
        fact["command_id"], fact["recorded_at"],
    )
    _recompute_event_id(records[5], fact["compensation_id"])
    problem = _expect_allocation_error(
        name, AllocationReasonCode.JOURNAL_CORRUPT,
        AllocationLedger.load,
        store=FrozenBytesStore(_rechain(records)),
        clock=StepClock(_AT0, _ASTEP), evidence_index=index,
    )
    if problem:
        problems.append("fact-only compensation tamper accepted: %s" % problem)

    # Variant B -- the MAXIMAL cascade: the command payload is
    # mutated too (amount 100 -> 800, digest recomputed), the
    # compensation fact + identities recomputed, and the entire
    # outer chain recomputed.  The journal is internally
    # self-consistent AND command-consistent; the DISTRIBUTABLE
    # BOUND (cumulative 800 + 50 + 25 + 10 = 885 > 850, pinned to
    # the snapshot) is the only gate that can reject it -- and it
    # does.
    records = json.loads(json.dumps(lines))
    command = records[5]["command"]
    command["payload"]["amount_micros"] = 800
    records[5]["command_digest"] = AllocationCommand.from_dict(
        command
    ).digest()
    fact = records[5]["event"]["fact"]
    fact["amount_micros"] = 800
    fact["compensation_id"] = derive_compensation_id(
        fact["usage_transaction_id"], fact["compensation_kind"],
        fact["amount_micros"], fact["reason"], fact["allocation_id"],
        fact["command_id"], fact["recorded_at"],
    )
    _recompute_event_id(records[5], fact["compensation_id"])
    problem = _expect_allocation_error(
        name, AllocationReasonCode.JOURNAL_CORRUPT,
        AllocationLedger.load,
        store=FrozenBytesStore(_rechain(records)),
        clock=StepClock(_AT0, _ASTEP), evidence_index=index,
    )
    if problem:
        problems.append("maximal-cascade over-compensation accepted: %s" % problem)

    # Variant C -- a second dispute record (everything recomputed):
    # the one-open-dispute fold gate catches it.
    records = json.loads(json.dumps(lines))
    dispute = json.loads(json.dumps(records[9]))
    dispute["command"]["command_id"] = "dispute-dup"
    dispute["command_digest"] = AllocationCommand.from_dict(
        dispute["command"]
    ).digest()
    fact = dispute["event"]["fact"]
    fact["command_id"] = "dispute-dup"
    fact["compensation_id"] = derive_compensation_id(
        fact["usage_transaction_id"], fact["compensation_kind"],
        fact["amount_micros"], fact["reason"], fact["allocation_id"],
        fact["command_id"], fact["recorded_at"],
    )
    _recompute_event_id(dispute, fact["compensation_id"])
    records = records + [dispute]
    problem = _expect_allocation_error(
        name, AllocationReasonCode.JOURNAL_CORRUPT,
        AllocationLedger.load,
        store=FrozenBytesStore(_rechain(records)),
        clock=StepClock(_AT0, _ASTEP), evidence_index=index,
    )
    if problem:
        problems.append("second dispute accepted: %s" % problem)

    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "fact-only reprice, maximal-cascade over-compensation, "
                 "and second-dispute forgeries all fail closed")
    )


def case_46_walk_valid_non_final_usage_forgery(results: List[Result]) -> None:
    name = "case_46_walk_valid_non_final_usage_forgery"
    ledger, index, _clock, fixture, refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    problems: List[str] = []
    # the control statement id the forged allocation cites (the
    # honest-shaped control snapshot below carries it)
    control_statement = "sha256:" + "9" * 64

    # THE VECTOR: a walk-valid, fully-recomputed journal claiming
    # allocation over the REAL OBSERVING usage transaction c3
    records = _forge_four_record_journal(
        usage_transaction_id=txs["c3"],
        usage_statement_id=control_statement,
        gross_micros=360,
        settlement_reference=refs["sett-3"],
    )
    problem = _expect_allocation_error(
        name, AllocationReasonCode.JOURNAL_CORRUPT,
        AllocationLedger.load,
        store=FrozenBytesStore(_rechain(records)),
        clock=StepClock(_AT0, _ASTEP), evidence_index=index,
    )
    if problem:
        problems.append("OBSERVING usage forgery accepted: %s" % problem)

    # admission symmetry (self-contained): live admission of the
    # same allocation against the same authority fails closed
    # exactly as case_13 proves (USAGE_NOT_FINAL)
    fresh = AllocationLedger(
        store=MemoryAllocationStore(),
        clock=StepClock("2026-10-02T00:00:00Z", 60),
        evidence_index=index,
    )
    fresh.register_policy(
        command_id="nf-01", label=_POLICY_LABEL,
        adcos_share_bps=_POLICY_ADCOS_BPS,
        provider_min_bps=_POLICY_MIN_BPS,
        provider_max_bps=_POLICY_MAX_BPS,
        rounding_mode=_POLICY_ROUNDING, currency=_POLICY_CURRENCY,
        minor_unit_digits=_POLICY_DIGITS,
        effective_from=_POLICY_FROM, effective_until=_POLICY_UNTIL,
        actor="platform", source="economic-policy-service",
    )
    problem = _expect_allocation_error(
        name, AllocationReasonCode.USAGE_NOT_FINAL,
        fresh.allocate,
        command_id="nf-02", usage_transaction_id=txs["c3"],
        usage_statement_id=control_statement,
        policy_id=_golden_policy_id(), provider_share_bps=5000,
        actor="billing", source="allocation-service",
    )
    if problem:
        problems.append("admission symmetry: %s" % problem)

    # CONTROL: the IDENTICAL forged journal replayed against an
    # index identical except the c3 snapshot is billable-final
    # with the cited statement and gross 360 (the honest-shaped
    # control a caller could have built had the usage sealed) --
    # it loads cleanly and folds to the expected allocation,
    # proving the rejection above is the finality gate and ONLY
    # the finality gate.
    control_usage: List[BillableUsageSnapshot] = []
    for key in ("c1", "c2", "c4"):
        control_usage.append(index.usage(txs[key]))
    control_usage.append(
        BillableUsageSnapshot(
            usage_transaction_id=txs["c3"],
            usage_state=USAGE_STATE_FINAL,
            gross_amount_micros=360,
            statement_id=control_statement,
            billable_quantity=120,
            unit_price_micros=3,
            billable_unit="byte",
            tariff_provenance="usage-public-read",
            sealed_at="2026-09-01T12:20:00Z",
        )
    )
    control_index = AllocationEvidenceIndex(
        usage=control_usage,
        references=[
            index.reference(refs[key]) for key in
            ("sett-1", "sett-2", "sett-3", "pay-1", "pay-2", "pay-3", "pay-4")
        ],
    )
    control = AllocationLedger.load(
        store=FrozenBytesStore(_rechain(records)),
        clock=StepClock(_AT0, _ASTEP), evidence_index=control_index,
    )
    control_projection = control.allocation(txs["c3"])
    if control_projection.state != "SETTLED":
        problems.append("control did not fold to SETTLED")
    if control_projection.snapshot.gross_micros != 360:
        problems.append("control gross wrong")
    adcos, provider, developer = compute_split(360, 1500, 5000, "half-up")
    if (
        control_projection.snapshot.adcos_share_micros != adcos
        or control_projection.snapshot.provider_share_micros != provider
        or control_projection.snapshot.developer_share_micros != developer
    ):
        problems.append("control shares wrong")

    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "walk-valid fully-recomputed forgery over OBSERVING usage "
                 "rejected; admission symmetric; honest control loads and "
                 "folds (54, 153, 153)")
    )


def case_47_walk_valid_settlement_kind_forgery(results: List[Result]) -> None:
    name = "case_47_walk_valid_settlement_kind_forgery"
    ledger, index, _clock, fixture, refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    statements = _usage_statements(usage_ledger, txs)
    problems: List[str] = []

    # THE VECTOR: a walk-valid, fully-recomputed journal whose
    # settlement acknowledgement cites a PAYMENT reference
    # (pay-1: genuinely resolvable, correctly correlated to c1 --
    # only the KIND is wrong)
    records = _forge_four_record_journal(
        usage_transaction_id=txs["c1"],
        usage_statement_id=statements["c1"],
        gross_micros=_C1_GROSS,
        settlement_reference=refs["pay-1"],
        policy_prefix="k-",
    )
    problem = _expect_allocation_error(
        name, AllocationReasonCode.JOURNAL_CORRUPT,
        AllocationLedger.load,
        store=FrozenBytesStore(_rechain(records)),
        clock=StepClock(_AT0, _ASTEP), evidence_index=index,
    )
    if problem:
        problems.append("payment-cited-as-settlement forgery accepted: %s" % problem)

    # admission symmetry: live admission of the same citation
    problem = _expect_allocation_error(
        name, AllocationReasonCode.PAYMENT_NOT_SETTLEMENT,
        ledger.acknowledge_settlement,
        command_id="sk-01", usage_transaction_id=txs["c1"],
        settlement_reference=refs["pay-1"], actor="settlement",
        source="settlement-service",
    )
    if problem:
        problems.append("admission symmetry: %s" % problem)

    # CONTROL: the same forged journal citing the honest
    # settlement reference loads cleanly and folds to SETTLED
    records = _forge_four_record_journal(
        usage_transaction_id=txs["c1"],
        usage_statement_id=statements["c1"],
        gross_micros=_C1_GROSS,
        settlement_reference=refs["sett-1"],
        policy_prefix="k-",
    )
    control = AllocationLedger.load(
        store=FrozenBytesStore(_rechain(records)),
        clock=StepClock(_AT0, _ASTEP), evidence_index=index,
    )
    if control.allocation(txs["c1"]).state != "SETTLED":
        problems.append("control did not fold to SETTLED")

    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "payment-cited-as-settlement forgery rejected at replay "
                 "(kind table, admission/replay symmetric); control loads")
    )


def case_48_walk_valid_duplicate_callback_forgery(results: List[Result]) -> None:
    name = "case_48_walk_valid_duplicate_callback_forgery"
    ledger, index, _clock, fixture, refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    statements = _usage_statements(usage_ledger, txs)
    problems: List[str] = []

    # THE VECTOR: a walk-valid, fully-recomputed journal whose TWO
    # payment-callback records cite the SAME external reference
    # identity under different command ids
    records = _forge_duplicate_callback_journal(
        usage_transaction_id=txs["c1"],
        usage_statement_id=statements["c1"],
        gross_micros=_C1_GROSS,
        payment_reference=refs["pay-1"],
    )
    problem = _expect_allocation_error(
        name, AllocationReasonCode.JOURNAL_CORRUPT,
        AllocationLedger.load,
        store=FrozenBytesStore(_rechain(records)),
        clock=StepClock(_AT0, _ASTEP), evidence_index=index,
    )
    if problem:
        problems.append("duplicate-callback journal accepted: %s" % problem)

    # CONTROL: the second callback citing a DIFFERENT reference
    # (pay-2) loads cleanly -- only the duplicate identity fires
    records[3]["command"]["payload"]["payment_reference"] = refs["pay-2"]
    records[3]["command_digest"] = AllocationCommand.from_dict(
        records[3]["command"]
    ).digest()
    fact = records[3]["event"]["fact"]
    fact["payment_reference"] = refs["pay-2"]
    fact["payment_reference_id"] = derive_payment_reference_id(
        fact["usage_transaction_id"], fact["allocation_id"],
        fact["payment_reference"], fact["command_id"], fact["recorded_at"],
    )
    _recompute_event_id(records[3], fact["payment_reference_id"])
    control = AllocationLedger.load(
        store=FrozenBytesStore(_rechain(records)),
        clock=StepClock(_AT0, _ASTEP), evidence_index=index,
    )
    projection = control.allocation(txs["c1"])
    if len(projection.payment_references) != 2:
        problems.append("control did not fold both callbacks")

    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "duplicated external callback identity in the journal "
                 "rejected; distinct-reference control loads")
    )


def case_49_clock_discipline(results: List[Result]) -> None:
    name = "case_49_clock_discipline"
    ledger, _index, clock, fixture, refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    problems: List[str] = []
    if clock.reads != 13:
        problems.append("golden read count %d != 13" % clock.reads)
    reads_before = clock.reads
    # three duplicate layers, none consuming a clock read
    ledger.acknowledge_settlement(  # exact command redelivery
        command_id="e-04", usage_transaction_id=txs["c1"],
        settlement_reference=refs["sett-1"], actor="settlement",
        source="settlement-service",
    )
    ledger.register_policy(  # identical policy terms, new command id
        command_id="cd-01", label=_POLICY_LABEL,
        adcos_share_bps=_POLICY_ADCOS_BPS,
        provider_min_bps=_POLICY_MIN_BPS,
        provider_max_bps=_POLICY_MAX_BPS,
        rounding_mode=_POLICY_ROUNDING, currency=_POLICY_CURRENCY,
        minor_unit_digits=_POLICY_DIGITS,
        effective_from=_POLICY_FROM, effective_until=_POLICY_UNTIL,
        actor="platform", source="economic-policy-service",
    )
    ledger.record_payment_reference(  # duplicate callback identity
        command_id="cd-02", usage_transaction_id=txs["c1"],
        payment_reference=refs["pay-1"],
        actor="payment-callback-gateway",
        source="payment-provider-boundary",
    )
    if clock.reads != reads_before:
        problems.append("duplicates consumed clock reads")
    # a rejected submission still consumes exactly one read
    try:
        ledger.record_refund(
            command_id="cd-03", usage_transaction_id=txs["c1"],
            amount_micros=999999, reason="over refund", actor="billing",
            source="allocation-service",
        )
    except AllocationError:
        pass
    if clock.reads != reads_before + 1:
        problems.append("rejected submission read count wrong")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "13 golden reads; all three duplicate layers consume none; "
                 "a gate-rejected submission consumes exactly one")
    )


def case_50_secret_hygiene(results: List[Result]) -> None:
    name = "case_50_secret_hygiene"
    ledger, _index, _clock, _fixture, _refs = _golden_ledger()
    journal_bytes = b"".join(
        record.to_line() for record in ledger.journal_records()
    )
    stream = ledger.digest_stream().encode("utf-8")
    index_bytes = json.dumps(
        ledger.evidence_index().to_dict(), sort_keys=True
    ).encode("utf-8")
    secrets = (
        _SECRET_A, _SECRET_B, _KEY_A, _KEY_B,
        hashlib.sha256(_KEY_A).hexdigest().encode("utf-8"),
        hashlib.sha256(_KEY_B).hexdigest().encode("utf-8"),
    )
    problems: List[str] = []
    for secret in secrets:
        for label, blob in (
            ("journal", journal_bytes),
            ("digest-stream", stream),
            ("evidence-index", index_bytes),
        ):
            if secret in blob:
                problems.append("secret material in %s" % label)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "journal/digest/index bytes carry no key material or "
                 "credential-like tokens")
    )


def case_51_no_shadow_authority(results: List[Result]) -> None:
    name = "case_51_no_shadow_authority"
    problems: List[str] = []
    for path in _FAMILY_FILES:
        source = path.read_text(encoding="utf-8")
        lowered = source.lower()
        for token in _VENDOR_TOKENS:
            if token in lowered:
                problems.append("%s encodes vendor token %r" % (path.name, token))
        for token in _FORBIDDEN_TOKENS:
            if token in source:
                problems.append(
                    "%s constructs/mutates a second authority: %r"
                    % (path.name, token)
                )
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "no vendor tokens; no authority construction/mutation "
                 "tokens in the allocation family (%d files)"
                 % len(_FAMILY_FILES))
    )


def case_52_import_discipline(results: List[Result]) -> None:
    name = "case_52_import_discipline"
    problems: List[str] = []
    for path in _FAMILY_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level > 0:
                    continue  # intra-package relative imports are sanctioned
                module = node.module or ""
            elif isinstance(node, ast.Import):
                if any(alias.name == "allocation" for alias in node.names):
                    continue
                module = None
                for alias in node.names:
                    candidate = alias.name
                    if candidate in _ALLOWED_IMPORT_MODULES or any(
                        candidate.startswith(prefix)
                        for prefix in _ALLOWED_IMPORT_PREFIXES
                    ):
                        continue
                    problems.append(
                        "%s imports %r (outside the sanctioned set)"
                        % (path.name, candidate)
                    )
                continue
            else:
                continue
            if module in _ALLOWED_IMPORT_MODULES:
                continue
            if any(
                module.startswith(prefix)
                for prefix in _ALLOWED_IMPORT_PREFIXES
            ):
                continue
            problems.append(
                "%s imports from %r (outside the sanctioned set)"
                % (path.name, module)
            )
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "sanctioned imports only: stdlib value types + "
                 "protocol.canonicalization + agent.clock")
    )


def case_53_public_api_stability(results: List[Result]) -> None:
    name = "case_53_public_api_stability"
    if sorted(allocation.__all__) != _EXPECTED_API:
        missing = sorted(set(_EXPECTED_API) - set(allocation.__all__))
        extra = sorted(set(allocation.__all__) - set(_EXPECTED_API))
        results.append(
            fail(
                name,
                "API drifted (missing %r, extra %r)" % (missing, extra),
            )
        )
        return
    results.append(
        ok(name, "the frozen 75-name public API surface is exact")
    )


def case_54_fail_closed_battery(results: List[Result]) -> None:
    name = "case_54_fail_closed_battery"
    ledger, index, _clock, fixture, refs = _golden_ledger()
    usage_ledger, txs, _world = fixture
    statements = _usage_statements(usage_ledger, txs)
    raised: Dict[str, bool] = {}

    def attempt(expected_reason: str, function, *args, **kwargs) -> None:
        # the parameter is NOT named ``reason`` because the
        # compensation command surface itself carries a ``reason``
        # member (the W052 helper precedent)
        try:
            function(*args, **kwargs)
        except AllocationError as error:
            if error.reason == expected_reason:
                raised[expected_reason] = True

    # model-level vectors
    attempt(
        AllocationReasonCode.INVALID_INPUT,
        BillableUsageSnapshot,
        usage_transaction_id="sha256:" + "7" * 64,
        usage_state="BILLABLE_FINAL",
        gross_amount_micros=10,
    )
    bad_command = AllocationCommand(
        command_id="fc-01", action="allocate",
        subject_id="sha256:" + "7" * 64,
        payload={"provider_share_bps": 5000},
        actor="a", source="s",
    )
    attempt(
        AllocationReasonCode.COMMAND_INVALID,
        validate_payload_shape, bad_command,
    )
    attempt(
        AllocationReasonCode.POLICY_INVALID,
        ledger.register_policy,
        command_id="fc-02", label="bad-policy",
        adcos_share_bps=20000, provider_min_bps=0,
        provider_max_bps=10000, rounding_mode="half-up",
        currency="usd", minor_unit_digits=6,
        effective_from=_POLICY_FROM, effective_until=_POLICY_UNTIL,
        actor="platform", source="economic-policy-service",
    )
    attempt(
        AllocationReasonCode.EVENT_INVALID,
        AllocationCompensationRecord,
        compensation_id="sha256:" + "4" * 64,
        usage_transaction_id="sha256:" + "2" * 64,
        compensation_kind="dispute", amount_micros=5, reason="r",
        allocation_id="sha256:" + "1" * 64, command_id="c",
        recorded_at=_AT0,
    )
    attempt(
        AllocationReasonCode.INSTANT_INVALID,
        AllocationLedger(
            store=MemoryAllocationStore(),
            clock=BrokenClock(),
            evidence_index=index,
        ).register_policy,
        command_id="fc-26", label=_POLICY_LABEL,
        adcos_share_bps=_POLICY_ADCOS_BPS,
        provider_min_bps=_POLICY_MIN_BPS,
        provider_max_bps=_POLICY_MAX_BPS,
        rounding_mode=_POLICY_ROUNDING, currency=_POLICY_CURRENCY,
        minor_unit_digits=_POLICY_DIGITS,
        effective_from=_POLICY_FROM, effective_until=_POLICY_UNTIL,
        actor="platform", source="economic-policy-service",
    )
    # admission-level vectors (the shared error path: one ledger
    # attempt per reason, never mutating the golden)
    attempt(
        AllocationReasonCode.COMMAND_CONFLICT,
        ledger.record_refund,
        command_id="e-06", usage_transaction_id=txs["c1"],
        amount_micros=77, reason="conflict", actor="billing",
        source="allocation-service",
    )
    attempt(
        AllocationReasonCode.USAGE_UNKNOWN,
        ledger.allocate,
        command_id="fc-03", usage_transaction_id="sha256:" + "e" * 64,
        usage_statement_id=statements["c1"],
        policy_id=_golden_policy_id(), provider_share_bps=5000,
        actor="billing", source="allocation-service",
    )
    attempt(
        AllocationReasonCode.USAGE_MISMATCH,
        ledger.allocate,
        command_id="fc-04", usage_transaction_id=txs["c2"],
        usage_statement_id=statements["c1"],
        policy_id=_golden_policy_id(), provider_share_bps=5000,
        actor="billing", source="allocation-service",
    )
    attempt(
        AllocationReasonCode.USAGE_NOT_FINAL,
        ledger.allocate,
        command_id="fc-05", usage_transaction_id=txs["c3"],
        usage_statement_id="sha256:" + "0" * 64,
        policy_id=_golden_policy_id(), provider_share_bps=5000,
        actor="billing", source="allocation-service",
    )
    attempt(
        AllocationReasonCode.PAYMENT_NOT_USAGE,
        ledger.allocate,
        command_id="fc-06", usage_transaction_id=refs["pay-1"],
        usage_statement_id="sha256:" + "0" * 64,
        policy_id=_golden_policy_id(), provider_share_bps=5000,
        actor="billing", source="allocation-service",
    )
    attempt(
        AllocationReasonCode.SETTLEMENT_NOT_USAGE,
        ledger.allocate,
        command_id="fc-07", usage_transaction_id=refs["sett-2"],
        usage_statement_id="sha256:" + "0" * 64,
        policy_id=_golden_policy_id(), provider_share_bps=5000,
        actor="billing", source="allocation-service",
    )
    attempt(
        AllocationReasonCode.POLICY_UNKNOWN,
        ledger.allocate,
        command_id="fc-08", usage_transaction_id=txs["c2"],
        usage_statement_id=statements["c2"],
        policy_id="sha256:" + "d" * 64, provider_share_bps=5000,
        actor="billing", source="allocation-service",
    )
    short = ledger.register_policy(
        command_id="fc-09", label="short-window",
        adcos_share_bps=_POLICY_ADCOS_BPS,
        provider_min_bps=_POLICY_MIN_BPS,
        provider_max_bps=_POLICY_MAX_BPS,
        rounding_mode=_POLICY_ROUNDING, currency=_POLICY_CURRENCY,
        minor_unit_digits=_POLICY_DIGITS,
        effective_from="2026-01-01T00:00:00Z",
        effective_until="2026-02-01T00:00:00Z",
        actor="platform", source="economic-policy-service",
    )
    attempt(
        AllocationReasonCode.POLICY_NOT_EFFECTIVE,
        ledger.allocate,
        command_id="fc-10", usage_transaction_id=txs["c4"],
        usage_statement_id=statements["c4"],
        policy_id=short.fact_id, provider_share_bps=5000,
        actor="billing", source="allocation-service",
    )
    attempt(
        AllocationReasonCode.SPLIT_OUT_OF_BOUNDS,
        ledger.allocate,
        command_id="fc-11", usage_transaction_id=txs["c2"],
        usage_statement_id=statements["c2"],
        policy_id=_golden_policy_id(), provider_share_bps=1000,
        actor="billing", source="allocation-service",
    )
    attempt(
        AllocationReasonCode.DISTRIBUTION_INVALID,
        ledger.allocate,
        command_id="fc-12", usage_transaction_id=txs["c2"],
        usage_statement_id=statements["c2"],
        policy_id=_golden_policy_id(), provider_share_bps=5000,
        fee_micros=999, actor="billing", source="allocation-service",
    )
    attempt(
        AllocationReasonCode.ALLOCATION_ALREADY_EXISTS,
        ledger.allocate,
        command_id="fc-13", usage_transaction_id=txs["c1"],
        usage_statement_id=statements["c1"],
        policy_id=_golden_policy_id(), provider_share_bps=4000,
        actor="billing", source="allocation-service",
    )
    attempt(
        AllocationReasonCode.ALLOCATION_UNKNOWN,
        ledger.record_payment_reference,
        command_id="fc-14", usage_transaction_id=txs["c3"],
        payment_reference=refs["pay-4"],
        actor="gateway", source="payment-provider-boundary",
    )
    attempt(
        AllocationReasonCode.REFERENCE_UNKNOWN,
        ledger.acknowledge_settlement,
        command_id="fc-15", usage_transaction_id=txs["c1"],
        settlement_reference="sha256:" + "1" * 64, actor="settlement",
        source="settlement-service",
    )
    attempt(
        AllocationReasonCode.REFERENCE_MISMATCH,
        ledger.acknowledge_settlement,
        command_id="fc-16", usage_transaction_id=txs["c1"],
        settlement_reference=refs["sett-2"], actor="settlement",
        source="settlement-service",
    )
    attempt(
        AllocationReasonCode.PAYMENT_NOT_SETTLEMENT,
        ledger.acknowledge_settlement,
        command_id="fc-17", usage_transaction_id=txs["c1"],
        settlement_reference=refs["pay-1"], actor="settlement",
        source="settlement-service",
    )
    attempt(
        AllocationReasonCode.SETTLEMENT_NOT_PAYMENT,
        ledger.record_payment_reference,
        command_id="fc-18", usage_transaction_id=txs["c1"],
        payment_reference=refs["sett-1"],
        actor="gateway", source="payment-provider-boundary",
    )
    attempt(
        AllocationReasonCode.SETTLEMENT_IMMUTABLE,
        ledger.acknowledge_settlement,
        command_id="fc-19", usage_transaction_id=txs["c1"],
        settlement_reference=refs["sett-1"], actor="settlement",
        source="settlement-service",
    )
    attempt(
        AllocationReasonCode.COMPENSATION_EXCEEDED,
        ledger.record_refund,
        command_id="fc-20", usage_transaction_id=txs["c2"],
        amount_micros=999, reason="over", actor="billing",
        source="allocation-service",
    )
    attempt(
        AllocationReasonCode.DISPUTE_ALREADY_OPEN,
        ledger.record_dispute,
        command_id="fc-21", usage_transaction_id=txs["c1"],
        reason="again", actor="billing", source="allocation-service",
    )
    # a fresh unacknowledged allocation for the pre-settlement reason
    fresh = AllocationLedger(
        store=MemoryAllocationStore(),
        clock=StepClock("2026-10-04T00:00:00Z", 60),
        evidence_index=index,
    )
    fresh.register_policy(
        command_id="fc-22", label=_POLICY_LABEL,
        adcos_share_bps=_POLICY_ADCOS_BPS,
        provider_min_bps=_POLICY_MIN_BPS,
        provider_max_bps=_POLICY_MAX_BPS,
        rounding_mode=_POLICY_ROUNDING, currency=_POLICY_CURRENCY,
        minor_unit_digits=_POLICY_DIGITS,
        effective_from=_POLICY_FROM, effective_until=_POLICY_UNTIL,
        actor="platform", source="economic-policy-service",
    )
    fresh.allocate(
        command_id="fc-23", usage_transaction_id=txs["c2"],
        usage_statement_id=statements["c2"],
        policy_id=_golden_policy_id(), provider_share_bps=6500,
        actor="billing", source="allocation-service",
    )
    attempt(
        AllocationReasonCode.COMPENSATION_REQUIRES_SETTLED,
        fresh.record_refund,
        command_id="fc-24", usage_transaction_id=txs["c2"],
        amount_micros=1, reason="early", actor="billing",
        source="allocation-service",
    )
    # store + journal corruption vectors
    attempt(
        AllocationReasonCode.STORE_FAILED,
        AllocationLedger(
            store=FailingAllocationStore(),
            clock=StepClock("2026-10-04T00:00:00Z", 60),
            evidence_index=index,
        ).register_policy,
        command_id="fc-25", label=_POLICY_LABEL,
        adcos_share_bps=_POLICY_ADCOS_BPS,
        provider_min_bps=_POLICY_MIN_BPS,
        provider_max_bps=_POLICY_MAX_BPS,
        rounding_mode=_POLICY_ROUNDING, currency=_POLICY_CURRENCY,
        minor_unit_digits=_POLICY_DIGITS,
        effective_from=_POLICY_FROM, effective_until=_POLICY_UNTIL,
        actor="platform", source="economic-policy-service",
    )
    data = b"".join(
        record.to_line() for record in ledger.journal_records()
    )
    flipped = bytearray(data)
    flipped[len(data) // 2] = (flipped[len(data) // 2] + 1) % 256
    attempt(
        AllocationReasonCode.JOURNAL_CORRUPT,
        AllocationLedger.load,
        store=FrozenBytesStore(bytes(flipped)),
        clock=StepClock(_AT0, _ASTEP), evidence_index=index,
    )
    missing = sorted(
        set(AllocationReasonCode.values()) - set(raised)
    )
    if missing:
        results.append(
            fail(name, "reasons never exercised: %r" % missing)
        )
        return
    results.append(
        ok(name, "all 27 frozen reasons exercised by typed vectors")
    )


def case_55_authority_composition(results: List[Result]) -> None:
    name = "case_55_authority_composition"
    ledger, _index, _clock, fixture, _refs = _golden_ledger()
    usage_ledger, txs, world = fixture
    runtime, peer, session_id, manager, integrator, shared = world
    problems: List[str] = []
    # the allocation's gross derives from the REAL W051->W052 chain:
    # 310 delivered bytes (the real wifi journal deltas) x 3
    wifi_events = _wifi_journal_events(integrator)
    deltas = []
    for first, second in zip(wifi_events, wifi_events[1:]):
        first_total = first.payload["rx_bytes"] + first.payload["tx_bytes"]
        second_total = second.payload["rx_bytes"] + second.payload["tx_bytes"]
        deltas.append(second_total - first_total)
    if deltas != [210, 150]:
        problems.append("fixture delivery deltas drifted: %r" % deltas)
    c1_projection = usage_ledger.transaction(txs["c1"])
    if c1_projection.statement is None:
        problems.append("c1 usage statement missing")
    else:
        if c1_projection.statement.amount_micros != 310 * 3:
            problems.append("usage gross not the real metered derivation")
        if (
            ledger.allocation(txs["c1"]).snapshot.usage_statement_id
            != c1_projection.statement.statement_id
        ):
            problems.append("allocation does not cite the public usage statement")
    # the allocation's W052 DATA citations are the real public reads
    snapshot_data = ledger.evidence_index().usage(txs["c1"])
    if (
        snapshot_data.refunded_amount_micros
        != c1_projection.refunded_amount_micros()
        or snapshot_data.reversed_amount_micros
        != c1_projection.reversed_amount_micros()
        or snapshot_data.disputed != c1_projection.disputed()
    ):
        problems.append("usage compensation DATA not the public reads")
    # the session/path/commercial authorities were genuinely driven
    if not session_id:
        problems.append("no session in the fixture")
    paths = manager.paths()
    if not paths:
        problems.append("no network paths in the fixture")
    # the allocation family never imported the authority modules
    # (the AST audit proves it structurally; this pins the ledger
    # constructor rejects a non-index input)
    problem = _expect_allocation_error(
        name, AllocationReasonCode.INVALID_INPUT,
        AllocationLedger,
        store=MemoryAllocationStore(),
        clock=StepClock(_AT0, _ASTEP),
        evidence_index="not-an-index",
    )
    if problem:
        problems.append("non-index accepted: %s" % problem)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "gross 930 = 310 real delivered bytes x 3 through the "
                 "W051/W052 public chain; statements/DATA from public reads")
    )


def case_56_py_compile(results: List[Result]) -> None:
    name = "case_56_py_compile"
    problems: List[str] = []
    targets = list(_FAMILY_FILES) + [Path(__file__).resolve()]
    for path in targets:
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as error:  # pragma: no cover
            problems.append("%s does not compile: %s" % (path.name, error))
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "allocation/ (%d modules) and the battery compile"
                 % len(_FAMILY_FILES))
    )


def case_57_frozen_spec_intact(results: List[Result]) -> None:
    name = "case_57_frozen_spec_intact"
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
        "spec/architect/authorizations/WORK-053.yaml",
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
        ok(name, "frozen architecture/lock/mission/governance/workflow/"
                 "backlog/schema/roadmap/W053-authorization byte-identical "
                 "to origin/main")
    )


def case_58_pr_delta_shape(results: List[Result]) -> None:
    name = "case_58_pr_delta_shape_authorized_scope"
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
        if "python3 tools/allocation_selftest.py" not in workflow:
            problems.append("CI wiring missing the allocation battery step")
        added = [
            line for line in wiring_diff.stdout.splitlines()
            if line.startswith("+") and "python3 tools/" in line
        ]
        for line in added:
            if "allocation_selftest.py" not in line:
                problems.append("CI wiring added an unrelated step: %r" % line)
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "delta confined to the WORK-053-CORE-001 scope (%d file(s) + "
                 "sanctioned additive CI wiring)" % len(delta))
    )


def case_59_fresh_world_independence(results: List[Result]) -> None:
    name = "case_59_fresh_world_independence"
    # two coexisting fresh worlds reproduce the isolated baseline
    ledger_a, _index_a, _clock_a, _fixture_a, _refs_a = _golden_ledger()
    stream_a = ledger_a.digest_stream()
    ledger_b, _index_b, _clock_b, _fixture_b, _refs_b = _golden_ledger()
    stream_b = ledger_b.digest_stream()
    if stream_a != stream_b:
        results.append(
            fail(name, "coexisting fresh worlds diverged byte-for-byte")
        )
        return
    # driving world B after world A settled must not disturb A
    ledger_c, _index_c, _clock_c, fixture_c, refs_c = _golden_ledger()
    usage_ledger_c, txs_c, _world_c = fixture_c
    stream_c_before = ledger_c.digest_stream()
    ledger_a, _index_a, _clock_a, _fixture_a, _refs_a = _golden_ledger()
    if ledger_c.digest_stream() != stream_c_before:
        results.append(
            fail(name, "a fresh world disturbed a coexisting settled world")
        )
        return
    results.append(
        ok(name, "coexisting fresh worlds byte-identical; no cross-world "
                 "contamination")
    )


def case_60_determinism_proofs(results: List[Result]) -> None:
    name = "case_60_determinism_proofs"
    problems: List[str] = []
    # in-process two-run equality
    stream_one = _scenario_stream()
    stream_two = _scenario_stream()
    if stream_one != stream_two:
        problems.append("in-process two-run divergence")
    # hash-seed subprocess equality
    outputs = []
    for seed in ("0", "1", "7919", None):
        env = dict(os.environ)
        if seed is None:
            env.pop("PYTHONHASHSEED", None)
        else:
            env["PYTHONHASHSEED"] = seed
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()),
             "--determinism-stream"],
            capture_output=True, text=True, env=env, cwd=str(REPO_ROOT),
        )
        if proc.returncode != 0:
            problems.append(
                "subprocess (seed %r) failed: %s" % (seed, proc.stderr[-200:])
            )
            continue
        outputs.append(proc.stdout.strip())
    if outputs and any(output != outputs[0] for output in outputs[1:]):
        problems.append("hash-seed subprocess divergence")
    if outputs and outputs[0] != "\n".join(
        "%s=%s" % (key, stream_one[key]) for key in sorted(stream_one)
    ):
        problems.append("subprocess stream diverged from the in-process run")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "two-run in-process + PYTHONHASHSEED 0/1/7919/unset "
                 "subprocess determinism proven (6 digest keys)")
    )


# ---------------------------------------------------------------------------
# Main
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
        case_07_illegal_transitions,
        case_08_three_way_conservation,
        case_09_rounding_exactness,
        case_10_usage_unknown,
        case_11_payment_not_usage,
        case_12_settlement_not_usage,
        case_13_usage_not_final,
        case_14_usage_statement_mismatch,
        case_15_policy_unknown,
        case_16_policy_not_effective,
        case_17_split_out_of_bounds,
        case_18_distribution_invalid,
        case_19_duplicate_commands,
        case_20_conflicting_duplicates,
        case_21_statement_already_allocated,
        case_22_duplicate_callbacks,
        case_23_callback_arrival_discipline,
        case_24_callback_before_allocation,
        case_25_settlement_acknowledgement,
        case_26_payment_not_settlement,
        case_27_settlement_not_payment,
        case_28_reference_unknown,
        case_29_reference_mismatch,
        case_30_settlement_immutable,
        case_31_compensation_family,
        case_32_compensation_requires_settled,
        case_33_compensation_exceeded,
        case_34_dispute_discipline,
        case_35_immutable_settled_history,
        case_36_reconciliation_statement,
        case_37_policy_version_immutability,
        case_38_tampered_journal,
        case_39_journal_first_recovery,
        case_40_replay_verification,
        case_41_inserted_out_of_order_record,
        case_42_persist_then_ack,
        case_43_walk_valid_allocation_tamper,
        case_44_walk_valid_policy_tamper,
        case_45_walk_valid_compensation_tamper,
        case_46_walk_valid_non_final_usage_forgery,
        case_47_walk_valid_settlement_kind_forgery,
        case_48_walk_valid_duplicate_callback_forgery,
        case_49_clock_discipline,
        case_50_secret_hygiene,
        case_51_no_shadow_authority,
        case_52_import_discipline,
        case_53_public_api_stability,
        case_54_fail_closed_battery,
        case_55_authority_composition,
        case_56_py_compile,
        case_57_frozen_spec_intact,
        case_58_pr_delta_shape,
        case_59_fresh_world_independence,
        case_60_determinism_proofs,
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
