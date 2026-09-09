"""ADCOS discovery package — WORK-006: peer discovery.

Implements authenticated, access-independent local and bootstrap-assisted
peer discovery with deterministic duplicate/stale convergence and
operation after upstream Internet loss, per spec/architecture.md and the
frozen WORK-006 handoff.

The central boundary (enforced throughout):

    Discovery observation  ≠  identity  ≠  trust
                          ≠  topology authority  ≠  route
                          ≠  resource availability

A discovered peer is an authenticated OBSERVATION/record that a Node was
observed through a discovery mechanism at a particular time/context. It
must carry enough provenance and freshness metadata for WORK-007 to
consume it WITHOUT silently promoting it to authoritative topology.

Discovery logic never branches on 5G, Wi-Fi, LTE, 6G, satellite, or
vendor names. The discovery substrate is IP-based for WORK-006;
access-specific discovery integration belongs behind later adapters.
Future 6G/IMT-2030/future access nodes use exactly the same discovery
contract; their access details are capability/profile data.

Identity binding uses the canonical WORK-004 NodeID parser and
credential/provenance machinery — no duplicated identity grammar.
Signing uses the WORK-003 canonical signature-input machinery and the
WORK-004 provider abstraction. No trust, authorization, topology,
routing, resource, or federation policy is decided here.

M003 refactor (Architecture 1.1, migration matrix: "Discovery:
REFACTOR → Offer discovery, not global topology"): observations may
carry OPAQUE ``offer_references`` (the offer identities providers
announce through the discovery mechanism — preserved verbatim, never
resolved or classified here; the offers authority, M003, owns them),
and ``offer_view.py`` projects OFFER sightings (provider, offer,
freshness, provenance) from the merged store — offers, never topology.
"""

from __future__ import annotations

from .bootstrap import BootstrapSource, InMemoryBootstrapSource, poll_bootstrap
from .convergence import DiscoveryStore, MergeResult, MergeRejectedError
from .model import (
    DiscoveryError,
    DiscoveryObservation,
    SourceType,
    observation_from_mapping,
    observation_signature_input,
)
from .serialization import (
    SerializationError,
    observation_from_bytes,
    observation_to_bytes,
    observation_to_dict,
)
from .service import DiscoveryService, DiscoveryServiceError
from .signing import sign_observation, verify_observation
from .offer_view import (
    OfferSighting,
    OfferViewError,
    SIGHTING_FRESHNESS,
    active_offer_sightings,
    offer_sightings,
    sighted_offer_references,
)
from .transport import (
    DiscoveryTransport,
    InMemoryEndpoint,
    InMemoryTransportBus,
    LocalInterfaceUdpTransport,
    LoopbackUdpTransport,
    TransportError,
    is_local_ipv4,
    is_loopback_ipv4,
    is_private_ipv4,
)
from .validation import DiscoveryStatus, FreshnessError, evaluate_status

__all__ = [
    "BootstrapSource",
    "DiscoveryError",
    "DiscoveryObservation",
    "DiscoveryService",
    "DiscoveryServiceError",
    "DiscoveryStatus",
    "DiscoveryStore",
    "DiscoveryTransport",
    "FreshnessError",
    "InMemoryBootstrapSource",
    "InMemoryEndpoint",
    "InMemoryTransportBus",
    "LocalInterfaceUdpTransport",
    "LoopbackUdpTransport",
    "MergeResult",
    "MergeRejectedError",
    "OfferSighting",
    "OfferViewError",
    "SIGHTING_FRESHNESS",
    "SerializationError",
    "SourceType",
    "TransportError",
    "evaluate_status",
    "active_offer_sightings",
    "is_local_ipv4",
    "is_loopback_ipv4",
    "is_private_ipv4",
    "observation_from_bytes",
    "observation_from_mapping",
    "observation_signature_input",
    "observation_to_bytes",
    "observation_to_dict",
    "offer_sightings",
    "poll_bootstrap",
    "sighted_offer_references",
    "sign_observation",
    "verify_observation",
]
