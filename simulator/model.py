"""Simulator vocabularies, scenario specification, and observation records.

WORK-031 -- Network and behavior simulator.

This module defines the frozen vocabularies and immutable records the
simulator operates on:

- :class:`EventKind` -- the frozen scenario-event taxonomy (node/link
  failures, partitions, resource exhaustion, policy amendments,
  telemetry emission, session/multipath/mobility flows, cleanup,
  observation points);
- :class:`SimulatedNodeSpec` / :class:`SimulatedLinkSpec` /
  :class:`ScenarioPolicyRule` -- the scenario configuration material
  (pure DATA -- it is never an authority object);
- :class:`ScenarioSpec` -- the complete, immutable, reproducible
  scenario configuration (explicit seed + injected time base + ordered
  events);
- :class:`ScheduledEvent` -- one scheduled scenario event with an
  explicit ``(at_tick, sequence)`` ordering key and a content-derived
  ``event_id``;
- :class:`ObservationRecord` / :class:`AuthorityMutation` /
  :class:`FlowObservation` / :class:`ScenarioResult` -- the observed
  authoritative outputs and evidence/trace state.

Module authority: ``/simulator`` owns deterministic scenario
orchestration and simulated environment state.  It does NOT own
topology truth (WORK-007), resource truth (WORK-008), policy decisions
(WORK-010), path selection (WORK-011), session lifecycle (WORK-012),
multipath plans (WORK-013), mobility transactions (WORK-014), telemetry
records (WORK-026), or energy/resilience mechanics (WORK-027).  Every
record in this module is scenario DATA or observed OUTPUT -- never a
second protocol authority.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Mapping, Set, Tuple

from protocol.canonicalization import CanonicalizationError, canonical_json_bytes

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

_SCENARIO_ID_RE_OK = frozenset(
    "abcdefghijklmnopqrstuvwxyz0123456789-"
)


class SimulatorError(ValueError):
    """Fail-closed simulator error with a stable machine-readable code."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__("%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


class SimulatorReasonCode:
    """Frozen stable reason-code vocabulary (mirrors the family style)."""

    INVALID_INPUT = "invalid-input"
    UNKNOWN_NODE = "unknown-node"
    UNKNOWN_LINK = "unknown-link"
    UNKNOWN_SESSION = "unknown-session"
    DUPLICATE_SEQUENCE = "duplicate-sequence"
    UNKNOWN_EVENT = "unknown-event"
    EVENT_OUT_OF_HORIZON = "event-out-of-horizon"
    UNSUPPORTED_SEAM_COMPONENT = "unsupported-seam-component"
    SEAM_PURPOSE_REQUIRED = "seam-purpose-required"
    REPLAY_MISMATCH = "replay-mismatch"
    DETERMINISM = "determinism"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.INVALID_INPUT,
            cls.UNKNOWN_NODE,
            cls.UNKNOWN_LINK,
            cls.UNKNOWN_SESSION,
            cls.DUPLICATE_SEQUENCE,
            cls.UNKNOWN_EVENT,
            cls.EVENT_OUT_OF_HORIZON,
            cls.UNSUPPORTED_SEAM_COMPONENT,
            cls.SEAM_PURPOSE_REQUIRED,
            cls.REPLAY_MISMATCH,
            cls.DETERMINISM,
        )


# ---------------------------------------------------------------------------
# Frozen event taxonomy
# ---------------------------------------------------------------------------

