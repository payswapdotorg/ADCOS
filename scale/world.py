"""WORK-039 multi-domain world construction over REAL federation
stores.

One isolated, genuine WORK-015 ``FederationStore`` per domain: the
horizontal-scale unit IS the per-domain real authority (never one
central store -- that would be a second, centralized federation
authority, which the W039 authority boundary forbids).  Every state
change flows through the stores' public contracts (``create_domain``,
``transition_domain``, ``establish_relationship``, ``publish_grant``,
``apply_exchange``); the harness holds no shadow state and mutates no
store internals.

The local view discipline: each store registers its OWN domain plus
exactly the domains it has relationships with (the honest local-first
view -- LOCK-012).  Relationships are established on BOTH sides of
every edge (each store holds its own perspective of the symmetric
relationship id).
"""

from __future__ import annotations

import hashlib
from typing import Dict, Optional, Tuple

from federation import (
    DomainLifecycle,
    FederationStore,
    GrantState,
    RelationshipState,
    derive_relationship_id,
)
from protocol import canonical_json_bytes

from .errors import ScaleError, ScaleReasonCode
from .topology import DomainMaterial, neighbor_map

__all__ = [
    "ScaleWorld",
    "build_world",
    "world_summary",
]


class ScaleWorld:
    """The multi-domain federation world: N real stores + topology
    DATA.  Read-only queries plus helpers that call ONLY public store
    contracts."""

    def __init__(
        self,
        materials: Tuple[DomainMaterial, ...],
        edges: Tuple[Tuple[int, int], ...],
        stores: Dict[int, FederationStore],
        relationship_ids: Dict[Tuple[int, int], str],
    ) -> None:
        self._materials = materials
        self._edges = edges
        self._stores = stores
        self._relationship_ids = relationship_ids

    # -- read-only surfaces ------------------------------------------

    @property
    def materials(self) -> Tuple[DomainMaterial, ...]:
        return self._materials

    @property
    def edges(self) -> Tuple[Tuple[int, int], ...]:
        return self._edges

    @property
    def domain_count(self) -> int:
        return len(self._materials)

    def material(self, index: int) -> DomainMaterial:
        self._require_index(index)
        return self._materials[index]

    def store(self, index: int) -> FederationStore:
        """The REAL WORK-015 authority owned by domain ``index``."""
        self._require_index(index)
        return self._stores[index]

    def relationship_id(self, a: int, b: int) -> str:
        key = (a, b) if a < b else (b, a)
        if key not in self._relationship_ids:
            raise ScaleError(
                ScaleReasonCode.WORLD_INVALID,
                "domains %r and %r have no relationship" % (a, b),
            )
        return self._relationship_ids[key]

    def _require_index(self, index: int) -> None:
        if not isinstance(index, int) or not 0 <= index < len(self._materials):
            raise ScaleError(
                ScaleReasonCode.DOMAIN_UNKNOWN,
                "domain index %r is outside [0, %d)" % (index, len(self._materials)),
            )

    # -- digest surfaces ----------------------------------------------

    def store_digest(self, index: int) -> str:
        """The canonical-bytes digest of one domain's REAL store
        snapshot (domains + relationships + grants + events, sorted by
        the store's own snapshot discipline)."""
        self._require_index(index)
        snapshot = self._stores[index].snapshot()
        return "sha256:" + hashlib.sha256(
            canonical_json_bytes(snapshot)
        ).hexdigest()

    def digests(self) -> Tuple[Tuple[int, str], ...]:
        """Per-domain store digests, sorted by domain index."""
        return tuple(
            (index, self.store_digest(index)) for index in range(self.domain_count)
        )

    def relationship_count(self) -> int:
        return len(self._edges)

    def grant_count(self) -> int:
        """Total grants across all stores (each side of every
        relationship publishes its own grants)."""
        return sum(
            len(self._stores[index].get_grants(self._relationship_ids[key]))
            for key in sorted(self._relationship_ids)
            for index in key
        )

    def next_sequence(self, index: int, relationship_key: Tuple[int, int]) -> int:
        """The next event-slot an exchange must occupy on its subject
        relationship in domain ``index``'s store (queried through the
        public contract, never tracked in shadow state)."""
        self._require_index(index)
        relationship_id = self.relationship_id(*relationship_key)
        relationship = self._stores[index].get_relationship(relationship_id)
        if relationship is None:
            raise ScaleError(
                ScaleReasonCode.WORLD_INVALID,
                "relationship %r missing from store %d" % (relationship_id, index),
            )
        return relationship.last_event_sequence + 1


