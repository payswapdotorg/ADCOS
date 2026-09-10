"""ADCOS assurance evaluation journal (M005 — Evidence and Assurance).

The append-only, idempotent evaluation-history journal (LOCK-107:
active contracts are CONTINUOUSLY — here: repeatedly, deterministically,
on demand — evaluated against their obligations; the journal is the
durable closed-loop trail of those evaluations):

- **Append-only, idempotent.** Appending the exact same evaluation
  again is a no-op (byte-identical content); appending a DIFFERENT
  evaluation under a retained id is tampering and fails closed.
- **Construction-is-recovery.** With a ``journal_path`` every
  accepted evaluation persists as one JSONL line and re-folds on
  construction; the fold is idempotent.
- **Secret scanning (LOCK-119).** Every persisted line is scanned
  before it enters the fold.
- **Sorted iteration.** History iterates in (evaluated_at,
  evaluation_id) order — PYTHONHASHSEED-safe, byte-identical across
  processes.

The journal is assurance-domain DATA only: it never writes contract
state (the contract bridge is the sole, explicit recording path), and
it never evaluates anything (evaluations are produced by the pure
``evaluate_contract`` kernel).
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .errors import AssuranceError, AssuranceReasonCode
from .model import AssuranceEvaluation

_SECRET_VALUE_PATTERN_LINE = re.compile(
    r"(ghp_|gho_|sk_|ak_|ck_|onbsec_)[A-Za-z0-9_-]+"
)


class AppendResult:
    """The outcome of one journal append: ``accepted`` True for a new
    evaluation, False for an idempotent duplicate.  Tampered
    duplicates raise instead of returning."""

    __slots__ = ("accepted", "evaluation_id", "detail")

    def __init__(self, accepted: bool, evaluation_id: str, detail: str) -> None:
        self.accepted = accepted
        self.evaluation_id = evaluation_id
        self.detail = detail


class AssuranceJournal:
    """The append-only assurance evaluation-history journal."""

    def __init__(self, journal_path: Optional[Path] = None) -> None:
        self._lock = threading.RLock()
        self._journal_path = Path(journal_path) if journal_path is not None else None
        self._evaluations: Dict[str, AssuranceEvaluation] = {}
        if self._journal_path is not None and self._journal_path.is_file():
            self._load_journal()

    # -- construction-is-recovery -----------------------------------------

    def _load_journal(self) -> None:
        assert self._journal_path is not None
        try:
            raw_lines = self._journal_path.read_text(encoding="utf-8").splitlines()
        except OSError as error:
            raise AssuranceError(
                AssuranceReasonCode.JOURNAL_TAMPER,
                "cannot read the assurance journal: %s" % str(error)[:120],
            ) from None
        for line_number, line in enumerate(raw_lines, start=1):
            if not line.strip():
                continue
            if _SECRET_VALUE_PATTERN_LINE.search(line):
                raise AssuranceError(
                    AssuranceReasonCode.SECRET_REJECTED,
                    "journal line %d carries secret-shaped material (LOCK-119)"
                    % line_number,
                )
            try:
                data = json.loads(line)
            except ValueError as error:
                raise AssuranceError(
                    AssuranceReasonCode.JOURNAL_TAMPER,
                    "journal line %d is not valid JSON: %s"
                    % (line_number, str(error)[:120]),
                ) from None
            try:
                evaluation = AssuranceEvaluation.from_dict(data)
            except AssuranceError as error:
                raise AssuranceError(
                    AssuranceReasonCode.JOURNAL_TAMPER,
                    "journal line %d is not a typed evaluation record: %s"
                    % (line_number, error.detail[:120]),
                ) from None
            self._append_unlocked(evaluation)

    # -- append-only history -------------------------------------------------

    def append(self, evaluation: Any) -> AppendResult:
        """Append one evaluation (idempotent; fail-closed on tampered
        duplicates and untyped input)."""
        if not isinstance(evaluation, AssuranceEvaluation):
            raise AssuranceError(
                AssuranceReasonCode.INVALID_INPUT,
                "append requires an AssuranceEvaluation record (got %s)"
                % type(evaluation).__name__,
            )
        with self._lock:
            return self._append_unlocked(evaluation)

    def _append_unlocked(self, evaluation: AssuranceEvaluation) -> AppendResult:
        evaluation_id = evaluation.evaluation_id
        existing = self._evaluations.get(evaluation_id)
        if existing is not None:
            if existing.canonical_bytes() == evaluation.canonical_bytes():
                return AppendResult(
                    False, evaluation_id, "idempotent duplicate (byte-identical content)"
                )
            raise AssuranceError(
                AssuranceReasonCode.JOURNAL_TAMPER,
                "evaluation %s already exists with different canonical "
                "content — the retained id over mutated DATA is rejected"
                % evaluation_id[:48],
            )
        self._evaluations[evaluation_id] = evaluation
        self._persist(evaluation)
        return AppendResult(True, evaluation_id, "evaluation appended")

    def _persist(self, evaluation: AssuranceEvaluation) -> None:
        if self._journal_path is None:
            return
        line = json.dumps(
            evaluation.to_dict(), sort_keys=True, separators=(",", ":")
        )
        if _SECRET_VALUE_PATTERN_LINE.search(line):
            raise AssuranceError(
                AssuranceReasonCode.SECRET_REJECTED,
                "evaluation %s carries secret-shaped material (LOCK-119)"
                % evaluation.evaluation_id[:48],
            )
        try:
            with self._journal_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError as error:
            raise AssuranceError(
                AssuranceReasonCode.INVALID_INPUT,
                "cannot persist the assurance journal: %s" % str(error)[:120],
            ) from None

    # -- typed read paths -----------------------------------------------------

    def history(self) -> Tuple[AssuranceEvaluation, ...]:
        """All evaluations in deterministic (evaluated_at,
        evaluation_id) order."""
        with self._lock:
            return tuple(
                self._evaluations[evaluation_id]
                for evaluation_id in sorted(
                    self._evaluations,
                    key=lambda eid: (
                        self._evaluations[eid].evaluated_at,
                        eid,
                    ),
                )
            )

    def for_contract(self, contract_ref: object) -> Tuple[AssuranceEvaluation, ...]:
        """The evaluation history of one contract, in (evaluated_at,
        evaluation_id) order."""
        if not isinstance(contract_ref, str) or not contract_ref:
            raise AssuranceError(
                AssuranceReasonCode.INVALID_INPUT,
                "contract_ref must be a non-empty str",
            )
        return tuple(
            evaluation
            for evaluation in self.history()
            if evaluation.contract_ref == contract_ref
        )

    def latest_for(self, contract_ref: object) -> AssuranceEvaluation:
        """The latest evaluation of one contract (fail closed when the
        contract has never been evaluated — the closed-loop query
        surface)."""
        evaluations = self.for_contract(contract_ref)
        if not evaluations:
            raise AssuranceError(
                AssuranceReasonCode.EVALUATION_UNKNOWN,
                "no evaluation recorded for contract %s" % str(contract_ref)[:48],
            )
        return evaluations[-1]

    def get(self, evaluation_id: object) -> AssuranceEvaluation:
        if not isinstance(evaluation_id, str):
            raise AssuranceError(
                AssuranceReasonCode.INVALID_INPUT,
                "evaluation_id must be a str (got %s)" % type(evaluation_id).__name__,
            )
        with self._lock:
            evaluation = self._evaluations.get(evaluation_id)
        if evaluation is None:
            raise AssuranceError(
                AssuranceReasonCode.EVALUATION_UNKNOWN,
                "no evaluation with id %s" % evaluation_id[:48],
            )
        return evaluation

    def __len__(self) -> int:
        with self._lock:
            return len(self._evaluations)

    # -- state digest -----------------------------------------------------------

    def state_digest(self) -> str:
        """A deterministic digest over the complete journal state (the
        determinism probe for cross-process checks)."""
        digest = hashlib.sha256()
        for evaluation in self.history():
            digest.update(evaluation.canonical_bytes())
        return digest.hexdigest()


__all__ = [
    "AssuranceJournal",
    "AppendResult",
]
