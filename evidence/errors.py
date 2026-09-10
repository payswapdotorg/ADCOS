"""ADCOS typed evidence-record error model (M005 — Evidence and Assurance).

Leaf module: imported by every other ``evidence`` submodule, imports
nothing from the package (no import cycles).  :class:`EvidenceError`
is the fail-closed caller-input/state error raised for caller-side
validation failures; the reason-code vocabulary is frozen (adding a
code is a deliberate vocabulary change, never a silent extension).

The evidence layer is a TYPED DATA layer, never a second authority:
``/evidence`` owns the typed evidence records (LOCK-106 — claim,
observation, commitment and attestation are distinct types); it never
interprets contracts (LOCK-101: the contracts/ domain stays the sole
contract authority), never evaluates assurance obligations (the
``assurance/`` domain owns evaluation), and never hosts provider
credentials or subscriber secrets (LOCK-119).
"""

from __future__ import annotations

from typing import Tuple

#: Canonical evidence family prefix (the M005 family namespace,
#: mirroring the telemetry family-prefix convention).
EVIDENCE_PREFIX = "evidence"


class EvidenceReasonCode:
    """Frozen reason-code vocabulary (typed evidence-record layer).

    Adding a code is a deliberate vocabulary change, never a silent
    extension.
    """

    INVALID_INPUT = "invalid-input"
    VOCABULARY = "vocabulary"
    INVALID_CONFIDENCE = "invalid-confidence"
    INVALID_INSTANT = "invalid-instant"
    INVALID_WINDOW = "invalid-window"
    ID_MISMATCH = "id-mismatch"
    SECRET_REJECTED = "secret-rejected"
    RECORD_UNKNOWN = "record-unknown"
    RECORD_TAMPER = "record-tamper"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.INVALID_INPUT,
            cls.VOCABULARY,
            cls.INVALID_CONFIDENCE,
            cls.INVALID_INSTANT,
            cls.ID_MISMATCH,
            cls.SECRET_REJECTED,
            cls.RECORD_UNKNOWN,
            cls.RECORD_TAMPER,
        )


class EvidenceError(ValueError):
    """Fail-closed caller-input/state error (mirrors the contracts/
    telemetry family discipline).  Raised for caller-side validation
    failures; the ``code`` is machine-readable and stable, and the
    ``detail`` never carries raw exception text into stored state."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__("%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


__all__ = [
    "EVIDENCE_PREFIX",
    "EvidenceReasonCode",
    "EvidenceError",
]
