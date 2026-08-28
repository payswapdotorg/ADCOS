"""WORK-037 Open RAN/Core interoperability profile: frozen
vocabularies and value records.

Everything here is DATA with validation (the WORK-033 ``agent.model``
style): frozen vocabularies with ``values()`` classmethods, immutable
records with content-derived ids/digests, and canonical bytes that
make every value replayable.  The profile reuses the ACCEPTED
work-item surfaces as DATA -- the component kinds name the accepted
adapter families (WORK-019/020/021), the conformance component names
WORK-032, the reference-agent component names WORK-033, and the
evidence-class mapping REUSES the WORK-032 ``EvidenceClass`` enum
(no second vocabulary is ever declared).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Tuple

from conformance.model import EvidenceClass
from protocol.canonicalization import canonical_json_bytes

from .errors import InteropError, InteropReasonCode

_DETAIL_LIMIT = 200


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _bounded_detail(value: str) -> str:
    text = str(value)
    if len(text) <= _DETAIL_LIMIT:
        return text
    return text[: _DETAIL_LIMIT - 3] + "..."


# ----------------------------------------------------------------------
# Frozen vocabularies
# ----------------------------------------------------------------------


class ProfileComponentKind:
    """The five profile components (the accepted dependency surface of
    WORK-037: W019, W020, W021, W032, W033).

    A valid profile declares EXACTLY one binding per kind -- all five
    are mandatory (the complete Open RAN/Core interoperability
    profile; a subset is not this work item).
    """

    FIVE_G_CORE = "five-g-core"
    RAN = "ran"
    NON_THREEGPP_ACCESS = "non-threegpp-access"
    CONFORMANCE = "conformance"
    REFERENCE_AGENT = "reference-agent"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.FIVE_G_CORE,
            cls.RAN,
            cls.NON_THREEGPP_ACCESS,
            cls.CONFORMANCE,
            cls.REFERENCE_AGENT,
        )


class ReferencePointKind:
    """The profile's interop reference points -- the seams the profile
    exercises over the ACCEPTED adapters (the profile's own naming of
    the exercised boundaries; the standards mapping itself lives in
    the accepted adapter families' frozen contracts, not here)."""

    CORE_CONTROL = "core-control"
    CORE_USER_PLANE = "core-user-plane"
    RAN_CONTROL = "ran-control"
    RAN_USER_PLANE = "ran-user-plane"
    NON_THREEGPP_ATTACH = "non-threegpp-attach"
    NON_THREEGPP_TUNNEL = "non-threegpp-tunnel"
    MIXED_ACCESS = "mixed-access"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.CORE_CONTROL,
            cls.CORE_USER_PLANE,
            cls.RAN_CONTROL,
            cls.RAN_USER_PLANE,
            cls.NON_THREEGPP_ATTACH,
            cls.NON_THREEGPP_TUNNEL,
            cls.MIXED_ACCESS,
        )


class AccessLegKind:
    """The two access families the mixed-access demonstration crosses."""

    THREE_GPP = "three-gpp"
    NON_THREE_GPP = "non-three-gpp"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.THREE_GPP, cls.NON_THREE_GPP)


class ScenarioLegName:
    """The frozen scenario leg vocabulary (application order).

    The class-B scenario carries ONE sacred ``session_id`` through
    four legs: the 5G Core PDU-session leg (W019 seam), the RAN
    access-path leg (W020 seam), the Wi-Fi/N3IWF tunnel leg (W021
    seam), and finally the 5G Core RE-BIND leg -- an access change
    BACK to 3GPP access with the session identity never re-minted
    (the W021 case_33 continuity pattern, profile-generalized).
    """

    FIVE_G_CORE_PDU = "five-g-core-pdu"
    RAN_ACCESS_PATH = "ran-access-path"
    NON_THREEGPP_TUNNEL = "non-threegpp-tunnel"
    FIVE_G_CORE_REBIND = "five-g-core-rebind"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.FIVE_G_CORE_PDU,
            cls.RAN_ACCESS_PATH,
            cls.NON_THREEGPP_TUNNEL,
            cls.FIVE_G_CORE_REBIND,
        )

    @classmethod
    def access_kind_for(cls, leg: str) -> str:
        """The access family each leg exercises (DATA map)."""
        if leg == cls.NON_THREEGPP_TUNNEL:
            return AccessLegKind.NON_THREE_GPP
        if leg in (cls.FIVE_G_CORE_PDU, cls.RAN_ACCESS_PATH, cls.FIVE_G_CORE_REBIND):
            return AccessLegKind.THREE_GPP
        raise InteropError(
            InteropReasonCode.INVALID_INPUT,
            "unknown scenario leg: %r" % (leg,),
        )


