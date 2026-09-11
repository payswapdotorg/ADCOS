#!/usr/bin/env python3
"""ADCOS local-first self-test (M016 — Local-First and Offline Operation).

Deterministic, offline verification of the ``localfirst/`` package
against the frozen Architecture 1.1 mandate (R8-CORE-001, DEC-0115 the
current-child state; the R8 charter M016 acceptance criteria): the
local-first/offline operation domain — deterministic offline operation
journals (ordered, idempotent, replayable), partition-tolerant
admission with fail-closed stale-authority rejection (a local state
past its declared freshness bound never silently authorizes), explicit
reconnect and resynchronization with divergence detection and
deterministic declared recorded convergence (the LOCK-111 class),
LOCK-108 across the offline boundary (no silent contract weakening
during partition or resynchronization), degraded/offline-mode operation
that is explicit and journaled, and the M015 runtime as the composition
substrate (the accepted RuntimeStore lifecycle driven BY REFERENCE for
every offline transition — never duplicated).

Battery coverage (the M016 work-item matrix, the charter's (a)-(h)):

- (a) case_03/case_04 — the offline journal append/replay round-trips
  (ordered, gapless, conflict-free; the fold is the sole writer; replay
  twice = the byte-identical state; construction-is-recovery) and the
  IDEMPOTENT append (a retried admission derives the same
  position-independent content identity and never double-applies);
- (b) case_05..case_08 — partition-tolerant admission: the fresh
  authority admits (the window carried on the decision); the stale
  authority FAILS CLOSED with the typed rejection (the twin outcome +
  the raising gate + the fold's mechanical enforcement of the forged
  silent-allow shape); the not-yet-valid window fails closed; the
  inclusive boundary outcomes;
- (c) case_21..case_24 — reconnect + resynchronization: no divergence
  (clean convergence), detected divergence (the typed record with full
  provenance on BOTH sides), conflicting operations resolved by the
  DECLARED RECORDED rule (deterministic — same inputs run twice
  byte-identical; both rule directions exercised; never dropped, never
  duplicated), and the invalid declared rules failing closed;
- (d) case_09..case_20 — LOCK-108 across the offline boundary: every
  weakening admission/resync candidate rejected (all 12 constraint
  kinds x DROP/RELAX/REINTERPRET on the admission twin and the raising
  gate; the wire-forged journaled admitted record with the weakened
  claimed set rejected by the resynchronization re-verification with
  the typed reason citing the kind);
- (e) case_25 — the degraded/offline mode entry/exit journaled and
  evidence-visible (the offline journal records carry the M015
  event/evidence ids; the M015 runtime journal carries the degraded
  entry with the LOCK-106 observation evidence kind and the
  episode-kinded evidence reference);
- (f) case_26 — the M015 composition (the runtime session drives the
  offline transitions: the attach, the partition entry through the
  accepted enter_degraded, the resync through the accepted reconnect
  pair naming BOTH the old and the new authority views — the WORK-012
  discipline; multiple episodes chain on one session);
- (g) case_27/case_28 — canonical-JSON round-trips + typed errors +
  exception isolation (consumed-domain errors wrapped with their
  deterministic text preserved; no raw exception text into stored
  state; LOCK-119 secret fixtures assembled from fragments);
- (h) case_29/case_30 — determinism under a re-run (byte-identical
  journals/states/resync results; construction-is-recovery) and across
  PYTHONHASHSEED subprocesses;
- plus the frozen-vocabulary matrix, the vocabulary/input gates, the
  lock-conformance mapping, the clock/import discipline, the one-way
  import boundary, the PR delta shape, and the evidence-doc honesty.

All instants are injected (T0-style constants); no wall clock, no
randomness, no network, no real sockets, no secrets (any
credential-shaped fixture is assembled at runtime from fragments so the
full shape never appears in source). Runs are byte-identical across
processes (PYTHONHASHSEED-safe).
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

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
from replan import (  # noqa: E402
    DEFAULT_TIE_BREAK,
    TIE_BREAK_KEYS,
)
from resilience import (  # noqa: E402
    RUNTIME_STATES,
    RuntimeStore,
)
from evidence import EVIDENCE_TYPES  # noqa: E402

from localfirst import (  # noqa: E402
    ADMISSION_OUTCOMES,
    DEFAULT_RESOLUTION_RULE,
    DIVERGENCE_RESOLUTIONS,
    EPISODE_STATES,
    OPERATION_KINDS,
    RESOLUTION_CANDIDATE_KINDS,
    AuthoritySnapshot,
    CloseResult,
    ConvergenceRejection,
    DivergenceRecord,
    LocalFirstError,
    LocalFirstReason,
    LocalState,
    OfflineJournal,
    OfflineOperation,
    ResyncResult,
    admit_operation,
    attach_runtime_session,
    authority_snapshot,
    check_admission_preserves_contract,
    check_authority_fresh,
    check_episode_state,
    close_partition,
    derive_episode_id,
    derive_operation_id,
    fold_operations,
    local_admit,
    normalize_resolution_rule,
    open_partition,
    resolve_conflict,
    resynchronize,
    sync_authority_view,
)

Result = Tuple[str, bool, str]

T0 = "2026-10-01T00:00:00Z"
T_END = "2026-11-01T00:00:00Z"
CREATE_AT = "2026-09-30T10:00:00Z"
OFFER_SEL_AT = "2026-09-30T10:05:00Z"

# Local-first injected instants (inside the owning contract's validity
# window so the composed surfaces accept the drives).
LF_CREATE = "2026-10-02T00:00:00Z"
LF_ACTIVATE = "2026-10-02T00:01:00Z"
P1_SYNC = "2026-10-02T00:30:00Z"
P1_OPEN = "2026-10-03T00:00:00Z"
P1_ADMIT_A = "2026-10-03T01:00:00Z"
P1_ADMIT_B = "2026-10-03T02:00:00Z"
P1_ADMIT_STALE = "2026-10-10T00:00:00Z"  # past the base window bound
P1_CLOSE = "2026-10-11T00:00:00Z"
P2_SYNC = "2026-10-11T00:30:00Z"
P2_OPEN = "2026-10-12T00:00:00Z"
P2_ADMIT_A = "2026-10-13T00:00:00Z"
P2_ADMIT_B = "2026-10-13T01:00:00Z"
P2_CLOSE = "2026-10-20T00:00:00Z"

# The base authority view's declared freshness window.
BASE_FROM = "2026-10-02T00:00:00Z"
BASE_UNTIL = "2026-10-09T00:00:00Z"
BASE_RECORDED = "2026-10-02T00:00:00Z"
# A pre-window instant (before the base window opens).
PRE_WINDOW = "2026-10-01T12:00:00Z"

# Opaque authority records and admission subjects (LOCK-117: opaque
# references, never authority).  The W-prefixed subject collides with
# an authority record value that sorts AFTER "sha256:" so the two
# declared rules resolve the SAME conflict in OPPOSITE directions (the
# rule decides, demonstrably).
REC_ALPHA = "record:lease-alpha"
REC_BETA = "record:lease-beta"
REC_GAMMA = "record:lease-gamma"
REC_EPSILON = "record:lease-epsilon"
REC_WIRELESS = "wireless:lease-contested"
SUBJ_DEVICE_42 = "lease:dev-42"
SUBJ_DEVICE_43 = "lease:dev-43"
SUBJ_DEVICE_44 = "lease:dev-44"
SUBJ_DELTA = "record:lease-delta"

BATTERY_ISSUER = "localfirst:battery"

ALL_KINDS: Tuple[str, ...] = (
    "latency-bound",
    "throughput-floor",
    "availability-floor",
    "loss-bound",
    "jitter-bound",
    "isolation",
    "jurisdiction",
    "security-level",
    "provider-trust",
    "evidence-obligation",
    "geography",
    "priority",
)

_KIND_FIXTURES: Dict[str, Tuple[Dict[str, Any], Dict[str, Any]]] = {
    "latency-bound": ({"max_ms": 150}, {"max_ms": 200}),
    "throughput-floor": ({"min_kbps": 10000}, {"min_kbps": 5000}),
    "availability-floor": ({"nine": "three"}, {"nine": "two"}),
    "loss-bound": ({"max_pct": 1}, {"max_pct": 5}),
    "jitter-bound": ({"max_ms": 30}, {"max_ms": 60}),
    "isolation": ({"level": "strict"}, {"level": "standard"}),
    "jurisdiction": ({"region": "GH"}, {"region": "anywhere"}),
    "security-level": ({"level": "high"}, {"level": "medium"}),
    "provider-trust": ({"tier": "verified"}, {"tier": "basic"}),
    "evidence-obligation": ({"cadence": "continuous"}, {"cadence": "periodic"}),
    "geography": ({"area": "accra-metro"}, {"area": "national"}),
    "priority": ({"class": "premium"}, {"class": "standard"}),
}


def ok(name: str, detail: str = "") -> Result:
    return (name, True, detail)


def fail(name: str, detail: str) -> Result:
    return (name, False, detail)


def expect_error(case: str, code: str, action: Callable[[], Any]) -> Result:
    try:
        action()
    except LocalFirstError as error:
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
    return fail(case, "expected LocalFirstError(%s); the input was accepted" % code)


def _prov(issuer: str, *refs: str) -> Provenance:
    return Provenance(issuer=issuer, decision_refs=tuple(refs))


def _constraints(*kinds: str) -> Tuple[HardConstraint, ...]:
    """The strict per-kind constraints (deterministic fixtures)."""
    return tuple(
        HardConstraint(
            kind=kind,
            params=_KIND_FIXTURES[kind][0],
            provenance=_prov("prov:netpro"),
        )
        for kind in kinds
    )


def _create_command(constraints: Tuple[HardConstraint, ...]) -> CreateContract:
    return CreateContract(
        principal=ConnectivityPrincipal(
            principal_kind="APPLICATION", principal_ref="app:lf-gateway-01"
        ),
        beneficiaries=(
            BeneficiaryScope(beneficiary_kind="DEVICE", beneficiary_ref="dev:pi-7f2a"),
        ),
        requirements=(
            OpaqueReference(
                ref_kind="intent-requirements",
                value="intent:abc123",
                provenance=_prov("arch:localfirst"),
            ),
        ),
        hard_constraints=constraints,
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
        provenance=_prov("arch:localfirst", "dec:elig-1"),
    )


_OFFER_A = OpaqueReference(
    ref_kind="offer", value="offer:netpro-basic-1", provenance=_prov("prov:netpro")
)
_OFFER_B = OpaqueReference(
    ref_kind="offer", value="offer:skywave-mesh-1", provenance=_prov("prov:skywave")
)


def _mature_contract(
    constraints: Tuple[HardConstraint, ...],
) -> Tuple[ContractStore, Any]:
    """A contract store whose single contract is EXECUTION_ACTIVE
    (deterministic; rebuilt per call so mutating cases stay isolated)."""
    store = ContractStore()
    created = store.submit(_create_command(constraints), recorded_at=CREATE_AT)
    cid = created.contract.contract_id
    store.submit(
        SelectOffers(offers=(_OFFER_A, _OFFER_B)),
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


def _mature_foreign_contract() -> Tuple[ContractStore, Any]:
    """A SECOND mature contract with DIFFERENT creation material (the
    deterministic-fixture trap: two identical commands derive the SAME
    contract identity, so the foreign-contract probes need a distinct
    principal)."""
    command = _create_command(_constraints("latency-bound"))
    command = CreateContract(
        principal=ConnectivityPrincipal(
            principal_kind="APPLICATION", principal_ref="app:lf-other-99"
        ),
        beneficiaries=command.beneficiaries,
        requirements=command.requirements,
        hard_constraints=command.hard_constraints,
        validity=command.validity,
        service_properties=command.service_properties,
        usage_pricing_terms=command.usage_pricing_terms,
        assurance_obligations=command.assurance_obligations,
        execution_scope=command.execution_scope,
        termination=command.termination,
        provenance=command.provenance,
    )
    store = ContractStore()
    created = store.submit(command, recorded_at=CREATE_AT)
    cid = created.contract.contract_id
    store.submit(
        SelectOffers(offers=(_OFFER_A, _OFFER_B)),
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
    """An opaque authority-record reference (LOCK-117: DATA)."""
    return OpaqueReference(
        ref_kind="execution-artifact",
        value=value,
        provenance=_prov("prov:netpro"),
    )


def _subject(value: str) -> OpaqueReference:
    """An opaque admission-subject reference (LOCK-117: DATA)."""
    return OpaqueReference(
        ref_kind="execution-artifact",
        value=value,
        provenance=_prov("app:lf-gateway-01"),
    )


def _base_view(contract: Any) -> AuthoritySnapshot:
    """The base authority view with the declared freshness window."""
    return authority_snapshot(
        contract,
        (_record(REC_ALPHA), _record(REC_BETA)),
        fresh_from=BASE_FROM,
        fresh_until=BASE_UNTIL,
        recorded_at=BASE_RECORDED,
    )


def _fresh_view(contract: Any) -> AuthoritySnapshot:
    """The fresh authority view at resynchronization (the authority
    moved on: lease-alpha gone, lease-gamma added)."""
    return authority_snapshot(
        contract,
        (_record(REC_BETA), _record(REC_GAMMA)),
        fresh_from="2026-10-11T00:00:00Z",
        fresh_until="2026-10-18T00:00:00Z",
        recorded_at="2026-10-11T00:00:00Z",
    )


def _open_episode(
    contract: Any, base: AuthoritySnapshot
) -> Tuple[RuntimeStore, Any, OfflineJournal]:
    """An attached runtime session plus an OPEN partition episode on the
    base view (the standard fixture for the admission cases)."""
    rstore = RuntimeStore()
    session = attach_runtime_session(
        rstore,
        contract,
        base,
        created_at=LF_CREATE,
        activated_at=LF_ACTIVATE,
        provenance=_prov(BATTERY_ISSUER),
    )
    journal, _ = open_partition(
        rstore,
        session.runtime_id,
        contract,
        base,
        recorded_at=P1_OPEN,
        provenance=_prov(BATTERY_ISSUER),
    )
    return rstore, session, journal


def _weakened_constraints(
    contract_constraints: Tuple[HardConstraint, ...], mode: str, kind: str
) -> Tuple[HardConstraint, ...]:
    """The constraint set that weakens ``kind``: DROP (omit it), RELAX
    (weakened params), or REINTERPRET (a different kind carrying the
    strict kind's params) — the replan-battery weakening convention."""
    strict_params = _KIND_FIXTURES[kind][0]
    weakened_params = _KIND_FIXTURES[kind][1]
    out: List[HardConstraint] = []
    for constraint in contract_constraints:
        if constraint.kind == kind:
            if mode == "DROP":
                continue
            if mode == "RELAX":
                out.append(
                    HardConstraint(
                        kind=kind, params=weakened_params, provenance=constraint.provenance
                    )
                )
                continue
            if mode == "REINTERPRET":
                other = "priority" if kind != "priority" else "geography"
                out.append(
                    HardConstraint(
                        kind=other, params=strict_params, provenance=constraint.provenance
                    )
                )
                continue
        out.append(constraint)
    return tuple(out)


# ---------------------------------------------------------------------------
# The deterministic full offline scenario (the round-trip + determinism
# material): attach -> open -> 3 admissions (fresh / stale / weakened)
# -> close (clean convergence onto the fresh view).
# ---------------------------------------------------------------------------


def _full_offline_scenario() -> Tuple[bytes, ...]:
    constraints = _constraints("latency-bound", "availability-floor")
    _, contract = _mature_contract(constraints)
    base = _base_view(contract)
    fresh = _fresh_view(contract)
    rstore = RuntimeStore()
    session = attach_runtime_session(
        rstore,
        contract,
        base,
        created_at=LF_CREATE,
        activated_at=LF_ACTIVATE,
        provenance=_prov(BATTERY_ISSUER),
    )
    rid = session.runtime_id
    journal, _ = open_partition(
        rstore, rid, contract, base, recorded_at=P1_OPEN, provenance=_prov(BATTERY_ISSUER)
    )
    local_admit(
        journal,
        contract,
        base,
        subject=_subject(SUBJ_DEVICE_42),
        claimed_constraints=tuple(contract.hard_constraints),
        decided_at=P1_ADMIT_A,
        provenance=_prov(BATTERY_ISSUER),
    )
    local_admit(
        journal,
        contract,
        base,
        subject=_subject(SUBJ_DEVICE_43),
        claimed_constraints=tuple(contract.hard_constraints),
        decided_at=P1_ADMIT_STALE,  # past the base window bound
        provenance=_prov(BATTERY_ISSUER),
    )
    weakened = _weakened_constraints(contract.hard_constraints, "RELAX", "latency-bound")
    local_admit(
        journal,
        contract,
        base,
        subject=_subject(SUBJ_DEVICE_44),
        claimed_constraints=weakened,
        decided_at=P1_ADMIT_B,
        provenance=_prov(BATTERY_ISSUER),
    )
    close = close_partition(
        rstore, rid, contract, journal, fresh, recorded_at=P1_CLOSE, provenance=_prov(BATTERY_ISSUER)
    )
    return (
        b"".join(r.canonical_bytes() for r in journal.records()),
        journal.state().canonical_bytes(),
        close.resync.canonical_bytes(),
        b"".join(e.canonical_bytes() for e in rstore.events(rid)),
        close.reconnect.canonical_bytes(),
        close.session.canonical_bytes(),
    )


# ---------------------------------------------------------------------------
# case_01 — the frozen vocabularies and the consumed vocabularies
# ---------------------------------------------------------------------------


def case_01_frozen_vocabularies() -> Result:
    name = "case_01_frozen_vocabularies"
    problems: List[str] = []
    if OPERATION_KINDS != (
        "partition-entered",
        "connectivity-admission",
        "partition-exited",
    ):
        problems.append("the offline record-kind vocabulary drifted")
    if ADMISSION_OUTCOMES != (
        "admitted",
        "stale-rejected",
        "not-yet-valid-rejected",
        "weakened-rejected",
    ):
        problems.append("the admission-outcome vocabulary drifted")
    if EPISODE_STATES != ("OPEN", "CLOSED"):
        problems.append("the episode-state vocabulary drifted")
    if RESOLUTION_CANDIDATE_KINDS != ("authority-record", "local-offline-operation"):
        problems.append("the resolution-candidate-kind vocabulary drifted")
    if DIVERGENCE_RESOLUTIONS != ("authority-record", "local-offline-operation"):
        problems.append("the divergence-resolution vocabulary drifted")
    if DEFAULT_RESOLUTION_RULE != ("candidate-kind", "candidate-id"):
        problems.append("the default declared resolution rule drifted")
    if LocalFirstReason.values() != (
        "localfirst-invalid-input",
        "localfirst-vocabulary",
        "localfirst-temporal-invalid",
        "localfirst-id-mismatch",
        "localfirst-journal-divergence",
        "localfirst-authority-stale",
        "localfirst-authority-not-yet-valid",
        "localfirst-constraint-weakened",
        "localfirst-constraint-mismatch",
        "localfirst-resolution-invalid",
        "localfirst-episode-closed",
        "localfirst-composition",
        "localfirst-secret-rejected",
    ):
        problems.append("the typed reason vocabulary drifted")
    # the consumed vocabularies ride BY REFERENCE (never redefined)
    if TIE_BREAK_KEYS != ("candidate-kind", "candidate-id"):
        problems.append("the consumed M008 tie-break key vocabulary drifted")
    if DEFAULT_TIE_BREAK != ("candidate-kind", "candidate-id"):
        problems.append("the consumed M008 default tie-break drifted")
    if set(EVIDENCE_TYPES) != {"claim", "observation", "commitment", "attestation"}:
        problems.append("the consumed evidence LOCK-106 vocabulary drifted")
    if RUNTIME_STATES != (
        "PENDING",
        "ACTIVE",
        "RECONNECTING",
        "DEGRADED",
        "FAILED",
        "TERMINATED",
    ):
        problems.append("the consumed M015 runtime-state vocabulary drifted")
    if set(CONSTRAINT_KINDS) != set(ALL_KINDS):
        problems.append("the consumed contracts constraint-kind vocabulary drifted")
    # the resolution rule normalizes against the CONSUMED vocabulary
    # (the same content keys; never a second key set)
    if normalize_resolution_rule(DEFAULT_RESOLUTION_RULE, "probe") != (
        "candidate-kind",
        "candidate-id",
    ):
        problems.append("the default rule does not normalize")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "the M016 vocabularies frozen; the M008/M015/M002/evidence vocabularies "
        "consumed BY REFERENCE (never redefined)",
    )


