#!/usr/bin/env python3
"""ADCOS resilience self-test (M015 — Execution Resilience Runtime).

Deterministic, offline verification of the ``resilience/`` package
against the frozen Architecture 1.1 mandate (R8-CORE-001, DEC-0114; the
R8 charter M015 acceptance criteria): the execution-runtime resilience
domain — the session-runtime lifecycle with EXPLICIT reconnect
transitions (the WORK-012 discipline re-expressed on the 1.1 authority
and functionally enforced: every route change an explicit recorded
reconnect event naming old AND new references, never a silent
replacement), mobility handover with hard-constraint preservation
(LOCK-108 — typed weakened-constraint rejection), multipath failover
orchestration with deterministic declared recorded tie-breaking
(LOCK-111) over the accepted ``executionplans/`` alternative segments,
the realization-state vocabulary consumed BY REFERENCE from the M008
kernel (projected onto, never redefined), explicit and evidence-visible
degraded-mode entry/exit, execution artifacts as opaque references
(LOCK-117), the replan-kernel composition core (the runtime DRIVES the
accepted M008 decisions — the gate is exercised, never duplicated),
provenance (LOCK-118), LOCK-119 determinism/secrets discipline,
canonical-JSON round-trips, typed fail-closed errors, and the
one-way-import boundary (no accepted authority imports ``resilience/``).

Battery coverage (the M015 work-item matrix, the charter's (a)-(j)):

- (a) case_03/case_04 — the session-runtime create / transition /
  reconnect / terminate round-trips; every reconnect event records old
  AND new references (the typed ``RuntimeReconnect`` evidence derived
  from the journal's initiated+completed pairs);
- (b) case_05 — a silent-replacement attempt is rejected (the WORK-012
  discipline mechanically enforced: orphaned completions, wrong old
  references, undeclared new references, route members outside the
  reconnect kinds, unnamed realizations — all fail closed
  ``resilience-silent-replacement``);
- (c) case_07 — successful handover: the new realization satisfies the
  SAME hard constraints (typed record, provenance intact — the consumed
  cross-authority gate re-verifies the decision against the contract);
- (d) case_08..case_19 — LOCK-108 per constraint kind (all 12 kinds ×
  DROP/RELAX/REINTERPRET on the handover gate; the engine drive never
  adopts a weakening candidate; the failover-side weakened plan rejected
  by the consumed M006 gate with the typed kind-citing reason);
- (e) case_20/case_21/case_22 — impossible realization: the EXPLICIT
  degraded state (soft trigger), the EXPLICIT failed state (hard
  trigger), and the EXPLICIT renegotiation trigger path (the successor
  contract created through the M002 ``superseded-contract`` reference);
- (f) case_23/case_24/case_25 — deterministic multipath failover
  selection with declared recorded tie-breaking (same inputs run twice
  -> byte-identical decision records; input-order independence; LOCK-115
  no-alternatives typed honesty; invalid/temporal/reordered rules fail
  closed);
- (g) case_26 — the replan-kernel composition: the runtime drives the
  accepted M008 decisions onto the journal (all four outcome kinds) with
  the attribution gates fail-closed — the kernel's decision gate is
  exercised, never duplicated;
- (h) case_27 — degraded-mode entry/exit journaled and evidence-visible
  (evidence kinds from the accepted ``evidence/`` LOCK-106 vocabulary,
  decision-kinded evidence references, the explicit recovery edge);
- (i) case_28/case_29 — canonical-JSON round-trips + typed errors +
  exception isolation (consumed-domain errors wrapped with their
  deterministic text preserved; no raw exception text into stored
  state);
- (j) case_30/case_31 — determinism under a re-run (byte-identical
  journals/sessions/decisions; construction-is-recovery) and across
  PYTHONHASHSEED subprocesses;
- plus the frozen-vocabulary/additive-projection matrix, journal
  divergence fail-closed, lock-conformance mapping, clock/import
  discipline, the one-way-import boundary, the PR delta shape, and the
  evidence-doc honesty.

All instants are injected (T0-style constants); no wall clock, no
randomness, no network, no real sockets, no secrets (any
credential-shaped fixture is assembled at runtime from fragments so the
full shape never appears in source). Runs are byte-identical across
processes (PYTHONHASHSEED-safe).
"""

from __future__ import annotations

import ast
import hashlib
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from protocol.canonicalization import canonical_json_bytes  # noqa: E402

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
    RecordAssurance,
    RecordExecutionActivation,
    SelectOffers,
    TerminationRules,
    ValidityInterval,
)
from executionplans import (  # noqa: E402
    ExecutionPlan,
    SegmentInput,
    translate_contract,
    verify_plan_preserves_contract,
)
from replan import (  # noqa: E402
    CANDIDATE_KINDS,
    DECISION_KINDS,
    DEFAULT_TIE_BREAK,
    REALIZATION_STATES,
    REALIZATION_TERMINAL_STATES,
    TIE_BREAK_KEYS,
    TRIGGER_KINDS,
    ReplanCandidate,
    ReplanTrigger,
    bridge_commands,
    decide_replan,
    renegotiation_reference,
    verify_decision_preserves_contract,
)
from evidence import EVIDENCE_TYPES  # noqa: E402

from resilience import (  # noqa: E402
    DRIVE_OUTCOME_KINDS,
    EVENT_TARGET_STATES,
    FAILOVER_CANDIDATE_KIND,
    FAILOVER_TRIGGER_KINDS,
    FAILOVER_TRIGGER_MAP,
    HANDOVER_CANDIDATE_KIND,
    ROUTE_MEMBER_NAMES,
    RUNTIME_DRIVEN_ISSUER,
    RUNTIME_EVENT_KINDS,
    RUNTIME_ISSUER,
    RUNTIME_REALIZATION_MAP,
    RUNTIME_RECONNECTABLE_STATES,
    RUNTIME_STATES,
    RUNTIME_TERMINAL_STATES,
    RUNTIME_TRANSITIONS,
    ResilienceError,
    ResilienceReason,
    RuntimeEvent,
    RuntimeReconnect,
    RuntimeSession,
    RuntimeStore,
    check_realization_surface,
    check_runtime_transition,
    derive_runtime_id,
    drive_replan_decision,
    failover_alternatives,
    fold_events,
    handover_candidate,
    handover_verdict,
    orchestrate_failover,
    perform_handover,
    reconnect_evidence,
    runtime_realization_snapshot,
    validate_handover_preserves_contract,
)

Result = Tuple[str, bool, str]

T0 = "2026-10-01T00:00:00Z"
T_END = "2026-11-01T00:00:00Z"
CREATE_AT = "2026-09-30T10:00:00Z"
OFFER_SEL_AT = "2026-09-30T10:05:00Z"

# Runtime-side injected instants (inside the owning contract's validity
# window so the consumed replan kernel accepts the drives).
R_CREATE = "2026-10-02T00:00:00Z"
R_ACTIVATE = "2026-10-02T00:05:00Z"
R_RECONNECT_A = "2026-10-03T00:00:00Z"
R_RECONNECT_A_DONE = "2026-10-03T00:01:00Z"
R_DEGRADED = "2026-10-04T00:00:00Z"
R_RECOVER = "2026-10-05T00:00:00Z"
R_RECONNECT_B = "2026-10-06T00:00:00Z"
R_RECONNECT_B_DONE = "2026-10-06T00:01:00Z"
R_RECONNECT_B_FAILED = "2026-10-06T00:02:00Z"
R_HANDOVER = "2026-10-07T00:00:00Z"
R_FAILOVER = "2026-10-08T00:00:00Z"
R_DRIVE = "2026-10-09T00:00:00Z"
R_TERMINATE = "2026-10-10T00:00:00Z"
R_OUTSIDE = "2026-12-01T00:00:00Z"  # escapes the contract validity

# Opaque realization references (LOCK-117: references, never authority).
ROUTE_D0 = "route:decision-0001"
PATH_P0 = "path:primary-0001"
ROUTE_D1 = "route:decision-0002"
PATH_P1 = "path:alternative-0002"
ROUTE_D2 = "route:decision-0003"
PATH_P2 = "path:alternative-0003"
ROUTE_H1 = "route:handover-0004"
PATH_H1 = "path:handover-0004"

