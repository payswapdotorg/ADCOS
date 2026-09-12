"""ADCOS recovery verification surface (M017 — Disaster Recovery and
State Reconciliation).

The restore verification and the cross-plane reconciliation:

- :func:`verify_restore` — the typed restore verification: the
  recovered state equals the pre-failure state BYTE-EXACTLY, or the
  divergence is explicitly disclosed and reconciled.  The mechanical
  discipline (LOCK-106 — recovery never fabricates history):

  1. the recovered plane MUST reproduce its recovery point
     byte-exactly (identity-for-identity, position-for-position — a
     re-identified or renumbered recovered record fails closed as
     ``recovery-history-fabricated``; a restore that does not
     reproduce its source fails closed as
     ``recovery-restore-diverged``);
  2. the pre-failure plane MUST carry the recovery point's history
     verbatim as its PREFIX (a pre-failure journal whose early records
     differ from the point's is REWRITTEN history — fail closed, never
     a "reconciliation");
  3. the records the pre-failure plane carried BEYOND the recovery
     point are LOST with the failure — one typed
     :class:`~recovery.model.RestoreDivergence` each, cited by their
     ORIGINAL content-derived identities, reconciled onto the recovery
     point as the authoritative base (restoring them would FABRICATE
     history; dropping them silently would absorb the divergence —
     both fail closed);
  4. the finished record's outcome discipline is mechanically
     enforced by :class:`~recovery.model.RestoreVerification`
     (byte-exact carries zero divergence records; a divergence outcome
     carries them — never a silently absorbed divergence).

- :func:`reconcile_planes` — the cross-plane reconciliation: the
  contracts/journal/evidence planes converge after a drill.  The
  accepted M016 resynchronization is driven BY REFERENCE when the
  offline episode is open (``localfirst.close_partition`` — the
  accepted fail-closed order, the accepted reconnect pair, the
  accepted typed divergence records preserved VERBATIM in the
  reconciliation record); the attribution gates fail closed (a
  journal that does not ride the owning contract is unreconcilable —
  LOCK-101/LOCK-117); the composition links between the journal
  planes and the LOCK-106 evidence records on the evidence plane are
  verified, every unresolved link or missing record disclosed as a
  typed :class:`~recovery.model.CrossPlaneDivergence` — never
  silently dropped.

Determinism (LOCK-119): pure functions over the injected inputs; no
wall clock, no randomness, no network, no secrets; canonical-JSON
round-trips with tamper-evident ids.
"""

from __future__ import annotations

import json
from typing import Any, List, Mapping, Optional, Sequence, Tuple

from contracts import ConnectivityContract, Provenance
from resilience import RuntimeStore
from localfirst import (
    DEFAULT_RESOLUTION_RULE,
    AuthoritySnapshot,
    CloseResult,
    OfflineJournal,
    close_partition,
)
from evidence import EvidenceStore

from .errors import RecoveryError, RecoveryReason
from .model import (
    DRILL_ISSUER,
    PLANE_KINDS,
    RECOVERY_ISSUER,
    CrossPlaneDivergence,
    PlaneReconciliation,
    RecoveryPoint,
    RestoreDivergence,
    RestoreVerification,
    _REF_VALUE_PATTERN,
    _wrap_consumed_error,
    journal_state_digest,
)
from .snapshot import plane_record_lines

__all__ = [
    "verify_restore",
    "reconcile_planes",
]


def _record_identities(lines: Sequence[str], plane: str, label: str) -> Tuple[str, ...]:
    """Parse the plane's canonical record lines and extract their
    content-derived record identities (the ``event_id`` of the runtime
    records / the ``operation_id`` of the offline records)."""
    if isinstance(lines, (str, bytes)) or not isinstance(lines, (tuple, list)):
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT, "%s must be a sequence of record lines" % label
        )
    member = "event_id" if plane == "runtime-journal" else "operation_id"
    identities = []
    for i, line in enumerate(lines):
        if not isinstance(line, str) or not line:
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT,
                "%s[%d] must be a non-empty canonical JSON record line" % (label, i),
            )
        try:
            data = json.loads(line)
        except ValueError as error:
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT,
                "%s[%d] is unparseable: %s" % (label, i, str(error)[:80]),
            ) from None
        if not isinstance(data, Mapping):
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT,
                "%s[%d] is not a record mapping" % (label, i),
            )
        value = data.get(member)
        if not isinstance(value, str) or not value:
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT,
                "%s[%d] does not carry its %s identity (the plane record shape "
                "is wrong for the %s plane)" % (label, i, member, plane),
            )
        identities.append(value)
    return tuple(identities)


