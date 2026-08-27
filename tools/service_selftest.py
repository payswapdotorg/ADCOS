#!/usr/bin/env python3
"""ADCOS service registry / edge compute self-test (WORK-025).

The focused verification battery for the ``services`` layer, mapping
every WORK-025 handoff verification item to a discriminating case:

- identity separation (service != node/session/path/resource/
  federation identity) and host-change stability  -> case_02
- deterministic, repeat-safe registration           -> case_03
- advertisement validity + provenance evidence      -> case_04
- stale/expired/withdrawn fail-closed states         -> case_05
- capability/intent-aware discovery, no routes       -> case_06
- local-first discovery with upstream absent         -> case_07
- local execution through the provider seam         -> case_08
- unauthorized execution fails before provider side
  effects                                            -> case_09
- execution/provider failures isolated and typed    -> case_10
- WORK-008 capacity DATA; advertisement != reservation -> case_11
- exhaustion/failure leaves authoritative state unchanged -> case_12
- placement host change with stable ServiceID       -> case_13
- placement transition recorded and auditable       -> case_14
- session identity stable across relocation         -> case_15
- federation-scoped visibility, no leak/trust       -> case_16
- removing exposure preserves the local record      -> case_17
- tenant/domain isolation                           -> case_18
- secrets never in records/bytes/results/errors     -> case_19
- least-authority execution context                 -> case_20
- no second authority; no vendor symbols (AST)      -> case_21
- validate/commit sequence discipline               -> case_22
- canonical state free of diagnostics               -> case_23
- determinism (repeated runs + hash seeds)          -> case_24
- frozen spec/ byte-identical                       -> case_25
- py_compile clean                                  -> case_26
- policy negative matrix                            -> case_27
- policy change between discovery and execution     -> case_28
- tombstone replay protection                       -> case_29
- REAL authority composition (W009/W010/W012/W015)  -> case_30
- observation honesty                               -> case_31
- no core leakage (reverse audit)                   -> case_32
- known-but-unavailable-at-execution                -> case_33
- step-budget isolation                             -> case_34
- vocabulary cross-checks vs the authorities        -> case_35
- registration conflict / host guard                -> case_36
- CI wiring                                         -> case_37
- tenant scope fail-closed on query (PR #26 B1)     -> case_18
- decision-bound invocation scope / anti-rebinding
  (PR #26 B2)                                       -> case_27, case_38
- peer-claim fingerprint semantics (PR #26 B3)     -> case_39
- NO services minting capability: a genuine UNBOUND
  WORK-010 ALLOW cannot be converted into
  authorization for an arbitrary scope (PR #26 B2,
  remediation 2 -- comment 5434924645; the binding
  is born at the WORK-010 evaluator)                -> case_38, case_40, case_21
- MONOTONIC advertisement lineage: older claims
  rejected, equal-time different-content claims
  conflict explicitly (PR #26 review 3, finding 1) -> case_41
- discovery authorization bound to the discovering
  caller/session/tenant with EXACT scope equality
  (PR #26 review 3, finding 2; negative coverage
  for a decision belonging to another
  caller/session)                                    -> case_42
- a later DENY invalidates an earlier standing
  ALLOW for the same scope (decision-lineage
  revocations; PR #26 review 3, finding 3)          -> case_27, case_43
- EXPLICIT cleanup outcomes: provider release
  failures become deterministic cleanup-pending
  admissions, surfaced on results, provable by
  retry; compensation failures and degraded
  terminal closure are explicit (PR #26 review 3,
  finding 4 + close observation)                     -> case_44
"""

from __future__ import annotations

import ast
import hashlib
import os
import py_compile
import re
import subprocess
import sys
from typing import Any, List, Mapping, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)

from services import (  # noqa: E402
    CONTEXT_SURFACE,
    CONTRACT_OPERATIONS,
    DEFAULT_STEP_BUDGET,
    FAILURE_THRESHOLD_DEGRADED,
    FAILURE_THRESHOLD_FAILED,
    SERVICES_PREFIX,
    SERVICE_CAPACITY_KINDS,
    SERVICE_DISCOVER_SCOPE,
    STEP_CHARGES,
    AdmissionState,
    AdvertisementEvidence,
    ExecutionProviderContract,
    FederationReader,
    InvocationDecision,
    ReferenceEdgeExecutor,
    SandboxedExecutionProvider,
    ServiceAdmission,
    ServiceAdvertisement,
    ServiceCapacity,
    ServiceCandidate,
    ServiceContext,
    ServiceDescriptor,
    ServiceError,
    ServiceEvent,
    ServiceEventType,
    ServiceLifecycle,
    ServiceObservation,
    ServiceReasonCode,
    ServiceRegistry,
    SessionReader,
    SessionView,
    VisibilityScope,
    derive_admission_ref,
    derive_advertisement_claim_digest,
    derive_decision_ref,
    derive_execution_ref,
    derive_exposure_ref,
    derive_service_ref,
    export_service_exposures,
    peer_claim_fingerprint,
)
from policy.evaluation import PolicyEngine  # noqa: E402
from policy.model import (  # noqa: E402
    Condition,
    Operation,
    PolicyContext,
    PolicyDecision,
    PolicyDomain,
    PolicyRule,
    PolicySet,
)
from protocol.canonicalization import canonical_json_bytes  # noqa: E402

Result = Tuple[str, bool, str]


def ok(name: str, detail: str = "") -> Result:
    return (name, True, detail)


def fail(name: str, detail: str) -> Result:
    return (name, False, detail)


# --------------------------------------------------------------------------
# Fixtures (deterministic; every instant is injected)
# --------------------------------------------------------------------------

_NOW = "2026-08-27T00:00:00Z"
_T1 = "2026-08-27T00:01:00Z"
_T2 = "2026-08-27T00:02:00Z"
_T3 = "2026-08-27T00:03:00Z"
_T4 = "2026-08-27T00:04:00Z"
_T5 = "2026-08-27T00:05:00Z"
_T6 = "2026-08-27T00:06:00Z"
_FRESH = "2027-01-01T00:00:00Z"
_EXPIRED = "2026-08-26T00:00:00Z"

_NODE_A = "adcos:node:test.profile.v1:" + "a" * 64
_NODE_B = "adcos:node:test.profile.v1:" + "b" * 64
_NODE_C = "adcos:node:test.profile.v1:" + "c" * 64
_NODE_UE = "adcos:node:test.profile.v1:" + "e" * 64

_SESSION_ID = "sha256:" + "1" * 64
_OTHER_SESSION_ID = "sha256:" + "2" * 64

_PAYLOAD = b"weather-request-v1"
_PAYLOAD_2 = b"telemetry-batch-42"


def _descriptor(
    name: str = "weather-cache",
    kind: str = "cache",
    tenant: str = "village-a",
    labels: Tuple[str, ...] = ("weather",),
    locality: Tuple[str, ...] = ("village-a",),
    privacy: Tuple[str, ...] = ("public",),
) -> ServiceDescriptor:
    return ServiceDescriptor(
        name=name,
        service_kind=kind,
        tenant_domain=tenant,
        capability_refs=(
            "capability.profile.service.%s" % (name.replace("_", "-"),),
        ),
        service_labels=labels,
        locality_labels=locality,
        privacy_labels=privacy,
    )


def _advertisement(
    descriptor: Optional[ServiceDescriptor] = None,
    host: str = _NODE_A,
    registered_at: str = _NOW,
    expires_at: str = _FRESH,
    visibility: str = VisibilityScope.TENANT,
    endpoint: str = "edge://slot-3",
    capacity: Optional[Tuple[ServiceCapacity, ...]] = None,
    policy_controlled: bool = False,
    federation_relationship_id: str = "",
) -> ServiceAdvertisement:
    if descriptor is None:
        descriptor = _descriptor()
    return ServiceAdvertisement(
        descriptor=descriptor,
        host_node_id=host,
        registered_at=registered_at,
        expires_at=expires_at,
        visibility=visibility,
        endpoint_ref=endpoint,
        capacity=(
            capacity
            if capacity is not None
            else (ServiceCapacity("edge-service-capacity", 2),)
        ),
        policy_controlled=policy_controlled,
        federation_relationship_id=federation_relationship_id,
    )


def _evidence(
    advertisement: ServiceAdvertisement,
    *,
    source_class: str = "direct-observation",
    observer: str = _NODE_A,
    reporter: str = _NODE_A,
    observed_at: str = _NOW,
    provenance: str = "local-edge-observation",
) -> AdvertisementEvidence:
    return AdvertisementEvidence(
        observer_node_id=observer,
        reporter_node_id=reporter,
        source_class=source_class,
        observed_at=observed_at,
        claim_digest=derive_advertisement_claim_digest(advertisement),
        provenance=provenance,
    )


def _allow_decision(
    evaluation_instant: str = _NOW,
    *,
    effect: str = "allow",
    decision_id: Optional[str] = None,
) -> PolicyDecision:
    """A genuine tamper-evident WORK-010 PolicyDecision for the
    WORK-012 session-composition leg (the probe trick: construct
    once, re-construct with the content-derived id -- the sanctioned
    selftest path).  NOTE: this is NOT the invocation-authorization
    path -- a service.invoke decision must come from the REAL engine
    (see _engine_invocation_decision), which binds the invocation
    scope at evaluation time."""
    probe = PolicyDecision(
        decision_id="0" * 64,
        effect=effect,
        code="allow" if effect == "allow" else "deny",
        detail="w025-selftest",
        matched_rule_ids=("service-allow",),
        policy_set_id="ps-services-1",
        policy_set_version=1,
        evaluation_instant=evaluation_instant,
    )
    real_id = decision_id if decision_id is not None else hashlib.sha256(
        probe.canonical_bytes()
    ).hexdigest()
    return PolicyDecision(
        decision_id=real_id,
        effect=effect,
        code="allow" if effect == "allow" else "deny",
        detail="w025-selftest",
        matched_rule_ids=("service-allow",),
        policy_set_id="ps-services-1",
        policy_set_version=1,
        evaluation_instant=evaluation_instant,
    )


# ----------------------------------------------------------------------
# REAL WORK-010 engine fixtures (the born-bound composition recipe:
# the invocation scope is declared in the evaluation context and the
# WORK-010 evaluator binds it into the decision -- there is no
# binding constructor anywhere in the services layer)
# ----------------------------------------------------------------------

_POLICY_ISSUER = "adcos:node:test.profile.v1:" + "0" * 64
_POLICY_VALID_FROM = "2026-01-01T00:00:00Z"
_POLICY_VALID_UNTIL = "2028-01-01T00:00:00Z"


def _invocation_policy_set(
    *, effect: str = "allow", domain_condition: bool = False,
) -> PolicySet:
    """A REAL WORK-010 PolicySet for service.invoke evaluations
    (issuer-bearing, windowed; optionally conditioning on the
    federation domain so rule evaluation is genuine)."""
    conditions: Tuple[Condition, ...] = ()
    if domain_condition:
        conditions = (
            Condition(
                predicate="federation-domain",
                arguments={"domain": "village-a"},
            ),
        )
    rule = PolicyRule(
        rule_id="svc-%s" % (effect,),
        domain=PolicyDomain.SERVICE,
        effect=effect,
        operation=Operation.SERVICE_INVOKE,
        conditions=conditions,
    )
    return PolicySet(
        set_id="ps-w025-invocation",
        version=1,
        rules=(rule,),
        issuer_node_id=_POLICY_ISSUER,
        valid_from=_POLICY_VALID_FROM,
        valid_until=_POLICY_VALID_UNTIL,
    )


def _invocation_descriptor(
    service_ref: str,
    *,
    session_id: str = "",
    caller_node_id: str = "",
    tenant_domain: str = "village-a",
) -> "dict[str, str]":
    """The invocation descriptor the composition root declares inside
    the evaluation context's extensions -- the exact (service,
    session, caller, tenant) scope being authorized."""
    return {
        "kind": "adcos.service-invocation",
        "operation": Operation.SERVICE_INVOKE,
        "service_ref": service_ref,
        "session_id": session_id,
        "caller_node_id": caller_node_id,
        "tenant_domain": tenant_domain,
    }


def _invocation_context(
    service_ref: str,
    *,
    evaluation_instant: str = _NOW,
    session_id: str = "",
    caller_node_id: str = "",
    tenant_domain: str = "village-a",
    descriptor: Optional[Mapping[str, Any]] = None,
) -> PolicyContext:
    """A REAL WORK-010 service.invoke PolicyContext carrying the
    invocation descriptor (the composition-root wiring: the first-class
    fields mirror the descriptor, exactly as the engine's derivation
    requires)."""
    if descriptor is None:
        descriptor = _invocation_descriptor(
            service_ref,
            session_id=session_id,
            caller_node_id=caller_node_id,
            tenant_domain=tenant_domain,
        )
    return PolicyContext(
        operation=Operation.SERVICE_INVOKE,
        requester_node_id=caller_node_id,
        evaluation_instant=evaluation_instant,
        federation_domain=tenant_domain,
        resource_refs=(service_ref,),
        extensions=(descriptor,),
    )


def _engine_invocation_decision(
    service_ref: str,
    *,
    evaluation_instant: str = _NOW,
    session_id: str = "",
    caller_node_id: str = "",
    tenant_domain: str = "village-a",
    effect: str = "allow",
    domain_condition: bool = False,
) -> PolicyDecision:
    """A GENUINE WORK-010 engine decision for a real service.invoke
    context -- BORN BOUND to the exact invocation scope (the only way
    a service.invoke decision can exist: the engine derives the
    digest-covered binding from the context's own descriptor)."""
    context = _invocation_context(
        service_ref,
        evaluation_instant=evaluation_instant,
        session_id=session_id,
        caller_node_id=caller_node_id,
        tenant_domain=tenant_domain,
    )
    result = PolicyEngine().evaluate(
        _invocation_policy_set(
            effect=effect, domain_condition=domain_condition,
        ),
        context,
    )
    assert result.ok and result.decision is not None, result.detail
    return result.decision


def _unbound_allow(evaluation_instant: str = _NOW) -> PolicyDecision:
    """A GENUINE WORK-010 engine ALLOW for a NON-service.invoke
    operation (resource.consume) -- genuinely UNBOUND: the engine
    binds invocation scopes only onto service.invoke decisions, so
    this decision carries no invocation binding anywhere.  This is
    the attacker's starting point for the no-minting regression
    (case_38): an authorization that WORK-010 genuinely granted, for
    a scope the services layer must never be able to re-target."""
    policy_set = PolicySet(
        set_id="ps-w025-unbound",
        version=1,
        rules=(
            PolicyRule(
                rule_id="res-allow",
                domain=PolicyDomain.RESOURCE,
                effect="allow",
                operation=Operation.RESOURCE_CONSUME,
            ),
        ),
        issuer_node_id=_POLICY_ISSUER,
        valid_from=_POLICY_VALID_FROM,
        valid_until=_POLICY_VALID_UNTIL,
    )
    context = PolicyContext(
        operation=Operation.RESOURCE_CONSUME,
        requester_node_id=_NODE_UE,
        evaluation_instant=evaluation_instant,
        resource_refs=("resources:account:" + "9" * 32,),
    )
    result = PolicyEngine().evaluate(policy_set, context)
    assert result.ok and result.decision is not None, result.detail
    return result.decision


class _TestSessionReader(SessionReader):
    """A test double implementing the WORK-012 read-only projection."""

    def __init__(
        self, secureable_sessions: Tuple[str, ...] = (_SESSION_ID,)
    ) -> None:
        self._secureable = tuple(secureable_sessions)

    def lookup(self, session_id: str) -> Optional[SessionView]:
        if session_id in self._secureable:
            return SessionView(
                session_id=session_id,
                secureable=True,
                initiator_node_id=_NODE_UE,
                responder_node_id=_NODE_A,
            )
        return SessionView(
            session_id=session_id,
            secureable=False,
            initiator_node_id=_NODE_UE,
            responder_node_id=_NODE_B,
        )


class _StoreSessionReader(SessionReader):
    """The REAL WORK-012 store adapter (the composition-root wiring)."""

    def __init__(self, store: Any) -> None:
        self._store = store

    def lookup(self, session_id: str) -> Optional[SessionView]:
        from sessions import SessionState

        session = self._store.get(session_id)
        if session is None:
            return None
        return SessionView(
            session_id=session.session_id,
            secureable=session.state
            in (SessionState.ESTABLISHED, SessionState.DEGRADED),
            initiator_node_id=session.binding.source_node_id,
            responder_node_id=session.binding.destination_node_id,
        )


class _StoreFederationReader(FederationReader):
    """The REAL WORK-015 scope-check adapter (read-only DATA)."""

    def __init__(self, store: Any) -> None:
        self._store = store

    def check_scope(
        self, relationship_id: str, scope: str, *, evaluation_instant: str
    ) -> Tuple[bool, str]:
        result = self._store.check_scope(
            relationship_id, scope, evaluation_instant=evaluation_instant
        )
        return (bool(result.ok), str(result.code))


def _full_registry(
    *, session_reader: Optional[SessionReader] = None,
    federation_reader: Optional[FederationReader] = None,
    step_budget: int = DEFAULT_STEP_BUDGET,
) -> Tuple[ServiceRegistry, ReferenceEdgeExecutor]:
    registry = ServiceRegistry(
        session_reader=session_reader, federation_reader=federation_reader,
        step_budget=step_budget,
    )
    executor = ReferenceEdgeExecutor()
    result = registry.register_execution_provider(
        executor, label="local-edge", now=_NOW
    )
    assert result.ok, result.detail
    return registry, executor


def _registered(
    registry: ServiceRegistry,
    advertisement: Optional[ServiceAdvertisement] = None,
    *,
    now: str = _NOW,
) -> str:
    if advertisement is None:
        advertisement = _advertisement()
    result = registry.register_service(
        now=now, advertisement=advertisement,
        evidence=_evidence(advertisement, observed_at=now),
    )
    assert result.ok, result.detail
    return result.value


def _decision_for(
    registry: ServiceRegistry,
    service_ref: str,
    *,
    now: str = _T1,
    session_id: str = "",
    caller_node_id: str = "",
    tenant_domain: str = "village-a",
) -> str:
    """Apply a GENUINE engine-evaluated (born-bound) invocation
    decision (the composition recipe: evaluate a real service.invoke
    context for the exact scope, then hand the born-bound decision to
    the registry -- which accepts no scope parameters)."""
    bound = _engine_invocation_decision(
        service_ref,
        evaluation_instant=now,
        session_id=session_id,
        caller_node_id=caller_node_id,
        tenant_domain=tenant_domain,
    )
    result = registry.apply_policy_decision(
        now=now, policy_decision=bound,
    )
    assert result.ok, result.detail
    return result.value


def _bound_decision(
    evaluation_instant: str = _NOW,
    *,
    effect: str = "allow",
    decision_id: Optional[str] = None,
    service_ref: str = "services:service:" + "a" * 32,
    session_id: str = "",
    caller_node_id: str = "",
    tenant_domain: str = "village-a",
) -> PolicyDecision:
    """A GENUINE engine-evaluated service.invoke decision, BORN BOUND
    to the exact invocation scope (the scope is declared in the
    evaluation context and the WORK-010 evaluator binds it into the
    decision's digest-covered extensions -- there is no services-layer
    binding constructor to call); ``decision_id`` may be overridden to
    simulate a tampered/rebound decision id."""
    bound = _engine_invocation_decision(
        service_ref,
        evaluation_instant=evaluation_instant,
        session_id=session_id,
        caller_node_id=caller_node_id,
        tenant_domain=tenant_domain,
        effect=effect,
    )
    if decision_id is None:
        return bound
    return PolicyDecision(
        decision_id=decision_id,
        effect=bound.effect,
        code=bound.code,
        detail=bound.detail,
        matched_rule_ids=bound.matched_rule_ids,
        policy_set_id=bound.policy_set_id,
        policy_set_version=bound.policy_set_version,
        evaluation_instant=bound.evaluation_instant,
        conflict_trace=bound.conflict_trace,
        extensions=bound.extensions,
    )


def _invoke(
    registry: ServiceRegistry,
    service_ref: str,
    decision_ref: str,
    *,
    now: str = _T1,
    session_id: str = "",
    caller_node_id: str = "",
    payload: bytes = _PAYLOAD,
) -> Tuple[Any, Any]:
    admit = registry.admit_execution(
        now=now, service_ref=service_ref, decision_ref=decision_ref,
        session_id=session_id, caller_node_id=caller_node_id,
    )
    if not admit.ok:
        return admit, None
    execute = registry.execute_request(
        now=now, admission_ref=admit.value.admission_ref,
        request_payload=payload,
    )
    release = registry.release_execution(
        now=now, admission_ref=admit.value.admission_ref
    )
    assert release.ok, release.detail
    return execute, admit.value


# --------------------------------------------------------------------------
# Family surface and identity
# --------------------------------------------------------------------------

