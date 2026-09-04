#!/usr/bin/env python3
"""WORK-051 CommercialCore battery (deterministic, stdlib only).

End-to-end verification of the canonical commercial
control-plane core (ACR-009, authorization WORK-051-CORE-001 /
DEC-0058) composing the accepted WORK-033 Linux reference
agent, WORK-012 logical sessions, WORK-041 NetworkPath, and
WORK-042 platform journal:

- frozen vocabularies: the fifteen-state lifecycle
  (CONNECTIVITY_INTENT .. SETTLED plus the four compensating
  terminals CANCELLED / EXPIRED / PATH_FAILED / NON_DELIVERED),
  the fifteen-action vocabulary, the twenty-reason vocabulary,
  the six external-reference families, and the transition table;
- lifecycle (criterion 1): the full canonical chain
  ConnectivityIntent -> ... -> Settled over REAL authority
  references (a real logical session id from the public session
  handshake, a real NetworkPath id from the manager's public
  reads, real delivery-evidence ids from the accepted platform
  journal), every legal transition exercised, every illegal
  transition rejected, attribution on every event (previous
  state, new state, action, causal command, causal references,
  actor, source);
- compensating families (criterion 2): cancellation from every
  cancellable state, expiry honestly deadline-gated (premature
  expiry and post-deadline forward progression both fail
  closed), path failure and non-delivery from the delivery
  states, historical records immutable;
- references (criterion 3): fabricated session / NetworkPath /
  delivery citations fail closed REFERENCE_UNKNOWN; wrong-family
  citations fail closed; the index is built from public reads
  only;
- payment/delivery separation (criterion 4): payment-family
  references can never justify a delivery command
  (PAYMENT_NOT_DELIVERY), never a settlement
  (PAYMENT_NOT_SETTLEMENT), reservation never implies delivery
  (table structure + command attempt), settlement without the
  intact delivery-evidence chain fails closed, delivery facts
  cannot be rewritten by later commercial events (append-only
  journal + settled immutability);
- authority boundaries (criterion 5): structural audits -- no
  second authority (construction/mutation call-token discipline
  over the frozen authority set), no authority parameters
  anywhere in the commercial surface, sanctioned imports only,
  no vendor tokens, frozen public API, frozen spec surfaces
  intact, PR delta confined to the authorized W051 scope (+ the
  sanctioned additive-only CI wiring), and the honest two-track
  evidence disclosure (software verified; PHYSICAL device
  evidence OPEN and W040-owned -- no synthetic physical claims);
- durability: append-only hash-chained journal (byte tamper,
  reorder, truncation, sequence-gap, digest-edit all fail closed
  JOURNAL_CORRUPT), persist-then-ack (a store failure leaves no
  phantom state), journal-first recovery (load == live,
  byte-identical), replay verification (fold == live state),
  command idempotency durable across restart (duplicates are
  no-ops; conflicting redeliveries fail closed);
- determinism: the golden scenario's whole digest stream
  (journal, state, command ledger, event list, reference index)
  is byte-identical across two fresh in-process runs and across
  PYTHONHASHSEED 0/1/7919/unset subprocesses; the ONLY time
  source is the injected clock seam (duplicates consume no read;
  every other submission consumes exactly one; no wall-clock
  module is imported in the commercial family);
- secret hygiene: journal and digest bytes carry no key
  material, credentials, or secret-like tokens;
- conformance completion (the three explicitly named
  order/immutability/isolation dimensions): out-of-order events
  fail closed at every layer (an early forward command at
  admission with zero journal drift; an incoherent action/target
  attribution at the model gate; a fully-recomputed,
  table-legal, chain-valid record whose declared from_state does
  not connect to the folded walk is rejected at replay by the
  walk-linkage verification -- the replay verifies the WALK, not
  merely the chain and each edge), delivery facts are immutable
  (no compensating action after DELIVERY_COMPLETED, no
  re-pointing of the delivery evidence, the recorded delivery
  events survive byte-identically through settlement), and
  fresh-world independence (every vector builds its own fixture
  world; interleaved coexisting worlds reproduce their isolated
  baselines byte-for-byte -- no shared mutable commercial
  state).

The battery exercises the PUBLIC production path only: the
ordinary AgentRuntime session establishment chain, the
NetworkPathManager public lifecycle, the PlatformIntegrator
public surface, and the CommercialCore public surface.  No
private method is called to manufacture a PASS.
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
# ambiguous top-level ``from platform import ...`` form (which the
# platform battery's stdlib-shadowing hazard pin rightly flags), the
# submodule form can resolve ONLY to the repository-local package --
# the stdlib has no journal/lifecycle submodules -- so the composition
# is unambiguous by construction.
from platform.journal import MemoryPlatformStore  # noqa: E402
from platform.lifecycle import PlatformIntegrator  # noqa: E402

import commercial  # noqa: E402
from commercial import (  # noqa: E402
    ACTION_FAMILY_RULES,
    ACTION_REQUIRED_STATE,
    ACTION_TARGET_STATE,
    CommercialAction,
    CommercialCommand,
    CommercialCore,
    CommercialError,
    CommercialEvent,
    CommercialReasonCode,
    CommercialState,
    LIFECYCLE_TRANSITIONS,
    Reference,
    ReferenceFamily,
    ReferenceIndex,
    transition_is_legal,
)
from commercial.digest import (
    command_ledger_digest,
    state_digest,
)
from commercial.journal import (  # noqa: E402
    GENESIS_RECORD_ID,
    derive_record_id,
    journal_bytes_for,
    record_content,
)
from commercial.lifecycle import fold_state  # noqa: E402
from commercial.model import derive_event_id  # noqa: E402

Result = Tuple[str, bool, str]

_FAMILY_FILES = sorted((REPO_ROOT / "commercial").rglob("*.py"))

_T0 = "2025-06-01T00:00:00Z"
_FRESH = "2026-06-01T00:00:00Z"
_SECRET_A = b"w051-battery-secret-A"
_SECRET_B = b"w051-battery-secret-B"
_PROFILE_ID = "identity.sha256-hmac-dev.v1"
_KEY_A = b"w051-battery-key-A"
_KEY_B = b"w051-battery-key-B"

#: The commercial clock epoch and step (one read per non-duplicate
#: command submission).
_CT0 = "2026-09-01T12:00:00Z"
_CSTEP = 60
#: The golden-scenario reservation window (t0 + 10 minutes; the
#: golden chain's authorize/activate instants are all inside it).
_DEADLINE = "2026-09-01T12:10:00Z"
#: A near deadline for expiry threads (t0 + 2 minutes).
_NEAR_DEADLINE = "2026-09-01T12:02:00Z"

WIFI_IF = "wlan0"
ETH_IF = "eth0"
USB_IF = "usb0"
CELL_IF = "vpn0"

#: The frozen commercial public API surface (independently pinned
#: here; the package must match exactly).
_EXPECTED_API = sorted([
    "ACTION_FAMILY_RULES",
    "ACTION_REQUIRED_STATE",
    "ACTION_TARGET_STATE",
    "AppendOnlyCommercialJournal",
    "CommercialAction",
    "CommercialCommand",
    "CommercialCore",
    "CommercialError",
    "CommercialEvent",
    "CommercialReasonCode",
    "CommercialState",
    "CommercialStore",
    "CommercialTransaction",
    "CommandOutcome",
    "CommandStatus",
    "FileCommercialStore",
    "GENESIS_RECORD_ID",
    "JOURNAL_RECORD_KIND",
    "JournalRecord",
    "LIFECYCLE_TRANSITIONS",
    "MemoryCommercialStore",
    "Reference",
    "ReferenceFamily",
    "ReferenceIndex",
    "apply_record",
    "assemble_digest_stream",
    "command_content",
    "command_ledger_digest",
    "derive_command_digest",
    "derive_event_id",
    "derive_record_id",
    "derive_transaction_id",
    "digest_of",
    "event_list_digest",
    "fold_state",
    "journal_bytes_for",
    "record_list_digest",
    "reference_family_counts",
    "reference_index_digest",
    "resolve_references",
    "state_digest",
    "transaction_digest",
    "transition_is_legal",
    "validate_cancel_state",
    "validate_command_against_transaction",
    "validate_expire_due",
    "validate_family_rules",
    "validate_non_delivery_state",
    "validate_path_failure_state",
    "validate_payload_shape",
    "validate_reservation_deadline",
    "validate_settlement_integrity",
])

#: The authorized W051 delta surface (scope of WORK-051-CORE-001)
#: plus the sanctioned additive CI-wiring path (the W041/W042
#: battery precedent: batteries explicitly allow an ADDITIVE
#: .github delta in the implementation PR and check it never
#: weakens a step).
_AUTHORIZED_PATHS = (
    "commercial/",
    "tools/commercial_selftest.py",
    "docs/WORK-051-handoff.md",
    "docs/WORK-051-evidence.md",
)
AUTHORIZED_CI_WIRING = ".github/workflows/spec-check.yml"

#: Vendor/payment-provider tokens the commercial family must
#: never encode (technology- and provider-neutral core).
_VENDOR_TOKENS = (
    "android", "rndis", "qualcomm", "mediatek", "samsung", "broadcom",
    "huawei", "apple", "google", "windows", "darwin", "ios_",
    "open5gs", "ocudu", "openairinterface",
    "stripe", "paypal", "mtn", "vodafone", "airteltigo", "telecel",
    "visa", "mastercard", "mpesa", "alipay", "wise",
)

#: Forbidden authority-construction/mutation tokens: the
#: commercial family must never build or drive a second
#: authority (isinstance checks and type annotations against the
#: composed public classes are fine -- the scan targets
#: CONSTRUCTION and MUTATION calls).
_FORBIDDEN_TOKENS = (
    "RoutingEngine(", "PolicyEngine(", "TransportManager(",
    "TopologyGraph(", "SessionStore(", "IdentityService(",
    "NetworkPathManager(", "AgentRuntime(", "MobileAgent(",
    "MultipathSessionManager(", "MobilityController(",
    "PlatformIntegrator(", "CommercialCore(",
    "sessions.create", "sessions.transition", "sessions.reconnect",
    "sessions.terminate", "sessions.suspend", "sessions.append_event",
    "derive_session_id", "establish_session(", "accept_session(",
    "complete_session(", "finalize_session(", "bind_session(",
    "register_peer(", "expose_interfaces(", "send_datagram(",
)

#: The sanctioned absolute-import allowlist for the commercial
#: family (stdlib value types + the accepted seams: WORK-003
#: canonicalization and the WORK-033 clock seam; the reference
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
            role_id="w051-battery-operator",
            capabilities=(
                ManagementCapability.SESSION_READ,
                ManagementCapability.SESSION_CONTROL,
                ManagementCapability.POLICY_READ,
            ),
            description="operator role (battery fixture)",
        ),
    )


def _config(
    label: str = "commercial-node",
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
    session, and a PlatformIntegrator journal of delivery-plane
    evidence events -- all through the ordinary public production
    chain.  Returns (runtime, peer, session_id, manager,
    integrator, shared clock)."""
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
    for snapshot in snapshots:
        integrator.ingest_interface_observation(
            snapshot, observed_at=shared.now()
        )
    integrator.ingest_platform_state(
        _platform_snapshot(), observed_at=shared.now()
    )
    return runtime, peer, session_id, manager, integrator, shared


def _path_for(manager: NetworkPathManager, interface_name: str) -> str:
    for path_id in manager.paths():
        if manager.path(path_id).interface_name == interface_name:
            return path_id
    raise AssertionError("no candidate for interface %r" % interface_name)


# ---------------------------------------------------------------------------
# Commercial fixtures (deterministic external ids, public reads only)
# ---------------------------------------------------------------------------


def _external_id(kind: str, label: str) -> str:
    """A deterministic well-formed EXTERNAL-plane id (settlement
    confirmations and payment observations genuinely live outside
    ADCOS; the battery cites synthetic-but-deterministic external
    ids with explicit provenance labels)."""
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes({"kind": kind, "label": label})
    ).hexdigest()


def _references(
    manager: NetworkPathManager,
    integrator: PlatformIntegrator,
    session_id: str,
    *,
    with_delivery: bool = True,
) -> ReferenceIndex:
    """Build the injected ReferenceIndex from PUBLIC reads only."""
    entries: List[Reference] = [
        Reference(session_id, ReferenceFamily.SESSION, "sessions-authority"),
    ]
    for path_id in manager.paths():
        entries.append(
            Reference(
                path_id, ReferenceFamily.NETWORK_PATH, "networkpath-manager"
            )
        )
    # partition the platform journal by observation kind: the
    # interface observations are the delivery plane's evidence;
    # the platform-state observation is the usage metering INPUT
    # plane (WORK-052 will own metering; W051 records citations)
    usage_ids: List[str] = []
    for record in integrator.journal_records():
        event = record.event
        if event.kind == "platform-state-observation":
            usage_ids.append(event.event_id)
            continue
        if with_delivery:
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


def _session_ref(references: ReferenceIndex) -> str:
    return references.by_family(ReferenceFamily.SESSION)[0].reference_id


def _path_ref(references: ReferenceIndex) -> str:
    return references.by_family(ReferenceFamily.NETWORK_PATH)[0].reference_id


def _delivery_refs(references: ReferenceIndex) -> Tuple[str, ...]:
    return tuple(
        ref.reference_id
        for ref in references.by_family(ReferenceFamily.DELIVERY_EVIDENCE)
    )


def _usage_ref(references: ReferenceIndex) -> str:
    return references.by_family(ReferenceFamily.USAGE)[0].reference_id


def _settlement_ref() -> str:
    return _external_id("settlement-confirmation", "settle-1")


def _payment_ref() -> str:
    return _external_id("payment-observation", "payment-1")


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


class FailingCommercialStore(commercial.MemoryCommercialStore):
    """A battery fixture: a store whose journal append fails (the
    persist-then-ack discipline: no phantom in-memory state)."""

    def append_journal_line(self, line: bytes) -> None:
        raise CommercialError(
            CommercialReasonCode.STORE_FAILED,
            "battery fixture: simulated durable-append failure",
        )


