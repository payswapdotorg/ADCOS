"""ADCOS access-technology extension registration surface (M020 —
Access Technology Capability Envelope, R9-CORE-001, DEC-0120).

The technology-extension registration surface of the R9 charter M020
scope: the exact declared path by which a NEW access technology —
**envelope + reference adapter composition + capability statement** —
registers into the system through the ACCEPTED boundaries with ZERO
contract-core delta:

* the **accepted ``adapters/capability.py`` seam** (the M007
  LOCK-110/LOCK-112 boundary): the registration drives the accepted
  WORK-016 ``AdapterRuntime`` (``register`` + ``open_adapter``) and
  wraps the composition in the accepted 1.1 §6
  :class:`~adapters.capability.CapabilityAdapter` translation seam —
  the ONLY path onto the execution boundary; nothing here bypasses
  the mediated runtime, and the sandbox's exception isolation,
  contract-shape enforcement and deterministic step budgets stay in
  force mechanically;
* the **accepted ``executionplans/`` bridge** (the M006 LOCK-109
  surface): the registration carries the frozen plan-side adapter
  operation vocabulary (``ADAPTER_OPERATIONS``) and verifies it is
  name-equal to the seam's own frozen ``CAPABILITY_OPERATIONS`` (the
  M007 composition-by-name-equality discipline — the adapter layer
  never imports the plan layer; this surface imports both and asserts
  the frozen equality the plan bridge composes over);
* **ZERO contract-core delta**: the registration touches no
  ``contracts/`` surface at all — no contract is created, mutated or
  re-derived; the technology enters as declaration data AROUND the
  canonical authority (LOCK-101/LOCK-117: ``ConnectivityContract``
  stays the sole authority; the registration record is DATA, never an
  authority; LOCK-105: no topology crosses; LOCK-119: no secrets).

The registration is the composition root for an adapter composition
the CALLER mounted through an accepted public surface (the M007
``adapters.reference.*.mount_reference`` family factories — the
reference compositions; a future composition mounts the same way).
The registration receives the mounted composition's products — the
``AdapterContract`` implementation (the accepted family bridge), the
``AdapterDescriptor`` (the composition's registration descriptor)
and the composition's binding requirements — and drives the accepted
seam with them, verbatim (the descriptor object is registered
unchanged; its ``access_technology_id`` must equal the envelope's
declared technology class — a cross-surface mismatch is a typed
rejection).

:func:`register_access_technology` returns a
:class:`TechnologyRegistration` — a typed, canonical-JSON
serializable record with a content-derived identity (LOCK-106
discipline) carrying the declaration surface (envelope id, ladder
id, handover-kind characteristic ids, adapter id, the capability
statement references, the LOCK-112 mechanism tags, the LOCK-109
bridge operations) plus the LIVE composition objects held BY
REFERENCE: the one :class:`~adapters.capability.CapabilityAdapter`
(the accepted composition's public runtime) and the one
:class:`~adapters.runtime.AdapterRuntime` created at registration.
Resolution is identity-preserving —
:meth:`TechnologyRegistration.resolve_capability_adapter` returns
the SAME live object every time (no re-instantiation, no second
runtime); the canonical ``to_dict()`` projection deliberately
excludes the live in-memory objects (identity-bearing declared
content only — the live runtime is not serializable state, and never
a persisted authority).

:class:`TechnologyRegistry` holds registrations keyed by technology
class (deterministic sorted iteration; duplicate technology-class
registrations are typed rejections — the duplicate-identity
malformed class).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from protocol.canonicalization import CanonicalizationError, canonical_json_bytes
from protocol.temporal import TemporalError, parse_instant

# BY REFERENCE: the accepted M007 seam surface.
from adapters import (
    CAPABILITY_OPERATIONS,
    AdapterRuntime,
    CapabilityAdapter,
    AdapterContract,
    AdapterDescriptor,
)
from adapters.errors import AdapterError

# BY REFERENCE: the accepted M006 LOCK-109 bridge vocabulary.
from executionplans import ADAPTER_OPERATIONS

from .envelopes import CapabilityEnvelope
from .handovers import HandoverCharacteristics
from .ladders import DegradationLadder
from .errors import AccessTechError, AccessTechReason

__all__ = [
    "REGISTRATION_OPERATIONS",
    "TechnologyRegistration",
    "TechnologyRegistry",
    "register_access_technology",
    "technology_registration_from_mapping",
]

#: The LOCK-109 bridge operations a registration carries: the accepted
#: plan-side frozen vocabulary (imported BY REFERENCE from
#: ``executionplans``), verified name-equal at import time to the
#: accepted seam vocabulary (the M007 name-equality discipline — the
#: registration surface asserts the frozen equality the plan bridge
#: composes over; drift is a fail-loud import-time rejection, never a
#: silently broken bridge).
REGISTRATION_OPERATIONS: Tuple[str, ...] = ADAPTER_OPERATIONS

if tuple(REGISTRATION_OPERATIONS) != tuple(CAPABILITY_OPERATIONS):
    raise AccessTechError(
        AccessTechReason.VOCABULARY,
        "the accepted LOCK-109 bridge vocabulary (executionplans."
        "ADAPTER_OPERATIONS) and the accepted seam vocabulary (adapters."
        "CAPABILITY_OPERATIONS) have diverged — the registration surface "
        "composes over their frozen name equality (fail loud)",
    )

#: Identity namespace (WORK-003 canonical-JSON SHA-256 convention).
_REGISTRATION_NAMESPACE = "adcos.accesstech.registration"

#: Maximum number of LOCK-112 mechanism tags on one registration (the
#: accepted seam enforces its own MAX_STANDARD_MECHANISMS bound; this
#: is the declared-side pre-check of the same discipline).
MAX_MECHANISMS = 16


def _canonical_bytes(document: Mapping[str, Any], label: str) -> bytes:
    try:
        return canonical_json_bytes(dict(document))
    except (CanonicalizationError, TypeError, ValueError) as error:
        raise AccessTechError(
            AccessTechReason.SERIALIZATION_INVALID,
            "%s is not canonicalizable: %s" % (label, error),
        ) from None


def _require_instant(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "%s must be an RFC 3339 UTC instant string" % label,
        )
    try:
        parse_instant(value)
    except TemporalError as error:
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "%s is not an injected RFC 3339 UTC instant: %s" % (label, error),
        ) from None
    return value


def derive_registration_id(
    technology_class: str,
    envelope_id: str,
    ladder_id: str,
    handover_ids: Sequence[str],
    adapter_id: str,
    capability_references: Sequence[str],
    mechanisms: Sequence[str],
    registered_at: str,
) -> str:
    """The content-derived registration identity (LOCK-106 discipline:
    sha256 over the canonical JSON of the declared registration
    content)."""
    document = {
        "kind": "adcos.accesstech.registration",
        "technology_class": technology_class,
        "envelope_id": envelope_id,
        "ladder_id": ladder_id,
        "handover_characteristics_ids": list(handover_ids),
        "adapter_id": adapter_id,
        "capability_references": list(capability_references),
        "standard_mechanisms": list(mechanisms),
        "bridge_operations": list(REGISTRATION_OPERATIONS),
        "registered_at": registered_at,
    }
    payload = dict(document)
    payload["namespace"] = _REGISTRATION_NAMESPACE
    return "sha256:" + hashlib.sha256(
        _canonical_bytes(payload, "the technology registration")
    ).hexdigest()


@dataclass(frozen=True)
class TechnologyRegistration:
    """One registered access technology: the declared surface (the
    envelope, the degradation ladder, the handover-kind
    characteristics, the capability statement, the LOCK-112 mechanism
    tags, the LOCK-109 bridge operations) plus the LIVE composition
    objects held BY REFERENCE (the one capability adapter — the
    accepted composition's public runtime — and the one adapter
    runtime the registration created).

    The live objects are intentionally NOT part of the canonical
    content (``content_dict`` carries the declared identity-bearing
    data only): resolution methods return the same live objects every
    call (identity-preserving, no re-instantiation) while the
    canonical record stays a deterministic, serializable declaration.
    """

    technology_class: str
    envelope: CapabilityEnvelope
    ladder: DegradationLadder
    handovers: Tuple[HandoverCharacteristics, ...]
    capability_adapter: CapabilityAdapter
    runtime: AdapterRuntime
    descriptor: AdapterDescriptor
    binding_requirements: Tuple[Tuple[str, Any], ...]
    mechanisms: Tuple[str, ...]
    registered_at: str
    registration_id: str = ""
    _capability_references: Tuple[str, ...] = field(default=())

    def __post_init__(self) -> None:
        if not isinstance(self.envelope, CapabilityEnvelope):
            raise AccessTechError(
                AccessTechReason.REGISTRATION_REJECTED,
                "the registration requires a CapabilityEnvelope (got %s)"
                % type(self.envelope).__name__,
            )
        if not isinstance(self.ladder, DegradationLadder):
            raise AccessTechError(
                AccessTechReason.REGISTRATION_REJECTED,
                "the registration requires a DegradationLadder (got %s)"
                % type(self.ladder).__name__,
            )
        if isinstance(self.handovers, (str, bytes)) or not isinstance(
            self.handovers, (tuple, list)
        ):
            raise AccessTechError(
                AccessTechReason.REGISTRATION_REJECTED,
                "the registration requires a sequence of "
                "HandoverCharacteristics records",
            )
        for item in self.handovers:
            if not isinstance(item, HandoverCharacteristics):
                raise AccessTechError(
                    AccessTechReason.REGISTRATION_REJECTED,
                    "handover declarations must be HandoverCharacteristics "
                    "records (got %s)" % type(item).__name__,
                )
        kinds = [item.kind for item in self.handovers]
        if len(set(kinds)) != len(kinds):
            raise AccessTechError(
                AccessTechReason.REGISTRATION_REJECTED,
                "duplicate handover-kind declarations are contradictory: %s"
                % ", ".join(sorted({k for k in kinds if kinds.count(k) > 1})),
            )
        if not self.handovers:
            raise AccessTechError(
                AccessTechReason.REGISTRATION_REJECTED,
                "a registered technology declares at least one handover "
                "kind's characteristics (an empty handover declaration "
                "declares no handover semantics)",
            )
        if not isinstance(self.capability_adapter, CapabilityAdapter):
            raise AccessTechError(
                AccessTechReason.REGISTRATION_REJECTED,
                "the registration requires the live CapabilityAdapter the "
                "accepted seam created (got %s)"
                % type(self.capability_adapter).__name__,
            )
        if not isinstance(self.runtime, AdapterRuntime):
            raise AccessTechError(
                AccessTechReason.REGISTRATION_REJECTED,
                "the registration requires the live AdapterRuntime the "
                "accepted seam drive created (got %s)"
                % type(self.runtime).__name__,
            )
        if not isinstance(self.descriptor, AdapterDescriptor):
            raise AccessTechError(
                AccessTechReason.REGISTRATION_REJECTED,
                "the registration requires the composition's "
                "AdapterDescriptor (got %s)" % type(self.descriptor).__name__,
            )
        if self.capability_adapter.adapter_id != self.descriptor.adapter_id:
            raise AccessTechError(
                AccessTechReason.REGISTRATION_REJECTED,
                "the live capability adapter %s is not the descriptor's "
                "adapter %s (cross-surface mismatch)"
                % (self.capability_adapter.adapter_id, self.descriptor.adapter_id),
            )
        if self.envelope.technology_class != self.descriptor.access_technology_id:
            raise AccessTechError(
                AccessTechReason.REGISTRATION_REJECTED,
                "the envelope's technology class %s does not match the "
                "composition's access_technology_id %s (cross-surface "
                "mismatch — one registration realizes exactly one declared "
                "technology class)"
                % (self.envelope.technology_class, self.descriptor.access_technology_id),
            )
        if self.ladder.technology_class != self.envelope.technology_class:
            raise AccessTechError(
                AccessTechReason.REGISTRATION_REJECTED,
                "the ladder's technology class %s does not match the "
                "envelope's %s (cross-surface mismatch)"
                % (self.ladder.technology_class, self.envelope.technology_class),
            )
        _require_instant(self.registered_at, "registered_at")
        if not isinstance(self.mechanisms, (tuple, list)):
            raise AccessTechError(
                AccessTechReason.REGISTRATION_REJECTED,
                "standard mechanisms must be a sequence of LOCK-112 "
                "citation tags",
            )
        mechanisms = tuple(self.mechanisms)
        if not mechanisms:
            raise AccessTechError(
                AccessTechReason.REGISTRATION_REJECTED,
                "a registered technology declares at least one LOCK-112 "
                "standard-mechanism citation tag (the tags are the "
                "composition's declared standards data)",
            )
        if len(mechanisms) > MAX_MECHANISMS:
            raise AccessTechError(
                AccessTechReason.REGISTRATION_REJECTED,
                "at most %d standard-mechanism tags are declarable" % MAX_MECHANISMS,
            )
        for tag in mechanisms:
            if not isinstance(tag, str) or not tag:
                raise AccessTechError(
                    AccessTechReason.REGISTRATION_REJECTED,
                    "standard-mechanism tags must be non-empty strings",
                )
        if len(set(mechanisms)) != len(mechanisms):
            raise AccessTechError(
                AccessTechReason.REGISTRATION_REJECTED,
                "duplicate standard-mechanism tags are contradictory",
            )
        object.__setattr__(self, "mechanisms", mechanisms)
        object.__setattr__(self, "handovers", tuple(self.handovers))
        if isinstance(self.binding_requirements, Mapping):
            object.__setattr__(
                self,
                "binding_requirements",
                tuple(sorted(self.binding_requirements.items())),
            )
        elif isinstance(self.binding_requirements, (tuple, list)):
            pairs: List[Tuple[str, Any]] = []
            for item in self.binding_requirements:
                if (
                    isinstance(item, (tuple, list))
                    and len(item) == 2
                    and isinstance(item[0], str)
                ):
                    pairs.append((item[0], item[1]))
                else:
                    raise AccessTechError(
                        AccessTechReason.REGISTRATION_REJECTED,
                        "binding requirements must be [key, value] pairs "
                        "(the composition's declared wiring data)",
                    )
            object.__setattr__(self, "binding_requirements", tuple(pairs))
        else:
            raise AccessTechError(
                AccessTechReason.REGISTRATION_REJECTED,
                "binding requirements must be a mapping or a sequence of "
                "pairs (the composition's declared wiring data)",
            )
        capability_references = tuple(self.descriptor.capabilities)
        if not capability_references:
            raise AccessTechError(
                AccessTechReason.REGISTRATION_REJECTED,
                "the composition's capability statement is empty (a "
                "registered technology declares at least one capability "
                "reference)",
            )
        object.__setattr__(self, "_capability_references", capability_references)
        derived = derive_registration_id(
            self.technology_class,
            self.envelope.envelope_id,
            self.ladder.ladder_id,
            [item.characteristics_id for item in self.handovers],
            self.descriptor.adapter_id,
            capability_references,
            mechanisms,
            self.registered_at,
        )
        if not isinstance(self.registration_id, str) or not self.registration_id:
            object.__setattr__(self, "registration_id", derived)
        elif self.registration_id != derived:
            raise AccessTechError(
                AccessTechReason.IDENTITY_MISMATCH,
                "registration_id does not match the content-derived "
                "identity (tamper evidence): declared %s, derived %s"
                % (self.registration_id, derived),
            )

    # ------------------------------------------------------------------
    # Identity-preserving resolution (BY REFERENCE — the live objects)
    # ------------------------------------------------------------------

    def resolve_capability_adapter(self) -> CapabilityAdapter:
        """The accepted composition's public runtime — the SAME live
        :class:`~adapters.capability.CapabilityAdapter` object the
        registration created through the accepted seam (identity-
        preserving: no re-instantiation, no second runtime)."""
        return self.capability_adapter

    def resolve_runtime(self) -> AdapterRuntime:
        """The live WORK-016 :class:`~adapters.runtime.AdapterRuntime`
        the seam drive created (identity-preserving)."""
        return self.runtime

    # ------------------------------------------------------------------
    # The declared-surface projections
    # ------------------------------------------------------------------

    def capability_statement(self) -> Tuple[str, ...]:
        """The composition's declared capability statement (the
        descriptor's capability references — BY REFERENCE from the
        accepted composition, never re-minted here)."""
        return self._capability_references

    def bridge_operations(self) -> Tuple[str, ...]:
        """The LOCK-109 bridge operations (the accepted plan-side
        frozen vocabulary, verified name-equal to the seam
        vocabulary)."""
        return REGISTRATION_OPERATIONS

    def content_dict(self) -> Dict[str, Any]:
        """The canonical declared content (identity-bearing data only —
        the live composition objects are deliberately excluded: they
        are in-memory references, never serialized authority)."""
        return {
            "technology_class": self.technology_class,
            "envelope_id": self.envelope.envelope_id,
            "ladder_id": self.ladder.ladder_id,
            "handover_characteristics_ids": [
                item.characteristics_id for item in self.handovers
            ],
            "handover_kinds": [item.kind for item in self.handovers],
            "adapter_id": self.descriptor.adapter_id,
            "access_technology_id": self.descriptor.access_technology_id,
            "capability_references": list(self._capability_references),
            "standard_mechanisms": list(self.mechanisms),
            "bridge_operations": list(REGISTRATION_OPERATIONS),
            "binding_requirements": [
                [key, value] for key, value in self.binding_requirements
            ],
            "registered_at": self.registered_at,
            "registration_id": self.registration_id,
        }

    def to_dict(self) -> Dict[str, Any]:
        return self.content_dict()

    def to_canonical_bytes(self) -> bytes:
        return _canonical_bytes(
            self.content_dict(), "the technology registration"
        )


def technology_registration_from_mapping(
    value: object,
    *,
    envelope: CapabilityEnvelope,
    ladder: DegradationLadder,
    handovers: Sequence[HandoverCharacteristics],
    capability_adapter: CapabilityAdapter,
    runtime: AdapterRuntime,
    descriptor: AdapterDescriptor,
    binding_requirements: Mapping[str, Any],
    mechanisms: Sequence[str],
) -> TechnologyRegistration:
    """Reconstruct a :class:`TechnologyRegistration` from its canonical
    mapping plus the LIVE composition objects (the live objects are
    never serialized; the caller re-supplies them through the accepted
    surfaces).  Fail-closed on grammar drift and on identity tampering
    (the content-derived registration id is recomputed and compared
    at load)."""
    if not isinstance(value, Mapping):
        raise AccessTechError(
            AccessTechReason.SERIALIZATION_INVALID,
            "the technology registration must be a mapping",
        )
    data = dict(value)
    registration_id = data.get("registration_id")
    if not isinstance(registration_id, str) or not registration_id:
        raise AccessTechError(
            AccessTechReason.SERIALIZATION_INVALID,
            "the technology registration lacks its content-derived "
            "registration_id",
        )
    for member in ("technology_class", "registered_at"):
        if member not in data:
            raise AccessTechError(
                AccessTechReason.SERIALIZATION_INVALID,
                "the technology registration lacks the %r member" % member,
            )
    return TechnologyRegistration(
        technology_class=data["technology_class"],
        envelope=envelope,
        ladder=ladder,
        handovers=tuple(handovers),
        capability_adapter=capability_adapter,
        runtime=runtime,
        descriptor=descriptor,
        binding_requirements=binding_requirements,
        mechanisms=tuple(mechanisms),
        registered_at=data["registered_at"],
        registration_id=registration_id,
    )


# ----------------------------------------------------------------------
# The registration surface (the declared extension path)
# ----------------------------------------------------------------------


def register_access_technology(
    *,
    envelope: CapabilityEnvelope,
    ladder: DegradationLadder,
    handovers: Sequence[HandoverCharacteristics],
    implementation: AdapterContract,
    descriptor: AdapterDescriptor,
    binding_requirements: Mapping[str, Any],
    mechanisms: Sequence[str],
    session_store: Any,
    now: str,
) -> TechnologyRegistration:
    """Register ONE access technology through the accepted boundaries
    (the declared extension path — the exact route a NEW technology
    takes: envelope + reference adapter composition + capability
    statement).

    The drive (every step fail-closed typed; consumed-seam rejections
    surface on this domain's vocabulary with their deterministic text
    preserved — exception isolation):

    1. the declarations are type-checked (envelope / ladder / handover
       characteristics — the construction-time validations already
       ran; the registration cross-checks the technology class across
       envelope, ladder and composition descriptor);
    2. the LOCK-109 bridge vocabulary is verified (import-time frozen
       name equality — carried on the registration record);
    3. the composition is driven through the ACCEPTED seam: one
       ``AdapterRuntime`` over the caller's session store, the
       descriptor + implementation registered through the runtime's
       public ``register``, the adapter ``open_adapter``-ed, and the
       live capability adapter created by the accepted
       ``CapabilityAdapter`` constructor with the composition's
       LOCK-112 mechanism tags;
    4. the typed registration record is assembled (content-derived
       identity over the declared surface).

    The caller mounts the composition through an accepted public
    surface (the M007 ``adapters.reference.*.mount_reference``
    factories — the reference compositions — or a future composition's
    equivalent) and passes the mounted products here; nothing in this
    path re-implements, forks or bypasses the accepted runtime — the
    registration IS the composed drive.

    ZERO contract-core delta: this path touches no ``contracts/``
    surface (no contract is created, mutated or re-derived; the
    technology enters as declaration data around the canonical
    authority).
    """
    _require_instant(now, "the registration instant")
    if not isinstance(implementation, AdapterContract):
        raise AccessTechError(
            AccessTechReason.REGISTRATION_REJECTED,
            "the registration requires the mounted composition's "
            "AdapterContract implementation (got %s)"
            % type(implementation).__name__,
        )
    if not isinstance(descriptor, AdapterDescriptor):
        raise AccessTechError(
            AccessTechReason.REGISTRATION_REJECTED,
            "the registration requires the mounted composition's "
            "AdapterDescriptor (got %s)" % type(descriptor).__name__,
        )
    if not isinstance(binding_requirements, Mapping):
        raise AccessTechError(
            AccessTechReason.REGISTRATION_REJECTED,
            "binding requirements must be a mapping (the composition's "
            "declared wiring data)",
        )
    if envelope.technology_class != descriptor.access_technology_id:
        raise AccessTechError(
            AccessTechReason.REGISTRATION_REJECTED,
            "the envelope's technology class %s does not match the "
            "composition's access_technology_id %s (one registration "
            "realizes exactly one declared technology class)"
            % (envelope.technology_class, descriptor.access_technology_id),
        )
    if ladder.technology_class != envelope.technology_class:
        raise AccessTechError(
            AccessTechReason.REGISTRATION_REJECTED,
            "the ladder's technology class %s does not match the "
            "envelope's %s" % (ladder.technology_class, envelope.technology_class),
        )
    if isinstance(handovers, (str, bytes)) or not isinstance(
        handovers, (tuple, list)
    ):
        raise AccessTechError(
            AccessTechReason.REGISTRATION_REJECTED,
            "handovers must be a sequence of HandoverCharacteristics",
        )
    handover_records: List[HandoverCharacteristics] = []
    for item in handovers:
        if not isinstance(item, HandoverCharacteristics):
            raise AccessTechError(
                AccessTechReason.REGISTRATION_REJECTED,
                "handover declarations must be HandoverCharacteristics "
                "records (got %s)" % type(item).__name__,
            )
        handover_records.append(item)
    if not handover_records:
        raise AccessTechError(
            AccessTechReason.REGISTRATION_REJECTED,
            "a registration declares at least one handover kind's "
            "characteristics",
        )
    kinds = [item.kind for item in handover_records]
    if len(set(kinds)) != len(kinds):
        raise AccessTechError(
            AccessTechReason.REGISTRATION_REJECTED,
            "duplicate handover-kind declarations are contradictory: %s"
            % ", ".join(sorted({k for k in kinds if kinds.count(k) > 1})),
        )
    mechanisms_tuple = tuple(mechanisms)
    if not mechanisms_tuple:
        raise AccessTechError(
            AccessTechReason.REGISTRATION_REJECTED,
            "a registration declares at least one LOCK-112 "
            "standard-mechanism citation tag",
        )
    for tag in mechanisms_tuple:
        if not isinstance(tag, str) or not tag:
            raise AccessTechError(
                AccessTechReason.REGISTRATION_REJECTED,
                "standard-mechanism tags must be non-empty strings",
            )

    # The accepted seam drive (the M007 LOCK-110/LOCK-112 boundary).
    try:
        runtime = AdapterRuntime(session_store=session_store)
        runtime.register(descriptor, implementation, now=now)
    except AdapterError as error:
        raise AccessTechError(
            AccessTechReason.REGISTRATION_REJECTED,
            "the accepted adapter runtime rejected the registration "
            "drive: %s" % error.detail,
        ) from None
    opened = runtime.open_adapter(descriptor.adapter_id, now=now)
    if not opened.ok:
        detail = (
            opened.failure.detail if opened.failure is not None else "unknown"
        )
        raise AccessTechError(
            AccessTechReason.REGISTRATION_REJECTED,
            "the accepted adapter runtime failed to open the registered "
            "adapter %s: %s" % (descriptor.adapter_id, detail),
        )
    try:
        capability_adapter = CapabilityAdapter(
            runtime, descriptor.adapter_id, standard_mechanisms=mechanisms_tuple
        )
    except AdapterError as error:
        raise AccessTechError(
            AccessTechReason.REGISTRATION_REJECTED,
            "the accepted capability seam rejected the composition: %s"
            % error.detail,
        ) from None

    return TechnologyRegistration(
        technology_class=envelope.technology_class,
        envelope=envelope,
        ladder=ladder,
        handovers=tuple(handover_records),
        capability_adapter=capability_adapter,
        runtime=runtime,
        descriptor=descriptor,
        binding_requirements=dict(binding_requirements),
        mechanisms=mechanisms_tuple,
        registered_at=now,
    )


# ----------------------------------------------------------------------
# The technology registry (deterministic, fail-closed)
# ----------------------------------------------------------------------


@dataclass
class TechnologyRegistry:
    """The deterministic technology registry: registrations keyed by
    technology class (sorted iteration; duplicate technology-class
    registrations are typed rejections — the duplicate-identity
    malformed class).

    An in-memory composition index (execution bookkeeping, never a
    persisted authority): the registry holds the live registration
    records BY REFERENCE and resolves lookups identity-preserving.
    """

    def __init__(self) -> None:
        self._registrations: Dict[str, TechnologyRegistration] = {}

    def register(self, registration: TechnologyRegistration) -> None:
        """Add ONE registration (fail-closed: the record must be a
        typed registration; the technology class must be unregistered
        — a second registration for an existing class is a typed
        duplicate-identity rejection)."""
        if not isinstance(registration, TechnologyRegistration):
            raise AccessTechError(
                AccessTechReason.REGISTRATION_REJECTED,
                "the registry registers TechnologyRegistration records "
                "(got %s)" % type(registration).__name__,
            )
        existing = self._registrations.get(registration.technology_class)
        if existing is not None:
            raise AccessTechError(
                AccessTechReason.REGISTRATION_REJECTED,
                "technology class %s is already registered (registration "
                "%s) — duplicate identities are typed rejections, never "
                "silent overwrites"
                % (registration.technology_class, existing.registration_id),
            )
        self._registrations[registration.technology_class] = registration

    def lookup(self, technology_class: str) -> TechnologyRegistration:
        """Resolve ONE technology class's registration (fail-closed on
        an unknown class; identity-preserving — the SAME registration
        record object every call)."""
        if not isinstance(technology_class, str):
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "technology class must be a string",
            )
        registration = self._registrations.get(technology_class)
        if registration is None:
            raise AccessTechError(
                AccessTechReason.REGISTRATION_REJECTED,
                "technology class %s is not registered (registered: %s)"
                % (
                    technology_class,
                    ", ".join(sorted(self._registrations)) or "none",
                ),
            )
        return registration

    def technology_classes(self) -> Tuple[str, ...]:
        """The registered technology classes (deterministic sorted
        order)."""
        return tuple(sorted(self._registrations))

    def registrations(self) -> Tuple[TechnologyRegistration, ...]:
        """All registrations in technology-class order
        (deterministic)."""
        return tuple(
            self._registrations[key] for key in sorted(self._registrations)
        )

    def __len__(self) -> int:
        return len(self._registrations)
