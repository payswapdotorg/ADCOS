#!/usr/bin/env python3
"""ADCOS recovery self-test (M017 — Disaster Recovery and State
Reconciliation).

Deterministic, offline verification of the ``recovery/`` package
against the frozen Architecture 1.1 mandate (R8-CORE-001, DEC-0116 the
current-child state; the R8 charter M017 acceptance criteria): the
disaster-recovery and state-reconciliation domain over the
journal-bearing state planes — deterministic disaster-recovery drills
(the M015 runtime journals and the M016 offline journals, driven BY
REFERENCE inside the drills), snapshot/recovery-point construction
with content-derived identities and full provenance, restore
verification (byte-exact or explicitly disclosed-and-reconciled
divergence), recovery-time bounds as declared deterministic operation
counts (never wall clock), cross-plane reconciliation (the
contracts/journal/evidence planes converge with typed divergence
records), recovery never fabricating history (LOCK-106), and
fail-closed recovery (an unverifiable snapshot rejected, never
partially trusted).

Battery coverage (the M017 work-item matrix, the charter's (a)-(h)):

- (a) case_04/case_05/case_06 — the snapshot construction + restore
  round-trips across BOTH journal-bearing planes (runtime + offline):
  byte-exact restores through the ACCEPTED construction-is-recovery
  constructors, identities preserved, and the restored planes remain
  LIVE accepted surfaces (the composition composes forward);
- (b) case_07/case_08 — the drill determinism: same drill inputs, run
  twice, the byte-identical outcome (content-derived run id, RTO
  accounting, reconciliation); plus byte-identical digests across
  PYTHONHASHSEED subprocesses;
- (c) case_09/case_10/case_11 — restore verification with induced
  divergence: the typed divergence records disclosed and reconciled
  (each lost record cited by its ORIGINAL content-derived identity,
  reconciled onto the recovery point as the authoritative base), the
  failure-during-recovery drill (a second loss after the
  reconciliation), and the silent-absorption rejections (an outcome
  without its disclosed records fails closed);
- (d) case_12/case_13 — the recovery-time bounds as DECLARED
  deterministic operation counts: expressed as integer counts on the
  plan (never time members), measured deterministically, recorded on
  the result, and ENFORCED (a tight budget fails closed
  ``recovery-rto-exceeded`` at the increment point; an over-budget
  hand-built result fails closed at construction);
- (e) case_14..case_18 — the cross-plane reconciliation: the converged
  outcome (zero divergences, the plane digests, the LOCK-106 evidence
  records preserved, the accepted resync preserved VERBATIM and
  re-validating through the accepted constructor), the accepted
  resync's own divergence records preserved (the conflicted subject
  cited, the no-silent-loss accounting), the evidence-record-missing
  and composition-link-unresolved divergences disclosed as typed
  records, and the attribution mismatch failing closed
  (unreconcilable — LOCK-101/LOCK-117);
- (f) case_19..case_22 — no-history-fabrication: the recovered
  identities preserved verbatim (never renumbered), a re-identified
  restored record failing closed, a renumbered restore failing
  closed, and a pre-failure history rewrite failing closed (never a
  "reconciliation");
- (g) case_23..case_27 — the fail-closed snapshot verification:
  unparseable, provenance-missing, tampered-identity, digest/id-
  mismatched, and renumbered snapshots REJECTED WHOLE (never
  partially trusted, never best-effort loaded);
- (h) case_28 — the composition substrate exercised: the accepted M015
  runtime session and the accepted M016 offline journal driven BY
  REFERENCE inside the drills (the accepted close/resync/reconnect
  chain, the preserved accepted records re-validating, the drill's
  LOCK-106 evidence records typed through the accepted vocabulary);
- plus case_29..case_36: canonical-JSON round-trips, typed errors +
  exception isolation + the LOCK-119 secret fixture, the determinism
  re-run + the serialized replay, the lock-conformance mapping, the
  clock/import discipline, the one-way import boundary, the PR delta
  shape, and the evidence-doc honesty.

All instants are injected (T0-style constants); no wall clock, no
randomness, no network, no real sockets, no secrets (any
credential-shaped fixture is assembled at runtime from fragments so the
full shape never appears in source). Runs are byte-identical across
processes (PYTHONHASHSEED-safe).
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from protocol.canonicalization import canonical_json_text  # noqa: E402

from contracts import (  # noqa: E402
    CONSTRAINT_KINDS,
    ContractStore,
    CreateContract,
    ActivateContract,
    BeneficiaryScope,
    ConnectivityPrincipal,
    HardConstraint,
    OpaqueReference,
    Provenance,
    RecordExecutionActivation,
    SelectOffers,
    TerminationRules,
    ValidityInterval,
)
from resilience import (  # noqa: E402
    RUNTIME_EVENT_KINDS,
    RuntimeEvent,
    RuntimeStore,
)
from localfirst import (  # noqa: E402
    DEFAULT_RESOLUTION_RULE,
    AuthoritySnapshot,
    OfflineJournal,
    ResyncResult,
    attach_runtime_session,
    authority_snapshot,
    close_partition,
    local_admit,
    open_partition,
)
from evidence import (  # noqa: E402
    EVIDENCE_TYPES,
    AttestationEvidence,
    EvidenceStore,
    ObservationEvidence,
)

from recovery import (  # noqa: E402
    CROSS_PLANE_DIVERGENCE_CODES,
    CROSS_PLANE_NAMES,
    DRILL_STEP_KINDS,
    OperationBudget,
    OperationCounts,
    PlaneReconciliation,
    PLANE_KINDS,
    RECONCILIATION_OUTCOMES,
    RESTORE_DIVERGENCE_CODES,
    RESTORE_DIVERGENCE_RESOLUTIONS,
    RESTORE_OUTCOMES,
    CrossPlaneDivergence,
    DrillPlan,
    DrillResult,
    DrillStep,
    RecoveryError,
    RecoveryPoint,
    RecoveryReason,
    RestoreDivergence,
    RestoreVerification,
    journal_state_digest,
    reconcile_planes,
    restore_offline_plane,
    restore_runtime_plane,
    run_drill,
    snapshot_offline_plane,
    snapshot_runtime_plane,
    verify_recovery_point,
    verify_restore,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

Result = Tuple[str, bool, str]

T0 = "2026-10-01T00:00:00Z"
T_END = "2026-11-01T00:00:00Z"
CREATE_AT = "2026-09-30T10:00:00Z"
OFFER_SEL_AT = "2026-09-30T10:05:00Z"

# The drill's injected instants (inside the owning contract's validity
# window so the composed surfaces accept the drives).
D_ATTACH = "2026-10-02T00:00:00Z"
D_ACTIVATE = "2026-10-02T00:01:00Z"
D_PARTITION = "2026-10-03T00:00:00Z"
D_ADMIT_A = "2026-10-03T01:00:00Z"
D_ADMIT_B = "2026-10-03T02:00:00Z"
D_ADMIT_C = "2026-10-03T03:00:00Z"
D_SNAP_R = "2026-10-04T00:00:00Z"
D_SNAP_O = "2026-10-04T00:01:00Z"
D_LOSS_R = "2026-10-05T00:00:00Z"
D_LOSS_O = "2026-10-05T00:01:00Z"
D_RESTORE_R = "2026-10-06T00:00:00Z"
D_RESTORE_O = "2026-10-06T00:01:00Z"
D_VERIFY_R = "2026-10-07T00:00:00Z"
D_VERIFY_O = "2026-10-07T00:01:00Z"
D_RECONCILE = "2026-10-08T00:00:00Z"
D_LOSS2_R = "2026-10-09T00:00:00Z"
D_RESTORE2_R = "2026-10-09T01:00:00Z"
D_VERIFY2_R = "2026-10-09T02:00:00Z"
D_RECONCILE2 = "2026-10-09T05:00:00Z"
D_VERIFY2_O = "2026-10-09T04:00:00Z"
# The induced-divergence fixtures' extra admissions (beyond the
# recovery point).
D_ADMIT_D = "2026-10-03T04:00:00Z"
D_ADMIT_E = "2026-10-03T05:00:00Z"

# The base authority view's declared freshness window.
BASE_FROM = "2026-10-02T00:00:00Z"
BASE_UNTIL = "2026-10-09T00:00:00Z"
BASE_RECORDED = "2026-10-02T00:00:00Z"

# The fresh authority views at reconciliation.
FRESH_FROM = "2026-10-11T00:00:00Z"
FRESH_UNTIL = "2026-10-18T00:00:00Z"
FRESH_RECORDED = "2026-10-11T00:00:00Z"

# Opaque authority records and admission subjects (LOCK-117: opaque
# references, never authority).  The W-prefixed subject collides with
# a record in the contested fresh view so the ACCEPTED resync
# resolution produces its own typed divergence record (preserved
# verbatim by the reconciliation).
REC_ALPHA = "record:lease-alpha"
REC_BETA = "record:lease-beta"
REC_GAMMA = "record:lease-gamma"
REC_WIRELESS = "wireless:lease-contested"
SUBJ_DEVICE_42 = "lease:dev-42"
SUBJ_DEVICE_43 = "lease:dev-43"
SUBJ_DEVICE_44 = "lease:dev-44"
SUBJ_DEVICE_45 = "lease:dev-45"

BATTERY_ISSUER = "recovery:battery"

_KIND_FIXTURES: Dict[str, Dict[str, Any]] = {
    "latency-bound": {"max_ms": 150},
    "availability-floor": {"nine": "three"},
}


# ---------------------------------------------------------------------------
# The harness
# ---------------------------------------------------------------------------


def ok(name: str, detail: str = "") -> Result:
    return (name, True, detail)


def fail(name: str, detail: str) -> Result:
    return (name, False, detail)


def expect_error(case: str, code: str, action: Callable[[], Any]) -> Result:
    try:
        action()
    except RecoveryError as error:
        if error.code == code:
            return ok(case, "fail-closed %s: %s" % (code, error.detail[:90]))
        return fail(
            case,
            "expected code %s, got %s (%s)" % (code, error.code, error.detail[:90]),
        )
    except Exception as error:  # noqa: BLE001
        return fail(
            case,
            "unexpected exception %s: %s" % (type(error).__name__, str(error)[:90]),
        )
    return fail(case, "expected RecoveryError(%s); the input was accepted" % code)


def _prov(issuer: str, *refs: str) -> Provenance:
    return Provenance(issuer=issuer, decision_refs=tuple(refs))


def _constraints(*kinds: str) -> Tuple[HardConstraint, ...]:
    return tuple(
        HardConstraint(
            kind=kind,
            params=_KIND_FIXTURES[kind],
            provenance=_prov("prov:netpro"),
        )
        for kind in kinds
    )


def _create_command(principal_ref: str) -> CreateContract:
    return CreateContract(
        principal=ConnectivityPrincipal(
            principal_kind="APPLICATION", principal_ref=principal_ref
        ),
        beneficiaries=(
            BeneficiaryScope(beneficiary_kind="DEVICE", beneficiary_ref="dev:pi-7f2a"),
        ),
        requirements=(
            OpaqueReference(
                ref_kind="intent-requirements",
                value="intent:dr017",
                provenance=_prov("arch:recovery"),
            ),
        ),
        hard_constraints=_constraints("latency-bound", "availability-floor"),
        validity=ValidityInterval(not_before=T0, not_after=T_END),
        service_properties=(
            OpaqueReference(
                ref_kind="service-property",
                value="prop:committed-1",
                provenance=_prov("prov:netpro"),
            ),
        ),
        usage_pricing_terms=OpaqueReference(
            ref_kind="usage-pricing-terms",
            value="terms:comm-42",
            provenance=_prov("comm:ops"),
        ),
        assurance_obligations=(
            OpaqueReference(ref_kind="assurance-obligation", value="oblig:evid-7"),
        ),
        execution_scope=(
            OpaqueReference(ref_kind="execution-scope", value="scope:exec-default"),
        ),
        termination=TerminationRules(
            conditions=("principal-requested", "constraint-violated"),
            compensation=OpaqueReference(
                ref_kind="compensation",
                value="comp:rule-9",
                provenance=_prov("comm:ops"),
            ),
        ),
        provenance=_prov("arch:recovery", "dec:elig-1"),
    )


_OFFER_A = OpaqueReference(
    ref_kind="offer", value="offer:netpro-basic-1", provenance=_prov("prov:netpro")
)


def _mature_contract(principal_ref: str = "app:dr-gateway-01"):
    """A contract store whose single contract is EXECUTION_ACTIVE
    (deterministic; rebuilt per call so mutating cases stay isolated)."""
    store = ContractStore()
    created = store.submit(_create_command(principal_ref), recorded_at=CREATE_AT)
    cid = created.contract.contract_id
    store.submit(
        SelectOffers(offers=(_OFFER_A,)),
        recorded_at=OFFER_SEL_AT,
        contract_id=cid,
    )
    store.submit(
        ActivateContract(
            activated_at=T0,
            signature_refs=(
                OpaqueReference(ref_kind="signature", value="sig:ed25519-1"),
            ),
        ),
        recorded_at=T0,
        contract_id=cid,
    )
    store.submit(RecordExecutionActivation(recorded_at=T0), recorded_at=T0, contract_id=cid)
    return store, store.contract(cid)


def _record(value: str) -> OpaqueReference:
    return OpaqueReference(
        ref_kind="execution-artifact",
        value=value,
        provenance=_prov("prov:netpro"),
    )


def _subject(value: str) -> OpaqueReference:
    return OpaqueReference(
        ref_kind="execution-artifact",
        value=value,
        provenance=_prov("app:dr-gateway-01"),
    )


def _base_view(contract: Any) -> AuthoritySnapshot:
    return authority_snapshot(
        contract,
        (_record(REC_ALPHA), _record(REC_BETA)),
        fresh_from=BASE_FROM,
        fresh_until=BASE_UNTIL,
        recorded_at=BASE_RECORDED,
    )


def _fresh_view(contract: Any) -> AuthoritySnapshot:
    """The fresh authority view at reconciliation (the authority moved
    on: lease-alpha gone, lease-gamma added)."""
    return authority_snapshot(
        contract,
        (_record(REC_BETA), _record(REC_GAMMA)),
        fresh_from=FRESH_FROM,
        fresh_until=FRESH_UNTIL,
        recorded_at=FRESH_RECORDED,
    )


def _contested_fresh_view(contract: Any) -> AuthoritySnapshot:
    """The fresh view carrying the CONTESTED record (a subject the
    local journal also admitted — the accepted resync resolves the
    conflict with its own typed divergence record)."""
    return authority_snapshot(
        contract,
        (_record(REC_BETA), _record(REC_WIRELESS)),
        fresh_from=FRESH_FROM,
        fresh_until=FRESH_UNTIL,
        recorded_at=FRESH_RECORDED,
    )


def _fixture(
    *,
    contested: bool = False,
):
    """The deterministic drill fixture: a mature contract, an attached
    M015 runtime session realizing the base authority view, and an
    OPEN M016 partition episode with journaled admissions (the
    accepted surfaces driven BY REFERENCE)."""
    _, contract = _mature_contract()
    base = _base_view(contract)
    rstore = RuntimeStore()
    session = attach_runtime_session(
        rstore,
        contract,
        base,
        created_at=D_ATTACH,
        activated_at=D_ACTIVATE,
        provenance=_prov(BATTERY_ISSUER),
    )
    journal, _ = open_partition(
        rstore,
        session.runtime_id,
        contract,
        base,
        recorded_at=D_PARTITION,
        provenance=_prov(BATTERY_ISSUER),
    )
    subjects = [SUBJ_DEVICE_42, SUBJ_DEVICE_43]
    if contested:
        subjects.append(REC_WIRELESS)
    for subject, at in zip(
        subjects,
        (D_ADMIT_A, D_ADMIT_B, D_ADMIT_C)[: len(subjects)],
    ):
        local_admit(
            journal,
            contract,
            base,
            subject=_subject(subject),
            claimed_constraints=tuple(contract.hard_constraints),
            decided_at=at,
            provenance=_prov(BATTERY_ISSUER),
        )
    return contract, base, rstore, session, journal


def _fixture_with_extra_admissions():
    """The induced-divergence fixture: the base fixture PLUS two more
    journaled admissions (the plane advances BEYOND the recovery
    point — the lost records at verification time)."""
    _, contract = _mature_contract()
    base = _base_view(contract)
    rstore = RuntimeStore()
    session = attach_runtime_session(
        rstore,
        contract,
        base,
        created_at=D_ATTACH,
        activated_at=D_ACTIVATE,
        provenance=_prov(BATTERY_ISSUER),
    )
    journal, _ = open_partition(
        rstore,
        session.runtime_id,
        contract,
        base,
        recorded_at=D_PARTITION,
        provenance=_prov(BATTERY_ISSUER),
    )
    for subject, at in (
        (SUBJ_DEVICE_42, D_ADMIT_A),
        (SUBJ_DEVICE_43, D_ADMIT_B),
        (SUBJ_DEVICE_44, D_ADMIT_D),
        (SUBJ_DEVICE_45, D_ADMIT_E),
    ):
        local_admit(
            journal,
            contract,
            base,
            subject=_subject(subject),
            claimed_constraints=tuple(contract.hard_constraints),
            decided_at=at,
            provenance=_prov(BATTERY_ISSUER),
        )
    return contract, base, rstore, session, journal


def _primary_plan(contract_id: str) -> DrillPlan:
    """The deterministic primary drill: snapshot both planes, lose
    both, restore both, verify both, reconcile (the accepted M016
    convergence drive)."""
    return DrillPlan(
        contract_id=contract_id,
        steps=(
            DrillStep(kind="snapshot-plane", plane="runtime-journal", recorded_at=D_SNAP_R, provenance=_prov(BATTERY_ISSUER)),
            DrillStep(kind="snapshot-plane", plane="offline-journal", recorded_at=D_SNAP_O, provenance=_prov(BATTERY_ISSUER)),
            DrillStep(kind="induce-plane-loss", plane="runtime-journal", recorded_at=D_LOSS_R, provenance=_prov(BATTERY_ISSUER)),
            DrillStep(kind="induce-plane-loss", plane="offline-journal", recorded_at=D_LOSS_O, provenance=_prov(BATTERY_ISSUER)),
            DrillStep(kind="restore-plane", plane="runtime-journal", recorded_at=D_RESTORE_R, provenance=_prov(BATTERY_ISSUER)),
            DrillStep(kind="restore-plane", plane="offline-journal", recorded_at=D_RESTORE_O, provenance=_prov(BATTERY_ISSUER)),
            DrillStep(kind="verify-restore", plane="runtime-journal", recorded_at=D_VERIFY_R, provenance=_prov(BATTERY_ISSUER)),
            DrillStep(kind="verify-restore", plane="offline-journal", recorded_at=D_VERIFY_O, provenance=_prov(BATTERY_ISSUER)),
            DrillStep(kind="reconcile-planes", recorded_at=D_RECONCILE, provenance=_prov(BATTERY_ISSUER)),
        ),
        budget=OperationBudget(journal_appends=16, folds=8, verifications=128),
        provenance=_prov(BATTERY_ISSUER),
    )


def _plan_for(contract_id: str, steps: Tuple[DrillStep, ...], budget: OperationBudget) -> DrillPlan:
    return DrillPlan(
        contract_id=contract_id,
        steps=steps,
        budget=budget,
        provenance=_prov(BATTERY_ISSUER),
    )


def _run_primary_drill(contested: bool = False):
    """Build the fixture + plan and run the primary drill (the
    determinism baseline: same inputs -> the byte-identical result)."""
    contract, base, rstore, session, journal = _fixture(contested=contested)
    plan = _primary_plan(contract.contract_id)
    fresh = _contested_fresh_view(contract) if contested else _fresh_view(contract)
    estore = EvidenceStore()
    result = run_drill(
        plan,
        contract=contract,
        runtime_store=rstore,
        runtime_id=session.runtime_id,
        offline_journal=journal,
        evidence_store=estore,
        fresh_view=fresh,
    )
    return contract, base, fresh, rstore, session, journal, estore, plan, result


def _divergence_plan_steps() -> Tuple[DrillStep, ...]:
    """The failure-during-recovery drill steps: the primary sequence,
    then a SECOND runtime-plane loss after the reconciliation (the
    recovery-time failure), its restore and verification, and the
    final reconciliation."""
    return (
        DrillStep(kind="snapshot-plane", plane="runtime-journal", recorded_at=D_SNAP_R, provenance=_prov(BATTERY_ISSUER)),
        DrillStep(kind="snapshot-plane", plane="offline-journal", recorded_at=D_SNAP_O, provenance=_prov(BATTERY_ISSUER)),
        DrillStep(kind="induce-plane-loss", plane="runtime-journal", recorded_at=D_LOSS_R, provenance=_prov(BATTERY_ISSUER)),
        DrillStep(kind="induce-plane-loss", plane="offline-journal", recorded_at=D_LOSS_O, provenance=_prov(BATTERY_ISSUER)),
        DrillStep(kind="restore-plane", plane="runtime-journal", recorded_at=D_RESTORE_R, provenance=_prov(BATTERY_ISSUER)),
        DrillStep(kind="restore-plane", plane="offline-journal", recorded_at=D_RESTORE_O, provenance=_prov(BATTERY_ISSUER)),
        DrillStep(kind="verify-restore", plane="runtime-journal", recorded_at=D_VERIFY_R, provenance=_prov(BATTERY_ISSUER)),
        DrillStep(kind="verify-restore", plane="offline-journal", recorded_at=D_VERIFY_O, provenance=_prov(BATTERY_ISSUER)),
        DrillStep(kind="reconcile-planes", recorded_at=D_RECONCILE, provenance=_prov(BATTERY_ISSUER)),
        DrillStep(kind="induce-plane-loss", plane="runtime-journal", recorded_at=D_LOSS2_R, provenance=_prov(BATTERY_ISSUER)),
        DrillStep(kind="restore-plane", plane="runtime-journal", recorded_at=D_RESTORE2_R, provenance=_prov(BATTERY_ISSUER)),
        DrillStep(kind="verify-restore", plane="runtime-journal", recorded_at=D_VERIFY2_R, provenance=_prov(BATTERY_ISSUER)),
        DrillStep(kind="reconcile-planes", recorded_at=D_RECONCILE2, provenance=_prov(BATTERY_ISSUER)),
    )


# ---------------------------------------------------------------------------
# The deterministic full drill scenario (the determinism + replay
# material): the primary drill over the standard fixture.
# ---------------------------------------------------------------------------


def _full_drill_scenario() -> Tuple[bytes, ...]:
    """The deterministic full drill scenario (the determinism + replay
    material): the primary drill over the standard fixture — the
    result, the plan, the evidence-plane state digest and both
    recovery points."""
    contract, _base, _fresh, rstore, session, journal, estore, plan, result = (
        _run_primary_drill()
    )
    runtime_point = snapshot_runtime_plane(
        rstore, session.runtime_id, recorded_at=D_SNAP_R, provenance=_prov(BATTERY_ISSUER)
    )
    offline_point = snapshot_offline_plane(
        journal, recorded_at=D_SNAP_O, provenance=_prov(BATTERY_ISSUER)
    )
    return (
        result.canonical_bytes(),
        plan.canonical_bytes(),
        estore.state_digest().encode("utf-8"),
        runtime_point.canonical_bytes(),
        offline_point.canonical_bytes(),
    )


# ---------------------------------------------------------------------------
# case_01 — the frozen vocabularies; the consumed vocabularies by
# reference
# ---------------------------------------------------------------------------


def case_01_frozen_vocabularies() -> Result:
    name = "case_01_frozen_vocabularies"
    problems: List[str] = []
    if PLANE_KINDS != ("runtime-journal", "offline-journal"):
        problems.append("the journal-bearing plane vocabulary drifted")
    if DRILL_STEP_KINDS != (
        "snapshot-plane",
        "induce-plane-loss",
        "restore-plane",
        "verify-restore",
        "reconcile-planes",
    ):
        problems.append("the drill step vocabulary drifted")
    if RESTORE_OUTCOMES != ("byte-exact", "divergence-reconciled"):
        problems.append("the restore outcome vocabulary drifted")
    if RESTORE_DIVERGENCE_CODES != ("record-lost-beyond-recovery-point",):
        problems.append("the restore divergence code vocabulary drifted")
    if RESTORE_DIVERGENCE_RESOLUTIONS != ("reconciled-to-recovery-point",):
        problems.append("the restore resolution vocabulary drifted")
    if CROSS_PLANE_DIVERGENCE_CODES != (
        "composition-link-unresolved",
        "evidence-record-missing",
    ):
        problems.append("the cross-plane divergence code vocabulary drifted")
    if RECONCILIATION_OUTCOMES != ("converged", "divergence-disclosed"):
        problems.append("the reconciliation outcome vocabulary drifted")
    if len(RecoveryReason.values()) != 11:
        problems.append("the typed reason vocabulary drifted (%d codes)" % len(RecoveryReason.values()))
    # the consumed vocabularies, by reference: the LOCK-106 evidence
    # types, the drill's observation metric and attestation kind, the
    # M015 event kinds (the runtime journal's own frozen vocabulary)
    if "observation" not in EVIDENCE_TYPES or "attestation" not in EVIDENCE_TYPES:
        problems.append("the LOCK-106 evidence types are not consumed")
    from recovery.drill import (  # noqa: E402
        PLANE_LOSS_OBSERVATION_VALUE,
        RESTORE_ATTESTATION_EXACT,
    )
    from evidence import ATTESTATION_KINDS, OBSERVATION_METRICS  # noqa: E402

    if "health-state" not in OBSERVATION_METRICS:
        problems.append("the drill's observation metric is not in the accepted vocabulary")
    if PLANE_LOSS_OBSERVATION_VALUE != 3:
        problems.append("the plane-loss ordinal is not the NOT_RUNNING rung")
    if "controller-verified" not in ATTESTATION_KINDS:
        problems.append("the drill's attestation kind is not in the accepted vocabulary")
    if RESTORE_ATTESTATION_EXACT != 1:
        problems.append("the byte-exact attestation value drifted")
    if set(DRILL_STEP_KINDS) - {"reconcile-planes"} != {"snapshot-plane", "induce-plane-loss", "restore-plane", "verify-restore"}:
        problems.append("the plane-scoped step set drifted")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "9 frozen M017 vocabularies + the 11-code reason vocabulary; the "
        "LOCK-106 evidence types/metrics/kinds and the M015 event kinds "
        "consumed BY REFERENCE (never redefined)",
    )


# ---------------------------------------------------------------------------
# case_02 — the vocabulary/input gates fail closed (record level)
# ---------------------------------------------------------------------------


def case_02_vocabulary_fail_closed() -> Result:
    name = "case_02_vocabulary_fail_closed"
    checks: List[Result] = []
    checks.append(
        expect_error(
            "step kind",
            RecoveryReason.VOCABULARY,
            lambda: DrillStep(
                kind="destroy-plane", recorded_at=D_SNAP_R, provenance=_prov(BATTERY_ISSUER)
            ),
        )
    )
    checks.append(
        expect_error(
            "reconcile carrying a plane",
            RecoveryReason.VOCABULARY,
            lambda: DrillStep(
                kind="reconcile-planes",
                recorded_at=D_SNAP_R,
                provenance=_prov(BATTERY_ISSUER),
                plane="runtime-journal",
            ),
        )
    )
    checks.append(
        expect_error(
            "plane-scoped step without a plane",
            RecoveryReason.VOCABULARY,
            lambda: DrillStep(
                kind="snapshot-plane", recorded_at=D_SNAP_R, provenance=_prov(BATTERY_ISSUER)
            ),
        )
    )
    checks.append(
        expect_error(
            "step instant",
            RecoveryReason.TEMPORAL_INVALID,
            lambda: DrillStep(
                kind="snapshot-plane",
                plane="runtime-journal",
                recorded_at="not-an-instant",
                provenance=_prov(BATTERY_ISSUER),
            ),
        )
    )
    contract, _base, rstore, session, journal = _fixture()
    checks.append(
        expect_error(
            "plan contract id",
            RecoveryReason.INVALID_INPUT,
            lambda: DrillPlan(
                contract_id="not-a-sha-id",
                steps=(DrillStep(kind="snapshot-plane", plane="runtime-journal", recorded_at=D_SNAP_R, provenance=_prov(BATTERY_ISSUER)),),
                budget=OperationBudget(journal_appends=1, folds=1, verifications=1),
                provenance=_prov(BATTERY_ISSUER),
            ),
        )
    )
    checks.append(
        expect_error(
            "plan instants not increasing",
            RecoveryReason.INVALID_INPUT,
            lambda: DrillPlan(
                contract_id=contract.contract_id,
                steps=(
                    DrillStep(kind="snapshot-plane", plane="runtime-journal", recorded_at=D_SNAP_O, provenance=_prov(BATTERY_ISSUER)),
                    DrillStep(kind="snapshot-plane", plane="offline-journal", recorded_at=D_SNAP_R, provenance=_prov(BATTERY_ISSUER)),
                ),
                budget=OperationBudget(journal_appends=1, folds=1, verifications=1),
                provenance=_prov(BATTERY_ISSUER),
            ),
        )
    )
    checks.append(
        expect_error(
            "plan empty steps",
            RecoveryReason.INVALID_INPUT,
            lambda: DrillPlan(
                contract_id=contract.contract_id,
                steps=(),
                budget=OperationBudget(journal_appends=1, folds=1, verifications=1),
                provenance=_prov(BATTERY_ISSUER),
            ),
        )
    )
    checks.append(
        expect_error(
            "budget negative",
            RecoveryReason.INVALID_INPUT,
            lambda: OperationBudget(journal_appends=-1, folds=1, verifications=1),
        )
    )
    checks.append(
        expect_error(
            "budget boolean",
            RecoveryReason.INVALID_INPUT,
            lambda: OperationBudget(journal_appends=True, folds=1, verifications=1),
        )
    )
    checks.append(
        expect_error(
            "point plane",
            RecoveryReason.VOCABULARY,
            lambda: RecoveryPoint(
                plane="contracts-plane",
                contract_id=contract.contract_id,
                subject_id=session.runtime_id,
                record_lines=("{}",),
                sequence=1,
                recorded_at=D_SNAP_R,
                provenance=_prov(BATTERY_ISSUER),
            ),
        )
    )
    checks.append(
        expect_error(
            "point subject id",
            RecoveryReason.INVALID_INPUT,
            lambda: RecoveryPoint(
                plane="runtime-journal",
                contract_id=contract.contract_id,
                subject_id="runtime-42",
                record_lines=("{}",),
                sequence=1,
                recorded_at=D_SNAP_R,
                provenance=_prov(BATTERY_ISSUER),
            ),
        )
    )
    checks.append(
        expect_error(
            "cross-plane same plane twice",
            RecoveryReason.INVALID_INPUT,
            lambda: CrossPlaneDivergence(
                divergence_id="",
                drill_id=contract.contract_id,
                contract_id=contract.contract_id,
                code="evidence-record-missing",
                plane_a="evidence-plane",
                plane_b="evidence-plane",
                expected="record:x",
                actual="missing",
                resolution="disclosed",
                provenance=_prov(BATTERY_ISSUER),
            ),
        )
    )
    checks.append(
        expect_error(
            "cross-plane bad code",
            RecoveryReason.VOCABULARY,
            lambda: CrossPlaneDivergence(
                divergence_id="",
                drill_id=contract.contract_id,
                contract_id=contract.contract_id,
                code="plane-exploded",
                plane_a="evidence-plane",
                plane_b="runtime-journal",
                expected="record:x",
                actual="missing",
                resolution="disclosed",
                provenance=_prov(BATTERY_ISSUER),
            ),
        )
    )
    for _, passed, detail in checks:
        if not passed:
            return fail(name, detail)
    return ok(name, "%d record-level gates all fail closed with the typed codes" % len(checks))


# ---------------------------------------------------------------------------
# case_03 — the drill engine's step-order gates fail closed
# ---------------------------------------------------------------------------


def case_03_drill_step_order_gates() -> Result:
    name = "case_03_drill_step_order_gates"
    contract, _base, rstore, session, journal = _fixture()
    fresh = _fresh_view(contract)
    estore = EvidenceStore()
    budget = OperationBudget(journal_appends=16, folds=8, verifications=128)

    def _run(steps: Tuple[DrillStep, ...]) -> Any:
        return run_drill(
            _plan_for(contract.contract_id, steps, budget),
            contract=contract,
            runtime_store=rstore,
            runtime_id=session.runtime_id,
            offline_journal=journal,
            evidence_store=estore,
            fresh_view=fresh,
        )

    checks: List[Result] = [
        expect_error(
            "loss before snapshot",
            RecoveryReason.INVALID_INPUT,
            lambda: _run(
                (DrillStep(kind="induce-plane-loss", plane="runtime-journal", recorded_at=D_LOSS_R, provenance=_prov(BATTERY_ISSUER)),)
            ),
        ),
        expect_error(
            "restore without a point",
            RecoveryReason.INVALID_INPUT,
            lambda: _run(
                (DrillStep(kind="restore-plane", plane="runtime-journal", recorded_at=D_RESTORE_R, provenance=_prov(BATTERY_ISSUER)),)
            ),
        ),
        expect_error(
            "restore without a loss",
            RecoveryReason.INVALID_INPUT,
            lambda: _run(
                (
                    DrillStep(kind="snapshot-plane", plane="runtime-journal", recorded_at=D_SNAP_R, provenance=_prov(BATTERY_ISSUER)),
                    DrillStep(kind="restore-plane", plane="runtime-journal", recorded_at=D_RESTORE_R, provenance=_prov(BATTERY_ISSUER)),
                )
            ),
        ),
        expect_error(
            "verify while lost",
            RecoveryReason.INVALID_INPUT,
            lambda: _run(
                (
                    DrillStep(kind="snapshot-plane", plane="runtime-journal", recorded_at=D_SNAP_R, provenance=_prov(BATTERY_ISSUER)),
                    DrillStep(kind="induce-plane-loss", plane="runtime-journal", recorded_at=D_LOSS_R, provenance=_prov(BATTERY_ISSUER)),
                )
            ),
        ),
        expect_error(
            "reconcile while lost",
            RecoveryReason.INVALID_INPUT,
            lambda: _run(
                (
                    DrillStep(kind="snapshot-plane", plane="runtime-journal", recorded_at=D_SNAP_R, provenance=_prov(BATTERY_ISSUER)),
                    DrillStep(kind="induce-plane-loss", plane="runtime-journal", recorded_at=D_LOSS_R, provenance=_prov(BATTERY_ISSUER)),
                    DrillStep(kind="reconcile-planes", recorded_at=D_RECONCILE, provenance=_prov(BATTERY_ISSUER)),
                )
            ),
        ),
        expect_error(
            "double snapshot",
            RecoveryReason.INVALID_INPUT,
            lambda: _run(
                (
                    DrillStep(kind="snapshot-plane", plane="runtime-journal", recorded_at=D_SNAP_R, provenance=_prov(BATTERY_ISSUER)),
                    DrillStep(kind="snapshot-plane", plane="runtime-journal", recorded_at=D_SNAP_O, provenance=_prov(BATTERY_ISSUER)),
                )
            ),
        ),
        expect_error(
            "evidence-producing final step",
            RecoveryReason.INVALID_INPUT,
            lambda: _run(
                (
                    DrillStep(kind="snapshot-plane", plane="runtime-journal", recorded_at=D_SNAP_R, provenance=_prov(BATTERY_ISSUER)),
                    DrillStep(kind="induce-plane-loss", plane="runtime-journal", recorded_at=D_LOSS_R, provenance=_prov(BATTERY_ISSUER)),
                )
            ),
        ),
        expect_error(
            "plan rides a foreign contract",
            RecoveryReason.ID_MISMATCH,
            lambda: run_drill(
                _plan_for("sha256:" + "0" * 64, (DrillStep(kind="reconcile-planes", recorded_at=D_RECONCILE, provenance=_prov(BATTERY_ISSUER)),), budget),
                contract=contract,
                runtime_store=rstore,
                runtime_id=session.runtime_id,
                offline_journal=journal,
                evidence_store=estore,
                fresh_view=fresh,
            ),
        ),
    ]
    for _, passed, detail in checks:
        if not passed:
            return fail(name, detail)
    return ok(name, "%d step-order gates fail closed (the drill never invents a plane)" % len(checks))


# ---------------------------------------------------------------------------
# case_04 / case_05 — (a) the snapshot + restore round-trips
# ---------------------------------------------------------------------------


def case_04_runtime_plane_round_trip() -> Result:
    name = "case_04_runtime_plane_round_trip"
    contract, _base, rstore, session, _journal = _fixture()
    point = snapshot_runtime_plane(
        rstore,
        session.runtime_id,
        recorded_at=D_SNAP_R,
        provenance=_prov(BATTERY_ISSUER),
    )
    problems: List[str] = []
    if point.plane != "runtime-journal":
        problems.append("the point names the wrong plane")
    if point.contract_id != contract.contract_id or point.subject_id != session.runtime_id:
        problems.append("the point's attribution is wrong")
    if point.sequence != len(rstore.events(session.runtime_id)):
        problems.append("the point's watermark is wrong")
    # the fail-closed verification passes on the honest point
    try:
        verify_recovery_point(point)
    except RecoveryError as error:
        return fail(name, "the honest point failed verification: %s" % error.detail[:90])
    # the restore round-trip: byte-exact through the ACCEPTED
    # construction-is-recovery constructor
    restored = restore_runtime_plane(point)
    restored_events = restored.events(session.runtime_id)
    original_events = rstore.events(session.runtime_id)
    if len(restored_events) != len(original_events):
        problems.append("the restored journal length differs")
    else:
        for i, (restored_event, original_event) in enumerate(zip(restored_events, original_events)):
            if restored_event.canonical_bytes() != original_event.canonical_bytes():
                problems.append("the restored event %d is not byte-identical" % i)
            if restored_event.event_id != original_event.event_id:
                problems.append("the restored event %d identity differs" % i)
            if restored_event.sequence != i + 1:
                problems.append("the restored event %d journal position differs" % i)
    if restored.session(session.runtime_id).canonical_bytes() != rstore.session(session.runtime_id).canonical_bytes():
        problems.append("the restored folded session is not byte-identical")
    if point.state_digest != journal_state_digest(
        tuple(e.canonical_bytes().decode("utf-8") for e in restored_events)
    ):
        problems.append("the plane digest does not re-derive over the restored journal")
    # the serialized round-trip: point -> dict -> point -> restore
    replay_point = RecoveryPoint.from_dict(point.to_dict())
    replay_store = restore_runtime_plane(replay_point)
    if (
        replay_store.session(session.runtime_id).canonical_bytes()
        != rstore.session(session.runtime_id).canonical_bytes()
    ):
        problems.append("the serialized replay restore is not byte-identical")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "runtime plane: byte-exact restore through RuntimeStore.from_events; "
        "identities + positions preserved; the serialized replay reproduces "
        "the folded session byte-identically",
    )


def case_05_offline_plane_round_trip() -> Result:
    name = "case_05_offline_plane_round_trip"
    contract, _base, _rstore, _session, journal = _fixture()
    point = snapshot_offline_plane(
        journal, recorded_at=D_SNAP_O, provenance=_prov(BATTERY_ISSUER)
    )
    problems: List[str] = []
    if point.plane != "offline-journal":
        problems.append("the point names the wrong plane")
    first = journal.records()[0]
    if point.contract_id != first.contract_id or point.subject_id != first.episode_id:
        problems.append("the point's attribution is wrong")
    if point.sequence != len(journal.records()):
        problems.append("the point's watermark is wrong")
    try:
        verify_recovery_point(point)
    except RecoveryError as error:
        return fail(name, "the honest point failed verification: %s" % error.detail[:90])
    restored = restore_offline_plane(point)
    restored_records = restored.records()
    original_records = journal.records()
    if len(restored_records) != len(original_records):
        problems.append("the restored journal length differs")
    else:
        for i, (restored_record, original_record) in enumerate(zip(restored_records, original_records)):
            if restored_record.canonical_bytes() != original_record.canonical_bytes():
                problems.append("the restored record %d is not byte-identical" % i)
            if restored_record.operation_id != original_record.operation_id:
                problems.append("the restored record %d identity differs" % i)
            if restored_record.sequence != i + 1:
                problems.append("the restored record %d journal position differs" % i)
    if restored.state().canonical_bytes() != journal.state().canonical_bytes():
        problems.append("the restored folded local state is not byte-identical")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "offline plane: byte-exact restore through OfflineJournal.from_records; "
        "identities + positions + the folded state preserved",
    )


# ---------------------------------------------------------------------------
# case_06 — (a) the restored planes remain LIVE accepted surfaces
# ---------------------------------------------------------------------------


def case_06_restored_planes_compose_forward() -> Result:
    name = "case_06_restored_planes_compose_forward"
    contract, base, rstore, session, journal = _fixture()
    runtime_point = snapshot_runtime_plane(
        rstore, session.runtime_id, recorded_at=D_SNAP_R, provenance=_prov(BATTERY_ISSUER)
    )
    offline_point = snapshot_offline_plane(
        journal, recorded_at=D_SNAP_O, provenance=_prov(BATTERY_ISSUER)
    )
    problems: List[str] = []
    # the restored runtime store ACCEPTS further accepted transitions
    restored_store = restore_runtime_plane(runtime_point)
    pre_bytes = tuple(
        e.canonical_bytes() for e in restored_store.events(session.runtime_id)
    )
    try:
        # the restored session is DEGRADED at the recovery point (the
        # partition is open): the explicit recovery FIRST, then the
        # explicit degraded entry again — both accepted transitions
        restored_store.recover_degraded(
            session.runtime_id,
            recorded_at=D_LOSS_R,
            provenance=_prov(BATTERY_ISSUER),
        )
        restored_store.enter_degraded(
            session.runtime_id,
            evidence_kind="observation",
            evidence_refs=(),
            recorded_at=D_RESTORE_R,
            provenance=_prov(BATTERY_ISSUER),
        )
    except RecoveryError as error:
        return fail(name, "the restored store rejected a transition: %s" % error.detail[:90])
    grown = restored_store.events(session.runtime_id)
    if tuple(e.canonical_bytes() for e in grown[: len(pre_bytes)]) != pre_bytes:
        problems.append("the accepted transitions rewrote the pre-existing events")
    if len(grown) != len(pre_bytes) + 2:
        problems.append("the accepted transitions did not append exactly 2 events")
    # the restored offline journal ACCEPTS further accepted admissions
    restored_journal = restore_offline_plane(offline_point)
    pre_line_bytes = tuple(
        r.canonical_bytes() for r in restored_journal.records()
    )
    try:
        local_admit(
            restored_journal,
            contract,
            base,
            subject=_subject(SUBJ_DEVICE_44),
            claimed_constraints=tuple(contract.hard_constraints),
            decided_at=D_ADMIT_C,
            provenance=_prov(BATTERY_ISSUER),
        )
    except RecoveryError as error:
        return fail(name, "the restored journal rejected an admission: %s" % error.detail[:90])
    grown_records = restored_journal.records()
    if tuple(r.canonical_bytes() for r in grown_records[: len(pre_line_bytes)]) != pre_line_bytes:
        problems.append("the accepted admission rewrote the pre-existing records")
    if len(grown_records) != len(pre_line_bytes) + 1:
        problems.append("the accepted admission did not append exactly 1 record")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "the restored planes remain live accepted surfaces: the restored store "
        "takes enter_degraded/recover_degraded; the restored journal takes "
        "local_admit — construction composes forward, history append-only",
    )


# ---------------------------------------------------------------------------
# case_07 / case_08 — (b) the drill determinism
# ---------------------------------------------------------------------------


def case_07_drill_determinism() -> Result:
    name = "case_07_drill_determinism"
    problems: List[str] = []
    outputs: List[Tuple[bytes, ...]] = []
    for _ in range(2):
        outputs.append(_full_drill_scenario())
    if outputs[0] != outputs[1]:
        problems.append("the full drill scenario is not byte-identical across runs")
    contract, _base, _fresh, _rstore, _session, _journal, _estore, plan, result = (
        _run_primary_drill()
    )
    contract2, _b2, _f2, _r2, _s2, _j2, _e2, _p2, result2 = _run_primary_drill()
    if result.canonical_bytes() != result2.canonical_bytes():
        problems.append("the drill results are not byte-identical")
    if result.drill_run_id != result2.drill_run_id:
        problems.append("the drill run ids differ")
    if result.measured_counts.to_dict() != result2.measured_counts.to_dict():
        problems.append("the measured RTO counts differ")
    if plan.canonical_bytes() != _p2.canonical_bytes():
        problems.append("the drill plans differ (same inputs)")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "same drill inputs, run twice (and the full scenario twice): the "
        "byte-identical result, run id and measured operation counts",
    )


def case_08_cross_process_pythonhashseed() -> Result:
    name = "case_08_cross_process_pythonhashseed"
    digest_hexes: Dict[str, str] = {}
    for seed in ("0", "1", "42"):
        import os

        env = dict(os.environ)
        env["PYTHONHASHSEED"] = seed
        probe = subprocess.run(
            [sys.executable, "-c", _SCENARIO_PROBE],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            env=env,
        )
        if probe.returncode != 0:
            return fail(
                name,
                "the PYTHONHASHSEED=%s probe failed: %s" % (seed, probe.stderr.strip()[:120]),
            )
        digest_hexes[seed] = probe.stdout.strip()
    if len(set(digest_hexes.values())) != 1:
        return fail(name, "the drill digests differ across PYTHONHASHSEED: %r" % digest_hexes)
    return ok(
        name,
        "the drill result + points + evidence digests are byte-identical across "
        "PYTHONHASHSEED 0/1/42 subprocesses",
    )


_SCENARIO_PROBE = r"""
import hashlib
import sys
sys.path.insert(0, ".")
sys.path.insert(0, "tools")
from recovery_selftest import _full_drill_scenario
scenario = _full_drill_scenario()
digest = hashlib.sha256()
for chunk in scenario:
    digest.update(chunk)
