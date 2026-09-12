"""ADCOS credential-lifecycle typed errors (M018 — Credential and
Key Lifecycle Operations).

The frozen ``credential-*`` reason vocabulary (fail-closed everywhere;
adding a code is a deliberate vocabulary change on this M018 surface):

- ``credential-invalid-input`` — malformed input at any public boundary;
- ``credential-vocabulary`` — a value outside a frozen vocabulary
  (operation kind, inventory break kind, propagation shape);
- ``credential-temporal-invalid`` — a malformed injected instant;
- ``credential-id-mismatch`` — a supplied content-derived id does not
  match the derived identity (tamper evidence), or an attribution does
  not match (journal vs owning node, round vs propagated revocation);
- ``credential-journal-divergence`` — the deterministic lifecycle
  operation journal failed its replay fold (a sequence gap/conflict, a
  duplicate position, an unrecorded admitted-set transition between
  consecutive operations, or a replayed journal whose records no
  longer re-derive their identities);
- ``credential-rotation-nonatomic`` — the zero-coverage-gap kernel
  rejected an admitted-set transition that is not an exact single
  flip: a rotation record whose before/after sets carry an
  intermediate window (both generations, or neither), or an authority
  outcome the drill could not verify as one atomic flip;
- ``credential-propagation-unconverged`` — the declared ROUND-COUNT
  convergence bound was exceeded: revocation propagation did not
  reach every declared consumer within the declared round count
  (never a wall-clock bound; fail closed);
- ``credential-inventory-incomplete`` — the inventory audit failed
  closed: an admitted credential without a complete lifecycle record
  chain (the typed break kind cites the specific hole — never a
  warning, never a silent pass);
- ``credential-lifecycle-illegal`` — an illegal lifecycle operation on
  this surface (revoking an unknown/terminal credential, a propagation
  without its revocation, a drill sequencing violation), or a consumed
  identity/M014 lifecycle rejection surfaced on this vocabulary;
- ``credential-composition`` — a consumed accepted authority rejected
  the composition drive (the accepted ``identity/`` service, the M014
  ``identity.convergence`` gates, the accepted ``federation/``
  admission runtime, the frozen ``client/`` protocol, the accepted
  ``evidence/`` store — the consumed engine's typed rejection wrapped
  with its deterministic text preserved, never a foreign exception
  type, never raw exception text into stored state);
- ``credential-secret-rejected`` — LOCK-119: secret-shaped material
  rejected at the boundary.

Exception isolation: the public surface raises ONLY this typed error;
consumed-domain errors (``IdentityError``, ``IdentityConvergenceError``,
``ConvergenceError``, ``ClientError``, ``EvidenceError`` — all carrying
``code``/``detail``) are wrapped at each boundary with their
deterministic text preserved in ``detail`` — no raw exception text
leaks into stored state, and no secret material is ever echoed.
"""

from __future__ import annotations


class CredentialLifecycleError(ValueError):
    """Fail-closed credential-lifecycle error with a stable
    machine-readable ``code`` and deterministic ``detail`` (secret
    material is never echoed; raw exception text never leaks into
    stored state)."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail

    @property
    def reason(self) -> str:
        return self.code


class CredentialLifecycleReason:
    """The frozen M018 credential-lifecycle reason vocabulary."""

    INVALID_INPUT = "credential-invalid-input"
    VOCABULARY = "credential-vocabulary"
    TEMPORAL_INVALID = "credential-temporal-invalid"
    ID_MISMATCH = "credential-id-mismatch"
    JOURNAL_DIVERGENCE = "credential-journal-divergence"
    ROTATION_NONATOMIC = "credential-rotation-nonatomic"
    PROPAGATION_UNCONVERGED = "credential-propagation-unconverged"
    INVENTORY_INCOMPLETE = "credential-inventory-incomplete"
    LIFECYCLE_ILLEGAL = "credential-lifecycle-illegal"
    COMPOSITION = "credential-composition"
    SECRET_REJECTED = "credential-secret-rejected"

    @classmethod
    def values(cls) -> tuple:
        return (
            cls.INVALID_INPUT,
            cls.VOCABULARY,
            cls.TEMPORAL_INVALID,
            cls.ID_MISMATCH,
            cls.JOURNAL_DIVERGENCE,
            cls.ROTATION_NONATOMIC,
            cls.PROPAGATION_UNCONVERGED,
            cls.INVENTORY_INCOMPLETE,
            cls.LIFECYCLE_ILLEGAL,
            cls.COMPOSITION,
            cls.SECRET_REJECTED,
        )
