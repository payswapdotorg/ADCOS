"""ADCOS replan typed errors (M008 — Replan and Failover).

The frozen ``replan-*`` reason vocabulary (fail-closed everywhere;
adding a code is a deliberate vocabulary change on this M008 surface):

- ``replan-invalid-input`` — malformed input at any public boundary;
- ``replan-vocabulary`` — a value outside a frozen vocabulary;
- ``replan-contract-not-replannable`` — the contract's lifecycle state
  carries no active realization to replan (INTENT/OFFER_SELECTED have
  no engaged realization; the post-execution commercial walk and
  terminal states never replan);
- ``replan-contract-terminal`` — the contract is terminal; terminal
  contracts never replan;
- ``replan-constraint-weakened`` — LOCK-108 fail-closed: a candidate
  realization drops, relaxes or re-interprets a hard contract
  constraint (a candidate that weakens/drops ANY hard constraint is
  REJECTED with this typed reason);
- ``replan-constraint-mismatch`` — the LOCK-108 constraint fingerprint
  does not match the constraint set a record carries (tamper evidence
  at the construction/deserialization boundary);
- ``replan-no-candidates`` — a replan evaluation with zero candidate
  realizations (fail-closed: there is nothing to decide silently);
- ``replan-candidate-invalid`` — a malformed candidate realization;
- ``replan-realization-terminal`` — the realization being replaced is
  already terminal (FAILED/SUPERSEDED realizations never replan; a
  deliberately terminated session is not a replan surface);
- ``replan-realization-not-established`` — the session surface has no
  established realization to replan (REQUESTED/AUTHORIZED sessions);
- ``replan-silent-replacement`` — the WORK-012 reconnect discipline
  violated: a route change without the explicit reconnect event
  carrying BOTH the old AND the new route references;
- ``replan-temporal-invalid`` — a malformed injected instant or a
  trigger instant outside the contract validity;
- ``replan-id-mismatch`` — a supplied content-derived id does not match
  the derived identity (tamper evidence), or an attribution does not
  match the owning contract identity;
- ``replan-tie-break-invalid`` — an invalid declared tie-breaking rule
  (LOCK-111: deterministic, injected, declared — never wall-clock);
- ``replan-decision-terminal`` — an effect addressed at a decision
  surface that is already terminal;
- ``replan-bridge-inapplicable`` — the decision's contract-recording
  bridge has no legal edge in the contract's own frozen transition
  table (mirrors the M005 ``BRIDGE_NOT_APPLICABLE`` honesty);
- ``replan-secret-rejected`` — LOCK-119: secret-shaped material
  rejected at the boundary.

Exception isolation: the public surface raises ONLY this typed error;
consumed-domain errors (``ContractError`` and friends) are wrapped at
each boundary with their deterministic text preserved in ``detail`` —
no raw exception text leaks into stored state.
"""

from __future__ import annotations


class ReplanError(ValueError):
    """Fail-closed replan error with a stable machine-readable ``code``
    and deterministic ``detail`` (secret material is never echoed; raw
    exception text never leaks into stored state)."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class ReplanReason:
    """The frozen M008 replan reason vocabulary."""

    INVALID_INPUT = "replan-invalid-input"
    VOCABULARY = "replan-vocabulary"
    NOT_REPLANNABLE = "replan-contract-not-replannable"
    CONTRACT_TERMINAL = "replan-contract-terminal"
    CONSTRAINT_WEAKENED = "replan-constraint-weakened"
    CONSTRAINT_MISMATCH = "replan-constraint-mismatch"
    NO_CANDIDATES = "replan-no-candidates"
    CANDIDATE_INVALID = "replan-candidate-invalid"
    REALIZATION_TERMINAL = "replan-realization-terminal"
    REALIZATION_NOT_ESTABLISHED = "replan-realization-not-established"
    SILENT_REPLACEMENT = "replan-silent-replacement"
    TEMPORAL_INVALID = "replan-temporal-invalid"
    ID_MISMATCH = "replan-id-mismatch"
    TIE_BREAK_INVALID = "replan-tie-break-invalid"
    DECISION_TERMINAL = "replan-decision-terminal"
    BRIDGE_INAPPLICABLE = "replan-bridge-inapplicable"
    SECRET_REJECTED = "replan-secret-rejected"

    @classmethod
    def values(cls) -> tuple:
        return (
            cls.INVALID_INPUT,
            cls.VOCABULARY,
            cls.NOT_REPLANNABLE,
            cls.CONTRACT_TERMINAL,
            cls.CONSTRAINT_WEAKENED,
            cls.CONSTRAINT_MISMATCH,
            cls.NO_CANDIDATES,
            cls.CANDIDATE_INVALID,
            cls.REALIZATION_TERMINAL,
            cls.REALIZATION_NOT_ESTABLISHED,
            cls.SILENT_REPLACEMENT,
            cls.TEMPORAL_INVALID,
            cls.ID_MISMATCH,
            cls.TIE_BREAK_INVALID,
            cls.DECISION_TERMINAL,
            cls.BRIDGE_INAPPLICABLE,
            cls.SECRET_REJECTED,
        )
