#!/usr/bin/env python3
"""ADCOS execution-plan self-test (M006 — Execution Plan).

Deterministic, offline verification of the ``executionplans/`` package
against the frozen Architecture 1.1 mandate (R7-CORE-001, DEC-0101;
the R7 charter M006 acceptance criteria): the contract-to-execution-
plan translation (LOCK-109) with verbatim hard-constraint
preservation (LOCK-108) at every boundary, typed execution segments
attributable to exactly one contract with the frozen state vocabulary
(PLANNED/RESERVED/ACTIVATED/MEASURED/RELEASED), optimizer
replaceability with deterministic injected tie-breaking (LOCK-111),
adapter-operation references by name only (LOCK-110 discipline —
M007 is a pending child and is never faked as delivered), opaque
execution-artifact plan references (LOCK-117), provenance (LOCK-118),
LOCK-119 determinism/secrets discipline, canonical-JSON round-trips,
and the disclosed composition harvest seam (WORK-054 patterns
harvested onto the 1.1 authority; composition stays the frozen
conformance layer — DEC-0085/DEC-0086 — with WORK-048
accepted-not-restored).

Battery coverage (the M006 work-item matrix):

- (a) simple translation: one real contract (accepted ``contracts/``
  API) with a real accepted offer (accepted ``offers/`` API) -> one
  segment (frozen 1.1 §10 simple deployment);
- (b) complex translation: multiple providers / segments / access
  mechanisms / failover alternatives under ONE contract (LOCK-116);
- (c) LOCK-108: every attempt to weaken/drop/reinterpret a hard
  constraint fails closed with a typed error — one case per
  constraint kind, plus the structural no-override surface;
- (d) the segment state machine: the legal path plus every illegal
  transition rejected (exhaustive matrix over the frozen vocabulary);
- (e) canonical-JSON round-trips and deterministic content-derived
  ids (plus cross-process PYTHONHASHSEED determinism);
- (f) provenance: plan/segment references resolve to the REAL
  contract and offer objects through their owning authorities;
- (g) the composition harvest seam: the WORK-054 conformance chain
  still runs fail-closed (BLOCKED_MISSING_AUTHORITY, W048 absent),
  the plan bridge is the canonical 1.1 bridge, no second authority is
  created on either side, and the composition battery itself re-runs
  green at its accepted count;
- (h) optimizer replaceability (LOCK-111): the plan shape is
  authority-true, tie-breaking deterministic and injected, never
  wall-clock.

All instants are injected (T0-style constants); no wall clock, no
randomness, no network, no real sockets, no secrets. Runs are
byte-identical across processes (PYTHONHASHSEED-safe).
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from contracts import (  # noqa: E402
    ASSURANCE_STATES,
    COMMAND_KINDS,
    CONSTRAINT_KINDS,
    CONTRACT_STATES,
    OpaqueReference,
    Provenance,
    TerminationRules,
    ValidityInterval,
    ActivateContract,
    BeneficiaryScope,
    BindExecutionArtifact,
    ConnectivityPrincipal,
    ContractStore,
    CreateContract,
    ExpireContract,
    FailContract,
    HardConstraint,
    RecordAssurance,
    RecordDelivery,
    RecordExecutionActivation,
    RecordSettled,
    RecordSettlementPending,
    RecordUsageFinal,
    SelectOffers,
    TerminateContract,
)

from offers import (  # noqa: E402
    OfferExchange,
    build_advertisement,
    build_offer,
    offer_reference,
    verify_accepted_offers,
)
from offers.model import (  # noqa: E402
    AdvertisementEntry,
    AdvertisementRef,
    OfferCommitment,
    OfferPricing,
    ServiceBoundary,
)

from executionplans import (  # noqa: E402
    ADAPTER_OPERATIONS,
    DEFAULT_TIE_BREAK,
    PLANNABLE_CONTRACT_STATES,
    SEGMENT_ROLES,
    SEGMENT_STATES,
    SEGMENT_TERMINAL_STATES,
    SEGMENT_TRANSITIONS,
    TIE_BREAK_KEYS,
    ExecutionPlan,
    ExecutionPlanError,
    ExecutionPlanReason,
    ExecutionSegment,
    SegmentInput,
    apply_segment_transition,
    check_segment_transition,
    conformance_digest,
    conformance_document,
    derive_plan_id,
    derive_segment_id,
    execution_sequence,
    plan_reference,
    translate_contract,
    verify_plan_preserves_contract,
    HARVEST_DISCLOSURE,
    PLAN_BRIDGE_DISCLAIMER,
)

Result = Tuple[str, bool, str]

T0 = "2026-10-01T00:00:00Z"
T1 = "2026-10-01T01:00:00Z"
T2 = "2026-10-01T02:00:00Z"
T3 = "2026-10-15T00:00:00Z"
T_END = "2026-11-01T00:00:00Z"
T_PAST_END = "2026-12-01T00:00:00Z"

PROVIDER_A = "adcos:node:identity.sha256-hmac-dev.v1:" + "1" * 64
PROVIDER_B = "adcos:node:identity.sha256-hmac-dev.v1:" + "2" * 64


def ok(name: str, detail: str = "") -> Result:
    return (name, True, detail)


def fail(name: str, detail: str) -> Result:
    return (name, False, detail)


def expect_error(case: str, code: str, action: Callable[[], Any]) -> Result:
    try:
        action()
    except ExecutionPlanError as error:
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
    return fail(case, "expected ExecutionPlanError(%s); the input was accepted" % code)


def _prov(issuer: str, *refs: str) -> Provenance:
    return Provenance(issuer=issuer, decision_refs=tuple(refs))


# ---------------------------------------------------------------------------
# Deterministic scenario fixtures (built once, in the fixed order)
# ---------------------------------------------------------------------------

_EXCHANGE: Optional[OfferExchange] = None
_OFFER_A_KEY = "offer:netpro-basic-1"
_OFFER_B1_KEY = "offer:skywave-mesh-1"
_OFFER_B2_KEY = "offer:skywave-failover-1"


def _exchange() -> OfferExchange:
    global _EXCHANGE
    if _EXCHANGE is not None:
        return _EXCHANGE
    exchange = OfferExchange()
    for provider, key in (
        (PROVIDER_A, _OFFER_A_KEY),
        (PROVIDER_B, _OFFER_B1_KEY),
        (PROVIDER_B, _OFFER_B2_KEY),
    ):
        issuer = "prov:%s" % ("netpro" if provider == PROVIDER_A else "skywave")
        advertisement = build_advertisement(
            provider=provider,
            entries=(
                AdvertisementEntry(
                    capability_id="capability.core.multipath",
                    schema_version="1.2",
                    statement_digest="sha256:" + "a" * 64,
                    classification="known",
                ),
            ),
            validity=ValidityInterval(not_before=T0, not_after=T_END),
            provenance=_prov(issuer),
        )
        offer = build_offer(
            provider=provider,
            provider_offer_key=key,
            schema_version=1,
            advertisements=(
                AdvertisementRef(
                    advertisement_id=advertisement.advertisement_id,
                    provenance=_prov(issuer),
                ),
            ),
            commitments=(
                OfferCommitment(
                    kind="latency-bound-ms",
                    params={"max_ms": 150},
                    window=ValidityInterval(not_before=T0, not_after=T_END),
                    provenance=_prov(issuer),
                ),
            ),
            pricing=OfferPricing(
                currency="USD",
                price_minor=250,
                price_exponent=2,
                billing_mode="flat",
                provenance=_prov(issuer),
            ),
            service_boundaries=(
                ServiceBoundary(
                    jurisdiction="GH",
                    geography_refs=("mpcell:v1:coarse-50000m:12:-1",),
                    provenance=_prov(issuer),
                ),
            ),
            validity=ValidityInterval(not_before=T0, not_after=T_END),
            provenance=_prov(issuer),
        )
        exchange.register_advertisement(advertisement)
        exchange.register_offer(offer)
    _EXCHANGE = exchange
    return exchange


def _offers() -> Dict[str, Any]:
    exchange = _exchange()
    by_key = {record.provider_offer_key: record for record in exchange.offers()}
    return {
        "A": by_key[_OFFER_A_KEY],
        "B1": by_key[_OFFER_B1_KEY],
        "B2": by_key[_OFFER_B2_KEY],
    }


def _offer_refs() -> Dict[str, OpaqueReference]:
    return {key: offer_reference(record) for key, record in _offers().items()}


#: Per-kind constraint fixtures: (strict params, weakened params).
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


def _create_command(
    constraints: Tuple[HardConstraint, ...],
) -> CreateContract:
    return CreateContract(
        principal=ConnectivityPrincipal(
            principal_kind="APPLICATION", principal_ref="app:sharenet-gw-01"
        ),
        beneficiaries=(
            BeneficiaryScope(beneficiary_kind="DEVICE", beneficiary_ref="dev:pi-7f2a"),
        ),
        requirements=(
            OpaqueReference(
                ref_kind="intent-requirements",
                value="intent:abc123",
                provenance=_prov("arch:sharenet"),
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
        provenance=_prov("arch:sharenet", "dec:elig-1"),
    )


_STORE_CACHE: Dict[str, Tuple[ContractStore, str]] = {}


def _mature_store(
    constraints: Tuple[HardConstraint, ...],
    *,
    offers: Tuple[str, ...] = ("A", "B1", "B2"),
) -> Tuple[ContractStore, str]:
    """A store whose single contract is CONTRACT_ACTIVE (cache-cleared
    per constraint set via a fresh walk; deterministic)."""
    key = "%s|%s" % (tuple(c.to_dict() for c in constraints), offers)
    if key in _STORE_CACHE:
        return _STORE_CACHE[key]
    store = ContractStore()
    created = store.submit(
        _create_command(constraints), recorded_at="2026-09-30T10:00:00Z"
    )
    cid = created.contract.contract_id
    refs = _offer_refs()
    store.submit(
        SelectOffers(offers=tuple(refs[name] for name in offers)),
        recorded_at="2026-09-30T10:05:00Z",
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
    _STORE_CACHE[key] = (store, cid)
    return store, cid


def _contract(constraints: Tuple[HardConstraint, ...]) -> Any:
    store, cid = _mature_store(constraints)
    return store.contract(cid)


def _plan(constraints: Optional[Tuple[HardConstraint, ...]] = None) -> Any:
    """The canonical simple plan: one primary segment over offer A."""
    contract = _contract(constraints or _constraints("latency-bound"))
    refs = _offer_refs()
    return translate_contract(
        contract,
        (
            SegmentInput(
                offer_reference=refs["A"],
                role="primary",
                operations=("reserve", "activate", "measure", "release"),
                provenance=_prov("optimizer:baseline-v1", "dec:opt-1"),
            ),
        ),
        provenance=_prov("optimizer:baseline-v1", "dec:opt-plan"),
    )


def _complex_inputs() -> Tuple[SegmentInput, ...]:
    """The canonical complex proposal: two providers, four segments
    (two primaries, one failover alternative, one access mechanism)."""
    refs = _offer_refs()
    return (
        SegmentInput(
            offer_reference=refs["B1"],
            role="primary",
            operations=("reserve", "activate", "measure", "release"),
            provenance=_prov("optimizer:baseline-v1", "dec:opt-3"),
        ),
        SegmentInput(
            offer_reference=refs["A"],
            role="alternative",
            operations=("reserve", "activate", "release"),
            provenance=_prov("optimizer:baseline-v1", "dec:opt-4"),
        ),
        SegmentInput(
            offer_reference=refs["A"],
            role="primary",
            operations=("reserve", "activate", "measure", "release"),
            provenance=_prov("optimizer:baseline-v1", "dec:opt-1"),
        ),
        SegmentInput(
            offer_reference=refs["B2"],
            role="access",
            operations=("reserve", "activate"),
            provenance=_prov("optimizer:baseline-v1", "dec:opt-2"),
        ),
    )


def _contract_at_state(
    target: str,
) -> Tuple[ContractStore, str, Any]:
    """A deterministic single-offer contract walked to the target
    lifecycle state (the frozen M002 transition table drives the walk)."""
    constraints = _constraints("latency-bound")
    store = ContractStore()
    created = store.submit(
        _create_command(constraints), recorded_at="2026-09-30T10:00:00Z"
    )
    cid = created.contract.contract_id
    refs = _offer_refs()
    if target == "INTENT":
        return store, cid, store.contract(cid)
    store.submit(
        SelectOffers(offers=(refs["A"],)),
        recorded_at="2026-09-30T10:05:00Z",
        contract_id=cid,
    )
    if target == "OFFER_SELECTED":
        return store, cid, store.contract(cid)
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
    if target == "CONTRACT_ACTIVE":
        return store, cid, store.contract(cid)
    if target == "TERMINATED":
        store.submit(
            TerminateContract(
                recorded_at=T1, condition="principal-requested", reason="done"
            ),
            recorded_at=T1,
            contract_id=cid,
        )
        return store, cid, store.contract(cid)
    if target == "EXPIRED":
        store.submit(ExpireContract(recorded_at=T_PAST_END), recorded_at=T_PAST_END, contract_id=cid)
        return store, cid, store.contract(cid)
    if target == "FAILED":
        store.submit(FailContract(recorded_at=T1, reason="test"), recorded_at=T1, contract_id=cid)
        return store, cid, store.contract(cid)
    store.submit(RecordExecutionActivation(recorded_at=T0), recorded_at=T0, contract_id=cid)
    if target == "EXECUTION_ACTIVE":
        return store, cid, store.contract(cid)
    if target == "DEGRADED":
        store.submit(
            RecordAssurance(
                recorded_at=T1,
                assurance_state="degraded",
                evidence_refs=(
                    OpaqueReference(ref_kind="decision", value="dec:assur-deg-1"),
                ),
            ),
            recorded_at=T1,
            contract_id=cid,
        )
        return store, cid, store.contract(cid)
    store.submit(RecordDelivery(recorded_at=T1), recorded_at=T1, contract_id=cid)
    if target == "DELIVERY":
        return store, cid, store.contract(cid)
    store.submit(
        RecordAssurance(
            recorded_at=T2,
            assurance_state="compliant",
            evidence_refs=(
                OpaqueReference(ref_kind="decision", value="dec:assur-ok-1"),
            ),
        ),
        recorded_at=T2,
        contract_id=cid,
    )
    if target == "ASSURED":
        return store, cid, store.contract(cid)
    store.submit(RecordUsageFinal(recorded_at=T2), recorded_at=T2, contract_id=cid)
    if target == "USAGE_FINAL":
        return store, cid, store.contract(cid)
    store.submit(RecordSettlementPending(recorded_at=T3), recorded_at=T3, contract_id=cid)
    if target == "SETTLEMENT_PENDING":
        return store, cid, store.contract(cid)
    store.submit(RecordSettled(recorded_at=T3), recorded_at=T3, contract_id=cid)
    if target == "SETTLED":
        return store, cid, store.contract(cid)
    raise AssertionError("unreachable target state %s" % target)


def _segment_input(
    offer_name: str = "A",
    role: str = "primary",
    operations: Tuple[str, ...] = ("reserve", "activate", "measure", "release"),
) -> SegmentInput:
    refs = _offer_refs()
    return SegmentInput(
        offer_reference=refs[offer_name],
        role=role,
        operations=operations,
        provenance=_prov("optimizer:baseline-v1", "dec:opt-1"),
    )


# ---------------------------------------------------------------------------
# 1. Frozen vocabularies
# ---------------------------------------------------------------------------


def case_01_frozen_vocabularies() -> Result:
    name = "case_01_frozen_vocabularies"
    if SEGMENT_STATES != ("PLANNED", "RESERVED", "ACTIVATED", "MEASURED", "RELEASED"):
        return fail(name, "the segment state vocabulary drifted from the frozen M006 set")
    if SEGMENT_TERMINAL_STATES != ("RELEASED",):
        return fail(name, "the terminal segment vocabulary drifted")
    if SEGMENT_ROLES != ("primary", "alternative", "access"):
        return fail(name, "the segment role vocabulary drifted")
    if ADAPTER_OPERATIONS != (
        "inspect-capabilities",
        "inspect-offers",
        "reserve",
        "activate",
        "measure",
        "reconfigure",
        "release",
        "health",
    ):
        return fail(name, "the adapter operation vocabulary drifted from frozen 1.1 §6")
    if PLANNABLE_CONTRACT_STATES != (
        "OFFER_SELECTED",
        "CONTRACT_ACTIVE",
        "EXECUTION_ACTIVE",
        "DEGRADED",
    ):
        return fail(name, "the plannable contract-state vocabulary drifted")
    if TIE_BREAK_KEYS != ("role", "operation", "offer", "segment-id"):
        return fail(name, "the tie-break key vocabulary drifted (LOCK-111)")
    if DEFAULT_TIE_BREAK != ("role", "offer", "segment-id"):
        return fail(name, "the default injected tie-break drifted")
    if set(SEGMENT_TRANSITIONS) != set(SEGMENT_STATES):
        return fail(name, "the transition table does not cover the state vocabulary")
    # LOCK-110 discipline: the operation vocabulary is capability-oriented
    # names only — no provider SDK type tokens
    for operation in ADAPTER_OPERATIONS:
        if not operation.replace("-", "").isalpha():
            return fail(name, "operation %r carries non-name tokens" % operation)
    return ok(
        name,
        "segment states/roles/operations/transitions/tie-break/plannable "
        "vocabularies are byte-frozen; operations are capability-oriented "
        "names only (LOCK-110 discipline)",
    )


# ---------------------------------------------------------------------------
# (a) 2. Simple deployment: one contract -> one segment
# ---------------------------------------------------------------------------


def case_02_simple_translation() -> Result:
    name = "case_02_simple_translation"
    contract = _contract(_constraints("latency-bound"))
    plan = _plan()
    problems: List[str] = []
    if plan.contract_id != contract.contract_id:
        problems.append("the plan is not attributable to the contract")
    if len(plan.segments) != 1:
        problems.append("simple translation produced %d segments" % len(plan.segments))
        return fail(name, "; ".join(problems))
    segment = plan.segments[0]
    if segment.role != "primary":
        problems.append("the single segment is not primary")
    if segment.state != "PLANNED":
        problems.append("the fresh segment is not PLANNED")
    if segment.operations != ("reserve", "activate", "measure", "release"):
        problems.append("the canonical realization order was not applied")
    if segment.contract_id != contract.contract_id:
        problems.append("the segment is not attributable to the contract")
    # the frozen 1.1 §10 simple shape: Intent -> Offer -> Contract -> one
    # ExecutionSegment (the contract walked INTENT -> OFFER_SELECTED ->
    # CONTRACT_ACTIVE through the real M002 store)
    if contract.state != "CONTRACT_ACTIVE":
        problems.append("the fixture contract is not CONTRACT_ACTIVE")
    if len(contract.accepted_offers) < 1:
        problems.append("the contract carries no accepted offers")
    # LOCK-108: verbatim constraint preservation + fingerprint
    if plan.constraint_fingerprint != contract.hard_constraint_fingerprint():
        problems.append("the plan fingerprint is not the contract's (LOCK-108)")
    if [c.to_dict() for c in plan.hard_constraints] != [
        c.to_dict() for c in contract.hard_constraints
    ]:
        problems.append("the plan constraint set is not the contract's verbatim set")
    try:
        verify_plan_preserves_contract(plan, contract)
    except ExecutionPlanError as error:
        problems.append("verify failed: %s" % error.detail[:80])
    if problems:
        return fail(name, "; ".join(problems))
    return ok(
        name,
        "one real contract -> one primary segment; constraints verbatim; "
        "fingerprint == the contract's; verify passes (frozen 1.1 §10 simple "
        "deployment)",
    )


# ---------------------------------------------------------------------------
# (b) 3. Complex deployment: multiple providers/segments/alternatives
# ---------------------------------------------------------------------------


def case_03_complex_translation() -> Result:
    name = "case_03_complex_translation"
    contract = _contract(_constraints("latency-bound", "geography"))
    plan = translate_contract(
        contract, _complex_inputs(), provenance=_prov("optimizer:baseline-v1")
    )
    problems: List[str] = []
    if plan.contract_id != contract.contract_id:
        problems.append("the complex plan is not attributable to the ONE contract")
    if len(plan.segments) != 4:
        problems.append("expected 4 segments, found %d" % len(plan.segments))
        return fail(name, "; ".join(problems))
    roles = [segment.role for segment in plan.segments]
    if sorted(roles) != ["access", "alternative", "primary", "primary"]:
        problems.append("the roles are not the LOCK-116 composition shape: %s" % roles)
    # every segment is typed, attributable, and references an accepted offer
    refs = _offer_refs()
    accepted = set(contract.accepted_offers)
    for i, segment in enumerate(plan.segments):
        if segment.contract_id != contract.contract_id:
            problems.append("segment %d is not attributable to the contract" % i)
        if segment.offer_reference not in accepted:
            problems.append("segment %d references an unaccepted offer" % i)
        if segment.state != "PLANNED":
            problems.append("segment %d is not PLANNED" % i)
    # two distinct providers under one contract (LOCK-116)
    exchange = _exchange()
    providers = set()
    for segment in plan.segments:
        record = exchange.offer(segment.offer_reference.value)
        providers.add(record.provider)
    if len(providers) != 2:
        problems.append("expected 2 providers under one contract, found %d" % len(providers))
    try:
        verify_plan_preserves_contract(plan, contract)
    except ExecutionPlanError as error:
        problems.append("verify failed: %s" % error.detail[:80])
    if problems:
        return fail(name, "; ".join(problems))
    return ok(
        name,
        "one contract -> 4 typed segments over 2 providers (2 primary + 1 "
        "failover alternative + 1 access mechanism), each attributable with "
        "accepted-offer provenance (LOCK-116)",
    )


# ---------------------------------------------------------------------------
# 4. The plannable-state matrix (every contract lifecycle state)
# ---------------------------------------------------------------------------


def case_04_plannable_state_matrix() -> Result:
    name = "case_04_plannable_state_matrix"
    problems: List[str] = []
    for state in CONTRACT_STATES:
        _, _, contract = _contract_at_state(state)
        try:
            translate_contract(
                contract,
                (_segment_input(),),
                provenance=_prov("optimizer:baseline-v1"),
            )
            if state not in PLANNABLE_CONTRACT_STATES:
                problems.append("%s: translation ACCEPTED (must fail closed)" % state)
        except ExecutionPlanError as error:
            if state in PLANNABLE_CONTRACT_STATES:
                problems.append("%s: translation failed: %s" % (state, error.detail[:60]))
            elif error.code != ExecutionPlanReason.NOT_PLANNABLE:
                problems.append(
                    "%s: wrong code %s (expected plan-contract-not-plannable)"
                    % (state, error.code)
                )
    if problems:
        return fail(name, "; ".join(problems))
    return ok(
        name,
        "all 13 contract lifecycle states probed: exactly %s translate; "
        "INTENT/terminal/post-execution states fail closed "
        "plan-contract-not-plannable" % ", ".join(PLANNABLE_CONTRACT_STATES),
    )


# ---------------------------------------------------------------------------
# 5-6. Translation inputs fail closed
# ---------------------------------------------------------------------------


def case_05_translation_inputs_fail_closed() -> Result:
    name = "case_05_translation_inputs_fail_closed"
    contract = _contract(_constraints("latency-bound"))
    refs = _offer_refs()
    results: List[Result] = []
    results.append(
        expect_error(
            name + "_non_contract",
            ExecutionPlanReason.INVALID_INPUT,
            lambda: translate_contract(
                "not-a-contract", (_segment_input(),), provenance=_prov("optimizer:x")
            ),
        )
    )
    results.append(
        expect_error(
            name + "_empty_segments",
            ExecutionPlanReason.INVALID_INPUT,
            lambda: translate_contract(
                contract, (), provenance=_prov("optimizer:x")
            ),
        )
    )
    results.append(
        expect_error(
            name + "_non_segment_input",
            ExecutionPlanReason.INVALID_INPUT,
            lambda: translate_contract(
                contract, ("not-a-segment",), provenance=_prov("optimizer:x")
            ),
        )
    )
    # an offer reference that is not a verbatim accepted member:
    # a lookalike with different provenance fails closed (LOCK-117/118)
    lookalike = OpaqueReference(
        ref_kind="offer", value=refs["A"].value, provenance=_prov("prov:unknown")
    )
    results.append(
        expect_error(
            name + "_lookalike_offer",
            ExecutionPlanReason.OFFER_NOT_ACCEPTED,
            lambda: translate_contract(
                contract,
                (
                    SegmentInput(
                        offer_reference=lookalike,
                        role="primary",
                        operations=("reserve", "activate"),
                        provenance=_prov("optimizer:x"),
                    ),
                ),
                provenance=_prov("optimizer:x"),
            ),
        )
    )
    # an offer registered on the exchange but NOT accepted by this contract
    # (the single-offer fixture contract accepted only offer A)
    unaccepted = offer_reference(_offers()["B2"])
    unaccepted_contract = _contract_at_state("CONTRACT_ACTIVE")[2]
    results.append(
        expect_error(
            name + "_unaccepted_offer",
            ExecutionPlanReason.OFFER_NOT_ACCEPTED,
            lambda: translate_contract(
                unaccepted_contract,
                (
                    SegmentInput(
                        offer_reference=unaccepted,
                        role="primary",
                        operations=("reserve",),
                        provenance=_prov("optimizer:x"),
                    ),
                ),
                provenance=_prov("optimizer:x"),
            ),
        )
    )
    # wrong reference kind on the proposal
    results.append(
        expect_error(
            name + "_wrong_reference_kind",
            ExecutionPlanReason.VOCABULARY,
            lambda: SegmentInput(
                offer_reference=OpaqueReference(
                    ref_kind="execution-scope", value="scope:exec-default"
                ),
                role="primary",
                operations=("reserve",),
                provenance=_prov("optimizer:x"),
            ),
        )
    )
    # no primary segment
    results.append(
        expect_error(
            name + "_no_primary",
            ExecutionPlanReason.NO_PRIMARY,
            lambda: translate_contract(
                contract,
                (
                    SegmentInput(
                        offer_reference=refs["A"],
                        role="alternative",
                        operations=("reserve",),
                        provenance=_prov("optimizer:x"),
                    ),
                ),
                provenance=_prov("optimizer:x"),
            ),
        )
    )
    # duplicate segment cores
    results.append(
        expect_error(
            name + "_duplicate_segments",
            ExecutionPlanReason.DUPLICATE_SEGMENT,
            lambda: translate_contract(
                contract,
                (_segment_input(), _segment_input()),
                provenance=_prov("optimizer:x"),
            ),
        )
    )
    # LOCK-119: secret-shaped provenance issuer rejected at the domain's
    # deserialization boundary (wrapped as a typed plan error)
    secret_proposal = _segment_input().to_dict()
    secret_proposal["provenance"]["issuer"] = "sk_workersecret123"
    results.append(
        expect_error(
            name + "_secret_shaped",
            ExecutionPlanReason.SECRET_REJECTED,
            lambda: SegmentInput.from_dict(secret_proposal),
        )
    )
    # unknown role / unknown operation / empty operations / repeated operation
    results.append(
        expect_error(
            name + "_unknown_role",
            ExecutionPlanReason.VOCABULARY,
            lambda: SegmentInput(
                offer_reference=refs["A"],
                role="backup",
                operations=("reserve",),
                provenance=_prov("optimizer:x"),
            ),
        )
    )
    results.append(
        expect_error(
            name + "_unknown_operation",
            ExecutionPlanReason.VOCABULARY,
            lambda: SegmentInput(
                offer_reference=refs["A"],
                role="primary",
                operations=("reserve", "sdk-call-ericsson"),
                provenance=_prov("optimizer:x"),
            ),
        )
    )
    results.append(
        expect_error(
            name + "_repeated_operation",
            ExecutionPlanReason.INVALID_INPUT,
            lambda: SegmentInput(
                offer_reference=refs["A"],
                role="primary",
                operations=("reserve", "reserve"),
                provenance=_prov("optimizer:x"),
            ),
        )
    )
    bad = [entry for entry in results if not entry[1]]
    if bad:
        return fail(bad[0][0], bad[0][2])
    return ok(
        name,
        "non-contract/empty/lookalike/unaccepted/wrong-kind/no-primary/"
        "duplicate/secret-shaped/unknown-role/unknown-or-repeated-operation "
        "inputs all fail closed with typed errors",
    )


def case_06_plan_window_containment() -> Result:
    name = "case_06_plan_window_containment"
    contract = _contract(_constraints("latency-bound"))
    results: List[Result] = []
    results.append(
        expect_error(
            name + "_before_contract",
            ExecutionPlanReason.TEMPORAL_INVALID,
            lambda: translate_contract(
                contract,
                (_segment_input(),),
                provenance=_prov("optimizer:x"),
                plan_window=ValidityInterval(
                    not_before="2026-09-01T00:00:00Z", not_after="2026-10-15T00:00:00Z"
                ),
            ),
        )
    )
    results.append(
        expect_error(
            name + "_after_contract",
            ExecutionPlanReason.TEMPORAL_INVALID,
            lambda: translate_contract(
                contract,
                (_segment_input(),),
                provenance=_prov("optimizer:x"),
                plan_window=ValidityInterval(
                    not_before="2026-10-02T00:00:00Z", not_after="2026-12-01T00:00:00Z"
                ),
            ),
        )
    )
    results.append(
        expect_error(
            name + "_non_interval",
            ExecutionPlanReason.INVALID_INPUT,
            lambda: translate_contract(
                contract,
                (_segment_input(),),
                provenance=_prov("optimizer:x"),
                plan_window="2026-10-01/2026-11-01",
            ),
        )
    )
    # a contained sub-window is accepted and carried
    plan = translate_contract(
        contract,
        (_segment_input(),),
        provenance=_prov("optimizer:x"),
        plan_window=ValidityInterval(
            not_before="2026-10-02T00:00:00Z", not_after="2026-10-20T00:00:00Z"
        ),
    )
    if plan.validity.not_before != "2026-10-02T00:00:00Z":
        results.append(fail(name + "_subwindow", "the contained window was not carried"))
    else:
        results.append(ok(name + "_subwindow", "the contained sub-window is carried"))
    # default: the contract validity itself
    plan_default = _plan()
    if plan_default.validity != contract.validity:
        results.append(
            fail(name + "_default", "the default window is not the contract validity")
        )
    else:
        results.append(ok(name + "_default", "the default window is the contract validity"))
    bad = [entry for entry in results if not entry[1]]
    if bad:
        return fail(bad[0][0], bad[0][2])
    return ok(name, "plan windows escaping the contract validity fail closed; contained windows carry")


# ---------------------------------------------------------------------------
# (c) LOCK-108 — one case per constraint kind
# ---------------------------------------------------------------------------


def _lock108_kind_cases() -> List[Result]:
    """Per constraint kind: drop / relax / re-interpret attempts all
    fail closed with typed errors citing the kind."""
    results: List[Result] = []
    kinds = list(CONSTRAINT_KINDS)
    for index, kind in enumerate(kinds):
        case = "case_%02d_lock108_%s" % (7 + index, kind.replace("-", "_"))
        strict_params, weak_params = _KIND_FIXTURES[kind]
        strict = _contract(_constraints(kind))
        strict_plan = translate_contract(
            strict, (_segment_input(),), provenance=_prov("optimizer:baseline-v1")
        )

        # attempt 1 — DROP: a contract without the constraint; its plan
        # presented against the strict contract fails closed
        if len(kinds) > 1:
            other = kinds[(index + 1) % len(kinds)]
            dropped = _contract(_constraints(other))
            dropped_plan = translate_contract(
                dropped, (_segment_input(),), provenance=_prov("optimizer:baseline-v1")
            )
            try:
                verify_plan_preserves_contract(dropped_plan, strict)
                results.append(
                    fail(case + "_drop", "the dropped constraint was ACCEPTED")
                )
                continue
            except ExecutionPlanError as error:
                if error.code != ExecutionPlanReason.CONSTRAINT_WEAKENED:
                    results.append(
                        fail(
                            case + "_drop",
                            "wrong code %s (expected plan-constraint-weakened): %s"
                            % (error.code, error.detail[:60]),
                        )
                    )
                    continue
                if kind not in error.detail:
                    results.append(
                        fail(
                            case + "_drop",
                            "the error does not cite the kind %s: %s"
                            % (kind, error.detail[:80]),
                        )
                    )
                    continue

        # attempt 2 — RELAX: the same kind with weakened params
        relaxed_contract = _contract(
            (
                HardConstraint(
                    kind=kind, params=weak_params, provenance=_prov("prov:netpro")
                ),
            )
        )
        relaxed_plan = translate_contract(
            relaxed_contract, (_segment_input(),), provenance=_prov("optimizer:baseline-v1")
        )
        try:
            verify_plan_preserves_contract(relaxed_plan, strict)
            results.append(fail(case + "_relax", "the relaxed constraint was ACCEPTED"))
            continue
        except ExecutionPlanError as error:
            if error.code != ExecutionPlanReason.CONSTRAINT_WEAKENED:
                results.append(
                    fail(
                        case + "_relax",
                        "wrong code %s: %s" % (error.code, error.detail[:60]),
                    )
                )
                continue

        # attempt 3 — REINTERPRET: a different kind carrying the strict
        # kind's parameters
        reinterpret_contract = _contract(
            (
                HardConstraint(
                    kind=kinds[(index + 2) % len(kinds)],
                    params=strict_params,
                    provenance=_prov("prov:netpro"),
                ),
            )
        )
        reinterpret_plan = translate_contract(
            reinterpret_contract, (_segment_input(),), provenance=_prov("optimizer:baseline-v1")
        )
        try:
            verify_plan_preserves_contract(reinterpret_plan, strict)
            results.append(fail(case + "_reinterpret", "the reinterpreted constraint was ACCEPTED"))
            continue
        except ExecutionPlanError as error:
            if error.code != ExecutionPlanReason.CONSTRAINT_WEAKENED:
                results.append(
                    fail(
                        case + "_reinterpret",
                        "wrong code %s: %s" % (error.code, error.detail[:60]),
                    )
                )
                continue

        # attempt 4 — FORGED DESERIALIZATION: the strict plan's dict with
        # the constraint relaxed on the wire fails at the boundary
        forged = strict_plan.to_dict()
        forged["hard_constraints"][0]["params"] = dict(weak_params)
        try:
            ExecutionPlan.from_dict(forged)
            results.append(fail(case + "_forge", "the forged plan deserialized"))
            continue
        except ExecutionPlanError as error:
            if error.code not in (
                ExecutionPlanReason.CONSTRAINT_MISMATCH,
                ExecutionPlanReason.ID_MISMATCH,
            ):
                results.append(
                    fail(case + "_forge", "wrong code %s: %s" % (error.code, error.detail[:60]))
                )
                continue

        results.append(
            ok(
                case,
                "%s: drop/relax/reinterpret fail plan-constraint-weakened citing "
                "the kind; wire forgery fails plan-constraint-mismatch (LOCK-108)"
                % kind,
            )
        )
    return results


def case_19_lock108_no_override_surface() -> Result:
    name = "case_19_lock108_no_override_surface"
    problems: List[str] = []
    # structural: the optimizer proposal record has NO constraint member
    # (the plan's constraint set is the contract's own — no input path)
    segment_fields = {f.name for f in SegmentInput.__dataclass_fields__.values()}
    if segment_fields & {"constraints", "hard_constraints", "constraint_fingerprint"}:
        problems.append("SegmentInput carries a constraint member (override path)")
    # structural: the translate surface has no constraint parameter
    import inspect

    signature = inspect.signature(translate_contract)
    for parameter in signature.parameters:
        if "constraint" in parameter:
            problems.append("translate_contract carries a %r parameter" % parameter)
    # behavior: two different optimizer proposals over the same contract
    # produce the SAME authority-true shape (contract attribution,
    # verbatim constraints, fingerprint, validity)
    contract = _contract(_constraints("latency-bound", "geography"))
    plan_one = translate_contract(
        contract, (_segment_input("A"),), provenance=_prov("optimizer:one")
    )
    plan_two = translate_contract(
        contract, (_segment_input("B1"), _segment_input("B2", "alternative")), provenance=_prov("optimizer:two")
    )
    if plan_one.contract_id != plan_two.contract_id:
        problems.append("contract attribution drifted between optimizers")
    if plan_one.constraint_fingerprint != plan_two.constraint_fingerprint:
        problems.append("the LOCK-108 fingerprint drifted between optimizers")
    if [c.to_dict() for c in plan_one.hard_constraints] != [
        c.to_dict() for c in plan_two.hard_constraints
    ]:
        problems.append("the constraint set drifted between optimizers")
    if plan_one.validity != plan_two.validity:
        problems.append("the validity window drifted between optimizers")
    # dataclasses.replace with a weakened set fails at the boundary
    from dataclasses import replace as dc_replace

    try:
        dc_replace(
            plan_one,
            hard_constraints=(
                HardConstraint(
                    kind="latency-bound",
                    params={"max_ms": 999},
                    provenance=_prov("prov:netpro"),
                ),
            ),
        )
        problems.append("replace() with weakened constraints was ACCEPTED")
    except ExecutionPlanError as error:
        if error.code != ExecutionPlanReason.CONSTRAINT_MISMATCH:
            problems.append("wrong code %s from replace()" % error.code)
    if problems:
        return fail(name, "; ".join(problems))
    return ok(
        name,
        "no constraint input exists on the translation surface; the constraint "
        "set/fingerprint/attribution are authority-true across optimizers; "
        "weakened construction fails plan-constraint-mismatch (LOCK-108)",
    )


# ---------------------------------------------------------------------------
# (d) The segment state machine
# ---------------------------------------------------------------------------


def case_20_segment_state_legal_path() -> Result:
    name = "case_20_segment_state_legal_path"
    plan = _plan()
    segment_id = plan.segments[0].segment_id
    problems: List[str] = []
    current = plan
    for target, instant in (
        ("RESERVED", T0),
        ("ACTIVATED", T1),
        ("MEASURED", T2),
        ("MEASURED", T2),
        ("RELEASED", T3),
    ):
        successor = apply_segment_transition(
            current, segment_id, target, at_instant=instant
        )
        if successor.plan_id != plan.plan_id:
            problems.append("the plan identity changed at %s" % target)
        if successor.segments[0].segment_id != segment_id:
            problems.append("the segment identity changed at %s" % target)
        if successor.constraint_fingerprint != plan.constraint_fingerprint:
            problems.append("the constraint fingerprint changed at %s (LOCK-108)" % target)
        if successor.segments[0].state != target:
            problems.append("the state did not advance to %s" % target)
        current = successor
    if current.segments[0].state != "RELEASED":
        problems.append("the full legal walk did not reach RELEASED")
    if not current.segments[0].is_terminal():
        problems.append("RELEASED is not terminal")
    if problems:
        return fail(name, "; ".join(problems))
    return ok(
        name,
        "PLANNED->RESERVED->ACTIVATED->MEASURED->(re-MEASURED)->RELEASED: "
        "identity, fingerprint and constraints stable at every step (the "
        "idempotent re-measurement transition is legal)",
    )


def case_21_segment_state_illegal_matrix() -> Result:
    name = "case_21_segment_state_illegal_matrix"
    problems: List[str] = []
    legal_expected: Dict[Tuple[str, str], bool] = {}
    for state in SEGMENT_STATES:
        for target in SEGMENT_STATES:
            if state == "RELEASED":
                legal_expected[(state, target)] = False
            elif state == "MEASURED":
                legal_expected[(state, target)] = target in ("RELEASED", "MEASURED")
            elif state == "ACTIVATED":
                legal_expected[(state, target)] = target in ("MEASURED", "RELEASED")
            elif state == "RESERVED":
                legal_expected[(state, target)] = target in ("ACTIVATED", "RELEASED")
            else:  # PLANNED
                legal_expected[(state, target)] = target in ("RESERVED", "RELEASED")
    # cross-check the frozen table itself
    for (state, target), expected in legal_expected.items():
        table_legal = target in SEGMENT_TRANSITIONS[state]
        if table_legal != expected:
            problems.append("table mismatch %s->%s" % (state, target))
    # probe every (current, target) pair on a REAL plan
    probes: Dict[str, Any] = {}
    base = _plan()
    segment_id = base.segments[0].segment_id
    probes["PLANNED"] = base
    step = base
    for target in ("RESERVED", "ACTIVATED", "MEASURED"):
        step = apply_segment_transition(step, segment_id, target, at_instant=T1)
        probes[step.segments[0].state] = step
    released = apply_segment_transition(step, segment_id, "RELEASED", at_instant=T2)
    probes["RELEASED"] = released
    for state, plan in probes.items():
        for target in SEGMENT_STATES:
            try:
                apply_segment_transition(plan, segment_id, target, at_instant=T1)
                accepted = True
            except ExecutionPlanError as error:
                accepted = False
                expected_code = (
                    ExecutionPlanReason.SEGMENT_TERMINAL
                    if state in SEGMENT_TERMINAL_STATES
                    else ExecutionPlanReason.INVALID_TRANSITION
                )
                if error.code != expected_code:
                    problems.append(
                        "%s->%s: wrong code %s" % (state, target, error.code)
                    )
            if accepted != legal_expected[(state, target)]:
                problems.append(
                    "%s->%s: %s (expected %s)"
                    % (state, target, "ACCEPTED" if accepted else "rejected", legal_expected[(state, target)])
                )
    if problems:
        return fail(name, "; ".join(problems[:6]))
    legal_count = sum(1 for value in legal_expected.values() if value)
    return ok(
        name,
        "all 25 (state, target) pairs probed: exactly %d legal transitions "
        "succeed, %d illegal ones fail closed (INVALID_TRANSITION, or "
        "SEGMENT_TERMINAL out of RELEASED)"
        % (legal_count, 25 - legal_count),
    )


def case_22_segment_transition_discipline() -> Result:
    name = "case_22_segment_transition_discipline"
    plan = _plan()
    segment_id = plan.segments[0].segment_id
    results: List[Result] = []
    results.append(
        expect_error(
            name + "_unknown_segment",
            ExecutionPlanReason.SEGMENT_UNKNOWN,
            lambda: apply_segment_transition(
                plan, "sha256:" + "9" * 64, "RESERVED", at_instant=T0
            ),
        )
    )
    results.append(
        expect_error(
            name + "_past_expiry_engagement",
            ExecutionPlanReason.TEMPORAL_INVALID,
            lambda: apply_segment_transition(
                plan, segment_id, "RESERVED", at_instant=T_PAST_END
            ),
        )
    )
    results.append(
        expect_error(
            name + "_before_window_engagement",
            ExecutionPlanReason.TEMPORAL_INVALID,
            lambda: apply_segment_transition(
                plan, segment_id, "RESERVED", at_instant="2026-09-01T00:00:00Z"
            ),
        )
    )
    results.append(
        expect_error(
            name + "_malformed_instant",
            ExecutionPlanReason.TEMPORAL_INVALID,
            lambda: apply_segment_transition(
                plan, segment_id, "RESERVED", at_instant="not-an-instant"
            ),
        )
    )
    results.append(
        expect_error(
            name + "_unknown_target",
            ExecutionPlanReason.VOCABULARY,
            lambda: apply_segment_transition(
                plan, segment_id, "DEGRADED", at_instant=T0
            ),
        )
    )
    results.append(
        expect_error(
            name + "_non_plan",
            ExecutionPlanReason.INVALID_INPUT,
            lambda: apply_segment_transition(
                "not-a-plan", segment_id, "RESERVED", at_instant=T0
            ),
        )
    )
    # RELEASE (cleanup) stays legal past expiry
    released = apply_segment_transition(
        plan, segment_id, "RELEASED", at_instant=T_PAST_END
    )
    if released.segments[0].state != "RELEASED":
        results.append(fail(name + "_release_past_expiry", "release past expiry rejected"))
    else:
        results.append(ok(name + "_release_past_expiry", "release past expiry is legal (cleanup)"))
    # the transition kernel touches segment state only: the untouched
    # constraint set and offer provenance survive verbatim
    if released.hard_constraints != plan.hard_constraints:
        results.append(fail(name + "_constraints_stable", "constraints changed across a transition"))
    else:
        results.append(ok(name + "_constraints_stable", "constraints verbatim across transitions"))
    bad = [entry for entry in results if not entry[1]]
    if bad:
        return fail(bad[0][0], bad[0][2])
    return ok(
        name,
        "unknown segment / out-of-window engagement / malformed instant / "
        "unknown target / non-plan all fail closed; release past expiry is "
        "legal cleanup; constraints stable (LOCK-108)",
    )


# ---------------------------------------------------------------------------
# (e) Canonical round-trips + deterministic ids
# ---------------------------------------------------------------------------


def case_23_canonical_round_trips() -> Result:
    name = "case_23_canonical_round_trips"
    problems: List[str] = []
    plan = _plan()
    document = plan.to_dict()
    rebuilt = ExecutionPlan.from_dict(document)
    if rebuilt.to_dict() != document:
        problems.append("the plan round-trip is not byte-stable")
    if rebuilt.canonical_bytes() != plan.canonical_bytes():
        problems.append("the canonical bytes differ after the round-trip")
    if json.loads(json.dumps(document)) != document:
        problems.append("stdlib JSON round-trip diverged")
    segment = plan.segments[0].to_dict()
    rebuilt_segment = ExecutionSegment.from_dict(segment)
    if rebuilt_segment.to_dict() != segment:
        problems.append("the segment round-trip is not byte-stable")
    # round-trip preserves the transitioned states, too
    advanced = apply_segment_transition(
        plan, plan.segments[0].segment_id, "RESERVED", at_instant=T0
    )
    advanced_document = advanced.to_dict()
    if ExecutionPlan.from_dict(advanced_document).to_dict() != advanced_document:
        problems.append("the transitioned plan round-trip is not byte-stable")
    # deserialization tamper evidence
    tampered = dict(document)
    tampered["plan_id"] = "sha256:" + "0" * 64
    try:
        ExecutionPlan.from_dict(tampered)
        problems.append("a tampered plan_id deserialized")
    except ExecutionPlanError as error:
        if error.code != ExecutionPlanReason.ID_MISMATCH:
            problems.append("tampered id: wrong code %s" % error.code)
    tampered_state = json.loads(json.dumps(document))
    tampered_state["segments"][0]["state"] = "DEGRADED"
    try:
        ExecutionPlan.from_dict(tampered_state)
        problems.append("an illegal segment state deserialized")
    except ExecutionPlanError as error:
        if error.code != ExecutionPlanReason.VOCABULARY:
            problems.append("illegal state: wrong code %s" % error.code)
    # the SegmentInput proposal record round-trips (optimizer evidence)
    proposal = _segment_input().to_dict()
    if SegmentInput.from_dict(proposal).to_dict() != proposal:
        problems.append("the segment-input round-trip is not byte-stable")
    if problems:
        return fail(name, "; ".join(problems))
    return ok(
        name,
        "plan/segment/input round-trips byte-stable (canonical JSON); tampered "
        "ids and illegal states fail closed at the boundary",
    )


def case_24_deterministic_ids() -> Result:
    name = "case_24_deterministic_ids"
    problems: List[str] = []
    import re as _re

    id_pattern = _re.compile(r"^sha256:[0-9a-f]{64}$")
    plan = _plan()
    if id_pattern.fullmatch(plan.plan_id) is None:
        problems.append("the plan id is not sha256 grammar")
    if id_pattern.fullmatch(plan.segments[0].segment_id) is None:
        problems.append("the segment id is not sha256 grammar")
    if id_pattern.fullmatch(plan.constraint_fingerprint) is None:
        problems.append("the constraint fingerprint is not sha256 grammar")
    if derive_plan_id(plan) != plan.plan_id:
        problems.append("plan id re-derivation disagrees")
    if derive_segment_id(plan.segments[0]) != plan.segments[0].segment_id:
        problems.append("segment id re-derivation disagrees")
    # re-translation of the same inputs produces the identical plan
    again = _plan()
    if again.plan_id != plan.plan_id or again.canonical_bytes() != plan.canonical_bytes():
        problems.append("re-translation diverged")
    # distinct segment cores on the same contract produce distinct ids
    complex_plan = translate_contract(
        _contract(_constraints("latency-bound")),
        _complex_inputs(),
        provenance=_prov("optimizer:baseline-v1"),
    )
    if len({segment.segment_id for segment in complex_plan.segments}) != len(
        complex_plan.segments
    ):
        problems.append("distinct cores collided on ids")
    # the same core proposed under a different role is a DIFFERENT segment
    if problems:
        return fail(name, "; ".join(problems))
    return ok(
        name,
        "content-derived sha256 ids for plan/segment/fingerprint; "
        "re-derivation agrees; re-translation is byte-identical; distinct "
        "cores never collide",
    )


def case_25_cross_process_determinism() -> Result:
    name = "case_25_cross_process_determinism"
    probe = r"""
