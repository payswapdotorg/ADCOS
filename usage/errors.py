"""WORK-052 UsageLedger error model.

Mirrors the accepted WORK-041/WORK-042/WORK-051 discipline: one
typed error class with a frozen reason vocabulary and
deterministic human-readable detail.  Reasons are DATA for
diagnostics -- they never branch core protocol semantics, and
secrets never appear in ``detail``.

The vocabulary separates the failure families the W052 boundary
must keep apart: input/command integrity, usage observation
admission (delivery-evidence correlation, quantity/window
discipline), idempotency (duplicates and conflicting reuse of an
observation or evidence identity), the usage transaction state
gates (billable finality), the payment/reservation/provider
separations (payment capture, reservation/lease state, and
provider observations never create usage), evidence/index
integrity (fabricated citations), compensation discipline
(refunds/reversals/disputes against a sealed statement), journal
integrity (tamper, corruption), and the store seam.
"""

from __future__ import annotations


class UsageReasonCode:
    """The frozen UsageLedger reason vocabulary (W052 contract)."""

    INVALID_INPUT = "invalid-input"
    COMMAND_INVALID = "command-invalid"
    COMMAND_CONFLICT = "command-conflict"
    TRANSACTION_UNKNOWN = "transaction-unknown"
    TRANSACTION_NOT_DELIVERING = "transaction-not-delivering"
    OBSERVATION_REJECTED = "observation-rejected"
    EVIDENCE_UNKNOWN = "evidence-unknown"
    EVIDENCE_MISMATCH = "evidence-mismatch"
    QUANTITY_EXCEEDED = "quantity-exceeded"
    WINDOW_INVALID = "window-invalid"
    PAYMENT_NOT_DELIVERY = "payment-not-delivery"
    PROVIDER_NOT_DELIVERY = "provider-not-delivery"
    RESERVATION_NOT_USAGE = "reservation-not-usage"
    OBSERVATION_CLASS_INVALID = "observation-class-invalid"
    USAGE_SEALED = "usage-sealed"
    FINAL_IMMUTABLE = "final-immutable"
    COMPENSATION_REQUIRES_FINAL = "compensation-requires-final"
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
            cls.TRANSACTION_UNKNOWN,
            cls.TRANSACTION_NOT_DELIVERING,
            cls.OBSERVATION_REJECTED,
            cls.EVIDENCE_UNKNOWN,
            cls.EVIDENCE_MISMATCH,
            cls.QUANTITY_EXCEEDED,
            cls.WINDOW_INVALID,
            cls.PAYMENT_NOT_DELIVERY,
            cls.PROVIDER_NOT_DELIVERY,
            cls.RESERVATION_NOT_USAGE,
            cls.OBSERVATION_CLASS_INVALID,
            cls.USAGE_SEALED,
            cls.FINAL_IMMUTABLE,
            cls.COMPENSATION_REQUIRES_FINAL,
            cls.COMPENSATION_EXCEEDED,
            cls.DISPUTE_ALREADY_OPEN,
            cls.EVENT_INVALID,
            cls.JOURNAL_CORRUPT,
            cls.STORE_FAILED,
            cls.INSTANT_INVALID,
        )


class UsageError(ValueError):
    """A typed UsageLedger failure (reason + detail, fail closed)."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__("%s: %s" % (reason, detail))
        self.reason = reason
        self.detail = detail

    def __str__(self) -> str:  # pragma: no cover - trivial
        return "%s: %s" % (self.reason, self.detail)
