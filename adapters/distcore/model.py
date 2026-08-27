"""ADCOS distributed-core adapter value model (WORK-024).

Frozen vocabularies, immutable value types, and the deterministic
content-derived identity functions for the distributed-core family.
Mirrors the WORK-022/023 model discipline:

* Every value type is a frozen dataclass whose constructor VALIDATES
  (shape checks through :mod:`adapters.distcore.validation`) and whose
  ``to_dict()`` emits only canonical-JSON-representable primitives.
* Every identity is CONTENT-DERIVED over ``canonical_json_bytes``
  (WORK-003) -- no randomness, no wall clock -- and the constructor of
  every view that CARRIES a derived id re-asserts the derivation
  (tamper-evident content binding, mirroring the WORK-011 Path, the
  WORK-022 binding, and the WORK-023 MeshRouteView/MeshBinding
  disciplines: a tampered or miscomputed id is rejected at
  construction).
* 3GPP reference shapes appear as DATA with citations (TS 23.501
  UPF/N6/PDU-session shapes; TS 23.548 edge/local UPF placement); no
  vendor, daemon, or element-management state is modeled.
* The W024 identity invariant is structural:

      ADCOS session_id != gateway identity != ordinary path identity
        != breakout identity != allocation identity
        != external gateway identifier

  A gateway/provider change mints a NEW ``breakout_ref`` bound to the
  SAME sacred ``session_id``; the boundary NEVER collapses them and
  never mints a new session_id merely because the breakout gateway
  changed (mirrors the WORK-018 route/session, WORK-019 PDU-session,
  WORK-021 association/tunnel, WORK-022 session/bearer, and WORK-023
  session/bearer separations).

Policy determines local vs remote breakout (WORK-024 invariant 2):
the breakout MODE is carried by :class:`BreakoutDecision` -- a DATA
record built from a REAL WORK-010 ``PolicyDecision`` -- and the
family never invents or re-evaluates the determination.  WORK-018
owns ordinary IP semantics; the family composes IP paths (ordinary
WORK-011 ``Path`` objects consumed as DATA) and recreates no
IPv6/NAT/routing primitive.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Tuple

from protocol.canonicalization import canonical_json_bytes

from .errors import DISTCORE_PREFIX, DistCoreError, DistCoreReasonCode
from .validation import (
    assert_ref_session_separation,
    reject_credential_like_text,
    validate_breakout_mode,
    validate_capacity_bps,
    validate_claim_digest,
    validate_evidence_source,
    validate_external_gateway_id,
    validate_gateway_name,
    validate_gateway_role,
    validate_instant,
    validate_locality_label,
    validate_node_id,
    validate_opaque_ref,
    validate_path_ref,
    validate_policy_decision_id,
    validate_session_ref,
)


# --------------------------------------------------------------------------
# Frozen vocabularies
# --------------------------------------------------------------------------


class BreakoutMode:
    """The breakout-mode vocabulary (the policy determination, DATA).

    ``LOCAL`` keeps local traffic local via a local breakout gateway
    (the frozen ``capability.core.local-breakout`` registry id
    classifies the concept).  ``REMOTE`` breaks out via a remote
    gateway/provider behind the WORK-019 5GC/UPF, WORK-021 Wi-Fi, or
    WORK-022 backhaul seams.  Policy (WORK-010) determines the mode;
    the distributed core RECORDS the determination and never invents
    one.
    """

    LOCAL = "local"
    REMOTE = "remote"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.LOCAL, cls.REMOTE)


class GatewayRoleClass:
    """The gateway role-classification vocabulary (registry DATA).

    A gateway is a ROLE, not an identity (WORK-024 invariant 5): the
    same node may host several gateway roles, and no core state
    machine branches on these labels.  ``ip-gateway`` classifies the
    WORK-018 generic IP gateway seam; ``upf`` the WORK-019 5G UPF
    seam (TS 23.501 UPF/N6); ``wifi-gateway`` the WORK-021 non-3GPP
    seam; ``backhaul-gateway`` the WORK-022 backhaul seam.
    """

    IP_GATEWAY = "ip-gateway"
    UPF = "upf"
    WIFI_GATEWAY = "wifi-gateway"
    BACKHAUL_GATEWAY = "backhaul-gateway"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.IP_GATEWAY,
            cls.UPF,
            cls.WIFI_GATEWAY,
            cls.BACKHAUL_GATEWAY,
        )


class GatewayState:
    """The gateway availability vocabulary (provider-owned state)."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    CLOSED = "closed"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.AVAILABLE, cls.UNAVAILABLE, cls.CLOSED)