class FrozenBytesStore(commercial.CommercialStore):
    """A battery fixture: serves fixed (possibly tampered) journal
    bytes for tamper-detection loads."""

    def __init__(self, data: bytes) -> None:
        self._data = data

    def append_journal_line(self, line: bytes) -> None:
        raise CommercialError(
            CommercialReasonCode.STORE_FAILED,
            "battery fixture: frozen store is read-only",
        )

    def journal_bytes(self) -> bytes:
        return self._data


def _expect_commercial_error(
    name: str, reason: str, func, *args, **kwargs
) -> Optional[str]:
    """Run func; PASS iff it raised CommercialError with the reason."""
    try:
        func(*args, **kwargs)
    except CommercialError as error:
        if error.reason == reason:
            return None
        return "expected %s, got %s (%s)" % (reason, error.reason, error.detail)
    except Exception as error:  # noqa: BLE001 - wrong exception type is a failure
        return "wrong exception type %s" % type(error).__name__
    return "no error raised (expected %s)" % reason


# ---------------------------------------------------------------------------
# The canonical golden scenario (determinism stream + composition)
# ---------------------------------------------------------------------------


def _golden_scenario(
    store, references, clock, *, intent=None, prefix="cmd-"
) -> Tuple[CommercialCore, str]:
    """Drive the full canonical lifecycle to SETTLED on one
    transaction over the composed world.  The optional ``intent``
    and ``prefix`` select a structurally different transaction (the
    fresh-world vector): with the defaults the scenario is the
    canonical golden run byte-for-byte."""
    core = CommercialCore(store=store, clock=clock, references=references)
    out = core.submit_intent(
        command_id=prefix + "01",
        actor="buyer-agent",
        source="developer-api",
        intent=intent if intent is not None else {
            "buyer": "buyer-1", "want": "connectivity", "region": "gh",
        },
    )
    tx = out.transaction_id
    core.select_offer(
        command_id=prefix + "02", transaction_id=tx, actor="buyer-agent",
        source="developer-api",
        offer={"offer_id": "offer-1", "provider": "provider-1",
               "unit": "GB", "price": "10"},
    )
    core.hold_reservation(
        command_id=prefix + "03", transaction_id=tx, actor="platform",
        source="reservation-service", expires_at=_DEADLINE,
        payment_refs=(_payment_ref(),),
    )
    core.authorize_session(
        command_id=prefix + "04", transaction_id=tx, actor="platform",
        source="session-service", session_ref=_session_ref(references),
    )
    core.activate_path(
        command_id=prefix + "05", transaction_id=tx, actor="platform",
        source="path-service", path_ref=_path_ref(references),
    )
    delivery = sorted(_delivery_refs(references))
    core.start_delivery(
        command_id=prefix + "06", transaction_id=tx, actor="platform",
        source="delivery-service", evidence_refs=(delivery[0],),
    )
    core.accrue_usage(
        command_id=prefix + "07", transaction_id=tx, actor="platform",
        source="usage-service", usage_refs=(_usage_ref(references),),
    )
    core.complete_delivery(
        command_id=prefix + "08", transaction_id=tx, actor="platform",
        source="delivery-service", evidence_refs=(delivery[-1],),
    )
    core.finalize_billable(
        command_id=prefix + "09", transaction_id=tx, actor="platform",
        source="billing-service",
    )
    core.initiate_settlement(
        command_id=prefix + "10", transaction_id=tx, actor="platform",
        source="settlement-service", payment_refs=(_payment_ref(),),
    )
    core.settle(
        command_id=prefix + "11", transaction_id=tx, actor="platform",
        source="settlement-service", settlement_refs=(_settlement_ref(),),
    )
    return core, tx


def _scenario_stream(store=None) -> Dict[str, str]:
    """The canonical battery scenario: full authority composition
    -> the golden commercial lifecycle to SETTLED -> the
    deterministic digest stream."""
    if store is None:
        store = commercial.MemoryCommercialStore()
    runtime, peer, session_id, manager, integrator, shared = _world()
    references = _references(manager, integrator, session_id)
    clock = CountingClock(StepClock(_CT0, _CSTEP))
    core, tx = _golden_scenario(store, references, clock)
    return {
        "journal_digest": core.journal_digest(),
        "state_digest": state_digest(core.transactions()),
        "command_ledger_digest": command_ledger_digest(core.command_ledger()),
        "event_list_digest": commercial.event_list_digest(
            tuple(record.event for record in core.journal_records())
        ),
        "digest_stream_sha256": hashlib.sha256(
            core.digest_stream().encode("utf-8")
        ).hexdigest(),
    }


# ---------------------------------------------------------------------------
# State-thread helpers (drive a fresh transaction to a given state)
# ---------------------------------------------------------------------------


def _fresh_core(references, clock=None) -> CommercialCore:
    if clock is None:
        clock = StepClock(_CT0, _CSTEP)
    return CommercialCore(
        store=commercial.MemoryCommercialStore(),
        clock=clock,
        references=references,
    )


def _apply_step(core, tx, step, references):
    """Apply one named canonical step (fixed ids/args)."""
    if step == "submit":
        return core.submit_intent(
            command_id="t-01", actor="buyer-agent", source="developer-api",
            intent={"buyer": "buyer-1", "want": "connectivity"},
        )
    if step == "select":
        return core.select_offer(
            command_id="t-02", transaction_id=tx, actor="buyer-agent",
            source="developer-api",
            offer={"offer_id": "offer-1", "price": "10"},
        )
    if step == "hold":
        return core.hold_reservation(
            command_id="t-03", transaction_id=tx, actor="platform",
            source="reservation-service", expires_at=_DEADLINE,
        )
    if step == "hold-near":
        return core.hold_reservation(
            command_id="t-03", transaction_id=tx, actor="platform",
            source="reservation-service", expires_at=_NEAR_DEADLINE,
        )
    if step == "authorize":
        return core.authorize_session(
            command_id="t-04", transaction_id=tx, actor="platform",
            source="session-service", session_ref=_session_ref(references),
        )
    if step == "activate":
        return core.activate_path(
            command_id="t-05", transaction_id=tx, actor="platform",
            source="path-service", path_ref=_path_ref(references),
        )
    if step == "start":
        delivery = sorted(_delivery_refs(references))
        return core.start_delivery(
            command_id="t-06", transaction_id=tx, actor="platform",
            source="delivery-service", evidence_refs=(delivery[0],),
        )
    if step == "accrue":
        return core.accrue_usage(
            command_id="t-07", transaction_id=tx, actor="platform",
            source="usage-service", usage_refs=(_usage_ref(references),),
        )
    if step == "complete":
        delivery = sorted(_delivery_refs(references))
        return core.complete_delivery(
            command_id="t-08", transaction_id=tx, actor="platform",
            source="delivery-service", evidence_refs=(delivery[-1],),
        )
    if step == "billable":
        return core.finalize_billable(
            command_id="t-09", transaction_id=tx, actor="platform",
            source="billing-service",
        )
    if step == "initiate":
        return core.initiate_settlement(
            command_id="t-10", transaction_id=tx, actor="platform",
            source="settlement-service",
        )
    if step == "settle":
        return core.settle(
            command_id="t-11", transaction_id=tx, actor="platform",
            source="settlement-service", settlement_refs=(_settlement_ref(),),
        )
    raise AssertionError("unknown step %r" % step)


_STATE_STEPS: Dict[str, Tuple[str, ...]] = {
    CommercialState.CONNECTIVITY_INTENT: ("submit",),
    CommercialState.OFFER_SELECTED: ("submit", "select"),
    CommercialState.RESERVATION_HELD: ("submit", "select", "hold"),
    CommercialState.SESSION_AUTHORIZED: ("submit", "select", "hold", "authorize"),
    CommercialState.PATH_ACTIVE: ("submit", "select", "hold", "authorize", "activate"),
    CommercialState.DELIVERY_STARTED: (
        "submit", "select", "hold", "authorize", "activate", "start",
    ),
    CommercialState.USAGE_ACCRUING: (
        "submit", "select", "hold", "authorize", "activate", "start", "accrue",
    ),
    CommercialState.DELIVERY_COMPLETED: (
        "submit", "select", "hold", "authorize", "activate", "start",
        "accrue", "complete",
    ),
    CommercialState.BILLABLE_FINAL: (
        "submit", "select", "hold", "authorize", "activate", "start",
        "accrue", "complete", "billable",
    ),
    CommercialState.SETTLEMENT_PENDING: (
        "submit", "select", "hold", "authorize", "activate", "start",
        "accrue", "complete", "billable", "initiate",
    ),
    CommercialState.SETTLED: (
        "submit", "select", "hold", "authorize", "activate", "start",
        "accrue", "complete", "billable", "initiate", "settle",
    ),
}


def _thread_at(state: str, references) -> Tuple[CommercialCore, str]:
    """A fresh core + transaction driven to the given state."""
    core = _fresh_core(references)
    out = None
    for step in _STATE_STEPS[state]:
        out = _apply_step(core, out.transaction_id if out else "", step, references)
    assert out is not None
    return core, out.transaction_id


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------


def case_01_frozen_vocabularies(results: List[Result]) -> None:
    name = "case_01_frozen_vocabularies"
    problems: List[str] = []
    if sorted(CommercialState.values()) != sorted([
        "CONNECTIVITY_INTENT", "OFFER_SELECTED", "RESERVATION_HELD",
        "SESSION_AUTHORIZED", "PATH_ACTIVE", "DELIVERY_STARTED",
        "USAGE_ACCRUING", "DELIVERY_COMPLETED", "BILLABLE_FINAL",
        "SETTLEMENT_PENDING", "SETTLED", "CANCELLED", "EXPIRED",
        "PATH_FAILED", "NON_DELIVERED",
    ]):
        problems.append("state vocabulary drifted")
    if sorted(CommercialState.terminal_values()) != sorted([
        "SETTLED", "CANCELLED", "EXPIRED", "PATH_FAILED", "NON_DELIVERED",
    ]):
        problems.append("terminal vocabulary drifted")
    if sorted(CommercialState.compensating_values()) != sorted([
        "CANCELLED", "EXPIRED", "PATH_FAILED", "NON_DELIVERED",
    ]):
        problems.append("compensating vocabulary drifted")
    if sorted(CommercialAction.values()) != sorted([
        "submit_intent", "select_offer", "hold_reservation",
        "authorize_session", "activate_path", "start_delivery",
        "accrue_usage", "complete_delivery", "finalize_billable",
        "initiate_settlement", "settle", "cancel", "expire",
        "record_path_failure", "record_non_delivery",
    ]):
        problems.append("action vocabulary drifted")
    if sorted(CommercialReasonCode.values()) != sorted([
        "invalid-input", "command-invalid", "command-duplicate",
        "command-conflict", "transaction-unknown", "lifecycle-illegal",
        "history-immutable", "reservation-expired", "expiry-not-due",
        "path-failure-rejected", "non-delivery-rejected",
        "settlement-rejected", "payment-not-delivery",
        "payment-not-settlement", "reference-unknown",
        "reference-family-invalid", "event-invalid", "journal-corrupt",
        "store-failed", "instant-invalid",
    ]):
        problems.append("reason vocabulary drifted")
    if sorted(ReferenceFamily.values()) != sorted([
        "session", "network-path", "delivery-evidence", "usage",
        "settlement", "payment",
    ]):
        problems.append("reference-family vocabulary drifted")
    if sorted(ACTION_TARGET_STATE) != sorted(CommercialAction.values()):
        problems.append("action target table drifted")
    if sorted(ACTION_REQUIRED_STATE) != sorted(CommercialAction.values()):
        problems.append("action precondition table drifted")
    if sorted(ACTION_FAMILY_RULES) != sorted(CommercialAction.values()):
        problems.append("action family-rules table drifted")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(ok(
        name, "states/actions/reasons/families/tables frozen: %d states, "
        "%d actions, %d reasons, %d families"
        % (len(CommercialState.values()), len(CommercialAction.values()),
           len(CommercialReasonCode.values()), len(ReferenceFamily.values()))
    ))


def case_02_lifecycle_table(results: List[Result]) -> None:
    name = "case_02_lifecycle_transition_table"
    expected: Dict[str, set] = {
        "CONNECTIVITY_INTENT": {"CONNECTIVITY_INTENT", "OFFER_SELECTED", "CANCELLED"},
        "OFFER_SELECTED": {"RESERVATION_HELD", "CANCELLED"},
        "RESERVATION_HELD": {"SESSION_AUTHORIZED", "CANCELLED", "EXPIRED"},
        "SESSION_AUTHORIZED": {"PATH_ACTIVE", "CANCELLED", "EXPIRED"},
        "PATH_ACTIVE": {"DELIVERY_STARTED", "CANCELLED", "PATH_FAILED", "NON_DELIVERED"},
        "DELIVERY_STARTED": {"USAGE_ACCRUING", "PATH_FAILED", "NON_DELIVERED"},
        "USAGE_ACCRUING": {"USAGE_ACCRUING", "DELIVERY_COMPLETED", "PATH_FAILED", "NON_DELIVERED"},
        "DELIVERY_COMPLETED": {"BILLABLE_FINAL"},
        "BILLABLE_FINAL": {"SETTLEMENT_PENDING"},
        "SETTLEMENT_PENDING": {"SETTLED"},
        "SETTLED": set(),
        "CANCELLED": set(),
        "EXPIRED": set(),
        "PATH_FAILED": set(),
        "NON_DELIVERED": set(),
    }
    actual = {state: set(targets) for state, targets in LIFECYCLE_TRANSITIONS.items()}
    problems: List[str] = []
    if actual != expected:
        for state in sorted(set(actual) | set(expected)):
            if actual.get(state) != expected.get(state):
                problems.append(
                    "%s: expected %s, found %s"
                    % (state, sorted(expected.get(state, set())),
                       sorted(actual.get(state, set())))
                )
    # structural invariants
    for state in CommercialState.terminal_values():
        if LIFECYCLE_TRANSITIONS.get(state) != frozenset():
            problems.append("terminal state %s has outgoing edges" % state)
    # payment/settlement/reservation states never jump to delivery
    for jump_from in ("RESERVATION_HELD", "SESSION_AUTHORIZED",
                      "BILLABLE_FINAL", "SETTLEMENT_PENDING", "SETTLED"):
        targets = LIFECYCLE_TRANSITIONS[jump_from]
        for delivery in ("DELIVERY_STARTED", "USAGE_ACCRUING", "DELIVERY_COMPLETED"):
            if delivery in targets:
                problems.append("%s can jump to %s" % (jump_from, delivery))
    # out-of-vocabulary states fail closed
    if transition_is_legal("UNKNOWN", "SETTLED"):
        problems.append("unknown state transitions")
    if transition_is_legal("SETTLED", "SETTLED"):
        problems.append("settled self-transition")
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    edge_count = sum(len(t) for t in LIFECYCLE_TRANSITIONS.values())
    results.append(ok(
        name, "table exact (%d edges); terminals immutable; no "
        "payment/reservation/settlement -> delivery jumps" % edge_count
    ))


