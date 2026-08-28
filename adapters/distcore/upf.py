"""ADCOS reference UPF breakout engine (WORK-024): the independent
remote-breakout reference implementation.

:class:`ReferenceUPFEngine` models a 5G-UPF-shaped remote breakout
runtime behind the SAME frozen
:class:`~adapters.distcore.contract.BreakoutProviderContract` as the
:class:`~adapters.distcore.engine.ReferenceIPGatewayEngine` -- with
DELIBERATELY DIFFERENT internals (an anchor table keyed by N6-style
anchor refs, per-breakout uplink state, a monolithic op discipline
with a nonce that advances only after every fail-closed check with
nothing but pure derivation and dict-insert following).  The pair
proves the W024 replaceability invariant exactly as the WORK-023
reference/sidelink pair proved mesh replaceability: identical
mediated op sequences over either implementation produce
byte-identical manager canonical state.

3GPP reference shapes as DATA (TS 23.501: the UPF's N6 interface to
the local data network, the PDU-session anchor role, the
session-AMBR/QoS-flow shapes; TS 23.548: the edge/local UPF
placement that motivates REMOTE breakout selection): the engine
models an ``anchor`` per admitted gateway (the N6 breakout point),
``uplink state`` per breakout (the PDU-session-anchored uplink), and
a deterministic N6 delivery log.  No SMF/UPF protocol state, no N4
(PFCP, TS 29.244) session machinery, no vendor daemon API, and no
credential material is modeled -- the reference engine is the
deterministic in-process conformance stand-in for the
WORK-019-mediated remote seam (a production composition root wraps a
real ``FiveGCoreManager`` behind the same contract; see the family
README).

The identity discipline is identical to the reference engine (the
contract baseline): the sacred ``session_id`` never appears in any
anchor/uplink ref; a gateway or path change mints a new
``breakout_ref`` for the SAME session; the derivation nonce
advances only with the commit (no failure path between the
increment and the dict insert -- monolithic bodies, the WORK-023
sidelink discipline).
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Tuple

from .contract import (
    BreakoutContext,
    BreakoutProviderContract,
)
from .errors import DistCoreError, DistCoreReasonCode
from .model import (
    AllocationState,
    BreakoutAllocation,
    BreakoutBinding,
    BreakoutState,
    DistCoreObservation,
    EgressOutcome,
    GatewayCandidate,
    GatewayDescriptor,
    GatewayEvidence,
    GatewayState,
    LinkMetricName,
    derive_allocation_ref,
    derive_binding_id,
    derive_breakout_ref,
    derive_gateway_claim_digest,
    derive_gateway_ref,
)
from .sandbox import STEP_CHARGES
from .validation import (
    validate_opaque_ref,
    validate_path_ref,
    validate_session_ref,
)

__all__ = ["ReferenceUPFEngine", "RATE_KINDS_BPS", "MAX_EGRESS_BYTES"]

from .engine import (  # noqa: E402
    RATE_KINDS_BPS,
    MAX_EGRESS_BYTES,
)

#: Requirement keys that carry IDENTITY material -- rejected
#: fail-closed inside the implementation as well (defense in depth;
#: the manager screens caller-side first).
_FORBIDDEN_REQUIREMENT_KEYS: Tuple[str, ...] = (
    "session_id",
    "session",
    "breakout_ref",
    "binding_id",
    "gateway_ref",
    "path_ref",
    "allocation_ref",
    "decision_ref",
    "flow_id",
    "pdu_session_ref",
)


class _AnchorEntry:
    """One admitted N6-style anchor (the remote breakout point):
    the candidate view, preserved evidence provenance, availability,
    the N6 delivery log, and the reserved anchor rate."""

    __slots__ = (
        "candidate", "evidence_source_class", "up", "n6_frames",
        "reserved_rate",
    )

    def __init__(self, candidate: GatewayCandidate, evidence_source_class: str) -> None:
        self.candidate = candidate
        self.evidence_source_class = evidence_source_class
        self.up = True
        self.n6_frames: List[bytes] = []
        self.reserved_rate = 0


class _UplinkState:
    """One breakout's uplink state (PDU-session-anchored)."""

    __slots__ = ("binding",)

    def __init__(self, binding: BreakoutBinding) -> None:
        self.binding = binding