class BreakoutState:
    """The breakout-binding lifecycle vocabulary.

    ``ACTIVE`` serves traffic; ``SUPERSEDED`` was explicitly replaced
    by a failover transition (the chain is preserved -- gateway
    replacement never rebinds retroactively); ``RELEASED`` was closed
    by the caller.  All three states remain in the manager's
    authoritative history (the explicit transition semantics).
    """

    ACTIVE = "active"
    SUPERSEDED = "superseded"
    RELEASED = "released"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.ACTIVE, cls.SUPERSEDED, cls.RELEASED)


class EvidenceSourceClass:
    """The gateway-evidence provenance vocabulary (DATA mirroring the
    WORK-007 SourceClass and the WORK-023 mesh HopEvidence classes).

    ``direct-observation`` -- a gateway claim the serving node itself
    observed.  ``remote-claim`` -- a claim an upstream node REPORTED
    and this boundary merely carries.  A remote-claim gateway NEVER
    silently becomes direct-observed (provenance preserved, never
    upgraded -- the LOCK-008 discipline applied to breakout
    gateways).
    """

    DIRECT_OBSERVATION = "direct-observation"
    REMOTE_CLAIM = "remote-claim"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.DIRECT_OBSERVATION, cls.REMOTE_CLAIM)


class AllocationState:
    """The breakout-capacity allocation vocabulary."""

    RESERVED = "reserved"
    RELEASED = "released"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.RESERVED, cls.RELEASED)


class LinkMetricName:
    """The generic WORK-016 link-metric vocabulary (DATA; the family
    vocabulary mirrors the SDK vocabulary so observations surface
    directly, mirroring the WORK-022/023 convention).

    Gateway/UPF-specific counters (N4 session reports, NAT table
    occupancy, N6 interface errors) stay INSIDE implementations and
    are reported through these generic measures only.
    """

    LINK_UP = "link-up"
    RX_BYTES_TOTAL = "rx-bytes-total"
    TX_BYTES_TOTAL = "tx-bytes-total"
    RX_ERROR_COUNT = "rx-error-count"
    TX_ERROR_COUNT = "tx-error-count"
    RETRANSMIT_COUNT = "retransmit-count"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.LINK_UP,
            cls.RX_BYTES_TOTAL,
            cls.TX_BYTES_TOTAL,
            cls.RX_ERROR_COUNT,
            cls.TX_ERROR_COUNT,
            cls.RETRANSMIT_COUNT,
        )


# --------------------------------------------------------------------------
# Descriptors, evidence, and views
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class GatewayDescriptor:
    """A breakout gateway descriptor (the registration input).

    ``name`` -- a human label (credential-free); ``gateway_id`` -- an
    integrator-scoped opaque string; ``node_id`` -- the WORK-004 node
    hosting the gateway ROLE (the path/gateway resolution anchor: a
    registered ordinary Path whose destination IS the gateway node
    addresses this gateway); ``role_class`` -- the seam
    classification (registry DATA); ``locality_label`` -- the policy
    locality vocabulary as DATA (e.g. ``village-A``); ``capacity_bps``
    -- the gateway's egress capacity in bits/second (WORK-008 base
    units; 0 ADMITS the gateway but contributes NO allocatable
    capacity -- the WORK-022 zero/unknown port-speed fail-closed
    lesson); ``external_gateway_id`` -- the integration seam
    identifier (an Open5GS UPF instance id, an N3IWF gateway id, a
    vendor element name) carried as OPAQUE DATA and deliberately
    EXCLUDED from the gateway identity content.
    """

    name: str
    gateway_id: str
    node_id: str
    role_class: str
    locality_label: str = ""
    capacity_bps: int = 0
    external_gateway_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "name", validate_gateway_name(self.name)
        )
        if not isinstance(self.gateway_id, str) or not self.gateway_id:
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "gateway_id must be a non-empty string",
            )
        object.__setattr__(self, "node_id", validate_node_id(self.node_id))
        object.__setattr__(
            self, "role_class", validate_gateway_role(self.role_class)
        )
        if self.locality_label:
            object.__setattr__(
                self,
                "locality_label",
                validate_locality_label(self.locality_label),
            )
        else:
            if not isinstance(self.locality_label, str):
                raise DistCoreError(
                    DistCoreReasonCode.INVALID_INPUT,
                    "locality_label must be a string",
                )
        object.__setattr__(
            self, "capacity_bps", validate_capacity_bps(self.capacity_bps)
        )
        if self.external_gateway_id:
            object.__setattr__(
                self,
                "external_gateway_id",
                validate_external_gateway_id(self.external_gateway_id),
            )
        else:
            if not isinstance(self.external_gateway_id, str):
                raise DistCoreError(
                    DistCoreReasonCode.INVALID_INPUT,
                    "external_gateway_id must be a string",
                )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "gateway_id": self.gateway_id,
            "node_id": self.node_id,
            "role_class": self.role_class,
            "locality_label": self.locality_label,
            "capacity_bps": self.capacity_bps,
            "external_gateway_id": self.external_gateway_id,
        }


