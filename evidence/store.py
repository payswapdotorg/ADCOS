"""ADCOS typed evidence-record store (M005 — Evidence and Assurance).

The append-only, immutable evidence-record store (LOCK-106):

- **Immutable, append-only records.** Evidence records enter through
  :meth:`EvidenceStore.ingest` and never change; there is no update
  or delete path.  Records are frozen dataclasses whose content
  already carries a content-derived identity, so an "update" is
  structurally a NEW record (a different id).
- **Idempotent ingest.** Ingesting the exact same record again is a
  journal no-op (the duplicate is reported, never re-appended).
  Ingesting a DIFFERENT record under a retained id is tampering and
  fails closed (RECORD_TAMPER).
- **Construction-is-recovery.** With a ``journal_path`` the store
  persists every accepted record as one JSONL line and re-folds on
  construction; the fold is idempotent (replaying the journal
  reproduces byte-identical state).
- **Secret scanning (LOCK-119).** Every persisted line is scanned for
  secret-shaped material before it enters the fold; a secret can never
  become persistent evidence DATA through the journal surface.
- **Sorted iteration.** Records iterate in record-id order
  (PYTHONHASHSEED-safe, byte-identical across processes).

The store holds TYPED records only — there is no untyped ingest path
(LOCK-106).  It never interprets evidence, never evaluates assurance
(the ``assurance/`` domain owns evaluation), and never touches
contract state (LOCK-101: ``contracts/`` is the sole contract
authority; the store references contracts by id only).
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .errors import EvidenceError, EvidenceReasonCode
from .model import EVIDENCE_TYPES, record_from_dict

#: Line-level secret scan (LOCK-119): the persisted-journal discipline
#: mirrors the contracts store.
_SECRET_VALUE_PATTERN_LINE = re.compile(
    r"(ghp_|gho_|sk_|ak_|ck_|onbsec_)[A-Za-z0-9_-]+"
)


class IngestResult:
    """The outcome of one ingest: ``accepted`` True for a new record,
    False for an idempotent duplicate (same id, same canonical
    content).  Tampered duplicates raise instead of returning."""

    __slots__ = ("accepted", "record_id", "detail")

    def __init__(self, accepted: bool, record_id: str, detail: str) -> None:
        self.accepted = accepted
        self.record_id = record_id
        self.detail = detail


class EvidenceStore:
    """The append-only typed evidence-record store."""

    def __init__(self, journal_path: Optional[Path] = None) -> None:
        self._lock = threading.RLock()
        self._journal_path = Path(journal_path) if journal_path is not None else None
        self._records: Dict[str, Any] = {}
        self._order: List[str] = []
        if self._journal_path is not None and self._journal_path.is_file():
            self._load_journal()

    # -- construction-is-recovery -----------------------------------------

    def _load_journal(self) -> None:
        assert self._journal_path is not None
        try:
            raw_lines = self._journal_path.read_text(encoding="utf-8").splitlines()
        except OSError as error:
            raise EvidenceError(
                EvidenceReasonCode.RECORD_TAMPER,
                "cannot read the evidence journal: %s" % str(error)[:120],
            ) from None
        for line_number, line in enumerate(raw_lines, start=1):
            if not line.strip():
                continue
            if _SECRET_VALUE_PATTERN_LINE.search(line):
                raise EvidenceError(
                    EvidenceReasonCode.SECRET_REJECTED,
                    "journal line %d carries secret-shaped material (LOCK-119)"
                    % line_number,
                )
            try:
                data = json.loads(line)
            except ValueError as error:
                raise EvidenceError(
                    EvidenceReasonCode.RECORD_TAMPER,
                    "journal line %d is not valid JSON: %s"
                    % (line_number, str(error)[:120]),
                ) from None
            try:
                record = record_from_dict(data)
            except EvidenceError as error:
                raise EvidenceError(
                    EvidenceReasonCode.RECORD_TAMPER,
                    "journal line %d is not a typed evidence record: %s"
                    % (line_number, error.detail[:120]),
                ) from None
            self._ingest_unlocked(record)

    # -- append-only ingest -------------------------------------------------

    def ingest(self, record: Any) -> IngestResult:
        """Ingest one typed evidence record (idempotent; fail-closed on
        tampered duplicates and untyped input)."""
        if not hasattr(record, "record_type") or record.record_type not in EVIDENCE_TYPES:
            raise EvidenceError(
                EvidenceReasonCode.INVALID_INPUT,
                "ingest requires a typed evidence record (LOCK-106: no "
                "untyped evidence); got %s" % type(record).__name__,
            )
        with self._lock:
            return self._ingest_unlocked(record)

    def _ingest_unlocked(self, record: Any) -> IngestResult:
        record_id = record.record_id
        existing = self._records.get(record_id)
        if existing is not None:
            if existing.canonical_bytes() == record.canonical_bytes():
                return IngestResult(
                    False, record_id, "idempotent duplicate (byte-identical content)"
                )
            raise EvidenceError(
                EvidenceReasonCode.RECORD_TAMPER,
                "record %s already exists with different canonical content — "
                "the retained id over mutated DATA is rejected" % record_id[:48],
            )
        self._records[record_id] = record
        self._order.append(record_id)
        self._persist(record)
        return IngestResult(True, record_id, "record appended")

    def ingest_many(self, records) -> List[IngestResult]:
        """Ingest records in the given sequence order (each ingest is
        individually idempotent and fail-closed)."""
        return [self.ingest(record) for record in records]

    def _persist(self, record: Any) -> None:
        if self._journal_path is None:
            return
        line = json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"))
        if _SECRET_VALUE_PATTERN_LINE.search(line):
            # defense in depth: construction already rejected secrets;
            # the journal line scan keeps the persisted surface honest
            raise EvidenceError(
                EvidenceReasonCode.SECRET_REJECTED,
                "record %s carries secret-shaped material (LOCK-119)" % record.record_id[:48],
            )
        try:
            with self._journal_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError as error:
            raise EvidenceError(
                EvidenceReasonCode.INVALID_INPUT,
                "cannot persist the evidence journal: %s" % str(error)[:120],
            ) from None

    # -- typed read paths -----------------------------------------------------

    def get(self, record_id: object) -> Any:
        """One typed record by id (fail closed on unknown ids)."""
        if not isinstance(record_id, str):
            raise EvidenceError(
                EvidenceReasonCode.INVALID_INPUT,
                "record_id must be a str (got %s)" % type(record_id).__name__,
            )
        with self._lock:
            record = self._records.get(record_id)
        if record is None:
            raise EvidenceError(
                EvidenceReasonCode.RECORD_UNKNOWN,
                "no evidence record with id %s" % record_id[:48],
            )
        return record

    def has(self, record_id: object) -> bool:
        """Existence probe (no content disclosed beyond membership)."""
        return isinstance(record_id, str) and record_id in self._records

    def records(self) -> Tuple[Any, ...]:
        """All records in deterministic record-id order (sorted
        iteration, PYTHONHASHSEED-safe)."""
        with self._lock:
            return tuple(self._records[record_id] for record_id in sorted(self._records))

    def for_contract(self, contract_ref: object) -> Tuple[Any, ...]:
        """All records referencing one contract, in record-id order."""
        if not isinstance(contract_ref, str) or not contract_ref:
            raise EvidenceError(
                EvidenceReasonCode.INVALID_INPUT,
                "contract_ref must be a non-empty str",
            )
        with self._lock:
            return tuple(
                record
                for record_id in sorted(self._records)
                if (record := self._records[record_id]).contract_ref == contract_ref
            )

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)

    # -- journal snapshot -------------------------------------------------------

    def snapshot_lines(self) -> Tuple[str, ...]:
        """The journal as canonical JSONL lines (byte-identical across
        runs: records in record-id order, keys sorted)."""
        with self._lock:
            return tuple(
                json.dumps(self._records[record_id].to_dict(), sort_keys=True, separators=(",", ":"))
                for record_id in sorted(self._records)
            )

    def state_digest(self) -> str:
        """A deterministic digest over the complete store state (the
        sha256 hex over the concatenated canonical bytes in record-id
        order — the determinism probe for cross-process checks)."""
        import hashlib

        digest = hashlib.sha256()
        for record in self.records():
            digest.update(record.canonical_bytes())
        return digest.hexdigest()


__all__ = [
    "EvidenceStore",
    "IngestResult",
]
