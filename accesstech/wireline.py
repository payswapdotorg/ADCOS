"""ADCOS wireline family envelope declarations (M021 — Wireline
Access Adapters, R9-CORE-001, DEC-0121; the R9 chain child whose M020
dependency is satisfied by the DEC-0121 acceptance).

The wireline family DECLARATIONS of the R9 charter M021 scope — the
capability envelopes, degradation ladders and handover declarations
for the Ethernet, fiber and enterprise-WAN access families — built
ONLY through the accepted M020 public surface (``accesstech.
envelopes`` / ``accesstech.ladders`` / ``accesstech.handovers`` /
``accesstech.registry``, imported here and NEVER edited): every
envelope is a :class:`~accesstech.envelopes.CapabilityEnvelope`
constructed through the accepted typed constructors, every ladder a
:class:`~accesstech.ladders.DegradationLadder` over the accepted
mode records, every handover declaration a
:func:`~accesstech.handovers.declare_handover_kind` product with the
machinery's own frozen semantics.  Nothing here redefines, weakens,
forks or bypasses the accepted M020 domain (the R9 charter
consumption rule); the registrations that carry these declarations
drive the accepted :func:`~accesstech.registry.register_access_
technology` surface over the M021 reference compositions
(``adapters/reference/wireline.py`` — the composition substrate this
module's declarations describe).

**Static-availability semantics (the wireline discipline).**  A
wireline access technology is STATIONARY: it has no mobility states
and no pass windows.  The declared surface expresses this exactly:

* the M020 envelope grammar carries NO mobility vocabulary at all
  (the four capability dimensions are bandwidth, latency, jitter and
  availability windows — no mobility member exists to declare), and
  these wireline declarations introduce none;
* the wireline availability dimension is ONE CONTINUOUS declared
  window — the technology's standing service interval
  (:func:`is_static_availability` /
  :func:`require_static_availability`, the typed discipline below);
  a MULTI-window availability declaration is pass/mobility-shaped —
  the M022 non-terrestrial discipline, never the wireline semantics
  — and a typed ENVELOPE_INCONSISTENT rejection on this surface
  (fail closed, never a warning).

**Degradation ladders as DECLARED CAPACITY STEPS.**  Every wireline
ladder is an ordered sequence of named capacity rungs mapped onto the
accepted M008-owned realization-state kernel (REALIZING at the
satisfying root, the explicit DEGRADED state on every middle rung —
each step a declared capacity step on the SAME explicit state — and
the explicit FAILED terminal rung).  Every step is an
EVIDENCE-VISIBLE transition: :func:`~accesstech.ladders.ladder_step`
descends exactly one rung deterministically, so each capacity step
is an explicit, recordable, content-identified transition (the
ladder identity and the rung names make every recorded step
tamper-evident through the LOCK-106 discipline).

One-way imports (the R9 charter consumption rule): this module
imports the accepted authorities inside ``accesstech`` itself
(relative imports only — no ``adapters`` import here, no accepted
authority outside ``accesstech``); NO accepted authority imports this
module (the M020-owned package prefix gains declaration modules, the
frozen ``accesstech/__init__.py`` surface stays untouched).

Determinism (LOCK-119): every declaration is a pure function of its
typed literal content — content-derived identities over canonical
JSON (LOCK-106), injected RFC 3339 UTC instants inside the declared
windows, integer base units, no wall clock, no randomness, no
network, no secrets.
"""

from __future__ import annotations

from typing import Dict, Tuple

from .envelopes import (
    AvailabilityWindow,
    AvailabilityWindows,
    BpsRange,
    CapabilityEnvelope,
    JitterMilliRange,
    LatencyMilliRange,
    envelope_from_mapping,
)
from .errors import AccessTechError, AccessTechReason
from .handovers import (
    HANDOVER_KINDS,
    HandoverCharacteristics,
    declare_handover_kind,
    handover_characteristics_from_mapping,
)
from .ladders import (
    DegradationLadder,
    DegradationMode,
    ladder_from_mapping,
    ladder_step,
    mode_realization_state,
)

__all__ = [
    "ETHERNET_TECHNOLOGY_CLASS",
    "FIBER_TECHNOLOGY_CLASS",
    "ENTERPRISE_WAN_TECHNOLOGY_CLASS",
    "WIRELINE_TECHNOLOGY_CLASSES",
    "WIRELINE_FAMILIES",
    "WIRELINE_ENVELOPES",
    "WIRELINE_LADDERS",
    "WIRELINE_HANDOVER_KINDS",
    "STATIC_SERVICE_INTERVAL",
    "is_static_availability",
    "require_static_availability",
    "wireline_handover_declarations",
]

