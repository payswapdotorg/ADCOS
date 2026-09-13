"""ADCOS satellite family M022 reference compositions (R9-CORE-001,
DEC-0122 — the current R9 chain child, its M020 and M021 dependencies
satisfied).

The non-terrestrial access families of the R9 charter M022 scope:
GSO, NGSO, LEO and mesh/IAB reference adapter compositions on the
accepted M020 envelope domain, each composing the ACCEPTED
``adapters/mesh/`` family runtime — the
:class:`~adapters.mesh.manager.MeshManager` over the deterministic
family engines (the :class:`~adapters.mesh.engine.ReferenceMeshEngine`
for the satellite relay families; the accepted
:class:`~adapters.mesh.sidelink.SidelinkRelayEngine` — the 3GPP
IAB/sidelink-seam relay implementation with the DTN store-and-forward
queue — for the mesh/IAB family) with the accepted WORK-016 SDK
bridge (:class:`~adapters.mesh.bridge.MeshTechnologyAdapter`) — BY
REFERENCE through the accepted ``adapters/capability.py`` seam (the
M007 LOCK-110/LOCK-112 boundary).  NOTHING in the frozen family
contract changes; every composition calls the family's OWN public
runtime APIs (LOCK-112 — the family models the standard mechanisms;
the citations are declared DATA below, never a branch input — the
satellite families additionally cite the 3GPP NTN and satellite
trunk standards they model over the composed relay runtime):

* ``3gpp-ntn-nr``          — 3GPP Rel-17 NR non-terrestrial networks
*                            (TS 38.300 §17 — the NTN access the
*                            satellite families model);
* ``3gpp-iab``             — 3GPP integrated access and backhaul
*                            (the relay classification the satellite
*                            legs carry — the accepted mesh family's
*                            own frozen tag);
* ``3gpp-sidelink-relay``  — 3GPP sidelink relay integration (the
*                            mesh/IAB composition's relay legs);
* ``dtn-store-and-forward`` — DTN-class store-and-forward bundles
*                            (the accepted family's queue discipline
*                            — the satellite disruption tolerance);
* ``etsi-dvb-s2``          — ETSI EN 302 307 DVB-S2 satellite trunk
*                            (the GSO family's feeder/trunk citation);
* ``ccsds-bundle-protocol`` — CCSDS/RFC 9171 bundle protocol (the
*                            NGSO constellation's cross-link DTN
*                            citation).

Compositions (one mount factory per family, the accepted
``adapters/reference/mesh.py`` pattern — the composition root wires
the family runtime and hands back the registration products; the
caller supplies the relay chain's WORK-004 node ids and the ordinary
WORK-011 ``Path`` the route registers, exactly the accepted M007 mesh
composition's signature):

* :func:`mount_gso_reference` — the GSO family (technology class
  ``access.satellite.gso``, open-world well-formed declared data):
  the BENT-PIPE geometry — two IAB-classified relay legs (terminal
  -> GSO relay -> ground gateway) over the deterministic reference
  engine;
* :func:`mount_ngso_reference` — the NGSO family (technology class
  ``access.satellite.ngso``): the CONSTELLATION geometry — three
  relay legs (terminal -> NGSO satellite -> NGSO satellite
  inter-satellite cross-link -> gateway); the pass-handover geometry
  itself is DECLARED DATA on the M020 envelope (the accesstech
  pass schedules) driven through the accepted ``resilience/``
  handover machinery by the composition's consumers — never
  re-modeled here;
* :func:`mount_leo_reference` — the LEO family (technology class
  ``access.satellite.leo``): two relay legs (terminal -> LEO relay
  -> gateway) over the deterministic reference engine;
* :func:`mount_mesh_iab_reference` — the MESH/IAB family (technology
  class ``access.3gpp.iab``, KNOWN in the WORK-002 registry — the
  same registry entry the accepted M007 mesh reference composition
  declares; the M021 ethernet-over-backhaul precedent of composing
  on the accepted family's own class): two SIDELINK-classified relay
  legs over the accepted :class:`SidelinkRelayEngine` configured with
  the declared satellite DTN store-and-forward limits
  (:data:`SATELLITE_DTN_CONFIG`).  The mount hands back the DTN
  wiring (the live family manager, the sidelink engine, the relay
  leg refs and the route ref) as composition-root wiring DATA — the
  caller drives the family's OWN public enqueue/forward/expire APIs
  through it (the sidelink relay + DTN store-and-forward semantics
  composed BY REFERENCE, never re-implemented).

LOCK-110 (SDK isolation) is structural here, inherited from the
composed surfaces: every 1.1 operation returns typed, canonical,
provider-neutral records through the accepted
:class:`~adapters.capability.CapabilityAdapter` seam; the opaque
``mesh:`` technology references (bearer/link/bundle handles) stay
behind the WORK-016 runtime (keyed internally, passed back on
release); the core imports no adapter implementation and branches on
no technology name.

Determinism (LOCK-119): fixed relay-chain shapes and declared DTN
limits; injected instants only; no wall clock, no randomness, no
network, no secrets (credential SLOT NAMES only — never material).
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from ..contract import AdapterContract
from ..model import (
    AdapterDescriptor,
    AdapterSecurityState,
    ResourceMappingEntry,
    derive_adapter_id,
)
from ..mesh.bridge import MeshTechnologyAdapter
from ..mesh.engine import ReferenceMeshEngine
from ..mesh.errors import MeshError, MeshReasonCode
from ..mesh.manager import MeshManager
from ..mesh.model import (
    RelayLinkDescriptor,
    RelayTechnology,
    StoreAndForwardConfig,
)
from ..mesh.sidelink import SidelinkRelayEngine

# BY REFERENCE: the accepted M007 mesh reference composition's own
# capability statement (the family's accepted references the satellite
# descriptors declare verbatim — the mediated runtime filters the live
# exposure to the declared set; the M021 wireline precedent of
# importing the accepted reference module's capability statement).
from .mesh import REFERENCE_CAPABILITIES

__all__ = [
    "GSO_MECHANISMS",
    "NGSO_MECHANISMS",
    "LEO_MECHANISMS",
    "MESH_IAB_MECHANISMS",
    "GSO_TECHNOLOGY_ID",
    "NGSO_TECHNOLOGY_ID",
    "LEO_TECHNOLOGY_ID",
    "MESH_IAB_TECHNOLOGY_ID",
    "GSO_LABEL",
    "NGSO_LABEL",
    "LEO_LABEL",
    "MESH_IAB_LABEL",
    "GSO_QUEUE_BYTES",
    "NGSO_QUEUE_BYTES",
    "LEO_QUEUE_BYTES",
    "MESH_IAB_QUEUE_BYTES",
    "GSO_DTN_CONFIG",
    "NGSO_DTN_CONFIG",
    "LEO_DTN_CONFIG",
    "SATELLITE_DTN_CONFIG",
    "CREDENTIAL_SLOT_NAME",
    "gso_descriptor",
    "ngso_descriptor",
    "leo_descriptor",
    "mesh_iab_descriptor",
    "mount_gso_reference",
    "mount_ngso_reference",
    "mount_leo_reference",
    "mount_mesh_iab_reference",
]

#: The LOCK-112 standard-mechanism tags the GSO family's reference
#: adapter models (citation DATA, never branch input): NTN NR access
#: over the composed relay runtime, the IAB relay classification, the
#: DTN queue discipline, and the DVB-S2 satellite trunk citation.
GSO_MECHANISMS: Tuple[str, ...] = (
    "3gpp-ntn-nr",
    "3gpp-iab",
    "dtn-store-and-forward",
    "etsi-dvb-s2",
)

#: The NGSO family's tags: the NTN access, the IAB relay
#: classification, the DTN queue discipline, and the CCSDS bundle
#: protocol citation for the constellation's cross-link DTN geometry.
NGSO_MECHANISMS: Tuple[str, ...] = (
    "3gpp-ntn-nr",
    "3gpp-iab",
    "dtn-store-and-forward",
    "ccsds-bundle-protocol",
)

#: The LEO family's tags: the NTN access, the IAB relay
#: classification, and the DTN queue discipline.
LEO_MECHANISMS: Tuple[str, ...] = (
    "3gpp-ntn-nr",
    "3gpp-iab",
    "dtn-store-and-forward",
)

#: The mesh/IAB family's tags: the accepted mesh family's OWN three
#: frozen citation tags, carried verbatim (this composition IS the
#: family extension — the sidelink relay, the IAB classification and
#: the DTN store-and-forward discipline it composes BY REFERENCE).
MESH_IAB_MECHANISMS: Tuple[str, ...] = (
    "3gpp-iab",
    "3gpp-sidelink-relay",
    "dtn-store-and-forward",
)

#: The GSO family's access technology (the geostationary satellite
#: relay class — open-world well-formed declared data).
GSO_TECHNOLOGY_ID = "access.satellite.gso"

#: The NGSO family's access technology (the non-geostationary
#: constellation class — open-world well-formed declared data).
NGSO_TECHNOLOGY_ID = "access.satellite.ngso"

#: The LEO family's access technology (the low-earth-orbit
#: constellation class — open-world well-formed declared data).
LEO_TECHNOLOGY_ID = "access.satellite.leo"

#: The mesh/IAB family's access technology (KNOWN in the WORK-002
#: registry: the IAB entry — the same registry entry the accepted
#: M007 mesh reference composition declares).
MESH_IAB_TECHNOLOGY_ID = "access.3gpp.iab"

#: Default instance labels of the four reference compositions.
GSO_LABEL = "satellite-gso-reference-0"
NGSO_LABEL = "satellite-ngso-reference-0"
LEO_LABEL = "satellite-leo-reference-0"
MESH_IAB_LABEL = "satellite-mesh-iab-reference-0"

#: The declared store-and-forward queue capacities of the four
#: compositions (integer bytes — the family's WORK-008 ``storage``
#: rate kind base units; each equals its family engine's configured
#: queue bound — the mapped capacity is the configured bound, the
#: honest composition).
GSO_QUEUE_BYTES = 200_000_000
NGSO_QUEUE_BYTES = 150_000_000
LEO_QUEUE_BYTES = 100_000_000
MESH_IAB_QUEUE_BYTES = 100_000_000

#: The GSO family's declared store-and-forward configuration (the
#: family engine's own public config record — explicit,
#: deterministic, fail-closed limits, never unbounded): the trunk
#: queue's bounded capacity, bundle count, and daily bundle
#: lifetime.
GSO_DTN_CONFIG = StoreAndForwardConfig(
    max_queued_bytes=200_000_000,
    max_queued_bundles=2048,
    ttl_seconds=86_400,
    default_hop_budget=16,
)

#: The NGSO family's declared store-and-forward configuration: the
#: pass queue's bounded capacity and a bundle lifetime long enough
#: to BRIDGE the declared inter-pass gaps (the DTN disruption
#: tolerance of the pass geometry).
NGSO_DTN_CONFIG = StoreAndForwardConfig(
    max_queued_bytes=150_000_000,
    max_queued_bundles=1024,
    ttl_seconds=7200,
    default_hop_budget=16,
)

#: The LEO family's declared store-and-forward configuration (the
#: short-pass queue's bounded capacity and hourly bundle lifetime).
LEO_DTN_CONFIG = StoreAndForwardConfig(
    max_queued_bytes=100_000_000,
    max_queued_bundles=1024,
    ttl_seconds=3600,
    default_hop_budget=16,
)

#: The declared satellite DTN store-and-forward configuration of the
#: mesh/IAB composition (the sidelink engine's own public config
#: record): a bounded queue, a bundle lifetime long enough to BRIDGE
#: the NGSO/LEO pass gaps (the declared pass schedules' inter-pass
#: gaps), and the family's hop budget.
SATELLITE_DTN_CONFIG = StoreAndForwardConfig(
    max_queued_bytes=100_000_000,
    max_queued_bundles=1024,
    ttl_seconds=7200,
    default_hop_budget=16,
)

#: The family's credential SLOT NAME (LOCK-023/LOCK-119: the name
#: only — the family's boundary rejects secret-shaped material, and
#: the relay management credentials stay behind the family runtime).
CREDENTIAL_SLOT_NAME = "relay-management"

#: The relay-leg count of each composition's chain (the declared
#: deterministic geometry: the GSO bent-pipe 2 legs over 3 nodes; the
#: NGSO constellation 3 legs over 4 nodes — the inter-satellite
#: cross-link; the LEO 2 legs over 3 nodes; the mesh/IAB sidelink
#: 2 legs over 3 nodes).
_FAMILY_CHAIN_NODES: Dict[str, int] = {
    "gso": 3,
    "ngso": 4,
    "leo": 3,
    "mesh-iab": 3,
}


# ----------------------------------------------------------------------
# The reference registration descriptors (declared data)
# ----------------------------------------------------------------------


def gso_descriptor(label: str = GSO_LABEL) -> AdapterDescriptor:
    """The reference registration descriptor for the GSO family
    (technology class ``access.satellite.gso``)."""
    return AdapterDescriptor(
        adapter_id=derive_adapter_id(GSO_TECHNOLOGY_ID, label),
        access_technology_id=GSO_TECHNOLOGY_ID,
        supported_profile_versions=("v1-0-0",),
        capabilities=REFERENCE_CAPABILITIES,
        resource_mapping=(
            ResourceMappingEntry(
                technology_resource="gso-relay-trunk-queue",
                kind="storage",
                unit="bytes",
                quantity=GSO_QUEUE_BYTES,
                availability="reservation-based",
            ),
        ),
        security_state=AdapterSecurityState(
            profile="baseline",
            credential_slots=(CREDENTIAL_SLOT_NAME,),
            attested=False,
        ),
    )


def ngso_descriptor(label: str = NGSO_LABEL) -> AdapterDescriptor:
    """The reference registration descriptor for the NGSO family
    (technology class ``access.satellite.ngso``)."""
    return AdapterDescriptor(
        adapter_id=derive_adapter_id(NGSO_TECHNOLOGY_ID, label),
        access_technology_id=NGSO_TECHNOLOGY_ID,
        supported_profile_versions=("v1-0-0",),
        capabilities=REFERENCE_CAPABILITIES,
        resource_mapping=(
            ResourceMappingEntry(
                technology_resource="ngso-relay-pass-queue",
                kind="storage",
                unit="bytes",
                quantity=NGSO_QUEUE_BYTES,
                availability="reservation-based",
            ),
        ),
        security_state=AdapterSecurityState(
            profile="baseline",
            credential_slots=(CREDENTIAL_SLOT_NAME,),
            attested=False,
        ),
    )


def leo_descriptor(label: str = LEO_LABEL) -> AdapterDescriptor:
    """The reference registration descriptor for the LEO family
    (technology class ``access.satellite.leo``)."""
    return AdapterDescriptor(
        adapter_id=derive_adapter_id(LEO_TECHNOLOGY_ID, label),
        access_technology_id=LEO_TECHNOLOGY_ID,
        supported_profile_versions=("v1-0-0",),
        capabilities=REFERENCE_CAPABILITIES,
        resource_mapping=(
            ResourceMappingEntry(
                technology_resource="leo-relay-pass-queue",
                kind="storage",
                unit="bytes",
                quantity=LEO_QUEUE_BYTES,
                availability="reservation-based",
            ),
        ),
        security_state=AdapterSecurityState(
            profile="baseline",
            credential_slots=(CREDENTIAL_SLOT_NAME,),
            attested=False,
        ),
    )


def mesh_iab_descriptor(label: str = MESH_IAB_LABEL) -> AdapterDescriptor:
    """The reference registration descriptor for the MESH/IAB family
    (technology class ``access.3gpp.iab`` — the accepted mesh
    family's own KNOWN registry entry)."""
    return AdapterDescriptor(
        adapter_id=derive_adapter_id(MESH_IAB_TECHNOLOGY_ID, label),
        access_technology_id=MESH_IAB_TECHNOLOGY_ID,
        supported_profile_versions=("v1-0-0",),
        capabilities=REFERENCE_CAPABILITIES,
        resource_mapping=(
            ResourceMappingEntry(
                technology_resource="store-and-forward-queue",
                kind="storage",
                unit="bytes",
                quantity=MESH_IAB_QUEUE_BYTES,
                availability="reservation-based",
            ),
        ),
        security_state=AdapterSecurityState(
            profile="baseline",
            credential_slots=(CREDENTIAL_SLOT_NAME,),
            attested=False,
        ),
    )


# ----------------------------------------------------------------------
# The reference compositions (the accepted family runtime, BY REFERENCE)
# ----------------------------------------------------------------------


def _require_chain_nodes(family: str, node_ids: Sequence[str]) -> Tuple[str, ...]:
    """Fail-closed chain-shape check: the family's declared relay-leg
    count over its node tuple (the GSO bent-pipe 3 nodes; the NGSO
    constellation 4 nodes; the LEO and mesh/IAB 3 nodes)."""
    if isinstance(node_ids, (str, bytes)) or not isinstance(
        node_ids, (tuple, list)
    ):
        raise MeshError(
            MeshReasonCode.INVALID_INPUT,
            "the %s reference relay chain requires a tuple of WORK-004 node "
            "ids" % family,
        )
    expected = _FAMILY_CHAIN_NODES[family]
    if len(node_ids) != expected:
        raise MeshError(
            MeshReasonCode.INVALID_INPUT,
            "the %s reference relay chain is %d legs over %d nodes (found "
            "%d node ids: %s)"
            % (
                family,
                expected - 1,
                expected,
                len(node_ids),
                ", ".join(str(node)[:34] for node in node_ids),
            ),
        )
    return tuple(node_ids)


def _mount_family_runtime(
    session_reader: Any,
    *,
    engine: Any,
    engine_label: str,
    now: str,
) -> MeshManager:
    """Wire the ACCEPTED mesh family runtime: one
    :class:`MeshManager` (read-only session facade injected) with the
    caller's engine registered as default through the manager's
    public ``register_implementation`` (the accepted M007 mesh
    composition's exact wiring, BY REFERENCE)."""
    manager = MeshManager(session_reader=session_reader)
    registered = manager.register_implementation(
        engine,
        label=engine_label,
        make_default=True,
        now=now,
    )
    if not registered.ok:
        raise MeshError(
            registered.reason,
            "satellite reference engine registration failed (%s)"
            % engine_label,
        )
    return manager


def _provision_relay_chain(
    manager: MeshManager,
    *,
    now: str,
    family: str,
    node_ids: Sequence[str],
    technology: str,
) -> Tuple[str, ...]:
    """Provision the family's relay chain — ONE
    :class:`RelayLinkDescriptor` per ADJACENT node pair — through the
    manager's public ``provision_link`` API, and return the opaque
    ``mesh:link:<hex>`` references (family-side wiring data the
    composition root legitimately holds; the WORK-016 runtime keeps
    its own technology refs opaque).  The legs' hop ids follow the
    accepted M007 mesh composition's ``link:<upstream>:<downstream>``
    convention so the caller's ordinary WORK-011 ``Path`` hops match
    them by exact string equality."""
    leg_refs = []
    for index in range(len(node_ids) - 1):
        upstream = node_ids[index]
        downstream = node_ids[index + 1]
        provisioned = manager.provision_link(
            now=now,
            descriptor=RelayLinkDescriptor(
                name="m022-%s-leg-%d" % (family, index + 1),
                link_id="link:%s:%s" % (upstream, downstream),
                upstream_node_id=upstream,
                downstream_node_id=downstream,
                technology=technology,
            ),
            credential_slot_name=CREDENTIAL_SLOT_NAME,
        )
        if not provisioned.ok:
            raise MeshError(
                provisioned.reason,
                "satellite reference relay chain provisioning failed "
                "(%s leg %d)" % (family, index + 1),
            )
        leg_refs.append(provisioned.value.link_ref)
    return tuple(leg_refs)


def _register_route(manager: MeshManager, *, now: str, path: Any) -> str:
    """Register ONE ordinary WORK-011 ``Path`` through the manager's
    public ``register_route`` API and return the route's path
    fingerprint (the ordinary WORK-011 path identity the family
    consumes as DATA — never minted here)."""
    route = manager.register_route(now=now, path=path)
    if not route.ok:
        raise MeshError(
            route.reason,
            "satellite reference route registration failed",
        )
    return route.value.path_ref


def mount_gso_reference(
    session_reader: Any,
    *,
    now: str,
    label: str = GSO_LABEL,
    node_ids: Sequence[str],
    path: Any,
    dtn_config: Optional[StoreAndForwardConfig] = None,
) -> Tuple[AdapterContract, AdapterDescriptor, Mapping[str, Any]]:
    """Compose the GSO satellite family reference adapter
    (deterministic): the BENT-PIPE geometry — the accepted family
    runtime (``MeshManager`` + the deterministic
    ``ReferenceMeshEngine`` configured with the declared GSO
    store-and-forward limits) with TWO IAB-classified relay legs
    provisioned through the manager's public API (terminal -> GSO
    relay -> ground gateway, the caller's three node ids) and ONE
    ordinary route registered over the same nodes.

    Returns ``(implementation, descriptor, binding_requirements)`` —
    the accepted WORK-016 SDK bridge to register through the
    ``accesstech`` extension surface, the reference descriptor, and
    the canonical requirements map (``route_ref``) the caller passes
    to the 1.1 ``activate``/``reconfigure`` operations (family wiring
    DATA, never an authority).
    """
    nodes = _require_chain_nodes("gso", node_ids)
    manager = _mount_family_runtime(
        session_reader,
        engine=ReferenceMeshEngine(
            queue_config=(
                GSO_DTN_CONFIG if dtn_config is None else dtn_config
            )
        ),
        engine_label="satellite-gso-m022",
        now=now,
    )
    _provision_relay_chain(
        manager, now=now, family="gso", node_ids=nodes,
        technology=RelayTechnology.IAB,
    )
    route_ref = _register_route(manager, now=now, path=path)
    bridge = MeshTechnologyAdapter(manager, label="satellite-gso-m022")
    return bridge, gso_descriptor(label), {"route_ref": route_ref}


def mount_ngso_reference(
    session_reader: Any,
    *,
    now: str,
    label: str = NGSO_LABEL,
    node_ids: Sequence[str],
    path: Any,
    dtn_config: Optional[StoreAndForwardConfig] = None,
) -> Tuple[AdapterContract, AdapterDescriptor, Mapping[str, Any]]:
    """Compose the NGSO satellite family reference adapter
    (deterministic): the CONSTELLATION geometry — the accepted family
    runtime (the deterministic ``ReferenceMeshEngine`` configured
    with the declared NGSO store-and-forward limits — the DTN
    disruption tolerance of the pass geometry) with THREE
    IAB-classified relay legs (terminal -> NGSO satellite -> NGSO
    satellite inter-satellite cross-link -> ground gateway, the
    caller's four node ids) and one ordinary route over the same
    nodes.

    The pass-handover geometry (which satellite serves which pass
    window, and every pass transition) is DECLARED DATA on the M020
    envelope (the ``accesstech`` satellite pass schedules) driven
    through the accepted ``resilience/`` handover machinery by this
    composition's consumers — never re-modeled here (the R9 charter
    consumption rule).

    Returns ``(implementation, descriptor, binding_requirements)``
    (the ``route_ref`` wiring data, exactly the accepted pattern).
    """
    nodes = _require_chain_nodes("ngso", node_ids)
    manager = _mount_family_runtime(
        session_reader,
        engine=ReferenceMeshEngine(
            queue_config=(
                NGSO_DTN_CONFIG if dtn_config is None else dtn_config
            )
        ),
        engine_label="satellite-ngso-m022",
        now=now,
    )
    _provision_relay_chain(
        manager, now=now, family="ngso", node_ids=nodes,
        technology=RelayTechnology.IAB,
    )
    route_ref = _register_route(manager, now=now, path=path)
    bridge = MeshTechnologyAdapter(manager, label="satellite-ngso-m022")
    return bridge, ngso_descriptor(label), {"route_ref": route_ref}


def mount_leo_reference(
    session_reader: Any,
    *,
    now: str,
    label: str = LEO_LABEL,
    node_ids: Sequence[str],
    path: Any,
    dtn_config: Optional[StoreAndForwardConfig] = None,
) -> Tuple[AdapterContract, AdapterDescriptor, Mapping[str, Any]]:
    """Compose the LEO satellite family reference adapter
    (deterministic): the accepted family runtime (the deterministic
    ``ReferenceMeshEngine`` configured with the declared LEO
    store-and-forward limits) with TWO IAB-classified relay legs
    (terminal -> LEO relay -> gateway, the caller's three node ids)
    and one ordinary route over the same nodes.

    Returns ``(implementation, descriptor, binding_requirements)``
    (the ``route_ref`` wiring data, exactly the accepted pattern).
    """
    nodes = _require_chain_nodes("leo", node_ids)
    manager = _mount_family_runtime(
        session_reader,
        engine=ReferenceMeshEngine(
            queue_config=(
                LEO_DTN_CONFIG if dtn_config is None else dtn_config
            )
        ),
        engine_label="satellite-leo-m022",
        now=now,
    )
    _provision_relay_chain(
        manager, now=now, family="leo", node_ids=nodes,
        technology=RelayTechnology.IAB,
    )
    route_ref = _register_route(manager, now=now, path=path)
    bridge = MeshTechnologyAdapter(manager, label="satellite-leo-m022")
    return bridge, leo_descriptor(label), {"route_ref": route_ref}


def mount_mesh_iab_reference(
    session_reader: Any,
    *,
    now: str,
    label: str = MESH_IAB_LABEL,
    node_ids: Sequence[str],
    path: Any,
    dtn_config: Optional[StoreAndForwardConfig] = None,
) -> Tuple[
    AdapterContract, AdapterDescriptor, Mapping[str, Any], Dict[str, Any]
]:
    """Compose the MESH/IAB family reference adapter (deterministic):
    the accepted family runtime with the accepted
    :class:`SidelinkRelayEngine` — the 3GPP IAB/sidelink-seam relay
    implementation — configured with the declared satellite DTN
    store-and-forward limits (:data:`SATELLITE_DTN_CONFIG` by
    default; the family engine's own public config record), TWO
    SIDELINK-classified relay legs (device -> sidelink relay ->
    donor/gateway, the caller's three node ids) and one ordinary
    route over the same nodes.

    Returns ``(implementation, descriptor, binding_requirements,
    dtn_wiring)``: the registration products plus the DTN wiring map
    (``manager`` / ``engine`` / ``leg_refs`` / ``route_ref``) —
    composition-root wiring DATA (live family objects the composition
    root holds BY REFERENCE, never registration state, never
    serialized authority).  The caller drives the family's OWN public
    DTN APIs through the wiring (``enqueue_bundle`` /
    ``forward_bundle`` / ``expire_bundles`` / ``inspect_bundle`` /
    the sidelink engine's own ``set_leg_state`` partition hook) —
    the sidelink relay + DTN store-and-forward semantics composed BY
    REFERENCE, never re-implemented here.
    """
    nodes = _require_chain_nodes("mesh-iab", node_ids)
    engine = SidelinkRelayEngine(
        queue_config=(
            SATELLITE_DTN_CONFIG if dtn_config is None else dtn_config
        )
    )
    manager = _mount_family_runtime(
        session_reader,
        engine=engine,
        engine_label="satellite-mesh-iab-m022",
        now=now,
    )
    leg_refs = _provision_relay_chain(
        manager, now=now, family="mesh-iab", node_ids=nodes,
        technology=RelayTechnology.SIDELINK,
    )
    route_ref = _register_route(manager, now=now, path=path)
    bridge = MeshTechnologyAdapter(manager, label="satellite-mesh-iab-m022")
    wiring: Dict[str, Any] = {
        "manager": manager,
        "engine": engine,
        "leg_refs": leg_refs,
        "route_ref": route_ref,
    }
    return bridge, mesh_iab_descriptor(label), {"route_ref": route_ref}, wiring
