"""Credential references and records (WORK-004 sections 4, 8).

A CredentialReference is an OPAQUE reference that lets later components
identify/select credential material without revealing it. Secret bytes
live only behind the CredentialStore (identity.store).

A CredentialRecord carries only public metadata: reference, NodeID
association, role, algorithm/profile identifier, key version (generation),
lifecycle status, timestamps, public material (a public key or a key
fingerprint — never secret material), and optional revocation info.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .lifecycle import LifecycleState
from .node_id import NodeID
from .revocation import RevocationInfo

#: Key roles seeded by the identity-profile registry. The identity role is
#: the STABLE key backing NodeID derivation and rotation authorization;
#: the operational role rotates freely.
class KeyRole:
    IDENTITY = "identity"
    OPERATIONAL = "operational"


@dataclass(frozen=True)
class CredentialReference:
    """Opaque, deterministic, non-secret credential reference."""

    reference_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.reference_id, str) or not self.reference_id:
            raise ValueError("credential reference id must be a non-empty string")
        if len(self.reference_id) > 256:
            raise ValueError("credential reference id too long (max 256 characters)")
        if any(char in self.reference_id for char in "\r\n\x00"):
            raise ValueError("credential reference id contains forbidden characters")

    def __str__(self) -> str:
        return self.reference_id

    def __repr__(self) -> str:
        return "CredentialReference(%r)" % self.reference_id


@dataclass
class CredentialRecord:
    """Public metadata for one credential generation. No secret material."""

    reference: CredentialReference
    node_id: NodeID
    profile_id: str
    role: str
    algorithm: str
    key_version: int
    public_material_hex: str
    status: LifecycleState
    provisioned_at: str
    activated_at: Optional[str] = None
    expires_at: Optional[str] = None
    superseded_at: Optional[str] = None
    revoked: Optional[RevocationInfo] = None
    provenance: str = "local"

    def __post_init__(self) -> None:
        if isinstance(self.key_version, bool) or not isinstance(self.key_version, int):
            raise ValueError("key_version must be an integer")
        if self.key_version < 1:
            raise ValueError("key_version must be >= 1")
        if not isinstance(self.public_material_hex, str) or len(self.public_material_hex) % 2 != 0:
            raise ValueError("public_material_hex must be a hex string")
        try:
            bytes.fromhex(self.public_material_hex)
        except ValueError as error:
            raise ValueError("public_material_hex is not valid hex") from error
        if self.provenance not in ("local", "external", "imported"):
            raise ValueError("provenance must be local|external|imported")

    @property
    def public_material(self) -> bytes:
        return bytes.fromhex(self.public_material_hex)

    def to_public_view(self) -> "PublicCredentialView":
        return PublicCredentialView(
            reference_id=self.reference.reference_id,
            role=self.role,
            algorithm=self.algorithm,
            key_version=self.key_version,
            status=self.status.value,
            public_material_hex=self.public_material_hex,
            provisioned_at=self.provisioned_at,
            activated_at=self.activated_at,
            expires_at=self.expires_at,
            revoked=(self.revoked.to_dict() if self.revoked is not None else None),
        )

    def __repr__(self) -> str:
        # Only public metadata; structurally secret-free.
        return (
            "CredentialReference=%r role=%r algorithm=%r version=%d status=%s"
            % (self.reference.reference_id, self.role, self.algorithm, self.key_version, self.status.value)
        )


@dataclass(frozen=True)
class PublicCredentialView:
    """Serializable public view of a credential record (no secrets)."""

    reference_id: str
    role: str
    algorithm: str
    key_version: int
    status: str
    public_material_hex: str
    provisioned_at: str
    activated_at: Optional[str]
    expires_at: Optional[str]
    revoked: Optional[dict]

    def to_dict(self) -> dict:
        return {
            "reference_id": self.reference_id,
            "role": self.role,
            "algorithm": self.algorithm,
            "key_version": self.key_version,
            "status": self.status,
            "public_material": self.public_material_hex,
            "provisioned_at": self.provisioned_at,
            "activated_at": self.activated_at,
            "expires_at": self.expires_at,
            "revoked": dict(self.revoked) if self.revoked else None,
        }
