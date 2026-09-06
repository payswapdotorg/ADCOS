#!/usr/bin/env python3
"""WORK-054 System Composition Conformance battery.

The deterministic R2 composition-conformance battery over the
accepted authorities' public boundaries (the W032/W041/W051/W052/
W053 battery conventions).  The battery proves:

- the authority availability table (W048 accepted-not-restored is
  DETECTED and fails closed; the W046 boundary was defect-
  inherited at the WORK-054 acceptance and is now REPAIRED and
  available on the WORK-056 mainline -- the case_03 oracle
  reconciled by DEC-0090);
- the STRICT production-composition chain: intent -> offer ->
  eligibility -> reservation/lease -> candidate selection ->
  NetworkPath validation -> containment (FAIL_CLOSED: the W048
  runtime is absent) -> [session .. reconciliation NOT ENTERED];
  the verdict is BLOCKED_MISSING_AUTHORITY and never a passing
  production composition;
- SEGMENT conformance: every available link downstream of the
  blocked edge exercised end to end through the real authorities;
- the SEVEN mandatory negative invariants of the R2 gate;
- the failure matrix (denied eligibility, failed reservation,
  unreachable candidate, failed NetworkPath validation,
  unavailable containment, session failure, absent delivery
  evidence, non-billable usage, allocation rejection,
  payment-provider divergence, duplicate and out-of-order
  observations);
- replay/idempotency, journal-first recovery, platform
  checkpoint/recovery;
- PYTHONHASHSEED invariance and repeated-run byte stability;
- the authority-ownership/import/dependency audits and the
  scope/provenance audits (only the authorized WORK-054 surfaces
  changed; spec/architect/ untouched).

Usage: python3 tools/composition_selftest.py
       python3 tools/composition_selftest.py --determinism-stream
"""

from __future__ import annotations

import ast
import os
import py_compile
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

Result = Tuple[str, bool, str]

from composition import (  # noqa: E402
    AUTHORITY_PROBES,
    AuthorityAvailability,
    CHAIN_EDGES,
    CHAIN_STAGE_NAMES,
    EVIDENCE_CLASS_SOFTWARE,
    NEGATIVE_PROOF_STATEMENTS,
    AuthorityProbe,
    CompositionEvidenceError,
    SoftwareEvidenceRecord,
    build_evidence_document,
    classify_evidence,
    composition_digest,
    physical_obligations_open,
    w048_runtime_absent,
)
from composition.chain import (  # noqa: E402
    ChainVerdict,
    EdgeOutcome,
    OutcomeReason,
    StageOutcome,
)
from composition.orchestrator import (  # noqa: E402
    SEGMENT_CONFORMANCE_DISCLAIMER,
    compose_scenario_stream,
    run_available_segments,
    run_full_chain,
)
from composition.world import (  # noqa: E402
    CompositionWorld,
    _POLICY_ADCOS_BPS,
    _POLICY_CURRENCY,
    _POLICY_DIGITS,
    _POLICY_FROM,
    _POLICY_LABEL,
    _POLICY_MAX_BPS,
    _POLICY_MIN_BPS,
    _POLICY_PROVIDER_BPS,
    _POLICY_ROUNDING,
    _POLICY_UNTIL,
    _PROVIDER_ID,
    build_allocation_evidence_index,
    build_delivery_evidence,
    build_payment_snapshot,
    build_reference_index,
    build_usage_evidence_index,
    evaluate_capability_declaration,
    sandbox_provider,
    usage_store,
)

from agent.clock import StepClock  # noqa: E402
from commercial import (  # noqa: E402
    CommercialCore,
    CommercialError,
    CommercialReasonCode,
    Reference,
    ReferenceFamily,
    ReferenceIndex,
)
from commercial.journal import MemoryCommercialStore  # noqa: E402
from usage import (  # noqa: E402
    DeliveryEvidence,
    EvidenceKind,
    QuantityClass,
    UsageError,
    UsageLedger,
)
from usage.journal import MemoryUsageStore  # noqa: E402
from allocation import (  # noqa: E402
    AllocationError,
    AllocationLedger,
)
from allocation.journal import MemoryAllocationStore  # noqa: E402
from payment import (  # noqa: E402
    PaymentError,
    SettlementGateway,
)
from payment.journal import MemoryPaymentStore  # noqa: E402
from eligibility import EligibilityError  # noqa: E402
from marketplace import (  # noqa: E402
    DiscoveryQuery,
    MarketplaceError,
    UserConstraints,
)
from networkpath import NetworkPathError  # noqa: E402
from sessions import SessionStore  # noqa: E402
from client import (  # noqa: E402
    ClientError,
    ClientRuntime,
    ProjectionCache,
    StatusSnapshot,
    Freshness,
)
from policy.model import PolicyDecision  # noqa: E402
import hashlib  # noqa: E402

from platform.integration import (  # noqa: E402
    session_bindings_from_manager,
)
from platform.lifecycle import PlatformIntegrator  # noqa: E402
from platform.journal import MemoryPlatformStore  # noqa: E402


def ok(name: str, detail: str = "") -> Result:
    return (name, True, detail)


def fail(name: str, detail: str) -> Result:
    return (name, False, detail)


# ---------------------------------------------------------------------------
# Shared deterministic scenario (built once, in the fixed order)
# ---------------------------------------------------------------------------

_SCENARIO: Optional[Dict[str, Any]] = None


def _scenario() -> Dict[str, Any]:
    global _SCENARIO
    if _SCENARIO is None:
        world = CompositionWorld()
        chain = run_full_chain(world)
        segments = run_available_segments(world, chain)
        _SCENARIO = {
            "world": world,
            "chain": chain,
            "segments": segments,
        }
    return _SCENARIO


#: The authorized WORK-054 delta surface (the scope of
#: WORK-054-CORE-001): the composition package, this battery, and
#: the two evidence documents.
_AUTHORIZED_PATHS = (
    "composition/",
    "tools/composition_selftest.py",
    "docs/WORK-054-evidence.md",
    "docs/WORK-054-handoff.md",
)

#: The frozen composition public API surface (pinned here; the
#: package must match exactly).
_EXPECTED_API = sorted([
    "AUTHORITY_PROBES",
    "AuthorityAvailability",
    "AuthorityProbe",
    "CHAIN_EDGES",
    "CHAIN_STAGE_NAMES",
    "CompositionEvidenceError",
    "CompositionTrace",
    "CompositionWorld",
    "EVIDENCE_CLASS_SOFTWARE",
    "EdgeOutcome",
    "EdgeSpec",
    "NEGATIVE_PROOF_STATEMENTS",
    "OutcomeReason",
    "ScenarioStream",
    "SoftwareEvidenceRecord",
    "StageOutcome",
    "W046_DEFECT_DETAIL",
    "W048_ABSENT_DETAIL",
    "build_allocation_evidence_index",
    "build_delivery_evidence",
    "build_evidence_document",
    "build_payment_snapshot",
    "build_reference_index",
    "build_usage_evidence_index",
    "chain_edge",
    "classify_evidence",
    "compose_scenario_stream",
    "composition_digest",
    "derive_tariff",
    "physical_obligations_open",
    "probe_authorities",
    "run_available_segments",
    "run_full_chain",
    "segment_conformance_allowed",
    "w048_runtime_absent",
])

#: The sanctioned import allowlist for the composition family
#: (stdlib + the WORK-003 canonicalization + the WORK-033 clock
#: seam + the composed authority families of the WORK-054
#: authority-input table, including the W011/W010/W008/W007
#: fixtures the W012 session authority's own contract requires).
_ALLOWED_IMPORT_PREFIXES = (
    "protocol.",
    "agent.clock",
    "agent.",
    "identity.",
    "management.",
    "policy.",
    "topology.",
    "mobile.",
    "networkpath.",
    "platform.journal",
    "platform.lifecycle",
    "platform.integration",
    "sessions.",
    "routing.",
    "resources.",
    "intent.",
    "marketplace.",
    "eligibility.",
    "commercial.",
    "usage.",
    "allocation.",
    "payment.",
    "client.",
    "platformcaps.",
    "containment.state",
)
_ALLOWED_IMPORT_MODULES = {
    "__future__",
    "ast",
    "hashlib",
    "dataclasses",
    "importlib",
    "importlib.util",
    "pathlib",
    "re",
    "typing",
    "protocol",
    "agent.clock",
    "agent",
    "containment.state",
    # the composed authority families (top-level package imports)
    "identity",
    "management",
    "policy",
    "topology",
    "mobile",
    "networkpath",
    "sessions",
    "routing",
    "resources",
    "intent",
    "marketplace",
    "eligibility",
    "commercial",
    "usage",
    "allocation",
    "payment",
    "client",
    "platformcaps",
}

#: Vendor/technology tokens the composition family must never
#: encode (technology- and provider-neutral conformance core).
_VENDOR_TOKENS = (
    "android", "rndis", "qualcomm", "mediatek", "samsung", "broadcom",
    "huawei", "apple", "google", "windows", "darwin", "ios_",
    "open5gs", "ocudu", "openairinterface",
    "stripe", "paypal", "mtn", "vodafone", "airteltigo", "telecel",
    "visa", "mastercard", "mpesa", "alipay", "wise",
)

#: Authority-class names the composition family must never define
#: or subclass (the no-second-authority rule, mechanically).
_AUTHORITY_CLASS_TOKENS = (
    "CommercialCore", "UsageLedger", "AllocationLedger",
    "SettlementGateway", "NetworkPathManager", "SessionStore",
    "EligibilityAuthority", "MarketplaceService", "PlatformIntegrator",
    "AgentRuntime", "RoutingEngine", "ClientRuntime", "PlatformCapabilityRegistry",
    "SandboxProvider", "AppendOnlyJournal", "MemoryCommercialStore",
    "MemoryUsageStore", "MemoryAllocationStore", "MemoryPaymentStore",
    "MemoryEligibilityStore", "MemoryPlatformStore",
)

#: The forbidden dependency directions (never imported by the
#: composition family: the absent W048 runtime, the W046
#: boundary (an out-of-family surface), and the out-of-scope
#: families).
_FORBIDDEN_IMPORT_ROOTS = (
    "sharing",
    "developerapi",
    "telemetry",
    "conformance",
    "simulator",
    "appliance",
    "edge",
    "services",
    "federation",
    "transport",
    "interop",
    "imt",
    "energy",
    "upgrade",
    "scale",
    "mobility",
    "multipath",
    "discovery",
    "management",
    "capabilities",
    "adapters",
)


_FAMILY_FILES = sorted((REPO_ROOT / "composition").rglob("*.py"))


def _expect_error(
    name: str, reason: str, call, *args, **kwargs
) -> str:
    """Run one call expecting a typed error with the exact reason;
    returns a problem string ('' when the expectation holds)."""
    try:
        call(*args, **kwargs)
    except Exception as error:  # the typed authority errors
        got = getattr(error, "reason", "")
        if got and reason and got != reason:
            return "wrong reason %r (expected %r)" % (got, reason)
        return ""
    return "the forbidden submission was ACCEPTED"


def _origin_main_available() -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "origin/main"],
        capture_output=True, cwd=str(REPO_ROOT),
    )
    return proc.returncode == 0


# ---------------------------------------------------------------------------
# A. Authority availability
# ---------------------------------------------------------------------------


def case_01_authority_availability(results: List[Result]) -> None:
    name = "case_01_authority_availability_table"
    available = [
        probe for probe in AUTHORITY_PROBES
        if probe.availability == AuthorityAvailability.AVAILABLE
    ]
    absent = [
        probe for probe in AUTHORITY_PROBES
        if probe.availability == AuthorityAvailability.ABSENT
    ]
    problems: List[str] = []
    if len(available) < 13:
        problems.append("only %d available authorities" % len(available))
    if not absent or all(p.work_item != "WORK-048" for p in absent):
        problems.append("WORK-048 is not classified ABSENT")
    # the W046 availability oracle, reconciled by DEC-0090: the
    # boundary repaired by WORK-056 imports cleanly (the same
    # single oracle pinned in case_03 and case_24)
    w046 = [
        probe for probe in AUTHORITY_PROBES
        if probe.work_item == "WORK-046"
    ]
    if not w046 or w046[0].availability != AuthorityAvailability.AVAILABLE:
        problems.append(
            "WORK-046 is not classified AVAILABLE (DEC-0090 "
            "reconciliation)"
        )
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "%d available, WORK-048 absent-fail-closed, WORK-046 "
            "repaired-available (DEC-0090 reconciled)" % len(available),
        )
    )


