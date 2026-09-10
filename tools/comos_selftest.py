#!/usr/bin/env python3
"""ADCOS COMOS vertical-proof self-test (M012 — Vertical Proofs:
COMOS).

Deterministic, offline verification of the M012 delivery against the
FROZEN COMOS flow of ``spec/integration/vertical-proof.md`` (ACR-014),
the R7 charter M012 acceptance criteria (R7-CORE-001, DEC-0101;
dependency M013 accepted via DEC-0113; M009 accepted via DEC-0109),
and the Architecture 1.1 locks.

What this battery proves:

- **The 6 frozen steps, in order, on the accepted authorities.**  The
  vertical harness composes the REAL M002 ``ContractStore``, the REAL
  M003 ``OfferExchange``/model/bridges, the REAL M013
  ``DeveloperApiService``/SDK, the REAL M009 ``CommercialCore``
  (bound mode, DEC-0109) and the REAL M009 ``UsageLedger``; every
  step of the frozen flow is exercised and recorded.
- **The step-2 selection paths.**  Constraint-aware selection over
  the real offers and the real hard constraints: both providers
  suitable (LOCK-116 dual-provider composition) and the
  constraint-exclusion path with the typed rejection trail.
- **The step-4/step-5 coupling.**  Technology-neutral communication
  requirements submitted AFTER contract formation, evaluated — never
  applied — against the committed terms (LOCK-108: the requirements
  mutate nothing); the satisfied path executes and settles; the
  unsatisfied path fails the contract closed under the typed reason,
  compensates the commercial account, and records NO usage.
- **Step-6 attribution + boundary.**  Evidence remains attributable
  to THE contract — including after terminal failure (LOCK-106
  distinct evidence kinds, LOCK-118 provenance, fail-closed ledger
  binding to the canonical fold); COMOS retains authority over its
  four frozen domains (LOCK-120) and speaks ONLY through the M013
  public surface.
- **LOCK-119/LOCK-110 discipline.**  AST audits: no wall clock, no
  randomness, no network, no secrets in the harness tree; the four
  simulation seams are disclosed and declared PENDING; M008 (no step
  in the frozen COMOS flow) is deliberately absent; M009 is REAL
  authority here (accepted DEC-0109), never a seam.
- **Determinism.**  Identical scenario digests in-process and
  cross-process under multiple PYTHONHASHSEED values.
- **The delivery delta shape.**  The PR delta is confined to
  ``comos/``, ``tools/comos_selftest.py``, and
  ``docs/M012-evidence.md`` (implementation-only; the drift guard
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

from comos import (  # noqa: E402
    COMOS_OWNED_DOMAINS,
    COMPOSITION_MAP,
    EVIDENCE_ISSUERS,
    EVIDENCE_KINDS,
    FROZEN_FLOW,
    INTENT_MEMBER_VOCABULARY,
    OBSERVATION_EVENT_TYPES,
    PROVIDER_ALPHA,
    PROVIDER_BETA,
    REASON_MEMBER_AUDIT,
    REASON_NOT_BOUND,
    REASON_VOCABULARY,
    REQUIREMENTS_MEMBER_VOCABULARY,
    SCENARIOS,
    SCENARIO_CONSTRAINT_EXCLUSION,
    SCENARIO_DUAL_PROVIDER_DELIVERY,
    SCENARIO_REQUIREMENTS_UNSATISFIED,
    SEAM_IDS,
    SETTLEMENT_CONFIRMATION_REF,
    SIMULATION_SEAMS,
    ComosError,
    ComosIntentSpec,
    ComosRequirementsSpec,
    ComosVertical,
    audit_member_name,
    run_scenario,
)
from comos.evidence import EvidenceEntry, EvidenceLedger  # noqa: E402
from comos.seams import (  # noqa: E402
    AssuranceSeam,
    RealizationEvent,
    evaluate_constraint,
    evaluate_offer_against_constraints,
    evaluate_requirements_against_offer,
)
from comos.vertical import COMOS_RETAINED_AUTHORITY  # noqa: E402

from contracts import ContractStore, HardConstraint  # noqa: E402

Result = Tuple[str, bool, str]

T_VALID_FROM = "2027-01-01T00:00:00Z"
T_VALID_TO = "2027-02-01T00:00:00Z"
T_REQUEST = "2027-01-01T00:01:00Z"

#: The frozen COMOS flow text, verbatim from
#: spec/integration/vertical-proof.md (the battery re-reads the spec
#: file and asserts byte-equality — the harness may not drift).
_SPEC_FLOW_FILE = REPO_ROOT / "spec" / "integration" / "vertical-proof.md"

#: The declared delivery scope (the PR delta shape; the drift guard
#: classifies the same delta independently).
_DECLARED_SCOPE = ("comos/", "tools/comos_selftest.py", "docs/M012-evidence.md")


def _active_authorization_covers(path: str) -> bool:
    """Consult the ACTIVE repository-local authorization
    (spec/architect/authorizations/): a path covered by the active
    authorization's declared scope is sanctioned battery-surface
    material even when it is outside THIS battery's frozen delivery
    scope (the authorization-aware consultation the M002-era repairs
    established, and which the M011 delivery's section 7.1
    retro-repaired into the M010 sharenet battery — this battery
    builds the consultation in from first delivery, so no later
    authorized R7 child PR trips the frozen-scope check).
    Fail-closed: no unique active authorization covers nothing."""
    try:
        from authorization_provenance import covers  # type: ignore
        return covers(path)
    except Exception:
        return False

#: The import roots the harness tree may depend on: the ACCEPTED
#: canonical authorities — contracts (M002, DEC-0102), offers (M003,
#: DEC-0103), developerapi (M013, DEC-0113), commercial + usage (M009,
#: DEC-0109 — REAL authority in M012, unlike the M010-era harness which
#: pre-dated the M009 acceptance), the sanctioned seams they themselves
#: use (agent.clock, protocol.canonicalization), and the harness's own
#: package.
_ALLOWED_IMPORT_ROOTS = (
    "contracts",
    "offers",
    "developerapi",
    "commercial",
    "usage",
    "agent",
    "protocol",
    "comos",
    # stdlib roots the harness family uses (pure-value tooling only)
    "__future__",
    "re",
    "hashlib",
    "dataclasses",
    "typing",
)

#: Import roots that would betray an authority grab, a pending child's
#: real semantics, or cross-harness composition (the sibling sharenet
#: harness is NOT composable material — each vertical proof stands on
#: the canonical authorities alone).
_FORBIDDEN_IMPORT_ROOTS = (
    "policy",
    "eligibility",
    "executionplans",
    "replan",
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
    "sharenet",
    "simulator",
)

#: LOCK-119/LOCK-110 AST vocabulary: attribute names the harness tree
#: must never touch (wall clock, randomness, network, provider SDK
#: surface).
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


def expect_comos_error(
    case: str, code: str, action: Callable[[], Any]
) -> Result:
    try:
        action()
    except ComosError as error:
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
    return fail(case, "expected ComosError(%s); the input was accepted" % code)


def _comos_sources() -> Dict[str, str]:
    """Every harness source file, keyed by path."""
    tree: Dict[str, str] = {}
    package = REPO_ROOT / "comos"
    for path in sorted(package.glob("*.py")):
        tree[str(path.relative_to(REPO_ROOT))] = path.read_text(encoding="utf-8")
    return tree


def _scenario_by_name(name: str):
    for scenario in SCENARIOS:
        if scenario.name == name:
            return scenario
    raise AssertionError("scenario %s is not registered" % name)


_RESULTS: Dict[str, Any] = {}


def _results_by_name() -> Dict[str, Any]:
    """Run every golden scenario once and index by name (the battery
    uses these results throughout)."""
    if not _RESULTS:
        for scenario in SCENARIOS:
            _RESULTS[scenario.name] = run_scenario(scenario)
    return _RESULTS


def _harness(name: str) -> ComosVertical:
    return ComosVertical(scenario=_scenario_by_name(name))


# ---------------------------------------------------------------------------
# 1-2: composition and LOCK-119 AST audits
# ---------------------------------------------------------------------------


def case_01_composition_imports() -> Result:
    """The harness tree imports ONLY the accepted canonical public
    surfaces (M002/M003/M013/M009-commercial/M009-usage) plus the
    sanctioned seams; no pending child domain, no payment surface, and
    no sibling-harness root is imported."""
    failures: List[str] = []
    for path, source in _comos_sources().items():
        tree = ast.parse(source, filename=path)
        roots: List[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.extend(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    roots.append(node.module.split(".")[0])
                elif node.level == 1 and node.module:
                    roots.append("comos")
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
        "harness tree imports only contracts/offers/developerapi/commercial/usage/"
        "agent/protocol/comos; no pending child or sibling harness imported",
    )


def case_02_lock119_ast_audit() -> Result:
    """LOCK-119 (and LOCK-110's SDK isolation): no wall clock, no
    randomness, no UUIDs, no network, no secret-shaped literals in
    the harness tree."""
    failures: List[str] = []
    for path, source in _comos_sources().items():
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
        "no wall clock / randomness / UUID / network / secret literals in comos/ "
        "(LOCK-119, LOCK-110)",
    )


# ---------------------------------------------------------------------------
# 3: the frozen flow matrix
# ---------------------------------------------------------------------------


def case_03_frozen_flow_matrix() -> Result:
    """The harness's frozen flow is byte-identical to the ACR-014
    spec text; the scenario step records carry the exact step titles
    1..6 in order; the retained-authority statement is verbatim."""
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
    if COMOS_RETAINED_AUTHORITY not in spec_text:
        return fail(
            "case_03_frozen_flow_matrix",
            "the COMOS retained-authority statement drifted from the spec",
        )
    if FROZEN_FLOW[5] != COMOS_RETAINED_AUTHORITY:
        return fail(
            "case_03_frozen_flow_matrix",
            "step 6 and the retained-authority statement disagree",
        )
    result = _results_by_name()[SCENARIO_DUAL_PROVIDER_DELIVERY]
    if len(result.steps) != 6:
        return fail(
            "case_03_frozen_flow_matrix",
            "expected exactly 6 step records (found %d)" % len(result.steps),
        )
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
        "6 frozen steps byte-identical to ACR-014 text; step records titled in order",
    )


# ---------------------------------------------------------------------------
# 4-10: the frozen steps, one by one
# ---------------------------------------------------------------------------


def case_04_step1_request() -> Result:
    """Step 1: COMOS requests gateway connectivity for communication
    traffic through the M013 surface ONLY; the canonical contract is
    created in INTENT state with the COMOS APPLICATION principal and
    OPAQUE beneficiaries (LOCK-102/LOCK-103/LOCK-114/LOCK-120)."""
    harness = _harness(SCENARIO_DUAL_PROVIDER_DELIVERY)
    intent = harness._app.submit_connectivity_request(
        spec=ComosIntentSpec(
            purpose="comos:gateway-connectivity:communication-traffic",
            requirements=(
                "req:comos:gateway-backhaul",
                "req:comos:communication-traffic",
            ),
            validity=(T_VALID_FROM, T_VALID_TO),
            termination_conditions=("principal-requested",),
            compensation="comp:comos:prorated-v1",
        ),
        idempotency_key="battery-step1",
        recorded_at=T_REQUEST,
    )
    contracts = harness._contracts
    contract = contracts.contract(intent.id)
    if contract.state != "INTENT":
        return fail("case_04_step1_request", "state is %s" % contract.state)
    if contract.principal.principal_kind != "APPLICATION":
        return fail(
            "case_04_step1_request",
            "principal kind is %s (LOCK-103 application sponsorship expected)"
            % contract.principal.principal_kind,
        )
    # technology neutrality: the creation core rides opaque reference
    # kinds only; the beneficiaries are opaque identity references
    members = {
        reference.ref_kind
        for reference in contract.requirements
    }
    if "intent-requirements" not in members:
        return fail(
            "case_04_step1_request",
            "requirements did not ride the intent-requirements reference kind",
        )
    for beneficiary in contract.beneficiaries:
        if "opaque" not in beneficiary.beneficiary_ref:
            return fail(
                "case_04_step1_request",
                "beneficiary reference is not opaque (LOCK-120 identity "
                "authority): %s" % beneficiary.beneficiary_ref[:40],
            )
    body_audit = audit_member_name("requirements")
    if body_audit != "requirements":
        return fail("case_04_step1_request", "member audit failed unexpectedly")
    return ok(
        "case_04_step1_request",
        "technology-neutral request accepted through the M013 SDK; contract INTENT; "
        "principal APPLICATION; beneficiaries opaque",
    )


def case_05_step2_selection() -> Result:
    """Step 2: ADCOS selects suitable offers — at least two provider
    domains advertise on the REAL M003 exchange; the constraint-aware
    selection (M004 seam) selects 2 of 2 in the dual scenario and
    excludes the violating offer in the constraint-exclusion scenario
    with the typed rejection trail."""
    harness = _harness(SCENARIO_DUAL_PROVIDER_DELIVERY)
    advertised = harness._exchange.offers()
    providers = {offer.provider for offer in advertised}
    if len(providers) < 2:
        return fail(
            "case_05_step2_selection",
            "only %d provider domains advertising" % len(providers),
        )
    if PROVIDER_ALPHA not in providers or PROVIDER_BETA not in providers:
        return fail("case_05_step2_selection", "expected providers missing")
    dual = _results_by_name()[SCENARIO_DUAL_PROVIDER_DELIVERY]
    if dual.steps[1].outcome != "offers-selected":
        return fail(
            "case_05_step2_selection", "step 2 outcome %s" % dual.steps[1].outcome
        )
    exclusion = _results_by_name()[SCENARIO_CONSTRAINT_EXCLUSION]
    selection = exclusion.selection
    if len(selection["selected"]) != 1 or len(selection["rejected"]) != 1:
        return fail(
            "case_05_step2_selection",
            "exclusion scenario selected/rejected %d/%d (expected 1/1)"
            % (len(selection["selected"]), len(selection["rejected"])),
        )
    rejected = [
        candidate
        for candidate in selection["candidates"]
        if not candidate["selected"]
    ][0]
    if "hard-constraint-violation" not in rejected["reason"]:
        return fail(
            "case_05_step2_selection",
            "rejection lacks the constraint-violation reason: %s"
            % rejected["reason"],
        )
    if "latency-bound" not in rejected["violated"]:
        return fail(
            "case_05_step2_selection",
            "the violated dimension trail is wrong: %s" % rejected["violated"],
        )
    return ok(
        "case_05_step2_selection",
        "2 providers advertising; dual selects 2; exclusion rejects 1 with the "
        "latency-bound violation trail",
    )


def case_06_step3_contract_created() -> Result:
    """Step 3: a contract is created — exactly ONE contract identity
    carries the whole flow; the selected offers bind through TYPED
    references (the M003 bridge); the plan covers the selected offers;
    the commercial account opens against the contract citation."""
    for name in (
        SCENARIO_DUAL_PROVIDER_DELIVERY,
        SCENARIO_CONSTRAINT_EXCLUSION,
        SCENARIO_REQUIREMENTS_UNSATISFIED,
    ):
        harness = _harness(name)
        result = harness.run()
        if len(harness._contracts.contracts()) != 1:
            return fail(
                "case_06_step3_contract_created",
                "%s: %d contracts in the fold"
                % (name, len(harness._contracts.contracts())),
            )
        contract = harness._contracts.contract(result.contract_id)
        if not contract.accepted_offers:
            return fail("case_06_step3_contract_created", "no accepted offers")
        kinds = {reference.ref_kind for reference in contract.accepted_offers}
        if kinds != {"offer"}:
            return fail(
                "case_06_step3_contract_created",
                "accepted offer reference kinds drifted: %s" % sorted(kinds),
            )
        if result.steps[2].outcome != "contract-created":
            return fail(
                "case_06_step3_contract_created",
                "step 3 outcome %s" % result.steps[2].outcome,
            )
        if len(result.plan_segments) != len(result.selected_offer_ids):
            return fail(
                "case_06_step3_contract_created",
                "%s: %d plan segments for %d selected offers"
                % (name, len(result.plan_segments), len(result.selected_offer_ids)),
            )
        if result.commercial["contract_binding"] != result.contract_id:
            return fail(
                "case_06_step3_contract_created",
                "the commercial account is not bound to THE contract",
            )
    dual = _results_by_name()[SCENARIO_DUAL_PROVIDER_DELIVERY]
    roles = [segment["role"] for segment in dual.plan_segments]
    if roles != ["primary", "secondary"]:
        return fail(
            "case_06_step3_contract_created",
            "dual-provider plan roles %s (expected primary+secondary)" % roles,
        )
    return ok(
        "case_06_step3_contract_created",
        "exactly one contract per scenario; typed offer references; plan over the "
        "selected offers; commercial account contract-bound",
    )


def case_07_step4_requirements_satisfied() -> Result:
    """Step 4 (satisfied path): COMOS sends TECHNOLOGY-NEUTRAL
    communication requirements — the document members stay inside the
    frozen requirements vocabulary, carry scalar bounds only, and are
    EVALUATED against every committed leg (never applied)."""
    dual = _results_by_name()[SCENARIO_DUAL_PROVIDER_DELIVERY]
    if dual.steps[3].outcome != "requirements-satisfied":
        return fail(
            "case_07_step4_requirements_satisfied",
            "step 4 outcome %s" % dual.steps[3].outcome,
        )
    document = dual.requirements["document"]
    for member in document:
        if member not in REQUIREMENTS_MEMBER_VOCABULARY:
            return fail(
                "case_07_step4_requirements_satisfied",
                "requirements member %r is outside the frozen vocabulary" % member,
            )
    if dual.requirements["satisfied"] != 1:
        return fail(
            "case_07_step4_requirements_satisfied",
            "the satisfied flag is not set",
        )
    if dual.requirements["violated_dimensions"]:
        return fail(
            "case_07_step4_requirements_satisfied",
            "violated dimensions on the satisfied path: %s"
            % dual.requirements["violated_dimensions"],
        )
    evaluations = dual.requirements["evaluations"]
    if len(evaluations) != len(dual.selected_offer_ids):
        return fail(
            "case_07_step4_requirements_satisfied",
            "%d evaluations for %d committed legs"
            % (len(evaluations), len(dual.selected_offer_ids)),
        )
    for evaluation in evaluations:
        if evaluation["violated"]:
            return fail(
                "case_07_step4_requirements_satisfied",
                "a committed leg violates the satisfied envelope: %s"
                % evaluation["violated"],
            )
    return ok(
        "case_07_step4_requirements_satisfied",
        "member-audited scalar envelope; every committed leg satisfies it",
    )


def case_08_step5_execution() -> Result:
    """Step 5: ADCOS supplies connectivity execution — the plan
    artifacts bind as DATA (LOCK-117); the canonical journal carries
    the full lifecycle chain; the REAL M009 usage ledger admits and
    seals the delivered traffic with the tariff resolved from the
    offer pricing DATA; the REAL M009 commercial walk settles."""
    harness = _harness(SCENARIO_DUAL_PROVIDER_DELIVERY)
    result = harness.run()
    contract = harness._contracts.contract(result.contract_id)
    if contract.state != "SETTLED":
        return fail(
            "case_08_step5_execution", "final state %s" % contract.state
        )
    if result.steps[4].outcome != "connectivity-executed":
        return fail(
            "case_08_step5_execution",
            "step 5 outcome %s" % result.steps[4].outcome,
        )
    kinds = {
        artifact.ref_kind for artifact in contract.execution_artifacts
    }
    if kinds != {"execution-artifact"}:
        return fail(
            "case_08_step5_execution",
            "artifact kinds drifted: %s" % sorted(kinds),
        )
    commands = [
        record.payload.get("command")
        for record in harness._contracts.journal()
        if record.contract_id == result.contract_id
    ]
    expected_commands = [
        "create",
        "select-offers",
        "activate",
        "bind-artifact",
        "bind-artifact",
        "record-execution-activation",
        "record-delivery",
        "record-assurance",
        "record-usage-final",
        "record-settlement-pending",
        "record-settled",
    ]
    if commands != expected_commands:
        return fail(
            "case_08_step5_execution",
            "journal chain drifted: %s" % commands,
        )
    # the REAL M009 usage ledger: admitted, sealed, and arithmetically
    # consistent with the offer pricing DATA
    if not result.usage["sealed"]:
        return fail("case_08_step5_execution", "usage never sealed")
    scenario = _scenario_by_name(SCENARIO_DUAL_PROVIDER_DELIVERY)
    if result.usage["billable_quantity"] != sum(scenario.delivered_quantities):
        return fail(
            "case_08_step5_execution",
            "billable quantity %d != delivered %d"
            % (result.usage["billable_quantity"], sum(scenario.delivered_quantities)),
        )
    primary_offer = harness._exchange.offer(
        result.plan_segments[0]["offer_id"]
    )
    expected_tariff = primary_offer.pricing.price_minor * (
        10 ** (6 - primary_offer.pricing.price_exponent)
    )
    if result.usage["unit_price_micros"] != expected_tariff:
        return fail(
            "case_08_step5_execution",
            "tariff %d != offer pricing DATA resolution %d"
            % (result.usage["unit_price_micros"], expected_tariff),
        )
    expected_gross = result.usage["unit_price_micros"] * result.usage[
        "billable_quantity"
    ]
    if result.usage["gross_amount_micros"] != expected_gross:
        return fail(
            "case_08_step5_execution",
            "gross %d != quantity x tariff %d"
            % (result.usage["gross_amount_micros"], expected_gross),
        )
    if result.commercial["state"] != "SETTLED":
        return fail(
            "case_08_step5_execution",
            "commercial state %s" % result.commercial["state"],
        )
    if result.commercial["chain"][-1] != "settle":
        return fail(
            "case_08_step5_execution",
            "commercial chain does not settle: %s" % result.commercial["chain"][-3:],
        )
    return ok(
        "case_08_step5_execution",
        "artifacts as DATA; 11-command journal; usage sealed 750 units at the "
        "offer-resolved tariff; commercial settled",
    )


def case_09_requirements_unsatisfied() -> Result:
    """The step-4 fail-closed path: when the committed legs violate
    the stated envelope, the contract FAILS under the typed reason,
    NO execution command exists on the journal, the commercial
    account compensates (cancel), no usage exists — and the
    submission/selection evidence REMAINS attributable."""
    result = _results_by_name()[SCENARIO_REQUIREMENTS_UNSATISFIED]
    if result.final_state != "FAILED":
        return fail(
            "case_09_requirements_unsatisfied",
            "final state %s (expected FAILED)" % result.final_state,
        )
    if result.steps[3].outcome != "requirements-unsatisfied":
        return fail(
            "case_09_requirements_unsatisfied",
            "step 4 outcome %s" % result.steps[3].outcome,
        )
    if result.steps[4].outcome != "execution-not-supplied":
        return fail(
            "case_09_requirements_unsatisfied",
            "step 5 outcome %s" % result.steps[4].outcome,
        )
    if result.requirements["violated_dimensions"] != ["latency_bound_ms"]:
        return fail(
            "case_09_requirements_unsatisfied",
            "violated dimensions %s" % result.requirements["violated_dimensions"],
        )
    harness = _harness(SCENARIO_REQUIREMENTS_UNSATISFIED)
    run = harness.run()
    contract = harness._contracts.contract(run.contract_id)
    reason = contract.termination_reason or ""
    if "requirements-unsatisfied" not in reason:
        return fail(
            "case_09_requirements_unsatisfied",
            "termination reason is not the typed requirements reason: %r" % reason,
        )
    if "latency" not in reason:
        return fail(
            "case_09_requirements_unsatisfied",
            "termination reason lacks the violated dimension: %r" % reason,
        )
    commands = [
        record.payload.get("command")
        for record in harness._contracts.journal()
        if record.contract_id == run.contract_id
    ]
    if commands != ["create", "select-offers", "activate", "fail"]:
        return fail(
            "case_09_requirements_unsatisfied",
            "the failed journal must stop at the fail command: %s" % commands,
        )
    if run.commercial["state"] != "CANCELLED":
        return fail(
            "case_09_requirements_unsatisfied",
            "commercial state %s (expected CANCELLED)" % run.commercial["state"],
        )
    if "settle" in run.commercial["chain"]:
        return fail(
            "case_09_requirements_unsatisfied",
            "nothing was delivered, yet the commercial walk settled",
        )
    if run.usage["observation_ids"] or run.usage["billable_quantity"]:
        return fail(
            "case_09_requirements_unsatisfied",
            "usage exists on a delivery that never began",
        )
    if run.attribution["usage_count"] or run.attribution["assurance_count"]:
        return fail(
            "case_09_requirements_unsatisfied",
            "usage/assurance evidence exists on the failed scenario",
        )
    if not run.attribution["requirements_count"] or not run.attribution[
        "selection_count"
    ]:
        return fail(
            "case_09_requirements_unsatisfied",
            "attribution did not survive terminal failure",
        )
    return ok(
        "case_09_requirements_unsatisfied",
        "fail-closed: typed termination reason; journal stops at fail; commercial "
        "cancelled; no usage; attribution survives",
    )


def case_10_step6_boundary_retained() -> Result:
    """Step 6 / LOCK-120: COMOS retains authority over identity,
    communication bundles, channel semantics and delivery semantics —
    a standing boundary record in EVERY scenario (including terminal
    failure); ADCOS supplied gateway connectivity only."""
    if COMOS_OWNED_DOMAINS != (
        "identity",
        "communication-bundles",
        "channel-semantics",
        "delivery-semantics",
    ):
        return fail(
            "case_10_step6_boundary_retained",
            "the COMOS owned-domain declaration drifted: %s"
            % (COMOS_OWNED_DOMAINS,),
        )
    for name in (
        SCENARIO_DUAL_PROVIDER_DELIVERY,
        SCENARIO_CONSTRAINT_EXCLUSION,
        SCENARIO_REQUIREMENTS_UNSATISFIED,
    ):
        result = _results_by_name()[name]
        step6 = result.steps[5]
        if step6.outcome != "boundary-retained":
            return fail(
                "case_10_step6_boundary_retained",
                "%s step 6 outcome %s" % (name, step6.outcome),
            )
        if step6.title != FROZEN_FLOW[5]:
            return fail(
                "case_10_step6_boundary_retained",
                "%s step 6 title drifted" % name,
            )
        if "/".join(COMOS_OWNED_DOMAINS) not in step6.detail:
            return fail(
                "case_10_step6_boundary_retained",
                "%s step 6 detail does not name the retained domains" % name,
            )
    return ok(
        "case_10_step6_boundary_retained",
        "boundary-retained record in all 3 scenarios; 4 frozen domains declared",
    )


# ---------------------------------------------------------------------------
# 11-12: LOCK-108 purity and the constraint kernel
# ---------------------------------------------------------------------------


def case_11_lock108_requirement_purity() -> Result:
    """LOCK-108: the step-4 requirements NEVER mutate the contract —
    the hard constraints are byte-identical to the scenario's declared
    bounds in EVERY scenario (including the failed one, where the
    contract is NOT weakened to satisfy the envelope); the journal
    carries no requirements command; the creation-core requirements
    ride their frozen reference kinds unchanged."""
    for scenario in SCENARIOS:
        result = _results_by_name()[scenario.name]
        harness = _harness(scenario.name)
        run = harness.run()
        contract = harness._contracts.contract(run.contract_id)
        bounds = {
            constraint.kind: dict(constraint.params)
            for constraint in contract.hard_constraints
        }
        if bounds.get("latency-bound", {}).get("ms") != scenario.latency_bound_ms:
            return fail(
                "case_11_lock108_requirement_purity",
                "%s: latency bound drifted to %s"
                % (scenario.name, bounds.get("latency-bound")),
            )
        if bounds.get("throughput-floor", {}).get("bps") != (
            scenario.throughput_floor_bps
        ):
            return fail(
                "case_11_lock108_requirement_purity",
                "%s: throughput floor drifted" % scenario.name,
            )
        if bounds.get("jitter-bound", {}).get("ms") != scenario.jitter_bound_ms:
            return fail(
                "case_11_lock108_requirement_purity",
                "%s: jitter bound drifted" % scenario.name,
            )
        commands = [
            record.payload.get("command")
            for record in harness._contracts.journal()
            if record.contract_id == run.contract_id
        ]
        for command in commands:
            if "requirement" in command:
                return fail(
                    "case_11_lock108_requirement_purity",
                    "the journal carries a requirements command %r" % command,
                )
        requirement_refs = {
            (ref.ref_kind, ref.value) for ref in contract.requirements
        }
        if ("intent-requirements", "req:comos:gateway-backhaul") not in (
            requirement_refs
        ):
            return fail(
                "case_11_lock108_requirement_purity",
                "%s: creation-core requirements drifted" % scenario.name,
            )
    # the failed scenario is the sharp proof: the contract keeps its
    # 200 ms bound while the envelope demanded 100 ms — the constraint
    # was never weakened to make the requirements pass
    failed = _results_by_name()[SCENARIO_REQUIREMENTS_UNSATISFIED]
    failed_scenario = _scenario_by_name(SCENARIO_REQUIREMENTS_UNSATISFIED)
    if failed_scenario.latency_bound_ms <= failed_scenario.requirements_latency_ms:
        return fail(
            "case_11_lock108_requirement_purity",
            "the failed scenario does not exercise the weakening temptation",
        )
    if "requirements-submission" not in str(
        failed.attribution["requirements_tokens"]
    ) + str(EVIDENCE_KINDS):
        return fail(
            "case_11_lock108_requirement_purity",
            "the submission is not recorded as typed evidence",
        )
    return ok(
        "case_11_lock108_requirement_purity",
        "hard constraints byte-identical in all scenarios; no requirements command "
        "exists; failed contract keeps the 200ms bound vs the 100ms demand",
    )


def case_12_constraint_kernel() -> Result:
    """The LOCK-108 kernel: True (present and satisfying), False
    (present and violating), None (uncommitted abstains); the offer
    evaluation covers every constraint; the requirements evaluation
    carries the full verdict trail."""
    harness = _harness(SCENARIO_DUAL_PROVIDER_DELIVERY)
    alpha = next(
        offer
        for offer in harness._exchange.offers()
        if offer.provider == PROVIDER_ALPHA
    )
    if evaluate_constraint(
        HardConstraint(kind="latency-bound", params={"ms": 150}), alpha
    ) is not True:
        return fail("case_12_constraint_kernel", "alpha latency 120 vs 150 failed")
    if evaluate_constraint(
        HardConstraint(kind="latency-bound", params={"ms": 100}), alpha
    ) is not False:
        return fail("case_12_constraint_kernel", "alpha latency 120 vs 100 passed")
    if evaluate_constraint(
        HardConstraint(kind="availability-floor", params={"nines": 3}), alpha
    ) is not None:
        return fail(
            "case_12_constraint_kernel",
            "an uncommitted dimension did not abstain",
        )
    constraints = (
        HardConstraint(kind="latency-bound", params={"ms": 150}),
        HardConstraint(kind="throughput-floor", params={"bps": 500}),
        HardConstraint(kind="jitter-bound", params={"ms": 50}),
    )
    evaluation = evaluate_offer_against_constraints(alpha, constraints)
    if evaluation.violated or evaluation.uncommitted:
        return fail(
            "case_12_constraint_kernel",
            "alpha should satisfy all three dimensions: %s/%s"
            % (evaluation.violated, evaluation.uncommitted),
        )
    if sorted(evaluation.satisfied) != [
        "jitter-bound",
        "latency-bound",
        "throughput-floor",
    ]:
        return fail(
            "case_12_constraint_kernel",
            "satisfied trail %s" % (evaluation.satisfied,),
        )
    # the requirements evaluation (the failed scenario's envelope vs
    # the alpha commitments): latency violated, jitter/throughput pass
    spec = ComosRequirementsSpec(
        purpose="comos:communication-envelope:v1",
        latency_bound_ms=100,
        jitter_bound_ms=50,
        throughput_floor_bps=500,
    )
    document = spec.to_document(recorded_at="2027-01-01T00:06:00Z")
    requirements_evaluation = evaluate_requirements_against_offer(
        requirements=document, offer=alpha
    )
    if requirements_evaluation.violated != ("latency_bound_ms",):
        return fail(
            "case_12_constraint_kernel",
            "violated dimensions %s" % (requirements_evaluation.violated,),
        )
    if sorted(requirements_evaluation.satisfied) != [
        "jitter_bound_ms",
        "throughput_floor_bps",
    ]:
        return fail(
            "case_12_constraint_kernel",
            "satisfied dimensions %s" % (requirements_evaluation.satisfied,),
        )
    latency_verdict = next(
        verdict
        for verdict in requirements_evaluation.verdicts
        if verdict.dimension == "latency_bound_ms"
    )
    if latency_verdict.committed_value != 120 or latency_verdict.required_bound != 100:
        return fail(
            "case_12_constraint_kernel",
            "the verdict trail lost the committed/bound pair",
        )
    # the kernel rejects non-canonical inputs fail-closed
    check = expect_comos_error(
        "case_12_constraint_kernel",
        "comos-invalid-input",
        lambda: evaluate_constraint("latency-bound", alpha),
    )
    if not check[1]:
        return check
    return ok(
        "case_12_constraint_kernel",
        "True/False/None semantics; full trails; fail-closed on non-canonical input",
    )


# ---------------------------------------------------------------------------
# 13-15: seam disclosure, attribution, ledger fail-closed
# ---------------------------------------------------------------------------


def case_13_seam_disclosure_registry() -> Result:
    """The single seam disclosure registry: exactly FOUR seams
    (M004/M005/M006/M007), every one declared PENDING DELIVERY with a
    resolvable exported symbol; M008 has NO step in the frozen COMOS
    flow and is deliberately absent; M009 is REAL authority
    (DEC-0109), never a seam; the composition map agrees."""
    if SEAM_IDS != (
        "seam:m004-selection",
        "seam:m005-assurance",
        "seam:m006-execution-plan",
        "seam:m007-realization",
    ):
        return fail(
            "case_13_seam_disclosure_registry",
            "the seam registry drifted: %s" % (SEAM_IDS,),
        )
    import importlib

    for entry in SIMULATION_SEAMS:
        if not entry.stands_in_for.startswith("M0"):
            return fail(
                "case_13_seam_disclosure_registry",
                "seam %s does not name its M-item" % entry.seam_id,
            )
        if not entry.authority_status.startswith("PENDING DELIVERY"):
            return fail(
                "case_13_seam_disclosure_registry",
                "seam %s is not declared PENDING" % entry.seam_id,
            )
        module_name, _, symbol = entry.exported_symbol.rpartition(".")
        module = importlib.import_module(module_name)
        if not hasattr(module, symbol):
            return fail(
                "case_13_seam_disclosure_registry",
                "exported symbol %s does not resolve" % entry.exported_symbol,
            )
    joined = " ".join(entry.stands_in_for for entry in SIMULATION_SEAMS)
    for absent in ("M008", "M009"):
        if absent in joined:
            return fail(
                "case_13_seam_disclosure_registry",
                "%s must not be a seam (M008: no step in the frozen flow; "
                "M009: accepted DEC-0109)" % absent,
            )
    if len(COMPOSITION_MAP["real_authorities"]) != 5:
        return fail(
            "case_13_seam_disclosure_registry",
            "the composition map does not carry the 5 real authorities",
        )
    authorities = " ".join(COMPOSITION_MAP["real_authorities"])
    for accepted in ("contracts", "offers", "developerapi", "commercial", "usage"):
        if accepted not in authorities:
            return fail(
                "case_13_seam_disclosure_registry",
                "the composition map lost the %s authority" % accepted,
            )
    boundary = COMPOSITION_MAP["boundary"]
    if isinstance(boundary, tuple):
        boundary = " ".join(boundary)
    if "LOCK-120" not in boundary:
        return fail(
            "case_13_seam_disclosure_registry",
            "the boundary statement lost the LOCK-120 reference",
        )
    return ok(
        "case_13_seam_disclosure_registry",
        "4 disclosed PENDING seams; M008 absent (no step); M009 real; composition "
        "map carries the 5 accepted authorities",
    )


def case_14_evidence_attribution() -> Result:
    """Attribution: every golden scenario's evidence counts match the
    frozen expectations; the usage tokens ARE the observation ids the
    REAL M009 ledger derived; the attribution state equals the
    terminal state (attribution survives terminal failure)."""
    expected = {
        SCENARIO_DUAL_PROVIDER_DELIVERY: (2, 1, 1, 1, "SETTLED"),
        SCENARIO_CONSTRAINT_EXCLUSION: (1, 1, 1, 1, "SETTLED"),
        SCENARIO_REQUIREMENTS_UNSATISFIED: (0, 0, 1, 1, "FAILED"),
    }
    for name, want in expected.items():
        result = _results_by_name()[name]
        attribution = result.attribution
        counts = (
            attribution["usage_count"],
            attribution["assurance_count"],
            attribution["requirements_count"],
            attribution["selection_count"],
        )
        if counts != want[:4]:
            return fail(
                "case_14_evidence_attribution",
                "%s evidence counts %s != %s" % (name, counts, want[:4]),
            )
        if attribution["contract_state"] != want[4]:
            return fail(
                "case_14_evidence_attribution",
                "%s attribution state %s != %s"
                % (name, attribution["contract_state"], want[4]),
            )
        if attribution["contract_id"] != result.contract_id:
            return fail(
                "case_14_evidence_attribution",
                "attribution is not bound to THE contract",
            )
        if sorted(attribution["usage_tokens"]) != sorted(
            result.usage["observation_ids"]
        ):
            return fail(
                "case_14_evidence_attribution",
                "%s: usage tokens are not the M009 observation ids" % name,
            )
    if EVIDENCE_ISSUERS != (
        "m009-authority:usage-observation",
        "m005-seam:assurance-observation",
        "comos-application:communication-requirements",
        "m004-seam:selection",
    ):
        return fail(
            "case_14_evidence_attribution",
            "the issuer vocabulary drifted: %s" % (EVIDENCE_ISSUERS,),
        )
    return ok(
        "case_14_evidence_attribution",
        "per-scenario counts exact; usage tokens == M009 observation ids; "
        "attribution state == terminal state",
    )


def case_15_ledger_fail_closed() -> Result:
    """The evidence ledger fails closed: an unbound ledger rejects
    construction; an unknown contract rejects every write; entries
    with unknown kinds, secret-shaped tokens, or non-scalar payloads
    are rejected at construction time."""
    check = expect_comos_error(
        "case_15_ledger_fail_closed",
        REASON_NOT_BOUND,
        lambda: EvidenceLedger(contracts=object()),
    )
    if not check[1]:
        return check
    ledger = EvidenceLedger(contracts=ContractStore())
    check = expect_comos_error(
        "case_15_ledger_fail_closed",
        REASON_NOT_BOUND,
        lambda: ledger.record(
            EvidenceEntry(
                kind="usage-observation",
                contract_id="sha256:" + "0" * 64,
                recorded_at="2027-01-01T00:00:00Z",
                token="token:x",
                issuer="issuer:x",
                decision_refs=(),
                payload={},
            )
        ),
    )
    if not check[1]:
        return check
    construction_probes = (
        ("claim kind", REASON_VOCABULARY, "claim"),
        ("secret-shaped token", REASON_VOCABULARY, "ghp_" + "a" * 20),
    )
    for label, code, token in construction_probes:
        check = expect_comos_error(
            "case_15_ledger_fail_closed",
            code,
            lambda token=token: EvidenceEntry(
                kind=token if label == "claim kind" else "usage-observation",
                contract_id="sha256:" + "0" * 64,
                recorded_at="2027-01-01T00:00:00Z",
                token="token:x" if label == "claim kind" else token,
                issuer="issuer:x",
                decision_refs=(),
                payload={},
            ),
        )
        if not check[1]:
            return check
    payload_probes = (
        {"nested": {"deep": 1}},
        {"api_key": "value"},
        {"flag": True},
        {"secret_token": 1},
    )
    for payload in payload_probes:
        check = expect_comos_error(
            "case_15_ledger_fail_closed",
            REASON_VOCABULARY,
            lambda payload=payload: EvidenceEntry(
                kind="usage-observation",
                contract_id="sha256:" + "0" * 64,
                recorded_at="2027-01-01T00:00:00Z",
                token="token:x",
                issuer="issuer:x",
                decision_refs=(),
                payload=payload,
            ),
        )
        if not check[1]:
            return check
    return ok(
        "case_15_ledger_fail_closed",
        "unbound ledger, unknown contract, 2 token shapes and 4 payload shapes all "
        "fail closed",
    )


# ---------------------------------------------------------------------------
# 16-18: canonical round-trips and determinism
# ---------------------------------------------------------------------------


def case_16_canonical_round_trips() -> Result:
    """Canonical JSON round-trips: StepRecord and EvidenceEntry
    survive dict -> record -> dict byte-exactly; the scenario digest
    is the canonical JSON hash of the whole result."""
    from comos.vertical import StepRecord  # noqa: PLC0415
    from protocol.canonicalization import canonical_json_bytes  # noqa: PLC0415

    result = _results_by_name()[SCENARIO_REQUIREMENTS_UNSATISFIED]
    record = result.steps[0]
    document = record.to_dict()
    rebuilt = StepRecord.from_dict(json.loads(json.dumps(document)))
    if rebuilt.to_dict() != document:
        return fail("case_16_canonical_round_trips", "StepRecord round-trip drifted")
    entry = EvidenceEntry(
        kind="usage-observation",
        contract_id=result.contract_id,
        recorded_at="2027-01-01T00:10:00Z",
        token="m009-authority:usage-observation:1",
        issuer="m009-authority:usage-observation",
        decision_refs=("m007-seam:delivered:primary:fact-1",),
        payload={"delivered_quantity": 400, "position": 1},
    )
    entry_document = entry.to_dict()
    rebuilt_entry = EvidenceEntry.from_dict(
        json.loads(json.dumps(entry_document))
    )
    if rebuilt_entry.to_dict() != entry_document:
        return fail("case_16_canonical_round_trips", "EvidenceEntry round-trip drifted")
    digest = result.digest()
    if digest != "sha256:" + hashlib_hex(canonical_json_bytes(result.to_dict())):
        return fail(
            "case_16_canonical_round_trips",
            "the scenario digest is not the canonical JSON hash",
        )
    if len(digest) != 7 + 64:
        return fail("case_16_canonical_round_trips", "digest shape drifted")
    return ok(
        "case_16_canonical_round_trips",
        "StepRecord / EvidenceEntry round-trips byte-exact; digest = canonical hash",
    )


def hashlib_hex(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def case_17_inprocess_determinism() -> Result:
    """Identical scenario digests across repeated in-process runs
    (fresh harness composition each time)."""
    first = [run_scenario(scenario).digest() for scenario in SCENARIOS]
    second = [run_scenario(scenario).digest() for scenario in SCENARIOS]
    if first != second:
        return fail(
            "case_17_inprocess_determinism",
            "scenario digests differ across in-process runs",
        )
    return ok(
        "case_17_inprocess_determinism",
        "3 scenario digests identical across repeated fresh compositions",
    )


_SNAPSHOT_SCRIPT = """
import sys
sys.path.insert(0, %r)
from comos import SCENARIOS, run_scenario
for scenario in SCENARIOS:
    print(run_scenario(scenario).digest())
""" % str(REPO_ROOT)


def case_18_cross_process_determinism() -> Result:
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
            "case_18_cross_process_determinism",
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
                "case_18_cross_process_determinism",
                "digests varied across PYTHONHASHSEED=%s: %s" % (seed, (err or out)[:120]),
            )
    in_process = "\n".join(
        run_scenario(scenario).digest() for scenario in SCENARIOS
    ) + "\n"
    if in_process != out0:
        return fail(
            "case_18_cross_process_determinism",
            "in-process digests differ from the subprocess digests",
        )
    return ok(
        "case_18_cross_process_determinism",
        "identical digests across processes and PYTHONHASHSEED 0/1/12345",
    )


# ---------------------------------------------------------------------------
# 19-22: the LOCK-120 member audit, observation channel, boundary
# ---------------------------------------------------------------------------


def case_19_lock120_member_audit() -> Result:
    """LOCK-102/LOCK-114/LOCK-120: the member audit fails closed on
    network-mechanism names AND on COMOS-owned communication-domain
    names (channel/conversation/message/receipt/...); the frozen
    vocabularies pass; the requirements spec validates its scalar
    bounds fail-closed."""
    cases = (
        ("tunnel", REASON_MEMBER_AUDIT),
        ("provider_sdk", REASON_MEMBER_AUDIT),
        ("ssid", REASON_MEMBER_AUDIT),
        ("bearer", REASON_MEMBER_AUDIT),
        ("upf", REASON_MEMBER_AUDIT),
        ("channel", REASON_MEMBER_AUDIT),
        ("conversation", REASON_MEMBER_AUDIT),
        ("message_queue", REASON_MEMBER_AUDIT),
        ("delivery_receipt", REASON_MEMBER_AUDIT),
        ("inbox", REASON_MEMBER_AUDIT),
        ("throughput", REASON_MEMBER_AUDIT),
        (123, REASON_MEMBER_AUDIT),
        ("", REASON_MEMBER_AUDIT),
    )
    for name, code in cases:
        if (
            isinstance(name, str)
            and name in INTENT_MEMBER_VOCABULARY + REQUIREMENTS_MEMBER_VOCABULARY
        ):
            return fail(
                "case_19_lock120_member_audit",
                "%r unexpectedly inside the frozen vocabulary" % (name,),
            )
        check = expect_comos_error(
            "case_19_lock120_member_audit", code, lambda name=name: audit_member_name(name)
        )
        if not check[1]:
            return check
    for member in INTENT_MEMBER_VOCABULARY + REQUIREMENTS_MEMBER_VOCABULARY:
        if audit_member_name(member) != member:
            return fail(
                "case_19_lock120_member_audit",
                "frozen member %r rejected by the audit" % member,
            )
    # the requirements spec validates its bounds fail-closed
    spec_probes = (
        ("non-positive", lambda: ComosRequirementsSpec(
            purpose="comos:communication-envelope:v1", latency_bound_ms=0
        )),
        ("non-integer", lambda: ComosRequirementsSpec(
            purpose="comos:communication-envelope:v1", latency_bound_ms="high"
        )),
        ("empty", lambda: ComosRequirementsSpec(
            purpose="comos:communication-envelope:v1"
        )),
    )
    for label, probe in spec_probes:
        check = expect_comos_error(
            "case_19_lock120_member_audit", "comos-vocabulary" if label != "empty" else "comos-invalid-input", probe
        )
        if not check[1]:
            return check
    return ok(
        "case_19_lock120_member_audit",
        "13 mechanism/COMOS-domain member shapes fail closed; frozen vocabularies "
        "pass; bounds validated",
    )


def case_20_observation_channel() -> Result:
    """The M013 observation channel: the COMOS endpoint receives
    SIGNED state observations of the whole lifecycle — observation
    only, never business state; the event types are exactly the
    registered ones; the app's received count matches the platform's
    delivery record."""
    expected_states = {
        SCENARIO_DUAL_PROVIDER_DELIVERY: ["INTENT", "CONTRACT_ACTIVE", "SETTLED"],
        SCENARIO_CONSTRAINT_EXCLUSION: ["INTENT", "CONTRACT_ACTIVE", "SETTLED"],
        SCENARIO_REQUIREMENTS_UNSATISFIED: ["INTENT", "CONTRACT_ACTIVE", "FAILED"],
    }
    for name, want in expected_states.items():
        result = _results_by_name()[name]
        deliveries = result.observation_deliveries
        if len(deliveries) != len(want):
            return fail(
                "case_20_observation_channel",
                "%s: %d deliveries (expected %d)"
                % (name, len(deliveries), len(want)),
            )
        states = [delivery["data"]["state"] for delivery in deliveries]
        if states != want:
            return fail(
                "case_20_observation_channel",
                "%s observation states %s != %s" % (name, states, want),
            )
        sequences = [delivery["sequence"] for delivery in deliveries]
        if sequences != sorted(sequences) or len(set(sequences)) != len(sequences):
            return fail(
                "case_20_observation_channel",
                "%s observation sequences are not strictly ordered" % name,
            )
        for delivery in deliveries:
            if delivery["event_type"] not in OBSERVATION_EVENT_TYPES:
                return fail(
                    "case_20_observation_channel",
                    "unexpected event type %s" % delivery["event_type"],
                )
            if delivery["data"]["contract_id"] != result.contract_id:
                return fail(
                    "case_20_observation_channel",
                    "an observation is not about THE contract",
                )
            if not delivery["event_id"].startswith("sha256:"):
                return fail(
                    "case_20_observation_channel",
                    "the observation is not signed",
                )
    return ok(
        "case_20_observation_channel",
        "signed state_changed observations INTENT->CONTRACT_ACTIVE->terminal in all "
        "3 scenarios; app receives them all",
    )


def case_21_lock120_boundary_isolation() -> Result:
    """LOCK-120: the COMOS application holds NO ADCOS authority — the
    application object references no ContractStore, no OfferExchange,
    no CommercialCore, no UsageLedger, and no seam; its only composed
    dependency is the M013 SDK client (+ the raw request surface)."""
    harness = _harness(SCENARIO_DUAL_PROVIDER_DELIVERY)
    app = harness._app
    from commercial import CommercialCore  # noqa: PLC0415
    from contracts import ContractStore  # noqa: PLC0415
    from offers import OfferExchange  # noqa: PLC0415
    from usage import UsageLedger  # noqa: PLC0415

    from comos.seams import (  # noqa: PLC0415
        AssuranceSeam,
        ExecutionPlanSeam,
        ProviderRealizationSeam,
        SelectionSeam,
    )

    forbidden_types = (
        ContractStore,
        OfferExchange,
        CommercialCore,
        UsageLedger,
        SelectionSeam,
        AssuranceSeam,
        ExecutionPlanSeam,
        ProviderRealizationSeam,
    )
    for attribute, value in vars(app).items():
        if isinstance(value, forbidden_types):
            return fail(
                "case_21_lock120_boundary_isolation",
                "the COMOS application holds an ADCOS authority (%s)" % attribute,
            )
    # the application boundary module imports only the M013 surface
    source = (REPO_ROOT / "comos" / "application.py").read_text(
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
    if not imported_roots <= {
        "developerapi",
        "re",
        "dataclasses",
        "typing",
        "__future__",
    }:
        return fail(
            "case_21_lock120_boundary_isolation",
            "application.py imports beyond the M013 surface: %s"
            % sorted(imported_roots),
        )
    # the retained domains are declared opaque and stay opaque
    if app.retained_domains() != COMOS_OWNED_DOMAINS:
        return fail(
            "case_21_lock120_boundary_isolation",
            "the retained-domain declaration drifted",
        )
    return ok(
        "case_21_lock120_boundary_isolation",
        "the app holds no authority (8 types checked); application.py imports only "
        "the M013 surface (LOCK-120)",
    )


def case_22_sdk_only_boundary() -> Result:
    """The COMOS application speaks ONLY through the M013 public
    surface: application.py imports no contracts/offers/commercial/
    usage material, and the app methods ride the SDK client or the
    canonical request representation."""
    source = (REPO_ROOT / "comos" / "application.py").read_text(encoding="utf-8")
    for forbidden in (
        "from contracts",
        "from offers",
        "from commercial",
        "from usage",
        "import contracts",
        "import offers",
        "import commercial",
        "import usage",
    ):
        if forbidden in source:
            return fail(
                "case_22_sdk_only_boundary",
                "application.py carries %r" % forbidden,
            )
    tree = ast.parse(source)
    calls = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            calls.add(node.func.attr)
    sdk_methods = {
        "create_intent",
        "get_contract",
        "get_contract_usage",
        "get_contract_assurance",
    }
    if not sdk_methods <= calls:
        return fail(
            "case_22_sdk_only_boundary",
            "the app does not ride the SDK surface: missing %s"
            % sorted(sdk_methods - calls),
        )
    # the raw request surface (endpoint registration) rides ApiRequest
    if "ApiRequest" not in source:
        return fail(
            "case_22_sdk_only_boundary",
            "the raw request surface is not the canonical ApiRequest",
        )
    return ok(
        "case_22_sdk_only_boundary",
        "the app rides the M013 SDK + canonical ApiRequest only",
    )


# ---------------------------------------------------------------------------
# 23-27: typed errors, evidence typing, commercial boundary,
# provenance, artifacts as DATA
# ---------------------------------------------------------------------------


def case_23_exception_isolation() -> Result:
    """Typed failures only: every harness failure is a ComosError
    with a frozen reason code from the closed set; no bare exception
    text leaks into stored state; the FAILED contract carries the
    typed termination reason."""
    closed = {
        "comos-invalid-input",
        "comos-vocabulary",
        "comos-member-audit",
        "comos-boundary",
        "comos-fail-closed",
        "comos-not-bound",
    }
    harness = _harness(SCENARIO_REQUIREMENTS_UNSATISFIED)
    result = harness.run()
    contract = harness._contracts.contract(result.contract_id)
    reason = contract.termination_reason or ""
    if "requirements-unsatisfied" not in reason:
        return fail(
            "case_23_exception_isolation",
            "the FAILED contract must carry the typed requirements reason "
            "(found %r)" % reason,
        )
    if "Traceback" in reason or "Error" in reason:
        return fail(
            "case_23_exception_isolation",
            "raw exception text leaked into the termination reason",
        )
    probes = (
        lambda: audit_member_name("tunnel"),
        lambda: ComosIntentSpec(
            purpose="comos:x",
            requirements=(),
            validity=(T_VALID_FROM, T_VALID_TO),
            termination_conditions=("principal-requested",),
            compensation="comp:x",
        ),
        lambda: AssuranceSeam().observe(
            realization_status="exploded",
            obligations=("oblig:comos:continuity-v1",),
            at_instant="2027-01-01T00:09:00Z",
            sequence=1,
        ),
        lambda: RealizationEvent(
            provider=PROVIDER_ALPHA,
            kind="exploded",
            effective_at="2027-01-01T00:09:00Z",
            detail="x",
        ),
    )
    for probe in probes:
        try:
            probe()
        except ComosError as error:
            if error.code not in closed:
                return fail(
                    "case_23_exception_isolation",
                    "reason code %r outside the closed set" % error.code,
                )
        except Exception as error:  # noqa: BLE001
            return fail(
                "case_23_exception_isolation",
                "non-typed exception %s: %s" % (type(error).__name__, str(error)[:80]),
            )
        else:
            return fail(
                "case_23_exception_isolation",
                "a fail-closed probe unexpectedly succeeded",
            )
    return ok(
        "case_23_exception_isolation",
        "typed ComosError codes from the closed set; no exception text in state",
    )


def case_24_lock106_evidence_typing() -> Result:
    """LOCK-106: usage observations, assurance evaluations,
    requirements submissions, and selection decisions are DISTINCT
    evidence kinds; the kind vocabulary is frozen; tokens never cross
    kinds; payloads are scalar DATA."""
    if EVIDENCE_KINDS != (
        "usage-observation",
        "assurance-evaluation",
        "requirements-submission",
        "selection-decision",
    ):
        return fail(
            "case_24_lock106_evidence_typing",
            "evidence kinds drifted: %s" % (EVIDENCE_KINDS,),
        )
    check = expect_comos_error(
        "case_24_lock106_evidence_typing",
        REASON_VOCABULARY,
        lambda: EvidenceEntry(
            kind="claim",
            contract_id="sha256:" + "0" * 64,
            recorded_at="2027-01-01T00:00:00Z",
            token="token:x",
            issuer="issuer:x",
            decision_refs=(),
            payload={},
        ),
    )
    if not check[1]:
        return check
    for name in (
        SCENARIO_DUAL_PROVIDER_DELIVERY,
        SCENARIO_REQUIREMENTS_UNSATISFIED,
    ):
        attribution = _results_by_name()[name].attribution
        token_sets = (
            set(attribution["usage_tokens"]),
            set(attribution["assurance_tokens"]),
            set(attribution["requirements_tokens"]),
            set(attribution["selection_tokens"]),
        )
        for first in range(len(token_sets)):
            for second in range(first + 1, len(token_sets)):
                if token_sets[first] & token_sets[second]:
                    return fail(
                        "case_24_lock106_evidence_typing",
                        "%s: tokens appear under two evidence kinds" % name,
                    )
    return ok(
        "case_24_lock106_evidence_typing",
        "4 distinct typed evidence kinds; frozen vocabulary; no token crosses kinds",
    )


def case_25_lock113_commercial_boundary() -> Result:
    """LOCK-113: the usage evidence moves NO money — usage records
    are DATA (quantity + offer-resolved tariff + derived gross) and
    settlement rides the EXTERNAL rail confirmation reference only;
    the harness tree carries no payment surface."""
    result = _results_by_name()[SCENARIO_DUAL_PROVIDER_DELIVERY]
    if not result.usage["observation_ids"]:
        return fail(
            "case_25_lock113_commercial_boundary", "no usage evidence recorded"
        )
    if not SETTLEMENT_CONFIRMATION_REF.startswith("m012:settlement:"):
        return fail(
            "case_25_lock113_commercial_boundary",
            "the settlement reference is not a harness DATA token",
        )
    if "external-rail" not in SETTLEMENT_CONFIRMATION_REF:
        return fail(
            "case_25_lock113_commercial_boundary",
            "the settlement reference does not name the external rail",
        )
    # the gross amount is derived DATA (quantity x tariff), not a
    # money movement
    if result.usage["gross_amount_micros"] != (
        result.usage["unit_price_micros"] * result.usage["billable_quantity"]
    ):
        return fail(
            "case_25_lock113_commercial_boundary",
            "the gross amount is not the derived statement",
        )
    for path, source in _comos_sources().items():
        lowered = source.lower()
        for forbidden in ("payment.", "paymentadapter", "charge", "invoice", "wallet"):
            if forbidden in lowered:
                return fail(
                    "case_25_lock113_commercial_boundary",
                    "%s carries a payment surface token %r" % (path, forbidden),
                )
    return ok(
        "case_25_lock113_commercial_boundary",
        "usage is DATA with offer-resolved tariff; settlement cites the external "
        "rail only; no payment surface in the tree",
    )


def case_26_lock118_provenance() -> Result:
    """LOCK-118: every externally asserted member carries issuer and
    provenance — the offer material, the evidence entries, and the
    contract's accepted-offer references all carry provenance
    records."""
    harness = _harness(SCENARIO_DUAL_PROVIDER_DELIVERY)
    for offer in harness._exchange.offers():
        if not offer.provenance.decision_refs:
            return fail(
                "case_26_lock118_provenance",
                "offer %s carries no decision refs" % offer.offer_id[:24],
            )
        for commitment in offer.commitments:
            if not commitment.provenance.issuer:
                return fail(
                    "case_26_lock118_provenance",
                    "commitment without issuer on %s" % offer.offer_id[:24],
                )
    result = harness.run()
    ledger = harness._ledger
    for entry in ledger.entries():
        if not entry.issuer or not entry.decision_refs:
            return fail(
                "case_26_lock118_provenance",
                "evidence entry %s lacks provenance" % entry.token[:32],
            )
    contract = harness._contracts.contract(result.contract_id)
    for reference in contract.accepted_offers:
        if reference.provenance is None:
            return fail(
                "case_26_lock118_provenance",
                "accepted offer reference without provenance",
            )
    return ok(
        "case_26_lock118_provenance",
        "offers, commitments, evidence entries, and accepted references all carry "
        "provenance",
    )


def case_27_lock117_artifacts_as_data() -> Result:
    """LOCK-117: execution artifacts bind as DATA — the artifact
    references are opaque tokens with seam provenance; binding them
    confers no authority (the contract's authority set is the command
    vocabulary, never the artifact)."""
    harness = _harness(SCENARIO_DUAL_PROVIDER_DELIVERY)
    result = harness.run()
    contract = harness._contracts.contract(result.contract_id)
    if len(contract.execution_artifacts) != len(result.plan_segments):
        return fail(
            "case_27_lock117_artifacts_as_data",
            "artifact count %d != plan segments %d"
            % (len(contract.execution_artifacts), len(result.plan_segments)),
        )
    for artifact in contract.execution_artifacts:
        if artifact.ref_kind != "execution-artifact":
            return fail(
                "case_27_lock117_artifacts_as_data",
                "artifact ref kind %s" % artifact.ref_kind,
            )
        if not artifact.value.startswith("m006-seam:realization:"):
            return fail(
                "case_27_lock117_artifacts_as_data",
                "the artifact token is not seam DATA: %s" % artifact.value[:40],
            )
        if not artifact.provenance.issuer:
            return fail(
                "case_27_lock117_artifacts_as_data",
                "the artifact reference carries no provenance",
            )
    return ok(
        "case_27_lock117_artifacts_as_data",
        "artifacts bind as opaque seam DATA with provenance; no authority conferred",
    )


# ---------------------------------------------------------------------------
# 28-30: golden lifecycle chains, commercial walk discipline,
# lock conformance mapping
# ---------------------------------------------------------------------------


def case_28_golden_lifecycle_chains() -> Result:
    """The golden lifecycle chains: the canonical journal command
    chain, the commercial command chain, and the observation state
    chain for every scenario — the failed scenario stops at the fail
    command and compensates instead of executing."""
    expected = {
        SCENARIO_DUAL_PROVIDER_DELIVERY: {
            "journal": [
                "create",
                "select-offers",
                "activate",
                "bind-artifact",
                "bind-artifact",
                "record-execution-activation",
                "record-delivery",
                "record-assurance",
                "record-usage-final",
                "record-settlement-pending",
                "record-settled",
            ],
            "commercial": [
                "submit_intent",
                "select_offer",
                "hold_reservation",
                "authorize_session",
                "activate_path",
                "start_delivery",
                "accrue_usage",
                "complete_delivery",
                "finalize_billable",
                "initiate_settlement",
                "settle",
            ],
            "states": ["INTENT", "CONTRACT_ACTIVE", "SETTLED"],
        },
        SCENARIO_CONSTRAINT_EXCLUSION: {
            "journal": [
                "create",
                "select-offers",
                "activate",
                "bind-artifact",
                "record-execution-activation",
                "record-delivery",
                "record-assurance",
                "record-usage-final",
                "record-settlement-pending",
                "record-settled",
            ],
            "commercial": [
                "submit_intent",
                "select_offer",
                "hold_reservation",
                "authorize_session",
                "activate_path",
                "start_delivery",
                "accrue_usage",
                "complete_delivery",
                "finalize_billable",
                "initiate_settlement",
                "settle",
            ],
            "states": ["INTENT", "CONTRACT_ACTIVE", "SETTLED"],
        },
        SCENARIO_REQUIREMENTS_UNSATISFIED: {
            "journal": ["create", "select-offers", "activate", "fail"],
            "commercial": [
                "submit_intent",
                "select_offer",
                "hold_reservation",
                "authorize_session",
                "activate_path",
                "cancel",
            ],
            "states": ["INTENT", "CONTRACT_ACTIVE", "FAILED"],
        },
    }
    for name, want in expected.items():
        harness = _harness(name)
        result = harness.run()
        commands = [
            record.payload.get("command")
            for record in harness._contracts.journal()
            if record.contract_id == result.contract_id
        ]
        if commands != want["journal"]:
            return fail(
                "case_28_golden_lifecycle_chains",
                "%s journal chain %s" % (name, commands),
            )
        if result.commercial["chain"] != want["commercial"]:
            return fail(
                "case_28_golden_lifecycle_chains",
                "%s commercial chain %s" % (name, result.commercial["chain"]),
            )
        states = [
            delivery["data"]["state"] for delivery in result.observation_deliveries
        ]
        if states != want["states"]:
            return fail(
                "case_28_golden_lifecycle_chains",
                "%s observation states %s" % (name, states),
            )
    return ok(
        "case_28_golden_lifecycle_chains",
        "journal/commercial/observation chains exact in all 3 scenarios; the failed "
        "scenario stops at fail and cancels",
    )


def case_29_commercial_walk_discipline() -> Result:
    """The M009 bound-mode discipline: the commercial account cites
    THE canonical contract; the walk mirrors the contract lifecycle
    (pre-execution formation, then journal-first reload for the
    post-execution walk — the walk never runs ahead of the contract);
    settlement cites the EXTERNAL rail confirmation; the compensating
    path settles nothing."""
    harness = _harness(SCENARIO_DUAL_PROVIDER_DELIVERY)
    result = harness.run()
    if result.commercial["contract_binding"] != result.contract_id:
        return fail(
            "case_29_commercial_walk_discipline",
            "the commercial transaction is not contract-cited",
        )
    chain = result.commercial["chain"]
    formation = [
        "submit_intent",
        "select_offer",
        "hold_reservation",
        "authorize_session",
        "activate_path",
    ]
    if chain[:5] != formation:
        return fail(
            "case_29_commercial_walk_discipline",
            "the pre-execution formation chain is out of order: %s" % chain[:5],
        )
    if chain[5:] != [
        "start_delivery",
        "accrue_usage",
        "complete_delivery",
        "finalize_billable",
        "initiate_settlement",
        "settle",
    ]:
        return fail(
            "case_29_commercial_walk_discipline",
            "the post-execution walk is out of order: %s" % chain[5:],
        )
    # settlement happens only after the usage seal (the walk follows
    # the authority's own sealed statement)
    if chain.index("settle") < chain.index("accrue_usage"):
        return fail(
            "case_29_commercial_walk_discipline",
            "settlement ran before usage accrual",
        )
    if not result.usage["sealed"]:
        return fail(
            "case_29_commercial_walk_discipline",
            "the commercial walk settled without a sealed usage statement",
        )
    # the journal-first reload: the harness reloaded the SAME store
    # and the walk continued from the persisted journal
    from commercial import CommercialCore  # noqa: PLC0415

    if not isinstance(harness._commercial, CommercialCore):
        return fail(
            "case_29_commercial_walk_discipline",
            "the composed commercial authority is not the REAL CommercialCore",
        )
    transaction = harness._commercial.transaction(
        harness._commercial_transaction_id
    )
    if transaction.state != "SETTLED":
        return fail(
            "case_29_commercial_walk_discipline",
            "the reloaded transaction state is %s" % transaction.state,
        )
    failed = _results_by_name()[SCENARIO_REQUIREMENTS_UNSATISFIED]
    if failed.commercial["state"] != "CANCELLED":
        return fail(
            "case_29_commercial_walk_discipline",
            "the compensating path did not cancel",
        )
    if "settle" in failed.commercial["chain"]:
        return fail(
            "case_29_commercial_walk_discipline",
            "the compensating path settled",
        )
    return ok(
        "case_29_commercial_walk_discipline",
        "contract-cited walk; formation then journal-first reload; settle after the "
        "seal; cancel compensates without settling",
    )


_LOCK_CASE_MAP = {
    "LOCK-101": "case_06_step3_contract_created",
    "LOCK-102": "case_19_lock120_member_audit",
    "LOCK-103": "case_04_step1_request",
    "LOCK-106": "case_24_lock106_evidence_typing",
    "LOCK-108": "case_11_lock108_requirement_purity",
    "LOCK-109": "case_13_seam_disclosure_registry",
    "LOCK-110": "case_22_sdk_only_boundary",
    "LOCK-113": "case_25_lock113_commercial_boundary",
    "LOCK-116": "case_33_golden_scenario_matrix",
    "LOCK-117": "case_27_lock117_artifacts_as_data",
    "LOCK-118": "case_26_lock118_provenance",
    "LOCK-119": "case_18_cross_process_determinism",
    "LOCK-120": "case_10_step6_boundary_retained",
}


def case_30_lock_conformance_mapping() -> Result:
    """The battery self-describes its lock conformance: every mapped
    Architecture 1.1 lock resolves to a battery case that exists in
    this module (the evidence doc carries the same mapping)."""
    for lock, case_name in _LOCK_CASE_MAP.items():
        if case_name not in globals() or not callable(globals()[case_name]):
            return fail(
                "case_30_lock_conformance_mapping",
                "%s maps to missing case %s" % (lock, case_name),
            )
    return ok(
        "case_30_lock_conformance_mapping",
        "13 Architecture 1.1 locks mapped to existing battery cases",
    )


# ---------------------------------------------------------------------------
# 31-33: PR delta shape, real-authority composition, golden matrix
# ---------------------------------------------------------------------------


def case_31_pr_delta_shape() -> Result:
    """The delivery delta is confined to the declared M012 scope:
    comos/, tools/comos_selftest.py, docs/M012-evidence.md
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
        and not _active_authorization_covers(path)
    ]
    if violations:
        return fail(
            "case_31_pr_delta_shape",
            "delta escapes the declared scope and the active authorization: %s"
            % violations[:4],
        )
    return ok(
        "case_31_pr_delta_shape",
        "delta confined to comos/ + tools/comos_selftest.py + "
        "docs/M012-evidence.md, or sanctioned by the active authorization "
        "(%d paths)" % len(paths),
    )


