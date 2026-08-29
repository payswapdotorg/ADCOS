"""WORK-038 coexistence: the future profile through the W029 contracts.

The handoff requires reuse of the compatibility/upgrade contracts
(WORK-029).  The question answered here is exactly WORK-029's own:

    Can a node carrying the future-IMT profile coexist with a node
    that does not, and what changes at the compatibility seams?

The answer is delegated, never re-decided:

- the PROTOCOL VERSION line is untouched by the future profile: the
  profile adds no protocol major/minor, so the envelope disposition
  for the protocol major it speaks is the WORK-003 classification's
  own verdict (``upgrade.compatibility.envelope_version_disposition``
  -- delegated);
- mixed-version coexistence is ``upgrade.compatibility
  .negotiate_protocol_profile``'s own verdict over the caller's
  inventories (the additive-evolution floor; unknown majors fail
  closed exactly as WORK-003/W029 say);
- the capability dimension is WORK-005's own verdict: a peer that
  does NOT advertise the future capability never fabricates it --
  a requirement on an unknown-but-well-formed future capability id
  fails closed with the capability authority's own reason (additive
  data, never authoritative).

No second authority exists in this module: it composes the accepted
verdicts and returns them unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from upgrade.compatibility import (
    ProfileNegotiation,
    negotiate_protocol_profile,
)
from upgrade.model import ProtocolProfile

from .errors import FutureError, FutureReasonCode
from .model import FutureProfileDeclaration

__all__ = [
    "FUTURE_PROTOCOL_MAJOR",
    "FUTURE_PROFILE_PROTOCOL_PROFILE",
    "future_envelope_disposition",
    "coexistence_with_future_profile",
    "future_capability_negotiation",
]

#: The protocol major the future profile speaks: the CURRENT known
#: major.  The future profile is additive data at the adapter layer;
#: it introduces NO protocol-line change (a hypothetical future
#: protocol major would be a standards-body act, not this profile's).
FUTURE_PROTOCOL_MAJOR = 1

#: The protocol profile a future-profile-carrying node speaks: the
#: current major at the current additive head (WORK-029's
#: ``ProtocolProfile`` record, used read-only as DATA).
FUTURE_PROFILE_PROTOCOL_PROFILE = ProtocolProfile(
    major=FUTURE_PROTOCOL_MAJOR, max_minor=0,
)


def future_envelope_disposition(*, metadata: Optional[Any] = None) -> str:
    """The WORK-003 envelope-version verdict for the protocol major
    the future profile speaks (fully delegated).

    The discrimination this supports: adding the future adapter
    profile changes NOTHING at the envelope/protocol-version seam --
    the disposition is the current major's own classification
    (``known-compatible``), identical with or without the future
    profile registered.
    """
    from upgrade.compatibility import envelope_version_disposition

    return envelope_version_disposition(FUTURE_PROTOCOL_MAJOR, metadata)


def coexistence_with_future_profile(
    local: ProtocolProfile, peer: ProtocolProfile
) -> ProfileNegotiation:
    """Mixed-version coexistence with a future-profile-carrying node
    (fully delegated to WORK-029's negotiation).

    The future profile does not participate in the negotiation AT
    ALL: a node carrying it negotiates exactly as any node at the
    same protocol profile does (the adapter-layer addition is
    invisible to the protocol-version line -- the additive boundary
    the work item must demonstrate).
    """
    if not isinstance(local, ProtocolProfile):
        raise FutureError(
            FutureReasonCode.INVALID_INPUT,
            "local must be an upgrade ProtocolProfile",
        )
    if not isinstance(peer, ProtocolProfile):
        raise FutureError(
            FutureReasonCode.INVALID_INPUT,
            "peer must be an upgrade ProtocolProfile",
        )
    return negotiate_protocol_profile(local, peer)


@dataclass(frozen=True)
class FutureCapabilityNegotiation:
    """The WORK-005 verdict over a future-capability requirement
    (delegated result, carried as DATA).

    ``succeeded`` is the capability authority's own verdict.  A peer
    without the future capability yields an explicit failure reason
    (never silent satisfaction); a peer WITH the future capability
    statement yields a selection -- the additive path.
    """

    requirement_capability_id: str
    succeeded: bool
    reason: Optional[str]
    detail: str
    selected: Optional[Tuple[str, str]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requirement_capability_id": self.requirement_capability_id,
            "succeeded": self.succeeded,
            "reason": self.reason,
            "detail": self.detail,
            "selected": (
                {"capability_id": self.selected[0], "provider": self.selected[1]}
                if self.selected is not None else None
            ),
        }


def future_capability_negotiation(
    profile: FutureProfileDeclaration,
    *,
    peer_offers_future: bool,
    required: bool = False,
    evaluation_instant: str,
) -> FutureCapabilityNegotiation:
    """Negotiate the profile's future capability with a peer through
    the REAL WORK-005 authority.

    The WORK-005 authority's own open-world rule is the discrimination
    this work item must expose: a well-formed but UNREGISTERED
    capability id

    - as a REQUIRED capability fails closed with the authority's own
      ``unknown-required-capability`` reason -- "never coerced to a
      known capability" -- EVEN WHEN THE PEER ADVERTISES THE SAME
      UNKNOWN ID (the future identifier gains no negotiation
      authority from mere data agreement);
    - as an OPTIONAL capability is "safely ignored (preserved, not
      coerced)" -- peers carrying or not carrying future-profile
      data coexist identically (the additive path).

    Both verdicts are the capability authority's own; this function
    only carries them.  ``evaluation_instant`` documents the injected
    instant (the authority consumes its own injected clock value).
    """
    from capabilities.negotiation import (
        NegotiationSpec,
        Requirement,
        negotiate,
    )
    from capabilities.model import CapabilityStatement
    from datetime import datetime, timezone

    from .profile import classify_technology_id

    if not isinstance(profile, FutureProfileDeclaration):
        raise FutureError(
            FutureReasonCode.INVALID_INPUT,
            "profile must be a FutureProfileDeclaration",
        )
    if not isinstance(evaluation_instant, str) or not evaluation_instant:
        raise FutureError(
            FutureReasonCode.INVALID_INPUT,
            "evaluation_instant must be a non-empty injected instant string",
        )
    # sanity: the profile's technology id stays classifiable (the
    # open-world rule holds for the declaration under negotiation).
    classify_technology_id(profile.technology_id)

    future_capability = next(
        (cid for cid in profile.capability_references
         if cid.startswith("capability.profile.")),
        None,
    )
    if future_capability is None:
        raise FutureError(
            FutureReasonCode.PROFILE_INVALID,
            "the negotiation demo requires a profile-scoped capability "
            "reference in the declaration",
        )

    requirement = Requirement(
        capability_id=future_capability, required=bool(required),
    )

    peer_statements: Tuple[CapabilityStatement, ...] = ()
    if peer_offers_future:
        statement = CapabilityStatement(
            capability_id=future_capability,
            schema_version="1.0",
            provider_identity="adcos:node:test.future.peer:" + "c" * 64,
            valid_from="2026-01-01T00:00:00Z",
            expires_at="2027-01-01T00:00:00Z",
        )
        peer_statements = (statement,)
    else:
        # A conservative peer advertises one KNOWN core capability
        # only -- it carries no future-profile data at all.
        statement = CapabilityStatement(
            capability_id="capability.core.store-and-forward",
            schema_version="1.0",
            provider_identity="adcos:node:test.future.peer:" + "c" * 64,
            valid_from="2026-01-01T00:00:00Z",
            expires_at="2027-01-01T00:00:00Z",
        )
        peer_statements = (statement,)

    now = datetime(
        2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc
    )
    spec = NegotiationSpec(
        requirements=(requirement,),
        peer_statements=peer_statements,
        now=now,
    )
    result = negotiate(spec)
    outcome = result.outcomes[0] if result.outcomes else None
    if outcome is None:
        return FutureCapabilityNegotiation(
            requirement_capability_id=future_capability,
            succeeded=False,
            reason="no-outcome",
            detail="the capability authority returned no outcome",
            selected=None,
        )
    selected: Optional[Tuple[str, str]] = None
    if outcome.selected is not None:
        selected = (
            outcome.selected.capability_id,
            outcome.selected.provider_identity,
        )
    return FutureCapabilityNegotiation(
        requirement_capability_id=future_capability,
        succeeded=bool(outcome.succeeded),
        reason=outcome.reason,
        detail=outcome.detail or "",
        selected=selected,
    )
