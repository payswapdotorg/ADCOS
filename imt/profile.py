"""WORK-038 profile validation: pure, fail-closed, delegated.

The validators answer exactly the WORK-038 boundary questions:

- is the declaration a well-formed future profile (shape validation,
  all semantics delegated to the ACCEPTED authorities)?
- which WORK-002 class does the technology identifier carry (KNOWN /
  UNKNOWN_BUT_WELL_FORMED -- delegated to
  ``adapters.validation.classify_access_technology_id``; the registry
  is read-only and never mutated here)?
- is the profile complete for the work item's acceptance (the
  declaration validated AND the synthetic conformance contract
  exercised)?

No second authority exists in this module: it validates data, it
never decides routing/session/resource/policy questions, and it never
constructs authority state.
"""

from __future__ import annotations

from typing import Optional

from adapters.validation import (
    AccessTechnologyClass,
    classify_access_technology_id,
)

from .errors import FutureError, FutureReasonCode
from .model import FutureProfileDeclaration

__all__ = [
    "validate_future_profile",
    "classify_technology_id",
    "profile_complete",
]


def classify_technology_id(technology_id: object) -> str:
    """Classify a technology id through the ACCEPTED WORK-002 rule.

    Delegation, never re-implementation: the classification is the
    registry's own verdict (KNOWN / UNKNOWN_BUT_WELL_FORMED /
    INVALID).  A malformed id raises the future-profile typed error
    (the INVALID class is not a value this profile can carry).
    """
    classification = classify_access_technology_id(technology_id)
    if classification == AccessTechnologyClass.INVALID:
        raise FutureError(
            FutureReasonCode.TECHNOLOGY_ID_INVALID,
            "technology id %r is malformed (well-formed unknown future "
            "ids are preserved; malformed ids fail closed)" % (technology_id,),
        )
    return classification


def validate_future_profile(
    profile: object,
) -> FutureProfileDeclaration:
    """Validate a future-profile declaration (fail closed).

    The declaration is already validated at construction (the record
    is a fail-closed value type); this function adds the work-item
    completeness invariants that construction cannot check in
    isolation: at least one capability reference must be carried (a
    profile that exposes nothing exercises no additive surface), and
    the record must be exactly a ``FutureProfileDeclaration``.
    """
    if not isinstance(profile, FutureProfileDeclaration):
        raise FutureError(
            FutureReasonCode.PROFILE_INVALID,
            "profile must be a FutureProfileDeclaration (got %s)"
            % type(profile).__name__,
        )
    if not profile.capability_references:
        raise FutureError(
            FutureReasonCode.PROFILE_INVALID,
            "a future profile carries at least one capability "
            "reference (the additive surface under test)",
        )
    classification = classify_technology_id(profile.technology_id)
    if classification not in (
        AccessTechnologyClass.KNOWN,
        AccessTechnologyClass.UNKNOWN_BUT_WELL_FORMED,
    ):
        raise FutureError(
            FutureReasonCode.TECHNOLOGY_ID_INVALID,
            "technology id %r class %r is not registrable as data"
            % (profile.technology_id, classification),
        )
    return profile


def profile_complete(
    *, validated: bool, contract_exercised: bool
) -> bool:
    """The work-item completeness verdict (pure).

    A complete WORK-038 profile run: the declaration validated AND the
    synthetic conformance contract (the nine WORK-016 operations over
    the composed runtime) exercised.  Anything less is not this work
    item's acceptance shape.
    """
    return bool(validated) and bool(contract_exercised)


def registry_untouched(*, digest_before: str, digest_after: str) -> bool:
    """Whether the WORK-002 access-profile registry stayed byte-stable
    across a run (the no-core-schema-change fact, as data)."""
    if not isinstance(digest_before, str) or not isinstance(digest_after, str):
        raise FutureError(
            FutureReasonCode.INVALID_INPUT,
            "registry digests must be strings",
        )
    return digest_before == digest_after


def unknown_id_gained_no_authority(
    *, technology_id: str, classification: str, still_unknown: Optional[bool] = None
) -> bool:
    """Whether an unknown-but-well-formed technology id preserved its
    open-world standing (never coerced, never promoted into the
    registry).

    The verdict is computed from the ACCEPTED classification surface
    itself: the id must classify UNKNOWN_BUT_WELL_FORMED and must
    remain absent from the known-id set.  ``still_unknown`` (when
    supplied) must agree with the recomputed fact -- disagreement is a
    fail-closed integrity error, not a silent pass.
    """
    from adapters.validation import known_access_technology_ids

    current = classify_access_technology_id(technology_id)
    remains_unknown = technology_id not in known_access_technology_ids()
    verdict = (
        current == AccessTechnologyClass.UNKNOWN_BUT_WELL_FORMED
        and current == classification
        and remains_unknown
    )
    if still_unknown is not None and bool(still_unknown) is not verdict:
        raise FutureError(
            FutureReasonCode.INVALID_INPUT,
            "unknown-id authority verdict disagrees with the observed "
            "facts (recorded %r, recomputed %r)" % (still_unknown, verdict),
        )
    return verdict
