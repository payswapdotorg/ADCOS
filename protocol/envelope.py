"""The ADCOS stable protocol envelope model (spec/architecture.md section 7).

The envelope is an explicit stable abstraction, not an ad-hoc dictionary.
Known fields follow the frozen section 7 contract exactly; any additional
top-level member is an *unknown optional field* that must be preserved
verbatim for forward compatibility (architecture section 7 rules 2-3).
Unknown extension entries live in ``extensions`` and are likewise
preserved; a parser never lets an extension or unknown field shadow,
overwrite, or coerce a known envelope field.

``message_id`` is a message-instance identifier only — it is not coupled
to NodeID, access technology, radio bearer, transport connection, or
process identity (spec/prompts/WORK-003.md section 8).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple

PROTOCOL_IDENTIFIER = "adcos"

#: Known top-level envelope members (the frozen section 7 contract).
KNOWN_FIELDS: Tuple[str, ...] = (
    "protocol",
    "version",
    "message_type",
    "message_id",
    "sender",
    "issued_at",
    "expires_at",
    "correlation_id",
    "extensions",
    "payload",
    "evidence",
    "signature",
)

_ID_PATTERN = re.compile(r"^[^\u0000-\u001f]{1,256}$")
_TEMPORAL_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


class EnvelopeError(ValueError):
    """Raised when an envelope violates the structural contract.

    ``code`` is a stable machine-readable reason (e.g. ``message-id``);
    ``detail`` is the human-readable explanation.
    """

    def __init__(self, code: str, detail: str) -> None:
        super().__init__("%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


def _check_id_shape(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise EnvelopeError(name, "%s must be a string" % name)
    if _ID_PATTERN.fullmatch(value) is None:
        raise EnvelopeError(
            name,
            "%s must be 1..256 characters without control characters (found %r)" % (name, value),
        )
    return value


def _check_temporal_format(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise EnvelopeError(name, "%s must be a string" % name)
    if _TEMPORAL_PATTERN.fullmatch(value) is None:
        raise EnvelopeError(name, "%s must be RFC 3339 UTC with Z suffix (found %r)" % (name, value))
    return value


def _check_signature(value: object) -> object:
    if isinstance(value, str):
        if not value:
            raise EnvelopeError("signature", "signature string must be non-empty")
        return value
    if isinstance(value, dict):
        algorithm = value.get("algorithm")
        signature_value = value.get("value")
        if not isinstance(algorithm, str) or not algorithm:
            raise EnvelopeError("signature", "structured signature requires a non-empty algorithm identifier")
        if not isinstance(signature_value, str) or not signature_value:
            raise EnvelopeError("signature", "structured signature requires non-empty value material")
        return value
    raise EnvelopeError(
        "signature",
        "signature must be an opaque string or an object with algorithm and value",
    )


@dataclass(frozen=True)
class Envelope:
    """The stable ADCOS protocol envelope.

    Attributes mirror the frozen section 7 contract. ``extra`` holds
    unknown top-level members (preserved verbatim); ``correlation_id`` is
    the only optional known member and is omitted from serialization when
    None.
    """

    version: int
    message_type: str
    message_id: str
    sender: str
    issued_at: str
    expires_at: str
    extensions: Mapping[str, Any] = field(default_factory=dict)
    payload: Any = None
    evidence: Tuple[Any, ...] = ()
    signature: Any = ""
    correlation_id: Optional[str] = None
    extra: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.version, bool) or not isinstance(self.version, int):
            raise EnvelopeError("version", "version must be an integer")
        if self.version < 1:
            raise EnvelopeError("version", "version must be >= 1")
        if not isinstance(self.message_type, str) or not self.message_type:
            raise EnvelopeError("message-type", "message_type must be a non-empty string")
        _check_id_shape("message-id", self.message_id)
        if not isinstance(self.sender, str) or not self.sender:
            raise EnvelopeError("sender", "sender must be a non-empty string")
        _check_temporal_format("issued-at", self.issued_at)
        _check_temporal_format("expires-at", self.expires_at)
        if self.correlation_id is not None:
            _check_id_shape("correlation-id", self.correlation_id)
        if not isinstance(self.extensions, Mapping):
            raise EnvelopeError("extensions", "extensions must be an object")
        if not isinstance(self.evidence, (list, tuple)):
            raise EnvelopeError("evidence", "evidence must be an array")
        _check_signature(self.signature)
        if not isinstance(self.extra, Mapping):
            raise EnvelopeError("extra", "unknown top-level members must form an object")
        for key in self.extra:
            if key in KNOWN_FIELDS:
                raise EnvelopeError(
                    "extra",
                    "unknown top-level member %r collides with a known envelope field" % key,
                )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain mapping, preserving unknown members."""
        result: Dict[str, Any] = {
            "protocol": PROTOCOL_IDENTIFIER,
            "version": self.version,
            "message_type": self.message_type,
            "message_id": self.message_id,
            "sender": self.sender,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "extensions": dict(self.extensions),
            "payload": self.payload,
            "evidence": list(self.evidence),
            "signature": self.signature,
        }
        if self.correlation_id is not None:
            result["correlation_id"] = self.correlation_id
        result.update(dict(self.extra))
        return result