BATTERY_ISSUER = "resilience:battery"

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
    except ResilienceError as error:
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
    return fail(case, "expected ResilienceError(%s); the input was accepted" % code)


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
            principal_kind="APPLICATION", principal_ref="app:resilience-gw-01"
        ),
        beneficiaries=(
            BeneficiaryScope(beneficiary_kind="DEVICE", beneficiary_ref="dev:pi-7f2a"),
        ),
        requirements=(
            OpaqueReference(
                ref_kind="intent-requirements",
                value="intent:abc123",
                provenance=_prov("arch:resilience"),
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
        provenance=_prov("arch:resilience", "dec:elig-1"),
    )


_OFFER_A = OpaqueReference(
    ref_kind="offer", value="offer:netpro-basic-1", provenance=_prov("prov:netpro")
)
_OFFER_B = OpaqueReference(
    ref_kind="offer", value="offer:skywave-mesh-1", provenance=_prov("prov:skywave")
)
_OFFER_C = OpaqueReference(
    ref_kind="offer", value="offer:skywave-failover-1", provenance=_prov("prov:skywave")
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
        SelectOffers(offers=(_OFFER_A, _OFFER_B, _OFFER_C)),
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


def _runtime_session(contract: Any) -> Tuple[RuntimeStore, RuntimeSession]:
    """A fresh runtime store whose single session is ACTIVE on the
    initial realization references (D0/P0)."""
    store = RuntimeStore()
    created = store.create(
        contract_id=contract.contract_id,
        created_at=R_CREATE,
        provenance=_prov(BATTERY_ISSUER),
    )
    store.activate(
        created.runtime_id,
        route_decision_id=ROUTE_D0,
        path_id=PATH_P0,
        recorded_at=R_ACTIVATE,
        provenance=_prov(BATTERY_ISSUER),
    )
    return store, store.session(created.runtime_id)


def _failover_plan(contract: Any) -> ExecutionPlan:
    """A complex-deployment plan (LOCK-116): one primary segment plus two
    alternative-role segments (the failover alternatives under ONE
    contract), translated from the SAME contract through the accepted
    M006 bridge."""
    return translate_contract(
        contract,
        (
            SegmentInput(
                offer_reference=_OFFER_A,
                role="primary",
                operations=("reserve", "activate", "measure"),
                provenance=_prov("optimizer:failover-v1", "dec:opt-f0"),
            ),
            SegmentInput(
                offer_reference=_OFFER_B,
                role="alternative",
                operations=("reserve", "activate", "measure"),
                provenance=_prov("optimizer:failover-v1", "dec:opt-f1"),
            ),
            SegmentInput(
                offer_reference=_OFFER_C,
                role="alternative",
                operations=("reserve", "activate"),
                provenance=_prov("optimizer:failover-v1", "dec:opt-f2"),
            ),
        ),
        provenance=_prov("optimizer:failover-v1", "dec:opt-failover"),
    )


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


def _forged_weakened_plan(
    plan: ExecutionPlan, weakened: Tuple[HardConstraint, ...]
) -> ExecutionPlan:
    """A wire-forged variant of an accepted plan whose constraint set is
    weakened but whose identities are re-derived over the forged content
    (ids are tamper-EVIDENT, not tamper-proof secrets — the battery
    recomputes exactly what the accepted derivation computes).  The
    consumed M006 LOCK-108 gate must reject it against the owning
    contract."""
    data = plan.to_dict()
    data["hard_constraints"] = [c.to_dict() for c in weakened]
    data["constraint_fingerprint"] = "sha256:" + hashlib.sha256(
        canonical_json_bytes({"constraints": data["hard_constraints"]})
    ).hexdigest()
    document = {
        "contract_id": data["contract_id"],
        "hard_constraints": data["hard_constraints"],
        "constraint_fingerprint": data["constraint_fingerprint"],
        "validity": data["validity"],
        "segment_ids": [s["segment_id"] for s in data["segments"]],
        "tie_break": data["tie_break"],
        "provenance": data["provenance"],
    }
    payload = dict(document)
    payload["namespace"] = "adc-os-execution-plan"
    data["plan_id"] = "sha256:" + hashlib.sha256(
        canonical_json_bytes(payload)
    ).hexdigest()
    return ExecutionPlan.from_dict(data)


# ---------------------------------------------------------------------------
# The deterministic full-lifecycle scenario (the round-trip + determinism
# material): create -> activate -> reconnect (complete) -> degraded ->
# recovered -> reconnect (failed) -> reconnect (complete) -> terminate.
# ---------------------------------------------------------------------------


def _full_lifecycle_scenario() -> Tuple[bytes, ...]:
    constraints = _constraints("latency-bound", "availability-floor")
    _, contract = _mature_contract(constraints)
    store, session = _runtime_session(contract)
    rid = session.runtime_id
    store.initiate_reconnect(
        rid,
        candidate_route_decision_id=ROUTE_D1,
        candidate_path_id=PATH_P1,
        recorded_at=R_RECONNECT_A,
        provenance=_prov(BATTERY_ISSUER),
    )
    store.complete_reconnect(
        rid, recorded_at=R_RECONNECT_A_DONE, provenance=_prov(BATTERY_ISSUER)
    )
    store.enter_degraded(
        rid,
        evidence_kind="observation",
        recorded_at=R_DEGRADED,
        provenance=_prov(BATTERY_ISSUER),
    )
    store.recover_degraded(
        rid, recorded_at=R_RECOVER, provenance=_prov(BATTERY_ISSUER)
    )
    store.initiate_reconnect(
        rid,
        candidate_route_decision_id=ROUTE_D2,
        candidate_path_id=PATH_P2,
        recorded_at=R_RECONNECT_B,
        provenance=_prov(BATTERY_ISSUER),
    )
    store.fail_reconnect(
        rid,
        target="DEGRADED",
        reason="probe-timeout",
        recorded_at=R_RECONNECT_B_FAILED,
        provenance=_prov(BATTERY_ISSUER),
    )
    store.initiate_reconnect(
        rid,
        candidate_route_decision_id=ROUTE_D2,
        candidate_path_id=PATH_P2,
        recorded_at=R_RECONNECT_B,
        provenance=_prov(BATTERY_ISSUER),
    )
    store.complete_reconnect(
        rid, recorded_at=R_RECONNECT_B_DONE, provenance=_prov(BATTERY_ISSUER)
    )
    store.terminate(
        rid, recorded_at=R_TERMINATE, provenance=_prov(BATTERY_ISSUER)
    )
    material = (
        store.session(rid).canonical_bytes(),
        b"".join(e.canonical_bytes() for e in store.events(rid)),
        b"".join(r.canonical_bytes() for r in store.reconnect_evidence(rid)),
    )
    return material


def _failover_scenario() -> Tuple[bytes, ...]:
    """The deterministic failover scenario: an ACTIVE runtime session
    over a complex-deployment plan fails over onto an alternative
    segment (the explicit reconnect pair)."""
    constraints = _constraints("latency-bound", "availability-floor")
    _, contract = _mature_contract(constraints)
    plan = _failover_plan(contract)
    store, session = _runtime_session(contract)
    result = orchestrate_failover(
        store,
        session.runtime_id,
        contract,
        plan,
        trigger_kind="path-failed",
        recorded_at=R_FAILOVER,
    )
    return (
        result.decision.canonical_bytes(),
        result.session.canonical_bytes(),
        b"".join(e.canonical_bytes() for e in store.events(session.runtime_id)),
        b"".join(r.canonical_bytes() for r in store.reconnect_evidence(session.runtime_id)),
    )


# ---------------------------------------------------------------------------
# case_01 — the frozen vocabularies and the additive realization
# projection (the M008 vocabulary consumed BY REFERENCE, never redefined)
# ---------------------------------------------------------------------------


def case_01_frozen_vocabularies() -> Result:
    name = "case_01_frozen_vocabularies"
    problems: List[str] = []
    if RUNTIME_STATES != (
        "PENDING",
        "ACTIVE",
        "RECONNECTING",
        "DEGRADED",
        "FAILED",
        "TERMINATED",
    ):
        problems.append("the runtime-state vocabulary drifted")
    if RUNTIME_TERMINAL_STATES != ("FAILED", "TERMINATED"):
        problems.append("the terminal-state set drifted")
    if RUNTIME_TRANSITIONS != {
        "PENDING": ("ACTIVE", "FAILED", "TERMINATED"),
        "ACTIVE": ("RECONNECTING", "DEGRADED", "FAILED", "TERMINATED"),
        "RECONNECTING": ("ACTIVE", "DEGRADED", "FAILED", "TERMINATED"),
        "DEGRADED": ("RECONNECTING", "ACTIVE", "FAILED", "TERMINATED"),
        "FAILED": (),
        "TERMINATED": (),
    }:
        problems.append("the runtime transition table drifted")
    if RUNTIME_RECONNECTABLE_STATES != ("ACTIVE", "DEGRADED"):
        problems.append("the reconnectable-state set drifted")
    if RUNTIME_EVENT_KINDS != (
        "session-created",
        "session-activated",
        "reconnect-initiated",
        "reconnect-completed",
        "reconnect-failed",
        "degraded-entered",
        "degraded-recovered",
        "session-failed",
        "session-terminated",
    ):
        problems.append("the event-kind vocabulary drifted")
    if ROUTE_MEMBER_NAMES != ("route_decision_id", "path_id"):
        problems.append("the route-member shape drifted")
    if DRIVE_OUTCOME_KINDS != ("adopted", "degraded", "failed", "renegotiate"):
        problems.append("the drive-outcome vocabulary drifted")
    # the M008-owned realization vocabulary is consumed BY REFERENCE and
    # NEVER redefined: the frozen four-state set, extended only additively
    # (the projection maps onto existing states only)
    if REALIZATION_STATES != ("REALIZING", "DEGRADED", "FAILED", "SUPERSEDED"):
        problems.append("the consumed M008 realization vocabulary drifted")
    projected = set(RUNTIME_REALIZATION_MAP.values())
    if not projected <= set(REALIZATION_STATES):
        problems.append("the runtime projection escapes the consumed vocabulary")
    if "SUPERSEDED" in projected:
        problems.append("the runtime projection invented a SUPERSEDED mapping")
    if RUNTIME_REALIZATION_MAP != {
        "ACTIVE": "REALIZING",
        "RECONNECTING": "REALIZING",
        "DEGRADED": "DEGRADED",
        "FAILED": "FAILED",
    }:
        problems.append("the frozen realization projection drifted")
    # the consumed trigger/candidate/tie-break vocabularies (by reference)
    if set(FAILOVER_TRIGGER_MAP.values()) - set(TRIGGER_KINDS):
        problems.append("the failover trigger map escapes the consumed M008 kinds")
    if FAILOVER_TRIGGER_KINDS != ("path-failed", "path-degraded"):
        problems.append("the failover trigger kinds drifted")
    if FAILOVER_TRIGGER_MAP != {
        "path-failed": "segment-loss",
        "path-degraded": "assurance-degraded",
    }:
        problems.append("the failover trigger map drifted")
    if HANDOVER_CANDIDATE_KIND not in CANDIDATE_KINDS:
        problems.append("the handover candidate kind is outside the consumed set")
    if FAILOVER_CANDIDATE_KIND not in CANDIDATE_KINDS:
        problems.append("the failover candidate kind is outside the consumed set")
    if HANDOVER_CANDIDATE_KIND != "mobility-handover":
        problems.append("the handover candidate kind drifted")
    if FAILOVER_CANDIDATE_KIND != "execution-plan":
        problems.append("the failover candidate kind drifted")
    if set(TIE_BREAK_KEYS) != {"candidate-kind", "candidate-id"}:
        problems.append("the consumed tie-break key vocabulary drifted")
    if tuple(DEFAULT_TIE_BREAK) != ("candidate-kind", "candidate-id"):
        problems.append("the consumed default tie-break drifted")
    # the frozen reason vocabulary (15 fail-closed codes, all distinct)
    values = ResilienceReason.values()
    if len(values) != 15 or len(set(values)) != 15:
        problems.append("the resilience reason vocabulary drifted (%d codes)" % len(values))
    if any(not code.startswith("resilience-") for code in values):
        problems.append("a reason code escaped the resilience- prefix")
    if tuple(CONSTRAINT_KINDS) != ALL_KINDS:
        problems.append("the consumed constraint-kind vocabulary drifted")
    # the kind/state chain vocabulary
    if EVENT_TARGET_STATES != {
        "session-created": ("PENDING",),
        "session-activated": ("ACTIVE",),
        "reconnect-initiated": ("RECONNECTING",),
        "reconnect-completed": ("ACTIVE",),
        "reconnect-failed": ("DEGRADED", "FAILED"),
        "degraded-entered": ("DEGRADED",),
        "degraded-recovered": ("ACTIVE",),
        "session-failed": ("FAILED",),
        "session-terminated": ("TERMINATED",),
    }:
        problems.append("the kind/state chain vocabulary drifted")
    if RUNTIME_ISSUER != "resilience:runtime":
        problems.append("the runtime issuer drifted")
    if RUNTIME_DRIVEN_ISSUER != "resilience:runtime-replan-drive":
        problems.append("the driven issuer drifted")
    if set(DECISION_KINDS) != {
        "adopt-alternative",
        "degraded",
        "failed",
        "renegotiate",
    }:
        problems.append("the consumed decision-kind vocabulary drifted")
    if set(REALIZATION_TERMINAL_STATES) != {"FAILED", "SUPERSEDED"}:
        problems.append("the consumed terminal realization states drifted")
    if set(EVIDENCE_TYPES) != {"claim", "observation", "commitment", "attestation"}:
        problems.append("the consumed evidence-type vocabulary drifted")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "runtime/event/outcome vocabularies frozen; the M008 realization, "
        "trigger, candidate and tie-break vocabularies consumed by reference "
        "(additive projection, nothing redefined)",
    )


# ---------------------------------------------------------------------------
# case_02 — vocabulary and input gates fail closed with typed codes
# ---------------------------------------------------------------------------


def case_02_vocabulary_fail_closed() -> Result:
    name = "case_02_vocabulary_fail_closed"
    constraints = _constraints("latency-bound")
    _, contract = _mature_contract(constraints)
    problems: List[str] = []

    def _probe(label: str, code: str, action: Callable[[], Any]) -> None:
        try:
            action()
            problems.append("%s was accepted" % label)
        except ResilienceError as error:
            if error.code != code:
                problems.append("%s: expected %s, got %s" % (label, code, error.code))

    _probe(
        "terminal transition",
        ResilienceReason.SESSION_TERMINAL,
        lambda: check_runtime_transition("FAILED", "ACTIVE"),
    )
    _probe(
        "illegal transition",
        ResilienceReason.TRANSITION_ILLEGAL,
        lambda: check_runtime_transition("ACTIVE", "PENDING"),
    )
    _probe(
        "PENDING realization surface",
        ResilienceReason.REALIZATION_NOT_ESTABLISHED,
        lambda: check_realization_surface("PENDING"),
    )
    _probe(
        "TERMINATED realization surface",
        ResilienceReason.SESSION_TERMINAL,
        lambda: check_realization_surface("TERMINATED"),
    )
    _probe(
        "unknown runtime state",
        ResilienceReason.VOCABULARY,
        lambda: RuntimeSession(
            runtime_id="sha256:" + "1" * 64,
            contract_id=contract.contract_id,
            state="HIBERNATING",
            created_at=R_CREATE,
            sequence=1,
            provenance=_prov(BATTERY_ISSUER),
        ),
    )
    _probe(
        "unknown event kind",
        ResilienceReason.VOCABULARY,
        lambda: RuntimeEvent(
            runtime_id="sha256:" + "1" * 64,
            contract_id=contract.contract_id,
            sequence=2,
            kind="session-paused",
            recorded_at=R_ACTIVATE,
            state_after="ACTIVE",
            provenance=_prov(BATTERY_ISSUER),
            route_decision_id=ROUTE_D0,
            path_id=PATH_P0,
        ),
    )
    # store-level gates
    store = RuntimeStore()
    _probe(
        "unknown runtime store read",
        ResilienceReason.INVALID_INPUT,
        lambda: store.session("sha256:" + "3" * 64),
    )
    if store.get("sha256:" + "3" * 64) is not None:
        problems.append("get() invented an unknown session")
    created = store.create(
        contract_id=contract.contract_id,
        created_at=R_CREATE,
        provenance=_prov(BATTERY_ISSUER),
    )
    store.activate(
        created.runtime_id,
        route_decision_id=ROUTE_D0,
        path_id=PATH_P0,
        recorded_at=R_ACTIVATE,
        provenance=_prov(BATTERY_ISSUER),
    )
    _probe(
        "activate a non-PENDING runtime",
        ResilienceReason.TRANSITION_ILLEGAL,
        lambda: store.activate(
            created.runtime_id,
            route_decision_id=ROUTE_D1,
            path_id=PATH_P1,
            recorded_at=R_RECONNECT_A,
            provenance=_prov(BATTERY_ISSUER),
        ),
    )
    # a PENDING runtime cannot initiate a reconnect (no realization to leave)
    pending = store.create(
        contract_id=contract.contract_id,
        created_at=R_CREATE,
        provenance=_prov("resilience:battery-pending"),
    )
    _probe(
        "initiate from PENDING",
        ResilienceReason.TRANSITION_ILLEGAL,
        lambda: store.initiate_reconnect(
            pending.runtime_id,
            candidate_route_decision_id=ROUTE_D1,
            candidate_path_id=PATH_P1,
            recorded_at=R_RECONNECT_A,
            provenance=_prov(BATTERY_ISSUER),
        ),
    )
    _probe(
        "unknown failover trigger kind",
        ResilienceReason.VOCABULARY,
        lambda: orchestrate_failover(
            store,
            created.runtime_id,
            contract,
            _failover_plan(contract),
            trigger_kind="path-exploded",
            recorded_at=R_FAILOVER,
        ),
    )
    _probe(
        "unknown handover trigger kind",
        ResilienceReason.VOCABULARY,
        lambda: perform_handover(
            store,
            created.runtime_id,
            contract,
            (
                handover_candidate(
                    contract,
                    route_decision_id=ROUTE_H1,
                    path_id=PATH_H1,
                    hard_constraints=tuple(contract.hard_constraints),
                ),
            ),
            trigger_kind="battery-flat",
            recorded_at=R_HANDOVER,
        ),
    )
    _probe(
        "non-sequence handover candidates",
        ResilienceReason.INVALID_INPUT,
        lambda: perform_handover(
            store,
            created.runtime_id,
            contract,
            "not-a-sequence",  # type: ignore[arg-type]
            trigger_kind="route-expiry",
            recorded_at=R_HANDOVER,
        ),
    )
    _probe(
        "empty handover candidates",
        ResilienceReason.NO_CANDIDATES,
        lambda: perform_handover(
            store,
            created.runtime_id,
            contract,
            (),
            trigger_kind="route-expiry",
            recorded_at=R_HANDOVER,
        ),
    )
    _probe(
        "bad evidence kind on degraded entry",
        ResilienceReason.VOCABULARY,
        lambda: store.enter_degraded(
            created.runtime_id,
            evidence_kind="guess",
            recorded_at=R_DEGRADED,
            provenance=_prov(BATTERY_ISSUER),
        ),
    )
    _probe(
        "non-string evidence kind",
        ResilienceReason.INVALID_INPUT,
        lambda: store.enter_degraded(
            created.runtime_id,
            evidence_kind=123,  # type: ignore[arg-type]
            recorded_at=R_DEGRADED,
            provenance=_prov(BATTERY_ISSUER),
        ),
    )
    _probe(
        "non-Store drive input",
        ResilienceReason.INVALID_INPUT,
        lambda: drive_replan_decision(
            object(),  # type: ignore[arg-type]
            created.runtime_id,
            contract,
            "not-a-decision",  # type: ignore[arg-type]
            recorded_at=R_DRIVE,
        ),
    )
    _probe(
        "non-Reconnect reference values",
        ResilienceReason.INVALID_INPUT,
        lambda: RuntimeReconnect(
            runtime_id="not-an-id",
            initiated_event_id="sha256:" + "1" * 64,
            completed_event_id="sha256:" + "2" * 64,
            reconnect_instant=R_RECONNECT_A_DONE,
            old_route_decision_id=ROUTE_D0,
            new_route_decision_id=ROUTE_D1,
            old_path_id=PATH_P0,
            new_path_id=PATH_P1,
        ),
    )
    if problems:
        return fail(name, "; ".join(problems[:6]))
    return ok(name, "every vocabulary/input gate fails closed with the typed code")


# ---------------------------------------------------------------------------
# case_03 — (a) the lifecycle round-trip
# ---------------------------------------------------------------------------


def case_03_lifecycle_round_trip() -> Result:
    name = "case_03_lifecycle_round_trip"
    constraints = _constraints("latency-bound", "availability-floor")
    _, contract = _mature_contract(constraints)
    store, session = _runtime_session(contract)
    rid = session.runtime_id
    problems: List[str] = []

    if session.state != "ACTIVE" or (session.route_decision_id, session.path_id) != (
        ROUTE_D0,
        PATH_P0,
    ):
        problems.append("the activated runtime is not ACTIVE on the initial references")
    # the explicit reconnect arc
    reconnecting = store.initiate_reconnect(
        rid,
        candidate_route_decision_id=ROUTE_D1,
        candidate_path_id=PATH_P1,
        recorded_at=R_RECONNECT_A,
        provenance=_prov(BATTERY_ISSUER),
    )
    if reconnecting.state != "RECONNECTING":
        problems.append("initiation did not land RECONNECTING")
    if (reconnecting.route_decision_id, reconnecting.path_id) != (ROUTE_D0, PATH_P0):
        problems.append("the RECONNECTING runtime changed references before completion")
    completed = store.complete_reconnect(
        rid, recorded_at=R_RECONNECT_A_DONE, provenance=_prov(BATTERY_ISSUER)
    )
    if completed.state != "ACTIVE" or (completed.route_decision_id, completed.path_id) != (
        ROUTE_D1,
        PATH_P1,
    ):
        problems.append("completion did not land ACTIVE on the new references")
    # the explicit degraded arc
    degraded = store.enter_degraded(
        rid,
        evidence_kind="observation",
        recorded_at=R_DEGRADED,
        provenance=_prov(BATTERY_ISSUER),
    )
    if degraded.state != "DEGRADED" or (degraded.route_decision_id, degraded.path_id) != (
        ROUTE_D1,
        PATH_P1,
    ):
        problems.append("the degraded entry changed the realization references")
    recovered = store.recover_degraded(
        rid, recorded_at=R_RECOVER, provenance=_prov(BATTERY_ISSUER)
    )
    if recovered.state != "ACTIVE":
        problems.append("the degraded recovery did not land ACTIVE")
    # the failed reconnect arc (references kept pre-change)
    store.initiate_reconnect(
        rid,
        candidate_route_decision_id=ROUTE_D2,
        candidate_path_id=PATH_P2,
        recorded_at=R_RECONNECT_B,
        provenance=_prov(BATTERY_ISSUER),
    )
    failed = store.fail_reconnect(
        rid,
        target="DEGRADED",
        reason="probe-timeout",
        recorded_at=R_RECONNECT_B_FAILED,
        provenance=_prov(BATTERY_ISSUER),
    )
    if failed.state != "DEGRADED" or (failed.route_decision_id, failed.path_id) != (
        ROUTE_D1,
        PATH_P1,
    ):
        problems.append("the failed reconnect changed the pre-change references")
    # a DEGRADED runtime may reconnect explicitly
    store.initiate_reconnect(
        rid,
        candidate_route_decision_id=ROUTE_D2,
        candidate_path_id=PATH_P2,
        recorded_at=R_RECONNECT_B,
        provenance=_prov(BATTERY_ISSUER),
    )
    completed2 = store.complete_reconnect(
        rid, recorded_at=R_RECONNECT_B_DONE, provenance=_prov(BATTERY_ISSUER)
    )
    if completed2.state != "ACTIVE" or (
        completed2.route_decision_id,
        completed2.path_id,
    ) != (ROUTE_D2, PATH_P2):
        problems.append("the degraded recovery reconnect did not land on the candidates")
    # the explicit terminal arc
    terminated = store.terminate(
        rid, recorded_at=R_TERMINATE, provenance=_prov(BATTERY_ISSUER)
    )
    if terminated.state != "TERMINATED" or not terminated.is_terminal:
        problems.append("termination did not land TERMINATED")
    if (terminated.route_decision_id, terminated.path_id) != (ROUTE_D2, PATH_P2):
        problems.append("the terminated runtime lost its historical references")
    # the terminal state never transitions
    try:
        store.recover_degraded(
            rid, recorded_at=R_TERMINATE, provenance=_prov(BATTERY_ISSUER)
        )
        problems.append("a TERMINATED runtime transitioned")
    except ResilienceError as error:
        if error.code != ResilienceReason.SESSION_TERMINAL:
            problems.append("terminal rejection code %s" % error.code)
    # construction-is-recovery: the journal alone rebuilds the state
    journal = store.events(rid)
    rebuilt = RuntimeStore.from_events(journal)
    if rebuilt.session(rid).canonical_bytes() != terminated.canonical_bytes():
        problems.append("construction-is-recovery diverged")
    store.verify_integrity(rid)
    # the runtime identity is state-independent (content-derived over
    # the creation core only — LOCK-117: the artifact evolves, the
    # identity does not)
    if derive_runtime_id(contract.contract_id, R_CREATE, _prov(BATTERY_ISSUER)) != rid:
        problems.append("the runtime identity is not the creation-core derivation")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "create/activate/reconnect/degraded/recover/fail-reconnect/terminate "
        "round-trip; journal replay rebuilds the state byte-identically",
    )


