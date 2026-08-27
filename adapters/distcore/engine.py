"""ADCOS reference IP-gateway breakout engine (WORK-024): the
deterministic local-breakout reference implementation.

:class:`ReferenceIPGatewayEngine` models a GENERIC IP-gateway
breakout runtime behind the frozen
:class:`~adapters.distcore.contract.BreakoutProviderContract` --
the deterministic in-process stand-in for the WORK-018-mediated
local breakout seam (a production composition root wraps a real
``IPIntegrationManager`` behind the same contract; see the family
README for the composition recipe).  Deterministic by construction:
no wall clock, no randomness, no I/O; every temporal decision uses
the injected context instant and every identity is content-derived
(WORK-003 canonical bytes).

Reference shapes as DATA (3GPP TS 23.501 UPF/N6; TS 23.548 edge and
local UPF placement -- the LOCAL side of the distributed core keeps
local traffic local, exactly the placement concern those specs
frame): a gateway table (admitted candidates with preserved evidence
provenance and availability), a breakout table (session-scoped
bindings with the ordinary path fingerprint carried as opaque DATA),
a breakout-capacity ledger grounded in the AVAILABLE gateway
capacity, and a per-gateway delivery log (the locality-isolation
reference surface: what the LOCAL breakout actually delivered).

The validate/commit transactional discipline (the PR #24
architectural-review lesson, applied from day one): every mutating
operation is split into a ``_validate_*`` phase (charges the step
budget, runs every fail-closed check, derives content -- and
performs NO mutation, deriving identity refs from a CANDIDATE
sequence) and a ``_commit_*`` phase (infallible local bookkeeping
with defensive re-asserts; the ONLY site where the derivation nonce
advances).  A failed operation -- validate-phase rejection or
commit-phase fault alike -- leaves canonical manager state AND the
derivation nonce untouched, so failed operations are unobservable
in every future derived ref (pinned by the WORK-024 selftest's
sequence-discipline regression).
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
    assert_ref_session_separation,
    validate_opaque_ref,
    validate_path_ref,
    validate_session_ref,
)

__all__ = [
    "ReferenceIPGatewayEngine",
    "RATE_KINDS_BPS",
    "MAX_EGRESS_BYTES",
]

#: The WORK-008 bps-based rate kinds the breakout-capacity ledger
#: admits (mirroring the WORK-022 ``RATE_KINDS_BPS`` convention:
#: gateway egress capacity maps onto the frozen ``bandwidth`` /
#: ``backhaul`` resource kinds in bits-per-second base units as
#: DATA; the family never becomes a second accounting authority).
RATE_KINDS_BPS: Tuple[str, ...] = (
    "bandwidth",
    "backhaul",
)

#: Maximum egress payload (bytes) -- mirrors the WORK-023 bundle bound.
MAX_EGRESS_BYTES = 65536

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


class _GatewayEntry:
    """One admitted gateway: the candidate view, preserved evidence
    provenance, availability, delivery log, and reserved capacity."""

    __slots__ = (
        "candidate", "evidence_source_class", "available",
        "delivered", "reserved_bps",
    )

    def __init__(self, candidate: GatewayCandidate, evidence_source_class: str) -> None:
        self.candidate = candidate
        self.evidence_source_class = evidence_source_class
        self.available = True
        self.delivered: List[bytes] = []
        self.reserved_bps = 0


class _BreakoutEntry:
    """One live breakout binding (provider-side lifecycle)."""

    __slots__ = ("binding",)

    def __init__(self, binding: BreakoutBinding) -> None:
        self.binding = binding


class _AllocationEntry:
    """One breakout-capacity reservation."""

    __slots__ = ("allocation",)

    def __init__(self, allocation: BreakoutAllocation) -> None:
        self.allocation = allocation


class ReferenceIPGatewayEngine(BreakoutProviderContract):
    """The deterministic local-breakout reference implementation.

    Deterministic, in-memory, no wall clock, no randomness, no real
    sockets: the sanctioned "ordinary reference implementation used
    for deterministic testing" (the WORK-024 handoff permits
    deterministic reference implementations for conformance; a
    required real-provider interoperability criterion can never be
    satisfied by this in-repo engine -- invariant 10).
    """

    label = "reference-ip-gateway"

    def __init__(self) -> None:
        self._open = False
        # Insertion-ordered tables (determinism).
        self._gateways: Dict[str, _GatewayEntry] = {}
        self._breakouts: Dict[str, _BreakoutEntry] = {}
        self._allocations: Dict[str, _AllocationEntry] = {}
        # The identity-derivation nonce: advances ONLY inside the
        # commit phases (candidate-sequence discipline).
        self._sequence = 0
        # Honest counters.
        self._egress_total = 0
        self._egress_bytes_total = 0
        self._egress_failures = 0

    # ------------------------------------------------------------------
    # Internal guards
    # ------------------------------------------------------------------

    def _require_open(self) -> None:
        if not self._open:
            raise DistCoreError(
                DistCoreReasonCode.NOT_OPEN,
                "breakout provider is not open",
            )

    def _require_gateway(self, gateway_ref: str) -> _GatewayEntry:
        entry = self._gateways.get(gateway_ref)
        if entry is None:
            raise DistCoreError(
                DistCoreReasonCode.GATEWAY_UNKNOWN,
                "gateway %r is not admitted" % gateway_ref[:80],
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

    def _available_capacity_bps(self) -> int:
        """The allocatable pool: the sum of AVAILABLE gateways'
        capacity.  Zero-capacity and UNAVAILABLE gateways contribute
        NOTHING (the WORK-022 zero/unknown port-speed fail-closed
        lesson)."""
        total = 0
        for entry in self._gateways.values():
            if entry.available and entry.candidate.state == GatewayState.AVAILABLE:
                total += entry.candidate.capacity_bps
        return total

    def _reserved_bps(self) -> int:
        total = 0
        for entry in self._allocations.values():
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
        if self._breakouts or self._allocations:
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
        for entry in self._gateways.values():
            if not entry.available:
                return "DEGRADED"
        return "HEALTHY"

    # ------------------------------------------------------------------
    # Gateway admission (evidence-bearing)
    # ------------------------------------------------------------------

    def _validate_register_gateway(
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
                "gateway registration REQUIRES provenance-bearing "
                "evidence (a gateway is a role, not an identity; "
                "unevidenced claims fail closed)",
            )
        # The evidence MUST bind to the WHOLE claim (the WORK-018
        # GatewayResolver discipline): evidence whose digest does not
        # match the descriptor it vouches for is rejected.
        expected_digest = derive_gateway_claim_digest(descriptor)
        if evidence.claim_digest != expected_digest:
            raise DistCoreError(
                DistCoreReasonCode.GATEWAY_UNEVIDENCED,
                "gateway evidence does not bind to the claim it "
                "vouches for (claim digest mismatch; unevidenced "
                "registration fails closed)",
            )
        gateway_ref = derive_gateway_ref(
            descriptor.name, descriptor.gateway_id,
            descriptor.node_id, descriptor.role_class,
        )
        if gateway_ref in self._gateways:
            raise DistCoreError(
                DistCoreReasonCode.BINDING_EXISTS,
                "gateway identity is already admitted on this "
                "provider",
            )
        return GatewayCandidate(
            gateway_ref=gateway_ref,
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

    def _commit_register_gateway(
        self, candidate: GatewayCandidate, evidence_source_class: str
    ) -> None:
        if candidate.gateway_ref in self._gateways:  # defensive
            raise DistCoreError(
                DistCoreReasonCode.ILLEGAL_STATE,
                "gateway ref collision (deterministic derivation "
                "broken)",
            )
        self._gateways[candidate.gateway_ref] = _GatewayEntry(
            candidate, evidence_source_class
        )

    def register_gateway(
        self,
        context: BreakoutContext,
        *,
        descriptor: GatewayDescriptor,
        evidence: GatewayEvidence,
    ) -> GatewayCandidate:
        candidate = self._validate_register_gateway(
            context, descriptor=descriptor, evidence=evidence
        )
        self._commit_register_gateway(
            candidate, evidence.source_class
        )
        return candidate

    def _validate_close_gateway(
        self, context: BreakoutContext, *, gateway_ref: str
    ) -> _GatewayEntry:
        context.charge(STEP_CHARGES["close_gateway"])
        self._require_open()
        validate_opaque_ref(gateway_ref, "gateway")
        entry = self._require_gateway(gateway_ref)
        for breakout in self._breakouts.values():
            if breakout.binding.gateway_ref == gateway_ref:
                raise DistCoreError(
                    DistCoreReasonCode.ILLEGAL_STATE,
                    "gateway has live breakouts (close is fail-closed; "
                    "release the breakouts first)",
                )
        return entry

    def _commit_close_gateway(self, entry: _GatewayEntry) -> None:
        self._gateways.pop(entry.candidate.gateway_ref, None)

    def close_gateway(
        self, context: BreakoutContext, *, gateway_ref: str
    ) -> None:
        entry = self._validate_close_gateway(context, gateway_ref=gateway_ref)
        self._commit_close_gateway(entry)

    # ------------------------------------------------------------------
    # Breakout-capacity ledger admission
    # ------------------------------------------------------------------

    def _validate_allocate(
        self,
        context: BreakoutContext,
        *,
        kind: str,
        quantity_base: int,
        purpose: str,
    ) -> Tuple[BreakoutAllocation, int]:
        context.charge(STEP_CHARGES["allocate"])
        self._require_open()
        if kind not in RATE_KINDS_BPS:
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "kind must be one of the WORK-008 bps-based rate kinds "
                "%s (bits/second of gateway egress capacity as DATA)"
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
        # Ground the admission in the AVAILABLE gateway capacity:
        # unavailable and zero-capacity gateways contribute NOTHING
        # (fail closed; the WORK-022 lesson).
        available = self._available_capacity_bps() - self._reserved_bps()
        if quantity_base > available:
            raise DistCoreError(
                DistCoreReasonCode.CAPACITY_EXHAUSTED,
                "breakout capacity exhausted (available=%d bps; "
                "requested=%d bps; unavailable/zero-capacity gateways "
                "contribute no allocatable capacity)"
                % (available, quantity_base),
            )
        # Derive from a CANDIDATE sequence: the nonce advances only
        # in the commit phase, so a failed validation (or a
        # commit-phase defensive failure) leaves the derivation
        # state untouched and failed operations are unobservable in
        # future derived refs (the PR #24 architectural-review
        # discipline, applied from day one).
        candidate_sequence = self._sequence + 1
        allocation_ref = derive_allocation_ref(
            kind, quantity_base, purpose, candidate_sequence
        )
        allocation = BreakoutAllocation(
            allocation_ref=allocation_ref,
            kind=kind,
            quantity_base=quantity_base,
            purpose=purpose,
            state=AllocationState.RESERVED,
        )
        return allocation, candidate_sequence

    def _commit_allocate(
        self, allocation: BreakoutAllocation, candidate_sequence: int
    ) -> None:
        if allocation.allocation_ref in self._allocations:  # defensive
            raise DistCoreError(
                DistCoreReasonCode.ILLEGAL_STATE,
                "allocation ref collision (deterministic derivation "
                "broken)",
            )
        # The sequence advances ONLY here, in the commit phase.
        self._sequence = candidate_sequence
        self._allocations[allocation.allocation_ref] = _AllocationEntry(
            allocation
        )

    def allocate(
        self,
        context: BreakoutContext,
        *,
        kind: str,
        quantity_base: int,
        purpose: str,
    ) -> BreakoutAllocation:
        allocation, candidate_sequence = self._validate_allocate(
            context, kind=kind, quantity_base=quantity_base, purpose=purpose
        )
        self._commit_allocate(allocation, candidate_sequence)
        return allocation

    def _validate_release(
        self, context: BreakoutContext, allocation_ref: str
    ) -> _AllocationEntry:
        context.charge(STEP_CHARGES["release"])
        self._require_open()
        validate_opaque_ref(allocation_ref, "alloc")
        entry = self._allocations.get(allocation_ref)
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
        return entry

    def _commit_release(self, entry: _AllocationEntry) -> None:
        self._allocations.pop(entry.allocation.allocation_ref, None)

    def release(self, context: BreakoutContext, *, allocation_ref: str) -> None:
        entry = self._validate_release(context, allocation_ref)
        self._commit_release(entry)

    # ------------------------------------------------------------------
    # Session breakouts
    # ------------------------------------------------------------------

    def _validate_establish_breakout(
        self,
        context: BreakoutContext,
        *,
        session_id: str,
        gateway_ref: str,
        path_ref: str,
        requirements: Optional[Mapping[str, Any]],
    ) -> Tuple[BreakoutBinding, int]:
        context.charge(STEP_CHARGES["establish_breakout"])
        self._require_open()
        validate_session_ref(session_id)
        validate_opaque_ref(gateway_ref, "gateway")
        gateway = self._require_gateway(gateway_ref)
        validate_path_ref(path_ref)
        self._reject_identity_smuggling(requirements)
        if not gateway.available or (
            gateway.candidate.state != GatewayState.AVAILABLE
        ):
            # Honest failure accounting (observable in the
            # observation's failed_egress/health).
            raise DistCoreError(
                DistCoreReasonCode.GATEWAY_UNAVAILABLE,
                "breakout gateway is unavailable (local breakout "
                "degrades gracefully: fail closed, alternate remote "
                "paths remain establishable where policy allows)",
            )
        # WORK-012 authority, consulted READ-ONLY through the
        # least-authority context facade (fail closed BEFORE any
        # state mutation): the session must exist and be secureable.
        view = context.session_reader().lookup(session_id)
        if view is None:
            raise DistCoreError(
                DistCoreReasonCode.SESSION_NOT_SECUREABLE,
                "session is unknown to the WORK-012 authority "
                "(establish fails closed before any state mutation)",
            )
        if not view.secureable:
            raise DistCoreError(
                DistCoreReasonCode.SESSION_NOT_SECUREABLE,
                "session is not secureable (WORK-012 state is not "
                "ESTABLISHED/DEGRADED)",
            )
        for entry in self._breakouts.values():
            if (
                entry.binding.session_id == session_id
                and entry.binding.gateway_ref == gateway_ref
                and entry.binding.path_ref == path_ref
            ):
                raise DistCoreError(
                    DistCoreReasonCode.BINDING_EXISTS,
                    "session already holds a live breakout on this "
                    "gateway/path pair (distinct gateway/path pairs "
                    "may coexist; the same pair may not)",
                )
        # Derive from a CANDIDATE sequence: the nonce advances only
        # in the commit phase, so a failed validation (or a
        # commit-phase defensive failure) leaves the derivation
        # state untouched and future derived refs are exactly what
        # they would have been had the failed operation never
        # occurred.
        candidate_sequence = self._sequence + 1
        breakout_ref = derive_breakout_ref(
            session_id, gateway_ref, path_ref, candidate_sequence
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
        return binding, candidate_sequence

    def _commit_establish_breakout(
        self, binding: BreakoutBinding, candidate_sequence: int
    ) -> None:
        if binding.breakout_ref in self._breakouts:  # defensive re-assert
            raise DistCoreError(
                DistCoreReasonCode.ILLEGAL_STATE,
                "breakout ref collision (deterministic derivation "
                "broken)",
            )
        # The sequence advances ONLY here, in the commit phase.
        self._sequence = candidate_sequence
        self._breakouts[binding.breakout_ref] = _BreakoutEntry(binding)

    def establish_breakout(
        self,
        context: BreakoutContext,
        *,
        session_id: str,
        gateway_ref: str,
        path_ref: str,
        requirements: Optional[Mapping[str, Any]] = None,
    ) -> BreakoutBinding:
        binding, candidate_sequence = self._validate_establish_breakout(
            context,
            session_id=session_id,
            gateway_ref=gateway_ref,
            path_ref=path_ref,
            requirements=requirements,
        )
        self._commit_establish_breakout(binding, candidate_sequence)
        return binding

    def _validate_release_breakout(
        self, context: BreakoutContext, *, breakout_ref: str
    ) -> _BreakoutEntry:
        context.charge(STEP_CHARGES["release_breakout"])
        self._require_open()
        validate_opaque_ref(breakout_ref, "breakout")
        entry = self._breakouts.get(breakout_ref)
        if entry is None:
            raise DistCoreError(
                DistCoreReasonCode.BREAKOUT_UNKNOWN,
                "breakout %r is unknown" % breakout_ref[:80],
            )
        if entry.binding.state != BreakoutState.ACTIVE:
            raise DistCoreError(
                DistCoreReasonCode.BREAKOUT_STATE,
                "breakout is not ACTIVE (already released or "
                "superseded)",
            )
        return entry

    def _commit_release_breakout(self, entry: _BreakoutEntry) -> None:
        self._breakouts.pop(entry.binding.breakout_ref, None)

    def release_breakout(
        self, context: BreakoutContext, *, breakout_ref: str
    ) -> None:
        entry = self._validate_release_breakout(
            context, breakout_ref=breakout_ref
        )
        self._commit_release_breakout(entry)

    # ------------------------------------------------------------------
    # Egress (the deterministic local data path)
    # ------------------------------------------------------------------

    def _commit_egress_failure(self) -> None:
        """The failure-accounting commit for an egress attempt
        against an unavailable gateway (mirrors the WORK-023
        ``_commit_hop_budget_exhausted`` shape: guards raise, but the
        honest counter mutation goes through an explicit commit
        helper, never a validate phase)."""
        self._egress_failures += 1

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
        entry = self._breakouts.get(breakout_ref)
        if entry is None:
            raise DistCoreError(
                DistCoreReasonCode.BREAKOUT_UNKNOWN,
                "breakout %r is unknown" % breakout_ref[:80],
            )
        if entry.binding.state != BreakoutState.ACTIVE:
            raise DistCoreError(
                DistCoreReasonCode.BREAKOUT_STATE,
                "breakout is not ACTIVE (superseded or released "
                "breakouts never carry traffic -- no retroactive "
                "rebinding)",
            )
        gateway = self._require_gateway(entry.binding.gateway_ref)
        if not gateway.available or (
            gateway.candidate.state != GatewayState.AVAILABLE
        ):
            # Honest failure accounting: the attempt is observable
            # (through the commit helper; guards stay pure).
            self._commit_egress_failure()
            raise DistCoreError(
                DistCoreReasonCode.GATEWAY_UNAVAILABLE,
                "breakout gateway is unavailable (egress fails "
                "closed; fail over explicitly -- the binding is "
                "preserved)",
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
        # Commit: the delivery log + honest counters.
        gateway.delivered.append(bytes(payload))
        self._egress_total += 1
        self._egress_bytes_total += len(payload)
        return EgressOutcome(
            breakout_ref=entry.binding.breakout_ref,
            gateway_ref=entry.binding.gateway_ref,
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
        for entry in self._gateways.values():
            if entry.available and (
                entry.candidate.state == GatewayState.AVAILABLE
            ):
                available += 1
            else:
                unavailable += 1
        active = sum(
            1
            for entry in self._breakouts.values()
            if entry.binding.state == BreakoutState.ACTIVE
        )
        return DistCoreObservation(
            samples=(
                (LinkMetricName.LINK_UP, available),
                (LinkMetricName.RX_BYTES_TOTAL, 0),
                (LinkMetricName.TX_BYTES_TOTAL, self._egress_bytes_total),
                (LinkMetricName.RX_ERROR_COUNT, 0),
                (LinkMetricName.TX_ERROR_COUNT, self._egress_failures),
                (LinkMetricName.RETRANSMIT_COUNT, 0),
            ),
            available_gateways=available,
            unavailable_gateways=unavailable,
            active_breakouts=active,
            delivered_egress=self._egress_total,
            failed_egress=self._egress_failures,
        )

    # ------------------------------------------------------------------
    # Reference-model controls (NOT in CONTRACT_OPERATIONS)
    # ------------------------------------------------------------------

    def set_gateway_state(self, gateway_ref: str, *, available: bool) -> None:
        """Partition/recovery stand-in (deterministic test control).

        Marks a gateway AVAILABLE/UNAVAILABLE; a same-state
        transition is an ILLEGAL_STATE (strict toggling).  The
        mediated effects surface through establish/egress failures,
        health DEGRADATION, and the honest observation counters.
        """
        entry = self._require_gateway(gateway_ref)
        if entry.available == available:
            raise DistCoreError(
                DistCoreReasonCode.ILLEGAL_STATE,
                "gateway is already in the requested availability "
                "state (strict partition/recovery toggling)",
            )
        entry.available = available

    def delivered_payloads(self, gateway_ref: str) -> Tuple[bytes, ...]:
        """The gateway's delivery log (the locality-isolation
        reference surface: exactly what THIS provider delivered)."""
        entry = self._require_gateway(gateway_ref)
        return tuple(entry.delivered)

    def capabilities(self) -> Tuple[str, ...]:
        """The informational capability ladder (mediated manager
        state is authoritative; this mirrors the family ladder)."""
        if not self._open:
            return ()
        return (
            "capability.core.local-breakout",
            "capability.profile.distcore.breakout",
        )
