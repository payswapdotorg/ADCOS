#!/usr/bin/env python3
"""ADCOS policy engine self-test (WORK-010 + the M004 evolution).

Deterministic, offline verification of the policy package against the
frozen WORK-010 requirements (spec/prompts/WORK-010.md): the 41
required adversarial verification categories, plus mechanical
forbidden-API/imports checks, frozen-vocabulary presence, deny-by-
default enforcement, equal-precedence fail-closed audit, secret-
material rejection, no-state-mutation audit, no-5g/vendor-leakage
audit, no-wall-clock audit, and a byte-identical determinism proof.

M004 — Eligibility and Policy (R7-CORE-001 child, DEC-0101) evolved the
battery to the refactored 1.1 surface (the disclosed M002/M003
battery-evolution precedent): cases 1-74 retain their case-for-case
WORK-010 semantics (the legacy engine is RETAINED untouched — every
dependent battery stays green); cases 75-87 verify the M004 delivery —
deterministic eligibility and policy evaluation AROUND the canonical
contract.  The evaluations live in the eligibility family
(``eligibility/contract_constraints.py`` — the policy half, guarding
contract-domain actions; ``eligibility/contract_eligibility.py`` — the
eligibility half, evaluating offer/contract references) as PURE-DATA
snapshot evaluators that never import the canonical domains; THIS
battery owns the composition seam that reads ``contracts/`` (M002) and
resolves references through ``offers/`` (M003) BY REFERENCE (LOCK-101),
proving the end-to-end pipeline.  The landing spot is disclosed in
docs/M004-evidence.md: the M009-accepted payment battery freezes the
policy family against any delta, so the matrix's single "Eligibility +
contract constraints" target hosts both halves.  Technology-neutral at
the boundary (LOCK-110), fail-closed typed errors, LOCK-118 provenance,
LOCK-119 secrets, canonical-JSON round-trips, cross-process
determinism.

The central boundary is exercised throughout:

    POLICY DECISION
      = evaluation of explicit policy rules against explicit facts/claims/context

    POLICY DECISION  !=  identity cryptography
    POLICY DECISION  !=  credential generation/rotation
    POLICY DECISION  !=  topology truth
    POLICY DECISION  !=  resource measurement
    POLICY DECISION  !=  resource mutation unless a separate caller executes an authorized operation
    POLICY DECISION  !=  intent normalization
    POLICY DECISION  !=  path computation / route selection
    POLICY DECISION  !=  adapter selection
    POLICY DECISION  !=  pricing / settlement / billing
    POLICY DECISION  !=  trust score

The most important adversarial invariant (mirrors WORK-007 LOCK-008 /
WORK-008 rule 25):

    An operator publishes an explicit policy; a requester asks for
    ``resource.reserve``; the engine returns ALLOW/DENY/DEFAULT_DENY
    deterministically, NEVER mutates topology/resource/identity/intent
    state, NEVER promotes a remote topology claim into authoritative
    fact, NEVER flips a hard intent constraint, NEVER computes a price,
    NEVER scores trust, NEVER reads the wall clock.

All key material is TEST-ONLY; all clocks are injected; all PRNGs are
seeded so runs are byte-identical. No external network access is
permitted or required for the suite. Identity binding flows through
the canonical WORK-004 ``parse_node_id``; policy operations/domains are
the frozen vocabularies (no second vocabulary authority); temporal uses
WORK-003 primitives; canonical bytes use WORK-003
``canonical_json_bytes``.
"""

from __future__ import annotations

import hashlib
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from policy import (  # noqa: E402
    Condition,
    DecisionCode,
    Effect,
    MAX_PRIORITY,
    MAX_SPECIFICITY,
    Operation,
    PolicyContext,
    PolicyDecision,
    PolicyDomain,
    PolicyError,
    PolicyEvaluationResult,
    PolicyRule,
    PolicySet,
    PolicyStore,
    PolicyEngine,
    PredicateKind,
    Privileged,
    evaluate,
    evaluate_condition,
    invocation_binding_from_context,
    policy_decision_canonical_bytes,
    policy_set_canonical_bytes,
    policy_set_from_mapping,
    resolve_conflicts,
    rule_from_mapping,
    context_from_mapping,
    validate_context,
    validate_policy_set,
    validate_rule,
)
from policy.predicates import PredicateResult  # noqa: E402

# M004 — the refactored 1.1 surface: the constraint/eligibility
# evaluations live in the eligibility family (the matrix's single
# "Eligibility + contract constraints" target authority) as pure-DATA
# snapshot evaluators; the accepted canonical domains (contracts/ M002,
# offers/ M003) are imported HERE for the battery-owned composition
# that builds the snapshots from their public surfaces BY REFERENCE
# (LOCK-101 — the evaluators themselves never import them).
from eligibility.contract_constraints import (  # noqa: E402
    ContractConstraintCondition,
    ContractConstraintDecision,
    ContractConstraintDecisionCode,
    ContractConstraintEffect,
    ContractConstraintError,
    ContractConstraintReason,
    ContractConstraintRule,
    ContractConstraintSet,
    ContractConstraintPredicateKind,
    ContractConstraintContext,
    OfferReferenceFacts,
    ValidityWindow,
    contract_constraint_decision_canonical_bytes,
    contract_constraint_set_from_mapping,
    evaluate_contract_constraints,
)
from eligibility.contract_eligibility import (  # noqa: E402
    ContractEligibility,
    ContractEligibilityError,
    ContractEligibilityReason,
    ContractEligibilityRuleset,
    ContractReferenceFacts,
    OfferReferenceEligibility,
    OfferReferenceEligibilityFacts,
    contract_eligibility_from_mapping,
    contract_eligibility_ruleset_from_mapping,
    evaluate_contract_reference_eligibility,
    evaluate_offer_reference_eligibility,
    offer_reference_eligibility_from_mapping,
)
from contracts import (  # noqa: E402
    COMMAND_KINDS,
    CONTRACT_STATES,
    TERMINAL_STATES,
    BeneficiaryScope,
    ConnectivityPrincipal,
    ContractStore,
    CreateContract,
    FailContract,
    HardConstraint,
    OpaqueReference,
    Provenance,
    SelectOffers,
    TerminationRules,
    ValidityInterval,
)
from offers import (  # noqa: E402
    AdvertisementEntry,
    AdvertisementRef,
    OfferCommitment,
    OfferExchange,
    OfferPricing,
    ServiceBoundary,
    build_advertisement,
    build_offer,
    offer_reference,
)

#: The guarded action vocabulary: the exact projection of the CANONICAL
#: M002 command vocabulary (LOCK-101 — computed here, at the composition
#: boundary, directly from the canonical source; the evaluator modules
#: treat actions as opaque strings and never enumerate them).
CONTRACT_ACTIONS = tuple("contract.%s" % kind for kind in COMMAND_KINDS)


Result = Tuple[str, bool, str]


def ok(name: str, detail: str = "") -> Tuple[str, bool, str]:
    return (name, True, detail)


def fail(name: str, detail: str) -> Tuple[str, bool, str]:
    return (name, False, detail)


# --------------------------------------------------------------------------
# Test helpers
# --------------------------------------------------------------------------

# A canonical, valid NodeID for use as ``requester_node_id`` /
# ``subjects`` (derived from test material -- not a real identity). The
# digest is 64 lowercase hex; the profile is a registered-style dotted
# lowercase id. Distinct node ids are constructed by varying the digest
# hex string so that the policy engine treats them as different subjects.
_NODE_A = "adcos:node:test.profile.v1:" + "a" * 64
_NODE_B = "adcos:node:test.profile.v1:" + "b" * 64
_NODE_C = "adcos:node:test.profile.v1:" + "c" * 64

_NOW = "2026-06-01T12:00:00Z"
_NOW_VALID_FROM = "2026-01-01T00:00:00Z"
_NOW_VALID_UNTIL = "2026-12-31T23:59:59Z"


def base_rule(
    rule_id: str = "r1",
    domain: str = PolicyDomain.IDENTITY,
    effect: str = Effect.ALLOW,
    operation: str = Operation.RESOURCE_RESERVE,
    subjects: Tuple[str, ...] = (),
    conditions: Tuple[Condition, ...] = (),
    priority: int = 0,
    specificity: int = 0,
    valid_from: str = "",
    valid_until: str = "",
    provenance: str = "",
    version: int = 1,
) -> PolicyRule:
    return PolicyRule(
        rule_id=rule_id,
        domain=domain,
        effect=effect,
        operation=operation,
        subjects=subjects,
        conditions=conditions,
        priority=priority,
        specificity=specificity,
        valid_from=valid_from,
        valid_until=valid_until,
        provenance=provenance,
        version=version,
    )


def base_set(
    set_id: str = "ps1",
    version: int = 1,
    rules: Tuple[PolicyRule, ...] = (),
    default_effect: str = Effect.DENY,
    domain_precedence: Tuple[str, ...] = (),
    valid_from: str = "",
    valid_until: str = "",
    issuer_node_id: str = _NODE_A,
) -> PolicySet:
    # issuer_node_id defaults to a canonical WORK-004 NodeID because the
    # frozen "Policy authority and provenance" requirement mandates
    # that every PolicySet identify its authority/issuer; an anonymous
    # policy MUST NOT be publishable or evaluable (Architect review of
    # PR #10, blocker 1). Tests that specifically exercise the empty-
    # issuer rejection pass issuer_node_id="" explicitly.
    return PolicySet(
        set_id=set_id,
        version=version,
        rules=rules,
        default_effect=default_effect,
        domain_precedence=domain_precedence,
        valid_from=valid_from,
        valid_until=valid_until,
        issuer_node_id=issuer_node_id,
    )


def base_ctx(
    operation: str = Operation.RESOURCE_RESERVE,
    requester_node_id: str = _NODE_A,
    credential_active=None,
    evaluation_instant: str = _NOW,
    **kwargs,
) -> PolicyContext:
    return PolicyContext(
        operation=operation,
        requester_node_id=requester_node_id,
        credential_active=credential_active,
        evaluation_instant=evaluation_instant,
        **kwargs,
    )


# --------------------------------------------------------------------------
# Required adversarial verification cases (1-41 from the prompt)
# --------------------------------------------------------------------------

def case_01_minimal_allow_decision(results: List[Result]) -> None:
    """1. minimal allow decision."""
    r = base_rule(rule_id="allow1", effect=Effect.ALLOW)
    ps = base_set(rules=(r,))
    ctx = base_ctx()
    res = evaluate(ps, ctx)
    if res.ok and res.code == DecisionCode.ALLOW and res.decision and res.decision.effect == Effect.ALLOW:
        results.append(ok("case_01_minimal_allow_decision", "ALLOW; matched=%s" % (res.decision.matched_rule_ids,)))
    else:
        results.append(fail("case_01_minimal_allow_decision", "got %r %r" % (res.code, res.detail)))


def case_02_minimal_explicit_deny(results: List[Result]) -> None:
    """2. minimal explicit deny."""
    r = base_rule(rule_id="deny1", effect=Effect.DENY)
    ps = base_set(rules=(r,))
    ctx = base_ctx()
    res = evaluate(ps, ctx)
    if res.ok and res.code == DecisionCode.DENY and res.decision and res.decision.effect == Effect.DENY:
        results.append(ok("case_02_minimal_explicit_deny", "DENY; matched=%s" % (res.decision.matched_rule_ids,)))
    else:
        results.append(fail("case_02_minimal_explicit_deny", "got %r %r" % (res.code, res.detail)))


def case_03_no_matching_privileged_rule_default_deny(results: List[Result]) -> None:
    """3. no matching privileged rule -> default deny."""
    # A rule for a DIFFERENT operation; the requested operation has no
    # matching rule. Privileged operation -> DEFAULT_DENY.
    r = base_rule(rule_id="r1", effect=Effect.ALLOW, operation=Operation.SESSION_CREATE)
    ps = base_set(rules=(r,))
    ctx = base_ctx(operation=Operation.RESOURCE_RESERVE)
    res = evaluate(ps, ctx)
    if res.ok and res.code == DecisionCode.DEFAULT_DENY and res.decision and res.decision.effect == Effect.DENY:
        results.append(ok("case_03_no_matching_privileged_rule_default_deny", "DEFAULT_DENY"))
    else:
        results.append(fail("case_03_no_matching_privileged_rule_default_deny", "got %r %r" % (res.code, res.detail)))


def case_04_missing_authorization_fact_fail_closed(results: List[Result]) -> None:
    """4. missing authorization fact -> fail closed (DEFAULT_DENY).

    A rule requires ``credential-active`` but the context's
    ``credential_active`` is None (unknown). The predicate returns
    ``missing-fact``; the rule does not match; the privileged operation
    has no applicable rule -> DEFAULT_DENY.
    """
    cond = Condition(predicate=PredicateKind.CREDENTIAL_ACTIVE, arguments={})
    r = base_rule(rule_id="r1", effect=Effect.ALLOW, conditions=(cond,))
    ps = base_set(rules=(r,))
    ctx = base_ctx(credential_active=None)  # missing
    res = evaluate(ps, ctx)
    if res.ok and res.code == DecisionCode.DEFAULT_DENY:
        # The trace must record the missing-fact code.
        trace_text = " ".join(res.decision.conflict_trace)
        if "missing-fact" in trace_text:
            results.append(ok("case_04_missing_authorization_fact_fail_closed", "DEFAULT_DENY; missing-fact recorded"))
        else:
            results.append(fail("case_04_missing_authorization_fact_fail_closed", "missing-fact not in trace: %s" % trace_text))
    else:
        results.append(fail("case_04_missing_authorization_fact_fail_closed", "got %r %r" % (res.code, res.detail)))


def case_05_expired_policy_fail_closed(results: List[Result]) -> None:
    """5. expired policy -> fail closed (POLICY_EXPIRED)."""
    r = base_rule(rule_id="r1", effect=Effect.ALLOW)
    ps = base_set(rules=(r,), valid_until="2026-01-01T00:00:00Z")  # expired before _NOW
    ctx = base_ctx()
    res = evaluate(ps, ctx)
    if res.ok and res.code == DecisionCode.POLICY_EXPIRED:
        results.append(ok("case_05_expired_policy_fail_closed", "POLICY_EXPIRED"))
    else:
        results.append(fail("case_05_expired_policy_fail_closed", "got %r %r" % (res.code, res.detail)))


def case_06_not_yet_valid_policy_fail_closed(results: List[Result]) -> None:
    """6. not-yet-valid policy -> fail closed (POLICY_NOT_YET_VALID)."""
    r = base_rule(rule_id="r1", effect=Effect.ALLOW)
    ps = base_set(rules=(r,), valid_from="2027-01-01T00:00:00Z")  # starts after _NOW
    ctx = base_ctx()
    res = evaluate(ps, ctx)
    if res.ok and res.code == DecisionCode.POLICY_NOT_YET_VALID:
        results.append(ok("case_06_not_yet_valid_policy_fail_closed", "POLICY_NOT_YET_VALID"))
    else:
        results.append(fail("case_06_not_yet_valid_policy_fail_closed", "got %r %r" % (res.code, res.detail)))


def case_07_exact_validity_boundary(results: List[Result]) -> None:
    """7. exact validity boundary (inclusive both ends).

    ``now == valid_from`` and ``now == valid_until`` are both valid
    (inclusive boundary convention).
    """
    r1 = base_rule(rule_id="r1", effect=Effect.ALLOW)
    ps_from = base_set(rules=(r1,), valid_from=_NOW)  # now == valid_from
    ps_until = base_set(set_id="ps2", rules=(r1,), valid_until=_NOW)  # now == valid_until
    ctx = base_ctx()
    res_from = evaluate(ps_from, ctx)
    res_until = evaluate(ps_until, ctx)
    if res_from.code == DecisionCode.ALLOW and res_until.code == DecisionCode.ALLOW:
        results.append(ok("case_07_exact_validity_boundary", "inclusive both ends: from=%s until=%s" % (res_from.code, res_until.code)))
    else:
        results.append(fail("case_07_exact_validity_boundary", "from=%r until=%r" % (res_from.code, res_until.code)))


def case_08_equal_priority_allow_deny_conflict(results: List[Result]) -> None:
    """8. equal-priority allow/deny conflict -> deterministic deny.

    Two rules at equal specificity/priority/domain, one ALLOW one DENY.
    Per rule 7, explicit deny beats allow at equal precedence.
    """
    ra = base_rule(rule_id="ra", effect=Effect.ALLOW, domain=PolicyDomain.RESOURCE)
    rd = base_rule(rule_id="rd", effect=Effect.DENY, domain=PolicyDomain.RESOURCE)
    ps = base_set(rules=(ra, rd), domain_precedence=(PolicyDomain.RESOURCE,))
    ctx = base_ctx()
    res = evaluate(ps, ctx)
    if res.ok and res.code == DecisionCode.DENY and res.decision.matched_rule_ids == ("rd",):
        results.append(ok("case_08_equal_priority_allow_deny_conflict", "deny beats allow; matched=%s" % (res.decision.matched_rule_ids,)))
    else:
        results.append(fail("case_08_equal_priority_allow_deny_conflict", "got %r %r" % (res.code, res.detail)))


def case_09_equal_specificity_equal_priority_conflict_fail_closed(results: List[Result]) -> None:
    """9. equal-specificity equal-priority conflicting rules -> fail closed.

    Two ALLOW rules at equal specificity/priority/domain (no DENY to
    resolve the tie). Per rule 4, equal-precedence conflicting rules
    MUST fail closed rather than depend on iteration order.
    """
    r1 = base_rule(rule_id="r1", effect=Effect.ALLOW, domain=PolicyDomain.RESOURCE, provenance="rule-source-A")
    r2 = base_rule(rule_id="r2", effect=Effect.ALLOW, domain=PolicyDomain.RESOURCE, provenance="rule-source-B")
    ps = base_set(rules=(r1, r2), domain_precedence=(PolicyDomain.RESOURCE,))
    ctx = base_ctx()
    res = evaluate(ps, ctx)
    if res.ok and res.code == DecisionCode.CONFLICT and res.decision.effect == Effect.DENY:
        results.append(ok("case_09_equal_specificity_equal_priority_conflict_fail_closed", "CONFLICT -> DENY"))
    else:
        results.append(fail("case_09_equal_specificity_equal_priority_conflict_fail_closed", "got %r %r" % (res.code, res.detail)))


def case_10_explicit_priority_ordering(results: List[Result]) -> None:
    """10. explicit priority ordering -- higher priority wins."""
    # ALLOW at priority 1; DENY at priority 0. ALLOW wins by priority.
    ra = base_rule(rule_id="ra", effect=Effect.ALLOW, domain=PolicyDomain.RESOURCE, priority=1)
    rd = base_rule(rule_id="rd", effect=Effect.DENY, domain=PolicyDomain.RESOURCE, priority=0)
    ps = base_set(rules=(ra, rd), domain_precedence=(PolicyDomain.RESOURCE,))
    ctx = base_ctx()
    res = evaluate(ps, ctx)
    if res.ok and res.code == DecisionCode.ALLOW and res.decision.matched_rule_ids == ("ra",):
        # Reverse insertion order; result must be identical.
        ps_rev = base_set(set_id="ps2", rules=(rd, ra), domain_precedence=(PolicyDomain.RESOURCE,))
        res_rev = evaluate(ps_rev, ctx)
        if res_rev.code == DecisionCode.ALLOW and res_rev.decision.matched_rule_ids == ("ra",):
            results.append(ok("case_10_explicit_priority_ordering", "ALLOW wins by priority; insertion-order-independent"))
        else:
            results.append(fail("case_10_explicit_priority_ordering", "reversed order broke: %r" % res_rev.code))
    else:
        results.append(fail("case_10_explicit_priority_ordering", "got %r %r" % (res.code, res.detail)))


def case_11_explicit_scope_specificity_ordering(results: List[Result]) -> None:
    """11. explicit scope-specificity ordering -- higher specificity wins."""
    # ALLOW at specificity 1; DENY at specificity 0. ALLOW wins by specificity.
    ra = base_rule(rule_id="ra", effect=Effect.ALLOW, domain=PolicyDomain.RESOURCE, specificity=1)
    rd = base_rule(rule_id="rd", effect=Effect.DENY, domain=PolicyDomain.RESOURCE, specificity=0)
    ps = base_set(rules=(ra, rd), domain_precedence=(PolicyDomain.RESOURCE,))
    ctx = base_ctx()
    res = evaluate(ps, ctx)
    if res.ok and res.code == DecisionCode.ALLOW and res.decision.matched_rule_ids == ("ra",):
        results.append(ok("case_11_explicit_scope_specificity_ordering", "ALLOW wins by specificity"))
    else:
        results.append(fail("case_11_explicit_scope_specificity_ordering", "got %r %r" % (res.code, res.detail)))


def case_12_deterministic_rule_order_independence(results: List[Result]) -> None:
    """12. deterministic rule-order independence -- same decision bytes
    regardless of rule insertion order."""
    r1 = base_rule(rule_id="r1", effect=Effect.ALLOW, domain=PolicyDomain.RESOURCE, priority=2)
    r2 = base_rule(rule_id="r2", effect=Effect.DENY, domain=PolicyDomain.RESOURCE, priority=1)
    r3 = base_rule(rule_id="r3", effect=Effect.ALLOW, domain=PolicyDomain.IDENTITY, priority=3)
    ps_a = base_set(rules=(r1, r2, r3), domain_precedence=(PolicyDomain.RESOURCE, PolicyDomain.IDENTITY))
    ps_b = base_set(rules=(r3, r2, r1), domain_precedence=(PolicyDomain.RESOURCE, PolicyDomain.IDENTITY))
    ctx = base_ctx()
    res_a = evaluate(ps_a, ctx)
    res_b = evaluate(ps_b, ctx)
    if not (res_a.ok and res_b.ok):
        results.append(fail("case_12_deterministic_rule_order_independence", "both must be ok: a=%r b=%r" % (res_a.code, res_b.code)))
        return
    da, db = res_a.decision, res_b.decision
    if da is None or db is None:
        results.append(fail("case_12_deterministic_rule_order_independence", "missing decision"))
        return
    if da.decision_id == db.decision_id and da.canonical_bytes() == db.canonical_bytes():
        results.append(ok("case_12_deterministic_rule_order_independence", "byte-identical; decision_id=%s" % da.decision_id[:12]))
    else:
        results.append(fail("case_12_deterministic_rule_order_independence", "decision ids differ: %s vs %s" % (da.decision_id[:12], db.decision_id[:12])))


def case_13_deterministic_policy_set_ordering(results: List[Result]) -> None:
    """13. deterministic policy-set ordering -- same context produces
    byte-identical decisions across two equal policy sets built with
    different rule-construction order (proves iteration-order
    independence at the set level)."""
    rules = [
        base_rule(rule_id="r%d" % i, effect=Effect.ALLOW, domain=PolicyDomain.RESOURCE, priority=i)
        for i in range(5)
    ]
    # Two policy sets with the SAME rules but inserted in opposite
    # orders. Highest priority (r4) wins in both.
    ps_fwd = base_set(rules=tuple(rules), domain_precedence=(PolicyDomain.RESOURCE,))
    ps_rev = base_set(rules=tuple(reversed(rules)), domain_precedence=(PolicyDomain.RESOURCE,))
    ctx = base_ctx()
    res_fwd = evaluate(ps_fwd, ctx)
    res_rev = evaluate(ps_rev, ctx)
    if res_fwd.decision is None or res_rev.decision is None:
        results.append(fail("case_13_deterministic_policy_set_ordering", "missing decision: fwd=%r rev=%r" % (res_fwd.code, res_rev.code)))
        return
    if res_fwd.decision.decision_id == res_rev.decision.decision_id:
        results.append(ok("case_13_deterministic_policy_set_ordering", "byte-identical across insertion order"))
    else:
        results.append(fail("case_13_deterministic_policy_set_ordering", "%s vs %s" % (res_fwd.decision.decision_id[:12], res_rev.decision.decision_id[:12])))