import sys
sys.path.insert(0, %r)
from contracts import (
    ContractStore, CreateContract, ConnectivityPrincipal, BeneficiaryScope,
    OpaqueReference, Provenance, ValidityInterval, HardConstraint,
    TerminationRules, SelectOffers, ActivateContract,
)
from offers import (
    OfferExchange, build_advertisement, build_offer, AdvertisementEntry,
    AdvertisementRef, OfferCommitment, OfferPricing, ServiceBoundary,
    offer_reference,
)
from executionplans import (
    SegmentInput, translate_contract, verify_plan_preserves_contract,
    apply_segment_transition, conformance_document, conformance_digest,
)
T0 = "2026-10-01T00:00:00Z"
T_END = "2026-11-01T00:00:00Z"
PROVIDER_A = "adcos:node:identity.sha256-hmac-dev.v1:" + "1" * 64
PROVIDER_B = "adcos:node:identity.sha256-hmac-dev.v1:" + "2" * 64
def prov(issuer, *refs):
    return Provenance(issuer=issuer, decision_refs=tuple(refs))
exchange = OfferExchange()
refs = {}
for provider, key in (
    (PROVIDER_A, "offer:netpro-basic-1"),
    (PROVIDER_B, "offer:skywave-mesh-1"),
    (PROVIDER_B, "offer:skywave-failover-1"),
):
    issuer = "prov:" + ("netpro" if provider == PROVIDER_A else "skywave")
    adv = build_advertisement(
        provider=provider,
        entries=(AdvertisementEntry(capability_id="capability.core.multipath", schema_version="1.2", statement_digest="sha256:" + "a" * 64, classification="known"),),
        validity=ValidityInterval(not_before=T0, not_after=T_END),
        provenance=prov(issuer),
    )
    offer = build_offer(
        provider=provider, provider_offer_key=key, schema_version=1,
        advertisements=(AdvertisementRef(advertisement_id=adv.advertisement_id, provenance=prov(issuer)),),
        commitments=(OfferCommitment(kind="latency-bound-ms", params={"max_ms": 150}, window=ValidityInterval(not_before=T0, not_after=T_END), provenance=prov(issuer)),),
        pricing=OfferPricing(currency="USD", price_minor=250, price_exponent=2, billing_mode="flat", provenance=prov(issuer)),
        service_boundaries=(ServiceBoundary(jurisdiction="GH", geography_refs=("mpcell:v1:coarse-50000m:12:-1",), provenance=prov(issuer)),),
        validity=ValidityInterval(not_before=T0, not_after=T_END),
        provenance=prov(issuer),
    )
    exchange.register_advertisement(adv)
    exchange.register_offer(offer)
    refs[key] = offer_reference(offer)
