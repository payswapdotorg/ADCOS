"""ADCOS Wi-Fi/non-3GPP family M007 reference composition (R7-CORE-001).

The Wi-Fi family's M007 surface: this module composes the family's
ACCEPTED WORK-021 runtime — the
:class:`~adapters.wifi.manager.WifiManager` over the deterministic
:class:`~adapters.wifi.engine.ReferenceWifiEngine` with the accepted
WORK-016 SDK bridge (:class:`~adapters.wifi.bridge.WifiTechnologyAdapter`)
— plus the reference registration data
(:func:`reference_descriptor`).  The 1.1 capability-oriented surface
(:class:`adapters.capability.CapabilityAdapter`) composes on top;
NOTHING in the frozen family contract changes.

LOCK-112 (standard leverage — the mechanisms this family models, taken
from the family's own frozen citations, never reinvented here):

* ``ieee-802.11``   — IEEE 802.11-2020 association/SSID shapes;
* ``ieee-802.1x``   — IEEE 802.1X-2020 / RFC 3748 (EAP) authentication
                      (the reference engine's OPEN policy keeps the
                      802.1X slot a name only — LOCK-023);
* ``3gpp-ts-23.316-n3iwf`` — 3GPP TS 23.316 non-3GPP access via the
                      N3IWF (the family's tunnel bearer);
* ``rfc-7296-ipsec`` — RFC 7296 (IKEv2/IPsec) tunnel shapes the
                      family models as DATA.

The tags are citation DATA carried in the 1.1 views
(:attr:`STANDARD_MECHANISMS`); the boundary never branches on them.

The composition provisions exactly ONE AP profile through the
MANAGER's public API (``provision_ap``) at the injected ``now`` and
hands its opaque ``wifi:ap:<hex>`` reference back as the binding
requirement DATA (``ap_ref`` + ``ssid_name``) the caller passes to
the 1.1 ``activate``/``reconfigure`` operations — family-side wiring
data the composition root legitimately holds (the WORK-021 battery
performs the same provisioning; the W016 runtime keeps its own
internal technology refs opaque, LOCK-017).

Determinism (LOCK-119): fixed AP profile (one 5 GHz SSID, OPEN
security policy, 8 stations/associations — the reference simulation
shape; no keys, no credential material, LOCK-023); injected instants;
no wall clock, no randomness, no network.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Tuple

from ..contract import AdapterContract
from ..model import (
    AdapterDescriptor,
    AdapterSecurityState,
    ResourceMappingEntry,
    derive_adapter_id,
)
from ..wifi.bridge import WifiTechnologyAdapter
from ..wifi.manager import WifiManager
from ..wifi.model import ApDescriptor, SecurityPolicy, SsidProfile

#: The LOCK-112 standard-mechanism tags this family's reference
#: adapter models (citation DATA, never branch input).
STANDARD_MECHANISMS: Tuple[str, ...] = (
    "ieee-802.11",
    "ieee-802.1x",
    "3gpp-ts-23.316-n3iwf",
    "rfc-7296-ipsec",
)

#: The reference access technology for this family (KNOWN in the
#: WORK-002 registry: the IEEE 802.11 entry).
REFERENCE_TECHNOLOGY_ID = "access.ieee.80211"

#: Default instance label of the reference composition.
REFERENCE_LABEL = "wifi-reference-0"

#: The reference SSID name (deterministic; the bridge's documented
#: allocate translation names provisioned SSIDs after the mapped
#: resource kind — the composition uses the same kind-named SSID so
#: the bridge's bind coordinates stay coherent).
_REFERENCE_SSID = "m007-wifi"

#: Capability references the reference composition declares
#: (UNKNOWN_BUT_WELL_FORMED in the WORK-002 grammar — preserved
#: verbatim; the family ladder mediates the live exposure).
REFERENCE_CAPABILITIES: Tuple[str, ...] = (
    "capability.profile.wifi.non-3gpp-access",
    "capability.profile.wifi.association",
    "capability.profile.wifi.authentication",
    "capability.profile.wifi.n3iwf-tunnel",
    "capability.profile.wifi.data-path",
)

#: The reference association capacity (integer stations).
REFERENCE_ASSOCIATIONS = 8


def reference_descriptor(label: str = REFERENCE_LABEL) -> AdapterDescriptor:
    """The reference registration descriptor for the Wi-Fi family."""
    return AdapterDescriptor(
        adapter_id=derive_adapter_id(REFERENCE_TECHNOLOGY_ID, label),
        access_technology_id=REFERENCE_TECHNOLOGY_ID,
        supported_profile_versions=("v1-0-0",),
        capabilities=REFERENCE_CAPABILITIES,
        resource_mapping=(
            ResourceMappingEntry(
                technology_resource="ap-association-capacity",
                kind="coverage",
                unit="count",
                quantity=REFERENCE_ASSOCIATIONS,
                availability="continuous",
            ),
        ),
        security_state=AdapterSecurityState(
            profile="baseline",
            credential_slots=("wifi-technology-credentials",),
            attested=False,
        ),
    )


def mount_reference(
    session_reader: Any,
    ap_profile_reader: Any,
    *,
    now: str,
    label: str = REFERENCE_LABEL,
) -> Tuple[AdapterContract, AdapterDescriptor, Mapping[str, Any]]:
    """Compose the Wi-Fi family reference adapter (deterministic).

    Wires the accepted family runtime: one
    :class:`WifiManager` (read-only session + AP-profile facades
    injected), the deterministic
    :class:`~adapters.wifi.engine.ReferenceWifiEngine` registered as
    default, ONE AP profile provisioned through the manager's public
    API (5 GHz, OPEN policy — the reference simulation shape; no
    credential material), and the accepted WORK-016 bridge over the
    manager.

    Returns ``(implementation, descriptor, binding_requirements)``:
    the bridge to register with the
    :class:`~adapters.runtime.AdapterRuntime`, the reference
    descriptor, and the canonical requirements map (``ap_ref`` +
    ``ssid_name``) the caller passes to the 1.1
    ``activate``/``reconfigure`` operations — family wiring DATA,
    never an authority.
    """
    manager = WifiManager(
        integration_id="adcos:wifi:m007",
        session_reader=session_reader,
        ap_profile_reader=ap_profile_reader,
    )
    from ..wifi.engine import ReferenceWifiEngine

    registered = manager.register_implementation(
        ReferenceWifiEngine(),
        label="wifi-m007",
        make_default=True,
        now=now,
    )
    if not registered.ok:
        from ..wifi.errors import WifiError

        raise WifiError(registered.reason, "reference engine registration failed")
    provisioned = manager.provision_ap(
        now=now,
        descriptor=ApDescriptor(
            name="m007-reference-ap",
            ssids=(
                SsidProfile(
                    ssid=_REFERENCE_SSID,
                    band="5ghz",
                    security_policy=SecurityPolicy.OPEN,
                    max_stations=REFERENCE_ASSOCIATIONS,
                ),
            ),
            bands=("5ghz",),
            max_associations=REFERENCE_ASSOCIATIONS,
        ),
        credential_slot_name="wifi-technology-credentials",
    )
    if not provisioned.ok:
        from ..wifi.errors import WifiError

        raise WifiError(provisioned.reason, "reference AP provisioning failed")
    bridge = WifiTechnologyAdapter(manager, label="wifi-m007")
    return bridge, reference_descriptor(label), {
        "ap_ref": provisioned.value.ap_ref,
        "ssid_name": _REFERENCE_SSID,
    }
