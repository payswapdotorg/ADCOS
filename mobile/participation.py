"""WORK-035 mobile participation: the composition layer.

``MobileAgent`` owns exactly one WORK-033 ``AgentRuntime`` and adds
what a mobile node needs ON TOP of it:

- **lifecycle adaptation** -- the OS-reported application phase
  (foreground / background / stopped) and the platform snapshot
  (power, usable access, metering, background restrictions) are
  explicit inputs; the pure participation gate
  (:mod:`mobile.lifecycle`) decides what may run, and every
  adaptation is journaled -- never a hidden authority change;
- **user-controlled resource sharing** -- metered-data,
  background-data, and local-discovery consent grants are user INPUT
  (records with TTLs and explicit revocation); they mediate
  participation, they are not a policy or resource authority;
- **session continuity** -- tracked sessions survive access changes
  and offline periods with their ``session_id`` UNCHANGED (the sacred
  access-independent identity): an access change re-binds the session
  through the ordinary WORK-033 ``bind_session`` path (which flows
  through the WORK-016 adapter and WORK-018 IP-binding surfaces), and
  outgoing datagrams defer into a bounded TTL'd queue that drains
  when participation re-opens;
- **the continuity view** -- per tracked session, the layer keeps an
  access-path view over the frozen WORK-013 constituent-path status
  vocabulary, mutated only through the WORK-013 legal-status table
  (DATA consumption of the accepted public contract -- the multipath
  authority itself is never operated);
- **local discovery** -- a host-provided port (``mobile.discovery``)
  participates only with the user's local-discovery consent;
- **restart/recovery** -- a stop produces a durable secret-free
  snapshot (grants, deferred queue with aging TTLs, journal
  continuation); ``recover`` builds the successor process, records
  the session loss honestly, and continues the journal.

Executed commands flow through the UNCHANGED ``AgentRuntime``
surfaces; no agent semantic is re-implemented, patched, or shadowed.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from agent.clock import AgentClock, parse_utc
from agent.errors import AgentError
from agent.interfaces import InterfaceSource
from agent.model import AgentCommand, AgentConfig, CommandKind
from agent.runtime import AgentRuntime
from multipath import PathStatus, status_transition_is_legal
from protocol.canonicalization import canonical_json_bytes
from sessions import SessionState

from .discovery import LocalDiscoveryPort, NullDiscovery, PeerObservation
from .errors import MobileError, MobileReasonCode
from .lifecycle import grant_active, participation_gate, transition_is_legal
from .model import (
    AccessPathView,
    DeferReason,
    GrantScope,
    MobileEvent,
    MobileEventType,
    MobileOutcome,
    MobilePhase,
    MobileRunResult,
    MobileSnapshot,
    MobileVerdict,
    NetworkKind,
    ParticipationDecision,
    PlatformSnapshot,
    UserGrant,
    mobile_event_list_digest,
)
from .platform import MobilePlatformSource

# ----------------------------------------------------------------------
# Command model (data-driven participation)
# ----------------------------------------------------------------------


class MobileCommandKind:
    """The frozen mobile participation command vocabulary.

    Agent-level commands (boot, expose-interfaces, monitor,
    receive-datagram) pass through to the runtime's own dispatch;
    mobile-level operations (send with participation gating, session
    tracking, consent, discovery, checkpointing) are composed here.
    """

    BOOT = "boot"
    EXPOSE_INTERFACES = "expose-interfaces"
    SEND_DATAGRAM = "send-datagram"
    RECEIVE_DATAGRAM = "receive-datagram"
    TRACK_SESSION = "track-session"
    POLL_DISCOVERY = "poll-discovery"
    MONITOR = "monitor"
    GRANT = "grant"
    REVOKE_GRANT = "revoke-grant"
    CHECKPOINT = "checkpoint"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.BOOT,
            cls.EXPOSE_INTERFACES,
            cls.SEND_DATAGRAM,
            cls.RECEIVE_DATAGRAM,
            cls.TRACK_SESSION,
            cls.POLL_DISCOVERY,
            cls.MONITOR,
            cls.GRANT,
            cls.REVOKE_GRANT,
            cls.CHECKPOINT,
        )


#: The mobile command kinds that pass through to the runtime's own
#: command dispatch (the unchanged agent path).
_PASSTHROUGH_KINDS = frozenset({
    MobileCommandKind.BOOT,
    MobileCommandKind.EXPOSE_INTERFACES,
    MobileCommandKind.MONITOR,
    MobileCommandKind.RECEIVE_DATAGRAM,
})


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def derive_mobile_command_id(kind: str, params: Mapping[str, Any]) -> str:
    content = {"kind": kind, "params": dict(params)}
    return "sha256:" + _sha256_hex(canonical_json_bytes(content))


@dataclass(frozen=True)
class MobileCommand:
    """One data-driven mobile command: a kind plus DATA parameters."""

    kind: str
    params: Mapping[str, Any]
    command_id: str = ""

    def __post_init__(self) -> None:
        if self.kind not in MobileCommandKind.values():
            raise MobileError(
                MobileReasonCode.INVALID_INPUT,
                "unknown mobile command kind %r" % self.kind,
            )
        if not isinstance(self.params, Mapping):
            raise MobileError(
                MobileReasonCode.INVALID_INPUT,
                "command params must be a mapping",
            )
        object.__setattr__(
            self,
            "command_id",
            self.command_id or derive_mobile_command_id(self.kind, self.params),
        )

    def to_dict(self) -> dict:
        return {
            "command_id": self.command_id,
            "kind": self.kind,
            "params": dict(self.params),
        }


# ----------------------------------------------------------------------
# Budget and internal state
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class MobileBudget:
    """The deterministic participation budget: how long a deferred
    send may age and how deep the defer queue may grow before the
    oldest entry is shed (never silently)."""

    deferred_ttl_seconds: int = 300
    max_deferred_depth: int = 32

    def __post_init__(self) -> None:
        for name in ("deferred_ttl_seconds", "max_deferred_depth"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise MobileError(
                    MobileReasonCode.INVALID_INPUT,
                    "%s must be an integer" % name,
                )
            if value <= 0:
                raise MobileError(
                    MobileReasonCode.INVALID_INPUT,
                    "%s must be positive (got %d)" % (name, value),
                )


@dataclass(frozen=True)
class _DeferredSend:
    """One deferred outgoing datagram (payload digested into records,
    content kept only here for the eventual drain)."""

    session_id: str
    payload: bytes
    deferred_at: str
    reason: str

    def entry_dict(self) -> Dict[str, str]:
        return {
            "session_id": self.session_id,
            "payload_hex": self.payload.hex(),
            "deferred_at": self.deferred_at,
            "reason": self.reason,
        }


class _TrackedSession:
    """Mobile-layer continuity bookkeeping for ONE session (a VIEW --
    never a second session authority; the WORK-012 store remains the
    only lifecycle owner)."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.paths: Dict[str, AccessPathView] = {}
        #: The access this session was LAST attached to (sticky across
        #: access loss so the handover provenance survives outages).
        self.bound_access: str = ""
        #: Whether the session is CURRENTLY attached (False after the
        #: access went away; True again after the ordinary re-bind).
        self.attached: bool = False

    def apply_path_status(
        self, access_class: str, interface_name: str, new_status: str,
    ) -> None:
        """Mutate the access-path view ONLY through the frozen WORK-013
        legal-status table; a fresh access is a fresh ACTIVE entry
        (removal + re-add discipline for terminal FAILED paths)."""
        current = self.paths.get(access_class)
        if current is not None and current.status == new_status:
            return
        if current is not None:
            if not status_transition_is_legal(current.status, new_status):
                raise MobileError(
                    MobileReasonCode.INVALID_INPUT,
                    "access-path view transition %s -> %s for %s violates "
                    "the WORK-013 status table"
                    % (current.status, new_status, access_class),
                )
            self.paths[access_class] = AccessPathView(
                access_class=access_class,
                interface_name=interface_name,
                status=new_status,
            )
        else:
            if new_status != PathStatus.ACTIVE:
                raise MobileError(
                    MobileReasonCode.INVALID_INPUT,
                    "a fresh access-path view must start ACTIVE (got %r)"
                    % (new_status,),
                )
            self.paths[access_class] = AccessPathView(
                access_class=access_class,
                interface_name=interface_name,
                status=new_status,
            )

    def view_dicts(self) -> List[Dict[str, str]]:
        return [
            self.paths[key].to_dict()
            for key in sorted(self.paths)
        ]


