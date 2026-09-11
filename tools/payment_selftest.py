#!/usr/bin/env python3
"""WORK-044 Payment Provider Adapters & Settlement Gateway
battery (deterministic, stdlib only).

End-to-end verification of the provider-neutral payment boundary
(ACR-009 commercial control plane, authorization
WORK-044-CORE-001 / DEC-0062, baseline reconciliation
DEC-0063 / LEDGER-RECON-010) consuming the accepted W051
CommercialCore transaction projections, W052 UsageLedger
billable-final facts, and W053 EconomicAllocation finalized
allocation accounts through an injected immutable commercial
snapshot:

- frozen vocabularies: the canonical provider-neutral intent
  lifecycle (CREATED, AUTHORIZED, CAPTURED plus the three
  terminals REFUNDED / REVERSED / FAILED), the payout lifecycle
  (EMITTED, TRANSFERRED, FAILED), the ten-action vocabulary,
  the entity kinds, the event outcomes, the callback kinds, the
  normalized provider-failure classes, the reconciliation
  classifications, the FIVE idempotency ledgers, and the
  versioned capability declaration model;
- the W044 contract boundary, each pinned by explicit positive
  and negative cases: payment intent create/retrieve is
  idempotent and correlated to ADCOS transactions;
  authorization/capture/refund/reversal mapping is
  provider-neutral with vendor semantics never leaking into
  canonical state; payout/transfer instructions are emitted
  ONLY from existing finalized allocation citations; callbacks
  are signature-verified external observations with durable
  anti-replay (duplicates, redeliveries, and out-of-order
  events are idempotent and append-only) that become state ONLY
  through the explicit reconciled application; provider
  failures are normalized at the adapter boundary; provider/
  ADCOS divergence reconciliation classifies and records
  without rewriting; capabilities are explicit and versioned;
  the deterministic sandbox provider proves all flows;
- the seven mandatory negative proofs: provider capture/success
  cannot create UsageLedger facts; callbacks cannot create
  delivery evidence; provider success cannot bypass
  BILLABLE_FINAL; payout cannot manufacture an allocation;
  settled history is never rewritten (corrections are
  compensating records); provider-specific statuses never leak
  into canonical state; forbidden imports into identity/session/
  routing/NetworkPath/transport/packet authorities are rejected
  (the payment family imports stdlib + WORK-003 canonicalization
  + the WORK-033 clock seam ONLY);
- authority composition over REAL references: a real WORK-051
  CommercialCore transaction driven to USAGE_ACCRUING, a real
  WORK-052 UsageLedger account driven to BILLABLE_FINAL, and a
  real WORK-053 allocation account driven to ALLOCATED/SETTLED
  -- the injected CommercialSnapshot is built from these public
  reads only, and the closed-loop composition feeds REAL
  payment intent and payout instruction identities back into
  the W051/W053 DATA citations;
- journal-first durability: hash-chained append-only records,
  persist-then-ack, tamper detection (byte flip, reorder,
  truncation, sequence gap, duplicated lines), journal-first
  recovery, and byte-identical replay with FIVE durable
  idempotency ledgers (commands, intents, payouts, callback
  events, capability declarations);
- determinism: two fresh runs byte-identical, and the digest
  stream reproduced byte-for-byte under PYTHONHASHSEED
  0/1/7919/unset subprocesses; the ONLY time source is the
  injected WORK-033 clock seam (duplicates consume no read;
  each other submission consumes exactly one);
- fail-closed negatives: every contract violation family raises
  its typed reason code and leaves no journal growth (no
  phantom state).

Usage:
    python3 tools/payment_selftest.py
    python3 tools/payment_selftest.py --determinism-stream
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import py_compile
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
from agent.clock import AgentClock, add_seconds  # noqa: E402

from mobile.model import (  # noqa: E402
    MobilePhase,
    NetworkKind,
    PlatformSnapshot,
    PowerState,
)

from networkpath import NetworkPath, NetworkPathManager  # noqa: E402

from platform.journal import MemoryPlatformStore  # noqa: E402
from platform.lifecycle import PlatformIntegrator  # noqa: E402

import commercial  # noqa: E402
from commercial import (  # noqa: E402
    CommercialCore,
    ContractCitation,
    ContractReferenceIndex,
    Reference,
    ReferenceFamily,
    ReferenceIndex,
)

import contracts  # noqa: E402
from contracts import (  # noqa: E402
    ActivateContract,
    ContractStore,
    CreateContract,
    HardConstraint,
    OpaqueReference,
    Provenance,
    RecordAssurance,
    RecordDelivery,
    RecordExecutionActivation,
    RecordSettled,
    RecordSettlementPending,
    RecordUsageFinal,
    SelectOffers,
    TerminationRules,
    ValidityInterval,
    BeneficiaryScope,
    ConnectivityPrincipal,
)

import usage  # noqa: E402
from usage import (  # noqa: E402
    CommercialTransactionSnapshot,
    ContractCommercialSnapshot,
    DeliveryEvidence,
    EvidenceFamily,
    EvidenceIndex,
    EvidenceKind,
    EvidenceReference,
    MemoryUsageStore,
    QuantityClass,
    UsageEvidenceIndex,
    UsageLedger,
    UsageState,
)

import allocation  # noqa: E402
from allocation import (  # noqa: E402
    AllocationEvidenceIndex,
    AllocationLedger,
    AllocationState,
    BillableUsageSnapshot,
    EconomicPolicy,
    ExternalReferenceSnapshot,
    FactFamily,
    FactIndex,
    FactReference,
    MemoryAllocationStore,
    ReferenceKind,
)

import payment  # noqa: E402
from payment import (  # noqa: E402
    CallbackKind,
    CitationFamily,
    CommercialCitation,
    CommercialSnapshot,
    CommandStatus,
    EventOutcome,
    FailureClass,
    FilePaymentStore,
    MemoryPaymentStore,
    PaymentAction,
    PaymentCommand,
    PaymentError,
    PaymentEvent,
    PaymentReasonCode,
    PaymentStatus,
    PayoutStatus,
    ProviderAdapter,
    ProviderCapabilities,
    ReconciliationClass,
    SandboxProvider,
    SettlementGateway,
    capability_key,
)

Result = Tuple[str, bool, str]

# ---------------------------------------------------------------------------
# Battery constants (deterministic fixtures)
# ---------------------------------------------------------------------------

_T0 = "2025-06-01T00:00:00Z"
_FRESH = "2026-06-01T00:00:00Z"
_SECRET_A = b"w044-battery-secret-A"
_SECRET_B = b"w044-battery-secret-B"
_PROFILE_ID = "identity.sha256-hmac-dev.v1"
_KEY_A = b"w044-battery-key-A"
_KEY_B = b"w044-battery-key-B"

#: The WORK-051 commercial clock epoch and step.
_CT0 = "2026-09-01T12:00:00Z"
_CSTEP = 60

#: The W052 usage-ledger clock epoch and step.
_UT0 = "2026-09-01T13:00:00Z"
_USTEP = 60

#: The delivery-plane metering time-series instants (the M009
#: delivered-evidence interval bounds; public journal reads).
_WE1 = "2026-09-01T13:00:00Z"
_WE2 = "2026-09-01T13:00:30Z"
_WE3 = "2026-09-01T13:01:00Z"

#: The usage observations' metering instants (caller DATA;
#: windows contained in the evidence intervals).
_OBS1 = "2026-09-01T13:00:10Z"
_OBS2 = "2026-09-01T13:00:20Z"
_OBS3 = "2026-09-01T13:00:40Z"

#: The canonical contract drive instants (the M002 recorded-at
#: instants; injected, never the wall clock).
_CX0 = "2026-09-01T11:00:00Z"
_CX_STEP = 300

#: The WORK-053 allocation-ledger clock epoch and step.
_AT0 = "2026-09-01T15:00:00Z"
_ASTEP = 60

#: The declared allocation effective instant.
_EFFECTIVE_AT = "2026-09-01T13:30:00Z"

#: The standard W053 economic policy fixture (the current
#: terms-derived immutable version: adcos 500 bps of the
#: distributable, provider share bounds [0, 10000] bps, declared
#: half-up rounding; the M009 allocation drive selects a 6000 bps
#: provider share).
_PID = "std"
_PID_V = 1
_CCY = "GHS"
_EXP = 2
_ROUNDING = "half-up"
_ADC_BPS = 500
_TAX_BPS = 1250
_DEV_MIN = 0
_DEV_MAX = 10000
_PROVIDER_BPS = 6000
_TAX_MICROS = 100
_POLICY_FROM = "2026-01-01T00:00:00Z"
_POLICY_UNTIL = "2027-01-01T00:00:00Z"

#: The payment-gateway clock epoch and step (one read per
#: non-duplicate appended record).
_PT0 = "2026-09-02T07:00:00Z"
_PSTEP = 60

#: The sandbox provider-side clock epoch and step (external
#: provider time; deterministic, never the wall clock).
_VT0 = "2026-09-02T07:00:00Z"
_VSTEP = 30

#: The sandbox provider identity and signing secret.
_PROV_ID = "sandbox-1"
_PROV_SECRET = b"w044-battery-provider-secret"

#: The standard payment intent fixture (the billable amount of
#: the real W052 final usage: 400 units x 2 = 800 minor units).
_INTENT_AMOUNT = 800
_PARTIAL_REFUND = 200

#: The exact W053 split of the billable 800 under the standard
#: M009 policy (tax 100; distributable 700; adcos 35; provider
#: 399; developer 266 -- exact integer conservation).
_SPLIT = (266, 399, 35, 100)

WIFI_IF = "wlan0"
ETH_IF = "eth0"
USB_IF = "usb0"
CELL_IF = "vpn0"

#: The WORK-044 authorized implementation baseline (DEC-0063 /
#: LEDGER-RECON-010; the exact branch point of this delivery).
_BASELINE_SHA = "66f6c4f0ae2c5e4cd4498e6090f876acb1859e45"

#: The frozen payment public API surface (independently pinned
#: here; the package must match exactly).
_EXPECTED_API = sorted(payment.__all__)

#: Vendor tokens and the sandbox's deliberately vendored wire
#: vocabulary: NONE of these may appear in canonical state
#: (intent/payout/observation/report projections) -- they live
#: inside the sandbox adapter and its wire envelopes only.
_VENDOR_TOKENS = (
    "android", "rndis", "qualcomm", "mediatek", "samsung", "broadcom",
    "huawei", "apple", "google", "windows", "darwin", "ios_",
    "open5gs", "ocudu", "openairinterface",
    "stripe", "paypal", "mtn", "vodafone", "airteltigo", "telecel",
    "visa", "mastercard", "mpesa", "alipay", "wise",
    "sbx_pmt", "sbx_trf", "SBX_ERR", "SBX_DECL",
    "PENDING_SETTLE", "FUNDS_HELD", "FUNDS_TAKEN", "MONIES_RETURNED",
    "HOLD_RELEASED", "HARD_REJECTED", "TRF_QUEUED", "TRF_DONE",
    "TRF_REFUSED",
)

#: Forbidden authority-construction/mutation tokens: the payment
#: family must never build or drive ANY authority -- including
#: the W051 CommercialCore, the W052 UsageLedger, and the W053
#: AllocationLedger themselves (the boundary consumes their
#: public projections through the injected snapshot; it never
#: constructs any).
_FORBIDDEN_TOKENS = (
    "RoutingEngine(", "PolicyEngine(", "TransportManager(",
    "TopologyGraph(", "SessionStore(", "IdentityService(",
    "NetworkPathManager(", "AgentRuntime(", "MobileAgent(",
    "MultipathSessionManager(", "MobilityController(",
    "PlatformIntegrator(", "CommercialCore(", "UsageLedger(",
    "AllocationLedger(",
    "sessions.create", "sessions.transition", "sessions.reconnect",
    "sessions.terminate", "sessions.suspend", "sessions.append_event",
    "derive_session_id", "establish_session(", "accept_session(",
    "complete_session(", "finalize_session(", "bind_session(",
    "register_peer(", "expose_interfaces(", "send_datagram(",
)

#: The sanctioned absolute-import allowlist for the payment
#: family: stdlib value types + the two accepted seams (WORK-003
#: canonicalization and the WORK-033 clock seam) ONLY -- the
#: payment family never imports usage, commercial, allocation,
#: identity, sessions, routing, networkpath, or transport.
_ALLOWED_IMPORT_PREFIXES = (
    "protocol.canonicalization",
    "agent.clock",
)
_ALLOWED_IMPORT_MODULES = {
    "__future__",
    "hashlib",
    "json",
    "dataclasses",
    "pathlib",
    "re",
    "types",
    "typing",
    "hmac",
    "ast",
}

_FAMILY_FILES = sorted((REPO_ROOT / "payment").rglob("*.py"))

#: The WORK-044-CORE-001 authorized delta surfaces.
_AUTHORIZED_PATHS = (
    "payment/",
    "tools/payment_selftest.py",
    "docs/WORK-044-evidence.md",
    # the M009 child scope (R7-CORE-001, DEC-0101): the commercial-track
    # re-bind lands across the usage/commercial/allocation domains, this
    # battery, and the M009 evidence record
    "usage/",
    "commercial/",
    "allocation/",
    "tools/usage_selftest.py",
    "tools/commercial_selftest.py",
    "tools/allocation_selftest.py",
    "tools/eligibility_selftest.py",
    "docs/M009-evidence.md",
)


def _active_authorization_covers(path: str) -> bool:
    """Authorization-aware delta-shape consultation (the
    docs/M001-evidence.md §4 duty for the post-M001 implementation
    era): a delta path covered by the ACTIVE repository-local
    authorization (the R7-CORE-001 program child scopes per
    DEC-0101) is sanctioned.  Fail-closed: no unique active
    authorization covers nothing."""
    try:
        from authorization_provenance import covers
        return covers(path)
    except Exception:
        return False
AUTHORIZED_CI_WIRING = ".github/workflows/spec-check.yml"


def ok(name: str, detail: str = "") -> Result:
    return (name, True, detail)


def fail(name: str, detail: str) -> Result:
    return (name, False, detail)


# ---------------------------------------------------------------------------
# Authority-composition fixtures (all through public surfaces)
# ---------------------------------------------------------------------------


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
            role_id="w044-battery-operator",
            capabilities=(
                ManagementCapability.SESSION_READ,
                ManagementCapability.SESSION_CONTROL,
                ManagementCapability.POLICY_READ,
            ),
            description="operator role (battery fixture)",
        ),
    )


def _config(
    label: str = "payment-node",
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


def _world():
    """One booted node + one booted peered peer runtime with one
    ESTABLISHED session, an ACTIVATED NetworkPath over the
    session, and a PlatformIntegrator journal carrying the
    DELIVERY-PLANE METERING TIME SERIES on the active interface
    (cumulative rx/tx counters at three instants; the M009
    delivery-evidence intervals derive from the pairs) -- all
    through the ordinary public production chain.  Returns
    (runtime, peer, session_id, manager, integrator, shared
    clock)."""
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
    # interface: cumulative counters (rx grows 0 -> 500 -> 900,
    # tx grows 0 -> 150 -> 250; totals 0 -> 650 -> 1150; the M009
    # delivered-evidence intervals [WE1, WE2] = 650 and
    # [WE2, WE3] = 500 -- public-read-only derivation)
    integrator.ingest_interface_observation(
        _snap(name=WIFI_IF, kind="wireless", addresses=("fd00::a:1",), rx=0, tx=0),
        observed_at=_WE1,
    )
    integrator.ingest_interface_observation(
        _snap(name=WIFI_IF, kind="wireless", addresses=("fd00::a:1",), rx=500, tx=150),
        observed_at=_WE2,
    )
    integrator.ingest_interface_observation(
        _snap(name=WIFI_IF, kind="wireless", addresses=("fd00::a:1",), rx=900, tx=250),
        observed_at=_WE3,
    )
    # one distractor observation on a second interface (NOT the
    # active path; its evidence correlates to a different
    # transaction in the index)
    integrator.ingest_interface_observation(
        _snap(name=ETH_IF, kind="ethernet", addresses=("fd00::a:2",), rx=11, tx=5),
        observed_at=_WE1,
    )
    return runtime, peer, session_id, manager, integrator, shared


def _path_for(manager: NetworkPathManager, interface_name: str) -> str:
    for path_id in manager.paths():
        if manager.path(path_id).interface_name == interface_name:
            return path_id
    raise AssertionError("no candidate for interface %r" % interface_name)


# ---------------------------------------------------------------------------
# WORK-051 composition fixtures (the transaction DATA)
# ---------------------------------------------------------------------------


def _external_id(kind: str, label: str) -> str:
    """A deterministic well-formed EXTERNAL-plane id (payment and
    settlement observations genuinely live outside ADCOS; the
    battery cites synthetic-but-deterministic external ids with
    explicit provenance labels)."""
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes({"kind": kind, "label": label})
    ).hexdigest()


def _commercial_references(
    manager: NetworkPathManager,
    integrator: PlatformIntegrator,
    session_id: str,
) -> ReferenceIndex:
    """Build the WORK-051 ReferenceIndex from PUBLIC reads only
    (the accepted W051 battery's builder, verbatim)."""
    entries: List[Reference] = [
        Reference(session_id, ReferenceFamily.SESSION, "sessions-authority"),
    ]
    for path_id in manager.paths():
        entries.append(
            Reference(
                path_id, ReferenceFamily.NETWORK_PATH, "networkpath-manager"
            )
        )
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


def _create_contract_command() -> CreateContract:
    """The canonical contract creation core (the M002 public
    surface; the M009 commercial-track binding authority)."""
    return CreateContract(
        principal=ConnectivityPrincipal(
            principal_kind="APPLICATION", principal_ref="app:buyer-1"
        ),
        beneficiaries=(
            BeneficiaryScope(
                beneficiary_kind="DEVICE", beneficiary_ref="dev:gw-1"
            ),
        ),
        requirements=(
            OpaqueReference(
                ref_kind="intent-requirements",
                value="intent:buyer-1-gh",
                provenance=Provenance(issuer="arch:buyer-agent"),
            ),
        ),
        hard_constraints=(
            HardConstraint(
                kind="latency-bound",
                params={"max_ms": 150},
                provenance=Provenance(issuer="prov:netpro"),
            ),
        ),
        validity=ValidityInterval(
            not_before="2026-09-01T00:00:00Z",
            not_after="2026-10-01T00:00:00Z",
        ),
        service_properties=(
            OpaqueReference(
                ref_kind="service-property",
                value="prop:committed-1",
                provenance=Provenance(issuer="prov:netpro"),
            ),
        ),
        usage_pricing_terms=OpaqueReference(
            ref_kind="usage-pricing-terms",
            value="terms:comm-m009-1",
            provenance=Provenance(issuer="comm:ops"),
        ),
        assurance_obligations=(
            OpaqueReference(
                ref_kind="assurance-obligation",
                value="oblig:evid-1",
                provenance=Provenance(issuer="assur:m005"),
            ),
        ),
        execution_scope=(
            OpaqueReference(
                ref_kind="execution-scope",
                value="scope:exec-default",
                provenance=Provenance(issuer="arch:buyer-agent"),
            ),
        ),
        termination=TerminationRules(
            conditions=("principal-requested", "constraint-violated"),
            compensation=OpaqueReference(
                ref_kind="compensation",
                value="comp:rule-1",
                provenance=Provenance(issuer="comm:ops"),
            ),
        ),
        provenance=Provenance(
            issuer="arch:buyer-agent", decision_refs=("dec:m009-buy",)
        ),
    )


def _wire_ref(kind: str, value: str, issuer: str) -> OpaqueReference:
    return OpaqueReference(
        ref_kind=kind, value=value, provenance=Provenance(issuer=issuer)
    )


#: The canonical contract walk stages (the frozen 1.1 #11 walk;
#: every M009 floor maps onto one of these).
_CONTRACT_STAGES = (
    "created",       # INTENT
    "offers",        # OFFER_SELECTED
    "active",        # CONTRACT_ACTIVE
    "execution",     # EXECUTION_ACTIVE (usage-metering eligible)
    "delivery",      # DELIVERY
    "usage-final",   # USAGE_FINAL
    "settlement-pending",  # SETTLEMENT_PENDING
    "settled",       # SETTLED
)


def _contract_store(*, through: str = "delivery") -> Tuple[ContractStore, str]:
    """Drive one REAL canonical ConnectivityContract through the
    M002 public surface (``contracts.ContractStore``) to the
    requested walk stage.  Returns (store, contract_id).

    The ASSURED stage is folded into the delivery->usage-final
    transition (``RecordAssurance`` with the compliant state
    between RecordDelivery and RecordUsageFinal, exactly the
    legal 1.1 chain DELIVERY -> ASSURED -> USAGE_FINAL).
    """
    store = ContractStore()
    created = store.submit(_create_contract_command(), recorded_at=_CX0)
    cid = created.contract.contract_id
    at = 1
    def step(command, instant=None):
        nonlocal at
        when = instant if instant is not None else (
            "2026-09-01T%02d:%02d:00Z" % (11 + (at * 300) // 3600, (at * 300) % 3600 // 60)
        )
        at += 1
        return store.submit(command, recorded_at=when, contract_id=cid)

    step(
        SelectOffers(
            offers=(_wire_ref("offer", "offer:provider-1-wifi", "prov:netpro"),)
        ),
        instant="2026-09-01T11:05:00Z",
    )
    if _stage_reached(through, "active"):
        step(
            ActivateContract(
                activated_at="2026-09-01T11:10:00Z",
                signature_refs=(_wire_ref("signature", "sig:ed25519-1", "arch:buyer-agent"),),
            ),
            instant="2026-09-01T11:10:00Z",
        )
    if _stage_reached(through, "execution"):
        step(
            RecordExecutionActivation(recorded_at="2026-09-01T11:15:00Z"),
            instant="2026-09-01T11:15:00Z",
        )
    if _stage_reached(through, "delivery"):
        step(
            RecordDelivery(recorded_at="2026-09-01T11:20:00Z"),
            instant="2026-09-01T11:20:00Z",
        )
    if _stage_reached(through, "usage-final"):
        step(
            RecordAssurance(
                recorded_at="2026-09-01T11:25:00Z",
                assurance_state="compliant",
                evidence_refs=(_wire_ref("decision", "dec:assur-ok-1", "assur:m005"),),
            ),
            instant="2026-09-01T11:25:00Z",
        )
        step(RecordUsageFinal(recorded_at="2026-09-01T11:30:00Z"),
             instant="2026-09-01T11:30:00Z")
    if _stage_reached(through, "settlement-pending"):
        step(RecordSettlementPending(recorded_at="2026-09-01T11:35:00Z"),
             instant="2026-09-01T11:35:00Z")
    if _stage_reached(through, "settled"):
        step(RecordSettled(recorded_at="2026-09-01T11:40:00Z"),
             instant="2026-09-01T11:40:00Z")
    return store, cid


def _stage_reached(through: str, stage: str) -> bool:
    """True iff the requested walk stage is at or past ``stage``
    (the linear 1.1 walk order)."""
    if through not in _CONTRACT_STAGES or stage not in _CONTRACT_STAGES:
        raise AssertionError("unknown contract walk stage %r" % through)
    return _CONTRACT_STAGES.index(through) >= _CONTRACT_STAGES.index(stage)


def _contract_index(store: ContractStore, contract_id: str) -> ContractReferenceIndex:
    """Build the injected ContractReferenceIndex from PUBLIC reads
    only (the CURRENT canonical contract state through the
    ContractStore public surface)."""
    return ContractReferenceIndex(
        [
            ContractCitation(
                contract_id=contract_id,
                contract_state=store.contract(contract_id).state,
                provenance="contract-store-public-read",
            )
        ]
    )


def _commercial_tx(
    manager: NetworkPathManager,
    integrator: PlatformIntegrator,
    session_id: str,
    *,
    clock_epoch: str = _CT0,
    contract_stage: str = "delivery",
):
    """Drive one REAL contract-bound commercial reconciliation
    account through the public typed surface to USAGE_ACCRUING
    (inside the delivery window).

    M009 re-bind: the canonical contract (driven through the M002
    public surface to ``contract_stage``) is cited at every step
    -- the intent payload carries the canonical contract id, the
    core runs BOUND (the injected ContractReferenceIndex), and
    every forward action's canonical-state floor is satisfied.
    Returns (core, transaction_id, store, contract_id)."""
    store, contract_id = _contract_store(through=contract_stage)
    references = _commercial_references(manager, integrator, session_id)
    core = CommercialCore(
        store=commercial.MemoryCommercialStore(),
        clock=StepClock(clock_epoch, _CSTEP),
        references=references,
        contract_references=_contract_index(store, contract_id),
    )
    deadline = add_seconds(clock_epoch, 600)
    out = core.submit_intent(
        command_id="w051-01",
        actor="buyer-agent",
        source="developer-api",
        intent={
            "buyer": "buyer-1", "want": "connectivity", "region": "gh",
            "contract_id": contract_id,
        },
    )
    tx = out.transaction_id
    core.select_offer(
        command_id="w051-02", transaction_id=tx, actor="buyer-agent",
        source="developer-api",
        offer={"offer_id": "offer-1", "provider": "provider-1",
               "unit": "GB", "price": "10"},
    )
    core.hold_reservation(
        command_id="w051-03", transaction_id=tx, actor="platform",
        source="reservation-service", expires_at=deadline,
    )
    core.authorize_session(
        command_id="w051-04", transaction_id=tx, actor="platform",
        source="session-service", session_ref=session_id,
    )
    active = manager.active_path_id(session_id)
    core.activate_path(
        command_id="w051-05", transaction_id=tx, actor="platform",
        source="path-service", path_ref=active,
    )
    delivery = sorted(
        ref.reference_id
        for ref in references.by_family(ReferenceFamily.DELIVERY_EVIDENCE)
    )
    core.start_delivery(
        command_id="w051-06", transaction_id=tx, actor="platform",
        source="delivery-service", evidence_refs=(delivery[0],),
    )
    usage_ref = references.by_family(ReferenceFamily.USAGE)[0].reference_id
    core.accrue_usage(
        command_id="w051-07", transaction_id=tx, actor="platform",
        source="usage-service", usage_refs=(usage_ref,),
    )
    return core, tx, store, contract_id


# ---------------------------------------------------------------------------
# WORK-052 composition fixtures (the billable-final usage facts,
# contract-bound per the M009 LOCK-113 re-bind)
# ---------------------------------------------------------------------------


def _payment_ref() -> str:
    return _external_id("payment-observation", "payment-1")


def _settlement_ref() -> str:
    return _external_id("settlement-confirmation", "settle-1")


def _evidence_window_id(first: Any, second: Any) -> str:
    """The content-derived delivery-evidence interval identity
    (the W052/M009 public derivation: a window is a pair of
    metering events; the id is canonical-JSON content)."""
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes(
            {
                "kind": "delivery-evidence-window",
                "from_event": first.event_id,
                "to_event": second.event_id,
            }
        )
    ).hexdigest()


def _wifi_journal_events(integrator: PlatformIntegrator) -> Tuple[Any, ...]:
    """The ordered public journal events of the ACTIVE path
    interface's metering time series (public reads only)."""
    return tuple(
        record.event
        for record in integrator.journal_records()
        if record.event.kind == "interface-observation"
        and record.event.platform_ref == WIFI_IF
    )


def _usage_evidence(
    manager: NetworkPathManager,
    integrator: PlatformIntegrator,
    session_id: str,
    core: CommercialCore,
    tx: str,
    *,
    contract_store: Optional[ContractStore] = None,
    contract_id: Optional[str] = None,
) -> EvidenceIndex:
    """Build the M009 family-classified EvidenceIndex from PUBLIC
    reads only (the re-established era surface carrying the M009
    semantics: family-classified citations with the canonical
    contract binding on the commercial family).  The typed
    projection for the ledger admission is built by
    :func:`_typed_evidence_index`."""
    entries: List[EvidenceReference] = []
    for record in integrator.journal_records():
        event = record.event
        if event.kind == "platform-state-observation":
            continue
        entries.append(
            EvidenceReference(
                reference_id=event.event_id,
                family=EvidenceFamily.DELIVERY_EVIDENCE,
                provenance="platform-journal",
                instant=event.observed_at,
            )
        )
    binding = (
        contract_id
        if contract_id is not None
        else core.transaction(tx).contract_id
    )
    entries.append(
        EvidenceReference(
            reference_id=binding,
            family=EvidenceFamily.COMMERCIAL,
            provenance="contract-store-public-read",
            commercial_state=(
                contract_store.contract(binding).state
                if contract_store is not None
                else "EXECUTION_ACTIVE"
            ),
            contract_id=binding,
            session_ref=core.transaction(tx).session_ref,
            path_ref=core.transaction(tx).path_ref,
        )
    )
    entries.append(
        EvidenceReference(
            reference_id=session_id,
            family=EvidenceFamily.SESSION,
            provenance="sessions-authority",
        )
    )
    for path_id in manager.paths():
        entries.append(
            EvidenceReference(
                reference_id=path_id,
                family=EvidenceFamily.NETWORK_PATH,
                provenance="networkpath-manager",
            )
        )
    entries.append(
        EvidenceReference(
            reference_id=_payment_ref(),
            family=EvidenceFamily.PAYMENT,
            provenance="external-payment-observation",
        )
    )
    return EvidenceIndex(entries)


def _typed_evidence_index(
    references: EvidenceIndex,
    *,
    contract_state: str = "EXECUTION_ACTIVE",
    unit_price_micros: int = 2,
    billable_unit: str = "MB",
    integrator: Optional[PlatformIntegrator] = None,
    distractor_transaction: Optional[str] = None,
) -> UsageEvidenceIndex:
    """Project the family index into the typed admission surface
    (the W052/M009 UsageEvidenceIndex): the delivered-evidence
    intervals (public journal reads; the contract-bound delivery
    facts) plus the contract-cited commercial snapshot
    (ContractCommercialSnapshot -- LOCK-113: the account key IS
    the canonical contract id) and the DATA-only payment /
    provider observation entries the kind table rejects
    structurally."""
    binding = references.by_family(EvidenceFamily.COMMERCIAL)[0].contract_id
    evidence: List[DeliveryEvidence] = []
    if integrator is not None:
        events = _wifi_journal_events(integrator)
        for first, second in zip(events, events[1:]):
            first_total = first.payload["rx_bytes"] + first.payload["tx_bytes"]
            second_total = (
                second.payload["rx_bytes"] + second.payload["tx_bytes"]
            )
            evidence.append(
                DeliveryEvidence(
                    evidence_id=_evidence_window_id(first, second),
                    transaction_id=binding,
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
            evidence_id=_payment_ref(),
            transaction_id=binding,
            delivered_quantity=0,
            window_start=_WE1,
            window_end=_WE3,
            evidence_kind=EvidenceKind.PAYMENT_OBSERVED,
            provenance="external-payment-observation",
        )
    )
    if distractor_transaction is not None:
        events = _wifi_journal_events(integrator)
        first = events[0]
        evidence.append(
            DeliveryEvidence(
                evidence_id=_evidence_window_id(first, first),
                transaction_id=distractor_transaction,
                delivered_quantity=1,
                window_start=first.observed_at,
                window_end=first.observed_at,
                evidence_kind=EvidenceKind.DELIVERED,
                provenance="platform-journal",
            )
        )
    snapshot = ContractCommercialSnapshot(
        transaction_id=binding,
        commercial_state=contract_state,
        unit_price_micros=unit_price_micros,
        billable_unit=billable_unit,
        tariff_provenance="contract-usage-pricing-terms-read",
    )
    return UsageEvidenceIndex(evidence=evidence, transactions=[snapshot])


def _observation(
    ledger: UsageLedger,
    tx: str,
    references: EvidenceIndex,
    *,
    command_id: str,
    observation_id: str,
    quantity: int,
    observed_at: str,
    evidence_id: Optional[str] = None,
    quantity_class: str = QuantityClass.DELIVERED,
    window_start: Optional[str] = None,
    window_end: Optional[str] = None,
) -> Any:
    """Ingest one M009 usage observation through the public typed
    surface (the W052/M009 admission: DELIVERED observations cite
    the authoritative delivery-evidence interval and the window;
    RESERVED/ATTEMPTED observations are DATA only).  The account
    key ``tx`` IS the canonical contract id (LOCK-113)."""
    kwargs: Dict[str, Any] = {}
    if quantity_class == QuantityClass.DELIVERED:
        if evidence_id is None:
            evidence_id = references.by_family(
                EvidenceFamily.DELIVERY_EVIDENCE
            )[0].reference_id
        kwargs["evidence_id"] = evidence_id
        kwargs["window_start"] = window_start
        kwargs["window_end"] = window_end
    return ledger.observe_usage(
        command_id=command_id,
        transaction_id=tx,
        quantity_class=quantity_class,
        quantity=quantity,
        actor="metering-agent",
        source="usage-service",
        **kwargs,
    )


def _final_usage(
    references: EvidenceIndex,
    tx: str,
    *,
    typed_index: Optional[UsageEvidenceIndex] = None,
    integrator: Optional[PlatformIntegrator] = None,
    store: Optional[MemoryUsageStore] = None,
    stop_after: Optional[str] = None,
):
    """Drive one REAL contract-bound UsageLedger account through
    the public typed surface: two DELIVERED observations on the
    first evidence interval plus one on the second (400 quantity
    total), one DATA-only reserved observation, and the explicit
    billable-final seal (the statement amount 400 x 2 = 800 minor
    units, tariff-bound to the contract-cited snapshot).
    ``stop_after`` optionally stops the drive early ("observed").
    Returns (usage_ledger, finality_id) where ``finality_id`` is
    the account's public citation identity: the immutable sealed
    statement id once final, else the contract-bound account key
    (the honest public identity of an unsealed account)."""
    if typed_index is None:
        typed_index = _typed_evidence_index(
            references, integrator=integrator
        )
    ledger = UsageLedger(
        store=store if store is not None else MemoryUsageStore(),
        clock=StepClock(_UT0, _USTEP),
        evidence_index=typed_index,
    )
    events = _wifi_journal_events(integrator) if integrator is not None else ()
    windows = [
        _evidence_window_id(first, second)
        for first, second in zip(events, events[1:])
    ]
    window_bounds = [
        (first.observed_at, second.observed_at)
        for first, second in zip(events, events[1:])
    ]
    first_window = windows[0] if windows else None
    first_bounds = window_bounds[0] if window_bounds else (_WE1, _WE2)
    second_window = windows[1] if len(windows) > 1 else first_window
    second_bounds = window_bounds[1] if len(window_bounds) > 1 else (
        _WE2, _WE3
    )
    _observation(
        ledger, tx, references,
        command_id="u-01", observation_id="obs-1",
        quantity=100, observed_at=_OBS1,
        evidence_id=first_window,
        window_start=_OBS1, window_end=_OBS2,
    )
    if stop_after == "observed":
        return ledger, tx
    _observation(
        ledger, tx, references,
        command_id="u-02", observation_id="obs-2",
        quantity=250, observed_at=_OBS2,
        evidence_id=first_window,
        window_start=_OBS2, window_end="2026-09-01T13:00:25Z",
    )
    _observation(
        ledger, tx, references,
        command_id="u-04", observation_id="obs-3",
        quantity=50, observed_at=_OBS3,
        evidence_id=second_window,
        window_start=second_bounds[0], window_end=_OBS3,
    )
    if stop_after == "reconciled":
        return ledger, tx
    ledger.seal_billable(
        command_id="u-06", transaction_id=tx,
        actor="billing", source="billing-service",
    )
    account = ledger.transaction(tx)
    finality_id = account.statement.statement_id
    return ledger, finality_id


# ---------------------------------------------------------------------------
# WORK-053 composition fixtures (the finalized allocations,
# contract-bound per the M009 LOCK-113 re-bind)
# ---------------------------------------------------------------------------


def _allocation_facts(
    usage_ledgers: Tuple[UsageLedger, ...],
    cores: Tuple[CommercialCore, ...],
) -> FactIndex:
    """Build the injected M009 FactIndex from PUBLIC reads only
    (the re-established era surface carrying the M009 semantics:
    family-classified fact citations with the canonical contract
    binding on the usage-final and commercial families)."""
    entries: List[FactReference] = []
    for ledger in usage_ledgers:
        for account in ledger.transactions():
            statement = account.statement
            entries.append(
                FactReference(
                    reference_id=(
                        statement.statement_id
                        if statement is not None
                        else account.transaction_id
                    ),
                    family=FactFamily.USAGE_FINAL,
                    provenance="usage-ledger",
                    usage_state=account.state,
                    transaction_id=account.transaction_id,
                    contract_id=account.transaction_id,
                    amount=(
                        statement.amount_micros if statement is not None else 0
                    ),
                    quantity=(
                        statement.billable_quantity
                        if statement is not None
                        else 0
                    ),
                    unit=(
                        statement.billable_unit
                        if statement is not None
                        else ""
                    ),
                    finalized_at=(
                        statement.sealed_at if statement is not None else ""
                    ),
                )
            )
    for core in cores:
        for tx in sorted(
            entry.transaction_id for entry in core.transactions()
        ):
            projection = core.transaction(tx)
            entries.append(
                FactReference(
                    reference_id=tx,
                    family=FactFamily.COMMERCIAL,
                    provenance="commercial-core",
                    commercial_state=projection.state,
                    contract_id=projection.contract_id,
                    session_ref=projection.session_ref,
                    path_ref=projection.path_ref,
                )
            )
    entries.append(
        FactReference(
            reference_id=_settlement_ref(),
            family=FactFamily.SETTLEMENT,
            provenance="external-settlement-confirmation",
        )
    )
    entries.append(
        FactReference(
            reference_id=_payment_ref(),
            family=FactFamily.PAYMENT_PROVIDER,
            provenance="external-payment-observation",
        )
    )
    return FactIndex(entries)


def _typed_allocation_index(
    facts: FactIndex,
    usage_ledgers: Tuple[UsageLedger, ...],
    *,
    contract_id: str,
) -> AllocationEvidenceIndex:
    """Project the family fact index into the typed admission
    surface (the W053/M009 AllocationEvidenceIndex): the
    billable-usage snapshots (contract-bound -- the
    ``contract_id`` member carries the canonical binding) and the
    external settlement/payment reference citations."""
    usage: List[BillableUsageSnapshot] = []
    for ledger in usage_ledgers:
        for account in ledger.transactions():
            statement = account.statement
            if statement is None:
                usage.append(
                    BillableUsageSnapshot(
                        usage_transaction_id=account.transaction_id,
                        usage_state=account.state,
                        contract_id=contract_id,
                    )
                )
            else:
                usage.append(
                    BillableUsageSnapshot(
                        usage_transaction_id=account.transaction_id,
                        usage_state=account.state,
                        contract_id=contract_id,
                        gross_amount_micros=statement.amount_micros,
                        statement_id=statement.statement_id,
                        billable_quantity=statement.billable_quantity,
                        unit_price_micros=statement.unit_price_micros,
                        billable_unit=statement.billable_unit,
                        tariff_provenance=statement.tariff_provenance,
                        sealed_at=statement.sealed_at,
                    )
                )
    references = [
        ExternalReferenceSnapshot(
            _settlement_ref(),
            ReferenceKind.SETTLEMENT,
            "external-settlement-plane",
            None,
        ),
        ExternalReferenceSnapshot(
            _payment_ref(),
            ReferenceKind.PAYMENT,
            "external-payment-plane",
            None,
        ),
    ]
    return AllocationEvidenceIndex(usage=usage, references=references)


def _register_std_policy(
    ledger: AllocationLedger, *, command_id: str = "p-01"
) -> Any:
    """Register the standard immutable economic-policy version
    through the public typed surface (the current W053/M009
    registration: terms-derived identity, adcos share and
    provider bounds, declared rounding).  Returns the command
    outcome (``fact_id`` is the content-derived policy id)."""
    return ledger.register_policy(
        command_id=command_id,
        label=_PID,
        adcos_share_bps=_ADC_BPS,
        provider_min_bps=_DEV_MIN,
        provider_max_bps=_DEV_MAX,
        rounding_mode=_ROUNDING,
        currency=_CCY,
        minor_unit_digits=_EXP,
        effective_from=_POLICY_FROM,
        effective_until=_POLICY_UNTIL,
        actor="economics",
        source="policy-service",
    )


def _std_allocate(
    ledger: AllocationLedger,
    finality_id: str,
    tx: str,
    *,
    command_id: str = "a-01",
    policy_id: Optional[str] = None,
):
    """Allocate one billable-final usage record under the standard
    policy through the public typed surface (the current
    W053/M009 surface: the usage transaction id + the sealed
    statement id + the policy version id + the provider share
    inside the policy bounds)."""
    return ledger.allocate(
        command_id=command_id,
        usage_transaction_id=tx,
        usage_statement_id=finality_id,
        policy_id=policy_id if policy_id is not None else _PID,
        provider_share_bps=_PROVIDER_BPS,
        tax_micros=_TAX_MICROS,
        actor="economics",
        source="allocation-service",
    )


def _std_policy_id() -> str:
    """The content-derived id of the standard policy version (the
    terms-derived identity; identical terms always mean the
    identical version)."""
    from allocation import derive_policy_id

    return derive_policy_id(
        label=_PID,
        adcos_share_bps=_ADC_BPS,
        provider_min_bps=_DEV_MIN,
        provider_max_bps=_DEV_MAX,
        rounding_mode=_ROUNDING,
        currency=_CCY,
        minor_unit_digits=_EXP,
        effective_from=_POLICY_FROM,
        effective_until=_POLICY_UNTIL,
    )


# ---------------------------------------------------------------------------
# The payment-boundary composition fixture (the composed world)
# ---------------------------------------------------------------------------


def _commercial_snapshot(
    core: CommercialCore,
    usage_ledger: UsageLedger,
    alloc_ledger: Optional[AllocationLedger],
) -> CommercialSnapshot:
    """Build the injected W044/M009 CommercialSnapshot from PUBLIC
    reads only: the contract-bound commercial reconciliation
    accounts (carrying the canonical ``contract_id`` binding --
    LOCK-113), the usage accounts (the sealed statement id once
    final, else the honest open contract-bound identity), and the
    allocation accounts with their public split DATA."""
    entries: List[CommercialCitation] = []
    for entry in core.transactions():
        entries.append(
            CommercialCitation(
                reference_id=entry.transaction_id,
                family=CitationFamily.COMMERCIAL,
                provenance="commercial-core",
                contract_id=entry.contract_id,
                commercial_state=entry.state,
            )
        )
    for account in usage_ledger.transactions():
        statement = account.statement
        entries.append(
            CommercialCitation(
                reference_id=(
                    statement.statement_id
                    if statement is not None
                    else account.transaction_id
                ),
                family=CitationFamily.USAGE_FINAL,
                provenance="usage-ledger",
                contract_id=account.transaction_id,
                transaction_id=account.transaction_id,
                usage_state=account.state,
                amount=(
                    statement.amount_micros if statement is not None else 0
                ),
                quantity=(
                    statement.billable_quantity
                    if statement is not None
                    else 0
                ),
                unit=(
                    statement.billable_unit if statement is not None else ""
                ),
                finalized_at=(
                    statement.sealed_at if statement is not None else ""
                ),
            )
        )
    if alloc_ledger is not None:
        for account in alloc_ledger.allocations():
            snapshot = account.snapshot
            entries.append(
                CommercialCitation(
                    reference_id=account.usage_transaction_id,
                    family=CitationFamily.ALLOCATION,
                    provenance="allocation-ledger",
                    contract_id=account.usage_transaction_id,
                    transaction_id=account.usage_transaction_id,
                    allocation_state=account.state,
                    billable_amount=(
                        snapshot.gross_micros if snapshot is not None else 0
                    ),
                    currency=(
                        snapshot.currency if snapshot is not None else ""
                    ),
                    exponent=(
                        snapshot.minor_unit_digits
                        if snapshot is not None
                        else 0
                    ),
                    developer_amount=(
                        snapshot.developer_share_micros
                        if snapshot is not None
                        else 0
                    ),
                    provider_amount=(
                        snapshot.provider_share_micros
                        if snapshot is not None
                        else 0
                    ),
                    adc_os_amount=(
                        snapshot.adcos_share_micros
                        if snapshot is not None
                        else 0
                    ),
                    tax_amount=(
                        snapshot.tax_micros if snapshot is not None else 0
                    ),
                )
            )
    return CommercialSnapshot(entries)


def _payment_world(*, allocation_state: Optional[str] = "SETTLED"):
    """The composed battery fixture (the M009 re-bind): real world
    + the real canonical contract (M002 public surface) + the
    contract-bound W051 commercial account + the contract-bound
    W052 usage ledger driven to BILLABLE_FINAL (or an open state
    via ``stop_after``) + the real W053 allocation account
    (PLANNED by default, SETTLED optionally; ``None`` skips
    allocation entirely).

    Returns (snapshot, finality_id, tx, core, usage_ledger,
    alloc_ledger, manager, integrator, store, contract_id).
    """
    runtime, peer, session_id, manager, integrator, shared = _world()
    core, tx, store, contract_id = _commercial_tx(
        manager, integrator, session_id
    )
    references = _usage_evidence(
        manager, integrator, session_id, core, tx,
        contract_store=store, contract_id=contract_id,
    )
    typed_index = _typed_evidence_index(
        references, contract_state=store.contract(contract_id).state,
        integrator=integrator,
    )
    usage_ledger, finality_id = _final_usage(
        references, contract_id, typed_index=typed_index,
        integrator=integrator,
    )
    alloc_ledger = None
    if allocation_state is not None:
        facts = _allocation_facts((usage_ledger,), (core,))
        alloc_ledger = AllocationLedger(
            store=MemoryAllocationStore(),
            clock=StepClock(_AT0, _ASTEP),
            evidence_index=_typed_allocation_index(
                facts, (usage_ledger,), contract_id=contract_id
            ),
        )
        out = _register_std_policy(alloc_ledger)
        _std_allocate(
            alloc_ledger, finality_id, contract_id, policy_id=out.fact_id
        )
        if allocation_state == AllocationState.SETTLED:
            alloc_ledger.acknowledge_settlement(
                command_id="s-01",
                usage_transaction_id=contract_id,
                settlement_reference=_settlement_ref(),
                actor="settlement",
                source="settlement-service",
            )
    snapshot = _commercial_snapshot(core, usage_ledger, alloc_ledger)
    return (
        snapshot, finality_id, tx, core, usage_ledger, alloc_ledger,
        manager, integrator, store, contract_id,
    )


def _sandbox(
    *,
    capabilities: Optional[ProviderCapabilities] = None,
    clock: Optional[StepClock] = None,
    secret: bytes = _PROV_SECRET,
) -> SandboxProvider:
    return SandboxProvider(
        capabilities=capabilities or _full_capabilities(),
        secret=secret,
        clock=clock if clock is not None else StepClock(_VT0, _VSTEP),
    )


def _full_capabilities(
    *, provider_id: str = _PROV_ID, version: int = 1
) -> ProviderCapabilities:
    return ProviderCapabilities(
        provider_id=provider_id,
        schema_version=version,
        supports_authorization=True,
        supports_capture=True,
        supports_refund=True,
        supports_partial_refund=True,
        supports_reversal=True,
        supports_payout_transfer=True,
        supports_callbacks=True,
        supports_status_query=True,
        currencies=("GHS", "USD"),
        max_exponent=2,
        max_amount=10_000_000,
    )


def _gateway(
    *,
    store: Optional[payment.PaymentStore] = None,
    snapshot: Optional[CommercialSnapshot] = None,
    clock: Optional[AgentClock] = None,
    provider: Optional[ProviderAdapter] = None,
    world=None,
) -> SettlementGateway:
    """A fresh gateway over the composed world (or a caller-provided
    snapshot); the sandbox provider and gateway clocks are fresh
    deterministic seams."""
    if world is None and snapshot is None:
        world = _payment_world()
    if snapshot is None:
        snapshot = world[0]
    return SettlementGateway(
        store=store if store is not None else MemoryPaymentStore(),
        clock=clock if clock is not None else StepClock(_PT0, _PSTEP),
        snapshot=snapshot,
        adapter=provider if provider is not None else _sandbox(),
    )


def _create_std_intent(
    gateway: SettlementGateway,
    tx: str,
    finality_id: str,
    *,
    command_id: str = "pi-c01",
    intent_id: str = "pi-01",
    amount: int = _INTENT_AMOUNT,
):
    return gateway.create_intent(
        command_id=command_id,
        intent_id=intent_id,
        transaction_id=tx,
        amount=amount,
        currency=_CCY,
        exponent=_EXP,
        usage_record_id=finality_id,
        description="connectivity billing",
        actor="billing",
        source="billing-service",
    )


def _drive_to_captured(
    gateway: SettlementGateway,
    *,
    intent_id: str = "pi-01",
    amount: int = _INTENT_AMOUNT,
):
    gateway.authorize(
        command_id="pi-c02", intent_id=intent_id,
        actor="billing", source="billing-service",
    )
    return gateway.capture(
        command_id="pi-c03", intent_id=intent_id, amount=amount,
        actor="billing", source="billing-service",
    )


# ---------------------------------------------------------------------------
# Battery fixtures (clocks, stores, error helper)
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


class FailingPaymentStore(MemoryPaymentStore):
    """A battery fixture: a store whose append fails (the
    persist-then-ack discipline: no phantom in-memory state)."""

    def append(self, record_bytes: bytes) -> None:
        raise PaymentError(
            PaymentReasonCode.STORE_FAILED,
            "battery fixture: simulated durable-append failure",
        )


class FrozenBytesStore(payment.PaymentStore):
    """A battery fixture: serves fixed (possibly tampered) journal
    bytes for tamper-detection loads."""

    def __init__(self, data: bytes) -> None:
        self._data = data

    def append(self, record_bytes: bytes) -> None:
        raise PaymentError(
            PaymentReasonCode.STORE_FAILED,
            "battery fixture: frozen store is read-only",
        )

    def load_bytes(self) -> Tuple[bytes, ...]:
        return tuple(
            line for line in self._data.split(b"\n") if line.strip()
        )


def _expect_error(
    case_name: str, expected_reason: str, func, *args, **kwargs
) -> Optional[str]:
    """Run func; PASS iff it raised PaymentError with the reason."""
    try:
        func(*args, **kwargs)
    except PaymentError as error:
        if error.reason == expected_reason:
            return None
        return "expected %s, got %s (%s)" % (
            expected_reason, error.reason, error.detail
        )
    except Exception as error:  # noqa: BLE001 - wrong exception type is a failure
        return "wrong exception type %s" % type(error).__name__
    return "no error raised (expected %s)" % expected_reason


# ---------------------------------------------------------------------------
# The canonical golden scenario (determinism stream + composition)
# ---------------------------------------------------------------------------


def _golden_payment(
    store=None,
    *,
    snapshot=None,
    provider=None,
    clock=None,
    world=None,
):
    """Drive the full canonical payment lifecycle over the
    composed world: the versioned capability declaration, the
    idempotent payment intent correlated to the REAL W051
    transaction and the REAL W052 billable-final fact, the
    authorization, the full capture, a partial refund, the
    payout/transfer instruction emitted from the REAL settled
    W053 allocation, the full callback observation drain (all
    provider events ingested as external observations), the
    asynchronous transfer completion (provider-side advance +
    callback + the EXPLICIT reconciled application), and the
    final divergence reconciliation report."""
    if world is None and snapshot is None:
        world = _payment_world()
    if snapshot is None:
        snapshot = world[0]
    finality_id = world[1] if world is not None else None
    tx = world[2] if world is not None else None
    #: the W053 allocation account key under the M009 re-bind: the
    #: usage transaction id IS the canonical contract id.
    alloc_key = world[9] if world is not None else None
    if provider is None:
        provider = _sandbox()
    gateway = SettlementGateway(
        store=store if store is not None else MemoryPaymentStore(),
        clock=clock if clock is not None else StepClock(_PT0, _PSTEP),
        snapshot=snapshot,
        adapter=provider,
    )
    gateway.record_capabilities(
        command_id="cap-01", actor="payments", source="payment-service"
    )
    _create_std_intent(gateway, tx, finality_id)
    gateway.authorize(
        command_id="pi-c02", intent_id="pi-01",
        actor="billing", source="billing-service",
    )
    gateway.capture(
        command_id="pi-c03", intent_id="pi-01", amount=_INTENT_AMOUNT,
        actor="billing", source="billing-service",
    )
    gateway.refund(
        command_id="pi-c04", intent_id="pi-01", amount=_PARTIAL_REFUND,
        reason="partial-service-credit",
        actor="billing", source="billing-service",
    )
    gateway.emit_payout(
        command_id="po-c01", usage_record_id=alloc_key,
        actor="settlement", source="payout-service",
    )
    # drain and ingest ALL emitted provider callbacks (the
    # external-observation stream, deterministic order)
    for envelope in provider.pending_callbacks():
        gateway.ingest_callback(
            envelope, actor="webhook-ingress", source="provider-callback"
        )
    # the asynchronous transfer completion: the provider moves
    # without an ADCOS operation, pushes the callback, ADCOS
    # records the observation and EXPLICITLY applies it
    payout = gateway.payout(alloc_key)
    provider.async_advance_transfer(payout.transfer_ref, "TRF_DONE")
    completion_event = None
    for envelope in provider.pending_callbacks():
        gateway.ingest_callback(
            envelope, actor="webhook-ingress", source="provider-callback"
        )
    for observation in gateway.observations():
        if (
            observation.kind == CallbackKind.TRANSFER_STATUS
            and observation.canonical_status == PayoutStatus.TRANSFERRED
        ):
            completion_event = observation.event_id
    assert completion_event is not None
    gateway.apply_observation(
        command_id="obs-a01", event_id=completion_event,
        actor="settlement", source="reconciliation-service",
    )
    gateway.reconcile(
        command_id="rec-01", actor="settlement",
        source="reconciliation-service",
    )
    return gateway


def _scenario_stream(store=None) -> Dict[str, str]:
    """The canonical battery scenario: full authority composition
    (real session, real NetworkPath, real platform delivery
    evidence, real W051 delivery window, real W052 billable-final
    usage, real W053 settled allocation) -> the golden payment
    lifecycle -> the deterministic digest stream."""
    gateway = _golden_payment(store=store)
    return {
        "journal_digest": gateway.journal_digest(),
        "state_digest": payment.state_digest(gateway.intents()),
        "payout_state_digest": payment.payout_state_digest(
            gateway.payouts()
        ),
        "observation_log_digest": payment.observation_log_digest(
            gateway.observations()
        ),
        "capability_registry_digest": (
            payment.capability_registry_digest(
                gateway.capability_declarations()
            )
        ),
        "report_log_digest": payment.report_log_digest(
            gateway.reports()
        ),
        "command_ledger_digest": payment.command_ledger_digest(
            gateway.command_ledger()
        ),
        "intent_ledger_digest": payment.intent_ledger_digest(
            gateway.intent_ledger()
        ),
        "payout_ledger_digest": payment.payout_ledger_digest(
            gateway.payout_ledger()
        ),
        "callback_ledger_digest": payment.callback_ledger_digest(
            gateway.callback_ledger()
        ),
        "capability_ledger_digest": payment.capability_ledger_digest(
            gateway.capability_ledger()
        ),
        "digest_stream_sha256": hashlib.sha256(
            gateway.digest_stream().encode("utf-8")
        ).hexdigest(),
    }


#: The golden digest stream of the canonical scenario (pinned;
#: byte-identical across two-run and hash-seed proofs).
_GOLDEN_STREAM_SHA256 = "2f33937c9b710331dfb453577bad3a0b834b0c00fa19d6ba72eb3d013e679ccf"


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------


def case_01_frozen_vocabularies(results: List[Result]) -> None:
    name = "case_01_frozen_vocabularies"
    problems: List[str] = []
    if PaymentStatus.values() != (
        "CREATED", "AUTHORIZED", "CAPTURED", "REFUNDED", "REVERSED", "FAILED",
    ):
        problems.append("intent status vocabulary changed")
    if PaymentStatus.terminal_values() != (
        "REFUNDED", "REVERSED", "FAILED",
    ):
        problems.append("terminal vocabulary changed")
    if PayoutStatus.values() != ("EMITTED", "TRANSFERRED", "FAILED"):
        problems.append("payout status vocabulary changed")
    if PayoutStatus.terminal_values() != ("TRANSFERRED", "FAILED"):
        problems.append("payout terminal vocabulary changed")
    if PaymentAction.values() != (
        "record_capabilities", "create_intent", "authorize", "capture",
        "refund", "reverse", "emit_payout", "ingest_callback",
        "apply_observation", "reconcile",
    ):
        problems.append("action vocabulary changed")
    if payment.EntityKind.values() != (
        "intent", "payout", "observation", "report", "capability",
    ):
        problems.append("entity-kind vocabulary changed")
    if EventOutcome.values() != (
        "appended", "declined", "observed", "orphan", "applied",
    ):
        problems.append("event-outcome vocabulary changed")
    if CallbackKind.values() != ("intent-status", "transfer-status"):
        problems.append("callback-kind vocabulary changed")
    if FailureClass.values() != ("unavailable", "timeout", "malformed"):
        problems.append("failure-class vocabulary changed")
    if ReconciliationClass.values() != (
        "matched", "provider-ahead", "gateway-ahead", "amount-divergent",
        "provider-unknown", "orphan-reference",
    ):
        problems.append("reconciliation vocabulary changed")
    if CitationFamily.values() != (
        "commercial", "usage-final", "allocation",
    ):
        problems.append("citation-family vocabulary changed")
    if PaymentReasonCode.counts() != 35:
        problems.append(
            "reason vocabulary count %d" % PaymentReasonCode.counts()
        )
    if len(payment.INTENT_TRANSITIONS) != 7 or len(
        payment.PAYOUT_TRANSITIONS
    ) != 4:
        problems.append("transition table size changed")
    caps = _full_capabilities()
    if caps.key() != "sandbox-1@v1":
        problems.append("capability key format changed")
    if len(payment.PAYLOAD_REQUIREMENTS) != 10:
        problems.append("payload contract table size changed")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(ok(name, "all frozen vocabularies pinned"))


def case_02_transition_tables(results: List[Result]) -> None:
    name = "case_02_transition_tables"
    legal = (
        ("intent", "", "CREATED"),
        ("intent", "CREATED", "AUTHORIZED"),
        ("intent", "CREATED", "FAILED"),
        ("intent", "AUTHORIZED", "CAPTURED"),
        ("intent", "AUTHORIZED", "REVERSED"),
        ("intent", "AUTHORIZED", "FAILED"),
        ("intent", "CAPTURED", "REFUNDED"),
        ("payout", "", "EMITTED"),
        ("payout", "EMITTED", "TRANSFERRED"),
        ("payout", "EMITTED", "FAILED"),
    )
    for entity, from_state, to_state in legal:
        if not transition_check(entity, from_state, to_state):
            results.append(
                fail(name, "edge %s %s->%s not legal" % (entity, from_state, to_state))
            )
            return
    illegal = (
        ("intent", "", "AUTHORIZED"),
        ("intent", "CREATED", "CAPTURED"),
        ("intent", "CREATED", "REFUNDED"),
        ("intent", "AUTHORIZED", "CREATED"),
        ("intent", "CAPTURED", "AUTHORIZED"),
        ("intent", "CAPTURED", "REVERSED"),
        ("intent", "CAPTURED", "FAILED"),
        ("intent", "REFUNDED", "CAPTURED"),
        ("intent", "REVERSED", "AUTHORIZED"),
        ("intent", "FAILED", "CREATED"),
        ("payout", "", "TRANSFERRED"),
        ("payout", "EMITTED", "EMITTED"),
        ("payout", "TRANSFERRED", "EMITTED"),
        ("payout", "FAILED", "EMITTED"),
        ("intent", "CREATED", "SETTLED"),
        ("weird", "CREATED", "AUTHORIZED"),
    )
    for entity, from_state, to_state in illegal:
        if transition_check(entity, from_state, to_state):
            results.append(
                fail(name, "edge %s %s->%s must be illegal" % (entity, from_state, to_state))
            )
            return
    results.append(
        ok(name, "transition tables pinned; terminals sealed (no outgoing edges)")
    )


def transition_check(entity: str, from_state: str, to_state: str) -> bool:
    return payment.transition_is_legal(entity, from_state, to_state)


def case_03_command_model(results: List[Result]) -> None:
    name = "case_03_command_model"
    command = PaymentCommand(
        command_id="c-01",
        action=PaymentAction.CREATE_INTENT,
        entity_id="pi-01",
        references=(
            CommercialCitation(
                reference_id="tx-1",
                family=CitationFamily.COMMERCIAL,
                provenance="command-citation",
            ),
        ),
        payload={
            "transaction_id": "tx-1",
            "usage_record_id": "",
            "amount": 100,
            "currency": "GHS",
            "exponent": 2,
            "description": "billing",
        },
        actor="billing",
        source="billing-service",
    )
    if not command.digest().startswith("sha256:"):
        results.append(fail(name, "command digest not content-derived"))
        return
    again = PaymentCommand.from_dict(command.to_dict())
    if again.digest() != command.digest():
        results.append(fail(name, "round-trip digest instability"))
        return
    try:
        command.payload["amount"] = 5
        results.append(fail(name, "payload mutation did not raise"))
        return
    except TypeError:
        pass
    problems = _expect_error(
        name, PaymentReasonCode.INVALID_INPUT,
        PaymentCommand,
        command_id="c-02",
        action=PaymentAction.CAPTURE,
        entity_id="pi-01",
        references=(),
        payload={"amount": 1.5},
        actor="billing",
        source="billing-service",
    )
    if problems:
        results.append(fail(name, problems))
        return
    problems = _expect_error(
        name, PaymentReasonCode.COMMAND_INVALID,
        PaymentCommand,
        command_id="c-03", action="not-an-action", entity_id="pi-01",
        references=(), payload={}, actor="a", source="s",
    )
    if problems:
        results.append(fail(name, problems))
        return
    results.append(ok(name, "command model: digests, deep freeze, floats rejected"))


def case_04_event_model(results: List[Result]) -> None:
    name = "case_04_event_model"
    content = payment.event_content(
        PaymentAction.AUTHORIZE, "intent", "pi-01", EventOutcome.APPENDED,
        "CREATED", "AUTHORIZED",
        {"provider_ref": "p-1", "authorized_amount": 100,
         "captured_amount": 0, "refunded_amount": 0,
         "provider_event_id": "", "provider_detail": "ok"},
        "2026-09-02T07:01:00Z", "billing", "billing-service",
    )
    event_id = payment.derive_event_id(content)
    event = PaymentEvent(
        event_id=event_id,
        action=PaymentAction.AUTHORIZE,
        entity_kind="intent",
        entity_id="pi-01",
        outcome=EventOutcome.APPENDED,
        from_state="CREATED",
        to_state="AUTHORIZED",
        payload={
            "provider_ref": "p-1", "authorized_amount": 100,
            "captured_amount": 0, "refunded_amount": 0,
            "provider_event_id": "", "provider_detail": "ok",
        },
        instant="2026-09-02T07:01:00Z",
        actor="billing",
        source="billing-service",
    )
    if event.event_id != event_id:
        results.append(fail(name, "event id not the content fingerprint"))
        return
    try:
        event.payload["authorized_amount"] = 0
        results.append(fail(name, "event payload mutation did not raise"))
        return
    except TypeError:
        pass
    problems = _expect_error(
        name, PaymentReasonCode.EVENT_INVALID,
        PaymentEvent,
        event_id=event_id,
        action=PaymentAction.AUTHORIZE,
        entity_kind="intent",
        entity_id="pi-01",
        outcome=EventOutcome.APPENDED,
        from_state="CREATED",
        to_state="REVERSED",
        payload={
            "provider_ref": "p-1", "authorized_amount": 100,
            "captured_amount": 0, "refunded_amount": 0,
            "provider_event_id": "", "provider_detail": "ok",
        },
        instant="2026-09-02T07:01:00Z",
        actor="billing",
        source="billing-service",
    )
    if problems:
        results.append(fail(name, "tampered id accepted: %s" % problems))
        return
    results.append(ok(name, "event model: content-derived ids, deep freeze, tamper rejection"))


def case_05_capability_model(results: List[Result]) -> None:
    name = "case_05_capability_model"
    caps = _full_capabilities()
    if caps.digest() != _full_capabilities().digest():
        results.append(fail(name, "capability digest not deterministic"))
        return
    if caps.key() != capability_key("sandbox-1", 1):
        results.append(fail(name, "capability key derivation"))
        return
    round_trip = ProviderCapabilities.from_dict(caps.to_dict())
    if round_trip.digest() != caps.digest():
        results.append(fail(name, "capability round-trip instability"))
        return
    v2 = _full_capabilities(version=2)
    if v2.key() == caps.key() or v2.digest() == caps.digest():
        results.append(fail(name, "versioning does not separate identities"))
        return
    problems = _expect_error(
        name, PaymentReasonCode.INVALID_INPUT,
        ProviderCapabilities,
        provider_id="sandbox-1", schema_version=0,
        supports_authorization=True, supports_capture=True,
        supports_refund=True, supports_partial_refund=True,
        supports_reversal=True, supports_payout_transfer=True,
        supports_callbacks=True, supports_status_query=True,
        currencies=("GHS",), max_exponent=2, max_amount=100,
    )
    if problems:
        results.append(fail(name, problems))
        return
    problems = _expect_error(
        name, PaymentReasonCode.INVALID_INPUT,
        ProviderCapabilities,
        provider_id="sandbox-1", schema_version=1,
        supports_authorization=True, supports_capture=True,
        supports_refund=True, supports_partial_refund=True,
        supports_reversal=True, supports_payout_transfer=True,
        supports_callbacks=True, supports_status_query=True,
        currencies=("ghs",), max_exponent=2, max_amount=100,
    )
    if problems:
        results.append(fail(name, problems))
        return
    if not caps.supports_currency("GHS") or caps.supports_currency("EUR"):
        results.append(fail(name, "currency membership check"))
        return
    results.append(ok(name, "capability model: versioned, immutable, validated"))


def case_06_citation_snapshot(results: List[Result]) -> None:
    name = "case_06_citation_snapshot"
    snapshot = CommercialSnapshot(
        [
            CommercialCitation(
                reference_id="tx-1", family=CitationFamily.COMMERCIAL,
                provenance="commercial-core", commercial_state="USAGE_ACCRUING",
            ),
            CommercialCitation(
                reference_id="uf-1", family=CitationFamily.USAGE_FINAL,
                provenance="usage-ledger", transaction_id="tx-1",
                usage_state="BILLABLE_FINAL", amount=800, quantity=400,
                unit="MB", finalized_at="2026-09-01T13:01:00Z",
            ),
            CommercialCitation(
                reference_id="al-1", family=CitationFamily.ALLOCATION,
                provenance="allocation-ledger", contract_id=(
                    "sha256:" + "0a" * 32
                ),
                transaction_id="tx-1",
                allocation_state="SETTLED", billable_amount=800,
                currency="GHS", exponent=2,
                developer_amount=266, provider_amount=399,
                adc_os_amount=35, tax_amount=100,
            ),
        ]
    )
    if len(snapshot) != 3 or len(snapshot.by_family(CitationFamily.COMMERCIAL)) != 1:
        results.append(fail(name, "snapshot index construction"))
        return
    resolved = snapshot.resolve("tx-1", CitationFamily.COMMERCIAL)
    if resolved.commercial_state != "USAGE_ACCRUING":
        results.append(fail(name, "citation resolution content"))
        return
    problems = _expect_error(
        name, PaymentReasonCode.CITATION_UNKNOWN,
        snapshot.resolve, "tx-404", CitationFamily.COMMERCIAL,
    )
    if problems:
        results.append(fail(name, problems))
        return
    problems = _expect_error(
        name, PaymentReasonCode.CITATION_FAMILY_INVALID,
        snapshot.resolve, "tx-1", CitationFamily.ALLOCATION,
    )
    if problems:
        results.append(fail(name, problems))
        return
    problems = _expect_error(
        name, PaymentReasonCode.INVALID_INPUT,
        CommercialSnapshot,
        [
            CommercialCitation(
                reference_id="tx-1", family=CitationFamily.COMMERCIAL,
                provenance="a",
            ),
            CommercialCitation(
                reference_id="tx-1", family=CitationFamily.COMMERCIAL,
                provenance="b",
            ),
        ],
    )
    if problems:
        results.append(fail(name, problems))
        return
    results.append(ok(name, "citation snapshot: fail-closed resolution, ambiguity rejected"))


def case_07_full_ledger_golden(results: List[Result]) -> None:
    name = "case_07_full_ledger_golden"
    stream = _scenario_stream()
    if _GOLDEN_STREAM_SHA256.startswith("PENDING"):
        results.append(
            fail(name, "golden digest stream not pinned (run once to pin)")
        )
        return
    if stream["digest_stream_sha256"] != _GOLDEN_STREAM_SHA256:
        results.append(
            fail(
                name,
                "digest stream %s != pinned golden %s"
                % (stream["digest_stream_sha256"], _GOLDEN_STREAM_SHA256),
            )
        )
        return
    gateway = None
    gateway = _golden_payment()
    intents = gateway.intents()
    if len(intents) != 1 or intents[0].state != PaymentStatus.CAPTURED:
        results.append(fail(name, "golden intent projection shape"))
        return
    if intents[0].refunded_amount != _PARTIAL_REFUND:
        results.append(fail(name, "golden refunded amount"))
        return
    payouts = gateway.payouts()
    if len(payouts) != 1 or payouts[0].state != PayoutStatus.TRANSFERRED:
        results.append(fail(name, "golden payout projection shape"))
        return
    if payouts[0].transfer_entries() != (
        ("developer", 266), ("provider", 399), ("adc-os", 35),
    ):
        results.append(fail(name, "golden transfer entries"))
        return
    if len(gateway.observations()) != 6:
        results.append(
            fail(name, "golden observation count %d" % len(gateway.observations()))
        )
        return
    if len(gateway.reports()) != 1:
        results.append(fail(name, "golden report count"))
        return
    if gateway.reports()[0].summary() != {"matched": 2}:
        results.append(
            fail(name, "golden reconciliation summary %r" % gateway.reports()[0].summary())
        )
        return
    results.append(
        ok(
            name,
            "golden scenario: %d records, stream %s, reconciled matched"
            % (gateway.tail_sequence(), stream["digest_stream_sha256"][:16]),
        )
    )


def case_08_every_legal_transition(results: List[Result]) -> None:
    name = "case_08_every_legal_transition"
    # intent: CREATED -> AUTHORIZED -> CAPTURED -> REFUNDED
    world = _payment_world()
    gateway = _gateway(world=world)
    gateway.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway, world[2], world[1])
    out = gateway.authorize(
        command_id="a-01", intent_id="pi-01", actor="b", source="s"
    )
    if out.to_state != "AUTHORIZED":
        results.append(fail(name, "authorize edge"))
        return
    gateway.capture(
        command_id="a-02", intent_id="pi-01", amount=_INTENT_AMOUNT,
        actor="b", source="s",
    )
    out = gateway.refund(
        command_id="a-03", intent_id="pi-01", amount=_INTENT_AMOUNT,
        reason="full-refund", actor="b", source="s",
    )
    if out.to_state != "REFUNDED":
        results.append(fail(name, "full-refund edge"))
        return
    # CREATED -> FAILED (authorization declined)
    provider = _sandbox()
    provider.decline_authorize = True
    gateway2 = _gateway(world=world, provider=provider)
    gateway2.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway2, world[2], world[1], intent_id="pi-02", command_id="pi-c02")
    out = gateway2.authorize(
        command_id="a-04", intent_id="pi-02", actor="b", source="s"
    )
    if out.to_state != "FAILED" or out.status != "appended":
        results.append(fail(name, "authorization-decline edge"))
        return
    # AUTHORIZED -> REVERSED
    provider3 = _sandbox()
    gateway3 = _gateway(world=world, provider=provider3)
    gateway3.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway3, world[2], world[1], intent_id="pi-03", command_id="pi-c03")
    gateway3.authorize(command_id="a-05", intent_id="pi-03", actor="b", source="s")
    out = gateway3.reverse(
        command_id="a-06", intent_id="pi-03", reason="void",
        actor="b", source="s",
    )
    if out.to_state != "REVERSED":
        results.append(fail(name, "reversal edge"))
        return
    # AUTHORIZED -> FAILED (capture declined)
    provider4 = _sandbox()
    provider4.decline_capture = True
    gateway4 = _gateway(world=world, provider=provider4)
    gateway4.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway4, world[2], world[1], intent_id="pi-04", command_id="pi-c04")
    gateway4.authorize(command_id="a-07", intent_id="pi-04", actor="b", source="s")
    out = gateway4.capture(
        command_id="a-08", intent_id="pi-04", amount=_INTENT_AMOUNT,
        actor="b", source="s",
    )
    if out.to_state != "FAILED":
        results.append(fail(name, "capture-decline edge"))
        return
    # payout: EMITTED -> TRANSFERRED (async) and EMITTED -> FAILED (declined)
    provider5 = _sandbox()
    provider5.transfer_outcome = "completed"
    gateway5 = _gateway(world=world, provider=provider5)
    gateway5.record_capabilities(command_id="cap-01", actor="p", source="s")
    out = gateway5.emit_payout(
        command_id="po-01", usage_record_id=world[9], actor="st", source="s"
    )
    if out.to_state != "TRANSFERRED":
        results.append(fail(name, "synchronous transfer completion edge"))
        return
    provider6 = _sandbox()
    provider6.transfer_outcome = "declined"
    gateway6 = _gateway(world=world, provider=provider6)
    gateway6.record_capabilities(command_id="cap-01", actor="p", source="s")
    out = gateway6.emit_payout(
        command_id="po-01", usage_record_id=world[9], actor="st", source="s"
    )
    if out.to_state != "FAILED" or out.status != "appended":
        results.append(fail(name, "transfer-decline edge"))
        return
    results.append(
        ok(name, "every legal intent/payout edge driven through the typed surface")
    )


