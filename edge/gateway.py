"""WORK-034 Pi-class edge gateway: the composition layer.

``EdgeGateway`` owns exactly one WORK-033 ``AgentRuntime`` and adds
what a Raspberry-Pi-class infrastructure node needs ON TOP of it:

- **resource-aware operation** -- every command batch is one
  scheduling epoch: the deterministic pressure model
  (:mod:`edge.pressure`) classifies CPU/memory/storage pressure, the
  scheduler (:mod:`edge.scheduler`) admits, defers, or sheds each
  command with typed reasons, and executed commands run through the
  UNCHANGED ``AgentRuntime.execute`` path (no agent semantics are
  re-implemented, patched, or shadowed);
- **coexistence** -- the gateway's access views
  (:mod:`edge.coexistence`) join the agent's interface snapshots with
  the live adapter lifecycle/health, classify Ethernet / Wi-Fi /
  cellular, select binding targets deterministically, and expose the
  connected / degraded / offline posture (failover keeps the node
  operating on the remaining classes);
- **gateway/relay behavior** -- an evidence-scoped gateway-claim
  table maps destinations to established sessions, reusing the
  WORK-023 evidence vocabulary (``direct-observation`` /
  ``remote-claim``) and relay-technology classification as DATA;
  forwarding goes through the ordinary session datagram path and
  fails closed on unknown, expired, or under-evidenced claims (a
  ``remote-claim`` never satisfies the forwarding requirement -- no
  upgrade path, LOCK-008 discipline);
- **offline/degraded operation** -- bulk relay defers while offline
  into a bounded, TTL'd queue that drains when an access path
  returns; monitoring, negotiation, and self-verification keep
  running;
- **hardware abstraction** -- the Pi-class board profile and hardware
  inventory (:mod:`edge.hardware`) size the pressure envelopes.

The agent runtime's authorities, event log, and trace digests remain
the single record of protocol state; the edge layer adds its own
append-only decision journal (:class:`EdgeEvent`) and digests, so a
whole edge scenario is one deterministic, replayable value.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from adapters.mesh import EvidenceSourceClass, RelayTechnology
from agent import (
    AgentClock,
    AgentCommand,
    AgentConfig,
    AgentError,
    AgentRuntime,
    InterfaceSource,
)
from agent.clock import add_seconds, parse_utc
from protocol.canonicalization import canonical_json_bytes
from telemetry import (
    TelemetryObservation,
    TelemetrySourceClass,
    TelemetrySubjectKind,
)

from .coexistence import (
    AccessView,
    build_access_views,
    connectivity_posture,
    select_access,
    validate_access_plan,
)
from .errors import EdgeError, EdgeReasonCode
from .hardware import (
    HardwareInventory,
    HardwareInventorySource,
)
from .model import (
    CommandPriority,
    ConnectivityPosture,
    EdgeEvent,
    EdgeEventType,
    EdgeOutcome,
    EdgeRunResult,
    ForwardRecord,
    PressureLevel,
    PressureReading,
    SchedulingVerdict,
    edge_event_list_digest,
    worse_pressure_level,
)
from .pressure import (
    PressureLedger,
    ResourceBudget,
    command_cpu_charge,
    command_memory_estimate,
    command_storage_estimate,
    compute_pressure,
)
from .scheduler import decide_command, priority_for_kind

#: Forwarding requires a DIRECTLY observed claim; a remote-claim
#: entry may sit in the table but never satisfies forwarding (no
#: upgrade path -- the WORK-023 LOCK-008 discipline).
FORWARD_EVIDENCE_REQUIREMENT = EvidenceSourceClass.DIRECT_OBSERVATION

#: The pressure-telemetry provenance label (MODELED pressure, never
#: a host measurement).
PRESSURE_PROVENANCE = "edge:modeled-pressure"

_DETAIL_LIMIT = 200


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


# ----------------------------------------------------------------------
# Gateway claims
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class GatewayClaim:
    """One evidenced gateway-forwarding claim: traffic for
    ``destination_node_id`` leaves through the established
    ``session_id``, classified by the WORK-023 relay vocabulary and
    carrying the WORK-023 evidence class of the claim's origin."""

    destination_node_id: str
    session_id: str
    evidence_class: str
    relay_technology: str
    issued_at: str
    expires_at: str
    claim_ref: str = ""

    def __post_init__(self) -> None:
        for name in ("destination_node_id", "session_id"):
            if not isinstance(getattr(self, name), str) \
                    or not getattr(self, name):
                raise EdgeError(
                    EdgeReasonCode.CLAIM_INVALID,
                    "gateway claim requires a non-empty %s" % (name,),
                )
        if self.evidence_class not in EvidenceSourceClass.values():
            raise EdgeError(
                EdgeReasonCode.CLAIM_INVALID,
                "evidence class %r not in the WORK-023 vocabulary"
                % (self.evidence_class,),
            )
        if self.relay_technology not in RelayTechnology.values():
            raise EdgeError(
                EdgeReasonCode.CLAIM_INVALID,
                "relay technology %r not in the WORK-023 vocabulary"
                % (self.relay_technology,),
            )
        try:
            issued = parse_utc(self.issued_at)
            expires = parse_utc(self.expires_at)
        except ValueError as error:
            raise EdgeError(
                EdgeReasonCode.CLAIM_INVALID,
                "claim instants must be RFC 3339 UTC strings: %s" % (error,),
            ) from error
        if expires <= issued:
            raise EdgeError(
                EdgeReasonCode.CLAIM_INVALID,
                "claim expiry (%s) must be after issuance (%s)"
                % (self.expires_at, self.issued_at),
            )
        if not self.claim_ref:
            payload = canonical_json_bytes(
                {
                    "destination_node_id": self.destination_node_id,
                    "session_id": self.session_id,
                    "evidence_class": self.evidence_class,
                    "relay_technology": self.relay_technology,
                    "issued_at": self.issued_at,
                    "expires_at": self.expires_at,
                }
            )
            object.__setattr__(
                self, "claim_ref", "edge-claim:" + _sha256_hex(payload)[:16],
            )

    def to_dict(self) -> dict:
        return {
            "destination_node_id": self.destination_node_id,
            "session_id": self.session_id,
            "evidence_class": self.evidence_class,
            "relay_technology": self.relay_technology,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "claim_ref": self.claim_ref,
        }