class EventKind:
    """The frozen scenario-event taxonomy (first-class fault injection).

    Failure/recovery vocabulary per the WORK-031 boundary: link
    down/degraded/up, node down/up (restart/rejoin), partition
    start/end, resource exhaustion, policy amend/withdraw, telemetry
    emission, session request, multipath path add/fail, mobility
    handover, cleanup (with observable cleanup failure), and pure
    observation points.
    """

    NODE_DOWN = "node-down"
    NODE_UP = "node-up"
    LINK_DOWN = "link-down"
    LINK_UP = "link-up"
    LINK_DEGRADE = "link-degraded"
    PARTITION_START = "partition-start"
    PARTITION_END = "partition-end"
    RESOURCE_EXHAUST = "resource-exhaust"
    POLICY_AMEND = "policy-amend"
    POLICY_WITHDRAW = "policy-withdraw"
    TELEMETRY_EMIT = "telemetry-emit"
    SESSION_REQUEST = "session-request"
    PATH_ADD = "path-add"
    PATH_FAIL = "path-fail"
    SESSION_FAIL = "session-fail"
    MOBILITY_HANDOVER = "mobility-handover"
    CLEANUP = "cleanup"
    OBSERVE = "observe"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.NODE_DOWN,
            cls.NODE_UP,
            cls.LINK_DOWN,
            cls.LINK_UP,
            cls.LINK_DEGRADE,
            cls.PARTITION_START,
            cls.PARTITION_END,
            cls.RESOURCE_EXHAUST,
            cls.POLICY_AMEND,
            cls.POLICY_WITHDRAW,
            cls.TELEMETRY_EMIT,
            cls.SESSION_REQUEST,
            cls.PATH_ADD,
            cls.PATH_FAIL,
            cls.SESSION_FAIL,
            cls.MOBILITY_HANDOVER,
            cls.CLEANUP,
            cls.OBSERVE,
        )


class EventVerdict:
    """The frozen per-event application verdict."""

    APPLIED = "applied"
    REJECTED = "rejected"
    FAILED = "failed"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.APPLIED, cls.REJECTED, cls.FAILED)


class MutationOutcome:
    """The frozen authority-mutation outcome vocabulary."""

    COMMITTED = "committed"
    REJECTED = "rejected"
    PENDING = "pending"
    DEGRADED = "degraded"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.COMMITTED, cls.REJECTED, cls.PENDING, cls.DEGRADED)


# ---------------------------------------------------------------------------
# Scenario configuration material (pure DATA)
# ---------------------------------------------------------------------------

# Mirrors the frozen WORK-027 PowerSource vocabulary (energy.model).
_POWER_SOURCES = frozenset(
    {"solar-hybrid", "grid", "battery", "generator", "harvesting"}
)


@dataclass(frozen=True)
class SimulatedNodeSpec:
    """One simulated node's power/resource configuration (DATA).

    The survival-profile fields carry only the thresholds the scenario
    needs to vary; the remaining WORK-027 ``SurvivalProfile`` fields are
    documented constants fixed by the runner (empty service classes,
    upstream 2/4/3 counters, loss threshold 2000 bp, max generation
    500 mW) so the derived ``profile_id`` stays a pure function of this
    spec.
    """

    node_id: str
    capacity_millijoules: int = 10_000_000
    initial_level_millijoules: int = 3_600_000
    load_milliwatts: int = 100
    generation_milliwatts: int = 0
    power_source: str = "solar-hybrid"
    conserve_threshold_bp: int = 6000
    critical_threshold_bp: int = 3000
    survival_threshold_bp: int = 1500
    survival_reserve_bp: int = 1000
    offline_grace_seconds: int = 3600

    def __post_init__(self) -> None:
        from identity.node_id import NodeIdError, parse_node_id

        try:
            parse_node_id(self.node_id)
        except NodeIdError as error:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "node_id %r must be a canonical ADCOS NodeID: %s"
                % (self.node_id, error),
            ) from error
        if self.power_source not in _POWER_SOURCES:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "power_source %r must be one of %s"
                % (self.power_source, sorted(_POWER_SOURCES)),
            )
        if self.capacity_millijoules <= 0:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "capacity_millijoules must be positive",
            )
        if not 0 <= self.initial_level_millijoules <= self.capacity_millijoules:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "initial_level_millijoules must be within [0, capacity]",
            )
        if self.load_milliwatts < 0 or self.generation_milliwatts < 0:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "load/generation milliwatts must be non-negative",
            )
        for name in (
            "conserve_threshold_bp",
            "critical_threshold_bp",
            "survival_threshold_bp",
            "survival_reserve_bp",
        ):
            value = getattr(self, name)
            if not 0 <= value <= 10_000:
                raise SimulatorError(
                    SimulatorReasonCode.INVALID_INPUT,
                    "%s must be within [0, 10000] basis points" % name,
                )
        if self.offline_grace_seconds < 0:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "offline_grace_seconds must be non-negative",
            )

    def content_dict(self) -> Dict[str, Any]:
        """The canonical content of this node configuration (the
        material the bootstrap registers)."""
        return {
            "node_id": self.node_id,
            "capacity_millijoules": self.capacity_millijoules,
            "initial_level_millijoules": self.initial_level_millijoules,
            "load_milliwatts": self.load_milliwatts,
            "generation_milliwatts": self.generation_milliwatts,
            "power_source": self.power_source,
            "conserve_threshold_bp": self.conserve_threshold_bp,
            "critical_threshold_bp": self.critical_threshold_bp,
            "survival_threshold_bp": self.survival_threshold_bp,
            "survival_reserve_bp": self.survival_reserve_bp,
            "offline_grace_seconds": self.offline_grace_seconds,
        }


