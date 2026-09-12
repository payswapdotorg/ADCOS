"""ADCOS recovery snapshot surface (M017 — Disaster Recovery and State
Reconciliation).

The snapshot/recovery-point construction and the restore, over the
journal-bearing state planes, composing the accepted surfaces BY
REFERENCE (the M015 runtime journals — ``resilience/`` — and the M016
offline journals — ``localfirst/``; imported and driven, never
reimplemented, weakened, forked, or bypassed):

- :func:`snapshot_runtime_plane` — construct the typed
  :class:`~recovery.model.RecoveryPoint` over one M015 runtime
  session's journal (the plane captured at its head through the
  accepted ``RuntimeStore`` read surface; the journal serialized as
  canonical JSON record lines — the byte-exact restore material; the
  content-derived identity and state digest over the plane CONTENT —
  the LOCK-106 class, never position or time).
- :func:`snapshot_offline_plane` — the same over one M016 partition
  episode's journal (the accepted ``OfflineJournal`` read surface).
- :func:`verify_recovery_point` — the fail-closed snapshot
  verification: the payload records are parsed and RECONSTRUCTED
  through the ACCEPTED constructors (each record's content-derived
  identity re-derived — tamper evidence), the plane attribution is
  checked (every record cites the owning contract and the plane
  subject), and the journal shape is checked (the identity sequence —
  the records' own journal positions, never renumbered).  An
  unverifiable snapshot (unparseable, provenance-missing, a record
  identity that does not re-derive, an attribution mismatch) is
  REJECTED WHOLE with the typed reason — never partially trusted,
  never best-effort loaded.
- :func:`restore_runtime_plane` — rebuild the M015 runtime plane from
  its recovery point through the ACCEPTED
  ``RuntimeStore.from_events`` (construction-is-recovery: no state
  exists outside the accepted fold; the restore never writes around
  it).
- :func:`restore_offline_plane` — the same through the ACCEPTED
  ``OfflineJournal.from_records``.
- :func:`plane_record_lines` — the deterministic journal serialization
  (the accepted records' canonical bytes, in journal order).

Determinism (LOCK-119): pure functions over the injected inputs; no
wall clock, no randomness, no network, no secrets; canonical-JSON
round-trips with tamper-evident ids.
"""

from __future__ import annotations

import contextlib
import json
from typing import Any, Iterator, Mapping, Sequence, Tuple

from contracts import Provenance
from resilience import RuntimeEvent, RuntimeStore
from localfirst import OfflineJournal, OfflineOperation

from .errors import RecoveryError, RecoveryReason
from .model import (
    RECOVERY_ISSUER,
    RecoveryPoint,
    _wrap_consumed_error,
    journal_state_digest,
)

__all__ = [
    "snapshot_runtime_plane",
    "snapshot_offline_plane",
    "verify_recovery_point",
    "restore_runtime_plane",
    "restore_offline_plane",
    "plane_record_lines",
    "plane_lines_digest",
]


@contextlib.contextmanager
def _snapshot_gate(label: str) -> Iterator[None]:
    """The whole-point snapshot verification gate: ANY failure of a
    payload record to reconstruct through the accepted constructors
    (a forged identity, a missing provenance envelope, a foreign
    record shape) rejects the SNAPSHOT WHOLE as
    ``recovery-snapshot-unverifiable`` — never partially trusted,
    never best-effort loaded.  A RecoveryError raised by this
    surface's own gates passes through untouched."""
    try:
        yield
    except RecoveryError:
        raise
    except ValueError as error:  # consumed typed errors are ValueError
        raise RecoveryError(
            RecoveryReason.SNAPSHOT_UNVERIFIABLE,
            "%s was rejected at the snapshot verification (bad integrity — "
            "the snapshot is rejected whole, never partially trusted): %s"
            % (label, getattr(error, "detail", error)),
        ) from None


def plane_record_lines(records: Sequence[Any]) -> Tuple[str, ...]:
    """The deterministic journal serialization: one canonical JSON
    line per accepted record (the record's ``canonical_bytes`` decoded
    as UTF-8 text — byte-exact restore material)."""
    if isinstance(records, (str, bytes)) or not isinstance(records, (tuple, list)):
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT,
            "the plane records must be a sequence of accepted journal records",
        )
    lines = []
    for i, record in enumerate(records):
        method = getattr(record, "canonical_bytes", None)
        if not callable(method):
            raise RecoveryError(
                RecoveryReason.INVALID_INPUT,
                "plane records[%d] is not an accepted journal record (no "
                "canonical serialization; got %s)" % (i, type(record).__name__),
            )
        lines.append(record.canonical_bytes().decode("utf-8"))
    return tuple(lines)


def plane_lines_digest(lines: Sequence[str]) -> str:
    """The plane state digest over the record lines (the
    :func:`~recovery.model.journal_state_digest` re-export for the
    verification callers)."""
    return journal_state_digest(lines)