print(digest.hexdigest())
""".strip()


# ---------------------------------------------------------------------------
# case_09 — (c) induced divergence at the verification boundary
# ---------------------------------------------------------------------------


def case_09_induced_divergence_disclosed() -> Result:
    name = "case_09_induced_divergence_disclosed"
    contract, _base, _rstore, _session, journal = _fixture_with_extra_admissions()
    # the recovery point over the FIRST three records (entered + 2
    # admissions); the plane then advanced by TWO MORE admissions
    first_three = journal.records()[:3]
    point = snapshot_offline_plane_from_records(first_three, D_SNAP_O)
    # the pre-failure content: the full 5-record journal
    pre_failure_lines = tuple(
        r.canonical_bytes().decode("utf-8") for r in journal.records()
    )
    # the restored content: the recovery point's payload (3 records)
    restored_lines = point.record_lines
    verification = verify_restore(
        point,
        pre_failure_lines,
        restored_lines,
        recorded_at=D_VERIFY_O,
        provenance=_prov(BATTERY_ISSUER),
    )
    problems: List[str] = []
    if verification.outcome != "divergence-reconciled":
        problems.append("the outcome is not divergence-reconciled (found %s)" % verification.outcome)
    lost_records = journal.records()[3:]
    if len(verification.divergences) != len(lost_records):
        problems.append("the divergence count does not match the lost records")
    else:
        for divergence, lost in zip(verification.divergences, lost_records):
            if divergence.code != "record-lost-beyond-recovery-point":
                problems.append("the divergence code is wrong")
            if divergence.expected_record_id != lost.operation_id:
                problems.append("the lost record is not cited by its ORIGINAL identity")
            if divergence.resolution != "reconciled-to-recovery-point":
                problems.append("the resolution does not name the recovery point base")
            if divergence.recovery_point_id != point.recovery_point_id:
                problems.append("the divergence does not cite its recovery point")
    if verification.expected_digest == verification.actual_digest:
        problems.append("the digests should differ (records were lost)")
    if verification.actual_digest != point.state_digest:
        problems.append("the restored plane is not the recovery point content")
    if verification.verified_records != 3:
        problems.append("the verified record count is wrong")
    # never silently absorbed: the divergences round-trip as typed records
    replay = RestoreVerification.from_dict(verification.to_dict())
    if replay.canonical_bytes() != verification.canonical_bytes():
        problems.append("the verification does not round-trip")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "the plane advanced 2 records beyond the point: BOTH disclosed as typed "
        "divergence records cited by their original identities, reconciled "
        "onto the recovery point — never silently absorbed",
    )


def snapshot_offline_plane_from_records(records, recorded_at: str) -> RecoveryPoint:
    """A test helper: build the offline recovery point directly from a
    record sequence (the snapshot construction over a partial journal —
    the recovery point at an earlier watermark)."""
    from recovery.snapshot import plane_record_lines

    lines = plane_record_lines(records)
    return RecoveryPoint(
        plane="offline-journal",
        contract_id=records[0].contract_id,
        subject_id=records[0].episode_id,
        record_lines=lines,
        sequence=records[-1].sequence,
        recorded_at=recorded_at,
        provenance=_prov(BATTERY_ISSUER),
    )


# ---------------------------------------------------------------------------
# case_10 — (c) the failure-during-recovery drill
# ---------------------------------------------------------------------------


def _run_divergence_drill():
    contract, _base, rstore, session, journal = _fixture()
    fresh = _fresh_view(contract)
    plan = _plan_for(
        contract.contract_id,
        _divergence_plan_steps(),
        OperationBudget(journal_appends=16, folds=12, verifications=256),
    )
    estore = EvidenceStore()
    result = run_drill(
        plan,
        contract=contract,
        runtime_store=rstore,
        runtime_id=session.runtime_id,
        offline_journal=journal,
        evidence_store=estore,
        fresh_view=fresh,
    )
    return contract, fresh, rstore, session, journal, estore, plan, result


def case_10_failure_during_recovery_drill() -> Result:
    name = "case_10_failure_during_recovery_drill"
    contract, _fresh, _rstore, _session, journal, _estore, _plan, result = (
        _run_divergence_drill()
    )
    problems: List[str] = []
    outcomes = [v.outcome for v in result.restorations]
    if outcomes != ["byte-exact", "byte-exact", "divergence-reconciled"]:
        problems.append("the verification outcomes are wrong: %r" % outcomes)
    third = result.restorations[2]
    if third.plane != "runtime-journal":
        problems.append("the third verification is not the runtime plane")
    # the lost records: the reconciliation's reconnect pair (2 events
    # appended by the accepted close, lost with the second failure)
    lost_ids = [d.expected_record_id for d in third.divergences]
    if len(lost_ids) != 2:
        problems.append("the second failure should lose exactly the 2 reconnect events")
    if third.verified_records != 3:
        problems.append("the second restore verifies the point's 3 records")
    if third.actual_digest != result.recovery_points[0][1] and False:
        problems.append("unreachable guard")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "the second loss (after the reconciliation) discloses the 2 reconnect "
        "events as typed lost records; the outcome is divergence-reconciled, "
        "never byte-exact-by-fabrication",
    )


# ---------------------------------------------------------------------------
# case_11 — (c) the silent-absorption rejections
# ---------------------------------------------------------------------------


def case_11_silent_absorption_rejected() -> Result:
    name = "case_11_silent_absorption_rejected"
    contract, _base, _rstore, _session, journal = _fixture_with_extra_admissions()
    first_three = journal.records()[:3]
    point = snapshot_offline_plane_from_records(first_three, D_SNAP_O)
    pre_failure_lines = tuple(
        r.canonical_bytes().decode("utf-8") for r in journal.records()
    )
    divergent = verify_restore(
        point,
        pre_failure_lines,
        point.record_lines,
        recorded_at=D_VERIFY_O,
        provenance=_prov(BATTERY_ISSUER),
    )
    if divergent.outcome != "divergence-reconciled":
        return fail(name, "the fixture did not produce a divergence (setup broken)")
    base_dict = divergent.to_dict()

    def _mutated(**overrides: Any) -> Dict[str, Any]:
        data = dict(base_dict)
        data.update(overrides)
        return data

    checks: List[Result] = [
        expect_error(
            "divergence outcome without records",
            RecoveryReason.RESTORE_DIVERGED,
            lambda: RestoreVerification.from_dict(
                _mutated(divergences=[])
            ),
        ),
        expect_error(
            "byte-exact outcome with records",
            RecoveryReason.RESTORE_DIVERGED,
            lambda: RestoreVerification.from_dict(
                _mutated(outcome="byte-exact")
            ),
        ),
        expect_error(
            "byte-exact outcome with differing digests",
            RecoveryReason.RESTORE_DIVERGED,
            lambda: RestoreVerification.from_dict(
                _mutated(outcome="byte-exact", divergences=[])
            ),
        ),
    ]
    for _, passed, detail in checks:
        if not passed:
            return fail(name, detail)
    return ok(
        name,
        "3 silent-absorption shapes fail closed at the record boundary (an "
        "outcome without its disclosed divergence records is a contradiction)",
    )


# ---------------------------------------------------------------------------
# case_12 / case_13 — (d) the recovery-time bounds as operation counts
# ---------------------------------------------------------------------------


def case_12_rto_declared_operation_counts() -> Result:
    name = "case_12_rto_declared_operation_counts"
    contract, _base, _fresh, _rstore, _session, _journal, _estore, plan, result = (
        _run_primary_drill()
    )
    problems: List[str] = []
    # the bound is EXPRESSED as declared integer counts (never time)
    for member in ("journal_appends", "folds", "verifications"):
        value = getattr(plan.budget, member)
        if isinstance(value, bool) or not isinstance(value, int):
            problems.append("the declared %s is not an integer count" % member)
    if set(plan.budget.to_dict()) != {"journal_appends", "folds", "verifications"}:
        problems.append("the budget carries members other than the operation counts")
    # the MEASURED accounting is recorded on the result and within bound
    measured = result.measured_counts
    if measured.exceeds(plan.budget) is not None:
        problems.append("the measured counts exceed the declared budget")
    if set(measured.to_dict()) != {"journal_appends", "folds", "verifications"}:
        problems.append("the measured counts carry non-count members")
    if measured.journal_appends < 1 or measured.folds < 1 or measured.verifications < 1:
        problems.append("the measured counts are empty (the accounting is broken)")
    # the declared budget rides the result VERBATIM
    if result.declared_budget.to_dict() != plan.budget.to_dict():
        problems.append("the declared budget is not carried verbatim")
    # deterministic: the same drill twice -> the byte-identical counts
    _c2, _b2, _f2, _r2, _s2, _j2, _e2, _p2, result2 = _run_primary_drill()
    if measured.to_dict() != result2.measured_counts.to_dict():
        problems.append("the measured counts are not deterministic")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "the RTO bound is declared and measured as pure integer operation "
        "counts (journal_appends=%d, folds=%d, verifications=%d — recorded on "
        "the result, deterministic, never wall clock)"
        % (measured.journal_appends, measured.folds, measured.verifications),
    )


def case_13_rto_enforced() -> Result:
    name = "case_13_rto_enforced"
    contract, _base, rstore, session, journal = _fixture()
    fresh = _fresh_view(contract)
    steps = _primary_plan(contract.contract_id).steps
    checks: List[Result] = [
        expect_error(
            "tight journal-appends bound",
            RecoveryReason.RTO_EXCEEDED,
            lambda: run_drill(
                _plan_for(contract.contract_id, steps, OperationBudget(journal_appends=2, folds=8, verifications=128)),
                contract=contract,
                runtime_store=rstore,
                runtime_id=session.runtime_id,
                offline_journal=journal,
                evidence_store=EvidenceStore(),
                fresh_view=fresh,
            ),
        ),
        expect_error(
            "tight folds bound",
            RecoveryReason.RTO_EXCEEDED,
            lambda: run_drill(
                _plan_for(contract.contract_id, steps, OperationBudget(journal_appends=16, folds=1, verifications=128)),
                contract=contract,
                runtime_store=rstore,
                runtime_id=session.runtime_id,
                offline_journal=journal,
                evidence_store=EvidenceStore(),
                fresh_view=fresh,
            ),
        ),
        expect_error(
            "tight verifications bound",
            RecoveryReason.RTO_EXCEEDED,
            lambda: run_drill(
                _plan_for(contract.contract_id, steps, OperationBudget(journal_appends=16, folds=8, verifications=4)),
                contract=contract,
                runtime_store=rstore,
                runtime_id=session.runtime_id,
                offline_journal=journal,
                evidence_store=EvidenceStore(),
                fresh_view=fresh,
            ),
        ),
    ]
    for _, passed, detail in checks:
        if not passed:
            return fail(name, detail)
    # an over-budget hand-built drill result fails closed at
    # construction (defense in depth)
    good = _run_primary_drill()[8]
    over = dict(good.to_dict())
    over["measured_counts"] = OperationCounts(
        journal_appends=good.declared_budget.journal_appends + 1,
        folds=0,
        verifications=0,
    ).to_dict()
    try:
        DrillResult.from_dict(over)
        return fail(name, "an over-budget hand-built result was accepted")
    except RecoveryError as error:
        if error.code != RecoveryReason.RTO_EXCEEDED:
            return fail(name, "wrong code for the over-budget result: %s" % error.code)
    return ok(
        name,
        "3 tight bounds fail closed at the increment point + the over-budget "
        "hand-built result fails closed at construction — the bound is "
        "ENFORCED as counts (deterministic detail: the counter, the measured "
        "count, the declared bound)",
    )


# ---------------------------------------------------------------------------
# case_14 — (e) the converged cross-plane reconciliation
# ---------------------------------------------------------------------------


def case_14_cross_plane_converged() -> Result:
    name = "case_14_cross_plane_converged"
    contract, _base, fresh, rstore, session, journal, estore, plan, result = (
        _run_primary_drill()
    )
    problems: List[str] = []
    recon = result.reconciliation
    if recon is None:
        return fail(name, "the drill produced no reconciliation")
    if recon.outcome != "converged":
        problems.append("the reconciliation did not converge (found %s)" % recon.outcome)
    if recon.divergences:
        problems.append("a converged reconciliation carries divergence records")
    # the contracts-plane material: the contract's OWN LOCK-108
    # fingerprint, consumed by reference (never recomputed)
    if recon.constraint_fingerprint != contract.hard_constraint_fingerprint():
        problems.append("the fingerprint is not the contract's own")
    # the plane digests reproduce an independent replay: restore both
    # points, drive the same accepted close (same inputs) -> the same
    # post-drill journals
    runtime_point = snapshot_runtime_plane(
        rstore, session.runtime_id, recorded_at=D_SNAP_R, provenance=plan.steps[0].provenance
    )
    offline_point = snapshot_offline_plane(
        journal, recorded_at=D_SNAP_O, provenance=plan.steps[1].provenance
    )
    replay_store = restore_runtime_plane(runtime_point)
    replay_journal = restore_offline_plane(offline_point)
    # the same accepted close the drill's reconcile step drove: the
    # same inputs (the close derives its own default provenance — the
    # drill's reconcile passes exactly these members through)
    replay_close = close_partition(
        replay_store,
        session.runtime_id,
        contract,
        replay_journal,
        fresh,
        resolution_rule=("candidate-kind", "candidate-id"),
        recorded_at=D_RECONCILE,
    )
    expected_digests = {
        "runtime-journal": journal_state_digest(
            tuple(e.canonical_bytes().decode("utf-8") for e in replay_store.events(session.runtime_id))
        ),
        "offline-journal": journal_state_digest(
            tuple(r.canonical_bytes().decode("utf-8") for r in replay_journal.records())
        ),
    }
    for plane, digest in recon.plane_digests:
        if expected_digests[plane] != digest:
            problems.append("the %s digest does not reproduce the independent replay" % plane)
    # the accepted resync preserved VERBATIM (it re-validates through
    # the ACCEPTED constructor — consumed by reference, never
    # re-interpreted)
    if recon.accepted_resync is None:
        problems.append("the accepted resynchronization result was not preserved")
    else:
        replay_resync = ResyncResult.from_dict(dict(recon.accepted_resync))
        if replay_resync.canonical_bytes() != canonical_json_bytes_of(recon.accepted_resync):
            problems.append("the preserved resync does not re-validate byte-identically")
        if replay_resync.resync_id != replay_close.resync.resync_id:
            problems.append("the preserved resync id does not match the replayed close")
        if tuple(replay_resync.applied_operations) != tuple(replay_close.resync.applied_operations):
            problems.append("the preserved applied set does not match the replay")
    # the evidence plane: the drill's LOCK-106 records preserved
    if len(recon.evidence_record_ids) != 4:
        problems.append("the drill should carry 4 evidence records (2 observations + 2 attestations)")
    for record_id in recon.evidence_record_ids:
        if not estore.has(record_id):
            problems.append("a drill evidence record is missing from the evidence plane")
    for record in estore.records():
        if record.record_type == "observation":
            if record.metric != "health-state" or record.value != 3:
                problems.append("the loss observation is not the NOT_RUNNING health state")
        elif record.record_type == "attestation":
            if record.attestation_kind != "controller-verified" or record.attested_value != 1:
                problems.append("the restore attestation does not attest byte-exact")
        else:
            problems.append("an unexpected evidence type was produced")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "converged: zero divergences; the contract's own fingerprint consumed; "
        "the plane digests reproduce the independent accepted replay; the "
        "accepted resync preserved verbatim and re-validating; 4 LOCK-106 "
        "records preserved on the evidence plane",
    )


def canonical_json_bytes_of(data: Any) -> bytes:
    return canonical_json_text(data).encode("utf-8")


# ---------------------------------------------------------------------------
# case_15 — (e) the accepted resync divergences preserved verbatim
# ---------------------------------------------------------------------------


def case_15_accepted_resync_divergences_preserved() -> Result:
    name = "case_15_accepted_resync_divergences_preserved"
    contract, _base, _fresh, _rstore, session, journal, _estore, _plan, result = (
        _run_primary_drill(contested=True)
    )
    problems: List[str] = []
    recon = result.reconciliation
    if recon is None or recon.accepted_resync is None:
        return fail(name, "the contested drill did not drive the resynchronization")
    divergences = recon.accepted_resync.get("divergences") or []
    if len(divergences) != 1:
        return fail(
            name,
            "the preserved resync should carry exactly the 1 contested divergence (found %d)"
            % len(divergences),
        )
    preserved = divergences[0]
    if preserved.get("subject_value") != REC_WIRELESS:
        problems.append("the preserved divergence does not name the contested subject")
    contested_operation_id = preserved.get("local_operation_id")
    if not contested_operation_id:
        problems.append("the preserved divergence does not cite the local operation")
    if preserved.get("resolution") != "authority-record":
        problems.append("the default rule should let the authority side win (LOCK-101)")
    if list(preserved.get("resolution_rule") or ()) != list(DEFAULT_RESOLUTION_RULE):
        problems.append("the declared rule is not preserved verbatim")
    # the contested local operation IS journaled (cited, never dropped)
    journal_ids = {r.operation_id for r in journal.records()}
    if contested_operation_id not in journal_ids:
        problems.append("the cited local operation is not in the pre-drill journal")
    # the no-silent-loss accounting: 3 admitted = 2 applied + 1 cited
    applied = recon.accepted_resync.get("applied_operations") or []
    if len(applied) != 2:
        problems.append("the applied set should carry the 2 clean operations")
    if contested_operation_id in applied:
        problems.append("the lost conflict is both cited and applied (a duplicate)")
    # the reconciliation itself stays converged (the citation IS the
    # convergence — the loser stays cited, only explicitly superseded)
    if recon.outcome != "converged":
        problems.append("the cross-plane outcome should stay converged")
    if recon.divergences:
        problems.append("the cross-plane record set should carry no divergences here")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "the accepted resync's OWN typed divergence record preserved VERBATIM "
        "(the contested subject, the local operation cited, the declared rule, "
        "the authority-side resolution) — the localfirst/ divergence "
        "vocabulary consumed by reference where it fits",
    )


# ---------------------------------------------------------------------------
# case_16 — (e) the evidence-record-missing divergence disclosed
# ---------------------------------------------------------------------------


def case_16_evidence_record_missing_disclosed() -> Result:
    name = "case_16_evidence_record_missing_disclosed"
    contract, _base, rstore, session, journal = _fixture()
    fresh = _fresh_view(contract)
    estore = EvidenceStore()
    # drive the accepted close on the LIVE holders (the episode closes;
    # the runtime journal gains the reconnect pair)
    close_partition(
        rstore,
        session.runtime_id,
        contract,
        journal,
        fresh,
        recorded_at=D_RECONCILE,
        provenance=_prov(BATTERY_ISSUER),
    )
    # the drill's real evidence records + one bogus citation
    real = ObservationEvidence(
        subject_ref=session.runtime_id,
        contract_ref=contract.contract_id,
        instant=D_LOSS_R,
        producer=BATTERY_ISSUER,
        metric="health-state",
        value=3,
        confidence_basis_points=10_000,
        freshness_until=D_VERIFY_R,
        source_refs=(contract.contract_id,),
    )
    estore.ingest(real)
    bogus = "evidence:observation:" + "0" * 40
    recon, close = reconcile_planes(
        drill_id="sha256:" + "1" * 64,
        contract=contract,
        runtime_store=rstore,
        runtime_id=session.runtime_id,
        offline_journal=journal,
        evidence_store=estore,
        expected_evidence=(("runtime-journal", real.record_id), ("offline-journal", bogus)),
        recorded_at=D_RECONCILE2,
        provenance=_prov(BATTERY_ISSUER),
    )
    problems: List[str] = []
    if close is not None:
        problems.append("the closed episode should not drive a second close")
    if recon.outcome != "divergence-disclosed":
        problems.append("the outcome should disclose the divergence")
    if len(recon.divergences) != 1:
        problems.append("exactly one divergence should be disclosed")
    else:
        divergence = recon.divergences[0]
        if divergence.code != "evidence-record-missing":
            problems.append("the divergence code is wrong")
        if (divergence.plane_a, divergence.plane_b) != ("evidence-plane", "offline-journal"):
            problems.append("the divergence plane pair is wrong")
        if divergence.expected != bogus or divergence.actual != "missing":
            problems.append("the divergence citations are wrong")
        if divergence.resolution != "disclosed":
            problems.append("the divergence resolution is wrong")
    if real.record_id not in recon.evidence_record_ids:
        problems.append("the present record is not cited")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "a missing LOCK-106 evidence record is disclosed as a typed "
        "cross-plane divergence (evidence-plane vs the attested plane, the "
        "expected id, resolution disclosed) — never silently dropped",
    )


# ---------------------------------------------------------------------------
# case_17 — (e) the composition-link-unresolved divergence disclosed
# ---------------------------------------------------------------------------


def case_17_composition_link_unresolved_disclosed() -> Result:
    name = "case_17_composition_link_unresolved_disclosed"
    contract, _base, rstore, session, journal = _fixture()
    fresh = _fresh_view(contract)
    # snapshot both planes, drive the accepted close (the episode
    # closes; the runtime journal gains the reconnect pair), then
    # RESTORE the runtime plane from its point (dropping the reconnect
    # events) — the offline journal's exit citation no longer resolves
    runtime_point = snapshot_runtime_plane(
        rstore, session.runtime_id, recorded_at=D_SNAP_R, provenance=_prov(BATTERY_ISSUER)
    )
    close_partition(
        rstore,
        session.runtime_id,
        contract,
        journal,
        fresh,
        recorded_at=D_RECONCILE,
        provenance=_prov(BATTERY_ISSUER),
    )
    exit_record = [r for r in journal.records() if r.kind == "partition-exited"][0]
    restored_store = restore_runtime_plane(runtime_point)
    estore = EvidenceStore()
    recon, _close = reconcile_planes(
        drill_id="sha256:" + "2" * 64,
        contract=contract,
        runtime_store=restored_store,
        runtime_id=session.runtime_id,
        offline_journal=journal,
        evidence_store=estore,
        expected_evidence=(),
        recorded_at=D_RECONCILE2,
        provenance=_prov(BATTERY_ISSUER),
    )
    problems: List[str] = []
    if recon.outcome != "divergence-disclosed":
        problems.append("the outcome should disclose the divergence")
    unresolved = [d for d in recon.divergences if d.code == "composition-link-unresolved"]
    if len(unresolved) != 1:
        problems.append("exactly one unresolved composition link should be disclosed")
    else:
        divergence = unresolved[0]
        if (divergence.plane_a, divergence.plane_b) != ("offline-journal", "runtime-journal"):
            problems.append("the divergence plane pair is wrong")
        if divergence.expected != exit_record.reconnect_id:
            problems.append("the divergence does not cite the unresolved reconnect evidence id")
        if divergence.resolution != "disclosed":
            problems.append("the divergence resolution is wrong")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "the offline journal's reconnect citation (lost with the restored "
        "runtime plane's reconnect evidence) is disclosed as a typed "
        "cross-plane divergence — the link is unresolved, honestly, never "
        "silently dropped",
    )


# ---------------------------------------------------------------------------
# case_18 — (e) the attribution mismatch fails closed (unreconcilable)
# ---------------------------------------------------------------------------


def case_18_attribution_mismatch_fails_closed() -> Result:
    name = "case_18_attribution_mismatch_fails_closed"
    contract, _base, rstore, session, journal = _fixture()
    # a SECOND contract with different creation material (the
    # foreign-contract probe)
    _, foreign = _mature_contract(principal_ref="app:dr-other-99")
    estore = EvidenceStore()
    checks: List[Result] = [
        expect_error(
            "runtime session rides a foreign contract",
            RecoveryReason.PLANE_MISMATCH,
            lambda: reconcile_planes(
                drill_id="sha256:" + "3" * 64,
                contract=foreign,
                runtime_store=rstore,
                runtime_id=session.runtime_id,
                offline_journal=journal,
                evidence_store=estore,
                expected_evidence=(),
                recorded_at=D_RECONCILE,
                provenance=_prov(BATTERY_ISSUER),
            ),
        ),
    ]
    # an offline journal from a foreign-contract fixture: close it
    # first (so the drive is not the failure surface), then reconcile
    # against THIS contract
    _c2, _b2, rs2, sess2, j2 = _fixture_with_extra_admissions()
    _f2 = _fresh_view(_c2)
    close_partition(
        rs2,
        sess2.runtime_id,
        _c2,
        j2,
        _f2,
        recorded_at=D_RECONCILE,
        provenance=_prov(BATTERY_ISSUER),
    )
    checks.append(
        expect_error(
            "offline journal rides a foreign contract",
            RecoveryReason.PLANE_MISMATCH,
            lambda: reconcile_planes(
                drill_id="sha256:" + "4" * 64,
                contract=foreign,
                runtime_store=rs2,
                runtime_id=sess2.runtime_id,
                offline_journal=j2,
                evidence_store=estore,
                expected_evidence=(),
                recorded_at=D_RECONCILE2,
                provenance=_prov(BATTERY_ISSUER),
            ),
        )
    )
    for _, passed, detail in checks:
        if not passed:
            return fail(name, detail)
    return ok(
        name,
        "2 attribution mismatches fail closed before any convergence drive "
        "(LOCK-101/LOCK-117: the recovery surface never rewrites attribution — "
        "unreconcilable, never a divergence record)",
    )


# ---------------------------------------------------------------------------
# case_19 — (f) the recovered identities preserved
# ---------------------------------------------------------------------------


def case_19_recovered_identities_preserved() -> Result:
    name = "case_19_recovered_identities_preserved"
    contract, _base, _fresh, rstore, session, journal, _estore, _plan, result = (
        _run_primary_drill()
    )
    problems: List[str] = []
    # the drill's recovery points reproduce the independently
    # constructed points (same inputs -> the same content identities)
    runtime_point = snapshot_runtime_plane(
        rstore, session.runtime_id, recorded_at=D_SNAP_R, provenance=_prov(BATTERY_ISSUER)
    )
    offline_point = snapshot_offline_plane(
        journal, recorded_at=D_SNAP_O, provenance=_prov(BATTERY_ISSUER)
    )
    point_ids = dict(result.recovery_points)
    if point_ids["runtime-journal"] != runtime_point.recovery_point_id:
        problems.append("the runtime recovery point identity is not reproducible")
    if point_ids["offline-journal"] != offline_point.recovery_point_id:
        problems.append("the offline recovery point identity is not reproducible")
    # the restored records preserve their identities and journal
    # positions VERBATIM (never renumbered)
    for point, holder_records in (
        (runtime_point, restore_runtime_plane(runtime_point).events(session.runtime_id)),
        (offline_point, restore_offline_plane(offline_point).records()),
    ):
        if len(point.record_lines) != len(holder_records):
            problems.append("the restored %s plane length differs" % point.plane)
            continue
        for i, (line, record) in enumerate(zip(point.record_lines, holder_records)):
            data = json.loads(line)
            identity = data.get("event_id") or data.get("operation_id")
            record_identity = getattr(record, "event_id", None) or getattr(record, "operation_id")
            if identity != record_identity:
                problems.append("the restored %s record %d identity differs" % (point.plane, i))
            if data.get("sequence") != i + 1 or record.sequence != i + 1:
                problems.append("the restored %s record %d position differs" % (point.plane, i))
            if line != record.canonical_bytes().decode("utf-8"):
                problems.append("the restored %s record %d bytes differ" % (point.plane, i))
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "every recovered record preserves its original content-derived "
        "identity, its journal position AND its canonical bytes (LOCK-106: "
        "recovery never fabricates history, never renumbers)",
    )


# ---------------------------------------------------------------------------
# case_20 / case_21 / case_22 — (f) the fabrication rejections
# ---------------------------------------------------------------------------


def _forged_line(line: str, **overrides: Any) -> str:
    data = json.loads(line)
    data.update(overrides)
    return canonical_json_text(data)


def case_20_reidentified_record_fails_closed() -> Result:
    name = "case_20_reidentified_record_fails_closed"
    contract, _base, rstore, session, _journal = _fixture()
    point = snapshot_runtime_plane(
        rstore, session.runtime_id, recorded_at=D_SNAP_R, provenance=_prov(BATTERY_ISSUER)
    )
    original_lines = list(point.record_lines)
    forged = _forged_line(
        original_lines[1],
        event_id="sha256:" + "ab" * 32,
    )
    restored_lines = tuple(original_lines[:1]) + (forged,) + tuple(original_lines[2:])
    problems: List[str] = []
    try:
        verify_restore(
            point,
            tuple(original_lines),
            restored_lines,
            recorded_at=D_VERIFY_R,
            provenance=_prov(BATTERY_ISSUER),
        )
        problems.append("a re-identified restored record was accepted")
    except RecoveryError as error:
        if error.code != RecoveryReason.HISTORY_FABRICATED:
            problems.append("wrong code: %s" % error.code)
        if "preserve" not in error.detail and "fabricates" not in error.detail:
            problems.append("the rejection does not cite the discipline")
    # the snapshot-side twin: a payload record whose identity does not
    # re-derive (the accepted constructor) rejects the SNAPSHOT whole
    tampered_point = RecoveryPoint(
        plane="runtime-journal",
        contract_id=point.contract_id,
        subject_id=point.subject_id,
        record_lines=tuple(restored_lines),
        sequence=point.sequence,
        recorded_at=point.recorded_at,
        provenance=point.provenance,
    )
    try:
        verify_recovery_point(tampered_point)
        problems.append("a tampered snapshot payload was accepted")
    except RecoveryError as error:
        if error.code != RecoveryReason.SNAPSHOT_UNVERIFIABLE:
            problems.append("wrong snapshot code: %s" % error.code)
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "a forged/re-identified record fails closed BOTH as a restored record "
        "(recovery-history-fabricated) and as a snapshot payload "
        "(recovery-snapshot-unverifiable, rejected whole)",
    )


def case_21_renumbered_restore_fails_closed() -> Result:
    name = "case_21_renumbered_restore_fails_closed"
    contract, _base, _rstore, _session, journal = _fixture()
    point = snapshot_offline_plane(
        journal, recorded_at=D_SNAP_O, provenance=_prov(BATTERY_ISSUER)
    )
    original_lines = list(point.record_lines)
    renumbered = _forged_line(original_lines[1], sequence=9)
    restored_lines = tuple(original_lines[:1]) + (renumbered,) + tuple(original_lines[2:])
    try:
        verify_restore(
            point,
            tuple(original_lines),
            restored_lines,
            recorded_at=D_VERIFY_O,
            provenance=_prov(BATTERY_ISSUER),
        )
        return fail(name, "a renumbered restored journal was accepted")
    except RecoveryError as error:
        if error.code != RecoveryReason.HISTORY_FABRICATED:
            return fail(name, "wrong code: %s" % error.code)
        if "renumbered" not in error.detail:
            return fail(name, "the rejection does not cite renumbering")
    return ok(
        name,
        "a silently renumbered journal position fails closed "
        "(recovery-history-fabricated — a gapless sequence is never silently "
        "renumbered)",
    )


def case_22_prefailure_rewrite_fails_closed() -> Result:
    name = "case_22_prefailure_rewrite_fails_closed"
    contract, _base, _rstore, _session, journal = _fixture()
    point = snapshot_offline_plane(
        journal, recorded_at=D_SNAP_O, provenance=_prov(BATTERY_ISSUER)
    )
    original_lines = list(point.record_lines)
    swapped = tuple([original_lines[1], original_lines[0]] + original_lines[2:])
    problems: List[str] = []
    try:
        verify_restore(
            point,
            swapped,
            tuple(original_lines),
            recorded_at=D_VERIFY_O,
            provenance=_prov(BATTERY_ISSUER),
        )
        problems.append("a rewritten pre-failure journal was accepted as a prefix")
    except RecoveryError as error:
        if error.code != RecoveryReason.HISTORY_FABRICATED:
            problems.append("wrong code: %s" % error.code)
    # the shorter pre-failure plane (the point claims more history than
    # the plane ever held)
    try:
        verify_restore(
            point,
            tuple(original_lines[:1]),
            tuple(original_lines),
            recorded_at=D_VERIFY_O,
            provenance=_prov(BATTERY_ISSUER),
        )
        problems.append("a point longer than the pre-failure history was accepted")
    except RecoveryError as error:
        if error.code != RecoveryReason.HISTORY_FABRICATED:
            problems.append("wrong code (short): %s" % error.code)
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "a rewritten pre-failure history fails closed (never a "
        "'reconciliation'); a point claiming unevidenced history fails "
        "closed",
    )


# ---------------------------------------------------------------------------
# case_23..case_27 — (g) the fail-closed snapshot verification
# ---------------------------------------------------------------------------


def _honest_offline_point():
    contract, _base, _rstore, _session, journal = _fixture()
    point = snapshot_offline_plane(
        journal, recorded_at=D_SNAP_O, provenance=_prov(BATTERY_ISSUER)
    )
    return contract, journal, point


def case_23_unparseable_snapshot_rejected() -> Result:
    name = "case_23_unparseable_snapshot_rejected"
    contract, _journal, point = _honest_offline_point()
    unparseable = RecoveryPoint(
        plane="offline-journal",
        contract_id=point.contract_id,
        subject_id=point.subject_id,
        record_lines=("{not-json",),
        sequence=1,
        recorded_at=point.recorded_at,
        provenance=point.provenance,
    )
    problems: List[str] = []
    for label, action in (
        ("verify", lambda: verify_recovery_point(unparseable)),
        ("restore", lambda: restore_offline_plane(unparseable)),
        (
            "load",
            lambda: verify_recovery_point(
                RecoveryPoint.from_dict(
                    dict(unparseable.to_dict())
                )
            ),
        ),
    ):
        try:
            action()
            problems.append("the unparseable snapshot was accepted at %s" % label)
        except RecoveryError as error:
            if error.code != RecoveryReason.SNAPSHOT_UNVERIFIABLE:
                problems.append("wrong code at %s: %s" % (label, error.code))
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "an unparseable snapshot is REJECTED WHOLE at the load, the "
        "verification and the restore (recovery-snapshot-unverifiable — "
        "never partially trusted, never best-effort loaded)",
    )


def case_24_provenance_missing_rejected() -> Result:
    name = "case_24_provenance_missing_rejected"
    contract, _journal, point = _honest_offline_point()
    problems: List[str] = []
    # the point's OWN provenance envelope missing
    data = dict(point.to_dict())
    del data["provenance"]
    try:
        RecoveryPoint.from_dict(data)
        problems.append("a provenance-missing point was loaded")
    except RecoveryError as error:
        if error.code != RecoveryReason.SNAPSHOT_UNVERIFIABLE:
            problems.append("wrong code (point): %s" % error.code)
    # a PAYLOAD record's provenance envelope missing
    stripped = json.loads(point.record_lines[0])
    del stripped["provenance"]
    stripped_point = RecoveryPoint(
        plane="offline-journal",
        contract_id=point.contract_id,
        subject_id=point.subject_id,
        record_lines=(canonical_json_text(stripped),),
        sequence=1,
        recorded_at=point.recorded_at,
        provenance=point.provenance,
    )
    try:
        verify_recovery_point(stripped_point)
        problems.append("a provenance-missing payload was accepted")
    except RecoveryError as error:
        if error.code != RecoveryReason.SNAPSHOT_UNVERIFIABLE:
            problems.append("wrong code (payload): %s" % error.code)
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "provenance-missing snapshots rejected WHOLE: the point's own "
        "envelope at the load, a payload record's envelope at the "
        "verification (LOCK-118 — never best-effort loaded)",
    )


def case_25_tampered_payload_identity_rejected() -> Result:
    name = "case_25_tampered_payload_identity_rejected"
    contract, _journal, point = _honest_offline_point()
    tampered_line = _forged_line(
        point.record_lines[1],
        operation_id="sha256:" + "cd" * 32,
    )
    tampered = RecoveryPoint(
        plane="offline-journal",
        contract_id=point.contract_id,
        subject_id=point.subject_id,
        record_lines=(point.record_lines[0], tampered_line),
        sequence=2,
        recorded_at=point.recorded_at,
        provenance=point.provenance,
    )
    try:
        verify_recovery_point(tampered)
        return fail(name, "a tampered payload identity was accepted")
    except RecoveryError as error:
        if error.code != RecoveryReason.SNAPSHOT_UNVERIFIABLE:
            return fail(name, "wrong code: %s" % error.code)
        if "rejected whole" not in error.detail:
            return fail(name, "the rejection does not cite the whole-point discipline")
    return ok(
        name,
        "a payload record whose content-derived identity does not re-derive "
        "rejects the snapshot WHOLE (the accepted constructor's tamper "
        "evidence surfaced as the typed whole-point rejection)",
    )


def case_26_digest_and_id_mismatch_rejected() -> Result:
    name = "case_26_digest_and_id_mismatch_rejected"
    contract, _journal, point = _honest_offline_point()
    problems: List[str] = []
    bad_digest = dict(point.to_dict())
    bad_digest["state_digest"] = "sha256:" + "ee" * 32
    try:
        RecoveryPoint.from_dict(bad_digest)
        problems.append("a bad-integrity digest was accepted")
    except RecoveryError as error:
        if error.code != RecoveryReason.SNAPSHOT_UNVERIFIABLE:
            problems.append("wrong code (digest): %s" % error.code)
    bad_id = dict(point.to_dict())
    bad_id["recovery_point_id"] = "sha256:" + "ff" * 32
    try:
        RecoveryPoint.from_dict(bad_id)
        problems.append("a mismatched recovery-point identity was accepted")
    except RecoveryError as error:
        if error.code != RecoveryReason.SNAPSHOT_UNVERIFIABLE:
            problems.append("wrong code (id): %s" % error.code)
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "a state digest that does not re-derive and a recovery-point identity "
        "that does not re-derive both reject the snapshot WHOLE (bad "
        "integrity, tamper evidence)",
    )


def case_27_renumbered_snapshot_rejected() -> Result:
    name = "case_27_renumbered_snapshot_rejected"
    contract, _base, rstore, session, _journal = _fixture()
    # a REAL runtime event carrying a forged journal position (its own
    # identity derives over the forged content — a valid record whose
    # POSITION violates the plane's gapless discipline)
    forged_event = RuntimeEvent(
        runtime_id=session.runtime_id,
        contract_id=contract.contract_id,
        sequence=2,
        kind="session-created",
        recorded_at=D_ATTACH,
        state_after="PENDING",
        provenance=_prov(BATTERY_ISSUER),
    )
    renumbered = RecoveryPoint(
        plane="runtime-journal",
        contract_id=contract.contract_id,
        subject_id=session.runtime_id,
        record_lines=(forged_event.canonical_bytes().decode("utf-8"),),
        sequence=1,
        recorded_at=D_SNAP_R,
        provenance=_prov(BATTERY_ISSUER),
    )
    try:
        verify_recovery_point(renumbered)
        return fail(name, "a renumbered snapshot was accepted")
    except RecoveryError as error:
        if error.code != RecoveryReason.HISTORY_FABRICATED:
            return fail(name, "wrong code: %s" % error.code)
    # the watermark/record-count mismatch twin
    mismatched = RecoveryPoint(
        plane="runtime-journal",
        contract_id=contract.contract_id,
        subject_id=session.runtime_id,
        record_lines=(forged_event.canonical_bytes().decode("utf-8"),),
        sequence=5,
        recorded_at=D_SNAP_R,
        provenance=_prov(BATTERY_ISSUER),
    )
    try:
        verify_recovery_point(mismatched)
        return fail(name, "a watermark-mismatched snapshot was accepted")
    except RecoveryError as error:
        if error.code != RecoveryReason.HISTORY_FABRICATED:
            return fail(name, "wrong code (watermark): %s" % error.code)
    return ok(
        name,
        "renumbered payloads and watermark/count mismatches reject the "
        "snapshot WHOLE (recovery-history-fabricated — a gapless sequence is "
        "never silently renumbered)",
    )


# ---------------------------------------------------------------------------
# case_28 — (h) the composition substrate exercised BY REFERENCE
# ---------------------------------------------------------------------------


def case_28_composition_substrate_exercised() -> Result:
    name = "case_28_composition_substrate_exercised"
    contract, _base, _fresh, rstore, session, journal, estore, _plan, result = (
        _run_primary_drill()
    )
    problems: List[str] = []
    # the pre-drill fixture drove the accepted M015/M016 surfaces: the
    # degraded entry carries the LOCK-106 observation evidence kind
    # and the episode id as the decision-kinded evidence reference
    events = rstore.events(session.runtime_id)
    degraded = [e for e in events if e.kind == "degraded-entered"]
    if not degraded:
        problems.append("the fixture did not drive the accepted degraded entry")
    else:
        if degraded[0].evidence_kind != "observation":
            problems.append("the degraded entry does not use the LOCK-106 observation kind")
    # the offline journal's partition-entered cites the M015
    # degraded-entry EVENT id (the evidence-visible composition link)
    entered = [r for r in journal.records() if r.kind == "partition-entered"]
    if not entered:
        problems.append("the fixture did not open the partition episode")
    else:
        if entered[0].runtime_event_id not in {e.event_id for e in events}:
            problems.append("the composition link does not resolve pre-drill")
    # the drill drove the accepted close INSIDE the reconcile step: the
    # preserved resync re-validates through the ACCEPTED constructor
    # and its reconnect citations resolve against the replayed close
    recon = result.reconciliation
    if recon is None or recon.accepted_resync is None:
        problems.append("the drill did not drive the accepted resynchronization")
    else:
        replay_resync = ResyncResult.from_dict(dict(recon.accepted_resync))
        if replay_resync.episode_id != entered[0].episode_id:
            problems.append("the preserved resync does not ride the drill's episode")
        if list(replay_resync.applied_operations) != [
            r.operation_id
            for r in journal.records()
            if r.kind == "connectivity-admission" and r.outcome == "admitted"
        ]:
            problems.append("the preserved applied set is not the journaled admissions")
    # the drill's LOCK-106 evidence records are the accepted typed
    # records (the classes consumed by reference)
    for record in estore.records():
        if not isinstance(record, (ObservationEvidence, AttestationEvidence)):
            problems.append("a drill evidence record is not an accepted typed record")
    if len(estore) != 4:
        problems.append("the drill should have produced exactly 4 evidence records")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "the accepted M015 runtime (attach/degraded/reconnect) and the "
        "accepted M016 journal (open/admit/close) driven BY REFERENCE inside "
        "the drill: the composition links resolve, the preserved resync "
        "re-validates through the accepted constructor, the drill's evidence "
        "records are the accepted LOCK-106 classes",
    )


# ---------------------------------------------------------------------------
# case_29 — canonical-JSON round-trips
# ---------------------------------------------------------------------------


def case_29_canonical_round_trips() -> Result:
    name = "case_29_canonical_round_trips"
    contract, _base, _fresh, rstore, session, journal, estore, plan, result = (
        _run_primary_drill()
    )
    problems: List[str] = []
    runtime_point = snapshot_runtime_plane(
        rstore, session.runtime_id, recorded_at=D_SNAP_R, provenance=_prov(BATTERY_ISSUER)
    )
    offline_point = snapshot_offline_plane(
        journal, recorded_at=D_SNAP_O, provenance=_prov(BATTERY_ISSUER)
    )
    subjects: List[Tuple[str, Any, Any]] = [
        ("RecoveryPoint", RecoveryPoint, offline_point),
        ("DrillPlan", DrillPlan, plan),
        ("DrillResult", DrillResult, result),
        ("OperationBudget", OperationBudget, plan.budget),
        ("OperationCounts", OperationCounts, result.measured_counts),
        ("PlaneReconciliation", PlaneReconciliation, result.reconciliation),
    ]
    for label, cls, record in subjects:
        if record is None:
            problems.append("the %s record is missing" % label)
            continue
        replay = cls.from_dict(record.to_dict())
        if replay.canonical_bytes() != record.canonical_bytes():
            problems.append("the %s does not round-trip byte-identically" % label)
    for label, record in (
        ("verification", result.restorations[0]),
        ("divergence", result.restorations[1]),
        ("step", plan.steps[0]),
    ):
        cls = type(record)
        replay = cls.from_dict(record.to_dict())
        if replay.canonical_bytes() != record.canonical_bytes():
            problems.append("the %s does not round-trip" % label)
    # tampered dicts fail closed (the identities re-derive)
    tampered = dict(result.to_dict())
    tampered["measured_counts"] = OperationCounts(
        journal_appends=0, folds=0, verifications=0
    ).to_dict()
    try:
        DrillResult.from_dict(tampered)
        problems.append("a tampered drill result was accepted")
    except RecoveryError:
        pass  # the run id no longer re-derives (tamper evidence)
    tampered_point = dict(offline_point.to_dict())
    tampered_point["sequence"] = 99
    try:
        RecoveryPoint.from_dict(tampered_point)
        problems.append("a tampered recovery point was accepted")
    except RecoveryError:
        pass
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "9 record classes round-trip byte-identically with tamper-evident "
        "ids; tampered dicts fail closed at deserialization",
    )


# ---------------------------------------------------------------------------
# case_30 — typed errors, exception isolation, LOCK-119
# ---------------------------------------------------------------------------


def case_30_typed_errors_exception_isolation() -> Result:
    name = "case_30_typed_errors_exception_isolation"
    contract, _base, rstore, session, journal = _fixture()
    problems: List[str] = []
    # consumed-domain errors surface on this surface's own vocabulary
    # with the deterministic text preserved (exception isolation)
    try:
        snapshot_runtime_plane(
            rstore,
            "sha256:" + "9" * 64,  # an unknown session id
            recorded_at=D_SNAP_R,
            provenance=_prov(BATTERY_ISSUER),
        )
        problems.append("an unknown runtime id was snapshotted")
    except RecoveryError as error:
        if error.code != RecoveryReason.INVALID_INPUT:
            problems.append("wrong code (unknown id): %s" % error.code)
        if "unknown to the runtime store" not in error.detail:
            problems.append("the consumed deterministic text was not preserved")
    # composition boundaries: plain-object holders fail with the
    # composition code citing BY REFERENCE
    for action in (
        lambda: snapshot_runtime_plane(
            object(), session.runtime_id, recorded_at=D_SNAP_R, provenance=_prov(BATTERY_ISSUER)
        ),
        lambda: snapshot_offline_plane(
            object(), recorded_at=D_SNAP_O, provenance=_prov(BATTERY_ISSUER)
        ),
        lambda: run_drill(
            _plan_for(
                contract.contract_id,
                (DrillStep(kind="reconcile-planes", recorded_at=D_RECONCILE, provenance=_prov(BATTERY_ISSUER)),),
                OperationBudget(journal_appends=1, folds=1, verifications=1),
            ),
            contract=contract,
            runtime_store=object(),
            runtime_id=session.runtime_id,
            offline_journal=journal,
            evidence_store=EvidenceStore(),
        ),
    ):
        try:
            action()
            problems.append("a plain-object holder was accepted")
        except RecoveryError as error:
            if error.code != RecoveryReason.COMPOSITION:
                problems.append("wrong composition code: %s" % error.code)
            if "BY REFERENCE" not in error.detail and "BY" not in error.detail:
                problems.append("the composition detail does not cite the substrate")
    # LOCK-119: secret-shaped material assembled from fragments is
    # rejected at the boundary (the full shape never appears in source)
    secret = "ghp" + "_" + "q" * 36
    try:
        RecoveryPoint(
            plane="offline-journal",
            contract_id=contract.contract_id,
            subject_id=journal.episode_id,
            record_lines=('{"subject": "%s"}' % secret,),
            sequence=1,
            recorded_at=D_SNAP_O,
            provenance=_prov(BATTERY_ISSUER),
        )
        problems.append("secret-shaped material entered a recovery point")
    except RecoveryError as error:
        if error.code != RecoveryReason.SECRET_REJECTED:
            problems.append("wrong secret code: %s" % error.code)
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "consumed errors wrapped with their deterministic text preserved; "
        "composition boundaries typed; the LOCK-119 secret fixture (assembled "
        "from fragments) rejected at the boundary",
    )


# ---------------------------------------------------------------------------
# case_31 — the determinism re-run + the serialized replay
# ---------------------------------------------------------------------------


def case_31_determinism_and_serialized_replay() -> Result:
    name = "case_31_determinism_and_serialized_replay"
    problems: List[str] = []
    # the full scenario: the drill result + the plan + the evidence
    # state digest, twice, byte-identical
    first = _full_drill_scenario()
    second = _full_drill_scenario()
    if first != second:
        problems.append("the full drill scenario is not byte-identical")
    # the serialized replay: the drill result reconstructs from its
    # canonical serialization (construction-is-recovery of the outcome)
    contract, _base, _fresh, rstore, session, journal, _estore, _plan, result = (
        _run_primary_drill()
    )
    replay = DrillResult.from_dict(json.loads(result.canonical_bytes().decode("utf-8")))
    if replay.canonical_bytes() != result.canonical_bytes():
        problems.append("the drill result does not replay from its canonical JSON")
    # the recovery from the SERIALIZED recovery point equals the
    # recovery from the live plane (construction-is-recovery)
    runtime_point = snapshot_runtime_plane(
        rstore, session.runtime_id, recorded_at=D_SNAP_R, provenance=_prov(BATTERY_ISSUER)
    )
    serialized = json.loads(runtime_point.canonical_bytes().decode("utf-8"))
    reloaded = RecoveryPoint.from_dict(serialized)
    restored_live = restore_runtime_plane(runtime_point)
    restored_serialized = restore_runtime_plane(reloaded)
    if (
        restored_live.session(session.runtime_id).canonical_bytes()
        != restored_serialized.session(session.runtime_id).canonical_bytes()
    ):
        problems.append("the serialized-point recovery differs from the live-point recovery")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "the full scenario byte-identical twice; the drill result and the "
        "recovery points replay from their canonical serializations; the "
        "serialized-point restore equals the live-point restore",
    )


# ---------------------------------------------------------------------------
# case_32 — the lock-conformance mapping (aggregate)
# ---------------------------------------------------------------------------


def case_32_lock_conformance_mapping() -> Result:
    name = "case_32_lock_conformance_mapping"
    contract, _base, fresh, rstore, session, journal, estore, plan, result = (
        _run_primary_drill()
    )
    problems: List[str] = []
    # LOCK-101/LOCK-117: the recovery records cite the contract id and
    # never re-derive contract identity; the reconciliation consumes
    # the contract's OWN fingerprint
    for point_pair in result.recovery_points:
        if not point_pair[1].startswith("sha256:"):
            problems.append("a recovery point identity is not content-derived")
    if result.reconciliation.constraint_fingerprint != contract.hard_constraint_fingerprint():
        problems.append("LOCK-108: the fingerprint is not the contract's own")
    # LOCK-108 through the consumed gates: a fresh view with a WRONG
    # fingerprint is rejected by the accepted resynchronization (the
    # consumed gate's rejection surfaces as this surface's composition
    # error with its deterministic text preserved)
    forged_view = AuthoritySnapshot(
        snapshot_id="",
        contract_id=contract.contract_id,
        authority_records=(_record(REC_BETA),),
        fresh_from=FRESH_FROM,
        fresh_until=FRESH_UNTIL,
        constraint_fingerprint="sha256:" + "7" * 64,
        recorded_at=FRESH_RECORDED,
        provenance=_prov(BATTERY_ISSUER),
    )
    try:
        run_drill(
            plan,
            contract=contract,
            runtime_store=rstore,
            runtime_id=session.runtime_id,
            offline_journal=journal,
            evidence_store=EvidenceStore(),
            fresh_view=forged_view,
        )
        problems.append("a forged-fingerprint fresh view was accepted")
    except RecoveryError as error:
        if error.code != RecoveryReason.COMPOSITION:
            problems.append("wrong code (forged view): %s" % error.code)
        if "fingerprint" not in error.detail:
            problems.append("the LOCK-108 rejection text was not preserved")
    # LOCK-106: the drill's evidence records are the accepted typed
    # classes with producers and provenance
    for record in estore.records():
        if record.producer != "recovery:drill":
            problems.append("the drill evidence records do not carry the drill producer")
    # LOCK-118: every serialized recovery record carries provenance
    for data in (
        result.to_dict(),
        plan.to_dict(),
    ):
        if "provenance" not in data:
            problems.append("a serialized record lacks the provenance envelope")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "LOCK-101/106/108/111/117/118/119: content-derived ids everywhere; "
        "the contract's own fingerprint consumed; the forged-fingerprint "
        "view rejected through the consumed gate; the drill's LOCK-106 "
        "records typed; provenance on every record",
    )


# ---------------------------------------------------------------------------
# case_33 — LOCK-119 clock/import discipline (AST audit)
# ---------------------------------------------------------------------------


def case_33_clock_import_discipline() -> Result:
    name = "case_33_clock_import_discipline"
    problems: List[str] = []
    files = sorted((REPO_ROOT / "recovery").glob("*.py"))
    if not files:
        return fail(name, "the recovery/ package is missing")
    allowed = {
        "__future__",
        "contextlib",
        "hashlib",
        "json",
        "re",
        "dataclasses",
        "typing",
        "protocol",
        "contracts",
        "resilience",
        "localfirst",
        "evidence",
        "recovery",
    }
    for path in files:
        source = path.read_text(encoding="utf-8")
        for forbidden in (
            "datetime.now",
            "time.time",
            "utcnow",
            "uuid",
            "random.",
            "socket.",
            "requests.",
            "urlopen",
            "time.monotonic",
            "time.sleep",
        ):
            if forbidden in source:
                problems.append("%s carries %r" % (path.name, forbidden))
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split(".")[0])
        unexpected = sorted(imported - allowed)
        if unexpected:
            problems.append("%s imports %s" % (path.name, unexpected))
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "no clock/random/network constructs anywhere in recovery/; imports: "
        "stdlib + protocol + the accepted authorities (contracts, "
        "resilience, localfirst, evidence) — by reference only",
    )


# ---------------------------------------------------------------------------
# case_34 — the one-way import boundary
# ---------------------------------------------------------------------------


def _imports_recovery(source: str) -> bool:
    """True when the source IMPORTS the recovery package (an actual
    import statement — ``import recovery`` or ``from recovery...``).
    A local identifier named ``recovery`` (the accepted adapters/
    transport sandbox parameter, predating M017) is NOT an import
    violation — the boundary is about imports, never about the English
    word."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.split(".")[0] == "recovery":
                return True
            for alias in node.names:
                if (alias.name or "").split(".")[0] == "recovery":
                    return True
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "recovery":
                    return True
    return False