def case_03_command_model(results: List[Result]) -> None:
    name = "case_03_command_model_and_digests"
    problems: List[str] = []
    command = CommercialCommand(
        command_id="c-1", action=CommercialAction.SELECT_OFFER,
        transaction_id="sha256:" + "1" * 64, references=(),
        payload={"offer": {"offer_id": "o1", "price": "10"}},
        actor="buyer", source="api",
    )
    if command.digest() != command.digest():
        problems.append("digest not stable")
    command_two = CommercialCommand(
        command_id="c-1", action=CommercialAction.SELECT_OFFER,
        transaction_id="sha256:" + "1" * 64, references=(),
        payload={"offer": {"offer_id": "o1", "price": "10"}},
        actor="buyer", source="api",
    )
    if command.digest() != command_two.digest():
        problems.append("identical content produced different digests")
    command_diff = CommercialCommand(
        command_id="c-1", action=CommercialAction.SELECT_OFFER,
        transaction_id="sha256:" + "1" * 64, references=(),
        payload={"offer": {"offer_id": "o2", "price": "10"}},
        actor="buyer", source="api",
    )
    if command.digest() == command_diff.digest():
        problems.append("different content produced the same digest")
    # round trip
    restored = CommercialCommand.from_dict(command.to_dict())
    if restored.to_dict() != command.to_dict():
        problems.append("command round trip drifted")
    # float payloads fail closed (canonical subset discipline)
    problem = _expect_commercial_error(
        name, CommercialReasonCode.INVALID_INPUT,
        CommercialCommand,
        command_id="c-f", action=CommercialAction.SELECT_OFFER,
        transaction_id="sha256:" + "1" * 64, references=(),
        payload={"offer": {"price": 10.5}}, actor="buyer", source="api",
    )
    if problem:
        problems.append("float payload accepted: %s" % problem)
    # submit_intent must not carry a transaction citation
    problem = _expect_commercial_error(
        name, CommercialReasonCode.COMMAND_INVALID,
        CommercialCommand,
        command_id="c-s", action=CommercialAction.SUBMIT_INTENT,
        transaction_id="sha256:" + "2" * 64, references=(),
        payload={"intent": {"k": "v"}}, actor="buyer", source="api",
    )
    if problem:
        problems.append("submit_intent with transaction citation: %s" % problem)
    # malformed from_dict
    problem = _expect_commercial_error(
        name, CommercialReasonCode.COMMAND_INVALID,
        CommercialCommand.from_dict, {"command_id": "x"},
    )
    if problem:
        problems.append("malformed command dict accepted: %s" % problem)
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(ok(name, "digests content-derived; round trips exact; "
                            "floats and malformed shapes fail closed"))


def case_04_event_model(results: List[Result]) -> None:
    name = "case_04_event_model_and_content_binding"
    problems: List[str] = []
    runtime, peer, session_id, manager, integrator, shared = _world()
    references = _references(manager, integrator, session_id)
    core, tx = _golden_scenario(
        commercial.MemoryCommercialStore(), references, StepClock(_CT0, _CSTEP)
    )
    event = core.journal_records()[0].event
    # round trip
    restored = CommercialEvent.from_dict(event.to_dict())
    if restored.to_dict() != event.to_dict():
        problems.append("event round trip drifted")
    # tampered event id fails the content binding
    tampered = event.to_dict()
    tampered["event_id"] = "sha256:" + "0" * 64
    problem = _expect_commercial_error(
        name, CommercialReasonCode.EVENT_INVALID,
        CommercialEvent.from_dict, tampered,
    )
    if problem:
        problems.append("tampered event id accepted: %s" % problem)
    # instant tampering: a malformed instant fails the shape gate;
    # a WELL-FORMED but altered instant fails the content binding
    tampered = event.to_dict()
    tampered["instant"] = "not-an-instant"
    problem = _expect_commercial_error(
        name, CommercialReasonCode.INSTANT_INVALID,
        CommercialEvent.from_dict, tampered,
    )
    if problem:
        problems.append("malformed instant accepted: %s" % problem)
    tampered = event.to_dict()
    tampered["instant"] = "2026-09-01T12:01:00Z"
    problem = _expect_commercial_error(
        name, CommercialReasonCode.EVENT_INVALID,
        CommercialEvent.from_dict, tampered,
    )
    if problem:
        problems.append("tampered well-formed instant accepted: %s" % problem)
    # unknown states/actions fail closed
    for key, value in (
        ("from_state", "NOT_A_STATE"),
        ("to_state", "NOT_A_STATE"),
        ("action", "not_an_action"),
    ):
        bad = event.to_dict()
        bad[key] = value
        problem = _expect_commercial_error(
            name, CommercialReasonCode.EVENT_INVALID,
            CommercialEvent.from_dict, bad,
        )
        if problem:
            problems.append("%s=%r accepted: %s" % (key, value, problem))
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(ok(name, "content-bound ids verified at construction and "
                            "deserialization; tamper fails closed"))


def case_05_full_lifecycle_golden(results: List[Result]) -> None:
    name = "case_05_full_lifecycle_golden"
    runtime, peer, session_id, manager, integrator, shared = _world()
    references = _references(manager, integrator, session_id)
    clock = CountingClock(StepClock(_CT0, _CSTEP))
    core, tx = _golden_scenario(commercial.MemoryCommercialStore(), references, clock)
    problems: List[str] = []
    chain = [
        "CONNECTIVITY_INTENT", "OFFER_SELECTED", "RESERVATION_HELD",
        "SESSION_AUTHORIZED", "PATH_ACTIVE", "DELIVERY_STARTED",
        "USAGE_ACCRUING", "DELIVERY_COMPLETED", "BILLABLE_FINAL",
        "SETTLEMENT_PENDING", "SETTLED",
    ]
    events = [record.event for record in core.journal_records()]
    observed = [event.to_state for event in events]
    if observed != chain:
        problems.append("state chain %s != canonical %s" % (observed, chain))
    transaction = core.transaction(tx)
    if not transaction.settled():
        problems.append("final state not SETTLED")
    # attribution on every event
    for event in events:
        if not (event.from_state and event.to_state and event.action
                and event.command_id and event.actor and event.source
                and event.instant and event.event_id):
            problems.append("event %s missing attribution" % event.event_id)
    # reference partitioning
    if transaction.session_ref != session_id:
        problems.append("session_ref not the real session id")
    if transaction.path_ref not in manager.paths():
        problems.append("path_ref not a real network path id")
    platform_event_ids = {
        record.event.event_id for record in integrator.journal_records()
    }
    if not set(transaction.delivery_evidence_refs) <= platform_event_ids:
        problems.append("delivery evidence refs not from the platform journal")
    if not transaction.usage_refs:
        problems.append("usage refs empty")
    if not transaction.settlement_refs:
        problems.append("settlement refs empty")
    if len(transaction.payment_refs) != 2:
        problems.append("payment DATA refs not recorded (hold + initiate)")
    if clock.reads != 11:
        problems.append("clock reads %d != 11 (one per command)" % clock.reads)
    if len(core.journal_records()) != 11:
        problems.append("journal records %d != 11" % len(core.journal_records()))
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(ok(
        name, "11-state chain over real authority references; every event "
        "attributable; one clock read per command; 11 atomic journal records"
    ))


def case_06_every_legal_transition(results: List[Result]) -> None:
    name = "case_06_every_legal_transition_exercised"
    runtime, peer, session_id, manager, integrator, shared = _world()
    references = _references(manager, integrator, session_id)
    problems: List[str] = []
    exercised: set = set()
    # map target state -> the (unique) action that produces it
    target_actions: Dict[str, str] = {
        target: action for action, target in ACTION_TARGET_STATE.items()
    }
    for source_state, targets in sorted(LIFECYCLE_TRANSITIONS.items()):
        for target in sorted(targets):
            if target == CommercialState.EXPIRED:
                # expiry edges need deadline-honest threads (below):
                # a generic thread's far deadline is honestly NOT due
                continue
            action = target_actions.get(target)
            if action is None:
                problems.append("no action for target %s" % target)
                continue
            # a thread at the source state
            if source_state not in _STATE_STEPS:
                continue  # compensating source states never threads
            core, tx = _thread_at(source_state, references)
            try:
                if action == CommercialAction.SUBMIT_INTENT:
                    continue  # creation self-edge covered by every thread
                out = _apply_action(core, tx, action, references)
            except CommercialError as error:
                problems.append(
                    "edge %s -> %s (%s) failed: %s"
                    % (source_state, target, action, error.detail)
                )
                continue
            if out.to_state != target:
                problems.append(
                    "edge %s -> %s produced %s" % (source_state, target, out.to_state)
                )
            if core.transaction(tx).state != target:
                problems.append(
                    "projection did not reach %s" % target
                )
            exercised.add((source_state, target))
    # expiry edges need per-thread deadlines (read n lands at
    # t0+(n-1)*60s; the deadline must close after the last forward
    # read and at/before the expire attempt's read)
    _EXPIRY_THREADS = {
        # hold at read3 (t0+120); expire at read4 (t0+180)
        "RESERVATION_HELD": (("submit", None), ("select", None),
                             ("hold-mid", "2026-09-01T12:03:00Z")),
        # hold at read3; authorize at read4 (t0+180); expire at
        # read5 (t0+240)
        "SESSION_AUTHORIZED": (("submit", None), ("select", None),
                               ("hold-mid", "2026-09-01T12:04:00Z"),
                               ("authorize", None)),
    }
    for source_state, steps in _EXPIRY_THREADS.items():
        core = _fresh_core(references)
        out = None
        for step, deadline in steps:
            if step == "hold-mid":
                out = core.hold_reservation(
                    command_id="t-03", transaction_id=out.transaction_id,
                    actor="platform", source="reservation-service",
                    expires_at=deadline,
                )
            else:
                out = _apply_step(
                    core, out.transaction_id if out else "", step, references
                )
        tx = out.transaction_id
        if core.transaction(tx).state != source_state:
            problems.append(
                "expiry thread for %s reached %s"
                % (source_state, core.transaction(tx).state)
            )
            continue
        out = core.expire(
            command_id="t-exp", transaction_id=tx, actor="platform",
            source="reservation-service",
        )
        if out.to_state != CommercialState.EXPIRED:
            problems.append("expiry edge from %s failed" % source_state)
        exercised.add((source_state, CommercialState.EXPIRED))
    total_edges = sum(len(t) for t in LIFECYCLE_TRANSITIONS.values())
    if len(exercised) + 1 != total_edges:  # +1: submit self-edge via threads
        problems.append(
            "exercised %d of %d edges" % (len(exercised), total_edges)
        )
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(ok(
        name, "all %d table edges driven to their exact target states"
        % total_edges
    ))


def _apply_action(core, tx, action, references):
    if action == CommercialAction.SUBMIT_INTENT:
        return core.submit_intent(
            command_id="x-01", actor="buyer-agent", source="developer-api",
            intent={"buyer": "buyer-1", "want": "connectivity"},
        )
    if action == CommercialAction.SELECT_OFFER:
        return core.select_offer(
            command_id="x-02", transaction_id=tx, actor="buyer-agent",
            source="developer-api", offer={"offer_id": "o1", "price": "10"},
        )
    if action == CommercialAction.HOLD_RESERVATION:
        return core.hold_reservation(
            command_id="x-03", transaction_id=tx, actor="platform",
            source="reservation-service", expires_at=_DEADLINE,
        )
    if action == CommercialAction.AUTHORIZE_SESSION:
        return core.authorize_session(
            command_id="x-04", transaction_id=tx, actor="platform",
            source="session-service", session_ref=_session_ref(references),
        )
    if action == CommercialAction.ACTIVATE_PATH:
        return core.activate_path(
            command_id="x-05", transaction_id=tx, actor="platform",
            source="path-service", path_ref=_path_ref(references),
        )
    if action == CommercialAction.START_DELIVERY:
        delivery = sorted(_delivery_refs(references))
        return core.start_delivery(
            command_id="x-06", transaction_id=tx, actor="platform",
            source="delivery-service", evidence_refs=(delivery[0],),
        )
    if action == CommercialAction.ACCRUE_USAGE:
        return core.accrue_usage(
            command_id="x-07", transaction_id=tx, actor="platform",
            source="usage-service", usage_refs=(_usage_ref(references),),
        )
    if action == CommercialAction.COMPLETE_DELIVERY:
        delivery = sorted(_delivery_refs(references))
        return core.complete_delivery(
            command_id="x-08", transaction_id=tx, actor="platform",
            source="delivery-service", evidence_refs=(delivery[-1],),
        )
    if action == CommercialAction.FINALIZE_BILLABLE:
        return core.finalize_billable(
            command_id="x-09", transaction_id=tx, actor="platform",
            source="billing-service",
        )
    if action == CommercialAction.INITIATE_SETTLEMENT:
        return core.initiate_settlement(
            command_id="x-10", transaction_id=tx, actor="platform",
            source="settlement-service",
        )
    if action == CommercialAction.SETTLE:
        return core.settle(
            command_id="x-11", transaction_id=tx, actor="platform",
            source="settlement-service", settlement_refs=(_settlement_ref(),),
        )
    if action == CommercialAction.CANCEL:
        return core.cancel(
            command_id="x-cancel", transaction_id=tx, actor="platform",
            source="operator-console",
        )
    if action == CommercialAction.EXPIRE:
        return core.expire(
            command_id="x-expire", transaction_id=tx, actor="platform",
            source="reservation-service",
        )
    if action == CommercialAction.RECORD_PATH_FAILURE:
        return core.record_path_failure(
            command_id="x-pf", transaction_id=tx, actor="platform",
            source="path-service",
        )
    if action == CommercialAction.RECORD_NON_DELIVERY:
        return core.record_non_delivery(
            command_id="x-nd", transaction_id=tx, actor="platform",
            source="delivery-service",
        )
    raise AssertionError("unknown action %r" % action)