def _capture_plane(
    *,
    plane: str,
    contract_id: str,
    subject_id: str,
    records: Sequence[Any],
    watermark: int,
    recorded_at: str,
    provenance: Provenance,
) -> RecoveryPoint:
    lines = plane_record_lines(records)
    return RecoveryPoint(
        plane=plane,
        contract_id=contract_id,
        subject_id=subject_id,
        record_lines=lines,
        sequence=watermark,
        recorded_at=recorded_at,
        provenance=provenance,
    )


def snapshot_runtime_plane(
    store: RuntimeStore,
    runtime_id: object,
    *,
    recorded_at: str,
    provenance: Provenance,
) -> RecoveryPoint:
    """Construct the typed recovery point over one M015 runtime
    session's journal (the plane captured at its head through the
    ACCEPTED read surface — the fold stays the accepted sole writer).

    Fail-closed gates: the store must be the accepted
    ``RuntimeStore``; the runtime session must exist (the accepted
    ``session``/``events`` reads — a fold and a raw journal read); the
    point carries the session's contract attribution and journal
    watermark.
    """
    if not isinstance(store, RuntimeStore):
        raise RecoveryError(
            RecoveryReason.COMPOSITION,
            "snapshot_runtime_plane requires a resilience RuntimeStore (got "
            "%s) — the accepted M015 runtime is the composition substrate, "
            "consumed BY REFERENCE" % type(store).__name__,
        )
    if not isinstance(provenance, Provenance):
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT,
            "the recovery point requires a contracts.Provenance record "
            "(LOCK-118)",
        )
    with _wrap_consumed_error("the runtime-plane snapshot read"):
        session = store.session(runtime_id)
        events = store.events(runtime_id)
    return _capture_plane(
        plane="runtime-journal",
        contract_id=session.contract_id,
        subject_id=session.runtime_id,
        records=events,
        watermark=events[-1].sequence,
        recorded_at=recorded_at,
        provenance=provenance,
    )


def snapshot_offline_plane(
    journal: OfflineJournal,
    *,
    recorded_at: str,
    provenance: Provenance,
) -> RecoveryPoint:
    """Construct the typed recovery point over one M016 partition
    episode's journal (the plane captured at its head through the
    ACCEPTED read surface).

    Fail-closed gates: the journal must be the accepted
    ``OfflineJournal`` and must carry records (an unopened episode has
    no plane to snapshot); the point carries the episode's contract
    attribution and journal watermark.
    """
    if not isinstance(journal, OfflineJournal):
        raise RecoveryError(
            RecoveryReason.COMPOSITION,
            "snapshot_offline_plane requires a localfirst OfflineJournal "
            "(got %s) — the accepted M016 offline journal is the composition "
            "substrate, consumed BY REFERENCE" % type(journal).__name__,
        )
    if not isinstance(provenance, Provenance):
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT,
            "the recovery point requires a contracts.Provenance record "
            "(LOCK-118)",
        )
    records = journal.records()
    if not records:
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT,
            "the offline journal of episode %s carries no records (an "
            "unopened episode has no plane to snapshot)"
            % journal.episode_id[:23],
        )
    first = records[0]
    return _capture_plane(
        plane="offline-journal",
        contract_id=first.contract_id,
        subject_id=first.episode_id,
        records=records,
        watermark=records[-1].sequence,
        recorded_at=recorded_at,
        provenance=provenance,
    )


def _parse_lines(point: RecoveryPoint, label: str) -> Tuple[Mapping[str, Any], ...]:
    """Parse the point's record lines (the fail-closed parse —
    unparseable material rejects the snapshot WHOLE)."""
    parsed = []
    for i, line in enumerate(point.record_lines):
        try:
            data = json.loads(line)
        except ValueError as error:
            raise RecoveryError(
                RecoveryReason.SNAPSHOT_UNVERIFIABLE,
                "%s record line %d is unparseable (bad integrity: %s) — the "
                "snapshot is rejected whole, never partially trusted"
                % (label, i, str(error)[:80]),
            ) from None
        if not isinstance(data, Mapping):
            raise RecoveryError(
                RecoveryReason.SNAPSHOT_UNVERIFIABLE,
                "%s record line %d is not a record mapping — the snapshot is "
                "rejected whole, never partially trusted" % (label, i),
            )
        parsed.append(data)
    return tuple(parsed)


