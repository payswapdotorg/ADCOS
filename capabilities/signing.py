"""Capability statement signing through the WORK-004 provider seam.

The signature input is the WORK-003 canonical JSON of the statement's
security-critical content — every semantic field including provider
identity, capability id, schema version, validity interval, parameters,
constraints, evidence references, and withdrawal state — with the
signature member itself excluded. Mutable/non-semantic formatting is
never signed.

Signature = attributable statement, NOT truth. Verification proves the
statement came from the holder of the referenced credential at signing
time; it does not establish availability, authorization, or trust.
"""

from __future__ import annotations

from typing import Optional

from identity.credentials import CredentialReference
from identity.store import CredentialStore
from identity.provider import SignatureProvider
from identity.node_id import NodeID, parse_node_id
from protocol.canonicalization import CanonicalizationError, canonical_json_bytes

from .model import CapabilityError, CapabilityStatement


def _unsigned_view(statement: CapabilityStatement) -> dict:
    """The security-critical content that MUST be covered by the
    signature: every semantic member except the signature itself."""
    document = statement.to_dict()
    document.pop("signature", None)
    return document


def statement_signature_input(statement: CapabilityStatement) -> bytes:
    """Deterministic canonical signature-input bytes (WORK-003
    canonicalization; withdrawal state included when present)."""
    try:
        return canonical_json_bytes(_unsigned_view(statement))
    except CanonicalizationError as error:
        raise CapabilityError(
            "canonicalization", "statement is not canonically representable: %s" % error
        ) from error


def sign_statement(
    statement: CapabilityStatement,
    *,
    store: CredentialStore,
    provider: SignatureProvider,
    credential: CredentialReference,
) -> CapabilityStatement:
    """Return a signed copy of the statement (signature material opaque).

    Signing flows exclusively through the WORK-004 provider seam — no
    key material ever enters the capability layer.
    """
    signature_input = statement_signature_input(statement)
    try:
        signature_bytes = provider.sign(store, credential, signature_input)
    except Exception as error:
        raise CapabilityError(
            "signing",
            "provider signing failed: %s: %s" % (type(error).__name__, error),
        ) from error
    from dataclasses import replace

    return replace(statement, signature=signature_bytes.hex())


def verify_statement(
    statement: CapabilityStatement,
    *,
    store: CredentialStore,
    provider: SignatureProvider,
    credential: CredentialReference,
) -> bool:
    """Verify a statement's signature through the provider seam.

    Returns True ONLY when:
    1. the credential's WORK-004 record belongs to the SAME NodeID as
       the statement's provider_identity (cross-node forgery rejected);
    2. the credential is ACTIVE and not expired at the current evaluation
       time (the store rejects revoked secrets already; we additionally
       confirm the credential is usable); and
    3. the signature is byte-exact over the canonical security-critical
       content.

    This does NOT introduce trust or authorization policy — it verifies
    PROVENANCE (the statement came from the node it claims to be from),
    never truth or authorization.
    """
    if not statement.signature:
        return False
    # BIND: the credential used for verification must belong to the same
    # NodeID the statement names as its provider_identity. A valid
    # signature from Node B on a statement naming Node A is rejected.
    try:
        record = store.get_record(credential)
    except Exception:
        return False
    try:
        declared_node_id = parse_node_id(statement.provider_identity)
    except Exception:
        return False
    if record.node_id != declared_node_id:
        return False
    # The credential must be in an ACTIVE usable state (not revoked, not
    # superseded — those are provenance-breaks).
    from identity.lifecycle import LifecycleState

    if record.status is not LifecycleState.ACTIVE:
        return False
    try:
        expected = provider.sign(store, credential, statement_signature_input(statement))
    except Exception:
        return False
    import hmac as _hmac

    try:
        provided = bytes.fromhex(statement.signature)
    except ValueError:
        return False
    return _hmac.compare_digest(expected, provided)
