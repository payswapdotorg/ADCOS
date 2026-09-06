"""ADCOS provider onboarding journal and state (WORK-057).

The onboarding state is a DETERMINISTIC FOLD over an append-only
command journal (the eligibility/developer-API discipline:
construction-is-recovery -- the fold IS the state). Durable recovery
after an interrupted onboarding means exactly this: re-folding the
journaled command prefix on a fresh federation store reproduces the
byte-identical onboarding state, and resuming from the watermark
never duplicates a domain, a relationship, a grant, or a membership.

Journal discipline (the resource-store merge semantics applied to
commands):

1. an exact duplicate command (identical content-derived id) is
   idempotent (``duplicate`` -- no state change, no second
   federation mutation);
2. a stale sequence (below the per-application watermark) fails
   closed (``replay-stale``);
3. the current watermark with different content fails closed
   (``sequence-conflict``);
4. a sequence above the next slot fails closed (``sequence-gap``);
5. every decision is a pure function of (watermark, accepted command
   ids, content) -- never wall clock, randomness, or thread
   scheduling.

The journal never carries secrets, key material, or decision
objects: only public data, opaque references, and digests (LOCK-023
discipline; enforced again at record construction).
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from protocol.canonicalization import CanonicalizationError, canonical_json_bytes

from .onboarding_model import (
    COMMAND_STATUS_APPENDED,
    ProviderApplication,
    OnboardingCommandRecord,
    OnboardingCredential,
    OnboardingDeclaration,
    OnboardingError,
    OnboardingProfileBinding,
    OnboardingReason,
    _reject_secret_material,
)

# ----------------------------------------------------------------------
# Append outcomes
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class JournalAppendOutcome:
    ok: bool
    code: str
    detail: str
    record: Optional[OnboardingCommandRecord]

    @property
    def duplicate(self) -> bool:
        return self.code == OnboardingReason.DUPLICATE


# ----------------------------------------------------------------------
# OnboardingJournal (append-only; memory or file-backed)
# ----------------------------------------------------------------------


class OnboardingJournal:
    """Append-only onboarding command journal.
    Thread-safe: appends are serialized under one lock; the record
    list is never mutated except by append. A file-backed journal
    additionally persists each accepted record as one canonical JSON
    line (single-writer discipline; deterministic bytes on disk).

    Sequence discipline: the per-application sequence is
    JOURNAL-ASSIGNED (a record appended with sequence 0 receives
    watermark+1); a directly supplied sequence must occupy exactly
    the next slot (below it is a stale replay, above it a gap -- both
    fail closed). An exact duplicate command id is idempotent and is
    never journaled twice. Command-key ownership: the first APPENDED
    record with a given (application, command_key) owns that key; a
    later APPENDED record with the same key but different content
    fails closed (``sequence-conflict``). REJECTED audit records do
    not claim key ownership (an adversarial attempt recorded under a
    key never blocks the legitimate command that key names).
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: List[OnboardingCommandRecord] = []
        self._by_id: Dict[str, OnboardingCommandRecord] = {}
        self._key_owner: Dict[str, str] = {}
        self._watermarks: Dict[str, int] = {}
        self._loading = False

    # -- append -------------------------------------------------------

    def append(self, record: OnboardingCommandRecord) -> JournalAppendOutcome:
        if not isinstance(record, OnboardingCommandRecord):
            return JournalAppendOutcome(
                False,
                OnboardingReason.INVALID_INPUT,
                "journal records must be OnboardingCommandRecord values",
                None,
            )
        with self._lock:
            existing = self._by_id.get(record.command_id)
            if existing is not None:
                return JournalAppendOutcome(
                    True,
                    OnboardingReason.DUPLICATE,
                    "command %r is an exact duplicate of the journaled command at "
                    "sequence %d with status %r (idempotent; no state change, not "
                    "re-journaled)"
                    % (record.command_id, existing.sequence, existing.status),
                    existing,
                )
            watermark = self._watermarks.get(record.application_id, 0)
            if record.sequence == 0:
                record = _with_sequence(record, watermark + 1)
            elif record.sequence != watermark + 1:
                if record.sequence <= watermark:
                    return JournalAppendOutcome(
                        False,
                        OnboardingReason.REPLAY_STALE,
                        "command sequence %d is at or below the application watermark "
                        "%d (stale replay; fail closed)" % (record.sequence, watermark),
                        None,
                    )
                return JournalAppendOutcome(
                    False,
                    OnboardingReason.SEQUENCE_GAP,
                    "command sequence %d skips past the next slot %d (gap; fail closed)"
                    % (record.sequence, watermark + 1),
                    None,
                )
            if record.status == COMMAND_STATUS_APPENDED:
                key_slot = record.application_id + "\x00" + record.command_key
                owner = self._key_owner.get(key_slot)
                if owner is not None and owner != record.command_id:
                    return JournalAppendOutcome(
                        False,
                        OnboardingReason.SEQUENCE_CONFLICT,
                        "command key %r is already owned by a different command %r "
                        "(same key, different content; fail closed)"
                        % (record.command_key, owner),
                        None,
                    )
                self._key_owner[key_slot] = record.command_id
            self._records.append(record)
            self._by_id[record.command_id] = record
            self._watermarks[record.application_id] = record.sequence
            self._persist(record)
            return JournalAppendOutcome(
                True,
                record.status,
                "command %r appended at sequence %d with status %r"
                % (record.command_id, record.sequence, record.status),
                record,
            )

    def _persist(self, record: OnboardingCommandRecord) -> None:
        """Hook for file-backed journals (no-op in memory)."""
    # -- queries ------------------------------------------------------

    def records(self) -> Tuple[OnboardingCommandRecord, ...]:
        with self._lock:
            return tuple(self._records)

    def records_for(self, application_id: str) -> Tuple[OnboardingCommandRecord, ...]:
        with self._lock:
            return tuple(
                record
                for record in self._records
                if record.application_id == application_id
            )

    def watermark(self, application_id: str) -> int:
        with self._lock:
            return self._watermarks.get(application_id, 0)

    def get(self, command_id: str) -> Optional[OnboardingCommandRecord]:
        with self._lock:
            return self._by_id.get(command_id)

    def key_owner(self, application_id: str, command_key: str) -> Optional[str]:
        """The command id that owns (application, command_key), if an
        APPENDED record claimed it."""
        with self._lock:
            return self._key_owner.get(application_id + "\x00" + command_key)

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)

    # -- deterministic serialization ----------------------------------

    def journal_document(self) -> List[Dict[str, Any]]:
        return [record.to_dict() for record in self.records()]

    def journal_digest(self) -> str:
        """Content-derived digest over the complete journal (stable
        across processes; PYTHONHASHSEED-safe)."""
        try:
            payload = canonical_json_bytes(self.journal_document())
        except CanonicalizationError as error:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "journal is not canonicalizable: %s" % (error,),
            ) from None
        return "sha256:" + hashlib.sha256(payload).hexdigest()

    def to_mapping(self) -> Dict[str, Any]:
        return {"journal_kind": "adcos:provider-onboarding-journal",
                "records": self.journal_document()}

    @classmethod
    def from_mapping(cls, data: object) -> "OnboardingJournal":
        if not isinstance(data, Mapping):
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "journal mapping must be a mapping"
            )
        _reject_secret_material(dict(data), "journal mapping")
        records = data.get("records", ())
        journal = cls()
        for item in records:
            record = OnboardingCommandRecord.from_mapping(item)
            outcome = journal.append(record)
            if not outcome.ok:
                raise OnboardingError(
                    OnboardingReason.INVALID_INPUT,
                    "journal record %r is not appendable: %s"
                    % (record.command_id, outcome.detail),
                )
        return journal