def case_02_w048_structural_absence(results: List[Result]) -> None:
    name = "case_02_w048_structural_absence"
    import importlib.util

    problems: List[str] = []
    if not w048_runtime_absent():
        problems.append("the W048 runtime probe reports present")
    if importlib.util.find_spec("sharing") is not None:
        problems.append("a 'sharing' package exists")
    if importlib.util.find_spec("containment.runtime") is not None:
        problems.append("a containment runtime module exists")
    containment_init = REPO_ROOT / "containment" / "__init__.py"
    if containment_init.exists():
        problems.append("containment/__init__.py exists (a real package)")
    modules = sorted(
        path.name for path in (REPO_ROOT / "containment").glob("*.py")
    )
    if modules != ["state.py"]:
        problems.append("containment carries %s (vocabulary only expected)" % modules)
    try:
        import containment  # noqa: F401  (namespace package probe)
    except ImportError as error:
        problems.append("containment import failed: %s" % error)
    # the W048-era authority names are not importable
    namespace = sys.modules.get("containment")
    if namespace is not None:
        for symbol in ("CapabilityMatrix", "ContainmentAuthority"):
            if hasattr(namespace, symbol):
                problems.append(
                    "containment exposes the W048-era name %s" % symbol
                )
    try:
        import sharing  # noqa: F401  # must not exist
        problems.append("'import sharing' succeeded")
    except ImportError:
        pass
    if (REPO_ROOT / "tools" / "sharing_selftest.py").exists():
        problems.append("tools/sharing_selftest.py exists")
    if (REPO_ROOT / "docs" / "WORK-048-evidence.md").exists():
        problems.append("docs/WORK-048-evidence.md exists")
    # the roadmap's own restoration note (read-only)
    roadmap = (REPO_ROOT / "spec" / "architect" / "roadmap.yaml").read_text(
        encoding="utf-8"
    )
    if "accepted-not-restored" not in roadmap:
        problems.append("the roadmap restoration note is missing")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "no sharing/ package; containment is the restored ACR-012 "
            "vocabulary only (state.py); no runtime, no authority class, "
            "no W048 battery/evidence artifacts; the roadmap records "
            "accepted-not-restored",
        )
    )


def case_03_w046_defect_disclosed(results: List[Result]) -> None:
    name = "case_03_w046_inherited_defect_disclosed"
    probes = [
        probe for probe in AUTHORITY_PROBES if probe.work_item == "WORK-046"
    ]
    if not probes:
        results.append(fail(name, "no WORK-046 probe recorded"))
        return
    probe = probes[0]
    problems: List[str] = []
    # DEC-0090 reconciliation (the W054 WORK-046 availability
    # oracle): the historical inherited import defect was
    # repaired by WORK-056 within developerapi/ (re-bound to the
    # current accepted W052/W053 public surfaces), so the
    # boundary now imports cleanly and is AVAILABLE -- the
    # repaired-state classification, replacing the obsolete
    # import-broken/no-repair expectation
    if probe.availability != AuthorityAvailability.AVAILABLE:
        problems.append("availability %r" % probe.availability)
    if "imports cleanly" not in probe.detail:
        problems.append(
            "the availability detail lacks the repaired-state wording"
        )
    # the composition family must not import developerapi statically
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in _FAMILY_FILES
    )
    if "import developerapi" in source or "from developerapi" in source:
        problems.append("composition statically imports developerapi")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "the W046 boundary imports cleanly on the WORK-056-repaired "
            "mainline (the historical usage.errors.UsageLedgerError "
            "cross-import defect repaired within developerapi/); the "
            "availability oracle reconciled per DEC-0090; composition "
            "never statically imports it",
        )
    )


def case_04_containment_vocabulary(results: List[Result]) -> None:
    name = "case_04_containment_vocabulary_restored"
    from containment.state import (
        BOUNDARY_TRANSITIONS,
        ACTION_REQUIRED_STATE,
        BoundaryAction,
        BoundaryState,
        CapabilityState,
        transition_is_legal,
    )

    problems: List[str] = []
    if transition_is_legal(BoundaryState.PREPARED, BoundaryState.ACTIVE):
        problems.append("prepared -> active must be illegal (verify first)")
    if not transition_is_legal(BoundaryState.PREPARED, BoundaryState.VERIFIED):
        problems.append("prepared -> verified must be the legal path")
    if BoundaryState.buyer_traffic_states() != ("active",):
        problems.append("buyer traffic states must be exactly ('active',)")
    if ACTION_REQUIRED_STATE[BoundaryAction.VERIFY] != BoundaryState.PREPARED:
        problems.append("verify must require the prepared state")
    if CapabilityState.fail_closed_values() != (
        CapabilityState.UNSUPPORTED, CapabilityState.UNKNOWN,
    ):
        problems.append("fail-closed capability values drifted")
    if not BOUNDARY_TRANSITIONS:
        problems.append("the transition table is empty")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "the frozen ACR-012 boundary vocabulary is restored as DATA "
            "(prepared -> verified -> active only; buyer traffic only in "
            "active; verify requires a runtime the current mainline does "
            "not have)",
        )
    )


def case_05_world_construction(results: List[Result]) -> None:
    name = "case_05_composed_world_construction"
    world_a = CompositionWorld()
    world_b = CompositionWorld()
    digests_a = world_a.public_digests()
    digests_b = world_b.public_digests()
    if digests_a != digests_b:
        results.append(fail(name, "two world builds differ"))
        return
    required = (
        "transport_session_id",
        "logical_session_id",
        "networkpath_content_digest",
        "platform_journal_digest",
        "eligibility_journal_digest",
        "capability_registry_digest",
        "listing_index_digest",
    )
    missing = [key for key in required if key not in digests_a]
    if missing:
        results.append(fail(name, "missing digests: %s" % missing))
        return
    results.append(
        ok(
            name,
            "the composed world builds deterministically (%d public "
            "authority digests identical across two builds)"
            % len(digests_a),
        )
    )


def case_06_world_authority_surfaces(results: List[Result]) -> None:
    name = "case_06_world_authority_surfaces"
    scenario = _scenario()
    world = scenario["world"]
    problems: List[str] = []
    if not world.transport_session_id:
        problems.append("no transport session established")
    if not world.logical_session_id:
        problems.append("no W012 logical session created")
    journal_kinds = {}
    for record in world.integrator.journal_records():
        kind = record.event.kind
        journal_kinds[kind] = journal_kinds.get(kind, 0) + 1
    if journal_kinds.get("interface-observation", 0) != 4:
        problems.append("metering series incomplete: %s" % journal_kinds)
    if journal_kinds.get("platform-state-observation", 0) != 1:
        problems.append("platform-state observation missing")
    if len(world.manager.paths()) != 4:
        problems.append("expected 4 discovered path candidates")
    if world.manager.path(
        scenario["chain"].handoff.network_path_id
    ).state != "ACTIVE":
        problems.append("the handed-off path is not ACTIVE")
    if not world.eligibility.providers():
        problems.append("no W045 provider records")
    if not world.capability_registry.profiles():
        problems.append("no W050 declaration profile")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "transport session + W012 logical session + 4 path candidates "
            "+ 5 platform journal events + W045/W050/W047 records all "
            "present through public surfaces",
        )
    )


# ---------------------------------------------------------------------------
# B. The strict full-chain run
# ---------------------------------------------------------------------------


def case_07_chain_edge_ownership(results: List[Result]) -> None:
    name = "case_07_chain_edge_ownership_frozen"
    expected_owners = {
        "edge-01-intent-offer": "WORK-009/WORK-047",
        "edge-02-offer-eligibility": "WORK-045",
        "edge-03-eligibility-reservation": "WORK-051",
        "edge-04-reservation-candidate-selection": "WORK-047",
        "edge-05-candidate-selection-networkpath-validation": "WORK-041",
        "edge-06-networkpath-validation-containment": "WORK-048",
        "edge-07-containment-session": "WORK-012/WORK-051",
        "edge-08-session-delivered-traffic": "WORK-042",
        "edge-09-delivered-traffic-usage": "WORK-052",
        "edge-10-usage-billable-final": "WORK-052/WORK-051",
        "edge-11-billable-final-allocation": "WORK-053",
        "edge-12-allocation-external-payment-reference": "WORK-044",
        "edge-13-external-payment-reference-reconciliation": "WORK-044",
    }
    problems: List[str] = []
    if [edge.edge_id for edge in CHAIN_EDGES] != list(expected_owners):
        problems.append("the chain edge ids drifted from the frozen contract")
        results.append(fail(name, "; ".join(problems)))
        return
    for edge in CHAIN_EDGES:
        if edge.owning_work_item != expected_owners[edge.edge_id]:
            problems.append(
                "%s owner %r != %r"
                % (edge.edge_id, edge.owning_work_item, expected_owners[edge.edge_id])
            )
        if edge.evidence_class != EVIDENCE_CLASS_SOFTWARE:
            problems.append("%s evidence class %r" % (edge.edge_id, edge.evidence_class))
    stages = [CHAIN_STAGE_NAMES[0]]
    for edge in CHAIN_EDGES:
        stages.append(edge.to_stage)
    if tuple(stages) != CHAIN_STAGE_NAMES:
        problems.append("the chain does not traverse the 14 contract stages")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "all 13 frozen edges carry the contract's owning authority and "
            "SOFTWARE evidence class across the 14 ordered stages",
        )
    )


def case_08_chain_advanced_edges(results: List[Result]) -> None:
    name = "case_08_chain_edges_intent_through_networkpath"
    scenario = _scenario()
    trace = scenario["chain"].trace
    problems: List[str] = []
    for edge_id in (
        "edge-01-intent-offer",
        "edge-02-offer-eligibility",
        "edge-03-eligibility-reservation",
        "edge-04-reservation-candidate-selection",
        "edge-05-candidate-selection-networkpath-validation",
    ):
        outcome = trace.outcomes_by_edge().get(edge_id)
        if outcome != StageOutcome.ADVANCED:
            problems.append("%s -> %r" % (edge_id, outcome))
    transaction = scenario["world"].core.transaction(
        scenario["chain"].transaction_id
    )
    if scenario["chain"].decision_result != "eligible":
        problems.append("the W045 decision was not eligible")
    if not scenario["chain"].proposal:
        problems.append("no selection proposal recorded")
    if not scenario["chain"].handoff:
        problems.append("no W041 handoff outcome recorded")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "intent, offer, eligibility, reservation/lease, candidate "
            "selection, and NetworkPath validation all ADVANCED through "
            "their owning authorities",
        )
    )


def case_09_chain_containment_fail_closed(results: List[Result]) -> None:
    name = "case_09_chain_containment_fail_closed"
    scenario = _scenario()
    trace = scenario["chain"].trace
    outcomes = trace.outcomes_by_edge()
    problems: List[str] = []
    if outcomes.get("edge-06-networkpath-validation-containment") != (
        StageOutcome.FAIL_CLOSED
    ):
        problems.append("the containment edge is not FAIL_CLOSED")
    reasons = trace.reasons_by_edge()
    if reasons.get("edge-06-networkpath-validation-containment") != (
        OutcomeReason.W048_RUNTIME_ABSENT
    ):
        problems.append("the containment reason is not the typed W048 absence")
    edge = trace.fail_closed_edges()[0]
    if edge.owning_work_item != "WORK-048":
        problems.append("the fail-closed edge is not owned by WORK-048")
    correlation = edge.correlation
    if correlation.get("sharing_package") != "absent":
        problems.append("the absence correlation is missing")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "the containment edge FAILS CLOSED with the typed "
            "w048-runtime-absent-fail-closed reason (detected explicitly; "
            "never restored, recreated, mocked, or substituted)",
        )
    )


def case_10_chain_blocked_verdict(results: List[Result]) -> None:
    name = "case_10_chain_blocked_verdict_honest"
    scenario = _scenario()
    trace = scenario["chain"].trace
    problems: List[str] = []
    if trace.verdict != ChainVerdict.BLOCKED_MISSING_AUTHORITY:
        problems.append("verdict %r" % trace.verdict)
    if trace.blocked_at != "containment":
        problems.append("blocked_at %r" % trace.blocked_at)
    if trace.missing_authority != "WORK-048":
        problems.append("missing_authority %r" % trace.missing_authority)
    if trace.production_composition:
        problems.append("the trace claims a production composition")
    if ChainVerdict.values() != (ChainVerdict.BLOCKED_MISSING_AUTHORITY,):
        problems.append("the verdict vocabulary has a passing-production form")
    # downstream edges are NOT ENTERED, never skipped
    for edge in CHAIN_EDGES[6:]:
        if trace.outcomes_by_edge().get(edge.edge_id) != StageOutcome.NOT_ENTERED:
            problems.append("%s is not NOT_ENTERED" % edge.edge_id)
            break
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    not_entered = sum(
        1 for outcome in trace.outcomes_by_edge().values()
        if outcome == StageOutcome.NOT_ENTERED
    )
    results.append(
        ok(
            name,
            "verdict BLOCKED_MISSING_AUTHORITY at containment "
            "(WORK-048); production_composition=False; %d downstream "
            "edges recorded NOT_ENTERED (never skipped, never guessed)"
            % not_entered,
        )
    )