@dataclass(frozen=True)
class GatewayEvidence:
    """Provenance-bearing evidence for a gateway claim (WORK-024
    invariant 5).

    ``observer_node_id`` -- the node that OBSERVED the gateway claim;
    ``reporter_node_id`` -- WHO reported it to this boundary;
    ``source_class`` -- the provenance class (never upgraded);
    ``observed_at`` -- the injected instant of the observation;
    ``claim_digest`` -- the SHA-256 digest over the CANONICAL gateway
    claim content (validated against the descriptor at registration:
    evidence that does not bind to the claim it vouches for is
    rejected fail-closed with ``GATEWAY_UNEVIDENCED`` -- mirroring
    the WORK-018 GatewayResolver discipline); ``provenance`` -- an
    opaque provenance annotation (DATA).
    """

    observer_node_id: str
    reporter_node_id: str
    source_class: str
    observed_at: str
    claim_digest: str
    provenance: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "observer_node_id", validate_node_id(self.observer_node_id)
        )
        object.__setattr__(
            self, "reporter_node_id", validate_node_id(self.reporter_node_id)
        )
        object.__setattr__(
            self, "source_class", validate_evidence_source(self.source_class)
        )
        object.__setattr__(
            self, "observed_at", validate_instant(self.observed_at)
        )
        object.__setattr__(
            self, "claim_digest", validate_claim_digest(self.claim_digest)
        )
        if not isinstance(self.provenance, str):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "provenance must be a string (opaque DATA)",
            )
        # LOCK-023: credential-like provenance annotations are
        # rejected (secret material never crosses the seam).
        reject_credential_like_text(self.provenance, label="provenance")

    def to_dict(self) -> dict:
        return {
            "observer_node_id": self.observer_node_id,
            "reporter_node_id": self.reporter_node_id,
            "source_class": self.source_class,
            "observed_at": self.observed_at,
            "claim_digest": self.claim_digest,
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class GatewayCandidate:
    """The result of ``register_gateway``: an admitted breakout
    gateway candidate (the evidence-bearing gateway record).

    ``gateway_ref`` is content-derived over the gateway IDENTITY
    content (name + gateway_id + node_id + role_class); the external
    seam identifier, the locality label, and the mutable capacity fact
    are DELIBERATELY EXCLUDED from the identity (changing them must
    not mint a new gateway identity).  ``evidence_source_class`` is
    the preserved provenance of the admitting evidence (a
    ``remote-claim`` candidate never silently becomes
    direct-observed).  ``state`` carries the provider-owned
    availability (diagnostic at the model level; the authoritative
    breakout state never lives here).
    """

    gateway_ref: str
    name: str
    gateway_id: str
    node_id: str
    role_class: str
    locality_label: str
    capacity_bps: int
    state: str
    evidence_source_class: str
    external_gateway_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "gateway_ref", validate_opaque_ref(self.gateway_ref, "gateway")
        )
        object.__setattr__(self, "name", validate_gateway_name(self.name))
        if not isinstance(self.gateway_id, str) or not self.gateway_id:
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "gateway_id must be a non-empty string",
            )
        object.__setattr__(self, "node_id", validate_node_id(self.node_id))
        object.__setattr__(
            self, "role_class", validate_gateway_role(self.role_class)
        )
        if self.locality_label:
            object.__setattr__(
                self,
                "locality_label",
                validate_locality_label(self.locality_label),
            )
        object.__setattr__(
            self, "capacity_bps", validate_capacity_bps(self.capacity_bps)
        )
        if self.state not in GatewayState.values():
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "gateway state %r must be one of %s"
                % (self.state, list(GatewayState.values())),
            )
        object.__setattr__(
            self,
            "evidence_source_class",
            validate_evidence_source(self.evidence_source_class),
        )
        if self.external_gateway_id:
            object.__setattr__(
                self,
                "external_gateway_id",
                validate_external_gateway_id(self.external_gateway_id),
            )
        # STRUCTURAL content-derivation check (mirrors the WORK-023
        # MeshRouteView/MeshBinding discipline): the gateway_ref is
        # not free text -- it MUST equal the content-derived
        # derive_gateway_ref(name, gateway_id, node_id, role_class).
        if self.gateway_ref != derive_gateway_ref(
            self.name, self.gateway_id, self.node_id, self.role_class
        ):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "gateway_ref must equal the content-derived "
                "derive_gateway_ref(name, gateway_id, node_id, "
                "role_class) -- a tampered or miscomputed ref is "
                "rejected (the gateway ref is structural, never free "
                "text)",
            )

    def to_dict(self) -> dict:
        return {
            "gateway_ref": self.gateway_ref,
            "name": self.name,
            "gateway_id": self.gateway_id,
            "node_id": self.node_id,
            "role_class": self.role_class,
            "locality_label": self.locality_label,
            "capacity_bps": self.capacity_bps,
            "state": self.state,
            "evidence_source_class": self.evidence_source_class,
            "external_gateway_id": self.external_gateway_id,
        }


