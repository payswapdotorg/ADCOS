#!/usr/bin/env python3
"""M011 — Vertical Proof: RoamLink battery (deterministic, stdlib only).

The SOFTWARE-class proof of the FROZEN 6-step RoamLink vertical boundary
(``spec/integration/vertical-proof.md``, ACR-014) over the ACCEPTED canonical
domains, under the R7 program authorization (R7-CORE-001, DEC-0101; child M011
"Vertical Proofs" scope: ``roamlink/`` + this battery + the evidence matrix;
requires-M013 satisfied by DEC-0113).

THE COMPOSITION MAP under proof (pinned by case_01):

- REAL AUTHORITY (accepted domains, composed through their public surfaces
  only): ``contracts`` (M002, DEC-0102), ``offers`` (M003, DEC-0103),
  ``commercial`` + ``usage`` (M009, DEC-0109), ``developerapi`` (M013,
  DEC-0113).
- DETERMINISTIC SIMULATION SEAMS (labeled test doubles of the NOT-YET-ACCEPTED
  children; never authority, never claimed delivered): M004
  eligibility/policy, M005 evidence/assurance, M006 execution plan, M007
  realization/adapter, M008 replan/failover (``roamlink/simulation.py``).

THE 6 STEPS under proof (each case names its step):

1. RoamLink requests connectivity for a defined subscriber cohort (the
   external application boundary; technology-neutral request over the accepted
   developer API; opaque cohort; LOCK-102/LOCK-120).
2. ADCOS exposes provider offers and commercial terms (the REAL M003 exchange
   surface; integer-minor-unit pricing; bounded commitments; service
   boundaries; LOCK-118 provenance).
3. A contract is accepted (the REAL M002 contract domain: SelectOffers +
   ActivateContract through the developer API routes; the M004 seam's verdict
   recorded as seam-labeled decision data).
4. RoamLink receives execution status and assurance events (the REAL contract
   walk through RecordExecutionActivation/BindExecutionArtifact/
   RecordDelivery/RecordAssurance; signed webhook observations; usage
   attribution to the ONE contract through the REAL M009 ledger; LOCK-106/
   LOCK-113).
5. Provider changes are absorbed behind the ADCOS contract (deterministic
   weakened-successor injection; honest DEGRADED status; the weakened
   alternate REJECTED at the change seam; admissible replacement bound behind
   the SAME contract; hard constraints byte-identical; LOCK-108).
6. RoamLink retains authority over mobile observation, device context, eSIM
   product behavior and mobile UX (the opaque application state never crosses;
   the cohort stays opaque; ADCOS supplies connectivity only; LOCK-120).

Structural discipline under proof: determinism (two fresh runs + PYTHONHASHSEED
subprocesses byte-identical), fail-closed negatives (subscriber-identity
tokens, vertical-semantics tokens, malformed cohorts, unsatisfiable policy,
LOCK-108 weakening attempts, vocabulary violations, webhook tampering,
duplicate observations), import discipline (the boundary composes ADCOS ONLY
through the developer API — the frozen boundary's architectural acceptance
clause; no pending child's real domain is imported), no second contract
authority in the boundary, LOCK-119 (no wall clock, no randomness, no
network, no secret material in any journal), py_compile, frozen spec intact,
and the PR delta shape against the ACTIVE repository-local authorization.

Evidence class: SOFTWARE (deterministic simulation batteries; the sandbox
environment's honest classification). No physical connectivity claim is made
anywhere; EVID-002..008 stay open/physical and untouched.
"""

from __future__ import annotations

import ast
import json
import os
import py_compile
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from roamlink import (  # noqa: E402
    APPLICATION_STATE_BLOB,
    AUTHORITY_DOMAINS,
    COHORT,
    COHORT_HANDLE_PATTERN,
    COHORT_MEMBER_PATTERN,
    ISSUANCE_KEY,
    OBSERVED_EVENT_TYPES,
    PROVIDER_CHANGE_KINDS,
    PROVIDER_A,
    PROVIDER_B,
    REALIZATION_STATES,
    SIMULATION_SEAMS,
    RoamLinkBoundary,
    RoamLinkError,
    RoamLinkReason,
    RoamLinkVerticalFlow,
    SubscriberCohort,
    WEAKENED_LATENCY_MS,
    build_weakened_successor_offer,
    hard_constraint_fingerprint,
)
from roamlink.cohort import CohortConnectivityRequest  # noqa: E402
from roamlink.simulation import (  # noqa: E402
    OBSERVATION_STATES,
    ProviderChange,
    SimulatedPolicyGate,
    SimulatedAssuranceEvaluator,
    SimulatedExecutionPlanner,
    SimulatedReplanner,
    build_provider_world,
)
from developerapi import webhooks as webhook_platform  # noqa: E402
from offers.errors import OfferError  # noqa: E402
from protocol.canonicalization import canonical_json_bytes  # noqa: E402

Result = Tuple[str, bool, str]

_FAMILY_FILES = tuple(sorted((REPO_ROOT / "roamlink").glob("*.py")))

#: The authorized M011 delta shape (the charter scope): the vertical harness
#: package, this battery, and the evidence matrix.
_AUTHORIZED_PATHS = (
    "roamlink/",
    "tools/roamlink_selftest.py",
    "docs/M011-evidence.md",
)

#: The pending children's REAL domains the roamlink package may never import
#: (their mechanics are simulation seams only; importing them would be
#: claiming the not-yet-delivered children as composed authority).
_PENDING_CHILD_MODULES = (
    "policy",
    "eligibility",
    "telemetry",
    "executionplans",
    "composition",
    "adapters",
    "sessions",
    "mobility",
    "multipath",
    "replan",
    "networkpath",
    "routing",
)

#: LOCK-119 discipline: modules that must never be imported by the
#: roamlink package (wall clock, randomness, uuids, network, secret
#: generation).
_FORBIDDEN_RUNTIMES = ("time", "random", "uuid", "socket", "secrets",
                       "requests", "urllib", "http", "asyncio", "threading")


def ok(name: str, detail: str = "") -> Result:
    return (name, True, detail)


def fail(name: str, detail: str) -> Result:
    return (name, False, detail)


def _expect_error(callable_thing, name: str, code: str) -> Tuple[bool, str]:
    """Run ``callable_thing`` and require a RoamLinkError with exactly the
    typed reason ``code`` (fail closed: any other outcome is a failure)."""
    try:
        callable_thing()
    except RoamLinkError as error:
        if error.code != code:
            return False, "wrong reason: expected %s, got %s (%s)" % (
                code, error.code, error)
        return True, str(error)
    except Exception as error:  # noqa: BLE001
        return False, "untyped exception escaped: %r" % (error,)
    return False, "the boundary accepted the invalid input (fail-open)"


# ---------------------------------------------------------------------------
# The golden run (shared fixture; fresh per construction)
# ---------------------------------------------------------------------------


def _golden() -> Any:
    flow = RoamLinkVerticalFlow()
    return flow, flow.run()


# ---------------------------------------------------------------------------
# The composition map (the disclosure the battery pins)
# ---------------------------------------------------------------------------


def case_01_composition_map_pinned(results: List[Result]) -> None:
    name = "case_01_composition_map_pinned"
    expected_authority = (
        ("M002", "contracts"),
        ("M003", "offers"),
        ("M009", "commercial+usage"),
        ("M013", "developerapi"),
    )
    expected_seams = (
        ("M004", "simulation-seam:m004-eligibility-policy"),
        ("M005", "simulation-seam:m005-evidence-assurance"),
        ("M006", "simulation-seam:m006-execution-plan"),
        ("M007", "simulation-seam:m007-realization-adapter"),
        ("M008", "simulation-seam:m008-replan-failover"),
    )
    problems: List[str] = []
    if tuple(AUTHORITY_DOMAINS) != expected_authority:
        problems.append("authority domains drifted: %r" % (AUTHORITY_DOMAINS,))
    if tuple(SIMULATION_SEAMS) != expected_seams:
        problems.append("simulation seams drifted: %r" % (SIMULATION_SEAMS,))
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "4 real authority domains (M002/M003/M009/M013) + 5 "
                 "labeled simulation seams (M004-M008): the honest "
                 "composition disclosure")
    )