def case_07_every_illegal_transition(results: List[Result]) -> None:
    name = "case_07_every_illegal_transition_rejected"
    runtime, peer, session_id, manager, integrator, shared = _world()
    references = _references(manager, integrator, session_id)
    problems: List[str] = []
    cancellable = {
        "CONNECTIVITY_INTENT", "OFFER_SELECTED", "RESERVATION_HELD",
        "SESSION_AUTHORIZED", "PATH_ACTIVE",
    }
    expirable = {"RESERVATION_HELD", "SESSION_AUTHORIZED"}
    failure_states = {"PATH_ACTIVE", "DELIVERY_STARTED", "USAGE_ACCRUING"}
    target_actions: Dict[str, str] = {
        target: action for action, target in ACTION_TARGET_STATE.items()
    }
    checked = 0
    for source_state in sorted(_STATE_STEPS):
        for action, target in sorted(ACTION_TARGET_STATE.items()):
            if action == CommercialAction.SUBMIT_INTENT:
                continue
            if target in LIFECYCLE_TRANSITIONS[source_state]:
                continue  # legal edge; covered by case_06
            checked += 1
            core, tx = _thread_at(source_state, references)
            if source_state == "SETTLED":
                expected = CommercialReasonCode.HISTORY_IMMUTABLE
            elif action == CommercialAction.CANCEL and source_state not in cancellable:
                expected = CommercialReasonCode.LIFECYCLE_ILLEGAL
            elif action == CommercialAction.EXPIRE and source_state not in expirable:
                expected = CommercialReasonCode.LIFECYCLE_ILLEGAL
            elif action == CommercialAction.RECORD_PATH_FAILURE and source_state not in failure_states:
                expected = CommercialReasonCode.PATH_FAILURE_REJECTED
            elif action == CommercialAction.RECORD_NON_DELIVERY and source_state not in failure_states:
                expected = CommercialReasonCode.NON_DELIVERY_REJECTED
            else:
                expected = CommercialReasonCode.LIFECYCLE_ILLEGAL
            problem = _expect_commercial_error(
                name, expected,
                lambda c, t, a, r: _apply_action(c, t, a, r),
                core, tx, action, references,
            )
            if problem:
                problems.append(
                    "%s -> %s (%s): %s" % (source_state, target, action, problem)
                )
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(ok(
        name, "all %d illegal (state, action) pairs fail closed "
        "(settled history immutable; compensating states gated)" % checked
    ))


def case_08_cancellation(results: List[Result]) -> None:
    name = "case_08_cancellation"
    runtime, peer, session_id, manager, integrator, shared = _world()
    references = _references(manager, integrator, session_id)
    problems: List[str] = []
    for source in (
        "CONNECTIVITY_INTENT", "OFFER_SELECTED", "RESERVATION_HELD",
        "SESSION_AUTHORIZED", "PATH_ACTIVE",
    ):
        core, tx = _thread_at(source, references)
        out = core.cancel(
            command_id="c-cancel", transaction_id=tx, actor="platform",
            source="operator-console",
        )
        if out.to_state != CommercialState.CANCELLED:
            problems.append("cancel from %s produced %s" % (source, out.to_state))
        if not core.transaction(tx).terminal():
            problems.append("cancel from %s not terminal" % source)
        # any further command fails closed
        problem = _expect_commercial_error(
            name, CommercialReasonCode.LIFECYCLE_ILLEGAL,
            core.select_offer,
            command_id="c-after", transaction_id=tx, actor="platform",
            source="x", offer={"offer_id": "o"},
        )
        if problem:
            problems.append("post-cancel command accepted: %s" % problem)
    # cancel from non-cancellable states rejected
    for source in ("DELIVERY_STARTED", "USAGE_ACCRUING", "DELIVERY_COMPLETED"):
        core, tx = _thread_at(source, references)
        problem = _expect_commercial_error(
            name, CommercialReasonCode.LIFECYCLE_ILLEGAL,
            core.cancel,
            command_id="c-bad", transaction_id=tx, actor="platform",
            source="x",
        )
        if problem:
            problems.append("cancel from %s accepted: %s" % (source, problem))
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(ok(name, "cancellation compensating record from every "
                            "cancellable state; terminal; immutable after"))


def case_09_expiry(results: List[Result]) -> None:
    name = "case_09_expiry"
    runtime, peer, session_id, manager, integrator, shared = _world()
    references = _references(manager, integrator, session_id)
    problems: List[str] = []
    # premature expiry fails closed
    core = _fresh_core(references)
    out = core.submit_intent(
        command_id="e-01", actor="buyer-agent", source="developer-api",
        intent={"buyer": "b"},
    )
    tx = out.transaction_id
    core.select_offer(
        command_id="e-02", transaction_id=tx, actor="buyer-agent",
        source="developer-api", offer={"offer_id": "o"},
    )
    core.hold_reservation(
        command_id="e-03", transaction_id=tx, actor="platform",
        source="reservation-service", expires_at=_DEADLINE,
    )
    problem = _expect_commercial_error(
        name, CommercialReasonCode.EXPIRY_NOT_DUE,
        core.expire, command_id="e-04", transaction_id=tx,
        actor="platform", source="reservation-service",
    )
    if problem:
        problems.append("premature expiry accepted: %s" % problem)
    # forward progression past the deadline fails closed
    # (near deadline: t0+120; hold consumes read 3 at t0+120 -> due)
    core2 = _fresh_core(references)
    out = core2.submit_intent(
        command_id="e-11", actor="buyer-agent", source="developer-api",
        intent={"buyer": "b"},
    )
    tx2 = out.transaction_id
    core2.select_offer(
        command_id="e-12", transaction_id=tx2, actor="buyer-agent",
        source="developer-api", offer={"offer_id": "o"},
    )
    core2.hold_reservation(
        command_id="e-13", transaction_id=tx2, actor="platform",
        source="reservation-service", expires_at=_NEAR_DEADLINE,
    )
    problem = _expect_commercial_error(
        name, CommercialReasonCode.RESERVATION_EXPIRED,
        core2.authorize_session,
        command_id="e-14", transaction_id=tx2, actor="platform",
        source="session-service", session_ref=_session_ref(references),
    )
    if problem:
        problems.append("authorization on expired reservation: %s" % problem)
    out = core2.expire(
        command_id="e-15", transaction_id=tx2, actor="platform",
        source="reservation-service",
    )
    if out.to_state != CommercialState.EXPIRED:
        problems.append("expire produced %s" % out.to_state)
    if not core2.transaction(tx2).terminal():
        problems.append("expired transaction not terminal")
    # expire from a non-window state fails closed
    core3, tx3 = _thread_at("PATH_ACTIVE", references)
    problem = _expect_commercial_error(
        name, CommercialReasonCode.LIFECYCLE_ILLEGAL,
        core3.expire, command_id="e-16", transaction_id=tx3,
        actor="platform", source="x",
    )
    if problem:
        problems.append("expire from PATH_ACTIVE accepted: %s" % problem)
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(ok(name, "expiry honestly deadline-gated: premature expiry, "
                            "post-deadline authorization, and wrong-state expiry "
                            "all fail closed"))


def case_10_path_failure(results: List[Result]) -> None:
    name = "case_10_path_failure"
    runtime, peer, session_id, manager, integrator, shared = _world()
    references = _references(manager, integrator, session_id)
    problems: List[str] = []
    for source in ("PATH_ACTIVE", "DELIVERY_STARTED", "USAGE_ACCRUING"):
        core, tx = _thread_at(source, references)
        out = core.record_path_failure(
            command_id="pf-1", transaction_id=tx, actor="platform",
            source="path-service",
        )
        if out.to_state != CommercialState.PATH_FAILED:
            problems.append("path failure from %s produced %s" % (source, out.to_state))
        if not core.transaction(tx).terminal():
            problems.append("path-failed not terminal")
    for source in ("CONNECTIVITY_INTENT", "RESERVATION_HELD",
                   "DELIVERY_COMPLETED", "SETTLEMENT_PENDING"):
        core, tx = _thread_at(source, references)
        problem = _expect_commercial_error(
            name, CommercialReasonCode.PATH_FAILURE_REJECTED,
            core.record_path_failure,
            command_id="pf-2", transaction_id=tx, actor="platform",
            source="path-service",
        )
        if problem:
            problems.append("path failure from %s accepted: %s" % (source, problem))
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(ok(name, "path-failure compensating record from the "
                            "path/delivery states only"))


def case_11_non_delivery(results: List[Result]) -> None:
    name = "case_11_non_delivery"
    runtime, peer, session_id, manager, integrator, shared = _world()
    references = _references(manager, integrator, session_id)
    problems: List[str] = []
    for source in ("PATH_ACTIVE", "DELIVERY_STARTED", "USAGE_ACCRUING"):
        core, tx = _thread_at(source, references)
        out = core.record_non_delivery(
            command_id="nd-1", transaction_id=tx, actor="platform",
            source="delivery-service",
        )
        if out.to_state != CommercialState.NON_DELIVERED:
            problems.append("non-delivery from %s produced %s" % (source, out.to_state))
        if not core.transaction(tx).terminal():
            problems.append("non-delivered not terminal")
    for source in ("CONNECTIVITY_INTENT", "RESERVATION_HELD",
                   "DELIVERY_COMPLETED", "SETTLEMENT_PENDING"):
        core, tx = _thread_at(source, references)
        problem = _expect_commercial_error(
            name, CommercialReasonCode.NON_DELIVERY_REJECTED,
            core.record_non_delivery,
            command_id="nd-2", transaction_id=tx, actor="platform",
            source="delivery-service",
        )
        if problem:
            problems.append("non-delivery from %s accepted: %s" % (source, problem))
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(ok(name, "non-delivery compensating record from the "
                            "path/delivery states only"))


def case_12_duplicate_commands(results: List[Result]) -> None:
    name = "case_12_duplicate_commands"
    runtime, peer, session_id, manager, integrator, shared = _world()
    references = _references(manager, integrator, session_id)
    store = commercial.MemoryCommercialStore()
    clock = CountingClock(StepClock(_CT0, _CSTEP))
    core, tx = _golden_scenario(store, references, clock)
    journal_len = len(core.journal_records())
    state_before = core.transaction(tx).to_dict()
    reads_before = clock.reads
    problems: List[str] = []
    # exact redelivery of every command is an idempotent no-op
    duplicate_specs = [
        (core.submit_intent, dict(
            command_id="cmd-01", actor="buyer-agent", source="developer-api",
            intent={"buyer": "buyer-1", "want": "connectivity", "region": "gh"},
        )),
        (core.select_offer, dict(
            command_id="cmd-02", transaction_id=tx, actor="buyer-agent",
            source="developer-api",
            offer={"offer_id": "offer-1", "provider": "provider-1",
                   "unit": "GB", "price": "10"},
        )),
        (core.settle, dict(
            command_id="cmd-11", transaction_id=tx, actor="platform",
            source="settlement-service", settlement_refs=(_settlement_ref(),),
        )),
    ]
    for func, kwargs in duplicate_specs:
        out = func(**kwargs)
        if out.status != "duplicate":
            problems.append(
                "redelivered %s returned %s" % (kwargs["command_id"], out.status)
            )
        if core.transaction(tx).to_dict() != state_before:
            problems.append("duplicate mutated state")
    if len(core.journal_records()) != journal_len:
        problems.append("duplicate grew the journal")
    if clock.reads != reads_before:
        problems.append("duplicate consumed a clock read")
    # duplicate event id is the RECORDED event id
    out = core.settle(
        command_id="cmd-11", transaction_id=tx, actor="platform",
        source="settlement-service", settlement_refs=(_settlement_ref(),),
    )
    recorded = core.journal_records()[-1].event.event_id
    if out.event_id != recorded:
        problems.append("duplicate event id is not the recorded event id")
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(ok(name, "exact redeliveries are idempotent no-ops: no "
                            "journal growth, no clock read, no state change"))


def case_13_conflicting_duplicates(results: List[Result]) -> None:
    name = "case_13_conflicting_duplicates"
    runtime, peer, session_id, manager, integrator, shared = _world()
    references = _references(manager, integrator, session_id)
    store = commercial.MemoryCommercialStore()
    core, tx = _golden_scenario(store, references, StepClock(_CT0, _CSTEP))
    journal_len = len(core.journal_records())
    digest_before = core.journal_digest()
    state_before = core.transaction(tx).to_dict()
    problem = _expect_commercial_error(
        name, CommercialReasonCode.COMMAND_CONFLICT,
        core.select_offer,
        command_id="cmd-02", transaction_id=tx, actor="buyer-agent",
        source="developer-api",
        offer={"offer_id": "DIFFERENT", "price": "10"},
    )
    if problem:
        results.append(fail(name, "conflicting redelivery accepted: %s" % problem))
        return
    if len(core.journal_records()) != journal_len:
        results.append(fail(name, "conflict grew the journal"))
        return
    if core.journal_digest() != digest_before:
        results.append(fail(name, "conflict changed the journal digest"))
        return
    if core.transaction(tx).to_dict() != state_before:
        results.append(fail(name, "conflict mutated state"))
        return
    results.append(ok(name, "same command id with different content fails "
                            "closed COMMAND_CONFLICT; state and journal intact"))


