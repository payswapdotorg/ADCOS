#!/usr/bin/env python3
"""ADCOS non-terrestrial access adapter self-test (M022).

Deterministic, offline verification of the M022 delivery — the
``adapters/reference/satellite.py`` reference compositions, the
``accesstech/satellite.py`` family declarations and their composition
through the accepted surfaces — against the R9 charter M022 scope
(R9-CORE-001, DEC-0122; the chain child whose M020 and M021
dependencies are satisfied by the DEC-0121/DEC-0122 acceptances):

- (a) case_01..case_05 — the non-terrestrial family declarations: the
  four capability envelopes (GSO ``access.satellite.gso``, NGSO
  ``access.satellite.ngso``, LEO ``access.satellite.leo``, mesh/IAB
  ``access.3gpp.iab`` — the accepted mesh family's own KNOWN registry
  entry) round-trip canonical-JSON byte-identically with
  content-derived identities (LOCK-106); DETERMINISTIC COVERAGE
  WINDOWS as declared availability intervals (the GSO standing
  window, the NGSO/LEO pass windows, the mesh/IAB DTN-bridged
  standing window — injected instants only, the wall-clock-shaped
  values typed-rejected, the pass-shape discipline typed);
  PROPAGATION-DELAY ENVELOPES as typed declared ranges (the latency
  dimension, with the typed margin discipline);
  the degradation ladders as PROPAGATION-AWARE DECLARED MARGIN STEPS
  (margin rungs on the accepted realization-state kernel, every step
  an evidence-visible transition, deterministic walking, typed
  rejections); and the declared PASS SCHEDULES (the NGSO/LEO
  pass-handover geometry as canonical declared data);
- (b) case_06..case_07 — the four families registered through the
  ACCEPTED M020 extension surface (envelope + reference adapter
  composition + capability statement over the accepted
  ``adapters/capability.py`` seam and the ``executionplans/``
  LOCK-109 bridge, zero contract-core delta) and resolving BY
  REFERENCE to the accepted mesh family runtime (identity-preserving
  live objects — no re-instantiation, no second runtime);
- (c) case_08..case_09 — the nine WORK-016 operations in
  deterministic reserve/activate/measure flows (the frozen disclosed
  translation map driven end-to-end: capabilities, allocate,
  bind_session, observe, unbind_session, release, health — with the
  registration's open_adapter drive) INCLUDING the deterministic
  re-bind translation for mid-session reconfiguration (the same
  session, the preserved reservation, the previous binding released
  first, the new binding created — typed Reconfiguration records);
- (d) case_10 — the NGSO PASS-HANDOVER GEOMETRY through the accepted
  ``resilience/`` handover machinery: every declared pass transition
  an EXPLICIT RECORDED RECONNECT naming the OLD and the NEW
  references (the WORK-012 discipline — the reconnect pair, the
  journal, the evidence records), LOCK-108 VERBATIM CONSTRAINT-SET
  EQUALITY across every pass handover (the constraint fingerprint ==
  the contract's own; a weakened candidate rejected with the typed
  kind-citing reason; an impossible handover landing the EXPLICIT
  FAILED state, never a silent swap), and the LEO sibling transition
  driven identically;
- (e) case_11 — the MESH/IAB EXTENSION composing the accepted
  ``adapters/mesh/`` family runtime BY REFERENCE: the accepted
  SidelinkRelayEngine (the sidelink relay implementation) with the
  declared satellite DTN store-and-forward limits, the
  enqueue/forward/partition-defer/recover-deliver drill and the
  deterministic TTL expiry sweep — all through the family's OWN
  public APIs (never re-implemented);
- (f) case_12..case_13 — LOCK-110 provider-SDK isolation (every 1.1
  operation returns the canonical typed provider-neutral records; no
  opaque family technology reference crosses into any record's
  canonical bytes; the LOCK-112 mechanism tags are citation DATA; no
  technology branching in the composition code) and the typed
  fail-closed matrix (capacity exhaustion, identity smuggling,
  unknown routes/keys, unmapped kinds, unknown
  reservations/activations, terminal-state discipline — deterministic
  typed rejections, never warnings);
- (g) case_14..case_17 — the one-way import audit (no accepted
  authority imports the new modules; the new modules' own import
  discipline — adapters/reference/satellite.py never imports
  accesstech, accesstech/satellite.py imports only the accepted
  accesstech surface + stdlib + protocol; the clock/random/network
  discipline), the zero contract-core delta + authorization-scope
  audit, determinism (in-process rebuild and the full PYTHONHASHSEED
  0/1/42 cross-process byte-identity), and the evidence-doc honesty
  (SOFTWARE class only; EVID-002..EVID-008 stay open — never a
  PHYSICAL PASS claim).

The central boundary is exercised throughout:

    NON-TERRESTRIAL ACCESS FAMILY
        = a reference adapter composition on the M020 envelope
          (declared data around the accepted authorities)
        = the accepted mesh family runtime composed BY REFERENCE
          through the accepted adapters/capability.py seam
          (LOCK-112: the families model the standard mechanisms —
          3GPP NTN / IAB / sidelink relay / DTN store-and-forward;
          LOCK-110: provider-SDK types never enter the core)
        = the NGSO pass handovers composed through the accepted
          resilience/ machinery (LOCK-108 verbatim constraint
          preservation; WORK-012 explicit recorded reconnects)
        != CONTRACT AUTHORITY (contracts/ stays the sole authority)
        != GLOBAL TOPOLOGY (LOCK-105: the pass schedules and relay
          chains are declared data bounded by their own declaration)

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
from typing import Any, Callable, Dict, List, Optional, Tuple

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
    handover_characteristics_from_mapping,
    ladder_from_mapping,
    ladder_step,
    mode_realization_state,
    preserved_constraint_kinds,
    register_access_technology,
    technology_registration_from_mapping,
)
from accesstech.errors import AccessTechError  # noqa: E402
from accesstech import satellite as sat  # noqa: E402  (the M022 declarations)

from adapters.reference import satellite as satref  # noqa: E402  (the M022 compositions)

# The resilience-side handover machinery the NGSO pass-handover
# geometry composes through (the ACCEPTED M015 surface, BY REFERENCE).
from resilience import (  # noqa: E402
    ResilienceError,
    ResilienceReason,
    RuntimeStore,
    handover_candidate,
    handover_verdict,
    perform_handover,
    validate_handover_preserves_contract,
)
from replan import verify_decision_preserves_contract  # noqa: E402

# The contracts-side fixtures the handover drive needs (the accepted
# M002 authority — the contract whose hard constraints every pass
# handover preserves VERBATIM).
from contracts import (  # noqa: E402
    ActivateContract,
    BeneficiaryScope,
    ConnectivityPrincipal,
    ContractStore,
    CreateContract,
    HardConstraint,
    OpaqueReference,
    Provenance,
    RecordExecutionActivation,
    SelectOffers,
    TerminationRules,
    ValidityInterval,
)

# The routing-side Path fixtures the relay routes register (the
# ordinary WORK-011 objects the accepted mesh composition consumes
# as DATA).
from routing import (  # noqa: E402
    LinkMetrics,
    Path,
    aggregate_link_metrics,
    derive_path_id,
)

from adapters.mesh.errors import MeshError, MeshReasonCode  # noqa: E402
from adapters.mesh.model import BundleState, ForwardVerdict  # noqa: E402

# The M007 battery's public mounting fixtures (the accepted reader
# facades + the real WORK-012 session store; the case_66
# cross-battery import precedent — the M020/M021 batteries' own
# pattern).
import adapter_selftest as ads  # noqa: E402

Result = Tuple[str, bool, str]

FAMILIES: Tuple[str, ...] = ("gso", "ngso", "leo", "mesh-iab")


def ok(name: str, detail: str = "") -> Result:
    return (name, True, detail)


def fail(name: str, detail: str) -> Result:
    return (name, False, detail)


# ---------------------------------------------------------------------------
# Deterministic fixtures (injected instants only)
# ---------------------------------------------------------------------------

_T0 = "2026-06-01T00:00:00Z"
_NOW = "2026-06-01T07:00:00Z"
_LATER = "2026-06-01T08:30:00Z"
_LATER2 = "2026-06-01T09:00:00Z"

#: The WORK-004 node fixtures of the relay chains (test-profile
#: NodeIDs — the composition's caller-supplied chain endpoints).
_NODE_TERMINAL = "adcos:node:test.profile.v1:" + "a" * 64
_NODE_RELAY = "adcos:node:test.profile.v1:" + "b" * 64
_NODE_GATEWAY = "adcos:node:test.profile.v1:" + "c" * 64
_NODE_SAT_1 = "adcos:node:test.profile.v1:" + "d" * 64
_NODE_SAT_2 = "adcos:node:test.profile.v1:" + "e" * 64
_NODE_LEO = "adcos:node:test.profile.v1:" + "f" * 64

#: The declared relay-chain geometry per family (the GSO bent-pipe
#: two legs; the NGSO constellation three legs — the inter-satellite
#: cross-link; the LEO and mesh/IAB two legs).
_FAMILY_CHAINS: Dict[str, Tuple[str, ...]] = {
    "gso": (_NODE_TERMINAL, _NODE_RELAY, _NODE_GATEWAY),
    "ngso": (_NODE_TERMINAL, _NODE_SAT_1, _NODE_SAT_2, _NODE_GATEWAY),
    "leo": (_NODE_TERMINAL, _NODE_LEO, _NODE_GATEWAY),
    "mesh-iab": (_NODE_TERMINAL, _NODE_RELAY, _NODE_GATEWAY),
}

#: The per-family chain leg latency (the deterministic fixture
#: metrics — the PROPAGATION declarations live on the envelopes).
_FAMILY_LEG_LATENCY: Dict[str, int] = {
    "gso": 250,
    "ngso": 90,
    "leo": 30,
    "mesh-iab": 50,
}

#: The per-family LOCK-112 mechanism tags (citation DATA).
_FAMILY_MECHANISMS: Dict[str, Tuple[str, ...]] = {
    "gso": satref.GSO_MECHANISMS,
    "ngso": satref.NGSO_MECHANISMS,
    "leo": satref.LEO_MECHANISMS,
    "mesh-iab": satref.MESH_IAB_MECHANISMS,
}

#: The per-family reserve quantity (integer byte base units — the
#: mapped ``storage`` kind).
_FAMILY_RESERVE: Dict[str, int] = {
    "gso": 10_000_000,
    "ngso": 10_000_000,
    "leo": 5_000_000,
    "mesh-iab": 5_000_000,
}


def _satellite_path(nodes: Tuple[str, ...], leg_latency_ms: int) -> Any:
    """The ordinary WORK-011 ``Path`` the family's route registers
    (deterministic: fixed nodes, fixed hop ids in the accepted
    ``link:<upstream>:<downstream>`` convention, fixed leg metrics —
    the M007 ``_m007_mesh_path`` pattern)."""
    hops = tuple(
        "link:%s:%s" % (nodes[i], nodes[i + 1])
        for i in range(len(nodes) - 1)
    )
    metrics = aggregate_link_metrics(
        tuple(
            LinkMetrics(
                latency_ms=leg_latency_ms,
                loss_basis_points=0,
                capacity_bps=1_000_000,
                energy_cost_millijoules=100,
                confidence_basis_points=10_000,
                observed_at=_T0,
                freshness_until="2026-06-02T00:00:00Z",
            )
            for _ in hops
        )
    )
    return Path(
        path_id=derive_path_id(nodes[0], nodes[-1], hops, nodes),
        source_node_id=nodes[0],
        destination_node_id=nodes[-1],
        hops=hops,
        nodes=nodes,
        metrics=metrics,
        feasible=True,
    )


def _mount_family(store, family: str):
    """Mount ONE non-terrestrial family reference composition through
    its own public ``mount_*`` factory (the reader facade over a real
    WORK-012 store; the accepted M007/M020/M021 composition-root
    pattern)."""
    reader = ads._mesh_session_reader(store)
    nodes = _FAMILY_CHAINS[family]
    path = _satellite_path(nodes, _FAMILY_LEG_LATENCY[family])
    if family == "gso":
        return (*satref.mount_gso_reference(
            reader, now=_T0, node_ids=nodes, path=path), {})
    if family == "ngso":
        return (*satref.mount_ngso_reference(
            reader, now=_T0, node_ids=nodes, path=path), {})
    if family == "leo":
        return (*satref.mount_leo_reference(
            reader, now=_T0, node_ids=nodes, path=path), {})
    if family == "mesh-iab":
        return satref.mount_mesh_iab_reference(
            reader, now=_T0, node_ids=nodes, path=path
        )
    raise AssertionError("unknown family %r" % family)


def _register_family(store, family: str):
    """Register ONE non-terrestrial family through the accepted M020
    public path (envelope + reference adapter composition + capability
    statement over the accepted seam + LOCK-109 bridge)."""
    bridge, descriptor, requirements, wiring = _mount_family(store, family)
    registration = register_access_technology(
        envelope=sat.NON_TERRESTRIAL_ENVELOPES[family],
        ladder=sat.NON_TERRESTRIAL_LADDERS[family],
        handovers=sat.non_terrestrial_handover_declarations(family),
        implementation=bridge,
        descriptor=descriptor,
        binding_requirements=requirements,
        mechanisms=_FAMILY_MECHANISMS[family],
        session_store=store,
        now=_T0,
    )
    return registration, wiring


def _register_all(store):
    """Register ALL FOUR non-terrestrial families into one registry
    (the deterministic registration surface state)."""
    registry = TechnologyRegistry()
    registrations: Dict[str, Any] = {}
    wirings: Dict[str, Dict[str, Any]] = {}
    for family in FAMILIES:
        registration, wiring = _register_family(store, family)
        registry.register(registration)
        registrations[family] = registration
        wirings[family] = wiring
    return registry, registrations, wirings


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
        kind="storage",
        quantity=_FAMILY_RESERVE[family],
        unit="bytes",
        purpose="m022-%s-lifecycle" % family,
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
    route coordinate plus a refreshed hop budget (the mesh/IAB relay
    steering data — the disclosed caller-supplied wiring keys)."""
    requirements = dict(registration.binding_requirements)
    requirements["hop_budget"] = 8
    return requirements


