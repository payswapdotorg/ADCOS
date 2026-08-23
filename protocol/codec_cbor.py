"""Provisional compact codec — deterministic CBOR profile (RFC 8949 section 4.2).

STATUS: PROVISIONAL. This codec implements RFC 8949 *core deterministic
encoding* for the ADCOS supported value subset. It is NOT the frozen
production canonicalization profile: spec/architecture.md section 7
leaves the exact production canonicalization profile to later
conformance work before production wire compatibility is declared. A
mechanical guard exists in tools/schema_check.py (SCHEMA-07) ensuring
the codec's declared status in spec/schemas/protocol.json stays
"provisional".

Supported subset (bijective with the canonical JSON subset):

- unsigned and negative integers (major types 0/1) in SHORTEST FORM;
- UTF-8 text strings (major type 3) with definite, shortest-form lengths;
- definite-length arrays (major type 4) with shortest-form lengths;
- definite-length string-keyed maps (major type 5) with shortest-form
  lengths and keys sorted per RFC 8949 section 4.2.1: shorter encoded key
  first, then bytewise lexicographic order;
- false/true/null (major type 7, simple values 20/21/22).

The DECODER enforces the same deterministic profile the encoder emits:
non-minimal integer or length encodings (e.g. 0x18 0x01 for the integer
1, or a length < 24 encoded with additional-info 24) are rejected, so
encode(decode(bytes)) == bytes holds for every accepted input.

Explicitly rejected (fail safely, deterministically):

- byte strings (major type 2) — not representable in the canonical JSON
  subset;
- tags (major type 6) — no tag semantics are frozen;
- floating-point numbers (major type 7, additional info 25/26/27) —
  outside the canonical subset;
- NON-MINIMAL integer or length encodings — RFC 8949 section 4.2.1
  requires the shortest form; alternate byte representations of the
  same value would break determinism of golden vectors and signature
  input material;
- indefinite lengths (additional info 31) and break codes;
- trailing bytes after a complete top-level value;
- inputs exceeding the size limit or the nesting-depth limit.

The decoder is guarded against pathological inputs (depth and size
limits) so malformed data fails safely rather than crashing.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .codec import CodecError, WireCodec
from .envelope import Envelope, EnvelopeError, envelope_from_mapping

MAX_CBOR_DEPTH = 64
DEFAULT_MAX_INPUT_BYTES = 1 << 20  # 1 MiB

_UINT64_MAX = (1 << 64) - 1

# additional-info -> argument byte length
_ARGUMENT_LENGTHS = {24: 1, 25: 2, 26: 4, 27: 8}

# The smallest argument value that legitimately requires the given
# argument byte length (RFC 8949 section 4.2.1 shortest-form rule):
# values below these bounds must use a shorter form and are rejected as
# non-minimal when they appear in the longer form.
_MINIMAL_ARGUMENT_BOUNDS = {
    1: 24,           # 1-byte form starts at 24 (0-23 use direct info)
    2: 1 << 8,      # 2-byte form starts at 256
    4: 1 << 16,     # 4-byte form starts at 65536
    8: 1 << 32,     # 8-byte form starts at 2**32
}


def _head(major: int, argument: int) -> bytes:
    prefix = major << 5
    if argument < 24:
        return bytes([prefix | argument])
    if argument <= 0xFF:
        return bytes([prefix | 24, argument])
    if argument <= 0xFFFF:
        return bytes([prefix | 25]) + argument.to_bytes(2, "big")
    if argument <= 0xFFFFFFFF:
        return bytes([prefix | 26]) + argument.to_bytes(4, "big")
    if argument <= _UINT64_MAX:
        return bytes([prefix | 27]) + argument.to_bytes(8, "big")
    raise CodecError("integer %d is outside the CBOR 64-bit range" % argument)


def _encode_item(value: Any, depth: int) -> bytes:
    if depth > MAX_CBOR_DEPTH:
        raise CodecError("value nesting exceeds %d levels" % MAX_CBOR_DEPTH)
    if value is None:
        return b"\xf6"  # simple 22 (null)
    if value is True:
        return b"\xf5"  # simple 21 (true)
    if value is False:
        return b"\xf4"  # simple 20 (false)
    if isinstance(value, bool):  # unreachable; bool handled above
        raise CodecError("boolean handling is exhaustive above")
    if isinstance(value, int):
        if value >= 0:
            return _head(0, value)
        return _head(1, -1 - value)
    if isinstance(value, float):
        raise CodecError("floating-point values are outside the compact subset")
    if isinstance(value, str):
        try:
            encoded = value.encode("utf-8")
        except UnicodeEncodeError as error:
            raise CodecError("string cannot be encoded as UTF-8: %s" % error) from error
        return _head(3, len(encoded)) + encoded
    if isinstance(value, (list, tuple)):
        body = b"".join(_encode_item(item, depth + 1) for item in value)
        return _head(4, len(value)) + body
    if isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                raise CodecError("map keys must be strings in the compact subset (found %r)" % (key,))
        entries: List[Tuple[bytes, bytes]] = []
        for key, item in value.items():
            encoded_key = _encode_item(key, depth + 1)
            entries.append((encoded_key, _encode_item(item, depth + 1)))
        # RFC 8949 section 4.2.1: sort by encoded key length first, then bytewise.
        entries.sort(key=lambda pair: (len(pair[0]), pair[0]))
        body = b"".join(key_bytes + item_bytes for key_bytes, item_bytes in entries)
        return _head(5, len(entries)) + body
    raise CodecError("value of type %s is outside the compact subset" % type(value).__name__)


def _decode_item(data: bytes, offset: int, depth: int) -> Tuple[Any, int]:
    if depth > MAX_CBOR_DEPTH:
        raise CodecError("decoded nesting exceeds %d levels" % MAX_CBOR_DEPTH)
    if offset >= len(data):
        raise CodecError("truncated input at offset %d" % offset)
    initial = data[offset]
    major = initial >> 5
    info = initial & 0x1F
    offset += 1

    if info < 24:
        argument: int = info
    elif info in (24, 25, 26, 27):
        length = _ARGUMENT_LENGTHS[info]
        if offset + length > len(data):
            raise CodecError("truncated length field at offset %d" % (offset - 1))
        argument = int.from_bytes(data[offset : offset + length], "big")
        # Core deterministic encoding (RFC 8949 section 4.2.1): integers
        # and lengths MUST be encoded in the shortest available form. A
        # longer-than-necessary argument encoding is NOT part of the
        # deterministic profile and is rejected here, so every accepted
        # byte sequence uses the same representation the encoder emits
        # (decode-then-encode is the identity on accepted input).
        if argument < _MINIMAL_ARGUMENT_BOUNDS[length]:
            raise CodecError(
                "non-minimal argument encoding: value %d uses the %d-byte form "
                "but fits in a shorter form (RFC 8949 section 4.2.1 shortest-form "
                "requirement)" % (argument, length)
            )
        offset += length
    elif info == 31:
        raise CodecError("indefinite lengths are not permitted in the deterministic profile")
    else:
        raise CodecError("reserved additional-info value %d" % info)

    if major == 0:
        return argument, offset
    if major == 1:
        return -1 - argument, offset
    if major == 2:
        raise CodecError("byte strings are outside the compact subset")
    if major == 3:
        end = offset + argument
        if end > len(data):
            raise CodecError("truncated text string at offset %d" % offset)
        try:
            return data[offset:end].decode("utf-8"), end
        except UnicodeDecodeError as error:
            raise CodecError("invalid UTF-8 in text string: %s" % error) from error
    if major == 4:
        items: List[Any] = []
        for _ in range(argument):
            item, offset = _decode_item(data, offset, depth + 1)
            items.append(item)
        return items, offset
    if major == 5:
        mapping: Dict[str, Any] = {}
        previous_sort_key: Optional[Tuple[int, bytes]] = None
        for _ in range(argument):
            key, offset = _decode_item(data, offset, depth + 1)
            if not isinstance(key, str):
                raise CodecError("map keys must be text strings in the compact subset")
            if key in mapping:
                raise CodecError("duplicate map key %r" % key)
            try:
                encoded = key.encode("utf-8")
            except UnicodeEncodeError as error:
                raise CodecError("map key cannot be encoded as UTF-8: %s" % error) from error
            sort_key = (len(encoded), encoded)
            if previous_sort_key is not None and sort_key <= previous_sort_key:
                raise CodecError("map keys are not in canonical sorted order")
            previous_sort_key = sort_key
            value, offset = _decode_item(data, offset, depth + 1)
            mapping[key] = value
        return mapping, offset
    if major == 6:
        raise CodecError("tags are not permitted in the compact profile")
    if major == 7:
        if info == 20:
            return False, offset
        if info == 21:
            return True, offset
        if info == 22:
            return None, offset
        raise CodecError("simple value %d is outside the compact subset" % info)
    raise CodecError("unreachable major type %d" % major)


def cbor_bytes(value: Any) -> bytes:
    """Encode a supported value to deterministic compact bytes."""
    return _encode_item(value, 0)


def cbor_value(data: bytes, max_input_bytes: int = DEFAULT_MAX_INPUT_BYTES) -> Any:
    """Decode deterministic compact bytes to a supported value."""
    if not isinstance(data, (bytes, bytearray)):
        raise CodecError("compact codec input must be bytes")
    if len(data) > max_input_bytes:
        raise CodecError(
            "input of %d bytes exceeds the maximum of %d" % (len(data), max_input_bytes)
        )
    if len(data) == 0:
        raise CodecError("empty input")
    value, offset = _decode_item(bytes(data), 0, 0)
    if offset != len(data):
        raise CodecError("trailing bytes after the top-level value at offset %d" % offset)
    return value


class CompactDeterministicCborCodec(WireCodec):
    """Provisional deterministic-CBOR-profile envelope codec."""

    name = "compact-deterministic-cbor"

    def __init__(self, max_input_bytes: int = DEFAULT_MAX_INPUT_BYTES) -> None:
        if max_input_bytes <= 0:
            raise ValueError("max_input_bytes must be positive")
        self.max_input_bytes = max_input_bytes

    def encode(self, envelope: Envelope) -> bytes:
        return _encode_item(envelope.to_dict(), 0)

    def decode(self, data: bytes) -> Envelope:
        value = cbor_value(data, self.max_input_bytes)
        try:
            return envelope_from_mapping(value)
        except EnvelopeError as error:
            raise error