MappingLike = Dict[str, Any]

#: alias used by the service layer to distinguish the fold state
#: (this module) from the onboarding lifecycle-state constants class
#: of the same name in onboarding_model
OnboardingFoldState = None


def _with_sequence(
    record: OnboardingCommandRecord, sequence: int
) -> OnboardingCommandRecord:
    """Rebuild a record with the journal-assigned sequence (the
    content-derived command id deliberately excludes the sequence, so
    the identity is unchanged)."""
    return OnboardingCommandRecord(
        command_id=record.command_id,
        application_id=record.application_id,
        command_kind=record.command_kind,
        command_key=record.command_key,
        sequence=sequence,
        issued_at=record.issued_at,
        effective_at=record.effective_at,
        actor=record.actor,
        credential_reference=record.credential_reference,
        payload=record.payload,
        status=record.status,
        reason_code=record.reason_code,
        detail=record.detail,
    )


class FileOnboardingJournal(OnboardingJournal):
    """File-backed journal: each accepted record is persisted as one
    canonical JSON line (append-only, single writer, flushed per
    record). Recovery after an interrupted write re-loads every
    complete line; a truncated final line (a torn write) fails closed
    rather than being silently interpreted."""

    def __init__(self, path: str) -> None:
        super().__init__()
        if not isinstance(path, str) or not path:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT, "journal path must be a non-empty string"
            )
        self._path = path
        if os.path.exists(path):
            self._loading = True
            try:
                self._load_lines()
            finally:
                self._loading = False

    def _persist(self, record: OnboardingCommandRecord) -> None:
        if self._loading:
            return
        line = canonical_json_bytes(record.to_dict()).decode("utf-8")
        with open(self._path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def _load_lines(self) -> None:
        with open(self._path, "r", encoding="utf-8") as handle:
            lines = handle.read().split("\n")
        if lines and lines[-1] == "":
            lines = lines[:-1]
        elif lines:
            # torn final line: an interrupted append -- fail closed on
            # the incomplete record but recover every complete prefix line
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "journal file %r ends with a torn (interrupted) record line; "
                "the prefix is recoverable, the partial line is not interpretable"
                % (self._path,),
            )
        for line in lines:
            try:
                document = json.loads(line)
            except ValueError as error:
                raise OnboardingError(
                    OnboardingReason.INVALID_INPUT,
                    "journal file %r contains a malformed line: %s" % (self._path, error),
                ) from None
            record = OnboardingCommandRecord.from_mapping(document)
            outcome = super().append(record)
            if not outcome.ok:
                raise OnboardingError(
                    OnboardingReason.INVALID_INPUT,
                    "journal file %r contains a non-appendable record: %s"
                    % (self._path, outcome.detail),
                ) from None