# ---------------------------------------------------------------------------
# The resilience-side pass-handover fixtures (the accepted machinery)
# ---------------------------------------------------------------------------

_CONTRACT_CREATED = "2026-05-30T10:00:00Z"
_CONTRACT_SELECTED = "2026-05-30T10:05:00Z"
_CONTRACT_T0 = "2026-06-01T00:00:00Z"
_CONTRACT_T_END = "2026-06-30T00:00:00Z"

#: The runtime-side instants (inside the owning contract's validity
#: window; the initial realization activates as the first declared
#: pass opens).
_R_CREATE = "2026-06-01T07:50:00Z"
_R_ACTIVATE = "2026-06-01T08:00:00Z"

_BATTERY_ISSUER = "satellite:m022-battery"

_OFFER_A = OpaqueReference(
    ref_kind="offer", value="offer:orbit-one-1",
    provenance=Provenance(issuer="prov:orbit-one"),
)
_OFFER_B = OpaqueReference(
    ref_kind="offer", value="offer:orbit-one-mesh-1",
    provenance=Provenance(issuer="prov:orbit-one"),
)
_OFFER_C = OpaqueReference(
    ref_kind="offer", value="offer:orbit-one-failover-1",
    provenance=Provenance(issuer="prov:orbit-one"),
)


def _prov(issuer: str, *refs: str) -> Provenance:
    return Provenance(issuer=issuer, decision_refs=tuple(refs))


def _pass_contract_constraints() -> Tuple[HardConstraint, ...]:
    """The satellite pass contract's hard constraints (deterministic
    fixtures: the declared service latency budget as the latency
    bound — 400 ms, the declared budget — plus the availability
    floor)."""
    return (
        HardConstraint(
            kind="latency-bound",
            params={"max_ms": sat.SERVICE_LATENCY_BUDGET_MS},
            provenance=_prov("prov:orbit-one"),
        ),
        HardConstraint(
            kind="availability-floor",
            params={"nine": "three"},
            provenance=_prov("prov:orbit-one"),
        ),
    )


def _create_command(
    constraints: Tuple[HardConstraint, ...]
) -> CreateContract:
    return CreateContract(
        principal=ConnectivityPrincipal(
            principal_kind="APPLICATION", principal_ref="app:orbit-gw-01"
        ),
        beneficiaries=(
            BeneficiaryScope(
                beneficiary_kind="DEVICE", beneficiary_ref="dev:term-4b1c"
            ),
        ),
        requirements=(
            OpaqueReference(
                ref_kind="intent-requirements",
                value="intent:ntn-pass-01",
                provenance=_prov("arch:satellite"),
            ),
        ),
        hard_constraints=constraints,
        validity=ValidityInterval(
            not_before=_CONTRACT_T0, not_after=_CONTRACT_T_END
        ),
        service_properties=(
            OpaqueReference(
                ref_kind="service-property",
                value="prop:committed-ntn-1",
                provenance=_prov("prov:orbit-one"),
            ),
        ),
        usage_pricing_terms=OpaqueReference(
            ref_kind="usage-pricing-terms",
            value="terms:comm-ntn-9",
            provenance=_prov("comm:ops"),
        ),
        assurance_obligations=(
            OpaqueReference(
                ref_kind="assurance-obligation", value="oblig:evid-ntn-4"
            ),
        ),
        execution_scope=(
            OpaqueReference(
                ref_kind="execution-scope", value="scope:exec-ntn"
            ),
        ),
        termination=TerminationRules(
            conditions=("principal-requested", "constraint-violated"),
            compensation=OpaqueReference(
                ref_kind="compensation",
                value="comp:rule-ntn-3",
                provenance=_prov("comm:ops"),
            ),
        ),
        provenance=_prov("arch:satellite", "dec:elig-ntn-1"),
    )


def _mature_pass_contract(
    constraints: Tuple[HardConstraint, ...],
):
    """A contract store whose single contract is EXECUTION_ACTIVE
    (deterministic; rebuilt per call so mutating cases stay
    isolated)."""
    store = ContractStore()
    created = store.submit(
        _create_command(constraints), recorded_at=_CONTRACT_CREATED
    )
    cid = created.contract.contract_id
    store.submit(
        SelectOffers(offers=(_OFFER_A, _OFFER_B, _OFFER_C)),
        recorded_at=_CONTRACT_SELECTED,
        contract_id=cid,
    )
    store.submit(
        ActivateContract(
            activated_at=_CONTRACT_T0,
            signature_refs=(
                OpaqueReference(
                    ref_kind="signature", value="sig:ed25519-ntn-1"
                ),
            ),
        ),
        recorded_at=_CONTRACT_T0,
        contract_id=cid,
    )
    store.submit(
        RecordExecutionActivation(recorded_at=_CONTRACT_T0),
        recorded_at=_CONTRACT_T0,
        contract_id=cid,
    )
    return store, store.contract(cid)


def _pass_runtime_session(contract: Any, initial_ref: str):
    """A fresh runtime store whose single session is ACTIVE on the
    initial realization references (the first pass's serving
    satellite)."""
    store = RuntimeStore()
    created = store.create(
        contract_id=contract.contract_id,
        created_at=_R_CREATE,
        provenance=_prov(_BATTERY_ISSUER),
    )
    store.activate(
        created.runtime_id,
        route_decision_id=initial_ref,
        path_id="path:%s" % initial_ref,
        recorded_at=_R_ACTIVATE,
        provenance=_prov(_BATTERY_ISSUER),
    )
    return store, store.session(created.runtime_id)


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


def expect_mesh_error(case: str, reason: str, action: Callable[[], Any]) -> Result:
    """Run one action; PASS when it raises the accepted mesh family's
    MeshError with the exact expected typed reason."""

    try:
        action()
    except MeshError as error:
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
    return fail(case, "expected MeshError(%s); the input was accepted" % reason)


def expect_resilience_error(
    case: str, code: str, action: Callable[[], Any]
) -> Result:
    """Run one action; PASS when it raises the accepted resilience
    machinery's ResilienceError with the exact expected typed
    code."""

    try:
        action()
    except ResilienceError as error:
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
    return fail(case, "expected ResilienceError(%s); the input was accepted" % code)


def _failure_reason(result) -> str:
    return result.failure.reason if result.failure is not None else "?"


# ---------------------------------------------------------------------------
# (a) the non-terrestrial family declarations
# ---------------------------------------------------------------------------


def case_01_family_declarations_round_trip() -> Result:
    name = "case_01_family_declarations_round_trip"
    if tuple(sat.NON_TERRESTRIAL_FAMILIES) != FAMILIES:
        return fail(name, "the declared family set drifted")
    if tuple(sorted(sat.NON_TERRESTRIAL_TECHNOLOGY_CLASSES)) != tuple(
        sorted(
            sat.NON_TERRESTRIAL_ENVELOPES[family].technology_class
            for family in sat.NON_TERRESTRIAL_FAMILIES
        )
    ):
        return fail(name, "the declared technology-class set is inconsistent")
    envelope_ids = set()
    ladder_ids = set()
    for family in FAMILIES:
        envelope = sat.NON_TERRESTRIAL_ENVELOPES[family]
        ladder = sat.NON_TERRESTRIAL_LADDERS[family]
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
        for characteristics in sat.non_terrestrial_handover_declarations(family):
            rebuilt = handover_characteristics_from_mapping(
                characteristics.to_dict()
            )
            if rebuilt.to_canonical_bytes() != characteristics.to_canonical_bytes():
                return fail(name, "%s handover round-trip not byte-identical" % family)
            if rebuilt.characteristics_id != characteristics.characteristics_id:
                return fail(name, "%s handover identity changed" % family)
        envelope_ids.add(envelope.envelope_id)
        ladder_ids.add(ladder.ladder_id)
    if len(envelope_ids) != 4 or len(ladder_ids) != 4:
        return fail(name, "declaration identities not distinct per family")
    # the declared pass schedules round-trip with their own identities
    for schedule in (sat.NGSO_PASS_SCHEDULE, sat.LEO_PASS_SCHEDULE):
        rebuilt = sat.pass_schedule_from_mapping(schedule.to_dict())
        if rebuilt.to_canonical_bytes() != schedule.to_canonical_bytes():
            return fail(name, "%s schedule round-trip not byte-identical" % schedule.family)
        if rebuilt.schedule_id != schedule.schedule_id:
            return fail(name, "%s schedule identity changed on reconstruction" % schedule.family)
    if sat.NGSO_PASS_SCHEDULE.schedule_id == sat.LEO_PASS_SCHEDULE.schedule_id:
        return fail(name, "the two declared pass schedules share an identity")
    # content-derived identity: one dimension changes -> identity changes
    variant = CapabilityEnvelope(
        technology_class=sat.GSO_TECHNOLOGY_CLASS,
        bandwidth=BpsRange(4_000_000, 500_000_000),
        latency=LatencyMilliRange(240, 290),
        jitter=JitterMilliRange(0, 30),
        availability=sat.NON_TERRESTRIAL_ENVELOPES["gso"].availability,
    )
    if variant.envelope_id == sat.NON_TERRESTRIAL_ENVELOPES["gso"].envelope_id:
        return fail(name, "identity not content-derived (bandwidth floor ignored)")
    same = CapabilityEnvelope(
        technology_class=sat.GSO_TECHNOLOGY_CLASS,
        bandwidth=BpsRange(2_000_000, 500_000_000),
        latency=LatencyMilliRange(240, 290),
        jitter=JitterMilliRange(0, 30),
        availability=sat.NON_TERRESTRIAL_ENVELOPES["gso"].availability,
    )
    if same.envelope_id != sat.NON_TERRESTRIAL_ENVELOPES["gso"].envelope_id:
        return fail(name, "same content produced a different identity")
    variant_schedule = sat.PassSchedule(
        family="ngso",
        windows=sat.NGSO_PASS_SCHEDULE.windows,
        serving_refs=("satellite:ngso-delta",) + sat.NGSO_SERVING_REFS[1:],
    )
    if variant_schedule.schedule_id == sat.NGSO_PASS_SCHEDULE.schedule_id:
        return fail(name, "schedule identity not content-derived (serving ref ignored)")
    return ok(
        name,
        "4 declared non-terrestrial families (gso/ngso/leo/mesh-iab): "
        "envelopes, ladders, handover declarations and pass schedules "
        "round-trip byte-identically; content-derived identities distinct "
        "and stable",
    )


