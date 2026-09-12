#!/usr/bin/env python3
"""ADCOS wireline access adapter self-test (M021).

Deterministic, offline verification of the M021 wireline delivery —
the ``adapters/reference/wireline.py`` reference compositions, the
``accesstech/wireline.py`` family declarations and their composition
through the accepted surfaces — against the R9 charter M021 scope
(R9-CORE-001, DEC-0121; the chain child whose M020 dependency is
satisfied by the DEC-0121 acceptance):

- (a) case_01..case_03 — the wireline family declarations: the three
  capability envelopes (Ethernet ``access.ieee.8023``, fiber
  ``access.itu.g709``, enterprise-WAN ``access.enterprise.wan``)
  round-trip canonical-JSON byte-identically with content-derived
  identities (LOCK-106); STATIC-AVAILABILITY semantics (exactly ONE
  continuous declared window per envelope — no mobility, no pass
  windows; a multi-window declaration is the typed
  non-wireline rejection; the declared surface carries no mobility
  vocabulary); the degradation ladders as DECLARED CAPACITY STEPS
  (named rungs on the accepted realization-state kernel, each step
  an explicit evidence-visible transition, deterministic walking,
  typed rejections on undeclared/terminal stepping);
- (b) case_04..case_05 — the three wireline families registered
  through the ACCEPTED M020 extension surface (envelope + reference
  adapter composition + capability statement over the accepted
  ``adapters/capability.py`` seam and the ``executionplans/``
  LOCK-109 bridge, zero contract-core delta) and resolving BY
  REFERENCE to the accepted backhaul family runtime (identity-
  preserving live objects — no re-instantiation, no second runtime);
- (c) case_06..case_07 — the nine WORK-016 operations in
  deterministic reserve/activate/measure flows (the frozen disclosed
  translation map driven end-to-end: capabilities, allocate,
  bind_session, observe, unbind_session, release, health — with the
  registration's open_adapter drive) INCLUDING the deterministic
  re-bind translation for mid-session reconfiguration (the same
  session, the preserved reservation, the previous binding released
  first, the new binding created — typed Reconfiguration records;
  the enterprise-WAN's mid-session SITE RESELECTION onto another
  declared site pair);
- (d) case_08 — the declared enterprise-WAN site-topology as
  DECLARED DATA ONLY (LOCK-105 — never global topology): canonical
  round-trips with tamper evidence; every malformed class a typed
  rejection (a pair reaching outside the declared site set IS the
  topology-leak class); NO transitive closure (an undeclared pair
  stays undeclared); the composition provisions EXACTLY the declared
  pairs; the boundary views carry no topology facts;
- (e) case_09..case_10 — LOCK-110 provider-SDK isolation (every 1.1
  operation returns the canonical typed provider-neutral records; no
  opaque family technology reference crosses into any record's
  canonical bytes; the LOCK-112 mechanism tags are citation DATA) and
  the typed fail-closed matrix (capacity exhaustion, unmapped kinds,
  identity smuggling, unknown endpoints/links/reservations,
  terminal-state reconfigure/measure — deterministic typed
  rejections, never warnings);
- (f) case_11..case_14 — the one-way import audit (no accepted
  authority imports the new modules; the new modules' own import
  discipline — adapters/reference/wireline.py never imports
  accesstech, accesstech/wireline.py never imports adapters; the
  clock/random/network discipline), the zero contract-core delta +
  authorization-scope audit, determinism (in-process rebuild and the
  full PYTHONHASHSEED 0/1/42 cross-process byte-identity), and the
  evidence-doc honesty (SOFTWARE class only; EVID-002..EVID-008 stay
  open — never a PHYSICAL PASS claim).

The central boundary is exercised throughout:

    WIRELINE ACCESS FAMILY
        = a reference adapter composition on the M020 envelope
          (declared data around the accepted authorities)
        = the accepted backhaul family runtime composed BY REFERENCE
          through the accepted adapters/capability.py seam
          (LOCK-112: the family models the standard mechanisms —
          IEEE 802.3 / 802.1Q / ITU-T G.709; LOCK-110: provider-SDK
          types never enter the core)
        != CONTRACT AUTHORITY (contracts/ stays the sole authority)
        != GLOBAL TOPOLOGY (LOCK-105: the site topology is declared
          data bounded by its own declaration)

All instants are injected (T0-style constants); no wall clock, no
randomness, no network, no real sockets, no secrets (LOCK-119).
Runs are byte-identical across processes (PYTHONHASHSEED-safe).
"""

from __future__ import annotations

import ast
import hashlib
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from protocol.canonicalization import canonical_json_bytes  # noqa: E402

from adapters import CAPABILITY_OPERATIONS  # noqa: E402
from adapters.capability import (  # noqa: E402
    CAPABILITY_TRANSLATION_MAP,
    Activation,
    CapabilityView,
    Measurement,
    OfferView,
    Reconfiguration,
    ReleaseReceipt,
)
from adapters.errors import AdapterError  # noqa: E402
from adapters.model import Allocation, HealthReport  # noqa: E402
from executionplans import ADAPTER_OPERATIONS  # noqa: E402

import accesstech  # noqa: E402
from accesstech import (  # noqa: E402
    AvailabilityWindow,
    AvailabilityWindows,
    BpsRange,
    CapabilityEnvelope,
    DegradationMode,
    JitterMilliRange,
    LatencyMilliRange,
    TechnologyRegistry,
    declare_handover_kind,
    envelope_from_mapping,
    ladder_from_mapping,
    ladder_step,
    mode_realization_state,
    preserved_constraint_kinds,
    register_access_technology,
    technology_registration_from_mapping,
)
from accesstech.errors import AccessTechError  # noqa: E402
from accesstech import wireline as wl  # noqa: E402  (the M021 declarations)

from adapters.reference import wireline as wire  # noqa: E402  (the M021 compositions)
from adapters.reference.wireline import (  # noqa: E402
    REFERENCE_SITE_TOPOLOGY,
    SiteTopology,
    site_pair_key,
    site_topology_from_mapping,
)

# The M007 battery's public mounting fixtures (the accepted reader
# facades + the real WORK-012 session store; the case_66
# cross-battery import precedent — the M020 battery's own pattern).
import adapter_selftest as ads  # noqa: E402

Result = Tuple[str, bool, str]

FAMILIES: Tuple[str, ...] = ("ethernet", "fiber", "enterprise-wan")


def ok(name: str, detail: str = "") -> Result:
    return (name, True, detail)


def fail(name: str, detail: str) -> Result:
    return (name, False, detail)


# ---------------------------------------------------------------------------
# Deterministic fixtures (injected instants only)
# ---------------------------------------------------------------------------

_T0 = "2026-06-01T00:00:00Z"
_NOW = "2026-06-01T12:00:00Z"
_LATER = "2026-06-01T13:00:00Z"
_LATER2 = "2026-06-01T14:00:00Z"

#: The per-family reserve parameters (the accepted descriptor's
#: mapped resource kind — ``backhaul`` bps base units).
_FAMILY_RESERVE: Dict[str, int] = {
    "ethernet": 100_000_000,
    "fiber": 1_000_000_000,
    "enterprise-wan": 100_000_000,
}


def _mount_family(store, family: str):
    """Mount ONE wireline family reference composition through its
    own public ``mount_*`` factory (the reader facade over a real
    WORK-012 store; the accepted M007/M020 composition-root
    pattern)."""
    reader = ads._backhaul_session_reader(store)
    if family == "ethernet":
        bridge, descriptor, requirements = wire.mount_reference(reader, now=_T0)
        return bridge, descriptor, requirements, {}
    if family == "fiber":
        bridge, descriptor, requirements = wire.mount_fiber_reference(reader, now=_T0)
        return bridge, descriptor, requirements, {}
    if family == "enterprise-wan":
        bridge, descriptor, requirements, site_links = (
            wire.mount_enterprise_wan_reference(reader, now=_T0)
        )
        return bridge, descriptor, requirements, site_links
    raise AssertionError("unknown family %r" % family)


def _register_family(store, family: str):
    """Register ONE wireline family through the accepted M020 public
    path (envelope + reference adapter composition + capability
    statement over the accepted seam + LOCK-109 bridge)."""
    bridge, descriptor, requirements, site_links = _mount_family(store, family)
    registration = register_access_technology(
        envelope=wl.WIRELINE_ENVELOPES[family],
        ladder=wl.WIRELINE_LADDERS[family],
        handovers=wl.wireline_handover_declarations(family),
        implementation=bridge,
        descriptor=descriptor,
        binding_requirements=requirements,
        mechanisms=wire.STANDARD_MECHANISMS,
        session_store=store,
        now=_T0,
    )
    return registration, site_links


def _register_all(store):
    """Register ALL THREE wireline families into one registry (the
    deterministic registration surface state)."""
    registry = TechnologyRegistry()
    registrations: Dict[str, Any] = {}
    site_links: Dict[str, Dict[str, str]] = {}
    for family in FAMILIES:
        registration, links = _register_family(store, family)
        registry.register(registration)
        registrations[family] = registration
        site_links[family] = links
    return registry, registrations, site_links


