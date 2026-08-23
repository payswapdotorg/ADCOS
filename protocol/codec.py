"""Wire codec abstraction for the ADCOS envelope.

The logical envelope model is independent of concrete encodings
(spec/architecture.md section 7): JSON is the required human/debug
encoding and a compact deterministic codec is the provisional compact
candidate. New codecs register here without changing envelope semantics
(LOCK-015-style agility at the codec layer; no codec is hard-coded into
core semantics).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Type

from .envelope import Envelope


class CodecError(ValueError):
    """Raised when encoded input cannot be decoded into an envelope."""


class WireCodec(ABC):
    """A named envelope encoding. ``encode``/``decode`` are inverses on
    the supported value subset and both are deterministic."""

    name: str = ""

    @abstractmethod
    def encode(self, envelope: Envelope) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def decode(self, data: bytes) -> Envelope:
        raise NotImplementedError


_REGISTRY: Dict[str, WireCodec] = {}


def register_codec(codec: WireCodec) -> None:
    if not codec.name:
        raise CodecError("codec must declare a name")
    if codec.name in _REGISTRY and type(_REGISTRY[codec.name]) is not type(codec):
        raise CodecError("codec name %r is already registered" % codec.name)
    _REGISTRY[codec.name] = codec


def get_codec(name: str) -> WireCodec:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise CodecError("unknown codec %r (registered: %s)" % (name, sorted(_REGISTRY))) from None


def registered_codecs() -> Dict[str, WireCodec]:
    return dict(_REGISTRY)


def _install_default_codecs() -> None:
    from .codec_cbor import CompactDeterministicCborCodec
    from .codec_json import JsonDebugCodec

    for codec_type in (JsonDebugCodec, CompactDeterministicCborCodec):
        if codec_type.name not in _REGISTRY:
            register_codec(codec_type())


_install_default_codecs()