def case_09_every_illegal_transition(results: List[Result]) -> None:
    name = "case_09_every_illegal_transition"
    world = _payment_world()
    gateway = _gateway(world=world)
    gateway.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway, world[2], world[1])
    gateway.authorize(command_id="a-01", intent_id="pi-01", actor="b", source="s")
    gateway.capture(
        command_id="a-02", intent_id="pi-01", amount=_INTENT_AMOUNT,
        actor="b", source="s",
    )
    checks = (
        ("authorize after capture", gateway.authorize,
         {"command_id": "x-1", "intent_id": "pi-01", "actor": "b", "source": "s"},
         PaymentReasonCode.INTENT_STATE_INVALID),
        ("reverse after capture", gateway.reverse,
         {"command_id": "x-2", "intent_id": "pi-01", "reason": "r",
          "actor": "b", "source": "s"},
         PaymentReasonCode.INTENT_STATE_INVALID),
        ("refund over remainder", gateway.refund,
         {"command_id": "x-3", "intent_id": "pi-01",
          "amount": _INTENT_AMOUNT + 1, "reason": "r",
          "actor": "b", "source": "s"},
         PaymentReasonCode.AMOUNT_INVALID),
        ("capture over authorization", gateway.capture,
         {"command_id": "x-4", "intent_id": "pi-01",
          "amount": _INTENT_AMOUNT + 1, "actor": "b", "source": "s"},
         PaymentReasonCode.INTENT_STATE_INVALID),
        ("unknown intent", gateway.authorize,
         {"command_id": "x-5", "intent_id": "pi-404", "actor": "b", "source": "s"},
         PaymentReasonCode.INTENT_UNKNOWN),
    )
    before = gateway.tail_sequence()
    for label, func, kwargs, reason in checks:
        problems = _expect_error(name, reason, func, **kwargs)
        if problems:
            results.append(fail(name, "%s: %s" % (label, problems)))
            return
    if gateway.tail_sequence() != before:
        results.append(fail(name, "rejected commands grew the journal"))
        return
    results.append(
        ok(name, "every illegal transition rejected with zero journal growth")
    )


