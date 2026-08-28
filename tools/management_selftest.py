#!/usr/bin/env python3
"""ADCOS management API self-test (WORK-030).

The focused API-security / audit / RBAC battery for the
``management`` family, mapping the WORK-030 work-item contract to
discriminating cases:

- frozen vocabularies present; operation specs structurally
  classified; spec policy operations cross-checked
  byte-for-byte against the WORK-010 authority      -> case_01
- role catalog validation (unknown capability; duplicate
  role; NodeID-shaped role = identity conflation)    -> case_02
- RBAC deny-by-default temporal matrix (no assignment;
  expired; not-yet-valid; revoked; re-grant; duplicate
  grant; revoking inactive)                          -> case_03
- roles are additive (union of capabilities)         -> case_04
- RBAC store closure-owned state (no instance
  attribute holds the ledger; closure cells immutable
  data only; exact public surface; attribute
  shadowing never rewrites history)                  -> case_05
- EVERY API call audited, allowed or denied; outcome
  vocabulary distinguishes denial causes            -> case_06
- audit tamper matrix (field mutation; deletion;
  reordering; forged append -> head change)          -> case_07
- audit chain discipline (monotonic 1..N sequence;
  prev linkage; head moves on append; fail-closed
  append validation)                                 -> case_08
- audit records carry no secrets                     -> case_09
- audit ledger closure-owned state (no mutation or
  removal API exists; frozen records)                -> case_10
- TWO-KEY authorization matrix (RBAC-only denied;
  policy-only denied; both keys -> executed)         -> case_11
- cross-set policy aggregation: explicit DENY in ANY
  live set blocks; a SILENT set does not veto another
  set's explicit ALLOW                               -> case_12
- no applicable policy set -> POLICY_DENIED
  (deny-by-default over the store)                   -> case_13
- PROVENANCE: no API method accepts a caller-supplied
  PolicyDecision/RouteDecision (structural signature
  scan); the executed decision is the one evaluated
  inside the call                                    -> case_14
- session.create runs the FULL genuine chain (policy
  -> routing -> session authority); the created
  session exists in the session authority            -> case_15
- authority verdicts are never overridden (no route;
  illegal transition; unknown session ->
  AUTHORITY_REJECTED, audited, state unchanged)      -> case_16
- session modify (transition + suspend) and terminate
  happy paths under explicit policy                  -> case_17
- federation join full flow (policy-gated
  establishment; relationship ESTABLISHED)           -> case_18
- federation control denials (RBAC-only; policy-only;
  unknown relationship)                              -> case_19
- federation accept-peer (scope NARROWING enforced by
  the authority; widening -> AUTHORITY_REJECTED)     -> case_20
- federation resource-export (grant published;
  scope escalation -> AUTHORITY_REJECTED)            -> case_21
- federation resource-import (recorded through the
  authority; ungranted import -> AUTHORITY_REJECTED,
  nothing mutated)                                   -> case_22
- telemetry query privacy fence stays with the
  WORK-026 authority (restricted needs purpose;
  above-scope invisible)                             -> case_23
- telemetry promotion: born-bound happy path;
  mismatched subject/unrecorded observation/privacy
  violation -> AUTHORITY_REJECTED                    -> case_24
- management.role-assign two-key matrix + authority
  validation (unknown role)                          -> case_25
- RBAC changes take effect on the NEXT call (a
  revoked capability denies immediately)             -> case_26
- import discipline: management consumes ONLY the five
  declared dependency families + shared protocol
  primitives + stdlib                                -> case_27
- no vendor/access symbols (LOCK-001/002/003)        -> case_28
- nothing imports management (reverse-import
  discipline)                                        -> case_29
- the API surface is EXACTLY the 15 frozen operation
  methods (no unlisted entry point)                  -> case_30
- DETERMINISM: composed scenario identical across
  hash seeds (0/1/7919)                              -> case_31
- frozen spec/ byte-identical to origin/main; docs/
  additions limited to the WORK-030 handoff; .github
  delta = the new CI step                            -> case_32
- py_compile clean                                   -> case_33
- CI wiring (this battery + every prior battery)     -> case_34
- serialization round-trips; tampered DATA fails
  closed                                             -> case_35
- NO-BYPASS structural proof: management never writes
  into an authority object and never touches another
  authority's private members (AST scan)             -> case_36
- API constructor requires GENUINE injected
  authorities (duck-typed fakes rejected however
  complete)                                          -> case_37
- OUTER FAILURE BOUNDARY: hostile/failing
  injected authorities (snapshot methods,
  RoutingEngine.evaluate, SessionStore create/
  terminate, federation lookup, the RBAC gate,
  denial-detail formation, telemetry query,
  policy snapshot) each leave ONE-AND-ONLY-ONE
  ``management.failed`` audit record -- never
  an unaudited exception, never a success,
  never a double audit; expected policy-
  material errors stay audited denials
                                                     -> case_38
- forged constructor-injected initial RBAC
  event ids (content/id mismatch) fail closed
  at the authoritative construction boundary;
  genuine content-derived initial events
  install cleanly                                   -> case_39

Run: python3 tools/management_selftest.py   (exit 0 = PASS)
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import os
import py_compile
import re
import subprocess
import sys
from dataclasses import FrozenInstanceError
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Tuple

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from federation.model import RelationshipState, Scope  # noqa: E402
from federation.store import FederationStore  # noqa: E402
from policy.model import (  # noqa: E402
    Effect,
    Operation,
    PolicyDomain,
    PolicyError,
    PolicyRule,
    PolicySet,
    Privileged,
)
from policy.store import PolicyStore  # noqa: E402
from resources.model import ResourceStore  # noqa: E402
from routing.engine import RoutingEngine  # noqa: E402
from sessions.store import SessionStore  # noqa: E402
from telemetry.model import (  # noqa: E402
    PrivacyClass,
    SourceDisclosure,
    TelemetryObservation,
    TelemetrySourceClass,
    TelemetrySubjectKind,
    derive_observation_id,
)
from telemetry.store import TelemetryStore  # noqa: E402
from topology.model import (  # noqa: E402
    ClaimType,
    SourceClass,
    TopologyClaim,
    TopologyGraph,
    make_link_subject,
)

from management import (  # noqa: E402
    AuditLedger,
    AuditOutcome,
    AuditRecord,
    ManagementAPI,
    ManagementCapability,
    ManagementError,
    ManagementOperation,
    ManagementReasonCode,
    ManagementResult,
    OPERATION_SPECS,
    PRIVILEGED_OPERATIONS,
    READ_OPERATIONS,
    RoleAssignmentEvent,
    RoleAssignmentStore,
    RoleDefinition,
    RoleEventKind,
    audit_record_from_mapping,
    audit_record_to_mapping,
    derive_audit_record_id,
    derive_role_event_id,
    role_event_from_mapping,
    role_event_to_mapping,
)

Result = Tuple[str, bool, str]


def ok(name: str, detail: str = "") -> Result:
    return (name, True, detail)


def fail(name: str, detail: str) -> Result:
    return (name, False, detail)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

_NODE_A = "adcos:node:test.profile.v1:" + "a" * 64
_NODE_B = "adcos:node:test.profile.v1:" + "b" * 64
_OPERATOR = "adcos:node:test.profile.v1:" + "c" * 64  # network operator
_SECURITY = "adcos:node:test.profile.v1:" + "d" * 64  # security admin
_NOBODY = "adcos:node:test.profile.v1:" + "e" * 64  # no roles at all
_ISSUER = "adcos:node:test.profile.v1:" + "f" * 64

_T0 = "2026-01-01T00:00:00Z"
_T1 = "2026-12-31T23:59:59Z"
_NOW = "2026-06-01T12:00:00Z"
_LATER = "2026-06-02T12:00:00Z"

_AB = (_NODE_A, _NODE_B)

_ROLE_OPERATOR = RoleDefinition(
    role_id="network-operator",
    capabilities=(
        ManagementCapability.SESSION_READ,
        ManagementCapability.SESSION_CONTROL,
        ManagementCapability.FEDERATION_READ,
        ManagementCapability.FEDERATION_CONTROL,
        ManagementCapability.TELEMETRY_READ,
        ManagementCapability.TELEMETRY_PROMOTE,
        ManagementCapability.POLICY_READ,
        ManagementCapability.AUDIT_READ,
        ManagementCapability.ROLES_READ,
        ManagementCapability.ROLES_ADMINISTER,
    ),
    description="full operational role (test fixture)",
)
_ROLE_OBSERVER = RoleDefinition(
    role_id="observer",
    capabilities=(ManagementCapability.SESSION_READ,),
)
_ROLE_AUDITOR = RoleDefinition(
    role_id="auditor",
    capabilities=(ManagementCapability.AUDIT_READ,),
)

_CATALOG = (_ROLE_OPERATOR, _ROLE_OBSERVER, _ROLE_AUDITOR)


def _rule(
    rule_id: str,
    effect: str,
    operation: str,
    subjects: Tuple[str, ...] = (),
) -> PolicyRule:
    return PolicyRule(
        rule_id=rule_id,
        domain=PolicyDomain.IDENTITY,
        effect=effect,
        operation=operation,
        subjects=subjects,
        priority=0,
        specificity=0,
        version=1,
    )


def _management_policy_set() -> PolicySet:
    """The standard test policy set: allows every privileged
    management operation for the OPERATOR subject and role-assign for
    SECURITY."""
    rules = [
        _rule("allow-sc", Effect.ALLOW, Operation.SESSION_CREATE, (_OPERATOR,)),
        _rule("allow-sm", Effect.ALLOW, Operation.SESSION_MODIFY, (_OPERATOR,)),
        _rule("allow-st", Effect.ALLOW, Operation.SESSION_TERMINATE, (_OPERATOR,)),
        _rule("allow-fj", Effect.ALLOW, Operation.FEDERATION_JOIN, (_OPERATOR,)),
        _rule("allow-fa", Effect.ALLOW, Operation.FEDERATION_ACCEPT_PEER, (_OPERATOR,)),
        _rule("allow-fe", Effect.ALLOW, Operation.FEDERATION_RESOURCE_EXPORT, (_OPERATOR,)),
        _rule("allow-fi", Effect.ALLOW, Operation.FEDERATION_RESOURCE_IMPORT, (_OPERATOR,)),
        _rule("allow-tp", Effect.ALLOW, Operation.TELEMETRY_TOPOLOGY_PROMOTE, (_OPERATOR,)),
        _rule("allow-ra", Effect.ALLOW, Operation.MANAGEMENT_ROLE_ASSIGN, (_SECURITY,)),
    ]
    return PolicySet(
        set_id="mgmt-policy",
        version=1,
        rules=tuple(rules),
        issuer_node_id=_ISSUER,
    )


def _policy_store(sets: List[PolicySet]) -> PolicyStore:
    store = PolicyStore()
    for ps in sets:
        store.publish(ps)
    return store


def _role_store() -> RoleAssignmentStore:
    store = RoleAssignmentStore(roles=_CATALOG)
    store.grant(_OPERATOR, "network-operator", instant=_T0, actor_node_id=_ISSUER)
    store.grant(_SECURITY, "auditor", instant=_T0, actor_node_id=_ISSUER)
    return store


def _api(
    policy_sets: Optional[List[PolicySet]] = None,
    role_store: Optional[RoleAssignmentStore] = None,
    session_store: Optional[SessionStore] = None,
    federation_store: Optional[FederationStore] = None,
    telemetry_store: Optional[TelemetryStore] = None,
    audit: Optional[AuditLedger] = None,
    routing_engine: Optional[RoutingEngine] = None,
) -> ManagementAPI:
    return ManagementAPI(
        policy_store=_policy_store(
            policy_sets if policy_sets is not None else [_management_policy_set()]
        ),
        session_store=session_store if session_store is not None else SessionStore(),
        federation_store=(
            federation_store if federation_store is not None else FederationStore()
        ),
        telemetry_store=(
            telemetry_store if telemetry_store is not None else TelemetryStore()
        ),
        role_store=role_store if role_store is not None else _role_store(),
        audit=audit if audit is not None else AuditLedger(),
        routing_engine=routing_engine,
    )


def _graph() -> TopologyGraph:
    g = TopologyGraph()
    g.merge(
        TopologyClaim(
            subject=make_link_subject(_NODE_A, _NODE_B),
            reporter=_NODE_A,
            claim_type=ClaimType.LINK_STATE,
            value="up",
            source_class=SourceClass.SELF_ADVERTISEMENT,
            issued_at=_T0,
            freshness_until=_T1,
            sequence=1,
            provenance="",
        )
    )
    g.merge(
        TopologyClaim(
            subject=_NODE_B,
            reporter=_NODE_A,
            claim_type=ClaimType.REACHABLE,
            value="true",
            source_class=SourceClass.DIRECT_OBSERVATION,
            issued_at=_T0,
            freshness_until=_T1,
            sequence=1,
            provenance="",
        )
    )
    return g


def _metrics() -> Dict[str, LinkMetrics]:
    return {
        make_link_subject(*_AB): LinkMetrics(
            latency_ms=10,
            loss_basis_points=0,
            capacity_bps=1_000_000,
            energy_cost_millijoules=100,
            confidence_basis_points=10_000,
            observed_at=_T0,
            freshness_until=_T1,
        )
    }


def _create_session(
    api: ManagementAPI, now: str = _NOW, operator: str = _OPERATOR
) -> ManagementResult:
    return api.create_session(
        operator,
        now=now,
        source_node_id=_NODE_A,
        destination_node_id=_NODE_B,
        topology=_graph(),
        resources=ResourceStore(),
        link_metrics=_metrics(),
    )


def _federation_domains() -> Tuple[FederationStore, str, str]:
    """A store with two ACTIVE registered domains; returns
    (store, local_domain_id of A, peer_domain_id of B) -- the accepted
    federation-battery fixture shape (domains selected by their
    registered operator identity, never by sorted-index accident)."""
    store = FederationStore()
    ra = store.create_domain(
        "operator-alpha", "11" * 32, operator_node_id=_NODE_A, created_at=_T0
    )
    rb = store.create_domain(
        "operator-beta", "22" * 32, operator_node_id=_NODE_B, created_at=_T0
    )
    assert ra.ok and rb.ok
    assert ra.domain is not None and rb.domain is not None
    store.transition_domain(ra.domain.domain_id, "active", event_instant=_T0)
    store.transition_domain(rb.domain.domain_id, "active", event_instant=_T0)
    return store, ra.domain.domain_id, rb.domain.domain_id


def _federation_store_with_domains() -> FederationStore:
    store, _local, _peer = _federation_domains()
    return store


def _recorded_observation(
    telemetry: TelemetryStore,
    *,
    privacy_class: str = PrivacyClass.OPERATIONAL,
    sequence: int = 1,
) -> TelemetryObservation:
    probe = TelemetryObservation(
        observation_id="",
        subject_kind=TelemetrySubjectKind.LINK,
        subject_ref=make_link_subject(*_AB),
        source_node_id=_NODE_A,
        source_class=TelemetrySourceClass.SELF_ADVERTISED,
        metric="link-up",
        value=sequence,
        confidence_basis_points=10_000,
        observed_at=_NOW,
        freshness_until=_T1,
        privacy_class=privacy_class,
        sequence=sequence,
        evidence_refs=(),
        provenance="",
    )
    observation = TelemetryObservation(
        observation_id=derive_observation_id(
            probe.subject_kind,
            probe.subject_ref,
            probe.source_node_id,
            probe.source_class,
            probe.metric,
            probe.value,
            probe.confidence_basis_points,
            probe.observed_at,
            probe.freshness_until,
            probe.sequence,
            privacy_class=privacy_class,
        ),
        subject_kind=probe.subject_kind,
        subject_ref=probe.subject_ref,
        source_node_id=probe.source_node_id,
        source_class=probe.source_class,
        metric=probe.metric,
        value=probe.value,
        confidence_basis_points=probe.confidence_basis_points,
        observed_at=probe.observed_at,
        freshness_until=probe.freshness_until,
        privacy_class=probe.privacy_class,
        sequence=probe.sequence,
        evidence_refs=probe.evidence_refs,
        provenance=probe.provenance,
    )
    telemetry.record_observation(observation, now=_NOW)
    return observation


from routing.model import LinkMetrics  # noqa: E402


# --------------------------------------------------------------------------
# 1-5: vocabularies and the RBAC authority
# --------------------------------------------------------------------------


def case_01_frozen_vocabularies() -> Result:
    name = "case_01_frozen_vocabularies"
    if len(ManagementCapability.values()) != 10:
        return fail(name, "capability vocabulary size changed")
    if len(ManagementOperation.values()) != 15:
        return fail(name, "operation vocabulary size changed")
    if len(PRIVILEGED_OPERATIONS) != 9 or len(READ_OPERATIONS) != 6:
        return fail(
            name,
            "structural classification wrong: %d privileged / %d reads"
            % (len(PRIVILEGED_OPERATIONS), len(READ_OPERATIONS)),
        )
    # Spec table integrity: every spec's policy operation must be a
    # genuine frozen WORK-010 operation, byte-for-byte.
    for spec in OPERATION_SPECS.values():
        if spec.capability not in ManagementCapability.values():
            return fail(name, "spec %s grants unknown capability" % spec.operation)
        if spec.privileged:
            if spec.policy_operation not in Operation.values():
                return fail(
                    name,
                    "spec %s references unknown policy operation %r"
                    % (spec.operation, spec.policy_operation),
                )
            if not Privileged.is_privileged(spec.policy_operation):
                return fail(
                    name,
                    "spec %s policy operation %r not privileged in WORK-010"
                    % (spec.operation, spec.policy_operation),
                )
        elif spec.policy_operation != "":
            return fail(name, "read spec %s carries a policy operation" % spec.operation)
    # The management.role-assign extension is present and privileged.
    if Operation.MANAGEMENT_ROLE_ASSIGN not in Operation.values():
        return fail(name, "management.role-assign missing from WORK-010 vocabulary")
    if not Privileged.is_privileged(Operation.MANAGEMENT_ROLE_ASSIGN):
        return fail(name, "management.role-assign must be privileged")
    if len(AuditOutcome.values()) != 6:
        return fail(name, "audit outcome vocabulary size changed")
    return ok(name, "vocabularies frozen; specs structurally classified")


def case_02_role_catalog_validation() -> Result:
    name = "case_02_role_catalog_validation"
    try:
        RoleDefinition(role_id="bad", capabilities=("no.such.capability",))
        return fail(name, "unknown capability accepted")
    except ManagementError:
        pass
    try:
        RoleDefinition(
            role_id="adcos:node:test.profile.v1:" + "a" * 64,
            capabilities=(ManagementCapability.SESSION_READ,),
        )
        return fail(name, "NodeID-shaped role id accepted (role != identity)")
    except ManagementError:
        pass
    try:
        RoleDefinition(role_id="Role", capabilities=(ManagementCapability.SESSION_READ,))
        return fail(name, "non-lowercase role id accepted")
    except ManagementError:
        pass
    try:
        RoleDefinition(
            role_id="dup",
            capabilities=(
                ManagementCapability.SESSION_READ,
                ManagementCapability.SESSION_READ,
            ),
        )
        return fail(name, "duplicate capability accepted")
    except ManagementError:
        pass
    try:
        RoleAssignmentStore(
            roles=(
                RoleDefinition(role_id="x", capabilities=(ManagementCapability.SESSION_READ,)),
                RoleDefinition(role_id="x", capabilities=(ManagementCapability.AUDIT_READ,)),
            )
        )
        return fail(name, "duplicate role id in catalog accepted")
    except ManagementError:
        pass
    # unknown role in initial events fails closed
    bad_event = RoleAssignmentEvent(
        event_id="0" * 64,
        kind=RoleEventKind.GRANT,
        operator_node_id=_OPERATOR,
        role_id="nonexistent-role",
        instant=_T0,
        actor_node_id=_ISSUER,
    )
    try:
        RoleAssignmentStore(roles=_CATALOG, initial_events=(bad_event,))
        return fail(name, "initial event with unknown role accepted")
    except ManagementError:
        pass
    return ok(name, "role catalog validation fail-closed in all directions")


def case_03_rbac_temporal_matrix() -> Result:
    name = "case_03_rbac_temporal_matrix"
    store = RoleAssignmentStore(roles=_CATALOG)
    # deny-by-default: never granted
    if store.active_capabilities(_NOBODY, now=_NOW):
        return fail(name, "never-granted operator holds capabilities")
    # valid window grant
    store.grant(
        _NOBODY, "observer", instant=_T0, actor_node_id=_ISSUER,
        valid_from=_T0, valid_until=_T1,
    )
    if ManagementCapability.SESSION_READ not in store.active_capabilities(_NOBODY, now=_NOW):
        return fail(name, "in-window grant inactive")
    # expired
    if store.active_capabilities(_NOBODY, now="2027-06-01T00:00:00Z"):
        return fail(name, "expired grant still active")
    # not-yet-valid
    store2 = RoleAssignmentStore(roles=_CATALOG)
    store2.grant(
        _NOBODY, "observer", instant=_T0, actor_node_id=_ISSUER,
        valid_from="2027-01-01T00:00:00Z", valid_until="2027-12-31T00:00:00Z",
    )
    if store2.active_capabilities(_NOBODY, now=_NOW):
        return fail(name, "future grant active")
    # revoke takes effect only from the revoke instant
    store.revoke(_NOBODY, "observer", instant=_LATER, actor_node_id=_ISSUER)
    if not store.active_capabilities(_NOBODY, now=_NOW):
        return fail(name, "revoke applied retroactively (before its instant)")
    if store.active_capabilities(_NOBODY, now="2026-06-03T00:00:00Z"):
        return fail(name, "revoked grant still active after revoke")
    # duplicate grant fails closed
    store3 = RoleAssignmentStore(roles=_CATALOG)
    store3.grant(_NOBODY, "observer", instant=_T0, actor_node_id=_ISSUER)
    try:
        store3.grant(_NOBODY, "observer", instant=_LATER, actor_node_id=_ISSUER)
        return fail(name, "duplicate grant accepted")
    except ManagementError:
        pass
    # revoking an inactive assignment fails closed
    store3.revoke(_NOBODY, "observer", instant=_LATER, actor_node_id=_ISSUER)
    try:
        store3.revoke(_NOBODY, "observer", instant="2026-06-04T00:00:00Z", actor_node_id=_ISSUER)
        return fail(name, "double revoke accepted")
    except ManagementError:
        pass
    # re-grant after revoke reactivates
    store3.grant(_NOBODY, "observer", instant="2026-06-05T00:00:00Z", actor_node_id=_ISSUER)
    if (
        ManagementCapability.SESSION_READ
        not in store3.active_capabilities(_NOBODY, now="2026-06-06T00:00:00Z")
    ):
        return fail(name, "re-grant after revoke inactive")
    return ok(name, "temporal fold correct in every direction")


def case_04_roles_additive() -> Result:
    name = "case_04_roles_additive"
    store = RoleAssignmentStore(roles=_CATALOG)
    store.grant(_NOBODY, "observer", instant=_T0, actor_node_id=_ISSUER)
    caps1 = set(store.active_capabilities(_NOBODY, now=_NOW))
    if caps1 != {ManagementCapability.SESSION_READ}:
        return fail(name, "observer caps wrong: %s" % sorted(caps1))
    store.grant(_NOBODY, "auditor", instant=_T0, actor_node_id=_ISSUER)
    caps2 = set(store.active_capabilities(_NOBODY, now=_NOW))
    if caps2 != {
        ManagementCapability.SESSION_READ,
        ManagementCapability.AUDIT_READ,
    }:
        return fail(name, "additive union wrong: %s" % sorted(caps2))
    return ok(name, "roles additive (union of capabilities)")


def case_05_rbac_closure_owned() -> Result:
    name = "case_05_rbac_closure_owned"
    store = RoleAssignmentStore(roles=_CATALOG)
    store.grant(_OPERATOR, "network-operator", instant=_T0, actor_node_id=_ISSUER)
    # No instance attribute holds the history (closure-owned): the
    # public surface is callables only, never a mutable collection.
    for key, value in vars(store).items():
        if isinstance(value, (list, dict, set)):
            return fail(name, "mutable instance attribute %r on the RBAC store" % key)
        if not callable(value):
            return fail(name, "non-callable public instance attribute %r" % key)
    if store.public_surface() != (
        "active_capabilities", "active_roles", "catalog_roles",
        "events", "grant", "revoke", "snapshot",
    ):
        return fail(name, "RBAC public surface changed: %s" % (store.public_surface(),))
    # Closure cells of the public callables contain only immutable data.
    for attr in store.public_surface():
        closure = getattr(getattr(store, attr), "__closure__", None) or ()
        for cell in closure:
            content = cell.cell_contents
            if callable(content):
                return fail(name, "callable found in %r closure cells" % attr)
            if isinstance(content, (list, dict, set)):
                return fail(name, "mutable collection in %r closure cells" % attr)
    # Attribute shadowing can never rewrite history: shadowing the
    # events accessor leaves every OTHER closure-backed reader and the
    # genuine state untouched.
    store.events = None  # type: ignore[assignment]
    if "network-operator" not in store.active_roles(_OPERATOR, now=_NOW):
        return fail(name, "attribute shadowing broke capability resolution")
    if ManagementCapability.SESSION_CONTROL not in store.active_capabilities(
        _OPERATOR, now=_NOW
    ):
        return fail(name, "attribute shadowing broke capability resolution (caps)")
    return ok(name, "RBAC state closure-owned; no mutable surface; shadowing inert")


# --------------------------------------------------------------------------
# 6-10: the audit authority
# --------------------------------------------------------------------------


def case_06_every_call_audited() -> Result:
    name = "case_06_every_call_audited"
    api = _api()
    ledger = api._audit
    before = len(ledger.records())
    # a denial (RBAC)
    r1 = api.create_session(
        _NOBODY, now=_NOW, source_node_id=_NODE_A, destination_node_id=_NODE_B,
        topology=_graph(), resources=ResourceStore(), link_metrics={},
    )
    # a denial (policy: capability held, no rule for _NOBODY)
    api._role_store.grant(_NOBODY, "network-operator", instant=_NOW, actor_node_id=_ISSUER)
    r2 = api.create_session(
        _NOBODY, now=_NOW, source_node_id=_NODE_A, destination_node_id=_NODE_B,
        topology=_graph(), resources=ResourceStore(), link_metrics={},
    )
    # an execution
    r3 = _create_session(api)
    # a read
    r4 = api.inspect_sessions(_OPERATOR, now=_NOW)
    records = ledger.records()
    if len(records) != before + 4:
        return fail(name, "expected 4 new audit records, got %d" % (len(records) - before))
    outcomes = [r.outcome for r in records[before:]]
    if outcomes != [
        AuditOutcome.DENIED_RBAC,
        AuditOutcome.DENIED_POLICY,
        AuditOutcome.EXECUTED,
        AuditOutcome.EXECUTED,
    ]:
        return fail(name, "outcome sequence wrong: %s" % outcomes)
    ids = {r.record_id for r in records}
    for r in (r1, r2, r3, r4):
        if not r.audit_record_id or r.audit_record_id not in ids:
            return fail(name, "result references a missing audit record")
    if r1.code != ManagementReasonCode.RBAC_DENIED or r1.ok:
        return fail(name, "RBAC denial code wrong")
    if r2.code != ManagementReasonCode.POLICY_DENIED or r2.ok:
        return fail(name, "policy denial code wrong")
    if not (r3.ok and r4.ok):
        return fail(name, "execution results not ok")
    return ok(name, "every call audited with the right outcome")


def case_07_audit_tamper_matrix() -> Result:
    name = "case_07_audit_tamper_matrix"
    api = _api()
    _create_session(api)
    api.inspect_sessions(_OPERATOR, now=_NOW)
    ledger = api._audit
    records = ledger.records()
    if len(records) < 2:
        return fail(name, "fixture produced too few records")
    wire = [audit_record_to_mapping(r) for r in records]


    def _record_for(data: Dict[str, Any]) -> AuditRecord:
        return AuditRecord(
            record_id=data["record_id"],
            sequence=data["sequence"],
            recorded_instant=data["recorded_instant"],
            operation=data["operation"],
            operator_node_id=data["operator_node_id"],
            outcome=data["outcome"],
            detail=data["detail"],
            evidence_refs=tuple(data["evidence_refs"]),
            prev_digest=data["prev_digest"],
        )

    def _verify_with(mutated: List[Dict[str, Any]]) -> Tuple[bool, int]:
        prev = ""
        for index, data in enumerate(mutated):
            if data["sequence"] != index + 1:
                return False, index + 1
            if data["prev_digest"] != prev:
                return False, index + 1
            if derive_audit_record_id(prev, _record_for(data)) != data["record_id"]:
                return False, index + 1
            prev = data["record_id"]
        return True, 0

    base_ok, _ = _verify_with(wire)
    if not base_ok:
        return fail(name, "baseline chain fails verification (fixture broken)")
    # (a) field mutation of the first record
    mutated = [dict(w) for w in wire]
    mutated[0]["detail"] = mutated[0]["detail"] + " tampered"
    ok_a, break_a = _verify_with(mutated)
    if ok_a:
        return fail(name, "field mutation undetected")
    # (b) deletion of the first record
    mutated = [dict(w) for w in wire]
    del mutated[0]
    ok_b, break_b = _verify_with(mutated)
    if ok_b:
        return fail(name, "deletion undetected")
    # (c) reordering
    mutated = [dict(w) for w in wire]
    mutated[0], mutated[-1] = mutated[-1], mutated[0]
    ok_c, _ = _verify_with(mutated)
    if ok_c:
        return fail(name, "reordering undetected")
    # (d) forged append with a recomputed id: internally consistent,
    # but it CHANGES THE HEAD (detectable against any pinned head).
    forged = {
        "sequence": len(wire) + 1,
        "recorded_instant": _NOW,
        "operation": ManagementOperation.SESSION_CREATE,
        "operator_node_id": _OPERATOR,
        "outcome": AuditOutcome.EXECUTED,
        "detail": "forged record",
        "evidence_refs": [],
        "prev_digest": wire[-1]["record_id"],
    }
    forged["record_id"] = derive_audit_record_id(
        forged["prev_digest"], _record_for({**forged, "record_id": "0" * 64})
    )
    ok_d, _ = _verify_with(wire + [forged])
    if not ok_d:
        return fail(name, "internally-consistent forged append fails its own chain")
    if forged["record_id"] == wire[-1]["record_id"]:
        return fail(name, "forged append did not change the head")
    # (e) the genuine ledger still verifies
    if not ledger.verify_chain().ok:
        return fail(name, "genuine ledger no longer verifies")
    return ok(
        name,
        "tamper matrix: mutation@%d deletion@%d reorder detected; forged append moves the head"
        % (break_a, break_b),
    )


def case_08_audit_chain_discipline() -> Result:
    name = "case_08_audit_chain_discipline"
    ledger = AuditLedger()
    if ledger.chain_head() != "":
        return fail(name, "empty ledger head is not empty string")
    empty = ledger.verify_chain()
    if not empty.ok or empty.checked != 0:
        return fail(name, "empty ledger verification wrong")
    heads = []
    for i in range(5):
        ledger.append(
            recorded_instant="2026-06-01T00:00:0%dZ" % i,
            operation=ManagementOperation.SESSION_CREATE,
            operator_node_id=_OPERATOR,
            outcome=AuditOutcome.EXECUTED,
            detail="record %d" % i,
            evidence_refs=("ref-%d" % i,),
        )
        heads.append(ledger.chain_head())
    records = ledger.records()
    if [r.sequence for r in records] != [1, 2, 3, 4, 5]:
        return fail(name, "sequence not monotonic 1..N")
    if records[0].prev_digest != "":
        return fail(name, "first record prev_digest not empty")
    for i in range(1, 5):
        if records[i].prev_digest != records[i - 1].record_id:
            return fail(name, "prev linkage broken at %d" % i)
    if len(set(heads)) != len(heads):
        return fail(name, "chain head did not move on every append")
    verification = ledger.verify_chain()
    if not verification.ok or verification.checked != 5:
        return fail(name, "genuine chain verification failed")
    # append validates the vocabularies fail-closed
    try:
        ledger.append(
            recorded_instant=_NOW,
            operation="not.an.operation",
            operator_node_id=_OPERATOR,
            outcome=AuditOutcome.EXECUTED,
            detail="x",
        )
        return fail(name, "invalid operation accepted by the ledger")
    except ManagementError:
        pass
    try:
        ledger.append(
            recorded_instant=_NOW,
            operation=ManagementOperation.SESSION_CREATE,
            operator_node_id=_OPERATOR,
            outcome="not-an-outcome",
            detail="x",
        )
        return fail(name, "invalid outcome accepted by the ledger")
    except ManagementError:
        pass
    return ok(name, "chain discipline: monotonic, linked, moving head, fail-closed append")


def case_09_audit_no_secrets() -> Result:
    name = "case_09_audit_no_secrets"
    api = _api()
    _create_session(api)
    api.terminate_session(_OPERATOR, now=_LATER, session_id="sha256:" + "0" * 64)
    api.query_telemetry(_OPERATOR, now=_NOW, privacy_scope=PrivacyClass.OPERATIONAL)
    for record in api._audit.records():
        blob = json.dumps(record.content_dict(), sort_keys=True)
        for token in ("private", "secret", "credential", "password", "pubkey", "key="):
            if token in blob.lower():
                return fail(name, "audit record carries secret-like text: %r" % token)
    return ok(name, "audit records carry diagnostics only, no secret-like text")


def case_10_audit_closure_owned() -> Result:
    name = "case_10_audit_closure_owned"
    ledger = AuditLedger()
    ledger.append(
        recorded_instant=_NOW,
        operation=ManagementOperation.AUDIT_VERIFY,
        operator_node_id=_OPERATOR,
        outcome=AuditOutcome.EXECUTED,
        detail="probe",
    )
    surface = ledger.public_surface()
    if surface != ("append", "chain_head", "records", "snapshot", "verify_chain"):
        return fail(name, "ledger public surface is not the frozen five: %s" % (surface,))
    for mutation in ("clear", "remove", "delete", "pop", "rewrite", "mutate", "truncate"):
        if any(mutation in s for s in surface):
            return fail(name, "mutation-like API %r on the ledger" % mutation)
    for key, value in vars(ledger).items():
        if isinstance(value, (list, dict, set)):
            return fail(name, "mutable instance attribute %r on the ledger" % key)
        if not callable(value):
            return fail(name, "non-callable public attribute %r on the ledger" % key)
    # records are immutable dataclasses
    record = ledger.records()[0]
    try:
        record.detail = "tampered"  # type: ignore[misc]
        return fail(name, "audit record is mutable")
    except FrozenInstanceError:
        pass
    # shadowing an accessor cannot rewrite history: verification
    # still runs over the genuine closure state.
    ledger.records = lambda: ()  # noqa: B010 -- deliberate attribute shadowing probe
    verification = ledger.verify_chain()
    if not verification.ok or verification.checked != 1:
        return fail(name, "attribute shadowing broke verification")
    return ok(name, "ledger immutable: no mutation API; frozen records; closure-owned")


# --------------------------------------------------------------------------
# 11-17: the policy gate and session control
# --------------------------------------------------------------------------


def case_11_two_key_matrix() -> Result:
    name = "case_11_two_key_matrix"
    # key A only (RBAC capability, no policy rule for the subject)
    api = _api()
    api._role_store.grant(_NOBODY, "network-operator", instant=_T0, actor_node_id=_ISSUER)
    r = api.create_session(
        _NOBODY, now=_NOW, source_node_id=_NODE_A, destination_node_id=_NODE_B,
        topology=_graph(), resources=ResourceStore(), link_metrics={},
    )
    if r.ok or r.code != ManagementReasonCode.POLICY_DENIED:
        return fail(name, "capability without policy allowed: %r" % r.code)
    # key B only (policy rule for the subject, no capability)
    empty_store = RoleAssignmentStore(roles=_CATALOG)  # no grants
    api2 = _api(role_store=empty_store)
    r2 = api2.create_session(
        _OPERATOR, now=_NOW, source_node_id=_NODE_A, destination_node_id=_NODE_B,
        topology=_graph(), resources=ResourceStore(), link_metrics={},
    )
    if r2.ok or r2.code != ManagementReasonCode.RBAC_DENIED:
        return fail(name, "policy without capability allowed: %r" % r2.code)
    # both keys -> executed
    r3 = _create_session(api)
    if not r3.ok or r3.code != ManagementReasonCode.EXECUTED:
        return fail(name, "both keys did not execute: %r %s" % (r3.code, r3.detail))
    # reads: capability only (no policy gate for non-privileged reads)
    r4 = api2.inspect_sessions(_OPERATOR, now=_NOW)
    if r4.ok or r4.code != ManagementReasonCode.RBAC_DENIED:
        return fail(name, "read without capability allowed")
    # capability granularity: auditor (audit.read only) cannot read sessions
    api3 = _api()
    r5 = api3.inspect_sessions(_SECURITY, now=_NOW)
    if r5.ok or r5.code != ManagementReasonCode.RBAC_DENIED:
        return fail(name, "session.read granted via auditor role (capability leak)")
    r6 = api3.verify_audit(_SECURITY, now=_NOW)
    if not r6.ok:
        return fail(name, "auditor cannot verify the audit chain")
    return ok(name, "two-key matrix + read-capability granularity")


def case_12_cross_set_aggregation() -> Result:
    name = "case_12_cross_set_aggregation"
    allow_set = _management_policy_set()
    # silent set: a second live set with NO rule for session.create
    silent_set = PolicySet(
        set_id="silent-set",
        version=1,
        rules=(_rule("other", Effect.ALLOW, Operation.RESOURCE_RESERVE, (_OPERATOR,)),),
        issuer_node_id=_ISSUER,
    )
    api = _api(policy_sets=[allow_set, silent_set])
    r = _create_session(api)
    if not r.ok:
        return fail(name, "silent set vetoed another set's explicit allow: %s" % r.detail)
    # explicit deny in ANY live set blocks
    deny_set = PolicySet(
        set_id="deny-set",
        version=1,
        rules=(_rule("deny-sc", Effect.DENY, Operation.SESSION_CREATE, (_OPERATOR,)),),
        issuer_node_id=_ISSUER,
    )
    api2 = _api(policy_sets=[allow_set, deny_set])
    r2 = api2.create_session(
        _OPERATOR, now=_NOW, source_node_id=_NODE_A, destination_node_id=_NODE_B,
        topology=_graph(), resources=ResourceStore(), link_metrics={},
    )
    if r2.ok or r2.code != ManagementReasonCode.POLICY_DENIED:
        return fail(name, "explicit deny in a second live set did not block")
    return ok(name, "aggregation: silent set neutral; explicit deny in any live set blocks")


def case_13_no_applicable_set_denies() -> Result:
    name = "case_13_no_applicable_set_denies"
    expired = PolicySet(
        set_id="expired",
        version=1,
        rules=(_rule("allow-sc", Effect.ALLOW, Operation.SESSION_CREATE, (_OPERATOR,)),),
        issuer_node_id=_ISSUER,
        valid_from=_T0,
        valid_until="2026-01-15T00:00:00Z",
    )
    api = _api(policy_sets=[expired])
    r = api.create_session(
        _OPERATOR, now=_NOW, source_node_id=_NODE_A, destination_node_id=_NODE_B,
        topology=_graph(), resources=ResourceStore(), link_metrics={},
    )
    if r.ok or r.code != ManagementReasonCode.POLICY_DENIED:
        return fail(name, "expired-only policy allowed a privileged op: %r" % r.code)
    if "no applicable policy set" not in r.detail:
        return fail(name, "denial detail not explainable: %s" % r.detail)
    return ok(name, "no applicable set -> deny-by-default with explainable detail")


def case_14_no_decision_injection_surface() -> Result:
    name = "case_14_no_decision_injection_surface"
    api = _api()
    # Structural: no public method accepts authority-minted objects.
    forbidden_annotations = (
        "PolicyDecision", "RouteDecision", "PolicySet", "Session",
        "FederationRelationship", "TopologyPromotion", "TelemetryObservation",
    )
    for method_name, method in inspect.getmembers(api, predicate=inspect.ismethod):
        if method_name.startswith("_"):
            continue
        signature = inspect.signature(method)
        for param in signature.parameters.values():
            annotation = str(param.annotation)
            for token in forbidden_annotations:
                if token in annotation:
                    return fail(
                        name,
                        "public method %s accepts authority-minted type %s"
                        % (method_name, token),
                    )
    # Behavioral: the executed decision is the one the engine
    # evaluated inside the call (evidence decision id == a genuine
    # engine evaluation of the same context against the live set).
    r = _create_session(api)
    if not r.ok:
        return fail(name, "fixture session creation failed: %s" % r.detail)
    decision_id = r.evidence_refs[0]
    live = api._policy_store.list_applicable(_NOW)
    if not live:
        return fail(name, "no live policy set in fixture")
    from policy.model import PolicyContext

    context = PolicyContext(
        operation=Operation.SESSION_CREATE,
        requester_node_id=_OPERATOR,
        evaluation_instant=_NOW,
    )
    result = api._engine.evaluate(live[0], context)
    if result.decision is None or result.decision.decision_id != decision_id:
        return fail(name, "executed decision is not the engine's own evaluation")
    return ok(name, "no injection surface; executed decision is the in-call evaluation")


def case_15_session_full_chain() -> Result:
    name = "case_15_session_full_chain"
    api = _api()
    r = _create_session(api)
    if not r.ok:
        return fail(name, "session creation failed: %s" % r.detail)
    session = r.payload
    # the session exists in the SESSION AUTHORITY's own state
    if api._session_store.get(session.session_id) is None:
        return fail(name, "created session missing from the session authority")
    # evidence: policy decision id + session id
    if len(r.evidence_refs) < 2 or not r.evidence_refs[1].startswith("sha256:"):
        return fail(name, "evidence refs incomplete: %s" % (r.evidence_refs,))
    # idempotent replay through the API
    r2 = _create_session(api)
    if not r2.ok or r2.payload.session_id != session.session_id:
        return fail(name, "idempotent re-creation diverged")
    return ok(name, "policy -> routing -> session chain; idempotent replay")


def case_16_authority_verdicts_never_overridden() -> Result:
    name = "case_16_authority_verdicts_never_overridden"
    api = _api()
    # routing authority: no route (empty topology -> no candidates)
    r = api.create_session(
        _OPERATOR, now=_NOW, source_node_id=_NODE_A, destination_node_id=_NODE_B,
        topology=TopologyGraph(), resources=ResourceStore(), link_metrics={},
    )
    if r.ok or r.code != ManagementReasonCode.AUTHORITY_REJECTED:
        return fail(name, "routing rejection not surfaced: %r %s" % (r.code, r.detail))
    # session authority: unknown session
    r2 = api.terminate_session(_OPERATOR, now=_NOW, session_id="sha256:" + "0" * 64)
    if r2.ok or r2.code != ManagementReasonCode.AUTHORITY_REJECTED:
        return fail(name, "unknown-session terminate not authority-rejected")
    # session authority: illegal transition (REQUESTED -> ESTABLISHED
    # is not in the frozen table; only REQUESTED -> AUTHORIZED/FAILED)
    _create_session(api)
    sessions = api._session_store.snapshot()["sessions"]
    session_id = sessions[0]["session_id"]
    r3 = api.modify_session(_OPERATOR, now=_NOW, session_id=session_id, transition="ESTABLISHED")
    if r3.ok or r3.code != ManagementReasonCode.AUTHORITY_REJECTED:
        return fail(name, "illegal transition not authority-rejected: %r" % r3.code)
    # no state was mutated by the rejected calls
    if len(api._session_store) != 1:
        return fail(name, "rejected calls mutated session authority state")
    fetched = api._session_store.get(session_id)
    assert fetched is not None
    if fetched.state != "REQUESTED":
        return fail(name, "rejected transition mutated the session state")
    return ok(name, "authority verdicts surfaced, never overridden; state unchanged")


def case_17_session_lifecycle_happy_path() -> Result:
    name = "case_17_session_lifecycle_happy_path"
    api = _api()
    r = _create_session(api)
    session_id = r.payload.session_id
    # transition REQUESTED -> AUTHORIZED -> ESTABLISHED via the API
    r2 = api.modify_session(_OPERATOR, now=_NOW, session_id=session_id, transition="AUTHORIZED")
    if not r2.ok:
        return fail(name, "transition failed: %s" % r2.detail)
    r2b = api.modify_session(_OPERATOR, now=_NOW, session_id=session_id, transition="ESTABLISHED")
    if not r2b.ok:
        return fail(name, "establish transition failed: %s" % r2b.detail)
    # suspend via the API (SUSPENDED only through the explicit op)
    r3 = api.modify_session(
        _OPERATOR, now=_NOW, session_id=session_id, suspend=True, reason_code="maintenance"
    )
    if not r3.ok:
        return fail(name, "suspend failed: %s" % r3.detail)
    fetched = api._session_store.get(session_id)
    assert fetched is not None
    if fetched.state != "SUSPENDED":
        return fail(name, "suspend did not reach SUSPENDED")
    # terminate via the API
    r4 = api.terminate_session(_OPERATOR, now=_LATER, session_id=session_id)
    if not r4.ok:
        return fail(name, "terminate failed: %s" % r4.detail)
    # ambiguous action rejected before touching the authority
    r5 = api.modify_session(
        _OPERATOR, now=_LATER, session_id=session_id, transition="FAILED", suspend=True
    )
    if r5.ok or r5.code != ManagementReasonCode.INVALID_INPUT:
        return fail(name, "ambiguous modify action accepted")
    return ok(name, "transition/suspend/terminate flow through the authority")


# --------------------------------------------------------------------------
# 18-22: federation control
# --------------------------------------------------------------------------


def case_18_federation_join_flow() -> Result:
    name = "case_18_federation_join_flow"
    federation, local_id, peer_id = _federation_domains()
    api = _api(federation_store=federation)
    r = api.join_federation(
        _OPERATOR,
        now=_NOW,
        local_domain_id=local_id,
        peer_domain_id=peer_id,
        peer_identity_reference=_NODE_B,
        declared_scopes=(Scope.ROUTE_IMPORT,),
        valid_from=_T0,
        valid_until=_T1,
        resource_exposure_refs=("resource:backhaul-1",),
    )
    if not r.ok:
        return fail(name, "join failed: %r %s" % (r.code, r.detail))
    relationship = r.payload.relationship
    assert relationship is not None
    if relationship.state != RelationshipState.ESTABLISHED:
        return fail(name, "relationship not ESTABLISHED: %r" % relationship.state)
    if relationship.resource_exposure_refs != ("resource:backhaul-1",):
        return fail(name, "exposure refs not recorded by the authority")
    return ok(name, "federation.join: policy-gated establishment recorded by the authority")


def case_19_federation_control_denials() -> Result:
    name = "case_19_federation_control_denials"
    federation, local_id, peer_id = _federation_domains()
    api = _api(federation_store=federation)
    # RBAC-only denial (auditor role has no federation.control)
    r = api.join_federation(
        _SECURITY, now=_NOW, local_domain_id=local_id, peer_domain_id=peer_id,
        peer_identity_reference=_NODE_B, declared_scopes=(Scope.ROUTE_IMPORT,),
        valid_from=_T0, valid_until=_T1,
    )
    if r.ok or r.code != ManagementReasonCode.RBAC_DENIED:
        return fail(name, "RBAC-only join allowed: %r" % r.code)
    # policy-only denial (capability held, no rule for the subject)
    no_policy = _api(
        federation_store=federation,
        role_store=RoleAssignmentStore(roles=_CATALOG),  # no grants
    )
    no_policy._role_store.grant(_SECURITY, "network-operator", instant=_T0, actor_node_id=_ISSUER)
    r2 = no_policy.join_federation(
        _SECURITY, now=_NOW, local_domain_id=local_id, peer_domain_id=peer_id,
        peer_identity_reference=_NODE_B, declared_scopes=(Scope.ROUTE_IMPORT,),
        valid_from=_T0, valid_until=_T1,
    )
    if r2.ok or r2.code != ManagementReasonCode.POLICY_DENIED:
        return fail(name, "policy-only join allowed: %r" % r2.code)
    # unknown relationship on accept
    r3 = api.accept_federation_peer(_OPERATOR, now=_NOW, relationship_id="fed:relationship:unknown")
    if r3.ok or r3.code != ManagementReasonCode.INVALID_INPUT:
        return fail(name, "unknown relationship accepted: %r" % r3.code)
    # nothing was established
    if federation.get_relationships():
        return fail(name, "denied joins created relationships")
    return ok(name, "federation denials: RBAC / policy / unknown-relationship")


def case_20_federation_accept_peer() -> Result:
    name = "case_20_federation_accept_peer"
    federation, local_id, peer_id = _federation_domains()
    proposal = federation.propose_relationship(
        local_id, peer_id,
        peer_identity_reference=_NODE_B,
        declared_scopes=(Scope.ROUTE_IMPORT,),
        valid_from=_T0, valid_until=_T1, event_instant=_NOW,
    )
    if not proposal.ok or proposal.relationship is None:
        return fail(name, "fixture proposal failed: %s" % proposal.detail)
    rid = proposal.relationship.relationship_id
    api = _api(federation_store=federation)
    # WIDENING acceptance (scope outside the proposed envelope): the
    # AUTHORITY rejects -- the accepting side can never widen.
    r = api.accept_federation_peer(
        _OPERATOR, now=_NOW, relationship_id=rid,
        scopes=(Scope.ROUTE_IMPORT, Scope.CAPABILITY_READ),
    )
    if r.ok or r.code != ManagementReasonCode.AUTHORITY_REJECTED:
        return fail(name, "widening acceptance allowed: %r" % r.code)
    current = federation.get_relationship(rid)
    assert current is not None
    if current.state != RelationshipState.PROPOSED:
        return fail(name, "rejected acceptance mutated the relationship")
    # narrowing acceptance via the API succeeds
    r2 = api.accept_federation_peer(_OPERATOR, now=_LATER, relationship_id=rid, scopes=())
    if not r2.ok:
        return fail(name, "narrowing accept failed: %s" % r2.detail)
    current = federation.get_relationship(rid)
    assert current is not None
    if current.state != RelationshipState.ESTABLISHED:
        return fail(name, "accept did not establish")
    return ok(name, "accept-peer: widening authority-rejected; narrowing works")


def case_21_federation_export() -> Result:
    name = "case_21_federation_export"
    federation, local_id, peer_id = _federation_domains()
    established = federation.establish_relationship(
        local_id, peer_id,
        peer_identity_reference=_NODE_B,
        declared_scopes=(Scope.ROUTE_IMPORT,),
        valid_from=_T0, valid_until=_T1, event_instant=_NOW,
    )
    if not established.ok or established.relationship is None:
        return fail(name, "fixture establish failed: %s" % established.detail)
    rid = established.relationship.relationship_id
    api = _api(federation_store=federation)
    # in-envelope grant via the API
    r = api.export_federation_resource(
        _OPERATOR, now=_NOW, relationship_id=rid, scope=Scope.ROUTE_IMPORT,
        valid_from=_NOW, valid_until=_T1,
    )
    if not r.ok:
        return fail(name, "export failed: %s" % r.detail)
    if not federation.get_grants(rid):
        return fail(name, "grant not recorded by the authority")
    # scope escalation (outside the declared envelope) -> AUTHORITY rejects
    r2 = api.export_federation_resource(
        _OPERATOR, now=_LATER, relationship_id=rid, scope=Scope.CAPABILITY_READ,
        valid_from=_LATER, valid_until=_T1,
    )
    if r2.ok or r2.code != ManagementReasonCode.AUTHORITY_REJECTED:
        return fail(name, "scope escalation not authority-rejected: %r" % r2.code)
    if len(federation.get_grants(rid)) != 1:
        return fail(name, "rejected export mutated grant state")
    return ok(name, "export: in-envelope grant recorded; escalation authority-rejected")


def case_22_federation_import() -> Result:
    name = "case_22_federation_import"
    from federation.exchange import ExchangeKind, FederationExchange

    federation, local_id, peer_id = _federation_domains()
    established = federation.establish_relationship(
        local_id, peer_id,
        peer_identity_reference=_NODE_B,
        declared_scopes=(Scope.ROUTE_IMPORT,),
        valid_from=_T0, valid_until=_T1, event_instant=_NOW,
    )
    if not established.ok or established.relationship is None:
        return fail(name, "fixture establish failed: %s" % established.detail)
    rid = established.relationship.relationship_id
    api = _api(federation_store=federation)

    def _exchange(sequence: int) -> FederationExchange:
        return FederationExchange(
            exchange_id="",
            exchange_kind=ExchangeKind.ROUTE_EXPORT,
            local_domain_id=peer_id,
            peer_domain_id=local_id,
            sequence=sequence,
            declared_at=_NOW,
            effective_at=_NOW,
            peer_identity_reference=_NODE_B,
            route_refs=("path:r1",),
        )

    # no grant yet: the authority rejects (slot NOT consumed) and
    # nothing is recorded
    r = api.import_federation_resource(_OPERATOR, now=_NOW, relationship_id=rid, exchange=_exchange(2))
    if r.ok or r.code != ManagementReasonCode.AUTHORITY_REJECTED:
        return fail(name, "ungranted import not authority-rejected: %r" % r.code)
    current = federation.get_relationship(rid)
    assert current is not None
    if current.route_import_refs:
        return fail(name, "denied import mutated refs")
    # grant the scope (the authority's own discipline surface; it
    # consumes event slot 2), then the import records through the API
    federation.publish_grant(rid, Scope.ROUTE_IMPORT, valid_from=_NOW, valid_until=_T1, event_instant=_NOW)
    r2 = api.import_federation_resource(_OPERATOR, now=_LATER, relationship_id=rid, exchange=_exchange(3))
    if not r2.ok:
        return fail(name, "granted import failed: %s" % r2.detail)
    current = federation.get_relationship(rid)
    assert current is not None
    if current.route_import_refs != ("path:r1",):
        return fail(name, "import refs not recorded by the authority")
    return ok(name, "import: ungranted rejected without mutation; granted recorded")


# --------------------------------------------------------------------------
# 23-24: telemetry
# --------------------------------------------------------------------------


def case_23_telemetry_query_privacy_fence() -> Result:
    name = "case_23_telemetry_query_privacy_fence"
    telemetry = TelemetryStore()
    _recorded_observation(telemetry, privacy_class=PrivacyClass.RESTRICTED)
    api = _api(telemetry_store=telemetry)
    # restricted scope requires purpose (the authority's rule surfaces)
    r = api.query_telemetry(_OPERATOR, now=_NOW, privacy_scope=PrivacyClass.RESTRICTED)
    if r.ok or r.code != ManagementReasonCode.INVALID_INPUT:
        return fail(name, "restricted query without purpose allowed")
    # above-scope observations are INVISIBLE under the operational
    # scope (filtered, never errored -- no existence probing)
    r2 = api.query_telemetry(_OPERATOR, now=_NOW, privacy_scope=PrivacyClass.OPERATIONAL)
    if not r2.ok:
        return fail(name, "operational query failed: %s" % r2.detail)
    if len(r2.payload) != 0:
        return fail(name, "restricted observation leaked under operational scope")
    # with purpose, restricted scope sees it
    r3 = api.query_telemetry(
        _OPERATOR, now=_NOW, privacy_scope=PrivacyClass.RESTRICTED,
        purpose="security-investigation",
    )
    if not r3.ok or len(r3.payload) != 1:
        return fail(name, "restricted-with-purpose query wrong: %r" % len(r3.payload))
    # no capability -> RBAC denial (no existence probing either)
    r4 = api.query_telemetry(_NOBODY, now=_NOW, privacy_scope=PrivacyClass.OPERATIONAL)
    if r4.ok or r4.code != ManagementReasonCode.RBAC_DENIED:
        return fail(name, "telemetry read without capability allowed")
    return ok(name, "privacy fence intact: scope required, purpose enforced, above-scope invisible")


def case_24_telemetry_promotion() -> Result:
    name = "case_24_telemetry_promotion"
    telemetry = TelemetryStore()
    observation = _recorded_observation(telemetry)
    api = _api(telemetry_store=telemetry)
    # born-bound happy path
    r = api.promote_telemetry_observation(
        _OPERATOR, now=_NOW, observation_id=observation.observation_id,
        subject_kind=TelemetrySubjectKind.LINK, subject_ref=observation.subject_ref,
        privacy_scope=PrivacyClass.OPERATIONAL,
        source_disclosure=SourceDisclosure.PSEUDONYMOUS,
    )
    if not r.ok:
        return fail(name, "promotion failed: %s" % r.detail)
    # mismatched subject ref: the binding must equal the RECORDED observation
    r2 = api.promote_telemetry_observation(
        _OPERATOR, now=_NOW, observation_id=observation.observation_id,
        subject_kind=TelemetrySubjectKind.LINK, subject_ref="link:some:other",
        privacy_scope=PrivacyClass.OPERATIONAL,
        source_disclosure=SourceDisclosure.PSEUDONYMOUS,
    )
    if r2.ok or r2.code != ManagementReasonCode.AUTHORITY_REJECTED:
        return fail(name, "mismatched-scope promotion allowed: %r" % r2.code)
    # unrecorded observation
    r3 = api.promote_telemetry_observation(
        _OPERATOR, now=_NOW, observation_id="telemetry:observation:" + "0" * 64,
        subject_kind=TelemetrySubjectKind.LINK, subject_ref=observation.subject_ref,
        privacy_scope=PrivacyClass.OPERATIONAL,
        source_disclosure=SourceDisclosure.PSEUDONYMOUS,
    )
    if r3.ok or r3.code != ManagementReasonCode.AUTHORITY_REJECTED:
        return fail(name, "unrecorded-observation promotion allowed")
    # privacy violation: observation class above the authorized scope
    restricted = _recorded_observation(telemetry, privacy_class=PrivacyClass.RESTRICTED, sequence=2)
    r4 = api.promote_telemetry_observation(
        _OPERATOR, now=_NOW, observation_id=restricted.observation_id,
        subject_kind=TelemetrySubjectKind.LINK, subject_ref=restricted.subject_ref,
        privacy_scope=PrivacyClass.OPERATIONAL,
        source_disclosure=SourceDisclosure.PSEUDONYMOUS,
    )
    if r4.ok or r4.code != ManagementReasonCode.AUTHORITY_REJECTED:
        return fail(name, "privacy-violating promotion allowed: %r" % r4.code)
    # RBAC-only denial
    r5 = api.promote_telemetry_observation(
        _SECURITY, now=_NOW, observation_id=observation.observation_id,
        subject_kind=TelemetrySubjectKind.LINK, subject_ref=observation.subject_ref,
        privacy_scope=PrivacyClass.OPERATIONAL,
        source_disclosure=SourceDisclosure.PSEUDONYMOUS,
    )
    if r5.ok or r5.code != ManagementReasonCode.RBAC_DENIED:
        return fail(name, "promotion without telemetry.promote capability allowed")
    return ok(name, "promotion: born-bound flow; mismatch/unrecorded/privacy/RBAC all fail closed")


# --------------------------------------------------------------------------
# 25-26: role administration
# --------------------------------------------------------------------------


def case_25_role_assign_two_key() -> Result:
    name = "case_25_role_assign_two_key"
    api = _api()
    # SECURITY holds policy (rule allow-ra) but the auditor role has
    # no ROLES_ADMINISTER capability -> RBAC denied.
    r = api.assign_role(_SECURITY, now=_NOW, target_operator=_NOBODY, role_id="observer")
    if r.ok or r.code != ManagementReasonCode.RBAC_DENIED:
        return fail(name, "policy-without-capability role assign allowed: %r" % r.code)
    # OPERATOR holds ROLES_ADMINISTER capability, policy allows only
    # SECURITY -> policy denied.
    r2 = api.assign_role(_OPERATOR, now=_NOW, target_operator=_NOBODY, role_id="observer")
    if r2.ok or r2.code != ManagementReasonCode.POLICY_DENIED:
        return fail(name, "capability-without-policy role assign allowed: %r" % r2.code)
    # grant the administer role to SECURITY (deployment bootstrap:
    # direct store grant), then both keys exist -> executed
    api._role_store.grant(_SECURITY, "network-operator", instant=_NOW, actor_node_id=_ISSUER)
    r3 = api.assign_role(_SECURITY, now=_LATER, target_operator=_NOBODY, role_id="observer", reason="onboarding")
    if not r3.ok:
        return fail(name, "two-key role assign failed: %s" % r3.detail)
    if "observer" not in api._role_store.active_roles(_NOBODY, now=_LATER):
        return fail(name, "granted role not active")
    # revoke through the API
    r4 = api.assign_role(
        _SECURITY, now="2026-06-03T00:00:00Z", target_operator=_NOBODY,
        role_id="observer", revoke=True,
    )
    if not r4.ok:
        return fail(name, "revoke failed: %s" % r4.detail)
    if "observer" in api._role_store.active_roles(_NOBODY, now="2026-06-04T00:00:00Z"):
        return fail(name, "revoked role still active")
    # unknown role -> RBAC authority rejects
    r5 = api.assign_role(
        _SECURITY, now="2026-06-05T00:00:00Z", target_operator=_NOBODY,
        role_id="no-such-role",
    )
    if r5.ok or r5.code != ManagementReasonCode.AUTHORITY_REJECTED:
        return fail(name, "unknown role not authority-rejected: %r" % r5.code)
    # unknown target references still fail closed structurally
    r6 = api.assign_role(_SECURITY, now="2026-06-06T00:00:00Z", target_operator="", role_id="observer")
    if r6.ok or r6.code != ManagementReasonCode.INVALID_INPUT:
        return fail(name, "empty target accepted: %r" % r6.code)
    return ok(name, "role-assign two-key matrix + revoke + authority validation")


def case_26_revocation_immediate_effect() -> Result:
    name = "case_26_revocation_immediate_effect"
    api = _api()
    r = _create_session(api)
    if not r.ok:
        return fail(name, "fixture creation failed")
    # emergency revocation through the RBAC authority, then the NEXT
    # call denies
    api._role_store.revoke(_OPERATOR, "network-operator", instant=_LATER, actor_node_id=_ISSUER)
    r2 = _create_session(api, now="2026-06-03T00:00:00Z")
    if r2.ok or r2.code != ManagementReasonCode.RBAC_DENIED:
        return fail(name, "revoked capability still grants: %r" % r2.code)
    r3 = api.inspect_sessions(_OPERATOR, now="2026-06-03T00:00:00Z")
    if r3.ok:
        return fail(name, "revoked read capability still grants")
    return ok(name, "revocation takes effect on the next call")


# --------------------------------------------------------------------------
# 27-31: boundaries, imports, surface, determinism
# --------------------------------------------------------------------------

_MANAGEMENT_FILES = tuple(
    sorted(
        os.path.join(REPO, "management", f)
        for f in os.listdir(os.path.join(REPO, "management"))
        if f.endswith(".py")
    )
)


def case_27_import_discipline() -> Result:
    name = "case_27_import_discipline"
    allowed = {"policy", "routing", "sessions", "federation", "telemetry", "protocol"}
    allowed_external = {
        "__future__", "typing", "dataclasses", "hashlib", "re", "threading", "abc",
    }
    for path in _MANAGEMENT_FILES:
        with open(path, "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root not in allowed and root not in allowed_external:
                        return fail(
                            name,
                            "%s imports %s (not a declared dependency)"
                            % (os.path.basename(path), alias.name),
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    root = node.module.split(".")[0]
                    if root not in allowed and root not in allowed_external:
                        return fail(
                            name,
                            "%s imports from %s (not a declared dependency)"
                            % (os.path.basename(path), node.module),
                        )
    return ok(
        name,
        "imports limited to the five declared families + shared protocol primitives + stdlib",
    )


def case_28_no_vendor_symbols() -> Result:
    name = "case_28_no_vendor_symbols"
    pattern = re.compile(
        r"\b(5g|5G|sixg|6g|lte|wifi|wi-fi|cellular|open5gs|oai|oran|o-ran|gnb|enb|android|ios|apn|imsi)\b"
    )
    for path in _MANAGEMENT_FILES:
        with open(path, "r", encoding="utf-8") as handle:
            for lineno, line in enumerate(handle, 1):
                if pattern.search(line):
                    return fail(
                        name,
                        "%s:%d carries vendor/access vocabulary"
                        % (os.path.basename(path), lineno),
                    )
    return ok(name, "no vendor/access symbols in the management family")


def case_29_no_reverse_imports() -> Result:
    name = "case_29_no_reverse_imports"
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [
            d
            for d in dirs
            if d not in ("__pycache__", ".git", "docs", "spec", "tools")
        ]
        for f in files:
            if not f.endswith(".py"):
                continue
            path = os.path.join(root, f)
            if os.path.dirname(path) == os.path.join(REPO, "management"):
                continue
            with open(path, "r", encoding="utf-8") as handle:
                source = handle.read()
            if re.search(r"^\s*(from|import)\s+management\b", source, re.M):
                return fail(name, "%s imports management (reverse dependency)" % path)
    return ok(name, "nothing imports the management family")


def case_30_api_surface_frozen() -> Result:
    name = "case_30_api_surface_frozen"
    api = _api()
    methods = sorted(
        m for m in dir(api) if not m.startswith("_") and callable(getattr(api, m))
    )
    expected = sorted(
        {
            "inspect_policy", "inspect_sessions", "inspect_federation",
            "query_telemetry", "verify_audit", "inspect_roles",
            "create_session", "modify_session", "terminate_session",
            "join_federation", "accept_federation_peer",
            "export_federation_resource", "import_federation_resource",
            "promote_telemetry_observation", "assign_role",
        }
    )
    if methods != expected:
        return fail(name, "API surface is not the 15 frozen operations: %s" % methods)
    if len(ManagementOperation.values()) != len(expected):
        return fail(name, "operation vocabulary / entry point count mismatch")
    return ok(name, "API surface is exactly the 15 frozen operation methods")


def _scenario_fingerprint() -> str:
    """A canonical fingerprint of the composed management scenario (the
    determinism case): the audit chain, RBAC history, and session
    authority snapshot over a full allowed/denied/rejected mix."""
    api = _api()
    parts: List[str] = []
    # denials
    api.create_session(
        _NOBODY, now=_NOW, source_node_id=_NODE_A, destination_node_id=_NODE_B,
        topology=_graph(), resources=ResourceStore(), link_metrics={},
    )
    api._role_store.grant(_NOBODY, "network-operator", instant=_T0, actor_node_id=_ISSUER)
    api.create_session(
        _NOBODY, now=_NOW, source_node_id=_NODE_A, destination_node_id=_NODE_B,
        topology=_graph(), resources=ResourceStore(), link_metrics={},
    )
    api._role_store.revoke(_NOBODY, "network-operator", instant=_NOW, actor_node_id=_ISSUER)
    # executions
    r = _create_session(api)
    parts.append(r.evidence_refs[0])  # policy decision id
    parts.append(r.payload.session_id)
    api.modify_session(_OPERATOR, now=_NOW, session_id=r.payload.session_id, transition="AUTHORIZED")
    api.terminate_session(_OPERATOR, now=_LATER, session_id=r.payload.session_id)
    # federation flow
    federation, local_id, peer_id = _federation_domains()
    api2 = _api(federation_store=federation)
    join = api2.join_federation(
        _OPERATOR, now=_NOW,
        local_domain_id=local_id,
        peer_domain_id=peer_id,
        peer_identity_reference=_NODE_B,
        declared_scopes=(Scope.ROUTE_IMPORT,),
        valid_from=_T0, valid_until=_T1,
    )
    parts.append(join.payload.relationship.relationship_id)
    # audit + rbac + session snapshots
    parts.append(json.dumps(api._audit.snapshot(), sort_keys=True))
    parts.append(json.dumps(api._role_store.snapshot(), sort_keys=True))
    parts.append(json.dumps(api._session_store.snapshot(), sort_keys=True))
    parts.append(json.dumps(federation.snapshot(), sort_keys=True))
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def case_31_determinism_across_hash_seeds() -> Result:
    name = "case_31_determinism_across_hash_seeds"
    script = (
        "import sys; sys.path.insert(0, %r); "
        "import tools.management_selftest as t; "
        "print(t._scenario_fingerprint())" % (REPO,)
    )
    digests = []
    for seed in ("0", "1", "7919"):
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, cwd=REPO,
            env=dict(os.environ, PYTHONHASHSEED=seed),
        )
        if proc.returncode != 0:
            return fail(
                name, "seed %s failed: %s" % (seed, proc.stderr.strip()[-300:])
            )
        digests.append(proc.stdout.strip())
    if len(set(digests)) != 1:
        return fail(name, "fingerprints diverge across seeds: %r" % (digests,))
    return ok(name, "composed scenario fingerprint identical across seeds 0/1/7919")


# --------------------------------------------------------------------------
# 32-34: frozen surfaces, compilation, CI wiring
# --------------------------------------------------------------------------


def case_32_frozen_spec_intact() -> Result:
    name = "case_32_frozen_spec_intact"
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", "spec/"],
        capture_output=True, text=True, cwd=REPO,
    )
    if status.stdout.strip():
        return fail(name, "uncommitted spec/ changes: %s" % status.stdout.strip())
    ref_check = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/main"],
        capture_output=True, text=True, cwd=REPO,
    )
    if ref_check.returncode == 0:
        spec_diff = subprocess.run(
            ["git", "diff", "--name-only", "origin/main", "HEAD", "--", "spec/"],
            capture_output=True, text=True, cwd=REPO,
        )
        if spec_diff.stdout.strip():
            return fail(
                name, "spec/ differs from origin/main: %s" % spec_diff.stdout.strip()
            )
        docs_diff = subprocess.run(
            ["git", "diff", "--name-only", "origin/main", "HEAD", "--", "docs/"],
            capture_output=True, text=True, cwd=REPO,
        )
        changed = {line for line in docs_diff.stdout.splitlines() if line.strip()}
        allowed = {"docs/WORK-030-handoff.md"}  # the W023..029 handoff precedent
        if not changed <= allowed:
            return fail(name, "docs/ changes beyond the handoff: %r" % sorted(changed))
        workflow = subprocess.run(
            ["git", "diff", "origin/main", "--", ".github/"],
            capture_output=True, text=True, cwd=REPO,
        )
        if "management_selftest.py" not in workflow.stdout:
            return fail(name, ".github delta does not include the management CI step")
        return ok(
            name,
            "spec/ byte-identical to origin/main; docs/ = the W030 handoff; CI step additive",
        )
    # Degraded mode (no origin/main ref in this checkout): the working
    # tree must still be clean over spec/.
    tree = subprocess.run(
        ["git", "status", "--porcelain", "--", "spec/"],
        capture_output=True, text=True, cwd=REPO,
    )
    if tree.stdout.strip():
        return fail(
            name, "working tree dirty over frozen surfaces: %s" % tree.stdout.strip()
        )
    return ok(name, "spec/ clean (origin/main ref unavailable; working tree clean)")


def case_33_py_compile_clean() -> Result:
    name = "case_33_py_compile_clean"
    for path in _MANAGEMENT_FILES:
        try:
            py_compile.compile(path, doraise=True)
        except py_compile.PyCompileError as error:
            return fail(name, "%s does not compile: %s" % (os.path.basename(path), error))
    return ok(name, "management family compiles clean")


def case_34_ci_wiring() -> Result:
    name = "case_34_ci_wiring"
    workflow_path = os.path.join(REPO, ".github", "workflows", "spec-check.yml")
    with open(workflow_path, "r", encoding="utf-8") as handle:
        workflow = handle.read()
    if "python3 tools/management_selftest.py" not in workflow:
        return fail(name, "management battery not wired into CI")
    expected = [
        "spec_check.py", "spec_check_selftest.py", "schema_check.py",
        "schema_selftest.py", "envelope_selftest.py", "identity_selftest.py",
        "capability_selftest.py", "discovery_selftest.py",
        "topology_selftest.py", "resource_selftest.py", "intent_selftest.py",
        "policy_selftest.py", "routing_selftest.py", "session_selftest.py",
        "multipath_selftest.py", "mobility_selftest.py",
        "federation_selftest.py", "adapter_selftest.py",
        "transport_selftest.py", "ipintegration_selftest.py",
        "fivegc_selftest.py", "wifi_selftest.py", "backhaul_selftest.py",
        "mesh_selftest.py", "distcore_selftest.py", "service_selftest.py",
        "telemetry_selftest.py", "energy_selftest.py", "security_selftest.py",
        "upgrade_selftest.py", "management_selftest.py",
    ]
    for battery in expected:
        if "tools/%s" % battery not in workflow:
            return fail(name, "battery %r missing from CI" % battery)
    return ok(name, "CI wired: management battery + all %d prior tools" % len(expected))


# --------------------------------------------------------------------------
# 35-37: serialization, no-bypass, genuine authorities
# --------------------------------------------------------------------------


def case_35_serialization_round_trips() -> Result:
    name = "case_35_serialization_round_trips"
    ledger = AuditLedger()
    ledger.append(
        recorded_instant=_NOW,
        operation=ManagementOperation.SESSION_CREATE,
        operator_node_id=_OPERATOR,
        outcome=AuditOutcome.EXECUTED,
        detail="probe",
        evidence_refs=("a", "b"),
    )
    record = ledger.records()[0]
    wire = audit_record_to_mapping(record)
    restored = audit_record_from_mapping(wire)
    if restored != record:
        return fail(name, "audit record round-trip diverged")
    # tampered content fails closed (id recomputation)
    tampered = dict(wire)
    tampered["detail"] = wire["detail"] + "!"
    try:
        audit_record_from_mapping(tampered)
        return fail(name, "tampered audit record accepted")
    except ManagementError:
        pass
    # unknown keys fail closed
    smuggled = dict(wire)
    smuggled["extra"] = "x"
    try:
        audit_record_from_mapping(smuggled)
        return fail(name, "unknown-key audit record accepted")
    except ManagementError:
        pass
    # role event round trip
    store = RoleAssignmentStore(roles=_CATALOG)
    event = store.grant(_OPERATOR, "observer", instant=_NOW, actor_node_id=_ISSUER)
    event_wire = role_event_to_mapping(event)
    if role_event_from_mapping(event_wire) != event:
        return fail(name, "role event round-trip diverged")
    tampered_event = dict(event_wire)
    tampered_event["reason"] = "tampered"
    try:
        role_event_from_mapping(tampered_event)
        return fail(name, "tampered role event accepted")
    except ManagementError:
        pass
    return ok(name, "wire round-trips byte-stable; tampered DATA fails closed")


def case_36_no_bypass_structural() -> Result:
    name = "case_36_no_bypass_structural"
    authority_holders = {
        "_policy_store", "_session_store", "_federation_store",
        "_telemetry_store", "_role_store", "_audit", "_engine",
        "_routing_engine",
    }
    api_path = os.path.join(REPO, "management", "api.py")
    with open(api_path, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=api_path)
    for node in ast.walk(tree):
        # (a) never WRITE into an authority object
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Attribute)
                    and isinstance(target.value.value, ast.Name)
                    and target.value.value.id == "self"
                    and target.value.attr in authority_holders
                ):
                    return fail(
                        name,
                        "management writes %s.%s (bypasses the authority API)"
                        % (target.value.attr, target.attr),
                    )
        # (b) never touch another authority's private members
        if isinstance(node, ast.Attribute):
            if (
                isinstance(node.value, ast.Attribute)
                and isinstance(node.value.value, ast.Name)
                and node.value.value.id == "self"
                and node.value.attr in authority_holders
                and node.attr.startswith("_")
            ):
                return fail(
                    name,
                    "management reaches into %s.%s (private member of an authority)"
                    % (node.value.attr, node.attr),
                )
    return ok(name, "AST proof: no writes into authorities; no private-member access")


def case_37_genuine_authorities_required() -> Result:
    name = "case_37_genuine_authorities_required"

    class FakeStore:  # duck-typed, however complete
        def snapshot(self) -> Dict[str, Any]:
            return {}

        def list_applicable(self, now: str) -> Tuple[PolicySet, ...]:
            return ()

        def active_capabilities(
            self, operator: str, *, now: str
        ) -> FrozenSet[str]:
            return frozenset()

    for label, kwargs in (
        ("policy_store", {"policy_store": FakeStore()}),
        ("session_store", {"session_store": FakeStore()}),
        ("federation_store", {"federation_store": FakeStore()}),
        ("telemetry_store", {"telemetry_store": FakeStore()}),
        ("role_store", {"role_store": FakeStore()}),
    ):
        merged = dict(
            policy_store=PolicyStore(),
            session_store=SessionStore(),
            federation_store=FederationStore(),
            telemetry_store=TelemetryStore(),
            role_store=_role_store(),
        )
        merged.update(kwargs)
        try:
            ManagementAPI(**merged)
            return fail(name, "duck-typed %s accepted" % label)
        except ManagementError:
            pass
    return ok(name, "constructor requires genuine authority instances (fakes rejected)")


# --------------------------------------------------------------------------
# 38-39: PR #32 Architect-correction regressions (review 5047201533)
# --------------------------------------------------------------------------


def _hostile(store: Any, method: str, failure: str) -> Any:
    """Turn a GENUINE authority instance into a failing one: replace
    exactly one public callable with a function that raises an
    unexpected RuntimeError.  (The object remains a genuine instance
    of its authority class -- this is the hostile/failing
    injected-authority regression shape: the authority fails, the
    composition root must still account for the call.)"""

    def hostile(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError(failure)

    setattr(store, method, hostile)
    return store


def case_38_hostile_authority_failure_boundary() -> Result:
    """PR #32 blocker 1 regression: the universal outer operation
    boundary guarantees ONE-AND-ONLY-ONE audit record per invocation
    when an injected authority fails unexpectedly -- never an
    unaudited exception, never a success, never a double audit."""
    name = "case_38_hostile_authority_failure_boundary"

    def run(
        label: str,
        api: ManagementAPI,
        call: Callable[[], ManagementResult],
        operation: str,
    ) -> Optional[str]:
        ledger = api._audit
        before = len(ledger.records())
        result = call()
        new_records = ledger.records()[before:]
        if len(new_records) != 1:
            return "%s: expected exactly 1 audit record, got %d" % (
                label,
                len(new_records),
            )
        record = new_records[0]
        if record.outcome != AuditOutcome.FAILED:
            return "%s: audit outcome %r is not failed" % (label, record.outcome)
        if record.operation != operation:
            return "%s: record operation %r wrong" % (label, record.operation)
        if result.ok or result.code != ManagementReasonCode.FAILED:
            return "%s: result not a FAILED envelope (ok=%r code=%r)" % (
                label,
                result.ok,
                result.code,
            )
        if result.audit_record_id != record.record_id:
            return "%s: result does not reference the failure record" % label
        if result.payload is not None:
            return "%s: failed result carries a payload" % label
        return None

    scenarios = 0

    # (1) read path -- hostile session-authority snapshot
    api = _api(
        session_store=_hostile(SessionStore(), "snapshot", "hostile snapshot")
    )
    error = run(
        "session.snapshot",
        api,
        lambda: api.inspect_sessions(_OPERATOR, now=_NOW),
        ManagementOperation.SESSION_SNAPSHOT,
    )
    if error:
        return fail(name, error)
    scenarios += 1

    # (2) privileged delegation -- hostile routing-engine evaluation
    engine = _hostile(RoutingEngine(), "evaluate", "hostile evaluation")
    api = _api(routing_engine=engine)
    error = run(
        "routing.evaluate",
        api,
        lambda: _create_session(api),
        ManagementOperation.SESSION_CREATE,
    )
    if error:
        return fail(name, error)
    scenarios += 1

    # (3) privileged delegation -- hostile session-authority creation
    api = _api(session_store=_hostile(SessionStore(), "create", "hostile create"))
    error = run(
        "session.create",
        api,
        lambda: _create_session(api),
        ManagementOperation.SESSION_CREATE,
    )
    if error:
        return fail(name, error)
    scenarios += 1

    # (4) privileged delegation -- hostile session-authority teardown
    api = _api(session_store=_hostile(SessionStore(), "terminate", "hostile teardown"))
    error = run(
        "session.terminate",
        api,
        lambda: api.terminate_session(
            _OPERATOR, now=_NOW, session_id="sha256:" + "0" * 64
        ),
        ManagementOperation.SESSION_TERMINATE,
    )
    if error:
        return fail(name, error)
    scenarios += 1

    # (5) federation control -- hostile relationship lookup
    api = _api(
        federation_store=_hostile(
            FederationStore(), "get_relationship", "hostile lookup"
        )
    )
    error = run(
        "federation.get_relationship",
        api,
        lambda: api.accept_federation_peer(
            _OPERATOR, now=_NOW, relationship_id="adcos:federation.relationship.v1:"
            + "0" * 64
        ),
        ManagementOperation.FEDERATION_ACCEPT_PEER,
    )
    if error:
        return fail(name, error)
    scenarios += 1

    # (6) RBAC gate -- hostile capability resolution (an UNEXPECTED
    # exception, not a ManagementError, so it must not be mistaken
    # for a clean denial)
    api = _api(
        role_store=_hostile(
            RoleAssignmentStore(roles=_CATALOG),
            "active_capabilities",
            "hostile gate",
        )
    )
    error = run(
        "rbac.active_capabilities",
        api,
        lambda: api.inspect_sessions(_OPERATOR, now=_NOW),
        ManagementOperation.SESSION_SNAPSHOT,
    )
    if error:
        return fail(name, error)
    scenarios += 1

    # (7) denial formation interrupted -- the RBAC denial was DECIDED
    # (no capability) but the hostile active_roles raises while
    # FORMING the denial detail: the invocation must still leave
    # exactly one record (not zero, not two)
    roles = RoleAssignmentStore(roles=_CATALOG)  # no grants: no capability
    _hostile(roles, "active_roles", "hostile denial detail")
    api = _api(role_store=roles)
    error = run(
        "rbac.active_roles (denial formation)",
        api,
        lambda: api.inspect_sessions(_OPERATOR, now=_NOW),
        ManagementOperation.SESSION_SNAPSHOT,
    )
    if error:
        return fail(name, error)
    scenarios += 1

    # (8) telemetry read -- hostile query (unexpected, not TelemetryError)
    api = _api(
        telemetry_store=_hostile(
            TelemetryStore(), "query_observations", "hostile query"
        )
    )
    error = run(
        "telemetry.query_observations",
        api,
        lambda: api.query_telemetry(
            _OPERATOR, now=_NOW, privacy_scope=PrivacyClass.OPERATIONAL
        ),
        ManagementOperation.TELEMETRY_QUERY,
    )
    if error:
        return fail(name, error)
    scenarios += 1

    # (9) policy read payload -- applicable sets resolve genuinely,
    # the hostile snapshot fails while materializing the payload
    genuine_policy = _policy_store([_management_policy_set()])
    policy = PolicyStore()
    setattr(policy, "list_applicable", genuine_policy.list_applicable)
    _hostile(policy, "snapshot", "hostile policy snapshot")
    api = ManagementAPI(
        policy_store=policy,
        session_store=SessionStore(),
        federation_store=FederationStore(),
        telemetry_store=TelemetryStore(),
        role_store=_role_store(),
    )
    error = run(
        "policy.snapshot",
        api,
        lambda: api.inspect_policy(_OPERATOR, now=_NOW),
        ManagementOperation.POLICY_SNAPSHOT,
    )
    if error:
        return fail(name, error)
    scenarios += 1

    # (10) contrast -- an EXPECTED policy-material failure (the
    # genuine PolicyError on a rejected instant) remains a documented
    # audited DENIAL, not a failure: exactly one record either way
    policy = PolicyStore()

    def _reject_instant(now: str) -> Tuple[PolicySet, ...]:
        raise PolicyError("evaluation-instant", "hostile rejected instant")

    setattr(policy, "list_applicable", _reject_instant)
    api = ManagementAPI(
        policy_store=policy,
        session_store=SessionStore(),
        federation_store=FederationStore(),
        telemetry_store=TelemetryStore(),
        role_store=_role_store(),
    )
    ledger = api._audit
    before = len(ledger.records())
    result = api.inspect_policy(_OPERATOR, now=_NOW)
    new_records = ledger.records()[before:]
    if len(new_records) != 1:
        return fail(
            name,
            "expected-policy-error: expected exactly 1 audit record, got %d"
            % len(new_records),
        )
    if new_records[0].outcome != AuditOutcome.DENIED_INVALID_INPUT:
        return fail(
            name,
            "expected-policy-error: outcome %r is not denied-invalid-input"
            % new_records[0].outcome,
        )
    if result.ok or result.code != ManagementReasonCode.INVALID_INPUT:
        return fail(name, "expected-policy-error: result is not the input denial")
    if result.audit_record_id != new_records[0].record_id:
        return fail(name, "expected-policy-error: audit reference missing")
    scenarios += 1

    # (11) no-double-audit proof -- a fault AFTER the invocation
    # already appended its record appends NOTHING further: the failed
    # envelope references the existing record and the ledger grows by
    # exactly one
    api = _api()
    ledger = api._audit
    before = len(ledger.records())

    def _audited_then_raises() -> ManagementResult:
        api._record(
            now=_NOW,
            operation=ManagementOperation.SESSION_SNAPSHOT,
            operator=_OPERATOR,
            outcome=AuditOutcome.EXECUTED,
            detail="audited before the fault",
        )
        raise RuntimeError("fault after the audit")

    result = api._invoke(
        ManagementOperation.SESSION_SNAPSHOT,
        _OPERATOR,
        _NOW,
        _audited_then_raises,
    )
    new_records = ledger.records()[before:]
    if len(new_records) != 1:
        return fail(
            name,
            "already-audited path: expected exactly 1 record, got %d"
            % len(new_records),
        )
    if result.ok or result.code != ManagementReasonCode.FAILED:
        return fail(name, "already-audited path: envelope is not FAILED")
    if result.audit_record_id != new_records[0].record_id:
        return fail(name, "already-audited path: envelope lost the record reference")
    scenarios += 1

    return ok(
        name,
        "%d hostile/expected scenarios: exactly one record each, "
        "no double audit" % scenarios,
    )


def case_39_forged_initial_event_id() -> Result:
    """PR #32 blocker 2 regression: constructor-injected initial RBAC
    events are integrity-validated at the authoritative construction
    boundary -- a valid-looking event whose event_id does not
    recompute from its content (forged identity) fails closed, while
    a genuine content-derived initial event installs cleanly."""
    name = "case_39_forged_initial_event_id"
    # a genuine event (id minted from its content by the store itself)
    seeder = RoleAssignmentStore(roles=_CATALOG)
    event = seeder.grant(
        _OPERATOR, "network-operator", instant=_T0, actor_node_id=_ISSUER
    )
    if event.event_id != derive_role_event_id(event):
        return fail(name, "fixture: grant did not mint a content-derived id")
    # genuine initial event -> construction succeeds, history installs
    store = RoleAssignmentStore(roles=_CATALOG, initial_events=(event,))
    if store.active_capabilities(_OPERATOR, now=_NOW) != frozenset(
        _ROLE_OPERATOR.capabilities
    ):
        return fail(name, "genuine initial event did not install capabilities")

    def _with_id(event_id: str) -> RoleAssignmentEvent:
        return RoleAssignmentEvent(
            event_id=event_id,
            kind=event.kind,
            operator_node_id=event.operator_node_id,
            role_id=event.role_id,
            instant=event.instant,
            actor_node_id=event.actor_node_id,
            reason=event.reason,
            valid_from=event.valid_from,
            valid_until=event.valid_until,
        )

    # forged well-formed id: same content, different identity
    forged = _with_id("f" * 64)
    if forged.event_id == derive_role_event_id(forged):
        return fail(name, "fixture: forged id accidentally content-valid")
    try:
        RoleAssignmentStore(roles=_CATALOG, initial_events=(forged,))
        return fail(name, "forged well-formed event id accepted")
    except ManagementError:
        pass
    # empty/garbage id also fails closed
    try:
        RoleAssignmentStore(roles=_CATALOG, initial_events=(_with_id(""),))
        return fail(name, "empty event id accepted")
    except ManagementError:
        pass
    # a SINGLE forged entry poisons the whole construction (fail
    # closed on any inconsistency, not just the first entry)
    try:
        RoleAssignmentStore(roles=_CATALOG, initial_events=(event, forged))
        return fail(name, "mixed genuine/forged initial events accepted")
    except ManagementError:
        pass
    # the wire-form reconstruction path still enforces the same
    # integrity (the pre-existing serialization check, unchanged)
    wire = role_event_to_mapping(event)
    wire["event_id"] = "e" * 64
    try:
        role_event_from_mapping(wire)
        return fail(name, "serialization layer lost its integrity check")
    except ManagementError:
        pass
    return ok(
        name,
        "forged initial event ids fail closed; genuine ones install",
    )


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------

CASES = (
    case_01_frozen_vocabularies,
    case_02_role_catalog_validation,
    case_03_rbac_temporal_matrix,
    case_04_roles_additive,
    case_05_rbac_closure_owned,
    case_06_every_call_audited,
    case_07_audit_tamper_matrix,
    case_08_audit_chain_discipline,
    case_09_audit_no_secrets,
    case_10_audit_closure_owned,
    case_11_two_key_matrix,
    case_12_cross_set_aggregation,
    case_13_no_applicable_set_denies,
    case_14_no_decision_injection_surface,
    case_15_session_full_chain,
    case_16_authority_verdicts_never_overridden,
    case_17_session_lifecycle_happy_path,
    case_18_federation_join_flow,
    case_19_federation_control_denials,
    case_20_federation_accept_peer,
    case_21_federation_export,
    case_22_federation_import,
    case_23_telemetry_query_privacy_fence,
    case_24_telemetry_promotion,
    case_25_role_assign_two_key,
    case_26_revocation_immediate_effect,
    case_27_import_discipline,
    case_28_no_vendor_symbols,
    case_29_no_reverse_imports,
    case_30_api_surface_frozen,
    case_31_determinism_across_hash_seeds,
    case_32_frozen_spec_intact,
    case_33_py_compile_clean,
    case_34_ci_wiring,
    case_35_serialization_round_trips,
    case_36_no_bypass_structural,
    case_37_genuine_authorities_required,
    case_38_hostile_authority_failure_boundary,
    case_39_forged_initial_event_id,
)


def main() -> int:
    print("ADCOS management API self-test (WORK-030) -- %d cases" % len(CASES))
    print("-" * 72)
    failures: List[str] = []
    for case in CASES:
        try:
            name, passed, detail = case()
        except Exception as error:  # noqa: BLE001 -- battery robustness
            name, passed, detail = case.__name__, False, "EXCEPTION: %r" % error
        status = "[ok  ]" if passed else "[FAIL]"
        print("%s %-52s %s" % (status, name, detail))
        if not passed:
            failures.append(name)
    print("-" * 72)
    if failures:
        print("Result: FAIL (%d/%d cases failed)" % (len(failures), len(CASES)))
        for name in failures:
            print("  - %s" % name)
        return 1
    print("Result: PASS (%d/%d cases)" % (len(CASES), len(CASES)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
