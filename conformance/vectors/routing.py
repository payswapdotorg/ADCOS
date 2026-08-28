"""WORK-032 conformance vectors -- routing (WORK-011).

Covers: routing determinism, policy-decision consumption (deny /
absent / tampered), snapshot digest pinning, tamper-evident path ids,
intent/resource constraints, confidence floors, forbidden property
tokens, and invalid inputs.  Routing only selects among permitted
feasible candidates; it never re-decides authorization.
"""

from __future__ import annotations

from typing import Any, Callable, FrozenSet, Tuple

from routing import RouteReasonCode

from conformance.model import ConformanceVector, ExpectedOutcome, ObservedOutcome
from conformance.world import NOW, T0, T1, ConformanceWorld

from routing import RoutingContext

from topology import ClaimType, SourceClass, TopologyClaim, make_link_subject

__all__ = ["vectors"]

_AREA = "routing"
_AUTHORITY = "WORK-011"
_CONTRACT = "spec/architecture.md section 12 (routing) / WORK-011"


def _vector(number: str, polarity: str, invariant: str,
            description: str, expected: ExpectedOutcome,
            execute: Callable[[ConformanceWorld], ObservedOutcome],
            tags: FrozenSet[str] = frozenset()) -> ConformanceVector:
    return ConformanceVector(
        vector_id="W032-CNF-RTG-%s" % number,
        area=_AREA,
        polarity=polarity,
        authority=_AUTHORITY,
        contract=_CONTRACT,
        invariant=invariant,
        description=description,
        expected=expected,
        execute=execute,
        tags=tags,
    )


