"""ADCOS identity package — WORK-004: cryptographic node identity and credential abstraction.

Implements durable, access-independent node identity and the credential
abstraction (references, lifecycle, rotation, revocation, algorithm
agility) defined by spec/architecture.md section 6.2, section 22, and
the machine-readable identity-profile registry under spec/schemas/.

Boundary summary (frozen):

- NodeID is derived ONLY from the stable identity-role public key and
  the identity profile — never from rotating operational keys, never
  from SIM/IMSI, modem identifiers, MAC addresses, IP addresses, access
  technology, cell/bearer identities, vendor accounts, or trust state.
- Operational key rotation and revocation never change NodeID.
- Secret material lives ONLY behind the CredentialStore interface; all
  public types (NodeID, credential references, public metadata) are
  structurally incapable of carrying secret bytes.
- Algorithms and profiles are explicit, registry-backed metadata;
  cryptographic providers are replaceable and the core never branches
  on a specific algorithm (LOCK-015).
- Trust/authorization policy is NOT decided here; possessing a valid
  identity is not trust (LOCK-022).

No trust policy, federation policy, discovery, topology, sessions, or
access-adapter behavior is implemented in this package.
"""

from __future__ import annotations

from .credentials import CredentialRecord, CredentialReference, KeyRole, PublicCredentialView
from .lifecycle import LifecycleError, LifecycleState, can_transition, transition
from .model import IdentityError, IdentityService, NodeIdentity, PublicIdentityMetadata
from .node_id import NodeID, NodeIdError, derive_node_id, parse_node_id
from .profiles import (
    IdentityProfile,
    ProfileError,
    ProfileSet,
    classify_profile_id,
    negotiate_profile,
)
from .provider import DevHmacSha256Provider, SignatureProvider
from .revocation import RevocationInfo
from .serialization import (
    SerializationError,
    public_metadata_from_bytes,
    public_metadata_from_mapping,
    public_metadata_to_bytes,
    public_metadata_to_dict,
)
from .store import (
    CredentialStore,
    DuplicateCredentialError,
    InMemoryCredentialStore,
    SecretMaterialError,
)

__all__ = [
    "CredentialRecord",
    "IdentityError",
    "CredentialReference",
    "CredentialStore",
    "DuplicateCredentialError",
    "DevHmacSha256Provider",
    "IdentityProfile",
    "IdentityService",
    "InMemoryCredentialStore",
    "KeyRole",
    "LifecycleError",
    "LifecycleState",
    "NodeID",
    "NodeIdError",
    "NodeIdentity",
    "ProfileError",
    "ProfileSet",
    "PublicCredentialView",
    "PublicIdentityMetadata",
    "RevocationInfo",
    "SerializationError",
    "SecretMaterialError",
    "SignatureProvider",
    "can_transition",
    "classify_profile_id",
    "derive_node_id",
    "negotiate_profile",
    "parse_node_id",
    "public_metadata_from_bytes",
    "public_metadata_from_mapping",
    "public_metadata_to_bytes",
    "public_metadata_to_dict",
    "transition",
]
