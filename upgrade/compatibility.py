"""Mixed-version coexistence and protocol-profile negotiation (WORK-029).

Answers exactly one question:

    What common protocol profile can two nodes at DIFFERENT software
    versions use together, and can they coexist on it?

Authority boundaries (the layering contract):

- **The Protocol Version line stays WORK-003.** The known-major truth
  is ``spec/schemas/protocol.json`` loaded through
  ``protocol.versioning.protocol_metadata()``; this module only
  CLASSIFIES against it (``classify_major``) and never redefines,
  duplicates, or mutates the line.  An unknown major fails closed
  exactly as WORK-003 says it must.
- **Capability negotiation stays WORK-005.** ``coexistence_report``
  DELEGATES to ``capabilities.negotiation.negotiate`` -- the real
  machinery, never a re-implementation.  What capabilities
  mixed-version peers may use together is the capability authority's
  verdict, carried here as DATA.
- **No peer authorization is answered here.** Whether a peer is
  trusted is WORK-010/federation; coexistence is a compatibility
  fact, not a trust decision.

Fail-closed semantics (the acceptance criterion "incompatible
versions fail closed"):

- majors that differ => ``MAJOR_MISMATCH`` -- there is NO fallback to
  a lower common major, no clamping, no best-effort guess;
- a major unknown to the WORK-003 artifact => ``MAJOR_UNKNOWN`` --
  rejected exactly as ``classify_major`` dictates;
- and the rejection is STRUCTURAL: :class:`ProfileNegotiation`
  refuses at construction to carry a ``selected`` profile whose major
  disagrees with either side, so a rogue negotiation result that
  "finds" a common profile across mismatched majors cannot exist as a
  value of this model at all.

Determinism: the common profile of two known-major peers is the
shared major with ``min(local.max_minor, peer.max_minor)`` -- the
additive-evolution floor (section 7 rule 5): each side speaks every
minor up to its head, so the common minor set is exactly the
intersection, whose head is the minimum head.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Optional, Sequence, Tuple

from .errors import UpgradeError, UpgradeReasonCode
from .model import ProtocolProfile, VersionInventory

# ----------------------------------------------------------------------
# ProfileNegotiation (the structurally fail-closed result)
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class ProfileNegotiation:
    """The result of negotiating a common protocol profile.

    ``selected`` is non-None exactly when both sides share one KNOWN
    major; a selected profile is validated at construction to agree
    with BOTH sides' majors and to sit at the additive-evolution
    floor ``min(local.max_minor, peer.max_minor)``.  A forged
    selection across mismatched majors is therefore not a value of
    this type: the model itself fails it closed.
    """

    local: ProtocolProfile
    peer: ProtocolProfile
    selected: Optional[ProtocolProfile]
    reason: Optional[str]
    detail: str

    def __post_init__(self) -> None:
        for name, value in (("local", self.local), ("peer", self.peer)):
            if not isinstance(value, ProtocolProfile):
                raise UpgradeError(
                    UpgradeReasonCode.VERSION_KIND_CONFLATED,
                    "ProfileNegotiation %s must be a ProtocolProfile, got %s"
                    % (name, type(value).__name__),
                )
        if self.selected is None:
            if self.reason is None:
                raise UpgradeError(
                    UpgradeReasonCode.INVALID_INPUT,
                    "a rejected profile negotiation must carry its reason",
                )
        else:
            if not isinstance(self.selected, ProtocolProfile):
                raise UpgradeError(
                    UpgradeReasonCode.VERSION_KIND_CONFLATED,
                    "selected profile must be a ProtocolProfile",
                )
            if self.reason is not None:
                raise UpgradeError(
                    UpgradeReasonCode.INVALID_INPUT,
                    "a selected profile negotiation carries no rejection reason",
                )
            if (
                self.selected.major != self.local.major
                or self.selected.major != self.peer.major
            ):
                raise UpgradeError(
                    UpgradeReasonCode.MAJOR_MISMATCH,
                    "selected profile %s disagrees with the negotiating majors "
                    "(%s, %s) -- a common profile across mismatched majors "
                    "is not a constructible value"
                    % (self.selected, self.local, self.peer),
                )
            expected_minor = min(self.local.max_minor, self.peer.max_minor)
            if self.selected.max_minor != expected_minor:
                raise UpgradeError(
                    UpgradeReasonCode.INVALID_INPUT,
                    "selected profile %s is not the additive-evolution floor "
                    "min(%s, %s) = %d.%d"
                    % (self.selected, self.local, self.peer,
                       self.selected.major, expected_minor),
                )

    @property
    def succeeded(self) -> bool:
        return self.selected is not None

    def to_dict(self) -> dict:
        return {
            "local": [self.local.major, self.local.max_minor],
            "peer": [self.peer.major, self.peer.max_minor],
            "selected": (
                [self.selected.major, self.selected.max_minor]
                if self.selected is not None else None
            ),
            "reason": self.reason,
            "detail": self.detail,
        }


# ----------------------------------------------------------------------
# Protocol-profile negotiation (fail closed)
# ----------------------------------------------------------------------

def negotiate_protocol_profile(
    local: ProtocolProfile, peer: ProtocolProfile, metadata: Optional[Any] = None,
) -> ProfileNegotiation:
    """Negotiate the common protocol profile of two peers.

    Deterministic and fail closed:

    - different majors => ``MAJOR_MISMATCH`` (no fallback, ever);
    - a major unknown to the WORK-003 protocol artifact =>
      ``MAJOR_UNKNOWN`` (``classify_major``'s verdict, delegated);
    - otherwise the shared major at ``min(local.max_minor,
      peer.max_minor)`` (the additive-evolution floor).
    """
    if local.major != peer.major:
        return ProfileNegotiation(
            local=local, peer=peer, selected=None,
            reason=UpgradeReasonCode.MAJOR_MISMATCH,
            detail=(
                "protocol majors %d and %d differ: incompatible versions "
                "fail closed (breaking changes require a new major; there "
                "is no cross-major fallback)" % (local.major, peer.major)
            ),
        )
    # Lazy import: the WORK-003 artifact is consumed read-only as DATA.
    from protocol.versioning import Classification, classify_major, protocol_metadata

    meta = metadata if metadata is not None else protocol_metadata()
    disposition = classify_major(local.major, meta)
    if disposition != Classification.KNOWN_COMPATIBLE:
        return ProfileNegotiation(
            local=local, peer=peer, selected=None,
            reason=UpgradeReasonCode.MAJOR_UNKNOWN,
            detail=(
                "protocol major %d is %s per the WORK-003 artifact "
                "(spec/schemas/protocol.json): unknown majors fail closed"
                % (local.major, disposition)
            ),
        )
    common_minor = min(local.max_minor, peer.max_minor)
    return ProfileNegotiation(
        local=local, peer=peer,
        selected=ProtocolProfile(major=local.major, max_minor=common_minor),
        reason=None,
        detail=(
            "common protocol profile %d.%d (shared known major; "
            "additive-evolution floor min(%d, %d))"
            % (local.major, common_minor, local.max_minor, peer.max_minor)
        ),
    )


# ----------------------------------------------------------------------
# Coexistence report (profile negotiation + REAL WORK-005 delegation)
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class CoexistenceReport:
    """Whether two mixed-version nodes can coexist, and on what terms.

    ``profile`` is the protocol-profile negotiation (WORK-003
    classification); ``capability_negotiation`` is the REAL WORK-005
    result over the caller-supplied requirements/peer statements
    (delegated -- never re-implemented here).  ``coexist`` is true
    exactly when both hold: a shared known-major protocol profile AND
    a successful capability negotiation.
    """

    local_inventory_id: str
    peer_inventory_id: str
    profile: ProfileNegotiation
    capability_succeeded: bool
    capability_failure_reasons: Tuple[str, ...]
    coexist: bool

    def to_dict(self) -> dict:
        return {
            "local_inventory_id": self.local_inventory_id,
            "peer_inventory_id": self.peer_inventory_id,
            "profile": self.profile.to_dict(),
            "capability_succeeded": self.capability_succeeded,
            "capability_failure_reasons": list(self.capability_failure_reasons),
            "coexist": self.coexist,
        }


def coexistence_report(
    local: VersionInventory,
    peer: VersionInventory,
    peer_statements: Sequence[Any] = (),
    requirements: Sequence[Any] = (),
    now: Optional[datetime] = None,
    metadata: Optional[Any] = None,
) -> CoexistenceReport:
    """The mixed-version coexistence verdict for two node inventories.

    The capability dimension DELEGATES to WORK-005's ``negotiate``
    (the real authority) over the caller's requirements and the
    peer's capability statements; the profile dimension uses the
    WORK-003 classification.  Both must hold for coexistence -- a
    shared profile with failed capability negotiation is NOT
    coexistence, and a successful capability negotiation across
    mismatched protocol majors is NOT coexistence either.
    """
    if now is None:
        raise UpgradeError(
            UpgradeReasonCode.INVALID_INPUT,
            "coexistence_report requires an injected evaluation instant "
            "(never a wall clock)",
        )
    profile = negotiate_protocol_profile(
        local.protocol_profile, peer.protocol_profile, metadata=metadata,
    )
    # Lazy import: delegated composition, read-only.
    from capabilities.negotiation import NegotiationSpec, negotiate

    negotiation = negotiate(
        NegotiationSpec(
            requirements=tuple(requirements),
            peer_statements=tuple(peer_statements),
            now=now,
        )
    )
    capability_succeeded = negotiation.succeeded
    coexist = profile.succeeded and capability_succeeded
    return CoexistenceReport(
        local_inventory_id=local.inventory_id,
        peer_inventory_id=peer.inventory_id,
        profile=profile,
        capability_succeeded=capability_succeeded,
        capability_failure_reasons=tuple(negotiation.failure_reasons),
        coexist=coexist,
    )


def envelope_version_disposition(major: int, metadata: Optional[Any] = None) -> str:
    """Classify an envelope's protocol major version via the WORK-003
    authority (``classify_major``): known majors are compatible,
    everything else is rejected -- the wire-level fail-closed verdict
    for mixed-version interoperation."""
    # Lazy import: the WORK-003 artifact is consumed read-only as DATA.
    from protocol.versioning import classify_major, protocol_metadata

    meta = metadata if metadata is not None else protocol_metadata()
    return classify_major(major, meta)
