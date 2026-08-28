"""WORK-038 future-IMT profile: frozen vocabularies and value records.

Everything here is DATA with validation (the W037 ``interop.model``
style over the W033 ``agent.model`` style): frozen vocabularies with
``values()`` classmethods, immutable records with content-derived
ids/digests, and canonical bytes that make every value replayable.

The future-IMT profile reuses the ACCEPTED work-item surfaces as DATA
and never as new semantics:

- the access-technology identifier is a WORK-002 registry reference
  (``access.3gpp.nr.imt2030`` -- the entry the registry itself has
  reserved since WORK-002 for exactly this additive future path; the
  registry is consumed read-only and is NEVER modified by this
  profile);
- the capability references are WORK-002 capability-registry
  references (KNOWN preserved, UNKNOWN_BUT_WELL_FORMED preserved --
  additive data, never new authority);
- the resource mapping entries are WORK-008 kind/unit mappings;
- the evidence-class mapping REUSES the WORK-032 ``EvidenceClass``
  enum (no second vocabulary is ever declared);
- the profile versions are WORK-016 adapter profile-version strings.

A future technology enters as DATA through the adapter boundary; it
never becomes a core domain type (architecture sections 8 and 10,
LOCK-001..LOCK-003; the registry's own frozen description).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Tuple

from conformance.model import EvidenceClass
from protocol.canonicalization import canonical_json_bytes

from .errors import FutureError, FutureReasonCode

_DETAIL_LIMIT = 200


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _bounded_detail(value: object) -> str:
    text = str(value)
    if len(text) <= _DETAIL_LIMIT:
        return text
    return text[: _DETAIL_LIMIT - 3] + "..."


# ----------------------------------------------------------------------
# Frozen vocabularies
# ----------------------------------------------------------------------


class FutureEventType:
    """The frozen scenario journal vocabulary (16 kinds).

    The journal records the profile's own decision sequence: what was
    validated, what was classified, what the registry pinning
    observed, which contract operations the composed runtime executed,
    what the unknown-identifier and core-equivalence probes saw, and
    what evidence class was recorded.  Every entry is DATA about an
    observation -- the journal never mutates any authority.
    """

    PROFILE_VALIDATED = "profile-validated"
    TECHNOLOGY_CLASSIFIED = "technology-classified"
    REGISTRY_PINNED = "registry-pinned"
    ADAPTER_REGISTERED = "adapter-registered"
    ADAPTER_OPENED = "adapter-opened"
    CAPABILITIES_EXPOSED = "capabilities-exposed"
    LINK_OBSERVED = "link-observed"
    CAPACITY_ALLOCATED = "capacity-allocated"
    CAPACITY_RELEASED = "capacity-released"
    SESSION_BOUND = "session-bound"
    SESSION_UNBOUND = "session-unbound"
    HEALTH_REPORTED = "health-reported"
    ADAPTER_CLOSED = "adapter-closed"
    UNKNOWN_ID_PRESERVED = "unknown-id-preserved"
    CORE_EQUIVALENCE_VERIFIED = "core-equivalence-verified"
    PROFILE_VERIFIED = "profile-verified"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.PROFILE_VALIDATED,
            cls.TECHNOLOGY_CLASSIFIED,
            cls.REGISTRY_PINNED,
            cls.ADAPTER_REGISTERED,
            cls.ADAPTER_OPENED,
            cls.CAPABILITIES_EXPOSED,
            cls.LINK_OBSERVED,
            cls.CAPACITY_ALLOCATED,
            cls.CAPACITY_RELEASED,
            cls.SESSION_BOUND,
            cls.SESSION_UNBOUND,
            cls.HEALTH_REPORTED,
            cls.ADAPTER_CLOSED,
            cls.UNKNOWN_ID_PRESERVED,
            cls.CORE_EQUIVALENCE_VERIFIED,
            cls.PROFILE_VERIFIED,
        )


#: The frozen evidence-class mapping -- the WORK-038 handoff's classes
#: A/B/C expressed over the ACCEPTED WORK-032 ``EvidenceClass``
#: vocabulary (reused as DATA; no second vocabulary is declared).
#: Class C (external/real-world evidence) is NOT APPLICABLE to this
#: synthetic work item per the handoff; the mapping exists so the
#: disclosure stays on the accepted vocabulary.
FUTURE_EVIDENCE_CLASS_MAP: Dict[str, EvidenceClass] = {
    "A": EvidenceClass.ARCHITECTURE_CONFORMANCE,
    "B": EvidenceClass.AUTOMATED_VERIFICATION,
    "C": EvidenceClass.EXTERNAL_EVIDENCE,
}


#: The core layers whose behavior must remain byte-identical for
#: unchanged inputs when the future profile is added (the handoff's
#: frozen acceptance list: routing, session, resource, policy).
CORE_EQUIVALENCE_LAYERS: Tuple[str, ...] = (
    "routing", "sessions", "resources", "policy",
)


# ----------------------------------------------------------------------
# Value records
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class FutureProfileDeclaration:
    """The declarative future-IMT adapter profile (pure DATA).

    Members mirror exactly what the WORK-038 handoff permits a future
    profile to introduce: a profile-specific identifier, capability
    data, an adapter resource mapping, and security-state structure.
    Every member is validated fail-closed at construction against the
    ACCEPTED authorities (WORK-002 id classification, WORK-005
    capability classification, WORK-008 kind/unit tables, WORK-016
    profile-version grammar) -- this record adds NO new vocabulary of
    its own beyond its own field names.
    """

    technology_id: str
    profile_versions: Tuple[str, ...]
    capability_references: Tuple[str, ...]
    technology_resource: str
    resource_kind: str
    resource_unit: str
    resource_quantity: int
    security_profile: str
    credential_slots: Tuple[str, ...]
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        from adapters.validation import (
            validate_access_technology_id,
            validate_capability_references,
            validate_profile_versions,
        )

        # WORK-002 open-world classification: KNOWN and
        # UNKNOWN_BUT_WELL_FORMED are preserved verbatim; INVALID
        # fails closed.  The profile NEVER mutates the registry and
        # never coerces an unknown id to a known one.
        object.__setattr__(
            self, "technology_id", validate_access_technology_id(self.technology_id)
        )
        object.__setattr__(
            self, "profile_versions", validate_profile_versions(self.profile_versions)
        )
        if not self.profile_versions:
            raise FutureError(
                FutureReasonCode.PROFILE_INVALID,
                "a profile declaration carries at least one profile version",
            )
        object.__setattr__(
            self,
            "capability_references",
            validate_capability_references(self.capability_references),
        )
        if not self.capability_references:
            raise FutureError(
                FutureReasonCode.PROFILE_INVALID,
                "a profile declaration carries at least one capability "
                "reference (the additive surface under test)",
            )
        if not isinstance(self.technology_resource, str) or not (
            1 <= len(self.technology_resource) <= 64
        ):
            raise FutureError(
                FutureReasonCode.MAPPING_INVALID,
                "technology resource name must be a 1..64 character string",
            )
        if isinstance(self.resource_quantity, bool) or not isinstance(
            self.resource_quantity, int
        ):
            raise FutureError(
                FutureReasonCode.MAPPING_INVALID,
                "resource quantity must be an integer",
            )
        if self.resource_quantity <= 0:
            raise FutureError(
                FutureReasonCode.MAPPING_INVALID,
                "resource quantity must be positive (a declared capacity)",
            )
        if not isinstance(self.security_profile, str) or not (
            1 <= len(self.security_profile) <= 64
        ):
            raise FutureError(
                FutureReasonCode.INVALID_INPUT,
                "security profile must be a 1..64 character string",
            )
        if not isinstance(self.credential_slots, (tuple, list)) or not all(
            isinstance(slot, str) and 1 <= len(slot) <= 64
            for slot in self.credential_slots
        ):
            raise FutureError(
                FutureReasonCode.INVALID_INPUT,
                "credential slots must be 1..64 character strings (slot "
                "names only -- LOCK-023 forbids secret material)",
            )
        if not isinstance(self.extensions, Mapping):
            raise FutureError(
                FutureReasonCode.INVALID_INPUT,
                "extensions must be a mapping (unknown members preserved)",
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "technology_id": self.technology_id,
            "profile_versions": list(self.profile_versions),
            "capability_references": list(self.capability_references),
            "technology_resource": self.technology_resource,
            "resource_kind": self.resource_kind,
            "resource_unit": self.resource_unit,
            "resource_quantity": self.resource_quantity,
            "security_profile": self.security_profile,
            "credential_slots": list(self.credential_slots),
            "extensions": dict(self.extensions),
        }

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())

    def digest(self) -> str:
        return "sha256:" + _sha256_hex(self.canonical_bytes())


#: The frozen default declaration: the hypothetical IMT-2030 study
#: profile over the registry's own RESERVED identifier path
#: (``access.3gpp.nr.imt2030`` -- reserved by WORK-002, never
#: activated: activation is the standards body's act, not this work
#: item's).  The capability set mixes one KNOWN core reference with
#: one profile-scoped UNKNOWN_BUT_WELL_FORMED reference so the
#: additive-preservation property is exercised on the canonical path.
CANONICAL_FUTURE_TECHNOLOGY_ID = "access.3gpp.nr.imt2030"


def canonical_future_profile() -> FutureProfileDeclaration:
    """The frozen canonical WORK-038 profile declaration."""
    return FutureProfileDeclaration(
        technology_id=CANONICAL_FUTURE_TECHNOLOGY_ID,
        profile_versions=("imt2030-study-1",),
        capability_references=(
            "capability.core.store-and-forward",
            "capability.profile.imt2030.data-transfer",
        ),
        technology_resource="imt2030:study-bandwidth",
        resource_kind="bandwidth",
        resource_unit="mbps",
        resource_quantity=100,
        security_profile="baseline",
        credential_slots=("technology-credential",),
        extensions={},
    )


#: The frozen unknown-future identifier used to demonstrate the
#: open-world path (architecture section 8's own example): a
#: well-formed id absent from the registry is UNKNOWN, preserved
#: verbatim, registrable as DATA, and gains no authority.
UNKNOWN_FUTURE_TECHNOLOGY_ID = "access.3gpp.future.unknown"


@dataclass(frozen=True)
class FutureEvent:
    """One append-only journal entry (content-derived id).

    The journal is the profile's own decision record: deterministic
    sequence, injected instant, frozen event-type vocabulary, bounded
    human detail.  Ids are content-derived over WORK-003 canonical
    JSON with a fixed domain salt so equal content always yields equal
    ids and tampering is detectable on reload.
    """

    sequence: int
    event_type: str
    instant: str
    detail: str

    def __post_init__(self) -> None:
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int):
            raise FutureError(
                FutureReasonCode.INVALID_INPUT,
                "event sequence must be an integer",
            )
        if self.sequence < 1:
            raise FutureError(
                FutureReasonCode.INVALID_INPUT,
                "event sequence is 1-based",
            )
        if self.event_type not in FutureEventType.values():
            raise FutureError(
                FutureReasonCode.INVALID_INPUT,
                "unknown event type: %r" % (self.event_type,),
            )
        if not isinstance(self.instant, str) or not self.instant:
            raise FutureError(
                FutureReasonCode.INVALID_INPUT,
                "event instant must be a non-empty string",
            )
        object.__setattr__(self, "detail", _bounded_detail(self.detail))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sequence": self.sequence,
            "event_type": self.event_type,
            "instant": self.instant,
            "detail": self.detail,
        }

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(
            dict(self.to_dict(), event_id=self.event_id())
        )

    def event_id(self) -> str:
        payload = canonical_json_bytes(
            {
                "salt": "adcos.future.event.v1",
                "sequence": self.sequence,
                "event_type": self.event_type,
                "instant": self.instant,
                "detail": self.detail,
            }
        )
        return "sha256:" + _sha256_hex(payload)


def future_events_canonical_bytes(events: Tuple[FutureEvent, ...]) -> bytes:
    """Canonical bytes over an ordered journal (replay substrate)."""
    return canonical_json_bytes([event.to_dict() for event in events])


def future_event_list_digest(events: Tuple[FutureEvent, ...]) -> str:
    return _sha256_hex(future_events_canonical_bytes(events))


@dataclass(frozen=True)
class CoreEquivalenceRecord:
    """The core-equivalence proof record (class-B observation DATA).

    For each of the four frozen core layers (routing, sessions,
    resources, policy) the record carries the digest of the layer's
    canonical state for the SAME fixed inputs before and after the
    future adapter was registered and fully exercised.  ``equal`` is
    per-layer truth; the scenario refuses to emit a record whose
    layers are not all equal (the handoff's byte-identity criterion
    enforced structurally).
    """

    layers: Tuple[Tuple[str, str, str, bool], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.layers, tuple):
            raise FutureError(
                FutureReasonCode.INVALID_INPUT,
                "equivalence layers must be a tuple of records",
            )
        seen: List[str] = []
        for entry in self.layers:
            if not isinstance(entry, tuple) or len(entry) != 4:
                raise FutureError(
                    FutureReasonCode.INVALID_INPUT,
                    "each layer entry is (layer, before, after, equal)",
                )
            layer, before, after, equal = entry
            if layer not in CORE_EQUIVALENCE_LAYERS:
                raise FutureError(
                    FutureReasonCode.INVALID_INPUT,
                    "unknown core layer: %r" % (layer,),
                )
            if layer in seen:
                raise FutureError(
                    FutureReasonCode.INVALID_INPUT,
                    "duplicate core layer: %r" % (layer,),
                )
            seen.append(layer)
            for digest in (before, after):
                if not isinstance(digest, str) or not digest.startswith("sha256:"):
                    raise FutureError(
                        FutureReasonCode.INVALID_INPUT,
                        "layer digests must be sha256:<hex> strings",
                    )
            if bool(equal) is not (before == after):
                raise FutureError(
                    FutureReasonCode.INVALID_INPUT,
                    "layer %r equal flag disagrees with its digests" % (layer,),
                )
        if tuple(seen) != CORE_EQUIVALENCE_LAYERS:
            raise FutureError(
                FutureReasonCode.INVALID_INPUT,
                "equivalence record must cover exactly %r in order"
                % (CORE_EQUIVALENCE_LAYERS,),
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "layers": [
                {
                    "layer": layer,
                    "before": before,
                    "after": after,
                    "equal": equal,
                }
                for layer, before, after, equal in self.layers
            ],
            "all_equal": all(equal for _l, _b, _a, equal in self.layers),
        }

    def all_equal(self) -> bool:
        return all(equal for _layer, _before, _after, equal in self.layers)

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())

    def digest(self) -> str:
        return _sha256_hex(self.canonical_bytes())


@dataclass(frozen=True)
class FutureRunResult:
    """The class-B synthetic conformance run outcome (pure DATA).

    Carries: the validated profile's digest, the technology
    classification observed (WORK-002's own verdict, recorded as
    data), the registry digest before and after the run (pinning the
    no-core-schema-change fact), the registered adapter ids, the
    unknown-identifier preservation facts, the core-equivalence
    record, and the ordered journal.  ``future_digest`` covers ALL of
    it -- two honest runs of the same profile over the same inputs
    always produce the same digest, and any drift is a replay
    divergence.
    """

    profile_digest: str
    technology_classification: str
    registry_digest_before: str
    registry_digest_after: str
    adapter_ids: Tuple[str, ...]
    unknown_id: str
    unknown_id_classification: str
    unknown_id_still_unknown: bool
    core_equivalence: CoreEquivalenceRecord
    events: Tuple[FutureEvent, ...]

    def __post_init__(self) -> None:
        for name in ("profile_digest", "registry_digest_before",
                     "registry_digest_after"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.startswith("sha256:"):
                raise FutureError(
                    FutureReasonCode.INVALID_INPUT,
                    "%s must be a sha256:<hex> digest" % name,
                )
        if not isinstance(self.technology_classification, str):
            raise FutureError(
                FutureReasonCode.INVALID_INPUT,
                "technology classification must be recorded as data",
            )
        if not isinstance(self.adapter_ids, tuple) or not self.adapter_ids:
            raise FutureError(
                FutureReasonCode.INVALID_INPUT,
                "a run registers at least one adapter",
            )
        for adapter_id in self.adapter_ids:
            if not isinstance(adapter_id, str) or not adapter_id:
                raise FutureError(
                    FutureReasonCode.INVALID_INPUT,
                    "adapter ids must be non-empty strings",
                )
        if not isinstance(self.unknown_id, str) or not self.unknown_id:
            raise FutureError(
                FutureReasonCode.INVALID_INPUT,
                "the unknown-id demonstration is mandatory",
            )
        if not isinstance(self.unknown_id_still_unknown, bool):
            raise FutureError(
                FutureReasonCode.INVALID_INPUT,
                "unknown_id_still_unknown must be a boolean fact",
            )
        if not isinstance(self.core_equivalence, CoreEquivalenceRecord):
            raise FutureError(
                FutureReasonCode.INVALID_INPUT,
                "core_equivalence must be a CoreEquivalenceRecord",
            )
        if not isinstance(self.events, tuple):
            raise FutureError(
                FutureReasonCode.INVALID_INPUT,
                "events must be a tuple of FutureEvent",
            )
        for event in self.events:
            if not isinstance(event, FutureEvent):
                raise FutureError(
                    FutureReasonCode.INVALID_INPUT,
                    "events must be FutureEvent records",
                )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_digest": self.profile_digest,
            "technology_classification": self.technology_classification,
            "registry_digest_before": self.registry_digest_before,
            "registry_digest_after": self.registry_digest_after,
            "registry_unchanged": (
                self.registry_digest_before == self.registry_digest_after
            ),
            "adapter_ids": list(self.adapter_ids),
            "unknown_id": self.unknown_id,
            "unknown_id_classification": self.unknown_id_classification,
            "unknown_id_still_unknown": self.unknown_id_still_unknown,
            "core_equivalence": self.core_equivalence.to_dict(),
            "events": [event.to_dict() for event in self.events],
            "journal_digest": future_event_list_digest(self.events),
        }

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())

    def future_digest(self) -> str:
        return "sha256:" + _sha256_hex(self.canonical_bytes())
