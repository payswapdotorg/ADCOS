"""WORK-038 future-IMT error values.

The typed failure vocabulary of the future-IMT/6G adapter profile.
Every reason code carries the ``future.`` prefix (the W033 agent
error-vocabulary style; the W037 ``interop.`` precedent).  The prefix
makes profile-scoped failures greppable and structurally distinct from
adapter (``adapter.``), upgrade (``upgrade.``), and interop
(``interop.``) failures: a future-profile problem can never masquerade
as a core-domain problem.
"""

from __future__ import annotations

from typing import Tuple

_DETAIL_LIMIT = 200

#: The frozen reason-code prefix (the W033/W037 typed-error style).
FUTURE_PREFIX = "future."


class FutureError(Exception):
    """A typed WORK-038 failure (never a bare exception crossing the
    profile boundary)."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__("%s: %s" % (reason, detail))
        self.reason = reason
        self.detail = detail

    def __str__(self) -> str:  # pragma: no cover - trivial
        return "%s: %s" % (self.reason, self.detail)


class FutureReasonCode:
    """The frozen reason vocabulary (11 codes).

    Fail-closed semantics: validation failures identify the exact
    violated contract; the evidence guard refuses any real-world
    promotion of synthetic evidence (the W020 lesson, WORK-038's
    class-C inapplicability rule).
    """

    INVALID_INPUT = "future.invalid-input"
    PROFILE_INVALID = "future.profile-invalid"
    TECHNOLOGY_ID_INVALID = "future.technology-id-invalid"
    CAPABILITY_INVALID = "future.capability-invalid"
    VERSION_INVALID = "future.profile-version-invalid"
    MAPPING_INVALID = "future.mapping-invalid"
    NOT_OPEN = "future.not-open"
    ALLOCATION_UNKNOWN = "future.allocation-unknown"
    BINDING_UNKNOWN = "future.binding-unknown"
    EVIDENCE_CLASS_VIOLATION = "future.evidence-class-violation"
    REPLAY_DIVERGENCE = "future.replay-divergence"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.INVALID_INPUT,
            cls.PROFILE_INVALID,
            cls.TECHNOLOGY_ID_INVALID,
            cls.CAPABILITY_INVALID,
            cls.VERSION_INVALID,
            cls.MAPPING_INVALID,
            cls.NOT_OPEN,
            cls.ALLOCATION_UNKNOWN,
            cls.BINDING_UNKNOWN,
            cls.EVIDENCE_CLASS_VIOLATION,
            cls.REPLAY_DIVERGENCE,
        )


def bounded_detail(value: object) -> str:
    """Bound any diagnostic to the frozen detail limit."""
    text = str(value)
    if len(text) <= _DETAIL_LIMIT:
        return text
    return text[: _DETAIL_LIMIT - 3] + "..."
