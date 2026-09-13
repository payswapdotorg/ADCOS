"""ADCOS future-IMT M023 reference composition (R9-CORE-001, DEC-0120
— the chain-independent Future Technology Extension Drill).

The M023 drill's synthetic future-IMT/6G-class technology — an access
technology the 1.1 architecture NEVER named — composed into ADCOS
ENTIRELY through the accepted public extension surface: this module
is one reference adapter composition in the EXACT pattern of the
accepted M007 modules (``adapters/reference/backhaul.py`` /
``adapters/reference/wifi.py`` — one module per family, composing a
runtime into a WORK-016 ``AdapterContract`` the 1.1 capability
boundary registers), with ZERO contract-core delta.

Because NO accepted family runtime exists for future-IMT (the M007
six model named standards families only), this module carries its
OWN deterministic reference engine —
:class:`ReferenceFutureImtEngine`, a pure function of its injected
instants (LOCK-119: no wall clock, no randomness, no network, no
secrets) — exposed through the SAME ``AdapterContract`` (the frozen
WORK-016 nine-op section 10.1 shape) and registered through the
accepted ``adapters/capability.py`` seam (LOCK-110/LOCK-112: the
core imports nothing from this module and branches on no technology
name).  The composition is offered through the accepted
``offers/``/``capabilities/`` exchange semantics, bridged by the
accepted ``executionplans/`` LOCK-109 surface, and admitted by the
accepted ``eligibility/``/``policy/`` gates — ALL consumed BY
REFERENCE through their public APIs by the delivery battery
(:mod:`tools.futureimt_selftest`); this module itself composes REAL
offer-exchange material for no one and re-decides nothing.

Harvest disclosure (the frozen migration matrix): the legacy 1.0
``imt/`` domain (WORK-038) is SOURCE MATERIAL ONLY for the modeling
vocabulary — the reserved WORK-002 registry path
``access.3gpp.nr.imt2030``, the open-world well-formed probe id
``access.3gpp.future.unknown`` (architecture section 8's own
example), the ``imt2030:`` opaque-ref grammar, the
``imt2030-study-1`` profile version, and the study-class citation
tags.  This module NEVER imports ``imt/`` (1.0 material is never a
forward dependency): the future-IMT semantics are RE-EXPRESSED on
the accepted 1.1 authorities.  No other module in the repository
imports this one (the one-way boundary; the battery's import audit
proves it).

The declared future-technology capability surface (the semantics
declared BY THIS MODULE, deterministically — the drill's synthetic
technology):

* **Terahertz-carrier-class bandwidth ranges** — the declared
  carrier range :data:`CARRIER_BANDWIDTH_RANGE_GBPS` (10..100 Gbps)
  mapped onto the WORK-008 ``bandwidth`` kind (``gbps`` unit); the
  reference composition provisions the fixed 100 Gbps carrier
  (:data:`REFERENCE_CARRIER_GBPS`).  A binding that names a carrier
  outside the declared range is a typed rejection (fail closed).
* **Holographic-latency-class bounds** — the declared bound
  :data:`HOLOGRAPHIC_LATENCY_BOUND_US` (100 microseconds), declared
  DATA only: the observable surface stays the generic
  technology-neutral link-metric vocabulary (LOCK-110 —
  technology-specific counters never cross the boundary).
* **AI-native adaptive beams** — the declared beam-class vocabulary
  :data:`REFERENCE_BEAM_CLASSES` (``thz-wideband`` — the wide-area
  reference beam, ``thz-focused`` — the focused high-gain reference
  beam): bindings name a declared beam class deterministically;
  an undeclared class is a typed rejection (never a warning).

LOCK-112 (standard leverage — study-class citations for a
technology with no deployed standard yet, declared as DATA, never
branch input):

* ``itu-r-m2160-imt2030-framework`` — the ITU-R IMT-2030 framework
  recommendation (the real study framework the synthetic semantics
  model);
* ``3gpp-rel-20-imt2030-study`` — the 3GPP IMT-2030 study track;
* ``ieee-802-15-3d-thz`` — IEEE 802.15.3d (the terahertz WPAN
  carrier class the declared bandwidth range models).

The tags are citation DATA carried in the 1.1 views
(:attr:`STANDARD_MECHANISMS`); the boundary never branches on them.

LOCK-110 (SDK isolation) is structural here, inherited from the
composed surfaces: every 1.1 operation returns typed, canonical,
provider-neutral records through the accepted
:class:`~adapters.capability.CapabilityAdapter` seam; the opaque
``imt2030:beam-grant:<seq>`` / ``imt2030:beam:<seq>`` technology
references stay behind the WORK-016 runtime (keyed internally,
passed back on release); the core imports no adapter implementation
and branches on no technology name.  Adapter identity stays the
WORK-016 grammar (``adcos:adapter:...``), distinct from NodeID.

ZERO CONTRACT-CORE DELTA: this module imports NO ``contracts/``
surface AT ALL and writes no contract state (the battery's AST
import audit and structural probe prove it); activations are
adapter-LOCAL execution bookkeeping under LOCK-117 (never a second
contract authority — the M002 ``contracts/`` domain stays the sole
authority for acquired connectivity).

Determinism (LOCK-119): fixed reference profile (the 100 Gbps
carrier, 8 beam associations, fixed declared beam classes and
ranges); injected instants only; no wall clock, no randomness, no
network, no secrets (credential SLOT NAMES only — never material).
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence, Tuple

from ..contract import AdapterContract
from ..errors import AdapterError, AdapterReasonCode
from ..model import (
    AdapterDescriptor,
    AdapterSecurityState,
    ResourceMappingEntry,
    derive_adapter_id,
)

__all__ = [
    "STANDARD_MECHANISMS",
    "REFERENCE_TECHNOLOGY_ID",
    "UNKNOWN_FUTURE_TECHNOLOGY_ID",
    "REFERENCE_LABEL",
    "REFERENCE_CAPABILITIES",
    "REFERENCE_BEAM_CLASSES",
    "REFERENCE_BEAM_CLASS",
    "CARRIER_BANDWIDTH_RANGE_GBPS",
    "REFERENCE_CARRIER_GBPS",
    "HOLOGRAPHIC_LATENCY_BOUND_US",
    "REFERENCE_BEAM_ASSOCIATIONS",
    "CREDENTIAL_SLOT_NAME",
    "STEP_CHARGES",
    "ReferenceFutureImtEngine",
    "reference_descriptor",
    "mount_reference",
]

#: The LOCK-112 study-class citation tags this synthetic technology's
#: reference adapter declares (citation DATA, never branch input).
STANDARD_MECHANISMS: Tuple[str, ...] = (
    "itu-r-m2160-imt2030-framework",
    "3gpp-rel-20-imt2030-study",
    "ieee-802-15-3d-thz",
)

#: The reference access technology for this composition — the
#: WORK-002 registry's own RESERVED future path (KNOWN by
#: classification: registered entries of any status, including the
#: reserved future path, classify KNOWN; reserved by WORK-002 "for
#: exactly this additive future registration", never activated —
#: activation is the standards body's act, not this drill's).
#: Harvested vocabulary: the legacy ``imt/`` domain declared the same
#: reserved path (SOURCE MATERIAL ONLY — never imported).
REFERENCE_TECHNOLOGY_ID = "access.3gpp.nr.imt2030"

#: The open-world probe identifier (architecture section 8's own
#: example, harvested vocabulary): a well-formed id ABSENT from the
#: registry — UNKNOWN_BUT_WELL_FORMED, preserved verbatim, registrable
#: as DATA, gaining no authority.  The battery's open-world case
#: registers a composition under this id through the same seam to
#: prove the boundary branches on no technology name.
UNKNOWN_FUTURE_TECHNOLOGY_ID = "access.3gpp.future.unknown"

#: Default instance label of the reference composition.
REFERENCE_LABEL = "futureimt-reference-0"

#: Capability references the reference composition declares
#: (UNKNOWN_BUT_WELL_FORMED in the WORK-005 grammar — preserved
#: verbatim; the seam mediates the live exposure).  The declared
#: future-IMT/6G-class surface: terahertz carrier, holographic-class
#: latency bound, AI-native adaptive beams, and the data-transfer
#: service capability (the legacy harvest's one profile-scoped
#: reference, re-expressed here).
REFERENCE_CAPABILITIES: Tuple[str, ...] = (
    "capability.profile.imt2030.terahertz-carrier",
    "capability.profile.imt2030.holographic-latency",
    "capability.profile.imt2030.adaptive-beam",
    "capability.profile.imt2030.data-transfer",
)

#: The declared AI-native adaptive-beam class vocabulary (module-local
#: declared DATA — the deterministic beam plan a binding names).
REFERENCE_BEAM_CLASSES: Tuple[str, ...] = (
    "thz-wideband",
    "thz-focused",
)

#: The reference beam class the composition hands back as the
#: binding requirement DATA (the wide-area reference beam).
REFERENCE_BEAM_CLASS = "thz-wideband"

#: The declared terahertz-carrier-class bandwidth range (integer
#: Gbps, inclusive bounds — declared DATA; a binding naming a carrier
#: outside the range is a typed rejection).
CARRIER_BANDWIDTH_RANGE_GBPS = (10, 100)

#: The reference carrier the composition provisions (integer Gbps —
#: the fixed deterministic reference shape, the declared range's
#: upper bound).
REFERENCE_CARRIER_GBPS = 100

#: The declared holographic-latency-class bound (integer
#: microseconds — declared DATA only; the observable surface stays
#: the generic link-metric vocabulary, LOCK-110).
HOLOGRAPHIC_LATENCY_BOUND_US = 100

#: The reference adaptive-beam association capacity (integer
#: concurrent beam associations — the deterministic reference
#: simulation shape).
REFERENCE_BEAM_ASSOCIATIONS = 8

#: The composition's credential SLOT NAME (LOCK-023/LOCK-119: the
#: name only — the boundary rejects secret-shaped material).
CREDENTIAL_SLOT_NAME = "imt2030-technology-credentials"

#: Deterministic step charges per operation (the WORK-016 budget
#: model — the GenericAdapter discipline; a hung/overrunning future
#: technology operation is the deterministic step-budget model, never
#: a wall-clock timeout).
STEP_CHARGES: dict = {
    "open": 4,
    "capabilities": 1,
    "observe": 2,
    "allocate": 10,
    "release": 4,
    "bind_session": 6,
    "unbind_session": 3,
    "health": 1,
    "close": 4,
}


class ReferenceFutureImtEngine(AdapterContract):
    """The module's OWN deterministic future-IMT reference engine.

    No accepted family runtime exists for future-IMT, so the
    composition carries this engine as its ``AdapterContract``
    implementation (the frozen WORK-016 nine-op section 10.1 shape —
    the exact ``GenericAdapter`` composition discipline, re-expressed
    on the future-IMT vocabulary).  Deterministic: sequence counters,
    injected instants, fixed step charges; no wall clock, no
    randomness, no network, no secrets (LOCK-119).

    The engine's declared semantics (THIS module's declarations —
    the drill's synthetic technology, deterministic):

    * ``capabilities()`` exposes the four declared
      ``capability.profile.imt2030.*`` references when OPEN, nothing
      otherwise;
    * ``observe()`` reports the generic link-metric vocabulary as
      pure functions of the engine's deterministic counters (the
      per-operation terahertz-class byte counters —
      ``1_000_000_000 * grants + bearers``; zero error/retransmit
      counters: the reference THz beam simulation shape);
    * ``allocate()`` mints opaque ``imt2030:beam-grant:<seq>``
      technology refs (the terahertz beam-grant vocabulary —
      LOCK-017: opaque handles, never authority);
    * ``bind_session()`` mints opaque ``imt2030:beam:<seq>`` bearer
      refs, validating the binding requirements against the declared
      beam-class vocabulary and the declared carrier range (a
      binding MUST name a declared beam class and an in-range
      integer carrier — typed ``invalid-input`` rejections on an
      undeclared class, an out-of-range or non-integer carrier, a
      missing member, or absent requirements: fail closed, the
      composition's own declared discipline);
    * ``health()`` reports DEGRADED while beam grants are
      outstanding (the deterministic adaptive-beam occupancy
      discipline — the harvested legacy ``imt/`` engine's shape),
      HEALTHY when open with none outstanding, FAILED when not open
      (LOCK-017: reported DATA, never authority — the runtime
      computes the effective state).

    The technology references are OPAQUE DATA (LOCK-017): preserved
    verbatim behind the runtime, passed back on release/unbind, and
    never used as ids, keys, or authority sources.
    """

    __slots__ = ("_sequence", "_open", "_beam_grants", "_beam_bearers")

    def __init__(self) -> None:
        self._sequence = 0
        self._open = False
        self._beam_grants: dict = {}
        self._beam_bearers: dict = {}

    # -- helpers ---------------------------------------------------------

    def _charge(self, context: Any, operation: str) -> None:
        context.charge(STEP_CHARGES.get(operation, 1))

    def _next(self) -> int:
        self._sequence += 1
        return self._sequence

    def _require_open(self) -> None:
        if not self._open:
            raise AdapterError(
                AdapterReasonCode.NOT_OPEN,
                "future-IMT reference engine is not open",
            )

    def _validate_binding_requirements(
        self, requirements: Optional[Mapping[str, Any]]
    ) -> Tuple[str, int]:
        """Validate the binding requirements against the declared
        future-IMT surface (fail closed, typed).

        The requirements MUST carry ``beam_class`` (a member of the
        declared beam-class vocabulary) and ``carrier_gbps`` (an
        integer inside the declared terahertz carrier range).  Every
        deviation is a typed ``invalid-input`` rejection — the
        module's own declared discipline, an ADAPTER-side fault the
        sandbox isolates as a failure VALUE (never an exception into
        core state).
        """
        if requirements is None:
            raise AdapterError(
                AdapterReasonCode.INVALID_INPUT,
                "future-IMT binding requirements are required: the beam "
                "class must be named (declared vocabulary: %s)"
                % ", ".join(REFERENCE_BEAM_CLASSES),
            )
        beam_class = requirements.get("beam_class")
        if beam_class not in REFERENCE_BEAM_CLASSES:
            raise AdapterError(
                AdapterReasonCode.INVALID_INPUT,
                "beam_class %r is not in the declared beam-class vocabulary "
                "(%s)" % (beam_class, ", ".join(REFERENCE_BEAM_CLASSES)),
            )
        carrier = requirements.get("carrier_gbps")
        if isinstance(carrier, bool) or not isinstance(carrier, int):
            raise AdapterError(
                AdapterReasonCode.INVALID_INPUT,
                "carrier_gbps must be an integer (the declared "
                "terahertz-carrier range is %d..%d Gbps)"
                % CARRIER_BANDWIDTH_RANGE_GBPS,
            )
        low, high = CARRIER_BANDWIDTH_RANGE_GBPS
        if not (low <= carrier <= high):
            raise AdapterError(
                AdapterReasonCode.INVALID_INPUT,
                "carrier_gbps %d is outside the declared terahertz-carrier "
                "range %d..%d Gbps" % (carrier, low, high),
            )
        return beam_class, carrier

    # -- contract --------------------------------------------------------

    def open(self, context: Any) -> None:
        self._charge(context, "open")
        self._open = True

    def capabilities(self) -> Sequence[str]:
        if not self._open:
            return ()
        return REFERENCE_CAPABILITIES

    def observe(self, context: Any) -> Mapping[str, int]:
        self._charge(context, "observe")
        self._require_open()
        from ..model import LinkMetricName

        # The deterministic terahertz-class byte counters: pure
        # functions of the engine's grant/bearer counters (no wall
        # clock, no randomness).  Technology specifics (the carrier
        # class, the latency bound) stay INSIDE — the observable
        # surface is the generic vocabulary (LOCK-110).
        traffic = 1_000_000_000 * (
            len(self._beam_grants) + len(self._beam_bearers)
        )
        return {
            LinkMetricName.LINK_UP: 1,
            LinkMetricName.RX_BYTES_TOTAL: traffic,
            LinkMetricName.TX_BYTES_TOTAL: traffic,
            LinkMetricName.RX_ERROR_COUNT: 0,
            LinkMetricName.TX_ERROR_COUNT: 0,
            LinkMetricName.RETRANSMIT_COUNT: 0,
        }

    def allocate(
        self,
        context: Any,
        *,
        kind: str,
        quantity_base: int,
        purpose: str,
    ) -> str:
        self._charge(context, "allocate")
        self._require_open()
        if isinstance(quantity_base, bool) or not isinstance(quantity_base, int):
            raise AdapterError(
                AdapterReasonCode.INVALID_INPUT,
                "allocation quantity must be an integer",
            )
        if quantity_base <= 0:
            raise AdapterError(
                AdapterReasonCode.INVALID_INPUT,
                "allocation quantity must be positive",
            )
        grant = "imt2030:beam-grant:%06d" % self._next()
        self._beam_grants[grant] = purpose
        return grant

    def release(self, context: Any, technology_ref: str) -> None:
        self._charge(context, "release")
        self._require_open()
        if technology_ref not in self._beam_grants:
            raise AdapterError(
                AdapterReasonCode.ALLOCATION_UNKNOWN,
                "future-IMT reference engine does not know beam grant "
                "(already released?)",
            )
        del self._beam_grants[technology_ref]

    def bind_session(
        self,
        context: Any,
        *,
        session_id: str,
        requirements: Optional[Mapping[str, Any]],
    ) -> str:
        self._charge(context, "bind_session")
        self._require_open()
        if not session_id:
            raise AdapterError(
                AdapterReasonCode.INVALID_INPUT,
                "session_id is required",
            )
        beam_class, _carrier = self._validate_binding_requirements(requirements)
        beam = "imt2030:beam:%s:%06d" % (
            beam_class.replace("-", "_"),
            self._next(),
        )
        self._beam_bearers[beam] = session_id
        return beam

    def unbind_session(self, context: Any, bearer_ref: str) -> None:
        self._charge(context, "unbind_session")
        self._require_open()
        if bearer_ref not in self._beam_bearers:
            raise AdapterError(
                AdapterReasonCode.BINDING_UNKNOWN,
                "future-IMT reference engine does not know beam bearer "
                "(already unbound?)",
            )
        del self._beam_bearers[bearer_ref]

    def health(self) -> str:
        from ..model import HealthState

        if not self._open:
            return HealthState.FAILED
        if self._beam_grants:
            # Deterministic adaptive-beam occupancy: outstanding beam
            # grants degrade the reference beam plan (reported DATA —
            # the harvested legacy discipline; the runtime computes
            # the effective state, LOCK-017).
            return HealthState.DEGRADED
        return HealthState.HEALTHY

    def close(self, context: Any) -> None:
        self._charge(context, "close")
        self._open = False
        self._beam_grants = {}
        self._beam_bearers = {}


def reference_descriptor(
    label: str = REFERENCE_LABEL,
    technology_id: str = REFERENCE_TECHNOLOGY_ID,
) -> AdapterDescriptor:
    """The reference registration descriptor for the future-IMT
    composition.

    ``technology_id`` defaults to the registry's reserved future path
    (KNOWN); the open-world probe id (UNKNOWN_BUT_WELL_FORMED)
    composes identically through the same constructor — the boundary
    branches on no technology name (the battery's open-world case).
    """
    return AdapterDescriptor(
        adapter_id=derive_adapter_id(technology_id, label),
        access_technology_id=technology_id,
        supported_profile_versions=("imt2030-study-1",),
        capabilities=REFERENCE_CAPABILITIES,
        resource_mapping=(
            ResourceMappingEntry(
                technology_resource="imt2030:terahertz-carrier-bandwidth",
                kind="bandwidth",
                unit="gbps",
                quantity=REFERENCE_CARRIER_GBPS,
                availability="reservation-based",
            ),
            ResourceMappingEntry(
                technology_resource="imt2030:adaptive-beam-associations",
                kind="coverage",
                unit="count",
                quantity=REFERENCE_BEAM_ASSOCIATIONS,
                availability="reservation-based",
            ),
        ),
        security_state=AdapterSecurityState(
            profile="baseline",
            credential_slots=(CREDENTIAL_SLOT_NAME,),
            attested=False,
        ),
    )


def mount_reference(
    *,
    now: str,
    label: str = REFERENCE_LABEL,
    technology_id: str = REFERENCE_TECHNOLOGY_ID,
) -> Tuple[AdapterContract, AdapterDescriptor, Mapping[str, Any]]:
    """Compose the future-IMT reference adapter (deterministic).

    Wires the module's OWN deterministic reference engine (no
    accepted family runtime exists for future-IMT) and hands back
    the registration products:

    ``(implementation, descriptor, binding_requirements)`` — the
    engine to register with the :class:`~adapters.runtime.AdapterRuntime`
    (composed by the accepted ``adapters/capability.py`` seam, never
    bypassed), the reference descriptor, and the canonical
    requirements map (``beam_class`` + ``carrier_gbps``) the caller
    passes to the 1.1 ``activate``/``reconfigure`` operations —
    module-declared wiring DATA naming the declared reference beam
    and the declared reference carrier, never an authority.

    ``now`` is the injected registration instant (LOCK-119 — never a
    wall clock); it seeds nothing random: the engine's determinism
    is its own counter discipline, so the same mount always yields
    the same products.
    """
    from ..validation import validate_instant

    validate_instant(now, "now")
    engine = ReferenceFutureImtEngine()
    return (
        engine,
        reference_descriptor(label=label, technology_id=technology_id),
        {
            "beam_class": REFERENCE_BEAM_CLASS,
            "carrier_gbps": REFERENCE_CARRIER_GBPS,
        },
    )
