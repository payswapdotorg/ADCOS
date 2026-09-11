"""ADCOS mesh/relay family M007 reference composition (R7-CORE-001).

The mesh/relay family's M007 surface: this module composes the family's
ACCEPTED WORK-023 runtime — the
:class:`~adapters.mesh.manager.MeshManager` over the deterministic
:class:`~adapters.mesh.engine.ReferenceMeshEngine` — with the accepted
WORK-016 SDK bridge (:class:`~adapters.mesh.bridge.MeshTechnologyAdapter`)
and the reference registration data
(:func:`reference_descriptor`) the execution boundary consumes.  The
1.1 capability-oriented surface (:class:`adapters.capability.CapabilityAdapter`)
composes on top; NOTHING in the frozen family contract changes.

LOCK-112 (standard leverage — the mechanisms this family models, taken
from the family's own frozen citations, never reinvented here):

* ``3gpp-iab``            — 3GPP integrated access and backhaul
                            (multi-hop relay paths; the family's
                            ordinary WORK-011 Path integration);
* ``3gpp-sidelink-relay`` — 3GPP sidelink relay integration;
* ``dtn-store-and-forward`` — DTN-class configured
                            store-and-forward bundles (bounded queues,
                            deterministic expiry, duplicate/replay
                            detection — the family's bundle discipline).

The tags are citation DATA carried in the 1.1 views
(:attr:`STANDARD_MECHANISMS`); the boundary never branches on them.

Determinism (LOCK-119): the composition is a pure function of its
inputs — a fixed two-hop relay chain and one ordinary route registered
at the injected ``now``; no wall clock, no randomness, no network.
The binding requirement the reference composition hands back
(``route_ref`` — an ordinary WORK-011 path fingerprint) is family-side
wiring DATA the caller passes to ``activate``/``reconfigure``
requirements; it is never minted here (the route is registered with
the manager, which derives its own path fingerprint).
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Tuple

from ..contract import AdapterContext, AdapterContract
from ..model import (
    AdapterDescriptor,
    AdapterSecurityState,
    ResourceMappingEntry,
    derive_adapter_id,
)
from ..mesh.bridge import MeshTechnologyAdapter
from ..mesh.engine import ReferenceMeshEngine
from ..mesh.manager import MeshManager
from ..mesh.model import RelayLinkDescriptor

#: The LOCK-112 standard-mechanism tags this family's reference
#: adapter models (citation DATA, never branch input).
STANDARD_MECHANISMS: Tuple[str, ...] = (
    "3gpp-iab",
    "3gpp-sidelink-relay",
    "dtn-store-and-forward",
)

#: The reference access technology for this family (KNOWN in the
#: WORK-002 registry: the IAB entry).
REFERENCE_TECHNOLOGY_ID = "access.3gpp.iab"

#: Default instance label of the reference composition.
REFERENCE_LABEL = "mesh-reference-0"

#: Capability references the reference composition declares
#: (UNKNOWN_BUT_WELL_FORMED in the WORK-002 grammar — preserved
#: verbatim; the family ladder mediates the live exposure).
REFERENCE_CAPABILITIES: Tuple[str, ...] = (
    "capability.profile.mesh.route",
    "capability.profile.mesh.store-and-forward",
    "capability.profile.mesh.bearer",
)

#: The reference store-and-forward queue capacity (integer bytes).
REFERENCE_QUEUE_BYTES = 100_000_000


def reference_descriptor(label: str = REFERENCE_LABEL) -> AdapterDescriptor:
    """The reference registration descriptor for the mesh family."""
    return AdapterDescriptor(
        adapter_id=derive_adapter_id(REFERENCE_TECHNOLOGY_ID, label),
        access_technology_id=REFERENCE_TECHNOLOGY_ID,
        supported_profile_versions=("v1-0-0",),
        capabilities=REFERENCE_CAPABILITIES,
        resource_mapping=(
            ResourceMappingEntry(
                technology_resource="store-and-forward-queue",
                kind="storage",
                unit="bytes",
                quantity=REFERENCE_QUEUE_BYTES,
                availability="reservation-based",
            ),
        ),
        security_state=AdapterSecurityState(
            profile="baseline",
            credential_slots=("relay-management",),
            attested=False,
        ),
    )


def mount_reference(
    session_reader: Any,
    *,
    now: str,
    label: str = REFERENCE_LABEL,
    node_ids: Tuple[str, str, str],
    path: Any,
) -> Tuple[AdapterContract, AdapterDescriptor, Mapping[str, Any]]:
    """Compose the mesh family reference adapter (deterministic).

    Wires the accepted family runtime: one
    :class:`MeshManager` (read-only session facade injected), the
    deterministic :class:`ReferenceMeshEngine` registered as default,
    a fixed two-hop relay chain (``node_ids[0] -> node_ids[1] ->
    node_ids[2]``) and one ordinary two-hop route (the caller's
    ``path`` — an ordinary WORK-011 ``Path`` over the same nodes)
    registered through the manager's public API.

    Returns ``(implementation, descriptor, binding_requirements)``:
    the WORK-016 nine-op adapter to register with the
    :class:`~adapters.runtime.AdapterRuntime`, the reference
    descriptor, and the canonical requirements map (``route_ref``)
    the caller passes to the 1.1 ``activate``/``reconfigure``
    operations — family wiring DATA, never an authority.
    """
    manager = MeshManager(session_reader=session_reader)
    registered = manager.register_implementation(
        ReferenceMeshEngine(),
        label="mesh-m007",
        make_default=True,
        now=now,
    )
    if not registered.ok:
        from ..mesh.errors import MeshError

        raise MeshError(registered.reason, "reference engine registration failed")
    upstream, midstream, downstream = node_ids
    chain = (
        ("link:%s:%s" % (upstream, midstream), upstream, midstream),
        ("link:%s:%s" % (midstream, downstream), midstream, downstream),
    )
    for link_id, hop_upstream, hop_downstream in chain:
        provisioned = manager.provision_link(
            now=now,
            descriptor=RelayLinkDescriptor(
                name="m007-leg",
                link_id=link_id,
                upstream_node_id=hop_upstream,
                downstream_node_id=hop_downstream,
            ),
            credential_slot_name="relay-management",
        )
        if not provisioned.ok:
            from ..mesh.errors import MeshError

            raise MeshError(
                provisioned.reason, "reference relay chain provisioning failed"
            )
    route = manager.register_route(now=now, path=path)
    if not route.ok:
        from ..mesh.errors import MeshError

        raise MeshError(route.reason, "reference route registration failed")
    bridge = MeshTechnologyAdapter(manager, label="mesh-m007")
    return bridge, reference_descriptor(label), {"route_ref": route.value.path_ref}
