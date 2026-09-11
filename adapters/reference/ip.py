"""ADCOS IP integration family M007 reference adapter (R7-CORE-001).

The IP integration family's M007 surface.  Like the 5G Core family,
the accepted WORK-018 IP integration boundary never grew a WORK-016
SDK bridge (its own 10-op family contract and its own manager
surface); M007 adds one —
:class:`IPIntegrationTechnologyAdapter`, the deterministic reference
composition over the family RUNTIME (the
:class:`~adapters.ip.manager.IPIntegrationManager`), following the
accepted bridge pattern (the manager mediates every family call; the
adapter holds the manager reference and nothing else).  The 1.1
capability-oriented surface (:class:`adapters.capability.CapabilityAdapter`)
composes on top; NOTHING in the frozen family contract changes.

LOCK-112 (standard leverage — the mechanisms this family models, taken
from the family's own frozen citations, never reinvented here):

* ``rfc-4291-ipv6``  — RFC 4291 IPv6 addressing (the engine's
                       flow/prefix derivation);
* ``rfc-6437-flow``  — RFC 6437 IPv6 flow labels (the flow identity
                       the engine content-derives);
* ``rfc-6146-nat64`` — RFC 6146/6147/7915 NAT64/464XLAT (the family's
                       NAT adapter surface, modeled as DATA).

The tags are citation DATA carried in the 1.1 views
(:attr:`STANDARD_MECHANISMS`); the boundary never branches on them.

Nine-op translation (SDK -> family runtime, each mediated):

* ``open``            -> the manager's idempotent ``open`` (a mediated
                         engine open)
* ``capabilities``    -> the reference capability ladder (declared
                         profile-namespace references; exposure is by
                         reference, never minted)
* ``observe``         -> the honest link-metric projection of the
                         mediated manager health (link-up mirrors
                         health; per-flow counters are family-native
                         ops the SDK surface has no flow parameter
                         for, so counters are honestly zero — the
                         backhaul-bridge pattern)
* ``allocate``        -> the deterministic reference
                         route-capacity model (adapter-local table of
                         ``ip:route-reservation:<n>`` refs over the
                         mapped WORK-008 rate kinds — the
                         GenericAdapter reference pattern)
* ``release``         -> release a reservation ref (fail closed on
                         unknown)
* ``bind_session``    -> mediated manager ``bind_session``; the
                         caller's requirements DATA carries the IP
                         binding coordinates (``transport_ref`` — an
                         opaque WORK-017 transport reference, and
                         ``route_ref`` — an opaque WORK-011 path
                         fingerprint, both consumed as DATA); the
                         return is the OPAQUE
                         ``binding_id`` (the family's content-derived
                         IP binding identity)
* ``unbind_session``  -> mediated manager ``close_binding`` (the
                         family's per-binding teardown)
* ``health``          -> the manager's effective health translated
                         onto the SDK's three-state vocabulary
* ``close``           -> honest no-op (the manager lifecycle belongs
                         to the composition root — the WORK-022
                         backhaul-bridge precedent)

Determinism (LOCK-119): sequence counters, injected instants, fixed
step charges; no wall clock, no randomness, no network.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence

from ..contract import AdapterContext, AdapterContract
from ..errors import AdapterError, AdapterReasonCode
from ..model import (
    AdapterDescriptor,
    AdapterSecurityState,
    HealthState,
    LinkMetricName,
    ResourceMappingEntry,
    derive_adapter_id,
)
from ..ip.manager import IPIntegrationManager

#: The LOCK-112 standard-mechanism tags this family's reference
#: adapter models (citation DATA, never branch input).
STANDARD_MECHANISMS: tuple = (
    "rfc-4291-ipv6",
    "rfc-6437-flow",
    "rfc-6146-nat64",
)

#: The reference access technology for this family (UNKNOWN_BUT_
#: WELL_FORMED in the WORK-002 grammar — the IP integration boundary
#: enters as DATA; disclosed, never coerced).
REFERENCE_TECHNOLOGY_ID = "access.ip.ipv6"

#: Default instance label of the reference composition.
REFERENCE_LABEL = "ip-reference-0"

#: Capability references the reference adapter declares and exposes
#: (UNKNOWN_BUT_WELL_FORMED in the WORK-002 grammar — preserved).
REFERENCE_CAPABILITIES: tuple = (
    "capability.profile.ip.flow",
    "capability.profile.ip.route-binding",
)

#: The reference route-capacity mapping (integer mbps).
REFERENCE_ROUTE_MBPS = 100

#: The reference binding coordinates (family wiring DATA the caller
#: passes to the 1.1 activate/reconfigure operations — opaque WORK-017
#: transport and WORK-011 route references, consumed as DATA).
REFERENCE_BINDING_REQUIREMENTS: Mapping[str, Any] = {
    "transport_ref": "transport-m007-0",
    "route_ref": "route-m007-0",
}

#: Deterministic step charges per translated operation (budget model).
STEP_CHARGES: Dict[str, int] = {
    "open": 4,
    "capabilities": 1,
    "observe": 2,
    "allocate": 10,
    "release": 4,
    "bind_session": 8,
    "unbind_session": 4,
    "health": 1,
    "close": 4,
}

#: Requirement keys the adapter consumes as the IP binding
#: coordinates (translated into the manager's explicit parameters;
#: the LEFTOVER map forwards as caller DATA).
_REQUIREMENT_KEYS = ("transport_ref", "route_ref")


def reference_descriptor(label: str = REFERENCE_LABEL) -> AdapterDescriptor:
    """The reference registration descriptor for the IP family."""
    return AdapterDescriptor(
        adapter_id=derive_adapter_id(REFERENCE_TECHNOLOGY_ID, label),
        access_technology_id=REFERENCE_TECHNOLOGY_ID,
        supported_profile_versions=("v1-0-0",),
        capabilities=REFERENCE_CAPABILITIES,
        resource_mapping=(
            ResourceMappingEntry(
                technology_resource="route-flow-capacity",
                kind="bandwidth",
                unit="mbps",
                quantity=REFERENCE_ROUTE_MBPS,
                availability="reservation-based",
            ),
        ),
        security_state=AdapterSecurityState(
            profile="baseline",
            credential_slots=("ip-integration-credentials",),
            attested=False,
        ),
    )


class IPIntegrationTechnologyAdapter(AdapterContract):
    """The IP integration family's WORK-016 SDK surface over the
    family RUNTIME (the
    :class:`~adapters.ip.manager.IPIntegrationManager`).

    Holds the manager reference and the deterministic reservation
    table only; every family call is mediated by the manager's own
    sandbox.  The binding requirements map carries the opaque
    transport/route coordinates as DATA; no IP address, prefix, or
    flow object ever crosses the SDK boundary (LOCK-110 — the flow
    identity stays family-side).
    """

    label = "ip-integration-technology"

    def __init__(self, manager: IPIntegrationManager) -> None:
        if not isinstance(manager, IPIntegrationManager):
            from ..ip.errors import IPIntegrationError, IPIntegrationReasonCode

            raise IPIntegrationError(
                IPIntegrationReasonCode.INVALID_INPUT,
                "manager must be an IPIntegrationManager (the adapter "
                "adapts the family RUNTIME)",
            )
        self._manager = manager
        self._sequence = 0
        self._reservations: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _charge(self, context: AdapterContext, operation: str) -> None:
        context.charge(STEP_CHARGES.get(operation, 1))

    def _family_failure(self, operation: str, detail: str) -> None:
        """Re-raise an isolated family-mediated failure as the
        family's typed error so the SDK sandbox isolates it (the SDK
        captures the exception CLASS NAME, never message text --
        LOCK-023; the family mediator already recorded the typed
        failure).  Never returns."""
        from ..ip.errors import IPIntegrationError, IPIntegrationReasonCode

        raise IPIntegrationError(
            IPIntegrationReasonCode.IPINTEGRATION_FAILURE,
            "%s: %s" % (operation, detail),
        )

    @staticmethod
    def _coordinates(
        requirements: Optional[Mapping[str, Any]]
    ) -> tuple:
        """Read the caller's IP binding coordinates (fail closed on
        malformed coordinates)."""
        if not isinstance(requirements, Mapping):
            raise AdapterError(
                AdapterReasonCode.INVALID_INPUT,
                "bind_session requirements must be a mapping carrying "
                "the IP binding coordinates (transport_ref/route_ref) -- "
                "the generic SDK surface has no route parameters",
            )
        transport_ref = requirements.get("transport_ref")
        route_ref = requirements.get("route_ref")
        for label, value in (
            ("transport_ref", transport_ref),
            ("route_ref", route_ref),
        ):
            if not isinstance(value, str) or not value:
                raise AdapterError(
                    AdapterReasonCode.INVALID_INPUT,
                    "bind_session requirements must carry a non-empty "
                    "'%s' string (opaque reference DATA)" % label,
                )
        return transport_ref, route_ref

    # ------------------------------------------------------------------
    # Nine-op SDK surface
    # ------------------------------------------------------------------

    def open(self, context: AdapterContext) -> None:
        self._charge(context, "open")
        result = self._manager.open(now=context.now())
        if not result.ok:
            self._family_failure("open", "IP integration open failed")

    def capabilities(self) -> Sequence[str]:
        return REFERENCE_CAPABILITIES

    def observe(self, context: AdapterContext) -> Mapping[str, int]:
        self._charge(context, "observe")
        result = self._manager.health(now=context.now())
        if not result.ok:
            self._family_failure("observe", "mediated health probe failed")
        healthy = result.value.get("effective") == "HEALTHY"
        return {
            LinkMetricName.LINK_UP: 1 if healthy else 0,
            LinkMetricName.RX_BYTES_TOTAL: 0,
            LinkMetricName.TX_BYTES_TOTAL: 0,
            LinkMetricName.RX_ERROR_COUNT: 0,
            LinkMetricName.TX_ERROR_COUNT: 0,
            LinkMetricName.RETRANSMIT_COUNT: 0,
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
        if not isinstance(kind, str) or kind not in ("bandwidth", "backhaul"):
            raise AdapterError(
                AdapterReasonCode.MAPPING_INVALID,
                "the IP reference reservation model maps the WORK-008 "
                "rate kinds (bandwidth/backhaul)",
            )
        if isinstance(quantity_base, bool) or not isinstance(quantity_base, int):
            raise AdapterError(
                AdapterReasonCode.INVALID_INPUT,
                "quantity_base must be an integer",
            )
        if quantity_base <= 0:
            raise AdapterError(
                AdapterReasonCode.INVALID_INPUT,
                "quantity_base must be positive",
            )
        if not isinstance(purpose, str) or not purpose:
            raise AdapterError(
                AdapterReasonCode.INVALID_INPUT,
                "purpose must be a non-empty string",
            )
        self._sequence += 1
        ref = "ip:route-reservation:%06d" % self._sequence
        self._reservations[ref] = purpose
        return ref

    def release(self, context: AdapterContext, technology_ref: str) -> None:
        self._charge(context, "release")
        if technology_ref not in self._reservations:
            raise AdapterError(
                AdapterReasonCode.ALLOCATION_UNKNOWN,
                "unknown IP reservation ref (already released?)",
            )
        del self._reservations[technology_ref]

    def bind_session(
        self,
        context: AdapterContext,
        *,
        session_id: str,
        requirements: Optional[Mapping[str, Any]],
    ) -> str:
        self._charge(context, "bind_session")
        if not isinstance(session_id, str) or not session_id:
            raise AdapterError(
                AdapterReasonCode.INVALID_INPUT,
                "session_id must be a non-empty string",
            )
        transport_ref, route_ref = self._coordinates(requirements)
        result = self._manager.bind_session(
            session_id=session_id,
            transport_ref=transport_ref,
            route_ref=route_ref,
            now=context.now(),
        )
        if not result.ok:
            self._family_failure(
                "bind_session", "mediated IP flow binding failed"
            )
        return result.value.binding_id

    def unbind_session(self, context: AdapterContext, bearer_ref: str) -> None:
        self._charge(context, "unbind_session")
        if not isinstance(bearer_ref, str) or not bearer_ref:
            raise AdapterError(
                AdapterReasonCode.INVALID_INPUT,
                "bearer_ref must be a non-empty string",
            )
        result = self._manager.close_binding(
            ip_binding_ref=bearer_ref, now=context.now()
        )
        if not result.ok:
            self._family_failure(
                "unbind_session", "mediated IP binding close failed"
            )

    def health(self) -> str:
        """Instant-free mediated-outcomes projection (LOCK-017: the
        report is data; the SDK runtime computes the effective state
        from its own counters).  Mirrors the family sandbox's
        documented consecutive-failure thresholds (DEGRADED at 2,
        FAILED at 5) from the manager's mediated counters."""
        from ..ip.sandbox import FAILURE_THRESHOLD_DEGRADED, FAILURE_THRESHOLD_FAILED

        consecutive = self._manager.engine_consecutive_failures()
        if consecutive >= FAILURE_THRESHOLD_FAILED:
            return HealthState.FAILED
        if consecutive >= FAILURE_THRESHOLD_DEGRADED:
            return HealthState.DEGRADED
        return HealthState.HEALTHY

    def close(self, context: AdapterContext) -> None:
        self._charge(context, "close")
        # Honest no-op (the manager lifecycle belongs to the
        # composition root — the WORK-022 backhaul-bridge precedent).