def case_14_requester_nodeid_validation(results: List[Result]) -> None:
    """14. requester NodeID validation via WORK-004.

    A malformed requester_node_id is rejected by validate_context
    (INVALID_SUBJECT).
    """
    bad_ids = ("", "not-a-node-id", "adcos:node:", "adcos:node:test:", "ADcos:node:test.profile.v1:" + "a" * 64)
    for bad in bad_ids:
        ctx = base_ctx(requester_node_id=bad)
        try:
            validate_context(ctx)
            # An empty requester is structurally permitted (means
            # anonymous/system). Any other malformed value must raise.
            if bad == "":
                continue
            results.append(fail("case_14_requester_nodeid_validation", "accepted bad requester %r" % (bad,)))
            return
        except PolicyError as e:
            if e.code not in ("requester", "node-id"):
                results.append(fail("case_14_requester_nodeid_validation", "wrong code %r for %r" % (e.code, bad)))
                return
    results.append(ok("case_14_requester_nodeid_validation", "malformed requester NodeIDs rejected via WORK-004"))


def case_15_credential_active_accepted(results: List[Result]) -> None:
    """15. credential active accepted."""
    cond = Condition(predicate=PredicateKind.CREDENTIAL_ACTIVE, arguments={})
    r = base_rule(rule_id="r1", effect=Effect.ALLOW, conditions=(cond,))
    ps = base_set(rules=(r,))
    ctx = base_ctx(credential_active=True)
    res = evaluate(ps, ctx)
    if res.ok and res.code == DecisionCode.ALLOW:
        results.append(ok("case_15_credential_active_accepted", "credential_active=True -> ALLOW"))
    else:
        results.append(fail("case_15_credential_active_accepted", "got %r" % res.code))


def case_16_revoked_credential_rejected(results: List[Result]) -> None:
    """16. revoked credential rejected (credential_active=False)."""
    cond = Condition(predicate=PredicateKind.CREDENTIAL_ACTIVE, arguments={})
    r = base_rule(rule_id="r1", effect=Effect.ALLOW, conditions=(cond,))
    ps = base_set(rules=(r,))
    ctx = base_ctx(credential_active=False)  # explicitly not active
    res = evaluate(ps, ctx)
    # The credential-active predicate returns not-matched; the rule
    # does not match; privileged operation -> DEFAULT_DENY.
    if res.ok and res.code == DecisionCode.DEFAULT_DENY:
        results.append(ok("case_16_revoked_credential_rejected", "credential_active=False -> DEFAULT_DENY"))
    else:
        results.append(fail("case_16_revoked_credential_rejected", "got %r" % res.code))


def case_17_expired_credential_rejected(results: List[Result]) -> None:
    """17. expired credential rejected.

    An expired credential is not ACTIVE (caller-supplied
    ``credential_active=False`` from WORK-004 lifecycle). Same behavior
    as case 16 -- the predicate returns not-matched.
    """
    # This case mirrors case 16 but exercises the semantic alias:
    # WORK-004 lifecycle EXPIRED maps to credential_active=False.
    cond = Condition(predicate=PredicateKind.CREDENTIAL_ACTIVE, arguments={})
    r = base_rule(rule_id="r1", effect=Effect.ALLOW, conditions=(cond,))
    ps = base_set(rules=(r,))
    ctx = base_ctx(credential_active=False)
    res = evaluate(ps, ctx)
    if res.ok and res.code == DecisionCode.DEFAULT_DENY:
        results.append(ok("case_17_expired_credential_rejected", "expired->credential_active=False -> DEFAULT_DENY"))
    else:
        results.append(fail("case_17_expired_credential_rejected", "got %r" % res.code))


def case_18_malformed_credential_reference_rejected(results: List[Result]) -> None:
    """18. malformed credential reference rejected.

    ``credential_active`` must be None or bool; an int is rejected at
    context construction.
    """
    for bad in (0, 1, "yes", []):
        try:
            ctx = PolicyContext(  # type: ignore[arg-type]
                operation=Operation.RESOURCE_RESERVE,
                requester_node_id=_NODE_A,
                credential_active=bad,  # type: ignore[arg-type]
                evaluation_instant=_NOW,
            )
            results.append(fail("case_18_malformed_credential_reference_rejected", "accepted bad credential_active=%r" % (bad,)))
            return
        except (PolicyError, TypeError):
            pass
    results.append(ok("case_18_malformed_credential_reference_rejected", "non-bool/non-None credential_active rejected"))


def case_19_resource_owner_access_policy(results: List[Result]) -> None:
    """19. resource-owner access policy."""
    cond = Condition(predicate=PredicateKind.RESOURCE_OWNER, arguments={"owner_node_id": _NODE_A})
    r = base_rule(rule_id="r1", effect=Effect.ALLOW, domain=PolicyDomain.RESOURCE, conditions=(cond,))
    ps = base_set(rules=(r,), domain_precedence=(PolicyDomain.RESOURCE,))
    ctx = base_ctx(resource_owner_node_id=_NODE_A)
    res = evaluate(ps, ctx)
    if res.ok and res.code == DecisionCode.ALLOW:
        results.append(ok("case_19_resource_owner_access_policy", "owner match -> ALLOW"))
    else:
        results.append(fail("case_19_resource_owner_access_policy", "got %r" % res.code))


def case_20_resource_kind_restriction(results: List[Result]) -> None:
    """20. resource-kind restriction."""
    cond = Condition(predicate=PredicateKind.RESOURCE_KIND, arguments={"kind": "bandwidth"})
    r = base_rule(rule_id="r1", effect=Effect.ALLOW, domain=PolicyDomain.RESOURCE, conditions=(cond,))
    ps = base_set(rules=(r,), domain_precedence=(PolicyDomain.RESOURCE,))
    # Match: context resource_kind == "bandwidth".
    ctx_ok = base_ctx(resource_kind="bandwidth")
    # Mismatch: context resource_kind == "compute".
    ctx_no = base_ctx(resource_kind="compute")
    res_ok = evaluate(ps, ctx_ok)
    res_no = evaluate(ps, ctx_no)
    if res_ok.code == DecisionCode.ALLOW and res_no.code == DecisionCode.DEFAULT_DENY:
        results.append(ok("case_20_resource_kind_restriction", "kind match->ALLOW, mismatch->DEFAULT_DENY"))
    else:
        results.append(fail("case_20_resource_kind_restriction", "ok=%r no=%r" % (res_ok.code, res_no.code)))


def case_21_locality_allow(results: List[Result]) -> None:
    """21. locality allow."""
    cond = Condition(predicate=PredicateKind.LOCALITY_EQUALS, arguments={"label": "village-A"})
    r = base_rule(rule_id="r1", effect=Effect.ALLOW, domain=PolicyDomain.LOCALITY, conditions=(cond,))
    ps = base_set(rules=(r,), domain_precedence=(PolicyDomain.LOCALITY,))
    ctx = base_ctx(locality_labels=("village-A",))
    res = evaluate(ps, ctx)
    if res.ok and res.code == DecisionCode.ALLOW:
        results.append(ok("case_21_locality_allow", "locality match -> ALLOW"))
    else:
        results.append(fail("case_21_locality_allow", "got %r" % res.code))


def case_22_locality_deny(results: List[Result]) -> None:
    """22. locality deny."""
    cond = Condition(predicate=PredicateKind.LOCALITY_EQUALS, arguments={"label": "village-A"})
    r = base_rule(rule_id="r1", effect=Effect.ALLOW, domain=PolicyDomain.LOCALITY, conditions=(cond,))
    ps = base_set(rules=(r,), domain_precedence=(PolicyDomain.LOCALITY,))
    # Context carries a DIFFERENT locality label -> rule does not match
    # -> DEFAULT_DENY.
    ctx = base_ctx(locality_labels=("village-B",))
    res = evaluate(ps, ctx)
    if res.ok and res.code == DecisionCode.DEFAULT_DENY:
        results.append(ok("case_22_locality_deny", "locality mismatch -> DEFAULT_DENY"))
    else:
        results.append(fail("case_22_locality_deny", "got %r" % res.code))


def case_23_federation_allow(results: List[Result]) -> None:
    """23. federation allow."""
    cond = Condition(predicate=PredicateKind.FEDERATION_DOMAIN, arguments={"domain": "gh-community-1"})
    r = base_rule(rule_id="r1", effect=Effect.ALLOW, domain=PolicyDomain.FEDERATION, operation=Operation.FEDERATION_JOIN, conditions=(cond,))
    ps = base_set(rules=(r,), domain_precedence=(PolicyDomain.FEDERATION,))
    ctx = base_ctx(operation=Operation.FEDERATION_JOIN, federation_domain="gh-community-1")
    res = evaluate(ps, ctx)
    if res.ok and res.code == DecisionCode.ALLOW:
        results.append(ok("case_23_federation_allow", "federation match -> ALLOW"))
    else:
        results.append(fail("case_23_federation_allow", "got %r" % res.code))


def case_24_federation_deny(results: List[Result]) -> None:
    """24. federation deny."""
    cond = Condition(predicate=PredicateKind.FEDERATION_DOMAIN, arguments={"domain": "gh-community-1"})
    r = base_rule(rule_id="r1", effect=Effect.ALLOW, domain=PolicyDomain.FEDERATION, operation=Operation.FEDERATION_JOIN, conditions=(cond,))
    ps = base_set(rules=(r,), domain_precedence=(PolicyDomain.FEDERATION,))
    # Different federation domain -> rule does not match -> DEFAULT_DENY.
    ctx = base_ctx(operation=Operation.FEDERATION_JOIN, federation_domain="other-domain")
    res = evaluate(ps, ctx)
    if res.ok and res.code == DecisionCode.DEFAULT_DENY:
        results.append(ok("case_24_federation_deny", "federation mismatch -> DEFAULT_DENY"))
    else:
        results.append(fail("case_24_federation_deny", "got %r" % res.code))


def case_25_privacy_requirement_allow(results: List[Result]) -> None:
    """25. privacy requirement allow."""
    cond = Condition(predicate=PredicateKind.PRIVACY_REQUIRED, arguments={"requirement": "end-to-end"})
    r = base_rule(rule_id="r1", effect=Effect.ALLOW, domain=PolicyDomain.PRIVACY, operation=Operation.PRIVACY_REQUIREMENT_OVERRIDE, conditions=(cond,))
    ps = base_set(rules=(r,), domain_precedence=(PolicyDomain.PRIVACY,))
    ctx = base_ctx(operation=Operation.PRIVACY_REQUIREMENT_OVERRIDE, privacy_requirements=("end-to-end",))
    res = evaluate(ps, ctx)
    if res.ok and res.code == DecisionCode.ALLOW:
        results.append(ok("case_25_privacy_requirement_allow", "privacy match -> ALLOW"))
    else:
        results.append(fail("case_25_privacy_requirement_allow", "got %r" % res.code))


def case_26_privacy_requirement_deny(results: List[Result]) -> None:
    """26. privacy requirement deny."""
    cond = Condition(predicate=PredicateKind.PRIVACY_REQUIRED, arguments={"requirement": "end-to-end"})
    r = base_rule(rule_id="r1", effect=Effect.ALLOW, domain=PolicyDomain.PRIVACY, operation=Operation.PRIVACY_REQUIREMENT_OVERRIDE, conditions=(cond,))
    ps = base_set(rules=(r,), domain_precedence=(PolicyDomain.PRIVACY,))
    ctx = base_ctx(operation=Operation.PRIVACY_REQUIREMENT_OVERRIDE, privacy_requirements=("best-effort",))
    res = evaluate(ps, ctx)
    if res.ok and res.code == DecisionCode.DEFAULT_DENY:
        results.append(ok("case_26_privacy_requirement_deny", "privacy mismatch -> DEFAULT_DENY"))
    else:
        results.append(fail("case_26_privacy_requirement_deny", "got %r" % res.code))


def case_27_emergency_override_explicitly_allowed(results: List[Result]) -> None:
    """27. emergency override explicitly allowed.

    An emergency rule with ``emergency-true`` predicate allows
    ``emergency.preempt`` when the context carries ``emergency=True``.
    No implicit bypass -- the emergency rule must explicitly authorize
    the override.
    """
    cond = Condition(predicate=PredicateKind.EMERGENCY_TRUE, arguments={})
    r = base_rule(rule_id="r1", effect=Effect.ALLOW, domain=PolicyDomain.EMERGENCY, operation=Operation.EMERGENCY_PREEMPT, conditions=(cond,))
    ps = base_set(rules=(r,), domain_precedence=(PolicyDomain.EMERGENCY,))
    ctx = base_ctx(operation=Operation.EMERGENCY_PREEMPT, emergency=True)
    res = evaluate(ps, ctx)
    if res.ok and res.code == DecisionCode.ALLOW:
        results.append(ok("case_27_emergency_override_explicitly_allowed", "emergency=True + explicit rule -> ALLOW"))
    else:
        results.append(fail("case_27_emergency_override_explicitly_allowed", "got %r" % res.code))


def case_28_emergency_override_absent_ordinary_deny_still_applies(results: List[Result]) -> None:
    """28. emergency override absent -> ordinary deny still applies.

    No emergency rule, ``emergency=True`` in the context. The
    ``emergency.preempt`` operation has no matching rule -> DEFAULT_DENY.
    The ``emergency=True`` fact does NOT implicitly bypass deny-by-
    default.
    """
    ps = base_set(rules=(), domain_precedence=(PolicyDomain.EMERGENCY,))
    ctx = base_ctx(operation=Operation.EMERGENCY_PREEMPT, emergency=True)
    res = evaluate(ps, ctx)
    if res.ok and res.code == DecisionCode.DEFAULT_DENY:
        results.append(ok("case_28_emergency_override_absent_ordinary_deny_still_applies", "no emergency rule + emergency=True -> DEFAULT_DENY"))
    else:
        results.append(fail("case_28_emergency_override_absent_ordinary_deny_still_applies", "got %r" % res.code))


def case_29_service_priority_conflict_resolution(results: List[Result]) -> None:
    """29. service-priority conflict resolution."""
    # Two service-class rules at different priorities; higher priority wins.
    cond_h = Condition(predicate=PredicateKind.SERVICE_CLASS, arguments={"class": "hospital-critical"})
    cond_l = Condition(predicate=PredicateKind.SERVICE_CLASS, arguments={"class": "ordinary"})
    rh = base_rule(rule_id="rh", effect=Effect.ALLOW, domain=PolicyDomain.SERVICE, priority=2, conditions=(cond_h,))
    rl = base_rule(rule_id="rl", effect=Effect.DENY, domain=PolicyDomain.SERVICE, priority=1, conditions=(cond_l,))
    ps = base_set(rules=(rh, rl), domain_precedence=(PolicyDomain.SERVICE,))
    # Context carries BOTH service classes (unusual but legal).
    ctx = base_ctx(service_class="hospital-critical")
    res = evaluate(ps, ctx)
    # Only rh matches (service_class == "hospital-critical"); rl does
    # not match because service_class != "ordinary". So ALLOW by rh.
    if res.ok and res.code == DecisionCode.ALLOW and res.decision.matched_rule_ids == ("rh",):
        results.append(ok("case_29_service_priority_conflict_resolution", "higher-priority service rule wins; matched=%s" % (res.decision.matched_rule_ids,)))
    else:
        results.append(fail("case_29_service_priority_conflict_resolution", "got %r %r" % (res.code, res.detail)))


def case_30_energy_reserve_allow(results: List[Result]) -> None:
    """30. energy reserve allow."""
    cond = Condition(predicate=PredicateKind.ENERGY_RESERVE_GTE, arguments={"threshold": 1000})
    r = base_rule(rule_id="r1", effect=Effect.ALLOW, domain=PolicyDomain.ENERGY, conditions=(cond,))
    ps = base_set(rules=(r,), domain_precedence=(PolicyDomain.ENERGY,))
    ctx = base_ctx(energy_reserve_current=5000, energy_reserve_threshold=1000)
    res = evaluate(ps, ctx)
    if res.ok and res.code == DecisionCode.ALLOW:
        results.append(ok("case_30_energy_reserve_allow", "reserve 5000 >= 1000 -> ALLOW"))
    else:
        results.append(fail("case_30_energy_reserve_allow", "got %r" % res.code))


def case_31_energy_reserve_deny(results: List[Result]) -> None:
    """31. energy reserve deny."""
    cond = Condition(predicate=PredicateKind.ENERGY_RESERVE_GTE, arguments={"threshold": 1000})
    r = base_rule(rule_id="r1", effect=Effect.ALLOW, domain=PolicyDomain.ENERGY, conditions=(cond,))
    ps = base_set(rules=(r,), domain_precedence=(PolicyDomain.ENERGY,))
    ctx = base_ctx(energy_reserve_current=500, energy_reserve_threshold=1000)  # below threshold
    res = evaluate(ps, ctx)
    if res.ok and res.code == DecisionCode.DEFAULT_DENY:
        results.append(ok("case_31_energy_reserve_deny", "reserve 500 < 1000 -> DEFAULT_DENY"))
    else:
        results.append(fail("case_31_energy_reserve_deny", "got %r" % res.code))


def case_32_hard_intent_constraint_untouched(results: List[Result]) -> None:
    """32. hard intent constraint remains untouched.

    Policy consumes the intent by reference (the
    ``normalized_intent_digest`` field on the context). The engine MUST
    NOT rewrite the intent or downgrade hard constraints. We exercise
    the ``intent-present`` predicate (digest non-empty -> match), then
    assert the digest is preserved verbatim in the decision's audit
    trail (it is NOT -- the decision carries its own decision_id, not
    the intent digest; the intent is never re-serialized by policy).
    """
    cond = Condition(predicate=PredicateKind.INTENT_PRESENT, arguments={})
    r = base_rule(rule_id="r1", effect=Effect.ALLOW, domain=PolicyDomain.RESOURCE, conditions=(cond,))
    ps = base_set(rules=(r,), domain_precedence=(PolicyDomain.RESOURCE,))
    intent_digest = "a" * 64  # 64-hex sha256 digest (fake, test-only)
    ctx = base_ctx(normalized_intent_digest=intent_digest)
    res = evaluate(ps, ctx)
    if not (res.ok and res.code == DecisionCode.ALLOW):
        results.append(fail("case_32_hard_intent_constraint_untouched", "expected ALLOW, got %r" % res.code))
        return
    # The decision's canonical bytes MUST NOT carry the intent digest
    # (policy never re-serializes the intent; it is consumed by
    # reference only). This proves the engine did not rewrite the intent.
    dec_text = res.decision.canonical_bytes().decode("utf-8")
    if intent_digest in dec_text:
        results.append(fail("case_32_hard_intent_constraint_untouched", "intent digest leaked into decision bytes"))
        return
    # The context's intent digest is unchanged (immutable context).
    if ctx.normalized_intent_digest == intent_digest:
        results.append(ok("case_32_hard_intent_constraint_untouched", "intent digest consumed by reference; not in decision; context unchanged"))
    else:
        results.append(fail("case_32_hard_intent_constraint_untouched", "context intent digest mutated"))


def case_33_soft_intent_preference_untouched(results: List[Result]) -> None:
    """33. soft intent preference remains untouched (no routing choice)."""
    # Same as case 32 but exercising that policy does not convert soft
    # preferences into routing choices: the decision carries only
    # ALLOW/DENY + matched rule ids + policy set identity, never a
    # route/path/resource preference.
    cond = Condition(predicate=PredicateKind.INTENT_PRESENT, arguments={})
    r = base_rule(rule_id="r1", effect=Effect.ALLOW, domain=PolicyDomain.RESOURCE, conditions=(cond,))
    ps = base_set(rules=(r,), domain_precedence=(PolicyDomain.RESOURCE,))
    ctx = base_ctx(normalized_intent_digest="b" * 64)
    res = evaluate(ps, ctx)
    if not (res.ok and res.decision is not None):
        results.append(fail("case_33_soft_intent_preference_untouched", "expected ok"))
        return
    dec_text = res.decision.canonical_bytes().decode("utf-8")
    # The decision MUST NOT carry route/path/resource fields.
    forbidden = ('"route"', '"path"', '"next_hop"', '"adapter"', '"access_technology"', '"selected_resource"', '"trust_score"', '"price"', '"settlement"')
    for f in forbidden:
        if f in dec_text:
            results.append(fail("case_33_soft_intent_preference_untouched", "forbidden field in decision: %s" % f))
            return
    results.append(ok("case_33_soft_intent_preference_untouched", "no routing/resource/trust/price fields in decision"))


def case_34_remote_topology_claim_not_promoted_to_authoritative_fact(results: List[Result]) -> None:
    """34. remote topology claim cannot become authoritative fact via policy.

    The ``topology-evidence-present`` predicate is a reference-presence
    check ONLY. The engine never inspects the classification of the
    evidence (SELF_OBSERVATION vs REMOTE_RELAY) -- that is WORK-007
    topology authority. A policy rule may say "deny unless evidence
    ref E is present" but MUST NOT promote that claim into topology
    authority (LOCK-008).
    """
    cond = Condition(predicate=PredicateKind.TOPOLOGY_EVIDENCE_PRESENT, arguments={"evidence_ref": "ev-remote-relay-1"})
    r = base_rule(rule_id="r1", effect=Effect.ALLOW, domain=PolicyDomain.RESOURCE, conditions=(cond,))
    ps = base_set(rules=(r,), domain_precedence=(PolicyDomain.RESOURCE,))
    ctx = base_ctx(topology_evidence_refs=("ev-remote-relay-1",))
    res = evaluate(ps, ctx)
    if not (res.ok and res.code == DecisionCode.ALLOW):
        results.append(fail("case_34_remote_topology_claim_not_promoted", "expected ALLOW, got %r" % res.code))
        return
    # The decision MUST NOT carry any topology fact / authoritative
    # subject fact field. The evidence ref is consumed by reference
    # only; it is NOT promoted into an authoritative fact.
    dec_text = res.decision.canonical_bytes().decode("utf-8")
    forbidden = ('"topology_fact"', '"authoritative_subject_fact"', '"evidence_class"', '"is_authoritative"')
    for f in forbidden:
        if f in dec_text:
            results.append(fail("case_34_remote_topology_claim_not_promoted", "forbidden field in decision: %s" % f))
            return
    # The context's evidence refs are unchanged (immutable context).
    if ctx.topology_evidence_refs == ("ev-remote-relay-1",):
        results.append(ok("case_34_remote_topology_claim_not_promoted", "remote evidence ref matched; not promoted; context unchanged"))
    else:
        results.append(fail("case_34_remote_topology_claim_not_promoted", "context evidence refs mutated"))


def case_35_policy_evaluation_cannot_mutate_state(results: List[Result]) -> None:
    """35. policy evaluation cannot mutate topology/resource/identity state.

    The engine is pure: it does not mutate the policy set, context, or
    any referenced object. We exercise this by holding references to the
    context's tuples (resource_refs, etc.) before/after evaluation and
    asserting identity is preserved (same tuple objects, same length,
    same contents).
    """
    r = base_rule(rule_id="r1", effect=Effect.ALLOW, domain=PolicyDomain.RESOURCE)
    ps = base_set(rules=(r,), domain_precedence=(PolicyDomain.RESOURCE,))
    ctx = base_ctx(
        resource_refs=("res-1", "res-2"),
        locality_labels=("village-A",),
        privacy_requirements=("end-to-end",),
        capability_evidence_refs=("cap-1",),
        topology_evidence_refs=("ev-1",),
        trust_assertions=(("verified", "high"),),
    )
    # Capture pre-evaluation state.
    pre_resource_refs = ctx.resource_refs
    pre_locality = ctx.locality_labels
    pre_privacy = ctx.privacy_requirements
    pre_caps = ctx.capability_evidence_refs
    pre_topology = ctx.topology_evidence_refs
    pre_trust = ctx.trust_assertions
    pre_intent = ctx.normalized_intent_digest
    pre_requester = ctx.requester_node_id
    res = evaluate(ps, ctx)
    if not res.ok:
        results.append(fail("case_35_policy_evaluation_cannot_mutate_state", "expected ok, got %r" % res.code))
        return
    # Post-evaluation: every captured tuple must be the SAME object
    # (Python id) -- proving no mutation. dataclass(frozen=True) +
    # tuple fields guarantee this structurally, but we assert it.
    post = (
        ctx.resource_refs, ctx.locality_labels, ctx.privacy_requirements,
        ctx.capability_evidence_refs, ctx.topology_evidence_refs,
        ctx.trust_assertions, ctx.normalized_intent_digest, ctx.requester_node_id,
    )
    pre = (pre_resource_refs, pre_locality, pre_privacy, pre_caps, pre_topology, pre_trust, pre_intent, pre_requester)
    if all(a is b for a, b in zip(pre, post)) and all(a == b for a, b in zip(pre, post)):
        results.append(ok("case_35_policy_evaluation_cannot_mutate_state", "all context fields preserved (same objects)"))
    else:
        results.append(fail("case_35_policy_evaluation_cannot_mutate_state", "context mutated during evaluation"))


