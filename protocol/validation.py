"""Envelope validation and the acceptance path.

Deterministic pipeline (spec/prompts/WORK-003.md sections 4, 6, 7):

1. structural parsing (codec + envelope contract) — failures classify as
   ``rejected_malformed``;
2. protocol major-version classification — unknown majors classify as
   ``rejected_incompatible_major``;
3. required-extension scan — an extension entry marked ``"required":
   true`` that the implementation does not understand classifies as
   ``rejected_unknown_required`` (fail safely rather than processing an
   incomplete semantic message);
4. unknown message-type policy — well-formed unregistered types are
   either rejected or forwarded opaquely, per the EXPLICIT policy
   supplied by the caller (no universal accept-all rule);
5. temporal validation — expired, not-yet-valid, inverted, or malformed
   temporal metadata classifies as ``rejected_temporal``;
6. optional replay-validation hook — caller-supplied and deterministic;
   WORK-003 deliberately ships no distributed replay state.

A ``ValidatedEnvelope`` is obtainable ONLY through this module's
validation path, so an expired or malformed envelope cannot be
accidentally processed through the normal API.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional, Union

from .codec import CodecError, WireCodec, get_codec
from .envelope import Envelope, EnvelopeError, envelope_from_mapping
from .temporal import TemporalError, check_temporal, parse_instant
from .versioning import Classification, protocol_metadata

DEFAULT_MAX_INPUT_BYTES = 1 << 20  # 1 MiB
DEFAULT_MAX_DEPTH = 64


class UnknownTypePolicy(Enum):
    """Explicit policy for well-formed but unregistered message types."""

    REJECT = "reject"
    FORWARD_OPAQUE = "forward-opaque"


class ReplayDecision(Enum):
    """Decision returned by a caller-supplied replay validator."""

    ALLOW = "allow"
    REJECT = "reject"


ReplayValidator = Callable[[Envelope], ReplayDecision]


@dataclass(frozen=True)
class ParsePolicy:
    """Explicit, injectable validation policy.

    ``unknown_type`` has no implicit default at the accept() call site:
    the caller must decide how unknown message types are handled.
    ``clock_skew`` is the tolerance window for expiry and not-yet-valid
    checks (default: none). ``max_input_bytes`` bounds encoded input
    size.
    """

    unknown_type: UnknownTypePolicy
    clock_skew: timedelta = timedelta(0)
    max_input_bytes: int = DEFAULT_MAX_INPUT_BYTES


@dataclass(frozen=True)
class ValidatedEnvelope:
    """An envelope that has passed the full validation path.

    Only constructible through validate()/accept(); downstream
    processing should require this type.
    """

    envelope: Envelope
    classification: str
    validated_at: datetime


@dataclass(frozen=True)
class AcceptOutcome:
    """Deterministic result of validation/acceptance."""

    accepted: bool
    validated: Optional[ValidatedEnvelope]
    classification: str
    detail: str

    @property
    def rejected(self) -> bool:
        return not self.accepted


def _reject(classification: str, detail: str) -> AcceptOutcome:
    return AcceptOutcome(
        accepted=False, validated=None, classification=classification, detail=detail
    )


def _has_unknown_optional_content(envelope: Envelope) -> bool:
    # Every registered extension is unknown to this implementation (no
    # extension vocabulary exists yet), and all extra top-level members
    # are unknown optional fields by construction.
    return bool(envelope.extensions) or bool(envelope.extra)


def validate(
    envelope: Envelope,
    *,
    now: datetime,
    policy: ParsePolicy,
    replay: Optional[ReplayValidator] = None,
) -> AcceptOutcome:
    """Validate a parsed envelope against the deterministic pipeline."""
    metadata = protocol_metadata()

    # 1. protocol major version
    if not metadata.is_known_major(envelope.version):
        return _reject(
            Classification.REJECTED_INCOMPATIBLE_MAJOR,
            "protocol major version %d is not known (known: %s)"
            % (envelope.version, sorted(metadata.known_major_versions)),
        )

    # 2. required-extension scan (fail safely on required-but-unknown features)
    for extension_name in sorted(envelope.extensions):
        value = envelope.extensions[extension_name]
        if isinstance(value, dict) and value.get("required") is True:
            return _reject(
                Classification.REJECTED_UNKNOWN_REQUIRED,
                "extension %r is marked required but is not understood" % extension_name,
            )

    # 3. message-type classification under the explicit policy
    type_known = metadata.is_known_message_type(envelope.message_type)
    if not type_known and policy.unknown_type is UnknownTypePolicy.REJECT:
        return _reject(
            Classification.REJECTED_UNKNOWN_TYPE,
            "message_type %r is well-formed but unregistered, and the policy rejects "
            "unknown types" % envelope.message_type,
        )

    # 4. temporal validation (before any acceptance)
    try:
        temporal_error = check_temporal(
            envelope.issued_at, envelope.expires_at, now, policy.clock_skew
        )
    except TemporalError as error:
        return _reject(Classification.REJECTED_TEMPORAL, "temporal validation failed: %s" % error)
    if temporal_error is not None:
        return _reject(Classification.REJECTED_TEMPORAL, temporal_error)

    # 5. replay-validation hook (caller-supplied; no shipped replay state)
    if replay is not None:
        try:
            decision = replay(envelope)
        except Exception as error:  # validator failure must fail safely
            return _reject(
                Classification.REJECTED_REPLAY,
                "replay validator raised %s: %s" % (type(error).__name__, error),
            )
        if decision is ReplayDecision.REJECT:
            return _reject(
                Classification.REJECTED_REPLAY, "replay validator rejected the message"
            )

    # 6. success classification
    if not type_known:
        classification = Classification.UNKNOWN_OPTIONAL_FORWARDED
        detail = "message type is unregistered; envelope is valid and the payload is forwarded opaquely"
    elif _has_unknown_optional_content(envelope):
        classification = Classification.KNOWN_ADDITIVE
        detail = "message parsed with unknown optional content preserved"
    else:
        classification = Classification.KNOWN_COMPATIBLE
        detail = "message parsed and processed"
    return AcceptOutcome(
        accepted=True,
        validated=ValidatedEnvelope(
            envelope=envelope, classification=classification, validated_at=now
        ),
        classification=classification,
        detail=detail,
    )


_SAFE_DECODE_ERRORS = (
    CodecError,
    EnvelopeError,
    TemporalError,
    UnicodeDecodeError,
    json.JSONDecodeError,
    RecursionError,
    ValueError,
)


def accept(
    data: Union[bytes, bytearray, str],
    *,
    now: datetime,
    policy: ParsePolicy,
    codec: Optional[WireCodec] = None,
    replay: Optional[ReplayValidator] = None,
) -> AcceptOutcome:
    """Decode and validate an encoded envelope (the normal entry point).

    All malformed inputs — invalid UTF-8, invalid JSON/CBOR, duplicate
    keys, contract violations, truncation, oversize input — fail safely
    with a ``rejected_malformed`` outcome; nothing is ever silently
    downgraded, coerced, or stripped to make a parse succeed.
    """
    if codec is None:
        codec = get_codec("json-debug")
    if isinstance(data, str):
        try:
            raw = data.encode("utf-8")
        except UnicodeEncodeError as error:
            return _reject(
                Classification.REJECTED_MALFORMED, "input text is not encodable: %s" % error
            )
    elif isinstance(data, (bytes, bytearray)):
        raw = bytes(data)
    else:
        raise TypeError("accept() expects bytes, bytearray, or str input")
    if len(raw) > policy.max_input_bytes:
        return _reject(
            Classification.REJECTED_MALFORMED,
            "input of %d bytes exceeds the policy maximum of %d" % (len(raw), policy.max_input_bytes),
        )
    try:
        envelope = codec.decode(raw)
    except _SAFE_DECODE_ERRORS as error:
        return _reject(
            Classification.REJECTED_MALFORMED,
            "%s: %s" % (type(error).__name__, error),
        )
    return validate(envelope, now=now, policy=policy, replay=replay)


def validation_clock(value: str) -> datetime:
    """Parse a deterministic validation time (RFC 3339 UTC)."""
    return parse_instant(value)