class _RateEntry:
    """One anchor-rate reservation (the capacity ledger entry)."""

    __slots__ = ("allocation",)

    def __init__(self, allocation: BreakoutAllocation) -> None:
        self.allocation = allocation


class ReferenceUPFEngine(BreakoutProviderContract):
    """The deterministic remote-breakout (5G-UPF-shaped) reference
    implementation.

    Deterministic, in-memory, no wall clock, no randomness, no real
    sockets, no N4/PFCP protocol machinery: the sanctioned
    deterministic conformance peer (the WORK-024 handoff permits
    deterministic reference implementations for conformance; a
    required real-provider interoperability criterion can never be
    satisfied by this in-repo engine -- invariant 10).
    """

    label = "reference-upf"

    def __init__(self) -> None:
        self._open = False
        # Insertion-ordered tables (determinism).
        self._anchors: Dict[str, _AnchorEntry] = {}
        self._uplinks: Dict[str, _UplinkState] = {}
        self._rates: Dict[str, _RateEntry] = {}
        # The identity-derivation nonce: monolithic discipline -- it
        # advances only AFTER every fail-closed check, immediately
        # before the dict insert (no failure path between).
        self._nonce = 0
        # Honest counters.
        self._n6_total = 0
        self._n6_bytes_total = 0
        self._n6_failures = 0

    # ------------------------------------------------------------------
    # Internal guards
    # ------------------------------------------------------------------

    def _require_open(self) -> None:
        if not self._open:
            raise DistCoreError(
                DistCoreReasonCode.NOT_OPEN,
                "breakout provider is not open",
            )

    def _require_anchor(self, gateway_ref: str) -> _AnchorEntry:
        entry = self._anchors.get(gateway_ref)
        if entry is None:
            raise DistCoreError(
                DistCoreReasonCode.GATEWAY_UNKNOWN,
                "anchor %r is not admitted" % gateway_ref[:80],
            )
        return entry

    def _reject_identity_smuggling(
        self, requirements: Optional[Mapping[str, Any]]
    ) -> None:
        if requirements is None:
            return
        if not isinstance(requirements, Mapping):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "requirements must be a mapping or None",
            )
        for key in requirements:
            if key in _FORBIDDEN_REQUIREMENT_KEYS:
                raise DistCoreError(
                    DistCoreReasonCode.ACCESS_SESSION_COLLAPSE,
                    "requirement key %r carries identity material "
                    "(session/gateway/path/breakout identity is never "
                    "caller-suppliable)" % key,
                )

    def _anchor_rate_available(self) -> int:
        """The allocatable pool: the sum of UP anchor rates
        (zero-rate and DOWN anchors contribute NOTHING -- the WORK-022
        fail-closed lesson)."""
        total = 0
        for entry in self._anchors.values():
            if entry.up and entry.candidate.state == GatewayState.AVAILABLE:
                total += entry.candidate.capacity_bps
        return total

    def _rate_reserved(self) -> int:
        total = 0
        for entry in self._rates.values():
            if entry.allocation.state == AllocationState.RESERVED:
                total += entry.allocation.quantity_base
        return total

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open(self, context: BreakoutContext) -> None:
        context.charge(STEP_CHARGES["open"])
        if self._open:
            raise DistCoreError(
                DistCoreReasonCode.ALREADY_OPEN,
                "breakout provider is already open (idempotent-open "
                "is a contract violation)",
            )
        self._open = True

    def close(self, context: BreakoutContext) -> None:
        context.charge(STEP_CHARGES["close"])
        self._require_open()
        if self._uplinks or self._rates:
            raise DistCoreError(
                DistCoreReasonCode.ILLEGAL_STATE,
                "breakout provider has outstanding breakouts or "
                "allocations (release them first; teardown is "
                "fail-closed)",
            )
        self._open = False

    def health(self) -> str:
        if not self._open:
            return "NOT_RUNNING"
        for entry in self._anchors.values():
            if not entry.up:
                return "DEGRADED"
        return "HEALTHY"

    # ------------------------------------------------------------------
    # Anchor admission (evidence-bearing)
    # ------------------------------------------------------------------

    def register_gateway(
        self,
        context: BreakoutContext,
        *,
        descriptor: GatewayDescriptor,
        evidence: GatewayEvidence,
    ) -> GatewayCandidate:
        context.charge(STEP_CHARGES["register_gateway"])
        self._require_open()
        if not isinstance(descriptor, GatewayDescriptor):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "descriptor must be a GatewayDescriptor",
            )
        if not isinstance(evidence, GatewayEvidence):
            raise DistCoreError(
                DistCoreReasonCode.GATEWAY_UNEVIDENCED,
                "anchor registration REQUIRES provenance-bearing "
                "evidence (unevidenced claims fail closed)",
            )
        if evidence.claim_digest != derive_gateway_claim_digest(descriptor):
            raise DistCoreError(
                DistCoreReasonCode.GATEWAY_UNEVIDENCED,
                "anchor evidence does not bind to the claim it "
                "vouches for (claim digest mismatch)",
            )
        anchor_ref = derive_gateway_ref(
            descriptor.name, descriptor.gateway_id,
            descriptor.node_id, descriptor.role_class,
        )
        if anchor_ref in self._anchors:
            raise DistCoreError(
                DistCoreReasonCode.BINDING_EXISTS,
                "anchor identity is already admitted on this provider",
            )
        candidate = GatewayCandidate(
            gateway_ref=anchor_ref,
            name=descriptor.name,
            gateway_id=descriptor.gateway_id,
            node_id=descriptor.node_id,
            role_class=descriptor.role_class,
            locality_label=descriptor.locality_label,
            capacity_bps=descriptor.capacity_bps,
            state=GatewayState.AVAILABLE,
            evidence_source_class=evidence.source_class,
            external_gateway_id=descriptor.external_gateway_id,
        )
        self._anchors[anchor_ref] = _AnchorEntry(
            candidate, evidence.source_class
        )
        return candidate

    def close_gateway(
        self, context: BreakoutContext, *, gateway_ref: str
    ) -> None:
        context.charge(STEP_CHARGES["close_gateway"])
        self._require_open()
        validate_opaque_ref(gateway_ref, "gateway")
        entry = self._require_anchor(gateway_ref)
        for uplink in self._uplinks.values():
            if uplink.binding.gateway_ref == gateway_ref:
                raise DistCoreError(
                    DistCoreReasonCode.ILLEGAL_STATE,
                    "anchor has live breakouts (close is fail-closed)",
                )
        self._anchors.pop(entry.candidate.gateway_ref, None)

    # ------------------------------------------------------------------
    # Breakout-capacity ledger admission
    # ------------------------------------------------------------------

    def allocate(
        self,
        context: BreakoutContext,
        *,
        kind: str,
        quantity_base: int,
        purpose: str,
    ) -> BreakoutAllocation:
        context.charge(STEP_CHARGES["allocate"])
        self._require_open()
        if kind not in RATE_KINDS_BPS:
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "kind must be one of the WORK-008 bps-based rate kinds "
                "%s (bits/second of anchor egress capacity as DATA)"
                % (list(RATE_KINDS_BPS),),
            )
        if isinstance(quantity_base, bool) or not isinstance(quantity_base, int):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "quantity_base must be an integer",
            )
        if quantity_base <= 0 or quantity_base > 2 ** 40:
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "quantity_base must be within 1..2^40",
            )
        if not isinstance(purpose, str) or not purpose:
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "purpose must be a non-empty string",
            )
        available = self._anchor_rate_available() - self._rate_reserved()
        if quantity_base > available:
            raise DistCoreError(
                DistCoreReasonCode.CAPACITY_EXHAUSTED,
                "anchor rate exhausted (available=%d bps; requested=%d "
                "bps; down/zero-rate anchors contribute no allocatable "
                "capacity)" % (available, quantity_base),
            )
        # Monolithic discipline: every fail-closed check has passed;
        # the nonce advances here and nothing can fail between the
        # increment and the dict insert (the WORK-023 sidelink
        # discipline -- a failed allocate never consumes the nonce).
        self._nonce += 1
        allocation_ref = derive_allocation_ref(
            kind, quantity_base, purpose, self._nonce
        )
        allocation = BreakoutAllocation(
            allocation_ref=allocation_ref,
            kind=kind,
            quantity_base=quantity_base,
            purpose=purpose,
            state=AllocationState.RESERVED,
        )
        self._rates[allocation_ref] = _RateEntry(allocation)
        return allocation

    def release(self, context: BreakoutContext, *, allocation_ref: str) -> None:
        context.charge(STEP_CHARGES["release"])
        self._require_open()
        validate_opaque_ref(allocation_ref, "alloc")
        entry = self._rates.get(allocation_ref)
        if entry is None:
            raise DistCoreError(
                DistCoreReasonCode.ALLOCATION_UNKNOWN,
                "allocation %r is unknown" % allocation_ref[:80],
            )
        if entry.allocation.state != AllocationState.RESERVED:
            raise DistCoreError(
                DistCoreReasonCode.ILLEGAL_STATE,
                "allocation is already released",
            )
        self._rates.pop(allocation_ref, None)

    # ------------------------------------------------------------------
    # Session breakouts
    # ------------------------------------------------------------------

    def establish_breakout(
        self,
        context: BreakoutContext,
        *,
        session_id: str,
        gateway_ref: str,
        path_ref: str,
        requirements: Optional[Mapping[str, Any]] = None,
    ) -> BreakoutBinding:
        context.charge(STEP_CHARGES["establish_breakout"])
        self._require_open()
        validate_session_ref(session_id)
        validate_opaque_ref(gateway_ref, "gateway")
        anchor = self._require_anchor(gateway_ref)
        validate_path_ref(path_ref)
        self._reject_identity_smuggling(requirements)
        if not anchor.up or (
            anchor.candidate.state != GatewayState.AVAILABLE
        ):
            raise DistCoreError(
                DistCoreReasonCode.GATEWAY_UNAVAILABLE,
                "remote breakout anchor is unavailable (fail closed)",
            )
        # WORK-012 authority, consulted READ-ONLY (fail closed
        # BEFORE any state mutation).
        view = context.session_reader().lookup(session_id)
        if view is None or not view.secureable:
            raise DistCoreError(
                DistCoreReasonCode.SESSION_NOT_SECUREABLE,
                "session is unknown or not secureable to the WORK-012 "
                "authority (establish fails closed before any state "
                "mutation)",
            )
        for uplink in self._uplinks.values():
            if (
                uplink.binding.session_id == session_id
                and uplink.binding.gateway_ref == gateway_ref
                and uplink.binding.path_ref == path_ref
            ):
                raise DistCoreError(
                    DistCoreReasonCode.BINDING_EXISTS,
                    "session already holds a live breakout on this "
                    "anchor/path pair",
                )
        # Monolithic discipline: all fail-closed checks passed; the
        # nonce advances here and nothing can fail between the
        # increment and the dict insert.
        self._nonce += 1
        breakout_ref = derive_breakout_ref(
            session_id, gateway_ref, path_ref, self._nonce
        )
        binding_id = derive_binding_id(session_id, breakout_ref)
        binding = BreakoutBinding(
            session_id=session_id,
            breakout_ref=breakout_ref,
            binding_id=binding_id,
            gateway_ref=gateway_ref,
            path_ref=path_ref,
            state=BreakoutState.ACTIVE,
            established_instant=context.now(),
        )
        self._uplinks[breakout_ref] = _UplinkState(binding)
        return binding

    def release_breakout(
        self, context: BreakoutContext, *, breakout_ref: str
    ) -> None:
        context.charge(STEP_CHARGES["release_breakout"])
        self._require_open()
        validate_opaque_ref(breakout_ref, "breakout")
        uplink = self._uplinks.get(breakout_ref)
        if uplink is None:
            raise DistCoreError(
                DistCoreReasonCode.BREAKOUT_UNKNOWN,
                "breakout %r is unknown" % breakout_ref[:80],
            )
        if uplink.binding.state != BreakoutState.ACTIVE:
            raise DistCoreError(
                DistCoreReasonCode.BREAKOUT_STATE,
                "breakout is not ACTIVE",
            )
        self._uplinks.pop(breakout_ref, None)

    # ------------------------------------------------------------------
    # Egress (the deterministic remote/N6 data path)
    # ------------------------------------------------------------------

    def _commit_n6_failure(self) -> None:
        """The failure-accounting commit for an egress attempt
        against a down anchor (guards stay pure; the honest counter
        mutation goes through an explicit commit helper)."""
        self._n6_failures += 1

    def egress(
        self,
        context: BreakoutContext,
        *,
        breakout_ref: str,
        payload: bytes,
    ) -> EgressOutcome:
        context.charge(STEP_CHARGES["egress"])
        self._require_open()
        validate_opaque_ref(breakout_ref, "breakout")
        uplink = self._uplinks.get(breakout_ref)
        if uplink is None:
            raise DistCoreError(
                DistCoreReasonCode.BREAKOUT_UNKNOWN,
                "breakout %r is unknown" % breakout_ref[:80],
            )
        if uplink.binding.state != BreakoutState.ACTIVE:
            raise DistCoreError(
                DistCoreReasonCode.BREAKOUT_STATE,
                "breakout is not ACTIVE (superseded or released "
                "breakouts never carry traffic)",
            )
        anchor = self._require_anchor(uplink.binding.gateway_ref)
        if not anchor.up or (
            anchor.candidate.state != GatewayState.AVAILABLE
        ):
            self._commit_n6_failure()
            raise DistCoreError(
                DistCoreReasonCode.GATEWAY_UNAVAILABLE,
                "remote breakout anchor is unavailable (egress fails "
                "closed; the binding is preserved)",
            )
        if not isinstance(payload, (bytes, bytearray)):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "payload must be bytes",
            )
        if not (1 <= len(payload) <= MAX_EGRESS_BYTES):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "payload must be 1..%d bytes" % MAX_EGRESS_BYTES,
            )
        # Commit: the N6 delivery log + honest counters.
        anchor.n6_frames.append(bytes(payload))
        self._n6_total += 1
        self._n6_bytes_total += len(payload)
        return EgressOutcome(
            breakout_ref=uplink.binding.breakout_ref,
            gateway_ref=uplink.binding.gateway_ref,
            egress_instant=context.now(),
            payload_bytes=len(payload),
        )

    # ------------------------------------------------------------------
    # Observation
    # ------------------------------------------------------------------

    def observe(self, context: BreakoutContext) -> DistCoreObservation:
        context.charge(STEP_CHARGES["observe"])
        self._require_open()
        available = 0
        unavailable = 0
        for entry in self._anchors.values():
            if entry.up and entry.candidate.state == GatewayState.AVAILABLE:
                available += 1
            else:
                unavailable += 1
        active = sum(
            1
            for uplink in self._uplinks.values()
            if uplink.binding.state == BreakoutState.ACTIVE
        )
        return DistCoreObservation(
            samples=(
                (LinkMetricName.LINK_UP, available),
                (LinkMetricName.RX_BYTES_TOTAL, 0),
                (LinkMetricName.TX_BYTES_TOTAL, self._n6_bytes_total),
                (LinkMetricName.RX_ERROR_COUNT, 0),
                (LinkMetricName.TX_ERROR_COUNT, self._n6_failures),
                (LinkMetricName.RETRANSMIT_COUNT, 0),
            ),
            available_gateways=available,
            unavailable_gateways=unavailable,
            active_breakouts=active,
            delivered_egress=self._n6_total,
            failed_egress=self._n6_failures,
        )

    # ------------------------------------------------------------------
    # Reference-model controls (NOT in CONTRACT_OPERATIONS)
    # ------------------------------------------------------------------

    def set_anchor_state(self, gateway_ref: str, *, up: bool) -> None:
        """Partition/recovery stand-in (deterministic test control;
        deliberately a DIFFERENT control surface than the reference
        engine's ``set_gateway_state`` -- the implementations are
        independent, mirroring the WORK-023 set_link_state /
        set_leg_state split)."""
        entry = self._require_anchor(gateway_ref)
        if entry.up == up:
            raise DistCoreError(
                DistCoreReasonCode.ILLEGAL_STATE,
                "anchor is already in the requested availability "
                "state (strict partition/recovery toggling)",
            )
        entry.up = up

    def delivered_payloads(self, gateway_ref: str) -> Tuple[bytes, ...]:
        """The anchor's N6 delivery log (the locality-isolation
        reference surface: exactly what THIS provider delivered)."""
        entry = self._require_anchor(gateway_ref)
        return tuple(entry.n6_frames)

    def capabilities(self) -> Tuple[str, ...]:
        """The informational capability ladder (mediated manager
        state is authoritative; this mirrors the family ladder)."""
        if not self._open:
            return ()
        return (
            "capability.core.local-breakout",
            "capability.profile.distcore.breakout",
        )
