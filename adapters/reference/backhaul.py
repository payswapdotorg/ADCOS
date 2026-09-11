"""ADCOS backhaul family M007 reference composition (R7-CORE-001).

The backhaul family's M007 surface: this module composes the family's
ACCEPTED WORK-022 runtime — the
:class:`~adapters.backhaul.manager.BackhaulManager` over the
deterministic :class:`~adapters.backhaul.engine.ReferenceBackhaulEngine`
(missing a dedicated engine module, the family's reference
implementation lives in ``engine.py``) with the accepted WORK-016 SDK
bridge (:class:`~adapters.backhaul.bridge.BackhaulTechnologyAdapter`)
— plus the reference registration data
(:func:`reference_descriptor`).  The 1.1 capability-oriented surface
(:class:`adapters.capability.CapabilityAdapter`) composes on top;
NOTHING in the frozen family contract changes.

LOCK-112 (standard leverage — the mechanisms this family models, taken
from the family's own frozen citations, never reinvented here):

* ``ieee-802.3-ethernet`` — IEEE 802.3-2018 Ethernet frames (the
                              reference profile this composition
                              provisions);
* ``ieee-802.1q-bridged``  — IEEE 802.1Q-2022 bridged LANs;
* ``itu-t-g709-otn``       — ITU-T G.709 optical transport trails.

The tags are citation DATA carried in the 1.1 views
(:attr:`STANDARD_MECHANISMS`); the boundary never branches on them.

The composition provisions exactly ONE Ethernet link profile through
the MANAGER's public API (``provision_link``) at the injected ``now``
and hands its opaque ``backhaul:link:<hex>`` reference back as the
binding requirement DATA (``link_ref``) the caller passes to the 1.1
``activate``/``reconfigure`` operations — family-side wiring data the
composition root legitimately holds (the WORK-022 battery performs
the same provisioning; the W016 runtime keeps its own internal
technology refs opaque, LOCK-017).

Determinism (LOCK-119): fixed link profile (Ethernet, 1 Gbps, 8
bearers, fixed endpoint labels); injected instants; no wall clock, no
randomness, no network.
"""

from __future__ import annotations

from typing import Any, Mapping, Tuple

from ..contract import AdapterContract
from ..model import (
    AdapterDescriptor,
    AdapterSecurityState,
    ResourceMappingEntry,
    derive_adapter_id,
)
from ..backhaul.bridge import BackhaulTechnologyAdapter
from ..backhaul.manager import BackhaulManager
from ..backhaul.model import BackhaulProfile, LinkDescriptor

#: The LOCK-112 standard-mechanism tags this family's reference
#: adapter models (citation DATA, never branch input).
STANDARD_MECHANISMS: Tuple[str, ...] = (
    "ieee-802.3-ethernet",
    "ieee-802.1q-bridged",
    "itu-t-g709-otn",
)

#: The reference access technology for this family (KNOWN in the
#: WORK-002 registry: the IEEE 802.3 entry).
REFERENCE_TECHNOLOGY_ID = "access.ieee.8023"

#: Default instance label of the reference composition.
REFERENCE_LABEL = "backhaul-reference-0"

#: Capability references the reference composition declares
#: (UNKNOWN_BUT_WELL_FORMED in the WORK-002 grammar — preserved
#: verbatim; the family ladder mediates the live exposure).
REFERENCE_CAPABILITIES: Tuple[str, ...] = (
    "capability.profile.backhaul.link",
    "capability.profile.backhaul.capacity",
    "capability.profile.backhaul.bearer",
    "capability.profile.backhaul.data-path",
)

#: The reference link capacity (integer bps).
REFERENCE_LINK_BPS = 1_000_000_000


def reference_descriptor(label: str = REFERENCE_LABEL) -> AdapterDescriptor:
    """The reference registration descriptor for the backhaul family."""
    return AdapterDescriptor(
        adapter_id=derive_adapter_id(REFERENCE_TECHNOLOGY_ID, label),
        access_technology_id=REFERENCE_TECHNOLOGY_ID,
        supported_profile_versions=("v1-0-0",),
        capabilities=REFERENCE_CAPABILITIES,
        resource_mapping=(
            ResourceMappingEntry(
                technology_resource="link-capacity",
                kind="backhaul",
                unit="bps",
                quantity=REFERENCE_LINK_BPS,
                availability="continuous",
            ),
        ),
        security_state=AdapterSecurityState(
            profile="baseline",
            credential_slots=("backhaul-technology-credentials",),
            attested=False,
        ),
    )


def mount_reference(
    session_reader: Any,
    *,
    now: str,
    label: str = REFERENCE_LABEL,
) -> Tuple[AdapterContract, AdapterDescriptor, Mapping[str, Any]]:
    """Compose the backhaul family reference adapter (deterministic).

    Wires the accepted family runtime: one
    :class:`BackhaulManager` (read-only session facade injected), the
    deterministic reference engine registered as default, ONE
    Ethernet link profile provisioned through the manager's public
    API (1 Gbps, 8 bearers, fixed endpoint labels), and the accepted
    WORK-016 bridge over the manager.

    Returns ``(implementation, descriptor, binding_requirements)``:
    the bridge to register with the
    :class:`~adapters.runtime.AdapterRuntime`, the reference
    descriptor, and the canonical requirements map (``link_ref``)
    the caller passes to the 1.1 ``activate``/``reconfigure``
    operations — family wiring DATA, never an authority.
    """
    manager = BackhaulManager(
        integration_id="adcos:backhaul:m007",
        session_reader=session_reader,
    )
    from ..backhaul.engine import ReferenceBackhaulEngine

    registered = manager.register_implementation(
        ReferenceBackhaulEngine(),
        label="backhaul-m007",
        make_default=True,
        now=now,
    )
    if not registered.ok:
        from ..backhaul.errors import BackhaulError

        raise BackhaulError(
            registered.reason, "reference engine registration failed"
        )
    provisioned = manager.provision_link(
        now=now,
        descriptor=LinkDescriptor(
            name="m007-reference-link",
            profile=BackhaulProfile.ETHERNET,
            capacity_bps=REFERENCE_LINK_BPS,
            max_bearers=8,
            endpoint_labels=("backhaul-sdk-endpoint",),
        ),
        credential_slot_name="backhaul-technology-credentials",
    )
    if not provisioned.ok:
        from ..backhaul.errors import BackhaulError

        raise BackhaulError(
            provisioned.reason, "reference link provisioning failed"
        )
    bridge = BackhaulTechnologyAdapter(manager, label="backhaul-m007")
    return bridge, reference_descriptor(label), {
        "link_ref": provisioned.value.link_ref
    }
