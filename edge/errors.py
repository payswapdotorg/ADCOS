"""WORK-034 edge-gateway error model.

Mirrors the WORK-033 agent discipline: a single typed error class
with a frozen reason vocabulary and a human-readable detail string.
Reasons are DATA for diagnostics -- they never branch core protocol
semantics, and secrets never appear in ``detail``.
"""

from __future__ import annotations


class EdgeReasonCode:
    """The frozen edge-gateway reason vocabulary."""

    INVALID_INPUT = "invalid-input"
    HARDWARE_INVALID = "hardware-invalid"
    HARDWARE_SOURCE_FAILED = "hardware-source-failed"
    BUDGET_INVALID = "budget-invalid"
    CLAIM_INVALID = "claim-invalid"
    CLAIM_REJECTED = "claim-rejected"
    FORWARD_REJECTED = "forward-rejected"
    ACCESS_UNAVAILABLE = "access-unavailable"

    @classmethod
    def values(cls) -> tuple:
        return (
            cls.INVALID_INPUT,
            cls.HARDWARE_INVALID,
            cls.HARDWARE_SOURCE_FAILED,
            cls.BUDGET_INVALID,
            cls.CLAIM_INVALID,
            cls.CLAIM_REJECTED,
            cls.FORWARD_REJECTED,
            cls.ACCESS_UNAVAILABLE,
        )


class EdgeError(ValueError):
    """A typed edge-gateway failure (reason + detail, fail closed)."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__("%s: %s" % (reason, detail))
        self.reason = reason
        self.detail = detail

    def __str__(self) -> str:  # pragma: no cover - trivial
        return "%s: %s" % (self.reason, self.detail)
