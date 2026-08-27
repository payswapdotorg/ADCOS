"""Input validation for the upgrade / compatibility family (WORK-029).

Every helper fails closed with a frozen :class:`UpgradeReasonCode`
(:class:`upgrade.errors.UpgradeError`) on the first malformed value.
Node references are opaque, trimmed, bounded strings (the node's
identity grammar is the WORK-004 identity authority's concern; the
upgrade family references it, it never re-validates or re-interprets
it -- the telemetry subject_ref discipline).
"""

from __future__ import annotations

import re
from typing import Mapping, Tuple

from protocol.temporal import TemporalError, parse_instant

from .errors import UpgradeError, UpgradeReasonCode

#: ``MAJOR.MINOR.PATCH`` implementation version (governance section 3
#: kind 4: the Implementation Version line, tracked by the
#: implementation, never specification evidence).
SOFTWARE_VERSION_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")

#: ``MAJOR.MINOR`` schema/protocol version (governance section 3
#: kinds 2 and 3).
DOTTED_PAIR_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")

#: Opaque reference bounds (the WORK-026 discipline).
_MAX_REF_LENGTH = 256


def validate_opaque_ref(value: object, label: str) -> str:
    """A non-empty, trimmed, bounded opaque reference string."""
    if not isinstance(value, str):
        raise UpgradeError(
            UpgradeReasonCode.INVALID_INPUT,
            "%s must be a str (got %s)" % (label, type(value).__name__),
        )
    stripped = value.strip()
    if not stripped or stripped != value:
        raise UpgradeError(
            UpgradeReasonCode.INVALID_INPUT,
            "%s must be a non-empty, trimmed opaque reference" % label,
        )
    if len(value) > _MAX_REF_LENGTH:
        raise UpgradeError(
            UpgradeReasonCode.INVALID_INPUT,
            "%s must be at most %d characters" % (label, _MAX_REF_LENGTH),
        )
    return value


def validate_instant(value: object, label: str) -> str:
    """An RFC 3339 Zulu instant string (injected; never a wall clock).

    Delegates to the WORK-003 temporal primitive (LOCK-018 -- standard
    leverage over reinvention); the upgrade family never re-implements
    instant parsing or comparison.
    """
    try:
        parse_instant(value)
    except TemporalError as error:
        raise UpgradeError(
            UpgradeReasonCode.VERSION_MALFORMED,
            "%s must be an RFC 3339 UTC instant: %s" % (label, error),
        ) from error
    return value  # type: ignore[return-value]


def parse_software_version(value: object) -> Tuple[int, int, int]:
    """Parse a strict ``MAJOR.MINOR.PATCH`` implementation version.

    No leading zeros, no extra components, no sign, no whitespace:
    one canonical spelling per version (deterministic comparison and
    byte-identical serialization depend on it).
    """
    if not isinstance(value, str):
        raise UpgradeError(
            UpgradeReasonCode.VERSION_MALFORMED,
            "software version must be a MAJOR.MINOR.PATCH str (got %s)"
            % (type(value).__name__,),
        )
    match = SOFTWARE_VERSION_PATTERN.fullmatch(value)
    if match is None:
        raise UpgradeError(
            UpgradeReasonCode.VERSION_MALFORMED,
            "software version %r must be canonical MAJOR.MINOR.PATCH "
            "(non-negative integers, no leading zeros)" % (value,),
        )
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def parse_dotted_pair(value: object, label: str) -> Tuple[int, int]:
    """Parse a strict ``MAJOR.MINOR`` (schema/protocol) version pair."""
    if not isinstance(value, str):
        raise UpgradeError(
            UpgradeReasonCode.VERSION_MALFORMED,
            "%s must be a MAJOR.MINOR str (got %s)" % (label, type(value).__name__),
        )
    match = DOTTED_PAIR_PATTERN.fullmatch(value)
    if match is None:
        raise UpgradeError(
            UpgradeReasonCode.VERSION_MALFORMED,
            "%s %r must be canonical MAJOR.MINOR (non-negative integers, "
            "no leading zeros)" % (label, value),
        )
    return (int(match.group(1)), int(match.group(2)))


def validate_schema_version_map(value: object, label: str) -> Tuple[Tuple[str, str], ...]:
    """Validate a ``schema_id -> schema_version`` mapping into the
    canonical sorted tuple-of-pairs form (deterministic order)."""
    if not isinstance(value, Mapping):
        raise UpgradeError(
            UpgradeReasonCode.INVALID_INPUT,
            "%s must be a mapping (got %s)" % (label, type(value).__name__),
        )
    pairs = []
    for schema_id, version in value.items():
        validate_opaque_ref(schema_id, "%s schema id" % label)
        if schema_id != schema_id.lower() or not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", schema_id):
            raise UpgradeError(
                UpgradeReasonCode.INVALID_INPUT,
                "%s schema id %r must be a lowercase dotted identifier" % (label, schema_id),
            )
        parse_dotted_pair(version, "%s schema version" % label)
        pairs.append((schema_id, version))
    seen = {schema_id for schema_id, _ in pairs}
    if len(seen) != len(pairs):
        raise UpgradeError(
            UpgradeReasonCode.INVALID_INPUT, "%s carries duplicate schema ids" % label
        )
    return tuple(sorted(pairs))