# ----------------------------------------------------------------------
# The mobile agent
# ----------------------------------------------------------------------


class MobileAgent:
    """The mobile participation composition over one ``AgentRuntime``."""

    def __init__(
        self,
        *,
        config: AgentConfig,
        clock: AgentClock,
        interface_source: InterfaceSource,
        platform_source: MobilePlatformSource,
        discovery: Optional[LocalDiscoveryPort] = None,
        access_interfaces: Mapping[str, str] = {},
        budget: Optional[MobileBudget] = None,
    ) -> None:
        if not isinstance(config, AgentConfig):
            raise MobileError(
                MobileReasonCode.INVALID_INPUT,
                "mobile agent requires a genuine AgentConfig",
            )
        if not isinstance(clock, AgentClock):
            raise MobileError(
                MobileReasonCode.INVALID_INPUT,
                "mobile agent requires a genuine AgentClock (injected time)",
            )
        if not isinstance(interface_source, InterfaceSource):
            raise MobileError(
                MobileReasonCode.INVALID_INPUT,
                "mobile agent requires a genuine InterfaceSource",
            )
        if not isinstance(platform_source, MobilePlatformSource):
            raise MobileError(
                MobileReasonCode.INVALID_INPUT,
                "mobile agent requires a genuine MobilePlatformSource",
            )
        if discovery is None:
            discovery = NullDiscovery()
        if not isinstance(discovery, LocalDiscoveryPort):
            raise MobileError(
                MobileReasonCode.INVALID_INPUT,
                "discovery must implement the LocalDiscoveryPort seam",
            )
        for access_class, interface_name in access_interfaces.items():
            if access_class not in (NetworkKind.WIFI, NetworkKind.CELLULAR):
                raise MobileError(
                    MobileReasonCode.INVALID_INPUT,
                    "access_interfaces key %r must be a usable access kind"
                    % (access_class,),
                )
            if not isinstance(interface_name, str) or not interface_name:
                raise MobileError(
                    MobileReasonCode.INVALID_INPUT,
                    "access_interfaces[%r] must be a non-empty interface name"
                    % (access_class,),
                )
        if budget is None:
            budget = MobileBudget()
        if not isinstance(budget, MobileBudget):
            raise MobileError(
                MobileReasonCode.INVALID_INPUT,
                "budget must be a genuine MobileBudget",
            )
        self._runtime = AgentRuntime(
            config, clock=clock, interface_source=interface_source,
        )
        self._clock = clock
        self._platform_source = platform_source
        self._discovery = discovery
        self._access_interfaces: Dict[str, str] = dict(access_interfaces)
        self._budget = budget
        # A launched app starts in the foreground; the first platform
        # observation may immediately move it (a legal transition).
        self._phase = MobilePhase.FOREGROUND
        self._platform: Optional[PlatformSnapshot] = None
        self._network_kind = NetworkKind.NONE
        self._grants: Dict[str, UserGrant] = {}
        self._events: List[MobileEvent] = []
        self._event_sequence = 0
        self._queue: List[_DeferredSend] = []
        self._tracked: Dict[str, _TrackedSession] = {}
        self._observations: List[PeerObservation] = []
        self._last_snapshot: Optional[MobileSnapshot] = None

    # -- read-only surfaces ------------------------------------------------

    @property
    def runtime(self) -> AgentRuntime:
        return self._runtime

    @property
    def phase(self) -> str:
        return self._phase

    @property
    def platform(self) -> Optional[PlatformSnapshot]:
        return self._platform

    @property
    def network_kind(self) -> str:
        return self._network_kind

    @property
    def grants(self) -> Tuple[UserGrant, ...]:
        return tuple(
            self._grants[scope] for scope in sorted(self._grants)
        )

    @property
    def deferred_depth(self) -> int:
        return len(self._queue)

    @property
    def access_interfaces(self) -> Mapping[str, str]:
        return dict(self._access_interfaces)

    @property
    def mobile_events(self) -> Tuple[MobileEvent, ...]:
        return tuple(self._events)

    @property
    def mobile_event_digest(self) -> str:
        return mobile_event_list_digest(tuple(self._events))

    @property
    def peer_observations(self) -> Tuple[PeerObservation, ...]:
        return tuple(self._observations)

    @property
    def last_snapshot(self) -> Optional[MobileSnapshot]:
        return self._last_snapshot

    def _default_platform(self) -> PlatformSnapshot:
        return PlatformSnapshot(
            app_phase=MobilePhase.FOREGROUND,
            power_state="on-battery",
            network_kind=NetworkKind.NONE,
            metered=False,
            background_restricted=False,
        )

    def _decision_at(self, instant: str) -> ParticipationDecision:
        """The participation gate evaluated at ONE explicit instant
        (internal determinism: a single epoch evaluates the gate at a
        single injected instant, never at drifting clock reads)."""
        platform = self._platform or self._default_platform()
        return participation_gate(
            self._phase, platform, self._grants, now=instant,
        )

    @property
    def decision(self) -> ParticipationDecision:
        """The current participation decision (pure gate over the
        current phase, platform, and grants).  Diagnostic surface:
        reads the injected clock once."""
        return self._decision_at(self._clock.now())

    def access_paths(self, session_id: str) -> Tuple[AccessPathView, ...]:
        """The continuity view of one tracked session (WORK-013
        vocabulary as DATA)."""
        tracked = self._tracked.get(session_id)
        if tracked is None:
            return ()
        return tuple(tracked.paths[key] for key in sorted(tracked.paths))

    def mobile_snapshot(self) -> Dict[str, Any]:
        """A secret-free deterministic snapshot of the mobile layer."""
        return {
            "phase": self._phase,
            "network_kind": self._network_kind,
            "deferred_depth": len(self._queue),
            "tracked_sessions": sorted(self._tracked),
            "grant_scopes": sorted(self._grants),
            "event_count": len(self._events),
            "mobile_event_digest": self.mobile_event_digest,
            "agent_status": self._runtime.status,
            "agent_event_digest": self._runtime.event_log_digest(),
        }

    def content_digest(self) -> str:
        return "sha256:" + _sha256_hex(
            canonical_json_bytes(self.mobile_snapshot())
        )

    # -- journal ------------------------------------------------------------

    def _record_event(
        self, kind: str, instant: str, *, subject: str = "",
        detail: str = "", ref: str = "",
    ) -> None:
        self._event_sequence += 1
        self._events.append(
            MobileEvent(
                kind=kind,
                sequence=self._event_sequence,
                instant=instant,
                subject=subject,
                detail=detail,
                ref=ref,
            )
        )

    # -- platform refresh ---------------------------------------------------

    def _read_platform(self) -> PlatformSnapshot:
        try:
            snapshot = self._platform_source.read()
        except MobileError:
            raise
        except Exception as error:  # fail closed, class name only
            raise MobileError(
                MobileReasonCode.PLATFORM_SOURCE_FAILED,
                "platform source failed: %s" % (type(error).__name__,),
            ) from error
        if not isinstance(snapshot, PlatformSnapshot):
            raise MobileError(
                MobileReasonCode.PLATFORM_SOURCE_FAILED,
                "platform source returned a non-snapshot %r"
                % (type(snapshot).__name__,),
            )
        return snapshot

    def _sweep_grants(self, instant: str) -> None:
        """Expire grants whose TTL boundary has passed (explicit,
        journaled -- consent ends loudly)."""
        for scope in sorted(self._grants):
            if not grant_active(self._grants, scope, now=instant):
                grant = self._grants.pop(scope)
                self._record_event(
                    MobileEventType.GRANT_EXPIRED, instant,
                    subject=scope,
                    detail="expired at %s" % instant,
                    ref=grant.grant_id,
                )

    def _fail_paths(self, instant: str) -> None:
        """Mark every current access path FAILED (the access went
        away; WORK-013 ACTIVE/DEGRADED -> FAILED is legal) and mark
        the sessions unattached (the binding to the lost access is
        gone -- the sticky ``bound_access`` keeps the handover
        provenance)."""
        for tracked in self._tracked.values():
            for access_class in sorted(tracked.paths):
                view = tracked.paths[access_class]
                if view.status == PathStatus.FAILED:
                    continue
                tracked.apply_path_status(
                    access_class, view.interface_name, PathStatus.FAILED,
                )
            tracked.attached = False
        _ = instant  # the failure is journaled by the caller

    def _maintain_bindings(self, instant: str) -> None:
        """The continuity invariant: every tracked ESTABLISHED session
        is attached to the currently usable access (through the
        ordinary WORK-033 binding path).  Metered access without the
        user's consent is never attached."""
        if self._runtime.status != "online":
            return
        decision = self._decision_at(instant)
        if not decision.online:
            return
        if decision.metered and decision.defer_reason == DeferReason.METERED_NOT_AUTHORIZED:
            return
        interface_name = self._access_interfaces.get(self._network_kind)
        if interface_name is None:
            raise MobileError(
                MobileReasonCode.ACCESS_UNAVAILABLE,
                "platform reports access %r with no mapped interface "
                "(deployment wiring incomplete)" % (self._network_kind,),
            )
        for session_id in sorted(self._tracked):
            tracked = self._tracked[session_id]
            session = self._runtime.sessions.get(session_id)
            if session is None or session.state != SessionState.ESTABLISHED:
                continue
            if tracked.attached and tracked.bound_access == self._network_kind:
                continue
            old_access = tracked.bound_access
            try:
                binding = self._runtime.bind_session(
                    session_id, interface_name=interface_name,
                )
            except AgentError as error:
                raise MobileError(
                    MobileReasonCode.ACCESS_UNAVAILABLE,
                    "session re-bind rejected by the runtime: %s"
                    % (error.detail or error.reason,),
                ) from error
            tracked.attached = True
            tracked.bound_access = self._network_kind
            # A terminal FAILED view for this access is REPLACED by a
            # fresh ACTIVE entry (the WORK-013 removal + re-add
            # discipline); every other status change flows through the
            # frozen legal-transition table.
            existing = tracked.paths.get(self._network_kind)
            if existing is not None and existing.status == PathStatus.FAILED:
                del tracked.paths[self._network_kind]
            tracked.apply_path_status(
                self._network_kind, interface_name, PathStatus.ACTIVE,
            )
            if old_access and old_access != self._network_kind:
                self._record_event(
                    MobileEventType.HANDOVER_COMPLETED, instant,
                    subject=session_id,
                    detail="%s -> %s" % (old_access, self._network_kind),
                    ref=binding.get("ip_binding_id", ""),
                )
            else:
                self._record_event(
                    MobileEventType.SESSION_BOUND_TO_ACCESS, instant,
                    subject=session_id,
                    detail=self._network_kind,
                    ref=binding.get("ip_binding_id", ""),
                )

    def _refresh_platform(self, instant: str) -> None:
        snapshot = self._read_platform()
        self._sweep_grants(instant)
        # -- phase transition -------------------------------------------
        if snapshot.app_phase != self._phase:
            if not transition_is_legal(self._phase, snapshot.app_phase):
                raise MobileError(
                    MobileReasonCode.LIFECYCLE_ILLEGAL,
                    "platform reported an illegal phase transition "
                    "%s -> %s" % (self._phase, snapshot.app_phase),
                )
            previous = self._phase
            self._phase = snapshot.app_phase
            self._record_event(
                MobileEventType.PHASE_CHANGED, instant,
                subject=snapshot.app_phase,
                detail="%s -> %s" % (previous, snapshot.app_phase),
            )
        # The platform snapshot is current from here on (the gate and
        # the binding maintenance below must see THIS observation).
        self._platform = snapshot
        if self._phase == MobilePhase.STOPPED:
            # The process dies: produce the durable state (the
            # snapshot models what was persisted at death).
            self._network_kind = snapshot.network_kind
            self.checkpoint()
            return
        # -- connectivity change ----------------------------------------
        if snapshot.network_kind != self._network_kind:
            old_kind = self._network_kind
            self._network_kind = snapshot.network_kind
            self._record_event(
                MobileEventType.CONNECTIVITY_CHANGED, instant,
                subject=snapshot.network_kind,
                detail="%s -> %s" % (old_kind, snapshot.network_kind),
            )
            if snapshot.network_kind == NetworkKind.NONE:
                self._fail_paths(instant)
            else:
                interface_name = self._access_interfaces.get(
                    snapshot.network_kind,
                )
                if interface_name is None:
                    raise MobileError(
                        MobileReasonCode.ACCESS_UNAVAILABLE,
                        "platform reports access %r with no mapped "
                        "interface (deployment wiring incomplete)"
                        % (snapshot.network_kind,),
                    )
                decision = participation_gate(
                    self._phase, snapshot, self._grants, now=instant,
                )
                if decision.metered and decision.defer_reason == DeferReason.METERED_NOT_AUTHORIZED:
                    # The user has not authorized this metered access:
                    # attach nothing, shed the old paths, defer sends.
                    self._fail_paths(instant)
                    self._record_event(
                        MobileEventType.ACCESS_REFUSED, instant,
                        subject=snapshot.network_kind,
                        detail="metered access not authorized by the user",
                    )
                else:
                    self._fail_paths(instant)
                    self._maintain_bindings(instant)
        # -- restriction drift (same access, changed OS limits) --------
        if self._network_kind != NetworkKind.NONE:
            decision = self._decision_at(instant)
            interface_name = self._access_interfaces.get(self._network_kind)
            if interface_name is not None:
                for tracked in self._tracked.values():
                    view = tracked.paths.get(self._network_kind)
                    if view is None or view.status == PathStatus.FAILED:
                        continue
                    target = (
                        PathStatus.DEGRADED
                        if decision.defer_reason else PathStatus.ACTIVE
                    )
                    tracked.apply_path_status(
                        self._network_kind, interface_name, target,
                    )

    # -- consent --------------------------------------------------------

    def grant(self, scope: str, *, expires_at: str = "") -> UserGrant:
        """Record a user consent grant (INPUT, not authority)."""
        instant = self._clock.now()
        if self._phase == MobilePhase.STOPPED:
            raise MobileError(
                MobileReasonCode.COMMAND_STOPPED,
                "a stopped process records no grants",
            )
        record = UserGrant(
            scope=scope, granted_at=instant, expires_at=expires_at,
        )
        self._grants[scope] = record
        self._record_event(
            MobileEventType.GRANT_GRANTED, instant,
            subject=scope,
            detail="expires %s" % (expires_at or "never"),
            ref=record.grant_id,
        )
        self._maintain_bindings(instant)
        return record

    def revoke(self, scope: str) -> None:
        """Revoke a user consent grant (immediate, journaled)."""
        instant = self._clock.now()
        if self._phase == MobilePhase.STOPPED:
            raise MobileError(
                MobileReasonCode.COMMAND_STOPPED,
                "a stopped process revokes no grants",
            )
        record = self._grants.pop(scope, None)
        if record is None:
            raise MobileError(
                MobileReasonCode.GRANT_INVALID,
                "no active %s grant to revoke" % (scope,),
            )
        self._record_event(
            MobileEventType.GRANT_REVOKED, instant,
            subject=scope,
            detail="revoked by the user",
            ref=record.grant_id,
        )

    # -- session continuity ----------------------------------------------

    def track_session(self, session_id: str) -> None:
        """Register a session for continuity management (a VIEW over
        the WORK-012-owned lifecycle; no session state is created or
        mutated here)."""
        instant = self._clock.now()
        if self._phase == MobilePhase.STOPPED:
            raise MobileError(
                MobileReasonCode.COMMAND_STOPPED,
                "a stopped process tracks no sessions",
            )
        session = self._runtime.sessions.get(session_id)
        if session is None:
            raise MobileError(
                MobileReasonCode.SESSION_UNKNOWN,
                "session %s is not known to the runtime" % (session_id[:32],),
            )
        if session_id in self._tracked:
            return
        self._tracked[session_id] = _TrackedSession(session_id)
        self._record_event(
            MobileEventType.SESSION_TRACKED, instant,
            subject=session_id,
            detail="state %s" % session.state,
        )
        self._maintain_bindings(instant)

    def _require_session(self, session_id: str) -> None:
        session = self._runtime.sessions.get(session_id)
        if session is None:
            raise MobileError(
                MobileReasonCode.SESSION_UNKNOWN,
                "session %s is not known to the runtime" % (session_id[:32],),
            )

    def _deferred_expired(self, deferred_at: str, instant: str) -> bool:
        expires = parse_utc(deferred_at) + timedelta(
            seconds=self._budget.deferred_ttl_seconds,
        )
        return parse_utc(instant) >= expires

    def _enqueue_send(
        self, session_id: str, payload: bytes, instant: str, reason: str,
    ) -> List[MobileOutcome]:
        """Queue a deferred send; shed oldest when the queue would
        exceed its bound.  Returns the shed outcome records (never
        silent)."""
        self._queue.append(
            _DeferredSend(session_id, payload, instant, reason)
        )
        self._record_event(
            MobileEventType.SEND_DEFERRED, instant,
            subject=session_id,
            detail=reason,
            ref="sha256:" + _sha256_hex(payload),
        )
        shed: List[MobileOutcome] = []
        while len(self._queue) > self._budget.max_deferred_depth:
            victim = self._queue.pop(0)
            self._record_event(
                MobileEventType.SEND_SHED, instant,
                subject=victim.session_id,
                detail="defer-queue-overflow",
                ref="sha256:" + _sha256_hex(victim.payload),
            )
            shed.append(
                MobileOutcome(
                    command_id="",
                    kind=MobileCommandKind.SEND_DATAGRAM,
                    verdict=MobileVerdict.SHED,
                    reason="defer-queue-overflow",
                )
            )
        return shed

    def _drain_queue(self, instant: str) -> List[MobileOutcome]:
        """Attempt to drain the deferred queue: TTL-expired entries
        shed; entries whose session is gone shed; entries the gate now
        admits are sent; the rest stay queued (TTLs keep aging from
        their ORIGINAL deferred-at instants)."""
        outcomes: List[MobileOutcome] = []
        if not self._queue:
            return outcomes
        decision = self._decision_at(instant)
        kept: List[_DeferredSend] = []
        for entry in self._queue:
            if self._deferred_expired(entry.deferred_at, instant):
                self._record_event(
                    MobileEventType.SEND_SHED, instant,
                    subject=entry.session_id,
                    detail="deferred-ttl-expired",
                    ref="sha256:" + _sha256_hex(entry.payload),
                )
                outcomes.append(
                    MobileOutcome(
                        command_id="",
                        kind=MobileCommandKind.SEND_DATAGRAM,
                        verdict=MobileVerdict.SHED,
                        reason="deferred-ttl-expired",
                    )
                )
                continue
            session = self._runtime.sessions.get(entry.session_id)
            if (
                session is None
                or session.state != SessionState.ESTABLISHED
            ):
                self._record_event(
                    MobileEventType.SEND_SHED, instant,
                    subject=entry.session_id,
                    detail="session-lost",
                    ref="sha256:" + _sha256_hex(entry.payload),
                )
                outcomes.append(
                    MobileOutcome(
                        command_id="",
                        kind=MobileCommandKind.SEND_DATAGRAM,
                        verdict=MobileVerdict.SHED,
                        reason="session-lost",
                    )
                )
                continue
            if not decision.sends_allowed:
                kept.append(entry)
                continue
            artifact = self._runtime.send_datagram(
                entry.session_id, entry.payload,
            )
            self._record_event(
                MobileEventType.DEFERRED_DRAINED, instant,
                subject=entry.session_id,
                detail=entry.reason,
                ref="sha256:" + _sha256_hex(entry.payload),
            )
            outcomes.append(
                MobileOutcome(
                    command_id="",
                    kind=MobileCommandKind.SEND_DATAGRAM,
                    verdict=MobileVerdict.EXECUTED,
                    detail="drained; frame sha256:" + _sha256_hex(
                        canonical_json_bytes(dict(artifact.frame))
                    ),
                )
            )
        self._queue = kept
        return outcomes

    def drain(self) -> List[MobileOutcome]:
        """Public drain hook (data-driven recovery)."""
        if self._phase == MobilePhase.STOPPED:
            raise MobileError(
                MobileReasonCode.COMMAND_STOPPED,
                "a stopped process drains nothing",
            )
        instant = self._clock.now()
        return self._drain_queue(instant)

    def send_datagram(self, session_id: str, payload: bytes) -> MobileOutcome:
        """One gated outgoing datagram: executed through the unchanged
        runtime transport path when participation allows, deferred
        with a typed reason when it does not."""
        if self._phase == MobilePhase.STOPPED:
            raise MobileError(
                MobileReasonCode.COMMAND_STOPPED,
                "a stopped process sends nothing",
            )
        if not isinstance(payload, (bytes, bytearray)):
            raise MobileError(
                MobileReasonCode.INVALID_INPUT,
                "payload must be bytes",
            )
        self._require_session(session_id)
        instant = self._clock.now()
        decision = self._decision_at(instant)
        if decision.sends_allowed:
            artifact = self._runtime.send_datagram(session_id, bytes(payload))
            return MobileOutcome(
                command_id="",
                kind=MobileCommandKind.SEND_DATAGRAM,
                verdict=MobileVerdict.EXECUTED,
                detail="frame sha256:" + _sha256_hex(
                    canonical_json_bytes(dict(artifact.frame))
                ),
            )
        self._enqueue_send(session_id, bytes(payload), instant, decision.defer_reason)
        return MobileOutcome(
            command_id="",
            kind=MobileCommandKind.SEND_DATAGRAM,
            verdict=MobileVerdict.DEFERRED,
            reason=decision.defer_reason,
            detail="sha256:" + _sha256_hex(bytes(payload)),
        )

    # -- local discovery ---------------------------------------------------

    def poll_discovery(self) -> MobileOutcome:
        """One gated local discovery cycle through the host-provided
        port.  Without the user's local-discovery consent (or while
        participation is otherwise closed) the cycle is deferred with
        a typed reason -- never silently skipped."""
        if self._phase == MobilePhase.STOPPED:
            raise MobileError(
                MobileReasonCode.COMMAND_STOPPED,
                "a stopped process discovers nothing",
            )
        instant = self._clock.now()
        decision = self._decision_at(instant)
        if not decision.discovery_allowed:
            self._record_event(
                MobileEventType.DISCOVERY_DEFERRED, instant,
                subject="local",
                detail=decision.defer_reason or "local-discovery-not-granted",
            )
            return MobileOutcome(
                command_id="",
                kind=MobileCommandKind.POLL_DISCOVERY,
                verdict=MobileVerdict.DEFERRED,
                reason=decision.defer_reason or "local-discovery-not-granted",
            )
        cycle = self._discovery.cycle(now=instant)
        for observation in cycle.observations:
            self._observations.append(observation)
        self._record_event(
            MobileEventType.DISCOVERY_COMPLETED, instant,
            subject="local",
            detail="announced=%s observed=%d"
            % ("yes" if cycle.announced else "no", len(cycle.observations)),
            ref=cycle.announcement_id,
        )
        return MobileOutcome(
            command_id="",
            kind=MobileCommandKind.POLL_DISCOVERY,
            verdict=MobileVerdict.EXECUTED,
            detail="observed %d" % len(cycle.observations),
        )

    # -- durable state ------------------------------------------------------

    def checkpoint(self) -> MobileSnapshot:
        """Produce the durable mobile-layer state (secret-free).

        The CHECKPOINTED event is journaled FIRST so the snapshot's
        journal continuation point covers it: the successor's first
        event (RESTARTED) continues strictly after the checkpoint."""
        instant = self._clock.now()
        self._record_event(
            MobileEventType.CHECKPOINTED, instant,
            subject=self._phase,
            detail="%d grants, %d deferred"
            % (len(self._grants), len(self._queue)),
        )
        sessions: List[Dict[str, str]] = []
        for session_id in sorted(self._tracked):
            tracked = self._tracked[session_id]
            for view in tracked.view_dicts():
                entry = dict(view)
                entry["session_id"] = session_id
                sessions.append(entry)
        snapshot = MobileSnapshot(
            phase=self._phase,
            grants=self.grants,
            deferred=tuple(entry.entry_dict() for entry in self._queue),
            sessions=tuple(sessions),
            event_sequence=self._event_sequence,
            event_digest=self.mobile_event_digest,
            produced_at=instant,
        )
        self._last_snapshot = snapshot
        return snapshot

    @classmethod
    def recover(
        cls,
        snapshot: MobileSnapshot,
        *,
        config: AgentConfig,
        clock: AgentClock,
        interface_source: InterfaceSource,
        platform_source: MobilePlatformSource,
        discovery: Optional[LocalDiscoveryPort] = None,
        access_interfaces: Mapping[str, str] = {},
        budget: Optional[MobileBudget] = None,
    ) -> "MobileAgent":
        """Build the successor process from a durable snapshot.

        The journal sequence CONTINUES (the successor's first event is
        a RESTARTED record); user grants are restored (their TTLs
        still evaluated against the recovered instant); the deferred
        queue is restored with its ORIGINAL deferred-at instants (TTLs
        aged through the downtime); tracked sessions are recorded as
        LOST (the killed process's runtime is gone -- the successor
        re-establishes through the ordinary path; nothing is
        fabricated).
        """
        if not isinstance(snapshot, MobileSnapshot):
            raise MobileError(
                MobileReasonCode.SNAPSHOT_INVALID,
                "recovery requires a genuine MobileSnapshot",
            )
        agent = cls(
            config=config,
            clock=clock,
            interface_source=interface_source,
            platform_source=platform_source,
            discovery=discovery,
            access_interfaces=access_interfaces,
            budget=budget,
        )
        agent._event_sequence = snapshot.event_sequence
        instant = clock.now()
        agent._record_event(
            MobileEventType.RESTARTED, instant,
            subject="process",
            detail="recovered from %s" % (snapshot.snapshot_id[:23],),
            ref=snapshot.event_digest,
        )
        for grant in snapshot.grants:
            if grant.scope not in agent._grants:
                agent._grants[grant.scope] = grant
        for entry in snapshot.deferred:
            agent._queue.append(
                _DeferredSend(
                    session_id=str(entry.get("session_id", "")),
                    payload=bytes.fromhex(str(entry.get("payload_hex", ""))),
                    deferred_at=str(entry.get("deferred_at", "")),
                    reason=str(entry.get("reason", "")),
                )
            )
        session_ids = sorted({
            str(entry.get("session_id", ""))
            for entry in snapshot.sessions
            if entry.get("session_id")
        })
        for session_id in session_ids:
            tracked = _TrackedSession(session_id)
            for entry in snapshot.sessions:
                if str(entry.get("session_id", "")) != session_id:
                    continue
                view = AccessPathView.from_dict(entry)
                # Every path the killed process held is FAILED at
                # recovery (the WORK-013 terminal status -- honestly
                # recorded, never resurrected).
                tracked.paths[view.access_class] = AccessPathView(
                    access_class=view.access_class,
                    interface_name=view.interface_name,
                    status=PathStatus.FAILED,
                )
            tracked.attached = False
            agent._tracked[session_id] = tracked
            agent._record_event(
                MobileEventType.SESSION_LOST_AT_RESTART, instant,
                subject=session_id,
                detail="the killed process held this session; "
                       "re-establish through the ordinary path",
            )
        agent._last_snapshot = snapshot
        return agent

    # -- the run epoch --------------------------------------------------------

    def run_mobile(
        self,
        commands: Sequence[MobileCommand],
        *,
        boot_secret: Optional[bytes] = None,
    ) -> MobileRunResult:
        """Execute one participation epoch over a command batch.

        Deterministic order: platform refresh (phase transition,
        connectivity/handover, consent sweep), deferred-queue drain,
        then per-command dispatch through the participation gate.
        Every decision is recorded; nothing is dropped silently.
        """
        if self._phase == MobilePhase.STOPPED:
            raise MobileError(
                MobileReasonCode.COMMAND_STOPPED,
                "the process is stopped; recover from the durable snapshot",
            )
        instant = self._clock.now()
        self._refresh_platform(instant)
        if self._phase == MobilePhase.STOPPED:
            # The platform reported death during this refresh: the
            # batch cannot continue (the process is gone).
            raise MobileError(
                MobileReasonCode.COMMAND_STOPPED,
                "the platform reported the process stopped; the durable "
                "snapshot was produced",
            )
        outcomes: List[MobileOutcome] = list(self._drain_queue(instant))
        executed = deferred = shed = 0
        for command in commands:
            if not isinstance(command, MobileCommand):
                raise MobileError(
                    MobileReasonCode.INVALID_INPUT,
                    "run_mobile requires genuine MobileCommand values",
                )
            if self._phase == MobilePhase.STOPPED:
                raise MobileError(
                    MobileReasonCode.COMMAND_STOPPED,
                    "the process stopped mid-batch",
                )
            outcome = self._dispatch(command, boot_secret)
            outcomes.append(outcome)
            if outcome.verdict == MobileVerdict.EXECUTED:
                executed += 1
            elif outcome.verdict == MobileVerdict.DEFERRED:
                deferred += 1
            else:
                shed += 1
        decision = self._decision_at(instant)
        payload = MobileRunResult(
            status=self._runtime.status,
            phase=self._phase,
            network_kind=self._network_kind,
            defer_reason=decision.defer_reason,
            executed=executed,
            deferred=deferred,
            shed=shed,
            outcomes=tuple(outcomes),
            deferred_depth=len(self._queue),
            agent_event_digest=self._runtime.event_log_digest(),
            mobile_event_digest=self.mobile_event_digest,
        )
        payload_dict = payload.to_dict()
        object.__setattr__(
            payload,
            "mobile_digest",
            "sha256:" + _sha256_hex(canonical_json_bytes(payload_dict)),
        )
        return payload

    def _dispatch(
        self, command: MobileCommand, boot_secret: Optional[bytes],
    ) -> MobileOutcome:
        kind = command.kind
        params = command.params
        if kind in _PASSTHROUGH_KINDS:
            agent_command = AgentCommand(kind=kind, params=dict(params))
            result = self._runtime.execute(
                (agent_command,), boot_secret=boot_secret,
            )
            agent_outcome = result.outcomes[0]
            verdict = MobileVerdict.EXECUTED
            detail = agent_outcome.detail[:160]
            if agent_outcome.verdict == "rejected":
                detail = "agent rejected: %s" % detail
            elif agent_outcome.verdict == "failed":
                detail = "agent failed: %s" % detail
            return MobileOutcome(
                command_id=command.command_id,
                kind=kind,
                verdict=verdict,
                detail=detail,
            )
        if kind == MobileCommandKind.SEND_DATAGRAM:
            session_id = str(params.get("session_id", ""))
            payload_hex = str(params.get("payload_hex", ""))
            try:
                payload = bytes.fromhex(payload_hex)
            except ValueError as error:
                raise MobileError(
                    MobileReasonCode.INVALID_INPUT,
                    "payload_hex must be hexadecimal",
                ) from error
            outcome = self.send_datagram(session_id, payload)
            return MobileOutcome(
                command_id=command.command_id,
                kind=kind,
                verdict=outcome.verdict,
                reason=outcome.reason,
                detail=outcome.detail,
            )
        if kind == MobileCommandKind.TRACK_SESSION:
            self.track_session(str(params.get("session_id", "")))
            return MobileOutcome(
                command_id=command.command_id,
                kind=kind,
                verdict=MobileVerdict.EXECUTED,
                detail="tracked",
            )
        if kind == MobileCommandKind.POLL_DISCOVERY:
            outcome = self.poll_discovery()
            return MobileOutcome(
                command_id=command.command_id,
                kind=kind,
                verdict=outcome.verdict,
                reason=outcome.reason,
                detail=outcome.detail,
            )
        if kind == MobileCommandKind.GRANT:
            scope = str(params.get("scope", ""))
            expires_at = str(params.get("expires_at", "") or "")
            record = self.grant(scope, expires_at=expires_at)
            return MobileOutcome(
                command_id=command.command_id,
                kind=kind,
                verdict=MobileVerdict.EXECUTED,
                detail=record.grant_id[:23],
            )
        if kind == MobileCommandKind.REVOKE_GRANT:
            self.revoke(str(params.get("scope", "")))
            return MobileOutcome(
                command_id=command.command_id,
                kind=kind,
                verdict=MobileVerdict.EXECUTED,
                detail="revoked",
            )
        if kind == MobileCommandKind.CHECKPOINT:
            snapshot = self.checkpoint()
            return MobileOutcome(
                command_id=command.command_id,
                kind=kind,
                verdict=MobileVerdict.EXECUTED,
                detail=snapshot.snapshot_id[:23],
            )
        raise MobileError(
            MobileReasonCode.INVALID_INPUT,
            "unhandled mobile command kind %r" % (kind,),
        )