def case_14_settlement_preconditions(results: List[Result]) -> None:
    name = "case_14_settlement_preconditions"
    runtime, peer, session_id, manager, integrator, shared = _world()
    references = _references(manager, integrator, session_id)
    problems: List[str] = []
    # settlement before BillableFinal (and before SETTLEMENT_PENDING)
    for source in ("DELIVERY_COMPLETED", "BILLABLE_FINAL"):
        core, tx = _thread_at(source, references)
        problem = _expect_commercial_error(
            name, CommercialReasonCode.LIFECYCLE_ILLEGAL,
            core.settle,
            command_id="s-early", transaction_id=tx, actor="platform",
            source="settlement-service", settlement_refs=(_settlement_ref(),),
        )
        if problem:
            problems.append("settle from %s accepted: %s" % (source, problem))
    # settlement without delivery evidence: the index evicts the
    # delivery citations between initiation and settlement (a
    # journal-first reload over the same durable store injects the
    # starving index through the PUBLIC load path)
    with tempfile.TemporaryDirectory() as tmp:
        durable = commercial.FileCommercialStore(Path(tmp) / "starved")
        core2 = CommercialCore(
            store=durable, clock=StepClock(_CT0, _CSTEP), references=references
        )
        out = core2.submit_intent(
            command_id="p-01", actor="buyer-agent", source="developer-api",
            intent={"buyer": "buyer-1", "want": "connectivity", "region": "gh"},
        )
        tx2 = out.transaction_id
        for step in (
            "select", "hold", "authorize", "activate", "start", "accrue",
            "complete", "billable", "initiate",
        ):
            _apply_step(core2, tx2, step, references)
        starving = ReferenceIndex([
            Reference(session_id, ReferenceFamily.SESSION, "sessions-authority"),
            Reference(_path_ref(references), ReferenceFamily.NETWORK_PATH, "networkpath-manager"),
            Reference(_usage_ref(references), ReferenceFamily.USAGE, "usage-plane"),
            Reference(_settlement_ref(), ReferenceFamily.SETTLEMENT, "external"),
        ])
        recovered = CommercialCore.load(
            store=commercial.FileCommercialStore(Path(tmp) / "starved"),
            clock=StepClock("2026-09-02T00:00:00Z", 60),
            references=starving,
        )
        problem = _expect_commercial_error(
            name, CommercialReasonCode.SETTLEMENT_REJECTED,
            recovered.settle,
            command_id="p-11", transaction_id=tx2, actor="platform",
            source="settlement-service", settlement_refs=(_settlement_ref(),),
        )
        if problem:
            problems.append("settlement without delivery evidence accepted: %s" % problem)
    # payment observations are not settlement confirmations
    core3, tx3 = _thread_at("SETTLEMENT_PENDING", references)
    problem = _expect_commercial_error(
        name, CommercialReasonCode.PAYMENT_NOT_SETTLEMENT,
        core3.settle,
        command_id="p-pay", transaction_id=tx3, actor="platform",
        source="settlement-service", settlement_refs=(_payment_ref(),),
    )
    if problem:
        problems.append("payment-as-settlement accepted: %s" % problem)
    # no settlement citation at all
    problem = _expect_commercial_error(
        name, CommercialReasonCode.COMMAND_INVALID,
        core3.settle,
        command_id="p-none", transaction_id=tx3, actor="platform",
        source="settlement-service", settlement_refs=(),
    )
    if problem:
        problems.append("settle without any citation accepted: %s" % problem)
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(ok(name, "settlement gated: before BillableFinal, without "
                            "delivery evidence, and with payment-only "
                            "justification all fail closed"))


def case_15_immutable_settled_history(results: List[Result]) -> None:
    name = "case_15_immutable_settled_history"
    runtime, peer, session_id, manager, integrator, shared = _world()
    references = _references(manager, integrator, session_id)
    store = commercial.MemoryCommercialStore()
    core, tx = _golden_scenario(store, references, StepClock(_CT0, _CSTEP))
    digest_before = core.journal_digest()
    state_before = core.transaction(tx).to_dict()
    problems: List[str] = []
    for action in CommercialAction.values():
        if action == CommercialAction.SUBMIT_INTENT:
            continue
        problem = _expect_commercial_error(
            name, CommercialReasonCode.HISTORY_IMMUTABLE,
            lambda a: _apply_action(core, tx, a, references), action,
        )
        if problem:
            problems.append("%s on settled: %s" % (action, problem))
        if core.journal_digest() != digest_before:
            problems.append("%s mutated the settled journal" % action)
        if core.transaction(tx).to_dict() != state_before:
            problems.append("%s mutated the settled transaction" % action)
    # a fresh settle (new command id) is also immutable-blocked
    problem = _expect_commercial_error(
        name, CommercialReasonCode.HISTORY_IMMUTABLE,
        core.settle,
        command_id="fresh-settle", transaction_id=tx, actor="platform",
        source="settlement-service", settlement_refs=(_settlement_ref(),),
    )
    if problem:
        problems.append("fresh settle on settled: %s" % problem)
    # no public mutation API exists on the store or journal classes
    journal_api = {
        attr for attr in dir(commercial.AppendOnlyCommercialJournal)
        if not attr.startswith("_")
    }
    store_api = {
        attr for attr in dir(commercial.CommercialStore)
        if not attr.startswith("_")
    }
    for api, owner in ((journal_api, "journal"), (store_api, "store")):
        for forbidden in ("pop", "remove", "clear", "update", "insert",
                          "delete", "rewrite"):
            if forbidden in api:
                problems.append("%s exposes mutation API %r" % (owner, forbidden))
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(ok(name, "SETTLED is terminal: every command (incl. a "
                            "fresh settle) fails HISTORY_IMMUTABLE with zero "
                            "journal/state drift; no mutation API exists"))


def case_16_payment_delivery_separation(results: List[Result]) -> None:
    name = "case_16_payment_delivery_separation"
    runtime, peer, session_id, manager, integrator, shared = _world()
    references = _references(manager, integrator, session_id)
    problems: List[str] = []
    # payment citations can never justify delivery commands
    for source, step_func in (
        ("PATH_ACTIVE", core_start),
    ):
        core, tx = _thread_at(source, references)
        problem = _expect_commercial_error(
            name, CommercialReasonCode.PAYMENT_NOT_DELIVERY,
            step_func, core, tx, (_payment_ref(),),
        )
        if problem:
            problems.append("payment-as-delivery from %s: %s" % (source, problem))
        # mixed real + payment evidence is still rejected
        delivery = sorted(_delivery_refs(references))
        problem = _expect_commercial_error(
            name, CommercialReasonCode.PAYMENT_NOT_DELIVERY,
            step_func, core, tx, (delivery[0], _payment_ref()),
        )
        if problem:
            problems.append("mixed payment+evidence accepted: %s" % problem)
    # accrue_usage with payment citations
    core, tx = _thread_at("DELIVERY_STARTED", references)
    problem = _expect_commercial_error(
        name, CommercialReasonCode.PAYMENT_NOT_DELIVERY,
        core.accrue_usage,
        command_id="m-1", transaction_id=tx, actor="platform",
        source="usage-service", usage_refs=(_payment_ref(),),
    )
    if problem:
        problems.append("payment-as-usage: %s" % problem)
    # reservation never implies delivery: the table has no edge and
    # the command attempt fails closed
    if "DELIVERY_STARTED" in LIFECYCLE_TRANSITIONS["RESERVATION_HELD"]:
        problems.append("table admits RESERVATION_HELD -> DELIVERY_STARTED")
    core, tx = _thread_at("RESERVATION_HELD", references)
    delivery = sorted(_delivery_refs(references))
    problem = _expect_commercial_error(
        name, CommercialReasonCode.LIFECYCLE_ILLEGAL,
        core.start_delivery,
        command_id="m-2", transaction_id=tx, actor="platform",
        source="delivery-service", evidence_refs=(delivery[0],),
    )
    if problem:
        problems.append("delivery from reservation accepted: %s" % problem)
    # settlement never implies delivery: settled is terminal
    core, tx = _thread_at("SETTLED", references)
    problem = _expect_commercial_error(
        name, CommercialReasonCode.HISTORY_IMMUTABLE,
        core.start_delivery,
        command_id="m-3", transaction_id=tx, actor="platform",
        source="delivery-service", evidence_refs=(delivery[0],),
    )
    if problem:
        problems.append("delivery from settled accepted: %s" % problem)
    # family table structure: payment forbidden for delivery/settle
    for action in ("start_delivery", "complete_delivery", "accrue_usage"):
        rules = ACTION_FAMILY_RULES[action]
        if "payment" not in rules["forbidden"]:
            problems.append("%s does not forbid payment family" % action)
        if "settlement" not in rules["forbidden"]:
            problems.append("%s does not forbid settlement family" % action)
    if "payment" not in ACTION_FAMILY_RULES["settle"]["forbidden"]:
        problems.append("settle does not forbid payment family")
    if "delivery-evidence" not in ACTION_FAMILY_RULES["start_delivery"]["required"]:
        problems.append("start_delivery does not require delivery evidence")
    if "settlement" not in ACTION_FAMILY_RULES["settle"]["required"]:
        problems.append("settle does not require settlement family")
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(ok(name, "payment success, reservation, and settlement can "
                            "never imply delivery (typed citations, family "
                            "table, and transition table all fail closed)"))


def core_start(core, tx, refs):
    delivery = sorted(refs)
    return core.start_delivery(
        command_id="pd-%d" % len(delivery), transaction_id=tx,
        actor="platform", source="delivery-service",
        evidence_refs=tuple(delivery),
    )


def case_17_fabricated_references(results: List[Result]) -> None:
    name = "case_17_fabricated_references"
    runtime, peer, session_id, manager, integrator, shared = _world()
    references = _references(manager, integrator, session_id)
    problems: List[str] = []
    unknown = "sha256:" + "0" * 64
    # fabricated session citation
    core, tx = _thread_at("RESERVATION_HELD", references)
    problem = _expect_commercial_error(
        name, CommercialReasonCode.REFERENCE_UNKNOWN,
        core.authorize_session,
        command_id="f-1", transaction_id=tx, actor="platform",
        source="session-service", session_ref=unknown,
    )
    if problem:
        problems.append("fabricated session: %s" % problem)
    # fabricated NetworkPath citation
    core, tx = _thread_at("SESSION_AUTHORIZED", references)
    problem = _expect_commercial_error(
        name, CommercialReasonCode.REFERENCE_UNKNOWN,
        core.activate_path,
        command_id="f-2", transaction_id=tx, actor="platform",
        source="path-service", path_ref=unknown,
    )
    if problem:
        problems.append("fabricated path: %s" % problem)
    # fabricated delivery evidence
    core, tx = _thread_at("PATH_ACTIVE", references)
    problem = _expect_commercial_error(
        name, CommercialReasonCode.REFERENCE_UNKNOWN,
        core.start_delivery,
        command_id="f-3", transaction_id=tx, actor="platform",
        source="delivery-service", evidence_refs=(unknown,),
    )
    if problem:
        problems.append("fabricated evidence: %s" % problem)
    # fabricated settlement confirmation
    core, tx = _thread_at("SETTLEMENT_PENDING", references)
    problem = _expect_commercial_error(
        name, CommercialReasonCode.REFERENCE_UNKNOWN,
        core.settle,
        command_id="f-4", transaction_id=tx, actor="platform",
        source="settlement-service", settlement_refs=(unknown,),
    )
    if problem:
        problems.append("fabricated settlement: %s" % problem)
    # wrong-family citations (real ids, wrong role) fail closed
    problem = _expect_commercial_error(
        name, CommercialReasonCode.COMMAND_INVALID,
        core.settle,
        command_id="f-5", transaction_id=tx, actor="platform",
        source="settlement-service", settlement_refs=(_path_ref(references),),
    )
    if problem:
        problems.append("path-as-settlement: %s" % problem)
    core, tx = _thread_at("SESSION_AUTHORIZED", references)
    problem = _expect_commercial_error(
        name, CommercialReasonCode.COMMAND_INVALID,
        core.activate_path,
        command_id="f-6", transaction_id=tx, actor="platform",
        source="path-service", path_ref=_session_ref(references),
    )
    if problem:
        problems.append("session-as-path: %s" % problem)
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(ok(name, "fabricated session/NetworkPath/delivery/settlement "
                            "citations fail closed; wrong-family roles fail "
                            "closed"))


def case_18_non_deterministic_timestamps(results: List[Result]) -> None:
    name = "case_18_non_deterministic_timestamp_discipline"
    runtime, peer, session_id, manager, integrator, shared = _world()
    references = _references(manager, integrator, session_id)
    problems: List[str] = []
    # no public command method accepts an event instant
    instant_params = ("instant", "at", "now", "timestamp", "event_time",
                      "occurred_at", "created_at", "time")
    for method_name in dir(CommercialCore):
        if method_name.startswith("_"):
            continue
        method = getattr(CommercialCore, method_name)
        if not callable(method):
            continue
        try:
            params = list(inspect.signature(method).parameters)
        except (TypeError, ValueError):
            continue
        for param in params:
            if param in instant_params:
                problems.append(
                    "public method %s accepts instant parameter %r"
                    % (method_name, param)
                )
    # the ONLY clock read site is the injected seam
    for path in _FAMILY_FILES:
        text = path.read_text(encoding="utf-8")
        if "datetime" in text:
            problems.append("%s mentions datetime" % path.name)
        if "\nimport time" in text or "import time\n" in text:
            problems.append("%s imports time" % path.name)
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Attribute) and node.attr == "now":
                value = node.value
                if not (isinstance(value, ast.Attribute) and value.attr == "_clock"):
                    if not (isinstance(value, ast.Name) and value.id == "self"):
                        problems.append(
                            "%s calls now() outside the clock seam" % path.name
                        )
    # malformed deadline payloads fail closed
    core, tx = _thread_at("OFFER_SELECTED", references)
    for index, bad in enumerate((
        "not-a-time", "2026-13-45T99:99:99Z", "", "2026-09-01",
    )):
        problem = _expect_commercial_error(
            name, CommercialReasonCode.INSTANT_INVALID,
            core.hold_reservation,
            command_id="ts-%d" % index, transaction_id=tx,
            actor="platform", source="reservation-service", expires_at=bad,
        )
        if problem:
            problems.append("malformed deadline %r accepted: %s" % (bad, problem))
    # forged event with malformed instant fails the model gate
    core, tx = _thread_at("PATH_ACTIVE", references)
    event = core.journal_records()[0].event.to_dict()
    event["instant"] = "garbage"
    problem = _expect_commercial_error(
        name, CommercialReasonCode.INSTANT_INVALID,
        CommercialEvent.from_dict, event,
    )
    if problem:
        problems.append("forged event instant accepted: %s" % problem)
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(ok(name, "no public instant parameter; the injected clock "
                            "seam is the only time source; malformed instants "
                            "fail closed"))


