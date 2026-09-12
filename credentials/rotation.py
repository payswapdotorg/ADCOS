"""ADCOS credential rotation drills (M018 — Credential and Key
Lifecycle Operations).

Rotation drills with ZERO COVERAGE GAPS: no operation window in which
a superseded (or revoked) credential is still admitted.  The
admitted-set transition is ATOMIC and JOURNALED — the drill:

1. reads the node's admitted set from the identity authority's own
   public records immediately BEFORE the operation (the WORK-004
   status truth — by reference);
2. drives the accepted ``IdentityService.rotate`` — the authority's
   own ATOMIC rotation (the all-or-nothing ``StoreBatch``: the old
   generation superseded, the new generation activated, the new
   secret stored, all in ONE commit; any failure leaves the
   pre-rotation state untouched — no half-rotated identity);
3. reads the admitted set again immediately AFTER;
4. MECHANICALLY verifies the authority outcome is EXACTLY ONE FLIP
   (the zero-coverage-gap kernel — a store outcome that left both
   generations admitted, or neither, fails closed BEFORE anything is
   journaled);
5. journals the rotation record with the before/after sets FULLY
   recorded and the flip at the journaled rotation instant;
6. maintains the accepted M014 credential-lifecycle bookkeeping
   (``CredentialLifecycleState`` — the identity convergence surface,
   by reference) so the composed admission gate's lifecycle verdicts
   track the drill.

The emergency-free ordinary revocation drill
(:func:`run_revocation_drill`) is the same discipline for the
one-removal transition (the distinct EMERGENCY path lives in
:mod:`credentials.emergency` — never a silent shortcut here).

LOCK-119: ``new_secret`` transits :func:`run_rotation_drill`
VERBATIM to the accepted ``IdentityService.rotate`` (the identity
battery's own convention — the secret goes ONLY to the store); it is
never journaled, never echoed, never stored by this domain, and no
public M018 record type can carry secret bytes (structural —
verified by the battery).

Determinism: injected instants only; the journaled operation
sequence is a deterministic, replayable function of the inputs (same
inputs -> the byte-identical journal).
"""

from __future__ import annotations

from typing import Optional

from identity.convergence import CredentialLifecycleState
from identity.credentials import CredentialReference
from identity.lifecycle import LifecycleState
from identity.model import IdentityService
from identity.node_id import NodeID

from .errors import CredentialLifecycleError, CredentialLifecycleReason
from .journal import LifecycleJournal
from .model import (
    CREDENTIALS_ISSUER,
    LifecycleOperationRecord,
    _wrap_consumed_error,
    admitted_set_from_records,
    check_removal_is_atomic,
    check_rotation_flip_is_atomic,
)

__all__ = ["run_rotation_drill", "run_revocation_drill", "admitted_set"]


def admitted_set(service: IdentityService, node_id: NodeID) -> tuple:
    """The node's admitted credential-reference set as read from the
    identity authority's own public records (ACTIVE status only —
    the WORK-004 truth, by reference; sorted, duplicate-free)."""
    if not isinstance(service, IdentityService):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "admitted_set requires the accepted identity.IdentityService "
            "(the identity authority, consumed by reference)",
        )
    if not isinstance(node_id, NodeID):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "admitted_set requires an identity.NodeID",
        )
    return admitted_set_from_records(service.records_for(node_id), node_id.text)