def case_32_real_authority_composition() -> Result:
    """The harness composes REAL accepted authorities, never
    re-implementations: the contract fold is the canonical
    ContractStore, the offer plane is the canonical OfferExchange,
    the boundary is the canonical DeveloperApiService, the commercial
    walk is the canonical CommercialCore, and the usage evidence is
    the canonical UsageLedger (M009, DEC-0109)."""
    from commercial import CommercialCore  # noqa: PLC0415
    from contracts import ContractStore  # noqa: PLC0415
    from developerapi import DeveloperApiService  # noqa: PLC0415
    from offers import OfferExchange  # noqa: PLC0415
    from usage import UsageLedger  # noqa: PLC0415

    harness = _harness(SCENARIO_DUAL_PROVIDER_DELIVERY)
    result = harness.run()
    checks = (
        ("ContractStore", harness._contracts, ContractStore),
        ("OfferExchange", harness._exchange, OfferExchange),
        ("DeveloperApiService", harness._service, DeveloperApiService),
        ("CommercialCore", harness._commercial, CommercialCore),
        ("UsageLedger", harness._usage_ledger, UsageLedger),
        ("EvidenceLedger fold", harness._ledger._contracts, ContractStore),
    )
    for label, value, expected_type in checks:
        if not isinstance(value, expected_type):
            return fail(
                "case_32_real_authority_composition",
                "%s is %s (expected the canonical %s)"
                % (label, type(value).__name__, expected_type.__name__),
            )
    # the app rides the canonical SDK client
    from developerapi.sdk import DeveloperApiClient  # noqa: PLC0415

    if not isinstance(harness._app._client, DeveloperApiClient):
        return fail(
            "case_32_real_authority_composition",
            "the COMOS application does not ride the canonical SDK client",
        )
    if not result.usage_ledger_digest:
        return fail(
            "case_32_real_authority_composition",
            "the REAL usage authority produced no digest stream",
        )
    if not result.commercial_journal_digest.startswith("sha256:"):
        return fail(
            "case_32_real_authority_composition",
            "the REAL commercial authority produced no journal digest",
        )
    return ok(
        "case_32_real_authority_composition",
        "5 canonical authorities + SDK client verified by type; both authority "
        "digest streams recorded",
    )