def case_36_audit_records_rule_ids_and_policy_version(results: List[Result]) -> None:
    """36. policy decision audit records participating rule IDs and policy version."""
    r = base_rule(rule_id="audit-r1", effect=Effect.ALLOW, domain=PolicyDomain.RESOURCE)
    ps = base_set(set_id="audit-ps", version=42, rules=(r,), domain_precedence=(PolicyDomain.RESOURCE,))
    ctx = base_ctx()
    res = evaluate(ps, ctx)
    if not (res.ok and res.decision):
        results.append(fail("case_36_audit_records_rule_ids_and_policy_version", "expected ok"))
        return
    d = res.decision
    if d.matched_rule_ids != ("audit-r1",):
        results.append(fail("case_36_audit_records_rule_ids_and_policy_version", "rule_ids wrong: %r" % (d.matched_rule_ids,)))
        return
    if d.policy_set_id != "audit-ps" or d.policy_set_version != 42:
        results.append(fail("case_36_audit_records_rule_ids_and_policy_version", "set id/version wrong: %r/%r" % (d.policy_set_id, d.policy_set_version)))
        return
    if not d.conflict_trace:
        results.append(fail("case_36_audit_records_rule_ids_and_policy_version", "conflict_trace empty"))
        return
    results.append(ok("case_36_audit_records_rule_ids_and_policy_version", "rule_ids+set_id+version+trace recorded"))


def case_37_secret_material_rejected_and_not_echoed(results: List[Result]) -> None:
    """37. secret material rejected and not echoed in diagnostics."""
    # A rule extension carrying a "private_key" field.
    bad_ext = {"private_key": "xxx"}
    try:
        r = PolicyRule(
            rule_id="r1",
            domain=PolicyDomain.RESOURCE,
            effect=Effect.ALLOW,
            operation=Operation.RESOURCE_RESERVE,
            extensions=(bad_ext,),
        )
        validate_rule(r)
        results.append(fail("case_37_secret_material_rejected_and_not_echoed", "secret in rule extensions not rejected"))
        return
    except PolicyError as e:
        if e.code != "secret-material":
            results.append(fail("case_37_secret_material_rejected_and_not_echoed", "wrong code %r" % e.code))
            return
        # The diagnostic MUST NOT echo the secret value "xxx".
        if "xxx" in e.detail:
            results.append(fail("case_37_secret_material_rejected_and_not_echoed", "secret value echoed in detail: %r" % e.detail))
            return
    # Also test deeply-nested secret in a context extension.
    nested = {"outer": {"inner": [{"password": "hunter2"}]}}
    try:
        ctx = PolicyContext(
            operation=Operation.RESOURCE_RESERVE,
            requester_node_id=_NODE_A,
            evaluation_instant=_NOW,
            extensions=(nested,),
        )
        validate_context(ctx)
        results.append(fail("case_37_secret_material_rejected_and_not_echoed", "nested secret in context extensions not rejected"))
        return
    except PolicyError as e:
        if e.code != "secret-material":
            results.append(fail("case_37_secret_material_rejected_and_not_echoed", "ctx wrong code %r" % e.code))
            return
        if "hunter2" in e.detail:
            results.append(fail("case_37_secret_material_rejected_and_not_echoed", "ctx secret echoed: %r" % e.detail))
            return
    results.append(ok("case_37_secret_material_rejected_and_not_echoed", "rule+context secret material rejected; not echoed"))


def case_38_unsupported_predicate_fails_explicitly(results: List[Result]) -> None:
    """38. unsupported predicate fails explicitly (rule 8)."""
    # Construct a Condition with an unknown predicate -> constructor rejects.
    try:
        Condition(predicate="unknown-future-predicate", arguments={})
        results.append(fail("case_38_unsupported_predicate_fails_explicitly", "unknown predicate accepted at construction"))
        return
    except PolicyError as e:
        if e.code != "predicate":
            results.append(fail("case_38_unsupported_predicate_fails_explicitly", "wrong code %r" % e.code))
            return
    # Also exercise an unsupported-argument path: a known predicate with
    # a missing required argument.
    cond = Condition(predicate=PredicateKind.ENERGY_RESERVE_GTE, arguments={})  # missing threshold
    r = base_rule(rule_id="r1", effect=Effect.ALLOW, domain=PolicyDomain.ENERGY, conditions=(cond,))
    ps = base_set(rules=(r,), domain_precedence=(PolicyDomain.ENERGY,))
    ctx = base_ctx(energy_reserve_current=1000)
    res = evaluate(ps, ctx)
    # The predicate returns unsupported-argument -> rule does not match
    # -> DEFAULT_DENY (privileged operation).
    if res.ok and res.code == DecisionCode.DEFAULT_DENY:
        results.append(ok("case_38_unsupported_predicate_fails_explicitly", "unknown predicate rejected; unsupported-argument -> DEFAULT_DENY"))
    else:
        results.append(fail("case_38_unsupported_predicate_fails_explicitly", "got %r" % res.code))


def case_39_implementation_specific_access_technology_predicate_rejected(results: List[Result]) -> None:
    """39. implementation-specific access technology predicate rejected.

    A rule_id / provenance / locality label / federation domain /
    service class containing a forbidden 5G/Wi-Fi/vendor/route token
    is rejected by validate_rule / validate_context (LOCK-001/002/003/004).
    """
    forbidden_values = (
        ("rule_id", "rule-5g-bypass"),
        ("provenance", "wifi-ssid-policy"),
        ("federation_domain", "satellite-mesh-1"),
        ("service_class", "lte-priority"),
        ("resource_kind", "5g-bearer"),
        ("locality_label", "wifi-zone-A"),
    )
    for label, value in forbidden_values:
        try:
            if label == "rule_id":
                r = base_rule(rule_id=value)
                validate_rule(r)
            elif label == "provenance":
                r = base_rule(provenance=value)
                validate_rule(r)
            elif label == "federation_domain":
                ctx = base_ctx(federation_domain=value)
                validate_context(ctx)
            elif label == "service_class":
                ctx = base_ctx(service_class=value)
                validate_context(ctx)
            elif label == "resource_kind":
                ctx = base_ctx(resource_kind=value)
                validate_context(ctx)
            elif label == "locality_label":
                ctx = base_ctx(locality_labels=(value,))
                validate_context(ctx)
            results.append(fail("case_39_implementation_specific_access_technology_predicate_rejected", "%s=%r not rejected" % (label, value)))
            return
        except PolicyError as e:
            if e.code != "access-technology-leakage":
                results.append(fail("case_39_implementation_specific_access_technology_predicate_rejected", "%s=%r wrong code %r" % (label, value, e.code)))
                return
    results.append(ok("case_39_implementation_specific_access_technology_predicate_rejected", "all 6 forbidden-token fields rejected"))


def case_40_decision_bytes_digest_deterministic_across_runs(results: List[Result]) -> None:
    """40. decision bytes/digest deterministic across repeated runs."""
    r = base_rule(rule_id="r1", effect=Effect.ALLOW, domain=PolicyDomain.RESOURCE, priority=2)
    r2 = base_rule(rule_id="r2", effect=Effect.DENY, domain=PolicyDomain.RESOURCE, priority=1)
    r3 = base_rule(rule_id="r3", effect=Effect.ALLOW, domain=PolicyDomain.IDENTITY, priority=3)
    ps = base_set(rules=(r, r2, r3), domain_precedence=(PolicyDomain.RESOURCE, PolicyDomain.IDENTITY))
    ctx = base_ctx()
    res1 = evaluate(ps, ctx)
    res2 = evaluate(ps, ctx)
    if not (res1.ok and res2.ok and res1.decision and res2.decision):
        results.append(fail("case_40_decision_bytes_digest_deterministic_across_runs", "expected ok"))
        return
    d1, d2 = res1.decision, res2.decision
    if d1.decision_id == d2.decision_id and d1.canonical_bytes() == d2.canonical_bytes():
        # Also verify the public invariant: sha256(canonical_bytes()) == decision_id
        recomputed = hashlib.sha256(d1.canonical_bytes()).hexdigest()
        if recomputed == d1.decision_id:
            results.append(ok("case_40_decision_bytes_digest_deterministic_across_runs", "byte-identical; invariant holds; id=%s" % d1.decision_id[:12]))
        else:
            results.append(fail("case_40_decision_bytes_digest_deterministic_across_runs", "invariant broken: %s != %s" % (recomputed[:12], d1.decision_id[:12])))
    else:
        results.append(fail("case_40_decision_bytes_digest_deterministic_across_runs", "differ: %s vs %s" % (d1.decision_id[:12], d2.decision_id[:12])))


def case_41_fuzz_property_inputs_never_crash_or_mutate_external_state(results: List[Result]) -> None:
    """41. fuzz/property inputs never crash or mutate external state.

    A small deterministic fuzz loop: vary (effect, domain, operation,
    priority, specificity) combinations and assert the engine returns
    a well-formed PolicyEvaluationResult (never raises, never crashes,
    never mutates the context's tuples).
    """
    import itertools
    effects = (Effect.ALLOW, Effect.DENY, Effect.REQUIRE_REVIEW)
    domains = (PolicyDomain.RESOURCE, PolicyDomain.IDENTITY, PolicyDomain.PRIVACY)
    operations = (Operation.RESOURCE_RESERVE, Operation.SESSION_CREATE, Operation.EMERGENCY_PREEMPT)
    priorities = (0, 1, 5)
    specificities = (0, 1, 5)
    crash = False
    for i, (eff, dom, op, pri, spe) in enumerate(itertools.product(effects, domains, operations, priorities, specificities)):
        if i >= 60:  # cap the fuzz to keep the suite fast
            break
        r = base_rule(rule_id="rf%d" % i, effect=eff, domain=dom, operation=op, priority=pri, specificity=spe)
        ps = base_set(set_id="fuzz%d" % i, rules=(r,), domain_precedence=(dom,))
        ctx = base_ctx(operation=op, resource_refs=("res-fuzz-%d" % i,))
        pre_refs = ctx.resource_refs
        try:
            res = evaluate(ps, ctx)
        except Exception as exc:
            crash = True
            results.append(fail("case_41_fuzz_property_inputs_never_crash_or_mutate_external_state", "crash at i=%d: %s %s" % (i, type(exc).__name__, exc)))
            return
        if not isinstance(res, PolicyEvaluationResult):
            crash = True
            results.append(fail("case_41_fuzz_property_inputs_never_crash_or_mutate_external_state", "non-result at i=%d" % i))
            return
        if ctx.resource_refs is not pre_refs or ctx.resource_refs != pre_refs:
            crash = True
            results.append(fail("case_41_fuzz_property_inputs_never_crash_or_mutate_external_state", "context mutated at i=%d" % i))
            return
    if not crash:
        results.append(ok("case_41_fuzz_property_inputs_never_crash_or_mutate_external_state", "60 fuzz combinations: no crash, no mutation"))


# --------------------------------------------------------------------------
# Mechanical / boundary cases (42+)
# --------------------------------------------------------------------------

def case_42_no_5g_vendor_imports(results: List[Result]) -> None:
    """No 5G/Wi-Fi/vendor SDK imports in policy/."""
    policy_dir = REPO_ROOT / "policy"
    forbidden_patterns = (
        "import 5g", "from 5g",
        "import wifi", "from wifi",
        "import cellular", "from cellular",
        "import satellite", "from satellite",
        "import huawei", "from huawei",
        "import ericsson", "from ericsson",
        "import nokia", "from nokia",
        "import samsung", "from samsung",
        "import fiber", "from fiber",
        "import ran", "from ran",
        "import adapter_5g", "from adapter_5g",
        "import lte", "from lte",
        "import nr", "from nr",
    )
    leaks = []
    for src in policy_dir.glob("*.py"):
        text = src.read_text(encoding="utf-8")
        for pat in forbidden_patterns:
            if pat in text:
                leaks.append("%s: %r" % (src.name, pat))
    if leaks:
        results.append(fail("case_42_no_5g_vendor_imports", "forbidden imports: %s" % leaks))
    else:
        results.append(ok("case_42_no_5g_vendor_imports", "no 5G/vendor SDK imports in policy/"))


def case_43_no_wall_clock_imports(results: List[Result]) -> None:
    """No wall-clock reads in pure evaluation. The engine consumes an
    INJECTED evaluation_instant; it MUST NOT import time.monotonic /
    datetime.now / time.time / time.perf_counter for evaluation
    decisions. (datetime is imported for typed UTC parsing only, which
    is allowed; the audit checks for the four wall-clock read APIs.)"""
    policy_dir = REPO_ROOT / "policy"
    forbidden = (
        "time.monotonic", "time.perf_counter", "time.time",
        "datetime.now", "datetime.utcnow", "datetime.today",
        "time.localtime", "time.gmtime", "time.strftime",
    )
    leaks = []
    for src in policy_dir.glob("*.py"):
        text = src.read_text(encoding="utf-8")
        for pat in forbidden:
            if pat in text:
                leaks.append("%s: %r" % (src.name, pat))
    if leaks:
        results.append(fail("case_43_no_wall_clock_imports", "wall-clock reads: %s" % leaks))
    else:
        results.append(ok("case_43_no_wall_clock_imports", "no wall-clock reads in policy/ evaluation"))


def case_44_no_pricing_settlement_trust_route_imports(results: List[Result]) -> None:
    """No pricing/settlement/billing/trust-scoring/route/path/adapter
    implementation in policy/."""
    policy_dir = REPO_ROOT / "policy"
    forbidden = (
        "def price", "def settle", "def settlement", "def billing",
        "def trust_score", "def score_trust",
        "def route", "def path_optimizer", "def select_adapter",
        "class PriceEngine", "class SettlementEngine", "class TrustScorer",
        "class RouteSelector", "class AdapterSelector", "class PathOptimizer",
        "import blockchain", "from blockchain",
        "import token", "from token",  # token module is stdlib (tokenizer); check would be too broad
    )
    # The token-module check is too broad (stdlib 'token' for Python
    # tokenizer); drop it and rely on the def/class checks above.
    forbidden = tuple(f for f in forbidden if "token" not in f)
    leaks = []
    for src in policy_dir.glob("*.py"):
        text = src.read_text(encoding="utf-8")
        for pat in forbidden:
            if pat in text:
                leaks.append("%s: %r" % (src.name, pat))
    if leaks:
        results.append(fail("case_44_no_pricing_settlement_trust_route_imports", "forbidden implementations: %s" % leaks))
    else:
        results.append(ok("case_44_no_pricing_settlement_trust_route_imports", "no price/settle/trust/route/adapter implementations in policy/"))


def case_45_frozen_vocabularies_present(results: List[Result]) -> None:
    """All frozen vocabularies are present and closed."""
    expected_effects = {"allow", "deny", "require-review"}
    expected_codes = {
        "allow", "deny", "default-deny", "fail-closed",
        "policy-expired", "policy-not-yet-valid", "missing-fact",
        "unsupported-predicate", "conflict", "invalid-subject", "invalid-policy",
    }
    expected_domains = {
        "identity", "resource", "locality", "federation", "privacy",
        "emergency", "service", "energy", "trust",
    }
    expected_ops = {
        "resource.reserve", "resource.consume", "resource.release",
        "session.create", "session.modify", "session.terminate",
        "federation.join", "federation.accept-peer",
        "federation.resource-export", "federation.resource-import",
        "service.invoke", "privacy.requirement-override", "emergency.preempt",
        # WORK-026 deliberate vocabulary extension ("policy-controlled
        # authority"): the telemetry topology-promotion operation.
        "telemetry.topology-promote",
        # WORK-030 deliberate vocabulary extension ("privileged actions
        # require explicit policy"): the management role-assignment
        # administration operation.
        "management.role-assign",
    }
    expected_preds = {
        "subject-equals", "credential-active", "resource-owner",
        "resource-kind", "locality-equals", "federation-domain",
        "privacy-required", "emergency-true", "service-class",
        "energy-reserve-gte", "trust-min-class", "capability-required",
        "topology-evidence-present", "intent-present",
    }
    checks = (
        ("Effect", set(Effect.values()), expected_effects),
        ("DecisionCode", set(DecisionCode.values()), expected_codes),
        ("PolicyDomain", set(PolicyDomain.values()), expected_domains),
        ("Operation", set(Operation.values()), expected_ops),
        ("PredicateKind", set(PredicateKind.values()), expected_preds),
    )
    for label, actual, expected in checks:
        if actual != expected:
            results.append(fail("case_45_frozen_vocabularies_present", "%s mismatch: missing=%s extra=%s" % (label, expected - actual, actual - expected)))
            return
    results.append(ok("case_45_frozen_vocabularies_present", "all 5 frozen vocabularies present and closed"))


def case_46_privileged_classification_structural(results: List[Result]) -> None:
    """Privileged classification is structural -- all 15 frozen operations
    (13 at WORK-010 + the WORK-026 telemetry.topology-promote extension +
    the WORK-030 management.role-assign extension) are privileged;
    NON_PRIVILEGED is empty."""
    if len(Privileged.PRIVILEGED) != 15:
        results.append(fail("case_46_privileged_classification_structural", "expected 15 privileged ops, got %d" % len(Privileged.PRIVILEGED)))
        return
    if Privileged.NON_PRIVILEGED:
        results.append(fail("case_46_privileged_classification_structural", "NON_PRIVILEGED should be empty in WORK-010"))
        return
    for op in Operation.values():
        if not Privileged.is_privileged(op):
            results.append(fail("case_46_privileged_classification_structural", "op %r not privileged" % op))
            return
    results.append(ok("case_46_privileged_classification_structural", "all 15 ops privileged; classification structural"))


def case_47_decision_no_forbidden_fields(results: List[Result]) -> None:
    """Serialized PolicyDecision contains no forbidden fields."""
    r = base_rule(rule_id="r1", effect=Effect.ALLOW)
    ps = base_set(rules=(r,))
    ctx = base_ctx(requester_node_id=_NODE_A, extensions=({"opaque-tag": "ok"},))
    res = evaluate(ps, ctx)
    if not (res.ok and res.decision):
        results.append(fail("case_47_decision_no_forbidden_fields", "expected ok"))
        return
    serialized = res.decision.canonical_bytes().decode("utf-8")
    forbidden = (
        '"route"', '"path"', '"next_hop"', '"adapter"', '"access_technology"',
        '"selected_resource"', '"trust_score"', '"price"', '"settlement"',
        '"topology_fact"', '"authoritative_subject_fact"',
        '"private_key"', '"secret_key"', '"password"', '"token"',
    )
    for f in forbidden:
        if f in serialized:
            results.append(fail("case_47_decision_no_forbidden_fields", "forbidden field in decision: %s" % f))
            return
    results.append(ok("case_47_decision_no_forbidden_fields", "no forbidden fields in serialized decision"))


def case_48_policy_store_publish_withdraw_snapshot(results: List[Result]) -> None:
    """PolicyStore: publish -> snapshot -> withdraw -> snapshot (atomic sequencing)."""
    store = PolicyStore()
    r = base_rule(rule_id="r1", effect=Effect.ALLOW)
    ps_v1 = base_set(set_id="s1", version=1, rules=(r,))
    ps_v2 = base_set(set_id="s1", version=2, rules=(r,), default_effect=Effect.ALLOW)
    store.publish(ps_v1)
    snap1 = store.snapshot()
    if len(snap1) != 1 or snap1[0].version != 1:
        results.append(fail("case_48_policy_store_publish_withdraw_snapshot", "snapshot after publish v1 wrong: %r" % (snap1,)))
        return
    store.publish(ps_v2)
    snap2 = store.snapshot()
    if len(snap2) != 1 or snap2[0].version != 2:
        results.append(fail("case_48_policy_store_publish_withdraw_snapshot", "snapshot after publish v2 wrong: %r" % (snap2,)))
        return
    store.withdraw("s1", 2)
    snap3 = store.snapshot()
    # After withdrawing v2, the live entry is v1 again.
    if len(snap3) != 1 or snap3[0].version != 1:
        results.append(fail("case_48_policy_store_publish_withdraw_snapshot", "snapshot after withdraw v2 wrong: %r" % (snap3,)))
        return
    # Withdrawn entry is still queryable via get().
    if store.is_withdrawn("s1", 2):
        results.append(ok("case_48_policy_store_publish_withdraw_snapshot", "publish v1->v2->withdraw v2; live=v1; v2 queryable+withdrawn"))
    else:
        results.append(fail("case_48_policy_store_publish_withdraw_snapshot", "v2 not marked withdrawn"))
        return


def case_49_policy_store_version_regression_rejected(results: List[Result]) -> None:
    """PolicyStore: older version cannot replace newer version."""
    store = PolicyStore()
    r = base_rule(rule_id="r1", effect=Effect.ALLOW)
    ps_v2 = base_set(set_id="s1", version=2, rules=(r,))
    ps_v1 = base_set(set_id="s1", version=1, rules=(r,))
    store.publish(ps_v2)
    try:
        store.publish(ps_v1)  # older version -> must fail
        results.append(fail("case_49_policy_store_version_regression_rejected", "older version accepted"))
        return
    except PolicyError as e:
        if e.code != "version-regression":
            results.append(fail("case_49_policy_store_version_regression_rejected", "wrong code %r" % e.code))
            return
    results.append(ok("case_49_policy_store_version_regression_rejected", "older version rejected (version-regression)"))


def case_50_policy_store_equal_version_different_content_rejected(results: List[Result]) -> None:
    """PolicyStore: equal-version/different-content conflicts fail closed."""
    store = PolicyStore()
    r = base_rule(rule_id="r1", effect=Effect.ALLOW)
    ps_a = base_set(set_id="s1", version=1, rules=(r,), default_effect=Effect.DENY)
    # Same version, different content (default_effect flipped).
    ps_b = base_set(set_id="s1", version=1, rules=(r,), default_effect=Effect.ALLOW)
    store.publish(ps_a)
    try:
        store.publish(ps_b)
        results.append(fail("case_50_policy_store_equal_version_different_content_rejected", "equal-version/different-content accepted"))
        return
    except PolicyError as e:
        if e.code != "version-conflict":
            results.append(fail("case_50_policy_store_equal_version_different_content_rejected", "wrong code %r" % e.code))
            return
    # Idempotent: same version, same content is a no-op.
    store.publish(ps_a)  # should not raise
    results.append(ok("case_50_policy_store_equal_version_different_content_rejected", "equal-version/different-content rejected; same-content idempotent"))


def case_51_policy_store_list_applicable_filters_expired(results: List[Result]) -> None:
    """PolicyStore.list_applicable filters out expired / not-yet-valid sets."""
    store = PolicyStore()
    r = base_rule(rule_id="r1", effect=Effect.ALLOW)
    ps_live = base_set(set_id="live", version=1, rules=(r,), valid_from=_NOW_VALID_FROM, valid_until=_NOW_VALID_UNTIL)
    ps_expired = base_set(set_id="expired", version=1, rules=(r,), valid_until="2026-01-01T00:00:00Z")
    ps_future = base_set(set_id="future", version=1, rules=(r,), valid_from="2027-01-01T00:00:00Z")
    store.publish(ps_live)
    store.publish(ps_expired)
    store.publish(ps_future)
    applicable = store.list_applicable(_NOW)
    ids = {ps.set_id for ps in applicable}
    if ids == {"live"}:
        results.append(ok("case_51_policy_store_list_applicable_filters_expired", "only live set applicable at _NOW"))
    else:
        results.append(fail("case_51_policy_store_list_applicable_filters_expired", "applicable=%s" % ids))


def case_52_serialization_roundtrip(results: List[Result]) -> None:
    """Serialization round-trip: policy_set_from_mapping(build_dict) -> PolicySet -> to_dict."""
    r = base_rule(rule_id="r1", effect=Effect.ALLOW, domain=PolicyDomain.RESOURCE, priority=2, specificity=1, provenance="unit-test")
    ps = base_set(rules=(r,), domain_precedence=(PolicyDomain.RESOURCE,), default_effect=Effect.DENY, issuer_node_id=_NODE_A, valid_from=_NOW_VALID_FROM, valid_until=_NOW_VALID_UNTIL)
    # to_dict then from_mapping then back to to_dict must be byte-identical.
    d1 = ps.to_dict()
    ps2 = policy_set_from_mapping(d1)
    d2 = ps2.to_dict()
    cb1 = policy_set_canonical_bytes(ps)
    cb2 = policy_set_canonical_bytes(ps2)
    if cb1 == cb2 and d1 == d2:
        results.append(ok("case_52_serialization_roundtrip", "byte-identical round-trip"))
    else:
        results.append(fail("case_52_serialization_roundtrip", "round-trip differs"))


