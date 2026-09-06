"""WORK-046 developer platform error model.

Mirrors the WORK-051/W052/W053/W044/W045 discipline: ONE typed
error class with a frozen boundary reason vocabulary and
deterministic human-readable detail.  Reasons are DATA for
diagnostics -- they never branch core protocol semantics, and
secrets never appear in ``detail``.

The W046-specific invariant (the frozen contract's criterion 4):

> developer-facing errors preserve canonical ADCOS reason codes.

Every :class:`DeveloperApiError` therefore carries, besides its
own boundary reason, the EXACT canonical reason string of the
underlying ADCOS subsystem failure (``canonical_reason``; empty
when the failure is boundary-local, e.g. authentication).  The
boundary NEVER rewrites, flattens, or invents a second
reason-code authority: a CommercialCore ``lifecycle-illegal``
reaches the developer as ``lifecycle-illegal``; a UsageLedger
``account-unknown`` reaches the developer as
``account-unknown``.

The boundary vocabulary separates the failure families the W046
boundary owns: authentication and credential expiry, environment
isolation (sandbox/production non-interchangeability), scoped
capability authorization, API-version compatibility, rate
limiting with truthful retry guidance, durable idempotency
(duplicate, conflict, missing key), deterministic pagination,
resource visibility, webhook verification (signature, timestamp
replay, duplicate, stale order), and boundary integrity
(validation, store, journal corruption).

HTTP mapping and retryability classification are derived tables
(frozen, single site): the developer-facing error carries the
HTTP status, the canonical reason, a human-readable explanation,
the request correlation id, the retryability classification, the
resource reference, and the environment -- exactly the members
the W046 contract requires.
"""

from __future__ import annotations


class DeveloperApiReasonCode:
    """The frozen developer-platform boundary reason vocabulary."""

    INVALID_INPUT = "invalid-input"
    ROUTE_UNKNOWN = "route-unknown"
    AUTHENTICATION_INVALID = "authentication-invalid"
    AUTHENTICATION_EXPIRED = "authentication-expired"
    ENVIRONMENT_MISMATCH = "environment-mismatch"
    CAPABILITY_DENIED = "capability-denied"
    VERSION_UNSUPPORTED = "version-unsupported"
    RATE_LIMITED = "rate-limited"
    IDEMPOTENCY_KEY_REQUIRED = "idempotency-key-required"
    IDEMPOTENCY_CONFLICT = "idempotency-conflict"
    PAGINATION_INVALID = "pagination-invalid"
    FILTER_INVALID = "filter-invalid"
    RESOURCE_UNKNOWN = "resource-unknown"
    WEBHOOK_SIGNATURE_INVALID = "webhook-signature-invalid"
    WEBHOOK_TIMESTAMP_STALE = "webhook-timestamp-stale"
    WEBHOOK_DELIVERY_UNKNOWN = "webhook-delivery-unknown"
    STORE_FAILED = "store-failed"
    JOURNAL_CORRUPT = "journal-corrupt"

    @classmethod
    def values(cls) -> tuple:
        return (
            cls.INVALID_INPUT,
            cls.ROUTE_UNKNOWN,
            cls.AUTHENTICATION_INVALID,
            cls.AUTHENTICATION_EXPIRED,
            cls.ENVIRONMENT_MISMATCH,
            cls.CAPABILITY_DENIED,
            cls.VERSION_UNSUPPORTED,
            cls.RATE_LIMITED,
            cls.IDEMPOTENCY_KEY_REQUIRED,
            cls.IDEMPOTENCY_CONFLICT,
            cls.PAGINATION_INVALID,
            cls.FILTER_INVALID,
            cls.RESOURCE_UNKNOWN,
            cls.WEBHOOK_SIGNATURE_INVALID,
            cls.WEBHOOK_TIMESTAMP_STALE,
            cls.WEBHOOK_DELIVERY_UNKNOWN,
            cls.STORE_FAILED,
            cls.JOURNAL_CORRUPT,
        )


#: The frozen boundary-reason -> HTTP status table (single site).
REASON_HTTP_STATUS = {
    DeveloperApiReasonCode.INVALID_INPUT: 400,
    DeveloperApiReasonCode.ROUTE_UNKNOWN: 404,
    DeveloperApiReasonCode.AUTHENTICATION_INVALID: 401,
    DeveloperApiReasonCode.AUTHENTICATION_EXPIRED: 401,
    DeveloperApiReasonCode.ENVIRONMENT_MISMATCH: 403,
    DeveloperApiReasonCode.CAPABILITY_DENIED: 403,
    DeveloperApiReasonCode.VERSION_UNSUPPORTED: 400,
    DeveloperApiReasonCode.RATE_LIMITED: 429,
    DeveloperApiReasonCode.IDEMPOTENCY_KEY_REQUIRED: 400,
    DeveloperApiReasonCode.IDEMPOTENCY_CONFLICT: 409,
    DeveloperApiReasonCode.PAGINATION_INVALID: 400,
    DeveloperApiReasonCode.FILTER_INVALID: 400,
    DeveloperApiReasonCode.RESOURCE_UNKNOWN: 404,
    DeveloperApiReasonCode.WEBHOOK_SIGNATURE_INVALID: 400,
    DeveloperApiReasonCode.WEBHOOK_TIMESTAMP_STALE: 400,
    DeveloperApiReasonCode.WEBHOOK_DELIVERY_UNKNOWN: 404,
    DeveloperApiReasonCode.STORE_FAILED: 500,
    DeveloperApiReasonCode.JOURNAL_CORRUPT: 500,
}

