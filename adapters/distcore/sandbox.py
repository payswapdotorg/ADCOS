"""ADCOS distributed-core sandbox (WORK-024): the failure-isolation
boundary.

:class:`SandboxedBreakoutProvider` mediates EVERY call from the
manager to a breakout-provider implementation.  The mediator
guarantees, mechanically (mirroring the WORK-016 adapter, WORK-017
transport, WORK-018 IP integration, WORK-019 5G Core integration,
WORK-021 Wi-Fi access, WORK-022 backhaul, and WORK-023 mesh
sandboxes):

1. **Exception isolation** -- any exception the implementation raises
   (``Exception`` AND ``BaseException``: a ``SystemExit`` from a
   vendor gateway daemon crashes the operation, never the manager)
   is converted into a typed
   :class:`adapters.distcore.errors.DistCoreFailure` VALUE.
   Distributed-core-side faults never propagate into core callers as
   exceptions (R5 failure-isolation invariant).  Exception MESSAGE
   TEXT is deliberately NOT captured (LOCK-023: an implementation
   cannot leak gateway management credentials, UPF N4 shared keys,
   or N3IWF IPsec/IKE material through failure diagnostics); only
   the exception CLASS NAME crosses, as a vocabulary-free fact.

2. **Contract enforcement** -- every return value is validated
   against the frozen contract shape BEFORE it can enter manager
   state.  A non-contract return is a ``CONTRACT_VIOLATION`` failure
   and is discarded; it can never be stored, keyed, or echoed.  A
   binding whose ref embeds WORK-012 session material (the W024
   identity invariant: session_id != gateway identity != path
   identity != breakout identity != allocation identity) is rejected
   at the seam with the value discarded.  A gateway candidate whose
   ref is not the content-derived gateway identity, or a decision
   whose ref is not the content-derived session-scoped decision ref,
   is rejected at the seam (tamper-evident content binding; mirrors
   the WORK-022 PR #23 / WORK-023 seam disciplines).

3. **Deterministic budget** -- every operation is charged against
   the frozen :data:`STEP_CHARGES` table through the least-authority
   :class:`~adapters.distcore.contract.BreakoutContext`; a hung or
   overrunning implementation exhausts the budget and fails closed
   (no wall clock exists anywhere in this layer).

NOTE (the W024 authority path, architect-anchored): the sandbox
exposes NO capability-escape surface of any kind onto the
implementation -- no generic attribute reach-around, no data-path
accessor, no private-attribute hook of any kind.  The ONLY things
that cross this seam are the 11 mediated operations above (charged,
contract-validated, exception-isolated) and the LEAST-AUTHORITY
BreakoutContext facade.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable, Mapping, Optional

from .contract import (
    BreakoutContext,
    BreakoutProviderContract,
    SessionReader,
)
from .errors import DistCoreError, DistCoreFailure, DistCoreReasonCode
from .model import (
    BreakoutAllocation,
    BreakoutBinding,
    DistCoreObservation,
    EgressOutcome,
    GatewayCandidate,
    LinkMetricName,
    derive_binding_id,
    derive_gateway_ref,
)
from .validation import (
    assert_ref_session_separation,
    validate_opaque_ref,
)

# The contract module defines _BudgetExhausted privately; re-import it
# here so the sandbox can catch it.  (Mirrors the WORK-018/019/021/
# 022/023 sandboxes importing _BudgetExhausted from their contract
# modules.)
from .contract import _BudgetExhausted  # noqa: E402

__all__ = [
    "DistCoreOpResult",
    "SandboxedBreakoutProvider",
    "STEP_CHARGES",
    "DEFAULT_STEP_BUDGET",
    "FAILURE_THRESHOLD_DEGRADED",
    "FAILURE_THRESHOLD_FAILED",
]

#: Default deterministic step budget (mirrors WORK-016/018/019/021/
#: 022/023).
DEFAULT_STEP_BUDGET = 10000

#: Deterministic health thresholds (mirrors WORK-016/018/019/021/022/
#: 023).
FAILURE_THRESHOLD_DEGRADED = 2
FAILURE_THRESHOLD_FAILED = 5

#: The frozen deterministic step-charge table for the 11
#: :class:`~adapters.distcore.contract.BreakoutProviderContract`
#: operations (op -> cost).  This is the family's PINNABLE surface:
#: the selftest pins this table byte-for-byte, and implementations
#: charge these costs against the
#: :class:`~adapters.distcore.contract.BreakoutContext` budget at op
#: entry (mirroring the WORK-023 convention).
STEP_CHARGES: Mapping[str, int] = MappingProxyType(
    {
        "open": 4,
        "register_gateway": 8,
        "close_gateway": 4,
        "allocate": 6,
        "release": 3,
        "establish_breakout": 8,
        "release_breakout": 3,
        "egress": 4,
        "observe": 2,
        "health": 1,
        "close": 4,
    }
)


class _ContractViolation:
    """Internal sentinel: the implementation returned a value that
    does not satisfy the frozen contract shape.  The sandbox discards
    the value (never stores, keys, or echoes it) and reports a
    ``CONTRACT_VIOLATION`` failure."""

    __slots__ = ("detail",)

    def __init__(self, detail: str) -> None:
        self.detail = detail


@dataclass
class DistCoreOpResult:
    """The mediated result of a distributed-core operation.

    * ``ok=True``: ``value`` carries the validated contract return.
    * ``ok=False``: ``failure`` carries the typed, isolated
      :class:`DistCoreFailure` (never an exception).  ``detail`` is a
      generic, secret-free diagnostic string (exception message text
      is NEVER captured -- LOCK-023).

    Caller-side state errors (unknown gateway/path/breakout/decision,
    policy-denied or stale decisions, capacity exhaustion) RAISE
    :class:`DistCoreError` from the manager; provider-side faults
    RETURN this typed value.
    """

    ok: bool
    value: Any = None
    failure: Optional[DistCoreFailure] = None
    detail: str = ""

    @property
    def reason(self) -> str:
        return self.failure.reason_code if self.failure is not None else ""

    def __bool__(self) -> bool:
        return self.ok


class SandboxedBreakoutProvider:
    """The failure-isolation mediator for a breakout-provider
    implementation.

    Constructed with a :class:`BreakoutProviderContract`
    implementation (NOT ``hasattr`` duck-typed -- ``isinstance``
    enforced) and the least-authority readers the manager injects.
    Every public method builds a fresh :class:`BreakoutContext`,
    delegates to the implementation through :meth:`_mediate`, and
    returns a :class:`DistCoreOpResult`.
    """

    def __init__(
        self,
        implementation: BreakoutProviderContract,
        *,
        integration_id: str,
        step_budget: int = DEFAULT_STEP_BUDGET,
        session_reader: Optional[SessionReader] = None,
    ) -> None:
        if not isinstance(implementation, BreakoutProviderContract):
            raise DistCoreError(
                DistCoreReasonCode.INVALID_INPUT,
                "implementation must satisfy the "
                "BreakoutProviderContract ABC (isinstance enforced; "
                "no hasattr duck-typing)",
            )
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
        self._implementation = implementation
        self._integration_id = integration_id
        self._step_budget = step_budget
        self._session_reader = session_reader
        # Health accounting.
        self._consecutive_failures = 0
        self._total_failures = 0
        self._total_contract_violations = 0
        self._open = False

    # ------------------------------------------------------------------
    # Least-authority context construction
    # ------------------------------------------------------------------

    def _context(self, now: str) -> BreakoutContext:
        return BreakoutContext(
            integration_id=self._integration_id,
            instant=now,
            step_budget=self._step_budget,
            session_reader=self._session_reader,
        )

    # ------------------------------------------------------------------
    # Universal mediation guard
    # ------------------------------------------------------------------

    def _mediate(
        self,
        now: str,
        operation: str,
        fn: Callable[[BreakoutContext], Any],
        *,
        validate: Callable[[Any], Any],
    ) -> DistCoreOpResult:
        """Build a fresh context, delegate to ``fn``, validate the
        return, and convert every exception (including
        ``BaseException``) into an isolated failure value."""
        context = self._context(now)
        try:
            value = fn(context)
        except _BudgetExhausted:
            self._record_failure()
            return DistCoreOpResult(
                ok=False,
                failure=DistCoreFailure(
                    reason_code=DistCoreReasonCode.BUDGET_EXHAUSTED,
                    integration_id=self._integration_id,
                    operation=operation,
                ),
                detail="distributed-core operation exceeded its "
                       "deterministic step budget (hang model); no "
                       "wall clock is consulted",
            )
        except DistCoreError as exc:
            # The reason CODE is safe (a vocabulary token).  The
            # exception MESSAGE TEXT (exc.detail) is deliberately NOT
            # captured -- an implementation cannot leak gateway
            # management, UPF N4, or N3IWF IPsec key material through
            # failure diagnostics (LOCK-023).
            self._record_failure()
            return DistCoreOpResult(
                ok=False,
                failure=DistCoreFailure(
                    reason_code=exc.reason,
                    integration_id=self._integration_id,
                    operation=operation,
                ),
                detail="implementation raised DistCoreError (reason=%s); "
                       "exception message text not captured" % exc.reason,
            )
        except BaseException as exc:  # full isolation: nothing crosses
            self._record_failure()
            return DistCoreOpResult(
                ok=False,
                failure=DistCoreFailure(
                    reason_code=DistCoreReasonCode.DISTCORE_FAILURE,
                    integration_id=self._integration_id,
                    operation=operation,
                    exception_class_name=type(exc).__name__,
                ),
                detail="implementation raised %s (message text not "
                       "captured; exception is fully isolated)"
                       % type(exc).__name__,
            )
        validated = validate(value)
        if isinstance(validated, _ContractViolation):
            self._record_failure(violation=True)
            return DistCoreOpResult(
                ok=False,
                failure=DistCoreFailure(
                    reason_code=DistCoreReasonCode.CONTRACT_VIOLATION,
                    integration_id=self._integration_id,
                    operation=operation,
                ),
                detail=validated.detail,
            )
        self._record_success()
        return DistCoreOpResult(ok=True, value=validated)

    # ------------------------------------------------------------------
    # Return-shape validators (the frozen contract surface)
    # ------------------------------------------------------------------

    def _validate_nothing(self, value: Any) -> Any:
        if value is not None:
            return _ContractViolation("operation must return None")
        return value

    def _validate_gateway_candidate(self, value: Any) -> Any:
        if not isinstance(value, GatewayCandidate):
            return _ContractViolation(
                "register_gateway must return a GatewayCandidate"
            )
        # Structural content-derivation re-assert (the model enforces
        # at construction; the seam re-checks structurally so a
        # hostile subclass cannot smuggle a misbound gateway identity
        # into manager state).
        try:
            validate_opaque_ref(value.gateway_ref, "gateway")
        except DistCoreError:
            return _ContractViolation(
                "register_gateway returned a malformed gateway_ref; "
                "value discarded"
            )
        if value.gateway_ref != derive_gateway_ref(
            value.name, value.gateway_id, value.node_id, value.role_class
        ):
            return _ContractViolation(
                "register_gateway returned a gateway_ref that is not "
                "the content-derived derive_gateway_ref(name, "
                "gateway_id, node_id, role_class) (tampered gateway "
                "identity); value discarded"
            )
        return value

    def _validate_allocation(self, value: Any) -> Any:
        if not isinstance(value, BreakoutAllocation):
            return _ContractViolation(
                "allocate must return a BreakoutAllocation"
            )
        return value

    def _validate_binding(self, value: Any) -> Any:
        if not isinstance(value, BreakoutBinding):
            return _ContractViolation(
                "establish_breakout must return a BreakoutBinding"
            )
        # W024 identity invariant, re-asserted at the seam: the
        # breakout ref must never embed WORK-012 session material
        # (the model enforces this at construction; the seam
        # re-checks structurally so a hostile subclass cannot smuggle
        # a collapsed identity into manager state).  The ref grammar
        # is checked FIRST so the separation re-assert below only
        # ever sees ref-shaped input.
        try:
            validate_opaque_ref(value.breakout_ref, "breakout")
            assert_ref_session_separation(
                value.breakout_ref, value.session_id
            )
            validate_opaque_ref(value.gateway_ref, "gateway")
        except DistCoreError:
            return _ContractViolation(
                "establish_breakout returned a binding whose refs are "
                "malformed or embed session identity (W024 identity "
                "invariant); value discarded"
            )
        # Structural content-derivation re-assert (mirrors the
        # WORK-022 PR #23 and WORK-023 disciplines): the binding key
        # MUST equal derive_binding_id(session_id, breakout_ref) -- a
        # hostile subclass cannot smuggle a fabricated binding key
        # into manager state even by bypassing the model constructor.
        if value.binding_id != derive_binding_id(
            value.session_id, value.breakout_ref
        ):
            return _ContractViolation(
                "establish_breakout returned a binding whose "
                "binding_id is not the content-derived "
                "derive_binding_id(session_id, breakout_ref) "
                "(tampered binding key); value discarded"
            )
        return value

    def _validate_egress(self, value: Any) -> Any:
        if not isinstance(value, EgressOutcome):
            return _ContractViolation(
                "egress must return an EgressOutcome"
            )
        try:
            validate_opaque_ref(value.breakout_ref, "breakout")
            validate_opaque_ref(value.gateway_ref, "gateway")
        except DistCoreError:
            return _ContractViolation(
                "egress returned a malformed ref; value discarded"
            )
        return value

    def _validate_observation(self, value: Any) -> Any:
        if not isinstance(value, DistCoreObservation):
            return _ContractViolation(
                "observe must return a DistCoreObservation"
            )
        # Generic metric vocabulary re-assert (mirrors the WORK-022/
        # 023 discipline): every sample metric must be the generic
        # WORK-016 link-metric vocabulary.
        valid_metrics = LinkMetricName.values()
        for sample in value.samples:
            name = sample[0]
            if name not in valid_metrics:
                return _ContractViolation(
                    "observe returned a sample metric %r outside the "
                    "generic WORK-016 link-metric vocabulary %s "
                    "(technology-specific counters stay inside "
                    "implementations); value discarded"
                    % (name, list(valid_metrics))
                )
        return value

    def _validate_health(self, value: Any) -> Any:
        if not isinstance(value, str) or value not in (
            "HEALTHY", "DEGRADED", "FAILED", "NOT_RUNNING",
        ):
            return _ContractViolation(
                "health must return HEALTHY/DEGRADED/FAILED/NOT_RUNNING"
            )
        return value

    # ------------------------------------------------------------------
    # Health accounting
    # ------------------------------------------------------------------

    def _record_failure(self, *, violation: bool = False) -> None:
        self._consecutive_failures += 1
        self._total_failures += 1
        if violation:
            self._total_contract_violations += 1

    def _record_success(self) -> None:
        self._consecutive_failures = 0

    def computed_health(self) -> str:
        """The deterministic effective health from mediated
        outcomes."""
        if not self._open:
            return "NOT_RUNNING"
        if self._consecutive_failures >= FAILURE_THRESHOLD_FAILED:
            return "FAILED"
        if self._consecutive_failures >= FAILURE_THRESHOLD_DEGRADED:
            return "DEGRADED"
        return "HEALTHY"

    # ------------------------------------------------------------------
    # Public mediated operations (the 11 contract operations)
    # ------------------------------------------------------------------

    def open(self, now: str) -> DistCoreOpResult:
        result = self._mediate(
            now, "open", lambda ctx: self._implementation.open(ctx),
            validate=self._validate_nothing,
        )
        if result.ok:
            self._open = True
        return result

    def register_gateway(
        self,
        now: str,
        *,
        descriptor: Any,
        evidence: Any,
    ) -> DistCoreOpResult:
        return self._mediate(
            now, "register_gateway",
            lambda ctx: self._implementation.register_gateway(
                ctx, descriptor=descriptor, evidence=evidence,
            ),
            validate=self._validate_gateway_candidate,
        )

    def close_gateway(self, now: str, *, gateway_ref: str) -> DistCoreOpResult:
        return self._mediate(
            now, "close_gateway",
            lambda ctx: self._implementation.close_gateway(
                ctx, gateway_ref=gateway_ref,
            ),
            validate=self._validate_nothing,
        )

    def allocate(
        self, now: str, *, kind: str, quantity_base: int, purpose: str,
    ) -> DistCoreOpResult:
        return self._mediate(
            now, "allocate",
            lambda ctx: self._implementation.allocate(
                ctx, kind=kind, quantity_base=quantity_base,
                purpose=purpose,
            ),
            validate=self._validate_allocation,
        )

    def release(self, now: str, *, allocation_ref: str) -> DistCoreOpResult:
        return self._mediate(
            now, "release",
            lambda ctx: self._implementation.release(
                ctx, allocation_ref=allocation_ref,
            ),
            validate=self._validate_nothing,
        )

    def establish_breakout(
        self,
        now: str,
        *,
        session_id: str,
        gateway_ref: str,
        path_ref: str,
        requirements: Optional[Mapping[str, Any]] = None,
    ) -> DistCoreOpResult:
        return self._mediate(
            now, "establish_breakout",
            lambda ctx: self._implementation.establish_breakout(
                ctx, session_id=session_id, gateway_ref=gateway_ref,
                path_ref=path_ref, requirements=requirements,
            ),
            validate=self._validate_binding,
        )

    def release_breakout(
        self, now: str, *, breakout_ref: str
    ) -> DistCoreOpResult:
        return self._mediate(
            now, "release_breakout",
            lambda ctx: self._implementation.release_breakout(
                ctx, breakout_ref=breakout_ref,
            ),
            validate=self._validate_nothing,
        )

    def egress(
        self, now: str, *, breakout_ref: str, payload: bytes,
    ) -> DistCoreOpResult:
        return self._mediate(
            now, "egress",
            lambda ctx: self._implementation.egress(
                ctx, breakout_ref=breakout_ref, payload=payload,
            ),
            validate=self._validate_egress,
        )

    def observe(self, now: str) -> DistCoreOpResult:
        return self._mediate(
            now, "observe",
            lambda ctx: self._implementation.observe(ctx),
            validate=self._validate_observation,
        )

    def health(self, now: str) -> DistCoreOpResult:
        return self._mediate(
            now, "health", lambda ctx: self._implementation.health(),
            validate=self._validate_health,
        )

    # NOTE (the W024 authority path, architect-anchored): the sandbox
    # exposes NO capability-escape surface of any kind onto the
    # implementation -- no generic attribute reach-around, no
    # data-path accessor, no private-attribute hook of any kind.  The
    # ONLY things that cross this seam are the 11 mediated operations
    # above (charged, contract-validated, exception-isolated) and the
    # LEAST-AUTHORITY BreakoutContext facade.

    # ------------------------------------------------------------------
    # Diagnostic surface (NOT canonical public state; B2)
    # ------------------------------------------------------------------

    def diagnostic_state(self) -> dict:
        return {
            "implementation_label": self._implementation.label,
            "computed_health": self.computed_health(),
            "consecutive_failures": self._consecutive_failures,
            "total_failures": self._total_failures,
            "total_contract_violations": self._total_contract_violations,
        }
