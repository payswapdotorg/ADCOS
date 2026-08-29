"""WORK-039 revocation propagation: REAL hop-by-hop relay delivery with
explicit convergence bounds.

The authoritative state is ALWAYS the revoking domain's own WORK-015
store: ``revoke_relationship`` executes there first (trust
invalidation is a local, deterministic store operation).  Propagation
is then the DELIVERY of the revocation declarations to every affected
peer store, where they take effect ONLY through the real
``apply_exchange`` contract (sequence discipline, declarer identity
binding, idempotent exact-duplicate replay).

HOW A DECLARATION TRAVELS (the multi-hop relay semantics):

- every affected peer is a DIRECT relationship neighbour of the
  revoking domain (the revocation is about THEIR bilateral
  relationship -- ``RevocationPlan`` enforces this); the delivery to
  that peer, however, may need MULTIPLE HOPS when the direct link is
  partitioned but an alternate up path exists;
- the revoking domain authors one ``REVOCATION`` declaration per peer
  and wraps it ONCE in a real WORK-003 envelope
  (``exchange_to_envelope``) under an unregistered, grammar-conforming
  message type; the envelope then travels along the deterministic BFS
  shortest path over the currently-up delivery subgraph
  (``scale.topology.delivery_paths``) -- one hop per round, forwarded
  VERBATIM (LOCK-014 opaque forward: the relay cannot even inspect
  the payload, which is also why a relay whose own relationship was
  just revoked still forwards it -- the transport is opaque);
- EVERY hop is an actual delivery to the next domain through the real
  WORK-003 acceptance surface: the receiving domain validates the
  envelope (``protocol.accept`` with
  ``ParsePolicy(unknown_type=FORWARD_OPAQUE)``) and the receipt is
  recorded per hop (round, from, to, peer) -- this is the evidence
  that proves WHICH intermediate domains actually carried the
  declaration;
- ONLY the final recipient applies the declaration: it extracts the
  exchange from the envelope (``exchange_from_envelope``) and applies
  it through the real ``apply_exchange`` on its own store.  An
  intermediate relay NEVER applies it -- the frozen WORK-015 contract
  rejects third-domain declarations fail-closed by design (a relay
  holds no relationship between the revoking domain and the peer), so
  the relay is TRANSPORT ONLY, proven by the byte-identical store
  digests of every pure relay across the propagation.

Predictability is measured, not asserted:

- the harness computes the EXPECTED convergence bound and path for
  every peer BEFORE delivery (graph distance over the up subgraph);
- delivery proceeds in explicit ROUNDS: round r moves every
  in-flight declaration exactly one hop along its path, so a peer at
  graph distance d receives the declaration -- and its store applies
  it -- in exactly round d;
- the ``convergence-mismatch`` guard fails closed if ANY predicted-
  reachable peer is not applied at exactly its predicted round.  A
  relay whose forwarding plane is sabotaged (``PartitionState``
  black-holes: the relay is up, the links are up, but transiting
  declarations are silently dropped) stalls the declaration mid-path;
  the prediction (computed from graph reachability, which cannot know
  about the black hole) then diverges from the observation and the
  convergence proof FAILS -- loudly, with the stall position in the
  error detail, and never by fabricating state at the recipient;
- idempotency is proven by re-delivering every applied declaration
  after convergence: each store reports ``replayed`` and every store
  digest is byte-identical;
- partitioned peers (unreachable in the delivery graph) are honestly
  recorded as ``unreached`` (they converge when the partition heals
  and delivery resumes -- never by fabricating state at their store).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Tuple

if TYPE_CHECKING:  # pragma: no cover - import cycle guard (type only)
    from .world import ScaleWorld

from federation import (
    ExchangeKind,
    FederationExchange,
    FederationReasonCode,
    exchange_from_envelope,
    exchange_to_envelope,
)
from protocol import (
    Classification,
    ParsePolicy,
    UnknownTypePolicy,
    accept,
    get_codec,
    validation_clock,
)
from simulator.time import ScenarioClock

from .errors import ScaleError, ScaleReasonCode
from .model import ConvergenceRecord
from .partition import (
    PartitionState,
    assert_delivery_target,
    reachable_distances,
)
from .topology import delivery_paths

__all__ = [
    "RevocationOutcome",
    "propagate_revocation",
    "convergence_record",
    "RELAY_MESSAGE_TYPE",
]


#: The message type revocation declarations ride under inside their
#: WORK-003 envelope.  Unregistered BY DESIGN (registering a federation
#: message type would require a frozen architecture message type or an
#: explicit ACR) and grammar-conforming, so the real WORK-003
#: validation accepts the envelope and classifies it
#: ``unknown-optional-forwarded`` -- the LOCK-014 opaque-forward
#: receipt every relay produces.  This is the exact surface the frozen
#: federation exchange module documents for carriage through parties
#: that do not understand the payload.
RELAY_MESSAGE_TYPE = "federation.revocation"

#: The deterministic envelope validity window, in seconds
#: (delivery-plane only; the declaration's own ``effective_at`` is the
#: recorded revocation instant).  The window is derived through the
#: injected W031 ScenarioClock -- the deterministic time authority --
#: never through wall-clock or direct datetime arithmetic.
_RELAY_WINDOW_SECONDS = 24 * 3600


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

    @property
    def paths(self) -> Dict[int, Tuple[int, ...]]:
        """The hop path each peer's declaration travelled (from the
        revoking domain to the peer's store)."""
        return {peer: path for peer, path in self._record.paths}

    @property
    def hops(self) -> Tuple[Tuple[int, int, int, int], ...]:
        """Every actual hop, as ``(round, from, to, peer)``, sorted."""
        return self._record.hops


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


