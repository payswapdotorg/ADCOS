"""WORK-042 append-only journal and durable persistence seam.

The journal-first durable core of ACR-006 section 3:

    immutable event records
        + append-only file discipline
        + content-derived record ids
        + a hash chain over (sequence, content, previous link)
        = tamper-evident, deterministically replayable history

Discipline (battery-pinned):

- **content-derived ids**: every ``record_id`` is the fingerprint of
  (sequence, record content, previous record id); every event
  ``event_id`` is the fingerprint of its observation content.  Both
  are mechanically verified at construction, so a tampered or
  deserialized record can never carry an attacker-chosen id.
- **canonical serialization**: one canonical-JSON line per record
  (the WORK-003 profile); identical logical histories produce
  byte-identical journals.
- **immutable records**: there is NO API that modifies, rewrites,
  or removes a journal record; the file discipline is append-only
  (``ab``), so the journal can only grow -- never silently
  overwrite.
- **deterministic replay**: loading and folding the same journal
  bytes always reproduces the same state.
- **duplicate detection**: an exact event replay (same event id)
  is an idempotent no-op at ingest; a duplicate that somehow
  reached a stored journal is rejected at load.
- **corruption/tamper detection**: load verifies every record id,
  the chain links, the contiguous 1..N sequence, and the
  (kind, reference, instant) collision index -- any tampered byte,
  reordered line, truncated tail, sequence gap, or contradictory
  pair fails closed with ``JOURNAL_CORRUPT``.
- **no secrets**: records carry kinds, ids, references, payloads of
  the accepted technology-neutral snapshot models, instants, and
  digests -- never key material, credentials, or protected
  payloads.

Records come in exactly two discriminated families (the W042
contract's "distinguish observations from protocol decisions"):

- ``platform-event`` -- an authoritative platform OBSERVATION;
- ``session-loss`` -- an honest recovery OUTCOME (a decision
  record), never an observation, never authority over sessions.

The persistence seam (:class:`PlatformStore`) is injectable:
:class:`MemoryPlatformStore` keeps verification deterministic and
in-process; :class:`FilePlatformStore` is the real durable store
(the only filesystem-write site in the platform family,
battery-audited).  The journal is persisted BEFORE the in-memory
record is acknowledged (persist-then-ack): a store failure leaves
no phantom in-memory state.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from protocol.canonicalization import (
    CanonicalizationError,
    canonical_json_bytes,
)

from .errors import PlatformError, PlatformReasonCode
from .model import PlatformEvent

#: The honest session-loss cause recorded at recovery (the WORK-035
#: ``SESSION_LOST_AT_RESTART`` semantics, restated as journal DATA).
SESSION_LOSS_CAUSE = "process-restart"


class JournalRecordKind:
    """The frozen journal record-kind vocabulary.

    Observations (``platform-event``) and honest recovery outcomes
    (``session-loss``) are discriminated at the record level: an
    outcome is never mistaken for a platform observation, and an
    observation is never mistaken for a protocol decision.
    """

    PLATFORM_EVENT = "platform-event"
    SESSION_LOSS = "session-loss"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.PLATFORM_EVENT, cls.SESSION_LOSS)


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise PlatformError(
            PlatformReasonCode.INVALID_INPUT,
            "%s must be a non-empty string" % label,
        )
    return value


def derive_record_id(
    sequence: int,
    record_kind: str,
    record_content: Dict[str, Any],
    prev_record_id: str,
) -> str:
    """The content-derived journal record fingerprint.

    Binds the record to its position (sequence), its family and
    content, and the ENTIRE preceding journal (prev link) -- the
    hash chain.
    """
    content = {
        "sequence": sequence,
        "record_kind": record_kind,
        "record": record_content,
        "prev_record_id": prev_record_id,
    }
    return "sha256:" + hashlib.sha256(canonical_json_bytes(content)).hexdigest()


def _session_loss_content(
    session_id: str,
    network_path_id: str,
    interface_name: str,
    cause: str,
    checkpoint_id: str,
) -> Dict[str, Any]:
    return {
        "session_id": session_id,
        "network_path_id": network_path_id,
        "interface_name": interface_name,
        "cause": cause,
        "checkpoint_id": checkpoint_id,
    }


@dataclass(frozen=True)
class JournalRecord:
    """One immutable journal record.

    Content binding: ``record_id`` MUST equal the fingerprint
    recomputed from (sequence, record_kind, content, prev link) --
    enforced at construction (empty id means "derive it"; a
    non-empty id must match).  Either ``event`` is a genuine
    PlatformEvent (platform-event family) or the session-loss
    fields are present (session-loss family); mixing families is
    rejected.
    """

    sequence: int
    record_kind: str
    record_id: str
    prev_record_id: str
    event: Optional[PlatformEvent] = None
    session_loss: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if isinstance(self.sequence, bool) or not isinstance(
            self.sequence, int
        ):
            raise PlatformError(
                PlatformReasonCode.INVALID_INPUT,
                "journal record sequence must be an integer",
            )
        if self.sequence < 1:
            raise PlatformError(
                PlatformReasonCode.INVALID_INPUT,
                "journal record sequence must be >= 1",
            )
        if self.record_kind not in JournalRecordKind.values():
            raise PlatformError(
                PlatformReasonCode.JOURNAL_CORRUPT,
                "journal record kind %r must be one of %s"
                % (self.record_kind, list(JournalRecordKind.values())),
            )
        if not isinstance(self.record_id, str):
            raise PlatformError(
                PlatformReasonCode.INVALID_INPUT,
                "record_id must be a string",
            )
        if self.record_kind == JournalRecordKind.PLATFORM_EVENT:
            if not isinstance(self.event, PlatformEvent):
                raise PlatformError(
                    PlatformReasonCode.JOURNAL_CORRUPT,
                    "platform-event record requires a genuine "
                    "PlatformEvent (observations only)",
                )
            if self.session_loss is not None:
                raise PlatformError(
                    PlatformReasonCode.JOURNAL_CORRUPT,
                    "platform-event record must not carry session-loss "
                    "content (observations and outcomes are distinct "
                    "families)",
                )
            content = {"event": self.event.to_dict()}
        else:
            loss = self.session_loss
            if not isinstance(loss, dict):
                raise PlatformError(
                    PlatformReasonCode.JOURNAL_CORRUPT,
                    "session-loss record requires loss content",
                )
            if self.event is not None:
                raise PlatformError(
                    PlatformReasonCode.JOURNAL_CORRUPT,
                    "session-loss record must not carry a platform event "
                    "(observations and outcomes are distinct families)",
                )
            for field_name in (
                "session_id",
                "network_path_id",
                "interface_name",
                "cause",
                "checkpoint_id",
            ):
                if not isinstance(loss.get(field_name), str) or not loss.get(
                    field_name
                ):
                    raise PlatformError(
                        PlatformReasonCode.JOURNAL_CORRUPT,
                        "session-loss content requires a non-empty %r"
                        % field_name,
                    )
            content = {"session_loss": dict(loss)}
        expected = derive_record_id(
            self.sequence, self.record_kind, content, self.prev_record_id
        )
        if self.record_id == "":
            object.__setattr__(self, "record_id", expected)
        elif self.record_id != expected:
            raise PlatformError(
                PlatformReasonCode.JOURNAL_CORRUPT,
                "record_id %r does not match the derived fingerprint %r "
                "(content + chain binding -- tampered or misbound record "
                "rejected)" % (self.record_id[:80], expected[:80]),
            )

    # -- typed accessors ---------------------------------------------------

    def session_loss_session_id(self) -> str:
        """The session-id reference of a session-loss record ('' for
        observation records)."""
        if self.record_kind != JournalRecordKind.SESSION_LOSS:
            return ""
        return str((self.session_loss or {}).get("session_id", ""))

    def to_dict(self) -> Dict[str, Any]:
        record: Dict[str, Any] = {
            "sequence": self.sequence,
            "record_kind": self.record_kind,
            "record_id": self.record_id,
            "prev_record_id": self.prev_record_id,
        }
        if self.record_kind == JournalRecordKind.PLATFORM_EVENT:
            record["event"] = (
                self.event.to_dict() if self.event is not None else None
            )
        else:
            record["session_loss"] = dict(self.session_loss or {})
        return record

    @classmethod
    def from_dict(cls, data: object) -> "JournalRecord":
        if not isinstance(data, dict):
            raise PlatformError(
                PlatformReasonCode.JOURNAL_CORRUPT,
                "journal record must be a mapping",
            )
        sequence = data.get("sequence", 0)
        if isinstance(sequence, bool) or not isinstance(sequence, int):
            raise PlatformError(
                PlatformReasonCode.JOURNAL_CORRUPT,
                "journal record sequence must be an integer",
            )
        event_data = data.get("event")
        event: Optional[PlatformEvent] = None
        if event_data is not None:
            event = PlatformEvent.from_dict(event_data)
        loss_data = data.get("session_loss")
        loss: Optional[Dict[str, Any]] = None
        if isinstance(loss_data, dict):
            loss = dict(loss_data)
        return cls(
            sequence=sequence,
            record_kind=str(data.get("record_kind", "")),
            record_id=str(data.get("record_id", "")),
            prev_record_id=str(data.get("prev_record_id", "")),
            event=event,
            session_loss=loss,
        )


def record_list_digest(records: List[JournalRecord]) -> str:
    """Deterministic digest over the ordered record list.

    ``record_list_digest(records[:p])`` is the journal PREFIX digest
    at position ``p`` (the checkpoint binding value).
    """
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes([record.to_dict() for record in records])
    ).hexdigest()


# ---------------------------------------------------------------------------
# The durable persistence seam (injectable)
# ---------------------------------------------------------------------------


class PlatformStore:
    """The durable persistence seam.

    Implementations append one canonical journal line per record and
    store one checkpoint payload.  The seam is the ONLY durability
    concern in the platform family: everything above it is pure
    deterministic logic, everything below it is bytes on a medium.
    """

    def append_journal_line(self, line: bytes) -> None:
        raise NotImplementedError

    def journal_bytes(self) -> bytes:
        raise NotImplementedError

    def write_checkpoint(self, payload: bytes) -> None:
        raise NotImplementedError

    def read_checkpoint(self) -> bytes:
        raise NotImplementedError


class MemoryPlatformStore(PlatformStore):
    """The deterministic in-memory store (verification seam)."""

    def __init__(self) -> None:
        self._journal = bytearray()
        self._checkpoint = b""

    def append_journal_line(self, line: bytes) -> None:
        if not isinstance(line, bytes):
            raise PlatformError(
                PlatformReasonCode.INVALID_INPUT,
                "journal line must be bytes",
            )
        self._journal.extend(line)

    def journal_bytes(self) -> bytes:
        return bytes(self._journal)

    def write_checkpoint(self, payload: bytes) -> None:
        if not isinstance(payload, bytes):
            raise PlatformError(
                PlatformReasonCode.INVALID_INPUT,
                "checkpoint payload must be bytes",
            )
        self._checkpoint = payload

    def read_checkpoint(self) -> bytes:
        return self._checkpoint


class FilePlatformStore(PlatformStore):
    """The real durable file-backed store.

    Layout (fixed names under one directory):

    - ``platform-journal.jsonl`` -- append-only journal lines;
    - ``platform-checkpoint.json`` -- the compact checkpoint.

    Journal discipline: the journal file is only ever opened in
    append-binary mode, so the file can only grow (no silent
    overwrite is possible).  A checkpoint is periodically REPLACED
    (that is the compact-snapshot model of ACR-006 section 3); its
    integrity is enforced by its own content digest and its journal
    binding, both verified at recovery.  All OS errors surface as
    the typed ``STORE_FAILED`` error (fail closed; an OS exception
    never crosses the seam untyped).
    """

    JOURNAL_NAME = "platform-journal.jsonl"
    CHECKPOINT_NAME = "platform-checkpoint.json"

    def __init__(self, directory: Path) -> None:
        if not isinstance(directory, Path):
            raise PlatformError(
                PlatformReasonCode.INVALID_INPUT,
                "directory must be a pathlib.Path",
            )
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise PlatformError(
                PlatformReasonCode.STORE_FAILED,
                "store directory unavailable (%s)" % type(error).__name__,
            ) from error
        self._directory = directory
        self._journal_path = directory / self.JOURNAL_NAME
        self._checkpoint_path = directory / self.CHECKPOINT_NAME

    @property
    def journal_path(self) -> Path:
        return self._journal_path

    @property
    def checkpoint_path(self) -> Path:
        return self._checkpoint_path

    def append_journal_line(self, line: bytes) -> None:
        if not isinstance(line, bytes):
            raise PlatformError(
                PlatformReasonCode.INVALID_INPUT,
                "journal line must be bytes",
            )
        try:
            with open(self._journal_path, "ab") as handle:
                handle.write(line)
        except OSError as error:
            raise PlatformError(
                PlatformReasonCode.STORE_FAILED,
                "journal append failed (%s)" % type(error).__name__,
            ) from error

    def journal_bytes(self) -> bytes:
        try:
            return self._journal_path.read_bytes()
        except FileNotFoundError:
            return b""
        except OSError as error:
            raise PlatformError(
                PlatformReasonCode.STORE_FAILED,
                "journal read failed (%s)" % type(error).__name__,
            ) from error

    def write_checkpoint(self, payload: bytes) -> None:
        if not isinstance(payload, bytes):
            raise PlatformError(
                PlatformReasonCode.INVALID_INPUT,
                "checkpoint payload must be bytes",
            )
        try:
            self._checkpoint_path.write_bytes(payload)
        except OSError as error:
            raise PlatformError(
                PlatformReasonCode.STORE_FAILED,
                "checkpoint write failed (%s)" % type(error).__name__,
            ) from error

    def read_checkpoint(self) -> bytes:
        try:
            return self._checkpoint_path.read_bytes()
        except FileNotFoundError:
            return b""
        except OSError as error:
            raise PlatformError(
                PlatformReasonCode.STORE_FAILED,
                "checkpoint read failed (%s)" % type(error).__name__,
            ) from error


# ---------------------------------------------------------------------------
# The append-only journal
# ---------------------------------------------------------------------------


class AppendOnlyJournal:
    """The append-only, hash-chained event journal.

    Owns the in-memory record list plus the duplicate and collision
    indexes (the ingest gate), backed by the durable store seam.
    Every append is PERSISTED FIRST (one canonical line through the
    store) and only then acknowledged in memory.

    There is deliberately NO mutation API: records are immutable,
    the sequence is strictly contiguous from 1, and the only way a
    record can exist is by appending.
    """

    def __init__(self, *, store: PlatformStore) -> None:
        if not isinstance(store, PlatformStore):
            raise PlatformError(
                PlatformReasonCode.INVALID_INPUT,
                "store must be a PlatformStore (the injectable seam)",
            )
        self._store = store
        self._records: List[JournalRecord] = []
        self._event_index: Dict[str, int] = {}
        self._collision_index: Dict[Tuple[str, str, str], str] = {}

    # -- loading -----------------------------------------------------------

    @classmethod
    def load(cls, store: PlatformStore) -> "AppendOnlyJournal":
        """Load and verify the durable journal (fail closed).

        Verification covers every tamper family: per-record content
        binding (record ids), the hash chain (prev links), the
        contiguous 1..N sequence (impossible transitions / gaps /
        reordering), duplicate event ids, and (kind, reference,
        instant) collisions (contradictory pairs smuggled into a
        hand-crafted store).
        """
        journal = cls(store=store)
        raw = store.journal_bytes()
        if raw == b"":
            return journal
        try:
            lines = [
                line
                for line in raw.split(b"\n")
                if line.strip() != b""
            ]
        except Exception as error:  # pragma: no cover - bytes split cannot raise
            raise PlatformError(
                PlatformReasonCode.JOURNAL_CORRUPT,
                "journal bytes unreadable (%s)" % type(error).__name__,
            ) from error
        for index, line in enumerate(lines, start=1):
            try:
                parsed = json.loads(line.decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as error:
                raise PlatformError(
                    PlatformReasonCode.JOURNAL_CORRUPT,
                    "journal line %d is not valid JSON (truncated or "
                    "corrupt tail -- fail closed, never silently "
                    "repaired): %s" % (index, type(error).__name__),
                ) from error
            if not isinstance(parsed, dict):
                raise PlatformError(
                    PlatformReasonCode.JOURNAL_CORRUPT,
                    "journal line %d is not a record mapping" % index,
                )
            try:
                record = JournalRecord.from_dict(parsed)
            except PlatformError as error:
                raise PlatformError(
                    PlatformReasonCode.JOURNAL_CORRUPT,
                    "journal line %d failed record verification: %s"
                    % (index, error.detail),
                ) from error
            journal._admit_loaded(record)
        journal._verify_chain()
        return journal

    def _admit_loaded(self, record: JournalRecord) -> None:
        """Admit a verified record into the indexes (load path)."""
        if record.record_kind == JournalRecordKind.PLATFORM_EVENT:
            event = record.event
            if event is None:  # pragma: no cover - constructor enforces
                raise PlatformError(
                    PlatformReasonCode.JOURNAL_CORRUPT,
                    "platform-event record without an event",
                )
            if event.event_id in self._event_index:
                raise PlatformError(
                    PlatformReasonCode.JOURNAL_CORRUPT,
                    "duplicate event id %r in the stored journal "
                    "(the append gate rejects duplicates; a tampered "
                    "store is suspected)" % event.event_id[:23],
                )
            key = (event.kind, event.platform_ref, event.observed_at)
            existing = self._collision_index.get(key)
            if existing is not None and existing != event.event_id:
                raise PlatformError(
                    PlatformReasonCode.JOURNAL_CORRUPT,
                    "contradictory events in the stored journal: "
                    "reference %r at instant %s reported by two "
                    "different events (%r vs %r -- fail closed)"
                    % (
                        event.platform_ref,
                        event.observed_at,
                        existing[:23],
                        event.event_id[:23],
                    ),
                )
            self._collision_index[key] = event.event_id
            self._event_index[event.event_id] = record.sequence
        self._records.append(record)

    def _verify_chain(self) -> None:
        """Chain + sequence verification (tamper, reorder, gap)."""
        previous: Optional[JournalRecord] = None
        for index, record in enumerate(self._records, start=1):
            if record.sequence != index:
                raise PlatformError(
                    PlatformReasonCode.JOURNAL_CORRUPT,
                    "journal sequence gap or reorder at position %d "
                    "(record claims sequence %d -- impossible journal "
                    "transition, fail closed)"
                    % (index, record.sequence),
                )
            if previous is None:
                if record.prev_record_id != "":
                    raise PlatformError(
                        PlatformReasonCode.JOURNAL_CORRUPT,
                        "first journal record must have an empty prev "
                        "link (found %r)" % record.prev_record_id[:23],
                    )
            else:
                if record.prev_record_id != previous.record_id:
                    raise PlatformError(
                        PlatformReasonCode.JOURNAL_CORRUPT,
                        "journal chain break at sequence %d: prev link "
                        "%r does not match the previous record id %r "
                        "(tamper, reorder, or truncation -- fail closed)"
                        % (
                            record.sequence,
                            record.prev_record_id[:23],
                            previous.record_id[:23],
                        ),
                    )
            previous = record

    # -- introspection -----------------------------------------------------

    def records(self) -> Tuple[JournalRecord, ...]:
        """The immutable record view (journal order)."""
        return tuple(self._records)

    def __len__(self) -> int:
        return len(self._records)

    def tail_sequence(self) -> int:
        """The sequence of the last record (0 for an empty
        journal)."""
        return self._records[-1].sequence if self._records else 0

    def journal_digest(self) -> str:
        """Deterministic digest over the full journal."""
        return record_list_digest(self._records)

    def prefix_digest(self, position: int) -> str:
        """Deterministic digest over records 1..position (the
        checkpoint binding value)."""
        if isinstance(position, bool) or not isinstance(position, int):
            raise PlatformError(
                PlatformReasonCode.INVALID_INPUT,
                "position must be an integer",
            )
        if position < 0 or position > len(self._records):
            raise PlatformError(
                PlatformReasonCode.CHECKPOINT_MISMATCH,
                "prefix position %d is beyond the journal tail %d"
                % (position, len(self._records)),
            )
        return record_list_digest(self._records[:position])

    def event_sequence(self, event_id: str) -> int:
        """The journal sequence of an event (0 if absent)."""
        return self._event_index.get(event_id, 0)

    def has_event(self, event_id: str) -> bool:
        return event_id in self._event_index

    def existing_event_at(
        self, kind: str, platform_ref: str, observed_at: str
    ) -> Optional[str]:
        """The event id already journaled at (kind, ref, instant), if
        any (the collision query)."""
        return self._collision_index.get((kind, platform_ref, observed_at))

    def lost_session_refs(self) -> Tuple[str, ...]:
        """Session-id references recorded by session-loss records
        (sorted, deterministic)."""
        refs = {
            record.session_loss_session_id()
            for record in self._records
            if record.record_kind == JournalRecordKind.SESSION_LOSS
        }
        refs.discard("")
        return tuple(sorted(refs))

    def has_session_loss(
        self, session_id: str, checkpoint_id: str
    ) -> bool:
        """Is the loss of ``session_id`` from ``checkpoint_id``
        already recorded (idempotent recovery)?"""
        for record in self._records:
            if record.record_kind != JournalRecordKind.SESSION_LOSS:
                continue
            loss = record.session_loss or {}
            if (
                loss.get("session_id") == session_id
                and loss.get("checkpoint_id") == checkpoint_id
            ):
                return True
        return False

    # -- the append gate ---------------------------------------------------

    def check_admissible(self, event: PlatformEvent) -> Optional[str]:
        """The ingest gate for one event.

        Returns ``None`` when the event is admissible; ``"duplicate"``
        when the exact event is already journaled (idempotent
        no-op); raises ``EVENT_CONTRADICTORY`` when a DIFFERENT
        event already occupies the same (kind, reference, instant)
        slot (fail closed, nothing journaled).
        """
        if not isinstance(event, PlatformEvent):
            raise PlatformError(
                PlatformReasonCode.INVALID_INPUT,
                "event must be a PlatformEvent",
            )
        if event.event_id in self._event_index:
            return "duplicate"
        existing = self._collision_index.get(
            (event.kind, event.platform_ref, event.observed_at)
        )
        if existing is not None and existing != event.event_id:
            raise PlatformError(
                PlatformReasonCode.EVENT_CONTRADICTORY,
                "contradictory platform events: reference %r already "
                "reported different content at instant %s (event %r vs "
                "new %r -- fail closed)"
                % (
                    event.platform_ref,
                    event.observed_at,
                    existing[:23],
                    event.event_id[:23],
                ),
            )
        return None

    def append_event(self, event: PlatformEvent) -> JournalRecord:
        """Append one platform-event record (persist-then-ack).

        Duplicates are rejected here (the idempotent no-op is
        decided by the caller through ``check_admissible``); nothing
        is journaled on failure.
        """
        if not isinstance(event, PlatformEvent):
            raise PlatformError(
                PlatformReasonCode.INVALID_INPUT,
                "event must be a PlatformEvent",
            )
        if event.event_id in self._event_index:
            raise PlatformError(
                PlatformReasonCode.JOURNAL_APPEND_REJECTED,
                "duplicate event %r (an exact replay is an idempotent "
                "no-op, never a second record)" % event.event_id[:23],
            )
        record = self._append(
            JournalRecord(
                sequence=len(self._records) + 1,
                record_kind=JournalRecordKind.PLATFORM_EVENT,
                record_id="",
                prev_record_id=(
                    self._records[-1].record_id if self._records else ""
                ),
                event=event,
            )
        )
        self._event_index[event.event_id] = record.sequence
        self._collision_index[
            (event.kind, event.platform_ref, event.observed_at)
        ] = event.event_id
        return record

    def append_session_loss(
        self,
        *,
        session_id: str,
        network_path_id: str,
        interface_name: str,
        cause: str,
        checkpoint_id: str,
        instant: str,
    ) -> JournalRecord:
        """Append one honest session-loss record (persist-then-ack).

        The ``instant`` is the recovery instant (injected clock);
        the RECORD CONTENT deliberately excludes it so the idempotent
        key is (session_id, checkpoint_id): a crash during recovery
        followed by re-recovery reproduces the identical record
        content and is detected as already-recorded by
        ``has_session_loss`` instead of double-journaling.
        """
        for label, value in (
            ("session_id", session_id),
            ("network_path_id", network_path_id),
            ("interface_name", interface_name),
            ("cause", cause),
            ("checkpoint_id", checkpoint_id),
            ("instant", instant),
        ):
            _require_text(value, label)
        record = self._append(
            JournalRecord(
                sequence=len(self._records) + 1,
                record_kind=JournalRecordKind.SESSION_LOSS,
                record_id="",
                prev_record_id=(
                    self._records[-1].record_id if self._records else ""
                ),
                session_loss=_session_loss_content(
                    session_id,
                    network_path_id,
                    interface_name,
                    cause,
                    checkpoint_id,
                ),
            )
        )
        return record

    def _append(self, record: JournalRecord) -> JournalRecord:
        """Persist-then-ack one record through the store seam."""
        try:
            line = canonical_json_bytes(record.to_dict()) + b"\n"
        except CanonicalizationError as error:
            raise PlatformError(
                PlatformReasonCode.JOURNAL_APPEND_REJECTED,
                "record is not canonically representable (%s)" % error,
            ) from error
        self._store.append_journal_line(line)  # persist FIRST (fail closed)
        self._records.append(record)  # ack only after durability
        return record


def journal_bytes_for(records: List[JournalRecord]) -> bytes:
    """The canonical durable journal bytes of a record list (the
    exact on-medium form; verification helper)."""
    parts: List[bytes] = []
    for record in records:
        parts.append(canonical_json_bytes(record.to_dict()) + b"\n")
    return b"".join(parts)


__all__ = [
    "AppendOnlyJournal",
    "FilePlatformStore",
    "JournalRecord",
    "JournalRecordKind",
    "MemoryPlatformStore",
    "PlatformStore",
    "SESSION_LOSS_CAUSE",
    "derive_record_id",
    "journal_bytes_for",
    "record_list_digest",
]