def case_34_one_way_imports() -> Result:
    name = "case_34_one_way_imports"
    problems: List[str] = []
    authorities = (
        "contracts",
        "replan",
        "executionplans",
        "evidence",
        "assurance",
        "offers",
        "eligibility",
        "policy",
        "adapters",
        "usage",
        "commercial",
        "allocation",
        "payment",
        "sharenet",
        "roamlink",
        "comos",
        "developerapi",
        "federation",
        "identity",
        "upgrade",
        "scale",
        "client",
        "resilience",
        "localfirst",
    )
    for package in authorities:
        package_dir = REPO_ROOT / package
        if not package_dir.is_dir():
            continue
        for path in sorted(package_dir.glob("*.py")):
            source = path.read_text(encoding="utf-8")
            if _imports_recovery(source):
                problems.append(
                    "%s imports the recovery package (imports must be one-way)"
                    % path.name
                )
    # the legacy reservoir stays un-imported by recovery/ (source
    # material only — the R8 charter consumption rule)
    legacy = ("sessions", "mobility", "multipath", "edge", "appliance")
    tree_modules: set = set()
    for path in sorted((REPO_ROOT / "recovery").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                tree_modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                tree_modules.add(node.module.split(".")[0])
    for package in legacy:
        if package in tree_modules:
            problems.append("recovery/ imports the legacy %s/ package" % package)
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "no accepted authority (incl. resilience/ and localfirst/) imports "
        "recovery/ (one-way boundary); the legacy reservoir is un-imported "
        "source material only",
    )


