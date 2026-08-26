"""ADCOS 5G RAN integration contract (WORK-020): the stable core-side seam.

The replaceable 5G RAN (gNB/CU/DU/RU) integration interface.
Implementations (:class:`RanContract`) depend on the least-authority
:class:`RanContext` facade -- and on nothing else in the core.  The
core-side path is::

    ADCOS core -> RanManager -> SandboxedRan -> RanContract
        -> concrete RAN stacks (OpenAirInterface, O-CU/O-DU/O-RU-style
           open implementations, future RAN)

The manager mediates every call through the sandbox: exception
isolation, contract-shape validation of every return value,
deterministic step budget.  The core never imports RAN
implementations and never lets RAN state become authoritative for
ADCOS core state (LOCK-002: 5G is an adapter -- 3GPP RAN functions
remain outside the ADCOS core domain; LOCK-006: logical session
identity is access independent; LOCK-016: external RAN/modem/SDR
implementations remain behind adapter/provider interfaces; LOCK-017:
vendor implementations are not ADCOS authority; architecture §25
rule 9 -- no fixed access technology).

The contract defines the 5G RAN integration boundary:

1. The boundary holds the mapping between a WORK-012 session (sacred,
   content-derived, access-independent ``session_id`` -- LOCK-006) and
   a RAN-side RADIO BEARER identity (the opaque ``ran:bearer:<digest>``
   reference standing for the adapter-private UE context: RNTI (TS
   38.321 §7.1), DRB ids (TS 38.331), serving cell/gNB).  Session/
   bearer identity SEPARATION is the central invariant (R1): the
   ``session_id`` is a READ-ONLY passthrough identity that crosses the
   seam exactly as given; implementations must NEVER mutate, re-derive,
   or echo it as a RAN handle, and a RAN reference must never equal or
   embed it (mechanically checked by
   :func:`adapters.ran.validation.assert_ref_session_separation`).

2. The boundary is RAN-STATE-OUT: gNB/CU/DU/RU/cell/RRC state (TS
   38.401 architecture, TS 38.331 RRC, TS 38.413 NGAP associations)
   lives in the adapter/conformance peer, NEVER in the ADCOS core.
   The manager's snapshot carries only integration-instance state
   (bindings, events) -- NEVER RAN state (LOCK-016/017).

3. The boundary is RESOURCE-MAPPED: PRB capacity/reservations (TS
   38.211 §4.4) and DRB/QoS-flow mappings (TS 23.501 §5.4) appear as
   integer DATA in :class:`adapters.ran.model.RanResourceSnapshot` --
   a mapping into generic resource semantics, never WORK-008 fabric
   accounting authority.

4. The boundary is TOPOLOGY-MAPPED: the CU/DU/RU boundary mapping (TS
   38.401 §5; TS 38.473 F1; TS 38.463 E1; O-RAN.WG4 open fronthaul,
   split 7-2x) is ADAPTER-OWNED DATA carried in
   :class:`adapters.ran.model.RanSplitTopology` -- never core
   topology authority (WORK-007).

5. The boundary is application-TRANSPARENT: ordinary applications use
   standard session semantics with a standard destination string; NO
   ADCOS/RAN API, no RNTI/DRB/cell id, appears in the app path
   (LOCK-019 analog; LOCK-006 -- access technology is invisible to
   the session).

6. The boundary is REPLACEABLE: ``register_implementation`` swaps the
   DEFAULT sandbox only; live bindings keep their owning sandbox (B2
   per-binding ownership, mirrors WORK-018/019).  An OpenAirInterface
   CU/DU + SDR stack, an O-CU/O-DU/O-RU-style open implementation, or
   a future RAN plugs in behind the SAME contract without modifying
   the manager or any core semantics (the WORK-020 acceptance
   criterion "ADCOS core imports no vendor/Open RAN implementation
   types").

Concrete 5G RAN stacks plug in behind the same ABC without modifying
the manager or any core semantics.  3GPP RAN functions and vendor
types remain outside the ADCOS core domain (LOCK-002/016/017).
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence, Tuple

from .errors import RanError, RanReasonCode
from .model import GnbProvisionRequest, RanObservation


# --------------------------------------------------------------------------
# Least-authority context facade
# --------------------------------------------------------------------------


class _BudgetExhausted(Exception):
    """Internal sentinel: the operation step budget is exhausted.

    Never crosses the sandbox boundary; the sandbox converts it into
    a ``BUDGET_EXHAUSTED`` failure value.  This is the deterministic
    model of a hung/overrunning RAN integration operation -- no
    wall-clock timeouts exist anywhere in the RAN integration layer
    (mirrors the WORK-016 adapter, WORK-017 transport, WORK-018 IP
    integration, and WORK-019 5G Core integration conventions).
    """


class RanContext:
    """The ONLY object the core hands to a RAN integration
    implementation.

    Least authority (architecture P6): the context exposes the
    integration's own id, the injected operation instant, and a
    deterministic step budget.  It deliberately holds NO references
    to session stores, identity material, credential material, policy
    engines, topology graphs, transport managers, resource stores, or
    the manager itself -- an implementation cannot reach core state
    through the context (mechanically verified by the WORK-020
    selftest).

    The ``session_id`` is NOT part of the context: it crosses as an
    explicit, read-only ``bind_session`` argument and must be treated
    by implementations as opaque passthrough identity (never mutated,
    never re-derived, never echoed as a RAN handle -- LOCK-006/R1).
    """

    __slots__ = ("_ran_integration_id", "_instant", "_steps_left")

    _ran_integration_id: str
    _instant: str
    _steps_left: int

    def __init__(
        self,
        ran_integration_id: str,
        instant: str,
        step_budget: int,
    ) -> None:
        if not isinstance(ran_integration_id, str) or not ran_integration_id:
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "ran_integration_id must be a non-empty string",
            )
        if not isinstance(instant, str) or not instant:
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "instant must be an RFC 3339 UTC instant string",
            )
        if isinstance(step_budget, bool) or not isinstance(step_budget, int):
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "step_budget must be an integer",
            )
        if step_budget < 0:
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "step_budget must be >= 0",
            )
        object.__setattr__(self, "_ran_integration_id", ran_integration_id)
        object.__setattr__(self, "_instant", instant)
        object.__setattr__(self, "_steps_left", step_budget)

    @property
    def ran_integration_id(self) -> str:
        """This integration instance's own id (never core authority)."""
        return self._ran_integration_id

    def now(self) -> str:
        """The injected instant of the current operation (never wall clock)."""
        return self._instant

    def charge(self, steps: int = 1) -> None:
        """Charge deterministic RAN integration work against the budget."""
        if isinstance(steps, bool) or not isinstance(steps, int):
            raise _BudgetExhausted()
        if steps < 0:
            raise _BudgetExhausted()
        object.__setattr__(self, "_steps_left", self._steps_left - steps)
        if self._steps_left < 0:
            raise _BudgetExhausted()

    def steps_left(self) -> int:
        """Remaining budget (introspection for tests/implementations)."""
        return self._steps_left

    def __setattr__(self, name: str, value: Any) -> None:
        raise TypeError(
            "RanContext is immutable: RAN integration implementations "
            "cannot inject state into the core facade"
        )


