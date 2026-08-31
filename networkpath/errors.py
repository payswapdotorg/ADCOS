"""WORK-041 NetworkPath error model.

Mirrors the WORK-033/WORK-035 discipline: one typed error class with
a frozen reason vocabulary and deterministic human-readable detail.
Reasons are DATA for diagnostics -- they never branch core protocol
semantics, and secrets never appear in ``detail``.
"""

from __future__ import annotations


class NetworkPathReasonCode:
    """The frozen NetworkPath reason vocabulary (WORK-041 contract).

    The vocabulary separates the failure families the W041 boundary
    must keep apart: observation integrity (platform facts), path
    lifecycle discipline (detection/validation/binding/activation/
    retirement), authority-mediated binding/probe outcomes, and
    evidence integrity.
    """

    INVALID_INPUT = "invalid-input"
    OBSERVATION_INVALID = "observation-invalid"
    OBSERVATION_SOURCE_FAILED = "observation-source-failed"
    PATH_UNKNOWN = "path-unknown"
    LIFECYCLE_ILLEGAL = "lifecycle-illegal"
    DUPLICATE_TRANSITION = "duplicate-transition"
    VALIDATION_REJECTED = "validation-rejected"
    BIND_REJECTED = "bind-rejected"
    PROBE_REJECTED = "probe-rejected"
    SESSION_UNKNOWN = "session-unknown"
    EVIDENCE_INVALID = "evidence-invalid"

    @classmethod
    def values(cls) -> tuple:
        return (
            cls.INVALID_INPUT,
            cls.OBSERVATION_INVALID,
            cls.OBSERVATION_SOURCE_FAILED,
            cls.PATH_UNKNOWN,
            cls.LIFECYCLE_ILLEGAL,
            cls.DUPLICATE_TRANSITION,
            cls.VALIDATION_REJECTED,
            cls.BIND_REJECTED,
            cls.PROBE_REJECTED,
            cls.SESSION_UNKNOWN,
            cls.EVIDENCE_INVALID,
        )


class NetworkPathError(ValueError):
    """A typed NetworkPath failure (reason + detail, fail closed)."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__("%s: %s" % (reason, detail))
        self.reason = reason
        self.detail = detail

    def __str__(self) -> str:  # pragma: no cover - trivial
        return "%s: %s" % (self.reason, self.detail)