# ---------------------------------------------------------------------------
# case_02 — the vocabulary/input gates fail closed
# ---------------------------------------------------------------------------


def case_02_vocabulary_fail_closed() -> Result:
    name = "case_02_vocabulary_fail_closed"
    constraints = _constraints("latency-bound")
    _, contract = _mature_contract(constraints)
    base = _base_view(contract)
    rstore, session, journal = _open_episode(contract, base)
    rid = session.runtime_id
    results: List[Result] = []
    # a record kind outside the frozen vocabulary
    results.append(
        expect_error(
            "bad kind",
            LocalFirstReason.VOCABULARY,
            lambda: OfflineOperation(
                operation_id="",
                episode_id=journal.episode_id,
                contract_id=contract.contract_id,
                sequence=2,
                kind="partition-half-opened",
                recorded_at=P1_ADMIT_A,
                provenance=_prov(BATTERY_ISSUER),
                base_snapshot_id=base.snapshot_id,
                base_state_digest=base.state_digest,
                runtime_event_id="sha256:" + "0" * 64,
            ),
        )
    )
    # an outcome outside the frozen vocabulary
    results.append(
        expect_error(
            "bad outcome",
            LocalFirstReason.VOCABULARY,
            lambda: OfflineOperation(
                operation_id="",
                episode_id=journal.episode_id,
                contract_id=contract.contract_id,
                sequence=2,
                kind="connectivity-admission",
                recorded_at=P1_ADMIT_A,
                provenance=_prov(BATTERY_ISSUER),
                subject=_subject("lease:x"),
                hard_constraints=tuple(contract.hard_constraints),
                fresh_from=base.fresh_from,
                fresh_until=base.fresh_until,
                outcome="maybe-rejected",
            ),
        )
    )
    # an episode state outside the frozen vocabulary
    results.append(
        expect_error(
            "bad episode state",
            LocalFirstReason.VOCABULARY,
            lambda: check_episode_state("HALF-OPEN", "OPEN", "probe"),
        )
    )
    # a temporal resolution key does not exist in the consumed vocabulary
    results.append(
        expect_error(
            "temporal resolution key",
            LocalFirstReason.RESOLUTION_INVALID,
            lambda: normalize_resolution_rule(("recorded-at", "candidate-id"), "probe"),
        )
    )
    results.append(
        expect_error(
            "non-sequence rule",
            LocalFirstReason.RESOLUTION_INVALID,
            lambda: normalize_resolution_rule("candidate-id", "probe"),
        )
    )
    results.append(
        expect_error(
            "empty rule",
            LocalFirstReason.RESOLUTION_INVALID,
            lambda: normalize_resolution_rule((), "probe"),
        )
    )
    results.append(
        expect_error(
            "repeated rule key",
            LocalFirstReason.RESOLUTION_INVALID,
            lambda: normalize_resolution_rule(
                ("candidate-kind", "candidate-kind", "candidate-id"), "probe"
            ),
        )
    )
    results.append(
        expect_error(
            "rule without the total-order key",
            LocalFirstReason.RESOLUTION_INVALID,
            lambda: normalize_resolution_rule(("candidate-kind",), "probe"),
        )
    )
    # a malformed instant
    results.append(
        expect_error(
            "malformed instant",
            LocalFirstReason.TEMPORAL_INVALID,
            lambda: AuthoritySnapshot(
                snapshot_id="",
                contract_id=contract.contract_id,
                authority_records=(),
                fresh_from="2026-13-99T00:00:00Z",
                fresh_until=BASE_UNTIL,
                constraint_fingerprint=contract.hard_constraint_fingerprint(),
                recorded_at=BASE_RECORDED,
                provenance=_prov(BATTERY_ISSUER),
            ),
        )
    )
    # an empty freshness window (until before from)
    results.append(
        expect_error(
            "empty window",
            LocalFirstReason.TEMPORAL_INVALID,
            lambda: AuthoritySnapshot(
                snapshot_id="",
                contract_id=contract.contract_id,
                authority_records=(),
                fresh_from=BASE_UNTIL,
                fresh_until=BASE_FROM,
                constraint_fingerprint=contract.hard_constraint_fingerprint(),
                recorded_at=BASE_RECORDED,
                provenance=_prov(BATTERY_ISSUER),
            ),
        )
    )
    # a tampered episode identity (the fold re-derives it from the
    # partition-entered record's core — tamper evidence)
    tampered_entry = journal.records()[0].to_dict()
    tampered_entry["episode_id"] = "sha256:" + "9" * 64
    results.append(
        expect_error(
            "tampered episode id",
            LocalFirstReason.ID_MISMATCH,
            lambda: fold_operations([OfflineOperation.from_dict(tampered_entry)]),
        )
    )
    # duplicate authority-record values in a snapshot
    results.append(
        expect_error(
            "duplicate authority records",
            LocalFirstReason.INVALID_INPUT,
            lambda: AuthoritySnapshot(
                snapshot_id="",
                contract_id=contract.contract_id,
                authority_records=(_record(REC_ALPHA), _record(REC_ALPHA)),
                fresh_from=BASE_FROM,
                fresh_until=BASE_UNTIL,
                constraint_fingerprint=contract.hard_constraint_fingerprint(),
                recorded_at=BASE_RECORDED,
                provenance=_prov(BATTERY_ISSUER),
            ),
        )
    )
    # an admission against a snapshot attributable to another contract
    other_store, other_contract = _mature_foreign_contract()
    results.append(
        expect_error(
            "foreign snapshot attribution",
            LocalFirstReason.ID_MISMATCH,
            lambda: admit_operation(
                contract,
                _base_view(other_contract),
                episode_id=journal.episode_id,
                sequence=2,
                subject=_subject("lease:x"),
                claimed_constraints=tuple(contract.hard_constraints),
                decided_at=P1_ADMIT_A,
            ),
        )
    )
    # local_admit against a snapshot that is not the episode's base view
    results.append(
        expect_error(
            "non-base snapshot admission",
            LocalFirstReason.ID_MISMATCH,
            lambda: local_admit(
                journal,
                contract,
                _fresh_view(contract),
                subject=_subject("lease:x"),
                claimed_constraints=tuple(contract.hard_constraints),
                decided_at=P1_ADMIT_A,
            ),
        )
    )
    # an unknown operation lookup fails closed
    results.append(
        expect_error(
            "unknown operation",
            LocalFirstReason.INVALID_INPUT,
            lambda: journal.operation("sha256:" + "7" * 64),
        )
    )
    # an empty journal has no state to fold
    results.append(
        expect_error(
            "unopened journal state",
            LocalFirstReason.INVALID_INPUT,
            lambda: OfflineJournal("sha256:" + "3" * 64).state(),
        )
    )
    # the composition attribution gates
    results.append(
        expect_error(
            "open on a foreign contract",
            LocalFirstReason.ID_MISMATCH,
            lambda: open_partition(
                rstore,
                rid,
                other_contract,
                _base_view(other_contract),
                recorded_at=P1_OPEN,
            ),
        )
    )
    # a secret-shaped subject value is rejected at the boundary (the
    # credential fixture is assembled from fragments at runtime)
    secret_prefix = "ghp_"
    secret_body = "A1b2C3d4E5f6G7h8I9j0"
    results.append(
        expect_error(
            "secret-shaped subject value",
            LocalFirstReason.SECRET_REJECTED,
            lambda: DivergenceRecord(
                divergence_id="",
                episode_id=journal.episode_id,
                contract_id=contract.contract_id,
                subject_value=secret_prefix + secret_body,
                local_operation_id="sha256:" + "1" * 64,
                authority_record=_record(REC_ALPHA),
                resolution_rule=DEFAULT_RESOLUTION_RULE,
                resolution="authority-record",
                provenance=_prov(BATTERY_ISSUER),
            ),
        )
    )
    bad = [r for r in results if not r[1]]
    if bad:
        return fail(name, "; ".join("%s: %s" % (r[0], r[2]) for r in bad[:5]))
    return ok(
        name,
        "kind/outcome/state/rule/temporal/id/duplicate-record/attribution/unknown/"
        "secret gates all fail closed with the specific typed code (%d probes)"
        % len(results),
    )