class ClaimLookup:
    """The result of a gateway-table lookup: the claim (when present)
    plus a frozen status -- ``ok``, ``unknown``, ``expired``, or
    ``evidence-insufficient``."""

    __slots__ = ("claim", "status")

    def __init__(self, claim: Optional[GatewayClaim], status: str) -> None:
        self.claim = claim
        self.status = status


class GatewayTable:
    """The evidence-scoped destination -> session table.

    The table is deployment DATA with evidence discipline: entries
    carry the WORK-023 evidence class of their origin, expiry is
    explicit and enforced at lookup time (expired entries are pruned,
    never silently used), and a claim whose evidence class does not
    meet the frozen forwarding requirement fails closed.
    """

    def __init__(self) -> None:
        self._claims: Dict[str, GatewayClaim] = {}

    def add(self, claim: GatewayClaim) -> str:
        """Add (or idempotently re-add) a claim; a different claim
        for the same destination REPLACES it (the operator's latest
        evidenced claim wins -- replacement, never merging)."""
        if not isinstance(claim, GatewayClaim):
            raise EdgeError(
                EdgeReasonCode.INVALID_INPUT,
                "gateway table requires a genuine GatewayClaim",
            )
        self._claims[claim.destination_node_id] = claim
        return claim.claim_ref

    def lookup(self, destination_node_id: str, *, now: str) -> ClaimLookup:
        """Look up the forwarding claim for a destination at an
        explicit instant (fail closed)."""
        claim = self._claims.get(destination_node_id)
        if claim is None:
            return ClaimLookup(None, "unknown")
        if parse_utc(now) >= parse_utc(claim.expires_at):
            del self._claims[destination_node_id]
            return ClaimLookup(claim, "expired")
        if claim.evidence_class != FORWARD_EVIDENCE_REQUIREMENT:
            return ClaimLookup(claim, "evidence-insufficient")
        return ClaimLookup(claim, "ok")

    def claims(self) -> Tuple[GatewayClaim, ...]:
        return tuple(
            self._claims[key] for key in sorted(self._claims)
        )

    def __len__(self) -> int:
        return len(self._claims)