#: The frozen canonical-reason -> HTTP status table: the mapping
#: for reasons surfaced from the canonical subsystems the W046
#: boundary adapts.  WORK-056 re-binds this table to the three
#: CURRENT accepted frozen vocabularies (the W052/W053 review
#: corrections renamed and extended the usage/allocation reason
#: sets after the W046-era names this table carried); every
#: reason below is carried UNCHANGED through the boundary (the
#: classification is transport DATA, never a rewrite).  Unknown
#: canonical reasons (future subsystem vocabularies) map to 400
#: and are non-retryable -- the boundary never guesses.
CANONICAL_REASON_HTTP_STATUS = {
    # WORK-051 CommercialCore (commercial/errors.py, current)
    "invalid-input": 400,
    "command-invalid": 400,
    "command-duplicate": 200,
    "command-conflict": 409,
    "transaction-unknown": 404,
    "lifecycle-illegal": 422,
    "history-immutable": 409,
    "reservation-expired": 422,
    "expiry-not-due": 422,
    "path-failure-rejected": 422,
    "non-delivery-rejected": 422,
    "settlement-rejected": 422,
    "payment-not-delivery": 422,
    "payment-not-settlement": 422,
    "reference-unknown": 404,
    "reference-family-invalid": 400,
    "event-invalid": 400,
    "journal-corrupt": 500,
    "store-failed": 500,
    "instant-invalid": 400,
    # WORK-052 UsageLedger (usage/errors.py, current post-
    # review-corrections vocabulary)
    "evidence-unknown": 404,
    "evidence-mismatch": 422,
    "transaction-not-delivering": 422,
    "observation-rejected": 422,
    "quantity-exceeded": 422,
    "window-invalid": 400,
    "provider-not-delivery": 422,
    "reservation-not-usage": 422,
    "observation-class-invalid": 400,
    "usage-sealed": 422,
    "final-immutable": 422,
    "compensation-requires-final": 422,
    "compensation-exceeded": 422,
    "dispute-already-open": 422,
    # WORK-053 EconomicAllocation (allocation/errors.py,
    # current post-review-corrections vocabulary)
    "policy-invalid": 400,
    "policy-unknown": 404,
    "policy-not-effective": 422,
    "split-out-of-bounds": 400,
    "distribution-invalid": 400,
    "usage-unknown": 404,
    "usage-mismatch": 422,
    "usage-not-final": 422,
    "payment-not-usage": 422,
    "settlement-not-usage": 422,
    "reference-mismatch": 422,
    "payment-not-settlement": 422,
    "settlement-not-payment": 422,
    "allocation-unknown": 404,
    "allocation-already-exists": 409,
    "settlement-immutable": 422,
    "compensation-requires-settled": 422,
}

#: The frozen retryability classification: which boundary
#: failures are safe to retry.  TRUTHFUL by construction: a
#: retryable classification exists only where the semantics
#: actually guarantee a safe retry (rate limiting recovers with
#: time; nothing else is marked retryable -- idempotent
#: mutations are safe to retry by KEY, which is guidance the
#: response envelope carries separately, never a blanket
#: retryable flag on errors).
RETRYABLE_REASONS = frozenset({
    DeveloperApiReasonCode.RATE_LIMITED,
})


class DeveloperApiError(ValueError):
    """A typed developer-platform boundary failure.

    Carries the exact canonical subsystem reason when the
    failure crossed an adapted ADCOS authority, plus the
    derived HTTP status and retryability classification.
    """

    def __init__(
        self,
        reason: str,
        detail: str = "",
        *,
        canonical_reason: str = "",
        request_id: str = "",
        resource_id: str = "",
        environment: str = "",
        retry_after: str = "",
    ) -> None:
        if reason not in DeveloperApiReasonCode.values():
            # cannot recursively raise DeveloperApiError here
            raise ValueError(
                "invalid-input: reason %r is not in the frozen boundary "
                "vocabulary" % reason
            )
        super().__init__("%s: %s" % (reason, detail))
        self.reason = reason
        self.detail = detail
        self.canonical_reason = canonical_reason
        self.request_id = request_id
        self.resource_id = resource_id
        self.environment = environment
        self.retry_after = retry_after

    # -- derived, frozen classification -------------------------------

    @property
    def http_status(self) -> int:
        if self.canonical_reason:
            return CANONICAL_REASON_HTTP_STATUS.get(self.canonical_reason, 400)
        return REASON_HTTP_STATUS[self.reason]

    @property
    def retryable(self) -> bool:
        return self.reason in RETRYABLE_REASONS

    def to_dict(self) -> dict:
        """The developer-facing error body (canonical members)."""
        return {
            "http_status": self.http_status,
            "reason": self.reason,
            "canonical_reason": self.canonical_reason,
            "message": self.detail,
            "retryable": self.retryable,
            "retry_after": self.retry_after,
            "resource_id": self.resource_id,
            "environment": self.environment,
            "request_id": self.request_id,
        }