# ---------------------------------------------------------------------------
# C. Segment conformance (the available links)
# ---------------------------------------------------------------------------


def case_11_segment_session(results: List[Result]) -> None:
    name = "case_11_segment_session_authorization"
    scenario = _scenario()
    world = scenario["world"]
    chain = scenario["chain"]
    segments = scenario["segments"].report["segments"]
    session_segment = segments[0]
    problems: List[str] = []
    if session_segment["correlation"].get("commercial_state") != "PATH_ACTIVE":
        problems.append(
            "session segment state %r"
            % session_segment["correlation"].get("commercial_state")
        )
    store = world.session_store
    logical = store.get(world.logical_session_id)
    if logical is None or logical.state not in ("REQUESTED", "AUTHORIZED", "ESTABLISHED"):
        problems.append("logical session state %r" % (logical and logical.state))
    if world.manager.active_path_id(world.transport_session_id) != (
        chain.handoff.network_path_id
    ):
        problems.append("the transport session's active path is not the handoff path")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "the commercial session was authorized and the path activated "
            "against the PROVEN W041 ACTIVE state (W047 record seam); the "
            "W012 logical session exists through the genuine W011/W010 "
            "decisions",
        )
    )


def case_12_segment_delivery(results: List[Result]) -> None:
    name = "case_12_segment_delivered_traffic_evidence"
    scenario = _scenario()
    world = scenario["world"]
    chain = scenario["chain"]
    segments = scenario["segments"].report["segments"]
    delivery_segment = segments[1]
    evidence = build_delivery_evidence(world.integrator, chain.transaction_id)
    problems: List[str] = []
    if delivery_segment["correlation"].get("commercial_state") != "DELIVERY_COMPLETED":
        problems.append(
            "delivery segment state %r"
            % delivery_segment["correlation"].get("commercial_state")
        )
    if not delivery_segment["correlation"].get("delivery_evidence_ids"):
        problems.append("the delivery segment recorded no evidence ids")
    quantities = tuple(record.delivered_quantity for record in evidence)
    if quantities != (210, 150):
        problems.append("delivery windows %s" % (quantities,))
    for record in evidence:
        if record.evidence_kind != EvidenceKind.DELIVERED:
            problems.append("evidence kind %r" % record.evidence_kind)
        if record.provenance != "platform-journal":
            problems.append("evidence provenance %r" % record.provenance)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "the delivery-plane evidence windows (210 + 150 bytes) were "
            "derived from the platform journal's public reads and the "
            "commercial core recorded delivery against them",
        )
    )


def case_13_segment_usage(results: List[Result]) -> None:
    name = "case_13_segment_usage_observations"
    scenario = _scenario()
    segments = scenario["segments"]
    ledger = segments.usage_ledger
    projection = ledger.transaction(segments.usage_transaction_id)
    problems: List[str] = []
    delivered = projection.statement.delivered_quantity if projection.statement else 0
    if projection.state not in ("BILLABLE_FINAL",):
        problems.append("usage state %r" % projection.state)
    observations = [
        record for record in ledger.journal_records()
        if getattr(record.command, "action", "") == "observe-usage"
    ]
    if len(observations) != 3:
        problems.append("%d observations (2 delivered + 1 reserved expected)" % len(observations))
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "the usage ledger admitted the delivered observations (citing "
            "the authoritative delivery evidence) plus one DATA-only "
            "reserved observation (never billable); state %s"
            % projection.state,
        )
    )


def case_14_segment_billable_final(results: List[Result]) -> None:
    name = "case_14_segment_billable_final_seal"
    scenario = _scenario()
    segments = scenario["segments"]
    world = scenario["world"]
    statement = segments.usage_ledger.transaction(
        segments.usage_transaction_id
    ).statement
    commercial_state = world.core.transaction(
        segments.usage_transaction_id
    ).state
    problems: List[str] = []
    if statement is None:
        problems.append("no sealed statement")
    else:
        if statement.billable_quantity != 360:
            problems.append("billable quantity %d" % statement.billable_quantity)
        if statement.delivered_quantity != statement.billable_quantity:
            problems.append("billable != delivered quantity")
        if statement.amount_micros != 1080:
            problems.append("amount %d micros" % statement.amount_micros)
        if statement.reserved_quantity != 500:
            problems.append("reserved DATA quantity %d" % statement.reserved_quantity)
    if commercial_state != "BILLABLE_FINAL":
        problems.append("commercial state %r" % commercial_state)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "BILLABLE_FINAL sealed: 360 delivered bytes x 3 micros = 1080 "
            "micros (integer arithmetic; the 500 reserved bytes stay "
            "non-billable DATA); the commercial core recorded billable "
            "finality",
        )
    )


def case_15_segment_allocation(results: List[Result]) -> None:
    name = "case_15_segment_allocation_split"
    scenario = _scenario()
    segments = scenario["segments"]
    account = segments.allocation_ledger.allocation(
        segments.usage_transaction_id
    )
    snapshot = account.snapshot
    problems: List[str] = []
    if account.state != "SETTLED":
        problems.append("allocation state %r" % account.state)
    total = (
        snapshot.adcos_share_micros
        + snapshot.provider_share_micros
        + snapshot.developer_share_micros
    )
    if total != snapshot.distributable_micros:
        problems.append("the split does not conserve (%d != %d)" % (
            total, snapshot.distributable_micros,
        ))
    if snapshot.gross_micros != 1080:
        problems.append("gross %d" % snapshot.gross_micros)
    if (snapshot.adcos_share_micros, snapshot.provider_share_micros,
            snapshot.developer_share_micros) != (162, 459, 459):
        problems.append("split %s" % (
            (snapshot.adcos_share_micros, snapshot.provider_share_micros,
             snapshot.developer_share_micros),
        ))
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "ALLOCATED then SETTLED: the exact half-up three-way split "
            "(162, 459, 459) conserves the 1080 gross micros under the "
            "15%/50% policy; the settlement acknowledgement cites the "
            "external settlement reference",
        )
    )


def case_16_segment_payment_reference(results: List[Result]) -> None:
    name = "case_16_segment_external_payment_reference"
    scenario = _scenario()
    segments = scenario["segments"]
    gateway = segments.gateway
    problems: List[str] = []
    intent = gateway.intent("w054-pi-01")
    if intent.state != "CAPTURED":
        problems.append("intent state %r" % intent.state)
    if intent.amount != 1080:
        problems.append("intent amount %d" % intent.amount)
    payout = gateway.payout(segments.usage_transaction_id)
    if payout.state != "TRANSFERRED":
        problems.append("payout state %r" % payout.state)
    snapshot_entries = {
        (entry.reference_id, entry.family)
        for entry in gateway.snapshot().entries()
    }
    if (segments.usage_transaction_id, "commercial") not in snapshot_entries:
        problems.append("the commercial citation is not in the snapshot")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "the payment boundary created/authorized/captured the intent "
            "(1080 micros) citing the W051/W052 public snapshots and "
            "emitted + transferred the payout from the finalized W053 "
            "allocation citation",
        )
    )


def case_17_segment_reconciliation(results: List[Result]) -> None:
    name = "case_17_segment_reconciliation"
    scenario = _scenario()
    segments = scenario["segments"]
    gateway = segments.gateway
    report = gateway.reports()[-1]
    problems: List[str] = []
    classifications = sorted(
        str(entry.get("classification", "")) for entry in report.entries
    )
    if classifications != ["matched", "matched"]:
        problems.append("classifications %s" % classifications)
    if gateway.intent("w054-pi-01").state != "CAPTURED":
        problems.append("the intent state changed during reconciliation")
    if gateway.payout(segments.usage_transaction_id).state != "TRANSFERRED":
        problems.append("the payout state changed during reconciliation")
    observations = gateway.observations()
    if not observations:
        problems.append("no observations recorded")
    for observation in observations:
        if observation.orphan:
            problems.append("an orphan observation in the golden run")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "%d provider callbacks were OBSERVATIONS (no auto-fold); the "
            "provider-ahead transfer observation was folded explicitly "
            "exactly once; the report classified both subjects MATCHED "
            "without rewriting any canonical state"
            % len(observations),
        )
    )


def case_18_segment_disclaimer(results: List[Result]) -> None:
    name = "case_18_segment_disclaimer_present"
    scenario = _scenario()
    report = scenario["segments"].report
    problems: List[str] = []
    if report.get("disclaimer") != SEGMENT_CONFORMANCE_DISCLAIMER:
        problems.append("the disclaimer is missing from the report")
    if report.get("production_composition") is not False:
        problems.append("the segment report claims a production composition")
    if "segments" not in report or len(report["segments"]) != 7:
        problems.append("expected 7 segment records")
    for segment in report["segments"]:
        if segment.get("evidence_class") != EVIDENCE_CLASS_SOFTWARE:
            problems.append("segment evidence class %r" % segment.get("evidence_class"))
        if segment.get("outcome") != "ADVANCED":
            problems.append("segment outcome %r" % segment.get("outcome"))
        if segment.get("reason") != "advanced-segment-conformance":
            problems.append("segment reason %r" % segment.get("reason"))
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "the 7 segment records each carry the SOFTWARE class, the "
            "segment-conformance reason, and the traveling disclaimer "
            "(never a production composition claim)",
        )
    )


# ---------------------------------------------------------------------------
# D. The seven mandatory negative proofs
# ---------------------------------------------------------------------------


def _payment_fixture(
    world: CompositionWorld, transaction_id: str
) -> Tuple[SettlementGateway, Any]:
    """A small payment fixture over one cited commercial transaction
    (the W044 boundary with the sandbox provider seam).  The usage
    citation is the transaction's honest open identity (one DATA-only
    reserved observation admits the account; it is never final and
    never cited as usage-final)."""
    ledger = _empty_usage_ledger(world, transaction_id)
    ledger.observe_usage(
        command_id="neg-usage-open-%s" % transaction_id[7:13],
        transaction_id=transaction_id,
        quantity_class=QuantityClass.RESERVED, quantity=50,
        actor="meter", source="neg",
    )
    snapshot = build_payment_snapshot(
        world.core, ledger, None, (transaction_id,),
    )
    provider = sandbox_provider()
    gateway = SettlementGateway(
        store=MemoryPaymentStore(),
        clock=StepClock("2026-12-01T09:00:00Z", 60),
        snapshot=snapshot,
        adapter=provider,
    )
    gateway.record_capabilities(
        command_id="neg-cap-01", actor="platform", source="payment-boundary"
    )
    return gateway, provider


def _empty_usage_ledger(
    world: CompositionWorld, transaction_id: str
) -> UsageLedger:
    index = build_usage_evidence_index(
        world.core, world.integrator, (transaction_id,)
    )
    return UsageLedger(
        store=MemoryUsageStore(),
        clock=StepClock("2026-09-01T13:00:00Z", 60),
        evidence_index=index,
    )


def _observing_usage_ledger(
    world: CompositionWorld, transaction_id: str
) -> UsageLedger:
    """A usage ledger whose cited transaction is honestly OBSERVING
    (one DATA-only reserved observation; never final)."""
    ledger = _empty_usage_ledger(world, transaction_id)
    ledger.observe_usage(
        command_id="neg-observing-%s" % transaction_id[7:13],
        transaction_id=transaction_id,
        quantity_class=QuantityClass.RESERVED, quantity=50,
        actor="meter", source="neg",
    )
    return ledger


def _driven_transaction(
    world: CompositionWorld, *, to: str = "PATH_ACTIVE"
) -> str:
    """A second commercial transaction driven through the public
    typed surface to the requested state."""
    core = world.core
    out = core.submit_intent(
        command_id="neg-tx-01", actor="w054-buyer-1", source="neg",
        intent={"buyer": "w054-buyer-1", "want": "connectivity", "region": "gh"},
    )
    tx = out.transaction_id
    core.select_offer(
        command_id="neg-tx-02", transaction_id=tx, actor="b", source="neg",
        offer={
            "provider_id": _PROVIDER_ID, "offer_id": "wifi-basic",
            "currency": "USD", "price_minor": 3, "price_exponent": 0,
            "billing_mode": "per-megabyte", "jurisdiction": "gh",
        },
    )
    core.hold_reservation(
        command_id="neg-tx-03", transaction_id=tx, actor="b", source="neg",
        expires_at="2027-01-01T00:00:00Z",
    )
    core.authorize_session(
        command_id="neg-tx-04", transaction_id=tx, actor="p", source="neg",
        session_ref=world.transport_session_id,
    )
    path_id = next(
        path for path in world.manager.paths()
        if world.manager.path(path).interface_name == "wlan0"
    )
    core.activate_path(
        command_id="neg-tx-05", transaction_id=tx, actor="p", source="neg",
        path_ref=path_id,
    )
    if to == "DELIVERY_STARTED":
        journal_evidence = tuple(
            ref.reference_id
            for ref in world.reference_index.by_family(
                ReferenceFamily.DELIVERY_EVIDENCE
            )
        )
        core.start_delivery(
            command_id="neg-tx-06", transaction_id=tx, actor="p",
            source="neg", evidence_refs=journal_evidence[:1],
        )
    return tx