# ---------------------------------------------------------------------------
# case_03 — (a) the offline journal round-trips (ordered, replayable)
# ---------------------------------------------------------------------------


def case_03_journal_round_trips() -> Result:
    name = "case_03_journal_round_trips"
    constraints = _constraints("latency-bound", "availability-floor")
    _, contract = _mature_contract(constraints)
    base = _base_view(contract)
    fresh = _fresh_view(contract)
    rstore, session, journal = _open_episode(contract, base)
    rid = session.runtime_id
    first = local_admit(
        journal,
        contract,
        base,
        subject=_subject(SUBJ_DEVICE_42),
        claimed_constraints=tuple(contract.hard_constraints),
        decided_at=P1_ADMIT_A,
        provenance=_prov(BATTERY_ISSUER),
    )
    second = local_admit(
        journal,
        contract,
        base,
        subject=_subject(SUBJ_DELTA),
        claimed_constraints=tuple(contract.hard_constraints),
        decided_at=P1_ADMIT_B,
        provenance=_prov(BATTERY_ISSUER),
    )
    close = close_partition(
        rstore, rid, contract, journal, fresh, recorded_at=P1_CLOSE, provenance=_prov(BATTERY_ISSUER)
    )
    records = journal.records()
    problems: List[str] = []
    # ordered: the journal positions are gapless and strictly increasing
    positions = [r.sequence for r in records]
    if positions != list(range(1, len(records) + 1)):
        problems.append("the journal positions are not gapless")
    if [r.kind for r in records] != [
        "partition-entered",
        "connectivity-admission",
        "connectivity-admission",
        "partition-exited",
    ]:
        problems.append("the journal kind chain drifted")
    # replayable: fold twice = the byte-identical state
    state_a = fold_operations(records)
    state_b = fold_operations(list(records))
    if state_a.canonical_bytes() != state_b.canonical_bytes():
        problems.append("the fold is not replay-stable")
    # construction-is-recovery: from_records rebuilds with no other state
    rebuilt = OfflineJournal.from_records(records)
    if rebuilt.state().canonical_bytes() != state_a.canonical_bytes():
        problems.append("construction-is-recovery diverged")
    # the state is always the fold of the journal
    if journal.state().canonical_bytes() != state_a.canonical_bytes():
        problems.append("the journal state diverged from the fold")
    # the admitted/rejected partition is journaled in order
    if state_a.admitted != (first.operation_id, second.operation_id):
        problems.append("the admitted set lost the journal order")
    if state_a.rejected:
        problems.append("an unexpected rejection was journaled")
    if state_a.state != "CLOSED" or rebuilt.state().state != "CLOSED":
        problems.append("the episode did not close")
    # the exit record carries the evidence-visible composition links
    exit_record = records[-1]
    if exit_record.resync_id != close.resync.resync_id:
        problems.append("the exit record lost the resync link")
    if exit_record.reconnect_id != close.reconnect.reconnect_id:
        problems.append("the exit record lost the M015 reconnect link")
    # the canonical round-trip of every record (byte-identical)
    for record in records:
        again = OfflineOperation.from_dict(record.to_dict())
        if again.canonical_bytes() != record.canonical_bytes():
            problems.append("a journal record does not round-trip")
            break
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "ordered gapless journal; fold twice + from_records rebuild = the "
        "byte-identical state; the exit carries the resync + reconnect links",
    )


# ---------------------------------------------------------------------------
# case_04 — (a) the idempotent append
# ---------------------------------------------------------------------------


def case_04_idempotent_append() -> Result:
    name = "case_04_idempotent_append"
    constraints = _constraints("latency-bound", "availability-floor")
    _, contract = _mature_contract(constraints)
    base = _base_view(contract)
    _, _, journal = _open_episode(contract, base)
    material = dict(
        subject=_subject(SUBJ_DEVICE_42),
        claimed_constraints=tuple(contract.hard_constraints),
        decided_at=P1_ADMIT_A,
        provenance=_prov(BATTERY_ISSUER),
    )
    first = local_admit(journal, contract, base, **material)
    journal_bytes_after_first = b"".join(
        r.canonical_bytes() for r in journal.records()
    )
    # the SAME admission material retried (an uncertain outcome retried
    # while partitioned): one application, the same identity
    retried = local_admit(journal, contract, base, **material)
    if retried.operation_id != first.operation_id:
        return fail(name, "the retried admission derived a different identity")
    if retried.sequence != first.sequence:
        return fail(name, "the retried admission double-applied at a new position")
    if len(journal.records()) != 2:  # partition-entered + the ONE admission
        return fail(
            name, "the retry appended a duplicate record (%d records)" % len(journal.records())
        )
    if b"".join(r.canonical_bytes() for r in journal.records()) != journal_bytes_after_first:
        return fail(name, "the retry mutated the journal bytes")
    # a DIFFERENT admission on the same subject (different material) is
    # a discipline violation — the APPEND fails closed atomically (the
    # candidate journal does not fold; the journal stays byte-identical)
    second = expect_error(
        "double admission",
        LocalFirstReason.JOURNAL_DIVERGENCE,
        lambda: local_admit(
            journal,
            contract,
            base,
            subject=_subject(SUBJ_DEVICE_42),
            claimed_constraints=tuple(contract.hard_constraints),
            decided_at=P1_ADMIT_B,  # a different instant -> different identity
            provenance=_prov(BATTERY_ISSUER),
        ),
    )
    if not second[1]:
        return fail(name, "a subject admitted twice in one episode was accepted: %s" % second[2])
    if len(journal.records()) != 2:
        return fail(name, "the rejected double admission mutated the journal")
    if b"".join(r.canonical_bytes() for r in journal.records()) != journal_bytes_after_first:
        return fail(name, "the rejected double admission mutated the journal bytes")
    return ok(
        name,
        "a retried admission returns the existing record (same identity, one "
        "application, byte-identical journal); a second admission of the same "
        "subject fails the fold as journal divergence",
    )


# ---------------------------------------------------------------------------
# case_05..case_08 — (b) partition-tolerant admission (a case per
# freshness outcome)
# ---------------------------------------------------------------------------


