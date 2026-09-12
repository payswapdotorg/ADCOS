"""ADCOS recovery drill engine (M017 — Disaster Recovery and State
Reconciliation).

The deterministic disaster-recovery drill: the executor of the
replayable drill operation sequence (:class:`~recovery.model.DrillPlan`)
over the journal-bearing state planes, composing the accepted surfaces
BY REFERENCE (the M015 runtime session and the M016 offline journal
driven INSIDE the drills — never duplicated):

    snapshot -> induce loss -> restore -> verify -> reconcile

- :func:`run_drill` — execute the plan's steps in order against the
  drill's plane holders (the caller's live holders for the runtime
  plane and the offline plane; the ACCEPTED stores, driven through
  this surface).  Every step is deterministic (injected instants, no
  wall clock); the same plan + the same plane content -> the
  byte-identical :class:`~recovery.model.DrillResult`.

- **The RTO accounting** (LOCK-119: the recovery-time bound is a
  DECLARED deterministic OPERATION COUNT, never wall clock): the
  engine counts the operations it drives — journal appends (measured
  mechanically as the per-plane record-count deltas across each step,
  the evidence-plane ingests included), folds (the engine-driven
  journal folds: 2 per restore — the accepted construction fold plus
  the accepted integrity re-fold — and 1 per reconcile — the accepted
  resynchronization's episode fold; the append-atomicity folds inside
  the accepted stores are counted within their append operations), and
  verifications (every identity re-derivation, digest computation,
  byte-comparison and cross-plane check the engine performs).  A
  counter that exceeds the declared budget fails closed at the
  increment point with ``recovery-rto-exceeded`` (the deterministic
  detail names the counter, the measured count and the declared
  bound); the measured counts are recorded on the drill result,
  byte-identical across re-runs.

- **The drill's LOCK-106 evidence records** (the evidence-visible
  drill): the induced plane loss is observed by a typed
  ``ObservationEvidence`` (the frozen ``health-state`` metric, the
  NOT_RUNNING ordinal 3 — the plane is lost), and each restore
  verification is attested by a typed ``AttestationEvidence`` (the
  frozen ``controller-verified`` kind; the attested value 1 = a
  byte-exact restore, 0 = a disclosed-and-reconciled divergence).  The
  records are ingested into the caller's accepted
  :class:`~evidence.store.EvidenceStore` (the evidence plane) and
  verified preserved by the reconciliation.  An evidence-producing
  step requires a successor step (its evidence window needs the
  deterministic horizon — the next step's injected instant).

Fail-closed discipline: a loss step for a plane with no recovery
point, a restore step for a plane with no point or with no induced
loss, a verify step for a plane that was not restored, a reconcile
step while a plane is lost, a second snapshot of the same plane, an
evidence-producing final step — each fails closed with the specific
typed reason BEFORE any state changes from that step; the drill never
invents a plane, never partially trusts a snapshot, never absorbs a
divergence silently.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from contracts import ConnectivityContract
from resilience import RuntimeStore
from localfirst import AuthoritySnapshot, OfflineJournal
from evidence import (
    AttestationEvidence,
    EvidenceStore,
    ObservationEvidence,
)

from .errors import RecoveryError, RecoveryReason
from .model import (
    DRILL_ISSUER,
    DrillPlan,
    DrillResult,
    OperationCounts,
    PlaneReconciliation,
    RestoreVerification,
    _wrap_consumed_error,
)
from .snapshot import (
    plane_record_lines,
    restore_offline_plane,
    restore_runtime_plane,
    snapshot_offline_plane,
    snapshot_runtime_plane,
)
from .verify import reconcile_planes, verify_restore

__all__ = [
    "run_drill",
    "PLANE_LOSS_OBSERVATION_VALUE",
    "RESTORE_ATTESTATION_EXACT",
    "RESTORE_ATTESTATION_DIVERGED",
]


#: The drill's LOCK-106 observation value for an induced plane loss
#: (the frozen WORK-016 health-state ordinal: 3 = NOT_RUNNING — the
#: plane is lost, not merely degraded).
PLANE_LOSS_OBSERVATION_VALUE = 3

#: The drill's LOCK-106 attestation value for a byte-exact restore
#: verification.
RESTORE_ATTESTATION_EXACT = 1

#: The drill's LOCK-106 attestation value for a disclosed-and-
#: reconciled restore divergence.
RESTORE_ATTESTATION_DIVERGED = 0


class _RtoLedger:
    """The deterministic RTO accounting (the engine's operation
    counters — NEVER a timing measurement).  Each increment is checked
    against the declared bound at the increment point; a counter that
    would exceed it fails closed immediately (the drill stops at the
    violation, honestly)."""

    __slots__ = ("_budget", "journal_appends", "folds", "verifications")

    def __init__(self, budget) -> None:
        self._budget = budget
        self.journal_appends = 0
        self.folds = 0
        self.verifications = 0

    def count_appends(self, amount: int) -> None:
        self.journal_appends += amount
        self._check("journal_appends")

    def count_folds(self, amount: int) -> None:
        self.folds += amount
        self._check("folds")

    def count_verifications(self, amount: int) -> None:
        self.verifications += amount
        self._check("verifications")

    def _check(self, member: str) -> None:
        measured = getattr(self, member)
        declared = getattr(self._budget, member)
        if measured > declared:
            raise RecoveryError(
                RecoveryReason.RTO_EXCEEDED,
                "the drill's measured %s (%d) exceeds the declared "
                "recovery-time bound (%d) — the bound is a DECLARED "
                "deterministic operation count, never wall clock "
                "(LOCK-119)" % (member, measured, declared),
            )

    def counts(self) -> OperationCounts:
        return OperationCounts(
            journal_appends=self.journal_appends,
            folds=self.folds,
            verifications=self.verifications,
        )


def _evidence_horizon(plan: DrillPlan, index: int) -> str:
    """The deterministic evidence horizon for a step: the NEXT step's
    injected instant (the drill's own next operation — an
    evidence-producing step requires a successor)."""
    if index + 1 >= len(plan.steps):
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT,
            "the %s step at plan position %d produces LOCK-106 evidence and "
            "requires a successor step for its evidence window (the "
            "deterministic horizon is the next step's injected instant)"
            % (plan.steps[index].kind, index + 1),
        )
    return plan.steps[index + 1].recorded_at


def _runtime_records(store: RuntimeStore, runtime_id: object) -> Tuple[object, ...]:
    """The current runtime journal (the ACCEPTED read surface — a raw
    journal read, no fold)."""
    with _wrap_consumed_error("the drill runtime read"):
        return store.events(runtime_id)


def _ingest_observation(
    plane: str,
    subject_id: str,
    contract_id: str,
    instant: str,
    horizon: str,
    store: EvidenceStore,
) -> str:
    """Ingest the LOCK-106 observation of the induced plane loss (the
    plane is NOT_RUNNING — the evidence-visible failure).  Returns the
    accepted record id."""
    with _wrap_consumed_error("the plane-loss observation"):
        record = ObservationEvidence(
            subject_ref=subject_id,
            contract_ref=contract_id,
            instant=instant,
            producer=DRILL_ISSUER,
            metric="health-state",
            value=PLANE_LOSS_OBSERVATION_VALUE,
            confidence_basis_points=10_000,
            freshness_until=horizon,
            source_refs=(contract_id,),
        )
        result = store.ingest(record)
    if not result.accepted:
        raise RecoveryError(
            RecoveryReason.COMPOSITION,
            "the plane-loss observation was not accepted by the evidence "
            "plane: %s" % result.detail[:90],
        )
    return result.record_id


def _ingest_attestation(
    verification: RestoreVerification,
    contract_id: str,
    instant: str,
    horizon: str,
    store: EvidenceStore,
) -> str:
    """Ingest the LOCK-106 attestation of the restore verification
    (the controller-verified outcome — byte-exact or the disclosed
    divergence).  Returns the accepted record id."""
    with _wrap_consumed_error("the restore-verification attestation"):
        record = AttestationEvidence(
            subject_ref=verification.subject_id,
            contract_ref=contract_id,
            instant=instant,
            producer=DRILL_ISSUER,
            attestation_kind="controller-verified",
            attested_value=(
                RESTORE_ATTESTATION_EXACT
                if verification.outcome == "byte-exact"
                else RESTORE_ATTESTATION_DIVERGED
            ),
            valid_until=horizon,
            source_refs=(verification.recovery_point_id,),
        )
        result = store.ingest(record)
    if not result.accepted:
        raise RecoveryError(
            RecoveryReason.COMPOSITION,
            "the restore-verification attestation was not accepted by the "
            "evidence plane: %s" % result.detail[:90],
        )
    return result.record_id


class _DrillState:
    """The engine's per-drill state (the plane holders, the recovery
    points, the captured pre-failure content, the results)."""

    __slots__ = (
        "runtime_holder",
        "runtime_id",
        "offline_holder",
        "points",
        "pre_failure",
        "lost",
        "verifications",
        "point_order",
        "reconciliation",
    )

    def __init__(
        self,
        runtime_holder: RuntimeStore,
        runtime_id: object,
        offline_holder: OfflineJournal,
    ) -> None:
        self.runtime_holder = runtime_holder
        self.runtime_id = runtime_id
        self.offline_holder = offline_holder
        self.points: dict = {}
        self.pre_failure: dict = {}
        self.lost: dict = {}
        self.verifications: List[RestoreVerification] = []
        self.point_order: List[Tuple[str, str]] = []
        self.reconciliation: Optional[PlaneReconciliation] = None


def run_drill(
    plan: DrillPlan,
    *,
    contract: ConnectivityContract,
    runtime_store: RuntimeStore,
    runtime_id: object,
    offline_journal: OfflineJournal,
    evidence_store: EvidenceStore,
    fresh_view: Optional[AuthoritySnapshot] = None,
    resolution_rule: Sequence[str] = ("candidate-kind", "candidate-id"),
) -> DrillResult:
    """Execute the deterministic drill operation sequence (see the
    module docstring).  The same plan + the same plane content + the
    same evidence plane -> the byte-identical drill result (the
    content-derived run id, the deterministic RTO accounting, the
    canonical-JSON round-trippable outcome)."""
    if not isinstance(plan, DrillPlan):
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT,
            "run_drill requires a recovery DrillPlan record (the "
            "deterministic, replayable operation sequence)",
        )
    if not isinstance(contract, ConnectivityContract):
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT,
            "run_drill requires a contracts.ConnectivityContract (got %s)"
            % type(contract).__name__,
        )
    if not isinstance(runtime_store, RuntimeStore):
        raise RecoveryError(
            RecoveryReason.COMPOSITION,
            "run_drill requires a resilience RuntimeStore (got %s) — the "
            "accepted M015 runtime is the composition substrate, consumed BY "
            "REFERENCE" % type(runtime_store).__name__,
        )
    if not isinstance(offline_journal, OfflineJournal):
        raise RecoveryError(
            RecoveryReason.COMPOSITION,
            "run_drill requires a localfirst OfflineJournal (got %s) — the "
            "accepted M016 offline journal is the composition substrate, "
            "consumed BY REFERENCE" % type(offline_journal).__name__,
        )
    if not isinstance(evidence_store, EvidenceStore):
        raise RecoveryError(
            RecoveryReason.COMPOSITION,
            "run_drill requires an evidence EvidenceStore (got %s) — the "
            "accepted LOCK-106 typing is the evidence plane, consumed BY "
            "REFERENCE" % type(evidence_store).__name__,
        )
    if plan.contract_id != contract.contract_id:
        raise RecoveryError(
            RecoveryReason.ID_MISMATCH,
            "the drill plan rides contract %s, not %s — a drill runs on "
            "exactly its owning contract"
            % (plan.contract_id[:23], contract.contract_id[:23]),
        )
    if not isinstance(runtime_id, str) or not runtime_id:
        raise RecoveryError(
            RecoveryReason.INVALID_INPUT,
            "runtime_id must be the drill's runtime session identity (a "
            "non-empty string)",
        )

    state = _DrillState(runtime_store, runtime_id, offline_journal)
    ledger = _RtoLedger(plan.budget)
    evidence_expected: List[Tuple[str, str]] = []

    for index, step in enumerate(plan.steps):
        kind = step.kind
        plane = step.plane
        instant = step.recorded_at

        if kind == "snapshot-plane":
            if plane in state.points:
                raise RecoveryError(
                    RecoveryReason.INVALID_INPUT,
                    "the drill snapshots the %s plane twice — a plane carries "
                    "one recovery point per drill run (the second snapshot "
                    "would orphan the first)" % plane,
                )
            if state.lost.get(plane):
                raise RecoveryError(
                    RecoveryReason.INVALID_INPUT,
                    "the drill snapshots the %s plane after its induced loss "
                    "(a lost plane has no holder to snapshot — restore it "
                    "first)" % plane,
                )
            if plane == "runtime-journal":
                point = snapshot_runtime_plane(
                    state.runtime_holder,
                    state.runtime_id,
                    recorded_at=instant,
                    provenance=step.provenance,
                )
            else:
                point = snapshot_offline_plane(
                    state.offline_holder,
                    recorded_at=instant,
                    provenance=step.provenance,
                )
            state.points[plane] = point
            state.point_order.append((plane, point.recovery_point_id))
            # the RTO accounting: the snapshot's verification
            # operations (the content-derived identity derivation and
            # the plane digest computation over every captured record)
            ledger.count_verifications(len(point.record_lines) + 1)

        elif kind == "induce-plane-loss":
            if plane not in state.points:
                raise RecoveryError(
                    RecoveryReason.INVALID_INPUT,
                    "the drill induces the %s plane loss BEFORE its snapshot "
                    "— a loss without a recovery point is unrecoverable by "
                    "construction (fail closed)" % plane,
                )
            if state.lost.get(plane):
                raise RecoveryError(
                    RecoveryReason.INVALID_INPUT,
                    "the %s plane is already lost (induce the loss once per "
                    "restore round)" % plane,
                )
            if plane == "runtime-journal":
                pre_records = _runtime_records(
                    state.runtime_holder, state.runtime_id
                )
            else:
                pre_records = state.offline_holder.records()
            state.pre_failure[plane] = plane_record_lines(pre_records)
            state.lost[plane] = True
            # the LOCK-106 observation of the loss (evidence-visible;
            # the journal-append count is the evidence-plane record
            # delta — an idempotent re-ingest grows the journal by 0,
            # measured honestly)
            horizon = _evidence_horizon(plan, index)
            before_evidence = len(evidence_store)
            record_id = _ingest_observation(
                plane,
                state.points[plane].subject_id,
                contract.contract_id,
                instant,
                horizon,
                evidence_store,
            )
            evidence_expected.append((plane, record_id))
            ledger.count_appends(len(evidence_store) - before_evidence)

        elif kind == "restore-plane":
            point = state.points.get(plane)
            if point is None:
                raise RecoveryError(
                    RecoveryReason.INVALID_INPUT,
                    "the drill restores the %s plane without a recovery point "
                    "(fail closed — never best-effort)" % plane,
                )
            if not state.lost.get(plane):
                raise RecoveryError(
                    RecoveryReason.INVALID_INPUT,
                    "the drill restores the %s plane without an induced loss "
                    "(the restore step follows the loss step)" % plane,
                )
            if plane == "runtime-journal":
                with _wrap_consumed_error("the runtime-plane restore"):
                    restored = restore_runtime_plane(point)
                state.runtime_holder = restored
            else:
                with _wrap_consumed_error("the offline-plane restore"):
                    restored = restore_offline_plane(point)
                state.offline_holder = restored
            state.lost[plane] = False
            # the RTO accounting: the fail-closed point verification
            # (one identity re-derivation per record plus the digest)
            # and the accepted construction-is-recovery folds (the
            # construction fold plus the integrity re-fold)
            ledger.count_verifications(len(point.record_lines) + 1)
            ledger.count_folds(2)

        elif kind == "verify-restore":
            point = state.points.get(plane)
            if point is None:
                raise RecoveryError(
                    RecoveryReason.INVALID_INPUT,
                    "the drill verifies the %s plane restore without a "
                    "recovery point" % plane,
                )
            if state.lost.get(plane) is not False:
                raise RecoveryError(
                    RecoveryReason.INVALID_INPUT,
                    "the drill verifies the %s plane while it is lost (the "
                    "verify step follows the restore step)" % plane,
                )
            if plane == "runtime-journal":
                restored_lines = plane_record_lines(
                    _runtime_records(state.runtime_holder, state.runtime_id)
                )
            else:
                restored_lines = plane_record_lines(
                    state.offline_holder.records()
                )
            verification = verify_restore(
                point,
                state.pre_failure[plane],
                restored_lines,
                recorded_at=instant,
                provenance=step.provenance,
            )
            state.verifications.append(verification)
            # the LOCK-106 attestation of the verification outcome
            # (the journal-append count is the evidence-plane record
            # delta — measured, never presumed)
            horizon = _evidence_horizon(plan, index)
            before_evidence = len(evidence_store)
            record_id = _ingest_attestation(
                verification,
                contract.contract_id,
                instant,
                horizon,
                evidence_store,
            )
            evidence_expected.append((plane, record_id))
            ledger.count_appends(len(evidence_store) - before_evidence)
            # the RTO accounting: the verification's identity
            # comparisons (restored vs point, pre-failure vs point —
            # two per record) plus the digest computations
            ledger.count_verifications(
                2 * len(point.record_lines)
                + 2 * len(state.pre_failure[plane])
                + 2
            )

        elif kind == "reconcile-planes":
            if state.lost.get("runtime-journal") or state.lost.get("offline-journal"):
                raise RecoveryError(
                    RecoveryReason.INVALID_INPUT,
                    "the drill reconciles the planes while a journal plane is "
                    "lost (restore and verify the planes first)",
                )
            before_runtime = len(
                _runtime_records(state.runtime_holder, state.runtime_id)
            )
            before_offline = len(state.offline_holder.records())
            before_evidence = len(evidence_store)
            reconciliation, _close = reconcile_planes(
                drill_id=plan.drill_id,
                contract=contract,
                runtime_store=state.runtime_holder,
                runtime_id=state.runtime_id,
                offline_journal=state.offline_holder,
                evidence_store=evidence_store,
                expected_evidence=tuple(evidence_expected),
                fresh_view=fresh_view,
                resolution_rule=resolution_rule,
                recorded_at=instant,
                provenance=step.provenance,
            )
            state.reconciliation = reconciliation
            # the RTO accounting: the journal appends the convergence
            # drive performed (measured mechanically as the per-plane
            # record-count deltas), the accepted resynchronization's
            # episode fold, and the cross-plane verification checks
            after_runtime = len(
                _runtime_records(state.runtime_holder, state.runtime_id)
            )
            after_offline = len(state.offline_holder.records())
            after_evidence = len(evidence_store)
            ledger.count_appends(
                (after_runtime - before_runtime)
                + (after_offline - before_offline)
                + (after_evidence - before_evidence)
            )
            ledger.count_folds(1)
            ledger.count_verifications(
                1  # the contract fingerprint consumption
                + len(reconciliation.evidence_record_ids)  # the preservation checks
                + 2  # the plane digest computations
            )

        else:  # pragma: no cover - the frozen vocabulary guard
            raise RecoveryError(
                RecoveryReason.VOCABULARY,
                "the drill step kind %r is outside the frozen vocabulary" % kind,
            )

    return DrillResult(
        drill_run_id="",
        drill_id=plan.drill_id,
        contract_id=contract.contract_id,
        recovery_points=tuple(state.point_order),
        restorations=tuple(state.verifications),
        reconciliation=state.reconciliation,
        measured_counts=ledger.counts(),
        declared_budget=plan.budget,
        completed_at=plan.steps[-1].recorded_at,
        provenance=plan.provenance,
    )
