"""WORK-039 partition/failure injection and failure-domain isolation.

The failure model is TRANSPORT-PLANE ONLY: a failed domain is a
domain the harness will not deliver exchanges to or from, and whose
own store stops processing scenario events while failed.  This is
simulation of UNREACHABILITY -- it is never protocol state, never a
lifecycle mutation of any domain record, and never a second authority
(the WORK-015 store validation remains the only gate that decides
what state may change).

Isolation is PROVEN, not assumed:

1. **Digest immutability** -- every non-failed store's canonical
   snapshot digest is byte-identical across the failure window
   (failures in one domain never mutate healthy stores);
2. **Fail-closed foreign declarations** -- a declaration authored by
   a failed domain, a third-domain declaration, or an identity-
   confused declaration is rejected by the REAL store validation and
   leaves the store digest unchanged;
3. **Local-first survival** -- relationships WITH the failed domain
   remain queryable and evaluable in healthy stores (LOCK-012);
4. **Containment** -- a rejected/poisoned application at one store
   never raises into, or mutates, another store.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, FrozenSet, Tuple

if TYPE_CHECKING:  # pragma: no cover - import cycle guard (type only)
    from .world import ScaleWorld

from federation import FederationExchange, FederationStore, RelationshipState

from .errors import ScaleError, ScaleReasonCode
from .model import IsolationProof
from .topology import delivery_distances

__all__ = [
    "PartitionState",
    "up_edges",
    "reachable_distances",
    "check_isolation",
    "foreign_declaration_rejected",
    "local_first_survives",
]


@dataclass
class PartitionState:
    """The harness's delivery-plane view of which domains and which
    links are currently unreachable (pure harness state; the stores
    know nothing about it).

    Two partition granularities, both delivery-plane only:

    - ``failed`` domains -- whole-domain failure (the failure-DOMAIN
      unit): nothing is delivered to or from the domain, and its own
      store stops processing scenario events while failed;
    - ``failed_edges`` -- link partitions between two UP domains (the
      W031 link-down discipline): the pair's relationship remains
      fully queryable at both stores (local-first); only delivery
      between them is withheld, forcing propagation through relays.
    """

    _failed: FrozenSet[int] = field(default_factory=frozenset)
    _failed_edges: FrozenSet[Tuple[int, int]] = field(default_factory=frozenset)

    @property
    def failed(self) -> FrozenSet[int]:
        return self._failed

    @property
    def failed_edges(self) -> FrozenSet[Tuple[int, int]]:
        return self._failed_edges

    def is_up(self, index: int) -> bool:
        return index not in self._failed

    def fail(self, indices: Tuple[int, ...]) -> None:
        self._failed = self._failed | frozenset(indices)

    def recover(self, indices: Tuple[int, ...]) -> None:
        self._failed = self._failed - frozenset(indices)

    def fail_edges(self, edges: Tuple[Tuple[int, int], ...]) -> None:
        normalized = {
            (a, b) if a < b else (b, a) for a, b in edges
        }
        self._failed_edges = self._failed_edges | frozenset(normalized)

    def recover_edges(self, edges: Tuple[Tuple[int, int], ...]) -> None:
        normalized = {
            (a, b) if a < b else (b, a) for a, b in edges
        }
        self._failed_edges = self._failed_edges - frozenset(normalized)


def up_edges(
    edges: Tuple[Tuple[int, int], ...], partition: PartitionState
) -> Tuple[Tuple[int, int], ...]:
    """The edges whose BOTH endpoints are currently up AND that are
    not themselves partitioned."""
    return tuple(
        edge for edge in edges
        if partition.is_up(edge[0]) and partition.is_up(edge[1])
        and (edge[0], edge[1]) not in partition.failed_edges
    )


def reachable_distances(
    edges: Tuple[Tuple[int, int], ...],
    count: int,
    source: int,
    partition: PartitionState,
) -> Dict[int, int]:
    """Delivery distances from ``source`` over the currently-up
    subgraph (the explicit propagation-bound input).  Both failed
    domains and partitioned links are removed from the delivery
    graph."""
    return delivery_distances(
        edges, count, source,
        excluded=partition.failed,
        excluded_edges=partition.failed_edges,
    )


def check_isolation(
    world: "ScaleWorld",
    before_digests: Dict[int, str],
    after_digests: Dict[int, str],
    failed_indices: Tuple[int, ...],
) -> IsolationProof:
    """Prove failure-domain isolation by digest immutability.

    Every NON-failed domain's store digest must be byte-identical
    between ``before_digests`` and ``after_digests``.  The failed
    domains' own stores are excluded from the check: a partitioned
    domain may still process purely local operations while isolated
    (local-first); isolation guarantees the failure never LEAKS into
    healthy stores.
    """
    checked: Tuple[Tuple[int, bool], ...] = tuple(
        (
            index,
            before_digests.get(index) == after_digests.get(index),
        )
        for index in range(world.domain_count)
        if index not in failed_indices
    )
    holds = all(unchanged for _, unchanged in checked)
    return IsolationProof(
        failed_indices=tuple(sorted(failed_indices)),
        checked=checked,
        holds=holds,
    )


def foreign_declaration_rejected(
    store: FederationStore,
    exchange: FederationExchange,
    *,
    event_instant: str,
) -> Tuple[bool, str]:
    """Apply one (expected-invalid) declaration through the REAL
    store contract and observe the typed rejection.

    Returns ``(rejected, code)``.  The caller proves the store digest
    is unchanged afterwards (the rejection must be side-effect free).
    """
    result = store.apply_exchange(exchange, event_instant=event_instant)
    return (not result.ok, str(result.code))


def local_first_survives(
    store: FederationStore, relationship_id: str
) -> Tuple[bool, str]:
    """LOCK-012 observation: a relationship with a partitioned peer
    remains queryable (history preserved) while the peer is gone."""
    relationship = store.get_relationship(relationship_id)
    if relationship is None:
        return (False, "relationship missing while peer partitioned")
    events = store.get_events(relationship_id)
    if not events:
        return (False, "relationship history vanished while peer partitioned")
    state_ok = relationship.state in RelationshipState.values()
    if not state_ok:
        return (False, "relationship state corrupted while peer partitioned")
    return (True, "queryable with %d events; state %r" % (len(events), relationship.state))


def assert_delivery_target(
    partition: PartitionState, index: int
) -> None:
    """Fail-closed delivery guard: the harness refuses to deliver to a
    currently-failed domain (delivery to a partitioned domain is
    withheld, not queued as protocol state)."""
    if not partition.is_up(index):
        raise ScaleError(
            ScaleReasonCode.DELIVERY_REFUSED,
            "domain %d is currently partitioned; delivery withheld" % (index,),
        )
