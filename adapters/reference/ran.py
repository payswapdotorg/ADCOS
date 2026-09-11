"""ADCOS 5G RAN family M007 reference composition (R7-CORE-001).

The RAN family's M007 surface: this module composes the family's
ACCEPTED WORK-020 runtime — the deterministic
:class:`~adapters.ran.engine.ReferenceRanEngine` with the accepted
WORK-016 SDK bridge (:class:`~adapters.ran.bridge.RanTechnologyAdapter`)
— plus the reference registration data
(:func:`reference_descriptor`) and the deterministic gNB/cell
provisioning the 1.1 ``activate`` operation needs.  The 1.1
capability-oriented surface (:class:`adapters.capability.CapabilityAdapter`)
composes on top; NOTHING in the frozen family contract changes.

LOCK-112 (standard leverage — the mechanisms this family models, taken
from the family's own frozen citations, never reinvented here):

* ``3gpp-nr``               — 3GPP NR radio access (TS 38.321/38.331
                              RNTI/DRB/QFI shapes the engine models
                              as DATA);
* ``oran-fronthaul-split``  — O-RAN 7-2x open fronthaul RU and the
                              F1/E1 CU/DU split topology the family
                              models (O-RAN.WG4 / TS 38.401 §5 /
                              TS 38.473).

The tags are citation DATA carried in the 1.1 views
(:attr:`STANDARD_MECHANISMS`); the boundary never branches on them.

Honest disclosure (family-documented): the RAN bridge's mediated
``capabilities()`` returns ``capability.access.ran.*`` references,
which the frozen WORK-002 capability-registry grammar does not yet
admit (only ``capability.core.*`` / ``capability.profile.*``); the
WORK-016 sandbox therefore classifies the mediated return as a
contract violation and the 1.1 ``inspect_capabilities`` view exposes
an EMPTY reference set for this family.  That is the family's own
documented behavior (see ``adapters/ran/bridge.py``), preserved
verbatim by the M007 seam — the adapter layer never rewrites
capability references to make exposure non-empty.

The composition wrapper (:class:`RanReferenceComposition`) is the
deterministic composition ROOT: it delegates all nine WORK-016
operations to the family bridge verbatim and, on the SDK ``open``,
provisions the canonical gNB and activates its cell through the
ENGINE's own public API (the composition root's wiring right — the
same family-side provisioning the WORK-020 battery performs; the
frozen bridge itself stays a thin state-free translation).

Determinism (LOCK-119): the composition provisions exactly one gNB
(the WORK-020 canonical lab shape — band-78 TDD cell ``c1``,
numerology 1, NR-ARFCN 632628, 10 PRBs, F1 CU/DU split, O-RAN 7-2x
RU) with the cell ACTIVE, at the injected instant; no wall clock, no
randomness, no network.  The reference binding requirements are
``None`` (the RAN bridge passes QoS DATA through; the engine's
deterministic cell choice needs no caller coordinates).
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence, Tuple

from ..contract import AdapterContext, AdapterContract
from ..model import (
    AdapterDescriptor,
    AdapterSecurityState,
    ResourceMappingEntry,
    derive_adapter_id,
)
from ..ran.bridge import RanTechnologyAdapter
from ..ran.engine import ReferenceRanEngine
from ..ran.model import (
    CellSpec,
    CuElement,
    DuplexMode,
    DuElement,
    GnbProvisionRequest,
    HealthState,
    RanSplitOption,
    RanSplitTopology,
    RuElement,
)

#: The LOCK-112 standard-mechanism tags this family's reference
#: adapter models (citation DATA, never branch input).
STANDARD_MECHANISMS: Tuple[str, ...] = (
    "3gpp-nr",
    "oran-fronthaul-split",
)

#: The reference access technology for this family (KNOWN in the
#: WORK-002 registry: the NR IMT-2020 entry).
REFERENCE_TECHNOLOGY_ID = "access.3gpp.nr.imt2020"

#: Default instance label of the reference composition.
REFERENCE_LABEL = "ran-reference-0"

#: Capability references the reference composition declares.  The
#: live mediated exposure through the WORK-016 runtime is EMPTY for
#: this family (the family-documented WORK-002 grammar gap disclosed
#: in the module docstring); the declaration stays well-formed data.
REFERENCE_CAPABILITIES: Tuple[str, ...] = (
    "capability.profile.ran.drb",
    "capability.profile.ran.cell",
)

#: The reference radio-capacity mapping (DRB bandwidth, integer mbps).
REFERENCE_DRB_MBPS = 100

#: The canonical cell id the reference composition activates.
_REFERENCE_CELL_ID = "c1"


def reference_descriptor(label: str = REFERENCE_LABEL) -> AdapterDescriptor:
    """The reference registration descriptor for the RAN family."""
    return AdapterDescriptor(
        adapter_id=derive_adapter_id(REFERENCE_TECHNOLOGY_ID, label),
        access_technology_id=REFERENCE_TECHNOLOGY_ID,
        supported_profile_versions=("v1-0-0",),
        capabilities=REFERENCE_CAPABILITIES,
        resource_mapping=(
            ResourceMappingEntry(
                technology_resource="drb-radio-capacity",
                kind="bandwidth",
                unit="mbps",
                quantity=REFERENCE_DRB_MBPS,
                availability="reservation-based",
            ),
        ),
        security_state=AdapterSecurityState(
            profile="baseline",
            credential_slots=("ran-technology-credentials",),
            attested=False,
        ),
    )


def _canonical_gnb_request() -> GnbProvisionRequest:
    """The fixed canonical gNB provision request (the WORK-020
    reference lab shape): one band-78 TDD cell (``c1``, numerology 1,
    NR-ARFCN 632628, 10 PRBs) carried on an F1 CU/DU split with an
    O-RAN 7-2x open fronthaul RU."""
    return GnbProvisionRequest(
        gnb_name="m007-gnb-1",
        cells=(
            CellSpec(
                cell_id=_REFERENCE_CELL_ID,
                band=78,
                duplex=DuplexMode.TDD,
                numerology=1,
                arfcn=632628,
                prb_count=10,
            ),
        ),
        topology=RanSplitTopology(
            cu=CuElement(
                element_id="cu-1",
                split=RanSplitOption.F1_CU_DU,
                state=HealthState.HEALTHY,
            ),
            dus=(
                DuElement(
                    element_id="du-1",
                    split=RanSplitOption.F1_CU_DU,
                    state=HealthState.HEALTHY,
                    cell_ids=(_REFERENCE_CELL_ID,),
                ),
            ),
            rus=(
                RuElement(
                    element_id="ru-1",
                    split=RanSplitOption.O_RAN_7_2X,
                    state=HealthState.HEALTHY,
                    band=78,
                ),
            ),
        ),
    )


class RanReferenceComposition(AdapterContract):
    """The RAN family's M007 deterministic composition root.

    Delegates every WORK-016 operation verbatim to the family
    :class:`~adapters.ran.bridge.RanTechnologyAdapter` (the accepted
    thin translation — no state, no re-translation) and performs, on
    the SDK ``open``, the composition-root provisioning the family's
    own battery performs: provision the canonical gNB, activate its
    cell.  Holds exactly the engine reference and the bridge — no
    session material, no policy, no topology.
    """

    label = "ran-m007-reference"

    def __init__(self) -> None:
        self._engine = ReferenceRanEngine()
        self._bridge = RanTechnologyAdapter(self._engine, label="ran-m007")

    @property
    def engine(self) -> ReferenceRanEngine:
        """The composed family engine (composition-root wiring aid;
        never a core-visible surface)."""
        return self._engine

    # ------------------------------------------------------------------
    # Nine-op SDK surface (verbatim delegation + open-time provisioning)
    # ------------------------------------------------------------------

    def open(self, context: AdapterContext) -> None:
        self._bridge.open(context)
        # Deterministic composition-root provisioning through the
        # ENGINE's public API (the family battery's own flow).
        from ..ran.contract import RanContext
        from ..ran.manager import DEFAULT_INTEGRATION_ID

        ran_context = RanContext(
            ran_integration_id=DEFAULT_INTEGRATION_ID,
            instant=context.now(),
            step_budget=context.steps_left(),
        )
        gnb_ref = self._engine.provision_gnb(
            ran_context, request=_canonical_gnb_request()
        )
        self._engine.activate_cell(
            ran_context, gnb_ref=gnb_ref, cell_id=_REFERENCE_CELL_ID
        )

    def capabilities(self) -> Sequence[str]:
        return self._bridge.capabilities()

    def observe(self, context: AdapterContext) -> Mapping[str, int]:
        return self._bridge.observe(context)

    def allocate(
        self,
        context: AdapterContext,
        *,
        kind: str,
        quantity_base: int,
        purpose: str,
    ) -> str:
        """SDK ``allocate`` -> the family bridge with the DISCLOSED
        resource-kind translation.

        The WORK-016 runtime only admits WORK-008 mapped kinds (the
        descriptor maps ``bandwidth``), while the RAN engine's
        reservation vocabulary is its own (``ran.radio-capacity``).
        The composition root translates the mapped bandwidth kind
        onto the family kind verbatim in quantity (integer bps base
        units) — the same bridge-fixed-default pattern the accepted
        backhaul/Wi-Fi bridges document for their family parameters.
        """
        from ..ran.engine import RAN_ALLOCATION_KIND_RADIO_CAPACITY

        family_kind = kind
        if kind in ("bandwidth", "backhaul"):
            family_kind = RAN_ALLOCATION_KIND_RADIO_CAPACITY
        return self._bridge.allocate(
            context, kind=family_kind, quantity_base=quantity_base, purpose=purpose
        )

    def release(self, context: AdapterContext, technology_ref: str) -> None:
        self._bridge.release(context, technology_ref=technology_ref)

    def bind_session(
        self,
        context: AdapterContext,
        *,
        session_id: str,
        requirements: Optional[Mapping[str, Any]],
    ) -> str:
        return self._bridge.bind_session(
            context, session_id=session_id, requirements=requirements
        )

    def unbind_session(self, context: AdapterContext, bearer_ref: str) -> None:
        return self._bridge.unbind_session(context, bearer_ref=bearer_ref)

    def health(self) -> str:
        return self._bridge.health()

    def close(self, context: AdapterContext) -> None:
        return self._bridge.close(context)


def mount_reference(
    *,
    now: str,
    label: str = REFERENCE_LABEL,
) -> Tuple[AdapterContract, AdapterDescriptor, Optional[Mapping[str, Any]]]:
    """Compose the RAN family reference adapter (deterministic).

    Returns ``(implementation, descriptor, binding_requirements)``:
    the :class:`RanReferenceComposition` to register with the
    :class:`~adapters.runtime.AdapterRuntime` (its SDK ``open``
    performs the deterministic gNB provisioning at the injected
    instant), the reference descriptor, and ``None`` binding
    requirements (the RAN seam needs no caller coordinates; QoS DATA
    passes through verbatim).
    """
    return RanReferenceComposition(), reference_descriptor(label), None