def mount_reference(
    session_reader: Any,
    topology_reader: Any,
    *,
    now: str,
    label: str = REFERENCE_LABEL,
) -> tuple:
    """Compose the IP integration family reference adapter
    (deterministic).

    Wires the accepted family runtime: one
    :class:`IPIntegrationManager` (read-only session + topology
    facades injected) over the deterministic
    :class:`~adapters.ip.engine.ReferenceIPIntegrationEngine`.

    Returns ``(implementation, descriptor, binding_requirements)``:
    the :class:`IPIntegrationTechnologyAdapter` to register with the
    :class:`~adapters.runtime.AdapterRuntime`, the reference
    descriptor, and the canonical binding coordinates
    (:data:`REFERENCE_BINDING_REQUIREMENTS`) the caller passes to the
    1.1 ``activate``/``reconfigure`` operations — family wiring DATA,
    never an authority.
    """
    from ..ip.engine import ReferenceIPIntegrationEngine

    manager = IPIntegrationManager(
        session_reader=session_reader,
        topology_reader=topology_reader,
        implementation=ReferenceIPIntegrationEngine(),
        integration_id="adcos:ipint:m007",
    )
    return (
        IPIntegrationTechnologyAdapter(manager),
        reference_descriptor(label),
        REFERENCE_BINDING_REQUIREMENTS,
    )
