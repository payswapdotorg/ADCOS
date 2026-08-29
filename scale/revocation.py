"""WORK-039 revocation propagation with explicit convergence bounds.

The authoritative state is ALWAYS the revoking domain's own WORK-015
store: ``revoke_relationship`` executes there first (trust
invalidation is a local, deterministic store operation).  Propagation
is then the DELIVERY of the revocation declarations to every affected
peer store, where they take effect ONLY through the real
``apply_exchange`` contract (sequence discipline, declarer identity
binding, idempotent exact-duplicate replay).

Predictability is measured, not asserted:

- the harness computes the EXPECTED convergence bound before delivery
  (the graph distance from the revoking domain to each affected peer
  over the currently-up delivery subgraph);
- delivery proceeds in explicit ROUNDS (round r reaches peers at
  distance r; relays forward the declaration when the direct edge is
  partitioned but an up path exists);
- the observed round of every application is recorded, and the
  ``convergence-mismatch`` guard fails closed if observation ever
  diverges from the bound;
- idempotency is proven by re-delivering every declaration after
  convergence: each store reports ``replayed`` and every store digest
  is byte-identical;
- partitioned peers are honestly recorded as ``unreached`` (they
  converge when the partition heals and delivery resumes -- never by
  fabricating state at their store).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Tuple

if TYPE_CHECKING:  # pragma: no cover - import cycle guard (type only)
    from .world import ScaleWorld

from federation import (
    ExchangeKind,
    FederationExchange,
    FederationReasonCode,
)

from .errors import ScaleError, ScaleReasonCode
from .model import ConvergenceRecord
from .partition import PartitionState, assert_delivery_target, reachable_distances

__all__ = [
    "RevocationOutcome",
    "propagate_revocation",
    "convergence_record",
]


class RevocationOutcome:
    """The frozen observation of one propagation wave (harness
    evidence only; the stores hold the protocol truth).  Constructed
    once, complete, by :func:`propagate_revocation`."""

    def __init__(
        self,
        revoking_index: int,
        peer_indices: Tuple[int, ...],
        reason: str,
        exchanges: Dict[int, FederationExchange],
        applied_round: Dict[int, int],
        rejected: Tuple[Tuple[int, str], ...],
        replayed_on_redelivery: Tuple[int, ...],
        record: ConvergenceRecord,
    ) -> None:
        self._revoking_index = revoking_index
        self._peer_indices = tuple(sorted(peer_indices))
        self._reason = reason
        self._exchanges = dict(exchanges)
        self._applied_round = dict(applied_round)
        self._rejected = tuple(rejected)
        self._replayed_on_redelivery = tuple(replayed_on_redelivery)
        self._record = record

    @property
    def revoking_index(self) -> int:
        return self._revoking_index

    @property
    def peer_indices(self) -> Tuple[int, ...]:
        return self._peer_indices

    @property
    def reason(self) -> str:
        return self._reason

    @property
    def exchanges(self) -> Dict[int, FederationExchange]:
        return dict(self._exchanges)

    @property
    def applied_round(self) -> Dict[int, int]:
        return dict(self._applied_round)

    @property
    def rejected(self) -> Tuple[Tuple[int, str], ...]:
        return self._rejected

    @property
    def replayed_on_redelivery(self) -> Tuple[int, ...]:
        return self._replayed_on_redelivery

    @property
    def record(self) -> ConvergenceRecord:
        return self._record

    @property
    def reached(self) -> Tuple[int, ...]:
        return tuple(sorted(self._applied_round))

    @property
    def unreached(self) -> Tuple[int, ...]:
        return tuple(
            index for index in self._peer_indices
            if index not in self._applied_round
        )

    @property
    def rounds(self) -> int:
        return max(self._applied_round.values()) if self._applied_round else 0


def _author_revocation_exchange(
    world: "ScaleWorld",
    revoking_index: int,
    peer_index: int,
    reason: str,
    event_instant: str,
) -> FederationExchange:
    """Author the REVOCATION declaration from the revoking domain to
    one peer, occupying the peer store's next event slot on the
    subject relationship (queried through the public contract)."""
    relationship_key = (
        (revoking_index, peer_index)
        if revoking_index < peer_index
        else (peer_index, revoking_index)
    )
    sequence = world.next_sequence(peer_index, relationship_key)
    return FederationExchange(
        exchange_id="",
        exchange_kind=ExchangeKind.REVOCATION,
        local_domain_id=world.material(revoking_index).domain_id,
        peer_domain_id=world.material(peer_index).domain_id,
        sequence=sequence,
        declared_at=event_instant,
        effective_at=event_instant,
        peer_identity_reference=world.material(revoking_index).operator_node_id,
        reason=reason,
    )


def propagate_revocation(
    world: "ScaleWorld",
    *,
    revoking_index: int,
    peer_indices: Tuple[int, ...],
    reason: str,
    event_instant: str,
    partition: PartitionState,
) -> RevocationOutcome:
    """Revoke at the AUTHORITATIVE store, then deliver the revocation
    declarations in explicit rounds.

    The revoking domain's own store MUST be up (revocation is issued
    by the authority; a partitioned authority cannot issue).  Every
    delivery goes through the real ``apply_exchange``; the round of
    each application is recorded and checked against the pre-computed
    graph-distance bound.
    """
    if not partition.is_up(revoking_index):
        raise ScaleError(
            ScaleReasonCode.DELIVERY_REFUSED,
            "the revoking domain %d is partitioned; revocation cannot be "
            "issued while its authority is unreachable" % (revoking_index,),
        )
    if not peer_indices:
        raise ScaleError(
            ScaleReasonCode.INVALID_INPUT,
            "propagation requires at least one affected peer",
        )

    # 1. The authoritative local revocations (one per relationship).
    for peer_index in sorted(peer_indices):
        relationship_key = (
            (revoking_index, peer_index)
            if revoking_index < peer_index
            else (peer_index, revoking_index)
        )
        relationship_id = world.relationship_id(*relationship_key)
        result = world.store(revoking_index).revoke_relationship(
            relationship_id, event_instant=event_instant, reason=reason
        )
        if not result.ok and result.code not in (
            FederationReasonCode.REVOKED,
            FederationReasonCode.REPLAYED,
        ):
            raise ScaleError(
                ScaleReasonCode.AUTHORITY_VIOLATION,
                "authoritative revocation failed for peer %d: %s"
                % (peer_index, result.detail),
            )

    # 2. Author one declaration per affected peer.
    exchanges: Dict[int, FederationExchange] = {}
    for peer_index in sorted(peer_indices):
        exchanges[peer_index] = _author_revocation_exchange(
            world, revoking_index, peer_index, reason, event_instant
        )

    # 3. The expected convergence bound (computed BEFORE delivery).
    distances = reachable_distances(
        world.edges, world.domain_count, revoking_index, partition
    )
    expected_bound = max(
        (distances[index] for index in peer_indices if index in distances),
        default=0,
    )

    # 4. Deliver in explicit rounds (round r reaches distance-r peers;
    #    relays carry the declaration when the direct edge is down).
    applied_round: Dict[int, int] = {}
    rejected: List[Tuple[int, str]] = []
    for round_number in range(1, expected_bound + 1):
        for peer_index in sorted(peer_indices):
            if peer_index in applied_round:
                continue
            if distances.get(peer_index) != round_number:
                continue
            assert_delivery_target(partition, peer_index)
            result = world.store(peer_index).apply_exchange(
                exchanges[peer_index], event_instant=event_instant
            )
            if result.ok:
                applied_round[peer_index] = round_number
            else:
                rejected.append((peer_index, str(result.code)))

    # 5. Idempotency: re-deliver every applied declaration once; the
    #    store must report ``replayed`` with a byte-identical digest.
    replayed: List[int] = []
    for peer_index in sorted(applied_round):
        before = world.store_digest(peer_index)
        result = world.store(peer_index).apply_exchange(
            exchanges[peer_index], event_instant=event_instant
        )
        after = world.store_digest(peer_index)
        if result.ok and result.code == FederationReasonCode.REPLAYED and before == after:
            replayed.append(peer_index)

    # 6. The convergence observation + the fail-closed bound match.
    observed_rounds = max(applied_round.values()) if applied_round else 0
    matched = observed_rounds == expected_bound
    record = ConvergenceRecord(
        revoking_index=revoking_index,
        affected_count=len(peer_indices),
        reached=tuple(sorted(applied_round)),
        unreached=tuple(
            index for index in sorted(peer_indices) if index not in applied_round
        ),
        rounds=observed_rounds,
        expected_bound=expected_bound,
        matched=matched,
        exchange_count=len(exchanges),
        idempotent=(len(replayed) == len(applied_round)),
    )
    if not matched:
        raise ScaleError(
            ScaleReasonCode.CONVERGENCE_MISMATCH,
            "observed convergence rounds %d != expected bound %d "
            "(revoking domain %d, %d peers)"
            % (observed_rounds, expected_bound, revoking_index, len(peer_indices)),
        )
    return RevocationOutcome(
        revoking_index=revoking_index,
        peer_indices=peer_indices,
        reason=reason,
        exchanges=exchanges,
        applied_round=applied_round,
        rejected=tuple(rejected),
        replayed_on_redelivery=tuple(replayed),
        record=record,
    )


def convergence_record(outcome: RevocationOutcome) -> ConvergenceRecord:
    """The frozen convergence observation of one propagation."""
    return outcome.record