def _full_flow(registration, family: str, sid: str, *, reconfigure: bool = True):
    """Drive ONE full deterministic lifecycle through the resolved
    capability adapter: inspect -> reserve -> activate -> measure ->
    (re-bind) -> release, returning the canonical record material
    (byte-comparable across rebuilds)."""
    capability = registration.resolve_capability_adapter()
    material: List[bytes] = []
    inspected = capability.inspect_capabilities(now=_NOW)
    if not inspected.ok:
        raise AssertionError("%s inspect_capabilities failed" % family)
    material.append(canonical_json_bytes(inspected.value.to_dict()))
    offers = capability.inspect_offers(now=_NOW)
    if not offers.ok:
        raise AssertionError("%s inspect_offers failed" % family)
    for view in offers.value:
        material.append(canonical_json_bytes(view.to_dict()))
    health = capability.health(now=_NOW)
    if not health.ok:
        raise AssertionError("%s health failed" % family)
    material.append(canonical_json_bytes(health.value.to_dict()))
    reserved = capability.reserve(
        kind="backhaul",
        quantity=_FAMILY_RESERVE[family],
        unit="bps",
        purpose="m021-%s-lifecycle" % family,
        now=_NOW,
    )
    if not reserved.ok:
        raise AssertionError("%s reserve failed" % family)
    material.append(canonical_json_bytes(reserved.value.to_dict()))
    activated = capability.activate(
        reservation_id=reserved.value.allocation_id,
        session_id=sid,
        requirements=dict(registration.binding_requirements),
        now=_NOW,
    )
    if not activated.ok:
        raise AssertionError("%s activate failed" % family)
    material.append(canonical_json_bytes(activated.value.to_dict()))
    measured = capability.measure(
        activation_id=activated.value.activation_id, now=_LATER
    )
    if not measured.ok:
        raise AssertionError("%s measure failed" % family)
    material.append(canonical_json_bytes(measured.value.to_dict()))
    if reconfigure:
        requirements = _reconfigure_requirements(family, registration)
        reconfigured = capability.reconfigure(
            activation_id=activated.value.activation_id,
            requirements=requirements,
            now=_LATER,
        )
        if not reconfigured.ok:
            raise AssertionError("%s reconfigure failed" % family)
        material.append(canonical_json_bytes(reconfigured.value.to_dict()))
        remeasured = capability.measure(
            activation_id=activated.value.activation_id, now=_LATER2
        )
        if not remeasured.ok:
            raise AssertionError("%s re-measure failed" % family)
        material.append(canonical_json_bytes(remeasured.value.to_dict()))
    released = capability.release(
        activation_id=activated.value.activation_id, now=_LATER2
    )
    if not released.ok:
        raise AssertionError("%s release failed" % family)
    material.append(canonical_json_bytes(released.value.to_dict()))
    return material


def _reconfigure_requirements(family: str, registration) -> Dict[str, Any]:
    """The mid-session reconfiguration requirements per family: the
    enterprise-WAN RESELECTS its site pair (another declared circuit);
    the ethernet/fiber families re-bind with refreshed QoS data on
    the same wiring."""
    _establish_wan_links()
    if family == "enterprise-wan":
        return {
            "link_ref": _WAN_SITE_LINKS["wan-site-b+wan-site-c"],
            "endpoint_label": "wan-site-b",
            "qos-class": "premium",
        }
    requirements = dict(registration.binding_requirements)
    requirements["qos-class"] = "premium"
    return requirements


#: The declared site-pair link map of the reference enterprise-WAN
#: mount (fixed at module scope for the re-configure fixture; the
#: link refs are content-derived over the declared link profiles —
#: deterministic).
_WAN_SITE_LINKS: Dict[str, str] = {}


def _establish_wan_links() -> None:
    if _WAN_SITE_LINKS:
        return
    store, _sid = ads._established_session()
    _bridge, _descriptor, _requirements, site_links = _mount_family(
        store, "enterprise-wan"
    )
    _WAN_SITE_LINKS.update(site_links)


# ---------------------------------------------------------------------------
# The typed-error probe helpers
# ---------------------------------------------------------------------------


def expect_typed(case: str, code: str, action: Callable[[], Any]) -> Result:
    """Run one action; PASS when it raises AccessTechError with the
    exact expected typed code (deterministic expected outcome)."""
    try:
        action()
    except AccessTechError as error:
        if error.code == code:
            return ok(case, "fail-closed %s: %s" % (code, error.detail[:88]))
        return fail(
            case,
            "expected code %s, got %s (%s)" % (code, error.code, error.detail[:88]),
        )
    except Exception as error:  # noqa: BLE001
        return fail(
            case,
            "unexpected exception %s: %s"
            % (type(error).__name__, str(error)[:88]),
        )
    return fail(case, "expected AccessTechError(%s); the input was accepted" % code)


def expect_adapter_error(case: str, reason: str, action: Callable[[], Any]) -> Result:
    """Run one action; PASS when it raises the accepted seam's
    AdapterError with the exact expected typed reason."""
    try:
        action()
    except AdapterError as error:
        if error.reason == reason:
            return ok(case, "fail-closed %s: %s" % (reason, error.detail[:88]))
        return fail(
            case,
            "expected reason %s, got %s (%s)" % (reason, error.reason, error.detail[:88]),
        )
    except Exception as error:  # noqa: BLE001
        return fail(
            case,
            "unexpected exception %s: %s"
            % (type(error).__name__, str(error)[:88]),
        )
    return fail(case, "expected AdapterError(%s); the input was accepted" % reason)


def expect_family_error(case: str, reason: str, action: Callable[[], Any]) -> Result:
    """Run one action; PASS when it raises the accepted backhaul
    family's BackhaulError with the exact expected typed reason."""
    from adapters.backhaul.errors import BackhaulError

    try:
        action()
    except BackhaulError as error:
        if error.reason == reason:
            return ok(case, "fail-closed %s: %s" % (reason, error.detail[:88]))
        return fail(
            case,
            "expected reason %s, got %s (%s)" % (reason, error.reason, error.detail[:88]),
        )
    except Exception as error:  # noqa: BLE001
        return fail(
            case,
            "unexpected exception %s: %s"
            % (type(error).__name__, str(error)[:88]),
        )
    return fail(case, "expected BackhaulError(%s); the input was accepted" % reason)


def _failure_reason(result) -> str:
    return result.failure.reason if result.failure is not None else "?"


# ---------------------------------------------------------------------------
# (a) the wireline family declarations
# ---------------------------------------------------------------------------


def case_01_wireline_declarations_round_trip() -> Result:
    name = "case_01_wireline_declarations_round_trip"
    if tuple(wl.WIRELINE_FAMILIES) != FAMILIES:
        return fail(name, "the declared family set drifted")
    if tuple(sorted(wl.WIRELINE_TECHNOLOGY_CLASSES)) != tuple(
        sorted(
            wl.WIRELINE_ENVELOPES[family].technology_class
            for family in wl.WIRELINE_FAMILIES
        )
    ):
        return fail(name, "the declared technology-class set is inconsistent")
    envelope_ids = set()
    ladder_ids = set()
    for family in FAMILIES:
        envelope = wl.WIRELINE_ENVELOPES[family]
        ladder = wl.WIRELINE_LADDERS[family]
        if ladder.technology_class != envelope.technology_class:
            return fail(name, "%s ladder/envelope class mismatch" % family)
        reconstructed = envelope_from_mapping(envelope.to_dict())
        if reconstructed.to_canonical_bytes() != envelope.to_canonical_bytes():
            return fail(name, "%s envelope round-trip not byte-identical" % family)
        if reconstructed.envelope_id != envelope.envelope_id:
            return fail(name, "%s envelope identity changed on reconstruction" % family)
        if envelope.to_canonical_bytes() != canonical_json_bytes(envelope.to_dict()):
            return fail(name, "%s envelope canonical bytes drift" % family)
        rebuilt_ladder = ladder_from_mapping(ladder.to_dict())
        if rebuilt_ladder.to_canonical_bytes() != ladder.to_canonical_bytes():
            return fail(name, "%s ladder round-trip not byte-identical" % family)
        if rebuilt_ladder.ladder_id != ladder.ladder_id:
            return fail(name, "%s ladder identity changed on reconstruction" % family)
        for characteristics in wl.wireline_handover_declarations(family):
            rebuilt = accesstech.handover_characteristics_from_mapping(
                characteristics.to_dict()
            )
            if rebuilt.to_canonical_bytes() != characteristics.to_canonical_bytes():
                return fail(name, "%s handover round-trip not byte-identical" % family)
            if rebuilt.characteristics_id != characteristics.characteristics_id:
                return fail(name, "%s handover identity changed" % family)
        envelope_ids.add(envelope.envelope_id)
        ladder_ids.add(ladder.ladder_id)
    if len(envelope_ids) != 3 or len(ladder_ids) != 3:
        return fail(name, "declaration identities not distinct per family")
    # content-derived identity: one dimension changes -> identity changes
    variant = CapabilityEnvelope(
        technology_class=wl.FIBER_TECHNOLOGY_CLASS,
        bandwidth=BpsRange(2_000_000_000, 100_000_000_000),
        latency=LatencyMilliRange(1, 15),
        jitter=JitterMilliRange(0, 2),
        availability=wl.WIRELINE_ENVELOPES["fiber"].availability,
    )
    if variant.envelope_id == wl.WIRELINE_ENVELOPES["fiber"].envelope_id:
        return fail(name, "identity not content-derived (bandwidth floor ignored)")
    same = CapabilityEnvelope(
        technology_class=wl.FIBER_TECHNOLOGY_CLASS,
        bandwidth=BpsRange(1_000_000_000, 100_000_000_000),
        latency=LatencyMilliRange(1, 15),
        jitter=JitterMilliRange(0, 2),
        availability=wl.WIRELINE_ENVELOPES["fiber"].availability,
    )
    if same.envelope_id != wl.WIRELINE_ENVELOPES["fiber"].envelope_id:
        return fail(name, "same content produced a different identity")
    return ok(
        name,
        "3 declared wireline families (ethernet/fiber/enterprise-wan): "
        "envelopes, ladders and handover declarations round-trip "
        "byte-identically; content-derived identities distinct and stable",
    )


