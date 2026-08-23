"""JSON debug codec — the required human/debug encoding.

Encoding is the deterministic canonical JSON form (see
``protocol.canonicalization``); decoding rejects duplicate object keys,
non-object roots, invalid UTF-8, and inputs beyond the configured size
limit — all fail-safely as CodecError / EnvelopeError, never as a crash
or a silently altered envelope.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Tuple

from .canonicalization import canonical_json_bytes
from .codec import CodecError, WireCodec
from .envelope import Envelope, EnvelopeError, envelope_from_mapping

DEFAULT_MAX_INPUT_BYTES = 1 << 20  # 1 MiB


def _reject_duplicate_keys(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CodecError("duplicate object key %r in JSON input" % key)
        result[key] = value
    return result


class JsonDebugCodec(WireCodec):
    """Deterministic canonical-JSON debug codec (status: normative)."""

    name = "json-debug"

    def __init__(self, max_input_bytes: int = DEFAULT_MAX_INPUT_BYTES) -> None:
        if max_input_bytes <= 0:
            raise ValueError("max_input_bytes must be positive")
        self.max_input_bytes = max_input_bytes

    def encode(self, envelope: Envelope) -> bytes:
        return canonical_json_bytes(envelope.to_dict())

    def decode(self, data: bytes) -> Envelope:
        if not isinstance(data, (bytes, bytearray)):
            raise CodecError("JSON codec input must be bytes")
        if len(data) > self.max_input_bytes:
            raise CodecError(
                "input of %d bytes exceeds the maximum of %d" % (len(data), self.max_input_bytes)
            )
        try:
            text = bytes(data).decode("utf-8")
        except UnicodeDecodeError as error:
            raise CodecError("input is not valid UTF-8: %s" % error) from error
        try:
            value = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
        except json.JSONDecodeError as error:
            raise CodecError("input is not valid JSON: %s" % error) from error
        try:
            return envelope_from_mapping(value)
        except EnvelopeError as error:
            raise error