@dataclass(frozen=True)
class SimulatedLinkSpec:
    """One simulated link's base metric facts (DATA).

    These are the technology-neutral WORK-011 metric facts the
    environment projects into real :class:`LinkMetrics` records; they
    are never topology authority state by themselves.
    """

    node_a: str
    node_b: str
    latency_ms: int = 10
    loss_basis_points: int = 0
    capacity_bps: int = 1_000_000
    energy_cost_millijoules: int = 100
    confidence_basis_points: int = 10_000

    def __post_init__(self) -> None:
        from identity.node_id import NodeIdError, parse_node_id

        for name in ("node_a", "node_b"):
            value = getattr(self, name)
            try:
                parse_node_id(value)
            except NodeIdError as error:
                raise SimulatorError(
                    SimulatorReasonCode.INVALID_INPUT,
                    "%s %r must be a canonical ADCOS NodeID: %s"
                    % (name, value, error),
                ) from error
        if self.latency_ms < 0:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT, "latency_ms must be >= 0"
            )
        if not 0 <= self.loss_basis_points <= 10_000:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "loss_basis_points must be within [0, 10000]",
            )
        if self.capacity_bps <= 0:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT, "capacity_bps must be positive"
            )
        if self.energy_cost_millijoules < 0:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "energy_cost_millijoules must be >= 0",
            )
        if not 0 <= self.confidence_basis_points <= 10_000:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "confidence_basis_points must be within [0, 10000]",
            )

    def content_dict(self) -> Dict[str, Any]:
        """The canonical content of this link configuration."""
        return {
            "node_a": self.node_a,
            "node_b": self.node_b,
            "latency_ms": self.latency_ms,
            "loss_basis_points": self.loss_basis_points,
            "capacity_bps": self.capacity_bps,
            "energy_cost_millijoules": self.energy_cost_millijoules,
            "confidence_basis_points": self.confidence_basis_points,
        }