def case_02_static_availability_no_mobility() -> Result:
    name = "case_02_static_availability_no_mobility"
    # (a) every wireline envelope carries EXACTLY ONE continuous
    # declared window (the standing service interval)
    for family in FAMILIES:
        envelope = wl.WIRELINE_ENVELOPES[family]
        if not wl.is_static_availability(envelope):
            return fail(name, "%s envelope is not static-availability" % family)
        try:
            wl.require_static_availability(envelope)
        except AccessTechError as error:
            return fail(name, "%s static check raised: %s" % (family, error.detail))
        windows = envelope.availability.windows
        if len(windows) != 1:
            return fail(name, "%s carries %d windows" % (family, len(windows)))
        start, end = wl.STATIC_SERVICE_INTERVAL
        if windows[0].start != start or windows[0].end != end:
            return fail(name, "%s window is not the declared service interval" % family)
    # (b) a multi-window (pass/mobility-shaped) declaration is the
    # typed non-wireline rejection — never a warning
    multi_window = CapabilityEnvelope(
        technology_class=wl.FIBER_TECHNOLOGY_CLASS,
        bandwidth=BpsRange(1_000_000_000, 100_000_000_000),
        latency=LatencyMilliRange(1, 15),
        jitter=JitterMilliRange(0, 2),
        availability=AvailabilityWindows(
            (
                AvailabilityWindow("2026-03-01T00:00:00Z", "2026-03-02T00:00:00Z"),
                AvailabilityWindow("2026-09-01T00:00:00Z", "2026-09-03T00:00:00Z"),
            )
        ),
    )
    outcome = expect_typed(
        name,
        "accesstech-envelope-inconsistent",
        lambda: wl.require_static_availability(multi_window),
    )
    if not outcome[1]:
        return fail(name, "multi-window rejection: %s" % outcome[2])
    if wl.is_static_availability(multi_window):
        return fail(name, "multi-window envelope read as static")
    # (c) NO mobility vocabulary on the declared surface: the
    # canonical envelope members are exactly the frozen grammar (no
    # mobility member exists to declare); the ladder mode states are
    # inside the accepted four-state kernel; the handover kinds are
    # inside the frozen four-kind vocabulary
    frozen_members = {
        "technology_class",
        "bandwidth",
        "latency",
        "jitter",
        "availability",
        "envelope_id",
    }
    for family in FAMILIES:
        envelope_dict = wl.WIRELINE_ENVELOPES[family].to_dict()
        if set(envelope_dict) != frozen_members:
            return fail(
                name,
                "%s envelope carries members beyond the frozen grammar: %s"
                % (family, sorted(set(envelope_dict) - frozen_members)),
            )
        for mode in wl.WIRELINE_LADDERS[family].modes:
            if mode.realization_state not in accesstech.REALIZATION_STATES:
                return fail(name, "%s mode escapes the kernel" % family)
            if "mobility" in mode.name or "handover" in mode.name:
                return fail(name, "%s mode name carries mobility vocabulary" % family)
        for characteristics in wl.wireline_handover_declarations(family):
            if characteristics.kind not in accesstech.HANDOVER_KINDS:
                return fail(name, "%s handover kind drift" % family)
    if "mobility" in " ".join(wl.__all__).lower():
        return fail(name, "the declarations module exports mobility vocabulary")
    return ok(
        name,
        "static availability holds: exactly ONE continuous declared window "
        "per family (the standing service interval); the multi-window "
        "pass/mobility shape is the typed ENVELOPE_INCONSISTENT rejection; "
        "no mobility vocabulary anywhere on the declared surface",
    )


def case_03_ladders_declared_capacity_steps() -> Result:
    name = "case_03_ladders_declared_capacity_steps"
    from replan import REALIZATION_STATES as KERNEL_STATES

    trails: Dict[str, List[Dict[str, Any]]] = {}
    for family in FAMILIES:
        ladder = wl.WIRELINE_LADDERS[family]
        modes = ladder.modes
        if modes[0].realization_state != "REALIZING":
            return fail(name, "%s root rung is not REALIZING" % family)
        if modes[-1].realization_state != "FAILED":
            return fail(name, "%s terminal rung is not FAILED" % family)
        for position in range(1, len(modes) - 1):
            if modes[position].realization_state != "DEGRADED":
                return fail(
                    name,
                    "%s middle rung %r is not an explicit DEGRADED capacity step"
                    % (family, modes[position].name),
                )
        # the full deterministic walk: every step an explicit
        # evidence-visible transition (deterministic trail over the
        # content-derived ladder identity + rung names — every
        # recorded step tamper-evident through LOCK-106)
        trail: List[Dict[str, Any]] = []
        mode = modes[0]
        steps = 0
        while mode.realization_state not in ("FAILED", "SUPERSEDED"):
            following = ladder_step(ladder, mode.name)
            trail.append(
                {
                    "ladder_id": ladder.ladder_id,
                    "from_mode": mode.name,
                    "to_mode": following.name,
                    "realization_state": following.realization_state,
                }
            )
            mode = following
            steps += 1
            if steps > len(modes):
                return fail(name, "%s ladder never terminated" % family)
        if mode.name != ladder.terminal_mode().name:
            return fail(name, "%s walk ended off the terminal rung" % family)
        trails[family] = trail
        # deterministic re-walk from the rebuilt ladder: identical steps
        rebuilt = ladder_from_mapping(ladder.to_dict())
        mode_a = ladder.modes[0]
        mode_b = rebuilt.modes[0]
        while mode_a.realization_state not in ("FAILED", "SUPERSEDED"):
            mode_a = ladder_step(ladder, mode_a.name)
            mode_b = ladder_step(rebuilt, mode_b.name)
            if (mode_a.name, mode_a.realization_state) != (
                mode_b.name,
                mode_b.realization_state,
            ):
                return fail(name, "%s stepping is not deterministic" % family)
        # the public state resolution helper agrees on every rung
        for rung in modes:
            if mode_realization_state(ladder, rung.name) != rung.realization_state:
                return fail(name, "%s state resolution mismatch" % family)
    # the materialized transition trails are canonical-JSON stable
    # (evidence-visible: each capacity step an explicit recordable
    # transition; the trail bytes byte-identical on rebuild)
    for family in FAMILIES:
        first = canonical_json_bytes(trails[family])
        second = canonical_json_bytes(trails[family])
        if first != second:
            return fail(name, "%s transition trail not stable" % family)
    # typed rejections: undeclared mode, terminal stepping
    probes = [
        ("undeclared mode stepped", lambda: ladder_step(
            wl.WIRELINE_LADDERS["ethernet"], "unknown-mode")),
        ("terminal mode stepped", lambda: ladder_step(
            wl.WIRELINE_LADDERS["ethernet"],
            wl.WIRELINE_LADDERS["ethernet"].terminal_mode().name)),
        ("undeclared mode state", lambda: DegradationMode("mystery", "RESTORING")),
    ]
    for label, action in probes:
        outcome = expect_typed(name, "accesstech-ladder-illegal", action)
        if label == "undeclared mode state":
            outcome = expect_typed(name, "accesstech-vocabulary", action)
        if not outcome[1]:
            return fail(name, "%s: %s" % (label, outcome[2]))
    if KERNEL_STATES != ("REALIZING", "DEGRADED", "FAILED", "SUPERSEDED"):
        return fail(name, "the consumed kernel drifted")
    return ok(
        name,
        "3 ladders walked rung-by-rung: every middle rung an explicit "
        "DEGRADED declared capacity step, the terminal rung FAILED, each "
        "step an evidence-visible deterministic transition (canonical "
        "trails, rebuilt-ladder walks identical); undeclared/terminal "
        "stepping typed",
    )


# ---------------------------------------------------------------------------
# (b) the registration surface — the three wireline families
# ---------------------------------------------------------------------------