def case_01_family_surface_frozen() -> Result:
    name = "case_01_family_surface_frozen"
    if CONTRACT_OPERATIONS != (
        "open", "admit", "execute", "release", "observe", "health", "close",
    ):
        return fail(name, "CONTRACT_OPERATIONS changed: %s" % (CONTRACT_OPERATIONS,))
    if len(ServiceReasonCode.values()) != 33:
        return fail(name, "reason-code count drift: %d" % len(ServiceReasonCode.values()))
    if STEP_CHARGES != {
        "open": 4, "admit": 8, "execute": 6, "release": 3,
        "observe": 2, "health": 1, "close": 4,
    }:
        return fail(name, "STEP_CHARGES changed")
    if CONTEXT_SURFACE != frozenset(
        {"integration_id", "now", "charge", "steps_left", "session_reader"}
    ):
        return fail(name, "CONTEXT_SURFACE changed")
    if DEFAULT_STEP_BUDGET != 10000 or FAILURE_THRESHOLD_DEGRADED != 2 or FAILURE_THRESHOLD_FAILED != 5:
        return fail(name, "sandbox constants drifted")
    if SERVICES_PREFIX != "services":
        return fail(name, "prefix drifted")
    sample = derive_service_ref("weather-cache", "cache", "village-a")
    if not sample.startswith("services:service:"):
        return fail(name, "service ref root drifted: %s" % sample[:20])
    for other in (
        "adcos:node:", "adcos:adapter:", "adcos:transport:", "adcos:ipint:",
        "adcos:fivegc", "mesh:", "backhaul:", "wifi:", "distcore:",
        "sha256:", "capability.", "adcos:resource:",
    ):
        if sample.startswith(other):
            return fail(name, "service ref collides with %r" % (other,))
    # The opaque kinds are frozen.
    for ref in (
        derive_service_ref("n", "cache", "t"),
        derive_decision_ref(
            "services:service:" + "0" * 32, "", "", "t", "1" * 64, _NOW
        ),
        derive_admission_ref("services:service:" + "0" * 32, 1),
        derive_execution_ref(
            "services:admission:" + "2" * 32, _NOW, "3" * 64
        ),
        derive_exposure_ref(
            "services:service:" + "0" * 32, "sha256:" + "4" * 64,
            SERVICE_DISCOVER_SCOPE,
        ),
    ):
        if not ref.startswith("services:") or len(ref.rsplit(":", 1)[1]) != 32:
            return fail(name, "opaque ref grammar drifted: %r" % (ref,))
    return ok(name, "family surface frozen (7 ops, 33 reason codes)")


