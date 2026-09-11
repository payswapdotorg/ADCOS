"""ADCOS local-first typed errors (M016 — Local-First and Offline
Operation).

The frozen ``localfirst-*`` reason vocabulary (fail-closed everywhere;
adding a code is a deliberate vocabulary change on this M016 surface):

- ``localfirst-invalid-input`` — malformed input at any public boundary;
- ``localfirst-vocabulary`` — a value outside a frozen vocabulary
  (operation kind, admission outcome, episode state, evidence kind);
- ``localfirst-temporal-invalid`` — a malformed injected instant;
- ``localfirst-id-mismatch`` — a supplied content-derived id does not
  match the derived identity (tamper evidence), or an attribution does
  not match (snapshot vs owning contract, operation vs episode, journal
  vs episode);
- ``localfirst-journal-divergence`` — the deterministic offline journal
  failed its replay fold (a sequence gap/conflict, a record after the
  episode exit, a duplicate admitted subject, or — the core M016
  discipline — an ADMITTED operation whose instant lies OUTSIDE the
  freshness window it carries: a local state past its declared
  freshness bound never silently authorizes, so a forged admitted
  record fails the fold);
- ``localfirst-authority-stale`` — the fail-closed stale-authority
  rejection (the charter's core typed reason): the local authority
  snapshot is PAST its declared freshness bound at the decision
  instant, and the admission is rejected — never a silent allow;
- ``localfirst-authority-not-yet-valid`` — the symmetric fail-closed
  rejection: the decision instant PRECEDES the freshness window's
  opening (the snapshot is not yet the authority's declaration), and
  the admission is rejected — never a silent allow;
- ``localfirst-constraint-weakened`` — LOCK-108 across the offline
  boundary: a local admission or a resynchronization candidate drops,
  relaxes or re-interprets a hard contract constraint (the consumed
  M008 replan gate's typed rejection surfaced on this surface's own
  vocabulary, citing the specific kinds);
- ``localfirst-constraint-mismatch`` — the LOCK-108 constraint
  fingerprint does not match the contract's own (tampered or forged
  authority material fails closed — a snapshot or journal record whose
  claimed constraint material does not reproduce the contract's
  fingerprint);
- ``localfirst-resolution-invalid`` — an invalid declared
  conflict-resolution rule (the LOCK-111 class: deterministic,
  declared, injected, recorded — content keys only, never temporal,
  never random; must end with the total-order key);
- ``localfirst-episode-closed`` — the partition episode is closed (the
  journal no longer accepts operations — the exit is final; a new
  partition opens a new episode);
- ``localfirst-composition`` — a consumed accepted authority rejected
  the composition drive (the consumed M008 gate, the consumed M015
  runtime, the consumed M002 contract material — the consumed engine's
  typed rejection wrapped with its deterministic text preserved, never
  a foreign exception type, never raw exception text into stored
  state);
- ``localfirst-secret-rejected`` — LOCK-119: secret-shaped material
  rejected at the boundary.

Exception isolation: the public surface raises ONLY this typed error;
consumed-domain errors (``ReplanError``, ``ResilienceError``,
``ContractError``) are wrapped at each boundary with their
deterministic text preserved in ``detail`` — no raw exception text
leaks into stored state.
"""

from __future__ import annotations


class LocalFirstError(ValueError):
    """Fail-closed local-first error with a stable machine-readable
    ``code`` and deterministic ``detail`` (secret material is never
    echoed; raw exception text never leaks into stored state)."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class LocalFirstReason:
    """The frozen M016 local-first reason vocabulary."""

    INVALID_INPUT = "localfirst-invalid-input"
    VOCABULARY = "localfirst-vocabulary"
    TEMPORAL_INVALID = "localfirst-temporal-invalid"
    ID_MISMATCH = "localfirst-id-mismatch"
    JOURNAL_DIVERGENCE = "localfirst-journal-divergence"
    AUTHORITY_STALE = "localfirst-authority-stale"
    AUTHORITY_NOT_YET_VALID = "localfirst-authority-not-yet-valid"
    CONSTRAINT_WEAKENED = "localfirst-constraint-weakened"
    CONSTRAINT_MISMATCH = "localfirst-constraint-mismatch"
    RESOLUTION_INVALID = "localfirst-resolution-invalid"
    EPISODE_CLOSED = "localfirst-episode-closed"
    COMPOSITION = "localfirst-composition"
    SECRET_REJECTED = "localfirst-secret-rejected"

    @classmethod
    def values(cls) -> tuple:
        return (
            cls.INVALID_INPUT,
            cls.VOCABULARY,
            cls.TEMPORAL_INVALID,
            cls.ID_MISMATCH,
            cls.JOURNAL_DIVERGENCE,
            cls.AUTHORITY_STALE,
            cls.AUTHORITY_NOT_YET_VALID,
            cls.CONSTRAINT_WEAKENED,
            cls.CONSTRAINT_MISMATCH,
            cls.RESOLUTION_INVALID,
            cls.EPISODE_CLOSED,
            cls.COMPOSITION,
            cls.SECRET_REJECTED,
        )