def case_02_deterministic_coverage_windows() -> Result:
    name = "case_02_deterministic_coverage_windows"
    # (a) the declared coverage windows per family: the GSO standing
    # window, the NGSO/LEO pass windows, the mesh/IAB DTN-bridged
    # standing window (injected instants only)
    expected_windows = {
        "gso": 1,
        "ngso": len(sat.NGSO_PASS_WINDOWS),
        "leo": len(sat.LEO_PASS_WINDOWS),
        "mesh-iab": 1,
    }
    for family in FAMILIES:
        windows = sat.NON_TERRESTRIAL_ENVELOPES[family].availability.windows
        if len(windows) != expected_windows[family]:
            return fail(
                name,
                "%s declares %d windows (expected %d)"
                % (family, len(windows), expected_windows[family]),
            )
        for window in windows:
            if not window.end.endswith("Z") or not window.start.endswith("Z"):
                return fail(name, "%s window carries a non-Z instant" % family)
    if tuple(
        (window.start, window.end)
        for window in sat.NON_TERRESTRIAL_ENVELOPES["gso"].availability.windows
    ) != (sat.GSO_STANDING_INTERVAL,):
        return fail(name, "the GSO standing window is not the declared interval")
    if tuple(
        (window.start, window.end)
        for window in sat.NON_TERRESTRIAL_ENVELOPES["ngso"].availability.windows
    ) != sat.NGSO_PASS_WINDOWS:
        return fail(name, "the NGSO pass windows are not the declared schedule")
    if tuple(
        (window.start, window.end)
        for window in sat.NON_TERRESTRIAL_ENVELOPES["leo"].availability.windows
    ) != sat.LEO_PASS_WINDOWS:
        return fail(name, "the LEO pass windows are not the declared schedule")
    if tuple(
        (window.start, window.end)
        for window in sat.NON_TERRESTRIAL_ENVELOPES["mesh-iab"].availability.windows
    ) != (sat.MESH_IAB_DTN_INTERVAL,):
        return fail(name, "the mesh/IAB DTN window is not the declared interval")
    # (b) the pass-shape discipline (typed, fail-closed): the
    # pass-shaped families declare MULTIPLE windows; the
    # single-window families carry no pass geometry
    if not sat.is_pass_shaped(sat.NON_TERRESTRIAL_ENVELOPES["ngso"]):
        return fail(name, "the NGSO envelope is not pass-shaped")
    if not sat.is_pass_shaped(sat.NON_TERRESTRIAL_ENVELOPES["leo"]):
        return fail(name, "the LEO envelope is not pass-shaped")
    if sat.is_pass_shaped(sat.NON_TERRESTRIAL_ENVELOPES["gso"]):
        return fail(name, "the GSO envelope read as pass-shaped")
    if sat.is_pass_shaped(sat.NON_TERRESTRIAL_ENVELOPES["mesh-iab"]):
        return fail(name, "the mesh/IAB envelope read as pass-shaped")
    for family in ("gso", "mesh-iab"):
        outcome = expect_typed(
            name,
            "accesstech-envelope-inconsistent",
            lambda f=family: sat.require_pass_shaped_envelope(
                sat.NON_TERRESTRIAL_ENVELOPES[f]
            ),
        )
        if not outcome[1]:
            return fail(name, "%s pass-shape rejection: %s" % (family, outcome[2]))
    outcome = expect_typed(
        name,
        "accesstech-handover-illegal",
        lambda: sat.require_handover_kinds_pass_consistent(
            ("intra-technology", "pass"),
            sat.NON_TERRESTRIAL_ENVELOPES["gso"],
        ),
    )
    if not outcome[1]:
        return fail(name, "pass-kind/single-window rejection: %s" % outcome[2])
    # (c) the typed WALL-CLOCK-LEAK rejection: wall-clock-shaped
    # values (the datetime.now().isoformat() shapes — offset forms,
    # Z-less forms, epoch integers) NEVER enter a declared window
    # (the accepted envelope grammar rejects them typed)
    wall_clock_probes = [
        ("offset-shaped instant", "2026-06-01T12:00:00.481327+00:00"),
        ("Z-less iso instant", "2026-06-01T12:00:00.481327"),
        ("naive local instant", "2026-06-01T12:00:00"),
        ("epoch integer", 1750000000),
    ]
    for label, value in wall_clock_probes:
        for position in ("start", "end"):
            outcome = expect_typed(
                name,
                "accesstech-invalid-input",
                lambda v=value, p=position: AvailabilityWindow(
                    v if p == "start" else "2026-06-01T13:00:00Z",
                    "2026-06-01T13:00:00Z" if p == "start" else v,
                ),
            )
            if not outcome[1]:
                return fail(
                    name,
                    "wall-clock leak (%s, %s) was accepted: %s"
                    % (label, position, outcome[2]),
                )
    # (d) the declared windows are ordered and non-overlapping (the
    # accepted grammar enforces it; the probe re-asserts)
    for family in ("ngso", "leo"):
        windows = sat.NON_TERRESTRIAL_ENVELOPES[family].availability.windows
        for earlier, later in zip(windows, windows[1:]):
            if earlier.start >= later.start or earlier.end > later.start:
                return fail(name, "%s pass windows disordered/overlapping" % family)
    return ok(
        name,
        "coverage windows are DECLARED availability intervals: GSO 1 "
        "standing window, NGSO %d / LEO %d pass windows, mesh/IAB 1 "
        "DTN-bridged standing window (injected instants only; ordered, "
        "non-overlapping); the pass-shape and pass-kind disciplines typed; "
        "4 wall-clock-leak shapes typed-rejected (never a warning)"
        % (len(sat.NGSO_PASS_WINDOWS), len(sat.LEO_PASS_WINDOWS)),
    )


def case_03_propagation_delay_typed_ranges() -> Result:
    name = "case_03_propagation_delay_typed_ranges"
    # (a) the latency dimension IS the family's typed declared
    # propagation-delay range (integer milliseconds — the physical
    # one-way propagation classes)
    expected = {
        "gso": (240, 290),
        "ngso": (70, 120),
        "leo": (10, 55),
        "mesh-iab": (10, 600),
    }
    for family in FAMILIES:
        latency = sat.NON_TERRESTRIAL_ENVELOPES[family].latency
        if (latency.min_ms, latency.max_ms) != expected[family]:
            return fail(
                name,
                "%s propagation range drifted: %s" % (family, (latency.min_ms, latency.max_ms)),
            )
    # (b) the accepted typed-range rejections (degenerate/inverted
    # ranges never construct — typed declared ranges)
    probes = [
        ("inverted propagation range", "accesstech-envelope-inconsistent",
         lambda: LatencyMilliRange(290, 240)),
        ("degenerate zero range", "accesstech-envelope-degenerate",
         lambda: LatencyMilliRange(0, 0)),
        ("float bound", "accesstech-invalid-input",
         lambda: LatencyMilliRange(10.5, 55)),
    ]
    for label, code, action in probes:
        outcome = expect_typed(name, code, action)
        if not outcome[1]:
            return fail(name, "%s: %s" % (label, outcome[2]))
    # (c) the typed margin discipline: the declared budgets admit the
    # declared propagation ceilings (the nominal margins)
    expected_margins = {
        "gso": sat.SERVICE_LATENCY_BUDGET_MS - 290,
        "ngso": sat.SERVICE_LATENCY_BUDGET_MS - 120,
        "leo": sat.SERVICE_LATENCY_BUDGET_MS - 55,
        "mesh-iab": sat.MESH_IAB_SERVICE_LATENCY_BUDGET_MS - 600,
    }
    for family in FAMILIES:
        envelope = sat.NON_TERRESTRIAL_ENVELOPES[family]
        budget = sat.declared_service_budget_ms(family)
        if budget != expected_margins[family] + envelope.latency.max_ms:
            return fail(name, "%s declared budget drifted" % family)
        margin = sat.propagation_margin_ms(envelope, budget)
        if margin != expected_margins[family]:
            return fail(name, "%s nominal margin drifted" % family)
    # (d) the typed fail-closed margins: a budget that does not admit
    # the ceiling; shape errors
    probes = [
        ("budget below the GSO ceiling", "accesstech-envelope-inconsistent",
         lambda: sat.propagation_margin_ms(
             sat.NON_TERRESTRIAL_ENVELOPES["gso"], 250)),
        ("float budget", "accesstech-invalid-input",
         lambda: sat.propagation_margin_ms(
             sat.NON_TERRESTRIAL_ENVELOPES["gso"], 400.5)),
        ("boolean budget", "accesstech-invalid-input",
         lambda: sat.propagation_margin_ms(
             sat.NON_TERRESTRIAL_ENVELOPES["gso"], True)),
        ("non-envelope input", "accesstech-invalid-input",
         lambda: sat.propagation_margin_ms(object(), 400)),
        ("unknown family budget", "accesstech-invalid-input",
         lambda: sat.declared_service_budget_ms("geo")),
    ]
    for label, code, action in probes:
        outcome = expect_typed(name, code, action)
        if not outcome[1]:
            return fail(name, "%s: %s" % (label, outcome[2]))
    return ok(
        name,
        "the latency dimension is the typed declared propagation-delay "
        "range per family (GSO 240-290, NGSO 70-120, LEO 10-55, mesh/IAB "
        "10-600 ms); degenerate/inverted/float bounds typed-rejected; the "
        "nominal margins verified per declared budget; a "
        "ceiling-exceeding budget is the typed ENVELOPE_INCONSISTENT "
        "rejection",
    )


