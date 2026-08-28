"""WORK-033 monitoring composition.

"Sessions can be established and monitored" and "logs/metrics are
available" are satisfied by COMPOSITION: the monitoring path reads the
real session store, transport manager, and adapter runtime, and
records explicit telemetry observations through the real WORK-026
store contract.  Monitoring never mutates authority state and never
invents a parallel health model -- every reported value is derived
from the owning authority's own state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Tuple

from telemetry import (
    TelemetryObservation,
    TelemetrySourceClass,
    TelemetrySubjectKind,
    HEALTH_STATE_ORDINALS,
)

from .model import MonitoringReport

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .runtime import AgentRuntime


def _session_views(runtime: "AgentRuntime") -> Tuple[Dict[str, Any], ...]:
    snapshot = runtime.sessions.snapshot()
    views: List[Dict[str, Any]] = []
    for session_data in snapshot.get("sessions", []):
        session_id = str(session_data.get("session_id", ""))
        state = str(session_data.get("state", ""))
        events = runtime.sessions.get_events(session_id)
        last_instant = events[-1].event_instant if events else ""
        views.append(
            {
                "session_id": session_id,
                "state": state,
                "source_node_id": session_data.get("binding", {}).get(
                    "source_node_id", ""
                ),
                "destination_node_id": session_data.get("binding", {}).get(
                    "destination_node_id", ""
                ),
                "event_count": len(events),
                "last_event_instant": last_instant,
            }
        )
    return tuple(views)


def _transport_views(runtime: "AgentRuntime") -> Tuple[Dict[str, Any], ...]:
    views: List[Dict[str, Any]] = []
    for transport_id in runtime.transport_manager.transports():
        state = runtime.transport_manager.get_security_state(transport_id)
        events = runtime.transport_manager.get_events(transport_id)
        views.append(
            {
                "transport_id": transport_id,
                "profile": getattr(state, "profile", ""),
                "generation": getattr(state, "generation", 0),
                "event_count": len(events),
            }
        )
    return tuple(views)


def _adapter_views(runtime: "AgentRuntime") -> Tuple[Dict[str, Any], ...]:
    views: List[Dict[str, Any]] = []
    for adapter_id in runtime.adapters_runtime.adapter_ids():
        report = runtime.adapters_runtime.health(adapter_id, now=runtime._now())
        samples = runtime.adapters_runtime.latest_samples(adapter_id)
        views.append(
            {
                "adapter_id": adapter_id,
                "lifecycle": runtime.adapters_runtime.lifecycle(adapter_id),
                "health": report.state,
                "computed_health": report.computed_state,
                "consecutive_failures": report.consecutive_failures,
                "sample_count": len(samples),
            }
        )
    return tuple(views)


def record_telemetry(runtime: "AgentRuntime", now: str) -> Tuple[str, ...]:
    """Record explicit observations for every registered adapter.

    Two subject families per adapter: ADAPTER_HEALTH (health-state
    ordinal + consecutive-failures, W016 ladder) and LINK (the six
    frozen link metrics, from the adapter runtime's own samples).
    Observations are SELF_ADVERTISED by this node with full confidence
    and a bounded freshness window.
    """
    recorded: List[str] = []
    freshness_until = runtime._instant_after(now, runtime.config.telemetry_freshness_seconds)
    for adapter_id in runtime.adapters_runtime.adapter_ids():
        # The monitoring loop samples first (the sanctioned observe
        # path), then records what the adapter authority reported.
        # Health is recorded even when observation is unavailable
        # (closed or isolated adapter); link samples only when fresh.
        observe_result = runtime.adapters_runtime.observe(adapter_id, now=now)
        report = runtime.adapters_runtime.health(adapter_id, now=now)
        samples = (
            runtime.adapters_runtime.latest_samples(adapter_id)
            if observe_result.ok
            else ()
        )
        observations: List[TelemetryObservation] = [
            TelemetryObservation(
                subject_kind=TelemetrySubjectKind.ADAPTER_HEALTH,
                subject_ref=adapter_id,
                source_node_id=runtime.node_id,
                source_class=TelemetrySourceClass.SELF_ADVERTISED,
                metric="health-state",
                value=HEALTH_STATE_ORDINALS.get(report.state, 3),
                confidence_basis_points=10_000,
                observed_at=now,
                freshness_until=freshness_until,
                sequence=runtime._next_sequence(
                    TelemetrySubjectKind.ADAPTER_HEALTH, adapter_id, "health-state"
                ),
                provenance="agent:adapter-health",
            ),
            TelemetryObservation(
                subject_kind=TelemetrySubjectKind.ADAPTER_HEALTH,
                subject_ref=adapter_id,
                source_node_id=runtime.node_id,
                source_class=TelemetrySourceClass.SELF_ADVERTISED,
                metric="consecutive-failures",
                value=report.consecutive_failures,
                confidence_basis_points=10_000,
                observed_at=now,
                freshness_until=freshness_until,
                sequence=runtime._next_sequence(
                    TelemetrySubjectKind.ADAPTER_HEALTH, adapter_id, "consecutive-failures"
                ),
                provenance="agent:adapter-health",
            ),
        ]
        for sample in samples:
            link_ref = "agent-if-link:%s" % runtime._interface_for_adapter(adapter_id)
            observations.append(
                TelemetryObservation(
                    subject_kind=TelemetrySubjectKind.LINK,
                    subject_ref=link_ref,
                    source_node_id=runtime.node_id,
                    source_class=TelemetrySourceClass.SELF_ADVERTISED,
                    metric=sample.metric,
                    value=sample.value,
                    confidence_basis_points=10_000,
                    observed_at=now,
                    freshness_until=freshness_until,
                    sequence=runtime._next_sequence(
                        TelemetrySubjectKind.LINK, link_ref, sample.metric
                    ),
                    provenance="agent:interface-observation",
                )
            )
        for observation in observations:
            stored = runtime.telemetry.record_observation(observation, now=now)
            recorded.append(stored.observation_id)
    return tuple(recorded)


def collect_monitoring_report(
    runtime: "AgentRuntime", now: str, *, record: bool = True
) -> MonitoringReport:
    """Assemble the composed observability snapshot of one agent node."""
    recorded: Tuple[str, ...] = ()
    if record:
        recorded = record_telemetry(runtime, now)
    return MonitoringReport(
        generated_at=now,
        sessions=_session_views(runtime),
        transports=_transport_views(runtime),
        adapters=_adapter_views(runtime),
        recorded_observation_ids=recorded,
    )
