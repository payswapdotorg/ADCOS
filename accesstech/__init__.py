"""ADCOS access-technology envelope package (M020 — Access Technology
Capability Envelope, R9-CORE-001, DEC-0120; the R9 charter's current
chain child, the chain root).

The typed access-technology envelope domain of the R9 charter M020
scope, composing the accepted R7/R8 authorities BY REFERENCE (the
M014/M019 convergence discipline — import and compose, never
reimplement, weaken, fork, or bypass):

- **Declared capability envelopes** (:mod:`accesstech.envelopes`):
  typed deterministic ranges over the capability dimensions
  (bandwidth, latency, jitter, availability windows), canonical-JSON
  serializable with content-derived identities (the LOCK-106
  discipline — deterministic ids from canonical bytes, never wall
  clock, never randomness), validated through the accepted
  open-world technology classifier (future technologies enter as
  data);
- **Degradation ladders** (:mod:`accesstech.ladders`): declared
  ordered sequences of degradation modes mapped onto the accepted
  ``resilience/`` realization-state vocabulary (the M008-owned
  REALIZING/DEGRADED/FAILED/SUPERSEDED kernel, imported BY REFERENCE
  and extended with named modes — never redefined, never a fifth
  state);
- **Handover characteristic declarations** (:mod:`accesstech.handovers`):
  per-handover-kind constraint-preservation declarations consumed BY
  REFERENCE from the accepted ``resilience/`` handover machinery
  (LOCK-108: the imported frozen constraint-kind vocabulary declared
  verbatim per kind — the full set, never weakened);
- **The technology-extension registration surface**
  (:mod:`accesstech.registry`): the exact declared path by which a
  new access technology (envelope + reference adapter composition +
  capability statement) registers through the accepted
  ``adapters/capability.py`` seam (the M007 LOCK-110/LOCK-112
  boundary) and the ``executionplans/`` LOCK-109 bridge with ZERO
  contract-core delta.

Authority boundaries (the layering contract, frozen 1.1):

- **LOCK-101/LOCK-117**: the accepted ``contracts/`` domain stays the
  sole authority for acquired connectivity; an envelope, ladder,
  handover declaration or registration is DECLARED DATA around that
  authority — never a second contract authority, never a carrier of
  constraint material (constraint preservation stays the accepted
  machinery's job).
- **LOCK-105**: no topology facts cross — the availability windows
  are technology-class-local declared intervals, never global
  infrastructure claims.
- **LOCK-106**: content-derived identities over canonical JSON
  (deterministic, tamper-evident at reconstruction).
- **LOCK-108**: every handover-kind declaration preserves the
  contract's hard-constraint set VERBATIM (the full imported frozen
  vocabulary; weakening declarations fail closed).
- **LOCK-110/LOCK-112**: access technologies enter ONLY through the
  accepted adapter boundary — the registration surface drives the
  accepted ``adapters/capability.py`` seam; the LOCK-112
  standard-mechanism tags are citation DATA, never a branch input.
- **LOCK-119**: no wall clock, no randomness, no network, no
  secrets; injected instants only; integer base units (canonical
  JSON rejects floats).

One-way imports (the R9 charter consumption rule): this package
imports the accepted authorities (``protocol``, ``contracts``,
``replan``, ``resilience``, ``adapters``, ``executionplans``); NO
accepted authority imports ``accesstech/``.
"""

from __future__ import annotations

from .errors import AccessTechError, AccessTechReason
from .envelopes import (
    AvailabilityWindow,
    AvailabilityWindows,
    BpsRange,
    CapabilityEnvelope,
    JitterMilliRange,
    LatencyMilliRange,
    derive_envelope_id,
    envelope_from_mapping,
    MAX_AVAILABILITY_WINDOWS,
)
from .ladders import (
    DegradationLadder,
    DegradationMode,
    derive_ladder_id,
    ladder_from_mapping,
    ladder_step,
    mode_realization_state,
    MAX_LADDER_MODES,
    REALIZATION_STATES,
    REALIZATION_TERMINAL_STATES,
)
from .handovers import (
    HANDOVER_KINDS,
    HandoverCharacteristics,
    declare_handover_kind,
    derive_characteristics_id,
    handover_characteristics_from_mapping,
    preserved_constraint_kinds,
)
from .registry import (
    REGISTRATION_OPERATIONS,
    TechnologyRegistration,
    TechnologyRegistry,
    register_access_technology,
    technology_registration_from_mapping,
    MAX_MECHANISMS,
)

__all__ = [
    # typed errors
    "AccessTechError",
    "AccessTechReason",
    # the capability envelopes
    "AvailabilityWindow",
    "AvailabilityWindows",
    "BpsRange",
    "CapabilityEnvelope",
    "JitterMilliRange",
    "LatencyMilliRange",
    "derive_envelope_id",
    "envelope_from_mapping",
    "MAX_AVAILABILITY_WINDOWS",
    # the degradation ladders (the consumed realization vocabulary)
    "DegradationLadder",
    "DegradationMode",
    "derive_ladder_id",
    "ladder_from_mapping",
    "ladder_step",
    "mode_realization_state",
    "MAX_LADDER_MODES",
    "REALIZATION_STATES",
    "REALIZATION_TERMINAL_STATES",
    # the handover characteristic declarations
    "HANDOVER_KINDS",
    "HandoverCharacteristics",
    "declare_handover_kind",
    "derive_characteristics_id",
    "handover_characteristics_from_mapping",
    "preserved_constraint_kinds",
    # the technology-extension registration surface
    "REGISTRATION_OPERATIONS",
    "TechnologyRegistration",
    "TechnologyRegistry",
    "register_access_technology",
    "technology_registration_from_mapping",
    "MAX_MECHANISMS",
]