def _record_positions(lines: Sequence[str], label: str) -> Tuple[int, ...]:
    """Parse the plane's canonical record lines and extract their
    journal positions."""
    positions = []
    for i, line in enumerate(lines):
        data = json.loads(line)
        position = data.get("sequence")
        if isinstance(position, bool) or not isinstance(position, int):
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT,
                "%s[%d] does not carry an integer journal position" % (label, i),
            )
        positions.append(position)
    return tuple(positions)


def verify_restore(
    point: RecoveryPoint,
    pre_failure_lines: Sequence[str],
    restored_lines: Sequence[str],
    *,
    recorded_at: str,
    provenance: Optional[Provenance] = None,
) -> RestoreVerification:
    """The typed restore verification (see the module docstring for
    the full mechanical discipline).  ``pre_failure_lines`` is the
    plane's journal at LOSS time (the pre-failure content);
    ``restored_lines`` is the recovered plane's journal.  Returns the
    typed :class:`~recovery.model.RestoreVerification` record
    (byte-exact or divergence-reconciled); every violation fails
    closed with the specific typed reason.
    """
    if not isinstance(point, RecoveryPoint):
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT,
            "verify_restore requires a recovery RecoveryPoint record",
        )
    label = "the %s restore verification" % point.plane
    if isinstance(pre_failure_lines, (str, bytes)) or not isinstance(
        pre_failure_lines, (tuple, list)
    ):
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT,
            "the pre-failure plane content must be a sequence of record lines",
        )
    if isinstance(restored_lines, (str, bytes)) or not isinstance(
        restored_lines, (tuple, list)
    ):
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT,
            "the restored plane content must be a sequence of record lines",
        )
    if provenance is None:
        provenance = Provenance(
            issuer=RECOVERY_ISSUER,
            decision_refs=(point.recovery_point_id, point.subject_id),
        )
    elif not isinstance(provenance, Provenance):
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT, "provenance must be a Provenance record"
        )

    restored_ids = _record_identities(restored_lines, point.plane, "the restored plane")
    point_ids = _record_identities(
        point.record_lines, point.plane, "the recovery point payload"
    )
    pre_ids = _record_identities(pre_failure_lines, point.plane, "the pre-failure plane")

    # 1. the recovered plane MUST reproduce its recovery point
    #    (identity-for-identity, position-for-position — never a
    #    re-identified or renumbered recovered record)
    for i, (restored_id, point_id) in enumerate(zip(restored_ids, point_ids)):
        if restored_id != point_id:
            raise RecoveryError(
                RecoveryReason.HISTORY_FABRICATED,
                "the restored plane record %d carries the identity %s, not the "
                "recovery point's %s — recovered records preserve their "
                "ORIGINAL content-derived identities (LOCK-106: recovery "
                "never fabricates history; a re-identified record fails "
                "closed)" % (i, restored_id[:23], point_id[:23]),
            )
    if len(restored_ids) != len(point_ids):
        raise RecoveryError(
            RecoveryReason.RESTORE_DIVERGED,
            "the restored plane carries %d records, not the recovery point's "
            "%d — a restore that does not reproduce its source fails closed "
            "(never a divergence to disclose)" % (len(restored_ids), len(point_ids)),
        )
    restored_positions = _record_positions(restored_lines, "the restored plane")
    for i, position in enumerate(restored_positions):
        if position != i + 1:
            raise RecoveryError(
                RecoveryReason.HISTORY_FABRICATED,
                "the restored plane record %d carries journal position %d — a "
                "recovered journal is never silently renumbered (LOCK-106)"
                % (i, position),
            )

    # 2. the pre-failure plane MUST carry the recovery point's history
    #    verbatim as its prefix (rewritten history fails closed, never
    #    a "reconciliation")
    if len(pre_ids) < len(point_ids):
        raise RecoveryError(
            RecoveryReason.HISTORY_FABRICATED,
            "the pre-failure plane carries %d records, fewer than the "
            "recovery point's %d — the point claims pre-failure history it "
            "cannot evidence (LOCK-106: recovery never fabricates history)"
            % (len(pre_ids), len(point_ids)),
        )
    for i, (pre_id, point_id) in enumerate(zip(pre_ids, point_ids)):
        if pre_id != point_id:
            raise RecoveryError(
                RecoveryReason.HISTORY_FABRICATED,
                "the pre-failure plane record %d carries the identity %s, not "
                "the recovery point's %s — the pre-failure journal does not "
                "carry the point's history verbatim (history was rewritten; "
                "never a reconciliation)" % (i, pre_id[:23], point_id[:23]),
            )
    pre_positions = _record_positions(pre_failure_lines, "the pre-failure plane")
    for i, position in enumerate(pre_positions):
        if position != i + 1:
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT,
                "the pre-failure plane record %d carries journal position %d "
                "(a pre-failure journal is gapless from position 1)"
                % (i, position),
            )

    expected_digest = journal_state_digest(tuple(pre_failure_lines))
    actual_digest = journal_state_digest(tuple(restored_lines))

    # 3. the LOST records: the pre-failure content beyond the recovery
    #    point's watermark — disclosed one typed record each, cited by
    #    their ORIGINAL identities, reconciled onto the recovery point
    divergences: List[RestoreDivergence] = []
    lost_ids = pre_ids[len(point_ids) :]
    for offset, lost_id in enumerate(lost_ids):
        divergences.append(
            RestoreDivergence(
                divergence_id="",
                recovery_point_id=point.recovery_point_id,
                plane=point.plane,
                subject_id=point.subject_id,
                code="record-lost-beyond-recovery-point",
                expected_record_id=lost_id,
                resolution="reconciled-to-recovery-point",
                provenance=Provenance(
                    issuer=RECOVERY_ISSUER,
                    decision_refs=(point.recovery_point_id, lost_id),
                ),
            )
        )

    outcome = "byte-exact" if not divergences else "divergence-reconciled"
    return RestoreVerification(
        verification_id="",
        recovery_point_id=point.recovery_point_id,
        plane=point.plane,
        subject_id=point.subject_id,
        expected_digest=expected_digest,
        actual_digest=actual_digest,
        outcome=outcome,
        divergences=tuple(divergences),
        verified_records=len(restored_ids),
        recorded_at=recorded_at,
        provenance=provenance,
    )


