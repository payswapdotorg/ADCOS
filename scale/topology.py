"""WORK-039 deterministic multi-domain topology construction.

Pure arithmetic over an explicit seed: how many domains exist, which
pairs federate, and what the delivery distances are.  This module
builds DATA only -- no store, no authority, no protocol state.  The
domain identity material is derived through the REAL WORK-015
``derive_domain_id`` fingerprint (the harness never invents its own
domain-id grammar), and the per-domain key material comes from the
accepted WORK-031 ``DeterministicStream`` (the documented counter-
based sha256 PRNG -- no ``random`` module anywhere in the family).

Operator NodeIDs use the WORK-004 canonical text form with the
``test.profile.v1`` development profile (the same form the WORK-015
battery uses); the harness never derives or rotates node identities
-- it references canonical NodeIDs by text, exactly as federation
validation consumes them.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Set, Tuple

from federation import derive_domain_id
from protocol import canonical_json_bytes
from simulator.random import DeterministicStream

from .errors import ScaleError, ScaleReasonCode
from .model import TopologyShape

__all__ = [
    "DomainMaterial",
    "CLIQUE_SIZE",
    "FULL_MESH_MAX_DOMAINS",
    "build_domain_materials",
    "topology_edges",
    "expected_edge_count",
    "neighbor_map",
    "delivery_distances",
    "delivery_paths",
    "validate_topology",
]


#: The fixed clique size for the CLIQUES shape (six domains per clique).
CLIQUE_SIZE = 6

#: The bounded-resource envelope for the quadratic FULL_MESH shape.
FULL_MESH_MAX_DOMAINS = 24


@dataclass(frozen=True)
class DomainMaterial:
    """One domain's deterministic identity material.

    ``domain_id`` is derived through the REAL WORK-015 fingerprint at
    construction (tamper evidence: constructing a DomainMaterial with
    a mismatched domain_id fails closed)."""

    index: int
    operator_reference: str
    identity_public_key: str
    operator_node_id: str
    domain_id: str

    def __post_init__(self) -> None:
        expected = derive_domain_id(
            self.operator_reference, self.identity_public_key
        )
        if not self.domain_id:
            object.__setattr__(self, "domain_id", expected)
        elif self.domain_id != expected:
            raise ScaleError(
                ScaleReasonCode.TOPOLOGY_INVALID,
                "domain_id does not match the derived WORK-015 fingerprint",
            )

    def to_dict(self) -> Dict[str, str]:
        return {
            "index": str(self.index),
            "operator_reference": self.operator_reference,
            "identity_public_key": self.identity_public_key,
            "operator_node_id": self.operator_node_id,
            "domain_id": self.domain_id,
        }


def build_domain_materials(
    count: int, seed: int
) -> Tuple[DomainMaterial, ...]:
    """Derive ``count`` domains' identity material deterministically.

    The key material and operator NodeID suffixes come from the
    accepted WORK-031 ``DeterministicStream`` bound to the explicit
    seed; the domain ids come from the real WORK-015 fingerprint over
    that material.  Same ``(count, seed)`` -> byte-identical material,
    always (no wall clock, no ``random``).
    """
    if not isinstance(count, int) or count < 2:
        raise ScaleError(
            ScaleReasonCode.TOPOLOGY_INVALID,
            "count must be an int >= 2 (got %r)" % (count,),
        )
    if not isinstance(seed, int) or seed < 0:
        raise ScaleError(
            ScaleReasonCode.TOPOLOGY_INVALID, "seed must be a non-negative int"
        )
    stream = DeterministicStream(seed, label="scale-topology")
    materials = []
    for index in range(count):
        key_hex = _hex_material(stream, 64)
        node_suffix = _hex_material(stream, 64)
        materials.append(
            DomainMaterial(
                index=index,
                operator_reference="operator-scale-%04d" % index,
                identity_public_key=key_hex,
                operator_node_id="adcos:node:test.profile.v1:" + node_suffix,
                domain_id="",
            )
        )
    return tuple(materials)


def _hex_material(stream: DeterministicStream, hex_chars: int) -> str:
    """Draw ``hex_chars`` lowercase hex characters from the accepted
    W031 stream (one byte per two characters; deterministic word
    order)."""
    if hex_chars % 2 != 0:
        raise ScaleError(
            ScaleReasonCode.INVALID_INPUT, "hex_material requires an even length"
        )
    return bytes(stream.uint(256) for _ in range(hex_chars // 2)).hex()


def validate_topology(shape: str, count: int) -> None:
    """Fail-closed topology-shape validation (the bounded-resource
    envelope included)."""
    if shape not in TopologyShape.values():
        raise ScaleError(
            ScaleReasonCode.SHAPE_UNKNOWN,
            "shape %r must be one of %s" % (shape, TopologyShape.values()),
        )
    if not isinstance(count, int) or count < 2:
        raise ScaleError(
            ScaleReasonCode.TOPOLOGY_INVALID,
            "domain_count must be an int >= 2 (got %r)" % (count,),
        )
    if shape == TopologyShape.RING and count < 3:
        raise ScaleError(
            ScaleReasonCode.TOPOLOGY_INVALID,
            "ring topology requires at least 3 domains",
        )
    if shape == TopologyShape.CLIQUES and count % CLIQUE_SIZE != 0:
        raise ScaleError(
            ScaleReasonCode.TOPOLOGY_INVALID,
            "cliques topology requires domain_count divisible by %d"
            % (CLIQUE_SIZE,),
        )
    if shape == TopologyShape.FULL_MESH and count > FULL_MESH_MAX_DOMAINS:
        raise ScaleError(
            ScaleReasonCode.TOPOLOGY_INVALID,
            "full-mesh topology is bounded to %d domains (bounded-resource "
            "envelope for quadratic shapes; got %d)"
            % (FULL_MESH_MAX_DOMAINS, count),
        )


def _normalize_edge(edge: Tuple[int, int]) -> Tuple[int, int]:
    """Normalize one edge to ``(min, max)``."""
    a, b = edge
    return (a, b) if a < b else (b, a)


def _dedup_edges(edges: Tuple[Tuple[int, int], ...]) -> Tuple[Tuple[int, int], ...]:
    """Normalize every edge to ``(min, max)`` and deduplicate."""
    normalized = {_normalize_edge(edge) for edge in edges}
    return tuple(sorted(normalized))


def topology_edges(shape: str, count: int) -> Tuple[Tuple[int, int], ...]:
    """The relationship edges for one topology shape.

    Edges are ``(i, j)`` index pairs with ``i < j``, returned in
    lexicographic order (insertion-order independent by
    construction)."""
    validate_topology(shape, count)
    if shape == TopologyShape.RING:
        edges: List[Tuple[int, int]] = [
            (i, (i + 1) % count) for i in range(count)
        ]
        return _dedup_edges(tuple(edges))
    if shape == TopologyShape.HUB_SPOKE:
        return tuple((0, i) for i in range(1, count))
    if shape == TopologyShape.CLIQUES:
        clique_count = count // CLIQUE_SIZE
        edges = []
        for clique in range(clique_count):
            base = clique * CLIQUE_SIZE
            for a in range(CLIQUE_SIZE):
                for b in range(a + 1, CLIQUE_SIZE):
                    edges.append((base + a, base + b))
        if clique_count >= 2:
            for clique in range(clique_count):
                representative = clique * CLIQUE_SIZE
                successor = ((clique + 1) % clique_count) * CLIQUE_SIZE
                if representative != successor:
                    edges.append(_normalize_edge((representative, successor)))
        return _dedup_edges(tuple(edges))
    # FULL_MESH
    return tuple(
        (i, j) for i in range(count) for j in range(i + 1, count)
    )


def expected_edge_count(shape: str, count: int) -> int:
    """The exact predicted relationship count for one shape (the
    horizontal-scaling formula the battery asserts against)."""
    validate_topology(shape, count)
    if shape == TopologyShape.RING:
        return count
    if shape == TopologyShape.HUB_SPOKE:
        return count - 1
    if shape == TopologyShape.CLIQUES:
        clique_count = count // CLIQUE_SIZE
        intra = clique_count * (CLIQUE_SIZE * (CLIQUE_SIZE - 1) // 2)
        if clique_count <= 1:
            inter = 0
        elif clique_count == 2:
            inter = 1
        else:
            inter = clique_count
        return intra + inter
    return count * (count - 1) // 2


def neighbor_map(
    edges: Tuple[Tuple[int, int], ...], count: int
) -> Dict[int, Tuple[int, ...]]:
    """Sorted adjacency map over the relationship edges."""
    neighbors: Dict[int, Tuple[int, ...]] = {index: () for index in range(count)}
    sets: Dict[int, Set[int]] = {index: set() for index in range(count)}
    for a, b in edges:
        sets.setdefault(a, set()).add(b)
        sets.setdefault(b, set()).add(a)
    for index in range(count):
        neighbors[index] = tuple(sorted(sets.get(index, set())))
    return neighbors


def delivery_distances(
    edges: Tuple[Tuple[int, int], ...],
    count: int,
    source: int,
    *,
    excluded: FrozenSet[int] = frozenset(),
    excluded_edges: FrozenSet[Tuple[int, int]] = frozenset(),
) -> Dict[int, int]:
    """BFS distances from ``source`` over the UP delivery subgraph.

    Failed (``excluded``) domains and their incident edges, plus the
    explicitly partitioned links (``excluded_edges``), are removed
    from the delivery graph entirely -- this is the harness's
    delivery model (transport-plane reachability in simulation),
    NEVER protocol state.  Unreachable domains are absent from the
    result.
    """
    if not isinstance(source, int) or not 0 <= source < count:
        raise ScaleError(
            ScaleReasonCode.DOMAIN_UNKNOWN,
            "source %r is not a domain index in [0, %d)" % (source, count),
        )
    if source in excluded:
        return {}
    blocked = {_normalize_edge(edge) for edge in excluded_edges}
    adjacency: Dict[int, Set[int]] = {index: set() for index in range(count)}
    for edge in edges:
        a, b = edge
        if a in excluded or b in excluded:
            continue
        if _normalize_edge(edge) in blocked:
            continue
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)
    distances: Dict[int, int] = {source: 0}
    frontier = [source]
    while frontier:
        next_frontier = []
        for node in frontier:
            for peer in sorted(adjacency.get(node, ())):
                if peer not in distances:
                    distances[peer] = distances[node] + 1
                    next_frontier.append(peer)
        frontier = next_frontier
    return distances


def delivery_paths(
    edges: Tuple[Tuple[int, int], ...],
    count: int,
    source: int,
    *,
    excluded: FrozenSet[int] = frozenset(),
    excluded_edges: FrozenSet[Tuple[int, int]] = frozenset(),
) -> Dict[int, Tuple[int, ...]]:
    """Deterministic shortest DELIVERY PATHS from ``source`` over the UP
    delivery subgraph (the hop sequence a relayed declaration travels).

    Same delivery model as :func:`delivery_distances` (failed domains and
    partitioned links removed; transport-plane reachability, never
    protocol state).  The path for each reachable domain is the BFS
    shortest path under the deterministic discipline (frontier in
    discovery order, neighbours in sorted order -- the first discovery
    fixes the parent), so the hop sequence is a pure function of the
    topology and the partition state: two identical worlds relay along
    byte-identical paths.  ``paths[v][0] == source`` and
    ``len(paths[v]) - 1 == delivery_distances(...)[v]`` for every
    reachable ``v``; unreachable domains are absent from the result.
    """
    distances = delivery_distances(
        edges, count, source, excluded=excluded, excluded_edges=excluded_edges
    )
    if source not in distances:
        return {}
    blocked = {_normalize_edge(edge) for edge in excluded_edges}
    adjacency: Dict[int, Tuple[int, ...]] = {
        index: () for index in range(count)
    }
    for a, b in edges:
        if a in excluded or b in excluded:
            continue
        if _normalize_edge((a, b)) in blocked:
            continue
        adjacency.setdefault(a, tuple())
        adjacency.setdefault(b, tuple())
        merged_a = adjacency.get(a, ()) + (b,)
        merged_b = adjacency.get(b, ()) + (a,)
        adjacency[a] = tuple(sorted(set(merged_a)))
        adjacency[b] = tuple(sorted(set(merged_b)))
    parents: Dict[int, int] = {}
    frontier = [source]
    while frontier:
        next_frontier = []
        for node in frontier:
            for peer in adjacency.get(node, ()):
                if peer in parents or peer == source:
                    continue
                parents[peer] = node
                next_frontier.append(peer)
        frontier = next_frontier
    paths: Dict[int, Tuple[int, ...]] = {source: (source,)}
    for node in sorted(parents):
        chain = [node]
        cursor = node
        while cursor != source:
            cursor = parents[cursor]
            chain.append(cursor)
        paths[node] = tuple(reversed(chain))
    # the parent-tree path length must equal the BFS distance exactly
    for node, path in paths.items():
        if len(path) - 1 != distances[node]:
            raise ScaleError(
                ScaleReasonCode.WORLD_INVALID,
                "delivery path for %d has %d hops but distance %d"
                % (node, len(path) - 1, distances[node]),
            )
    return paths


def edge_fingerprint(edges: Tuple[Tuple[int, int], ...]) -> str:
    """A stable digest over the edge set (order-independent)."""
    material = [
        [a, b] for a, b in sorted(_normalize_edge(edge) for edge in edges)
    ]
    return "sha256:" + hashlib.sha256(canonical_json_bytes(material)).hexdigest()