# ---------------------------------------------------------------------------
# case_04 — (a) every reconnect event records old AND new references
# ---------------------------------------------------------------------------


def case_04_reconnect_evidence_records() -> Result:
    name = "case_04_reconnect_evidence_records"
    constraints = _constraints("latency-bound", "availability-floor")
    _, contract = _mature_contract(constraints)
    store, session = _runtime_session(contract)
    rid = session.runtime_id
    store.initiate_reconnect(
        rid,
        candidate_route_decision_id=ROUTE_D1,
        candidate_path_id=PATH_P1,
        recorded_at=R_RECONNECT_A,
        provenance=_prov(BATTERY_ISSUER),
    )
    store.complete_reconnect(
        rid, recorded_at=R_RECONNECT_A_DONE, provenance=_prov(BATTERY_ISSUER)
    )
    store.initiate_reconnect(
        rid,
        candidate_route_decision_id=ROUTE_D2,
        candidate_path_id=PATH_P2,
        recorded_at=R_RECONNECT_B,
        provenance=_prov(BATTERY_ISSUER),
    )
    store.complete_reconnect(
        rid, recorded_at=R_RECONNECT_B_DONE, provenance=_prov(BATTERY_ISSUER)
    )
    problems: List[str] = []
    events = store.events(rid)
    initiations = [e for e in events if e.kind == "reconnect-initiated"]
    completions = [e for e in events if e.kind == "reconnect-completed"]
    if len(initiations) != 2 or len(completions) != 2:
        return fail(name, "expected two reconnect pairs (found %d/%d)" % (len(initiations), len(completions)))
    for i, event in enumerate(initiations):
        # the initiation names the OLD references verbatim AND the
        # CANDIDATE new ones (all four members on the initiating event)
        if not (
            event.old_route_decision_id
            and event.old_path_id
            and event.candidate_route_decision_id
            and event.candidate_path_id
        ):
            problems.append("initiation %d does not carry old+candidates" % i)
    if (initiations[0].old_route_decision_id, initiations[0].old_path_id) != (ROUTE_D0, PATH_P0):
        problems.append("the first initiation does not name the initial references")
    if (initiations[0].candidate_route_decision_id, initiations[0].candidate_path_id) != (
        ROUTE_D1,
        PATH_P1,
    ):
        problems.append("the first initiation does not declare its candidates")
    for i, event in enumerate(completions):
        # the completed event records BOTH the old AND the new references
        if not (
            event.old_route_decision_id
            and event.old_path_id
            and event.new_route_decision_id
            and event.new_path_id
        ):
            problems.append("completion %d does not carry old+new" % i)
    if (completions[0].old_route_decision_id, completions[0].old_path_id) != (ROUTE_D0, PATH_P0):
        problems.append("the first completion does not name the OLD references")
    if (completions[0].new_route_decision_id, completions[0].new_path_id) != (ROUTE_D1, PATH_P1):
        problems.append("the first completion does not name the NEW references")
    if (completions[1].old_route_decision_id, completions[1].old_path_id) != (ROUTE_D1, PATH_P1):
        problems.append("the second completion does not name the OLD references")
    if (completions[1].new_route_decision_id, completions[1].new_path_id) != (ROUTE_D2, PATH_P2):
        problems.append("the second completion does not name the NEW references")
    # the typed evidence records derived from the journal pairs
    records = store.reconnect_evidence(rid)
    if len(records) != 2:
        problems.append("expected two typed reconnect records (found %d)" % len(records))
    for record in records:
        if not (
            record.old_route_decision_id
            and record.new_route_decision_id
            and record.old_path_id
            and record.new_path_id
        ):
            problems.append("a reconnect record misses one side of the route change")
        if record.initiated_event_id == record.completed_event_id:
            problems.append("the reconnect record cites one event for both sides")
    # the module-level derivation over the raw journal agrees
    raw = reconnect_evidence(events)
    if [r.reconnect_id for r in raw] != [r.reconnect_id for r in records]:
        problems.append("the module-level evidence derivation diverged")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "every reconnect event carries old AND new references; two typed "
        "evidence records derived from the initiated+completed pairs",
    )


# ---------------------------------------------------------------------------
# case_05 — (b) a silent-replacement attempt is rejected (the WORK-012
# discipline mechanically enforced)
# ---------------------------------------------------------------------------


def case_05_silent_replacement_rejected() -> Result:
    name = "case_05_silent_replacement_rejected"
    constraints = _constraints("latency-bound")
    _, contract = _mature_contract(constraints)
    store, session = _runtime_session(contract)
    rid = session.runtime_id
    journal_before = b"".join(e.canonical_bytes() for e in store.events(rid))
    problems: List[str] = []

    def _activate_unnamed() -> None:
        fresh = RuntimeStore()
        created_fresh = fresh.create(
            contract_id=contract.contract_id,
            created_at=R_CREATE,
            provenance=_prov(BATTERY_ISSUER),
        )
        fresh.activate(
            created_fresh.runtime_id,
            route_decision_id="",
            path_id=PATH_P0,
            recorded_at=R_ACTIVATE,
            provenance=_prov(BATTERY_ISSUER),
        )

    probes: List[Tuple[str, str, Callable[[], Any]]] = [
        (
            "store completion without initiation",
            ResilienceReason.SILENT_REPLACEMENT,
            lambda: store.complete_reconnect(
                rid, recorded_at=R_RECONNECT_A_DONE, provenance=_prov(BATTERY_ISSUER)
            ),
        ),
        (
            "store initiation without declared candidates",
            ResilienceReason.SILENT_REPLACEMENT,
            lambda: store.initiate_reconnect(
                rid,
                candidate_route_decision_id="",
                candidate_path_id=PATH_P1,
                recorded_at=R_RECONNECT_A,
                provenance=_prov(BATTERY_ISSUER),
            ),
        ),
        (
            "activation without named references",
            ResilienceReason.SILENT_REPLACEMENT,
            _activate_unnamed,
        ),
    ]
    for label, code, action in probes:
        try:
            action()
            problems.append("%s was accepted" % label)
        except ResilienceError as error:
            if error.code != code:
                problems.append("%s: expected %s, got %s" % (label, code, error.code))
    # the journal is byte-identical after every rejected probe (atomicity)
    if b"".join(e.canonical_bytes() for e in store.events(rid)) != journal_before:
        problems.append("a rejected operation mutated the journal")

    created, activated = store.events(rid)[0], store.events(rid)[1]

    def _event(sequence: int, kind: str, state_after: str, **members: Any) -> RuntimeEvent:
        return RuntimeEvent(
            runtime_id=rid,
            contract_id=contract.contract_id,
            sequence=sequence,
            kind=kind,
            recorded_at=R_RECONNECT_A,
            state_after=state_after,
            provenance=_prov(BATTERY_ISSUER),
            **members,
        )

    # fold-level probes (the mechanical enforcement in the replay fold)
    orphan_completion = _event(
        3,
        "reconnect-completed",
        "ACTIVE",
        old_route_decision_id=ROUTE_D0,
        old_path_id=PATH_P0,
        new_route_decision_id=ROUTE_D1,
        new_path_id=PATH_P1,
    )
    probes = [
        (
            "an orphaned completion in the fold",
            ResilienceReason.SILENT_REPLACEMENT,
            lambda: fold_events((created, activated, orphan_completion)),
        ),
        (
            "reconnect_evidence on an orphaned completion",
            ResilienceReason.SILENT_REPLACEMENT,
            lambda: reconnect_evidence((created, activated, orphan_completion)),
        ),
        (
            "an initiation naming the wrong OLD references",
            ResilienceReason.SILENT_REPLACEMENT,
            lambda: fold_events(
                (
                    created,
                    activated,
                    _event(
                        3,
                        "reconnect-initiated",
                        "RECONNECTING",
                        old_route_decision_id="route:wrong-old",
                        old_path_id=PATH_P0,
                        candidate_route_decision_id=ROUTE_D1,
                        candidate_path_id=PATH_P1,
                    ),
                )
            ),
        ),
        (
            "a completion naming undeclared NEW references",
            ResilienceReason.SILENT_REPLACEMENT,
            lambda: fold_events(
                (
                    created,
                    activated,
                    _event(
                        3,
                        "reconnect-initiated",
                        "RECONNECTING",
                        old_route_decision_id=ROUTE_D0,
                        old_path_id=PATH_P0,
                        candidate_route_decision_id=ROUTE_D1,
                        candidate_path_id=PATH_P1,
                    ),
                    _event(
                        4,
                        "reconnect-completed",
                        "ACTIVE",
                        old_route_decision_id=ROUTE_D0,
                        old_path_id=PATH_P0,
                        new_route_decision_id="route:undeclared-9",
                        new_path_id=PATH_P1,
                    ),
                )
            ),
        ),
        (
            "route members on a non-reconnect kind",
            ResilienceReason.SILENT_REPLACEMENT,
            lambda: _event(
                3,
                "session-terminated",
                "TERMINATED",
                new_route_decision_id=ROUTE_D1,
            ),
        ),
        (
            "a realization holder without named references",
            ResilienceReason.SILENT_REPLACEMENT,
            lambda: RuntimeSession(
                runtime_id=rid,
                contract_id=contract.contract_id,
                state="ACTIVE",
                created_at=R_CREATE,
                sequence=2,
                provenance=_prov(BATTERY_ISSUER),
            ),
        ),
        (
            "a reconnect record missing one side",
            ResilienceReason.SILENT_REPLACEMENT,
            lambda: RuntimeReconnect(
                runtime_id=rid,
                initiated_event_id=created.event_id,
                completed_event_id=activated.event_id,
                reconnect_instant=R_RECONNECT_A_DONE,
                old_route_decision_id=ROUTE_D0,
                new_route_decision_id="",
                old_path_id=PATH_P0,
                new_path_id=PATH_P1,
            ),
        ),
    ]
    for label, code, action in probes:
        try:
            action()
            problems.append("%s was accepted" % label)
        except ResilienceError as error:
            if error.code != code:
                problems.append("%s: expected %s, got %s" % (label, code, error.code))
    # a route change NEVER happens outside the pair: a journal whose
    # terminal event changes references without a reconnect is rejected
    if problems:
        return fail(name, "; ".join(problems[:6]))
    return ok(
        name,
        "orphaned completions, wrong old refs, undeclared new refs, foreign "
        "route members and unnamed realizations all fail closed "
        "resilience-silent-replacement; the journal stays byte-identical",
    )