class InteropEventType:
    """The frozen scenario decision-journal vocabulary (9 kinds)."""

    PROFILE_VALIDATED = "profile-validated"
    LEG_STARTED = "leg-started"
    LEG_BYTES_VERIFIED = "leg-bytes-verified"
    LEG_RELEASED = "leg-released"
    ACCESS_CHANGED = "access-changed"
    SESSION_COHERENCE_VERIFIED = "session-coherence-verified"
    REF_OPACITY_VERIFIED = "ref-opacity-verified"
    PROFILE_VERIFIED = "profile-verified"
    EVIDENCE_RECORDED = "evidence-recorded"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.PROFILE_VALIDATED,
            cls.LEG_STARTED,
            cls.LEG_BYTES_VERIFIED,
            cls.LEG_RELEASED,
            cls.ACCESS_CHANGED,
            cls.SESSION_COHERENCE_VERIFIED,
            cls.REF_OPACITY_VERIFIED,
            cls.PROFILE_VERIFIED,
            cls.EVIDENCE_RECORDED,
        )


#: The frozen evidence-class mapping -- the WORK-037 handoff's classes
#: A/B/C expressed over the ACCEPTED WORK-032 ``EvidenceClass``
#: vocabulary (reused as DATA; no second vocabulary is declared).
PROFILE_EVIDENCE_CLASS_MAP: Dict[str, EvidenceClass] = {
    "A": EvidenceClass.ARCHITECTURE_CONFORMANCE,
    "B": EvidenceClass.AUTOMATED_VERIFICATION,
    "C": EvidenceClass.EXTERNAL_EVIDENCE,
}


# ----------------------------------------------------------------------
# Component ownership maps (DATA, validated by profile.py)
# ----------------------------------------------------------------------

#: The frozen component -> adapter-family map (each component binds
#: to exactly one accepted family surface; a binding naming another
#: family is a component mismatch, refused fail-closed).
COMPONENT_FAMILY: Dict[str, str] = {
    ProfileComponentKind.FIVE_G_CORE: "adapters.fivegc",
    ProfileComponentKind.RAN: "adapters.ran",
    ProfileComponentKind.NON_THREEGPP_ACCESS: "adapters.wifi",
    ProfileComponentKind.CONFORMANCE: "conformance",
    ProfileComponentKind.REFERENCE_AGENT: "agent",
}

#: The frozen component -> owned reference points (the CONFORMANCE
#: component owns no reference point -- it VERIFIES the others; the
#: REFERENCE_AGENT component owns the MIXED_ACCESS seam: the access
#: change is transparent at the agent's session surface).
COMPONENT_REFERENCE_POINTS: Dict[str, Tuple[str, ...]] = {
    ProfileComponentKind.FIVE_G_CORE: (
        ReferencePointKind.CORE_CONTROL,
        ReferencePointKind.CORE_USER_PLANE,
    ),
    ProfileComponentKind.RAN: (
        ReferencePointKind.RAN_CONTROL,
        ReferencePointKind.RAN_USER_PLANE,
    ),
    ProfileComponentKind.NON_THREEGPP_ACCESS: (
        ReferencePointKind.NON_THREEGPP_ATTACH,
        ReferencePointKind.NON_THREEGPP_TUNNEL,
    ),
    ProfileComponentKind.CONFORMANCE: (),
    ProfileComponentKind.REFERENCE_AGENT: (ReferencePointKind.MIXED_ACCESS,),
}

