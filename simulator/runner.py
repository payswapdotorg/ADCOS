"""The deterministic scenario runner (WORK-031).

:class:`Simulator` is the orchestration core: it applies the scenario's
scheduled events in explicit ``(at_tick, sequence)`` order against a
composition of REAL accepted authorities, recording for every event a
trace :class:`~simulator.model.ObservationRecord` with pre/post
authority digests, every owner-contract mutation, and every observed
flow outcome.

The composition boundary (frozen WORK-031 handoff):

- topology truth          -> real WORK-007 ``TopologyGraph``
- resource truth          -> real WORK-008 ``ResourceStore``
- policy decisions        -> real WORK-010 ``PolicyEngine`` over a real
                             ``PolicyStore`` (no shadow policy engine)
- path selection          -> real WORK-011 ``RoutingEngine``
- session lifecycle       -> real WORK-012 ``SessionStore``
- multipath plans         -> real WORK-013 ``MultipathStore``
- mobility transactions   -> real WORK-014 ``MobilityStore``
- telemetry records       -> real WORK-026 ``TelemetryStore``
- energy/resilience       -> real WORK-027 ``PowerSimulator`` /
                             ``EnergyGovernor`` / ``NodeRejoinLedger``

The runner NEVER mutates an authority except through that authority's
own public contract, and every such mutation is recorded in the trace.
By default all authority instances are ISOLATED (created here, owned
here); a caller-provided component is reachable ONLY through an
explicit :class:`~simulator.seam.AuthorityTestSeam`.

Universal event failure boundary: an unexpected exception during any
event application is contained as exactly one ``failed`` observation
record carrying the exception class and the pre/post digests (partial
state visibility is explicit); the scenario continues.  Semantic
fail-closed rejections (:class:`SimulatorError`) are ``rejected``
records that advance no simulator state.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Mapping, Optional, Tuple

from energy.errors import EnergyError
from energy.governor import EnergyGovernor
from energy.resilience import NodeRejoinLedger
from mobility.store import MobilityStore
from policy.evaluation import PolicyEngine
from policy.model import (
    DecisionCode,
    Effect,
    Operation,
    PolicyContext,
    PolicyDomain,
    PolicyError,
    PolicyRule,
    PolicySet,
)
from policy.store import PolicyStore
from protocol.canonicalization import canonical_json_bytes
from protocol.temporal import parse_instant
from resources.model import (
    AvailabilityMode,
    EnergyState,
    MeasurementSource,
    Quantity,
    Resource,
    ResourceKind,
    ResourceOffer,
    ResourceStore,
    make_resource_id,
)
from routing.engine import RoutingEngine
from routing.model import LinkMetrics, RoutingContext, RoutingError
from sessions.store import SessionStore
from telemetry.errors import TelemetryError
from telemetry.model import (
    TelemetryObservation,
    TelemetrySourceClass,
    TelemetrySubjectKind,
)
from telemetry.store import TelemetryStore
from topology.model import LinkState, MergeOutcome, TopologyGraph

from .environment import SimulatedEnvironment
from .model import (
    AuthorityMutation,
    EventKind,
    EventVerdict,
    FlowObservation,
    MutationOutcome,
    ObservationRecord,
    ScenarioPolicyRule,
    ScenarioResult,
    ScenarioSpec,
    ScheduledEvent,
    SimulatorError,
    SimulatorReasonCode,
)
from .random import DeterministicStream
from .seam import AuthorityTestSeam, seam_verdict
from .time import ScenarioClock

#: The documented conservative cross-set policy aggregation (identical
#: semantics to the accepted WORK-030 management plane): an explicit
#: blocking code in ANY live set denies; a SILENT set (DEFAULT_DENY /
#: no matching rule) does not veto another set's explicit ALLOW.
_BLOCKING_POLICY_CODES = frozenset(
    {
        DecisionCode.DENY,
        DecisionCode.FAIL_CLOSED,
        DecisionCode.CONFLICT,
        DecisionCode.INVALID_POLICY,
        DecisionCode.INVALID_SUBJECT,
        DecisionCode.UNSUPPORTED_PREDICATE,
    }
)

#: The energy-resource scope label every simulated node registers under.
_ENERGY_SCOPE = "simulator:node-energy"

#: The avoid-variant latency penalty used to explore alternate paths
#: (scenario exploration INPUT handed to the routing authority as
#: ordinary metric facts; routing still decides).
_AVOID_LATENCY_MS = 1_000_000_000


def trace_digest(trace: Tuple[ObservationRecord, ...]) -> str:
    """The reproducibility fingerprint over the ordered trace."""
    material = canonical_json_bytes([record.content_dict() for record in trace])
    return "sha256:" + hashlib.sha256(material).hexdigest()


class Simulator:
    """The deterministic scenario runner over real authorities."""

    def __init__(
        self,
        spec: ScenarioSpec,
        *,
        seam: Optional[AuthorityTestSeam] = None,
    ) -> None:
        self._spec = spec
        self._clock = ScenarioClock(spec.start_instant, spec.tick_seconds)
        self._stream = DeterministicStream(spec.seed, label="scenario")
        self._environment = SimulatedEnvironment(spec, self._clock, self._stream)
        self._horizon_instant = self._clock.horizon_instant(spec.horizon_ticks)

        # -- isolated REAL authorities (no production state reachable) --
        self._topology = TopologyGraph()
        self._resources = ResourceStore()
        self._policy_store = PolicyStore()
        self._engine = PolicyEngine()
        self._routing = RoutingEngine()
        self._sessions = SessionStore()
        self._multipath = self._make_multipath(self._sessions)
        self._mobility = MobilityStore(self._sessions, multipath_store=self._multipath)
        self._telemetry = TelemetryStore()
        self._ledger = NodeRejoinLedger()
        self._governor = EnergyGovernor()

        # -- the explicit test seam replaces exactly one component --
        self._seam = seam
        if seam is not None:
            self._install_seam(seam)

        # -- runner bookkeeping (simulator state, never authority state) --
        self._trace: List[ObservationRecord] = []
        self._sessions_by_label: Dict[str, Tuple[str, Any, Any, str, str]] = {}
        self._measurement_sequence: Dict[str, int] = {}
        self._telemetry_sequence: Dict[Tuple[str, str, str], int] = {}
        self._posture_sequence: Dict[str, int] = {}
        self._energy_resource_ids: Dict[str, str] = {}
        self._applied = 0
        self._rejected = 0
        self._failed = 0
        self._pending_cleanups = 0
        if spec.nodes:
            self._issuer = spec.nodes[0].node_id

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    def _make_multipath(self, sessions: SessionStore) -> Any:
        from multipath.store import MultipathStore

        return MultipathStore(sessions)

    def _install_seam(self, seam: AuthorityTestSeam) -> None:
        from energy.resilience import NodeRejoinLedger as _Ledger
        from mobility.store import MobilityStore as _Mobility
        from policy.store import PolicyStore as _Policy
        from telemetry.store import TelemetryStore as _Telemetry

        component = seam.component
        if isinstance(component, _Ledger):
            self._ledger = component
        elif isinstance(component, SessionStore):
            self._sessions = component
            self._multipath = self._make_multipath(component)
            self._mobility = MobilityStore(
                component, multipath_store=self._multipath
            )
        elif isinstance(component, _Telemetry):
            self._telemetry = component
        elif isinstance(component, _Mobility):
            self._mobility = component
        elif isinstance(component, _Policy):
            self._policy_store = component
        else:  # pragma: no cover - authority_digest already fail-closed
            raise SimulatorError(
                SimulatorReasonCode.UNSUPPORTED_SEAM_COMPONENT,
                "unsupported seam component %s" % type(component).__name__,
            )

    # ------------------------------------------------------------------
    # The scenario run
    # ------------------------------------------------------------------

    def run(self) -> ScenarioResult:
        """Run the scenario deterministically and return the trace."""
        start = self._clock.instant_at(0)
        if self._seam is not None:
            self._seam.open()
        self._bootstrap(start)
        ordered = sorted(self._spec.events, key=lambda event: (event.at_tick, event.sequence))
        for tick in range(0, self._spec.horizon_ticks + 1):
            now = self._clock.instant_at(tick)
            if tick > 0:
                self._environment.advance_power(self._spec.tick_seconds)
            for event in ordered:
                if event.at_tick != tick:
                    continue
                self._trace.append(self._apply_event(event, tick, now))
        seam_purpose = ""
        seam_outcome = ""
        seam_detail = ""
        if self._seam is not None:
            close_digest = self._seam.close()
            seam_purpose = self._seam.purpose
            seam_outcome = seam_verdict(self._seam.open_digest, close_digest)
            if seam_outcome == "validated" and self._pending_cleanups > 0:
                seam_outcome = "degraded"
                seam_detail = (
                    "%d cleanup(s) left pending/degraded -- unresolved "
                    "simulated resource cleanup is explicit" % self._pending_cleanups
                )
            else:
                seam_detail = "digest %s -> %s" % (
                    self._seam.open_digest[:18],
                    close_digest[:18],
                )
        final = self._digest_state(self._clock.instant_at(self._spec.horizon_ticks))
        ok = self._failed == 0 and self._pending_cleanups == 0
        return ScenarioResult(
            ok=ok,
            scenario_id=self._spec.scenario_id,
            seed=self._spec.seed,
            trace=tuple(self._trace),
            trace_digest=trace_digest(tuple(self._trace)),
            final_digests=final,
            applied_events=self._applied,
            rejected_events=self._rejected,
            failed_events=self._failed,
            pending_cleanups=self._pending_cleanups,
            seam_purpose=seam_purpose,
            seam_verdict=seam_outcome,
            seam_detail=seam_detail,
        )

    # ------------------------------------------------------------------
    # Bootstrap: register the scenario world into the real authorities
    # ------------------------------------------------------------------

    def _bootstrap(self, start: str) -> None:
        mutations: List[AuthorityMutation] = []
        for node in self._spec.nodes:
            resource_id = make_resource_id(node.node_id, ResourceKind.ENERGY, _ENERGY_SCOPE)
            self._energy_resource_ids[node.node_id] = resource_id
            self._measurement_sequence[resource_id] = 1
            try:
                self._resources.register_resource(
                    Resource(
                        resource_id=resource_id,
                        owner_node_id=node.node_id,
                        kind=ResourceKind.ENERGY,
                        availability=AvailabilityMode.CONTINUOUS,
                        scope=_ENERGY_SCOPE,
                        created_at=start,
                    )
                )
                mutations.append(
                    AuthorityMutation(
                        authority="resources",
                        operation="register-resource",
                        outcome=MutationOutcome.COMMITTED,
                        detail=resource_id,
                    )
                )
            except ValueError as error:
                mutations.append(
                    AuthorityMutation(
                        authority="resources",
                        operation="register-resource",
                        outcome=MutationOutcome.REJECTED,
                        detail=str(error),
                    )
                )
            try:
                self._resources.create_offer(
                    ResourceOffer(
                        resource_id=resource_id,
                        provider_node_id=node.node_id,
                        quantity=Quantity(
                            value=node.capacity_millijoules, unit="millijoules"
                        ),
                        valid_from=start,
                        expires_at=self._horizon_instant,
                        provenance="simulator:environment",
                    )
                )
                mutations.append(
                    AuthorityMutation(
                        authority="resources",
                        operation="create-offer",
                        outcome=MutationOutcome.COMMITTED,
                        detail=resource_id,
                    )
                )
            except ValueError as error:
                mutations.append(
                    AuthorityMutation(
                        authority="resources",
                        operation="create-offer",
                        outcome=MutationOutcome.REJECTED,
                        detail=str(error),
                    )
                )
            self._ledger.register_profile(self._environment.survival_profile(node.node_id))
        mutations.append(
            AuthorityMutation(
                authority="energy-resilience",
                operation="register-profile",
                outcome=MutationOutcome.COMMITTED,
                detail="%d survival profiles" % len(self._spec.nodes),
            )
        )
        for claim in self._environment.node_claims(start, self._horizon_instant) + \
                self._environment.all_link_claims(start, self._horizon_instant):
            outcome = self._topology.merge(claim)
            mutations.append(
                AuthorityMutation(
                    authority="topology",
                    operation="merge-claim",
                    outcome=(
                        MutationOutcome.COMMITTED
                        if outcome.accepted
                        else MutationOutcome.REJECTED
                    ),
                    detail="%s (%s)" % (outcome.code, claim.subject[:48]),
                )
            )
        if self._spec.policy_rules:
            policy_set = self._policy_set(
                "scenario-policy", 1, self._spec.policy_rules
            )
            try:
                self._policy_store.publish(policy_set)
                mutations.append(
                    AuthorityMutation(
                        authority="policy",
                        operation="publish",
                        outcome=MutationOutcome.COMMITTED,
                        detail="scenario-policy@1 (%d rules)"
                        % len(self._spec.policy_rules),
                    )
                )
            except PolicyError as error:
                mutations.append(
                    AuthorityMutation(
                        authority="policy",
                        operation="publish",
                        outcome=MutationOutcome.REJECTED,
                        detail=str(error),
                    )
                )
        record = ObservationRecord(
            tick=0,
            instant=start,
            event_id="simulator:bootstrap:" + self._spec.scenario_id,
            kind="bootstrap",
            verdict=EventVerdict.APPLIED,
            mutations=tuple(mutations),
            before_digests=(),
            after_digests=self._digest_state(start),
            flows=(),
            detail="scenario world registered into isolated real authorities",
        )
        self._trace.append(record)
        self._applied += 1

    # ------------------------------------------------------------------
    # Event application boundary
    # ------------------------------------------------------------------

    def _apply_event(self, event: ScheduledEvent, tick: int, now: str) -> ObservationRecord:
        event_id = event.event_id()
        before = self._digest_state(now)
        problems = _validate_payload(event)
        if problems:
            self._rejected += 1
            return ObservationRecord(
                tick=tick,
                instant=now,
                event_id=event_id,
                kind=event.kind,
                verdict=EventVerdict.REJECTED,
                mutations=(),
                before_digests=before,
                after_digests=before,
                flows=(),
                detail=problems,
            )
        try:
            mutations, flows, detail = self._dispatch(event, now)
        except SimulatorError as error:
            # Semantic fail-closed rejection: nothing was mutated.
            self._rejected += 1
            return ObservationRecord(
                tick=tick,
                instant=now,
                event_id=event_id,
                kind=event.kind,
                verdict=EventVerdict.REJECTED,
                mutations=(),
                before_digests=before,
                after_digests=self._digest_state(now),
                flows=(),
                detail="%s: %s" % (error.code, error.detail),
            )
        except Exception as error:  # noqa: BLE001 -- universal boundary
            # Unexpected failure: exactly one failed record; the
            # pre/post digests make any partial state explicit.
            self._failed += 1
            return ObservationRecord(
                tick=tick,
                instant=now,
                event_id=event_id,
                kind=event.kind,
                verdict=EventVerdict.FAILED,
                mutations=(),
                before_digests=before,
                after_digests=self._digest_state(now),
                flows=(),
                detail="unexpected failure: %r" % (error,),
            )
        self._applied += 1
        return ObservationRecord(
            tick=tick,
            instant=now,
            event_id=event_id,
            kind=event.kind,
            verdict=EventVerdict.APPLIED,
            mutations=tuple(mutations),
            before_digests=before,
            after_digests=self._digest_state(now),
            flows=tuple(flows),
            detail=detail,
        )

    def _dispatch(
        self, event: ScheduledEvent, now: str
    ) -> Tuple[List[AuthorityMutation], List[FlowObservation], str]:
        kind = event.kind
        payload = event.payload
        if kind == EventKind.NODE_DOWN:
            return self._apply_node_down(payload, now)
        if kind == EventKind.NODE_UP:
            return self._apply_node_up(payload, now)
        if kind == EventKind.LINK_DOWN:
            return self._apply_link_change(payload, now, "down")
        if kind == EventKind.LINK_UP:
            return self._apply_link_change(payload, now, "up")
        if kind == EventKind.LINK_DEGRADE:
            return self._apply_link_change(payload, now, "degraded")
        if kind == EventKind.PARTITION_START:
            return self._apply_partition(payload, now, cut=True)
        if kind == EventKind.PARTITION_END:
            return self._apply_partition(payload, now, cut=False)
        if kind == EventKind.RESOURCE_EXHAUST:
            return self._apply_resource_exhaust(payload, now)
        if kind == EventKind.POLICY_AMEND:
            return self._apply_policy_amend(payload, now)
        if kind == EventKind.POLICY_WITHDRAW:
            return self._apply_policy_withdraw(payload, now)
        if kind == EventKind.TELEMETRY_EMIT:
            return self._apply_telemetry_emit(payload, now)
        if kind == EventKind.SESSION_REQUEST:
            return self._apply_session_request(payload, now)
        if kind == EventKind.PATH_ADD:
            return self._apply_path_add(payload, now)
        if kind == EventKind.PATH_FAIL:
            return self._apply_path_fail(payload, now)
        if kind == EventKind.SESSION_FAIL:
            return self._apply_session_fail(payload, now)
        if kind == EventKind.MOBILITY_HANDOVER:
            return self._apply_mobility_handover(payload, now)
        if kind == EventKind.CLEANUP:
            return self._apply_cleanup(payload, now)
        if kind == EventKind.OBSERVE:
            return self._apply_observe(payload, now)
        raise SimulatorError(
            SimulatorReasonCode.UNKNOWN_EVENT,
            "unhandled event kind %r" % kind,
        )

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _apply_node_down(
        self, payload: Mapping[str, Any], now: str
    ) -> Tuple[List[AuthorityMutation], List[FlowObservation], str]:
        node = payload["node"]
        if node not in self._environment.node_ids:
            raise SimulatorError(
                SimulatorReasonCode.UNKNOWN_NODE, "node %r is not in the scenario" % node
            )
        self._environment.set_online(node, False)
        return (
            [],
            [],
            "node %s offline at %s (simulator state; restart/rejoin is a "
            "node-up event through the WORK-027 ledger)" % (node[:32], now),
        )

    def _apply_node_up(
        self, payload: Mapping[str, Any], now: str
    ) -> Tuple[List[AuthorityMutation], List[FlowObservation], str]:
        node = payload["node"]
        if node not in self._environment.node_ids:
            raise SimulatorError(
                SimulatorReasonCode.UNKNOWN_NODE, "node %r is not in the scenario" % node
            )
        self._environment.set_online(node, True)
        simulator = self._environment.power_simulator(node)
        state = simulator.energy_state()
        level = int(payload.get("level_millijoules", state.energy_level.value))
        capacity = int(payload.get("capacity_millijoules", state.energy_capacity.value))
        draw = int(payload.get("power_draw_milliwatts", state.power_draw.value))
        mutations: List[AuthorityMutation] = []
        try:
            record = self._ledger.rejoin(
                node,
                claimed_level_millijoules=level,
                claimed_capacity_millijoules=capacity,
                claimed_power_draw_milliwatts=draw,
                rejoin_instant=now,
            )
            mutations.append(
                AuthorityMutation(
                    authority="energy-resilience",
                    operation="rejoin",
                    outcome=MutationOutcome.COMMITTED,
                    detail="epoch %d (%s)" % (record.epoch, record.rejoin_id[:24]),
                )
            )
            flows = [
                FlowObservation(
                    flow="energy",
                    ok=True,
                    code="rejoined",
                    ref=record.rejoin_id,
                    detail="epoch %d" % record.epoch,
                )
            ]
        except EnergyError as error:
            mutations.append(
                AuthorityMutation(
                    authority="energy-resilience",
                    operation="rejoin",
                    outcome=MutationOutcome.REJECTED,
                    detail=str(error),
                )
            )
            flows = [
                FlowObservation(
                    flow="energy", ok=False, code="rejoin-rejected", detail=str(error)
                )
            ]
        return mutations, flows, "node %s restarted; rejoin through the real WORK-027 ledger" % node[:32]

    def _apply_link_change(
        self, payload: Mapping[str, Any], now: str, status: str
    ) -> Tuple[List[AuthorityMutation], List[FlowObservation], str]:
        subject = self._environment.link_subject(payload["node_a"], payload["node_b"])
        if status == LinkState.DEGRADED:
            # Degradation is a METRIC-quality dimension (LOCK-009): the
            # topology link-state claim stays ``up`` (routing only builds
            # candidates over UP links) and the deterministic metric
            # penalty carries the degradation. No topology mutation.
            self._environment.degrade_link(subject)
            flows = self._observe_probes(now)
            return (
                [],
                flows,
                "link %s degraded (metric facts penalized; topology state "
                "unchanged); probes observed" % subject[:48],
            )
        self._environment.set_link_status(subject, status)
        mutations = self._merge_link_claim(subject, now)
        flows = self._observe_probes(now)
        return (
            mutations,
            flows,
            "link %s -> %s; topology claim ingested; probes observed" % (subject[:48], status),
        )

    def _apply_partition(
        self, payload: Mapping[str, Any], now: str, cut: bool
    ) -> Tuple[List[AuthorityMutation], List[FlowObservation], str]:
        subjects = tuple(
            self._environment.link_subject(pair[0], pair[1]) for pair in payload["cuts"]
        )
        if cut:
            self._environment.cut_links(subjects)
        else:
            self._environment.restore_links(subjects)
        mutations: List[AuthorityMutation] = []
        for subject in subjects:
            mutations.extend(self._merge_link_claim(subject, now))
        flows = self._observe_probes(now)
        return (
            mutations,
            flows,
            "partition %s over %d link(s); claims ingested; probes observed"
            % ("start" if cut else "end", len(subjects)),
        )

    def _apply_resource_exhaust(
        self, payload: Mapping[str, Any], now: str
    ) -> Tuple[List[AuthorityMutation], List[FlowObservation], str]:
        from resources.model import ResourceMeasurement

        node = payload["node"]
        if node not in self._environment.node_ids:
            raise SimulatorError(
                SimulatorReasonCode.UNKNOWN_NODE, "node %r is not in the scenario" % node
            )
        resource_id = self._energy_resource_ids[node]
        state = self._environment.power_simulator(node).energy_state()
        capacity = state.energy_capacity.value
        remaining = max(0, capacity * payload["fraction_bp"] // 10_000)
        sequence = self._measurement_sequence[resource_id]
        self._measurement_sequence[resource_id] = sequence + 1
        measurement = ResourceMeasurement(
            resource_id=resource_id,
            source_node_id=node,
            observed_at=now,
            freshness_until=self._horizon_instant,
            value=EnergyState(
                energy_level=Quantity(value=remaining, unit="millijoules"),
                energy_capacity=Quantity(value=capacity, unit="millijoules"),
                power_draw=Quantity(
                    value=state.power_draw.value, unit="milliwatts"
                ),
            ),
            method_ref="simulator:energy-remaining",
            source_class=MeasurementSource.SELF_OBSERVATION,
            sequence=sequence,
            provenance="simulator:environment",
        )
        outcome = self._resources.record_measurement(measurement)
        mutation = AuthorityMutation(
            authority="resources",
            operation="record-measurement",
            outcome=(
                MutationOutcome.COMMITTED
                if outcome.accepted
                else MutationOutcome.REJECTED
            ),
            detail="%s (%s)" % (outcome.code, resource_id[:48]),
        )
        flows = [
            FlowObservation(
                flow="resource",
                ok=outcome.accepted,
                code=outcome.code,
                ref=measurement.measurement_id,
                detail="remaining %d millijoules (%d bp of capacity)"
                % (remaining, payload["fraction_bp"]),
            )
        ]
        return (
            [mutation],
            flows,
            "energy exhaustion measurement recorded through the real WORK-008 store",
        )

    def _apply_policy_amend(
        self, payload: Mapping[str, Any], now: str
    ) -> Tuple[List[AuthorityMutation], List[FlowObservation], str]:
        try:
            rules = tuple(
                ScenarioPolicyRule(
                    rule_id=rule["rule_id"],
                    effect=rule.get("effect", "allow"),
                    operation=rule.get("operation", "session.create"),
                    subjects=tuple(rule.get("subjects", ())),
                    priority=rule.get("priority", 0),
                    specificity=rule.get("specificity", 0),
                )
                for rule in payload["rules"]
            )
            policy_set = self._policy_set(
                payload["set_id"], payload["version"], rules
            )
            self._policy_store.publish(policy_set)
            mutation = AuthorityMutation(
                authority="policy",
                operation="publish",
                outcome=MutationOutcome.COMMITTED,
                detail="%s@%d (%d rules)"
                % (payload["set_id"], payload["version"], len(rules)),
            )
        except PolicyError as error:
            # The policy owner rejects malformed material at rule
            # construction or publication -- an observed authority
            # rejection, not an unexpected simulator failure.
            mutation = AuthorityMutation(
                authority="policy",
                operation="publish",
                outcome=MutationOutcome.REJECTED,
                detail=str(error),
            )
        return ([mutation], [], "policy material published through the real WORK-010 store at %s" % now)

    def _apply_policy_withdraw(
        self, payload: Mapping[str, Any], now: str
    ) -> Tuple[List[AuthorityMutation], List[FlowObservation], str]:
        try:
            self._policy_store.withdraw(payload["set_id"], payload["version"])
            mutation = AuthorityMutation(
                authority="policy",
                operation="withdraw",
                outcome=MutationOutcome.COMMITTED,
                detail="%s@%d" % (payload["set_id"], payload["version"]),
            )
        except PolicyError as error:
            mutation = AuthorityMutation(
                authority="policy",
                operation="withdraw",
                outcome=MutationOutcome.REJECTED,
                detail=str(error),
            )
        return ([mutation], [], "policy set withdrawn at %s" % now)

    def _apply_telemetry_emit(
        self, payload: Mapping[str, Any], now: str
    ) -> Tuple[List[AuthorityMutation], List[FlowObservation], str]:
        node = payload["node"]
        if node not in self._environment.node_ids:
            raise SimulatorError(
                SimulatorReasonCode.UNKNOWN_NODE, "node %r is not in the scenario" % node
            )
        if payload["subject_kind"] not in TelemetrySubjectKind.values():
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "subject_kind %r must be one of %s"
                % (payload["subject_kind"], TelemetrySubjectKind.values()),
            )
        key = (payload["subject_ref"], node, payload["metric"])
        sequence = self._telemetry_sequence.get(key, 1)
        self._telemetry_sequence[key] = sequence + 1
        confidence = 9_000 + self._stream.uint(1_000)
        observation = TelemetryObservation(
            subject_kind=payload["subject_kind"],
            subject_ref=payload["subject_ref"],
            source_node_id=node,
            source_class=TelemetrySourceClass.SELF_ADVERTISED,
            metric=payload["metric"],
            value=payload["value"],
            confidence_basis_points=confidence,
            observed_at=now,
            freshness_until=self._horizon_instant,
            sequence=sequence,
            provenance="simulator:environment",
        )
        try:
            recorded = self._telemetry.record_observation(observation, now=now)
            mutation = AuthorityMutation(
                authority="telemetry",
                operation="record-observation",
                outcome=MutationOutcome.COMMITTED,
                detail=recorded.observation_id,
            )
            flows = [
                FlowObservation(
                    flow="telemetry",
                    ok=True,
                    code="recorded",
                    ref=recorded.observation_id,
                )
            ]
        except TelemetryError as error:
            mutation = AuthorityMutation(
                authority="telemetry",
                operation="record-observation",
                outcome=MutationOutcome.REJECTED,
                detail=str(error),
            )
            flows = [
                FlowObservation(
                    flow="telemetry", ok=False, code="rejected", detail=str(error)
                )
            ]
        return (
            [mutation],
            flows,
            "telemetry observation recorded through the real WORK-026 store",
        )

    def _apply_session_request(
        self, payload: Mapping[str, Any], now: str
    ) -> Tuple[List[AuthorityMutation], List[FlowObservation], str]:
        label = payload["label"]
        source = payload["source"]
        destination = payload["destination"]
        for node in (source, destination):
            if node not in self._environment.node_ids:
                raise SimulatorError(
                    SimulatorReasonCode.UNKNOWN_NODE,
                    "node %r is not in the scenario" % node,
                )
        if label in self._sessions_by_label:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "session label %r already used in this scenario" % label,
            )
        mutations: List[AuthorityMutation] = []
        flows: List[FlowObservation] = []
        authorized, decision, policy_flows = self._policy_gate(source, now)
        flows.extend(policy_flows)
        if not authorized or decision is None:
            return (
                mutations,
                flows,
                "session request %r denied by policy; no session created" % label,
            )
        route_flows, route_decision = self._evaluate_route(
            source, destination, decision, now, avoid=()
        )
        flows.extend(route_flows)
        if route_decision is None:
            return (
                mutations,
                flows,
                "session request %r produced no accepted route; no session created"
                % label,
            )
        result = self._sessions.create(
            route_decision,
            decision,
            source_node_id=source,
            destination_node_id=destination,
            creation_instant=now,
            actor_reference="simulator:scenario",
        )
        mutations.append(
            AuthorityMutation(
                authority="sessions",
                operation="create",
                outcome=(
                    MutationOutcome.COMMITTED if result.ok else MutationOutcome.REJECTED
                ),
                detail="%s (%s)" % (result.code, result.detail[:64]),
            )
        )
        flows.append(
            FlowObservation(
                flow="session",
                ok=result.ok,
                code=result.code,
                ref=(result.session.session_id if result.session else ""),
            )
        )
        if result.ok and result.session is not None:
            # Drive the genuine WORK-012 lifecycle to ESTABLISHED so
            # the session is operational (plan operations, handover,
            # and terminate all require an established session).
            session_id = result.session.session_id
            for new_state in ("AUTHORIZED", "ESTABLISHED"):
                transition = self._sessions.transition(
                    session_id,
                    new_state,
                    event_instant=now,
                    actor_reference="simulator:scenario",
                    reason_code="simulator:lifecycle",
                )
                mutations.append(
                    AuthorityMutation(
                        authority="sessions",
                        operation="transition-%s" % new_state.lower(),
                        outcome=(
                            MutationOutcome.COMMITTED
                            if transition.ok
                            else MutationOutcome.REJECTED
                        ),
                        detail="%s (%s)" % (transition.code, transition.detail[:64]),
                    )
                )
                flows.append(
                    FlowObservation(
                        flow="session",
                        ok=transition.ok,
                        code=transition.code,
                        ref=session_id,
                    )
                )
                if not transition.ok:
                    return (
                        mutations,
                        flows,
                        "session request %r: lifecycle transition to %s failed closed"
                        % (label, new_state),
                    )
            self._sessions_by_label[label] = (
                session_id,
                route_decision,
                decision,
                source,
                destination,
            )
        return (
            mutations,
            flows,
            "session request %r: policy -> routing -> session authority chain" % label,
        )

    def _apply_path_add(
        self, payload: Mapping[str, Any], now: str
    ) -> Tuple[List[AuthorityMutation], List[FlowObservation], str]:
        label = payload["label"]
        session_id, current, decision, source, destination = self._require_session(label)
        avoid = tuple(
            self._environment.link_subject(pair[0], pair[1])
            for pair in payload.get("avoid", ())
        )
        mutations: List[AuthorityMutation] = []
        flows: List[FlowObservation] = []
        # The session's policy binding never changes silently: the new
        # route is computed under the SAME retained accepted policy
        # decision (WORK-012 reconnect verification, reused verbatim by
        # the WORK-013 admission verification).
        route_flows, route_decision = self._evaluate_route(
            source, destination, decision, now, avoid=avoid
        )
        flows.extend(route_flows)
        if route_decision is None:
            return mutations, flows, "path-add for %r produced no alternate route" % label
        result = self._multipath.add_path(
            session_id,
            route_decision,
            event_instant=now,
            actor_reference="simulator:scenario",
        )
        mutations.append(
            AuthorityMutation(
                authority="multipath",
                operation="add-path",
                outcome=(
                    MutationOutcome.COMMITTED if result.ok else MutationOutcome.REJECTED
                ),
                detail="%s (%s)" % (result.code, result.detail[:64]),
            )
        )
        flows.append(
            FlowObservation(
                flow="multipath",
                ok=result.ok,
                code=result.code,
                ref=(result.plan.plan_id if result.plan else ""),
            )
        )
        return (
            mutations,
            flows,
            "path-add for %r through the real WORK-013 store (routing selected the "
            "alternate; multipath admitted it)" % label,
        )

    def _apply_path_fail(
        self, payload: Mapping[str, Any], now: str
    ) -> Tuple[List[AuthorityMutation], List[FlowObservation], str]:
        from multipath.model import PathStatus

        label = payload["label"]
        session_id, _current, _decision, _source, _destination = self._require_session(label)
        plan = self._multipath.get_plan(session_id)
        if plan is None:
            raise SimulatorError(
                SimulatorReasonCode.UNKNOWN_SESSION,
                "session %r has no multipath plan" % label,
            )
        entries = plan.entries
        index = payload.get("index", 0)
        if not 0 <= index < len(entries):
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "path index %d out of range (plan has %d entries)"
                % (index, len(entries)),
            )
        path_id = entries[index].path_id
        result = self._multipath.change_path_status(
            session_id,
            path_id,
            PathStatus.FAILED,
            event_instant=now,
            actor_reference="simulator:scenario",
            reason_code="simulator:fault-injection",
        )
        mutations = [
            AuthorityMutation(
                authority="multipath",
                operation="change-path-status",
                outcome=(
                    MutationOutcome.COMMITTED if result.ok else MutationOutcome.REJECTED
                ),
                detail="%s (%s)" % (result.code, result.detail[:64]),
            )
        ]
        session = self._sessions.get(session_id)
        flows = [
            FlowObservation(
                flow="multipath",
                ok=result.ok,
                code=result.code,
                ref=path_id,
                detail="constituent failed; session state %s"
                % (session.state if session else "unknown"),
            )
        ]
        return (
            mutations,
            flows,
            "path failure injected through the real WORK-013 store (loss of one "
            "path does not terminate the session)",
        )

    def _apply_session_fail(
        self, payload: Mapping[str, Any], now: str
    ) -> Tuple[List[AuthorityMutation], List[FlowObservation], str]:
        """Inject a provider/session failure through the REAL WORK-012
        transition table (the frozen table routes active sessions to
        FAILED; a failed session is terminal)."""
        label = payload["label"]
        session_id, _current, _decision, _source, _destination = self._require_session(label)
        result = self._sessions.transition(
            session_id,
            "FAILED",
            event_instant=now,
            actor_reference="simulator:scenario",
            reason_code="simulator:fault-injection",
        )
        mutations = [
            AuthorityMutation(
                authority="sessions",
                operation="transition-failed",
                outcome=(
                    MutationOutcome.COMMITTED if result.ok else MutationOutcome.REJECTED
                ),
                detail="%s (%s)" % (result.code, result.detail[:64]),
            )
        ]
        flows = [
            FlowObservation(
                flow="session",
                ok=result.ok,
                code=result.code,
                ref=session_id,
            )
        ]
        return (
            mutations,
            flows,
            "session failure injected through the real WORK-012 transition table",
        )

    def _apply_mobility_handover(
        self, payload: Mapping[str, Any], now: str
    ) -> Tuple[List[AuthorityMutation], List[FlowObservation], str]:
        from mobility.model import HandoverMode

        label = payload["label"]
        session_id, current, decision, source, destination = self._require_session(label)
        avoid = tuple(
            self._environment.link_subject(pair[0], pair[1])
            for pair in payload.get("avoid", ())
        )
        mutations: List[AuthorityMutation] = []
        flows: List[FlowObservation] = []
        # Same retained-decision discipline as path-add: the candidate
        # route is computed under the session's accepted policy decision.
        route_flows, candidate = self._evaluate_route(
            source, destination, decision, now, avoid=avoid
        )
        flows.extend(route_flows)
        if candidate is None:
            return mutations, flows, "handover for %r produced no candidate route" % label
        prepared = self._mobility.prepare_handover(
            session_id,
            candidate,
            mode=HandoverMode.MAKE_BEFORE_BREAK,
            event_instant=now,
            old_route_decision=current,
        )
        mutations.append(
            AuthorityMutation(
                authority="mobility",
                operation="prepare-handover",
                outcome=(
                    MutationOutcome.COMMITTED if prepared.ok else MutationOutcome.REJECTED
                ),
                detail="%s (%s)" % (prepared.code, prepared.detail[:64]),
            )
        )
        if not prepared.ok or prepared.transaction is None:
            flows.append(
                FlowObservation(
                    flow="mobility",
                    ok=False,
                    code=prepared.code,
                    detail=prepared.detail[:96],
                )
            )
            return mutations, flows, "handover preparation failed closed for %r" % label
        committed = self._mobility.commit_handover(
            prepared.transaction.transaction_id,
            event_instant=now,
            actor_reference="simulator:scenario",
        )
        mutations.append(
            AuthorityMutation(
                authority="mobility",
                operation="commit-handover",
                outcome=(
                    MutationOutcome.COMMITTED if committed.ok else MutationOutcome.REJECTED
                ),
                detail="%s (%s)" % (committed.code, committed.detail[:64]),
            )
        )
        flows.append(
            FlowObservation(
                flow="mobility",
                ok=committed.ok,
                code=committed.code,
                ref=prepared.transaction.transaction_id,
                detail="make-before-break; session identity preserved",
            )
        )
        if committed.ok:
            self._sessions_by_label[label] = (
                session_id,
                candidate,
                decision,
                source,
                destination,
            )
        return (
            mutations,
            flows,
            "mobility handover for %r through the real WORK-014 store" % label,
        )

    def _apply_cleanup(
        self, payload: Mapping[str, Any], now: str
    ) -> Tuple[List[AuthorityMutation], List[FlowObservation], str]:
        label = payload["label"]
        session_id, _current, _decision, _source, _destination = self._require_session(label)
        result = self._sessions.terminate(
            session_id,
            event_instant=now,
            actor_reference="simulator:scenario",
            reason_code="simulator:cleanup",
        )
        if result.ok:
            mutation = AuthorityMutation(
                authority="sessions",
                operation="terminate",
                outcome=MutationOutcome.COMMITTED,
                detail="%s (%s)" % (result.code, result.detail[:64]),
            )
        else:
            # Cleanup is correctness: an owner-contract cleanup failure
            # becomes an EXPLICIT pending state, never a silent pass.
            self._pending_cleanups += 1
            mutation = AuthorityMutation(
                authority="sessions",
                operation="terminate",
                outcome=MutationOutcome.PENDING,
                detail="%s (%s)" % (result.code, result.detail[:64]),
            )
        flows = [
            FlowObservation(
                flow="cleanup",
                ok=result.ok,
                code=result.code,
                ref=session_id,
                detail=result.detail[:96],
            )
        ]
        return (
            [mutation],
            flows,
            "cleanup for %r through the real WORK-012 terminate contract" % label,
        )

    def _apply_observe(
        self, payload: Mapping[str, Any], now: str
    ) -> Tuple[List[AuthorityMutation], List[FlowObservation], str]:
        flows = self._observe_probes(now)
        for node in self._environment.node_ids:
            state = self._environment.power_simulator(node).energy_state()
            sequence = self._posture_sequence.get(node, 1)
            self._posture_sequence[node] = sequence + 1
            posture = self._governor.posture_from_energy_state(
                state,
                node_id=node,
                power_source=self._node_power_source(node),
                thermal_state="normal",
                observed_at=now,
                sequence=sequence,
            )
            stage = self._governor.classify_stage(
                posture, self._environment.survival_profile(node)
            )
            flows.append(
                FlowObservation(
                    flow="energy",
                    ok=True,
                    code="posture",
                    ref=posture.posture_id,
                    detail="stage %s (reserve %d bp)"
                    % (stage, posture.reserve_basis_points),
                )
            )
        return (
            [],
            flows,
            "observation sweep: %d probe(s) + %d energy posture(s)"
            % (len(self._spec.probes), len(self._environment.node_ids)),
        )

    # ------------------------------------------------------------------
    # Flow composition (the genuine authority chains)
    # ------------------------------------------------------------------

    def _policy_gate(
        self, requester: str, now: str
    ) -> Tuple[bool, Any, List[FlowObservation]]:
        """Evaluate policy through the REAL WORK-010 engine over the
        live policy store (the documented conservative aggregation)."""
        context = PolicyContext(
            operation=Operation.SESSION_CREATE,
            requester_node_id=requester,
            credential_active=True,
            evaluation_instant=now,
        )
        try:
            applicable = self._policy_store.list_applicable(now)
        except PolicyError as error:
            return (
                False,
                None,
                [
                    FlowObservation(
                        flow="policy",
                        ok=False,
                        code="store-error",
                        detail=str(error)[:96],
                    )
                ],
            )
        if not applicable:
            return (
                False,
                None,
                [
                    FlowObservation(
                        flow="policy",
                        ok=False,
                        code=DecisionCode.DEFAULT_DENY,
                        detail="no applicable policy set at %s (deny-by-default)" % now,
                    )
                ],
            )
        allow_decision = None
        blocking = ""
        for policy_set in applicable:
            result = self._engine.evaluate(policy_set, context)
            if result.code in _BLOCKING_POLICY_CODES:
                blocking = "%s@%d blocks (%s)" % (
                    policy_set.set_id,
                    policy_set.version,
                    result.code,
                )
                break
            if (
                allow_decision is None
                and result.code == DecisionCode.ALLOW
                and result.decision is not None
                and result.decision.effect == Effect.ALLOW
            ):
                allow_decision = result.decision
        if allow_decision is not None:
            return (
                True,
                allow_decision,
                [
                    FlowObservation(
                        flow="policy",
                        ok=True,
                        code=DecisionCode.ALLOW,
                        ref=allow_decision.decision_id,
                    )
                ],
            )
        detail = blocking if blocking else "no explicit ALLOW in live sets"
        return (
            False,
            None,
            [FlowObservation(flow="policy", ok=False, code=DecisionCode.DEFAULT_DENY, detail=detail[:96])],
        )

    def _evaluate_route(
        self,
        source: str,
        destination: str,
        decision: Any,
        now: str,
        avoid: Tuple[str, ...],
    ) -> Tuple[List[FlowObservation], Optional[Any]]:
        """Evaluate routing through the REAL WORK-011 engine over the
        current authority state and environment metric facts.

        ``avoid`` is scenario exploration INPUT: the named links carry
        an extreme latency penalty in the metric facts handed to the
        engine (the routing authority still selects; the simulator
        never picks a path itself)."""
        metrics = self._environment.link_metrics(now, self._horizon_instant)
        for subject in avoid:
            if subject in metrics:
                current = metrics[subject]
                metrics[subject] = LinkMetrics(
                    latency_ms=_AVOID_LATENCY_MS,
                    loss_basis_points=current.loss_basis_points,
                    capacity_bps=current.capacity_bps,
                    energy_cost_millijoules=current.energy_cost_millijoules,
                    confidence_basis_points=current.confidence_basis_points,
                    observed_at=current.observed_at,
                    freshness_until=current.freshness_until,
                    provenance=current.provenance,
                )
        try:
            context = RoutingContext(
                source_node_id=source,
                destination_node_id=destination,
                topology=self._topology,
                resources=self._resources,
                evaluation_instant=now,
                policy_decision=decision,
                link_metrics=metrics,
            )
        except RoutingError as error:
            return (
                [
                    FlowObservation(
                        flow="routing",
                        ok=False,
                        code="invalid-context",
                        detail=str(error)[:96],
                    )
                ],
                None,
            )
        result = self._routing.evaluate(context)
        selected = result.decision.selected if result.decision is not None else None
        ok = bool(result.ok and result.decision is not None and selected is not None)
        flow = FlowObservation(
            flow="routing",
            ok=ok,
            code=result.code,
            ref=(result.decision.decision_id if result.decision else ""),
            detail=(
                "path %s (%d hops)" % (selected.path_id[:24], selected.metrics.hop_count)
                if selected is not None
                else result.detail[:96]
            ),
        )
        if ok and result.decision is not None:
            return [flow], result.decision
        return [flow], None

    def _observe_probes(self, now: str) -> List[FlowObservation]:
        flows: List[FlowObservation] = []
        for source, destination in self._spec.probes:
            authorized, decision, policy_flows = self._policy_gate(source, now)
            flows.extend(policy_flows)
            if not authorized or decision is None:
                continue
            route_flows, _ = self._evaluate_route(source, destination, decision, now, avoid=())
            flows.extend(route_flows)
        return flows

    # ------------------------------------------------------------------
    # Authority state digests
    # ------------------------------------------------------------------

    def _digest_state(self, now: str) -> Tuple[Tuple[str, str], ...]:
        moment = parse_instant(now)
        topology_projection = sorted(
            claim.claim_id for claim in self._topology.get_current_observations(now=moment)
        )
        resource_projection: Dict[str, Any] = {}
        for node in sorted(self._energy_resource_ids):
            resource_id = self._energy_resource_ids[node]
            offer = self._resources.get_current_offer(resource_id, now=moment)
            measurement = self._resources.get_current_measurement(resource_id, now=moment)
            resource_projection[resource_id] = [
                offer.offer_id if offer else None,
                measurement.measurement_id if measurement else None,
            ]
        power_projection = {
            node: self._environment.power_simulator(node).trajectory_digest()
            for node in sorted(self._environment.node_ids)
        }
        return (
            (
                "topology",
                _digest(
                    {
                        "claims": topology_projection,
                    }
                ),
            ),
            ("resources", _digest(resource_projection)),
            (
                "sessions",
                "sha256:"
                + hashlib.sha256(self._sessions.to_canonical_bytes()).hexdigest(),
            ),
            (
                "policy",
                _digest(
                    [
                        set_id_version
                        for policy_set in self._policy_store.snapshot()
                        for set_id_version in (
                            "%s@%d" % (policy_set.set_id, policy_set.version),
                        )
                    ]
                ),
            ),
            ("telemetry", _digest(_plain(self._telemetry.snapshot()))),
            ("mobility", _digest(_plain(self._mobility.snapshot()))),
            ("ledger", "sha256:" + hashlib.sha256(self._ledger.ledger_digest().encode("utf-8")).hexdigest()),
            ("power", _digest(power_projection)),
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _merge_link_claim(self, subject: str, now: str) -> List[AuthorityMutation]:
        claim = self._environment.link_claim(subject, now, self._horizon_instant)
        outcome: MergeOutcome = self._topology.merge(claim)
        return [
            AuthorityMutation(
                authority="topology",
                operation="merge-link-state",
                outcome=(
                    MutationOutcome.COMMITTED
                    if outcome.accepted
                    else MutationOutcome.REJECTED
                ),
                detail="%s (%s)" % (outcome.code, subject[:48]),
            )
        ]

    def _require_session(self, label: str) -> Tuple[str, Any, Any, str, str]:
        """(session_id, current route decision, retained policy decision,
        source, destination) for a scenario session label."""
        entry = self._sessions_by_label.get(label)
        if entry is None:
            raise SimulatorError(
                SimulatorReasonCode.UNKNOWN_SESSION,
                "no session with label %r in this scenario" % label,
            )
        return entry

    def _node_power_source(self, node: str) -> str:
        for spec_node in self._spec.nodes:
            if spec_node.node_id == node:
                return spec_node.power_source
        return "battery"

    def _policy_set(
        self, set_id: str, version: int, rules: Tuple[ScenarioPolicyRule, ...]
    ) -> PolicySet:
        real_rules = tuple(
            PolicyRule(
                rule_id=rule.rule_id,
                domain=PolicyDomain.IDENTITY,
                effect=rule.effect,
                operation=rule.operation,
                subjects=rule.subjects,
                priority=rule.priority,
                specificity=rule.specificity,
            )
            for rule in rules
        )
        return PolicySet(
            set_id=set_id,
            version=version,
            rules=real_rules,
            default_effect=Effect.DENY,
            issuer_node_id=self._issuer,
        )


def _validate_payload(event: ScheduledEvent) -> str:
    """Structural payload validation per event kind (fail closed).

    Returns an empty string when the payload is structurally valid;
    otherwise a human-readable rejection detail.  Semantic target
    resolution (unknown nodes/links/sessions) happens in the handlers
    so those rejections are observable REJECTED records.
    """
    kind = event.kind
    payload = event.payload

    def _need_str(key: str) -> Optional[str]:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            return "%r must be a non-empty string" % key
        return None

    def _need_pairs(key: str) -> Optional[str]:
        value = payload.get(key, [])
        if not isinstance(value, (list, tuple)):
            return "%r must be a list of [node_a, node_b] pairs" % key
        for pair in value:
            if (
                not isinstance(pair, (list, tuple))
                or len(pair) != 2
                or not all(isinstance(item, str) and item for item in pair)
            ):
                return "%r entries must be [node_a, node_b] string pairs" % key
        return None

    if kind in (EventKind.NODE_DOWN, EventKind.NODE_UP):
        problem = _need_str("node")
        if problem:
            return problem
        if kind == EventKind.NODE_UP:
            for key in ("level_millijoules", "capacity_millijoules", "power_draw_milliwatts"):
                if key in payload and not isinstance(payload[key], int):
                    return "%r must be an integer" % key
        return ""

    if kind in (EventKind.LINK_DOWN, EventKind.LINK_UP, EventKind.LINK_DEGRADE):
        for key in ("node_a", "node_b"):
            problem = _need_str(key)
            if problem:
                return problem
        return ""

    if kind in (EventKind.PARTITION_START, EventKind.PARTITION_END):
        return _need_pairs("cuts") or ""

    if kind == EventKind.RESOURCE_EXHAUST:
        problem = _need_str("node")
        if problem:
            return problem
        fraction = payload.get("fraction_bp")
        if not isinstance(fraction, int) or not 0 <= fraction <= 10_000:
            return "'fraction_bp' must be an integer within [0, 10000]"
        return ""

    if kind == EventKind.POLICY_AMEND:
        for key in ("set_id",):
            problem = _need_str(key)
            if problem:
                return problem
        version = payload.get("version")
        if not isinstance(version, int) or version < 1:
            return "'version' must be an integer >= 1"
        rules = payload.get("rules")
        if not isinstance(rules, (list, tuple)) or not rules:
            return "'rules' must be a non-empty list of rule objects"
        for rule in rules:
            if not isinstance(rule, dict):
                return "'rules' entries must be objects"
            if not isinstance(rule.get("rule_id"), str) or not rule.get("rule_id"):
                return "each rule needs a non-empty 'rule_id'"
            effect = rule.get("effect", "allow")
            if effect not in ("allow", "deny"):
                return "rule 'effect' must be 'allow' or 'deny'"
            subjects = rule.get("subjects", ())
            if not isinstance(subjects, (list, tuple)) or not all(
                isinstance(item, str) and item for item in subjects
            ):
                return "rule 'subjects' must be a list of strings"
        return ""

    if kind == EventKind.POLICY_WITHDRAW:
        problem = _need_str("set_id")
        if problem:
            return problem
        version = payload.get("version")
        if not isinstance(version, int) or version < 1:
            return "'version' must be an integer >= 1"
        return ""

    if kind == EventKind.TELEMETRY_EMIT:
        for key in ("node", "subject_kind", "subject_ref", "metric"):
            problem = _need_str(key)
            if problem:
                return problem
        value = payload.get("value")
        if not isinstance(value, int):
            return "'value' must be an integer"
        return ""

    if kind == EventKind.SESSION_REQUEST:
        for key in ("label", "source", "destination"):
            problem = _need_str(key)
            if problem:
                return problem
        return ""

    if kind in (EventKind.PATH_ADD, EventKind.MOBILITY_HANDOVER):
        problem = _need_str("label")
        if problem:
            return problem
        return _need_pairs("avoid") or ""

    if kind in (EventKind.PATH_FAIL, EventKind.SESSION_FAIL):
        problem = _need_str("label")
        if problem:
            return problem
        if kind == EventKind.PATH_FAIL:
            index = payload.get("index", 0)
            if not isinstance(index, int) or index < 0:
                return "'index' must be a non-negative integer"
        return ""

    if kind == EventKind.CLEANUP:
        return _need_str("label") or ""

    if kind == EventKind.OBSERVE:
        return ""

    return "unknown event kind %r" % kind


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(_plain(value))).hexdigest()


def _plain(value: Any) -> Any:
    """Convert snapshot trees into canonical-JSON-safe structures."""
    if isinstance(value, dict):
        return {
            str(key): _plain(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "to_dict"):
        return _plain(value.to_dict())
    return repr(value)


def verify_replay(
    spec: ScenarioSpec,
    expected: ScenarioResult,
    *,
    seam: Optional[AuthorityTestSeam] = None,
) -> Tuple[bool, str]:
    """Re-run ``spec`` in a fresh isolated :class:`Simulator` and verify
    the trace digest against ``expected``.

    Replay evidence is committed only after successful verification:
    the digest comparison IS the verification (any divergence raises
    no mutation and returns an explicit mismatch report).
    """
    actual = Simulator(spec, seam=seam).run()
    if actual.trace_digest != expected.trace_digest:
        return (
            False,
            "trace digest mismatch: %s != %s"
            % (actual.trace_digest[:24], expected.trace_digest[:24]),
        )
    if actual.to_dict() != expected.to_dict():
        return False, "result content diverged despite equal trace digests"
    return True, "replay verified: trace digest %s" % actual.trace_digest[:24]
