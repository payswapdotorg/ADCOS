"""WORK-053 EconomicAllocation error model.

Mirrors the accepted WORK-041/WORK-042/WORK-051/WORK-052
discipline: one typed error class with a frozen reason
vocabulary and deterministic human-readable detail.  Reasons
are DATA for diagnostics -- they never branch core protocol
semantics, and secrets never appear in ``detail``.

The vocabulary separates the failure families the W053 boundary
must keep apart: input/command integrity, policy-version
integrity (unknown, not-yet/no-longer effective, invalid
terms), allocation arithmetic (split bounds, distribution
discipline, rounding), the billable-usage admission separations
(payment/settlement references are never usage facts; only
BILLABLE_FINAL usage creates allocation), external-reference
integrity (unknown, correlation mismatch, the payment/
settlement kind table), the allocation state gates (unknown
subject, already allocated, settlement immutability), the
compensation discipline (requires settled, exceeded, one open
dispute), journal integrity (tamper, corruption), and the store
seam.
"""

from __future__ import annotations


class AllocationReasonCode:
    """The frozen EconomicAllocation reason vocabulary (W053
    contract)."""

    INVALID_INPUT = "invalid-input"
    COMMAND_INVALID = "command-invalid"
    COMMAND_CONFLICT = "command-conflict"
    POLICY_INVALID = "policy-invalid"
    POLICY_UNKNOWN = "policy-unknown"
    POLICY_NOT_EFFECTIVE = "policy-not-effective"
    SPLIT_OUT_OF_BOUNDS = "split-out-of-bounds"
    DISTRIBUTION_INVALID = "distribution-invalid"
    USAGE_UNKNOWN = "usage-unknown"
    USAGE_MISMATCH = "usage-mismatch"
    USAGE_NOT_FINAL = "usage-not-final"
    PAYMENT_NOT_USAGE = "payment-not-usage"
    SETTLEMENT_NOT_USAGE = "settlement-not-usage"
    REFERENCE_UNKNOWN = "reference-unknown"
    REFERENCE_MISMATCH = "reference-mismatch"
    PAYMENT_NOT_SETTLEMENT = "payment-not-settlement"
    SETTLEMENT_NOT_PAYMENT = "settlement-not-payment"
    ALLOCATION_UNKNOWN = "allocation-unknown"
    ALLOCATION_ALREADY_EXISTS = "allocation-already-exists"
    SETTLEMENT_IMMUTABLE = "settlement-immutable"
    COMPENSATION_REQUIRES_SETTLED = "compensation-requires-settled"
    COMPENSATION_EXCEEDED = "compensation-exceeded"
    DISPUTE_ALREADY_OPEN = "dispute-already-open"
    EVENT_INVALID = "event-invalid"
    JOURNAL_CORRUPT = "journal-corrupt"
    STORE_FAILED = "store-failed"
    INSTANT_INVALID = "instant-invalid"

    @classmethod
    def values(cls) -> tuple:
        return (
            cls.INVALID_INPUT,
            cls.COMMAND_INVALID,
            cls.COMMAND_CONFLICT,
            cls.POLICY_INVALID,
            cls.POLICY_UNKNOWN,
            cls.POLICY_NOT_EFFECTIVE,
            cls.SPLIT_OUT_OF_BOUNDS,
            cls.DISTRIBUTION_INVALID,
            cls.USAGE_UNKNOWN,
            cls.USAGE_MISMATCH,
            cls.USAGE_NOT_FINAL,
            cls.PAYMENT_NOT_USAGE,
            cls.SETTLEMENT_NOT_USAGE,
            cls.REFERENCE_UNKNOWN,
            cls.REFERENCE_MISMATCH,
            cls.PAYMENT_NOT_SETTLEMENT,
            cls.SETTLEMENT_NOT_PAYMENT,
            cls.ALLOCATION_UNKNOWN,
            cls.ALLOCATION_ALREADY_EXISTS,
            cls.SETTLEMENT_IMMUTABLE,
            cls.COMPENSATION_REQUIRES_SETTLED,
            cls.COMPENSATION_EXCEEDED,
            cls.DISPUTE_ALREADY_OPEN,
            cls.EVENT_INVALID,
            cls.JOURNAL_CORRUPT,
            cls.STORE_FAILED,
            cls.INSTANT_INVALID,
        )


class AllocationError(ValueError):
    """A typed EconomicAllocation failure (reason + detail, fail
    closed)."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__("%s: %s" % (reason, detail))
        self.reason = reason
        self.detail = detail

    def __str__(self) -> str:  # pragma: no cover - trivial
        return "%s: %s" % (self.reason, self.detail)
