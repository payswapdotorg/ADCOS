"""Capability statement serialization via the WORK-003 machinery.

No second serialization system: canonical JSON bytes for transport
(through the WORK-003 envelope where applicable), duplicate-key
rejection on parse, fail-closed on every malformed input.
"""

from __future__ import annotations

import json
from typing import Any, List, Tuple

from protocol.canonicalization import canonical_json_bytes

from .model import CapabilityError, CapabilityStatement, statement_from_mapping


class SerializationError(ValueError):
    """Raised when serialized capability content is malformed."""


def statement_to_dict(statement: CapabilityStatement) -> dict:
    return statement.to_dict()


def statement_to_bytes(statement: CapabilityStatement) -> bytes:
    """Canonical JSON bytes (WORK-003 canonicalization)."""
    try:
        return canonical_json_bytes(statement.to_dict())
    except Exception as error:
        raise SerializationError(
            "statement is not canonically representable: %s" % error
        ) from error


def _reject_duplicate_keys(pairs: List[Tuple[str, Any]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise SerializationError("duplicate object key %r in serialized capability" % key)
        result[key] = value
    return result


def statement_from_bytes(data: bytes) -> CapabilityStatement:
    """Parse canonical (or any valid) JSON bytes into a statement,
    failing closed on malformed structure."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SerializationError("serialized capability is not valid UTF-8: %s" % error) from error
    try:
        value = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as error:
        raise SerializationError("serialized capability is not valid JSON: %s" % error) from error
    try:
        return statement_from_mapping(value)
    except CapabilityError as error:
        raise SerializationError("serialized capability is malformed: %s" % error) from error
