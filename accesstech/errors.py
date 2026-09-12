"""ADCOS access-technology domain typed errors (M020).

The fail-closed typed-error vocabulary of the ``accesstech/`` domain
(the exception-isolation discipline every accepted domain carries):
every malformed, inconsistent, degenerate or contradictory declaration
raises :class:`AccessTechError` with a typed :class:`AccessTechReason`
code and a deterministic, detail-carrying message — never a warning,
never a raw consumer exception leaking into stored state (consumed-
domain errors are wrapped with their deterministic text preserved).
"""

from __future__ import annotations

from typing import Tuple


class AccessTechReason:
    """The typed rejection codes (fail closed on every surface)."""

    #: Caller-side shape/type errors (non-string ids, non-mappings,
    #: malformed instants, non-integer dimensions).
    INVALID_INPUT = "accesstech-invalid-input"

    #: A declared vocabulary member drifted outside a consumed frozen
    #: vocabulary (realization states, constraint kinds, handover
    #: kinds, bridge operations) — never silently coerced.
    VOCABULARY = "accesstech-vocabulary"

    #: An empty or unphysical envelope range (a dimension promising
    #: nothing, an availability-window sequence with no windows).
    ENVELOPE_DEGENERATE = "accesstech-envelope-degenerate"

    #: Inverted bounds or contradictory envelope content (floor above
    #: ceiling, a window ending before it starts, disordered or
    #: overlapping availability windows, a tampered content identity).
    ENVELOPE_INCONSISTENT = "accesstech-envelope-inconsistent"

    #: An illegal degradation ladder (undeclared mode names, mode
    #: states outside the consumed realization-state vocabulary,
    #: recovery edges inside a one-way ladder, rungs after a terminal
    #: state, a ladder without its explicit terminal rung).
    LADDER_ILLEGAL = "accesstech-ladder-illegal"

    #: An illegal handover characteristic declaration (a constraint-
    #: preservation set weaker or stronger than the accepted machinery's
    #: frozen full-set semantics, a silent-swap or contract-breaking
    #: characteristic — LOCK-108/LOCK-101 declarations never weaken).
    HANDOVER_ILLEGAL = "accesstech-handover-illegal"

    #: The technology-extension registration path rejected the inputs
    #: (cross-surface mismatches, duplicate registrations, a failed
    #: seam drive through the accepted adapter runtime).
    REGISTRATION_REJECTED = "accesstech-registration-rejected"

    #: A reconstructed record's content-derived identity does not match
    #: its content (tamper evidence at load).
    IDENTITY_MISMATCH = "accesstech-identity-mismatch"

    #: A canonical mapping does not satisfy the record grammar at
    #: deserialization time.
    SERIALIZATION_INVALID = "accesstech-serialization-invalid"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.INVALID_INPUT,
            cls.VOCABULARY,
            cls.ENVELOPE_DEGENERATE,
            cls.ENVELOPE_INCONSISTENT,
            cls.LADDER_ILLEGAL,
            cls.HANDOVER_ILLEGAL,
            cls.REGISTRATION_REJECTED,
            cls.IDENTITY_MISMATCH,
            cls.SERIALIZATION_INVALID,
        )


class AccessTechError(Exception):
    """The typed domain error (code + deterministic detail)."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__("%s: %s" % (code, detail))
        self.code = code
        self.detail = detail

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return "AccessTechError(%r, %r)" % (self.code, self.detail)


__all__ = ["AccessTechError", "AccessTechReason"]