@dataclass(frozen=True)
class BreakoutDecision:
    """A policy breakout decision consumed as DATA (WORK-024
    invariant 2: policy determines local vs remote breakout; the
    distributed core never invents a second policy authority).

    Built ONLY from a REAL, tamper-evident WORK-010
    ``PolicyDecision`` with ``effect == allow`` (the manager verifies
    the decision_id against the decision's canonical bytes before
    applying -- a tampered or denied decision never authorizes a
    breakout).  ``decision_ref`` is content-derived over
    (session_id, policy_decision_id, mode, applied_instant) and is
    SESSION-SCOPED: a decision applied for one session can never
    authorize another (fail-closed at establish).  ``matched_rule_ids``
    and ``locality_labels`` carry the policy provenance verbatim
    (DATA).
    """

    decision_ref: str
    session_id: str
    policy_decision_id: str
    policy_effect: str
    mode: str
    matched_rule_ids: Tuple[str, ...]
    locality_labels: Tuple[str, ...]
    applied_instant: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "decision_ref", validate_opaque_ref(self.decision_ref, "decision")
        )
        object.__setattr__(
            self, "session_id", validate_session_ref(self.session_id)
        )
        object.__setattr__(
            self,
            "policy_decision_id",
            validate_policy_decision_id(self.policy_decision_id),
        )
        if self.policy_effect != "allow":
            raise DistCoreError(
                DistCoreReasonCode.DECISION_DENIED,
                "a breakout decision requires an ALLOW policy effect "
                "(a denied decision never authorizes a breakout; the "
                "distributed core never overrides policy)",
            )
        object.__setattr__(
            self, "mode", validate_breakout_mode(self.mode)
        )
        if not isinstance(self.matched_rule_ids, tuple):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "matched_rule_ids must be a tuple of strings",
            )
        for rule_id in self.matched_rule_ids:
            if not isinstance(rule_id, str) or not rule_id:
                raise DistCoreError(
                    DistCoreReasonCode.INVALID_INPUT,
                    "matched_rule_ids entries must be non-empty strings",
                )
        if not isinstance(self.locality_labels, tuple):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "locality_labels must be a tuple of strings",
            )
        for label in self.locality_labels:
            validate_locality_label(label)
        object.__setattr__(
            self, "applied_instant", validate_instant(self.applied_instant)
        )
        # STRUCTURAL content-derivation check: the decision_ref MUST
        # equal derive_decision_ref(session_id, policy_decision_id,
        # mode, applied_instant) -- a tampered decision record is
        # rejected at construction.
        if self.decision_ref != derive_decision_ref(
            self.session_id,
            self.policy_decision_id,
            self.mode,
            self.applied_instant,
        ):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "decision_ref must equal the content-derived "
                "derive_decision_ref(session_id, policy_decision_id, "
                "mode, applied_instant) -- a tampered decision record "
                "is rejected (the decision ref is structural, never "
                "free text)",
            )

    def to_dict(self) -> dict:
        return {
            "decision_ref": self.decision_ref,
            "session_id": self.session_id,
            "policy_decision_id": self.policy_decision_id,
            "policy_effect": self.policy_effect,
            "mode": self.mode,
            "matched_rule_ids": list(self.matched_rule_ids),
            "locality_labels": list(self.locality_labels),
            "applied_instant": self.applied_instant,
        }


