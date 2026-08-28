"""ADCOS distributed-core manager (WORK-024): the mediated
composition service.

:class:`DistributedCoreManager` is the distributed-core composition
layer of the frozen WORK-024 handoff:

    ADCOS Policy / Routing / Session authority
                     |
                     v
            DistributedCoreManager
              /              \\
     local-breakout          remote-breakout
          |                       |
     adapter/provider       adapter/provider
          |                       |
     W018 IPv6/IP seam       W019 5GC/UPF seam
                            W021 Wi-Fi seam
                            W022 backhaul seam

It COMPOSES existing authorities; it never creates competing ones
(the central W024 rule):

* **Session authority remains WORK-012** -- the manager consults the
  injected read-only :class:`~adapters.distcore.contract.SessionReader`
  fail-closed (unknown/non-secureable sessions are rejected
  caller-side BEFORE any provider is invoked) and never reinterprets
  or replaces a ``session_id``.  Gateway/provider replacement
  preserves the logical session identity: failover is an EXPLICIT
  recorded transition (the old breakout is superseded, the new one
  carries the SAME sacred session_id, and the chain is preserved).
* **Policy authority remains WORK-010** --
  :meth:`apply_policy_decision` consumes a REAL
  ``policy.model.PolicyDecision`` (isinstance-enforced,
  tamper-evident: the decision_id is verified against the decision's
  canonical bytes; an ALLOW effect is required -- a denied decision
  never authorizes a breakout; a future-dated decision is stale).
  The local/remote MODE is the policy determination, recorded as
  DATA on the session-scoped decision record; the manager never
  invents or re-evaluates it.
* **Routing authority remains WORK-011** --
  :meth:`register_path` consumes an ordinary
  ``routing.model.Path`` object as DATA (the ordinary path
  fingerprint IS the breakout path reference; the manager mints NO
  parallel route identity and runs NO second routing authority --
  it never enumerates, scores, or selects paths; the local-first
  choice among registered paths is the caller's, driven by the
  policy-determined mode).
* **IP/5GC state remains adapter-owned** -- the manager mediates
  every provider call through
  :class:`~adapters.distcore.sandbox.SandboxedBreakoutProvider`
  (exception isolation, contract enforcement, deterministic budget)
  and never lets gateway/user-plane state become core authority.

Design mirrors the accepted WORK-022 ``BackhaulManager`` and WORK-023
``MeshManager``:

* **B2 per-record implementation ownership** --
  ``register_provider`` swaps the DEFAULT sandbox only; live
  gateways, allocations, and breakouts keep their OWNING sandbox (a
  provider change never invalidates established logical sessions or
  rewrites canonical state merely because the implementation
  identity changed).
* **ACCESS-STATE-OUT** -- the canonical snapshot carries
  integration-instance state ONLY (breakout bindings with their
  supersedes chain, applied policy decisions, events): gateway
  tables, path content, payloads, and provider internals live behind
  the seam (LOCK-016/017).
* **Transactional failover** -- validation is side-effect free;
  the failover's external confirmation (the new provider breakout)
  is committed only on success, with compensation for a partially
  completed external operation (the new breakout is released
  best-effort if the local commit faults -- the WORK-022 ``managed``
  discipline); the OLD provider breakout is released best-effort
  AFTER the authoritative supersede commits (a partitioned old
  provider never blocks failover -- exactly when failover is
  needed).
* **Honest locality/latency accounting** -- the egress record
  composes the policy-determined locality with the ordinary Path's
  deterministic latency (WORK-011 DATA captured at establishment);
  local traffic stays local (egress through a LOCAL binding never
  touches a remote provider); data-path operations append NO events.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

from protocol.temporal import TemporalError, parse_instant
from policy.model import PolicyDecision
from routing.model import Path as RoutingPath
from routing.model import derive_path_id

from .contract import BreakoutProviderContract, SessionReader
from .errors import DistCoreError, DistCoreReasonCode
from .model import (
    BreakoutDecision,
    BreakoutEgress,
    BreakoutMode,
    BreakoutState,
    DistCoreEvent,
    GatewayDescriptor,
    GatewayEvidence,
    derive_decision_ref,
    derive_gateway_claim_digest,
    derive_integration_id,
)
from .sandbox import (
    DEFAULT_STEP_BUDGET,
    DistCoreOpResult,
    SandboxedBreakoutProvider,
)
from .validation import (
    validate_breakout_mode,
    validate_instant,
    validate_opaque_ref,
    validate_path_ref,
    validate_session_ref,
)

__all__ = ["DistributedCoreManager", "DEFAULT_INTEGRATION_ID"]

#: Default integration instance label.
DEFAULT_INTEGRATION_ID = "distcore-integration"

#: Caller-supplied requirement keys that carry IDENTITY material --
#: rejected fail-closed before the provider is ever invoked (the W024
#: identity invariant enforced caller-side; mirrors the WORK-022/023
#: forbidden-requirements vocabulary).
_FORBIDDEN_REQUIREMENT_KEYS: Tuple[str, ...] = (
    "session_id",
    "session",
    "breakout_ref",
    "binding_id",
    "gateway_ref",
    "path_ref",
    "allocation_ref",
    "decision_ref",
    "flow_id",
    "pdu_session_ref",
)


@dataclass
class _Registration:
    """One registered breakout provider (diagnostic; labels never
    enter canonical state)."""

    label: str
    sandbox: SandboxedBreakoutProvider
    mode: str


class _GatewayRecord:
    """Manager-side record: an admitted gateway and its OWNING
    sandbox + registered mode (B2 extends to gateways, mirroring the
    WORK-022 per-link ownership)."""

    __slots__ = ("candidate", "sandbox", "mode")

    def __init__(
        self,
        candidate: Any,
        sandbox: SandboxedBreakoutProvider,
        mode: str,
    ) -> None:
        self.candidate = candidate
        self.sandbox = sandbox
        self.mode = mode


class _PathRecord:
    """Manager-side record: a registered ordinary WORK-011 Path
    (routing DATA; the path CONTENT stays with the routing authority
    -- the manager holds the object read-only and its fingerprint as
    the reference)."""

    __slots__ = ("path",)

    def __init__(self, path: RoutingPath) -> None:
        self.path = path


class _AllocationRecord:
    """Manager-side record: a breakout-capacity admission and its
    OWNING sandbox (B2)."""

    __slots__ = ("sandbox",)

    def __init__(self, sandbox: SandboxedBreakoutProvider) -> None:
        self.sandbox = sandbox


class _BreakoutRecord:
    """Manager-side record: one breakout binding, its OWNING sandbox
    (B2), and the AUTHORITATIVE chain state (ACTIVE / SUPERSEDED /
    RELEASED with the supersedes/superseded_by links -- the explicit
    transition semantics; gateway replacement never rebinds
    retroactively)."""

    __slots__ = (
        "binding", "sandbox", "mode", "role_class", "decision_ref",
        "path_latency_ms", "state", "supersedes", "superseded_by",
    )

    def __init__(
        self,
        binding: Any,
        sandbox: SandboxedBreakoutProvider,
        mode: str,
        role_class: str,
        decision_ref: str,
        path_latency_ms: int,
    ) -> None:
        self.binding = binding
        self.sandbox = sandbox
        self.mode = mode
        self.role_class = role_class
        self.decision_ref = decision_ref
        self.path_latency_ms = path_latency_ms
        self.state = BreakoutState.ACTIVE
        self.supersedes = ""
        self.superseded_by = ""

    def to_dict(self) -> dict:
        return {
            "session_id": self.binding.session_id,
            "breakout_ref": self.binding.breakout_ref,
            "binding_id": self.binding.binding_id,
            "gateway_ref": self.binding.gateway_ref,
            "path_ref": self.binding.path_ref,
            "mode": self.mode,
            "role_class": self.role_class,
            "decision_ref": self.decision_ref,
            "state": self.state,
            "established_instant": self.binding.established_instant,
            "path_latency_ms": self.path_latency_ms,
            "supersedes": self.supersedes,
            "superseded_by": self.superseded_by,
        }


class DistributedCoreManager:
    """The mediated distributed-core composition service (WORK-024)."""

    def __init__(
        self,
        *,
        integration_id: Optional[str] = None,
        step_budget: int = DEFAULT_STEP_BUDGET,
        session_reader: Optional[SessionReader] = None,
    ) -> None:
        if integration_id is None:
            integration_id = DEFAULT_INTEGRATION_ID
        if not isinstance(integration_id, str) or not integration_id:
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "integration_id must be a non-empty string",
            )
        if isinstance(step_budget, bool) or not isinstance(step_budget, int):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "step_budget must be an integer",
            )
        if session_reader is not None and not isinstance(
            session_reader, SessionReader
        ):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "session_reader must be a SessionReader or None",
            )
        self._integration_id = derive_integration_id(integration_id)
        self._integration_label = integration_id
        self._step_budget = step_budget
        self._session_reader = session_reader
        # Registrations in registration order (diagnostic only).
        self._registrations: List[_Registration] = []
        self._default_sandbox: Optional[SandboxedBreakoutProvider] = None
        # Manager-side records (owning sandboxes per B2).
        self._gateways: Dict[str, _GatewayRecord] = {}
        self._paths: Dict[str, _PathRecord] = {}
        self._allocations: Dict[str, _AllocationRecord] = {}
        self._decisions: Dict[str, BreakoutDecision] = {}
        self._breakouts: Dict[str, _BreakoutRecord] = {}
        self._breakout_refs: Dict[str, str] = {}  # breakout_ref -> binding_id
        # Canonical event history (append-only, deterministic).
        self._events: List[DistCoreEvent] = []
        self._closed = False

    # ------------------------------------------------------------------
    # Caller-side guards
    # ------------------------------------------------------------------

    def _require_not_closed(self) -> None:
        if self._closed:
            raise DistCoreError(
                DistCoreReasonCode.ILLEGAL_STATE,
                "distributed-core integration is closed",
            )

    def _require_now(self, now: str) -> None:
        if not isinstance(now, str) or not now:
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "now must be a non-empty RFC 3339 UTC instant string",
            )
        validate_instant(now, label="now")

    def _require_default(self) -> SandboxedBreakoutProvider:
        if self._default_sandbox is None:
            raise DistCoreError(
                DistCoreReasonCode.ILLEGAL_STATE,
                "no breakout provider registered (register one "
                "first)",
            )
        return self._default_sandbox

    def _require_provider(self, label: str) -> _Registration:
        for registration in self._registrations:
            if registration.label == label:
                return registration
        raise DistCoreError(
            DistCoreReasonCode.ILLEGAL_STATE,
            "no breakout provider registered with label %r" % label,
        )

    def _require_registration_for(
        self, sandbox: SandboxedBreakoutProvider
    ) -> _Registration:
        """The registration owning a sandbox (the registration's
        MODE is the gateway's mode when the default provider is
        selected without an explicit label)."""
        for registration in self._registrations:
            if registration.sandbox is sandbox:
                return registration
        raise DistCoreError(  # pragma: no cover - defensive
            DistCoreReasonCode.ILLEGAL_STATE,
            "sandbox is not registered on this integration",
        )

    def _require_gateway(self, gateway_ref: str) -> _GatewayRecord:
        record = self._gateways.get(gateway_ref)
        if record is None:
            raise DistCoreError(
                DistCoreReasonCode.GATEWAY_UNKNOWN,
                "gateway %r is not admitted" % gateway_ref[:80],
            )
        return record

    def _require_path(self, path_ref: str) -> _PathRecord:
        record = self._paths.get(path_ref)
        if record is None:
            raise DistCoreError(
                DistCoreReasonCode.PATH_UNKNOWN,
                "path %r is not registered" % path_ref[:80],
            )
        return record

    def _require_decision(self, decision_ref: str) -> BreakoutDecision:
        decision = self._decisions.get(decision_ref)
        if decision is None:
            raise DistCoreError(
                DistCoreReasonCode.DECISION_UNKNOWN,
                "breakout decision %r is not applied" % decision_ref[:80],
            )
        return decision

    def _require_breakout(self, breakout_ref: str) -> _BreakoutRecord:
        binding_id = self._breakout_refs.get(breakout_ref)
        if binding_id is None:
            raise DistCoreError(
                DistCoreReasonCode.BREAKOUT_UNKNOWN,
                "breakout %r is not bound" % breakout_ref[:80],
            )
        record = self._breakouts.get(binding_id)
        if record is None:  # pragma: no cover - defensive
            raise DistCoreError(
                DistCoreReasonCode.ILLEGAL_STATE,
                "breakout index is inconsistent",
            )
        return record

    def _resolve_gateway(
        self, path: RoutingPath, mode: str
    ) -> _GatewayRecord:
        """Resolve the gateway the path's destination node addresses
        for the decision's mode (path -> gateway resolution; never a
        path re-derivation -- the WORK-011 authority chose the path,
        the manager only admits it to a gateway role).

        A gateway is a ROLE, not an identity: the path's DESTINATION
        node is the breakout point.  Zero mode-matching gateways on
        that node -> PATH_GATEWAY_MISMATCH (fail closed); more than
        one -> GATEWAY_AMBIGUOUS (fail closed; the composition root
        registers one gateway per node role).
        """
        matches = [
            record
            for record in self._gateways.values()
            if record.candidate.node_id == path.destination_node_id
            and record.mode == mode
        ]
        if not matches:
            raise DistCoreError(
                DistCoreReasonCode.PATH_GATEWAY_MISMATCH,
                "the registered path's destination node does not "
                "address a %r-mode breakout gateway (local-first "
                "composition requires the policy-determined mode to "
                "match the path's breakout point)" % mode,
            )
        if len(matches) > 1:
            raise DistCoreError(
                DistCoreReasonCode.GATEWAY_AMBIGUOUS,
                "the path's destination node addresses more than one "
                "%r-mode gateway (ambiguous breakout point fails "
                "closed)" % mode,
            )
        return matches[0]

    def _reject_identity_smuggling(
        self, requirements: Optional[Mapping[str, Any]]
    ) -> None:
        """Caller-side identity-smuggling guard (fail-closed BEFORE
        the provider is invoked)."""
        if requirements is None:
            return
        if not isinstance(requirements, Mapping):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "requirements must be a mapping or None",
            )
        for key in requirements:
            if key in _FORBIDDEN_REQUIREMENT_KEYS:
                raise DistCoreError(
                    DistCoreReasonCode.ACCESS_SESSION_COLLAPSE,
                    "requirement key %r carries identity material "
                    "(session/gateway/path/breakout identity is never "
                    "caller-suppliable)" % key,
                )

    def _require_secureable_session(self, session_id: str) -> None:
        """Caller-side WORK-012 authorization (fail closed BEFORE
        invoking the provider): the session must exist and be
        secureable through the injected read-only reader."""
        if self._session_reader is None:
            raise DistCoreError(
                DistCoreReasonCode.SESSION_NOT_SECUREABLE,
                "no WORK-012 session authority injected (fail "
                "closed; the distributed core never fabricates "
                "bindability)",
            )
        view = self._session_reader.lookup(session_id)
        if view is None:
            raise DistCoreError(
                DistCoreReasonCode.SESSION_NOT_SECUREABLE,
                "session is unknown to the WORK-012 authority "
                "(fails closed before any provider call)",
            )
        if not view.secureable:
            raise DistCoreError(
                DistCoreReasonCode.SESSION_NOT_SECUREABLE,
                "session is not secureable (WORK-012 state is not "
                "ESTABLISHED/DEGRADED)",
            )

    def _append_event(
        self,
        event_type: str,
        now: str,
        *,
        gateway_ref: str = "",
        breakout_ref: str = "",
        path_ref: str = "",
        detail: str = "",
    ) -> None:
        self._events.append(
            DistCoreEvent(
                event_type=event_type,
                integration_id=self._integration_id,
                instant=now,
                gateway_ref=gateway_ref,
                breakout_ref=breakout_ref,
                path_ref=path_ref,
                detail=detail,
            )
        )

    # ------------------------------------------------------------------
    # Registration and lifecycle
    # ------------------------------------------------------------------

    def register_provider(
        self,
        implementation: BreakoutProviderContract,
        *,
        label: str,
        breakout_mode: str,
        make_default: bool = False,
        now: str,
    ) -> DistCoreOpResult:
        """Register a breakout provider (LOCAL or REMOTE mode)
        behind its own sandbox.

        ``make_default=True`` reassigns the DEFAULT sandbox ONLY --
        live gateways/allocations/breakouts keep their OWNING
        sandboxes (B2 per-record ownership: a provider change never
        invalidates established logical sessions).
        """
        self._require_not_closed()
        self._require_now(now)
        if not isinstance(implementation, BreakoutProviderContract):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "implementation must satisfy the "
                "BreakoutProviderContract ABC",
            )
        if not isinstance(label, str) or not label:
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "label must be a non-empty string",
            )
        validate_breakout_mode(breakout_mode)
        for registration in self._registrations:
            if registration.label == label:
                raise DistCoreError(
                    DistCoreReasonCode.BINDING_EXISTS,
                    "provider label %r is already registered" % label,
                )
        sandbox = SandboxedBreakoutProvider(
            implementation,
            integration_id=self._integration_id,
            step_budget=self._step_budget,
            session_reader=self._session_reader,
        )
        opened = sandbox.open(now)
        if not opened.ok:
            self._append_event("PROVIDER_REGISTER_FAILED", now, detail=label)
            return opened
        health = sandbox.health(now)
        if not health.ok:
            self._append_event("PROVIDER_REGISTER_FAILED", now, detail=label)
            return health
        self._registrations.append(
            _Registration(label, sandbox, breakout_mode)
        )
        if make_default or self._default_sandbox is None:
            self._default_sandbox = sandbox
        # The PROVIDER_REGISTERED event carries NO label and NO mode
        # string (labels/modes are diagnostic, never canonical
        # state).
        self._append_event("PROVIDER_REGISTERED", now)
        return DistCoreOpResult(ok=True)

    def computed_health(self) -> str:
        """The aggregate deterministic health over the registered
        providers (instant-free)."""
        if not self._registrations:
            return "NOT_RUNNING"
        worst = "HEALTHY"
        for registration in self._registrations:
            health = registration.sandbox.computed_health()
            if health == "FAILED":
                return "FAILED"
            if health == "DEGRADED":
                worst = "DEGRADED"
        return worst

    def health(self, *, now: str) -> DistCoreOpResult:
        self._require_not_closed()
        self._require_now(now)
        sandbox = self._require_default()
        result = sandbox.health(now)
        if result.ok:
            self._append_event("OBSERVE_HEALTH", now)
        return result

    def capabilities(self) -> Tuple[str, ...]:
        """The informational capability ladder, derived from MEDIATED
        MANAGER STATE ONLY (LOCK-017: reported, never authoritative).

        ``()`` while no provider is registered; the boundary
        capabilities once one is; the frozen
        ``capability.core.local-breakout`` registry id once a
        LOCAL-mode provider is registered (the core capability this
        module exists to provide); the remote-breakout profile once
        a REMOTE-mode provider is registered.
        """
        if self._default_sandbox is None:
            return ()
        caps: Tuple[str, ...] = (
            "capability.profile.distcore.breakout",
            "capability.profile.distcore.failover",
        )
        modes = {registration.mode for registration in self._registrations}
        if BreakoutMode.LOCAL in modes:
            caps = ("capability.core.local-breakout",) + caps
        if BreakoutMode.REMOTE in modes:
            caps = caps + ("capability.profile.distcore.remote-breakout",)
        return caps

    # ------------------------------------------------------------------
    # Gateway admission (evidence-bearing)
    # ------------------------------------------------------------------

    def register_gateway(
        self,
        *,
        now: str,
        label: Optional[str] = None,
        descriptor: Any,
        evidence: Any,
    ) -> DistCoreOpResult:
        """Admit a breakout gateway on a provider's runtime.

        ``label`` selects the OWNING provider (``None`` = the default
        provider).  The evidence is REQUIRED and its claim digest
        MUST bind to the whole claim (verified caller-side BEFORE
        the provider is invoked; unevidenced registration fails
        closed with ``GATEWAY_UNEVIDENCED`` -- the WORK-018
        GatewayResolver discipline).
        """
        self._require_not_closed()
        self._require_now(now)
        if label is not None:
            registration = self._require_provider(label)
        else:
            registration = self._require_registration_for(
                self._require_default()
            )
        # Caller-side evidence discipline (fail closed BEFORE the
        # provider is invoked).
        if not isinstance(descriptor, GatewayDescriptor):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "descriptor must be a GatewayDescriptor",
            )
        if not isinstance(evidence, GatewayEvidence):
            raise DistCoreError(
                DistCoreReasonCode.GATEWAY_UNEVIDENCED,
                "gateway registration REQUIRES provenance-bearing "
                "GatewayEvidence (a gateway is a role, not an "
                "identity; unevidenced claims fail closed)",
            )
        expected_digest = derive_gateway_claim_digest(descriptor)
        if evidence.claim_digest != expected_digest:
            raise DistCoreError(
                DistCoreReasonCode.GATEWAY_UNEVIDENCED,
                "gateway evidence does not bind to the claim it "
                "vouches for (claim digest mismatch)",
            )
        result = registration.sandbox.register_gateway(
            now, descriptor=descriptor, evidence=evidence
        )
        if result.ok:
            candidate = result.value
            if candidate.gateway_ref in self._gateways:
                from .errors import DistCoreFailure

                return DistCoreOpResult(
                    ok=False,
                    failure=DistCoreFailure(
                        reason_code=DistCoreReasonCode.ILLEGAL_STATE,
                        integration_id=self._integration_id,
                        operation="register_gateway",
                    ),
                    detail="provider returned a duplicate gateway "
                           "ref (rejected; no manager state "
                           "committed)",
                )
            self._gateways[candidate.gateway_ref] = _GatewayRecord(
                candidate, registration.sandbox, registration.mode
            )
            self._append_event(
                "GATEWAY_REGISTERED",
                now,
                gateway_ref=candidate.gateway_ref,
                detail="role_class=%s" % candidate.role_class,
            )
        return result

    def close_gateway(self, *, now: str, gateway_ref: str) -> DistCoreOpResult:
        self._require_not_closed()
        self._require_now(now)
        validate_opaque_ref(gateway_ref, "gateway")
        record = self._require_gateway(gateway_ref)
        result = record.sandbox.close_gateway(now, gateway_ref=gateway_ref)
        if result.ok:
            self._gateways.pop(gateway_ref, None)
            self._append_event("GATEWAY_CLOSED", now, gateway_ref=gateway_ref)
        return result

    # ------------------------------------------------------------------
    # Registered paths (ordinary WORK-011 Paths, consumed as DATA)
    # ------------------------------------------------------------------

    def register_path(self, *, now: str, path: Any) -> DistCoreOpResult:
        """Register an ordinary WORK-011 ``Path`` as a breakout path
        (DATA; the routing authority stays WORK-011 -- this family
        never enumerates, scores, or selects paths).

        The ordinary path fingerprint IS the breakout path
        reference; the family mints NO parallel route identity.  A
        non-feasible path is rejected fail-closed (PATH_INFEASIBLE).
        """
        self._require_not_closed()
        self._require_now(now)
        if not isinstance(path, RoutingPath):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "path must be an ordinary routing.model.Path object "
                "(WORK-011 DATA; the family runs no second routing "
                "authority)",
            )
        # Structural content-binding re-assert (the Path constructor
        # enforces it; the manager re-checks so a hostile subclass
        # cannot smuggle a misbound path into manager state).
        if path.path_id != derive_path_id(
            path.source_node_id,
            path.destination_node_id,
            path.hops,
            path.nodes,
        ):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "path fingerprint does not bind to the path content "
                "(tampered ordinary Path rejected)",
            )
        if not path.feasible:
            raise DistCoreError(
                DistCoreReasonCode.PATH_INFEASIBLE,
                "an infeasible ordinary Path cannot serve a breakout "
                "(fail closed; the routing authority's feasibility "
                "verdict is consumed as DATA)",
            )
        if path.path_id in self._paths:
            raise DistCoreError(
                DistCoreReasonCode.BINDING_EXISTS,
                "path is already registered",
            )
        self._paths[path.path_id] = _PathRecord(path)
        self._append_event(
            "PATH_REGISTERED",
            now,
            path_ref=path.path_id,
            detail="latency_ms=%d" % path.metrics.latency_ms,
        )
        return DistCoreOpResult(ok=True, value=path.path_id)

    # ------------------------------------------------------------------
    # Policy breakout decisions (REAL WORK-010 consumption)
    # ------------------------------------------------------------------

    def apply_policy_decision(
        self,
        *,
        now: str,
        session_id: str,
        policy_decision: PolicyDecision,
        mode: str,
        locality_labels: Tuple[str, ...] = (),
    ) -> DistCoreOpResult:
        """Apply a REAL WORK-010 policy decision as the breakout
        determination for one session (DATA; the manager NEVER
        evaluates policy -- the WORK-010 authority stays sole).

        Fail-closed verification BEFORE anything is recorded:
        ``policy_decision`` must be a genuine
        ``policy.model.PolicyDecision`` whose ``decision_id`` equals
        the SHA-256 of its canonical bytes (tamper-evident), whose
        effect is ALLOW (a denied decision never authorizes a
        breakout -- the distributed core never overrides policy),
        and whose evaluation instant is not in the future (stale
        decisions fail closed).  The MODE is the policy
        determination supplied by the composition root (which read
        it off the policy evaluation, e.g. a locality-domain allow);
        the manager records it on the session-scoped decision
        record and never invents one.
        """
        self._require_not_closed()
        self._require_now(now)
        validate_session_ref(session_id)
        validate_breakout_mode(mode)
        if not isinstance(policy_decision, PolicyDecision):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "policy_decision must be a genuine policy.model."
                "PolicyDecision (the REAL WORK-010 authority "
                "artifact; the distributed core never fabricates "
                "one)",
            )
        # Tamper-evidence: the decision id MUST equal the digest of
        # the decision's own canonical bytes.
        expected_id = hashlib.sha256(
            policy_decision.canonical_bytes()
        ).hexdigest()
        if policy_decision.decision_id != expected_id:
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "policy decision id does not bind to the decision's "
                "canonical bytes (tampered decision rejected; the "
                "distributed core never overrides policy)",
            )
        if policy_decision.effect != "allow":
            raise DistCoreError(
                DistCoreReasonCode.DECISION_DENIED,
                "policy DENIED the operation (a denied decision "
                "never authorizes a breakout; the distributed core "
                "never overrides policy)",
            )
        # Freshness: a future-dated decision is stale (fail closed).
        try:
            evaluated_at = parse_instant(policy_decision.evaluation_instant)
            applied_at = parse_instant(now)
        except TemporalError as error:  # pragma: no cover - shape-checked
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "decision/now instants are not RFC 3339 UTC: %s"
                % type(error).__name__,
            ) from error
        if evaluated_at > applied_at:
            raise DistCoreError(
                DistCoreReasonCode.DECISION_STALE,
                "policy decision is future-dated relative to the "
                "applied instant (stale decision fails closed)",
            )
        if not isinstance(locality_labels, tuple):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "locality_labels must be a tuple of strings",
            )
        decision = BreakoutDecision(
            decision_ref=derive_decision_ref(
                session_id, policy_decision.decision_id, mode, now
            ),
            session_id=session_id,
            policy_decision_id=policy_decision.decision_id,
            policy_effect="allow",
            mode=mode,
            matched_rule_ids=policy_decision.matched_rule_ids,
            locality_labels=locality_labels,
            applied_instant=now,
        )
        if decision.decision_ref in self._decisions:
            raise DistCoreError(
                DistCoreReasonCode.BINDING_EXISTS,
                "this policy determination is already applied for "
                "the session at this instant (deterministic "
                "re-application is rejected; apply at a distinct "
                "instant or with a distinct determination)",
            )
        self._decisions[decision.decision_ref] = decision
        self._append_event(
            "DECISION_APPLIED",
            now,
            detail="mode=%s" % mode,
        )
        return DistCoreOpResult(ok=True, value=decision)

    # ------------------------------------------------------------------
    # Breakout establishment / release
    # ------------------------------------------------------------------

    def establish_breakout(
        self,
        *,
        now: str,
        session_id: str,
        decision_ref: str,
        path_ref: str,
        requirements: Optional[Mapping[str, Any]] = None,
    ) -> DistCoreOpResult:
        """Establish one breakout for a session: the POLICY-determined
        mode + the REGISTERED ordinary path resolve the gateway (the
        path's destination node addresses the mode's breakout
        gateway), and the OWNING provider establishes the binding.

        Fail-closed caller-side BEFORE any provider invocation:
        session secureable through the WORK-012 reader; the decision
        is applied AND session-scoped to THIS session (a decision
        applied for another session can never authorize this one);
        the path is registered; the path's destination addresses the
        decision-mode's gateway.
        """
        self._require_not_closed()
        self._require_now(now)
        validate_session_ref(session_id)
        validate_opaque_ref(decision_ref, "decision")
        validate_path_ref(path_ref)
        self._reject_identity_smuggling(requirements)
        decision = self._require_decision(decision_ref)
        if decision.session_id != session_id:
            raise DistCoreError(
                DistCoreReasonCode.ACCESS_SESSION_COLLAPSE,
                "the breakout decision is scoped to ANOTHER session "
                "(a policy determination applied for one session can "
                "never authorize another)",
            )
        path_record = self._require_path(path_ref)
        gateway_record = self._resolve_gateway(
            path_record.path, decision.mode
        )
        # WORK-012 authorization, fail closed BEFORE the provider.
        self._require_secureable_session(session_id)
        result = gateway_record.sandbox.establish_breakout(
            now,
            session_id=session_id,
            gateway_ref=gateway_record.candidate.gateway_ref,
            path_ref=path_ref,
            requirements=requirements,
        )
        if result.ok:
            binding = result.value
            # Defense-in-depth re-assert (the sandbox already
            # validated the shapes; the manager re-checks the
            # cross-record invariants).
            if binding.breakout_ref in self._breakout_refs:
                from .errors import DistCoreFailure

                return DistCoreOpResult(
                    ok=False,
                    failure=DistCoreFailure(
                        reason_code=DistCoreReasonCode.ILLEGAL_STATE,
                        integration_id=self._integration_id,
                        operation="establish_breakout",
                    ),
                    detail="provider returned a duplicate breakout "
                           "ref (rejected; no manager state "
                           "committed)",
                )
            record = _BreakoutRecord(
                binding=binding,
                sandbox=gateway_record.sandbox,
                mode=decision.mode,
                role_class=gateway_record.candidate.role_class,
                decision_ref=decision.decision_ref,
                path_latency_ms=path_record.path.metrics.latency_ms,
            )
            self._breakouts[binding.binding_id] = record
            self._breakout_refs[binding.breakout_ref] = binding.binding_id
            self._append_event(
                "BREAKOUT_ESTABLISHED",
                now,
                gateway_ref=binding.gateway_ref,
                breakout_ref=binding.breakout_ref,
                path_ref=path_ref,
            )
        return result

    def release_breakout(self, *, now: str, breakout_ref: str) -> DistCoreOpResult:
        self._require_not_closed()
        self._require_now(now)
        validate_opaque_ref(breakout_ref, "breakout")
        record = self._require_breakout(breakout_ref)
        if record.state != BreakoutState.ACTIVE:
            raise DistCoreError(
                DistCoreReasonCode.BREAKOUT_STATE,
                "breakout is not ACTIVE (superseded or released)",
            )
        result = record.sandbox.release_breakout(
            now, breakout_ref=breakout_ref
        )
        if result.ok:
            # The AUTHORITATIVE record is retained as RELEASED (the
            # binding history; the provider-side resource is freed).
            record.state = BreakoutState.RELEASED
            self._append_event(
                "BREAKOUT_RELEASED",
                now,
                breakout_ref=breakout_ref,
                path_ref=record.binding.path_ref,
            )
        return result

    # ------------------------------------------------------------------
    # Egress (the composed locality/latency data path)
    # ------------------------------------------------------------------

    def egress(self, *, now: str, breakout_ref: str, payload: bytes) -> DistCoreOpResult:
        """Send one payload through the breakout's OWNING provider
        (B2) and compose the locality/latency record.

        The locality is the POLICY-determined breakout mode recorded
        on the binding; the latency is the ordinary Path's
        deterministic latency captured at establishment (WORK-011
        DATA).  Data-path operations append NO events (canonical
        lifecycle state is unaffected by payload flow; the honest
        delivery accounting lives in the provider's observation).
        """
        self._require_not_closed()
        self._require_now(now)
        validate_opaque_ref(breakout_ref, "breakout")
        record = self._require_breakout(breakout_ref)
        if record.state != BreakoutState.ACTIVE:
            raise DistCoreError(
                DistCoreReasonCode.BREAKOUT_STATE,
                "breakout is not ACTIVE (superseded or released "
                "breakouts never carry traffic -- no retroactive "
                "rebinding without an explicit transition)",
            )
        result = record.sandbox.egress(
            now, breakout_ref=breakout_ref, payload=payload
        )
        if result.ok:
            outcome = result.value
            egress_record = BreakoutEgress(
                breakout_ref=breakout_ref,
                session_id=record.binding.session_id,
                gateway_ref=record.binding.gateway_ref,
                path_ref=record.binding.path_ref,
                mode=record.mode,
                locality=record.mode,
                path_latency_ms=record.path_latency_ms,
                payload_bytes=outcome.payload_bytes,
                egress_instant=outcome.egress_instant,
            )
            return DistCoreOpResult(ok=True, value=egress_record)
        return result

    # ------------------------------------------------------------------
    # Failover (the explicit gateway/provider transition)
    # ------------------------------------------------------------------

    def failover_binding(
        self,
        *,
        now: str,
        breakout_ref: str,
        target_decision_ref: str,
        target_path_ref: str,
    ) -> DistCoreOpResult:
        """Fail one breakout over to a new gateway/path pair
        (the EXPLICIT transition semantics -- WORK-024 invariant 7).

        Validation is side-effect free and runs to completion BEFORE
        any external effect: the old breakout must be ACTIVE; the
        target decision must be applied, ALLOW-effect, and scoped to
        the SAME sacred session; the target path must be registered
        and its destination must address the target mode's gateway;
        the session must still be secureable.  The external
        confirmation (the NEW provider breakout) is then committed
        ONLY on success -- a failed confirmation leaves the old
        binding INTACT (byte-identical canonical state).  On
        success the old binding is SUPERSEDED (the chain is
        preserved; the session_id NEVER changes), the transition is
        recorded, and the OLD provider breakout is released
        best-effort AFTER the authoritative commit (a partitioned
        old provider never blocks failover -- exactly when failover
        is needed).  A commit-phase fault compensates by releasing
        the NEW breakout best-effort (the WORK-022 managed
        discipline).
        """
        self._require_not_closed()
        self._require_now(now)
        validate_opaque_ref(breakout_ref, "breakout")
        old_record = self._require_breakout(breakout_ref)
        if old_record.state != BreakoutState.ACTIVE:
            raise DistCoreError(
                DistCoreReasonCode.BREAKOUT_STATE,
                "breakout is not ACTIVE (only an active breakout can "
                "fail over)",
            )
        validate_opaque_ref(target_decision_ref, "decision")
        decision = self._require_decision(target_decision_ref)
        session_id = old_record.binding.session_id
        if decision.session_id != session_id:
            raise DistCoreError(
                DistCoreReasonCode.ACCESS_SESSION_COLLAPSE,
                "the target breakout decision is scoped to ANOTHER "
                "session (failover never changes the logical session "
                "identity)",
            )
        validate_path_ref(target_path_ref)
        path_record = self._require_path(target_path_ref)
        gateway_record = self._resolve_gateway(
            path_record.path, decision.mode
        )
        # WORK-012 authorization, fail closed BEFORE the provider.
        self._require_secureable_session(session_id)
        # EXTERNAL CONFIRMATION FIRST: establish the new breakout on
        # the target provider.  A failure returns with the OLD
        # binding INTACT (no manager state was touched).
        result = gateway_record.sandbox.establish_breakout(
            now,
            session_id=session_id,
            gateway_ref=gateway_record.candidate.gateway_ref,
            path_ref=target_path_ref,
            requirements=None,
        )
        if not result.ok:
            return result
        new_binding = result.value
        try:
            if new_binding.breakout_ref in self._breakout_refs:
                raise DistCoreError(
                    DistCoreReasonCode.ILLEGAL_STATE,
                    "provider returned a duplicate breakout ref "
                    "(rejected; no manager state committed)",
                )
            new_record = _BreakoutRecord(
                binding=new_binding,
                sandbox=gateway_record.sandbox,
                mode=decision.mode,
                role_class=gateway_record.candidate.role_class,
                decision_ref=decision.decision_ref,
                path_latency_ms=path_record.path.metrics.latency_ms,
            )
            new_record.supersedes = old_record.binding.binding_id
            # The authoritative commit: the new binding lands ACTIVE,
            # the old binding is SUPERSEDED (chain preserved), the
            # transition is recorded.
            self._breakouts[new_binding.binding_id] = new_record
            self._breakout_refs[new_binding.breakout_ref] = (
                new_binding.binding_id
            )
            old_record.state = BreakoutState.SUPERSEDED
            old_record.superseded_by = new_binding.binding_id
            self._append_event(
                "BREAKOUT_SUPERSEDED",
                now,
                gateway_ref=new_binding.gateway_ref,
                breakout_ref=breakout_ref,
                path_ref=target_path_ref,
                detail="new_breakout=%s" % new_binding.breakout_ref,
            )
        except BaseException:
            # COMPENSATION (the WORK-022 managed discipline): a
            # partially completed external operation is rolled back
            # best-effort -- the NEW provider breakout is released so
            # no provider-side resource leaks; the OLD binding was
            # never touched.
            try:
                gateway_record.sandbox.release_breakout(
                    now, breakout_ref=new_binding.breakout_ref
                )
            except BaseException:  # pragma: no cover - best-effort
                pass  # never mask the primary error
            raise
        # POST-COMMIT best-effort cleanup: release the OLD
        # provider-side breakout.  The authoritative supersede has
        # committed; a failed cleanup (e.g. a crashed old provider)
        # is diagnostic only and never blocks the failover.
        try:
            old_record.sandbox.release_breakout(
                now, breakout_ref=breakout_ref
            )
        except BaseException:  # pragma: no cover - best-effort
            pass  # never masks the committed transition
        return DistCoreOpResult(ok=True, value=new_binding)

    # ------------------------------------------------------------------
    # Observation
    # ------------------------------------------------------------------

    def observe(self, *, now: str, label: Optional[str] = None) -> DistCoreOpResult:
        """Observe one provider's state (``label`` selects the
        provider; ``None`` = the default provider)."""
        self._require_not_closed()
        self._require_now(now)
        if label is not None:
            sandbox = self._require_provider(label).sandbox
        else:
            sandbox = self._require_default()
        result = sandbox.observe(now)
        if result.ok:
            self._append_event("OBSERVED", now)
        return result

    # ------------------------------------------------------------------
    # Breakout-capacity ledger admission
    # ------------------------------------------------------------------

    def allocate(
        self,
        *,
        now: str,
        kind: str,
        quantity_base: int,
        purpose: str,
    ) -> DistCoreOpResult:
        self._require_not_closed()
        self._require_now(now)
        sandbox = self._require_default()
        result = sandbox.allocate(
            now, kind=kind, quantity_base=quantity_base, purpose=purpose
        )
        if result.ok:
            self._allocations[result.value.allocation_ref] = _AllocationRecord(
                sandbox
            )
            self._append_event(
                "ALLOCATED", now, detail=result.value.allocation_ref
            )
        return result

    def release(self, *, now: str, allocation_ref: str) -> DistCoreOpResult:
        self._require_not_closed()
        self._require_now(now)
        validate_opaque_ref(allocation_ref, "alloc")
        record = self._allocations.get(allocation_ref)
        if record is None:
            raise DistCoreError(
                DistCoreReasonCode.ALLOCATION_UNKNOWN,
                "allocation %r is unknown" % allocation_ref[:80],
            )
        result = record.sandbox.release(now, allocation_ref=allocation_ref)
        if result.ok:
            self._allocations.pop(allocation_ref, None)
            self._append_event("RELEASED", now, detail=allocation_ref)
        return result

    # ------------------------------------------------------------------
    # Canonical state
    # ------------------------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        """The canonical integration-instance state (breakout
        bindings with their supersedes chain, applied policy
        decisions, and events ONLY -- never gateway/user-plane
        state, never path content, never implementation labels,
        never payloads: ACCESS-STATE-OUT)."""
        return {
            "integration_id": self._integration_id,
            "closed": self._closed,
            "breakout_count": sum(
                1
                for record in self._breakouts.values()
                if record.state == BreakoutState.ACTIVE
            ),
            "breakouts": [
                self._breakouts[binding_id].to_dict()
                for binding_id in sorted(self._breakouts.keys())
            ],
            "decisions": [
                self._decisions[decision_ref].to_dict()
                for decision_ref in sorted(self._decisions.keys())
            ],
            "events": [event.to_dict() for event in self._events],
        }

    def to_canonical_bytes(self) -> bytes:
        from .serialization import to_canonical_bytes as _bytes

        return _bytes(self.snapshot())

    def content_digest(self) -> str:
        return hashlib.sha256(self.to_canonical_bytes()).hexdigest()

    def diagnostic_state(self) -> Dict[str, Any]:
        """Diagnostic surface (implementation labels/modes/healths,
        record counts) -- NEVER canonical state (B2: labels are
        diagnostic)."""
        return {
            "integration_id": self._integration_id,
            "integration_label": self._integration_label,
            "computed_health": self.computed_health(),
            "registrations": [
                {
                    "label": registration.label,
                    "mode": registration.mode,
                    "health": registration.sandbox.computed_health(),
                }
                for registration in self._registrations
            ],
            "gateway_count": len(self._gateways),
            "path_count": len(self._paths),
            "decision_count": len(self._decisions),
            "breakout_count": len(self._breakouts),
            "allocation_count": len(self._allocations),
        }

    # ------------------------------------------------------------------
    # Properties and teardown
    # ------------------------------------------------------------------

    @property
    def integration_id(self) -> str:
        return self._integration_id

    @property
    def breakout_count(self) -> int:
        """The number of ACTIVE breakouts (superseded/released
        bindings remain in the authoritative history)."""
        return sum(
            1
            for record in self._breakouts.values()
            if record.state == BreakoutState.ACTIVE
        )

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        """Close the integration (caller-side fail-closed; subsequent
        operations reject)."""
        self._closed = True
