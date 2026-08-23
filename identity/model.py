"""Node identity model and the identity service (WORK-004).

``NodeIdentity`` is the durable, access-independent identity descriptor:
NodeID (derived from the STABLE identity-role public key and the
profile), the profile, and creation time. Rotating operational keys,
revoking credentials, and changing access adapters never touch it.

``IdentityService`` composes a CredentialStore, a SignatureProvider, and
a ProfileSet to implement the credential lifecycle: provisioning,
activation, ATOMIC rotation authorized by the identity key, revocation,
expiry, and explicit identity destruction. All time-dependent behavior
takes an injected ``now`` (RFC 3339 UTC string) so everything is
deterministic. No trust/authorization decision is made here.

Rotation authorization: the identity-role credential signs the canonical
JSON statement {node_id, role, from_generation, to_generation,
new_public_material_hex, rotated_at} (canonicalized by the accepted
WORK-003 serialization). A rotation with an invalid authorization leaves
all state unchanged — no half-rotated identity.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, List, Optional, Tuple

from protocol.canonicalization import canonical_json_bytes
from protocol.temporal import parse_instant

from .credentials import CredentialRecord, CredentialReference, KeyRole, PublicCredentialView
from .lifecycle import LifecycleError, LifecycleState, transition
from .node_id import NodeID, NodeIdError, derive_node_id
from .profiles import IdentityProfile, ProfileError, ProfileSet
from .provider import SignatureProvider
from .revocation import RevocationInfo
from .store import CredentialStore, DuplicateCredentialError, StoreBatch


class IdentityError(ValueError):
    """Raised when an identity operation fails (fail closed)."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__("%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class NodeIdentity:
    """Durable, access-independent node identity descriptor."""

    node_id: NodeID
    profile_id: str
    created_at: str

    @classmethod
    def create(
        cls,
        profile: IdentityProfile,
        identity_public_key: bytes,
        created_at: str,
    ) -> "NodeIdentity":
        if profile.status != "active":
            raise ProfileError(
                "profile", "profile %r has status %r; only active profiles can create identities"
                % (profile.profile_id, profile.status),
            )
        node_id = derive_node_id(
            profile_id=profile.profile_id,
            identity_public_key=identity_public_key,
            derivation_rule=profile.derivation,
            domain_separation=profile.domain_separation,
        )
        parse_instant(created_at)  # validate deterministically
        return cls(node_id=node_id, profile_id=profile.profile_id, created_at=created_at)

    def __repr__(self) -> str:
        return "NodeIdentity(node_id=%r, profile_id=%r)" % (self.node_id.text, self.profile_id)


@dataclass(frozen=True)
class PublicIdentityMetadata:
    """Serializable public identity metadata. Structurally secret-free."""

    node_id: str
    profile_id: str
    created_at: str
    destroyed: bool
    credentials: Tuple[PublicCredentialView, ...]

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "profile_id": self.profile_id,
            "created_at": self.created_at,
            "destroyed": self.destroyed,
            "credentials": [view.to_dict() for view in self.credentials],
        }


def _require_active(
    records: List[CredentialRecord], node_id: NodeID, role: str, now: str
) -> CredentialRecord:
    """Find the single ACTIVE, non-expired credential for (node, role)."""
    now_instant = parse_instant(now)
    matches = [
        record
        for record in records
        if record.node_id == node_id
        and record.role == role
        and record.status is LifecycleState.ACTIVE
    ]
    expired: List[CredentialRecord] = []
    for record in matches:
        if record.expires_at is not None and parse_instant(record.expires_at) <= now_instant:
            expired.append(record)
    if expired:
        raise IdentityError(
            "expired",
            "active credential %s expired at %s (now=%s); expiry and revocation are distinct states"
            % (record.reference.reference_id, record.expires_at, now),
        )
    if not matches:
        raise IdentityError(
            "no-active-credential",
            "no active %s credential for %s" % (role, node_id.text),
        )
    if len(matches) > 1:
        raise IdentityError(
            "ambiguous",
            "multiple active %s credentials for %s: %s"
            % (role, node_id.text, sorted(r.reference.reference_id for r in matches)),
        )
    return matches[0]