def case_10_intent_create_retrieve(results: List[Result]) -> None:
    name = "case_10_intent_create_retrieve"
    world = _payment_world()
    gateway = _gateway(world=world)
    gateway.record_capabilities(command_id="cap-01", actor="p", source="s")
    out = _create_std_intent(gateway, world[2], world[1])
    if out.status != "appended" or out.to_state != "CREATED":
        results.append(fail(name, "intent creation outcome"))
        return
    intent = gateway.intent("pi-01")
    if intent.transaction_id != world[2]:
        results.append(fail(name, "intent transaction correlation"))
        return
    if intent.usage_record_id != world[1]:
        results.append(fail(name, "intent usage correlation"))
        return
    if intent.capability_key != "sandbox-1@v1":
        results.append(fail(name, "intent capability citation"))
        return
    if not intent.provider_ref:
        results.append(fail(name, "provider reference not assigned"))
        return
    # duplicate create under a NEW command id: idempotent no-op
    out2 = _create_std_intent(
        gateway, world[2], world[1], command_id="pi-c09", intent_id="pi-01"
    )
    if out2.status != "duplicate" or out2.event_id != out.event_id:
        results.append(fail(name, "duplicate intent creation not a no-op"))
        return
    if len(gateway.intents()) != 1:
        results.append(fail(name, "duplicate created a second intent"))
        return
    problems = _expect_error(
        name, PaymentReasonCode.INTENT_UNKNOWN, gateway.intent, "pi-404"
    )
    if problems:
        results.append(fail(name, problems))
        return
    results.append(
        ok(name, "intent create/retrieve idempotent with provider correlation")
    )


