"""ADCOS 5G RAN integration error model (WORK-020).

Leaf module: imported by every other ``adapters.ran`` submodule,
imports nothing from the package (no import cycles).  ``RanError`` is
the fail-closed caller-input/state error; RAN-side faults (an
implementation raising, contract violations, budget exhaustion, unknown
gNB/cell/bearer/allocation, RAN stack unavailable, RAN/session identity
collapse) are reported as VALUES (:class:`RanFailure`) so they never
propagate into core callers -- failure isolation is structural, exactly
as in the WORK-016 adapter SDK and the WORK-017/018/19 transport/IP/
5G-Core integration layers (mirrors the accepted ``adapters.fivegc``
error model).

The reason-code vocabulary is frozen: adding a code is a deliberate
vocabulary change, never a silent extension.

The RAN (gNB/CU/DU/RU) is an EXTERNAL implementation, not an ADCOS
authority (LOCK-002: 5G NR is an adapter; 3GPP RAN functions remain
outside the ADCOS core domain; LOCK-016: external RAN/modem/SDR
implementations remain behind adapter/provider interfaces; LOCK-017:
vendor implementations are not ADCOS authority).  No RAN type, RAN
identifier (RNTI/DRB/cell/gNB id), or 3GPP state machine is imported
into the ADCOS core (LOCK-002/016; the WORK-020 selftest's
no-core-RAN-leakage audit verifies this mechanically).  RAN identifiers
are adapter-private opaque state; the ADCOS ``session_id`` is sacred
and access-independent (LOCK-006).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

#: Canonical 5G RAN integration instance prefix.  Structurally disjoint
#: from the WORK-004 NodeID prefix ``adcos:node:``, the WORK-016
#: adapter prefix ``adcos:adapter:``, the WORK-017 transport prefix
#: ``adcos:transport:``, the WORK-018 IP integration prefix
#: ``adcos:ipint:``, and the WORK-019 5G Core prefix ``adcos:fivegc``
#: by construction.
RAN_PREFIX = "adcos:ran"

#: Opaque RAN-side reference prefix family (the grammar pinned by
#: :mod:`adapters.ran.validation`): ``ran:gnb:<digest-or-counter>``,
#: ``ran:bearer:<digest-or-counter>``, ``ran:alloc:<digest-or-counter>``,
#: ``ran:ue:<digest-or-counter>``.  These are RAN-side identity handles
#: -- deliberately NOT the WORK-012 ``session_id`` and never
#: authoritative for ADCOS state (LOCK-006/017; the R1 mechanical
#: separation check lives in
#: :func:`adapters.ran.validation.assert_ref_session_separation`).
RAN_REF_PREFIX = "ran"


class RanReasonCode:
    """Frozen reason-code vocabulary (5G RAN integration layer).

    Adding a code is a deliberate vocabulary change, never a silent
    extension.
    """

    INVALID_INPUT = "invalid-input"
    NOT_OPEN = "not-open"
    BINDING_UNKNOWN = "binding-unknown"
    BINDING_EXISTS = "binding-exists"
    GNB_UNKNOWN = "gnb-unknown"
    CELL_UNKNOWN = "cell-unknown"
    BEARER_UNKNOWN = "bearer-unknown"
    ALLOCATION_UNKNOWN = "allocation-unknown"
    RAN_UNAVAILABLE = "ran-unavailable"
    RAN_SESSION_COLLAPSE = "ran-session-collapse"
    CONTRACT_VIOLATION = "contract-violation"
    BUDGET_EXHAUSTED = "budget-exhausted"
    FROZEN_SPEC_VIOLATION = "frozen-spec-violation"
    RAN_FAILURE = "ran-failure"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.INVALID_INPUT,
            cls.NOT_OPEN,
            cls.BINDING_UNKNOWN,
            cls.BINDING_EXISTS,
            cls.GNB_UNKNOWN,
            cls.CELL_UNKNOWN,
            cls.BEARER_UNKNOWN,
            cls.ALLOCATION_UNKNOWN,
            cls.RAN_UNAVAILABLE,
            cls.RAN_SESSION_COLLAPSE,
            cls.CONTRACT_VIOLATION,
            cls.BUDGET_EXHAUSTED,
            cls.FROZEN_SPEC_VIOLATION,
            cls.RAN_FAILURE,
        )


class RanError(ValueError):
    """Fail-closed caller-input / state error (raised, never swallowed).

    The 5G RAN integration boundary's structural rule (mirroring the
    WORK-016 ``/adapters`` SDK, WORK-017 ``/transport``, WORK-018
    ``/adapters/ip``, and WORK-019 ``/adapters/fivegc``):

    * CALLER-side input/state errors RAISE this exception (unknown
      binding, malformed input, RAN/session identity collapse, double
      close, unknown gNB/cell/bearer/allocation, RAN stack not
      configured).

    * IMPLEMENTATION-side faults RETURN a typed :class:`RanFailure`
      VALUE so an implementation that raises (including
      ``BaseException`` such as ``SystemExit`` from a vendor RAN SDK),
      violates the contract shape, or exhausts its budget can never
      corrupt manager state and never propagates an exception.

    Mechanics mirror :class:`adapters.fivegc.errors.FiveGCoreError`
    exactly (a ``ValueError`` carrying a reason code and a detail
    string); the attribute is named ``reason_code`` to match
    :class:`RanFailure`'s field vocabulary.
    """

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__("%s: %s" % (reason_code, detail))
        self.reason_code = reason_code
        self.detail = detail


@dataclass(frozen=True)
class RanFailure:
    """A typed, isolated RAN-side fault (value, not exception).

    ``exception_class_name`` carries, for implementation exceptions,
    ONLY the exception class name -- exception message text is
    deliberately NOT captured, so an implementation cannot leak
    credential-like material through failure diagnostics (LOCK-023
    discipline, mirroring the WORK-016/017/018/019 convention).

    The fields are public, structurally secret-free, and
    canonical-JSON serializable through :meth:`to_payload`.
    """

    reason_code: str
    ran_integration_id: str
    operation: str
    exception_class_name: str = ""

    def to_payload(self) -> dict:
        """The canonical, secret-free payload of this failure value."""
        return {
            "reason_code": self.reason_code,
            "ran_integration_id": self.ran_integration_id,
            "operation": self.operation,
            "exception_class_name": self.exception_class_name,
        }


__all__ = [
    "RAN_PREFIX",
    "RAN_REF_PREFIX",
    "RanReasonCode",
    "RanError",
    "RanFailure",
]