@dataclass(frozen=True)
class ScenarioPolicyRule:
    """Scenario-side policy material (DATA).

    The runner converts each entry into a REAL WORK-010
    :class:`PolicyRule` inside a REAL :class:`PolicySet` published
    through the real :class:`PolicyStore`; the simulator never
    evaluates policy itself.
    """

    rule_id: str
    effect: str = "allow"
    operation: str = "session.create"
    subjects: Tuple[str, ...] = ()
    priority: int = 0
    specificity: int = 0
    valid_from: str = ""
    valid_until: str = ""

    def __post_init__(self) -> None:
        if not self.rule_id or not isinstance(self.rule_id, str):
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT, "rule_id must be non-empty"
            )
        if self.effect not in ("allow", "deny"):
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "effect %r must be 'allow' or 'deny'" % (self.effect,),
            )
        if not isinstance(self.operation, str) or not self.operation:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "operation must be a non-empty policy operation code",
            )
        for subject in self.subjects:
            if not isinstance(subject, str) or not subject:
                raise SimulatorError(
                    SimulatorReasonCode.INVALID_INPUT,
                    "subjects entries must be non-empty strings",
                )
        if not isinstance(self.priority, int) or not isinstance(
            self.specificity, int
        ):
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "priority/specificity must be integers",
            )

    def content_dict(self) -> Dict[str, Any]:
        """The canonical content of this scenario policy rule."""
        return {
            "rule_id": self.rule_id,
            "effect": self.effect,
            "operation": self.operation,
            "subjects": list(self.subjects),
            "priority": self.priority,
            "specificity": self.specificity,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
        }


@dataclass(frozen=True)
class ScheduledEvent:
    """One scheduled scenario event with an explicit ordering key.

    ``event_id`` is content-derived over the canonical bytes of
    ``(at_tick, sequence, kind, payload)`` -- insertion order in the
    spec tuple carries no identity, and two specs differing only in
    tuple order are the same scenario (insertion/order independence).
    """

    at_tick: int
    sequence: int
    kind: str
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.at_tick, int) or self.at_tick < 0:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT, "at_tick must be an int >= 0"
            )
        if not isinstance(self.sequence, int) or self.sequence < 1:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT, "sequence must be an int >= 1"
            )
        if self.kind not in EventKind.values():
            raise SimulatorError(
                SimulatorReasonCode.UNKNOWN_EVENT,
                "kind %r must be one of %s" % (self.kind, EventKind.values()),
            )
        if not isinstance(self.payload, Mapping):
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "payload must be a mapping of str to JSON-representable data",
            )
        for key in self.payload:
            if not isinstance(key, str) or not key:
                raise SimulatorError(
                    SimulatorReasonCode.INVALID_INPUT,
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
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "event payload is not canonically representable: %s" % error,
            ) from error
        return "sha256:" + hashlib.sha256(digest).hexdigest()