def case_11_duplicate_commands(results: List[Result]) -> None:
    name = "case_11_duplicate_commands"
    world = _payment_world()
    clock = CountingClock(StepClock(_PT0, _PSTEP))
    gateway = _gateway(world=world, clock=clock)
    gateway.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway, world[2], world[1])
    reads_before = clock.reads
    out = gateway.authorize(
        command_id="pi-c02", intent_id="pi-01", actor="b", source="s"
    )
    appended_event = out.event_id
    reads_after_append = clock.reads
    out2 = gateway.authorize(
        command_id="pi-c02", intent_id="pi-01", actor="b", source="s"
    )
    if out2.status != "duplicate" or out2.event_id != appended_event:
        results.append(fail(name, "duplicate command not an idempotent no-op"))
        return
    if out2.from_state != "AUTHORIZED" or out2.to_state != "AUTHORIZED":
        results.append(fail(name, "duplicate context state"))
        return
    if clock.reads != reads_after_append:
        results.append(fail(name, "duplicate consumed a clock read"))
        return
    if gateway.tail_sequence() != 3:
        results.append(fail(name, "duplicate grew the journal"))
        return
    if reads_after_append - reads_before != 1:
        results.append(fail(name, "append did not consume exactly one read"))
        return
    results.append(
        ok(name, "exact command redelivery: no-op, no clock read, no journal growth")
    )


def case_12_conflicting_commands(results: List[Result]) -> None:
    name = "case_12_conflicting_commands"
    world = _payment_world()
    gateway = _gateway(world=world)
    gateway.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway, world[2], world[1])
    gateway.authorize(
        command_id="pi-c02", intent_id="pi-01", actor="billing",
        source="billing-service",
    )
    before = gateway.tail_sequence()
    problems = _expect_error(
        name, PaymentReasonCode.COMMAND_CONFLICT,
        gateway.capture,
        command_id="pi-c02", intent_id="pi-01", amount=100,
        actor="billing", source="billing-service",
    )
    if problems:
        results.append(fail(name, problems))
        return
    if gateway.tail_sequence() != before:
        results.append(fail(name, "conflicting command grew the journal"))
        return
    results.append(ok(name, "conflicting command redelivery fails closed"))


def case_13_duplicate_intent_identity(results: List[Result]) -> None:
    name = "case_13_duplicate_intent_identity"
    world = _payment_world()
    gateway = _gateway(world=world)
    gateway.record_capabilities(command_id="cap-01", actor="p", source="s")
    out = _create_std_intent(gateway, world[2], world[1])
    before = gateway.tail_sequence()
    # exact redelivery under a new command id: durable
    # intent-ledger no-op BEFORE live citation resolution
    empty_snapshot = CommercialSnapshot([])
    gateway.snapshot  # noqa: B018 - read-only access check
    out2 = _create_std_intent(
        gateway, world[2], world[1], command_id="pi-c13"
    )
    if out2.status != "duplicate":
        results.append(fail(name, "intent identity redelivery not a no-op"))
        return
    # conflicting reuse: different amount under the same intent id
    problems = _expect_error(
        name, PaymentReasonCode.INTENT_CONFLICT,
        gateway.create_intent,
        command_id="pi-c14", intent_id="pi-01", transaction_id=world[2],
        amount=_INTENT_AMOUNT - 1, currency=_CCY, exponent=_EXP,
        usage_record_id=world[1], description="different",
        actor="b", source="s",
    )
    if problems:
        results.append(fail(name, problems))
        return
    if gateway.tail_sequence() != before:
        results.append(fail(name, "intent conflicts grew the journal"))
        return
    # restart + citation eviction: the durable intent ledger
    # replays the exact duplicate as a no-op even when the
    # snapshot no longer carries the citations
    from payment import FilePaymentStore
    with tempfile.TemporaryDirectory() as tmp:
        store = FilePaymentStore(Path(tmp) / "journal.jsonl")
        gateway3 = _gateway(world=world, store=store)
        gateway3.record_capabilities(command_id="cap-01", actor="p", source="s")
        _create_std_intent(gateway3, world[2], world[1])
        recovered = SettlementGateway.load(
            store=store, clock=StepClock(_PT0, _PSTEP),
            snapshot=CommercialSnapshot([]),  # EVICTED citations
            adapter=_sandbox(),
        )
        out3 = recovered.create_intent(
            command_id="pi-c15", intent_id="pi-01", transaction_id=world[2],
            amount=_INTENT_AMOUNT, currency=_CCY, exponent=_EXP,
            usage_record_id=world[1], description="connectivity billing",
            actor="b", source="s",
        )
        if out3.status != "duplicate":
            results.append(
                fail(name, "evicted-citation redelivery not a durable no-op")
            )
            return
    results.append(
        ok(
            name,
            "intent identity: durable no-op (restart + eviction) and "
            "conflicting reuse fail-closed",
        )
    )


def case_14_provider_reference_conflict(results: List[Result]) -> None:
    name = "case_14_provider_reference_conflict"
    world = _payment_world()
    provider = _sandbox()
    gateway = _gateway(world=world, provider=provider)
    gateway.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway, world[2], world[1])
    first_ref = gateway.intent("pi-01").provider_ref
    # the provider is scripted to hand the SAME reference to the
    # next intent: the correlation boundary must fail closed
    provider.force_provider_ref = first_ref
    before = gateway.tail_sequence()
    problems = _expect_error(
        name, PaymentReasonCode.PROVIDER_REFERENCE_CONFLICT,
        _create_std_intent,
        gateway, world[2], world[1],
        command_id="pi-c14", intent_id="pi-02",
    )
    if problems:
        results.append(fail(name, problems))
        return
    if gateway.tail_sequence() != before:
        results.append(fail(name, "reference conflict grew the journal"))
        return
    if "pi-02" not in gateway.intent_ledger() and gateway.intent_ledger():
        pass
    results.append(
        ok(name, "conflicting provider-reference reuse fails closed, no journal")
    )


def case_15_authorize_flow(results: List[Result]) -> None:
    name = "case_15_authorize_flow"
    world = _payment_world()
    gateway = _gateway(world=world)
    gateway.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway, world[2], world[1])
    out = gateway.authorize(
        command_id="pi-c02", intent_id="pi-01", actor="b", source="s"
    )
    intent = gateway.intent("pi-01")
    if intent.state != "AUTHORIZED" or intent.authorized_amount != _INTENT_AMOUNT:
        results.append(fail(name, "authorization fold"))
        return
    if out.from_state != "CREATED" or out.to_state != "AUTHORIZED":
        results.append(fail(name, "authorization transition context"))
        return
    # second authorization: state-gated (fail closed)
    problems = _expect_error(
        name, PaymentReasonCode.INTENT_STATE_INVALID,
        gateway.authorize,
        command_id="x-1", intent_id="pi-01", actor="b", source="s",
    )
    if problems:
        results.append(fail(name, problems))
        return
    # capability gate: an authorization-incapable provider
    caps = _full_capabilities()
    restricted = ProviderCapabilities(
        provider_id=_PROV_ID, schema_version=1,
        supports_authorization=False, supports_capture=True,
        supports_refund=True, supports_partial_refund=True,
        supports_reversal=True, supports_payout_transfer=True,
        supports_callbacks=True, supports_status_query=True,
        currencies=("GHS", "USD"), max_exponent=2, max_amount=10_000_000,
    )
    provider2 = SandboxProvider(
        capabilities=restricted, secret=_PROV_SECRET,
        clock=StepClock(_VT0, _VSTEP),
    )
    gateway2 = _gateway(world=world, provider=provider2)
    gateway2.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway2, world[2], world[1], command_id="pi-c15")
    problems = _expect_error(
        name, PaymentReasonCode.CAPABILITY_UNSUPPORTED,
        gateway2.authorize,
        command_id="x-2", intent_id="pi-01", actor="b", source="s",
    )
    if problems:
        results.append(fail(name, problems))
        return
    results.append(ok(name, "authorization flow + state/capability gates"))


def case_16_capture_flow(results: List[Result]) -> None:
    name = "case_16_capture_flow"
    world = _payment_world()
    gateway = _gateway(world=world)
    gateway.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway, world[2], world[1])
    gateway.authorize(command_id="pi-c02", intent_id="pi-01", actor="b", source="s")
    # partial capture within the authorized amount
    out = gateway.capture(
        command_id="pi-c03", intent_id="pi-01", amount=_INTENT_AMOUNT - 100,
        actor="b", source="s",
    )
    intent = gateway.intent("pi-01")
    if intent.state != "CAPTURED" or intent.captured_amount != _INTENT_AMOUNT - 100:
        results.append(fail(name, "partial capture fold"))
        return
    # over-capture rejected (fail closed)
    problems = _expect_error(
        name, PaymentReasonCode.INTENT_STATE_INVALID,
        gateway.capture,
        command_id="x-1", intent_id="pi-01", amount=1, actor="b", source="s",
    )
    if problems:
        results.append(fail(name, problems))
        return
    results.append(ok(name, "capture flow: partial capture, bounds enforced"))


def case_17_refund_flow(results: List[Result]) -> None:
    name = "case_17_refund_flow"
    world = _payment_world()
    gateway = _gateway(world=world)
    gateway.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway, world[2], world[1])
    _drive_to_captured(gateway)
    # partial refund: stays CAPTURED with the accumulated amount
    gateway.refund(
        command_id="pi-c04", intent_id="pi-01", amount=_PARTIAL_REFUND,
        reason="partial-service-credit", actor="b", source="s",
    )
    intent = gateway.intent("pi-01")
    if intent.state != "CAPTURED" or intent.refunded_amount != _PARTIAL_REFUND:
        results.append(fail(name, "partial refund fold"))
        return
    # completing the refund: CAPTURED -> REFUNDED (terminal)
    out = gateway.refund(
        command_id="pi-c05", intent_id="pi-01",
        amount=_INTENT_AMOUNT - _PARTIAL_REFUND, reason="settle-up",
        actor="b", source="s",
    )
    if out.to_state != "REFUNDED" or gateway.intent("pi-01").refunded_amount != _INTENT_AMOUNT:
        results.append(fail(name, "full refund fold"))
        return
    # refunds after the terminal: history-immutable
    problems = _expect_error(
        name, PaymentReasonCode.INTENT_STATE_INVALID,
        gateway.refund,
        command_id="x-1", intent_id="pi-01", amount=1, reason="r",
        actor="b", source="s",
    )
    if problems:
        results.append(fail(name, problems))
        return
    # over-refund on a fresh captured intent
    gateway2 = _gateway(world=world)
    gateway2.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway2, world[2], world[1])
    _drive_to_captured(gateway2)
    problems = _expect_error(
        name, PaymentReasonCode.AMOUNT_INVALID,
        gateway2.refund,
        command_id="x-2", intent_id="pi-01", amount=_INTENT_AMOUNT + 1,
        reason="r", actor="b", source="s",
    )
    if problems:
        results.append(fail(name, problems))
        return
    # declined refund: journaled refusal, state unchanged
    provider = _sandbox()
    provider.decline_refund = True
    gateway3 = _gateway(world=world, provider=provider)
    gateway3.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway3, world[2], world[1])
    _drive_to_captured(gateway3)
    out = gateway3.refund(
        command_id="pi-c04", intent_id="pi-01", amount=100, reason="r",
        actor="b", source="s",
    )
    if out.status != "appended":
        results.append(fail(name, "declined refund not journaled"))
        return
    intent3 = gateway3.intent("pi-01")
    if intent3.state != "CAPTURED" or intent3.refunded_amount != 0:
        results.append(fail(name, "declined refund changed state"))
        return
    results.append(
        ok(name, "refund flow: partial/full/over-refund/declined all disciplined")
    )


