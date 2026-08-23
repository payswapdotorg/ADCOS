"""ADCOS protocol package — WORK-003: versioned protocol envelope and serialization.

This package implements the stable wire-message envelope and the
implementation-independent serialization/versioning primitives defined by
spec/architecture.md section 7 and spec/schemas/protocol.json.

Scope boundaries (frozen):

- No cryptographic identity, keys, or trust policy (WORK-004).
- No capability advertisement/negotiation runtime (WORK-005).
- No discovery, topology, routing, sessions, mobility, adapters, or any
  networking runtime.
- The compact codec is a PROVISIONAL deterministic-CBOR-profile
  implementation; it is not the frozen production canonicalization
  profile, which is declared only by later conformance work.

All modules are deterministic and use only the Python standard library.
"""

from __future__ import annotations

from .canonicalization import (
    CanonicalizationError,
    canonical_json_bytes,
    canonical_json_text,
)
from .codec import CodecError, WireCodec, get_codec, register_codec
from .codec_cbor import CompactDeterministicCborCodec, cbor_bytes
from .codec_json import JsonDebugCodec
from .envelope import Envelope, EnvelopeError, envelope_from_mapping
from .signature import signature_input_bytes
from .temporal import TemporalError, parse_instant
from .validation import (
    AcceptOutcome,
    ParsePolicy,
    ReplayDecision,
    UnknownTypePolicy,
    ValidatedEnvelope,
    accept,
    validate,
    validation_clock,
)
from .versioning import (
    Classification,
    ProtocolVersion,
    protocol_metadata,
)

__all__ = [
    "AcceptOutcome",
    "CanonicalizationError",
    "Classification",
    "CodecError",
    "CompactDeterministicCborCodec",
    "Envelope",
    "EnvelopeError",
    "JsonDebugCodec",
    "ParsePolicy",
    "ProtocolVersion",
    "ReplayDecision",
    "TemporalError",
    "UnknownTypePolicy",
    "ValidatedEnvelope",
    "WireCodec",
    "accept",
    "canonical_json_bytes",
    "canonical_json_text",
    "cbor_bytes",
    "envelope_from_mapping",
    "get_codec",
    "parse_instant",
    "protocol_metadata",
    "register_codec",
    "signature_input_bytes",
    "validate",
    "validation_clock",
]