@dataclass(frozen=True)
class BreakoutBinding:
    """The result of ``establish_breakout``: the session-breakout
    binding on one gateway (the provider-side view).

    The ADCOS ``session_id`` is SACRED; ``breakout_ref`` is the OPAQUE
    technology breakout handle (content-derived over session_id +
    gateway_ref + path_ref + sequence).  A gateway change, path
    change, or breakout re-establishment mints a NEW ``breakout_ref``
    bound to the SAME ``session_id`` -- the W024 identity invariant;
    the boundary NEVER collapses them, and never mints a new
    session_id merely because the breakout gateway changed (mirrors
    the WORK-018 flow/session, WORK-019 PDU-session, WORK-021
    association/tunnel, WORK-022 session/bearer, and WORK-023
    session/bearer separations).  ``binding_id`` is the manager's
    binding key (content-derived over session_id + breakout_ref).
    ``path_ref`` carries the ordinary WORK-011 path fingerprint as
    opaque DATA (which registered path the breakout serves).
    ``state`` is the provider-side lifecycle (ACTIVE until released;
    the MANAGER-side authoritative chain state -- ACTIVE/SUPERSEDED/
    RELEASED with the supersedes/superseded_by links -- is manager
    record state, never provider state).
    """

    session_id: str
    breakout_ref: str
    binding_id: str
    gateway_ref: str
    path_ref: str
    state: str
    established_instant: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "session_id", validate_session_ref(self.session_id)
        )
        object.__setattr__(
            self, "breakout_ref", validate_opaque_ref(self.breakout_ref, "breakout")
        )
        if not isinstance(self.binding_id, str) or not self.binding_id:
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "binding_id must be a non-empty string",
            )
        # STRUCTURAL content-derivation check (mirrors the WORK-022
        # PR #23 and WORK-023 disciplines): the binding key MUST equal
        # derive_binding_id(session_id, breakout_ref).
        if self.binding_id != derive_binding_id(
            self.session_id, self.breakout_ref
        ):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "binding_id must equal the content-derived "
                "derive_binding_id(session_id, breakout_ref) -- a "
                "tampered or miscomputed binding key is rejected",
            )
        object.__setattr__(
            self, "gateway_ref", validate_opaque_ref(self.gateway_ref, "gateway")
        )
        object.__setattr__(self, "path_ref", validate_path_ref(self.path_ref))
        if self.state not in BreakoutState.values():
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "breakout state %r must be one of %s"
                % (self.state, list(BreakoutState.values())),
            )
        object.__setattr__(
            self,
            "established_instant",
            validate_instant(self.established_instant),
        )
        assert_ref_session_separation(self.breakout_ref, self.session_id)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "breakout_ref": self.breakout_ref,
            "binding_id": self.binding_id,
            "gateway_ref": self.gateway_ref,
            "path_ref": self.path_ref,
            "state": self.state,
            "established_instant": self.established_instant,
        }


@dataclass(frozen=True)
class BreakoutAllocation:
    """A breakout-capacity ledger admission (WORK-008 base units as
    DATA; the family never becomes a second accounting authority)."""

    allocation_ref: str
    kind: str
    quantity_base: int
    purpose: str
    state: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "allocation_ref", validate_opaque_ref(self.allocation_ref, "alloc")
        )
        if not isinstance(self.kind, str) or not self.kind:
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "kind must be a non-empty string",
            )
        if isinstance(self.quantity_base, bool) or not isinstance(
            self.quantity_base, int
        ):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "quantity_base must be an integer",
            )
        if self.quantity_base <= 0 or self.quantity_base > 2 ** 40:
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "quantity_base must be within 1..2^40",
            )
        if not isinstance(self.purpose, str) or not self.purpose:
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "purpose must be a non-empty string",
            )
        if self.state not in AllocationState.values():
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "allocation state %r must be one of %s"
                % (self.state, list(AllocationState.values())),
            )

    def to_dict(self) -> dict:
        return {
            "allocation_ref": self.allocation_ref,
            "kind": self.kind,
            "quantity_base": self.quantity_base,
            "purpose": self.purpose,
            "state": self.state,
        }