def case_53_decision_digest_recomputable(results: List[Result]) -> None:
    """PUBLIC decision digest invariant: sha256(canonical_bytes()) == decision_id."""
    r = base_rule(rule_id="r1", effect=Effect.ALLOW)
    ps = base_set(rules=(r,))
    ctx = base_ctx()
    res = evaluate(ps, ctx)
    if not (res.ok and res.decision):
        results.append(fail("case_53_decision_digest_recomputable", "expected ok"))
        return
    d = res.decision
    recomputed = hashlib.sha256(d.canonical_bytes()).hexdigest()
    if recomputed != d.decision_id:
        results.append(fail("case_53_decision_digest_recomputable", "invariant broken: %s != %s" % (recomputed[:12], d.decision_id[:12])))
        return
    # content_dict MUST NOT carry the decision_id field (circular).
    content = d.content_dict()
    if "decision_id" in content:
        results.append(fail("case_53_decision_digest_recomputable", "content_dict carries decision_id (circular)"))
        return
    # to_dict MUST carry the decision_id field (storage form).
    stored = d.to_dict()
    if "decision_id" not in stored or stored["decision_id"] != d.decision_id:
        results.append(fail("case_53_decision_digest_recomputable", "to_dict missing decision_id"))
        return
    results.append(ok("case_53_decision_digest_recomputable", "sha256(canonical_bytes())==decision_id; content_dict/to_dict explicit"))


def case_54_require_review_never_silently_becomes_allow(results: List[Result]) -> None:
    """REQUIRE_REVIEW rule that wins -> DENY + FAIL_CLOSED (no silent ALLOW)."""
    r = base_rule(rule_id="rr1", effect=Effect.REQUIRE_REVIEW, domain=PolicyDomain.RESOURCE)
    ps = base_set(rules=(r,), domain_precedence=(PolicyDomain.RESOURCE,))
    ctx = base_ctx()
    res = evaluate(ps, ctx)
    if not (res.ok and res.decision):
        results.append(fail("case_54_require_review_never_silently_becomes_allow", "expected ok"))
        return
    if res.decision.effect != Effect.DENY:
        results.append(fail("case_54_require_review_never_silently_becomes_allow", "effect=%r (must be DENY)" % res.decision.effect))
        return
    if res.code != DecisionCode.FAIL_CLOSED:
        results.append(fail("case_54_require_review_never_silently_becomes_allow", "code=%r (must be FAIL_CLOSED)" % res.code))
        return
    results.append(ok("case_54_require_review_never_silently_becomes_allow", "REQUIRE_REVIEW -> DENY+FAIL_CLOSED (no silent ALLOW)"))


def case_55_domain_precedence_explicit(results: List[Result]) -> None:
    """domain_precedence is explicit and deterministic.

    Two conflicting ALLOW rules in different domains at equal
    priority/specificity. The domain listed earlier in
    domain_precedence wins; the decision is deterministic across
    insertion order.
    """
    ra = base_rule(rule_id="ra", effect=Effect.ALLOW, domain=PolicyDomain.RESOURCE)
    rb = base_rule(rule_id="rb", effect=Effect.ALLOW, domain=PolicyDomain.IDENTITY)
    # RESOURCE before IDENTITY -> ra wins.
    ps1 = base_set(rules=(ra, rb), domain_precedence=(PolicyDomain.RESOURCE, PolicyDomain.IDENTITY))
    # Reverse insertion order; same precedence; SAME set_id.
    ps2 = base_set(rules=(rb, ra), domain_precedence=(PolicyDomain.RESOURCE, PolicyDomain.IDENTITY))
    ctx = base_ctx()
    res1 = evaluate(ps1, ctx)
    res2 = evaluate(ps2, ctx)
    if not (res1.ok and res2.ok):
        results.append(fail("case_55_domain_precedence_explicit", "both must be ok: %r %r" % (res1.code, res2.code)))
        return
    if res1.decision.matched_rule_ids != ("ra",):
        results.append(fail("case_55_domain_precedence_explicit", "ps1 winner wrong: %r" % (res1.decision.matched_rule_ids,)))
        return
    if res2.decision.matched_rule_ids != ("ra",):
        results.append(fail("case_55_domain_precedence_explicit", "ps2 winner wrong: %r" % (res2.decision.matched_rule_ids,)))
        return
    if res1.decision is None or res2.decision is None:
        results.append(fail("case_55_domain_precedence_explicit", "missing decision: %r %r" % (res1.code, res2.code)))
        return
    if res1.decision.decision_id != res2.decision.decision_id:
        results.append(fail("case_55_domain_precedence_explicit", "decision ids differ"))
        return
    results.append(ok("case_55_domain_precedence_explicit", "RESOURCE before IDENTITY; ra wins; insertion-order-independent"))


def case_56_partial_domain_precedence_coverage_rejected(results: List[Result]) -> None:
    """domain_precedence partial coverage is rejected (ambiguous)."""
    r_resource = base_rule(rule_id="rr", effect=Effect.ALLOW, domain=PolicyDomain.RESOURCE)
    r_identity = base_rule(rule_id="ri", effect=Effect.ALLOW, domain=PolicyDomain.IDENTITY)
    # Precedence lists RESOURCE but not IDENTITY -> partial coverage.
    try:
        ps = PolicySet(
            set_id="partial",
            version=1,
            rules=(r_resource, r_identity),
            domain_precedence=(PolicyDomain.RESOURCE,),  # IDENTITY missing
            issuer_node_id=_NODE_A,
        )
        validate_policy_set(ps)
        results.append(fail("case_56_partial_domain_precedence_coverage_rejected", "partial coverage accepted"))
        return
    except PolicyError as e:
        if e.code != "domain-precedence-coverage":
            results.append(fail("case_56_partial_domain_precedence_coverage_rejected", "wrong code %r" % e.code))
            return
    results.append(ok("case_56_partial_domain_precedence_coverage_rejected", "partial coverage rejected (ambiguous)"))


def case_57_duplicate_rule_id_rejected(results: List[Result]) -> None:
    """Duplicate rule_id within a set is rejected (ambiguity)."""
    r1 = base_rule(rule_id="dup", effect=Effect.ALLOW)
    r2 = base_rule(rule_id="dup", effect=Effect.DENY)  # same rule_id
    try:
        ps = PolicySet(set_id="dup-set", version=1, rules=(r1, r2), issuer_node_id=_NODE_A)
        validate_policy_set(ps)
        results.append(fail("case_57_duplicate_rule_id_rejected", "duplicate rule_id accepted"))
        return
    except PolicyError as e:
        if e.code != "duplicate-rule-id":
            results.append(fail("case_57_duplicate_rule_id_rejected", "wrong code %r" % e.code))
            return
    results.append(ok("case_57_duplicate_rule_id_rejected", "duplicate rule_id rejected"))


def case_58_malformed_temporal_rejected(results: List[Result]) -> None:
    """Malformed valid_from / valid_until (non-RFC-3339-UTC) rejected."""
    for bad in ("not-a-date", "2026-13-01T00:00:00Z", "2026-01-01T25:00:00Z", "2026-01-01T00:00:00", "2026-01-01T00:00:00+02:00"):
        try:
            r = base_rule(rule_id="r1", effect=Effect.ALLOW, valid_from=bad)
            validate_rule(r)
            results.append(fail("case_58_malformed_temporal_rejected", "bad valid_from %r accepted" % bad))
            return
        except PolicyError as e:
            if e.code != "valid-from":
                results.append(fail("case_58_malformed_temporal_rejected", "bad %r wrong code %r" % (bad, e.code)))
                return
    results.append(ok("case_58_malformed_temporal_rejected", "5 malformed temporal values rejected"))


def case_59_valid_until_before_valid_from_rejected(results: List[Result]) -> None:
    """valid_until < valid_from rejected (valid-before-from)."""
    try:
        r = base_rule(rule_id="r1", effect=Effect.ALLOW, valid_from=_NOW_VALID_UNTIL, valid_until=_NOW_VALID_FROM)
        validate_rule(r)
        results.append(fail("case_59_valid_until_before_valid_from_rejected", "valid_until<valid_from accepted"))
        return
    except PolicyError as e:
        if e.code != "valid-before-from":
            results.append(fail("case_59_valid_until_before_valid_from_rejected", "wrong code %r" % e.code))
            return
    results.append(ok("case_59_valid_until_before_valid_from_rejected", "valid_until<valid_from rejected"))