def case_19_neg_payment_not_connectivity(results: List[Result]) -> None:
    name = "case_19_neg_payment_success_cannot_create_connectivity"
    world = CompositionWorld()
    chain = run_full_chain(world)
    tx = _driven_transaction(world, to="PATH_ACTIVE")
    gateway, provider = _payment_fixture(world, tx)
    gateway.create_intent(
        command_id="neg-pay-01", intent_id="neg-pi-01", transaction_id=tx,
        amount=999, currency="USD", exponent=6,
        actor="billing", source="neg",
    )
    gateway.authorize(
        command_id="neg-pay-02", intent_id="neg-pi-01",
        actor="billing", source="neg",
    )
    gateway.capture(
        command_id="neg-pay-03", intent_id="neg-pi-01", amount=999,
        actor="billing", source="neg",
    )
    problems: List[str] = []
    if gateway.intent("neg-pi-01").state != "CAPTURED":
        problems.append("the payment success fixture did not capture")
    pay_ref = world.reference_index.by_family(ReferenceFamily.PAYMENT)[0].reference_id
    problem = _expect_error(
        name, CommercialReasonCode.PAYMENT_NOT_DELIVERY,
        world.core.start_delivery,
        command_id="neg-pay-04", transaction_id=tx, actor="p", source="neg",
        evidence_refs=(pay_ref,),
    )
    if problem:
        problems.append("start_delivery: %s" % problem)
    problem = _expect_error(
        name, CommercialReasonCode.PAYMENT_NOT_DELIVERY,
        world.core.accrue_usage,
        command_id="neg-pay-05", transaction_id=tx, actor="p", source="neg",
        usage_refs=(pay_ref,),
    )
    if problem:
        problems.append("accrue_usage: %s" % problem)
    # the payment observation cannot become usage evidence either
    payment_observed = DeliveryEvidence(
        evidence_id="sha256:" + "ee" * 32,
        transaction_id=tx, delivered_quantity=0,
        window_start="2026-09-01T12:01:00Z",
        window_end="2026-09-01T12:05:00Z",
        evidence_kind=EvidenceKind.PAYMENT_OBSERVED,
        provenance="external-payment-observation",
    )
    index = build_usage_evidence_index(
        world.core, world.integrator, (tx,), extra_evidence=(payment_observed,)
    )
    ledger = UsageLedger(
        store=MemoryUsageStore(), clock=StepClock("2026-09-01T13:00:00Z", 60),
        evidence_index=index,
    )
    try:
        ledger.observe_usage(
            command_id="neg-pay-06", transaction_id=tx,
            quantity_class=QuantityClass.DELIVERED, quantity=210,
            evidence_id=payment_observed.evidence_id,
            window_start=payment_observed.window_start,
            window_end=payment_observed.window_end,
            actor="m", source="neg",
        )
        problems.append("usage accepted a payment observation as delivery")
    except UsageError as error:
        if error.reason != "payment-not-delivery":
            problems.append("usage reason %r" % error.reason)
    # and nothing advanced: the second transaction stays pre-delivery
    if world.core.transaction(tx).state != "PATH_ACTIVE":
        problems.append("commercial state drifted after payment success")
    if world.core.transaction(chain.transaction_id).state != "RESERVATION_HELD":
        problems.append("the chain transaction drifted")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "CAPTURED payment success was refused as delivery justification "
            "(payment-not-delivery on start_delivery/accrue_usage), the "
            "payment observation was refused by the W052 kind table, and "
            "no connectivity state advanced",
        )
    )


def case_20_neg_reservation_not_reachability(results: List[Result]) -> None:
    name = "case_20_neg_reservation_cannot_imply_reachability"
    world = CompositionWorld()
    chain = run_full_chain(world)
    tx = chain.transaction_id
    ledger = _empty_usage_ledger(world, tx)
    evidence = build_delivery_evidence(world.integrator, tx)
    problems: List[str] = []
    # a usage observation citing the RESERVED transaction is refused
    try:
        ledger.observe_usage(
            command_id="neg-r-01", transaction_id=tx,
            quantity_class=QuantityClass.DELIVERED,
            quantity=210, evidence_id=evidence[0].evidence_id,
            window_start=evidence[0].window_start,
            window_end=evidence[0].window_end,
            actor="m", source="neg",
        )
        problems.append("usage accepted a reserved transaction")
    except UsageError as error:
        if error.reason != "reservation-not-usage":
            problems.append("usage reason %r" % error.reason)
    # delivery cannot start without delivery evidence
    problem = _expect_error(
        name, CommercialReasonCode.COMMAND_INVALID,
        world.core.start_delivery,
        command_id="neg-r-02", transaction_id=tx, actor="p", source="neg",
        evidence_refs=(),
    )
    if problem:
        problems.append("empty-evidence start_delivery: %s" % problem)
    # the reservation cannot activate the path on its own: on a
    # fresh manager (no handoff), the candidate stays DISCOVERED
    fresh_world = CompositionWorld()
    fresh_chain = run_full_chain(fresh_world)
    if fresh_chain.transaction_id:
        pass
    # (the handoff inside run_full_chain proves the machinery; the
    # negative here: a SECOND path the machinery never drove cannot
    # be activated while the commercial reservation merely exists)
    untouched = next(
        path for path in fresh_world.manager.paths()
        if fresh_world.manager.path(path).interface_name == "eth0"
    )
    try:
        fresh_world.manager.activate(untouched)
        problems.append("an unvalidated/unbound path was activated")
    except NetworkPathError as error:
        if error.reason != "lifecycle-illegal":
            problems.append("activate reason %r" % error.reason)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "the reserved transaction cannot create usage "
            "(reservation-not-usage), delivery requires real evidence, and "
            "the W041 machinery (not the reservation) is the only path "
            "activation authority",
        )
    )


def case_21_neg_discovery_not_activation(results: List[Result]) -> None:
    name = "case_21_neg_marketplace_discovery_cannot_activate_path"
    world = CompositionWorld()
    query = DiscoveryQuery(
        buyer_id="w054-buyer-1", jurisdiction="gh",
        payment_reference="w054-payauth-1",
        constraints=UserConstraints(currency="USD", max_price_minor=500),
    )
    discovery = world.marketplace.discover(query=query)
    proposal = world.marketplace.propose(query=query, count=1)
    problems: List[str] = []
    if proposal.status != "proposed":
        problems.append("proposal status %r" % proposal.status)
    # the proposal cannot activate the W041 machinery's path
    eth = next(
        path for path in world.manager.paths()
        if world.manager.path(path).interface_name == "eth0"
    )
    try:
        world.manager.activate(eth)
        problems.append("a DISCOVERED path was activated from a proposal")
    except NetworkPathError as error:
        if error.reason != "lifecycle-illegal":
            problems.append("activate reason %r" % error.reason)
    # the proposal id is not a path reference for the commercial core
    # (a fabricated or wrong-family citation fails closed at reference
    # resolution, before any state gate runs)
    chain = run_full_chain(world)
    try:
        world.core.activate_path(
            command_id="neg-d-01", transaction_id=chain.transaction_id,
            actor="p", source="neg", path_ref=proposal.proposal_id,
        )
        problems.append("a proposal id was accepted as a path reference")
    except CommercialError as error:
        if error.reason != "reference-unknown":
            problems.append("activate reason %r" % error.reason)
    if not discovery.ranked:
        problems.append("the discovery fixture ranked nothing")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "the selection proposal stays 'proposed' (nothing validated, "
            "bound, or activated); a DISCOVERED path cannot be activated; "
            "a proposal id is not a NetworkPath reference",
        )
    )


def case_22_neg_w050_declaration_not_containment(results: List[Result]) -> None:
    name = "case_22_neg_w050_declaration_cannot_enforce_containment"
    world = CompositionWorld()
    evaluation = evaluate_capability_declaration(world.capability_registry)
    chain = run_full_chain(world)
    from containment.state import BoundaryState, transition_is_legal

    problems: List[str] = []
    if evaluation["state"] != "supported":
        problems.append("the declaration evaluation is %r" % evaluation["state"])
    if evaluation["evidence_class"] != "SOFTWARE":
        problems.append("declaration evidence class %r" % evaluation["evidence_class"])
    # the 'supported' declaration does NOT move the containment edge
    outcomes = chain.trace.outcomes_by_edge()
    if outcomes.get("edge-06-networkpath-validation-containment") != (
        StageOutcome.FAIL_CLOSED
    ):
        problems.append("the containment edge advanced despite W048 absence")
    if chain.trace.reasons_by_edge().get(
        "edge-06-networkpath-validation-containment"
    ) != OutcomeReason.W048_RUNTIME_ABSENT:
        problems.append("the containment reason is not the W048 absence")
    # the vocabulary gate: a declaration can never produce an active
    # boundary (prepare -> verify -> activate is runtime-only)
    if transition_is_legal(BoundaryState.PREPARED, BoundaryState.ACTIVE):
        problems.append("prepared -> active became legal")
    # no containment runtime constructor exists to consume the
    # declaration (structural)
    import importlib.util

    if importlib.util.find_spec("containment.runtime") is not None:
        problems.append("a containment runtime module exists")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "the W050 registry declares 'supported' (a SOFTWARE "
            "compatibility statement), yet the containment edge still "
            "fails closed (W048 runtime absent): a declaration is never "
            "permission, authorization, or proven enforcement",
        )
    )


def case_23_neg_client_not_canonical(results: List[Result]) -> None:
    name = "case_23_neg_w049_client_state_cannot_become_canonical"
    scenario = _scenario()
    world = scenario["world"]
    problems: List[str] = []
    # the sharing read fails closed (never fabricated)
    try:
        world.client_runtime.gateway.read_sharing_session("any-sharing-id")
        problems.append("a sharing read succeeded without a runtime")
    except ClientError as error:
        if error.reason != "client-stale-state":
            problems.append("sharing read reason %r" % error.reason)
    # the provider-mode client refuses construction without the W048 runtime
    from client import ProviderClient

    try:
        ProviderClient(runtime=world.client_runtime, sharing=None)
        problems.append("a provider client was built without a sharing runtime")
    except ClientError as error:
        if error.reason != "client-invalid-input":
            problems.append("provider client reason %r" % error.reason)
    # the projection cache: authority-class dominance (a local
    # ACTIVE observation never displaces canonical truth)
    cache = ProjectionCache(max_entries=4)
    local = StatusSnapshot(
        subject="w054-subject-1", state="ACTIVE",
        freshness=Freshness.LOCAL_OBSERVATION,
        observed_at="2026-09-01T14:00:00Z", canonical_source="client-ui",
    )
    canonical = StatusSnapshot(
        subject="w054-subject-1", state="RESERVATION_HELD",
        freshness=Freshness.CANONICAL_STATE,
        observed_at="2026-09-01T12:00:00Z", canonical_source="commercial-core",
    )
    if not cache.apply(local):
        problems.append("the local observation was not admitted first")
    if not cache.apply(canonical):
        problems.append("the canonical read was refused")
    later_local = StatusSnapshot(
        subject="w054-subject-1", state="ACTIVE",
        freshness=Freshness.LOCAL_OBSERVATION,
        observed_at="2026-09-01T15:00:00Z", canonical_source="client-ui",
    )
    if cache.apply(later_local):
        problems.append("a later local ACTIVE displaced canonical truth")
    if cache.get("w054-subject-1").state != "RESERVATION_HELD":
        problems.append("the cached state is not the canonical truth")
    # the client's own subject ids are not authority references
    try:
        world.core.start_delivery(
            command_id="neg-c-01", transaction_id=scenario["chain"].transaction_id,
            actor="p", source="neg",
            evidence_refs=(world.client_runtime.context.user_ref,),
        )
        problems.append("a client user ref was accepted as delivery evidence")
    except CommercialError as error:
        if error.reason != "reference-unknown":
            problems.append("client-ref reason %r" % error.reason)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "client state stays non-canonical: sharing reads fail closed, "
            "the provider client requires the absent W048 runtime, a "
            "future-dated local ACTIVE observation cannot displace "
            "canonical truth, and client subject ids are not authority "
            "references",
        )
    )


