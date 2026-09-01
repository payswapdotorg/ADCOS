"""WORK-051 CommercialCore error model.

Mirrors the WORK-041/WORK-042 discipline: one typed error class
with a frozen reason vocabulary and deterministic human-readable
detail.  Reasons are DATA for diagnostics -- they never branch
core protocol semantics, and secrets never appear in ``detail``.

The vocabulary separates the failure families the W051 boundary
must keep apart: input/command integrity, commercial lifecycle
discipline (the canonical state machine), idempotency (duplicates
and conflicting duplicates), reservation expiry, the compensating
families (cancellation, expiry, path failure, non-delivery),
settlement integrity (BillableFinal gate, delivery evidence),
the payment/delivery authority separation, external reference
integrity (fabricated session/NetworkPath/delivery references),
journal integrity (tamper, corruption), settled-history
immutability, and event/record validation.
"""

from __future__ import annotations


class CommercialReasonCode:
    """The frozen CommercialCore reason vocabulary (W051 contract)."""

    INVALID_INPUT = "invalid-input"
    COMMAND_INVALID = "command-invalid"
    COMMAND_DUPLICATE = "command-duplicate"
    COMMAND_CONFLICT = "command-conflict"
    TRANSACTION_UNKNOWN = "transaction-unknown"
    LIFECYCLE_ILLEGAL = "lifecycle-illegal"
    HISTORY_IMMUTABLE = "history-immutable"
    RESERVATION_EXPIRED = "reservation-expired"
    EXPIRY_NOT_DUE = "expiry-not-due"
    PATH_FAILURE_REJECTED = "path-failure-rejected"
    NON_DELIVERY_REJECTED = "non-delivery-rejected"
    SETTLEMENT_REJECTED = "settlement-rejected"
    PAYMENT_NOT_DELIVERY = "payment-not-delivery"
    PAYMENT_NOT_SETTLEMENT = "payment-not-settlement"
    REFERENCE_UNKNOWN = "reference-unknown"
    REFERENCE_FAMILY_INVALID = "reference-family-invalid"
    EVENT_INVALID = "event-invalid"
    JOURNAL_CORRUPT = "journal-corrupt"
    STORE_FAILED = "store-failed"
    INSTANT_INVALID = "instant-invalid"

    @classmethod
    def values(cls) -> tuple:
        return (
            cls.INVALID_INPUT,
            cls.COMMAND_INVALID,
            cls.COMMAND_DUPLICATE,
            cls.COMMAND_CONFLICT,
            cls.TRANSACTION_UNKNOWN,
            cls.LIFECYCLE_ILLEGAL,
            cls.HISTORY_IMMUTABLE,
            cls.RESERVATION_EXPIRED,
            cls.EXPIRY_NOT_DUE,
            cls.PATH_FAILURE_REJECTED,
            cls.NON_DELIVERY_REJECTED,
            cls.SETTLEMENT_REJECTED,
            cls.PAYMENT_NOT_DELIVERY,
            cls.PAYMENT_NOT_SETTLEMENT,
            cls.REFERENCE_UNKNOWN,
            cls.REFERENCE_FAMILY_INVALID,
            cls.EVENT_INVALID,
            cls.JOURNAL_CORRUPT,
            cls.STORE_FAILED,
            cls.INSTANT_INVALID,
        )


class CommercialError(ValueError):
    """A typed CommercialCore failure (reason + detail, fail closed)."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__("%s: %s" % (reason, detail))
        self.reason = reason
        self.detail = detail

    def __str__(self) -> str:  # pragma: no cover - trivial
        return "%s: %s" % (self.reason, self.detail)