def case_02_evidence_class_software(results: List[Result]) -> None:
    name = "case_02_evidence_class_software"
    _, result = _golden()
    if result.transcript.get("environment") != "sandbox":
        results.append(fail(name, "transcript environment is not sandbox"))
        return
    blob = b"".join(
        path.read_bytes() for path in _FAMILY_FILES
    )
    lowered = blob.decode("utf-8", "replace").lower()
    if "physical pass" in lowered or "physically verified" in lowered:
        results.append(fail(name, "a physical-verification claim exists"))
        return
    results.append(
        ok(name, "SOFTWARE-class: sandbox transcript + no physical "
                 "claim anywhere in the package")
    )


# ---------------------------------------------------------------------------
# STEP 1 — the cohort connectivity request
# ---------------------------------------------------------------------------


def case_03_step1_cohort_request_creates_intent(results: List[Result]) -> None:
    name = "case_03_step1_cohort_request_creates_intent"
    flow, result = _golden()
    step = result.transcript["steps"][0]
    problems: List[str] = []
    # the step record pins the state AT the step (the live contract
    # keeps walking; the journal carries the INTENT record)
    if step["contract_state"] != "INTENT":
        problems.append("step state %r" % step["contract_state"])
    if step["principal_kind"] != "APPLICATION":
        problems.append("principal %r" % step["principal_kind"])
    if step["step"] != 1 or step["kind"] != "cohort-connectivity-request":
        problems.append("step record shape %r" % step["kind"])
    if flow.service.environment() != "sandbox":
        problems.append("service environment %r" % flow.service.environment())
    journal_commands = [
        record.to_dict()["payload"].get("command")
        for record in result.store.journal()
    ]
    if journal_commands[0] != "create":
        problems.append("the journal does not open with the create command")
    if problems:
        results.append(fail(name, "; ".join(str(p) for p in problems)))
        return
    results.append(
        ok(name, "the technology-neutral request created an INTENT contract "
                 "with the APPLICATION principal (LOCK-103)")
    )


def case_04_step1_technology_neutral_request(results: List[Result]) -> None:
    name = "case_04_step1_technology_neutral_request"
    _, result = _golden()
    contract = result.store.contract(result.contract_id)
    problems: List[str] = []
    # LOCK-102: requirements are opaque typed references -- never a
    # mechanism, vendor or access technology
    mechanisms = ("5g", "wifi", "lte", "satellite", "fiber", "mpls",
                  "vendor", "esim")
    body = json.dumps(
        [r.to_dict() for r in contract.requirements]
        + [c.to_dict() for c in contract.hard_constraints]
        + [contract.termination.to_dict()],
        sort_keys=True,
    ).lower()
    for token in mechanisms:
        if token in body:
            problems.append("mechanism token %r in the request" % token)
    if not contract.requirements:
        problems.append("no requirements recorded")
    if not contract.hard_constraints:
        problems.append("no hard constraints recorded")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "the request carries opaque typed references + service-level "
                 "constraints only (LOCK-102: intent independence)")
    )


def case_05_step1_opaque_beneficiaries(results: List[Result]) -> None:
    name = "case_05_step1_opaque_beneficiaries"
    _, result = _golden()
    contract = result.store.contract(result.contract_id)
    handles = tuple(b.beneficiary_ref for b in contract.beneficiaries)
    problems: List[str] = []
    if len(handles) != COHORT.member_count:
        problems.append("beneficiary count %d" % len(handles))
    for handle in handles:
        if COHORT_MEMBER_PATTERN.fullmatch(handle) is None:
            problems.append("non-opaque member handle %r" % handle)
    kinds = {b.beneficiary_kind for b in contract.beneficiaries}
    if kinds != {"USER"}:
        problems.append("beneficiary kinds %r" % kinds)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "%d enumerated OPAQUE member handles (USER kind; the "
                 "membership table stays RoamLink's -- LOCK-120)"
                 % len(handles))
    )


def case_06_step1_cohort_grammar(results: List[Result]) -> None:
    name = "case_06_step1_cohort_grammar"
    problems: List[str] = []
    if COHORT_HANDLE_PATTERN.fullmatch(COHORT.cohort_handle) is None:
        problems.append("fixture handle fails its own grammar")
    for good in (
        "roamlink-cohort:v1:gh-accra:0007",
        "roamlink-cohort:v1:eu-roam:team-9",
    ):
        if COHORT_HANDLE_PATTERN.fullmatch(good) is None:
            problems.append("valid handle rejected: %r" % good)
    for bad in (
        "roamlink-cohort:v0:gh:1",
        "msisdn:+233201234567",
        "roamlink-cohort:v1:GH-ACCRA:UPPER",
        "",
        "roamlink-cohort:v1",
        "roamlink-cohort:v1:region:handle:extra",
    ):
        if COHORT_HANDLE_PATTERN.fullmatch(bad) is not None:
            problems.append("invalid handle accepted: %r" % bad)
    members = COHORT.member_handles()
    if members != tuple(sorted(members)):
        problems.append("member enumeration not sorted")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "the opaque cohort grammar admits exactly the bounded "
                 "region-scoped handle shapes")
    )


# ---------------------------------------------------------------------------
# STEP 2 — provider offers and commercial terms exposed
# ---------------------------------------------------------------------------


def case_07_step2_offers_exposed(results: List[Result]) -> None:
    name = "case_07_step2_offers_exposed"
    _, result = _golden()
    step = result.transcript["steps"][1]
    problems: List[str] = []
    if step["step"] != 2 or step["kind"] != "provider-offers-and-terms-exposed":
        problems.append("step record shape %r" % step["kind"])
    if step["exposed_offer_count"] != 2:
        problems.append("exposed %r offers" % step["exposed_offer_count"])
    providers = {term["provider"] for term in step["terms"]}
    if providers != {PROVIDER_A, PROVIDER_B}:
        problems.append("providers %r" % providers)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "two live provider listings exposed at the exposure instant")
    )


def case_08_step2_commercial_terms_shape(results: List[Result]) -> None:
    name = "case_08_step2_commercial_terms_shape"
    _, result = _golden()
    step = result.transcript["steps"][1]
    problems: List[str] = []
    for term in step["terms"]:
        pricing = term["pricing"]
        # integer minor units + exponent + currency + billing mode
        if not isinstance(pricing.get("price_minor"), int):
            problems.append("non-integer price %r" % pricing.get("price_minor"))
        if not isinstance(pricing.get("price_exponent"), int):
            problems.append("non-integer exponent")
        if not pricing.get("currency"):
            problems.append("no currency")
        if not pricing.get("billing_mode"):
            problems.append("no billing mode")
        for commitment in term["commitments"]:
            if "kind" not in commitment or "params" not in commitment:
                problems.append("commitment shape %r" % commitment)
        for boundary in term["service_boundaries"]:
            if not boundary.get("jurisdiction"):
                problems.append("no jurisdiction")
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "integer-minor-unit pricing, bounded commitments, service "
                 "boundaries, issuer provenance on every term (LOCK-118)")
    )


