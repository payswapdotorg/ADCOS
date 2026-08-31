"""WORK-042 platform-integration error model.

Mirrors the WORK-033/WORK-035/WORK-041 discipline: one typed error
class with a frozen reason vocabulary and deterministic
human-readable detail.  Reasons are DATA for diagnostics -- they
never branch core protocol semantics, and secrets never appear in
``detail``.

The vocabulary separates the failure families the W042 boundary
must keep apart: platform-observation integrity (what the platform
reported), event-record integrity (content-derived identity), the
append-only journal discipline (tamper, chain, sequence), durable
persistence (the store seam), checkpoint binding (snapshot/journal
consistency), and reconstruction integrity (state and recovery).
"""

from __future__ import annotations


class PlatformReasonCode:
    """The frozen WORK-042 reason vocabulary (the ACR-006 contract).

    Fail-closed is the DEFAULT: every reason below marks a condition
    where ambiguous, stale, contradictory, tampered, or corrupt input
    is REJECTED rather than silently converted into state.
    """

    INVALID_INPUT = "invalid-input"
    OBSERVATION_INVALID = "observation-invalid"
    OBSERVATION_SOURCE_FAILED = "observation-source-failed"
    EVENT_INVALID = "event-invalid"
    EVENT_CONTRADICTORY = "event-contradictory"
    JOURNAL_CORRUPT = "journal-corrupt"
    JOURNAL_APPEND_REJECTED = "journal-append-rejected"
    CHECKPOINT_INVALID = "checkpoint-invalid"
    CHECKPOINT_MISMATCH = "checkpoint-mismatch"
    STATE_INVALID = "state-invalid"
    STORE_FAILED = "store-failed"
    RECOVERY_REJECTED = "recovery-rejected"

    @classmethod
    def values(cls) -> tuple:
        return (
            cls.INVALID_INPUT,
            cls.OBSERVATION_INVALID,
            cls.OBSERVATION_SOURCE_FAILED,
            cls.EVENT_INVALID,
            cls.EVENT_CONTRADICTORY,
            cls.JOURNAL_CORRUPT,
            cls.JOURNAL_APPEND_REJECTED,
            cls.CHECKPOINT_INVALID,
            cls.CHECKPOINT_MISMATCH,
            cls.STATE_INVALID,
            cls.STORE_FAILED,
            cls.RECOVERY_REJECTED,
        )


class PlatformError(ValueError):
    """A typed platform-integration failure (reason + detail, fail
    closed)."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__("%s: %s" % (reason, detail))
        self.reason = reason
        self.detail = detail

    def __str__(self) -> str:  # pragma: no cover - trivial
        return "%s: %s" % (self.reason, self.detail)