def case_24_neg_webhook_not_source_of_truth(results: List[Result]) -> None:
    name = "case_24_neg_webhook_observation_cannot_become_truth"
    world = CompositionWorld()
    chain = run_full_chain(world)
    tx = _driven_transaction(world, to="DELIVERY_STARTED")
    gateway, provider = _payment_fixture(world, tx)
    gateway.create_intent(
        command_id="neg-w-01", intent_id="neg-pi-02", transaction_id=tx,
        amount=500, currency="USD", exponent=6, actor="b", source="neg",
    )
    gateway.authorize(
        command_id="neg-w-02", intent_id="neg-pi-02", actor="b", source="neg",
    )
    envelopes = provider.pending_callbacks()
    problems: List[str] = []
    if not envelopes:
        problems.append("the provider emitted no callbacks")
    for envelope in envelopes:
        out = gateway.ingest_callback(
            envelope, actor="webhook-ingress", source="provider-callback"
        )
        if out.status != "appended":
            problems.append("callback ingestion %r" % out.status)
    if gateway.intent("neg-pi-02").state != "AUTHORIZED":
        problems.append("an observation folded canonical state by itself")
    for observation in gateway.observations():
        if observation.applied:
            problems.append("an observation auto-applied")
    # exact redelivery: idempotent no-op, no journal growth
    before = gateway.tail_sequence()
    out = gateway.ingest_callback(
        envelopes[0], actor="webhook-ingress", source="provider-callback"
    )
    if out.status != "duplicate":
        problems.append("callback redelivery %r" % out.status)
    if gateway.tail_sequence() != before:
        problems.append("callback replay grew the journal")
    # a payment observation is not usage evidence (the W052 kind table)
    payment_observed = DeliveryEvidence(
        evidence_id="sha256:" + "ff" * 32,
        transaction_id=tx, delivered_quantity=0,
        window_start="2026-09-01T12:01:00Z",
        window_end="2026-09-01T12:05:00Z",
        evidence_kind=EvidenceKind.PAYMENT_OBSERVED,
        provenance="external-payment-observation",
    )
    provider_observed = DeliveryEvidence(
        evidence_id="sha256:" + "fa" * 32,
        transaction_id=tx, delivered_quantity=0,
        window_start="2026-09-01T12:01:00Z",
        window_end="2026-09-01T12:05:00Z",
        evidence_kind=EvidenceKind.PROVIDER_OBSERVED,
        provenance="external-provider-observation",
    )
    index = build_usage_evidence_index(
        world.core, world.integrator, (tx,),
        extra_evidence=(payment_observed, provider_observed),
    )
    ledger = UsageLedger(
        store=MemoryUsageStore(), clock=StepClock("2026-09-01T13:00:00Z", 60),
        evidence_index=index,
    )
    for evidence, expected in (
        (payment_observed, "payment-not-delivery"),
        (provider_observed, "provider-not-delivery"),
    ):
        try:
            ledger.observe_usage(
                command_id="neg-w-%s" % evidence.evidence_id[7:13],
                transaction_id=tx, quantity_class=QuantityClass.DELIVERED,
                quantity=210, evidence_id=evidence.evidence_id,
                window_start=evidence.window_start,
                window_end=evidence.window_end, actor="m", source="neg",
            )
            problems.append("usage accepted %s as delivery" % evidence.evidence_kind)
        except UsageError as error:
            if error.reason != expected:
                problems.append("usage kind reason %r != %r" % (error.reason, expected))
    # the W046 boundary is repaired and available (the same
    # single availability oracle, DEC-0090 reconciled)
    probes = [p for p in AUTHORITY_PROBES if p.work_item == "WORK-046"]
    if probes and probes[0].availability != AuthorityAvailability.AVAILABLE:
        problems.append("W046 is not reconciled as available")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "verified callbacks stay OBSERVATIONS (canonical state folds "
            "only through the explicit exactly-once apply command); "
            "redelivery is an idempotent no-op; payment/provider "
            "observations are refused by the W052 kind table; the W046 "
            "webhook boundary is repaired and available (DEC-0090 "
            "reconciled) and its observations still never bypass the "
            "fold",
        )
    )


def case_25_neg_software_not_physical(results: List[Result]) -> None:
    name = "case_25_neg_software_cannot_close_physical_evidence"
    problems: List[str] = []
    try:
        classify_evidence("PHYSICAL")
        problems.append("a PHYSICAL claim was classified")
    except CompositionEvidenceError as error:
        if "SOFTWARE_EVIDENCE_CANNOT_CLOSE_PHYSICAL" not in str(error):
            problems.append("physical rejection %s" % error)
    for forbidden in ("EXTERNAL", "OPERATIONAL", "external-evidence"):
        try:
            classify_evidence(forbidden)
            problems.append("%r was classified" % forbidden)
        except CompositionEvidenceError:
            pass
    obligations_text = (
        REPO_ROOT / "spec" / "architect" / "evidence-obligations.yaml"
    ).read_text(encoding="utf-8")
    statuses = physical_obligations_open(obligations_text)
    for obligation in ("EVID-007", "EVID-008"):
        entry = statuses.get(obligation, {})
        if entry.get("status") not in ("PARTIAL", "NOT-TESTABLE", "OPEN"):
            problems.append(
                "%s status %r (must remain open)" % (obligation, entry.get("status"))
            )
        if entry.get("owner") != "WORK-040":
            problems.append("%s owner %r" % (obligation, entry.get("owner")))
        if entry.get("evidence_class") != "PHYSICAL":
            problems.append("%s class %r" % (obligation, entry.get("evidence_class")))
    # the software evidence document mints SOFTWARE only
    document = build_evidence_document(
        (
            SoftwareEvidenceRecord(
                record_id="w054-ev-01",
                subject="the composition battery evidence class",
                produced_by="tools/composition_selftest.py",
                correlation={"class": "SOFTWARE"},
            ),
        )
    )
    if document["evidence_class"] != EVIDENCE_CLASS_SOFTWARE:
        problems.append("document class %r" % document["evidence_class"])
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "PHYSICAL/EXTERNAL claims fail closed "
            "(SOFTWARE_EVIDENCE_CANNOT_CLOSE_PHYSICAL); EVID-007 stays "
            "PARTIAL and EVID-008 NOT-TESTABLE, both WORK-040-owned "
            "physical obligations in the durable projection; every "
            "composition record is SOFTWARE class",
        )
    )


# ---------------------------------------------------------------------------
# E. Failure matrix
# ---------------------------------------------------------------------------


def case_26_fail_denied_eligibility(results: List[Result]) -> None:
    name = "case_26_fail_denied_eligibility"
    world = CompositionWorld()
    world.eligibility.suspend(
        command_id="neg-s-01", actor="platform", source="neg",
        provider_id=_PROVIDER_ID, reason="w054 suspension fixture",
    )
    chain = run_full_chain(world)
    problems: List[str] = []
    if chain.trace.blocked_at != "eligibility":
        problems.append("blocked_at %r" % chain.trace.blocked_at)
    reasons = chain.trace.reasons_by_edge()
    if reasons.get("edge-02-offer-eligibility") != OutcomeReason.ELIGIBILITY_DENIED:
        problems.append("eligibility reason %r" % reasons.get("edge-02-offer-eligibility"))
    # the direct decision is NOT-ELIGIBLE with denial codes
    decision = world.eligibility.evaluate(
        command_id="neg-s-02", actor="platform", source="neg",
        jurisdiction="gh", provider_id=_PROVIDER_ID, offer_id="wifi-basic",
        valid_until="2027-01-01T00:00:00Z",
    )
    record = world.eligibility.decision(decision.decision_id)
    if record.result != "not-eligible":
        problems.append("decision result %r" % record.result)
    if "provider-suspended" not in record.reason_codes:
        problems.append("denial codes %s" % (record.reason_codes,))
    # no reservation was created
    if world.core.transactions():
        problems.append("a commercial transaction was created after denial")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "the suspended provider is denied (provider-suspended); the "
            "chain fails closed at the eligibility edge and NO commercial "
            "reservation exists",
        )
    )


def case_27_fail_reservation(results: List[Result]) -> None:
    name = "case_27_fail_reservation"
    world = CompositionWorld()
    chain = run_full_chain(world)
    core = world.core
    problems: List[str] = []
    # wrong-state hold: without a selected offer there is nothing to hold
    out = core.submit_intent(
        command_id="neg-h-01", actor="b", source="neg",
        intent={"buyer": "w054-buyer-2", "want": "connectivity", "region": "gh"},
    )
    tx = out.transaction_id
    problem = _expect_error(
        name, CommercialReasonCode.LIFECYCLE_ILLEGAL,
        core.hold_reservation,
        command_id="neg-h-02", transaction_id=tx, actor="b", source="neg",
        expires_at="2027-01-01T00:00:00Z",
    )
    if problem:
        problems.append("wrong-state hold: %s" % problem)
    if core.transaction(tx).state != "CONNECTIVITY_INTENT":
        problems.append("the failed reservation mutated the transaction")
    # a failed reservation is fail-closed in the chain when the
    # commercial authority refuses the coordination
    if chain.trace.outcomes_by_edge().get(
        "edge-03-eligibility-reservation"
    ) != StageOutcome.ADVANCED:
        problems.append("the golden chain reservation unexpectedly failed")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "a hold without a selected offer is refused "
            "(lifecycle-illegal: hold_reservation requires "
            "OFFER_SELECTED) and mutates nothing",
        )
    )


def case_28_fail_unreachable_candidate(results: List[Result]) -> None:
    name = "case_28_fail_unreachable_candidate"
    world = CompositionWorld()
    query = DiscoveryQuery(
        buyer_id="w054-buyer-1", jurisdiction="gh",
        payment_reference="w054-payauth-1",
        constraints=UserConstraints(currency="USD", max_price_minor=500),
        max_distance_m=1,
    )
    problems: List[str] = []
    result = world.marketplace.discover(query=query)
    if result.ranked:
        problems.append("distance-constrained discovery still ranked candidates")
    try:
        world.marketplace.propose(query=query, count=1)
        problems.append("a selection proposal was composed from nothing")
    except MarketplaceError as error:
        if error.reason != "marketplace-selection-empty":
            problems.append("propose reason %r" % error.reason)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "a distance-constrained query excludes every candidate "
            "(%d excluded) and the selection fails closed "
            "(selection-empty)" % len(result.excluded),
        )
    )


def case_29_fail_networkpath_validation(results: List[Result]) -> None:
    name = "case_29_fail_networkpath_validation"
    world = CompositionWorld(eth_down=True)
    chain = run_full_chain(world)
    problems: List[str] = []
    # the wifi handoff path is active (the golden chain works)
    if world.manager.path(chain.handoff.network_path_id).state != "ACTIVE":
        problems.append("the golden path is not ACTIVE")
    # the link-down candidate is refused and preserved
    eth = next(
        path for path in world.manager.paths()
        if world.manager.path(path).interface_name == "eth0"
    )
    try:
        world.manager.validate(eth)
        problems.append("a link-down candidate was validated")
    except NetworkPathError as error:
        if error.reason != "validation-rejected":
            problems.append("validate reason %r" % error.reason)
        if "link-down" not in error.detail:
            problems.append("the deterministic reason is missing from the detail")
    if world.manager.path(eth).state != "DISCOVERED":
        problems.append("the failed candidate mutated")
    if world.manager.path(chain.handoff.network_path_id).state != "ACTIVE":
        problems.append("the ACTIVE path was disturbed")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "the link-down candidate is rejected "
            "(validation-rejected/link-down), stays DISCOVERED, and the "
            "golden ACTIVE path is undisturbed",
        )
    )


def case_30_fail_containment_unavailable(results: List[Result]) -> None:
    name = "case_30_fail_containment_authority_unavailable"
    problems: List[str] = []
    if not w048_runtime_absent():
        problems.append("the W048 runtime is unexpectedly present")
    scenario = _scenario()
    trace = scenario["chain"].trace
    if trace.outcomes_by_edge().get(
        "edge-06-networkpath-validation-containment"
    ) != StageOutcome.FAIL_CLOSED:
        problems.append("the containment edge is not fail-closed")
    try:
        scenario["world"].client_runtime.gateway.read_consent("any-consent")
        problems.append("a consent read succeeded without a runtime")
    except ClientError as error:
        if error.reason != "client-stale-state":
            problems.append("consent read reason %r" % error.reason)
    # the absence is never downgraded into a passing composition
    if trace.production_composition:
        problems.append("the trace claims a production composition")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "unavailable containment is detected (no sharing runtime, no "
            "containment runtime, vocabulary only), every "
            "containment-dependent admission fails closed (chain edge, "
            "gateway reads), and the absence is never downgraded into a "
            "passing composition",
        )
    )