store = ContractStore()
cmd = CreateContract(
    principal=ConnectivityPrincipal(principal_kind="APPLICATION", principal_ref="app:sharenet-gw-01"),
    beneficiaries=(BeneficiaryScope(beneficiary_kind="DEVICE", beneficiary_ref="dev:pi-7f2a"),),
    requirements=(OpaqueReference(ref_kind="intent-requirements", value="intent:abc123", provenance=prov("arch:sharenet")),),
    hard_constraints=(HardConstraint(kind="latency-bound", params={"max_ms": 150}, provenance=prov("prov:netpro")),),
    validity=ValidityInterval(not_before=T0, not_after=T_END),
    service_properties=(OpaqueReference(ref_kind="service-property", value="prop:committed-1", provenance=prov("prov:netpro")),),
    usage_pricing_terms=OpaqueReference(ref_kind="usage-pricing-terms", value="terms:comm-42", provenance=prov("comm:ops")),
    assurance_obligations=(OpaqueReference(ref_kind="assurance-obligation", value="oblig:evid-7"),),
    execution_scope=(OpaqueReference(ref_kind="execution-scope", value="scope:exec-default"),),
    termination=TerminationRules(conditions=("principal-requested",), compensation=OpaqueReference(ref_kind="compensation", value="comp:rule-9", provenance=prov("comm:ops"))),
    provenance=prov("arch:sharenet", "dec:elig-1"),
)
result = store.submit(cmd, recorded_at="2026-09-30T10:00:00Z")
cid = result.contract.contract_id
store.submit(SelectOffers(offers=tuple(refs.values())), recorded_at="2026-09-30T10:05:00Z", contract_id=cid)
store.submit(ActivateContract(activated_at=T0, signature_refs=(OpaqueReference(ref_kind="signature", value="sig:ed25519-1"),)), recorded_at=T0, contract_id=cid)
contract = store.contract(cid)
segments = (
    SegmentInput(offer_reference=refs["offer:skywave-mesh-1"], role="primary", operations=("reserve", "activate", "measure", "release"), provenance=prov("optimizer:baseline-v1", "dec:opt-3")),
    SegmentInput(offer_reference=refs["offer:netpro-basic-1"], role="primary", operations=("reserve", "activate", "measure", "release"), provenance=prov("optimizer:baseline-v1", "dec:opt-1")),
    SegmentInput(offer_reference=refs["offer:skywave-failover-1"], role="access", operations=("reserve", "activate"), provenance=prov("optimizer:baseline-v1", "dec:opt-2")),
    SegmentInput(offer_reference=refs["offer:netpro-basic-1"], role="alternative", operations=("reserve", "activate", "release"), provenance=prov("optimizer:baseline-v1", "dec:opt-4")),
)
plan = translate_contract(contract, segments, provenance=prov("optimizer:baseline-v1"))
advanced = apply_segment_transition(plan, plan.segments[0].segment_id, "RESERVED", at_instant=T0)
verify_plan_preserves_contract(plan, contract)
document = conformance_document(plan, contract)
print(plan.plan_id)
print(advanced.plan_id)
print(conformance_digest(document))
""" % (str(REPO_ROOT),)
    outputs: List[str] = []
    for seed in ("0", "1", "42"):
        env = {"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"}
        proc = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            env=env,
        )
        if proc.returncode != 0:
            return fail(
                name,
                "probe subprocess exit %d: %s" % (proc.returncode, proc.stderr[-200:]),
            )
        outputs.append(proc.stdout)
    if len(set(outputs)) != 1:
        return fail(name, "PYTHONHASHSEED variation changed the plan id or digest")
    return ok(
        name,
        "byte-identical plan ids and conformance digests across PYTHONHASHSEED "
        "0/1/42 subprocesses (deterministic, offline, seeded)",
    )


# ---------------------------------------------------------------------------
# (f) Provenance resolves to the REAL contract and offer objects
# ---------------------------------------------------------------------------


def case_26_provenance_resolves() -> Result:
    name = "case_26_provenance_resolves"
    contract = _contract(_constraints("latency-bound"))
    plan = translate_contract(
        contract,
        _complex_inputs(),
        provenance=_prov("optimizer:baseline-v1", "dec:opt-plan"),
    )
    problems: List[str] = []
    store, cid = _mature_store(_constraints("latency-bound"))
    # the plan attribution resolves to the real contract object
    resolved_contract = store.contract(plan.contract_id)
    if resolved_contract.contract_id != cid or resolved_contract.state != "CONTRACT_ACTIVE":
        problems.append("the plan attribution does not resolve to the real contract")
    # every segment offer reference resolves to the real offer record
    exchange = _exchange()
    for i, segment in enumerate(plan.segments):
        record = exchange.resolve(segment.offer_reference, at_instant=T2)
        if record.offer_id != segment.offer_reference.value:
            problems.append("segment %d does not resolve to its offer" % i)
        if segment.offer_reference not in contract.accepted_offers:
            problems.append("segment %d is not a verbatim accepted reference" % i)
    # the offers authority's own contract-side verification passes
    try:
        resolved = verify_accepted_offers(contract, exchange, at_instant=T2)
        if tuple(record.offer_id for record in resolved) != tuple(
            reference.value for reference in contract.accepted_offers
        ):
            problems.append("verify_accepted_offers resolved a different set")
    except Exception as error:  # noqa: BLE001
        problems.append("verify_accepted_offers failed: %s" % str(error)[:80])
    # LOCK-118: provenance issuers preserved on plan and segments
    if plan.provenance.issuer != "optimizer:baseline-v1":
        problems.append("the plan provenance issuer was lost")
    if not plan.provenance.decision_refs:
        problems.append("the plan provenance carries no decision refs")
    if any(
        segment.provenance.issuer != "optimizer:baseline-v1"
        for segment in plan.segments
    ):
        problems.append("a segment lost its planning provenance")
    if problems:
        return fail(name, "; ".join(problems))
    return ok(
        name,
        "plan.contract_id resolves to the real stored contract; every segment "
        "offer reference resolves through the real exchange to the real "
        "OfferRecord; issuers and decision refs preserved (LOCK-118)",
    )


def case_27_plan_reference_is_data() -> Result:
    name = "case_27_plan_reference_is_data"
    plan = _plan()
    contract = _contract(_constraints("latency-bound"))
    store, cid = _mature_store(_constraints("latency-bound"))
    reference = plan_reference(plan)
    problems: List[str] = []
    if reference.ref_kind != "execution-artifact":
        problems.append("the plan reference is not the execution-artifact kind")
    if reference.value != plan.plan_id:
        problems.append("the plan reference does not carry the plan id")
    if reference.provenance is None:
        problems.append("the plan reference carries no provenance (LOCK-118)")
    # LOCK-117: binding the plan as DATA never changes contract identity or
    # state; there is no path that turns the artifact into an authority
    bound = store.submit(
        BindExecutionArtifact(artifact=reference), recorded_at=T1, contract_id=cid
    )
    if bound.contract.contract_id != cid:
        problems.append("binding changed the contract identity")
    if bound.contract.state != contract.state:
        problems.append("binding changed the contract state")
    if bound.contract.hard_constraints != contract.hard_constraints:
        problems.append("binding changed the contract constraints (LOCK-108)")
    if reference not in bound.contract.execution_artifacts:
        problems.append("the plan reference did not bind as artifact data")
    if plan.plan_id not in [artifact.value for artifact in bound.contract.execution_artifacts]:
        problems.append("the bound artifact value is not the plan id")
    if problems:
        return fail(name, "; ".join(problems))
    return ok(
        name,
        "the plan rides as an opaque execution-artifact reference; binding "
        "changes no identity, state, or constraint — artifacts are data, "
        "never authorities (LOCK-117/LOCK-108)",
    )


# ---------------------------------------------------------------------------
# (g) The composition harvest seam
# ---------------------------------------------------------------------------


def _origin_main_available() -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "origin/main"],
        capture_output=True,
        cwd=str(REPO_ROOT),
    )
    return proc.returncode == 0


def _composition_all_on_origin_main() -> Optional[List[str]]:
    proc = subprocess.run(
        ["git", "show", "origin/main:composition/__init__.py"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    if proc.returncode != 0:
        return None
    try:
        tree = ast.parse(proc.stdout)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        return [
                            element.value
                            for element in node.value.elts
                            if isinstance(element, ast.Constant)
                        ]
    return None


def case_28_composition_harvest_seam() -> Result:
    name = "case_28_composition_harvest_seam"
    problems: List[str] = []
    try:
        import composition  # noqa: F401
        from composition.chain import ChainVerdict  # noqa: F401
        from composition import (  # noqa: F401
            CompositionWorld,
            run_full_chain,
            w048_runtime_absent,
        )
    except Exception as error:  # noqa: BLE001
        return fail(name, "composition import failed: %s" % str(error)[:80])

    # WORK-048 stays accepted-not-restored (never implicitly restored
    # by the M006 harvest)
    if not w048_runtime_absent():
        problems.append("W048 is no longer absent-fail-closed (implicit restoration)")

    # the frozen WORK-054 verdict discipline: BLOCKED_MISSING_AUTHORITY
    # is the only reachable verdict; no passing-production verdict exists
    if ChainVerdict.values() != ("BLOCKED_MISSING_AUTHORITY",):
        problems.append("the composition verdict vocabulary drifted (DEC-0085/DEC-0086)")

    # the conformance chain still runs fail-closed: the trace blocks at
    # the containment edge and never claims a production composition
    world = CompositionWorld()
    chain = run_full_chain(world)
    trace = chain.trace
    if trace.verdict != "BLOCKED_MISSING_AUTHORITY":
        problems.append("the chain verdict is %s" % trace.verdict)
    if trace.production_composition is not False:
        problems.append("the trace claims a production composition")
    fail_closed = trace.fail_closed_edges()
    if not fail_closed or all(
        edge.reason != "w048-runtime-absent-fail-closed" for edge in fail_closed
    ):
        problems.append("the chain no longer fails closed at the containment edge")

    # the plan bridge is the canonical 1.1 bridge over the REAL contract
    # authority (the composition layer's 1.0-era chain and the 1.1 plan
    # bridge coexist; the bridge is where translation lives)
    plan = _plan()
    contract = _contract(_constraints("latency-bound"))
    verify_plan_preserves_contract(plan, contract)
    document = conformance_document(plan, contract)
    digest = conformance_digest(document)

    # the conformance-evidence pattern lineage: both sides mint
    # sha256-prefixed digests over canonical JSON (WORK-003 convention)
    if not digest.startswith("sha256:"):
        problems.append("the plan conformance digest is not sha256 grammar")
    if not trace.digest().startswith("sha256:"):
        problems.append("the composition trace digest is not sha256 grammar")
    if document.get("evidence_class") != "SOFTWARE":
        problems.append("the plan conformance document is not SOFTWARE class")
    if PLAN_BRIDGE_DISCLAIMER not in document.get("disclaimer", ""):
        problems.append("the plan conformance disclaimer is absent")
    if "WORK-054" not in document.get("harvest_disclosure", ""):
        problems.append("the harvest disclosure is absent")
    if "BLOCKED_MISSING_AUTHORITY" not in PLAN_BRIDGE_DISCLAIMER:
        problems.append("the disclaimer does not disclose the blocked chain")

    # the derived document is deterministic (pure function of plan+contract)
    if conformance_document(plan, contract) != document:
        problems.append("the conformance document is not deterministic")

    # no second authority on either side: the plan binds as artifact data
    # only (case_28) and the composition trace stays non-authoritative
    # (production_composition False — asserted above)

    # the composition public API surface is preserved by the harvest
    # (docstring-only delta: the pinned export table is unchanged)
    if _origin_main_available():
        origin_all = _composition_all_on_origin_main()
        if origin_all is None:
            problems.append("cannot extract composition __all__ on origin/main")
        elif sorted(origin_all) != sorted(composition.__all__):
            problems.append(
                "the composition public API drifted from origin/main: %s"
                % sorted(set(origin_all) ^ set(composition.__all__))
            )
    if problems:
        return fail(name, "; ".join(problems))
    return ok(
        name,
        "the WORK-054 chain still blocks fail-closed (W048 absent, "
        "BLOCKED_MISSING_AUTHORITY, production_composition=False); the plan "
        "bridge is the canonical 1.1 translation; both sides mint WORK-003 "
        "digests; the export surface is unchanged; no second authority",
    )


def case_29_composition_battery_reruns() -> Result:
    name = "case_29_composition_battery_reruns"
    battery = REPO_ROOT / "tools" / "composition_selftest.py"
    if not battery.exists():
        return fail(name, "tools/composition_selftest.py is missing")
    proc = subprocess.run(
        [sys.executable, str(battery)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    if proc.returncode != 0:
        return fail(
            name,
            "the composition battery failed at the delivery head (rc=%d): %s"
            % (proc.returncode, proc.stdout[-300:]),
        )
    if "Result: PASS (55/55 cases passed)" not in proc.stdout:
        return fail(
            name,
            "the composition battery passed with an unexpected count: %s"
            % proc.stdout.strip().splitlines()[-1][:120],
        )
    return ok(
        name,
        "the harvested WORK-054 surface re-runs its own battery green at the "
        "accepted 55/55 on the M006 delivery head (the frozen DEC-0085/"
        "DEC-0086 contract is preserved by the harvest)",
    )


# ---------------------------------------------------------------------------
# (h) Optimizer replaceability (LOCK-111)
# ---------------------------------------------------------------------------


def case_30_optimizer_replaceability() -> Result:
    name = "case_30_optimizer_replaceability"
    contract = _contract(_constraints("latency-bound"))
    inputs = _complex_inputs()
    problems: List[str] = []
    # same proposal set in a different input order, same declared rule ->
    # the byte-identical plan (order normalization; never wall-clock)
    plan_one = translate_contract(
        contract, inputs, provenance=_prov("optimizer:one")
    )
    plan_two = translate_contract(
        contract, tuple(reversed(inputs)), provenance=_prov("optimizer:one")
    )
    if plan_one.plan_id != plan_two.plan_id:
        problems.append("input order changed the plan id")
    if plan_one.canonical_bytes() != plan_two.canonical_bytes():
        problems.append("input order changed the canonical bytes")
    # a different declared rule is deterministic and recorded (a
    # different ordering is a different plan — disclosed, not ambiguous)
    plan_offer_first = translate_contract(
        contract,
        inputs,
        provenance=_prov("optimizer:one"),
        tie_break=("offer", "role", "segment-id"),
    )
    roles_default = [segment.role for segment in plan_one.segments]
    roles_offer_first = [segment.role for segment in plan_offer_first.segments]
    if roles_default == roles_offer_first:
        problems.append("the two declared rules produced the identical order")
    if plan_offer_first.tie_break != ("offer", "role", "segment-id"):
        problems.append("the declared rule was not recorded on the plan")
    if plan_offer_first.plan_id == plan_one.plan_id:
        problems.append("different declared rules collided on the plan id")
    # re-declaring the same rule reproduces the same alternative order
    plan_offer_first_again = translate_contract(
        contract,
        tuple(reversed(inputs)),
        provenance=_prov("optimizer:one"),
        tie_break=("offer", "role", "segment-id"),
    )
    if plan_offer_first_again.canonical_bytes() != plan_offer_first.canonical_bytes():
        problems.append("the declared-rule order is not reproducible")
    # the authority-true shape is invariant under both optimizers and
    # both rules (LOCK-111: optimizers never override the authority)
    for candidate in (plan_one, plan_offer_first):
        if candidate.contract_id != contract.contract_id:
            problems.append("attribution drifted under a declared rule")
        if candidate.constraint_fingerprint != contract.hard_constraint_fingerprint():
            problems.append("the fingerprint drifted under a declared rule")
        if candidate.validity != contract.validity:
            problems.append("the validity drifted under a declared rule")
    # the rule omitted by the caller is completed with the total order
    plan_completed = translate_contract(
        contract, inputs, provenance=_prov("optimizer:one"), tie_break=("role",)
    )
    if plan_completed.tie_break != ("role", "segment-id"):
        problems.append("the total-order key was not appended")
    if problems:
        return fail(name, "; ".join(problems))
    return ok(
        name,
        "input order never changes the plan; declared rules are recorded, "
        "deterministic and reproducible; the authority-true shape (attribution/"
        "constraints/validity) is invariant; omitted total-order keys are "
        "completed (LOCK-111, never wall-clock)",
    )


def case_31_tie_break_validation() -> Result:
    name = "case_31_tie_break_validation"
    contract = _contract(_constraints("latency-bound"))
    results: List[Result] = []
    results.append(
        expect_error(
            name + "_unknown_key",
            ExecutionPlanReason.VOCABULARY,
            lambda: translate_contract(
                contract,
                (_segment_input(),),
                provenance=_prov("optimizer:x"),
                tie_break=("role", "wall-clock"),
            ),
        )
    )
    results.append(
        expect_error(
            name + "_repeated_key",
            ExecutionPlanReason.TIE_BREAK_INVALID,
            lambda: translate_contract(
                contract,
                (_segment_input(),),
                provenance=_prov("optimizer:x"),
                tie_break=("role", "role", "segment-id"),
            ),
        )
    )
    # a stored (serialized) rule that is not total-order fails closed at
    # the plan construction boundary (the translator AUTO-completes; the
    # record itself must be complete)
    non_total = _plan().to_dict()
    non_total["tie_break"] = ["offer", "role"]
    results.append(
        expect_error(
            name + "_not_total",
            ExecutionPlanReason.TIE_BREAK_INVALID,
            lambda: ExecutionPlan.from_dict(non_total),
        )
    )
    results.append(
        expect_error(
            name + "_empty",
            ExecutionPlanReason.INVALID_INPUT,
            lambda: translate_contract(
                contract,
                (_segment_input(),),
                provenance=_prov("optimizer:x"),
                tie_break=(),
            ),
        )
    )
    # the vocabulary is content-only: no temporal key exists to declare
    if any(key in TIE_BREAK_KEYS for key in ("instant", "time", "clock", "date")):
        results.append(fail(name + "_no_temporal_keys", "a temporal tie-break key exists"))
    else:
        results.append(ok(name + "_no_temporal_keys", "no temporal tie-break key exists (content keys only)"))
    bad = [entry for entry in results if not entry[1]]
    if bad:
        return fail(bad[0][0], bad[0][2])
    return ok(
        name,
        "unknown/repeated/non-total/empty tie-break rules fail closed; the "
        "key vocabulary is content-only (never wall-clock) (LOCK-111)",
    )


# ---------------------------------------------------------------------------
# The conformance document discipline (the harvested evidence pattern)
# ---------------------------------------------------------------------------


def case_32_conformance_document_discipline() -> Result:
    name = "case_32_conformance_document_discipline"
    contract = _contract(_constraints("latency-bound"))
    plan = _plan()
    document = conformance_document(plan, contract)
    problems: List[str] = []
    # the harvested chain-orchestration shape: an ordered typed step
    # sequence attributed to segments
    sequence = document["execution_sequence"]
    expected_pairs = execution_sequence(plan)
    if [
        (step["segment_id"], step["operation"]) for step in sequence
    ] != list(expected_pairs):
        problems.append("the execution sequence does not match the plan")
    if [step["step"] for step in sequence] != list(range(1, len(sequence) + 1)):
        problems.append("the steps are not 1-based ordered")
    # the fail-closed evidence gate: a weakened plan produces NO document
    weak_contract = _contract(
        (
            HardConstraint(
                kind="latency-bound",
                params={"max_ms": 999},
                provenance=_prov("prov:netpro"),
            ),
        )
    )
    weak_plan = translate_contract(
        weak_contract, (_segment_input(),), provenance=_prov("optimizer:baseline-v1")
    )
    try:
        conformance_document(weak_plan, contract)
        problems.append("a weakened plan produced conformance evidence")
    except ExecutionPlanError as error:
        if error.code != ExecutionPlanReason.CONSTRAINT_WEAKENED:
            problems.append("wrong code %s from the evidence gate" % error.code)
    # derived data follows the plan value: a state transition is
    # reflected, deterministically
    advanced = apply_segment_transition(
        plan, plan.segments[0].segment_id, "RESERVED", at_instant=T0
    )
    advanced_document = conformance_document(advanced, contract)
    if advanced_document["segments"][0]["state"] != "RESERVED":
        problems.append("the document does not reflect the segment state")
    if conformance_digest(advanced_document) == conformance_digest(document):
        problems.append("the digest ignores the derived state change")
    if problems:
        return fail(name, "; ".join(problems))
    return ok(
        name,
        "ordered typed execution sequence; no evidence over a weakened plan "
        "(LOCK-108 gate inside); derived data follows the plan state "
        "deterministically (the harvested conformance-evidence pattern)",
    )


# ---------------------------------------------------------------------------
# AST audits: clock + import discipline (LOCK-110/117/119)
# ---------------------------------------------------------------------------


def case_33_clock_and_import_discipline() -> Result:
    name = "case_33_clock_and_import_discipline"
    problems: List[str] = []
    files = sorted((REPO_ROOT / "executionplans").glob("*.py"))
    if not files:
        return fail(name, "the executionplans/ package is missing")
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
        allowed = {
            "__future__",
            "contextlib",
            "hashlib",
            "re",
            "dataclasses",
            "typing",
            "protocol",
            "contracts",
            "executionplans",
        }
        unexpected = sorted(imported - allowed)
        if unexpected:
            problems.append("%s imports %s" % (path.name, unexpected))
        # LOCK-110/LOCK-117: no provider SDK family, no offers resolution,
        # no composition dependency inside the domain (the harvest is
        # one-way; offers resolve through their own authority)
        forbidden_roots = {
            "offers",
            "composition",
            "adapters",
            "marketplace",
            "networkpath",
            "sessions",
            "payment",
            "commercial",
            "usage",
            "developerapi",
        }
        hit = sorted(imported & forbidden_roots)
        if hit:
            problems.append("%s imports forbidden root(s) %s" % (path.name, hit))
    if problems:
        return fail(name, "; ".join(problems[:6]))
    return ok(
        name,
        "executionplans/ imports only stdlib + protocol + contracts (by "
        "reference); no offers/composition/SDK family; no wall clock, "
        "randomness, UUIDs, or network (LOCK-110/117/119)",
    )


def case_34_lock_conformance_mapping() -> Result:
    name = "case_34_lock_conformance_mapping"
    plan = _plan()
    contract = _contract(_constraints("latency-bound"))
    complex_plan = translate_contract(
        contract, _complex_inputs(), provenance=_prov("optimizer:baseline-v1")
    )
    checks: Dict[str, bool] = {
        # LOCK-101: the contract is the authority; the plan never writes it
        "LOCK-101": isinstance(contract.state, str)
        and plan.contract_id == contract.contract_id,
        # LOCK-108: verbatim constraints + fingerprint equality
        "LOCK-108": plan.constraint_fingerprint == contract.hard_constraint_fingerprint()
        and [c.to_dict() for c in plan.hard_constraints]
        == [c.to_dict() for c in contract.hard_constraints],
        # LOCK-109: typed bridge with provenance-carrying references
        "LOCK-109": all(
            segment.offer_reference.provenance is not None
            for segment in complex_plan.segments
        )
        and plan.provenance is not None,
        # LOCK-110: capability-oriented operation names only
        "LOCK-110": all(
            operation in ADAPTER_OPERATIONS
            for segment in complex_plan.segments
            for operation in segment.operations
        ),
        # LOCK-111: declared deterministic tie-breaking
        "LOCK-111": plan.tie_break[-1] == "segment-id"
        and all(key in TIE_BREAK_KEYS for key in plan.tie_break),
        # LOCK-115: the simple single-segment deployment is valid
        "LOCK-115": len(plan.segments) == 1 and plan.segments[0].role == "primary",
        # LOCK-116: multi-provider composition under one contract
        "LOCK-116": len(complex_plan.segments) == 4
        and complex_plan.contract_id == contract.contract_id,
        # LOCK-117: the plan rides as an execution-artifact reference
        "LOCK-117": plan_reference(plan).ref_kind == "execution-artifact",
        # LOCK-118: issuer + provenance on the plan and every segment
        "LOCK-118": plan.provenance.issuer != ""
        and all(
            segment.provenance.issuer != "" for segment in complex_plan.segments
        ),
        # LOCK-119: secret rejection exists in the frozen reason vocabulary
        "LOCK-119": ExecutionPlanReason.SECRET_REJECTED
        in ExecutionPlanReason.values(),
    }
    missing = sorted(lock for lock, held in checks.items() if not held)
    if missing:
        return fail(name, "locks not evidenced: %s" % missing)
    return ok(
        name,
        "LOCK-101/108/109/110/111/115/116/117/118/119 evidenced on the plan "
        "bridge (simple and complex deployments)",
    )


# ---------------------------------------------------------------------------
# PR delta shape + evidence doc honesty (the M005 battery conventions)
# ---------------------------------------------------------------------------


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
        "delta confined to the M006 scope (%d file(s): executionplans/ + the "
        "composition harvest disclosure + battery + evidence doc)" % len(delta),
    )


def case_36_evidence_doc_honest() -> Result:
    name = "case_36_evidence_doc_honest"
    path = REPO_ROOT / "docs" / "M006-evidence.md"
    if not path.exists():
        return fail(name, "docs/M006-evidence.md is missing")
    text = path.read_text(encoding="utf-8")
    problems: List[str] = []
    if "SOFTWARE" not in text:
        problems.append("the evidence class is not disclosed")
    if "M006" not in text:
        problems.append("the evidence does not name M006")
    if "LOCK-108" not in text or "LOCK-109" not in text:
        problems.append("the lock mapping is not disclosed")
    if "PLANNED" not in text or "RELEASED" not in text:
        problems.append("the segment state vocabulary is not disclosed")
    if "harvest" not in text.lower():
        problems.append("the composition harvest is not disclosed")
    # an AFFIRMATIVE physical-verification claim is rejected; a negation is
    # the required honesty statement (window-based so wrapped lines cannot
    # split the negation from the phrase)
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
    if problems:
        return fail(name, "; ".join(problems))
    return ok(
        name,
        "the evidence matrix discloses SOFTWARE class, the lock mapping, the "
        "state vocabulary, the harvest, and no affirmative physical claims",
    )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    results: List[Result] = []
    results.append(case_01_frozen_vocabularies())
    results.append(case_02_simple_translation())
    results.append(case_03_complex_translation())
    results.append(case_04_plannable_state_matrix())
    results.append(case_05_translation_inputs_fail_closed())
    results.append(case_06_plan_window_containment())
    results.extend(_lock108_kind_cases())
    results.append(case_19_lock108_no_override_surface())
    results.append(case_20_segment_state_legal_path())
    results.append(case_21_segment_state_illegal_matrix())
    results.append(case_22_segment_transition_discipline())
    results.append(case_23_canonical_round_trips())
    results.append(case_24_deterministic_ids())
    results.append(case_25_cross_process_determinism())
    results.append(case_26_provenance_resolves())
    results.append(case_27_plan_reference_is_data())
    results.append(case_28_composition_harvest_seam())
    results.append(case_29_composition_battery_reruns())
    results.append(case_30_optimizer_replaceability())
    results.append(case_31_tie_break_validation())
    results.append(case_32_conformance_document_discipline())
    results.append(case_33_clock_and_import_discipline())
    results.append(case_34_lock_conformance_mapping())
    results.append(case_35_pr_delta_shape_authorized_scope())
    results.append(case_36_evidence_doc_honest())

    for name, passed, detail in results:
        print("[%s] %-56s %s" % ("ok  " if passed else "FAIL", name, detail))
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
