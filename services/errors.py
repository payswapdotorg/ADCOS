"""ADCOS service registry / edge compute error model (WORK-025).

Leaf module: imported by every other ``services`` submodule, imports
nothing from the package (no import cycles).  :class:`ServiceError` is
the fail-closed caller-input/state error; service-side faults (a
provider implementation raising, contract violations, budget
exhaustion, unknown service/admission/allocation, capacity
exhaustion, a policy-denied or stale invocation decision, service /
session identity collapse, federation scope denial) are reported as
VALUES (:class:`ServiceFailure`) so they never propagate into core
callers -- failure isolation is structural, exactly as in the
WORK-016 adapter SDK and the WORK-017/018/019/021/022/023/024
transport/IP/5G-Core/Wi-Fi/backhaul/mesh/distributed-core layers.

The reason-code vocabulary is frozen: adding a code is a deliberate
vocabulary change, never a silent extension.

The service layer is a COMPOSITION layer, not a new authority (the
WORK-025 contract): service identity is distinct from node identity,
policy authority remains WORK-010, federation authority remains
WORK-015, routing authority remains WORK-011, session authority
remains WORK-012, and resource/capacity vocabulary remains WORK-008.
No Kubernetes, container, VM, vendor-edge, or application-platform
concept crosses into core semantics (LOCK-016: external execution
implementations remain behind provider interfaces; LOCK-017: no
vendor authority -- verified by the WORK-025 selftest's
standards-boundary audit).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

#: Canonical service registry / edge runtime instance prefix.  Uses its
#: own ``services`` root namespace (WORK-025 family convention), so it is
#: structurally disjoint from the WORK-004 NodeID prefix
#: ``adcos:node:``, the WORK-016 adapter prefix ``adcos:adapter:``, the
#: WORK-017 transport prefix ``adcos:transport:``, the WORK-018 IP
#: integration prefix ``adcos:ipint:``, the WORK-019 5G Core
#: integration prefix ``adcos:fivegc``, the WORK-021 Wi-Fi prefix
#: ``wifi``, the WORK-022 backhaul prefix ``backhaul``, the WORK-023
#: mesh prefix ``mesh``, and the WORK-024 distributed-core prefix
#: ``distcore`` by construction.
SERVICES_PREFIX = "services"


class ServiceReasonCode:
    """Frozen reason-code vocabulary (service registry / edge layer).

    Mirrors the WORK-022/023/024 reason-code sets with domain terms
    renamed (gateway -> service record, breakout binding -> execution
    admission, gateway evidence -> advertisement evidence), plus the
    service-specific advertisement-lifecycle, tenant-isolation,
    re-authorization, and federation-scope codes.  Adding a code is a
    deliberate vocabulary change, never a silent extension.
    """

    INVALID_INPUT = "invalid-input"
    NOT_OPEN = "not-open"
    ALREADY_OPEN = "already-open"
    SERVICE_UNKNOWN = "service-unknown"
    SERVICE_STALE = "service-stale"
    SERVICE_WITHDRAWN = "service-withdrawn"
    SERVICE_CONFLICT = "service-conflict"
    SERVICE_UNAVAILABLE = "service-unavailable"
    ADVERTISEMENT_UNEVIDENCED = "advertisement-unevidenced"
    ADVERTISEMENT_REPLAY = "advertisement-replay"
    TENANT_ISOLATION = "tenant-isolation"
    VISIBILITY_HIDDEN = "visibility-hidden"
    DECISION_UNKNOWN = "decision-unknown"
    DECISION_DENIED = "decision-denied"
    DECISION_STALE = "decision-stale"
    DECISION_EXISTS = "decision-exists"
    DECISION_SCOPE_MISMATCH = "decision-scope-mismatch"
    REAUTHORIZATION_REQUIRED = "reauthorization-required"
    ADMISSION_UNKNOWN = "admission-unknown"
    ADMISSION_EXISTS = "admission-exists"
    ADMISSION_STATE = "admission-state"
    ALLOCATION_UNKNOWN = "allocation-unknown"
    CAPACITY_EXHAUSTED = "capacity-exhausted"
    SESSION_NOT_SECUREABLE = "session-not-secureable"
    ACCESS_SESSION_COLLAPSE = "access-session-collapse"
    EXECUTION_STATE = "execution-state"
    FEDERATION_SCOPE_DENIED = "federation-scope-denied"
    FEDERATION_UNKNOWN = "federation-unknown"
    CONTRACT_VIOLATION = "contract-violation"
    BUDGET_EXHAUSTED = "budget-exhausted"
    FROZEN_SPEC_VIOLATION = "frozen-spec-violation"
    ILLEGAL_STATE = "illegal-state"
    SERVICES_FAILURE = "services-failure"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.INVALID_INPUT,
            cls.NOT_OPEN,
            cls.ALREADY_OPEN,
            cls.SERVICE_UNKNOWN,
            cls.SERVICE_STALE,
            cls.SERVICE_WITHDRAWN,
            cls.SERVICE_CONFLICT,
            cls.SERVICE_UNAVAILABLE,
            cls.ADVERTISEMENT_UNEVIDENCED,
            cls.ADVERTISEMENT_REPLAY,
            cls.TENANT_ISOLATION,
            cls.VISIBILITY_HIDDEN,
            cls.DECISION_UNKNOWN,
            cls.DECISION_DENIED,
            cls.DECISION_STALE,
            cls.DECISION_EXISTS,
            cls.DECISION_SCOPE_MISMATCH,
            cls.REAUTHORIZATION_REQUIRED,
            cls.ADMISSION_UNKNOWN,
            cls.ADMISSION_EXISTS,
            cls.ADMISSION_STATE,
            cls.ALLOCATION_UNKNOWN,
            cls.CAPACITY_EXHAUSTED,
            cls.SESSION_NOT_SECUREABLE,
            cls.ACCESS_SESSION_COLLAPSE,
            cls.EXECUTION_STATE,
            cls.FEDERATION_SCOPE_DENIED,
            cls.FEDERATION_UNKNOWN,
            cls.CONTRACT_VIOLATION,
            cls.BUDGET_EXHAUSTED,
            cls.FROZEN_SPEC_VIOLATION,
            cls.ILLEGAL_STATE,
            cls.SERVICES_FAILURE,
        )


class ServiceError(ValueError):
    """Fail-closed caller-input/state error (mirrors the WORK-016..024
    adapter discipline).  Raised for caller-side validation failures;
    never used to carry provider-implementation faults, which are
    returned as :class:`ServiceFailure` values.
    """

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__("%s: %s" % (reason, detail))
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class ServiceFailure:
    """Implementation-side fault reported as a VALUE (never raised into
    core callers).  Carries the frozen reason code, the owning
    integration id, the failing operation name, and -- at most -- the
    exception CLASS name.  Exception message text is deliberately never
    captured (LOCK-023: no diagnostic text crosses the boundary).
    """

    reason_code: str
    integration_id: str
    operation: str
    exception_class_name: str = ""

    def to_dict(self) -> dict:
        return {
            "reason_code": self.reason_code,
            "integration_id": self.integration_id,
            "operation": self.operation,
            "exception_class_name": self.exception_class_name,
        }


__all__ = [
    "SERVICES_PREFIX",
    "ServiceReasonCode",
    "ServiceError",
    "ServiceFailure",
]