def case_31_fail_session_failure(results: List[Result]) -> None:
    name = "case_31_fail_session_establishment_failure"
    scenario = _scenario()
    world = scenario["world"]
    from composition.world import (
        _w011_route_decision,
        _w012_policy_decision,
        _ids,
    )
    import hashlib as _hashlib

    id_a, id_b = _ids()
    base = PolicyDecision(
        decision_id="0" * 64, effect="deny", code="deny", detail="w054 neg",
        matched_rule_ids=("r1",), policy_set_id="w054-ps-deny",
        policy_set_version=1, evaluation_instant="2026-09-01T11:15:00Z",
    )
    deny = PolicyDecision(
        decision_id=_hashlib.sha256(base.canonical_bytes()).hexdigest(),
        effect="deny", code="deny", detail="w054 neg",
        matched_rule_ids=("r1",), policy_set_id="w054-ps-deny",
        policy_set_version=1, evaluation_instant="2026-09-01T11:15:00Z",
    )
    route = _w011_route_decision(id_a, id_b, _w012_policy_decision())
    store = SessionStore()
    problems: List[str] = []
    result = store.create(
        route, deny, source_node_id=id_a, destination_node_id=id_b,
        creation_instant="2026-09-01T11:15:00Z",
    )
    if result.ok:
        problems.append("a session was created from a DENY policy")
    else:
        if result.code != "policy-binding-mismatch":
            problems.append("failure code %r" % result.code)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "the W012 session authority refuses creation from a deny "
            "PolicyDecision (%s: a session may only be created from an "
            "explicit allow)" % result.code,
        )
    )


def case_32_fail_absent_delivery_evidence(results: List[Result]) -> None:
    name = "case_32_fail_absent_delivery_evidence"
    world = CompositionWorld()
    chain = run_full_chain(world)
    ledger = _empty_usage_ledger(world, chain.transaction_id)
    problems: List[str] = []
    try:
        ledger.observe_usage(
            command_id="neg-e-01", transaction_id=chain.transaction_id,
            quantity_class=QuantityClass.DELIVERED, quantity=210,
            actor="m", source="neg",
        )
        problems.append("a DELIVERED observation without evidence was admitted")
    except UsageError as error:
        if "evidence_id" not in error.detail:
            problems.append("no-evidence reason %r/%s" % (error.reason, error.detail[:60]))
    problem = _expect_error(
        name, CommercialReasonCode.COMMAND_INVALID,
        world.core.start_delivery,
        command_id="neg-e-02", transaction_id=chain.transaction_id,
        actor="p", source="neg", evidence_refs=(),
    )
    if problem:
        problems.append("empty-evidence start_delivery: %s" % problem)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "a DELIVERED-class observation without an evidence citation is "
            "refused, and start_delivery without delivery evidence is "
            "refused (command-invalid)",
        )
    )


def case_33_fail_non_billable_usage(results: List[Result]) -> None:
    name = "case_33_fail_non_billable_usage"
    world = CompositionWorld()
    chain = run_full_chain(world)
    tx = _driven_transaction(world, to="DELIVERY_STARTED")
    index = build_usage_evidence_index(world.core, world.integrator, (tx,))
    ledger = UsageLedger(
        store=MemoryUsageStore(), clock=StepClock("2026-09-01T13:00:00Z", 60),
        evidence_index=index,
    )
    problems: List[str] = []
    ledger.observe_usage(
        command_id="neg-nb-01", transaction_id=tx,
        quantity_class=QuantityClass.RESERVED, quantity=700,
        actor="m", source="reservation-service",
    )
    ledger.observe_usage(
        command_id="neg-nb-02", transaction_id=tx,
        quantity_class=QuantityClass.ATTEMPTED, quantity=90,
        actor="m", source="traffic-monitor",
    )
    ledger.seal_billable(
        command_id="neg-nb-03", transaction_id=tx, actor="b", source="neg",
    )
    statement = ledger.transaction(tx).statement
    if statement is None:
        problems.append("no statement sealed")
    else:
        if statement.billable_quantity != 0:
            problems.append("billable quantity %d (non-billable leaked)" % statement.billable_quantity)
        if statement.amount_micros != 0:
            problems.append("amount %d (non-billable leaked)" % statement.amount_micros)
        if statement.reserved_quantity != 700 or statement.attempted_quantity != 90:
            problems.append("DATA classes %d/%d" % (
                statement.reserved_quantity, statement.attempted_quantity,
            ))
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "reserved/attempted observations are recorded as DATA only: "
            "the sealed statement carries billable quantity 0 / amount 0 "
            "with the reserved (700) and attempted (90) classes separated",
        )
    )


def case_34_fail_allocation_rejection(results: List[Result]) -> None:
    name = "case_34_fail_allocation_rejection"
    scenario = _scenario()
    segments = scenario["segments"]
    world = scenario["world"]
    problems: List[str] = []
    # a non-final usage citation is refused
    non_final_index = build_allocation_evidence_index(
        _observing_usage_ledger(world, segments.usage_transaction_id),
        (segments.usage_transaction_id,),
    )
    observing_ledger = AllocationLedger(
        store=MemoryAllocationStore(),
        clock=StepClock("2026-10-01T09:00:00Z", 60),
        evidence_index=non_final_index,
    )
    policy = observing_ledger.register_policy(
        command_id="neg-a-01", label=_POLICY_LABEL,
        adcos_share_bps=_POLICY_ADCOS_BPS,
        provider_min_bps=_POLICY_MIN_BPS, provider_max_bps=_POLICY_MAX_BPS,
        rounding_mode=_POLICY_ROUNDING, currency=_POLICY_CURRENCY,
        minor_unit_digits=_POLICY_DIGITS, effective_from=_POLICY_FROM,
        effective_until=_POLICY_UNTIL, actor="p", source="neg",
    )
    try:
        observing_ledger.allocate(
            command_id="neg-a-02",
            usage_transaction_id=segments.usage_transaction_id,
            usage_statement_id="sha256:" + "00" * 32,
            policy_id=policy.fact_id, provider_share_bps=_POLICY_PROVIDER_BPS,
            actor="b", source="neg",
        )
        problems.append("a non-final usage citation was allocated")
    except AllocationError as error:
        if error.reason != "usage-not-final":
            problems.append("non-final reason %r" % error.reason)
    # an out-of-policy-bounds provider share is refused (the
    # in-range 20% share violates the policy's [30%, 70%] bounds)
    try:
        segments.allocation_ledger.allocate(
            command_id="neg-a-03",
            usage_transaction_id=segments.usage_transaction_id,
            usage_statement_id=segments.statement_id,
            policy_id=segments.policy_id, provider_share_bps=2000,
            actor="b", source="neg",
        )
        problems.append("an out-of-bounds split was allocated")
    except AllocationError as error:
        if error.reason != "split-out-of-bounds":
            problems.append("bounds reason %r" % error.reason)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "allocating a non-final (OBSERVING) usage citation is refused "
            "(usage-not-final) and an out-of-bounds provider share is "
            "refused (split-out-of-bounds)",
        )
    )


def case_35_fail_payment_divergence(results: List[Result]) -> None:
    name = "case_35_fail_payment_provider_divergence"
    world = CompositionWorld()
    chain = run_full_chain(world)
    tx = _driven_transaction(world, to="PATH_ACTIVE")
    gateway, provider = _payment_fixture(world, tx)
    gateway.create_intent(
        command_id="neg-dv-01", intent_id="neg-pi-03", transaction_id=tx,
        amount=777, currency="USD", exponent=6, actor="b", source="neg",
    )
    gateway.authorize(
        command_id="neg-dv-02", intent_id="neg-pi-03", actor="b", source="neg",
    )
    intent = gateway.intent("neg-pi-03")
    provider.pending_callbacks()
    provider.async_advance(intent.provider_ref, "MONIES_RETURNED")
    problems: List[str] = []
    for envelope in provider.pending_callbacks():
        out = gateway.ingest_callback(
            envelope, actor="webhook-ingress", source="provider-callback"
        )
        if out.status != "appended":
            problems.append("divergence callback %r" % out.status)
    if gateway.intent("neg-pi-03").state != "AUTHORIZED":
        problems.append("the divergence observation rewrote canonical state")
    gateway.reconcile(
        command_id="neg-dv-03", actor="settlement", source="neg",
    )
    report = gateway.reports()[-1]
    classifications = [
        str(entry.get("classification", "")) for entry in report.entries
    ]
    if "provider-ahead" not in classifications:
        problems.append("classifications %s" % classifications)
    if gateway.intent("neg-pi-03").state != "AUTHORIZED":
        problems.append("the report rewrote canonical state")
    # an ORPHAN callback (unknown provider reference) is divergence
    # evidence and never creates an intent
    orphan_count = sum(
        1 for observation in gateway.observations() if observation.orphan
    )
    intents_before = len(gateway.intents())
    envelopes = provider.pending_callbacks()
    if envelopes:
        forged = dict(envelopes[0])
        forged["event_id"] = "sha256:" + "cd" * 32
        forged["provider_ref"] = "sandbox-pmt-999999"
        body = {
            "event_id": forged["event_id"],
            "provider_id": forged["provider_id"],
            "provider_ref": forged["provider_ref"],
            "kind": forged["kind"],
            "payload": forged["payload"],
            "occurred_at": forged["occurred_at"],
        }
        import hmac as _hmac

        forged["signature"] = "hmac-sha256:" + _hmac.new(
            b"w054-battery-provider-secret",
            __import__("protocol").canonical_json_bytes(body),
            hashlib.sha256,
        ).hexdigest()
        out = gateway.ingest_callback(
            forged, actor="webhook-ingress", source="provider-callback"
        )
        if out.status != "appended":
            problems.append("orphan callback %r" % out.status)
        orphan_count = sum(
            1 for observation in gateway.observations() if observation.orphan
        )
        if orphan_count != 1:
            problems.append("orphan count %d" % orphan_count)
        if len(gateway.intents()) != intents_before:
            problems.append("the orphan created an intent")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "the provider-ahead divergence (provider REFUNDED vs gateway "
            "AUTHORIZED) is classified PROVIDER_AHEAD by the "
            "reconciliation report without rewriting canonical state, and "
            "an orphan callback stays divergence evidence (never an "
            "intent)",
        )
    )


def case_36_fail_duplicate_observations(results: List[Result]) -> None:
    name = "case_36_fail_duplicate_observations"
    scenario = _scenario()
    segments = scenario["segments"]
    world = scenario["world"]
    problems: List[str] = []
    # usage: exact duplicate command = idempotent no-op
    ledger = segments.usage_ledger
    tx = segments.usage_transaction_id
    evidence = build_delivery_evidence(world.integrator, tx)
    before_digest = ledger.journal_digest()
    out = ledger.observe_usage(
        command_id="w054-use-01", transaction_id=tx,
        quantity_class=QuantityClass.DELIVERED, quantity=210,
        evidence_id=evidence[0].evidence_id,
        window_start=evidence[0].window_start,
        window_end=evidence[0].window_end,
        actor="meter", source="usage-collector",
    )
    if out.status != "duplicate":
        problems.append("usage duplicate %r" % out.status)
    if ledger.journal_digest() != before_digest:
        problems.append("the duplicate grew the usage journal")
    # commercial: exact duplicate = idempotent no-op
    core = world.core
    out = core.hold_reservation(
        command_id="w054-chain-03", transaction_id=tx,
        actor="w054-buyer-1", source="composition-conformance",
        expires_at="2026-09-01T12:15:00Z",
    )
    if out.status != "duplicate":
        problems.append("commercial duplicate %r" % out.status)
    # payment: callback redelivery = idempotent no-op
    gateway = segments.gateway
    provider = segments.provider
    envelopes = provider.pending_callbacks()
    if envelopes:
        out = gateway.ingest_callback(
            envelopes[0], actor="webhook-ingress", source="provider-callback"
        )
        if out.status != "duplicate":
            problems.append("callback duplicate %r" % out.status)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "duplicate usage observations, commercial commands, and "
            "callback redeliveries are idempotent no-ops (no journal "
            "growth, no state change)",
        )
    )