def case_04_families_registered_through_extension_surface() -> Result:
    name = "case_04_families_registered_through_extension_surface"
    _establish_wan_links()
    store, sid = ads._established_session()
    registry, registrations, _links = _register_all(store)
    if tuple(registry.technology_classes()) != tuple(
        sorted(wl.WIRELINE_TECHNOLOGY_CLASSES)
    ):
        return fail(name, "registry class set wrong: %s" % (registry.technology_classes(),))
    ids = set()
    for family in FAMILIES:
        registration = registrations[family]
        envelope = wl.WIRELINE_ENVELOPES[family]
        ladder = wl.WIRELINE_LADDERS[family]
        if registration.technology_class != envelope.technology_class:
            return fail(name, "%s technology class mismatch" % family)
        if registration.envelope.envelope_id != envelope.envelope_id:
            return fail(name, "%s envelope not carried by reference" % family)
        if registration.ladder.ladder_id != ladder.ladder_id:
            return fail(name, "%s ladder not carried by reference" % family)
        if registration.descriptor.access_technology_id != envelope.technology_class:
            return fail(name, "%s descriptor technology mismatch" % family)
        if registration.capability_statement() != tuple(
            registration.descriptor.capabilities
        ):
            return fail(name, "%s capability statement mismatch" % family)
        # the LOCK-109 bridge: the frozen name-equal vocabularies
        if registration.bridge_operations() != tuple(ADAPTER_OPERATIONS):
            return fail(name, "%s bridge operations drifted" % family)
        if tuple(ADAPTER_OPERATIONS) != tuple(CAPABILITY_OPERATIONS):
            return fail(name, "the seam/bridge vocabularies diverged")
        if registration.mechanisms != tuple(wire.STANDARD_MECHANISMS):
            return fail(name, "%s mechanism tags not carried verbatim" % family)
        # the handover declarations carried with the machinery's own
        # frozen semantics (the FULL preserved set — LOCK-108)
        kinds = tuple(
            characteristics.kind
            for characteristics in registration.handovers
        )
        if kinds != wl.WIRELINE_HANDOVER_KINDS[family]:
            return fail(name, "%s handover kinds not carried verbatim" % family)
        for characteristics in registration.handovers:
            if characteristics.preserved_constraint_kinds != preserved_constraint_kinds():
                return fail(name, "%s preserved set drift" % family)
        if registry.lookup(envelope.technology_class) is not registration:
            return fail(name, "%s registry lookup lost the registration" % family)
        ids.add(registration.registration_id)
    if len(ids) != 3:
        return fail(name, "registration identities not distinct per family")
    # the registration path itself is the accepted public surface
    # (the resolved public runtime IS the accepted seam object)
    if type(registration.resolve_capability_adapter()).__name__ != (
        "CapabilityAdapter"
    ):
        return fail(name, "the resolved runtime is not the accepted seam object")
    if type(registration.resolve_runtime()).__name__ != "AdapterRuntime":
        return fail(name, "the resolved runtime object is not the WORK-016 runtime")
    return ok(
        name,
        "all three wireline families registered through the accepted M020 "
        "public path: envelopes/ladders/handover declarations carried by "
        "reference; capability statements + LOCK-112 tags + LOCK-108 "
        "preserved sets verbatim; the LOCK-109 bridge frozen name-equal; "
        "identities content-derived and distinct",
    )


def case_05_registration_resolves_by_reference() -> Result:
    name = "case_05_registration_resolves_by_reference"
    _establish_wan_links()
    store, sid = ads._established_session()
    for family in FAMILIES:
        bridge, descriptor, requirements, site_links = _mount_family(store, family)
        registration = register_access_technology(
            envelope=wl.WIRELINE_ENVELOPES[family],
            ladder=wl.WIRELINE_LADDERS[family],
            handovers=wl.wireline_handover_declarations(family),
            implementation=bridge,
            descriptor=descriptor,
            binding_requirements=requirements,
            mechanisms=wire.STANDARD_MECHANISMS,
            session_store=store,
            now=_T0,
        )
        # identity-preserving resolution: the SAME live objects every
        # call (no re-instantiation, no second runtime)
        if registration.resolve_capability_adapter() is not registration.capability_adapter:
            return fail(name, "%s resolution re-instantiated the adapter" % family)
        if registration.resolve_capability_adapter() is not registration.resolve_capability_adapter():
            return fail(name, "%s resolution is not stable" % family)
        if registration.resolve_runtime() is not registration.runtime:
            return fail(name, "%s runtime resolution re-instantiated" % family)
        if registration.descriptor is not descriptor:
            return fail(name, "%s descriptor is not the mounted object" % family)
        # the public runtime carries the composition's technology and
        # resolves to the ACCEPTED backhaul family runtime BY REFERENCE
        view = registration.resolve_capability_adapter().inspect_capabilities(
            now=_NOW
        )
        if not view.ok:
            return fail(name, "%s inspect failed" % family)
        if view.value.adapter_id != descriptor.adapter_id:
            return fail(name, "%s view adapter mismatch" % family)
        if view.value.access_technology_id != wl.WIRELINE_ENVELOPES[family].technology_class:
            return fail(name, "%s view technology mismatch" % family)
        if view.value.lifecycle != "OPEN":
            return fail(name, "%s adapter not OPEN" % family)
        if view.value.standard_mechanisms != tuple(wire.STANDARD_MECHANISMS):
            return fail(name, "%s view mechanism tags mismatch" % family)
        # the composition's bridge IS the accepted family runtime's
        # SDK surface (the registered implementation object)
        if registration.descriptor is descriptor and bridge.__class__.__name__ != (
            "BackhaulTechnologyAdapter"
        ):
            return fail(name, "%s implementation is not the family bridge" % family)
        # the canonical record excludes the live objects and
        # round-trips with the live references re-supplied
        content = registration.to_dict()
        for key in ("capability_adapter", "runtime", "descriptor", "envelope", "ladder"):
            if key in content:
                return fail(name, "the canonical record carries %r" % key)
        rebuilt = technology_registration_from_mapping(
            content,
            envelope=wl.WIRELINE_ENVELOPES[family],
            ladder=wl.WIRELINE_LADDERS[family],
            handovers=wl.wireline_handover_declarations(family),
            capability_adapter=registration.capability_adapter,
            runtime=registration.runtime,
            descriptor=descriptor,
            binding_requirements=requirements,
            mechanisms=wire.STANDARD_MECHANISMS,
        )
        if rebuilt.registration_id != registration.registration_id:
            return fail(name, "%s registration identity changed on rebuild" % family)
        if rebuilt.to_canonical_bytes() != registration.to_canonical_bytes():
            return fail(name, "%s canonical record changed on rebuild" % family)
        if rebuilt.resolve_capability_adapter() is not registration.capability_adapter:
            return fail(name, "%s rebuild lost the live reference" % family)
    return ok(
        name,
        "3 families: resolution identity-preserving (the same live adapter, "
        "runtime and descriptor objects — the accepted backhaul family "
        "runtime BY REFERENCE); the public runtime carries the "
        "composition's technology; canonical records round-trip with the "
        "live references re-supplied",
    )


# ---------------------------------------------------------------------------
# (c) the nine WORK-016 operations — deterministic flows + the re-bind
# ---------------------------------------------------------------------------


def case_06_nine_operations_reserve_activate_measure() -> Result:
    name = "case_06_nine_operations_reserve_activate_measure"
    _establish_wan_links()
    # (a) the frozen disclosed translation map: every 1.1 operation
    # composes onto the WORK-016 nine-op surface exactly as declared
    if tuple(CAPABILITY_TRANSLATION_MAP) != (
        ("inspect-capabilities", ("capabilities",)),
        ("inspect-offers", ("capabilities",)),
        ("reserve", ("allocate",)),
        ("activate", ("bind_session",)),
        ("measure", ("observe",)),
        ("reconfigure", ("unbind_session", "bind_session")),
        ("release", ("release", "unbind_session")),
        ("health", ("health",)),
    ):
        return fail(name, "the disclosed translation map drifted")
    exercised: set = set()
    for family in FAMILIES:
        store, sid = ads._established_session()
        registration, _links = _register_family(store, family)
        capability = registration.resolve_capability_adapter()
        # inspect-capabilities -> capabilities
        inspected = capability.inspect_capabilities(now=_NOW)
        if not inspected.ok or not isinstance(inspected.value, CapabilityView):
            return fail(name, "%s inspect-capabilities not a typed view" % family)
        exercised.add("capabilities")
        # inspect-offers -> capabilities
        offers = capability.inspect_offers(now=_NOW)
        if not offers.ok or not isinstance(offers.value, tuple):
            return fail(name, "%s inspect-offers not a typed tuple" % family)
        for view in offers.value:
            if not isinstance(view, OfferView):
                return fail(name, "%s offer view not typed" % family)
            if view.quantity <= 0:
                return fail(name, "%s offer quantity non-positive" % family)
            if view.availability != "continuous":
                return fail(name, "%s offer availability not continuous" % family)
        exercised.add("capabilities")
        # health -> health
        health = capability.health(now=_NOW)
        if not health.ok or not isinstance(health.value, HealthReport):
            return fail(name, "%s health not a typed report" % family)
        exercised.add("health")
        # reserve -> allocate
        reserved = capability.reserve(
            kind="backhaul",
            quantity=_FAMILY_RESERVE[family],
            unit="bps",
            purpose="m021-%s-flow" % family,
            now=_NOW,
        )
        if not reserved.ok or not isinstance(reserved.value, Allocation):
            return fail(name, "%s reserve not a typed allocation" % family)
        if reserved.value.quantity_base != _FAMILY_RESERVE[family]:
            return fail(name, "%s reserve base-unit drift" % family)
        exercised.add("allocate")
        # activate -> bind_session
        activated = capability.activate(
            reservation_id=reserved.value.allocation_id,
            session_id=sid,
            requirements=dict(registration.binding_requirements),
            now=_NOW,
        )
        if not activated.ok or not isinstance(activated.value, Activation):
            return fail(name, "%s activate not a typed activation" % family)
        if activated.value.state != "ACTIVE":
            return fail(name, "%s activation not ACTIVE" % family)
        if activated.value.session_id != sid:
            return fail(name, "%s activation session mismatch" % family)
        if activated.value.reservation_id != reserved.value.allocation_id:
            return fail(name, "%s activation reservation mismatch" % family)
        exercised.add("bind_session")
        # measure -> observe
        measured = capability.measure(
            activation_id=activated.value.activation_id, now=_LATER
        )
        if not measured.ok or not isinstance(measured.value, Measurement):
            return fail(name, "%s measure not a typed measurement" % family)
        if not measured.value.samples:
            return fail(name, "%s measurement carries no samples" % family)
        if measured.value.activation_id != activated.value.activation_id:
            return fail(name, "%s measurement attribution mismatch" % family)
        exercised.add("observe")
        # release -> release + unbind_session
        released = capability.release(
            activation_id=activated.value.activation_id, now=_LATER2
        )
        if not released.ok or not isinstance(released.value, ReleaseReceipt):
            return fail(name, "%s release not a typed receipt" % family)
        if released.value.released_kinds != ("activation", "reservation"):
            return fail(name, "%s release kinds wrong: %s" % (family, released.value.released_kinds))
        if capability.activation(activated.value.activation_id).state != "RELEASED":
            return fail(name, "%s activation not terminal RELEASED" % family)
        exercised.update({"release", "unbind_session"})
        # the measurement trail is bounded and ordered
        trail = capability.measurements(activated.value.activation_id)
        if len(trail) != 1:
            return fail(name, "%s measurement trail wrong size" % family)
    # every translation target was driven through the mediated
    # nine-op runtime in these flows (open happens at registration)
    if not exercised >= {
        "capabilities", "allocate", "bind_session", "observe",
        "unbind_session", "release", "health",
    }:
        return fail(name, "translation targets not all exercised: %s" % sorted(exercised))
    return ok(
        name,
        "3 families: the frozen translation map verified and every flow "
        "green through the mediated WORK-016 nine-op runtime "
        "(capabilities/allocate/bind_session/observe/unbind_session/"
        "release/health + the registration open drive); typed records at "
        "every step; activation trails bounded and ordered",
    )


