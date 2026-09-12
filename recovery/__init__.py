"""ADCOS recovery package (M017 — Disaster Recovery and State
Reconciliation).

The disaster-recovery and state-reconciliation domain of the R8
charter (R8-CORE-001, DEC-0114; the THIRD R8 child, composing the
accepted surfaces BY REFERENCE — import and compose, never
reimplemented, weakened, forked, or bypassed):

- **Deterministic disaster-recovery drills over the journal-bearing
  state planes** (:mod:`recovery.drill`): the M015 runtime journals
  and the M016 offline journals — a drill is itself a deterministic,
  replayable operation sequence (snapshot -> induced loss -> restore
  -> verify -> reconcile; injected instants, never wall-clock
  dependent).  The composition substrate is exercised INSIDE the
  drills: the accepted ``RuntimeStore`` and ``OfflineJournal`` are
  snapshotted through their accepted read surfaces, restored through
  their accepted construction-is-recovery constructors, and converged
  through the accepted M016 resynchronization (the explicit
  reconnect pair included — the WORK-012 discipline).
- **Snapshot/recovery-point construction** (:mod:`recovery.snapshot`,
  :class:`recovery.model.RecoveryPoint`): typed recovery points over
  the journal-bearing planes; a snapshot carries its CONTENT-DERIVED
  identity (the LOCK-106 class — identity derived from content, never
  position or time) and its full provenance (LOCK-118).
- **Restore verification** (:mod:`recovery.verify`): recovered state
  equals the pre-failure state BYTE-EXACTLY, or the divergence is
  explicitly disclosed and reconciled (typed divergence records with
  full provenance — the accepted ``localfirst/`` divergence
  vocabulary consumed BY REFERENCE where it fits; never silently
  absorbed).
- **Recovery-time bounds as declared deterministic operation counts**
  (:class:`recovery.model.OperationBudget` /
  :class:`recovery.model.OperationCounts`): RTO-style bounds are
  expressed as declared operation counts (journal appends, folds,
  verifications) and ENFORCED by the drill engine's deterministic
  counters — NEVER wall clock, never sleeps, never timing
  measurements (LOCK-119).
- **Cross-plane reconciliation** (:func:`recovery.verify.reconcile_planes`):
  the contracts/journal/evidence planes converge after a drill with
  typed divergence records (the accepted ``evidence/`` LOCK-106
  typing discipline consumed by reference; the drill's evidence
  records cited and preserved).
- **Recovery never fabricates history** (LOCK-106): recovered records
  preserve their original content-derived identities — no historical
  record is rewritten, no gapless sequence is silently renumbered; a
  restored plane is byte-identical or the difference is a typed,
  disclosed, reconciled divergence (construction-is-recovery per the
  accepted journal conventions).
- **Fail-closed recovery** (:func:`recovery.snapshot.verify_recovery_point`):
  an unverifiable snapshot (bad integrity, unparseable,
  provenance-missing) is REJECTED with a typed reason — never
  partially trusted, never best-effort loaded.

Authority boundaries (the layering contract, frozen 1.1):

- **LOCK-101/LOCK-117**: contracts/ stays the sole authority; the
  recovery points, drills and reconciliations ride the contract and
  the accepted journal-bearing planes as opaque references, cite ids,
  never re-derive contract identity, and never write contract,
  runtime or local state — the accepted folds stay the sole writers
  (construction-is-recovery).  Imports flow one way: ``recovery/``
  imports the accepted authorities (contracts, resilience,
  localfirst, evidence); NO accepted authority imports ``recovery/``.
- **LOCK-106**: the drill's evidence records are typed through the
  accepted four-type vocabulary (the plane-loss observation and the
  restore-verification attestation), and the recovered records
  preserve their original content-derived identities — history is
  never fabricated, never renumbered, never rewritten.
- **LOCK-119**: no wall clock, no randomness, no network, no secrets;
  content-derived ids over canonical JSON; canonical-JSON round-trips
  with tamper-evident ids.

Harvest disclosure (R8 charter M017 scope): the legacy 1.0 reservoir
is SOURCE MATERIAL ONLY — no legacy package is imported or modified;
the DR disciplines are re-expressed on the 1.1 authority (the
accepted journal-bearing planes) inside this package.
"""

from __future__ import annotations

from .errors import RecoveryError, RecoveryReason
from .model import (
    CROSS_PLANE_DIVERGENCE_CODES,
    CROSS_PLANE_NAMES,
    CROSS_PLANE_RESOLUTIONS,
    DRILL_ISSUER,
    DRILL_STEP_KINDS,
    OperationBudget,
    OperationCounts,
    PlaneReconciliation,
    PLANE_KINDS,
    RECONCILIATION_OUTCOMES,
    RECOVERY_ISSUER,
    RESTORE_DIVERGENCE_CODES,
    RESTORE_DIVERGENCE_RESOLUTIONS,
    RESTORE_OUTCOMES,
    CrossPlaneDivergence,
    DrillPlan,
    DrillResult,
    DrillStep,
    RecoveryPoint,
    RestoreDivergence,
    RestoreVerification,
    journal_state_digest,
)
from .snapshot import (
    plane_lines_digest,
    plane_record_lines,
    restore_offline_plane,
    restore_runtime_plane,
    snapshot_offline_plane,
    snapshot_runtime_plane,
    verify_recovery_point,
)
from .verify import reconcile_planes, verify_restore
from .drill import (
    PLANE_LOSS_OBSERVATION_VALUE,
    RESTORE_ATTESTATION_DIVERGED,
    RESTORE_ATTESTATION_EXACT,
    run_drill,
)

__all__ = [
    # typed errors
    "RecoveryError",
    "RecoveryReason",
    # frozen vocabularies
    "PLANE_KINDS",
    "CROSS_PLANE_NAMES",
    "DRILL_STEP_KINDS",
    "RESTORE_OUTCOMES",
    "RESTORE_DIVERGENCE_CODES",
    "RESTORE_DIVERGENCE_RESOLUTIONS",
    "CROSS_PLANE_DIVERGENCE_CODES",
    "CROSS_PLANE_RESOLUTIONS",
    "RECONCILIATION_OUTCOMES",
    "RECOVERY_ISSUER",
    "DRILL_ISSUER",
    # typed records
    "OperationBudget",
    "OperationCounts",
    "DrillStep",
    "DrillPlan",
    "RecoveryPoint",
    "RestoreDivergence",
    "RestoreVerification",
    "CrossPlaneDivergence",
    "PlaneReconciliation",
    "DrillResult",
    # snapshot/recovery-point construction + fail-closed verification
    "snapshot_runtime_plane",
    "snapshot_offline_plane",
    "verify_recovery_point",
    "restore_runtime_plane",
    "restore_offline_plane",
    "plane_record_lines",
    "plane_lines_digest",
    "journal_state_digest",
    # restore verification + cross-plane reconciliation
    "verify_restore",
    "reconcile_planes",
    # the deterministic drill engine
    "run_drill",
    "PLANE_LOSS_OBSERVATION_VALUE",
    "RESTORE_ATTESTATION_EXACT",
    "RESTORE_ATTESTATION_DIVERGED",
]