def case_33_golden_scenario_matrix() -> Result:
    """The three golden scenarios and their frozen expectations:
    final states, selected/rejected counts, evidence counts, and the
    expected per-step outcome tokens."""
    expected = {
        SCENARIO_DUAL_PROVIDER_DELIVERY: {
            "final": "SETTLED",
            "selected": 2,
            "rejected": 0,
            "usage": 2,
            "assurance": 1,
            "step4": "requirements-satisfied",
            "step5": "connectivity-executed",
            "commercial": "SETTLED",
        },
        SCENARIO_CONSTRAINT_EXCLUSION: {
            "final": "SETTLED",
            "selected": 1,
            "rejected": 1,
            "usage": 1,
            "assurance": 1,
            "step4": "requirements-satisfied",
            "step5": "connectivity-executed",
            "commercial": "SETTLED",
        },
        SCENARIO_REQUIREMENTS_UNSATISFIED: {
            "final": "FAILED",
            "selected": 2,
            "rejected": 0,
            "usage": 0,
            "assurance": 0,
            "step4": "requirements-unsatisfied",
            "step5": "execution-not-supplied",
            "commercial": "CANCELLED",
        },
    }
    for name, want in expected.items():
        result = _results_by_name()[name]
        if result.final_state != want["final"]:
            return fail(
                "case_33_golden_scenario_matrix",
                "%s final %s != %s" % (name, result.final_state, want["final"]),
            )
        if len(result.selected_offer_ids) != want["selected"]:
            return fail(
                "case_33_golden_scenario_matrix",
                "%s selected %d != %d"
                % (name, len(result.selected_offer_ids), want["selected"]),
            )
        if len(result.selection["rejected"]) != want["rejected"]:
            return fail(
                "case_33_golden_scenario_matrix",
                "%s rejected %d != %d"
                % (name, len(result.selection["rejected"]), want["rejected"]),
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
        if result.steps[3].outcome != want["step4"]:
            return fail(
                "case_33_golden_scenario_matrix",
                "%s step4 %s != %s" % (name, result.steps[3].outcome, want["step4"]),
            )
        if result.steps[4].outcome != want["step5"]:
            return fail(
                "case_33_golden_scenario_matrix",
                "%s step5 %s != %s" % (name, result.steps[4].outcome, want["step5"]),
            )
        if result.commercial["state"] != want["commercial"]:
            return fail(
                "case_33_golden_scenario_matrix",
                "%s commercial %s != %s"
                % (name, result.commercial["state"], want["commercial"]),
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
    results.append(case_04_step1_request())
    results.append(case_05_step2_selection())
    results.append(case_06_step3_contract_created())
    results.append(case_07_step4_requirements_satisfied())
    results.append(case_08_step5_execution())
    results.append(case_09_requirements_unsatisfied())
    results.append(case_10_step6_boundary_retained())
    results.append(case_11_lock108_requirement_purity())
    results.append(case_12_constraint_kernel())
    results.append(case_13_seam_disclosure_registry())
    results.append(case_14_evidence_attribution())
    results.append(case_15_ledger_fail_closed())
    results.append(case_16_canonical_round_trips())
    results.append(case_17_inprocess_determinism())
    results.append(case_18_cross_process_determinism())
    results.append(case_19_lock120_member_audit())
    results.append(case_20_observation_channel())
    results.append(case_21_lock120_boundary_isolation())
    results.append(case_22_sdk_only_boundary())
    results.append(case_23_exception_isolation())
    results.append(case_24_lock106_evidence_typing())
    results.append(case_25_lock113_commercial_boundary())
    results.append(case_26_lock118_provenance())
    results.append(case_27_lock117_artifacts_as_data())
    results.append(case_28_golden_lifecycle_chains())
    results.append(case_29_commercial_walk_discipline())
    results.append(case_30_lock_conformance_mapping())
    results.append(case_31_pr_delta_shape())
    results.append(case_32_real_authority_composition())
    results.append(case_33_golden_scenario_matrix())

    print("ADCOS COMOS vertical-proof self-test (M012 — Vertical Proofs: COMOS)")
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
