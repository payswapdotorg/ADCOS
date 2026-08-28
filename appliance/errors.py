"""WORK-036 Network-in-a-Box appliance errors.

A single frozen exception type with a frozen reason-code vocabulary
(the WORK-033/W034/W035 discipline): caller-side misuse raises
:class:`ApplianceError`; authority-side rejections flow through the
outcome surfaces as typed reasons, never as silent drops.
"""

from __future__ import annotations


class ApplianceError(ValueError):
    """Raised for caller-side appliance-boundary violations.

    ``reason`` is one of the frozen :class:`ApplianceReasonCode`
    values; ``detail`` is a bounded human-readable string that never
    carries payload content or secrets.
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__("%s: %s" % (reason, detail))
        self.reason = reason
        self.detail = detail


class ApplianceReasonCode:
    """The frozen appliance reason vocabulary (``appliance.`` prefix,
    structurally disjoint from every accepted family prefix)."""

    INVALID_INPUT = "appliance.invalid-input"
    ILLEGAL_STATE = "appliance.illegal-state"
    COMMAND_UNKNOWN = "appliance.command-unknown"
    PARAMS_INVALID = "appliance.params-invalid"
    MANIFEST_INVALID = "appliance.manifest-invalid"
    DUPLICATE_ENTRY = "appliance.duplicate-entry"
    PATH_INCOHERENT = "appliance.path-incoherent"
    UPSTREAM_UNCHANGED = "appliance.upstream-unchanged"
    FEDERATION_OUT_OF_SCOPE = "appliance.federation-out-of-scope"
    POLICY_DECISION_REQUIRED = "appliance.policy-decision-required"
    NOT_PROVISIONED = "appliance.not-provisioned"

    @classmethod
    def values(cls) -> tuple:
        return (
            cls.INVALID_INPUT,
            cls.ILLEGAL_STATE,
            cls.COMMAND_UNKNOWN,
            cls.PARAMS_INVALID,
            cls.MANIFEST_INVALID,
            cls.DUPLICATE_ENTRY,
            cls.PATH_INCOHERENT,
            cls.UPSTREAM_UNCHANGED,
            cls.FEDERATION_OUT_OF_SCOPE,
            cls.POLICY_DECISION_REQUIRED,
            cls.NOT_PROVISIONED,
        )


__all__ = [
    "ApplianceError",
    "ApplianceReasonCode",
]