def vectors() -> Tuple[ConformanceVector, ...]:
    out = []

    # -- RTG-001: deterministic selected route --------------------------------
    def _rtg001(world: ConformanceWorld) -> ObservedOutcome:
        routing = world.routing
        first = routing.decision(world.node_a, world.node_b, NOW)
        second = routing.decision(world.node_a, world.node_b, NOW)
        if first.decision_id == second.decision_id and first.selected is not None:
            return ObservedOutcome(
                True, "selected",
                "identical context produces an identical content-derived "
                "decision id with a selected path",
            )
        return ObservedOutcome(
            False, "routing-unstable",
            "decision ids differ across identical evaluations",
        )

    out.append(_vector(
        "001", "positive",
        "routing is deterministic with content-derived decision ids",
        "Two evaluations of the same context yield the same decision_id.",
        ExpectedOutcome(True, frozenset({RouteReasonCode.SELECTED})),
        _rtg001,
        frozenset({"positive:core-behavior", "positive:determinism"}),
    ))

    # -- RTG-002: insertion-order independence ---------------------------------
    def _rtg002(world: ConformanceWorld) -> ObservedOutcome:
        routing = world.routing
        subject_ab = make_link_subject(world.node_a, world.node_b)
        subject_bc = make_link_subject(world.node_b, world.node_c)
        graph = _two_hop_graph(world)
        metrics_regular = {
            subject_ab: routing.metrics(latency_ms=10),
            subject_bc: routing.metrics(latency_ms=10),
        }
        metrics_reversed = {
            subject_bc: routing.metrics(latency_ms=10),
            subject_ab: routing.metrics(latency_ms=10),
        }
        first = routing.evaluate(routing.context(
            world.node_a, world.node_c, NOW,
            graph=graph, link_metrics=metrics_regular,
        ))
        second = routing.evaluate(routing.context(
            world.node_a, world.node_c, NOW,
            graph=graph, link_metrics=metrics_reversed,
        ))
        if first.decision is None or second.decision is None:
            return ObservedOutcome(
                False, "no-decision",
                "two-hop evaluation produced no decision",
            )
        if (first.decision.decision_id == second.decision.decision_id
                and first.decision.selected is not None):
            return ObservedOutcome(
                True, RouteReasonCode.SELECTED,
                "link-metric insertion order does not affect the decision",
            )
        return ObservedOutcome(
            False, "order-dependent",
            "decision ids differ across metric insertion orders",
        )

    out.append(_vector(
        "002", "positive",
        "candidate construction and ranking are insertion-order independent",
        "Reversing the link-metrics mapping yields the same decision id.",
        ExpectedOutcome(True, frozenset({RouteReasonCode.SELECTED})),
        _rtg002,
        frozenset({"positive:determinism"}),
    ))

    # -- RTG-003: denied policy decision blocks routing -------------------------
    def _rtg003(world: ConformanceWorld) -> ObservedOutcome:
        routing = world.routing
        denied = routing.policy(NOW, effect="deny", code="deny")
        result = routing.evaluate(routing.context(
            world.node_a, world.node_b, NOW, policy=denied,
        ))
        if result.decision is not None:
            return ObservedOutcome(
                result.decision.code == RouteReasonCode.POLICY_DENIED,
                result.decision.code,
                "denied policy decision produced %s" % result.decision.code,
            )
        return ObservedOutcome(False, result.code, result.detail)

    out.append(_vector(
        "003", "negative",
        "a denied policy decision is never reinterpreted as permission",
        "RoutingContext with effect=deny -> policy-denied.",
        ExpectedOutcome(False, frozenset({RouteReasonCode.POLICY_DENIED})),
        _rtg003,
        frozenset({"negative:binding-violation",
                   "discriminating:authority-boundary"}),
    ))

    # -- RTG-004: absent policy decision fails closed ----------------------------
    def _rtg004(world: ConformanceWorld) -> ObservedOutcome:
        routing = world.routing
        context = routing.context(world.node_a, world.node_b, NOW,
                                  policy=None)
        # rebuild without a policy decision
        context = RoutingContext(
            source_node_id=world.node_a,
            destination_node_id=world.node_b,
            topology=routing.graph(world.node_a, world.node_b),
            resources=routing.context(world.node_a, world.node_b, NOW
                                      ).resources,
            evaluation_instant=NOW,
            link_metrics={
                make_link_subject(world.node_a, world.node_b):
                    routing.metrics()
            },
        )
        result = routing.evaluate(context)
        if result.decision is not None:
            return ObservedOutcome(
                result.decision.code == RouteReasonCode.POLICY_DENIED,
                result.decision.code,
                "absent policy produced %s" % result.decision.code,
            )
        return ObservedOutcome(False, result.code, result.detail)

    out.append(_vector(
        "004", "negative",
        "missing permission is denial (no route score becomes policy)",
        "RoutingContext without a policy decision -> policy-denied.",
        ExpectedOutcome(False, frozenset({RouteReasonCode.POLICY_DENIED})),
        _rtg004,
        frozenset({"negative:binding-violation",
                   "discriminating:authority-boundary"}),
    ))

    # -- RTG-005: tampered policy decision ----------------------------------------
    def _rtg005(world: ConformanceWorld) -> ObservedOutcome:
        routing = world.routing
        tampered = routing.tampered_policy(NOW)
        result = routing.evaluate(routing.context(
            world.node_a, world.node_b, NOW, policy=tampered,
        ))
        code = result.code if result.decision is None else result.decision.code
        if code == RouteReasonCode.CONFLICTING_INPUT:
            return ObservedOutcome(
                False, code, "tampered policy decision rejected"
            )
        return ObservedOutcome(
            code == RouteReasonCode.CONFLICTING_INPUT, code,
            "tampered policy decision produced %s" % code,
        )

    out.append(_vector(
        "005", "negative",
        "policy decisions are tamper-evident; forged ids fail closed",
        "A decision whose id does not match its content is rejected as "
        "conflicting-input.",
        ExpectedOutcome(False, frozenset({RouteReasonCode.CONFLICTING_INPUT})),
        _rtg005,
        frozenset({"negative:forged-provenance"}),
    ))

    # -- RTG-006: snapshot digest pinning -------------------------------------------
    def _rtg006(world: ConformanceWorld) -> ObservedOutcome:
        routing = world.routing
        result = routing.evaluate(routing.context(
            world.node_a, world.node_b, NOW,
            expected_topology_digest="sha256:" + "0" * 64,
        ))
        code = result.code if result.decision is None else result.decision.code
        if code == RouteReasonCode.INCONSISTENT_SNAPSHOT:
            return ObservedOutcome(
                False, code, "snapshot digest mismatch rejected"
            )
        return ObservedOutcome(
            code == RouteReasonCode.INCONSISTENT_SNAPSHOT, code,
            "digest mismatch produced %s" % code,
        )

    out.append(_vector(
        "006", "negative",
        "expected snapshot digests pin the evaluation inputs",
        "Wrong expected_topology_digest -> inconsistent-snapshot.",
        ExpectedOutcome(
            False, frozenset({RouteReasonCode.INCONSISTENT_SNAPSHOT}
        )),
        _rtg006,
        frozenset({"negative:binding-violation"}),
    ))

    # -- RTG-007: tamper-evident path ids ---------------------------------------------
    def _rtg007(world: ConformanceWorld) -> ObservedOutcome:
        from routing import derive_path_id, path_from_mapping

        routing = world.routing
        decision = routing.decision(world.node_a, world.node_b, NOW)
        if decision.selected is None:
            return ObservedOutcome(
                False, "no-selected-path", "fixture decision has no path"
            )
        path = decision.selected
        mapping = path.to_dict() if hasattr(path, "to_dict") else None
        if mapping is None:
            return ObservedOutcome(
                False, "no-path-mapping", "Path exposes no mapping"
            )
        # The attack: keep the path id, change the hops.
        mapping["hops"] = list(mapping["hops"]) + [mapping["hops"][-1]]
        try:
            forged = path_from_mapping(mapping)
        except Exception as error:
            return ObservedOutcome(
                False, "tampered-path-rejected",
                "%s: %s" % (type(error).__name__, error),
            )
        if forged.path_id != derive_path_id(
            forged.source_node_id, forged.destination_node_id,
            tuple(forged.hops), tuple(forged.nodes),
        ):
            return ObservedOutcome(
                False, "tampered-path-rejected",
                "mutated hops no longer match the path id",
            )
        return ObservedOutcome(
            True, "tampered-path-accepted",
            "path with mutated hops and original id accepted",
        )

    out.append(_vector(
        "007", "negative",
        "path ids are tamper-evident over hops",
        "Mutating hops while keeping the path id fails closed on "
        "reconstruction.",
        ExpectedOutcome(False, frozenset({"tampered-path-rejected",
                                          "RoutingError"})),
        _rtg007,
        frozenset({"negative:forged-provenance"}),
    ))

    # -- RTG-008: forbidden property tokens ----------------------------------------------
    def _rtg008(world: ConformanceWorld) -> ObservedOutcome:
        routing = world.routing
        result = routing.evaluate(routing.context(
            world.node_a, world.node_b, NOW,
            link_metrics={
                make_link_subject(world.node_a, world.node_b):
                    routing.metrics(properties=("vendor-secret-token",))
            },
        ))
        code = result.code if result.decision is None else result.decision.code
        if code in (RouteReasonCode.INVALID_INPUT,
                    RouteReasonCode.UNSUPPORTED_CONSTRAINT):
            return ObservedOutcome(
                False, code, "forbidden property token rejected"
            )
        return ObservedOutcome(
            code in (RouteReasonCode.INVALID_INPUT,
                     RouteReasonCode.UNSUPPORTED_CONSTRAINT), code,
            "forbidden token produced %s" % code,
        )

    out.append(_vector(
        "008", "negative",
        "link metric property tokens are constrained",
        "A vendor-ish property token on LinkMetrics is rejected "
        "(no vendor/access leakage into routing).",
        ExpectedOutcome(False, frozenset({
            RouteReasonCode.INVALID_INPUT, RouteReasonCode.UNSUPPORTED_CONSTRAINT,
        })),
        _rtg008,
        frozenset({"negative:forbidden-imports"}),
    ))

    # -- RTG-009: confidence floor excludes weak evidence ----------------------------------
    def _rtg009(world: ConformanceWorld) -> ObservedOutcome:
        routing = world.routing
        result = routing.evaluate(routing.context(
            world.node_a, world.node_b, NOW,
            link_metrics={
                make_link_subject(world.node_a, world.node_b):
                    routing.metrics(confidence=1_000)
            },
            min_confidence=9_000,
        ))
        code = result.code if result.decision is None else result.decision.code
        if not result.ok or code in (
            RouteReasonCode.NO_FEASIBLE_PATH, RouteReasonCode.EXPIRED_PATH,
        ):
            return ObservedOutcome(
                False, code, "low-confidence link excluded from routing"
            )
        if result.decision is not None and result.decision.selected is None:
            return ObservedOutcome(
                False, result.decision.code,
                "low-confidence link excluded from routing",
            )
        return ObservedOutcome(
            True, "weak-evidence-routed",
            "low-confidence evidence still produced a selected path",
        )

    out.append(_vector(
        "009", "negative",
        "evidence confidence below the floor excludes the candidate",
        "min_confidence_basis_points above the link's confidence yields no "
        "selected path.",
        ExpectedOutcome(False, frozenset({
            RouteReasonCode.NO_FEASIBLE_PATH, RouteReasonCode.EXPIRED_PATH,
        })),
        _rtg009,
        frozenset({"negative:binding-violation"}),
    ))

    # -- RTG-010: no path when link is down -----------------------------------------------
    def _rtg010(world: ConformanceWorld) -> ObservedOutcome:
        routing = world.routing
        graph = routing.graph(world.node_a, world.node_b)
        # Down the single link with a higher-sequence self claim.
        graph.merge(TopologyClaim(
            subject=make_link_subject(world.node_a, world.node_b),
            reporter=world.node_a,
            claim_type=ClaimType.LINK_STATE,
            value="down",
            source_class=SourceClass.SELF_ADVERTISEMENT,
            issued_at=T0, freshness_until=T1, sequence=2,
        ))
        result = routing.evaluate(routing.context(
            world.node_a, world.node_b, NOW, graph=graph,
        ))
        code = result.code if result.decision is None else result.decision.code
        if code in (RouteReasonCode.NO_FEASIBLE_PATH,
                    RouteReasonCode.TOPOLOGY_DISCONNECTED):
            return ObservedOutcome(
                False, code, "downed link yields a clean failure decision"
            )
        return ObservedOutcome(
            code in (RouteReasonCode.NO_FEASIBLE_PATH,
                     RouteReasonCode.TOPOLOGY_DISCONNECTED), code,
            "downed link produced %s" % code,
        )

    out.append(_vector(
        "010", "negative",
        "a downed link produces a clean deterministic failure decision",
        "LINK_STATE=down at higher sequence -> no-feasible-path / "
        "topology-disconnected.",
        ExpectedOutcome(False, frozenset({
            RouteReasonCode.NO_FEASIBLE_PATH,
            RouteReasonCode.TOPOLOGY_DISCONNECTED,
        })),
        _rtg010,
        frozenset({"recovery:version-conflict", "negative:binding-violation"}),
    ))

    # -- RTG-011: invalid node ids ----------------------------------------------------------
    def _rtg011(world: ConformanceWorld) -> ObservedOutcome:
        from routing import RoutingError
        from topology import TopologyError

        routing = world.routing
        try:
            result = routing.evaluate(routing.context(
                "not-a-node-id", world.node_b, NOW,
            ))
        except (RoutingError, TopologyError) as error:
            code = getattr(error, "code", None) or "invalid-input"
            return ObservedOutcome(False, code, str(error))
        code = result.code if result.decision is None else result.decision.code
        if code == RouteReasonCode.INVALID_NODE:
            return ObservedOutcome(
                False, code, "malformed node id rejected"
            )
        return ObservedOutcome(
            code == RouteReasonCode.INVALID_NODE, code,
            "malformed node id produced %s" % code,
        )

    out.append(_vector(
        "011", "negative",
        "malformed node ids fail closed",
        "A non-NodeID-shaped source yields invalid-node (or fails closed "
        "even earlier at link-subject construction).",
        ExpectedOutcome(False, frozenset({
            RouteReasonCode.INVALID_NODE, RouteReasonCode.INVALID_INPUT,
            "link-endpoint",
        })),
        _rtg011,
        frozenset({"negative:malformed-required-fields"}),
    ))

    # -- RTG-012: max_hops bounds ------------------------------------------------------------
    def _rtg012(world: ConformanceWorld) -> ObservedOutcome:
        from routing import RoutingError

        routing = world.routing
        try:
            result = routing.evaluate(routing.context(
                world.node_a, world.node_b, NOW, max_hops=0,
            ))
        except RoutingError as error:
            code = getattr(error, "code", None) or "invalid-input"
            return ObservedOutcome(False, code, str(error))
        code = result.code if result.decision is None else result.decision.code
        if code == RouteReasonCode.INVALID_INPUT:
            return ObservedOutcome(
                False, code, "out-of-bounds max_hops rejected"
            )
        return ObservedOutcome(
            code == RouteReasonCode.INVALID_INPUT, code,
            "max_hops=0 produced %s" % code,
        )

    out.append(_vector(
        "012", "negative",
        "computation bounds are validated",
        "max_hops=0 (below MIN_MAX_HOPS) -> invalid-input.",
        ExpectedOutcome(False, frozenset({RouteReasonCode.INVALID_INPUT})),
        _rtg012,
        frozenset({"negative:malformed-required-fields"}),
    ))

    return tuple(out)


def _two_hop_graph(world: ConformanceWorld) -> Any:
    from topology import TopologyGraph

    graph = TopologyGraph()
    for source, destination in (
        (world.node_a, world.node_b),
        (world.node_b, world.node_c),
    ):
        graph.merge(TopologyClaim(
            subject=make_link_subject(source, destination),
            reporter=source,
            claim_type=ClaimType.LINK_STATE,
            value="up",
            source_class=SourceClass.SELF_ADVERTISEMENT,
            issued_at=T0, freshness_until=T1, sequence=1,
        ))
        graph.merge(TopologyClaim(
            subject=destination,
            reporter=source,
            claim_type=ClaimType.REACHABLE,
            value="true",
            source_class=SourceClass.DIRECT_OBSERVATION,
            issued_at=T0, freshness_until=T1, sequence=1,
        ))
    return graph
