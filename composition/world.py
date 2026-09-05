"""WORK-054 composed conformance world.

One deterministic, fully composed fixture over the ACCEPTED
authorities' public constructors and seams -- the W032
``ConformanceWorld`` precedent applied to the system composition
chain.  The world holds and constructs ONLY existing authority
objects (it creates no authority of its own):

- the W033 agent seam: two ``AgentRuntime`` peers, an ESTABLISHED
  transport session, the W041 ``NetworkPathManager``, and the
  W042 ``PlatformIntegrator`` journal carrying the delivery-plane
  metering time series;
- the W045 ``EligibilityAuthority`` with its registered provider/
  offer/policy/capability records;
- the W050 ``PlatformCapabilityRegistry`` (a DECLARATION surface
  -- never containment enforcement);
- the W047 ``MarketplaceService`` with its listing index, the
  eligibility view built from the W045 authority's public reads,
  and the W044 payment capability declarations;
- the W051 ``CommercialCore`` with the caller-built
  ``ReferenceIndex`` (public reads only);
- the W012 ``SessionStore`` logical session created through the
  genuine W011 ``RoutingEngine`` and W010 ``PolicyDecision``;
- the W049 ``ClientRuntime`` + ``ComposedGateway`` over the
  composed authorities (with NO sharing runtime wired -- the W048
  absence surfaces fail closed at this boundary by design).

The usage/allocation/payment authorities are constructed
mid-scenario by the orchestrator (their injected snapshots are
caller-built from the CURRENT public reads at each construction
point, exactly as their own contracts require).

Determinism: every clock is a ``StepClock`` with a frozen epoch;
every secret/key/external id is a fixed battery constant; every
identity is derived through the genuine machinery.  Identical
worlds are byte-identical in all public digests.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Tuple

from protocol.canonicalization import canonical_json_bytes

from agent import (
    AgentConfig,
    AgentIdentitySpec,
    AgentRuntime,
    InterfaceSnapshot,
    LinkMetricSpec,
    MigrationSpec,
    StaticInterfaceSource,
    StepClock,
)
from agent.clock import AgentClock

from identity.node_id import parse_node_id
from identity.model import NodeIdentity
from identity.profiles import ProfileSet

from management import ManagementCapability, RoleDefinition
from mobile.model import (
    MobilePhase,
    NetworkKind,
    PlatformSnapshot,
    PowerState,
)
from policy import PolicyDomain, PolicyRule
from topology import (
    ClaimType,
    SourceClass,
    TopologyClaim,
    make_link_subject,
)

from platform.journal import MemoryPlatformStore
from platform.lifecycle import PlatformIntegrator

from networkpath import NetworkPathManager

from policy.model import PolicyDecision
from resources import ResourceStore
from routing import (
    LinkMetrics,
    RouteDecision,
    RoutingContext,
    RoutingEngine,
)
from sessions import SessionStore
from topology import TopologyGraph

from commercial import (
    CommercialCore,
    Reference,
    ReferenceFamily,
    ReferenceIndex,
)
from usage import (
    CommercialTransactionSnapshot,
    DeliveryEvidence,
    EvidenceKind,
    QuantityClass,
    UsageEvidenceIndex,
    UsageLedger,
)
from usage.journal import MemoryUsageStore
from allocation import (
    AllocationEvidenceIndex,
    AllocationLedger,
    BillableUsageSnapshot,
    ExternalReferenceSnapshot,
    ReferenceKind,
)
from allocation.journal import MemoryAllocationStore

from payment import (
    CommercialCitation,
    CitationFamily,
    CommercialSnapshot,
    ProviderCapabilities,
)
from payment.journal import MemoryPaymentStore
from payment.lifecycle import SettlementGateway
from payment.sandbox import SandboxProvider

from eligibility import (
    EligibilityAuthority,
    JurisdictionPolicy,
    OfferEligibilityRecord,
    ProviderSharingCapabilities,
    ProviderTrustRecord,
)
from eligibility.journal import MemoryEligibilityStore
from eligibility.evidence import AuthoritySnapshot

from marketplace import (
    MarketplaceIndex,
    MarketplaceOffer,
    MarketplaceService,
    RankingPolicy,
    EligibilityView,
)
from marketplace.model import AdvertisedQuality, CapacityObservation
from marketplace.proximity import declare_coverage_cell

from platformcaps import (
    PlatformCapabilityRegistry,
    evaluate_sharing_compatibility,
)
from platformcaps.model import (
    IsolationPrimitive,
    LeaseEnforcementCapability,
    MeteringCapability,
    PlatformIdentity,
    PlatformProfile,
    RoleCapability,
    SharingModeDeclaration,
)
from containment.state import CapabilityState as _DeclarationState

from client import (
    ClientContext,
    ClientRuntime,
    ComposedGateway,
    SandboxPlatformAdapter,
)

# ---------------------------------------------------------------------------
# Frozen deterministic battery constants
# ---------------------------------------------------------------------------

_T0 = "2025-06-01T00:00:00Z"
_FRESH = "2026-06-01T00:00:00Z"
_SECRET_A = b"w054-battery-secret-A"
_SECRET_B = b"w054-battery-secret-B"
_PROFILE_ID = "identity.sha256-hmac-dev.v1"
_KEY_A = b"w054-battery-key-A"
_KEY_B = b"w054-battery-key-B"

#: The delivery-plane metering time series on the ACTIVE path
#: interface (cumulative rx/tx counters read through the platform
#: journal's public surface): 12:01 -> 120 total, 12:05 -> 330,
#: 12:10 -> 480.  Consecutive-delta window deltas: [12:01,12:05] = 210,
#: [12:05,12:10] = 150 (the caller-side public-read derivation).
_W1 = "2026-09-01T12:01:00Z"
_W2 = "2026-09-01T12:05:00Z"
_W3 = "2026-09-01T12:10:00Z"
WIFI_IF = "wlan0"
ETH_IF = "eth0"
USB_IF = "usb0"
CELL_IF = "vpn0"

#: The marketplace / eligibility evaluation epoch (the discovery
#: and decision instants; the reservation deadline anchors on the
#: proposal instant, never a fresh clock read).
_MKT_T0 = "2026-09-01T11:00:00Z"

#: The marketplace discovery epoch (AFTER the W045 registry
#: registrations and evaluations: discovery consults the
#: authority's live records at a later instant).
_MKT_DISCOVER_T0 = "2026-09-01T12:00:00Z"

#: The W051 commercial clock epoch/step.
_CORE_T0 = "2026-09-01T11:30:00Z"
_CORE_STEP = 60

#: The W052 usage ledger epoch/step.
_USAGE_T0 = "2026-09-01T13:00:00Z"
_USAGE_STEP = 60

#: The W053 allocation ledger epoch/step.
_ALLOC_T0 = "2026-10-01T09:00:00Z"
_ALLOC_STEP = 60

#: The W044 payment gateway epoch/step and the sandbox provider
#: clock epoch/step.
_PAY_T0 = "2026-11-01T09:00:00Z"
_PAY_STEP = 60
_PROV_T0 = "2026-11-01T08:00:00Z"
_PROV_STEP = 60

#: The W012 logical-session fixture instants.
_SESSION_T0 = "2026-09-01T11:15:00Z"

#: The listing terms: per-megabyte billing, 3 whole-currency
#: units per decimal megabyte -> the derived byte tariff is
#: exactly 3 micro-units per byte (integer arithmetic only).
_OFFER_CURRENCY = "USD"
_OFFER_PRICE_MINOR = 3
_OFFER_PRICE_EXPONENT = 0
_BILLING_MODE = "per-megabyte"
_BYTES_PER_MEGABYTE = 1_000_000
_MICROS_PER_UNIT = 1_000_000

#: The W053 economic policy terms: ADCOS 15%, provider share
#: bounded to [30%, 70%], half-up rounding, USD micro precision,
#: effective calendar 2026.
_POLICY_LABEL = "w054-standard-2026"
_POLICY_ADCOS_BPS = 1500
_POLICY_MIN_BPS = 3000
_POLICY_MAX_BPS = 7000
_POLICY_ROUNDING = "half-up"
_POLICY_CURRENCY = "USD"
_POLICY_DIGITS = 6
_POLICY_FROM = "2026-01-01T00:00:00Z"
_POLICY_UNTIL = "2027-01-01T00:00:00Z"
_POLICY_PROVIDER_BPS = 5000

#: The sandbox payment provider identity.
_PROVIDER_ID = "provider-1"
_PROV_SECRET = b"w054-battery-provider-secret"
_SANDBOX_PLATFORM = "w054-sandbox-platform"

#: The deterministic node ids (derived through the genuine
#: identity machinery).
_PROFILE_CACHE: Dict[str, Tuple[str, str]] = {}


def _ids() -> Tuple[str, str]:
    if "ids" not in _PROFILE_CACHE:
        profiles = ProfileSet.load_default()
        profile = profiles.get(_PROFILE_ID)
        identity_a = NodeIdentity.create(profile, _KEY_A, _T0)
        identity_b = NodeIdentity.create(profile, _KEY_B, _T0)
        _PROFILE_CACHE["ids"] = (
            identity_a.node_id.text,
            identity_b.node_id.text,
        )
    return _PROFILE_CACHE["ids"]


def _external_id(kind: str, label: str) -> str:
    """A deterministic well-formed EXTERNAL-plane id."""
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes({"kind": kind, "label": label})
    ).hexdigest()


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
            role_id="w054-battery-operator",
            capabilities=(
                ManagementCapability.SESSION_READ,
                ManagementCapability.SESSION_CONTROL,
                ManagementCapability.POLICY_READ,
            ),
            description="operator role (battery fixture)",
        ),
    )


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


def _config(
    label: str = "w054-node",
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
    return _config("w054-peer-node", key=_KEY_B, peer_id=id_a, self_id=id_b)


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


def _snapshots(eth_down: bool = False) -> Tuple[InterfaceSnapshot, ...]:
    return (
        _snap(name=WIFI_IF, kind="wireless", addresses=("fd00::a:1",)),
        _snap(
            name=ETH_IF, kind="ethernet", addresses=("fd00::a:2",),
            speed=1000, up=not eth_down,
        ),
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
    runtime: AgentRuntime, peer: AgentRuntime
) -> str:
    """The ordinary public production session handshake."""
    request = runtime.establish_session(peer.node_id)
    accept = peer.accept_session(request)
    confirm = runtime.complete_session(accept)
    peer.finalize_session(confirm)
    return confirm.session_id


def _advertised(ref: str) -> AdvertisedQuality:
    return AdvertisedQuality(
        latency_ms=20, throughput_kbps=50_000, availability_percent=99,
        advertisement_ref=ref,
    )


def _capacity_obs(
    observed_at: str = _MKT_T0, confidence: int = 80,
    load_kbps: int = 5000, ref: str = "load-1",
) -> CapacityObservation:
    return CapacityObservation(
        observed_at=observed_at, provenance="provider-telemetry",
        confidence=confidence, load_kbps=load_kbps, observation_ref=ref,
    )


def _listing(
    *,
    offer_id: str,
    provider_id: str,
    interface_name: str,
    link_kind: str,
    price_minor: int = _OFFER_PRICE_MINOR,
) -> MarketplaceOffer:
    return MarketplaceOffer(
        offer_id=offer_id, schema_version=1,
        provider_id=provider_id, jurisdiction="gh",
        network_sharing_mode="tether", access_type="wifi",
        metered=True, currency=_OFFER_CURRENCY, price_minor=price_minor,
        price_exponent=_OFFER_PRICE_EXPONENT, billing_mode=_BILLING_MODE,
        valid_from="2026-01-01T00:00:00Z", valid_until="2027-01-01T00:00:00Z",
        interface_name=interface_name, link_kind=link_kind,
        advertised=_advertised("adv-%s" % offer_id),
        quality_observations=(),
        declared_capacity_kbps=50000,
        capacity_observations=(
            _capacity_obs(ref="cap-%s" % offer_id),
        ),
        coverage=(
            declare_coverage_cell(5_603_000, -13_000, "district-2500m"),
        ),
        provenance="provider-registry",
    )


def _payment_capabilities() -> ProviderCapabilities:
    """The W044 payment capability declaration for the fixture
    provider (a DATA declaration consumed by the W047 payment
    gate)."""
    return ProviderCapabilities(
        provider_id=_PROVIDER_ID, schema_version=1,
        supports_authorization=True, supports_capture=True,
        supports_refund=True, supports_partial_refund=True,
        supports_reversal=True, supports_payout_transfer=True,
        supports_callbacks=True, supports_status_query=True,
        currencies=(_OFFER_CURRENCY,),
        max_exponent=2, max_amount=100_000,
    )


def _sandbox_capabilities() -> ProviderCapabilities:
    """The sandbox provider's journaled capability declaration
    (micro precision: the usage statement amount is in micro
    units, and the payment boundary cites it at exponent 6)."""
    return ProviderCapabilities(
        provider_id=_PROVIDER_ID, schema_version=1,
        supports_authorization=True, supports_capture=True,
        supports_refund=True, supports_partial_refund=True,
        supports_reversal=True, supports_payout_transfer=True,
        supports_callbacks=True, supports_status_query=True,
        currencies=(_OFFER_CURRENCY,),
        max_exponent=6, max_amount=10_000_000_000,
    )


def derive_tariff(offer: Dict[str, Any]) -> Tuple[int, str, str]:
    """Derive the usage tariff from the W051 public offer read.

    The caller-side, public-read-only derivation: a per-megabyte
    listing price of ``price_minor`` units at exponent
    ``price_exponent`` means ``price_minor * 10^(6 - exponent)``
    micro-units per decimal megabyte, i.e. exactly
    ``price_minor * 10^(6 - exponent) / 10^6`` micro-units per
    byte (integer division is exact for every sane listing; a
    non-integer or unsupported tariff fails closed).
    """
    if not isinstance(offer, dict):
        raise ValueError("the commercial offer record must be a mapping")
    billing_mode = offer.get("billing_mode", "")
    if billing_mode != _BILLING_MODE:
        raise ValueError(
            "unsupported billing mode %r (only %r is derivable to a byte "
            "tariff)" % (billing_mode, _BILLING_MODE)
        )
    price_minor = offer.get("price_minor")
    exponent = offer.get("price_exponent")
    if not isinstance(price_minor, int) or isinstance(price_minor, bool):
        raise ValueError("price_minor must be an integer")
    if not isinstance(exponent, int) or isinstance(exponent, bool):
        raise ValueError("price_exponent must be an integer")
    if exponent < 0 or exponent > 6:
        raise ValueError("price_exponent %r is outside the derivable range" % exponent)
    # price_minor units at exponent e are price_minor * 10^(6-e)
    # micro-units per (decimal) megabyte:
    micros_per_megabyte = price_minor * (10 ** (6 - exponent))
    if micros_per_megabyte % _BYTES_PER_MEGABYTE != 0:
        raise ValueError(
            "the per-megabyte price does not divide into an integer "
            "per-byte tariff (price_minor=%r, exponent=%r)"
            % (price_minor, exponent)
        )
    unit_price_micros = micros_per_megabyte // _BYTES_PER_MEGABYTE
    return (
        unit_price_micros,
        "byte",
        "commercial-core-public-read",
    )


# ---------------------------------------------------------------------------
# Public-read snapshot builders (the caller-side composition seams)
# ---------------------------------------------------------------------------


def build_reference_index(
    manager: NetworkPathManager,
    integrator: PlatformIntegrator,
    session_id: str,
) -> ReferenceIndex:
    """Build the W051 ReferenceIndex from PUBLIC reads only (the
    W051 composition precedent)."""
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
            _external_id("settlement-confirmation", "w054-settle-1"),
            ReferenceFamily.SETTLEMENT,
            "external-settlement-confirmation",
        )
    )
    entries.append(
        Reference(
            _external_id("payment-observation", "w054-payment-1"),
            ReferenceFamily.PAYMENT,
            "external-payment-observation",
        )
    )
    return ReferenceIndex(entries)


def build_delivery_evidence(
    integrator: PlatformIntegrator,
    transaction_id: str,
) -> Tuple[DeliveryEvidence, ...]:
    """Derive the authoritative delivery evidence-window records from
    the platform journal's PUBLIC reads: consecutive cumulative
    counter deltas on the active path interface (the caller-side,
    public-read-only metering derivation, transaction-tagged so
    distinct transactions cite distinct evidence identities)."""
    events = tuple(
        record.event
        for record in integrator.journal_records()
        if record.event.kind == "interface-observation"
        and record.event.platform_ref == WIFI_IF
    )
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


def build_usage_evidence_index(
    core: CommercialCore,
    integrator: PlatformIntegrator,
    transaction_ids: Tuple[str, ...],
    *,
    extra_evidence: Tuple[DeliveryEvidence, ...] = (),
) -> UsageEvidenceIndex:
    """Build the injected W052 UsageEvidenceIndex from PUBLIC
    reads only: the delivery evidence-window records per transaction and
    the commercial transaction snapshots (state + tariff derived
    from the core's own journaled offer record)."""
    evidence: List[DeliveryEvidence] = []
    for transaction_id in transaction_ids:
        evidence.extend(build_delivery_evidence(integrator, transaction_id))
    evidence.extend(extra_evidence)
    snapshots: List[CommercialTransactionSnapshot] = []
    for transaction_id in transaction_ids:
        transaction = core.transaction(transaction_id)
        offer = transaction.offer
        if not isinstance(offer, dict):
            raise ValueError(
                "transaction %s carries no offer record (public read)"
                % transaction_id
            )
        unit_price_micros, billable_unit, provenance = derive_tariff(offer)
        snapshots.append(
            CommercialTransactionSnapshot(
                transaction_id=transaction_id,
                commercial_state=transaction.state,
                unit_price_micros=unit_price_micros,
                billable_unit=billable_unit,
                tariff_provenance=provenance,
            )
        )
    return UsageEvidenceIndex(evidence=evidence, transactions=snapshots)


def build_allocation_evidence_index(
    usage_ledger: UsageLedger,
    transaction_ids: Tuple[str, ...],
    *,
    settlement_labels: Tuple[str, ...] = ("w054-settle-1",),
    payment_labels: Tuple[str, ...] = ("w054-payment-1", "w054-payment-2"),
) -> AllocationEvidenceIndex:
    """Build the injected W053 AllocationEvidenceIndex from PUBLIC
    reads only: the W052 usage projections (state + sealed
    statement + compensation DATA, read through the UsageLedger
    public surface) and the external settlement/payment reference
    citations."""
    usage: List[BillableUsageSnapshot] = []
    for transaction_id in transaction_ids:
        projection = usage_ledger.transaction(transaction_id)
        statement = projection.statement
        if statement is None:
            usage.append(
                BillableUsageSnapshot(
                    usage_transaction_id=transaction_id,
                    usage_state=projection.state,
                )
            )
        else:
            usage.append(
                BillableUsageSnapshot(
                    usage_transaction_id=transaction_id,
                    usage_state=projection.state,
                    gross_amount_micros=statement.amount_micros,
                    statement_id=statement.statement_id,
                    billable_quantity=statement.billable_quantity,
                    unit_price_micros=statement.unit_price_micros,
                    billable_unit=statement.billable_unit,
                    tariff_provenance=statement.tariff_provenance,
                    refunded_amount_micros=projection.refunded_amount_micros(),
                    reversed_amount_micros=projection.reversed_amount_micros(),
                    disputed=projection.disputed(),
                    sealed_at=statement.sealed_at,
                )
            )
    references: List[ExternalReferenceSnapshot] = []
    for label in settlement_labels:
        references.append(
            ExternalReferenceSnapshot(
                _external_id("settlement-confirmation", label),
                ReferenceKind.SETTLEMENT,
                "external-settlement-plane",
                transaction_ids[0] if transaction_ids else None,
            )
        )
    for label in payment_labels:
        references.append(
            ExternalReferenceSnapshot(
                _external_id("payment-observation", label),
                ReferenceKind.PAYMENT,
                "external-payment-plane",
                transaction_ids[0] if transaction_ids else None,
            )
        )
    return AllocationEvidenceIndex(usage=usage, references=references)


def build_payment_snapshot(
    core: CommercialCore,
    usage_ledger: UsageLedger,
    allocation_ledger: Optional[AllocationLedger],
    transaction_ids: Tuple[str, ...],
) -> CommercialSnapshot:
    """Build the injected W044 CommercialSnapshot from PUBLIC
    reads only: WORK-051 transaction projections, WORK-052 usage
    finality records (the sealed statement identity once final),
    and WORK-053 allocation accounts with their public split
    DATA."""
    entries: List[CommercialCitation] = []
    for transaction_id in transaction_ids:
        transaction = core.transaction(transaction_id)
        entries.append(
            CommercialCitation(
                reference_id=transaction_id,
                family=CitationFamily.COMMERCIAL,
                provenance="commercial-core",
                commercial_state=transaction.state,
            )
        )
    for transaction_id in transaction_ids:
        projection = usage_ledger.transaction(transaction_id)
        statement = projection.statement
        if statement is None:
            entries.append(
                CommercialCitation(
                    reference_id=transaction_id,
                    family=CitationFamily.USAGE_FINAL,
                    provenance="usage-ledger",
                    transaction_id=transaction_id,
                    usage_state=projection.state,
                )
            )
        else:
            entries.append(
                CommercialCitation(
                    reference_id=statement.statement_id,
                    family=CitationFamily.USAGE_FINAL,
                    provenance="usage-ledger",
                    transaction_id=transaction_id,
                    usage_state=projection.state,
                    amount=statement.amount_micros,
                    quantity=statement.billable_quantity,
                    unit=statement.billable_unit,
                    finalized_at=statement.sealed_at,
                )
            )
    if allocation_ledger is not None:
        for account in allocation_ledger.allocations():
            snapshot = account.snapshot
            if snapshot is None:
                continue
            entries.append(
                CommercialCitation(
                    reference_id=account.usage_transaction_id,
                    family=CitationFamily.ALLOCATION,
                    provenance="allocation-ledger",
                    transaction_id=transaction_ids[0]
                    if transaction_ids
                    else "",
                    allocation_state=account.state,
                    billable_amount=snapshot.gross_micros,
                    currency=snapshot.currency,
                    exponent=snapshot.minor_unit_digits,
                    developer_amount=snapshot.developer_share_micros,
                    provider_amount=snapshot.provider_share_micros,
                    adc_os_amount=snapshot.adcos_share_micros,
                    tax_amount=snapshot.tax_micros,
                )
            )
    return CommercialSnapshot(entries)


# ---------------------------------------------------------------------------
# The composed world
# ---------------------------------------------------------------------------


class CompositionWorld:
    """The deterministic composed fixture over the accepted
    authorities' public constructors and seams.

    Every member is an authority-owned object; the world owns no
    state of its own (all cross-authority inputs are immutable
    caller-built snapshots derived from public reads).
    """

    def __init__(self, *, eth_down: bool = False) -> None:
        snapshots = _snapshots(eth_down=eth_down)
        self.shared_clock = StepClock(_T0, 60)
        self.peer = AgentRuntime(
            _peer_config(), clock=self.shared_clock,
            interface_source=StaticInterfaceSource(snapshots),
        )
        self.peer.boot(_SECRET_B)
        self.peer.expose_interfaces()
        self.runtime = AgentRuntime(
            _config(), clock=self.shared_clock,
            interface_source=StaticInterfaceSource(snapshots),
        )
        self.runtime.boot(_SECRET_A)
        self.runtime.expose_interfaces()
        _register_peers(self.runtime, self.peer, self.shared_clock)
        self.transport_session_id = _establish_session(
            self.runtime, self.peer
        )
        self.manager = NetworkPathManager(self.runtime, self.shared_clock)
        # one observation cycle: the W041 candidates exist (the
        # chain validates the selected candidate later, through
        # the sanctioned W047 handoff seam)
        self.manager.discover()

        self.platform_store = MemoryPlatformStore()
        self.integrator = PlatformIntegrator(
            store=self.platform_store, clock=self.shared_clock,
        )
        self.integrator.ingest_platform_state(
            _platform_snapshot(), observed_at=self.shared_clock.now()
        )
        self.integrator.ingest_interface_observation(
            _snap(
                name=WIFI_IF, kind="wireless",
                addresses=("fd00::a:1",), rx=100, tx=20,
            ),
            observed_at=_W1,
        )
        self.integrator.ingest_interface_observation(
            _snap(
                name=WIFI_IF, kind="wireless",
                addresses=("fd00::a:1",), rx=280, tx=50,
            ),
            observed_at=_W2,
        )
        self.integrator.ingest_interface_observation(
            _snap(
                name=WIFI_IF, kind="wireless",
                addresses=("fd00::a:1",), rx=400, tx=80,
            ),
            observed_at=_W3,
        )
        self.integrator.ingest_interface_observation(
            _snap(name=ETH_IF, kind="ethernet", addresses=("fd00::a:2",), rx=11, tx=5),
            observed_at=_W1,
        )

        # the W045 eligibility authority with the fixture records
        self.eligibility = EligibilityAuthority(
            store=MemoryEligibilityStore(),
            clock=StepClock(_MKT_T0, 60),
            snapshot=AuthoritySnapshot(()),
        )
        self._register_eligibility()

        # the W050 declaration registry (never containment
        # enforcement)
        self.capability_registry = self._build_capability_registry()

        # the W047 marketplace service over the listing index, the
        # W045 public-read eligibility view, and the W044 payment
        # capability declarations
        self.listing_index = MarketplaceIndex(
            (
                _listing(
                    offer_id="wifi-basic", provider_id=_PROVIDER_ID,
                    interface_name=WIFI_IF, link_kind="wireless",
                ),
                _listing(
                    offer_id="eth-basic", provider_id=_PROVIDER_ID,
                    interface_name=ETH_IF, link_kind="ethernet",
                ),
            )
        )
        self.marketplace = MarketplaceService(
            index=self.listing_index,
            clock=StepClock(_MKT_DISCOVER_T0, 60),
            policy=RankingPolicy(),
            eligibility=self._eligibility_view(),
            payment_capabilities=(_payment_capabilities(),),
        )

        # the W051 commercial core over the caller-built
        # reference index (public reads only)
        self.reference_index = build_reference_index(
            self.manager, self.integrator, self.transport_session_id
        )
        self.commercial_store = commercial_store()
        self.core = CommercialCore(
            store=self.commercial_store,
            clock=StepClock(_CORE_T0, _CORE_STEP),
            references=self.reference_index,
        )

        # the W012 logical session through the genuine W011 route
        # decision and W010 policy decision
        self.session_store = SessionStore()
        self.logical_session_id = self._create_logical_session()

        # the W049 client runtime over a composed read gateway
        # with NO sharing runtime wired (the W048 absence surfaces
        # fail closed at this boundary)
        self.client_runtime = ClientRuntime(
            context=ClientContext(
                user_ref="w054-buyer-1",
                device_ref="w054-device-1",
                application_ref="w054-application-1",
                platform_id=_SANDBOX_PLATFORM,
            ),
            adapter=SandboxPlatformAdapter(
                platform_id=_SANDBOX_PLATFORM,
                provider_support="supported",
                buyer_support="supported",
                restrictions=(),
                permissions=(
                    "notification", "background-network", "secure-storage",
                ),
            ),
            gateway=ComposedGateway(
                clock=StepClock(_MKT_T0, 60),
                core=self.core,
                paths=self.manager,
            ),
        )

    # -----------------------------------------------------------------
    # Fixture construction helpers (public authority surfaces only)
    # -----------------------------------------------------------------

    def _register_eligibility(self) -> None:
        authority = self.eligibility
        authority.register_provider(
            command_id="w054-elg-01", actor="platform",
            source="provider-registry",
            provider_id=_PROVIDER_ID, jurisdictions=("gh",),
            kyc_reference="w054-kyc-1", provenance="provider-registry",
        )
        authority.declare_capabilities(
            command_id="w054-elg-02", actor="platform",
            source="provider-registry",
            provider_id=_PROVIDER_ID, schema_version=1,
            sharing_modes=("tether",), access_types=("wifi", "ethernet"),
            capabilities=("metering",), supports_metered=True,
            supports_unmetered=False, jurisdictions=("gh",),
            provenance="provider-registry",
        )
        authority.enroll_policy(
            command_id="w054-elg-04", actor="platform",
            source="policy-service",
            jurisdiction="gh", policy_version=1,
            effective_from="2025-01-01T00:00:00Z",
            sharing_modes=("tether",), access_types=("wifi", "ethernet"),
            metering_required=True, required_capabilities=("metering",),
            allowed_platform_families=("sandbox-os",),
            allowed_device_classes=("sandbox-device",),
            payment_prerequisite_required=False, kyc_reference_required=True,
            provenance="policy-service",
        )
        # the provider-subject evaluation confers provider trust
        # 'eligible' (the W045 authority's own semantics: only an
        # evaluation decision confers eligibility)
        authority.evaluate(
            command_id="w054-elg-05", actor="platform",
            source="provider-registry",
            jurisdiction="gh", provider_id=_PROVIDER_ID,
            network_sharing_mode="tether", access_type="wifi",
            valid_until="2027-01-01T00:00:00Z",
        )
        authority.register_offer(
            command_id="w054-elg-03", actor="platform",
            source="provider-registry",
            offer_id="wifi-basic", schema_version=1,
            provider_id=_PROVIDER_ID, jurisdiction="gh",
            network_sharing_mode="tether", access_type="wifi",
            metered=True, valid_from="2026-01-01T00:00:00Z",
            valid_until="2027-01-01T00:00:00Z",
            provenance="provider-registry",
        )
        authority.register_offer(
            command_id="w054-elg-06", actor="platform",
            source="provider-registry",
            offer_id="eth-basic", schema_version=1,
            provider_id=_PROVIDER_ID, jurisdiction="gh",
            network_sharing_mode="tether", access_type="ethernet",
            metered=True, valid_from="2026-01-01T00:00:00Z",
            valid_until="2027-01-01T00:00:00Z",
            provenance="provider-registry",
        )

    def _eligibility_view(self) -> EligibilityView:
        """The W047 eligibility view built from the W045
        authority's PUBLIC reads (the caller-side composition
        seam)."""
        return EligibilityView(
            providers=self.eligibility.providers(),
            offers=self.eligibility.offers(),
            policies=self.eligibility.policies(),
            capabilities=self.eligibility.capability_declarations(),
        )

    def _build_capability_registry(self) -> PlatformCapabilityRegistry:
        """The W050 DECLARATION registry for the fixture platform
        (a 'supported' declaration is a compatibility statement,
        never permission, authorization, or proven enforcement --
        the negative-proof fixture for the containment rule)."""
        identity = PlatformIdentity(
            platform_id=_SANDBOX_PLATFORM,
            os_family="sandbox-os",
            device_class="sandbox-device",
            network_configuration="sandbox-network",
            deployment_mode="sandbox-deployment",
        )
        profile = PlatformProfile(
            identity=identity,
            provider=RoleCapability(
                role="provider",
                state=_DeclarationState.SUPPORTED,
                restrictions=(),
            ),
            buyer=RoleCapability(
                role="buyer",
                state=_DeclarationState.SUPPORTED,
                restrictions=(),
            ),
            sharing_modes=(
                SharingModeDeclaration(
                    sharing_mode="os-level-forwarding",
                    state=_DeclarationState.SUPPORTED,
                    restrictions=(),
                    required_isolation_mechanisms=("netns-nftables",),
                ),
            ),
            isolation_primitives=(
                IsolationPrimitive(
                    mechanism="netns-nftables",
                    state=_DeclarationState.SUPPORTED,
                    minimum_security_properties=("netns-table-isolation",),
                    restrictions=(),
                ),
            ),
            metering=MeteringCapability(
                _DeclarationState.SUPPORTED,
                _DeclarationState.SUPPORTED,
            ),
            lease_enforcement=LeaseEnforcementCapability(
                _DeclarationState.SUPPORTED,
                _DeclarationState.SUPPORTED,
                _DeclarationState.SUPPORTED,
                _DeclarationState.SUPPORTED,
            ),
            constraints=(),
            evidence_references=(),
        )
        return PlatformCapabilityRegistry("1.0", (profile,))

    def _create_logical_session(self) -> str:
        id_a, id_b = _ids()
        policy = _w012_policy_decision()
        route = _w011_route_decision(id_a, id_b, policy)
        result = self.session_store.create(
            route,
            policy,
            source_node_id=id_a,
            destination_node_id=id_b,
            creation_instant=_SESSION_T0,
            intent_digest="",
        )
        if not result.ok:
            raise AssertionError(
                "the W012 logical session fixture failed: %s (%s)"
                % (result.code, result.detail)
            )
        return result.session.session_id

    # -----------------------------------------------------------------
    # Deterministic public digests (the world fingerprint)
    # -----------------------------------------------------------------

    def public_digests(self) -> Dict[str, str]:
        """The deterministic world fingerprint (authority-sourced
        public digests only)."""
        return {
            "transport_session_id": self.transport_session_id,
            "logical_session_id": self.logical_session_id,
            "networkpath_paths": "%d paths" % len(self.manager.paths()),
            "networkpath_content_digest": self.manager.content_digest(),
            "platform_journal_digest": (
                self.integrator.journal_digest()
            ),
            "commercial_reference_count": "%d" % len(self.reference_index),
            "eligibility_journal_digest": (
                self.eligibility.journal_digest()
            ),
            "capability_registry_digest": (
                self.capability_registry.content_digest()
            ),
            "listing_index_digest": self.listing_index.digest(),
        }


def commercial_store():
    """A fresh W051 in-memory store (the battery injects and keeps
    the store for the journal-first recovery proofs)."""
    from commercial.journal import MemoryCommercialStore

    return MemoryCommercialStore()


def usage_store():
    """A fresh W052 in-memory store."""
    return MemoryUsageStore()


def allocation_store():
    """A fresh W053 in-memory store."""
    return MemoryAllocationStore()


def payment_store():
    """A fresh W044 in-memory store."""
    return MemoryPaymentStore()


def sandbox_provider(
    *, capabilities: Optional[ProviderCapabilities] = None,
    clock: Optional[AgentClock] = None,
    secret: bytes = _PROV_SECRET,
) -> SandboxProvider:
    """The sandbox payment provider (the sanctioned W044 adapter
    seam; deterministic scripted outcomes only)."""
    return SandboxProvider(
        capabilities=capabilities or _sandbox_capabilities(),
        secret=secret,
        clock=clock if clock is not None else StepClock(_PROV_T0, _PROV_STEP),
    )


def _w012_policy_decision() -> PolicyDecision:
    """A tamper-evident WORK-010 PolicyDecision fixture (the
    genuine policy model's canonical bytes digest)."""
    decision = PolicyDecision(
        decision_id="0" * 64, effect="allow", code="allow",
        detail="w054 fixture", matched_rule_ids=("w054-r1",),
        policy_set_id="w054-ps-1", policy_set_version=1,
        evaluation_instant=_SESSION_T0,
    )
    digest = hashlib.sha256(decision.canonical_bytes()).hexdigest()
    return PolicyDecision(
        decision_id=digest, effect="allow", code="allow",
        detail="w054 fixture", matched_rule_ids=("w054-r1",),
        policy_set_id="w054-ps-1", policy_set_version=1,
        evaluation_instant=_SESSION_T0,
    )


def _w011_route_decision(
    source: str, destination: str, policy: PolicyDecision
) -> RouteDecision:
    """A genuine WORK-011 route decision produced by the real
    engine (the sessions package itself never invokes it)."""
    graph = TopologyGraph()
    graph.merge(
        TopologyClaim(
            subject=make_link_subject(source, destination),
            reporter=source,
            claim_type=ClaimType.LINK_STATE, value="up",
            source_class=SourceClass.SELF_ADVERTISEMENT,
            issued_at=_T0, freshness_until="2027-01-01T00:00:00Z", sequence=1,
        )
    )
    metrics = {
        make_link_subject(source, destination): LinkMetrics(
            latency_ms=10, loss_basis_points=0, capacity_bps=1_000_000,
            energy_cost_millijoules=100, confidence_basis_points=10_000,
            observed_at=_T0, freshness_until="2027-01-01T00:00:00Z",
        )
    }
    context = RoutingContext(
        source_node_id=source, destination_node_id=destination,
        topology=graph, resources=ResourceStore(),
        evaluation_instant=_SESSION_T0, policy_decision=policy,
        link_metrics=metrics,
    )
    result = RoutingEngine().evaluate(context)
    if result.decision is None or result.decision.selected is None:
        raise AssertionError(
            "the W011 route fixture was not selected: %s" % result.detail
        )
    return result.decision


def evaluate_capability_declaration(
    registry: PlatformCapabilityRegistry,
) -> Dict[str, Any]:
    """Evaluate the W050 capability declaration for the fixture
    platform (the DECLARATION surface: 'supported' is a declared
    compatibility statement, never permission, authorization, or
    proven enforcement)."""
    evaluation = evaluate_sharing_compatibility(
        registry, _SANDBOX_PLATFORM, "provider", "os-level-forwarding",
        ("netns-nftables",),
    )
    return {
        "state": evaluation.state,
        "evidence_class": evaluation.evidence_class,
        "registry_version": evaluation.registry_version,
        "registry_digest": evaluation.registry_digest,
    }