def run_rotation_drill(
    *,
    service: IdentityService,
    m014_state: CredentialLifecycleState,
    journal: LifecycleJournal,
    identity_credential: CredentialReference,
    node_id: NodeID,
    role: str,
    new_secret: bytes,
    authorization: bytes,
    rotated_at: str,
    provenance: Optional[str] = None,
) -> LifecycleOperationRecord:
    """One ATOMIC rotation drill (zero coverage gap; journaled).

    ``new_secret`` and ``authorization`` transit verbatim to the
    accepted ``IdentityService.rotate`` — LOCK-119: the secret goes
    only to the store, never into any M018 record.  ``authorization``
    is the caller-prepared identity-role signature over the canonical
    rotation statement (the identity battery's convention).

    Fail-closed order: the authority rotation FIRST (any identity
    rejection surfaces as the typed composition error with the store
    untouched — the authority's own atomicity), then the flip
    verification, then the journal append (a rejected append leaves
    the journal byte-identical).
    """
    if not isinstance(service, IdentityService):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "run_rotation_drill requires the accepted "
            "identity.IdentityService (by reference)",
        )
    if not isinstance(m014_state, CredentialLifecycleState):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "run_rotation_drill requires the accepted M014 "
            "CredentialLifecycleState (by reference)",
        )
    if not isinstance(journal, LifecycleJournal):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "run_rotation_drill requires a LifecycleJournal",
        )
    if not isinstance(identity_credential, CredentialReference):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "run_rotation_drill requires an identity.CredentialReference "
            "(the rotation authorizer)",
        )
    if not isinstance(node_id, NodeID) or node_id.text != journal.node_id:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.ID_MISMATCH,
            "the rotation drill requires the journal's own node (%r)"
            % (journal.node_id,),
        )
    if not isinstance(role, str) or not role:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "the rotation drill requires the rotating key role",
        )
    if not isinstance(new_secret, (bytes, bytearray)) or not new_secret:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "the rotation drill requires non-empty new secret material "
            "(transit-only: it goes verbatim to the accepted identity "
            "store and never enters any M018 record — LOCK-119)",
        )
    if not isinstance(authorization, (bytes, bytearray)) or not authorization:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "the rotation drill requires the prepared rotation "
            "authorization signature bytes",
        )
    before = admitted_set(service, node_id)
    # 1. the AUTHORITY rotation — atomic by the identity domain's own
    #    StoreBatch discipline (any rejection leaves the identity
    #    state byte-identical; no half-rotated identity).
    with _wrap_consumed_error("the identity rotation authority"):
        activated = service.rotate(
            identity_credential,
            node_id=node_id,
            role=role,
            new_secret=bytes(new_secret),
            authorization=bytes(authorization),
            rotated_at=rotated_at,
        )
    after = admitted_set(service, node_id)
    old_ref = _superseded_reference(before, after, activated)
    new_ref = activated.reference.reference_id
    # 2. the zero-coverage-gap kernel over the AUTHORITY outcome: the
    #    transition must be exactly one flip (fail closed BEFORE any
    #    journaling — a non-atomic authority outcome is never
    #    recorded as a rotation).
    check_rotation_flip_is_atomic(before, after, old_ref, new_ref)
    # 3. the M014 bookkeeping (the identity convergence surface, by
    #    reference: the superseded status observation + the new
    #    generation's activation).
    with _wrap_consumed_error("the M014 credential-lifecycle bookkeeping"):
        m014_state.record_status(old_ref, LifecycleState.SUPERSEDED.value)
        m014_state.record_activation(
            new_ref, rotated_at, LifecycleState.ACTIVE.value
        )
    # 4. the journaled rotation (the flip at the journaled instant,
    #    before/after fully recorded).
    record = LifecycleOperationRecord(
        operation_id="",
        kind="rotation",
        sequence=len(journal) + 1,
        node_id=node_id.text,
        recorded_at=rotated_at,
        subject_ref=old_ref,
        before_admitted=before,
        after_admitted=after,
        replacement_ref=new_ref,
        evidence_refs=(activated.reference.reference_id,),
        provenance=provenance or CREDENTIALS_ISSUER,
    )
    return journal.append(record)


def _superseded_reference(
    before: tuple, after: tuple, activated
) -> str:
    """The superseded generation's reference — derived from the
    authority outcome (the member of the before-set that the rotation
    replaced; exactly one by the flip kernel)."""
    removed = sorted(set(before) - set(after))
    added = sorted(set(after) - set(before))
    if len(removed) != 1 or added != [activated.reference.reference_id]:
        # the kernel re-checks with full diagnostics; here only the
        # derivation fails closed
        raise CredentialLifecycleError(
            CredentialLifecycleReason.ROTATION_NONATOMIC,
            "the authority rotation outcome is not a single flip "
            "(removed %s, added %s)" % (removed, added),
        )
    return removed[0]


def run_revocation_drill(
    *,
    service: IdentityService,
    m014_state: CredentialLifecycleState,
    journal: LifecycleJournal,
    credential_ref: CredentialReference,
    node_id: NodeID,
    reason: str,
    revoked_at: str,
    provenance: Optional[str] = None,
) -> LifecycleOperationRecord:
    """One ORDINARY (non-emergency) revocation drill: the accepted
    ``IdentityService.revoke`` driven by reference, the one-removal
    transition verified by the zero-coverage-gap kernel, the before/
    after sets fully journaled.  The DISTINCT emergency path lives in
    :mod:`credentials.emergency` — never a silent shortcut here."""
    if not isinstance(service, IdentityService):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "run_revocation_drill requires the accepted "
            "identity.IdentityService (by reference)",
        )
    if not isinstance(m014_state, CredentialLifecycleState):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "run_revocation_drill requires the accepted M014 "
            "CredentialLifecycleState (by reference)",
        )
    if not isinstance(journal, LifecycleJournal):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "run_revocation_drill requires a LifecycleJournal",
        )
    if not isinstance(credential_ref, CredentialReference):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "run_revocation_drill requires an identity.CredentialReference",
        )
    if not isinstance(node_id, NodeID) or node_id.text != journal.node_id:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.ID_MISMATCH,
            "the revocation drill requires the journal's own node (%r)"
            % (journal.node_id,),
        )
    if not isinstance(reason, str) or not reason:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "the revocation drill requires a non-empty reason",
        )
    before = admitted_set(service, node_id)
    with _wrap_consumed_error("the identity revocation authority"):
        revoked = service.revoke(credential_ref, reason=reason, now=revoked_at)
    after = admitted_set(service, node_id)
    check_removal_is_atomic(
        before, after, credential_ref.reference_id
    )
    with _wrap_consumed_error("the M014 credential-lifecycle bookkeeping"):
        m014_state.record_status(
            credential_ref.reference_id, LifecycleState.REVOKED.value
        )
    record = LifecycleOperationRecord(
        operation_id="",
        kind="revocation",
        sequence=len(journal) + 1,
        node_id=node_id.text,
        recorded_at=revoked_at,
        subject_ref=credential_ref.reference_id,
        before_admitted=before,
        after_admitted=after,
        reason=reason,
        evidence_refs=(revoked.reference.reference_id,),
        provenance=provenance or CREDENTIALS_ISSUER,
    )
    return journal.append(record)
