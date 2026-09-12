#!/usr/bin/env python3
"""ADCOS access-technology envelope self-test (M020).

Deterministic, offline verification of the ``accesstech/`` domain
against the R9 charter M020 scope (R9-CORE-001, DEC-0120; the R9
chain root — the current child):

- (a) case_01..case_04 — the declared capability envelopes per
  technology class: well-formed envelopes round-trip canonical-JSON
  byte-identically with content-derived identities (the LOCK-106
  discipline: identities derived from canonical bytes, never wall
  clock, never randomness); every malformed class fails closed with
  the typed error (empty ranges, inverted bounds, contradictory
  windows, tampered identities, malformed technology ids);
- (b) case_05..case_07 — the degradation ladders: composed from the
  accepted ``resilience/`` realization-state vocabulary BY REFERENCE
  (the M008-owned REALIZING/DEGRADED/FAILED/SUPERSEDED kernel — the
  imported-object identity proven, never redefined); deterministic
  stepping; every mode in the accepted vocabulary; no undeclared
  modes (typed rejections);
- (c) case_08..case_10 — the handover characteristic declarations:
  LOCK-108 constraint-set declarations per handover kind consumed
  from the accepted machinery (the imported frozen 12-kind
  vocabulary declared verbatim — the FULL set, weakened declarations
  fail closed), and the REAL accepted machinery driven as the proof
  (a preserving candidate verdict accepted; a weakening candidate
  rejected with the typed kind-citing reason);
- (d) case_11..case_13 — the technology-extension registration
  surface: each of the six accepted M007 reference families
  (backhaul, fivegc, ip, mesh, ran, wifi) registers through the
  public path (envelope + reference adapter composition + capability
  statement over the accepted ``adapters/capability.py`` seam and the
  ``executionplans/`` LOCK-109 bridge with zero contract-core delta)
  and resolves BY REFERENCE — the accepted composition's public
  runtime, identity-preserving (no re-instantiation, no second
  runtime), driving a full typed lifecycle;
- (e) case_14..case_15 — the extension proof: a synthetic future
  envelope (a technology class the 1.1 architecture never named)
  registers through the SAME public path (open-world classified,
  pure data, the full lifecycle green), and the registration path
  fails closed on every cross-surface contradiction (typed
  rejections);
- (f) case_16..case_18 — zero contract-core delta (the AST import
  audit + the git-guarded PR delta shape), the one-way import
  boundary (no accepted authority imports accesstech/), the
  clock/import discipline of the new domain, and determinism (the
  whole fixture surface rebuilt in-process byte-identically; the
  registration material byte-identical across PYTHONHASHSEED
  0/1/42 subprocesses);
- plus case_19 — the evidence-doc honesty (SOFTWARE class only; the
  open physical obligations EVID-002..EVID-008 stay open — never a
  PHYSICAL PASS claim).

The central boundary is exercised throughout:

    ACCESS-TECHNOLOGY ENVELOPE
        = DECLARED DATA around the accepted authorities
        != CONTRACT AUTHORITY (contracts/ stays the sole authority;
          the registration path touches no contract surface)
        != THE ADAPTER MECHANISM (the accepted capability seam owns
          the mechanisms; the registration drives it BY REFERENCE)
        != THE REALIZATION-STATE KERNEL (the M008-owned vocabulary is
          imported and projected onto, never redefined)

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

from contracts import CONSTRAINT_KINDS  # noqa: E402

from replan import REALIZATION_STATES as KERNEL_STATES  # noqa: E402
import resilience.model  # noqa: E402  (the accepted vocabulary surface)

from adapters import (  # noqa: E402
    CAPABILITY_OPERATIONS,
    GenericAdapter,
)
from adapters.capability import Activation  # noqa: E402
from adapters.model import (  # noqa: E402
    AdapterDescriptor,
    AdapterSecurityState,
    ResourceMappingEntry,
    derive_adapter_id,
)
from executionplans import ADAPTER_OPERATIONS  # noqa: E402

import accesstech  # noqa: E402
from accesstech import (  # noqa: E402
    AvailabilityWindow,
    AvailabilityWindows,
    BpsRange,
    CapabilityEnvelope,
    DegradationLadder,
    DegradationMode,
    HandoverCharacteristics,
    JitterMilliRange,
    LatencyMilliRange,
    TechnologyRegistry,
    declare_handover_kind,
    envelope_from_mapping,
    handover_characteristics_from_mapping,
    ladder_from_mapping,
    ladder_step,
    mode_realization_state,
    preserved_constraint_kinds,
    register_access_technology,
    technology_registration_from_mapping,
)
from accesstech.errors import AccessTechError  # noqa: E402

# The M007 battery's public mounting fixtures (the accepted reader
# facades + the real WORK-012 session store; the case_66
# cross-battery import precedent).
import adapter_selftest as ads  # noqa: E402

# The resilience battery's public contract fixtures (the real M002
# contract store at EXECUTION_ACTIVE — the handover-gate drive).
import resilience_selftest as rbs  # noqa: E402

Result = Tuple[str, bool, str]


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

#: The synthetic future access technology (a class the 1.1
#: architecture never named; open-world classified
#: UNKNOWN_BUT_WELL_FORMED — the extension-proof carrier).
_SYNTHETIC_TECH = "access.synthetic.entangled-relay"

#: The declared handover kinds per technology class (declared DATA).
_FAMILY_HANDOVER_KINDS: Dict[str, Tuple[str, ...]] = {
    "backhaul": ("intra-technology", "replacement"),
    "fivegc": ("intra-technology", "cross-technology"),
    "ip": ("intra-technology", "cross-technology"),
    "mesh": ("intra-technology", "cross-technology"),
    "ran": ("intra-technology", "cross-technology"),
    "wifi": ("intra-technology", "cross-technology"),
}

#: The declared capability envelopes per technology class: typed
#: deterministic integer ranges over the four dimensions.
_FAMILY_ENVELOPES: Dict[str, CapabilityEnvelope] = {
    "backhaul": CapabilityEnvelope(
        technology_class="access.ieee.8023",
        bandwidth=BpsRange(100_000_000, 1_000_000_000),
        latency=LatencyMilliRange(1, 20),
        jitter=JitterMilliRange(0, 5),
        availability=AvailabilityWindows(
            (AvailabilityWindow("2026-01-01T00:00:00Z", "2026-12-31T23:59:59Z"),)
        ),
    ),
    "fivegc": CapabilityEnvelope(
        technology_class="access.3gpp.5gc",
        bandwidth=BpsRange(1_000_000, 2_000_000_000),
        latency=LatencyMilliRange(3, 80),
        jitter=JitterMilliRange(0, 15),
        availability=AvailabilityWindows(
            (AvailabilityWindow("2026-01-01T00:00:00Z", "2026-12-31T23:59:59Z"),)
        ),
    ),
    "ip": CapabilityEnvelope(
        technology_class="access.ip.ipv6",
        bandwidth=BpsRange(10_000, 10_000_000_000),
        latency=LatencyMilliRange(1, 150),
        jitter=JitterMilliRange(0, 40),
        availability=AvailabilityWindows(
            (AvailabilityWindow("2026-01-01T00:00:00Z", "2026-06-30T23:59:59Z"),)
        ),
    ),
    "mesh": CapabilityEnvelope(
        technology_class="access.3gpp.iab",
        bandwidth=BpsRange(1_000, 100_000_000),
        latency=LatencyMilliRange(10, 250),
        jitter=JitterMilliRange(0, 50),
        availability=AvailabilityWindows(
            (
                AvailabilityWindow("2026-03-01T00:00:00Z", "2026-03-02T00:00:00Z"),
                AvailabilityWindow("2026-09-01T00:00:00Z", "2026-09-03T00:00:00Z"),
            )
        ),
    ),
    "ran": CapabilityEnvelope(
        technology_class="access.3gpp.nr.imt2020",
        bandwidth=BpsRange(1_000_000, 1_000_000_000),
        latency=LatencyMilliRange(5, 50),
        jitter=JitterMilliRange(0, 20),
        availability=AvailabilityWindows(
            (AvailabilityWindow("2026-01-01T00:00:00Z", "2026-12-31T23:59:59Z"),)
        ),
    ),
    "wifi": CapabilityEnvelope(
        technology_class="access.ieee.80211",
        bandwidth=BpsRange(1_000_000, 600_000_000),
        latency=LatencyMilliRange(2, 100),
        jitter=JitterMilliRange(0, 30),
        availability=AvailabilityWindows(
            (AvailabilityWindow("2026-01-01T00:00:00Z", "2026-12-31T23:59:59Z"),)
        ),
    ),
}

_SYNTHETIC_ENVELOPE = CapabilityEnvelope(
    technology_class=_SYNTHETIC_TECH,
    bandwidth=BpsRange(1_000_000_000, 400_000_000_000),
    latency=LatencyMilliRange(1, 5),
    jitter=JitterMilliRange(0, 2),
    availability=AvailabilityWindows(
        (
            AvailabilityWindow("2027-01-01T00:00:00Z", "2027-01-31T00:00:00Z"),
            AvailabilityWindow("2027-07-01T00:00:00Z", "2027-08-01T00:00:00Z"),
        )
    ),
)

#: The declared degradation ladders per technology class (ordered
#: mode sequences mapped onto the consumed realization vocabulary).
_FAMILY_LADDERS: Dict[str, DegradationLadder] = {
    "backhaul": DegradationLadder(
        technology_class="access.ieee.8023",
        modes=(
            DegradationMode("nominal", "REALIZING"),
            DegradationMode("capacity-75", "DEGRADED"),
            DegradationMode("capacity-50", "DEGRADED"),
            DegradationMode("link-failed", "FAILED"),
        ),
    ),
    "fivegc": DegradationLadder(
        technology_class="access.3gpp.5gc",
        modes=(
            DegradationMode("nominal", "REALIZING"),
            DegradationMode("qos-degraded", "DEGRADED"),
            DegradationMode("session-failed", "FAILED"),
        ),
    ),
    "ip": DegradationLadder(
        technology_class="access.ip.ipv6",
        modes=(
            DegradationMode("nominal", "REALIZING"),
            DegradationMode("route-degraded", "DEGRADED"),
            DegradationMode("flow-constrained", "DEGRADED"),
            DegradationMode("path-failed", "FAILED"),
        ),
    ),
    "mesh": DegradationLadder(
        technology_class="access.3gpp.iab",
        modes=(
            DegradationMode("nominal", "REALIZING"),
            DegradationMode("relay-degraded", "DEGRADED"),
            DegradationMode("queue-constrained", "DEGRADED"),
            DegradationMode("link-failed", "FAILED"),
        ),
    ),
    "ran": DegradationLadder(
        technology_class="access.3gpp.nr.imt2020",
        modes=(
            DegradationMode("nominal", "REALIZING"),
            DegradationMode("coverage-edge", "DEGRADED"),
            DegradationMode("congestion", "DEGRADED"),
            DegradationMode("radio-link-failed", "FAILED"),
        ),
    ),
    "wifi": DegradationLadder(
        technology_class="access.ieee.80211",
        modes=(
            DegradationMode("nominal", "REALIZING"),
            DegradationMode("interference-degraded", "DEGRADED"),
            DegradationMode("association-failed", "FAILED"),
        ),
    ),
}

_SYNTHETIC_LADDER = DegradationLadder(
    technology_class=_SYNTHETIC_TECH,
    modes=(
        DegradationMode("nominal", "REALIZING"),
        DegradationMode("coherence-degraded", "DEGRADED"),
        DegradationMode("channel-failed", "FAILED"),
    ),
)

#: The per-family mapped reserve parameters (the accepted descriptor
#: resource-mapping kinds — the composition's OWN declared units).
_FAMILY_RESERVE: Dict[str, Tuple[str, int, str]] = {
    "backhaul": ("backhaul", 10, "bps"),
    "fivegc": ("bandwidth", 10, "mbps"),
    "ip": ("bandwidth", 10, "mbps"),
    "mesh": ("storage", 1000, "bytes"),
    "ran": ("bandwidth", 10, "mbps"),
    "wifi": ("coverage", 1, "count"),
}

FAMILIES: Tuple[str, ...] = ("backhaul", "fivegc", "ip", "mesh", "ran", "wifi")


def _mount_family(store, family: str):
    """Mount ONE accepted family reference composition through its
    OWN public ``mount_reference`` factory (the reader facades over a
    real WORK-012 store; the accepted M007 pattern)."""
    if family == "mesh":
        from adapters.reference.mesh import mount_reference, STANDARD_MECHANISMS

        return (
            *mount_reference(
                ads._mesh_session_reader(store),
                now=_T0,
                node_ids=(ads._M007_NODE_A, ads._M007_NODE_B, ads._M007_NODE_C),
                path=ads._m007_mesh_path(),
            ),
            STANDARD_MECHANISMS,
        )
    if family == "ran":
        from adapters.reference.ran import mount_reference, STANDARD_MECHANISMS

        return (*mount_reference(now=_T0), STANDARD_MECHANISMS)
    if family == "backhaul":
        from adapters.reference.backhaul import mount_reference, STANDARD_MECHANISMS

        return (
            *mount_reference(ads._backhaul_session_reader(store), now=_T0),
            STANDARD_MECHANISMS,
        )
    if family == "wifi":
        from adapters.reference.wifi import mount_reference, STANDARD_MECHANISMS

        return (
            *mount_reference(
                ads._wifi_session_reader(store),
                ads._wifi_ap_profile_reader(),
                now=_T0,
            ),
            STANDARD_MECHANISMS,
        )
    if family == "fivegc":
        from adapters.reference.fivegc import mount_reference, STANDARD_MECHANISMS

        return (
            *mount_reference(ads._fivegc_session_reader(store), now=_T0),
            STANDARD_MECHANISMS,
        )
    if family == "ip":
        from adapters.reference.ip import mount_reference, STANDARD_MECHANISMS

        return (
            *mount_reference(
                ads._ip_session_reader(store),
                ads._ip_topology_reader(),
                now=_T0,
            ),
            STANDARD_MECHANISMS,
        )
    raise AssertionError("unknown family %r" % family)


def _register_family(store, family: str):
    """Register ONE accepted family through the M020 public path
    (envelope + reference adapter composition + capability statement
    over the accepted seam + LOCK-109 bridge)."""
    impl, descriptor, requirements, mechanisms = _mount_family(store, family)
    return register_access_technology(
        envelope=_FAMILY_ENVELOPES[family],
        ladder=_FAMILY_LADDERS[family],
        handovers=tuple(
            declare_handover_kind(kind)
            for kind in _FAMILY_HANDOVER_KINDS[family]
        ),
        implementation=impl,
        descriptor=descriptor,
        binding_requirements=requirements,
        mechanisms=mechanisms,
        session_store=store,
        now=_T0,
    )


def _register_all(store):
    """Register ALL SIX accepted families into one registry (the
    deterministic registration surface state)."""
    registry = TechnologyRegistry()
    registrations = {}
    for family in FAMILIES:
        registration = _register_family(store, family)
        registry.register(registration)
        registrations[family] = registration
    return registry, registrations


def _synthetic_descriptor() -> AdapterDescriptor:
    """The synthetic future composition's registration descriptor
    (declared data over the accepted descriptor grammar — the
    technology enters as DATA, exactly as the accepted seam
    requires)."""
    return AdapterDescriptor(
        adapter_id=derive_adapter_id(_SYNTHETIC_TECH, "synthetic-reference-0"),
        access_technology_id=_SYNTHETIC_TECH,
        supported_profile_versions=("v1-0-0",),
        capabilities=("capability.profile.synthetic.entangled-relay",),
        resource_mapping=(
            ResourceMappingEntry(
                technology_resource="entangled-channel-capacity",
                kind="bandwidth",
                unit="mbps",
                quantity=100,
                availability="reservation-based",
            ),
        ),
        security_state=AdapterSecurityState(
            profile="baseline",
            credential_slots=("synthetic-technology-credentials",),
            attested=False,
        ),
    )


def _register_synthetic(store):
    """Register the synthetic future technology through the SAME
    public registration path (the extension proof)."""
    descriptor = _synthetic_descriptor()
    return register_access_technology(
        envelope=_SYNTHETIC_ENVELOPE,
        ladder=_SYNTHETIC_LADDER,
        handovers=(
            declare_handover_kind("intra-technology"),
            declare_handover_kind("cross-technology"),
            declare_handover_kind("pass"),
            declare_handover_kind("replacement"),
        ),
        implementation=GenericAdapter(),
        descriptor=descriptor,
        binding_requirements={},
        mechanisms=("synthetic-future-envelope",),
        session_store=store,
        now=_T0,
    )


# ---------------------------------------------------------------------------
# The typed-error probe helper
# ---------------------------------------------------------------------------


def expect_typed(case: str, code: str, action: Callable[[], Any]):
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


# ---------------------------------------------------------------------------
# (a) the capability envelopes
# ---------------------------------------------------------------------------


def case_01_envelope_declaration_round_trip() -> Result:
    name = "case_01_envelope_declaration_round_trip"
    envelopes = dict(_FAMILY_ENVELOPES)
    envelopes["synthetic"] = _SYNTHETIC_ENVELOPE
    if len(envelopes) != 7:
        return fail(name, "fixture count wrong: %d" % len(envelopes))
    ids = set()
    for label, envelope in sorted(envelopes.items()):
        # canonical-JSON round-trip byte-identical + identity stable
        reconstructed = envelope_from_mapping(envelope.to_dict())
        if reconstructed.to_canonical_bytes() != envelope.to_canonical_bytes():
            return fail(name, "%s round-trip is not byte-identical" % label)
        if reconstructed.envelope_id != envelope.envelope_id:
            return fail(name, "%s identity changed across the round-trip" % label)
        if envelope.to_canonical_bytes() != canonical_json_bytes(
            envelope.to_dict()
        ):
            return fail(name, "%s canonical bytes drift" % label)
        ids.add(envelope.envelope_id)
    if len(ids) != 7:
        return fail(name, "envelope identities are not distinct per content")
    # content-derived identity: one dimension changes -> identity changes
    variant = CapabilityEnvelope(
        technology_class="access.ieee.8023",
        bandwidth=BpsRange(200_000_000, 1_000_000_000),
        latency=LatencyMilliRange(1, 20),
        jitter=JitterMilliRange(0, 5),
        availability=AvailabilityWindows(
            (AvailabilityWindow("2026-01-01T00:00:00Z", "2026-12-31T23:59:59Z"),)
        ),
    )
    if variant.envelope_id == _FAMILY_ENVELOPES["backhaul"].envelope_id:
        return fail(name, "identity not content-derived (bandwidth floor ignored)")
    same = CapabilityEnvelope(
        technology_class="access.ieee.8023",
        bandwidth=BpsRange(100_000_000, 1_000_000_000),
        latency=LatencyMilliRange(1, 20),
        jitter=JitterMilliRange(0, 5),
        availability=AvailabilityWindows(
            (AvailabilityWindow("2026-01-01T00:00:00Z", "2026-12-31T23:59:59Z"),)
        ),
    )
    if same.envelope_id != _FAMILY_ENVELOPES["backhaul"].envelope_id:
        return fail(name, "same content produced a different identity")
    return ok(
        name,
        "7 declared envelopes (6 families + synthetic): canonical round-trips "
        "byte-identical; content-derived identities distinct and stable",
    )


def case_02_envelope_malformed_empty_ranges() -> Result:
    name = "case_02_envelope_malformed_empty_ranges"
    probes: List[Tuple[str, str, Callable[[], Any]]] = [
        ("bandwidth ceiling 0", "accesstech-envelope-degenerate",
         lambda: BpsRange(100, 0)),
        ("bandwidth floor 0", "accesstech-envelope-degenerate",
         lambda: BpsRange(0, 100)),
        ("latency zero-width", "accesstech-envelope-degenerate",
         lambda: LatencyMilliRange(0, 0)),
        ("jitter zero-width", "accesstech-envelope-degenerate",
         lambda: JitterMilliRange(0, 0)),
        ("empty availability", "accesstech-envelope-degenerate",
         lambda: AvailabilityWindows(())),
    ]
    for label, code, action in probes:
        outcome = expect_typed(name, code, action)
        if not outcome[1]:
            return fail(name, "%s: %s" % (label, outcome[2]))
    return ok(
        name,
        "5 empty/degenerate range classes rejected with the typed "
        "ENVELOPE_DEGENERATE error (never warnings)",
    )


def case_03_envelope_malformed_inverted_bounds() -> Result:
    name = "case_03_envelope_malformed_inverted_bounds"
    probes: List[Tuple[str, str, Callable[[], Any]]] = [
        ("bandwidth inverted", "accesstech-envelope-inconsistent",
         lambda: BpsRange(500, 100)),
        ("latency inverted", "accesstech-envelope-inconsistent",
         lambda: LatencyMilliRange(30, 10)),
        ("jitter inverted", "accesstech-envelope-inconsistent",
         lambda: JitterMilliRange(30, 10)),
        ("window inverted", "accesstech-envelope-inconsistent",
         lambda: AvailabilityWindow(
             "2026-01-02T00:00:00Z", "2026-01-01T00:00:00Z")),
        ("window zero-width", "accesstech-envelope-inconsistent",
         lambda: AvailabilityWindow(
             "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z")),
    ]
    for label, code, action in probes:
        outcome = expect_typed(name, code, action)
        if not outcome[1]:
            return fail(name, "%s: %s" % (label, outcome[2]))
    return ok(
        name,
        "5 inverted-bound classes rejected with the typed "
        "ENVELOPE_INCONSISTENT error",
    )


def case_04_envelope_malformed_contradictory() -> Result:
    name = "case_04_envelope_malformed_contradictory"
    good = AvailabilityWindow("2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z")
    later = AvailabilityWindow("2026-03-01T00:00:00Z", "2026-04-01T00:00:00Z")
    overlapping = AvailabilityWindow("2026-01-15T00:00:00Z", "2026-03-15T00:00:00Z")
    probes: List[Tuple[str, str, Callable[[], Any]]] = [
        ("disordered windows", "accesstech-envelope-inconsistent",
         lambda: AvailabilityWindows((later, good))),
        ("overlapping windows", "accesstech-envelope-inconsistent",
         lambda: AvailabilityWindows((good, overlapping))),
        ("malformed instant", "accesstech-invalid-input",
         lambda: AvailabilityWindow("2026-01-01 00:00:00", "2026-02-01T00:00:00Z")),
        ("float dimension", "accesstech-invalid-input",
         lambda: BpsRange(100.5, 1000)),  # type: ignore[arg-type]
        ("malformed technology id", "accesstech-invalid-input",
         lambda: CapabilityEnvelope(
             technology_class="not-a-technology-id",
             bandwidth=BpsRange(1, 100),
             latency=LatencyMilliRange(1, 10),
             jitter=JitterMilliRange(0, 5),
             availability=AvailabilityWindows((good,)),
         )),
    ]
    for label, code, action in probes:
        outcome = expect_typed(name, code, action)
        if not outcome[1]:
            return fail(name, "%s: %s" % (label, outcome[2]))
    # tampered identity: the reconstructed envelope's id is recomputed
    tampered = dict(_FAMILY_ENVELOPES["mesh"].to_dict())
    tampered["envelope_id"] = "sha256:" + "0" * 64
    outcome = expect_typed(
        name, "accesstech-identity-mismatch",
        lambda: envelope_from_mapping(tampered),
    )
    if not outcome[1]:
        return fail(name, "identity tampering: %s" % outcome[2])
    # grammar drift at reconstruction
    truncated = dict(_FAMILY_ENVELOPES["mesh"].to_dict())
    del truncated["jitter"]
    outcome = expect_typed(
        name, "accesstech-serialization-invalid",
        lambda: envelope_from_mapping(truncated),
    )
    if not outcome[1]:
        return fail(name, "grammar drift: %s" % outcome[2])
    return ok(
        name,
        "contradictory content, malformed ids/instants/floats, identity "
        "tampering and grammar drift all fail closed with typed errors",
    )


# ---------------------------------------------------------------------------
# (b) the degradation ladders (the consumed realization vocabulary)
# ---------------------------------------------------------------------------


def case_05_ladder_vocabulary_by_reference() -> Result:
    name = "case_05_ladder_vocabulary_by_reference"
    # BY REFERENCE identity proof: the imported vocabulary object IS
    # the accepted resilience surface's object IS the replan kernel.
    if accesstech.REALIZATION_STATES is not resilience.model.REALIZATION_STATES:
        return fail(name, "accesstech vocabulary is not the resilience object")
    if resilience.model.REALIZATION_STATES is not KERNEL_STATES:
        return fail(name, "the resilience object is not the replan kernel")
    if KERNEL_STATES != ("REALIZING", "DEGRADED", "FAILED", "SUPERSEDED"):
        return fail(name, "the kernel drifted from the frozen four-state set")
    if accesstech.REALIZATION_TERMINAL_STATES != ("FAILED", "SUPERSEDED"):
        return fail(name, "the consumed terminal set drifted")
    ladders = dict(_FAMILY_LADDERS)
    ladders["synthetic"] = _SYNTHETIC_LADDER
    for label, ladder in sorted(ladders.items()):
        for mode in ladder.modes:
            if mode.realization_state not in KERNEL_STATES:
                return fail(
                    name,
                    "%s mode %r escapes the consumed vocabulary"
                    % (label, mode.name),
                )
        reconstructed = ladder_from_mapping(ladder.to_dict())
        if reconstructed.to_canonical_bytes() != ladder.to_canonical_bytes():
            return fail(name, "%s ladder round-trip not byte-identical" % label)
        if reconstructed.ladder_id != ladder.ladder_id:
            return fail(name, "%s ladder identity changed on reconstruction" % label)
        if ladder.terminal_mode().realization_state not in (
            "FAILED",
            "SUPERSEDED",
        ):
            return fail(name, "%s terminal rung not terminal" % label)
    return ok(
        name,
        "the realization vocabulary is imported BY REFERENCE (the same "
        "object resilience.model consumed from replan); all 7 ladders map "
        "every mode into the frozen four-state kernel; round-trips "
        "byte-identical",
    )


def case_06_ladder_deterministic_stepping() -> Result:
    name = "case_06_ladder_deterministic_stepping"
    ladders = dict(_FAMILY_LADDERS)
    ladders["synthetic"] = _SYNTHETIC_LADDER
    for label, ladder in sorted(ladders.items()):
        # full deterministic walk: first rung -> terminal rung, one
        # rung at a time, states never leaving the vocabulary
        states_seen: List[str] = []
        mode = ladder.modes[0]
        steps = 0
        while mode.realization_state not in ("FAILED", "SUPERSEDED"):
            mode = ladder_step(ladder, mode.name)
            states_seen.append(mode.realization_state)
            steps += 1
            if steps > len(ladder.modes):
                return fail(name, "%s ladder never terminated" % label)
        if mode.name != ladder.terminal_mode().name:
            return fail(name, "%s walk ended off the terminal rung" % label)
        for state in states_seen:
            if state not in KERNEL_STATES:
                return fail(name, "%s walk left the vocabulary" % label)
        # deterministic re-walk: identical steps from the rebuilt ladder
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
                return fail(name, "%s stepping is not deterministic" % label)
        # the state mapping resolves through the public helper
        if mode_realization_state(ladder, "nominal") != "REALIZING":
            return fail(name, "%s nominal rung does not map to REALIZING" % label)
    return ok(
        name,
        "7 ladders walked to their explicit terminal rungs; stepping "
        "deterministic (rebuilt ladder -> identical steps); every state "
        "inside the consumed vocabulary",
    )


def case_07_ladder_malformed_fail_closed() -> Result:
    name = "case_07_ladder_malformed_fail_closed"
    nominal = DegradationMode("nominal", "REALIZING")
    degraded = DegradationMode("degraded", "DEGRADED")
    failed = DegradationMode("failed", "FAILED")
    superseded = DegradationMode("superseded", "SUPERSEDED")
    recovering = DegradationMode("recovered", "REALIZING")
    probes: List[Tuple[str, str, Callable[[], Any]]] = [
        ("no modes", "accesstech-ladder-illegal",
         lambda: DegradationLadder("access.ieee.8023", ())),
        ("first rung DEGRADED", "accesstech-ladder-illegal",
         lambda: DegradationLadder("access.ieee.8023", (degraded, failed))),
        ("missing terminal rung", "accesstech-ladder-illegal",
         lambda: DegradationLadder("access.ieee.8023", (nominal, degraded))),
        ("rung after terminal", "accesstech-ladder-illegal",
         lambda: DegradationLadder(
             "access.ieee.8023", (nominal, failed, degraded))),
        ("recovery edge inside ladder", "accesstech-ladder-illegal",
         lambda: DegradationLadder(
             "access.ieee.8023", (nominal, degraded, recovering, failed))),
        ("undeclared mode state", "accesstech-vocabulary",
         lambda: DegradationMode("mystery", "RESTORING")),
        ("duplicate mode names", "accesstech-ladder-illegal",
         lambda: DegradationLadder(
             "access.ieee.8023", (nominal, DegradationMode("nominal", "DEGRADED"),
                                  failed))),
        ("malformed mode name", "accesstech-invalid-input",
         lambda: DegradationMode("Nominal", "REALIZING")),
        ("undeclared mode stepped", "accesstech-ladder-illegal",
         lambda: ladder_step(_FAMILY_LADDERS["backhaul"], "unknown-mode")),
        ("terminal mode stepped", "accesstech-ladder-illegal",
         lambda: ladder_step(
             _FAMILY_LADDERS["backhaul"],
             _FAMILY_LADDERS["backhaul"].terminal_mode().name)),
    ]
    for label, code, action in probes:
        outcome = expect_typed(name, code, action)
        if not outcome[1]:
            return fail(name, "%s: %s" % (label, outcome[2]))
    # legal two-rung ladders: REALIZING -> FAILED and the
    # make-before-break replacement shape REALIZING -> SUPERSEDED
    try:
        DegradationLadder("access.ieee.8023", (nominal, failed))
        DegradationLadder("access.ieee.8023", (nominal, superseded))
    except AccessTechError as error:
        return fail(name, "legal short ladder rejected: %s" % error.detail)
    return ok(
        name,
        "10 malformed ladder classes rejected with typed errors (empty, "
        "mis-rooted, unterminated, post-terminal, recovery-edge, "
        "out-of-vocabulary states, duplicates, grammar, undeclared and "
        "terminal stepping); the legal short ladders accepted",
    )


# ---------------------------------------------------------------------------
# (c) the handover characteristic declarations (LOCK-108)
# ---------------------------------------------------------------------------


def case_08_handover_characteristics_lock108() -> Result:
    name = "case_08_handover_characteristics_lock108"
    if accesstech.HANDOVER_KINDS != (
        "intra-technology",
        "cross-technology",
        "pass",
        "replacement",
    ):
        return fail(name, "the declared handover-kind vocabulary drifted")
    declared = preserved_constraint_kinds()
    if tuple(declared) != tuple(sorted(CONSTRAINT_KINDS)):
        return fail(name, "the preserved set is not the imported vocabulary")
    if set(declared) != set(rbs.ALL_KINDS):
        return fail(name, "the preserved set is not the machinery's 12-kind set")
    ids = set()
    for kind in accesstech.HANDOVER_KINDS:
        characteristics = declare_handover_kind(kind)
        if characteristics.preserved_constraint_kinds != declared:
            return fail(name, "%s declares a different preserved set" % kind)
        if characteristics.explicit_reconnect is not True:
            return fail(name, "%s drops the explicit-reconnect discipline" % kind)
        if characteristics.contract_continuity is not True:
            return fail(name, "%s drops contract continuity" % kind)
        reconstructed = handover_characteristics_from_mapping(
            characteristics.to_dict()
        )
        if reconstructed.to_canonical_bytes() != characteristics.to_canonical_bytes():
            return fail(name, "%s round-trip not byte-identical" % kind)
        if reconstructed.characteristics_id != characteristics.characteristics_id:
            return fail(name, "%s identity changed on reconstruction" % kind)
        ids.add(characteristics.characteristics_id)
    if len(ids) != 4:
        return fail(name, "characteristic identities not distinct per kind")
    return ok(
        name,
        "4 handover kinds declared: preserved constraint set == the imported "
        "frozen 12-kind vocabulary verbatim (LOCK-108 full-set semantics); "
        "round-trips byte-identical; identities content-derived per kind",
    )


def case_09_handover_declarations_fail_closed() -> Result:
    name = "case_09_handover_declarations_fail_closed"
    full = preserved_constraint_kinds()
    weakened = tuple(kind for kind in full if kind != "latency-bound")
    unknown = full + ("made-up-kind",)
    probes: List[Tuple[str, str, Callable[[], Any]]] = [
        ("weakened preservation set", "accesstech-handover-illegal",
         lambda: HandoverCharacteristics("pass", weakened, True, True)),
        ("unknown constraint kind", "accesstech-vocabulary",
         lambda: HandoverCharacteristics("pass", unknown, True, True)),
        ("silent reference swap", "accesstech-handover-illegal",
         lambda: HandoverCharacteristics("pass", full, False, True)),
        ("contract-breaking handover", "accesstech-handover-illegal",
         lambda: HandoverCharacteristics("pass", full, True, False)),
        ("unknown handover kind", "accesstech-vocabulary",
         lambda: HandoverCharacteristics("intra-orbit", full, True, True)),
        ("duplicated declared kinds", "accesstech-envelope-inconsistent",
         lambda: HandoverCharacteristics(
             "pass", full + ("latency-bound",), True, True)),
    ]
    for label, code, action in probes:
        outcome = expect_typed(name, code, action)
        if not outcome[1]:
            return fail(name, "%s: %s" % (label, outcome[2]))
    # tampered identity at reconstruction
    tampered = dict(declare_handover_kind("pass").to_dict())
    tampered["characteristics_id"] = "sha256:" + "0" * 64
    outcome = expect_typed(
        name, "accesstech-identity-mismatch",
        lambda: handover_characteristics_from_mapping(tampered),
    )
    if not outcome[1]:
        return fail(name, "identity tampering: %s" % outcome[2])
    return ok(
        name,
        "6 weakened/contradictory declaration classes and identity tampering "
        "rejected with typed errors (LOCK-108 never weakened by declaration)",
    )


def case_10_handover_gate_consumed_by_reference() -> Result:
    name = "case_10_handover_gate_consumed_by_reference"
    # the REAL accepted machinery drives the proof: a preserving
    # candidate verdict is accepted; a weakening candidate is rejected
    # with the typed kind-citing reason; the raising gate fires.
    from resilience import (
        handover_candidate,
        handover_verdict,
        validate_handover_preserves_contract,
    )

    _store, contract = rbs._mature_contract(
        rbs._constraints("latency-bound", "throughput-floor")
    )
    # (a) the full set passes the accepted LOCK-108 gate
    try:
        validate_handover_preserves_contract(
            tuple(contract.hard_constraints), contract
        )
    except Exception as error:  # noqa: BLE001
        return fail(name, "full set rejected by the machinery: %s" % error)
    # (b) a preserving candidate is ACCEPTED by the machinery verdict
    candidate = handover_candidate(
        contract,
        route_decision_id="route:decision-0021",
        path_id="path:handover-0021",
        hard_constraints=contract.hard_constraints,
    )
    verdict = handover_verdict(candidate, contract)
    if not verdict.accepted or verdict.code != "replan-candidate-accepted":
        return fail(name, "preserving candidate not accepted: %s" % verdict.code)
    # (c) a weakening candidate is REJECTED with the typed reason
    weakened = (contract.hard_constraints[0],)
    weak_verdict = handover_verdict(
        handover_candidate(
            contract,
            route_decision_id="route:decision-0022",
            path_id="path:handover-0022",
            hard_constraints=weakened,
        ),
        contract,
    )
    if weak_verdict.accepted or weak_verdict.code != "replan-constraint-weakened":
        return fail(name, "weakening candidate not rejected: %s" % weak_verdict.code)
    if "throughput-floor" not in weak_verdict.detail:
        return fail(name, "the rejection does not cite the weakened kind")
    # (d) the raising gate fires on the weakened set (typed)
    try:
        validate_handover_preserves_contract(weakened, contract)
        return fail(name, "the raising gate accepted a weakened set")
    except Exception as error:  # noqa: BLE001
        code = getattr(error, "code", "")
        if code != "resilience-constraint-weakened":
            return fail(name, "wrong typed rejection: %s" % code)
    # (e) the tie: every kind the machinery can enforce is inside the
    # declared per-kind preservation set (the declarations state the
    # machinery's OWN semantics, never less)
    declared = set(preserved_constraint_kinds())
    enforced = {constraint.kind for constraint in contract.hard_constraints}
    if not enforced <= declared:
        return fail(name, "the machinery enforces kinds outside the declaration")
    if set(rbs.ALL_KINDS) != declared:
        return fail(name, "the declared set is not the full frozen vocabulary")
    return ok(
        name,
        "the accepted machinery driven for real: preserving candidate "
        "accepted, weakening candidate rejected (kind-citing), the raising "
        "gate typed; the declared set covers every enforceable kind",
    )


# ---------------------------------------------------------------------------
# (d) the registration surface — the six accepted families
# ---------------------------------------------------------------------------


def case_11_registration_surface_six_families() -> Result:
    name = "case_11_registration_surface_six_families"
    store, sid = ads._established_session()
    registrations = {}
    for family in FAMILIES:
        registration = _register_family(store, family)
        registrations[family] = registration
    if sorted(registrations) != list(FAMILIES):
        return fail(name, "family registration set wrong")
    ids = set()
    for family in sorted(registrations):
        registration = registrations[family]
        envelope = _FAMILY_ENVELOPES[family]
        ladder = _FAMILY_LADDERS[family]
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
        if registration.mechanisms != tuple(
            _mount_family(store, family)[3]
        ):
            return fail(name, "%s mechanism tags not carried verbatim" % family)
        ids.add(registration.registration_id)
    if len(ids) != 6:
        return fail(name, "registration identities not distinct per family")
    return ok(
        name,
        "all six accepted families registered through the public path: "
        "envelope/ladder/descriptor carried by reference; capability "
        "statement + LOCK-112 tags verbatim; the LOCK-109 bridge frozen "
        "name-equal; identities content-derived and distinct",
    )


def case_12_registration_resolves_by_reference() -> Result:
    name = "case_12_registration_resolves_by_reference"
    store, sid = ads._established_session()
    for family in FAMILIES:
        impl, descriptor, requirements, mechanisms = _mount_family(store, family)
        registration = register_access_technology(
            envelope=_FAMILY_ENVELOPES[family],
            ladder=_FAMILY_LADDERS[family],
            handovers=tuple(
                declare_handover_kind(kind)
                for kind in _FAMILY_HANDOVER_KINDS[family]
            ),
            implementation=impl,
            descriptor=descriptor,
            binding_requirements=requirements,
            mechanisms=mechanisms,
            session_store=store,
            now=_T0,
        )
        # identity-preserving resolution (no re-instantiation, no
        # second runtime): repeated resolution returns the SAME live
        # objects; the descriptor IS the mounted composition's object
        if registration.resolve_capability_adapter() is not registration.capability_adapter:
            return fail(name, "%s resolution re-instantiated the adapter" % family)
        if registration.resolve_capability_adapter() is not registration.resolve_capability_adapter():
            return fail(name, "%s resolution is not stable" % family)
        if registration.resolve_runtime() is not registration.runtime:
            return fail(name, "%s runtime resolution re-instantiated" % family)
        if registration.descriptor is not descriptor:
            return fail(name, "%s descriptor is not the mounted object" % family)
        # the public runtime carries the composition's technology
        view = registration.resolve_capability_adapter().inspect_capabilities(
            now=_NOW
        )
        if not view.ok:
            return fail(name, "%s inspect failed" % family)
        if view.value.adapter_id != descriptor.adapter_id:
            return fail(name, "%s view adapter mismatch" % family)
        if view.value.access_technology_id != _FAMILY_ENVELOPES[family].technology_class:
            return fail(name, "%s view technology mismatch" % family)
        if view.value.lifecycle != "OPEN":
            return fail(name, "%s adapter not OPEN" % family)
        # the canonical record excludes the live objects (declared
        # content only) and round-trips with re-supplied live objects
        content = registration.to_dict()
        for key in ("capability_adapter", "runtime", "descriptor", "envelope", "ladder"):
            if key in content:
                return fail(name, "the canonical record carries %r" % key)
        rebuilt = technology_registration_from_mapping(
            content,
            envelope=_FAMILY_ENVELOPES[family],
            ladder=_FAMILY_LADDERS[family],
            handovers=tuple(
                declare_handover_kind(kind)
                for kind in _FAMILY_HANDOVER_KINDS[family]
            ),
            capability_adapter=registration.capability_adapter,
            runtime=registration.runtime,
            descriptor=descriptor,
            binding_requirements=requirements,
            mechanisms=mechanisms,
        )
        if rebuilt.registration_id != registration.registration_id:
            return fail(name, "%s registration identity changed on rebuild" % family)
        if rebuilt.to_canonical_bytes() != registration.to_canonical_bytes():
            return fail(name, "%s canonical record changed on rebuild" % family)
        if rebuilt.resolve_capability_adapter() is not registration.capability_adapter:
            return fail(name, "%s rebuild lost the live reference" % family)
    return ok(
        name,
        "6 families: resolution identity-preserving (the same live adapter, "
        "runtime and descriptor objects — no re-instantiation); the public "
        "runtime carries the composition's technology; canonical records "
        "round-trip with the live references re-supplied",
    )


def case_13_registration_full_lifecycle_per_family() -> Result:
    name = "case_13_registration_full_lifecycle_per_family"
    store, sid = ads._established_session()
    registry, registrations = _register_all(store)
    for family in sorted(registrations):
        registration = registrations[family]
        capability = registration.resolve_capability_adapter()
        kind, quantity, unit = _FAMILY_RESERVE[family]
        reserved = capability.reserve(
            kind=kind,
            quantity=quantity,
            unit=unit,
            purpose="m020-%s-lifecycle" % family,
            now=_NOW,
        )
        if not reserved.ok:
            return fail(
                name,
                "%s reserve failed: %s"
                % (family, reserved.failure.detail if reserved.failure else "?"),
            )
        activated = capability.activate(
            reservation_id=reserved.value.allocation_id,
            session_id=sid,
            requirements=dict(registration.binding_requirements),
            now=_NOW,
        )
        if not activated.ok:
            return fail(
                name,
                "%s activate failed: %s"
                % (family, activated.failure.detail if activated.failure else "?"),
            )
        # LOCK-110: the boundary returns the canonical typed records
        if not isinstance(activated.value, Activation):
            return fail(name, "%s activation is not the canonical type" % family)
        measured = capability.measure(
            activation_id=activated.value.activation_id, now=_LATER
        )
        if not measured.ok:
            return fail(name, "%s measure failed" % family)
        if family == "wifi":
            # The DISCLOSED accepted family discipline (the M007
            # case_65 disclosure, never papered over): the frozen
            # 12-op Wi-Fi family contract has no AP decommission, so
            # the AP-ref release fails closed DETERMINISTICALLY
            # through the seam (twice, same typed reason); the
            # activation stays visible — the family's own honest
            # behavior surfaced verbatim by the registration surface.
            first_release = capability.release(
                activation_id=activated.value.activation_id, now=_LATER2
            )
            second_release = capability.release(
                activation_id=activated.value.activation_id, now=_LATER2
            )
            if first_release.ok or second_release.ok:
                return fail(
                    name,
                    "wifi release silently succeeded — the frozen family "
                    "discipline was papered over",
                )
            if (
                first_release.failure is None
                or second_release.failure is None
                or first_release.failure.reason != second_release.failure.reason
            ):
                return fail(name, "wifi fail-closed release not deterministic")
            continue
        released = capability.release(
            activation_id=activated.value.activation_id, now=_LATER2
        )
        if not released.ok:
            return fail(name, "%s release failed" % family)
        if capability.activation(activated.value.activation_id).state != "RELEASED":
            return fail(name, "%s activation not terminal RELEASED" % family)
    # the registry resolves the six families deterministically
    if registry.technology_classes() != tuple(
        sorted(_FAMILY_ENVELOPES[f].technology_class for f in FAMILIES)
    ):
        return fail(name, "registry class set wrong: %s" % (registry.technology_classes(),))
    for family in FAMILIES:
        if registry.lookup(_FAMILY_ENVELOPES[family].technology_class) is not registrations[family]:
            return fail(name, "%s registry lookup lost the registration object" % family)
    return ok(
        name,
        "5 families: full typed lifecycle (reserve -> activate -> measure -> "
        "release) green; wifi disclosed (the accepted family's AP-release "
        "fail-closed discipline, the M007 case_65 shape, deterministic "
        "through the seam); the registry resolves all six (sorted, "
        "identity-preserving)",
    )


# ---------------------------------------------------------------------------
# (e) the extension proof — the synthetic future technology
# ---------------------------------------------------------------------------


def case_14_registration_extension_proof_future() -> Result:
    name = "case_14_registration_extension_proof_future"
    from adapters import AccessTechnologyClass, classify_access_technology_id

    if classify_access_technology_id(_SYNTHETIC_TECH) != AccessTechnologyClass.UNKNOWN_BUT_WELL_FORMED:
        return fail(name, "the synthetic class is not open-world classified")
    store, sid = ads._established_session()
    # the SAME public registration path (the identical function object
    # the six families drove — no second surface)
    registration = _register_synthetic(store)
    if registration.technology_class != _SYNTHETIC_TECH:
        return fail(name, "synthetic technology class mismatch")
    if registration.registration_id == _register_family(
        store, "backhaul"
    ).registration_id:
        return fail(name, "synthetic identity collided with a family")
    # the full lifecycle through the seam on the future technology
    capability = registration.resolve_capability_adapter()
    reserved = capability.reserve(
        kind="bandwidth", quantity=10, unit="mbps",
        purpose="m020-extension-proof", now=_NOW,
    )
    if not reserved.ok:
        return fail(name, "synthetic reserve failed")
    activated = capability.activate(
        reservation_id=reserved.value.allocation_id,
        session_id=sid,
        requirements={},
        now=_NOW,
    )
    if not activated.ok:
        return fail(
            name,
            "synthetic activate failed: %s"
            % (activated.failure.detail if activated.failure else "?"),
        )
    measured = capability.measure(
        activation_id=activated.value.activation_id, now=_LATER
    )
    if not measured.ok:
        return fail(name, "synthetic measure failed")
    released = capability.release(
        activation_id=activated.value.activation_id, now=_LATER2
    )
    if not released.ok:
        return fail(name, "synthetic release failed")
    # the future technology composes into the same registry
    registry = TechnologyRegistry()
    registry.register(registration)
    if registry.lookup(_SYNTHETIC_TECH) is not registration:
        return fail(name, "synthetic lookup failed")
    # the registration path code carries NO technology branching (the
    # technology enters as DATA — the M007 case_09 discipline)
    forbidden = (
        "3gpp", "80211", "8023", "imt2020", "imt2030", "wifi", "wi-fi",
        "nr", "lte", "5g", "6g", "bluetooth", "microwave", "satellite",
        "entangled", "synthetic",
    )
    for path in sorted((REPO_ROOT / "accesstech").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
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
        for token in forbidden:
            for code_name in names:
                if token in code_name.lower():
                    return fail(
                        name,
                        "%s: code name %r embeds %r (no tech branching)"
                        % (path.name, code_name, token),
                    )
    return ok(
        name,
        "the synthetic future class (never named by the 1.1 architecture) "
        "registered through the SAME public path: full lifecycle green, "
        "registry lookup resolves, and the registration code branches on "
        "no technology name (pure data)",
    )


def case_15_registration_fail_closed() -> Result:
    name = "case_15_registration_fail_closed"
    store, sid = ads._established_session()
    impl, descriptor, requirements, mechanisms = _mount_family(store, "backhaul")
    envelope = _FAMILY_ENVELOPES["backhaul"]
    ladder = _FAMILY_LADDERS["backhaul"]
    handovers = (declare_handover_kind("intra-technology"),)
    base = dict(
        envelope=envelope,
        ladder=ladder,
        handovers=handovers,
        implementation=impl,
        descriptor=descriptor,
        binding_requirements=requirements,
        mechanisms=mechanisms,
        session_store=store,
        now=_T0,
    )
    wrong_class_envelope = CapabilityEnvelope(
        technology_class=_SYNTHETIC_TECH,
        bandwidth=BpsRange(1_000_000_000, 400_000_000_000),
        latency=LatencyMilliRange(1, 5),
        jitter=JitterMilliRange(0, 2),
        availability=AvailabilityWindows(
            (AvailabilityWindow("2027-01-01T00:00:00Z", "2027-02-01T00:00:00Z"),)
        ),
    )
    probes: List[Tuple[str, str, Callable[[], Any]]] = [
        ("envelope/descriptor mismatch", "accesstech-registration-rejected",
         lambda: register_access_technology(
             **{**base, "envelope": wrong_class_envelope})),
        ("ladder class mismatch", "accesstech-registration-rejected",
         lambda: register_access_technology(
             **{**base, "ladder": _SYNTHETIC_LADDER})),
        ("no handover declarations", "accesstech-registration-rejected",
         lambda: register_access_technology(**{**base, "handovers": ()})),
        ("duplicate handover kinds", "accesstech-registration-rejected",
         lambda: register_access_technology(
             **{**base, "handovers": (
                 declare_handover_kind("intra-technology"),
                 declare_handover_kind("intra-technology"),
             )})),
        ("no mechanism tags", "accesstech-registration-rejected",
         lambda: register_access_technology(**{**base, "mechanisms": ()})),
        ("malformed registration instant", "accesstech-invalid-input",
         lambda: register_access_technology(
             **{**base, "now": "2026-06-01 12:00:00"})),
        ("non-contract implementation", "accesstech-registration-rejected",
         lambda: register_access_technology(**{**base, "implementation": object()})),
    ]
    for label, code, action in probes:
        outcome = expect_typed(name, code, action)
        if not outcome[1]:
            return fail(name, "%s: %s" % (label, outcome[2]))
    # the registry discipline: duplicate classes and unknown lookups
    registration = register_access_technology(**base)
    registry = TechnologyRegistry()
    registry.register(registration)
    duplicate = expect_typed(
        name, "accesstech-registration-rejected",
        lambda: registry.register(registration),
    )
    if not duplicate[1]:
        return fail(name, "duplicate registration: %s" % duplicate[2])
    unknown = expect_typed(
        name, "accesstech-registration-rejected",
        lambda: registry.lookup("access.unknown.absent"),
    )
    if not unknown[1]:
        return fail(name, "unknown lookup: %s" % unknown[2])
    return ok(
        name,
        "7 registration-path contradictions plus registry duplicate/unknown "
        "discipline all fail closed with typed rejections (never warnings)",
    )


# ---------------------------------------------------------------------------
# (f) zero contract-core delta, one-way imports, determinism
# ---------------------------------------------------------------------------


def _origin_main_available() -> bool:
    probe = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/main"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    return probe.returncode == 0


def case_16_zero_contract_core_delta() -> Result:
    name = "case_16_zero_contract_core_delta"
    # (a) the AST import audit: the ONLY name imported from contracts
    # anywhere in accesstech/ is CONSTRAINT_KINDS — the frozen
    # read-only vocabulary constant (no ContractStore, no commands,
    # no mutation surface; the registration path composes AROUND the
    # authority and never touches it)
    imported_from_contracts: set = set()
    for path in sorted((REPO_ROOT / "accesstech").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                top = node.module.split(".")[0]
                if top == "contracts":
                    imported_from_contracts.update(
                        alias.name for alias in node.names
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] == "contracts":
                        imported_from_contracts.add("*")
    if imported_from_contracts - {"CONSTRAINT_KINDS"}:
        return fail(
            name,
            "accesstech/ imports contract surfaces beyond the frozen "
            "vocabulary: %s" % sorted(imported_from_contracts),
        )
    # (b) the git-guarded PR delta: zero contracts/ files touched; the
    # delta confined to the authorization scope
    if not _origin_main_available():
        return ok(
            name,
            "AST audit green (contracts imports == CONSTRAINT_KINDS only); "
            "git delta check skipped (no origin/main ref; the CI provenance "
            "step enforces scope)",
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
            problems.append("the registration delta touches the contract core: %s" % path)
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
        "AST audit green (the only contracts import is the frozen "
        "CONSTRAINT_KINDS vocabulary); the PR delta (%d file(s)) touches no "
        "contract-core file and stays inside the R9-CORE-001 scope" % len(delta),
    )


def case_17_one_way_imports_and_clock_discipline() -> Result:
    name = "case_17_one_way_imports_and_clock_discipline"
    # (a) the one-way boundary: no accepted authority references
    # accesstech in CODE (AST tokens, not docstrings)
    authorities = (
        "contracts", "replan", "executionplans", "evidence", "assurance",
        "offers", "eligibility", "policy", "adapters", "usage", "commercial",
        "allocation", "payment", "sharenet", "roamlink", "comos",
        "developerapi", "federation", "identity", "upgrade", "scale",
        "client", "resilience", "localfirst", "recovery", "credentials",
    )
    problems: List[str] = []

    def _references_accesstech(source: str) -> bool:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return False
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "accesstech":
                return True
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                if node.value.id == "accesstech":
                    return True
            if isinstance(node, ast.ImportFrom) and node.module and "accesstech" in node.module:
                return True
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] == "accesstech":
                        return True
        return False

    for package in authorities:
        package_dir = REPO_ROOT / package
        if not package_dir.is_dir():
            continue
        for path in sorted(package_dir.glob("*.py")):
            source = path.read_text(encoding="utf-8")
            if "accesstech" in source and _references_accesstech(source):
                problems.append(
                    "%s references accesstech (one-way boundary)" % path.name
                )
    # (b) the new domain's own clock/import discipline
    allowed = {
        "__future__", "hashlib", "re", "dataclasses", "typing",
        "protocol", "contracts", "replan", "resilience", "adapters",
        "executionplans",
    }
    legacy = (
        "imt", "transport", "topology", "networkpath", "sessions",
        "mobility", "multipath", "edge", "appliance", "mobile",
        "management", "simulator", "resources", "services",
    )
    tree_modules: set = set()
    for path in sorted((REPO_ROOT / "accesstech").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        for forbidden in (
            "datetime.now", "time.time", "utcnow", "uuid", "random.",
            "socket.", "requests.", "urlopen", "time.monotonic",
            "time.sleep",
        ):
            if forbidden in source:
                problems.append("%s carries %r" % (path.name, forbidden))
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                tree_modules.update(
                    alias.name.split(".")[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                tree_modules.add(node.module.split(".")[0])
    unexpected = sorted(tree_modules - allowed)
    if unexpected:
        problems.append("accesstech/ imports %s" % unexpected)
    for package in legacy:
        if package in tree_modules:
            problems.append("accesstech/ imports the legacy %s/ package" % package)
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "no accepted authority imports accesstech/ (one-way boundary over "
        "%d packages); the domain itself is clock/random/network-free with "
        "imports confined to stdlib + protocol + the accepted authorities; "
        "the legacy reservoir un-imported" % len(authorities),
    )


def case_18_determinism_byte_identical() -> Result:
    name = "case_18_determinism_byte_identical"
    # (a) in-process rebuild: the whole fixture surface rebuilt from
    # scratch -> byte-identical canonical bytes and identities
    store, _sid = ads._established_session()
    registry_first, registrations_first = _register_all(store)
    synthetic_first = _register_synthetic(store)
    registry_second, registrations_second = _register_all(store)
    synthetic_second = _register_synthetic(store)
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
    if synthetic_first.to_canonical_bytes() != synthetic_second.to_canonical_bytes():
        return fail(name, "synthetic registration bytes differ on rebuild")
    if registry_first.technology_classes() != registry_second.technology_classes():
        return fail(name, "registry order differs on rebuild")

    # (b) cross-process: the registration material (all six families
    # + the synthetic extension) built in PYTHONHASHSEED 0/1/42
    # subprocesses -> byte-identical digests
    probe = r"""
