"""ADCOS local-first offline journal (M016 — Local-First and Offline
Operation).

The deterministic, replayable offline operation journal and its fold
(construction-is-recovery — the journal discipline conventions of the
accepted ``resilience/journal.py``, studied and consumed as CONVENTIONS:
ordered, gapless, conflict-free, kind/member-disciplined, tamper-
evident identities — this is its OWN typed surface, never a fork of
the runtime journal):

- :func:`fold_operations` — the pure deterministic fold of one
  partition episode's append-only record sequence onto its
  :class:`~localfirst.model.LocalState` snapshot.  The fold is the
  SOLE writer of local state (the journal appends validated records;
  the state is always the fold of the journal).  Fail-closed gates:

  1. the sequence starts with ``partition-entered`` at position 1, and
     the episode identity re-derives from the episode core (the owning
     contract, the base authority view, the opening instant, the
     opening provenance — tamper evidence);
  2. journal positions are gapless and conflict-free
     (``localfirst-journal-divergence``); every record attributes to
     the same episode and the same owning contract;
  3. the kind/shape chain is legal (the frozen kind-member rules;
     ``partition-exited`` is final and unique);
  4. — the CORE M016 discipline, MECHANICALLY ENFORVED — an ADMITTED
     admission decision always carries an instant INSIDE the authority
     freshness window it carries: a local state past its declared
     freshness bound NEVER silently authorizes, so a forged admitted
     record outside its window fails the fold as
     ``localfirst-journal-divergence`` (never a silent allow);
  5. an admitted subject is admitted at most ONCE per episode (a
     retry is idempotent by operation identity; a second admission of
     the same subject is a discipline violation and fails closed).

- :class:`OfflineJournal` — the deterministic store: atomic append
  (validated in full BEFORE any state changes; a rejected operation
  leaves the journal byte-identical), IDEMPOTENT append (an operation
  retried while partitioned derives the same content identity and
  returns the existing record — the same operation never
  double-applies), and ``from_records`` (construction-is-recovery: no
  state exists outside the fold).

Determinism (LOCK-119): the fold is pure and order-driven (no wall
clock, no randomness, no network, no secrets); the same record
sequence always folds to the byte-identical local state;
canonical-JSON round-trips with tamper-evident ids.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from protocol.temporal import parse_instant

from contracts import Provenance

from .errors import LocalFirstError, LocalFirstReason
from .model import (
    OfflineOperation,
    LocalState,
    derive_episode_id,
)

__all__ = [
    "fold_operations",
    "OfflineJournal",
]


def _require_record_sequence(
    records: object, label: str
) -> Tuple[OfflineOperation, ...]:
    if isinstance(records, (str, bytes)) or not isinstance(records, (tuple, list)):
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT, "%s must be a sequence of records" % label
        )
    for i, item in enumerate(records):
        if not isinstance(item, OfflineOperation):
            raise LocalFirstError(
                LocalFirstReason.INVALID_INPUT,
                "%s[%d] must be an OfflineOperation record (got %s)"
                % (label, i, type(item).__name__),
            )
    return tuple(records)


def fold_operations(
    records: object, *, label: str = "the offline journal"
) -> LocalState:
    """Fold one partition episode's append-only record sequence onto
    its :class:`~localfirst.model.LocalState` snapshot (the pure
    deterministic fold — construction-is-recovery).

    Fail-closed gates, in fold order:

    1. the sequence is non-empty and starts with ``partition-entered``
       at journal position 1, with the episode identity re-derived
       from the episode core (tamper evidence);
    2. journal positions are gapless and conflict-free
       (``localfirst-journal-divergence``); every record attributes to
       the same episode and the same owning contract;
    3. the kind/shape chain is legal (``partition-exited`` is final
       and unique — a record after the exit diverges);
    4. an ADMITTED admission's instant lies INSIDE the freshness window
       it carries (a local state past its declared freshness bound
       never silently authorizes — the forged silent-allow shape fails
       closed as journal divergence);
    5. an admitted subject is admitted at most once per episode.
    """
    sequence = _require_record_sequence(records, label)
    if not sequence:
        raise LocalFirstError(
            LocalFirstReason.INVALID_INPUT, "%s carries no records" % label
        )

    first = sequence[0]
    if first.kind != "partition-entered":
        raise LocalFirstError(
            LocalFirstReason.JOURNAL_DIVERGENCE,
            "%s does not start with partition-entered (found %r at position 1)"
            % (label, first.kind),
        )
    if first.sequence != 1:
        raise LocalFirstError(
            LocalFirstReason.JOURNAL_DIVERGENCE,
            "the partition-entered record must hold journal position 1 (found %d)"
            % first.sequence,
        )
    expected_episode_id = derive_episode_id(
        first.contract_id,
        first.base_snapshot_id,
        first.recorded_at,
        first.provenance,
    )
    if first.episode_id != expected_episode_id:
        raise LocalFirstError(
            LocalFirstReason.ID_MISMATCH,
            "the episode identity does not re-derive from the episode core "
            "(tamper evidence): expected %s, the journal carries %s"
            % (expected_episode_id[:23], first.episode_id[:23]),
        )

    state = "OPEN"
    fresh_snapshot_id = ""
    fresh_state_digest = ""
    resync_id = ""
    admitted: List[str] = []
    rejected: List[str] = []
    admitted_subjects: Dict[str, str] = {}
    seen_operation_ids: Dict[str, int] = {}

    for index, record in enumerate(sequence):
        position = index + 1
        if record.sequence != position:
            raise LocalFirstError(
                LocalFirstReason.JOURNAL_DIVERGENCE,
                "record at fold position %d carries journal position %d "
                "(gap or conflict — the journal is not replayable)"
                % (position, record.sequence),
            )
        if record.episode_id != first.episode_id or record.contract_id != first.contract_id:
            raise LocalFirstError(
                LocalFirstReason.JOURNAL_DIVERGENCE,
                "record at position %d attributes to episode %s / contract %s, "
                "not the journal's %s / %s"
                % (
                    position,
                    record.episode_id[:23],
                    record.contract_id[:23],
                    first.episode_id[:23],
                    first.contract_id[:23],
                ),
            )
        if record.operation_id in seen_operation_ids:
            raise LocalFirstError(
                LocalFirstReason.JOURNAL_DIVERGENCE,
                "the operation %s appears at both journal positions %d and %d "
                "(a duplicate application — the offline journal is idempotent; "
                "a double-applied operation is journal divergence)"
                % (record.operation_id[:23], seen_operation_ids[record.operation_id], position),
            )
        seen_operation_ids[record.operation_id] = position
        if state == "CLOSED":
            raise LocalFirstError(
                LocalFirstReason.JOURNAL_DIVERGENCE,
                "the %s record at position %d follows the partition exit — a "
                "closed episode never accepts operations (a new partition "
                "opens a new episode)" % (record.kind, position),
            )
        if record.kind == "partition-exited":
            fresh_snapshot_id = record.fresh_snapshot_id
            fresh_state_digest = record.fresh_state_digest
            resync_id = record.resync_id
            state = "CLOSED"
        elif record.kind == "connectivity-admission":
            if record.outcome == "admitted":
                # the CORE M016 discipline, mechanically enforced: an
                # admitted decision's instant MUST lie inside the
                # authority freshness window it carries — a local state
                # past its declared freshness bound NEVER silently
                # authorizes (a forged admitted record is journal
                # divergence, never a silent allow)
                decided = parse_instant(record.recorded_at)
                if decided < parse_instant(record.fresh_from):
                    raise LocalFirstError(
                        LocalFirstReason.JOURNAL_DIVERGENCE,
                        "the admitted operation at position %d was decided at "
                        "%s, BEFORE its carried freshness window opens (%s) — "
                        "a local state outside its declared freshness window "
                        "never silently authorizes (the forged silent-allow "
                        "shape fails the fold)" % (position, record.recorded_at, record.fresh_from),
                    )
                if decided > parse_instant(record.fresh_until):
                    raise LocalFirstError(
                        LocalFirstReason.JOURNAL_DIVERGENCE,
                        "the admitted operation at position %d was decided at "
                        "%s, PAST its carried freshness bound (%s) — a local "
                        "state past its declared freshness bound never "
                        "silently authorizes (the forged silent-allow shape "
                        "fails the fold)" % (position, record.recorded_at, record.fresh_until),
                    )
                subject_value = record.subject.value
                if subject_value in admitted_subjects:
                    raise LocalFirstError(
                        LocalFirstReason.JOURNAL_DIVERGENCE,
                        "the subject %r is admitted twice in one episode "
                        "(positions %d and %d) — a subject is admitted once; "
                        "a retried admission is idempotent by operation "
                        "identity, and a second admission with different "
                        "material is a discipline violation (fail closed)"
                        % (
                            subject_value[:40],
                            admitted_subjects[subject_value],
                            position,
                        ),
                    )
                admitted_subjects[subject_value] = position
                admitted.append(record.operation_id)
            else:
                rejected.append(record.operation_id)

    return LocalState(
        episode_id=first.episode_id,
        contract_id=first.contract_id,
        state=state,
        base_snapshot_id=first.base_snapshot_id,
        base_state_digest=first.base_state_digest,
        sequence=sequence[-1].sequence,
        provenance=first.provenance,
        fresh_snapshot_id=fresh_snapshot_id,
        fresh_state_digest=fresh_state_digest,
        resync_id=resync_id,
        admitted=tuple(admitted),
        rejected=tuple(rejected),
    )


class OfflineJournal:
    """The deterministic partition-episode journal store (append-only
    records + the pure fold; the sole writer of local state is the
    fold).

    ATOMICITY: every append is validated in full BEFORE any state
    changes (the candidate journal must fold cleanly or nothing is
    appended); a rejected operation leaves the journal byte-identical.

    IDEMPOTENCY: an offline operation retried while partitioned (an
    uncertain outcome retried after a crash) derives the SAME
    content-derived identity over its position-independent core; the
    append returns the EXISTING record without a second application —
    the same operation never double-applies.

    REPLAY: the local state is ALWAYS the deterministic fold of the
    append-only journal (construction-is-recovery);
    ``OfflineJournal.from_records`` rebuilds a journal from a record
    sequence with no other state.
    """

    def __init__(self, episode_id: str) -> None:
        if not isinstance(episode_id, str) or not episode_id:
            raise LocalFirstError(
                LocalFirstReason.INVALID_INPUT,
                "the journal requires its episode identity",
            )
        self._episode_id = episode_id
        self._records: List[OfflineOperation] = []
        self._operations: Dict[str, OfflineOperation] = {}

    # -- read surface --------------------------------------------------

    @property
    def episode_id(self) -> str:
        """The partition episode this journal belongs to."""
        return self._episode_id

    def state(self) -> LocalState:
        """The folded local state (fail-closed on an empty journal —
        an unopened episode has no state to fold)."""
        if not self._records:
            raise LocalFirstError(
                LocalFirstReason.INVALID_INPUT,
                "the journal of episode %s carries no records (open the "
                "partition episode first)" % self._episode_id[:23],
            )
        return fold_operations(self._records, label="the offline journal")

    def records(self) -> Tuple[OfflineOperation, ...]:
        """The append-only journal (its own deterministic order)."""
        return tuple(self._records)

    def operation(self, operation_id: object) -> OfflineOperation:
        """One journaled operation by its content-derived identity
        (fail-closed on unknown)."""
        if not isinstance(operation_id, str) or not operation_id:
            raise LocalFirstError(
                LocalFirstReason.INVALID_INPUT,
                "operation_id must be a non-empty string",
            )
        record = self._operations.get(operation_id)
        if record is None:
            raise LocalFirstError(
                LocalFirstReason.INVALID_INPUT,
                "operation %s is unknown to the journal of episode %s "
                "(fail-closed: the local-first surface never invents an "
                "operation)" % (operation_id[:32], self._episode_id[:23]),
            )
        return record

    def verify_integrity(self) -> None:
        """Fail closed unless the journal re-folds byte-identically
        (the deterministic replay check — construction-is-recovery)."""
        current = self.state()
        replayed = fold_operations(self._records, label="the integrity replay")
        if current.canonical_bytes() != replayed.canonical_bytes():
            raise LocalFirstError(
                LocalFirstReason.JOURNAL_DIVERGENCE,
                "the journal of episode %s does not re-fold byte-identically "
                "(construction-is-recovery violated)" % current.episode_id[:23],
            )

    # -- construction-is-recovery ---------------------------------------

    @classmethod
    def from_records(cls, records: object) -> "OfflineJournal":
        """Rebuild a journal from a record sequence
        (construction-is-recovery: no state exists outside the fold)."""
        sequence = _require_record_sequence(records, "the recovery journal")
        folded = fold_operations(sequence, label="the recovery journal")
        journal = cls(folded.episode_id)
        journal._records = list(sequence)
        journal._operations = {r.operation_id: r for r in sequence}
        journal.verify_integrity()
        return journal

    # -- the idempotent append ------------------------------------------

    def append(self, record: OfflineOperation) -> OfflineOperation:
        """Append one validated offline record (atomic + idempotent).

        IDEMPOTENT: a record whose content-derived operation identity
        is already journaled returns the EXISTING record (a retried
        operation never double-applies — the position-independent
        identity is the idempotency key).

        ATOMIC: the candidate journal must fold cleanly BEFORE the
        append is visible (a rejected append leaves the journal
        byte-identical).
        """
        if not isinstance(record, OfflineOperation):
            raise LocalFirstError(
                LocalFirstReason.INVALID_INPUT,
                "append requires an OfflineOperation record (got %s)"
                % type(record).__name__,
            )
        if record.episode_id != self._episode_id:
            raise LocalFirstError(
                LocalFirstReason.ID_MISMATCH,
                "the record attributes to episode %s, not this journal's %s"
                % (record.episode_id[:23], self._episode_id[:23]),
            )
        existing = self._operations.get(record.operation_id)
        if existing is not None:
            # the identity IS the position-independent operation core
            # (the record constructor re-derives and verifies it at
            # construction — tamper evidence), so an equal identity
            # means equal core material: the retry returns the
            # existing record, never a second application (the journal
            # position is an assignment, not content)
            return existing
        if self._records and self._records[-1].kind == "partition-exited":
            raise LocalFirstError(
                LocalFirstReason.EPISODE_CLOSED,
                "the partition episode is CLOSED; closed episodes never "
                "accept operations (a new partition opens a new episode)",
            )
        candidate = self._records + [record]
        # the fold is the sole writer of state: the appended journal
        # must fold cleanly or nothing is appended (atomicity)
        fold_operations(candidate, label="the candidate journal")
        self._records.append(record)
        self._operations[record.operation_id] = record
        return record

    # -- the episode lifecycle ------------------------------------------

    @classmethod
    def open_episode(
        cls,
        *,
        contract_id: str,
        base_snapshot_id: str,
        base_state_digest: str,
        runtime_event_id: str,
        recorded_at: str,
        provenance: Provenance,
    ) -> Tuple["OfflineJournal", OfflineOperation]:
        """Open one partition episode (the ``partition-entered`` record
        at journal position 1; the episode identity derives over the
        episode core — the journaled offline/degraded-mode ENTRY,
        carrying the base authority view and the M015 runtime
        degraded-entry event id as the evidence-visible composition
        link)."""
        if not isinstance(provenance, Provenance):
            raise LocalFirstError(
                LocalFirstReason.INVALID_INPUT,
                "the partition entry requires a contracts.Provenance record "
                "(LOCK-118)",
            )
        episode_id = derive_episode_id(
            contract_id, base_snapshot_id, recorded_at, provenance
        )
        journal = cls(episode_id)
        record = journal.append(
            OfflineOperation(
                operation_id="",
                episode_id=episode_id,
                contract_id=contract_id,
                sequence=1,
                kind="partition-entered",
                recorded_at=recorded_at,
                provenance=provenance,
                base_snapshot_id=base_snapshot_id,
                base_state_digest=base_state_digest,
                runtime_event_id=runtime_event_id,
            )
        )
        return journal, record

    def exit(
        self,
        *,
        fresh_snapshot_id: str,
        fresh_state_digest: str,
        resync_id: str,
        reconnect_id: str,
        recorded_at: str,
        provenance: Provenance,
    ) -> OfflineOperation:
        """Append the ``partition-exited`` record (final position; the
        journaled offline-mode EXIT — the explicit reconnect and
        resynchronization completed, carrying the fresh authority view,
        the resync result id and the M015 reconnect evidence id as the
        evidence-visible composition links)."""
        if not self._records:
            raise LocalFirstError(
                LocalFirstReason.INVALID_INPUT,
                "the journal of episode %s carries no records (the exit "
                "requires an opened episode)" % self._episode_id[:23],
            )
        if self._records[-1].kind == "partition-exited":
            raise LocalFirstError(
                LocalFirstReason.EPISODE_CLOSED,
                "the partition episode is CLOSED; the exit is final (a new "
                "partition opens a new episode)",
            )
        return self.append(
            OfflineOperation(
                operation_id="",
                episode_id=self._episode_id,
                contract_id=self._records[0].contract_id,
                sequence=len(self._records) + 1,
                kind="partition-exited",
                recorded_at=recorded_at,
                provenance=provenance,
                fresh_snapshot_id=fresh_snapshot_id,
                fresh_state_digest=fresh_state_digest,
                resync_id=resync_id,
                reconnect_id=reconnect_id,
            )
        )
