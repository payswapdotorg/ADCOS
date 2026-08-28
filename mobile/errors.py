"""WORK-035 mobile-agent error model.

Mirrors the WORK-033/WORK-034 discipline: a single typed error class
with a frozen reason vocabulary and a human-readable detail string.
Reasons are DATA for diagnostics -- they never branch core protocol
semantics, and secrets never appear in ``detail``.
"""

from __future__ import annotations


class MobileReasonCode:
    """The frozen mobile-participation reason vocabulary."""

    INVALID_INPUT = "invalid-input"
    PLATFORM_INVALID = "platform-invalid"
    PLATFORM_SOURCE_FAILED = "platform-source-failed"
    LIFECYCLE_ILLEGAL = "lifecycle-illegal"
    COMMAND_STOPPED = "command-stopped"
    SESSION_UNKNOWN = "session-unknown"
    SEND_REJECTED = "send-rejected"
    DISCOVERY_REJECTED = "discovery-rejected"
    GRANT_INVALID = "grant-invalid"
    SNAPSHOT_INVALID = "snapshot-invalid"
    ACCESS_UNAVAILABLE = "access-unavailable"

    @classmethod
    def values(cls) -> tuple:
        return (
            cls.INVALID_INPUT,
            cls.PLATFORM_INVALID,
            cls.PLATFORM_SOURCE_FAILED,
            cls.LIFECYCLE_ILLEGAL,
            cls.COMMAND_STOPPED,
            cls.SESSION_UNKNOWN,
            cls.SEND_REJECTED,
            cls.DISCOVERY_REJECTED,
            cls.GRANT_INVALID,
            cls.SNAPSHOT_INVALID,
            cls.ACCESS_UNAVAILABLE,
        )


class MobileError(ValueError):
    """A typed mobile-participation failure (reason + detail, fail closed)."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__("%s: %s" % (reason, detail))
        self.reason = reason
        self.detail = detail

    def __str__(self) -> str:  # pragma: no cover - trivial
        return "%s: %s" % (self.reason, self.detail)