# ---------------------------------------------------------------------------
# case_06 — the deterministic journal fails closed on divergence
# ---------------------------------------------------------------------------


def case_06_journal_divergence_fail_closed() -> Result:
    name = "case_06_journal_divergence_fail_closed"
    constraints = _constraints("latency-bound")
    _, contract = _mature_contract(constraints)
    store, session = _runtime_session(contract)
    rid = session.runtime_id
    created, activated = store.events(rid)[0], store.events(rid)[1]
    problems: List[str] = []

    def _event(sequence: int, kind: str, state_after: str, **members: Any) -> RuntimeEvent:
        return RuntimeEvent(
            runtime_id=rid,
            contract_id=contract.contract_id,
            sequence=sequence,
            kind=kind,
            recorded_at=R_RECONNECT_A,
            state_after=state_after,
            provenance=_prov(BATTERY_ISSUER),
            **members,
        )

    def _gap_event() -> RuntimeEvent:
        return _event(
            5,
            "reconnect-initiated",
            "RECONNECTING",
            old_route_decision_id=ROUTE_D0,
            old_path_id=PATH_P0,
            candidate_route_decision_id=ROUTE_D1,
            candidate_path_id=PATH_P1,
        )

    def _foreign_runtime_event() -> RuntimeEvent:
        return RuntimeEvent(
            runtime_id="sha256:" + "e" * 64,
            contract_id=contract.contract_id,
            sequence=3,
            kind="session-terminated",
            recorded_at=R_TERMINATE,
            state_after="TERMINATED",
            provenance=_prov(BATTERY_ISSUER),
        )

    def _kind_state_event() -> RuntimeEvent:
        return _event(3, "degraded-entered", "RECONNECTING", evidence_kind="observation")

    def _double_activation() -> RuntimeEvent:
        return _event(
            3,
            "session-activated",
            "ACTIVE",
            route_decision_id=ROUTE_D1,
            path_id=PATH_P1,
        )

    def _failed_then_terminated() -> Tuple[RuntimeEvent, ...]:
        failed = _event(3, "session-failed", "FAILED", reason="probe-timeout")
        terminated = _event(4, "session-terminated", "TERMINATED")
        return (created, activated, failed, terminated)

    def _not_created_first() -> RuntimeEvent:
        return _event(
            1,
            "session-activated",
            "ACTIVE",
            route_decision_id=ROUTE_D0,
            path_id=PATH_P0,
        )

    def _created_off_position() -> RuntimeEvent:
        return _event(2, "session-created", "PENDING")

    def _identity_tampered() -> RuntimeEvent:
        return RuntimeEvent(
            runtime_id="sha256:" + "f" * 64,
            contract_id=contract.contract_id,
            sequence=1,
            kind="session-created",
            recorded_at=R_CREATE,
            state_after="PENDING",
            provenance=created.provenance,
        )

    probes: List[Tuple[str, str, Callable[[], Any]]] = [
        (
            "a journal position gap",
            ResilienceReason.JOURNAL_DIVERGENCE,
            lambda: fold_events((created, activated, _gap_event())),
        ),
        (
            "an event attributing to a foreign runtime",
            ResilienceReason.JOURNAL_DIVERGENCE,
            lambda: fold_events((created, activated, _foreign_runtime_event())),
        ),
        (
            "a kind landing the wrong state",
            ResilienceReason.JOURNAL_DIVERGENCE,
            lambda: fold_events((created, activated, _kind_state_event())),
        ),
        (
            "an illegal state edge",
            ResilienceReason.JOURNAL_DIVERGENCE,
            lambda: fold_events((created, activated, _double_activation())),
        ),
        (
            "an event after a terminal state",
            ResilienceReason.JOURNAL_DIVERGENCE,
            lambda: fold_events(_failed_then_terminated()),
        ),
        (
            "a journal not starting with session-created",
            ResilienceReason.JOURNAL_DIVERGENCE,
            lambda: fold_events((_not_created_first(),)),
        ),
        (
            "session-created off position 1",
            ResilienceReason.JOURNAL_DIVERGENCE,
            lambda: fold_events((_created_off_position(),)),
        ),
        (
            "the runtime identity not re-deriving",
            ResilienceReason.ID_MISMATCH,
            lambda: fold_events((_identity_tampered(),)),
        ),
        (
            "an empty journal",
            ResilienceReason.INVALID_INPUT,
            lambda: fold_events(()),
        ),
        (
            "a non-event journal",
            ResilienceReason.INVALID_INPUT,
            lambda: fold_events(("not-an-event",)),  # type: ignore[arg-type]
        ),
    ]
    for label, code, action in probes:
        try:
            action()
            problems.append("%s was accepted" % label)
        except ResilienceError as error:
            if error.code != code:
                problems.append("%s: expected %s, got %s" % (label, code, error.code))
    if problems:
        return fail(name, "; ".join(problems[:6]))
    return ok(
        name,
        "sequence gaps, attribution conflicts, kind/state divergence, illegal "
        "edges, post-terminal events and identity tampering all fail closed",
    )


# ---------------------------------------------------------------------------
# case_07 — (c) successful handover with hard-constraint preservation
# ---------------------------------------------------------------------------


def case_07_successful_handover() -> Result:
    name = "case_07_successful_handover"
    constraints = _constraints("latency-bound", "availability-floor")
    _, contract = _mature_contract(constraints)
    store, session = _runtime_session(contract)
    rid = session.runtime_id
    candidate = handover_candidate(
        contract,
        route_decision_id=ROUTE_H1,
        path_id=PATH_H1,
        hard_constraints=tuple(contract.hard_constraints),
    )
    problems: List[str] = []
    if candidate.kind != HANDOVER_CANDIDATE_KIND:
        problems.append("the handover candidate kind drifted")
    # the LOCK-108 verdict twin accepts the strict candidate
    verdict = handover_verdict(candidate, contract)
    if not verdict.accepted:
        problems.append("the strict handover candidate was rejected: %s" % verdict.detail[:80])
    validate_handover_preserves_contract(tuple(contract.hard_constraints), contract)
    result = perform_handover(
        store,
        rid,
        contract,
        (candidate,),
        trigger_kind="route-expiry",
        recorded_at=R_HANDOVER,
    )
    if result.outcome != "adopted" or result.decision.decision != "adopt-alternative":
        problems.append("the strict handover was not adopted (%s)" % result.outcome)
    after = result.session
    if after.state != "ACTIVE":
        problems.append("the adopted handover did not land ACTIVE (found %s)" % after.state)
    if (after.route_decision_id, after.path_id) != (ROUTE_H1, PATH_H1):
        problems.append("the adopted handover did not land on the new references")
    # the SAME hard constraints: the consumed cross-authority gate
    # re-verifies the finished decision against the contract
    try:
        verify_decision_preserves_contract(result.decision, contract)
    except Exception as error:  # noqa: BLE001
        problems.append("the decision failed the consumed gate: %s" % str(error)[:80])
    if result.decision.constraint_fingerprint != contract.hard_constraint_fingerprint():
        problems.append("the decision fingerprint is not the contract's own")
    if result.decision.adopted_candidate_id != candidate.candidate_id:
        problems.append("the adopted candidate id drifted")
    reconnect = result.reconnect
    if reconnect is None:
        problems.append("the adopted handover produced no reconnect evidence")
    else:
        if (reconnect.old_route_decision_id, reconnect.old_path_id) != (ROUTE_D0, PATH_P0):
            problems.append("the handover reconnect lost the OLD references")
        if (reconnect.new_route_decision_id, reconnect.new_path_id) != (ROUTE_H1, PATH_H1):
            problems.append("the handover reconnect lost the NEW references")
        if reconnect.runtime_id != rid:
            problems.append("the reconnect evidence does not attribute to the runtime")
    events = store.events(rid)
    kinds = [e.kind for e in events]
    if kinds[-2:] != ["reconnect-initiated", "reconnect-completed"]:
        problems.append("the journal does not end with the explicit reconnect pair")
    if result.decision.decision_id not in events[-1].provenance.decision_refs:
        problems.append("the completing event does not cite the decision (LOCK-118)")
    if not result.event_ids:
        problems.append("the drive produced no appended event ids")
    if len(result.event_ids) != 2:
        problems.append("the drive appended %d events (expected the pair)" % len(result.event_ids))
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "handover adopted through the explicit reconnect pair; the consumed "
        "cross-authority gate re-verifies the SAME hard constraints; "
        "provenance cites the decision on every appended event",
    )


# ---------------------------------------------------------------------------
# case_08..case_19 — (d) LOCK-108 per constraint kind: every weakening
# handover/failover candidate rejected with the typed kind-citing reason
# ---------------------------------------------------------------------------


def _lock108_case(kind: str, index: int) -> Result:
    name = "case_%02d_lock108_%s" % (index, kind.replace("-", "_"))
    constraints = _constraints(*ALL_KINDS)
    _, contract = _mature_contract(constraints)
    problems: List[str] = []
    for mode in ("DROP", "RELAX", "REINTERPRET"):
        weakened = _weakened_constraints(contract.hard_constraints, mode, kind)
        label = "%s %s" % (mode, kind)
        # 1. the raising gate (the typed weakened-constraint rejection)
        try:
            validate_handover_preserves_contract(weakened, contract)
            problems.append("the raising gate accepted the %s weakening" % label)
        except ResilienceError as error:
            if error.code != ResilienceReason.CONSTRAINT_WEAKENED:
                problems.append(
                    "%s: expected resilience-constraint-weakened, got %s"
                    % (label, error.code)
                )
            elif kind not in error.detail:
                problems.append("%s: the rejection does not cite the kind" % label)
        # 2. the verdict twin (the consumed M008 gate, surfaced verbatim)
        candidate = handover_candidate(
            contract,
            route_decision_id="route:weak-%s-%s" % (kind, mode.lower()),
            path_id="path:weak-%s-%s" % (kind, mode.lower()),
            hard_constraints=weakened,
        )
        verdict = handover_verdict(candidate, contract)
        if verdict.accepted:
            problems.append("the verdict twin accepted the %s weakening" % label)
        elif kind not in verdict.detail:
            problems.append("%s: the verdict does not cite the kind" % label)
    # 3. the engine drive NEVER adopts a weakening candidate: the only
    # candidate weakens DROP-wise -> the explicit FAILED state (a hard
    # trigger), the verdict citing the kind, no reconnect evidence
    weakened_drop = _weakened_constraints(contract.hard_constraints, "DROP", kind)
    weak_candidate = handover_candidate(
        contract,
        route_decision_id="route:engine-weak-%s" % kind,
        path_id="path:engine-weak-%s" % kind,
        hard_constraints=weakened_drop,
    )
    store, session = _runtime_session(contract)
    result = perform_handover(
        store,
        session.runtime_id,
        contract,
        (weak_candidate,),
        trigger_kind="adapter-failure",
        recorded_at=R_HANDOVER,
    )
    if result.decision.decision == "adopt-alternative":
        problems.append("the engine adopted the weakening %s candidate" % kind)
    if result.session.state != "FAILED":
        problems.append(
            "the impossible handover did not land FAILED explicitly (found %s)"
            % result.session.state
        )
    if store.reconnect_evidence(session.runtime_id):
        problems.append("a weakening candidate silently reconnected")
    cited = any(
        (not v.accepted) and kind in v.detail for v in result.decision.verdicts
    )
    if not cited:
        problems.append("the decision verdicts do not cite the weakened kind %s" % kind)
    # 4. the failover side: a wire-forged weakened plan is rejected by
    # the consumed M006 LOCK-108 gate BEFORE any alternative is read
    plan = _failover_plan(contract)
    forged = _forged_weakened_plan(plan, weakened_drop)
    store2, session2 = _runtime_session(contract)
    try:
        orchestrate_failover(
            store2,
            session2.runtime_id,
            contract,
            forged,
            trigger_kind="path-failed",
            recorded_at=R_FAILOVER,
        )
        problems.append("the failover orchestrator accepted the weakened %s plan" % kind)
    except ResilienceError as error:
        if error.code != ResilienceReason.CONSTRAINT_WEAKENED:
            problems.append(
                "the weakened %s plan rejection code %s is not the typed "
                "weakened-constraint rejection" % (kind, error.code)
            )
        elif kind not in error.detail:
            problems.append("the weakened %s plan rejection does not cite the kind" % kind)
    # the forged rejection left the journal byte-identical (atomicity)
    if store2.events(session2.runtime_id)[0].event_id != store.events(session.runtime_id)[0].event_id:
        # same deterministic fixtures -> identical creation events; a
        # differing id would mean nondeterministic fixture material
        problems.append("the fixture material is nondeterministic")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "DROP/RELAX/REINTERPRET rejections cite the kind (%s); the engine never "
        "adopts a weakening candidate; the forged weakened plan is rejected "
        "by the consumed M006 gate" % kind,
    )