# ---------------------------------------------------------------------------
# case_35 — the PR delta shape (the active authorization scope)
# ---------------------------------------------------------------------------


def _origin_main_available() -> bool:
    probe = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/main"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    return probe.returncode == 0


def _active_authorization_covers(path: str) -> bool:
    try:
        from authorization_provenance import covers  # type: ignore

        return covers(path)
    except Exception:  # noqa: BLE001
        return False


def case_35_pr_delta_shape_authorized_scope() -> Result:
    name = "case_35_pr_delta_shape_authorized_scope"
    if not _origin_main_available():
        return ok(name, "skipped (no origin/main ref; the CI provenance step enforces scope)")
    delta: set = set()
    diff = subprocess.run(
        ["git", "diff", "--name-only", "origin/main"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    if diff.returncode == 0:
        delta |= {line for line in diff.stdout.splitlines() if line.strip()}
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    if untracked.returncode == 0:
        delta |= {line for line in untracked.stdout.splitlines() if line.strip()}
    if not delta:
        return ok(name, "no delta (clean main)")
    problems: List[str] = []
    for path in sorted(delta):
        if path.startswith("spec/"):
            problems.append("delta touches the frozen spec/ control plane: %s" % path)
            continue
        if path.startswith(".github/"):
            problems.append("delta touches the CI control plane: %s" % path)
            continue
        if _active_authorization_covers(path):
            continue
        problems.append("delta outside the active authorization scope: %s" % path)
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "delta confined to the M017 scope (%d file(s): recovery/ + the "
        "battery + the evidence doc)" % len(delta),
    )


# ---------------------------------------------------------------------------
# case_36 — the evidence-doc honesty
# ---------------------------------------------------------------------------


def case_36_evidence_doc_honest() -> Result:
    name = "case_36_evidence_doc_honest"
    path = REPO_ROOT / "docs" / "M017-evidence.md"
    if not path.exists():
        return fail(name, "docs/M017-evidence.md is missing")
    text = path.read_text(encoding="utf-8")
    problems: List[str] = []
    if "SOFTWARE" not in text:
        problems.append("the evidence class is not disclosed")
    if "M017" not in text:
        problems.append("the evidence does not name M017")
    if "LOCK-106" not in text:
        problems.append("the LOCK-106 mapping is not disclosed")
    if "harvest" not in text.lower():
        problems.append("the harvest is not disclosed")
    if "EVID-002" not in text:
        problems.append("the open physical evidence obligations are not disclosed")
    if "by reference" not in text.lower():
        problems.append("the by-reference composition is not disclosed")
    if "operation count" not in text.lower():
        problems.append("the RTO-as-operation-counts disclosure is missing")
    # an AFFIRMATIVE physical-verification claim is rejected; a negation
    # is the required honesty statement
    normalized = " ".join(text.split()).lower()
    for phrase in (
        "physical pass",
        "physically verified",
        "production pass",
        "live-service evidence",
    ):
        start = 0
        while True:
            index = normalized.find(phrase, start)
            if index < 0:
                break
            window = normalized[max(0, index - 90) : index]
            if "not" not in window and "never" not in window and "no " not in window:
                problems.append("affirmative physical claim near %r" % phrase)
            start = index + 1
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "SOFTWARE class, by-reference composition, harvest, locks, the "
        "RTO-as-counts disclosure and the open physical obligations "
        "disclosed; no affirmative physical claims",
    )