def case_04_propagation_margin_ladders() -> Result:
    name = "case_04_propagation_margin_ladders"
    from replan import REALIZATION_STATES as KERNEL_STATES

    trails: Dict[str, List[Dict[str, Any]]] = {}
    for family in FAMILIES:
        ladder = sat.NON_TERRESTRIAL_LADDERS[family]
        envelope = sat.NON_TERRESTRIAL_ENVELOPES[family]
        budget = sat.declared_service_budget_ms(family)
        # the margin ladder discipline green per family
        sat.require_propagation_margin_ladder(
            ladder, envelope, service_budget_ms=budget
        )
        modes = ladder.modes
        if modes[0].realization_state != "REALIZING":
            return fail(name, "%s root rung is not REALIZING" % family)
        if modes[-1].realization_state != "FAILED":
            return fail(name, "%s terminal rung is not FAILED" % family)
        nominal = sat.propagation_margin_ms(envelope, budget)
        fractions = []
        for position in range(1, len(modes) - 1):
            if modes[position].realization_state != "DEGRADED":
                return fail(
                    name,
                    "%s middle rung %r is not an explicit DEGRADED step"
                    % (family, modes[position].name),
                )
            if not modes[position].name.startswith("margin-"):
                return fail(
                    name,
                    "%s middle rung %r is not a margin step"
                    % (family, modes[position].name),
                )
            fraction = int(modes[position].name.split("-")[1])
            fractions.append(fraction)
            if (nominal * fraction) // 100 < 1:
                return fail(
                    name,
                    "%s margin step %r drops below the propagation floor"
                    % (family, modes[position].name),
                )
        if tuple(fractions) != sat.MARGIN_FRACTIONS:
            return fail(
                name,
                "%s margin fractions drifted: %s" % (family, fractions),
            )
        if fractions != sorted(fractions, reverse=True):
            return fail(name, "%s margin fractions not descending" % family)
        # the full deterministic walk: every step an evidence-visible
        # transition (deterministic trail over the content-derived
        # ladder identity + rung names — LOCK-106)
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
        for rung in modes:
            if mode_realization_state(ladder, rung.name) != rung.realization_state:
                return fail(name, "%s state resolution mismatch" % family)
    # the trails are canonical-JSON stable (every step an explicit
    # recordable transition)
    for family in FAMILIES:
        first = canonical_json_bytes(trails[family])
        second = canonical_json_bytes(trails[family])
        if first != second:
            return fail(name, "%s transition trail not stable" % family)
    # typed rejections: the ladder-discipline probes
    probes = [
        ("undeclared mode stepped", "accesstech-ladder-illegal",
         lambda: ladder_step(sat.NON_TERRESTRIAL_LADDERS["gso"], "unknown-mode")),
        ("terminal mode stepped", "accesstech-ladder-illegal",
         lambda: ladder_step(
             sat.NON_TERRESTRIAL_LADDERS["gso"],
             sat.NON_TERRESTRIAL_LADDERS["gso"].terminal_mode().name)),
        ("undeclared mode state", "accesstech-vocabulary",
         lambda: DegradationMode("mystery", "RESTORING")),
        ("non-margin middle rung", "accesstech-ladder-illegal",
         lambda: sat.require_propagation_margin_ladder(
             accesstech.DegradationLadder(
                 technology_class=sat.GSO_TECHNOLOGY_CLASS,
                 modes=(
                     DegradationMode("nominal", "REALIZING"),
                     DegradationMode("capacity-75", "DEGRADED"),
                     DegradationMode("trunk-failed", "FAILED"),
                 ),
             ),
             sat.NON_TERRESTRIAL_ENVELOPES["gso"],
             service_budget_ms=sat.declared_service_budget_ms("gso"),
         )),
        ("ascending margin fractions", "accesstech-ladder-illegal",
         lambda: sat.require_propagation_margin_ladder(
             accesstech.DegradationLadder(
                 technology_class=sat.GSO_TECHNOLOGY_CLASS,
                 modes=(
                     DegradationMode("nominal", "REALIZING"),
                     DegradationMode("margin-25", "DEGRADED"),
                     DegradationMode("margin-75", "DEGRADED"),
                     DegradationMode("trunk-failed", "FAILED"),
                 ),
             ),
             sat.NON_TERRESTRIAL_ENVELOPES["gso"],
             service_budget_ms=sat.declared_service_budget_ms("gso"),
         )),
        ("margin step below the floor", "accesstech-ladder-illegal",
         lambda: sat.require_propagation_margin_ladder(
             sat.NON_TERRESTRIAL_LADDERS["gso"],
             sat.NON_TERRESTRIAL_ENVELOPES["gso"],
             service_budget_ms=292,
         )),
        ("budget without margin", "accesstech-envelope-inconsistent",
         lambda: sat.require_propagation_margin_ladder(
             sat.NON_TERRESTRIAL_LADDERS["gso"],
             sat.NON_TERRESTRIAL_ENVELOPES["gso"],
             service_budget_ms=250,
         )),
        ("fraction out of range", "accesstech-ladder-illegal",
         lambda: sat.require_propagation_margin_ladder(
             accesstech.DegradationLadder(
                 technology_class=sat.GSO_TECHNOLOGY_CLASS,
                 modes=(
                     DegradationMode("nominal", "REALIZING"),
                     DegradationMode("margin-100", "DEGRADED"),
                     DegradationMode("trunk-failed", "FAILED"),
                 ),
             ),
             sat.NON_TERRESTRIAL_ENVELOPES["gso"],
             service_budget_ms=sat.declared_service_budget_ms("gso"),
         )),
    ]
    for label, code, action in probes:
        outcome = expect_typed(name, code, action)
        if not outcome[1]:
            return fail(name, "%s: %s" % (label, outcome[2]))
    if KERNEL_STATES != ("REALIZING", "DEGRADED", "FAILED", "SUPERSEDED"):
        return fail(name, "the consumed kernel drifted")
    return ok(
        name,
        "4 ladders walked rung-by-rung: every middle rung an explicit "
        "DEGRADED propagation-aware margin step (%s fractions of the "
        "nominal margin, descending, every step above the propagation "
        "floor), the terminal rung FAILED, each step an evidence-visible "
        "deterministic transition (canonical trails, rebuilt-ladder walks "
        "identical); 8 typed ladder/margin rejections" % (
            "/".join(str(f) for f in sat.MARGIN_FRACTIONS),
        ),
    )


def case_05_declared_pass_schedules() -> Result:
    name = "case_05_declared_pass_schedules"
    # (a) the declared schedules: NGSO 4 passes / 3 transitions; LEO
    # 6 passes / 5 transitions; every transition changes the serving
    # reference and lands at the new pass's opening instant
    expected = {
        "ngso": (4, 3, sat.NGSO_SERVING_REFS),
        "leo": (6, 5, sat.LEO_SERVING_REFS),
    }
    schedules = {"ngso": sat.NGSO_PASS_SCHEDULE, "leo": sat.LEO_PASS_SCHEDULE}
    for family, (passes, transitions, refs) in expected.items():
        schedule = schedules[family]
        if schedule.pass_count() != passes:
            return fail(name, "%s pass count drifted" % family)
        if len(schedule.pass_transitions()) != transitions:
            return fail(name, "%s transition count drifted" % family)
        if schedule.serving_refs != refs:
            return fail(name, "%s serving refs drifted" % family)
        for position, transition in enumerate(schedule.pass_transitions()):
            if transition.position != position:
                return fail(name, "%s transition position drifted" % family)
            if transition.old_ref != refs[position]:
                return fail(name, "%s transition old ref drifted" % family)
            if transition.new_ref != refs[position + 1]:
                return fail(name, "%s transition new ref drifted" % family)
            if transition.reconnect_instant != transition.to_pass_start:
                return fail(name, "%s reconnect instant is not the new opening" % family)
            if transition.to_pass_start != schedule.windows[position + 1].start:
                return fail(name, "%s transition target window drifted" % family)
            if transition.from_pass_end != schedule.windows[position].end:
                return fail(name, "%s transition source window drifted" % family)
        # the schedule's windows ARE the family envelope's own
        # declared windows (the typed cross-check)
        sat.require_schedule_matches_envelope(
            schedule, sat.NON_TERRESTRIAL_ENVELOPES[family]
        )
    # the module's declared schedule factory agrees
    for family in ("ngso", "leo"):
        factory = sat.declared_pass_schedule(family)
        if factory.schedule_id != schedules[family].schedule_id:
            return fail(name, "%s factory schedule identity drifted" % family)
    # (b) the typed schedule rejections
    probes = [
        ("consecutive same serving ref", "accesstech-envelope-inconsistent",
         lambda: sat.PassSchedule(
             family="ngso",
             windows=sat.NGSO_PASS_SCHEDULE.windows,
             serving_refs=(
                 "satellite:ngso-alpha", "satellite:ngso-alpha",
                 "satellite:ngso-bravo", "satellite:ngso-charlie",
             ))),
        ("one-window schedule", "accesstech-envelope-degenerate",
         lambda: sat.PassSchedule(
             family="ngso",
             windows=sat.NGSO_PASS_SCHEDULE.windows[:1],
             serving_refs=("satellite:ngso-alpha",))),
        ("wrong family", "accesstech-invalid-input",
         lambda: sat.PassSchedule(
             family="gso",
             windows=sat.NGSO_PASS_SCHEDULE.windows,
             serving_refs=sat.NGSO_SERVING_REFS)),
        ("serving count mismatch", "accesstech-envelope-inconsistent",
         lambda: sat.PassSchedule(
             family="ngso",
             windows=sat.NGSO_PASS_SCHEDULE.windows,
             serving_refs=sat.NGSO_SERVING_REFS[:3])),
        ("non-window entries", "accesstech-invalid-input",
         lambda: sat.PassSchedule(
             family="ngso",
             windows=("2026-06-01T08:00:00Z",),
             serving_refs=sat.NGSO_SERVING_REFS)),
        ("tampered identity", "accesstech-identity-mismatch",
         lambda: sat.pass_schedule_from_mapping(
             {**sat.NGSO_PASS_SCHEDULE.to_dict(),
              "schedule_id": "sha256:" + "0" * 64})),
        ("grammar drift", "accesstech-serialization-invalid",
         lambda: sat.pass_schedule_from_mapping(
             {k: v for k, v in sat.NGSO_PASS_SCHEDULE.to_dict().items()
              if k != "serving_refs"})),
    ]
    for label, code, action in probes:
        outcome = expect_typed(name, code, action)
        if not outcome[1]:
            return fail(name, "%s: %s" % (label, outcome[2]))
    # (c) the schedule/envelope cross-check is typed fail-closed
    outcome = expect_typed(
        name,
        "accesstech-envelope-inconsistent",
        lambda: sat.require_schedule_matches_envelope(
            sat.NGSO_PASS_SCHEDULE,
            sat.NON_TERRESTRIAL_ENVELOPES["leo"],
        ),
    )
    if not outcome[1]:
        return fail(name, "schedule/envelope mismatch probe: %s" % outcome[2])
    outcome = expect_typed(
        name,
        "accesstech-invalid-input",
        lambda: sat.declared_pass_schedule("gso"),
    )
    if not outcome[1]:
        return fail(name, "non-pass-family schedule probe: %s" % outcome[2])
    return ok(
        name,
        "the declared pass schedules: NGSO 4 passes / 3 transitions, LEO "
        "6 passes / 5 transitions — every transition names the OLD and "
        "NEW serving references with the reconnect instant at the new "
        "pass's opening; the schedules carry the envelopes' own windows "
        "(typed cross-check); 9 malformed classes typed-rejected",
    )


# ---------------------------------------------------------------------------
# (b) the registration surface — the four families
# ---------------------------------------------------------------------------