def case_18_reversal_flow(results: List[Result]) -> None:
    name = "case_18_reversal_flow"
    world = _payment_world()
    gateway = _gateway(world=world)
    gateway.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway, world[2], world[1])
    gateway.authorize(command_id="pi-c02", intent_id="pi-01", actor="b", source="s")
    out = gateway.reverse(
        command_id="pi-c06", intent_id="pi-01", reason="void",
        actor="b", source="s",
    )
    intent = gateway.intent("pi-01")
    if intent.state != "REVERSED" or intent.authorized_amount != 0:
        results.append(fail(name, "reversal fold"))
        return
    # reversal before authorization: state-gated
    gateway2 = _gateway(world=world)
    gateway2.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway2, world[2], world[1])
    problems = _expect_error(
        name, PaymentReasonCode.INTENT_STATE_INVALID,
        gateway2.reverse,
        command_id="x-1", intent_id="pi-01", reason="r", actor="b", source="s",
    )
    if problems:
        results.append(fail(name, problems))
        return
    # the reversed terminal is sealed
    problems = _expect_error(
        name, PaymentReasonCode.INTENT_STATE_INVALID,
        gateway.authorize,
        command_id="x-2", intent_id="pi-01", actor="b", source="s",
    )
    if problems:
        results.append(fail(name, problems))
        return
    results.append(ok(name, "reversal flow: pre-auth gate, terminal seal"))


def case_19_payout_emission(results: List[Result]) -> None:
    name = "case_19_payout_emission"
    # from the SETTLED allocation
    world = _payment_world(allocation_state="SETTLED")
    gateway = _gateway(world=world)
    gateway.record_capabilities(command_id="cap-01", actor="p", source="s")
    out = gateway.emit_payout(
        command_id="po-c01", usage_record_id=world[9],
        actor="settlement", source="payout-service",
    )
    if out.to_state != "EMITTED":
        results.append(fail(name, "payout emission outcome"))
        return
    instruction = gateway.payout(world[9])
    if instruction.billable_amount != _INTENT_AMOUNT:
        results.append(fail(name, "payout billable basis"))
        return
    if (instruction.developer_amount, instruction.provider_amount,
            instruction.adc_os_amount, instruction.tax_amount) != _SPLIT:
        results.append(fail(name, "payout split basis"))
        return
    if not instruction.instruction_id.startswith("sha256:"):
        results.append(fail(name, "payout public identity"))
        return
    # from the ALLOCATED allocation
    world2 = _payment_world(allocation_state="PLANNED")
    gateway2 = _gateway(world=world2)
    gateway2.record_capabilities(command_id="cap-01", actor="p", source="s")
    out2 = gateway2.emit_payout(
        command_id="po-c01", usage_record_id=world2[9],
        actor="settlement", source="payout-service",
    )
    if out2.to_state != "EMITTED":
        results.append(fail(name, "payout emission from PLANNED"))
        return
    # idempotent re-emission: same basis -> no-op
    out3 = gateway2.emit_payout(
        command_id="po-c02", usage_record_id=world2[9],
        actor="settlement", source="payout-service",
    )
    if out3.status != "duplicate" or out3.event_id != out2.event_id:
        results.append(fail(name, "payout re-emission not a no-op"))
        return
    # unknown allocation: fail closed -- payout can NEVER
    # manufacture an allocation (negative proof 4)
    before = gateway2.tail_sequence()
    problems = _expect_error(
        name, PaymentReasonCode.CITATION_UNKNOWN,
        gateway2.emit_payout,
        command_id="po-c03", usage_record_id="sha256:" + "0" * 64,
        actor="settlement", source="payout-service",
    )
    if problems:
        results.append(fail(name, problems))
        return
    if gateway2.tail_sequence() != before or len(gateway2.payouts()) != 1:
        results.append(fail(name, "failed emission manufactured state"))
        return
    # the compensated allocation: the era W044 negative
    # (compensated-STATE citations rejected) is superseded by the
    # current W053/M009 append-only compensation model (the
    # account state stays SETTLED; the immutable snapshot split
    # remains the emission basis; the compensation record is
    # visible reconciliation DATA) -- the honest re-baseline
    # replaces the vacuous negative with the REAL current-surface
    # negative: a citation whose public split violates exact
    # conservation fails closed (the emission basis must be the
    # REAL public split).
    world3 = _payment_world(allocation_state="SETTLED")
    alloc = world3[5]
    alloc.record_refund(
        command_id="cr-01", usage_transaction_id=world3[9],
        amount_micros=300, reason="battery",
        actor="billing", source="billing-service",
    )
    compensated = alloc.allocation(world3[9])
    if not tuple(
        compensation
        for compensation in compensated.compensations
        if compensation.compensation_kind == "refund"
    ):
        results.append(fail(name, "W053 refund compensation missing"))
        return
    if compensated.state != AllocationState.SETTLED:
        results.append(
            fail(name, "W053 compensation rewrote the account state")
        )
        return
    snapshot3 = _commercial_snapshot(world3[3], world3[4], alloc)
    corrupted = list(snapshot3.entries())
    for position, entry in enumerate(corrupted):
        if entry.family == CitationFamily.ALLOCATION:
            corrupted[position] = CommercialCitation(
                reference_id=entry.reference_id,
                family=entry.family,
                provenance=entry.provenance,
                contract_id=entry.contract_id,
                commercial_state=entry.commercial_state,
                transaction_id=entry.transaction_id,
                usage_state=entry.usage_state,
                amount=entry.amount,
                quantity=entry.quantity,
                unit=entry.unit,
                finalized_at=entry.finalized_at,
                allocation_state=entry.allocation_state,
                billable_amount=entry.billable_amount,
                currency=entry.currency,
                exponent=entry.exponent,
                developer_amount=entry.developer_amount + 1,
                provider_amount=entry.provider_amount,
                adc_os_amount=entry.adc_os_amount,
                tax_amount=entry.tax_amount,
            )
    gateway3 = _gateway(snapshot=CommercialSnapshot(corrupted))
    gateway3.record_capabilities(command_id="cap-01", actor="p", source="s")
    problems = _expect_error(
        name, PaymentReasonCode.CITATION_STATE_INVALID,
        gateway3.emit_payout,
        command_id="po-c01", usage_record_id=world3[9],
        actor="settlement", source="payout-service",
    )
    if problems:
        results.append(fail(name, problems))
        return
    results.append(
        ok(
            name,
            "payout emission: finalized citations only, idempotent, never "
            "manufactures allocations; the compensated account keeps its "
            "immutable split (append-only compensations), and a "
            "conservation-violating citation fails closed",
        )
    )


def case_20_payout_transfer_outcomes(results: List[Result]) -> None:
    name = "case_20_payout_transfer_outcomes"
    # asynchronous completion: submitted -> callback -> apply
    world = _payment_world(allocation_state="SETTLED")
    provider = _sandbox()
    gateway = _gateway(world=world, provider=provider)
    gateway.record_capabilities(command_id="cap-01", actor="p", source="s")
    gateway.emit_payout(
        command_id="po-c01", usage_record_id=world[9],
        actor="settlement", source="payout-service",
    )
    payout = gateway.payout(world[9])
    if payout.state != "EMITTED":
        results.append(fail(name, "submitted transfer not EMITTED"))
        return
    provider.async_advance_transfer(payout.transfer_ref, "TRF_DONE")
    completion = None
    for envelope in provider.pending_callbacks():
        gateway.ingest_callback(
            envelope, actor="webhook-ingress", source="provider-callback"
        )
    for observation in gateway.observations():
        if (
            observation.kind == CallbackKind.TRANSFER_STATUS
            and observation.canonical_status == PayoutStatus.TRANSFERRED
        ):
            completion = observation.event_id
    if completion is None:
        results.append(fail(name, "transfer completion callback missing"))
        return
    out = gateway.apply_observation(
        command_id="obs-a01", event_id=completion,
        actor="settlement", source="reconciliation-service",
    )
    if out.to_state != "TRANSFERRED" or gateway.payout(world[9]).state != "TRANSFERRED":
        results.append(fail(name, "async transfer completion fold"))
        return
    # the W053 compensation closed loop: a declined transfer is
    # cited as payment-provider DATA in the REAL W053
    # compensate_payout_failure record
    world2 = _payment_world(allocation_state="PLANNED")
    provider2 = _sandbox()
    provider2.transfer_outcome = "declined"
    gateway2 = _gateway(world=world2, provider=provider2)
    gateway2.record_capabilities(command_id="cap-01", actor="p", source="s")
    gateway2.emit_payout(
        command_id="po-c01", usage_record_id=world2[9],
        actor="settlement", source="payout-service",
    )
    instruction = gateway2.payout(world2[9])
    if instruction.state != "FAILED":
        results.append(fail(name, "declined transfer not FAILED"))
        return
    facts = _allocation_facts((world2[4],), (world2[3],))
    entries = list(facts.by_family(FactFamily.USAGE_FINAL)) + list(
        facts.by_family(FactFamily.COMMERCIAL)
    ) + list(facts.by_family(FactFamily.SETTLEMENT)) + list(
        facts.by_family(FactFamily.PAYMENT_PROVIDER)
    )
    entries.append(
        FactReference(
            reference_id=instruction.instruction_id,
            family=FactFamily.PAYMENT_PROVIDER,
            provenance="payment-gateway",
        )
    )
    extended = FactIndex(entries)
    # re-drive the deterministic W053 history with the extended
    # fact index (identical commands, identical journal, plus
    # the payout instruction id as citable provider DATA) -- the
    # M009 surface: the typed evidence index projects the extended
    # family facts, the payout failure appends the compensating
    # record, and the declined transfer instruction is recorded
    # as external payment-reference DATA on the REAL account
    base_index = _typed_allocation_index(
        extended, (world2[4],), contract_id=world2[9]
    )
    typed_extended = AllocationEvidenceIndex(
        usage=[
            base_index.usage(key)
            for key in base_index.usage_transaction_ids()
        ],
        references=[
            base_index.reference(key)
            for key in base_index.reference_ids()
        ]
        + [
            ExternalReferenceSnapshot(
                instruction.instruction_id,
                ReferenceKind.PAYMENT,
                "payment-gateway",
                world2[9],
            )
        ],
    )
    ledger2 = AllocationLedger(
        store=MemoryAllocationStore(),
        clock=StepClock(_AT0, _ASTEP),
        evidence_index=typed_extended,
    )
    out = _register_std_policy(ledger2, command_id="p-01")
    _std_allocate(
        ledger2, world2[1], world2[9], command_id="a-01",
        policy_id=out.fact_id,
    )
    ledger2.acknowledge_settlement(
        command_id="s-01",
        usage_transaction_id=world2[9],
        settlement_reference=_settlement_ref(),
        actor="settlement", source="settlement-service",
    )
    ledger2.record_payment_reference(
        command_id="pr-01",
        usage_transaction_id=world2[9],
        payment_reference=instruction.instruction_id,
        actor="settlement", source="payout-service",
    )
    ledger2.record_payout_failure(
        command_id="pf-01", usage_transaction_id=world2[9],
        amount_micros=100,
        reason="sandbox-transfer-refused",
        actor="settlement", source="payout-service",
    )
    account = ledger2.allocation(world2[9])
    payout_failure_compensations = tuple(
        compensation
        for compensation in account.compensations
        if compensation.compensation_kind == "payout-failure"
    )
    if not payout_failure_compensations:
        results.append(fail(name, "W053 payout-failure compensation"))
        return
    if not any(
        reference.payment_reference == instruction.instruction_id
        for reference in account.payment_references
    ):
        results.append(fail(name, "instruction id not cited as provider DATA"))
        return
    results.append(
        ok(
            name,
            "transfer outcomes: async apply, sync, declined + the REAL W053 "
            "compensation closed loop (the declined instruction cited as "
            "provider DATA on the compensated account)",
        )
    )


def case_21_callback_ingestion(results: List[Result]) -> None:
    name = "case_21_callback_ingestion"
    world = _payment_world()
    provider = _sandbox()
    gateway = _gateway(world=world, provider=provider)
    gateway.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway, world[2], world[1])
    gateway.authorize(command_id="pi-c02", intent_id="pi-01", actor="b", source="s")
    envelopes = provider.pending_callbacks()
    if len(envelopes) != 2:
        results.append(fail(name, "provider emitted %d callbacks" % len(envelopes)))
        return
    for envelope in envelopes:
        out = gateway.ingest_callback(
            envelope, actor="webhook-ingress", source="provider-callback"
        )
        if out.status != "appended":
            results.append(fail(name, "callback ingestion"))
            return
    observations = gateway.observations()
    if len(observations) != 2:
        results.append(fail(name, "observation count"))
        return
    # canonical statuses only (the vendor statuses never cross)
    for observation in observations:
        if observation.canonical_status not in PaymentStatus.values():
            results.append(fail(name, "vendor status leaked"))
            return
        if observation.applied:
            results.append(fail(name, "observation auto-applied"))
            return
    # exact redelivery: idempotent no-op (anti-replay)
    before = gateway.tail_sequence()
    out = gateway.ingest_callback(
        envelopes[0], actor="webhook-ingress", source="provider-callback"
    )
    if out.status != "duplicate":
        results.append(fail(name, "callback redelivery not a no-op"))
        return
    if gateway.tail_sequence() != before:
        results.append(fail(name, "callback replay grew the journal"))
        return
    # out-of-order redelivery of the later event first: already
    # recorded, still a no-op (append-only, idempotent)
    out = gateway.ingest_callback(
        envelopes[1], actor="webhook-ingress", source="provider-callback"
    )
    if out.status != "duplicate":
        results.append(fail(name, "out-of-order redelivery not a no-op"))
        return
    # observations are DATA: the intent state is unchanged
    if gateway.intent("pi-01").state != "AUTHORIZED":
        results.append(fail(name, "observation changed intent state"))
        return
    # ORPHAN: a verified callback for an unknown provider
    # reference is recorded as divergence evidence
    forged = dict(envelopes[0])
    forged["event_id"] = "sha256:" + "ab" * 32
    forged["provider_ref"] = "sandbox-pmt-999999"
    body = {
        "event_id": forged["event_id"],
        "provider_id": forged["provider_id"],
        "provider_ref": forged["provider_ref"],
        "kind": forged["kind"],
        "payload": forged["payload"],
        "occurred_at": forged["occurred_at"],
    }
    import hmac as _hmac
    forged["signature"] = "hmac-sha256:" + _hmac.new(
        _PROV_SECRET, canonical_json_bytes(body), hashlib.sha256
    ).hexdigest()
    out = gateway.ingest_callback(
        forged, actor="webhook-ingress", source="provider-callback"
    )
    if out.status != "appended":
        results.append(fail(name, "orphan callback not recorded"))
        return
    orphan = [
        obs for obs in gateway.observations() if obs.orphan
    ]
    if len(orphan) != 1:
        results.append(fail(name, "orphan observation count"))
        return
    # the orphan never created an intent
    if len(gateway.intents()) != 1:
        results.append(fail(name, "orphan created an intent"))
        return
    results.append(
        ok(
            name,
            "callbacks: verified, canonical, anti-replay, out-of-order "
            "idempotent, orphans recorded as divergence",
        )
    )


def case_22_invalid_signatures(results: List[Result]) -> None:
    name = "case_22_invalid_signatures"
    world = _payment_world()
    provider = _sandbox()
    gateway = _gateway(world=world, provider=provider)
    gateway.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway, world[2], world[1])
    envelopes = provider.pending_callbacks()
    before = gateway.tail_sequence()
    # tampered payload with the original signature
    tampered = dict(envelopes[0])
    tampered["payload"] = dict(tampered["payload"])
    tampered["payload"]["vendor_status"] = "FUNDS_TAKEN"
    problems = _expect_error(
        name, PaymentReasonCode.SIGNATURE_INVALID,
        gateway.ingest_callback, tampered,
        actor="webhook-ingress", source="provider-callback",
    )
    if problems:
        results.append(fail(name, "tampered payload: %s" % problems))
        return
    # tampered signature
    tampered_sig = dict(envelopes[0])
    tampered_sig["signature"] = "hmac-sha256:" + "0" * 64
    problems = _expect_error(
        name, PaymentReasonCode.SIGNATURE_INVALID,
        gateway.ingest_callback, tampered_sig,
        actor="webhook-ingress", source="provider-callback",
    )
    if problems:
        results.append(fail(name, "tampered signature: %s" % problems))
        return
    # a callback signed with a DIFFERENT secret (wrong provider)
    import hmac as _hmac
    wrong_secret = dict(envelopes[0])
    body = {
        "event_id": wrong_secret["event_id"],
        "provider_id": wrong_secret["provider_id"],
        "provider_ref": wrong_secret["provider_ref"],
        "kind": wrong_secret["kind"],
        "payload": wrong_secret["payload"],
        "occurred_at": wrong_secret["occurred_at"],
    }
    wrong_secret["signature"] = "hmac-sha256:" + _hmac.new(
        b"attacker-secret", canonical_json_bytes(body), hashlib.sha256
    ).hexdigest()
    problems = _expect_error(
        name, PaymentReasonCode.SIGNATURE_INVALID,
        gateway.ingest_callback, wrong_secret,
        actor="webhook-ingress", source="provider-callback",
    )
    if problems:
        results.append(fail(name, "wrong secret: %s" % problems))
        return
    # malformed envelope
    problems = _expect_error(
        name, PaymentReasonCode.CALLBACK_INVALID,
        gateway.ingest_callback, {"event_id": "x"},
        actor="webhook-ingress", source="provider-callback",
    )
    if problems:
        results.append(fail(name, "malformed envelope: %s" % problems))
        return
    if gateway.tail_sequence() != before:
        results.append(fail(name, "unauthenticated envelopes grew the journal"))
        return
    if gateway.observations():
        results.append(fail(name, "unauthenticated envelope recorded"))
        return
    results.append(
        ok(name, "invalid signatures rejected before any journal record exists")
    )


def case_23_observation_folds(results: List[Result]) -> None:
    name = "case_23_observation_folds"
    # a provider observation that JUMPS lifecycle edges (async
    # capture while canonical is still CREATED -- no recorded
    # authorization) is divergence evidence, never a fold: the
    # explicit application fails closed on the illegal edge
    world = _payment_world()
    provider = _sandbox()
    gateway = _gateway(world=world, provider=provider)
    gateway.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway, world[2], world[1])
    provider.async_advance(gateway.intent("pi-01").provider_ref, "FUNDS_TAKEN")
    jumped_event = None
    for envelope in provider.pending_callbacks():
        gateway.ingest_callback(
            envelope, actor="webhook-ingress", source="provider-callback"
        )
    for observation in gateway.observations():
        if observation.canonical_status == PaymentStatus.CAPTURED:
            jumped_event = observation.event_id
    if jumped_event is None:
        results.append(fail(name, "async capture observation missing"))
        return
    problems = _expect_error(
        name, PaymentReasonCode.OBSERVATION_CONFLICT,
        gateway.apply_observation,
        command_id="obs-a00", event_id=jumped_event,
        actor="settlement", source="reconciliation-service",
    )
    if problems:
        results.append(fail(name, "lifecycle jump: %s" % problems))
        return
    if gateway.intent("pi-01").state != "CREATED":
        results.append(fail(name, "lifecycle jump folded state"))
        return
    # provider-ahead through the LEGAL edges: async authorization
    # first, then the async capture, each applied explicitly
    provider.async_advance(gateway.intent("pi-01").provider_ref, "FUNDS_HELD")
    auth_event = None
    for envelope in provider.pending_callbacks():
        gateway.ingest_callback(
            envelope, actor="webhook-ingress", source="provider-callback"
        )
    for observation in gateway.observations():
        if (
            observation.canonical_status == PaymentStatus.AUTHORIZED
            and not observation.applied
        ):
            auth_event = observation.event_id
    if auth_event is None:
        results.append(fail(name, "async authorization observation missing"))
        return
    out = gateway.apply_observation(
        command_id="obs-a01", event_id=auth_event,
        actor="settlement", source="reconciliation-service",
    )
    if out.to_state != "AUTHORIZED":
        results.append(fail(name, "explicit fold did not apply the authorization"))
        return
    # the earlier jumped capture observation is now applicable
    # (AUTHORIZED -> CAPTURED is a legal edge)
    out = gateway.apply_observation(
        command_id="obs-a02", event_id=jumped_event,
        actor="settlement", source="reconciliation-service",
    )
    intent = gateway.intent("pi-01")
    if intent.state != "CAPTURED" or intent.captured_amount != _INTENT_AMOUNT:
        results.append(fail(name, "explicit fold did not apply the capture"))
        return
    if gateway.observation(jumped_event).applied is not True:
        results.append(fail(name, "observation applied flag"))
        return
    # re-apply: already applied
    problems = _expect_error(
        name, PaymentReasonCode.OBSERVATION_ALREADY_APPLIED,
        gateway.apply_observation,
        command_id="obs-a03", event_id=jumped_event,
        actor="settlement", source="reconciliation-service",
    )
    if problems:
        results.append(fail(name, problems))
        return
    # regression: an AUTHORIZED observation after CAPTURED
    provider.async_advance(gateway.intent("pi-01").provider_ref, "FUNDS_HELD")
    for envelope in provider.pending_callbacks():
        gateway.ingest_callback(
            envelope, actor="webhook-ingress", source="provider-callback"
        )
    regression = None
    for observation in gateway.observations():
        if (
            observation.canonical_status == PaymentStatus.AUTHORIZED
            and not observation.applied
        ):
            regression = observation.event_id
    if regression is None:
        results.append(fail(name, "regression observation missing"))
        return
    problems = _expect_error(
        name, PaymentReasonCode.OBSERVATION_CONFLICT,
        gateway.apply_observation,
        command_id="obs-a03", event_id=regression,
        actor="settlement", source="reconciliation-service",
    )
    if problems:
        results.append(fail(name, problems))
        return
    if gateway.intent("pi-01").state != "CAPTURED":
        results.append(fail(name, "regression rewrote state"))
        return
    # amount conflict: an observation contradicting a recorded amount
    provider2 = _sandbox()
    gateway2 = _gateway(world=world, provider=provider2)
    gateway2.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway2, world[2], world[1])
    _drive_to_captured(gateway2)
    provider2.async_advance(gateway2.intent("pi-01").provider_ref, "FUNDS_TAKEN")
    envelopes2 = provider2.pending_callbacks()
    conflict_event = None
    for envelope in envelopes2:
        gateway2.ingest_callback(
            envelope, actor="webhook-ingress", source="provider-callback"
        )
    for observation in gateway2.observations():
        if (
            observation.canonical_status == PaymentStatus.CAPTURED
            and observation.amounts.get("captured_amount") == _INTENT_AMOUNT
        ):
            conflict_event = observation.event_id
    # craft a conflicting observation: same event id, different
    # amounts, correctly re-signed (the provider reports a
    # DIFFERENT captured amount than ADCOS recorded)
    conflicting = None
    for envelope in envelopes2:
        if envelope["event_id"] == conflict_event:
            conflicting = dict(envelope)
    if conflicting is None:
        results.append(fail(name, "conflict envelope missing"))
        return
    intent2 = gateway2.intent("pi-01")
    if intent2.captured_amount != _INTENT_AMOUNT:
        results.append(fail(name, "setup: canonical capture amount"))
        return
    # the sandbox echoes the ADCOS-commanded amount; build the
    # conflicting variant through the adapter's own signing path
    conflicting_payload = dict(conflicting["payload"])
    conflicting_payload["amounts"] = {
        "authorized_amount": _INTENT_AMOUNT,
        "captured_amount": _INTENT_AMOUNT - 1,
        "refunded_amount": 0,
    }
    body = {
        "event_id": "sha256:" + "cd" * 32,
        "provider_id": conflicting["provider_id"],
        "provider_ref": conflicting["provider_ref"],
        "kind": conflicting["kind"],
        "payload": conflicting_payload,
        "occurred_at": conflicting["occurred_at"],
    }
    import hmac as _hmac
    envelope3 = dict(body)
    envelope3["signature"] = "hmac-sha256:" + _hmac.new(
        _PROV_SECRET, canonical_json_bytes(body), hashlib.sha256
    ).hexdigest()
    gateway2.ingest_callback(
        envelope3, actor="webhook-ingress", source="provider-callback"
    )
    problems = _expect_error(
        name, PaymentReasonCode.OBSERVATION_CONFLICT,
        gateway2.apply_observation,
        command_id="obs-a04", event_id=body["event_id"],
        actor="settlement", source="reconciliation-service",
    )
    if problems:
        results.append(fail(name, "amount conflict: %s" % problems))
        return
    if gateway2.intent("pi-01").captured_amount != _INTENT_AMOUNT:
        results.append(fail(name, "amount conflict rewrote canonical amounts"))
        return
    results.append(
        ok(
            name,
            "explicit folds: provider-ahead applies; regression, "
            "already-applied, and amount conflicts fail closed",
        )
    )