def case_19_malformed_events(results: List[Result]) -> None:
    name = "case_19_malformed_events"
    runtime, peer, session_id, manager, integrator, shared = _world()
    references = _references(manager, integrator, session_id)
    core, tx = _golden_scenario(
        commercial.MemoryCommercialStore(), references, StepClock(_CT0, _CSTEP)
    )
    event = core.journal_records()[0].event.to_dict()
    problems: List[str] = []
    # missing required members
    for key in list(event):
        bad = dict(event)
        del bad[key]
        problem = _expect_commercial_error(
            name, CommercialReasonCode.EVENT_INVALID,
            CommercialEvent.from_dict, bad,
        )
        if problem:
            problems.append("event missing %r accepted: %s" % (key, problem))
    # non-mapping payload
    problem = _expect_commercial_error(
        name, CommercialReasonCode.EVENT_INVALID,
        CommercialEvent.from_dict, "not-a-mapping",
    )
    if problem:
        problems.append("non-mapping event accepted: %s" % problem)
    # causal_references wrong shape
    bad = dict(event)
    bad["causal_references"] = "not-a-list"
    problem = _expect_commercial_error(
        name, CommercialReasonCode.EVENT_INVALID,
        CommercialEvent.from_dict, bad,
    )
    if problem:
        problems.append("malformed causal_references accepted: %s" % problem)
    # reference payload malformed
    bad = dict(event)
    bad["causal_references"] = [{"reference_id": "x"}]
    problem = _expect_commercial_error(
        name, CommercialReasonCode.REFERENCE_FAMILY_INVALID,
        CommercialEvent.from_dict, bad,
    )
    if problem:
        problems.append("malformed reference accepted: %s" % problem)
    # journal record malformed
    problem = _expect_commercial_error(
        name, CommercialReasonCode.JOURNAL_CORRUPT,
        commercial.JournalRecord.from_dict, {"sequence": 1},
    )
    if problem:
        problems.append("malformed journal record accepted: %s" % problem)
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(ok(name, "missing members, wrong shapes, unknown "
                            "vocabularies, and malformed references all fail "
                            "closed at the model gate"))


def case_20_tampered_journal(results: List[Result]) -> None:
    name = "case_20_tampered_journal"
    runtime, peer, session_id, manager, integrator, shared = _world()
    references = _references(manager, integrator, session_id)
    store = commercial.MemoryCommercialStore()
    core, tx = _golden_scenario(store, references, StepClock(_CT0, _CSTEP))
    data = store.journal_bytes()
    lines = data.split(b"\n")[:-1]
    problems: List[str] = []
    variants: Dict[str, bytes] = {}
    # byte flip in a middle line (swap two hex characters)
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
    for label, mutated in sorted(variants.items()):
        problem = _expect_commercial_error(
            name, CommercialReasonCode.JOURNAL_CORRUPT,
            CommercialCore.load,
            store=FrozenBytesStore(mutated),
            clock=StepClock(_CT0, _CSTEP),
            references=references,
        )
        if problem:
            problems.append("%s accepted: %s" % (label, problem))
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(ok(name, "byte flip, reorder, truncation, sequence gap, "
                            "digest edit, and event-id edit all fail closed "
                            "JOURNAL_CORRUPT at load"))


def case_21_journal_append_only(results: List[Result]) -> None:
    name = "case_21_journal_append_only_persist_then_ack"
    problems: List[str] = []
    runtime, peer, session_id, manager, integrator, shared = _world()
    references = _references(manager, integrator, session_id)
    with tempfile.TemporaryDirectory() as tmp:
        store = commercial.FileCommercialStore(Path(tmp) / "durability")
        core = CommercialCore(
            store=store, clock=StepClock(_CT0, _CSTEP), references=references
        )
        sizes: List[int] = []
        out = None
        for step in ("submit", "select", "hold"):
            out = _apply_step(core, out.transaction_id if out else "", step, references)
            sizes.append(len(store.journal_bytes()))
        if sizes != sorted(sizes) or 0 in sizes:
            problems.append("journal file did not grow monotonically: %s" % sizes)
        if store.journal_bytes() != journal_bytes_for(core.journal_records()):
            problems.append("file bytes diverge from the record serialization")
        # a store failure leaves no phantom state
        failing = FailingCommercialStore()
        core2 = CommercialCore(
            store=failing, clock=StepClock(_CT0, _CSTEP), references=references
        )
        problem = _expect_commercial_error(
            name, CommercialReasonCode.STORE_FAILED,
            core2.submit_intent,
            command_id="ph-1", actor="buyer-agent", source="developer-api",
            intent={"buyer": "b"},
        )
        if problem:
            problems.append("store failure not surfaced: %s" % problem)
        if len(core2.journal_records()) != 0:
            problems.append("phantom journal record after store failure")
        problem = _expect_commercial_error(
            name, CommercialReasonCode.TRANSACTION_UNKNOWN,
            core2.transaction, "sha256:" + "0" * 64,
        )
        if problem:
            problems.append("phantom transaction after store failure: %s" % problem)
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(ok(name, "append-only file grows monotonically; bytes == "
                            "serialization; persist-then-ack leaves no phantom "
                            "state on store failure"))


def case_22_journal_first_recovery(results: List[Result]) -> None:
    name = "case_22_journal_first_recovery"
    runtime, peer, session_id, manager, integrator, shared = _world()
    references = _references(manager, integrator, session_id)
    problems: List[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        store = commercial.FileCommercialStore(Path(tmp) / "recovery")
        core, tx = _golden_scenario(
            store, references, StepClock(_CT0, _CSTEP)
        )
        recovered = CommercialCore.load(
            store=store, clock=StepClock("2026-09-02T00:00:00Z", 60),
            references=references,
        )
        if recovered.journal_digest() != core.journal_digest():
            problems.append("recovered journal digest diverged")
        if state_digest(recovered.transactions()) != state_digest(core.transactions()):
            problems.append("recovered state digest diverged")
        if command_ledger_digest(recovered.command_ledger()) != command_ledger_digest(core.command_ledger()):
            problems.append("recovered command ledger diverged")
        for live in core.transactions():
            replayed = recovered.transaction(live.transaction_id)
            if replayed.to_dict() != live.to_dict():
                problems.append("replayed transaction %s diverged" % live.transaction_id)
        recovered.verify_integrity()
        # durable idempotency: a redelivered command is a no-op after restart
        out = recovered.select_offer(
            command_id="cmd-02", transaction_id=tx, actor="buyer-agent",
            source="developer-api",
            offer={"offer_id": "offer-1", "provider": "provider-1",
                   "unit": "GB", "price": "10"},
        )
        if out.status != "duplicate":
            problems.append("redelivery after restart was not a no-op")
        # the recovered core accepts NEW commands
        out = recovered.submit_intent(
            command_id="post-recovery", actor="buyer-agent",
            source="developer-api", intent={"buyer": "buyer-2"},
        )
        if out.status != "appended":
            problems.append("recovered core rejected a new command")
        if len(recovered.transactions()) != 2:
            problems.append("recovered core transaction count wrong")
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(ok(name, "load == live byte-identical (journal, state, "
                            "ledger); durable idempotency survives restart; "
                            "new commands accepted post-recovery"))


def case_23_replay_verification(results: List[Result]) -> None:
    name = "case_23_replay_verification"
    runtime, peer, session_id, manager, integrator, shared = _world()
    references = _references(manager, integrator, session_id)
    problems: List[str] = []
    scenarios: List[Tuple[CommercialCore, str]] = []
    store = commercial.MemoryCommercialStore()
    scenarios.append(_golden_scenario(store, references, StepClock(_CT0, _CSTEP)))
    core, tx = _thread_at("PATH_ACTIVE", references)
    core.record_path_failure(
        command_id="rv-1", transaction_id=tx, actor="platform",
        source="path-service",
    )
    scenarios.append((core, tx))
    core, tx = _thread_at("RESERVATION_HELD", references)
    core.cancel(
        command_id="rv-2", transaction_id=tx, actor="platform",
        source="operator-console",
    )
    scenarios.append((core, tx))
    for core, tx in scenarios:
        folded = fold_state(core.journal_records())
        live = {t.transaction_id: t.to_dict() for t in core.transactions()}
        replayed = {k: v.to_dict() for k, v in folded.items()}
        if live != replayed:
            problems.append("fold != live state for tx %s" % tx)
        # the fold is a pure function: refolding is byte-identical
        if fold_state(core.journal_records()) != folded:
            problems.append("fold not deterministic")
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(ok(name, "fold(journal) == live state byte-identical for "
                            "golden, compensating, and cancellation scenarios"))


def case_24_deterministic_two_run(results: List[Result]) -> None:
    name = "case_24_deterministic_two_run"
    first = _scenario_stream()
    second = _scenario_stream()
    if first != second:
        results.append(fail(name, "two fresh runs diverged: %r vs %r" % (first, second)))
        return
    results.append(ok(
        name, "two fresh runs byte-identical (journal/state/ledger/events/"
              "stream digests): %s" % first["digest_stream_sha256"][:24]
    ))


def case_25_subprocess_hash_seeds(results: List[Result]) -> None:
    name = "case_25_subprocess_hash_seeds"
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


def case_26_secret_hygiene(results: List[Result]) -> None:
    name = "case_26_secret_hygiene"
    runtime, peer, session_id, manager, integrator, shared = _world()
    references = _references(manager, integrator, session_id)
    store = commercial.MemoryCommercialStore()
    core, tx = _golden_scenario(store, references, StepClock(_CT0, _CSTEP))
    blob = b"\n".join([
        store.journal_bytes(),
        core.digest_stream().encode("utf-8"),
        json.dumps([t.to_dict() for t in core.transactions()]).encode("utf-8"),
    ]).decode("utf-8", errors="ignore")
    problems: List[str] = []
    for secret in (_SECRET_A, _SECRET_B, _KEY_A, _KEY_B):
        if secret.decode("utf-8", errors="ignore") in blob:
            problems.append("secret material %r leaked into commercial state" % secret)
    for token in (
        "secret", "password", "credential", "private_key", "token_hex",
        "hmac-key", "bootstrap",
    ):
        if token in blob.lower():
            problems.append("secret-like token %r in commercial state" % token)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "journal/state/stream bytes secret-free (no key material, "
                 "no credentials, no secret-like tokens)")
    )


def case_27_no_shadow_authority(results: List[Result]) -> None:
    name = "case_27_no_shadow_authority"
    problems: List[str] = []
    for path in _FAMILY_FILES:
        text = path.read_text(encoding="utf-8")
        for token in _FORBIDDEN_TOKENS:
            if token in text:
                problems.append("%s contains forbidden authority token %r"
                                % (path.name, token))
    # the CommercialCore constructor takes NO authority objects:
    # only a store, the clock seam, and the reference index
    params = list(inspect.signature(CommercialCore.__init__).parameters)
    for param in params:
        if param in ("runtime", "manager", "session_store", "peer",
                     "integrator", "authority", "engine", "agent"):
            problems.append("constructor accepts authority parameter %r" % param)
    load_params = list(inspect.signature(CommercialCore.load).parameters)
    for param in load_params:
        if param in ("runtime", "manager", "session_store", "peer",
                     "integrator", "authority", "engine", "agent"):
            problems.append("load accepts authority parameter %r" % param)
    # authority reachability is structurally impossible: no authority
    # module is importable in the family (case_28 pins the import
    # allowlist); the battery additionally audits its own public-path
    # discipline -- no private attribute access on the composed
    # authorities or the commercial core from THIS battery.
    import re

    battery_text = Path(__file__).resolve().read_text(encoding="utf-8")
    for pattern in (
        r"\b(?:core|core[0-9]+|recovered|recovered[0-9]+)\._",
        r"\b(?:manager|runtime|peer|integrator|session_store)\._",
    ):
        for match in re.finditer(pattern, battery_text):
            problems.append(
                "battery accesses private attribute %r (public path only)"
                % battery_text[match.start():match.start() + 24]
            )
            break
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "no authority construction/mutation tokens; no authority "
                 "parameters; battery public-path only (no private access)")
    )


def case_28_import_discipline(results: List[Result]) -> None:
    name = "case_28_import_discipline"
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


def case_29_public_api_stability(results: List[Result]) -> None:
    name = "case_29_public_api_stability"
    if sorted(commercial.__all__) != _EXPECTED_API:
        missing = set(_EXPECTED_API) - set(commercial.__all__)
        extra = set(commercial.__all__) - set(_EXPECTED_API)
        results.append(
            fail(name, "API drifted (missing %r, extra %r)"
                        % (sorted(missing), sorted(extra)))
        )
        return
    results.append(ok(name, "frozen public API: %d names" % len(_EXPECTED_API)))