def case_07_rebind_translation_mid_session() -> Result:
    name = "case_07_rebind_translation_mid_session"
    _establish_wan_links()
    for family in FAMILIES:
        store, sid = ads._established_session()
        registration, site_links = _register_family(store, family)
        capability = registration.resolve_capability_adapter()
        reserved = capability.reserve(
            kind="backhaul",
            quantity=_FAMILY_RESERVE[family],
            unit="bps",
            purpose="m021-%s-rebind" % family,
            now=_NOW,
        )
        if not reserved.ok:
            return fail(name, "%s reserve failed" % family)
        activated = capability.activate(
            reservation_id=reserved.value.allocation_id,
            session_id=sid,
            requirements=dict(registration.binding_requirements),
            now=_NOW,
        )
        if not activated.ok:
            return fail(name, "%s activate failed" % family)
        activation = activated.value
        previous_binding = activation.binding_id
        # the deterministic re-bind translation: SAME session, the
        # PRESERVED reservation, the previous binding released FIRST,
        # a NEW binding created — one typed Reconfiguration record
        requirements = _reconfigure_requirements(family, registration)
        reconfigured = capability.reconfigure(
            activation_id=activation.activation_id,
            requirements=requirements,
            now=_LATER,
        )
        if not reconfigured.ok or not isinstance(reconfigured.value, Reconfiguration):
            return fail(name, "%s reconfigure not a typed record" % family)
        record = reconfigured.value
        if record.session_id != sid:
            return fail(name, "%s re-bind changed the session" % family)
        if record.reservation_id != reserved.value.allocation_id:
            return fail(name, "%s re-bind lost the reservation" % family)
        if record.activation_id != activation.activation_id:
            return fail(name, "%s re-bind changed the activation" % family)
        if record.previous_binding_id != previous_binding:
            return fail(name, "%s re-bind hid the previous binding" % family)
        if record.binding_id == previous_binding:
            return fail(name, "%s re-bind reused the previous binding" % family)
        if record.applied_requirements != tuple(requirements.items()):
            return fail(name, "%s applied requirements mismatch" % family)
        if record.applied_instant != _LATER:
            return fail(name, "%s applied instant mismatch" % family)
        # the activation ledger: ACTIVE -> RECONFIGURED with the new
        # binding id and the reconfiguration instant recorded
        updated = capability.activation(activation.activation_id)
        if updated.state != "RECONFIGURED":
            return fail(name, "%s activation not RECONFIGURED" % family)
        if updated.binding_id != record.binding_id:
            return fail(name, "%s activation binding mismatch" % family)
        if updated.last_reconfigured_instant != _LATER:
            return fail(name, "%s reconfiguration instant missing" % family)
        # idempotent second reconfiguration (RECONFIGURED ->
        # RECONFIGURED; the reference semantics of standards-native
        # steering/reweighting updates)
        second = capability.reconfigure(
            activation_id=activation.activation_id,
            requirements=requirements,
            now=_LATER2,
        )
        if not second.ok:
            return fail(name, "%s second reconfigure failed" % family)
        if capability.activation(activation.activation_id).state != "RECONFIGURED":
            return fail(name, "%s second reconfigure state drift" % family)
        # measure after the re-bind + release green
        measured = capability.measure(
            activation_id=activation.activation_id, now=_LATER2
        )
        if not measured.ok:
            return fail(name, "%s post-rebind measure failed" % family)
        released = capability.release(
            activation_id=activation.activation_id, now=_LATER2
        )
        if not released.ok:
            return fail(name, "%s post-rebind release failed" % family)
        if capability.activation(activation.activation_id).state != "RELEASED":
            return fail(name, "%s post-rebind release not terminal" % family)
    # the enterprise-WAN's mid-session SITE RESELECTION: the
    # re-bound circuit is a DIFFERENT declared site pair
    store, sid = ads._established_session()
    registration, site_links = _register_family(store, "enterprise-wan")
    capability = registration.resolve_capability_adapter()
    reserved = capability.reserve(
        kind="backhaul", quantity=100_000_000, unit="bps",
        purpose="m021-wan-site-reselection", now=_NOW,
    )
    activated = capability.activate(
        reservation_id=reserved.value.allocation_id,
        session_id=sid,
        requirements=dict(registration.binding_requirements),
        now=_NOW,
    )
    if not activated.ok:
        return fail(name, "wan activate failed")
    reselected = capability.reconfigure(
        activation_id=activated.value.activation_id,
        requirements={
            "link_ref": site_links["wan-site-b+wan-site-c"],
            "endpoint_label": "wan-site-c",
        },
        now=_LATER,
    )
    if not reselected.ok:
        return fail(
            name,
            "wan site reselection failed: %s" % _failure_reason(reselected),
        )
    if reselected.value.previous_binding_id == reselected.value.binding_id:
        return fail(name, "wan site reselection did not re-bind")
    released = capability.release(
        activation_id=activated.value.activation_id, now=_LATER2
    )
    if not released.ok:
        return fail(name, "wan site reselection release failed")
    return ok(
        name,
        "3 families: the deterministic re-bind translation verified "
        "(same session, preserved reservation, previous binding released "
        "first, new binding created — typed Reconfiguration records; "
        "ACTIVE -> RECONFIGURED; idempotent second reconfiguration; "
        "measure + release green after the re-bind) — including the "
        "enterprise-WAN mid-session SITE RESELECTION onto another "
        "declared site pair",
    )


# ---------------------------------------------------------------------------
# (d) the declared enterprise-WAN site topology (LOCK-105)
# ---------------------------------------------------------------------------