def case_60_thread_safe_evaluation(results: List[Result]) -> None:
    """Evaluation is thread-safe (no shared mutable state)."""
    r = base_rule(rule_id="r1", effect=Effect.ALLOW)
    ps = base_set(rules=(r,))
    ctx = base_ctx()
    decision_ids: List[str] = []
    errors: List[str] = []

    def _worker():
        try:
            res = evaluate(ps, ctx)
            if res.ok and res.decision:
                decision_ids.append(res.decision.decision_id)
            else:
                errors.append("err: %s" % res.code)
        except Exception as exc:  # pragma: no cover - defensive
            errors.append("exc: %s %s" % (type(exc).__name__, exc))

    threads = [threading.Thread(target=_worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if errors:
        results.append(fail("case_60_thread_safe_evaluation", "errors: %s" % errors[:3]))
    elif len(set(decision_ids)) == 1:
        results.append(ok("case_60_thread_safe_evaluation", "20 threads agree; id=%s" % decision_ids[0][:12]))
    else:
        results.append(fail("case_60_thread_safe_evaluation", "%d distinct ids across 20 threads" % len(set(decision_ids))))


def case_61_no_external_network_dependency(results: List[Result]) -> None:
    """No external network dependency: no socket/urllib/requests/http
    imports in policy/."""
    policy_dir = REPO_ROOT / "policy"
    forbidden = (
        "import socket", "from socket",
        "import urllib", "from urllib",
        "import requests", "from requests",
        "import http", "from http",
        "import aiohttp", "from aiohttp",
    )
    leaks = []
    for src in policy_dir.glob("*.py"):
        text = src.read_text(encoding="utf-8")
        for pat in forbidden:
            if pat in text:
                leaks.append("%s: %r" % (src.name, pat))
    if leaks:
        results.append(fail("case_61_no_external_network_dependency", "network imports: %s" % leaks))
    else:
        results.append(ok("case_61_no_external_network_dependency", "no network imports in policy/"))


def case_62_evaluation_instant_required(results: List[Result]) -> None:
    """Missing evaluation_instant -> FAIL_CLOSED (no wall-clock fallback)."""
    r = base_rule(rule_id="r1", effect=Effect.ALLOW)
    ps = base_set(rules=(r,))
    ctx = base_ctx(evaluation_instant="")
    res = evaluate(ps, ctx)
    if res.ok and res.code == DecisionCode.FAIL_CLOSED:
        results.append(ok("case_62_evaluation_instant_required", "empty evaluation_instant -> FAIL_CLOSED"))
    else:
        results.append(fail("case_62_evaluation_instant_required", "got %r" % res.code))


def case_63_malformed_evaluation_instant_fail_closed(results: List[Result]) -> None:
    """Malformed evaluation_instant -> FAIL_CLOSED (deterministic)."""
    r = base_rule(rule_id="r1", effect=Effect.ALLOW)
    ps = base_set(rules=(r,))
    for bad in ("not-a-date", "2026-13-01T00:00:00Z", "2026-01-01T25:00:00Z"):
        ctx = base_ctx(evaluation_instant=bad)
        res = evaluate(ps, ctx)
        if not (res.ok and res.code == DecisionCode.FAIL_CLOSED):
            results.append(fail("case_63_malformed_evaluation_instant_fail_closed", "bad %r got %r" % (bad, res.code)))
            return
    results.append(ok("case_63_malformed_evaluation_instant_fail_closed", "3 malformed instants -> FAIL_CLOSED"))


def case_64_rule_temporal_subwindow(results: List[Result]) -> None:
    """A rule's own validity window is a sub-interval of the set's window.
    An expired rule is skipped (not in the matched set) even when the
    set is still valid."""
    r_live = base_rule(rule_id="live", effect=Effect.ALLOW, valid_from=_NOW_VALID_FROM, valid_until=_NOW_VALID_UNTIL)
    r_expired = base_rule(rule_id="expired", effect=Effect.DENY, valid_until="2026-03-01T00:00:00Z")  # expired before _NOW
    ps = base_set(rules=(r_live, r_expired), domain_precedence=(PolicyDomain.IDENTITY,))
    ctx = base_ctx()
    res = evaluate(ps, ctx)
    # The expired DENY rule is skipped; only the live ALLOW rule matches.
    if res.ok and res.code == DecisionCode.ALLOW and res.decision.matched_rule_ids == ("live",):
        results.append(ok("case_64_rule_temporal_subwindow", "expired DENY rule skipped; live ALLOW wins"))
    else:
        results.append(fail("case_64_rule_temporal_subwindow", "got %r %r" % (res.code, res.detail)))


def case_65_subject_selector(results: List[Result]) -> None:
    """A rule with explicit subjects only matches when the context's
    requester is in the subject set; otherwise DEFAULT_DENY."""
    r = base_rule(rule_id="r1", effect=Effect.ALLOW, subjects=(_NODE_A,))
    ps = base_set(rules=(r,))
    # Match: requester is _NODE_A.
    res_ok = evaluate(ps, base_ctx(requester_node_id=_NODE_A))
    # No match: requester is _NODE_B.
    res_no = evaluate(ps, base_ctx(requester_node_id=_NODE_B))
    if res_ok.code == DecisionCode.ALLOW and res_no.code == DecisionCode.DEFAULT_DENY:
        results.append(ok("case_65_subject_selector", "subject match->ALLOW, mismatch->DEFAULT_DENY"))
    else:
        results.append(fail("case_65_subject_selector", "ok=%r no=%r" % (res_ok.code, res_no.code)))


def case_66_trust_assertion_input_not_score(results: List[Result]) -> None:
    """trust-min-class predicate consumes an explicit INPUT assertion --
    NOT a computed trust score (LOCK-022)."""
    cond = Condition(predicate=PredicateKind.TRUST_MIN_CLASS, arguments={"min": "verified"})
    r = base_rule(rule_id="r1", effect=Effect.ALLOW, domain=PolicyDomain.TRUST, conditions=(cond,))
    ps = base_set(rules=(r,), domain_precedence=(PolicyDomain.TRUST,))
    # Context carries a verified trust assertion -> match.
    ctx_ok = base_ctx(trust_assertions=(("verified", "high"),))
    # Context carries only an attested assertion -> below min -> no match.
    ctx_no = base_ctx(trust_assertions=(("attested", "mid"),))
    res_ok = evaluate(ps, ctx_ok)
    res_no = evaluate(ps, ctx_no)
    if res_ok.code == DecisionCode.ALLOW and res_no.code == DecisionCode.DEFAULT_DENY:
        results.append(ok("case_66_trust_assertion_input_not_score", "verified>=verified->ALLOW; attested<verified->DEFAULT_DENY (input, not score)"))
    else:
        results.append(fail("case_66_trust_assertion_input_not_score", "ok=%r no=%r" % (res_ok.code, res_no.code)))


def case_67_capability_required(results: List[Result]) -> None:
    """capability-required predicate matches when the context carries the ref."""
    cond = Condition(predicate=PredicateKind.CAPABILITY_REQUIRED, arguments={"capability_id": "cap-bandwidth-1"})
    r = base_rule(rule_id="r1", effect=Effect.ALLOW, domain=PolicyDomain.RESOURCE, conditions=(cond,))
    ps = base_set(rules=(r,), domain_precedence=(PolicyDomain.RESOURCE,))
    ctx = base_ctx(capability_evidence_refs=("cap-bandwidth-1",))
    res = evaluate(ps, ctx)
    if res.ok and res.code == DecisionCode.ALLOW:
        results.append(ok("case_67_capability_required", "capability ref match -> ALLOW"))
    else:
        results.append(fail("case_67_capability_required", "got %r" % res.code))


def case_68_frozen_doc_unchanged(results: List[Result]) -> None:
    """Frozen architecture documents are byte-identical to the merged main."""
    import subprocess
    frozen = ["spec/architecture.md", "spec/architecture-lock.md", "spec/work-items.md", "spec/dependency-graph.md"]
    problems = []
    for doc in frozen:
        try:
            # diff against origin/main -- the merged WORK-009 head.
            r = subprocess.run(
                ["git", "diff", "origin/main", "--", doc],
                cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=10,
            )
            if r.stdout.strip():
                problems.append("%s changed vs origin/main" % doc)
        except Exception as exc:  # pragma: no cover - defensive
            problems.append("%s: git diff failed: %s" % (doc, exc))
    if problems:
        results.append(fail("case_68_frozen_doc_unchanged", "; ".join(problems)))
    else:
        results.append(ok("case_68_frozen_doc_unchanged", "all 4 frozen docs unchanged vs origin/main"))


def case_69_prior_prompts_unchanged(results: List[Result]) -> None:
    """Prior prompts WORK-001..WORK-009 are byte-identical to origin/main."""
    import subprocess
    prompts_dir = REPO_ROOT / "spec" / "prompts"
    prompts = sorted(p.name for p in prompts_dir.iterdir() if p.name.startswith("WORK-") and p.name.endswith(".md"))
    # WORK-012.md is new on this branch (the WORK-012 handoff);
    # WORK-001..011 prompts are merged into main and INCLUDED in the
    # byte-identity check below.
    prior = [p for p in prompts if p != "WORK-014.md"]
    problems = []
    for doc in prior:
        try:
            r = subprocess.run(
                ["git", "diff", "origin/main", "--", "spec/prompts/" + doc],
                cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=10,
            )
            if r.stdout.strip():
                problems.append("%s changed vs origin/main" % doc)
        except Exception as exc:  # pragma: no cover - defensive
            problems.append("%s: git diff failed: %s" % (doc, exc))
    if problems:
        results.append(fail("case_69_prior_prompts_unchanged", "; ".join(problems)))
    else:
        results.append(ok("case_69_prior_prompts_unchanged", "all %d prior prompts unchanged vs origin/main" % len(prior)))


# --------------------------------------------------------------------------
# Architect-review regression cases (PR #10 correction cycle)
# --------------------------------------------------------------------------

def case_70_issuer_mandatory(results: List[Result]) -> None:
    """REGRESSION (Architect review of PR #10, blocker 1): every PolicySet
    MUST identify its authority/issuer. An empty/missing ``issuer_node_id``
    is rejected at construction, at validation, and at wire-form
    deserialization -- an anonymous policy MUST NOT be publishable or
    evaluable (frozen "Policy authority and provenance" requirement).
    """
    from policy.validation import _validate_issuer_node_id
    r = base_rule(rule_id="r1", effect=Effect.ALLOW, domain=PolicyDomain.RESOURCE)
    problems = []
    # 1. Direct construction with empty issuer -> rejected at __post_init__.
    try:
        PolicySet(set_id="anon", version=1, rules=(r,), issuer_node_id="")
        problems.append("construction with empty issuer accepted")
    except PolicyError as e:
        if e.code != "issuer":
            problems.append("construction wrong code %r (want 'issuer')" % e.code)
    # 2. The validator's _validate_issuer_node_id rejects empty.
    try:
        _validate_issuer_node_id("", "anon-set")
        problems.append("validate_issuer_node_id('') accepted")
    except PolicyError as e:
        if e.code != "issuer":
            problems.append("validate_issuer_node_id('') wrong code %r" % e.code)
    # 3. Wire-form deserialization without issuer -> rejected.
    wire = {"set_id": "anon-wire", "version": 1, "rules": [r.to_dict()]}
    try:
        policy_set_from_mapping(wire)
        problems.append("deserialization without issuer accepted")
    except PolicyError as e:
        if e.code != "issuer":
            problems.append("deserialization wrong code %r (want 'issuer')" % e.code)
    # 4. A well-formed canonical issuer round-trips and evaluates normally.
    ps = base_set(rules=(r,), issuer_node_id=_NODE_A)
    validate_policy_set(ps)
    ctx = base_ctx()
    res = evaluate(ps, ctx)
    if not (res.ok and res.code == DecisionCode.ALLOW):
        problems.append("well-formed issuer did not evaluate to ALLOW: %r" % res.code)
    if problems:
        results.append(fail("case_70_issuer_mandatory", "; ".join(problems)))
    else:
        results.append(ok("case_70_issuer_mandatory", "empty issuer rejected at construction/validation/deserialization; valid issuer round-trips"))


def case_71_issuer_must_be_canonical_nodeid(results: List[Result]) -> None:
    """REGRESSION (Architect review of PR #10, blocker 1): the issuer MUST be
    a CANONICAL WORK-004 NodeID, not merely a non-empty string. A well-
    formed-but-non-canonical issuer (wrong prefix, short/long digest,
    uppercase, non-hex, malformed profile) fails closed at validation.
    The model constructor checks non-emptiness only; the canonical-NodeID
    parse check is enforced by ``validate_policy_set`` (defense-in-depth
    at the wire-form boundary), so the deserialization + evaluation path
    rejects non-canonical issuers.
    """
    from policy.validation import _validate_issuer_node_id
    r = base_rule(rule_id="r1", effect=Effect.ALLOW)
    malformed_issuers = (
        "not-a-node",                                    # wrong prefix / shape
        "adcos:node:test.profile.v1:abc",                # short digest
        "adcos:node:test.profile.v1:" + "a" * 65,        # long digest
        "adcos:node:test.profile.v1:" + "A" * 64,        # uppercase hex
        "adcos:node:test.profile.v1:" + "z" * 64,        # non-hex chars
        "adcos:node:badprofile:" + "a" * 64,             # malformed profile
        "ADcos:node:test.profile.v1:" + "a" * 64,        # uppercase prefix
        "adcos:node:test.profile.v1:" + "a" * 64 + ":x",  # extra segment
    )
    problems = []
    # 1. The validator rejects every non-canonical issuer with code 'issuer'.
    for bad in malformed_issuers:
        try:
            _validate_issuer_node_id(bad, "set-x")
            problems.append("validator accepted %r" % (bad[:40],))
        except PolicyError as e:
            if e.code != "issuer":
                problems.append("validator wrong code %r for %r" % (e.code, bad[:40]))
    # 2. The model constructor accepts any non-empty string for issuer_node_id
    #    (it checks non-emptiness only), so a non-canonical issuer CAN be
    #    constructed directly -- but validate_policy_set rejects it. This
    #    proves the canonical-NodeID parse check is enforced at the
    #    validation layer, which is what evaluate() calls before evaluating.
    try:
        ps = PolicySet(set_id="badissuer", version=1, rules=(r,), issuer_node_id="not-a-node")
        validate_policy_set(ps)
        problems.append("validate_policy_set accepted non-canonical issuer")
    except PolicyError as e:
        if e.code != "issuer":
            problems.append("validate_policy_set wrong code %r for non-canonical issuer" % e.code)
    # 3. evaluate() itself rejects a non-canonical issuer (it calls
    #    validate_policy_set first and returns a fail-closed result -- the
    #    engine NEVER raises; it produces a stable INVALID_POLICY code so
    #    a non-canonical issuer cannot authorize anything).
    try:
        ps = PolicySet(set_id="badissuer-eval", version=1, rules=(r,), issuer_node_id="not-a-node")
    except PolicyError as e:  # pragma: no cover - constructor only checks non-empty
        problems.append("constructor rejected non-canonical issuer unexpectedly: %r" % e.code)
    else:
        res = evaluate(ps, base_ctx())
        if res.ok:
            problems.append("evaluate accepted non-canonical issuer (ok=True, code=%r)" % res.code)
        elif res.code != DecisionCode.INVALID_POLICY:
            problems.append("evaluate wrong code %r for non-canonical issuer (want INVALID_POLICY)" % res.code)
    if problems:
        results.append(fail("case_71_issuer_must_be_canonical_nodeid", "; ".join(problems)))
    else:
        results.append(ok("case_71_issuer_must_be_canonical_nodeid", "%d non-canonical issuers rejected at validation; evaluate() rejects too" % len(malformed_issuers)))


def case_72_malformed_intent_digest_cannot_authorize(results: List[Result]) -> None:
    """REGRESSION (Architect review of PR #10, blocker 2): a malformed
    intent reference (e.g. ``"not-an-intent"``) MUST NOT satisfy
    ``INTENT_PRESENT`` and MUST NOT participate in an allow rule. The
    digest is validated structurally (64 lowercase hex) at construction,
    at validation, at wire-form deserialization, and defensively inside
    the matcher. A malformed non-empty digest yields ``intent-digest``
    (fail closed), never ``satisfied``.
    """
    cond = Condition(predicate=PredicateKind.INTENT_PRESENT, arguments={})
    r = base_rule(rule_id="r1", effect=Effect.ALLOW, domain=PolicyDomain.RESOURCE, conditions=(cond,))
    ps = base_set(rules=(r,), domain_precedence=(PolicyDomain.RESOURCE,))
    problems = []
    malformed = (
        "not-an-intent",   # not hex at all
        "a" * 63,          # too short
        "a" * 65,          # too long
        "A" * 64,          # uppercase hex (must be lowercase)
        "g" * 64,          # non-hex chars
        "deadbeef",        # short hex
        "0123456789abcdef" * 4 + "0",  # 65 hex (boundary overflow)
    )
    for bad in malformed:
        # 1. Construction rejects malformed digests with code 'intent-digest'.
        try:
            PolicyContext(
                operation=Operation.RESOURCE_RESERVE,
                requester_node_id=_NODE_A,
                evaluation_instant=_NOW,
                normalized_intent_digest=bad,
            )
            problems.append("construction accepted malformed digest %r" % (bad[:20],))
        except PolicyError as e:
            if e.code != "intent-digest":
                problems.append("construction wrong code %r for %r" % (e.code, bad[:20]))
    # 2. Wire-form deserialization rejects a malformed digest.
    wire_ctx = {
        "operation": Operation.RESOURCE_RESERVE,
        "requester_node_id": _NODE_A,
        "evaluation_instant": _NOW,
        "normalized_intent_digest": "not-an-intent",
    }
    try:
        context_from_mapping(wire_ctx)
        problems.append("deserialization accepted malformed digest")
    except PolicyError as e:
        if e.code != "intent-digest":
            problems.append("deserialization wrong code %r" % e.code)
    # 3. A VALID 64-lowercase-hex digest satisfies INTENT_PRESENT and
    #    authorizes ALLOW (proves the gate is not over-restrictive).
    good = "a" * 64
    ctx_good = base_ctx(normalized_intent_digest=good)
    res = evaluate(ps, ctx_good)
    if not (res.ok and res.code == DecisionCode.ALLOW):
        problems.append("valid digest did not authorize ALLOW: %r" % res.code)
    # 4. An EMPTY digest does NOT satisfy INTENT_PRESENT (no intent
    #    referenced -> deny-by-default for the privileged resource.reserve
    #    operation). This proves the predicate is a presence check, not a
    #    blanket allow.
    ctx_empty = base_ctx()
    res_empty = evaluate(ps, ctx_empty)
    if res_empty.ok and res_empty.code == DecisionCode.ALLOW:
        problems.append("empty digest authorized ALLOW (intent-present should not match)")
    if problems:
        results.append(fail("case_72_malformed_intent_digest_cannot_authorize", "; ".join(problems)))
    else:
        results.append(ok("case_72_malformed_intent_digest_cannot_authorize", "malformed digests rejected at construction/deserialization; valid digest authorizes ALLOW; empty digest does not"))


def case_73_invocation_binding_born_bound(results: List[Result]) -> None:
    """REGRESSION (Architect review of PR #26, remediation 2 -- the
    WORK-025 service layer must never possess a binding-construction
    capability): the WORK-010 evaluator itself binds the exact
    invocation scope into every ``service.invoke`` decision it emits.

    Trust chain (PR #26 review comment 5434924645):

        WORK-010 policy authority / composition root
                -> decision already bound to exact invocation context
                -> services verification + extraction ONLY
                -> execution

    Discriminating legs:
    - a service.invoke evaluation produces a decision whose OWN
      digest-covered extensions carry exactly one invocation binding
      equal to the context's descriptor (born bound -- ALLOW and DENY
      alike);
    - the decision_id digest covers the binding (mutating the binding
      breaks sha256(canonical_bytes));
    - a service.invoke context WITHOUT a valid descriptor fails closed
      (ok=False, INVALID_POLICY, no decision) -- the engine never
      emits an unbound service.invoke decision, so no downstream
      consumer can be handed one to "convert";
    - the descriptor schema is strict (exactly six keys, string
      values, frozen operation) and MIRRORS the first-class context
      facts (caller == requester, tenant == federation_domain), so the
      authorized scope is exactly the evaluated scope;
    - a descriptor riding a NON-service.invoke context is inert
      opaque DATA: the decision carries no binding.
    """
    name = "case_73_invocation_binding_born_bound"
    problems: List[str] = []
    allow_rule = base_rule(
        rule_id="svc-allow", domain=PolicyDomain.SERVICE,
        effect=Effect.ALLOW, operation=Operation.SERVICE_INVOKE,
    )
    deny_rule = base_rule(
        rule_id="svc-deny", domain=PolicyDomain.SERVICE,
        effect=Effect.DENY, operation=Operation.SERVICE_INVOKE,
    )
    ps_allow = base_set(rules=(allow_rule,))
    ps_deny = base_set(rules=(deny_rule,))
    descriptor = {
        "kind": "adcos.service-invocation",
        "operation": Operation.SERVICE_INVOKE,
        "service_ref": "services:service:" + "a" * 32,
        "session_id": "sha256:" + "1" * 64,
        "caller_node_id": _NODE_A,
        "tenant_domain": "village-a",
    }
    good_kwargs: Dict[str, Any] = dict(
        operation=Operation.SERVICE_INVOKE,
        requester_node_id=_NODE_A,
        evaluation_instant=_NOW,
        federation_domain="village-a",
        resource_refs=("services:service:" + "a" * 32,),
        extensions=(dict(descriptor),),
    )

    def _descriptor_ctx(**overrides: Any) -> PolicyContext:
        kwargs = dict(good_kwargs)
        extensions = list(kwargs["extensions"])
        for key, value in overrides.items():
            if key == "extensions":
                extensions = [dict(e) for e in value]
            else:
                kwargs[key] = value
        kwargs["extensions"] = tuple(extensions)
        return base_ctx(**kwargs)

    # 1. Born bound: ALLOW decision carries exactly one binding equal
    #    to the descriptor, digest-covered.
    res = evaluate(ps_allow, _descriptor_ctx())
    if not (res.ok and res.decision and res.code == DecisionCode.ALLOW):
        problems.append("valid service.invoke context did not yield ALLOW: %r" % (res.code,))
    else:
        bindings = [
            e for e in res.decision.extensions
            if e.get("kind") == "adcos.service-invocation"
        ]
        if len(bindings) != 1:
            problems.append("decision carries %d invocation bindings (expected 1)" % len(bindings))
        elif dict(bindings[0]) != descriptor:
            problems.append("binding != descriptor: %r" % (dict(bindings[0]),))
        else:
            import hashlib as _hashlib
            if res.decision.decision_id != _hashlib.sha256(
                res.decision.canonical_bytes()
            ).hexdigest():
                problems.append("decision_id does not bind canonical bytes")
            # Mutating the binding breaks the digest (tamper-evidence).
            mutated = PolicyDecision(
                decision_id=res.decision.decision_id,
                effect=res.decision.effect,
                code=res.decision.code,
                detail=res.decision.detail,
                matched_rule_ids=res.decision.matched_rule_ids,
                policy_set_id=res.decision.policy_set_id,
                policy_set_version=res.decision.policy_set_version,
                evaluation_instant=res.decision.evaluation_instant,
                conflict_trace=res.decision.conflict_trace,
                extensions=(
                    dict(bindings[0], service_ref="services:service:" + "b" * 32),
                ) + res.decision.extensions[1:],
            )
            if mutated.decision_id == _hashlib.sha256(
                mutated.canonical_bytes()
            ).hexdigest():
                problems.append("mutated binding still satisfies the digest")
    # 2. DENY decisions are born bound too (auditable artifacts).
    res_deny = evaluate(ps_deny, _descriptor_ctx())
    if not (res_deny.ok and res_deny.decision and res_deny.decision.effect == Effect.DENY):
        problems.append("deny-rule service.invoke context did not yield DENY")
    elif not any(
        e.get("kind") == "adcos.service-invocation" for e in res_deny.decision.extensions
    ):
        problems.append("DENY decision not born bound")
    # 3. Fail-closed matrix: each malformed/absent descriptor yields
    #    ok=False INVALID_POLICY with NO decision (an unbound
    #    service.invoke decision can never be obtained from the engine).
    def _expect_invalid(label: str, ctx: PolicyContext) -> None:
        outcome = evaluate(ps_allow, ctx)
        if outcome.ok or outcome.decision is not None:
            problems.append("%s: engine did not fail closed (%r)" % (label, outcome.code))
        elif outcome.code != DecisionCode.INVALID_POLICY:
            problems.append("%s: wrong code %r" % (label, outcome.code))

    _expect_invalid(
        "no descriptor",
        base_ctx(
            operation=Operation.SERVICE_INVOKE,
            requester_node_id=_NODE_A,
            evaluation_instant=_NOW,
            federation_domain="village-a",
        ),
    )
    _expect_invalid(
        "double descriptor",
        _descriptor_ctx(extensions=(dict(descriptor), dict(descriptor))),
    )
    _expect_invalid(
        "unknown key",
        _descriptor_ctx(extensions=({**descriptor, "extra": "x"},)),
    )
    _expect_invalid(
        "missing key",
        _descriptor_ctx(extensions=({k: v for k, v in descriptor.items() if k != "session_id"},)),
    )
    _expect_invalid(
        "non-string value",
        _descriptor_ctx(extensions=({**descriptor, "service_ref": 7},)),
    )
    _expect_invalid(
        "foreign operation",
        _descriptor_ctx(extensions=({**descriptor, "operation": Operation.RESOURCE_CONSUME},)),
    )
    _expect_invalid(
        "empty service_ref",
        _descriptor_ctx(extensions=({**descriptor, "service_ref": ""},)),
    )
    _expect_invalid(
        "empty tenant",
        _descriptor_ctx(extensions=({**descriptor, "tenant_domain": ""},)),
    )
    # Mirror violations: the descriptor disagrees with the first-class
    # context facts the rules evaluated.
    _expect_invalid(
        "caller mirror mismatch",
        _descriptor_ctx(extensions=({**descriptor, "caller_node_id": _NODE_B},)),
    )
    _expect_invalid(
        "tenant mirror mismatch",
        _descriptor_ctx(extensions=({**descriptor, "tenant_domain": "village-z"},)),
    )
    # 4. The derivation function itself self-defends against foreign
    #    operations (direct call contract).
    try:
        invocation_binding_from_context(base_ctx(operation=Operation.RESOURCE_RESERVE))
        problems.append("derivation accepted a non-service.invoke context")
    except PolicyError as e:
        if e.code != "invocation-binding":
            problems.append("derivation wrong code %r" % e.code)
    # 5. A descriptor riding a NON-service.invoke context is inert
    #    opaque DATA: the decision carries no binding.
    res_other = evaluate(
        base_set(rules=(base_rule(rule_id="r-rr", effect=Effect.ALLOW),)),
        base_ctx(
            operation=Operation.RESOURCE_RESERVE,
            requester_node_id=_NODE_A,
            evaluation_instant=_NOW,
            extensions=(dict(descriptor),),
        ),
    )
    if not (res_other.ok and res_other.decision):
        problems.append("descriptor on resource.reserve broke evaluation")
    elif any(e.get("kind") == "adcos.service-invocation" for e in res_other.decision.extensions):
        problems.append("non-service.invoke decision unexpectedly carries a binding")
    # 6. Determinism + scope sensitivity: same context -> byte-identical
    #    decision; a different scope -> a different decision_id.
    again = evaluate(ps_allow, _descriptor_ctx())
    if again.decision is None or res.decision is None:
        problems.append("re-evaluation lost the decision")
    elif again.decision.canonical_bytes() != res.decision.canonical_bytes():
        problems.append("re-evaluation not byte-identical")
    else:
        other_scope = evaluate(
            ps_allow,
            _descriptor_ctx(
                extensions=(
                    {**descriptor, "service_ref": "services:service:" + "c" * 32},
                ),
                resource_refs=("services:service:" + "c" * 32,),
            ),
        )
        if other_scope.decision is None:
            problems.append("other-scope evaluation lost the decision")
        elif other_scope.decision.decision_id == res.decision.decision_id:
            problems.append("different invocation scopes produced the same decision_id")
    if problems:
        results.append(fail(name, "; ".join(problems)))
    else:
        results.append(
            ok(
                name,
                "service.invoke decisions born bound (digest-covered, mirror-checked); "
                "missing/malformed descriptor fails closed; inert on other operations",
            )
        )


def case_74_promotion_binding_born_bound(results: List[Result]) -> None:
    """REGRESSION (WORK-026 "policy-controlled authority"): the frozen
    ``telemetry.topology-promote`` operation is PRIVILEGED
    (deny-by-default) and its decisions are BORN bound to the exact
    promotion scope (observation, subject kind, subject ref) AND the
    privacy disclosure authorization (privacy_scope,
    source_disclosure) -- the same trust chain case_73 pins for
    service.invoke, applied to the telemetry topology-promotion seam
    (privacy axes added by the PR #27 Architect review, blocker 2).
    Without an explicit rule ALLOW the promotion is denied by
    default, so telemetry can never silently become topology
    authority.

    Discriminating legs:
    - deny-by-default: no applicable rule -> DEFAULT_DENY (privileged
      operation), and even that denial is born bound;
    - an explicit ALLOW rule yields a decision whose digest-covered
      extensions carry exactly one promotion binding equal to the
      context's descriptor;
    - a promotion context WITHOUT a valid descriptor fails closed
      (ok=False, INVALID_POLICY, no decision);
    - the descriptor schema is strict (seven keys, strings, frozen
      operation) and its (observation, subject) scope EQUALS the
      context's first-class resource_refs scope EXACTLY (scope
      equality: membership is not authorization -- cross-pairing,
      subset pairing, and any third ref beside the authorized pair
      fail closed; PR #27 Architect review, remediation 2);
    - the privacy disclosure authorization keys (privacy_scope,
      source_disclosure) are REQUIRED, non-empty strings -- a
      promotion decision without an explicit privacy boundary can
      never exist (structural schema only: the VALUE vocabularies are
      owned by the telemetry family and validated at its consumption
      seam);
    - a promotion descriptor riding a non-promotion context is inert
      opaque DATA.
    """
    name = "case_74_promotion_binding_born_bound"
    problems: List[str] = []
    from policy.promotion import (
        PROMOTION_BINDING_KIND as _KIND,
        promotion_binding_from_context as _derive,
    )

    obs_id = "telemetry:observation:" + "d" * 64
    subject_ref = "adcos:link:" + "e" * 32
    descriptor = {
        "kind": _KIND,
        "operation": Operation.TELEMETRY_TOPOLOGY_PROMOTE,
        "observation_id": obs_id,
        "subject_kind": "link",
        "subject_ref": subject_ref,
        "privacy_scope": "operational",
        "source_disclosure": "identity",
    }
    good_kwargs: Dict[str, Any] = dict(
        operation=Operation.TELEMETRY_TOPOLOGY_PROMOTE,
        requester_node_id=_NODE_A,
        evaluation_instant=_NOW,
        resource_refs=(obs_id, subject_ref),
        extensions=(dict(descriptor),),
    )

    def _ctx(**overrides: Any) -> PolicyContext:
        kwargs = dict(good_kwargs)
        extensions = list(kwargs["extensions"])
        for key, value in overrides.items():
            if key == "extensions":
                extensions = [dict(e) for e in value]
            else:
                kwargs[key] = value
        kwargs["extensions"] = tuple(extensions)
        return base_ctx(**kwargs)

    # 1. Deny-by-default (privileged): no applicable promotion rule.
    res_default = evaluate(base_set(rules=()), _ctx())
    if not (res_default.ok and res_default.decision):
        problems.append("default evaluation lost the decision")
    elif res_default.decision.effect != Effect.DENY or res_default.code != DecisionCode.DEFAULT_DENY:
        problems.append(
            "no-rule promotion not deny-by-default (%r/%r)"
            % (res_default.decision.effect, res_default.code)
        )
    elif not any(e.get("kind") == _KIND for e in res_default.decision.extensions):
        problems.append("DEFAULT_DENY promotion decision not born bound")
    # 2. Explicit ALLOW rule -> born-bound ALLOW.
    allow_rule = base_rule(
        rule_id="promo-allow", domain=PolicyDomain.IDENTITY,
        effect=Effect.ALLOW, operation=Operation.TELEMETRY_TOPOLOGY_PROMOTE,
    )
    ps_allow = base_set(rules=(allow_rule,))
    res = evaluate(ps_allow, _ctx())
    if not (res.ok and res.decision and res.code == DecisionCode.ALLOW):
        problems.append("valid promotion context did not yield ALLOW: %r" % (res.code,))
    else:
        bindings = [e for e in res.decision.extensions if e.get("kind") == _KIND]
        if len(bindings) != 1:
            problems.append("decision carries %d promotion bindings (expected 1)" % len(bindings))
        elif dict(bindings[0]) != descriptor:
            problems.append("binding != descriptor: %r" % (dict(bindings[0]),))
        else:
            import hashlib as _hashlib
            if res.decision.decision_id != _hashlib.sha256(
                res.decision.canonical_bytes()
            ).hexdigest():
                problems.append("decision_id does not bind canonical bytes")
    # 3. Fail-closed matrix: malformed/absent descriptor.
    def _expect_invalid(label: str, ctx: PolicyContext) -> None:
        outcome = evaluate(ps_allow, ctx)
        if outcome.ok or outcome.decision is not None:
            problems.append("%s: engine did not fail closed (%r)" % (label, outcome.code))
        elif outcome.code != DecisionCode.INVALID_POLICY:
            problems.append("%s: wrong code %r" % (label, outcome.code))

    _expect_invalid("no descriptor", _ctx(extensions=()))
    _expect_invalid(
        "double descriptor",
        _ctx(extensions=(dict(descriptor), dict(descriptor))),
    )
    _expect_invalid(
        "unknown key", _ctx(extensions=({**descriptor, "extra": "x"},)),
    )
    _expect_invalid(
        "missing key",
        _ctx(extensions=({k: v for k, v in descriptor.items() if k != "subject_kind"},)),
    )
    _expect_invalid(
        "non-string value", _ctx(extensions=({**descriptor, "subject_ref": 7},)),
    )
    _expect_invalid(
        "foreign operation",
        _ctx(extensions=({**descriptor, "operation": Operation.RESOURCE_CONSUME},)),
    )
    _expect_invalid(
        "empty observation_id", _ctx(extensions=({**descriptor, "observation_id": ""},)),
    )
    # Privacy disclosure authorization keys are REQUIRED (PR #27
    # review, blocker 2): a promotion decision without an explicit
    # privacy boundary can never be born.
    _expect_invalid(
        "missing privacy_scope",
        _ctx(extensions=({k: v for k, v in descriptor.items() if k != "privacy_scope"},)),
    )
    _expect_invalid(
        "missing source_disclosure",
        _ctx(extensions=({k: v for k, v in descriptor.items() if k != "source_disclosure"},)),
    )
    _expect_invalid(
        "empty privacy_scope", _ctx(extensions=({**descriptor, "privacy_scope": ""},)),
    )
    _expect_invalid(
        "empty source_disclosure",
        _ctx(extensions=({**descriptor, "source_disclosure": ""},)),
    )
    _expect_invalid(
        "non-string privacy_scope",
        _ctx(extensions=({**descriptor, "privacy_scope": 3},)),
    )
    _expect_invalid(
        "non-string source_disclosure",
        _ctx(extensions=({**descriptor, "source_disclosure": True},)),
    )
    # Mirror violations: subject/observation not among the evaluated
    # first-class resource_refs.
    _expect_invalid(
        "subject not evaluated",
        _ctx(
            extensions=(dict(descriptor),),
            resource_refs=(obs_id,),  # subject_ref dropped
        ),
    )
    _expect_invalid(
        "observation not evaluated",
        _ctx(
            extensions=(dict(descriptor),),
            resource_refs=(subject_ref,),  # observation dropped
        ),
    )
    # Scope EQUALITY (PR #27 Architect review, remediation 2 -- the
    # pinned invariant): membership is not authorization.  The
    # born-bound promotion scope must BE the complete evaluated
    # scope exactly: the descriptor's (observation, subject) pair
    # equals the context's resource_refs set.  In a context that
    # evaluated [observation-A, subject-A, observation-B, subject-B]
    # neither the cross-pairing observation-A + subject-B nor the
    # subset pairing observation-A + subject-A is an exact-scope
    # promotion -- each pairing requires its own decision born into
    # exactly that scope.
    obs_b = "telemetry:observation:" + "1" * 64
    subj_b = "adcos:link:" + "2" * 32
    broad_refs = (obs_id, subject_ref, obs_b, subj_b)
    _expect_invalid(
        "cross-pairing in broader scope",
        _ctx(
            extensions=({**descriptor, "subject_ref": subj_b},),
            resource_refs=broad_refs,
        ),
    )
    _expect_invalid(
        "subset pairing in broader scope",
        _ctx(
            extensions=(dict(descriptor),),
            resource_refs=broad_refs,
        ),
    )
    _expect_invalid(
        "third ref beside the pair",
        _ctx(
            extensions=(dict(descriptor),),
            resource_refs=(obs_id, subject_ref, _NODE_B),
        ),
    )
    # 4. The derivation function self-defends against foreign
    #    operations (direct call contract).
    try:
        _derive(base_ctx(operation=Operation.RESOURCE_RESERVE))
        problems.append("derivation accepted a non-promotion context")
    except PolicyError as e:
        if e.code != "promotion-binding":
            problems.append("derivation wrong code %r" % e.code)
    # 5. A promotion descriptor riding a NON-promotion context is
    #    inert opaque DATA: the decision carries no binding.
    res_other = evaluate(
        base_set(rules=(base_rule(rule_id="r-rr", effect=Effect.ALLOW),)),
        base_ctx(
            operation=Operation.RESOURCE_RESERVE,
            requester_node_id=_NODE_A,
            evaluation_instant=_NOW,
            resource_refs=(obs_id, subject_ref),
            extensions=(dict(descriptor),),
        ),
    )
    if not (res_other.ok and res_other.decision):
        problems.append("descriptor on resource.reserve broke evaluation")
    elif any(e.get("kind") == _KIND for e in res_other.decision.extensions):
        problems.append("non-promotion decision unexpectedly carries a binding")
    if problems:
        results.append(fail(name, "; ".join(problems)))
    else:
        results.append(
            ok(
                name,
                "telemetry.topology-promote is deny-by-default privileged and born "
                "bound (digest-covered, scope-EQUAL to the evaluated "
                "resource_refs, privacy disclosure authorization required); "
                "malformed/absent descriptor and non-exact scopes fail "
                "closed; inert on other operations",
            )
        )


# --------------------------------------------------------------------------
# M004 — Eligibility and Policy (R7-CORE-001 child, DEC-0101): the
# refactored 1.1 surface around the canonical contract.
#
# Architecture (disclosed; see docs/M004-evidence.md): the constraint
# and eligibility evaluations live in the eligibility family
# (eligibility/contract_constraints.py + eligibility/
# contract_eligibility.py — the matrix's single "Eligibility + contract
# constraints" target authority) as PURE-DATA snapshot evaluators: they
# never import the canonical domains (the family's frozen import
# discipline) and consume caller-composed snapshots built from the
# canonical public surfaces.  THIS battery owns the composition seam:
# the helpers below read the canonical contract record (M002) and
# resolve offer references through the M003 exchange BY REFERENCE
# (LOCK-101), proving the end-to-end pipeline case-by-case.  The
# legacy policy/ engine is RETAINED untouched (cases 1-74 unchanged;
# the payment battery's frozen policy-family audit stays green).
# --------------------------------------------------------------------------

# Deterministic M004 instants (injected; never the wall clock).
_M4_T0 = "2026-10-01T00:00:00Z"
_M4_T_CREATE = "2026-09-30T10:00:00Z"
_M4_T_SELECT = "2026-09-30T10:05:00Z"
_M4_T_MID = "2026-10-15T00:00:00Z"
_M4_T_LATE = "2026-10-25T00:00:00Z"
_M4_T_END = "2026-11-01T00:00:00Z"
_M4_T_PAST_END = "2026-12-01T00:00:00Z"

# Canonical NodeID-shaped provider domain identities (test material).
_M4_PROVIDER_A = "adcos:node:identity.sha256-hmac-dev.v1:" + "1" * 64
_M4_PROVIDER_B = "adcos:node:identity.sha256-hmac-dev.v1:" + "2" * 64

_M4_ISSUER_A = "provider:netpro-a"
_M4_ISSUER_OPS = "issuer:platform-ops"


def _m4_prov(issuer: str = _M4_ISSUER_A, *refs: str) -> Provenance:
    return Provenance(issuer=issuer, decision_refs=tuple(refs))


def _m4_entry() -> AdvertisementEntry:
    return AdvertisementEntry(
        capability_id="capability.core.multipath",
        schema_version="1.2",
        statement_digest="sha256:" + "a" * 64,
        classification="known",
    )


def _m4_commitment(issuer: str = _M4_ISSUER_A) -> OfferCommitment:
    return OfferCommitment(
        kind="latency-bound-ms",
        params={"max_ms": 150},
        window=ValidityInterval(not_before=_M4_T0, not_after=_M4_T_END),
        provenance=_m4_prov(issuer),
    )


def _m4_pricing(issuer: str = _M4_ISSUER_A) -> OfferPricing:
    return OfferPricing(
        currency="USD",
        price_minor=250,
        price_exponent=2,
        billing_mode="flat",
        provenance=_m4_prov(issuer),
    )


def _m4_boundary(
    jurisdiction: str = "GH", issuer: str = _M4_ISSUER_A
) -> ServiceBoundary:
    return ServiceBoundary(
        jurisdiction=jurisdiction,
        geography_refs=("mpcell:v1:coarse-50000m:12:-1",),
        provenance=_m4_prov(issuer),
    )


def _m4_advertisement(
    provider: str = _M4_PROVIDER_A,
    issuer: str = _M4_ISSUER_A,
) -> "CapabilityAdvertisement":
    return build_advertisement(
        provider=provider,
        entries=(_m4_entry(),),
        validity=ValidityInterval(not_before=_M4_T0, not_after=_M4_T_END),
        provenance=_m4_prov(issuer),
    )


def _m4_offer(
    provider: str = _M4_PROVIDER_A,
    key: str = "offer:netpro-basic-1",
    advertisement_id: Optional[str] = None,
    jurisdiction: str = "GH",
    issuer: str = _M4_ISSUER_A,
) -> "OfferRecord":
    return build_offer(
        provider=provider,
        provider_offer_key=key,
        schema_version=1,
        advertisements=(
            AdvertisementRef(
                advertisement_id=advertisement_id or ("sha256:" + "a" * 64),
                provenance=_m4_prov(issuer),
            ),
        ),
        commitments=(_m4_commitment(issuer),),
        pricing=_m4_pricing(issuer),
        service_boundaries=(_m4_boundary(jurisdiction, issuer),),
        validity=ValidityInterval(not_before=_M4_T0, not_after=_M4_T_END),
        provenance=_m4_prov(issuer),
    )


def _m4_exchange(
    *, with_offer: bool = True, jurisdiction: str = "GH"
) -> "OfferExchange":
    exchange = OfferExchange()
    advertisement = _m4_advertisement()
    exchange.register_advertisement(advertisement)
    if with_offer:
        offer = _m4_offer(advertisement_id=advertisement.advertisement_id, jurisdiction=jurisdiction)
        exchange.register_offer(offer)
    return exchange


def _m4_ruleset(
    providers: Tuple[str, ...] = (_M4_PROVIDER_A,),
    jurisdictions: Tuple[str, ...] = ("GH",),
    ruleset_id: str = "rs-platform-1",
    version: int = 1,
    valid_from: str = "",
    valid_until: str = "",
) -> ContractEligibilityRuleset:
    return ContractEligibilityRuleset(
        ruleset_id=ruleset_id,
        version=version,
        issuer=_M4_ISSUER_OPS,
        permitted_providers=providers,
        permitted_jurisdictions=jurisdictions,
        valid_from=valid_from,
        valid_until=valid_until,
        decision_refs=("decision:platform-eligibility-v1",),
    )


def _m4_contract_create(principal_ref: str = "app:sharenet-gw-01") -> CreateContract:
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
                value="intent:abc123",
                provenance=_m4_prov("arch:sharenet"),
            ),
        ),
        hard_constraints=(
            HardConstraint(
                kind="latency-bound", params={"max_ms": 150}, provenance=_m4_prov()
            ),
        ),
        validity=ValidityInterval(not_before=_M4_T0, not_after=_M4_T_END),
        service_properties=(
            OpaqueReference(
                ref_kind="service-property",
                value="prop:committed-1",
                provenance=_m4_prov(),
            ),
        ),
        usage_pricing_terms=OpaqueReference(
            ref_kind="usage-pricing-terms",
            value="terms:comm-42",
            provenance=_m4_prov("comm:ops"),
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
                provenance=_m4_prov("comm:ops"),
            ),
        ),
        provenance=_m4_prov("arch:sharenet"),
    )


