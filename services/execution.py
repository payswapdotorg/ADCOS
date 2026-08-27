"""ADCOS reference edge executor (WORK-025).

The deterministic in-process reference implementation of the
:class:`~services.contract.ExecutionProviderContract` -- the edge
execution seam's reference model.  It is NOT an application platform
(WORK-025 invariant 9): execution is a fixed deterministic
request/response transform (an echo service whose response bytes
equal the request bytes), there is no arbitrary code loading, no
plugin system, no container orchestration, and no vendor runtime
concept.

Discipline (mirrors the WORK-024 reference engines):

- **Validate/commit split with candidate sequence**: every mutating
  operation is split into a side-effect-free ``_validate_*`` phase
  (charges the step budget, validates inputs, derives the
  identity from ``candidate_sequence = self._sequence + 1``) and an
  infallible ``_commit_*`` phase that advances the derivation nonce
  ONLY on success.  A failed validation or a failed commit consumes
  NO derivation state -- the PR #24 architectural-review lesson,
  applied from day one (WORK-025 invariant 13).
- **Honest failure accounting**: guard paths stay pure; failure
  counters advance only through explicit ``_commit_*`` helpers.
- **Reference-model controls** (NOT in CONTRACT_OPERATIONS):
  ``set_executor_state`` (strict availability toggling -- the
  "known but unavailable at execution time" partition control) and
  ``executed_payloads`` (the request/response isolation surface the
  selftest uses to prove that failed operations leave no provider
  side effects).

3GPP TS 23.548 (edge computing enablers) and ETSI MEC are cited as
DATA only: the reference executor carries no MEC API, no vendor
platform, and no radio/3GPP protocol semantics.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Tuple

from .contract import ExecutionProviderContract, ServiceContext
from .errors import ServiceError, ServiceReasonCode
from .model import (
    AdmissionState,
    ExecutionOutcome,
    ExecutionStatus,
    ServiceAdmission,
    ServiceMetricName,
    ServiceObservation,
    derive_admission_ref,
    derive_execution_ref,
)
from .sandbox import STEP_CHARGES
from .validation import (
    assert_ref_session_separation,
    validate_node_id,
    validate_opaque_ref,
    validate_session_ref,
    validate_tenant_domain,
)

#: Maximum accepted request payload size (bytes; mirrors the WORK-024
#: MAX_EGRESS_BYTES discipline).
MAX_REQUEST_BYTES = 65536

#: Maximum concurrently ACTIVE admissions on the reference executor
#: (provider-side execution readiness -- distinct from the WORK-008
#: capacity DATA admitted by the registry).
MAX_CONCURRENT_ADMISSIONS = 64

#: Requirement keys that carry identity material: requirements are
#: opaque operational hints ONLY, never a second channel for identity
#: re-assertion (the WORK-023/024 discipline, duplicated from the
#: registry as defense in depth).
_FORBIDDEN_REQUIREMENT_KEYS = (
    "node_id", "session_id", "service_ref", "decision_ref",
    "admission_ref", "path_ref", "gateway_ref", "breakout_ref",
    "resource_id", "capability_id", "federation_id", "caller_node_id",
)


class _AdmissionEntry:
    """Internal provider-side admission bookkeeping."""

    __slots__ = ("admission", "executed")

    def __init__(self, admission: ServiceAdmission) -> None:
        self.admission = admission
        self.executed: List[Tuple[bytes, bytes]] = []


def _reject_identity_smuggling(requirements: Any) -> None:
    if requirements is None:
        return
    if not isinstance(requirements, dict):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "requirements must be a mapping of opaque operational hints",
        )
    for key in requirements:
        if isinstance(key, str) and key in _FORBIDDEN_REQUIREMENT_KEYS:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "requirements key %r carries identity material -- "
                "requirements are opaque operational hints only" % (key,),
            )


class ReferenceEdgeExecutor(ExecutionProviderContract):
    """Deterministic in-process reference edge executor."""

    label = "reference-edge-executor"

    def __init__(self) -> None:
        self._open = False
        self._available = True
        # Insertion-ordered dicts: determinism.
        self._admissions: Dict[str, _AdmissionEntry] = {}
        # The identity-derivation nonce: advances ONLY inside the
        # commit phases (the WORK-023/024 candidate-sequence
        # discipline; a failed validation consumes no derivation
        # state).
        self._sequence = 0
        # Honest counters.
        self._executed_total = 0
        self._executed_bytes_total = 0
        self._execution_failures = 0

    # ---- # lifecycle --------------------------------------------------- #

    def open(self, context: ServiceContext) -> None:
        context.charge(STEP_CHARGES["open"])
        if self._open:
            raise ServiceError(
                ServiceReasonCode.ALREADY_OPEN,
                "reference edge executor is already open",
            )
        self._open = True

    def close(self, context: ServiceContext) -> None:
        context.charge(STEP_CHARGES["close"])
        if not self._open:
            raise ServiceError(
                ServiceReasonCode.NOT_OPEN,
                "reference edge executor is not open",
            )
        if any(
            entry.admission.state == AdmissionState.ACTIVE
            for entry in self._admissions.values()
        ):
            raise ServiceError(
                ServiceReasonCode.ILLEGAL_STATE,
                "reference edge executor has outstanding admissions",
            )
        self._open = False

    def health(self) -> str:
        if not self._open:
            return "NOT_RUNNING"
        return "HEALTHY" if self._available else "DEGRADED"

    # ---- # admission (validate / commit) -------------------------------- #

    def _require_open(self) -> None:
        if not self._open:
            raise ServiceError(
                ServiceReasonCode.NOT_OPEN,
                "reference edge executor is not open",
            )

    def _require_available(self) -> None:
        if not self._available:
            raise ServiceError(
                ServiceReasonCode.SERVICE_UNAVAILABLE,
                "edge executor is currently unavailable (partitioned "
                "execution provider)",
            )

    def _validate_admit(
        self,
        context: ServiceContext,
        *,
        service_ref: str,
        host_node_id: str,
        tenant_domain: str,
        session_id: str,
        decision_ref: str,
        requirements: Any,
    ) -> Tuple[ServiceAdmission, int]:
        context.charge(STEP_CHARGES["admit"])
        self._require_open()
        validate_opaque_ref(service_ref, "service")
        validate_node_id(host_node_id)
        validate_tenant_domain(tenant_domain)
        if session_id:
            validate_session_ref(session_id)
        # An admission always carries the governing invocation
        # decision ref (execution is never implicitly authorized).
        validate_opaque_ref(decision_ref, "decision")
        _reject_identity_smuggling(requirements)
        self._require_available()
        active = sum(
            1
            for entry in self._admissions.values()
            if entry.admission.state == AdmissionState.ACTIVE
        )
        if active >= MAX_CONCURRENT_ADMISSIONS:
            raise ServiceError(
                ServiceReasonCode.CAPACITY_EXHAUSTED,
                "reference executor concurrency exhausted (%d active "
                "admissions)" % (active,),
            )
        # Derive from a CANDIDATE sequence: the nonce advances only
        # in the commit phase, so a failed validation leaves the
        # derivation state untouched (the PR #24 architectural-review
        # discipline).
        candidate_sequence = self._sequence + 1
        admission_ref = derive_admission_ref(service_ref, candidate_sequence)
        if session_id:
            assert_ref_session_separation(admission_ref, session_id)
        admission = ServiceAdmission(
            admission_ref=admission_ref,
            service_ref=service_ref,
            host_node_id=host_node_id,
            tenant_domain=tenant_domain,
            session_id=session_id,
            decision_ref=decision_ref,
            admitted_at=context.now(),
            state=AdmissionState.ACTIVE,
        )
        return admission, candidate_sequence

    def _commit_admit(
        self, admission: ServiceAdmission, candidate_sequence: int
    ) -> None:
        if admission.admission_ref in self._admissions:
            raise ServiceError(
                ServiceReasonCode.ILLEGAL_STATE,
                "admission ref collision -- derivation state is corrupt",
            )
        # The sequence advances ONLY here, in the commit phase.
        self._sequence = candidate_sequence
        self._admissions[admission.admission_ref] = _AdmissionEntry(admission)

    def admit(
        self,
        context: ServiceContext,
        *,
        service_ref: str,
        host_node_id: str,
        tenant_domain: str,
        session_id: str,
        decision_ref: str,
        requirements: Any = None,
    ) -> ServiceAdmission:
        admission, candidate_sequence = self._validate_admit(
            context,
            service_ref=service_ref,
            host_node_id=host_node_id,
            tenant_domain=tenant_domain,
            session_id=session_id,
            decision_ref=decision_ref,
            requirements=requirements,
        )
        self._commit_admit(admission, candidate_sequence)
        return admission

    # ---- # execution ---------------------------------------------------- #

    def _require_admission(self, admission_ref: str) -> _AdmissionEntry:
        entry = self._admissions.get(admission_ref)
        if entry is None:
            raise ServiceError(
                ServiceReasonCode.ADMISSION_UNKNOWN,
                "admission %r is unknown to this executor" % (admission_ref,),
            )
        return entry

    def _validate_execute(
        self,
        context: ServiceContext,
        *,
        admission_ref: str,
        request_payload: Any,
        requirements: Any,
    ) -> _AdmissionEntry:
        context.charge(STEP_CHARGES["execute"])
        self._require_open()
        validate_opaque_ref(admission_ref, "admission")
        if not isinstance(request_payload, bytes):
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "request payload must be bytes (got %s)"
                % (type(request_payload).__name__,),
            )
        if not request_payload:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "request payload must be non-empty",
            )
        if len(request_payload) > MAX_REQUEST_BYTES:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "request payload exceeds %d bytes" % (MAX_REQUEST_BYTES,),
            )
        _reject_identity_smuggling(requirements)
        self._require_available()
        entry = self._require_admission(admission_ref)
        if entry.admission.state != AdmissionState.ACTIVE:
            raise ServiceError(
                ServiceReasonCode.ADMISSION_STATE,
                "admission %r is %r, not active" % (
                    admission_ref, entry.admission.state,
                ),
            )
        return entry

    def _commit_execution_failure(self) -> None:
        """Honest failure accounting: the counter advances ONLY here,
        through an explicit commit helper (guards stay pure)."""
        self._execution_failures += 1

    def execute(
        self,
        context: ServiceContext,
        *,
        admission_ref: str,
        request_payload: bytes,
        requirements: Any = None,
    ) -> ExecutionOutcome:
        entry = self._validate_execute(
            context,
            admission_ref=admission_ref,
            request_payload=request_payload,
            requirements=requirements,
        )
        # Deterministic reference execution: an echo transform (no
        # arbitrary code, no platform).
        response_payload = bytes(request_payload)
        request_digest = hashlib.sha256(request_payload).hexdigest()
        outcome = ExecutionOutcome(
            admission_ref=admission_ref,
            service_ref=entry.admission.service_ref,
            execution_ref=derive_execution_ref(
                admission_ref, context.now(), request_digest
            ),
            status=ExecutionStatus.COMPLETED,
            executed_at=context.now(),
            request_bytes=len(request_payload),
            request_digest=request_digest,
            response_payload=response_payload,
        )
        entry.executed.append((bytes(request_payload), response_payload))
        self._executed_total += 1
        self._executed_bytes_total += len(request_payload)
        return outcome

    # ---- # release (validate / commit) ---------------------------------- #

    def _validate_release(
        self, context: ServiceContext, *, admission_ref: str
    ) -> _AdmissionEntry:
        context.charge(STEP_CHARGES["release"])
        self._require_open()
        validate_opaque_ref(admission_ref, "admission")
        entry = self._require_admission(admission_ref)
        if entry.admission.state != AdmissionState.ACTIVE:
            raise ServiceError(
                ServiceReasonCode.ADMISSION_STATE,
                "admission %r is %r, not active" % (
                    admission_ref, entry.admission.state,
                ),
            )
        return entry

    def _commit_release(
        self, entry: _AdmissionEntry, *, state: str
    ) -> None:
        # Frozen dataclass: replace the stored admission with a new
        # value carrying the terminal state (deterministic, no
        # in-place mutation of a frozen record).
        released = ServiceAdmission(
            admission_ref=entry.admission.admission_ref,
            service_ref=entry.admission.service_ref,
            host_node_id=entry.admission.host_node_id,
            tenant_domain=entry.admission.tenant_domain,
            session_id=entry.admission.session_id,
            decision_ref=entry.admission.decision_ref,
            admitted_at=entry.admission.admitted_at,
            state=state,
        )
        entry.admission = released

    def release(
        self, context: ServiceContext, *, admission_ref: str
    ) -> None:
        entry = self._validate_release(context, admission_ref=admission_ref)
        self._commit_release(entry, state=AdmissionState.RELEASED)

    # ---- # observation --------------------------------------------------- #

    def observe(self, context: ServiceContext) -> ServiceObservation:
        context.charge(STEP_CHARGES["observe"])
        self._require_open()
        active = sum(
            1
            for entry in self._admissions.values()
            if entry.admission.state == AdmissionState.ACTIVE
        )
        return ServiceObservation(
            samples=(
                (ServiceMetricName.ACTIVE_ADMISSIONS, active),
                (ServiceMetricName.EXECUTED_REQUESTS, self._executed_total),
                (ServiceMetricName.FAILED_REQUESTS, self._execution_failures),
            ),
            active_admissions=active,
            executed_requests=self._executed_total,
            failed_requests=self._execution_failures,
        )

    # ---- # reference-model controls (NOT in CONTRACT_OPERATIONS) -------- #

    def set_executor_state(self, *, available: bool) -> None:
        """Partition control: strict toggling (re-applying the current
        state raises ILLEGAL_STATE), mirroring the WORK-024
        ``set_gateway_state`` discipline."""
        if isinstance(available, bool) is False:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "available must be a bool",
            )
        if available == self._available:
            raise ServiceError(
                ServiceReasonCode.ILLEGAL_STATE,
                "executor availability is already %r" % (available,),
            )
        self._available = available

    def executed_payloads(
        self, admission_ref: str
    ) -> Tuple[Tuple[bytes, bytes], ...]:
        """The request/response isolation surface: the exact payloads
        executed under one admission (reference-model control used by
        the selftest to prove failed operations leave no provider
        side effects)."""
        entry = self._admissions.get(admission_ref)
        if entry is None:
            return ()
        return tuple(entry.executed)

    def capabilities(self) -> Tuple[str, ...]:
        return (
            "capability.profile.service.edge-execution",
            "capability.profile.service.deterministic-echo",
        )

    def sequence_state(self) -> int:
        """Reference-model control exposing the derivation nonce (for
        the sequence-discipline regression only; never canonical)."""
        return self._sequence


__all__ = [
    "MAX_REQUEST_BYTES",
    "MAX_CONCURRENT_ADMISSIONS",
    "ReferenceEdgeExecutor",
]