# ----------------------------------------------------------------------
# Fold state (per-application projection)
# ----------------------------------------------------------------------


@dataclass
class ApplicationProjection:
    """Everything the fold knows about one onboarding application.

    The projection carries only public/reference data: credentials
    appear in their secret-free public form, certifications as their
    public documents, and membership as federation references."""

    application: ProviderApplication
    credentials: Dict[str, OnboardingCredential] = field(default_factory=dict)
    declarations: Dict[str, OnboardingDeclaration] = field(default_factory=dict)
    bindings: Dict[str, OnboardingProfileBinding] = field(default_factory=dict)
    certifications: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    command_log: List[OnboardingCommandRecord] = field(default_factory=list)
    next_command_sequence: int = 1
    next_credential_sequence: int = 1
    next_declaration_sequence: int = 1
    membership_status: str = ""
    membership_grant_ids: Tuple[str, ...] = ()
    activated_at: str = ""
    suspended_at: str = ""
    revoked_at: str = ""
    offboarded_at: str = ""
    cancelled_at: str = ""
    policy_decision_ref: str = ""
    eligibility_decision_ref: str = ""

    # -- queries ------------------------------------------------------

    def active_credentials_at(self, evaluation_instant: str) -> Tuple[OnboardingCredential, ...]:
        return tuple(
            self.credentials[reference]
            for reference in sorted(self.credentials)
            if self.credentials[reference].is_active_at(evaluation_instant)
        )

    def credential_with_scope(
        self, scope: str, evaluation_instant: str
    ) -> Tuple[Optional[OnboardingCredential], str]:
        """The first (deterministically, by reference) credential that
        is active and covers ``scope``; with a reason code when none
        applies (fail-closed diagnostics: revoked vs expired vs
        scope)."""
        candidates = [
            self.credentials[reference]
            for reference in sorted(self.credentials)
            if self.credentials[reference].scope == scope
        ]
        if not candidates:
            return None, OnboardingReason.CREDENTIAL_INVALID
        active = [credential for credential in candidates if credential.status == "active"]
        if not active:
            return None, OnboardingReason.CREDENTIAL_REVOKED_CODE
        instant_valid = [
            credential
            for credential in active
            if credential.valid_from <= evaluation_instant <= credential.valid_until
        ]
        if not instant_valid:
            return None, OnboardingReason.CREDENTIAL_EXPIRED
        return instant_valid[0], ""

    def certified_adapters(self) -> Tuple[Dict[str, Any], ...]:
        return tuple(
            self.certifications[certification_id]
            for certification_id in sorted(self.certifications)
            if self.certifications[certification_id].get("verdict") == "certified"
        )

    def live_declarations(self, evaluation_instant: str) -> Tuple[OnboardingDeclaration, ...]:
        return tuple(
            self.declarations[declaration_id]
            for declaration_id in sorted(self.declarations)
            if self.declarations[declaration_id].is_live_at(evaluation_instant)
        )