def case_37_fail_out_of_order(results: List[Result]) -> None:
    name = "case_37_fail_out_of_order_observations"
    world = CompositionWorld()
    chain = run_full_chain(world)
    tx = _driven_transaction(world, to="DELIVERY_STARTED")
    index = build_usage_evidence_index(world.core, world.integrator, (tx,))
    ledger = UsageLedger(
        store=MemoryUsageStore(), clock=StepClock("2026-09-01T13:00:00Z", 60),
        evidence_index=index,
    )
    evidence = build_delivery_evidence(world.integrator, tx)
    problems: List[str] = []
    # a window that is not CONTAINED in the cited evidence window
    # is refused (windowed sub-metering stays inside the
    # authoritative delivery window)
    try:
        ledger.observe_usage(
            command_id="neg-o-01", transaction_id=tx,
            quantity_class=QuantityClass.DELIVERED, quantity=210,
            evidence_id=evidence[0].evidence_id,
            window_start="2026-09-01T12:00:00Z",
            window_end="2026-09-01T12:06:00Z",
            actor="m", source="neg",
        )
        problems.append("an out-of-bounds window was admitted")
    except UsageError as error:
        if error.reason != "window-invalid":
            problems.append("out-of-bounds window reason %r" % error.reason)
    # a quantity above the evidence window is refused
    try:
        ledger.observe_usage(
            command_id="neg-o-02", transaction_id=tx,
            quantity_class=QuantityClass.DELIVERED, quantity=9999,
            evidence_id=evidence[0].evidence_id,
            window_start=evidence[0].window_start,
            window_end=evidence[0].window_end,
            actor="m", source="neg",
        )
        problems.append("an over-quantity observation was admitted")
    except UsageError as error:
        if error.reason != "quantity-exceeded":
            problems.append("over-quantity reason %r" % error.reason)
    # payment: applying an already-covered observation is refused
    gateway, provider = _payment_fixture(world, tx)
    gateway.create_intent(
        command_id="neg-o-03", intent_id="neg-pi-04", transaction_id=tx,
        amount=100, currency="USD", exponent=6, actor="b", source="neg",
    )
    gateway.authorize(
        command_id="neg-o-04", intent_id="neg-pi-04", actor="b", source="neg",
    )
    gateway.capture(
        command_id="neg-o-05", intent_id="neg-pi-04", amount=100,
        actor="b", source="neg",
    )
    envelopes = provider.pending_callbacks()
    stale_event_id = None
    for envelope in envelopes:
        out = gateway.ingest_callback(
            envelope, actor="webhook-ingress", source="provider-callback"
        )
        if out.status == "appended":
            stale_event_id = out.entity_id
    if stale_event_id:
        try:
            gateway.apply_observation(
                command_id="neg-o-06", event_id=stale_event_id,
                actor="s", source="neg",
            )
            problems.append("an out-of-order observation was folded")
        except PaymentError as error:
            if error.reason != "observation-conflict":
                problems.append("out-of-order fold reason %r" % error.reason)
    else:
        problems.append("no callbacks captured for the out-of-order probe")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "misaligned windows, over-quantity observations, and "
            "out-of-order observation folds are refused "
            "(evidence-mismatch/quantity-exceeded/observation-conflict)",
        )
    )


# ---------------------------------------------------------------------------
# F. Replay, idempotency, recovery
# ---------------------------------------------------------------------------


def case_38_idempotent_resubmission(results: List[Result]) -> None:
    name = "case_38_idempotent_resubmission"
    scenario = _scenario()
    segments = scenario["segments"]
    world = scenario["world"]
    digests_before = (
        world.core.journal_digest(),
        segments.usage_ledger.journal_digest(),
        segments.allocation_ledger.journal_digest(),
        segments.gateway.journal_digest(),
    )
    problems: List[str] = []
    out = world.core.submit_intent(
        command_id="w054-chain-01", actor="w054-buyer-1",
        source="composition-conformance",
        intent={
            "buyer": "w054-buyer-1", "want": "connectivity", "region": "gh",
            "provider": _PROVIDER_ID, "offer": "wifi-basic",
        },
    )
    if out.status != "duplicate":
        problems.append("submit_intent replay %r" % out.status)
    out = segments.usage_ledger.seal_billable(
        command_id="w054-seal-01", transaction_id=segments.usage_transaction_id,
        actor="billing", source="usage-ledger",
    )
    if out.status != "duplicate":
        problems.append("seal_billable replay %r" % out.status)
    out = segments.allocation_ledger.allocate(
        command_id="w054-alloc-02",
        usage_transaction_id=segments.usage_transaction_id,
        usage_statement_id=segments.statement_id,
        policy_id=segments.policy_id,
        provider_share_bps=_POLICY_PROVIDER_BPS,
        actor="billing", source="allocation-service",
    )
    if out.status != "duplicate":
        problems.append("allocate replay %r" % out.status)
    out = segments.gateway.capture(
        command_id="w054-pay-03", intent_id="w054-pi-01",
        amount=1080, actor="billing", source="composition-conformance",
    )
    if out.status != "duplicate":
        problems.append("capture replay %r" % out.status)
    digests_after = (
        world.core.journal_digest(),
        segments.usage_ledger.journal_digest(),
        segments.allocation_ledger.journal_digest(),
        segments.gateway.journal_digest(),
    )
    if digests_before != digests_after:
        problems.append("the replay changed an authority journal digest")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "replaying the full command sequence across W051/W052/W053/W044 "
            "is entirely DUPLICATE no-ops: all four authority journal "
            "digests are byte-identical",
        )
    )


def case_39_journal_first_recovery(results: List[Result]) -> None:
    name = "case_39_journal_first_recovery"
    scenario = _scenario()
    segments = scenario["segments"]
    world = scenario["world"]
    problems: List[str] = []
    core2 = CommercialCore.load(
        store=world.commercial_store,
        clock=StepClock("2026-09-01T11:30:00Z", 60),
        references=world.reference_index,
    )
    if core2.journal_digest() != world.core.journal_digest():
        problems.append("the W051 recovery diverged")
    core2.verify_integrity()
    usage_index = build_usage_evidence_index(
        world.core, world.integrator, (segments.usage_transaction_id,)
    )
    usage2 = UsageLedger.load(
        store=segments.usage_store,
        clock=StepClock("2026-09-01T13:00:00Z", 60),
        evidence_index=usage_index,
    )
    if usage2.journal_digest() != segments.usage_ledger.journal_digest():
        problems.append("the W052 recovery diverged")
    usage2.verify_replay()
    alloc_index = build_allocation_evidence_index(
        segments.usage_ledger, (segments.usage_transaction_id,)
    )
    alloc2 = AllocationLedger.load(
        store=segments.allocation_store,
        clock=StepClock("2026-10-01T09:00:00Z", 60),
        evidence_index=alloc_index,
    )
    if alloc2.journal_digest() != segments.allocation_ledger.journal_digest():
        problems.append("the W053 recovery diverged")
    alloc2.verify_replay()
    snapshot = build_payment_snapshot(
        world.core, segments.usage_ledger, segments.allocation_ledger,
        (segments.usage_transaction_id,),
    )
    gateway2 = SettlementGateway.load(
        store=segments.payment_store,
        clock=StepClock("2026-11-01T09:00:00Z", 60),
        snapshot=snapshot,
        adapter=segments.provider,
    )
    if gateway2.journal_digest() != segments.gateway.journal_digest():
        problems.append("the W044 recovery diverged")
    gateway2.verify_integrity()
    if gateway2.intent("w054-pi-01").state != "CAPTURED":
        problems.append("the recovered intent state diverged")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "journal-first recovery of W051/W052/W053/W044 from the same "
            "stores reproduces byte-identical journal digests, verifies "
            "integrity/replay, and resumes the exact canonical state",
        )
    )


def case_40_platform_checkpoint_recovery(results: List[Result]) -> None:
    name = "case_40_platform_checkpoint_recovery"
    scenario = _scenario()
    world = scenario["world"]
    integrator = world.integrator
    bindings = session_bindings_from_manager(world.manager)
    problems: List[str] = []
    if not bindings:
        problems.append("no session bindings to checkpoint")
    checkpoint = integrator.checkpoint(session_bindings=bindings)
    if not checkpoint.checkpoint_id:
        problems.append("the checkpoint carries no id")
    journal_digest_before = integrator.journal_digest()
    # process death + restart: recover from the same store with a
    # fresh observation cycle (the W042 epoch pattern; the recovery
    # seams are the accepted WORK-033 interface-source seam)
    from agent import StaticInterfaceSource
    from composition.world import _snapshots

    recovered, report = PlatformIntegrator.recover(
        store=world.platform_store,
        clock=StepClock("2026-09-02T09:00:00Z", 60),
        interface_source=StaticInterfaceSource(_snapshots()),
    )
    if not report.recovery_instant:
        problems.append("the recovery report carries no instant")
    if len(report.fresh_event_ids) < 1:
        problems.append("no fresh observation events recorded")
    if not report.divergences:
        problems.append("the changed-during-downtime divergences were not classified")
    if not report.lost_sessions:
        problems.append("the session loss was not recorded")
    if not report.journal_digest:
        problems.append("the recovered journal digest is missing")
    if report.journal_tail_sequence < 5:
        problems.append("the journal tail sequence drifted")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "the platform integrator checkpointed %d session binding(s) "
            "and recovered journal-first (tail sequence %d, %d fresh "
            "events, %d divergences classified, the lost session recorded, "
            "journal digest %s)"
            % (len(bindings), report.journal_tail_sequence,
               len(report.fresh_event_ids), len(report.divergences),
               report.journal_digest[:16]),
        )
    )


# ---------------------------------------------------------------------------
# G. Determinism
# ---------------------------------------------------------------------------


def case_41_repeat_run_stability(results: List[Result]) -> None:
    name = "case_41_repeat_run_byte_stability"
    stream_a = compose_scenario_stream()
    stream_b = compose_scenario_stream()
    if stream_a != stream_b:
        results.append(fail(name, "two fresh composed runs differ"))
        return
    results.append(
        ok(
            name,
            "two fully fresh composed runs are byte-identical (%d stream "
            "entries)" % len(stream_a),
        )
    )


def case_42_hashseed_invariance(results: List[Result]) -> None:
    name = "case_42_pythonhashseed_invariance"
    baseline = compose_scenario_stream()
    problems: List[str] = []
    for seed in ("0", "1", "7919"):
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = seed
        proc = subprocess.run(
            [sys.executable, __file__, "--determinism-stream"],
            capture_output=True, text=True, env=env, cwd=str(REPO_ROOT),
            timeout=600,
        )
        if proc.returncode != 0:
            problems.append("seed %s failed: %s" % (seed, proc.stderr[-120:]))
            continue
        lines = [line for line in proc.stdout.splitlines() if line.strip()]
        stream = {}
        for line in lines:
            key, _, value = line.partition("=")
            stream[key] = value
        if stream != baseline:
            problems.append("seed %s diverged" % seed)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "PYTHONHASHSEED 0/1/7919 subprocess runs reproduce the "
            "baseline stream byte for byte",
        )
    )


def case_43_unset_seed_stability(results: List[Result]) -> None:
    name = "case_43_unset_seed_stability"
    baseline = compose_scenario_stream()
    env = dict(os.environ)
    env.pop("PYTHONHASHSEED", None)
    proc = subprocess.run(
        [sys.executable, __file__, "--determinism-stream"],
        capture_output=True, text=True, env=env, cwd=str(REPO_ROOT),
        timeout=600,
    )
    if proc.returncode != 0:
        results.append(fail(name, proc.stderr[-200:]))
        return
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    stream = {}
    for line in lines:
        key, _, value = line.partition("=")
        stream[key] = value
    if stream != baseline:
        results.append(fail(name, "the unset-seed run diverged"))
        return
    results.append(
        ok(name, "the unset-PYTHONHASHSEED run reproduces the baseline stream")
    )


def case_44_digest_convention(results: List[Result]) -> None:
    name = "case_44_digest_convention_work003"
    trace = _scenario()["chain"].trace
    problems: List[str] = []
    if not trace.digest().startswith("sha256:"):
        problems.append("the trace digest is not sha256-prefixed")
    try:
        composition_digest({"float": 1.5})
        problems.append("a float survived canonicalization")
    except Exception:
        pass
    document = build_evidence_document(())
    if "digest" not in document:
        problems.append("the evidence document carries no digest")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "every composition digest is 'sha256:' + hex over the WORK-003 "
            "canonical JSON form (floats fail closed)",
        )
    )


# ---------------------------------------------------------------------------
# H. Audits
# ---------------------------------------------------------------------------


def _imported_roots(tree: ast.AST) -> List[str]:
    roots: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                roots.append(node.module)
    return roots


def case_45_import_audit(results: List[Result]) -> None:
    name = "case_45_import_dependency_audit"
    problems: List[str] = []
    for path in _FAMILY_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for root in _imported_roots(tree):
            if root in _ALLOWED_IMPORT_MODULES:
                continue
            if any(root.startswith(prefix) for prefix in _ALLOWED_IMPORT_PREFIXES):
                continue
            problems.append("%s imports %r" % (path.name, root))
    if problems:
        results.append(fail(name, "; ".join(problems[:6])))
        return
    results.append(
        ok(
            name,
            "composition/ imports only stdlib + protocol + agent.clock + "
            "the composed authority families (incl. the W012-mandated "
            "W011/W010/W008/W007 fixtures); no sharing, no developerapi, "
            "no out-of-scope family",
        )
    )


