"""Canonical serialization for scenario specs and results (WORK-031).

Round-trip mappings over the WORK-003 canonicalization machinery so
scenarios and their results can cross process boundaries byte-identically
(the cross-process determinism proof serializes a spec, runs it in a
subprocess, and compares trace digests).
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from .model import (
    AuthorityMutation,
    FlowObservation,
    ObservationRecord,
    ScenarioPolicyRule,
    ScenarioResult,
    ScenarioSpec,
    ScheduledEvent,
    SimulatedLinkSpec,
    SimulatedNodeSpec,
    SimulatorError,
    SimulatorReasonCode,
)
from .runner import trace_digest


def spec_to_mapping(spec: ScenarioSpec) -> Dict[str, Any]:
    """The canonical wire form of a scenario spec."""
    return {
        "scenario_id": spec.scenario_id,
        "seed": spec.seed,
        "start_instant": spec.start_instant,
        "tick_seconds": spec.tick_seconds,
        "horizon_ticks": spec.horizon_ticks,
        "nodes": [
            {
                "node_id": node.node_id,
                "capacity_millijoules": node.capacity_millijoules,
                "initial_level_millijoules": node.initial_level_millijoules,
                "load_milliwatts": node.load_milliwatts,
                "generation_milliwatts": node.generation_milliwatts,
                "power_source": node.power_source,
                "conserve_threshold_bp": node.conserve_threshold_bp,
                "critical_threshold_bp": node.critical_threshold_bp,
                "survival_threshold_bp": node.survival_threshold_bp,
                "survival_reserve_bp": node.survival_reserve_bp,
                "offline_grace_seconds": node.offline_grace_seconds,
            }
            for node in spec.nodes
        ],
        "links": [
            {
                "node_a": link.node_a,
                "node_b": link.node_b,
                "latency_ms": link.latency_ms,
                "loss_basis_points": link.loss_basis_points,
                "capacity_bps": link.capacity_bps,
                "energy_cost_millijoules": link.energy_cost_millijoules,
                "confidence_basis_points": link.confidence_basis_points,
            }
            for link in spec.links
        ],
        "probes": [[source, destination] for source, destination in spec.probes],
        "policy_rules": [
            {
                "rule_id": rule.rule_id,
                "effect": rule.effect,
                "operation": rule.operation,
                "subjects": list(rule.subjects),
                "priority": rule.priority,
                "specificity": rule.specificity,
            }
            for rule in spec.policy_rules
        ],
        "events": [event.content_dict() for event in spec.events],
    }


def spec_from_mapping(mapping: Dict[str, Any]) -> ScenarioSpec:
    """Reconstruct a scenario spec from its canonical wire form."""
    try:
        nodes = tuple(
            SimulatedNodeSpec(
                node_id=node["node_id"],
                capacity_millijoules=node.get("capacity_millijoules", 10_000_000),
                initial_level_millijoules=node.get("initial_level_millijoules", 3_600_000),
                load_milliwatts=node.get("load_milliwatts", 100),
                generation_milliwatts=node.get("generation_milliwatts", 0),
                power_source=node.get("power_source", "solar-hybrid"),
                conserve_threshold_bp=node.get("conserve_threshold_bp", 6000),
                critical_threshold_bp=node.get("critical_threshold_bp", 3000),
                survival_threshold_bp=node.get("survival_threshold_bp", 1500),
                survival_reserve_bp=node.get("survival_reserve_bp", 1000),
                offline_grace_seconds=node.get("offline_grace_seconds", 3600),
            )
            for node in mapping["nodes"]
        )
        links = tuple(
            SimulatedLinkSpec(
                node_a=link["node_a"],
                node_b=link["node_b"],
                latency_ms=link.get("latency_ms", 10),
                loss_basis_points=link.get("loss_basis_points", 0),
                capacity_bps=link.get("capacity_bps", 1_000_000),
                energy_cost_millijoules=link.get("energy_cost_millijoules", 100),
                confidence_basis_points=link.get("confidence_basis_points", 10_000),
            )
            for link in mapping.get("links", ())
        )
        rules = tuple(
            ScenarioPolicyRule(
                rule_id=rule["rule_id"],
                effect=rule.get("effect", "allow"),
                operation=rule.get("operation", "session.create"),
                subjects=tuple(rule.get("subjects", ())),
                priority=rule.get("priority", 0),
                specificity=rule.get("specificity", 0),
            )
            for rule in mapping.get("policy_rules", ())
        )
        events = tuple(
            ScheduledEvent(
                at_tick=event["at_tick"],
                sequence=event["sequence"],
                kind=event["kind"],
                payload=dict(event.get("payload", {})),
            )
            for event in mapping.get("events", ())
        )
        return ScenarioSpec(
            scenario_id=mapping["scenario_id"],
            seed=mapping["seed"],
            start_instant=mapping["start_instant"],
            tick_seconds=mapping["tick_seconds"],
            horizon_ticks=mapping["horizon_ticks"],
            nodes=nodes,
            links=links,
            probes=tuple(
                (pair[0], pair[1]) for pair in mapping.get("probes", ())
            ),
            policy_rules=rules,
            events=events,
        )
    except (KeyError, TypeError) as error:
        raise SimulatorError(
            SimulatorReasonCode.INVALID_INPUT,
            "spec mapping is malformed: %s" % error,
        ) from error


def result_from_mapping(mapping: Dict[str, Any]) -> ScenarioResult:
    """Reconstruct a scenario result from its canonical wire form."""
    records = []
    for record in mapping.get("records", ()):
        records.append(
            ObservationRecord(
                tick=record["tick"],
                instant=record["instant"],
                event_id=record["event_id"],
                kind=record["kind"],
                verdict=record["verdict"],
                mutations=tuple(
                    AuthorityMutation(
                        authority=mutation["authority"],
                        operation=mutation["operation"],
                        outcome=mutation["outcome"],
                        detail=mutation.get("detail", ""),
                    )
                    for mutation in record.get("mutations", ())
                ),
                before_digests=tuple(
                    (key, value)
                    for key, value in record.get("before", {}).items()
                ),
                after_digests=tuple(
                    (key, value)
                    for key, value in record.get("after", {}).items()
                ),
                flows=tuple(
                    FlowObservation(
                        flow=flow["flow"],
                        ok=bool(flow["ok"]),
                        code=flow["code"],
                        ref=flow.get("ref", ""),
                        detail=flow.get("detail", ""),
                    )
                    for flow in record.get("flows", ())
                ),
                detail=record.get("detail", ""),
            )
        )
    trace = tuple(records)
    return ScenarioResult(
        ok=bool(mapping["ok"]),
        scenario_id=mapping["scenario_id"],
        seed=mapping["seed"],
        trace=trace,
        trace_digest=trace_digest(trace),
        final_digests=tuple(
            (key, value)
            for key, value in mapping.get("final_digests", {}).items()
        ),
        applied_events=mapping.get("applied_events", 0),
        rejected_events=mapping.get("rejected_events", 0),
        failed_events=mapping.get("failed_events", 0),
        pending_cleanups=mapping.get("pending_cleanups", 0),
        seam_purpose=mapping.get("seam_purpose", ""),
        seam_verdict=mapping.get("seam_verdict", ""),
        seam_detail=mapping.get("seam_detail", ""),
    )


__all__ = [
    "spec_to_mapping",
    "spec_from_mapping",
    "result_from_mapping",
    "trace_digest",
]
