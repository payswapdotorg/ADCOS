"""WORK-039 federation-at-scale vocabularies and value records.

The frozen DATA vocabulary of the scale harness: the scenario-journal
event taxonomy, the multi-domain topology-shape vocabulary, the
journaled ``ScaleEvent`` (content-derived id -- the W031 style), the
``ConvergenceRecord`` / ``IsolationProof`` observation records, and
the ``ScaleRunResult`` evidence record.  Everything is canonical-bytes
digestable; the journal and run digests are the determinism contract.

NO federation vocabulary is re-defined here: scopes, lifecycle
states, exchange kinds, and reason codes belong to the WORK-015
authority and are imported from it.  The W032 ``EvidenceClass``
vocabulary is reused as DATA (the W037/W038 precedent) for the
three-class evidence map.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Tuple

from protocol import canonical_json_bytes
from protocol.canonicalization import CanonicalizationError

from conformance.model import EvidenceClass

from .errors import ScaleError, ScaleReasonCode

__all__ = [
    "ScaleEventType",
    "TopologyShape",
    "SCALE_EVIDENCE_CLASS_MAP",
    "ScaleEvent",
    "ConvergenceRecord",
    "IsolationProof",
    "ScaleRunResult",
    "scale_events_canonical_bytes",
    "scale_event_list_digest",
]


# ---------------------------------------------------------------------------
# Frozen journal vocabulary
# ---------------------------------------------------------------------------

class ScaleEventType:
    """The frozen scenario-journal event taxonomy.

    The journal records what the HARNESS observed (harness state and
    delivery decisions) plus the verdicts the REAL federation
    authorities returned.  It is evidence, never protocol state: a
    journal entry can never be replayed into a store, and a store
    never reads the journal.
    """

    SCENARIO_STARTED = "scenario-started"
    WORLD_BUILT = "world-built"
    GRANT_PUBLISHED = "grant-published"
    EXCHANGE_DECLARED = "exchange-declared"
    EXCHANGE_APPLIED = "exchange-applied"
    EXCHANGE_REJECTED = "exchange-rejected"
    EXCHANGE_REPLAYED = "exchange-replayed"
    DOMAIN_FAILED = "domain-failed"
    DOMAIN_RECOVERED = "domain-recovered"
    REVOCATION_ISSUED = "revocation-issued"
    REVOCATION_RELAYED = "revocation-relayed"
    REVOCATION_PROPAGATED = "revocation-propagated"
    RELAY_BLACKHOLED = "relay-blackholed"
    CONVERGENCE_OBSERVED = "convergence-observed"
    SCOPE_CLOSED = "scope-closed"
    ISOLATION_PROVEN = "isolation-proven"
    OBSERVATION = "observation"
    SCENARIO_COMPLETED = "scenario-completed"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.SCENARIO_STARTED,
            cls.WORLD_BUILT,
            cls.GRANT_PUBLISHED,
            cls.EXCHANGE_DECLARED,
            cls.EXCHANGE_APPLIED,
            cls.EXCHANGE_REJECTED,
            cls.EXCHANGE_REPLAYED,
            cls.DOMAIN_FAILED,
            cls.DOMAIN_RECOVERED,
            cls.REVOCATION_ISSUED,
            cls.REVOCATION_RELAYED,
            cls.REVOCATION_PROPAGATED,
            cls.RELAY_BLACKHOLED,
            cls.CONVERGENCE_OBSERVED,
            cls.SCOPE_CLOSED,
            cls.ISOLATION_PROVEN,
            cls.OBSERVATION,
            cls.SCENARIO_COMPLETED,
        )


# ---------------------------------------------------------------------------
# Frozen topology-shape vocabulary
# ---------------------------------------------------------------------------

class TopologyShape:
    """The frozen multi-domain topology shapes.

    ``RING``: each domain federates with exactly two neighbours
    (N edges, N >= 3).  ``HUB_SPOKE``: domain 0 is the hub, every
    other domain federates with the hub only (N-1 edges, N >= 2).
    ``CLIQUES``: domains are partitioned into cliques of exactly six;
    each clique is fully meshed and clique representatives form a ring
    (the inter-clique ring has 0 edges for one clique, 1 for two, k
    otherwise; N must be divisible by six).  ``FULL_MESH``: every pair
    federates (N(N-1)/2 edges; N <= 24 -- the bounded-resource
    envelope for quadratic shapes).
    """

    RING = "ring"
    HUB_SPOKE = "hub-spoke"
    CLIQUES = "cliques"
    FULL_MESH = "full-mesh"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.RING, cls.HUB_SPOKE, cls.CLIQUES, cls.FULL_MESH)


#: The frozen three-class evidence map (the W032 vocabulary reused as
#: DATA -- the W037/W038 precedent; WORK-033, a declared W039
#: dependency, composes WORK-032 the same way).
SCALE_EVIDENCE_CLASS_MAP: Dict[str, EvidenceClass] = {
    "A": EvidenceClass.ARCHITECTURE_CONFORMANCE,
    "B": EvidenceClass.AUTOMATED_VERIFICATION,
    "C": EvidenceClass.EXTERNAL_EVIDENCE,
}


# ---------------------------------------------------------------------------
# Journal records
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScaleEvent:
    """One journaled harness observation with an explicit ordering key.

    ``event_id`` is content-derived over the canonical bytes of
    ``(at_tick, sequence, kind, payload)`` (the W031 ``ScheduledEvent``
    style): insertion order in any tuple carries no identity, and two
    journals differing only in tuple order are the same journal.
    """

    at_tick: int
    sequence: int
    kind: str
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.at_tick, int) or self.at_tick < 0:
            raise ScaleError(
                ScaleReasonCode.INVALID_INPUT, "at_tick must be an int >= 0"
            )
        if not isinstance(self.sequence, int) or self.sequence < 1:
            raise ScaleError(
                ScaleReasonCode.INVALID_INPUT, "sequence must be an int >= 1"
            )
        if self.kind not in ScaleEventType.values():
            raise ScaleError(
                ScaleReasonCode.INVALID_INPUT,
                "kind %r must be one of %s" % (self.kind, ScaleEventType.values()),
            )
        if not isinstance(self.payload, Mapping):
            raise ScaleError(
                ScaleReasonCode.INVALID_INPUT, "payload must be a mapping"
            )
        for key in self.payload:
            if not isinstance(key, str) or not key:
                raise ScaleError(
                    ScaleReasonCode.INVALID_INPUT,
                    "payload keys must be non-empty strings",
                )

    def content_dict(self) -> Dict[str, Any]:
        return {
            "at_tick": self.at_tick,
            "sequence": self.sequence,
            "kind": self.kind,
            "payload": dict(self.payload),
        }

    def event_id(self) -> str:
        try:
            digest = canonical_json_bytes(self.content_dict())
        except CanonicalizationError as error:
            raise ScaleError(
                ScaleReasonCode.INVALID_INPUT,
                "event payload is not canonically representable: %s" % error,
            ) from error
        return "sha256:" + hashlib.sha256(digest).hexdigest()


def scale_events_canonical_bytes(events: Tuple[ScaleEvent, ...]) -> bytes:
    """Canonical bytes over the ORDERED journal (sorted by the explicit
    ``(at_tick, sequence)`` keys -- never by insertion order)."""
    ordered = sorted(events, key=lambda event: (event.at_tick, event.sequence))
    return canonical_json_bytes([event.content_dict() for event in ordered])


def scale_event_list_digest(events: Tuple[ScaleEvent, ...]) -> str:
    return "sha256:" + hashlib.sha256(scale_events_canonical_bytes(events)).hexdigest()


# ---------------------------------------------------------------------------
# Observation records
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConvergenceRecord:
    """One revocation-propagation observation.

    Everything here is OBSERVED from the real stores after delivery
    (or explicitly predicted from the delivery graph BEFORE delivery
    and then matched): ``rounds`` is the last round at which a peer
    applied the revocation, ``expected_bound`` is the computed
    graph-distance bound, and ``matched`` records whether the
    observation equals the bound.  A ``False`` match is a
    ``convergence-mismatch`` failure in the checker.

    The relay evidence (the multi-hop delivery proof):

    - ``paths`` -- one ``(peer, hop-path)`` pair per affected peer: the
      exact domain sequence the declaration travelled from the
      revoking domain to the peer's store (``(revoker, peer)`` for a
      direct delivery; the full relay chain when the direct edge is
      partitioned);
    - ``hops`` -- every actual hop as ``(round, from, to, peer)``:
      round r moves the declaration for ``peer`` one hop
      ``from -> to``; the FINAL hop's ``to`` is the peer, where the
      real ``apply_exchange`` applied it (the only protocol-state
      mutation in the whole propagation);
    - ``relay_digest_checks`` -- ``(relay, unchanged)`` for every PURE
      relay on any path (an intermediate domain that is not itself an
      affected peer): its store digest must be byte-identical across
      the propagation -- the relay is transport, never protocol state.
    """

    revoking_index: int
    affected_count: int
    reached: Tuple[int, ...]
    unreached: Tuple[int, ...]
    rounds: int
    expected_bound: int
    matched: bool
    exchange_count: int
    idempotent: bool
    paths: Tuple[Tuple[int, Tuple[int, ...]], ...] = ()
    hops: Tuple[Tuple[int, int, int, int], ...] = ()
    relay_digest_checks: Tuple[Tuple[int, bool], ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "revoking_index": self.revoking_index,
            "affected_count": self.affected_count,
            "reached": list(self.reached),
            "unreached": list(self.unreached),
            "rounds": self.rounds,
            "expected_bound": self.expected_bound,
            "matched": self.matched,
            "exchange_count": self.exchange_count,
            "idempotent": self.idempotent,
            "paths": [
                [peer, list(path)] for peer, path in self.paths
            ],
            "hops": [
                [round_number, hop_from, hop_to, peer]
                for round_number, hop_from, hop_to, peer in self.hops
            ],
            "relay_digest_checks": [
                [relay, unchanged] for relay, unchanged in self.relay_digest_checks
            ],
        }


@dataclass(frozen=True)
class IsolationProof:
    """One failure-domain isolation observation.

    ``checked`` carries one ``(domain_index, unchanged)`` pair per
    non-failed domain; the proof holds iff every non-failed store
    digest is byte-identical across the failure window.  The failed
    domains' own stores are NOT checked for immutability (a failed
    domain may process local operations while partitioned -- local
    first); what isolation guarantees is that THEIR state never leaks
    into healthy stores.
    """

    failed_indices: Tuple[int, ...]
    checked: Tuple[Tuple[int, bool], ...]
    holds: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "failed_indices": list(self.failed_indices),
            "checked": [[index, unchanged] for index, unchanged in self.checked],
            "holds": self.holds,
        }


@dataclass(frozen=True)
class ScaleRunResult:
    """The complete deterministic outcome of one scale-scenario run."""

    scenario_id: str
    spec_digest: str
    domain_count: int
    relationship_count: int
    grant_count: int
    exchange_count: int
    applied_count: int
    rejected_count: int
    replayed_count: int
    journal: Tuple[ScaleEvent, ...]
    store_digests: Tuple[Tuple[int, str], ...]
    convergence: Tuple[ConvergenceRecord, ...]
    isolation: Tuple[IsolationProof, ...]

    def content_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "spec_digest": self.spec_digest,
            "domain_count": self.domain_count,
            "relationship_count": self.relationship_count,
            "grant_count": self.grant_count,
            "exchange_count": self.exchange_count,
            "applied_count": self.applied_count,
            "rejected_count": self.rejected_count,
            "replayed_count": self.replayed_count,
            "journal_digest": scale_event_list_digest(self.journal),
            "store_digests": [[index, digest] for index, digest in self.store_digests],
            "convergence": [record.to_dict() for record in self.convergence],
            "isolation": [proof.to_dict() for proof in self.isolation],
        }

    def run_digest(self) -> str:
        return "sha256:" + hashlib.sha256(
            canonical_json_bytes(self.content_dict())
        ).hexdigest()