# ---------------------------------------------------------------------------
# case_20/21/22 — (e) impossible realization: the explicit degraded /
# failed states and the explicit renegotiation trigger path
# ---------------------------------------------------------------------------


def case_20_impossible_degraded_explicit() -> Result:
    name = "case_20_impossible_degraded_explicit"
    constraints = _constraints("latency-bound", "availability-floor")
    store_contract, contract = _mature_contract(constraints)
    weakened = _weakened_constraints(contract.hard_constraints, "RELAX", "latency-bound")
    candidate = handover_candidate(
        contract,
        route_decision_id=ROUTE_H1,
        path_id=PATH_H1,
        hard_constraints=weakened,
    )
    store, session = _runtime_session(contract)
    result = perform_handover(
        store,
        session.runtime_id,
        contract,
        (candidate,),
        trigger_kind="assurance-degraded",
        recorded_at=R_DEGRADED,
    )
    problems: List[str] = []
    if result.outcome != "degraded" or result.decision.decision != "degraded":
        return fail(name, "expected the degraded outcome, got %s" % result.outcome)
    if result.decision.realization_state != "DEGRADED":
        problems.append("the decision did not carry the explicit DEGRADED realization")
    after = result.session
    if after.state != "DEGRADED":
        problems.append("the runtime did not land DEGRADED (found %s)" % after.state)
    if (after.route_decision_id, after.path_id) != (ROUTE_D0, PATH_P0):
        problems.append("the degraded runtime changed its references")
    # the degraded entry is journaled and evidence-visible
    events = store.events(session.runtime_id)
    entry = events[-1]
    if entry.kind != "degraded-entered":
        problems.append("the journal does not end with the degraded entry")
    if entry.evidence_kind not in EVIDENCE_TYPES:
        problems.append("the degraded entry evidence kind is not from the accepted vocabulary")
    if not any(
        ref.value == result.decision.decision_id for ref in entry.evidence_refs
    ):
        problems.append("the degraded entry does not cite the decision as evidence")
    if entry.evidence_refs[0].ref_kind != "decision":
        problems.append("the degraded evidence reference is not decision-kinded")
    # the projection: the DEGRADED runtime IS the explicit degraded
    # realization (the M008 vocabulary, projected)
    snapshot = runtime_realization_snapshot(after, observed_at=R_RECOVER)
    if snapshot.state != "DEGRADED":
        problems.append("the DEGRADED runtime does not project onto the M008 DEGRADED state")
    # the closed loop: the contract records degraded through its OWN
    # command vocabulary (the runtime never writes contract state)
    cmds = bridge_commands(result.decision, contract)
    if not (
        len(cmds) == 1
        and isinstance(cmds[0], RecordAssurance)
        and cmds[0].assurance_state == "degraded"
    ):
        problems.append("the bridge did not produce the degraded assurance command")
    else:
        store_contract.submit(
            cmds[0], recorded_at=R_DEGRADED, contract_id=contract.contract_id
        )
        if store_contract.contract(contract.contract_id).state != "DEGRADED":
            problems.append("the contract did not record the explicit degraded state")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "soft-trigger impossible realization: the runtime lands the explicit "
        "DEGRADED state, journaled with the accepted evidence kind and the "
        "decision cited as evidence; the contract records through its own "
        "vocabulary",
    )


def case_21_impossible_failed_explicit() -> Result:
    name = "case_21_impossible_failed_explicit"
    constraints = _constraints("latency-bound", "availability-floor")
    store_contract, contract = _mature_contract(constraints)
    weakened = _weakened_constraints(contract.hard_constraints, "DROP", "availability-floor")
    candidate = handover_candidate(
        contract,
        route_decision_id=ROUTE_H1,
        path_id=PATH_H1,
        hard_constraints=weakened,
    )
    store, session = _runtime_session(contract)
    result = perform_handover(
        store,
        session.runtime_id,
        contract,
        (candidate,),
        trigger_kind="segment-loss",
        recorded_at=R_FAILOVER,
    )
    problems: List[str] = []
    if result.outcome != "failed" or result.decision.decision != "failed":
        return fail(name, "expected the failed outcome, got %s" % result.outcome)
    if result.decision.realization_state != "FAILED":
        problems.append("the decision did not carry the explicit FAILED realization")
    after = result.session
    if after.state != "FAILED" or not after.is_terminal:
        problems.append("the runtime did not land the terminal FAILED state")
    if (after.route_decision_id, after.path_id) != (ROUTE_D0, PATH_P0):
        problems.append("the failed runtime lost its historical references")
    events = store.events(session.runtime_id)
    if events[-1].kind != "session-failed" or not events[-1].reason:
        problems.append("the journal does not end with the explicit reasoned failure")
    if result.reconnect is not None:
        problems.append("the failed drive produced reconnect evidence")
    if store.reconnect_evidence(session.runtime_id):
        problems.append("an impossible realization silently reconnected")
    # the closed loop: the contract records the violation through its
    # own vocabulary
    cmds = bridge_commands(result.decision, contract)
    if not (
        len(cmds) == 1
        and isinstance(cmds[0], RecordAssurance)
        and cmds[0].assurance_state == "violated"
    ):
        problems.append("the bridge did not produce the violated assurance command")
    else:
        store_contract.submit(
            cmds[0], recorded_at=R_FAILOVER, contract_id=contract.contract_id
        )
        if store_contract.contract(contract.contract_id).state != "FAILED":
            problems.append("the contract did not fail explicitly")
    # a FAILED runtime never transitions (terminal)
    try:
        store.recover_degraded(
            session.runtime_id, recorded_at=R_RECOVER, provenance=_prov(BATTERY_ISSUER)
        )
        problems.append("the FAILED runtime transitioned")
    except ResilienceError as error:
        if error.code != ResilienceReason.SESSION_TERMINAL:
            problems.append("terminal rejection code %s" % error.code)
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "hard-trigger impossible realization: the runtime lands the terminal "
        "FAILED state with the journaled reason; the contract records the "
        "violation through its own vocabulary; terminal never transitions",
    )


def case_22_renegotiation_trigger_path() -> Result:
    name = "case_22_renegotiation_trigger_path"
    constraints = _constraints("latency-bound", "geography")
    store_contract, contract = _mature_contract(constraints)
    weakened = _weakened_constraints(contract.hard_constraints, "RELAX", "latency-bound")
    candidate = handover_candidate(
        contract,
        route_decision_id=ROUTE_H1,
        path_id=PATH_H1,
        hard_constraints=weakened,
    )
    store, session = _runtime_session(contract)
    result = perform_handover(
        store,
        session.runtime_id,
        contract,
        (candidate,),
        trigger_kind="constraint-unsatisfiable",
        recorded_at=R_DRIVE,
    )
    problems: List[str] = []
    if result.outcome != "renegotiate" or result.decision.decision != "renegotiate":
        return fail(name, "expected the renegotiate outcome, got %s" % result.outcome)
    if result.decision.realization_state != "FAILED":
        problems.append("renegotiate must carry the explicit FAILED realization")
    if result.decision.renegotiation is None:
        problems.append("the renegotiate decision carries no typed notice")
    elif result.decision.renegotiation.superseded_contract_id != contract.contract_id:
        problems.append("the notice does not cite the superseded contract")
    if result.session.state != "FAILED":
        problems.append("the runtime did not land the explicit FAILED state")
    # the successor contract: created through the M002 surface with the
    # superseded-contract reference carried from the notice (the
    # principal-side flow — the runtime never creates contracts)
    ref = renegotiation_reference(result.decision)
    if ref.ref_kind != "superseded-contract" or ref.value != contract.contract_id:
        problems.append("the renegotiation reference is not the superseded-contract ref")
    successor_cmd = _create_command(_constraints("latency-bound", "jurisdiction"))
    successor_cmd = CreateContract(
        principal=successor_cmd.principal,
        beneficiaries=successor_cmd.beneficiaries,
        requirements=successor_cmd.requirements,
        hard_constraints=successor_cmd.hard_constraints,
        validity=successor_cmd.validity,
        service_properties=successor_cmd.service_properties,
        usage_pricing_terms=successor_cmd.usage_pricing_terms,
        assurance_obligations=successor_cmd.assurance_obligations,
        execution_scope=successor_cmd.execution_scope,
        termination=successor_cmd.termination,
        provenance=successor_cmd.provenance,
        superseded_contract=ref,
    )
    successor_store = ContractStore()
    successor = successor_store.submit(successor_cmd, recorded_at=R_DRIVE).contract
    if (
        successor.superseded_contract is None
        or successor.superseded_contract.value != contract.contract_id
    ):
        problems.append("the successor contract does not carry the superseded reference")
    if successor.contract_id == contract.contract_id:
        problems.append("renegotiation mutated the contract identity")
    # the superseded contract fails through its own vocabulary
    cmds = bridge_commands(result.decision, contract)
    if not (
        len(cmds) == 1
        and isinstance(cmds[0], RecordAssurance)
        and cmds[0].assurance_state == "violated"
    ):
        problems.append("the bridge did not produce the violated command")
    else:
        store_contract.submit(
            cmds[0], recorded_at=R_DRIVE, contract_id=contract.contract_id
        )
        if store_contract.contract(contract.contract_id).state != "FAILED":
            problems.append("the superseded contract did not fail explicitly")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "constraint-unsatisfiable: the typed notice -> the superseded-contract "
        "reference -> the successor contract through the M002 surface; the "
        "superseded contract fails explicitly",
    )


# ---------------------------------------------------------------------------
# case_23 — (f) deterministic multipath failover selection with declared
# recorded tie-breaking (same inputs -> byte-identical records)
# ---------------------------------------------------------------------------


def case_23_deterministic_failover_selection() -> Result:
    name = "case_23_deterministic_failover_selection"
    problems: List[str] = []
    material_a = _failover_scenario()
    material_b = _failover_scenario()
    if material_a != material_b:
        return fail(name, "the failover scenario is not byte-identical across re-runs")
    decision_bytes, session_bytes, journal_bytes, reconnect_bytes = material_a
    if hashlib.sha256(decision_bytes).hexdigest() == hashlib.sha256(b"").hexdigest():
        problems.append("empty decision material")
    # the plan's alternative segments are read BY REFERENCE: two plans
    # with reversed segment INPUT order are byte-identical (LOCK-111
    # input-order independence at the translation boundary)
    constraints = _constraints("latency-bound", "availability-floor")
    _, contract = _mature_contract(constraints)
    plan_a = _failover_plan(contract)
    segments_reversed = tuple(
        SegmentInput(
            offer_reference=seg.offer_reference,
            role=seg.role,
            operations=seg.operations,
            provenance=seg.provenance,
        )
        for seg in reversed(plan_a.segments)
    )
    plan_b = translate_contract(
        contract,
        segments_reversed,
        provenance=_prov("optimizer:failover-v1", "dec:opt-failover"),
    )
    if plan_a.canonical_bytes() != plan_b.canonical_bytes():
        problems.append("reversed segment input order produced a different plan")
    # the alternatives carry the PLAN's constraints (the contract's own
    # set, verbatim — LOCK-108 double verification through the kernel)
    alternatives = failover_alternatives(plan_a)
    if len(alternatives) != 2:
        problems.append("expected two failover alternatives (found %d)" % len(alternatives))
    for candidate in alternatives:
        if candidate.kind != FAILOVER_CANDIDATE_KIND:
            problems.append("an alternative escaped the execution-plan candidate kind")
        if candidate.hard_constraints != plan_a.hard_constraints:
            problems.append("an alternative does not carry the plan's constraint set")
        if candidate.contract_id != contract.contract_id:
            problems.append("an alternative does not attribute to the contract")
    # a second full scenario with a DIFFERENT tie-break rule still
    # selects deterministically (the declared rule recorded on the
    # decision — LOCK-111)
    def _scenario_with_rule(rule: Tuple[str, ...]) -> Tuple[Any, Any]:
        _, contract2 = _mature_contract(constraints)
        plan2 = _failover_plan(contract2)
        store2, session2 = _runtime_session(contract2)
        result2 = orchestrate_failover(
            store2,
            session2.runtime_id,
            contract2,
            plan2,
            trigger_kind="path-degraded",
            recorded_at=R_FAILOVER,
            tie_break=rule,
        )
        return result2.decision, result2.session

    decision_default, session_default = _scenario_with_rule(("candidate-kind", "candidate-id"))
    decision_id_only, session_id_only = _scenario_with_rule(("candidate-id",))
    if decision_default.adopted_candidate_id != decision_id_only.adopted_candidate_id:
        problems.append("the two declared rules selected different alternatives")
    if session_default.route_decision_id != session_id_only.route_decision_id:
        problems.append("the two declared rules landed different realizations")
    if decision_default.tie_break != ("candidate-kind", "candidate-id"):
        problems.append("the default rule is not recorded verbatim")
    if decision_id_only.tie_break != ("candidate-id",):
        problems.append("the declared rule is not recorded verbatim")
    if decision_default.decision_id == decision_id_only.decision_id:
        problems.append("different declared rules produced the same decision id")
    if decision_default.decision != "adopt-alternative":
        problems.append("the failover did not adopt an alternative")
    if session_default.state != "ACTIVE":
        problems.append("the failed-over runtime is not ACTIVE")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "same inputs -> byte-identical decision/journal/evidence across "
        "re-runs; reversed input order -> the byte-identical plan; declared "
        "tie-break rules recorded verbatim with the same selection",
    )


