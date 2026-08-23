"""Signature provider abstraction (WORK-004 section 9).

Providers are replaceable cryptographic backends. The identity core
NEVER branches on a specific algorithm: it compares the algorithms a
provider declares against the algorithms a profile declares — both are
data. Provider implementations resolve secret material exclusively
through the CredentialStore (so HSM/TPM-backed providers can keep
material behind their own boundary).

``DevHmacSha256Provider`` implements the development/test algorithm
``alg.hmac-sha256.dev`` with HMAC-SHA256 (a standard primitive) so the
full identity lifecycle is deterministic and offline. It is a test and
development backend only — real deployments use asymmetric providers
(Ed25519, ECDSA P-256, ...) for the corresponding registered profiles.
"""

from __future__ import annotations

import hashlib
import hmac
from abc import ABC, abstractmethod
from typing import FrozenSet

from .credentials import CredentialReference
from .store import CredentialStore

DEV_ALGORITHM = "alg.hmac-sha256.dev"


class SignatureProvider(ABC):
    """A replaceable cryptographic signing/verification backend."""

    @abstractmethod
    def supported_algorithms(self) -> FrozenSet[str]:
        """Algorithm identifiers this provider implements."""

    @abstractmethod
    def public_material(self, secret: bytes) -> bytes:
        """Derive the publishable public material for a secret key.

        For asymmetric providers this is the public key; for the HMAC
        development provider it is a SHA-256 key fingerprint (safe to
        publish; verification still requires store-held material).
        """

    @abstractmethod
    def sign(self, store: CredentialStore, reference: CredentialReference, data: bytes) -> bytes:
        """Sign ``data`` with the credential addressed by ``reference``.

        The provider resolves secret material through the store (its own
        backend for HSM-style providers).
        """

    @abstractmethod
    def verify(
        self,
        public_material: bytes,
        algorithm: str,
        data: bytes,
        signature: bytes,
    ) -> bool:
        """Verify a signature against public material.

        For asymmetric algorithms this is external public verification.
        For the symmetric development algorithm, verification requires
        store-held material and is performed via
        ``verify_with_credential``; this method still validates shape and
        fails closed for the dev algorithm (it cannot verify externally
        with public material alone — a documented dev limitation).
        """

    def verify_with_credential(
        self,
        store: CredentialStore,
        reference: CredentialReference,
        data: bytes,
        signature: bytes,
    ) -> bool:
        """Verify a signature using store-held material for a reference.

        Default implementation: sign again and constant-time compare.
        """
        try:
            expected = self.sign(store, reference, data)
        except Exception:
            return False
        return hmac.compare_digest(expected, signature)


class DevHmacSha256Provider(SignatureProvider):
    """Deterministic development/test provider (HMAC-SHA256).

    DEVELOPMENT/TEST ONLY: HMAC is symmetric, so 'public material' is a
    key fingerprint and external public verification is not possible.
    The registered profile identity.sha256-hmac-dev.v1 documents the
    same limitation. Real deployments use asymmetric providers.
    """

    def supported_algorithms(self) -> FrozenSet[str]:
        return frozenset({DEV_ALGORITHM})

    def public_material(self, secret: bytes) -> bytes:
        if not isinstance(secret, (bytes, bytearray)) or not secret:
            raise ValueError("secret material must be non-empty bytes")
        return hashlib.sha256(bytes(secret)).digest()

    def sign(self, store: CredentialStore, reference: CredentialReference, data: bytes) -> bytes:
        secret = store.get_secret(reference)
        return hmac.new(secret, data, hashlib.sha256).digest()

    def verify(
        self,
        public_material: bytes,
        algorithm: str,
        data: bytes,
        signature: bytes,
    ) -> bool:
        # Symmetric: external verification with public material alone is
        # impossible for the dev algorithm — fail closed rather than
        # pretending the fingerprint can verify.
        raise NotImplementedError(
            "external public verification is not available for the symmetric "
            "development algorithm %r; use verify_with_credential" % DEV_ALGORITHM
        )
