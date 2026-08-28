"""ADCOS distributed-core adapter error model (WORK-024).

Leaf module: imported by every other ``adapters.distcore`` submodule,
imports nothing from the package (no import cycles).  :class:`DistCoreError`
is the fail-closed caller-input/state error; distributed-core-side faults
(a provider implementation raising, contract violations, budget
exhaustion, unknown gateway/path/breakout, capacity exhaustion, a
policy-denied or stale breakout decision, session/breakout identity
collapse) are reported as VALUES (:class:`DistCoreFailure`) so they
never propagate into core callers -- failure isolation is structural,
exactly as in the WORK-016 adapter and the WORK-017/018/019/021/022/023
transport/IP/5G-Core/Wi-Fi/backhaul/mesh layers.

The reason-code vocabulary is frozen: adding a code is a deliberate
vocabulary change, never a silent extension.

The distributed core is a COMPOSITION layer, not a new authority
(the WORK-024 contract): session authority remains WORK-012, routing
authority remains WORK-011, policy authority remains WORK-010, and
ordinary IP semantics remain WORK-018.  No Open5GS, N3IWF, vendor, or
gateway implementation type crosses into core authority (LOCK-016:
external access implementations remain behind adapter/provider
interfaces; LOCK-017: no vendor authority -- verified by the WORK-024
selftest's standards-boundary audit).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

#: Canonical distributed-core adapter instance prefix.  Uses its own
#: ``distcore`` root namespace (WORK-024 family convention), so it is
#: structurally disjoint from the WORK-004 NodeID prefix
#: ``adcos:node:``, the WORK-016 adapter prefix ``adcos:adapter:``, the
#: WORK-017 transport prefix ``adcos:transport:``, the WORK-018 IP
#: integration prefix ``adcos:ipint:``, the WORK-019 5G Core
#: integration prefix ``adcos:fivegc``, the WORK-021 Wi-Fi prefix
#: ``wifi``, the WORK-022 backhaul prefix ``backhaul``, and the
#: WORK-023 mesh prefix ``mesh`` by construction.
DISTCORE_PREFIX = "distcore"


class DistCoreReasonCode:
    """Frozen reason-code vocabulary (distributed-core layer).

    Mirrors the WORK-022/023 reason-code sets with domain terms renamed
    (link -> breakout gateway, bearer -> breakout binding, route ->
    registered ordinary Path, allocation -> breakout-capacity ledger
    admission), plus the distributed-core-specific policy-decision,
    gateway-evidence, and mode-mismatch codes.  Adding a code is a
    deliberate vocabulary change, never a silent extension.
    """

    INVALID_INPUT = "invalid-input"
    NOT_OPEN = "not-open"
    ALREADY_OPEN = "already-open"
    BINDING_EXISTS = "binding-exists"
    GATEWAY_UNKNOWN = "gateway-unknown"
    GATEWAY_UNAVAILABLE = "gateway-unavailable"
    GATEWAY_AMBIGUOUS = "gateway-ambiguous"
    GATEWAY_UNEVIDENCED = "gateway-unevidenced"
    PATH_UNKNOWN = "path-unknown"
    PATH_INFEASIBLE = "path-infeasible"
    PATH_GATEWAY_MISMATCH = "path-gateway-mismatch"
    DECISION_UNKNOWN = "decision-unknown"
    DECISION_DENIED = "decision-denied"
    DECISION_STALE = "decision-stale"
    ALLOCATION_UNKNOWN = "allocation-unknown"
    CAPACITY_EXHAUSTED = "capacity-exhausted"
    SESSION_NOT_SECUREABLE = "session-not-secureable"
    ACCESS_SESSION_COLLAPSE = "access-session-collapse"
    BREAKOUT_UNKNOWN = "breakout-unknown"
    BREAKOUT_STATE = "breakout-state"
    CONTRACT_VIOLATION = "contract-violation"
    BUDGET_EXHAUSTED = "budget-exhausted"
    FROZEN_SPEC_VIOLATION = "frozen-spec-violation"
    ILLEGAL_STATE = "illegal-state"
    DISTCORE_FAILURE = "distcore-failure"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.INVALID_INPUT,
            cls.NOT_OPEN,
            cls.ALREADY_OPEN,
            cls.BINDING_EXISTS,
            cls.GATEWAY_UNKNOWN,
            cls.GATEWAY_UNAVAILABLE,
            cls.GATEWAY_AMBIGUOUS,
            cls.GATEWAY_UNEVIDENCED,
            cls.PATH_UNKNOWN,
            cls.PATH_INFEASIBLE,
            cls.PATH_GATEWAY_MISMATCH,
            cls.DECISION_UNKNOWN,
            cls.DECISION_DENIED,
            cls.DECISION_STALE,
            cls.ALLOCATION_UNKNOWN,
            cls.CAPACITY_EXHAUSTED,
            cls.SESSION_NOT_SECUREABLE,
            cls.ACCESS_SESSION_COLLAPSE,
            cls.BREAKOUT_UNKNOWN,
            cls.BREAKOUT_STATE,
            cls.CONTRACT_VIOLATION,
            cls.BUDGET_EXHAUSTED,
            cls.FROZEN_SPEC_VIOLATION,
            cls.ILLEGAL_STATE,
            cls.DISTCORE_FAILURE,
        )


class DistCoreError(ValueError):
    """Fail-closed caller-input / state error (raised, never swallowed).

    The distributed-core boundary's structural rule (mirroring WORK-016
    ``/adapters``, WORK-017 ``/transport``, WORK-018 ``/adapters/ip``,
    WORK-019 ``/adapters/fivegc``, WORK-021 ``/adapters/wifi``,
    WORK-022 ``/adapters/backhaul``, and WORK-023 ``/adapters/mesh``):

    * CALLER-side input/state errors RAISE this exception (unknown
      gateway/path/breakout/decision, malformed input, a policy-DENIED
      or stale breakout decision, session/breakout identity collapse,
      capacity exhaustion, illegal lifecycle state).
    * IMPLEMENTATION-side faults RETURN a typed :class:`DistCoreFailure`
      VALUE so a provider that raises (including ``BaseException`` such
      as ``SystemExit`` from a vendor gateway daemon), violates the
      contract shape, or exhausts its budget can never corrupt manager
      state and never propagates an exception.
    """

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__("%s: %s" % (reason, detail))
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class DistCoreFailure:
    """A typed, isolated distributed-core-side fault (value, not
    exception).

    For implementation exceptions ONLY the exception class name
    crosses -- exception message text is deliberately NOT captured, so
    an implementation cannot leak secret material (gateway management
    credentials, UPF N4 shared keys, IPsec/IKE material for the N3IWF
    plane) through failure diagnostics (LOCK-023 discipline, mirroring
    the WORK-016/017/018/019/021/022/023 convention).

    The fields are public, structurally secret-free, and
    canonical-JSON serializable through :meth:`to_dict`.
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
    "DISTCORE_PREFIX",
    "DistCoreReasonCode",
    "DistCoreError",
    "DistCoreFailure",
]
