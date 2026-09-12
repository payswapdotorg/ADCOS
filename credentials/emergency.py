"""ADCOS emergency credential revocation (M018 — Credential and Key
Lifecycle Operations).

Emergency revocation paths that are EXPLICIT and EVIDENCE-VISIBLE:

- the emergency path is a DISTINCT, TYPED, JOURNALED operation — the
  ``emergency-revocation`` journal kind (never a silent shortcut:
  the ordinary ``revocation`` kind structurally CANNOT carry the
  emergency steps, and the emergency record must carry exactly the
  frozen emergency steps in order);
- it is evidence-visible at EVERY step: each of the three steps
  carries LOCK-106 evidence references consumed BY REFERENCE from
  the accepted ``evidence/`` typing (real ``AttestationEvidence``
  record ids inside the real evidence store the composed world
  holds):

  1. ``identity-revocation`` — the credential revoked through the
     accepted ``IdentityService.revoke`` (the WORK-004 authority:
     the revocation metadata lands on the credential record itself);
  2. ``authorization-revocation`` — the node's principal
     authorization revoked through the accepted M014
     ``AuthorizationRegistry.revoke`` (the revocation record is
     append-only and idempotent; the authorization attestation
     lifted through the accepted M014 closed-loop seam
     ``identity.convergence.authorization_attestation`` into the
     real evidence store cites WHAT was revoked);
  3. ``admission-gate-stop`` — the accepted emergency stop driven
     through the frozen W049 client's OWN ``emergency_stop``
     control (the frozen sequence: the local fail-safe, the
     canonical termination — the converged authority's emergency
     stop revoking the canonical lease through the contract store's
     OWN ``RevokeLease`` command and withdrawing the consent with a
     typed attestation append — then the verified terminal state).
     The consent-attestation stream (pending -> granted ->
     withdrawn) produced by the ACCEPTED authority during the
     drill's lifetime is the LOCK-106 evidence for this step.

Fail-closed order: the steps run in the frozen order; the journal
append happens only when the whole path completed (a failed
emergency leaves the M018 journal byte-identical — no partial
record; the authority-side transitions that DID complete remain
visible at their own authorities, and the typed error discloses the
failing step).  The zero-coverage-gap kernel verifies the admitted-
set transition is exactly one removal BEFORE journaling.
"""

from __future__ import annotations

from typing import Any, Optional, Tuple

from identity.convergence import (
    AuthorizationRegistry,
    CredentialLifecycleState,
    authorization_attestation,
    authorization_revocation,
)
from identity.credentials import CredentialReference
from identity.lifecycle import LifecycleState
from identity.model import IdentityService
from identity.node_id import NodeID

from evidence import AttestationEvidence  # the accepted LOCK-106 typing

from .errors import CredentialLifecycleError, CredentialLifecycleReason
from .journal import LifecycleJournal
from .model import (
    CREDENTIALS_ISSUER,
    EMERGENCY_STEP_KINDS,
    EmergencyStep,
    LifecycleOperationRecord,
    _wrap_consumed_error,
    check_removal_is_atomic,
)
from .rotation import admitted_set

__all__ = ["run_emergency_revocation", "verify_emergency_evidence"]