def case_09_step2_policy_gate_eligible(results: List[Result]) -> None:
    name = "case_09_step2_policy_gate_eligible"
    _, result = _golden()
    step = result.transcript["steps"][1]
    decision = step["policy_decision"]
    problems: List[str] = []
    if decision["verdict"] != "eligible":
        problems.append("verdict %r" % decision["verdict"])
    if decision["seam"] != "simulation-seam:m004-eligibility-policy":
        problems.append("seam label %r" % decision["seam"])
    if len(decision["eligible_offer_ids"]) != 2:
        problems.append("eligible %r" % decision["eligible_offer_ids"])
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "the M004 seam found both offers eligible and its verdict "
                 "carries the seam label (simulation material, never "
                 "delivered-child authority)")
    )


def case_10_step2_service_boundaries(results: List[Result]) -> None:
    name = "case_10_step2_service_boundaries"
    _, result = _golden()
    step = result.transcript["steps"][1]
    jurisdictions = {
        boundary["jurisdiction"]
        for term in step["terms"]
        for boundary in term["service_boundaries"]
    }
    if jurisdictions != {"GH"}:
        results.append(fail(name, "jurisdictions %r" % jurisdictions))
        return
    results.append(
        ok(name, "both listings declare the requested jurisdiction with "
                 "geography references")
    )


# ---------------------------------------------------------------------------
# STEP 3 — the contract is accepted
# ---------------------------------------------------------------------------


def case_11_step3_offers_selected_typed_references(results: List[Result]) -> None:
    name = "case_11_step3_offers_selected_typed_references"
    _, result = _golden()
    contract = result.store.contract(result.contract_id)
    accepted = contract.accepted_offers
    problems: List[str] = []
    if len(accepted) != 2:
        problems.append("accepted %d offers" % len(accepted))
    for reference in accepted:
        if reference.ref_kind != "offer":
            problems.append("ref kind %r" % reference.ref_kind)
        if not reference.value.startswith("sha256:"):
            problems.append("non-content-derived offer id")
    step = result.transcript["steps"][2]
    if step["step"] != 3 or step["kind"] != "contract-accepted":
        problems.append("step record shape %r" % step["kind"])
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "both offers bound through the real typed offer references "
                 "(the M003 bridge shape)")
    )


def case_12_step3_contract_activated(results: List[Result]) -> None:
    name = "case_12_step3_contract_activated"
    _, result = _golden()
    step = result.transcript["steps"][2]
    problems: List[str] = []
    if step["contract_state"] != "CONTRACT_ACTIVE":
        problems.append("step state %r" % step["contract_state"])
    journal_commands = [
        record.to_dict()["payload"].get("command")
        for record in result.store.journal()
    ]
    if "activate" not in journal_commands:
        problems.append("no activate command in the journal")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "the acceptance activated the contract (real "
                 "SelectOffers/ActivateContract commands over the API routes; "
                 "journal-recorded CONTRACT_ACTIVE)")
    )


def case_13_step3_policy_decision_recorded_as_data(results: List[Result]) -> None:
    name = "case_13_step3_policy_decision_recorded_as_data"
    _, result = _golden()
    step = result.transcript["steps"][2]
    reference = step["policy_decision_ref"]
    if reference.get("ref_kind") != "decision":
        results.append(fail(name, "ref kind %r" % reference.get("ref_kind")))
        return
    provenance = reference.get("provenance", {})
    if provenance.get("issuer") != "simulation-seam:m004-eligibility-policy":
        results.append(
            fail(name, "issuer %r" % provenance.get("issuer"))
        )
        return
    results.append(
        ok(name, "the simulated eligibility verdict rides as a typed decision "
                 "reference whose provenance issuer IS the seam label")
    )


# ---------------------------------------------------------------------------
# STEP 4 — execution status and assurance events
# ---------------------------------------------------------------------------


def case_14_step4_execution_activation_and_artifacts(results: List[Result]) -> None:
    name = "case_14_step4_execution_activation_and_artifacts"
    _, result = _golden()
    contract = result.store.contract(result.contract_id)
    artifacts = contract.execution_artifacts
    problems: List[str] = []
    if not artifacts:
        problems.append("no execution artifacts bound")
    for artifact in artifacts:
        if artifact.ref_kind != "execution-artifact":
            problems.append("ref kind %r" % artifact.ref_kind)
        issuer = artifact.provenance.issuer
        if not issuer.startswith("simulation-seam:m007"):
            problems.append("artifact issuer %r" % issuer)
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "execution artifacts ride the REAL BindExecutionArtifact "
                 "command as opaque references with the seam issuer "
                 "(LOCK-117: data, never authority)")
    )


def case_15_step4_delivery_and_assurance_states(results: List[Result]) -> None:
    name = "case_15_step4_delivery_and_assurance_states"
    _, result = _golden()
    step = result.transcript["steps"][3]
    problems: List[str] = []
    if step["step"] != 4 or step["kind"] != "execution-status-and-assurance-events":
        problems.append("step record shape %r" % step["kind"])
    if step["assurance_state"] != "compliant":
        problems.append("assurance %r" % step["assurance_state"])
    if step["boundary_assurance_state"] != "ASSURED":
        problems.append("boundary assurance %r" % step["boundary_assurance_state"])
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "real RecordDelivery/RecordAssurance walk: compliant "
                 "assurance recorded, ASSURED observed through the API read")
    )


def case_16_step4_execution_status_honest(results: List[Result]) -> None:
    name = "case_16_step4_execution_status_honest"
    _, result = _golden()
    step = result.transcript["steps"][3]
    if step["execution_status"] != "delivered-assured":
        results.append(
            fail(name, "status %r" % step["execution_status"])
        )
        return
    results.append(
        ok(name, "the lifecycle read reports the honest derived "
                 "classification (delivered-assured) -- never a physical "
                 "connectivity claim")
    )


def case_17_step4_signed_observations_received(results: List[Result]) -> None:
    name = "case_17_step4_signed_observations_received"
    _, result = _golden()
    observations = result.boundary.observations_for(result.contract_id)
    if not observations:
        results.append(fail(name, "no signed observations received"))
        return
    event_types = {record["event_type"] for record in observations}
    unknown = event_types - set(OBSERVED_EVENT_TYPES)
    if unknown:
        results.append(fail(name, "unsubscribed event types %r" % unknown))
        return
    results.append(
        ok(name, "%d signed observation events verified consumer-side "
                 "(signature + duplicate detection) and received"
                 % len(observations))
    )


def case_18_step4_assurance_read(results: List[Result]) -> None:
    name = "case_18_step4_assurance_read"
    _, result = _golden()
    # the step record pins what the boundary read AT step 4 (the live
    # contract keeps walking to settlement afterwards)
    step = result.transcript["steps"][3]
    state = step["boundary_assurance_state"]
    if state != "ASSURED":
        results.append(fail(name, "assurance read state %r" % state))
        return
    assurance = result.boundary.read_assurance(result.contract_id)
    obligations = assurance.get("assurance_obligations") or ()
    if not obligations:
        results.append(fail(name, "no assurance obligations in the read"))
        return
    for obligation in obligations:
        if obligation.get("ref_kind") != "assurance-obligation":
            results.append(
                fail(name, "obligation kind %r" % obligation.get("ref_kind"))
            )
            return
    results.append(
        ok(name, "the assurance read returns the contract state + the typed "
                 "obligation references (ASSURED observed at step 4)")
    )


def case_19_step4_usage_semantics_read(results: List[Result]) -> None:
    name = "case_19_step4_usage_semantics_read"
    _, result = _golden()
    usage = result.boundary.read_usage_semantics(result.contract_id)
    terms = usage.get("usage_pricing_terms")
    if not terms or terms.get("ref_kind") != "usage-pricing-terms":
        results.append(fail(name, "usage terms %r" % terms))
        return
    if not str(terms.get("value", "")).startswith("roamlink:"):
        results.append(fail(name, "terms value %r" % terms.get("value")))
        return
    results.append(
        ok(name, "the usage semantics read returns the opaque "
                 "usage-pricing-terms typed reference (LOCK-114)")
    )


