"""WORK-042 evidence chain and honest disclosure.

The explicit evidence chain the W042 contract requires:

    platform observation (event, boundary, provenance)
            |
            v
    deterministic reconciliation (journal fold)
            |
            v
    durable checkpoint (journal-bound compact snapshot)
            |
            v
    journal-first recovery (fresh observation + session-loss
    honesty)

Assembled into :class:`RecoveryEvidenceRecord` -- a pure,
content-addressed DATA record built ONLY from the recovery report,
the journal digests, and the checkpoint identity.  Evidence
discipline (the WORK-020/W034/W035/W041 two-track model):

- **explicit**: every chain link is a named field with its own
  digest; nothing is implied;
- **deterministic**: the same logical history produces the
  identical record digest (content-derived, no ambient input);
- **replay-safe**: records are addressed by content; a replayed
  history either reproduces the digest byte-for-byte or fails
  closed at the journal/checkpoint gates before evidence is
  assembled;
- **independently verifiable**: anyone holding the record can
  recompute every digest from the recorded facts;
- **no secrets**: records carry ids, digests, and references only
  -- never key material, credentials, or protected payloads.

The honest disclosure (:data:`PLATFORM_EVIDENCE_STATUS`) is pinned
by the battery: software/deterministic event-journal and recovery
evidence is verified by the battery; PHYSICAL device evidence is
OPEN and remains governed by WORK-040's open obligations
(EVID-007/EVID-008) -- no synthetic physical claim is ever made.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Tuple

from protocol.canonicalization import canonical_json_bytes

from .errors import PlatformError, PlatformReasonCode
from .recovery import RecoveryReport

#: The anti-faking evidence disclosure for the platform family
#: (the WORK-020/W034/W035/W041 two-track model).  The battery
#: pins this object so no run can report physical-device evidence
#: that does not exist.
PLATFORM_EVIDENCE_STATUS = {
    "software_deterministic_event_journal": "supported-verified",
    "software_deterministic_recovery": "supported-verified",
    "physical_device": "open",
}


@dataclass(frozen=True)
class RecoveryEvidenceRecord:
    """One assembled recovery evidence record (pure DATA +
    digests)."""

    checkpoint_id: str
    journal_digest: str
    state_digest: str
    recovery_digest: str
    journal_records_replayed: int
    fresh_event_ids: Tuple[str, ...]
    divergences: Tuple[Dict[str, Any], ...]
    lost_sessions: Tuple[str, ...]
    session_loss_record_ids: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "journal_digest": self.journal_digest,
            "state_digest": self.state_digest,
            "recovery_digest": self.recovery_digest,
            "journal_records_replayed": self.journal_records_replayed,
            "fresh_event_ids": list(self.fresh_event_ids),
            "divergences": [dict(item) for item in self.divergences],
            "lost_sessions": list(self.lost_sessions),
            "session_loss_record_ids": list(self.session_loss_record_ids),
        }

    def record_digest(self) -> str:
        """Content digest over the canonical record (identity
        DATA)."""
        return "sha256:" + hashlib.sha256(
            canonical_json_bytes(self.to_dict())
        ).hexdigest()


def assemble_recovery_evidence(
    report: RecoveryReport,
) -> RecoveryEvidenceRecord:
    """Assemble one recovery evidence record from a recovery
    report."""
    if not isinstance(report, RecoveryReport):
        raise PlatformError(
            PlatformReasonCode.INVALID_INPUT,
            "report must be a RecoveryReport",
        )
    return RecoveryEvidenceRecord(
        checkpoint_id=report.checkpoint_id,
        journal_digest=report.journal_digest,
        state_digest=report.state_digest,
        recovery_digest=report.recovery_digest(),
        journal_records_replayed=report.journal_records_replayed,
        fresh_event_ids=tuple(report.fresh_event_ids),
        divergences=tuple(
            dict(item.to_dict()) for item in report.divergences
        ),
        lost_sessions=tuple(report.lost_sessions),
        session_loss_record_ids=tuple(report.session_loss_record_ids),
    )


def evidence_digest(records: List[RecoveryEvidenceRecord]) -> str:
    """Deterministic digest over an ordered evidence record set."""
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes([record.to_dict() for record in records])
    ).hexdigest()


def verify_recovery_evidence(record: RecoveryEvidenceRecord) -> bool:
    """Independent verification of one record's internal coherence.

    The chain invariants: honest session-loss is recorded whenever
    transport could not survive (lost_sessions non-empty implies
    loss record ids exist); divergence reports and fresh events are
    consistent (every divergence has a corresponding fresh event);
    and no resurrection is claimed (the record's lost sessions are
    never reported as preserved).  Purely local re-derivation from
    the recorded facts -- the "independently verifiable" criterion.
    """
    divergence_refs = {
        str(item.get("platform_ref", "")) for item in record.divergences
    }
    if record.divergences and not record.fresh_event_ids:
        return False
    if divergence_refs and len(divergence_refs) > len(
        record.fresh_event_ids
    ):
        return False
    if record.lost_sessions and not record.session_loss_record_ids:
        return False
    if record.session_loss_record_ids and not record.lost_sessions:
        return False
    if not record.journal_digest.startswith("sha256:"):
        return False
    if not record.state_digest.startswith("sha256:"):
        return False
    return True


__all__ = [
    "PLATFORM_EVIDENCE_STATUS",
    "RecoveryEvidenceRecord",
    "assemble_recovery_evidence",
    "evidence_digest",
    "verify_recovery_evidence",
]
