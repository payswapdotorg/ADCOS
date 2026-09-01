"""WORK-051 CommercialCore append-only journal and durable
persistence seam.

The journal-first durable core of the commercial history (the
ACR-006 journal discipline referenced by the W051 contract):

    immutable commercial records
        + append-only file discipline
        + content-derived record ids
        + a hash chain over (sequence, content, previous link)
        = tamper-evident, deterministically replayable commercial
          history

Discipline (battery-pinned, mirroring the accepted W042 journal):

- **atomic command records**: every executed command appends
  EXACTLY ONE journal record carrying the admitted command
  (input + content digest, the durable idempotency ledger) AND
  its resulting commercial event (the fact with full
  attribution).  One append = one atomic persist-then-ack; there
  is no intermediate state where a command is admitted without
  its fact.
- **content-derived ids**: every ``record_id`` is the fingerprint
  of (sequence, record content, previous record id) -- the hash
  chain; every ``event_id`` is the fingerprint of its commercial
  content; every ``command_digest`` is the fingerprint of the
  command content.  All are mechanically verified at construction
  and on deserialization, so a tampered record can never carry an
  attacker-chosen id.
- **canonical serialization**: one canonical-JSON line per record
  (the WORK-003 profile); identical logical histories produce
  byte-identical journals.
- **immutable records**: there is NO API that modifies, rewrites,
  or removes a journal record; the file discipline is append-only
  (``ab``), so the journal can only grow -- settled or historical
  commercial facts can never be edited in place.
- **deterministic replay**: loading and folding the same journal
  bytes always reproduces the same commercial state (the fold
  lives in :mod:`commercial.lifecycle` and reuses the single
  apply function the manager itself uses).
- **duplicate detection**: the command ledger is journaled with
  each record, so command-idempotency survives restart; a
  duplicate command id in a stored journal fails closed at load.
- **corruption/tamper detection**: load verifies every record id,
  the chain links, the contiguous 1..N sequence, every command
  digest, and duplicate command ids -- any tampered byte,
  reordered line, truncated tail, sequence gap, or duplicate pair
  fails closed with ``JOURNAL_CORRUPT``.
- **persist-then-ack**: the journal is persisted BEFORE the
  in-memory record is acknowledged; a store failure leaves no
  phantom in-memory state (``STORE_FAILED``).

The persistence seam (:class:`CommercialStore`) is injectable:
:class:`MemoryCommercialStore` keeps verification deterministic
and in-process; :class:`FileCommercialStore` is the real durable
store (the only filesystem-write site in the commercial family,
battery-audited).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

from protocol.canonicalization import canonical_json_bytes

from .errors import CommercialError, CommercialReasonCode
from .model import CommercialCommand, CommercialEvent

#: The record-kind vocabulary: one discriminated family.
JOURNAL_RECORD_KIND = "commercial-record"

GENESIS_RECORD_ID = "sha256:" + "0" * 64


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise CommercialError(
            CommercialReasonCode.INVALID_INPUT,
            "%s must be a non-empty string" % label,
        )
    return value


def derive_record_id(
    sequence: int,
    record_content: Dict[str, Any],
    prev_record_id: str,
) -> str:
    """The content-derived journal record fingerprint (hash chain).

    Binds the record to its position (sequence), its content (the
    admitted command + its event), and the ENTIRE preceding
    journal (prev link).
    """
    content = {
        "sequence": sequence,
        "record_kind": JOURNAL_RECORD_KIND,
        "record": record_content,
        "prev_record_id": prev_record_id,
    }
    return "sha256:" + hashlib.sha256(canonical_json_bytes(content)).hexdigest()


def record_content(
    command: CommercialCommand, command_digest: str, event: CommercialEvent
) -> Dict[str, Any]:
    """The canonical journal record content (command + fact)."""
    return {
        "command": command.to_dict(),
        "command_digest": command_digest,
        "event": event.to_dict(),
    }


@dataclass(frozen=True)
class JournalRecord:
    """One append-only journal record: an admitted command and its
    resulting commercial event (one atomic commercial fact).

    ``record_id`` is the hash-chain fingerprint over (sequence,
    {command, command_digest, event}, prev) and is mechanically
    verified at construction and deserialization.
    """

    sequence: int
    record_id: str
    command: CommercialCommand
    command_digest: str
    event: CommercialEvent

    def __post_init__(self) -> None:
        if not isinstance(self.sequence, int) or isinstance(self.sequence, bool):
            raise CommercialError(
                CommercialReasonCode.JOURNAL_CORRUPT,
                "sequence must be an integer",
            )
        if self.sequence < 1:
            raise CommercialError(
                CommercialReasonCode.JOURNAL_CORRUPT,
                "sequence must be >= 1 (contiguous 1..N journal)",
            )
        _require_text(self.record_id, "record_id")
        if not isinstance(self.command, CommercialCommand):
            raise CommercialError(
                CommercialReasonCode.JOURNAL_CORRUPT,
                "record must carry a CommercialCommand",
            )
        _require_text(self.command_digest, "command_digest")
        if not isinstance(self.event, CommercialEvent):
            raise CommercialError(
                CommercialReasonCode.JOURNAL_CORRUPT,
                "record must carry a CommercialEvent",
            )
        if self.command.command_id != self.event.command_id:
            raise CommercialError(
                CommercialReasonCode.JOURNAL_CORRUPT,
                "record command id %r does not match the event command id %r"
                % (self.command.command_id, self.event.command_id),
            )
        if self.command.action != self.event.action:
            raise CommercialError(
                CommercialReasonCode.JOURNAL_CORRUPT,
                "record action %r does not match the event action %r"
                % (self.command.action, self.event.action),
            )

    def content(self) -> Dict[str, Any]:
        return record_content(self.command, self.command_digest, self.event)

    def verify_id(self, prev_record_id: str) -> None:
        """Mechanical content binding (the hash-chain gate)."""
        expected = derive_record_id(
            self.sequence, self.content(), prev_record_id
        )
        if self.record_id != expected:
            raise CommercialError(
                CommercialReasonCode.JOURNAL_CORRUPT,
                "record %d id %s does not match the content-derived id %s "
                "(tampered journal record)"
                % (self.sequence, self.record_id, expected),
            )

    def verify_command_digest(self) -> None:
        """The command digest must recompute from the command
        content (tamper detection on the idempotency ledger)."""
        expected = self.command.digest()
        if self.command_digest != expected:
            raise CommercialError(
                CommercialReasonCode.JOURNAL_CORRUPT,
                "record %d command digest %s does not match the recomputed "
                "digest %s (tampered command content)"
                % (self.sequence, self.command_digest, expected),
            )

    def to_line(self) -> bytes:
        """One canonical-JSON journal line (deterministic bytes)."""
        payload = {
            "sequence": self.sequence,
            "record_id": self.record_id,
            "command": self.command.to_dict(),
            "command_digest": self.command_digest,
            "event": self.event.to_dict(),
        }
        return canonical_json_bytes(payload) + b"\n"

    @classmethod
    def build(
        cls,
        sequence: int,
        prev_record_id: str,
        command: CommercialCommand,
        command_digest: str,
        event: CommercialEvent,
    ) -> "JournalRecord":
        record = cls(
            sequence=sequence,
            record_id=GENESIS_RECORD_ID,
            command=command,
            command_digest=command_digest,
            event=event,
        )
        record_id = derive_record_id(
            sequence, record_content(command, command_digest, event), prev_record_id
        )
        object.__setattr__(record, "record_id", record_id)
        return record

    @classmethod
    def from_dict(cls, data: object) -> "JournalRecord":
        if not isinstance(data, dict):
            raise CommercialError(
                CommercialReasonCode.JOURNAL_CORRUPT,
                "journal record must be a mapping",
            )
        required = ("sequence", "record_id", "command", "command_digest", "event")
        for key in required:
            if key not in data:
                raise CommercialError(
                    CommercialReasonCode.JOURNAL_CORRUPT,
                    "journal record is missing required member %r" % key,
                )
        try:
            command = CommercialCommand.from_dict(data["command"])
            event = CommercialEvent.from_dict(data["event"])
        except CommercialError as error:
            # a malformed command/event payload inside the STORED
            # journal is journal corruption, fail closed.
            raise CommercialError(
                CommercialReasonCode.JOURNAL_CORRUPT,
                "journal record payload invalid: %s" % error.detail,
            ) from error
        return cls(
            sequence=data["sequence"],
            record_id=data["record_id"],
            command=command,
            command_digest=data["command_digest"],
            event=event,
        )


def record_list_digest(records: Tuple[JournalRecord, ...]) -> str:
    """Deterministic digest over the full ordered journal."""
    content = {
        "kind": "commercial-journal",
        "records": [
            {
                "sequence": record.sequence,
                "record_id": record.record_id,
                "command_digest": record.command_digest,
                "event_id": record.event.event_id,
            }
            for record in records
        ],
        "count": len(records),
    }
    return "sha256:" + hashlib.sha256(canonical_json_bytes(content)).hexdigest()


class CommercialStore:
    """The injectable persistence seam (abstract)."""

    def append_journal_line(self, line: bytes) -> None:
        raise NotImplementedError

    def journal_bytes(self) -> bytes:
        raise NotImplementedError


class MemoryCommercialStore(CommercialStore):
    """The in-memory store (deterministic verification)."""

    def __init__(self) -> None:
        self._lines: List[bytes] = []

    def append_journal_line(self, line: bytes) -> None:
        self._lines.append(bytes(line))

    def journal_bytes(self) -> bytes:
        return b"".join(self._lines)


class FileCommercialStore(CommercialStore):
    """The real durable store: an append-only journal file.

    The only filesystem-write site in the commercial family; the
    file is opened append-binary so history can only grow.  A
    store failure raises ``STORE_FAILED`` (persist-then-ack
    leaves no phantom state).
    """

    def __init__(self, directory: Path) -> None:
        if not isinstance(directory, Path):
            raise CommercialError(
                CommercialReasonCode.INVALID_INPUT,
                "directory must be a Path",
            )
        self._directory = directory
        self._journal_path = directory / "commercial-journal.jsonl"

    @property
    def journal_path(self) -> Path:
        return self._journal_path

    def append_journal_line(self, line: bytes) -> None:
        try:
            self._directory.mkdir(parents=True, exist_ok=True)
            with self._journal_path.open("ab") as handle:
                handle.write(bytes(line))
                handle.flush()
        except OSError as error:
            raise CommercialError(
                CommercialReasonCode.STORE_FAILED,
                "journal append failed: %s" % error,
            ) from error

    def journal_bytes(self) -> bytes:
        try:
            if not self._journal_path.exists():
                return b""
            with self._journal_path.open("rb") as handle:
                return handle.read()
        except OSError as error:
            raise CommercialError(
                CommercialReasonCode.STORE_FAILED,
                "journal read failed: %s" % error,
            ) from error


def journal_bytes_for(records: Tuple[JournalRecord, ...]) -> bytes:
    """Deterministic journal bytes for an ordered record list."""
    return b"".join(record.to_line() for record in records)


class AppendOnlyCommercialJournal:
    """The append-only, hash-chained commercial journal.

    Responsibilities (all fail-closed):

    - append atomic command+event records with contiguous
      sequence and hash-chain verification (persist-then-ack);
    - load a journal from store bytes with full integrity
      verification (ids, chain, sequence, command digests,
      duplicate command ids);
    - expose the ordered records, the durable command ledger,
      and digests for replay.
    """

    def __init__(self, *, store: CommercialStore) -> None:
        if not isinstance(store, CommercialStore):
            raise CommercialError(
                CommercialReasonCode.INVALID_INPUT,
                "store must be a CommercialStore",
            )
        self._store = store
        self._records: List[JournalRecord] = []
        self._command_ledger: Dict[str, Dict[str, str]] = {}
        self._load_and_verify()

    @property
    def store(self) -> CommercialStore:
        return self._store

    def _load_and_verify(self) -> None:
        """Load + verify the persisted journal (if any)."""
        data = self._store.journal_bytes()
        if not data:
            return
        if not data.endswith(b"\n"):
            raise CommercialError(
                CommercialReasonCode.JOURNAL_CORRUPT,
                "journal tail is truncated (last line is not "
                "newline-terminated)",
            )
        prev_record_id = GENESIS_RECORD_ID
        expected_sequence = 1
        for line_no, raw_line in enumerate(data.split(b"\n")[:-1], start=1):
            try:
                payload = json.loads(raw_line.decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as error:
                raise CommercialError(
                    CommercialReasonCode.JOURNAL_CORRUPT,
                    "journal line %d is not valid JSON: %s" % (line_no, error),
                ) from error
            record = JournalRecord.from_dict(payload)
            if record.sequence != expected_sequence:
                raise CommercialError(
                    CommercialReasonCode.JOURNAL_CORRUPT,
                    "journal sequence gap at line %d: expected %d, found %d"
                    % (line_no, expected_sequence, record.sequence),
                )
            record.verify_command_digest()
            record.verify_id(prev_record_id)
            if record.command.command_id in self._command_ledger:
                raise CommercialError(
                    CommercialReasonCode.JOURNAL_CORRUPT,
                    "duplicate command id %r in the stored journal"
                    % record.command.command_id,
                )
            self._command_ledger[record.command.command_id] = {
                "command_digest": record.command_digest,
                "event_id": record.event.event_id,
            }
            prev_record_id = record.record_id
            expected_sequence += 1
            self._records.append(record)

    def append(self, record: JournalRecord) -> None:
        """Append one record (persist-then-ack, fail closed)."""
        expected_sequence = len(self._records) + 1
        if record.sequence != expected_sequence:
            raise CommercialError(
                CommercialReasonCode.JOURNAL_CORRUPT,
                "append sequence %d is not the next journal sequence %d"
                % (record.sequence, expected_sequence),
            )
        prev_record_id = (
            self._records[-1].record_id if self._records else GENESIS_RECORD_ID
        )
        record.verify_command_digest()
        record.verify_id(prev_record_id)
        if record.command.command_id in self._command_ledger:
            raise CommercialError(
                CommercialReasonCode.JOURNAL_CORRUPT,
                "duplicate command id %r rejected at append (duplicates "
                "are no-ops at admission, never double-journaled)"
                % record.command.command_id,
            )
        # persist BEFORE acknowledge (no phantom in-memory state)
        self._store.append_journal_line(record.to_line())
        self._command_ledger[record.command.command_id] = {
            "command_digest": record.command_digest,
            "event_id": record.event.event_id,
        }
        self._records.append(record)

    def known_command(self, command_id: str):
        """The recorded (digest, event_id) for an admitted command
        id, or None (the durable idempotency ledger)."""
        return self._command_ledger.get(command_id)

    def command_ledger(self) -> Dict[str, Dict[str, str]]:
        return dict(self._command_ledger)

    def records(self) -> Tuple[JournalRecord, ...]:
        return tuple(self._records)

    def events(self) -> Tuple[CommercialEvent, ...]:
        return tuple(record.event for record in self._records)

    def __len__(self) -> int:
        return len(self._records)

    def tail_sequence(self) -> int:
        return len(self._records)

    def journal_digest(self) -> str:
        return record_list_digest(tuple(self._records))
