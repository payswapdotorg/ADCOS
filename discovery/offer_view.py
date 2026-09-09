"""The offer-discovery projection (M003 refactor).

Migration classification (``spec/migration/classification-matrix.md``):
"Discovery: REFACTOR → Offer discovery, not global topology."

This module is the REFACTOR's projection surface: over a merged
``DiscoveryStore`` of authenticated observations, it surfaces OFFER
SIGHTINGS — which offers the local node has observed providers
announcing, with the observation's provenance and freshness — and
NOTHING else. A sighting answers exactly:

    "provider P's offer O was observed announced through mechanism M,
     fresh until T, per observation X (authenticated by its sender)"

A sighting is NOT topology: it carries no node/link/path/graph
structure, no reachability or route claim, no cross-provider
composition, and no trust/authorization judgment. The offer
IDENTITIES are opaque references the offers authority (M003,
``offers/``) owns; this projection preserves them verbatim, never
resolves them, and never classifies them. Cross-provider composition
is an M006+ execution-plan concern, deliberately absent.

Determinism: the evaluation instant is injected (no wall clock); the
listing is sorted by the data model (offer reference, provider,
source type, then the source observation id) — stable under input
reordering and repeat runs; only the store's CURRENT observation per
(sender, observed) key is projected (the convergence discipline
already guarantees one current record per key).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

from .convergence import DiscoveryStore
from .model import DiscoveryObservation, SourceType
from .validation import DiscoveryStatus, evaluate_status


class OfferViewError(ValueError):
    """Raised when the offer-discovery projection misused (fail
    closed). ``code`` is a stable machine-readable reason."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__("%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


#: The frozen sighting freshness vocabulary (mirrors the observation
#: freshness discipline: a stale sighting is retained for audit and
#: never silently treated as current).
SIGHTING_FRESHNESS = ("fresh", "stale")


@dataclass(frozen=True)
class OfferSighting:
    """One observed offer announcement (an OFFER sighting, not topology).

    Members: the opaque offer reference (verbatim from the observation,
    owned by the offers authority); the provider node that announced it
    (the observation's ``observed_node_id`` — an identity reference,
    never a trust claim); the source type provenance marker; the
    observation's issued/freshness instants; the sighting freshness at
    the evaluation instant; and the source observation id (provenance —
    the authenticated record the sighting was projected from)."""

    offer_reference: str
    provider_node_id: str
    source_type: str
    issued_at: str
    freshness_until: str
    sighting_freshness: str
    observation_id: str

    def sort_key(self) -> Tuple[str, str, str, str]:
        return (
            self.offer_reference,
            self.provider_node_id,
            self.source_type,
            self.observation_id,
        )

    def to_dict(self) -> dict:
        return {
            "offer_reference": self.offer_reference,
            "provider_node_id": self.provider_node_id,
            "source_type": self.source_type,
            "issued_at": self.issued_at,
            "freshness_until": self.freshness_until,
            "sighting_freshness": self.sighting_freshness,
            "observation_id": self.observation_id,
        }

    def __repr__(self) -> str:
        return (
            "OfferSighting(offer=%s, provider=%s, %s)"
            % (
                self.offer_reference[:24],
                self.provider_node_id[:24],
                self.sighting_freshness,
            )
        )


def _current_observations(store: DiscoveryStore) -> Tuple[DiscoveryObservation, ...]:
    """The store's current observations, deterministically ordered by
    (sender, observed) — the convergence discipline guarantees exactly
    one current record per key."""
    return store.snapshot()


def offer_sightings(
    store: DiscoveryStore, *, now: datetime, provider: Optional[str] = None
) -> Tuple[OfferSighting, ...]:
    """Project the offer sightings from the store at the injected
    instant.

    ``provider`` optionally scopes the projection to one provider's
    announcements (the provider-local view). Every sighting derives
    from the store's CURRENT observation for its (sender, observed)
    key; observations carrying no offer references contribute nothing.
    The result is sorted by the data model — deterministic under input
    reordering and repeat runs."""
    if not isinstance(store, DiscoveryStore):
        raise OfferViewError(
            "store", "offer_sightings requires a discovery.DiscoveryStore"
        )
    if not isinstance(now, datetime):
        raise OfferViewError("now", "the evaluation instant must be a datetime")
    if now.tzinfo is None:
        raise OfferViewError("now", "the evaluation instant must be timezone-aware")
    if provider is not None and (not isinstance(provider, str) or not provider):
        raise OfferViewError(
            "provider", "the provider scope must be a non-empty string when given"
        )
    sightings: List[OfferSighting] = []
    for observation in _current_observations(store):
        if not observation.offer_references:
            continue
        if provider is not None and observation.observed_node_id != provider:
            continue
        status = evaluate_status(observation, now=now)
        if status == DiscoveryStatus.MALFORMED:
            raise OfferViewError(
                "malformed",
                "observation %s has malformed freshness material — the "
                "projection fails closed" % observation.observation_id[:24],
            )
        freshness = (
            "fresh" if status == DiscoveryStatus.FRESH else "stale"
        )
        for offer_reference in observation.offer_references:
            sightings.append(
                OfferSighting(
                    offer_reference=offer_reference,
                    provider_node_id=observation.observed_node_id,
                    source_type=observation.source_type,
                    issued_at=observation.issued_at,
                    freshness_until=observation.freshness_until,
                    sighting_freshness=freshness,
                    observation_id=observation.observation_id,
                )
            )
    sightings.sort(key=lambda sighting: sighting.sort_key())
    return tuple(sightings)


def active_offer_sightings(
    store: DiscoveryStore, *, now: datetime, provider: Optional[str] = None
) -> Tuple[OfferSighting, ...]:
    """The FRESH offer sightings only (stale sightings remain queryable
    through ``offer_sightings`` for audit — never silently equivalent
    to current)."""
    return tuple(
        sighting
        for sighting in offer_sightings(store, now=now, provider=provider)
        if sighting.sighting_freshness == "fresh"
    )


def sighted_offer_references(
    store: DiscoveryStore, *, now: datetime, provider: Optional[str] = None
) -> Tuple[str, ...]:
    """The distinct OPAQUE offer identities sighted (sorted, deduped) —
    the bridge a consumer hands to the offers authority's exchange.
    References stay opaque: this projection resolves nothing."""
    references = {
        sighting.offer_reference
        for sighting in offer_sightings(store, now=now, provider=provider)
    }
    return tuple(sorted(references))