#: The attribute surface an implementation may use (the sandbox and
#: the selftest verify implementations receive nothing beyond this).
RAN_CONTEXT_SURFACE = frozenset(
    {
        "ran_integration_id",
        "now",
        "charge",
        "steps_left",
    }
)


# --------------------------------------------------------------------------
# Secret-free view projections (what the boundary may report outward)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class BearerView:
    """A secret-free projection of a bound radio bearer.

    ``bearer_ref`` is the OPAQUE RAN-side handle (``ran:bearer:...``);
    ``session_id`` is stored EXACTLY as provided -- the boundary is a
    read-only projection and session identity is access-independent
    (LOCK-006): the projection never mutates, re-derives, or
    reinterprets it.  No RNTI/DRB/cell material ever appears here
    (LOCK-016/017; mirrors the WORK-018/019 secret-free views).
    """

    bearer_ref: str
    session_id: str


@dataclass(frozen=True)
class GnbView:
    """A secret-free projection of a provisioned gNB.

    ``gnb_ref`` is the OPAQUE RAN-side handle (``ran:gnb:...``);
    ``gnb_name`` is the caller-chosen label; ``cell_count`` is the
    number of served cells; the topology summary fields (the CU
    element id, the DU element ids, the RU element ids) are plain
    adapter-owned DATA, never core topology authority (WORK-007;
    LOCK-016/017).
    """

    gnb_ref: str
    gnb_name: str
    cell_count: int
    cu_element_id: str
    du_element_ids: Tuple[str, ...]
    ru_element_ids: Tuple[str, ...]


