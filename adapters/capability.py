"""ADCOS capability-oriented execution boundary (M007, R7-CORE-001).

The Architecture 1.1 normative execution-adapter boundary (frozen 1.1
``spec/architecture.md`` §6): adapters MAY expose operations equivalent
to ``inspect_capabilities()``, ``inspect_offers()``, ``reserve()``,
``activate()``, ``measure()``, ``reconfigure()``, ``release()`` and
``health()``.  This module is that surface for the WORK-016-era
``/adapters`` package, harvested onto the 1.1 authority (R7 charter
M007; DEC-0101).

The harvest is a REFACTOR, never a rewrite (LOCK-112 discipline in the
positive direction): the WORK-016 public API —
:class:`adapters.contract.AdapterContract` (the frozen nine-op section
10.1 surface), :class:`adapters.runtime.AdapterRuntime`,
:class:`adapters.sandbox.SandboxedAdapter`, and every domain object in
:mod:`adapters.model` — stays available to its existing consumers,
byte-for-byte.  What M007 adds is ONE explicit, disclosed translation
seam (:class:`CapabilityAdapter`) that maps the nine WORK-016
operations onto the 1.1 capability-oriented surface:

    1.1 §6 operation        WORK-016 translation (disclosed)
    ------------------      ------------------------------------------
    inspect_capabilities -> capabilities() (mediated, filtered by the
                            descriptor declaration) + descriptor data
    inspect_offers       -> descriptor resource-mapping data +
                            mediated current capability references
                            (declared data only; provider-local,
                            LOCK-105; never topology)
    reserve              -> allocate() (the adapter-scoped capacity
                            ledger; integer base units, lease expiry)
    activate             -> bind_session() (read-only WORK-012
                            bindability verification + mediated bearer
                            creation)
    measure              -> observe() (generic link metrics, injected
                            instant)
    reconfigure          -> unbind_session() + bind_session() with the
                            SAME session id and the NEW requirements
                            (the deterministic re-bind translation of a
                            mid-session reconfiguration; the previous
                            binding is released first, the reservation
                            is preserved)
    release              -> release() and/or unbind_session()
                            (reservation release / activation teardown)
    health               -> health() (mediated, LOCK-017: reported
                            state is data, the computed state wins)

The seam is the ONLY place this mapping exists; the WORK-016 surface
never learns about it, and the 1.1 surface never bypasses it (every
1.1 operation composes through the WORK-016 ``AdapterRuntime``, so the
sandbox's exception isolation, contract-shape enforcement and
deterministic step budgets remain in force — LOCK-110 mechanically
preserved, not conventionally).

LOCK-110 (SDK isolation) is structural here:

* every 1.1 operation returns typed, canonical, provider-neutral
  records (:class:`CapabilityView`, :class:`OfferView`, the WORK-016
  :class:`~adapters.model.Allocation`, :class:`Activation`,
  :class:`Measurement`, :class:`Reconfiguration`,
  :class:`ReleaseReceipt`, :class:`~adapters.model.HealthReport`) —
  never a provider-native type, never an opaque technology/bearer
  reference (those stay behind the WORK-016 runtime, keyed internally,
  passed back on release);
* the core imports no adapter implementation and branches on no
  technology name — the standard-mechanism tags carried by the views
  are DATA (LOCK-112 citations), never a branch input;
* adapter-side faults cross as typed
  :class:`adapters.sandbox.AdapterFailure` VALUES inside
  :class:`adapters.runtime.AdapterOpResult` — never exceptions.

The 1.1 operation vocabulary (:data:`CAPABILITY_OPERATIONS`) uses the
hyphenated names of the frozen §6 set — the same names the accepted
M006 ``executionplans`` domain carries as ``ADAPTER_OPERATIONS``
(the ExecutionSegment's typed operation references compose down onto
THIS surface; the M006 relationship is by NAME EQUALITY verified in
the M007 battery, never by import — the adapter layer stays
independent of the plan layer, which is the direction frozen 1.1 §6
draws: plans reference adapter operations, adapters never reference
plans).

Adapter-side ledger authority boundaries (the WORK-016 frozen module
rules, preserved verbatim): activations are adapter-LOCAL execution
bookkeeping mapping a session to a reservation and a binding —
execution artifacts under LOCK-117 (never a second contract authority;
the M002 ``contracts/`` domain stays the sole authority for acquired
connectivity).  Adapter identity stays the WORK-016 grammar
(``adcos:adapter:...``), distinct from NodeID.  All instants are
injected (WORK-003 grammar); there is no wall clock, no randomness,
no network, and no secret material anywhere (LOCK-119); ids are
content-derived over WORK-003 canonical JSON, recomputed at
deserialization (tamper evidence at construction AND load).
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from protocol.canonicalization import canonical_json_bytes

from .errors import AdapterError, AdapterReasonCode
from .model import (
    AdapterDescriptor,
    Allocation,
    AllocationState,
    BindingState,
    HealthReport,
    LinkMetricsSample,
)
from .runtime import AdapterOpResult, AdapterRuntime
from .sandbox import AdapterFailure
from .validation import (
    validate_instant,
    validate_nonempty_str,
    validate_sequence_mapping,
)

# --------------------------------------------------------------------------
# The frozen 1.1 §6 capability-oriented operation vocabulary
# --------------------------------------------------------------------------

#: The capability-oriented execution-boundary operations (frozen 1.1
#: ``spec/architecture.md`` §6; LOCK-110: names only).  The hyphenated
#: spelling matches the accepted M006 ``executionplans.ADAPTER_OPERATIONS``
#: verbatim (the battery verifies the equality — the composition seam is
#: by name, never by import).
CAPABILITY_OPERATIONS: Tuple[str, ...] = (
    "inspect-capabilities",
    "inspect-offers",
    "reserve",
    "activate",
    "measure",
    "reconfigure",
    "release",
    "health",
)

#: The disclosed WORK-016 <- 1.1 translation map (documentation-shaped
#: data; the battery freezes it).  Every 1.1 operation composes onto the
#: WORK-016 nine-op surface exactly as declared here — nothing bypasses
#: the ``AdapterRuntime`` mediator.
CAPABILITY_TRANSLATION_MAP: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("inspect-capabilities", ("capabilities",)),
    ("inspect-offers", ("capabilities",)),
    ("reserve", ("allocate",)),
    ("activate", ("bind_session",)),
    ("measure", ("observe",)),
    ("reconfigure", ("unbind_session", "bind_session")),
    ("release", ("release", "unbind_session")),
    ("health", ("health",)),
)

#: Maximum number of standard-mechanism tags a reference adapter may
#: declare (fail-closed bound; the tags are LOCK-112 citation DATA).
MAX_STANDARD_MECHANISMS = 16

#: Maximum number of measurements retained in one activation's
#: measurement trail (bounded deterministic replay aid).
MAX_MEASUREMENTS_PER_ACTIVATION = 64


# --------------------------------------------------------------------------
# Typed, provider-neutral record vocabularies
# --------------------------------------------------------------------------


class ActivationState:
    """Adapter-local activation lifecycle vocabulary (M007).

    ``ACTIVE`` — the activation holds a live binding.
    ``RECONFIGURED`` — the activation was re-bound with new
    requirements (the re-bind translation of a mid-session
    reconfiguration; further reconfigurations are legal from here).
    ``RELEASED`` — terminal teardown (binding released, reservation
    released).

    These are ADAPTER-LOCAL execution-artifact states (LOCK-117: data,
    never authority).  The plan-side segment vocabulary
    (PLANNED/RESERVED/ACTIVATED/MEASURED/RELEASED) is owned by the
    accepted M006 ``executionplans`` domain and is never re-invented
    here: an activation is the adapter-side realization of a segment's
    ``activate`` engagement, and this vocabulary describes only the
    adapter-local binding lifecycle.
    """

    ACTIVE = "ACTIVE"
    RECONFIGURED = "RECONFIGURED"
    RELEASED = "RELEASED"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.ACTIVE, cls.RECONFIGURED, cls.RELEASED)


#: Legal activation-state transitions (fail-closed elsewhere).
ACTIVATION_TRANSITIONS: Dict[str, Tuple[str, ...]] = {
    ActivationState.ACTIVE: (ActivationState.RECONFIGURED, ActivationState.RELEASED),
    ActivationState.RECONFIGURED: (
        ActivationState.RECONFIGURED,
        ActivationState.RELEASED,
    ),
    ActivationState.RELEASED: (),
}


def activation_transition_is_legal(previous: str, new: str) -> bool:
    return new in ACTIVATION_TRANSITIONS.get(previous, ())


@dataclass(frozen=True)
class CapabilityView:
    """Provider-neutral capability inspection record (1.1 §6
    ``inspect_capabilities`` return).

    ``capability_references`` are the mediated, descriptor-filtered
    capability id references (declared data — the adapter is not the
    capability authority).  ``standard_mechanisms`` are LOCK-112
    citation tags declared by the reference adapter (DATA with issuer
    provenance; never a branch input).  No NodeID, no secret material,
    no topology facts.
    """

    adapter_id: str
    access_technology_id: str
    capability_references: Tuple[str, ...]
    standard_mechanisms: Tuple[str, ...]
    computed_instant: str
    lifecycle: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "access_technology_id": self.access_technology_id,
            "capability_references": list(self.capability_references),
            "standard_mechanisms": list(self.standard_mechanisms),
            "computed_instant": self.computed_instant,
            "lifecycle": self.lifecycle,
        }

    def to_canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())


@dataclass(frozen=True)
class OfferView:
    """Provider-neutral offer inspection record (1.1 §6
    ``inspect_offers`` return, one per mapped technology resource).

    The record mirrors the descriptor's declared resource mapping plus
    the mediated capability references the adapter can currently
    expose: the provider-local, LOCK-105-safe inventory slice the
    provider exports for interoperability (frozen 1.1 §5).  It is an
    inspection VIEW — the offers authority (M003 ``offers/``) owns
    real offer records; this view never becomes one, never carries
    pricing/commitments, and never asserts topology.
    """

    adapter_id: str
    access_technology_id: str
    technology_resource: str
    kind: str
    unit: str
    quantity: int
    availability: str
    capability_references: Tuple[str, ...]
    standard_mechanisms: Tuple[str, ...]
    inspect_instant: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "access_technology_id": self.access_technology_id,
            "technology_resource": self.technology_resource,
            "kind": self.kind,
            "unit": self.unit,
            "quantity": self.quantity,
            "availability": self.availability,
            "capability_references": list(self.capability_references),
            "standard_mechanisms": list(self.standard_mechanisms),
            "inspect_instant": self.inspect_instant,
        }

    def to_canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())


@dataclass(frozen=True)
class Activation:
    """One adapter-local activation: a reserved capacity slice put
    into service for one ADCOS session.

    The activation maps ``reservation_id`` (the WORK-016 content-
    derived allocation id), ``session_id`` (the sacred WORK-012
    session id — never re-derived, never mutated here) and
    ``binding_id`` (the WORK-016 content-derived binding id).  The
    opaque technology/bearer references stay behind the WORK-016
    runtime.  ``requirements`` is the caller-supplied canonical
    requirements snapshot at bind time (re-configuration replaces it
    on the record with the new snapshot — identity is content,
    sequence is provenance, the WORK-013/WORK-016 convention).

    Execution artifact under LOCK-117: this record is data riding
    behind the execution boundary; it is never a contract authority
    and never mutates any contract state.
    """

    activation_id: str
    adapter_id: str
    reservation_id: str
    session_id: str
    binding_id: str
    requirements: Tuple[Tuple[str, Any], ...]
    created_instant: str
    last_reconfigured_instant: Optional[str]
    state: str
    sequence: int

    def content_dict(self) -> Dict[str, Any]:
        """Identity content (excludes the provenance sequence)."""
        return {
            "activation_id": self.activation_id,
            "adapter_id": self.adapter_id,
            "reservation_id": self.reservation_id,
            "session_id": self.session_id,
            "binding_id": self.binding_id,
            "requirements": [list(item) for item in self.requirements],
            "created_instant": self.created_instant,
            "last_reconfigured_instant": self.last_reconfigured_instant,
            "state": self.state,
        }

    def to_dict(self) -> Dict[str, Any]:
        out = self.content_dict()
        out["sequence"] = self.sequence
        return out

    def to_canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())


@dataclass(frozen=True)
class Measurement:
    """One mediated measurement collection (1.1 §6 ``measure`` return).

    ``samples`` are the WORK-016 generic link-metric samples (adapter-
    REPORTED data, never topology authority).  ``activation_id`` is
    ``None`` for adapter-level measurements, or the activation the
    measurement was collected for.
    """

    measurement_id: str
    adapter_id: str
    activation_id: Optional[str]
    samples: Tuple[Dict[str, Any], ...]
    collected_instant: str
    sequence: int

    def content_dict(self) -> Dict[str, Any]:
        return {
            "measurement_id": self.measurement_id,
            "adapter_id": self.adapter_id,
            "activation_id": self.activation_id,
            "samples": list(self.samples),
            "collected_instant": self.collected_instant,
        }

    def to_dict(self) -> Dict[str, Any]:
        out = self.content_dict()
        out["sequence"] = self.sequence
        return out

    def to_canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())


@dataclass(frozen=True)
class Reconfiguration:
    """One applied mid-session reconfiguration (1.1 §6 ``reconfigure``
    return).

    Records the re-bind translation: ``previous_binding_id`` released,
    ``binding_id`` created, same session and reservation, the applied
    canonical requirements snapshot.  The previous binding id is
    historical DATA (already released — never a live handle).
    """

    reconfiguration_id: str
    activation_id: str
    adapter_id: str
    session_id: str
    reservation_id: str
    previous_binding_id: str
    binding_id: str
    applied_requirements: Tuple[Tuple[str, Any], ...]
    applied_instant: str
    sequence: int

    def content_dict(self) -> Dict[str, Any]:
        return {
            "reconfiguration_id": self.reconfiguration_id,
            "activation_id": self.activation_id,
            "adapter_id": self.adapter_id,
            "session_id": self.session_id,
            "reservation_id": self.reservation_id,
            "previous_binding_id": self.previous_binding_id,
            "binding_id": self.binding_id,
            "applied_requirements": [list(item) for item in self.applied_requirements],
            "applied_instant": self.applied_instant,
        }

    def to_dict(self) -> Dict[str, Any]:
        out = self.content_dict()
        out["sequence"] = self.sequence
        return out

    def to_canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())


@dataclass(frozen=True)
class ReleaseReceipt:
    """One applied teardown (1.1 §6 ``release`` return).

    ``released_kinds`` discloses exactly what was released
    (``activation`` and/or ``reservation``); the ids are the
    content-derived ADCOS-side ids; the technology-side teardown ran
    through the mediated WORK-016 operations — a failed technology
    teardown is an isolated failure value, never a receipt.
    """

    release_id: str
    adapter_id: str
    activation_id: Optional[str]
    reservation_id: Optional[str]
    binding_id: Optional[str]
    released_kinds: Tuple[str, ...]
    released_instant: str
    reason: str
    sequence: int

    def content_dict(self) -> Dict[str, Any]:
        return {
            "release_id": self.release_id,
            "adapter_id": self.adapter_id,
            "activation_id": self.activation_id,
            "reservation_id": self.reservation_id,
            "binding_id": self.binding_id,
            "released_kinds": list(self.released_kinds),
            "released_instant": self.released_instant,
            "reason": self.reason,
        }

    def to_dict(self) -> Dict[str, Any]:
        out = self.content_dict()
        out["sequence"] = self.sequence
        return out

    def to_canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())


# --------------------------------------------------------------------------
# Content-derived ids (WORK-003 canonical-JSON convention)
# --------------------------------------------------------------------------


def _sha256_id(document: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(dict(document))).hexdigest()


def derive_activation_id(
    adapter_id: str,
    reservation_id: str,
    session_id: str,
    created_instant: str,
    sequence: int,
) -> str:
    document = {
        "kind": "adcos.adapter.activation",
        "adapter_id": adapter_id,
        "reservation_id": reservation_id,
        "session_id": session_id,
        "created_instant": created_instant,
        "sequence": sequence,
    }
    return _sha256_id(document)


def derive_measurement_id(
    adapter_id: str,
    activation_id: Optional[str],
    samples: Sequence[Mapping[str, Any]],
    collected_instant: str,
    sequence: int,
) -> str:
    document = {
        "kind": "adcos.adapter.measurement",
        "adapter_id": adapter_id,
        "activation_id": activation_id,
        "samples": list(samples),
        "collected_instant": collected_instant,
        "sequence": sequence,
    }
    return _sha256_id(document)


def derive_reconfiguration_id(
    activation_id: str,
    binding_id: str,
    applied_requirements: Sequence[Tuple[str, Any]],
    applied_instant: str,
    sequence: int,
) -> str:
    document = {
        "kind": "adcos.adapter.reconfiguration",
        "activation_id": activation_id,
        "binding_id": binding_id,
        "applied_requirements": [list(item) for item in applied_requirements],
        "applied_instant": applied_instant,
        "sequence": sequence,
    }
    return _sha256_id(document)


def derive_release_id(
    adapter_id: str,
    reservation_id: Optional[str],
    activation_id: Optional[str],
    released_instant: str,
    sequence: int,
) -> str:
    document = {
        "kind": "adcos.adapter.release",
        "adapter_id": adapter_id,
        "reservation_id": reservation_id,
        "activation_id": activation_id,
        "released_instant": released_instant,
        "sequence": sequence,
    }
    return _sha256_id(document)


# --------------------------------------------------------------------------
# Canonical record reconstruction (round-trip discipline)
# --------------------------------------------------------------------------


def _require_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AdapterError(
            AdapterReasonCode.SERIALIZATION_INVALID,
            "%s must be a mapping" % label,
        )
    return value


def _require_pairs(value: object, label: str) -> Tuple[Tuple[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise AdapterError(
            AdapterReasonCode.SERIALIZATION_INVALID,
            "%s must be a sequence of pairs" % label,
        )
    pairs: List[Tuple[str, Any]] = []
    for item in value:
        if not isinstance(item, Sequence) or isinstance(item, (str, bytes)):
            raise AdapterError(
                AdapterReasonCode.SERIALIZATION_INVALID,
                "%s entries must be pairs" % label,
            )
        if len(item) != 2:
            raise AdapterError(
                AdapterReasonCode.SERIALIZATION_INVALID,
                "%s entries must be [key, value] pairs" % label,
            )
        pairs.append((str(item[0]), item[1]))
    return tuple(pairs)


def _require_sequence_field(data: Mapping[str, Any], label: str) -> int:
    sequence = data.get("sequence")
    if isinstance(sequence, bool) or not isinstance(sequence, int):
        raise AdapterError(
            AdapterReasonCode.SERIALIZATION_INVALID,
            "%s sequence must be an integer" % label,
        )
    return sequence


def activation_from_mapping(value: object) -> Activation:
    """Reconstruct an :class:`Activation` from its canonical mapping.

    Fail-closed on any drift from the record grammar, on id tampering
    (the content-derived id is recomputed), and on illegal states.
    """
    data = _require_mapping(value, "activation")
    record = Activation(
        activation_id=validate_nonempty_str(
            data.get("activation_id"), "activation_id", 128
        ),
        adapter_id=validate_nonempty_str(data.get("adapter_id"), "adapter_id"),
        reservation_id=validate_nonempty_str(
            data.get("reservation_id"), "reservation_id", 128
        ),
        session_id=validate_nonempty_str(data.get("session_id"), "session_id"),
        binding_id=validate_nonempty_str(data.get("binding_id"), "binding_id", 128),
        requirements=_require_pairs(data.get("requirements"), "activation requirements"),
        created_instant=validate_instant(data.get("created_instant"), "created_instant"),
        last_reconfigured_instant=(
            None
            if data.get("last_reconfigured_instant") is None
            else validate_instant(
                data.get("last_reconfigured_instant"), "last_reconfigured_instant"
            )
        ),
        state=validate_nonempty_str(data.get("state"), "state", 32),
        sequence=_require_sequence_field(data, "activation"),
    )
    if record.state not in ActivationState.values():
        raise AdapterError(
            AdapterReasonCode.SERIALIZATION_INVALID,
            "activation state %r is not in the vocabulary" % (record.state,),
        )
    expected = derive_activation_id(
        record.adapter_id,
        record.reservation_id,
        record.session_id,
        record.created_instant,
        record.sequence,
    )
    if record.activation_id != expected:
        raise AdapterError(
            AdapterReasonCode.SERIALIZATION_INVALID,
            "activation_id does not match the derived identity (tamper evidence)",
        )
    return record


def measurement_from_mapping(value: object) -> Measurement:
    """Reconstruct a :class:`Measurement` from its canonical mapping."""
    data = _require_mapping(value, "measurement")
    samples_raw = data.get("samples")
    if not isinstance(samples_raw, Sequence) or isinstance(samples_raw, (str, bytes)):
        raise AdapterError(
            AdapterReasonCode.SERIALIZATION_INVALID,
            "measurement samples must be a sequence of sample mappings",
        )
    samples: List[Dict[str, Any]] = []
    for item in samples_raw:
        sample = _require_mapping(item, "measurement sample")
        # Round-trip through the WORK-016 typed sample (grammar + value
        # validation at load, the model.py convention).
        typed = LinkMetricsSample(
            metric=sample.get("metric"),
            value=sample.get("value"),
            observed_at=sample.get("observed_at"),
        )
        samples.append(typed.to_dict())
    activation_id = data.get("activation_id")
    record = Measurement(
        measurement_id=validate_nonempty_str(
            data.get("measurement_id"), "measurement_id", 128
        ),
        adapter_id=validate_nonempty_str(data.get("adapter_id"), "adapter_id"),
        activation_id=(
            None
            if activation_id is None
            else validate_nonempty_str(activation_id, "activation_id", 128)
        ),
        samples=tuple(samples),
        collected_instant=validate_instant(
            data.get("collected_instant"), "collected_instant"
        ),
        sequence=_require_sequence_field(data, "measurement"),
    )
    expected = derive_measurement_id(
        record.adapter_id,
        record.activation_id,
        record.samples,
        record.collected_instant,
        record.sequence,
    )
    if record.measurement_id != expected:
        raise AdapterError(
            AdapterReasonCode.SERIALIZATION_INVALID,
            "measurement_id does not match the derived identity (tamper evidence)",
        )
    return record


def reconfiguration_from_mapping(value: object) -> Reconfiguration:
    """Reconstruct a :class:`Reconfiguration` from its canonical mapping."""
    data = _require_mapping(value, "reconfiguration")
    record = Reconfiguration(
        reconfiguration_id=validate_nonempty_str(
            data.get("reconfiguration_id"), "reconfiguration_id", 128
        ),
        activation_id=validate_nonempty_str(
            data.get("activation_id"), "activation_id", 128
        ),
        adapter_id=validate_nonempty_str(data.get("adapter_id"), "adapter_id"),
        session_id=validate_nonempty_str(data.get("session_id"), "session_id"),
        reservation_id=validate_nonempty_str(
            data.get("reservation_id"), "reservation_id", 128
        ),
        previous_binding_id=validate_nonempty_str(
            data.get("previous_binding_id"), "previous_binding_id", 128
        ),
        binding_id=validate_nonempty_str(data.get("binding_id"), "binding_id", 128),
        applied_requirements=_require_pairs(
            data.get("applied_requirements"), "applied requirements"
        ),
        applied_instant=validate_instant(
            data.get("applied_instant"), "applied_instant"
        ),
        sequence=_require_sequence_field(data, "reconfiguration"),
    )
    expected = derive_reconfiguration_id(
        record.activation_id,
        record.binding_id,
        record.applied_requirements,
        record.applied_instant,
        record.sequence,
    )
    if record.reconfiguration_id != expected:
        raise AdapterError(
            AdapterReasonCode.SERIALIZATION_INVALID,
            "reconfiguration_id does not match the derived identity (tamper evidence)",
        )
    return record


def release_receipt_from_mapping(value: object) -> ReleaseReceipt:
    """Reconstruct a :class:`ReleaseReceipt` from its canonical mapping."""
    data = _require_mapping(value, "release receipt")
    activation_id = data.get("activation_id")
    reservation_id = data.get("reservation_id")
    binding_id = data.get("binding_id")
    kinds_raw = data.get("released_kinds")
    if not isinstance(kinds_raw, Sequence) or isinstance(kinds_raw, (str, bytes)):
        raise AdapterError(
            AdapterReasonCode.SERIALIZATION_INVALID,
            "release receipt kinds must be a sequence of strings",
        )
    for item in kinds_raw:
        if item not in ("activation", "reservation"):
            raise AdapterError(
                AdapterReasonCode.SERIALIZATION_INVALID,
                "release receipt kind %r is not in the vocabulary" % (item,),
            )
    record = ReleaseReceipt(
        release_id=validate_nonempty_str(data.get("release_id"), "release_id", 128),
        adapter_id=validate_nonempty_str(data.get("adapter_id"), "adapter_id"),
        activation_id=(
            None
            if activation_id is None
            else validate_nonempty_str(activation_id, "activation_id", 128)
        ),
        reservation_id=(
            None
            if reservation_id is None
            else validate_nonempty_str(reservation_id, "reservation_id", 128)
        ),
        binding_id=(
            None
            if binding_id is None
            else validate_nonempty_str(binding_id, "binding_id", 128)
        ),
        released_kinds=tuple(kinds_raw),
        released_instant=validate_instant(
            data.get("released_instant"), "released_instant"
        ),
        reason=validate_nonempty_str(data.get("reason"), "reason", 128),
        sequence=_require_sequence_field(data, "release receipt"),
    )
    expected = derive_release_id(
        record.adapter_id,
        record.reservation_id,
        record.activation_id,
        record.released_instant,
        record.sequence,
    )
    if record.release_id != expected:
        raise AdapterError(
            AdapterReasonCode.SERIALIZATION_INVALID,
            "release_id does not match the derived identity (tamper evidence)",
        )
    return record


# --------------------------------------------------------------------------
# The translation seam: 1.1 §6 operations over the WORK-016 runtime
# --------------------------------------------------------------------------


class CapabilityAdapter:
    """The disclosed WORK-016 -> 1.1 translation seam for ONE adapter.

    Wraps a registered adapter in a
    :class:`~adapters.runtime.AdapterRuntime` and exposes the frozen
    1.1 §6 capability-oriented surface.  Every operation composes
    through the WORK-016 runtime — the sandbox's exception isolation,
    contract-shape enforcement and deterministic step budgets stay in
    force mechanically (LOCK-110 preserved structurally).

    ``standard_mechanisms`` are the LOCK-112 citation tags the
    reference adapter declares for the mechanisms its family models
    (DATA with issuer provenance; the boundary never branches on
    them).

    Result convention (inherited verbatim from the WORK-016 runtime):

    * CALLER-side input/state errors RAISE :class:`AdapterError`
      (unknown adapter, malformed requirements, unknown activation);
    * ADAPTER-side faults and deterministic runtime rejections RETURN
      :class:`~adapters.runtime.AdapterOpResult` with a typed
      :class:`~adapters.sandbox.AdapterFailure` — isolated values,
      never exceptions.

    The activation ledger (adapter-local execution bookkeeping,
    LOCK-117: data, never authority) is deterministic: content-derived
    ids, injected instants, monotone sequence, no randomness.  Failed
    operations never advance the sequence (the ledger only moves on
    committed effects).
    """

    def __init__(
        self,
        runtime: AdapterRuntime,
        adapter_id: str,
        *,
        standard_mechanisms: Sequence[str] = (),
    ) -> None:
        if not isinstance(runtime, AdapterRuntime):
            raise AdapterError(
                AdapterReasonCode.INVALID_INPUT,
                "runtime must be a WORK-016 AdapterRuntime (the seam composes "
                "through the mediated runtime; it never bypasses it)",
            )
        validate_nonempty_str(adapter_id, "adapter_id")
        if not isinstance(standard_mechanisms, (list, tuple)):
            raise AdapterError(
                AdapterReasonCode.INVALID_INPUT,
                "standard mechanisms must be a sequence of citation tags",
            )
        if len(standard_mechanisms) > MAX_STANDARD_MECHANISMS:
            raise AdapterError(
                AdapterReasonCode.INVALID_INPUT,
                "at most %d standard-mechanism tags are declarable"
                % MAX_STANDARD_MECHANISMS,
            )
        for tag in standard_mechanisms:
            validate_nonempty_str(tag, "standard mechanism tag", 128)
        descriptor = runtime.get(adapter_id)  # fail-closed unknown adapter
        self._runtime = runtime
        self._adapter_id = adapter_id
        self._standard_mechanisms: Tuple[str, ...] = tuple(standard_mechanisms)
        self._descriptor: AdapterDescriptor = descriptor
        self._activations: Dict[str, Activation] = {}
        self._measurements: Dict[str, List[Measurement]] = {}
        self._sequence = 0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def adapter_id(self) -> str:
        return self._adapter_id

    @property
    def access_technology_id(self) -> str:
        return self._descriptor.access_technology_id

    @property
    def standard_mechanisms(self) -> Tuple[str, ...]:
        return self._standard_mechanisms

    def activation(self, activation_id: str) -> Activation:
        """One activation record (fail-closed on unknown id)."""
        with self._lock:
            record = self._activations.get(activation_id)
        if record is None:
            raise AdapterError(
                AdapterReasonCode.ALLOCATION_UNKNOWN,
                "activation %s is unknown to this adapter's activation ledger"
                % activation_id,
            )
        return record

    def activations(self) -> Tuple[Activation, ...]:
        """All activation records, deterministic (sorted by id)."""
        with self._lock:
            return tuple(self._activations[key] for key in sorted(self._activations))

    def measurements(self, activation_id: str) -> Tuple[Measurement, ...]:
        """The measurement trail for one activation (deterministic)."""
        with self._lock:
            trail = self._measurements.get(activation_id, [])
        return tuple(trail)

    # ------------------------------------------------------------------
    # 1.1 §6 operations (every one composes through the runtime)
    # ------------------------------------------------------------------

    def inspect_capabilities(self, *, now: str) -> AdapterOpResult:
        """``inspect_capabilities``: the mediated capability view.

        Composes the runtime's mediated, descriptor-filtered capability
        references (a FAILED or non-open adapter exposes nothing) with
        the descriptor's declared data and the LOCK-112 mechanism
        tags.  Deterministic pure function of (runtime state, now).
        """
        validate_instant(now, "now")
        references = self._runtime.capabilities(self._adapter_id, now=now)
        lifecycle = self._runtime.lifecycle(self._adapter_id)
        view = CapabilityView(
            adapter_id=self._adapter_id,
            access_technology_id=self._descriptor.access_technology_id,
            capability_references=tuple(references),
            standard_mechanisms=self._standard_mechanisms,
            computed_instant=now,
            lifecycle=lifecycle,
        )
        return AdapterOpResult(ok=True, value=view)

    def inspect_offers(self, *, now: str) -> AdapterOpResult:
        """``inspect_offers``: the provider-neutral inventory views.

        One :class:`OfferView` per descriptor resource-mapping entry
        (declared data), annotated with the mediated current capability
        references.  Provider-local (LOCK-105: no topology crosses),
        LOCK-118 issuer/inspect provenance, never an M003 authority
        object.
        """
        validate_instant(now, "now")
        references = self._runtime.capabilities(self._adapter_id, now=now)
        views = tuple(
            OfferView(
                adapter_id=self._adapter_id,
                access_technology_id=self._descriptor.access_technology_id,
                technology_resource=entry.technology_resource,
                kind=entry.kind,
                unit=entry.unit,
                quantity=entry.quantity,
                availability=entry.availability,
                capability_references=tuple(references),
                standard_mechanisms=self._standard_mechanisms,
                inspect_instant=now,
            )
            for entry in self._descriptor.resource_mapping
        )
        return AdapterOpResult(ok=True, value=views)

    def reserve(
        self,
        *,
        kind: str,
        quantity: int,
        unit: str,
        purpose: str,
        now: str,
        expires_at: Optional[str] = None,
    ) -> AdapterOpResult:
        """``reserve`` -> the WORK-016 ``allocate`` translation.

        Reserves adapter-scoped mapped capacity (integer base units,
        lease expiry) and returns the typed
        :class:`~adapters.model.Allocation` — the reservation record,
        content-derived id, canonical, provider-neutral.
        """
        validate_instant(now, "now")
        return self._runtime.allocate(
            self._adapter_id,
            kind=kind,
            quantity=quantity,
            unit=unit,
            purpose=purpose,
            now=now,
            expires_at=expires_at,
        )

    def activate(
        self,
        *,
        reservation_id: str,
        session_id: str,
        requirements: Optional[Mapping[str, Any]] = None,
        now: str,
    ) -> AdapterOpResult:
        """``activate`` -> the WORK-016 ``bind_session`` translation.

        Puts a RESERVED (ACTIVE allocation) capacity slice into service
        for one ADCOS session (read-only WORK-012 bindability
        verification happens inside the runtime, fail-closed).  Returns
        the new typed :class:`Activation` ledger record.
        """
        validate_instant(now, "now")
        validate_nonempty_str(session_id, "session_id")
        canonical_requirements: Tuple[Tuple[str, Any], ...] = ()
        if requirements is not None:
            canonical_requirements = validate_sequence_mapping(
                requirements, "activation requirements"
            )
        try:
            allocation = self._runtime.allocation(reservation_id)
        except AdapterError as exc:
            raise AdapterError(
                AdapterReasonCode.ALLOCATION_UNKNOWN,
                "reservation %s is unknown: %s" % (reservation_id, exc.detail),
            ) from None
        if allocation.adapter_id != self._adapter_id:
            raise AdapterError(
                AdapterReasonCode.ALLOCATION_UNKNOWN,
                "reservation %s belongs to adapter %s, not %s"
                % (reservation_id, allocation.adapter_id, self._adapter_id),
            )
        if allocation.state != AllocationState.ACTIVE:
            raise AdapterError(
                AdapterReasonCode.ALLOCATION_STATE,
                "reservation %s is %s (only ACTIVE reservations can activate)"
                % (reservation_id, allocation.state),
            )
        bind = self._runtime.bind_session(
            self._adapter_id, session_id=session_id, now=now, requirements=requirements
        )
        if not bind.ok or bind.value is None:
            return bind
        binding = bind.value
        with self._lock:
            self._sequence += 1
            activation_id = derive_activation_id(
                self._adapter_id, reservation_id, session_id, now, self._sequence
            )
            record = Activation(
                activation_id=activation_id,
                adapter_id=self._adapter_id,
                reservation_id=reservation_id,
                session_id=session_id,
                binding_id=binding.binding_id,
                requirements=canonical_requirements,
                created_instant=now,
                last_reconfigured_instant=None,
                state=ActivationState.ACTIVE,
                sequence=self._sequence,
            )
            self._activations[activation_id] = record
            self._measurements[activation_id] = []
        return AdapterOpResult(ok=True, value=record)

    def measure(
        self,
        *,
        activation_id: Optional[str] = None,
        now: str,
    ) -> AdapterOpResult:
        """``measure`` -> the WORK-016 ``observe`` translation.

        Collects one mediated observation of the generic link metrics
        and returns a typed :class:`Measurement`.  With
        ``activation_id`` the measurement is attributed to that
        activation (which must be in an active state); without it the
        measurement is adapter-level.  Adapter-REPORTED data, never
        topology authority.
        """
        validate_instant(now, "now")
        attribution: Optional[Activation] = None
        if activation_id is not None:
            validate_nonempty_str(activation_id, "activation_id", 128)
            attribution = self.activation(activation_id)
            if attribution.state == ActivationState.RELEASED:
                raise AdapterError(
                    AdapterReasonCode.STATE_CONFLICT,
                    "activation %s is RELEASED (terminal); it cannot be measured"
                    % activation_id,
                )
            with self._lock:
                trail = self._measurements.get(activation_id, [])
                if len(trail) >= MAX_MEASUREMENTS_PER_ACTIVATION:
                    raise AdapterError(
                        AdapterReasonCode.INVALID_INPUT,
                        "activation %s already carries the maximum of %d "
                        "measurements"
                        % (activation_id, MAX_MEASUREMENTS_PER_ACTIVATION),
                    )
        observe = self._runtime.observe(self._adapter_id, now=now)
        if not observe.ok:
            return observe
        samples = observe.value if isinstance(observe.value, tuple) else ()
        sample_dicts = tuple(sample.to_dict() for sample in samples)
        with self._lock:
            self._sequence += 1
            measurement = Measurement(
                measurement_id=derive_measurement_id(
                    self._adapter_id,
                    activation_id,
                    sample_dicts,
                    now,
                    self._sequence,
                ),
                adapter_id=self._adapter_id,
                activation_id=activation_id,
                samples=sample_dicts,
                collected_instant=now,
                sequence=self._sequence,
            )
            if attribution is not None:
                self._measurements.setdefault(activation_id, []).append(measurement)
        return AdapterOpResult(ok=True, value=measurement)

    def reconfigure(
        self,
        *,
        activation_id: str,
        requirements: Mapping[str, Any],
        now: str,
    ) -> AdapterOpResult:
        """``reconfigure`` -> the disclosed re-bind translation.

        The WORK-016 surface has no mid-session reconfiguration
        primitive, so the seam translates one onto the deterministic
        pair (``unbind_session``, ``bind_session``) with the SAME
        session id and the NEW requirements: the previous binding is
        released first (explicit, auditable teardown — the runtime
        records the unbind event), the reservation is preserved, and a
        new binding is created.  A failure at either step is an
        isolated value; the activation ledger never advances to
        RECONFIGURED on a failed reconfiguration.

        Typed transition: ACTIVE -> RECONFIGURED (idempotent from
        RECONFIGURED — repeated reconfigurations are the reference
        semantics of standards-native steering/reweighting updates).
        """
        validate_instant(now, "now")
        validate_nonempty_str(activation_id, "activation_id", 128)
        if not isinstance(requirements, Mapping):
            raise AdapterError(
                AdapterReasonCode.INVALID_INPUT,
                "reconfigure requirements must be a mapping",
            )
        canonical_requirements = validate_sequence_mapping(
            requirements, "reconfigure requirements"
        )
        current = self.activation(activation_id)
        if current.state == ActivationState.RELEASED:
            raise AdapterError(
                AdapterReasonCode.STATE_CONFLICT,
                "activation %s is RELEASED (terminal); it cannot be reconfigured"
                % activation_id,
            )
        if not activation_transition_is_legal(
            current.state, ActivationState.RECONFIGURED
        ):
            raise AdapterError(
                AdapterReasonCode.STATE_CONFLICT,
                "activation state %s cannot transition to RECONFIGURED"
                % current.state,
            )
        # Step 1: release the previous binding (mediated; isolated value).
        unbind = self._runtime.unbind_session(current.binding_id, now=now)
        if not unbind.ok:
            return unbind
        # Step 2: create the new binding with the new requirements.
        bind = self._runtime.bind_session(
            self._adapter_id,
            session_id=current.session_id,
            now=now,
            requirements=dict(requirements),
        )
        if not bind.ok or bind.value is None:
            # Step 1 committed, step 2 failed: the activation is TORN
            # (binding released, reservation held).  The ledger keeps
            # the activation visible in its previous state with its
            # (now released) binding id; the caller must release the
            # activation explicitly (release() tolerates the already-
            # released binding).  No silent partial success.
            failure = AdapterFailure(
                adapter_id=self._adapter_id,
                operation="reconfigure",
                reason=AdapterReasonCode.BINDING_STATE,
                instant=now,
                detail="re-bind failed after the previous binding was "
                "released; the activation is torn (binding released, "
                "reservation held) and must be released explicitly",
            )
            return AdapterOpResult(ok=False, failure=failure)
        binding = bind.value
        with self._lock:
            self._sequence += 1
            reconfigured = Activation(
                activation_id=current.activation_id,
                adapter_id=current.adapter_id,
                reservation_id=current.reservation_id,
                session_id=current.session_id,
                binding_id=binding.binding_id,
                requirements=canonical_requirements,
                created_instant=current.created_instant,
                last_reconfigured_instant=now,
                state=ActivationState.RECONFIGURED,
                sequence=current.sequence,
            )
            self._activations[reconfigured.activation_id] = reconfigured
            record = Reconfiguration(
                reconfiguration_id=derive_reconfiguration_id(
                    activation_id,
                    binding.binding_id,
                    canonical_requirements,
                    now,
                    self._sequence,
                ),
                activation_id=activation_id,
                adapter_id=self._adapter_id,
                session_id=current.session_id,
                reservation_id=current.reservation_id,
                previous_binding_id=current.binding_id,
                binding_id=binding.binding_id,
                applied_requirements=canonical_requirements,
                applied_instant=now,
                sequence=self._sequence,
            )
        return AdapterOpResult(ok=True, value=record)

    def release(
        self,
        *,
        activation_id: Optional[str] = None,
        reservation_id: Optional[str] = None,
        now: str,
        reason: str = "explicit-release",
    ) -> AdapterOpResult:
        """``release`` -> the WORK-016 release/unbind translation.

        * ``activation_id`` given: tears the activation down — the
          binding is unbound (mediated; an already-released binding,
          e.g. after a torn reconfiguration, is tolerated and skipped)
          and the underlying reservation is released (mediated); the
          activation is marked RELEASED.
        * only ``reservation_id`` given: releases the reservation (the
          cancellation edge; the reservation must not be held by a
          live activation).
        * both ``None`` is a caller error (fail closed).

        Returns a typed :class:`ReleaseReceipt`; a failed mediated
        teardown is an isolated value and never produces a receipt.
        """
        validate_instant(now, "now")
        validate_nonempty_str(reason, "reason", 128)
        if activation_id is None and reservation_id is None:
            raise AdapterError(
                AdapterReasonCode.INVALID_INPUT,
                "release requires an activation_id and/or a reservation_id",
            )
        if activation_id is not None:
            validate_nonempty_str(activation_id, "activation_id", 128)
            current = self.activation(activation_id)
            if current.state == ActivationState.RELEASED:
                raise AdapterError(
                    AdapterReasonCode.STATE_CONFLICT,
                    "activation %s is already RELEASED (terminal)" % activation_id,
                )
            binding = self._runtime.binding(current.binding_id)
            if binding.state == BindingState.BOUND:
                unbind = self._runtime.unbind_session(current.binding_id, now=now)
                if not unbind.ok:
                    return unbind
            release_allocation = self._runtime.release(
                current.reservation_id, now=now
            )
            if not release_allocation.ok:
                # The binding may be released but the reservation
                # teardown failed: keep the activation visible so the
                # caller can retry; never a silent partial success.
                return release_allocation
            with self._lock:
                self._sequence += 1
                released = Activation(
                    activation_id=current.activation_id,
                    adapter_id=current.adapter_id,
                    reservation_id=current.reservation_id,
                    session_id=current.session_id,
                    binding_id=current.binding_id,
                    requirements=current.requirements,
                    created_instant=current.created_instant,
                    last_reconfigured_instant=current.last_reconfigured_instant,
                    state=ActivationState.RELEASED,
                    sequence=current.sequence,
                )
                self._activations[released.activation_id] = released
                receipt = ReleaseReceipt(
                    release_id=derive_release_id(
                        self._adapter_id,
                        current.reservation_id,
                        activation_id,
                        now,
                        self._sequence,
                    ),
                    adapter_id=self._adapter_id,
                    activation_id=activation_id,
                    reservation_id=current.reservation_id,
                    binding_id=current.binding_id,
                    released_kinds=("activation", "reservation"),
                    released_instant=now,
                    reason=reason,
                    sequence=self._sequence,
                )
            return AdapterOpResult(ok=True, value=receipt)
        # Reservation-only release (the cancellation edge).
        validate_nonempty_str(reservation_id, "reservation_id", 128)
        holder = None
        with self._lock:
            for key in sorted(self._activations):
                record = self._activations[key]
                if (
                    record.reservation_id == reservation_id
                    and record.state != ActivationState.RELEASED
                ):
                    holder = record
                    break
        if holder is not None:
            raise AdapterError(
                AdapterReasonCode.ALLOCATION_STATE,
                "reservation %s is held by live activation %s; release the "
                "activation first" % (reservation_id, holder.activation_id),
            )
        release_allocation = self._runtime.release(reservation_id, now=now)
        if not release_allocation.ok:
            return release_allocation
        with self._lock:
            self._sequence += 1
            receipt = ReleaseReceipt(
                release_id=derive_release_id(
                    self._adapter_id,
                    reservation_id,
                    None,
                    now,
                    self._sequence,
                ),
                adapter_id=self._adapter_id,
                activation_id=None,
                reservation_id=reservation_id,
                binding_id=None,
                released_kinds=("reservation",),
                released_instant=now,
                reason=reason,
                sequence=self._sequence,
            )
        return AdapterOpResult(ok=True, value=receipt)

    def health(self, *, now: str) -> AdapterOpResult:
        """``health`` -> the mediated WORK-016 health report.

        Returns the typed :class:`~adapters.model.HealthReport` (the
        effective computed state; LOCK-017: the implementation's
        report is data, never authority).  Pure deterministic read.
        """
        validate_instant(now, "now")
        report = self._runtime.health(self._adapter_id, now=now)
        return AdapterOpResult(ok=True, value=report)