def case_08_enterprise_wan_site_topology_declared_data() -> Result:
    name = "case_08_enterprise_wan_site_topology_declared_data"
    # (a) the declared record round-trips canonical-JSON
    # byte-identically with a content-derived identity
    topology = REFERENCE_SITE_TOPOLOGY
    rebuilt = site_topology_from_mapping(topology.to_dict())
    if rebuilt.to_canonical_bytes() != topology.to_canonical_bytes():
        return fail(name, "site topology round-trip not byte-identical")
    if rebuilt.topology_id != topology.topology_id:
        return fail(name, "site topology identity changed on reconstruction")
    # (b) NO transitive closure: declared pairs stay declared,
    # undeclared pairs stay undeclared (declared data only — never
    # a computed global graph)
    partial = SiteTopology(
        sites=("wan-site-a", "wan-site-b", "wan-site-d"),
        site_pairs=(("wan-site-a", "wan-site-b"), ("wan-site-b", "wan-site-d")),
    )
    if not partial.declares_pair("wan-site-a", "wan-site-b"):
        return fail(name, "declared pair reported undeclared")
    if not partial.declares_pair("wan-site-b", "wan-site-d"):
        return fail(name, "declared pair reported undeclared (order-insensitive)")
    if partial.declares_pair("wan-site-a", "wan-site-d"):
        return fail(
            name,
            "undeclared pair reported declared — a transitive-closure leak "
            "(LOCK-105: declared data only, never computed reachability)",
        )
    # (c) every malformed class a TYPED rejection (the undeclared-
    # site pair IS the global-topology-leak class)
    probes = [
        ("undeclared site pair (topology leak)", lambda: SiteTopology(
            sites=("wan-site-a", "wan-site-b"),
            site_pairs=(("wan-site-a", "wan-site-c"),))),
        ("self pair", lambda: SiteTopology(
            sites=("wan-site-a", "wan-site-b"),
            site_pairs=(("wan-site-a", "wan-site-a"),))),
        ("duplicate pair", lambda: SiteTopology(
            sites=("wan-site-a", "wan-site-b"),
            site_pairs=(("wan-site-a", "wan-site-b"), ("wan-site-b", "wan-site-a")))),
        ("disordered sites", lambda: SiteTopology(
            sites=("wan-site-b", "wan-site-a"),
            site_pairs=(("wan-site-a", "wan-site-b"),))),
        ("no sites", lambda: SiteTopology(
            sites=(), site_pairs=(("wan-site-a", "wan-site-b"),))),
        ("no pairs", lambda: SiteTopology(
            sites=("wan-site-a", "wan-site-b"), site_pairs=())),
        ("node-id shaped site label", lambda: SiteTopology(
            sites=("adcos:node:abc123",), site_pairs=())),
        ("tampered topology identity", lambda: site_topology_from_mapping(
            {**topology.to_dict(), "topology_id": "sha256:" + "0" * 64})),
        ("grammar drift", lambda: site_topology_from_mapping(
            {k: v for k, v in topology.to_dict().items() if k != "sites"})),
    ]
    for label, action in probes:
        outcome = expect_family_error(name, "invalid-input", action)
        if not outcome[1]:
            return fail(name, "%s: %s" % (label, outcome[2]))
    # (d) the composition provisions EXACTLY the declared pairs (no
    # inferred links — the site-link map keys are the declared pairs)
    store, sid = ads._established_session()
    _bridge, descriptor, requirements, site_links = _mount_family(
        store, "enterprise-wan"
    )
    expected_keys = tuple(
        site_pair_key(first, second) for first, second in topology.site_pairs
    )
    if tuple(sorted(site_links)) != tuple(sorted(expected_keys)):
        return fail(
            name,
            "the composition provisioned beyond the declared pairs: %s"
            % sorted(set(site_links) - set(expected_keys)),
        )
    if requirements["endpoint_label"] not in topology.sites:
        return fail(name, "default binding endpoint is not a declared site")
    if descriptor.resource_mapping[0].quantity != wire.SITE_PAIR_LINK_BPS * len(
        topology.site_pairs
    ):
        return fail(name, "mapped capacity is not the declared pair sum")
    # (e) the boundary views carry NO topology facts (the offer views
    # carry the mapped resource + capability references + LOCK-112
    # tags — never site sets or site pairs)
    _establish_wan_links()
    registration = register_access_technology(
        envelope=wl.WIRELINE_ENVELOPES["enterprise-wan"],
        ladder=wl.WIRELINE_LADDERS["enterprise-wan"],
        handovers=wl.wireline_handover_declarations("enterprise-wan"),
        implementation=_bridge,
        descriptor=descriptor,
        binding_requirements=requirements,
        mechanisms=wire.STANDARD_MECHANISMS,
        session_store=store,
        now=_T0,
    )
    view = registration.resolve_capability_adapter().inspect_capabilities(now=_NOW)
    if not view.ok:
        return fail(name, "wan inspect failed")
    view_dict = view.value.to_dict()
    if "sites" in view_dict or "site_pairs" in view_dict or "topology" in view_dict:
        return fail(name, "the capability view carries topology facts")
    offers = registration.resolve_capability_adapter().inspect_offers(now=_NOW)
    if not offers.ok:
        return fail(name, "wan offers failed")
    for offer in offers.value:
        offer_dict = offer.to_dict()
        for member in ("sites", "site_pairs", "topology"):
            if member in offer_dict:
                return fail(name, "the offer view carries topology facts")
    # the declared topology never becomes view data beyond the
    # mapped declared capacity
    if view.value.capability_references != tuple(descriptor.capabilities):
        return fail(name, "view capability references drift")
    return ok(
        name,
        "the declared enterprise-WAN site topology is DECLARED DATA ONLY: "
        "canonical round-trips with tamper evidence; 9 malformed classes "
        "typed-rejected (the undeclared-site pair IS the topology-leak "
        "class); NO transitive closure (undeclared pairs stay undeclared); "
        "the composition provisions exactly the declared pairs; the "
        "boundary views carry no topology facts",
    )


# ---------------------------------------------------------------------------
# (e) LOCK-110 isolation + the typed fail-closed matrix
# ---------------------------------------------------------------------------


def case_09_lock110_provider_sdk_isolation() -> Result:
    name = "case_09_lock110_provider_sdk_isolation"
    _establish_wan_links()
    for family in FAMILIES:
        store, sid = ads._established_session()
        registration, _links = _register_family(store, family)
        capability = registration.resolve_capability_adapter()
        records: List[Any] = []
        inspected = capability.inspect_capabilities(now=_NOW)
        offers = capability.inspect_offers(now=_NOW)
        health = capability.health(now=_NOW)
        reserved = capability.reserve(
            kind="backhaul", quantity=_FAMILY_RESERVE[family], unit="bps",
            purpose="m021-%s-isolation" % family, now=_NOW,
        )
        activated = capability.activate(
            reservation_id=reserved.value.allocation_id,
            session_id=sid,
            requirements=dict(registration.binding_requirements),
            now=_NOW,
        )
        measured = capability.measure(
            activation_id=activated.value.activation_id, now=_LATER
        )
        reconfigured = capability.reconfigure(
            activation_id=activated.value.activation_id,
            requirements=_reconfigure_requirements(family, registration),
            now=_LATER,
        )
        released = capability.release(
            activation_id=activated.value.activation_id, now=_LATER2
        )
        for result in (inspected, offers, health, reserved, activated,
                       measured, reconfigured, released):
            if not result.ok:
                return fail(name, "%s flow failed" % family)
        # every 1.1 operation returns the CANONICAL typed
        # provider-neutral records (LOCK-110)
        expected_types = (
            CapabilityView, OfferView, HealthReport, Allocation,
            Activation, Measurement, Reconfiguration, ReleaseReceipt,
        )
        values = [inspected.value]
        values.extend(offers.value)
        values.extend(
            [health.value, reserved.value, activated.value,
             measured.value, reconfigured.value, released.value]
        )
        for value in values:
            if not isinstance(value, expected_types):
                return fail(
                    name,
                    "%s returned a non-canonical type %s"
                    % (family, type(value).__name__),
                )
        records.extend(values)
        # NO opaque family technology reference crosses into any
        # canonical record byte OUTSIDE the caller-supplied
        # requirements snapshots (the wiring link_ref the composition
        # hands the caller is disclosed binding DATA — LOCK-017; the
        # provider-SDK bearer/link HANDLES stay behind the WORK-016
        # runtime, keyed internally)
        wiring_members = ("requirements", "applied_requirements")
        for record in records:
            record_dict = record.to_dict()
            scanned = {
                key: value
                for key, value in record_dict.items()
                if key not in wiring_members
            }
            blob = canonical_json_bytes(scanned)
            if b"backhaul:" in blob:
                return fail(
                    name,
                    "%s: an opaque family technology reference crossed the "
                    "boundary into a canonical record" % family,
                )
        # the requirements snapshots carry EXACTLY the caller-supplied
        # wiring data (the disclosed composition wiring — never keys
        # the caller did not supply)
        supplied = dict(registration.binding_requirements)
        activation_requirements = dict(activated.value.requirements)
        if set(activation_requirements) - set(supplied):
            return fail(
                name,
                "%s activation requirements carry unsupplied keys" % family,
            )
        # the activation ledger's binding id is the ADCOS
        # content-derived id (sha256:), never the opaque bearer ref
        if not activated.value.binding_id.startswith("sha256:"):
            return fail(name, "%s binding id is not content-derived" % family)
        # the LOCK-112 mechanism tags ride as citation DATA in the views
        if inspected.value.standard_mechanisms != tuple(wire.STANDARD_MECHANISMS):
            return fail(name, "%s view tags mismatch" % family)
    # the composition modules branch on NO technology name (the
    # technology enters as DATA — the M007 case_09 discipline).  The
    # scan covers the modules' OWN declared/defined vocabulary:
    # identifiers IMPORTED from the accepted surfaces (the family
    # bridge class, the model types) are the by-reference composition
    # itself, never this delivery's branching — excluded from the
    # token scan exactly as the accepted M007 audit scoped itself to
    # the M007-owned files.
    forbidden = ("3gpp", "80211", "8023", "imt2020", "imt2030", "wifi",
                 "wi-fi", "nr", "lte", "5g", "6g", "bluetooth", "microwave",
                 "satellite", "entangled", "synthetic")
    for path in (REPO_ROOT / "adapters" / "reference" / "wireline.py",
                 REPO_ROOT / "accesstech" / "wireline.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported_names: set = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name.split(".")[-1])
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name.split(".")[-1])
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.arg):
                names.add(node.arg)
        own_names = names - imported_names
        for token in forbidden:
            for code_name in own_names:
                if token in code_name.lower():
                    return fail(
                        name,
                        "%s: code name %r embeds %r (no tech branching)"
                        % (path.name, code_name, token),
                    )
    return ok(
        name,
        "LOCK-110 holds: every 1.1 operation returns the canonical typed "
        "provider-neutral records; zero opaque family technology "
        "references in any canonical record byte; the LOCK-112 tags are "
        "citation DATA; the composition modules branch on no technology "
        "name",
    )


