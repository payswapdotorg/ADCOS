"""ADCOS closed-loop assurance error model (M005 — Evidence and
Assurance).

Leaf module: imported by every other ``assurance`` submodule, imports
nothing from the package (no import cycles).  :class:`AssuranceError`
is the fail-closed caller-input/state error raised for caller-side
validation failures; the reason-code vocabulary is frozen (adding a
code is a deliberate vocabulary change, never a silent extension).

The assurance layer evaluates ACTIVE canonical contracts against
their assurance obligations using typed evidence records (LOCK-107).
It is an EVALUATION domain, never a second contract authority:
``contracts/`` stays the sole authority for acquired connectivity
(LOCK-101/LOCK-117 — the assurance domain consumes the contract
surface by reference, never modifies it, never duplicates it); the
``evidence/`` domain owns the typed records the evaluation consumes.
"""

from __future__ import annotations

from typing import Tuple

#: Canonical assurance family prefix (the M005 family namespace).
ASSURANCE_PREFIX = "assurance"


class AssuranceReasonCode:
    """Frozen reason-code vocabulary (closed-loop assurance layer).

    Adding a code is a deliberate vocabulary change, never a silent
    extension.
    """

    INVALID_INPUT = "invalid-input"
    VOCABULARY = "vocabulary"
    INVALID_INSTANT = "invalid-instant"
    INVALID_WINDOW = "invalid-window"
    ID_MISMATCH = "id-mismatch"
    SECRET_REJECTED = "secret-rejected"
    OBLIGATION_UNRESOLVED = "obligation-unresolved"
    OBLIGATION_NOT_REFERENCED = "obligation-not-referenced"
    NOT_EVALUABLE = "not-evaluable"
    EVALUATION_UNKNOWN = "evaluation-unknown"
    JOURNAL_TAMPER = "journal-tamper"
    BRIDGE_NOT_APPLICABLE = "bridge-not-applicable"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.INVALID_INPUT,
            cls.VOCABULARY,
            cls.INVALID_INSTANT,
            cls.INVALID_WINDOW,
            cls.ID_MISMATCH,
            cls.SECRET_REJECTED,
            cls.OBLIGATION_UNRESOLVED,
            cls.OBLIGATION_NOT_REFERENCED,
            cls.NOT_EVALUABLE,
            cls.EVALUATION_UNKNOWN,
            cls.JOURNAL_TAMPER,
            cls.BRIDGE_NOT_APPLICABLE,
        )


class AssuranceError(ValueError):
    """Fail-closed caller-input/state error (mirrors the contracts/
    evidence family discipline).  Raised for caller-side validation
    failures; the ``code`` is machine-readable and stable, and the
    ``detail`` never carries raw exception text into stored state."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__("%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


__all__ = [
    "ASSURANCE_PREFIX",
    "AssuranceReasonCode",
    "AssuranceError",
]
