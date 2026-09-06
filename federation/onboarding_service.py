"""ADCOS provider onboarding service (WORK-057).

The deterministic, auditable onboarding lifecycle executor: the
service FOLDS an append-only command journal into the onboarding
state while composing the existing authorities through their public
interfaces ONLY.

    registration -> identity binding -> scoped credentials ->
    adapter certification (authority-verified admission) ->
    declarations -> commercial profile binding -> eligibility/policy
    gate -> federation proposal -> PEER-AUTHORIZED explicit
    acceptance -> active membership ->
    suspension/revocation/offboarding

Authorization model (DEC-0096 corrections, round 2):

- **Certification admission is authority-verified** (W057-R1-P0-001):
  a certification document enters the onboarding state ONLY through
  the composition-root-injected adapters-authority admission
  verifier, which recomputes the content-derived identity (forged
  ids and mutated contents fail), enforces the authority's own
  attestation/evidence/verdict requirements, and evaluates the
  validity window at the journaled command instant. The check is
  deterministic and runs in BOTH execute and fold mode -- the fold
  re-verifies every journaled certification.
- **Federation acceptance is peer-authorized** (W057-R1-P0-002):
  acceptance is executed by the RELATIONSHIP's peer domain's
  registered operator (actor binding, deterministic, fold-
  re-derivable) presenting the peer operator key proof (fingerprint
  constant-time compared against the peer domain's registered
  ``identity_public_key``; execute-time auth, trusted-as-journaled
  by the secret-free fold). The proposing application's operator,
  scoped credentials, and key proof are the WRONG authority for
  acceptance -- proposer self-acceptance and wrong-peer acceptance
  fail closed.

Recovery model (construction-is-recovery): ``ProviderOnboardingService.load``
re-folds the journaled command prefix onto a FRESH federation store;
the fold is a pure function of (journal, platform profile, issuance
key, certification verifier), so the recovered state is byte-identical
to the pre-interruption state and resuming from the watermark never
duplicates a domain, a relationship, a grant, or a membership. A
journaled outcome the fold cannot reproduce is ``journal-tamper``
(fail closed); the only trusted-as-journaled outcomes are the
secret-dependent authentication rejections, which cannot be
re-derived without the secrets -- by design.

Layering (the frozen import boundaries of the composed packages are
respected exactly): this module lives in the federation package and
imports ONLY the federation surfaces, protocol (canonicalization,
temporal, and the WORK-003 version line used by the mixed-version
gate), the WORK-004 NodeID reference validation, the WORK-005 id
classification, the WORK-010 decision record, and the WORK-045
decision record. Adapter certifications are the adapters authority's
tamper-evident artifacts, admitted ONLY through the injected
adapters-authority admission verifier (the authority owns the
verification logic; this package owns only the seam -- the adapter
boundary is not weakened); resource ownership is checked over the
frozen WORK-008 reference grammar (never imported); the
mixed-version gate consumes the WORK-003 version line directly --
the battery proves all three behaviors verdict-for-verdict against
the adapters, resource, and upgrade authorities' own surfaces.

Onboarding can NEVER create connectivity, session, path, route,
transport, usage, payment, or settlement state: structurally, this
module writes only the onboarding journal/state and the injected
federation store. The forbidden-import audit (battery) pins that
boundary at source level.

Determinism: identical journals produce identical ids, ordering,
decisions, lifecycle transitions, evidence, and serialized outputs.
No wall-clock, no randomness, no UUIDs, no network, no thread
scheduling dependence (all mutations serialized under one lock).
"""

from __future__ import annotations

import hashlib
import hmac
import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

from capabilities.classification import CapabilityIdClass, classify_capability_id
from eligibility.decision import DecisionRecord
from eligibility.states import AuthorizationDomain, DecisionResult, SubjectKind
from policy.model import Effect, PolicyDecision
from protocol.versioning import Classification, classify_major

from .model import DomainLifecycle, RelationshipState, Scope, derive_relationship_id
from .store import FederationStore
from .onboarding_model import (
    COMMAND_ACCEPTS_KEY_PROOF,
    COMMAND_REQUIRED_SCOPE,
    COMMAND_STATUS_APPENDED,
    COMMAND_STATUS_REJECTED,
    DeclarationKind,
    ProviderApplication,
    OnboardingCommandKind,
    OnboardingCommandRecord,
    OnboardingCredential,
    OnboardingCredentialScope,
    OnboardingDeclaration,
    OnboardingError,
    OnboardingProfileBinding,
    OnboardingReason,
    OnboardingState,
    derive_application_id,
    derive_key_proof_digest,
    derive_onboarding_credential_secret,
    onboarding_transition_is_legal,
    peer_key_proof_fingerprint,
    secret_digest,
    _reject_secret_material,
    validate_free_text,
    validate_instant,
    validate_node_id_reference,
    validate_policy_references,
)
from .onboarding_store import (
    ApplicationProjection,
    OnboardingFoldState,
    OnboardingJournal,
)

# ----------------------------------------------------------------------
# Authentication material (execute-time only -- NEVER journaled)
# ----------------------------------------------------------------------


@dataclass
class CommandAuth:
    """Execute-time authentication material.

    Secrets and key material ride HERE only; the journal records just
    the credential reference. In fold mode no auth is available (by
    design), which is exactly why secret-dependent rejections are the
    only trusted-as-journaled outcomes."""

    key_material: bytes = b""
    credential_reference: str = ""
    credential_secret: str = ""


#: reasons that cannot be re-derived by a secret-free fold (the auth
#: checks short-circuit before every deterministic check, so a
#: journaled rejection carrying one of these is trusted as recorded)
_AUTH_DEPENDENT_REASONS = frozenset(
    {
        OnboardingReason.KEY_PROOF_INVALID,
        OnboardingReason.CREDENTIAL_INVALID,
        OnboardingReason.CREDENTIAL_REVOKED_CODE,
        OnboardingReason.CREDENTIAL_EXPIRED,
        OnboardingReason.CREDENTIAL_SCOPE,
        OnboardingReason.PEER_KEY_PROOF_INVALID,
    }
)

#: lifecycle success reasons (a rejected record carrying one of these
#: is a tampered status -- fail closed)
_SUCCESS_REASONS = frozenset(
    {
        OnboardingReason.REGISTERED,
        OnboardingReason.IDENTITY_BOUND,
        OnboardingReason.CREDENTIAL_ISSUED,
        OnboardingReason.CREDENTIAL_REVOKED,
        OnboardingReason.ADAPTER_CERTIFIED,
        OnboardingReason.DECLARED,
        OnboardingReason.DECLARATION_WITHDRAWN,
        OnboardingReason.PROFILE_BOUND,
        OnboardingReason.ELIGIBILITY_GRANTED,
        OnboardingReason.PROPOSED,
        OnboardingReason.ACCEPTED,
        OnboardingReason.MEMBERSHIP_ACTIVE,
        OnboardingReason.MEMBERSHIP_SUSPENDED,
        OnboardingReason.MEMBERSHIP_RESUMED,
        OnboardingReason.REVOKED,
        OnboardingReason.OFFBOARDED,
        OnboardingReason.PROPOSAL_CANCELLED,
        OnboardingReason.DUPLICATE,
    }
)

#: lifecycle stage order (for "artifact may be added once the stage
#: it belongs to is complete" preconditions)
_STAGE_INDEX = {
    OnboardingState.REGISTERED: 0,
    OnboardingState.IDENTITY_BOUND: 1,
    OnboardingState.CREDENTIALS_ISSUED: 2,
    OnboardingState.ADAPTERS_CERTIFIED: 3,
    OnboardingState.DECLARED: 4,
    OnboardingState.PROFILE_BOUND: 5,
    OnboardingState.ELIGIBILITY_GRANTED: 6,
    OnboardingState.PROPOSED: 7,
    OnboardingState.ACCEPTED: 8,
    OnboardingState.ACTIVE: 9,
    OnboardingState.SUSPENDED: 9,
    OnboardingState.REVOKED: 10,
    OnboardingState.OFFBOARDED: 10,
    OnboardingState.CANCELLED: 10,
}


@dataclass(frozen=True)
class OnboardingCommandOutcome:
    """Uniform command result envelope (the service never raises past
    its API for command evaluation). ``secret`` carries a one-time
    issuance secret exactly once (issue-credential only; it is never
    journaled)."""

    ok: bool
    code: str
    detail: str
    record: Optional[OnboardingCommandRecord]
    application_id: str = ""
    secret: str = ""


# ----------------------------------------------------------------------
# Decision document (de)construction -- policy/eligibility decisions
# are fully public data, so the journal carries their complete public
# documents and both the execute path and the fold verify the SAME
# tamper-evident bytes
# ----------------------------------------------------------------------


def policy_decision_document(decision: PolicyDecision) -> Dict[str, Any]:
    return {
        "decision_id": decision.decision_id,
        "effect": decision.effect,
        "code": decision.code,
        "detail": decision.detail,
        "matched_rule_ids": list(decision.matched_rule_ids),
        "policy_set_id": decision.policy_set_id,
        "policy_set_version": int(decision.policy_set_version),
        "evaluation_instant": decision.evaluation_instant,
        "conflict_trace": list(decision.conflict_trace),
        "extensions": [dict(entry) for entry in decision.extensions],
    }


def policy_decision_from_document(document: object) -> PolicyDecision:
    if not isinstance(document, Mapping):
        raise OnboardingError(
            OnboardingReason.INVALID_INPUT,
            "policy decision document must be a mapping",
        )
    return PolicyDecision(
        decision_id=document["decision_id"],
        effect=document["effect"],
        code=document["code"],
        detail=document["detail"],
        matched_rule_ids=tuple(document.get("matched_rule_ids", ())),
        policy_set_id=document["policy_set_id"],
        policy_set_version=int(document["policy_set_version"]),
        evaluation_instant=document["evaluation_instant"],
        conflict_trace=tuple(document.get("conflict_trace", ())),
        extensions=tuple(dict(entry) for entry in document.get("extensions", ())),
    )


def eligibility_decision_document(decision: DecisionRecord) -> Dict[str, Any]:
    return dict(decision.to_dict())


def eligibility_decision_from_document(document: object) -> DecisionRecord:
    if not isinstance(document, Mapping):
        raise OnboardingError(
            OnboardingReason.INVALID_INPUT,
            "eligibility decision document must be a mapping",
        )
    return DecisionRecord(
        decision_id=document["decision_id"],
        subject_kind=document["subject_kind"],
        subject_ref=document["subject_ref"],
        authorization_domain=document["authorization_domain"],
        provider_id=document["provider_id"],
        offer_id=document.get("offer_id", ""),
        device_id=document.get("device_id", ""),
        jurisdiction=document.get("jurisdiction", ""),
        network_sharing_mode=document.get("network_sharing_mode", ""),
        policy_key=document.get("policy_key", ""),
        policy_version=int(document.get("policy_version", 1)),
        policy_digest=document.get("policy_digest", ""),
        result=document["result"],
        reason_codes=tuple(document.get("reason_codes", ())),
        issued_at=document["issued_at"],
        effective_at=document["effective_at"],
        valid_until=document["valid_until"],
        payment_reference=document.get("payment_reference", ""),
        citations=tuple(document.get("citations", ())),
        input_digest=document.get("input_digest", ""),
        provenance=document.get("provenance", ""),
    )


def _short_id(value: object, limit: int = 24) -> str:
    """Compact deterministic rendering of an id for detail strings
    (details are bounded; full ids always ride in the payload/records)."""
    text = value if isinstance(value, str) else repr(value)
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def verify_policy_decision_tamper_evidence(decision: PolicyDecision) -> None:
    """Recompute the decision's content-derived id (the federation
    ``verify_establishment_policy`` discipline: a policy ALLOW is only
    evidence when its id matches its own canonical bytes)."""
    recomputed = hashlib.sha256(decision.canonical_bytes()).hexdigest()
    recorded = decision.decision_id
    if recorded.startswith("sha256:"):
        recorded = recorded[len("sha256:"):]
    if not hmac.compare_digest(recomputed, recorded):
        raise OnboardingError(
            OnboardingReason.POLICY_TAMPERED,
            "policy decision id %r does not match its canonical bytes (tamper "
            "evidence failed; the decision is not admissible)" % (decision.decision_id,),
        )


# ----------------------------------------------------------------------
# ProviderOnboardingService
# ----------------------------------------------------------------------

#: The certification admission-verifier seam (DEC-0096
#: W057-R1-P0-001). The federation package NEVER imports the adapters
#: authority; instead the composition root injects the adapters
#: authority's own verifier (built by
#: ``adapters.certification.make_certification_admission_verifier``)
#: at construction AND at recovery. The contract is plain data:
#: ``(document, evaluation_instant) -> (ok, code, detail, verified)``
#: where ``code``/``detail`` are the adapters authority's own stable
#: fail-closed vocabulary and ``verified`` is the VERIFIED document
#: (None on failure). A service constructed WITHOUT a verifier is a
#: construction error (fail closed) -- there is no shape-check
#: fallback, because a shape check is exactly the round-1 bypass.
CertificationAdmissionVerifier = Callable[
    [Mapping[str, Any], str], Tuple[bool, str, str, Optional[Mapping[str, Any]]]
]