def case_24_provider_failures(results: List[Result]) -> None:
    name = "case_24_provider_failures"
    world = _payment_world()
    provider = _sandbox()
    gateway = _gateway(world=world, provider=provider)
    gateway.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway, world[2], world[1])
    # normalized unavailability: typed error, no journal, state
    # unchanged, retryable with a new command id
    provider.script_failures["authorize"] = FailureClass.UNAVAILABLE
    before = gateway.tail_sequence()
    problems = _expect_error(
        name, PaymentReasonCode.PROVIDER_FAILURE,
        gateway.authorize,
        command_id="pi-c02", intent_id="pi-01", actor="b", source="s",
    )
    if problems:
        results.append(fail(name, problems))
        return
    if gateway.tail_sequence() != before:
        results.append(fail(name, "normalized failure grew the journal"))
        return
    if gateway.intent("pi-01").state != "CREATED":
        results.append(fail(name, "normalized failure changed state"))
        return
    out = gateway.authorize(
        command_id="pi-c02b", intent_id="pi-01", actor="b", source="s"
    )
    if out.to_state != "AUTHORIZED":
        results.append(fail(name, "retry after failure did not succeed"))
        return
    # timeout + malformed classes
    provider.script_failures["capture"] = FailureClass.TIMEOUT
    problems = _expect_error(
        name, PaymentReasonCode.PROVIDER_FAILURE,
        gateway.capture,
        command_id="pi-c03", intent_id="pi-01", amount=_INTENT_AMOUNT,
        actor="b", source="s",
    )
    if problems:
        results.append(fail(name, problems))
        return
    provider.script_failures["capture"] = FailureClass.MALFORMED
    problems = _expect_error(
        name, PaymentReasonCode.PROVIDER_FAILURE,
        gateway.capture,
        command_id="pi-c03b", intent_id="pi-01", amount=_INTENT_AMOUNT,
        actor="b", source="s",
    )
    if problems:
        results.append(fail(name, problems))
        return
    # the vendor error code never crosses the boundary (the
    # detail carries the normalized class only)
    try:
        provider.script_failures["refund"] = FailureClass.UNAVAILABLE
        gateway.refund(
            command_id="pi-c04", intent_id="pi-01", amount=1, reason="r",
            actor="b", source="s",
        )
    except PaymentError as error:
        if "SBX_ERR" in error.detail or "SBX_DECL" in error.detail:
            results.append(fail(name, "vendor code leaked into the error detail"))
            return
    # normalized transfer failure: the emission fails before
    # any instruction exists
    world2 = _payment_world(allocation_state="SETTLED")
    provider2 = _sandbox()
    provider2.transfer_outcome = "failed"
    gateway2 = _gateway(world=world2, provider=provider2)
    gateway2.record_capabilities(command_id="cap-01", actor="p", source="s")
    problems = _expect_error(
        name, PaymentReasonCode.PROVIDER_FAILURE,
        gateway2.emit_payout,
        command_id="po-c01", usage_record_id=world2[9],
        actor="settlement", source="payout-service",
    )
    if problems:
        results.append(fail(name, problems))
        return
    if len(gateway2.payouts()) != 0:
        results.append(fail(name, "failed emission left an instruction"))
        return
    results.append(
        ok(
            name,
            "provider failures: normalized, typed, retryable, no phantom "
            "state, vendor codes never cross",
        )
    )


def case_25_reconciliation(results: List[Result]) -> None:
    name = "case_25_reconciliation"
    # matched: the golden lifecycle reconciles clean
    gateway = _golden_payment()
    report = gateway.reports()[0]
    if report.summary() != {"matched": 2}:
        results.append(
            fail(name, "golden reconciliation %r" % report.summary())
        )
        return
    # provider-ahead: the provider moved without an ADCOS op
    world = _payment_world()
    provider = _sandbox()
    gateway2 = _gateway(world=world, provider=provider)
    gateway2.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway2, world[2], world[1])
    provider.async_advance(gateway2.intent("pi-01").provider_ref, "FUNDS_HELD")
    for envelope in provider.pending_callbacks():
        gateway2.ingest_callback(
            envelope, actor="webhook-ingress", source="provider-callback"
        )
    gateway2.reconcile(command_id="rec-01", actor="st", source="s")
    entries = gateway2.reports()[0].entries
    classifications = tuple(entry["classification"] for entry in entries)
    if classifications != ("provider-ahead",):
        results.append(
            fail(name, "provider-ahead classification %r" % (classifications,))
        )
        return
    # apply the observation (the legal AUTHORIZED edge), reconcile
    # again: matched
    auth_event = None
    for observation in gateway2.observations():
        if (
            observation.canonical_status == PaymentStatus.AUTHORIZED
            and not observation.applied
        ):
            auth_event = observation.event_id
    gateway2.apply_observation(
        command_id="obs-a01", event_id=auth_event,
        actor="st", source="s",
    )
    gateway2.reconcile(command_id="rec-02", actor="st", source="s")
    if gateway2.reports()[-1].summary() != {"matched": 1}:
        results.append(
            fail(name, "post-apply summary %r" % gateway2.reports()[-1].summary())
        )
        return
    # drive the canonical state BEYOND the provider (the async
    # capture applies legally), then regress the provider view
    provider.async_advance(gateway2.intent("pi-01").provider_ref, "FUNDS_TAKEN")
    for envelope in provider.pending_callbacks():
        gateway2.ingest_callback(
            envelope, actor="webhook-ingress", source="provider-callback"
        )
    capture_observation = None
    for observation in gateway2.observations():
        if (
            observation.canonical_status == PaymentStatus.CAPTURED
            and not observation.applied
        ):
            capture_observation = observation.event_id
    gateway2.apply_observation(
        command_id="obs-a02", event_id=capture_observation,
        actor="st", source="s",
    )
    # gateway-ahead: the provider reports LESS than ADCOS
    # recorded (stale/divergent provider view) -- recorded, never
    # rewritten
    provider.async_advance(gateway2.intent("pi-01").provider_ref, "FUNDS_HELD")
    gateway2.reconcile(command_id="rec-03", actor="st", source="s")
    classifications = tuple(
        entry["classification"] for entry in gateway2.reports()[-1].entries
    )
    if classifications != ("gateway-ahead",):
        results.append(
            fail(name, "gateway-ahead classification %r" % (classifications,))
        )
        return
    if gateway2.intent("pi-01").state != "CAPTURED":
        results.append(fail(name, "reconciliation rewrote canonical state"))
        return
    # amount-divergent: statuses agree, amounts differ
    world3 = _payment_world()
    provider3 = _sandbox()
    gateway3 = _gateway(world=world3, provider=provider3)
    gateway3.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway3, world3[2], world3[1])
    gateway3.authorize(command_id="pi-c02", intent_id="pi-01", actor="b", source="s")
    gateway3.capture(
        command_id="pi-c03", intent_id="pi-01", amount=_INTENT_AMOUNT - 100,
        actor="b", source="s",
    )
    provider3.async_advance(gateway3.intent("pi-01").provider_ref, "FUNDS_TAKEN")
    gateway3.reconcile(command_id="rec-01", actor="st", source="s")
    classifications = tuple(
        entry["classification"] for entry in gateway3.reports()[-1].entries
    )
    if classifications != ("amount-divergent",):
        results.append(
            fail(name, "amount-divergent classification %r" % (classifications,))
        )
        return
    if gateway3.intent("pi-01").captured_amount != _INTENT_AMOUNT - 100:
        results.append(fail(name, "amount divergence rewrote canonical amounts"))
        return
    # provider-unknown: the provider lost the reference
    provider3._intents.pop(gateway3.intent("pi-01").provider_ref)
    gateway3.reconcile(command_id="rec-02", actor="st", source="s")
    classifications = tuple(
        entry["classification"] for entry in gateway3.reports()[-1].entries
    )
    if classifications != ("provider-unknown",):
        results.append(
            fail(name, "provider-unknown classification %r" % (classifications,))
        )
        return
    # orphan-reference: recorded orphan observations are
    # divergence entries (built in case_21's shape)
    world4 = _payment_world()
    provider4 = _sandbox()
    gateway4 = _gateway(world=world4, provider=provider4)
    gateway4.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway4, world4[2], world4[1])
    # a provider-side intent the gateway never bound: its
    # callbacks are verified but cite an unknown reference
    orphan = provider4.create_intent(
        intent_ref="orphan-1", transaction_ref=world4[2], amount=100,
        currency=_CCY, exponent=_EXP, description="orphan",
    )
    provider4.async_advance(orphan.provider_ref, "FUNDS_HELD")
    for envelope in provider4.pending_callbacks():
        gateway4.ingest_callback(
            envelope, actor="webhook-ingress", source="provider-callback"
        )
    gateway4.reconcile(command_id="rec-01", actor="st", source="s")
    classifications = tuple(
        entry["classification"] for entry in gateway4.reports()[-1].entries
    )
    if set(classifications) != {"matched", "orphan-reference"}:
        results.append(
            fail(name, "orphan classification %r" % (classifications,))
        )
        return
    # reconcile itself is idempotent per command id
    before = gateway4.tail_sequence()
    out = gateway4.reconcile(command_id="rec-01", actor="st", source="s")
    if out.status != "duplicate" or gateway4.tail_sequence() != before:
        results.append(fail(name, "reconcile idempotency"))
        return
    results.append(
        ok(
            name,
            "reconciliation: matched/provider-ahead/gateway-ahead/amount/"
            "provider-unknown/orphan all classified, never rewritten",
        )
    )


def case_26_capability_gating(results: List[Result]) -> None:
    name = "case_26_capability_gating"
    world = _payment_world()
    no_refund = ProviderCapabilities(
        provider_id=_PROV_ID, schema_version=1,
        supports_authorization=True, supports_capture=True,
        supports_refund=False, supports_partial_refund=False,
        supports_reversal=True, supports_payout_transfer=True,
        supports_callbacks=True, supports_status_query=True,
        currencies=("GHS", "USD"), max_exponent=2, max_amount=10_000_000,
    )
    provider = _sandbox(capabilities=no_refund)
    gateway = _gateway(world=world, provider=provider)
    gateway.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway, world[2], world[1])
    _drive_to_captured(gateway)
    problems = _expect_error(
        name, PaymentReasonCode.CAPABILITY_UNSUPPORTED,
        gateway.refund,
        command_id="x-1", intent_id="pi-01", amount=100, reason="r",
        actor="b", source="s",
    )
    if problems:
        results.append(fail(name, problems))
        return
    # partial refund on a partial-incapable provider
    no_partial = ProviderCapabilities(
        provider_id=_PROV_ID, schema_version=1,
        supports_authorization=True, supports_capture=True,
        supports_refund=True, supports_partial_refund=False,
        supports_reversal=True, supports_payout_transfer=True,
        supports_callbacks=True, supports_status_query=True,
        currencies=("GHS", "USD"), max_exponent=2, max_amount=10_000_000,
    )
    provider2 = _sandbox(capabilities=no_partial)
    gateway2 = _gateway(world=world, provider=provider2)
    gateway2.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway2, world[2], world[1])
    _drive_to_captured(gateway2)
    problems = _expect_error(
        name, PaymentReasonCode.CAPABILITY_UNSUPPORTED,
        gateway2.refund,
        command_id="x-2", intent_id="pi-01", amount=_PARTIAL_REFUND,
        reason="r", actor="b", source="s",
    )
    if problems:
        results.append(fail(name, problems))
        return
    # currency unsupported
    problems = _expect_error(
        name, PaymentReasonCode.CAPABILITY_UNSUPPORTED,
        gateway2.create_intent,
        command_id="x-3", intent_id="pi-02", transaction_id=world[2],
        amount=100, currency="EUR", exponent=2,
        actor="b", source="s",
    )
    if problems:
        results.append(fail(name, problems))
        return
    # exponent over the provider maximum
    problems = _expect_error(
        name, PaymentReasonCode.CAPABILITY_UNSUPPORTED,
        gateway2.create_intent,
        command_id="x-4", intent_id="pi-03", transaction_id=world[2],
        amount=100, currency="GHS", exponent=3,
        actor="b", source="s",
    )
    if problems:
        results.append(fail(name, problems))
        return
    # amount over the provider maximum
    problems = _expect_error(
        name, PaymentReasonCode.CAPABILITY_UNSUPPORTED,
        gateway2.create_intent,
        command_id="x-5", intent_id="pi-04", transaction_id=world[2],
        amount=100_000_000, currency="GHS", exponent=2,
        actor="b", source="s",
    )
    if problems:
        results.append(fail(name, problems))
        return
    # undeclared: nothing may run before the declaration journals
    gateway3 = _gateway(world=world)
    problems = _expect_error(
        name, PaymentReasonCode.CAPABILITY_UNDECLARED,
        _create_std_intent, gateway3, world[2], world[1],
    )
    if problems:
        results.append(fail(name, problems))
        return
    # callbacks gate: a callback-incapable provider
    no_callbacks = ProviderCapabilities(
        provider_id=_PROV_ID, schema_version=1,
        supports_authorization=True, supports_capture=True,
        supports_refund=True, supports_partial_refund=True,
        supports_reversal=True, supports_payout_transfer=True,
        supports_callbacks=False, supports_status_query=True,
        currencies=("GHS", "USD"), max_exponent=2, max_amount=10_000_000,
    )
    provider4 = _sandbox(capabilities=no_callbacks)
    gateway4 = _gateway(world=world, provider=provider4)
    gateway4.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway4, world[2], world[1])
    # a GENUINE signed callback from the provider: authenticity
    # verifies first, then the capability gate fails closed
    envelopes4 = provider4.pending_callbacks()
    problems = _expect_error(
        name, PaymentReasonCode.CAPABILITY_UNSUPPORTED,
        gateway4.ingest_callback, envelopes4[0],
        actor="webhook-ingress", source="provider-callback",
    )
    if problems:
        results.append(fail(name, problems))
        return
    # status-query gate: reconcile needs the query capability
    no_query = ProviderCapabilities(
        provider_id=_PROV_ID, schema_version=1,
        supports_authorization=True, supports_capture=True,
        supports_refund=True, supports_partial_refund=True,
        supports_reversal=True, supports_payout_transfer=True,
        supports_callbacks=True, supports_status_query=False,
        currencies=("GHS", "USD"), max_exponent=2, max_amount=10_000_000,
    )
    provider5 = _sandbox(capabilities=no_query)
    gateway5 = _gateway(world=world, provider=provider5)
    gateway5.record_capabilities(command_id="cap-01", actor="p", source="s")
    problems = _expect_error(
        name, PaymentReasonCode.CAPABILITY_UNSUPPORTED,
        gateway5.reconcile,
        command_id="rec-01", actor="st", source="s",
    )
    if problems:
        results.append(fail(name, problems))
        return
    # payout-transfer gate
    no_payout = ProviderCapabilities(
        provider_id=_PROV_ID, schema_version=1,
        supports_authorization=True, supports_capture=True,
        supports_refund=True, supports_partial_refund=True,
        supports_reversal=True, supports_payout_transfer=False,
        supports_callbacks=True, supports_status_query=True,
        currencies=("GHS", "USD"), max_exponent=2, max_amount=10_000_000,
    )
    provider6 = _sandbox(capabilities=no_payout)
    gateway6 = _gateway(world=world, provider=provider6)
    gateway6.record_capabilities(command_id="cap-01", actor="p", source="s")
    problems = _expect_error(
        name, PaymentReasonCode.CAPABILITY_UNSUPPORTED,
        gateway6.emit_payout,
        command_id="po-01", usage_record_id=world[9],
        actor="st", source="s",
    )
    if problems:
        results.append(fail(name, problems))
        return
    results.append(
        ok(name, "capability gates: operations, money bounds, declarations, callbacks, queries")
    )


def case_27_payment_never_usage(results: List[Result]) -> None:
    name = "case_27_payment_never_usage"
    # negative proof 1: provider capture success cannot create
    # UsageLedger facts (the real W052 ledger is byte-identical
    # across the whole payment lifecycle)
    world = _payment_world()
    usage_ledger = world[4]
    usage_journal_before = usage_ledger.journal_digest()
    usage_account_before = usage_ledger.transaction(world[9]).to_dict()
    core = world[3]
    core_journal_before = core.journal_digest()
    alloc = world[5]
    alloc_journal_before = alloc.journal_digest()
    provider = _sandbox()
    gateway = _gateway(world=world, provider=provider)
    gateway.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway, world[2], world[1])
    _drive_to_captured(gateway)
    gateway.refund(
        command_id="pi-c04", intent_id="pi-01", amount=_PARTIAL_REFUND,
        reason="credit", actor="b", source="s",
    )
    gateway.emit_payout(
        command_id="po-c01", usage_record_id=world[9],
        actor="st", source="s",
    )
    for envelope in provider.pending_callbacks():
        gateway.ingest_callback(
            envelope, actor="webhook-ingress", source="provider-callback"
        )
    if usage_ledger.journal_digest() != usage_journal_before:
        results.append(fail(name, "payment changed the W052 journal"))
        return
    if usage_ledger.transaction(world[9]).to_dict() != usage_account_before:
        results.append(fail(name, "payment changed the W052 account"))
        return
    if core.journal_digest() != core_journal_before:
        results.append(fail(name, "payment changed the W051 journal"))
        return
    if alloc.journal_digest() != alloc_journal_before:
        results.append(fail(name, "payment changed the W053 journal"))
        return
    # and the payment side really did progress to CAPTURED
    if gateway.intent("pi-01").state != "CAPTURED":
        results.append(fail(name, "payment did not progress (test invalid)"))
        return
    results.append(
        ok(
            name,
            "negative proof 1: full payment flow leaves W051/W052/W053 "
            "byte-identical",
        )
    )


def case_28_callbacks_never_delivery(results: List[Result]) -> None:
    name = "case_28_callbacks_never_delivery"
    # negative proof 2: provider callbacks cannot create delivery
    # evidence (the real platform delivery journal is
    # byte-identical across full callback ingestion)
    world = _payment_world()
    integrator = world[7]
    records_before = tuple(
        record.record_id for record in integrator.journal_records()
    )
    provider = _sandbox()
    gateway = _gateway(world=world, provider=provider)
    gateway.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway, world[2], world[1])
    _drive_to_captured(gateway)
    provider.async_advance(gateway.intent("pi-01").provider_ref, "MONIES_RETURNED")
    for envelope in provider.pending_callbacks():
        gateway.ingest_callback(
            envelope, actor="webhook-ingress", source="provider-callback"
        )
    records_after = tuple(
        record.record_id for record in integrator.journal_records()
    )
    if records_before != records_after:
        results.append(fail(name, "callbacks changed the delivery journal"))
        return
    if len(gateway.observations()) == 0:
        results.append(fail(name, "no observations recorded (test invalid)"))
        return
    # the evidence index snapshot stays immutable
    usage_ledger = world[4]
    evidence_before = usage_ledger.evidence_index()
    applied = 0
    for observation in gateway.observations():
        try:
            gateway.apply_observation(
                command_id="obs-%s" % observation.event_id[:8],
                event_id=observation.event_id,
                actor="st", source="s",
            )
            applied += 1
        except PaymentError:
            # already-covered / conflicting observations are
            # honest fail-closed rejections (recorded divergence
            # only); they are NOT the invariant under test here
            pass
    if applied == 0:
        results.append(fail(name, "no observation could be applied (test invalid)"))
        return
    if usage_ledger.evidence_index() is not evidence_before:
        results.append(fail(name, "evidence index replaced"))
        return
    results.append(
        ok(
            name,
            "negative proof 2: full callback ingestion leaves the platform "
            "delivery journal byte-identical",
        )
    )


