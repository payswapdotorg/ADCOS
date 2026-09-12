"""ADCOS credential-lifecycle operation journal (M018 — Credential
and Key Lifecycle Operations).

The deterministic, ordered, gapless, IDEMPOTENT, replayable journal
of one node's credential-lifecycle operations (rotation drills,
revocations, the emergency path, propagation rounds, inventory
audits).  The journal discipline conventions of the accepted
``resilience/journal.py`` and ``localfirst/journal.py`` surfaces are
consumed as CONVENTIONS (ordered, gapless, conflict-free,
kind-disciplined, tamper-evident identities, construction-is-
recovery) — this is its OWN typed surface, never a fork.

The fold is the sole writer of the replayed view: ``fold()`` re-
derives the ADMITTED-SET TIMELINE purely from the journaled records
and MECHANICALLY enforces the zero-coverage-gap invariants at replay:

- positions 1..N, gapless (a gap is journal divergence);
- one operation identity per position (a different record under a
  used id fails closed; the IDENTICAL record replays idempotently);
- CONTINUITY: every record's ``before_admitted`` equals its
  predecessor's ``after_admitted`` — an unrecorded admitted-set
  transition between journaled operations is journal divergence
  (there is NO operation window the journal does not account for);
- the per-kind atomicity kernels (the exact single flip / single
  removal — verified at construction AND re-verified by the fold).

Determinism (LOCK-119): appended records carry content-derived
POSITION-INDEPENDENT identities; the append is idempotent (a retried
operation re-derives the same identity and never double-applies) and
ATOMIC (a rejected append leaves the journal byte-identical); the
digest is byte-stable across runs and hash seeds; injected instants
only.
"""

from __future__ import annotations

import hashlib
from typing import Dict, Iterable, List, Tuple

from protocol.canonicalization import canonical_json_bytes

from .errors import CredentialLifecycleError, CredentialLifecycleReason
from .model import (
    LifecycleFold,
    LifecycleOperationRecord,
)

__all__ = ["LifecycleJournal", "fold_operations"]


class LifecycleJournal:
    """One node's append-only deterministic lifecycle-operation
    journal (ordered, gapless, idempotent, replayable, tamper-
    evident).  Construction-is-recovery: ``from_records`` rebuilds
    the identical journal."""

    def __init__(self, node_id: str) -> None:
        if not isinstance(node_id, str) or not node_id:
            raise CredentialLifecycleError(
                CredentialLifecycleReason.INVALID_INPUT,
                "a lifecycle journal is node-scoped (node_id must be a "
                "non-empty string)",
            )
        self._node_id = node_id
        self._records: List[LifecycleOperationRecord] = []

    # -- the read surface ---------------------------------------------------

    @property
    def node_id(self) -> str:
        return self._node_id

    def operations(self) -> Tuple[LifecycleOperationRecord, ...]:
        return tuple(self._records)

    def __len__(self) -> int:
        return len(self._records)

    def operation(self, operation_id: str) -> LifecycleOperationRecord:
        for record in self._records:
            if record.operation_id == operation_id:
                return record
        raise CredentialLifecycleError(
            CredentialLifecycleReason.LIFECYCLE_ILLEGAL,
            "unknown lifecycle operation %r on this journal" % (operation_id,),
        )

    # -- the append surface (idempotent, atomic) -----------------------------

    def append(
        self, record: LifecycleOperationRecord
    ) -> LifecycleOperationRecord:
        """Append one operation record at the next gapless position.

        IDEMPOTENT: a record whose content identity already exists at
        its exact position replays as a no-op returning the stored
        record (a retried operation never double-applies).  A
        DIFFERENT record under a used identity fails closed, and any
        rejection leaves the journal byte-identical (atomic append).
        """
        if not isinstance(record, LifecycleOperationRecord):
            raise CredentialLifecycleError(
                CredentialLifecycleReason.INVALID_INPUT,
                "append requires a LifecycleOperationRecord",
            )
        if record.node_id != self._node_id:
            raise CredentialLifecycleError(
                CredentialLifecycleReason.ID_MISMATCH,
                "operation record for node %r cannot be journaled on the "
                "journal of node %r (attribution fails closed)"
                % (record.node_id, self._node_id),
            )
        expected_sequence = len(self._records) + 1
        for stored in self._records:
            if stored.operation_id == record.operation_id:
                if stored.to_dict() == record.to_dict():
                    return stored
                raise CredentialLifecycleError(
                    CredentialLifecycleReason.JOURNAL_DIVERGENCE,
                    "operation identity %r already exists with different "
                    "content (a distinct operation never reuses an identity)"
                    % (record.operation_id,),
                )
        if record.sequence != expected_sequence:
            raise CredentialLifecycleError(
                CredentialLifecycleReason.JOURNAL_DIVERGENCE,
                "operation sequence %d does not occupy the next gapless "
                "journal position %d (gapless positions only)"
                % (record.sequence, expected_sequence),
            )
        self._validate_continuity(record)
        self._records.append(record)
        return record

    def _validate_continuity(
        self, record: LifecycleOperationRecord
    ) -> None:
        """The fold discipline on append: the record's before-set is
        exactly the current journaled after-set (an unrecorded
        admitted-set transition is divergence — there is no operation
        window the journal does not account for)."""
        if not self._records:
            return
        current = self._records[-1].after_admitted
        if record.before_admitted != current:
            raise CredentialLifecycleError(
                CredentialLifecycleReason.JOURNAL_DIVERGENCE,
                "operation %d records before_admitted %s but the journal's "
                "current admitted set is %s (an UNRECORDED admitted-set "
                "transition — the zero-coverage-gap discipline requires "
                "every transition journaled)"
                % (record.sequence, list(record.before_admitted), list(current)),
            )

    # -- the replay surface (the fold) -----------------------------------------

    def fold(self) -> LifecycleFold:
        """The deterministic replay: re-derive the admitted-set
        timeline from the journaled records, re-verifying every
        mechanical invariant (gapless positions, unique identities,
        continuity, the per-kind atomicity kernels — re-verified at
        construction and again here).  Construction-is-recovery."""
        return fold_operations(self._records, node_id=self._node_id)

    def admitted_set_at(self, at_instant: str) -> Tuple[str, ...]:
        return self.fold().admitted_set_at(at_instant)

    # -- the canonical snapshot surface ------------------------------------------

    def digest(self) -> str:
        """The byte-stable content digest of the whole journal
        (PYTHONHASHSEED-safe; identical journals -> identical
        digests)."""
        return hashlib.sha256(canonical_json_bytes({
            "node_id": self._node_id,
            "operations": [record.to_dict() for record in self._records],
        })).hexdigest()

    def to_records(self) -> Tuple[Dict[str, object], ...]:
        return tuple(record.to_dict() for record in self._records)

    @classmethod
    def from_records(
        cls, records: Iterable[object], *, node_id: str
    ) -> "LifecycleJournal":
        """Construction-is-recovery: rebuild the identical journal from
        canonical record dicts (every derived identity re-verified)."""
        journal = cls(node_id=node_id)
        for data in records:
            journal.append(LifecycleOperationRecord.from_dict(data))
        return journal

    def snapshot_dict(self) -> Dict[str, object]:
        return {"node_id": self._node_id, "operations": list(self.to_records())}


