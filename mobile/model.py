"""WORK-035 mobile-participation value model.

The frozen vocabularies and value records of the mobile layer:

- **lifecycle** -- the mobile app phases (foreground / background /
  stopped) and the OS-reported platform snapshot (power, usable access,
  metering, background restrictions) that drives them: background
  limitations and offline state are EXPLICIT inputs, never hidden
  authority changes;
- **consent** -- the user resource-sharing grant records (metered data
  / background data / local discovery): user authorization is INPUT to
  the participation gate, not a new resource or policy authority;
- **continuity** -- the per-session access-path view over the frozen
  WORK-013 constituent-path status vocabulary (DATA only; the mobile
  layer never operates the multipath authority);
- **events** -- the append-only mobile event journal (the WORK-033
  agent-event discipline applied to the mobile layer's own decisions);
- **results** -- the mobile run result: the agent's own outcomes plus
  the participation verdicts and digests, so a whole mobile scenario
  is one deterministic, replayable digest.

Nothing here mutates another subsystem's state.  The value model is
DATA with validation, in the WORK-033 ``agent.model`` style.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import List, Mapping, Tuple

from protocol.canonicalization import canonical_json_bytes

from .errors import MobileError, MobileReasonCode


# ----------------------------------------------------------------------
# Frozen vocabularies
# ----------------------------------------------------------------------


class MobilePhase:
    """The frozen mobile application lifecycle vocabulary.

    The phase is the OS-reported application state (an explicit input
    through the platform source); the mobile layer adapts to it, it
    never forces it.
    """

    FOREGROUND = "foreground"
    BACKGROUND = "background"
    STOPPED = "stopped"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.FOREGROUND, cls.BACKGROUND, cls.STOPPED)


class PowerState:
    """The frozen device power vocabulary (platform-reported DATA)."""

    CHARGING = "charging"
    ON_BATTERY = "on-battery"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.CHARGING, cls.ON_BATTERY)


class NetworkKind:
    """The frozen platform-reported usable-access vocabulary.

    This is the OS connectivity callback's view of WHICH access can
    currently carry traffic (``none`` = offline).  It is a
    classification of a platform INPUT -- never a new access
    technology, and never core routing state.
    """

    NONE = "none"
    WIFI = "wifi"
    CELLULAR = "cellular"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.NONE, cls.WIFI, cls.CELLULAR)


class GrantScope:
    """The frozen user resource-sharing consent vocabulary.

    A grant is user authorization INPUT that mediates what the mobile
    layer may do with device resources.  It is not a policy decision
    (the WORK-010 engine is untouched) and not a resource authority
    (the WORK-008 store is untouched).
    """

    METERED_DATA = "metered-data"
    BACKGROUND_DATA = "background-data"
    LOCAL_DISCOVERY = "local-discovery"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.METERED_DATA, cls.BACKGROUND_DATA, cls.LOCAL_DISCOVERY)


class MobileVerdict:
    """The frozen participation verdict vocabulary (what the mobile
    layer did with a command; the agent's own applied/rejected/failed
    verdict is carried separately when a command was executed)."""

    EXECUTED = "executed"
    DEFERRED = "deferred"
    SHED = "shed"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.EXECUTED, cls.DEFERRED, cls.SHED)


class DeferReason:
    """The frozen reason vocabulary for deferred participation."""

    OFFLINE = "offline"
    METERED_NOT_AUTHORIZED = "metered-not-authorized"
    BACKGROUND_NOT_AUTHORIZED = "background-not-authorized"
    BACKGROUND_RESTRICTED = "background-restricted"
    STOPPED = "stopped"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.OFFLINE,
            cls.METERED_NOT_AUTHORIZED,
            cls.BACKGROUND_NOT_AUTHORIZED,
            cls.BACKGROUND_RESTRICTED,
            cls.STOPPED,
        )


class ShedReason:
    """The frozen reason vocabulary for shed participation."""

    DEFERRED_TTL_EXPIRED = "deferred-ttl-expired"
    DEFER_QUEUE_OVERFLOW = "defer-queue-overflow"
    SESSION_LOST = "session-lost"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.DEFERRED_TTL_EXPIRED,
            cls.DEFER_QUEUE_OVERFLOW,
            cls.SESSION_LOST,
        )


class MobileEventType:
    """The frozen mobile event vocabulary (kebab-case, the WORK-033
    agent-event discipline).  Events record mobile-layer DECISIONS --
    lifecycle adaptation, consent changes, handover, deferral --
    never authority state (the agent event log remains the record of
    authority mutations)."""

    PHASE_CHANGED = "phase-changed"
    CONNECTIVITY_CHANGED = "connectivity-changed"
    ACCESS_REFUSED = "access-refused"
    SESSION_TRACKED = "session-tracked"
    SESSION_BOUND_TO_ACCESS = "session-bound-to-access"
    HANDOVER_COMPLETED = "handover-completed"
    SESSION_LOST_AT_RESTART = "session-lost-at-restart"
    SEND_DEFERRED = "send-deferred"
    SEND_SHED = "send-shed"
    DEFERRED_DRAINED = "deferred-drained"
    GRANT_GRANTED = "grant-granted"
    GRANT_REVOKED = "grant-revoked"
    GRANT_EXPIRED = "grant-expired"
    DISCOVERY_COMPLETED = "discovery-completed"
    DISCOVERY_DEFERRED = "discovery-deferred"
    CHECKPOINTED = "checkpointed"
    RESTARTED = "restarted"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.PHASE_CHANGED,
            cls.CONNECTIVITY_CHANGED,
            cls.ACCESS_REFUSED,
            cls.SESSION_TRACKED,
            cls.SESSION_BOUND_TO_ACCESS,
            cls.HANDOVER_COMPLETED,
            cls.SESSION_LOST_AT_RESTART,
            cls.SEND_DEFERRED,
            cls.SEND_SHED,
            cls.DEFERRED_DRAINED,
            cls.GRANT_GRANTED,
            cls.GRANT_REVOKED,
            cls.GRANT_EXPIRED,
            cls.DISCOVERY_COMPLETED,
            cls.DISCOVERY_DEFERRED,
            cls.CHECKPOINTED,
            cls.RESTARTED,
        )


# ----------------------------------------------------------------------
# Platform snapshot (the OS-input record)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class PlatformSnapshot:
    """One OS-reported platform observation (pure DATA).

    Everything the OS imposes on the app is HERE, as explicit input:
    the application phase, the power state, the usable access kind,
    whether that access is metered, and whether background work is
    currently restricted (doze / battery saver).  The mobile layer
    adapts to these; it never mutates them and never lets them leak
    into authority state.
    """

    app_phase: str
    power_state: str
    network_kind: str
    metered: bool
    background_restricted: bool

    def __post_init__(self) -> None:
        if self.app_phase not in MobilePhase.values():
            raise MobileError(
                MobileReasonCode.PLATFORM_INVALID,
                "app_phase must be one of %s (got %r)"
                % (MobilePhase.values(), self.app_phase),
            )
        if self.power_state not in PowerState.values():
            raise MobileError(
                MobileReasonCode.PLATFORM_INVALID,
                "power_state must be one of %s (got %r)"
                % (PowerState.values(), self.power_state),
            )
        if self.network_kind not in NetworkKind.values():
            raise MobileError(
                MobileReasonCode.PLATFORM_INVALID,
                "network_kind must be one of %s (got %r)"
                % (NetworkKind.values(), self.network_kind),
            )
        for name in ("metered", "background_restricted"):
            if not isinstance(getattr(self, name), bool):
                raise MobileError(
                    MobileReasonCode.PLATFORM_INVALID,
                    "%s must be a bool (got %s)"
                    % (name, type(getattr(self, name)).__name__),
                )
        if self.network_kind == NetworkKind.NONE and self.metered:
            raise MobileError(
                MobileReasonCode.PLATFORM_INVALID,
                "metered must be False when there is no usable access",
            )

    def to_dict(self) -> dict:
        return {
            "app_phase": self.app_phase,
            "power_state": self.power_state,
            "network_kind": self.network_kind,
            "metered": self.metered,
            "background_restricted": self.background_restricted,
        }

    @classmethod
    def from_dict(cls, data: object) -> "PlatformSnapshot":
        if not isinstance(data, Mapping):
            raise MobileError(
                MobileReasonCode.PLATFORM_INVALID,
                "platform snapshot must be a mapping",
            )
        return cls(
            app_phase=str(data.get("app_phase", "")),
            power_state=str(data.get("power_state", "")),
            network_kind=str(data.get("network_kind", "")),
            metered=bool(data.get("metered", False)),
            background_restricted=bool(data.get("background_restricted", False)),
        )


# ----------------------------------------------------------------------
# User grants (consent records)
# ----------------------------------------------------------------------


def _validate_instant(value: str, label: str) -> None:
    if not isinstance(value, str) or not value:
        raise MobileError(
            MobileReasonCode.INVALID_INPUT,
            "%s must be a non-empty RFC 3339 string" % label,
        )


@dataclass(frozen=True)
class UserGrant:
    """One user resource-sharing authorization record.

    ``grant_id`` is a content-derived digest over (scope, granted_at,
    expires_at) -- a fingerprint, never an authorization.  ``expires_at``
    is the injected TTL boundary ("" = no expiry); evaluation against
    an explicit instant is :func:`mobile.lifecycle.grant_active`.  The
    record carries no secret material and no policy semantics.
    """

    scope: str
    granted_at: str
    expires_at: str = ""
    grant_id: str = ""

    def __post_init__(self) -> None:
        if self.scope not in GrantScope.values():
            raise MobileError(
                MobileReasonCode.GRANT_INVALID,
                "grant scope must be one of %s (got %r)"
                % (GrantScope.values(), self.scope),
            )
        _validate_instant(self.granted_at, "granted_at")
        if self.expires_at != "":
            _validate_instant(self.expires_at, "expires_at")
        object.__setattr__(
            self,
            "grant_id",
            self.grant_id or self._derive_grant_id(),
        )

    def _derive_grant_id(self) -> str:
        content = {
            "scope": self.scope,
            "granted_at": self.granted_at,
            "expires_at": self.expires_at,
        }
        return "sha256:" + hashlib.sha256(
            canonical_json_bytes(content)
        ).hexdigest()

    def to_dict(self) -> dict:
        return {
            "scope": self.scope,
            "granted_at": self.granted_at,
            "expires_at": self.expires_at,
            "grant_id": self.grant_id,
        }

    @classmethod
    def from_dict(cls, data: object) -> "UserGrant":
        if not isinstance(data, Mapping):
            raise MobileError(
                MobileReasonCode.GRANT_INVALID,
                "user grant must be a mapping",
            )
        return cls(
            scope=str(data.get("scope", "")),
            granted_at=str(data.get("granted_at", "")),
            expires_at=str(data.get("expires_at", "")),
            grant_id=str(data.get("grant_id", "")),
        )


# ----------------------------------------------------------------------
# Participation decision (the pure gate output)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ParticipationDecision:
    """The pure output of the participation gate: what the mobile node
    may do RIGHT NOW, derived only from the phase, the platform
    snapshot, and the active user grants.  ``defer_reason`` is ""
    exactly when participation is allowed."""

    phase: str
    network_kind: str
    online: bool
    metered: bool
    background_restricted: bool
    sends_allowed: bool
    discovery_allowed: bool
    defer_reason: str

    def __post_init__(self) -> None:
        if self.phase not in MobilePhase.values():
            raise MobileError(
                MobileReasonCode.INVALID_INPUT,
                "decision phase must be one of %s" % (MobilePhase.values(),),
            )
        if self.network_kind not in NetworkKind.values():
            raise MobileError(
                MobileReasonCode.INVALID_INPUT,
                "decision network_kind must be one of %s"
                % (NetworkKind.values(),),
            )
        if self.defer_reason and self.defer_reason not in DeferReason.values():
            raise MobileError(
                MobileReasonCode.INVALID_INPUT,
                "defer reason %r not in the frozen vocabulary"
                % (self.defer_reason,),
            )
        if self.sends_allowed and self.defer_reason:
            raise MobileError(
                MobileReasonCode.INVALID_INPUT,
                "sends_allowed and defer_reason are inconsistent",
            )
        if not self.sends_allowed and not self.defer_reason:
            raise MobileError(
                MobileReasonCode.INVALID_INPUT,
                "a closed gate must carry a defer reason",
            )

    def to_dict(self) -> dict:
        return {
            "phase": self.phase,
            "network_kind": self.network_kind,
            "online": self.online,
            "metered": self.metered,
            "background_restricted": self.background_restricted,
            "sends_allowed": self.sends_allowed,
            "discovery_allowed": self.discovery_allowed,
            "defer_reason": self.defer_reason,
        }


# ----------------------------------------------------------------------
# Mobile events (append-only decision journal)
# ----------------------------------------------------------------------


def derive_mobile_event_id(
    kind: str, sequence: int, instant: str, subject: str, detail: str, ref: str,
) -> str:
    content = {
        "kind": kind,
        "sequence": sequence,
        "instant": instant,
        "subject": subject,
        "detail": detail,
        "ref": ref,
    }
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes(content)
    ).hexdigest()


@dataclass(frozen=True)
class MobileEvent:
    """One append-only mobile-layer decision record."""

    kind: str
    sequence: int
    instant: str
    subject: str = ""
    detail: str = ""
    ref: str = ""
    event_id: str = ""

    def __post_init__(self) -> None:
        if self.kind not in MobileEventType.values():
            raise MobileError(
                MobileReasonCode.INVALID_INPUT,
                "mobile event kind %r not in the frozen vocabulary"
                % (self.kind,),
            )
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int):
            raise MobileError(
                MobileReasonCode.INVALID_INPUT,
                "event sequence must be an integer",
            )
        if self.sequence < 1:
            raise MobileError(
                MobileReasonCode.INVALID_INPUT,
                "event sequence must be >= 1",
            )
        _validate_instant(self.instant, "event instant")
        object.__setattr__(
            self,
            "event_id",
            self.event_id or derive_mobile_event_id(
                self.kind, self.sequence, self.instant,
                self.subject, self.detail, self.ref,
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
    def from_dict(cls, data: object) -> "MobileEvent":
        if not isinstance(data, Mapping):
            raise MobileError(
                MobileReasonCode.INVALID_INPUT,
                "mobile event must be a mapping",
            )
        return cls(
            kind=str(data.get("kind", "")),
            sequence=int(data.get("sequence", 0)),
            instant=str(data.get("instant", "")),
            subject=str(data.get("subject", "")),
            detail=str(data.get("detail", "")),
            ref=str(data.get("ref", "")),
            event_id=str(data.get("event_id", "")),
        )


def mobile_events_canonical_bytes(events: Tuple[MobileEvent, ...]) -> bytes:
    """Canonical bytes over the ordered event list (the WORK-033
    discipline: order + content, byte-stable)."""
    payload: List[dict] = [event.to_dict() for event in events]
    return canonical_json_bytes(payload)


def mobile_event_list_digest(events: Tuple[MobileEvent, ...]) -> str:
    return "sha256:" + hashlib.sha256(
        mobile_events_canonical_bytes(events)
    ).hexdigest()


# ----------------------------------------------------------------------
# Access-path view (WORK-013 vocabulary consumed as DATA)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class AccessPathView:
    """The mobile layer's continuity view of ONE tracked session's
    attachment to one access class.

    ``status`` uses the frozen WORK-013 constituent-path status
    vocabulary (ACTIVE / DEGRADED / FAILED) as DATA -- the mobile
    layer renders its own view through the accepted public
    vocabulary; it never operates the multipath authority.
    """

    access_class: str
    interface_name: str
    status: str

    def __post_init__(self) -> None:
        if self.access_class not in (NetworkKind.WIFI, NetworkKind.CELLULAR):
            raise MobileError(
                MobileReasonCode.INVALID_INPUT,
                "access path access_class must be a usable access kind "
                "(got %r)" % (self.access_class,),
            )
        if not isinstance(self.interface_name, str) or not self.interface_name:
            raise MobileError(
                MobileReasonCode.INVALID_INPUT,
                "access path interface_name must be a non-empty string",
            )
        if self.status not in ("ACTIVE", "DEGRADED", "FAILED"):
            raise MobileError(
                MobileReasonCode.INVALID_INPUT,
                "access path status must be a WORK-013 PathStatus value "
                "(got %r)" % (self.status,),
            )

    def to_dict(self) -> dict:
        return {
            "access_class": self.access_class,
            "interface_name": self.interface_name,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: object) -> "AccessPathView":
        if not isinstance(data, Mapping):
            raise MobileError(
                MobileReasonCode.INVALID_INPUT,
                "access path view must be a mapping",
            )
        return cls(
            access_class=str(data.get("access_class", "")),
            interface_name=str(data.get("interface_name", "")),
            status=str(data.get("status", "")),
        )


# ----------------------------------------------------------------------
# Command outcomes and run results
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class MobileOutcome:
    """One mobile command's participation verdict.  ``detail`` carries
    a digest or reference (never payload CONTENT, never secrets)."""

    command_id: str
    kind: str
    verdict: str
    reason: str = ""
    detail: str = ""

    def __post_init__(self) -> None:
        if self.verdict not in MobileVerdict.values():
            raise MobileError(
                MobileReasonCode.INVALID_INPUT,
                "mobile verdict must be one of %s (got %r)"
                % (MobileVerdict.values(), self.verdict),
            )
        if self.verdict == MobileVerdict.EXECUTED and self.reason:
            raise MobileError(
                MobileReasonCode.INVALID_INPUT,
                "an executed outcome carries no defer reason",
            )

    def to_dict(self) -> dict:
        return {
            "command_id": self.command_id,
            "kind": self.kind,
            "verdict": self.verdict,
            "reason": self.reason,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, data: object) -> "MobileOutcome":
        if not isinstance(data, Mapping):
            raise MobileError(
                MobileReasonCode.INVALID_INPUT,
                "mobile outcome must be a mapping",
            )
        return cls(
            command_id=str(data.get("command_id", "")),
            kind=str(data.get("kind", "")),
            verdict=str(data.get("verdict", "")),
            reason=str(data.get("reason", "")),
            detail=str(data.get("detail", "")),
        )


@dataclass(frozen=True)
class MobileRunResult:
    """The deterministic result of one mobile participation epoch:
    the agent's own status, the mobile verdicts, the final phase and
    connectivity, and the digests that make the whole scenario
    replayable."""

    status: str
    phase: str
    network_kind: str
    defer_reason: str
    executed: int
    deferred: int
    shed: int
    outcomes: Tuple[MobileOutcome, ...] = ()
    deferred_depth: int = 0
    agent_event_digest: str = ""
    mobile_event_digest: str = ""
    mobile_digest: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "phase": self.phase,
            "network_kind": self.network_kind,
            "defer_reason": self.defer_reason,
            "executed": self.executed,
            "deferred": self.deferred,
            "shed": self.shed,
            "outcomes": [outcome.to_dict() for outcome in self.outcomes],
            "deferred_depth": self.deferred_depth,
            "agent_event_digest": self.agent_event_digest,
            "mobile_event_digest": self.mobile_event_digest,
            "mobile_digest": self.mobile_digest,
        }


# ----------------------------------------------------------------------
# Durable snapshot (restart/recovery state)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class MobileSnapshot:
    """The durable mobile-layer state for restart/recovery.

    Pure DATA: the user grants, the deferred-send queue (with original
    deferred-at instants so TTLs keep aging across downtime), the
    tracked-session continuity views, and the journal continuation
    point.  Agent authority state is NOT carried here (a killed
    process loses its runtime; the successor re-establishes through
    the ordinary path and the loss is recorded honestly).
    """

    phase: str
    grants: Tuple[UserGrant, ...] = ()
    deferred: Tuple[Mapping[str, str], ...] = ()
    sessions: Tuple[Mapping[str, str], ...] = ()
    event_sequence: int = 0
    event_digest: str = ""
    produced_at: str = ""
    snapshot_id: str = ""

    def __post_init__(self) -> None:
        if self.phase not in MobilePhase.values():
            raise MobileError(
                MobileReasonCode.SNAPSHOT_INVALID,
                "snapshot phase must be one of %s" % (MobilePhase.values(),),
            )
        if isinstance(self.event_sequence, bool) or not isinstance(
            self.event_sequence, int
        ) or self.event_sequence < 0:
            raise MobileError(
                MobileReasonCode.SNAPSHOT_INVALID,
                "snapshot event_sequence must be a non-negative integer",
            )
        _validate_instant(self.produced_at, "produced_at")
        object.__setattr__(
            self,
            "snapshot_id",
            self.snapshot_id or self._derive_snapshot_id(),
        )

    def _derive_snapshot_id(self) -> str:
        content = {
            "phase": self.phase,
            "grants": [grant.to_dict() for grant in self.grants],
            "deferred": [dict(entry) for entry in self.deferred],
            "sessions": [dict(entry) for entry in self.sessions],
            "event_sequence": self.event_sequence,
            "event_digest": self.event_digest,
            "produced_at": self.produced_at,
        }
        return "sha256:" + hashlib.sha256(
            canonical_json_bytes(content)
        ).hexdigest()

    def to_dict(self) -> dict:
        return {
            "phase": self.phase,
            "grants": [grant.to_dict() for grant in self.grants],
            "deferred": [dict(entry) for entry in self.deferred],
            "sessions": [dict(entry) for entry in self.sessions],
            "event_sequence": self.event_sequence,
            "event_digest": self.event_digest,
            "produced_at": self.produced_at,
            "snapshot_id": self.snapshot_id,
        }

    @classmethod
    def from_dict(cls, data: object) -> "MobileSnapshot":
        if not isinstance(data, Mapping):
            raise MobileError(
                MobileReasonCode.SNAPSHOT_INVALID,
                "mobile snapshot must be a mapping",
            )
        grants_data = data.get("grants", ())
        deferred_data = data.get("deferred", ())
        sessions_data = data.get("sessions", ())
        if not isinstance(grants_data, (list, tuple)) or not isinstance(
            deferred_data, (list, tuple)
        ) or not isinstance(sessions_data, (list, tuple)):
            raise MobileError(
                MobileReasonCode.SNAPSHOT_INVALID,
                "snapshot grants/deferred/sessions must be sequences",
            )
        grants = tuple(
            UserGrant.from_dict(entry) for entry in grants_data
        )
        deferred = tuple(dict(entry) for entry in deferred_data)
        sessions = tuple(dict(entry) for entry in sessions_data)
        return cls(
            phase=str(data.get("phase", "")),
            grants=grants,
            deferred=deferred,
            sessions=sessions,
            event_sequence=int(data.get("event_sequence", 0)),
            event_digest=str(data.get("event_digest", "")),
            produced_at=str(data.get("produced_at", "")),
            snapshot_id=str(data.get("snapshot_id", "")),
        )