class IdentityService:
    """Credential lifecycle operations over a store + provider + profiles."""

    def __init__(
        self,
        store: CredentialStore,
        provider: SignatureProvider,
        profiles: Optional[ProfileSet] = None,
    ) -> None:
        self._store = store
        self._provider = provider
        self._profiles = profiles or ProfileSet.load_default()
        self._destroyed: Dict[str, bool] = {}

    # ------------------------------------------------------------------
    # Provisioning / activation
    # ------------------------------------------------------------------

    def provision(
        self,
        identity: NodeIdentity,
        role: str,
        secret: bytes,
        *,
        now: str,
        expires_at: Optional[str] = None,
        provenance: str = "local",
    ) -> CredentialReference:
        """Provision a new credential generation with secret material.

        The secret goes ONLY to the store; the record carries public
        material (public key / fingerprint derived by the provider).
        """
        if self._destroyed.get(identity.node_id.text):
            raise IdentityError("destroyed", "identity %s is destroyed" % identity.node_id.text)
        profile = self._profiles.get(identity.profile_id)
        if not profile.supports_role(role):
            raise IdentityError(
                "role", "profile %r does not declare key role %r" % (profile.profile_id, role)
            )
        supported = self._provider.supported_algorithms() & set(profile.signing_algorithms)
        if not supported:
            raise IdentityError(
                "algorithm",
                "provider implements %s but profile %r declares %s"
                % (
                    sorted(self._provider.supported_algorithms()),
                    profile.profile_id,
                    sorted(profile.signing_algorithms),
                ),
            )
        algorithm = sorted(supported)[0]  # deterministic selection
        existing = [
            record
            for record in self._store.list_records()
            if record.node_id == identity.node_id and record.role == role
        ]
        if any(record.status is LifecycleState.ACTIVE for record in existing):
            raise IdentityError(
                "duplicate-active",
                "an active %s credential already exists for %s; use rotate()"
                % (role, identity.node_id.text),
            )
        generation = max((record.key_version for record in existing), default=0) + 1
        reference = CredentialReference(
            reference_id="cred:%s:%s:v%d" % (identity.node_id.text, role, generation)
        )
        public_material = self._provider.public_material(secret)
        record = CredentialRecord(
            reference=reference,
            node_id=identity.node_id,
            profile_id=profile.profile_id,
            role=role,
            algorithm=algorithm,
            key_version=generation,
            public_material_hex=public_material.hex(),
            status=LifecycleState.PROVISIONED,
            provisioned_at=now,
            expires_at=expires_at,
            provenance=provenance,
        )
        try:
            self._store.put_record(record)
            self._store.put_secret(reference, secret)
        except (DuplicateCredentialError, KeyError) as error:
            raise IdentityError("duplicate", str(error)) from error
        return reference

    def activate(self, reference: CredentialReference, *, now: str) -> CredentialRecord:
        """PROVISIONED -> ACTIVE, failing closed for expired/revoked."""
        record = self._store.get_record(reference)
        if record.status is LifecycleState.REVOKED:
            raise IdentityError(
                "revoked", "credential %s is revoked; activation fails closed" % reference.reference_id
            )
        if record.expires_at is not None and parse_instant(record.expires_at) <= parse_instant(now):
            raise IdentityError(
                "expired", "credential %s expired at %s; activation fails closed"
                % (reference.reference_id, record.expires_at),
            )
        record = replace(
            transition_record(self._store, reference, LifecycleState.ACTIVE),
            activated_at=now,
        )
        self._store.update_record(record)
        return record

    # ------------------------------------------------------------------
    # Rotation (atomic, identity-key authorized)
    # ------------------------------------------------------------------

    def rotation_statement(
        self,
        node_id: NodeID,
        role: str,
        from_generation: int,
        to_generation: int,
        new_public_material: bytes,
        rotated_at: str,
    ) -> bytes:
        """Canonical rotation statement bytes (WORK-003 canonicalization)."""
        return canonical_json_bytes(
            {
                "from_generation": from_generation,
                "new_public_material": new_public_material.hex(),
                "node_id": node_id.text,
                "role": role,
                "rotated_at": rotated_at,
                "to_generation": to_generation,
            }
        )

    def rotate(
        self,
        identity_credential: CredentialReference,
        *,
        node_id: NodeID,
        role: str,
        new_secret: bytes,
        authorization: bytes,
        rotated_at: str,
    ) -> CredentialRecord:
        """Atomically rotate a role's credential.

        1. Verify the authorization signature (identity-role credential)
           over the canonical rotation statement.
        2. Build the next-generation record and validate every lifecycle
           transition IN MEMORY.
        3. Commit: store the new secret and record, supersede the old
           generation, activate the new one.

        Any failure raises IdentityError BEFORE any persisted state
        changes — the previous valid credential remains active (no
        half-rotated identity).
        """
        if self._destroyed.get(node_id.text):
            raise IdentityError("destroyed", "identity %s is destroyed" % node_id.text)
        identity_record = self._store.get_record(identity_credential)
        if identity_record.node_id != node_id or identity_record.role != KeyRole.IDENTITY:
            raise IdentityError(
                "authorization",
                "rotation authorization must come from an identity-role credential of %s"
                % node_id.text,
            )
        if identity_record.status is not LifecycleState.ACTIVE:
            raise IdentityError(
                "authorization",
                "identity credential %s is %s; authorization fails closed"
                % (identity_credential.reference_id, identity_record.status.value),
            )
        if identity_record.expires_at is not None and parse_instant(
            identity_record.expires_at
        ) <= parse_instant(rotated_at):
            raise IdentityError(
                "authorization",
                "identity credential %s expired at %s (rotation time %s); "
                "authorization fails closed"
                % (identity_credential.reference_id, identity_record.expires_at, rotated_at),
            )
        # The CURRENT role credential must be ACTIVE and unexpired at the
        # actual rotation instant — never at a synthetic epoch timestamp.
        current = self._require_role_credential(node_id, role, now=rotated_at)
        profile = self._profiles.get(node_id.profile_id)
        if not profile.supports_role(role):
            raise IdentityError(
                "role", "profile %r does not declare key role %r" % (profile.profile_id, role)
            )
        supported = self._provider.supported_algorithms() & set(profile.signing_algorithms)
        if not supported:
            raise IdentityError(
                "algorithm",
                "provider implements %s but profile %r declares %s"
                % (
                    sorted(self._provider.supported_algorithms()),
                    profile.profile_id,
                    sorted(profile.signing_algorithms),
                ),
            )
        algorithm = sorted(supported)[0]
        new_public = self._provider.public_material(new_secret)
        from_generation = current.key_version
        to_generation = from_generation + 1
        statement = self.rotation_statement(
            node_id, role, from_generation, to_generation, new_public, rotated_at
        )
        if not self._provider.verify_with_credential(
            self._store, identity_credential, statement, authorization
        ):
            raise IdentityError(
                "authorization",
                "rotation authorization signature is invalid for %s role=%s from_generation=%d"
                % (node_id.text, role, from_generation),
            )
        new_reference = CredentialReference(
            reference_id="cred:%s:%s:v%d" % (node_id.text, role, to_generation)
        )
        new_record = CredentialRecord(
            reference=new_reference,
            node_id=node_id,
            profile_id=profile.profile_id,
            role=role,
            algorithm=algorithm,
            key_version=to_generation,
            public_material_hex=new_public.hex(),
            status=LifecycleState.PROVISIONED,
            provisioned_at=rotated_at,
        )
        # Validate every transition in memory before any persisted change.
        transition(current.status, LifecycleState.ROTATING)
        transition(LifecycleState.ROTATING, LifecycleState.SUPERSEDED)
        transition(new_record.status, LifecycleState.ACTIVE)
        # Build the FINAL states of every affected record, then commit the
        # whole rotation as ONE atomic store transaction: any failure at
        # the storage boundary leaves the pre-rotation state untouched
        # (old credential still ACTIVE, no new record, no new secret).
        superseded_final = replace(
            current,
            status=LifecycleState.SUPERSEDED,
            superseded_at=rotated_at,
        )
        activated_final = replace(
            new_record,
            status=LifecycleState.ACTIVE,
            activated_at=rotated_at,
        )
        self._store.commit_batch(
            StoreBatch(
                records_to_add=(new_record,),
                secrets_to_add=((new_reference, new_secret),),
                records_to_update=(superseded_final, activated_final),
            )
        )
        return activated_final

    # ------------------------------------------------------------------
    # Revocation / expiry / destruction
    # ------------------------------------------------------------------

    def revoke(
        self, reference: CredentialReference, *, reason: str, now: str
    ) -> CredentialRecord:
        """Revoke a credential (distinct from expiry). Identity survives."""
        record = replace(
            transition_record(self._store, reference, LifecycleState.REVOKED),
            revoked=RevocationInfo(revoked_at=now, reason=reason),
        )
        self._store.update_record(record)
        return record

    def expire(self, reference: CredentialReference, *, now: str) -> CredentialRecord:
        """Mark a credential expired (time-based, distinct from revocation)."""
        record = transition_record(self._store, reference, LifecycleState.EXPIRED)
        self._store.update_record(record)
        return record

    def destroy_identity(self, node_id: NodeID, *, now: str, reason: str) -> List[CredentialReference]:
        """EXPLICIT identity-destruction semantics: revoke every non-terminal
        credential and mark the identity destroyed. NodeID and records
        remain queryable (historical reference); no new credentials may
        be provisioned or rotated. This is the only operation that ends
        an identity's operability, and it is never implicit."""
        targets = [
            record
            for record in self._store.list_records()
            if record.node_id == node_id and not record.status.terminal
        ]
        batch = StoreBatch(
            records_to_update=tuple(
                replace(
                    record,
                    status=LifecycleState.REVOKED,
                    revoked=RevocationInfo(revoked_at=now, reason=reason),
                )
                for record in targets
            )
        )
        self._store.commit_batch(batch)  # all-or-nothing destruction
        self._destroyed[node_id.text] = True
        return [record.reference for record in targets]

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def active_credential(self, node_id: NodeID, role: str, *, now: str) -> CredentialRecord:
        return _require_active(self._store.list_records(), node_id, role, now)

    def records_for(self, node_id: NodeID) -> List[CredentialRecord]:
        return [r for r in self._store.list_records() if r.node_id == node_id]

    def public_metadata(self, identity: NodeIdentity) -> PublicIdentityMetadata:
        views = tuple(
            record.to_public_view()
            for record in self._store.list_records()
            if record.node_id == identity.node_id
        )
        return PublicIdentityMetadata(
            node_id=identity.node_id.text,
            profile_id=identity.profile_id,
            created_at=identity.created_at,
            destroyed=bool(self._destroyed.get(identity.node_id.text)),
            credentials=views,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_role_credential(
        self, node_id: NodeID, role: str, *, now: str
    ) -> CredentialRecord:
        """The ACTIVE, unexpired credential for (node, role) at ``now``.

        ``now`` is the actual operation instant (e.g. the rotation time) —
        never a synthetic epoch value, so an ACTIVE credential whose
        expires_at has passed cannot be used for or authorize a rotation.
        """
        try:
            return _require_active(self._store.list_records(), node_id, role, now=now)
        except IdentityError as error:
            if error.code == "expired":
                raise IdentityError(
                    "expired",
                    "current %s credential for %s is expired at %s; rotation fails closed"
                    % (role, node_id.text, now),
                ) from error
            raise IdentityError(
                "no-active-credential",
                "rotation requires an active %s credential for %s (%s)"
                % (role, node_id.text, error.detail),
            ) from error

def transition_record(
    store: CredentialStore, reference: CredentialReference, target: LifecycleState
) -> CredentialRecord:
    """Fetch a record, apply a fail-closed lifecycle transition, persist."""
    record = store.get_record(reference)
    try:
        new_status = transition(record.status, target)
    except LifecycleError as error:
        raise IdentityError(
            "lifecycle",
            "credential %s: %s" % (reference.reference_id, error),
        ) from error
    return replace(record, status=new_status)