#: the adapters authority's admission-requirement failure code (a
#: genuine REJECTED-verdict record or an admission-requirement
#: failure -- mapped to the onboarding ADAPTER_REJECTED audit reason;
#: every other verifier failure is a tamper/shape failure and maps to
#: CERTIFICATION_INVALID)
_CERTIFICATION_NOT_CERTIFIED_CODE = "not-certified"


class ProviderOnboardingService:
    """The WORK-057 onboarding lifecycle service.

    Fresh construction requires an EMPTY journal and an EMPTY
    federation store; ``load`` recovers by folding a populated journal
    onto a fresh federation store (construction-is-recovery).
    """

    def __init__(
        self,
        *,
        journal: OnboardingJournal,
        federation_store: FederationStore,
        platform_profile: Tuple[int, int],
        issuance_key: bytes,
        certification_verifier: CertificationAdmissionVerifier,
    ) -> None:
        if not isinstance(journal, OnboardingJournal):
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "journal must be an OnboardingJournal"
            )
        if not isinstance(federation_store, FederationStore):
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "federation_store must be a FederationStore"
            )
        if not callable(certification_verifier):
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "certification_verifier must be the adapters authority's admission "
                "verifier (composition-root injected; a service without the "
                "authority's verifier cannot admit ANY certification -- fail "
                "closed, there is no shape-check fallback)",
            )
        if (
            not isinstance(platform_profile, tuple)
            or len(platform_profile) != 2
            or not all(isinstance(value, int) and not isinstance(value, bool)
                       for value in platform_profile)
        ):
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "platform_profile must be a (major, max_minor) integer pair -- the "
                "platform's protocol profile as plain data on the WORK-003 "
                "version line",
            )
        if not isinstance(issuance_key, (bytes, bytearray)) or not issuance_key:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "issuance_key must be non-empty bytes"
            )
        if len(journal) != 0:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "fresh construction requires an empty journal (use load() to recover)",
            )
        if federation_store.get_domains():
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "fresh construction requires an empty federation store (use load() "
                "to recover)",
            )
        self._journal = journal
        self._federation_store = federation_store
        self._platform_profile = platform_profile
        self._issuance_key = bytes(issuance_key)
        self._certification_verifier = certification_verifier
        self._state = OnboardingFoldState()
        self._lock = threading.RLock()

    # -- recovery -----------------------------------------------------

    @classmethod
    def load(
        cls,
        *,
        journal: OnboardingJournal,
        federation_store: FederationStore,
        platform_profile: Tuple[int, int],
        issuance_key: bytes,
        certification_verifier: CertificationAdmissionVerifier,
    ) -> "ProviderOnboardingService":
        """Recover deterministically from the journaled command prefix.

        The fold re-executes every appended command's effects on a
        fresh federation store and verifies every journaled outcome it
        can re-derive; an unreproducible outcome is ``journal-tamper``
        and the service refuses to start (fail closed). The fold
        RE-VERIFIES every journaled certification through the injected
        adapters-authority admission verifier (recomputed identity,
        attestation/evidence requirements, validity window) -- a
        certification mutated in the journal is tamper, not state.
        """
        service = cls.__new__(cls)
        if not isinstance(journal, OnboardingJournal):
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "journal must be an OnboardingJournal"
            )
        if not isinstance(federation_store, FederationStore):
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "federation_store must be a FederationStore"
            )
        if not callable(certification_verifier):
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "certification_verifier must be the adapters authority's admission "
                "verifier (composition-root injected at recovery too; the fold "
                "re-verifies journaled certifications through it -- fail closed)",
            )
        if (
            not isinstance(platform_profile, tuple)
            or len(platform_profile) != 2
            or not all(isinstance(value, int) and not isinstance(value, bool)
                       for value in platform_profile)
        ):
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "platform_profile must be a (major, max_minor) integer pair",
            )
        if not isinstance(issuance_key, (bytes, bytearray)) or not issuance_key:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "issuance_key must be non-empty bytes"
            )
        if federation_store.get_domains():
            # Recovery folds the journaled onboarding mutations ON TOP of the
            # caller's deterministically re-created platform-local federation
            # state (every journaled create_domain replays idempotently; the
            # fold verifies each appended command still applies cleanly).
            pass
        service._journal = journal
        service._federation_store = federation_store
        service._platform_profile = platform_profile
        service._issuance_key = bytes(issuance_key)
        service._certification_verifier = certification_verifier
        service._state = OnboardingFoldState()
        service._lock = threading.RLock()
        with service._lock:
            key_owners: Dict[str, str] = {}
            for record in journal.records():
                if record.status == COMMAND_STATUS_APPENDED:
                    key_slot = record.application_id + "\x00" + record.command_key
                    owner = key_owners.get(key_slot)
                    if owner is not None and owner != record.command_id:
                        raise OnboardingError(
                            OnboardingReason.JOURNAL_TAMPER,
                            "appended command %r re-uses the key %r already owned by "
                            "%r" % (record.command_id, record.command_key, owner),
                        )
                    key_owners[key_slot] = record.command_id
                if record.status == COMMAND_STATUS_REJECTED:
                    if record.reason_code in _SUCCESS_REASONS:
                        raise OnboardingError(
                            OnboardingReason.JOURNAL_TAMPER,
                            "journaled command %r is rejected but carries the success "
                            "reason %r (status tampering; fail closed)"
                            % (record.command_id, record.reason_code),
                        )
                    if record.reason_code in _AUTH_DEPENDENT_REASONS:
                        # Trusted as journaled: the auth check fires before every
                        # deterministic check, so a secret-dependent rejection can
                        # be neither re-derived nor re-applied by a secret-free
                        # fold. No effects, by construction.
                        service._absorb_command_record(service._state, record)
                        continue
                try:
                    ok, reason, detail, _secret = service._evaluate(
                        service._state, record, None, fold_mode=True
                    )
                except OnboardingError as error:
                    ok, reason, detail = False, error.code, error.detail
                if record.status == COMMAND_STATUS_APPENDED:
                    if not ok or reason != record.reason_code:
                        raise OnboardingError(
                            OnboardingReason.JOURNAL_TAMPER,
                            "journaled command %r claims status appended with reason "
                            "%r but the fold derives %s/%r (%s)"
                            % (record.command_id, record.reason_code, ok, reason, detail),
                        )
                else:
                    if ok or reason != record.reason_code:
                        raise OnboardingError(
                            OnboardingReason.JOURNAL_TAMPER,
                            "journaled command %r claims rejection %r but the fold "
                            "derives %s/%r (%s)"
                            % (record.command_id, record.reason_code, ok, reason, detail),
                        )
                service._absorb_command_record(service._state, record)
        return service

    @staticmethod
    def _absorb_command_record(
        state: OnboardingFoldState, record: OnboardingCommandRecord
    ) -> None:
        projection = state.get(record.application_id)
        if projection is not None:
            projection.command_log.append(record)
            projection.next_command_sequence = record.sequence + 1

    # -- queries ------------------------------------------------------

    @property
    def state(self) -> OnboardingState:
        with self._lock:
            return self._state

    @property
    def federation_store(self) -> FederationStore:
        return self._federation_store

    def application(self, application_id: str) -> Optional[ApplicationProjection]:
        with self._lock:
            return self._state.get(application_id)

    def application_ids(self) -> Tuple[str, ...]:
        with self._lock:
            return self._state.application_ids()

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return self._state.snapshot()

    def state_digest(self) -> str:
        with self._lock:
            return self._state.state_digest()

    def journal_digest(self) -> str:
        return self._journal.journal_digest()

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------

    def _execute(
        self,
        *,
        application_id: str,
        command_kind: str,
        command_key: str,
        actor: str,
        issued_at: str,
        effective_at: str,
        payload: Dict[str, Any],
        auth: Optional[CommandAuth] = None,
    ) -> OnboardingCommandOutcome:
        """Build, authenticate, evaluate, and journal one command.

        Atomic: the whole operation (duplicate probe, evaluation,
        state mutation, journal append) runs under the service lock, so
        concurrent submissions serialize deterministically and an
        idempotent duplicate never re-applies effects."""
        with self._lock:
            payload_pairs = tuple(sorted(payload.items(), key=lambda item: item[0]))
            probe = OnboardingCommandRecord(
                command_id="",
                application_id=application_id,
                command_kind=command_kind,
                command_key=command_key,
                sequence=0,
                issued_at=issued_at,
                effective_at=effective_at,
                actor=actor,
                credential_reference=(auth.credential_reference if auth else ""),
                payload=payload_pairs,
                status=COMMAND_STATUS_REJECTED,
                reason_code=OnboardingReason.INVALID_INPUT,
                detail="content probe",
            )
            existing = self._journal.get(probe.command_id)
            if existing is not None:
                return OnboardingCommandOutcome(
                    ok=True,
                    code=OnboardingReason.DUPLICATE,
                    detail=(
                        "command %r is an exact duplicate of the journaled command at "
                        "sequence %d with status %r (idempotent; no state change)"
                        % (probe.command_id, existing.sequence, existing.status)
                    ),
                    record=existing,
                    application_id=application_id,
                )
            key_owner = self._journal.key_owner(application_id, command_key)
            if key_owner is not None and key_owner != probe.command_id:
                return self._journal_rejection(
                    probe,
                    OnboardingReason.SEQUENCE_CONFLICT,
                    "command key %r is already owned by command %r (same key, "
                    "different content; fail closed)" % (command_key, key_owner),
                    application_id,
                )
            try:
                ok, reason, detail, secret = self._evaluate(
                    self._state, probe, auth, fold_mode=False
                )
            except OnboardingError as error:
                ok, reason, detail, secret = False, error.code, error.detail, ""
            if ok:
                record = OnboardingCommandRecord(
                    command_id="",
                    application_id=application_id,
                    command_kind=command_kind,
                    command_key=command_key,
                    sequence=0,
                    issued_at=issued_at,
                    effective_at=effective_at,
                    actor=actor,
                    credential_reference=(auth.credential_reference if auth else ""),
                    payload=payload_pairs,
                    status=COMMAND_STATUS_APPENDED,
                    reason_code=reason,
                    detail=detail,
                )
            else:
                record = OnboardingCommandRecord(
                    command_id="",
                    application_id=application_id,
                    command_kind=command_kind,
                    command_key=command_key,
                    sequence=0,
                    issued_at=issued_at,
                    effective_at=effective_at,
                    actor=actor,
                    credential_reference=(auth.credential_reference if auth else ""),
                    payload=payload_pairs,
                    status=COMMAND_STATUS_REJECTED,
                    reason_code=reason,
                    detail=detail,
                )
            outcome = self._journal.append(record)
            if not outcome.ok:
                # Only reachable through direct journal manipulation
                # races outside the service lock -- fail closed.
                return OnboardingCommandOutcome(
                    ok=False,
                    code=outcome.code,
                    detail=outcome.detail,
                    record=outcome.record,
                    application_id=application_id,
                )
            materialized = outcome.record
            projection = self._state.get(application_id)
            if projection is not None:
                projection.command_log.append(materialized)
                projection.next_command_sequence = materialized.sequence + 1
            return OnboardingCommandOutcome(
                ok=materialized.status == COMMAND_STATUS_APPENDED,
                code=materialized.reason_code,
                detail=materialized.detail,
                record=materialized,
                application_id=application_id,
                secret=secret,
            )

    def _journal_rejection(
        self,
        probe: OnboardingCommandRecord,
        reason: str,
        detail: str,
        application_id: str,
    ) -> OnboardingCommandOutcome:
        record = OnboardingCommandRecord(
            command_id="",
            application_id=probe.application_id,
            command_kind=probe.command_kind,
            command_key=probe.command_key,
            sequence=0,
            issued_at=probe.issued_at,
            effective_at=probe.effective_at,
            actor=probe.actor,
            credential_reference=probe.credential_reference,
            payload=probe.payload,
            status=COMMAND_STATUS_REJECTED,
            reason_code=reason,
            detail=detail,
        )
        outcome = self._journal.append(record)
        materialized = outcome.record if outcome.record is not None else record
        projection = self._state.get(application_id)
        if projection is not None:
            projection.command_log.append(materialized)
            projection.next_command_sequence = materialized.sequence + 1
        return OnboardingCommandOutcome(
            ok=False, code=reason, detail=detail, record=materialized,
            application_id=application_id,
        )

    # ------------------------------------------------------------------
    # Authentication (execute mode only; the fold has no secrets)
    # ------------------------------------------------------------------

    def _authenticate(
        self,
        projection: ApplicationProjection,
        command: OnboardingCommandRecord,
        auth: Optional[CommandAuth],
    ) -> None:
        """Authenticate one command (raises OnboardingError fail
        closed). Auth checks run BEFORE every deterministic check so
        the fold's trusted-as-journaled set is exactly the auth
        reasons."""
        if command.command_kind == OnboardingCommandKind.REGISTER_APPLICATION:
            return
        if command.command_kind == OnboardingCommandKind.ACCEPT_FEDERATION:
            # DEC-0096 W057-R1-P0-002: acceptance is NOT an application-operator
            # command. The proposing application's operator, credentials, and
            # key proof are all WRONG authorities here -- acceptance is
            # authorized by the PEER domain: the actor must be the
            # relationship's peer domain's registered operator (a deterministic,
            # fold-re-derivable binding enforced in the acceptance handler) and
            # the principal must present the peer operator key proof (the
            # secret-dependent check; fold-trusted as journaled).
            self._authorize_peer_acceptance(projection, command, auth)
            return
        if command.actor != projection.application.operator_node_id:
            raise OnboardingError(
                OnboardingReason.PRECONDITION_UNMET,
                "command actor %r is not the application operator %r"
                % (command.actor, projection.application.operator_node_id),
            )
        required_scope = COMMAND_REQUIRED_SCOPE.get(command.command_kind)
        if command.command_kind in COMMAND_ACCEPTS_KEY_PROOF and (
            auth is None or not auth.credential_reference
        ):
            if auth is None or not auth.key_material:
                raise OnboardingError(
                    OnboardingReason.KEY_PROOF_INVALID,
                    "bootstrap command requires the operator key proof (key material "
                    "presented at execute time only; never stored or journaled)",
                )
            derived = derive_key_proof_digest(auth.key_material, command.application_id)
            if not hmac.compare_digest(
                derived, projection.application.key_proof_digest
            ):
                raise OnboardingError(
                    OnboardingReason.KEY_PROOF_INVALID,
                    "operator key proof does not match the application's registered "
                    "proof digest (fail closed; the material itself is never echoed)",
                )
            return
        if auth is None or not auth.credential_reference or not auth.credential_secret:
            raise OnboardingError(
                OnboardingReason.CREDENTIAL_INVALID,
                "command requires a presented scoped credential (reference + secret)",
            )
        credential = projection.credentials.get(auth.credential_reference)
        if credential is None:
            raise OnboardingError(
                OnboardingReason.CREDENTIAL_INVALID,
                "credential %r is not issued for this application"
                % (auth.credential_reference,),
            )
        if not hmac.compare_digest(
            secret_digest(auth.credential_secret), credential.secret_digest
        ):
            raise OnboardingError(
                OnboardingReason.CREDENTIAL_INVALID,
                "credential secret does not match the stored digest (constant-time "
                "compare; no enumeration)",
            )
        if credential.status != "active":
            raise OnboardingError(
                OnboardingReason.CREDENTIAL_REVOKED_CODE,
                "credential %r is revoked (fail closed)" % (auth.credential_reference,),
            )
        if not (
            credential.valid_from <= command.effective_at <= credential.valid_until
        ):
            raise OnboardingError(
                OnboardingReason.CREDENTIAL_EXPIRED,
                "credential %r is not valid at the command instant %r (validity is "
                "evaluated, never observed)"
                % (auth.credential_reference, command.effective_at),
            )
        if required_scope is not None and credential.scope != required_scope:
            raise OnboardingError(
                OnboardingReason.CREDENTIAL_SCOPE,
                "credential scope %r does not cover the required scope %r (least "
                "authority: no scope implies another)"
                % (credential.scope, required_scope),
            )

    def _authorize_peer_acceptance(
        self,
        projection: ApplicationProjection,
        command: OnboardingCommandRecord,
        auth: Optional[CommandAuth],
    ) -> None:
        """Authorize one federation-acceptance command as the PEER
        domain's operator (raises OnboardingError fail closed).

        The secret-dependent half of peer authorization (DEC-0096
        W057-R1-P0-002): the accepting principal must present key
        material whose fingerprint matches the RELATIONSHIP's peer
        domain's registered ``identity_public_key`` -- the WORK-015
        domain-id-deriving identity material, constant-time compared.
        When no relationship/peer domain can be resolved, NO key proof
        can be valid (there is no peer authority to prove possession
        against), so the failure stays on the auth-dependent reason
        and the secret-free fold trusts it as journaled. The actor-to-
        peer-domain binding (and the proposer-self-acceptance
        prohibition) is deterministic and re-derived by the fold
        inside the acceptance handler; only this proof-of-possession
        check is auth-layer. The material itself is never stored or
        journaled.
        """
        relationship = self._federation_store.get_relationship(
            projection.application.relationship_id
        )
        peer_domain = (
            self._federation_store.get_domain(relationship.peer_domain_id)
            if relationship is not None
            else None
        )
        if relationship is None or peer_domain is None:
            raise OnboardingError(
                OnboardingReason.PEER_KEY_PROOF_INVALID,
                "no peer-domain authority is resolvable for acceptance (no "
                "relationship %r or peer domain not registered); no peer key "
                "proof can be valid (fail closed)"
                % (projection.application.relationship_id,),
            )
        if auth is None or not auth.key_material:
            raise OnboardingError(
                OnboardingReason.PEER_KEY_PROOF_INVALID,
                "federation acceptance requires the PEER operator key proof (the "
                "proposing application's operator identity, scoped credentials, "
                "and key proof are all the WRONG authority for acceptance; the "
                "proposer cannot self-accept)",
            )
        fingerprint = peer_key_proof_fingerprint(auth.key_material)
        if not hmac.compare_digest(fingerprint, peer_domain.identity_public_key):
            raise OnboardingError(
                OnboardingReason.PEER_KEY_PROOF_INVALID,
                "peer operator key proof does not match the peer domain's "
                "registered identity material (fail closed; the material itself "
                "is never echoed)",
            )

    # ------------------------------------------------------------------
    # Evaluation (the fold; also the execute path's Phase A/B)
    # ------------------------------------------------------------------

    def _evaluate(
        self,
        state: OnboardingState,
        command: OnboardingCommandRecord,
        auth: Optional[CommandAuth],
        *,
        fold_mode: bool,
    ) -> Tuple[bool, str, str, str]:
        """Evaluate one command against ``state``, applying its effects.

        Returns (ok, reason, detail, secret). In execute mode the auth
        checks run first; in fold mode they are absent (secret-free),
        which is exactly the trusted-as-journaled residual. All
        deterministic checks run identically in both modes."""
        payload = {key: value for key, value in command.payload}
        handler = self._HANDLERS.get(command.command_kind)
        if handler is None:
            return (
                False,
                OnboardingReason.INVALID_INPUT,
                "command kind %r has no handler" % (command.command_kind,),
                "",
            )
        projection = state.get(command.application_id)
        if projection is None and command.command_kind != OnboardingCommandKind.REGISTER_APPLICATION:
            return (
                False,
                OnboardingReason.UNKNOWN_APPLICATION,
                "onboarding application %r is not registered"
                % (command.application_id,),
                "",
            )
        if projection is not None and not fold_mode:
            try:
                self._authenticate(projection, command, auth)
            except OnboardingError as error:
                return False, error.code, error.detail, ""
        return handler(self, state, command, payload, projection)

    # -- individual handlers ------------------------------------------

    def _mixed_version_gate(
        self, applicant_major: int, applicant_max_minor: int
    ) -> Optional[Tuple[int, int]]:
        """The mixed-version admission gate over the WORK-003 version
        line (the single importable version authority): the applicant's
        major must be KNOWN-COMPATIBLE per the frozen protocol artifact
        and must equal the platform's major; compatible peers share the
        additive-evolution floor min(applicant, platform) as DATA.
        Incompatible peers fail closed -- never silently reinterpreted.
        (The battery proves this gate verdict-for-verdict against the
        WORK-029 authority's own ``negotiate_protocol_profile``.)"""
        if classify_major(applicant_major) != Classification.KNOWN_COMPATIBLE:
            return None
        platform_major, platform_max_minor = self._platform_profile
        if applicant_major != platform_major:
            return None
        return (applicant_major, min(applicant_max_minor, platform_max_minor))

    def _eval_register(
        self,
        state: OnboardingState,
        command: OnboardingCommandRecord,
        payload: Mapping[str, Any],
        projection: Optional[ApplicationProjection],
    ) -> Tuple[bool, str, str, str]:
        try:
            operator_reference = validate_free_text(
                payload.get("operator_reference"), "operator_reference"
            )
            identity_public_key = payload.get("identity_public_key", "")
            if not isinstance(identity_public_key, str):
                raise OnboardingError(
                    OnboardingReason.INVALID_INPUT, "identity_public_key must be a string"
                )
            operator_node_id = payload.get("operator_node_id", "")
            provider_id = validate_free_text(payload.get("provider_id"), "provider_id")
            display_name = payload.get("display_name", "")
            if not isinstance(display_name, str):
                raise OnboardingError(
                    OnboardingReason.INVALID_INPUT, "display_name must be a string"
                )
            policy_references = validate_policy_references(
                tuple(
                    (item.get("set_id", ""), int(item.get("version", 0)))
                    for item in payload.get("policy_references", ())
                ),
                "policy_references",
            )
            protocol = payload.get("protocol", {})
            if not isinstance(protocol, Mapping):
                raise OnboardingError(
                    OnboardingReason.INVALID_INPUT, "protocol must be a mapping"
                )
            protocol_major = int(protocol.get("major", -1))
            protocol_max_minor = int(protocol.get("max_minor", -1))
            key_proof_digest = payload.get("key_proof_digest", "")
            if not isinstance(key_proof_digest, str) or not key_proof_digest.startswith(
                "sha256:"
            ):
                raise OnboardingError(
                    OnboardingReason.INVALID_INPUT,
                    "key_proof_digest must be a sha256: digest (key material itself "
                    "never journaled)",
                )
        except OnboardingError as error:
            return False, error.code, error.detail, ""
        try:
            validate_node_id_reference(operator_node_id, "operator_node_id")
        except OnboardingError as error:
            return False, error.code, error.detail, ""
        if command.actor != operator_node_id:
            return (
                False,
                OnboardingReason.PRECONDITION_UNMET,
                "registration actor %r is not the operator being registered %r"
                % (command.actor, operator_node_id),
                "",
            )
        application_id = derive_application_id(
            operator_reference,
            identity_public_key,
            operator_node_id,
            provider_id,
            protocol_major,
            protocol_max_minor,
        )
        if application_id != command.application_id:
            return (
                False,
                OnboardingReason.INVALID_INPUT,
                "command application id %r does not match the payload-derived "
                "identity %r" % (command.application_id, application_id),
                "",
            )
        # Mixed-version gate over the WORK-003 version line (the importable
        # version authority): the applicant's major must be KNOWN and equal
        # the platform's major; the common profile is the additive-evolution
        # floor min(applicant, platform) carried as data. The battery proves
        # this gate agrees with the WORK-029 authority's own negotiation
        # (upgrade.compatibility) verdict-for-verdict.
        common_profile = self._mixed_version_gate(
            protocol_major, protocol_max_minor
        )
        if common_profile is None:
            return (
                False,
                OnboardingReason.VERSION_INCOMPATIBLE,
                "registration refused: protocol major %r is not a known-compatible "
                "major on the WORK-003 version line, or it disagrees with the "
                "platform major %r (incompatible peers fail closed; never silently "
                "reinterpreted)" % (protocol_major, self._platform_profile[0]),
                "",
            )
        try:
            application = ProviderApplication(
                application_id="",
                operator_reference=operator_reference,
                identity_public_key=identity_public_key,
                operator_node_id=operator_node_id,
                provider_id=provider_id,
                display_name=display_name,
                protocol_major=protocol_major,
                protocol_max_minor=protocol_max_minor,
                key_proof_digest=key_proof_digest,
                policy_references=policy_references,
                common_profile_major=common_profile[0],
                common_profile_minor=common_profile[1],
                created_at=command.effective_at,
                lifecycle_state=OnboardingState.REGISTERED,
            )
        except OnboardingError as error:
            return False, error.code, error.detail, ""
        existing = state.get(application_id)
        if existing is not None:
            existing_app = existing.application
            if (
                existing_app.operator_reference == operator_reference
                and existing_app.identity_public_key == identity_public_key
                and existing_app.operator_node_id == operator_node_id
                and existing_app.provider_id == provider_id
                and existing_app.protocol_major == protocol_major
                and existing_app.protocol_max_minor == protocol_max_minor
                and existing_app.key_proof_digest == key_proof_digest
                and existing_app.policy_references == policy_references
            ):
                return (
                    True,
                    OnboardingReason.REGISTERED,
                    "idempotent re-registration of identical material for application "
                    "%r (no state change; admin metadata differences never change identity)"
                    % (application_id,),
                    "",
                )
            return (
                False,
                OnboardingReason.PRECONDITION_UNMET,
                "application %r is already registered with different material "
                "(operator key proof or references differ)" % (application_id,),
                "",
            )
        state.applications[application_id] = ApplicationProjection(application=application)
        return (
            True,
            OnboardingReason.REGISTERED,
            "application %r registered (common protocol profile %d.%d; state "
            "registered)" % (application_id, common_profile[0], common_profile[1]),
            "",
        )

    def _require_live(
        self, projection: ApplicationProjection, minimum_stage: int
    ) -> Tuple[bool, str, str]:
        state = projection.application.lifecycle_state
        if state not in _STAGE_INDEX:
            return (
                False,
                OnboardingReason.INVALID_INPUT,
                "unknown lifecycle state %r" % (state,),
            )
        if _STAGE_INDEX[state] >= 10:
            return (
                False,
                OnboardingReason.APPLICATION_TERMINAL,
                "application is in the terminal state %r (fail closed; history is "
                "preserved but no further commands apply)" % (state,),
            )
        if _STAGE_INDEX[state] < minimum_stage:
            return (
                False,
                OnboardingReason.PRECONDITION_UNMET,
                "lifecycle stage %r precedes the required stage for this command "
                "(deterministic ordering: every stage completes before the next)"
                % (state,),
            )
        return True, "", ""

    def _advance(
        self, projection: ApplicationProjection, new_state: str
    ) -> Tuple[bool, str, str]:
        previous = projection.application.lifecycle_state
        if not onboarding_transition_is_legal(previous, new_state):
            return (
                False,
                OnboardingReason.INVALID_TRANSITION,
                "transition %r -> %r is not legal for an onboarding application"
                % (previous, new_state),
            )
        projection.application = ProviderApplication(
            application_id=projection.application.application_id,
            operator_reference=projection.application.operator_reference,
            identity_public_key=projection.application.identity_public_key,
            operator_node_id=projection.application.operator_node_id,
            provider_id=projection.application.provider_id,
            display_name=projection.application.display_name,
            protocol_major=projection.application.protocol_major,
            protocol_max_minor=projection.application.protocol_max_minor,
            key_proof_digest=projection.application.key_proof_digest,
            policy_references=projection.application.policy_references,
            common_profile_major=projection.application.common_profile_major,
            common_profile_minor=projection.application.common_profile_minor,
            created_at=projection.application.created_at,
            lifecycle_state=new_state,
            domain_id=projection.application.domain_id,
            relationship_id=projection.application.relationship_id,
        )
        return True, "", ""

    def _set_domain_reference(
        self, projection: ApplicationProjection, domain_id: str
    ) -> None:
        application = projection.application
        projection.application = ProviderApplication(
            application_id=application.application_id,
            operator_reference=application.operator_reference,
            identity_public_key=application.identity_public_key,
            operator_node_id=application.operator_node_id,
            provider_id=application.provider_id,
            display_name=application.display_name,
            protocol_major=application.protocol_major,
            protocol_max_minor=application.protocol_max_minor,
            key_proof_digest=application.key_proof_digest,
            policy_references=application.policy_references,
            common_profile_major=application.common_profile_major,
            common_profile_minor=application.common_profile_minor,
            created_at=application.created_at,
            lifecycle_state=application.lifecycle_state,
            domain_id=domain_id,
            relationship_id=application.relationship_id,
        )

    def _set_relationship_reference(
        self, projection: ApplicationProjection, relationship_id: str
    ) -> None:
        application = projection.application
        projection.application = ProviderApplication(
            application_id=application.application_id,
            operator_reference=application.operator_reference,
            identity_public_key=application.identity_public_key,
            operator_node_id=application.operator_node_id,
            provider_id=application.provider_id,
            display_name=application.display_name,
            protocol_major=application.protocol_major,
            protocol_max_minor=application.protocol_max_minor,
            key_proof_digest=application.key_proof_digest,
            policy_references=application.policy_references,
            common_profile_major=application.common_profile_major,
            common_profile_minor=application.common_profile_minor,
            created_at=application.created_at,
            lifecycle_state=application.lifecycle_state,
            domain_id=application.domain_id,
            relationship_id=relationship_id,
        )

    def _eval_bind_identity(
        self,
        state: OnboardingState,
        command: OnboardingCommandRecord,
        payload: Mapping[str, Any],
        projection: ApplicationProjection,
    ) -> Tuple[bool, str, str, str]:
        ok, code, detail = self._require_live(projection, _STAGE_INDEX[OnboardingState.REGISTERED])
        if not ok:
            return False, code, detail, ""
        if projection.application.lifecycle_state != OnboardingState.REGISTERED:
            return (
                False,
                OnboardingReason.PRECONDITION_UNMET,
                "identity binding applies exactly once (state is %r)"
                % (projection.application.lifecycle_state,),
                "",
            )
        application = projection.application
        result = self._federation_store.create_domain(
            application.operator_reference,
            application.identity_public_key,
            operator_node_id=application.operator_node_id,
            display_name=application.display_name,
            policy_references=application.policy_references,
            created_at=command.effective_at,
        )
        if not result.ok or result.code not in ("created", "replayed"):
            return (
                False,
                OnboardingReason.DOMAIN_ERROR,
                "federation domain creation refused: %s (%s)"
                % (result.code, result.detail),
                "",
            )
        domain_id = result.domain.domain_id if result.domain is not None else ""
        if not domain_id:
            return (
                False,
                OnboardingReason.DOMAIN_ERROR,
                "federation domain creation returned no domain id",
                "",
            )
        transition = self._federation_store.transition_domain(
            domain_id,
            DomainLifecycle.ACTIVE,
            event_instant=command.effective_at,
            reason="provider onboarding identity binding",
        )
        if not transition.ok or transition.code not in ("transitioned", "replayed"):
            return (
                False,
                OnboardingReason.DOMAIN_ERROR,
                "federation domain activation refused: %s (%s)"
                % (transition.code, transition.detail),
                "",
            )
        self._set_domain_reference(projection, domain_id)
        ok, code, detail = self._advance(projection, OnboardingState.IDENTITY_BOUND)
        if not ok:
            return False, code, detail, ""
        return (
            True,
            OnboardingReason.IDENTITY_BOUND,
            "operator/domain identity bound: federation domain %s created/verified "
            "and active (operator %s held by validated reference; identity "
            "immutability thereafter enforced by the federation authority)"
            % (_short_id(domain_id), _short_id(application.operator_node_id)),
            "",
        )

    def _eval_issue_credential(
        self,
        state: OnboardingState,
        command: OnboardingCommandRecord,
        payload: Mapping[str, Any],
        projection: ApplicationProjection,
    ) -> Tuple[bool, str, str, str]:
        ok, code, detail = self._require_live(
            projection, _STAGE_INDEX[OnboardingState.IDENTITY_BOUND]
        )
        if not ok:
            return False, code, detail, ""
        if not projection.application.domain_id:
            return (
                False,
                OnboardingReason.PRECONDITION_UNMET,
                "credentials are issued only after the operator/domain identity "
                "binding",
                "",
            )
        scope = payload.get("scope", "")
        if scope not in OnboardingCredentialScope.values():
            return (
                False,
                OnboardingReason.INVALID_INPUT,
                "credential scope %r is not one of the five least-authority "
                "onboarding scopes" % (scope,),
                "",
            )
        try:
            valid_from = validate_instant(payload.get("valid_from"), "valid_from")
            valid_until = validate_instant(payload.get("valid_until"), "valid_until")
        except OnboardingError as error:
            return False, error.code, error.detail, ""
        if valid_until < valid_from:
            return (
                False,
                OnboardingReason.INVALID_INPUT,
                "valid_until must not precede valid_from",
                "",
            )
        sequence = projection.next_credential_sequence
        secret = derive_onboarding_credential_secret(
            self._issuance_key, command.application_id, scope, sequence
        )
        credential = OnboardingCredential(
            credential_reference="",
            application_id=command.application_id,
            scope=scope,
            sequence=sequence,
            status="active",
            valid_from=valid_from,
            valid_until=valid_until,
            issued_at=command.effective_at,
            revoked_at="",
            secret_digest=secret_digest(secret),
        )
        projection.credentials[credential.credential_reference] = credential
        projection.next_credential_sequence = sequence + 1
        if projection.application.lifecycle_state == OnboardingState.IDENTITY_BOUND:
            ok, code, detail = self._advance(
                projection, OnboardingState.CREDENTIALS_ISSUED
            )
            if not ok:
                return False, code, detail, ""
        return (
            True,
            OnboardingReason.CREDENTIAL_ISSUED,
            "scoped credential %r issued (scope %r, sequence %d; the secret is "
            "returned exactly once and only its digest is stored)"
            % (credential.credential_reference, scope, sequence),
            secret,
        )

    def _eval_revoke_credential(
        self,
        state: OnboardingState,
        command: OnboardingCommandRecord,
        payload: Mapping[str, Any],
        projection: ApplicationProjection,
    ) -> Tuple[bool, str, str, str]:
        ok, code, detail = self._require_live(
            projection, _STAGE_INDEX[OnboardingState.IDENTITY_BOUND]
        )
        if not ok:
            return False, code, detail, ""
        target_reference = payload.get("credential_reference", "")
        target = projection.credentials.get(target_reference)
        if target is None:
            return (
                False,
                OnboardingReason.CREDENTIAL_INVALID,
                "credential %r is not issued for this application"
                % (target_reference,),
                "",
            )
        if target.status == "revoked":
            return (
                False,
                OnboardingReason.INVALID_TRANSITION,
                "credential %r is already revoked (revocation is idempotent per "
                "command key; a re-revocation with a new key is a deterministic "
                "rejection)" % (target_reference,),
                "",
            )
        revoked = OnboardingCredential(
            credential_reference=target.credential_reference,
            application_id=target.application_id,
            scope=target.scope,
            sequence=target.sequence,
            status="revoked",
            valid_from=target.valid_from,
            valid_until=target.valid_until,
            issued_at=target.issued_at,
            revoked_at=command.effective_at,
            secret_digest=target.secret_digest,
        )
        projection.credentials[target_reference] = revoked
        return (
            True,
            OnboardingReason.CREDENTIAL_REVOKED,
            "credential %r revoked at %r (fail closed; historical evidence preserved)"
            % (target_reference, command.effective_at),
            "",
        )

    def _eval_certify_adapter(
        self,
        state: OnboardingState,
        command: OnboardingCommandRecord,
        payload: Mapping[str, Any],
        projection: ApplicationProjection,
    ) -> Tuple[bool, str, str, str]:
        ok, code, detail = self._require_live(
            projection, _STAGE_INDEX[OnboardingState.CREDENTIALS_ISSUED]
        )
        if not ok:
            return False, code, detail, ""
        document = payload.get("certification")
        # DEC-0096 W057-R1-P0-001: certification admission CONSUMES the adapters
        # authority's tamper-evident artifact through the injected admission
        # verifier (composition-root seam; the federation package never imports
        # the adapter boundary). The verifier RECOMPUTES the content-derived
        # certification identity (a forged id or any mutated content fails),
        # enforces the authority's own admission requirements (certified
        # verdict, declared attestation, non-empty evidence), and evaluates the
        # validity window at the journaled command instant. This check is
        # deterministic and runs in BOTH execute and fold mode -- the fold
        # re-verifies every journaled certification, so a certification mutated
        # in the journal is tamper, not state. A caller-supplied mapping that
        # merely claims "verdict: certified" is NEVER admitted (the round-1
        # shape-check bypass is closed).
        if not isinstance(document, Mapping):
            return (
                False,
                OnboardingReason.CERTIFICATION_INVALID,
                "adapter certification must be a mapping (the adapters authority's "
                "public record document)",
                "",
            )
        try:
            (
                authority_ok,
                authority_code,
                authority_detail,
                verified_document,
            ) = self._certification_verifier(dict(document), command.effective_at)
        except Exception as error:  # a defective verifier never admits anything
            return (
                False,
                OnboardingReason.CERTIFICATION_INVALID,
                "the adapters certification admission verifier failed closed: "
                "%s" % (type(error).__name__,),
                "",
            )
        if not authority_ok or not isinstance(verified_document, Mapping):
            # journal detail is capped at 256 characters: the stable
            # authority CODE carries the machine-readable verdict, the
            # authority detail is carried truncated (never silent)
            authority_text = authority_detail or ""
            if len(authority_text) > 140:
                authority_text = authority_text[:137] + "..."
            if authority_code == _CERTIFICATION_NOT_CERTIFIED_CODE:
                return (
                    False,
                    OnboardingReason.ADAPTER_REJECTED,
                    "adapter declaration NOT certified by the adapters authority: %s "
                    "(journaled for audit; fail closed)" % (authority_text,),
                    "",
                )
            return (
                False,
                OnboardingReason.CERTIFICATION_INVALID,
                "certification admission refused (%s): %s -- forged or tampered "
                "documents never enter the onboarding state" % (authority_code, authority_text),
                "",
            )
        verified = dict(verified_document)
        certification_id = verified.get("certification_id", "")
        provider_node_id = verified.get("provider_node_id", "")
        if provider_node_id != projection.application.operator_node_id:
            return (
                False,
                OnboardingReason.INVALID_INPUT,
                "adapter declaration binds operator %s but the application "
                "operator is %s (a provider certifies only its own declarations)"
                % (
                    _short_id(provider_node_id, 40),
                    _short_id(projection.application.operator_node_id, 40),
                ),
                "",
            )
        projection.certifications[certification_id] = verified
        if projection.application.lifecycle_state == OnboardingState.CREDENTIALS_ISSUED:
            ok, code, detail = self._advance(
                projection, OnboardingState.ADAPTERS_CERTIFIED
            )
            if not ok:
                return False, code, detail, ""
        return (
            True,
            OnboardingReason.ADAPTER_CERTIFIED,
            "adapter declaration certified through the adapters authority's "
            "verified admission (identity recomputed; attestation and evidence "
            "enforced; validity evaluated at the command instant; evidence is "
            "a claim about a declaration, never topology truth)",
            "",
        )

    def _eval_declare_capability(
        self,
        state: OnboardingState,
        command: OnboardingCommandRecord,
        payload: Mapping[str, Any],
        projection: ApplicationProjection,
    ) -> Tuple[bool, str, str, str]:
        ok, code, detail = self._require_live(
            projection, _STAGE_INDEX[OnboardingState.ADAPTERS_CERTIFIED]
        )
        if not ok:
            return False, code, detail, ""
        subject_reference = payload.get("capability_reference", "")
        classification = classify_capability_id(subject_reference)
        if classification == CapabilityIdClass.INVALID:
            return (
                False,
                OnboardingReason.DECLARATION_INVALID,
                "capability reference %r is not a well-formed capability id "
                "(INVALID ids fail closed; the registry is never coerced)"
                % (subject_reference,),
                "",
            )
        ok, code, detail, _, provenance_pair, _ = (True, "", "", "", "", ())
        try:
            provenance = validate_free_text(payload.get("provenance"), "provenance")
            source_reference = validate_free_text(
                payload.get("source_reference"), "source_reference"
            )
            evidence_refs = tuple(payload.get("evidence_refs", ()))
            valid_from = validate_instant(payload.get("valid_from"), "valid_from")
            expires_at = validate_instant(payload.get("expires_at"), "expires_at")
            if expires_at < valid_from:
                raise OnboardingError(
                    OnboardingReason.INVALID_INPUT,
                    "expires_at must not precede valid_from",
                )
        except OnboardingError as error:
            return False, error.code, error.detail, ""
        sequence = projection.next_declaration_sequence
        try:
            declaration = OnboardingDeclaration(
                declaration_id="",
                application_id=command.application_id,
                declaration_kind=DeclarationKind.CAPABILITY,
                subject_reference=subject_reference,
                subject_owner_node_id=projection.application.operator_node_id,
                provenance=provenance,
                source_reference=source_reference,
                evidence_refs=evidence_refs,
                declared_at=command.effective_at,
                sequence=sequence,
                valid_from=valid_from,
                expires_at=expires_at,
            )
        except OnboardingError as error:
            return False, error.code, error.detail, ""
        projection.declarations[declaration.declaration_id] = declaration
        projection.next_declaration_sequence = sequence + 1
        if projection.application.lifecycle_state == OnboardingState.ADAPTERS_CERTIFIED:
            ok, code, detail = self._advance(projection, OnboardingState.DECLARED)
            if not ok:
                return False, code, detail, ""
        return (
            True,
            OnboardingReason.DECLARED,
            "capability declaration %s recorded (classification %r -- a claim with "
            "provenance, validity, and expiry; never reachability truth; the "
            "capability registry is untouched)"
            % (_short_id(declaration.declaration_id), classification),
            "",
        )

    def _eval_declare_resource(
        self,
        state: OnboardingState,
        command: OnboardingCommandRecord,
        payload: Mapping[str, Any],
        projection: ApplicationProjection,
    ) -> Tuple[bool, str, str, str]:
        ok, code, detail = self._require_live(
            projection, _STAGE_INDEX[OnboardingState.ADAPTERS_CERTIFIED]
        )
        if not ok:
            return False, code, detail, ""
        resource_reference = payload.get("resource_id", "")
        # Owner binding over the frozen WORK-008 reference grammar
        # ("adcos:resource:<owner NodeID>:<kind>:<hash>"): a provider
        # declares only its own resources. The grammar authority stays
        # WORK-008 -- the onboarding layer checks only the owner segment
        # (the full canonical parse is proven by the battery through the
        # resource authority's own parser on the same ids).
        owner_prefix = "adcos:resource:" + projection.application.operator_node_id + ":"
        if not isinstance(resource_reference, str) or not resource_reference.startswith(
            owner_prefix
        ):
            return (
                False,
                OnboardingReason.DECLARATION_INVALID,
                "resource %s is not owned by the declaring operator; a provider "
                "declares only its own resources (owner binding fails closed)"
                % (_short_id(resource_reference, 60),),
                "",
            )
        try:
            provenance = validate_free_text(payload.get("provenance"), "provenance")
            source_reference = validate_free_text(
                payload.get("source_reference"), "source_reference"
            )
            evidence_refs = tuple(payload.get("evidence_refs", ()))
            valid_from = validate_instant(payload.get("valid_from"), "valid_from")
            expires_at = validate_instant(payload.get("expires_at"), "expires_at")
            if expires_at < valid_from:
                raise OnboardingError(
                    OnboardingReason.INVALID_INPUT,
                    "expires_at must not precede valid_from",
                )
        except OnboardingError as error:
            return False, error.code, error.detail, ""
        sequence = projection.next_declaration_sequence
        try:
            declaration = OnboardingDeclaration(
                declaration_id="",
                application_id=command.application_id,
                declaration_kind=DeclarationKind.RESOURCE,
                subject_reference=resource_reference,
                subject_owner_node_id=projection.application.operator_node_id,
                provenance=provenance,
                source_reference=source_reference,
                evidence_refs=evidence_refs,
                declared_at=command.effective_at,
                sequence=sequence,
                valid_from=valid_from,
                expires_at=expires_at,
            )
        except OnboardingError as error:
            return False, error.code, error.detail, ""
        projection.declarations[declaration.declaration_id] = declaration
        projection.next_declaration_sequence = sequence + 1
        if projection.application.lifecycle_state == OnboardingState.ADAPTERS_CERTIFIED:
            ok, code, detail = self._advance(projection, OnboardingState.DECLARED)
            if not ok:
                return False, code, detail, ""
        return (
            True,
            OnboardingReason.DECLARED,
            "resource declaration %s recorded (owner-verified reference; provenance, "
            "validity, and expiry carried; consumed only by the WORK-008 authority)"
            % (_short_id(declaration.declaration_id),),
            "",
        )

    def _eval_withdraw_declaration(
        self,
        state: OnboardingState,
        command: OnboardingCommandRecord,
        payload: Mapping[str, Any],
        projection: ApplicationProjection,
    ) -> Tuple[bool, str, str, str]:
        ok, code, detail = self._require_live(
            projection, _STAGE_INDEX[OnboardingState.ADAPTERS_CERTIFIED]
        )
        if not ok:
            return False, code, detail, ""
        declaration_id = payload.get("declaration_id", "")
        declaration = projection.declarations.get(declaration_id)
        if declaration is None:
            return (
                False,
                OnboardingReason.DECLARATION_INVALID,
                "declaration %r does not exist for this application" % (declaration_id,),
                "",
            )
        if declaration.is_withdrawn():
            return (
                False,
                OnboardingReason.INVALID_TRANSITION,
                "declaration %r is already withdrawn (withdrawal is explicit and "
                "recorded once)" % (declaration_id,),
                "",
            )
        withdrawn = OnboardingDeclaration(
            declaration_id=declaration.declaration_id,
            application_id=declaration.application_id,
            declaration_kind=declaration.declaration_kind,
            subject_reference=declaration.subject_reference,
            subject_owner_node_id=declaration.subject_owner_node_id,
            provenance=declaration.provenance,
            source_reference=declaration.source_reference,
            evidence_refs=declaration.evidence_refs,
            declared_at=declaration.declared_at,
            sequence=declaration.sequence,
            valid_from=declaration.valid_from,
            expires_at=declaration.expires_at,
            withdrawn_at=command.effective_at,
        )
        projection.declarations[declaration_id] = withdrawn
        return (
            True,
            OnboardingReason.DECLARATION_WITHDRAWN,
            "declaration %s withdrawn at %r (the declaration remains queryable as "
            "historical evidence; withdrawal never deletes history)"
            % (_short_id(declaration_id), command.effective_at),
            "",
        )

    def _eval_bind_commercial_profile(
        self,
        state: OnboardingState,
        command: OnboardingCommandRecord,
        payload: Mapping[str, Any],
        projection: ApplicationProjection,
    ) -> Tuple[bool, str, str, str]:
        ok, code, detail = self._require_live(
            projection, _STAGE_INDEX[OnboardingState.DECLARED]
        )
        if not ok:
            return False, code, detail, ""
        sequence = projection.next_declaration_sequence
        try:
            binding = OnboardingProfileBinding(
                binding_id="",
                application_id=command.application_id,
                service_profile_ref=payload.get("service_profile_ref", ""),
                commercial_policy_ref=payload.get("commercial_policy_ref", ""),
                settlement_reference=payload.get("settlement_reference", ""),
                evidence_refs=tuple(payload.get("evidence_refs", ())),
                bound_at=command.effective_at,
                sequence=sequence,
            )
        except OnboardingError as error:
            return False, error.code, error.detail, ""
        projection.bindings[binding.binding_id] = binding
        projection.next_declaration_sequence = sequence + 1
        if projection.application.lifecycle_state == OnboardingState.DECLARED:
            ok, code, detail = self._advance(projection, OnboardingState.PROFILE_BOUND)
            if not ok:
                return False, code, detail, ""
        return (
            True,
            OnboardingReason.PROFILE_BOUND,
            "service/commercial profile binding %s recorded (opaque references to "
            "the existing commercial authorities; settlement stays a typed opaque "
            "reference -- no payment or settlement authority exists here)"
            % (_short_id(binding.binding_id),),
            "",
        )

    def _eval_evaluate_eligibility(
        self,
        state: OnboardingState,
        command: OnboardingCommandRecord,
        payload: Mapping[str, Any],
        projection: ApplicationProjection,
    ) -> Tuple[bool, str, str, str]:
        ok, code, detail = self._require_live(
            projection, _STAGE_INDEX[OnboardingState.PROFILE_BOUND]
        )
        if not ok:
            return False, code, detail, ""
        try:
            policy_decision = policy_decision_from_document(
                payload.get("policy_decision", {})
            )
        except Exception as error:
            return (
                False,
                OnboardingReason.POLICY_TAMPERED,
                "policy decision is not constructible from the public document: %s"
                % (error,),
                "",
            )
        try:
            verify_policy_decision_tamper_evidence(policy_decision)
        except OnboardingError as error:
            return False, error.code, error.detail, ""
        if policy_decision.effect != Effect.ALLOW:
            return (
                False,
                OnboardingReason.POLICY_DENIED,
                "policy decision %r is not an explicit ALLOW (effect %r, code %r) -- "
                "onboarding admission fails closed"
                % (policy_decision.decision_id, policy_decision.effect, policy_decision.code),
                "",
            )
        if (policy_decision.policy_set_id, policy_decision.policy_set_version) not in (
            projection.application.policy_references
        ):
            return (
                False,
                OnboardingReason.POLICY_DENIED,
                "policy decision set (%r, %r) is not among the application's "
                "declared policy references %s"
                % (
                    policy_decision.policy_set_id,
                    policy_decision.policy_set_version,
                    _short_id(repr(projection.application.policy_references), 60),
                ),
                "",
            )
        try:
            eligibility_decision = eligibility_decision_from_document(
                payload.get("eligibility_decision", {})
            )
        except Exception as error:
            return (
                False,
                OnboardingReason.ELIGIBILITY_INVALID,
                "eligibility decision is not constructible from the public document: %s"
                % (error,),
                "",
            )
        if eligibility_decision.authorization_domain != AuthorizationDomain.CONNECTIVITY:
            return (
                False,
                OnboardingReason.ELIGIBILITY_INVALID,
                "eligibility decision %r is not a connectivity-domain decision"
                % (eligibility_decision.decision_id,),
                "",
            )
        if eligibility_decision.subject_kind != SubjectKind.PROVIDER:
            return (
                False,
                OnboardingReason.ELIGIBILITY_INVALID,
                "eligibility decision %r is not a provider-subject decision"
                % (eligibility_decision.decision_id,),
                "",
            )
        if eligibility_decision.provider_id != projection.application.provider_id:
            return (
                False,
                OnboardingReason.ELIGIBILITY_INVALID,
                "eligibility decision provider %r does not match the application "
                "provider %r"
                % (
                    _short_id(eligibility_decision.provider_id, 40),
                    _short_id(projection.application.provider_id, 40),
                ),
                "",
            )
        if eligibility_decision.subject_ref != projection.application.provider_id:
            return (
                False,
                OnboardingReason.ELIGIBILITY_INVALID,
                "eligibility decision subject %r does not match the application "
                "provider %r"
                % (
                    _short_id(eligibility_decision.subject_ref, 40),
                    _short_id(projection.application.provider_id, 40),
                ),
                "",
            )
        if eligibility_decision.result != DecisionResult.ELIGIBLE:
            return (
                False,
                OnboardingReason.ELIGIBILITY_DENIED,
                "eligibility decision %r is %r (reasons %s) -- admission fails closed"
                % (
                    _short_id(eligibility_decision.decision_id),
                    eligibility_decision.result,
                    _short_id(repr(eligibility_decision.reason_codes), 60),
                ),
                "",
            )
        if not (
            eligibility_decision.effective_at
            <= command.effective_at
            <= eligibility_decision.valid_until
        ):
            return (
                False,
                OnboardingReason.ELIGIBILITY_DENIED,
                "eligibility decision %r does not cover the command instant %r "
                "(effective %r, valid until %r -- expiry is evaluated, never observed)"
                % (
                    _short_id(eligibility_decision.decision_id),
                    command.effective_at,
                    eligibility_decision.effective_at,
                    eligibility_decision.valid_until,
                ),
                "",
            )
        projection.policy_decision_ref = policy_decision.decision_id
        projection.eligibility_decision_ref = eligibility_decision.decision_id
        if projection.application.lifecycle_state == OnboardingState.PROFILE_BOUND:
            ok, code, detail = self._advance(
                projection, OnboardingState.ELIGIBILITY_GRANTED
            )
            if not ok:
                return False, code, detail, ""
        return (
            True,
            OnboardingReason.ELIGIBILITY_GRANTED,
            "eligibility/policy gate passed: tamper-evident policy ALLOW %s (set %r "
            "v%d) + eligible connectivity-domain decision %s (both consumed as "
            "records from the owning authorities; onboarding confers neither)"
            % (
                _short_id(policy_decision.decision_id),
                policy_decision.policy_set_id,
                policy_decision.policy_set_version,
                _short_id(eligibility_decision.decision_id),
            ),
            "",
        )

    def _verified_proposal_decision(
        self,
        payload: Mapping[str, Any],
        projection: ApplicationProjection,
    ) -> Tuple[bool, str, str, Optional[PolicyDecision]]:
        """Reconstruct + verify the policy decision a proposal carries
        (the federation authority requires a matching ALLOW whenever
        policy references are declared -- even at proposal time)."""
        if not projection.application.policy_references:
            return True, "", "", None
        document = payload.get("policy_decision")
        if not isinstance(document, Mapping) or not document:
            return (
                False,
                OnboardingReason.POLICY_DENIED,
                "the application declares policy references; a proposal must carry "
                "the verified tamper-evident policy ALLOW",
                None,
            )
        try:
            decision = policy_decision_from_document(document)
            verify_policy_decision_tamper_evidence(decision)
        except OnboardingError as error:
            return False, error.code, error.detail, None
        except Exception as error:
            return (
                False,
                OnboardingReason.POLICY_TAMPERED,
                "policy decision is not constructible: %s" % (error,),
                None,
            )
        if decision.effect != Effect.ALLOW:
            return (
                False,
                OnboardingReason.POLICY_DENIED,
                "proposal policy decision is not an explicit ALLOW",
                None,
            )
        if (decision.policy_set_id, decision.policy_set_version) not in (
            projection.application.policy_references
        ):
            return (
                False,
                OnboardingReason.POLICY_DENIED,
                "proposal policy decision set does not match the application's "
                "declared policy references",
                None,
            )
        return True, "", "", decision

    def _eval_propose_federation(
        self,
        state: OnboardingState,
        command: OnboardingCommandRecord,
        payload: Mapping[str, Any],
        projection: ApplicationProjection,
    ) -> Tuple[bool, str, str, str]:
        if projection.application.lifecycle_state != OnboardingState.ELIGIBILITY_GRANTED:
            return (
                False,
                OnboardingReason.PRECONDITION_UNMET,
                "federation proposal applies exactly from the eligibility-granted "
                "state (state is %r)" % (projection.application.lifecycle_state,),
                "",
            )
        peer_domain_id = payload.get("peer_domain_id", "")
        peer_identity_reference = payload.get("peer_identity_reference", "")
        declared_scopes = payload.get("declared_scopes", ())
        if not isinstance(declared_scopes, (list, tuple)):
            return (
                False,
                OnboardingReason.INVALID_INPUT,
                "declared_scopes must be a list",
                "",
            )
        for scope in declared_scopes:
            if scope not in Scope.values():
                return (
                    False,
                    OnboardingReason.INVALID_INPUT,
                    "scope %r is not in the frozen federation scope vocabulary "
                    "(least authority; no scope implies another)" % (scope,),
                    "",
                )
        scopes = tuple(sorted(set(declared_scopes)))
        if not scopes:
            return (
                False,
                OnboardingReason.INVALID_INPUT,
                "a federation proposal declares at least one scope",
                "",
            )
        peer_domain = self._federation_store.get_domain(peer_domain_id)
        if peer_domain is None:
            return (
                False,
                OnboardingReason.PEER_UNREGISTERED,
                "peer domain %r is not registered locally (explicit peer binding "
                "required; unknown peers fail closed)" % (peer_domain_id,),
                "",
            )
        if peer_domain.lifecycle_state == DomainLifecycle.RETIRED:
            return (
                False,
                OnboardingReason.PEER_UNREGISTERED,
                "peer domain %r is retired (fail closed)" % (peer_domain_id,),
                "",
            )
        common_profile = self._mixed_version_gate(
            projection.application.protocol_major,
            projection.application.protocol_max_minor,
        )
        if common_profile is None:
            return (
                False,
                OnboardingReason.VERSION_INCOMPATIBLE,
                "proposal refused at the mixed-version gate: the application's "
                "protocol profile is not compatible with the platform's on the "
                "WORK-003 version line (fail closed)",
                "",
            )
        ok, code, detail, decision = self._verified_proposal_decision(payload, projection)
        if not ok:
            return False, code, detail, ""
        valid_from = payload.get("valid_from", "")
        valid_until = payload.get("valid_until", "")
        audit_requirements = tuple(
            (item.get("key", ""), item.get("value", ""))
            for item in payload.get("audit_requirements", ())
        )
        settlement_reference = payload.get("settlement_policy_reference", "")
        result = self._federation_store.propose_relationship(
            projection.application.domain_id,
            peer_domain_id,
            peer_identity_reference=peer_identity_reference,
            declared_scopes=scopes,
            valid_from=valid_from,
            valid_until=valid_until,
            event_instant=command.effective_at,
            settlement_policy_reference=settlement_reference,
            audit_requirements=audit_requirements,
            policy_references=projection.application.policy_references,
            policy_decision=decision,
        )
        if not result.ok:
            if result.code == "peer-identity-mismatch":
                return (
                    False,
                    OnboardingReason.PEER_IDENTITY_MISMATCH,
                    "peer identity reference does not match the locally registered "
                    "peer operator (cross-domain identity confusion fails closed)",
                    "",
                )
            if result.code == "policy-denied":
                return (
                    False,
                    OnboardingReason.POLICY_DENIED,
                    "federation authority refused the proposal on policy: %s"
                    % (result.detail,),
                    "",
                )
            return (
                False,
                OnboardingReason.RELATIONSHIP_ERROR,
                "federation proposal refused: %s (%s)" % (result.code, result.detail),
                "",
            )
        relationship_id = (
            result.relationship.relationship_id
            if result.relationship is not None
            else derive_relationship_id(
                projection.application.domain_id, peer_domain_id
            )
        )
        self._set_relationship_reference(projection, relationship_id)
        ok, code, detail = self._advance(projection, OnboardingState.PROPOSED)
        if not ok:
            return False, code, detail, ""
        return (
            True,
            OnboardingReason.PROPOSED,
            "federation proposal recorded through the WORK-015 authority "
            "(relationship %s, scopes %r, settlement reference opaque; membership "
            "never implies node-level trust)"
            % (_short_id(relationship_id), list(scopes)),
            "",
        )

    def _eval_accept_federation(
        self,
        state: OnboardingState,
        command: OnboardingCommandRecord,
        payload: Mapping[str, Any],
        projection: ApplicationProjection,
    ) -> Tuple[bool, str, str, str]:
        if projection.application.lifecycle_state != OnboardingState.PROPOSED:
            return (
                False,
                OnboardingReason.PRECONDITION_UNMET,
                "acceptance applies exactly from the proposed state (state is %r)"
                % (projection.application.lifecycle_state,),
                "",
            )
        scopes = payload.get("scopes", ())
        if not isinstance(scopes, (list, tuple)):
            return (
                False,
                OnboardingReason.INVALID_INPUT,
                "scopes must be a list",
                "",
            )
        relationship = self._federation_store.get_relationship(
            projection.application.relationship_id
        )
        if relationship is None:
            return (
                False,
                OnboardingReason.RELATIONSHIP_ERROR,
                "relationship %r does not exist in the federation authority"
                % (projection.application.relationship_id,),
                "",
            )
        # DEC-0096 W057-R1-P0-002: deterministic peer-domain authorization,
        # enforced in BOTH execute and fold mode (the fold re-derives it, so a
        # journal-forged acceptance with a non-peer actor is tamper, not
        # state). The accepting principal MUST be the relationship's peer
        # domain's registered operator, and MUST NOT be the proposing
        # application's operator -- the proposer can never self-accept. (The
        # proof-of-possession half -- the peer operator key proof against the
        # peer domain's registered identity material -- is execute-time auth
        # and is trusted-as-journaled by the secret-free fold.)
        peer_domain = self._federation_store.get_domain(relationship.peer_domain_id)
        if peer_domain is None:
            return (
                False,
                OnboardingReason.PEER_NOT_AUTHORIZED,
                "peer domain %r is not registered; acceptance has no authorizing "
                "peer authority (fail closed)" % (relationship.peer_domain_id,),
                "",
            )
        if command.actor != peer_domain.operator_node_id:
            return (
                False,
                OnboardingReason.PEER_NOT_AUTHORIZED,
                "accepting principal %s is not the peer domain's registered "
                "operator %s (acceptance is authorized by the PEER domain; "
                "wrong-peer operators fail closed)"
                % (
                    _short_id(command.actor, 40),
                    _short_id(peer_domain.operator_node_id, 40),
                ),
                "",
            )
        if command.actor == projection.application.operator_node_id:
            return (
                False,
                OnboardingReason.PEER_NOT_AUTHORIZED,
                "the proposing application's operator %s cannot accept its own "
                "federation proposal (proposer self-acceptance is forbidden; "
                "acceptance requires the peer domain's independent authority)"
                % (_short_id(command.actor, 40),),
                "",
            )
        for scope in scopes:
            if scope not in relationship.declared_scopes:
                return (
                    False,
                    OnboardingReason.INVALID_INPUT,
                    "acceptance scope %r is outside the declared envelope (the "
                    "accepting side may only NARROW)" % (scope,),
                    "",
                )
        ok, code, detail, decision = self._verified_proposal_decision(payload, projection)
        if not ok:
            return False, code, detail, ""
        result = self._federation_store.accept_relationship(
            projection.application.relationship_id,
            event_instant=command.effective_at,
            scopes=tuple(sorted(set(scopes))),
            policy_decision=decision,
        )
        if not result.ok:
            if result.code == "policy-denied":
                return (
                    False,
                    OnboardingReason.POLICY_DENIED,
                    "federation authority refused acceptance on policy: %s"
                    % (result.detail,),
                    "",
                )
            return (
                False,
                OnboardingReason.RELATIONSHIP_ERROR,
                "federation acceptance refused: %s (%s)" % (result.code, result.detail),
                "",
            )
        ok, code, detail = self._advance(projection, OnboardingState.ACCEPTED)
        if not ok:
            return False, code, detail, ""
        return (
            True,
            OnboardingReason.ACCEPTED,
            "federation acceptance recorded (EXPLICIT acceptance; scope may only "
            "narrow; relationship %s ESTABLISHED by the owning authority)"
            % (_short_id(projection.application.relationship_id),),
            "",
        )

    def _eval_activate_membership(
        self,
        state: OnboardingState,
        command: OnboardingCommandRecord,
        payload: Mapping[str, Any],
        projection: ApplicationProjection,
    ) -> Tuple[bool, str, str, str]:
        if projection.application.lifecycle_state != OnboardingState.ACCEPTED:
            return (
                False,
                OnboardingReason.PRECONDITION_UNMET,
                "membership activation applies exactly from the accepted state "
                "(state is %r)" % (projection.application.lifecycle_state,),
                "",
            )
        relationship = self._federation_store.get_relationship(
            projection.application.relationship_id
        )
        if relationship is None or relationship.state != RelationshipState.ESTABLISHED:
            return (
                False,
                OnboardingReason.RELATIONSHIP_ERROR,
                "relationship %r is not ESTABLISHED (membership activation requires "
                "the owning authority's established state)"
                % (projection.application.relationship_id,),
                "",
            )
        grant_ids = []
        for scope in sorted(relationship.declared_scopes):
            grant_result = self._federation_store.publish_grant(
                projection.application.relationship_id,
                scope,
                valid_from=relationship.valid_from,
                valid_until=relationship.valid_until,
                event_instant=command.effective_at,
            )
            if not grant_result.ok:
                return (
                    False,
                    OnboardingReason.RELATIONSHIP_ERROR,
                    "grant publication refused for scope %r: %s (%s)"
                    % (scope, grant_result.code, grant_result.detail),
                    "",
                )
            if grant_result.grant is not None:
                grant_ids.append(grant_result.grant.grant_id)
        projection.membership_status = "active"
        projection.membership_grant_ids = tuple(sorted(grant_ids))
        projection.activated_at = command.effective_at
        ok, code, detail = self._advance(projection, OnboardingState.ACTIVE)
        if not ok:
            return False, code, detail, ""
        return (
            True,
            OnboardingReason.MEMBERSHIP_ACTIVE,
            "federated membership active (relationship %s; %d least-authority "
            "grants published inside the declared envelope; membership never "
            "implies node-level trust)"
            % (_short_id(projection.application.relationship_id), len(grant_ids)),
            "",
        )

    def _eval_suspend_membership(
        self,
        state: OnboardingState,
        command: OnboardingCommandRecord,
        payload: Mapping[str, Any],
        projection: ApplicationProjection,
    ) -> Tuple[bool, str, str, str]:
        if projection.application.lifecycle_state != OnboardingState.ACTIVE:
            return (
                False,
                OnboardingReason.PRECONDITION_UNMET,
                "suspension applies exactly from the active state (state is %r)"
                % (projection.application.lifecycle_state,),
                "",
            )
        result = self._federation_store.suspend_relationship(
            projection.application.relationship_id,
            event_instant=command.effective_at,
        )
        if not result.ok:
            return (
                False,
                OnboardingReason.RELATIONSHIP_ERROR,
                "federation suspension refused: %s (%s)" % (result.code, result.detail),
                "",
            )
        projection.membership_status = "suspended"
        projection.suspended_at = command.effective_at
        ok, code, detail = self._advance(projection, OnboardingState.SUSPENDED)
        if not ok:
            return False, code, detail, ""
        return (
            True,
            OnboardingReason.MEMBERSHIP_SUSPENDED,
            "membership suspended (new admission is blocked fail-closed while "
            "suspended; historical evidence preserved)",
            "",
        )

    def _eval_resume_membership(
        self,
        state: OnboardingState,
        command: OnboardingCommandRecord,
        payload: Mapping[str, Any],
        projection: ApplicationProjection,
    ) -> Tuple[bool, str, str, str]:
        if projection.application.lifecycle_state != OnboardingState.SUSPENDED:
            return (
                False,
                OnboardingReason.PRECONDITION_UNMET,
                "resumption applies exactly from the suspended state (state is %r)"
                % (projection.application.lifecycle_state,),
                "",
            )
        result = self._federation_store.resume_relationship(
            projection.application.relationship_id,
            event_instant=command.effective_at,
        )
        if not result.ok:
            return (
                False,
                OnboardingReason.RELATIONSHIP_ERROR,
                "federation resumption refused: %s (%s)" % (result.code, result.detail),
                "",
            )
        projection.membership_status = "active"
        ok, code, detail = self._advance(projection, OnboardingState.ACTIVE)
        if not ok:
            return False, code, detail, ""
        return (
            True,
            OnboardingReason.MEMBERSHIP_RESUMED,
            "membership resumed (explicit resumption; the full lifecycle history "
            "remains append-only)",
            "",
        )

    def _eval_cancel_proposal(
        self,
        state: OnboardingState,
        command: OnboardingCommandRecord,
        payload: Mapping[str, Any],
        projection: ApplicationProjection,
    ) -> Tuple[bool, str, str, str]:
        if projection.application.lifecycle_state != OnboardingState.PROPOSED:
            return (
                False,
                OnboardingReason.PRECONDITION_UNMET,
                "cancellation applies exactly from the proposed state (state is %r)"
                % (projection.application.lifecycle_state,),
                "",
            )
        result = self._federation_store.cancel_relationship(
            projection.application.relationship_id,
            event_instant=command.effective_at,
        )
        if not result.ok:
            return (
                False,
                OnboardingReason.RELATIONSHIP_ERROR,
                "federation cancellation refused: %s (%s)" % (result.code, result.detail),
                "",
            )
        projection.membership_status = "cancelled"
        projection.cancelled_at = command.effective_at
        ok, code, detail = self._advance(projection, OnboardingState.CANCELLED)
        if not ok:
            return False, code, detail, ""
        return (
            True,
            OnboardingReason.PROPOSAL_CANCELLED,
            "federation proposal cancelled (terminal; history preserved)",
            "",
        )

    def _revoke_all_credentials(
        self, projection: ApplicationProjection, effective_at: str
    ) -> int:
        revoked_count = 0
        for reference in sorted(projection.credentials):
            credential = projection.credentials[reference]
            if credential.status == "active":
                projection.credentials[reference] = OnboardingCredential(
                    credential_reference=credential.credential_reference,
                    application_id=credential.application_id,
                    scope=credential.scope,
                    sequence=credential.sequence,
                    status="revoked",
                    valid_from=credential.valid_from,
                    valid_until=credential.valid_until,
                    issued_at=credential.issued_at,
                    revoked_at=effective_at,
                    secret_digest=credential.secret_digest,
                )
                revoked_count += 1
        return revoked_count

    def _relationship_is_terminal(self, relationship_id: str) -> bool:
        if not relationship_id:
            return True
        relationship = self._federation_store.get_relationship(relationship_id)
        if relationship is None:
            return True
        return relationship.state in (
            RelationshipState.REVOKED,
            RelationshipState.TERMINATED,
            RelationshipState.CANCELLED,
        )

    def _eval_revoke_application(
        self,
        state: OnboardingState,
        command: OnboardingCommandRecord,
        payload: Mapping[str, Any],
        projection: ApplicationProjection,
    ) -> Tuple[bool, str, str, str]:
        ok, code, detail = self._require_live(projection, 0)
        if not ok:
            return False, code, detail, ""
        reason = payload.get("reason", "onboarding revocation")
        try:
            validate_free_text(reason, "reason")
        except OnboardingError as error:
            return False, error.code, error.detail, ""
        relationship_id = projection.application.relationship_id
        if relationship_id and not self._relationship_is_terminal(relationship_id):
            result = self._federation_store.revoke_relationship(
                relationship_id,
                event_instant=command.effective_at,
                reason=reason,
            )
            if not result.ok:
                return (
                    False,
                    OnboardingReason.RELATIONSHIP_ERROR,
                    "federation revocation refused: %s (%s)" % (result.code, result.detail),
                    "",
                )
        revoked_credentials = self._revoke_all_credentials(projection, command.effective_at)
        projection.membership_status = "revoked"
        projection.revoked_at = command.effective_at
        ok, code, detail = self._advance(projection, OnboardingState.REVOKED)
        if not ok:
            return False, code, detail, ""
        return (
            True,
            OnboardingReason.REVOKED,
            "onboarding application revoked (fail closed: %d credential(s) revoked, "
            "new admission blocked, full history preserved queryable)"
            % (revoked_credentials,),
            "",
        )

    def _eval_offboard_application(
        self,
        state: OnboardingState,
        command: OnboardingCommandRecord,
        payload: Mapping[str, Any],
        projection: ApplicationProjection,
    ) -> Tuple[bool, str, str, str]:
        if projection.application.lifecycle_state not in (
            OnboardingState.ACTIVE,
            OnboardingState.SUSPENDED,
        ):
            return (
                False,
                OnboardingReason.PRECONDITION_UNMET,
                "offboarding applies from the active or suspended membership states "
                "(state is %r)" % (projection.application.lifecycle_state,),
                "",
            )
        reason = payload.get("reason", "deterministic offboarding")
        try:
            validate_free_text(reason, "reason")
        except OnboardingError as error:
            return False, error.code, error.detail, ""
        relationship_id = projection.application.relationship_id
        if relationship_id and not self._relationship_is_terminal(relationship_id):
            result = self._federation_store.terminate_relationship(
                relationship_id,
                event_instant=command.effective_at,
                reason=reason,
            )
            if not result.ok:
                return (
                    False,
                    OnboardingReason.RELATIONSHIP_ERROR,
                    "federation termination refused: %s (%s)" % (result.code, result.detail),
                    "",
                )
        domain_id = projection.application.domain_id
        if domain_id:
            domain = self._federation_store.get_domain(domain_id)
            if domain is not None and domain.lifecycle_state != DomainLifecycle.RETIRED:
                result = self._federation_store.transition_domain(
                    domain_id,
                    DomainLifecycle.RETIRED,
                    event_instant=command.effective_at,
                    reason="deterministic provider offboarding",
                )
                if not result.ok:
                    return (
                        False,
                        OnboardingReason.DOMAIN_ERROR,
                        "domain retirement refused: %s (%s)" % (result.code, result.detail),
                        "",
                    )
        revoked_credentials = self._revoke_all_credentials(projection, command.effective_at)
        projection.membership_status = "offboarded"
        projection.offboarded_at = command.effective_at
        ok, code, detail = self._advance(projection, OnboardingState.OFFBOARDED)
        if not ok:
            return False, code, detail, ""
        return (
            True,
            OnboardingReason.OFFBOARDED,
            "deterministic offboarding complete (%d credential(s) revoked, "
            "relationship terminated, domain retired; future participation is "
            "blocked fail-closed and historical commercial/federation evidence is "
            "never deleted)" % (revoked_credentials,),
            "",
        )

    _HANDLERS = {
        OnboardingCommandKind.REGISTER_APPLICATION: _eval_register,
        OnboardingCommandKind.BIND_IDENTITY: _eval_bind_identity,
        OnboardingCommandKind.ISSUE_CREDENTIAL: _eval_issue_credential,
        OnboardingCommandKind.REVOKE_CREDENTIAL: _eval_revoke_credential,
        OnboardingCommandKind.CERTIFY_ADAPTER: _eval_certify_adapter,
        OnboardingCommandKind.DECLARE_CAPABILITY: _eval_declare_capability,
        OnboardingCommandKind.DECLARE_RESOURCE: _eval_declare_resource,
        OnboardingCommandKind.WITHDRAW_DECLARATION: _eval_withdraw_declaration,
        OnboardingCommandKind.BIND_COMMERCIAL_PROFILE: _eval_bind_commercial_profile,
        OnboardingCommandKind.EVALUATE_ELIGIBILITY: _eval_evaluate_eligibility,
        OnboardingCommandKind.PROPOSE_FEDERATION: _eval_propose_federation,
        OnboardingCommandKind.ACCEPT_FEDERATION: _eval_accept_federation,
        OnboardingCommandKind.ACTIVATE_MEMBERSHIP: _eval_activate_membership,
        OnboardingCommandKind.SUSPEND_MEMBERSHIP: _eval_suspend_membership,
        OnboardingCommandKind.RESUME_MEMBERSHIP: _eval_resume_membership,
        OnboardingCommandKind.CANCEL_PROPOSAL: _eval_cancel_proposal,
        OnboardingCommandKind.REVOKE_APPLICATION: _eval_revoke_application,
        OnboardingCommandKind.OFFBOARD_APPLICATION: _eval_offboard_application,
    }

    # ------------------------------------------------------------------
    # Typed command surface (each marshals a JSON-safe payload and
    # executes atomically; secrets/key material never reach the journal)
    # ------------------------------------------------------------------

    def register_application(
        self,
        *,
        operator_reference: str,
        identity_public_key: str,
        operator_node_id: str,
        provider_id: str,
        display_name: str = "",
        policy_references: Tuple[Tuple[str, int], ...] = (),
        protocol_major: int,
        protocol_max_minor: int,
        key_material: bytes,
        actor: str,
        command_key: str,
        issued_at: str,
        effective_at: str,
    ) -> OnboardingCommandOutcome:
        application_id = derive_application_id(
            operator_reference,
            identity_public_key,
            operator_node_id,
            provider_id,
            protocol_major,
            protocol_max_minor,
        )
        payload = {
            "operator_reference": operator_reference,
            "identity_public_key": identity_public_key,
            "operator_node_id": operator_node_id,
            "provider_id": provider_id,
            "display_name": display_name,
            "policy_references": [
                {"set_id": set_id, "version": version}
                for set_id, version in policy_references
            ],
            "protocol": {"major": int(protocol_major), "max_minor": int(protocol_max_minor)},
            "key_proof_digest": derive_key_proof_digest(key_material, application_id),
        }
        return self._execute(
            application_id=application_id,
            command_kind=OnboardingCommandKind.REGISTER_APPLICATION,
            command_key=command_key,
            actor=actor,
            issued_at=issued_at,
            effective_at=effective_at,
            payload=payload,
        )

    def bind_identity(
        self,
        *,
        application_id: str,
        key_material: bytes,
        command_key: str,
        actor: str,
        issued_at: str,
        effective_at: str,
    ) -> OnboardingCommandOutcome:
        return self._execute(
            application_id=application_id,
            command_kind=OnboardingCommandKind.BIND_IDENTITY,
            command_key=command_key,
            actor=actor,
            issued_at=issued_at,
            effective_at=effective_at,
            payload={},
            auth=CommandAuth(key_material=key_material),
        )

    def issue_credential(
        self,
        *,
        application_id: str,
        scope: str,
        valid_from: str,
        valid_until: str,
        command_key: str,
        actor: str,
        issued_at: str,
        effective_at: str,
        key_material: bytes = b"",
        credential_reference: str = "",
        credential_secret: str = "",
    ) -> OnboardingCommandOutcome:
        return self._execute(
            application_id=application_id,
            command_kind=OnboardingCommandKind.ISSUE_CREDENTIAL,
            command_key=command_key,
            actor=actor,
            issued_at=issued_at,
            effective_at=effective_at,
            payload={"scope": scope, "valid_from": valid_from, "valid_until": valid_until},
            auth=CommandAuth(
                key_material=key_material,
                credential_reference=credential_reference,
                credential_secret=credential_secret,
            ),
        )

    def revoke_credential(
        self,
        *,
        application_id: str,
        target_credential_reference: str,
        command_key: str,
        actor: str,
        issued_at: str,
        effective_at: str,
        auth: CommandAuth,
    ) -> OnboardingCommandOutcome:
        return self._execute(
            application_id=application_id,
            command_kind=OnboardingCommandKind.REVOKE_CREDENTIAL,
            command_key=command_key,
            actor=actor,
            issued_at=issued_at,
            effective_at=effective_at,
            payload={"credential_reference": target_credential_reference},
            auth=auth,
        )

    def certify_adapter(
        self,
        *,
        application_id: str,
        certification,
        command_key: str,
        actor: str,
        issued_at: str,
        effective_at: str,
        auth: CommandAuth,
    ) -> OnboardingCommandOutcome:
        """Record one adapter certification (authority-verified).

        ``certification`` is the adapters authority's tamper-evident
        record (an object exposing ``to_dict()``, e.g. the
        ``adapters.certification.AdapterCertification`` built by
        ``certify_adapter_descriptor``) or its public document mapping.
        The document is VERIFIED at admission through the
        composition-root-injected adapters-authority admission verifier
        (recomputed content-derived identity, attestation/evidence
        requirements, validity window at the command instant) -- the
        federation package never imports the adapter boundary, and a
        caller-supplied mapping that merely claims ``verdict:
        certified`` is never admitted (DEC-0096 W057-R1-P0-001)."""
        if hasattr(certification, "to_dict") and not isinstance(certification, Mapping):
            document = certification.to_dict()
        elif isinstance(certification, Mapping):
            document = dict(certification)
        else:
            document = {}
        projection = self._state.get(application_id)
        if projection is None:
            # Unknown application: the deterministic rejection is journaled
            # for audit without validating any certification record.
            document = {}
        return self._execute(
            application_id=application_id,
            command_kind=OnboardingCommandKind.CERTIFY_ADAPTER,
            command_key=command_key,
            actor=actor,
            issued_at=issued_at,
            effective_at=effective_at,
            payload={"certification": document},
            auth=auth,
        )

    def declare_capability(
        self,
        *,
        application_id: str,
        capability_reference: str,
        provenance: str,
        source_reference: str,
        evidence_refs: Tuple[str, ...],
        valid_from: str,
        expires_at: str,
        command_key: str,
        actor: str,
        issued_at: str,
        effective_at: str,
        auth: CommandAuth,
    ) -> OnboardingCommandOutcome:
        return self._execute(
            application_id=application_id,
            command_kind=OnboardingCommandKind.DECLARE_CAPABILITY,
            command_key=command_key,
            actor=actor,
            issued_at=issued_at,
            effective_at=effective_at,
            payload={
                "capability_reference": capability_reference,
                "provenance": provenance,
                "source_reference": source_reference,
                "evidence_refs": list(evidence_refs),
                "valid_from": valid_from,
                "expires_at": expires_at,
            },
            auth=auth,
        )

    def declare_resource(
        self,
        *,
        application_id: str,
        resource_id: str,
        provenance: str,
        source_reference: str,
        evidence_refs: Tuple[str, ...],
        valid_from: str,
        expires_at: str,
        command_key: str,
        actor: str,
        issued_at: str,
        effective_at: str,
        auth: CommandAuth,
    ) -> OnboardingCommandOutcome:
        return self._execute(
            application_id=application_id,
            command_kind=OnboardingCommandKind.DECLARE_RESOURCE,
            command_key=command_key,
            actor=actor,
            issued_at=issued_at,
            effective_at=effective_at,
            payload={
                "resource_id": resource_id,
                "provenance": provenance,
                "source_reference": source_reference,
                "evidence_refs": list(evidence_refs),
                "valid_from": valid_from,
                "expires_at": expires_at,
            },
            auth=auth,
        )

    def withdraw_declaration(
        self,
        *,
        application_id: str,
        declaration_id: str,
        command_key: str,
        actor: str,
        issued_at: str,
        effective_at: str,
        auth: CommandAuth,
    ) -> OnboardingCommandOutcome:
        return self._execute(
            application_id=application_id,
            command_kind=OnboardingCommandKind.WITHDRAW_DECLARATION,
            command_key=command_key,
            actor=actor,
            issued_at=issued_at,
            effective_at=effective_at,
            payload={"declaration_id": declaration_id},
            auth=auth,
        )

    def bind_commercial_profile(
        self,
        *,
        application_id: str,
        service_profile_ref: str,
        commercial_policy_ref: str,
        settlement_reference: str,
        evidence_refs: Tuple[str, ...],
        command_key: str,
        actor: str,
        issued_at: str,
        effective_at: str,
        auth: CommandAuth,
    ) -> OnboardingCommandOutcome:
        return self._execute(
            application_id=application_id,
            command_kind=OnboardingCommandKind.BIND_COMMERCIAL_PROFILE,
            command_key=command_key,
            actor=actor,
            issued_at=issued_at,
            effective_at=effective_at,
            payload={
                "service_profile_ref": service_profile_ref,
                "commercial_policy_ref": commercial_policy_ref,
                "settlement_reference": settlement_reference,
                "evidence_refs": list(evidence_refs),
            },
            auth=auth,
        )

    def evaluate_eligibility(
        self,
        *,
        application_id: str,
        policy_decision: PolicyDecision,
        eligibility_decision: DecisionRecord,
        command_key: str,
        actor: str,
        issued_at: str,
        effective_at: str,
        auth: CommandAuth,
    ) -> OnboardingCommandOutcome:
        return self._execute(
            application_id=application_id,
            command_kind=OnboardingCommandKind.EVALUATE_ELIGIBILITY,
            command_key=command_key,
            actor=actor,
            issued_at=issued_at,
            effective_at=effective_at,
            payload={
                "policy_decision": policy_decision_document(policy_decision),
                "eligibility_decision": eligibility_decision_document(eligibility_decision),
            },
            auth=auth,
        )

    def propose_federation(
        self,
        *,
        application_id: str,
        peer_domain_id: str,
        peer_identity_reference: str,
        declared_scopes: Tuple[str, ...],
        valid_from: str,
        valid_until: str,
        command_key: str,
        actor: str,
        issued_at: str,
        effective_at: str,
        audit_requirements: Tuple[Tuple[str, str], ...] = (),
        policy_decision: Optional[PolicyDecision] = None,
        auth: CommandAuth,
    ) -> OnboardingCommandOutcome:
        settlement_reference = ""
        projection = self._state.get(application_id)
        if projection is not None:
            for binding_id in sorted(projection.bindings):
                settlement_reference = projection.bindings[binding_id].settlement_reference
                break
        payload = {
            "peer_domain_id": peer_domain_id,
            "peer_identity_reference": peer_identity_reference,
            "declared_scopes": list(declared_scopes),
            "valid_from": valid_from,
            "valid_until": valid_until,
            "audit_requirements": [
                {"key": key, "value": value} for key, value in audit_requirements
            ],
            "settlement_policy_reference": settlement_reference,
        }
        if policy_decision is not None:
            payload["policy_decision"] = policy_decision_document(policy_decision)
        return self._execute(
            application_id=application_id,
            command_kind=OnboardingCommandKind.PROPOSE_FEDERATION,
            command_key=command_key,
            actor=actor,
            issued_at=issued_at,
            effective_at=effective_at,
            payload=payload,
            auth=auth,
        )

    def accept_federation(
        self,
        *,
        application_id: str,
        peer_key_material: bytes,
        scopes: Tuple[str, ...] = (),
        command_key: str,
        actor: str,
        issued_at: str,
        effective_at: str,
        policy_decision: Optional[PolicyDecision] = None,
    ) -> OnboardingCommandOutcome:
        """Accept one federation proposal AS THE PEER DOMAIN'S OPERATOR.

        DEC-0096 W057-R1-P0-002: ``actor`` must be the RELATIONSHIP's
        peer domain's registered operator (the WORK-015 authority's
        own operator binding) and ``peer_key_material`` is the peer
        operator's key proof, presented at execute time only (never
        stored or journaled; its fingerprint is constant-time compared
        against the peer domain's registered ``identity_public_key``).
        The proposing application's operator, scoped credentials, and
        key proof are the WRONG authority for acceptance -- proposer
        self-acceptance and wrong-peer acceptance fail closed, and the
        deterministic half of this authorization is re-derived by the
        recovery fold (a journal-forged acceptance is tamper).
        """
        payload = {"scopes": list(scopes)}
        if policy_decision is not None:
            payload["policy_decision"] = policy_decision_document(policy_decision)
        return self._execute(
            application_id=application_id,
            command_kind=OnboardingCommandKind.ACCEPT_FEDERATION,
            command_key=command_key,
            actor=actor,
            issued_at=issued_at,
            effective_at=effective_at,
            payload=payload,
            auth=CommandAuth(key_material=peer_key_material),
        )

    def activate_membership(
        self,
        *,
        application_id: str,
        command_key: str,
        actor: str,
        issued_at: str,
        effective_at: str,
        auth: CommandAuth,
    ) -> OnboardingCommandOutcome:
        return self._execute(
            application_id=application_id,
            command_kind=OnboardingCommandKind.ACTIVATE_MEMBERSHIP,
            command_key=command_key,
            actor=actor,
            issued_at=issued_at,
            effective_at=effective_at,
            payload={},
            auth=auth,
        )

    def suspend_membership(
        self,
        *,
        application_id: str,
        command_key: str,
        actor: str,
        issued_at: str,
        effective_at: str,
        auth: CommandAuth,
    ) -> OnboardingCommandOutcome:
        return self._execute(
            application_id=application_id,
            command_kind=OnboardingCommandKind.SUSPEND_MEMBERSHIP,
            command_key=command_key,
            actor=actor,
            issued_at=issued_at,
            effective_at=effective_at,
            payload={},
            auth=auth,
        )

    def resume_membership(
        self,
        *,
        application_id: str,
        command_key: str,
        actor: str,
        issued_at: str,
        effective_at: str,
        auth: CommandAuth,
    ) -> OnboardingCommandOutcome:
        return self._execute(
            application_id=application_id,
            command_kind=OnboardingCommandKind.RESUME_MEMBERSHIP,
            command_key=command_key,
            actor=actor,
            issued_at=issued_at,
            effective_at=effective_at,
            payload={},
            auth=auth,
        )

    def cancel_proposal(
        self,
        *,
        application_id: str,
        command_key: str,
        actor: str,
        issued_at: str,
        effective_at: str,
        auth: CommandAuth,
    ) -> OnboardingCommandOutcome:
        return self._execute(
            application_id=application_id,
            command_kind=OnboardingCommandKind.CANCEL_PROPOSAL,
            command_key=command_key,
            actor=actor,
            issued_at=issued_at,
            effective_at=effective_at,
            payload={},
            auth=auth,
        )

    def revoke_application(
        self,
        *,
        application_id: str,
        reason: str,
        command_key: str,
        actor: str,
        issued_at: str,
        effective_at: str,
        auth: CommandAuth,
    ) -> OnboardingCommandOutcome:
        return self._execute(
            application_id=application_id,
            command_kind=OnboardingCommandKind.REVOKE_APPLICATION,
            command_key=command_key,
            actor=actor,
            issued_at=issued_at,
            effective_at=effective_at,
            payload={"reason": reason},
            auth=auth,
        )

    def offboard_application(
        self,
        *,
        application_id: str,
        reason: str,
        command_key: str,
        actor: str,
        issued_at: str,
        effective_at: str,
        auth: CommandAuth,
    ) -> OnboardingCommandOutcome:
        return self._execute(
            application_id=application_id,
            command_kind=OnboardingCommandKind.OFFBOARD_APPLICATION,
            command_key=command_key,
            actor=actor,
            issued_at=issued_at,
            effective_at=effective_at,
            payload={"reason": reason},
            auth=auth,
        )

    # -- generic surface (adversarial/direct command execution) -------

    def execute_command(
        self,
        *,
        application_id: str,
        command_kind: str,
        command_key: str,
        actor: str,
        issued_at: str,
        effective_at: str,
        payload: Mapping[str, Any],
        auth: Optional[CommandAuth] = None,
    ) -> OnboardingCommandOutcome:
        """Direct command execution with a raw payload (the battery's
        adversarial surface; identical semantics to the typed
        surface)."""
        return self._execute(
            application_id=application_id,
            command_kind=command_kind,
            command_key=command_key,
            actor=actor,
            issued_at=issued_at,
            effective_at=effective_at,
            payload=dict(payload),
            auth=auth,
        )


__all__ = [
    "CommandAuth",
    "OnboardingCommandOutcome",
    "ProviderOnboardingService",
    "eligibility_decision_document",
    "eligibility_decision_from_document",
    "policy_decision_document",
    "policy_decision_from_document",
    "verify_policy_decision_tamper_evidence",
]