@dataclass(frozen=True)
class _DeferredCommand:
    """One queued command waiting for capacity or an access path."""

    command: AgentCommand
    deferred_at: str
    reason: str


# ----------------------------------------------------------------------
# The edge gateway
# ----------------------------------------------------------------------


class EdgeGateway:
    """The Pi-class edge composition over one ``AgentRuntime``."""

    def __init__(
        self,
        *,
        config: AgentConfig,
        clock: AgentClock,
        interface_source: InterfaceSource,
        hardware_source: HardwareInventorySource,
        budget: Optional[ResourceBudget] = None,
        access_plan: Mapping[str, str] = {},
        claims: Sequence[GatewayClaim] = (),
    ) -> None:
        if not isinstance(config, AgentConfig):
            raise EdgeError(
                EdgeReasonCode.INVALID_INPUT,
                "edge gateway requires a genuine AgentConfig",
            )
        if not isinstance(clock, AgentClock):
            raise EdgeError(
                EdgeReasonCode.INVALID_INPUT,
                "edge gateway requires a genuine AgentClock (injected time)",
            )
        if not isinstance(interface_source, InterfaceSource):
            raise EdgeError(
                EdgeReasonCode.INVALID_INPUT,
                "edge gateway requires a genuine InterfaceSource",
            )
        if not isinstance(hardware_source, HardwareInventorySource):
            raise EdgeError(
                EdgeReasonCode.INVALID_INPUT,
                "edge gateway requires a genuine HardwareInventorySource",
            )
        if budget is None:
            budget = ResourceBudget()
        if not isinstance(budget, ResourceBudget):
            raise EdgeError(
                EdgeReasonCode.BUDGET_INVALID,
                "budget must be a genuine ResourceBudget",
            )
        validate_access_plan(access_plan)
        self._runtime = AgentRuntime(
            config, clock=clock, interface_source=interface_source,
        )
        self._clock = clock
        self._budget = budget
        self._access_plan: Dict[str, str] = dict(access_plan)
        self._hardware_source = hardware_source
        try:
            self._inventory = hardware_source.read()
        except EdgeError:
            raise
        except Exception as error:  # fail closed, class name only
            raise EdgeError(
                EdgeReasonCode.HARDWARE_SOURCE_FAILED,
                "hardware source failed: %s" % (type(error).__name__,),
            ) from error
        if not isinstance(self._inventory, HardwareInventory):
            raise EdgeError(
                EdgeReasonCode.HARDWARE_SOURCE_FAILED,
                "hardware source returned a non-inventory %r"
                % (type(self._inventory).__name__,),
            )
        self._ledger = PressureLedger()
        self._events: List[EdgeEvent] = []
        self._event_sequence = 0
        self._queue: List[_DeferredCommand] = []
        self._posture = ConnectivityPosture.OFFLINE
        self._views: Tuple[AccessView, ...] = ()
        self._table = GatewayTable()
        self._last_pressure_level = PressureLevel.NOMINAL
        self._telemetry_sequences: Dict[str, int] = {}
        for claim in claims:
            self._table.add(claim)

    # -- read-only surfaces ------------------------------------------------

    @property
    def runtime(self) -> AgentRuntime:
        return self._runtime

    @property
    def inventory(self) -> HardwareInventory:
        return self._inventory

    @property
    def budget(self) -> ResourceBudget:
        return self._budget

    @property
    def posture(self) -> str:
        return self._posture

    @property
    def deferred_depth(self) -> int:
        return len(self._queue)

    @property
    def access_plan(self) -> Mapping[str, str]:
        return dict(self._access_plan)

    def access_views(self) -> Tuple[AccessView, ...]:
        return self._views

    def claims(self) -> Tuple[GatewayClaim, ...]:
        return self._table.claims()

    def edge_events(self) -> Tuple[EdgeEvent, ...]:
        return tuple(self._events)

    def edge_event_digest(self) -> str:
        return edge_event_list_digest(tuple(self._events))

    def pressure(self) -> Tuple[PressureReading, ...]:
        return compute_pressure(self._inventory, self._ledger, self._budget)

    def pressure_level(self) -> str:
        return worse_pressure_level(
            tuple(reading.level for reading in self.pressure())
        )

    def edge_snapshot(self) -> Dict[str, Any]:
        return {
            "posture": self._posture,
            "pressure": [
                reading.to_dict() for reading in self.pressure()
            ],
            "pressure_level": self.pressure_level(),
            "deferred_depth": len(self._queue),
            "ledger": self._ledger.to_dict(),
            "claim_count": len(self._table),
            "edge_event_digest": self.edge_event_digest(),
        }

    def content_digest(self) -> str:
        payload = canonical_json_bytes(
            {
                "edge": self.edge_snapshot(),
                "agent": self._runtime.snapshot(),
            }
        )
        return "sha256:" + _sha256_hex(payload)

    # -- event journal ------------------------------------------------------

    def _record_event(
        self, kind: str, instant: str, *, subject: str = "",
        detail: str = "", ref: str = "",
    ) -> None:
        self._event_sequence += 1
        self._events.append(
            EdgeEvent(
                kind=kind,
                sequence=self._event_sequence,
                instant=instant,
                subject=subject,
                detail=detail[:_DETAIL_LIMIT],
                ref=ref,
            )
        )

    # -- hardware / pressure hooks ------------------------------------------

    def refresh_hardware(self) -> HardwareInventory:
        """Re-read the hardware inventory (dynamic memory/storage
        availability); pressure recomputes against the new envelope
        on the next observation."""
        try:
            inventory = self._hardware_source.read()
        except EdgeError:
            raise
        except Exception as error:  # fail closed, class name only
            raise EdgeError(
                EdgeReasonCode.HARDWARE_SOURCE_FAILED,
                "hardware source failed: %s" % (type(error).__name__,),
            ) from error
        if not isinstance(inventory, HardwareInventory):
            raise EdgeError(
                EdgeReasonCode.HARDWARE_SOURCE_FAILED,
                "hardware source returned a non-inventory %r"
                % (type(inventory).__name__,),
            )
        self._inventory = inventory
        return inventory

    def reclaim_memory(self, size_bytes: int, *, now: str = "") -> int:
        """Reclaim modeled memory (deployment-level release)."""
        instant = now or self._clock.now()
        reclaimed = self._ledger.reclaim_memory(size_bytes)
        self._record_event(
            EdgeEventType.MEMORY_RECLAIMED, instant,
            subject="edge-pressure:memory",
            detail="reclaimed %d bytes" % (reclaimed,),
        )
        self._maybe_pressure_event(instant)
        return reclaimed

    def compact_storage(self, size_bytes: int, *, now: str = "") -> int:
        """Compact modeled journal growth (deployment-level)."""
        instant = now or self._clock.now()
        released = self._ledger.compact_storage(size_bytes)
        self._record_event(
            EdgeEventType.STORAGE_COMPACTED, instant,
            subject="edge-pressure:storage",
            detail="released %d bytes" % (released,),
        )
        self._maybe_pressure_event(instant)
        return released

    def _maybe_pressure_event(self, instant: str) -> None:
        level = self.pressure_level()
        if level != self._last_pressure_level:
            self._record_event(
                EdgeEventType.PRESSURE_LEVEL_CHANGED, instant,
                subject="edge-pressure",
                detail="%s->%s" % (self._last_pressure_level, level),
            )
            self._last_pressure_level = level

    def observe_pressure(
        self, *, record: bool = True, now: str = ""
    ) -> Tuple[PressureReading, ...]:
        """Observe (and optionally record) the modeled pressure.

        Recorded observations are genuine WORK-026 telemetry: subject
        RESOURCE, metric ``utilization-bp``, source class
        SELF_ADVERTISED, provenance ``edge:modeled-pressure`` (the
        MODELED label is explicit -- these are scheduler-model
        readings, never host measurements).
        """
        instant = now or self._clock.now()
        readings = self.pressure()
        self._maybe_pressure_event(instant)
        if not record:
            return readings
        freshness = add_seconds(
            instant, self._runtime.config.telemetry_freshness_seconds,
        )
        for reading in readings:
            key = "edge-pressure:%s|utilization-bp" % (reading.domain,)
            sequence = self._telemetry_sequences.get(key, 0) + 1
            observation = TelemetryObservation(
                subject_kind=TelemetrySubjectKind.RESOURCE,
                subject_ref="edge-pressure:%s" % (reading.domain,),
                source_node_id=self._runtime.node_id,
                source_class=TelemetrySourceClass.SELF_ADVERTISED,
                metric="utilization-bp",
                value=reading.utilization_bp,
                confidence_basis_points=10000,
                observed_at=instant,
                freshness_until=freshness,
                sequence=sequence,
                provenance=PRESSURE_PROVENANCE,
            )
            self._runtime.telemetry.record_observation(
                observation, now=instant,
            )
            self._telemetry_sequences[key] = sequence
        return readings

    # -- access / coexistence ------------------------------------------------

    def _refresh_access(self, instant: str) -> None:
        """Recompute the access views and posture from the agent's
        own live state (read-only: discover + monitor(record=False)).

        Best-effort by design: a failing interface source surfaces
        through the agent's own typed command verdicts; the gateway
        keeps its previous views rather than inventing state.
        """
        if self._runtime.status != "online":
            return
        try:
            snapshots = self._runtime.interface_source.discover()
            report = self._runtime.monitor(record=False)
            adapter_interfaces = self._runtime.snapshot().get(
                "adapter_interfaces", {}
            )
        except (AgentError, OSError, ValueError):
            return
        views = build_access_views(
            snapshots,
            report.adapters,
            adapter_interfaces if isinstance(
                adapter_interfaces, Mapping
            ) else {},
            self._access_plan,
        )
        self._views = views
        posture = connectivity_posture(views)
        if posture != self._posture:
            self._posture = posture
            self._record_event(
                EdgeEventType.POSTURE_CHANGED, instant,
                subject="edge-access",
                detail="->%s" % (posture,),
            )

    def bind_access(
        self, session_id: str, *, required_class: str = "",
    ) -> Dict[str, str]:
        """Bind a session through the coexistence-selected access
        interface (the ordinary WORK-016/W018 agent binding path --
        only the interface CHOICE is the edge layer's)."""
        instant = self._clock.now()
        self._refresh_access(instant)
        view = select_access(self._views, required_class=required_class)
        if view is None:
            raise EdgeError(
                EdgeReasonCode.ACCESS_UNAVAILABLE,
                "no %scarriable access view (posture %s)"
                % (
                    "%s " % (required_class,) if required_class else "",
                    self._posture,
                ),
            )
        binding = self._runtime.bind_session(
            session_id, interface_name=view.interface_name,
        )
        self._record_event(
            EdgeEventType.ACCESS_SELECTED, instant,
            subject=view.interface_name,
            detail=view.access_class,
            ref=str(binding.get("binding_id", "")),
        )
        result: Dict[str, str] = {
            key: str(value) for key, value in binding.items()
        }
        result["interface_name"] = view.interface_name
        result["access_class"] = view.access_class
        return result

    # -- gateway claims / forwarding ------------------------------------------

    def add_claim(self, claim: GatewayClaim) -> str:
        """Add an evidenced gateway claim (records the addition)."""
        instant = self._clock.now()
        claim_ref = self._table.add(claim)
        self._record_event(
            EdgeEventType.CLAIM_ADDED, instant,
            subject=claim.destination_node_id,
            detail=claim.evidence_class,
            ref=claim.claim_ref,
        )
        return claim_ref

    def forward(
        self, destination_node_id: str, payload: bytes, *, now: str = "",
    ) -> ForwardRecord:
        """Forward a payload for a destination through the evidenced
        claim's session (the ordinary WORK-012/W017 datagram path).

        Fails closed on unknown, expired, or under-evidenced claims;
        payload CONTENT is digested, never copied into the record.
        """
        if not isinstance(payload, (bytes, bytearray)):
            raise EdgeError(
                EdgeReasonCode.INVALID_INPUT,
                "forward payload must be bytes",
            )
        instant = now or self._clock.now()
        lookup = self._table.lookup(destination_node_id, now=instant)
        if lookup.status == "expired":
            self._record_event(
                EdgeEventType.CLAIM_EXPIRED, instant,
                subject=destination_node_id,
                ref=lookup.claim.claim_ref if lookup.claim else "",
            )
        if lookup.status != "ok" or lookup.claim is None:
            self._record_event(
                EdgeEventType.GATEWAY_FORWARD_REJECTED, instant,
                subject=destination_node_id,
                detail=lookup.status,
            )
            raise EdgeError(
                EdgeReasonCode.CLAIM_REJECTED,
                "gateway claim lookup %s for destination %s"
                % (lookup.status, destination_node_id),
            )
        claim = lookup.claim
        try:
            self._runtime.send_datagram(claim.session_id, bytes(payload))
        except AgentError as error:
            self._record_event(
                EdgeEventType.GATEWAY_FORWARD_REJECTED, instant,
                subject=destination_node_id,
                detail="%s:%s" % (lookup.status, error.reason),
                ref=claim.claim_ref,
            )
            raise EdgeError(
                EdgeReasonCode.FORWARD_REJECTED,
                "session send failed: %s" % (error.reason,),
            ) from error
        record = ForwardRecord(
            destination_node_id=destination_node_id,
            session_id=claim.session_id,
            payload_digest="sha256:" + _sha256_hex(bytes(payload)),
            instant=instant,
            claim_ref=claim.claim_ref,
            evidence_class=claim.evidence_class,
            relay_technology=claim.relay_technology,
        )
        self._record_event(
            EdgeEventType.GATEWAY_FORWARDED, instant,
            subject=destination_node_id,
            detail=claim.relay_technology,
            ref=claim.claim_ref,
        )
        return record

    # -- scheduling -----------------------------------------------------------

    def _cpu_steps_remaining(self) -> int:
        remaining = self._budget.cpu_steps_per_epoch \
            - self._ledger.cpu_steps_used
        return remaining if remaining > 0 else 0

    def _execute_one(
        self, command: AgentCommand, *, boot_secret: Optional[bytes],
    ) -> EdgeOutcome:
        agent_result = self._runtime.execute(
            (command,), boot_secret=boot_secret,
        )
        agent_outcome = agent_result.outcomes[0]
        self._ledger.charge_cpu(command_cpu_charge(command.kind))
        self._ledger.charge_memory(command_memory_estimate(command.kind))
        self._ledger.charge_storage(command_storage_estimate(command.kind))
        return EdgeOutcome(
            command_id=command.command_id,
            kind=command.kind,
            verdict=SchedulingVerdict.EXECUTED,
            reason="",
            agent_verdict=agent_outcome.verdict,
            detail=agent_outcome.detail[:_DETAIL_LIMIT],
        )

    def _enqueue(
        self, command: AgentCommand, instant: str, reason: str,
    ) -> List[EdgeOutcome]:
        """Queue a deferred command; shed oldest (bulk first) when
        the queue would exceed its bound.  Returns the shed outcome
        records (never silent)."""
        self._queue.append(_DeferredCommand(command, instant, reason))
        self._record_event(
            EdgeEventType.COMMAND_DEFERRED, instant,
            subject=command.kind,
            detail=reason,
            ref=command.command_id,
        )
        shed_outcomes: List[EdgeOutcome] = []
        while len(self._queue) > self._budget.max_deferred_depth:
            victim_index = 0
            for index, entry in enumerate(self._queue):
                if priority_for_kind(entry.command.kind) == CommandPriority.BULK:
                    victim_index = index
                    break
            victim = self._queue.pop(victim_index)
            self._record_event(
                EdgeEventType.COMMAND_SHED, instant,
                subject=victim.command.kind,
                detail="deferred-queue-overflow",
                ref=victim.command.command_id,
            )
            shed_outcomes.append(
                EdgeOutcome(
                    command_id=victim.command.command_id,
                    kind=victim.command.kind,
                    verdict=SchedulingVerdict.SHED,
                    reason="deferred-queue-overflow",
                )
            )
        return shed_outcomes

    def _deferred_expired(self, deferred_at: str, instant: str) -> bool:
        expires = parse_utc(deferred_at) + timedelta(
            seconds=self._budget.deferred_ttl_seconds,
        )
        return parse_utc(instant) >= expires

    def _drain_queue(
        self, instant: str, *, boot_secret: Optional[bytes] = None,
    ) -> List[EdgeOutcome]:
        """Attempt to drain the deferred queue at an explicit
        instant: TTL-expired entries are shed; entries the scheduler
        now admits are executed; the rest stay queued (their original
        deferred-at is kept, so the TTL keeps aging)."""
        outcomes: List[EdgeOutcome] = []
        if not self._queue:
            return outcomes
        kept: List[_DeferredCommand] = []
        for entry in self._queue:
            if self._deferred_expired(entry.deferred_at, instant):
                self._record_event(
                    EdgeEventType.COMMAND_SHED, instant,
                    subject=entry.command.kind,
                    detail="deferred-ttl-expired",
                    ref=entry.command.command_id,
                )
                outcomes.append(
                    EdgeOutcome(
                        command_id=entry.command.command_id,
                        kind=entry.command.kind,
                        verdict=SchedulingVerdict.SHED,
                        reason="deferred-ttl-expired",
                    )
                )
                continue
            level = self.pressure_level()
            decision = decide_command(
                entry.command.kind,
                pressure_level_now=level,
                posture=self._posture,
                cpu_steps_remaining=self._cpu_steps_remaining(),
                cpu_charge=command_cpu_charge(entry.command.kind),
            )
            if decision.verdict == SchedulingVerdict.EXECUTED:
                outcome = self._execute_one(
                    entry.command, boot_secret=boot_secret,
                )
                self._record_event(
                    EdgeEventType.DEFERRED_DRAINED, instant,
                    subject=entry.command.kind,
                    detail=entry.reason,
                    ref=entry.command.command_id,
                )
                outcomes.append(outcome)
            else:
                kept.append(entry)
        self._queue = kept
        return outcomes

    def drain(self, *, boot_secret: Optional[bytes] = None) -> List[EdgeOutcome]:
        """Public drain hook (data-driven recovery)."""
        instant = self._clock.now()
        self._refresh_access(instant)
        return self._drain_queue(instant, boot_secret=boot_secret)

    def run_edge(
        self,
        commands: Sequence[AgentCommand],
        *,
        boot_secret: Optional[bytes] = None,
    ) -> EdgeRunResult:
        """Execute one scheduling epoch over a command batch.

        Deterministic order: epoch replenishment, access/posture
        refresh, deferred-queue drain, then per-command admission
        (offline gate -> priority -> cpu budget -> pressure matrix)
        with execution through the unchanged agent path.  Every
        decision is recorded; nothing is dropped silently.
        """
        instant = self._clock.now()
        self._ledger.replenish_epoch()
        self._refresh_access(instant)
        outcomes: List[EdgeOutcome] = list(
            self._drain_queue(instant, boot_secret=boot_secret)
        )
        applied = rejected = failed = 0
        executed = deferred = shed = 0
        for command in commands:
            if not isinstance(command, AgentCommand):
                raise EdgeError(
                    EdgeReasonCode.INVALID_INPUT,
                    "run_edge requires genuine AgentCommand values",
                )
            level = self.pressure_level()
            decision = decide_command(
                command.kind,
                pressure_level_now=level,
                posture=self._posture,
                cpu_steps_remaining=self._cpu_steps_remaining(),
                cpu_charge=command_cpu_charge(command.kind),
            )
            if decision.verdict == SchedulingVerdict.EXECUTED:
                outcome = self._execute_one(command, boot_secret=boot_secret)
                outcomes.append(outcome)
                executed += 1
                if outcome.agent_verdict == "applied":
                    applied += 1
                elif outcome.agent_verdict == "rejected":
                    rejected += 1
                else:
                    failed += 1
                if command.kind == "expose-interfaces":
                    self._refresh_access(instant)
                self._maybe_pressure_event(instant)
            elif decision.verdict == SchedulingVerdict.DEFERRED:
                shed_outcomes = self._enqueue(
                    command, instant, decision.reason,
                )
                outcomes.append(
                    EdgeOutcome(
                        command_id=command.command_id,
                        kind=command.kind,
                        verdict=SchedulingVerdict.DEFERRED,
                        reason=decision.reason,
                    )
                )
                outcomes.extend(shed_outcomes)
                deferred += 1
                shed += len(shed_outcomes)
            else:  # SHED directly from the scheduler (never silent)
                self._record_event(
                    EdgeEventType.COMMAND_SHED, instant,
                    subject=command.kind,
                    detail=decision.reason,
                    ref=command.command_id,
                )
                outcomes.append(
                    EdgeOutcome(
                        command_id=command.command_id,
                        kind=command.kind,
                        verdict=SchedulingVerdict.SHED,
                        reason=decision.reason,
                    )
                )
                shed += 1
        readings = self.pressure()
        payload = EdgeRunResult(
            status=self._runtime.status,
            applied=applied,
            rejected=rejected,
            failed=failed,
            executed=executed,
            deferred=deferred,
            shed=shed,
            outcomes=tuple(outcomes),
            pressure=readings,
            posture=self._posture,
            deferred_depth=len(self._queue),
            agent_trace_digest=self._runtime.event_log_digest(),
            edge_event_digest=self.edge_event_digest(),
        )
        payload_dict = payload.to_dict()
        object.__setattr__(
            payload,
            "edge_digest",
            "sha256:" + _sha256_hex(canonical_json_bytes(payload_dict)),
        )
        return payload