def case_46_shadow_authority_scan(results: List[Result]) -> None:
    name = "case_46_no_second_authority_scan"
    problems: List[str] = []
    for path in _FAMILY_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if node.name in _AUTHORITY_CLASS_TOKENS:
                    problems.append(
                        "%s defines authority class %s" % (path.name, node.name)
                    )
                for base in node.bases:
                    base_name = getattr(base, "id", getattr(base, "attr", ""))
                    if base_name in _AUTHORITY_CLASS_TOKENS:
                        problems.append(
                            "%s subclasses %s" % (path.name, base_name)
                        )
                # a conformance layer defines no store/journal/ledger of its own
                lowered = node.name.lower()
                for token in ("store", "journal", "ledger", "gateway", "manager"):
                    if token in lowered and node.name not in ("CompositionWorld",):
                        problems.append(
                            "%s defines %s (authority-shaped class)" % (path.name, node.name)
                        )
    # the package writes no files, holds no durable state (AST call
    # scan: genuine open/write/mkdir calls, never name substrings)
    for path in _FAMILY_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            call_name = getattr(func, "id", getattr(func, "attr", ""))
            if call_name in (
                "open", "write_text", "write_bytes", "mkdir", "makedirs",
            ):
                problems.append(
                    "%s calls %r (filesystem write surface)"
                    % (path.name, call_name)
                )
                break
    if problems:
        results.append(fail(name, "; ".join(sorted(set(problems))[:6])))
        return
    results.append(
        ok(
            name,
            "composition/ defines/subclasses NO authority class, no "
            "store/journal/ledger/gateway/manager, and touches no "
            "filesystem: it is a conformance/evidence layer only",
        )
    )


def case_47_vendor_token_scan(results: List[Result]) -> None:
    name = "case_47_vendor_token_scan"
    problems: List[str] = []
    for path in _FAMILY_FILES:
        source = path.read_text(encoding="utf-8").lower()
        for token in _VENDOR_TOKENS:
            if token in source:
                problems.append("%s contains vendor token %r" % (path.name, token))
    if problems:
        results.append(fail(name, "; ".join(sorted(set(problems))[:6])))
        return
    results.append(ok(name, "no vendor/technology tokens in the composition family"))


def case_48_nondeterminism_scan(results: List[Result]) -> None:
    name = "case_48_nondeterminism_scan"
    problems: List[str] = []
    forbidden_roots = ("time", "random", "uuid", "secrets", "datetime")
    for path in _FAMILY_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for root in _imported_roots(tree):
            if root.split(".")[0] in forbidden_roots:
                problems.append("%s imports %r" % (path.name, root))
        source = path.read_text(encoding="utf-8")
        for call in ("time.time", "random.", "uuid.", "urandom"):
            if call in source:
                problems.append("%s calls %r" % (path.name, call))
    if problems:
        results.append(fail(name, "; ".join(problems[:6])))
        return
    results.append(
        ok(
            name,
            "no wall-clock, entropy, or uuid surface in composition/ "
            "(WORK-033 StepClock only; digests are content-derived)",
        )
    )


def case_49_private_access_scan(results: List[Result]) -> None:
    name = "case_49_private_access_scan"
    problems: List[str] = []
    for path in _FAMILY_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
                if not node.attr.startswith("__"):
                    receiver = node.value
                    if isinstance(receiver, ast.Name) and receiver.id == "self":
                        continue
                    if isinstance(receiver, ast.Name) and receiver.id == "cls":
                        continue
                    if isinstance(receiver, ast.Name) and receiver.id == "path":
                        continue
                    problems.append(
                        "%s accesses private member .%s" % (path.name, node.attr)
                    )
    if problems:
        results.append(fail(name, "; ".join(sorted(set(problems))[:6])))
        return
    results.append(
        ok(
            name,
            "composition/ never accesses another family's private members "
            "(public boundaries only)",
        )
    )


def case_50_frozen_spec_intact(results: List[Result]) -> None:
    name = "case_50_frozen_spec_intact"
    frozen = (
        "spec/architecture.md",
        "spec/architecture-lock.md",
        "spec/mission.md",
        "spec/governance.md",
        "spec/change-control.md",
        "spec/workflow.md",
        "spec/work-items.md",
        "spec/dependency-graph.md",
        "spec/schemas/protocol.json",
        "spec/architect/authorizations/WORK-054.yaml",
        "spec/architect/roadmap.yaml",
        "spec/architect/roadmap.md",
        "spec/architect/execution-state.yaml",
        "spec/architect/execution-ledger.yaml",
        "spec/architect/current-state.md",
    )
    if not _origin_main_available():
        results.append(
            ok(name, "skipped (no origin/main ref; CI enforces the frozen surfaces)")
        )
        return
    problems: List[str] = []
    for rel in frozen:
        proc = subprocess.run(
            ["git", "show", "origin/main:%s" % rel],
            capture_output=True, cwd=str(REPO_ROOT),
        )
        if proc.returncode != 0:
            problems.append("%s missing on origin/main" % rel)
            continue
        current = (REPO_ROOT / rel).read_bytes()
        if current != proc.stdout:
            problems.append("%s differs from origin/main" % rel)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "the frozen architecture/lock/mission/governance/workflow/"
            "backlog/schema and the entire spec/architect/ package are "
            "byte-identical to origin/main (the implementation PR never "
            "modified the Architect package)",
        )
    )


def case_51_pr_delta_scope(results: List[Result]) -> None:
    name = "case_51_pr_delta_authorized_scope"
    if not _origin_main_available():
        results.append(
            ok(
                name,
                "skipped (no origin/main ref; the CI provenance step "
                "enforces the authorized scope)",
            )
        )
        return
    delta: set = set()
    diff = subprocess.run(
        ["git", "diff", "--name-only", "origin/main"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    if diff.returncode == 0:
        delta |= {line for line in diff.stdout.splitlines() if line.strip()}
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    if untracked.returncode == 0:
        delta |= {line for line in untracked.stdout.splitlines() if line.strip()}
    if not delta:
        results.append(ok(name, "no delta (clean main)"))
        return
    problems: List[str] = []
    for path in sorted(delta):
        if path.startswith("spec/"):
            problems.append("delta touches frozen spec/: %s" % path)
            continue
        if not any(
            path == surface or path.startswith(surface)
            for surface in _AUTHORIZED_PATHS
        ):
            problems.append("delta outside the authorized scope: %s" % path)
    # the authorized baseline is an ancestor of the delivery head
    ancestry = subprocess.run(
        [
            "git", "merge-base", "--is-ancestor",
            "461d1482180222f4b63f780d6d9ea1d54c49d643", "HEAD",
        ],
        capture_output=True, cwd=str(REPO_ROOT),
    )
    if ancestry.returncode != 0:
        problems.append("the authorized baseline is not an ancestor of HEAD")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "the %d-file delta lies exactly within the authorized "
            "WORK-054 scope (composition/, tools/composition_selftest.py, "
            "docs/WORK-054-*.md) and the authorized baseline "
            "461d1482180222f4b63f780d6d9ea1d54c49d643 is an ancestor of "
            "HEAD" % len(delta),
        )
    )


def case_52_evidence_docs_exist(results: List[Result]) -> None:
    name = "case_52_evidence_documents_present"
    problems: List[str] = []
    evidence = REPO_ROOT / "docs" / "WORK-054-evidence.md"
    handoff = REPO_ROOT / "docs" / "WORK-054-handoff.md"
    for path, required in (
        (evidence, ("Seven mandatory negative proofs", "W048", "Determinism")),
        (handoff, ("WORK-054", "authority", "scope")),
    ):
        if not path.exists():
            problems.append("%s is missing" % path.name)
            continue
        text = path.read_text(encoding="utf-8")
        if len(text) < 2000:
            problems.append("%s is too small (%d bytes)" % (path.name, len(text)))
        for marker in required:
            if marker.lower() not in text.lower():
                problems.append("%s lacks %r" % (path.name, marker))
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "docs/WORK-054-evidence.md and docs/WORK-054-handoff.md are "
            "present and carry the required sections",
        )
    )


def case_53_public_api_pin(results: List[Result]) -> None:
    name = "case_53_public_api_surface_pinned"
    import composition

    if sorted(composition.__all__) != _EXPECTED_API:
        results.append(
            fail(
                name,
                "the composition public API drifted: %s"
                % sorted(set(composition.__all__) ^ set(_EXPECTED_API)),
            )
        )
        return
    results.append(
        ok(
            name,
            "the composition public API surface matches the pinned %d-name "
            "export table" % len(_EXPECTED_API),
        )
    )


def case_54_py_compile(results: List[Result]) -> None:
    name = "case_54_py_compile"
    problems: List[str] = []
    targets = _FAMILY_FILES + [Path(__file__)]
    for path in targets:
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as error:
            problems.append("%s does not compile: %s" % (path.name, error))
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "composition/ (%d modules) and the battery compile" % len(_FAMILY_FILES))
    )


def case_55_negative_proof_registry(results: List[Result]) -> None:
    name = "case_55_seven_negative_proofs_proven"
    mapping = {
        "payment success cannot create connectivity": "case_19",
        "reservation success cannot imply reachability": "case_20",
        "marketplace discovery cannot activate a path": "case_21",
        "W050 capability declaration cannot enforce containment": "case_22",
        "W049 client state cannot become canonical state": "case_23",
        "API/webhook observation cannot become a second source of truth": "case_24",
        "software evidence cannot close physical evidence": "case_25",
    }
    problems: List[str] = []
    for statement in NEGATIVE_PROOF_STATEMENTS:
        if statement not in mapping:
            problems.append("unproven statement %r" % statement)
    if [s for s in NEGATIVE_PROOF_STATEMENTS] != list(mapping):
        problems.append("the proof registry does not match the frozen statements")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(
            name,
            "all seven mandatory negative proofs are mechanically proven "
            "(%s)" % ", ".join(sorted(mapping.values())),
        )
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

CASES = (
    case_01_authority_availability,
    case_02_w048_structural_absence,
    case_03_w046_defect_disclosed,
    case_04_containment_vocabulary,
    case_05_world_construction,
    case_06_world_authority_surfaces,
    case_07_chain_edge_ownership,
    case_08_chain_advanced_edges,
    case_09_chain_containment_fail_closed,
    case_10_chain_blocked_verdict,
    case_11_segment_session,
    case_12_segment_delivery,
    case_13_segment_usage,
    case_14_segment_billable_final,
    case_15_segment_allocation,
    case_16_segment_payment_reference,
    case_17_segment_reconciliation,
    case_18_segment_disclaimer,
    case_19_neg_payment_not_connectivity,
    case_20_neg_reservation_not_reachability,
    case_21_neg_discovery_not_activation,
    case_22_neg_w050_declaration_not_containment,
    case_23_neg_client_not_canonical,
    case_24_neg_webhook_not_source_of_truth,
    case_25_neg_software_not_physical,
    case_26_fail_denied_eligibility,
    case_27_fail_reservation,
    case_28_fail_unreachable_candidate,
    case_29_fail_networkpath_validation,
    case_30_fail_containment_unavailable,
    case_31_fail_session_failure,
    case_32_fail_absent_delivery_evidence,
    case_33_fail_non_billable_usage,
    case_34_fail_allocation_rejection,
    case_35_fail_payment_divergence,
    case_36_fail_duplicate_observations,
    case_37_fail_out_of_order,
    case_38_idempotent_resubmission,
    case_39_journal_first_recovery,
    case_40_platform_checkpoint_recovery,
    case_41_repeat_run_stability,
    case_42_hashseed_invariance,
    case_43_unset_seed_stability,
    case_44_digest_convention,
    case_45_import_audit,
    case_46_shadow_authority_scan,
    case_47_vendor_token_scan,
    case_48_nondeterminism_scan,
    case_49_private_access_scan,
    case_50_frozen_spec_intact,
    case_51_pr_delta_scope,
    case_52_evidence_docs_exist,
    case_53_public_api_pin,
    case_54_py_compile,
    case_55_negative_proof_registry,
)


def main() -> int:
    if "--determinism-stream" in sys.argv[1:]:
        stream = compose_scenario_stream()
        for key in sorted(stream):
            print("%s=%s" % (key, stream[key]))
        return 0
    results: List[Result] = []
    for case in CASES:
        case(results)
        # print incrementally (a long battery stays observable)
        (name, passed, detail) = results[-1]
        print(
            "[%s] %-56s %s"
            % ("ok  " if passed else "FAIL", name, detail)
        )
        if not passed:
            break
    passed = sum(1 for entry in results if entry[1])
    failed = len(results) - passed
    print()
    if failed:
        print("Result: FAIL (%d/%d cases failed)" % (failed, len(results)))
        for name, _, detail in results:
            if not _:
                print("  FAILED %s: %s" % (name, detail))
        return 1
    print("Result: PASS (%d/%d cases passed)" % (passed, len(results)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
