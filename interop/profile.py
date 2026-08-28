"""WORK-037 profile validation: the pure fail-closed checks.

The profile layer VALIDATES and COMPOSES; it never mints authority
objects.  This module holds the pure predicates over the frozen
vocabularies:

- :func:`validate_profile` -- the full fail-closed declaration check
  (types, vocabulary, five components exactly once, family ownership,
  the complete seven reference points, digest coherence);
- :func:`reference_points_for_component` -- the frozen ownership map
  accessor;
- :func:`profile_complete` -- the pure completion predicate used by
  the evidence model's class-A report.

Everything is a pure function of explicit inputs -- no clock, no OS
state, no network.
"""

from __future__ import annotations

from typing import Tuple

from .errors import InteropError, InteropReasonCode
from .model import (
    COMPONENT_FAMILY,
    COMPONENT_REFERENCE_POINTS,
    ComponentBinding,
    ProfileComponentKind,
    ProfileDeclaration,
    ReferencePointKind,
    REQUIRED_REFERENCE_POINTS,
)

__all__ = [
    "validate_profile",
    "reference_points_for_component",
    "profile_complete",
]


def reference_points_for_component(component_kind: str) -> Tuple[str, ...]:
    """The frozen component -> reference-point ownership map accessor."""
    if component_kind not in ProfileComponentKind.values():
        raise InteropError(
            InteropReasonCode.COMPONENT_MISMATCH,
            "unknown component kind: %r" % (component_kind,),
        )
    return COMPONENT_REFERENCE_POINTS[component_kind]


def validate_profile(profile: ProfileDeclaration) -> str:
    """Validate a profile declaration fail-closed; return its digest.

    Re-runs the complete structural check (the record constructors
    already enforce most invariants; this is the belt-and-braces
    composition check the scenario and the evidence model both call
    before anything is exercised).  Raises :class:`InteropError` with
    a typed reason on the FIRST violation.
    """
    if not isinstance(profile, ProfileDeclaration):
        raise InteropError(
            InteropReasonCode.INVALID_INPUT,
            "profile must be a ProfileDeclaration (got %s)"
            % (type(profile).__name__,),
        )

    # 1. The five components, each exactly once, each bound to the
    #    family the frozen map assigns it.
    kinds = tuple(b.component_kind for b in profile.bindings)
    for expected in ProfileComponentKind.values():
        if kinds.count(expected) != 1:
            raise InteropError(
                InteropReasonCode.PROFILE_INVALID,
                "component %r must be bound exactly once (found %d)"
                % (expected, kinds.count(expected)),
            )
    for binding in profile.bindings:
        if not isinstance(binding, ComponentBinding):
            raise InteropError(
                InteropReasonCode.INVALID_INPUT,
                "profile bindings must be ComponentBinding records",
            )
        if binding.family != COMPONENT_FAMILY[binding.component_kind]:
            raise InteropError(
                InteropReasonCode.COMPONENT_MISMATCH,
                "component %r is bound to family %r but must bind %r"
                % (
                    binding.component_kind,
                    binding.family,
                    COMPONENT_FAMILY[binding.component_kind],
                ),
            )

    # 2. The complete seven reference points, each owned by exactly
    #    one component (the ownership map is DATA; the profile must
    #    not re-declare ownership).
    if tuple(profile.required_reference_points) != REQUIRED_REFERENCE_POINTS:
        raise InteropError(
            InteropReasonCode.REFERENCE_POINT_UNBOUND,
            "the complete profile requires exactly the frozen seven "
            "reference points",
        )
    owned: Tuple[str, ...] = ()
    for component_kind in ProfileComponentKind.values():
        owned = owned + COMPONENT_REFERENCE_POINTS[component_kind]
    if sorted(owned) != sorted(REQUIRED_REFERENCE_POINTS):
        raise InteropError(
            InteropReasonCode.REFERENCE_POINT_UNBOUND,
            "the frozen ownership map must cover every required "
            "reference point exactly once",
        )

    # 3. Digest coherence (canonical bytes are deterministic; the
    #    recomputed digest must equal the declared one).
    digest = profile.digest()
    if not digest or len(digest) != 64:
        raise InteropError(
            InteropReasonCode.PROFILE_INVALID,
            "profile digest must be a 64-hex sha256 (got %r)" % (digest,),
        )
    return digest


def profile_complete(*, validated: bool, legs_verified: int) -> bool:
    """The pure completion predicate for the class-A report.

    A complete profile-level architecture-conformance posture is a
    VALIDATED declaration plus all four scenario legs verified (the
    mixed-access demonstration at class-B strength).  It says NOTHING
    about the real lab: class C is a separate track that only the
    real-lab gate may close.
    """
    if not isinstance(validated, bool):
        raise InteropError(
            InteropReasonCode.INVALID_INPUT,
            "validated must be a bool",
        )
    if isinstance(legs_verified, bool) or not isinstance(legs_verified, int):
        raise InteropError(
            InteropReasonCode.INVALID_INPUT,
            "legs_verified must be an integer",
        )
    return validated and legs_verified >= 4