# ----------------------------------------------------------------------
# Headless entry points
# ----------------------------------------------------------------------


def run_edge_headless(
    config: AgentConfig,
    commands: Sequence[AgentCommand],
    *,
    clock: AgentClock,
    interface_source: InterfaceSource,
    hardware_source: HardwareInventorySource,
    boot_secret: Optional[bytes] = None,
    budget: Optional[ResourceBudget] = None,
    access_plan: Mapping[str, str] = {},
    claims: Sequence[GatewayClaim] = (),
) -> EdgeRunResult:
    """Construct an edge gateway and run one scheduling epoch (the
    WORK-033 ``run_headless`` discipline: everything is data + an
    injected clock)."""
    gateway = EdgeGateway(
        config=config,
        clock=clock,
        interface_source=interface_source,
        hardware_source=hardware_source,
        budget=budget,
        access_plan=access_plan,
        claims=claims,
    )
    return gateway.run_edge(commands, boot_secret=boot_secret)


def verify_edge_replay(
    config: AgentConfig,
    commands: Sequence[AgentCommand],
    *,
    clock_factory: Callable[[], AgentClock],
    interface_source_factory: Callable[[], InterfaceSource],
    hardware_source_factory: Callable[[], HardwareInventorySource],
    boot_secret: Optional[bytes] = None,
    budget: Optional[ResourceBudget] = None,
    access_plan: Mapping[str, str] = {},
    claims: Sequence[GatewayClaim] = (),
    expected_edge_digest: str = "",
) -> Tuple[bool, str]:
    """Re-run an edge scenario with fresh factories; the whole
    scenario digest must reproduce byte-identically or the replay
    fails closed."""
    result = run_edge_headless(
        config,
        commands,
        clock=clock_factory(),
        interface_source=interface_source_factory(),
        hardware_source=hardware_source_factory(),
        boot_secret=boot_secret,
        budget=budget,
        access_plan=access_plan,
        claims=claims,
    )
    if expected_edge_digest and result.edge_digest != expected_edge_digest:
        return (False, "edge digest diverged on replay")
    return (True, result.edge_digest)


__all__ = [
    "FORWARD_EVIDENCE_REQUIREMENT",
    "PRESSURE_PROVENANCE",
    "GatewayClaim",
    "ClaimLookup",
    "GatewayTable",
    "EdgeGateway",
    "run_edge_headless",
    "verify_edge_replay",
]
