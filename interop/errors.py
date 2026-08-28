"""WORK-037 interoperability-profile errors.

The frozen typed-error surface for the Open RAN/Core interoperability
profile (the WORK-033/034/035/036 ``errors.py`` discipline): one
exception type carrying a frozen reason-code vocabulary with the
``interop.`` prefix.  Every refusal is typed and journaled; nothing
fails silently and nothing is silently downgraded.
"""

from __future__ import annotations

__all__ = ["INTEROP_PREFIX", "InteropError", "InteropReasonCode"]


#: The frozen reason-code prefix (mirrors the family prefixes).
INTEROP_PREFIX = "interop"


class InteropReasonCode:
    """The frozen reason-code vocabulary (16 reasons).

    Reasons are stable strings; the battery asserts the exact frozen
    set.  Adding a reason is a vocabulary change that requires a
    governance amendment -- none is planned for WORK-037.
    """

    INVALID_INPUT = "interop.invalid-input"
    PROFILE_INVALID = "interop.profile-invalid"
    COMPONENT_MISMATCH = "interop.component-mismatch"
    REFERENCE_POINT_UNBOUND = "interop.reference-point-unbound"
    SESSION_UNKNOWN = "interop.session-unknown"
    SESSION_UNSECUREABLE = "interop.session-unsecureable"
    SESSION_DIVERGENCE = "interop.session-divergence"
    LEG_UNAVAILABLE = "interop.leg-unavailable"
    LEG_BYTE_MISMATCH = "interop.leg-byte-mismatch"
    REF_OPACITY_VIOLATION = "interop.ref-opacity-violation"
    FORBIDDEN_SUBSTITUTION = "interop.forbidden-substitution"
    LAB_UNREACHABLE = "interop.lab-unreachable"
    LEG_DISABLED = "interop.leg-disabled"
    LEG_FAILED = "interop.leg-failed"
    EVIDENCE_CLASS_VIOLATION = "interop.evidence-class-violation"
    REPLAY_MISMATCH = "interop.replay-mismatch"

    @classmethod
    def values(cls) -> tuple:
        return (
            cls.INVALID_INPUT,
            cls.PROFILE_INVALID,
            cls.COMPONENT_MISMATCH,
            cls.REFERENCE_POINT_UNBOUND,
            cls.SESSION_UNKNOWN,
            cls.SESSION_UNSECUREABLE,
            cls.SESSION_DIVERGENCE,
            cls.LEG_UNAVAILABLE,
            cls.LEG_BYTE_MISMATCH,
            cls.REF_OPACITY_VIOLATION,
            cls.FORBIDDEN_SUBSTITUTION,
            cls.LAB_UNREACHABLE,
            cls.LEG_DISABLED,
            cls.LEG_FAILED,
            cls.EVIDENCE_CLASS_VIOLATION,
            cls.REPLAY_MISMATCH,
        )


#: Bounded detail length (the family discipline; diagnostics never
#: carry unbounded peer output and never carry credential material).
_DETAIL_LIMIT = 300


class InteropError(Exception):
    """The single typed exception for the interoperability profile.

    ``reason`` is one of :class:`InteropReasonCode.values()`; ``detail``
    is a bounded, secret-free diagnostic string.
    """

    def __init__(self, reason: str, detail: str) -> None:
        if reason not in InteropReasonCode.values():
            raise InteropError(
                InteropReasonCode.INVALID_INPUT,
                "unknown interop reason code: %r" % (reason,),
            )
        self.reason = reason
        self.detail = str(detail)[:_DETAIL_LIMIT]
        super().__init__("%s: %s" % (reason, self.detail))