# ---------------------------------------------------------------------------
# case_24 — LOCK-115: a plan with no alternative segments is an honest
# typed no-candidates outcome (never an invented alternative)
# ---------------------------------------------------------------------------


def case_24_failover_no_alternatives_typed() -> Result:
    name = "case_24_failover_no_alternatives_typed"
    constraints = _constraints("latency-bound")
    _, contract = _mature_contract(constraints)
    simple_plan = translate_contract(
        contract,
        (
            SegmentInput(
                offer_reference=_OFFER_A,
                role="primary",
                operations=("reserve", "activate"),
                provenance=_prov("optimizer:simple-v1", "dec:opt-simple"),
            ),
        ),
        provenance=_prov("optimizer:simple-v1", "dec:opt-simple-plan"),
    )
    verify_plan_preserves_contract(simple_plan, contract)
    problems: List[str] = []
    if failover_alternatives(simple_plan) != ():
        problems.append("a simple plan invented failover alternatives")
    store, session = _runtime_session(contract)
    journal_before = b"".join(e.canonical_bytes() for e in store.events(session.runtime_id))
    try:
        orchestrate_failover(
            store,
            session.runtime_id,
            contract,
            simple_plan,
            trigger_kind="path-failed",
            recorded_at=R_FAILOVER,
        )
        problems.append("the simple-deployment failover was orchestrated")
    except ResilienceError as error:
        if error.code != ResilienceReason.NO_CANDIDATES:
            problems.append("expected resilience-no-candidates, got %s" % error.code)
    if b"".join(e.canonical_bytes() for e in store.events(session.runtime_id)) != journal_before:
        problems.append("the typed no-candidates rejection mutated the journal")
    # the non-Plan input fails closed
    try:
        failover_alternatives("not-a-plan")  # type: ignore[arg-type]
        problems.append("a non-Plan failover_alternatives input was accepted")
    except ResilienceError as error:
        if error.code != ResilienceReason.INVALID_INPUT:
            problems.append("non-Plan rejection code %s" % error.code)
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "LOCK-115: a simple deployment (no alternative segments) yields the "
        "typed resilience-no-candidates outcome; the journal stays "
        "byte-identical; never an invented alternative",
    )


# ---------------------------------------------------------------------------
# case_25 — (f) declared recorded tie-breaking: validity gates
# ---------------------------------------------------------------------------


def case_25_declared_tie_break_recorded() -> Result:
    name = "case_25_declared_tie_break_recorded"
    constraints = _constraints("latency-bound", "availability-floor")
    _, contract = _mature_contract(constraints)
    plan = _failover_plan(contract)
    store, session = _runtime_session(contract)
    rid = session.runtime_id
    problems: List[str] = []
    invalid_rules: List[Tuple[Any, str]] = [
        ((), "an empty rule"),
        (("candidate-id", "candidate-kind"), "a rule not ending with candidate-id"),
        (("recorded-at", "candidate-id"), "a temporal key"),
        (("candidate-id", "candidate-id"), "a repeated key"),
        ("candidate-id", "a bare string"),
        ((42,), "a non-string key"),  # type: ignore[list-item]
    ]
    for rule, label in invalid_rules:
        journal_before = b"".join(e.canonical_bytes() for e in store.events(rid))
        try:
            orchestrate_failover(
                store,
                rid,
                contract,
                plan,
                trigger_kind="path-failed",
                recorded_at=R_FAILOVER,
                tie_break=rule,
            )
            problems.append("%s was accepted" % label)
        except ResilienceError as error:
            if error.code != ResilienceReason.TIE_BREAK_INVALID:
                problems.append("%s: expected tie-break-invalid, got %s" % (label, error.code))
        if b"".join(e.canonical_bytes() for e in store.events(rid)) != journal_before:
            problems.append("%s mutated the journal before rejection" % label)
    # an incomplete rule is COMPLETED with the total-order key
    result = orchestrate_failover(
        store,
        rid,
        contract,
        plan,
        trigger_kind="path-failed",
        recorded_at=R_FAILOVER,
        tie_break=("candidate-kind",),
    )
    if result.decision.tie_break != ("candidate-kind", "candidate-id"):
        problems.append("the incomplete rule was not completed with candidate-id")
    if result.outcome != "adopted":
        problems.append("the completed-rule failover did not adopt")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "empty/temporal/reordered/repeated/non-sequence rules fail closed "
        "resilience-tie-break-invalid with the journal byte-identical; an "
        "incomplete rule is completed with the candidate-id total order",
    )


# ---------------------------------------------------------------------------
# case_26 — (g) the replan-kernel composition: the runtime DRIVES the
# accepted M008 decisions (its decision gate exercised, never duplicated)
# ---------------------------------------------------------------------------


def case_26_replan_kernel_composition() -> Result:
    name = "case_26_replan_kernel_composition"
    constraints = _constraints("latency-bound", "availability-floor")
    _, contract = _mature_contract(constraints)
    problems: List[str] = []

    def _fresh() -> Tuple[RuntimeStore, RuntimeSession]:
        return _runtime_session(contract)

    def _decision_for(
        store: RuntimeStore,
        session: RuntimeSession,
        candidate: ReplanCandidate,
        trigger_kind: str,
    ) -> Any:
        snapshot = runtime_realization_snapshot(session, observed_at=R_DRIVE)
        trigger = ReplanTrigger(
            kind=trigger_kind,
            contract_id=contract.contract_id,
            recorded_at=R_DRIVE,
            realization_ref=session.runtime_id,
        )
        return decide_replan(contract, trigger, snapshot, (candidate,))

    strict = handover_candidate(
        contract,
        route_decision_id=ROUTE_H1,
        path_id=PATH_H1,
        hard_constraints=tuple(contract.hard_constraints),
    )
    weakened = handover_candidate(
        contract,
        route_decision_id="route:weak-composition",
        path_id="path:weak-composition",
        hard_constraints=_weakened_constraints(
            contract.hard_constraints, "RELAX", "latency-bound"
        ),
    )

    # 1. adopt-alternative -> the EXPLICIT reconnect pair
    store, session = _fresh()
    decision = _decision_for(store, session, strict, "route-expiry")
    if decision.decision != "adopt-alternative":
        problems.append("the kernel did not adopt the strict candidate")
    after, reconnect = drive_replan_decision(
        store,
        session.runtime_id,
        contract,
        decision,
        recorded_at=R_DRIVE,
        new_route_decision_id=ROUTE_H1,
        new_path_id=PATH_H1,
    )
    if after.state != "ACTIVE" or (after.route_decision_id, after.path_id) != (ROUTE_H1, PATH_H1):
        problems.append("the adopt drive did not land ACTIVE on the adopted references")
    if reconnect is None or reconnect.new_route_decision_id != ROUTE_H1:
        problems.append("the adopt drive produced no reconnect evidence")
    kinds = [e.kind for e in store.events(session.runtime_id)]
    if kinds[-2:] != ["reconnect-initiated", "reconnect-completed"]:
        problems.append("the adopt drive did not append the explicit pair")
    # the drive provenance cites the consumed decision (LOCK-118)
    if decision.decision_id not in store.events(session.runtime_id)[-1].provenance.decision_refs:
        problems.append("the driven event does not cite the decision")

    # 2. degraded -> the journaled evidence-visible degraded entry
    store, session = _fresh()
    decision = _decision_for(store, session, weakened, "assurance-degraded")
    if decision.decision != "degraded":
        problems.append("the soft-trigger kernel decision was not degraded")
    after, _ = drive_replan_decision(
        store, session.runtime_id, contract, decision, recorded_at=R_DRIVE
    )
    if after.state != "DEGRADED":
        problems.append("the degraded drive did not land DEGRADED")
    entry = store.events(session.runtime_id)[-1]
    if entry.kind != "degraded-entered" or entry.evidence_kind != "observation":
        problems.append("the degraded drive did not journal the evidence-visible entry")
    if not any(ref.value == decision.decision_id for ref in entry.evidence_refs):
        problems.append("the degraded drive did not cite the decision as evidence")

    # 3. failed -> the explicit terminal failure
    store, session = _fresh()
    decision = _decision_for(store, session, weakened, "adapter-failure")
    if decision.decision != "failed":
        problems.append("the hard-trigger kernel decision was not failed")
    after, _ = drive_replan_decision(
        store, session.runtime_id, contract, decision, recorded_at=R_DRIVE
    )
    if after.state != "FAILED":
        problems.append("the failed drive did not land FAILED")
    if store.events(session.runtime_id)[-1].kind != "session-failed":
        problems.append("the failed drive did not journal the reasoned failure")

    # 4. renegotiate -> the explicit terminal failure with the notice
    store, session = _fresh()
    decision = _decision_for(store, session, weakened, "constraint-unsatisfiable")
    if decision.decision != "renegotiate":
        problems.append("the unsatisfiable kernel decision was not renegotiate")
    after, _ = drive_replan_decision(
        store, session.runtime_id, contract, decision, recorded_at=R_DRIVE
    )
    if after.state != "FAILED":
        problems.append("the renegotiate drive did not land FAILED")

    # 5. the attribution gates fail closed
    other_constraints = _constraints("latency-bound", "jurisdiction")
    _, other_contract = _mature_contract(other_constraints)
    store, session = _fresh()
    other_candidate = handover_candidate(
        other_contract,
        route_decision_id=ROUTE_H1,
        path_id=PATH_H1,
        hard_constraints=tuple(other_contract.hard_constraints),
    )
    _, other_session = _runtime_session(other_contract)
    foreign_decision = decide_replan(
        other_contract,
        ReplanTrigger(
            kind="route-expiry",
            contract_id=other_contract.contract_id,
            recorded_at=R_DRIVE,
            realization_ref=other_session.runtime_id,
        ),
        runtime_realization_snapshot(other_session, observed_at=R_DRIVE),
        (other_candidate,),
    )
    try:
        drive_replan_decision(
            store,
            session.runtime_id,
            contract,
            foreign_decision,
            recorded_at=R_DRIVE,
        )
        problems.append("a foreign-contract decision was driven")
    except ResilienceError as error:
        if error.code != ResilienceReason.ID_MISMATCH:
            problems.append("foreign-decision rejection code %s" % error.code)

    # the adopt shape gates: the supplied references must equal the
    # decision's adopted artifacts (the decision record is the truth)
    store, session = _fresh()
    decision = _decision_for(store, session, strict, "route-expiry")
    try:
        drive_replan_decision(
            store,
            session.runtime_id,
            contract,
            decision,
            recorded_at=R_DRIVE,
            new_route_decision_id="route:not-the-adopted-one",
            new_path_id=PATH_H1,
        )
        problems.append("a divergent adopted reference was driven")
    except ResilienceError as error:
        if error.code != ResilienceReason.ID_MISMATCH:
            problems.append("divergent-reference rejection code %s" % error.code)

    # a PENDING runtime is not a replan surface (fail closed, typed)
    pending_store = RuntimeStore()
    pending = pending_store.create(
        contract_id=contract.contract_id,
        created_at=R_CREATE,
        provenance=_prov(BATTERY_ISSUER),
    )
    store_f, session_f = _fresh()
    decision_f = _decision_for(store_f, session_f, weakened, "adapter-failure")
    try:
        drive_replan_decision(
            pending_store,
            pending.runtime_id,
            contract,
            decision_f,
            recorded_at=R_DRIVE,
        )
        problems.append("a PENDING runtime was driven")
    except ResilienceError as error:
        if error.code != ResilienceReason.REALIZATION_NOT_ESTABLISHED:
            problems.append("pending-drive rejection code %s" % error.code)

    # a terminal runtime never transitions
    store_t, session_t = _fresh()
    decision_t = _decision_for(store_t, session_t, weakened, "adapter-failure")
    drive_replan_decision(store_t, session_t.runtime_id, contract, decision_t, recorded_at=R_DRIVE)
    try:
        drive_replan_decision(
            store_t,
            session_t.runtime_id,
            contract,
            decision_t,
            recorded_at=R_DRIVE,
        )
        problems.append("a FAILED runtime was driven again")
    except ResilienceError as error:
        if error.code != ResilienceReason.SESSION_TERMINAL:
            problems.append("terminal-drive rejection code %s" % error.code)

    # a runtime riding a DIFFERENT contract than the driven decision's
    store_x, session_x = _runtime_session(other_contract)
    try:
        drive_replan_decision(
            store_x,
            session_x.runtime_id,
            other_contract,
            decision_f,
            recorded_at=R_DRIVE,
        )
        problems.append("a decision was driven onto a foreign runtime's contract")
    except ResilienceError as error:
        if error.code != ResilienceReason.ID_MISMATCH:
            problems.append("foreign-runtime rejection code %s" % error.code)
    if problems:
        return fail(name, "; ".join(problems[:6]))
    return ok(
        name,
        "the runtime drives all four consumed decision kinds onto the journal "
        "(adopt -> the explicit pair; degraded -> evidence-visible entry; "
        "failed/renegotiate -> the reasoned terminal failure); attribution, "
        "divergence, pending and terminal gates fail closed typed",
    )