# ---------------------------------------------------------------------------
# STEP 5 — provider changes absorbed behind the contract
# ---------------------------------------------------------------------------


def case_20_step5_superseded_offer_unresolvable(results: List[Result]) -> None:
    name = "case_20_step5_superseded_offer_unresolvable"
    _, result = _golden()
    step = [s for s in result.transcript["steps"]
            if s["kind"] == "provider-change-absorbed-behind-contract"][0]
    unabsorbable = step["unabsorbable_realizations"]
    if not unabsorbable:
        results.append(fail(name, "the superseded listing resolved (fail-open)"))
        return
    # the exchange must fail closed at resolution time for the superseded v1
    try:
        result.exchange.resolve(
            result.contract().accepted_offers[0], at_instant="2026-10-10T00:00:00Z"
        )
    except OfferError:
        results.append(
            ok(name, "the superseded provider-A listing is unresolvable at "
                     "the change instant (fail-closed resolution)")
        )
        return
    results.append(fail(name, "resolve did not fail closed for the superseded offer"))
    return


def case_21_step5_honest_degraded_status(results: List[Result]) -> None:
    name = "case_21_step5_honest_degraded_status"
    _, result = _golden()
    step = [s for s in result.transcript["steps"]
            if s["kind"] == "provider-change-absorbed-behind-contract"][0]
    degraded = step["degraded_assurance"]
    problems: List[str] = []
    if degraded["assurance_state"] != "degraded":
        problems.append("degraded state %r" % degraded["assurance_state"])
    if degraded["seam"] != "simulation-seam:m005-evidence-assurance":
        problems.append("degraded seam %r" % degraded["seam"])
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "the honest DEGRADED assurance recorded at the change (the "
                 "assurance seam's labeled verdict)")
    )


def case_22_step5_weakened_alternate_rejected(results: List[Result]) -> None:
    name = "case_22_step5_weakened_alternate_rejected"
    _, result = _golden()
    step = [s for s in result.transcript["steps"]
            if s["kind"] == "provider-change-absorbed-behind-contract"][0]
    outcome = step["replan_outcome"]
    # the rejected realization is the weakened successor's offer id
    rejected = outcome["rejected_realizations"]
    if len(rejected) != 1:
        results.append(fail(name, "rejected %r" % rejected))
        return
    # verify the rejected offer IS the weakened one (150ms > 100ms bound)
    rejected_offer = result.exchange.offer(rejected[0])
    latency = [
        c for c in rejected_offer.commitments if c.kind == "latency-bound-ms"
    ][0]
    if int(latency.params["max_ms"]) != WEAKENED_LATENCY_MS:
        results.append(fail(name, "rejected offer latency %r" % latency.params))
        return
    results.append(
        ok(name, "the weakened successor (latency %d ms vs the 100 ms bound) "
                 "was REJECTED at the change seam and recorded (LOCK-108)"
                 % WEAKENED_LATENCY_MS)
    )


def case_23_step5_constraint_fingerprint_preserved(results: List[Result]) -> None:
    name = "case_23_step5_constraint_fingerprint_preserved"
    _, result = _golden()
    step = [s for s in result.transcript["steps"]
            if s["kind"] == "provider-change-absorbed-behind-contract"][0]
    problems: List[str] = []
    if step["constraint_fingerprint_before"] != step["constraint_fingerprint_after"]:
        problems.append("fingerprints differ")
    if not step["constraints_preserved"]:
        problems.append("preserved flag false")
    if hard_constraint_fingerprint(result.contract()) != step["constraint_fingerprint_after"]:
        problems.append("the final contract fingerprint drifted")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "the hard-constraint set is byte-identical across the "
                 "provider-change absorption (LOCK-108)")
    )


def case_24_step5_accepted_offers_and_identity_unchanged(results: List[Result]) -> None:
    name = "case_24_step5_accepted_offers_and_identity_unchanged"
    _, result = _golden()
    step = [s for s in result.transcript["steps"]
            if s["kind"] == "provider-change-absorbed-behind-contract"][0]
    if not step["accepted_offers_unchanged"]:
        results.append(fail(name, "accepted offers changed across absorption"))
        return
    if result.contract().contract_id != result.contract_id:
        results.append(fail(name, "contract identity changed"))
        return
    results.append(
        ok(name, "the accepted-offer set and the contract identity are "
                 "unchanged: the change is absorbed BEHIND the contract")
    )


def case_25_step5_replacement_binds_same_contract(results: List[Result]) -> None:
    name = "case_25_step5_replacement_binds_same_contract"
    _, result = _golden()
    step = [s for s in result.transcript["steps"]
            if s["kind"] == "provider-change-absorbed-behind-contract"][0]
    replacement = step["replacement_segment"]
    problems: List[str] = []
    if replacement["provider"] != PROVIDER_B:
        problems.append("replacement provider is not provider B")
    if replacement["state"] not in REALIZATION_STATES:
        problems.append("replacement state %r" % replacement["state"])
    artifacts = result.contract().execution_artifacts
    if not any(
        a.value == "simseam:segment:%s" % replacement["segment_id"]
        for a in artifacts
    ):
        problems.append("the replacement artifact is not bound")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "provider B's admissible realization is bound behind the "
                 "SAME contract through the real bind command")
    )


def case_26_step5_recovery_status(results: List[Result]) -> None:
    name = "case_26_step5_recovery_status"
    _, result = _golden()
    step = [s for s in result.transcript["steps"]
            if s["kind"] == "provider-change-absorbed-behind-contract"][0]
    if step["recovered_execution_status"] != "delivered-assured":
        results.append(
            fail(name, "recovered status %r" % step["recovered_execution_status"])
        )
        return
    results.append(
        ok(name, "the boundary observed the recovered delivered-assured "
                 "status after the absorption")
    )


def case_27_step5_change_injection_deterministic(results: List[Result]) -> None:
    name = "case_27_step5_change_injection_deterministic"
    _, result = _golden()
    step = [s for s in result.transcript["steps"]
            if s["kind"] == "provider-change-absorbed-behind-contract"][0]
    change = step["change"]
    problems: List[str] = []
    if change["kind"] != "offer-superseded":
        problems.append("kind %r" % change["kind"])
    if change["instant"] != "2026-10-10T00:00:00Z":
        problems.append("instant %r" % change["instant"])
    if change["provider"] != PROVIDER_A:
        problems.append("provider %r" % change["provider"])
    if change["kind"] not in PROVIDER_CHANGE_KINDS:
        problems.append("outside the frozen vocabulary")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "the provider-change injection is a fixed fixture event at "
                 "a fixed instant from the frozen vocabulary")
    )


# ---------------------------------------------------------------------------
# The usage/commercial closing (still behind the ONE contract)
# ---------------------------------------------------------------------------


def case_28_usage_account_key_is_contract_citation(results: List[Result]) -> None:
    name = "case_28_usage_account_key_is_contract_citation"
    _, result = _golden()
    step = [s for s in result.transcript["steps"]
            if s["kind"] == "usage-attribution-and-settlement"][0]
    usage = step["usage"]
    problems: List[str] = []
    if usage.get("account_key") != result.contract_id:
        problems.append("account key %r" % usage.get("account_key"))
    if usage.get("attributed_observation_count") != usage.get("observation_count"):
        problems.append("attribution count mismatch")
    if usage.get("contract_citation") != result.contract_id:
        problems.append("statement citation %r" % usage.get("contract_citation"))
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "the usage ledger account key and the sealed statement "
                 "citation ARE the contract id (LOCK-113)")
    )