@dataclass(frozen=True)
class EgressOutcome:
    """The provider-side result of ``egress`` (what the provider
    observed -- the MANAGER composes the locality/latency-enriched
    record around it)."""

    breakout_ref: str
    gateway_ref: str
    egress_instant: str
    payload_bytes: int
    detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "breakout_ref", validate_opaque_ref(self.breakout_ref, "breakout")
        )
        object.__setattr__(
            self, "gateway_ref", validate_opaque_ref(self.gateway_ref, "gateway")
        )
        object.__setattr__(
            self, "egress_instant", validate_instant(self.egress_instant)
        )
        if isinstance(self.payload_bytes, bool) or not isinstance(
            self.payload_bytes, int
        ):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "payload_bytes must be an integer",
            )
        if self.payload_bytes <= 0:
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "payload_bytes must be positive",
            )
        if not isinstance(self.detail, str):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "detail must be a string",
            )

    def to_dict(self) -> dict:
        return {
            "breakout_ref": self.breakout_ref,
            "gateway_ref": self.gateway_ref,
            "egress_instant": self.egress_instant,
            "payload_bytes": self.payload_bytes,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class BreakoutEgress:
    """The MANAGER-composed egress record (locality + deterministic
    latency over WORK-011 path metrics).

    ``locality`` is the breakout mode policy determined ("local" or
    "remote"); ``path_latency_ms`` is the REGISTERED ordinary Path's
    aggregated latency (WORK-011 DATA captured at establishment --
    the deterministic latency fixture surface).  Local traffic stays
    local: egress through a LOCAL binding reports ``local`` and never
    touches a remote provider.
    """

    breakout_ref: str
    session_id: str
    gateway_ref: str
    path_ref: str
    mode: str
    locality: str
    path_latency_ms: int
    payload_bytes: int
    egress_instant: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "breakout_ref", validate_opaque_ref(self.breakout_ref, "breakout")
        )
        object.__setattr__(
            self, "session_id", validate_session_ref(self.session_id)
        )
        object.__setattr__(
            self, "gateway_ref", validate_opaque_ref(self.gateway_ref, "gateway")
        )
        object.__setattr__(self, "path_ref", validate_path_ref(self.path_ref))
        object.__setattr__(
            self, "mode", validate_breakout_mode(self.mode)
        )
        if self.locality not in BreakoutMode.values():
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "locality %r must be the breakout mode vocabulary %s"
                % (self.locality, list(BreakoutMode.values())),
            )
        if isinstance(self.path_latency_ms, bool) or not isinstance(
            self.path_latency_ms, int
        ):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "path_latency_ms must be an integer (WORK-011 DATA)",
            )
        if self.path_latency_ms < 0:
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "path_latency_ms must be non-negative",
            )
        if isinstance(self.payload_bytes, bool) or not isinstance(
            self.payload_bytes, int
        ):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "payload_bytes must be an integer",
            )
        if self.payload_bytes <= 0:
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "payload_bytes must be positive",
            )
        object.__setattr__(
            self, "egress_instant", validate_instant(self.egress_instant)
        )

    def to_dict(self) -> dict:
        return {
            "breakout_ref": self.breakout_ref,
            "session_id": self.session_id,
            "gateway_ref": self.gateway_ref,
            "path_ref": self.path_ref,
            "mode": self.mode,
            "locality": self.locality,
            "path_latency_ms": self.path_latency_ms,
            "payload_bytes": self.payload_bytes,
            "egress_instant": self.egress_instant,
        }