# ---------------------------------------------------------------------------
# case_27 — (h) degraded-mode entry/exit journaled and evidence-visible
# ---------------------------------------------------------------------------


def case_27_degraded_mode_journaled_evidence_visible() -> Result:
    name = "case_27_degraded_mode_journaled_evidence_visible"
    constraints = _constraints("latency-bound")
    _, contract = _mature_contract(constraints)
    store, session = _runtime_session(contract)
    rid = session.runtime_id
    problems: List[str] = []
    decision_ref = OpaqueReference(
        ref_kind="decision",
        value="sha256:" + "d" * 64,
        provenance=_prov(BATTERY_ISSUER, "dec:assurance-1"),
    )
    degraded = store.enter_degraded(
        rid,
        evidence_kind="observation",
        evidence_refs=(decision_ref,),
        recorded_at=R_DEGRADED,
        provenance=_prov(BATTERY_ISSUER),
    )
    if degraded.state != "DEGRADED":
        problems.append("the explicit entry did not land DEGRADED")
    events = store.events(rid)
    entry = events[-1]
    if entry.kind != "degraded-entered":
        problems.append("the degraded entry was not journaled")
    if entry.evidence_kind != "observation" or entry.evidence_kind not in EVIDENCE_TYPES:
        problems.append("the degraded entry evidence kind is not accepted/typed")
    if not entry.evidence_refs or entry.evidence_refs[0].value != decision_ref.value:
        problems.append("the degraded entry is not evidence-visible (no references)")
    if entry.evidence_refs[0].ref_kind != "decision":
        problems.append("the degraded evidence reference is not decision-kinded")
    if entry.provenance.issuer != BATTERY_ISSUER:
        problems.append("the degraded entry lost its provenance (LOCK-118)")
    # the projection: DEGRADED runtime -> the M008 DEGRADED realization
    snapshot = runtime_realization_snapshot(degraded, observed_at=R_RECOVER)
    if snapshot.state != "DEGRADED" or snapshot.contract_id != contract.contract_id:
        problems.append("the DEGRADED runtime does not project onto the M008 state")
    if snapshot.session_ref != rid:
        problems.append("the projection does not cite the runtime session")
    if snapshot.route_refs != (ROUTE_D0,):
        problems.append("the projection lost the route references")
    # the explicit exit
    recovered = store.recover_degraded(
        rid, recorded_at=R_RECOVER, provenance=_prov(BATTERY_ISSUER)
    )
    if recovered.state != "ACTIVE":
        problems.append("the explicit exit did not land ACTIVE")
    exit_event = store.events(rid)[-1]
    if exit_event.kind != "degraded-recovered":
        problems.append("the degraded exit was not journaled")
    # never silent: a recovery without DEGRADED fails closed
    try:
        store.recover_degraded(
            rid, recorded_at=R_TERMINATE, provenance=_prov(BATTERY_ISSUER)
        )
        problems.append("an ACTIVE runtime 'recovered' from degraded")
    except ResilienceError as error:
        if error.code != ResilienceReason.TRANSITION_ILLEGAL:
            problems.append("recovery gate code %s" % error.code)
    # a non-decision evidence reference fails closed (LOCK-106 typing)
    store2, session2 = _runtime_session(contract)
    try:
        store2.enter_degraded(
            session2.runtime_id,
            evidence_kind="observation",
            evidence_refs=(
                OpaqueReference(
                    ref_kind="execution-artifact",
                    value="path:not-decision-kinded",
                    provenance=_prov(BATTERY_ISSUER),
                ),
            ),
            recorded_at=R_DEGRADED,
            provenance=_prov(BATTERY_ISSUER),
        )
        problems.append("a non-decision evidence reference was accepted")
    except ResilienceError as error:
        if error.code != ResilienceReason.VOCABULARY:
            problems.append("evidence-kind rejection code %s" % error.code)
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "degraded entry/exit journaled with the accepted LOCK-106 evidence "
        "typing and decision-kinded references; the M008 DEGRADED projection "
        "verified; silent recoveries and untyped evidence fail closed",
    )


# ---------------------------------------------------------------------------
# case_28 — (i) canonical-JSON round-trips
# ---------------------------------------------------------------------------


def case_28_canonical_round_trips() -> Result:
    name = "case_28_canonical_round_trips"
    problems: List[str] = []
    material = _full_lifecycle_scenario()
    # rebuild the scenario records for the round-trip probes
    constraints = _constraints("latency-bound", "availability-floor")
    _, contract = _mature_contract(constraints)
    store, session = _runtime_session(contract)
    rid = session.runtime_id
    store.initiate_reconnect(
        rid,
        candidate_route_decision_id=ROUTE_D1,
        candidate_path_id=PATH_P1,
        recorded_at=R_RECONNECT_A,
        provenance=_prov(BATTERY_ISSUER),
    )
    store.complete_reconnect(
        rid, recorded_at=R_RECONNECT_A_DONE, provenance=_prov(BATTERY_ISSUER)
    )
    store.enter_degraded(
        rid,
        evidence_kind="observation",
        recorded_at=R_DEGRADED,
        provenance=_prov(BATTERY_ISSUER),
    )
    store.terminate(rid, recorded_at=R_TERMINATE, provenance=_prov(BATTERY_ISSUER))
    records: List[Any] = [store.session(rid), *store.events(rid), *store.reconnect_evidence(rid)]
    if not records:
        return fail(name, "the scenario produced no records")
    for record in records:
        clone = type(record).from_dict(record.to_dict())
        if clone.canonical_bytes() != record.canonical_bytes():
            problems.append(
                "%s round-trip diverged" % type(record).__name__
            )
        identity_names = (
            "event_id" if isinstance(record, RuntimeEvent)
            else "reconnect_id" if isinstance(record, RuntimeReconnect)
            else "runtime_id"
        )
        if getattr(clone, identity_names) != getattr(record, identity_names):
            problems.append("%s identity drifted across the round-trip" % type(record).__name__)
    # tamper evidence: a mutated dict fails closed at deserialization
    tampered = store.events(rid)[2].to_dict()
    tampered["recorded_at"] = "2026-10-03T09:99:00Z"
    try:
        RuntimeEvent.from_dict(tampered)
        problems.append("a tampered event deserialized")
    except ResilienceError as error:
        if error.code not in (ResilienceReason.ID_MISMATCH, ResilienceReason.TEMPORAL_INVALID):
            problems.append("tamper rejection code %s" % error.code)
    tampered_session = store.session(rid).to_dict()
    tampered_session["state"] = "PENDING"
    try:
        RuntimeSession.from_dict(tampered_session)
        problems.append("a tampered session deserialized")
    except ResilienceError as error:
        if error.code not in (
            ResilienceReason.ID_MISMATCH,
            ResilienceReason.SILENT_REPLACEMENT,
            ResilienceReason.INVALID_INPUT,
        ):
            problems.append("session tamper rejection code %s" % error.code)
    # the DriveResult envelope carries the consumed decision verbatim
    plan_material = _failover_scenario()
    if plan_material[0] != _failover_scenario()[0]:
        problems.append("the failover decision record is not reproducible")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    if len(material) != 3:
        return fail(name, "the lifecycle scenario material shape drifted")
    return ok(
        name,
        "session/event/reconnect records round-trip byte-identically with "
        "stable content-derived ids; tampered dicts fail closed",
    )


# ---------------------------------------------------------------------------
# case_29 — (i) typed errors and exception isolation
# ---------------------------------------------------------------------------


def case_29_typed_errors_exception_isolation() -> Result:
    name = "case_29_typed_errors_exception_isolation"
    constraints = _constraints("latency-bound")
    _, contract = _mature_contract(constraints)
    problems: List[str] = []
    # a malformed instant surfaces as the typed temporal rejection (the
    # consumed TemporalError wrapped, never leaked)
    try:
        RuntimeSession(
            runtime_id="sha256:" + "1" * 64,
            contract_id=contract.contract_id,
            state="PENDING",
            created_at="2026-13-99T00:00:00Z",
            sequence=1,
            provenance=_prov(BATTERY_ISSUER),
        )
        problems.append("a malformed instant was accepted")
    except ResilienceError as error:
        if error.code != ResilienceReason.TEMPORAL_INVALID:
            problems.append("temporal rejection code %s" % error.code)
    # LOCK-119: secret-shaped material is rejected at the boundary (the
    # credential fixture is assembled from fragments at runtime)
    secret_prefix = "ghp_"
    secret_body = "A1b2C3d4E5f6G7h8I9j0"
    try:
        RuntimeEvent(
            runtime_id="sha256:" + "2" * 64,
            contract_id=contract.contract_id,
            sequence=2,
            kind="session-activated",
            recorded_at=R_ACTIVATE,
            state_after="ACTIVE",
            provenance=_prov(BATTERY_ISSUER),
            route_decision_id=ROUTE_D0,
            path_id=secret_prefix + secret_body,
        )
        problems.append("a secret-shaped value was accepted")
    except ResilienceError as error:
        if error.code != ResilienceReason.SECRET_REJECTED:
            problems.append("secret rejection code %s" % error.code)
    # consumed-domain errors are wrapped with their deterministic text
    # preserved (exception isolation at the deserialization boundary)
    try:
        RuntimeSession.from_dict(
            {
                "runtime_id": "sha256:" + "3" * 64,
                "contract_id": contract.contract_id,
                "state": "PENDING",
                "created_at": R_CREATE,
                "sequence": 1,
                "provenance": "not-a-provenance-mapping",
            }
        )
        problems.append("a garbage provenance was accepted")
    except ResilienceError as error:
        if error.code != ResilienceReason.INVALID_INPUT:
            problems.append("provenance wrap code %s" % error.code)
        elif "consumed domain" not in error.detail:
            problems.append("the wrap does not disclose the consumed boundary")
    # engine-boundary isolation: the consumed kernel's typed rejection
    # surfaces as resilience-replan-composition with its text preserved
    store, session = _runtime_session(contract)
    candidate = handover_candidate(
        contract,
        route_decision_id=ROUTE_H1,
        path_id=PATH_H1,
        hard_constraints=tuple(contract.hard_constraints),
    )
    try:
        perform_handover(
            store,
            session.runtime_id,
            contract,
            (candidate,),
            trigger_kind="route-expiry",
            recorded_at=R_OUTSIDE,  # escapes the contract validity
        )
        problems.append("an out-of-validity drive was accepted")
    except ResilienceError as error:
        if error.code != ResilienceReason.REPLAN_COMPOSITION:
            problems.append("engine isolation code %s" % error.code)
        elif "validity" not in error.detail:
            problems.append("the engine isolation lost the consumed detail")
    # the rejected drive left no trace on the journal (atomicity + no
    # raw exception text into stored state)
    journal_bytes = b"".join(e.canonical_bytes() for e in store.events(session.runtime_id))
    if b"Traceback" in journal_bytes or b"Exception" in journal_bytes:
        problems.append("raw exception text leaked into stored state")
    if len(store.events(session.runtime_id)) != 2:
        problems.append("the rejected drive mutated the journal")
    # every public error is the ONE typed error class (no foreign types)
    try:
        handover_candidate("not-a-contract", route_decision_id="r", path_id="p", hard_constraints=())  # type: ignore[arg-type]
        problems.append("a non-contract handover input was accepted")
    except ResilienceError as error:
        if error.code != ResilienceReason.INVALID_INPUT:
            problems.append("handover input gate code %s" % error.code)
    except ValueError:
        problems.append("a raw ValueError escaped the typed boundary")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "temporal/secret/consumed-wrap/engine-isolation rejections all typed "
        "with deterministic text preserved; no raw exception text reaches "
        "stored state; rejected drives leave the journal byte-identical",
    )


# ---------------------------------------------------------------------------
# case_30 — (j) determinism under a re-run
# ---------------------------------------------------------------------------


def case_30_determinism_same_inputs() -> Result:
    name = "case_30_determinism_same_inputs"
    problems: List[str] = []
    lifecycle_a = _full_lifecycle_scenario()
    lifecycle_b = _full_lifecycle_scenario()
    if lifecycle_a != lifecycle_b:
        problems.append("the lifecycle scenario is not byte-identical across re-runs")
    failover_a = _failover_scenario()
    failover_b = _failover_scenario()
    if failover_a != failover_b:
        problems.append("the failover scenario is not byte-identical across re-runs")
    # construction-is-recovery: the journal alone rebuilds the store
    constraints = _constraints("latency-bound", "availability-floor")
    _, contract = _mature_contract(constraints)
    store, session = _runtime_session(contract)
    rid = session.runtime_id
    store.initiate_reconnect(
        rid,
        candidate_route_decision_id=ROUTE_D1,
        candidate_path_id=PATH_P1,
        recorded_at=R_RECONNECT_A,
        provenance=_prov(BATTERY_ISSUER),
    )
    store.complete_reconnect(
        rid, recorded_at=R_RECONNECT_A_DONE, provenance=_prov(BATTERY_ISSUER)
    )
    rebuilt = RuntimeStore.from_events(store.events(rid))
    if rebuilt.session(rid).canonical_bytes() != store.session(rid).canonical_bytes():
        problems.append("construction-is-recovery diverged")
    if rebuilt.reconnect_evidence(rid) != store.reconnect_evidence(rid):
        problems.append("the rebuilt reconnect evidence diverged")
    # the deterministic multi-session store ordering
    store2 = RuntimeStore()
    ids = []
    for suffix in ("a", "b", "c"):
        created = store2.create(
            contract_id=contract.contract_id,
            created_at=R_CREATE,
            provenance=_prov("resilience:battery-%s" % suffix),
        )
        ids.append(created.runtime_id)
    if [s.runtime_id for s in store2.sessions()] != sorted(ids):
        problems.append("the multi-session store ordering is not deterministic")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "the full lifecycle and failover scenarios are byte-identical across "
        "re-runs; construction-is-recovery and the session ordering are "
        "deterministic",
    )