def _offline_runtime_links(
    journal: OfflineJournal,
) -> Tuple[Tuple[str, str], ...]:
    """The offline journal's citations into the runtime journal (the
    M016 evidence-visible composition links): every partition-entered
    record's ``runtime_event_id`` and every partition-exited record's
    ``reconnect_id`` — (member, citation) pairs."""
    links = []
    for record in journal.records():
        if record.kind == "partition-entered":
            links.append(("runtime_event_id", record.runtime_event_id))
        elif record.kind == "partition-exited":
            links.append(("reconnect_id", record.reconnect_id))
    return tuple(links)


def reconcile_planes(
    *,
    drill_id: str,
    contract: ConnectivityContract,
    runtime_store: RuntimeStore,
    runtime_id: object,
    offline_journal: OfflineJournal,
    evidence_store: EvidenceStore,
    expected_evidence: Sequence[Tuple[str, str]],
    fresh_view: Optional[AuthoritySnapshot] = None,
    resolution_rule: Sequence[str] = DEFAULT_RESOLUTION_RULE,
    recorded_at: str,
    provenance: Optional[Provenance] = None,
) -> Tuple[PlaneReconciliation, Optional[CloseResult]]:
    """The cross-plane reconciliation (the contracts/journal/evidence
    planes converge after a drill — with typed divergence records).

    **The convergence drive** (the accepted M016 surface, BY
    REFERENCE): when the offline episode is OPEN and a fresh
    authority view is supplied, the accepted ``close_partition`` is
    driven — the accepted fail-closed order (the pure convergence
    FIRST; a typed rejection leaves the runtime DEGRADED and the
    partition open), the accepted reconnect pair naming BOTH the OLD
    and the NEW authority views (the WORK-012 discipline), and the
    journaled offline exit.  The accepted
    :class:`~localfirst.model.ResyncResult` is preserved VERBATIM in
    the reconciliation record (consumed by reference — never
    re-interpreted).  A consumed typed rejection fails closed on this
    surface's own vocabulary.

    **The cross-plane gates** (every divergence disclosed as a typed
    record, every unreconcilable mismatch fail-closed):

    1. attribution — every record on both journal planes must cite
       exactly the owning contract, and the runtime session must ride
       it (LOCK-101/LOCK-117: a journal that does not ride the
       contract is unreconcilable — fail closed, never a divergence
       record to disclose);
    2. composition links — every offline journal citation into the
       runtime journal (the partition entry's degraded-entry event id,
       the exit's reconnect evidence id) must resolve (an unresolved
       link is a typed disclosed divergence);
    3. evidence preservation — every drill-produced LOCK-106 evidence
       record must be present on the evidence plane with its identity
       intact (a missing record is a typed disclosed divergence — the
       evidence is never silently dropped).

    Returns ``(reconciliation, close_result)`` — the close result
    carries the accepted live records (the resync result, the runtime
    session after the reconnect, the WORK-012 reconnect evidence, the
    folded local state); None when no drive happened (the episode was
    already closed or no fresh view was supplied).
    """
    if not isinstance(contract, ConnectivityContract):
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT,
            "reconcile_planes requires a contracts.ConnectivityContract (got "
            "%s)" % type(contract).__name__,
        )
    if not isinstance(runtime_store, RuntimeStore):
        raise RecoveryError(
            RecoveryReason.COMPOSITION,
            "reconcile_planes requires a resilience RuntimeStore (got %s) — "
            "the accepted M015 runtime is the composition substrate, consumed "
            "BY REFERENCE" % type(runtime_store).__name__,
        )
    if not isinstance(offline_journal, OfflineJournal):
        raise RecoveryError(
            RecoveryReason.COMPOSITION,
            "reconcile_planes requires a localfirst OfflineJournal (got %s) — "
            "the accepted M016 offline journal is the composition substrate, "
            "consumed BY REFERENCE" % type(offline_journal).__name__,
        )
    if not isinstance(evidence_store, EvidenceStore):
        raise RecoveryError(
            RecoveryReason.COMPOSITION,
            "reconcile_planes requires an evidence EvidenceStore (got %s) — "
            "the accepted LOCK-106 typing is the evidence plane, consumed BY "
            "REFERENCE" % type(evidence_store).__name__,
        )
    if isinstance(expected_evidence, (str, bytes)) or not isinstance(
        expected_evidence, (tuple, list)
    ):
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT,
            "expected_evidence must be a sequence of (plane, record id) pairs",
        )
    for i, pair in enumerate(expected_evidence):
        if isinstance(pair, (str, bytes)) or not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT,
                "expected_evidence[%d] must be a (plane, record id) pair" % i,
            )
        plane, record_id = pair[0], pair[1]
        if plane not in PLANE_KINDS:
            raise RecoveryError(
                RecoveryReason.VOCABULARY,
                "expected_evidence[%d][0] must name a journal-bearing plane "
                "(found %r)" % (i, plane),
            )
        if not isinstance(record_id, str) or _REF_VALUE_PATTERN.fullmatch(record_id) is None:
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT,
                "expected_evidence[%d][1] must be a well-formed evidence record "
                "id (found %r)" % (i, record_id),
            )
    if provenance is None:
        provenance = Provenance(
            issuer=DRILL_ISSUER,
            decision_refs=(drill_id, contract.contract_id),
        )
    elif not isinstance(provenance, Provenance):
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT, "provenance must be a Provenance record"
        )

    # -- gate 1: the attribution (fail closed — unreconcilable; BEFORE
    # any convergence drive: a journal that does not ride the owning
    # contract is never driven, never reconciled, never diverged -----
    divergences: List[CrossPlaneDivergence] = []
    with _wrap_consumed_error("the reconciliation runtime read"):
        session = runtime_store.session(runtime_id)
        events = runtime_store.events(runtime_id)
    if session.contract_id != contract.contract_id:
        raise RecoveryError(
            RecoveryReason.PLANE_MISMATCH,
            "runtime session %s rides contract %s, not %s — a journal that "
            "does not ride the owning contract is unreconcilable (LOCK-101/"
            "LOCK-117; the recovery surface never rewrites attribution)"
            % (
                session.runtime_id[:23],
                session.contract_id[:23],
                contract.contract_id[:23],
            ),
        )
    for event in events:
        if event.contract_id != contract.contract_id:
            raise RecoveryError(
                RecoveryReason.PLANE_MISMATCH,
                "the runtime journal event at position %d cites contract %s, "
                "not %s — unreconcilable attribution (fail closed)"
                % (event.sequence, event.contract_id[:23], contract.contract_id[:23]),
            )
    for record in offline_journal.records():
        if record.contract_id != contract.contract_id:
            raise RecoveryError(
                RecoveryReason.PLANE_MISMATCH,
                "the offline journal record at position %d cites contract %s, "
                "not %s — unreconcilable attribution (fail closed)"
                % (record.sequence, record.contract_id[:23], contract.contract_id[:23]),
            )

    # -- the convergence drive (the accepted M016 close, BY REFERENCE) --
    close_result: Optional[CloseResult] = None
    local_state = offline_journal.state()
    if local_state.state == "OPEN":
        if fresh_view is None:
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT,
                "the offline episode %s is OPEN and the reconciliation drives "
                "its convergence — supply the fresh authority view (the "
                "accepted resynchronization input)"
                % local_state.episode_id[:23],
            )
        with _wrap_consumed_error("the accepted M016 resynchronization drive"):
            close_result = close_partition(
                runtime_store,
                runtime_id,
                contract,
                offline_journal,
                fresh_view,
                resolution_rule=resolution_rule,
                recorded_at=recorded_at,
            )
        # the converged states (the accepted close's own outcomes,
        # verified — a close that left the episode open or the runtime
        # degraded did not converge)
        after_state = offline_journal.state()
        if after_state.state != "CLOSED":
            raise RecoveryError(
                RecoveryReason.PLANE_MISMATCH,
                "the accepted resynchronization did not close the episode "
                "(the planes did not converge)",
            )
        if close_result.session.state != "ACTIVE":
            raise RecoveryError(
                RecoveryReason.PLANE_MISMATCH,
                "the accepted reconnect did not land the runtime session "
                "ACTIVE on the fresh view (the planes did not converge)",
            )
        # re-read the post-drive runtime journal (the convergence
        # appended the reconnect pair)
        with _wrap_consumed_error("the reconciliation runtime re-read"):
            events = runtime_store.events(runtime_id)

    # -- gate 2: the composition links (typed disclosed divergence) --
    runtime_event_ids = {event.event_id for event in events}
    with _wrap_consumed_error("the reconciliation reconnect evidence read"):
        reconnect_ids = {
            evidence.reconnect_id for evidence in runtime_store.reconnect_evidence(runtime_id)
        }
    for member, citation in _offline_runtime_links(offline_journal):
        resolved = citation in (runtime_event_ids if member == "runtime_event_id" else reconnect_ids)
        if not resolved:
            divergences.append(
                CrossPlaneDivergence(
                    divergence_id="",
                    drill_id=drill_id,
                    contract_id=contract.contract_id,
                    code="composition-link-unresolved",
                    plane_a="offline-journal",
                    plane_b="runtime-journal",
                    expected=citation,
                    actual="unresolved",
                    resolution="disclosed",
                    provenance=Provenance(
                        issuer=DRILL_ISSUER,
                        decision_refs=(drill_id, citation),
                    ),
                )
            )

    # -- gate 3: the evidence-plane preservation (typed divergence) --
    for plane, record_id in expected_evidence:
        if not evidence_store.has(record_id):
            divergences.append(
                CrossPlaneDivergence(
                    divergence_id="",
                    drill_id=drill_id,
                    contract_id=contract.contract_id,
                    code="evidence-record-missing",
                    plane_a="evidence-plane",
                    plane_b=plane,
                    expected=record_id,
                    actual="missing",
                    resolution="disclosed",
                    provenance=Provenance(
                        issuer=DRILL_ISSUER,
                        decision_refs=(drill_id, record_id),
                    ),
                )
            )

    # -- the plane digests + the contracts-plane material -----------
    plane_digests = (
        ("runtime-journal", journal_state_digest(plane_record_lines(events))),
        ("offline-journal", journal_state_digest(plane_record_lines(offline_journal.records()))),
    )
    accepted_resync: Optional[Mapping[str, Any]] = (
        close_result.resync.to_dict() if close_result is not None else None
    )
    outcome = "converged" if not divergences else "divergence-disclosed"
    reconciliation = PlaneReconciliation(
        reconciliation_id="",
        drill_id=drill_id,
        contract_id=contract.contract_id,
        constraint_fingerprint=contract.hard_constraint_fingerprint(),
        plane_digests=plane_digests,
        evidence_record_ids=tuple(
            record_id for _, record_id in expected_evidence
        ),
        divergences=tuple(divergences),
        accepted_resync=accepted_resync,
        outcome=outcome,
        recorded_at=recorded_at,
        provenance=provenance,
    )
    return reconciliation, close_result