def _relay_envelope_bytes(
    world: "ScaleWorld",
    revoking_index: int,
    exchange: FederationExchange,
    event_instant: str,
) -> bytes:
    """Wrap one revocation declaration in its WORK-003 envelope and
    encode it ONCE (the bytes are forwarded verbatim at every hop --
    LOCK-014 opaque forward)."""
    window_clock = ScenarioClock(event_instant, _RELAY_WINDOW_SECONDS)
    envelope = exchange_to_envelope(
        exchange,
        message_type=RELAY_MESSAGE_TYPE,
        message_id="revocation-relay." + exchange.exchange_id,
        sender=world.material(revoking_index).operator_node_id,
        issued_at=event_instant,
        expires_at=window_clock.instant_at(1),
    )
    return get_codec("json-debug").encode(envelope)


def _hop_receipt(
    envelope_bytes: bytes, event_instant: str
) -> Tuple[bool, str]:
    """One actual hop delivery: the RECEIVING domain validates the
    forwarded envelope through the real WORK-003 acceptance surface
    under the explicit opaque-forward policy.  Returns
    ``(received, classification)``."""
    outcome = accept(
        envelope_bytes,
        now=validation_clock(event_instant),
        policy=ParsePolicy(unknown_type=UnknownTypePolicy.FORWARD_OPAQUE),
    )
    return (
        outcome.accepted
        and outcome.classification == Classification.UNKNOWN_OPTIONAL_FORWARDED,
        outcome.classification,
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
    declarations hop by hop through the relays in explicit rounds.

    The revoking domain's own store MUST be up (revocation is issued
    by the authority; a partitioned authority cannot issue).  Every
    hop is a real WORK-003 envelope receipt at the next domain; the
    final hop applies the declaration through the real
    ``apply_exchange`` at the recipient store.  The round of each
    application is recorded and checked against the pre-computed
    graph-distance bound; any divergence fails closed.
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

    # 2. Author one declaration per affected peer and wrap each in its
    #    WORK-003 relay envelope (encoded once; forwarded verbatim).
    exchanges: Dict[int, FederationExchange] = {}
    envelope_bytes: Dict[int, bytes] = {}
    for peer_index in sorted(peer_indices):
        exchanges[peer_index] = _author_revocation_exchange(
            world, revoking_index, peer_index, reason, event_instant
        )
        envelope_bytes[peer_index] = _relay_envelope_bytes(
            world, revoking_index, exchanges[peer_index], event_instant
        )

    # 3. The predicted convergence bound and the deterministic relay
    #    paths, computed BEFORE delivery (graph reachability over the
    #    currently-up subgraph; the prediction cannot know about relay
    #    sabotage -- that is the point of the discriminating test).
    distances = reachable_distances(
        world.edges, world.domain_count, revoking_index, partition
    )
    paths = delivery_paths(
        world.edges, world.domain_count, revoking_index,
        excluded=partition.failed, excluded_edges=partition.failed_edges,
    )
    predicted: Dict[int, int] = {
        peer_index: distances[peer_index]
        for peer_index in peer_indices if peer_index in distances
    }
    expected_bound = max(predicted.values()) if predicted else 0

    # The pure relays whose stores must NOT change across the whole
    # propagation (intermediate positions that are not affected peers:
    # an affected peer's store legitimately applies its own revocation).
    relay_set = sorted({
        node
        for peer_index, path in paths.items() if peer_index in predicted
        for node in path[1:-1]
        if node not in peer_indices
    })
    relay_digests_before = {
        relay: world.store_digest(relay) for relay in relay_set
    }

    # 4. The actual hop-by-hop relay delivery, in explicit rounds.
    #    Round r moves every in-flight declaration exactly one hop
    #    along its path; a peer at distance d is applied in round d.
    applied_round: Dict[int, int] = {}
    rejected: List[Tuple[int, str]] = []
    hops: List[Tuple[int, int, int, int]] = []
    position: Dict[int, int] = {
        peer_index: revoking_index for peer_index in predicted
    }
    stalled: List[Tuple[int, int, int]] = []  # (peer, at, predicted_round)

    for round_number in range(1, expected_bound + 1):
        for peer_index in sorted(predicted):
            if peer_index in applied_round or peer_index not in position:
                continue
            path = paths[peer_index]
            if round_number > len(path) - 1:
                continue
            holder = position[peer_index]
            next_hop = path[round_number]
            # the hop edge must be deliverable (both endpoints up, link
            # not partitioned) -- the paths were computed over the up
            # subgraph, so a failure here is a harness defect: fail
            # closed rather than teleport the declaration.
            if not partition.is_up(holder) or not partition.is_up(next_hop):
                stalled.append((peer_index, holder, predicted[peer_index]))
                del position[peer_index]
                continue
            assert_delivery_target(partition, next_hop)
            received, classification = _hop_receipt(
                envelope_bytes[peer_index], event_instant
            )
            if not received:
                raise ScaleError(
                    ScaleReasonCode.CONVERGENCE_MISMATCH,
                    "hop %d -> %d for peer %d was refused by the real "
                    "WORK-003 acceptance surface (%s)"
                    % (holder, next_hop, peer_index, classification),
                )
            hops.append((round_number, holder, next_hop, peer_index))
            if next_hop == peer_index:
                # the FINAL hop: the recipient extracts the declaration
                # from the envelope and applies it through the real
                # store contract -- the only protocol-state mutation.
                exchange = exchange_from_envelope(
                    get_codec("json-debug").decode(envelope_bytes[peer_index])
                )
                result = world.store(peer_index).apply_exchange(
                    exchange, event_instant=event_instant
                )
                if result.ok:
                    applied_round[peer_index] = round_number
                else:
                    rejected.append((peer_index, str(result.code)))
                    del position[peer_index]
            elif partition.is_blackholed(next_hop):
                # the delivery INTO the sabotaged relay succeeded (it is
                # up; the edge is up) but its forwarding plane silently
                # drops the declaration: the wave stalls here.
                stalled.append((peer_index, next_hop, predicted[peer_index]))
                del position[peer_index]
            else:
                position[peer_index] = next_hop

    # 5. The fail-closed convergence guard: every predicted-reachable
    #    peer must have been applied at EXACTLY its predicted round.
    #    A stalled (sabotaged) or rejected delivery is a divergence
    #    between prediction and observation -- never a fabricated
    #    convergence.
    divergences = []
    for peer_index in sorted(predicted):
        if peer_index in applied_round:
            if applied_round[peer_index] != predicted[peer_index]:
                divergences.append(
                    "peer %d applied in round %d, predicted %d"
                    % (peer_index, applied_round[peer_index], predicted[peer_index])
                )
        else:
            where = next(
                (at for peer, at, _ in stalled if peer == peer_index), None
            )
            if where is not None:
                divergences.append(
                    "peer %d predicted round %d but the declaration "
                    "stalled at relay %d (black-holed)"
                    % (peer_index, predicted[peer_index], where)
                )
            else:
                divergences.append(
                    "peer %d predicted round %d but never applied"
                    % (peer_index, predicted[peer_index])
                )
    if divergences:
        raise ScaleError(
            ScaleReasonCode.CONVERGENCE_MISMATCH,
            "revocation delivery diverged from the graph-distance bound "
            "(revoking domain %d): %s"
            % (revoking_index, "; ".join(divergences[:3])),
        )

    # 6. The relay immutability proof: every pure relay's store digest
    #    is byte-identical across the whole propagation (the relay is
    #    transport only; the frozen WORK-015 contract would reject the
    #    third-domain declaration anyway).
    relay_digest_checks: Tuple[Tuple[int, bool], ...] = tuple(
        (relay, relay_digests_before[relay] == world.store_digest(relay))
        for relay in relay_set
    )

    # 7. Idempotency: re-deliver every applied declaration once; the
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

    # 8. The convergence observation + the fail-closed bound match.
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
        paths=tuple(
            (peer_index, paths[peer_index])
            for peer_index in sorted(peer_indices)
            if peer_index in paths
        ),
        hops=tuple(sorted(hops)),
        relay_digest_checks=relay_digest_checks,
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