#: The ETHERNET wireline family's technology class (KNOWN in the
#: WORK-002 registry — the IEEE 802.3 entry; the same registry entry
#: the accepted M007 backhaul reference composition declares).
ETHERNET_TECHNOLOGY_CLASS = "access.ieee.8023"

#: The FIBER wireline family's technology class (the ITU-T G.709
#: optical transport class — open-world well-formed declared data).
FIBER_TECHNOLOGY_CLASS = "access.itu.g709"

#: The ENTERPRISE-WAN wireline family's technology class (the
#: enterprise WAN class over IEEE 802.1Q bridged Ethernet —
#: open-world well-formed declared data).
ENTERPRISE_WAN_TECHNOLOGY_CLASS = "access.enterprise.wan"

#: The declared wireline technology classes (deterministic order).
WIRELINE_TECHNOLOGY_CLASSES: Tuple[str, ...] = (
    ETHERNET_TECHNOLOGY_CLASS,
    FIBER_TECHNOLOGY_CLASS,
    ENTERPRISE_WAN_TECHNOLOGY_CLASS,
)

#: The family labels the declarations key on (deterministic order;
#: one declaration set per family, the M020 battery's family-keyed
#: declaration shape).
WIRELINE_FAMILIES: Tuple[str, ...] = ("ethernet", "fiber", "enterprise-wan")

#: The ONE continuous declared service interval every wireline
#: envelope carries (the static-availability discipline: a standing
#: service interval, injected RFC 3339 UTC bounds — never wall clock).
STATIC_SERVICE_INTERVAL = (
    "2026-01-01T00:00:00Z",
    "2026-12-31T23:59:59Z",
)


def _static_windows() -> AvailabilityWindows:
    """The single continuous static window (the wireline
    standing-service declaration)."""
    start, end = STATIC_SERVICE_INTERVAL
    return AvailabilityWindows((AvailabilityWindow(start, end),))


#: The declared wireline capability envelopes per family: typed
#: deterministic integer ranges over the four capability dimensions,
#: each carrying EXACTLY ONE continuous static availability window
#: (the static-availability discipline — no mobility, no pass
#: windows; the M022 non-terrestrial discipline is a different
#: family's semantics and never appears here).
WIRELINE_ENVELOPES: Dict[str, CapabilityEnvelope] = {
    "ethernet": CapabilityEnvelope(
        technology_class=ETHERNET_TECHNOLOGY_CLASS,
        bandwidth=BpsRange(100_000_000, 1_000_000_000),
        latency=LatencyMilliRange(1, 20),
        jitter=JitterMilliRange(0, 5),
        availability=_static_windows(),
    ),
    "fiber": CapabilityEnvelope(
        technology_class=FIBER_TECHNOLOGY_CLASS,
        bandwidth=BpsRange(1_000_000_000, 100_000_000_000),
        latency=LatencyMilliRange(1, 15),
        jitter=JitterMilliRange(0, 2),
        availability=_static_windows(),
    ),
    "enterprise-wan": CapabilityEnvelope(
        technology_class=ENTERPRISE_WAN_TECHNOLOGY_CLASS,
        bandwidth=BpsRange(10_000_000, 10_000_000_000),
        latency=LatencyMilliRange(2, 50),
        jitter=JitterMilliRange(0, 10),
        availability=_static_windows(),
    ),
}