def case_02_service_identity_distinct() -> Result:
    name = "case_02_service_identity_distinct"
    ref = derive_service_ref("weather-cache", "cache", "village-a")
    # Distinct from every other identity grammar.
    if ref == _NODE_A or ref.startswith("adcos:node:"):
        return fail(name, "service ref collides with NodeID grammar")
    if ref.startswith("sha256:"):
        return fail(name, "service ref collides with session/path/federation grammar")
    if ref.startswith("capability."):
        return fail(name, "service ref collides with CapabilityID grammar")
    # Stability under host change: hosting is NOT identity material.
    adv_a = _advertisement(host=_NODE_A)
    adv_b = _advertisement(host=_NODE_B)
    if adv_a.service_ref != ref or adv_b.service_ref != ref:
        return fail(name, "service identity must not depend on the hosting node")
    # Structural separation asserts.
    from services import (
        assert_ref_session_separation, assert_service_node_separation,
    )
    try:
        assert_service_node_separation(ref, _NODE_A)
    except ServiceError as exc:
        return fail(name, "clean separation rejected: %s" % (exc,))
    forged = "services:service:" + _NODE_A.rsplit(":", 1)[1][:32]
    try:
        assert_service_node_separation(forged, _NODE_A)
        return fail(name, "node-derived service ref accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.ACCESS_SESSION_COLLAPSE:
            return fail(name, "wrong reason: %s" % (exc.reason,))
    try:
        assert_ref_session_separation(ref, _SESSION_ID)
    except ServiceError:
        return fail(name, "clean ref/session separation rejected")
    # A service may host many services: one node, several refs.
    refs = {
        derive_service_ref(n, "cache", "village-a")
        for n in ("weather-cache", "telemetry-cache", "media-cache")
    }
    if len(refs) != 3:
        return fail(name, "distinct services collapsed")
    # Cross-parser rejection: the node grammar rejects service refs.
    if _node_grammar_accepts(ref):
        return fail(name, "node grammar accepted a service ref")
    return ok(name, "ServiceID != NodeID != SessionID; stable under host change")


def _node_grammar_accepts(value: str) -> bool:
    return bool(re.fullmatch(
        r"adcos:node:((?:[a-z0-9][a-z0-9-]*\.)+[a-z0-9][a-z0-9-]*):([0-9a-f]{64})",
        value,
    ))


def case_03_registration_deterministic_repeat_safe() -> Result:
    name = "case_03_registration_deterministic_repeat_safe"
    registry, _executor = _full_registry()
    advertisement = _advertisement()
    first = _registered(registry, advertisement)
    bytes_after_first = registry.to_canonical_bytes()
    # Repeat registration: same claim -> idempotent, no state change.
    second = _registered(registry, advertisement)
    if second != first:
        return fail(name, "repeat registration derived a different ref")
    if registry.to_canonical_bytes() != bytes_after_first:
        return fail(name, "repeat registration mutated canonical state")
    if registry.registered_count != 1:
        return fail(name, "repeat registration duplicated the record")
    # Cross-instance determinism: a fresh twin derives identical bytes.
    twin, _twin_executor = _full_registry()
    _registered(twin, advertisement)
    if twin.to_canonical_bytes() != bytes_after_first:
        return fail(name, "twin registry derived different canonical bytes")
    return ok(name, "registration deterministic and repeat-safe")


def case_04_advertisement_validity_provenance() -> Result:
    name = "case_04_advertisement_validity_provenance"
    registry, _executor = _full_registry()
    advertisement = _advertisement()
    # Evidence type discipline.
    for bad in ("evidence", 42):
        try:
            registry.register_service(
                now=_NOW, advertisement=advertisement,
                evidence=bad,  # type: ignore[arg-type]
            )
            return fail(name, "mistyped evidence accepted: %r" % (bad,))
        except ServiceError as exc:
            if exc.reason != ServiceReasonCode.INVALID_INPUT:
                return fail(name, "mistyped evidence: %s" % (exc.reason,))
    # Claim-digest binding: a mismatched digest is unevidenced.
    good = _evidence(advertisement)
    for tampered_digest in ("0" * 64, "f" * 64):
        bad_evidence = AdvertisementEvidence(
            observer_node_id=good.observer_node_id,
            reporter_node_id=good.reporter_node_id,
            source_class=good.source_class,
            observed_at=good.observed_at,
            claim_digest=tampered_digest,
            provenance=good.provenance,
        )
        try:
            registry.register_service(
                now=_NOW, advertisement=advertisement, evidence=bad_evidence
            )
            return fail(name, "mismatched claim digest accepted")
        except ServiceError as exc:
            if exc.reason != ServiceReasonCode.ADVERTISEMENT_UNEVIDENCED:
                return fail(name, "unevidenced: %s" % (exc.reason,))
    # The digest binds the WHOLE claim: any field change breaks it.
    changed = _advertisement(endpoint="edge://other-slot")
    if derive_advertisement_claim_digest(changed) == derive_advertisement_claim_digest(advertisement):
        return fail(name, "claim digest ignores advertisement content")
    try:
        registry.register_service(
            now=_NOW, advertisement=changed, evidence=good
        )
        return fail(name, "evidence for a different claim accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.ADVERTISEMENT_UNEVIDENCED:
            return fail(name, "cross-claim evidence: %s" % (exc.reason,))
    # Provenance is explicit and secret-free.
    try:
        AdvertisementEvidence(
            observer_node_id=_NODE_A, reporter_node_id=_NODE_A,
            source_class="direct-observation", observed_at=_NOW,
            claim_digest="0" * 64, provenance="shared_secret",
        )
        return fail(name, "credential-like provenance accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.INVALID_INPUT:
            return fail(name, "provenance rejection: %s" % (exc.reason,))
    # Validity window is explicit DATA on the advertisement.
    if advertisement.registered_at != _NOW or advertisement.expires_at != _FRESH:
        return fail(name, "validity window not carried")
    return ok(name, "advertisements carry explicit validity + provenance")


def case_05_lookup_state_matrix() -> Result:
    name = "case_05_lookup_state_matrix"
    registry, _executor = _full_registry()
    # Unknown.
    try:
        registry.lookup_service(
            now=_NOW,
            service_ref=derive_service_ref("ghost", "cache", "village-a"),
            tenant_domain="village-a",
        )
        return fail(name, "unknown service resolved")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.SERVICE_UNKNOWN:
            return fail(name, "unknown: %s" % (exc.reason,))
    # Eligible.
    fresh_ref = _registered(registry)
    candidate = registry.lookup_service(
        now=_NOW, service_ref=fresh_ref, tenant_domain="village-a"
    )
    if candidate.state != ServiceLifecycle.REGISTERED:
        return fail(name, "eligible lookup returned %r" % (candidate.state,))
    # Stale (expired advertisement).
    stale_ref = _registered(
        registry, _advertisement(
            descriptor=_descriptor(name="stale-cache"),
            expires_at=_EXPIRED,
        )
    )
    try:
        registry.lookup_service(now=_NOW, service_ref=stale_ref, tenant_domain="village-a")
        return fail(name, "stale advertisement resolved")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.SERVICE_STALE:
            return fail(name, "stale: %s" % (exc.reason,))
    # Withdrawn.
    withdrawn_ref = _registered(
        registry, _advertisement(descriptor=_descriptor(name="old-cache"))
    )
    result = registry.withdraw_service(now=_T1, service_ref=withdrawn_ref, reason="decommissioned")
    if not result.ok:
        return fail(name, "withdrawal failed: %s" % (result.detail,))
    try:
        registry.lookup_service(
            now=_T2, service_ref=withdrawn_ref, tenant_domain="village-a"
        )
        return fail(name, "withdrawn service resolved")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.SERVICE_WITHDRAWN:
            return fail(name, "withdrawn: %s" % (exc.reason,))
    # Discovery excludes stale and withdrawn, includes fresh.
    discovered = registry.discover_services(now=_T2, tenant_domain="village-a")
    refs = {c.service_ref for c in discovered}
    if stale_ref in refs or withdrawn_ref in refs:
        return fail(name, "discovery returned stale/withdrawn records")
    if fresh_ref not in refs:
        return fail(name, "discovery dropped the fresh record")
    return ok(name, "unknown/stale/withdrawn/eligible all distinguished")


def case_06_discovery_capability_intent_aware_no_routes() -> Result:
    name = "case_06_discovery_capability_intent_aware_no_routes"
    from intent.model import ConnectivityIntent, Constraint

    registry, _executor = _full_registry()
    weather = _registered(
        registry, _advertisement(descriptor=_descriptor(name="weather-cache"))
    )
    compute_ref = _registered(
        registry, _advertisement(
            descriptor=_descriptor(
                name="vision-infer", kind="compute",
                labels=("vision",), locality=("village-b",),
                privacy=("sensitive",),
            )
        )
    )
    # Capability filtering.
    found = registry.discover_services(
        now=_NOW, tenant_domain="village-a",
        capability_ref="capability.profile.service.weather-cache",
    )
    if {c.service_ref for c in found} != {weather}:
        return fail(name, "capability filtering failed")
    # Intent service-label filtering (hard requirement).
    intent = ConnectivityIntent(
        intent_id="intent-1",
        requirements=(
            Constraint(
                constraint_id="c1", dimension="service", operator="=",
                value="weather", hardness="hard",
            ),
        ),
    )
    found = registry.discover_services(now=_NOW, tenant_domain="village-a", intent=intent)
    if {c.service_ref for c in found} != {weather}:
        return fail(name, "service-label intent filtering failed")
    # Locality + privacy filtering.
    intent = ConnectivityIntent(
        intent_id="intent-2",
        privacy_requirements=(
            Constraint(
                constraint_id="p1", dimension="privacy", operator="=",
                value="public", hardness="hard",
            ),
        ),
    )
    found = registry.discover_services(now=_NOW, tenant_domain="village-a", intent=intent)
    if compute_ref in {c.service_ref for c in found}:
        return fail(name, "privacy filtering failed")
    # service_constraints bucket.
    intent = ConnectivityIntent(
        intent_id="intent-3",
        service_constraints=(
            Constraint(
                constraint_id="s1", dimension="service", operator="=",
                value="vision", hardness="hard",
            ),
        ),
    )
    found = registry.discover_services(now=_NOW, tenant_domain="village-a", intent=intent)
    if {c.service_ref for c in found} != {compute_ref}:
        return fail(name, "service_constraints filtering failed")
    # Soft preferences never filter (selection is the caller's).
    intent = ConnectivityIntent(
        intent_id="intent-4",
        preferences=(
            Constraint(
                constraint_id="s2", dimension="service", operator="=",
                value="nonexistent-label", hardness="soft", weight=1,
            ),
        ),
    )
    found = registry.discover_services(now=_NOW, tenant_domain="village-a", intent=intent)
    if len(found) != 2:
        return fail(name, "soft preference filtered candidates")
    # Numeric dimensions are connectivity concerns: pass through.
    intent = ConnectivityIntent(
        intent_id="intent-5",
        requirements=(
            Constraint(
                constraint_id="l1", dimension="latency", operator="<=",
                value=20, unit="ms", hardness="hard",
            ),
        ),
    )
    found = registry.discover_services(now=_NOW, tenant_domain="village-a", intent=intent)
    if len(found) != 2:
        return fail(name, "numeric dimension filtered service candidates")
    # Label-dimension ordering operators fail closed (not service
    # semantics).
    intent = ConnectivityIntent(
        intent_id="intent-6",
        requirements=(
            Constraint(
                constraint_id="l2", dimension="locality", operator=">=",
                value="village-a", hardness="hard",
            ),
        ),
    )
    try:
        registry.discover_services(now=_NOW, tenant_domain="village-a", intent=intent)
        return fail(name, "ordering operator on a label dimension accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.INVALID_INPUT:
            return fail(name, "operator discipline: %s" % (exc.reason,))
    # A second intent grammar is rejected outright.
    try:
        registry.discover_services(
            now=_NOW, tenant_domain="village-a", intent={"service": "weather"}
        )
        return fail(name, "non-genuine intent accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.INVALID_INPUT:
            return fail(name, "intent type discipline: %s" % (exc.reason,))
    # Candidates carry locations, never routes.
    for candidate in registry.discover_services(now=_NOW, tenant_domain="village-a"):
        blob = str(sorted(vars(candidate).keys())) + str(candidate.to_dict())
        if "path" in blob.replace("path_", "").replace("_path", ""):
            return fail(name, "candidate carries path-like data")
        if candidate.to_dict().get("hops") is not None:
            return fail(name, "candidate carries hops")
    # The module imports no routing authority at all.
    source = _read_source(os.path.join(_ROOT, "services", "registry.py"))
    if re.search(r"\brouting\b", _strip_prose(source)):
        return fail(name, "registry source references a routing authority")
    return ok(name, "capability/intent aware; locations only, no routes")


def case_07_local_first_upstream_absent() -> Result:
    name = "case_07_local_first_upstream_absent"
    registry, _executor = _full_registry()
    local_ref = _registered(registry)
    _decision_for(registry, local_ref)
    bytes_before = registry.to_canonical_bytes()
    # Upstream connectivity is lost.
    registry.set_upstream_state(available=False)
    # Local discovery still works.
    found = registry.discover_services(now=_T1, tenant_domain="village-a")
    if local_ref not in {c.service_ref for c in found}:
        return fail(name, "local discovery broken under upstream loss")
    # Local execution still works.
    execute, admission = _invoke(registry, local_ref, _decision_ref_of(registry, local_ref), now=_T1)
    if not execute.ok or execute.value.response_payload != _PAYLOAD:
        return fail(name, "local execution broken under upstream loss")
    # The outage is REPORTED without corrupting local state.
    observation = registry.observe(now=_T1)
    if observation.upstream_available != 0:
        return fail(name, "observation did not report the outage")
    # Local authoritative facts unchanged (the canonical digest only
    # gained the decision/admission records the operations created;
    # no record was erased or corrupted).
    snapshot = registry.snapshot()
    service = [
        s for s in snapshot["services"] if s["service_ref"] == local_ref
    ]
    if not service:
        return fail(name, "upstream loss erased the local record")
    # Federated discovery is off (fail closed), local still on.
    found = registry.discover_services(
        now=_T1, tenant_domain="village-a", include_federated=True
    )
    if local_ref not in {c.service_ref for c in found}:
        return fail(name, "federated switch disabled local discovery")
    registry.set_upstream_state(available=True)
    if registry.to_canonical_bytes() == bytes_before:
        return fail(name, "canonical bytes never changed (sanity)")
    return ok(name, "local-first: discovery+execution survive upstream loss")


def _decision_ref_of(registry: ServiceRegistry, service_ref: str) -> str:
    latest = None
    for decision in registry._decisions.values():  # noqa: SLF001
        if decision.service_ref != service_ref:
            continue
        if latest is None or decision.applied_instant > latest.applied_instant:
            latest = decision
    if latest is None:
        raise AssertionError("no decision applied for %r" % (service_ref,))
    return latest.decision_ref


def case_08_local_execution_seam() -> Result:
    name = "case_08_local_execution_seam"
    registry, executor = _full_registry()
    service_ref = _registered(registry)
    decision_ref = _decision_for(registry, service_ref)
    # Granular surface: admit -> execute -> release.
    admit = registry.admit_execution(
        now=_T1, service_ref=service_ref, decision_ref=decision_ref
    )
    if not admit.ok:
        return fail(name, "admit failed: %s" % (admit.detail,))
    admission = admit.value
    if not isinstance(admission, ServiceAdmission):
        return fail(name, "admit returned %s" % (type(admission).__name__,))
    if admission.state != "active":
        return fail(name, "fresh admission state %r" % (admission.state,))
    execute = registry.execute_request(
        now=_T1, admission_ref=admission.admission_ref,
        request_payload=_PAYLOAD,
    )
    if not execute.ok:
        return fail(name, "execute failed: %s" % (execute.detail,))
    outcome = execute.value
    if outcome.status != "completed" or outcome.response_payload != _PAYLOAD:
        return fail(name, "deterministic echo broken")
    if outcome.request_bytes != len(_PAYLOAD):
        return fail(name, "request_bytes wrong")
    if executor.executed_payloads(admission.admission_ref) != ((_PAYLOAD, _PAYLOAD),):
        return fail(name, "executor isolation surface wrong")
    release = registry.release_execution(
        now=_T1, admission_ref=admission.admission_ref
    )
    if not release.ok:
        return fail(name, "release failed")
    # Released admissions are retained (history), no longer active.
    try:
        registry.execute_request(
            now=_T2, admission_ref=admission.admission_ref,
            request_payload=b"again",
        )
        return fail(name, "released admission executed")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.ADMISSION_STATE:
            return fail(name, "released admission: %s" % (exc.reason,))
    snapshot = registry.snapshot()
    states = [a["state"] for a in snapshot["admissions"]]
    if states != ["released"]:
        return fail(name, "admission history not retained: %s" % (states,))
    return ok(name, "admit -> execute -> release through the seam")


def case_09_unauthorized_execution_before_provider_effects() -> Result:
    name = "case_09_unauthorized_execution_before_provider_effects"
    registry, executor = _full_registry()
    service_ref = _registered(registry)
    # No decision at all: fails closed before the provider runs.
    try:
        registry.admit_execution(
            now=_T1, service_ref=service_ref, decision_ref="services:decision:" + "0" * 32
        )
        return fail(name, "unknown decision accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.DECISION_UNKNOWN:
            return fail(name, "no decision: %s" % (exc.reason,))
    # A DENIED policy decision never becomes authorization: it
    # applies ONLY as a per-scope revocation lineage marker (PR #26
    # third review, finding 3), and its ref authorizes NOTHING.
    denied = _bound_decision(effect="deny", service_ref=service_ref)
    revoked = registry.apply_policy_decision(
        now=_T1, policy_decision=denied
    )
    if not revoked.ok:
        return fail(
            name, "genuine deny rejected: %s" % (revoked.detail,)
        )
    if len(registry.snapshot()["decision_revocations"]) != 1:
        return fail(name, "deny not recorded as a revocation")
    try:
        registry.admit_execution(
            now=_T1, service_ref=service_ref, decision_ref=revoked.value
        )
        return fail(name, "denied decision authorized execution")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.DECISION_UNKNOWN:
            return fail(name, "denied ref: %s" % (exc.reason,))
    # Decision for another service: scope mismatch, before provider.
    other_ref = _registered(
        registry, _advertisement(descriptor=_descriptor(name="other-cache"))
    )
    other_decision = _decision_for(registry, other_ref, now=_T1)
    try:
        registry.admit_execution(
            now=_T2, service_ref=service_ref, decision_ref=other_decision
        )
        return fail(name, "cross-service decision accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.DECISION_SCOPE_MISMATCH:
            return fail(name, "cross-service: %s" % (exc.reason,))
    # Decision for another session/caller.
    decision = _decision_for(registry, service_ref, now=_T1, session_id=_SESSION_ID)
    try:
        registry.admit_execution(
            now=_T2, service_ref=service_ref, decision_ref=decision,
            session_id=_OTHER_SESSION_ID,
        )
        return fail(name, "cross-session decision accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.DECISION_SCOPE_MISMATCH:
            return fail(name, "cross-session: %s" % (exc.reason,))
    # Policy-controlled lookup without a decision is unauthorized.
    protected = _registered(
        registry, _advertisement(
            descriptor=_descriptor(name="hospital-records"),
            policy_controlled=True,
        )
    )
    try:
        registry.lookup_service(
            now=_T2, service_ref=protected, tenant_domain="village-a"
        )
        return fail(name, "policy-controlled lookup without decision")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.DECISION_DENIED:
            return fail(name, "policy-controlled lookup: %s" % (exc.reason,))
    # The provider executed NOTHING through all of this.
    if any(
        executor.executed_payloads(ref)
        for ref in _executor_refs(executor)
    ):
        return fail(name, "provider side effects before authorization")
    return ok(name, "unauthorized invocations fail before provider effects")


def _executor_refs(executor: ReferenceEdgeExecutor) -> List[str]:
    return [  # noqa: SLF001
        ref for ref in executor._admissions
    ]


def case_10_execution_failures_isolated_typed() -> Result:
    name = "case_10_execution_failures_isolated_typed"

    class _ExplodingExecutor(ReferenceEdgeExecutor):
        def execute(self, context, *, admission_ref, request_payload, requirements=None):
            raise RuntimeError("secret-diagnostic: %s" % ("x" * 64))

    class _FailingOutcomeExecutor(ReferenceEdgeExecutor):
        def execute(self, context, *, admission_ref, request_payload, requirements=None):
            from services import ExecutionOutcome, ExecutionStatus
            import hashlib as _h
            digest = _h.sha256(request_payload).hexdigest()
            return ExecutionOutcome(
                admission_ref=admission_ref,
                service_ref="services:service:" + "0" * 32,
                execution_ref=derive_execution_ref(
                    admission_ref, context.now(), digest
                ),
                status="failed",
                executed_at=context.now(),
                request_bytes=len(request_payload),
                request_digest=digest,
                response_payload=b"",
                detail="service-level partial failure",
            )

    registry = ServiceRegistry()
    result = registry.register_execution_provider(
        _ExplodingExecutor(), label="exploding", now=_NOW
    )
    assert result.ok
    service_ref = _registered(registry)
    decision_ref = _decision_for(registry, service_ref)
    admit = registry.admit_execution(
        now=_T1, service_ref=service_ref, decision_ref=decision_ref
    )
    if not admit.ok:
        return fail(name, "admit failed: %s" % (admit.detail,))
    bytes_before = registry.to_canonical_bytes()
    execute = registry.execute_request(
        now=_T1, admission_ref=admit.value.admission_ref,
        request_payload=_PAYLOAD,
    )
    if execute.ok:
        return fail(name, "exploding provider produced an ok result")
    failure = execute.failure
    if failure is None:
        return fail(name, "failed execution carried no failure value")
    if failure.reason_code != ServiceReasonCode.SERVICES_FAILURE:
        return fail(name, "isolation reason: %s" % (failure.reason_code,))
    if failure.exception_class_name != "RuntimeError":
        return fail(name, "exception class not carried")
    if "secret-diagnostic" in str(failure) or "xxxx" in str(failure):
        return fail(name, "exception message text leaked (LOCK-023)")
    if registry.to_canonical_bytes() != bytes_before:
        return fail(name, "provider fault mutated canonical state")
    # Health ladder degrades on consecutive failures.
    for _ in range(3):
        registry.execute_request(
            now=_T1, admission_ref=admit.value.admission_ref,
            request_payload=_PAYLOAD,
        )
    if registry.computed_health() != "DEGRADED":
        return fail(name, "health ladder: %s" % (registry.computed_health(),))
    # A completed run may report an honest FAILED status as a value.
    registry2 = ServiceRegistry()
    registry2.register_execution_provider(
        _FailingOutcomeExecutor(), label="failing-outcome", now=_NOW
    )
    service_ref2 = _registered(registry2)
    decision_ref2 = _decision_for(registry2, service_ref2)
    execute2, _admission = _invoke(registry2, service_ref2, decision_ref2)
    if not execute2.ok or execute2.value.status != "failed":
        return fail(name, "failed-status outcome not an honest value")
    if execute2.value.detail != "service-level partial failure":
        return fail(name, "partial-failure detail lost")
    return ok(name, "provider faults isolated as typed values; honest failures")


def _admit_fails_with(
    registry: ServiceRegistry, *, reason: str, **kwargs: Any
) -> Optional[str]:
    """Invoke admit_execution expecting a caller-side fail-closed
    ServiceError with the given reason; returns a failure detail when
    the expectation is NOT met (None when met)."""
    try:
        result = registry.admit_execution(**kwargs)
    except ServiceError as exc:
        if exc.reason != reason:
            return "raised %s (expected %s): %s" % (exc.reason, reason, exc.detail)
        return None
    if result.ok:
        return "admission succeeded (expected %s)" % (reason,)
    if result.reason != reason:
        return "failed with %s (expected %s)" % (result.reason, reason)
    return None


def _allocate_fails_with(
    registry: ServiceRegistry, *, reason: str, **kwargs: Any
) -> Optional[str]:
    try:
        result = registry.allocate(**kwargs)
    except ServiceError as exc:
        if exc.reason != reason:
            return "raised %s (expected %s)" % (exc.reason, reason)
        return None
    if result.ok:
        return "allocation succeeded (expected %s)" % (reason,)
    if result.reason != reason:
        return "failed with %s (expected %s)" % (result.reason, reason)
    return None


def case_11_capacity_work008_data() -> Result:
    name = "case_11_capacity_work008_data"
    from resources.model import ResourceKind

    # The carried kinds are exactly WORK-008 consumable kinds.
    for kind in SERVICE_CAPACITY_KINDS:
        if kind not in ResourceKind.CONSUMABLE:
            return fail(name, "kind %r is not a WORK-008 consumable kind" % (kind,))
    registry, _executor = _full_registry()
    # Advertisement declares edge-service-capacity: 2 (an OFFER).
    service_ref = _registered(registry)
    decision_ref = _decision_for(registry, service_ref)
    first = registry.admit_execution(
        now=_T1, service_ref=service_ref, decision_ref=decision_ref
    )
    second = registry.admit_execution(
        now=_T1, service_ref=service_ref, decision_ref=decision_ref
    )
    if not (first.ok and second.ok):
        return fail(name, "declared capacity did not admit two executions")
    # The third standing admission exhausts the DECLARED capacity.
    problem = _admit_fails_with(
        registry, reason=ServiceReasonCode.CAPACITY_EXHAUSTED,
        now=_T1, service_ref=service_ref, decision_ref=decision_ref,
    )
    if problem:
        return fail(name, "exhaustion: %s" % (problem,))
    # Advertisement != reservation: a service with NO declared
    # capacity admits nothing (existence is not a reservation).
    no_capacity_ref = _registered(
        registry, _advertisement(
            descriptor=_descriptor(name="zero-capacity"),
            capacity=(),
        )
    )
    zero_decision = _decision_for(registry, no_capacity_ref, now=_T1)
    problem = _admit_fails_with(
        registry, reason=ServiceReasonCode.CAPACITY_EXHAUSTED,
        now=_T2, service_ref=no_capacity_ref, decision_ref=zero_decision,
    )
    if problem:
        return fail(name, "zero-capacity admission: %s" % (problem,))
    zero_qty_ref = _registered(
        registry, _advertisement(
            descriptor=_descriptor(name="zero-qty"),
            capacity=(ServiceCapacity("edge-service-capacity", 0),),
        )
    )
    zero_qty_decision = _decision_for(registry, zero_qty_ref, now=_T1)
    problem = _admit_fails_with(
        registry, reason=ServiceReasonCode.CAPACITY_EXHAUSTED,
        now=_T2, service_ref=zero_qty_ref, decision_ref=zero_qty_decision,
    )
    if problem:
        return fail(name, "zero-quantity admission: %s" % (problem,))
    # Unknown kinds fail closed (no second vocabulary).
    try:
        registry.allocate(now=_T1, kind="quantum-flux", quantity_base=1, purpose="p")
        return fail(name, "unknown capacity kind accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.INVALID_INPUT:
            return fail(name, "unknown kind: %s" % (exc.reason,))
    # Explicit allocation path over the DECLARED pool.
    compute_ref = _registered(
        registry, _advertisement(
            descriptor=_descriptor(name="compute-pool", kind="compute"),
            capacity=(
                ServiceCapacity("compute", 4000),
                ServiceCapacity("edge-service-capacity", 4),
            ),
        )
    )
    allocation = registry.allocate(
        now=_T1, kind="compute", quantity_base=2500, purpose="inference-batch"
    )
    if not allocation.ok:
        return fail(name, "allocation failed: %s" % (allocation.detail,))
    over_problem = _allocate_fails_with(
        registry, reason=ServiceReasonCode.CAPACITY_EXHAUSTED,
        now=_T1, kind="compute", quantity_base=2000, purpose="inference-batch-2",
    )
    if over_problem:
        return fail(name, "pool over-allocation: %s" % (over_problem,))
    released = registry.release(now=_T1, allocation_ref=allocation.value)
    if not released.ok:
        return fail(name, "release failed")
    again = registry.allocate(
        now=_T1, kind="compute", quantity_base=2000, purpose="inference-batch-3"
    )
    if not again.ok:
        return fail(name, "release did not return capacity")
    return ok(name, "WORK-008 DATA; advertisement=offer, admission=reservation")


def case_12_capacity_exhaustion_state_unchanged() -> Result:
    name = "case_12_capacity_exhaustion_state_unchanged"
    registry, _executor = _full_registry()
    service_ref = _registered(
        registry, _advertisement(capacity=(ServiceCapacity("edge-service-capacity", 1),))
    )
    decision_ref = _decision_for(registry, service_ref)
    first = registry.admit_execution(
        now=_T1, service_ref=service_ref, decision_ref=decision_ref
    )
    if not first.ok:
        return fail(name, "first admission failed")
    bytes_before = registry.to_canonical_bytes()
    # Exhausted admission fails closed...
    problem = _admit_fails_with(
        registry, reason=ServiceReasonCode.CAPACITY_EXHAUSTED,
        now=_T1, service_ref=service_ref, decision_ref=decision_ref,
    )
    if problem:
        return fail(name, "exhaustion: %s" % (problem,))
    # ...leaving authoritative state byte-identical.
    if registry.to_canonical_bytes() != bytes_before:
        return fail(name, "failed admission mutated canonical state")
    # Failed execution (provider fault) also leaves state unchanged.
    class _OnceFailing(ReferenceEdgeExecutor):
        def execute(self, context, *, admission_ref, request_payload, requirements=None):
            raise RuntimeError("boom")

    registry2 = ServiceRegistry()
    registry2.register_execution_provider(_OnceFailing(), label="failing", now=_NOW)
    service_ref2 = _registered(registry2)
    decision_ref2 = _decision_for(registry2, service_ref2)
    admit2 = registry2.admit_execution(
        now=_T1, service_ref=service_ref2, decision_ref=decision_ref2
    )
    bytes_before2 = registry2.to_canonical_bytes()
    execute2 = registry2.execute_request(
        now=_T1, admission_ref=admit2.value.admission_ref,
        request_payload=_PAYLOAD,
    )
    if execute2.ok:
        return fail(name, "failing executor produced ok")
    if registry2.to_canonical_bytes() != bytes_before2:
        return fail(name, "failed execution mutated canonical state")
    return ok(name, "exhaustion/failure leave authoritative state unchanged")


def case_13_placement_host_change_identity_stable() -> Result:
    name = "case_13_placement_host_change_identity_stable"
    registry, _executor = _full_registry()
    service_ref = _registered(registry)
    before = registry.lookup_service(
        now=_NOW, service_ref=service_ref, tenant_domain="village-a"
    )
    result = registry.relocate_service(
        now=_T1, service_ref=service_ref, target_host_node_id=_NODE_B,
        target_endpoint_ref="edge://slot-9",
    )
    if not result.ok:
        return fail(name, "relocation failed: %s" % (result.detail,))
    after = registry.lookup_service(
        now=_T2, service_ref=service_ref, tenant_domain="village-a"
    )
    if after.service_ref != service_ref:
        return fail(name, "ServiceID changed across relocation")
    if after.host_node_id != _NODE_B:
        return fail(name, "host did not change")
    if after.host_node_id == before.host_node_id:
        return fail(name, "host unchanged")
    if after.endpoint_ref != "edge://slot-9":
        return fail(name, "endpoint not updated")
    if after.name != before.name or after.tenant_domain != before.tenant_domain:
        return fail(name, "service-owned identity material mutated")
    # Relocating to the current host is rejected.
    try:
        registry.relocate_service(
            now=_T2, service_ref=service_ref, target_host_node_id=_NODE_B
        )
        return fail(name, "no-op relocation accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.INVALID_INPUT:
            return fail(name, "no-op relocation: %s" % (exc.reason,))
    return ok(name, "ServiceID stable; HostNode changed explicitly")


def case_14_placement_transition_recorded() -> Result:
    name = "case_14_placement_transition_recorded"
    registry, _executor = _full_registry()
    service_ref = _registered(registry)
    registry.relocate_service(
        now=_T1, service_ref=service_ref, target_host_node_id=_NODE_B
    )
    registry.relocate_service(
        now=_T2, service_ref=service_ref, target_host_node_id=_NODE_C
    )
    snapshot = registry.snapshot()
    placements = snapshot["placements"]
    if len(placements) != 2:
        return fail(name, "placement transitions not recorded: %d" % (len(placements),))
    if placements[0]["from_host_node_id"] != _NODE_A or placements[0]["to_host_node_id"] != _NODE_B:
        return fail(name, "first transition wrong: %s" % (placements[0],))
    if placements[1]["from_host_node_id"] != _NODE_B or placements[1]["to_host_node_id"] != _NODE_C:
        return fail(name, "second transition wrong: %s" % (placements[1],))
    if placements[0]["transitioned_at"] != _T1 or placements[1]["transitioned_at"] != _T2:
        return fail(name, "transition instants not carried")
    events = [e["event_type"] for e in snapshot["events"]]
    if events.count(ServiceEventType.SERVICE_RELOCATED) != 2:
        return fail(name, "relocation events missing: %s" % (events,))
    # Each transition is auditable DATA (deterministic
    # reconstruction).
    blob = registry.to_canonical_bytes()
    if b"from_host_node_id" not in blob or b"to_host_node_id" not in blob:
        return fail(name, "transition facts not in canonical bytes")
    return ok(name, "both transitions recorded and auditable")


def case_15_session_identity_stable_across_relocation() -> Result:
    name = "case_15_session_identity_stable_across_relocation"
    store, session_id, _decision, _path = _compose_real_session()
    registry, _executor = _full_registry(
        session_reader=_StoreSessionReader(store)
    )
    service_ref = _registered(registry)
    first_decision = _decision_for(
        registry, service_ref, now=_T1, session_id=session_id
    )
    execute, _admission = _invoke(
        registry, service_ref, first_decision, now=_T1, session_id=session_id
    )
    if not execute.ok:
        return fail(name, "pre-relocation execution failed: %s" % (execute.detail,))
    # Relocate the service (connectivity/provider changes; the
    # governing session identity is untouched).
    result = registry.relocate_service(
        now=_T2, service_ref=service_ref, target_host_node_id=_NODE_B
    )
    if not result.ok:
        return fail(name, "relocation failed")
    # The old decision is no longer current: re-authorization under
    # current policy is required.
    try:
        registry.admit_execution(
            now=_T3, service_ref=service_ref, decision_ref=first_decision,
            session_id=session_id,
        )
        return fail(name, "pre-relocation decision survived relocation")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.REAUTHORIZATION_REQUIRED:
            return fail(name, "relocation re-auth: %s" % (exc.reason,))
    # Re-authorize the SAME session and execute on the new host.
    second_decision = _decision_for(
        registry, service_ref, now=_T3, session_id=session_id
    )
    execute, admission = _invoke(
        registry, service_ref, second_decision, now=_T3, session_id=session_id
    )
    if not execute.ok:
        return fail(name, "post-relocation execution failed: %s" % (execute.detail,))
    if admission.host_node_id != _NODE_B:
        return fail(name, "admission bound the old host")
    # The governing session identity is unchanged end-to-end.
    if admission.session_id != session_id:
        return fail(name, "session identity changed across relocation")
    snapshot = registry.snapshot()
    for adm in snapshot["admissions"]:
        if adm["session_id"] != session_id:
            return fail(name, "foreign session id in admissions")
    return ok(name, "session identity preserved across relocation")


def case_16_federation_scoped_visibility() -> Result:
    name = "case_16_federation_scoped_visibility"
    store, relationship_id, _domain_a = _compose_real_federation()
    reader = _StoreFederationReader(store)
    registry, _executor = _full_registry(federation_reader=reader)
    # A federated-visibility local service + exposure.
    federated_ref = _registered(
        registry, _advertisement(
            descriptor=_descriptor(name="shared-analytics", kind="analytics",
                                   tenant="village-a", labels=("analytics",)),
            visibility=VisibilityScope.FEDERATED,
        )
    )
    exposure = registry.apply_federation_exposure(
        now=_T1, service_ref=federated_ref, relationship_id=relationship_id
    )
    if not exposure.ok:
        return fail(name, "exposure failed: %s" % (exposure.detail,))
    # A local-only service is never exported.
    local_only = _registered(registry)
    claims = export_service_exposures(
        (registry.lookup_service(
            now=_T1, service_ref=r, tenant_domain="village-a"
        )
         for r in (federated_ref, local_only)),
        registry._exposures.values(),  # noqa: SLF001
        relationship_id=relationship_id,
    )
    if len(claims) != 1 or claims[0]["service_ref"] != federated_ref:
        return fail(name, "export leaked non-exposed services")
    # The peer side imports the claim as a federation-scoped record.
    peer_registry, _peer_executor = _full_registry(federation_reader=reader)
    peer_advertisement = _advertisement_from_claim(claims[0], relationship_id)
    peer_result = peer_registry.register_service(
        now=_T2, advertisement=peer_advertisement,
        evidence=_evidence(
            peer_advertisement, source_class="remote-claim",
            observer=_NODE_B, reporter=_NODE_B, observed_at=_T2,
            provenance="federation-exchange",
        ),
    )
    if not peer_result.ok:
        return fail(name, "peer import failed: %s" % (peer_result.detail,))
    # Scoped federated discovery on the peer side.
    found = peer_registry.discover_services(
        now=_T2, tenant_domain="village-a", include_federated=True
    )
    refs = {c.service_ref for c in found}
    if federated_ref not in refs:
        return fail(name, "federated discovery missed the exposed service")
    if local_only in refs:
        return fail(name, "federated discovery leaked a non-exposed local service")
    # The peer's own local records do not leak into the local
    # tenant-only view either.
    if any(
        c.source_class != "direct-observation"
        for c in peer_registry.discover_services(now=_T2, tenant_domain="village-a")
    ):
        return fail(name, "remote claims visible without include_federated")
    # No universal trust: an un-granted scope hides the service.
    other_relationship = "sha256:" + "9" * 64
    try:
        registry.apply_federation_exposure(
            now=_T2, service_ref=federated_ref,
            relationship_id=other_relationship,
        )
        return fail(name, "exposure to unknown relationship accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.FEDERATION_SCOPE_DENIED:
            return fail(name, "unknown relationship: %s" % (exc.reason,))
    # Local visibility gating: a tenant-visible service cannot be
    # exposed.
    try:
        registry.apply_federation_exposure(
            now=_T2, service_ref=local_only, relationship_id=relationship_id
        )
        return fail(name, "non-federated visibility exposed")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.VISIBILITY_HIDDEN:
            return fail(name, "visibility gating: %s" % (exc.reason,))
    # Membership never implies trust on the peer side either: without
    # the reader the peer sees nothing federated.
    blind_registry, _b = _full_registry()
    blind_registry.register_service(
        now=_T2, advertisement=peer_advertisement,
        evidence=_evidence(
            peer_advertisement, source_class="remote-claim",
            observer=_NODE_B, reporter=_NODE_B, observed_at=_T2,
        ),
    )
    if blind_registry.discover_services(
        now=_T2, tenant_domain="village-a", include_federated=True
    ):
        return fail(name, "federated discovery without federation authority")
    return ok(name, "federation visibility scoped; no leaks; no universal trust")


def _advertisement_from_claim(
    claim: Mapping[str, Any], relationship_id: str
) -> ServiceAdvertisement:
    descriptor = ServiceDescriptor(
        name=claim["name"],
        service_kind=claim["service_kind"],
        tenant_domain=claim["tenant_domain"],
        capability_refs=tuple(claim["capability_refs"]),
        service_labels=tuple(claim["service_labels"]),
        locality_labels=tuple(claim["locality_labels"]),
        privacy_labels=tuple(claim["privacy_labels"]),
    )
    return ServiceAdvertisement(
        descriptor=descriptor,
        host_node_id=claim["host_node_id"],
        registered_at=claim["registered_at"],
        expires_at=claim["expires_at"],
        visibility=VisibilityScope.FEDERATED,
        endpoint_ref=claim["endpoint_ref"],
        capacity=(),
        policy_controlled=claim["policy_controlled"],
        federation_relationship_id=relationship_id,
    )


def case_17_federation_removal_preserves_local() -> Result:
    name = "case_17_federation_removal_preserves_local"
    store, relationship_id, _domain = _compose_real_federation()
    registry, _executor = _full_registry(
        federation_reader=_StoreFederationReader(store)
    )
    federated_ref = _registered(
        registry, _advertisement(visibility=VisibilityScope.FEDERATED)
    )
    exposure = registry.apply_federation_exposure(
        now=_T1, service_ref=federated_ref, relationship_id=relationship_id
    )
    if not exposure.ok:
        return fail(name, "exposure failed")
    with_service = registry.snapshot()
    removed = registry.remove_federation_exposure(
        now=_T2, service_ref=federated_ref, relationship_id=relationship_id
    )
    if not removed.ok:
        return fail(name, "removal failed: %s" % (removed.detail,))
    after = registry.snapshot()
    # The exposure is gone...
    if after["exposures"]:
        return fail(name, "exposure not removed")
    # ...but the LOCAL SERVICE RECORD IS INTACT.
    refs = [s["service_ref"] for s in after["services"]]
    if federated_ref not in refs:
        return fail(name, "removing exposure deleted the local record")
    if with_service["services"] != after["services"]:
        return fail(name, "local record content changed")
    if registry.registered_count != 1:
        return fail(name, "registered count changed")
    # Removal is auditable.
    events = [e["event_type"] for e in after["events"]]
    if ServiceEventType.EXPOSURE_REMOVED not in events:
        return fail(name, "removal not audited")
    # The service remains locally discoverable.
    if federated_ref not in {
        c.service_ref for c in registry.discover_services(
            now=_T2, tenant_domain="village-a"
        )
    }:
        return fail(name, "service not locally discoverable after removal")
    # Re-applying is idempotent.
    again = registry.apply_federation_exposure(
        now=_T3, service_ref=federated_ref, relationship_id=relationship_id
    )
    if not again.ok or again.value != exposure.value:
        return fail(name, "exposure re-application not idempotent")
    return ok(name, "exposure removed; local record preserved")


def case_18_tenant_isolation() -> Result:
    name = "case_18_tenant_isolation"
    import inspect

    registry, _executor = _full_registry()
    village_a = _registered(registry)
    village_b = _registered(
        registry, _advertisement(
            descriptor=_descriptor(name="village-b-cache", tenant="village-b")
        )
    )
    # Structural: tenant_domain is a REQUIRED parameter of both query
    # methods -- there is no unscoped call shape at all (PR #26
    # review, blocker 1).
    for method in (registry.lookup_service, registry.discover_services):
        param = inspect.signature(method).parameters["tenant_domain"]
        if param.default is not inspect.Parameter.empty:
            return fail(
                name, "%s.tenant_domain is optional" % (method.__name__,)
            )
    # Omitting the scope is a TypeError, not an implicit global view.
    try:
        registry.discover_services(now=_NOW)  # type: ignore[call-arg]
        return fail(name, "scope-less discovery ran")
    except TypeError:
        pass
    try:
        registry.lookup_service(now=_NOW, service_ref=village_a)  # type: ignore[call-arg]
        return fail(name, "scope-less lookup ran")
    except TypeError:
        pass
    # An explicitly empty scope fails closed with TENANT_ISOLATION.
    for caller in (
        lambda: registry.discover_services(now=_NOW, tenant_domain=""),
        lambda: registry.lookup_service(
            now=_NOW, service_ref=village_b, tenant_domain=""
        ),
        lambda: registry.discover_services(now=_NOW, tenant_domain=None),  # type: ignore[arg-type]
    ):
        try:
            caller()
            return fail(name, "empty tenant scope accepted")
        except ServiceError as exc:
            if exc.reason != ServiceReasonCode.TENANT_ISOLATION:
                return fail(name, "empty scope: %s" % (exc.reason,))
    # Cross-tenant lookup fails closed.
    try:
        registry.lookup_service(
            now=_NOW, service_ref=village_b, tenant_domain="village-a"
        )
        return fail(name, "cross-tenant lookup allowed")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.TENANT_ISOLATION:
            return fail(name, "cross-tenant lookup: %s" % (exc.reason,))
    # Discovery is strictly tenant-scoped: each scope sees exactly
    # its own records and never the other tenant's.
    found = registry.discover_services(now=_NOW, tenant_domain="village-a")
    if {c.service_ref for c in found} != {village_a}:
        return fail(name, "tenant discovery leaked another tenant")
    found = registry.discover_services(now=_NOW, tenant_domain="village-b")
    if {c.service_ref for c in found} != {village_b}:
        return fail(name, "tenant discovery incomplete")
    # Cross-tenant authorization fails closed too: an ALLOW bound to
    # village-a's tenant can never authorize village-b's service.
    try:
        registry.apply_policy_decision(
            now=_T1,
            policy_decision=_bound_decision(
                evaluation_instant=_T1, service_ref=village_b,
                tenant_domain="village-a",
            ),
        )
        return fail(name, "cross-tenant authorization accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.TENANT_ISOLATION:
            return fail(name, "cross-tenant auth: %s" % (exc.reason,))
    # Canonical state is tenant-labelled throughout.
    for record in registry.snapshot()["services"]:
        if not record["tenant_domain"]:
            return fail(name, "record without tenant label")
    return ok(
        name,
        "tenant scope required + fail-closed on lookup/discovery/"
        "authorization",
    )


def case_19_secrets_never_in_records() -> Result:
    name = "case_19_secrets_never_in_records"
    # Credential-like text is rejected in every free-text field.
    for builder in (
        lambda: _descriptor(name="shared-secret-cache"),
        lambda: _descriptor(labels=("api-key",)),
        lambda: _descriptor(locality=("password-zone",)),
        lambda: _descriptor(privacy=("psk-zone",)),
        lambda: _advertisement(endpoint="secret://password"),
        lambda: AdvertisementEvidence(
            observer_node_id=_NODE_A, reporter_node_id=_NODE_A,
            source_class="direct-observation", observed_at=_NOW,
            claim_digest="0" * 64, provenance="pre_shared_key material",
        ),
    ):
        try:
            builder()
            return fail(name, "credential-like text accepted: %s" % (builder,))
        except ServiceError as exc:
            if exc.reason != ServiceReasonCode.INVALID_INPUT:
                return fail(name, "rejection reason: %s" % (exc.reason,))
    # Separator normalization catches disguised forms.
    try:
        _descriptor(name="shared.secret-cache")
        return fail(name, "dot-separated secret accepted")
    except ServiceError:
        pass
    try:
        _descriptor(name="shared secret-cache")
        return fail(name, "space-separated secret accepted")
    except ServiceError:
        pass
    # Canonical bytes, results, and errors never carry secret
    # markers.
    registry, _executor = _full_registry()
    service_ref = _registered(registry)
    decision_ref = _decision_for(registry, service_ref)
    execute, _admission = _invoke(registry, service_ref, decision_ref)
    if not execute.ok:
        return fail(name, "execution failed")
    blob = registry.to_canonical_bytes().decode("ascii")
    for marker in (
        "password", "secret", "passphrase", "api_key", "api-key",
        "shared_secret", "community_string", "private_key", "token",
    ):
        if marker in blob:
            return fail(name, "canonical bytes carry %r" % (marker,))
    outcome_blob = str(execute.value.to_dict())
    for marker in ("password", "secret", "token"):
        if marker in outcome_blob:
            return fail(name, "execution result carries %r" % (marker,))
    # Withdrawal reasons and event details are credential-rejected.
    try:
        registry.withdraw_service(now=_T1, service_ref=service_ref, reason="password rotation")
        return fail(name, "credential-like withdrawal reason accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.INVALID_INPUT:
            return fail(name, "withdrawal reason: %s" % (exc.reason,))
    return ok(name, "no secret markers in records/bytes/results/errors")


def case_20_least_authority_context() -> Result:
    name = "case_20_least_authority_context"
    context = ServiceContext(
        integration_id="services:test", instant=_NOW, step_budget=10
    )
    # The surface is frozen and structurally enforced.
    surface = {
        attr for attr in dir(context) if not attr.startswith("_")
    }
    if not surface <= CONTEXT_SURFACE:
        return fail(name, "context grew extra surface: %s" % (surface,))
    try:
        context._integration_id = "x"  # type: ignore[attr-defined]
        return fail(name, "context attribute assignment allowed")
    except TypeError:
        pass
    try:
        del context._instant  # type: ignore[attr-defined]
        return fail(name, "context attribute deletion allowed")
    except TypeError:
        pass
    # Budget accounting is deterministic and typed.
    if context.steps_left() != 10:
        return fail(name, "initial budget wrong")
    context.charge(4)
    if context.steps_left() != 6:
        return fail(name, "charge accounting wrong")
    try:
        context.charge(7)
        return fail(name, "budget overdraft allowed")
    except Exception as exc:
        if type(exc).__name__ != "_BudgetExhausted":
            return fail(name, "overdraft raised %s" % (type(exc).__name__,))
    try:
        context.charge(True)
        return fail(name, "bool charge accepted")
    except ServiceError:
        pass
    # The absent session reader fails closed.
    if context.session_reader().lookup(_SESSION_ID) is not None:
        return fail(name, "absent reader resolved a session")
    # A mediated provider receives ONLY the context (the sandbox
    # hands nothing else to implementations).
    seen: List[Any] = []

    class _SpyExecutor(ReferenceEdgeExecutor):
        def admit(self, context, **kwargs):
            seen.append(context)
            return super().admit(context, **kwargs)

    registry = ServiceRegistry()
    registry.register_execution_provider(_SpyExecutor(), label="spy", now=_NOW)
    service_ref = _registered(registry)
    decision_ref = _decision_for(registry, service_ref)
    registry.admit_execution(
        now=_T1, service_ref=service_ref, decision_ref=decision_ref
    )
    if not seen or not isinstance(seen[0], ServiceContext):
        return fail(name, "provider did not receive a ServiceContext")
    reachable = {
        attr for attr in dir(seen[0]) if not attr.startswith("_")
    }
    if not reachable <= CONTEXT_SURFACE:
        return fail(name, "mediated context surface: %s" % (reachable,))
    return ok(name, "context surface frozen; immutable; budget typed")


def case_21_no_second_authority_ast() -> Result:
    name = "case_21_no_second_authority_ast"
    allowed_roots = (
        "__future__", "abc", "dataclasses", "typing", "types", "re",
        "hashlib", "protocol", "policy", "intent",
    )
    family_dir = os.path.join(_ROOT, "services")
    modules = sorted(
        f for f in os.listdir(family_dir) if f.endswith(".py")
    )
    if not modules:
        return fail(name, "services package empty")
    forbidden_symbols = re.compile(
        r"\b(RoutingEngine|RoutingContext|PolicyEngine|FederationStore|"
        r"ResourceStore|SessionStore|classify_capability_id|parse_node_id|"
        r"derive_node_id|derive_path_id|LinkMetrics|TopologyGraph|"
        r"FederationGrant|FederationRelationship|normalize_intent)\b"
    )
    vendor_tokens = re.compile(
        r"\b(kubernetes|kubelet|docker|containerd|openfaas|open5gs|n3iwf|"
        r"pfcp|helm|terraform|serverless|faas|paas)\b", re.IGNORECASE,
    )
    saw_citation = False
    for module_name in modules:
        path = os.path.join(family_dir, module_name)
        source = _read_source(path)
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            return fail(name, "%s: syntax error %s" % (module_name, exc))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root not in allowed_roots:
                        return fail(
                            name, "%s imports forbidden root %r"
                            % (module_name, alias.name),
                        )
                    if alias.name.split(".")[:2] == ["policy", "evaluation"]:
                        return fail(
                            name, "%s imports the WORK-010 evaluation "
                            "engine (the services layer never evaluates "
                            "policy)" % (module_name,),
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0:
                    root = (node.module or "").split(".")[0]
                    if root not in allowed_roots:
                        return fail(
                            name, "%s imports from forbidden root %r"
                            % (module_name, node.module),
                        )
                    if (node.module or "").split(".")[:2] == ["policy", "evaluation"]:
                        return fail(
                            name, "%s imports from the WORK-010 evaluation "
                            "engine (the services layer never evaluates "
                            "policy)" % (module_name,),
                        )
            elif isinstance(node, ast.Call):
                # PR #26 blocker 2 (remediation 2): the services layer
                # must never CONSTRUCT a PolicyDecision -- it is a
                # consumer (verification + extraction only).  Any
                # construction site would be a decision-manufacturing
                # capability.
                func = node.func
                target = (
                    func.id if isinstance(func, ast.Name)
                    else func.attr if isinstance(func, ast.Attribute)
                    else None
                )
                if target == "PolicyDecision":
                    return fail(
                        name, "%s constructs a PolicyDecision (the "
                        "services layer consumes decisions; it never "
                        "manufactures them)" % (module_name,),
                    )
        stripped = _strip_prose(source)
        match = forbidden_symbols.search(stripped)
        if match:
            return fail(
                name, "%s references authority symbol %s"
                % (module_name, match.group(0)),
            )
        match = vendor_tokens.search(_strip_prose(source))
        if match:
            return fail(
                name, "%s carries vendor/platform token %s"
                % (module_name, match.group(0)),
            )
        if "ts 23.548" in source.lower():
            saw_citation = True
    if not saw_citation:
        return fail(name, "edge-compute standards citation missing (TS 23.548 as DATA)")
    # The policy import is exactly the model DATA class.
    registry_source = _read_source(os.path.join(family_dir, "registry.py"))
    if "from policy.model import PolicyDecision" not in registry_source:
        return fail(name, "policy import discipline broken")
    if "from intent.model import" not in registry_source:
        return fail(name, "intent import discipline broken")
    # The authorization seam imports exactly the authority-owned
    # discriminator constant (never defines its own, never touches the
    # engine).
    auth_source = _read_source(os.path.join(family_dir, "authorization.py"))
    if "from policy.invocation import INVOCATION_BINDING_KIND" not in auth_source:
        return fail(name, "binding-kind import discipline broken")
    if "def bind" in auth_source or "bind_invocation_decision" in auth_source:
        return fail(name, "authorization seam still carries a binding constructor")
    return ok(
        name,
        "AST audit clean: no second authority, no vendor symbols, "
        "no decision manufacturing, no engine import",
    )


def case_22_validate_commit_sequence_discipline() -> Result:
    name = "case_22_validate_commit_sequence_discipline"

    class _OnceFailingCommitExecutor(ReferenceEdgeExecutor):
        """Fails the FIRST commit phase exactly once, then behaves."""

        def __init__(self) -> None:
            super().__init__()
            self._commit_failed = False

        def _commit_admit(self, admission, candidate_sequence):
            if not self._commit_failed:
                self._commit_failed = True
                raise RuntimeError("commit-phase fault")
            super()._commit_admit(admission, candidate_sequence)

    registry = ServiceRegistry()
    executor = _OnceFailingCommitExecutor()
    registry.register_execution_provider(executor, label="once", now=_NOW)
    service_ref = _registered(registry)
    decision_ref = _decision_for(registry, service_ref)
    bytes_before = registry.to_canonical_bytes()
    admit = registry.admit_execution(
        now=_T1, service_ref=service_ref, decision_ref=decision_ref
    )
    if admit.ok:
        return fail(name, "commit fault not surfaced")
    # A failed COMMIT consumes no derivation state on the executor...
    if executor.sequence_state() != 0:
        return fail(name, "commit fault consumed executor derivation state")
    # ...and the registry's canonical state is unchanged.
    if registry.to_canonical_bytes() != bytes_before:
        return fail(name, "commit fault mutated canonical state")
    # The NEXT successful admission derives the ref a clean twin
    # would derive.
    clean_registry, clean_executor = _full_registry()
    clean_ref = _registered(clean_registry)
    clean_decision = _decision_for(clean_registry, clean_ref)
    clean_admit = clean_registry.admit_execution(
        now=_T1, service_ref=clean_ref, decision_ref=clean_decision
    )
    retry = registry.admit_execution(
        now=_T1, service_ref=service_ref, decision_ref=decision_ref
    )
    if not retry.ok or not clean_admit.ok:
        return fail(name, "retry or clean admit failed")
    if retry.value.admission_ref != clean_admit.value.admission_ref:
        return fail(name, "derived refs diverged after commit fault")
    # Registry-side allocation nonce: same discipline.
    class _OnceFailingCommitRegistry(ServiceRegistry):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._commit_failed = False

        def _commit_allocate(self, allocation, candidate_sequence):
            if not self._commit_failed:
                self._commit_failed = True
                raise RuntimeError("commit-phase fault")
            super()._commit_allocate(allocation, candidate_sequence)

    failing = _OnceFailingCommitRegistry()
    failing.register_execution_provider(
        ReferenceEdgeExecutor(), label="edge", now=_NOW
    )
    compute_ref = _registered(
        failing, _advertisement(
            descriptor=_descriptor(name="seq-compute", kind="compute"),
            capacity=(ServiceCapacity("compute", 1000),),
        )
    )
    failing_bytes = failing.to_canonical_bytes()
    try:
        failing.allocate(now=_T1, kind="compute", quantity_base=5, purpose="p")
        return fail(name, "allocation commit fault not surfaced")
    except RuntimeError:
        pass
    if failing._sequence != 0:  # noqa: SLF001
        return fail(name, "commit fault consumed registry derivation state")
    if failing.to_canonical_bytes() != failing_bytes:
        return fail(name, "allocation commit fault mutated canonical state")
    retry_alloc = failing.allocate(
        now=_T1, kind="compute", quantity_base=5, purpose="p"
    )
    if not retry_alloc.ok:
        return fail(name, "allocation retry failed")
    clean_registry2 = ServiceRegistry()
    clean_registry2.register_execution_provider(
        ReferenceEdgeExecutor(), label="edge", now=_NOW
    )
    _registered(
        clean_registry2, _advertisement(
            descriptor=_descriptor(name="seq-compute", kind="compute"),
            capacity=(ServiceCapacity("compute", 1000),),
        )
    )
    clean_alloc = clean_registry2.allocate(
        now=_T1, kind="compute", quantity_base=5, purpose="p"
    )
    if retry_alloc.value != clean_alloc.value:
        return fail(name, "allocation refs diverged after commit fault")
    # Validate-phase faults consume nothing either.
    registry3, executor3 = _full_registry()
    service_ref3 = _registered(registry3)
    decision_ref3 = _decision_for(registry3, service_ref3)
    try:
        registry3.admit_execution(
            now=_T1, service_ref=service_ref3, decision_ref="services:decision:" + "0" * 32
        )
        return fail(name, "validate fault not surfaced")
    except ServiceError:
        pass
    if executor3.sequence_state() != 0:
        return fail(name, "validate fault consumed derivation state")
    return ok(name, "validate/commit discipline holds on both derivation sites")


def case_23_canonical_state_clean() -> Result:
    name = "case_23_canonical_state_clean"
    store, session_id, _d, _p = _compose_real_session()
    fed_store, relationship_id, _dom = _compose_real_federation()
    registry, executor = _full_registry(
        session_reader=_StoreSessionReader(store),
        federation_reader=_StoreFederationReader(fed_store),
    )
    service_ref = _registered(
        registry, _advertisement(visibility=VisibilityScope.FEDERATED)
    )
    registry.apply_federation_exposure(
        now=_T1, service_ref=service_ref, relationship_id=relationship_id
    )
    decision_ref = _decision_for(
        registry, service_ref, now=_T2, session_id=session_id
    )
    execute, _adm = _invoke(
        registry, service_ref, decision_ref, now=_T2, session_id=session_id
    )
    if not execute.ok:
        return fail(name, "execution failed")
    registry.allocate(now=_T2, kind="edge-service-capacity", quantity_base=1, purpose="audit")
    snapshot = registry.snapshot()
    blob = registry.to_canonical_bytes().decode("ascii")
    # Shape is frozen.
    if sorted(snapshot.keys()) != [
        "admission_count", "admissions", "allocations", "closed",
        "decision_revocations", "decisions", "events", "exposures",
        "integration_id", "placements", "registered_count", "services",
        "tombstones",
    ]:
        return fail(name, "snapshot shape drifted: %s" % (sorted(snapshot.keys()),))
    # No diagnostics cross into canonical state.
    for marker in (
        "local-edge", "providers", "computed_health", "upstream",
        "sequence", "step", "budget", "sandbox", "executor",
        "pid", "socket", "filesystem", "traceback", '"label"',
    ):
        if marker in blob:
            return fail(name, "canonical bytes carry %r" % (marker,))
    # Events are append-only and complete.
    types = [e["event_type"] for e in snapshot["events"]]
    expected_prefix = [
        "provider-registered", "service-registered", "exposure-applied",
        "decision-applied", "admission-established", "admission-released",
        "allocation-reserved",
    ]
    if types[: len(expected_prefix)] != expected_prefix:
        return fail(name, "event order drifted: %s" % (types,))
    # Data-path executions appended NO events.
    if types.count("admission-established") != 1:
        return fail(name, "data-path ops appended events")
    return ok(name, "canonical state: authoritative facts only")


def case_24_determinism() -> Result:
    name = "case_24_determinism"
    script = r"""
import sys, os
sys.path.insert(0, %r)
import hashlib
from services import (
    ServiceRegistry, ReferenceEdgeExecutor, ServiceAdvertisement,
    ServiceCapacity, ServiceDescriptor, AdvertisementEvidence,
    VisibilityScope, derive_advertisement_claim_digest,
)
from policy.evaluation import PolicyEngine
from policy.model import Operation, PolicyContext, PolicyDomain, PolicyRule, PolicySet

NOW = "2026-08-27T00:00:00Z"
T1 = "2026-08-27T00:01:00Z"
T2 = "2026-08-27T00:02:00Z"
NODE_A = "adcos:node:test.profile.v1:" + "a" * 64
NODE_B = "adcos:node:test.profile.v1:" + "b" * 64
ISSUER = "adcos:node:test.profile.v1:" + "0" * 64

def born_bound_decision(service_ref):
    # The born-bound composition recipe: the exact invocation scope is
    # declared in the evaluation context and the WORK-010 evaluator
    # derives the digest-covered binding from it (there is no
    # services-layer binding constructor).
    ps = PolicySet(set_id="ps-w025-invocation", version=1,
        rules=(PolicyRule(rule_id="svc-allow", domain=PolicyDomain.SERVICE,
            effect="allow", operation=Operation.SERVICE_INVOKE),),
        issuer_node_id=ISSUER, valid_from="2026-01-01T00:00:00Z",
        valid_until="2028-01-01T00:00:00Z")
    ctx = PolicyContext(operation=Operation.SERVICE_INVOKE,
        evaluation_instant=NOW, federation_domain="village-a",
        resource_refs=(service_ref,),
        extensions=({"kind": "adcos.service-invocation",
            "operation": Operation.SERVICE_INVOKE, "service_ref": service_ref,
            "session_id": "", "caller_node_id": "", "tenant_domain": "village-a"},))
    res = PolicyEngine().evaluate(ps, ctx)
    assert res.ok and res.decision is not None, res.detail
    return res.decision

def build():
    reg = ServiceRegistry()
    reg.register_execution_provider(ReferenceEdgeExecutor(), label="local-edge", now=NOW)
    d = ServiceDescriptor(name="weather-cache", service_kind="cache", tenant_domain="village-a",
        capability_refs=("capability.profile.service.weather-cache",),
        service_labels=("weather",), locality_labels=("village-a",),
        privacy_labels=("public",))
    adv = ServiceAdvertisement(descriptor=d, host_node_id=NODE_A, registered_at=NOW,
        expires_at="2027-01-01T00:00:00Z", visibility=VisibilityScope.FEDERATED,
        endpoint_ref="edge://slot-3", capacity=(ServiceCapacity("edge-service-capacity", 2),))
    ev = AdvertisementEvidence(observer_node_id=NODE_A, reporter_node_id=NODE_A,
        source_class="direct-observation", observed_at=NOW,
        claim_digest=derive_advertisement_claim_digest(adv))
    reg.register_service(now=NOW, advertisement=adv, evidence=ev)
    dec = born_bound_decision(adv.service_ref)
    r = reg.apply_policy_decision(now=T1, policy_decision=dec)
    assert r.ok
    a = reg.admit_execution(now=T1, service_ref=adv.service_ref, decision_ref=r.value)
    assert a.ok
    e = reg.execute_request(now=T1, admission_ref=a.value.admission_ref, request_payload=b"determinism")
    assert e.ok
    rl = reg.release_execution(now=T1, admission_ref=a.value.admission_ref)
    assert rl.ok
    reg.relocate_service(now=T2, service_ref=adv.service_ref, target_host_node_id=NODE_B)
    d2 = reg.apply_policy_decision(now=T2, policy_decision=dec)
    assert d2.ok
    reg.withdraw_service(now=T2, service_ref=adv.service_ref, reason="done")
    return reg.content_digest()

digests = {build() for _ in range(3)}
assert len(digests) == 1
print(digests.pop())
""" % (_ROOT,)
    # In-process twin runs.
    first = _run_script(script)
    second = _run_script(script)
    if first is None or first != second:
        return fail(name, "in-process twin digests diverged")
    # Hash-seed independence.
    seeds = ("0", "1", "7919")
    outputs = []
    for seed in seeds:
        env = dict(os.environ, PYTHONHASHSEED=seed)
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, env=env, cwd=_ROOT,
        )
        if proc.returncode != 0:
            return fail(name, "seed %s failed: %s" % (seed, proc.stderr[-300:]))
        outputs.append(proc.stdout.strip())
    if len(set(outputs)) != 1 or outputs[0] != first:
        return fail(name, "hash-seed dependent output: %s" % (outputs,))
    return ok(name, "byte-identical across runs and PYTHONHASHSEED 0/1/7919")


def _run_script(script: str) -> Optional[str]:
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, cwd=_ROOT,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def case_25_frozen_spec_intact() -> Result:
    name = "case_25_frozen_spec_intact"
    diff = subprocess.run(
        ["git", "diff", "origin/main", "HEAD", "--", "spec/"],
        capture_output=True, text=True, cwd=_ROOT,
    )
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", "spec/"],
        capture_output=True, text=True, cwd=_ROOT,
    )
    if diff.stdout.strip() or status.stdout.strip():
        return fail(name, "spec/ not byte-identical to origin/main")
    prompts = subprocess.run(
        ["git", "diff", "origin/main", "HEAD", "--", "spec/prompts/"],
        capture_output=True, text=True, cwd=_ROOT,
    )
    if prompts.stdout.strip():
        return fail(name, "spec/prompts/ modified")
    return ok(name, "spec/ byte-identical to origin/main; working tree clean")


def case_26_py_compile_clean() -> Result:
    name = "case_26_py_compile_clean"
    family_dir = os.path.join(_ROOT, "services")
    for module_name in sorted(os.listdir(family_dir)):
        if not module_name.endswith(".py"):
            continue
        try:
            py_compile.compile(
                os.path.join(family_dir, module_name), doraise=True
            )
        except py_compile.PyCompileError as exc:
            return fail(name, "%s: %s" % (module_name, exc))
    try:
        py_compile.compile(os.path.abspath(__file__), doraise=True)
    except py_compile.PyCompileError as exc:
        return fail(name, "selftest: %s" % (exc,))
    return ok(name, "py_compile clean for services/ and the selftest")


def case_27_policy_negative_matrix() -> Result:
    name = "case_27_policy_negative_matrix"
    registry, _executor = _full_registry()
    service_ref = _registered(registry)
    # Non-genuine decision object.
    try:
        registry.apply_policy_decision(
            now=_T1,
            policy_decision={"effect": "allow"},  # type: ignore[arg-type]
        )
        return fail(name, "non-genuine decision accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.INVALID_INPUT:
            return fail(name, "non-genuine: %s" % (exc.reason,))
    # An engine ALLOW with NO invocation binding: the authorized
    # scope is not tied to the decision -- fail closed.
    unbound = _allow_decision(evaluation_instant=_T1)
    try:
        registry.apply_policy_decision(now=_T1, policy_decision=unbound)
        return fail(name, "unbound decision accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.DECISION_SCOPE_MISMATCH:
            return fail(name, "unbound: %s" % (exc.reason,))
    # Tampered decision DATA (id does not bind to canonical bytes).
    tampered = _bound_decision(
        evaluation_instant=_T1, decision_id="f" * 64,
        service_ref=service_ref,
    )
    try:
        registry.apply_policy_decision(now=_T1, policy_decision=tampered)
        return fail(name, "tampered decision accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.INVALID_INPUT:
            return fail(name, "tampered: %s" % (exc.reason,))
    # REBOUND decision: a valid binding for service B re-stamped with
    # service A's decision id -- the digest no longer binds, so the
    # manufactured scope is rejected (the PR #26 blocker-2 attack).
    rebound = _bound_decision(evaluation_instant=_T1, service_ref=service_ref)
    rebound = PolicyDecision(
        decision_id=rebound.decision_id,
        effect=rebound.effect,
        code=rebound.code,
        detail=rebound.detail,
        matched_rule_ids=rebound.matched_rule_ids,
        policy_set_id=rebound.policy_set_id,
        policy_set_version=rebound.policy_set_version,
        evaluation_instant=rebound.evaluation_instant,
        conflict_trace=rebound.conflict_trace,
        extensions=(
            dict(
                rebound.extensions[0],
                service_ref=_registered(
                    registry,
                    _advertisement(descriptor=_descriptor(name="rebind-target")),
                ),
            ),
        ),
    )
    try:
        registry.apply_policy_decision(now=_T1, policy_decision=rebound)
        return fail(name, "rebound decision accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.INVALID_INPUT:
            return fail(name, "rebound: %s" % (exc.reason,))
    # A binding for another OPERATION is a scope mismatch (the digest
    # is VALID over the wrong-operation content -- the rejection comes
    # from the binding itself, exactly as a composition root binding a
    # route.compute decision would be rejected for invocation).
    wrong_op = _bound_decision(
        evaluation_instant=_T1, service_ref=service_ref,
    )
    wrong_op = PolicyDecision(
        decision_id="0" * 64,
        effect=wrong_op.effect,
        code=wrong_op.code,
        detail=wrong_op.detail,
        matched_rule_ids=wrong_op.matched_rule_ids,
        policy_set_id=wrong_op.policy_set_id,
        policy_set_version=wrong_op.policy_set_version,
        evaluation_instant=wrong_op.evaluation_instant,
        conflict_trace=wrong_op.conflict_trace,
        extensions=(
            dict(wrong_op.extensions[0], operation="route.compute"),
        ),
    )
    wrong_op = PolicyDecision(
        decision_id=hashlib.sha256(wrong_op.canonical_bytes()).hexdigest(),
        effect=wrong_op.effect,
        code=wrong_op.code,
        detail=wrong_op.detail,
        matched_rule_ids=wrong_op.matched_rule_ids,
        policy_set_id=wrong_op.policy_set_id,
        policy_set_version=wrong_op.policy_set_version,
        evaluation_instant=wrong_op.evaluation_instant,
        conflict_trace=wrong_op.conflict_trace,
        extensions=wrong_op.extensions,
    )
    try:
        registry.apply_policy_decision(now=_T1, policy_decision=wrong_op)
        return fail(name, "other-operation binding accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.DECISION_SCOPE_MISMATCH:
            return fail(name, "other-operation: %s" % (exc.reason,))
    # A binding whose tenant is not the service record's tenant:
    # cross-tenant authorization fails closed.
    cross_tenant = _bound_decision(
        evaluation_instant=_T1, service_ref=service_ref,
        tenant_domain="village-z",
    )
    try:
        registry.apply_policy_decision(now=_T1, policy_decision=cross_tenant)
        return fail(name, "cross-tenant authorization accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.TENANT_ISOLATION:
            return fail(name, "cross-tenant: %s" % (exc.reason,))
    # Future-dated decision (stale fails closed).
    future = _bound_decision(
        evaluation_instant=_T3, service_ref=service_ref,
    )
    try:
        registry.apply_policy_decision(now=_T1, policy_decision=future)
        return fail(name, "future-dated decision accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.DECISION_STALE:
            return fail(name, "future-dated: %s" % (exc.reason,))
    # Applied decision + negative follow-ups.
    decision_ref = _decision_for(registry, service_ref, now=_T1)
    # Exact re-application fails (deterministic conflict): the SAME
    # policy decision at the SAME applied instant derives the same
    # ref.
    try:
        registry.apply_policy_decision(
            now=_T1,
            policy_decision=_bound_decision(
                evaluation_instant=_T1, service_ref=service_ref,
            ),
        )
        return fail(name, "exact re-application accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.DECISION_EXISTS:
            return fail(name, "re-application: %s" % (exc.reason,))
    # A different decision at a non-advancing instant fails (same
    # scope as the applied decision above -- the session-scoped
    # negative comes further below).
    later_same_instant = _bound_decision(
        evaluation_instant=_NOW, service_ref=service_ref,
    )
    try:
        registry.apply_policy_decision(
            now=_T1, policy_decision=later_same_instant,
        )
        return fail(name, "non-advancing instant accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.DECISION_STALE:
            return fail(name, "non-advancing: %s" % (exc.reason,))
    # Denied effect (PR #26 third review, finding 3): a genuine
    # engine DENY applies at a LATER instant ONLY as a per-scope
    # revocation lineage marker -- never as authorization -- and it
    # INVALIDATES the earlier standing allow for the same scope.
    denied = _bound_decision(
        evaluation_instant=_T3, effect="deny", service_ref=service_ref,
    )
    revoked = registry.apply_policy_decision(
        now=_T3, policy_decision=denied
    )
    if not revoked.ok:
        return fail(name, "genuine deny rejected: %s" % (revoked.detail,))
    try:
        registry.admit_execution(
            now=_T3, service_ref=service_ref, decision_ref=revoked.value
        )
        return fail(name, "deny ref authorized execution")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.DECISION_UNKNOWN:
            return fail(name, "deny ref: %s" % (exc.reason,))
    try:
        registry.admit_execution(
            now=_T3, service_ref=service_ref, decision_ref=decision_ref
        )
        return fail(name, "earlier ALLOW survived a later DENY")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.REAUTHORIZATION_REQUIRED:
            return fail(name, "revoked allow: %s" % (exc.reason,))
    # Session-bound execution requires a secureable session.
    session_decision = _decision_for(
        registry, service_ref, now=_T2, session_id=_OTHER_SESSION_ID
    )
    try:
        registry.admit_execution(
            now=_T2, service_ref=service_ref, decision_ref=session_decision,
            session_id=_OTHER_SESSION_ID,
        )
        return fail(name, "unsecureable session admitted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.SESSION_NOT_SECUREABLE:
            return fail(name, "session check: %s" % (exc.reason,))
    # Without a session authority injected at all: fail closed.
    bare_registry, _b = _full_registry()
    bare_ref = _registered(bare_registry)
    bare_decision = _decision_for(
        bare_registry, bare_ref, now=_T1, session_id=_SESSION_ID
    )
    try:
        bare_registry.admit_execution(
            now=_T1, service_ref=bare_ref, decision_ref=bare_decision,
            session_id=_SESSION_ID,
        )
        return fail(name, "execution without session authority")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.SESSION_NOT_SECUREABLE:
            return fail(name, "no authority: %s" % (exc.reason,))
    return ok(name, "denied/stale/future/tampered/rebound/scope/session all fail closed")

def case_28_policy_change_between_discovery_execution() -> Result:
    name = "case_28_policy_change_between_discovery_execution"
    registry, _executor = _full_registry()
    service_ref = _registered(
        registry, _advertisement(
            descriptor=_descriptor(name="billing-service"),
            policy_controlled=True,
        )
    )
    first = _decision_for(registry, service_ref, now=_T1)
    # Discovery WITH the authorization: the service is visible.
    found = registry.discover_services(
        now=_T1, tenant_domain="village-a", decision_refs=(first,)
    )
    if service_ref not in {c.service_ref for c in found}:
        return fail(name, "authorized discovery hid the service")
    # Without the authorization: hidden.
    found = registry.discover_services(now=_T1, tenant_domain="village-a")
    if service_ref in {c.service_ref for c in found}:
        return fail(name, "unauthorized discovery exposed the service")
    # Policy changes between discovery and execution: a NEWER
    # decision supersedes; executing with the old one fails.
    second = _decision_for(registry, service_ref, now=_T2)
    try:
        registry.admit_execution(
            now=_T2, service_ref=service_ref, decision_ref=first
        )
        return fail(name, "superseded decision admitted execution")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.REAUTHORIZATION_REQUIRED:
            return fail(name, "superseded: %s" % (exc.reason,))
    execute, _adm = _invoke(registry, service_ref, second, now=_T2)
    if not execute.ok:
        return fail(name, "current decision failed: %s" % (execute.detail,))
    return ok(name, "policy change forces re-authorization between discovery and execution")


def case_29_tombstone_replay_protection() -> Result:
    name = "case_29_tombstone_replay_protection"
    registry, _executor = _full_registry()
    advertisement = _advertisement()
    service_ref = _registered(registry, advertisement)
    registry.withdraw_service(now=_T1, service_ref=service_ref, reason="rotated")
    # Replaying the SAME advertisement (registered_at <= tombstone)
    # is rejected.
    try:
        registry.register_service(
            now=_T2, advertisement=advertisement,
            evidence=_evidence(advertisement),
        )
        return fail(name, "tombstone replay accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.ADVERTISEMENT_REPLAY:
            return fail(name, "replay: %s" % (exc.reason,))
    # An EARLIER advertisement is also a replay.
    older = _advertisement(registered_at="2026-08-20T00:00:00Z")
    try:
        registry.register_service(
            now=_T2, advertisement=older, evidence=_evidence(older)
        )
        return fail(name, "earlier advertisement accepted after tombstone")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.ADVERTISEMENT_REPLAY:
            return fail(name, "earlier replay: %s" % (exc.reason,))
    # A STRICTLY LATER advertisement legitimately re-registers (a new
    # lifecycle epoch; the tombstone stays as audit history).
    newer = _advertisement(registered_at=_T2)
    result = registry.register_service(
        now=_T2, advertisement=newer, evidence=_evidence(newer, observed_at=_T2)
    )
    if not result.ok:
        return fail(name, "legitimate re-registration rejected: %s" % (result.detail,))
    snapshot = registry.snapshot()
    if not snapshot["tombstones"]:
        return fail(name, "tombstone history not retained")
    if len(snapshot["services"]) != 1:
        return fail(name, "record count wrong after re-registration")
    return ok(name, "replay rejected; later re-registration allowed; history kept")


def case_30_real_authority_composition() -> Result:
    name = "case_30_real_authority_composition"
    from intent.model import ConnectivityIntent, Constraint
    from intent.normalization import normalize_intent

    # REAL WORK-009 intent (normalized; consumed as DATA).
    intent = ConnectivityIntent(
        intent_id="w025-real-intent",
        requester_node_id=_NODE_UE,
        issued_at=_NOW,
        requirements=(
            Constraint(
                constraint_id="s1", dimension="service", operator="=",
                value="weather", hardness="hard",
            ),
        ),
        preferences=(
            Constraint(
                constraint_id="l1", dimension="latency", operator="<=",
                value=20, unit="ms", hardness="soft", weight=1,
            ),
        ),
    )
    normalized = normalize_intent(intent)
    if not normalized.ok:
        return fail(name, "real intent failed normalization: %s" % (normalized.detail,))
    # REAL WORK-012 session.
    store, session_id, policy_decision, _path = _compose_real_session()
    # REAL WORK-015 federation store + reader.
    fed_store, relationship_id, _domain = _compose_real_federation()
    reader = _StoreFederationReader(fed_store)
    registry, _executor = _full_registry(
        session_reader=_StoreSessionReader(store),
        federation_reader=reader,
    )
    # Register a federated service and expose it (the REAL WORK-015
    # check_scope authorizes service.discover).
    advertisement = _advertisement(
        descriptor=_descriptor(name="weather-cache"),
        visibility=VisibilityScope.FEDERATED,
    )
    service_ref = _registered(registry, advertisement)
    exposure = registry.apply_federation_exposure(
        now=_T1, service_ref=service_ref, relationship_id=relationship_id
    )
    if not exposure.ok:
        return fail(name, "real-federation exposure failed: %s" % (exposure.detail,))
    # Discovery through the REAL intent + a REAL WORK-010 engine
    # evaluation of the exact invocation scope: the composition root
    # declares the (service, session, caller, tenant) descriptor in
    # the service.invoke PolicyContext, the evaluator binds it into
    # the decision's digest-covered extensions (born bound -- there
    # is no services-layer binding constructor), and the registry
    # extracts the scope from the decision itself.
    bound_decision = _engine_invocation_decision(
        service_ref,
        evaluation_instant=_T1,
        session_id=session_id,
        caller_node_id=_NODE_UE,
        tenant_domain=advertisement.descriptor.tenant_domain,
    )
    # The REAL session-policy ALLOW (genuinely unbound for invocation
    # purposes) must NOT be applicable as an invocation authorization
    # -- there is no exported services API to convert it (case_40
    # pins that absence structurally).
    try:
        registry.apply_policy_decision(
            now=_T1, policy_decision=policy_decision,
        )
        return fail(
            name, "session-policy ACCEPTED as invocation authorization"
        )
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.DECISION_SCOPE_MISMATCH:
            return fail(name, "session-policy ALLOW: %s" % (exc.reason,))
    decision_ref = registry.apply_policy_decision(
        now=_T1, policy_decision=bound_decision,
    )
    if not decision_ref.ok:
        return fail(name, "real policy decision rejected: %s" % (decision_ref.detail,))
    found = registry.discover_services(
        now=_T1, tenant_domain="village-a", intent=intent, host_node_id=_NODE_A,
        session_id=session_id, caller_node_id=_NODE_UE,
        decision_refs=(decision_ref.value,),
    )
    if {c.service_ref for c in found} != {service_ref}:
        return fail(name, "real intent/policy discovery failed")
    # Execute under the real session.
    execute, admission = _invoke(
        registry, service_ref, decision_ref.value,
        now=_T1, session_id=session_id, caller_node_id=_NODE_UE,
    )
    if not execute.ok:
        return fail(name, "real-session execution failed: %s" % (execute.detail,))
    if admission.session_id != session_id:
        return fail(name, "real session identity lost")
    # The peer side (real federation data) discovers the exposed
    # service through its own registry.
    peer_registry, _peer_executor = _full_registry(federation_reader=reader)
    claims = export_service_exposures(
        (registry.lookup_service(
        now=_T1, service_ref=service_ref, tenant_domain="village-a"
    ),),
        registry._exposures.values(),  # noqa: SLF001
        relationship_id=relationship_id,
    )
    peer_advertisement = _advertisement_from_claim(claims[0], relationship_id)
    imported = peer_registry.register_service(
        now=_T2, advertisement=peer_advertisement,
        evidence=_evidence(
            peer_advertisement, source_class="remote-claim",
            observer=_NODE_B, reporter=_NODE_B, observed_at=_T2,
            provenance="federation-exchange",
        ),
    )
    if not imported.ok:
        return fail(name, "peer import failed: %s" % (imported.detail,))
    peer_found = peer_registry.discover_services(
        now=_T2, tenant_domain="village-a", include_federated=True
    )
    if service_ref not in {c.service_ref for c in peer_found}:
        return fail(name, "peer federated discovery failed")
    # All composed authorities are REAL objects.
    from sessions import SessionStore as _RealStore
    from federation import FederationStore as _RealFedStore
    from intent.model import ConnectivityIntent as _RealIntent
    if not isinstance(store, _RealStore) or not isinstance(fed_store, _RealFedStore):
        return fail(name, "authorities are not the real stores")
    if not isinstance(intent, _RealIntent):
        return fail(name, "intent is not the real model")
    return ok(name, "REAL W009 intent + W010 decision + W012 session + W015 federation composed")


def case_31_observation_honesty() -> Result:
    name = "case_31_observation_honesty"
    registry, executor = _full_registry()
    fresh = _registered(registry)
    _registered(
        registry, _advertisement(
            descriptor=_descriptor(name="stale-obs"), expires_at=_EXPIRED,
        )
    )
    withdrawn = _registered(
        registry, _advertisement(descriptor=_descriptor(name="gone-obs"))
    )
    registry.withdraw_service(now=_T1, service_ref=withdrawn, reason="retired")
    decision = _decision_for(registry, fresh)
    execute, _adm = _invoke(registry, fresh, decision, now=_T1)
    if not execute.ok:
        return fail(name, "execution failed")
    observation = registry.observe(now=_T1)
    if observation.registered_services != 2:
        return fail(name, "registered count: %d" % (observation.registered_services,))
    if observation.available_services != 1:
        return fail(name, "available count: %d" % (observation.available_services,))
    if observation.expired_services != 1:
        return fail(name, "expired count: %d" % (observation.expired_services,))
    if observation.withdrawn_services != 1:
        return fail(name, "withdrawn count: %d" % (observation.withdrawn_services,))
    if observation.executed_requests != 1:
        return fail(name, "executed count: %d" % (observation.executed_requests,))
    if observation.upstream_available != 1:
        return fail(name, "upstream should be available")
    # The outage is reported honestly.
    registry.set_upstream_state(available=False)
    observation = registry.observe(now=_T2)
    if observation.upstream_available != 0:
        return fail(name, "outage not reported")
    if observation.registered_services != 2:
        return fail(name, "outage corrupted local counts")
    # Provider-side observation is honest too.
    provider_observation = ServiceObservation(
        samples=(
            ("active-admissions", 0),
            ("executed-requests", 1),
            ("failed-requests", 0),
        ),
        executed_requests=1,
    )
    if provider_observation.to_dict()["executed_requests"] != 1:
        return fail(name, "provider observation dict wrong")
    # Bad metric names are rejected.
    try:
        ServiceObservation(samples=(("bogus-metric", 1),))
        return fail(name, "unknown metric name accepted")
    except ServiceError:
        pass
    return ok(name, "observations honest at every level")


def case_32_no_core_leakage() -> Result:
    name = "case_32_no_core_leakage"
    core_roots = (
        "identity", "capabilities", "discovery", "topology", "resources",
        "intent", "policy", "routing", "sessions", "multipath",
        "mobility", "federation", "transport", "protocol",
    )
    ref_pattern = re.compile(
        r"services:(service|decision|admission|allocation|execution|exposure):"
    )
    for root in core_roots:
        root_dir = os.path.join(_ROOT, root)
        if not os.path.isdir(root_dir):
            return fail(name, "missing core root %r" % (root,))
        for module_name in sorted(os.listdir(root_dir)):
            if not module_name.endswith(".py"):
                continue
            source = _read_source(os.path.join(root_dir, module_name))
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] == "services":
                            return fail(
                                name, "%s/%s imports the service layer"
                                % (root, module_name),
                            )
                elif isinstance(node, ast.ImportFrom):
                    if node.level == 0 and (node.module or "").split(".")[0] == "services":
                        return fail(
                            name, "%s/%s imports from the service layer"
                            % (root, module_name),
                        )
            if "ServiceRegistry" in source:
                return fail(name, "%s/%s references ServiceRegistry" % (root, module_name))
            if ref_pattern.search(source):
                return fail(name, "%s/%s references service refs" % (root, module_name))
    # Sibling adapter families do not reference the service layer.
    adapters_dir = os.path.join(_ROOT, "adapters")
    for family in sorted(os.listdir(adapters_dir)):
        family_dir = os.path.join(adapters_dir, family)
        if not os.path.isdir(family_dir):
            continue
        for module_name in sorted(os.listdir(family_dir)):
            if not module_name.endswith(".py"):
                continue
            source = _read_source(os.path.join(family_dir, module_name))
            if re.search(r"\bservices\b", _strip_prose(source)):
                return fail(
                    name, "adapters/%s/%s references the service layer"
                    % (family, module_name),
                )
    return ok(name, "no core module or adapter family imports services")


def case_33_unavailable_at_execution() -> Result:
    name = "case_33_unavailable_at_execution"
    registry, executor = _full_registry()
    service_ref = _registered(registry)
    decision_ref = _decision_for(registry, service_ref)
    # The executor becomes unavailable (partition): the service is
    # KNOWN and ELIGIBLE but unavailable AT EXECUTION TIME -- a typed
    # value, distinct from unknown/stale/withdrawn.
    executor.set_executor_state(available=False)
    admit = registry.admit_execution(
        now=_T1, service_ref=service_ref, decision_ref=decision_ref
    )
    if admit.ok or admit.reason != ServiceReasonCode.SERVICE_UNAVAILABLE:
        return fail(name, "partitioned executor: %s" % (admit.reason,))
    # Lookup still succeeds (the record is fine).
    registry.lookup_service(
        now=_T1, service_ref=service_ref, tenant_domain="village-a"
    )
    # Strict toggling discipline.
    try:
        executor.set_executor_state(available=False)
        return fail(name, "re-applied availability state accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.ILLEGAL_STATE:
            return fail(name, "toggle discipline: %s" % (exc.reason,))
    # Recovery restores execution.
    executor.set_executor_state(available=True)
    execute, _adm = _invoke(registry, service_ref, decision_ref, now=_T2)
    if not execute.ok:
        return fail(name, "recovery failed: %s" % (execute.detail,))
    return ok(name, "unavailable-at-execution distinct and recoverable")


def case_34_budget_isolation() -> Result:
    name = "case_34_budget_isolation"
    # Step budgets are per-operation contexts (a fresh context per
    # mediated operation, the WORK-024 discipline): open (4) + health
    # probe (1) fit in 6, but admit (8) overdraws -> typed failure.
    registry, _executor = _full_registry(step_budget=6)
    service_ref = _registered(registry)
    decision_ref = _decision_for(registry, service_ref)
    admit = registry.admit_execution(
        now=_T1, service_ref=service_ref, decision_ref=decision_ref
    )
    if admit.ok or admit.reason != ServiceReasonCode.BUDGET_EXHAUSTED:
        return fail(name, "budget exhaustion: %r ok=%s" % (admit.reason, admit.ok))
    if service_ref not in [
        s["service_ref"] for s in registry.snapshot()["services"]
    ]:
        return fail(name, "budget failure corrupted records")
    if registry.snapshot()["admissions"]:
        return fail(name, "budget failure left an admission behind")
    # A comfortable budget executes fine.
    roomy, _roomy_executor = _full_registry(step_budget=DEFAULT_STEP_BUDGET)
    roomy_ref = _registered(roomy)
    roomy_decision = _decision_for(roomy, roomy_ref)
    execute, _adm = _invoke(roomy, roomy_ref, roomy_decision)
    if not execute.ok:
        return fail(name, "roomy budget failed: %s" % (execute.detail,))
    return ok(name, "step budgets fail closed as typed values")


def case_35_vocabulary_cross_checks() -> Result:
    name = "case_35_vocabulary_cross_checks"
    from resources.model import ResourceKind
    from federation.model import Scope
    from capabilities.classification import classify_capability_id

    # Capacity kinds are exactly the handoff's WORK-008 set, and all
    # are genuinely WORK-008 consumable kinds (no second vocabulary).
    if set(SERVICE_CAPACITY_KINDS) != {
        "compute", "storage", "bandwidth", "energy", "edge-service-capacity",
    }:
        return fail(name, "capacity kind set drifted: %s" % (SERVICE_CAPACITY_KINDS,))
    for kind in SERVICE_CAPACITY_KINDS:
        if kind not in ResourceKind.values():
            return fail(name, "kind %r is not a WORK-008 kind" % (kind,))
    if "edge-service-capacity" not in ResourceKind.CONSUMABLE:
        return fail(name, "edge-service-capacity not consumable in WORK-008")
    # Federation scope constants are the frozen WORK-015 values.
    if SERVICE_DISCOVER_SCOPE != Scope.SERVICE_DISCOVER:
        return fail(name, "service.discover scope drifted from WORK-015")
    from services import SERVICE_INVOKE_SCOPE
    if SERVICE_INVOKE_SCOPE != Scope.SERVICE_INVOKE:
        return fail(name, "service.invoke scope drifted from WORK-015")
    # The invocation-binding operation constant is the frozen WORK-010
    # Operation value (PR #26 blocker 2: the binding authorizes exactly
    # the frozen policy operation; no second operation vocabulary).
    from policy.model import Operation
    from services import (
        SERVICE_INVOKE_OPERATION as _OP,
        INVOCATION_BINDING_KIND as _KIND,
    )
    if _OP != Operation.SERVICE_INVOKE:
        return fail(name, "binding operation drifted from WORK-010")
    if _KIND != "adcos.service-invocation":
        return fail(name, "binding kind discriminator drifted")
    # Capability grammar agrees with the WORK-002 classifier.
    sample = "capability.profile.service.weather-cache"
    if classify_capability_id(sample) != "unknown_but_well_formed":
        return fail(name, "classifier disagrees on %r" % (sample,))
    if classify_capability_id("capability.bogus.weather-cache") != "invalid":
        return fail(name, "classifier accepted a malformed id")
    if classify_capability_id("capability.core.multipath") != "known":
        return fail(name, "classifier rejected a known core capability")
    # The model vocabulary validates against the classifier grammar.
    from services.validation import validate_capability_ref
    validate_capability_ref(sample)
    try:
        validate_capability_ref("capability.bogus.x")
        return fail(name, "malformed capability ref accepted")
    except ServiceError:
        pass
    return ok(name, "vocabularies cross-checked against W002/W008/W015")


def case_36_registration_conflict_and_host_guard() -> Result:
    name = "case_36_registration_conflict_and_host_guard"
    registry, _executor = _full_registry()
    service_ref = _registered(registry)
    # Host change through register_service is rejected: placement
    # changes must use relocate_service (never silent).
    moved = _advertisement(host=_NODE_B)
    try:
        registry.register_service(
            now=_T1, advertisement=moved, evidence=_evidence(moved, observed_at=_T1)
        )
        return fail(name, "silent host change accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.SERVICE_CONFLICT:
            return fail(name, "host guard: %s" % (exc.reason,))
    # A non-host content update with a STRICTLY LATER registered_at is
    # an explicit, auditable, forward-in-time update (PR #26 third
    # review, finding 1: equal-time different-content claims are an
    # explicit conflict -- see case_41 -- so a refresh must advance
    # registered_at).
    refreshed = _advertisement(
        registered_at=_T1, expires_at="2027-06-01T00:00:00Z"
    )
    result = registry.register_service(
        now=_T1, advertisement=refreshed,
        evidence=_evidence(refreshed, observed_at=_T1),
    )
    if not result.ok:
        return fail(name, "legitimate update rejected: %s" % (result.detail,))
    events = [e["event_type"] for e in registry.snapshot()["events"]]
    if ServiceEventType.SERVICE_UPDATED not in events:
        return fail(name, "update not audited: %s" % (events,))
    record = registry.lookup_service(
        now=_T1, service_ref=service_ref, tenant_domain="village-a"
    )
    if record.expires_at != "2027-06-01T00:00:00Z":
        return fail(name, "update not applied")
    if registry.registered_count != 1:
        return fail(name, "update duplicated the record")
    # Peer-claim discipline: remote evidence without a relationship
    # is rejected.
    peer_ad = _advertisement(visibility=VisibilityScope.FEDERATED)
    try:
        registry.register_service(
            now=_T1, advertisement=peer_ad,
            evidence=_evidence(peer_ad, source_class="remote-claim"),
        )
        return fail(name, "relationship-less peer claim accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.INVALID_INPUT:
            return fail(name, "peer claim: %s" % (exc.reason,))
    # And local evidence must not carry a relationship.
    tainted = _advertisement(
        federation_relationship_id="sha256:" + "7" * 64
    )
    try:
        registry.register_service(
            now=_T1, advertisement=tainted, evidence=_evidence(tainted)
        )
        return fail(name, "local claim with relationship accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.INVALID_INPUT:
            return fail(name, "local claim discipline: %s" % (exc.reason,))
    return ok(name, "conflicts deterministic; host changes explicit; peer claims scoped")


def case_37_ci_wiring() -> Result:
    name = "case_37_ci_wiring"
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        return ok(name, "pyyaml unavailable; skipped structural yaml check")
    workflow_path = os.path.join(_ROOT, ".github", "workflows", "spec-check.yml")
    if not os.path.isfile(workflow_path):
        return fail(name, "workflow file missing")
    with open(workflow_path, "r", encoding="utf-8") as handle:
        workflow = yaml.safe_load(handle)
    steps = workflow["jobs"]["specification-consistency"]["steps"]
    runs = [
        step.get("run", "") for step in steps if "run" in step
    ]
    if not any(
        "python3 tools/service_selftest.py" in run for run in runs
    ):
        return fail(name, "service selftest not wired into CI")
    if not any("python3 tools/distcore_selftest.py" in run for run in runs):
        return fail(name, "distcore step lost")
    if not any("python3 tools/spec_check.py" in run for run in runs):
        return fail(name, "spec_check step lost")
    return ok(name, "CI executes the service suite alongside all prior tools")


def case_38_decision_bound_invocation_scope() -> Result:
    """PR #26 Architect review, blocker 2: the service layer must not
    be able to take a valid ALLOW decision and manufacture a different
    authorization scope around it.  The scope may come ONLY from the
    decision's own digest-covered invocation binding."""
    name = "case_38_decision_bound_invocation_scope"
    import inspect

    registry, _executor = _full_registry()
    service_ref = _registered(registry)
    other_ref = _registered(
        registry, _advertisement(descriptor=_descriptor(name="ledger-sync"))
    )
    # Structural: apply_policy_decision accepts EXACTLY (now,
    # policy_decision) -- no scope parameters exist to supply.
    params = inspect.signature(
        registry.apply_policy_decision
    ).parameters
    if set(params) != {"now", "policy_decision"}:
        return fail(name, "apply signature carries scope params: %s" % (sorted(params),))
    # A genuine ALLOW bound to (A, sess-1, caller-N, village-a).
    decision_ref = _decision_for(
        registry, service_ref, now=_T1,
        session_id=_SESSION_ID, caller_node_id=_NODE_UE,
    )
    stored = registry._decisions[decision_ref]  # noqa: SLF001
    if (
        stored.service_ref != service_ref
        or stored.session_id != _SESSION_ID
        or stored.caller_node_id != _NODE_UE
        or stored.tenant_domain != "village-a"
    ):
        return fail(name, "stored scope does not match the decision binding")
    # The stored record restates ONLY the decision's own scope.
    if stored.policy_decision_id != hashlib.sha256(
        _bound_decision(
            evaluation_instant=_T1, service_ref=service_ref,
            session_id=_SESSION_ID, caller_node_id=_NODE_UE,
        ).canonical_bytes()
    ).hexdigest():
        return fail(name, "stored decision id drifted from the binding")
    # THE ATTACK, attempt 1: cite the decision for ANOTHER service.
    try:
        registry.admit_execution(
            now=_T2, service_ref=other_ref, decision_ref=decision_ref,
            session_id=_SESSION_ID, caller_node_id=_NODE_UE,
        )
        return fail(name, "decision re-scoped to another service")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.DECISION_SCOPE_MISMATCH:
            return fail(name, "other-service: %s" % (exc.reason,))
    # THE ATTACK, attempt 2: cite the decision for another session.
    try:
        registry.admit_execution(
            now=_T2, service_ref=service_ref, decision_ref=decision_ref,
            session_id=_OTHER_SESSION_ID, caller_node_id=_NODE_UE,
        )
        return fail(name, "decision re-scoped to another session")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.DECISION_SCOPE_MISMATCH:
            return fail(name, "other-session: %s" % (exc.reason,))
    # THE ATTACK, attempt 3: cite the decision for another caller.
    try:
        registry.admit_execution(
            now=_T2, service_ref=service_ref, decision_ref=decision_ref,
            session_id=_SESSION_ID, caller_node_id=_NODE_B,
        )
        return fail(name, "decision re-scoped to another caller")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.DECISION_SCOPE_MISMATCH:
            return fail(name, "other-caller: %s" % (exc.reason,))
    # THE ATTACK, attempt 4: re-stamp the binding extension with a
    # different service while KEEPING the valid decision id -- the
    # digest check rejects the manufactured scope outright.
    genuine = _bound_decision(
        evaluation_instant=_T1, service_ref=service_ref,
        session_id=_SESSION_ID, caller_node_id=_NODE_UE,
    )
    forged = PolicyDecision(
        decision_id=genuine.decision_id,
        effect=genuine.effect,
        code=genuine.code,
        detail=genuine.detail,
        matched_rule_ids=genuine.matched_rule_ids,
        policy_set_id=genuine.policy_set_id,
        policy_set_version=genuine.policy_set_version,
        evaluation_instant=genuine.evaluation_instant,
        conflict_trace=genuine.conflict_trace,
        extensions=(dict(genuine.extensions[0], service_ref=other_ref),),
    )
    try:
        registry.apply_policy_decision(now=_T2, policy_decision=forged)
        return fail(name, "forged binding accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.INVALID_INPUT:
            return fail(name, "forged binding: %s" % (exc.reason,))
    # The binding extension travels inside the decision's canonical
    # content (that is what makes it tamper-evident).
    blob = genuine.canonical_bytes().decode("ascii")
    if "adcos.service-invocation" not in blob or other_ref[:20] in blob:
        return fail(name, "binding not carried in canonical decision bytes")
    # A second binding on one decision is ambiguous and fails closed.
    double = PolicyDecision(
        decision_id="0" * 64,
        effect=genuine.effect,
        code=genuine.code,
        detail=genuine.detail,
        matched_rule_ids=genuine.matched_rule_ids,
        policy_set_id=genuine.policy_set_id,
        policy_set_version=genuine.policy_set_version,
        evaluation_instant=genuine.evaluation_instant,
        conflict_trace=genuine.conflict_trace,
        extensions=genuine.extensions + (genuine.extensions[0],),
    )
    real_double = PolicyDecision(
        decision_id=hashlib.sha256(double.canonical_bytes()).hexdigest(),
        effect=double.effect,
        code=double.code,
        detail=double.detail,
        matched_rule_ids=double.matched_rule_ids,
        policy_set_id=double.policy_set_id,
        policy_set_version=double.policy_set_version,
        evaluation_instant=double.evaluation_instant,
        conflict_trace=double.conflict_trace,
        extensions=double.extensions,
    )
    try:
        registry.apply_policy_decision(now=_T2, policy_decision=real_double)
        return fail(name, "double binding accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.DECISION_SCOPE_MISMATCH:
            return fail(name, "double binding: %s" % (exc.reason,))
    # The authorized scope still WORKS end-to-end for its own scope
    # (a sessionless binding for the same caller executes cleanly).
    sessionless = _decision_for(
        registry, service_ref, now=_T2, caller_node_id=_NODE_UE,
    )
    execute, _admission = _invoke(
        registry, service_ref, sessionless,
        now=_T2, caller_node_id=_NODE_UE,
    )
    if not execute.ok:
        return fail(name, "bound-scope execution failed: %s" % (execute.detail,))
    return ok(name, "invocation scope is decision-bound; rebinding fails closed")


def case_39_peer_claim_fingerprint_semantics() -> Result:
    """PR #26 Architect review, blocker 3: peer_claim_fingerprint is a
    real content-derived digest with pinned, unambiguous semantics."""
    name = "case_39_peer_claim_fingerprint_semantics"
    service_ref = derive_service_ref("weather-cache", "cache", "village-a")
    base_claim = {
        "service_ref": service_ref,
        "name": "weather-cache",
        "service_kind": "cache",
        "tenant_domain": "village-a",
        "host_node_id": _NODE_A,
        "capability_refs": ["capability.profile.service.weather-cache"],
        "service_labels": ["weather"],
        "locality_labels": ["village-a"],
        "privacy_labels": ["public"],
        "registered_at": _NOW,
        "expires_at": _FRESH,
        "endpoint_ref": "edge://slot-3",
        "policy_controlled": False,
    }
    fp = peer_claim_fingerprint(base_claim)
    # Form: a genuine sha256 content digest, not a join of fields.
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", fp):
        return fail(name, "fingerprint is not a sha256 digest: %r" % (fp[:32],))
    if "|" in fp:
        return fail(name, "fingerprint is still a joined string")
    # GOLDEN VALUE (semantics pin): the exact digest for this fixed
    # claim.  Any change to the derivation changes this pin.
    expected = "sha256:" + hashlib.sha256(
        canonical_json_bytes(dict(base_claim))
    ).hexdigest()
    if fp != expected:
        return fail(name, "fingerprint does not match the canonical digest")
    # Sensitivity: ANY field change changes the fingerprint.
    variants = []
    for mutation in (
        {"name": "weather-cache-2"},
        {"service_kind": "compute"},
        {"tenant_domain": "village-b"},
        {"host_node_id": _NODE_B},
        {"endpoint_ref": "edge://slot-4"},
        {"expires_at": "2028-01-01T00:00:00Z"},
        {"service_labels": ["weather", "telemetry"]},
        {"policy_controlled": True},
        {"capability_refs": ["capability.profile.service.other"]},
    ):
        variant = dict(base_claim)
        variant.update(mutation)
        variants.append(peer_claim_fingerprint(variant))
    if len(set(variants)) != len(variants) or fp in variants:
        return fail(name, "fingerprint is insensitive to content changes")
    # A claim with the same identity fields but different content
    # never collides with the identity-only join (the old semantics).
    if fp == peer_claim_fingerprint(
        dict(base_claim, host_node_id=_NODE_B)
    ):
        return fail(name, "fingerprint ignores non-identity fields")
    # Extra content changes the digest (whole-content coverage).
    extended = dict(base_claim)
    extended["extra_observation"] = "seen-on-relationship-1"
    if peer_claim_fingerprint(extended) == fp:
        return fail(name, "fingerprint ignores extra keys")
    # Key-order independence: same content, different mapping order.
    reordered = dict(reversed(list(base_claim.items())))
    if peer_claim_fingerprint(reordered) != fp:
        return fail(name, "fingerprint depends on key order")
    # Determinism: repeated calls are byte-identical.
    if tuple(peer_claim_fingerprint(base_claim) for _ in range(3)) != (fp, fp, fp):
        return fail(name, "fingerprint is not deterministic")
    # Fail closed: malformed claims are rejected, never digested.
    for bad in (
        {"service_ref": "not-a-service-ref", "name": "x",
         "service_kind": "cache", "tenant_domain": "village-a"},
        {"service_ref": service_ref, "name": "x",
         "service_kind": "bogus-kind", "tenant_domain": "village-a"},
        {"service_ref": service_ref, "name": "x",
         "service_kind": "cache", "tenant_domain": ""},
        {"service_ref": service_ref, "name": "shared-secret",
         "service_kind": "cache", "tenant_domain": "village-a"},
        {"service_ref": service_ref, "name": "x",
         "service_kind": "cache", "tenant_domain": "village-a",
         "latency_hint": 3.5},
        "not-a-mapping",
    ):
        try:
            peer_claim_fingerprint(bad)  # type: ignore[arg-type]
            return fail(name, "malformed claim accepted: %r" % (bad,))
        except ServiceError as exc:
            if exc.reason != ServiceReasonCode.INVALID_INPUT:
                return fail(name, "malformed claim: %s" % (exc.reason,))
    # The fingerprint of a REAL exported claim (real WORK-015
    # exposure path) is stable provenance DATA on the composition-root
    # side.
    fed_store, relationship_id, _domain = _compose_real_federation()
    registry, _executor = _full_registry(
        federation_reader=_StoreFederationReader(fed_store)
    )
    federated = _registered(
        registry, _advertisement(
            visibility=VisibilityScope.FEDERATED, endpoint="edge://slot-9",
        )
    )
    _registered(
        registry, _advertisement(
            descriptor=_descriptor(name="local-only-cache")
        )
    )
    exposure = registry.apply_federation_exposure(
        now=_T1, service_ref=federated, relationship_id=relationship_id
    )
    if not exposure.ok:
        return fail(name, "exposure failed: %s" % (exposure.detail,))
    claims = export_service_exposures(
        (registry.lookup_service(
            now=_T1, service_ref=r, tenant_domain="village-a"
        ) for r in (
            federated,
            derive_service_ref("local-only-cache", "cache", "village-a"),
        )),
        registry._exposures.values(),  # noqa: SLF001
        relationship_id=relationship_id,
    )
    if len(claims) != 1 or claims[0]["service_ref"] != federated:
        return fail(name, "export did not isolate the exposed claim")
    exported_fp = peer_claim_fingerprint(claims[0])
    if exported_fp != peer_claim_fingerprint(dict(claims[0])):
        return fail(name, "exported-claim fingerprint unstable")
    if exported_fp == fp:
        return fail(name, "exported claim collided with the fixture claim")
    return ok(name, "peer-claim fingerprint is a pinned canonical content digest")


def case_40_no_services_minting_capability() -> Result:
    """PR #26 Architect review, blocker 2 (remediation 2 -- comment
    5434924645), the REQUIRED regression: start with a GENUINE
    UNBOUND WORK-010 ALLOW (a real PolicyEngine evaluation) and prove
    there is NO exported ``services`` API capable of transforming it
    into authorization for an arbitrary scope.

    The invocation binding is born at the WORK-010 evaluator
    (``policy.invocation``): the engine derives it from the
    evaluation context's own descriptor -- mirror-checked against
    the first-class facts the rules evaluated -- and NEVER emits an
    unbound ``service.invoke`` decision (WORK-010 selftest case_73).
    This case pins the downstream half of that trust chain: the
    ``services`` package is verification + extraction ONLY."""
    name = "case_40_no_services_minting_capability"
    import services as services_module
    from policy import invocation as policy_invocation

    registry, _executor = _full_registry()
    service_ref = _registered(registry)
    attacker_ref = derive_service_ref("attacker-service", "compute", "village-a")

    # 1. The attacker's starting point: a GENUINE WORK-010 engine
    #    ALLOW (real PolicyEngine, real issuer-bearing PolicySet,
    #    digest-valid) that carries NO invocation binding -- the
    #    engine binds invocation scopes only onto service.invoke
    #    decisions, so a resource.consume ALLOW is genuinely unbound.
    unbound = _unbound_allow(_T1)
    if hashlib.sha256(unbound.canonical_bytes()).hexdigest() != unbound.decision_id:
        return fail(name, "starting ALLOW is not digest-valid")
    if any(
        ext.get("kind") == services_module.INVOCATION_BINDING_KIND
        for ext in unbound.extensions
    ):
        return fail(name, "starting ALLOW unexpectedly carries a binding")
    # 2. Extraction fails closed on it (it authorizes NO scope) ...
    try:
        services_module.extract_invocation_binding(unbound)
        return fail(name, "extraction accepted an unbound ALLOW")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.DECISION_SCOPE_MISMATCH:
            return fail(name, "unbound extraction: %s" % (exc.reason,))
    # 3. ... and the registry refuses it outright.
    try:
        registry.apply_policy_decision(now=_T1, policy_decision=unbound)
        return fail(name, "registry accepted the unbound ALLOW")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.DECISION_SCOPE_MISMATCH:
            return fail(name, "unbound apply: %s" % (exc.reason,))
    # 4. THE CAPABILITY-ABSENCE PROBE: enumerate the ENTIRE exported
    #    services API surface and try every callable with the genuine
    #    unbound ALLOW plus the attacker-selected scope.  NO call may
    #    return a PolicyDecision (a transformed/bound ALLOW).  This
    #    pins the absence of the CAPABILITY, not one blocked path,
    #    and pairs with the AST pin (case_21: no PolicyDecision
    #    construction site and no engine import anywhere in
    #    services/) -- so there is no exported OR internal minting
    #    path at all.
    surface_names = sorted(
        set(services_module.__all__)
        | {n for n in dir(services_module) if not n.startswith("_")}
    )
    if "bind_invocation_decision" in surface_names:
        return fail(name, "bind_invocation_decision is still exported")
    minting_suspects: List[str] = []
    attempted = 0
    probed = 0
    attack_kwargs = dict(
        service_ref=attacker_ref,
        session_id=_SESSION_ID,
        caller_node_id=_NODE_UE,
        tenant_domain="village-a",
        policy_decision=unbound,
        decision=unbound,
    )
    for export_name in surface_names:
        export = getattr(services_module, export_name)
        if export_name.lower().startswith("bind"):
            minting_suspects.append(
                "exported name %r looks like a binding constructor"
                % (export_name,)
            )
        if not callable(export):
            continue
        for args in ((unbound,), (unbound, attacker_ref)):
            for kwargs_set in ({}, dict(attack_kwargs)):
                attempted += 1
                try:
                    returned = export(*args, **kwargs_set)
                except Exception:  # noqa: BLE001 -- refusals are the point
                    continue
                probed += 1
                if isinstance(returned, PolicyDecision):
                    minting_suspects.append(
                        "%s(unbound_ALLOW, ...) returned a PolicyDecision"
                        % (export_name,)
                    )
    if minting_suspects:
        return fail(name, "; ".join(minting_suspects[:4]))
    if attempted < 200 or probed < 1:
        return fail(
            name,
            "capability probe was too shallow (%d attempted / %d returned)"
            % (attempted, probed),
        )
    # 5. The binding derivation lives at the policy authority and is
    #    NOT reachable through the services surface (only the
    #    discriminator constant is aliased, read-only).
    if hasattr(services_module, "invocation_binding_from_context"):
        return fail(name, "services re-exports the authority-side derivation")
    if (
        services_module.INVOCATION_BINDING_KIND
        is not policy_invocation.INVOCATION_BINDING_KIND
    ):
        return fail(name, "binding-kind constant drifted from the authority")
    # 6. The ONLY route to an authorizing decision is a REAL engine
    #    evaluation of the EXACT scope (scope-sensitive decision
    #    ids; born-bound semantics pinned by WORK-010 case_73).
    genuine = _engine_invocation_decision(
        service_ref, evaluation_instant=_T1, caller_node_id=_NODE_UE,
    )
    other_scope = _engine_invocation_decision(
        attacker_ref, evaluation_instant=_T1, caller_node_id=_NODE_UE,
    )
    if genuine.decision_id == other_scope.decision_id:
        return fail(name, "different scopes produced the same decision")
    if (
        services_module.extract_invocation_binding(other_scope).service_ref
        != attacker_ref
    ):
        return fail(name, "engine decision is not scope-faithful")
    applied = registry.apply_policy_decision(now=_T1, policy_decision=genuine)
    if not applied.ok:
        return fail(
            name, "genuine engine decision rejected: %s" % (applied.detail,)
        )
    try:
        registry.admit_execution(
            now=_T1, service_ref=service_ref, decision_ref=applied.value,
            caller_node_id=_NODE_UE,
        )
    except ServiceError as exc:
        return fail(name, "genuine scope failed to admit: %s" % (exc,))
    return ok(
        name,
        "genuine unbound ALLOW converted by NO exported services API "
        "(%d attempted / %d returned calls across the whole surface + "
        "AST pin); only engine-evaluated exact-scope decisions authorize"
        % (attempted, probed),
    )


# --------------------------------------------------------------------------
# PR #26 third Architect review regressions (findings 1-4)
# --------------------------------------------------------------------------

def case_41_monotonic_advertisement_lineage() -> Result:
    """PR #26 third Architect review, finding 1: service advertisements
    must only move FORWARD in time.  An older claim overwriting a newer
    advertisement violates deterministic replay/freshness semantics;
    equal-time different-content claims must conflict explicitly."""
    name = "case_41_monotonic_advertisement_lineage"
    registry, _executor = _full_registry()
    # The current advertisement: registered_at=_T1.
    current = _advertisement(registered_at=_T1)
    service_ref = _registered(registry, current)
    before = registry.to_canonical_bytes()
    # An OLDER different claim (registered_at=_NOW < _T1): rejected as
    # a backward-in-time replay, state unchanged.
    older = _advertisement(
        registered_at=_NOW, expires_at="2027-02-01T00:00:00Z"
    )
    try:
        registry.register_service(
            now=_T2, advertisement=older, evidence=_evidence(older, observed_at=_T2)
        )
        return fail(name, "older claim overwrote a newer advertisement")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.ADVERTISEMENT_REPLAY:
            return fail(name, "older claim: %s" % (exc.reason,))
    if registry.to_canonical_bytes() != before:
        return fail(name, "rejected older claim mutated canonical state")
    record = registry.lookup_service(
        now=_T2, service_ref=service_ref, tenant_domain="village-a"
    )
    if record.expires_at != current.expires_at:
        return fail(name, "registry kept the older claim")
    # An EQUAL-TIME different-content claim: explicit conflict (the
    # digest covers the WHOLE claim).
    equal_time = _advertisement(
        registered_at=_T1, expires_at="2027-03-01T00:00:00Z"
    )
    try:
        registry.register_service(
            now=_T2, advertisement=equal_time,
            evidence=_evidence(equal_time, observed_at=_T2),
        )
        return fail(name, "equal-time different-content claim accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.SERVICE_CONFLICT:
            return fail(name, "equal-time conflict: %s" % (exc.reason,))
    # The IDENTICAL claim replay stays repeat-safe (no state change).
    replay = registry.register_service(
        now=_T2, advertisement=current, evidence=_evidence(current, observed_at=_T2)
    )
    if not replay.ok:
        return fail(name, "identical replay rejected: %s" % (replay.detail,))
    if registry.to_canonical_bytes() != before:
        return fail(name, "identical replay mutated canonical state")
    # A STRICTLY NEWER claim updates the record (auditable).
    newer = _advertisement(
        registered_at=_T2, expires_at="2027-06-01T00:00:00Z"
    )
    updated = registry.register_service(
        now=_T2, advertisement=newer, evidence=_evidence(newer, observed_at=_T2)
    )
    if not updated.ok:
        return fail(name, "newer claim rejected: %s" % (updated.detail,))
    events = [e["event_type"] for e in registry.snapshot()["events"]]
    if events.count(ServiceEventType.SERVICE_UPDATED) != 1:
        return fail(name, "forward update not audited: %s" % (events,))
    record = registry.lookup_service(
        now=_T2, service_ref=service_ref, tenant_domain="village-a"
    )
    if record.expires_at != "2027-06-01T00:00:00Z":
        return fail(name, "forward update not applied")
    if registry.registered_count != 1:
        return fail(name, "update duplicated the record")
    # And after the forward update, backdating to _T1 is STILL a
    # replay (the lineage never moves backward).
    try:
        registry.register_service(
            now=_T3, advertisement=equal_time,
            evidence=_evidence(equal_time, observed_at=_T3),
        )
        return fail(name, "backdated claim accepted after forward update")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.ADVERTISEMENT_REPLAY:
            return fail(name, "backdate: %s" % (exc.reason,))
    return ok(name, "advertisements only move forward; equal-time conflicts explicit")


def case_42_discovery_decision_scope_binding() -> Result:
    """PR #26 third Architect review, finding 2 (the handoff-required
    negative coverage): a decision belonging to another caller/session
    must NEVER make a service eligible in a discovery performed for a
    different caller/session.  Discovery authorization is bound to the
    discovering scope with EXACT equality -- never a silent partial
    authorization."""
    name = "case_42_discovery_decision_scope_binding"
    registry, _executor = _full_registry()
    service_ref = _registered(
        registry, _advertisement(
            descriptor=_descriptor(name="scoped-billing"),
            policy_controlled=True,
        )
    )
    # A decision genuinely issued for caller X / session X1.
    decision_ref = _decision_for(
        registry, service_ref, now=_T1,
        session_id=_SESSION_ID, caller_node_id=_NODE_UE,
    )
    # Positive: the EXACT scope discovers the service.
    found = registry.discover_services(
        now=_T1, tenant_domain="village-a",
        session_id=_SESSION_ID, caller_node_id=_NODE_UE,
        decision_refs=(decision_ref,),
    )
    if service_ref not in {c.service_ref for c in found}:
        return fail(name, "exact-scope discovery hid the service")
    # NEGATIVE (the review-required case): the SAME decision used by
    # another session fails closed.
    try:
        registry.discover_services(
            now=_T1, tenant_domain="village-a",
            session_id=_OTHER_SESSION_ID, caller_node_id=_NODE_UE,
            decision_refs=(decision_ref,),
        )
        return fail(name, "another session's discovery accepted a foreign decision")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.DECISION_SCOPE_MISMATCH:
            return fail(name, "foreign session: %s" % (exc.reason,))
    # Another CALLER fails closed too.
    try:
        registry.discover_services(
            now=_T1, tenant_domain="village-a",
            session_id=_SESSION_ID, caller_node_id=_NODE_B,
            decision_refs=(decision_ref,),
        )
        return fail(name, "another caller's discovery accepted a foreign decision")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.DECISION_SCOPE_MISMATCH:
            return fail(name, "foreign caller: %s" % (exc.reason,))
    # Cross-tenant discovery with the decision fails closed as well.
    try:
        registry.discover_services(
            now=_T1, tenant_domain="village-b",
            session_id=_SESSION_ID, caller_node_id=_NODE_UE,
            decision_refs=(decision_ref,),
        )
        return fail(name, "cross-tenant discovery accepted a foreign decision")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.DECISION_SCOPE_MISMATCH:
            return fail(name, "foreign tenant: %s" % (exc.reason,))
    # An UNSCoped discovery (no caller/session stated) can never be
    # authorized by a scoped decision: empty scope != the decision's.
    try:
        registry.discover_services(
            now=_T1, tenant_domain="village-a",
            decision_refs=(decision_ref,),
        )
        return fail(name, "unscoped discovery authorized by a scoped decision")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.DECISION_SCOPE_MISMATCH:
            return fail(name, "unscoped: %s" % (exc.reason,))
    # Without supplying the decision the service is simply not
    # eligible for anyone else.
    found = registry.discover_services(
        now=_T1, tenant_domain="village-a",
        session_id=_OTHER_SESSION_ID, caller_node_id=_NODE_B,
    )
    if service_ref in {c.service_ref for c in found}:
        return fail(name, "policy-controlled service eligible without its decision")
    # An unknown decision ref fails closed (never silently skipped).
    try:
        registry.discover_services(
            now=_T1, tenant_domain="village-a",
            session_id=_SESSION_ID, caller_node_id=_NODE_UE,
            decision_refs=("services:decision:" + "0" * 32,),
        )
        return fail(name, "unknown decision ref skipped")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.DECISION_UNKNOWN:
            return fail(name, "unknown ref: %s" % (exc.reason,))
    return ok(
        name,
        "discovery authorization bound to the exact caller/session/tenant",
    )


def case_43_deny_revocation_invalidates_standing_allow() -> Result:
    """PR #26 third Architect review, finding 3: a previous ALLOW must
    not survive a subsequent policy DENY/change for the same scope.
    The decision lineage is per-scope and moves forward in applied
    time: a later DENY is recorded as an explicit revocation that
    invalidates the earlier ALLOW everywhere (lookup, discovery,
    admission) and never authorizes anything itself."""
    name = "case_43_deny_revocation_invalidates_standing_allow"
    registry, _executor = _full_registry()
    service_ref = _registered(
        registry, _advertisement(
            descriptor=_descriptor(name="revocable-service"),
            policy_controlled=True,
        )
    )
    allow_ref = _decision_for(registry, service_ref, now=_T1)
    # The ALLOW is live at _T1.
    found = registry.discover_services(
        now=_T1, tenant_domain="village-a", decision_refs=(allow_ref,)
    )
    if service_ref not in {c.service_ref for c in found}:
        return fail(name, "standing ALLOW did not authorize discovery")
    registry.lookup_service(
        now=_T1, service_ref=service_ref, tenant_domain="village-a",
        decision_ref=allow_ref,
    )
    # Policy changes to DENY at _T2 (genuine engine deny, born bound).
    deny = _engine_invocation_decision(
        service_ref, evaluation_instant=_T2, effect="deny",
    )
    revoked = registry.apply_policy_decision(now=_T2, policy_decision=deny)
    if not revoked.ok:
        return fail(name, "later DENY not applicable: %s" % (revoked.detail,))
    snapshot = registry.snapshot()
    if len(snapshot["decision_revocations"]) != 1:
        return fail(name, "deny not recorded as a revocation")
    events = [e["event_type"] for e in snapshot["events"]]
    if events.count(ServiceEventType.DECISION_REVOKED) != 1:
        return fail(name, "revocation not audited")
    # The DENY ref itself authorizes NOTHING.
    try:
        registry.lookup_service(
            now=_T2, service_ref=service_ref, tenant_domain="village-a",
            decision_ref=revoked.value,
        )
        return fail(name, "deny ref authorized lookup")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.DECISION_UNKNOWN:
            return fail(name, "deny ref lookup: %s" % (exc.reason,))
    # The earlier ALLOW is invalidated everywhere.
    try:
        registry.lookup_service(
            now=_T2, service_ref=service_ref, tenant_domain="village-a",
            decision_ref=allow_ref,
        )
        return fail(name, "revoked ALLOW survived lookup")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.REAUTHORIZATION_REQUIRED:
            return fail(name, "revoked lookup: %s" % (exc.reason,))
    try:
        registry.admit_execution(
            now=_T2, service_ref=service_ref, decision_ref=allow_ref
        )
        return fail(name, "revoked ALLOW admitted execution")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.REAUTHORIZATION_REQUIRED:
            return fail(name, "revoked admit: %s" % (exc.reason,))
    found = registry.discover_services(
        now=_T2, tenant_domain="village-a", decision_refs=(allow_ref,)
    )
    if service_ref in {c.service_ref for c in found}:
        return fail(name, "revoked ALLOW still authorized discovery")
    # Re-applying the identical deny at the same instant: DECISION_EXISTS.
    try:
        registry.apply_policy_decision(now=_T2, policy_decision=deny)
        return fail(name, "identical deny re-applied")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.DECISION_EXISTS:
            return fail(name, "deny re-apply: %s" % (exc.reason,))
    # A different deny outcome at a NON-ADVANCING instant: stale.
    other_deny = _engine_invocation_decision(
        service_ref, evaluation_instant=_T1, effect="deny",
    )
    try:
        registry.apply_policy_decision(now=_T2, policy_decision=other_deny)
        return fail(name, "non-advancing deny accepted")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.DECISION_STALE:
            return fail(name, "non-advancing deny: %s" % (exc.reason,))
    # The lineage moves forward: a LATER ALLOW re-authorizes the scope.
    reallow_ref = _decision_for(registry, service_ref, now=_T3)
    found = registry.discover_services(
        now=_T3, tenant_domain="village-a", decision_refs=(reallow_ref,)
    )
    if service_ref not in {c.service_ref for c in found}:
        return fail(name, "forward ALLOW did not re-authorize discovery")
    execute, _admission = _invoke(registry, service_ref, reallow_ref, now=_T3)
    if not execute.ok:
        return fail(name, "forward ALLOW failed to execute: %s" % (execute.detail,))
    return ok(name, "later DENY invalidates earlier ALLOW; lineage moves forward")


def case_44_explicit_cleanup_outcomes() -> Result:
    """PR #26 third Architect review, finding 4 + the close
    observation: provider cleanup failures must be represented
    explicitly -- never swallowed behind a successful operation
    result.  A deterministic cleanup-pending state machine with a
    provable retry, an explicit compensation failure for admission
    commit, and an explicit (never silent) degraded terminal closure."""
    name = "case_44_explicit_cleanup_outcomes"

    class _FlakyReleaseExecutor(ReferenceEdgeExecutor):
        """Release raises for the first N attempts, then behaves."""

        def __init__(self, fail_times: int = 1) -> None:
            super().__init__()
            self._fail_times = fail_times
            self.release_attempts = 0

        def release(self, context, *, admission_ref):
            self.release_attempts += 1
            if self.release_attempts <= self._fail_times:
                raise RuntimeError("provider partitioned during release")
            super().release(context, admission_ref=admission_ref)

    # 1. withdraw_service: registry-authoritative success with an
    #    EXPLICIT cleanup-pending outcome (never a plain success).
    registry = ServiceRegistry()
    flaky = _FlakyReleaseExecutor(fail_times=2)
    registry.register_execution_provider(flaky, label="flaky", now=_NOW)
    service_ref = _registered(registry)
    decision_ref = _decision_for(registry, service_ref, now=_T1)
    admit = registry.admit_execution(
        now=_T1, service_ref=service_ref, decision_ref=decision_ref
    )
    if not admit.ok:
        return fail(name, "admit failed: %s" % (admit.detail,))
    admission_ref = admit.value.admission_ref
    withdraw = registry.withdraw_service(
        now=_T2, service_ref=service_ref, reason="decommissioned"
    )
    if not withdraw.ok:
        return fail(name, "withdraw must succeed authoritatively")
    if withdraw.cleanup_pending != (admission_ref,):
        return fail(name, "cleanup failure not surfaced on the result")
    snapshot = registry.snapshot()
    states = {a["admission_ref"]: a["state"] for a in snapshot["admissions"]}
    if states.get(admission_ref) != AdmissionState.CLEANUP_PENDING:
        return fail(name, "admission not parked cleanup-pending: %s" % (states,))
    events = [e["event_type"] for e in snapshot["events"]]
    if events.count(ServiceEventType.ADMISSION_CLEANUP_PENDING) != 1:
        return fail(name, "cleanup-pending not audited: %s" % (events,))
    if ServiceEventType.SERVICE_WITHDRAWN not in events:
        return fail(name, "tombstone event missing")
    if not any(
        t["service_ref"] == service_ref for t in snapshot["tombstones"]
    ):
        return fail(name, "tombstone missing")
    if registry.diagnostic_state()["cleanup_pending_admissions"] != [admission_ref]:
        return fail(name, "diagnostics do not carry the pending cleanup")
    # 2. retry while the provider still fails: explicit failure, the
    #    admission STAYS cleanup-pending.
    retry = registry.retry_admission_cleanup(
        now=_T3, admission_ref=admission_ref
    )
    if retry.ok:
        return fail(name, "unproven cleanup reported proven")
    states = {
        a["admission_ref"]: a["state"] for a in registry.snapshot()["admissions"]
    }
    if states.get(admission_ref) != AdmissionState.CLEANUP_PENDING:
        return fail(name, "pending state lost on failed retry")
    # 3. retry after provider recovery PROVES the cleanup.
    retry2 = registry.retry_admission_cleanup(
        now=_T4, admission_ref=admission_ref
    )
    if not retry2.ok:
        return fail(name, "proven cleanup not accepted: %s" % (retry2.detail,))
    states = {
        a["admission_ref"]: a["state"] for a in registry.snapshot()["admissions"]
    }
    if states.get(admission_ref) != AdmissionState.SUPERSEDED:
        return fail(name, "proven cleanup did not supersede")
    # 4. retrying a non-pending admission is an explicit state error.
    try:
        registry.retry_admission_cleanup(now=_T5, admission_ref=admission_ref)
        return fail(name, "non-pending cleanup retried")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.ADMISSION_STATE:
            return fail(name, "non-pending retry: %s" % (exc.reason,))
    # 5. relocate_service surfaces cleanup the same way, and the
    #    placement transition is still recorded.
    registry2 = ServiceRegistry()
    flaky2 = _FlakyReleaseExecutor(fail_times=1)
    registry2.register_execution_provider(flaky2, label="flaky2", now=_NOW)
    service_ref2 = _registered(registry2)
    decision_ref2 = _decision_for(registry2, service_ref2, now=_T1)
    admit2 = registry2.admit_execution(
        now=_T1, service_ref=service_ref2, decision_ref=decision_ref2
    )
    if not admit2.ok:
        return fail(name, "relocate-leg admit failed")
    relocated = registry2.relocate_service(
        now=_T2, service_ref=service_ref2, target_host_node_id=_NODE_B
    )
    if not relocated.ok:
        return fail(name, "relocate must succeed authoritatively")
    if relocated.cleanup_pending != (admit2.value.admission_ref,):
        return fail(name, "relocate cleanup failure not surfaced")
    if registry2.lookup_service(
        now=_T3, service_ref=service_ref2, tenant_domain="village-a"
    ).host_node_id != _NODE_B:
        return fail(name, "relocation not applied")
    retry3 = registry2.retry_admission_cleanup(
        now=_T3, admission_ref=admit2.value.admission_ref
    )
    if not retry3.ok:
        return fail(name, "relocate cleanup retry failed: %s" % (retry3.detail,))
    # 6. admission-commit compensation failure is EXPLICIT: a typed
    #    error naming the dangling provider admission + a ledger.
    class _FailingCommitRegistry(ServiceRegistry):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.commit_failed = False

        def _commit_admission(self, admission, sandbox, *, now):
            self.commit_failed = True
            raise RuntimeError("commit fault")

    broken = _FailingCommitRegistry()
    broken.register_execution_provider(
        _FlakyReleaseExecutor(fail_times=99), label="broken", now=_NOW
    )
    broken_ref = _registered(broken)
    broken_decision = _decision_for(broken, broken_ref, now=_T1)
    compensation_text = ""
    try:
        broken.admit_execution(
            now=_T1, service_ref=broken_ref, decision_ref=broken_decision
        )
        return fail(name, "compensation failure not surfaced")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.ILLEGAL_STATE:
            return fail(name, "compensation: %s" % (exc.reason,))
        compensation_text = str(exc)
    dangling = broken.diagnostic_state()["dangling_provider_admissions"]
    if not dangling or not any(
        d["admission_ref"] in compensation_text for d in dangling
    ):
        return fail(name, "dangling provider admission vanished: %s" % (dangling,))
    if any(
        a["service_ref"] == broken_ref for a in broken.snapshot()["admissions"]
    ):
        return fail(name, "failed admit committed registry state")
    # 7. close() is explicit: terminal closure with a provider that
    #    still holds an active admission raises, naming the provider.
    registry4 = ServiceRegistry()
    executor4 = ReferenceEdgeExecutor()
    registry4.register_execution_provider(executor4, label="busy", now=_NOW)
    service_ref4 = _registered(registry4)
    decision_ref4 = _decision_for(registry4, service_ref4, now=_T1)
    admit4 = registry4.admit_execution(
        now=_T1, service_ref=service_ref4, decision_ref=decision_ref4
    )
    if not admit4.ok:
        return fail(name, "close-leg admit failed")
    try:
        registry4.close(now=_T2)
        return fail(name, "silent terminal closure with an active provider")
    except ServiceError as exc:
        if exc.reason != ServiceReasonCode.ILLEGAL_STATE:
            return fail(name, "degraded close: %s" % (exc.reason,))
        if "busy" not in str(exc):
            return fail(name, "degraded close does not name the provider")
    if not registry4.closed:
        return fail(name, "closure must still be terminal")
    if executor4.health() != "HEALTHY":
        return fail(name, "provider fact lost after degraded closure")
    # A clean registry closes quietly with the REAL injected instant.
    clean_registry, _clean_executor = _full_registry()
    try:
        clean_registry.close(now=_T5)
    except ServiceError as exc:
        return fail(name, "clean close raised: %s" % (exc,))
    if not clean_registry.closed:
        return fail(name, "clean close did not close")
    return ok(
        name,
        "cleanup-pending state machine + provable retry + explicit "
        "compensation and terminal closure",
    )


# --------------------------------------------------------------------------
# Real-authority composition helpers
# --------------------------------------------------------------------------

def _compose_real_session(variant: str = "5"):
    """Compose a REAL WORK-012 ESTABLISHED session driven by a REAL
    routing decision over a REAL topology graph (the WORK-022/023/024
    composition recipe); returns (store, session_id, decision,
    selected_path)."""
    from resources import ResourceStore
    from routing import RoutingContext, RoutingEngine
    from routing.model import LinkMetrics
    from sessions import SessionState, SessionStore
    from topology import (
        ClaimType,
        SourceClass,
        TopologyClaim,
        TopologyGraph,
        make_link_subject,
    )

    node_a = "adcos:node:test.profile.v1:" + variant * 64
    node_b = _NODE_A
    decision = _allow_decision()
    graph = TopologyGraph()
    graph.merge(
        TopologyClaim(
            subject=make_link_subject(node_a, node_b), reporter=node_a,
            claim_type=ClaimType.LINK_STATE, value="up",
            source_class=SourceClass.SELF_ADVERTISEMENT,
            issued_at=_NOW, freshness_until=_FRESH, sequence=1,
        )
    )
    graph.merge(
        TopologyClaim(
            subject=node_b, reporter=node_a,
            claim_type=ClaimType.REACHABLE, value="true",
            source_class=SourceClass.DIRECT_OBSERVATION,
            issued_at=_NOW, freshness_until=_FRESH, sequence=1,
        )
    )
    evaluation = RoutingEngine().evaluate(
        RoutingContext(
            source_node_id=node_a, destination_node_id=node_b,
            topology=graph, resources=ResourceStore(),
            evaluation_instant=_NOW, policy_decision=decision,
            link_metrics={
                make_link_subject(node_a, node_b): LinkMetrics(
                    latency_ms=5, loss_basis_points=0, capacity_bps=10 ** 6,
                    energy_cost_millijoules=10,
                    confidence_basis_points=10_000, observed_at=_NOW,
                    freshness_until=_FRESH,
                )
            },
        )
    )
    if evaluation.decision is None or evaluation.decision.selected is None:
        raise AssertionError("routing composition failed")
    store = SessionStore()
    created = store.create(
        evaluation.decision, decision,
        source_node_id=node_a, destination_node_id=node_b,
        creation_instant=_NOW,
    )
    if not created.ok:
        raise AssertionError("session creation failed")
    sid = created.session.session_id
    store.transition(sid, SessionState.AUTHORIZED, event_instant=_NOW)
    store.transition(sid, SessionState.ESTABLISHED, event_instant=_NOW)
    return store, sid, decision, evaluation.decision.selected


def _compose_real_federation():
    """A REAL WORK-015 FederationStore with two ACTIVE domains, an
    ESTABLISHED relationship declaring the service scopes, and an
    ACTIVE service.discover grant; returns (store, relationship_id,
    domain_a_id)."""
    from federation import FederationStore, Scope
    from federation.model import RelationshipState

    store = FederationStore()
    key_a = "11" * 32
    key_b = "22" * 32
    result_a = store.create_domain(
        "operator-alpha", key_a, operator_node_id=_NODE_A,
        created_at="2026-06-01T00:00:00Z",
    )
    result_b = store.create_domain(
        "operator-beta", key_b, operator_node_id=_NODE_B,
        created_at="2026-06-01T00:00:00Z",
    )
    assert result_a.ok and result_b.ok, (result_a.detail, result_b.detail)
    store.transition_domain(
        result_a.domain.domain_id, "active", event_instant="2026-06-02T00:00:00Z"
    )
    store.transition_domain(
        result_b.domain.domain_id, "active", event_instant="2026-06-02T00:00:00Z"
    )
    relationship = store.establish_relationship(
        result_a.domain.domain_id,
        result_b.domain.domain_id,
        peer_identity_reference=result_b.domain.operator_node_id,
        declared_scopes=(Scope.SERVICE_DISCOVER, Scope.SERVICE_INVOKE),
        valid_from="2026-06-01T00:00:00Z",
        valid_until="2027-06-01T00:00:00Z",
        event_instant="2026-06-01T00:00:00Z",
    )
    assert relationship.ok, relationship.detail
    relationship_id = relationship.relationship.relationship_id
    if relationship.relationship.state != RelationshipState.ESTABLISHED:
        raise AssertionError("relationship not established")
    grant = store.publish_grant(
        relationship_id, Scope.SERVICE_DISCOVER,
        valid_from="2026-06-01T00:00:00Z",
        valid_until="2027-06-01T00:00:00Z",
        event_instant="2026-06-01T00:00:00Z",
    )
    assert grant.ok, grant.detail
    return store, relationship_id, result_a.domain.domain_id


# --------------------------------------------------------------------------
# Source helpers
# --------------------------------------------------------------------------

def _read_source(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _strip_prose(source: str) -> str:
    tree = ast.parse(source)
    chunks = [source]
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            body = getattr(node, "body", None)
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                chunks.append(body[0].value.value)
    stripped = chunks[0]
    for doc in chunks[1:]:
        stripped = stripped.replace(doc, "")
    lines = [
        line for line in stripped.splitlines()
        if not line.lstrip().startswith("#")
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------

def main() -> int:
    cases = [
        case_01_family_surface_frozen,
        case_02_service_identity_distinct,
        case_03_registration_deterministic_repeat_safe,
        case_04_advertisement_validity_provenance,
        case_05_lookup_state_matrix,
        case_06_discovery_capability_intent_aware_no_routes,
        case_07_local_first_upstream_absent,
        case_08_local_execution_seam,
        case_09_unauthorized_execution_before_provider_effects,
        case_10_execution_failures_isolated_typed,
        case_11_capacity_work008_data,
        case_12_capacity_exhaustion_state_unchanged,
        case_13_placement_host_change_identity_stable,
        case_14_placement_transition_recorded,
        case_15_session_identity_stable_across_relocation,
        case_16_federation_scoped_visibility,
        case_17_federation_removal_preserves_local,
        case_18_tenant_isolation,
        case_19_secrets_never_in_records,
        case_20_least_authority_context,
        case_21_no_second_authority_ast,
        case_22_validate_commit_sequence_discipline,
        case_23_canonical_state_clean,
        case_24_determinism,
        case_25_frozen_spec_intact,
        case_26_py_compile_clean,
        case_27_policy_negative_matrix,
        case_28_policy_change_between_discovery_execution,
        case_29_tombstone_replay_protection,
        case_30_real_authority_composition,
        case_31_observation_honesty,
        case_32_no_core_leakage,
        case_33_unavailable_at_execution,
        case_34_budget_isolation,
        case_35_vocabulary_cross_checks,
        case_36_registration_conflict_and_host_guard,
        case_37_ci_wiring,
        case_38_decision_bound_invocation_scope,
        case_39_peer_claim_fingerprint_semantics,
        case_40_no_services_minting_capability,
        case_41_monotonic_advertisement_lineage,
        case_42_discovery_decision_scope_binding,
        case_43_deny_revocation_invalidates_standing_allow,
        case_44_explicit_cleanup_outcomes,
    ]
    print("ADCOS service registry / edge compute self-test (WORK-025)")
    print("=" * 72)
    failures = 0
    for case in cases:
        try:
            case_name, passed, detail = case()
        except Exception as exc:  # noqa: BLE001
            case_name, passed, detail = (
                case.__name__, False,
                "case raised %s: %s" % (type(exc).__name__, exc),
            )
        if not passed:
            failures += 1
        print("[%s] %-56s %s" % ("ok  " if passed else "FAIL", case_name, detail))
    print("-" * 72)
    if failures:
        print("Result: FAIL (%d/%d cases)" % (len(cases) - failures, len(cases)))
        return 1
    print("Result: PASS (%d/%d cases)" % (len(cases), len(cases)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