def build_world(
    materials: Tuple[DomainMaterial, ...],
    edges: Tuple[Tuple[int, int], ...],
    *,
    declared_scopes: Tuple[str, ...],
    grant_scopes: Tuple[str, ...],
    start_instant: str,
    valid_until: str,
    event_instant: str,
) -> ScaleWorld:
    """Build the multi-domain world: N real stores, both-side
    relationships over every edge, both-side grants.

    Deterministic construction order everywhere: domains in index
    order, edges in lexicographic order, scopes in the caller's fixed
    tuple order (the stores normalize internally).  Two worlds built
    from the same material are byte-identical at every step.
    """
    if not materials:
        raise ScaleError(
            ScaleReasonCode.WORLD_INVALID, "a world requires domain material"
        )
    if not declared_scopes:
        raise ScaleError(
            ScaleReasonCode.WORLD_INVALID,
            "a world requires at least one declared scope",
        )
    for scope in grant_scopes:
        if scope not in declared_scopes:
            raise ScaleError(
                ScaleReasonCode.WORLD_INVALID,
                "grant scope %r is not in the declared scope envelope "
                "(grant escalation fails closed at world construction)" % (scope,),
            )
    count = len(materials)
    neighbors = neighbor_map(edges, count)

    stores: Dict[int, FederationStore] = {}
    for index in range(count):
        stores[index] = FederationStore()
        # register the OWN domain + every federated neighbour
        for peer_index in (index,) + neighbors[index]:
            material = materials[peer_index]
            result = stores[index].create_domain(
                material.operator_reference,
                material.identity_public_key,
                operator_node_id=material.operator_node_id,
                created_at=start_instant,
            )
            if not result.ok and result.code != "replayed":
                raise ScaleError(
                    ScaleReasonCode.WORLD_INVALID,
                    "domain registration failed at %d for %d: %s"
                    % (index, peer_index, result.detail),
                )
        # activate every registered domain (the local record of each
        # domain's lifecycle; deterministic order)
        for domain in stores[index].get_domains():
            result = stores[index].transition_domain(
                domain.domain_id,
                DomainLifecycle.ACTIVE,
                event_instant=event_instant,
            )
            if not result.ok and result.code != "replayed":
                raise ScaleError(
                    ScaleReasonCode.WORLD_INVALID,
                    "domain activation failed at %d: %s" % (index, result.detail),
                )

    relationship_ids: Dict[Tuple[int, int], str] = {}
    for a, b in edges:
        key = (a, b) if a < b else (b, a)
        relationship_ids[key] = derive_relationship_id(
            materials[key[0]].domain_id, materials[key[1]].domain_id
        )
        for local, peer in ((key[0], key[1]), (key[1], key[0])):
            result = stores[local].establish_relationship(
                materials[local].domain_id,
                materials[peer].domain_id,
                peer_identity_reference=materials[peer].operator_node_id,
                declared_scopes=declared_scopes,
                valid_from=start_instant,
                valid_until=valid_until,
                event_instant=event_instant,
            )
            if not result.ok and result.code != "replayed":
                raise ScaleError(
                    ScaleReasonCode.WORLD_INVALID,
                    "relationship establishment failed for %r: %s"
                    % (key, result.detail),
                )

    for key in sorted(relationship_ids):
        for index in key:
            for scope in sorted(grant_scopes):
                result = stores[index].publish_grant(
                    relationship_ids[key],
                    scope,
                    valid_from=start_instant,
                    valid_until=valid_until,
                    event_instant=event_instant,
                )
                if not result.ok and result.code != "replayed":
                    raise ScaleError(
                        ScaleReasonCode.WORLD_INVALID,
                        "grant publication failed for %r/%s: %s"
                        % (key, scope, result.detail),
                    )

    return ScaleWorld(materials, edges, stores, relationship_ids)


def world_summary(world: ScaleWorld) -> Dict[str, int]:
    """Exact object counts of one world (the bounded-resource
    observations: deterministic integers, never measurements)."""
    total_events = 0
    total_domains = 0
    for index in range(world.domain_count):
        store = world.store(index)
        total_domains += len(store.get_domains())
        for relationship in store.get_relationships():
            total_events += len(store.get_events(relationship.relationship_id))
        for domain in store.get_domains():
            total_events += len(store.get_events(domain.domain_id))
    return {
        "domains": world.domain_count,
        "registered_domain_records": total_domains,
        "relationships": world.relationship_count(),
        "grants": world.grant_count(),
        "event_records": total_events,
    }
