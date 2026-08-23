"""Capability statement validity and lifecycle evaluation.

Uses WORK-003 temporal primitives (RFC 3339 UTC, no wall-clock access —
the evaluation instant is always injected). The lifecycle distinguishes:

    ACTIVE      within its validity interval, not withdrawn
    WITHDRAWN   explicitly withdrawn by the provider (terminal here)
    EXPIRED     past expires_at (terminal for usability)

These are distinct concepts (a withdrawn capability is not an expired
one; neither is a node-identity revocation or a trust judgment — those
belong to other layers). Historical statements remain queryable for
audit/provenance; evaluation only decides CURRENT usability.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from protocol.temporal import TemporalError, parse_instant


class ValidityError(ValueError):
    """Raised when a validity interval is malformed or impossible."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__("%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


def validate_validity(valid_from: str, expires_at: str) -> None:
    """Structural validation: RFC 3339 UTC instants and a sane interval
    (expires_at >= valid_from). Fails closed."""
    try:
        start = parse_instant(valid_from)
    except TemporalError as error:
        raise ValidityError("valid-from", "valid_from: %s" % error) from error
    try:
        end = parse_instant(expires_at)
    except TemporalError as error:
        raise ValidityError("expires-at", "expires_at: %s" % error) from error
    if end < start:
        raise ValidityError(
            "interval",
            "expires_at %s is before valid_from %s" % (expires_at, valid_from),
        )


class StatementStatus:
    """Evaluated lifecycle status of a capability statement."""

    ACTIVE = "active"
    NOT_YET_VALID = "not-yet-valid"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"


def evaluate_status(
    *,
    valid_from: str,
    expires_at: str,
    withdrawn_at: Optional[str],
    now: datetime,
) -> str:
    """Evaluate the CURRENT usability status at the injected instant.

    Withdrawal is checked before expiry (both terminal for usability;
    withdrawal is an explicit act, expiry is time-based). Raises
    ValidityError for malformed values — malformed statements never
    negotiate as usable. "not-yet-valid" is reported for statements whose
    validity window has not opened yet — not usable now, distinct from
    expired.
    """
    validate_validity(valid_from, expires_at)
    start = parse_instant(valid_from)
    end = parse_instant(expires_at)
    if now.tzinfo is None:
        raise ValidityError("now", "evaluation instant must be timezone-aware")
    if withdrawn_at is not None:
        # A withdrawal timestamp must itself be a well-formed instant.
        parse_instant(withdrawn_at)
        return StatementStatus.WITHDRAWN
    if now > end:
        return StatementStatus.EXPIRED
    if now < start:
        return StatementStatus.NOT_YET_VALID
    return StatementStatus.ACTIVE