@dataclass(frozen=True)
class ScenarioSpec:
    """The complete, immutable, reproducible scenario configuration.

    Reproducibility contract: ``seed`` + this spec's content + the
    deterministic execution order (events ordered by the explicit
    ``(at_tick, sequence)`` keys) produces byte-identical results.
    Scenario time is ALWAYS the injected
    :class:`~simulator.time.ScenarioClock` derived from
    ``start_instant`` and ``tick_seconds``; no wall clock is ever read.
    """

    scenario_id: str
    seed: int
    start_instant: str
    tick_seconds: int
    horizon_ticks: int
    nodes: Tuple[SimulatedNodeSpec, ...]
    links: Tuple[SimulatedLinkSpec, ...] = ()
    probes: Tuple[Tuple[str, str], ...] = ()
    policy_rules: Tuple[ScenarioPolicyRule, ...] = ()
    events: Tuple[ScheduledEvent, ...] = ()

    def __post_init__(self) -> None:
        from protocol.temporal import TemporalError, parse_instant

        if not self.scenario_id or not set(self.scenario_id) <= _SCENARIO_ID_RE_OK:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "scenario_id %r must be non-empty lowercase/hyphen/digit"
                % (self.scenario_id,),
            )
        if not isinstance(self.seed, int) or self.seed < 0:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "seed must be a non-negative integer",
            )
        try:
            parse_instant(self.start_instant)
        except TemporalError as error:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "start_instant must be an RFC 3339 UTC instant: %s" % error,
            ) from error
        if not isinstance(self.tick_seconds, int) or self.tick_seconds < 1:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "tick_seconds must be an int >= 1",
            )
        if not isinstance(self.horizon_ticks, int) or self.horizon_ticks < 0:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "horizon_ticks must be an int >= 0",
            )
        if not self.nodes:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "a scenario requires at least one simulated node",
            )
        node_ids = {node.node_id for node in self.nodes}
        if len(node_ids) != len(self.nodes):
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "duplicate node_id in scenario nodes",
            )
        for link in self.links:
            if link.node_a == link.node_b:
                raise SimulatorError(
                    SimulatorReasonCode.INVALID_INPUT,
                    "link endpoints must differ: %r" % (link.node_a,),
                )
            for endpoint in (link.node_a, link.node_b):
                if endpoint not in node_ids:
                    raise SimulatorError(
                        SimulatorReasonCode.UNKNOWN_NODE,
                        "link endpoint %r is not a scenario node" % endpoint,
                    )
        seen_links: Set[FrozenSet[str]] = set()
        for link in self.links:
            key = frozenset((link.node_a, link.node_b))
            if key in seen_links:
                raise SimulatorError(
                    SimulatorReasonCode.INVALID_INPUT,
                    "duplicate link between %r and %r" % (link.node_a, link.node_b),
                )
            seen_links.add(key)
        for source, destination in self.probes:
            if source not in node_ids or destination not in node_ids:
                raise SimulatorError(
                    SimulatorReasonCode.UNKNOWN_NODE,
                    "probe (%r, %r) must reference scenario nodes"
                    % (source, destination),
                )
        seen_keys: Set[Tuple[int, int]] = set()
        for event in self.events:
            event_key = (event.at_tick, event.sequence)
            if event_key in seen_keys:
                raise SimulatorError(
                    SimulatorReasonCode.DUPLICATE_SEQUENCE,
                    "duplicate event ordering key (tick=%d, sequence=%d)"
                    % event_key,
                )
            seen_keys.add(event_key)
            if event.at_tick > self.horizon_ticks:
                raise SimulatorError(
                    SimulatorReasonCode.EVENT_OUT_OF_HORIZON,
                    "event at tick %d exceeds horizon %d"
                    % (event.at_tick, self.horizon_ticks),
                )

    def bootstrap_event_id(self) -> str:
        """The content-derived identity of the tick-0 bootstrap
        observation.

        sha256 over the canonical JSON bytes of the complete,
        order-normalized scenario WORLD configuration -- everything the
        bootstrap registers (identity, seed, time base, horizon,
        nodes, links, probes, policy material).  The event schedule is
        deliberately excluded: the bootstrap event registers the
        world, not the schedule.  Nodes/links/probes/rules are sorted
        into canonical order, and every field participates, so the
        bootstrap identity is exactly as content-derived and
        insertion-order independent as every ``ScheduledEvent``
        identity -- one uniform identity rule for the whole trace.
        """
        material = {
            "kind": "bootstrap",
            "scenario_id": self.scenario_id,
            "seed": self.seed,
            "start_instant": self.start_instant,
            "tick_seconds": self.tick_seconds,
            "horizon_ticks": self.horizon_ticks,
            "nodes": [
                node.content_dict()
                for node in sorted(self.nodes, key=lambda item: item.node_id)
            ],
            "links": [
                link.content_dict()
                for link in sorted(
                    self.links, key=lambda item: (item.node_a, item.node_b)
                )
            ],
            "probes": [
                [source, destination]
                for source, destination in sorted(self.probes)
            ],
            "policy_rules": [
                rule.content_dict()
                for rule in sorted(self.policy_rules, key=lambda item: item.rule_id)
            ],
        }
        try:
            digest = canonical_json_bytes(material)
        except CanonicalizationError as error:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "scenario world configuration is not canonically "
                "representable: %s" % error,
            ) from error
        return "sha256:" + hashlib.sha256(digest).hexdigest()