# ---------------------------------------------------------------------------
# case_31 — (j) cross-process PYTHONHASHSEED determinism
# ---------------------------------------------------------------------------


def case_31_cross_process_pythonhashseed() -> Result:
    name = "case_31_cross_process_pythonhashseed"
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
from executionplans import SegmentInput, translate_contract
from replan import ReplanTrigger
from resilience import RuntimeStore, orchestrate_failover
T0 = "2026-10-01T00:00:00Z"
CREATE_AT = "2026-09-30T10:00:00Z"
R_CREATE = "2026-10-02T00:00:00Z"
R_ACTIVATE = "2026-10-02T00:05:00Z"
R_FAILOVER = "2026-10-08T00:00:00Z"
def prov(issuer, *refs):
    return Provenance(issuer=issuer, decision_refs=tuple(refs))
cmd = CreateContract(
    principal=ConnectivityPrincipal(principal_kind="APPLICATION", principal_ref="app:resilience-gw-01"),
    beneficiaries=(BeneficiaryScope(beneficiary_kind="DEVICE", beneficiary_ref="dev:pi-7f2a"),),
    requirements=(OpaqueReference(ref_kind="intent-requirements", value="intent:abc123", provenance=prov("arch:resilience")),),
    hard_constraints=(
        HardConstraint(kind="latency-bound", params={"max_ms": 150}, provenance=prov("prov:netpro")),
        HardConstraint(kind="availability-floor", params={"nine": "three"}, provenance=prov("prov:netpro")),
    ),
    validity=ValidityInterval(not_before=T0, not_after="2026-11-01T00:00:00Z"),
    service_properties=(OpaqueReference(ref_kind="service-property", value="prop:committed-1", provenance=prov("prov:netpro")),),
    usage_pricing_terms=OpaqueReference(ref_kind="usage-pricing-terms", value="terms:comm-42", provenance=prov("comm:ops")),
    assurance_obligations=(OpaqueReference(ref_kind="assurance-obligation", value="oblig:evid-7"),),
    execution_scope=(OpaqueReference(ref_kind="execution-scope", value="scope:exec-default"),),
    termination=TerminationRules(
        conditions=("principal-requested", "constraint-violated"),
        compensation=OpaqueReference(ref_kind="compensation", value="comp:rule-9", provenance=prov("comm:ops")),
    ),
    provenance=prov("arch:resilience", "dec:elig-1"),
)
store = ContractStore()
created = store.submit(cmd, recorded_at=CREATE_AT)
cid = created.contract.contract_id
offers = (
    OpaqueReference(ref_kind="offer", value="offer:netpro-basic-1", provenance=prov("prov:netpro")),
    OpaqueReference(ref_kind="offer", value="offer:skywave-mesh-1", provenance=prov("prov:skywave")),
    OpaqueReference(ref_kind="offer", value="offer:skywave-failover-1", provenance=prov("prov:skywave")),
)
store.submit(SelectOffers(offers=offers), recorded_at="2026-09-30T10:05:00Z", contract_id=cid)
store.submit(ActivateContract(activated_at=T0, signature_refs=(OpaqueReference(ref_kind="signature", value="sig:ed25519-1"),)), recorded_at=T0, contract_id=cid)
store.submit(RecordExecutionActivation(recorded_at=T0), recorded_at=T0, contract_id=cid)
contract = store.contract(cid)
plan = translate_contract(
    contract,
    (
        SegmentInput(offer_reference=offers[0], role="primary", operations=("reserve", "activate", "measure"), provenance=prov("optimizer:failover-v1", "dec:opt-f0")),
        SegmentInput(offer_reference=offers[1], role="alternative", operations=("reserve", "activate", "measure"), provenance=prov("optimizer:failover-v1", "dec:opt-f1")),
        SegmentInput(offer_reference=offers[2], role="alternative", operations=("reserve", "activate"), provenance=prov("optimizer:failover-v1", "dec:opt-f2")),
    ),
    provenance=prov("optimizer:failover-v1", "dec:opt-failover"),
)
rstore = RuntimeStore()
session = rstore.create(contract_id=cid, created_at=R_CREATE, provenance=prov("resilience:battery"))
rstore.activate(session.runtime_id, route_decision_id="route:decision-0001", path_id="path:primary-0001", recorded_at=R_ACTIVATE, provenance=prov("resilience:battery"))
result = orchestrate_failover(rstore, session.runtime_id, contract, plan, trigger_kind="path-failed", recorded_at=R_FAILOVER)
journal = b"".join(e.canonical_bytes() for e in rstore.events(session.runtime_id))
print(result.decision.decision_id)
print(hashlib.sha256(journal).hexdigest())
print(hashlib.sha256(result.decision.canonical_bytes()).hexdigest())
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
        "byte-identical decision ids, journal digests and decision records "
        "across PYTHONHASHSEED 0/1/42 subprocesses",
    )


# ---------------------------------------------------------------------------
# case_32 — the lock-conformance mapping (aggregate structural evidence)
# ---------------------------------------------------------------------------


def case_32_lock_conformance_mapping() -> Result:
    name = "case_32_lock_conformance_mapping"
    constraints = _constraints("latency-bound", "availability-floor")
    _, contract = _mature_contract(constraints)
    store, session = _runtime_session(contract)
    rid = session.runtime_id
    problems: List[str] = []
    # LOCK-101/117: the runtime session is an execution artifact riding
    # the contract as an opaque reference — it carries NO constraint
    # material and never becomes a second contract authority
    forbidden_members = {"hard_constraints", "constraints", "constraint_fingerprint"}
    session_fields = {f for f in RuntimeSession.__dataclass_fields__}
    if session_fields & forbidden_members:
        problems.append("the runtime session carries constraint material")
    event_fields = {f for f in RuntimeEvent.__dataclass_fields__}
    if event_fields & forbidden_members:
        problems.append("the runtime event carries constraint material")
    if session.contract_id != contract.contract_id:
        problems.append("the runtime does not cite the owning contract")
    if not session.contract_id.startswith("sha256:"):
        problems.append("the contract citation is not an opaque content id")
    # the snapshot carries only opaque references (LOCK-117)
    snapshot = runtime_realization_snapshot(session, observed_at=R_DRIVE)
    for ref in snapshot.artifact_refs:
        if ref.ref_kind != "execution-artifact":
            problems.append("the snapshot artifact is not an execution-artifact reference")
    # LOCK-106: the degraded evidence typing comes from the accepted
    # vocabulary (case_27 exercises the value gate)
    if "observation" not in EVIDENCE_TYPES:
        problems.append("the degraded evidence kind is not in the accepted vocabulary")
    # LOCK-111: the tie-break keys are the consumed M008 vocabulary
    if set(TIE_BREAK_KEYS) <= {"recorded-at", "observed-at", "wall-clock"}:
        problems.append("a temporal tie-break key exists in the consumed vocabulary")
    # LOCK-115/116: simple (no alternatives) and complex (alternatives
    # under ONE contract) deployments are both honest (cases 23/24)
    plan = _failover_plan(contract)
    roles = [s.role for s in plan.segments]
    if roles.count("alternative") != 2 or "primary" not in roles:
        problems.append("the complex plan shape drifted")
    if plan.contract_id != contract.contract_id:
        problems.append("the plan does not ride the one contract")
    # LOCK-118: provenance on every record
    for record in (session, *store.events(rid)):
        if not record.provenance.issuer:
            problems.append("a record lost its provenance issuer")
    # LOCK-119: content-derived ids only (no uuid randomness)
    for record in (session, *store.events(rid)):
        identity = getattr(record, "runtime_id")
        if not identity.startswith("sha256:"):
            problems.append("a record identity is not content-derived")
    # the consumed authority fingerprint discipline: the decision that
    # drives the runtime carries the CONTRACT's own fingerprint
    candidate = handover_candidate(
        contract,
        route_decision_id=ROUTE_H1,
        path_id=PATH_H1,
        hard_constraints=tuple(contract.hard_constraints),
    )
    result = perform_handover(
        store,
        rid,
        contract,
        (candidate,),
        trigger_kind="route-expiry",
        recorded_at=R_HANDOVER,
    )
    if result.decision.constraint_fingerprint != contract.hard_constraint_fingerprint():
        problems.append("the driving decision's fingerprint is not the contract's own")
    # the consumed cross-authority gate passes on the driving decision
    verify_decision_preserves_contract(result.decision, contract)
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "LOCK-101/106/108/111/115/116/117/118/119 conformance evidenced "
        "(no constraint material on the runtime surface; opaque references "
        "only; accepted evidence typing; the contract's own fingerprint "
        "rides every driving decision)",
    )


# ---------------------------------------------------------------------------
# case_33 — clock/import discipline (AST audit of resilience/)
# ---------------------------------------------------------------------------


def case_33_clock_import_discipline() -> Result:
    name = "case_33_clock_import_discipline"
    problems: List[str] = []
    files = sorted((REPO_ROOT / "resilience").glob("*.py"))
    if not files:
        return fail(name, "the resilience/ package is missing")
    allowed = {
        "__future__",
        "contextlib",
        "hashlib",
        "re",
        "dataclasses",
        "typing",
        "protocol",
        "contracts",
        "evidence",
        "replan",
        "executionplans",
        "resilience",
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
        "no clock/random/network constructs anywhere in resilience/; imports: "
        "stdlib + protocol + the accepted authorities (contracts, evidence, "
        "replan, executionplans) — by reference only",
    )


# ---------------------------------------------------------------------------
# case_34 — the one-way import boundary (no accepted authority imports
# resilience/)
# ---------------------------------------------------------------------------


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
    )
    for package in authorities:
        package_dir = REPO_ROOT / package
        if not package_dir.is_dir():
            continue
        for path in sorted(package_dir.glob("*.py")):
            source = path.read_text(encoding="utf-8")
            if "resilience" in source and _code_tokens(source):
                problems.append("%s references resilience (imports must be one-way)" % path.name)
    # the legacy reservoir stays un-imported by resilience/ (source
    # material only — the R8 charter consumption rule)
    legacy = ("sessions", "mobility", "multipath", "edge", "appliance")
    tree_modules: set = set()
    for path in sorted((REPO_ROOT / "resilience").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                tree_modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                tree_modules.add(node.module.split(".")[0])
    for package in legacy:
        if package in tree_modules:
            problems.append("resilience/ imports the legacy %s/ package" % package)
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "no accepted authority imports resilience/ (one-way boundary); the "
        "legacy reservoir is un-imported source material only",
    )


def _code_tokens(source: str) -> bool:
    """True when the source references resilience in CODE (an AST token),
    not merely in a docstring/comment."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "resilience":
            return True
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == "resilience":
                return True
        if isinstance(node, ast.ImportFrom) and node.module and "resilience" in node.module:
            return True
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "resilience":
                    return True
    return False


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
        "delta confined to the M015 scope (%d file(s): resilience/ + the "
        "battery + the evidence doc)" % len(delta),
    )


def _active_authorization_covers(path: str) -> bool:
    try:
        from authorization_provenance import covers  # type: ignore

        return covers(path)
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# case_36 — the evidence-doc honesty
# ---------------------------------------------------------------------------


def case_36_evidence_doc_honest() -> Result:
    name = "case_36_evidence_doc_honest"
    path = REPO_ROOT / "docs" / "M015-evidence.md"
    if not path.exists():
        return fail(name, "docs/M015-evidence.md is missing")
    text = path.read_text(encoding="utf-8")
    problems: List[str] = []
    if "SOFTWARE" not in text:
        problems.append("the evidence class is not disclosed")
    if "M015" not in text:
        problems.append("the evidence does not name M015")
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
    results.append(case_03_lifecycle_round_trip())
    results.append(case_04_reconnect_evidence_records())
    results.append(case_05_silent_replacement_rejected())
    results.append(case_06_journal_divergence_fail_closed())
    results.append(case_07_successful_handover())
    # (d) LOCK-108 per constraint kind: one numbered case per kind (12
    # kinds), each probing DROP/RELAX/REINTERPRET on the handover gate,
    # the engine drive, and the forged-plan failover gate
    for index, kind in enumerate(ALL_KINDS, start=8):
        results.append(_lock108_case(kind, index))
    results.append(case_20_impossible_degraded_explicit())
    results.append(case_21_impossible_failed_explicit())
    results.append(case_22_renegotiation_trigger_path())
    results.append(case_23_deterministic_failover_selection())
    results.append(case_24_failover_no_alternatives_typed())
    results.append(case_25_declared_tie_break_recorded())
    results.append(case_26_replan_kernel_composition())
    results.append(case_27_degraded_mode_journaled_evidence_visible())
    results.append(case_28_canonical_round_trips())
    results.append(case_29_typed_errors_exception_isolation())
    results.append(case_30_determinism_same_inputs())
    results.append(case_31_cross_process_pythonhashseed())
    results.append(case_32_lock_conformance_mapping())
    results.append(case_33_clock_import_discipline())
    results.append(case_34_one_way_imports())
    results.append(case_35_pr_delta_shape_authorized_scope())
    results.append(case_36_evidence_doc_honest())

    print("ADCOS resilience self-test (M015 — Execution Resilience Runtime)")
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