# --------------------------------------------------------------------------
# The stable 5G RAN integration contract
# --------------------------------------------------------------------------


class RanContract(abc.ABC):
    """The stable interface every 5G RAN integration implementation
    satisfies.

    Implementations are untrusted: the sandbox mediates every call,
    validates every return value against the contract shape, converts
    any exception (including ``BaseException``) into an isolated
    failure value, and enforces the deterministic step budget.  A
    contract method must never be called directly by core code -- only
    through the sandboxed RAN wrapper.

    Authority boundary (every method): the implementation is
    authoritative ONLY for RAN technology state (its own gNB/cell/
    bearer/RNTI/DRB bookkeeping, TS 38.300/38.401/38.331/38.321/38.413
    reference shapes).  The ADCOS ``session_id`` is a sacred,
    access-independent, READ-ONLY passthrough identity: it crosses as
    given, implementations must never mutate or re-derive it, and no
    RAN-side reference may equal or embed it (LOCK-006; R1 invariant
    checked mechanically at the seam).  All references returned by
    these operations are OPAQUE RAN-side handles -- never core state.
    """

    __slots__ = ()

    #: Optional human label.  Informational only -- never parsed, never
    #: branched on (no core state machine branches on implementation
    #: names), and NEVER part of canonical public state (B2; mirrors
    #: the WORK-018/019 discipline).
    label: str = ""

    @abc.abstractmethod
    def open(self, context: RanContext) -> None:
        """Bring the RAN integration up.  Return None on success.

        The implementation is authoritative only for its own RAN
        technology state; the session identity never crosses this op.
        """

    @abc.abstractmethod
    def close(self, context: RanContext) -> None:
        """Bring the RAN integration down.  Return None on success.

        Fails closed while bindings are outstanding (the manager never
        tears down a live session-to-bearer mapping underneath an
        application).
        """

    @abc.abstractmethod
    def capabilities(self) -> Sequence[str]:
        """Current capability-id REFERENCES (subset of the RAN catalog).

        References into WORK-005 registry semantics only -- never
        minted, registered, or reinterpreted here (exposure by
        reference; LOCK-018 open-world discipline).
        """

    @abc.abstractmethod
    def observe(self, context: RanContext) -> RanObservation:
        """Report the mapped RAN state snapshot.

        Carries capability references, per-element health (gNB/CU/DU/
        RU/cell + NGAP-connected flag), the integer resource snapshot
        (PRB totals/reservations, RRC-connected UE count, active DRB
        count), the CU/DU/RU topology, and the generic link metrics.
        ALL of it is adapter-reported DATA -- never core topology/
        resource/health authority (LOCK-016/017).
        """

    @abc.abstractmethod
    def provision_gnb(self, context: RanContext, *, request: GnbProvisionRequest) -> str:
        """Provision a gNB (TS 38.300 §5 logical node serving cells).

        Returns the OPAQUE ``ran:gnb:<digest>`` reference.  The gNB
        cells/topology are adapter-private RAN state; the reference is
        RAN-side identity, never core state and never the sacred
        ``session_id`` (LOCK-006/016).
        """

    @abc.abstractmethod
    def decommission_gnb(self, context: RanContext, *, gnb_ref: str) -> None:
        """Decommission a provisioned gNB by its opaque reference.

        Fails closed while live bearers are served by the gNB (the
        manager never collapses a live mapping underneath an
        application).
        """

    @abc.abstractmethod
    def activate_cell(self, context: RanContext, *, gnb_ref: str, cell_id: str) -> None:
        """Activate a served cell (TS 38.413 cell activation semantics
        as adapter state; no RRC state machine crosses the seam)."""

    @abc.abstractmethod
    def deactivate_cell(self, context: RanContext, *, gnb_ref: str, cell_id: str) -> None:
        """Deactivate a served cell (its PRBs leave the active capacity;
        live bearers on it degrade the health aggregate)."""

    @abc.abstractmethod
    def bind_session(
        self,
        context: RanContext,
        *,
        session_id: str,
        requirements: Optional[Mapping[str, Any]],
    ) -> str:
        """Create a radio bearer for a WORK-012 session.

        The ``session_id`` is a READ-ONLY passthrough identity: the
        implementation stores it EXACTLY as given for its own mapping
        bookkeeping, never mutates or re-derives it, and never echoes
        it as a RAN handle (LOCK-006; R1).  ``requirements`` is
        caller-supplied QoS DATA (e.g. a PRB reservation hint);
        enforcing QoS is the RAN's job, behind the seam.

        Returns the OPAQUE ``ran:bearer:<digest>`` reference standing
        for the adapter-private UE context (RNTI allocation per TS
        38.321 §7.1, DRB per TS 38.331, QoS-flow mapping per TS 23.501
        §5.4 -- all INSIDE the implementation; the core sees only the
        opaque ref).
        """

    @abc.abstractmethod
    def unbind_session(self, context: RanContext, *, bearer_ref: str) -> None:
        """Tear down a radio bearer by its opaque reference.

        Releases the adapter-private UE context (RNTI/DRB state) and
        the cell's PRB reservation.  The manager removes its
        session-to-bearer mapping only after this succeeds.
        """

    @abc.abstractmethod
    def egress_data(
        self,
        context: RanContext,
        *,
        bearer_ref: str,
        payload: bytes,
    ) -> bytes:
        """Carry the payload over the radio bearer's user plane.

        A deterministic reference engine applies a content-derived
        transform (its model of the radio user plane); real RAN stacks
        traverse the actual radio user plane and return the bytes the
        far end returned.  In both cases the return is bytes -- the
        payload path is byte-exact and wall-clock-free.
        """

    @abc.abstractmethod
    def allocate(
        self,
        context: RanContext,
        *,
        kind: str,
        quantity_base: int,
        purpose: str,
    ) -> str:
        """Reserve radio capacity (an adapter-scoped reservation).

        ``kind``/``quantity_base``/``purpose`` mirror the WORK-016
        allocate semantics (integer base units).  Returns the OPAQUE
        ``ran:alloc:<digest>`` reference.  A mapping into generic
        resource semantics -- never WORK-008 fabric accounting.
        """

    @abc.abstractmethod
    def release(self, context: RanContext, *, technology_ref: str) -> None:
        """Release a previously returned radio-capacity reservation."""

    @abc.abstractmethod
    def health(self) -> str:
        """Implementation-local health: HEALTHY, DEGRADED, or FAILED.

        Reported, never authoritative by itself (LOCK-017): the manager
        computes the effective health from mediated outcomes.
        """


#: The frozen 5G RAN integration contract operations, in interface
#: order (a later selftest pins this tuple exactly).  The nine WORK-016
#: SDK operations (open, capabilities, observe, allocate, release,
#: bind_session, unbind_session, health, close) are translated by the
#: WORK-016 bridge; the RAN-local operations (provision_gnb,
#: decommission_gnb, activate_cell, deactivate_cell, egress_data)
#: carry the RAN-specific vocabulary that has no generic-SDK analog
#: and therefore stays inside the RAN family's own seam (mirrors the
#: accepted WORK-019 family, whose provision/authenticate/establish
#: vocabulary likewise stays inside ``FiveGCoreContract``).
RAN_CONTRACT_OPERATIONS: Tuple[str, ...] = (
    "open",
    "close",
    "capabilities",
    "observe",
    "provision_gnb",
    "decommission_gnb",
    "activate_cell",
    "deactivate_cell",
    "bind_session",
    "unbind_session",
    "egress_data",
    "allocate",
    "release",
    "health",
)


__all__ = [
    "RanContext",
    "RanContract",
    "RAN_CONTEXT_SURFACE",
    "RAN_CONTRACT_OPERATIONS",
    "BearerView",
    "GnbView",
]
