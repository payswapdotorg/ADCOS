"""Offer record serialization via the WORK-003 canonicalization machinery.

No second serialization system: canonical JSON bytes for transport,
duplicate-key rejection on parse, fail-closed on every malformed input.
Round-trips are byte-stable (serialize -> parse -> serialize produces
byte-identical output) and every parse re-derives the content identity
(tamper evidence at deserialization time, exactly like construction).
"""

from __future__ import annotations

import json
from typing import Any, List, Tuple

from protocol.canonicalization import canonical_json_bytes

from .errors import OfferError
from .model import CapabilityAdvertisement, OfferRecord

__all__ = [
    "SerializationError",
    "advertisement_from_bytes",
    "advertisement_to_bytes",
    "offer_from_bytes",
    "offer_to_bytes",
]


class SerializationError(ValueError):
    """Raised when serialized offer content is malformed."""


def advertisement_to_bytes(advertisement: CapabilityAdvertisement) -> bytes:
    """Canonical JSON bytes (WORK-003 canonicalization)."""
    try:
        return canonical_json_bytes(advertisement.to_dict())
    except Exception as error:
        raise SerializationError(
            "advertisement is not canonically representable: %s" % error
        ) from error


def offer_to_bytes(offer: OfferRecord) -> bytes:
    """Canonical JSON bytes (WORK-003 canonicalization)."""
    try:
        return canonical_json_bytes(offer.to_dict())
    except Exception as error:
        raise SerializationError(
            "offer is not canonically representable: %s" % error
        ) from error


def _reject_duplicate_keys(pairs: List[Tuple[str, Any]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise SerializationError(
                "duplicate object key %r in serialized offer content" % key
            )
        result[key] = value
    return result


def advertisement_from_bytes(data: bytes) -> CapabilityAdvertisement:
    """Parse canonical (or any valid) JSON bytes into a capability
    advertisement, failing closed on malformed structure (the parse
    re-derives the content identity — tamper evidence)."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SerializationError(
            "serialized advertisement is not valid UTF-8: %s" % error
        ) from error
    try:
        value = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as error:
        raise SerializationError(
            "serialized advertisement is not valid JSON: %s" % error
        ) from error
    try:
        return CapabilityAdvertisement.from_dict(value)
    except OfferError as error:
        raise SerializationError(
            "serialized advertisement is malformed: %s" % error
        ) from error


def offer_from_bytes(data: bytes) -> OfferRecord:
    """Parse canonical (or any valid) JSON bytes into an offer record,
    failing closed on malformed structure (the parse re-derives the
    content identity — tamper evidence)."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SerializationError(
            "serialized offer is not valid UTF-8: %s" % error
        ) from error
    try:
        value = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as error:
        raise SerializationError(
            "serialized offer is not valid JSON: %s" % error
        ) from error
    try:
        return OfferRecord.from_dict(value)
    except OfferError as error:
        raise SerializationError(
            "serialized offer is malformed: %s" % error
        ) from error