#: The complete reference-point set the profile REQUIRES (all seven:
#: the complete Open RAN/Core interoperability profile -- a subset is
#: not this work item; the battery pins the exact tuple).
REQUIRED_REFERENCE_POINTS: Tuple[str, ...] = ReferencePointKind.values()


# ----------------------------------------------------------------------
# Value records
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ComponentBinding:
    """One profile component binding: component kind + family +
    integration id + implementation label (pure DATA; validated
    fail-closed against the frozen ownership maps)."""

    component_kind: str
    family: str
    integration_id: str
    label: str

    def __post_init__(self) -> None:
        if self.component_kind not in ProfileComponentKind.values():
            raise InteropError(
                InteropReasonCode.COMPONENT_MISMATCH,
                "unknown component kind: %r" % (self.component_kind,),
            )
        expected = COMPONENT_FAMILY[self.component_kind]
        if self.family != expected:
            raise InteropError(
                InteropReasonCode.COMPONENT_MISMATCH,
                "component %r must bind family %r (got %r)"
                % (self.component_kind, expected, self.family),
            )
        if not isinstance(self.integration_id, str) or not self.integration_id:
            raise InteropError(
                InteropReasonCode.INVALID_INPUT,
                "integration_id must be a non-empty string",
            )
        if not isinstance(self.label, str) or not self.label:
            raise InteropError(
                InteropReasonCode.INVALID_INPUT,
                "label must be a non-empty string",
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_kind": self.component_kind,
            "family": self.family,
            "integration_id": self.integration_id,
            "label": self.label,
        }


@dataclass(frozen=True)
class ProfileDeclaration:
    """The declarative interoperability profile document.

    ``profile_id`` must carry the ``adcos:interop:`` prefix;
    ``bindings`` must cover all five component kinds exactly once;
    ``required_reference_points`` must be exactly the frozen complete
    set.  Canonical bytes + content digest make the declaration
    replayable DATA (the WORK-036 manifest discipline).
    """

    profile_id: str
    version: int
    bindings: Tuple[ComponentBinding, ...]
    required_reference_points: Tuple[str, ...] = REQUIRED_REFERENCE_POINTS

    def __post_init__(self) -> None:
        if not isinstance(self.profile_id, str) or not self.profile_id.startswith(
            "adcos:interop:"
        ):
            raise InteropError(
                InteropReasonCode.PROFILE_INVALID,
                "profile_id must carry the 'adcos:interop:' prefix",
            )
        if isinstance(self.version, bool) or not isinstance(self.version, int):
            raise InteropError(
                InteropReasonCode.INVALID_INPUT,
                "version must be an integer",
            )
        if self.version < 1:
            raise InteropError(
                InteropReasonCode.INVALID_INPUT,
                "version must be >= 1",
            )
        if not isinstance(self.bindings, tuple):
            raise InteropError(
                InteropReasonCode.INVALID_INPUT,
                "bindings must be a tuple",
            )
        kinds = [b.component_kind for b in self.bindings]
        for kind in ProfileComponentKind.values():
            if kinds.count(kind) != 1:
                raise InteropError(
                    InteropReasonCode.PROFILE_INVALID,
                    "profile must bind component %r exactly once (found %d)"
                    % (kind, kinds.count(kind)),
                )
        if tuple(self.required_reference_points) != REQUIRED_REFERENCE_POINTS:
            raise InteropError(
                InteropReasonCode.REFERENCE_POINT_UNBOUND,
                "the complete profile requires exactly the frozen seven "
                "reference points (got %r)" % (list(self.required_reference_points),),
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "version": self.version,
            "bindings": [b.to_dict() for b in self.bindings],
            "required_reference_points": list(self.required_reference_points),
        }

    def canonical_bytes(self) -> bytes:
        """Deterministic canonical JSON bytes (bindings in the frozen
        component order, independent of construction order)."""
        by_kind = {b.component_kind: b for b in self.bindings}
        ordered = tuple(
            by_kind[k] for k in ProfileComponentKind.values()
        )
        payload = {
            "profile_id": self.profile_id,
            "version": self.version,
            "bindings": [b.to_dict() for b in ordered],
            "required_reference_points": list(self.required_reference_points),
        }
        return canonical_json_bytes(payload)

    def digest(self) -> str:
        return _sha256_hex(self.canonical_bytes())