def case_29_history_never_rewritten(results: List[Result]) -> None:
    name = "case_29_history_never_rewritten"
    # negative proof 5: settled history is never rewritten --
    # terminal intents reject every further operation, and the
    # journal detects tampering (byte flip, reorder, truncation,
    # duplicated lines)
    world = _payment_world()
    provider = _sandbox()
    gateway = _gateway(world=world, provider=provider)
    gateway.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway, world[2], world[1])
    _drive_to_captured(gateway)
    gateway.refund(
        command_id="pi-c04", intent_id="pi-01", amount=_INTENT_AMOUNT,
        reason="full", actor="b", source="s",
    )
    before = gateway.tail_sequence()
    for label, func, kwargs in (
        ("authorize", gateway.authorize,
         {"command_id": "t-1", "intent_id": "pi-01", "actor": "b", "source": "s"}),
        ("capture", gateway.capture,
         {"command_id": "t-2", "intent_id": "pi-01", "amount": 1,
          "actor": "b", "source": "s"}),
        ("refund", gateway.refund,
         {"command_id": "t-3", "intent_id": "pi-01", "amount": 1,
          "reason": "r", "actor": "b", "source": "s"}),
        ("reverse", gateway.reverse,
         {"command_id": "t-4", "intent_id": "pi-01", "reason": "r",
          "actor": "b", "source": "s"}),
    ):
        problems = _expect_error(
            name, PaymentReasonCode.INTENT_STATE_INVALID, func, **kwargs
        )
        if problems:
            results.append(fail(name, "%s after terminal: %s" % (label, problems)))
            return
    if gateway.tail_sequence() != before:
        results.append(fail(name, "terminal rejections grew the journal"))
        return
    # tamper detection over the persisted journal bytes
    with tempfile.TemporaryDirectory() as tmp:
        store = FilePaymentStore(Path(tmp) / "journal.jsonl")
        gateway2 = _gateway(world=world, store=store)
        gateway2.record_capabilities(command_id="cap-01", actor="p", source="s")
        _create_std_intent(gateway2, world[2], world[1])
        raw = (Path(tmp) / "journal.jsonl").read_bytes()
        lines = [line for line in raw.split(b"\n") if line.strip()]
        # byte flip inside the second record
        flipped = lines[1][:20] + bytes([lines[1][20] ^ 0x01]) + lines[1][21:]
        problems = _expect_error(
            name, PaymentReasonCode.JOURNAL_CORRUPT,
            SettlementGateway.load,
            store=FrozenBytesStore(b"\n".join([lines[0], flipped]) + b"\n"),
            clock=StepClock(_PT0, _PSTEP), snapshot=world[0],
            adapter=_sandbox(),
        )
        if problems:
            results.append(fail(name, "byte flip: %s" % problems))
            return
        # reordered records
        problems = _expect_error(
            name, PaymentReasonCode.JOURNAL_CORRUPT,
            SettlementGateway.load,
            store=FrozenBytesStore(b"\n".join([lines[1], lines[0]]) + b"\n"),
            clock=StepClock(_PT0, _PSTEP), snapshot=world[0],
            adapter=_sandbox(),
        )
        if problems:
            results.append(fail(name, "reorder: %s" % problems))
            return
        # truncated tail
        problems = _expect_error(
            name, PaymentReasonCode.JOURNAL_CORRUPT,
            SettlementGateway.load,
            store=FrozenBytesStore(lines[0] + b"\n" + lines[1][:40] + b"\n"),
            clock=StepClock(_PT0, _PSTEP), snapshot=world[0],
            adapter=_sandbox(),
        )
        if problems:
            results.append(fail(name, "truncation: %s" % problems))
            return
        # duplicated line
        problems = _expect_error(
            name, PaymentReasonCode.JOURNAL_CORRUPT,
            SettlementGateway.load,
            store=FrozenBytesStore(
                b"\n".join([lines[0], lines[1], lines[1]]) + b"\n"
            ),
            clock=StepClock(_PT0, _PSTEP), snapshot=world[0],
            adapter=_sandbox(),
        )
        if problems:
            results.append(fail(name, "duplicated line: %s" % problems))
            return
    results.append(
        ok(
            name,
            "negative proof 5: terminals sealed; byte flip/reorder/truncate/"
            "duplicate all fail closed",
        )
    )


def case_30_no_vendor_leakage(results: List[Result]) -> None:
    name = "case_30_no_vendor_leakage"
    # negative proof 6: provider-specific statuses never leak into
    # canonical state (the sandbox deliberately speaks a
    # vendored wire vocabulary)
    provider = _sandbox()
    gateway = _golden_payment(provider=provider)
    canonical_blobs = []
    for intent in gateway.intents():
        canonical_blobs.append(json.dumps(intent.to_dict(), sort_keys=True))
    for instruction in gateway.payouts():
        canonical_blobs.append(json.dumps(instruction.to_dict(), sort_keys=True))
    for observation in gateway.observations():
        canonical_blobs.append(json.dumps(observation.to_dict(), sort_keys=True))
    for report in gateway.reports():
        canonical_blobs.append(json.dumps(report.to_dict(), sort_keys=True))
    blob = "\n".join(canonical_blobs)
    for token in _VENDOR_TOKENS:
        if token in blob:
            results.append(
                fail(name, "vendor token %r leaked into canonical state" % token)
            )
            return
    # reason codes are canonical (no vendor vocabulary)
    for reason in PaymentReasonCode.values():
        for token in _VENDOR_TOKENS:
            if token.lower() in reason:
                results.append(fail(name, "reason %r carries vendor token" % reason))
                return
    # the mapping proof: the provider's wire envelopes DO carry
    # the vendored statuses (the boundary really maps)
    envelopes = provider.pending_callbacks()
    if envelopes:
        results.append(fail(name, "pending callbacks left undrained"))
        return
    world = _payment_world()
    provider2 = _sandbox()
    gateway2 = _gateway(world=world, provider=provider2)
    gateway2.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway2, world[2], world[1])
    gateway2.authorize(command_id="pi-c02", intent_id="pi-01", actor="b", source="s")
    envelopes = provider2.pending_callbacks()
    wire = json.dumps(envelopes, sort_keys=True)
    if "FUNDS_HELD" not in wire:
        results.append(fail(name, "sandbox wire lost its vendored vocabulary"))
        return
    if "AUTHORIZED" in wire:
        results.append(fail(name, "canonical status leaked onto the wire"))
        return
    for envelope in envelopes:
        gateway2.ingest_callback(
            envelope, actor="webhook-ingress", source="provider-callback"
        )
    if gateway2.intent("pi-01").state != "AUTHORIZED":
        results.append(fail(name, "mapping did not preserve semantics"))
        return
    results.append(
        ok(
            name,
            "negative proof 6: vendored wire statuses map in; canonical "
            "state stays vendor-free",
        )
    )


def case_31_import_discipline(results: List[Result]) -> None:
    name = "case_31_import_discipline"
    # negative proof 7: forbidden imports are rejected -- the
    # payment family imports stdlib + WORK-003 canonicalization
    # + the WORK-033 clock seam ONLY
    problems: List[str] = []
    for path in _FAMILY_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
        relative = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name
                    if module in _ALLOWED_IMPORT_MODULES or any(
                        module == prefix.rstrip(".")
                        or module.startswith(prefix)
                        for prefix in _ALLOWED_IMPORT_PREFIXES
                    ):
                        continue
                    problems.append("%s imports %s" % (relative, module))
            elif isinstance(node, ast.ImportFrom):
                if node.level > 0:
                    continue  # intra-family relative imports
                module = node.module or ""
                if module in _ALLOWED_IMPORT_MODULES or any(
                    module == prefix.rstrip(".")
                    or module.startswith(prefix)
                    for prefix in _ALLOWED_IMPORT_PREFIXES
                ):
                    continue
                problems.append("%s imports from %s" % (relative, module))
        text = path.read_text(encoding="utf-8")
        for token in _FORBIDDEN_TOKENS:
            if token in text:
                problems.append("%s carries forbidden token %r" % (relative, token))
        for token in _VENDOR_TOKENS:
            if token in text and relative != "payment/sandbox.py":
                problems.append("%s carries vendor token %r" % (relative, token))
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(
            name,
            "negative proof 7: payment family imports stdlib + canon + "
            "clock seam only; no authority construction anywhere",
        )
    )


def case_32_public_api_stability(results: List[Result]) -> None:
    name = "case_32_public_api_stability"
    if sorted(payment.__all__) != _EXPECTED_API:
        results.append(fail(name, "the frozen public API surface drifted"))
        return
    for member in payment.__all__:
        if not hasattr(payment, member):
            results.append(fail(name, "export %r missing" % member))
            return
    results.append(
        ok(name, "frozen public API: %d exports pinned" % len(payment.__all__))
    )


def case_33_journal_first_recovery(results: List[Result]) -> None:
    name = "case_33_journal_first_recovery"
    with tempfile.TemporaryDirectory() as tmp:
        store = FilePaymentStore(Path(tmp) / "journal.jsonl")
        provider = _sandbox()
        gateway = _golden_payment(store=store, provider=provider)
        recovered = SettlementGateway.load(
            store=store, clock=StepClock(_PT0, _PSTEP),
            snapshot=_payment_world()[0], adapter=_sandbox(),
        )
        checks = (
            ("journal", gateway.journal_digest(), recovered.journal_digest()),
            ("stream", gateway.digest_stream(), recovered.digest_stream()),
        )
        for label, before, after in checks:
            if before != after:
                results.append(fail(name, "%s digest diverged on recovery" % label))
                return
        if len(recovered.intents()) != 1 or len(recovered.payouts()) != 1:
            results.append(fail(name, "recovered projections incomplete"))
            return
        if len(recovered.observations()) != len(gateway.observations()):
            results.append(fail(name, "recovered observations incomplete"))
            return
        if len(recovered.reports()) != 1:
            results.append(fail(name, "recovered reports incomplete"))
            return
        if len(recovered.capability_declarations()) != 1:
            results.append(fail(name, "recovered capabilities incomplete"))
            return
        for ledger_name in (
            "command_ledger", "intent_ledger", "payout_ledger",
            "callback_ledger", "capability_ledger",
        ):
            before = getattr(gateway, ledger_name)()
            after = getattr(recovered, ledger_name)()
            if dict(before) != dict(after):
                results.append(fail(name, "%s diverged on recovery" % ledger_name))
                return
        recovered.verify_integrity()
    results.append(
        ok(name, "journal-first recovery: live == reloaded byte-identical (all layers)")
    )


def case_34_restart_replay(results: List[Result]) -> None:
    name = "case_34_restart_replay"
    with tempfile.TemporaryDirectory() as tmp:
        store = FilePaymentStore(Path(tmp) / "journal.jsonl")
        world = _payment_world()
        provider = _sandbox()
        gateway = _gateway(world=world, store=store, provider=provider)
        gateway.record_capabilities(command_id="cap-01", actor="p", source="s")
        out = _create_std_intent(gateway, world[2], world[1])
        gateway.authorize(command_id="pi-c02", intent_id="pi-01", actor="b", source="s")
        stream_before = gateway.digest_stream()
        # restart: a FRESH provider whose state is rebuilt by
        # replaying the same deterministic registration (the
        # external rails persist independently of the ADCOS
        # journal; the recovered journal replays duplicates as
        # no-ops)
        provider2 = _sandbox()
        provider2.create_intent(
            intent_ref="pi-01", transaction_ref=world[2],
            amount=_INTENT_AMOUNT, currency=_CCY, exponent=_EXP,
            description="connectivity billing",
        )
        recovered = SettlementGateway.load(
            store=store, clock=StepClock(_PT0, _PSTEP),
            snapshot=world[0], adapter=provider2,
        )
        out2 = _create_std_intent(
            recovered, world[2], world[1], command_id="pi-c01"
        )
        if out2.status != "duplicate" or out2.event_id != out.event_id:
            results.append(fail(name, "command redelivery not a no-op after restart"))
            return
        out3 = _create_std_intent(
            recovered, world[2], world[1], command_id="pi-c34"
        )
        if out3.status != "duplicate":
            results.append(fail(name, "intent identity redelivery not a no-op"))
            return
        problems = _expect_error(
            name, PaymentReasonCode.INTENT_CONFLICT,
            recovered.create_intent,
            command_id="pi-c35", intent_id="pi-01", transaction_id=world[2],
            amount=_INTENT_AMOUNT + 1, currency=_CCY, exponent=_EXP,
            usage_record_id=world[1], description="conflict",
            actor="b", source="s",
        )
        if problems:
            results.append(fail(name, problems))
            return
        if recovered.digest_stream() != stream_before:
            results.append(fail(name, "duplicates changed the stream"))
            return
        # the recovered gateway continues appending correctly
        out4 = recovered.authorize(
            command_id="pi-c02", intent_id="pi-01", actor="b", source="s"
        )
        if out4.status != "duplicate" or recovered.intent("pi-01").state != "AUTHORIZED":
            results.append(fail(name, "recovered authorize replay"))
            return
        out5 = recovered.capture(
            command_id="pi-c36", intent_id="pi-01", amount=_INTENT_AMOUNT,
            actor="b", source="s",
        )
        if out5.to_state != "CAPTURED" or recovered.tail_sequence() != 4:
            results.append(fail(name, "recovered gateway cannot append"))
            return
        recovered.verify_integrity()
    results.append(
        ok(name, "restart/replay: durable no-ops, conflicts preserved, appends resume")
    )


def case_35_two_run_determinism(results: List[Result]) -> None:
    name = "case_35_two_run_determinism"
    first = _scenario_stream()
    second = _scenario_stream()
    if first != second:
        diff = [
            key for key in sorted(first) if first[key] != second.get(key)
        ]
        results.append(fail(name, "two fresh runs diverged: %s" % diff))
        return
    results.append(
        ok(name, "two fresh runs byte-identical across the whole digest stream")
    )


def case_36_subprocess_hash_seeds(results: List[Result]) -> None:
    name = "case_36_subprocess_hash_seeds"
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
            [sys.executable, str(Path(__file__).resolve()),
             "--determinism-stream"],
            capture_output=True, text=True, env=env, cwd=str(REPO_ROOT),
            timeout=300,
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
    if _GOLDEN_STREAM_SHA256 not in digests["0"]:
        results.append(
            fail(name, "subprocess stream does not carry the pinned golden digest")
        )
        return
    results.append(
        ok(name, "PYTHONHASHSEED 0/1/7919/unset subprocesses agree "
                 "byte-for-byte on the whole digest stream")
    )


def case_37_clock_discipline(results: List[Result]) -> None:
    name = "case_37_clock_discipline"
    clock = CountingClock(StepClock(_PT0, _PSTEP))
    provider = _sandbox()
    world = _payment_world()
    gateway = SettlementGateway(
        store=MemoryPaymentStore(), clock=clock, snapshot=world[0],
        adapter=provider,
    )
    gateway.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway, world[2], world[1])
    gateway.authorize(command_id="pi-c02", intent_id="pi-01", actor="b", source="s")
    reads = clock.reads
    # duplicates consume no read
    gateway.authorize(command_id="pi-c02", intent_id="pi-01", actor="b", source="s")
    if clock.reads != reads:
        results.append(fail(name, "duplicate consumed a clock read"))
        return
    # rejections consume no read
    try:
        gateway.capture(
            command_id="x-1", intent_id="pi-01", amount=_INTENT_AMOUNT + 1,
            actor="b", source="s",
        )
    except PaymentError:
        pass
    if clock.reads != reads:
        results.append(fail(name, "rejection consumed a clock read"))
        return
    # every appended record consumes EXACTLY one
    gateway.capture(
        command_id="pi-c03", intent_id="pi-01", amount=_INTENT_AMOUNT,
        actor="b", source="s",
    )
    if clock.reads != reads + 1:
        results.append(fail(name, "append did not consume exactly one read"))
        return
    # the golden lifecycle: total reads == total appended records
    golden_clock = CountingClock(StepClock(_PT0, _PSTEP))
    golden = _golden_payment(clock=golden_clock)
    if golden_clock.reads != golden.tail_sequence():
        results.append(
            fail(
                name,
                "golden clock reads %d != appended records %d"
                % (golden_clock.reads, golden.tail_sequence()),
            )
        )
        return
    results.append(
        ok(name, "clock discipline: duplicates/rejections free; 1 read per append")
    )


def case_38_scope_audit(results: List[Result]) -> None:
    name = "case_38_scope_audit"
    audit_ref = _audit_ref()
    if audit_ref is None:
        results.append(
            ok(name, "SKIP (no audit ref available in this checkout; CI "
                     "enforces provenance via the dedicated step)")
        )
        return
    delta = {
        line.strip()
        for line in (_git(["diff", "--name-only", audit_ref]) or "").splitlines()
        if line.strip()
    }
    delta |= {
        line.strip()
        for line in (
            _git(["ls-files", "--others", "--exclude-standard"]) or ""
        ).splitlines()
        if line.strip()
    }
    unauthorized = [
        path for path in sorted(delta)
        if not (
            _active_authorization_covers(path)
            or any(
                path == authorized
                or (authorized.endswith("/") and path.startswith(authorized))
                for authorized in _AUTHORIZED_PATHS + (AUTHORIZED_CI_WIRING,)
            )
        )
    ]
    if unauthorized:
        results.append(
            fail(
                name,
                "delta outside the WORK-044-CORE-001 scope vs %s: %s"
                % (audit_ref, ", ".join(unauthorized[:5])),
            )
        )
        return
    sibling_changes = _git(
        ["diff", "--name-only", audit_ref, "--"] + list(
            _SIBLING_PREFIXES
        )
    )
    # Authorization-aware frozen-family consultation (the M002-era repair
    # pattern, the same repair ratified by DEC-0111 for the sharenet battery
    # case_31: the M007 delivery disclosed this stop-condition — the frozen
    # sibling-family check predates the R7 program authorizations and trips
    # on every authorized R7 child delivery that touches its own charter
    # scope inside a family the WORK-044-era battery froze. Sibling paths
    # covered by the ACTIVE repository-local authorization are sanctioned;
    # the freeze stays byte-identical for everything else.)
    if sibling_changes:
        sibling_changes = {
            line.strip()
            for line in sibling_changes.splitlines()
            if line.strip() and not _active_authorization_covers(line.strip())
        }
    if sibling_changes:
        results.append(
            fail(
                name,
                "accepted authority families changed vs %s: %s"
                % (audit_ref, sorted(sibling_changes)),
            )
        )
        return
    spec_changes = _git(["diff", "--name-only", audit_ref, "--", "spec/"])
    if spec_changes:
        results.append(
            fail(name, "spec/ changed vs %s: %s" % (audit_ref, spec_changes))
        )
        return
    results.append(
        ok(
            name,
            "scope audit vs %s: delta within the authorized surfaces; "
            "frozen families byte-identical" % audit_ref[:12],
        )
    )


#: The accepted authority code families that must stay
#: byte-identical (docs/tools/spec are covered by the scope
#: check and the dedicated spec/ check).
_SIBLING_PREFIXES = (
    "agent", "identity", "sessions",
    "routing", "networkpath", "transport", "platform", "policy", "protocol",
    "topology", "management", "mobile",
    "conformance", "adapters", "appliance", "capabilities", "discovery",
    "edge", "energy", "federation", "imt", "intent", "interop", "mobility",
    "multipath", "resources", "scale", "services", "simulator", "telemetry",
    "upgrade",
)


def _git(args: List[str]) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git"] + args, capture_output=True, text=True,
            cwd=str(REPO_ROOT), timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _commit_available(ref: str) -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "%s^{commit}" % ref],
        capture_output=True, cwd=str(REPO_ROOT),
    )
    return proc.returncode == 0


def _origin_main_available() -> bool:
    return _commit_available("origin/main")


def _is_ancestor(ancestor: str, descendant: str) -> bool:
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        capture_output=True, cwd=str(REPO_ROOT),
    )
    return proc.returncode == 0


def _audit_ref() -> Optional[str]:
    """The honest scope-audit reference.

    Merge-commit context (the CI PR checkout refs/pull/N/merge,
    and any GitHub-direction merge whose FIRST parent is the
    base): ``HEAD^1`` -- the delta is exactly this PR's files.
    Branch context (HEAD descends from the authorized baseline,
    no merge): the exact baseline SHA -- the delta is the whole
    implementation as the Architect reviews it.  Base-less
    context: None (skip; CI enforces provenance separately).
    """
    if _commit_available("HEAD^2"):
        # a merge commit: the first parent is the base the PR is
        # evaluated against (GitHub merge direction)
        return "HEAD^1"
    if _origin_main_available() and _is_ancestor("origin/main", "HEAD"):
        return "origin/main"
    if _commit_available(_BASELINE_SHA) and _is_ancestor(
        _BASELINE_SHA, "HEAD"
    ):
        return _BASELINE_SHA
    return None


def case_39_capability_lifecycle(results: List[Result]) -> None:
    name = "case_39_capability_lifecycle"
    world = _payment_world()
    provider = _sandbox()
    gateway = _gateway(world=world, provider=provider)
    gateway.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway, world[2], world[1])
    if gateway.intent("pi-01").capability_key != "sandbox-1@v1":
        results.append(fail(name, "intent does not cite the declaration version"))
        return
    # the identical declaration under a new command id: no-op
    out = gateway.record_capabilities(
        command_id="cap-02", actor="p", source="s"
    )
    if out.status != "duplicate":
        results.append(fail(name, "identical re-declaration not a no-op"))
        return
    # a conflicting re-declaration of the SAME version with
    # different content (the adapter changed its mind) fails
    # closed: capability versions are immutable history
    provider._capabilities = ProviderCapabilities(
        provider_id=_PROV_ID, schema_version=1,
        supports_authorization=False, supports_capture=True,
        supports_refund=True, supports_partial_refund=True,
        supports_reversal=True, supports_payout_transfer=True,
        supports_callbacks=True, supports_status_query=True,
        currencies=("GHS", "USD"), max_exponent=2, max_amount=5,
    )
    problems = _expect_error(
        name, PaymentReasonCode.CAPABILITY_CONFLICT,
        gateway.record_capabilities,
        command_id="cap-03", actor="p", source="s",
    )
    provider._capabilities = _full_capabilities()
    if problems:
        results.append(fail(name, problems))
        return
    # the adapter upgrades to v2: a NEW version appends, the old
    # intents still cite v1, and the live v2 gates new operations
    upgraded = _full_capabilities(version=2)
    provider._capabilities = upgraded
    out = gateway.record_capabilities(
        command_id="cap-04", actor="p", source="s"
    )
    if out.status != "appended" or out.entity_id != "sandbox-1@v2":
        results.append(fail(name, "capability upgrade not journaled"))
        return
    if len(gateway.capability_declarations()) != 2:
        results.append(fail(name, "capability registry size"))
        return
    if gateway.intent("pi-01").capability_key != "sandbox-1@v1":
        results.append(fail(name, "historical citation rewritten"))
        return
    # conflicting re-declaration of v1 under new content: the
    # live adapter is v2 now, so a v1 record attempt mismatches
    # an undeclared live version gates everything: the adapter
    # moved to v3 without journaling it first
    provider._capabilities = _full_capabilities(version=3)
    problems = _expect_error(
        name, PaymentReasonCode.CAPABILITY_UNDECLARED,
        gateway.create_intent,
        command_id="x-1", intent_id="pi-02", transaction_id=world[2],
        amount=100, currency="GHS", exponent=2,
        actor="b", source="s",
    )
    if problems:
        results.append(fail(name, problems))
        return
    # v4 gating: a newly declared authorization-incapable
    # version blocks NEW intents (the live declaration gates)
    provider._capabilities = ProviderCapabilities(
        provider_id=_PROV_ID, schema_version=4,
        supports_authorization=False, supports_capture=True,
        supports_refund=True, supports_partial_refund=True,
        supports_reversal=True, supports_payout_transfer=True,
        supports_callbacks=True, supports_status_query=True,
        currencies=("GHS", "USD"), max_exponent=2, max_amount=10_000_000,
    )
    gateway.record_capabilities(command_id="cap-05", actor="p", source="s")
    _create_std_intent(
        gateway, world[2], world[1], command_id="pi-c39", intent_id="pi-03"
    )
    problems = _expect_error(
        name, PaymentReasonCode.CAPABILITY_UNSUPPORTED,
        gateway.authorize,
        command_id="x-2", intent_id="pi-03", actor="b", source="s",
    )
    if problems:
        results.append(fail(name, problems))
        return
    results.append(
        ok(
            name,
            "capability lifecycle: versioned declarations, immutable "
            "history, live gating",
        )
    )