def case_29_usage_statement_attribution_and_arithmetic(results: List[Result]) -> None:
    name = "case_29_usage_statement_attribution_and_arithmetic"
    _, result = _golden()
    step = [s for s in result.transcript["steps"]
            if s["kind"] == "usage-attribution-and-settlement"][0]
    usage = step["usage"]
    quantity = usage["billable_quantity"]
    price = usage["unit_price_micros"]
    amount = usage["billable_amount_micros"]
    if quantity != 315:  # 120 + 90 + 45 + 60 (the four windows)
        results.append(fail(name, "billable quantity %r" % quantity))
        return
    if amount != quantity * price:
        results.append(
            fail(name, "amount %r != %r * %r" % (amount, quantity, price))
        )
        return
    if not usage["statement_id"].startswith("sha256:"):
        results.append(fail(name, "statement id %r" % usage["statement_id"]))
        return
    results.append(
        ok(name, "sealed statement: 315 billable units at %d micros = %d "
                 "micros, attributed to the one contract"
                 % (price, amount))
    )


def case_30_commercial_walk_contract_binding(results: List[Result]) -> None:
    name = "case_30_commercial_walk_contract_binding"
    _, result = _golden()
    step = [s for s in result.transcript["steps"]
            if s["kind"] == "usage-attribution-and-settlement"][0]
    commercial = step["commercial"]
    problems: List[str] = []
    if commercial.get("contract_binding") != result.contract_id:
        problems.append("binding %r" % commercial.get("contract_binding"))
    if commercial.get("final_state") != "SETTLED":
        problems.append("final state %r" % commercial.get("final_state"))
    if commercial.get("command_count") != 11:
        problems.append("command count %r" % commercial.get("command_count"))
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "the REAL M009 commercial core walked its 11-command "
                 "settlement chain bound to the one contract and settled")
    )


def case_31_contract_settled_state(results: List[Result]) -> None:
    name = "case_31_contract_settled_state"
    _, result = _golden()
    state = result.contract().state
    if state != "SETTLED":
        results.append(fail(name, "final contract state %r" % state))
        return
    results.append(
        ok(name, "the ONE contract walked to SETTLED behind the whole "
                 "vertical (usage-final -> settlement-pending -> settled)")
    )


# ---------------------------------------------------------------------------
# STEP 6 — the application authority boundary
# ---------------------------------------------------------------------------


def case_32_step6_application_state_never_crosses(results: List[Result]) -> None:
    name = "case_32_step6_application_state_never_crosses"
    _, result = _golden()
    blob_text = APPLICATION_STATE_BLOB.decode("utf-8", "replace")
    surfaces = {
        "transcript": json.dumps(result.transcript, sort_keys=True),
        "contract_journal": json.dumps(
            result.store.journal_digest(), sort_keys=True
        ),
        "offer_catalog": json.dumps(
            [o.to_dict() for o in result.exchange.active_offers(
                at_instant="2026-10-15T00:00:00Z")], sort_keys=True
        ),
        "api_journal": json.dumps(result.service.journal_digest(), sort_keys=True),
    }
    for label, material in surfaces.items():
        if result.boundary.application_state_crossed(material):
            results.append(
                fail(name, "the application state crossed into %s" % label)
            )
            return
    if blob_text in surfaces["transcript"]:
        results.append(fail(name, "blob text in transcript"))
        return
    digest = result.boundary.application_state_digest()
    if not digest.startswith("sha256:"):
        results.append(fail(name, "no application-state digest"))
        return
    results.append(
        ok(name, "the opaque application-owned state exists (digest %s...) "
                 "and never enters any ADCOS surface (LOCK-120)"
                 % digest[7:19])
    )


def case_33_step6_all_observations_attributed(results: List[Result]) -> None:
    name = "case_33_step6_all_observations_attributed"
    _, result = _golden()
    step = [s for s in result.transcript["steps"]
            if s["kind"] == "application-authority-retained"][0]
    problems: List[str] = []
    if step["step"] != 6 or step["kind"] != "application-authority-retained":
        problems.append("step record shape %r" % step["kind"])
    if not step["all_observations_attributed"]:
        problems.append("attribution flag false")
    if step["vertical_semantics_in_adcos"]:
        problems.append("vertical semantics present")
    if step["received_observation_count"] < 4:
        problems.append("only %d observations" % step["received_observation_count"])
    observations = result.boundary.received_observations()
    for record in observations:
        if record["resource_id"] != result.contract_id:
            problems.append("observation for %s" % record["resource_id"][:24])
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "every received observation is attributable to the one "
                 "contract through typed references (LOCK-106 attribution)")
    )


def case_34_step6_boundary_surface_is_developer_api_only(results: List[Result]) -> None:
    name = "case_34_step6_boundary_surface_is_developer_api_only"
    expected = {
        "register_observation_endpoint",
        "request_cohort_connectivity",
        "accept_provider_offers",
        "activate_acceptance",
        "read_execution_status",
        "read_assurance",
        "read_usage_semantics",
        "receive_observation",
        "received_observations",
        "observations_for",
        "application_state_digest",
        "application_state_crossed",
    }
    actual = {
        attribute for attribute in dir(RoamLinkBoundary)
        if not attribute.startswith("_") and callable(
            getattr(RoamLinkBoundary, attribute, None)
        )
    }
    if actual != expected:
        results.append(
            fail(name, "boundary surface drifted: extra=%r missing=%r"
                       % (sorted(actual - expected), sorted(expected - actual)))
        )
        return
    # the boundary is not a contract authority: it drives no contract
    # command and holds no store
    source = (REPO_ROOT / "roamlink" / "cohort.py").read_text(encoding="utf-8")
    for forbidden in ("ContractStore", "submit(", "CreateContract", "SelectOffers"):
        if forbidden in source:
            results.append(
                fail(name, "boundary references %r (contract authority leak)"
                           % forbidden)
            )
            return
    results.append(
        ok(name, "the boundary's whole surface is the accepted M013 route "
                 "set: no contract command, no store, no second authority "
                 "(LOCK-117/LOCK-120 + the frozen boundary's acceptance "
                 "clause)")
    )


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def case_35_determinism_two_fresh_runs(results: List[Result]) -> None:
    name = "case_35_determinism_two_fresh_runs"
    _, first = _golden()
    _, second = _golden()
    if first.digest != second.digest:
        results.append(fail(name, "%s != %s" % (first.digest, second.digest)))
        return
    if json.dumps(first.transcript, sort_keys=True) != json.dumps(
        second.transcript, sort_keys=True
    ):
        results.append(fail(name, "transcripts differ"))
        return
    results.append(
        ok(name, "two fresh runs produce byte-identical transcripts and "
                 "digests (%s)" % first.digest[:19])
    )


def case_36_determinism_hash_seeds(results: List[Result]) -> None:
    name = "case_36_determinism_hash_seeds"
    digests = []
    for seed in ("0", "1", "7919"):
        proc = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, %r); "
             "from roamlink import RoamLinkVerticalFlow; "
             "print(RoamLinkVerticalFlow().run().digest)" % str(REPO_ROOT)],
            capture_output=True, text=True,
            env={**os.environ, "PYTHONHASHSEED": seed},
        )
        if proc.returncode != 0:
            results.append(
                fail(name, "seed %s failed: %s" % (seed, proc.stderr[-300:]))
            )
            return
        digests.append(proc.stdout.strip())
    if len(set(digests)) != 1:
        results.append(fail(name, "digests differ across hash seeds: %r" % digests))
        return
    results.append(
        ok(name, "PYTHONHASHSEED 0/1/7919 subprocess runs agree (%s)"
                 % digests[0][:19])
    )


def case_37_transcript_json_round_trip(results: List[Result]) -> None:
    name = "case_37_transcript_json_round_trip"
    _, result = _golden()
    encoded = json.dumps(result.transcript, sort_keys=True)
    decoded = json.loads(encoded)
    if json.dumps(decoded, sort_keys=True) != encoded:
        results.append(fail(name, "round-trip not stable"))
        return
    try:
        canonical_json_bytes(decoded)
    except Exception as error:  # noqa: BLE001
        results.append(fail(name, "not canonically serializable: %r" % error))
        return
    results.append(
        ok(name, "the transcript round-trips through sorted and canonical "
                 "JSON byte-identically")
    )