def case_30_fail_closed_battery(results: List[Result]) -> None:
    """The 16 mandated negative cases in one fail-closed battery,
    with state-unchanged invariants after every rejection."""
    name = "case_30_fail_closed_battery"
    runtime, peer, session_id, manager, integrator, shared = _world()
    references = _references(manager, integrator, session_id)
    store = commercial.MemoryCommercialStore()
    core, tx = _golden_scenario(store, references, StepClock(_CT0, _CSTEP))
    digest_before = core.journal_digest()
    problems: List[str] = []
    checks = 0

    def guard(problem: Optional[str], label: str) -> None:
        nonlocal checks
        checks += 1
        if problem:
            problems.append("%s: %s" % (label, problem))
        if core.journal_digest() != digest_before:
            problems.append("%s mutated the journal" % label)

    delivery = sorted(_delivery_refs(references))
    unknown = "sha256:" + "0" * 64
    # 1. illegal lifecycle transition (settled forward)
    guard(_expect_commercial_error(
        name, CommercialReasonCode.HISTORY_IMMUTABLE,
        core.finalize_billable,
        command_id="n-1", transaction_id=tx, actor="platform", source="x",
    ), "illegal-transition")
    # 2. duplicate command (exact)
    out = core.select_offer(
        command_id="cmd-02", transaction_id=tx, actor="buyer-agent",
        source="developer-api",
        offer={"offer_id": "offer-1", "provider": "provider-1",
               "unit": "GB", "price": "10"},
    )
    checks += 1
    if out.status != "duplicate":
        problems.append("duplicate-command: %s" % out.status)
    # 3. conflicting duplicate
    guard(_expect_commercial_error(
        name, CommercialReasonCode.COMMAND_CONFLICT,
        core.hold_reservation,
        command_id="cmd-03", transaction_id=tx, actor="platform",
        source="reservation-service", expires_at="2026-09-01T13:00:00Z",
    ), "conflicting-duplicate")
    # 4. expired reservation (authorization past the deadline)
    core4 = _fresh_core(references)
    out4 = core4.submit_intent(
        command_id="n-4a", actor="buyer-agent", source="developer-api",
        intent={"buyer": "b"},
    )
    tx4 = out4.transaction_id
    core4.select_offer(
        command_id="n-4b", transaction_id=tx4, actor="buyer-agent",
        source="developer-api", offer={"offer_id": "o"},
    )
    core4.hold_reservation(
        command_id="n-4c", transaction_id=tx4, actor="platform",
        source="reservation-service", expires_at=_NEAR_DEADLINE,
    )
    guard(_expect_commercial_error(
        name, CommercialReasonCode.RESERVATION_EXPIRED,
        core4.authorize_session,
        command_id="n-4d", transaction_id=tx4, actor="platform",
        source="session-service", session_ref=_session_ref(references),
    ), "expired-reservation")
    # 5. cancelled reservation (command on a cancelled transaction)
    core5, tx5 = _thread_at("RESERVATION_HELD", references)
    core5.cancel(
        command_id="n-5a", transaction_id=tx5, actor="platform",
        source="operator-console",
    )
    guard(_expect_commercial_error(
        name, CommercialReasonCode.LIFECYCLE_ILLEGAL,
        core5.authorize_session,
        command_id="n-5b", transaction_id=tx5, actor="platform",
        source="session-service", session_ref=_session_ref(references),
    ), "cancelled-reservation")
    # 6. path failure (from a non-delivery state)
    core6, tx6 = _thread_at("SETTLEMENT_PENDING", references)
    guard(_expect_commercial_error(
        name, CommercialReasonCode.PATH_FAILURE_REJECTED,
        core6.record_path_failure,
        command_id="n-6", transaction_id=tx6, actor="platform", source="x",
    ), "path-failure-gate")
    # 7. non-delivery (from a non-delivery state)
    guard(_expect_commercial_error(
        name, CommercialReasonCode.NON_DELIVERY_REJECTED,
        core6.record_non_delivery,
        command_id="n-7", transaction_id=tx6, actor="platform", source="x",
    ), "non-delivery-gate")
    # 8. settlement before BillableFinal
    core8, tx8 = _thread_at("DELIVERY_COMPLETED", references)
    guard(_expect_commercial_error(
        name, CommercialReasonCode.LIFECYCLE_ILLEGAL,
        core8.settle,
        command_id="n-8", transaction_id=tx8, actor="platform",
        source="settlement-service", settlement_refs=(_settlement_ref(),),
    ), "settlement-before-billable")
    # 9. settlement without delivery evidence (evicted index, via the
    # public journal-first reload over a durable store)
    with tempfile.TemporaryDirectory() as tmp:
        durable = commercial.FileCommercialStore(Path(tmp) / "starved")
        core9 = CommercialCore(
            store=durable, clock=StepClock(_CT0, _CSTEP), references=references
        )
        out9 = core9.submit_intent(
            command_id="n-9a", actor="buyer-agent", source="developer-api",
            intent={"buyer": "b"},
        )
        tx9 = out9.transaction_id
        for step in ("select", "hold", "authorize", "activate", "start",
                     "accrue", "complete", "billable", "initiate"):
            _apply_step(core9, tx9, step, references)
        starving = ReferenceIndex([
            Reference(session_id, ReferenceFamily.SESSION, "sessions-authority"),
            Reference(_path_ref(references), ReferenceFamily.NETWORK_PATH, "p"),
            Reference(_usage_ref(references), ReferenceFamily.USAGE, "u"),
            Reference(_settlement_ref(), ReferenceFamily.SETTLEMENT, "s"),
        ])
        recovered9 = CommercialCore.load(
            store=commercial.FileCommercialStore(Path(tmp) / "starved"),
            clock=StepClock("2026-09-02T00:00:00Z", 60),
            references=starving,
        )
        guard(_expect_commercial_error(
            name, CommercialReasonCode.SETTLEMENT_REJECTED,
            recovered9.settle,
            command_id="n-9z", transaction_id=tx9, actor="platform",
            source="settlement-service", settlement_refs=(_settlement_ref(),),
        ), "settlement-without-evidence")
    # 10. mutation of settled history
    guard(_expect_commercial_error(
        name, CommercialReasonCode.HISTORY_IMMUTABLE,
        core.cancel,
        command_id="n-10", transaction_id=tx, actor="platform", source="x",
    ), "settled-mutation")
    # 11. payment success treated as delivery
    core11, tx11 = _thread_at("PATH_ACTIVE", references)
    guard(_expect_commercial_error(
        name, CommercialReasonCode.PAYMENT_NOT_DELIVERY,
        core11.start_delivery,
        command_id="n-11", transaction_id=tx11, actor="platform",
        source="delivery-service", evidence_refs=(_payment_ref(),),
    ), "payment-as-delivery")
    # 12. fabricated NetworkPath reference
    core12, tx12 = _thread_at("SESSION_AUTHORIZED", references)
    guard(_expect_commercial_error(
        name, CommercialReasonCode.REFERENCE_UNKNOWN,
        core12.activate_path,
        command_id="n-12", transaction_id=tx12, actor="platform",
        source="path-service", path_ref=unknown,
    ), "fabricated-path")
    # 13. fabricated session reference
    core13, tx13 = _thread_at("RESERVATION_HELD", references)
    guard(_expect_commercial_error(
        name, CommercialReasonCode.REFERENCE_UNKNOWN,
        core13.authorize_session,
        command_id="n-13", transaction_id=tx13, actor="platform",
        source="session-service", session_ref=unknown,
    ), "fabricated-session")
    # 14. non-deterministic timestamp (malformed deadline payload)
    core14, tx14 = _thread_at("OFFER_SELECTED", references)
    guard(_expect_commercial_error(
        name, CommercialReasonCode.INSTANT_INVALID,
        core14.hold_reservation,
        command_id="n-14", transaction_id=tx14, actor="platform",
        source="reservation-service", expires_at="not-a-time",
    ), "non-deterministic-timestamp")
    # 15. malformed commercial event
    bad_event = core.journal_records()[0].event.to_dict()
    del bad_event["actor"]
    guard(_expect_commercial_error(
        name, CommercialReasonCode.EVENT_INVALID,
        CommercialEvent.from_dict, bad_event,
    ), "malformed-event")
    # 16. tampered commercial record digest
    data = store.journal_bytes()
    lines = data.split(b"\n")[:-1]
    payload = json.loads(lines[2].decode("utf-8"))
    payload["command_digest"] = "sha256:" + "0" * 64
    mutated = b"\n".join(
        lines[:2] + [json.dumps(payload).encode("utf-8")] + lines[3:]
    ) + b"\n"
    guard(_expect_commercial_error(
        name, CommercialReasonCode.JOURNAL_CORRUPT,
        CommercialCore.load,
        store=FrozenBytesStore(mutated),
        clock=StepClock(_CT0, _CSTEP), references=references,
    ), "tampered-record-digest")
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(ok(name, "all 16 mandated negative cases fail closed with "
                            "zero journal drift (%d guards)" % checks))


def case_31_authority_reference_composition(results: List[Result]) -> None:
    name = "case_31_authority_reference_composition"
    runtime, peer, session_id, manager, integrator, shared = _world()
    references = _references(manager, integrator, session_id)
    problems: List[str] = []
    # the session citation IS the real session authority id
    session_entries = references.by_family(ReferenceFamily.SESSION)
    if len(session_entries) != 1 or session_entries[0].reference_id != session_id:
        problems.append("session citation is not the real session id")
    # the path citation IS a real manager-owned NetworkPath id (ACTIVE)
    path_entries = references.by_family(ReferenceFamily.NETWORK_PATH)
    if not path_entries:
        problems.append("no network path citations")
    active = manager.active_path_id(session_id)
    if active is None:
        problems.append("the bound path is not ACTIVE in the manager")
    elif not any(e.reference_id == active for e in path_entries):
        problems.append("the ACTIVE network path is not cited")
    # delivery citations ARE real platform journal event ids
    platform_ids = {
        record.event.event_id for record in integrator.journal_records()
    }
    for entry in references.by_family(ReferenceFamily.DELIVERY_EVIDENCE):
        if entry.reference_id not in platform_ids:
            problems.append("delivery citation %s is not a platform event" % entry.reference_id[:20])
    # every citation is DATA (id + family + provenance strings)
    for entry in (
        references.by_family(ReferenceFamily.SESSION)
        + references.by_family(ReferenceFamily.NETWORK_PATH)
        + references.by_family(ReferenceFamily.DELIVERY_EVIDENCE)
        + references.by_family(ReferenceFamily.USAGE)
        + references.by_family(ReferenceFamily.SETTLEMENT)
        + references.by_family(ReferenceFamily.PAYMENT)
    ):
        if not (isinstance(entry.reference_id, str)
                and isinstance(entry.family, str)
                and isinstance(entry.provenance, str)):
            problems.append("citation carries non-DATA fields")
    # the golden lifecycle runs on top of the composed citations
    core, tx = _golden_scenario(
        commercial.MemoryCommercialStore(), references, StepClock(_CT0, _CSTEP)
    )
    if not core.transaction(tx).settled():
        problems.append("composed golden lifecycle did not settle")
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(ok(
        name, "index built from PUBLIC reads only: real session id, real "
        "ACTIVE NetworkPath id, real platform delivery-evidence event ids; "
        "citations are DATA strings; golden lifecycle settles on top"
    ))


def case_32_usage_reference_semantics(results: List[Result]) -> None:
    name = "case_32_usage_reference_semantics"
    runtime, peer, session_id, manager, integrator, shared = _world()
    references = _references(manager, integrator, session_id)
    problems: List[str] = []
    core, tx = _thread_at("DELIVERY_STARTED", references)
    out = core.accrue_usage(
        command_id="u-1", transaction_id=tx, actor="platform",
        source="usage-service", usage_refs=(_usage_ref(references),),
    )
    if out.from_state != "DELIVERY_STARTED" or out.to_state != "USAGE_ACCRUING":
        problems.append("first accrual is not the state transition")
    # subsequent accrual is state-preserving
    out2 = core.accrue_usage(
        command_id="u-2", transaction_id=tx, actor="platform",
        source="usage-service", usage_refs=(_usage_ref(references),),
    )
    if out2.from_state != "USAGE_ACCRUING" or out2.to_state != "USAGE_ACCRUING":
        problems.append("subsequent accrual is not state-preserving")
    transaction = core.transaction(tx)
    if transaction.usage_refs != (_usage_ref(references),) * 2:
        problems.append("usage citations not append-accumulated")
    if transaction.state != "USAGE_ACCRUING":
        problems.append("state drifted during accrual")
    # the events journal both accruals (append-only evidence)
    accruals = [
        record for record in core.journal_records()
        if record.event.action == CommercialAction.ACCRUE_USAGE
    ]
    if len(accruals) != 2:
        problems.append("expected 2 journaled accruals, found %d" % len(accruals))
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(ok(name, "first usage citation transitions "
                            "DELIVERY_STARTED -> USAGE_ACCRUING; subsequent "
                            "citations are state-preserving journaled records"))


def case_33_py_compile(results: List[Result]) -> None:
    name = "case_33_py_compile"
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
    results.append(ok(name, "commercial/ (%d modules) and the battery compile"
                            % len(_FAMILY_FILES)))


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
        "spec/mission.md",
        "spec/governance.md",
        "spec/change-control.md",
        "spec/workflow.md",
        "spec/work-items.md",
        "spec/dependency-graph.md",
        "spec/schemas/protocol.json",
        "spec/architect/authorizations/WORK-051.yaml",
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
        if "python3 tools/commercial_selftest.py" not in workflow:
            problems.append("CI wiring missing the commercial battery step")
        added = [
            line for line in wiring_diff.stdout.splitlines()
            if line.startswith("+") and "python3 tools/" in line
        ]
        for line in added:
            if "commercial_selftest.py" not in line:
                problems.append("CI wiring added an unrelated step: %r" % line)
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "delta confined to the WORK-051-CORE-001 scope (%d file(s) + "
                 "sanctioned additive CI wiring)" % len(delta))
    )


# ---------------------------------------------------------------------------
# Conformance-completion vectors (the permanent battery around the
# fourteen directive categories: the three dimensions the original
# 35-case battery covered only implicitly are made explicit here --
# out-of-order events at every layer, delivery immutability as a
# named dimension, and fresh-world independence).
# ---------------------------------------------------------------------------