def envelope_from_mapping(data: object, message_type_grammar: Optional[re.Pattern] = None) -> Envelope:
    """Build an Envelope from a mapping, failing safely on contract violations.

    ``message_type_grammar`` defaults to the grammar declared in
    spec/schemas/protocol.json (single source of truth).
    """
    if not isinstance(data, Mapping):
        raise EnvelopeError("envelope", "envelope must be a JSON object at the top level")
    grammar = message_type_grammar
    if grammar is None:
        from .versioning import protocol_metadata

        grammar = protocol_metadata().message_type_grammar

    if data.get("protocol") != PROTOCOL_IDENTIFIER:
        raise EnvelopeError(
            "protocol",
            "protocol identifier must be %r (found %r)" % (PROTOCOL_IDENTIFIER, data.get("protocol")),
        )

    version = data.get("version")
    if isinstance(version, bool) or not isinstance(version, int):
        raise EnvelopeError("version", "version must be an integer (found %r)" % (version,))
    if version < 1:
        raise EnvelopeError("version", "version must be >= 1 (found %r)" % (version,))

    message_type = data.get("message_type")
    if not isinstance(message_type, str):
        raise EnvelopeError("message-type", "message_type must be a string")
    if grammar.fullmatch(message_type) is None:
        raise EnvelopeError(
            "message-type",
            "message_type %r does not match the registered grammar" % message_type,
        )

    if "message_id" not in data:
        raise EnvelopeError("message-id", "message_id is required")
    message_id = _check_id_shape("message-id", data["message_id"])

    if "sender" not in data:
        raise EnvelopeError("sender", "sender is required")
    sender = data["sender"]
    if not isinstance(sender, str) or not sender:
        raise EnvelopeError("sender", "sender must be a non-empty string")

    if "issued_at" not in data:
        raise EnvelopeError("issued-at", "issued_at is required")
    issued_at = _check_temporal_format("issued-at", data["issued_at"])

    if "expires_at" not in data:
        raise EnvelopeError("expires-at", "expires_at is required")
    expires_at = _check_temporal_format("expires-at", data["expires_at"])

    correlation_id = None
    if "correlation_id" in data and data["correlation_id"] is not None:
        correlation_id = _check_id_shape("correlation-id", data["correlation_id"])

    if "extensions" not in data:
        raise EnvelopeError("extensions", "extensions is required")
    extensions = data["extensions"]
    if not isinstance(extensions, Mapping):
        raise EnvelopeError("extensions", "extensions must be an object")

    if "payload" not in data:
        raise EnvelopeError("payload", "payload is required (may be any JSON value)")
    payload = data["payload"]

    if "evidence" not in data:
        raise EnvelopeError("evidence", "evidence is required (may be an empty array)")
    evidence = data["evidence"]
    if not isinstance(evidence, list):
        raise EnvelopeError("evidence", "evidence must be an array")

    if "signature" not in data:
        raise EnvelopeError("signature", "signature is required (opaque metadata)")
    signature = _check_signature(data["signature"])

    extra = {key: value for key, value in data.items() if key not in KNOWN_FIELDS}

    return Envelope(
        version=version,
        message_type=message_type,
        message_id=message_id,
        sender=sender,
        issued_at=issued_at,
        expires_at=expires_at,
        extensions=dict(extensions),
        payload=payload,
        evidence=tuple(evidence),
        signature=signature,
        correlation_id=correlation_id,
        extra=extra,
    )