def case_38_transcript_tamper_detected(results: List[Result]) -> None:
    name = "case_38_transcript_tamper_detected"
    flow, result = _golden()
    tampered = json.loads(json.dumps(result.transcript, sort_keys=True))
    tampered["steps"][0]["contract_state"] = "TAMPERED"
    digest_a = flow._transcript_digest(result.transcript)
    digest_b = flow._transcript_digest(tampered)
    if digest_a == digest_b:
        results.append(fail(name, "the digest does not bind the transcript"))
        return
    results.append(
        ok(name, "any transcript mutation changes the deterministic digest")
    )


# ---------------------------------------------------------------------------
# Fail-closed negatives
# ---------------------------------------------------------------------------


def case_39_negative_subscriber_identity_rejected(results: List[Result]) -> None:
    name = "case_39_negative_subscriber_identity_rejected"
    flow = RoamLinkVerticalFlow()
    request = CohortConnectivityRequest(
        cohort=COHORT,
        requirement_values=("roamlink-req:cohort-data-v1",),
        hard_constraints=(
            {"kind": "latency-bound", "params": {"max_ms": 100}},
        ),
        validity={"not_before": "2026-10-02T00:00:00Z",
                  "not_after": "2026-11-03T00:00:00Z"},
        termination={"conditions": ("principal-requested",)},
        recorded_at="2026-10-02T00:00:00Z",
        usage_pricing_terms_value="roamlink:envelope:msisdn-imsi-payload",
    )
    good, detail = _expect_error(
        lambda: request.intent_body(), name, RoamLinkReason.COHORT_NOT_OPAQUE
    )
    if not good:
        results.append(fail(name, detail))
        return
    if "msisdn" not in detail:
        results.append(fail(name, "detail %r" % detail))
        return
    results.append(
        ok(name, "subscriber-identity-shaped material never crosses into "
                 "ADCOS (LOCK-119/LOCK-120): rejected %r" % detail[:80])
    )


def case_40_negative_vertical_semantics_rejected(results: List[Result]) -> None:
    name = "case_40_negative_vertical_semantics_rejected"
    request = CohortConnectivityRequest(
        cohort=COHORT,
        requirement_values=("roamlink-req:esim-profile-install",),
        hard_constraints=({"kind": "geography", "params": {"region": "GH"}},),
        validity={"not_before": "2026-10-02T00:00:00Z",
                  "not_after": "2026-11-03T00:00:00Z"},
        termination={"conditions": ("principal-requested",)},
        recorded_at="2026-10-02T00:00:00Z",
    )
    good, detail = _expect_error(
        lambda: request.intent_body(), name,
        RoamLinkReason.VERTICAL_SEMANTICS_REJECTED,
    )
    if not good:
        results.append(fail(name, detail))
        return
    results.append(
        ok(name, "mobile/eSIM/UX semantics in a request body are rejected: "
                 "ADCOS supplies connectivity only (LOCK-120)")
    )


def case_41_negative_malformed_cohort(results: List[Result]) -> None:
    name = "case_41_negative_malformed_cohort"
    for bad_handle in ("msisdn:+233201234567", "roamlink-cohort", ""):
        good, detail = _expect_error(
            lambda bad=bad_handle: SubscriberCohort(
                cohort_handle=bad, member_count=3
            ),
            name, RoamLinkReason.COHORT_NOT_OPAQUE,
        )
        if not good:
            results.append(fail(name, detail))
            return
    for bad_count in (0, -1, 100001, "3", True):
        good, detail = _expect_error(
            lambda count=bad_count: SubscriberCohort(
                cohort_handle="roamlink-cohort:v1:gh-accra:0007",
                member_count=count,
            ),
            name, RoamLinkReason.INVALID_INPUT,
        )
        if not good:
            results.append(fail(name, detail))
            return
    results.append(
        ok(name, "malformed cohort handles and counts fail closed")
    )


def case_42_negative_policy_gate_rejects_unsatisfiable(results: List[Result]) -> None:
    name = "case_42_negative_policy_gate_rejects_unsatisfiable"
    from contracts import HardConstraint
    world = build_provider_world(
        provider_a=PROVIDER_A, provider_b=PROVIDER_B,
        validity=("2026-10-01T00:00:00Z", "2026-11-05T00:00:00Z"),
    )
    offers = world.exchange.active_offers(at_instant="2026-10-03T00:00:00Z")
    gate = SimulatedPolicyGate()
    decision = gate.evaluate(
        constraints=(
            HardConstraint.from_dict(
                {"kind": "latency-bound", "params": {"max_ms": 10}}
            ),
        ),
        offers=offers,
    )
    if decision.verdict != "rejected" or decision.eligible_offer_ids:
        results.append(
            fail(name, "verdict %r eligible %r"
                       % (decision.verdict, decision.eligible_offer_ids))
        )
        return
    results.append(
        ok(name, "an unsatisfiable latency bound yields the honest rejected "
                 "verdict (fail closed, no offer admitted)")
    )


def case_43_negative_planner_lock108(results: List[Result]) -> None:
    name = "case_43_negative_planner_lock108"
    flow = RoamLinkVerticalFlow()
    request = flow.cohort_request()
    intent = flow.boundary.request_cohort_connectivity(
        idempotency_key="roamlink-intent-1", request=request,
    )
    weakened = build_weakened_successor_offer(
        flow.world, validity=("2026-10-01T00:00:00Z", "2026-11-05T00:00:00Z"),
        latency_ms=WEAKENED_LATENCY_MS,
    )
    planner = SimulatedExecutionPlanner()
    good, detail = _expect_error(
        lambda: planner.plan(
            contract=flow.store.contract(intent.id), offers=(weakened,),
        ),
        name, RoamLinkReason.CONSTRAINT_VIOLATION,
    )
    if not good:
        results.append(fail(name, detail))
        return
    results.append(
        ok(name, "planning a realization over a constraint-violating offer "
                 "fails closed (LOCK-108: never bind a weakening)")
    )


def case_44_negative_replanner_unrecoverable(results: List[Result]) -> None:
    name = "case_44_negative_replanner_unrecoverable"
    flow = RoamLinkVerticalFlow()
    request = flow.cohort_request()
    intent = flow.boundary.request_cohort_connectivity(
        idempotency_key="roamlink-intent-1", request=request,
    )
    weakened = build_weakened_successor_offer(
        flow.world, validity=("2026-10-01T00:00:00Z", "2026-11-05T00:00:00Z"),
        latency_ms=WEAKENED_LATENCY_MS,
    )
    replanner = SimulatedReplanner()
    change = ProviderChange(
        kind="offer-superseded", instant="2026-10-10T00:00:00Z",
        provider=PROVIDER_A, detail="fixture change",
    )
    contract = flow.store.contract(intent.id)
    # no admissible alternate: the weakened offer alone
    outcome = replanner.absorb(
        contract=contract, change=change,
        alternate_offers=(weakened,),
        failed_segment=SimulatedExecutionPlanner().plan(
            contract=contract,
            offers=flow.world.exchange.active_offers(
                at_instant="2026-10-03T00:00:00Z"
            ),
        ).segments[0],
    )
    if outcome.verdict != "unrecoverable":
        results.append(fail(name, "verdict %r" % outcome.verdict))
        return
    if not outcome.rejected_realizations:
        results.append(fail(name, "the weakening alternate was not recorded"))
        return
    results.append(
        ok(name, "with no admissible alternate the honest verdict is "
                 "unrecoverable (explicit failure or renegotiation -- never "
                 "a silent weakening)")
    )


