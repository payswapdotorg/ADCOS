"""WORK-041 session-continuity integration.

Session continuity verification reads the production session
authority through its PUBLIC surface only (``AgentRuntime.sessions``
-> ``SessionStore.get`` / ``get_events``): the NetworkPath family
never mutates session internals and never re-creates a session to
make handover succeed.

The continuity contract (W041 acceptance criterion 1):

    physical path changes  !=  logical session replacement

so across a validated handover the following must hold:

- ``session_id_before == session_id_after`` (identity stability);
- the session is still ESTABLISHED (the authority owns lifecycle
  truth);
- exactly ONE creation event exists in the session's append-only
  event journal (the session was not destroyed and re-created);
- the event journal only grew (monotonic history).

:class:`SessionContinuityFacts` records these as DATA so callers
(batteries, monitoring, review evidence) can assert them without
touching private state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from agent.runtime import AgentRuntime
from sessions import SessionState

from .errors import NetworkPathError, NetworkPathReasonCode

#: The session-authority event type that records session creation.
SESSION_CREATED_EVENT_TYPE = "created"


@dataclass(frozen=True)
class SessionContinuityFacts:
    """The public, read-only continuity facts for one session."""

    session_id: str
    exists: bool
    state: str
    event_count: int
    created_event_count: int

    def to_dict(self) -> Dict[str, str]:
        return {
            "session_id": self.session_id,
            "exists": "true" if self.exists else "false",
            "state": self.state,
            "event_count": str(self.event_count),
            "created_event_count": str(self.created_event_count),
        }

    @property
    def established(self) -> bool:
        return self.exists and self.state == SessionState.ESTABLISHED

    @property
    def never_recreated(self) -> bool:
        """True iff the session was created exactly once (no
        destroy-and-recreate behind a stable id)."""
        return self.created_event_count == 1


def session_continuity_facts(
    runtime: AgentRuntime, session_id: str
) -> SessionContinuityFacts:
    """Read one session's continuity facts through the public seam."""
    if not isinstance(runtime, AgentRuntime):
        raise NetworkPathError(
            NetworkPathReasonCode.INVALID_INPUT,
            "runtime must be an AgentRuntime",
        )
    if not isinstance(session_id, str) or not session_id:
        raise NetworkPathError(
            NetworkPathReasonCode.INVALID_INPUT,
            "session_id must be a non-empty string",
        )
    session = runtime.sessions.get(session_id)
    if session is None:
        return SessionContinuityFacts(
            session_id=session_id,
            exists=False,
            state="",
            event_count=0,
            created_event_count=0,
        )
    events = runtime.sessions.get_events(session_id)
    created = sum(
        1 for event in events if event.event_type == SESSION_CREATED_EVENT_TYPE
    )
    return SessionContinuityFacts(
        session_id=session_id,
        exists=True,
        state=session.state,
        event_count=len(events),
        created_event_count=created,
    )


def assert_session_continuity(
    before: SessionContinuityFacts, after: SessionContinuityFacts
) -> None:
    """Fail closed unless continuity held across a path change.

    The checks are the W041 criterion exactly: same session_id, still
    established, created exactly once both sides, and a history that
    only grew.
    """
    if before.session_id != after.session_id:
        raise NetworkPathError(
            NetworkPathReasonCode.INVALID_INPUT,
            "continuity check received two different session ids "
            "(%r vs %r)" % (before.session_id[:23], after.session_id[:23]),
        )
    if not after.exists:
        raise NetworkPathError(
            NetworkPathReasonCode.SESSION_UNKNOWN,
            "session %r no longer exists after the path change (the "
            "logical session was destroyed -- continuity violated)"
            % after.session_id[:23],
        )
    if after.state != SessionState.ESTABLISHED:
        raise NetworkPathError(
            NetworkPathReasonCode.SESSION_UNKNOWN,
            "session %r is %s after the path change (expected "
            "ESTABLISHED -- continuity violated)"
            % (after.session_id[:23], after.state),
        )
    if after.created_event_count != before.created_event_count:
        raise NetworkPathError(
            NetworkPathReasonCode.INVALID_INPUT,
            "session %r creation-event count changed (%d -> %d): the "
            "session was re-created (continuity violated)"
            % (
                after.session_id[:23],
                before.created_event_count,
                after.created_event_count,
            ),
        )
    if after.event_count < before.event_count:
        raise NetworkPathError(
            NetworkPathReasonCode.INVALID_INPUT,
            "session %r event history shrank (%d -> %d): the append-only "
            "journal was reset (continuity violated)"
            % (after.session_id[:23], before.event_count, after.event_count),
        )
