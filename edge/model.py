"""WORK-034 edge-gateway value model.

The frozen vocabularies and value records of the Pi-class edge layer:

- **pressure** -- the CPU / memory / storage pressure domains and the
  nominal -> pressured -> critical ladder (a classification of MODELED
  utilization, never a wall-clock measurement);
- **posture** -- the coexistence posture of the node's access
  interfaces (connected / degraded / offline);
- **scheduling** -- the resource-aware command verdicts (executed /
  deferred / shed) and the protected / essential / bulk priority
  classes;
- **events** -- the append-only edge event journal (the WORK-033
  agent-event discipline, applied to the edge layer's own decisions);
- **results** -- the edge run result: the agent's own outcomes plus
  the edge scheduling verdicts and digests, so a whole edge scenario
  is one deterministic, replayable digest.

Nothing here mutates another subsystem's state.  The value model is
DATA with validation, in the WORK-033 ``agent.model`` style.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Mapping, Tuple

from protocol.canonicalization import canonical_json_bytes

from .errors import EdgeError, EdgeReasonCode


# ----------------------------------------------------------------------
# Frozen vocabularies
# ----------------------------------------------------------------------


class PressureDomain:
    """The frozen resource-pressure domain vocabulary."""

    CPU = "cpu"
    MEMORY = "memory"
    STORAGE = "storage"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.CPU, cls.MEMORY, cls.STORAGE)


class PressureLevel:
    """The frozen pressure ladder (classification of modeled
    utilization; the WORK-016 worse-of discipline applies across
    domains)."""

    NOMINAL = "nominal"
    PRESSURED = "pressured"
    CRITICAL = "critical"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.NOMINAL, cls.PRESSURED, cls.CRITICAL)


#: Ladder ordinals for worse-of composition (higher == worse).
PRESSURE_LEVEL_ORDINALS = {
    PressureLevel.NOMINAL: 0,
    PressureLevel.PRESSURED: 1,
    PressureLevel.CRITICAL: 2,
}


def worse_pressure_level(levels: Tuple[str, ...]) -> str:
    """Compose pressure levels worst-first (the WORK-016 ladder
    discipline applied to the edge pressure domains)."""
    worst = PressureLevel.NOMINAL
    for level in levels:
        if PRESSURE_LEVEL_ORDINALS.get(level, 0) > PRESSURE_LEVEL_ORDINALS[worst]:
            worst = level
    return worst


class ConnectivityPosture:
    """The frozen access-coexistence posture vocabulary."""

    CONNECTED = "connected"
    DEGRADED = "degraded"
    OFFLINE = "offline"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.CONNECTED, cls.DEGRADED, cls.OFFLINE)


class CommandPriority:
    """The frozen resource-aware command priority vocabulary."""

    PROTECTED = "protected"
    ESSENTIAL = "essential"
    BULK = "bulk"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.PROTECTED, cls.ESSENTIAL, cls.BULK)


class SchedulingVerdict:
    """The frozen scheduling verdict vocabulary (what the edge layer
    did with a command; the agent's own applied/rejected/failed
    verdict is carried separately when a command was executed)."""

    EXECUTED = "executed"
    DEFERRED = "deferred"
    SHED = "shed"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.EXECUTED, cls.DEFERRED, cls.SHED)


class EdgeEventType:
    """The frozen edge event vocabulary (kebab-case, the WORK-033
    agent-event discipline).  Events record edge-layer DECISIONS --
    scheduling, coexistence, gateway claims -- never authority state
    (the agent event log remains the record of authority mutations)."""

    PRESSURE_LEVEL_CHANGED = "pressure-level-changed"
    POSTURE_CHANGED = "posture-changed"
    COMMAND_DEFERRED = "command-deferred"
    COMMAND_SHED = "command-shed"
    DEFERRED_DRAINED = "deferred-drained"
    ACCESS_SELECTED = "access-selected"
    CLAIM_ADDED = "claim-added"
    CLAIM_EXPIRED = "claim-expired"
    GATEWAY_FORWARDED = "gateway-forwarded"
    GATEWAY_FORWARD_REJECTED = "gateway-forward-rejected"
    MEMORY_RECLAIMED = "memory-reclaimed"
    STORAGE_COMPACTED = "storage-compacted"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.PRESSURE_LEVEL_CHANGED,
            cls.POSTURE_CHANGED,
            cls.COMMAND_DEFERRED,
            cls.COMMAND_SHED,
            cls.DEFERRED_DRAINED,
            cls.ACCESS_SELECTED,
            cls.CLAIM_ADDED,
            cls.CLAIM_EXPIRED,
            cls.GATEWAY_FORWARDED,
            cls.GATEWAY_FORWARD_REJECTED,
            cls.MEMORY_RECLAIMED,
            cls.STORAGE_COMPACTED,
        )


# ----------------------------------------------------------------------
# Pressure readings
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class PressureReading:
    """One modeled pressure reading: integer usage over an integer
    capacity, classified on the frozen ladder.  ``utilization_bp`` is
    basis points (0..10000) CLAMPED at the ceiling -- the ledger keeps
    the raw integer counts; the reading never invents precision."""

    domain: str
    used: int
    capacity: int
    utilization_bp: int
    level: str

    def __post_init__(self) -> None:
        if self.domain not in PressureDomain.values():
            raise EdgeError(
                EdgeReasonCode.INVALID_INPUT,
                "pressure domain must be one of %s" % (PressureDomain.values(),),
            )
        for name in ("used", "capacity", "utilization_bp"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise EdgeError(
                    EdgeReasonCode.INVALID_INPUT,
                    "%s must be an integer (got %s)"
                    % (name, type(value).__name__),
                )
            if value < 0:
                raise EdgeError(
                    EdgeReasonCode.INVALID_INPUT,
                    "%s must be non-negative (got %d)" % (name, value),
                )
        if self.utilization_bp > 10000:
            raise EdgeError(
                EdgeReasonCode.INVALID_INPUT,
                "utilization_bp must not exceed 10000 (clamp before "
                "constructing a reading)",
            )
        if self.level not in PressureLevel.values():
            raise EdgeError(
                EdgeReasonCode.INVALID_INPUT,
                "pressure level must be one of %s" % (PressureLevel.values(),),
            )

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "used": self.used,
            "capacity": self.capacity,
            "utilization_bp": self.utilization_bp,
            "level": self.level,
        }

    @classmethod
    def from_dict(cls, data: object) -> "PressureReading":
        if not isinstance(data, Mapping):
            raise EdgeError(
                EdgeReasonCode.INVALID_INPUT,
                "pressure reading must be a mapping",
            )
        return cls(
            domain=data.get("domain", ""),
            used=data.get("used", 0),
            capacity=data.get("capacity", 0),
            utilization_bp=data.get("utilization_bp", 0),
            level=data.get("level", ""),
        )


# ----------------------------------------------------------------------
# Edge events
# ----------------------------------------------------------------------


def derive_edge_event_id(
    kind: str, sequence: int, instant: str, subject: str, detail: str, ref: str
) -> str:
    """Derive the deterministic event id (sha256 over the canonical
    event identity; the WORK-033 ``derive_agent_event_id``
    discipline)."""
    payload = canonical_json_bytes(
        {
            "kind": kind,
            "sequence": sequence,
            "instant": instant,
            "subject": subject,
            "detail": detail,
            "ref": ref,
        }
    )
    return "sha256:" + hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class EdgeEvent:
    """One append-only edge-layer decision record."""

    kind: str
    sequence: int
    instant: str
    subject: str = ""
    detail: str = ""
    ref: str = ""
    event_id: str = ""

    def __post_init__(self) -> None:
        if self.kind not in EdgeEventType.values():
            raise EdgeError(
                EdgeReasonCode.INVALID_INPUT,
                "edge event kind %r not in the frozen vocabulary" % (self.kind,),
            )
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int):
            raise EdgeError(
                EdgeReasonCode.INVALID_INPUT,
                "event sequence must be an integer",
            )
        if self.sequence < 1:
            raise EdgeError(
                EdgeReasonCode.INVALID_INPUT,
                "event sequence must be >= 1",
            )
        if not self.instant:
            raise EdgeError(
                EdgeReasonCode.INVALID_INPUT,
                "event instant must be a non-empty RFC 3339 string",
            )
        object.__setattr__(
            self,
            "event_id",
            derive_edge_event_id(
                self.kind, self.sequence, self.instant, self.subject, self.detail,
                self.ref,
            ),
        )

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "sequence": self.sequence,
            "instant": self.instant,
            "subject": self.subject,
            "detail": self.detail,
            "ref": self.ref,
            "event_id": self.event_id,
        }

    @classmethod
    def from_dict(cls, data: object) -> "EdgeEvent":
        if not isinstance(data, Mapping):
            raise EdgeError(
                EdgeReasonCode.INVALID_INPUT,
                "edge event must be a mapping",
            )
        return cls(
            kind=data.get("kind", ""),
            sequence=data.get("sequence", 0),
            instant=data.get("instant", ""),
            subject=data.get("subject", ""),
            detail=data.get("detail", ""),
            ref=data.get("ref", ""),
        )


def edge_events_canonical_bytes(events: Tuple[EdgeEvent, ...]) -> bytes:
    """The canonical byte encoding of an edge event list (sorted by
    construction order; identical scenarios produce identical
    bytes)."""
    return canonical_json_bytes(
        {"events": [event.to_dict() for event in events]}
    )


def edge_event_list_digest(events: Tuple[EdgeEvent, ...]) -> str:
    return "sha256:" + hashlib.sha256(edge_events_canonical_bytes(events)).hexdigest()


# ----------------------------------------------------------------------
# Scheduling records
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class SchedulerDecision:
    """The deterministic admission decision for one command."""

    verdict: str
    reason: str = ""
    priority: str = ""

    def __post_init__(self) -> None:
        if self.verdict not in SchedulingVerdict.values():
            raise EdgeError(
                EdgeReasonCode.INVALID_INPUT,
                "scheduling verdict %r not in the frozen vocabulary"
                % (self.verdict,),
            )
        if self.priority and self.priority not in CommandPriority.values():
            raise EdgeError(
                EdgeReasonCode.INVALID_INPUT,
                "command priority %r not in the frozen vocabulary"
                % (self.priority,),
            )


@dataclass(frozen=True)
class EdgeOutcome:
    """What the edge layer did with one command: EXECUTED (the agent
    ran it -- the agent's own verdict is carried in
    ``agent_verdict``), DEFERRED (queued for a later drain), or SHED
    (dropped with a typed reason; never silent)."""

    command_id: str
    kind: str
    verdict: str
    reason: str = ""
    agent_verdict: str = ""
    detail: str = ""

    def __post_init__(self) -> None:
        if self.verdict not in SchedulingVerdict.values():
            raise EdgeError(
                EdgeReasonCode.INVALID_INPUT,
                "edge outcome verdict %r not in the frozen vocabulary"
                % (self.verdict,),
            )
        if not self.command_id:
            raise EdgeError(
                EdgeReasonCode.INVALID_INPUT,
                "edge outcome requires a command id",
            )

    def to_dict(self) -> dict:
        return {
            "command_id": self.command_id,
            "kind": self.kind,
            "verdict": self.verdict,
            "reason": self.reason,
            "agent_verdict": self.agent_verdict,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, data: object) -> "EdgeOutcome":
        if not isinstance(data, Mapping):
            raise EdgeError(
                EdgeReasonCode.INVALID_INPUT,
                "edge outcome must be a mapping",
            )
        return cls(
            command_id=data.get("command_id", ""),
            kind=data.get("kind", ""),
            verdict=data.get("verdict", ""),
            reason=data.get("reason", ""),
            agent_verdict=data.get("agent_verdict", ""),
            detail=data.get("detail", ""),
        )


@dataclass(frozen=True)
class EdgeRunResult:
    """The deterministic result of one edge scheduling epoch: the
    agent's own counters, the edge verdicts, the final pressure and
    posture, and the digests that make the whole scenario
    replayable."""

    status: str
    applied: int
    rejected: int
    failed: int
    executed: int
    deferred: int
    shed: int
    outcomes: Tuple[EdgeOutcome, ...] = ()
    pressure: Tuple[PressureReading, ...] = ()
    posture: str = ""
    deferred_depth: int = 0
    agent_trace_digest: str = ""
    edge_event_digest: str = ""
    edge_digest: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "applied": self.applied,
            "rejected": self.rejected,
            "failed": self.failed,
            "executed": self.executed,
            "deferred": self.deferred,
            "shed": self.shed,
            "outcomes": [outcome.to_dict() for outcome in self.outcomes],
            "pressure": [reading.to_dict() for reading in self.pressure],
            "posture": self.posture,
            "deferred_depth": self.deferred_depth,
            "agent_trace_digest": self.agent_trace_digest,
            "edge_event_digest": self.edge_event_digest,
            "edge_digest": self.edge_digest,
        }


@dataclass(frozen=True)
class ForwardRecord:
    """One gateway forwarding decision record: the evidenced claim
    used, the relay classification, and the payload digest (payload
    CONTENT is digested, never copied into the record)."""

    destination_node_id: str
    session_id: str
    payload_digest: str
    instant: str
    claim_ref: str
    evidence_class: str
    relay_technology: str

    def to_dict(self) -> dict:
        return {
            "destination_node_id": self.destination_node_id,
            "session_id": self.session_id,
            "payload_digest": self.payload_digest,
            "instant": self.instant,
            "claim_ref": self.claim_ref,
            "evidence_class": self.evidence_class,
            "relay_technology": self.relay_technology,
        }


__all__ = [
    "PressureDomain",
    "PressureLevel",
    "PRESSURE_LEVEL_ORDINALS",
    "worse_pressure_level",
    "ConnectivityPosture",
    "CommandPriority",
    "SchedulingVerdict",
    "EdgeEventType",
    "PressureReading",
    "derive_edge_event_id",
    "EdgeEvent",
    "edge_events_canonical_bytes",
    "edge_event_list_digest",
    "SchedulerDecision",
    "EdgeOutcome",
    "EdgeRunResult",
    "ForwardRecord",
]