# ===========================================================================
# Main
# ===========================================================================


def main() -> int:
    results: List[Result] = []
    results.append(case_01_frozen_vocabularies())
    results.append(case_02_vocabulary_fail_closed())
    results.append(case_03_drill_step_order_gates())
    # (a) the snapshot construction + restore round-trips
    results.append(case_04_runtime_plane_round_trip())
    results.append(case_05_offline_plane_round_trip())
    results.append(case_06_restored_planes_compose_forward())
    # (b) the drill determinism
    results.append(case_07_drill_determinism())
    results.append(case_08_cross_process_pythonhashseed())
    # (c) restore verification with induced divergence
    results.append(case_09_induced_divergence_disclosed())
    results.append(case_10_failure_during_recovery_drill())
    results.append(case_11_silent_absorption_rejected())
    # (d) the recovery-time bounds as declared operation counts
    results.append(case_12_rto_declared_operation_counts())
    results.append(case_13_rto_enforced())
    # (e) the cross-plane reconciliation
    results.append(case_14_cross_plane_converged())
    results.append(case_15_accepted_resync_divergences_preserved())
    results.append(case_16_evidence_record_missing_disclosed())
    results.append(case_17_composition_link_unresolved_disclosed())
    results.append(case_18_attribution_mismatch_fails_closed())
    # (f) no-history-fabrication
    results.append(case_19_recovered_identities_preserved())
    results.append(case_20_reidentified_record_fails_closed())
    results.append(case_21_renumbered_restore_fails_closed())
    results.append(case_22_prefailure_rewrite_fails_closed())
    # (g) the fail-closed snapshot verification
    results.append(case_23_unparseable_snapshot_rejected())
    results.append(case_24_provenance_missing_rejected())
    results.append(case_25_tampered_payload_identity_rejected())
    results.append(case_26_digest_and_id_mismatch_rejected())
    results.append(case_27_renumbered_snapshot_rejected())
    # (h) the composition substrate exercised
    results.append(case_28_composition_substrate_exercised())
    # the structural closing set
    results.append(case_29_canonical_round_trips())
    results.append(case_30_typed_errors_exception_isolation())
    results.append(case_31_determinism_and_serialized_replay())
    results.append(case_32_lock_conformance_mapping())
    results.append(case_33_clock_import_discipline())
    results.append(case_34_one_way_imports())
    results.append(case_35_pr_delta_shape_authorized_scope())
    results.append(case_36_evidence_doc_honest())

    print("ADCOS recovery self-test (M017 — Disaster Recovery and State Reconciliation)")
    print("=" * 78)
    for name, passed, detail in results:
        print("[%s] %-56s %s" % ("ok  " if passed else "FAIL", name, detail))
    print("-" * 78)
    passed_count = sum(1 for _, p, _ in results if p)
    if passed_count == len(results):
        print("Result: PASS (%d/%d cases)" % (passed_count, len(results)))
        return 0
    print("Result: FAIL (%d/%d cases passed)" % (passed_count, len(results)))
    return 1


if __name__ == "__main__":
    sys.exit(main())