def case_06_families_registered_through_extension_surface() -> Result:
    name = "case_06_families_registered_through_extension_surface"
    store, sid = ads._established_session()
    registry, registrations, _wirings = _register_all(store)
    if tuple(registry.technology_classes()) != tuple(
        sorted(sat.NON_TERRESTRIAL_TECHNOLOGY_CLASSES)
    ):
        return fail(
            name,
            "registry class set wrong: %s" % (registry.technology_classes(),),
        )
    ids = set()
    for family in FAMILIES:
        registration = registrations[family]
        envelope = sat.NON_TERRESTRIAL_ENVELOPES[family]
        ladder = sat.NON_TERRESTRIAL_LADDERS[family]
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
        if registration.mechanisms != _FAMILY_MECHANISMS[family]:
            return fail(name, "%s mechanism tags not carried verbatim" % family)
        # the handover declarations carried with the machinery's own
        # frozen semantics (the FULL preserved set — LOCK-108)
        kinds = tuple(
            characteristics.kind
            for characteristics in registration.handovers
        )
        if kinds != sat.NON_TERRESTRIAL_HANDOVER_KINDS[family]:
            return fail(name, "%s handover kinds not carried verbatim" % family)
        for characteristics in registration.handovers:
            if characteristics.preserved_constraint_kinds != preserved_constraint_kinds():
                return fail(name, "%s preserved set drift" % family)
            if characteristics.explicit_reconnect is not True:
                return fail(name, "%s explicit-reconnect weakened" % family)
            if characteristics.contract_continuity is not True:
                return fail(name, "%s contract-continuity weakened" % family)
        if registry.lookup(envelope.technology_class) is not registration:
            return fail(name, "%s registry lookup lost the registration" % family)
        ids.add(registration.registration_id)
    if len(ids) != 4:
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
        "all four non-terrestrial families registered through the "
        "accepted M020 public path: envelopes/ladders/handover "
        "declarations carried by reference; capability statements + "
        "LOCK-112 tags + LOCK-108 preserved sets verbatim; the LOCK-109 "
        "bridge frozen name-equal; identities content-derived and "
        "distinct",
    )