#: The declared wireline degradation ladders per family: DECLARED
#: CAPACITY STEPS (named rungs, each an explicit evidence-visible
#: transition) mapped onto the accepted M008-owned realization-state
#: kernel — REALIZING at the satisfying root, the explicit DEGRADED
#: state on every middle rung (a deeper declared capacity step on
#: the same explicit state), the explicit FAILED terminal rung
#: (every declared ladder carries its terminal).
WIRELINE_LADDERS: Dict[str, DegradationLadder] = {
    "ethernet": DegradationLadder(
        technology_class=ETHERNET_TECHNOLOGY_CLASS,
        modes=(
            DegradationMode("nominal", "REALIZING"),
            DegradationMode("capacity-75", "DEGRADED"),
            DegradationMode("capacity-50", "DEGRADED"),
            DegradationMode("capacity-25", "DEGRADED"),
            DegradationMode("link-failed", "FAILED"),
        ),
    ),
    "fiber": DegradationLadder(
        technology_class=FIBER_TECHNOLOGY_CLASS,
        modes=(
            DegradationMode("nominal", "REALIZING"),
            DegradationMode("capacity-75", "DEGRADED"),
            DegradationMode("capacity-50", "DEGRADED"),
            DegradationMode("trail-failed", "FAILED"),
        ),
    ),
    "enterprise-wan": DegradationLadder(
        technology_class=ENTERPRISE_WAN_TECHNOLOGY_CLASS,
        modes=(
            DegradationMode("nominal", "REALIZING"),
            DegradationMode("capacity-75", "DEGRADED"),
            DegradationMode("capacity-50", "DEGRADED"),
            DegradationMode("site-pair-lost", "DEGRADED"),
            DegradationMode("wan-failed", "FAILED"),
        ),
    ),
}

#: The declared handover kinds per wireline family (declared DATA —
#: the kinds are the M020 frozen four-kind vocabulary; the
#: characteristics are ALWAYS the accepted machinery's own frozen
#: semantics through :func:`declare_handover_kind`): every wireline
#: family declares the intra-technology kind (the access-internal
#: site-link reselection — the re-bind translation's declared
#: companion) and the cross-technology kind (the M024 interchange
#: drill); the enterprise-WAN family additionally declares the
#: replacement kind (the M024 technology-replacement drill over a
#: declared site interconnect).
WIRELINE_HANDOVER_KINDS: Dict[str, Tuple[str, ...]] = {
    "ethernet": ("intra-technology", "cross-technology"),
    "fiber": ("intra-technology", "cross-technology"),
    "enterprise-wan": ("intra-technology", "cross-technology", "replacement"),
}


# ----------------------------------------------------------------------
# The static-availability discipline (typed, fail-closed)
# ----------------------------------------------------------------------


def is_static_availability(envelope: CapabilityEnvelope) -> bool:
    """True iff the envelope's availability dimension is EXACTLY ONE
    continuous declared window — the wireline static-availability
    semantics (a standing service interval: no mobility, no pass
    windows; a multi-window declaration is the non-terrestrial
    pass/mobility shape, never the wireline semantics)."""
    if not isinstance(envelope, CapabilityEnvelope):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "is_static_availability requires a CapabilityEnvelope (got %s)"
            % type(envelope).__name__,
        )
    return len(envelope.availability.windows) == 1


def require_static_availability(envelope: CapabilityEnvelope) -> None:
    """The typed static-availability discipline: a wireline envelope
    declares EXACTLY ONE continuous operating window (the standing
    service interval).  A multi-window availability declaration on a
    wireline family is a typed ENVELOPE_INCONSISTENT rejection —
    pass/mobility-shaped availability is the non-terrestrial
    discipline (M022), never the wireline semantics (fail closed,
    never a warning)."""
    if not isinstance(envelope, CapabilityEnvelope):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "require_static_availability requires a CapabilityEnvelope "
            "(got %s)" % type(envelope).__name__,
        )
    windows = envelope.availability.windows
    if len(windows) != 1:
        raise AccessTechError(
            AccessTechReason.ENVELOPE_INCONSISTENT,
            "the wireline envelope for %s declares %d availability "
            "windows — static availability is EXACTLY ONE continuous "
            "declared window (the standing service interval; no "
            "mobility, no pass windows: a multi-window declaration is "
            "the non-terrestrial discipline, never the wireline "
            "semantics)"
            % (envelope.technology_class, len(windows)),
        )


def wireline_handover_declarations(
    family: str,
) -> Tuple[HandoverCharacteristics, ...]:
    """The handover declarations of ONE wireline family, built ONLY
    through the accepted :func:`~accesstech.handovers.
    declare_handover_kind` constructor (the machinery's own frozen
    semantics: the FULL imported constraint-kind preservation set,
    the mandatory explicit-reconnect discipline, the mandatory
    contract-continuity discipline — never weakened, never
    re-typed)."""
    if family not in WIRELINE_HANDOVER_KINDS:
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "family %r is not a declared wireline family (declared: %s)"
            % (family, ", ".join(WIRELINE_FAMILIES)),
        )
    return tuple(
        declare_handover_kind(kind) for kind in WIRELINE_HANDOVER_KINDS[family]
    )