def fold_operations(
    records: Iterable[LifecycleOperationRecord], *, node_id: str
) -> LifecycleFold:
    """The pure fold over a record sequence: the admitted-set timeline
    plus the mechanical re-verification (gapless positions, unique
    identities, continuity).  Used by the journal fold and directly by
    callers holding replayed record sequences."""
    ordered: List[LifecycleOperationRecord] = []
    seen: Dict[str, LifecycleOperationRecord] = {}
    timeline: List[Tuple[str, ...]] = []
    current: Tuple[str, ...] = ()
    problems: List[str] = []
    for record in records:
        if not isinstance(record, LifecycleOperationRecord):
            raise CredentialLifecycleError(
                CredentialLifecycleReason.INVALID_INPUT,
                "the fold consumes LifecycleOperationRecord objects only",
            )
        if record.node_id != node_id:
            raise CredentialLifecycleError(
                CredentialLifecycleReason.ID_MISMATCH,
                "record for node %r folded onto the journal of node %r"
                % (record.node_id, node_id),
            )
        if record.sequence != len(ordered) + 1:
            problems.append(
                "position %d does not occupy the next gapless slot %d"
                % (record.sequence, len(ordered) + 1)
            )
            break
        if record.operation_id in seen:
            problems.append(
                "operation identity %r appears twice" % (record.operation_id,)
            )
            break
        if ordered and record.before_admitted != current:
            problems.append(
                "operation %d records an unrecorded admitted-set transition "
                "(%s -> %s)" % (record.sequence, list(current),
                                list(record.before_admitted))
            )
            break
        seen[record.operation_id] = record
        ordered.append(record)
        current = record.after_admitted
        timeline.append(current)
    if problems:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.JOURNAL_DIVERGENCE,
            "the lifecycle journal failed its replay fold: %s" % problems[0],
        )
    initial = ordered[0].before_admitted if ordered else ()
    digest = hashlib.sha256(canonical_json_bytes({
        "node_id": node_id,
        "operations": [record.to_dict() for record in ordered],
    })).hexdigest()
    return LifecycleFold(
        node_id=node_id,
        records=tuple(ordered),
        admitted_timeline=tuple(timeline),
        initial_admitted=initial,
        digest=digest,
    )