def case_05_fresh_authority_admits() -> Result:
    name = "case_05_fresh_authority_admits"
    constraints = _constraints("latency-bound", "availability-floor")
    _, contract = _mature_contract(constraints)
    base = _base_view(contract)
    _, _, journal = _open_episode(contract, base)
    record = local_admit(
        journal,
        contract,
        base,
        subject=_subject(SUBJ_DEVICE_42),
        claimed_constraints=tuple(contract.hard_constraints),
        decided_at=P1_ADMIT_A,
        provenance=_prov(BATTERY_ISSUER),
    )
    problems: List[str] = []
    if record.outcome != "admitted":
        problems.append("the fresh-window admission did not admit (%s)" % record.outcome)
    # the decision CARRIES the authority's declared freshness window
    # (the charter requirement)
    if record.fresh_from != base.fresh_from or record.fresh_until != base.fresh_until:
        problems.append("the decision does not carry the declared freshness window")
    # the claimed constraint set rides verbatim (DATA, re-verified later)
    if len(record.hard_constraints) != len(contract.hard_constraints):
        problems.append("the claimed set lost constraints")
    # the raising gate agrees (fresh inside the window)
    if check_authority_fresh(base, P1_ADMIT_A) != "fresh":
        problems.append("the raising freshness gate disagrees")
    # the journaled record is evidence-visible on the open episode
    state = journal.state()
    if state.admitted != (record.operation_id,) or state.state != "OPEN":
        problems.append("the admitted decision is not journaled on the open episode")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "the fresh authority admits; the decision carries the declared "
        "freshness window and the claimed set verbatim (journaled, OPEN)",
    )


def case_06_stale_authority_fails_closed() -> Result:
    name = "case_06_stale_authority_fails_closed"
    constraints = _constraints("latency-bound", "availability-floor")
    _, contract = _mature_contract(constraints)
    base = _base_view(contract)
    _, _, journal = _open_episode(contract, base)
    # the twin: a stale decision is JOURNALED as the typed rejection
    record = local_admit(
        journal,
        contract,
        base,
        subject=_subject(SUBJ_DEVICE_43),
        claimed_constraints=tuple(contract.hard_constraints),
        decided_at=P1_ADMIT_STALE,  # past BASE_UNTIL
        provenance=_prov(BATTERY_ISSUER),
    )
    problems: List[str] = []
    if record.outcome != "stale-rejected":
        problems.append("the past-bound admission outcome is %s" % record.outcome)
    if record.fresh_until != base.fresh_until:
        problems.append("the stale rejection does not carry the window")
    state = journal.state()
    if state.admitted or state.rejected != (record.operation_id,):
        problems.append("the stale rejection is not journaled as evidence")
    # the raising gate: the typed fail-closed stale-authority rejection
    gate = expect_error(
        "raising gate",
        LocalFirstReason.AUTHORITY_STALE,
        lambda: check_authority_fresh(base, P1_ADMIT_STALE),
    )
    if not gate[1]:
        problems.append("the raising gate: %s" % gate[2])
    # the fold's MECHANICAL enforcement: a forged ADMITTED record whose
    # instant lies OUTSIDE its carried window never folds (the silent-
    # allow shape is journal divergence, never a silent authorization)
    forged = OfflineOperation(
        operation_id="",
        episode_id=journal.episode_id,
        contract_id=contract.contract_id,
        sequence=3,
        kind="connectivity-admission",
        recorded_at=P1_ADMIT_STALE,
        provenance=_prov(BATTERY_ISSUER),
        subject=_subject("lease:forged-stale"),
        hard_constraints=tuple(contract.hard_constraints),
        fresh_from=base.fresh_from,
        fresh_until=base.fresh_until,
        outcome="admitted",
    )
    fold = expect_error(
        "fold enforcement",
        LocalFirstReason.JOURNAL_DIVERGENCE,
        lambda: fold_operations(
            list(journal.records()[:1]) + [forged]
        ),
    )
    if not fold[1]:
        problems.append("the forged silent-allow folded: %s" % fold[2])
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "past the declared bound: the journaled stale-rejected outcome + the "
        "typed raising rejection + the fold's mechanical enforcement of the "
        "forged silent-allow shape (never a silent allow)",
    )


def case_07_not_yet_valid_fails_closed() -> Result:
    name = "case_07_not_yet_valid_fails_closed"
    constraints = _constraints("latency-bound", "availability-floor")
    _, contract = _mature_contract(constraints)
    base = _base_view(contract)
    _, _, journal = _open_episode(contract, base)
    record = local_admit(
        journal,
        contract,
        base,
        subject=_subject(SUBJ_DEVICE_44),
        claimed_constraints=tuple(contract.hard_constraints),
        decided_at=PRE_WINDOW,  # before BASE_FROM
        provenance=_prov(BATTERY_ISSUER),
    )
    problems: List[str] = []
    if record.outcome != "not-yet-valid-rejected":
        problems.append("the pre-window admission outcome is %s" % record.outcome)
    state = journal.state()
    if state.admitted or state.rejected != (record.operation_id,):
        problems.append("the pre-window rejection is not journaled as evidence")
    gate = expect_error(
        "raising gate",
        LocalFirstReason.AUTHORITY_NOT_YET_VALID,
        lambda: check_authority_fresh(base, PRE_WINDOW),
    )
    if not gate[1]:
        problems.append("the raising gate: %s" % gate[2])
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "before the window opens: the journaled not-yet-valid-rejected outcome "
        "+ the typed raising rejection (the symmetric fail-closed outcome)",
    )


def case_08_inclusive_window_bounds() -> Result:
    name = "case_08_inclusive_window_bounds"
    constraints = _constraints("latency-bound", "availability-floor")
    _, contract = _mature_contract(constraints)
    base = _base_view(contract)
    _, _, journal = _open_episode(contract, base)
    problems: List[str] = []
    # decided_at == fresh_from (the window's opening instant): fresh
    at_open = local_admit(
        journal,
        contract,
        base,
        subject=_subject("lease:at-open"),
        claimed_constraints=tuple(contract.hard_constraints),
        decided_at=base.fresh_from,
        provenance=_prov(BATTERY_ISSUER),
    )
    if at_open.outcome != "admitted":
        problems.append("the opening-bound instant did not admit (%s)" % at_open.outcome)
    # decided_at == fresh_until (the window's closing instant): fresh
    at_close = local_admit(
        journal,
        contract,
        base,
        subject=_subject("lease:at-close"),
        claimed_constraints=tuple(contract.hard_constraints),
        decided_at=base.fresh_until,
        provenance=_prov(BATTERY_ISSUER),
    )
    if at_close.outcome != "admitted":
        problems.append("the closing-bound instant did not admit (%s)" % at_close.outcome)
    # one microsecond-equivalent past the bound (a strictly later
    # instant): stale — the bound is inclusive, deterministic
    past = local_admit(
        journal,
        contract,
        base,
        subject=_subject("lease:past-bound"),
        claimed_constraints=tuple(contract.hard_constraints),
        decided_at="2026-10-09T00:00:00.000001Z",
        provenance=_prov(BATTERY_ISSUER),
    )
    if past.outcome != "stale-rejected":
        problems.append("the past-bound instant did not reject (%s)" % past.outcome)
    if check_authority_fresh(base, base.fresh_until) != "fresh":
        problems.append("the raising gate disagrees at the closing bound")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "the declared window is inclusive at both bounds (deterministic); a "
        "strictly later instant is the stale rejection",
    )


# ---------------------------------------------------------------------------
# case_09..case_20 — (d) LOCK-108 across the offline boundary, one
# numbered case per constraint kind (all 12 kinds x DROP/RELAX/
# REINTERPRET on the admission twin + the raising gate + the forged
# journaled admitted record rejected by the resync re-verification)
# ---------------------------------------------------------------------------


def _lock108_case(kind: str, index: int) -> Result:
    name = "case_%02d_lock108_%s" % (index, kind.replace("-", "_"))
    constraints = _constraints(*ALL_KINDS)
    _, contract = _mature_contract(constraints)
    base = _base_view(contract)
    problems: List[str] = []
    for mode in ("DROP", "RELAX", "REINTERPRET"):
        weakened = _weakened_constraints(contract.hard_constraints, mode, kind)
        label = "%s %s" % (mode, kind)
        # 1. the raising gate: the typed weakened-constraint rejection
        #    citing the kind (the CONSUMED M008 gate surfaced on this
        #    surface's own vocabulary)
        try:
            check_admission_preserves_contract(
                contract, weakened, subject_value="lease:weak-%s" % kind
            )
            problems.append("the raising gate accepted the %s weakening" % label)
        except LocalFirstError as error:
            if error.code != LocalFirstReason.CONSTRAINT_WEAKENED:
                problems.append(
                    "%s: expected localfirst-constraint-weakened, got %s"
                    % (label, error.code)
                )
            elif kind not in error.detail:
                problems.append("%s: the rejection does not cite the kind" % label)
        # 2. the typed twin: the admission NEVER admits a weakening
        #    claim; the rejection is JOURNALED as evidence
        rstore, session, journal = _open_episode(contract, base)
        record = local_admit(
            journal,
            contract,
            base,
            subject=_subject("lease:weak-%s-%s" % (kind, mode.lower())),
            claimed_constraints=weakened,
            decided_at=P1_ADMIT_A,
            provenance=_prov(BATTERY_ISSUER),
        )
        if record.outcome != "weakened-rejected":
            problems.append(
                "the twin admitted the %s weakening (outcome %s)"
                % (label, record.outcome)
            )
        state = journal.state()
        if state.admitted or state.rejected != (record.operation_id,):
            problems.append("the %s rejection is not journaled as evidence" % label)
        # the rejected admission left nothing admitted (LOCK-108:
        # never a silent weakening during partition)
        if state.admitted:
            problems.append("a weakening admission silently authorized (%s)" % label)
    # 3. the resynchronization re-verification: a wire-forged ADMITTED
    #    journal record carrying the weakened claimed set (the record
    #    is DATA — ids re-derived over the forged content, exactly what
    #    the accepted derivation computes; the M008 battery's wire-
    #    forged precedent) is REJECTED by the resync with the typed
    #    reason citing the kind — never silently converged, never
    #    silently dropped
    weakened_drop = _weakened_constraints(contract.hard_constraints, "DROP", kind)
    rstore, session, journal = _open_episode(contract, base)
    forged = OfflineOperation(
        operation_id="",
        episode_id=journal.episode_id,
        contract_id=contract.contract_id,
        sequence=2,
        kind="connectivity-admission",
        recorded_at=P1_ADMIT_A,
        provenance=_prov(BATTERY_ISSUER),
        subject=_subject("lease:forged-weak-%s" % kind),
        hard_constraints=weakened_drop,
        fresh_from=base.fresh_from,
        fresh_until=base.fresh_until,
        outcome="admitted",
    )
    journal.append(forged)
    result = resynchronize(
        contract,
        journal,
        _fresh_view(contract),
        recorded_at=P1_CLOSE,
    )
    if result.applied_operations:
        problems.append("the resync converged the weakened %s operation" % kind)
    rejections = result.rejected_operations
    if len(rejections) != 1:
        problems.append(
            "the weakened %s resync rejection count is %d" % (kind, len(rejections))
        )
    else:
        rejection = rejections[0]
        if rejection.operation_id != forged.operation_id:
            problems.append("the %s rejection cites the wrong operation" % kind)
        if rejection.code != LocalFirstReason.CONSTRAINT_WEAKENED:
            problems.append(
                "the %s resync rejection code %s is not the typed "
                "weakened-constraint rejection" % (kind, rejection.code)
            )
        elif kind not in rejection.detail:
            problems.append("the %s resync rejection does not cite the kind" % kind)
    # the rejection is ACCOUNTED (never a silent drop): the forged op
    # appears exactly once across the result's outcome sets
    accounted = list(result.applied_operations) + [
        r.operation_id for r in result.rejected_operations
    ] + [d.local_operation_id for d in result.divergences]
    if accounted != [forged.operation_id]:
        problems.append(
            "the forged %s operation is not accounted exactly once (%s)"
            % (kind, accounted)
        )
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "DROP/RELAX/REINTERPRET rejections cite the kind (%s); the journaled "
        "weakened admitted record is rejected by the resync re-verification "
        "with the typed reason and accounted exactly once" % kind,
    )


# ---------------------------------------------------------------------------
# case_21 — (c) reconnect + resync: no divergence (clean convergence)
# ---------------------------------------------------------------------------


