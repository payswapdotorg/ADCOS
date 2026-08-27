"""The management API composition root (WORK-030).

This is the operator-facing control surface of the Management &
Observability plane (spec/architecture.md 5.6, 22): management,
configuration, audit, and operational control APIs.  It is a
composition root and a facade -- NEVER a new authority:

    operator request
        ->
    [1] RBAC gate        (roles/capabilities; deny-by-default; P6)
        ->
    [2] policy gate      (privileged actions only: a FRESH genuine
                          WORK-010 engine evaluation over the policy
                          store's live applicable sets; explicit ALLOW
                          required; deny-by-default)
        ->
    [3] delegation       (the owning authority's genuine public API
                          executes the action -- routing computes,
                          sessions/federation/telemetry mutate their
                          own state; management owns none of it)
        ->
    [4] audit append     (every call -- allowed OR denied -- produces
                          exactly one tamper-evident audit record)

Provenance discipline (the PR #31 review lesson, applied at birth):
the policy decision that authorizes a privileged action is evaluated
INSIDE this call, by THIS composition root, against the injected
genuine :class:`policy.evaluation.PolicyEngine` and the injected
genuine :class:`policy.store.PolicyStore`.  No API method accepts a
caller-supplied ``PolicyDecision``, route decision, or any other
authority-minted object as authorization material -- there is no
injection surface to duck-type, and a complete-content digest is
never mistaken for authority provenance.

Cross-set policy aggregation (documented, conservative, deterministic):
the store's live applicable sets are evaluated in snapshot order; the
operation is authorized iff at least one evaluation explicitly ALLOWS
(``code == allow``) and NO evaluation explicitly denies or fails
closed (``code in {deny, fail-closed, conflict, invalid-policy,
invalid-subject, unsupported-predicate}``).  Verdicts where a set is
merely SILENT about the operation (``default-deny``, ``missing-fact``,
``policy-expired``, ``policy-not-yet-valid``) grant nothing and do not
block a different set's explicit allow.  Management performs no rule
interpretation, no precedence invention, and no conflict resolution
(those are the WORK-010 engine's job inside one set); with the common
single-applicable-set deployment this aggregation reduces exactly to
that set's own verdict.

Two-key authorization: RBAC decides whether THIS operator may even
request the operation (capability); WORK-010 policy decides whether
the privileged ACTION is permitted.  Neither alone ever suffices --
see the package README for the full rationale.
"""

from __future__ import annotations

from typing import Any, FrozenSet, Mapping, Optional, Tuple

from federation.model import FederationError, FederationRelationship
from federation.policy import evaluate_federation_operation
from federation.store import FederationStore
from policy.evaluation import PolicyEngine
from policy.model import (
    DecisionCode,
    Effect,
    Operation as PolicyOperation,
    PolicyContext,
    PolicyDecision,
    PolicySet,
)
from policy.store import PolicyStore
from routing.engine import RoutingEngine
from routing.model import RouteEvaluationResult, RoutingContext, RoutingError
from sessions.store import SessionStore
from telemetry.errors import TelemetryError
from telemetry.store import TelemetryStore

from .audit import AuditLedger
from .errors import ManagementError, ManagementReasonCode
from .model import (
    AuditOutcome,
    ManagementOperation,
    ManagementResult,
    operation_spec,
    require_instant,
)
from .rbac import RoleAssignmentStore, _validate_operator_ref

#: Decision codes under which one policy set is SILENT about an
#: operation (no rule matched / facts absent / rules out of validity
#: window).  A silent set grants nothing but does not veto another
#: set's explicit allow.
_SILENT_POLICY_CODES = frozenset(
    {
        DecisionCode.DEFAULT_DENY,
        DecisionCode.MISSING_FACT,
        DecisionCode.POLICY_EXPIRED,
        DecisionCode.POLICY_NOT_YET_VALID,
    }
)

#: Decision codes under which one policy set HARD-BLOCKS the
#: operation across all live sets: an explicit deny, or an evaluation
#: that failed closed (conflict, invalid set, invalid subject,
#: unsupported predicate).  The conservative direction of "explicit
#: deny beats allow" -- a blocking code can only remove authority.
_BLOCKING_POLICY_CODES = frozenset(
    {
        DecisionCode.DENY,
        DecisionCode.FAIL_CLOSED,
        DecisionCode.CONFLICT,
        DecisionCode.INVALID_POLICY,
        DecisionCode.INVALID_SUBJECT,
        DecisionCode.UNSUPPORTED_PREDICATE,
    }
)


