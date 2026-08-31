"""WORK-042 platform value model: events, observations, and bindings.

The frozen value records of the event-driven platform integration
family (ACR-006, authorization WORK-042-CORE-001 / DEC-0055):

- **PlatformEvent** -- one authoritative platform observation
  delivered as an ordered change notification.  An event is
  OBSERVATION DATA only: it records what an authoritative platform
  source reported (interface facts, OS platform-state facts) with
  its provenance.  It is never protocol truth, never a session,
  route, policy, or transport fact, and never a decision.

- **SessionBindingRef** -- a checkpoint-scoped REFERENCE (pure DATA)
  to a logical session and the network path that carried it.  The
  platform layer records these references so process death can be
  reported honestly; it never owns, mints, or mutates session
  identity (WORK-012 owns it).

- **IngestionOutcome** -- what the ingestion boundary did with one
  observation: ``appended`` (state changed), ``stale`` (journaled,
  deterministically inert -- an older observation never causes a
  transition), or ``duplicate`` (already journaled; idempotent
  no-op).

Identity discipline (the WORK-004/007/012/041 convention):
``event_id`` is a CONTENT-DERIVED fingerprint --
``"sha256:" + sha256(canonical_json_bytes(content))`` over (event
kind, authoritative source, platform reference, observation payload,
observed instant).  It is a fingerprint ONLY: not a NodeID, not a
session id, never trust, never an authorization.  The constructor
mechanically verifies the content binding (empty id means "derive
it"; a non-empty id MUST equal the recomputed fingerprint), so a
tampered or deserialized event can never carry an attacker-chosen
id.

Temporal discipline: every instant is an RFC 3339 UTC string
validated through the WORK-003 ``parse_instant`` seam (lexicographic
order == chronological order for the fixed-width form, so instants
are monotonic-orderable DATA).  No wall-clock reads, no UUIDs, no
randomness, no environment-dependent identity anywhere in this
family.  Iteration over event sets is sorted, so identical logical
inputs produce identical canonical bytes.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Tuple

from protocol.canonicalization import canonical_json_bytes
from protocol.temporal import TemporalError, parse_instant

from agent.model import InterfaceSnapshot

from mobile.model import PlatformSnapshot

from .errors import PlatformError, PlatformReasonCode


def _wrap_payload_error(error: Exception, label: str) -> PlatformError:
    """Re-wrap a composed-family payload failure into the typed
    platform vocabulary (fail-closed isolation: an agent-family or
    mobile-family error never crosses the boundary untyped)."""
    detail = getattr(error, "detail", "") or str(error)
    return PlatformError(
        PlatformReasonCode.OBSERVATION_INVALID,
        "%s rejected by the composed observation model: %s"
        % (label, detail),
    )


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise PlatformError(
            PlatformReasonCode.INVALID_INPUT,
            "%s must be a non-empty string" % label,
        )
    return value


def _require_instant(value: object, label: str) -> str:
    """RFC 3339 UTC instants (WORK-003 validation, fail closed)."""
    if not isinstance(value, str) or not value:
        raise PlatformError(
            PlatformReasonCode.INVALID_INPUT,
            "%s must be an RFC 3339 UTC instant string" % label,
        )
    try:
        parse_instant(value)
    except TemporalError as error:
        raise PlatformError(
            PlatformReasonCode.INVALID_INPUT,
            "%s is not a valid RFC 3339 UTC instant: %s" % (label, error),
        ) from error
    return value


#: The frozen platform-event kind vocabulary.  These are the two
#: observation families that exist on the ACCEPTED seams this
#: boundary composes (WORK-033 ``InterfaceSource`` interface
#: observations; WORK-035 ``MobilePlatformSource`` OS platform-state
#: observations), plus the removal notification the interface
#: family requires so that a disappeared interface is a journaled
#: observation (not an ambient side effect).  No other kinds are
#: invented: ACR-006 requires platform events that "carry the
#: observation that caused the event" -- these three ARE that
#: vocabulary over the existing seams.
class EventKind:
    INTERFACE_OBSERVATION = "interface-observation"
    INTERFACE_REMOVAL = "interface-removal"
    PLATFORM_STATE_OBSERVATION = "platform-state-observation"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.INTERFACE_OBSERVATION,
            cls.INTERFACE_REMOVAL,
            cls.PLATFORM_STATE_OBSERVATION,
        )


#: Default provenance labels for the two composed seams (DATA only;
#: a host may pass its own source label to distinguish its own
#: platform adapter instances).
DEFAULT_INTERFACE_SOURCE = "interface-source"
DEFAULT_PLATFORM_SOURCE = "mobile-platform-source"

#: The platform reference of the singleton OS platform-state
#: observation (the WORK-035 ``PlatformSnapshot`` family has exactly
#: one subject: the host platform itself).
PLATFORM_STATE_REF = "platform"


def platform_event_content(
    kind: str,
    source: str,
    platform_ref: str,
    payload: Mapping[str, Any],
    observed_at: str,
) -> Dict[str, Any]:
    """The canonical identity content of a PlatformEvent.

    The payload is normalized to a plain dict mapping (sorted at
    serialization time by the canonical profile); volatile ordering
    of payload keys never affects identity.
    """
    return {
        "kind": kind,
        "source": source,
        "platform_ref": platform_ref,
        "payload": dict(payload),
        "observed_at": observed_at,
    }


def derive_platform_event_id(
    kind: str,
    source: str,
    platform_ref: str,
    payload: Mapping[str, Any],
    observed_at: str,
) -> str:
    """The content-derived PlatformEvent fingerprint (identity DATA
    only)."""
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes(
            platform_event_content(
                kind, source, platform_ref, payload, observed_at
            )
        )
    ).hexdigest()


@dataclass(frozen=True)
class PlatformEvent:
    """One authoritative platform observation as a change
    notification (pure DATA + provenance).

    Content binding: ``event_id`` MUST equal the fingerprint
    recomputed from (kind, source, platform_ref, payload,
    observed_at) -- enforced at construction, so every event (built
    by the boundary, redelivered by a host, or deserialized) passes
    through the same tamper-evident gate.

    ``payload`` is the observation itself: an ``InterfaceSnapshot``
    dict (interface-observation), the removed interface name
    (interface-removal), or a ``PlatformSnapshot`` dict
    (platform-state-observation).  Kind and payload family are
    verified against each other -- a platform-state payload in an
    interface event is rejected (fail closed).
    """

    event_id: str
    kind: str
    source: str
    platform_ref: str
    payload: Dict[str, Any]
    observed_at: str

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, str):
            raise PlatformError(
                PlatformReasonCode.INVALID_INPUT,
                "event_id must be a string",
            )
        if self.kind not in EventKind.values():
            raise PlatformError(
                PlatformReasonCode.EVENT_INVALID,
                "event kind %r must be one of %s (the frozen "
                "platform-observation vocabulary)"
                % (self.kind, list(EventKind.values())),
            )
        _require_text(self.source, "source")
        _require_text(self.platform_ref, "platform_ref")
        if not isinstance(self.payload, dict):
            raise PlatformError(
                PlatformReasonCode.EVENT_INVALID,
                "event payload must be a mapping (the observation DATA)",
            )
        _require_instant(self.observed_at, "observed_at")
        self._validate_payload_family()
        expected = derive_platform_event_id(
            self.kind, self.source, self.platform_ref,
            self.payload, self.observed_at,
        )
        if self.event_id == "":
            object.__setattr__(self, "event_id", expected)
        elif self.event_id != expected:
            raise PlatformError(
                PlatformReasonCode.EVENT_INVALID,
                "event_id %r does not match the derived fingerprint %r "
                "(content binding: kind + source + platform_ref + payload "
                "+ observed_at -- tampered or misbound event id rejected)"
                % (self.event_id[:80], expected[:80]),
            )

    def _validate_payload_family(self) -> None:
        """Kind/payload coherence (fail closed on mismatched
        families)."""
        if self.kind == EventKind.INTERFACE_OBSERVATION:
            try:
                snapshot = InterfaceSnapshot.from_dict(self.payload)
            except Exception as error:  # typed re-wrap (fail closed)
                raise _wrap_payload_error(error, "interface observation") from error
            if snapshot.name != self.platform_ref:
                raise PlatformError(
                    PlatformReasonCode.EVENT_INVALID,
                    "interface observation payload name %r does not "
                    "match the event platform_ref %r"
                    % (snapshot.name, self.platform_ref),
                )
        elif self.kind == EventKind.INTERFACE_REMOVAL:
            name = self.payload.get("interface_name", "")
            if not isinstance(name, str) or not name:
                raise PlatformError(
                    PlatformReasonCode.EVENT_INVALID,
                    "interface-removal payload requires a non-empty "
                    "'interface_name'",
                )
            if name != self.platform_ref:
                raise PlatformError(
                    PlatformReasonCode.EVENT_INVALID,
                    "interface-removal payload name %r does not match "
                    "the event platform_ref %r" % (name, self.platform_ref),
                )
        else:
            # The platform-state family constructor IS the validation
            # (vocabulary + coherence, fail closed on malformed).
            try:
                PlatformSnapshot.from_dict(self.payload)
            except Exception as error:  # typed re-wrap (fail closed)
                raise _wrap_payload_error(
                    error, "platform-state observation"
                ) from error
            if self.platform_ref != PLATFORM_STATE_REF:
                raise PlatformError(
                    PlatformReasonCode.EVENT_INVALID,
                    "platform-state-observation platform_ref must be %r "
                    "(the singleton platform subject), got %r"
                    % (PLATFORM_STATE_REF, self.platform_ref),
                )

    def interface_snapshot(self) -> InterfaceSnapshot:
        """The observation as an ``InterfaceSnapshot`` (interface
        family only; otherwise fail closed)."""
        if self.kind != EventKind.INTERFACE_OBSERVATION:
            raise PlatformError(
                PlatformReasonCode.EVENT_INVALID,
                "interface_snapshot() requires an interface-observation "
                "event (kind %r)" % self.kind,
            )
        try:
            return InterfaceSnapshot.from_dict(self.payload)
        except Exception as error:  # typed re-wrap (fail closed)
            raise _wrap_payload_error(error, "interface observation") from error

    def platform_snapshot(self) -> PlatformSnapshot:
        """The observation as a ``PlatformSnapshot`` (platform-state
        family only; otherwise fail closed)."""
        if self.kind != EventKind.PLATFORM_STATE_OBSERVATION:
            raise PlatformError(
                PlatformReasonCode.EVENT_INVALID,
                "platform_snapshot() requires a platform-state-observation "
                "event (kind %r)" % self.kind,
            )
        try:
            return PlatformSnapshot.from_dict(self.payload)
        except Exception as error:  # typed re-wrap (fail closed)
            raise _wrap_payload_error(
                error, "platform-state observation"
            ) from error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "kind": self.kind,
            "source": self.source,
            "platform_ref": self.platform_ref,
            "payload": dict(self.payload),
            "observed_at": self.observed_at,
        }

    @classmethod
    def from_dict(cls, data: object) -> "PlatformEvent":
        if not isinstance(data, Mapping):
            raise PlatformError(
                PlatformReasonCode.EVENT_INVALID,
                "platform event must be a mapping",
            )
        payload = data.get("payload", {})
        if not isinstance(payload, Mapping):
            raise PlatformError(
                PlatformReasonCode.EVENT_INVALID,
                "platform event payload must be a mapping",
            )
        try:
            return cls(
                event_id=str(data.get("event_id", "")),
                kind=str(data.get("kind", "")),
                source=str(data.get("source", "")),
                platform_ref=str(data.get("platform_ref", "")),
                payload=dict(payload),
                observed_at=str(data.get("observed_at", "")),
            )
        except PlatformError as error:
            raise PlatformError(
                PlatformReasonCode.EVENT_INVALID,
                "platform event round-trip rejected: %s" % error.detail,
            ) from error

    def payload_digest(self) -> str:
        """Content digest over the observation payload (DATA)."""
        return "sha256:" + hashlib.sha256(
            canonical_json_bytes(self.payload)
        ).hexdigest()


def event_list_digest(events: List[PlatformEvent]) -> str:
    """Deterministic digest over the ordered event list (identity
    DATA for verification)."""
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes([event.to_dict() for event in events])
    ).hexdigest()


# ---------------------------------------------------------------------------
# Session binding references (checkpoint DATA; never authority)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SessionBindingRef:
    """A checkpoint-scoped REFERENCE to a logical session held by
    the process at checkpoint time.

    Pure DATA: ``session_id`` and ``network_path_id`` are references
    minted by their owning authorities (WORK-012 / WORK-041) and are
    recorded here ONLY so that process death can be reported
    honestly.  This record carries no authority, grants no
    continuity, and never recreates anything.
    """

    session_id: str
    network_path_id: str
    interface_name: str

    def __post_init__(self) -> None:
        _require_text(self.session_id, "session_id")
        _require_text(self.network_path_id, "network_path_id")
        _require_text(self.interface_name, "interface_name")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "network_path_id": self.network_path_id,
            "interface_name": self.interface_name,
        }

    @classmethod
    def from_dict(cls, data: object) -> "SessionBindingRef":
        if not isinstance(data, Mapping):
            raise PlatformError(
                PlatformReasonCode.STATE_INVALID,
                "session binding reference must be a mapping",
            )
        return cls(
            session_id=str(data.get("session_id", "")),
            network_path_id=str(data.get("network_path_id", "")),
            interface_name=str(data.get("interface_name", "")),
        )

    def binding_key(self) -> Tuple[str, str]:
        """The deterministic sort/key identity of a binding
        reference."""
        return (self.session_id, self.network_path_id)


# ---------------------------------------------------------------------------
# Ingestion outcome
# ---------------------------------------------------------------------------


class IngestionStatus:
    """The frozen ingestion-outcome vocabulary.

    ``appended``  -- the observation changed the reconciled state.
    ``stale``     -- the observation was journaled but is
                     deterministically inert (an older observation
                     for its reference never causes a transition --
                     ACR-006 section 2).
    ``duplicate`` -- the exact event is already journaled; the
                     idempotent no-op (replay safety).
    """

    APPENDED = "appended"
    STALE = "stale"
    DUPLICATE = "duplicate"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.APPENDED, cls.STALE, cls.DUPLICATE)


@dataclass(frozen=True)
class IngestionOutcome:
    """What the boundary did with one observation (pure DATA)."""

    status: str
    event_id: str
    record_id: str
    sequence: int
    detail: str = ""

    def __post_init__(self) -> None:
        if self.status not in IngestionStatus.values():
            raise PlatformError(
                PlatformReasonCode.INVALID_INPUT,
                "ingestion status %r must be one of %s"
                % (self.status, list(IngestionStatus.values())),
            )
        _require_text(self.event_id, "event_id")
        if self.status == IngestionStatus.DUPLICATE:
            if self.record_id != "" or self.sequence != 0:
                raise PlatformError(
                    PlatformReasonCode.INVALID_INPUT,
                    "a duplicate ingestion outcome carries no new record",
                )
        else:
            _require_text(self.record_id, "record_id")
            if isinstance(self.sequence, bool) or not isinstance(
                self.sequence, int
            ):
                raise PlatformError(
                    PlatformReasonCode.INVALID_INPUT,
                    "ingestion sequence must be an integer",
                )
            if self.sequence < 1:
                raise PlatformError(
                    PlatformReasonCode.INVALID_INPUT,
                    "ingestion sequence must be >= 1",
                )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "event_id": self.event_id,
            "record_id": self.record_id,
            "sequence": self.sequence,
            "detail": self.detail,
        }


__all__ = [
    "DEFAULT_INTERFACE_SOURCE",
    "DEFAULT_PLATFORM_SOURCE",
    "PLATFORM_STATE_REF",
    "EventKind",
    "IngestionOutcome",
    "IngestionStatus",
    "PlatformEvent",
    "SessionBindingRef",
    "derive_platform_event_id",
    "event_list_digest",
    "platform_event_content",
]