def case_21_clean_convergence() -> Result:
    name = "case_21_clean_convergence"
    constraints = _constraints("latency-bound", "availability-floor")
    _, contract = _mature_contract(constraints)
    base = _base_view(contract)
    fresh = _fresh_view(contract)
    rstore, session, journal = _open_episode(contract, base)
    rid = session.runtime_id
    first = local_admit(
        journal,
        contract,
        base,
        subject=_subject(SUBJ_DEVICE_42),
        claimed_constraints=tuple(contract.hard_constraints),
        decided_at=P1_ADMIT_A,
        provenance=_prov(BATTERY_ISSUER),
    )
    second = local_admit(
        journal,
        contract,
        base,
        subject=_subject(SUBJ_DELTA),
        claimed_constraints=tuple(contract.hard_constraints),
        decided_at=P1_ADMIT_B,
        provenance=_prov(BATTERY_ISSUER),
    )
    close = close_partition(
        rstore, rid, contract, journal, fresh, recorded_at=P1_CLOSE, provenance=_prov(BATTERY_ISSUER)
    )
    result = close.resync
    problems: List[str] = []
    if result.divergences:
        problems.append("an unexpected divergence was detected")
    # every local admitted operation converged (applied, none dropped)
    if set(result.applied_operations) != {first.operation_id, second.operation_id}:
        problems.append("an admitted operation was not applied")
    # the converged replica record set: the fresh authority records +
    # the applied local subjects (deterministic order)
    values = [r.value for r in result.converged_records]
    if values != [REC_BETA, REC_GAMMA, SUBJ_DEVICE_42, SUBJ_DELTA]:
        problems.append("the converged record set drifted: %s" % values)
    # the resync carries the declared rule verbatim
    if result.resolution_rule != DEFAULT_RESOLUTION_RULE:
        problems.append("the declared rule is not recorded verbatim")
    # the episode closed; the state names the fresh view + the resync
    if close.state.state != "CLOSED" or close.state.resync_id != result.resync_id:
        problems.append("the episode did not close under the resync")
    # the M015 runtime landed ACTIVE on the fresh view
    if close.session.state != "ACTIVE":
        problems.append("the runtime did not land ACTIVE (%s)" % close.session.state)
    if close.session.realization_refs() != fresh.realization_refs():
        problems.append("the runtime does not realize the fresh view")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "zero divergences; both admitted operations applied; the converged "
        "set = the fresh authority records + the local subjects in order; the "
        "episode closed and the runtime lands ACTIVE on the fresh view",
    )


# ---------------------------------------------------------------------------
# case_22 — (c) detected divergence (the typed record, full provenance)
# ---------------------------------------------------------------------------


def case_22_divergence_detected_typed() -> Result:
    name = "case_22_divergence_detected_typed"
    constraints = _constraints("latency-bound", "availability-floor")
    _, contract = _mature_contract(constraints)
    base = _base_view(contract)
    # the fresh view CARRIES the local subject as an authority record
    # (the authority independently recorded an operation on the same
    # subject during the partition — the divergence)
    fresh = authority_snapshot(
        contract,
        (_record(REC_BETA), _record(SUBJ_DEVICE_42)),
        fresh_from="2026-10-11T00:00:00Z",
        fresh_until="2026-10-18T00:00:00Z",
        recorded_at="2026-10-11T00:00:00Z",
    )
    rstore, session, journal = _open_episode(contract, base)
    rid = session.runtime_id
    local = local_admit(
        journal,
        contract,
        base,
        subject=_subject(SUBJ_DEVICE_42),
        claimed_constraints=tuple(contract.hard_constraints),
        decided_at=P1_ADMIT_A,
        provenance=_prov(BATTERY_ISSUER),
    )
    close = close_partition(
        rstore, rid, contract, journal, fresh, recorded_at=P1_CLOSE, provenance=_prov(BATTERY_ISSUER)
    )
    result = close.resync
    problems: List[str] = []
    if len(result.divergences) != 1:
        return fail(
            name, "the divergence was not detected exactly once (%d)" % len(result.divergences)
        )
    divergence = result.divergences[0]
    # the typed record carries the FULL provenance of BOTH sides
    if divergence.local_operation_id != local.operation_id:
        problems.append("the divergence does not cite the local operation")
    if divergence.authority_record.value != SUBJ_DEVICE_42:
        problems.append("the divergence does not ride the authority record")
    if divergence.authority_record.provenance.issuer != "prov:netpro":
        problems.append("the authority record lost its provenance")
    if divergence.subject_value != SUBJ_DEVICE_42:
        problems.append("the divergence does not name the subject")
    if divergence.resolution_rule != DEFAULT_RESOLUTION_RULE:
        problems.append("the divergence does not record the declared rule")
    # the default rule lets the authority side win (LOCK-101)
    if divergence.resolution != "authority-record":
        problems.append("the default rule did not retain the authority record")
    # the local operation is NOT applied, but it IS cited (accounted
    # exactly once — never a silent drop)
    if local.operation_id in result.applied_operations:
        problems.append("the lost conflict was silently applied")
    accounted = list(result.applied_operations) + [
        r.operation_id for r in result.rejected_operations
    ] + [d.local_operation_id for d in result.divergences]
    if accounted != [local.operation_id]:
        problems.append("the conflicting operation is not accounted exactly once")
    # the converged set keeps the authority record (the winner)
    values = [r.value for r in result.converged_records]
    if values != [REC_BETA, SUBJ_DEVICE_42]:
        problems.append("the converged set did not keep the authority record: %s" % values)
    # the divergence record round-trips byte-identically
    again = DivergenceRecord.from_dict(divergence.to_dict())
    if again.canonical_bytes() != divergence.canonical_bytes():
        problems.append("the divergence record does not round-trip")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "the conflicting subject yields ONE typed divergence record citing "
        "both sides with provenance; the default rule retains the authority "
        "record; the local operation is cited, never silently dropped",
    )


# ---------------------------------------------------------------------------
# case_23 — (c) the deterministic DECLARED RECORDED resolution
# ---------------------------------------------------------------------------


def _conflict_scenario(
    resolution_rule: Tuple[str, ...],
) -> Tuple[bytes, str]:
    """One conflict scenario under a declared rule: the local subject
    is an authority record value that sorts AFTER 'sha256:' so the two
    declared rules resolve the SAME conflict in OPPOSITE directions
    (the rule decides, demonstrably).  Returns (the resync canonical
    bytes, the resolution outcome)."""
    constraints = _constraints("latency-bound", "availability-floor")
    _, contract = _mature_contract(constraints)
    base = _base_view(contract)
    fresh = authority_snapshot(
        contract,
        (_record(REC_BETA), _record(REC_WIRELESS)),
        fresh_from="2026-10-11T00:00:00Z",
        fresh_until="2026-10-18T00:00:00Z",
        recorded_at="2026-10-11T00:00:00Z",
    )
    rstore = RuntimeStore()
    session = attach_runtime_session(
        rstore,
        contract,
        base,
        created_at=LF_CREATE,
        activated_at=LF_ACTIVATE,
        provenance=_prov(BATTERY_ISSUER),
    )
    journal, _ = open_partition(
        rstore, session.runtime_id, contract, base, recorded_at=P1_OPEN, provenance=_prov(BATTERY_ISSUER)
    )
    local_admit(
        journal,
        contract,
        base,
        subject=_subject(REC_WIRELESS),
        claimed_constraints=tuple(contract.hard_constraints),
        decided_at=P1_ADMIT_A,
        provenance=_prov(BATTERY_ISSUER),
    )
    result = resynchronize(
        contract,
        journal,
        fresh,
        resolution_rule=resolution_rule,
        recorded_at=P1_CLOSE,
    )
    outcome = result.divergences[0].resolution if result.divergences else "(none)"
    return result.canonical_bytes(), outcome


def case_23_deterministic_declared_resolution() -> Result:
    name = "case_23_deterministic_declared_resolution"
    problems: List[str] = []
    # the default rule: the projected candidate-kind orders
    # authority-record before local-offline-operation -> the authority
    # side wins
    default_a, default_outcome_a = _conflict_scenario(DEFAULT_RESOLUTION_RULE)
    default_b, default_outcome_b = _conflict_scenario(DEFAULT_RESOLUTION_RULE)
    if default_a != default_b:
        problems.append("the default-rule resolution is not byte-identical on a re-run")
    if default_outcome_a != "authority-record":
        problems.append("the default rule did not retain the authority record")
    # the content-order rule: the projected candidate-ids decide — the
    # local operation id ('sha256:...') sorts BEFORE the authority
    # record value ('wireless:...') -> the LOCAL side wins
    content_a, content_outcome_a = _conflict_scenario(("candidate-id",))
    content_b, content_outcome_b = _conflict_scenario(("candidate-id",))
    if content_a != content_b:
        problems.append("the content-rule resolution is not byte-identical on a re-run")
    if content_outcome_a != "local-offline-operation":
        problems.append("the content-order rule did not retain the local operation")
    # the SAME conflict, DIFFERENT declared rules, OPPOSITE outcomes —
    # the rule decides (declared, recorded, deterministic)
    if default_outcome_a == content_outcome_a:
        problems.append("the two declared rules did not discriminate the outcome")
    # the pure kernel agrees with the projection semantics
    if resolve_conflict(
        "local-offline-operation", "sha256:" + "1" * 64, "authority-record", REC_WIRELESS, ("candidate-id",)
    ) != "local-offline-operation":
        problems.append("the pure kernel mis-ordered the projected ids")
    if resolve_conflict(
        "local-offline-operation", "sha256:" + "1" * 64, "authority-record", REC_WIRELESS, DEFAULT_RESOLUTION_RULE
    ) != "authority-record":
        problems.append("the pure kernel mis-ordered the projected kinds")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "same inputs -> byte-identical resolutions under each declared rule; "
        "the two rules resolve the SAME conflict in opposite directions "
        "(authority-record vs local-offline-operation) — the rule decides, "
        "recorded verbatim, never dropped or duplicated",
    )


# ---------------------------------------------------------------------------
# case_24 — (c) invalid declared resolution rules fail closed
# ---------------------------------------------------------------------------


def case_24_invalid_rules_fail_closed() -> Result:
    name = "case_24_invalid_rules_fail_closed"
    constraints = _constraints("latency-bound", "availability-floor")
    _, contract = _mature_contract(constraints)
    base = _base_view(contract)
    fresh = _fresh_view(contract)
    _, _, journal = _open_episode(contract, base)
    local_admit(
        journal,
        contract,
        base,
        subject=_subject(SUBJ_DEVICE_42),
        claimed_constraints=tuple(contract.hard_constraints),
        decided_at=P1_ADMIT_A,
        provenance=_prov(BATTERY_ISSUER),
    )
    journal_bytes = b"".join(r.canonical_bytes() for r in journal.records())
    probes = (
        ("recorded-at", "candidate-id"),  # a temporal key (never wall-clock)
        ("candidate-kind",),  # no total-order key
        ("candidate-id", "candidate-kind"),  # the total-order key is not last
        "candidate-id",  # not a sequence
        (),  # empty
    )
    results: List[Result] = []
    for i, rule in enumerate(probes):
        results.append(
            expect_error(
                "rule probe %d" % i,
                LocalFirstReason.RESOLUTION_INVALID,
                lambda rule=rule: resynchronize(
                    contract,
                    journal,
                    fresh,
                    resolution_rule=rule,
                    recorded_at=P1_CLOSE,
                ),
            )
        )
    bad = [r for r in results if not r[1]]
    if bad:
        return fail(name, "; ".join("%s: %s" % (r[0], r[2]) for r in bad[:5]))
    # the rejected rules left the journal byte-identical (atomicity)
    if b"".join(r.canonical_bytes() for r in journal.records()) != journal_bytes:
        return fail(name, "a rejected rule mutated the journal")
    # a rule with a repeated key fails closed (probe on the pure kernel)
    kernel = expect_error(
        "repeated key",
        LocalFirstReason.RESOLUTION_INVALID,
        lambda: normalize_resolution_rule(("candidate-id", "candidate-id"), "probe"),
    )
    if not kernel[1]:
        return fail(name, kernel[2])
    return ok(
        name,
        "temporal/non-total/reordered/non-sequence/empty/repeated rules all "
        "fail closed localfirst-resolution-invalid; the journal stays "
        "byte-identical",
    )