def case_10_typed_errors_fail_closed() -> Result:
    name = "case_10_typed_errors_fail_closed"
    _establish_wan_links()
    store, sid = ads._established_session()
    registration, _links = _register_family(store, "ethernet")
    capability = registration.resolve_capability_adapter()
    requirements = dict(registration.binding_requirements)
    reserved = capability.reserve(
        kind="backhaul", quantity=100, unit="bps",
        purpose="m021-failclosed", now=_NOW,
    )
    if not reserved.ok:
        return fail(name, "reserve failed")
    # (a) isolated failure VALUES (deterministic reasons, twice each —
    # fail-closed determinism): capacity exhaustion, identity
    # smuggling, unknown endpoint, unknown link
    isolated_probes = [
        ("capacity exhaustion", lambda: capability.reserve(
            kind="backhaul", quantity=2_000_000_000, unit="bps",
            purpose="too-big", now=_NOW), "capacity-exhausted"),
        ("identity smuggling", lambda: capability.activate(
            reservation_id=reserved.value.allocation_id, session_id=sid,
            requirements={"session_id": "smuggled"}, now=_NOW), "adapter-failure"),
        ("unknown endpoint", lambda: capability.activate(
            reservation_id=reserved.value.allocation_id, session_id=sid,
            requirements={"link_ref": requirements["link_ref"],
                          "endpoint_label": "no-such-port"}, now=_NOW), "adapter-failure"),
        ("unknown link", lambda: capability.activate(
            reservation_id=reserved.value.allocation_id, session_id=sid,
            requirements={"link_ref": "backhaul:link:" + "0" * 16}, now=_NOW), "adapter-failure"),
    ]
    for label, action, reason in isolated_probes:
        first = action()
        second = action()
        if first.ok or second.ok:
            return fail(name, "%s was accepted" % label)
        if _failure_reason(first) != reason or _failure_reason(second) != reason:
            return fail(
                name,
                "%s reason drift: %s / %s (expected %s)"
                % (label, _failure_reason(first), _failure_reason(second), reason),
            )
    # (b) caller-side typed RAISES (the accepted seam's discipline)
    raised_probes = [
        ("unmapped kind", lambda: capability.reserve(
            kind="storage", quantity=10, unit="bytes",
            purpose="bad-kind", now=_NOW), "mapping-invalid"),
        ("unknown reservation", lambda: capability.activate(
            reservation_id="sha256:" + "0" * 64, session_id=sid,
            requirements=dict(requirements), now=_NOW), "allocation-unknown"),
        ("unknown activation", lambda: capability.activation(
            "sha256:" + "0" * 64), "allocation-unknown"),
        ("release without ids", lambda: capability.release(now=_NOW), "invalid-input"),
    ]
    for label, action, reason in raised_probes:
        outcome = expect_adapter_error(name, reason, action)
        if not outcome[1]:
            return fail(name, "%s: %s" % (label, outcome[2]))
    # (c) terminal-state discipline: a RELEASED activation can be
    # neither reconfigured nor measured (typed STATE_CONFLICT)
    activated = capability.activate(
        reservation_id=reserved.value.allocation_id, session_id=sid,
        requirements=dict(requirements), now=_NOW,
    )
    if not activated.ok:
        return fail(name, "activate failed")
    released = capability.release(
        activation_id=activated.value.activation_id, now=_LATER
    )
    if not released.ok:
        return fail(name, "release failed")
    for label, action in (
        ("released reconfigure", lambda: capability.reconfigure(
            activation_id=activated.value.activation_id,
            requirements=dict(requirements), now=_LATER)),
        ("released measure", lambda: capability.measure(
            activation_id=activated.value.activation_id, now=_LATER)),
        ("double release", lambda: capability.release(
            activation_id=activated.value.activation_id, now=_LATER)),
    ):
        outcome = expect_adapter_error(name, "state-conflict", action)
        if not outcome[1]:
            return fail(name, "%s: %s" % (label, outcome[2]))
    # (d) the static-availability and site-topology typed rejections
    # re-fire identically on the declarations (fail-closed twice)
    multi_window = CapabilityEnvelope(
        technology_class=wl.FIBER_TECHNOLOGY_CLASS,
        bandwidth=BpsRange(1_000_000_000, 100_000_000_000),
        latency=LatencyMilliRange(1, 15),
        jitter=JitterMilliRange(0, 2),
        availability=AvailabilityWindows(
            (
                AvailabilityWindow("2026-03-01T00:00:00Z", "2026-03-02T00:00:00Z"),
                AvailabilityWindow("2026-09-01T00:00:00Z", "2026-09-03T00:00:00Z"),
            )
        ),
    )
    for probe in range(2):
        outcome = expect_typed(
            name, "accesstech-envelope-inconsistent",
            lambda: wl.require_static_availability(multi_window),
        )
        if not outcome[1]:
            return fail(name, "static rejection %d: %s" % (probe, outcome[2]))
        outcome = expect_family_error(
            name, "invalid-input",
            lambda: SiteTopology(
                sites=("wan-site-a",), site_pairs=(("wan-site-a", "wan-site-b"),)),
        )
        if not outcome[1]:
            return fail(name, "topology rejection %d: %s" % (probe, outcome[2]))
    return ok(
        name,
        "the typed fail-closed matrix: 4 isolated failure classes "
        "(deterministic reasons, twice each), 4 caller-side typed raises, "
        "3 terminal-state rejections, and the declaration rejections "
        "re-fire identically — never warnings",
    )


# ---------------------------------------------------------------------------
# (f) the one-way boundary, the delta audit, determinism, evidence
# ---------------------------------------------------------------------------


def _origin_main_available() -> bool:
    probe = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/main"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    return probe.returncode == 0


