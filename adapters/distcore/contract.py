"""ADCOS distributed-core adapter contract (WORK-024): the stable
core-side seam.

The replaceable breakout-provider interface.  Implementations
(:class:`BreakoutProviderContract`) depend on the least-authority
:class:`BreakoutContext` facade -- and on nothing else in the core.
The manager (:mod:`adapters.distcore.manager`) mediates every call
through the sandbox (exception isolation, contract-shape validation
of every return value, deterministic step budget).  The core never
imports breakout-provider implementations and never lets gateway or
user-plane state become authoritative for ADCOS core state (LOCK-001:
the core encodes no single access technology; LOCK-016: external
access implementations behind adapter/provider interfaces; LOCK-017:
no vendor authority).

The contract defines the distributed-core boundary (the WORK-024
architect handoff):

1. The boundary holds the mapping between a WORK-012 session (sacred
   content-derived ``session_id``) and the BREAKOUT identity (the
   mutable, opaque ``breakout_ref`` serving one gateway/path pair).
   Session/gateway/path/breakout identity SEPARATION is the central
   invariant (the W024 standard):

       ADCOS session_id != breakout gateway identity != ordinary path
                         identity != breakout identity
                         != allocation identity

   A gateway change, path change, or breakout re-establishment
   produces a NEW ``breakout_ref`` bound to the SAME ``session_id``;
   the boundary NEVER collapses them, and never mints a new
   session_id merely because the breakout gateway changed (mirrors
   the WORK-018 route/session, WORK-019 PDU-session, WORK-021
   association/tunnel, WORK-022 session/bearer, and WORK-023
   session/bearer separations).

2. POLICY determines local versus remote breakout (WORK-024
   invariant 2): the breakout decision arrives as DATA -- the
   manager's ``apply_policy_decision`` consumes a REAL WORK-010
   ``PolicyDecision`` (tamper-evident, ALLOW effect, fresh) and the
   provider receives only the derived session-scoped
   ``decision_ref``-free coordinate pair (gateway_ref + path_ref).
   The family runs NO second policy authority: it never evaluates,
   re-evaluates, or overrides policy.

3. ROUTING is the WORK-011 engine's authority: this family CONSUMES
   ordinary ``Path`` objects and path fingerprints as DATA and never
   enumerates, scores, or selects paths.  Local-first composition is
   the CALLER's choice among REGISTERED ordinary Paths, driven by
   the policy-determined mode -- never a re-derivation inside this
   boundary.

4. A GATEWAY IS A ROLE, NOT AN IDENTITY (WORK-024 invariant 5):
   gateway registration is evidence-bearing DATA (reporter identity
   + provenance class + a claim digest binding the evidence to the
   whole claim).  Unevidenced registration fails closed
   (``GATEWAY_UNEVIDENCED`` -- the WORK-018 GatewayResolver
   discipline); a ``remote-claim`` gateway NEVER silently becomes
   direct-observed (provenance preserved, never upgraded).

5. WORK-018 owns ordinary IP semantics and WORK-019 owns the 5G
   user-plane shapes: this family COMPOSES IP paths (ordinary Path
   DATA) and mediates UPF/IP-gateway adapters; it recreates no
   IPv6/NAT/routing primitive and imports no Open5GS, N3IWF, vendor,
   or gateway implementation type (WORK-024 invariant 3 -- provider
   state stays adapter-owned).

6. Local breakout DEGRADES gracefully when unavailable (WORK-024
   invariant 6): an unavailable gateway fails closed
   (``GATEWAY_UNAVAILABLE``) at establish and egress; alternate
   remote paths remain establishable where policy/capabilities
   allow; failover is an EXPLICIT manager-side transition (invariant
   7) that never retroactively rebinds established flows -- the old
   breakout is superseded, the session_id is preserved, and the
   transition is recorded.

7. The boundary is ACCESS-STATE-OUT: the gateway/user-plane state
   (UPF N4/N6 state, NAT tables, gateway element management, N3IWF
   tunnels) lives in the adapter, NEVER in the ADCOS core.  The
   manager's snapshot carries only integration-instance state
   (breakout bindings + chain, applied decisions, events) -- NEVER
   gateway or user-plane state (LOCK-016/017).

8. The boundary is CREDENTIAL-OUT: gateway/UPF credentials (N4
   shared keys, gateway admin passphrases, IPsec/IKE material) live
   ONLY in the adapter's private credential store.  The context
   exposes slot NAMES only (LOCK-023).

9. The boundary is REPLACEABLE: ``register_provider`` swaps the
   DEFAULT sandbox only; live gateways and breakouts keep their
   owning sandbox (B2 per-record ownership, mirrors
   WORK-018/019/021/022/023).  Another gateway/UPF implementation
   plugs in behind the SAME contract without modifying the manager
   or any core semantics.

External gateway identifiers (an Open5GS UPF instance id, an N3IWF
gateway id, a vendor element name) ride the seam as opaque DATA
(``GatewayDescriptor.external_gateway_id``) and are never parsed into
core semantics, never part of any identity derivation, and never
allowed to match an ADCOS identifier grammar.  3GPP TS 23.501
(UPF/N6/PDU-session reference shapes) and TS 23.548 (edge/local UPF
placement) classify the same families as DATA with citations.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Tuple

from .errors import DistCoreError, DistCoreReasonCode
from .model import (
    BreakoutAllocation,
    BreakoutBinding,
    DistCoreObservation,
    EgressOutcome,
    GatewayCandidate,
    GatewayDescriptor,
    GatewayEvidence,
)


# --------------------------------------------------------------------------
# Least-authority context facade
# --------------------------------------------------------------------------


class _BudgetExhausted(Exception):
    """Internal sentinel: the operation step budget is exhausted.

    Never crosses the sandbox boundary; the sandbox converts it into
    a ``BUDGET_EXHAUSTED`` failure value.  This is the deterministic
    model of a hung/overrunning gateway/UPF operation -- no wall-clock
    timeouts exist anywhere in this layer (mirrors the WORK-016
    adapter, WORK-017 transport, WORK-018 IP integration, WORK-019
    5G Core integration, WORK-021 Wi-Fi access, WORK-022 backhaul,
    and WORK-023 mesh conventions).
    """


@dataclass(frozen=True)
class SessionView:
    """A secret-free projection of a WORK-012 session.

    The distributed-core boundary MAY see (session_id, secureable
    flag, endpoint node ids) and NOTHING ELSE.  No identity material,
    no policy decision id, no intent digest.  The WORK-012
    SessionStore's full surface is reduced to this projection by the
    :class:`SessionReader` facade -- the distributed-core boundary
    cannot reach beyond it (mirrors the WORK-018/019/021/022/023
    secret-free SessionView).
    """

    session_id: str
    secureable: bool
    initiator_node_id: str
    responder_node_id: str


class SessionReader(abc.ABC):
    """Read-only session lookup (the WORK-012 surface the
    distributed-core boundary may see -- ``lookup`` and nothing else).

    The facade deliberately exposes NOTHING mutating: no transition,
    no append, no event write.  A test double implements this same
    interface (the import-lock rule for test doubles).
    """

    __slots__ = ()

    @abc.abstractmethod
    def lookup(self, session_id: str) -> Optional[SessionView]:
        """Look up a session by id (read-only; never mutates).

        Returns the secret-free :class:`SessionView` projection, or
        ``None`` if the session does not exist.
        """


class BreakoutContext:
    """The ONLY object the core hands to a breakout-provider
    implementation.

    Least authority (architecture P6): the context exposes the
    integration's own id, the injected operation instant, a
    deterministic step budget, and the READ-ONLY
    :class:`SessionReader` facade.  It deliberately holds NO
    references to session stores, identity material, credential
    material, policy engines, topology graphs, routing engines, other
    adapter families, or the manager itself -- an implementation
    cannot reach core state through the context (mechanically:
    ``__slots__`` plus the frozen ``__setattr__`` below reject ANY
    attempt to inject session authority, credential material, or any
    other smuggled state into the facade; verified by the WORK-024
    selftest).
    """

    __slots__ = (
        "_integration_id",
        "_instant",
        "_steps_left",
        "_session_reader",
    )

    _integration_id: str
    _instant: str
    _steps_left: int
    _session_reader: Optional[SessionReader]

    def __init__(
        self,
        integration_id: str,
        instant: str,
        step_budget: int,
        session_reader: Optional[SessionReader],
    ) -> None:
        if not isinstance(integration_id, str) or not integration_id:
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "integration_id must be a non-empty string",
            )
        if not isinstance(instant, str) or not instant:
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "instant must be an RFC 3339 UTC instant string",
            )
        if isinstance(step_budget, bool) or not isinstance(step_budget, int):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "step_budget must be an integer",
            )
        if step_budget < 0:
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "step_budget must be >= 0",
            )
        if session_reader is not None and not isinstance(
            session_reader, SessionReader
        ):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "session_reader must be a SessionReader or None",
            )
        object.__setattr__(self, "_integration_id", integration_id)
        object.__setattr__(self, "_instant", instant)
        object.__setattr__(self, "_steps_left", step_budget)
        object.__setattr__(self, "_session_reader", session_reader)

    def __setattr__(self, name: str, value: Any) -> None:
        raise TypeError(
            "BreakoutContext is an immutable least-authority facade "
            "(attribute %r cannot be injected)" % name,
        )

    def __delattr__(self, name: str) -> None:
        raise TypeError(
            "BreakoutContext is an immutable least-authority facade "
            "(attribute %r cannot be deleted)" % name,
        )

    @property
    def integration_id(self) -> str:
        """The integration instance's own id."""
        return self._integration_id

    def now(self) -> str:
        """The injected operation instant (RFC 3339 UTC string).

        No wall clock exists anywhere in this layer -- every temporal
        decision (evidence instants, binding instants, freshness) is
        made against THIS injected instant.
        """
        return self._instant

    def charge(self, steps: int = 1) -> None:
        """Charge the deterministic step budget (hang model)."""
        if isinstance(steps, bool) or not isinstance(steps, int):
            raise _BudgetExhausted()
        if steps < 0:
            raise _BudgetExhausted()
        object.__setattr__(
            self, "_steps_left", self._steps_left - steps
        )
        if self._steps_left < 0:
            raise _BudgetExhausted()

    def steps_left(self) -> int:
        """The remaining step budget for this operation."""
        return self._steps_left

    def session_reader(self) -> SessionReader:
        """The READ-ONLY WORK-012 session facade (never None after
        construction; absent authority surfaces a rejecting reader).

        The distributed-core boundary MAY consult session bindability
        (is the session ESTABLISHED/DEGRADED and secureable?) but can
        NEVER mutate, create, or terminate sessions through this
        facade.
        """
        if self._session_reader is None:
            return _AbsentSessionReader()
        return self._session_reader