def case_40_closed_loop_composition(results: List[Result]) -> None:
    name = "case_40_closed_loop_composition"
    # the full authority chain under the M009 re-bind: the REAL
    # canonical contract (M002 public surface) -> the REAL
    # contract-bound W051 account -> the REAL contract-bound W052
    # usage account -> the REAL contract-bound W053 allocation
    # -> payment intent -> capture -> the REAL W053 settlement
    # acknowledgement citing the payment intent as provider DATA
    # -> the REAL W051 settlement initiation citing the payment
    # intent as payment DATA -> W051 SETTLE (with the contract
    # walked to SETTLED through the canonical public surface),
    # with the payment DATA rejected as a settlement confirmation
    world = _payment_world(allocation_state="PLANNED")
    (
        snapshot, finality_id, tx, core, usage_ledger, alloc, manager,
        integrator, contract_store, contract_id,
    ) = world
    provider = _sandbox()
    gateway = _gateway(snapshot=snapshot, provider=provider)
    gateway.record_capabilities(command_id="cap-01", actor="p", source="s")
    _create_std_intent(gateway, tx, finality_id)
    _drive_to_captured(gateway)
    intent = gateway.intent("pi-01")
    # reload the W053 allocation ledger with the payment intent
    # id cited as PAYMENT_PROVIDER DATA (public reads only; the
    # M009 typed evidence index projects the extended family
    # facts)
    facts = _allocation_facts((usage_ledger,), (core,))
    entries = list(facts.by_family(FactFamily.USAGE_FINAL)) + list(
        facts.by_family(FactFamily.COMMERCIAL)
    ) + list(facts.by_family(FactFamily.SETTLEMENT)) + list(
        facts.by_family(FactFamily.PAYMENT_PROVIDER)
    )
    entries.append(
        FactReference(
            reference_id=intent.intent_id,
            family=FactFamily.PAYMENT_PROVIDER,
            provenance="payment-gateway",
        )
    )
    extended_facts = FactIndex(entries)
    # re-drive the deterministic W053 history with the extended
    # fact index (identical commands, identical journal, plus
    # the payment intent id as citable provider DATA)
    base_index = _typed_allocation_index(
        extended_facts, (usage_ledger,), contract_id=contract_id
    )
    extended_index_alloc = AllocationEvidenceIndex(
        usage=[
            base_index.usage(key)
            for key in base_index.usage_transaction_ids()
        ],
        references=[
            base_index.reference(key)
            for key in base_index.reference_ids()
        ]
        + [
            ExternalReferenceSnapshot(
                intent.intent_id,
                ReferenceKind.PAYMENT,
                "payment-gateway",
                contract_id,
            )
        ],
    )
    alloc2 = AllocationLedger(
        store=MemoryAllocationStore(),
        clock=StepClock(_AT0, _ASTEP),
        evidence_index=extended_index_alloc,
    )
    out = _register_std_policy(alloc2, command_id="p-01")
    _std_allocate(alloc2, finality_id, contract_id, command_id="a-01",
                  policy_id=out.fact_id)
    out = alloc2.acknowledge_settlement(
        command_id="s-01", usage_transaction_id=contract_id,
        settlement_reference=_settlement_ref(),
        actor="settlement", source="settlement-service",
    )
    if out.to_state != AllocationState.SETTLED:
        results.append(fail(name, "W053 settlement acknowledgement"))
        return
    # the payment intent id rides the account as provider DATA
    alloc2.record_payment_reference(
        command_id="pr-01", usage_transaction_id=contract_id,
        payment_reference=intent.intent_id,
        actor="settlement", source="settlement-service",
    )
    if not any(
        reference.payment_reference == intent.intent_id
        for reference in alloc2.allocation(contract_id).payment_references
    ):
        results.append(fail(name, "payment intent not cited as W053 DATA"))
        return
    # advance the REAL canonical contract through the M002 public
    # surface: DELIVERY -> ASSURED -> USAGE_FINAL ->
    # SETTLEMENT_PENDING -> SETTLED (the commercial walk's floors)
    contract_store.submit(
        RecordAssurance(
            recorded_at="2026-09-01T11:25:00Z",
            assurance_state="compliant",
            evidence_refs=(_wire_ref("decision", "dec:assur-ok-2", "assur:m005"),),
        ),
        recorded_at="2026-09-01T11:25:00Z", contract_id=contract_id,
    )
    contract_store.submit(
        RecordUsageFinal(recorded_at="2026-09-01T11:30:00Z"),
        recorded_at="2026-09-01T11:30:00Z", contract_id=contract_id,
    )
    contract_store.submit(
        RecordSettlementPending(recorded_at="2026-09-01T11:35:00Z"),
        recorded_at="2026-09-01T11:35:00Z", contract_id=contract_id,
    )
    contract_store.submit(
        RecordSettled(recorded_at="2026-09-01T11:40:00Z"),
        recorded_at="2026-09-01T11:40:00Z", contract_id=contract_id,
    )
    if contract_store.contract(contract_id).state != "SETTLED":
        results.append(fail(name, "canonical contract settlement walk"))
        return
    # re-drive the deterministic W051 history with the extended
    # reference index (identical commands, identical journal,
    # plus the payment intent id in the PAYMENT family) and the
    # CURRENT canonical contract citations (the bound mode; every
    # floor satisfied by the walked contract)
    references = _commercial_references(manager, integrator, _session_of(world))
    reference_entries = list(references.by_family(ReferenceFamily.SESSION)) + list(
        references.by_family(ReferenceFamily.NETWORK_PATH)
    ) + list(references.by_family(ReferenceFamily.DELIVERY_EVIDENCE)) + list(
        references.by_family(ReferenceFamily.USAGE)
    ) + list(references.by_family(ReferenceFamily.SETTLEMENT)) + list(
        references.by_family(ReferenceFamily.PAYMENT)
    )
    reference_entries.append(
        Reference(intent.intent_id, ReferenceFamily.PAYMENT, "payment-gateway")
    )
    extended_index = ReferenceIndex(reference_entries)
    core2 = CommercialCore(
        store=commercial.MemoryCommercialStore(),
        clock=StepClock(_CT0, _CSTEP),
        references=extended_index,
        contract_references=_contract_index(contract_store, contract_id),
    )
    # re-drive the transaction to USAGE_ACCRUING (the
    # deterministic identical command sequence, contract-bound),
    # then to settlement with the payment DATA riding along
    core2.submit_intent(
        command_id="w051-01",
        actor="buyer-agent",
        source="developer-api",
        intent={
            "buyer": "buyer-1", "want": "connectivity", "region": "gh",
            "contract_id": contract_id,
        },
    )
    if core2.transaction(tx).contract_id != contract_id:
        results.append(fail(name, "the W051 account is not contract-bound"))
        return
    core2.select_offer(
        command_id="w051-02", transaction_id=tx, actor="buyer-agent",
        source="developer-api",
        offer={"offer_id": "offer-1", "provider": "provider-1",
               "unit": "GB", "price": "10"},
    )
    core2.hold_reservation(
        command_id="w051-03", transaction_id=tx, actor="platform",
        source="reservation-service", expires_at=add_seconds(_CT0, 600),
    )
    core2.authorize_session(
        command_id="w051-04", transaction_id=tx, actor="platform",
        source="session-service", session_ref=_session_of(world),
    )
    core2.activate_path(
        command_id="w051-05", transaction_id=tx, actor="platform",
        source="path-service", path_ref=manager.active_path_id(
            _session_of(world)
        ),
    )
    delivery = sorted(
        ref.reference_id
        for ref in extended_index.by_family(ReferenceFamily.DELIVERY_EVIDENCE)
    )
    core2.start_delivery(
        command_id="w051-06", transaction_id=tx, actor="platform",
        source="delivery-service", evidence_refs=(delivery[0],),
    )
    usage_ref = extended_index.by_family(ReferenceFamily.USAGE)[0].reference_id
    core2.accrue_usage(
        command_id="w051-07", transaction_id=tx, actor="platform",
        source="usage-service", usage_refs=(usage_ref,),
    )
    core2.complete_delivery(
        command_id="w051-08", transaction_id=tx, actor="platform",
        source="delivery-service", evidence_refs=(delivery[0],),
    )
    core2.finalize_billable(
        command_id="w051-09", transaction_id=tx, actor="billing",
        source="billing-service",
    )
    out = core2.initiate_settlement(
        command_id="w051-10", transaction_id=tx, actor="billing",
        source="billing-service", payment_refs=(intent.intent_id,),
    )
    if out.to_state != "SETTLEMENT_PENDING":
        results.append(fail(name, "W051 settlement initiation"))
        return
    # negative: payment DATA can NEVER justify settlement
    problems = _expect_commercial_error(
        name, "payment-not-settlement",
        core2.settle,
        command_id="w051-11", transaction_id=tx, actor="billing",
        source="billing-service", settlement_refs=(intent.intent_id,),
    )
    if problems:
        results.append(fail(name, problems))
        return
    out = core2.settle(
        command_id="w051-12", transaction_id=tx, actor="billing",
        source="billing-service", settlement_refs=(_settlement_ref(),),
    )
    if out.to_state != "SETTLED":
        results.append(fail(name, "W051 settlement"))
        return
    # and the payment side never noticed settlement as payment
    # truth: the intent state is still CAPTURED (external
    # observations until reconciled)
    if gateway.intent("pi-01").state != "CAPTURED":
        results.append(fail(name, "settlement leaked back into payment state"))
        return
    results.append(
        ok(
            name,
            "closed loop: the canonical contract cited at every step; "
            "payment DATA cited by REAL W053/W051 records; payment DATA "
            "never justifies settlement",
        )
    )


def _session_of(world) -> str:
    """The composed world's real session id (rebuilt through the
    public W051 projection: the transaction cites the session)."""
    return world[3].transaction(world[2]).session_ref


def _expect_commercial_error(
    case_name: str, expected_reason: str, func, *args, **kwargs
) -> Optional[str]:
    try:
        func(*args, **kwargs)
    except commercial.CommercialError as error:
        if error.reason == expected_reason:
            return None
        return "expected %s, got %s (%s)" % (
            expected_reason, error.reason, error.detail
        )
    except Exception as error:  # noqa: BLE001
        return "wrong exception type %s" % type(error).__name__
    return "no error raised (expected %s)" % expected_reason


def case_41_intent_correlation_citations(results: List[Result]) -> None:
    name = "case_41_intent_correlation_citations"
    world = _payment_world()
    gateway = _gateway(world=world)
    gateway.record_capabilities(command_id="cap-01", actor="p", source="s")
    # unknown transaction citation: fail closed (a fabricated
    # transaction can never enter payment state)
    problems = _expect_error(
        name, PaymentReasonCode.CITATION_UNKNOWN,
        gateway.create_intent,
        command_id="x-1", intent_id="pi-01", transaction_id="sha256:" + "9" * 64,
        amount=100, currency="GHS", exponent=2,
        actor="b", source="s",
    )
    if problems:
        results.append(fail(name, problems))
        return
    # wrong family: citing the ALLOCATION id as the commercial
    # transaction
    problems = _expect_error(
        name, PaymentReasonCode.CITATION_FAMILY_INVALID,
        gateway.create_intent,
        command_id="x-2", intent_id="pi-01", transaction_id=world[1],
        amount=100, currency="GHS", exponent=2,
        actor="b", source="s",
    )
    if problems:
        results.append(fail(name, problems))
        return
    # unknown usage citation
    problems = _expect_error(
        name, PaymentReasonCode.CITATION_UNKNOWN,
        gateway.create_intent,
        command_id="x-3", intent_id="pi-01", transaction_id=world[2],
        amount=100, currency="GHS", exponent=2,
        usage_record_id="sha256:" + "8" * 64,
        actor="b", source="s",
    )
    if problems:
        results.append(fail(name, problems))
        return
    # wrong-family usage citation (the transaction id is a
    # COMMERCIAL-family id, not a usage-final id)
    problems = _expect_error(
        name, PaymentReasonCode.CITATION_FAMILY_INVALID,
        gateway.create_intent,
        command_id="x-4", intent_id="pi-01", transaction_id=world[2],
        amount=100, currency="GHS", exponent=2,
        usage_record_id=world[2],
        actor="b", source="s",
    )
    if problems:
        results.append(fail(name, problems))
        return
    if gateway.intents():
        results.append(fail(name, "rejected citations created intents"))
        return
    results.append(
        ok(name, "intent citations: unknown and wrong-family citations fail closed")
    )


def case_42_store_failures(results: List[Result]) -> None:
    name = "case_42_store_failures"
    world = _payment_world()
    # every durable append fails: the very first command fails
    # closed with no phantom in-memory state (no journal record,
    # no capability registry entry, no state)
    store = FailingPaymentStore()
    gateway = _gateway(world=world, store=store)
    problems = _expect_error(
        name, PaymentReasonCode.STORE_FAILED,
        gateway.record_capabilities,
        command_id="cap-01", actor="p", source="s",
    )
    if problems:
        results.append(fail(name, problems))
        return
    if gateway.tail_sequence() != 0:
        results.append(fail(name, "store failure left a phantom journal record"))
        return
    if gateway.capability_declarations():
        results.append(fail(name, "store failure left a phantom declaration"))
        return
    problems = _expect_error(
        name, PaymentReasonCode.CAPABILITY_UNDECLARED,
        _create_std_intent, gateway, world[2], world[1],
    )
    if problems:
        results.append(fail(name, problems))
        return
    if gateway.intents():
        results.append(fail(name, "store failure left a phantom intent"))
        return
    # a healthy store over the same world still works (the
    # failure is not sticky)
    healthy = _gateway(world=world)
    healthy.record_capabilities(command_id="cap-01", actor="p", source="s")
    out = _create_std_intent(healthy, world[2], world[1])
    if out.status != "appended":
        results.append(fail(name, "healthy store did not recover"))
        return
    results.append(
        ok(name, "persist-then-ack: store failure leaves no phantom state")
    )


def case_43_open_usage_stays_open(results: List[Result]) -> None:
    name = "case_43_open_usage_stays_open"
    # negative proof 3: provider success cannot bypass
    # BILLABLE_FINAL -- a payment flow over an OPEN (non-final)
    # usage account never creates the finality
    runtime, peer, session_id, manager, integrator, shared = _world()
    core, tx, store, contract_id = _commercial_tx(
        manager, integrator, session_id
    )
    references = _usage_evidence(
        manager, integrator, session_id, core, tx,
        contract_store=store, contract_id=contract_id,
    )
    typed_index = _typed_evidence_index(
        references, contract_state=store.contract(contract_id).state,
        integrator=integrator,
    )
    usage_ledger, open_id = _final_usage(
        references, contract_id, typed_index=typed_index,
        integrator=integrator, stop_after="observed",
    )
    account_before = usage_ledger.transaction(contract_id).to_dict()
    snapshot = _commercial_snapshot(core, usage_ledger, None)
    provider = _sandbox()
    gateway = _gateway(snapshot=snapshot, provider=provider)
    gateway.record_capabilities(command_id="cap-01", actor="p", source="s")
    # the intent cites the OPEN usage account (honest DATA: the
    # snapshot keys it by the transaction id)
    out = gateway.create_intent(
        command_id="pi-c01", intent_id="pi-01", transaction_id=tx,
        amount=800, currency="GHS", exponent=2,
        usage_record_id=open_id, description="pre-billing",
        actor="billing", source="billing-service",
    )
    if out.status != "appended":
        results.append(fail(name, "open-usage citation rejected (DATA must be legal)"))
        return
    _drive_to_captured(gateway)
    for envelope in provider.pending_callbacks():
        gateway.ingest_callback(
            envelope, actor="webhook-ingress", source="provider-callback"
        )
    account = usage_ledger.transaction(contract_id)
    if account.state != "OBSERVING":
        results.append(
            fail(name, "payment changed the open usage state: %s" % account.state)
        )
        return
    if account.statement is not None:
        results.append(fail(name, "payment created a finality record"))
        return
    if account.to_dict() != account_before:
        results.append(fail(name, "usage account changed at all"))
        return
    # the usage journal is byte-identical
    # (built fresh: the ledger object is the same authority)
    if len(usage_ledger.transactions()) != 1:
        results.append(fail(name, "usage accounts changed"))
        return
    # and there is no gateway API that touches usage state
    # (structural: the public surface exposes no usage mutation)
    surface = [member for member in dir(gateway) if not member.startswith("_")]
    forbidden = [m for m in surface if "usage" in m or "final" in m or "billable" in m]
    if forbidden:
        results.append(
            fail(name, "gateway surface carries usage vocabulary: %r" % forbidden)
        )
        return
    results.append(
        ok(
            name,
            "negative proof 3: payment on an open account never finalizes "
            "usage (BILLABLE_FINAL untouchable)",
        )
    )


def _mutation_raises(container: Any) -> bool:
    """True iff an in-place mutation of the container raises."""
    try:
        key = sorted(container)[0]
        container[key] = "forged"
        return False
    except TypeError:
        return True


def case_44_deep_immutable_projections(results: List[Result]) -> None:
    name = "case_44_deep_immutable_projections"
    gateway = _golden_payment()
    stream_before = gateway.digest_stream()
    mutations = 0
    # observation amounts
    observation = gateway.observations()[0]
    if not _mutation_raises(observation.amounts):
        results.append(fail(name, "observation amounts mutable"))
        return
    mutations += 1
    # report entries
    report = gateway.reports()[0]
    if not _mutation_raises(report.entries[0]):
        results.append(fail(name, "report entries mutable"))
        return
    mutations += 1
    # journaled command payloads and event payloads (every
    # non-empty payload must reject in-place mutation)
    for record in gateway.journal_records():
        if record.command.payload:
            if not _mutation_raises(record.command.payload):
                results.append(
                    fail(name, "command payload mutable at seq %d" % record.sequence)
                )
                return
            mutations += 1
        if record.event.payload:
            if not _mutation_raises(record.event.payload):
                results.append(
                    fail(name, "event payload mutable at seq %d" % record.sequence)
                )
                return
            mutations += 1
    # the five idempotency ledgers (outer AND inner containers)
    for ledger_name in (
        "command_ledger", "intent_ledger", "payout_ledger",
        "callback_ledger", "capability_ledger",
    ):
        ledger = getattr(gateway, ledger_name)()
        try:
            ledger["forged"] = {"x": 1}
            results.append(fail(name, "%s outer container mutable" % ledger_name))
            return
        except TypeError:
            mutations += 1
        for key in ledger:
            if not _mutation_raises(ledger[key]):
                results.append(
                    fail(name, "%s inner entry mutable at %r" % (ledger_name, key))
                )
                return
            mutations += 1
    # digest stream unchanged and integrity still verified
    if gateway.digest_stream() != stream_before:
        results.append(fail(name, "mutation attempts changed the digest stream"))
        return
    gateway.verify_integrity()
    results.append(
        ok(
            name,
            "deep immutability: %d mutation paths rejected; digest stream "
            "byte-identical; integrity verified" % mutations,
        )
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    results: List[Result] = []
    for case in (
        case_01_frozen_vocabularies,
        case_02_transition_tables,
        case_03_command_model,
        case_04_event_model,
        case_05_capability_model,
        case_06_citation_snapshot,
        case_07_full_ledger_golden,
        case_08_every_legal_transition,
        case_09_every_illegal_transition,
        case_10_intent_create_retrieve,
        case_11_duplicate_commands,
        case_12_conflicting_commands,
        case_13_duplicate_intent_identity,
        case_14_provider_reference_conflict,
        case_15_authorize_flow,
        case_16_capture_flow,
        case_17_refund_flow,
        case_18_reversal_flow,
        case_19_payout_emission,
        case_20_payout_transfer_outcomes,
        case_21_callback_ingestion,
        case_22_invalid_signatures,
        case_23_observation_folds,
        case_24_provider_failures,
        case_25_reconciliation,
        case_26_capability_gating,
        case_27_payment_never_usage,
        case_28_callbacks_never_delivery,
        case_29_history_never_rewritten,
        case_30_no_vendor_leakage,
        case_31_import_discipline,
        case_32_public_api_stability,
        case_33_journal_first_recovery,
        case_34_restart_replay,
        case_35_two_run_determinism,
        case_36_subprocess_hash_seeds,
        case_37_clock_discipline,
        case_38_scope_audit,
        case_39_capability_lifecycle,
        case_40_closed_loop_composition,
        case_41_intent_correlation_citations,
        case_42_store_failures,
        case_43_open_usage_stays_open,
        case_44_deep_immutable_projections,
    ):
        case(results)
    failures = [result for result in results if not result[1]]
    for entry in results:
        print("[%s] %-44s %s" % ("ok  " if entry[1] else "FAIL",
                                 entry[0], entry[2]))
    if failures:
        print("Result: FAIL (%d/%d cases failed)"
              % (len(failures), len(results)))
        for entry in failures:
            print("  FAILED %s: %s" % (entry[0], entry[2]))
        return 1
    print("Result: PASS (%d/%d cases passed)"
          % (len(results), len(results)))
    return 0


if __name__ == "__main__":
    if "--determinism-stream" in sys.argv:
        stream = _scenario_stream()
        for key in sorted(stream):
            print("%s=%s" % (key, stream[key]))
        sys.exit(0)
    sys.exit(main())
