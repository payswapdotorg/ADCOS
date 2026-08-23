"""Signature-input material for the ADCOS envelope.

WORK-003 represents signature METADATA only and provides deterministic
canonical input bytes suitable for later signing. It does not implement
signing, verification, key management, credentials, rotation,
revocation, or trust policy — those belong to WORK-004 and later
security Work Items. No cryptographic algorithm is hard-coded
(LOCK-015); algorithm/profile identifiers ride as opaque or
registry-backed metadata in the signature field.

The signing basis defined here (provisional until the production
signature profile is frozen by later conformance/security work) is the
canonical JSON serialization of the envelope with the ``signature``
member removed. Two conformant implementations therefore derive
byte-identical signature-input material from the same logical envelope.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from .canonicalization import canonical_json_bytes
from .envelope import Envelope, EnvelopeError


def signature_input_bytes(envelope: Envelope) -> bytes:
    """Deterministic canonical signature-input bytes for an envelope.

    The bytes are the canonical JSON form of the envelope with the
    ``signature`` member omitted (all other members — including unknown
    preserved members — are covered).
    """
    document = envelope.to_dict()
    document.pop("signature", None)
    return canonical_json_bytes(document)


def signature_metadata(envelope: Envelope) -> Optional[Mapping[str, Any]]:
    """Return the structured signature metadata, if the signature is
    structured; None for opaque string signatures."""
    signature = envelope.signature
    if isinstance(signature, Mapping):
        return dict(signature)
    return None


def validate_signature_metadata(metadata: object) -> None:
    """Validate the shape of structured signature metadata (fail-safely)."""
    if not isinstance(metadata, Mapping):
        raise EnvelopeError("signature", "structured signature metadata must be an object")
    algorithm = metadata.get("algorithm")
    if not isinstance(algorithm, str) or not algorithm:
        raise EnvelopeError("signature", "structured signature requires a non-empty algorithm identifier")
    value = metadata.get("value")
    if not isinstance(value, str) or not value:
        raise EnvelopeError("signature", "structured signature requires non-empty value material")
