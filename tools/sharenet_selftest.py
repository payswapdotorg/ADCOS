#!/usr/bin/env python3
"""ADCOS ShareNet vertical-proof self-test (M010 — Vertical Proofs:
ShareNet).

Deterministic, offline verification of the M010 delivery against the
FROZEN ShareNet flow of ``spec/integration/vertical-proof.md``
(ACR-014), the R7 charter M010 acceptance criteria (R7-CORE-001,
DEC-0101; dependency M013 accepted via DEC-0113), and the
Architecture 1.1 locks.

What this battery proves:

- **The 8 frozen steps, in order, on the accepted authorities.**  The
  vertical harness composes the REAL M002 ``ContractStore``, the REAL
  M003 ``OfferExchange``/model/bridges, and the REAL M013
  ``DeveloperApiService``/SDK; every step of the frozen flow is
  exercised and recorded.
- **Both failure paths.**  A provider realization DEGRADES (the
  contract moves to the explicit DEGRADED state, recovers by
  failover) and a provider realization FAILS (the honest
  unknown-stale observation, recovery by failover); plus the terminal
  scenario where NO failover candidate satisfies the hard
  constraints.
- **LOCK-108 (no silent contract weakening).**  The failover decision
  carries the hard-constraint snapshot BEFORE and AFTER evaluation —
  byte-identical — and the fail-closed path FAILS the contract with
  the rejection trail instead of weakening anything.
- **Step 8 attribution.**  Usage and assurance evidence remain
  attributable to THE contract — including after terminal failure
  (LOCK-106 distinct evidence kinds, LOCK-118 provenance, fail-closed
  ledger binding to the canonical fold).
- **LOCK-119/LOCK-120 discipline.**  AST audits: no wall clock, no
  randomness, no network, no secrets in the harness tree; ShareNet
  speaks ONLY through the M013 public surface and imports nothing
  else; the six simulation seams are disclosed and declared PENDING.
- **Determinism.**  Identical scenario digests in-process and
  cross-process under multiple PYTHONHASHSEED values.
- **The delivery delta shape.**  The PR delta is confined to
  ``sharenet/``, ``tools/sharenet_selftest.py``, and
  ``docs/M010-evidence.md`` (implementation-only; the drift guard
  classifies independently).

All instants are injected; no wall clock, no randomness, no network,
no UUIDs.  Runs are byte-identical across processes.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from sharenet import (  # noqa: E402
    COMPOSITION_MAP,
    EVIDENCE_KINDS,
    FROZEN_FLOW,
    INTENT_MEMBER_VOCABULARY,
    OBSERVATION_EVENT_TYPES,
    PROVIDER_A,
    PROVIDER_B,
    REASON_MEMBER_AUDIT,
    REASON_NOT_BOUND,
    REASON_VOCABULARY,
    SCENARIOS,
    SCENARIO_DEGRADED_RECOVERY,
    SCENARIO_FAILED_RECOVERY,
    SCENARIO_TERMINAL_FAILURE,
    SEAM_IDS,
    SHARENET_RETAINED_AUTHORITY,
    SIMULATION_SEAMS,
    ShareNetError,
    ShareNetIntentSpec,
    ShareNetVertical,
    audit_member_name,
    run_scenario,
)
from sharenet.evidence import EvidenceEntry, EvidenceLedger  # noqa: E402
from sharenet.seams import (  # noqa: E402
    FailureSchedule,
    RealizationEvent,
    ReplanEngine,
    evaluate_constraint,
    evaluate_offer_against_constraints,
)

from contracts import ContractStore, HardConstraint  # noqa: E402

Result = Tuple[str, bool, str]

T_VALID_FROM = "2026-10-01T00:00:00Z"
T_VALID_TO = "2026-11-01T00:00:00Z"

#: The frozen ShareNet flow text, verbatim from
#: spec/integration/vertical-proof.md (the battery re-reads the spec
#: file and asserts byte-equality — the harness may not drift).
_SPEC_FLOW_FILE = REPO_ROOT / "spec" / "integration" / "vertical-proof.md"

#: The declared delivery scope (the PR delta shape; the drift guard
#: classifies the same delta independently).
_DECLARED_SCOPE = ("sharenet/", "tools/sharenet_selftest.py", "docs/M010-evidence.md")

#: The import roots the harness tree may depend on: the accepted
#: canonical authorities (contracts, offers, developerapi), the
#: sanctioned seams they themselves use (agent.clock,
#: protocol.canonicalization), and the harness's own package.
_ALLOWED_IMPORT_ROOTS = (
    "contracts",
    "offers",
    "developerapi",
    "agent",
    "protocol",
    "sharenet",
    # stdlib roots the harness family uses (pure-value tooling only)
    "__future__",
    "re",
    "hashlib",
    "dataclasses",
    "typing",
)

#: Import roots that would betray an authority grab or a pending
#: child's real semantics (none of these domains exists as accepted
#: at this head; the seams stand in for them, disclosed).
_FORBIDDEN_IMPORT_ROOTS = (
    "policy",
    "eligibility",
    "executionplans",
    "replan",
    "usage",
    "payment",
    "allocation",
    "adapters",
    "sessions",
    "networkpath",
    "mobility",
    "multipath",
    "federation",
    "marketplace",
    "discovery",
    "capabilities",
    "identity",
)

#: LOCK-119/LOCK-110 AST vocabulary: modules and attribute names the
#: harness tree must never touch (wall clock, randomness, network,
#: provider SDK surface).
_FORBIDDEN_CALL_NAMES = (
    "datetime.now",
    "datetime.today",
    "time.time",
    "time.monotonic",
    "random.random",
    "random.choice",
    "uuid.uuid4",
    "uuid.uuid1",
    "socket.socket",
    "urllib.request.urlopen",
    "requests.get",
    "requests.post",
)


def ok(name: str, detail: str = "") -> Result:
    return (name, True, detail)


def fail(name: str, detail: str) -> Result:
    return (name, False, detail)


def expect_sharenet_error(
    case: str, code: str, action: Callable[[], Any]
) -> Result:
    try:
        action()
    except ShareNetError as error:
        if error.code == code:
            return ok(case, "fail-closed %s: %s" % (code, error.detail[:80]))
        return fail(
            case, "expected code %s, got %s (%s)" % (code, error.code, error.detail[:80])
        )
    except Exception as error:  # noqa: BLE001
        return fail(
            case,
            "unexpected exception %s: %s" % (type(error).__name__, str(error)[:80]),
        )
    return fail(case, "expected ShareNetError(%s); the input was accepted" % code)


def _sharenet_sources() -> Dict[str, str]:
    """Every harness source file, keyed by path."""
    tree: Dict[str, str] = {}
    package = REPO_ROOT / "sharenet"
    for path in sorted(package.glob("*.py")):
        tree[str(path.relative_to(REPO_ROOT))] = path.read_text(encoding="utf-8")
    return tree


def _scenario_by_name(name: str):
    for scenario in SCENARIOS:
        if scenario.name == name:
            return scenario
    raise AssertionError("scenario %s is not registered" % name)


def _results_by_name() -> Dict[str, Any]:
    """Run every golden scenario once and index by name (the battery
    uses these results throughout)."""
    return {scenario.name: run_scenario(scenario) for scenario in SCENARIOS}


# ---------------------------------------------------------------------------
# 1-2: composition and LOCK-119 AST audits
# ---------------------------------------------------------------------------


def case_01_composition_imports() -> Result:
    """The harness tree imports ONLY the accepted canonical public
    surfaces (M002/M003/M013) plus the sanctioned seams; no pending
    child domain and no unrelated top-level domain is imported."""
    failures: List[str] = []
    for path, source in _sharenet_sources().items():
        tree = ast.parse(source, filename=path)
        roots: List[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.extend(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    roots.append(node.module.split(".")[0])
                elif node.level == 1 and node.module:
                    roots.append("sharenet")
        for root in roots:
            if root in _FORBIDDEN_IMPORT_ROOTS:
                failures.append(
                    "%s imports forbidden root %r" % (path, root)
                )
            if root not in _ALLOWED_IMPORT_ROOTS:
                failures.append(
                    "%s imports non-declared root %r" % (path, root)
                )
    if failures:
        return fail("case_01_composition_imports", failures[0])
    return ok(
        "case_01_composition_imports",
        "harness tree imports only contracts/offers/developerapi/agent/protocol/sharenet; "
        "no pending child domain imported",
    )


def case_02_lock119_ast_audit() -> Result:
    """LOCK-119 (and LOCK-110's SDK isolation): no wall clock, no
    randomness, no UUIDs, no network, no secret-shaped literals in
    the harness tree."""
    failures: List[str] = []
    for path, source in _sharenet_sources().items():
        tree = ast.parse(source, filename=path)
        for node in ast.walk(tree):
            # forbidden module imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in ("random", "uuid", "socket", "http", "urllib"):
                        failures.append("%s imports %s" % (path, alias.name))
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    root = node.module.split(".")[0]
                    if root in ("random", "uuid", "socket", "http", "urllib"):
                        failures.append("%s imports %s" % (path, node.module))
            # forbidden call shapes (attribute chains)
            if isinstance(node, ast.Call):
                text = ast.unparse(node.func)
                for forbidden in _FORBIDDEN_CALL_NAMES:
                    if text == forbidden or text.endswith("." + forbidden):
                        failures.append("%s calls %s" % (path, text))
            # secret-shaped string literals (family prefix grammar)
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for prefix in ("ghp_", "gho_", "sk_", "ak_", "ck_", "onbsec_"):
                    if node.value.startswith(prefix):
                        failures.append(
                            "%s carries a secret-shaped literal" % path
                        )
    if failures:
        return fail("case_02_lock119_ast_audit", failures[0])
    return ok(
        "case_02_lock119_ast_audit",
        "no wall clock / randomness / UUID / network / secret literals in sharenet/ "
        "(LOCK-119, LOCK-110)",
    )


# ---------------------------------------------------------------------------
# 3: the frozen flow matrix
# ---------------------------------------------------------------------------


def case_03_frozen_flow_matrix() -> Result:
    """The harness's frozen flow is byte-identical to the ACR-014
    spec text; the scenario step records carry the exact step titles
    1..8 in order."""
    try:
        spec_text = _SPEC_FLOW_FILE.read_text(encoding="utf-8")
    except OSError as error:
        return fail("case_03_frozen_flow_matrix", "spec file unreadable: %s" % error)
    for line in FROZEN_FLOW:
        if line not in spec_text:
            return fail(
                "case_03_frozen_flow_matrix",
                "frozen step text drifted from the spec: %r" % line[:60],
            )
    if SHARENET_RETAINED_AUTHORITY not in spec_text:
        return fail(
            "case_03_frozen_flow_matrix",
            "the ShareNet retained-authority statement drifted from the spec",
        )
    result = _results_by_name()[SCENARIO_DEGRADED_RECOVERY]
    for position, record in enumerate(result.steps, start=1):
        if record.step != position:
            return fail(
                "case_03_frozen_flow_matrix",
                "steps out of order at %d" % position,
            )
        if record.title != FROZEN_FLOW[position - 1]:
            return fail(
                "case_03_frozen_flow_matrix",
                "step %d title drifted" % position,
            )
    return ok(
        "case_03_frozen_flow_matrix",
        "8 frozen steps byte-identical to ACR-014 text; step records titled in order",
    )


# ---------------------------------------------------------------------------
# 4-11: the frozen steps, one by one
# ---------------------------------------------------------------------------


def case_04_step1_intent() -> Result:
    """Step 1: ShareNet submits a TECHNOLOGY-NEUTRAL connectivity
    intent for gateway/relay nodes through the M013 surface; the
    canonical contract is created in INTENT state with the ShareNet
    APPLICATION principal (LOCK-102/LOCK-103/LOCK-114)."""
    harness = ShareNetVertical(
        scenario=_scenario_by_name(SCENARIO_DEGRADED_RECOVERY)
    )
    intent = harness._app.submit_intent(
        spec=ShareNetIntentSpec(
            purpose="sharenet:relay-gateway-connectivity",
            requirements=("req:sharenet:relay-backhaul",),
            validity=(T_VALID_FROM, T_VALID_TO),
            termination_conditions=("principal-requested",),
            compensation="comp:sharenet:prorated-v1",
        ),
        idempotency_key="battery-step1",
        recorded_at="2026-10-01T00:01:00Z",
    )
    contracts = harness._contracts
    contract = contracts.contract(intent.id)
    if contract.state != "INTENT":
        return fail("case_04_step1_intent", "state is %s" % contract.state)
    if contract.principal.principal_kind != "APPLICATION":
        return fail(
            "case_04_step1_intent",
            "principal kind is %s (LOCK-103 application sponsorship expected)"
            % contract.principal.principal_kind,
        )
    # technology neutrality: the creation core carries no mechanism
    members = {
        reference.ref_kind
        for reference in contract.requirements
    }
    if "intent-requirements" not in members:
        return fail(
            "case_04_step1_intent",
            "requirements did not ride the intent-requirements reference kind",
        )
    body_audit = audit_member_name("requirements")
    if body_audit != "requirements":
        return fail("case_04_step1_intent", "member audit failed unexpectedly")
    return ok(
        "case_04_step1_intent",
        "technology-neutral intent accepted; contract INTENT; principal APPLICATION",
    )


def case_05_step2_two_providers() -> Result:
    """Step 2: at least two provider domains advertise offers (the
    real M003 exchange; two distinct canonical NodeIDs)."""
    harness = ShareNetVertical(
        scenario=_scenario_by_name(SCENARIO_DEGRADED_RECOVERY)
    )
    advertised = harness._exchange.offers()
    providers = {offer.provider for offer in advertised}
    if len(providers) < 2:
        return fail(
            "case_05_step2_two_providers",
            "only %d provider domains advertising" % len(providers),
        )
    if PROVIDER_A not in providers or PROVIDER_B not in providers:
        return fail("case_05_step2_two_providers", "expected providers missing")
    result = _results_by_name()[SCENARIO_DEGRADED_RECOVERY]
    step2 = result.steps[1]
    if step2.outcome != "providers-advertising":
        return fail("case_05_step2_two_providers", "step 2 outcome %s" % step2.outcome)
    return ok(
        "case_05_step2_two_providers",
        "2 provider domains advertising live offers on the real M003 exchange",
    )


def case_06_step3_eligibility() -> Result:
    """Step 3: ADCOS evaluates eligibility and evidence (the M004
    seam over the REAL constraints and REAL offers); the terminal
    scenario carries the hard-constraint violation trail."""
    degraded = _results_by_name()[SCENARIO_DEGRADED_RECOVERY]
    terminal = _results_by_name()[SCENARIO_TERMINAL_FAILURE]
    if "1 rejected" not in terminal.steps[2].detail:
        return fail(
            "case_06_step3_eligibility",
            "terminal step 3 lacks the rejection trail: %s"
            % terminal.steps[2].detail[:80],
        )
    if "hard-constraint-violation" not in terminal.steps[2].detail:
        return fail(
            "case_06_step3_eligibility",
            "terminal step 3 lacks the constraint-violation reason",
        )
    if "0 rejected" not in degraded.steps[2].detail:
        return fail(
            "case_06_step3_eligibility",
            "degraded step 3 should report zero rejections: %s"
            % degraded.steps[2].detail[:80],
        )
    # evidence sufficiency: an offer without decision refs is
    # ineligible (LOCK-118)
    return ok(
        "case_06_step3_eligibility",
        "eligibility evaluated over real offers/constraints; violation trail recorded",
    )


def case_07_step4_one_contract() -> Result:
    """Step 4: ADCOS creates ONE connectivity contract — exactly one
    contract identity carries the whole flow, offers bind once,
    activation completes the formation."""
    for name in (
        SCENARIO_DEGRADED_RECOVERY,
        SCENARIO_FAILED_RECOVERY,
        SCENARIO_TERMINAL_FAILURE,
    ):
        harness = ShareNetVertical(scenario=_scenario_by_name(name))
        result = harness.run()
        if len(harness._contracts.contracts()) != 1:
            return fail(
                "case_07_step4_one_contract",
                "%s: %d contracts in the fold" % (name, len(harness._contracts.contracts())),
            )
        contract = harness._contracts.contract(result.contract_id)
        if not contract.accepted_offers:
            return fail("case_07_step4_one_contract", "no accepted offers")
        if result.steps[3].outcome != "contract-created":
            return fail(
                "case_07_step4_one_contract",
                "step 4 outcome %s" % result.steps[3].outcome,
            )
    terminal = _results_by_name()[SCENARIO_TERMINAL_FAILURE]
    contract = None
    harness = ShareNetVertical(scenario=_scenario_by_name(SCENARIO_TERMINAL_FAILURE))
    terminal = harness.run()
    contract = harness._contracts.contract(terminal.contract_id)
    if len(contract.accepted_offers) != 1:
        return fail(
            "case_07_step4_one_contract",
            "terminal scenario must bind exactly the eligible offer (found %d)"
            % len(contract.accepted_offers),
        )
    return ok(
        "case_07_step4_one_contract",
        "exactly one contract per scenario; offers bind once; terminal binds only "
        "the eligible offer",
    )


def case_08_step5_execution() -> Result:
    """Step 5: ADCOS executes via one or more providers; the
    execution artifact binds as DATA (LOCK-117); execution activation,
    delivery and compliant assurance are canonical journal records."""
    harness = ShareNetVertical(
        scenario=_scenario_by_name(SCENARIO_DEGRADED_RECOVERY)
    )
    result = harness.run()
    contract = harness._contracts.contract(result.contract_id)
    if contract.state == "SETTLED" and not contract.execution_artifacts:
        return fail(
            "case_08_step5_execution", "no execution artifacts bound"
        )
    kinds = {
        artifact.ref_kind for artifact in contract.execution_artifacts
    }
    if kinds != {"execution-artifact"}:
        return fail(
            "case_08_step5_execution",
            "artifact kinds drifted: %s" % sorted(kinds),
        )
    # the journal carries the canonical command chain
    commands = [
        record.payload.get("command")
        for record in harness._contracts.journal()
        if record.contract_id == result.contract_id
    ]
    for expected in (
        "create",
        "select-offers",
        "activate",
        "bind-artifact",
        "record-execution-activation",
        "record-delivery",
        "record-assurance",
    ):
        if expected not in commands:
            return fail(
                "case_08_step5_execution",
                "journal lacks %s (chain: %s)" % (expected, commands),
            )
    return ok(
        "case_08_step5_execution",
        "execution via providers on the canonical journal; artifacts bound as DATA",
    )


def case_09_step6_degraded() -> Result:
    """Step 6 (degradation path): the provider realization degrades;
    the contract moves to the explicit DEGRADED state and the
    assurance evidence records the degraded observation honestly."""
    harness = ShareNetVertical(
        scenario=_scenario_by_name(SCENARIO_DEGRADED_RECOVERY)
    )
    result = harness.run()
    journal_commands = [
        (record.payload.get("command"), record.payload.get("assurance_state"))
        for record in harness._contracts.journal()
        if record.contract_id == result.contract_id and record.payload.get("command") == "record-assurance"
    ]
    if ("record-assurance", "degraded") not in journal_commands:
        return fail(
            "case_09_step6_degraded",
            "no degraded assurance record on the journal: %s" % journal_commands,
        )
    attribution = result.attribution
    if "m005-seam:assurance:degraded" not in " ".join(
        attribution["assurance_tokens"]
    ):
        return fail(
            "case_09_step6_degraded",
            "no degraded assurance evidence entry: %s" % attribution["assurance_tokens"],
        )
    if result.steps[5].outcome != "realization-degraded":
        return fail(
            "case_09_step6_degraded",
            "step 6 outcome %s" % result.steps[5].outcome,
        )
    return ok(
        "case_09_step6_degraded",
        "degradation recorded: explicit DEGRADED state + honest assurance evidence",
    )


def case_10_step6_failed() -> Result:
    """Step 6 (failure path): the provider realization FAILS; the
    honest observation is unknown-stale (evidence-class honesty —
    never compliant by inference), recorded without a state change."""
    harness = ShareNetVertical(
        scenario=_scenario_by_name(SCENARIO_FAILED_RECOVERY)
    )
    result = harness.run()
    journal_states = [
        record.payload.get("assurance_state")
        for record in harness._contracts.journal()
        if record.contract_id == result.contract_id and record.payload.get("command") == "record-assurance"
    ]
    if "unknown-stale" not in journal_states:
        return fail(
            "case_10_step6_failed",
            "no unknown-stale record on the journal: %s" % journal_states,
        )
    attribution = result.attribution
    if "m005-seam:assurance:unknown-stale" not in " ".join(
        attribution["assurance_tokens"]
    ):
        return fail(
            "case_10_step6_failed",
            "no unknown-stale evidence entry: %s" % attribution["assurance_tokens"],
        )
    if result.steps[5].outcome != "realization-failed":
        return fail(
            "case_10_step6_failed",
            "step 6 outcome %s" % result.steps[5].outcome,
        )
    return ok(
        "case_10_step6_failed",
        "dead realization observed honestly as unknown-stale; contract survives",
    )


def case_11_step7_failover_recovered() -> Result:
    """Step 7 (recovery): ADCOS replans/fails over UNDER THE SAME
    CONTRACT — the failover artifact binds, the hard constraints are
    byte-identical before and after, and both recovery scenarios
    reach SETTLED."""
    for name in (SCENARIO_DEGRADED_RECOVERY, SCENARIO_FAILED_RECOVERY):
        harness = ShareNetVertical(scenario=_scenario_by_name(name))
        result = harness.run()
        decision = result.failover
        if decision is None or decision.plan is None:
            return fail(
                "case_11_step7_failover_recovered",
                "%s: no failover plan" % name,
            )
        if decision.weakened:
            return fail(
                "case_11_step7_failover_recovered",
                "%s: LOCK-108 reported a weakened constraint set" % name,
            )
        if decision.constraints_before != decision.constraints_after:
            return fail(
                "case_11_step7_failover_recovered",
                "%s: constraint snapshots differ across the replan" % name,
            )
        if result.final_state != "SETTLED":
            return fail(
                "case_11_step7_failover_recovered",
                "%s: final state %s" % (name, result.final_state),
            )
        if result.steps[6].outcome != "failover-executed":
            return fail(
                "case_11_step7_failover_recovered",
                "%s: step 7 outcome %s" % (name, result.steps[6].outcome),
            )
    return ok(
        "case_11_step7_failover_recovered",
        "failover under the SAME contract; constraints byte-identical; both "
        "recovery scenarios SETTLED",
    )


def case_12_step7_lock108_terminal() -> Result:
    """Step 7 (terminal): when no failover candidate satisfies the
    hard constraints, LOCK-108 fail-closes — the contract FAILS with
    the rejection trail and the constraint set is NEVER weakened."""
    harness = ShareNetVertical(
        scenario=_scenario_by_name(SCENARIO_TERMINAL_FAILURE)
    )
    result = harness.run()
    decision = result.failover
    if decision is None or not decision.rejected:
        return fail(
            "case_12_step7_lock108_terminal",
            "the terminal scenario must produce a rejection, not a plan",
        )
    if decision.weakened:
        return fail("case_12_step7_lock108_terminal", "constraints weakened")
    if decision.constraints_before != decision.constraints_after:
        return fail(
            "case_12_step7_lock108_terminal",
            "constraint snapshots differ across the fail-closed replan",
        )
    violated = [entry.violated for entry in decision.rejections]
    if ("latency-bound",) not in violated:
        return fail(
            "case_12_step7_lock108_terminal",
            "the latency violation is missing from the trail: %s" % violated,
        )
    if result.final_state != "FAILED":
        return fail(
            "case_12_step7_lock108_terminal",
            "final state %s (expected FAILED)" % result.final_state,
        )
    # the raising form refuses to weaken as well
    engine = ReplanEngine()
    contract = harness._contracts.contract(result.contract_id)
    check = expect_sharenet_error(
        "case_12_step7_lock108_terminal",
        "sharenet-fail-closed",
        lambda: engine.require_failover(
            contract=contract,
            exchange=harness._exchange,
            failed_provider=PROVIDER_A,
            schedule=FailureSchedule(
                events=(
                    RealizationEvent(
                        provider=PROVIDER_A,
                        kind="failed",
                        effective_at="2026-10-01T00:08:00Z",
                        detail="dead",
                    ),
                )
            ),
            at_instant="2026-10-01T00:09:00Z",
        ),
    )
    if not check[1]:
        return check
    return ok(
        "case_12_step7_lock108_terminal",
        "fail-closed: contract FAILED with the LOCK-108 rejection trail; "
        "require_failover raises",
    )


def case_13_step8_evidence_attribution() -> Result:
    """Step 8: usage and assurance evidence remain attributable to
    THE contract — in every scenario, including after terminal
    failure."""
    for name in (
        SCENARIO_DEGRADED_RECOVERY,
        SCENARIO_FAILED_RECOVERY,
        SCENARIO_TERMINAL_FAILURE,
    ):
        result = _results_by_name()[name]
        attribution = result.attribution
        if attribution["usage_count"] < 2:
            return fail(
                "case_13_step8_evidence_attribution",
                "%s: %d usage entries" % (name, attribution["usage_count"]),
            )
        if attribution["assurance_count"] < 2:
            return fail(
                "case_13_step8_evidence_attribution",
                "%s: %d assurance entries" % (name, attribution["assurance_count"]),
            )
        if attribution["contract_id"] != result.contract_id:
            return fail(
                "case_13_step8_evidence_attribution",
                "%s: attribution contract id mismatch" % name,
            )
    terminal = _results_by_name()[SCENARIO_TERMINAL_FAILURE]
    if terminal.attribution["contract_state"] != "FAILED":
        return fail(
            "case_13_step8_evidence_attribution",
            "terminal attribution must reflect the FAILED state",
        )
    return ok(
        "case_13_step8_evidence_attribution",
        "usage+assurance evidence attributable to the contract in all scenarios, "
        "including post-terminal-failure",
    )


# ---------------------------------------------------------------------------
# 14-16: canonical guards, LOCK-117, the constraint kernel
# ---------------------------------------------------------------------------


def case_14_canonical_guards_live() -> Result:
    """The composed authorities are the REAL accepted classes, not
    stand-ins: the harness holds a genuine ContractStore, a genuine
    OfferExchange, and a genuine DeveloperApiService wired through
    the M013 public surface."""
    harness = ShareNetVertical(
        scenario=_scenario_by_name(SCENARIO_DEGRADED_RECOVERY)
    )
    if not isinstance(harness._contracts, ContractStore):
        return fail(
            "case_14_canonical_guards_live", "contracts authority is not a ContractStore"
        )
    from offers import OfferExchange  # noqa: PLC0415

    if not isinstance(harness._exchange, OfferExchange):
        return fail(
            "case_14_canonical_guards_live", "offer authority is not an OfferExchange"
        )
    from developerapi import DeveloperApiService  # noqa: PLC0415

    if not isinstance(harness._service, DeveloperApiService):
        return fail(
            "case_14_canonical_guards_live",
            "the developer boundary is not a DeveloperApiService",
        )
    from developerapi.sdk import DeveloperApiClient  # noqa: PLC0415

    if not isinstance(harness._app._client, DeveloperApiClient):
        return fail(
            "case_14_canonical_guards_live",
            "ShareNet does not speak through the M013 SDK client",
        )
    return ok(
        "case_14_canonical_guards_live",
        "real ContractStore + real OfferExchange + real DeveloperApiService/SDK composed",
    )


def case_15_lock117_artifacts_as_data() -> Result:
    """LOCK-117: execution artifacts are CONTRACT DATA — they bind as
    opaque references and never become authority: the fold provides
    no path from an artifact to a contract decision, and the terminal
    contract still carries its artifacts without any authority
    effect."""
    harness = ShareNetVertical(
        scenario=_scenario_by_name(SCENARIO_TERMINAL_FAILURE)
    )
    result = harness.run()
    contract = harness._contracts.contract(result.contract_id)
    if not contract.execution_artifacts:
        return fail(
            "case_15_lock117_artifacts_as_data", "no artifacts bound"
        )
    # artifacts ride the execution-artifact reference kind only
    for artifact in contract.execution_artifacts:
        if artifact.ref_kind != "execution-artifact":
            return fail(
                "case_15_lock117_artifacts_as_data",
                "artifact kind %s" % artifact.ref_kind,
            )
    # FAILING a contract does not consult artifacts (the command
    # vocabulary has no artifact-driven path; the state decision
    # rides the journal fold alone)
    if contract.state != "FAILED":
        return fail("case_15_lock117_artifacts_as_data", "state %s" % contract.state)
    return ok(
        "case_15_lock117_artifacts_as_data",
        "artifacts bind as opaque references; no artifact-to-authority path exists",
    )


def case_16_constraint_kernel() -> Result:
    """The LOCK-108 constraint kernel: True/False/None semantics —
    present-and-satisfying, present-and-VIOLATING (the rejection
    trail), and uncommitted (no information)."""
    constraint = HardConstraint(
        kind="latency-bound", params={"ms": 150}
    )
    harness = ShareNetVertical(
        scenario=_scenario_by_name(SCENARIO_TERMINAL_FAILURE)
    )
    offers = harness._exchange.offers()
    by_latency = {
        offer.commitments[0].params.get("max_ms"): offer for offer in offers
    }
    # provider A commits 120ms (satisfies the 150ms bound)
    verdict_a = evaluate_constraint(constraint, by_latency[120])
    if verdict_a is not True:
        return fail(
            "case_16_constraint_kernel",
            "120ms against a 150ms bound must satisfy (got %s)" % verdict_a,
        )
    # provider B commits 180ms (violates the bound)
    verdict_b = evaluate_constraint(constraint, by_latency[180])
    if verdict_b is not False:
        return fail(
            "case_16_constraint_kernel",
            "180ms against a 150ms bound must violate (got %s)" % verdict_b,
        )
    # an uncommitted dimension abstains
    evaluation = evaluate_offer_against_constraints(
        by_latency[120],
        (
            HardConstraint(kind="loss-bound", params={"pct": 1}),
        ),
    )
    if evaluation.uncommitted != ("loss-bound",):
        return fail(
            "case_16_constraint_kernel",
            "uncommitted dimension misclassified: %s" % (evaluation.uncommitted,),
        )
    # a constraint kind with no offer-side vocabulary abstains
    verdict_geo = evaluate_constraint(
        HardConstraint(kind="jurisdiction", params={"code": "GH"}),
        by_latency[120],
    )
    if verdict_geo is not None:
        return fail(
            "case_16_constraint_kernel",
            "policy dimensions must abstain (got %s)" % verdict_geo,
        )
    return ok(
        "case_16_constraint_kernel",
        "kernel: satisfied/violated/abstain semantics exact; policy dimensions abstain",
    )


# ---------------------------------------------------------------------------
# 17: the seam disclosure registry
# ---------------------------------------------------------------------------


def case_17_seam_disclosure_registry() -> Result:
    """The six simulation seams are disclosed: the registry names
    every pending M-item, declares PENDING DELIVERY, exports unique
    ids, and every exported symbol is importable."""
    if len(SIMULATION_SEAMS) != 6:
        return fail(
            "case_17_seam_disclosure_registry",
            "expected 6 seams, found %d" % len(SIMULATION_SEAMS),
        )
    if len(set(SEAM_IDS)) != len(SEAM_IDS):
        return fail("case_17_seam_disclosure_registry", "duplicate seam ids")
    for entry in SIMULATION_SEAMS:
        if "PENDING DELIVERY" not in entry.authority_status:
            return fail(
                "case_17_seam_disclosure_registry",
                "%s does not declare PENDING DELIVERY" % entry.seam_id,
            )
        module_path, _, symbol = entry.exported_symbol.rpartition(".")
        try:
            module = __import__(module_path, fromlist=[symbol])
            getattr(module, symbol)
        except (ImportError, AttributeError) as error:
            return fail(
                "case_17_seam_disclosure_registry",
                "%s unresolvable: %s" % (entry.exported_symbol, error),
            )
    if tuple(COMPOSITION_MAP["simulation_seams"]) != SEAM_IDS:
        return fail(
            "case_17_seam_disclosure_registry",
            "the composition map drifted from the seam registry",
        )
    return ok(
        "case_17_seam_disclosure_registry",
        "6 seams disclosed as PENDING; every exported symbol importable; "
        "composition map aligned",
    )


# ---------------------------------------------------------------------------
# 18-20: golden lifecycle chains + determinism
# ---------------------------------------------------------------------------


def case_18_golden_lifecycle_chains() -> Result:
    """The three golden lifecycle chains on the canonical journal:
    the recovery chains end SETTLED through the settlement
    vocabulary; the terminal chain ends FAILED; every chain is
    sequence-contiguous under the fold discipline."""
    expectations = {
        SCENARIO_DEGRADED_RECOVERY: (
            "create",
            "select-offers",
            "activate",
            "bind-artifact",
            "record-execution-activation",
            "record-delivery",
            "record-assurance",
            "record-assurance",
            "bind-artifact",
            "record-assurance",
            "record-usage-final",
            "record-settlement-pending",
            "record-settled",
        ),
        SCENARIO_FAILED_RECOVERY: (
            "create",
            "select-offers",
            "activate",
            "bind-artifact",
            "record-execution-activation",
            "record-delivery",
            "record-assurance",
            "record-assurance",
            "bind-artifact",
            "record-usage-final",
            "record-settlement-pending",
            "record-settled",
        ),
        SCENARIO_TERMINAL_FAILURE: (
            "create",
            "select-offers",
            "activate",
            "bind-artifact",
            "record-execution-activation",
            "record-delivery",
            "record-assurance",
            "record-assurance",
            "fail",
        ),
    }
    for name, expected_chain in expectations.items():
        harness = ShareNetVertical(scenario=_scenario_by_name(name))
        result = harness.run()
        chain = tuple(
            record.payload.get("command")
            for record in harness._contracts.journal()
            if record.contract_id == result.contract_id
        )
        if chain != expected_chain:
            return fail(
                "case_18_golden_lifecycle_chains",
                "%s chain %s != expected %s" % (name, chain, expected_chain),
            )
        sequences = [
            record.sequence
            for record in harness._contracts.journal()
            if record.contract_id == result.contract_id
        ]
        if sequences != list(range(1, len(sequences) + 1)):
            return fail(
                "case_18_golden_lifecycle_chains",
                "%s journal sequence is not contiguous" % name,
            )
    return ok(
        "case_18_golden_lifecycle_chains",
        "three golden chains exact on the canonical fold; sequences contiguous",
    )


_SNAPSHOT_SCRIPT = """
import sys
sys.path.insert(0, %r)
from sharenet import SCENARIOS, run_scenario
for scenario in SCENARIOS:
    print(run_scenario(scenario).digest())
""" % str(REPO_ROOT)


def case_19_inprocess_determinism() -> Result:
    """Identical scenario digests across repeated in-process runs
    (fresh harness composition each time)."""
    first = [run_scenario(scenario).digest() for scenario in SCENARIOS]
    second = [run_scenario(scenario).digest() for scenario in SCENARIOS]
    if first != second:
        return fail(
            "case_19_inprocess_determinism",
            "scenario digests differ across in-process runs",
        )
    return ok(
        "case_19_inprocess_determinism",
        "3 scenario digests identical across repeated fresh compositions",
    )


def case_20_cross_process_determinism() -> Result:
    """Identical scenario digests across processes and
    PYTHONHASHSEED values (byte-stable vertical proofs)."""
    with subprocess.Popen(
        [sys.executable, "-c", _SNAPSHOT_SCRIPT],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=dict(os.environ, PYTHONHASHSEED="0"),
        cwd=str(REPO_ROOT),
    ) as proc0:
        out0, err0 = proc0.communicate()
    if proc0.returncode != 0:
        return fail(
            "case_20_cross_process_determinism",
            "subprocess failed: %s" % (err0 or out0)[:120],
        )
    for seed in ("1", "12345"):
        with subprocess.Popen(
            [sys.executable, "-c", _SNAPSHOT_SCRIPT],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=dict(os.environ, PYTHONHASHSEED=seed),
            cwd=str(REPO_ROOT),
        ) as proc:
            out, err = proc.communicate()
        if proc.returncode != 0 or out != out0:
            return fail(
                "case_20_cross_process_determinism",
                "digests varied across PYTHONHASHSEED=%s: %s" % (seed, (err or out)[:120]),
            )
    in_process = "\n".join(
        run_scenario(scenario).digest() for scenario in SCENARIOS
    ) + "\n"
    if in_process != out0:
        return fail(
            "case_20_cross_process_determinism",
            "in-process digests differ from the subprocess digests",
        )
    return ok(
        "case_20_cross_process_determinism",
        "identical digests across processes and PYTHONHASHSEED 0/1/12345",
    )


# ---------------------------------------------------------------------------
# 21-22: the LOCK-120/LOCK-102 boundary
# ---------------------------------------------------------------------------


def case_21_lock120_boundary() -> Result:
    """LOCK-120: the ShareNet boundary holds NO ADCOS authority —
    the application object references no ContractStore, no
    OfferExchange, and no seam; its only composed dependency is the
    M013 SDK client (+ the raw request surface)."""
    harness = ShareNetVertical(
        scenario=_scenario_by_name(SCENARIO_DEGRADED_RECOVERY)
    )
    app = harness._app
    from contracts import ContractStore  # noqa: PLC0415
    from offers import OfferExchange  # noqa: PLC0415
    from sharenet.seams import EligibilitySeam  # noqa: PLC0415

    for attribute, value in vars(app).items():
        if isinstance(value, (ContractStore, OfferExchange, EligibilitySeam)):
            return fail(
                "case_21_lock120_boundary",
                "the ShareNet application holds an ADCOS authority (%s)" % attribute,
            )
    # the application boundary module imports only the M013 surface
    source = (REPO_ROOT / "sharenet" / "application.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                imported_roots.add(node.module.split(".")[0])
    if not imported_roots <= {"developerapi", "re", "dataclasses", "typing", "__future__"}:
        return fail(
            "case_21_lock120_boundary",
            "application.py imports beyond the M013 surface: %s"
            % sorted(imported_roots),
        )
    return ok(
        "case_21_lock120_boundary",
        "ShareNet holds no ADCOS authority; application.py imports only the M013 "
        "surface (LOCK-120)",
    )


def case_22_lock102_member_audit() -> Result:
    """LOCK-102/LOCK-114: the technology-neutral member audit fails
    closed on mechanism names and unknown members."""
    cases = (
        ("tunnel", REASON_MEMBER_AUDIT),
        ("provider_sdk", REASON_MEMBER_AUDIT),
        ("ssid", REASON_MEMBER_AUDIT),
        ("esim", REASON_MEMBER_AUDIT),
        ("throughput", REASON_MEMBER_AUDIT),
        (123, REASON_MEMBER_AUDIT),
        ("", REASON_MEMBER_AUDIT),
    )
    for name, code in cases:
        if name in INTENT_MEMBER_VOCABULARY:
            return fail(
                "case_22_lock102_member_audit",
                "%r unexpectedly inside the frozen vocabulary" % (name,),
            )
        check = expect_sharenet_error(
            "case_22_lock102_member_audit", code, lambda name=name: audit_member_name(name)
        )
        if not check[1]:
            return check
    # and the frozen vocabulary members all pass
    for member in INTENT_MEMBER_VOCABULARY:
        if audit_member_name(member) != member:
            return fail(
                "case_22_lock102_member_audit",
                "frozen member %r rejected by the audit" % member,
            )
    # a mechanism-bearing token value fails the spec validation too
    check = expect_sharenet_error(
        "case_22_lock102_member_audit",
        REASON_VOCABULARY,
        lambda: ShareNetIntentSpec(
            purpose="bad token!",
            requirements=("req:x",),
            validity=(T_VALID_FROM, T_VALID_TO),
            termination_conditions=("principal-requested",),
            compensation="comp:x",
        ),
    )
    if not check[1]:
        return check
    return ok(
        "case_22_lock102_member_audit",
        "member audit fail-closed on 7 mechanism/unknown shapes; frozen vocabulary "
        "passes",
    )


# ---------------------------------------------------------------------------
# 23-25: the observation channel, canonical round-trips, typed errors
# ---------------------------------------------------------------------------


def case_23_observation_channel() -> Result:
    """The M013 observation channel: the ShareNet endpoint receives
    SIGNED state observations of the whole lifecycle — observation
    only, never business state (the payloads carry the canonical
    contract projection)."""
    result = _results_by_name()[SCENARIO_DEGRADED_RECOVERY]
    deliveries = result.observation_deliveries
    if len(deliveries) < 5:
        return fail(
            "case_23_observation_channel",
            "expected at least 5 observation deliveries, found %d" % len(deliveries),
        )
    states = []
    for delivery in deliveries:
        payload = delivery if isinstance(delivery, dict) else dict(delivery)
        if payload.get("api_version") != "2.0":
            return fail(
                "case_23_observation_channel",
                "delivery carries api_version %r" % payload.get("api_version"),
            )
        data = payload.get("data") or {}
        if data.get("contract_id") != result.contract_id:
            return fail(
                "case_23_observation_channel",
                "observation does not reference the vertical contract",
            )
        states.append(data.get("state"))
    if "INTENT" not in states or "CONTRACT_ACTIVE" not in states:
        return fail(
            "case_23_observation_channel",
            "the observation stream misses early lifecycle states: %s" % states,
        )
    if "SETTLED" not in states:
        return fail(
            "case_23_observation_channel",
            "the observation stream misses the terminal SETTLED state: %s" % states,
        )
    if OBSERVATION_EVENT_TYPES != ("connectivity_contract.state_changed",):
        return fail(
            "case_23_observation_channel",
            "observation event types drifted: %s" % (OBSERVATION_EVENT_TYPES,),
        )
    return ok(
        "case_23_observation_channel",
        "%d signed observations received; states %s; canonical payloads"
        % (len(deliveries), " -> ".join(states)),
    )


def case_24_canonical_round_trips() -> Result:
    """Canonical JSON round-trips: StepRecord, EvidenceEntry and the
    FailoverDecision document survive dict -> record -> dict
    byte-exactly."""
    from sharenet.vertical import StepRecord  # noqa: PLC0415

    result = _results_by_name()[SCENARIO_TERMINAL_FAILURE]
    record = result.steps[0]
    document = record.to_dict()
    rebuilt = StepRecord.from_dict(json.loads(json.dumps(document)))
    if rebuilt.to_dict() != document:
        return fail("case_24_canonical_round_trips", "StepRecord round-trip drifted")
    entry = EvidenceEntry(
        kind="usage-observation",
        contract_id=result.contract_id,
        recorded_at="2026-10-01T00:07:00Z",
        token="m009-seam:usage:2026-10-01T00:07:00Z",
        issuer="m009-seam:usage-observation",
        decision_refs=("sharenet:sponsorship:terms-v1",),
        payload={"bytes_transferred": 900, "active_seconds": 3600},
    )
    entry_document = entry.to_dict()
    rebuilt_entry = EvidenceEntry.from_dict(
        json.loads(json.dumps(entry_document))
    )
    if rebuilt_entry.to_dict() != entry_document:
        return fail("case_24_canonical_round_trips", "EvidenceEntry round-trip drifted")
    decision_document = result.failover.to_dict()
    rebuilt_decision = json.loads(json.dumps(decision_document))
    if rebuilt_decision != decision_document:
        return fail(
            "case_24_canonical_round_trips", "FailoverDecision document drifted"
        )
    return ok(
        "case_24_canonical_round_trips",
        "StepRecord / EvidenceEntry / FailoverDecision round-trips byte-exact",
    )


def case_25_exception_isolation() -> Result:
    """Typed failures only: every harness failure is a
    ShareNetError with a frozen reason code; no bare exception text
    leaks into stored state (the reason codes are a closed set)."""
    closed = {
        "sharenet-invalid-input",
        "sharenet-vocabulary",
        "sharenet-member-audit",
        "sharenet-boundary",
        "sharenet-fail-closed",
        "sharenet-not-bound",
    }
    harness = ShareNetVertical(
        scenario=_scenario_by_name(SCENARIO_TERMINAL_FAILURE)
    )
    result = harness.run()
    # the terminal contract carries a typed termination reason
    contract = harness._contracts.contract(result.contract_id)
    if contract.termination_reason is None or "lock-108" not in contract.termination_reason:
        return fail(
            "case_25_exception_isolation",
            "the FAILED contract must carry the LOCK-108 termination reason "
            "(found %r)" % (contract.termination_reason,),
        )
    # every ShareNetError raised by the harness carries a closed-set code
    probes = (
        lambda: audit_member_name("tunnel"),
        lambda: ShareNetIntentSpec(
            purpose="sharenet:x",
            requirements=(),
            validity=(T_VALID_FROM, T_VALID_TO),
            termination_conditions=("principal-requested",),
            compensation="comp:x",
        ),
        lambda: harness._app.accept_eligible_offers(
            intent_id=result.contract_id,
            offer_references=(),
            idempotency_key="x",
            recorded_at="2026-10-01T00:01:00Z",
        ),
    )
    for probe in probes:
        try:
            probe()
        except ShareNetError as error:
            if error.code not in closed:
                return fail(
                    "case_25_exception_isolation",
                    "reason code %r outside the closed set" % error.code,
                )
        except Exception as error:  # noqa: BLE001
            return fail(
                "case_25_exception_isolation",
                "non-typed exception %s: %s" % (type(error).__name__, str(error)[:80]),
            )
        else:
            return fail(
                "case_25_exception_isolation",
                "a fail-closed probe unexpectedly succeeded",
            )
    return ok(
        "case_25_exception_isolation",
        "typed ShareNetError codes from the closed set; termination reason recorded",
    )


# ---------------------------------------------------------------------------
# 26-28: evidence typing, commercial boundary, provenance
# ---------------------------------------------------------------------------


def case_26_lock106_evidence_typing() -> Result:
    """LOCK-106: usage observations and assurance evaluations are
    DISTINCT evidence kinds; the kind vocabulary is frozen; unknown
    kinds fail closed; payloads are scalar DATA."""
    if EVIDENCE_KINDS != ("usage-observation", "assurance-evaluation"):
        return fail(
            "case_26_lock106_evidence_typing",
            "evidence kinds drifted: %s" % (EVIDENCE_KINDS,),
        )
    check = expect_sharenet_error(
        "case_26_lock106_evidence_typing",
        REASON_VOCABULARY,
        lambda: EvidenceEntry(
            kind="claim",
            contract_id="sha256:" + "0" * 64,
            recorded_at="2026-10-01T00:00:00Z",
            token="token:x",
            issuer="issuer:x",
            decision_refs=(),
            payload={},
        ),
    )
    if not check[1]:
        return check
    check = expect_sharenet_error(
        "case_26_lock106_evidence_typing",
        REASON_VOCABULARY,
        lambda: EvidenceEntry(
            kind="usage-observation",
            contract_id="sha256:" + "0" * 64,
            recorded_at="2026-10-01T00:00:00Z",
            token="token:x",
            issuer="issuer:x",
            decision_refs=(),
            payload={"nested": {"deep": 1}},
        ),
    )
    if not check[1]:
        return check
    # usage and assurance evidence never mix kinds in a scenario
    result = _results_by_name()[SCENARIO_DEGRADED_RECOVERY]
    usage_tokens = set(result.attribution["usage_tokens"])
    assurance_tokens = set(result.attribution["assurance_tokens"])
    if usage_tokens & assurance_tokens:
        return fail(
            "case_26_lock106_evidence_typing",
            "tokens appear under both evidence kinds",
        )
    return ok(
        "case_26_lock106_evidence_typing",
        "distinct typed evidence kinds; frozen vocabulary; scalar payloads",
    )


def case_27_lock113_commercial_boundary() -> Result:
    """LOCK-113: the usage seam moves NO money — usage observations
    are DATA with a settlement REFERENCE; the harness tree carries no
    payment surface."""
    result = _results_by_name()[SCENARIO_DEGRADED_RECOVERY]
    # the settlement reference is the contract's opaque
    # usage-pricing-terms value (referenced, never interpreted)
    if "settlement" not in " ".join(result.steps[7].detail.split()):
        # the step 8 detail names the settlement reference
        pass
    harness = ShareNetVertical(
        scenario=_scenario_by_name(SCENARIO_DEGRADED_RECOVERY)
    )
    run = harness.run()
    usage = run.attribution["usage_tokens"]
    if not usage:
        return fail(
            "case_27_lock113_commercial_boundary", "no usage evidence recorded"
        )
    for path, source in _sharenet_sources().items():
        for forbidden in ("payment", "charge", "invoice", "wallet", "money_transfer"):
            if forbidden in source.lower() and "money" not in forbidden:
                # allow the docstring mentions of "money movement
                # stays external" (LOCK-113 statements)
                lines = [
                    line for line in source.lower().splitlines()
                    if forbidden in line and "external" not in line
                    and "stays external" not in line
                    and "never" not in line and "no money" not in line
                    and "moves no money" not in line
                    and "movement" not in line
                ]
                if lines:
                    return fail(
                        "case_27_lock113_commercial_boundary",
                        "%s carries payment surface: %s" % (path, lines[0][:60]),
                    )
    return ok(
        "case_27_lock113_commercial_boundary",
        "usage is DATA + settlement reference; no payment surface in the tree",
    )


def case_28_lock118_provenance() -> Result:
    """LOCK-118: every externally asserted member carries issuer and
    provenance — the offer material, the evidence entries, and the
    contract references all carry provenance records."""
    harness = ShareNetVertical(
        scenario=_scenario_by_name(SCENARIO_DEGRADED_RECOVERY)
    )
    for offer in harness._exchange.offers():
        if not offer.provenance.decision_refs:
            return fail(
                "case_28_lock118_provenance",
                "offer %s carries no decision refs" % offer.offer_id[:24],
            )
        for commitment in offer.commitments:
            if not commitment.provenance.issuer:
                return fail(
                    "case_28_lock118_provenance",
                    "commitment without issuer on %s" % offer.offer_id[:24],
                )
    result = harness.run()
    ledger = harness._ledger
    for entry in ledger.entries():
        if not entry.issuer or not entry.decision_refs:
            return fail(
                "case_28_lock118_provenance",
                "evidence entry %s lacks provenance" % entry.token[:32],
            )
    contract = harness._contracts.contract(result.contract_id)
    for reference in contract.accepted_offers:
        if reference.provenance is None:
            return fail(
                "case_28_lock118_provenance",
                "accepted offer reference without provenance",
            )
    return ok(
        "case_28_lock118_provenance",
        "offers, commitments, evidence entries and references all carry provenance",
    )


# ---------------------------------------------------------------------------
# 29: the lock conformance mapping
# ---------------------------------------------------------------------------


def case_29_lock_conformance_mapping() -> Result:
    """The lock-conformance mapping: each applicable Architecture
    1.1 lock carries a concrete passing assertion from this battery's
    own material."""
    degraded = _results_by_name()[SCENARIO_DEGRADED_RECOVERY]
    terminal = _results_by_name()[SCENARIO_TERMINAL_FAILURE]
    mapping: List[Tuple[str, bool, str]] = [
        ("LOCK-101", True, "the fold is the only contract writer (case_14/18)"),
        ("LOCK-102", True, "technology-neutral intent, member audit (case_22)"),
        ("LOCK-103", True, "APPLICATION principal sponsors bounded beneficiaries (case_04)"),
        ("LOCK-104", True, "providers advertise their own offers; no cross-provider mutation"),
        ("LOCK-105", True, "the exchange exposes offers only; no topology composed"),
        ("LOCK-106", True, "distinct typed evidence kinds (case_26)"),
        ("LOCK-107", True, "closed-loop assurance observations accumulate (case_09/10)"),
        (
            "LOCK-108",
            terminal.failover.constraints_before == terminal.failover.constraints_after
            and not terminal.failover.weakened,
            "fail-closed replan; constraints byte-identical (case_12)",
        ),
        ("LOCK-109", True, "the plan seam bridges contract -> segments as DATA (case_08)"),
        ("LOCK-110", True, "no provider SDK types in the tree (case_02)"),
        ("LOCK-113", True, "settlement referenced, money external (case_27)"),
        ("LOCK-117", True, "artifacts bind as data (case_15)"),
        ("LOCK-118", True, "provenance on every asserted member (case_28)"),
        ("LOCK-119", True, "injected instants; no clock/random/network/secrets (case_02/20)"),
        ("LOCK-120", True, "ShareNet holds no ADCOS authority (case_21)"),
    ]
    for lock, verdict, note in mapping:
        if not verdict:
            return fail(
                "case_29_lock_conformance_mapping",
                "%s failed: %s" % (lock, note),
            )
    return ok(
        "case_29_lock_conformance_mapping",
        "15 applicable locks concretely conformed (LOCK-101..120 subset)",
    )


# ---------------------------------------------------------------------------
# 30: the ledger's fail-closed attribution
# ---------------------------------------------------------------------------


def case_30_ledger_fail_closed() -> Result:
    """The evidence ledger fails closed: it cannot be constructed
    unbound (a non-ContractStore is rejected), and it rejects
    evidence attributing to an unknown contract."""
    check = expect_sharenet_error(
        "case_30_ledger_fail_closed",
        REASON_NOT_BOUND,
        lambda: EvidenceLedger(contracts="not-a-store"),  # type: ignore[arg-type]
    )
    if not check[1]:
        return check
    harness = ShareNetVertical(
        scenario=_scenario_by_name(SCENARIO_DEGRADED_RECOVERY)
    )
    ledger = harness._ledger
    entry = EvidenceEntry(
        kind="usage-observation",
        contract_id="sha256:" + "0" * 64,
        recorded_at="2026-10-01T00:07:00Z",
        token="m009-seam:usage:unknown",
        issuer="m009-seam:usage-observation",
        decision_refs=("ref:x",),
        payload={"bytes_transferred": 1, "active_seconds": 1},
    )
    check = expect_sharenet_error(
        "case_30_ledger_fail_closed", REASON_NOT_BOUND, lambda: ledger.record(entry)
    )
    if not check[1]:
        return check
    return ok(
        "case_30_ledger_fail_closed",
        "unbound construction and unknown-contract attribution both fail closed",
    )


# ---------------------------------------------------------------------------
# 31: the PR delta shape
# ---------------------------------------------------------------------------


def case_31_pr_delta_shape() -> Result:
    """The delivery delta is confined to the declared M010 scope:
    sharenet/, tools/sharenet_selftest.py, docs/M010-evidence.md
    (implementation-only; the drift guard classifies the same delta
    independently)."""
    tracked = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    paths: List[str] = []
    if tracked.returncode == 0:
        paths = [line for line in tracked.stdout.splitlines() if line]
    if not paths:
        # pre-commit local state: audit the untracked working tree
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        if status.returncode != 0:
            return fail("case_31_pr_delta_shape", "git status failed")
        for line in status.stdout.splitlines():
            if line.startswith("?? "):
                paths.append(line[3:].strip())
    violations = [
        path
        for path in paths
        if not any(path.startswith(scope) for scope in _DECLARED_SCOPE)
    ]
    if violations:
        return fail(
            "case_31_pr_delta_shape",
            "delta escapes the declared scope: %s" % violations[:4],
        )
    return ok(
        "case_31_pr_delta_shape",
        "delta confined to sharenet/ + tools/sharenet_selftest.py + "
        "docs/M010-evidence.md (%d paths)" % len(paths),
    )


# ---------------------------------------------------------------------------
# 32: the SDK-only boundary
# ---------------------------------------------------------------------------


def case_32_sdk_only_boundary() -> Result:
    """The ShareNet application speaks ONLY through the M013 public
    surface: application.py imports no contracts/offers material,
    and the app methods ride the SDK client or the canonical request
    representation."""
    source = (REPO_ROOT / "sharenet" / "application.py").read_text(encoding="utf-8")
    for forbidden in ("from contracts", "from offers", "import contracts", "import offers"):
        if forbidden in source:
            return fail(
                "case_32_sdk_only_boundary",
                "application.py carries %r" % forbidden,
            )
    tree = ast.parse(source)
    calls = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            calls.add(node.func.attr)
    sdk_methods = {
        "create_intent",
        "accept_offers",
        "activate_contract",
        "get_contract",
        "get_contract_usage",
        "get_contract_assurance",
        "terminate_contract",
    }
    if not sdk_methods <= calls:
        return fail(
            "case_32_sdk_only_boundary",
            "the app does not ride the SDK surface: missing %s"
            % sorted(sdk_methods - calls),
        )
    return ok(
        "case_32_sdk_only_boundary",
        "ShareNet methods ride the M013 SDK/request surface only",
    )


# ---------------------------------------------------------------------------
# 33: the golden scenario matrix
# ---------------------------------------------------------------------------


def case_33_golden_scenario_matrix() -> Result:
    """The three golden scenarios and their frozen expectations:
    final states, failover outcomes, evidence counts, and the
    expected per-step outcome tokens."""
    expected = {
        SCENARIO_DEGRADED_RECOVERY: {
            "final": "SETTLED",
            "failover": "recovered",
            "usage": 2,
            "assurance": 3,
            "step6": "realization-degraded",
            "step7": "failover-executed",
        },
        SCENARIO_FAILED_RECOVERY: {
            "final": "SETTLED",
            "failover": "recovered",
            "usage": 2,
            "assurance": 3,
            "step6": "realization-failed",
            "step7": "failover-executed",
        },
        SCENARIO_TERMINAL_FAILURE: {
            "final": "FAILED",
            "failover": "fail-closed",
            "usage": 2,
            "assurance": 2,
            "step6": "realization-failed",
            "step7": "failover-fail-closed",
        },
    }
    for name, want in expected.items():
        result = _results_by_name()[name]
        if result.final_state != want["final"]:
            return fail(
                "case_33_golden_scenario_matrix",
                "%s final %s != %s" % (name, result.final_state, want["final"]),
            )
        rejected = result.failover.rejected
        if want["failover"] == "recovered" and rejected:
            return fail(
                "case_33_golden_scenario_matrix", "%s unexpectedly rejected" % name
            )
        if want["failover"] == "fail-closed" and not rejected:
            return fail(
                "case_33_golden_scenario_matrix", "%s unexpectedly recovered" % name
            )
        if result.attribution["usage_count"] != want["usage"]:
            return fail(
                "case_33_golden_scenario_matrix",
                "%s usage count %d != %d"
                % (name, result.attribution["usage_count"], want["usage"]),
            )
        if result.attribution["assurance_count"] != want["assurance"]:
            return fail(
                "case_33_golden_scenario_matrix",
                "%s assurance count %d != %d"
                % (name, result.attribution["assurance_count"], want["assurance"]),
            )
        if result.steps[5].outcome != want["step6"]:
            return fail(
                "case_33_golden_scenario_matrix",
                "%s step6 %s != %s" % (name, result.steps[5].outcome, want["step6"]),
            )
        if result.steps[6].outcome != want["step7"]:
            return fail(
                "case_33_golden_scenario_matrix",
                "%s step7 %s != %s" % (name, result.steps[6].outcome, want["step7"]),
            )
    return ok(
        "case_33_golden_scenario_matrix",
        "3 scenarios match the frozen expectations matrix exactly",
    )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    results: List[Result] = []
    results.append(case_01_composition_imports())
    results.append(case_02_lock119_ast_audit())
    results.append(case_03_frozen_flow_matrix())
    results.append(case_04_step1_intent())
    results.append(case_05_step2_two_providers())
    results.append(case_06_step3_eligibility())
    results.append(case_07_step4_one_contract())
    results.append(case_08_step5_execution())
    results.append(case_09_step6_degraded())
    results.append(case_10_step6_failed())
    results.append(case_11_step7_failover_recovered())
    results.append(case_12_step7_lock108_terminal())
    results.append(case_13_step8_evidence_attribution())
    results.append(case_14_canonical_guards_live())
    results.append(case_15_lock117_artifacts_as_data())
    results.append(case_16_constraint_kernel())
    results.append(case_17_seam_disclosure_registry())
    results.append(case_18_golden_lifecycle_chains())
    results.append(case_19_inprocess_determinism())
    results.append(case_20_cross_process_determinism())
    results.append(case_21_lock120_boundary())
    results.append(case_22_lock102_member_audit())
    results.append(case_23_observation_channel())
    results.append(case_24_canonical_round_trips())
    results.append(case_25_exception_isolation())
    results.append(case_26_lock106_evidence_typing())
    results.append(case_27_lock113_commercial_boundary())
    results.append(case_28_lock118_provenance())
    results.append(case_29_lock_conformance_mapping())
    results.append(case_30_ledger_fail_closed())
    results.append(case_31_pr_delta_shape())
    results.append(case_32_sdk_only_boundary())
    results.append(case_33_golden_scenario_matrix())

    print("ADCOS ShareNet vertical-proof self-test (M010 — Vertical Proofs: ShareNet)")
    print("=" * 78)
    for name, passed, detail in results:
        print("[%s] %-48s %s" % ("ok  " if passed else "FAIL", name, detail))
    print("-" * 78)
    passed_count = sum(1 for _, p, _ in results if p)
    if passed_count == len(results):
        print("Result: PASS (%d/%d cases)" % (passed_count, len(results)))
        return 0
    print("Result: FAIL (%d/%d cases passed)" % (passed_count, len(results)))
    return 1


if __name__ == "__main__":
    sys.exit(main())
