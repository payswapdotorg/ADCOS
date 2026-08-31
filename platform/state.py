"""WORK-042 deterministic event/snapshot reconciliation.

Snapshots remain STATE REPRESENTATION; events are CHANGE
NOTIFICATIONS (ACR-006 section 1).  This module owns exactly the
deterministic function the contract requires:

    event stream + prior snapshot  ->  same resulting snapshot

:func:`fold_state` is a PURE fold over the ordered journal record
list; :func:`apply_record` is one deterministic step.  The fold is
order-total (journal sequence is the total order), idempotent
(replaying the same records reproduces the same state byte-for-
byte), and fail-closed on contradiction:

- per platform reference, the latest observation is the record with
  the greatest (observed_at, sequence) key -- an OLDER observation
  is deterministically INERT (``stale``: ACR-006 section 2, "must
  not infer a transition from stale or concurrently re-read
  state");
- two events for the same (kind, platform_ref, observed_at) with
  DIFFERENT content are a CONTRADICTION -- the fold fails closed
  (the journal ingest gate rejects them first; the fold re-checks
  on replay so a hand-crafted store can never smuggle one through);
- journal records that are honest OUTCOMES (session-loss records)
  are kept distinct from observations: they contribute to
  ``lost_sessions`` and never to platform state.

Session discipline: ``lost_sessions`` is a fold-derived SET of
session-id REFERENCES recorded by session-loss records.  It is
evidence of honest reporting, never authority: the session
authority (WORK-012) alone owns session state, and this module
never mints, recreates, or mutates a session.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

from protocol.canonicalization import canonical_json_bytes
import hashlib

from .errors import PlatformError, PlatformReasonCode
from .journal import JournalRecord, JournalRecordKind
from .model import (
    EventKind,
    PlatformEvent,
)


# ---------------------------------------------------------------------------
# The reconciled state (state representation, pure DATA)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ObservationRecord:
    """The latest observation for one platform reference (DATA).

    ``kind`` distinguishes a present interface observation from an
    interface-removal notification (the latest record for a removed
    interface has kind ``interface-removal`` and no snapshot
    payload).  ``sequence`` is the journal sequence of the event
    that set this record, so the state is fully reconstructible
    from the journal alone.
    """

    event_id: str
    kind: str
    source: str
    platform_ref: str
    observed_at: str
    payload: Dict[str, Any]
    sequence: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "kind": self.kind,
            "source": self.source,
            "platform_ref": self.platform_ref,
            "observed_at": self.observed_at,
            "payload": dict(self.payload),
            "sequence": self.sequence,
        }

    @classmethod
    def from_dict(cls, data: object) -> "ObservationRecord":
        if not isinstance(data, Mapping):
            raise PlatformError(
                PlatformReasonCode.STATE_INVALID,
                "observation record must be a mapping",
            )
        payload = data.get("payload", {})
        if not isinstance(payload, Mapping):
            raise PlatformError(
                PlatformReasonCode.STATE_INVALID,
                "observation record payload must be a mapping",
            )
        sequence = data.get("sequence", 0)
        if isinstance(sequence, bool) or not isinstance(sequence, int):
            raise PlatformError(
                PlatformReasonCode.STATE_INVALID,
                "observation record sequence must be an integer",
            )
        return cls(
            event_id=str(data.get("event_id", "")),
            kind=str(data.get("kind", "")),
            source=str(data.get("source", "")),
            platform_ref=str(data.get("platform_ref", "")),
            observed_at=str(data.get("observed_at", "")),
            payload=dict(payload),
            sequence=sequence,
        )

    def order_key(self) -> Tuple[str, int]:
        """The deterministic latest-observation ordering key."""
        return (self.observed_at, self.sequence)


@dataclass(frozen=True)
class ReconciledState:
    """The deterministic snapshot of the platform integration state.

    Pure fold output: per-interface latest observations, the OS
    platform-state observation, and the fold-derived set of
    honestly-recorded lost-session REFERENCES.  This is a state
    REPRESENTATION -- never an authority over sessions, paths,
    routes, or policy.
    """

    interface_records: Tuple[ObservationRecord, ...] = ()
    platform_record: Optional[ObservationRecord] = None
    lost_sessions: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for record in self.interface_records:
            if not isinstance(record, ObservationRecord):
                raise PlatformError(
                    PlatformReasonCode.STATE_INVALID,
                    "interface_records must contain ObservationRecord values",
                )
        if self.platform_record is not None and not isinstance(
            self.platform_record, ObservationRecord
        ):
            raise PlatformError(
                PlatformReasonCode.STATE_INVALID,
                "platform_record must be an ObservationRecord or None",
            )
        names = [record.platform_ref for record in self.interface_records]
        if len(names) != len(set(names)):
            raise PlatformError(
                PlatformReasonCode.STATE_INVALID,
                "duplicate platform references in a reconciled state "
                "(the fold keeps exactly one record per reference)",
            )

    # -- accessors ---------------------------------------------------------

    def interface_map(self) -> Dict[str, ObservationRecord]:
        """The latest observation per interface reference."""
        return {
            record.platform_ref: record for record in self.interface_records
        }

    @property
    def interface_records_map(self) -> Dict[str, ObservationRecord]:
        """Alias used by the polling fallback (readable name)."""
        return self.interface_map()

    def present_interface_names(self) -> Tuple[str, ...]:
        """Interface references whose latest observation is a PRESENT
        interface observation (not a removal)."""
        return tuple(
            sorted(
                record.platform_ref
                for record in self.interface_records
                if record.kind == EventKind.INTERFACE_OBSERVATION
            )
        )

    def removed_interface_names(self) -> Tuple[str, ...]:
        """Interface references whose latest observation is a removal
        notification."""
        return tuple(
            sorted(
                record.platform_ref
                for record in self.interface_records
                if record.kind == EventKind.INTERFACE_REMOVAL
            )
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "interface_records": [
                record.to_dict() for record in self.interface_records
            ],
            "platform_record": (
                self.platform_record.to_dict()
                if self.platform_record is not None
                else None
            ),
            "lost_sessions": list(self.lost_sessions),
        }

    @classmethod
    def from_dict(cls, data: object) -> "ReconciledState":
        if not isinstance(data, Mapping):
            raise PlatformError(
                PlatformReasonCode.STATE_INVALID,
                "reconciled state must be a mapping",
            )
        raw_interfaces = data.get("interface_records", [])
        if not isinstance(raw_interfaces, (list, tuple)):
            raise PlatformError(
                PlatformReasonCode.STATE_INVALID,
                "reconciled state interface_records must be a sequence",
            )
        interfaces = tuple(
            ObservationRecord.from_dict(item) for item in raw_interfaces
        )
        raw_platform = data.get("platform_record")
        platform = (
            ObservationRecord.from_dict(raw_platform)
            if raw_platform is not None
            else None
        )
        raw_lost = data.get("lost_sessions", [])
        if not isinstance(raw_lost, (list, tuple)):
            raise PlatformError(
                PlatformReasonCode.STATE_INVALID,
                "reconciled state lost_sessions must be a sequence",
            )
        return cls(
            interface_records=tuple(
                sorted(interfaces, key=lambda record: record.platform_ref)
            ),
            platform_record=platform,
            lost_sessions=tuple(sorted(str(item) for item in raw_lost)),
        )

    def state_digest(self) -> str:
        """Content digest over the canonical state (identity DATA)."""
        return "sha256:" + hashlib.sha256(
            canonical_json_bytes(self.to_dict())
        ).hexdigest()

    def state_equal(self, other: "ReconciledState") -> bool:
        """Deterministic structural equality (canonical bytes)."""
        return self.to_dict() == other.to_dict()


# ---------------------------------------------------------------------------
# The deterministic fold
# ---------------------------------------------------------------------------


def _event_order_key(event: PlatformEvent, sequence: int) -> Tuple[str, int]:
    return (event.observed_at, sequence)


def apply_record(
    state: ReconciledState, record: JournalRecord
) -> ReconciledState:
    """One deterministic reconciliation step (pure).

    Fail-closed re-verification: the fold independently re-derives
    the event content binding and the contradiction discipline, so
    replaying a hand-crafted or tampered journal fails closed even
    if it bypassed the ingest gate.
    """
    if not isinstance(state, ReconciledState):
        raise PlatformError(
            PlatformReasonCode.INVALID_INPUT,
            "state must be a ReconciledState",
        )
    if not isinstance(record, JournalRecord):
        raise PlatformError(
            PlatformReasonCode.INVALID_INPUT,
            "record must be a JournalRecord",
        )

    if record.record_kind == JournalRecordKind.SESSION_LOSS:
        lost = set(state.lost_sessions)
        session_id = record.session_loss_session_id()
        if session_id:
            lost.add(session_id)
        return ReconciledState(
            interface_records=state.interface_records,
            platform_record=state.platform_record,
            lost_sessions=tuple(sorted(lost)),
        )

    event = record.event
    if event.kind == EventKind.PLATFORM_STATE_OBSERVATION:
        current = state.platform_record
        if current is not None:
            _reject_contradiction(current, event, record.sequence)
            if _event_order_key(event, record.sequence) <= current.order_key():
                return state  # deterministically inert (stale)
        return ReconciledState(
            interface_records=state.interface_records,
            platform_record=ObservationRecord(
                event_id=event.event_id,
                kind=event.kind,
                source=event.source,
                platform_ref=event.platform_ref,
                observed_at=event.observed_at,
                payload=dict(event.payload),
                sequence=record.sequence,
            ),
            lost_sessions=state.lost_sessions,
        )

    # interface family: keep exactly one record per reference
    records = {
        record_.platform_ref: record_ for record_ in state.interface_records
    }
    current = records.get(event.platform_ref)
    if current is not None:
        _reject_contradiction(current, event, record.sequence)
        if _event_order_key(event, record.sequence) <= current.order_key():
            return state  # deterministically inert (stale)
    records[event.platform_ref] = ObservationRecord(
        event_id=event.event_id,
        kind=event.kind,
        source=event.source,
        platform_ref=event.platform_ref,
        observed_at=event.observed_at,
        payload=dict(event.payload),
        sequence=record.sequence,
    )
    return ReconciledState(
        interface_records=tuple(
            sorted(records.values(), key=lambda item: item.platform_ref)
        ),
        platform_record=state.platform_record,
        lost_sessions=state.lost_sessions,
    )


def _reject_contradiction(
    current: ObservationRecord, event: PlatformEvent, sequence: int
) -> None:
    """Two events for the same reference at the same observed
    instant with different content are a contradiction (fail
    closed).

    Same (platform_ref, observed_at) with fully identical content is
    the same event by construction (content-derived ids) and can
    only reach the fold as a journal duplicate, which the ingest
    gate already rejects; a genuinely equal-instant, different-
    content pair -- including an observation and a removal for one
    reference at one instant -- is the platform reporting two
    different states for one reference at one instant: ambiguous
    and rejected whole.
    """
    if current.platform_ref != event.platform_ref:
        return
    if current.observed_at != event.observed_at:
        return
    if (
        current.kind == event.kind
        and current.source == event.source
        and current.payload == dict(event.payload)
        and current.event_id == event.event_id
    ):
        raise PlatformError(
            PlatformReasonCode.JOURNAL_APPEND_REJECTED,
            "duplicate event %r reached the fold (the journal must "
            "reject duplicates at append; a tampered store is "
            "suspected)" % event.event_id[:23],
        )
    raise PlatformError(
        PlatformReasonCode.EVENT_CONTRADICTORY,
        "contradictory platform events: reference %r reported "
        "different content at the same observed instant %s "
        "(event %r vs %r -- fail closed)"
        % (
            event.platform_ref,
            event.observed_at,
            current.event_id[:23],
            event.event_id[:23],
        ),
    )


def fold_state(records: List[JournalRecord]) -> ReconciledState:
    """The deterministic reconciliation of an ordered record list.

    ``fold_state(records)`` is a pure function: the same record list
    always produces the same state (idempotent replay).
    """
    state = ReconciledState()
    for record in records:
        state = apply_record(state, record)
    return state


def fold_state_from(
    prior: ReconciledState, records: List[JournalRecord]
) -> ReconciledState:
    """Fold a journal TAIL on top of a prior (checkpointed) state.

    Deterministic equivalence (battery-pinned):
    ``fold_state_from(fold_state(head), tail) == fold_state(head + tail)``
    for any journal split -- the fold is a sequential function, so
    checkpointed reconstruction and full replay agree byte-for-byte.
    """
    if not isinstance(prior, ReconciledState):
        raise PlatformError(
            PlatformReasonCode.INVALID_INPUT,
            "prior must be a ReconciledState (the checkpoint state)",
        )
    state = prior
    for record in records:
        state = apply_record(state, record)
    return state


__all__ = [
    "ObservationRecord",
    "ReconciledState",
    "apply_record",
    "fold_state",
    "fold_state_from",
]