def canonical_profile() -> ProfileDeclaration:
    """The canonical WORK-037 profile declaration (pure DATA).

    The one profile this work item freezes: the accepted W019/W020/
    W021 adapter families + the W032 conformance suite + the W033
    reference agent, over the complete seven reference points.
    """
    return ProfileDeclaration(
        profile_id="adcos:interop:profile:open-ran-core:v1",
        version=1,
        bindings=(
            ComponentBinding(
                component_kind=ProfileComponentKind.FIVE_G_CORE,
                family=COMPONENT_FAMILY[ProfileComponentKind.FIVE_G_CORE],
                integration_id="adcos:fivegc:interop-profile",
                label="open5gs-adapter",
            ),
            ComponentBinding(
                component_kind=ProfileComponentKind.RAN,
                family=COMPONENT_FAMILY[ProfileComponentKind.RAN],
                integration_id="adcos:ran:interop-profile",
                label="openran-adapter",
            ),
            ComponentBinding(
                component_kind=ProfileComponentKind.NON_THREEGPP_ACCESS,
                family=COMPONENT_FAMILY[ProfileComponentKind.NON_THREEGPP_ACCESS],
                integration_id="adcos:wifi:interop-profile",
                label="n3iwf-adapter",
            ),
            ComponentBinding(
                component_kind=ProfileComponentKind.CONFORMANCE,
                family=COMPONENT_FAMILY[ProfileComponentKind.CONFORMANCE],
                integration_id="adcos:conformance:interop-profile",
                label="conformance-suite",
            ),
            ComponentBinding(
                component_kind=ProfileComponentKind.REFERENCE_AGENT,
                family=COMPONENT_FAMILY[ProfileComponentKind.REFERENCE_AGENT],
                integration_id="adcos:agent:interop-profile",
                label="linux-reference-agent",
            ),
        ),
    )


@dataclass(frozen=True)
class InteropEvent:
    """One journaled scenario decision (content-derived id).

    Adapter-side refs NEVER appear in ``detail`` raw -- only their
    SHA-256 digests (the ref-opacity + secret-hygiene discipline).
    """

    sequence: int
    instant: str
    kind: str
    subject: str
    detail: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int):
            raise InteropError(
                InteropReasonCode.INVALID_INPUT,
                "event sequence must be an integer",
            )
        if self.sequence < 1:
            raise InteropError(
                InteropReasonCode.INVALID_INPUT,
                "event sequence must be >= 1",
            )
        if self.kind not in InteropEventType.values():
            raise InteropError(
                InteropReasonCode.INVALID_INPUT,
                "unknown interop event kind: %r" % (self.kind,),
            )
        if not isinstance(self.instant, str) or not self.instant:
            raise InteropError(
                InteropReasonCode.INVALID_INPUT,
                "event instant must be a non-empty string",
            )
        if not isinstance(self.subject, str) or not self.subject:
            raise InteropError(
                InteropReasonCode.INVALID_INPUT,
                "event subject must be a non-empty string",
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sequence": self.sequence,
            "instant": self.instant,
            "kind": self.kind,
            "subject": self.subject,
            "detail": _bounded_detail(self.detail),
        }

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())

    def event_id(self) -> str:
        material = canonical_json_bytes(
            {"event": self.to_dict(), "salt": "adcos.interop.event.v1"}
        )
        return _sha256_hex(material)


def interop_events_canonical_bytes(events: Tuple[InteropEvent, ...]) -> bytes:
    """Canonical bytes over the ordered event list (replayable)."""
    return canonical_json_bytes(
        {"events": [e.to_dict() for e in events], "salt": "adcos.interop.journal.v1"}
    )


def interop_event_list_digest(events: Tuple[InteropEvent, ...]) -> str:
    return _sha256_hex(interop_events_canonical_bytes(events))