def case_45_negative_replacement_fail_closed(results: List[Result]) -> None:
    name = "case_45_negative_replacement_fail_closed"
    flow = RoamLinkVerticalFlow()
    request = flow.cohort_request()
    intent = flow.boundary.request_cohort_connectivity(
        idempotency_key="roamlink-intent-1", request=request,
    )
    weakened = build_weakened_successor_offer(
        flow.world, validity=("2026-10-01T00:00:00Z", "2026-11-05T00:00:00Z"),
        latency_ms=WEAKENED_LATENCY_MS,
    )
    contract = flow.store.contract(intent.id)
    planner = SimulatedExecutionPlanner()
    failed = planner.plan(
        contract=contract,
        offers=flow.world.exchange.active_offers(
            at_instant="2026-10-03T00:00:00Z"
        ),
    ).segments[0]
    replanner = SimulatedReplanner()
    good, detail = _expect_error(
        lambda: replanner.replacement_segment(
            contract=contract,
            change=ProviderChange(
                kind="realization-failed", instant="2026-10-10T00:00:00Z",
                provider=PROVIDER_A, detail="fixture failure",
            ),
            offer=weakened,
            failed_segment=failed,
        ),
        name, RoamLinkReason.CONSTRAINT_VIOLATION,
    )
    if not good:
        results.append(fail(name, detail))
        return
    results.append(
        ok(name, "binding a weakening replacement realization fails closed "
                 "(LOCK-108 at the change seam)")
    )


def case_46_negative_vocabulary_enforcement(results: List[Result]) -> None:
    name = "case_46_negative_vocabulary_enforcement"
    evaluator = SimulatedAssuranceEvaluator()
    good, detail = _expect_error(
        lambda: evaluator.evaluate(
            contract_id="sha256:" + "a" * 64, observed="exploded",
        ),
        name, RoamLinkReason.VOCABULARY,
    )
    if not good:
        results.append(fail(name, detail))
        return
    good, detail = _expect_error(
        lambda: ProviderChange(
            kind="provider-merged", instant="2026-10-10T00:00:00Z",
            provider=PROVIDER_A, detail="fixture",
        ),
        name, RoamLinkReason.VOCABULARY,
    )
    if not good:
        results.append(fail(name, detail))
        return
    good, detail = _expect_error(
        lambda: ProviderChange(
            kind="offer-withdrawn", instant="", provider=PROVIDER_A,
            detail="fixture",
        ),
        name, RoamLinkReason.INVALID_INPUT,
    )
    if not good:
        results.append(fail(name, detail))
        return
    # the frozen vocabularies themselves stay frozen
    if OBSERVATION_STATES != ("nominal", "degraded-realization",
                              "violated-realization"):
        results.append(fail(name, "observation vocabulary drifted"))
        return
    results.append(
        ok(name, "unknown observation states, change kinds and malformed "
                 "instants fail closed (frozen vocabularies)")
    )


def case_47_negative_webhook_signature_tamper(results: List[Result]) -> None:
    name = "case_47_negative_webhook_signature_tamper"
    flow = RoamLinkVerticalFlow()
    flow.boundary.register_observation_endpoint(
        idempotency_key="roamlink-endpoint-key",
        url="https://roamlink.example/hooks/adcos",
        event_types=OBSERVED_EVENT_TYPES,
    )
    flow.boundary.request_cohort_connectivity(
        idempotency_key="roamlink-intent-1", request=flow.cohort_request(),
    )
    flow.service.process_due_deliveries()
    if not flow.received_deliveries:
        results.append(fail(name, "no deliveries captured to tamper"))
        return
    headers, payload = flow.received_deliveries[0]
    tampered = dict(headers)
    tampered[webhook_platform.SIGNATURE_HEADER] = "sha256:" + "0" * 64
    good, detail = _expect_error(
        lambda: flow.boundary.receive_observation(tampered, payload),
        name, RoamLinkReason.ATTRIBUTION_INVALID,
    )
    if not good:
        results.append(fail(name, detail))
        return
    results.append(
        ok(name, "a tampered delivery signature never enters the boundary's "
                 "observation log (consumer-side verification)")
    )


def case_48_negative_duplicate_observation(results: List[Result]) -> None:
    name = "case_48_negative_duplicate_observation"
    flow = RoamLinkVerticalFlow()
    flow.boundary.register_observation_endpoint(
        idempotency_key="roamlink-endpoint-key",
        url="https://roamlink.example/hooks/adcos",
        event_types=OBSERVED_EVENT_TYPES,
    )
    flow.boundary.request_cohort_connectivity(
        idempotency_key="roamlink-intent-1", request=flow.cohort_request(),
    )
    flow.service.process_due_deliveries()
    if not flow.received_deliveries:
        results.append(fail(name, "no deliveries captured to replay"))
        return
    headers, payload = flow.received_deliveries[0]
    first = flow.boundary.receive_observation(headers, payload)
    good, detail = _expect_error(
        lambda: flow.boundary.receive_observation(headers, payload),
        name, RoamLinkReason.ATTRIBUTION_INVALID,
    )
    if not good:
        results.append(fail(name, detail))
        return
    if not first.get("event_id"):
        results.append(fail(name, "the first observation has no event id"))
        return
    results.append(
        ok(name, "a replayed observation event is rejected by the "
                 "consumer-side duplicate detector")
    )


# ---------------------------------------------------------------------------
# Structural discipline
# ---------------------------------------------------------------------------


def _module_imports(path: Path) -> List[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.append(node.module.split(".")[0])
    return modules


def case_49_import_discipline_cohort(results: List[Result]) -> None:
    name = "case_49_import_discipline_cohort"
    modules = set(_module_imports(REPO_ROOT / "roamlink" / "cohort.py"))
    stdlib = {"__future__", "hashlib", "re", "json", "dataclasses", "typing"}
    expected = stdlib | {"developerapi"}
    unexpected = modules - expected
    missing = expected - modules
    if unexpected or not {"developerapi"} <= modules:
        results.append(
            fail(name, "imports drifted: unexpected=%r missing developerapi=%r"
                       % (sorted(unexpected), sorted(missing)))
        )
        return
    results.append(
        ok(name, "the application boundary imports ONLY developerapi + "
                 "stdlib: ADCOS composed through the accepted API alone (the "
                 "frozen boundary's architectural acceptance clause)")
    )


def case_50_import_discipline_no_pending_children(results: List[Result]) -> None:
    name = "case_50_import_discipline_no_pending_children"
    problems: List[str] = []
    for path in _FAMILY_FILES:
        modules = set(_module_imports(path))
        leaked = modules & set(_PENDING_CHILD_MODULES)
        if leaked:
            problems.append("%s imports %r" % (path.name, sorted(leaked)))
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "the roamlink package never imports any pending child's "
                 "real domain (M004-M008 mechanics are seams only; the "
                 "children are not claimed delivered)")
    )


def case_51_no_wall_clock_or_randomness(results: List[Result]) -> None:
    name = "case_51_no_wall_clock_or_randomness"
    problems: List[str] = []
    for path in _FAMILY_FILES:
        modules = set(_module_imports(path))
        leaked = modules & set(_FORBIDDEN_RUNTIMES)
        if leaked:
            problems.append("%s imports %r" % (path.name, sorted(leaked)))
        source = path.read_text(encoding="utf-8")
        for token in ("datetime.now", "time.time", "uuid4", "os.urandom"):
            if token in source:
                problems.append("%s references %r" % (path.name, token))
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "no wall clock, randomness, uuid, network or secret "
                 "generation anywhere in the package (LOCK-119: injected "
                 "instants only)")
    )


