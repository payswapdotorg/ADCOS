"""ADCOS recovery typed errors (M017 — Disaster Recovery and State
Reconciliation).

The frozen ``recovery-*`` reason vocabulary (fail-closed everywhere;
adding a code is a deliberate vocabulary change on this M017 surface):

- ``recovery-invalid-input`` — malformed input at any public boundary;
- ``recovery-vocabulary`` — a value outside a frozen vocabulary (plane
  kind, drill step kind, restore outcome, reconciliation resolution);
- ``recovery-temporal-invalid`` — a malformed injected instant;
- ``recovery-id-mismatch`` — a supplied content-derived id does not
  match the derived identity (tamper evidence), or an attribution does
  not match (a recovery point vs its plane subject, a journal record vs
  its owning contract, a drill plan vs its planes);
- ``recovery-snapshot-unverifiable`` — the fail-closed snapshot
  verification (the charter's core typed reason): a recovery point
  whose integrity cannot be verified — unparseable material, a missing
  provenance envelope, an identity that does not re-derive, or a
  payload whose records do not re-derive their own content identities
  — is REJECTED WHOLE.  Never partially trusted, never best-effort
  loaded;
- ``recovery-restore-diverged`` — the restored plane does not equal the
  pre-failure plane byte-exactly AND the divergence is not explicitly
  disclosed and reconciled (a divergence silently absorbed fails
  closed);
- ``recovery-history-fabricated`` — LOCK-106 no-history-fabrication
  violation: a recovered record does not preserve its original
  content-derived identity, a gapless journal sequence was silently
  renumbered, or a recovery point claims pre-failure content it cannot
  evidence;
- ``recovery-rto-exceeded`` — the recovery-time bound (a DECLARED
  deterministic operation count — journal appends, folds,
  verifications) was exceeded by the drill's own measured operation
  counts (LOCK-119: bounds are counts, never wall clock);
- ``recovery-plane-mismatch`` — cross-plane reconciliation detected a
  plane pair that does not converge and cannot be typed/reconciled
  (attribution mismatch, an unresolved cross-plane evidence link, a
  missing LOCK-106 evidence record);
- ``recovery-composition`` — a consumed accepted authority rejected the
  composition drive (the consumed M015 runtime, the consumed M016
  journal, the consumed M002 contract material, the consumed evidence
  typing — the consumed surface's typed rejection wrapped with its
  deterministic text preserved, never a foreign exception type, never
  raw exception text into stored state);
- ``recovery-secret-rejected`` — LOCK-119: secret-shaped material
  rejected at the boundary.

Exception isolation: the public surface raises ONLY this typed error;
consumed-domain errors (``ResilienceError``, ``LocalFirstError``,
``ContractError``, ``EvidenceError``, ``ReplanError``) are wrapped at
each boundary with their deterministic text preserved in ``detail`` —
no raw exception text leaks into stored state.
"""

from __future__ import annotations


class RecoveryError(ValueError):
    """Fail-closed recovery error with a stable machine-readable
    ``code`` and deterministic ``detail`` (secret material is never
    echoed; raw exception text never leaks into stored state)."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class RecoveryReason:
    """The frozen M017 recovery reason vocabulary."""

    INVALID_INPUT = "recovery-invalid-input"
    VOCABULARY = "recovery-vocabulary"
    TEMPORAL_INVALID = "recovery-temporal-invalid"
    ID_MISMATCH = "recovery-id-mismatch"
    SNAPSHOT_UNVERIFIABLE = "recovery-snapshot-unverifiable"
    RESTORE_DIVERGED = "recovery-restore-diverged"
    HISTORY_FABRICATED = "recovery-history-fabricated"
    RTO_EXCEEDED = "recovery-rto-exceeded"
    PLANE_MISMATCH = "recovery-plane-mismatch"
    COMPOSITION = "recovery-composition"
    SECRET_REJECTED = "recovery-secret-rejected"

    @classmethod
    def values(cls) -> tuple:
        return (
            cls.INVALID_INPUT,
            cls.VOCABULARY,
            cls.TEMPORAL_INVALID,
            cls.ID_MISMATCH,
            cls.SNAPSHOT_UNVERIFIABLE,
            cls.RESTORE_DIVERGED,
            cls.HISTORY_FABRICATED,
            cls.RTO_EXCEEDED,
            cls.PLANE_MISMATCH,
            cls.COMPOSITION,
            cls.SECRET_REJECTED,
        )
