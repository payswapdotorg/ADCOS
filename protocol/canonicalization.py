"""Canonical JSON serialization for the ADCOS supported value subset.

Deterministic canonical form (provisional until the production
canonicalization profile is frozen by later conformance work, per
spec/architecture.md section 7):

- Object keys are sorted by UTF-16 code-unit order (the sort key is the
  key encoded as UTF-16 big-endian), matching RFC 8785 (JCS) for the
  supported subset.
- No insignificant whitespace: tokens are separated by ``","`` and
  ``":"`` only.
- Strings use minimal JSON escaping: ``"`` and ``\\`` are escaped; the
  five control characters with short escapes use them (``\\b \\f \\n \\r
  \\t``); other characters below U+0020 use ``\\u00xx`` with lowercase
  hexadecimal digits; all other characters are emitted literally and the
  output is UTF-8.
- Booleans and null use their JSON literals; ``bool`` is checked before
  ``int`` because Python booleans are integer subclasses.
- Integers are emitted in shortest decimal form.
- Floating-point values are OUTSIDE the canonical subset and raise
  CanonicalizationError (fail safely) rather than being silently
  formatted with platform-specific float rules.
- Absent optional members are omitted, never emitted as null.
- Duplicate object keys are impossible by construction (dictionaries);
  parsers reject duplicate keys separately.

Two conformant implementations of this documented subset can
independently reproduce identical canonical bytes for any supported
value.
"""

from __future__ import annotations

from typing import Any, List

MAX_CANONICAL_DEPTH = 64


class CanonicalizationError(ValueError):
    """Raised when a value cannot be represented in canonical form."""


_SHORT_ESCAPES = {
    '"': '\\"',
    "\\": "\\\\",
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


def _canonical_string(value: str) -> str:
    parts = ['"']
    for char in value:
        escape = _SHORT_ESCAPES.get(char)
        if escape is not None:
            parts.append(escape)
        elif char < "\u0020":
            parts.append("\\u%04x" % ord(char))
        else:
            parts.append(char)
    parts.append('"')
    return "".join(parts)


def _utf16_sort_key(key: str) -> bytes:
    try:
        return key.encode("utf-16-be")
    except UnicodeEncodeError as error:
        raise CanonicalizationError(
            "object key %r cannot be encoded to UTF-16 (lone surrogate)" % key
        ) from error


def _write(value: Any, out: List[str], depth: int) -> None:
    if depth > MAX_CANONICAL_DEPTH:
        raise CanonicalizationError("value nesting exceeds %d levels" % MAX_CANONICAL_DEPTH)
    if value is None:
        out.append("null")
    elif value is True:
        out.append("true")
    elif value is False:
        out.append("false")
    elif isinstance(value, str):
        out.append(_canonical_string(value))
    elif isinstance(value, bool):  # unreachable; kept for clarity of ordering
        raise CanonicalizationError("boolean handling is exhaustive above")
    elif isinstance(value, int):
        out.append(str(value))
    elif isinstance(value, float):
        raise CanonicalizationError(
            "floating-point values are outside the canonical subset; "
            "encode numbers as integers or strings"
        )
    elif isinstance(value, (list, tuple)):
        out.append("[")
        for index, item in enumerate(value):
            if index:
                out.append(",")
            _write(item, out, depth + 1)
        out.append("]")
    elif isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                raise CanonicalizationError(
                    "object keys must be strings in the canonical subset (found %r)" % (key,)
                )
        out.append("{")
        for index, key in enumerate(sorted(value, key=_utf16_sort_key)):
            if index:
                out.append(",")
            out.append(_canonical_string(key))
            out.append(":")
            _write(value[key], out, depth + 1)
        out.append("}")
    else:
        raise CanonicalizationError(
            "value of type %s is outside the canonical subset" % type(value).__name__
        )


def canonical_json_text(value: Any) -> str:
    """Return the deterministic canonical JSON text of a supported value."""
    parts: List[str] = []
    _write(value, parts, 0)
    return "".join(parts)


def canonical_json_bytes(value: Any) -> bytes:
    """Return the deterministic canonical JSON bytes (UTF-8) of a value."""
    text = canonical_json_text(value)
    try:
        return text.encode("utf-8")
    except UnicodeEncodeError as error:
        raise CanonicalizationError(
            "value contains text that cannot be encoded as UTF-8 (lone surrogate)"
        ) from error
