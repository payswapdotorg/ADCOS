"""ADCOS service registry / edge compute execution sandbox
(WORK-025).

The least-authority execution mediator (mirrors the WORK-024
``SandboxedBreakoutProvider`` discipline):

- every provider operation runs behind a fresh immutable
  :class:`~services.contract.ServiceContext` with a fixed step
  budget (deterministic resource accounting);
- provider exceptions NEVER propagate into the registry or core
  callers: they are converted into typed
  :class:`~services.errors.ServiceFailure` values carrying only the
  frozen reason code and -- at most -- the exception CLASS name
  (LOCK-023: no exception message text crosses the boundary);
- return shapes are contract-validated (isinstance + ref grammars +
  content-derived ref re-derivation) so a provider cannot smuggle a
  malformed admission, outcome, or observation into canonical state;
- consecutive failure accounting drives a computed health ladder
  (HEALTHY -> DEGRADED -> FAILED); the sandbox is closed until
  ``open`` succeeds.

A failing provider therefore degrades the service layer's execution
seam deterministically, and never corrupts authoritative service
state.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable, Mapping, Optional

from .contract import (
    _BudgetExhausted,
    DEFAULT_STEP_BUDGET,
    ExecutionProviderContract,
    ServiceContext,
    SessionReader,
)
from .errors import ServiceError, ServiceFailure, ServiceReasonCode
from .model import (
    AdmissionState,
    ExecutionOutcome,
    ServiceAdmission,
    ServiceObservation,
    derive_execution_ref,
)
from .validation import (
    assert_ref_session_separation,
    validate_opaque_ref,
)

#: Frozen per-operation step charges (byte-pinned by the WORK-025
#: selftest; implementations charge ``context.charge(...)`` at op
#: entry).
STEP_CHARGES: Mapping[str, int] = MappingProxyType({
    "open": 4,
    "admit": 8,
    "execute": 6,
    "release": 3,
    "observe": 2,
    "health": 1,
    "close": 4,
})

#: Consecutive provider failures at or above which the sandbox
#: reports DEGRADED.
FAILURE_THRESHOLD_DEGRADED = 2

#: Consecutive provider failures at or above which the sandbox
#: reports FAILED.
FAILURE_THRESHOLD_FAILED = 5

#: The frozen provider health vocabulary.
HEALTH_VALUES = ("HEALTHY", "DEGRADED", "FAILED", "NOT_RUNNING")


class _ContractViolation(Exception):
    """Internal sentinel: a provider returned a value that violates
    the execution contract.  The offending value is deliberately
    discarded (never stored, never echoed)."""

    __slots__ = ("detail",)

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


@dataclass
class ServiceOpResult:
    """The mediated operation result: either ``ok=True`` with the
    contract-validated ``value``, or ``ok=False`` with a typed
    ``failure`` (never both, never neither)."""

    ok: bool
    value: Any = None
    failure: Optional[ServiceFailure] = None
    detail: str = ""

    @property
    def reason(self) -> str:
        if self.failure is None:
            return ""
        return self.failure.reason_code

    def __bool__(self) -> bool:
        return self.ok


def _validate_nothing(value: Any) -> None:
    if value is not None:
        raise _ContractViolation(
            "operation must return None (got %s)" % (type(value).__name__,)
        )


def _validate_admission(value: Any) -> ServiceAdmission:
    if not isinstance(value, ServiceAdmission):
        raise _ContractViolation(
            "admit must return a ServiceAdmission (got %s)"
            % (type(value).__name__,)
        )
    validate_opaque_ref(value.admission_ref, "admission")
    validate_opaque_ref(value.service_ref, "service")
    if value.state != AdmissionState.ACTIVE:
        raise _ContractViolation(
            "a fresh admission must be in the active state (got %r)"
            % (value.state,)
        )
    if value.session_id:
        assert_ref_session_separation(value.admission_ref, value.session_id)
    return value


def _validate_outcome(value: Any) -> ExecutionOutcome:
    if not isinstance(value, ExecutionOutcome):
        raise _ContractViolation(
            "execute must return an ExecutionOutcome (got %s)"
            % (type(value).__name__,)
        )
    validate_opaque_ref(value.admission_ref, "admission")
    validate_opaque_ref(value.service_ref, "service")
    validate_opaque_ref(value.execution_ref, "execution")
    expected = derive_execution_ref(
        value.admission_ref, value.executed_at, value.request_digest
    )
    if value.execution_ref != expected:
        raise _ContractViolation(
            "execution_ref does not bind to the outcome content "
            "(tampered or miscomputed outcome rejected)"
        )
    return value


def _validate_observation(value: Any) -> ServiceObservation:
    if not isinstance(value, ServiceObservation):
        raise _ContractViolation(
            "observe must return a ServiceObservation (got %s)"
            % (type(value).__name__,)
        )
    return value


def _validate_health(value: Any) -> str:
    if not isinstance(value, str) or value not in HEALTH_VALUES:
        raise _ContractViolation(
            "health must be one of %s (got %r)" % (HEALTH_VALUES, value)
        )
    return value


class SandboxedExecutionProvider:
    """The universal least-authority mediator over an
    :class:`~services.contract.ExecutionProviderContract`
    implementation."""

    def __init__(
        self,
        implementation: ExecutionProviderContract,
        *,
        integration_id: str,
        step_budget: int = DEFAULT_STEP_BUDGET,
        session_reader: Optional[SessionReader] = None,
    ) -> None:
        if not isinstance(implementation, ExecutionProviderContract):
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "implementation must implement the "
                "ExecutionProviderContract ABC (isinstance-enforced; no "
                "hasattr duck-typing)",
            )
        if not isinstance(integration_id, str) or not integration_id:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "integration_id must be a non-empty str",
            )
        if isinstance(step_budget, bool) or not isinstance(step_budget, int):
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "step_budget must be an int",
            )
        if step_budget <= 0:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "step_budget must be positive",
            )
        self._implementation = implementation
        self._integration_id = integration_id
        self._step_budget = step_budget
        self._session_reader = session_reader
        self._open = False
        self._consecutive_failures = 0
        self._total_failures = 0
        self._total_contract_violations = 0

    # ---- # context and mediation ------------------------------------- #

    def _context(self, now: str) -> ServiceContext:
        return ServiceContext(
            integration_id=self._integration_id,
            instant=now,
            step_budget=self._step_budget,
            session_reader=self._session_reader,
        )

    def _record_failure(self, *, violation: bool = False) -> None:
        self._consecutive_failures += 1
        self._total_failures += 1
        if violation:
            self._total_contract_violations += 1

    def _record_success(self) -> None:
        self._consecutive_failures = 0

    def computed_health(self) -> str:
        if not self._open:
            return "NOT_RUNNING"
        if self._consecutive_failures >= FAILURE_THRESHOLD_FAILED:
            return "FAILED"
        if self._consecutive_failures >= FAILURE_THRESHOLD_DEGRADED:
            return "DEGRADED"
        return "HEALTHY"

    def _mediate(
        self,
        now: str,
        operation: str,
        fn: Callable[[ServiceContext], Any],
        *,
        validate: Callable[[Any], Any],
    ) -> ServiceOpResult:
        context = self._context(now)
        try:
            value = fn(context)
        except _BudgetExhausted:
            # The provider overdrawn its step budget: deterministic
            # resource accounting fails closed (a hang model -- no
            # wall clock exists in this layer).
            self._record_failure()
            return ServiceOpResult(
                ok=False,
                failure=ServiceFailure(
                    reason_code=ServiceReasonCode.BUDGET_EXHAUSTED,
                    integration_id=self._integration_id,
                    operation=operation,
                ),
                detail="provider step budget exhausted",
            )
        except ServiceError as exc:
            # A provider raising ServiceError reports its frozen
            # reason code as a VALUE (failure isolation).
            self._record_failure()
            return ServiceOpResult(
                ok=False,
                failure=ServiceFailure(
                    reason_code=exc.reason,
                    integration_id=self._integration_id,
                    operation=operation,
                ),
                detail=exc.detail,
            )
        except BaseException as exc:  # noqa: BLE001
            # Any other provider fault is isolated: only the CLASS
            # name crosses (LOCK-023).
            self._record_failure()
            return ServiceOpResult(
                ok=False,
                failure=ServiceFailure(
                    reason_code=ServiceReasonCode.SERVICES_FAILURE,
                    integration_id=self._integration_id,
                    operation=operation,
                    exception_class_name=type(exc).__name__,
                ),
                detail="provider fault isolated",
            )
        try:
            validated = validate(value)
        except _ContractViolation:
            self._record_failure(violation=True)
            return ServiceOpResult(
                ok=False,
                failure=ServiceFailure(
                    reason_code=ServiceReasonCode.CONTRACT_VIOLATION,
                    integration_id=self._integration_id,
                    operation=operation,
                ),
                detail="provider return shape violated the contract",
            )
        except ServiceError as exc:
            self._record_failure()
            return ServiceOpResult(
                ok=False,
                failure=ServiceFailure(
                    reason_code=exc.reason,
                    integration_id=self._integration_id,
                    operation=operation,
                ),
                detail=exc.detail,
            )
        self._record_success()
        return ServiceOpResult(ok=True, value=validated)

    # ---- # mediated contract operations -------------------------------- #

    def open(self, *, now: str) -> ServiceOpResult:
        result = self._mediate(
            now, "open", self._implementation.open, validate=_validate_nothing
        )
        if result.ok:
            self._open = True
        return result

    def admit(
        self,
        *,
        now: str,
        service_ref: str,
        host_node_id: str,
        tenant_domain: str,
        session_id: str,
        decision_ref: str,
        requirements: Any = None,
    ) -> ServiceOpResult:
        return self._mediate(
            now,
            "admit",
            lambda context: self._implementation.admit(
                context,
                service_ref=service_ref,
                host_node_id=host_node_id,
                tenant_domain=tenant_domain,
                session_id=session_id,
                decision_ref=decision_ref,
                requirements=requirements,
            ),
            validate=_validate_admission,
        )

    def execute(
        self,
        *,
        now: str,
        admission_ref: str,
        request_payload: bytes,
        requirements: Any = None,
    ) -> ServiceOpResult:
        return self._mediate(
            now,
            "execute",
            lambda context: self._implementation.execute(
                context,
                admission_ref=admission_ref,
                request_payload=request_payload,
                requirements=requirements,
            ),
            validate=_validate_outcome,
        )

    def release(self, *, now: str, admission_ref: str) -> ServiceOpResult:
        return self._mediate(
            now,
            "release",
            lambda context: self._implementation.release(
                context, admission_ref=admission_ref
            ),
            validate=_validate_nothing,
        )

    def observe(self, *, now: str) -> ServiceOpResult:
        return self._mediate(
            now,
            "observe",
            self._implementation.observe,
            validate=_validate_observation,
        )

    def health(self, *, now: str) -> ServiceOpResult:
        """Mediated provider-declared health (vocabulary-validated).
        The sandbox's own computed ladder is :meth:`computed_health`."""
        return self._mediate(
            now,
            "health",
            lambda context: self._implementation.health(),
            validate=_validate_health,
        )

    def close(self, *, now: str) -> ServiceOpResult:
        result = self._mediate(
            now, "close", self._implementation.close,
            validate=_validate_nothing,
        )
        if result.ok:
            self._open = False
        return result

    # ---- # diagnostics (never canonical) ------------------------------- #

    def diagnostic_state(self) -> dict:
        return {
            "integration_id": self._integration_id,
            "open": self._open,
            "computed_health": self.computed_health(),
            "consecutive_failures": self._consecutive_failures,
            "total_failures": self._total_failures,
            "total_contract_violations": self._total_contract_violations,
        }


__all__ = [
    "STEP_CHARGES",
    "FAILURE_THRESHOLD_DEGRADED",
    "FAILURE_THRESHOLD_FAILED",
    "HEALTH_VALUES",
    "ServiceOpResult",
    "SandboxedExecutionProvider",
]