@dataclass(frozen=True)
class DistCoreObservation:
    """A technology-neutral breakout observation (DATA, never topology
    facts).

    ``samples`` follow the generic WORK-016 link-metric vocabulary as
    DATA; gateway/UPF-specific counters (N4 session reports, NAT
    table occupancy, N6 errors) stay inside implementations and are
    reported through these generic measures only (architecture §25).
    The explicit counters carry the availability facts:
    ``available_gateways`` / ``unavailable_gateways`` (partition
    honesty -- an unavailable local gateway DEGRADES the observation
    rather than silently disappearing), ``active_breakouts``, and the
    cumulative ``delivered_egress`` / ``failed_egress`` (attempts
    against unavailable gateways honestly counted, never masked).
    """

    samples: Tuple[Tuple[str, int], ...] = ()
    available_gateways: int = 0
    unavailable_gateways: int = 0
    active_breakouts: int = 0
    delivered_egress: int = 0
    failed_egress: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.samples, tuple):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "samples must be a tuple of (metric, value) pairs",
            )
        valid_metrics = LinkMetricName.values()
        for sample in self.samples:
            if not isinstance(sample, tuple) or len(sample) != 2:
                raise DistCoreError(
                    DistCoreReasonCode.INVALID_INPUT,
                    "each sample must be a (metric, value) pair",
                )
            name, value = sample
            if not isinstance(name, str) or not name:
                raise DistCoreError(
                    DistCoreReasonCode.INVALID_INPUT,
                    "sample metric names must be non-empty strings",
                )
            # STRUCTURAL vocabulary check (mirrors the WORK-022/023
            # discipline): metric names MUST be the generic WORK-016
            # link-metric vocabulary.
            if name not in valid_metrics:
                raise DistCoreError(
                    DistCoreReasonCode.INVALID_INPUT,
                    "sample metric %r is not in the generic WORK-016 "
                    "link-metric vocabulary %s (technology-specific "
                    "counters stay inside implementations)"
                    % (name, list(valid_metrics)),
                )
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise DistCoreError(
                    DistCoreReasonCode.INVALID_INPUT,
                    "sample values must be non-negative integers",
                )
        for field_name in (
            "available_gateways", "unavailable_gateways",
            "active_breakouts", "delivered_egress", "failed_egress",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise DistCoreError(
                    DistCoreReasonCode.INVALID_INPUT,
                    "%s must be a non-negative integer" % field_name,
                )

    def to_dict(self) -> dict:
        return {
            "samples": [[k, v] for k, v in self.samples],
            "available_gateways": self.available_gateways,
            "unavailable_gateways": self.unavailable_gateways,
            "active_breakouts": self.active_breakouts,
            "delivered_egress": self.delivered_egress,
            "failed_egress": self.failed_egress,
        }


@dataclass(frozen=True)
class DistCoreEvent:
    """A distributed-core integration event (manager event log)."""

    event_type: str
    integration_id: str
    instant: str
    gateway_ref: str = ""
    breakout_ref: str = ""
    path_ref: str = ""
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "integration_id": self.integration_id,
            "instant": self.instant,
            "gateway_ref": self.gateway_ref,
            "breakout_ref": self.breakout_ref,
            "path_ref": self.path_ref,
            "detail": self.detail,
        }


# --------------------------------------------------------------------------
# Content-derived id derivation (deterministic; no randomness)
# --------------------------------------------------------------------------


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def derive_gateway_ref(
    name: str, gateway_id: str, node_id: str, role_class: str
) -> str:
    """Content-derive the OPAQUE breakout-gateway ref.

    The identity content is the gateway's role tuple (name, gateway
    id, hosting node, role class).  The EXTERNAL seam identifier, the
    locality label, and the mutable capacity fact are DELIBERATELY
    EXCLUDED from the identity content (they are DATA: changing them
    must not mint a new gateway identity, and they must never leak
    into one).  The underlying gateway element / UPF N4/N6 / vendor
    daemon identity material is NEVER part of the content -- it stays
    adapter-side opaque (W024 identity invariant).
    """
    material = canonical_json_bytes(
        {
            "gateway": {
                "name": name,
                "gateway_id": gateway_id,
                "node_id": node_id,
                "role_class": role_class,
            }
        }
    )
    return "%s:gateway:%s" % (DISTCORE_PREFIX, _sha256_hex(material)[:32])


def derive_gateway_claim_digest(descriptor: GatewayDescriptor) -> str:
    """Content-derive the FULL gateway claim digest (what the evidence
    must bind to).

    The claim content is the COMPLETE descriptor (including the
    external seam identifier, the locality label, and the capacity
    fact): the evidence vouches for the WHOLE claim, so any change to
    the claim invalidates the evidence binding (fail-closed at
    registration with ``GATEWAY_UNEVIDENCED``).
    """
    material = canonical_json_bytes(
        {"claim": descriptor.to_dict()}
    )
    return _sha256_hex(material)