def verify_recovery_point(point: RecoveryPoint) -> None:
    """The fail-closed snapshot verification (the whole-point check —
    never partial trust):

    1. the payload lines parse (unparseable -> rejected whole);
    2. every payload record RECONSTRUCTS through the ACCEPTED
       constructor — its content-derived identity re-derives (a
       forged/re-identified record is rejected whole: tamper
       evidence), and its provenance envelope is present (a
       provenance-missing record rejects the snapshot whole);
    3. every record attributes to the point's owning contract and the
       plane subject (an attribution mismatch rejects the whole);
    4. the records' journal positions are the point's own gapless
       identity sequence, 1..N in order, matching the point's declared
       watermark (a renumbered or gap-carrying snapshot is rejected
       whole — recovery never renumbers history).

    Raises ``recovery-snapshot-unverifiable`` (or the attribution's
    ``recovery-id-mismatch``) on the FIRST violation; nothing is
    loaded, nothing is trusted.
    """
    if not isinstance(point, RecoveryPoint):
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT,
            "verify_recovery_point requires a recovery RecoveryPoint record",
        )
    label = "the %s recovery point" % point.plane
    parsed = _parse_lines(point, label)
    # 2. reconstruct through the accepted constructors (identity
    #    re-derivation + provenance presence — ANY failure rejects
    #    the snapshot whole: never partially trusted, never
    #    best-effort loaded)
    if point.plane == "runtime-journal":
        for i, data in enumerate(parsed):
            with _snapshot_gate("%s record line %d" % (label, i)):
                RuntimeEvent.from_dict(data)
        subject_member = "runtime_id"
    else:
        for i, data in enumerate(parsed):
            with _snapshot_gate("%s record line %d" % (label, i)):
                OfflineOperation.from_dict(data)
        subject_member = "episode_id"
    # 3. the attribution checks (contract + plane subject)
    for i, data in enumerate(parsed):
        if data.get("contract_id") != point.contract_id:
            raise RecoveryError(
                RecoveryReason.ID_MISMATCH,
                "%s record line %d attributes to contract %s, not the "
                "recovery point's %s — the snapshot is rejected whole"
                % (
                    label,
                    i,
                    str(data.get("contract_id"))[:23],
                    point.contract_id[:23],
                ),
            )
        if data.get(subject_member) != point.subject_id:
            raise RecoveryError(
                RecoveryReason.ID_MISMATCH,
                "%s record line %d attributes to %s %s, not the recovery "
                "point's subject %s — the snapshot is rejected whole"
                % (
                    label,
                    i,
                    subject_member,
                    str(data.get(subject_member))[:23],
                    point.subject_id[:23],
                ),
            )
    # 4. the journal-position discipline: gapless 1..N, in order,
    #    matching the declared watermark
    for i, data in enumerate(parsed):
        position = data.get("sequence")
        if position != i + 1:
            raise RecoveryError(
                RecoveryReason.HISTORY_FABRICATED,
                "%s record line %d carries journal position %r (expected %d) "
                "— a renumbered or gapped snapshot fabricates history; the "
                "snapshot is rejected whole" % (label, i, position, i + 1),
            )
    if point.sequence != len(parsed):
        raise RecoveryError(
            RecoveryReason.HISTORY_FABRICATED,
            "%s declares the journal watermark %d but carries %d records — "
            "the watermark does not match the plane content; the snapshot "
            "is rejected whole" % (label, point.sequence, len(parsed)),
        )


def restore_runtime_plane(point: RecoveryPoint) -> RuntimeStore:
    """Rebuild the M015 runtime plane from its recovery point through
    the ACCEPTED ``RuntimeStore.from_events`` (construction-is-
    recovery: the accepted fold is the sole writer of runtime state —
    the restore never writes around it).

    The fail-closed point verification (:func:`verify_recovery_point`)
    runs FIRST; an unverifiable snapshot is rejected before any
    construction begins (never partially trusted).
    """
    if not isinstance(point, RecoveryPoint):
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT,
            "restore_runtime_plane requires a recovery RecoveryPoint record",
        )
    if point.plane != "runtime-journal":
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT,
            "restore_runtime_plane requires a runtime-journal recovery point "
            "(found %s)" % point.plane,
        )
    verify_recovery_point(point)
    parsed = _parse_lines(point, "the runtime recovery point")
    events = []
    for i, data in enumerate(parsed):
        with _wrap_consumed_error("the runtime recovery point record %d" % i):
            events.append(RuntimeEvent.from_dict(data))
    with _wrap_consumed_error("the runtime-plane construction"):
        store = RuntimeStore.from_events(tuple(events))
    return store


def restore_offline_plane(point: RecoveryPoint) -> OfflineJournal:
    """Rebuild the M016 offline plane from its recovery point through
    the ACCEPTED ``OfflineJournal.from_records`` (construction-is-
    recovery: the accepted fold is the sole writer of local state).

    The fail-closed point verification runs FIRST.
    """
    if not isinstance(point, RecoveryPoint):
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT,
            "restore_offline_plane requires a recovery RecoveryPoint record",
        )
    if point.plane != "offline-journal":
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT,
            "restore_offline_plane requires an offline-journal recovery "
            "point (found %s)" % point.plane,
        )
    verify_recovery_point(point)
    parsed = _parse_lines(point, "the offline recovery point")
    records = []
    for i, data in enumerate(parsed):
        with _wrap_consumed_error("the offline recovery point record %d" % i):
            records.append(OfflineOperation.from_dict(data))
    with _wrap_consumed_error("the offline-plane construction"):
        journal = OfflineJournal.from_records(tuple(records))
    return journal