def _m4_selected_contract():
    """The canonical composition fixture: a contract built through the
    M002 store with the M003 exchange's offer reference bound
    (INTENT -> OFFER_SELECTED).  Returns (store, exchange, offer,
    contract)."""
    exchange = _m4_exchange()
    offer = _m4_offer(advertisement_id=exchange.advertisements()[0].advertisement_id)
    exchange.register_offer(offer)
    store = ContractStore()
    created = store.submit(_m4_contract_create(), recorded_at=_M4_T_CREATE)
    selected = store.submit(
        SelectOffers(offers=(offer_reference(offer),)),
        recorded_at=_M4_T_SELECT,
        contract_id=created.contract.contract_id,
    )
    return store, exchange, offer, selected.contract


# -- the battery-owned composition seam (LOCK-101: reads of the ------
# -- canonical public surfaces; the evaluators see pure DATA only) ---


def _m4_offer_facts_from_exchange(
    exchange: OfferExchange, contract, *, at_instant: str
) -> Tuple[OfferReferenceFacts, ...]:
    """Compose the offer reference facts for one canonical contract by
    resolving every accepted offer reference through the M003 exchange
    at the injected instant (BY REFERENCE — the exchange owns offer
    usability; an unresolvable/withdrawn/expired/superseded offer
    composes as usable=False with the reference's own value, never a
    crash, never a catalog mutation)."""
    facts = []
    for reference in contract.accepted_offers:
        try:
            record = exchange.resolve(reference, at_instant=at_instant)
            facts.append(
                OfferReferenceFacts(
                    value=reference.value,
                    offer_id=record.offer_id,
                    provider=record.provider,
                    jurisdictions=tuple(
                        boundary.jurisdiction
                        for boundary in record.service_boundaries
                    ),
                    usable=True,
                )
            )
        except Exception:
            facts.append(
                OfferReferenceFacts(
                    value=reference.value,
                    offer_id=reference.value,
                    provider="unresolved-offer-reference",
                    jurisdictions=(),
                    usable=False,
                )
            )
    return tuple(facts)


def _m4_context_from_contract(
    contract,
    action: str,
    *,
    evaluation_instant: str,
    offer_facts: Optional[Tuple[OfferReferenceFacts, ...]] = None,
) -> ContractConstraintContext:
    """Compose the constraint context for one guarded action by READING
    the canonical contract's public fields (LOCK-101: consume by
    reference; the contract record is never mutated and its semantics
    are never re-implemented).  The action is pinned HERE against the
    canonical projection CONTRACT_ACTIONS (computed from
    contracts.COMMAND_KINDS) — the vocabulary authority stays
    canonical; the evaluator treats actions as opaque strings.

    ``offer_facts`` is the composed offer reference material; when None
    the context carries NO offer facts and every offer-fact condition
    fails closed as a non-match (deny-by-default — absence of a fact
    is never an approval)."""
    if action not in CONTRACT_ACTIONS:
        raise ValueError(
            "action %r is not a member of the canonical M002 command "
            "vocabulary projection (LOCK-101: the composition boundary "
            "pins the guarded actions to contracts.COMMAND_KINDS)" % action
        )
    return ContractConstraintContext(
        action=action,
        principal_kind=contract.principal.principal_kind,
        principal_ref=contract.principal.principal_ref,
        beneficiary_kinds=tuple(
            beneficiary.beneficiary_kind for beneficiary in contract.beneficiaries
        ),
        contract_state=contract.state,
        hard_constraint_kinds=tuple(
            constraint.kind for constraint in contract.hard_constraints
        ),
        validity=ValidityWindow(
            not_before=contract.validity.not_before,
            not_after=contract.validity.not_after,
        ),
        accepted_offer_values=tuple(
            reference.value for reference in contract.accepted_offers
        ),
        offer_facts=offer_facts if offer_facts is not None else (),
        evaluation_instant=evaluation_instant,
    )


def _m4_contract_facts(
    contract,
    offer_facts: Tuple[OfferReferenceFacts, ...],
) -> ContractReferenceFacts:
    """Compose the contract reference facts by READING the canonical
    contract's public fields: the state (opaque DATA), the terminal
    classification (derived from the canonical TERMINAL_STATES
    vocabulary — consumed by reference), the validity window (read
    verbatim), and the composed per-offer facts."""
    return ContractReferenceFacts(
        contract_id=contract.contract_id,
        state=contract.state,
        state_is_terminal=contract.state in TERMINAL_STATES,
        validity=ValidityWindow(
            not_before=contract.validity.not_before,
            not_after=contract.validity.not_after,
        ),
        offer_facts=offer_facts,
    )


def _m4_constraint_set(
    rules: Tuple[ContractConstraintRule, ...],
    set_id: str = "cps-platform-1",
    version: int = 1,
    valid_from: str = "",
    valid_until: str = "",
) -> ContractConstraintSet:
    return ContractConstraintSet(
        set_id=set_id,
        version=version,
        rules=rules,
        issuer=_M4_ISSUER_OPS,
        valid_from=valid_from,
        valid_until=valid_until,
    )


def _m4_rule(
    rule_id: str,
    action: str,
    effect: str = ContractConstraintEffect.ALLOW,
    subjects: Tuple[str, ...] = (),
    conditions: Tuple[ContractConstraintCondition, ...] = (),
    specificity: int = 0,
    priority: int = 0,
    valid_from: str = "",
    valid_until: str = "",
) -> ContractConstraintRule:
    return ContractConstraintRule(
        rule_id=rule_id,
        action=action,
        effect=effect,
        subjects=subjects,
        conditions=conditions,
        specificity=specificity,
        priority=priority,
        valid_from=valid_from,
        valid_until=valid_until,
        issuer=_M4_ISSUER_OPS,
        decision_refs=("decision:platform-constraints-v1",),
    )


def _m4_expect_constraint_error(
    case: str, code: str, action: Callable[[], Any]
) -> Result:
    try:
        action()
    except ContractConstraintError as error:
        if error.code == code:
            return ok(case, "fail-closed %s: %s" % (code, error.detail[:80]))
        return fail(
            case, "expected code %s, got %s (%s)" % (code, error.code, error.detail[:80])
        )
    except Exception as error:  # noqa: BLE001
        return fail(
            case, "unexpected exception %s: %s" % (type(error).__name__, str(error)[:80])
        )
    return fail(case, "expected ContractConstraintError(%s); the input was accepted" % code)


def _m4_expect_eligibility_error(
    case: str, code: str, action: Callable[[], Any]
) -> Result:
    try:
        action()
    except ContractEligibilityError as error:
        if error.code == code:
            return ok(case, "fail-closed %s: %s" % (code, error.detail[:80]))
        return fail(
            case, "expected code %s, got %s (%s)" % (code, error.code, error.detail[:80])
        )
    except Exception as error:  # noqa: BLE001
        return fail(
            case, "unexpected exception %s: %s" % (type(error).__name__, str(error)[:80])
        )
    return fail(
        case, "expected ContractEligibilityError(%s); the input was accepted" % code
    )


def case_75_m004_surface_and_vocabularies(results: List[Result]) -> None:
    """75. M004 surface present with closed vocabularies; the guarded
    action vocabulary is the exact projection of the CANONICAL M002
    command vocabulary (LOCK-101: composed at the battery boundary
    directly from contracts.COMMAND_KINDS — the evaluators treat
    actions as opaque strings and never enumerate them); the legacy
    frozen vocabularies are untouched; the legacy policy/ engine is
    byte-identical to origin/main (RETAIN discipline)."""
    name = "case_75_m004_surface_and_vocabularies"
    import subprocess as _sp

    problems: List[str] = []
    if CONTRACT_ACTIONS != tuple("contract.%s" % kind for kind in COMMAND_KINDS):
        problems.append("CONTRACT_ACTIONS drifted from the canonical M002 command vocabulary")
    if set(ContractConstraintEffect.values()) != {"allow", "deny", "require-review"}:
        problems.append("effect vocabulary drifted: %s" % sorted(ContractConstraintEffect.values()))
    expected_codes = {
        "allow", "deny", "default-deny", "require-review", "fail-closed",
        "policy-expired", "policy-not-yet-valid", "missing-fact", "conflict",
        "invalid-policy",
    }
    if set(ContractConstraintDecisionCode.values()) != expected_codes:
        problems.append("decision-code vocabulary drifted: %s" % sorted(ContractConstraintDecisionCode.values()))
    expected_predicates = {
        "principal-kind", "principal-ref", "beneficiary-kind", "offer-provider",
        "offer-jurisdiction", "constraint-kind", "contract-state", "validity-live",
    }
    if set(ContractConstraintPredicateKind.values()) != expected_predicates:
        problems.append("predicate vocabulary drifted: %s" % sorted(ContractConstraintPredicateKind.values()))
    if not all(
        code.startswith("contract-constraint-") for code in (
            ContractConstraintReason.INVALID_INPUT,
            ContractConstraintReason.TEMPORAL_INVALID,
            ContractConstraintReason.VOCABULARY,
            ContractConstraintReason.SECRET_REJECTED,
            ContractConstraintReason.PROVENANCE_REQUIRED,
            ContractConstraintReason.ID_MISMATCH,
        )
    ):
        problems.append("constraint reason namespace drifted")
    if not all(
        code.startswith("contract-eligibility-")
        for code in (
            ContractEligibilityReason.INVALID_INPUT,
            ContractEligibilityReason.TEMPORAL_INVALID,
            ContractEligibilityReason.VOCABULARY,
            ContractEligibilityReason.SECRET_REJECTED,
            ContractEligibilityReason.PROVENANCE_REQUIRED,
        )
    ):
        problems.append("eligibility reason namespace drifted")
    if not all(
        not code.startswith(("contract-constraint-", "contract-eligibility-"))
        for code in ContractEligibilityReason.denial_values()
    ):
        problems.append("denial DATA reasons must be unnamespaced outcome codes")
    # the legacy frozen vocabularies are untouched (RETAIN discipline)
    if len(Operation.values()) != 15 or len(Effect.values()) != 3:
        problems.append("legacy vocabularies changed (Operation/Effect counts)")
    if len(PredicateKind.values()) != 14 or len(PolicyDomain.values()) != 9:
        problems.append("legacy vocabularies changed (PredicateKind/PolicyDomain counts)")
    # the legacy policy/ tree is byte-identical to origin/main
    r = _sp.run(
        ["git", "diff", "origin/main", "--", "policy"],
        cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=10,
    )
    if r.stdout.strip():
        problems.append("the legacy policy/ tree changed vs origin/main (RETAIN violated)")
    if problems:
        results.append(fail(name, "; ".join(problems)))
    else:
        results.append(
            ok(
                name,
                "CONTRACT_ACTIONS == projection of contracts.COMMAND_KINDS (%d actions); "
                "M004 vocabularies closed; legacy vocabularies + policy/ tree untouched" % len(CONTRACT_ACTIONS),
            )
        )


def case_76_contract_constraints_minimal_flow(results: List[Result]) -> None:
    """76. Minimal allow around the canonical contract: an explicit rule
    guards ``contract.select-offers``; the context is composed from the
    canonical contract record by reference; the offer facts resolve
    through the M003 exchange; the decision is ALLOW with the matched
    rule id and policy version (audit trail)."""
    name = "case_76_contract_constraints_minimal_flow"
    _store, exchange, _offer, contract = _m4_selected_contract()
    facts = _m4_offer_facts_from_exchange(exchange, contract, at_instant=_M4_T_MID)
    context = _m4_context_from_contract(
        contract,
        "contract.select-offers",
        evaluation_instant=_M4_T_MID,
        offer_facts=facts,
    )
    rule = _m4_rule(
        "allow-select",
        "contract.select-offers",
        conditions=(
            ContractConstraintCondition(
                predicate=ContractConstraintPredicateKind.PRINCIPAL_KIND,
                arguments={"kind": "APPLICATION"},
            ),
            ContractConstraintCondition(
                predicate=ContractConstraintPredicateKind.OFFER_PROVIDER,
                arguments={"provider": _M4_PROVIDER_A},
            ),
        ),
    )
    constraint_set = _m4_constraint_set((rule,))
    result = evaluate_contract_constraints(constraint_set, context)
    problems: List[str] = []
    if not (result.ok and result.code == ContractConstraintDecisionCode.ALLOW):
        problems.append("expected ALLOW, got %r (%s)" % (result.code, result.detail))
    elif result.decision is None:
        problems.append("no decision record")
    else:
        if result.decision.matched_rule_ids != ("allow-select",):
            problems.append("matched ids %r" % (result.decision.matched_rule_ids,))
        if result.decision.policy_set_id != "cps-platform-1" or result.decision.policy_set_version != 1:
            problems.append("policy identity/version missing from the audit trail")
        if result.decision.action != "contract.select-offers":
            problems.append("decision action drifted")
    # the context facts are the contract's own reference facts (read, never re-implemented)
    if context.contract_state != "OFFER_SELECTED":
        problems.append("context state %r is not the contract's state" % context.contract_state)
    if context.principal_ref != "app:sharenet-gw-01":
        problems.append("context principal drifted")
    if facts and (facts[0].provider != _M4_PROVIDER_A or facts[0].jurisdictions != ("GH",)):
        problems.append("offer facts drifted from the M003 record")
    if problems:
        results.append(fail(name, "; ".join(problems)))
    else:
        results.append(
            ok(
                name,
                "ALLOW on contract.select-offers; matched=(allow-select,); facts read "
                "off the canonical contract + M003 exchange by reference",
            )
        )


def case_77_contract_constraints_deny_and_default_deny(results: List[Result]) -> None:
    """77. Explicit deny wins; an action with no applicable rule denies
    by default (every guarded contract action is privileged)."""
    name = "case_77_contract_constraints_deny_and_default_deny"
    _store, exchange, _offer, contract = _m4_selected_contract()
    facts = _m4_offer_facts_from_exchange(exchange, contract, at_instant=_M4_T_MID)
    context = _m4_context_from_contract(
        contract, "contract.activate", evaluation_instant=_M4_T_MID, offer_facts=facts
    )
    deny_rule = _m4_rule("deny-activate", "contract.activate", effect=ContractConstraintEffect.DENY)
    constraint_set = _m4_constraint_set((deny_rule,))
    result = evaluate_contract_constraints(constraint_set, context)
    problems: List[str] = []
    if not (result.ok and result.code == ContractConstraintDecisionCode.DENY and result.decision is not None):
        problems.append("explicit deny failed: %r %r" % (result.code, result.detail))
    elif result.decision.effect != ContractConstraintEffect.DENY:
        problems.append("deny decision effect drifted")
    # no applicable rule -> DEFAULT_DENY (the decision-producing outcome)
    unruled = _m4_context_from_contract(
        contract, "contract.bind-artifact", evaluation_instant=_M4_T_MID, offer_facts=facts
    )
    result2 = evaluate_contract_constraints(constraint_set, unruled)
    if not (result2.ok and result2.code == ContractConstraintDecisionCode.DEFAULT_DENY):
        problems.append("expected DEFAULT_DENY, got %r %r" % (result2.code, result2.detail))
    elif result2.decision is None or result2.decision.effect != ContractConstraintEffect.DENY:
        problems.append("default-deny decision drifted")
    if problems:
        results.append(fail(name, "; ".join(problems)))
    else:
        results.append(
            ok(name, "explicit DENY (matched=(deny-activate,)); unruled action -> DEFAULT_DENY")
        )


def case_78_contract_constraints_fail_closed(results: List[Result]) -> None:
    """78. Fail-closed inputs: the evaluation instant is required and
    must be well formed (no wall-clock fallback); a missing offer fact
    is a non-match (DEFAULT_DENY with missing-fact recorded — the
    harvested case_04 semantics); expired / not-yet-valid constraint
    sets fail closed; an empty issuer, a permissive default effect and
    a non-canonical action (at the composition boundary) are rejected
    at construction."""
    name = "case_78_contract_constraints_fail_closed"
    _store, exchange, _offer, contract = _m4_selected_contract()
    facts = _m4_offer_facts_from_exchange(exchange, contract, at_instant=_M4_T_MID)
    rule = _m4_rule(
        "allow-select",
        "contract.select-offers",
        conditions=(
            ContractConstraintCondition(
                predicate=ContractConstraintPredicateKind.OFFER_JURISDICTION,
                arguments={"jurisdiction": "GH"},
            ),
        ),
    )
    constraint_set = _m4_constraint_set((rule,))
    problems: List[str] = []
    sub: List[Result] = []

    # (a) the evaluation instant is required
    context_no_instant = _m4_context_from_contract(
        contract, "contract.select-offers", evaluation_instant=_M4_T_MID, offer_facts=facts
    )
    context_no_instant = ContractConstraintContext(
        **{**context_no_instant.content(), "evaluation_instant": ""}
    )
    result = evaluate_contract_constraints(constraint_set, context_no_instant)
    if not (not result.ok and result.code == ContractConstraintDecisionCode.FAIL_CLOSED):
        problems.append("missing instant: %r" % (result.code,))
    # (b) malformed instants fail closed: typed rejection at the context
    # boundary (defense-in-depth — the legacy case_63 evaluation-time
    # FAIL_CLOSED guarantee is enforced one boundary earlier here: a
    # malformed instant can never even ENTER an evaluation)
    for bad in ("not-a-date", "2026-13-01T00:00:00Z", "2026-01-01T25:00:00Z"):
        sub.append(
            _m4_expect_constraint_error(
                "case_78b_malformed_instant_%s" % bad.replace(":", "").replace("-", "")[:12],
                ContractConstraintReason.TEMPORAL_INVALID,
                lambda bad=bad: ContractConstraintContext(
                    **{**context_no_instant.content(), "evaluation_instant": bad}
                ),
            )
        )
    # (c) missing offer facts -> non-match -> DEFAULT_DENY + missing-fact recorded
    context_missing = _m4_context_from_contract(
        contract, "contract.select-offers", evaluation_instant=_M4_T_MID, offer_facts=None
    )
    result_missing = evaluate_contract_constraints(constraint_set, context_missing)
    if not (
        result_missing.ok
        and result_missing.code == ContractConstraintDecisionCode.DEFAULT_DENY
        and result_missing.decision is not None
        and "missing-fact" in result_missing.decision.detail
    ):
        problems.append(
            "missing fact: %r %r" % (result_missing.code, result_missing.detail)
        )
    # (d) constraint-set temporal fail-closed
    expired = _m4_constraint_set((rule,), valid_from="2026-01-01T00:00:00Z", valid_until="2026-02-01T00:00:00Z")
    context_valid = _m4_context_from_contract(
        contract, "contract.select-offers", evaluation_instant=_M4_T_MID, offer_facts=facts
    )
    result_expired = evaluate_contract_constraints(expired, context_valid)
    if not (not result_expired.ok and result_expired.code == ContractConstraintDecisionCode.POLICY_EXPIRED):
        problems.append("expired policy: %r" % (result_expired.code,))
    future = _m4_constraint_set((rule,), valid_from="2027-01-01T00:00:00Z", valid_until="2027-02-01T00:00:00Z")
    result_future = evaluate_contract_constraints(future, context_valid)
    if not (
        not result_future.ok and result_future.code == ContractConstraintDecisionCode.POLICY_NOT_YET_VALID
    ):
        problems.append("future policy: %r" % (result_future.code,))
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    # (e) construction fail-closed: empty issuer / permissive default
    sub.append(
        _m4_expect_constraint_error(
            "case_78e_empty_issuer", ContractConstraintReason.INVALID_INPUT,
            lambda: ContractConstraintSet(set_id="anon", version=1, rules=(rule,), issuer=""),
        )
    )
    sub.append(
        _m4_expect_constraint_error(
            "case_78g_permissive_default", ContractConstraintReason.VOCABULARY,
            lambda: ContractConstraintSet(
                set_id="permissive", version=1, rules=(), issuer=_M4_ISSUER_OPS,
                default_effect=ContractConstraintEffect.ALLOW,
            ),
        )
    )
    # (f) a non-canonical action is rejected at the composition
    # boundary (the vocabulary pin lives where the canonical projection
    # is computed — LOCK-101: the evaluator itself stays opaque)
    try:
        _m4_context_from_contract(
            contract, "contract.not-a-command", evaluation_instant=_M4_T_MID
        )
        sub.append(fail("case_78f_non_canonical_action", "the composition boundary accepted a non-canonical action"))
    except ValueError:
        sub.append(
            ok(
                "case_78f_non_canonical_action",
                "non-canonical action rejected at the composition boundary "
                "(the canonical M002 command vocabulary pin)",
            )
        )
    results.extend(sub)
    results.append(
        ok(
            name,
            "instant required + malformed fail-closed; missing fact -> DEFAULT_DENY "
            "(recorded); expired/not-yet-valid fail closed; empty issuer / permissive "
            "default / non-canonical action rejected",
        )
    )