import sys
sys.path.insert(0, %r)
sys.path.insert(0, %r)
import hashlib
import adapter_selftest as ads
import accesstech_selftest as m020
store, sid = ads._established_session()
registry, registrations = m020._register_all(store)
synthetic = m020._register_synthetic(store)
material = b"".join(
    registrations[family].to_canonical_bytes() for family in m020.FAMILIES
) + synthetic.to_canonical_bytes()
print(hashlib.sha256(material).hexdigest())
print(" ".join(r[6:] for r in (
    registrations[f].registration_id for f in m020.FAMILIES
)))
print(synthetic.registration_id[7:])
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
            "registration material differs across PYTHONHASHSEED "
            "subprocesses (%d distinct outputs)" % len(outputs),
        )
    return ok(
        name,
        "in-process rebuild byte-identical (registrations, envelopes, "
        "ladders, registry order); the full registration material "
        "byte-identical across PYTHONHASHSEED 0/1/42 subprocesses",
    )


def case_19_evidence_doc_honest() -> Result:
    name = "case_19_evidence_doc_honest"
    path = REPO_ROOT / "docs" / "M020-evidence.md"
    if not path.exists():
        return fail(name, "docs/M020-evidence.md is missing")
    text = path.read_text(encoding="utf-8")
    problems: List[str] = []
    if "SOFTWARE" not in text:
        problems.append("the evidence class is not disclosed")
    if "M020" not in text:
        problems.append("the evidence does not name M020")
    if "LOCK-108" not in text:
        problems.append("the LOCK-108 mapping is not disclosed")
    if "LOCK-110" not in text:
        problems.append("the LOCK-110 mapping is not disclosed")
    if "LOCK-109" not in text:
        problems.append("the LOCK-109 mapping is not disclosed")
    if "EVID-002" not in text:
        problems.append("the open physical evidence obligations are not disclosed")
    if "by reference" not in text.lower():
        problems.append("the by-reference composition is not disclosed")
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
        "SOFTWARE class, by-reference composition, the lock mapping and "
        "the open physical obligations disclosed; no affirmative physical "
        "claims",
    )


# ===========================================================================
# Main
# ===========================================================================


def main() -> int:
    results: List[Result] = []
    results.append(case_01_envelope_declaration_round_trip())
    results.append(case_02_envelope_malformed_empty_ranges())
    results.append(case_03_envelope_malformed_inverted_bounds())
    results.append(case_04_envelope_malformed_contradictory())
    results.append(case_05_ladder_vocabulary_by_reference())
    results.append(case_06_ladder_deterministic_stepping())
    results.append(case_07_ladder_malformed_fail_closed())
    results.append(case_08_handover_characteristics_lock108())
    results.append(case_09_handover_declarations_fail_closed())
    results.append(case_10_handover_gate_consumed_by_reference())
    results.append(case_11_registration_surface_six_families())
    results.append(case_12_registration_resolves_by_reference())
    results.append(case_13_registration_full_lifecycle_per_family())
    results.append(case_14_registration_extension_proof_future())
    results.append(case_15_registration_fail_closed())
    results.append(case_16_zero_contract_core_delta())
    results.append(case_17_one_way_imports_and_clock_discipline())
    results.append(case_18_determinism_byte_identical())
    results.append(case_19_evidence_doc_honest())

    print("ADCOS accesstech self-test (M020 — Access Technology Capability Envelope)")
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