# ----------------------------------------------------------------------
# Headless entry points
# ----------------------------------------------------------------------


def run_mobile_headless(
    config: AgentConfig,
    commands: Sequence[MobileCommand],
    *,
    clock: AgentClock,
    interface_source: InterfaceSource,
    platform_source: MobilePlatformSource,
    discovery: Optional[LocalDiscoveryPort] = None,
    access_interfaces: Mapping[str, str] = {},
    budget: Optional[MobileBudget] = None,
    boot_secret: Optional[bytes] = None,
) -> MobileRunResult:
    """Construct a mobile agent and execute one headless command
    batch (the WORK-033 ``run_headless`` discipline: everything is
    data + an injected clock)."""
    agent = MobileAgent(
        config=config,
        clock=clock,
        interface_source=interface_source,
        platform_source=platform_source,
        discovery=discovery,
        access_interfaces=access_interfaces,
        budget=budget,
    )
    return agent.run_mobile(commands, boot_secret=boot_secret)


def verify_mobile_replay(
    config: AgentConfig,
    commands: Sequence[MobileCommand],
    *,
    clock_factory: Callable[[], AgentClock],
    interface_source_factory: Callable[[], InterfaceSource],
    platform_source_factory: Callable[[], MobilePlatformSource],
    discovery_factory: Optional[Callable[[], LocalDiscoveryPort]] = None,
    access_interfaces: Mapping[str, str] = {},
    budget: Optional[MobileBudget] = None,
    boot_secret: Optional[bytes] = None,
    expected_mobile_digest: str = "",
) -> Tuple[bool, str]:
    """Re-run a mobile scenario with fresh factories; the whole
    scenario digest must reproduce byte-identically or the replay
    fails closed."""
    result = run_mobile_headless(
        config,
        commands,
        clock=clock_factory(),
        interface_source=interface_source_factory(),
        platform_source=platform_source_factory(),
        discovery=discovery_factory() if discovery_factory else None,
        access_interfaces=access_interfaces,
        budget=budget,
        boot_secret=boot_secret,
    )
    if expected_mobile_digest and result.mobile_digest != expected_mobile_digest:
        return (False, "mobile digest diverged on replay")
    return (True, result.mobile_digest)


__all__ = [
    "MobileCommandKind",
    "MobileCommand",
    "MobileBudget",
    "MobileAgent",
    "derive_mobile_command_id",
    "run_mobile_headless",
    "verify_mobile_replay",
]
