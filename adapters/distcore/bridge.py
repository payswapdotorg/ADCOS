"""ADCOS distributed-core WORK-016 SDK bridge (WORK-024): the generic
nine-op adapter surface.

:class:`DistCoreTechnologyAdapter` subclasses the accepted WORK-016
:class:`~adapters.contract.AdapterContract` and routes every SDK
operation through the
:class:`~adapters.distcore.manager.DistributedCoreManager` (and its
:class:`~adapters.distcore.sandbox.SandboxedBreakoutProvider`
mediators) -- NEVER around it and NEVER through a raw provider
implementation.  The bridge holds ONLY the manager and a label
(mirroring the WORK-021/022/023 bridge shapes).

The nine-op translation (the generic SDK surface carries no
distributed-core parameters -- every breakout-specific coordinate
rides the requirements mapping as DATA):

* ``open``    -> mediated ``manager.health`` (the distributed-core
                 boundary's readiness);
* ``capabilities`` -> ``manager.capabilities()`` (the informational
                 ladder, including the frozen
                 ``capability.core.local-breakout`` registry id once
                 a LOCAL-mode provider is registered; the SDK runtime
                 filters it to the descriptor's declared set);
* ``observe`` -> mediated ``manager.observe`` projected onto the six
                 generic WORK-016 link metrics (the observation's
                 samples already ARE that vocabulary);
* ``allocate`` -> mediated ``manager.allocate`` (a breakout-capacity
                 ledger admission in WORK-008 base units --
                 bits/second of gateway egress capacity over the
                 bps-based rate kinds ``bandwidth``/``backhaul``)
                 returning the OPAQUE ``distcore:alloc:<hex>`` ref;
* ``release`` -> dispatch on the technology ref's kind: a
                 ``distcore:alloc:`` ref releases the admission, a
                 ``distcore:breakout:`` ref releases the breakout, a
                 ``distcore:gateway:`` ref closes the gateway;
* ``bind_session`` -> mediated ``manager.establish_breakout``; the
                 requirements map carries the breakout coordinates
                 (``decision_ref`` -- a policy determination ALREADY
                 applied through the manager's authoritative
                 ``apply_policy_decision`` path, and ``path_ref`` --
                 an ALREADY-REGISTERED ordinary WORK-011 path
                 fingerprint; both REQUIRED and both consumed here so
                 nothing unverified is smuggled through the SDK
                 surface);
* ``unbind_session`` -> mediated ``manager.release_breakout``;
* ``health``  -> ``manager.computed_health()`` (NOT_RUNNING maps to
                 FAILED on the SDK surface);
* ``close``   -> honest documented no-op (the manager's lifecycle is
                 the integrator's; the SDK close never silently
                 kills live breakouts -- mirrors the WORK-021/022/023
                 bridges).

The only import crossing the family boundary is the WORK-016 SDK
contract itself (``from ..contract import AdapterContext,
AdapterContract``) -- the sanctioned additive bridging pattern.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from ..contract import AdapterContext, AdapterContract
from ..errors import AdapterError, AdapterReasonCode

from .errors import DISTCORE_PREFIX, DistCoreError, DistCoreReasonCode
from .manager import DistributedCoreManager
from .validation import validate_opaque_ref

__all__ = ["DistCoreTechnologyAdapter"]

#: The bridge's documented requirement keys (the breakout
#: coordinates the generic SDK surface carries as DATA).
_REQUIREMENT_DECISION_REF = "decision_ref"
_REQUIREMENT_PATH_REF = "path_ref"
_BRIDGE_REQUIREMENT_KEYS = (
    _REQUIREMENT_DECISION_REF,
    _REQUIREMENT_PATH_REF,
)

#: The WORK-008 bps-based rate kinds the breakout-capacity admission
#: accepts (mirrors the engines' ``RATE_KINDS_BPS``).
from .engine import RATE_KINDS_BPS  # noqa: E402


def _raise_failure(operation: str, detail: str) -> None:
    """Convert a caller-side distributed-core error into the SDK's
    failure vocabulary so the SDK sandbox isolates it (never
    propagates a family exception through the SDK boundary)."""
    raise AdapterError(AdapterReasonCode.ADAPTER_FAILURE, detail)


def _ref_kind(technology_ref: str) -> str:
    """The distributed-core ref's kind segment
    (gateway/breakout/binding/decision/alloc)."""
    validate_opaque_ref(technology_ref)
    return technology_ref.split(":", 2)[1]


class DistCoreTechnologyAdapter(AdapterContract):
    """The distributed-core family's WORK-016 SDK surface over the
    DistributedCoreManager."""

    label = "distcore-technology"

    def __init__(
        self,
        manager: DistributedCoreManager,
        *,
        label: str = "distcore-technology",
    ) -> None:
        if not isinstance(manager, DistributedCoreManager):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "DistCoreTechnologyAdapter requires a "
                "DistributedCoreManager (the mediated manager; never "
                "a raw provider implementation)",
            )
        self._manager = manager
        self.label = label

    # ------------------------------------------------------------------
    # Nine-op SDK surface
    # ------------------------------------------------------------------

    def open(self, context: AdapterContext) -> None:
        result = self._manager.health(now=context.now())
        if not result.ok:
            _raise_failure("open", "distributed-core boundary is not healthy")

    def capabilities(self) -> Sequence[str]:
        return self._manager.capabilities()

    def observe(self, context: AdapterContext) -> Mapping[str, int]:
        result = self._manager.observe(now=context.now())
        if not result.ok:
            _raise_failure(
                "observe", "provider observation failed on the "
                "distributed-core implementation"
            )
        observation = result.value
        # The observation's samples already ARE the six generic
        # WORK-016 link-metric names (the family vocabulary mirrors
        # the SDK vocabulary); the bridge surfaces them directly and
        # adds nothing.
        mapping: dict = {name: value for name, value in observation.samples}
        return mapping

    def allocate(
        self,
        context: AdapterContext,
        *,
        kind: str,
        quantity_base: int,
        purpose: str,
    ) -> str:
        if not isinstance(kind, str) or not kind:
            _raise_failure(
                "allocate", "kind must be a non-empty WORK-008 resource "
                "kind name (breakout capacity maps onto the bps-based "
                "rate kinds %s)" % (list(RATE_KINDS_BPS),)
            )
        if isinstance(quantity_base, bool) or not isinstance(
            quantity_base, int
        ):
            _raise_failure(
                "allocate", "quantity_base must be an integer "
                "(bits/second base units)"
            )
        if not isinstance(purpose, str) or not purpose:
            _raise_failure("allocate", "purpose must be a non-empty string")
        result = self._manager.allocate(
            now=context.now(),
            kind=kind,
            quantity_base=quantity_base,
            purpose=purpose,
        )
        if not result.ok:
            _raise_failure(
                "allocate",
                "breakout-capacity admission failed (%s)" % result.reason,
            )
        return result.value.allocation_ref

    def release(self, context: AdapterContext, technology_ref: str) -> None:
        if not isinstance(technology_ref, str) or not technology_ref:
            _raise_failure("release", "technology_ref must be a %s ref" % DISTCORE_PREFIX)
        try:
            kind = _ref_kind(technology_ref)
        except DistCoreError:
            _raise_failure(
                "release", "technology_ref must be a %s ref" % DISTCORE_PREFIX
            )
        now = context.now()
        if kind == "alloc":
            result = self._manager.release(
                now=now, allocation_ref=technology_ref
            )
        elif kind == "breakout":
            result = self._manager.release_breakout(
                now=now, breakout_ref=technology_ref
            )
        elif kind == "gateway":
            result = self._manager.close_gateway(
                now=now, gateway_ref=technology_ref
            )
        else:
            _raise_failure(
                "release",
                "%s ref kind %r is not releasable through the SDK "
                "surface (decisions are policy provenance, bindings "
                "are chain history)" % (DISTCORE_PREFIX, kind),
            )
            return
        if not result.ok:
            _raise_failure(
                "release", "release failed (%s)" % result.reason
            )

    def bind_session(
        self,
        context: AdapterContext,
        *,
        session_id: str,
        requirements: Optional[Mapping[str, Any]] = None,
    ) -> str:
        if not isinstance(session_id, str) or not session_id:
            _raise_failure("bind_session", "session_id must be non-empty")
        coordinates: dict = {}
        if requirements is not None:
            if not isinstance(requirements, Mapping):
                _raise_failure(
                    "bind_session", "requirements must be a mapping"
                )
            for key, value in requirements.items():
                if key not in _BRIDGE_REQUIREMENT_KEYS:
                    _raise_failure(
                        "bind_session",
                        "unknown requirement key %r (bridge keys: %s)"
                        % (key, list(_BRIDGE_REQUIREMENT_KEYS)),
                    )
                coordinates[key] = value
        for required in _BRIDGE_REQUIREMENT_KEYS:
            if required not in coordinates:
                _raise_failure(
                    "bind_session",
                    "the breakout coordinates are REQUIRED (requirement "
                    "keys %s -- a policy determination ALREADY applied "
                    "through the manager's authoritative "
                    "apply_policy_decision path, and an ALREADY-"
                    "REGISTERED ordinary WORK-011 path fingerprint)"
                    % (list(_BRIDGE_REQUIREMENT_KEYS),),
                )
        result = self._manager.establish_breakout(
            now=context.now(),
            session_id=session_id,
            decision_ref=coordinates[_REQUIREMENT_DECISION_REF],
            path_ref=coordinates[_REQUIREMENT_PATH_REF],
        )
        if not result.ok:
            _raise_failure(
                "bind_session", "establish failed (%s)" % result.reason
            )
        return result.value.breakout_ref

    def unbind_session(self, context: AdapterContext, bearer_ref: str) -> None:
        if not isinstance(bearer_ref, str) or not bearer_ref:
            _raise_failure("unbind_session", "bearer_ref must be non-empty")
        result = self._manager.release_breakout(
            now=context.now(), breakout_ref=bearer_ref
        )
        if not result.ok:
            _raise_failure(
                "unbind_session", "release failed (%s)" % result.reason
            )

    def health(self) -> str:
        health = self._manager.computed_health()
        if health == "NOT_RUNNING":
            return "FAILED"
        return health

    def close(self, context: AdapterContext) -> None:
        # Honest documented no-op: the integration lifecycle belongs
        # to the integrator (DistributedCoreManager.close); an SDK
        # close never silently kills live breakouts (mirrors the
        # WORK-021/022/023 bridges).
        return None