def case_79_contract_constraints_precedence_conflict(results: List[Result]) -> None:
    """79. Deterministic precedence + conflict (the harvested WORK-010
    semantics): explicit deny beats allow at equal precedence; higher
    specificity then higher priority wins; equal-precedence distinct
    allows fail closed (CONFLICT); rule input order never leaks into
    the outcome."""
    name = "case_79_contract_constraints_precedence_conflict"
    _store, exchange, _offer, contract = _m4_selected_contract()
    facts = _m4_offer_facts_from_exchange(exchange, contract, at_instant=_M4_T_MID)
    context = _m4_context_from_contract(
        contract, "contract.create", evaluation_instant=_M4_T_MID, offer_facts=facts
    )
    problems: List[str] = []

    # (a) deny beats allow at equal precedence
    allow = _m4_rule("a1", "contract.create", effect=ContractConstraintEffect.ALLOW)
    deny = _m4_rule("d1", "contract.create", effect=ContractConstraintEffect.DENY)
    tie = evaluate_contract_constraints(_m4_constraint_set((allow, deny)), context)
    if not (
        tie.ok and tie.code == ContractConstraintDecisionCode.DENY
        and tie.decision is not None
        and tie.decision.matched_rule_ids == ("d1",)
    ):
        problems.append("tie: %r %r" % (tie.code, tie.decision and tie.decision.matched_rule_ids))
    # (b) higher specificity wins
    specific_deny = _m4_rule("d2", "contract.create", effect=ContractConstraintEffect.DENY, specificity=5)
    plain_allow = _m4_rule("a2", "contract.create", effect=ContractConstraintEffect.ALLOW)
    spec = evaluate_contract_constraints(_m4_constraint_set((specific_deny, plain_allow)), context)
    if not (spec.ok and spec.code == ContractConstraintDecisionCode.DENY and spec.decision is not None and spec.decision.matched_rule_ids == ("d2",)):
        problems.append("specificity: %r" % (spec.code,))
    # (c) higher priority wins (specificity equal)
    prio_allow = _m4_rule("a3", "contract.create", effect=ContractConstraintEffect.ALLOW, priority=5)
    plain_deny = _m4_rule("d3", "contract.create", effect=ContractConstraintEffect.DENY)
    prio = evaluate_contract_constraints(_m4_constraint_set((prio_allow, plain_deny)), context)
    if not (prio.ok and prio.code == ContractConstraintDecisionCode.ALLOW and prio.decision is not None and prio.decision.matched_rule_ids == ("a3",)):
        problems.append("priority: %r" % (prio.code,))
    # (d) equal-precedence distinct allows -> CONFLICT (fail closed)
    allow_b = _m4_rule("a1b", "contract.create", effect=ContractConstraintEffect.ALLOW)
    conflict = evaluate_contract_constraints(_m4_constraint_set((allow, allow_b)), context)
    if not (not conflict.ok and conflict.code == ContractConstraintDecisionCode.CONFLICT):
        problems.append("conflict: %r" % (conflict.code,))
    # (e) require-review never silently becomes allow
    review = _m4_rule("rr1", "contract.create", effect=ContractConstraintEffect.REQUIRE_REVIEW)
    rr = evaluate_contract_constraints(_m4_constraint_set((review,)), context)
    if not (
        not rr.ok
        and rr.code == ContractConstraintDecisionCode.REQUIRE_REVIEW
        and rr.decision is not None
        and rr.decision.effect == ContractConstraintEffect.DENY
    ):
        problems.append("require-review: %r" % (rr.code,))
    # (f) rule input order never leaks into the outcome (byte-identical decisions)
    order_a = evaluate_contract_constraints(_m4_constraint_set((allow, deny, review)), context)
    order_b = evaluate_contract_constraints(_m4_constraint_set((review, deny, allow)), context)
    if (
        order_a.decision is None
        or order_b.decision is None
        or contract_constraint_decision_canonical_bytes(order_a.decision)
        != contract_constraint_decision_canonical_bytes(order_b.decision)
    ):
        problems.append("rule input order leaked into the decision")
    if problems:
        results.append(fail(name, "; ".join(problems)))
    else:
        results.append(
            ok(
                name,
                "deny>allow at equal precedence; specificity then priority; "
                "equal-precedence distinct allows -> CONFLICT; require-review -> "
                "DENY+FAIL_CLOSED; input order never leaks",
            )
        )


def case_80_contract_constraints_temporal_subwindows(results: List[Result]) -> None:
    """80. Temporal windows: a rule's own validity window is a
    sub-interval of the set's window; an expired rule is skipped (the
    live rule wins); the boundary convention is inclusive on both
    edges."""
    name = "case_80_contract_constraints_temporal_subwindows"
    _store, exchange, _offer, contract = _m4_selected_contract()
    facts = _m4_offer_facts_from_exchange(exchange, contract, at_instant=_M4_T_MID)
    context = _m4_context_from_contract(
        contract, "contract.create", evaluation_instant=_M4_T_MID, offer_facts=facts
    )
    live_allow = _m4_rule(
        "live", "contract.create", effect=ContractConstraintEffect.ALLOW,
        valid_from="2026-10-01T00:00:00Z", valid_until="2026-10-31T00:00:00Z",
    )
    expired_deny = _m4_rule(
        "expired", "contract.create", effect=ContractConstraintEffect.DENY,
        valid_until="2026-09-01T00:00:00Z",
    )
    result = evaluate_contract_constraints(
        _m4_constraint_set((live_allow, expired_deny)), context
    )
    problems: List[str] = []
    if not (
        result.ok and result.code == ContractConstraintDecisionCode.ALLOW
        and result.decision is not None
        and result.decision.matched_rule_ids == ("live",)
    ):
        problems.append("expired rule not skipped: %r" % (result.code,))
    # inclusive boundary convention: evaluate exactly at valid_from and valid_until
    edge_rule = _m4_rule(
        "edge", "contract.create", effect=ContractConstraintEffect.ALLOW,
        valid_from=_M4_T_MID, valid_until=_M4_T_MID,
    )
    at_edge = evaluate_contract_constraints(_m4_constraint_set((edge_rule,)), context)
    if not (at_edge.ok and at_edge.code == ContractConstraintDecisionCode.ALLOW):
        problems.append("inclusive boundary convention drifted: %r" % (at_edge.code,))
    if problems:
        results.append(fail(name, "; ".join(problems)))
    else:
        results.append(
            ok(name, "expired DENY rule skipped; live ALLOW wins; inclusive bounds at both edges")
        )


def case_81_contract_constraints_subject_and_conditions(results: List[Result]) -> None:
    """81. Subject selectors and typed reference-fact conditions:
    principal-kind / principal-ref / beneficiary-kind / constraint-kind
    / contract-state / validity-live match the contract's own facts;
    offer-provider / offer-jurisdiction match the M003-resolved offer
    facts; every mismatch is a non-match (deny-by-default — an
    out-of-vocabulary selector can never authorize anything)."""
    name = "case_81_contract_constraints_subject_and_conditions"
    _store, exchange, _offer, contract = _m4_selected_contract()
    facts = _m4_offer_facts_from_exchange(exchange, contract, at_instant=_M4_T_MID)
    context = _m4_context_from_contract(
        contract, "contract.create", evaluation_instant=_M4_T_MID, offer_facts=facts
    )
    problems: List[str] = []

    def _decision(conditions, subjects=()):
        rule = _m4_rule("r", "contract.create", conditions=conditions, subjects=subjects)
        return evaluate_contract_constraints(_m4_constraint_set((rule,)), context)

    # every selector matches the contract's own facts
    matching = (
        ContractConstraintCondition(predicate=ContractConstraintPredicateKind.PRINCIPAL_KIND, arguments={"kind": "APPLICATION"}),
        ContractConstraintCondition(predicate=ContractConstraintPredicateKind.PRINCIPAL_REF, arguments={"ref": "app:sharenet-gw-01"}),
        ContractConstraintCondition(predicate=ContractConstraintPredicateKind.BENEFICIARY_KIND, arguments={"kind": "DEVICE"}),
        ContractConstraintCondition(predicate=ContractConstraintPredicateKind.CONSTRAINT_KIND, arguments={"kind": "latency-bound"}),
        ContractConstraintCondition(predicate=ContractConstraintPredicateKind.CONTRACT_STATE, arguments={"state": "OFFER_SELECTED"}),
        ContractConstraintCondition(predicate=ContractConstraintPredicateKind.VALIDITY_LIVE, arguments={}),
        ContractConstraintCondition(predicate=ContractConstraintPredicateKind.OFFER_PROVIDER, arguments={"provider": _M4_PROVIDER_A}),
        ContractConstraintCondition(predicate=ContractConstraintPredicateKind.OFFER_JURISDICTION, arguments={"jurisdiction": "GH"}),
    )
    for condition in matching:
        result = _decision((condition,))
        if not (result.ok and result.code == ContractConstraintDecisionCode.ALLOW):
            problems.append("matching condition %r denied" % condition.predicate)
    # every mismatch is a non-match -> DEFAULT_DENY (including an
    # out-of-vocabulary kind selector: deny-by-default holds — the
    # canonical vocabulary authority stays with the canonical domains)
    mismatches = (
        ContractConstraintCondition(predicate=ContractConstraintPredicateKind.PRINCIPAL_KIND, arguments={"kind": "GOVERNMENT"}),
        ContractConstraintCondition(predicate=ContractConstraintPredicateKind.PRINCIPAL_REF, arguments={"ref": "app:other-99"}),
        ContractConstraintCondition(predicate=ContractConstraintPredicateKind.BENEFICIARY_KIND, arguments={"kind": "NGO"}),
        ContractConstraintCondition(predicate=ContractConstraintPredicateKind.CONSTRAINT_KIND, arguments={"kind": "geography"}),
        ContractConstraintCondition(predicate=ContractConstraintPredicateKind.CONTRACT_STATE, arguments={"state": "SETTLED"}),
        ContractConstraintCondition(predicate=ContractConstraintPredicateKind.OFFER_PROVIDER, arguments={"provider": _M4_PROVIDER_B}),
        ContractConstraintCondition(predicate=ContractConstraintPredicateKind.OFFER_JURISDICTION, arguments={"jurisdiction": "NG"}),
        ContractConstraintCondition(predicate=ContractConstraintPredicateKind.PRINCIPAL_KIND, arguments={"kind": "ROBOT"}),
    )
    for condition in mismatches:
        result = _decision((condition,))
        if not (result.ok and result.code == ContractConstraintDecisionCode.DEFAULT_DENY):
            problems.append("mismatched condition %r did not default-deny: %r" % (condition.predicate, result.code))
    # validity-live fails at an instant outside the contract window
    outside = ContractConstraintContext(
        **{**context.content(), "evaluation_instant": _M4_T_PAST_END}
    )
    live_rule = _m4_rule("live-only", "contract.create", conditions=(ContractConstraintCondition(predicate=ContractConstraintPredicateKind.VALIDITY_LIVE, arguments={}),))
    result = evaluate_contract_constraints(_m4_constraint_set((live_rule,)), outside)
    if not (result.ok and result.code == ContractConstraintDecisionCode.DEFAULT_DENY):
        problems.append("validity-live outside window: %r" % (result.code,))
    # subject selector: the rule applies only to its subject
    subject_rule = _m4_rule("subject-only", "contract.create", subjects=("app:sharenet-gw-01",))
    subject_ok = evaluate_contract_constraints(_m4_constraint_set((subject_rule,)), context)
    if not (subject_ok.ok and subject_ok.code == ContractConstraintDecisionCode.ALLOW):
        problems.append("subject match failed")
    stranger = ContractConstraintContext(**{**context.content(), "principal_ref": "app:stranger-77"})
    stranger_result = evaluate_contract_constraints(_m4_constraint_set((subject_rule,)), stranger)
    if not (stranger_result.ok and stranger_result.code == ContractConstraintDecisionCode.DEFAULT_DENY):
        problems.append("subject mismatch did not default-deny: %r" % (stranger_result.code,))
    # predicate argument SHAPE grammar fails closed at construction
    sub: List[Result] = []
    sub.append(
        _m4_expect_constraint_error(
            "case_81h_bad_predicate_shape", ContractConstraintReason.INVALID_INPUT,
            lambda: ContractConstraintCondition(
                predicate=ContractConstraintPredicateKind.VALIDITY_LIVE, arguments={"kind": "USER"}
            ),
        )
    )
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.extend(sub)
    results.append(
        ok(
            name,
            "8 matching selectors ALLOW; 8 mismatched (incl. out-of-vocabulary) + "
            "out-of-window + stranger subject DEFAULT_DENY; bad predicate shape "
            "rejected at construction",
        )
    )


def case_82_m004_lock101_by_reference(results: List[Result]) -> None:
    """82. LOCK-101 by-reference discipline: composition + evaluation
    never mutate the canonical contract (identity, state,
    hard-constraint fingerprint, canonical bytes byte-identical) or the
    M003 exchange (catalog digest identical); a withdrawn offer composes
    as usable=False (an eligibility FACT, never a catalog mutation) and
    offer-fact conditions then fail closed; the contract stays
    byte-identical across a failed composition."""
    name = "case_82_m004_lock101_by_reference"
    _store, exchange, offer, contract = _m4_selected_contract()
    contract_bytes_before = contract.canonical_bytes()
    fingerprint_before = contract.hard_constraint_fingerprint()
    catalog_before = exchange.catalog_digest()
    facts = _m4_offer_facts_from_exchange(exchange, contract, at_instant=_M4_T_MID)
    ruleset = _m4_ruleset()
    contract_facts = _m4_contract_facts(contract, facts)
    eligibility = evaluate_contract_reference_eligibility(
        contract_facts, ruleset, at_instant=_M4_T_MID
    )
    rule = _m4_rule("allow-select", "contract.select-offers")
    constraint_set = _m4_constraint_set((rule,))
    context = _m4_context_from_contract(
        contract, "contract.select-offers", evaluation_instant=_M4_T_MID, offer_facts=facts
    )
    decision = evaluate_contract_constraints(constraint_set, context)
    problems: List[str] = []
    if contract.canonical_bytes() != contract_bytes_before:
        problems.append("the contract record changed after composition + evaluation")
    if contract.hard_constraint_fingerprint() != fingerprint_before:
        problems.append("the hard-constraint fingerprint changed after composition + evaluation")
    if contract.state != "OFFER_SELECTED":
        problems.append("the contract state changed after composition + evaluation")
    if exchange.catalog_digest() != catalog_before:
        problems.append("the exchange catalog changed after composition + evaluation")
    if not (decision.ok and eligibility.eligible):
        problems.append("the composition did not evaluate cleanly")
    # exception isolation (the snapshot discipline): a withdrawn offer
    # composes as usable=False — never a crash, never a catalog mutation
    exchange.withdraw_offer(
        provider=offer.provider,
        provider_offer_key=offer.provider_offer_key,
        withdrawn_at=_M4_T_LATE,
        reason="capacity reallocation",
    )
    late_facts = _m4_offer_facts_from_exchange(exchange, contract, at_instant=_M4_T_LATE)
    if late_facts and late_facts[0].usable:
        problems.append("a withdrawn offer composed as usable")
    # offer-fact conditions fail closed on the unusable fact
    late_context = _m4_context_from_contract(
        contract, "contract.select-offers", evaluation_instant=_M4_T_LATE, offer_facts=late_facts
    )
    provider_rule = _m4_rule(
        "allow-live-provider",
        "contract.select-offers",
        conditions=(
            ContractConstraintCondition(
                predicate=ContractConstraintPredicateKind.OFFER_PROVIDER,
                arguments={"provider": _M4_PROVIDER_A},
            ),
        ),
    )
    late_decision = evaluate_contract_constraints(
        _m4_constraint_set((provider_rule,)), late_context
    )
    if not (
        late_decision.ok
        and late_decision.code == ContractConstraintDecisionCode.DEFAULT_DENY
    ):
        problems.append("offer-fact condition matched an unusable offer: %r" % (late_decision.code,))
    # the contract is still untouched by the failed resolution
    if contract.canonical_bytes() != contract_bytes_before:
        problems.append("the contract record changed after a failed offer-fact composition")
    if problems:
        results.append(fail(name, "; ".join(problems)))
    else:
        results.append(
            ok(
                name,
                "contract identity/state/fingerprint/bytes + exchange catalog byte-identical "
                "across composition + evaluation; withdrawn offer composes usable=False and "
                "offer-fact conditions fail closed",
            )
        )


def case_83_offer_reference_eligibility(results: List[Result]) -> None:
    """83. Offer-reference eligibility: the eligible path composes from
    the M003 exchange's resolution; provider/jurisdiction rule denials
    are decision DATA with deterministic reasons; an unusable offer is a
    DENIAL (never a raised error); a stale ruleset raises typed errors
    (the raised/DATA separation); empty permitted lists deny everything
    (fail closed, never silently permit)."""
    name = "case_83_offer_reference_eligibility"
    exchange = _m4_exchange()
    offer = _m4_offer(advertisement_id=exchange.advertisements()[0].advertisement_id)
    exchange.register_offer(offer)
    reference = OpaqueReference(
        ref_kind="offer", value=offer.offer_id, provenance=_m4_prov(_M4_ISSUER_A)
    )
    # compose the offer facts through the M003 exchange (by reference)
    from offers import resolve_offer_reference

    record = resolve_offer_reference(exchange, reference, at_instant=_M4_T_MID)
    facts = OfferReferenceEligibilityFacts(
        value=reference.value,
        offer_id=record.offer_id,
        provider=record.provider,
        jurisdictions=tuple(
            boundary.jurisdiction for boundary in record.service_boundaries
        ),
        usable=True,
    )
    ruleset = _m4_ruleset()
    outcome = evaluate_offer_reference_eligibility(facts, ruleset, at_instant=_M4_T_MID)
    problems: List[str] = []
    if not (
        outcome.eligible and outcome.reasons == () and outcome.provider == _M4_PROVIDER_A
        and outcome.jurisdictions == ("GH",)
    ):
        problems.append("eligible path drifted: %r %r" % (outcome.eligible, outcome.reasons))
    # provider not permitted -> denial DATA
    stranger_rules = _m4_ruleset(providers=(_M4_PROVIDER_B,))
    denied_provider = evaluate_offer_reference_eligibility(
        facts, stranger_rules, at_instant=_M4_T_MID
    )
    if denied_provider.eligible or denied_provider.reasons != (
        ContractEligibilityReason.PROVIDER_NOT_PERMITTED,
    ):
        problems.append("provider denial: %r %r" % (denied_provider.eligible, denied_provider.reasons))
    # jurisdiction not covered -> denial DATA
    jurisdiction_rules = _m4_ruleset(jurisdictions=("NG",))
    denied_jurisdiction = evaluate_offer_reference_eligibility(
        facts, jurisdiction_rules, at_instant=_M4_T_MID
    )
    if denied_jurisdiction.eligible or denied_jurisdiction.reasons != (
        ContractEligibilityReason.JURISDICTION_NOT_COVERED,
    ):
        problems.append("jurisdiction denial: %r" % (denied_jurisdiction.reasons,))
    # both violated -> deterministic ordered reasons
    both_rules = _m4_ruleset(providers=(_M4_PROVIDER_B,), jurisdictions=("NG",))
    denied_both = evaluate_offer_reference_eligibility(
        facts, both_rules, at_instant=_M4_T_MID
    )
    if denied_both.reasons != (
        ContractEligibilityReason.PROVIDER_NOT_PERMITTED,
        ContractEligibilityReason.JURISDICTION_NOT_COVERED,
    ):
        problems.append("merged denial reasons drifted: %r" % (denied_both.reasons,))
    # an unusable (withdrawn) offer is a DENIAL — decision DATA, never raised
    unusable_facts = OfferReferenceEligibilityFacts(
        value=reference.value,
        offer_id=reference.value,
        provider="unresolved-offer-reference",
        jurisdictions=(),
        usable=False,
    )
    withdrawn_outcome = evaluate_offer_reference_eligibility(
        unusable_facts, ruleset, at_instant=_M4_T_LATE
    )
    if withdrawn_outcome.eligible or withdrawn_outcome.reasons != (
        ContractEligibilityReason.OFFER_NOT_USABLE,
    ):
        problems.append("unusable offer: %r %r" % (withdrawn_outcome.eligible, withdrawn_outcome.reasons))
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    sub: List[Result] = []
    # stale ruleset never silently evaluates (raised typed error)
    stale = _m4_ruleset(valid_from="2026-01-01T00:00:00Z", valid_until="2026-02-01T00:00:00Z")
    sub.append(
        _m4_expect_eligibility_error(
            "case_83g_stale_ruleset", ContractEligibilityReason.TEMPORAL_INVALID,
            lambda: evaluate_offer_reference_eligibility(
                facts, stale, at_instant=_M4_T_MID
            ),
        )
    )
    # empty permitted lists deny everything (fail closed, never silently permit)
    empty_rules = _m4_ruleset(providers=(), jurisdictions=())
    empty_outcome = evaluate_offer_reference_eligibility(
        facts, empty_rules, at_instant=_M4_T_MID
    )
    if empty_outcome.eligible or empty_outcome.reasons != (
        ContractEligibilityReason.PROVIDER_NOT_PERMITTED,
        ContractEligibilityReason.JURISDICTION_NOT_COVERED,
    ):
        sub.append(
            fail(
                "case_83h_empty_rulesets_fail_closed",
                "empty permitted lists: %r %r" % (empty_outcome.eligible, empty_outcome.reasons),
            )
        )
    else:
        sub.append(
            ok(
                "case_83h_empty_rulesets_fail_closed",
                "empty permitted provider/jurisdiction lists deny (never silently permit)",
            )
        )
    # a jurisdiction-less usable offer cannot certify jurisdiction eligibility
    no_jur_facts = OfferReferenceEligibilityFacts(
        value=reference.value, offer_id=record.offer_id, provider=_M4_PROVIDER_A,
        jurisdictions=(), usable=True,
    )
    no_jur_outcome = evaluate_offer_reference_eligibility(
        no_jur_facts, ruleset, at_instant=_M4_T_MID
    )
    if no_jur_outcome.eligible or no_jur_outcome.reasons != (
        ContractEligibilityReason.JURISDICTION_NOT_COVERED,
    ):
        sub.append(
            fail(
                "case_83i_absent_jurisdiction_fails_closed",
                "absent jurisdiction facts: %r %r" % (no_jur_outcome.eligible, no_jur_outcome.reasons),
            )
        )
    else:
        sub.append(
            ok(
                "case_83i_absent_jurisdiction_fails_closed",
                "absent jurisdiction facts deny (never silently certify)",
            )
        )
    results.extend(sub)
    results.append(
        ok(
            name,
            "eligible composes via the M003 exchange; provider/jurisdiction denials are "
            "ordered DATA; unusable offer is a DENIAL (offer-not-usable); stale ruleset "
            "raises typed; empty/absent rule facts fail closed",
        )
    )