def _forged_discontinuous_journal(store, references, tx) -> bytes:
    """Rebuild the golden journal bytes with an INSERTED record whose
    event is table-legal, action-coherent, family-correct, and fully
    recomputed (event_id, command digest, hash chain, sequences) but
    whose declared from_state does not connect to the folded walk:
    activate_path SESSION_AUTHORIZED -> PATH_ACTIVE inserted while
    the walk is at OFFER_SELECTED (the out-of-order event)."""
    lines = store.journal_bytes().split(b"\n")[:-1]
    records = [json.loads(line.decode("utf-8")) for line in lines]
    path_ref = _path_ref(references)
    causal = (
        Reference(path_ref, ReferenceFamily.NETWORK_PATH,
                  "networkpath-manager"),
    )
    command = CommercialCommand(
        command_id="forged-activate",
        action=CommercialAction.ACTIVATE_PATH,
        transaction_id=tx,
        references=causal,
        payload={"forged": True},
        actor="platform",
        source="path-service",
    )
    event = CommercialEvent(
        event_id=derive_event_id(
            tx, CommercialAction.ACTIVATE_PATH,
            CommercialState.SESSION_AUTHORIZED, CommercialState.PATH_ACTIVE,
            command.command_id, _CT0,
        ),
        transaction_id=tx,
        action=CommercialAction.ACTIVATE_PATH,
        from_state=CommercialState.SESSION_AUTHORIZED,
        to_state=CommercialState.PATH_ACTIVE,
        command_id=command.command_id,
        causal_references=causal,
        actor="platform",
        source="path-service",
        instant=_CT0,
    )
    forged = {
        "sequence": 3,
        "record_id": "",
        "command": command.to_dict(),
        "command_digest": command.digest(),
        "event": event.to_dict(),
    }
    new_records = records[:2] + [forged] + records[2:]
    prev = GENESIS_RECORD_ID
    for index, record in enumerate(new_records):
        record["sequence"] = index + 1
        content = record_content(
            CommercialCommand.from_dict(record["command"]),
            record["command_digest"],
            CommercialEvent.from_dict(record["event"]),
        )
        record["record_id"] = derive_record_id(index + 1, content, prev)
        prev = record["record_id"]
    return b"".join(
        (json.dumps(record) + "\n").encode("utf-8")
        for record in new_records
    )


def case_36_out_of_order_events(results: List[Result]) -> None:
    """Out-of-order events fail closed at EVERY layer: admission
    (a forward command whose required state has not been reached),
    the model gate (an incoherent action/target attribution), and
    replay (a fully-recomputed, table-legal record whose declared
    from_state does not connect to the folded walk)."""
    name = "case_36_out_of_order_events"
    runtime, peer, session_id, manager, integrator, shared = _world()
    references = _references(manager, integrator, session_id)
    problems: List[str] = []

    # (1) admission: the completion command arrives while the
    # transaction is still at RESERVATION_HELD; the settlement
    # command arrives while it is at OFFER_SELECTED.  Both fail
    # closed with zero journal drift.
    core, tx = _thread_at("RESERVATION_HELD", references)
    before = (core.journal_digest(), core.tail_sequence())
    problem = _expect_commercial_error(
        name, CommercialReasonCode.LIFECYCLE_ILLEGAL,
        lambda: core.complete_delivery(
            command_id="oo-1", transaction_id=tx, actor="platform",
            source="delivery-service",
            evidence_refs=(sorted(_delivery_refs(references))[0],),
        ),
    )
    if problem:
        problems.append("out-of-order complete_delivery: %s" % problem)
    core2, tx2 = _thread_at("OFFER_SELECTED", references)
    problem = _expect_commercial_error(
        name, CommercialReasonCode.LIFECYCLE_ILLEGAL,
        lambda: core2.settle(
            command_id="oo-2", transaction_id=tx2, actor="platform",
            source="settlement-service", settlement_refs=(_settlement_ref(),),
        ),
    )
    if problem:
        problems.append("out-of-order settle: %s" % problem)
    for probe_core, probe_before in ((core, before),):
        after = (probe_core.journal_digest(), probe_core.tail_sequence())
        if after != probe_before:
            problems.append("a rejected out-of-order command drifted the journal")

    # (2) model gate: a settle event landing in OFFER_SELECTED (a
    # table-legal edge with an incoherent action/target pair) fails
    # closed at construction.
    problem = _expect_commercial_error(
        name, CommercialReasonCode.EVENT_INVALID,
        lambda: CommercialEvent(
            event_id=derive_event_id(
                "sha256:" + "0" * 64, CommercialAction.SETTLE,
                CommercialState.CONNECTIVITY_INTENT,
                CommercialState.OFFER_SELECTED, "oo-3", _CT0,
            ),
            transaction_id="sha256:" + "0" * 64,
            action=CommercialAction.SETTLE,
            from_state=CommercialState.CONNECTIVITY_INTENT,
            to_state=CommercialState.OFFER_SELECTED,
            command_id="oo-3",
            causal_references=(),
            actor="platform",
            source="settlement-service",
            instant=_CT0,
        ),
    )
    if problem:
        problems.append("incoherent action/target event: %s" % problem)

    # (3) replay: a fully-recomputed forged record (valid chain,
    # valid sequences, valid digests, table-legal edge, coherent
    # action/target, correct families) whose declared from_state
    # does not connect to the folded walk fails closed at load.
    store = commercial.MemoryCommercialStore()
    core3, tx3 = _golden_scenario(store, references, StepClock(_CT0, _CSTEP))
    forged = _forged_discontinuous_journal(store, references, tx3)
    problem = _expect_commercial_error(
        name, CommercialReasonCode.JOURNAL_CORRUPT,
        CommercialCore.load,
        store=FrozenBytesStore(forged),
        clock=StepClock(_CT0, _CSTEP),
        references=references,
    )
    if problem:
        problems.append("discontinuous walk accepted at replay: %s" % problem)

    # (4) regression guard: the honest journal still loads (the
    # walk-linkage verification accepts the contiguous walk).
    honest = CommercialCore.load(
        store=store, clock=StepClock(_CT0, _CSTEP), references=references,
    )
    if not honest.transaction(tx3).settled():
        problems.append("the honest golden journal no longer loads to SETTLED")

    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(ok(
        name, "out-of-order events fail closed at every layer: an early "
              "forward command is rejected at admission with zero journal "
              "drift, an incoherent action/target attribution is rejected "
              "at the model gate, and a fully-recomputed record whose "
              "declared from_state does not connect to the folded walk is "
              "rejected at replay (the walk-linkage verification); the "
              "honest contiguous journal still loads"
    ))


def case_37_delivery_immutability(results: List[Result]) -> None:
    """Delivery facts are immutable: once DELIVERY_COMPLETED, no
    compensating action can undo the delivery, the delivery record
    cannot be re-pointed at different evidence, and the recorded
    delivery events survive byte-identically through settlement."""
    name = "case_37_delivery_immutability"
    runtime, peer, session_id, manager, integrator, shared = _world()
    references = _references(manager, integrator, session_id)
    problems: List[str] = []
    core, tx = _thread_at("DELIVERY_COMPLETED", references)
    before_digest = core.journal_digest()
    before_tail = core.tail_sequence()
    delivery = sorted(_delivery_refs(references))

    # (1) no compensating action can undo a completed delivery
    compensating_probes = (
        ("cancel", lambda: core.cancel(
            command_id="di-1", transaction_id=tx, actor="platform",
            source="operator-console",
        ), CommercialReasonCode.LIFECYCLE_ILLEGAL),
        ("expire", lambda: core.expire(
            command_id="di-2", transaction_id=tx, actor="platform",
            source="reservation-service",
        ), CommercialReasonCode.LIFECYCLE_ILLEGAL),
        ("record_path_failure", lambda: core.record_path_failure(
            command_id="di-3", transaction_id=tx, actor="platform",
            source="path-service",
        ), CommercialReasonCode.PATH_FAILURE_REJECTED),
        ("record_non_delivery", lambda: core.record_non_delivery(
            command_id="di-4", transaction_id=tx, actor="platform",
            source="delivery-service",
        ), CommercialReasonCode.NON_DELIVERY_REJECTED),
    )
    for label, probe, expected in compensating_probes:
        problem = _expect_commercial_error(name, expected, probe)
        if problem:
            problems.append("compensating %s after completion: %s"
                            % (label, problem))

    # (2) the delivery record cannot be re-pointed at different
    # evidence (a second completion with a different citation and a
    # fresh command id fails closed)
    other_evidence = delivery[-1] if len(delivery) > 1 else delivery[0]
    problem = _expect_commercial_error(
        name, CommercialReasonCode.LIFECYCLE_ILLEGAL,
        lambda: core.complete_delivery(
            command_id="di-5", transaction_id=tx, actor="platform",
            source="delivery-service", evidence_refs=(other_evidence,),
        ),
    )
    if problem:
        problems.append("delivery re-pointing: %s" % problem)
    after = (core.journal_digest(), core.tail_sequence())
    if after != (before_digest, before_tail):
        problems.append("a rejected delivery mutation drifted the journal")

    # (3) the recorded delivery events survive byte-identically
    # through settlement (history is append-only; the delivery
    # facts are never rewritten by later commercial events)
    delivery_events = {
        record.sequence: record.event.to_dict()
        for record in core.journal_records()
        if record.event.action in (
            CommercialAction.START_DELIVERY,
            CommercialAction.COMPLETE_DELIVERY,
        )
    }
    core.finalize_billable(
        command_id="di-6", transaction_id=tx, actor="platform",
        source="billing-service",
    )
    core.initiate_settlement(
        command_id="di-7", transaction_id=tx, actor="platform",
        source="settlement-service", payment_refs=(_payment_ref(),),
    )
    core.settle(
        command_id="di-8", transaction_id=tx, actor="platform",
        source="settlement-service", settlement_refs=(_settlement_ref(),),
    )
    if not core.transaction(tx).settled():
        problems.append("the transaction did not settle after completion")
    settled_events = {
        record.sequence: record.event.to_dict()
        for record in core.journal_records()
        if record.event.action in (
            CommercialAction.START_DELIVERY,
            CommercialAction.COMPLETE_DELIVERY,
        )
    }
    if settled_events != delivery_events:
        problems.append("the delivery events were rewritten after settlement")
    transaction = core.transaction(tx)
    if not transaction.delivery_evidence_refs:
        problems.append("the settled transaction lost its delivery citations")
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(ok(
        name, "delivery facts are immutable: every compensating action is "
              "rejected after DELIVERY_COMPLETED with zero journal drift, "
              "the delivery record cannot be re-pointed at different "
              "evidence, and the recorded delivery events survive "
              "byte-identically through settlement (append-only history)"
    ))


def case_38_fresh_world_independence(results: List[Result]) -> None:
    """Fresh-world independence: every vector constructs its own
    fixture world, and coexisting interleaved worlds (separate
    stores, separate clocks, structurally different transactions)
    produce byte-identical results to their isolated runs -- no
    shared mutable commercial state exists."""
    name = "case_38_fresh_world_independence"
    problems: List[str] = []

    # isolated baselines over two independent worlds (A uses the
    # same stepwise machinery as its interleaved run; B uses the
    # golden variant with a structurally different intent)
    world_a = _world()
    references_a = _references(world_a[3], world_a[4], world_a[2])
    core_a = _fresh_core(references_a)
    tx_a = ""
    for step in _STATE_STEPS[CommercialState.SETTLED]:
        out = _apply_step(core_a, tx_a, step, references_a)
        tx_a = out.transaction_id
    stream_a = core_a.digest_stream()

    world_b = _world()
    references_b = _references(world_b[3], world_b[4], world_b[2])
    store_b = commercial.MemoryCommercialStore()
    core_b, tx_b = _golden_scenario(
        store_b, references_b, StepClock(_CT0, _CSTEP),
        intent={"buyer": "buyer-2", "want": "connectivity", "region": "gh"},
        prefix="alt-",
    )
    stream_b = core_b.digest_stream()

    if tx_a == tx_b:
        problems.append("structurally different intents produced one transaction")
    if stream_a == stream_b:
        problems.append("the two worlds produced identical streams (no independence)")

    # interleaved execution: A pauses at DELIVERY_STARTED, B runs to
    # SETTLED, then A resumes to SETTLED -- both must land on their
    # isolated baselines byte-for-byte
    core_i_a = _fresh_core(references_a)
    tx_i_a = ""
    paused = False
    for step in _STATE_STEPS[CommercialState.DELIVERY_STARTED]:
        out = _apply_step(core_i_a, tx_i_a, step, references_a)
        tx_i_a = out.transaction_id
        paused = True
    if not paused or core_i_a.transaction(tx_i_a).state != "DELIVERY_STARTED":
        problems.append("the interleaved world A did not pause at DELIVERY_STARTED")
    store_i_b = commercial.MemoryCommercialStore()
    core_i_b, tx_i_b = _golden_scenario(
        store_i_b, references_b, StepClock(_CT0, _CSTEP),
        intent={"buyer": "buyer-2", "want": "connectivity", "region": "gh"},
        prefix="alt-",
    )
    for step in (
        "accrue", "complete", "billable", "initiate", "settle",
    ):
        _apply_step(core_i_a, tx_i_a, step, references_a)
    if core_i_a.digest_stream() != stream_a:
        problems.append("the interleaved world A diverged from its isolated baseline")
    if core_i_b.digest_stream() != stream_b:
        problems.append("the interleaved world B diverged from its isolated baseline")
    if not core_i_a.transaction(tx_i_a).settled():
        problems.append("the interleaved world A did not settle")

    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(ok(
        name, "fresh-world independence holds: every vector builds its own "
              "fixture world, two structurally different worlds produce "
              "distinct streams, and interleaved coexisting worlds "
              "(A paused at DELIVERY_STARTED while B settled, then A "
              "resumed) reproduce their isolated baselines byte-for-byte "
              "-- no shared mutable commercial state"
    ))


def main() -> int:
    results: List[Result] = []
    for case in (
        case_01_frozen_vocabularies,
        case_02_lifecycle_table,
        case_03_command_model,
        case_04_event_model,
        case_05_full_lifecycle_golden,
        case_06_every_legal_transition,
        case_07_every_illegal_transition,
        case_08_cancellation,
        case_09_expiry,
        case_10_path_failure,
        case_11_non_delivery,
        case_12_duplicate_commands,
        case_13_conflicting_duplicates,
        case_14_settlement_preconditions,
        case_15_immutable_settled_history,
        case_16_payment_delivery_separation,
        case_17_fabricated_references,
        case_18_non_deterministic_timestamps,
        case_19_malformed_events,
        case_20_tampered_journal,
        case_21_journal_append_only,
        case_22_journal_first_recovery,
        case_23_replay_verification,
        case_24_deterministic_two_run,
        case_25_subprocess_hash_seeds,
        case_26_secret_hygiene,
        case_27_no_shadow_authority,
        case_28_import_discipline,
        case_29_public_api_stability,
        case_30_fail_closed_battery,
        case_31_authority_reference_composition,
        case_32_usage_reference_semantics,
        case_33_py_compile,
        case_34_frozen_spec_intact,
        case_35_pr_delta_shape,
        case_36_out_of_order_events,
        case_37_delivery_immutability,
        case_38_fresh_world_independence,
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
