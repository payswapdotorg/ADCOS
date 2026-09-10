"""ADCOS execution-plan typed errors (M006 — Execution Plan).

The frozen ``plan-*`` reason vocabulary (fail-closed everywhere; adding
a code is a deliberate vocabulary change on this M006 surface):

- ``plan-invalid-input`` — malformed input at any public boundary;
- ``plan-vocabulary`` — a value outside a frozen vocabulary;
- ``plan-contract-not-plannable`` — the contract's lifecycle state is
  not plan-translatable (INTENT has no accepted offers; terminal and
  post-execution evaluation states never plan);
- ``plan-offer-not-accepted`` — a segment proposes an offer reference
  that is not a verbatim member of the contract's accepted offers;
- ``plan-constraint-weakened`` — LOCK-108 fail-closed: a hard contract
  constraint is dropped, relaxed or re-interpreted on a plan presented
  against the contract;
- ``plan-constraint-mismatch`` — the plan's LOCK-108 constraint
  fingerprint does not match the constraint set it carries (tamper
  evidence at the construction/deserialization boundary);
- ``plan-temporal-invalid`` — a temporal value is malformed, an
  interval is impossible, a plan window escapes the contract validity,
  or a transition instant falls outside the plan window;
- ``plan-id-mismatch`` — a supplied content-derived id does not match
  the derived identity (tamper evidence), or plan attribution does not
  match the contract identity;
- ``plan-invalid-transition`` — an illegal segment-state transition;
- ``plan-segment-unknown`` — a transition addressed at a segment the
  plan does not carry;
- ``plan-segment-terminal`` — a transition out of a terminal segment
  state (RELEASED never transitions);
- ``plan-duplicate-segment`` — two segments with the identical
  content-derived core on one plan;
- ``plan-no-primary-segment`` — a plan with no primary realization
  segment;
- ``plan-tie-break-invalid`` — an invalid declared tie-breaking rule
  (LOCK-111: deterministic, injected, declared);
- ``plan-secret-rejected`` — LOCK-119: secret-shaped material
  rejected at the boundary.
"""

from __future__ import annotations


class ExecutionPlanError(ValueError):
    """Fail-closed execution-plan error with a stable machine-readable
    ``code`` and deterministic ``detail`` (secret material is never
    echoed; raw exception text never leaks into stored state)."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class ExecutionPlanReason:
    """The frozen M006 execution-plan reason vocabulary."""

    INVALID_INPUT = "plan-invalid-input"
    VOCABULARY = "plan-vocabulary"
    NOT_PLANNABLE = "plan-contract-not-plannable"
    OFFER_NOT_ACCEPTED = "plan-offer-not-accepted"
    CONSTRAINT_WEAKENED = "plan-constraint-weakened"
    CONSTRAINT_MISMATCH = "plan-constraint-mismatch"
    TEMPORAL_INVALID = "plan-temporal-invalid"
    ID_MISMATCH = "plan-id-mismatch"
    INVALID_TRANSITION = "plan-invalid-transition"
    SEGMENT_UNKNOWN = "plan-segment-unknown"
    SEGMENT_TERMINAL = "plan-segment-terminal"
    DUPLICATE_SEGMENT = "plan-duplicate-segment"
    NO_PRIMARY = "plan-no-primary-segment"
    TIE_BREAK_INVALID = "plan-tie-break-invalid"
    SECRET_REJECTED = "plan-secret-rejected"

    @classmethod
    def values(cls) -> tuple:
        return (
            cls.INVALID_INPUT,
            cls.VOCABULARY,
            cls.NOT_PLANNABLE,
            cls.OFFER_NOT_ACCEPTED,
            cls.CONSTRAINT_WEAKENED,
            cls.CONSTRAINT_MISMATCH,
            cls.TEMPORAL_INVALID,
            cls.ID_MISMATCH,
            cls.INVALID_TRANSITION,
            cls.SEGMENT_UNKNOWN,
            cls.SEGMENT_TERMINAL,
            cls.DUPLICATE_SEGMENT,
            cls.NO_PRIMARY,
            cls.TIE_BREAK_INVALID,
            cls.SECRET_REJECTED,
        )
