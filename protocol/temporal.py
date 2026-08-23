"""Temporal metadata handling for the ADCOS envelope.

RFC 3339 UTC instants with ``Z`` suffix only — no local-time ambiguity.
Fractional seconds beyond microsecond precision are truncated for
comparison purposes (deterministic, documented); timestamp strings
themselves are never rewritten.

WORK-003 owns the validation mechanics only: presence/format checks,
``expires_at >= issued_at``, expiry and not-yet-valid checks with a
configurable clock-skew tolerance, and a replay-validation hook. There is
no persistent or distributed replay state here.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from .versioning import protocol_metadata  # noqa: F401  (kept for API locality)

RFC3339_UTC_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(\.\d+)?Z$"
)


class TemporalError(ValueError):
    """Raised when a temporal value is malformed or semantically invalid."""


def parse_instant(value: object) -> datetime:
    """Parse an RFC 3339 UTC instant (``Z`` suffix required).

    Raises TemporalError for malformed values, invalid calendar dates,
    or non-string input. Returns a timezone-aware UTC datetime.
    """
    if not isinstance(value, str):
        raise TemporalError("timestamp must be a string (found %s)" % type(value).__name__)
    match = RFC3339_UTC_RE.fullmatch(value)
    if match is None:
        raise TemporalError("timestamp %r is not RFC 3339 UTC (YYYY-MM-DDTHH:MM:SS[.f]Z)" % value)
    year, month, day, hour, minute, second = (int(match.group(i)) for i in range(1, 7))
    fraction = match.group(7)
    microsecond = int((fraction[1:] + "000000")[:6]) if fraction else 0
    try:
        return datetime(
            year, month, day, hour, minute, second, microsecond, tzinfo=timezone.utc
        )
    except ValueError as error:
        raise TemporalError("timestamp %r is not a valid calendar instant: %s" % (value, error)) from error


def check_temporal(
    issued_at: str,
    expires_at: str,
    now: datetime,
    clock_skew: timedelta = timedelta(0),
) -> Optional[str]:
    """Validate envelope temporal metadata against ``now``.

    Returns None when the message is temporally valid, otherwise a
    deterministic error code:

    - ``issued-at-invalid`` / ``expires-at-invalid`` — malformed values;
    - ``expires-before-issued`` — expires_at < issued_at;
    - ``expired`` — now is past expires_at (beyond the skew tolerance);
    - ``not-yet-valid`` — issued_at is in the future beyond the skew
      tolerance.

    ``now`` must be timezone-aware; naive datetimes are rejected.
    """
    if now.tzinfo is None:
        raise TemporalError("validation time must be timezone-aware (UTC)")
    try:
        issued = parse_instant(issued_at)
    except TemporalError as error:
        return "issued-at-invalid"
    try:
        expires = parse_instant(expires_at)
    except TemporalError:
        return "expires-at-invalid"
    if expires < issued:
        return "expires-before-issued"
    if now > expires + clock_skew:
        return "expired"
    if issued > now + clock_skew:
        return "not-yet-valid"
    return None
