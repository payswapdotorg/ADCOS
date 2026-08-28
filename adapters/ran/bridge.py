"""ADCOS RAN technology adapter bridge (WORK-020): the adapter
translation layer onto the accepted WORK-016 Adapter SDK.

:class:`RanTechnologyAdapter` IMPLEMENTS the WORK-016 SDK's frozen
nine-operation :class:`adapters.contract.AdapterContract` over a
RAN-family :class:`RanContract` implementation.  This is how the RAN
family USES the accepted WORK-016 Adapter SDK rather than inventing
a second adapter framework (the explicit WORK-020 Architect
instruction): the generic core-side surface stays the SDK's; the
RAN-specific vocabulary (gNB provisioning, cell activation, the
adapter-private UE context/RNTI/DRB, radio bearer egress) stays
inside the RAN family's own seam -- exactly as the accepted WORK-019
5G-Core family keeps its PDU-session/SUPI vocabulary behind
``FiveGCoreContract``.

The Architect's layering (verbatim)::

    RAN implementation
        -> adapter translation
        -> generic AdapterContract
        -> ADCOS capabilities / resources / session mapping

This module is the middle box.  Authority notes (every operation):

* The bridge (and the implementation it adapts) is authoritative
  ONLY for the RAN technology state it controls -- its own
  gNB/cell/bearer/UE-context bookkeeping.  ADCOS remains
  authoritative for identity (WORK-004), topology (WORK-007),
  routing, policy, and session semantics (WORK-012): the bridge
  never mints, mutates, or re-derives any of them.
* The sacred, access-independent ``session_id`` (LOCK-006) crosses
  the bridge EXACTLY as given in ``bind_session`` -- a read-only
  passthrough, never mutated, never re-derived (LOCK-006; R1), and
  never echoed as a RAN handle.
* Every reference the bridge returns is an OPAQUE RAN-side handle
  (``ran:alloc:<digest>`` / ``ran:bearer:<digest>``) -- never core
  state and never the ``session_id``.

Sanctioned dependency direction (the SDK README, verbatim in
substance): "Implementations depend on ``AdapterContract`` + the
least-authority ``AdapterContext`` facade ... and on nothing else."
Accordingly this module imports ONLY
``from ..contract import AdapterContext, AdapterContract`` from the
SDK -- the stable interface, nothing else (no SDK errors module, no
SDK runtime, no SDK sandbox internals).  Everything else it uses is
the RAN family's own vocabulary.

Mediation note (honest): the bridge itself does NO mediation -- it
is a thin translation with NO state of its own beyond the label.
Failure isolation and contract-shape enforcement happen (a) inside
the RAN family, when the implementation is driven through
:class:`adapters.ran.sandbox.SandboxedRan`, and (b) when the bridge
is registered in the WORK-016 Adapter Runtime, via the SDK's own
:class:`adapters.sandbox.SandboxedAdapter` mediating every bridge
call.  RAN-side ``RanError`` reason codes therefore cross the SDK
seam only as far as the SDK's isolation allows (the SDK captures the
exception CLASS NAME, never message text -- LOCK-023); full
reason-code fidelity is preserved at the RAN family's own mediator.

Budget conversion (honest): the bridge forwards the SDK's budget
semantics by constructing a fresh :class:`RanContext` per call whose
instant is ``context.now()`` and whose step budget is the
AdapterContext's REMAINING budget (``context.steps_left()``) -- the
SDK budget is the single authority and the bridge never mints budget
of its own.  The RanContext surface it builds mirrors
``RAN_CONTEXT_SURFACE`` (ran_integration_id / now / charge /
steps_left).  The bridge charges nothing itself: per-operation step
charging is the MEDIATORS' job (the RAN sandbox's fixed
``STEP_CHARGES`` table, or the SDK sandbox's own charges when the
bridge runs under the WORK-016 runtime).
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from ..contract import AdapterContext, AdapterContract

from .contract import RanContext, RanContract, _BudgetExhausted
from .errors import RanError, RanReasonCode
from .manager import DEFAULT_INTEGRATION_ID
from .model import LinkMetricName, RanObservation

__all__ = ["RanTechnologyAdapter"]


class RanTechnologyAdapter(AdapterContract):
    """The WORK-016 SDK adapter over a :class:`RanContract`
    implementation.

    Constructed with the RAN implementation and an informational
    label.  Subclasses the accepted SDK's
    :class:`adapters.contract.AdapterContract` (isinstance-enforced)
    and satisfies its frozen ``CONTRACT_OPERATIONS`` surface; each SDK
    operation translates onto the RAN seam as documented in the
    module docstring.  The bridge owns NO state beyond the
    implementation reference and the label: a fresh
    :class:`RanContext` is built per call from the
    :class:`AdapterContext`'s injected instant and remaining step
    budget, so the SDK's budget semantics remain the single
    authority.
    """

    def __init__(
        self,
        implementation: RanContract,
        *,
        label: str = "ran-technology",
    ) -> None:
        if not isinstance(implementation, RanContract):
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "implementation must satisfy the RanContract ABC "
                "(isinstance enforced; no hasattr duck-typing)",
            )
        if not isinstance(label, str) or not label:
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "label must be a non-empty string",
            )
        self._implementation = implementation
        # Informational only (the SDK contract's label discipline):
        # never parsed, never branched on, never canonical state.
        self.label = label

    # ------------------------------------------------------------------
    # RanContext construction (per call, from the AdapterContext)
    # ------------------------------------------------------------------

    def _ran_context(self, context: AdapterContext) -> RanContext:
        """Build the RAN seam's least-authority context from the
        SDK's.

        The AdapterContext's injected instant and REMAINING step
        budget become the RanContext's instant/budget: the SDK budget
        is the single authority (the bridge never mints budget of
        its own).  The ``ran_integration_id`` is the RAN family's
        default integration instance id (the bridge is
        implementation-neutral bookkeeping, not an integration
        instance of its own).
        """
        return RanContext(
            ran_integration_id=DEFAULT_INTEGRATION_ID,
            instant=context.now(),
            step_budget=context.steps_left(),
        )

    def _call(self, context: AdapterContext, fn: Any) -> Any:
        """Delegate to the implementation with a fresh RanContext.

        The RAN seam's private ``_BudgetExhausted`` sentinel (the
        deterministic hang model raised by ``RanContext.charge``
        when the remaining budget is spent) is kept INSIDE the
        family: it is re-raised as the family's own
        ``RanError(BUDGET_EXHAUSTED)`` so the private sentinel class
        never crosses the SDK seam.  Whichever mediator is in charge
        (the RAN sandbox, or the SDK sandbox around this bridge)
        isolates the error as a typed failure value -- the bridge
        never lets an exception escape unmediated into core callers.
        """
        ran_context = self._ran_context(context)
        try:
            return fn(ran_context)
        except _BudgetExhausted:
            raise RanError(
                RanReasonCode.BUDGET_EXHAUSTED,
                "RAN implementation exhausted the adapter step budget "
                "(deterministic hang model; no wall clock is consulted)",
            ) from None

    # ------------------------------------------------------------------
    # The nine frozen WORK-016 SDK operations
    # ------------------------------------------------------------------

    def open(self, context: AdapterContext) -> None:
        """SDK ``open`` -> ``impl.open`` (bring the RAN integration
        up)."""
        return self._call(
            context, lambda ran: self._implementation.open(ran)
        )

    def capabilities(self) -> Sequence[str]:
        """SDK ``capabilities`` -> ``impl.capabilities``.

        RAN capability-id REFERENCES (``capability.access.ran.*``):
        exposure by reference into WORK-005 registry semantics, never
        minted here.  NOTE (honest disclosure): the frozen WORK-002
        capability-registry grammar today admits only the
        ``capability.core.*`` / ``capability.profile.*`` namespaces,
        so the SDK sandbox's registry classification would reject
        these references as invalid until WORK-005 admits the
        reserved ``capability.access.*`` namespace (a frozen-spec
        vocabulary change under ``spec/change-control.md`` -- never
        an adapter-family action).  The references therefore
        circulate at the RAN seam and its conformance surface today;
        the translation itself is and stays verbatim (exposure by
        reference is never rewritten).
        """
        return tuple(self._implementation.capabilities())

    def observe(self, context: AdapterContext) -> Mapping[str, int]:
        """SDK ``observe`` -> ``impl.observe`` mapped to the GENERIC
        link metrics.

        The :class:`RanObservation` carries the generic link-metric
        names (the WORK-016 ``LinkMetricName`` vocabulary mirrored as
        plain strings: link-up / rx-bytes-total / tx-bytes-total /
        rx-error-count / tx-error-count / retransmit-count); the
        projection is 1:1 over exactly the metrics the observation
        carries (nothing is fabricated, nothing is dropped).  The RAN
        resource/health/topology detail stays at the RAN seam (the
        SDK's generic observe surface carries metric counters only).

        Empty-RAN translation (honest): the RAN seam's ``observe``
        fails closed with ``RAN_UNAVAILABLE`` while no gNB/cell is
        provisioned (the frozen observation shape requires at least
        one reported cell).  The honest GENERIC translation of "no
        cell on air yet" is a link-down sample -- ``link_up: 0`` with
        all-zero counters -- exactly what the SDK's
        :class:`adapters.contract.GenericAdapter` reports for a
        down/unpopulated technology, so an adapter registered before
        any gNB is provisioned still satisfies the nine-op surface
        without fabricating radio state.  Only that specific
        reason code is translated; every other failure propagates to
        whichever mediator is in charge.
        """
        try:
            observation = self._call(
                context, lambda ran: self._implementation.observe(ran)
            )
        except RanError as exc:
            if exc.reason_code != RanReasonCode.RAN_UNAVAILABLE:
                raise
            return {
                LinkMetricName.LINK_UP: 0,
                LinkMetricName.RX_BYTES_TOTAL: 0,
                LinkMetricName.TX_BYTES_TOTAL: 0,
                LinkMetricName.RX_ERROR_COUNT: 0,
                LinkMetricName.TX_ERROR_COUNT: 0,
                LinkMetricName.RETRANSMIT_COUNT: 0,
            }
        if not isinstance(observation, RanObservation):
            raise RanError(
                RanReasonCode.CONTRACT_VIOLATION,
                "observe must return a RanObservation (the bridge "
                "translates; it does not fabricate metrics)",
            )
        return {
            metric: value
            for metric, value in observation.link_metrics.items()
        }

    def allocate(
        self,
        context: AdapterContext,
        *,
        kind: str,
        quantity_base: int,
        purpose: str,
    ) -> str:
        """SDK ``allocate`` -> ``impl.allocate`` (opaque
        ``ran:alloc:<digest>`` radio-capacity reservation; integer
        base units, WORK-016 semantics)."""
        return self._call(
            context,
            lambda ran: self._implementation.allocate(
                ran, kind=kind, quantity_base=quantity_base, purpose=purpose
            ),
        )

    def release(self, context: AdapterContext, technology_ref: str) -> None:
        """SDK ``release`` -> ``impl.release`` (release a previously
        returned radio-capacity reservation)."""
        return self._call(
            context,
            lambda ran: self._implementation.release(
                ran, technology_ref=technology_ref
            ),
        )

    def bind_session(
        self,
        context: AdapterContext,
        *,
        session_id: str,
        requirements: Optional[Mapping[str, Any]],
    ) -> str:
        """SDK ``bind_session`` -> ``impl.bind_session``.

        The sacred ``session_id`` crosses EXACTLY as given (read-only
        passthrough identity -- never mutated, never re-derived,
        LOCK-006; the returned bearer reference is mechanically
        checked against it at the RAN seam); ``requirements`` passes
        through as caller-supplied QoS DATA; the return is the opaque
        ``ran:bearer:<digest>`` reference (RAN-side identity, never
        ADCOS authority).
        """
        return self._call(
            context,
            lambda ran: self._implementation.bind_session(
                ran, session_id=session_id, requirements=requirements
            ),
        )

    def unbind_session(self, context: AdapterContext, bearer_ref: str) -> None:
        """SDK ``unbind_session`` -> ``impl.unbind_session`` (tear
        down a radio bearer by its opaque reference)."""
        return self._call(
            context,
            lambda ran: self._implementation.unbind_session(
                ran, bearer_ref=bearer_ref
            ),
        )

    def health(self) -> str:
        """SDK ``health`` -> ``impl.health``.

        The RAN family's health vocabulary (HEALTHY / DEGRADED /
        FAILED) is already the SDK's vocabulary; the report passes
        through verbatim (reported, never authoritative by itself --
        LOCK-017: the runtime computes the effective health from
        mediated outcomes).
        """
        return self._implementation.health()

    def close(self, context: AdapterContext) -> None:
        """SDK ``close`` -> ``impl.close`` (bring the RAN integration
        down; fails closed while bearers are outstanding -- the
        fail-closed semantics are the implementation's own and are
        preserved verbatim by this translation)."""
        return self._call(
            context, lambda ran: self._implementation.close(ran)
        )
