"""Credential store interface and a deterministic in-memory development store.

The store is the ONLY component that holds secret material. Provider
implementations (keystore, TPM, HSM, secure enclave, file-backed
development store, external secret manager) are replaceable behind the
CredentialStore interface — the core identity API never depends on one
provider (WORK-004 section 8).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from .credentials import CredentialRecord, CredentialReference
from .lifecycle import LifecycleState
from .revocation import RevocationInfo


class DuplicateCredentialError(ValueError):
    """Raised when a credential reference would be duplicated."""


class SecretMaterialError(RuntimeError):
    """Raised when secret material is requested for a record whose secret
    is absent or whose lifecycle forbids selection (fail closed)."""


class CredentialStore(ABC):
    """Abstract credential storage: records (public metadata) + secrets.

    Implementations may back this with an OS keystore, TPM, HSM, secure
    enclave, a file-backed development store, or an external secret
    manager. Secrets are addressed ONLY by credential reference.
    """

    @abstractmethod
    def put_record(self, record: CredentialRecord) -> None:
        """Store a credential record. Duplicate reference ids fail."""

    @abstractmethod
    def get_record(self, reference: CredentialReference) -> CredentialRecord:
        """Fetch a record by reference; unknown references fail."""

    @abstractmethod
    def list_records(self) -> List[CredentialRecord]:
        """All records, deterministic (reference-id sorted) order."""

    @abstractmethod
    def put_secret(self, reference: CredentialReference, secret: bytes) -> None:
        """Store secret material for a reference. Duplicate secrets fail."""

    @abstractmethod
    def get_secret(self, reference: CredentialReference) -> bytes:
        """Return the secret material for a reference (the only secret
        access path). Missing secrets fail closed."""

    @abstractmethod
    def update_record(self, record: CredentialRecord) -> None:
        """Persist a mutated record (lifecycle/revocation transitions)."""


class InMemoryCredentialStore(CredentialStore):
    """Deterministic in-memory development store (records + secrets).

    Suitable for tests and local development; NOT a secure production
    backend. Secrets never leave through anything but get_secret().
    """

    def __init__(self) -> None:
        self._records: Dict[str, CredentialRecord] = {}
        self._secrets: Dict[str, bytes] = {}

    def put_record(self, record: CredentialRecord) -> None:
        key = record.reference.reference_id
        if key in self._records:
            raise DuplicateCredentialError("credential reference %r already exists" % key)
        self._records[key] = record

    def get_record(self, reference: CredentialReference) -> CredentialRecord:
        try:
            return self._records[reference.reference_id]
        except KeyError:
            raise KeyError(
                "unknown credential reference %r" % reference.reference_id
            ) from None

    def list_records(self) -> List[CredentialRecord]:
        return [self._records[key] for key in sorted(self._records)]

    def put_secret(self, reference: CredentialReference, secret: bytes) -> None:
        if not isinstance(secret, (bytes, bytearray)) or not secret:
            raise SecretMaterialError("secret material must be non-empty bytes")
        key = reference.reference_id
        if key in self._secrets:
            raise DuplicateCredentialError("secret for %r already exists" % key)
        self._secrets[key] = bytes(secret)

    def get_secret(self, reference: CredentialReference) -> bytes:
        key = reference.reference_id
        if key not in self._secrets:
            raise SecretMaterialError("no secret material for reference %r" % key)
        record = self.get_record(reference)
        if record.status is LifecycleState.REVOKED:
            raise SecretMaterialError(
                "reference %r is revoked; secret selection fails closed" % key
            )
        return self._secrets[key]

    def update_record(self, record: CredentialRecord) -> None:
        key = record.reference.reference_id
        if key not in self._records:
            raise KeyError("unknown credential reference %r" % key)
        self._records[key] = record