class _AbsentSessionReader(SessionReader):
    """The rejecting reader returned when no authority was injected.

    Every lookup returns ``None`` (unknown session) -- fail closed:
    an implementation that consults sessions without the manager
    injecting the real read-only authority gets a uniformly negative
    answer and can never fabricate bindability.
    """

    __slots__ = ()

    def lookup(self, session_id: str) -> Optional[SessionView]:
        return None


#: The least-authority context surface (pinned by the selftest).
CONTEXT_SURFACE = frozenset(
    {"integration_id", "now", "charge", "steps_left", "session_reader"}
)


# --------------------------------------------------------------------------
# The technology-neutral breakout-provider contract
# --------------------------------------------------------------------------


class BreakoutProviderContract(abc.ABC):
    """The stable technology-neutral breakout-provider interface
    (WORK-024).

    One implementation models a breakout-provider runtime serving one
    breakout mode's gateways: gateway candidates admitted with
    evidence, breakout-capacity ledger admission grounded in the
    AVAILABLE gateway capacity (zero-capacity/unavailable gateways
    contribute NOTHING -- the WORK-022 fail-closed lesson),
    session-scoped breakout bindings, and the deterministic egress
    discipline.  ``label`` is informational only (never canonical
    state).

    The eleven operations below are the family's frozen surface
    (:data:`CONTRACT_OPERATIONS`); every method is keyword-only after
    ``context`` and every return value crosses the sandbox's
    contract-shape validation before it can enter manager state.
    Deliberately NOT a subtype of the WORK-016 ``AdapterContract``
    (own domain vocabulary, mirroring the WORK-022/023 family
    decisions); the WORK-016 bridge subclasses the SDK contract
    instead.
    """

    __slots__ = ()

    #: Informational implementation label (never canonical state).
    label: str = ""

    @abc.abstractmethod
    def open(self, context: BreakoutContext) -> None:
        """Start the breakout-provider runtime (idempotent-open is a
        violation)."""

    @abc.abstractmethod
    def register_gateway(
        self,
        context: BreakoutContext,
        *,
        descriptor: GatewayDescriptor,
        evidence: GatewayEvidence,
    ) -> GatewayCandidate:
        """Admit one breakout gateway with provenance-bearing
        evidence (the evidence's claim digest MUST bind to the whole
        claim; unevidenced registration fails closed)."""

    @abc.abstractmethod
    def close_gateway(self, context: BreakoutContext, *, gateway_ref: str) -> None:
        """Close an admitted gateway (fail closed while breakouts are
        outstanding on it)."""

    @abc.abstractmethod
    def allocate(
        self,
        context: BreakoutContext,
        *,
        kind: str,
        quantity_base: int,
        purpose: str,
    ) -> BreakoutAllocation:
        """Reserve breakout capacity (family-native ledger admission
        grounded in the AVAILABLE gateway capacity; WORK-008 base
        units as DATA)."""

    @abc.abstractmethod
    def release(self, context: BreakoutContext, *, allocation_ref: str) -> None:
        """Release a breakout-capacity reservation."""

    @abc.abstractmethod
    def establish_breakout(
        self,
        context: BreakoutContext,
        *,
        session_id: str,
        gateway_ref: str,
        path_ref: str,
        requirements: Optional[Mapping[str, Any]] = None,
    ) -> BreakoutBinding:
        """Bind the sacred session to one breakout gateway on one
        registered ordinary Path (opaque DATA)."""

    @abc.abstractmethod
    def release_breakout(self, context: BreakoutContext, *, breakout_ref: str) -> None:
        """Release a breakout binding (fail closed)."""

    @abc.abstractmethod
    def egress(
        self,
        context: BreakoutContext,
        *,
        breakout_ref: str,
        payload: bytes,
    ) -> EgressOutcome:
        """Send one payload through the breakout (deterministic;
        fails closed on unavailable gateways and non-ACTIVE
        breakouts)."""

    @abc.abstractmethod
    def observe(self, context: BreakoutContext) -> DistCoreObservation:
        """Observe the provider/gateway state (generic metric
        vocabulary plus the availability counters; never topology
        facts)."""

    @abc.abstractmethod
    def health(self) -> str:
        """Report HEALTHY/DEGRADED/FAILED (informational)."""

    @abc.abstractmethod
    def close(self, context: BreakoutContext) -> None:
        """Tear the provider runtime down (fail closed while
        state is outstanding)."""


#: The frozen breakout-provider contract operation names, in canonical
#: order.
CONTRACT_OPERATIONS: Tuple[str, ...] = (
    "open",
    "register_gateway",
    "close_gateway",
    "allocate",
    "release",
    "establish_breakout",
    "release_breakout",
    "egress",
    "observe",
    "health",
    "close",
)


__all__ = [
    "SessionView",
    "SessionReader",
    "BreakoutContext",
    "CONTEXT_SURFACE",
    "BreakoutProviderContract",
    "CONTRACT_OPERATIONS",
]
