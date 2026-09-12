"""ADCOS wireline family M021 reference compositions (R9-CORE-001,
DEC-0121 — the current R9 chain child, its M020 dependency satisfied).

The wireline access families of the R9 charter M021 scope: Ethernet,
fiber and enterprise-WAN reference adapter compositions on the
accepted M020 envelope domain, each composing the ACCEPTED
``adapters/backhaul/`` family runtime — the
:class:`~adapters.backhaul.manager.BackhaulManager` over the
deterministic :class:`~adapters.backhaul.engine.ReferenceBackhaulEngine`
with the accepted WORK-016 SDK bridge
(:class:`~adapters.backhaul.bridge.BackhaulTechnologyAdapter`) — BY
REFERENCE through the accepted ``adapters/capability.py`` seam (the
M007 LOCK-110/LOCK-112 boundary).  NOTHING in the frozen family
contract changes; every composition calls the family's OWN public
runtime APIs (LOCK-112 — the family models the standard mechanisms;
the citations below are the family's own frozen tags, carried
verbatim):

* ``ieee-802.3-ethernet`` — IEEE 802.3-2018 Ethernet frames (the
                              reference profile the Ethernet
                              composition provisions);
* ``ieee-802.1q-bridged``  — IEEE 802.1Q-2022 bridged LANs (the
                              enterprise-WAN site interconnect);
* ``itu-t-g709-otn``       — ITU-T G.709 optical transport trails
                              (the fiber composition's OTN trail).

The tags are citation DATA carried in the 1.1 views; the boundary
never branches on them (LOCK-112).

Compositions (one mount factory per family, the accepted
``adapters/reference/backhaul.py`` pattern — the composition root
wires the family runtime and hands back the registration products):

* :func:`mount_reference` — the ETHERNET access family (technology
  class ``access.ieee.8023``, KNOWN in the WORK-002 registry — the
  same registry entry the accepted M007 backhaul reference
  composition uses): one Ethernet link profile provisioned through
  the manager's public ``provision_link`` (1 Gbps, 8 bearers);
* :func:`mount_fiber_reference` — the FIBER access family (technology
  class ``access.itu.g709``, open-world well-formed declared data):
  one ITU-T G.709 OTN fiber trail provisioned through the same public
  API (10 Gbps, 8 bearers);
* :func:`mount_enterprise_wan_reference` — the ENTERPRISE-WAN access
  family (technology class ``access.enterprise.wan``, open-world
  well-formed declared data) over IEEE 802.1Q bridged Ethernet: the
  DECLARED site topology (:class:`SiteTopology`) with one bridged
  link provisioned per declared site pair.

**The declared enterprise-WAN site topology is DECLARED DATA ONLY
(LOCK-105 — never global topology).**  The :class:`SiteTopology`
record is the enterprise's OWN declared site set — operator-chosen
site labels on the accepted family's endpoint-label grammar (a
grammar that mechanically excludes NodeID-shaped values and every
identity form outside ``[A-Za-z0-9][A-Za-z0-9._-]*``) plus the
declared site pairs the WAN interconnects.  It carries NO NodeID, no
provider infrastructure facts, no reachability inference
(:meth:`SiteTopology.declares_pair` is an EXACT declared lookup —
the record never computes a transitive closure, so undeclared pairs
stay undeclared), and it never becomes a global topology database:
the record is a bounded, canonical-JSON-serializable declaration
with a content-derived identity (LOCK-106 discipline — sha256 over
the canonical bytes of the declared content, never wall clock, never
randomness; recomputed and compared at reconstruction).  A
declaration that references a site outside its own declared set, a
self-pair, a duplicate or disordered pair, or a tampered identity is
a TYPED rejection (fail closed, never a warning).

The wireline capability envelopes, degradation ladders (the declared
capacity steps) and handover declarations for these families live in
the M020-owned ``accesstech/`` prefix as NEW declaration modules
(``accesstech/wireline.py``) built ONLY through the accepted M020
public surface — this module never imports ``accesstech`` (the
one-way boundary: ``accesstech`` imports the adapter authorities,
never the reverse).

LOCK-110 (SDK isolation) is structural here, inherited from the
composed surfaces: every 1.1 operation returns typed, canonical,
provider-neutral records through the accepted
:class:`~adapters.capability.CapabilityAdapter` seam; the opaque
``backhaul:link:<hex>`` / ``backhaul:bearer:<hex>`` technology
references stay behind the WORK-016 runtime (keyed internally,
passed back on release); the core imports no adapter implementation
and branches on no technology name.

Determinism (LOCK-119): fixed link profiles (Ethernet 1 Gbps / fiber
10 Gbps / one 1 Gbps bridged circuit per declared site pair, 8
bearers each, fixed endpoint labels); injected instants only; no
wall clock, no randomness, no network, no secrets (credential SLOT
NAMES only — never material).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from protocol.canonicalization import CanonicalizationError, canonical_json_bytes

from .backhaul import REFERENCE_CAPABILITIES
from ..backhaul.bridge import BackhaulTechnologyAdapter
from ..backhaul.errors import BackhaulError, BackhaulReasonCode
from ..backhaul.manager import BackhaulManager
from ..backhaul.model import BackhaulProfile, LinkDescriptor
from ..backhaul.validation import validate_endpoint_label
from ..model import (
    AdapterDescriptor,
    AdapterSecurityState,
    ResourceMappingEntry,
    derive_adapter_id,
)

__all__ = [
    "STANDARD_MECHANISMS",
    "REFERENCE_TECHNOLOGY_ID",
    "FIBER_TECHNOLOGY_ID",
    "ENTERPRISE_WAN_TECHNOLOGY_ID",
    "REFERENCE_LABEL",
    "FIBER_REFERENCE_LABEL",
    "ENTERPRISE_WAN_REFERENCE_LABEL",
    "REFERENCE_LINK_BPS",
    "FIBER_TRAIL_BPS",
    "SITE_PAIR_LINK_BPS",
    "SiteTopology",
    "site_pair_key",
    "derive_site_topology_id",
    "site_topology_from_mapping",
    "REFERENCE_SITE_TOPOLOGY",
    "reference_descriptor",
    "fiber_reference_descriptor",
    "enterprise_wan_descriptor",
    "mount_reference",
    "mount_fiber_reference",
    "mount_enterprise_wan_reference",
]

#: The LOCK-112 standard-mechanism tags the wireline families' reference
#: adapters model (citation DATA, never branch input) — the accepted
#: backhaul family's own frozen citation tags, carried verbatim.
STANDARD_MECHANISMS: Tuple[str, ...] = (
    "ieee-802.3-ethernet",
    "ieee-802.1q-bridged",
    "itu-t-g709-otn",
)

#: The ETHERNET family's access technology (KNOWN in the WORK-002
#: registry: the IEEE 802.3 entry — the same registry entry the
#: accepted M007 backhaul reference composition declares).
REFERENCE_TECHNOLOGY_ID = "access.ieee.8023"

#: The FIBER family's access technology (the ITU-T G.709 optical
#: transport class — open-world well-formed declared data; the
#: architecture's registry never named it, so it enters as data,
#: exactly the R9 open-world classifier's design).
FIBER_TECHNOLOGY_ID = "access.itu.g709"

#: The ENTERPRISE-WAN family's access technology (the enterprise WAN
#: class over IEEE 802.1Q bridged Ethernet — open-world well-formed
#: declared data).
ENTERPRISE_WAN_TECHNOLOGY_ID = "access.enterprise.wan"

#: Default instance labels of the three reference compositions.
REFERENCE_LABEL = "wireline-ethernet-reference-0"
FIBER_REFERENCE_LABEL = "wireline-fiber-reference-0"
ENTERPRISE_WAN_REFERENCE_LABEL = "wireline-enterprise-wan-reference-0"

#: The reference link capacities (integer bps — the family's WORK-008
#: ``backhaul`` rate kind base units): Ethernet 1 Gbps, the ITU-T
#: G.709 OTN fiber trail 10 Gbps, one 1 Gbps bridged circuit per
#: declared enterprise-WAN site pair.
REFERENCE_LINK_BPS = 1_000_000_000
FIBER_TRAIL_BPS = 10_000_000_000
SITE_PAIR_LINK_BPS = 1_000_000_000

#: The bridge-fixed endpoint label the accepted SDK bridge falls back
#: to when caller binding requirements omit one (the same label the
#: accepted M007 backhaul reference composition provisions, so the
#: default binding coordinates resolve).
BRIDGE_ENDPOINT_LABEL = "backhaul-sdk-endpoint"

#: The family's credential SLOT NAME (LOCK-023/LOCK-119: the name
#: only — the family's boundary rejects secret-shaped material, and
#: the adapter's own private credential store stays behind the
#: family runtime).
CREDENTIAL_SLOT_NAME = "backhaul-technology-credentials"

#: The declared bearer bound on every provisioned wireline link.
MAX_BEARERS_PER_LINK = 8

#: Identity namespace (WORK-003 canonical-JSON SHA-256 convention).
_SITE_TOPOLOGY_NAMESPACE = "adcos.wireline.site-topology"

#: Fail-closed bounds on the declared site topology (a bounded
#: declaration, never an unbounded stream).
MAX_SITES = 16
MAX_SITE_PAIRS = 64


def _canonical_bytes(document: Mapping[str, Any], label: str) -> bytes:
    try:
        return canonical_json_bytes(dict(document))
    except (CanonicalizationError, TypeError, ValueError) as error:
        raise BackhaulError(
            "serialization-invalid",
            "%s is not canonicalizable: %s" % (label, error),
        ) from None


# ----------------------------------------------------------------------
# The declared enterprise-WAN site topology (DECLARED DATA — LOCK-105)
# ----------------------------------------------------------------------


def site_pair_key(site_a: str, site_b: str) -> str:
    """The canonical declared-pair key: the two site labels in sorted
    order joined by ``+`` (deterministic — the same pair always
    produces the same key regardless of argument order)."""
    first, second = sorted((site_a, site_b))
    return "%s+%s" % (first, second)


def derive_site_topology_id(
    sites: Sequence[str], site_pairs: Sequence[Sequence[str]]
) -> str:
    """The content-derived site-topology identity (LOCK-106
    discipline: sha256 over the canonical JSON of the declared
    content; no wall clock, no randomness)."""
    document = {
        "kind": "adcos.wireline.site-topology",
        "sites": list(sites),
        "site_pairs": [list(pair) for pair in site_pairs],
        "namespace": _SITE_TOPOLOGY_NAMESPACE,
    }
    return "sha256:" + hashlib.sha256(
        _canonical_bytes(document, "the declared site topology")
    ).hexdigest()


@dataclass(frozen=True)
class SiteTopology:
    """The DECLARED enterprise-WAN site topology: the enterprise's own
    declared site set plus the declared site pairs the WAN
    interconnects — DECLARED DATA ONLY (LOCK-105: never global
    topology).

    The record is a bounded declaration over operator-chosen site
    labels (each validated on the accepted family's endpoint-label
    grammar — a grammar that mechanically excludes NodeID-shaped
    values and any identity form outside ``[A-Za-z0-9][A-Za-z0-9._-]*``).
    It is NOT:

    * a topology authority — no provider infrastructure facts, no
      third-party reachability, nothing beyond the declared set;
    * a computed graph — :meth:`declares_pair` is an EXACT declared
      lookup; the record never computes a transitive closure, so a
      pair the enterprise did not declare stays undeclared however
      many declared pairs share its endpoints;
    * a global topology database — the declared sites and pairs are
      provider-local declared data, exactly the shape LOCK-105
      permits (the provider exports what the interconnect requires,
      never a global graph).

    Fail-closed declaration discipline (every malformed class a
    TYPED rejection, never a warning): the site set is non-empty,
    bounded (:data:`MAX_SITES`), sorted ascending and duplicate-free
    (deterministic declaration means exactly one canonical order);
    the pair set is non-empty, bounded (:data:`MAX_SITE_PAIRS`),
    every pair references DECLARED sites (a pair reaching outside the
    declared set is the topology-leak class — typed rejection), no
    self-pairs, no duplicates, every pair stored in canonical sorted
    order and the pair sequence sorted ascending (deterministic
    order); the identity is content-derived and tamper-evident at
    reconstruction.
    """

    sites: Tuple[str, ...]
    site_pairs: Tuple[Tuple[str, str], ...]
    topology_id: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.sites, (str, bytes)) or not isinstance(
            self.sites, (tuple, list)
        ):
            raise BackhaulError(
                BackhaulReasonCode.INVALID_INPUT,
                "declared site topology sites must be a sequence of site labels",
            )
        sites: List[str] = []
        for index, item in enumerate(self.sites):
            if not isinstance(item, str):
                raise BackhaulError(
            BackhaulReasonCode.INVALID_INPUT,
                    "declared site %d must be a site-label string" % index,
                )
            sites.append(validate_endpoint_label(item))
        if not sites:
            raise BackhaulError(
                BackhaulReasonCode.INVALID_INPUT,
                "the declared site topology carries no sites (an empty "
                "site set declares no WAN)",
            )
        if len(sites) > MAX_SITES:
            raise BackhaulError(
                BackhaulReasonCode.INVALID_INPUT,
                "at most %d sites are declarable (found %d)"
                % (MAX_SITES, len(sites)),
            )
        if len(set(sites)) != len(sites):
            raise BackhaulError(
                BackhaulReasonCode.INVALID_INPUT,
                "duplicate declared site labels are contradictory: %s"
                % ", ".join(sorted({s for s in sites if sites.count(s) > 1})),
            )
        if sites != sorted(sites):
            raise BackhaulError(
                BackhaulReasonCode.INVALID_INPUT,
                "declared sites are disordered: %s (deterministic "
                "declaration requires ascending order)"
                % ", ".join(sites),
            )
        if isinstance(self.site_pairs, (str, bytes)) or not isinstance(
            self.site_pairs, (tuple, list)
        ):
            raise BackhaulError(
                BackhaulReasonCode.INVALID_INPUT,
                "declared site pairs must be a sequence of two-site pairs",
            )
        pairs: List[Tuple[str, str]] = []
        for index, item in enumerate(self.site_pairs):
            if (
                isinstance(item, (str, bytes))
                or not isinstance(item, (tuple, list))
                or len(item) != 2
            ):
                raise BackhaulError(
            BackhaulReasonCode.INVALID_INPUT,
                    "declared site pair %d must be a two-site pair" % index,
                )
            first, second = item
            if not isinstance(first, str) or not isinstance(second, str):
                raise BackhaulError(
            BackhaulReasonCode.INVALID_INPUT,
                    "declared site pair %d endpoints must be site-label strings"
                    % index,
                )
            if first not in sites or second not in sites:
                raise BackhaulError(
            BackhaulReasonCode.INVALID_INPUT,
                    "declared site pair %s references a site outside the "
                    "declared site set %s (LOCK-105: the declared topology "
                    "is bounded by its own declaration — never a global-"
                    "topology reach)"
                    % (site_pair_key(first, second), ", ".join(sites)),
                )
            if first == second:
                raise BackhaulError(
            BackhaulReasonCode.INVALID_INPUT,
                    "declared site pair (%s, %s) is a self-pair (a site "
                    "does not interconnect with itself)" % (first, second),
                )
            low, high = sorted((first, second))
            pairs.append((low, high))
        if not pairs:
            raise BackhaulError(
                BackhaulReasonCode.INVALID_INPUT,
                "the declared site topology carries no site pairs (an empty "
                "pair set declares no WAN interconnect)",
            )
        if len(pairs) > MAX_SITE_PAIRS:
            raise BackhaulError(
                BackhaulReasonCode.INVALID_INPUT,
                "at most %d site pairs are declarable (found %d)"
                % (MAX_SITE_PAIRS, len(pairs)),
            )
        keys = [site_pair_key(first, second) for first, second in pairs]
        if len(set(keys)) != len(keys):
            raise BackhaulError(
                BackhaulReasonCode.INVALID_INPUT,
                "duplicate declared site pairs are contradictory: %s"
                % ", ".join(sorted({k for k in keys if keys.count(k) > 1})),
            )
        if keys != sorted(keys):
            raise BackhaulError(
                BackhaulReasonCode.INVALID_INPUT,
                "declared site pairs are disordered (deterministic "
                "declaration requires ascending canonical order)",
            )
        object.__setattr__(self, "sites", tuple(sites))
        object.__setattr__(self, "site_pairs", tuple(pairs))
        derived = derive_site_topology_id(sites, pairs)
        if not isinstance(self.topology_id, str) or not self.topology_id:
            object.__setattr__(self, "topology_id", derived)
        elif self.topology_id != derived:
            raise BackhaulError(
                BackhaulReasonCode.INVALID_INPUT,
                "topology_id does not match the content-derived identity "
                "(tamper evidence): declared %s, derived %s"
                % (self.topology_id, derived),
            )

    def content_dict(self) -> Dict[str, Any]:
        return {
            "sites": list(self.sites),
            "site_pairs": [list(pair) for pair in self.site_pairs],
            "topology_id": self.topology_id,
        }

    def to_dict(self) -> Dict[str, Any]:
        return self.content_dict()

    def to_canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.content_dict(), "the declared site topology")

    def declares_pair(self, site_a: str, site_b: str) -> bool:
        """EXACT declared-pair lookup (LOCK-105: declared data only —
        never a transitive closure; an undeclared pair stays
        undeclared however many declared pairs share its endpoints)."""
        if not isinstance(site_a, str) or not isinstance(site_b, str):
            raise BackhaulError(
                BackhaulReasonCode.INVALID_INPUT,
                "declares_pair endpoints must be site-label strings",
            )
        return (site_a, site_b) in self.site_pairs or (
            site_b,
            site_a,
        ) in self.site_pairs

    def pair_link_names(self) -> Tuple[str, ...]:
        """The deterministic link-profile names for the declared site
        pairs (one name per declared pair — the exact set the
        composition provisions, no inferred links)."""
        return tuple(
            "m021-wan-%s" % site_pair_key(first, second).replace("+", "-")
            for first, second in self.site_pairs
        )


def site_topology_from_mapping(value: object) -> SiteTopology:
    """Reconstruct a :class:`SiteTopology` from its canonical mapping
    (fail-closed on grammar drift and on identity tampering — the
    content-derived topology id is recomputed and compared at load)."""
    if not isinstance(value, Mapping):
        raise BackhaulError(
            BackhaulReasonCode.INVALID_INPUT,
            "the declared site topology must be a mapping",
        )
    data = dict(value)
    topology_id = data.get("topology_id")
    if not isinstance(topology_id, str) or not topology_id:
        raise BackhaulError(
            BackhaulReasonCode.INVALID_INPUT,
            "the declared site topology lacks its content-derived topology_id",
        )
    for member in ("sites", "site_pairs"):
        if member not in data:
            raise BackhaulError(
                BackhaulReasonCode.INVALID_INPUT,
                "the declared site topology lacks the %r member" % member,
            )
    sites_raw = data["sites"]
    if isinstance(sites_raw, (str, bytes)) or not isinstance(sites_raw, (tuple, list)):
        raise BackhaulError(
            BackhaulReasonCode.INVALID_INPUT,
            "declared site topology sites must be a sequence of site labels",
        )
    pairs_raw = data["site_pairs"]
    if isinstance(pairs_raw, (str, bytes)) or not isinstance(pairs_raw, (tuple, list)):
        raise BackhaulError(
            BackhaulReasonCode.INVALID_INPUT,
            "declared site pairs must be a sequence of two-site pairs",
        )
    return SiteTopology(
        sites=tuple(sites_raw),
        site_pairs=tuple(
            tuple(pair) if isinstance(pair, (tuple, list)) else pair
            for pair in pairs_raw
        ),
        topology_id=topology_id,
    )


#: The declared reference enterprise-WAN site topology (declared DATA:
#: three enterprise sites, fully meshed — the composition root's own
#: declaration; a real deployment declares its own site set through
#: the same record, and nothing beyond the declaration is ever
#: asserted).
REFERENCE_SITE_TOPOLOGY = SiteTopology(
    sites=("wan-site-a", "wan-site-b", "wan-site-c"),
    site_pairs=(
        ("wan-site-a", "wan-site-b"),
        ("wan-site-a", "wan-site-c"),
        ("wan-site-b", "wan-site-c"),
    ),
)


# ----------------------------------------------------------------------
# The reference registration descriptors (declared data)
# ----------------------------------------------------------------------


def reference_descriptor(label: str = REFERENCE_LABEL) -> AdapterDescriptor:
    """The reference registration descriptor for the ETHERNET wireline
    family (technology class ``access.ieee.8023``)."""
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
            credential_slots=(CREDENTIAL_SLOT_NAME,),
            attested=False,
        ),
    )


def fiber_reference_descriptor(label: str = FIBER_REFERENCE_LABEL) -> AdapterDescriptor:
    """The reference registration descriptor for the FIBER wireline
    family (technology class ``access.itu.g709`` — the ITU-T G.709
    OTN class, open-world declared data)."""
    return AdapterDescriptor(
        adapter_id=derive_adapter_id(FIBER_TECHNOLOGY_ID, label),
        access_technology_id=FIBER_TECHNOLOGY_ID,
        supported_profile_versions=("v1-0-0",),
        capabilities=REFERENCE_CAPABILITIES,
        resource_mapping=(
            ResourceMappingEntry(
                technology_resource="otn-trail-capacity",
                kind="backhaul",
                unit="bps",
                quantity=FIBER_TRAIL_BPS,
                availability="continuous",
            ),
        ),
        security_state=AdapterSecurityState(
            profile="baseline",
            credential_slots=(CREDENTIAL_SLOT_NAME,),
            attested=False,
        ),
    )


def enterprise_wan_descriptor(
    topology: SiteTopology = REFERENCE_SITE_TOPOLOGY,
    label: str = ENTERPRISE_WAN_REFERENCE_LABEL,
) -> AdapterDescriptor:
    """The reference registration descriptor for the ENTERPRISE-WAN
    wireline family (technology class ``access.enterprise.wan``): ONE
    consolidated mapped capacity entry — the sum over the DECLARED
    site pairs (the accepted descriptor grammar consolidates mapped
    capacity per kind/unit; the declared topology is the capacity
    derivation — LOCK-105 declared data only)."""
    return AdapterDescriptor(
        adapter_id=derive_adapter_id(ENTERPRISE_WAN_TECHNOLOGY_ID, label),
        access_technology_id=ENTERPRISE_WAN_TECHNOLOGY_ID,
        supported_profile_versions=("v1-0-0",),
        capabilities=REFERENCE_CAPABILITIES,
        resource_mapping=(
            ResourceMappingEntry(
                technology_resource="site-interconnect-capacity",
                kind="backhaul",
                unit="bps",
                quantity=SITE_PAIR_LINK_BPS * len(topology.site_pairs),
                availability="continuous",
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


def _mount_family_runtime(
    session_reader: Any,
    *,
    integration_id: str,
    engine_label: str,
    now: str,
) -> BackhaulManager:
    """Wire the ACCEPTED backhaul family runtime: one
    :class:`BackhaulManager` (read-only session facade injected) with
    the deterministic reference engine registered as default (the
    accepted M007 composition's exact wiring, BY REFERENCE)."""
    manager = BackhaulManager(
        integration_id=integration_id,
        session_reader=session_reader,
    )
    from ..backhaul.engine import ReferenceBackhaulEngine

    registered = manager.register_implementation(
        ReferenceBackhaulEngine(),
        label=engine_label,
        make_default=True,
        now=now,
    )
    if not registered.ok:
        raise BackhaulError(
            registered.reason,
            "wireline reference engine registration failed (%s)" % engine_label,
        )
    return manager


def _provision_link(
    manager: BackhaulManager,
    *,
    now: str,
    descriptor: LinkDescriptor,
) -> str:
    """Provision ONE link profile through the manager's PUBLIC
    ``provision_link`` API and return the opaque
    ``backhaul:link:<hex>`` reference (family-side wiring data the
    composition root legitimately holds — the WORK-016 runtime keeps
    its own technology refs opaque)."""
    provisioned = manager.provision_link(
        now=now,
        descriptor=descriptor,
        credential_slot_name=CREDENTIAL_SLOT_NAME,
    )
    if not provisioned.ok:
        raise BackhaulError(
            provisioned.reason,
            "wireline reference link provisioning failed (%s)" % descriptor.name,
        )
    return provisioned.value.link_ref


def mount_reference(
    session_reader: Any,
    *,
    now: str,
    label: str = REFERENCE_LABEL,
) -> Tuple[Any, AdapterDescriptor, Mapping[str, Any]]:
    """Compose the ETHERNET wireline family reference adapter
    (deterministic).

    Wires the accepted family runtime (manager + reference engine)
    and provisions ONE Ethernet link profile through the manager's
    public API (IEEE 802.3, 1 Gbps, 8 bearers, the bridge-fixed
    endpoint label), then hands back the registration products:

    ``(implementation, descriptor, binding_requirements)`` — the
    accepted WORK-016 SDK bridge to register through the
    ``accesstech`` extension surface, the reference descriptor, and
    the canonical requirements map (``link_ref``) the caller passes
    to the 1.1 ``activate``/``reconfigure`` operations (family wiring
    DATA, never an authority).
    """
    manager = _mount_family_runtime(
        session_reader,
        integration_id="adcos:backhaul:m021-ethernet",
        engine_label="wireline-ethernet-m021",
        now=now,
    )
    link_ref = _provision_link(
        manager,
        now=now,
        descriptor=LinkDescriptor(
            name="m021-ethernet-reference-link",
            profile=BackhaulProfile.ETHERNET,
            capacity_bps=REFERENCE_LINK_BPS,
            max_bearers=MAX_BEARERS_PER_LINK,
            endpoint_labels=(BRIDGE_ENDPOINT_LABEL,),
        ),
    )
    bridge = BackhaulTechnologyAdapter(manager, label="wireline-ethernet-m021")
    return bridge, reference_descriptor(label), {"link_ref": link_ref}


def mount_fiber_reference(
    session_reader: Any,
    *,
    now: str,
    label: str = FIBER_REFERENCE_LABEL,
) -> Tuple[Any, AdapterDescriptor, Mapping[str, Any]]:
    """Compose the FIBER wireline family reference adapter
    (deterministic): the same accepted family runtime with ONE ITU-T
    G.709 OTN fiber trail provisioned through the manager's public
    API (10 Gbps, 8 bearers).

    Returns ``(implementation, descriptor, binding_requirements)``
    (the ``link_ref`` wiring data, exactly the accepted pattern).
    """
    manager = _mount_family_runtime(
        session_reader,
        integration_id="adcos:backhaul:m021-fiber",
        engine_label="wireline-fiber-m021",
        now=now,
    )
    link_ref = _provision_link(
        manager,
        now=now,
        descriptor=LinkDescriptor(
            name="m021-fiber-reference-trail",
            profile=BackhaulProfile.FIBER,
            capacity_bps=FIBER_TRAIL_BPS,
            max_bearers=MAX_BEARERS_PER_LINK,
            endpoint_labels=(BRIDGE_ENDPOINT_LABEL,),
        ),
    )
    bridge = BackhaulTechnologyAdapter(manager, label="wireline-fiber-m021")
    return bridge, fiber_reference_descriptor(label), {"link_ref": link_ref}


def mount_enterprise_wan_reference(
    session_reader: Any,
    *,
    now: str,
    topology: SiteTopology = REFERENCE_SITE_TOPOLOGY,
    label: str = ENTERPRISE_WAN_REFERENCE_LABEL,
) -> Tuple[Any, AdapterDescriptor, Mapping[str, Any], Dict[str, str]]:
    """Compose the ENTERPRISE-WAN wireline family reference adapter
    (deterministic): the same accepted family runtime over IEEE
    802.1Q bridged Ethernet with ONE bridged circuit provisioned per
    DECLARED site pair (the site labels are the links' endpoint
    labels — the declared topology is the wiring).

    Returns ``(implementation, descriptor, binding_requirements,
    site_links)``: the registration products plus the declared
    site-pair link map (canonical ``site-pair key -> opaque
    ``backhaul:link:<hex>`` reference`` — DECLARED DATA ONLY, the
    composition root's own wiring map; LOCK-105: never a global
    topology).  The ``binding_requirements`` carry the default wiring
    (the first declared site pair's link and endpoint) the caller
    passes to ``activate``; mid-session reconfiguration onto another
    declared site pair passes that pair's ``link_ref`` and
    ``endpoint_label`` as the reconfigure requirements.
    """
    manager = _mount_family_runtime(
        session_reader,
        integration_id="adcos:backhaul:m021-enterprise-wan",
        engine_label="wireline-enterprise-wan-m021",
        now=now,
    )
    site_links: Dict[str, str] = {}
    for first, second in topology.site_pairs:
        key = site_pair_key(first, second)
        site_links[key] = _provision_link(
            manager,
            now=now,
            descriptor=LinkDescriptor(
                name="m021-wan-%s" % key.replace("+", "-"),
                profile=BackhaulProfile.ETHERNET,
                capacity_bps=SITE_PAIR_LINK_BPS,
                max_bearers=MAX_BEARERS_PER_LINK,
                endpoint_labels=(first, second),
            ),
        )
    first_pair = topology.site_pairs[0]
    default_link = site_links[site_pair_key(*first_pair)]
    bridge = BackhaulTechnologyAdapter(
        manager, label="wireline-enterprise-wan-m021"
    )
    return (
        bridge,
        enterprise_wan_descriptor(topology, label),
        {
            "link_ref": default_link,
            "endpoint_label": first_pair[0],
        },
        site_links,
    )