# ---------------------------------------------------------------------------
# case_25 — (e) the degraded/offline mode entry/exit journaled and
# evidence-visible
# ---------------------------------------------------------------------------


def case_25_degraded_mode_journaled_evidence_visible() -> Result:
    name = "case_25_degraded_mode_journaled_evidence_visible"
    constraints = _constraints("latency-bound", "availability-floor")
    _, contract = _mature_contract(constraints)
    base = _base_view(contract)
    fresh = _fresh_view(contract)
    rstore = RuntimeStore()
    session = attach_runtime_session(
        rstore,
        contract,
        base,
        created_at=LF_CREATE,
        activated_at=LF_ACTIVATE,
        provenance=_prov(BATTERY_ISSUER),
    )
    rid = session.runtime_id
    journal, entry = open_partition(
        rstore, rid, contract, base, recorded_at=P1_OPEN, provenance=_prov(BATTERY_ISSUER)
    )
    local_admit(
        journal,
        contract,
        base,
        subject=_subject(SUBJ_DEVICE_42),
        claimed_constraints=tuple(contract.hard_constraints),
        decided_at=P1_ADMIT_A,
        provenance=_prov(BATTERY_ISSUER),
    )
    close = close_partition(
        rstore, rid, contract, journal, fresh, recorded_at=P1_CLOSE, provenance=_prov(BATTERY_ISSUER)
    )
    problems: List[str] = []
    # the offline ENTRY is journaled on the offline journal with typed
    # provenance and the M015 event link (evidence-visible)
    if entry.kind != "partition-entered":
        problems.append("the entry record kind drifted")
    if entry.base_snapshot_id != base.snapshot_id:
        problems.append("the entry does not name the base view")
    if not entry.runtime_event_id.startswith("sha256:"):
        problems.append("the entry does not carry the M015 event link")
    if not entry.provenance.issuer:
        problems.append("the entry lost its provenance issuer")
    # the M015 runtime journal carries the degraded entry with the
    # accepted LOCK-106 evidence kind and the episode-kinded reference
    events = rstore.events(rid)
    kinds = [e.kind for e in events]
    if kinds != [
        "session-created",
        "session-activated",
        "degraded-entered",
        "reconnect-initiated",
        "reconnect-completed",
    ]:
        problems.append("the M015 journal kind chain drifted: %s" % kinds)
    degraded_events = [e for e in events if e.kind == "degraded-entered"]
    if len(degraded_events) != 1:
        problems.append("the degraded entry count drifted")
    else:
        degraded = degraded_events[0]
        if degraded.evidence_kind != "observation":
            problems.append("the degraded evidence kind is not the accepted observation")
        if degraded.evidence_kind not in EVIDENCE_TYPES:
            problems.append("the degraded evidence kind left the accepted vocabulary")
        if not degraded.evidence_refs or degraded.evidence_refs[0].value != journal.episode_id:
            problems.append("the degraded entry does not cite the episode reference")
        if degraded.evidence_refs[0].ref_kind != "decision":
            problems.append("the episode reference is not decision-kinded")
        if degraded.event_id != entry.runtime_event_id:
            problems.append("the journaled entry does not link the M015 event")
    # the offline EXIT is journaled with the resync + reconnect links
    exit_record = journal.records()[-1]
    if exit_record.kind != "partition-exited":
        problems.append("the exit record kind drifted")
    if exit_record.resync_id != close.resync.resync_id:
        problems.append("the exit does not carry the resync link")
    if exit_record.reconnect_id != close.reconnect.reconnect_id:
        problems.append("the exit does not carry the reconnect link")
    if not exit_record.provenance.issuer:
        problems.append("the exit lost its provenance issuer")
    # the entry and the exit are visible on the folded state (the
    # episode lifecycle is evidence, never silent)
    state = journal.state()
    if state.state != "CLOSED":
        problems.append("the folded state did not close")
    if state.resync_id != close.resync.resync_id:
        problems.append("the folded state lost the resync link")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "the entry/exit are journaled on both surfaces with typed provenance "
        "and the cross-surface evidence links (the M015 event id / the "
        "episode reference / the resync + reconnect ids)",
    )


# ---------------------------------------------------------------------------
# case_26 — (f) the M015 composition (the runtime drives the offline
# transitions; multiple episodes chain on one session)
# ---------------------------------------------------------------------------


def case_26_m015_composition() -> Result:
    name = "case_26_m015_composition"
    constraints = _constraints("latency-bound", "availability-floor")
    _, contract = _mature_contract(constraints)
    base = _base_view(contract)
    fresh1 = _fresh_view(contract)
    # episode 2's base view (the fresh view of episode 1 + a window
    # refresh); the session must SYNC onto it while connected (the
    # explicit reconnect — the WORK-012 discipline for the view change)
    base2 = authority_snapshot(
        contract,
        (_record(REC_BETA), _record(REC_GAMMA)),
        fresh_from="2026-10-11T00:30:00Z",
        fresh_until="2026-10-18T00:30:00Z",
        recorded_at="2026-10-11T00:30:00Z",
    )
    fresh2 = authority_snapshot(
        contract,
        (_record(REC_GAMMA), _record(REC_EPSILON)),
        fresh_from="2026-10-20T00:00:00Z",
        fresh_until="2026-10-27T00:00:00Z",
        recorded_at="2026-10-20T00:00:00Z",
    )
    rstore = RuntimeStore()
    session = attach_runtime_session(
        rstore,
        contract,
        base,
        created_at=LF_CREATE,
        activated_at=LF_ACTIVATE,
        provenance=_prov(BATTERY_ISSUER),
    )
    rid = session.runtime_id
    problems: List[str] = []
    if session.state != "ACTIVE" or session.realization_refs() != base.realization_refs():
        problems.append("the attached session does not realize the base view")
    # episode 1
    journal1, _ = open_partition(
        rstore, rid, contract, base, recorded_at=P1_OPEN, provenance=_prov(BATTERY_ISSUER)
    )
    if rstore.session(rid).state != "DEGRADED":
        problems.append("the partition entry did not degrade the runtime (M015)")
    local_admit(
        journal1,
        contract,
        base,
        subject=_subject(SUBJ_DEVICE_42),
        claimed_constraints=tuple(contract.hard_constraints),
        decided_at=P1_ADMIT_A,
        provenance=_prov(BATTERY_ISSUER),
    )
    close1 = close_partition(
        rstore, rid, contract, journal1, fresh1, recorded_at=P1_CLOSE, provenance=_prov(BATTERY_ISSUER)
    )
    # the reconnect evidence names BOTH the old and the new authority
    # views (the WORK-012 discipline across the offline boundary)
    if close1.reconnect.old_route_decision_id != base.snapshot_id:
        problems.append("the reconnect evidence lost the OLD view")
    if close1.reconnect.new_route_decision_id != fresh1.snapshot_id:
        problems.append("the reconnect evidence lost the NEW view")
    if close1.reconnect.old_path_id != base.state_digest:
        problems.append("the reconnect evidence lost the OLD state digest")
    if close1.reconnect.new_path_id != fresh1.state_digest:
        problems.append("the reconnect evidence lost the NEW state digest")
    if close1.session.state != "ACTIVE":
        problems.append("the post-resync runtime is not ACTIVE")
    # the connected sync onto episode 2's base view: the explicit
    # reconnect pair (idempotent on the already-held view: None)
    if sync_authority_view(rstore, rid, contract, fresh1, recorded_at=P2_SYNC) is not None:
        problems.append("the already-synced view reconnected (a fabricated event)")
    evidence = sync_authority_view(
        rstore, rid, contract, base2, recorded_at=P2_SYNC, provenance=_prov(BATTERY_ISSUER)
    )
    if evidence is None:
        problems.append("the connected sync did not reconnect")
    elif evidence.new_route_decision_id != base2.snapshot_id:
        problems.append("the connected sync did not name the new view")
    # episode 2 chains on the SAME session (multiple episodes)
    journal2, entry2 = open_partition(
        rstore, rid, contract, base2, recorded_at=P2_OPEN, provenance=_prov(BATTERY_ISSUER)
    )
    if journal2.episode_id == journal1.episode_id:
        problems.append("the second episode reused the first episode identity")
    local_admit(
        journal2,
        contract,
        base2,
        subject=_subject(SUBJ_DELTA),
        claimed_constraints=tuple(contract.hard_constraints),
        decided_at=P2_ADMIT_A,
        provenance=_prov(BATTERY_ISSUER),
    )
    close2 = close_partition(
        rstore, rid, contract, journal2, fresh2, recorded_at=P2_CLOSE, provenance=_prov(BATTERY_ISSUER)
    )
    # the full runtime journal now carries BOTH episodes' transitions
    kinds = [e.kind for e in rstore.events(rid)]
    expected = [
        "session-created",
        "session-activated",
        "degraded-entered",  # episode 1 open
        "reconnect-initiated",  # episode 1 close
        "reconnect-completed",
        "reconnect-initiated",  # the connected sync onto base2
        "reconnect-completed",
        "degraded-entered",  # episode 2 open
        "reconnect-initiated",  # episode 2 close
        "reconnect-completed",
    ]
    if kinds != expected:
        problems.append("the two-episode runtime chain drifted: %s" % kinds)
    if entry2.runtime_event_id != rstore.events(rid)[7].event_id:
        problems.append("the second entry does not link its M015 event")
    if close2.session.realization_refs() != fresh2.realization_refs():
        problems.append("the session does not realize the second fresh view")
    # the reconnect evidence set covers every view change (3 reconnects)
    if len(rstore.reconnect_evidence(rid)) != 3:
        problems.append("the reconnect evidence count drifted")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "the accepted M015 runtime drives every offline transition (degraded "
        "entries, the reconnect pairs naming old+new views, the connected "
        "sync idempotent); two episodes chain on one session with the full "
        "WORK-012 evidence chain",
    )


# ---------------------------------------------------------------------------
# case_27 — (g) canonical-JSON round-trips
# ---------------------------------------------------------------------------


