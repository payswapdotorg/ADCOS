"""Public identity metadata serialization (WORK-004 section 12).

Consumes the accepted WORK-003 serialization boundary — no second
serialization system. Public metadata is canonicalized by
``protocol.canonicalization`` and can travel through the WORK-003
envelope (unknown message types are transported opaquely under the
explicit forward policy, per architecture section 7). Parsing rejects
duplicate JSON keys and every malformed field — fail closed.
"""

from __future__ import annotations

import json
from typing import Any, List, Optional, Tuple

from protocol.canonicalization import canonical_json_bytes

from .credentials import PublicCredentialView
from .lifecycle import LifecycleState
from .model import PublicIdentityMetadata
from .node_id import NodeIdError, parse_node_id
from .revocation import RevocationInfo


class SerializationError(ValueError):
    """Raised when serialized public metadata is malformed."""


def public_metadata_to_dict(metadata: PublicIdentityMetadata) -> dict:
    """Public metadata as a plain dict (structurally secret-free)."""
    return metadata.to_dict()


def public_metadata_to_bytes(metadata: PublicIdentityMetadata) -> bytes:
    """Canonical JSON bytes via the WORK-003 canonicalization."""
    return canonical_json_bytes(metadata.to_dict())


def _reject_duplicate_keys(pairs: List[Tuple[str, Any]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise SerializationError("duplicate object key %r in serialized identity metadata" % key)
        result[key] = value
    return result


def _require_str(data: dict, field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value:
        raise SerializationError("field %r must be a non-empty string" % field)
    return value


def public_metadata_from_mapping(data: object) -> PublicIdentityMetadata:
    """Parse/validate public identity metadata (fail closed)."""
    if not isinstance(data, dict):
        raise SerializationError("public identity metadata must be a JSON object")
    node_id_text = _require_str(data, "node_id")
    try:
        parse_node_id(node_id_text)
    except NodeIdError as error:
        raise SerializationError("node_id: %s" % error) from error
    profile_id = _require_str(data, "profile_id")
    created_at = _require_str(data, "created_at")
    destroyed = data.get("destroyed")
    if not isinstance(destroyed, bool):
        raise SerializationError("field 'destroyed' must be a boolean")
    credentials = data.get("credentials")
    if not isinstance(credentials, list):
        raise SerializationError("field 'credentials' must be an array")
    views: List[PublicCredentialView] = []
    for index, entry in enumerate(credentials):
        if not isinstance(entry, dict):
            raise SerializationError("credentials[%d] must be an object" % index)
        status = entry.get("status")
        if status not in {state.value for state in LifecycleState}:
            raise SerializationError("credentials[%d].status %r is not a lifecycle state" % (index, status))
        key_version = entry.get("key_version")
        if isinstance(key_version, bool) or not isinstance(key_version, int) or key_version < 1:
            raise SerializationError("credentials[%d].key_version must be a positive integer" % index)
        public_material = entry.get("public_material")
        if not isinstance(public_material, str) or len(public_material) % 2 != 0:
            raise SerializationError("credentials[%d].public_material must be a hex string" % index)
        try:
            bytes.fromhex(public_material)
        except ValueError as error:
            raise SerializationError(
                "credentials[%d].public_material is not valid hex" % index
            ) from error
        revoked = entry.get("revoked")
        if revoked is not None:
            try:
                RevocationInfo.from_dict(revoked)
            except ValueError as error:
                raise SerializationError("credentials[%d].revoked: %s" % (index, error)) from error
        for field in ("reference_id", "role", "algorithm"):
            if not isinstance(entry.get(field), str) or not entry.get(field):
                raise SerializationError("credentials[%d].%s must be a non-empty string" % (index, field))
        views.append(
            PublicCredentialView(
                reference_id=entry["reference_id"],
                role=entry["role"],
                algorithm=entry["algorithm"],
                key_version=key_version,
                status=status,
                public_material_hex=public_material,
                provisioned_at=_require_str(entry, "provisioned_at"),
                activated_at=entry.get("activated_at") if isinstance(entry.get("activated_at"), str) else None,
                expires_at=entry.get("expires_at") if isinstance(entry.get("expires_at"), str) else None,
                revoked=dict(revoked) if isinstance(revoked, dict) else None,
            )
        )
    return PublicIdentityMetadata(
        node_id=node_id_text,
        profile_id=profile_id,
        created_at=created_at,
        destroyed=destroyed,
        credentials=tuple(views),
    )


def public_metadata_from_bytes(data: bytes) -> PublicIdentityMetadata:
    """Parse canonical (or any valid) JSON bytes into public metadata."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SerializationError("serialized metadata is not valid UTF-8: %s" % error) from error
    try:
        value = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as error:
        raise SerializationError("serialized metadata is not valid JSON: %s" % error) from error
    return public_metadata_from_mapping(value)
