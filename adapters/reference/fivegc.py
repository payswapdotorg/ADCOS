"""ADCOS 5G Core family M007 reference adapter (R7-CORE-001).

The 5G Core family's M007 surface.  Unlike the backhaul/mesh/RAN/Wi-Fi
families, the WORK-019 5G Core family never grew a WORK-016 SDK
bridge (its 12-op family contract has no natural nine-op mapping); M007
adds one — :class:`FiveGCTechnologyAdapter`, the deterministic
reference composition over the family RUNTIME (the
:class:`~adapters.fivegc.manager.FiveGCoreManager`), following the
accepted bridge pattern (the manager mediates every family call; the
adapter holds the manager reference and nothing else).  The 1.1
capability-oriented surface (:class:`adapters.capability.CapabilityAdapter`)
composes on top; NOTHING in the frozen family contract changes.

LOCK-112 (standard leverage — the mechanisms this family models, taken
from the family's own frozen citations, never reinvented here):

* ``3gpp-ts-23.501`` — 3GPP TS 23.501 5G System architecture (PDU
                        sessions, S-NSSAI, DNN, 5QI shapes as DATA);
* ``3gpp-ts-23.316`` — 3GPP TS 23.316 ATSSS-style access steering
                        (the reference reconfiguration semantics:
                        a requirements change is a re-bind of the
                        SAME session with new QoS DATA).

The tags are citation DATA carried in the 1.1 views
(:attr:`STANDARD_MECHANISMS`); the boundary never branches on them.

Nine-op translation (SDK -> family runtime, each mediated):

* ``open``            -> a mediated manager health probe
* ``capabilities``    -> the reference capability ladder (declared
                         profile-namespace references; exposure is
                         by reference, never minted)
* ``observe``         -> the honest link-metric projection of the
                         mediated manager health (link-up mirrors
                         health; per-PDU-session counters are
                         family-native ops the SDK surface has no
                         session parameter for, so counters are
                         honestly zero — the backhaul-bridge pattern)
* ``allocate``        -> the deterministic reference QoS-reservation
                         model (adapter-local table of
                         ``fivegc:qos-reservation:<n>`` refs over the
                         mapped WORK-008 rate kinds — the
                         GenericAdapter reference pattern)
* ``release``         -> release a reservation ref (fail closed on
                         unknown)
* ``bind_session``    -> mediated manager ``provision_subscriber`` +
                         ``bind_session``; the caller's requirements
                         DATA carries the 5G binding coordinates
                         (``supi``, ``snssai`` {sst, sd}, ``dnn``)
                         which the adapter translates into the
                         family's typed values; the return is the
                         OPAQUE ``pdu_session_ref``
* ``unbind_session``  -> mediated manager ``release_pdu_session``
* ``health``          -> the manager's computed health translated
                         onto the SDK's three-state vocabulary
* ``close``           -> honest no-op (the family expresses close
                         per binding; the manager lifecycle belongs
                         to the composition root)

Determinism (LOCK-119): fixed reference subscriber profile, sequence
counters, injected instants, fixed step charges; no wall clock, no
randomness, no network, no credential material (LOCK-023 — the
credential slot stays a NAME).
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
from ..fivegc.errors import FiveGCoreError, FiveGCoreReasonCode
from ..fivegc.manager import FiveGCoreManager
from ..fivegc.model import Dnn, Snssai

#: The LOCK-112 standard-mechanism tags this family's reference
#: adapter models (citation DATA, never branch input).
STANDARD_MECHANISMS: tuple = (
    "3gpp-ts-23.501",
    "3gpp-ts-23.316",
)

#: The reference access technology for this family (UNKNOWN_BUT_
#: WELL_FORMED in the WORK-002 grammar — the 5G Core integration
#: enters as DATA; disclosed, never coerced).
REFERENCE_TECHNOLOGY_ID = "access.3gpp.5gc"

#: Default instance label of the reference composition.
REFERENCE_LABEL = "fivegc-reference-0"

#: Capability references the reference adapter declares and exposes
#: (UNKNOWN_BUT_WELL_FORMED in the WORK-002 grammar — preserved).
REFERENCE_CAPABILITIES: tuple = (
    "capability.profile.fivegc.pdu-session",
    "capability.profile.fivegc.subscriber-provisioning",
)

#: The reference QoS-reservation capacity (integer mbps).
REFERENCE_QOS_MBPS = 100

#: The reference subscriber binding coordinates (family wiring DATA
#: the caller passes to the 1.1 activate/reconfigure operations; the
#: SUPI shape is the family's own documented test shape — no real
#: subscriber identifier, no credential material).
REFERENCE_BINDING_REQUIREMENTS: Mapping[str, Any] = {
    "supi": "imsi-001010000000001",
    "snssai": {"sst": 1, "sd": "010203"},
    "dnn": "internet",
}

#: The credential slot NAME the reference profile uses (LOCK-023: a
#: name, never material).
_REFERENCE_CREDENTIAL_SLOT = "subscriber-credentials"

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

#: Requirement keys the adapter consumes as the 5G binding
#: coordinates (translated into the family's typed values; the
#: LEFTOVER map forwards as QoS DATA).
_REQUIREMENT_KEYS = ("supi", "snssai", "dnn")


def reference_descriptor(label: str = REFERENCE_LABEL) -> AdapterDescriptor:
    """The reference registration descriptor for the 5G Core family."""
    return AdapterDescriptor(
        adapter_id=derive_adapter_id(REFERENCE_TECHNOLOGY_ID, label),
        access_technology_id=REFERENCE_TECHNOLOGY_ID,
        supported_profile_versions=("v1-0-0",),
        capabilities=REFERENCE_CAPABILITIES,
        resource_mapping=(
            ResourceMappingEntry(
                technology_resource="pdu-session-qos-capacity",
                kind="bandwidth",
                unit="mbps",
                quantity=REFERENCE_QOS_MBPS,
                availability="reservation-based",
            ),
        ),
        security_state=AdapterSecurityState(
            profile="baseline",
            credential_slots=(_REFERENCE_CREDENTIAL_SLOT,),
            attested=False,
        ),
    )


class FiveGCTechnologyAdapter(AdapterContract):
    """The 5G Core family's WORK-016 SDK surface over the family
    RUNTIME (the :class:`~adapters.fivegc.manager.FiveGCoreManager`).

    Holds the manager reference and the deterministic reservation
    table only; every family call is mediated by the manager's own
    sandbox (B2 discipline).  The binding requirements map carries
    the 5G coordinates as DATA; the adapter translates them into the
    family's typed values (``Supi``/``Snssai``/``Dnn``) — no vendor
    type ever crosses the SDK boundary (LOCK-110).
    """

    label = "fivegc-technology"

    def __init__(self, manager: FiveGCoreManager) -> None:
        if not isinstance(manager, FiveGCoreManager):
            raise FiveGCoreError(
                FiveGCoreReasonCode.INVALID_INPUT,
                "manager must be a FiveGCoreManager (the adapter adapts "
                "the family RUNTIME -- never a raw FiveGCoreContract "
                "implementation)",
            )
        self._manager = manager
        self._sequence = 0
        self._reservations: Dict[str, str] = {}
        self._provisioned: Dict[str, bool] = {}

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
        raise FiveGCoreError(
            FiveGCoreReasonCode.FIVEGC_FAILURE,
            "%s: %s" % (operation, detail),
        )

    @staticmethod
    def _coordinates(
        requirements: Optional[Mapping[str, Any]]
    ) -> tuple:
        """Translate the caller's binding-coordinate DATA into the
        family's typed values (fail closed on malformed coordinates)."""
        if not isinstance(requirements, Mapping):
            raise AdapterError(
                AdapterReasonCode.INVALID_INPUT,
                "bind_session requirements must be a mapping carrying "
                "the 5G binding coordinates (supi/snssai/dnn) -- the "
                "generic SDK surface has no subscriber parameters",
            )
        supi = requirements.get("supi")
        snssai_raw = requirements.get("snssai")
        dnn = requirements.get("dnn")
        if not isinstance(supi, str) or not supi:
            raise AdapterError(
                AdapterReasonCode.INVALID_INPUT,
                "bind_session requirements must carry a 'supi' string",
            )
        if not isinstance(snssai_raw, Mapping) or "sst" not in snssai_raw:
            raise AdapterError(
                AdapterReasonCode.INVALID_INPUT,
                "bind_session requirements must carry an 'snssai' "
                "mapping with the 'sst' member",
            )
        if not isinstance(dnn, str) or not dnn:
            raise AdapterError(
                AdapterReasonCode.INVALID_INPUT,
                "bind_session requirements must carry a 'dnn' string",
            )
        sd = snssai_raw.get("sd")
        if sd is not None and not isinstance(sd, str):
            raise AdapterError(
                AdapterReasonCode.INVALID_INPUT,
                "snssai 'sd' must be a string or absent",
            )
        snssai = Snssai(sst=snssai_raw["sst"], sd=sd)
        leftover = {
            key: value
            for key, value in requirements.items()
            if key not in _REQUIREMENT_KEYS
        }
        return supi, snssai, dnn, leftover

    # ------------------------------------------------------------------
    # Nine-op SDK surface
    # ------------------------------------------------------------------

    def open(self, context: AdapterContext) -> None:
        self._charge(context, "open")
        result = self._manager.health(now=context.now())
        if not result.ok:
            self._family_failure("open", "5G Core integration is not healthy")

    def capabilities(self) -> Sequence[str]:
        return REFERENCE_CAPABILITIES

    def observe(self, context: AdapterContext) -> Mapping[str, int]:
        self._charge(context, "observe")
        result = self._manager.health(now=context.now())
        if not result.ok:
            self._family_failure("observe", "mediated health probe failed")
        healthy = result.value == "HEALTHY"
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
                "the 5G Core reference reservation model maps the WORK-008 "
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
        ref = "fivegc:qos-reservation:%06d" % self._sequence
        self._reservations[ref] = purpose
        return ref

    def release(self, context: AdapterContext, technology_ref: str) -> None:
        self._charge(context, "release")
        if technology_ref not in self._reservations:
            raise AdapterError(
                AdapterReasonCode.ALLOCATION_UNKNOWN,
                "unknown 5G Core reservation ref (already released?)",
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
        supi, snssai, dnn, leftover = self._coordinates(requirements)
        if not self._provisioned.get(supi):
            provisioned = self._manager.provision_subscriber(
                now=context.now(),
                supi=supi,
                credential_slot_name=_REFERENCE_CREDENTIAL_SLOT,
                subscribed_snssai=snssai,
                subscribed_dnn=Dnn(value=dnn),
            )
            if not provisioned.ok:
                self._family_failure(
                    "bind_session",
                    "mediated subscriber provisioning failed",
                )
            self._provisioned[supi] = True
        result = self._manager.bind_session(
            now=context.now(),
            session_id=session_id,
            supi=supi,
            snssai=snssai,
            dnn=Dnn(value=dnn),
            qos_requirements=leftover or None,
        )
        if not result.ok:
            self._family_failure(
                "bind_session",
                "mediated PDU session establishment failed",
            )
        return result.value.pdu_session_ref

    def unbind_session(self, context: AdapterContext, bearer_ref: str) -> None:
        self._charge(context, "unbind_session")
        if not isinstance(bearer_ref, str) or not bearer_ref:
            raise AdapterError(
                AdapterReasonCode.INVALID_INPUT,
                "bearer_ref must be a non-empty string",
            )
        result = self._manager.release_pdu_session(
            now=context.now(), pdu_session_ref=bearer_ref
        )
        if not result.ok:
            self._family_failure(
                "unbind_session", "mediated PDU session release failed"
            )

    def health(self) -> str:
        state = self._manager.computed_health()
        if state == HealthState.HEALTHY:
            return HealthState.HEALTHY
        if state == HealthState.DEGRADED:
            return HealthState.DEGRADED
        return HealthState.FAILED

    def close(self, context: AdapterContext) -> None:
        self._charge(context, "close")
        # Honest no-op (the frozen family contract expresses close per
        # PDU session; the manager lifecycle belongs to the
        # composition root).


def mount_reference(
    session_reader: Any,
    *,
    now: str,
    label: str = REFERENCE_LABEL,
) -> tuple:
    """Compose the 5G Core family reference adapter (deterministic).

    Wires the accepted family runtime: one
    :class:`FiveGCoreManager` (read-only session facade injected),
    the deterministic :class:`~adapters.fivegc.engine.Reference5GCoreEngine`
    registered through the manager's public API.

    Returns ``(implementation, descriptor, binding_requirements)``:
    the :class:`FiveGCTechnologyAdapter` to register with the
    :class:`~adapters.runtime.AdapterRuntime`, the reference
    descriptor, and the canonical 5G binding coordinates
    (:data:`REFERENCE_BINDING_REQUIREMENTS`) the caller passes to the
    1.1 ``activate``/``reconfigure`` operations — family wiring DATA,
    never an authority.
    """
    manager = FiveGCoreManager(
        integration_id="adcos:5gc:m007",
        session_reader=session_reader,
    )
    from ..fivegc.engine import Reference5GCoreEngine

    registered = manager.register_implementation(
        Reference5GCoreEngine(), now=now
    )
    if not registered.ok:
        raise FiveGCoreError(
            FiveGCoreReasonCode.FIVEGC_FAILURE,
            "reference engine registration failed",
        )
    return (
        FiveGCTechnologyAdapter(manager),
        reference_descriptor(label),
        REFERENCE_BINDING_REQUIREMENTS,
    )
