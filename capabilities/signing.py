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

from datetime import datetime
from typing import Optional

from identity.credentials import CredentialReference
from identity.store import CredentialStore
from identity.provider import SignatureProvider
from identity.node_id import NodeID, parse_node_id
from protocol.canonicalization import CanonicalizationError, canonical_json_bytes
from protocol.temporal import TemporalError, parse_instant

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
    now: datetime,
) -> bool:
    """Verify a statement's signature through the provider seam at the
    injected evaluation instant.

    ``now`` is a timezone-aware UTC datetime INJECTED by the caller — no
    wall-clock access anywhere in this layer, so verification is fully
    deterministic and reproducible.

    Returns True ONLY when:
    1. the credential's WORK-004 record belongs to the SAME NodeID as
       the statement's provider_identity (cross-node forgery rejected);
    2. the credential's lifecycle is usable AT the evaluation instant —
       ACTIVE status, not revoked, and not expired (``expires_at <= now``
       is rejected, mirroring ``IdentityService._require_active``); and
    3. the signature is byte-exact over the canonical security-critical
       content.

    This does NOT introduce trust or authorization policy — it verifies
    PROVENANCE (the statement came from the node it claims to be from,
    using a credential that was usable at the claimed instant), never
    truth or authorization. An ACTIVE-but-expired credential has a
    byte-correct signature but is rejected because the key was no longer
    usable at the evaluation instant.
    """
    if not statement.signature:
        return False
    if now.tzinfo is None:
        # Fail closed: a naive evaluation instant is a caller bug.
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
    # LIFECYCLE at the evaluation instant. ``status`` is the primary
    # lifecycle signal (REVOKED / SUPERSEDED / EXPIRED / PROVISIONED /
    # ROTATING are all provenance-breaks). Expiry is additionally checked
    # against the injected instant — an ACTIVE credential whose
    # ``expires_at`` has passed is no longer usable (mirrors
    # IdentityService._require_active). Revocation metadata is checked
    # defensively (an invariant violation would mean a record carries
    # revocation info without the status having flipped — fail closed).
    from identity.lifecycle import LifecycleState

    if record.status is not LifecycleState.ACTIVE:
        return False
    if record.revoked is not None:
        return False
    if record.expires_at is not None:
        try:
            expires_instant = parse_instant(record.expires_at)
        except TemporalError:
            return False
        if expires_instant <= now:
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