@dataclass
class OnboardingState:
    """The complete fold projection (applications by id)."""

    applications: Dict[str, ApplicationProjection] = field(default_factory=dict)

    def get(self, application_id: str) -> Optional[ApplicationProjection]:
        return self.applications.get(application_id)

    def require(self, application_id: str) -> ApplicationProjection:
        projection = self.applications.get(application_id)
        if projection is None:
            raise OnboardingError(
                OnboardingReason.UNKNOWN_APPLICATION,
                "onboarding application %r is not registered" % (application_id,),
            )
        return projection

    def application_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self.applications))

    def snapshot(self) -> Dict[str, Any]:
        """Deterministic complete snapshot (byte-identical across runs
        and processes for identical journals; PYTHONHASHSEED-safe)."""
        applications = []
        for application_id in self.application_ids():
            projection = self.applications[application_id]
            application_dict = projection.application.to_dict()
            application_dict["onboarding"] = {
                "credentials": [
                    projection.credentials[reference].public_dict()
                    for reference in sorted(projection.credentials)
                ],
                "certifications": [
                    projection.certifications[certification_id]
                    for certification_id in sorted(projection.certifications)
                ],
                "declarations": [
                    projection.declarations[declaration_id].to_dict()
                    for declaration_id in sorted(projection.declarations)
                ],
                "profile_bindings": [
                    projection.bindings[binding_id].to_dict()
                    for binding_id in sorted(projection.bindings)
                ],
                "membership": {
                    "status": projection.membership_status,
                    "grant_ids": list(projection.membership_grant_ids),
                    "activated_at": projection.activated_at,
                    "suspended_at": projection.suspended_at,
                    "revoked_at": projection.revoked_at,
                    "offboarded_at": projection.offboarded_at,
                    "cancelled_at": projection.cancelled_at,
                },
                "decision_references": {
                    "policy_decision": projection.policy_decision_ref,
                    "eligibility_decision": projection.eligibility_decision_ref,
                },
                "sequences": {
                    "next_command_sequence": projection.next_command_sequence,
                    "next_credential_sequence": projection.next_credential_sequence,
                    "next_declaration_sequence": projection.next_declaration_sequence,
                },
                "command_count": len(projection.command_log),
            }
            applications.append(application_dict)
        return {
            "state_kind": "adcos:provider-onboarding-state",
            "applications": applications,
        }

    def state_digest(self) -> str:
        try:
            payload = canonical_json_bytes(self.snapshot())
        except CanonicalizationError as error:
            raise OnboardingError(
                OnboardingReason.INVALID_INPUT,
                "state is not canonicalizable: %s" % (error,),
            ) from None
        return "sha256:" + hashlib.sha256(payload).hexdigest()


#: the fold state under its service-layer alias (distinct from the
#: onboarding lifecycle-state constants class in onboarding_model)
OnboardingFoldState = OnboardingState


__all__ = [
    "ApplicationProjection",
    "FileOnboardingJournal",
    "JournalAppendOutcome",
    "OnboardingFoldState",
    "OnboardingJournal",
    "OnboardingState",
]
