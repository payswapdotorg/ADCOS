"""ADCOS resilience typed errors (M015 — Execution Resilience Runtime).

The frozen ``resilience-*`` reason vocabulary (fail-closed everywhere;
adding a code is a deliberate vocabulary change on this M015 surface):

- ``resilience-invalid-input`` — malformed input at any public boundary;
- ``resilience-vocabulary`` — a value outside a frozen vocabulary
  (runtime state, event kind, failover trigger kind, evidence kind);
- ``resilience-transition-illegal`` — an illegal runtime lifecycle
  transition (the deterministic state machine, fail-closed);
- ``resilience-session-terminal`` — the runtime session is terminal
  (FAILED/TERMINATED sessions never transition);
- ``resilience-realization-not-established`` — the runtime session
  carries no established realization to replan yet (PENDING runtimes
  have no realization references);
- ``resilience-silent-replacement`` — the WORK-012 explicit-reconnect
  discipline violated (re-expressed on this 1.1 authority): a route or
  realization change without the explicit reconnect pair naming BOTH
  the old AND the new references;
- ``resilience-constraint-weakened`` — LOCK-108 fail-closed: a
  handover/failover candidate drops, relaxes or re-interprets a hard
  contract constraint (the consumed replan gate's typed rejection
  surfaced on this surface's own vocabulary);
- ``resilience-constraint-mismatch`` — the LOCK-108 constraint
  fingerprint does not match the constraint set a record carries
  (tamper evidence);
- ``resilience-no-candidates`` — a failover orchestration with zero
  alternative realizations (fail-closed: there is nothing to select
  silently; LOCK-115: a simple deployment need not carry
  alternatives, and the typed outcome says so honestly);
- ``resilience-tie-break-invalid`` — an invalid declared tie-breaking
  rule (LOCK-111: deterministic, injected, declared — content keys
  only, never wall-clock);
- ``resilience-temporal-invalid`` — a malformed injected instant;
- ``resilience-id-mismatch`` — a supplied content-derived id does not
  match the derived identity (tamper evidence), or an attribution does
  not match (runtime session vs owning contract, plan vs contract,
  adopted artifacts vs the new realization references);
- ``resilience-journal-divergence`` — the deterministic runtime journal
  failed its replay fold (sequence gap/conflict, an illegal state
  chain, or a route change outside the explicit reconnect discipline);
- ``resilience-replan-composition`` — the accepted M008 replan kernel
  rejected the composition drive (the consumed engine's typed
  rejection wrapped with its deterministic text preserved — never a
  foreign exception type, never raw exception text into stored state);
- ``resilience-secret-rejected`` — LOCK-119: secret-shaped material
  rejected at the boundary.

Exception isolation: the public surface raises ONLY this typed error;
consumed-domain errors (``ReplanError``, ``ExecutionPlanError``,
``ContractError``) are wrapped at each boundary with their
deterministic text preserved in ``detail`` — no raw exception text
leaks into stored state.
"""

from __future__ import annotations


class ResilienceError(ValueError):
    """Fail-closed resilience error with a stable machine-readable
    ``code`` and deterministic ``detail`` (secret material is never
    echoed; raw exception text never leaks into stored state)."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class ResilienceReason:
    """The frozen M015 resilience reason vocabulary."""

    INVALID_INPUT = "resilience-invalid-input"
    VOCABULARY = "resilience-vocabulary"
    TRANSITION_ILLEGAL = "resilience-transition-illegal"
    SESSION_TERMINAL = "resilience-session-terminal"
    REALIZATION_NOT_ESTABLISHED = "resilience-realization-not-established"
    SILENT_REPLACEMENT = "resilience-silent-replacement"
    CONSTRAINT_WEAKENED = "resilience-constraint-weakened"
    CONSTRAINT_MISMATCH = "resilience-constraint-mismatch"
    NO_CANDIDATES = "resilience-no-candidates"
    TIE_BREAK_INVALID = "resilience-tie-break-invalid"
    TEMPORAL_INVALID = "resilience-temporal-invalid"
    ID_MISMATCH = "resilience-id-mismatch"
    JOURNAL_DIVERGENCE = "resilience-journal-divergence"
    REPLAN_COMPOSITION = "resilience-replan-composition"
    SECRET_REJECTED = "resilience-secret-rejected"

    @classmethod
    def values(cls) -> tuple:
        return (
            cls.INVALID_INPUT,
            cls.VOCABULARY,
            cls.TRANSITION_ILLEGAL,
            cls.SESSION_TERMINAL,
            cls.REALIZATION_NOT_ESTABLISHED,
            cls.SILENT_REPLACEMENT,
            cls.CONSTRAINT_WEAKENED,
            cls.CONSTRAINT_MISMATCH,
            cls.NO_CANDIDATES,
            cls.TIE_BREAK_INVALID,
            cls.TEMPORAL_INVALID,
            cls.ID_MISMATCH,
            cls.JOURNAL_DIVERGENCE,
            cls.REPLAN_COMPOSITION,
            cls.SECRET_REJECTED,
        )
