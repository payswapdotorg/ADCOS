"""WORK-038 future-IMT adapter: the deterministic reference bridge.

The hypothetical IMT-2030 technology implementation for the synthetic
conformance profile.  It follows the sanctioned SDK-bridge pattern
exactly (the W033 ``agent.bridge`` precedent over the W016 contract):

- imports ONLY ``AdapterContract`` and ``AdapterContext`` from the
  core (nothing else -- the mechanical import audit in the battery
  pins this);
- holds only deterministic local state (sequence counters, opaque
  reference ledgers, an open flag);
- charges the deterministic step budget for every operation (the hang
  model; no wall-clock timeouts exist anywhere in this layer);
- returns OPAQUE technology references (``imt2030:...`` strings) that
  the core never interprets;
- implements NO radio, NO 3GPP state machines, NO vendor APIs, and NO
  real IMT-2030 behavior (LOCK-016/LOCK-017; the handoff's "synthetic
  conformance evidence" class).  It is a deterministic model of a
  hypothetical technology's CONTRACT shape, not a model of the
  technology itself.

The descriptor factory builds the WORK-016 ``AdapterDescriptor`` from
a validated profile declaration: the technology enters the runtime as
DATA (``AdapterRuntime.register``), never as a core schema change.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence

from adapters import (
    AdapterContract,
    AdapterContext,
    AdapterDescriptor,
    AdapterSecurityState,
    ResourceMappingEntry,
    derive_adapter_id,
)

from .errors import FutureError, FutureReasonCode
from .model import FutureProfileDeclaration

__all__ = [
    "FUTURE_ADAPTER_LABEL",
    "STEP_CHARGES",
    "FutureTechnologyAdapter",
    "future_descriptor",
]

#: Informational implementation label (never parsed, never branched on).
FUTURE_ADAPTER_LABEL = "future-imt2030-study"

#: Deterministic step charges per contract operation (the hang model).
STEP_CHARGES: Dict[str, int] = {
    "open": 4,
    "capabilities": 1,
    "observe": 2,
    "allocate": 10,
    "release": 4,
    "bind_session": 6,
    "unbind_session": 3,
    "health": 1,
    "close": 4,
}


def future_descriptor(
    profile: FutureProfileDeclaration, instance_label: str
) -> AdapterDescriptor:
    """Build the WORK-016 descriptor for one future-profile instance.

    The mapping translates the declared technology capacity into the
    WORK-008 resource model (mapping only -- never accounting), the
    security state is structure only (slot names, LOCK-023), and the
    adapter id is derived from the technology id + instance label so
    the same declaration always yields the same id (duplicate
    registrations collide visibly).
    """
    if not isinstance(profile, FutureProfileDeclaration):
        raise FutureError(
            FutureReasonCode.INVALID_INPUT,
            "profile must be a FutureProfileDeclaration",
        )
    adapter_id = derive_adapter_id(profile.technology_id, instance_label)
    return AdapterDescriptor(
        adapter_id=adapter_id,
        access_technology_id=profile.technology_id,
        supported_profile_versions=profile.profile_versions,
        capabilities=profile.capability_references,
        resource_mapping=(
            ResourceMappingEntry(
                technology_resource=profile.technology_resource,
                kind=profile.resource_kind,
                unit=profile.resource_unit,
                quantity=profile.resource_quantity,
                availability="continuous",
            ),
        ),
        security_state=AdapterSecurityState(
            profile=profile.security_profile,
            credential_slots=profile.credential_slots,
            attested=False,
        ),
        extensions={
            "work-item": "WORK-038",
            "profile-digest": profile.digest(),
        },
    )


class FutureTechnologyAdapter(AdapterContract):
    """The deterministic hypothetical-technology adapter.

    A synthetic, fully contract-shaped implementation of the
    hypothetical future access technology: sequence counters,
    injected instants, fixed step charges, opaque ledgers.  No
    randomness, no wall clock, no network, no vendor SDK -- the
    battery's purity audit pins all of this.  All adapter-side faults
    surface through the sandbox as typed failure values.
    """

    label = FUTURE_ADAPTER_LABEL

    __slots__ = ("_sequence", "_open", "_refs", "_bearer_sessions", "_capabilities")

    def __init__(self, capabilities: Optional[Sequence[str]] = None) -> None:
        self._sequence = 0
        self._open = False
        self._refs: Dict[str, str] = {}
        self._bearer_sessions: Dict[str, str] = {}
        self._capabilities: Sequence[str] = tuple(capabilities or ())

    # -- helpers -----------------------------------------------------------

    def _charge(self, context: AdapterContext, operation: str) -> None:
        context.charge(STEP_CHARGES.get(operation, 1))

    def _next(self) -> int:
        self._sequence += 1
        return self._sequence

    def _require_open(self) -> None:
        if not self._open:
            raise FutureError(
                FutureReasonCode.NOT_OPEN,
                "future adapter technology is not open",
            )

    # -- the nine contract operations --------------------------------------

    def open(self, context: AdapterContext) -> None:
        self._charge(context, "open")
        self._open = True

    def capabilities(self) -> Sequence[str]:
        if not self._open:
            return ()
        return tuple(self._capabilities)

    def observe(self, context: AdapterContext) -> Mapping[str, int]:
        self._charge(context, "observe")
        self._require_open()
        return {
            "link-up": 1,
            "rx-bytes-total": 1000 * self._sequence,
            "tx-bytes-total": 1000 * self._sequence,
            "rx-error-count": 0,
            "tx-error-count": 0,
            "retransmit-count": 0,
        }

    def allocate(
        self,
        context: AdapterContext,
        *,
        kind: str,
        quantity_base: int,
        purpose: str,
    ) -> str:
        self._charge(context, "allocate")
        self._require_open()
        if not kind:
            raise FutureError(
                FutureReasonCode.INVALID_INPUT,
                "allocation kind is required",
            )
        if isinstance(quantity_base, bool) or not isinstance(quantity_base, int):
            raise FutureError(
                FutureReasonCode.INVALID_INPUT,
                "allocation quantity must be an integer",
            )
        if quantity_base <= 0:
            raise FutureError(
                FutureReasonCode.INVALID_INPUT,
                "allocation quantity must be positive",
            )
        reference = "imt2030:allocation:%06d" % self._next()
        self._refs[reference] = purpose
        return reference

    def release(self, context: AdapterContext, technology_ref: str) -> None:
        self._charge(context, "release")
        self._require_open()
        if technology_ref not in self._refs:
            raise FutureError(
                FutureReasonCode.ALLOCATION_UNKNOWN,
                "future adapter does not know technology ref (already released?)",
            )
        del self._refs[technology_ref]

    def bind_session(
        self,
        context: AdapterContext,
        *,
        session_id: str,
        requirements: Optional[Mapping[str, Any]],
    ) -> str:
        self._charge(context, "bind_session")
        self._require_open()
        if not session_id:
            raise FutureError(
                FutureReasonCode.INVALID_INPUT,
                "session_id is required",
            )
        bearer = "imt2030:bearer:%06d" % self._next()
        self._bearer_sessions[bearer] = session_id
        return bearer

    def unbind_session(self, context: AdapterContext, bearer_ref: str) -> None:
        self._charge(context, "unbind_session")
        self._require_open()
        if bearer_ref not in self._bearer_sessions:
            raise FutureError(
                FutureReasonCode.BINDING_UNKNOWN,
                "future adapter does not know bearer ref (already unbound?)",
            )
        del self._bearer_sessions[bearer_ref]

    def health(self) -> str:
        if not self._open:
            return "FAILED"
        if self._refs:
            return "DEGRADED"
        return "HEALTHY"

    def close(self, context: AdapterContext) -> None:
        self._charge(context, "close")
        self._open = False
        self._refs = {}
        self._bearer_sessions = {}