def run_emergency_revocation(
    *,
    service: IdentityService,
    registry: AuthorizationRegistry,
    evidence_store: Any,
    journal: LifecycleJournal,
    credential_ref: CredentialReference,
    authorization_id: str,
    contract_id: str,
    node_id: NodeID,
    client: Any,
    reason: str,
    now: str,
    evidence_valid_until: str,
    m014_state: Any = None,
    provenance: Optional[str] = None,
) -> LifecycleOperationRecord:
    """Run the distinct typed emergency-revocation path (explicit,
    journaled, evidence-visible at every step).

    ``client`` is the frozen W049 provider client from the composed
    admission-gate world (the accepted ``client/`` surface, driven
    through its OWN ``emergency_stop`` control — by reference).  The
    returned record carries the three frozen steps, each with the
    LOCK-106 evidence references that resolve inside the real
    evidence store.  ``m014_state`` (the accepted M014 bookkeeping)
    is maintained when supplied so the composed admission gate's
    lifecycle verdicts track the emergency.
    """
    if not isinstance(service, IdentityService):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "run_emergency_revocation requires the accepted "
            "identity.IdentityService (by reference)",
        )
    if not isinstance(registry, AuthorizationRegistry):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "run_emergency_revocation requires the accepted M014 "
            "AuthorizationRegistry (by reference)",
        )
    if m014_state is not None and not isinstance(
        m014_state, CredentialLifecycleState
    ):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "run_emergency_revocation requires the accepted M014 "
            "CredentialLifecycleState (by reference) when the M014 "
            "bookkeeping is maintained",
        )
    if evidence_store is None or not hasattr(evidence_store, "records"):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "run_emergency_revocation requires the real evidence store of "
            "the composed admission-gate world (LOCK-106 records consumed "
            "by reference)",
        )
    if not isinstance(journal, LifecycleJournal):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "run_emergency_revocation requires a LifecycleJournal",
        )
    if not isinstance(credential_ref, CredentialReference):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "run_emergency_revocation requires an "
            "identity.CredentialReference",
        )
    if not isinstance(node_id, NodeID) or node_id.text != journal.node_id:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.ID_MISMATCH,
            "the emergency path requires the journal's own node (%r)"
            % (journal.node_id,),
        )
    if client is None or not hasattr(client, "emergency_stop"):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "run_emergency_revocation requires the frozen W049 provider "
            "client of the composed admission-gate world (the accepted "
            "client/ surface, driven through its OWN emergency-stop "
            "control — by reference)",
        )
    from client import ProviderClient

    if not isinstance(client, ProviderClient):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "the emergency stop must be driven through the frozen W049 "
            "ProviderClient (got %s — LOCK-117: the accepted client "
            "surface is driven by reference, never wrapped into a second "
            "runtime)" % type(client).__name__,
        )
    if not isinstance(reason, str) or not reason:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "the emergency path requires a non-empty reason (explicit, "
            "journaled verbatim)",
        )
    if not isinstance(contract_id, str) or not contract_id:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "the emergency path requires the canonical contract id of the "
            "composed admission-gate world (the LOCK-106 evidence records "
            "cite it)",
        )
    before = admitted_set(service, node_id)

    # -- step 1: the identity-side emergency revocation + the typed
    #    evidence lift (a REAL LOCK-106 record in the REAL store, the
    #    controller-verified attestation of the emergency revocation)
    with _wrap_consumed_error("the identity emergency revocation"):
        revoked = service.revoke(credential_ref, reason=reason, now=now)
    if m014_state is not None:
        with _wrap_consumed_error("the M014 credential-lifecycle bookkeeping"):
            m014_state.record_status(
                credential_ref.reference_id, LifecycleState.REVOKED.value
            )
    step1_refs: Tuple[str, ...] = ()
    with _wrap_consumed_error("the emergency revocation attestation"):
        revocation_attestation = AttestationEvidence(
            subject_ref=credential_ref.reference_id,
            contract_ref=contract_id,
            instant=now,
            producer="m018-lifecycle:emergency",
            attestation_kind="controller-verified",
            attested_value=2,
            valid_until=evidence_valid_until,
            source_refs=(credential_ref.reference_id,),
        )
        evidence_store.ingest(revocation_attestation)
        step1_refs = (revocation_attestation.record_id,)

    # -- step 2: the M014 authorization revocation + the evidence lift --
    step2_refs: Tuple[str, ...] = ()
    with _wrap_consumed_error("the M014 authorization revocation"):
        authorization = registry.authorization(authorization_id)
        registry.revoke(
            authorization_revocation(
                authorization_id=authorization_id,
                reason=reason,
                revoked_at=now,
            )
        )
    with _wrap_consumed_error("the M014 authorization attestation lift"):
        attestation = authorization_attestation(
            authorization,
            producer="m018-lifecycle:emergency",
            valid_until=evidence_valid_until,
        )
        evidence_store.ingest(attestation)
        step2_refs = (attestation.record_id,)

    # -- step 3: the accepted emergency stop through the frozen client --
    with _wrap_consumed_error("the frozen client emergency stop"):
        client.emergency_stop()
    step3_refs = _withdrawn_attestation_refs(evidence_store)

    # -- the zero-coverage-gap kernel over the completed path -----------
    after = admitted_set(service, node_id)
    check_removal_is_atomic(
        before, after, credential_ref.reference_id
    )
    steps = (
        EmergencyStep(
            step=EMERGENCY_STEP_KINDS[0],
            detail="credential %s revoked through the identity authority "
            "at %s (reason %r); the controller-verified emergency "
            "attestation ingested in the real evidence store"
            % (credential_ref.reference_id, now, reason),
            evidence_refs=step1_refs,
        ),
        EmergencyStep(
            step=EMERGENCY_STEP_KINDS[1],
            detail="authorization %s revoked through the M014 registry; "
            "attestation lifted through the M014 closed-loop seam"
            % (authorization_id,),
            evidence_refs=step2_refs,
        ),
        EmergencyStep(
            step=EMERGENCY_STEP_KINDS[2],
            detail="the frozen W049 emergency stop driven through the "
            "accepted client/ control (the canonical lease revoked through "
            "the contract store's own command; the consent withdrawn)",
            evidence_refs=step3_refs,
        ),
    )
    record = LifecycleOperationRecord(
        operation_id="",
        kind="emergency-revocation",
        sequence=len(journal) + 1,
        node_id=node_id.text,
        recorded_at=now,
        subject_ref=credential_ref.reference_id,
        before_admitted=before,
        after_admitted=after,
        reason=reason,
        steps=steps,
        evidence_refs=tuple(
            sorted(set(step1_refs) | set(step2_refs) | set(step3_refs))
        ),
        provenance=provenance or CREDENTIALS_ISSUER,
    )
    return journal.append(record)