@dataclass(frozen=True)
class LegEvidence:
    """One scenario leg's verified evidence record.

    ``adapter_ref_digest`` is the SHA-256 of the leg's adapter-side
    opaque ref STRING -- the raw ref never appears in any evidence
    surface (adapter refs stay adapter-side; only their digests are
    journaled).  ``evidence_class`` is always "B" for the in-repo
    conformance legs (automated verification -- NEVER class C).
    """

    leg: str
    access_kind: str
    session_id: str
    payload_sha256: str
    echo_sha256: str
    bytes_equal: bool
    adapter_ref_digest: str
    evidence_class: str = "B"

    def __post_init__(self) -> None:
        if self.leg not in ScenarioLegName.values():
            raise InteropError(
                InteropReasonCode.INVALID_INPUT,
                "unknown scenario leg: %r" % (self.leg,),
            )
        if self.access_kind not in AccessLegKind.values():
            raise InteropError(
                InteropReasonCode.INVALID_INPUT,
                "unknown access kind: %r" % (self.access_kind,),
            )
        if self.evidence_class != "B":
            raise InteropError(
                InteropReasonCode.EVIDENCE_CLASS_VIOLATION,
                "a conformance-peer scenario leg is evidence class B "
                "(automated verification) and may NEVER be recorded as "
                "class %r (real interoperability requires the real-lab "
                "gate)" % (self.evidence_class,),
            )
        if not self.bytes_equal:
            raise InteropError(
                InteropReasonCode.LEG_BYTE_MISMATCH,
                "leg %r echo digest diverges from the payload digest"
                % (self.leg,),
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "leg": self.leg,
            "access_kind": self.access_kind,
            "session_id": self.session_id,
            "payload_sha256": self.payload_sha256,
            "echo_sha256": self.echo_sha256,
            "bytes_equal": self.bytes_equal,
            "adapter_ref_digest": self.adapter_ref_digest,
            "evidence_class": self.evidence_class,
        }


@dataclass(frozen=True)
class InteropRunResult:
    """The whole scenario's verified result (replayable DATA).

    ``interop_digest`` covers the profile digest, the sacred
    session_id, every leg evidence record, and the full journal --
    byte-identical across fresh runs of the same scenario.
    """

    profile_digest: str
    session_id: str
    legs: Tuple[LegEvidence, ...]
    events: Tuple[InteropEvent, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.profile_digest, str) or not self.profile_digest:
            raise InteropError(
                InteropReasonCode.INVALID_INPUT,
                "profile_digest must be a non-empty string",
            )
        if not isinstance(self.session_id, str) or not self.session_id:
            raise InteropError(
                InteropReasonCode.INVALID_INPUT,
                "session_id must be a non-empty string",
            )
        if not isinstance(self.legs, tuple) or not self.legs:
            raise InteropError(
                InteropReasonCode.INVALID_INPUT,
                "legs must be a non-empty tuple",
            )
        if not isinstance(self.events, tuple) or not self.events:
            raise InteropError(
                InteropReasonCode.INVALID_INPUT,
                "events must be a non-empty tuple",
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_digest": self.profile_digest,
            "session_id": self.session_id,
            "legs": [leg.to_dict() for leg in self.legs],
            "events": [e.to_dict() for e in self.events],
            "interop_digest": self.interop_digest(),
        }

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())

    def interop_digest(self) -> str:
        payload = {
            "profile_digest": self.profile_digest,
            "session_id": self.session_id,
            "legs": [leg.to_dict() for leg in self.legs],
            "journal_digest": interop_event_list_digest(self.events),
            "salt": "adcos.interop.run.v1",
        }
        return _sha256_hex(canonical_json_bytes(payload))


__all__ = [
    "ProfileComponentKind",
    "ReferencePointKind",
    "AccessLegKind",
    "ScenarioLegName",
    "InteropEventType",
    "PROFILE_EVIDENCE_CLASS_MAP",
    "COMPONENT_FAMILY",
    "COMPONENT_REFERENCE_POINTS",
    "REQUIRED_REFERENCE_POINTS",
    "ComponentBinding",
    "ProfileDeclaration",
    "canonical_profile",
    "InteropEvent",
    "interop_events_canonical_bytes",
    "interop_event_list_digest",
    "LegEvidence",
    "InteropRunResult",
]