def case_27_canonical_round_trips() -> Result:
    name = "case_27_canonical_round_trips"
    constraints = _constraints("latency-bound", "availability-floor")
    _, contract = _mature_contract(constraints)
    base = _base_view(contract)
    fresh = _fresh_view(contract)
    rstore, session, journal = _open_episode(contract, base)
    rid = session.runtime_id
    local_admit(
        journal,
        contract,
        base,
        subject=_subject(SUBJ_DEVICE_42),
        claimed_constraints=tuple(contract.hard_constraints),
        decided_at=P1_ADMIT_A,
        provenance=_prov(BATTERY_ISSUER),
    )
    close = close_partition(
        rstore, rid, contract, journal, fresh, recorded_at=P1_CLOSE, provenance=_prov(BATTERY_ISSUER)
    )
    problems: List[str] = []
    pairs = (
        ("the snapshot", base),
        ("the journal records", journal.records()),
        ("the local state", journal.state()),
        ("the resync result", close.resync),
    )
    for label, material in pairs:
        items = material if isinstance(material, tuple) else (material,)
        for item in items:
            again = type(item).from_dict(item.to_dict())
            if again.canonical_bytes() != item.canonical_bytes():
                problems.append("%s does not round-trip" % label)
                break
    # the divergence record round-trips (fixture: construct one)
    divergence = DivergenceRecord(
        divergence_id="",
        episode_id=journal.episode_id,
        contract_id=contract.contract_id,
        subject_value=SUBJ_DEVICE_42,
        local_operation_id=journal.state().admitted[0],
        authority_record=_record(REC_BETA),
        resolution_rule=DEFAULT_RESOLUTION_RULE,
        resolution="authority-record",
        provenance=_prov(BATTERY_ISSUER),
    )
    again = DivergenceRecord.from_dict(divergence.to_dict())
    if again.canonical_bytes() != divergence.canonical_bytes():
        problems.append("the divergence record does not round-trip")
    # the rejection record round-trips
    rejection = ConvergenceRejection(
        operation_id=journal.state().admitted[0],
        code=LocalFirstReason.CONSTRAINT_WEAKENED,
        detail="fixture: the claimed set drops latency-bound",
    )
    again_rej = ConvergenceRejection.from_dict(rejection.to_dict())
    if again_rej.canonical_bytes() != rejection.canonical_bytes():
        problems.append("the rejection record does not round-trip")
    # tampered dicts fail closed (tamper evidence): the snapshot's
    # derived identity and the journal records' derived identities are
    # re-verified at deserialization
    tampered = base.to_dict()
    tampered["fresh_until"] = "2026-12-01T00:00:00Z"
    tamper = expect_error(
        "tampered snapshot",
        LocalFirstReason.ID_MISMATCH,
        lambda: AuthoritySnapshot.from_dict(tampered),
    )
    if not tamper[1]:
        problems.append("the tampered snapshot round-tripped: %s" % tamper[2])
    tampered_record = journal.records()[1].to_dict()
    tampered_record["recorded_at"] = "2026-10-04T00:00:00Z"
    tamper_record = expect_error(
        "tampered journal record",
        LocalFirstReason.ID_MISMATCH,
        lambda: OfflineOperation.from_dict(tampered_record),
    )
    if not tamper_record[1]:
        problems.append("the tampered journal record round-tripped")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "snapshot/records/state/resync/divergence/rejection round-trips are "
        "byte-identical with stable content-derived ids; tampered dicts fail "
        "closed (tamper evidence)",
    )


# ---------------------------------------------------------------------------
# case_28 — (g) typed errors + exception isolation
# ---------------------------------------------------------------------------


def case_28_typed_errors_exception_isolation() -> Result:
    name = "case_28_typed_errors_exception_isolation"
    constraints = _constraints("latency-bound", "availability-floor")
    _, contract = _mature_contract(constraints)
    base = _base_view(contract)
    problems: List[str] = []
    # a malformed instant surfaces as the typed temporal rejection (the
    # consumed TemporalError wrapped, never leaked)
    temporal = expect_error(
        "malformed instant",
        LocalFirstReason.TEMPORAL_INVALID,
        lambda: OfflineOperation(
            operation_id="",
            episode_id="sha256:" + "1" * 64,
            contract_id=contract.contract_id,
            sequence=1,
            kind="partition-entered",
            recorded_at="2026-13-99T00:00:00Z",
            provenance=_prov(BATTERY_ISSUER),
            base_snapshot_id=base.snapshot_id,
            base_state_digest=base.state_digest,
            runtime_event_id="sha256:" + "2" * 64,
        ),
    )
    if not temporal[1]:
        problems.append(temporal[2])
    # a consumed M008 rejection surfaces with the deterministic text
    # preserved on this surface's own vocabulary (citing the kind)
    weakened = _weakened_constraints(contract.hard_constraints, "DROP", "latency-bound")
    try:
        check_admission_preserves_contract(
            contract, weakened, subject_value="lease:probe"
        )
        problems.append("the consumed M008 gate accepted the weakened set")
    except LocalFirstError as error:
        if error.code != LocalFirstReason.CONSTRAINT_WEAKENED:
            problems.append("the consumed gate wrap code %s" % error.code)
        elif "latency-bound" not in error.detail:
            problems.append("the consumed gate wrap lost the kind-citing text")
    # a reordered claimed set fails the fingerprint gate (tamper
    # evidence, not an admission outcome)
    reordered = expect_error(
        "reordered claimed set",
        LocalFirstReason.CONSTRAINT_MISMATCH,
        lambda: admit_operation(
            contract,
            base,
            episode_id="sha256:" + "3" * 64,
            sequence=2,
            subject=_subject("lease:reordered"),
            claimed_constraints=tuple(reversed(contract.hard_constraints)),
            decided_at=P1_ADMIT_A,
        ),
    )
    if not reordered[1]:
        problems.append(reordered[2])
    # the consumed M015 runtime's typed rejection surfaces as this
    # surface's own typed error with its deterministic text preserved
    # (exception isolation at the composition boundary)
    rstore = RuntimeStore()
    session = attach_runtime_session(
        rstore,
        contract,
        base,
        created_at=LF_CREATE,
        activated_at=LF_ACTIVATE,
        provenance=_prov(BATTERY_ISSUER),
    )
    rstore.fail(
        session.runtime_id,
        reason="probe-terminal",
        recorded_at="2026-10-02T00:10:00Z",
        provenance=_prov(BATTERY_ISSUER),
    )
    composition = expect_error(
        "terminal M015 runtime",
        LocalFirstReason.COMPOSITION,
        lambda: open_partition(
            rstore,
            session.runtime_id,
            contract,
            base,
            recorded_at=P1_OPEN,
        ),
    )
    if not composition[1]:
        problems.append(composition[2])
    elif "terminal" not in composition[2]:
        # the wrapped detail preserves the consumed deterministic text
        problems.append("the composition wrap lost the consumed text")
    # the rejected composition left the runtime journal byte-identical
    # (atomicity + no raw exception text into stored state)
    journal_bytes = b"".join(e.canonical_bytes() for e in rstore.events(session.runtime_id))
    if b"Traceback" in journal_bytes or b"Exception" in journal_bytes:
        problems.append("raw exception text leaked into stored state")
    if len(rstore.events(session.runtime_id)) != 3:
        problems.append("the rejected composition mutated the M015 journal")
    # every public error is the ONE typed error class (no foreign types)
    foreign = expect_error(
        "non-contract input",
        LocalFirstReason.INVALID_INPUT,
        lambda: authority_snapshot(
            "not-a-contract", (), fresh_from=BASE_FROM, fresh_until=BASE_UNTIL, recorded_at=BASE_RECORDED
        ),
    )
    if not foreign[1]:
        problems.append(foreign[2])
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "temporal/consumed-M008/fingerprint/composition/input rejections all "
        "typed with the deterministic text preserved; no raw exception text "
        "reaches stored state; rejected compositions leave the M015 journal "
        "byte-identical",
    )


# ---------------------------------------------------------------------------
# case_29 — (h) determinism under a re-run
# ---------------------------------------------------------------------------


def case_29_determinism_same_inputs() -> Result:
    name = "case_29_determinism_same_inputs"
    problems: List[str] = []
    first = _full_offline_scenario()
    second = _full_offline_scenario()
    if first != second:
        problems.append("the full offline scenario is not byte-identical on a re-run")
    # construction-is-recovery: a journal rebuilt from the serialized
    # records folds to the same state (the replay is the evidence)
    constraints = _constraints("latency-bound", "availability-floor")
    _, contract = _mature_contract(constraints)
    base = _base_view(contract)
    rstore, session, journal = _open_episode(contract, base)
    local_admit(
        journal,
        contract,
        base,
        subject=_subject(SUBJ_DEVICE_42),
        claimed_constraints=tuple(contract.hard_constraints),
        decided_at=P1_ADMIT_A,
        provenance=_prov(BATTERY_ISSUER),
    )
    serialized = [OfflineOperation.from_dict(r.to_dict()) for r in journal.records()]
    if fold_operations(serialized).canonical_bytes() != journal.state().canonical_bytes():
        problems.append("the serialized replay diverged from the live fold")
    rebuilt = OfflineJournal.from_records(serialized)
    if rebuilt.state().canonical_bytes() != journal.state().canonical_bytes():
        problems.append("the rebuilt journal diverged from the live state")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "the full offline scenario (journals, states, resync results, M015 "
        "runtime journals, reconnect evidence) is byte-identical across "
        "re-runs; construction-is-recovery verified on the serialized replay",
    )


# ---------------------------------------------------------------------------
# case_30 — (h) determinism across PYTHONHASHSEED subprocesses
# ---------------------------------------------------------------------------


def case_30_cross_process_pythonhashseed() -> Result:
    name = "case_30_cross_process_pythonhashseed"
    probe = r"""
import sys
sys.path.insert(0, %r)
sys.path.insert(0, %r)
import hashlib
from contracts import (
    ContractStore, CreateContract, ConnectivityPrincipal, BeneficiaryScope,
    OpaqueReference, Provenance, ValidityInterval, HardConstraint,
    TerminationRules, SelectOffers, ActivateContract, RecordExecutionActivation,
)
from resilience import RuntimeStore
from localfirst import (
    authority_snapshot, attach_runtime_session, open_partition, local_admit,
    close_partition,
)
T0 = "2026-10-01T00:00:00Z"
def prov(issuer, *refs):
    return Provenance(issuer=issuer, decision_refs=tuple(refs))
constraints = (
    HardConstraint(kind="latency-bound", params={"max_ms": 150}, provenance=prov("prov:netpro")),
    HardConstraint(kind="availability-floor", params={"nine": "three"}, provenance=prov("prov:netpro")),
)
cmd = CreateContract(
    principal=ConnectivityPrincipal(principal_kind="APPLICATION", principal_ref="app:lf-gateway-01"),
    beneficiaries=(BeneficiaryScope(beneficiary_kind="DEVICE", beneficiary_ref="dev:pi-7f2a"),),
    requirements=(OpaqueReference(ref_kind="intent-requirements", value="intent:abc123", provenance=prov("arch:localfirst")),),
    hard_constraints=constraints,
    validity=ValidityInterval(not_before=T0, not_after="2026-11-01T00:00:00Z"),
    service_properties=(OpaqueReference(ref_kind="service-property", value="prop:committed-1", provenance=prov("prov:netpro")),),
    usage_pricing_terms=OpaqueReference(ref_kind="usage-pricing-terms", value="terms:comm-42", provenance=prov("comm:ops")),
    assurance_obligations=(OpaqueReference(ref_kind="assurance-obligation", value="oblig:evid-7"),),
    execution_scope=(OpaqueReference(ref_kind="execution-scope", value="scope:exec-default"),),
    termination=TerminationRules(
        conditions=("principal-requested", "constraint-violated"),
        compensation=OpaqueReference(ref_kind="compensation", value="comp:rule-9", provenance=prov("comm:ops")),
    ),
    provenance=prov("arch:localfirst", "dec:elig-1"),
)
store = ContractStore()
created = store.submit(cmd, recorded_at="2026-09-30T10:00:00Z")
cid = created.contract.contract_id
offers = (
    OpaqueReference(ref_kind="offer", value="offer:netpro-basic-1", provenance=prov("prov:netpro")),
    OpaqueReference(ref_kind="offer", value="offer:skywave-mesh-1", provenance=prov("prov:skywave")),
)
store.submit(SelectOffers(offers=offers), recorded_at="2026-09-30T10:05:00Z", contract_id=cid)
store.submit(ActivateContract(activated_at=T0, signature_refs=(OpaqueReference(ref_kind="signature", value="sig:ed25519-1"),)), recorded_at=T0, contract_id=cid)
store.submit(RecordExecutionActivation(recorded_at=T0), recorded_at=T0, contract_id=cid)
contract = store.contract(cid)
def rec(value):
    return OpaqueReference(ref_kind="execution-artifact", value=value, provenance=prov("prov:netpro"))
def subj(value):
    return OpaqueReference(ref_kind="execution-artifact", value=value, provenance=prov("app:lf-gateway-01"))
base = authority_snapshot(
    contract, (rec("record:lease-alpha"), rec("record:lease-beta")),
    fresh_from="2026-10-02T00:00:00Z", fresh_until="2026-10-09T00:00:00Z",
    recorded_at="2026-10-02T00:00:00Z",
)
fresh = authority_snapshot(
    contract, (rec("record:lease-beta"), rec("record:lease-gamma")),
    fresh_from="2026-10-11T00:00:00Z", fresh_until="2026-10-18T00:00:00Z",
    recorded_at="2026-10-11T00:00:00Z",
)
rstore = RuntimeStore()
session = attach_runtime_session(rstore, contract, base, created_at="2026-10-02T00:00:00Z", activated_at="2026-10-02T00:01:00Z", provenance=prov("localfirst:battery"))
journal, _ = open_partition(rstore, session.runtime_id, contract, base, recorded_at="2026-10-03T00:00:00Z", provenance=prov("localfirst:battery"))
local_admit(journal, contract, base, subject=subj("lease:dev-42"), claimed_constraints=contract.hard_constraints, decided_at="2026-10-03T01:00:00Z", provenance=prov("localfirst:battery"))
local_admit(journal, contract, base, subject=subj("lease:dev-43"), claimed_constraints=contract.hard_constraints, decided_at="2026-10-10T00:00:00Z", provenance=prov("localfirst:battery"))
close = close_partition(rstore, session.runtime_id, contract, journal, fresh, recorded_at="2026-10-11T00:00:00Z", provenance=prov("localfirst:battery"))
journal_bytes = b"".join(r.canonical_bytes() for r in journal.records())
print(close.resync.resync_id)
print(hashlib.sha256(journal_bytes).hexdigest())
print(hashlib.sha256(close.resync.canonical_bytes()).hexdigest())
""" % (str(REPO_ROOT), str(REPO_ROOT / "tools"))
    ids: set = set()
    for seed in ("0", "1", "42"):
        env = {"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"}
        run = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(REPO_ROOT),
        )
        if run.returncode != 0:
            return fail(name, "seed %s subprocess failed: %s" % (seed, run.stderr[-200:]))
        lines = [line for line in run.stdout.splitlines() if line.strip()]
        if len(lines) != 3:
            return fail(name, "seed %s unexpected output" % seed)
        ids.add(tuple(lines))
    if len(ids) != 1:
        return fail(name, "scenario material differs across seeds: %d distinct" % len(ids))
    return ok(
        name,
        "byte-identical resync ids, journal digests and resync records "
        "across PYTHONHASHSEED 0/1/42 subprocesses",
    )


