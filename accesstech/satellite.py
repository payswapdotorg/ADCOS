"""ADCOS satellite family envelope declarations (M022 — Non-Terrestrial
Access Adapters, R9-CORE-001, DEC-0122; the R9 chain child whose M020
and M021 dependencies are satisfied by the DEC-0121/DEC-0122
acceptances).

The non-terrestrial family DECLARATIONS of the R9 charter M022 scope —
the capability envelopes, degradation ladders, handover declarations
and declared pass schedules for the GSO, NGSO, LEO and mesh/IAB
access families — built ONLY through the accepted M020 public surface
(``accesstech.envelopes`` / ``accesstech.ladders`` /
``accesstech.handovers`` / ``accesstech.registry``, imported here and
NEVER edited): every envelope is a
:class:`~accesstech.envelopes.CapabilityEnvelope` constructed through
the accepted typed constructors, every ladder a
:class:`~accesstech.ladders.DegradationLadder` over the accepted mode
records, every handover declaration a
:func:`~accesstech.handovers.declare_handover_kind` product with the
machinery's own frozen semantics.  Nothing here redefines, weakens,
forks or bypasses the accepted M020 domain (the R9 charter
consumption rule); the registrations that carry these declarations
drive the accepted :func:`~accesstech.registry.register_access_
technology` surface over the M022 reference compositions
(``adapters/reference/satellite.py`` — the composition substrate this
module's declarations describe).

**Deterministic coverage windows (the non-terrestrial discipline).**
A non-terrestrial access technology serves through DECLARED
availability intervals — injected RFC 3339 UTC instants, never wall
clock (LOCK-119; the accepted envelope grammar rejects every
wall-clock-shaped instant value typed — no ``Z``-suffix-free or
offset-shaped value can enter a declared window):

* the **GSO** family declares its STANDING continuous window (the
  geostationary standing-service interval — one declared window, no
  pass transitions);
* the **NGSO** and **LEO** families declare their PASS WINDOWS (the
  deterministic coverage intervals of successive passes — ordered,
  non-overlapping declared windows on the accepted grammar; every
  window boundary is a declared pass transition);
* the **mesh/IAB** family declares its DTN-BRIDGED standing window
  (the sidelink relay mesh's standing service interval — the
  store-and-forward discipline bridges the relay gaps, so the service
  interval is continuous while the latency dimension admits the
  queueing delay).

The pass-shape discipline (:func:`is_pass_shaped` /
:func:`require_pass_shaped_envelope` /
:func:`require_handover_kinds_pass_consistent`, typed fail-closed
below): a family declaring the ``pass`` handover kind carries a
MULTI-window envelope (the pass geometry exists); a single-window
family never declares the pass kind (no pass transitions exist).

**Propagation-delay envelopes as typed declared ranges.**  The latency
dimension of every satellite envelope IS the family's typed declared
one-way propagation-delay range (integer milliseconds; the GSO trunk
~240-290 ms, NGSO passes ~70-120 ms, LEO passes ~10-55 ms, the
mesh/IAB sidelink+DTN relay ~10-600 ms with the store-and-forward
queueing admitted).  The margin discipline
(:func:`propagation_margin_ms` /
:func:`require_propagation_margin_ladder`): the declared service
latency budget over the envelope's declared propagation ceiling is
the NOMINAL propagation margin; a budget that does not admit the
ceiling is a typed ENVELOPE_INCONSISTENT rejection, never a warning.

**Degradation ladders with propagation-aware declared margin steps.**
Every satellite ladder's middle rungs are DECLARED MARGIN STEPS —
named rungs (``margin-75`` / ``margin-50`` / ``margin-25``) mapping
onto the accepted M008-owned realization-state kernel (REALIZING at
the satisfying root, the explicit DEGRADED state on every middle
rung, the explicit FAILED terminal rung): each step declares the
REMAINING propagation margin as a descending fraction of nominal, and
every step still covers the declared propagation floor (a rung whose
margin would drop below the floor is past the terminal, never a
middle DEGRADED rung — the typed LADDER_ILLEGAL rejection).  Each
step is an evidence-visible transition through the accepted
:func:`~accesstech.ladders.ladder_step` (deterministic walking; every
recorded step tamper-evident through the LOCK-106 discipline).

**The declared pass schedules (the NGSO/LEO pass-handover
geometry).**  :class:`PassSchedule` is the DECLARED geometry of the
pass handovers: the family's pass windows (exactly the envelope's own
declared windows — the cross-check
:func:`require_schedule_matches_envelope` is typed) plus the serving
reference of each pass.  Every ADJACENT pass pair is a
:class:`PassTransition` — a deterministic declared event naming the
OLD and the NEW serving references with the reconnect instant (the
new pass's opening instant).  Consecutive passes carrying the SAME
serving reference are a typed rejection (a transition that changes
nothing is not pass geometry); a schedule with fewer than two windows
is degenerate.  The transitions are DECLARED DATA consumed by the
composition battery, which drives each one through the ACCEPTED
``resilience/`` handover machinery (``perform_handover`` over the
RUNTIME journal — LOCK-108 verbatim constraint-set equality and the
WORK-012 explicit recorded reconnect discipline, enforced by the
machinery itself, never re-implemented here).

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

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from protocol.canonicalization import (
    CanonicalizationError,
    canonical_json_bytes,
)

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
    "GSO_TECHNOLOGY_CLASS",
    "NGSO_TECHNOLOGY_CLASS",
    "LEO_TECHNOLOGY_CLASS",
    "MESH_IAB_TECHNOLOGY_CLASS",
    "NON_TERRESTRIAL_TECHNOLOGY_CLASSES",
    "NON_TERRESTRIAL_FAMILIES",
    "NON_TERRESTRIAL_ENVELOPES",
    "NON_TERRESTRIAL_LADDERS",
    "NON_TERRESTRIAL_HANDOVER_KINDS",
    "PASS_SCHEDULE_FAMILIES",
    "GSO_STANDING_INTERVAL",
    "MESH_IAB_DTN_INTERVAL",
    "NGSO_PASS_WINDOWS",
    "LEO_PASS_WINDOWS",
    "NGSO_SERVING_REFS",
    "LEO_SERVING_REFS",
    "NGSO_PASS_SCHEDULE",
    "LEO_PASS_SCHEDULE",
    "MARGIN_FRACTIONS",
    "SERVICE_LATENCY_BUDGET_MS",
    "MESH_IAB_SERVICE_LATENCY_BUDGET_MS",
    "declared_service_budget_ms",
    "propagation_margin_ms",
    "require_propagation_margin_ladder",
    "is_pass_shaped",
    "require_pass_shaped_envelope",
    "require_handover_kinds_pass_consistent",
    "require_schedule_matches_envelope",
    "PassSchedule",
    "PassTransition",
    "derive_pass_schedule_id",
    "pass_schedule_from_mapping",
    "declared_pass_schedule",
    "non_terrestrial_handover_declarations",
]

#: The GSO family's technology class (the geostationary satellite
#: relay class — open-world well-formed declared data; the
#: architecture's registry never named it, so it enters as data,
#: exactly the R9 open-world classifier's design).
GSO_TECHNOLOGY_CLASS = "access.satellite.gso"

#: The NGSO family's technology class (the non-geostationary
#: constellation class — open-world well-formed declared data).
NGSO_TECHNOLOGY_CLASS = "access.satellite.ngso"

#: The LEO family's technology class (the low-earth-orbit
#: constellation class — open-world well-formed declared data).
LEO_TECHNOLOGY_CLASS = "access.satellite.leo"

#: The mesh/IAB family's technology class (KNOWN in the WORK-002
#: registry: the IAB entry — the same registry entry the accepted M007
#: mesh reference composition declares; the M021 ethernet-over-backhaul
#: precedent of composing on the accepted family's own class).
MESH_IAB_TECHNOLOGY_CLASS = "access.3gpp.iab"

#: The declared non-terrestrial technology classes (deterministic
#: order).
NON_TERRESTRIAL_TECHNOLOGY_CLASSES: Tuple[str, ...] = (
    GSO_TECHNOLOGY_CLASS,
    NGSO_TECHNOLOGY_CLASS,
    LEO_TECHNOLOGY_CLASS,
    MESH_IAB_TECHNOLOGY_CLASS,
)

#: The family labels the declarations key on (deterministic order;
#: one declaration set per family, the M020/M021 family-keyed
#: declaration shape).
NON_TERRESTRIAL_FAMILIES: Tuple[str, ...] = ("gso", "ngso", "leo", "mesh-iab")

#: The pass-shaped families (the families whose coverage windows are
#: pass windows and whose handover declarations carry the ``pass``
#: kind — the NGSO pass-handover geometry and its LEO sibling).
PASS_SCHEDULE_FAMILIES: Tuple[str, ...] = ("ngso", "leo")

#: The GSO family's STANDING continuous service interval (the
#: geostationary standing window — one declared availability window,
#: injected RFC 3339 UTC bounds, never wall clock; no pass
#: transitions).
GSO_STANDING_INTERVAL: Tuple[str, str] = (
    "2026-01-01T00:00:00Z",
    "2026-12-31T23:59:59Z",
)

#: The mesh/IAB family's DTN-BRIDGED standing service interval (the
#: sidelink relay mesh's standing window — the store-and-forward
#: discipline bridges the relay gaps, so the declared service interval
#: is continuous; the queueing delay is admitted on the latency
#: dimension).
MESH_IAB_DTN_INTERVAL: Tuple[str, str] = (
    "2026-01-01T00:00:00Z",
    "2026-12-31T23:59:59Z",
)

#: The NGSO family's declared pass windows (deterministic coverage
#: intervals of four successive passes — ordered, non-overlapping,
#: injected instants only; every window boundary is a declared pass
#: transition).
NGSO_PASS_WINDOWS: Tuple[Tuple[str, str], ...] = (
    ("2026-06-01T08:00:00Z", "2026-06-01T08:40:00Z"),
    ("2026-06-01T10:00:00Z", "2026-06-01T10:38:00Z"),
    ("2026-06-01T12:05:00Z", "2026-06-01T12:47:00Z"),
    ("2026-06-01T14:10:00Z", "2026-06-01T14:52:00Z"),
)

#: The LEO family's declared pass windows (six short passes — the
#: frequent-pass geometry; ordered, non-overlapping, injected
#: instants only).
LEO_PASS_WINDOWS: Tuple[Tuple[str, str], ...] = (
    ("2026-06-01T06:00:00Z", "2026-06-01T06:08:00Z"),
    ("2026-06-01T07:30:00Z", "2026-06-01T07:39:00Z"),
    ("2026-06-01T09:05:00Z", "2026-06-01T09:13:00Z"),
    ("2026-06-01T10:42:00Z", "2026-06-01T10:51:00Z"),
    ("2026-06-01T12:20:00Z", "2026-06-01T12:28:00Z"),
    ("2026-06-01T13:55:00Z", "2026-06-01T14:04:00Z"),
)

#: The NGSO serving references (one per declared pass window — the
#: constellation's deterministic serving sequence; the same satellite
#: serving two NON-adjacent passes is real geometry, adjacent repeats
#: are typed rejections).
NGSO_SERVING_REFS: Tuple[str, ...] = (
    "satellite:ngso-alpha",
    "satellite:ngso-bravo",
    "satellite:ngso-charlie",
    "satellite:ngso-alpha",
)

#: The LEO serving references (one per declared pass window — a large
#: constellation's deterministic serving sequence, every pass a
#: distinct satellite).
LEO_SERVING_REFS: Tuple[str, ...] = (
    "satellite:leo-01",
    "satellite:leo-02",
    "satellite:leo-03",
    "satellite:leo-04",
    "satellite:leo-05",
    "satellite:leo-06",
)

#: The declared propagation-aware margin fractions (the remaining
#: propagation-margin percentage each ladder rung declares —
#: descending, every step still above the propagation floor; the
#: margin-rung grammar the ladders below carry).
MARGIN_FRACTIONS: Tuple[int, ...] = (75, 50, 25)

#: The declared service latency budget the relay families' margin
#: discipline is evaluated against (an integer-millisecond declared
#: budget — the reference composition's deterministic service budget;
#: a deployment declares its own through the same typed helpers).
SERVICE_LATENCY_BUDGET_MS = 400

#: The declared service latency budget for the mesh/IAB family — the
#: DTN family's budget admits the store-and-forward queueing delay
#: its envelope declares (the latency ceiling INCLUDES the queueing;
#: the budget covers it with a declared margin).
MESH_IAB_SERVICE_LATENCY_BUDGET_MS = 800


def declared_service_budget_ms(family: str) -> int:
    """The family's declared service latency budget (the reference
    composition's deterministic budget — the relay families' 400 ms
    and the DTN family's 800 ms; the margin discipline is evaluated
    per family against its own declared budget)."""
    if family not in NON_TERRESTRIAL_FAMILIES:
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "family %r is not a declared non-terrestrial family (declared: "
            "%s)" % (family, ", ".join(NON_TERRESTRIAL_FAMILIES)),
        )
    if family == "mesh-iab":
        return MESH_IAB_SERVICE_LATENCY_BUDGET_MS
    return SERVICE_LATENCY_BUDGET_MS

#: Identity namespace (WORK-003 canonical-JSON SHA-256 convention).
_PASS_SCHEDULE_NAMESPACE = "adcos.accesstech.pass-schedule"

#: The margin-rung name grammar (``margin-<percent>``).
_MARGIN_RUNG_PATTERN = re.compile(r"^margin-(\d{1,3})$")


def _canonical_bytes(document: Mapping[str, Any], label: str) -> bytes:
    try:
        return canonical_json_bytes(dict(document))
    except (CanonicalizationError, TypeError, ValueError) as error:
        raise AccessTechError(
            AccessTechReason.SERIALIZATION_INVALID,
            "%s is not canonicalizable: %s" % (label, error),
        ) from None


def _windows(pairs: Sequence[Sequence[str]]) -> Tuple[AvailabilityWindow, ...]:
    return tuple(AvailabilityWindow(start, end) for start, end in pairs)


def _standing(interval: Tuple[str, str]) -> AvailabilityWindows:
    start, end = interval
    return AvailabilityWindows((AvailabilityWindow(start, end),))


#: The declared non-terrestrial capability envelopes per family: typed
#: deterministic integer ranges over the four capability dimensions —
#: the LATENCY dimension is the family's typed declared one-way
#: PROPAGATION-DELAY range; the AVAILABILITY dimension is the
#: family's declared deterministic coverage windows (the GSO standing
#: window, the NGSO/LEO pass windows, the mesh/IAB DTN-bridged
#: standing window).
NON_TERRESTRIAL_ENVELOPES: Dict[str, CapabilityEnvelope] = {
    "gso": CapabilityEnvelope(
        technology_class=GSO_TECHNOLOGY_CLASS,
        bandwidth=BpsRange(2_000_000, 500_000_000),
        latency=LatencyMilliRange(240, 290),
        jitter=JitterMilliRange(0, 30),
        availability=_standing(GSO_STANDING_INTERVAL),
    ),
    "ngso": CapabilityEnvelope(
        technology_class=NGSO_TECHNOLOGY_CLASS,
        bandwidth=BpsRange(10_000_000, 1_000_000_000),
        latency=LatencyMilliRange(70, 120),
        jitter=JitterMilliRange(0, 20),
        availability=AvailabilityWindows(_windows(NGSO_PASS_WINDOWS)),
    ),
    "leo": CapabilityEnvelope(
        technology_class=LEO_TECHNOLOGY_CLASS,
        bandwidth=BpsRange(50_000_000, 2_000_000_000),
        latency=LatencyMilliRange(10, 55),
        jitter=JitterMilliRange(0, 15),
        availability=AvailabilityWindows(_windows(LEO_PASS_WINDOWS)),
    ),
    "mesh-iab": CapabilityEnvelope(
        technology_class=MESH_IAB_TECHNOLOGY_CLASS,
        bandwidth=BpsRange(1_000_000, 400_000_000),
        latency=LatencyMilliRange(10, 600),
        jitter=JitterMilliRange(0, 200),
        availability=_standing(MESH_IAB_DTN_INTERVAL),
    ),
}

#: The declared non-terrestrial degradation ladders per family:
#: PROPAGATION-AWARE DECLARED MARGIN STEPS (named rungs on the
#: accepted M008-owned REALIZING/DEGRADED/FAILED kernel — REALIZING
#: at the satisfying root, the explicit DEGRADED state on every
#: middle margin rung, the explicit FAILED terminal rung; every step
#: an evidence-visible deterministic transition through the accepted
#: ladder_step).
NON_TERRESTRIAL_LADDERS: Dict[str, DegradationLadder] = {
    "gso": DegradationLadder(
        technology_class=GSO_TECHNOLOGY_CLASS,
        modes=(
            DegradationMode("nominal", "REALIZING"),
            DegradationMode("margin-75", "DEGRADED"),
            DegradationMode("margin-50", "DEGRADED"),
            DegradationMode("margin-25", "DEGRADED"),
            DegradationMode("trunk-failed", "FAILED"),
        ),
    ),
    "ngso": DegradationLadder(
        technology_class=NGSO_TECHNOLOGY_CLASS,
        modes=(
            DegradationMode("nominal", "REALIZING"),
            DegradationMode("margin-75", "DEGRADED"),
            DegradationMode("margin-50", "DEGRADED"),
            DegradationMode("margin-25", "DEGRADED"),
            DegradationMode("pass-failed", "FAILED"),
        ),
    ),
    "leo": DegradationLadder(
        technology_class=LEO_TECHNOLOGY_CLASS,
        modes=(
            DegradationMode("nominal", "REALIZING"),
            DegradationMode("margin-75", "DEGRADED"),
            DegradationMode("margin-50", "DEGRADED"),
            DegradationMode("margin-25", "DEGRADED"),
            DegradationMode("pass-failed", "FAILED"),
        ),
    ),
    "mesh-iab": DegradationLadder(
        technology_class=MESH_IAB_TECHNOLOGY_CLASS,
        modes=(
            DegradationMode("nominal", "REALIZING"),
            DegradationMode("margin-75", "DEGRADED"),
            DegradationMode("margin-50", "DEGRADED"),
            DegradationMode("margin-25", "DEGRADED"),
            DegradationMode("mesh-failed", "FAILED"),
        ),
    ),
}

#: The declared handover kinds per satellite family (declared DATA —
#: the kinds are the M020 frozen four-kind vocabulary; the
#: characteristics are ALWAYS the accepted machinery's own frozen
#: semantics through :func:`declare_handover_kind`): every family
#: declares the intra-technology kind (the access-internal relay
#: reselection) and the cross-technology kind (the M024 interchange
#: drill); the NGSO and LEO families additionally declare the
#: ``pass`` kind (the NGSO/LEO pass-handover geometry — their
#: envelopes carry pass windows, the typed pass-consistency
#: discipline below); the single-window families (GSO, mesh/IAB)
#: declare NO pass kind.
NON_TERRESTRIAL_HANDOVER_KINDS: Dict[str, Tuple[str, ...]] = {
    "gso": ("intra-technology", "cross-technology"),
    "ngso": ("intra-technology", "cross-technology", "pass"),
    "leo": ("intra-technology", "cross-technology", "pass"),
    "mesh-iab": ("intra-technology", "cross-technology"),
}


# ----------------------------------------------------------------------
# The propagation-margin discipline (typed, fail-closed)
# ----------------------------------------------------------------------


def propagation_margin_ms(envelope: CapabilityEnvelope, service_budget_ms: int) -> int:
    """The NOMINAL propagation margin: the declared service latency
    budget over the envelope's declared propagation-delay ceiling
    (``budget_ms - latency.max_ms``), in integer milliseconds.

    Fail-closed (typed, never a warning): the inputs must be the
    accepted typed envelope and an integer budget; a budget that does
    not admit the envelope's declared propagation ceiling (margin
    below 1 ms) is the typed ENVELOPE_INCONSISTENT rejection — the
    declared budget and the declared propagation range are
    contradictory declarations, never silently accepted.
    """
    if not isinstance(envelope, CapabilityEnvelope):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "propagation_margin_ms requires a CapabilityEnvelope (got %s)"
            % type(envelope).__name__,
        )
    if isinstance(service_budget_ms, bool) or not isinstance(service_budget_ms, int):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "the service latency budget must be an integer number of "
            "milliseconds (canonical base units; floats are outside the "
            "canonical JSON subset)",
        )
    margin = service_budget_ms - envelope.latency.max_ms
    if margin < 1:
        raise AccessTechError(
            AccessTechReason.ENVELOPE_INCONSISTENT,
            "the declared service latency budget %d ms does not admit the "
            "envelope's declared propagation-delay ceiling %d ms for %s "
            "(margin %d ms < 1 ms — the budget and the declared "
            "propagation range are contradictory, never a warning)"
            % (
                service_budget_ms,
                envelope.latency.max_ms,
                envelope.technology_class,
                margin,
            ),
        )
    return margin


def require_propagation_margin_ladder(
    ladder: DegradationLadder,
    envelope: CapabilityEnvelope,
    *,
    service_budget_ms: int,
) -> None:
    """The propagation-aware margin-step ladder discipline (typed,
    fail-closed):

    * the nominal margin is positive (the budget admits the envelope's
      declared propagation ceiling —
      :func:`propagation_margin_ms` gates this);
    * every MIDDLE ladder rung is a declared margin step (the
      ``margin-<percent>`` grammar — a middle rung outside the margin
      grammar is not a propagation-aware declared step);
    * the declared margin fractions descend strictly (a deeper
      degradation step never claims MORE remaining margin);
    * every declared step's remaining margin still covers the
      propagation floor (the nominal margin times the fraction, in
      integer milliseconds, is at least 1 ms — a step that would drop
      below the floor is past the terminal, never a middle DEGRADED
      rung);
    * the terminal rung maps onto the explicit FAILED state (a
      realization that cannot satisfy the propagation budget enters
      the EXPLICIT failed state — frozen §9).
    """
    if not isinstance(ladder, DegradationLadder):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "require_propagation_margin_ladder requires a DegradationLadder "
            "(got %s)" % type(ladder).__name__,
        )
    nominal = propagation_margin_ms(envelope, service_budget_ms)
    modes = ladder.modes
    fractions: List[int] = []
    for position in range(1, len(modes) - 1):
        match = _MARGIN_RUNG_PATTERN.fullmatch(modes[position].name)
        if match is None:
            raise AccessTechError(
                AccessTechReason.LADDER_ILLEGAL,
                "ladder rung %r of %s is not a declared margin step (the "
                "propagation-aware middle rungs carry the "
                "'margin-<percent>' grammar)"
                % (modes[position].name, ladder.technology_class),
            )
        fraction = int(match.group(1))
        if fraction < 1 or fraction > 99:
            raise AccessTechError(
                AccessTechReason.LADDER_ILLEGAL,
                "ladder rung %r of %s declares a margin fraction outside "
                "1..99 (a 100%% step is the nominal root; a 0%% step is "
                "past the terminal)" % (modes[position].name, ladder.technology_class),
            )
        remaining = (nominal * fraction) // 100
        if remaining < 1:
            raise AccessTechError(
                AccessTechReason.LADDER_ILLEGAL,
                "ladder rung %r of %s drops below the propagation floor "
                "(nominal margin %d ms at %d%% leaves %d ms < 1 ms — a step "
                "past the floor is the terminal FAILED state, never a "
                "middle DEGRADED rung)"
                % (
                    modes[position].name,
                    ladder.technology_class,
                    nominal,
                    fraction,
                    remaining,
                ),
            )
        fractions.append(fraction)
    if not fractions:
        raise AccessTechError(
            AccessTechReason.LADDER_ILLEGAL,
            "the ladder of %s carries no declared margin steps (a "
            "propagation-aware ladder declares its middle rungs as margin "
            "steps)" % ladder.technology_class,
        )
    for position in range(len(fractions) - 1):
        if fractions[position] <= fractions[position + 1]:
            raise AccessTechError(
                AccessTechReason.LADDER_ILLEGAL,
                "the declared margin fractions of %s are not strictly "
                "descending (found %s — a deeper degradation step never "
                "claims MORE remaining margin)"
                % (ladder.technology_class, fractions),
            )
    if len(set(fractions)) != len(fractions):
        raise AccessTechError(
            AccessTechReason.LADDER_ILLEGAL,
            "the declared margin fractions of %s carry duplicates "
            "(contradictory declaration: %s)"
            % (ladder.technology_class, fractions),
        )
    if modes[-1].realization_state != "FAILED":
        raise AccessTechError(
            AccessTechReason.LADDER_ILLEGAL,
            "the terminal rung of %s maps onto %r — the satellite discipline "
            "enters the EXPLICIT FAILED state (a realization that cannot "
            "satisfy the propagation budget fails, never a silent open-ended "
            "degradation)" % (ladder.technology_class, modes[-1].realization_state),
        )


# ----------------------------------------------------------------------
# The pass-shape discipline (typed, fail-closed)
# ----------------------------------------------------------------------


def is_pass_shaped(envelope: CapabilityEnvelope) -> bool:
    """True iff the envelope's availability dimension declares MORE
    THAN ONE window — the non-terrestrial pass shape (successive
    coverage windows, pass transitions between them; a single-window
    declaration is the standing-service shape — no pass transitions
    exist)."""
    if not isinstance(envelope, CapabilityEnvelope):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "is_pass_shaped requires a CapabilityEnvelope (got %s)"
            % type(envelope).__name__,
        )
    return len(envelope.availability.windows) > 1


def require_pass_shaped_envelope(envelope: CapabilityEnvelope) -> None:
    """The typed pass-shape discipline: a family whose handover
    declarations carry the ``pass`` kind declares pass windows
    (MULTIPLE ordered availability windows — the pass geometry).
    A single-window envelope on a pass-kind family is the typed
    ENVELOPE_INCONSISTENT rejection (no pass transitions exist to
    hand over — fail closed, never a warning)."""
    if not isinstance(envelope, CapabilityEnvelope):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "require_pass_shaped_envelope requires a CapabilityEnvelope "
            "(got %s)" % type(envelope).__name__,
        )
    windows = envelope.availability.windows
    if len(windows) < 2:
        raise AccessTechError(
            AccessTechReason.ENVELOPE_INCONSISTENT,
            "the envelope for %s declares %d availability window(s) — pass "
            "geometry requires successive pass windows (MULTIPLE ordered "
            "declared windows; a single standing window carries no pass "
            "transitions to hand over)"
            % (envelope.technology_class, len(windows)),
        )


def require_handover_kinds_pass_consistent(
    kinds: Sequence[str], envelope: CapabilityEnvelope
) -> None:
    """The typed pass-kind/coverage-window consistency: a family
    declaring the ``pass`` handover kind carries a pass-shaped
    (multi-window) envelope; a single-window family never declares
    the pass kind (no pass transitions exist — the GSO standing window
    and the mesh/IAB DTN-bridged window carry no pass geometry).

    Fail-closed on both sides: an unknown kind is the typed
    VOCABULARY rejection (the accepted frozen four-kind vocabulary);
    a pass kind declared over a single-window envelope is the typed
    HANDOVER_ILLEGAL rejection (no pass transitions exist to hand
    over)."""
    if isinstance(kinds, (str, bytes)) or not isinstance(kinds, (tuple, list)):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "kinds must be a sequence of handover-kind names",
        )
    if not isinstance(envelope, CapabilityEnvelope):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "require_handover_kinds_pass_consistent requires a "
            "CapabilityEnvelope (got %s)" % type(envelope).__name__,
        )
    for kind in kinds:
        if kind not in HANDOVER_KINDS:
            raise AccessTechError(
                AccessTechReason.VOCABULARY,
                "handover kind %r is not in the declared kind vocabulary %s"
                % (kind, ", ".join(HANDOVER_KINDS)),
            )
    if "pass" in kinds:
        try:
            require_pass_shaped_envelope(envelope)
        except AccessTechError:
            raise AccessTechError(
                AccessTechReason.HANDOVER_ILLEGAL,
                "the handover kinds %s declare the 'pass' kind over the "
                "single-window envelope for %s — the pass-handover geometry "
                "requires successive pass windows (a standing window carries "
                "no pass transitions to hand over; fail closed)"
                % (list(kinds), envelope.technology_class),
            ) from None


# ----------------------------------------------------------------------
# The declared pass schedule (the NGSO/LEO pass-handover geometry)
# ----------------------------------------------------------------------


def derive_pass_schedule_id(
    family: str,
    windows: Sequence[AvailabilityWindow],
    serving_refs: Sequence[str],
) -> str:
    """The content-derived pass-schedule identity (LOCK-106
    discipline: sha256 over the canonical JSON of the declared
    geometry; no wall clock, no randomness)."""
    document = {
        "kind": "adcos.accesstech.pass-schedule",
        "family": family,
        "windows": [window.to_dict() for window in windows],
        "serving_refs": list(serving_refs),
    }
    payload = dict(document)
    payload["namespace"] = _PASS_SCHEDULE_NAMESPACE
    return "sha256:" + hashlib.sha256(
        _canonical_bytes(payload, "the declared pass schedule")
    ).hexdigest()


@dataclass(frozen=True)
class PassTransition:
    """One declared pass transition: the deterministic handover
    geometry between two ADJACENT declared passes — the OLD serving
    reference, the NEW serving reference, the old pass's end, the new
    pass's opening, and the RECONNECT INSTANT (the new pass's opening
    instant — when the explicit recorded reconnect lands through the
    accepted resilience/ handover machinery).

    DECLARED DATA ONLY: the references are opaque realization
    references (LOCK-117 — the machinery drives the actual handover;
    this record never becomes an event itself, never a contract
    authority, never a topology claim).
    """

    position: int
    old_ref: str
    new_ref: str
    from_pass_end: str
    to_pass_start: str
    reconnect_instant: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "position": self.position,
            "old_ref": self.old_ref,
            "new_ref": self.new_ref,
            "from_pass_end": self.from_pass_end,
            "to_pass_start": self.to_pass_start,
            "reconnect_instant": self.reconnect_instant,
        }


@dataclass(frozen=True)
class PassSchedule:
    """The DECLARED pass schedule of ONE pass-shaped family: the
    family's pass windows (exactly the envelope's own declared
    availability windows — the typed cross-check
    :func:`require_schedule_matches_envelope`) plus the serving
    reference of each pass, with a content-derived identity.

    Fail-closed declaration discipline (every malformed class a TYPED
    rejection, never a warning):

    * the family is a declared pass-shaped family (``ngso``/``leo``);
    * the schedule carries AT LEAST TWO pass windows (a one-window
      schedule declares no transitions — degenerate);
    * every entry is an accepted :class:`AvailabilityWindow` (typed
      at construction by the accepted surface — injected instants
      only, never wall clock);
    * the serving references are non-empty strings, one per window;
    * NO two CONSECUTIVE passes carry the same serving reference (a
      transition that changes nothing is not pass geometry — the
      typed contradictory-content rejection; the same satellite
      serving two NON-adjacent passes is real constellation geometry
      and stays declarable);
    * the identity is content-derived and tamper-evident at
      reconstruction (LOCK-106).
    """

    family: str
    windows: Tuple[AvailabilityWindow, ...]
    serving_refs: Tuple[str, ...]
    schedule_id: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.family, str) or self.family not in (
            PASS_SCHEDULE_FAMILIES
        ):
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "a declared pass schedule belongs to a pass-shaped family "
                "(declared: %s; found %r)"
                % (", ".join(PASS_SCHEDULE_FAMILIES), self.family),
            )
        if isinstance(self.windows, (str, bytes)) or not isinstance(
            self.windows, (tuple, list)
        ):
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "pass schedule windows must be a sequence of "
                "AvailabilityWindow records",
            )
        normalized: List[AvailabilityWindow] = []
        for index, item in enumerate(self.windows):
            if not isinstance(item, AvailabilityWindow):
                raise AccessTechError(
                    AccessTechReason.INVALID_INPUT,
                    "pass window %d must be an AvailabilityWindow record "
                    "(got %s — the accepted typed constructor validates the "
                    "injected instants)"
                    % (index, type(item).__name__),
                )
            normalized.append(item)
        windows = tuple(normalized)
        if len(windows) < 2:
            raise AccessTechError(
                AccessTechReason.ENVELOPE_DEGENERATE,
                "the declared pass schedule for %s carries %d window(s) — a "
                "pass schedule requires at least two passes (one pass "
                "declares no transitions)"
                % (self.family, len(windows)),
            )
        if isinstance(self.serving_refs, (str, bytes)) or not isinstance(
            self.serving_refs, (tuple, list)
        ):
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "pass schedule serving refs must be a sequence of strings",
            )
        refs: List[str] = []
        for index, item in enumerate(self.serving_refs):
            if not isinstance(item, str) or not item:
                raise AccessTechError(
                    AccessTechReason.INVALID_INPUT,
                    "serving reference %d must be a non-empty string (an "
                    "opaque realization reference)" % index,
                )
            refs.append(item)
        serving_refs = tuple(refs)
        if len(serving_refs) != len(windows):
            raise AccessTechError(
                AccessTechReason.ENVELOPE_INCONSISTENT,
                "the declared pass schedule for %s carries %d serving "
                "references over %d pass windows — exactly one serving "
                "reference per declared pass"
                % (self.family, len(serving_refs), len(windows)),
            )
        for position in range(len(serving_refs) - 1):
            if serving_refs[position] == serving_refs[position + 1]:
                raise AccessTechError(
                    AccessTechReason.ENVELOPE_INCONSISTENT,
                    "passes %d and %d of the %s schedule carry the same "
                    "serving reference %r — every pass transition changes "
                    "the serving reference (a transition that changes "
                    "nothing is not pass geometry)"
                    % (
                        position,
                        position + 1,
                        self.family,
                        serving_refs[position],
                    ),
                )
        object.__setattr__(self, "windows", windows)
        object.__setattr__(self, "serving_refs", serving_refs)
        derived = derive_pass_schedule_id(self.family, windows, serving_refs)
        if not isinstance(self.schedule_id, str) or not self.schedule_id:
            object.__setattr__(self, "schedule_id", derived)
        elif self.schedule_id != derived:
            raise AccessTechError(
                AccessTechReason.IDENTITY_MISMATCH,
                "schedule_id does not match the content-derived identity "
                "(tamper evidence): declared %s, derived %s"
                % (self.schedule_id, derived),
            )

    def content_dict(self) -> Dict[str, Any]:
        return {
            "family": self.family,
            "windows": [window.to_dict() for window in self.windows],
            "serving_refs": list(self.serving_refs),
            "schedule_id": self.schedule_id,
        }

    def to_dict(self) -> Dict[str, Any]:
        return self.content_dict()

    def to_canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.content_dict(), "the declared pass schedule")

    def pass_count(self) -> int:
        """The number of declared passes (the window count)."""
        return len(self.windows)

    def pass_transitions(self) -> Tuple[PassTransition, ...]:
        """The deterministic declared transition sequence: one
        :class:`PassTransition` per ADJACENT pass pair (the geometry
        the composition drives through the accepted resilience/
        handover machinery — every transition an explicit recorded
        reconnect naming the OLD and the NEW serving references)."""
        transitions: List[PassTransition] = []
        for position in range(len(self.windows) - 1):
            current = self.windows[position]
            following = self.windows[position + 1]
            transitions.append(
                PassTransition(
                    position=position,
                    old_ref=self.serving_refs[position],
                    new_ref=self.serving_refs[position + 1],
                    from_pass_end=current.end,
                    to_pass_start=following.start,
                    reconnect_instant=following.start,
                )
            )
        return tuple(transitions)


def pass_schedule_from_mapping(value: object) -> PassSchedule:
    """Reconstruct a :class:`PassSchedule` from its canonical mapping
    (fail-closed on grammar drift and on identity tampering — the
    content-derived schedule id is recomputed and compared at load)."""
    if not isinstance(value, Mapping):
        raise AccessTechError(
            AccessTechReason.SERIALIZATION_INVALID,
            "the declared pass schedule must be a mapping",
        )
    data = dict(value)
    schedule_id = data.get("schedule_id")
    if not isinstance(schedule_id, str) or not schedule_id:
        raise AccessTechError(
            AccessTechReason.SERIALIZATION_INVALID,
            "the declared pass schedule lacks its content-derived "
            "schedule_id",
        )
    for member in ("family", "windows", "serving_refs"):
        if member not in data:
            raise AccessTechError(
                AccessTechReason.SERIALIZATION_INVALID,
                "the declared pass schedule lacks the %r member" % member,
            )
    windows_raw = data["windows"]
    if isinstance(windows_raw, (str, bytes)) or not isinstance(
        windows_raw, (tuple, list)
    ):
        raise AccessTechError(
            AccessTechReason.SERIALIZATION_INVALID,
            "pass schedule windows must be a sequence of window mappings",
        )
    windows: List[AvailabilityWindow] = []
    for item in windows_raw:
        if not isinstance(item, Mapping):
            raise AccessTechError(
                AccessTechReason.SERIALIZATION_INVALID,
                "each pass window must be a mapping",
            )
        window_data = dict(item)
        for member in ("start", "end"):
            if member not in window_data:
                raise AccessTechError(
                    AccessTechReason.SERIALIZATION_INVALID,
                    "a pass window lacks the %r member" % member,
                )
        windows.append(
            AvailabilityWindow(window_data["start"], window_data["end"])
        )
    serving_raw = data["serving_refs"]
    if isinstance(serving_raw, (str, bytes)) or not isinstance(
        serving_raw, (tuple, list)
    ):
        raise AccessTechError(
            AccessTechReason.SERIALIZATION_INVALID,
            "pass schedule serving refs must be a sequence of strings",
        )
    return PassSchedule(
        family=data["family"],
        windows=tuple(windows),
        serving_refs=tuple(serving_raw),
        schedule_id=schedule_id,
    )


def require_schedule_matches_envelope(
    schedule: PassSchedule, envelope: CapabilityEnvelope
) -> None:
    """The typed schedule/envelope cross-check: the schedule's
    declared pass windows ARE the family envelope's declared
    availability windows (verbatim — the envelope owns the coverage
    declaration; the schedule adds only the serving geometry), and
    the envelope is pass-shaped."""
    if not isinstance(schedule, PassSchedule):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "require_schedule_matches_envelope requires a PassSchedule "
            "(got %s)" % type(schedule).__name__,
        )
    if not isinstance(envelope, CapabilityEnvelope):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "require_schedule_matches_envelope requires a "
            "CapabilityEnvelope (got %s)" % type(envelope).__name__,
        )
    require_pass_shaped_envelope(envelope)
    schedule_windows = tuple(
        (window.start, window.end) for window in schedule.windows
    )
    envelope_windows = tuple(
        (window.start, window.end) for window in envelope.availability.windows
    )
    if schedule_windows != envelope_windows:
        raise AccessTechError(
            AccessTechReason.ENVELOPE_INCONSISTENT,
            "the declared pass schedule for %s does not carry the envelope's "
            "own declared pass windows (the envelope owns the coverage "
            "declaration; the schedule adds only the serving geometry — "
            "schedule %s vs envelope %s)"
            % (schedule.family, schedule_windows, envelope_windows),
        )


def declared_pass_schedule(family: str) -> PassSchedule:
    """The module's own declared pass schedule for one pass-shaped
    family (built from the family envelope's own declared windows —
    the module's schedules and envelopes are consistent by
    construction; the battery re-verifies through
    :func:`require_schedule_matches_envelope`)."""
    if family not in PASS_SCHEDULE_FAMILIES:
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "family %r is not a declared pass-shaped family (declared: %s)"
            % (family, ", ".join(PASS_SCHEDULE_FAMILIES)),
        )
    return PassSchedule(
        family=family,
        windows=NON_TERRESTRIAL_ENVELOPES[family].availability.windows,
        serving_refs=(
            NGSO_SERVING_REFS if family == "ngso" else LEO_SERVING_REFS
        ),
    )


#: The declared NGSO pass schedule (four passes, three transitions —
#: the NGSO pass-handover geometry the battery drives through the
#: accepted resilience/ handover machinery).
NGSO_PASS_SCHEDULE: PassSchedule = PassSchedule(
    family="ngso",
    windows=_windows(NGSO_PASS_WINDOWS),
    serving_refs=NGSO_SERVING_REFS,
)

#: The declared LEO pass schedule (six passes, five transitions).
LEO_PASS_SCHEDULE: PassSchedule = PassSchedule(
    family="leo",
    windows=_windows(LEO_PASS_WINDOWS),
    serving_refs=LEO_SERVING_REFS,
)


def non_terrestrial_handover_declarations(
    family: str,
) -> Tuple[HandoverCharacteristics, ...]:
    """The handover declarations of ONE non-terrestrial family, built
    ONLY through the accepted :func:`~accesstech.handovers.
    declare_handover_kind` constructor (the machinery's own frozen
    semantics: the FULL imported constraint-kind preservation set,
    the mandatory explicit-reconnect discipline, the mandatory
    contract-continuity discipline — never weakened, never
    re-typed).  The declared kinds are pass-consistent with the
    family's envelope (the typed cross-check above — the NGSO/LEO
    families carry the ``pass`` kind over pass windows; the GSO and
    mesh/IAB standing windows declare no pass kind)."""
    if family not in NON_TERRESTRIAL_HANDOVER_KINDS:
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "family %r is not a declared non-terrestrial family (declared: "
            "%s)" % (family, ", ".join(NON_TERRESTRIAL_FAMILIES)),
        )
    kinds = NON_TERRESTRIAL_HANDOVER_KINDS[family]
    require_handover_kinds_pass_consistent(
        kinds, NON_TERRESTRIAL_ENVELOPES[family]
    )
    return tuple(declare_handover_kind(kind) for kind in kinds)