class ManagementAPI:
    """The management/control API facade (WORK-030).

    Constructed from GENUINE injected authorities:

    - ``policy_store``     -- WORK-010 ``PolicyStore`` (read: live
      applicable sets; the engine is constructed here and never
      shared as a mutation surface);
    - ``session_store``    -- WORK-012 ``SessionStore``;
    - ``federation_store`` -- WORK-015 ``FederationStore``;
    - ``telemetry_store``  -- WORK-026 ``TelemetryStore``;
    - ``role_store``       -- the management plane's own RBAC store
      (WORK-030);
    - ``audit``            -- the management plane's own audit ledger
      (WORK-030);
    - ``routing_engine``   -- optional WORK-011 ``RoutingEngine``
      (a stateless genuine engine is constructed when omitted).

    The API exposes no authority object and no mutation capability
    beyond the frozen operation methods below: it cannot bypass the
    authority boundaries because it HOLDS the authorities and DELEGATES
    to them -- it never reaches around them.
    """

    def __init__(
        self,
        *,
        policy_store: PolicyStore,
        session_store: SessionStore,
        federation_store: FederationStore,
        telemetry_store: TelemetryStore,
        role_store: RoleAssignmentStore,
        audit: Optional[AuditLedger] = None,
        routing_engine: Optional[RoutingEngine] = None,
    ) -> None:
        for label, obj, types in (
            ("policy_store", policy_store, PolicyStore),
            ("session_store", session_store, SessionStore),
            ("federation_store", federation_store, FederationStore),
            ("telemetry_store", telemetry_store, TelemetryStore),
            ("role_store", role_store, RoleAssignmentStore),
        ):
            if not isinstance(obj, types):
                raise ManagementError(
                    ManagementReasonCode.INVALID_INPUT,
                    "%s must be a genuine %s (got %s)"
                    % (label, types.__name__, type(obj).__name__),
                )
        if audit is not None and not isinstance(audit, AuditLedger):
            raise ManagementError(
                ManagementReasonCode.INVALID_INPUT,
                "audit must be a genuine AuditLedger",
            )
        if routing_engine is not None and not isinstance(
            routing_engine, RoutingEngine
        ):
            raise ManagementError(
                ManagementReasonCode.INVALID_INPUT,
                "routing_engine must be a genuine RoutingEngine",
            )
        self._policy_store = policy_store
        self._session_store = session_store
        self._federation_store = federation_store
        self._telemetry_store = telemetry_store
        self._role_store = role_store
        self._audit = audit if audit is not None else AuditLedger()
        self._engine = PolicyEngine()
        self._routing_engine = (
            routing_engine if routing_engine is not None else RoutingEngine()
        )

    # ------------------------------------------------------------------
    # Shared machinery
    # ------------------------------------------------------------------

    def _record(
        self,
        *,
        now: str,
        operation: str,
        operator: str,
        outcome: str,
        detail: str,
        evidence_refs: Tuple[str, ...] = (),
    ) -> str:
        """Append one audit record; return its id (every call is
        audited -- allowed or denied)."""
        record = self._audit.append(
            recorded_instant=now,
            operation=operation,
            operator_node_id=operator,
            outcome=outcome,
            detail=detail,
            evidence_refs=evidence_refs,
        )
        return record.record_id

    def _deny(
        self,
        *,
        now: str,
        operation: str,
        operator: str,
        code: str,
        detail: str,
        evidence_refs: Tuple[str, ...] = (),
    ) -> ManagementResult:
        """Uniform audited denial."""
        outcome = {
            ManagementReasonCode.RBAC_DENIED: AuditOutcome.DENIED_RBAC,
            ManagementReasonCode.POLICY_DENIED: AuditOutcome.DENIED_POLICY,
            ManagementReasonCode.INVALID_INPUT: (
                AuditOutcome.DENIED_INVALID_INPUT
            ),
        }.get(code, AuditOutcome.FAILED)
        audit_id = self._record(
            now=now,
            operation=operation,
            operator=operator,
            outcome=outcome,
            detail=detail,
            evidence_refs=evidence_refs,
        )
        return ManagementResult(
            ok=False,
            code=code,
            detail=detail,
            evidence_refs=evidence_refs,
            audit_record_id=audit_id,
        )

    def _evaluate_policy(
        self, context: PolicyContext, *, now: str
    ) -> Tuple[bool, Optional[PolicyDecision], str]:
        """Evaluate ``context`` over the live applicable policy sets
        (the documented conservative aggregation).  Returns
        ``(authorized, decision, detail)``.  The decision is the FIRST
        explicit ALLOW in deterministic snapshot order (the one whose
        policy-set identity downstream binding checks will see)."""
        try:
            applicable = self._policy_store.list_applicable(now)
        except Exception as error:  # PolicyError on malformed now
            return False, None, "policy store rejected the instant: %s" % error
        if not applicable:
            return (
                False,
                None,
                "no applicable policy set at %s (deny-by-default)" % now,
            )
        allow_decision: Optional[PolicyDecision] = None
        for policy_set in applicable:
            result = self._engine.evaluate(policy_set, context)
            code = result.code
            decision = result.decision
            if code in _BLOCKING_POLICY_CODES:
                return (
                    False,
                    decision,
                    "policy set %s@%d blocks the operation (code %s: %s)"
                    % (
                        policy_set.set_id,
                        policy_set.version,
                        code,
                        result.detail,
                    ),
                )
            if (
                allow_decision is None
                and code == DecisionCode.ALLOW
                and decision is not None
                and decision.effect == Effect.ALLOW
            ):
                allow_decision = decision
        if allow_decision is None:
            return (
                False,
                None,
                "no applicable policy set explicitly allows the "
                "operation (deny-by-default)",
            )
        return True, allow_decision, "explicit ALLOW by decision %s" % (
            allow_decision.decision_id,
        )

    def _gate(
        self,
        *,
        operation: str,
        operator: str,
        now: str,
        context: Optional[PolicyContext] = None,
    ) -> Tuple[bool, Optional[PolicyDecision], Optional[ManagementResult]]:
        """The two-key authorization gate.

        Returns ``(authorized, decision, denial)``: exactly one of the
        denial result (audited) or the decision is set.  RBAC runs
        first (cheap, local); the policy gate runs only for privileged
        operations (the frozen structural classification)."""
        spec = operation_spec(operation)
        try:
            capabilities = self._role_store.active_capabilities(
                operator, now=now
            )
        except ManagementError as error:
            return (
                False,
                None,
                self._deny(
                    now=now,
                    operation=operation,
                    operator=operator,
                    code=ManagementReasonCode.INVALID_INPUT,
                    detail="RBAC resolution failed: %s" % error.detail,
                ),
            )
        if spec.capability not in capabilities:
            return (
                False,
                None,
                self._deny(
                    now=now,
                    operation=operation,
                    operator=operator,
                    code=ManagementReasonCode.RBAC_DENIED,
                    detail="operator holds no active role granting %r "
                    "(active roles: %s; deny-by-default)"
                    % (
                        spec.capability,
                        self._role_store.active_roles(operator, now=now),
                    ),
                ),
            )
        decision: Optional[PolicyDecision] = None
        if spec.privileged:
            if context is None:
                return (
                    False,
                    None,
                    self._deny(
                        now=now,
                        operation=operation,
                        operator=operator,
                        code=ManagementReasonCode.FAILED,
                        detail="internal error: privileged operation "
                        "evaluated without a policy context",
                    ),
                )
            authorized, decision, why = self._evaluate_policy(context, now=now)
            if not authorized:
                return (
                    False,
                    None,
                    self._deny(
                        now=now,
                        operation=operation,
                        operator=operator,
                        code=ManagementReasonCode.POLICY_DENIED,
                        detail=why,
                    ),
                )
        return True, decision, None

    @staticmethod
    def _operator_and_now(
        operator: object, now: object
    ) -> Tuple[str, str]:
        operator_ref = _validate_operator_ref(operator, "operator")
        require_instant(now, "now")
        return operator_ref, str(now)

    # ------------------------------------------------------------------
    # Read / inspect operations (non-privileged; RBAC capability-gated)
    # ------------------------------------------------------------------

    def inspect_policy(self, operator: str, *, now: str) -> ManagementResult:
        """Inspect the live policy material (RBAC ``policy.read``)."""
        operation = ManagementOperation.POLICY_SNAPSHOT
        try:
            operator, now = self._operator_and_now(operator, now)
        except ManagementError as error:
            return self._deny(
                now="1970-01-01T00:00:00Z",
                operation=operation,
                operator=str(operator),
                code=ManagementReasonCode.INVALID_INPUT,
                detail=error.detail,
            )
        authorized, _, denial = self._gate(
            operation=operation, operator=operator, now=now
        )
        if denial is not None:
            return denial
        try:
            applicable = self._policy_store.list_applicable(now)
        except Exception as error:
            return self._deny(
                now=now,
                operation=operation,
                operator=operator,
                code=ManagementReasonCode.INVALID_INPUT,
                detail="policy store rejected the instant: %s" % error,
            )
        payload = {
            "applicable": [
                {"set_id": ps.set_id, "version": ps.version}
                for ps in applicable
            ],
            "snapshot": [
                {"set_id": ps.set_id, "version": ps.version}
                for ps in self._policy_store.snapshot()
            ],
        }
        evidence = tuple(
            "policy:%s@%d" % (ps.set_id, ps.version) for ps in applicable
        )
        audit_id = self._record(
            now=now,
            operation=operation,
            operator=operator,
            outcome=AuditOutcome.EXECUTED,
            detail="inspected policy material (%d applicable set(s))"
            % len(applicable),
            evidence_refs=evidence,
        )
        return ManagementResult(
            ok=True,
            code=ManagementReasonCode.EXECUTED,
            detail="policy material inspection",
            evidence_refs=evidence,
            payload=payload,
            audit_record_id=audit_id,
        )

    def inspect_sessions(self, operator: str, *, now: str) -> ManagementResult:
        """Inspect session authority state (RBAC ``session.read``)."""
        operation = ManagementOperation.SESSION_SNAPSHOT
        try:
            operator, now = self._operator_and_now(operator, now)
        except ManagementError as error:
            return self._deny(
                now="1970-01-01T00:00:00Z",
                operation=operation,
                operator=str(operator),
                code=ManagementReasonCode.INVALID_INPUT,
                detail=error.detail,
            )
        authorized, _, denial = self._gate(
            operation=operation, operator=operator, now=now
        )
        if denial is not None:
            return denial
        payload = self._session_store.snapshot()
        audit_id = self._record(
            now=now,
            operation=operation,
            operator=operator,
            outcome=AuditOutcome.EXECUTED,
            detail="inspected session authority state (%d session(s))"
            % len(payload.get("sessions", ())),
            evidence_refs=(),
        )
        return ManagementResult(
            ok=True,
            code=ManagementReasonCode.EXECUTED,
            detail="session authority snapshot",
            payload=payload,
            audit_record_id=audit_id,
        )

    def inspect_federation(
        self, operator: str, *, now: str
    ) -> ManagementResult:
        """Inspect federation authority state (RBAC
        ``federation.read``)."""
        operation = ManagementOperation.FEDERATION_SNAPSHOT
        try:
            operator, now = self._operator_and_now(operator, now)
        except ManagementError as error:
            return self._deny(
                now="1970-01-01T00:00:00Z",
                operation=operation,
                operator=str(operator),
                code=ManagementReasonCode.INVALID_INPUT,
                detail=error.detail,
            )
        authorized, _, denial = self._gate(
            operation=operation, operator=operator, now=now
        )
        if denial is not None:
            return denial
        payload = self._federation_store.snapshot()
        audit_id = self._record(
            now=now,
            operation=operation,
            operator=operator,
            outcome=AuditOutcome.EXECUTED,
            detail="inspected federation authority state",
            evidence_refs=(),
        )
        return ManagementResult(
            ok=True,
            code=ManagementReasonCode.EXECUTED,
            detail="federation authority snapshot",
            payload=payload,
            audit_record_id=audit_id,
        )

    def query_telemetry(
        self,
        operator: str,
        *,
        now: str,
        privacy_scope: str,
        purpose: str = "",
        subject_kind: Optional[str] = None,
        subject_ref: Optional[str] = None,
        source_class: Optional[str] = None,
        metric: Optional[str] = None,
        min_confidence_basis_points: Optional[int] = None,
        include_stale: bool = False,
    ) -> ManagementResult:
        """Query telemetry observations (RBAC ``telemetry.read``).

        The PRIVACY FENCE stays entirely with the WORK-026 authority:
        ``privacy_scope`` is required, restricted scopes require an
        explicit purpose, and observations above the scope are
        filtered -- never erroring -- so this surface cannot be used to
        probe the existence of restricted data."""
        operation = ManagementOperation.TELEMETRY_QUERY
        try:
            operator, now = self._operator_and_now(operator, now)
        except ManagementError as error:
            return self._deny(
                now="1970-01-01T00:00:00Z",
                operation=operation,
                operator=str(operator),
                code=ManagementReasonCode.INVALID_INPUT,
                detail=error.detail,
            )
        authorized, _, denial = self._gate(
            operation=operation, operator=operator, now=now
        )
        if denial is not None:
            return denial
        try:
            results = self._telemetry_store.query_observations(
                now=now,
                privacy_scope=privacy_scope,
                purpose=purpose,
                subject_kind=subject_kind,
                subject_ref=subject_ref,
                source_class=source_class,
                metric=metric,
                min_confidence_basis_points=min_confidence_basis_points,
                include_stale=include_stale,
            )
        except TelemetryError as error:
            return self._deny(
                now=now,
                operation=operation,
                operator=operator,
                code=ManagementReasonCode.INVALID_INPUT,
                detail="telemetry authority rejected the query: %s" % error,
            )
        audit_id = self._record(
            now=now,
            operation=operation,
            operator=operator,
            outcome=AuditOutcome.EXECUTED,
            detail="telemetry query (scope %r, purpose %r) returned %d "
            "result(s)" % (privacy_scope, purpose, len(results)),
            evidence_refs=(),
        )
        return ManagementResult(
            ok=True,
            code=ManagementReasonCode.EXECUTED,
            detail="telemetry query",
            payload=results,
            audit_record_id=audit_id,
        )

    def verify_audit(self, operator: str, *, now: str) -> ManagementResult:
        """Verify the audit chain and inspect the ledger head (RBAC
        ``audit.read``).  This is the operational tamper-evidence
        check: the recomputed chain must be intact and the head is the
        value deployments pin externally."""
        operation = ManagementOperation.AUDIT_VERIFY
        try:
            operator, now = self._operator_and_now(operator, now)
        except ManagementError as error:
            return self._deny(
                now="1970-01-01T00:00:00Z",
                operation=operation,
                operator=str(operator),
                code=ManagementReasonCode.INVALID_INPUT,
                detail=error.detail,
            )
        authorized, _, denial = self._gate(
            operation=operation, operator=operator, now=now
        )
        if denial is not None:
            return denial
        verification = self._audit.verify_chain()
        evidence = ("audit-head:%s" % verification.head,) if verification.ok else ()
        audit_id = self._record(
            now=now,
            operation=operation,
            operator=operator,
            outcome=(
                AuditOutcome.EXECUTED if verification.ok else AuditOutcome.FAILED
            ),
            detail="audit chain verification: ok=%s checked=%d head=%s"
            % (verification.ok, verification.checked, verification.head[:16]),
            evidence_refs=evidence,
        )
        return ManagementResult(
            ok=True,
            code=ManagementReasonCode.EXECUTED,
            detail="audit chain verification",
            evidence_refs=evidence,
            payload=verification,
            audit_record_id=audit_id,
        )

    def inspect_roles(self, operator: str, *, now: str) -> ManagementResult:
        """Inspect the RBAC state (catalog + assignment history; RBAC
        ``roles.read``)."""
        operation = ManagementOperation.ROLES_SNAPSHOT
        try:
            operator, now = self._operator_and_now(operator, now)
        except ManagementError as error:
            return self._deny(
                now="1970-01-01T00:00:00Z",
                operation=operation,
                operator=str(operator),
                code=ManagementReasonCode.INVALID_INPUT,
                detail=error.detail,
            )
        authorized, _, denial = self._gate(
            operation=operation, operator=operator, now=now
        )
        if denial is not None:
            return denial
        payload = self._role_store.snapshot()
        audit_id = self._record(
            now=now,
            operation=operation,
            operator=operator,
            outcome=AuditOutcome.EXECUTED,
            detail="inspected RBAC state (%d assignment event(s))"
            % payload["event_count"],
            evidence_refs=(),
        )
        return ManagementResult(
            ok=True,
            code=ManagementReasonCode.EXECUTED,
            detail="RBAC snapshot",
            payload=payload,
            audit_record_id=audit_id,
        )

    # ------------------------------------------------------------------
    # Privileged control operations (RBAC + explicit policy + delegation)
    # ------------------------------------------------------------------

    def create_session(
        self,
        operator: str,
        *,
        now: str,
        source_node_id: str,
        destination_node_id: str,
        topology: Any,
        resources: Any,
        link_metrics: Optional[Mapping[str, Any]] = None,
        intent_digest: str = "",
        resource_refs: Tuple[str, ...] = (),
        federation_domain: str = "",
        credential_active: Optional[bool] = None,
    ) -> ManagementResult:
        """Create a logical session through the FULL genuine chain
        (RBAC ``session.control`` + policy ``session.create``):

        policy decision (fresh, evaluated here) -> genuine WORK-011
        route computation under that decision -> genuine WORK-012
        creation-contract verification.

        Routing snapshot materials (``topology`` graph, ``resources``
        store, ``link_metrics``) are request-supplied INPUTS the
        management layer passes through WITHOUT interpretation: the
        routing context validates them structurally and the routing
        engine computes over them.  Management never recomputes,
        repairs, or replaces a route (WORK-012's rule) and never
        accepts a precomputed route/policy decision (provenance: the
        decision used is the one evaluated inside this call)."""
        operation = ManagementOperation.SESSION_CREATE
        try:
            operator, now = self._operator_and_now(operator, now)
        except ManagementError as error:
            return self._deny(
                now="1970-01-01T00:00:00Z",
                operation=operation,
                operator=str(operator),
                code=ManagementReasonCode.INVALID_INPUT,
                detail=error.detail,
            )
        try:
            context = PolicyContext(
                operation=PolicyOperation.SESSION_CREATE,
                requester_node_id=operator,
                normalized_intent_digest=intent_digest,
                resource_refs=tuple(resource_refs),
                federation_domain=federation_domain,
                credential_active=credential_active,
                evaluation_instant=now,
            )
        except Exception as error:
            return self._deny(
                now=now,
                operation=operation,
                operator=operator,
                code=ManagementReasonCode.INVALID_INPUT,
                detail="policy context construction failed: %s" % error,
            )
        authorized, decision, denial = self._gate(
            operation=operation,
            operator=operator,
            now=now,
            context=context,
        )
        if denial is not None or decision is None:
            return denial  # type: ignore[return-value]
        try:
            routing_context = RoutingContext(
                source_node_id=source_node_id,
                destination_node_id=destination_node_id,
                topology=topology,
                resources=resources,
                evaluation_instant=now,
                policy_decision=decision,
                link_metrics=dict(link_metrics) if link_metrics else {},
            )
        except RoutingError as error:
            return self._deny(
                now=now,
                operation=operation,
                operator=operator,
                code=ManagementReasonCode.INVALID_INPUT,
                detail="routing materials rejected: %s" % error,
                evidence_refs=(decision.decision_id,),
            )
        route_result: RouteEvaluationResult = self._routing_engine.evaluate(
            routing_context
        )
        if (
            not route_result.ok
            or route_result.decision is None
            or route_result.decision.selected is None
        ):
            audit_id = self._record(
                now=now,
                operation=operation,
                operator=operator,
                outcome=AuditOutcome.AUTHORITY_REJECTED,
                detail="routing authority found no permitted route "
                "(code %s: %s)" % (route_result.code, route_result.detail),
                evidence_refs=(decision.decision_id,),
            )
            return ManagementResult(
                ok=False,
                code=ManagementReasonCode.AUTHORITY_REJECTED,
                detail="routing authority rejected: %s" % route_result.detail,
                evidence_refs=(decision.decision_id,),
                audit_record_id=audit_id,
            )
        session_result = self._session_store.create(
            route_result.decision,
            decision,
            source_node_id=source_node_id,
            destination_node_id=destination_node_id,
            creation_instant=now,
            intent_digest=intent_digest,
            actor_reference=operator,
        )
        if not session_result.ok or session_result.session is None:
            audit_id = self._record(
                now=now,
                operation=operation,
                operator=operator,
                outcome=AuditOutcome.AUTHORITY_REJECTED,
                detail="session authority rejected creation (code %s: %s)"
                % (session_result.code, session_result.detail),
                evidence_refs=(decision.decision_id,),
            )
            return ManagementResult(
                ok=False,
                code=ManagementReasonCode.AUTHORITY_REJECTED,
                detail="session authority rejected: %s"
                % session_result.detail,
                evidence_refs=(decision.decision_id,),
                audit_record_id=audit_id,
            )
        session_id = session_result.session.session_id
        audit_id = self._record(
            now=now,
            operation=operation,
            operator=operator,
            outcome=AuditOutcome.EXECUTED,
            detail="session created (%s; route %s) under policy decision %s"
            % (
                session_result.code,
                route_result.decision.decision_id,
                decision.decision_id,
            ),
            evidence_refs=(
                decision.decision_id,
                session_id,
                route_result.decision.decision_id,
            ),
        )
        return ManagementResult(
            ok=True,
            code=ManagementReasonCode.EXECUTED,
            detail="session %s created" % session_id[:24],
            evidence_refs=(decision.decision_id, session_id),
            payload=session_result.session,
            audit_record_id=audit_id,
        )

    def modify_session(
        self,
        operator: str,
        *,
        now: str,
        session_id: str,
        transition: Optional[str] = None,
        suspend: bool = False,
        reason_code: str = "",
        metadata: Tuple[Tuple[str, str], ...] = (),
    ) -> ManagementResult:
        """Modify a session's lifecycle (RBAC ``session.control`` +
        policy ``session.modify``).  Exactly one action per call:
        ``transition`` delegates to the session authority's frozen
        transition table (it validates legality fail-closed);
        ``suspend`` delegates to the explicit suspend operation
        (SUSPENDED is reachable ONLY through it)."""
        operation = ManagementOperation.SESSION_MODIFY
        try:
            operator, now = self._operator_and_now(operator, now)
        except ManagementError as error:
            return self._deny(
                now="1970-01-01T00:00:00Z",
                operation=operation,
                operator=str(operator),
                code=ManagementReasonCode.INVALID_INPUT,
                detail=error.detail,
            )
        if (transition is None) == (not suspend):
            return self._deny(
                now=now,
                operation=operation,
                operator=operator,
                code=ManagementReasonCode.INVALID_INPUT,
                detail="exactly one action is required (transition=<state> "
                "or suspend=True)",
            )
        context = PolicyContext(
            operation=PolicyOperation.SESSION_MODIFY,
            requester_node_id=operator,
            evaluation_instant=now,
        )
        authorized, decision, denial = self._gate(
            operation=operation,
            operator=operator,
            now=now,
            context=context,
        )
        if denial is not None or decision is None:
            return denial  # type: ignore[return-value]
        if suspend:
            session_result = self._session_store.suspend(
                session_id,
                event_instant=now,
                actor_reference=operator,
                reason_code=reason_code,
                metadata=metadata,
            )
        else:
            assert transition is not None
            session_result = self._session_store.transition(
                session_id,
                transition,
                event_instant=now,
                actor_reference=operator,
                reason_code=reason_code,
                metadata=metadata,
            )
        return self._session_outcome(
            operation=operation,
            operator=operator,
            now=now,
            decision=decision,
            result=session_result,
            verb="modified",
        )

    def terminate_session(
        self, operator: str, *, now: str, session_id: str, reason_code: str = ""
    ) -> ManagementResult:
        """Terminate a session (RBAC ``session.control`` + policy
        ``session.terminate``).  The session authority owns teardown
        semantics (terminal states, idempotence, the two-event
        terminating sequence)."""
        operation = ManagementOperation.SESSION_TERMINATE
        try:
            operator, now = self._operator_and_now(operator, now)
        except ManagementError as error:
            return self._deny(
                now="1970-01-01T00:00:00Z",
                operation=operation,
                operator=str(operator),
                code=ManagementReasonCode.INVALID_INPUT,
                detail=error.detail,
            )
        context = PolicyContext(
            operation=PolicyOperation.SESSION_TERMINATE,
            requester_node_id=operator,
            evaluation_instant=now,
        )
        authorized, decision, denial = self._gate(
            operation=operation,
            operator=operator,
            now=now,
            context=context,
        )
        if denial is not None or decision is None:
            return denial  # type: ignore[return-value]
        session_result = self._session_store.terminate(
            session_id,
            event_instant=now,
            actor_reference=operator,
            reason_code=reason_code,
        )
        return self._session_outcome(
            operation=operation,
            operator=operator,
            now=now,
            decision=decision,
            result=session_result,
            verb="terminated",
        )

    def _session_outcome(
        self,
        *,
        operation: str,
        operator: str,
        now: str,
        decision: PolicyDecision,
        result: Any,
        verb: str,
    ) -> ManagementResult:
        """Uniform audited session-authority outcome."""
        if not result.ok or result.session is None:
            audit_id = self._record(
                now=now,
                operation=operation,
                operator=operator,
                outcome=AuditOutcome.AUTHORITY_REJECTED,
                detail="session authority rejected (code %s: %s)"
                % (result.code, result.detail),
                evidence_refs=(decision.decision_id,),
            )
            return ManagementResult(
                ok=False,
                code=ManagementReasonCode.AUTHORITY_REJECTED,
                detail="session authority rejected: %s" % result.detail,
                evidence_refs=(decision.decision_id,),
                audit_record_id=audit_id,
            )
        audit_id = self._record(
            now=now,
            operation=operation,
            operator=operator,
            outcome=AuditOutcome.EXECUTED,
            detail="session %s (%s) under policy decision %s"
            % (verb, result.code, decision.decision_id),
            evidence_refs=(decision.decision_id, result.session.session_id),
        )
        return ManagementResult(
            ok=True,
            code=ManagementReasonCode.EXECUTED,
            detail="session %s (%s)" % (verb, result.code),
            evidence_refs=(decision.decision_id, result.session.session_id),
            payload=result.session,
            audit_record_id=audit_id,
        )

    # -- federation control ------------------------------------------------

    def join_federation(
        self,
        operator: str,
        *,
        now: str,
        local_domain_id: str,
        peer_domain_id: str,
        peer_identity_reference: str,
        declared_scopes: Tuple[str, ...],
        valid_from: str,
        valid_until: str,
        resource_exposure_refs: Tuple[str, ...] = (),
        capability_import_refs: Tuple[str, ...] = (),
        policy_references: Tuple[Tuple[str, int], ...] = (),
    ) -> ManagementResult:
        """Establish a federation relationship (RBAC
        ``federation.control`` + policy ``federation.join``).  The
        policy context mirrors the WORK-015 thin consumer's shape
        (peer domain as ``federation_domain``, exposure refs as
        ``resource_refs``, import refs as capability evidence) -- no
        relationship exists yet to derive one from.  Establishment
        itself is the federation authority's: identity binding, scope
        envelope, and (when policy references are declared) the
        matching tamper-evident ALLOW decision are verified THERE."""
        operation = ManagementOperation.FEDERATION_JOIN
        try:
            operator, now = self._operator_and_now(operator, now)
        except ManagementError as error:
            return self._deny(
                now="1970-01-01T00:00:00Z",
                operation=operation,
                operator=str(operator),
                code=ManagementReasonCode.INVALID_INPUT,
                detail=error.detail,
            )
        context = PolicyContext(
            operation=PolicyOperation.FEDERATION_JOIN,
            requester_node_id=operator,
            federation_domain=peer_domain_id,
            resource_refs=tuple(resource_exposure_refs),
            capability_evidence_refs=tuple(capability_import_refs),
            evaluation_instant=now,
        )
        authorized, decision, denial = self._gate(
            operation=operation,
            operator=operator,
            now=now,
            context=context,
        )
        if denial is not None or decision is None:
            return denial  # type: ignore[return-value]
        fed_result = self._federation_store.establish_relationship(
            local_domain_id,
            peer_domain_id,
            peer_identity_reference=peer_identity_reference,
            declared_scopes=tuple(declared_scopes),
            valid_from=valid_from,
            valid_until=valid_until,
            event_instant=now,
            capability_import_refs=tuple(capability_import_refs),
            resource_exposure_refs=tuple(resource_exposure_refs),
            policy_references=tuple(policy_references),
            policy_decision=decision,
        )
        return self._federation_outcome(
            operation=operation,
            operator=operator,
            now=now,
            decision=decision,
            result=fed_result,
            verb="relationship established",
        )

    def accept_federation_peer(
        self,
        operator: str,
        *,
        now: str,
        relationship_id: str,
        scopes: Tuple[str, ...] = (),
    ) -> ManagementResult:
        """Accept a proposed relationship (RBAC ``federation.control``
        + policy ``federation.accept-peer``).  The policy context is
        built by the GENUINE WORK-015 thin consumer from the
        relationship's own fields; the federation authority enforces
        that acceptance may only NARROW the proposed scope envelope."""
        operation = ManagementOperation.FEDERATION_ACCEPT_PEER
        return self._federation_control(
            operation,
            operator=operator,
            now=now,
            relationship_id=relationship_id,
            policy_operation=PolicyOperation.FEDERATION_ACCEPT_PEER,
            executor=lambda relationship, decision: (
                self._federation_store.accept_relationship(
                    relationship_id,
                    event_instant=now,
                    scopes=tuple(scopes),
                    policy_decision=decision,
                )
            ),
            verb="relationship accepted",
        )

    def export_federation_resource(
        self,
        operator: str,
        *,
        now: str,
        relationship_id: str,
        scope: str,
        valid_from: str,
        valid_until: str,
        evidence_refs: Tuple[str, ...] = (),
    ) -> ManagementResult:
        """Publish a least-authority federation grant (RBAC
        ``federation.control`` + policy ``federation.resource-export``).
        Grant discipline (scope vocabulary, envelope containment,
        anti-escalation) is the federation authority's."""
        operation = ManagementOperation.FEDERATION_RESOURCE_EXPORT
        return self._federation_control(
            operation,
            operator=operator,
            now=now,
            relationship_id=relationship_id,
            policy_operation=PolicyOperation.FEDERATION_RESOURCE_EXPORT,
            executor=lambda relationship, decision: (
                self._federation_store.publish_grant(
                    relationship_id,
                    scope,
                    valid_from=valid_from,
                    valid_until=valid_until,
                    event_instant=now,
                    evidence_refs=tuple(evidence_refs),
                )
            ),
            verb="grant published",
        )

    def import_federation_resource(
        self,
        operator: str,
        *,
        now: str,
        relationship_id: str,
        exchange: Any,
    ) -> ManagementResult:
        """Apply a peer-originated resource exposure exchange (RBAC
        ``federation.control`` + policy ``federation.resource-import``).
        The exchange is request-supplied DATA; the federation authority
        validates determinism, scope grants, and identity binding
        fail-closed -- the management layer never records imports on
        its own."""
        operation = ManagementOperation.FEDERATION_RESOURCE_IMPORT
        return self._federation_control(
            operation,
            operator=operator,
            now=now,
            relationship_id=relationship_id,
            policy_operation=PolicyOperation.FEDERATION_RESOURCE_IMPORT,
            executor=lambda relationship, decision: (
                self._federation_store.apply_exchange(exchange, event_instant=now)
            ),
            verb="import recorded",
        )

    def _federation_control(
        self,
        operation: str,
        *,
        operator: str,
        now: str,
        relationship_id: str,
        policy_operation: str,
        executor: Any,
        verb: str,
    ) -> ManagementResult:
        """Shared federation-control flow: validate inputs -> fetch the
        genuine relationship -> evaluate policy through the genuine
        WORK-015 consumer over every live applicable set (the same
        conservative aggregation) -> delegate to ``executor`` -> audit."""
        try:
            operator, now = self._operator_and_now(operator, now)
        except ManagementError as error:
            return self._deny(
                now="1970-01-01T00:00:00Z",
                operation=operation,
                operator=str(operator),
                code=ManagementReasonCode.INVALID_INPUT,
                detail=error.detail,
            )
        relationship = self._federation_store.get_relationship(relationship_id)
        if relationship is None:
            return self._deny(
                now=now,
                operation=operation,
                operator=operator,
                code=ManagementReasonCode.INVALID_INPUT,
                detail="relationship %r does not exist" % relationship_id,
            )
        # RBAC gate (capability).
        spec = operation_spec(operation)
        capabilities = self._role_store.active_capabilities(operator, now=now)
        if spec.capability not in capabilities:
            return self._deny(
                now=now,
                operation=operation,
                operator=operator,
                code=ManagementReasonCode.RBAC_DENIED,
                detail="operator holds no active role granting %r "
                "(deny-by-default)" % spec.capability,
            )
        # Policy gate through the genuine WORK-015 consumer.
        try:
            applicable = self._policy_store.list_applicable(now)
        except Exception as error:
            return self._deny(
                now=now,
                operation=operation,
                operator=operator,
                code=ManagementReasonCode.INVALID_INPUT,
                detail="policy store rejected the instant: %s" % error,
            )
        if not applicable:
            return self._deny(
                now=now,
                operation=operation,
                operator=operator,
                code=ManagementReasonCode.POLICY_DENIED,
                detail="no applicable policy set at %s (deny-by-default)"
                % now,
            )
        decision: Optional[PolicyDecision] = None
        for policy_set in applicable:
            result = evaluate_federation_operation(
                policy_set,
                relationship,
                policy_operation,
                evaluation_instant=now,
                requester_node_id=operator,
            )
            code = result.code
            if code in _BLOCKING_POLICY_CODES:
                return self._deny(
                    now=now,
                    operation=operation,
                    operator=operator,
                    code=ManagementReasonCode.POLICY_DENIED,
                    detail="policy set %s@%d blocks the operation (code %s: "
                    "%s)"
                    % (
                        policy_set.set_id,
                        policy_set.version,
                        code,
                        result.detail,
                    ),
                    evidence_refs=(
                        result.decision.decision_id,
                    )
                    if result.decision is not None
                    else (),
                )
            if (
                decision is None
                and code == DecisionCode.ALLOW
                and result.decision is not None
                and result.decision.effect == Effect.ALLOW
            ):
                decision = result.decision
        if decision is None:
            return self._deny(
                now=now,
                operation=operation,
                operator=operator,
                code=ManagementReasonCode.POLICY_DENIED,
                detail="no applicable policy set explicitly allows the "
                "operation (deny-by-default)",
            )
        try:
            fed_result = executor(relationship, decision)
        except FederationError as error:
            audit_id = self._record(
                now=now,
                operation=operation,
                operator=operator,
                outcome=AuditOutcome.AUTHORITY_REJECTED,
                detail="federation authority rejected (code %s: %s)"
                % (error.code, error),
                evidence_refs=(decision.decision_id,),
            )
            return ManagementResult(
                ok=False,
                code=ManagementReasonCode.AUTHORITY_REJECTED,
                detail="federation authority rejected: %s" % error,
                evidence_refs=(decision.decision_id,),
                audit_record_id=audit_id,
            )
        return self._federation_outcome(
            operation=operation,
            operator=operator,
            now=now,
            decision=decision,
            result=fed_result,
            verb=verb,
        )

    def _federation_outcome(
        self,
        *,
        operation: str,
        operator: str,
        now: str,
        decision: PolicyDecision,
        result: Any,
        verb: str,
    ) -> ManagementResult:
        """Uniform audited federation-authority outcome."""
        subject = (
            result.relationship.relationship_id
            if getattr(result, "relationship", None) is not None
            else ""
        )
        # evidence refs are always non-empty strings (an unknown/absent
        # subject contributes no ref)
        evidence = tuple(
            ref for ref in (decision.decision_id, subject) if ref
        )
        if not result.ok:
            audit_id = self._record(
                now=now,
                operation=operation,
                operator=operator,
                outcome=AuditOutcome.AUTHORITY_REJECTED,
                detail="federation authority rejected (code %s: %s)"
                % (result.code, result.detail),
                evidence_refs=evidence,
            )
            return ManagementResult(
                ok=False,
                code=ManagementReasonCode.AUTHORITY_REJECTED,
                detail="federation authority rejected: %s" % result.detail,
                evidence_refs=evidence,
                audit_record_id=audit_id,
            )
        audit_id = self._record(
            now=now,
            operation=operation,
            operator=operator,
            outcome=AuditOutcome.EXECUTED,
            detail="%s (%s) under policy decision %s"
            % (verb, result.code, decision.decision_id),
            evidence_refs=evidence,
        )
        return ManagementResult(
            ok=True,
            code=ManagementReasonCode.EXECUTED,
            detail="%s (%s)" % (verb, result.code),
            evidence_refs=evidence,
            payload=result,
            audit_record_id=audit_id,
        )

    # -- telemetry promotion ----------------------------------------------

    def promote_telemetry_observation(
        self,
        operator: str,
        *,
        now: str,
        observation_id: str,
        subject_kind: str,
        subject_ref: str,
        privacy_scope: str,
        source_disclosure: str,
    ) -> ManagementResult:
        """Promote one telemetry observation toward topology authority
        (RBAC ``telemetry.promote`` + policy
        ``telemetry.topology-promote``).

        The promotion scope and privacy disclosure authorization are
        declared UP FRONT in the born-bound descriptor (the WORK-026
        composition-root flow): the engine derives the binding from
        the descriptor with mirror checks, so the decision the
        telemetry authority consumes is BORN carrying its exact scope
        -- and the telemetry authority additionally verifies the
        binding equals the RECORDED observation's own (id, kind, ref),
        that the observation is fresh, and that the privacy boundary
        is honored.  Management adds no disclosure capability of its
        own."""
        operation = ManagementOperation.TELEMETRY_TOPOLOGY_PROMOTE
        try:
            operator, now = self._operator_and_now(operator, now)
        except ManagementError as error:
            return self._deny(
                now="1970-01-01T00:00:00Z",
                operation=operation,
                operator=str(operator),
                code=ManagementReasonCode.INVALID_INPUT,
                detail=error.detail,
            )
        descriptor = {
            "kind": "adcos.telemetry-topology-promotion",
            "operation": PolicyOperation.TELEMETRY_TOPOLOGY_PROMOTE,
            "observation_id": observation_id,
            "subject_kind": subject_kind,
            "subject_ref": subject_ref,
            "privacy_scope": privacy_scope,
            "source_disclosure": source_disclosure,
        }
        try:
            context = PolicyContext(
                operation=PolicyOperation.TELEMETRY_TOPOLOGY_PROMOTE,
                requester_node_id=operator,
                resource_refs=(observation_id, subject_ref),
                evaluation_instant=now,
                extensions=(descriptor,),
            )
        except Exception as error:
            return self._deny(
                now=now,
                operation=operation,
                operator=operator,
                code=ManagementReasonCode.INVALID_INPUT,
                detail="policy context construction failed: %s" % error,
            )
        authorized, decision, denial = self._gate(
            operation=operation,
            operator=operator,
            now=now,
            context=context,
        )
        if denial is not None or decision is None:
            return denial  # type: ignore[return-value]
        try:
            promotion = (
                self._telemetry_store.authorize_topology_promotion(
                    now=now,
                    observation_id=observation_id,
                    policy_decision=decision,
                )
            )
        except TelemetryError as error:
            audit_id = self._record(
                now=now,
                operation=operation,
                operator=operator,
                outcome=AuditOutcome.AUTHORITY_REJECTED,
                detail="telemetry authority rejected the promotion (code "
                "%s: %s)" % (error.reason, error),
                evidence_refs=(decision.decision_id, observation_id),
            )
            return ManagementResult(
                ok=False,
                code=ManagementReasonCode.AUTHORITY_REJECTED,
                detail="telemetry authority rejected: %s" % error,
                evidence_refs=(decision.decision_id, observation_id),
                audit_record_id=audit_id,
            )
        audit_id = self._record(
            now=now,
            operation=operation,
            operator=operator,
            outcome=AuditOutcome.EXECUTED,
            detail="topology promotion authorized for observation %s under "
            "policy decision %s" % (observation_id, decision.decision_id),
            evidence_refs=(decision.decision_id, observation_id),
        )
        return ManagementResult(
            ok=True,
            code=ManagementReasonCode.EXECUTED,
            detail="promotion authorized",
            evidence_refs=(decision.decision_id, observation_id),
            payload=promotion,
            audit_record_id=audit_id,
        )

    # -- RBAC administration ----------------------------------------------

    def assign_role(
        self,
        operator: str,
        *,
        now: str,
        target_operator: str,
        role_id: str,
        revoke: bool = False,
        reason: str = "",
        valid_from: str = "",
        valid_until: str = "",
    ) -> ManagementResult:
        """Grant or revoke an operator role (RBAC ``roles.administer``
        + policy ``management.role-assign`` -- the deliberate WORK-030
        vocabulary extension, deny-by-default like every privileged
        operation).

        Two-key design: the acting operator must hold the administer
        capability AND an explicit policy ALLOW must cover the
        assignment change.  Neither key alone can change RBAC state:
        an operator holding the capability but lacking policy is
        denied, and policy allowing an operation for a subject without
        the capability is denied at the RBAC gate.  The RBAC authority
        (the management plane's own store) validates the transition
        itself (unknown roles, duplicate grants, revoking inactive
        assignments all fail closed) and its history is append-only
        and auditable."""
        operation = ManagementOperation.MANAGEMENT_ROLE_ASSIGN
        try:
            operator, now = self._operator_and_now(operator, now)
            _validate_operator_ref(target_operator, "target_operator")
        except ManagementError as error:
            return self._deny(
                now="1970-01-01T00:00:00Z",
                operation=operation,
                operator=str(operator),
                code=ManagementReasonCode.INVALID_INPUT,
                detail=error.detail,
            )
        context = PolicyContext(
            operation=PolicyOperation.MANAGEMENT_ROLE_ASSIGN,
            requester_node_id=operator,
            evaluation_instant=now,
        )
        authorized, decision, denial = self._gate(
            operation=operation,
            operator=operator,
            now=now,
            context=context,
        )
        if denial is not None or decision is None:
            return denial  # type: ignore[return-value]
        try:
            if revoke:
                event = self._role_store.revoke(
                    target_operator,
                    role_id,
                    instant=now,
                    actor_node_id=operator,
                    reason=reason,
                )
                verb = "role revoked"
            else:
                event = self._role_store.grant(
                    target_operator,
                    role_id,
                    instant=now,
                    actor_node_id=operator,
                    reason=reason,
                    valid_from=valid_from,
                    valid_until=valid_until,
                )
                verb = "role granted"
        except ManagementError as error:
            audit_id = self._record(
                now=now,
                operation=operation,
                operator=operator,
                outcome=AuditOutcome.AUTHORITY_REJECTED,
                detail="RBAC authority rejected the change: %s" % error.detail,
                evidence_refs=(decision.decision_id, target_operator, role_id),
            )
            return ManagementResult(
                ok=False,
                code=ManagementReasonCode.AUTHORITY_REJECTED,
                detail="RBAC authority rejected: %s" % error.detail,
                evidence_refs=(decision.decision_id, target_operator, role_id),
                audit_record_id=audit_id,
            )
        audit_id = self._record(
            now=now,
            operation=operation,
            operator=operator,
            outcome=AuditOutcome.EXECUTED,
            detail="%s: %r -> %r (%s) under policy decision %s"
            % (
                verb,
                target_operator,
                role_id,
                event.event_id[:16],
                decision.decision_id,
            ),
            evidence_refs=(decision.decision_id, event.event_id),
        )
        return ManagementResult(
            ok=True,
            code=ManagementReasonCode.EXECUTED,
            detail="%s: %r -> %r" % (verb, target_operator, role_id),
            evidence_refs=(decision.decision_id, event.event_id),
            payload=event,
            audit_record_id=audit_id,
        )


__all__ = ["ManagementAPI"]