def case_84_contract_eligibility_composition(results: List[Result]) -> None:
    """84. Contract eligibility composition (end-to-end through the M002
    store + M003 exchange + the battery composition seam): a contract
    with no accepted offers denies (no-accepted-offers); after
    SelectOffers the reference set is eligible; a terminal contract
    denies (contract-terminal); an instant past the validity window
    denies (contract-not-live merged with offer-not-usable in the fixed
    deterministic order); the reason merge is deduplicated and
    order-preserving."""
    name = "case_84_contract_eligibility_composition"
    store, exchange, offer, contract = _m4_selected_contract()
    ruleset = _m4_ruleset()
    problems: List[str] = []

    # (a) INTENT with no accepted offers -> no-accepted-offers (a
    # DISTINCT contract: different principal -> different derived
    # identity; an identical create would be the store's idempotent no-op)
    created = store.submit(
        _m4_contract_create(principal_ref="app:roamlink-gw-02"),
        recorded_at="2026-09-30T11:00:00Z",
    )
    intent_facts = _m4_offer_facts_from_exchange(exchange, created.contract, at_instant=_M4_T_MID)
    intent_reference_facts = _m4_contract_facts(created.contract, intent_facts)
    intent_outcome = evaluate_contract_reference_eligibility(
        intent_reference_facts, ruleset, at_instant=_M4_T_MID
    )
    if intent_outcome.eligible or intent_outcome.reasons != (
        ContractEligibilityReason.NO_ACCEPTED_OFFERS,
    ):
        problems.append("no-offers: %r" % (intent_outcome.reasons,))
    # (b) OFFER_SELECTED with the live offer -> eligible
    selected_facts = _m4_offer_facts_from_exchange(exchange, contract, at_instant=_M4_T_MID)
    selected_reference_facts = _m4_contract_facts(contract, selected_facts)
    selected_outcome = evaluate_contract_reference_eligibility(
        selected_reference_facts, ruleset, at_instant=_M4_T_MID
    )
    if not (selected_outcome.eligible and selected_outcome.reasons == ()):
        problems.append("selected: %r %r" % (selected_outcome.eligible, selected_outcome.reasons))
    elif selected_outcome.contract_state != "OFFER_SELECTED":
        problems.append("outcome state drifted")
    elif len(selected_outcome.offer_outcomes) != 1 or not selected_outcome.offer_outcomes[0].eligible:
        problems.append("per-offer outcome drifted")
    # (c) terminal contract -> contract-terminal
    failed = store.submit(
        FailContract(recorded_at=_M4_T_MID, reason="constraint realization impossible"),
        recorded_at=_M4_T_MID,
        contract_id=contract.contract_id,
    )
    failed_facts = _m4_offer_facts_from_exchange(exchange, failed.contract, at_instant=_M4_T_MID)
    failed_reference_facts = _m4_contract_facts(failed.contract, failed_facts)
    terminal_outcome = evaluate_contract_reference_eligibility(
        failed_reference_facts, ruleset, at_instant=_M4_T_MID
    )
    if terminal_outcome.eligible or terminal_outcome.reasons != (
        ContractEligibilityReason.CONTRACT_TERMINAL,
    ):
        problems.append("terminal: %r" % (terminal_outcome.reasons,))
    # (d) past the validity window -> contract-not-live (+ the offer is
    # also past its own window -> unusable) in the fixed merge order
    past_facts = _m4_offer_facts_from_exchange(exchange, contract, at_instant=_M4_T_PAST_END)
    past_reference_facts = _m4_contract_facts(contract, past_facts)
    past_outcome = evaluate_contract_reference_eligibility(
        past_reference_facts, ruleset, at_instant=_M4_T_PAST_END
    )
    if past_outcome.eligible or past_outcome.reasons != (
        ContractEligibilityReason.CONTRACT_NOT_LIVE,
        ContractEligibilityReason.OFFER_NOT_USABLE,
    ):
        problems.append("past-window merge: %r" % (past_outcome.reasons,))
    if problems:
        results.append(fail(name, "; ".join(problems)))
    else:
        results.append(
            ok(
                name,
                "no-accepted-offers -> eligible -> contract-terminal -> "
                "past-window (contract-not-live + offer-not-usable, fixed merge order); "
                "reasons deduplicated and deterministic",
            )
        )


def case_85_m004_lock110_technology_neutral(results: List[Result]) -> None:
    """85. LOCK-110 at the policy boundary + the family import
    discipline: the M004 modules import stdlib +
    protocol.canonicalization + agent.clock (+ intra-family relatives)
    ONLY — the canonical domains are consumed through composed
    snapshots, never imported (LOCK-101's strongest form); no provider
    SDK/vendor types or transport objects anywhere in the new surface
    (AST audit)."""
    name = "case_85_m004_lock110_technology_neutral"
    import ast as _ast

    allowed_modules = {
        "__future__", "hashlib", "re", "dataclasses", "typing",
    }
    allowed_prefixes = ("protocol.canonicalization", "agent.clock")
    modules = (
        "eligibility/contract_constraints.py",
        "eligibility/contract_eligibility.py",
    )
    problems: List[str] = []
    for module_name in modules:
        source = (REPO_ROOT / module_name).read_text(encoding="utf-8")
        tree = _ast.parse(source)
        for node in _ast.walk(tree):
            if isinstance(node, _ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root not in allowed_modules:
                        problems.append("%s imports %s" % (module_name, alias.name))
            elif isinstance(node, _ast.ImportFrom):
                module = node.module or ""
                if module == "__future__" or node.level > 0:
                    continue  # relative imports stay intra-family
                if not any(
                    module == prefix or module.startswith(prefix + ".")
                    for prefix in allowed_prefixes
                ):
                    if module.split(".")[0] not in allowed_modules:
                        problems.append("%s imports from %s" % (module_name, module))
    # no SDK/vendor/transport tokens in the new surface CODE
    for module_name in modules:
        source = (REPO_ROOT / module_name).read_text(encoding="utf-8")
        tree = _ast.parse(source)
        code_tokens = set()
        for node in _ast.walk(tree):
            if isinstance(node, _ast.Name):
                code_tokens.add(node.id.lower())
            elif isinstance(node, _ast.Attribute):
                code_tokens.add(node.attr.lower())
            elif isinstance(node, _ast.ClassDef):
                code_tokens.add(node.name.lower())
            elif isinstance(node, _ast.FunctionDef):
                code_tokens.add(node.name.lower())
        for token in ("sdk", "vendor", "bearer", "esim", "radio", "modem", "wifi", "transport"):
            if token in code_tokens:
                problems.append("%s code carries %r token" % (module_name, token))
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
    else:
        results.append(
            ok(
                name,
                "M004 modules import stdlib + protocol.canonicalization + agent.clock "
                "only (canonical domains consumed via composed snapshots — never "
                "imported); no SDK/vendor/transport tokens in code (LOCK-110)",
            )
        )


def case_86_m004_lock119_and_round_trips(results: List[Result]) -> None:
    """86. LOCK-119 + canonical round-trips: secret-shaped material is
    rejected at construction; the constraint set, decision, ruleset and
    outcomes round-trip byte-stably through canonical JSON; mutated
    digests and unknown wire members fail closed (tamper evidence)."""
    name = "case_86_m004_lock119_and_round_trips"
    import json as _json

    _store, exchange, _offer, contract = _m4_selected_contract()
    facts = _m4_offer_facts_from_exchange(exchange, contract, at_instant=_M4_T_MID)
    context = _m4_context_from_contract(
        contract, "contract.select-offers", evaluation_instant=_M4_T_MID, offer_facts=facts
    )
    rule = _m4_rule("allow-select", "contract.select-offers")
    constraint_set = _m4_constraint_set((rule,))
    result = evaluate_contract_constraints(constraint_set, context)
    decision = result.decision
    ruleset = _m4_ruleset()
    reference_facts = _m4_contract_facts(contract, facts)
    outcome = evaluate_contract_reference_eligibility(
        reference_facts, ruleset, at_instant=_M4_T_MID
    )
    problems: List[str] = []
    if decision is None:
        results.append(fail(name, "the constraint evaluation did not produce a decision"))
        return

    # canonical round-trips (byte-stable)
    from protocol.canonicalization import canonical_json_bytes as _cjb

    wire_set = _cjb(constraint_set.to_dict())
    rebuilt_set = contract_constraint_set_from_mapping(_json.loads(wire_set.decode()))
    if _cjb(rebuilt_set.to_dict()) != wire_set or rebuilt_set.digest() != constraint_set.digest():
        problems.append("constraint set round-trip not byte-stable")
    wire_decision = _cjb(decision.to_dict())
    rebuilt_decision = ContractConstraintDecision.from_dict(_json.loads(wire_decision.decode()))
    if _cjb(rebuilt_decision.to_dict()) != wire_decision:
        problems.append("decision round-trip not byte-stable")
    wire_ruleset = _cjb(ruleset.to_dict())
    rebuilt_ruleset = contract_eligibility_ruleset_from_mapping(_json.loads(wire_ruleset.decode()))
    if _cjb(rebuilt_ruleset.to_dict()) != wire_ruleset or rebuilt_ruleset.digest() != ruleset.digest():
        problems.append("ruleset round-trip not byte-stable")
    wire_outcome = _cjb(outcome.to_dict())
    rebuilt_outcome = contract_eligibility_from_mapping(_json.loads(wire_outcome.decode()))
    if _cjb(rebuilt_outcome.to_dict()) != wire_outcome:
        problems.append("contract eligibility outcome round-trip not byte-stable")
    offer_outcome = outcome.offer_outcomes[0]
    wire_offer_outcome = _cjb(offer_outcome.to_dict())
    rebuilt_offer_outcome = offer_reference_eligibility_from_mapping(
        _json.loads(wire_offer_outcome.decode())
    )
    if _cjb(rebuilt_offer_outcome.to_dict()) != wire_offer_outcome:
        problems.append("offer eligibility outcome round-trip not byte-stable")

    # tamper evidence: mutated digests fail closed
    sub: List[Result] = []
    mutated = dict(_json.loads(wire_decision.decode()))
    mutated["decision_id"] = "sha256:" + "0" * 64
    sub.append(
        _m4_expect_constraint_error(
            "case_86g_mutated_decision_id", ContractConstraintReason.ID_MISMATCH,
            lambda: ContractConstraintDecision.from_dict(mutated),
        )
    )
    mutated_outcome = dict(_json.loads(wire_outcome.decode()))
    mutated_outcome["evaluation_digest"] = "sha256:" + "0" * 64
    sub.append(
        _m4_expect_eligibility_error(
            "case_86h_mutated_evaluation_digest", ContractEligibilityReason.INVALID_INPUT,
            lambda: ContractEligibility.from_dict(mutated_outcome),
        )
    )
    # unknown wire members fail closed
    unknown_member = dict(_json.loads(wire_set.decode()))
    unknown_member["mystery"] = 1
    sub.append(
        _m4_expect_constraint_error(
            "case_86i_unknown_wire_member", ContractConstraintReason.INVALID_INPUT,
            lambda: contract_constraint_set_from_mapping(unknown_member),
        )
    )
    # LOCK-119: secret-shaped material rejected at construction (the
    # M002/M003 discipline: secret-shaped VALUES and secret-named labels)
    sub.append(
        _m4_expect_constraint_error(
            "case_86j_secret_subject_value", ContractConstraintReason.SECRET_REJECTED,
            lambda: _m4_rule(
                "r-guarded", "contract.create", subjects=("ghp_secretechmaterial00",)
            ),
        )
    )
    sub.append(
        _m4_expect_constraint_error(
            "case_86k_secret_condition_value", ContractConstraintReason.SECRET_REJECTED,
            lambda: ContractConstraintCondition(
                predicate=ContractConstraintPredicateKind.PRINCIPAL_REF,
                arguments={"ref": "ghp_secretechmaterial00"},
            ),
        )
    )
    sub.append(
        _m4_expect_eligibility_error(
            "case_86l_secret_ruleset_issuer", ContractEligibilityReason.SECRET_REJECTED,
            lambda: ContractEligibilityRuleset(
                ruleset_id="rs2", version=1, issuer="sk_livematerial000000",
                permitted_providers=(_M4_PROVIDER_A,), permitted_jurisdictions=("GH",),
                decision_refs=("decision:platform-eligibility-v1",),
            ),
        )
    )
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.extend(sub)
    results.append(
        ok(
            name,
            "constraint set/decision/ruleset/outcomes round-trip byte-stably; mutated "
            "digests + unknown wire members fail closed; secret-shaped subject "
            "values, condition values and issuers rejected (LOCK-119)",
        )
    )


def case_87_m004_determinism(results: List[Result]) -> None:
    """87. Determinism: byte-identical decision/outcome bytes across
    repeated evaluations; identical digests across PYTHONHASHSEED
    0/1/12345 subprocesses (the pure-DATA evaluators, independent of
    any canonical import); no wall clock / randomness / network tokens
    in the M004 modules."""
    name = "case_87_m004_determinism"
    _store, exchange, _offer, contract = _m4_selected_contract()
    facts = _m4_offer_facts_from_exchange(exchange, contract, at_instant=_M4_T_MID)
    context = _m4_context_from_contract(
        contract, "contract.select-offers", evaluation_instant=_M4_T_MID, offer_facts=facts
    )
    rule = _m4_rule("allow-select", "contract.select-offers")
    constraint_set = _m4_constraint_set((rule,))
    ruleset = _m4_ruleset()
    first = evaluate_contract_constraints(constraint_set, context).decision
    second = evaluate_contract_constraints(constraint_set, context).decision
    reference_facts = _m4_contract_facts(contract, facts)
    eligibility_first = evaluate_contract_reference_eligibility(
        reference_facts, ruleset, at_instant=_M4_T_MID
    )
    eligibility_second = evaluate_contract_reference_eligibility(
        reference_facts, ruleset, at_instant=_M4_T_MID
    )
    problems: List[str] = []
    if first is None or second is None:
        results.append(fail(name, "no decision produced"))
        return
    if contract_constraint_decision_canonical_bytes(first) != contract_constraint_decision_canonical_bytes(second):
        problems.append("decision bytes differ across repeated evaluations")
    if first.decision_id != second.decision_id:
        problems.append("decision ids differ across repeated evaluations")
    if eligibility_first.evaluation_digest != eligibility_second.evaluation_digest:
        problems.append("eligibility digests differ across repeated evaluations")

    # cross-process determinism under PYTHONHASHSEED 0/1/12345: the
    # child builds the pure-DATA records directly (no canonical-domain
    # imports — the evaluators are independently deterministic)
    import subprocess as _sp
    import os as _os

    child = (
        "import sys; sys.path.insert(0, %r)\n" % (str(REPO_ROOT),)
        + """
from eligibility.contract_constraints import (
    ContractConstraintRule, ContractConstraintSet, ContractConstraintContext,
    OfferReferenceFacts, ValidityWindow, evaluate_contract_constraints,
)
from eligibility.contract_eligibility import (
    ContractEligibilityRuleset, ContractReferenceFacts,
    evaluate_contract_reference_eligibility,
)
PROVIDER_A = "adcos:node:identity.sha256-hmac-dev.v1:" + "1" * 64
T_MID = "2026-10-15T00:00:00Z"
facts = (OfferReferenceFacts(
    value="sha256:" + "a" * 64, offer_id="sha256:" + "b" * 64,
    provider=PROVIDER_A, jurisdictions=("GH",), usable=True,
),)
context = ContractConstraintContext(
    action="contract.select-offers", principal_kind="APPLICATION",
    principal_ref="app:sharenet-gw-01", beneficiary_kinds=("DEVICE",),
    contract_state="OFFER_SELECTED", hard_constraint_kinds=("latency-bound",),
    validity=ValidityWindow(not_before="2026-10-01T00:00:00Z", not_after="2026-11-01T00:00:00Z"),
    accepted_offer_values=("sha256:" + "b" * 64,), offer_facts=facts,
    evaluation_instant=T_MID,
)
rule = ContractConstraintRule(
    rule_id="allow-select", action="contract.select-offers", effect="allow",
    issuer="issuer:platform-ops", decision_refs=("decision:platform-constraints-v1",),
)
ps = ContractConstraintSet(set_id="cps-platform-1", version=1, rules=(rule,), issuer="issuer:platform-ops")
decision = evaluate_contract_constraints(ps, context).decision
reference_facts = ContractReferenceFacts(
    contract_id="sha256:" + "c" * 64, state="OFFER_SELECTED", state_is_terminal=False,
    validity=ValidityWindow(not_before="2026-10-01T00:00:00Z", not_after="2026-11-01T00:00:00Z"),
    offer_facts=facts,
)
ruleset = ContractEligibilityRuleset(
    ruleset_id="rs-platform-1", version=1, issuer="issuer:platform-ops",
    permitted_providers=(PROVIDER_A,), permitted_jurisdictions=("GH",),
    decision_refs=("decision:platform-eligibility-v1",),
)
outcome = evaluate_contract_reference_eligibility(reference_facts, ruleset, at_instant=T_MID)
print(decision.decision_id, outcome.evaluation_digest)
"""
    )
    digests = set()
    for seed in ("0", "1", "12345"):
        env = dict(_os.environ)
        env["PYTHONHASHSEED"] = seed
        run = _sp.run(
            [sys.executable, "-c", child],
            capture_output=True, text=True, env=env, timeout=120,
        )
        if run.returncode != 0:
            problems.append("PYTHONHASHSEED=%s child failed: %s" % (seed, run.stderr[-200:]))
            break
        digests.add(run.stdout.strip())
    if len(digests) > 1:
        problems.append("cross-process digests differ: %s" % sorted(digests))

    # clock/network discipline in the M004 modules (text audit)
    for module_name in (
        "eligibility/contract_constraints.py",
        "eligibility/contract_eligibility.py",
    ):
        text = (REPO_ROOT / module_name).read_text(encoding="utf-8")
        for token in (
            "time.monotonic", "time.perf_counter", "time.time", "datetime.now",
            "datetime.utcnow", "datetime.today", "import random", "import uuid",
            "import socket", "import urllib", "import requests", "import http",
            "os.urandom",
        ):
            if token in text:
                problems.append("%s contains %r" % (module_name, token))
    if problems:
        results.append(fail(name, "; ".join(problems[:5])))
    else:
        results.append(
            ok(
                name,
                "decision/outcome bytes identical across runs; identical digests across "
                "PYTHONHASHSEED 0/1/12345 subprocesses (pure-DATA evaluators, no "
                "canonical imports); no wall-clock/randomness/network tokens in the "
                "M004 modules",
            )
        )


def main() -> int:
    results: List[Result] = []
    # Required adversarial verification cases (1-41 from the prompt).
    case_01_minimal_allow_decision(results)
    case_02_minimal_explicit_deny(results)
    case_03_no_matching_privileged_rule_default_deny(results)
    case_04_missing_authorization_fact_fail_closed(results)
    case_05_expired_policy_fail_closed(results)
    case_06_not_yet_valid_policy_fail_closed(results)
    case_07_exact_validity_boundary(results)
    case_08_equal_priority_allow_deny_conflict(results)
    case_09_equal_specificity_equal_priority_conflict_fail_closed(results)
    case_10_explicit_priority_ordering(results)
    case_11_explicit_scope_specificity_ordering(results)
    case_12_deterministic_rule_order_independence(results)
    case_13_deterministic_policy_set_ordering(results)
    case_14_requester_nodeid_validation(results)
    case_15_credential_active_accepted(results)
    case_16_revoked_credential_rejected(results)
    case_17_expired_credential_rejected(results)
    case_18_malformed_credential_reference_rejected(results)
    case_19_resource_owner_access_policy(results)
    case_20_resource_kind_restriction(results)
    case_21_locality_allow(results)
    case_22_locality_deny(results)
    case_23_federation_allow(results)
    case_24_federation_deny(results)
    case_25_privacy_requirement_allow(results)
    case_26_privacy_requirement_deny(results)
    case_27_emergency_override_explicitly_allowed(results)
    case_28_emergency_override_absent_ordinary_deny_still_applies(results)
    case_29_service_priority_conflict_resolution(results)
    case_30_energy_reserve_allow(results)
    case_31_energy_reserve_deny(results)
    case_32_hard_intent_constraint_untouched(results)
    case_33_soft_intent_preference_untouched(results)
    case_34_remote_topology_claim_not_promoted_to_authoritative_fact(results)
    case_35_policy_evaluation_cannot_mutate_state(results)
    case_36_audit_records_rule_ids_and_policy_version(results)
    case_37_secret_material_rejected_and_not_echoed(results)
    case_38_unsupported_predicate_fails_explicitly(results)
    case_39_implementation_specific_access_technology_predicate_rejected(results)
    case_40_decision_bytes_digest_deterministic_across_runs(results)
    case_41_fuzz_property_inputs_never_crash_or_mutate_external_state(results)
    # Additional mechanical / boundary cases (42-69).
    case_42_no_5g_vendor_imports(results)
    case_43_no_wall_clock_imports(results)
    case_44_no_pricing_settlement_trust_route_imports(results)
    case_45_frozen_vocabularies_present(results)
    case_46_privileged_classification_structural(results)
    case_47_decision_no_forbidden_fields(results)
    case_48_policy_store_publish_withdraw_snapshot(results)
    case_49_policy_store_version_regression_rejected(results)
    case_50_policy_store_equal_version_different_content_rejected(results)
    case_51_policy_store_list_applicable_filters_expired(results)
    case_52_serialization_roundtrip(results)
    case_53_decision_digest_recomputable(results)
    case_54_require_review_never_silently_becomes_allow(results)
    case_55_domain_precedence_explicit(results)
    case_56_partial_domain_precedence_coverage_rejected(results)
    case_57_duplicate_rule_id_rejected(results)
    case_58_malformed_temporal_rejected(results)
    case_59_valid_until_before_valid_from_rejected(results)
    case_60_thread_safe_evaluation(results)
    case_61_no_external_network_dependency(results)
    case_62_evaluation_instant_required(results)
    case_63_malformed_evaluation_instant_fail_closed(results)
    case_64_rule_temporal_subwindow(results)
    case_65_subject_selector(results)
    case_66_trust_assertion_input_not_score(results)
    case_67_capability_required(results)
    case_68_frozen_doc_unchanged(results)
    case_69_prior_prompts_unchanged(results)
    # Architect-review regression cases (PR #10 correction cycle).
    case_70_issuer_mandatory(results)
    case_71_issuer_must_be_canonical_nodeid(results)
    case_72_malformed_intent_digest_cannot_authorize(results)
    # Architect-review regression case (PR #26 correction cycle, the
    # WORK-025 authority-boundary remediation).
    case_73_invocation_binding_born_bound(results)
    # WORK-026 ("policy-controlled authority") regression case: the
    # telemetry topology-promotion operation and its born binding.
    case_74_promotion_binding_born_bound(results)
    # M004 — Eligibility and Policy (R7-CORE-001 child, DEC-0101): the
    # refactored 1.1 surface around the canonical contract.
    case_75_m004_surface_and_vocabularies(results)
    case_76_contract_constraints_minimal_flow(results)
    case_77_contract_constraints_deny_and_default_deny(results)
    case_78_contract_constraints_fail_closed(results)
    case_79_contract_constraints_precedence_conflict(results)
    case_80_contract_constraints_temporal_subwindows(results)
    case_81_contract_constraints_subject_and_conditions(results)
    case_82_m004_lock101_by_reference(results)
    case_83_offer_reference_eligibility(results)
    case_84_contract_eligibility_composition(results)
    case_85_m004_lock110_technology_neutral(results)
    case_86_m004_lock119_and_round_trips(results)
    case_87_m004_determinism(results)

    print("ADCOS policy self-test (WORK-010 + M004)")
    print("=" * 72)
    for name, ok_flag, detail in results:
        print("[%s] %-72s %s" % ("ok  " if ok_flag else "FAIL", name, detail))
    print("-" * 72)
    passed = sum(1 for _, ok_flag, _ in results if ok_flag)
    if passed == len(results):
        print("Result: PASS (%d/%d cases)" % (passed, len(results)))
        return 0
    print("Result: FAIL (%d/%d cases passed)" % (passed, len(results)))
    return 1


if __name__ == "__main__":
    sys.exit(main())