def derive_decision_ref(
    session_id: str,
    policy_decision_id: str,
    mode: str,
    applied_instant: str,
) -> str:
    """Content-derive the SESSION-SCOPED breakout-decision ref.

    Scoped to the session by construction: a decision applied for one
    session can never authorize another (the establish-time check is
    a simple ref equality -- no cross-session decision replay).  The
    policy decision id is hash INPUT, never observable ref TEXT.
    """
    material = canonical_json_bytes(
        {
            "session_id": session_id,
            "policy_decision_id": policy_decision_id,
            "mode": mode,
            "applied_instant": applied_instant,
        }
    )
    return "%s:decision:%s" % (DISTCORE_PREFIX, _sha256_hex(material)[:32])


def derive_breakout_ref(
    session_id: str,
    gateway_ref: str,
    path_ref: str,
    sequence: int,
) -> str:
    """Content-derive the OPAQUE breakout ref.

    Distinct from the sacred ``session_id`` by construction: the
    content includes ``session_id`` + the gateway binding material +
    the ordinary path fingerprint + a sequence, hashed to a 32-hex
    digest -- the session_id is hash INPUT, never observable ref
    TEXT.  A gateway change, path change, or breakout
    re-establishment produces a NEW ``breakout_ref`` for the SAME
    ``session_id`` (W024 identity invariant).  The technology
    breakout identity material (UPF N4 session id, NAT translation
    table slot, N3IWF tunnel id) is NEVER part of the content.
    """
    if isinstance(sequence, bool) or not isinstance(sequence, int):
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "sequence must be an integer",
        )
    material = canonical_json_bytes(
        {
            "session_id": session_id,
            "gateway_ref": gateway_ref,
            "path_ref": path_ref,
            "sequence": sequence,
        }
    )
    return "%s:breakout:%s" % (DISTCORE_PREFIX, _sha256_hex(material)[:32])


def derive_binding_id(session_id: str, breakout_ref: str) -> str:
    """Content-derive a binding id (the manager's binding key)."""
    material = canonical_json_bytes(
        {"session_id": session_id, "breakout_ref": breakout_ref}
    )
    return "%s:binding:%s" % (DISTCORE_PREFIX, _sha256_hex(material)[:32])


def derive_allocation_ref(
    kind: str,
    quantity_base: int,
    purpose: str,
    sequence: int,
) -> str:
    """Content-derive the OPAQUE breakout-capacity allocation ref.

    Deliberately NOT part of any identity content (mirrors the
    WORK-018/019/021/022/023 ref separation): a re-allocation after
    release produces a new ref without minting anything new on the
    session side.
    """
    if isinstance(sequence, bool) or not isinstance(sequence, int):
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "sequence must be an integer",
        )
    material = canonical_json_bytes(
        {
            "kind": kind,
            "quantity_base": quantity_base,
            "purpose": purpose,
            "sequence": sequence,
        }
    )
    return "%s:alloc:%s" % (DISTCORE_PREFIX, _sha256_hex(material)[:32])


def derive_integration_id(instance_label: str) -> str:
    """Content-derive the integration instance id (the manager's id)."""
    if not isinstance(instance_label, str) or not instance_label:
        raise DistCoreError(
            DistCoreReasonCode.INVALID_INPUT,
            "instance_label must be a non-empty string",
        )
    material = canonical_json_bytes({"instance_label": instance_label})
    return "%s:%s" % (DISTCORE_PREFIX, _sha256_hex(material)[:16])


__all__ = [
    "BreakoutMode",
    "GatewayRoleClass",
    "GatewayState",
    "BreakoutState",
    "EvidenceSourceClass",
    "AllocationState",
    "LinkMetricName",
    "GatewayDescriptor",
    "GatewayEvidence",
    "GatewayCandidate",
    "BreakoutDecision",
    "BreakoutBinding",
    "BreakoutAllocation",
    "EgressOutcome",
    "BreakoutEgress",
    "DistCoreObservation",
    "DistCoreEvent",
    "derive_gateway_ref",
    "derive_gateway_claim_digest",
    "derive_decision_ref",
    "derive_breakout_ref",
    "derive_binding_id",
    "derive_allocation_ref",
    "derive_integration_id",
]