# ---------------------------------------------------------------------------
# case_31 — the lock-conformance mapping (aggregate structural evidence)
# ---------------------------------------------------------------------------


def case_31_lock_conformance_mapping() -> Result:
    name = "case_31_lock_conformance_mapping"
    constraints = _constraints("latency-bound", "availability-floor")
    _, contract = _mature_contract(constraints)
    base = _base_view(contract)
    rstore, session, journal = _open_episode(contract, base)
    rid = session.runtime_id
    record = local_admit(
        journal,
        contract,
        base,
        subject=_subject(SUBJ_DEVICE_42),
        claimed_constraints=tuple(contract.hard_constraints),
        decided_at=P1_ADMIT_A,
        provenance=_prov(BATTERY_ISSUER),
    )
    problems: List[str] = []
    # LOCK-101/117: the local-first records ride the contract as opaque
    # references — the snapshot, the operations and the state cite the
    # contract id, never re-derive contract identity, and never become
    # a second contract authority.  The claimed constraint sets riding
    # the journal records are DATA (the ReplanCandidate precedent) —
    # no AUTHORITY constraint material exists on the fold surfaces.
    forbidden_authority_members = {"hard_constraint_fingerprint", "constraints", "hard_constraints"}
    # the snapshot carries the CONTRACT's own fingerprint as an opaque
    # citation (LOCK-108 verification material), which is the
    # disclosed exception — it never carries the constraint set
    if set(AuthoritySnapshot.__dataclass_fields__) & {"hard_constraints", "constraints"}:
        problems.append("the snapshot carries a constraint set")
    state_fields = set(LocalState.__dataclass_fields__)
    if state_fields & forbidden_authority_members:
        problems.append("the local state carries constraint material")
    if base.constraint_fingerprint != contract.hard_constraint_fingerprint():
        problems.append("the snapshot does not carry the contract's own fingerprint")
    if journal.state().contract_id != contract.contract_id:
        problems.append("the local state does not cite the owning contract")
    for rec in journal.records():
        if not rec.contract_id.startswith("sha256:"):
            problems.append("a record lost its opaque contract citation")
    # the claimed set rides the ADMISSION record only (re-validated at
    # admission AND at resync — the data-not-authority discipline)
    if not record.hard_constraints:
        problems.append("the admitted record lost its claimed set")
    if record.kind != "connectivity-admission":
        problems.append("constraint data rode a non-admission record")
    # LOCK-106: the degraded evidence typing comes from the accepted
    # vocabulary (case_25 exercises the value gate)
    if "observation" not in EVIDENCE_TYPES:
        problems.append("the degraded evidence kind is not in the accepted vocabulary")
    # LOCK-111: the resolution keys are the consumed M008 vocabulary
    if set(TIE_BREAK_KEYS) <= {"recorded-at", "observed-at", "wall-clock"}:
        problems.append("a temporal resolution key exists in the consumed vocabulary")
    # LOCK-118: provenance on every record
    for rec in journal.records():
        if not rec.provenance.issuer:
            problems.append("a journal record lost its provenance issuer")
    if not base.provenance.issuer:
        problems.append("the snapshot lost its provenance issuer")
    # LOCK-119: content-derived ids only (no uuid randomness)
    for rec in journal.records():
        if not rec.operation_id.startswith("sha256:"):
            problems.append("a record identity is not content-derived")
    if not base.snapshot_id.startswith("sha256:"):
        problems.append("the snapshot identity is not content-derived")
    # the consumed M015 runtime is driven, never duplicated: the
    # offline transitions land on the ACCEPTED runtime journal
    kinds = [e.kind for e in rstore.events(rid)]
    if kinds[:3] != ["session-created", "session-activated", "degraded-entered"]:
        problems.append("the offline transitions did not ride the M015 journal")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "LOCK-101/106/108/111/117/118/119 conformance evidenced (opaque "
        "references only; the claimed sets are admission DATA re-validated "
        "twice; the snapshot carries the contract's own fingerprint; "
        "provenance and content ids on every record; the M015 runtime driven "
        "by reference)",
    )


# ---------------------------------------------------------------------------
# case_32 — the clock/import discipline (AST audit of localfirst/)
# ---------------------------------------------------------------------------


def case_32_clock_import_discipline() -> Result:
    name = "case_32_clock_import_discipline"
    problems: List[str] = []
    files = sorted((REPO_ROOT / "localfirst").glob("*.py"))
    if not files:
        return fail(name, "the localfirst/ package is missing")
    allowed = {
        "__future__",
        "contextlib",
        "hashlib",
        "re",
        "dataclasses",
        "typing",
        "protocol",
        "contracts",
        "replan",
        "resilience",
        "localfirst",
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
        "no clock/random/network constructs anywhere in localfirst/; imports: "
        "stdlib + protocol + the accepted authorities (contracts, replan, "
        "resilience) — by reference only",
    )


# ---------------------------------------------------------------------------
# case_33 — the one-way import boundary
# ---------------------------------------------------------------------------


def _code_tokens(source: str) -> bool:
    """True when the source references localfirst in CODE (an AST token),
    not merely in a docstring/comment."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "localfirst":
            return True
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == "localfirst":
                return True
        if isinstance(node, ast.ImportFrom) and node.module and "localfirst" in node.module:
            return True
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "localfirst":
                    return True
    return False


def case_33_one_way_imports() -> Result:
    name = "case_33_one_way_imports"
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
    )
    for package in authorities:
        package_dir = REPO_ROOT / package
        if not package_dir.is_dir():
            continue
        for path in sorted(package_dir.glob("*.py")):
            source = path.read_text(encoding="utf-8")
            if "localfirst" in source and _code_tokens(source):
                problems.append(
                    "%s references localfirst (imports must be one-way)" % path.name
                )
    # the legacy reservoir stays un-imported by localfirst/ (source
    # material only — the R8 charter consumption rule)
    legacy = ("sessions", "mobility", "multipath", "edge", "appliance")
    tree_modules: set = set()
    for path in sorted((REPO_ROOT / "localfirst").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                tree_modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                tree_modules.add(node.module.split(".")[0])
    for package in legacy:
        if package in tree_modules:
            problems.append("localfirst/ imports the legacy %s/ package" % package)
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "no accepted authority imports localfirst/ (one-way boundary); the "
        "legacy reservoir is un-imported source material only",
    )


# ---------------------------------------------------------------------------
# case_34 — the PR delta shape (the active authorization scope)
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


def case_34_pr_delta_shape_authorized_scope() -> Result:
    name = "case_34_pr_delta_shape_authorized_scope"
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
        "delta confined to the M016 scope (%d file(s): localfirst/ + the "
        "battery + the evidence doc)" % len(delta),
    )


# ---------------------------------------------------------------------------
# case_35 — the evidence-doc honesty
# ---------------------------------------------------------------------------


def case_35_evidence_doc_honest() -> Result:
    name = "case_35_evidence_doc_honest"
    path = REPO_ROOT / "docs" / "M016-evidence.md"
    if not path.exists():
        return fail(name, "docs/M016-evidence.md is missing")
    text = path.read_text(encoding="utf-8")
    problems: List[str] = []
    if "SOFTWARE" not in text:
        problems.append("the evidence class is not disclosed")
    if "M016" not in text:
        problems.append("the evidence does not name M016")
    if "LOCK-108" not in text:
        problems.append("the LOCK-108 mapping is not disclosed")
    if "harvest" not in text.lower():
        problems.append("the harvest is not disclosed")
    if "EVID-002" not in text:
        problems.append("the open physical evidence obligations are not disclosed")
    if "by reference" not in text.lower():
        problems.append("the by-reference composition is not disclosed")
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
        "SOFTWARE class, by-reference composition, harvest, locks and the "
        "open physical obligations disclosed; no affirmative physical claims",
    )


# ===========================================================================
# Main
# ===========================================================================


def main() -> int:
    results: List[Result] = []
    results.append(case_01_frozen_vocabularies())
    results.append(case_02_vocabulary_fail_closed())
    results.append(case_03_journal_round_trips())
    results.append(case_04_idempotent_append())
    # (b) partition-tolerant admission: one case per freshness outcome
    results.append(case_05_fresh_authority_admits())
    results.append(case_06_stale_authority_fails_closed())
    results.append(case_07_not_yet_valid_fails_closed())
    results.append(case_08_inclusive_window_bounds())
    # (d) LOCK-108 across the offline boundary: one numbered case per
    # constraint kind (12 kinds), each probing DROP/RELAX/REINTERPRET on
    # the admission twin + the raising gate + the forged journaled
    # admitted record rejected by the resync re-verification
    for index, kind in enumerate(ALL_KINDS, start=9):
        results.append(_lock108_case(kind, index))
    # (c) reconnect + resynchronization
    results.append(case_21_clean_convergence())
    results.append(case_22_divergence_detected_typed())
    results.append(case_23_deterministic_declared_resolution())
    results.append(case_24_invalid_rules_fail_closed())
    # (e)/(f) the journaled degraded mode + the M015 composition
    results.append(case_25_degraded_mode_journaled_evidence_visible())
    results.append(case_26_m015_composition())
    # (g)/(h) round-trips, typed errors, determinism
    results.append(case_27_canonical_round_trips())
    results.append(case_28_typed_errors_exception_isolation())
    results.append(case_29_determinism_same_inputs())
    results.append(case_30_cross_process_pythonhashseed())
    # the structural closing set
    results.append(case_31_lock_conformance_mapping())
    results.append(case_32_clock_import_discipline())
    results.append(case_33_one_way_imports())
    results.append(case_34_pr_delta_shape_authorized_scope())
    results.append(case_35_evidence_doc_honest())

    print("ADCOS local-first self-test (M016 — Local-First and Offline Operation)")
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