# ---------------------------------------------------------------------------
# Observed authoritative outputs / trace state
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AuthorityMutation:
    """One authority mutation the runner performed through an OWNER
    contract, with the owner's own verdict (committed/rejected/pending/
    degraded).  This is the mechanical record that every authority
    change in a scenario went through the real owner API.
    """

    authority: str
    operation: str
    outcome: str
    detail: str = ""

    def __post_init__(self) -> None:
        if self.outcome not in MutationOutcome.values():
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "mutation outcome %r must be one of %s"
                % (self.outcome, MutationOutcome.values()),
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "authority": self.authority,
            "operation": self.operation,
            "outcome": self.outcome,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class FlowObservation:
    """One observed authoritative flow outcome (policy decision, route
    evaluation, session operation, multipath operation, mobility
    transaction, telemetry ingest, energy posture).  Carries only
    references (ids/codes) -- never authority objects."""

    flow: str
    ok: bool
    code: str
    ref: str = ""
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flow": self.flow,
            "ok": self.ok,
            "code": self.code,
            "ref": self.ref,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class ObservationRecord:
    """One trace record: the application of one scenario event (or one
    observation sweep) with the pre/post authority digests, every owner
    mutation, and every observed flow outcome.

    ``observation_id`` is content-derived over the canonical bytes of
    the record content -- deterministic and insertion-order
    independent.
    """

    tick: int
    instant: str
    event_id: str
    kind: str
    verdict: str
    mutations: Tuple[AuthorityMutation, ...] = ()
    before_digests: Tuple[Tuple[str, str], ...] = ()
    after_digests: Tuple[Tuple[str, str], ...] = ()
    flows: Tuple[FlowObservation, ...] = ()
    detail: str = ""

    def __post_init__(self) -> None:
        if self.verdict not in EventVerdict.values():
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "verdict %r must be one of %s" % (self.verdict, EventVerdict.values()),
            )

    def content_dict(self) -> Dict[str, Any]:
        return {
            "tick": self.tick,
            "instant": self.instant,
            "event_id": self.event_id,
            "kind": self.kind,
            "verdict": self.verdict,
            "mutations": [m.to_dict() for m in self.mutations],
            "before": dict(self.before_digests),
            "after": dict(self.after_digests),
            "flows": [f.to_dict() for f in self.flows],
            "detail": self.detail,
        }

    def observation_id(self) -> str:
        try:
            digest = canonical_json_bytes(self.content_dict())
        except CanonicalizationError as error:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "observation record is not canonically representable: %s" % error,
            ) from error
        return "sha256:" + hashlib.sha256(digest).hexdigest()


@dataclass(frozen=True)
class ScenarioResult:
    """The complete deterministic scenario outcome.

    ``trace_digest`` is the sha256 over the canonical bytes of the
    ordered observation records -- the reproducibility fingerprint.
    Two runs of the same spec (same seed, same content) MUST produce
    identical ``trace_digest`` values; any divergence is a
    determinism failure.
    """

    ok: bool
    scenario_id: str
    seed: int
    trace: Tuple[ObservationRecord, ...]
    trace_digest: str
    final_digests: Tuple[Tuple[str, str], ...] = ()
    applied_events: int = 0
    rejected_events: int = 0
    failed_events: int = 0
    pending_cleanups: int = 0
    seam_purpose: str = ""
    seam_verdict: str = ""
    seam_detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "scenario_id": self.scenario_id,
            "seed": self.seed,
            "records": [record.content_dict() for record in self.trace],
            "trace_digest": self.trace_digest,
            "final_digests": dict(self.final_digests),
            "applied_events": self.applied_events,
            "rejected_events": self.rejected_events,
            "failed_events": self.failed_events,
            "pending_cleanups": self.pending_cleanups,
            "seam_purpose": self.seam_purpose,
            "seam_verdict": self.seam_verdict,
            "seam_detail": self.seam_detail,
        }