def case_07_registration_resolves_by_reference() -> Result:
    name = "case_07_registration_resolves_by_reference"
    for family in FAMILIES:
        store, sid = ads._established_session()
        bridge, descriptor, requirements, wiring = _mount_family(store, family)
        registration = register_access_technology(
            envelope=sat.NON_TERRESTRIAL_ENVELOPES[family],
            ladder=sat.NON_TERRESTRIAL_LADDERS[family],
            handovers=sat.non_terrestrial_handover_declarations(family),
            implementation=bridge,
            descriptor=descriptor,
            binding_requirements=requirements,
            mechanisms=_FAMILY_MECHANISMS[family],
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
        # resolves to the ACCEPTED mesh family runtime BY REFERENCE
        # (the implementation IS the accepted family bridge class)
        view = registration.resolve_capability_adapter().inspect_capabilities(
            now=_NOW
        )
        if not view.ok:
            return fail(name, "%s inspect failed" % family)
        if view.value.adapter_id != descriptor.adapter_id:
            return fail(name, "%s view adapter mismatch" % family)
        if view.value.access_technology_id != sat.NON_TERRESTRIAL_ENVELOPES[family].technology_class:
            return fail(name, "%s view technology mismatch" % family)
        if view.value.lifecycle != "OPEN":
            return fail(name, "%s adapter not OPEN" % family)
        if view.value.standard_mechanisms != _FAMILY_MECHANISMS[family]:
            return fail(name, "%s view mechanism tags mismatch" % family)
        if bridge.__class__.__name__ != "MeshTechnologyAdapter":
            return fail(name, "%s implementation is not the family bridge" % family)
        # the mesh/IAB composition's DTN wiring carries the SAME live
        # family objects the composition root created (BY REFERENCE)
        if family == "mesh-iab":
            if wiring["engine"].__class__.__name__ != "SidelinkRelayEngine":
                return fail(name, "mesh/IAB engine is not the sidelink relay")
            if wiring["manager"].__class__.__name__ != "MeshManager":
                return fail(name, "mesh/IAB wiring manager is not the family manager")
            if len(wiring["leg_refs"]) != 2:
                return fail(name, "mesh/IAB chain is not two sidelink legs")
        # the canonical record excludes the live objects and
        # round-trips with the live references re-supplied
        content = registration.to_dict()
        for key in ("capability_adapter", "runtime", "descriptor", "envelope", "ladder"):
            if key in content:
                return fail(name, "the canonical record carries %r" % key)
        rebuilt = technology_registration_from_mapping(
            content,
            envelope=sat.NON_TERRESTRIAL_ENVELOPES[family],
            ladder=sat.NON_TERRESTRIAL_LADDERS[family],
            handovers=sat.non_terrestrial_handover_declarations(family),
            capability_adapter=registration.capability_adapter,
            runtime=registration.runtime,
            descriptor=descriptor,
            binding_requirements=requirements,
            mechanisms=_FAMILY_MECHANISMS[family],
        )
        if rebuilt.registration_id != registration.registration_id:
            return fail(name, "%s registration identity changed on rebuild" % family)
        if rebuilt.to_canonical_bytes() != registration.to_canonical_bytes():
            return fail(name, "%s canonical record changed on rebuild" % family)
        if rebuilt.resolve_capability_adapter() is not registration.capability_adapter:
            return fail(name, "%s rebuild lost the live reference" % family)
    return ok(
        name,
        "4 families: resolution identity-preserving (the same live "
        "adapter, runtime and descriptor objects — the accepted mesh "
        "family runtime BY REFERENCE through the accepted family "
        "bridge); the public runtime carries the composition's "
        "technology; canonical records round-trip with the live "
        "references re-supplied",
    )


# ---------------------------------------------------------------------------
# (c) the nine WORK-016 operations — deterministic flows + the re-bind
# ---------------------------------------------------------------------------


def case_08_nine_operations_reserve_activate_measure() -> Result:
    name = "case_08_nine_operations_reserve_activate_measure"
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
        registration, _wiring = _register_family(store, family)
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
            if view.kind != "storage" or view.unit != "bytes":
                return fail(name, "%s offer mapped resource drifted" % family)
            if view.availability != "reservation-based":
                return fail(name, "%s offer availability drifted" % family)
        exercised.add("capabilities")
        # health -> health
        health = capability.health(now=_NOW)
        if not health.ok or not isinstance(health.value, HealthReport):
            return fail(name, "%s health not a typed report" % family)
        exercised.add("health")
        # reserve -> allocate
        reserved = capability.reserve(
            kind="storage",
            quantity=_FAMILY_RESERVE[family],
            unit="bytes",
            purpose="m022-%s-flow" % family,
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
        "4 families: the frozen translation map verified and every flow "
        "green through the mediated WORK-016 nine-op runtime "
        "(capabilities/allocate/bind_session/observe/unbind_session/"
        "release/health + the registration open drive); typed records at "
        "every step; activation trails bounded and ordered",
    )


def case_09_rebind_translation_mid_session() -> Result:
    name = "case_09_rebind_translation_mid_session"
    for family in FAMILIES:
        store, sid = ads._established_session()
        registration, _wiring = _register_family(store, family)
        capability = registration.resolve_capability_adapter()
        reserved = capability.reserve(
            kind="storage",
            quantity=_FAMILY_RESERVE[family],
            unit="bytes",
            purpose="m022-%s-rebind" % family,
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
    return ok(
        name,
        "4 families: the deterministic re-bind translation verified "
        "(same session, preserved reservation, previous binding released "
        "first, new binding created — typed Reconfiguration records; "
        "ACTIVE -> RECONFIGURED; idempotent second reconfiguration; "
        "measure + release green after the re-bind)",
    )


# ---------------------------------------------------------------------------
# (d) the NGSO pass-handover geometry (the accepted resilience machinery)
# ---------------------------------------------------------------------------


def _drive_pass_handover(
    contract: Any,
    store: RuntimeStore,
    runtime_id: object,
    transition: Any,
) -> Any:
    """Drive ONE declared pass transition through the ACCEPTED
    ``perform_handover`` machinery (the candidate names the new
    realization references and carries the contract's hard
    constraints VERBATIM — LOCK-108)."""
    candidate = handover_candidate(
        contract,
        route_decision_id=transition.new_ref,
        path_id="path:%s" % transition.new_ref,
        hard_constraints=tuple(contract.hard_constraints),
    )
    return perform_handover(
        store,
        runtime_id,
        contract,
        (candidate,),
        trigger_kind="route-expiry",
        recorded_at=transition.reconnect_instant,
    )


def case_10_ngso_pass_handover_geometry() -> Result:
    name = "case_10_ngso_pass_handover_geometry"
    constraints = _pass_contract_constraints()
    _store, contract = _mature_pass_contract(constraints)
    store, session = _pass_runtime_session(
        contract, sat.NGSO_SERVING_REFS[0]
    )
    rid = session.runtime_id
    problems: List[str] = []
    previous_ref = sat.NGSO_SERVING_REFS[0]
    # (a) EVERY declared pass transition drives through the accepted
    # machinery: the explicit reconnect pair, LOCK-108 verbatim
    # constraint equality, the new references landed
    for transition in sat.NGSO_PASS_SCHEDULE.pass_transitions():
        result = _drive_pass_handover(contract, store, rid, transition)
        if result.outcome != "adopted":
            problems.append(
                "the pass transition %d was not adopted (%s)"
                % (transition.position, result.outcome)
            )
            break
        after = result.session
        if after.state != "ACTIVE":
            problems.append(
                "the adopted pass handover did not land ACTIVE (%s)"
                % after.state
            )
        if (after.route_decision_id, after.path_id) != (
            transition.new_ref,
            "path:%s" % transition.new_ref,
        ):
            problems.append(
                "the adopted pass handover did not land on the new refs"
            )
        # LOCK-108: the decision's constraint fingerprint IS the
        # contract's own (verbatim equality across every pass
        # handover), re-verified through the consumed cross-authority
        # gate
        if result.decision.constraint_fingerprint != contract.hard_constraint_fingerprint():
            problems.append(
                "the pass decision fingerprint is not the contract's own"
            )
        try:
            verify_decision_preserves_contract(result.decision, contract)
        except Exception as error:  # noqa: BLE001
            problems.append(
                "the pass decision failed the consumed gate: %s"
                % str(error)[:80]
            )
        # WORK-012: the explicit recorded reconnect — OLD AND NEW
        # references both named, the pair in the journal, the
        # reconnect instant the transition's declared instant
        reconnect = result.reconnect
        if reconnect is None:
            problems.append(
                "the pass transition %d produced no reconnect evidence"
                % transition.position
            )
        else:
            if reconnect.old_route_decision_id != previous_ref:
                problems.append(
                    "the reconnect lost the OLD serving reference"
                )
            if reconnect.new_route_decision_id != transition.new_ref:
                problems.append("the reconnect lost the NEW serving reference")
            if reconnect.old_path_id != "path:%s" % previous_ref:
                problems.append("the reconnect lost the OLD path reference")
            if reconnect.new_path_id != "path:%s" % transition.new_ref:
                problems.append("the reconnect lost the NEW path reference")
            if reconnect.reconnect_instant != transition.reconnect_instant:
                problems.append(
                    "the reconnect instant is not the declared transition "
                    "instant"
                )
        events = store.events(rid)
        kinds = [event.kind for event in events]
        if kinds[-2:] != ["reconnect-initiated", "reconnect-completed"]:
            problems.append(
                "the journal does not end with the explicit reconnect pair"
            )
        if len(result.event_ids) != 2:
            problems.append(
                "the drive appended %d events (expected the pair)"
                % len(result.event_ids)
            )
        previous_ref = transition.new_ref
    if problems:
        return fail(name, "; ".join(problems[:5]))
    # (b) the reconnect evidence records: exactly one per declared
    # transition, derived from the journal
    evidence = store.reconnect_evidence(rid)
    if len(evidence) != len(sat.NGSO_PASS_SCHEDULE.pass_transitions()):
        return fail(
            name,
            "reconnect evidence count %d != the declared transitions %d"
            % (len(evidence), len(sat.NGSO_PASS_SCHEDULE.pass_transitions())),
        )
    for record, transition in zip(
        evidence, sat.NGSO_PASS_SCHEDULE.pass_transitions()
    ):
        if record.new_route_decision_id != transition.new_ref:
            return fail(name, "evidence order does not match the schedule")
    # (c) the LEO sibling: one representative transition driven
    # identically (the same machinery, the same disciplines)
    leo_transition = sat.LEO_PASS_SCHEDULE.pass_transitions()[0]
    _store2, contract2 = _mature_pass_contract(constraints)
    store2, session2 = _pass_runtime_session(
        contract2, sat.LEO_SERVING_REFS[0]
    )
    result2 = _drive_pass_handover(contract2, store2, session2.runtime_id, leo_transition)
    if result2.outcome != "adopted":
        return fail(name, "the LEO sibling transition was not adopted")
    if result2.reconnect is None:
        return fail(name, "the LEO sibling transition produced no reconnect")
    if result2.reconnect.new_route_decision_id != leo_transition.new_ref:
        return fail(name, "the LEO sibling reconnect lost the new reference")
    # (d) LOCK-108 fail-closed: a WEAKENED candidate constraint set is
    # rejected with the typed kind-citing reason (the raising gate,
    # the verdict twin), and the machinery NEVER adopts it — the
    # EXPLICIT FAILED state, no silent reconnect
    weakened = (
        HardConstraint(
            kind="latency-bound",
            params={"max_ms": sat.SERVICE_LATENCY_BUDGET_MS + 200},
            provenance=_prov("prov:orbit-one"),
        ),
    )
    outcome = expect_resilience_error(
        name,
        "resilience-constraint-weakened",
        lambda: validate_handover_preserves_contract(
            weakened, contract
        ),
    )
    if not outcome[1]:
        return fail(name, "the weakened candidate gate: %s" % outcome[2])
    weak_candidate = handover_candidate(
        contract,
        route_decision_id="satellite:ngso-weak",
        path_id="path:satellite:ngso-weak",
        hard_constraints=weakened,
    )
    verdict = handover_verdict(weak_candidate, contract)
    if verdict.accepted:
        return fail(name, "the verdict twin accepted the weakening candidate")
    if "availability-floor" not in verdict.detail:
        return fail(name, "the verdict does not cite the weakened kind")
    _store3, contract3 = _mature_pass_contract(constraints)
    store3, session3 = _pass_runtime_session(
        contract3, sat.NGSO_SERVING_REFS[0]
    )
    weak_result = perform_handover(
        store3,
        session3.runtime_id,
        contract3,
        (weak_candidate,),
        trigger_kind="route-expiry",
        recorded_at=sat.NGSO_PASS_SCHEDULE.pass_transitions()[0].reconnect_instant,
    )
    if weak_result.decision.decision == "adopt-alternative":
        return fail(name, "the machinery adopted the weakening candidate")
    if weak_result.session.state != "FAILED":
        return fail(
            name,
            "the impossible handover did not land FAILED explicitly (%s)"
            % weak_result.session.state,
        )
    if store3.reconnect_evidence(session3.runtime_id):
        return fail(name, "a weakening candidate silently reconnected")
    # (e) the WORK-012 no-silent-swap gate: a reconnect completion
    # WITHOUT an in-progress initiation is the typed SILENT_REPLACEMENT
    # rejection (a route change without the explicit initiated+
    # completed pair naming old AND new references never lands) —
    # probed on a FRESH ACTIVE session (the weakened drive's session
    # is terminal; the terminal gate is a different typed rejection)
    _store4, contract4 = _mature_pass_contract(constraints)
    store4, session4 = _pass_runtime_session(
        contract4, sat.NGSO_SERVING_REFS[0]
    )
    outcome = expect_resilience_error(
        name,
        "resilience-silent-replacement",
        lambda: store4.complete_reconnect(
            session4.runtime_id,
            recorded_at=_LATER,
            provenance=_prov(_BATTERY_ISSUER),
        ),
    )
    if not outcome[1]:
        return fail(name, "the silent-completion gate: %s" % outcome[2])
    # (f) the pass-kind declaration semantics: the FULL preserved
    # constraint set (LOCK-108), the mandatory explicit reconnect
    # (WORK-012) and contract continuity (LOCK-101/117) — the
    # machinery's own frozen semantics, declared per kind
    for family in ("ngso", "leo"):
        for characteristics in sat.non_terrestrial_handover_declarations(family):
            if characteristics.kind == "pass":
                if characteristics.preserved_constraint_kinds != preserved_constraint_kinds():
                    return fail(name, "%s pass kind preserved set drift" % family)
                if characteristics.explicit_reconnect is not True:
                    return fail(name, "%s pass kind silent swap declared" % family)
    return ok(
        name,
        "the NGSO pass-handover geometry driven through the accepted "
        "resilience/ machinery: all %d declared transitions adopted "
        "through the EXPLICIT reconnect pair (old AND new references "
        "named, the declared reconnect instants); LOCK-108 verbatim "
        "constraint equality across every handover (the fingerprint is "
        "the contract's own; the weakened candidate typed-rejected and "
        "landing the EXPLICIT FAILED state, never a silent reconnect); "
        "the silent-completion gate typed; the LEO sibling driven "
        "identically; the pass-kind declarations carry the machinery's "
        "own frozen semantics" % len(sat.NGSO_PASS_SCHEDULE.pass_transitions()),
    )


# ---------------------------------------------------------------------------
# (e) the mesh/IAB extension — sidelink relay + DTN store-and-forward
# ---------------------------------------------------------------------------


def _dtn_drill(wiring: Dict[str, Any], store, sid: str) -> Dict[str, Any]:
    """Drive the deterministic mesh/IAB DTN drill through the family's
    OWN public APIs (the sidelink engine's partition hook included) —
    the store-and-forward semantics composed BY REFERENCE.  Returns
    the canonical outcome trail (byte-comparable across rebuilds)."""
    manager = wiring["manager"]
    engine = wiring["engine"]
    leg_refs = wiring["leg_refs"]
    route_ref = wiring["route_ref"]
    payload = b"m022-dtn-payload"
    bound = manager.bind_session(now=_NOW, session_id=sid, route_ref=route_ref)
    if not bound.ok:
        raise AssertionError("DTN bind failed: %s" % bound.detail)
    bearer_ref = bound.value.bearer_ref
    enqueued = manager.enqueue_bundle(
        now=_NOW, bearer_ref=bearer_ref, payload=payload
    )
    if not enqueued.ok:
        raise AssertionError("DTN enqueue failed: %s" % enqueued.detail)
    bundle_ref = enqueued.value.bundle_ref
    trail: Dict[str, Any] = {
        "bundle_ref": bundle_ref,
        "bearer_ref": bearer_ref,
        "verdicts": [],
    }
    # hop 1 forwards
    first = manager.forward_bundle(now=_NOW, bundle_ref=bundle_ref)
    if not first.ok:
        raise AssertionError("DTN hop 1 failed: %s" % first.detail)
    trail["verdicts"].append(first.value.verdict)
    # PARTITION the second sidelink leg: the bundle DEFERS (the
    # store-and-forward discipline — metadata preserved, no delivery
    # claimed)
    engine.set_leg_state(leg_refs[1], up=False)
    second = manager.forward_bundle(now=_NOW, bundle_ref=bundle_ref)
    if not second.ok:
        raise AssertionError("DTN partition forward failed: %s" % second.detail)
    trail["verdicts"].append(second.value.verdict)
    during = manager.inspect_bundle(now=_NOW, bundle_ref=bundle_ref).value
    trail["deferred_state"] = during.state
    trail["deferred_position"] = during.position
    trail["deferred_session_ok"] = during.session_id == sid
    # RECOVERY: the original bytes deliver
    engine.set_leg_state(leg_refs[1], up=True)
    third = manager.forward_bundle(now=_NOW, bundle_ref=bundle_ref)
    if not third.ok:
        raise AssertionError("DTN recovery forward failed: %s" % third.detail)
    trail["verdicts"].append(third.value.verdict)
    if third.value.verdict == ForwardVerdict.DELIVERED:
        trail["delivered_payload"] = bytes(third.value.payload)
    # the application facade: the delivered bytes drain; the payload
    # crossed intact
    facade = manager.app_session(now=_NOW, session_id=sid).value
    facade.connect(_NODE_GATEWAY)
    trail["drained"] = facade.recv()
    return trail


def case_11_mesh_iab_sidelink_dtn_extension() -> Result:
    name = "case_11_mesh_iab_sidelink_dtn_extension"
    store, sid = ads._established_session()
    bridge, descriptor, requirements, wiring = _mount_family(store, "mesh-iab")
    # (a) the composition wires the ACCEPTED family objects BY
    # REFERENCE: the SidelinkRelayEngine (the sidelink relay
    # implementation), the MeshManager, the accepted bridge class
    if wiring["engine"].__class__.__name__ != "SidelinkRelayEngine":
        return fail(name, "the mesh/IAB engine is not the sidelink relay")
    if wiring["engine"].label != "sidelink-relay":
        return fail(name, "the sidelink engine label drifted")
    if wiring["manager"].__class__.__name__ != "MeshManager":
        return fail(name, "the mesh/IAB manager is not the family manager")
    if bridge.__class__.__name__ != "MeshTechnologyAdapter":
        return fail(name, "the mesh/IAB implementation is not the family bridge")
    if satref.MESH_IAB_DTN_CONFIG.max_queued_bytes != satref.MESH_IAB_QUEUE_BYTES:
        return fail(name, "the declared DTN queue bound is not the mapped capacity")
    # the registration drives the accepted extension surface with the
    # composed products (the mesh/IAB family is an M022 family like
    # the other three)
    registration = register_access_technology(
        envelope=sat.NON_TERRESTRIAL_ENVELOPES["mesh-iab"],
        ladder=sat.NON_TERRESTRIAL_LADDERS["mesh-iab"],
        handovers=sat.non_terrestrial_handover_declarations("mesh-iab"),
        implementation=bridge,
        descriptor=descriptor,
        binding_requirements=requirements,
        mechanisms=satref.MESH_IAB_MECHANISMS,
        session_store=store,
        now=_T0,
    )
    reserved = registration.resolve_capability_adapter().reserve(
        kind="storage", quantity=1_000_000, unit="bytes",
        purpose="m022-dtn", now=_NOW,
    )
    if not reserved.ok:
        return fail(name, "the mesh/IAB reserve failed")
    # (b) the DTN drill: enqueue -> forward -> PARTITION-DEFER ->
    # recover -> DELIVER (the original bytes), through the family's
    # OWN public APIs
    trail = _dtn_drill(wiring, store, sid)
    if trail["verdicts"][:2] != [ForwardVerdict.FORWARDED, ForwardVerdict.DEFERRED]:
        return fail(name, "the partition drill verdicts drifted: %s" % trail["verdicts"])
    if trail["verdicts"][2] != ForwardVerdict.DELIVERED:
        return fail(name, "the recovery did not deliver: %s" % trail["verdicts"])
    if trail["delivered_payload"] != b"m022-dtn-payload":
        return fail(name, "the payload corrupted across the partition")
    if trail["drained"] != b"m022-dtn-payload":
        return fail(name, "the facade did not drain the delivered bytes")
    if trail["deferred_state"] != BundleState.DEFERRED:
        return fail(name, "the deferred state drifted: %s" % trail["deferred_state"])
    if not trail["deferred_session_ok"]:
        return fail(name, "the bundle lost its session attribution during the gap")
    # (c) the deterministic TTL expiry sweep (the declared DTN
    # discipline: a bundle whose lifetime lapses during a gap EXPIRES
    # — never a ghost delivery, capacity released) — on the SAME
    # live bearer the drill bound (the family's one-bearer-per-route
    # discipline)
    manager = wiring["manager"]
    bound_bearer = trail["bearer_ref"]
    expiring = manager.enqueue_bundle(
        now=_NOW, bearer_ref=bound_bearer, payload=b"m022-expiring"
    ).value
    first_hop = manager.forward_bundle(
        now=_NOW, bundle_ref=expiring.bundle_ref
    )
    if not first_hop.ok or first_hop.value.verdict != ForwardVerdict.FORWARDED:
        return fail(name, "the expiring bundle did not take its first hop")
    # _NOW + ttl(7200s) + 1s: the bundle's deterministic lifetime has
    # lapsed (the declared config's own bound)
    swept = manager.expire_bundles(now="2026-06-01T09:00:01Z").value
    if expiring.bundle_ref not in swept:
        return fail(name, "the sweep missed the TTL-lapsed bundle")
    again = manager.forward_bundle(
        now="2026-06-01T09:00:02Z", bundle_ref=expiring.bundle_ref
    )
    if again.ok or again.reason != MeshReasonCode.ILLEGAL_STATE:
        return fail(
            name,
            "the expired bundle forwarded again: %s" % again.reason,
        )
    fresh = manager.enqueue_bundle(
        now="2026-06-01T09:00:02Z", bearer_ref=bound_bearer, payload=b"m022-fresh"
    )
    if not fresh.ok:
        return fail(name, "the expiry did not release the queue capacity")
    facade = manager.app_session(
        now="2026-06-01T09:00:02Z", session_id=sid
    ).value
    facade.connect(_NODE_GATEWAY)
    if facade.recv() != b"":
        return fail(name, "a ghost delivery was claimed for the expired bundle")
    # (d) the whole drill is deterministic: a fresh mount produces the
    # identical trail (the projection is the digest-able material —
    # the same shape the determinism case_16 rebuilds)
    store2, sid2 = ads._established_session()
    _bridge2, _descriptor2, _requirements2, wiring2 = _mount_family(store2, "mesh-iab")
    trail2 = _dtn_drill(wiring2, store2, sid2)
    projection = {
        "bundle_ref": trail["bundle_ref"],
        "verdicts": [str(v) for v in trail["verdicts"]],
        "deferred_state": str(trail["deferred_state"]),
        "deferred_position": trail["deferred_position"],
        "delivered_payload": trail["delivered_payload"].decode(),
        "drained": trail["drained"].decode(),
    }
    projection2 = {
        "bundle_ref": trail2["bundle_ref"],
        "verdicts": [str(v) for v in trail2["verdicts"]],
        "deferred_state": str(trail2["deferred_state"]),
        "deferred_position": trail2["deferred_position"],
        "delivered_payload": trail2["delivered_payload"].decode(),
        "drained": trail2["drained"].decode(),
    }
    if canonical_json_bytes(projection) != canonical_json_bytes(projection2):
        return fail(name, "the DTN drill trail is not deterministic on rebuild")
    return ok(
        name,
        "the mesh/IAB extension composes the accepted adapters/mesh/ "
        "family runtime BY REFERENCE: the accepted SidelinkRelayEngine "
        "with the declared satellite DTN limits; the drill "
        "forward/partition-DEFER/recover-DELIVER (original bytes, "
        "metadata preserved) and the TTL expiry sweep (swept, tombstone "
        "typed, capacity released, no ghost delivery) — all through the "
        "family's OWN public APIs; byte-identical on rebuild",
    )


# ---------------------------------------------------------------------------
# (f) LOCK-110 isolation + the typed fail-closed matrix
# ---------------------------------------------------------------------------


def case_12_lock110_provider_sdk_isolation() -> Result:
    name = "case_12_lock110_provider_sdk_isolation"
    for family in FAMILIES:
        store, sid = ads._established_session()
        registration, _wiring = _register_family(store, family)
        capability = registration.resolve_capability_adapter()
        records: List[Any] = []
        inspected = capability.inspect_capabilities(now=_NOW)
        offers = capability.inspect_offers(now=_NOW)
        health = capability.health(now=_NOW)
        reserved = capability.reserve(
            kind="storage", quantity=_FAMILY_RESERVE[family], unit="bytes",
            purpose="m022-%s-isolation" % family, now=_NOW,
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
        # NO opaque family technology reference crosses into ANY
        # canonical record byte (the caller-supplied wiring data is a
        # WORK-011 path fingerprint — an ordinary route identity, never
        # a mesh handle; the provider-SDK bearer/link/bundle HANDLES
        # stay behind the WORK-016 runtime, keyed internally)
        for record in records:
            blob = canonical_json_bytes(record.to_dict())
            if b"mesh:" in blob:
                return fail(
                    name,
                    "%s: an opaque family technology reference crossed the "
                    "boundary into a canonical record" % family,
                )
        # the activation ledger's binding id is the ADCOS
        # content-derived id (sha256:), never the opaque bearer ref
        if not activated.value.binding_id.startswith("sha256:"):
            return fail(name, "%s binding id is not content-derived" % family)
        # the LOCK-112 mechanism tags ride as citation DATA in the views
        if inspected.value.standard_mechanisms != _FAMILY_MECHANISMS[family]:
            return fail(name, "%s view tags mismatch" % family)
    # the composition modules branch on NO technology name (the M007
    # case_09 discipline — the scan covers the modules' OWN declared
    # vocabulary; identifiers IMPORTED from the accepted surfaces are
    # the by-reference composition itself, excluded exactly as the
    # accepted audits scoped themselves)
    forbidden = ("80211", "8023", "8021q", "g709", "imt2020", "imt2030",
                 "wifi", "wi-fi", "bluetooth", "microwave", "entangled",
                 "synthetic", "ethernet", "fiber", "enterprise",
                 "wireline", "fivegc", "backhaul")
    for path in (REPO_ROOT / "adapters" / "reference" / "satellite.py",
                 REPO_ROOT / "accesstech" / "satellite.py"):
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
        "references in ANY canonical record byte (the wiring data is the "
        "ordinary WORK-011 path fingerprint); the LOCK-112 tags are "
        "citation DATA; the composition modules branch on no other "
        "technology name",
    )


def case_13_typed_errors_fail_closed() -> Result:
    name = "case_13_typed_errors_fail_closed"
    store, sid = ads._established_session()
    registration, _wiring = _register_family(store, "mesh-iab")
    capability = registration.resolve_capability_adapter()
    requirements = dict(registration.binding_requirements)
    reserved = capability.reserve(
        kind="storage", quantity=1_000, unit="bytes",
        purpose="m022-failclosed", now=_NOW,
    )
    if not reserved.ok:
        return fail(name, "reserve failed")
    # (a) isolated failure VALUES (deterministic reasons, twice each —
    # fail-closed determinism): capacity exhaustion, identity
    # smuggling, unknown route, unknown requirement key
    isolated_probes = [
        ("capacity exhaustion", lambda: capability.reserve(
            kind="storage", quantity=300_000_000, unit="bytes",
            purpose="too-big", now=_NOW), "capacity-exhausted"),
        ("identity smuggling", lambda: capability.activate(
            reservation_id=reserved.value.allocation_id, session_id=sid,
            requirements={"session_id": "smuggled"}, now=_NOW), "adapter-failure"),
        ("unknown route", lambda: capability.activate(
            reservation_id=reserved.value.allocation_id, session_id=sid,
            requirements={"route_ref": "sha256:" + "0" * 64}, now=_NOW), "adapter-failure"),
        ("unknown requirement key", lambda: capability.activate(
            reservation_id=reserved.value.allocation_id, session_id=sid,
            requirements={"route_ref": requirements["route_ref"],
                          "banana": 1}, now=_NOW), "adapter-failure"),
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
            kind="bandwidth", quantity=10, unit="mbps",
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
    # (d) the composition-side chain-shape and declaration
    # rejections re-fire identically (fail-closed twice)
    reader = ads._mesh_session_reader(store)
    nodes = _FAMILY_CHAINS["gso"]
    path = _satellite_path(nodes, _FAMILY_LEG_LATENCY["gso"])
    for probe in range(2):
        outcome = expect_mesh_error(
            name, "invalid-input",
            lambda: satref.mount_gso_reference(
                reader, now=_T0, node_ids=nodes + (_NODE_SAT_1,), path=path,
            ),
        )
        if not outcome[1]:
            return fail(name, "chain-shape rejection %d: %s" % (probe, outcome[2]))
        outcome = expect_typed(
            name, "accesstech-envelope-inconsistent",
            lambda: sat.require_pass_shaped_envelope(
                sat.NON_TERRESTRIAL_ENVELOPES["gso"]),
        )
        if not outcome[1]:
            return fail(name, "pass-shape rejection %d: %s" % (probe, outcome[2]))
        outcome = expect_typed(
            name, "accesstech-envelope-inconsistent",
            lambda: sat.propagation_margin_ms(
                sat.NON_TERRESTRIAL_ENVELOPES["gso"], 250),
        )
        if not outcome[1]:
            return fail(name, "margin rejection %d: %s" % (probe, outcome[2]))
    return ok(
        name,
        "the typed fail-closed matrix: 4 isolated failure classes "
        "(deterministic reasons, twice each), 4 caller-side typed raises, "
        "3 terminal-state rejections, and the composition/declaration "
        "rejections re-fire identically — never warnings",
    )


# ---------------------------------------------------------------------------
# (g) the one-way boundary, the delta audit, determinism, evidence
# ---------------------------------------------------------------------------


def _origin_main_available() -> bool:
    probe = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/main"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    return probe.returncode == 0


def case_14_one_way_import_audit() -> Result:
    name = "case_14_one_way_import_audit"
    problems: List[str] = []
    # (a) no accepted authority imports the new modules (AST tokens,
    # not docstrings): neither ``adapters.reference.satellite`` nor
    # ``accesstech.satellite`` is referenced in authority CODE
    # (the new modules themselves are the delivery, not the protected
    # authorities — excluded from the scan)
    authorities = (
        "contracts", "replan", "executionplans", "evidence", "assurance",
        "offers", "eligibility", "policy", "adapters", "usage", "commercial",
        "allocation", "payment", "sharenet", "roamlink", "comos",
        "developerapi", "federation", "identity", "upgrade", "scale",
        "client", "resilience", "localfirst", "recovery", "credentials",
        "accesstech",
    )
    new_modules = (
        REPO_ROOT / "adapters" / "reference" / "satellite.py",
        REPO_ROOT / "accesstech" / "satellite.py",
    )

    def _references_module(source: str) -> bool:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return False
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "satellite":
                return True
            if isinstance(node, ast.Attribute) and node.attr == "satellite":
                return True
            if isinstance(node, ast.ImportFrom) and node.module and (
                "satellite" in node.module
            ):
                return True
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "satellite" in alias.name:
                        return True
        return False

    for package in authorities:
        package_dir = REPO_ROOT / package
        if not package_dir.is_dir():
            continue
        for path in sorted(package_dir.glob("*.py")):
            if path in new_modules:
                continue  # the delivery's own new modules
            source = path.read_text(encoding="utf-8")
            if "satellite" in source and _references_module(source):
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
            if isinstance(node, ast.ImportFrom) and node.module and "satellite" in (
                node.module or ""
            ):
                problems.append("%s imports the new module" % init_path.name)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "satellite" in alias.name:
                        problems.append("%s imports the new module" % init_path.name)
    # (b) the new modules' own import discipline:
    # adapters/reference/satellite.py NEVER imports accesstech (the
    # one-way boundary) nor any legacy 1.0 reservoir package nor any
    # contracts surface; accesstech/satellite.py imports only the
    # accepted accesstech surface via relative imports plus the
    # stdlib/protocol modules the accepted accesstech core itself
    # imports (hashlib/re/dataclasses/typing — the accepted audit's
    # own allowed set)
    composition_path = REPO_ROOT / "adapters" / "reference" / "satellite.py"
    declarations_path = REPO_ROOT / "accesstech" / "satellite.py"
    composition_tree = ast.parse(composition_path.read_text(encoding="utf-8"))
    for node in ast.walk(composition_tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] == "accesstech":
                problems.append("adapters/reference/satellite.py imports accesstech")
            if node.module and node.module.split(".")[0] in (
                "imt", "transport", "topology", "networkpath", "sessions",
                "mobility", "multipath", "edge", "appliance", "mobile",
                "management", "simulator", "resources", "services",
                "contracts",
            ):
                problems.append(
                    "adapters/reference/satellite.py imports %s" % node.module
                )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in ("accesstech", "contracts"):
                    problems.append(
                        "adapters/reference/satellite.py imports %s" % root
                    )
    declarations_tree = ast.parse(declarations_path.read_text(encoding="utf-8"))
    allowed_roots = {
        "__future__", "typing", "hashlib", "re", "dataclasses", "protocol",
    }
    for node in ast.walk(declarations_tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            root = node.module.split(".")[0]
            if root not in allowed_roots:
                problems.append(
                    "accesstech/satellite.py imports the non-relative %s" % root
                )
        elif isinstance(node, ast.ImportFrom) and node.level > 0:
            continue  # the accepted accesstech surface, relatively imported
        elif isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in allowed_roots:
                    problems.append(
                        "accesstech/satellite.py imports the non-relative %s" % root
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
        "untouched; adapters/reference/satellite.py never imports accesstech "
        "(nor contracts nor the legacy reservoir); accesstech/satellite.py "
        "imports only the accepted accesstech surface (relative) + the "
        "stdlib/protocol set the accepted core itself imports; both modules "
        "clock/random/network-free" % len(authorities),
    )


def case_15_zero_contract_core_delta() -> Result:
    name = "case_15_zero_contract_core_delta"
    # (a) the AST import audit: the new modules import NO contracts
    # surface AT ALL (the battery's handover fixtures are the BATTERY's
    # own fixtures — the modules never touch the contract core)
    for path in (REPO_ROOT / "adapters" / "reference" / "satellite.py",
                 REPO_ROOT / "accesstech" / "satellite.py"):
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


def _pass_handover_material() -> bytes:
    """The canonical material of the full NGSO pass-handover drive
    (+ the LEO sibling transition): the decisions, sessions and
    reconnect evidence, rebuilt fresh (deterministic)."""
    constraints = _pass_contract_constraints()
    _store, contract = _mature_pass_contract(constraints)
    store, session = _pass_runtime_session(contract, sat.NGSO_SERVING_REFS[0])
    material: List[bytes] = []
    for transition in sat.NGSO_PASS_SCHEDULE.pass_transitions():
        result = _drive_pass_handover(contract, store, session.runtime_id, transition)
        material.append(
            canonical_json_bytes(result.decision.to_dict())
            if hasattr(result.decision, "to_dict")
            else canonical_json_bytes({"decision_id": result.decision.decision_id})
        )
        material.append(
            canonical_json_bytes(
                {
                    "state": result.session.state,
                    "route": result.session.route_decision_id,
                    "path": result.session.path_id,
                }
            )
        )
    for record in store.reconnect_evidence(session.runtime_id):
        material.append(canonical_json_bytes(record.to_dict()))
    leo_transition = sat.LEO_PASS_SCHEDULE.pass_transitions()[0]
    _store2, contract2 = _mature_pass_contract(constraints)
    store2, session2 = _pass_runtime_session(contract2, sat.LEO_SERVING_REFS[0])
    result2 = _drive_pass_handover(contract2, store2, session2.runtime_id, leo_transition)
    material.append(
        canonical_json_bytes({"decision_id": result2.decision.decision_id})
    )
    return b"".join(material)


def _dtn_drill_digest() -> bytes:
    """The canonical material of the mesh/IAB DTN drill (a fresh
    mount, the full drill trail — deterministic)."""
    store, sid = ads._established_session()
    _bridge, _descriptor, _requirements, wiring = _mount_family(store, "mesh-iab")
    trail = _dtn_drill(wiring, store, sid)
    return canonical_json_bytes(
        {
            "bundle_ref": trail["bundle_ref"],
            "verdicts": [str(v) for v in trail["verdicts"]],
            "deferred_state": str(trail["deferred_state"]),
            "deferred_position": trail["deferred_position"],
            "delivered_payload": trail["delivered_payload"].decode(),
            "drained": trail["drained"].decode(),
        }
    )


def case_16_determinism_byte_identical() -> Result:
    name = "case_16_determinism_byte_identical"
    # (a) in-process rebuild: the whole non-terrestrial surface
    # re-registered from scratch -> byte-identical canonical bytes and
    # identities
    store, sid = ads._established_session()
    registry_first, registrations_first, wirings_first = _register_all(store)
    flows_first = {
        family: _full_flow(registrations_first[family], family, sid)
        for family in FAMILIES
    }
    registry_second, registrations_second, _wirings_second = _register_all(store)
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
    if registry_first.technology_classes() != registry_second.technology_classes():
        return fail(name, "registry order differs on rebuild")
    if sat.NGSO_PASS_SCHEDULE.to_canonical_bytes() != sat.pass_schedule_from_mapping(
        sat.NGSO_PASS_SCHEDULE.to_dict()
    ).to_canonical_bytes():
        return fail(name, "pass schedule bytes differ on rebuild")
    # the pass-handover drive and the DTN drill rebuild byte-identical
    if _pass_handover_material() != _pass_handover_material():
        return fail(name, "the pass-handover material differs on rebuild")
    if _dtn_drill_digest() != _dtn_drill_digest():
        return fail(name, "the DTN drill material differs on rebuild")
    # (b) cross-process: the registration + lifecycle + handover + DTN
    # material built in PYTHONHASHSEED 0/1/42 subprocesses ->
    # byte-identical digests
    probe = r"""
import sys
sys.path.insert(0, %r)
sys.path.insert(0, %r)
import hashlib
import adapter_selftest as ads
import satellite_selftest as m022
from accesstech import satellite as sat
store, sid = ads._established_session()
registry, registrations, wirings = m022._register_all(store)
material = b"".join(
    registrations[family].to_canonical_bytes()
    for family in m022.FAMILIES
)
material += sat.NGSO_PASS_SCHEDULE.to_canonical_bytes()
material += sat.LEO_PASS_SCHEDULE.to_canonical_bytes()
for family in m022.FAMILIES:
    material += b"".join(m022._full_flow(registrations[family], family, sid))
material += m022._pass_handover_material()
material += m022._dtn_drill_digest()
print(hashlib.sha256(material).hexdigest())
print(" ".join(r[6:] for r in (
    registrations[f].registration_id for f in m022.FAMILIES
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
            "satellite material differs across PYTHONHASHSEED subprocesses "
            "(%d distinct outputs)" % len(outputs),
        )
    return ok(
        name,
        "in-process rebuild byte-identical (registrations, envelopes, "
        "ladders, lifecycle records, registry order, pass-handover "
        "material, DTN drill trails); the full non-terrestrial material "
        "byte-identical across PYTHONHASHSEED 0/1/42 subprocesses",
    )


def case_17_evidence_doc_honest() -> Result:
    name = "case_17_evidence_doc_honest"
    path = REPO_ROOT / "docs" / "M022-evidence.md"
    if not path.exists():
        return fail(name, "docs/M022-evidence.md is missing")
    text = path.read_text(encoding="utf-8")
    problems: List[str] = []
    if "SOFTWARE" not in text:
        problems.append("the evidence class is not disclosed")
    if "M022" not in text:
        problems.append("the evidence does not name M022")
    for lock in ("LOCK-105", "LOCK-108", "LOCK-110", "LOCK-112", "LOCK-106", "LOCK-119"):
        if lock not in text:
            problems.append("the %s mapping is not disclosed" % lock)
    if "EVID-002" not in text:
        problems.append("the open physical evidence obligations are not disclosed")
    if "by reference" not in text.lower():
        problems.append("the by-reference composition is not disclosed")
    if "case_68" not in text:
        problems.append("the adapter-battery delta-guard conflict is not disclosed")
    if "accesstech" not in text and "no-tech-branching" not in text:
        problems.append("the accesstech audit coexistence is not disclosed")
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
        "adapter-battery conflict, the accesstech audit coexistence and "
        "the open physical obligations disclosed; no affirmative physical "
        "claims",
    )


# ===========================================================================
# Main
# ===========================================================================


def main() -> int:
    results: List[Result] = []
    results.append(case_01_family_declarations_round_trip())
    results.append(case_02_deterministic_coverage_windows())
    results.append(case_03_propagation_delay_typed_ranges())
    results.append(case_04_propagation_margin_ladders())
    results.append(case_05_declared_pass_schedules())
    results.append(case_06_families_registered_through_extension_surface())
    results.append(case_07_registration_resolves_by_reference())
    results.append(case_08_nine_operations_reserve_activate_measure())
    results.append(case_09_rebind_translation_mid_session())
    results.append(case_10_ngso_pass_handover_geometry())
    results.append(case_11_mesh_iab_sidelink_dtn_extension())
    results.append(case_12_lock110_provider_sdk_isolation())
    results.append(case_13_typed_errors_fail_closed())
    results.append(case_14_one_way_import_audit())
    results.append(case_15_zero_contract_core_delta())
    results.append(case_16_determinism_byte_identical())
    results.append(case_17_evidence_doc_honest())

    print("ADCOS non-terrestrial access self-test (M022 — Non-Terrestrial Access Adapters)")
    print("=" * 90)
    for name, passed, detail in results:
        print("[%s] %-56s %s" % ("ok  " if passed else "FAIL", name, detail))
    print("-" * 90)
    passed_count = sum(1 for _, p, _ in results if p)
    if passed_count == len(results):
        print("Result: PASS (%d/%d cases)" % (passed_count, len(results)))
        return 0
    print("Result: FAIL (%d/%d cases passed)" % (passed_count, len(results)))
    return 1


if __name__ == "__main__":
    sys.exit(main())
