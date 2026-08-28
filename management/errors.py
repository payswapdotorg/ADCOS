"""Management-plane error vocabulary (WORK-030).

A single frozen reason-code vocabulary shared by the RBAC store, the
audit ledger, and the management API.  Codes are stable
machine-readable identifiers (never free text) so denial causes are
auditable and diagnosable -- the same discipline the policy engine
applies to ``DecisionCode`` (deny-by-default auditability requires the
distinction, never a collapsed generic ``false``).
"""

from __future__ import annotations

from typing import Tuple

#: Prefix for every management reason code (namespace discipline --
#: management codes are never confusable with policy/session/federation/
#: telemetry codes).
MANAGEMENT_PREFIX = "management."


class ManagementReasonCode:
    """Frozen management result/reason vocabulary.

    - ``EXECUTED`` -- the operation was authorized and the authority
      accepted it (ok);
    - ``INVALID_INPUT`` -- malformed request material (denied before
      any authority was touched);
    - ``RBAC_DENIED`` -- the operator holds no active role granting the
      operation's required capability (deny-by-default; P6 least
      authority);
    - ``POLICY_DENIED`` -- the operation is privileged and the WORK-010
      authority did not explicitly allow it (no applicable policy set,
      no explicit ALLOW, or an explicit DENY from an applicable live
      set);
    - ``AUTHORITY_REJECTED`` -- authorization succeeded but the owning
      authority rejected the transition (the management layer NEVER
      overrides an authority verdict);
    - ``FAILED`` -- an unexpected internal failure (audited; nothing
      was executed).
    """

    EXECUTED = MANAGEMENT_PREFIX + "executed"
    INVALID_INPUT = MANAGEMENT_PREFIX + "invalid-input"
    RBAC_DENIED = MANAGEMENT_PREFIX + "rbac-denied"
    POLICY_DENIED = MANAGEMENT_PREFIX + "policy-denied"
    AUTHORITY_REJECTED = MANAGEMENT_PREFIX + "authority-rejected"
    FAILED = MANAGEMENT_PREFIX + "failed"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.EXECUTED,
            cls.INVALID_INPUT,
            cls.RBAC_DENIED,
            cls.POLICY_DENIED,
            cls.AUTHORITY_REJECTED,
            cls.FAILED,
        )

    @classmethod
    def ok_values(cls) -> Tuple[str, ...]:
        return (cls.EXECUTED,)

    @classmethod
    def is_valid(cls, code: object) -> bool:
        return isinstance(code, str) and code in cls.values()


class ManagementError(Exception):
    """Fail-closed management error.

    Carries a frozen :class:`ManagementReasonCode` (never free text)
    plus a deterministic human-readable detail without secrets.  The
    management API layer translates these into audited
    ``ManagementResult`` denials; the store-level constructors raise
    them for malformed state (the established ADCOS fail-closed
    construction discipline).
    """

    def __init__(self, code: str, detail: str) -> None:
        if not ManagementReasonCode.is_valid(code) and not code.startswith(
            MANAGEMENT_PREFIX
        ):
            raise ValueError("invalid management reason code %r" % (code,))
        super().__init__("%s: %s" % (code, detail))
        self.code = code
        self.detail = detail

    def __repr__(self) -> str:  # pragma: no cover -- trivial
        return "ManagementError(%r, %r)" % (self.code, self.detail)


__all__ = [
    "MANAGEMENT_PREFIX",
    "ManagementError",
    "ManagementReasonCode",
]
