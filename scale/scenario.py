"""WORK-039 deterministic large-scale scenario runner.

The class-B verification core: one ``ScaleScenarioSpec`` (pure,
validated, reproducible DATA) executes deterministically over REAL
per-domain WORK-015 stores, producing a journaled
``ScaleRunResult`` whose digest is byte-identical for identical specs
-- across fresh runs, across ``PYTHONHASHSEED`` values, and across
insertion orders of the spec tuples.

Execution order is ALWAYS the explicit ``(at_tick, sequence)`` key of
the journaled events (the W031 discipline).  Scenario time is ALWAYS
the injected WORK-031 ``ScenarioClock``; the harness never reads a
wall clock anywhere (structurally enforced by the battery).

What the scenario exercises, per the frozen W039 acceptance
criteria:

- **horizontal scaling** -- the world grows with ``domain_count``
  over a frozen topology shape; every object count is an exact
  predicted formula (no measurement);
- **large-scale discovery/capability exchange** -- capability, route,
  service, and resource declarations flow over every relationship
  through the real ``apply_exchange`` contract;
- **failure-domain isolation** -- failures partition delivery only;
  isolation is proven by digest immutability of non-failed stores;
- **revocation propagation** -- the ``scale.revocation`` machinery
  with explicit, fail-closed convergence bounds.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from federation import (
    ExchangeKind,
    FederationExchange,
    RelationshipState,
    Scope,
    classify_scope,
)
from protocol import canonical_json_bytes
from simulator.time import ScenarioClock

from .errors import ScaleError, ScaleReasonCode
from .model import (
    ScaleEvent,
    ScaleEventType,
    ScaleRunResult,
    TopologyShape,
    scale_event_list_digest,
)
from .partition import (
    PartitionState,
    check_isolation,
    local_first_survives,
    up_edges,
)
from .revocation import convergence_record, propagate_revocation
from .topology import (
    build_domain_materials,
    expected_edge_count,
    neighbor_map,
    topology_edges,
    validate_topology,
)
from .world import ScaleWorld, build_world

__all__ = [
    "RevocationPlan",
    "FailurePlan",
    "ExportPlan",
    "ScaleScenarioSpec",
    "run_scale_scenario",
    "verify_scale_replay",
    "scenario_summary",
]


_SCENARIO_ID_OK = frozenset(
    "abcdefghijklmnopqrstuvwxyz0123456789-"
)
_VALIDITY_WINDOW_SECONDS = 30 * 24 * 3600


def _sorted_plan_dicts(dicts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Canonical plan ordering (sorted by canonical bytes -- the
    insertion-order-independent form)."""
    return sorted(
        dicts, key=lambda item: canonical_json_bytes(item).decode("utf-8")
    )