def _withdrawn_attestation_refs(evidence_store: Any) -> Tuple[str, ...]:
    """The consent-withdrawal attestation references (the LOCK-106
    records the ACCEPTED authority's emergency stop appended — the
    evidence consumed by reference from the accepted evidence
    typing: the typed ``controller-verified`` attestation whose
    attested value is the WITHDRAWN consent state, i.e. 2 in the
    accepted convergence mapping)."""
    refs: list = []
    with _wrap_consumed_error("the evidence-store consent stream read"):
        for record in evidence_store.records():
            kind = getattr(record, "attestation_kind", "")
            attested = getattr(record, "attested_value", None)
            if kind == "controller-verified" and attested == 2:
                refs.append(record.record_id)
    return tuple(sorted(set(refs)))


def verify_emergency_evidence(
    record: LifecycleOperationRecord, evidence_store: Any
) -> Tuple[str, ...]:
    """Fail-closed verification that every LOCK-106 evidence
    reference carried by one emergency-revocation record (on every
    step) resolves to a REAL typed evidence record inside the real
    evidence store — the evidence-visible-at-every-step discipline,
    consumed by reference (never re-derived here).  Returns the
    resolved record ids."""
    if record.kind != "emergency-revocation":
        raise CredentialLifecycleError(
            CredentialLifecycleReason.VOCABULARY,
            "verify_emergency_evidence requires an emergency-revocation "
            "record (got kind %r)" % (record.kind,),
        )
    if evidence_store is None or not hasattr(evidence_store, "has"):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "verify_emergency_evidence requires the real evidence store",
        )
    resolved: set = set()
    problems: list = []
    for step in record.steps:
        for ref in step.evidence_refs:
            with _wrap_consumed_error("the evidence-store resolution"):
                present = evidence_store.has(ref)
            if not present:
                problems.append(
                    "step %r cites evidence %r which does not resolve in "
                    "the real evidence store (fail closed)" % (step.step, ref)
                )
            else:
                resolved.add(ref)
    if problems:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.COMPOSITION,
            "the emergency path is not evidence-visible: %s" % problems[0],
        )
    return tuple(sorted(resolved))