def case_52_secret_hygiene(results: List[Result]) -> None:
    name = "case_52_secret_hygiene"
    _, result = _golden()
    endpoint_secret = webhook_platform.derive_endpoint_signing_secret(
        ISSUANCE_KEY, RoamLinkVerticalFlow().endpoint_id
    )
    materials = {
        "transcript": json.dumps(result.transcript, sort_keys=True),
        "contract_journal": json.dumps(
            [r.to_dict() for r in result.store.journal()],
            sort_keys=True, default=str,
        ),
        "api_journal": json.dumps(result.service.journal_digest(), sort_keys=True),
    }
    problems: List[str] = []
    for label, material in materials.items():
        if endpoint_secret in material:
            problems.append("the signing secret appears in %s" % label)
        if ISSUANCE_KEY.decode("utf-8", "replace") in material:
            problems.append("the issuance key appears in %s" % label)
        if "roamlink-developer-key" in material:
            problems.append("the application key material appears in %s" % label)
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "no signing secret, issuance key or application key "
                 "material in any journal or transcript (LOCK-119)")
    )


def case_53_py_compile(results: List[Result]) -> None:
    name = "case_53_py_compile"
    problems: List[str] = []
    targets = list(_FAMILY_FILES) + [Path(__file__).resolve()]
    for path in targets:
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as error:
            problems.append("%s does not compile: %s" % (path.name, error))
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "roamlink/ (%d modules) and the battery compile"
                 % len(_FAMILY_FILES))
    )


def _origin_main_available() -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/main"],
        capture_output=True, cwd=str(REPO_ROOT),
    )
    return proc.returncode == 0


def case_54_frozen_spec_intact(results: List[Result]) -> None:
    name = "case_54_frozen_spec_intact"
    frozen = (
        "spec/integration/vertical-proof.md",
        "spec/architecture.md",
        "spec/architecture-lock.md",
        "spec/mission.md",
        "spec/architect/work-items/R7-charter.md",
        "spec/architect/authorizations/R7.yaml",
    )
    if not _origin_main_available():
        results.append(
            ok(name, "skipped (no origin/main ref; CI enforces the frozen "
                     "surfaces)")
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
        ok(name, "the frozen vertical-proof boundary, architecture, locks, "
                 "R7 charter and R7-CORE-001 authorization are "
                 "byte-identical to origin/main")
    )


def _active_authorization_covers(path: str) -> bool:
    """Consult the ACTIVE repository-local authorization (the shared
    authority for the batteries' authorization-aware delta-shape duty)."""
    try:
        from authorization_provenance import covers  # type: ignore
        return covers(path)
    except Exception:  # noqa: BLE001
        return False


def case_55_pr_delta_shape(results: List[Result]) -> None:
    name = "case_55_pr_delta_shape_authorized_scope"
    if not _origin_main_available():
        results.append(
            ok(name, "skipped (no origin/main ref; CI provenance step "
                     "enforces scope)")
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
        if _active_authorization_covers(path):
            continue  # sanctioned by the ACTIVE repository-local authorization
        if not any(
            path == scope or path.startswith(scope) for scope in _AUTHORIZED_PATHS
        ):
            problems.append("delta outside authorized scope: %s" % path)
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
        return
    results.append(
        ok(name, "delta confined to the M011 scope (%d file(s): roamlink/ "
                 "harness + battery + evidence matrix)" % len(delta))
    )


def case_56_evidence_doc_honest(results: List[Result]) -> None:
    name = "case_56_evidence_doc_honest"
    path = REPO_ROOT / "docs" / "M011-evidence.md"
    if not path.exists():
        results.append(fail(name, "docs/M011-evidence.md is missing"))
        return
    text = path.read_text(encoding="utf-8")
    problems: List[str] = []
    if "SOFTWARE" not in text:
        problems.append("the evidence class is not disclosed")
    if "simulation seam" not in text.lower() and "SIMULATION SEAMS" not in text:
        problems.append("the seams are not disclosed in the evidence")
    # an AFFIRMATIVE physical-verification claim fails; a negation
    # ("No SOFTWARE evidence is converted into PHYSICAL PASS") is the
    # required honesty statement, not a claim (window-based so wrapped
    # lines cannot split the negation from the phrase)
    normalized = " ".join(text.split()).lower()
    problems_claim: List[str] = []
    start = 0
    while True:
        index = normalized.find("physical pass", start)
        if index < 0:
            index = normalized.find("physically verified", start)
            if index < 0:
                break
        window = normalized[max(0, index - 100):index]
        if not any(neg in window for neg in (" no ", "never ", "not ")):
            problems_claim.append(normalized[max(0, index - 40):index + 40])
        start = index + 1
    problems.extend(
        "an affirmative physical claim: ...%s..." % snippet
        for snippet in problems_claim[:3]
    )
    if "M011" not in text:
        problems.append("the evidence does not name M011")
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(
        ok(name, "the evidence matrix discloses SOFTWARE class, the "
                 "simulation seams, and no affirmative physical claims")
    )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    results: List[Result] = []
    for case in (
        case_01_composition_map_pinned,
        case_02_evidence_class_software,
        case_03_step1_cohort_request_creates_intent,
        case_04_step1_technology_neutral_request,
        case_05_step1_opaque_beneficiaries,
        case_06_step1_cohort_grammar,
        case_07_step2_offers_exposed,
        case_08_step2_commercial_terms_shape,
        case_09_step2_policy_gate_eligible,
        case_10_step2_service_boundaries,
        case_11_step3_offers_selected_typed_references,
        case_12_step3_contract_activated,
        case_13_step3_policy_decision_recorded_as_data,
        case_14_step4_execution_activation_and_artifacts,
        case_15_step4_delivery_and_assurance_states,
        case_16_step4_execution_status_honest,
        case_17_step4_signed_observations_received,
        case_18_step4_assurance_read,
        case_19_step4_usage_semantics_read,
        case_20_step5_superseded_offer_unresolvable,
        case_21_step5_honest_degraded_status,
        case_22_step5_weakened_alternate_rejected,
        case_23_step5_constraint_fingerprint_preserved,
        case_24_step5_accepted_offers_and_identity_unchanged,
        case_25_step5_replacement_binds_same_contract,
        case_26_step5_recovery_status,
        case_27_step5_change_injection_deterministic,
        case_28_usage_account_key_is_contract_citation,
        case_29_usage_statement_attribution_and_arithmetic,
        case_30_commercial_walk_contract_binding,
        case_31_contract_settled_state,
        case_32_step6_application_state_never_crosses,
        case_33_step6_all_observations_attributed,
        case_34_step6_boundary_surface_is_developer_api_only,
        case_35_determinism_two_fresh_runs,
        case_36_determinism_hash_seeds,
        case_37_transcript_json_round_trip,
        case_38_transcript_tamper_detected,
        case_39_negative_subscriber_identity_rejected,
        case_40_negative_vertical_semantics_rejected,
        case_41_negative_malformed_cohort,
        case_42_negative_policy_gate_rejects_unsatisfiable,
        case_43_negative_planner_lock108,
        case_44_negative_replanner_unrecoverable,
        case_45_negative_replacement_fail_closed,
        case_46_negative_vocabulary_enforcement,
        case_47_negative_webhook_signature_tamper,
        case_48_negative_duplicate_observation,
        case_49_import_discipline_cohort,
        case_50_import_discipline_no_pending_children,
        case_51_no_wall_clock_or_randomness,
        case_52_secret_hygiene,
        case_53_py_compile,
        case_54_frozen_spec_intact,
        case_55_pr_delta_shape,
        case_56_evidence_doc_honest,
    ):
        case(results)
    failures = [result for result in results if not result[1]]
    for entry in results:
        print("[%s] %-52s %s" % ("ok  " if entry[1] else "FAIL", entry[0], entry[2]))
    if failures:
        print("Result: FAIL (%d/%d cases failed)" % (len(failures), len(results)))
        for entry in failures:
            print("  FAILED %s: %s" % (entry[0], entry[2]))
        return 1
    print("Result: PASS (%d/%d cases passed)" % (len(results), len(results)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