@dataclass(frozen=True)
class RevocationPlan:
    """One planned revocation wave (pure DATA).

    ``peer_indices`` empty means every neighbour of the revoking
    domain.  ``reason`` is free text (bounded)."""

    at_tick: int
    revoking_index: int
    peer_indices: Tuple[int, ...] = ()
    reason: str = "scale-scenario"

    def content_dict(self) -> Dict[str, Any]:
        return {
            "at_tick": self.at_tick,
            "revoking_index": self.revoking_index,
            "peer_indices": list(self.peer_indices),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class FailurePlan:
    """One planned partition window (pure DATA).

    The listed domains are unreachable (delivery withheld, their
    stores stop processing scenario events) from ``at_tick`` until
    ``recover_at_tick`` (``None`` = no recovery inside this scenario).
    The listed ``failed_edges`` (topology edges between UP domains)
    are link-partitioned for the same window: both stores stay fully
    queryable; only delivery across the link is withheld.
    """

    at_tick: int
    failed_indices: Tuple[int, ...] = ()
    failed_edges: Tuple[Tuple[int, int], ...] = ()
    recover_at_tick: Optional[int] = None

    def content_dict(self) -> Dict[str, Any]:
        return {
            "at_tick": self.at_tick,
            "failed_indices": list(self.failed_indices),
            "failed_edges": [[a, b] for a, b in self.failed_edges],
            "recover_at_tick": self.recover_at_tick,
        }


@dataclass(frozen=True)
class ExportPlan:
    """One planned capability/route/service/resource declaration wave
    (pure DATA).

    ``kinds`` lists the exchange kinds each edge carries (one
    declaration per kind per edge, with deterministic refs).
    """

    at_tick: int
    kinds: Tuple[str, ...] = ()

    def content_dict(self) -> Dict[str, Any]:
        return {"at_tick": self.at_tick, "kinds": list(self.kinds)}


@dataclass(frozen=True)
class ScaleScenarioSpec:
    """The complete, immutable, reproducible scale-scenario
    configuration.

    Reproducibility contract: ``seed`` + this spec's content + the
    deterministic ``(at_tick, sequence)`` execution order produces
    byte-identical ``ScaleRunResult.run_digest()`` values.  Scenario
    time is ALWAYS the injected W031 ``ScenarioClock`` derived from
    ``start_instant`` and ``tick_seconds``.
    """

    scenario_id: str
    seed: int
    start_instant: str
    tick_seconds: int
    horizon_ticks: int
    domain_count: int
    shape: str
    declared_scopes: Tuple[str, ...] = (
        Scope.ROUTE_IMPORT,
        Scope.ROUTE_EXPORT,
        Scope.CAPABILITY_READ,
        Scope.CAPABILITY_OFFER,
        Scope.SERVICE_DISCOVER,
        Scope.RESOURCE_READ,
    )
    grant_scopes: Tuple[str, ...] = (
        Scope.ROUTE_IMPORT,
        Scope.CAPABILITY_READ,
        Scope.SERVICE_DISCOVER,
        Scope.RESOURCE_READ,
    )
    exports: Tuple[ExportPlan, ...] = ()
    revocations: Tuple[RevocationPlan, ...] = ()
    failures: Tuple[FailurePlan, ...] = ()
    observation_ticks: Tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not self.scenario_id or not set(self.scenario_id) <= _SCENARIO_ID_OK:
            raise ScaleError(
                ScaleReasonCode.SPEC_INVALID,
                "scenario_id %r must be non-empty lowercase/hyphen/digit"
                % (self.scenario_id,),
            )
        if not isinstance(self.seed, int) or self.seed < 0:
            raise ScaleError(
                ScaleReasonCode.SPEC_INVALID, "seed must be a non-negative integer"
            )
        if not isinstance(self.tick_seconds, int) or self.tick_seconds < 1:
            raise ScaleError(
                ScaleReasonCode.SPEC_INVALID, "tick_seconds must be an int >= 1"
            )
        if not isinstance(self.horizon_ticks, int) or self.horizon_ticks < 0:
            raise ScaleError(
                ScaleReasonCode.SPEC_INVALID, "horizon_ticks must be an int >= 0"
            )
        # start_instant validity is enforced by the W031 ScenarioClock
        # at run time (single validation authority for instants).
        validate_topology(self.shape, self.domain_count)
        if not self.declared_scopes:
            raise ScaleError(
                ScaleReasonCode.SPEC_INVALID,
                "a scenario requires at least one declared scope",
            )
        seen_scopes = set()
        for scope in self.declared_scopes:
            if classify_scope(scope) != "known":
                raise ScaleError(
                    ScaleReasonCode.SPEC_INVALID,
                    "declared scope %r is not in the frozen WORK-015 vocabulary"
                    % (scope,),
                )
            if scope in seen_scopes:
                raise ScaleError(
                    ScaleReasonCode.SPEC_INVALID,
                    "duplicate declared scope %r" % (scope,),
                )
            seen_scopes.add(scope)
        for scope in self.grant_scopes:
            if scope not in self.declared_scopes:
                raise ScaleError(
                    ScaleReasonCode.SPEC_INVALID,
                    "grant scope %r is outside the declared envelope "
                    "(grant escalation fails closed)" % (scope,),
                )
        neighbors = neighbor_map(
            topology_edges(self.shape, self.domain_count), self.domain_count
        )
        for rplan in self.revocations:
            if not isinstance(rplan.at_tick, int) or rplan.at_tick < 1:
                raise ScaleError(
                    ScaleReasonCode.SPEC_INVALID,
                    "revocation at_tick must be an int >= 1",
                )
            if not 0 <= rplan.revoking_index < self.domain_count:
                raise ScaleError(
                    ScaleReasonCode.SPEC_INVALID,
                    "revoking_index %r outside [0, %d)"
                    % (rplan.revoking_index, self.domain_count),
                )
            peers = rplan.peer_indices or tuple(neighbors[rplan.revoking_index])
            if not peers:
                raise ScaleError(
                    ScaleReasonCode.SPEC_INVALID,
                    "revoking domain %d has no relationships"
                    % (rplan.revoking_index,),
                )
            for peer in peers:
                if peer not in neighbors[rplan.revoking_index]:
                    raise ScaleError(
                        ScaleReasonCode.SPEC_INVALID,
                        "revocation peer %r is not a neighbour of %d"
                        % (peer, rplan.revoking_index),
                    )
            if len(set(peers)) != len(peers):
                raise ScaleError(
                    ScaleReasonCode.SPEC_INVALID,
                    "duplicate revocation peer for domain %d"
                    % (rplan.revoking_index,),
                )
            if len(rplan.reason) > 64:
                raise ScaleError(
                    ScaleReasonCode.SPEC_INVALID,
                    "revocation reason must be <= 64 characters",
                )
        topology_edge_set = {
            (edge[0], edge[1]) if edge[0] < edge[1] else (edge[1], edge[0])
            for edge in topology_edges(self.shape, self.domain_count)
        }
        for fplan in self.failures:
            if not isinstance(fplan.at_tick, int) or fplan.at_tick < 1:
                raise ScaleError(
                    ScaleReasonCode.SPEC_INVALID,
                    "failure at_tick must be an int >= 1",
                )
            for index in fplan.failed_indices:
                if not 0 <= index < self.domain_count:
                    raise ScaleError(
                        ScaleReasonCode.SPEC_INVALID,
                        "failed index %r outside [0, %d)"
                        % (index, self.domain_count),
                    )
            if len(set(fplan.failed_indices)) != len(fplan.failed_indices):
                raise ScaleError(
                    ScaleReasonCode.SPEC_INVALID,
                    "duplicate failed index",
                )
            normalized_edges = []
            for edge in fplan.failed_edges:
                key = (edge[0], edge[1]) if edge[0] < edge[1] else (edge[1], edge[0])
                if key not in topology_edge_set:
                    raise ScaleError(
                        ScaleReasonCode.SPEC_INVALID,
                        "partitioned link %r is not a topology edge" % (key,),
                    )
                normalized_edges.append(key)
            if len(set(normalized_edges)) != len(normalized_edges):
                raise ScaleError(
                    ScaleReasonCode.SPEC_INVALID,
                    "duplicate partitioned link",
                )
            if fplan.recover_at_tick is not None and fplan.recover_at_tick <= fplan.at_tick:
                raise ScaleError(
                    ScaleReasonCode.SPEC_INVALID,
                    "recover_at_tick must be after at_tick",
                )
        for eplan in self.exports:
            if not isinstance(eplan.at_tick, int) or eplan.at_tick < 1:
                raise ScaleError(
                    ScaleReasonCode.SPEC_INVALID,
                    "export at_tick must be an int >= 1",
                )
            for kind in eplan.kinds:
                if kind not in (
                    ExchangeKind.CAPABILITY_EXPORT,
                    ExchangeKind.ROUTE_EXPORT,
                    ExchangeKind.SERVICE_EXPOSURE,
                    ExchangeKind.RESOURCE_EXPOSURE,
                ):
                    raise ScaleError(
                        ScaleReasonCode.SPEC_INVALID,
                        "export kind %r is not a recording declaration kind"
                        % (kind,),
                    )
        for tick in self.observation_ticks:
            if not isinstance(tick, int) or tick < 0:
                raise ScaleError(
                    ScaleReasonCode.SPEC_INVALID,
                    "observation ticks must be non-negative integers",
                )
        if sorted(set(self.observation_ticks)) != list(self.observation_ticks):
            raise ScaleError(
                ScaleReasonCode.SPEC_INVALID,
                "observation_ticks must be sorted and unique",
            )

    def content_dict(self) -> Dict[str, Any]:
        """The canonical spec content: plan tuples and scope tuples are
        canonically SORTED, so two specs differing only in tuple order
        are the same scenario (insertion-order independence, the W031
        discipline)."""
        return {
            "scenario_id": self.scenario_id,
            "seed": self.seed,
            "start_instant": self.start_instant,
            "tick_seconds": self.tick_seconds,
            "horizon_ticks": self.horizon_ticks,
            "domain_count": self.domain_count,
            "shape": self.shape,
            "declared_scopes": sorted(self.declared_scopes),
            "grant_scopes": sorted(self.grant_scopes),
            "exports": _sorted_plan_dicts(
                [plan.content_dict() for plan in self.exports]
            ),
            "revocations": _sorted_plan_dicts(
                [plan.content_dict() for plan in self.revocations]
            ),
            "failures": _sorted_plan_dicts(
                [plan.content_dict() for plan in self.failures]
            ),
            "observation_ticks": list(self.observation_ticks),
        }

    def spec_digest(self) -> str:
        return "sha256:" + hashlib.sha256(
            canonical_json_bytes(self.content_dict())
        ).hexdigest()


class _Journal:
    """The ordered scenario journal (harness evidence, never protocol
    state)."""

    def __init__(self) -> None:
        self._events: List[ScaleEvent] = []
        self._sequence = 0

    def append(self, at_tick: int, kind: str, payload: Mapping[str, Any]) -> None:
        self._sequence += 1
        self._events.append(
            ScaleEvent(at_tick=at_tick, sequence=self._sequence, kind=kind, payload=dict(payload))
        )

    @property
    def events(self) -> Tuple[ScaleEvent, ...]:
        return tuple(self._events)


_EXPORT_REFS_FIELD = {
    ExchangeKind.CAPABILITY_EXPORT: "capability_refs",
    ExchangeKind.ROUTE_EXPORT: "route_refs",
    ExchangeKind.SERVICE_EXPOSURE: "service_refs",
    ExchangeKind.RESOURCE_EXPOSURE: "resource_refs",
}


def _export_refs(kind: str, exporter: int, wave: int) -> Tuple[str, ...]:
    """Deterministic declaration refs (DATA by reference; the refs are
    opaque ids the stores record with provenance)."""
    suffix = "%d-%d" % (exporter, wave)
    if kind == ExchangeKind.CAPABILITY_EXPORT:
        return (
            "capability.profile.scale.%s" % suffix,
            "capability.profile.scale.%s.alt" % suffix,
        )
    if kind == ExchangeKind.ROUTE_EXPORT:
        return ("route.scale.%s" % suffix,)
    if kind == ExchangeKind.SERVICE_EXPOSURE:
        return ("service.scale.%s" % suffix,)
    return ("resource.scale.%s" % suffix,)


def _apply_export_wave(
    world: ScaleWorld,
    partition: PartitionState,
    journal: _Journal,
    at_tick: int,
    kinds: Tuple[str, ...],
    wave: int,
    event_instant: str,
    counters: Dict[str, int],
) -> None:
    """Deliver one declaration wave over every UP edge (both
    directions), through the real ``apply_exchange`` contract.

    Edges whose relationship is terminal at either endpoint store are
    skipped -- a revoked relationship authorizes nothing, and a sane
    transport does not declare over it (the store would reject the
    declaration with ``relationship-terminal``; the harness simply
    does not attempt it)."""
    live_edges = up_edges(world.edges, partition)
    for a, b in sorted(live_edges):
        relationship_key = (a, b) if a < b else (b, a)
        relationship_id = world.relationship_id(*relationship_key)
        terminal = False
        for endpoint in relationship_key:
            relationship = world.store(endpoint).get_relationship(relationship_id)
            if relationship is None or relationship.state in (
                RelationshipState.REVOKED,
                RelationshipState.TERMINATED,
                RelationshipState.CANCELLED,
            ):
                terminal = True
        if terminal:
            continue
        for exporter, recipient in ((a, b), (b, a)):
            if not partition.is_up(exporter) or not partition.is_up(recipient):
                continue
            for kind in kinds:
                sequence = world.next_sequence(recipient, relationship_key)
                refs = _export_refs(kind, exporter, wave)
                field = _EXPORT_REFS_FIELD[kind]
                exchange = FederationExchange(
                    exchange_id="",
                    exchange_kind=kind,
                    local_domain_id=world.material(exporter).domain_id,
                    peer_domain_id=world.material(recipient).domain_id,
                    sequence=sequence,
                    declared_at=event_instant,
                    effective_at=event_instant,
                    peer_identity_reference=world.material(exporter).operator_node_id,
                    capability_refs=refs if field == "capability_refs" else (),
                    route_refs=refs if field == "route_refs" else (),
                    service_refs=refs if field == "service_refs" else (),
                    resource_refs=refs if field == "resource_refs" else (),
                )
                journal.append(
                    at_tick,
                    ScaleEventType.EXCHANGE_DECLARED,
                    {
                        "kind": kind,
                        "from": exporter,
                        "to": recipient,
                        "exchange_id": exchange.exchange_id,
                    },
                )
                counters["exchange_count"] += 1
                result = world.store(recipient).apply_exchange(
                    exchange, event_instant=event_instant
                )
                if result.ok:
                    counters["applied_count"] += 1
                    journal.append(
                        at_tick,
                        ScaleEventType.EXCHANGE_APPLIED,
                        {
                            "kind": kind,
                            "at": recipient,
                            "code": str(result.code),
                        },
                    )
                else:
                    counters["rejected_count"] += 1
                    journal.append(
                        at_tick,
                        ScaleEventType.EXCHANGE_REJECTED,
                        {
                            "kind": kind,
                            "at": recipient,
                            "code": str(result.code),
                        },
                    )


def run_scale_scenario(spec: ScaleScenarioSpec) -> ScaleRunResult:
    """Execute the scenario deterministically and return the journaled
    result.

    Every protocol mutation flows through a real WORK-015 store
    contract; the harness owns only delivery order and observation.
    """
    if not isinstance(spec, ScaleScenarioSpec):
        raise ScaleError(
            ScaleReasonCode.INVALID_INPUT, "spec must be a ScaleScenarioSpec"
        )
    clock = ScenarioClock(spec.start_instant, spec.tick_seconds)
    journal = _Journal()
    counters = {
        "exchange_count": 0,
        "applied_count": 0,
        "rejected_count": 0,
        "replayed_count": 0,
    }

    journal.append(
        0,
        ScaleEventType.SCENARIO_STARTED,
        {"scenario_id": spec.scenario_id, "spec_digest": spec.spec_digest()},
    )

    materials = build_domain_materials(spec.domain_count, spec.seed)
    edges = topology_edges(spec.shape, spec.domain_count)
    world = build_world(
        materials,
        edges,
        declared_scopes=spec.declared_scopes,
        grant_scopes=spec.grant_scopes,
        start_instant=clock.instant_at(0),
        valid_until=clock.instant_at(_VALIDITY_WINDOW_SECONDS // spec.tick_seconds),
        event_instant=clock.instant_at(0),
    )
    journal.append(
        0,
        ScaleEventType.WORLD_BUILT,
        {
            "domains": spec.domain_count,
            "relationships": world.relationship_count(),
            "grants": world.grant_count(),
        },
    )

    partition = PartitionState()
    convergence_records = []
    isolation_proofs = []
    # Declarations authored but not yet delivered (their recipient was
    # partitioned at issue time); they drain when the partition heals.
    pending_deliveries: List[Tuple[int, FederationExchange]] = []

    # The deterministic timeline: (at_tick, kind-order, canonical
    # payload key, body) steps -- the canonical key makes the execution
    # order fully insertion-order independent.
    timeline: List[Tuple[int, int, str, str, Any]] = []
    for eplan in spec.exports:
        timeline.append(
            (eplan.at_tick, 0, canonical_json_bytes(eplan.content_dict()).decode("utf-8"), "export", eplan)
        )
    for fplan in spec.failures:
        timeline.append(
            (fplan.at_tick, 1, canonical_json_bytes(fplan.content_dict()).decode("utf-8"), "fail", fplan)
        )
        if fplan.recover_at_tick is not None:
            timeline.append(
                (fplan.recover_at_tick, 4, canonical_json_bytes(fplan.content_dict()).decode("utf-8"), "recover", fplan)
            )
    for rplan in spec.revocations:
        timeline.append(
            (rplan.at_tick, 2, canonical_json_bytes(rplan.content_dict()).decode("utf-8"), "revoke", rplan)
        )
    for tick in spec.observation_ticks:
        timeline.append((tick, 5, str(tick), "observe", tick))
    timeline.sort(key=lambda step: (step[0], step[1], step[2]))

    export_wave = 0
    for at_tick, _, _, action, payload in timeline:
        event_instant = clock.instant_at(at_tick)
        if action == "export":
            export_wave += 1
            _apply_export_wave(
                world,
                partition,
                journal,
                at_tick,
                tuple(sorted(payload.kinds)),
                export_wave,
                event_instant,
                counters,
            )
        elif action == "fail":
            before = dict(world.digests())
            partition.fail(payload.failed_indices)
            partition.fail_edges(payload.failed_edges)
            journal.append(
                at_tick,
                ScaleEventType.DOMAIN_FAILED,
                {
                    "failed": sorted(payload.failed_indices),
                    "partitioned_links": [
                        [a, b] for a, b in sorted(payload.failed_edges)
                    ],
                },
            )
            # Isolation is proven across the failure transition itself:
            # healthy stores must be byte-identical before/after.
            after = dict(world.digests())
            proof = check_isolation(
                world, before, after, tuple(sorted(payload.failed_indices))
            )
            isolation_proofs.append(proof)
            journal.append(
                at_tick,
                ScaleEventType.ISOLATION_PROVEN,
                {"failed": sorted(payload.failed_indices), "holds": proof.holds},
            )
            # LOCK-012: relationships WITH the failed domain remain
            # queryable in healthy stores.
            for healthy in range(spec.domain_count):
                if healthy in partition.failed:
                    continue
                for peer in neighbor_map(edges, spec.domain_count)[healthy]:
                    if peer in partition.failed:
                        relationship_key = (
                            (healthy, peer) if healthy < peer else (peer, healthy)
                        )
                        ok_flag, detail = local_first_survives(
                            world.store(healthy),
                            world.relationship_id(*relationship_key),
                        )
                        if ok_flag:
                            journal.append(
                                at_tick,
                                ScaleEventType.OBSERVATION,
                                {
                                    "local_first": True,
                                    "store": healthy,
                                    "peer": peer,
                                    "detail": detail,
                                },
                            )
        elif action == "recover":
            partition.recover(payload.failed_indices)
            partition.recover_edges(payload.failed_edges)
            journal.append(
                at_tick,
                ScaleEventType.DOMAIN_RECOVERED,
                {
                    "recovered": sorted(payload.failed_indices),
                    "restored_links": [
                        [a, b] for a, b in sorted(payload.failed_edges)
                    ],
                },
            )
            # Partition healing: undelivered revocation declarations
            # drain through the real apply_exchange contract.  A peer
            # that was partitioned at issue time converges exactly now
            # -- never earlier, never by fabricated state.  The drain
            # journals the REAL store verdict (applied or the typed
            # rejection; e.g. a same-slot conflict between two pending
            # declarations on one subject fails closed, as the WORK-015
            # conflict rules demand).
            still_pending: List[Tuple[int, FederationExchange]] = []
            for peer_index, exchange in pending_deliveries:
                if not partition.is_up(peer_index):
                    still_pending.append((peer_index, exchange))
                    continue
                result = world.store(peer_index).apply_exchange(
                    exchange, event_instant=event_instant
                )
                if result.ok:
                    counters["applied_count"] += 1
                    journal.append(
                        at_tick,
                        ScaleEventType.REVOCATION_PROPAGATED,
                        {"peer": peer_index, "round": "post-recovery"},
                    )
                else:
                    counters["rejected_count"] += 1
                    journal.append(
                        at_tick,
                        ScaleEventType.EXCHANGE_REJECTED,
                        {"peer": peer_index, "code": str(result.code)},
                    )
            pending_deliveries = still_pending
            journal.append(
                at_tick,
                ScaleEventType.CONVERGENCE_OBSERVED,
                {
                    "post_recovery": True,
                    "drained": len(pending_deliveries) == 0,
                    "pending": len(pending_deliveries),
                },
            )
        elif action == "revoke":
            neighbors = neighbor_map(edges, spec.domain_count)
            peers = payload.peer_indices or tuple(
                neighbors[payload.revoking_index]
            )
            # Affected peers are those with an UP relationship path at
            # revocation time; partitioned peers are honestly unreached.
            outcome = propagate_revocation(
                world,
                revoking_index=payload.revoking_index,
                peer_indices=peers,
                reason=payload.reason,
                event_instant=event_instant,
                partition=partition,
            )
            journal.append(
                at_tick,
                ScaleEventType.REVOCATION_ISSUED,
                {
                    "revoking": payload.revoking_index,
                    "affected": len(peers),
                    "reason": payload.reason,
                },
            )
            for peer_index, round_number in sorted(outcome.applied_round.items()):
                journal.append(
                    at_tick,
                    ScaleEventType.REVOCATION_PROPAGATED,
                    {"peer": peer_index, "round": round_number},
                )
                counters["applied_count"] += 1
            for peer_index in outcome.unreached:
                pending_deliveries.append((peer_index, outcome.exchanges[peer_index]))
            counters["exchange_count"] += len(outcome.exchanges)
            counters["replayed_count"] += len(outcome.replayed_on_redelivery)
            record = convergence_record(outcome)
            journal.append(
                at_tick,
                ScaleEventType.CONVERGENCE_OBSERVED,
                {
                    "rounds": record.rounds,
                    "expected_bound": record.expected_bound,
                    "matched": record.matched,
                    "reached": len(record.reached),
                    "unreached": len(record.unreached),
                    "idempotent": record.idempotent,
                },
            )
            convergence_records.append(record)
            # Predictable effect: at every converged store the scope
            # evaluation now fails closed on the revoked relationship.
            for peer_index in record.reached:
                revoker = payload.revoking_index
                relationship_key = (
                    (revoker, peer_index) if revoker < peer_index else (peer_index, revoker)
                )
                scope_check = world.store(peer_index).check_scope(
                    world.relationship_id(*relationship_key),
                    spec.grant_scopes[0] if spec.grant_scopes else spec.declared_scopes[0],
                    evaluation_instant=event_instant,
                )
                if not scope_check.ok:
                    journal.append(
                        at_tick,
                        ScaleEventType.SCOPE_CLOSED,
                        {"store": peer_index, "code": str(scope_check.code)},
                    )
        elif action == "observe":
            digests = world.digests()
            journal.append(
                at_tick,
                ScaleEventType.OBSERVATION,
                {
                    "tick": at_tick,
                    "stores": len(digests),
                    "digest": "sha256:"
                    + hashlib.sha256(
                        canonical_json_bytes(
                            [[index, digest] for index, digest in digests]
                        )
                    ).hexdigest(),
                },
            )

    journal.append(
        max((step[0] for step in timeline), default=0) + 1,
        ScaleEventType.SCENARIO_COMPLETED,
        {
            "exchanges": counters["exchange_count"],
            "applied": counters["applied_count"],
            "rejected": counters["rejected_count"],
        },
    )

    return ScaleRunResult(
        scenario_id=spec.scenario_id,
        spec_digest=spec.spec_digest(),
        domain_count=spec.domain_count,
        relationship_count=world.relationship_count(),
        grant_count=world.grant_count(),
        exchange_count=counters["exchange_count"],
        applied_count=counters["applied_count"],
        rejected_count=counters["rejected_count"],
        replayed_count=counters["replayed_count"],
        journal=journal.events,
        store_digests=world.digests(),
        convergence=tuple(convergence_records),
        isolation=tuple(isolation_proofs),
    )


def verify_scale_replay(
    spec: ScaleScenarioSpec, *, expected_digest: str
) -> Dict[str, Any]:
    """TRUE replay verification: re-run the scenario from the spec and
    compare the complete run digest (a fresh execution, never a cached
    artifact)."""
    replay = run_scale_scenario(spec)
    digest = replay.run_digest()
    return {
        "verified": digest == expected_digest,
        "expected_digest": expected_digest,
        "observed_digest": digest,
        "journal_digest": scale_event_list_digest(replay.journal),
    }


def scenario_summary(result: ScaleRunResult) -> Dict[str, Any]:
    """A compact deterministic summary (the battery's observable
    evidence)."""
    return {
        "scenario_id": result.scenario_id,
        "spec_digest": result.spec_digest,
        "domain_count": result.domain_count,
        "relationship_count": result.relationship_count,
        "grant_count": result.grant_count,
        "exchange_count": result.exchange_count,
        "applied_count": result.applied_count,
        "rejected_count": result.rejected_count,
        "replayed_count": result.replayed_count,
        "journal_length": len(result.journal),
        "convergence_records": [record.to_dict() for record in result.convergence],
        "isolation_proofs": [proof.to_dict() for proof in result.isolation],
        "run_digest": result.run_digest(),
    }