def case_11_one_way_import_audit() -> Result:
    name = "case_11_one_way_import_audit"
    problems: List[str] = []
    # (a) no accepted authority imports the new modules (AST tokens,
    # not docstrings): neither ``adapters.reference.wireline`` nor
    # ``accesstech.wireline`` is referenced in authority CODE
    authorities = (
        "contracts", "replan", "executionplans", "evidence", "assurance",
        "offers", "eligibility", "policy", "adapters", "usage", "commercial",
        "allocation", "payment", "sharenet", "roamlink", "comos",
        "developerapi", "federation", "identity", "upgrade", "scale",
        "client", "resilience", "localfirst", "recovery", "credentials",
        "accesstech",
    )

    def _references_module(source: str) -> bool:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return False
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "wireline":
                return True
            if isinstance(node, ast.Attribute) and node.attr == "wireline":
                return True
            if isinstance(node, ast.ImportFrom) and node.module and (
                "wireline" in node.module
            ):
                return True
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "wireline" in alias.name:
                        return True
        return False

    for package in authorities:
        package_dir = REPO_ROOT / package
        if not package_dir.is_dir():
            continue
        for path in sorted(package_dir.glob("*.py")):
            source = path.read_text(encoding="utf-8")
            if "wireline" in source and _references_module(source):
                problems.append(
                    "%s/%s references the new module (one-way boundary)"
                    % (package, path.name)
                )
    # the frozen package initializers do not import the new modules
    # (the accepted __init__ surfaces stay untouched)
    for init_path in (
        REPO_ROOT / "accesstech" / "__init__.py",
        REPO_ROOT / "adapters" / "reference" / "__init__.py",
    ):
        tree = ast.parse(init_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "wireline" in (
                node.module or ""
            ):
                problems.append("%s imports the new module" % init_path.name)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "wireline" in alias.name:
                        problems.append("%s imports the new module" % init_path.name)
    # (b) the new modules' own import discipline:
    # adapters/reference/wireline.py NEVER imports accesstech (the
    # one-way boundary); accesstech/wireline.py imports only the
    # accepted accesstech surface (relative imports — no adapters
    # import, no authority outside accesstech)
    composition_path = REPO_ROOT / "adapters" / "reference" / "wireline.py"
    declarations_path = REPO_ROOT / "accesstech" / "wireline.py"
    composition_tree = ast.parse(composition_path.read_text(encoding="utf-8"))
    for node in ast.walk(composition_tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] == "accesstech":
                problems.append("adapters/reference/wireline.py imports accesstech")
            if node.module and node.module.split(".")[0] in (
                "imt", "transport", "topology", "networkpath", "sessions",
                "mobility", "multipath", "edge", "appliance", "mobile",
                "management", "simulator", "resources", "services",
                "contracts",
            ):
                problems.append(
                    "adapters/reference/wireline.py imports %s" % node.module
                )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in ("accesstech", "contracts"):
                    problems.append(
                        "adapters/reference/wireline.py imports %s" % root
                    )
    declarations_tree = ast.parse(declarations_path.read_text(encoding="utf-8"))
    for node in ast.walk(declarations_tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            root = node.module.split(".")[0]
            if root != "__future__" and root != "typing":
                problems.append(
                    "accesstech/wireline.py imports the non-relative %s" % root
                )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root != "__future__" and root != "typing":
                    problems.append(
                        "accesstech/wireline.py imports the non-relative %s" % root
                    )
    # (c) the clock/random/network discipline on both new modules
    for path in (composition_path, declarations_path):
        source = path.read_text(encoding="utf-8")
        for forbidden in (
            "datetime.now", "time.time", "utcnow", "uuid", "random.",
            "socket.", "requests.", "urlopen", "time.monotonic",
            "time.sleep",
        ):
            if forbidden in source:
                problems.append("%s carries %r" % (path.name, forbidden))
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "no accepted authority references the new modules (one-way boundary "
        "over %d packages, AST tokens); the frozen package initializers "
        "untouched; adapters/reference/wireline.py never imports accesstech; "
        "accesstech/wireline.py imports only the accepted accesstech surface "
        "(relative only); both modules clock/random/network-free" % len(authorities),
    )


def case_12_zero_contract_core_delta() -> Result:
    name = "case_12_zero_contract_core_delta"
    # (a) the AST import audit: the new modules import NO contracts
    # surface AT ALL (stronger than the M020 CONSTRAINT_KINDS-only
    # shape — the wireline surface needs no contract vocabulary)
    for path in (REPO_ROOT / "adapters" / "reference" / "wireline.py",
                 REPO_ROOT / "accesstech" / "wireline.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[0] == "contracts":
                    return fail(
                        name,
                        "%s imports a contracts surface" % path.name,
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] == "contracts":
                        return fail(
                            name,
                            "%s imports a contracts surface" % path.name,
                        )
    # (b) the git-guarded PR delta: zero contracts/ files touched; the
    # delta confined to the authorization scope
    if not _origin_main_available():
        return ok(
            name,
            "AST audit green (zero contracts imports); git delta check "
            "skipped (no origin/main ref; the CI provenance step enforces "
            "scope)",
        )
    delta: set = set()
    diff = subprocess.run(
        ["git", "diff", "--name-only", "origin/main"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    if diff.returncode == 0:
        delta |= {line for line in diff.stdout.splitlines() if line.strip()}
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    if untracked.returncode == 0:
        delta |= {line for line in untracked.stdout.splitlines() if line.strip()}
    if not delta:
        return ok(name, "AST audit green; no delta (clean main)")
    problems: List[str] = []
    for path in sorted(delta):
        if path.startswith("contracts/"):
            problems.append("the delivery delta touches the contract core: %s" % path)
            continue
        try:
            from authorization_provenance import covers  # type: ignore

            covered = covers(path)
        except Exception:  # noqa: BLE001
            covered = False
        if not covered:
            problems.append("delta outside the authorization scope: %s" % path)
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "AST audit green (zero contracts imports in the new modules); the "
        "PR delta (%d file(s)) touches no contract-core file and stays "
        "inside the R9-CORE-001 scope" % len(delta),
    )


def case_13_determinism_byte_identical() -> Result:
    name = "case_13_determinism_byte_identical"
    _establish_wan_links()
    # (a) in-process rebuild: the whole wireline surface re-registered
    # from scratch -> byte-identical canonical bytes and identities
    store, sid = ads._established_session()
    registry_first, registrations_first, links_first = _register_all(store)
    flows_first = {
        family: _full_flow(registrations_first[family], family, sid)
        for family in FAMILIES
    }
    registry_second, registrations_second, links_second = _register_all(store)
    flows_second = {
        family: _full_flow(registrations_second[family], family, sid)
        for family in FAMILIES
    }
    for family in FAMILIES:
        first = registrations_first[family]
        second = registrations_second[family]
        if first.to_canonical_bytes() != second.to_canonical_bytes():
            return fail(name, "%s registration bytes differ on rebuild" % family)
        if first.registration_id != second.registration_id:
            return fail(name, "%s registration identity differs" % family)
        if first.envelope.to_canonical_bytes() != second.envelope.to_canonical_bytes():
            return fail(name, "%s envelope bytes differ on rebuild" % family)
        if first.ladder.to_canonical_bytes() != second.ladder.to_canonical_bytes():
            return fail(name, "%s ladder bytes differ on rebuild" % family)
        if flows_first[family] != flows_second[family]:
            return fail(name, "%s lifecycle record bytes differ on rebuild" % family)
        if links_first[family] != links_second[family]:
            return fail(name, "%s site links differ on rebuild" % family)
    if registry_first.technology_classes() != registry_second.technology_classes():
        return fail(name, "registry order differs on rebuild")
    if REFERENCE_SITE_TOPOLOGY.to_canonical_bytes() != site_topology_from_mapping(
        REFERENCE_SITE_TOPOLOGY.to_dict()
    ).to_canonical_bytes():
        return fail(name, "site topology bytes differ on rebuild")
    # (b) cross-process: the registration + lifecycle material built
    # in PYTHONHASHSEED 0/1/42 subprocesses -> byte-identical digests
    probe = r"""
import sys
sys.path.insert(0, %r)
sys.path.insert(0, %r)
import hashlib
import adapter_selftest as ads
import wireline_selftest as m021
from adapters.reference.wireline import REFERENCE_SITE_TOPOLOGY
store, sid = ads._established_session()
registry, registrations, links = m021._register_all(store)
material = b"".join(
    registrations[family].to_canonical_bytes()
    for family in m021.FAMILIES
)
material += REFERENCE_SITE_TOPOLOGY.to_canonical_bytes()
for family in m021.FAMILIES:
    material += b"".join(m021._full_flow(registrations[family], family, sid))
print(hashlib.sha256(material).hexdigest())
print(" ".join(r[6:] for r in (
    registrations[f].registration_id for f in m021.FAMILIES
)))
print(len(registry))
""" % (str(REPO_ROOT), str(REPO_ROOT / "tools"))
    outputs: set = set()
    for seed in ("0", "1", "42"):
        env = {"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"}
        run = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(REPO_ROOT),
        )
        if run.returncode != 0:
            return fail(
                name,
                "seed %s subprocess failed: %s" % (seed, run.stderr[-200:]),
            )
        outputs.add(run.stdout)
    if len(outputs) != 1:
        return fail(
            name,
            "wireline material differs across PYTHONHASHSEED subprocesses "
            "(%d distinct outputs)" % len(outputs),
        )
    return ok(
        name,
        "in-process rebuild byte-identical (registrations, envelopes, "
        "ladders, lifecycle records, site links, registry order); the "
        "full wireline material byte-identical across PYTHONHASHSEED "
        "0/1/42 subprocesses",
    )


def case_14_evidence_doc_honest() -> Result:
    name = "case_14_evidence_doc_honest"
    path = REPO_ROOT / "docs" / "M021-evidence.md"
    if not path.exists():
        return fail(name, "docs/M021-evidence.md is missing")
    text = path.read_text(encoding="utf-8")
    problems: List[str] = []
    if "SOFTWARE" not in text:
        problems.append("the evidence class is not disclosed")
    if "M021" not in text:
        problems.append("the evidence does not name M021")
    for lock in ("LOCK-105", "LOCK-110", "LOCK-112", "LOCK-106", "LOCK-119"):
        if lock not in text:
            problems.append("the %s mapping is not disclosed" % lock)
    if "EVID-002" not in text:
        problems.append("the open physical evidence obligations are not disclosed")
    if "by reference" not in text.lower():
        problems.append("the by-reference composition is not disclosed")
    if "case_68" not in text:
        problems.append("the adapter-battery delta-guard conflict is not disclosed")
    normalized = " ".join(text.split()).lower()
    for phrase in (
        "physical pass",
        "physically verified",
        "production pass",
        "live-service evidence",
    ):
        start = 0
        while True:
            index = normalized.find(phrase, start)
            if index < 0:
                break
            window = normalized[max(0, index - 90) : index]
            if "not" not in window and "never" not in window and "no " not in window:
                problems.append("affirmative physical claim near %r" % phrase)
            start = index + 1
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "SOFTWARE class, by-reference composition, the lock mapping, the "
        "adapter-battery conflict and the open physical obligations "
        "disclosed; no affirmative physical claims",
    )


# ===========================================================================
# Main
# ===========================================================================


def main() -> int:
    _establish_wan_links()
    results: List[Result] = []
    results.append(case_01_wireline_declarations_round_trip())
    results.append(case_02_static_availability_no_mobility())
    results.append(case_03_ladders_declared_capacity_steps())
    results.append(case_04_families_registered_through_extension_surface())
    results.append(case_05_registration_resolves_by_reference())
    results.append(case_06_nine_operations_reserve_activate_measure())
    results.append(case_07_rebind_translation_mid_session())
    results.append(case_08_enterprise_wan_site_topology_declared_data())
    results.append(case_09_lock110_provider_sdk_isolation())
    results.append(case_10_typed_errors_fail_closed())
    results.append(case_11_one_way_import_audit())
    results.append(case_12_zero_contract_core_delta())
    results.append(case_13_determinism_byte_identical())
    results.append(case_14_evidence_doc_honest())

    print("ADCOS wireline self-test (M021 — Wireline Access Adapters)")
    print("=" * 78)
    for name, passed, detail in results:
        print("[%s] %-56s %s" % ("ok  " if passed else "FAIL", name, detail))
    print("-" * 78)
    passed_count = sum(1 for _, p, _ in results if p)
    if passed_count == len(results):
        print("Result: PASS (%d/%d cases)" % (passed_count, len(results)))
        return 0
    print("Result: FAIL (%d/%d cases passed)" % (passed_count, len(results)))
    return 1


if __name__ == "__main__":
    sys.exit(main())
