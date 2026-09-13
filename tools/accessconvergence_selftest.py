#!/usr/bin/env python3
"""ADCOS future access convergence self-test (M024).

Deterministic, offline verification of the M024 delivery — the
``accesstech/convergence.py`` R9 convergence surface composed over the
accepted M020/M021/M022/M023 child authorities — against the R9
charter M024 scope (R9-CORE-001, DEC-0120; the convergence child whose
acceptance completes the R9 gate — the terminal roadmap gate — and
evaluates the program_exit conditions):

- (a) case_01..case_03 — the CROSS-TECHNOLOGY INTERCHANGE DRILL:
  deterministic technology handovers wireline <-> radio-family <->
  non-terrestrial with LOCK-108 VERBATIM constraint-set equality at
  every step, driven through the accepted ``resilience/`` handover
  machinery (``perform_handover`` over the RUNTIME journal).  The
  composed technologies are the accepted M021 wireline composition,
  the accepted M007 radio-family composition and the accepted M022
  non-terrestrial composition, mounted through their OWN public
  factories and registered through the accepted M020 registration
  surface (this battery is the composition root — the
  M014/M019 discipline), consumed by the drill as registration
  records.  Every hop an EXPLICIT recorded reconnect naming BOTH the
  old AND the new references (WORK-012); the fail-closed probes cover
  the machinery's weakened-candidate discipline (the typed
  kind-citing rejection, the EXPLICIT FAILED landing, zero silent
  reconnects), the machinery's silent-completion gate, and the
  drill's own typed gates (unregistered class, undeclared
  cross-technology kind, plan discipline);
- (b) case_04..case_05 — the technology REPLACEMENT DRILL (the "or
  replace" half of the gate objective): a LIVE radio technology
  replaced by the accepted M023 future-IMT technology under an ACTIVE
  contract with CONTRACT CONTINUITY — every replacement an explicit
  recorded reconnect naming old AND new references, never a silent
  swap (the silent-swap record shape is a typed failure; the
  machinery's silent-completion gate is probed typed);
- (c) case_06..case_07 — the CONVERGED-DOMAIN COMPATIBILITY MATRIX
  extended over the R9 domains (the accepted ``upgrade/`` matrix
  discipline extended: the frozen MAJOR.MINOR grammar, the frozen
  verdict vocabulary pinned against the accepted engine's own set,
  sorted-domain iteration, input-order independence, byte-stable
  digests) composed with the accepted upgrade engine's OWN
  R7-substrate rows and the accepted M019 R8 matrix rows into ONE
  converged matrix;
- (d) case_08 — FEDERATION-SCALE CONVERGENCE over the R9 domains: the
  drill's REAL material (the interchange and replacement handover
  decisions) cited through the accepted ``federation.convergence``
  cite-* constructors, propagated across the accepted multi-domain
  federation harness (``scale.convergence``) with declared
  deterministic bounds, the revocation propagated in
  topology-predicted rounds, the replay byte-identical, and the M024
  verifier's composed report stable;
- (e) case_09 — the BY-REFERENCE COMPOSITION AUDIT (the
  M014/M019 discipline): one-way imports (no accepted authority
  references the new module; the module imports only the accepted
  one-way set; ZERO contracts imports — the M020
  zero-contract-import discipline preserved); the module never
  references the M021/M022/M023 composition modules (the composition
  happens through the accepted registration surface);
- (f) case_10 — LOCK-110 provider-SDK isolation: the drill records'
  canonical bytes carry no opaque family technology references; no
  technology-branching names in the module's own vocabulary; the
  registrations resolve through the accepted
  ``adapters/capability.py`` seam (the mediated boundary);
- (g) case_11..case_13 — LOCK-119 purity + typed errors + determinism
  (in-process rebuild byte-identical; the full drill material
  byte-identical across PYTHONHASHSEED 0/1/42 subprocesses);
- (h) case_14..case_15 — the zero contract-core delta + authorization
  scope audit (the delivery delta exactly the declared M024 files,
  fully covered by R9-CORE-001; the contract state unchanged through
  the drills) and the evidence-doc honesty (SOFTWARE class only; the
  program_exit completion review recorded SOFTWARE-class; EVID-002..
  EVID-008 stay open — never a PHYSICAL PASS claim).

The central boundary is exercised throughout:

    R9 CONVERGENCE SURFACE
        = the accepted machinery composed BY REFERENCE (the
          resilience/ handover engine, the replan LOCK-108 gates,
          the upgrade/ matrix discipline, the scale/ harness, the
          M020 registration surface)
        != CONTRACT AUTHORITY (contracts/ stays the sole authority;
          the module imports no contracts type at all)
        != A SECOND HANDOVER ENGINE (the accepted machinery drives
          every handover; this surface verifies and types)
        != THE FAMILY RUNTIMES (the compositions enter as
          registration records through the accepted seam — LOCK-110)

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

from adapters.capability import CapabilityAdapter  # noqa: E402

# The accepted resilience-side handover machinery the drills compose
# through (BY REFERENCE — the M015 surface).
from resilience import (  # noqa: E402
    ResilienceError,
    RuntimeStore,
    handover_candidate,
    handover_verdict,
    perform_handover,
    validate_handover_preserves_contract,
)
from replan import verify_decision_preserves_contract  # noqa: E402

# The accepted M020 registration surface (the composition root's path
# for every technology entering the drills) and the M024 module.
import accesstech  # noqa: E402
from accesstech import (  # noqa: E402
    BpsRange,
    CapabilityEnvelope,
    AvailabilityWindow,
    AvailabilityWindows,
    DegradationLadder,
    DegradationMode,
    JitterMilliRange,
    LatencyMilliRange,
    TechnologyRegistry,
    declare_handover_kind,
    preserved_constraint_kinds,
    register_access_technology,
)
from accesstech.errors import AccessTechError  # noqa: E402
import accesstech.convergence as acv  # noqa: E402

# The four accepted R9 child authorities composed BY REFERENCE (this
# battery is the composition root): the M021 wireline composition +
# declarations, the M022 non-terrestrial composition + declarations,
# the M007 radio-family composition and the M023 future-IMT
# composition, each imported through its OWN public module.
from adapters.reference import ran as ranref  # noqa: E402
from adapters.reference import futureimt as fref  # noqa: E402

# The accepted matrix surfaces the composed matrix consumes: the R7
# substrate engine (upgrade/convergence) and the R8 matrix
# (resilience/convergence — the M019 surface).
from upgrade.convergence import (  # noqa: E402
    CONVERGED_DOMAIN_SET,
    DOMAIN_COMPATIBILITY_VERDICTS,
    DomainVersion,
    negotiate_converged_compatibility,
)
from resilience.convergence import (  # noqa: E402
    R8_CONVERGENCE_DOMAINS,
    ConvergenceDomainVersion,
    MATRIX_VERDICTS as R8_MATRIX_VERDICTS,
    negotiate_r8_matrix,
)

# The accepted federation citation constructors (the R9 drill material
# cited through the REAL accepted surface) and the accepted scale
# harness (the federation-scale convergence engine).
from federation.convergence import cite_replan_decision  # noqa: E402
from scale.convergence import (  # noqa: E402
    ConvergenceCitationPlan,
    ConvergenceRevocationPlan,
    ConvergenceScenarioSpec,
    run_convergence_scenario,
    verify_convergence_replay,
)
from scale.model import ScaleEventType, TopologyShape  # noqa: E402
from scale.topology import delivery_distances, topology_edges  # noqa: E402

# The sibling batteries' public mounting fixtures (the case_66
# cross-battery import precedent — the M020/M021/M022 batteries' own
# pattern): the M007 reader facades + session store, the M021 wireline
# registration helper and the M022 non-terrestrial registration
# helper.
import adapter_selftest as ads  # noqa: E402
import wireline_selftest as wbs  # noqa: E402
import satellite_selftest as sbs  # noqa: E402

Result = Tuple[str, bool, str]

WIRELINE_TECHNOLOGY_CLASS = wbs.wire.REFERENCE_TECHNOLOGY_ID  # access.ieee.8023
RADIO_TECHNOLOGY_CLASS = ranref.REFERENCE_TECHNOLOGY_ID  # access.3gpp.nr.imt2020
NONTERRESTRIAL_TECHNOLOGY_CLASS = sbs.satref.NGSO_TECHNOLOGY_ID  # access.satellite.ngso
FUTURE_TECHNOLOGY_CLASS = fref.REFERENCE_TECHNOLOGY_ID  # access.3gpp.nr.imt2030


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

#: The contract lifecycle instants.
_CONTRACT_CREATED = "2026-05-01T00:00:00Z"
_CONTRACT_SELECTED = "2026-05-02T00:00:00Z"
_CONTRACT_T0 = "2026-06-01T00:00:00Z"
_CONTRACT_T_END = "2026-12-31T23:59:59Z"

#: The runtime-session lifecycle instants.
_R_CREATE = "2026-06-01T11:50:00Z"
_R_ACTIVATE = "2026-06-01T12:00:00Z"

#: The interchange drill's hop instants (strictly increasing).
_T_HOP1 = "2026-06-01T13:10:00Z"
_T_HOP2 = "2026-06-01T14:20:00Z"
_T_HOP3 = "2026-06-01T15:30:00Z"

#: The replacement drill's instant.
_T_REPLACE = "2026-06-01T16:40:00Z"

#: The federation-scale citation instant.
_T_CITE = "2026-06-01T17:00:00Z"

_BATTERY_ISSUER = "m024:convergence-battery"

_OFFER_A = OpaqueReference(
    ref_kind="offer", value="offer:converge-wireline-1",
    provenance=Provenance(issuer="prov:wireline-one"),
)
_OFFER_B = OpaqueReference(
    ref_kind="offer", value="offer:converge-radio-1",
    provenance=Provenance(issuer="prov:radio-one"),
)
_OFFER_C = OpaqueReference(
    ref_kind="offer", value="offer:converge-future-1",
    provenance=Provenance(issuer="prov:future-one"),
)


def _prov(issuer: str, *refs: str) -> Provenance:
    return Provenance(issuer=issuer, decision_refs=tuple(refs))


def _contract_constraints() -> Tuple[HardConstraint, ...]:
    """The drill contract's hard constraints (deterministic fixtures:
    the declared service latency budget + the availability floor)."""
    return (
        HardConstraint(
            kind="latency-bound",
            params={"max_ms": 400},
            provenance=_prov("prov:converge-one"),
        ),
        HardConstraint(
            kind="availability-floor",
            params={"nine": "three"},
            provenance=_prov("prov:converge-one"),
        ),
    )


def _create_command(
    constraints: Tuple[HardConstraint, ...]
) -> CreateContract:
    return CreateContract(
        principal=ConnectivityPrincipal(
            principal_kind="APPLICATION", principal_ref="app:converge-gw-01"
        ),
        beneficiaries=(
            BeneficiaryScope(
                beneficiary_kind="DEVICE", beneficiary_ref="dev:term-9f2e"
            ),
        ),
        requirements=(
            OpaqueReference(
                ref_kind="intent-requirements",
                value="intent:converge-01",
                provenance=_prov("arch:convergence"),
            ),
        ),
        hard_constraints=constraints,
        validity=ValidityInterval(
            not_before=_CONTRACT_T0, not_after=_CONTRACT_T_END
        ),
        service_properties=(
            OpaqueReference(
                ref_kind="service-property",
                value="prop:committed-converge-1",
                provenance=_prov("prov:converge-one"),
            ),
        ),
        usage_pricing_terms=OpaqueReference(
            ref_kind="usage-pricing-terms",
            value="terms:comm-converge-9",
            provenance=_prov("comm:ops"),
        ),
        assurance_obligations=(
            OpaqueReference(
                ref_kind="assurance-obligation", value="oblig:evid-converge-4"
            ),
        ),
        execution_scope=(
            OpaqueReference(
                ref_kind="execution-scope", value="scope:exec-converge"
            ),
        ),
        termination=TerminationRules(
            conditions=("principal-requested", "constraint-violated"),
            compensation=OpaqueReference(
                ref_kind="compensation",
                value="comp:rule-converge-3",
                provenance=_prov("comm:ops"),
            ),
        ),
        provenance=_prov("arch:convergence", "dec:elig-converge-1"),
    )


def _mature_contract():
    """A contract store whose single contract is EXECUTION_ACTIVE
    (deterministic; rebuilt per call so mutating cases stay
    isolated)."""
    store = ContractStore()
    created = store.submit(
        _create_command(_contract_constraints()),
        recorded_at=_CONTRACT_CREATED,
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
                    ref_kind="signature", value="sig:ed25519-converge-1"
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


def _runtime_session(contract: Any, initial_ref: str):
    """A fresh runtime store whose single session is ACTIVE on the
    initial realization references."""
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
# The composition root: the four accepted R9 child technologies
# registered through the accepted M020 surface
# ---------------------------------------------------------------------------

#: The RAN family's declared capability envelope + ladder (the
#: composition root's own declared fixtures over the accepted M007
#: composition — the accesstech battery's family-fixture shape).
_RADIO_ENVELOPE = CapabilityEnvelope(
    technology_class=RADIO_TECHNOLOGY_CLASS,
    bandwidth=BpsRange(1_000_000, 1_000_000_000),
    latency=LatencyMilliRange(5, 50),
    jitter=JitterMilliRange(0, 20),
    availability=AvailabilityWindows(
        (AvailabilityWindow("2026-01-01T00:00:00Z", "2026-12-31T23:59:59Z"),)
    ),
)
_RADIO_LADDER = DegradationLadder(
    technology_class=RADIO_TECHNOLOGY_CLASS,
    modes=(
        DegradationMode("nominal", "REALIZING"),
        DegradationMode("coverage-edge", "DEGRADED"),
        DegradationMode("congestion", "DEGRADED"),
        DegradationMode("radio-link-failed", "FAILED"),
    ),
)

#: The future-IMT family's declared capability envelope + ladder (the
#: composition root's own declared fixtures over the accepted M023
#: composition).
_FUTURE_ENVELOPE = CapabilityEnvelope(
    technology_class=FUTURE_TECHNOLOGY_CLASS,
    bandwidth=BpsRange(1_000_000_000, 400_000_000_000),
    latency=LatencyMilliRange(1, 5),
    jitter=JitterMilliRange(0, 2),
    availability=AvailabilityWindows(
        (AvailabilityWindow("2026-01-01T00:00:00Z", "2026-12-31T23:59:59Z"),)
    ),
)
_FUTURE_LADDER = DegradationLadder(
    technology_class=FUTURE_TECHNOLOGY_CLASS,
    modes=(
        DegradationMode("nominal", "REALIZING"),
        DegradationMode("coherence-degraded", "DEGRADED"),
        DegradationMode("channel-failed", "FAILED"),
    ),
)


def _mount_registry(store):
    """The composition root: register the four accepted R9 child
    technologies (the M021 wireline ethernet family, the M007
    radio-family RAN composition, the M022 non-terrestrial NGSO
    family and the M023 future-IMT composition) through the accepted
    M020 registration surface — each mounted through its OWN public
    factory, each registered with declared envelope/ladder/handover
    declarations, ZERO contract-core delta."""
    registry = TechnologyRegistry()
    # (a) the accepted M021 wireline composition (ethernet family —
    # the wireline battery's own registration helper, BY REFERENCE)
    wireline_registration, _links = wbs._register_family(store, "ethernet")
    registry.register(wireline_registration)
    # (b) the accepted M007 radio-family composition (RAN — its own
    # public mount factory, registered with the composition root's
    # declared fixtures; the family declares the cross-technology AND
    # replacement kinds for the drills)
    radio_implementation, radio_descriptor, _radio_requirements = (
        ranref.mount_reference(now=_T0)
    )
    radio_registration = register_access_technology(
        envelope=_RADIO_ENVELOPE,
        ladder=_RADIO_LADDER,
        handovers=(
            declare_handover_kind("intra-technology"),
            declare_handover_kind("cross-technology"),
            declare_handover_kind("replacement"),
        ),
        implementation=radio_implementation,
        descriptor=radio_descriptor,
        binding_requirements={},
        mechanisms=ranref.STANDARD_MECHANISMS,
        session_store=store,
        now=_T0,
    )
    registry.register(radio_registration)
    # (c) the accepted M022 non-terrestrial composition (NGSO family —
    # the satellite battery's own registration helper, BY REFERENCE)
    nonterrestrial_registration, _wiring = sbs._register_family(store, "ngso")
    registry.register(nonterrestrial_registration)
    # (d) the accepted M023 future-IMT composition (its own public
    # mount factory, registered with the composition root's declared
    # fixtures; the future technology declares all four handover
    # kinds — the replacement drill's target)
    future_implementation, future_descriptor, _future_requirements = (
        fref.mount_reference(now=_T0)
    )
    future_registration = register_access_technology(
        envelope=_FUTURE_ENVELOPE,
        ladder=_FUTURE_LADDER,
        handovers=(
            declare_handover_kind("intra-technology"),
            declare_handover_kind("cross-technology"),
            declare_handover_kind("pass"),
            declare_handover_kind("replacement"),
        ),
        implementation=future_implementation,
        descriptor=future_descriptor,
        binding_requirements={},
        mechanisms=fref.STANDARD_MECHANISMS,
        session_store=store,
        now=_T0,
    )
    registry.register(future_registration)
    return registry


#: The interchange drill's declared hop chain: wireline -> radio-family
#: -> non-terrestrial -> wireline (the full domain circle, every hop
#: crossing domains, the technology chain chained end to end).
_INTERCHANGE_HOPS = (
    acv.InterchangeHop(
        position=0,
        from_domain="wireline",
        to_domain="radio-family",
        from_class=WIRELINE_TECHNOLOGY_CLASS,
        to_class=RADIO_TECHNOLOGY_CLASS,
        new_route_decision_id="m024:radio-ran",
        new_path_id="path:m024:radio-ran",
        reconnect_instant=_T_HOP1,
    ),
    acv.InterchangeHop(
        position=1,
        from_domain="radio-family",
        to_domain="non-terrestrial",
        from_class=RADIO_TECHNOLOGY_CLASS,
        to_class=NONTERRESTRIAL_TECHNOLOGY_CLASS,
        new_route_decision_id="m024:nt-ngso",
        new_path_id="path:m024:nt-ngso",
        reconnect_instant=_T_HOP2,
    ),
    acv.InterchangeHop(
        position=2,
        from_domain="non-terrestrial",
        to_domain="wireline",
        from_class=NONTERRESTRIAL_TECHNOLOGY_CLASS,
        to_class=WIRELINE_TECHNOLOGY_CLASS,
        new_route_decision_id="m024:wireline-return",
        new_path_id="path:m024:wireline-return",
        reconnect_instant=_T_HOP3,
    ),
)


def _interchange_fixture():
    """The full interchange drill fixture: the mature contract, the
    registered technologies (mounted over a real WORK-012 session
    store), the live runtime session on the wireline realization, and
    the driven drill result."""
    contract_store, contract = _mature_contract()
    session_store, _sid = ads._established_session()
    registry = _mount_registry(session_store)
    store, session = _runtime_session(contract, "m024:wireline-eth")
    plan = acv.InterchangeDrillPlan(
        contract_id=contract.contract_id,
        runtime_id=session.runtime_id,
        trigger_kind="route-expiry",
        hops=_INTERCHANGE_HOPS,
    )
    result = acv.run_interchange_drill(
        plan, registry, store, contract, session.runtime_id
    )
    return {
        "contract_store": contract_store,
        "contract": contract,
        "store": store,
        "session": session,
        "registry": registry,
        "plan": plan,
        "result": result,
    }


def _replacement_fixture():
    """The replacement drill fixture: a fresh mature contract, the
    registered technologies (mounted over a real WORK-012 session
    store), a live session on the radio realization, and the driven
    replacement."""
    contract_store, contract = _mature_contract()
    session_store, _sid = ads._established_session()
    registry = _mount_registry(session_store)
    store, session = _runtime_session(contract, "m024:radio-live")
    record = acv.replace_technology(
        registry,
        store,
        session.runtime_id,
        contract,
        old_class=RADIO_TECHNOLOGY_CLASS,
        new_class=FUTURE_TECHNOLOGY_CLASS,
        new_route_decision_id="m024:future-imt",
        new_path_id="path:m024:future-imt",
        reconnect_instant=_T_REPLACE,
        trigger_kind="route-expiry",
    )
    return {
        "contract_store": contract_store,
        "contract": contract,
        "store": store,
        "session": session,
        "registry": registry,
        "record": record,
    }


# ---------------------------------------------------------------------------
# The typed-error probe helper
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


# ---------------------------------------------------------------------------
# (a) the cross-technology interchange drill
# ---------------------------------------------------------------------------


def case_01_interchange_plan_declarations() -> Result:
    name = "case_01_interchange_plan_declarations"
    fixture = _interchange_fixture()
    plan = fixture["plan"]
    contract = fixture["contract"]
    problems: List[str] = []
    # the plan's declared surface: the domain circle covers all three
    # cross domains; the technology chain chains; the instants
    # strictly increase; the identity is content-derived
    if [hop.from_domain for hop in plan.hops] != [
        "wireline", "radio-family", "non-terrestrial"
    ]:
        problems.append("the from-domain chain drifted")
    if [hop.to_domain for hop in plan.hops] != [
        "radio-family", "non-terrestrial", "wireline"
    ]:
        problems.append("the to-domain chain drifted")
    if (plan.hops[0].to_class, plan.hops[1].to_class) != (
        plan.hops[1].from_class, plan.hops[2].from_class
    ):
        problems.append("the technology chain does not chain")
    covered = {hop.from_domain for hop in plan.hops} | {
        hop.to_domain for hop in plan.hops
    }
    if covered != set(acv.CROSS_DOMAINS):
        problems.append("the plan does not cover all three cross domains")
    # canonical round-trip: the plan's canonical bytes and identity are
    # stable and tamper-evident
    first = plan.to_canonical_bytes()
    if acv.InterchangeDrillPlan(
        contract_id=plan.contract_id,
        runtime_id=plan.runtime_id,
        trigger_kind=plan.trigger_kind,
        hops=plan.hops,
        drill_id=plan.drill_id,
    ).to_canonical_bytes() != first:
        problems.append("the plan round-trip drifted")
    try:
        acv.InterchangeDrillPlan(
            contract_id=plan.contract_id,
            runtime_id=plan.runtime_id,
            trigger_kind=plan.trigger_kind,
            hops=plan.hops,
            drill_id="sha256:" + "0" * 64,
        )
        problems.append("a tampered drill identity was accepted")
    except AccessTechError:
        pass
    # the plan-level fail-closed discipline (typed rejections)
    probes: List[Tuple[str, str, Callable[[], Any]]] = [
        ("single hop", "accesstech-envelope-degenerate",
         lambda: acv.InterchangeDrillPlan(
             contract_id=contract.contract_id,
             runtime_id="sha256:" + "1" * 64,
             trigger_kind="route-expiry",
             hops=_INTERCHANGE_HOPS[:1],
         )),
        ("domain not crossed", "accesstech-envelope-inconsistent",
         lambda: acv.InterchangeHop(
             position=0, from_domain="wireline", to_domain="wireline",
             from_class=WIRELINE_TECHNOLOGY_CLASS,
             to_class=RADIO_TECHNOLOGY_CLASS,
             new_route_decision_id="m024:x", new_path_id="path:m024:x",
             reconnect_instant=_T_HOP1,
         )),
        ("domain not covered", "accesstech-envelope-inconsistent",
         lambda: acv.InterchangeDrillPlan(
             contract_id=contract.contract_id,
             runtime_id="sha256:" + "2" * 64,
             trigger_kind="route-expiry",
             hops=(
                 acv.InterchangeHop(
                     position=0, from_domain="wireline",
                     to_domain="radio-family",
                     from_class=WIRELINE_TECHNOLOGY_CLASS,
                     to_class=RADIO_TECHNOLOGY_CLASS,
                     new_route_decision_id="m024:a", new_path_id="path:m024:a",
                     reconnect_instant=_T_HOP1,
                 ),
                 acv.InterchangeHop(
                     position=1, from_domain="radio-family",
                     to_domain="wireline",
                     from_class=RADIO_TECHNOLOGY_CLASS,
                     to_class=WIRELINE_TECHNOLOGY_CLASS,
                     new_route_decision_id="m024:b", new_path_id="path:m024:b",
                     reconnect_instant=_T_HOP2,
                 ),
             ),
         )),
        ("unknown cross domain", "accesstech-vocabulary",
         lambda: acv.InterchangeHop(
             position=0, from_domain="wireline", to_domain="orbital",
             from_class=WIRELINE_TECHNOLOGY_CLASS,
             to_class=RADIO_TECHNOLOGY_CLASS,
             new_route_decision_id="m024:x", new_path_id="path:m024:x",
             reconnect_instant=_T_HOP1,
         )),
        ("unknown trigger kind", "accesstech-vocabulary",
         lambda: acv.InterchangeDrillPlan(
             contract_id=contract.contract_id,
             runtime_id="sha256:" + "3" * 64,
             trigger_kind="technology-sunset",
             hops=_INTERCHANGE_HOPS,
         )),
        ("disordered positions", "accesstech-envelope-inconsistent",
         lambda: acv.InterchangeDrillPlan(
             contract_id=contract.contract_id,
             runtime_id="sha256:" + "4" * 64,
             trigger_kind="route-expiry",
             hops=(
                 _INTERCHANGE_HOPS[1],
                 acv.InterchangeHop(
                     position=2, from_domain="non-terrestrial",
                     to_domain="wireline",
                     from_class=NONTERRESTRIAL_TECHNOLOGY_CLASS,
                     to_class=WIRELINE_TECHNOLOGY_CLASS,
                     new_route_decision_id="m024:wireline-return",
                     new_path_id="path:m024:wireline-return",
                     reconnect_instant=_T_HOP3,
                 ),
             ),
         )),
        ("non-increasing instants", "accesstech-envelope-inconsistent",
         lambda: acv.InterchangeDrillPlan(
             contract_id=contract.contract_id,
             runtime_id="sha256:" + "5" * 64,
             trigger_kind="route-expiry",
             hops=(
                 acv.InterchangeHop(
                     position=0, from_domain="wireline",
                     to_domain="radio-family",
                     from_class=WIRELINE_TECHNOLOGY_CLASS,
                     to_class=RADIO_TECHNOLOGY_CLASS,
                     new_route_decision_id="m024:a", new_path_id="path:m024:a",
                     reconnect_instant=_T_HOP2,
                 ),
                 acv.InterchangeHop(
                     position=1, from_domain="radio-family",
                     to_domain="non-terrestrial",
                     from_class=RADIO_TECHNOLOGY_CLASS,
                     to_class=NONTERRESTRIAL_TECHNOLOGY_CLASS,
                     new_route_decision_id="m024:b", new_path_id="path:m024:b",
                     reconnect_instant=_T_HOP1,
                 ),
                 acv.InterchangeHop(
                     position=2, from_domain="non-terrestrial",
                     to_domain="wireline",
                     from_class=NONTERRESTRIAL_TECHNOLOGY_CLASS,
                     to_class=WIRELINE_TECHNOLOGY_CLASS,
                     new_route_decision_id="m024:c", new_path_id="path:m024:c",
                     reconnect_instant=_T_HOP3,
                 ),
             ),
         )),
    ]
    for label, code, action in probes:
        outcome = expect_typed(name, code, action)
        if not outcome[1]:
            return fail(name, "%s: %s" % (label, outcome[2]))
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "the plan covers the full domain circle (wireline -> radio-family "
        "-> non-terrestrial -> wireline), chains end to end, carries "
        "strictly increasing injected instants and a content-derived "
        "tamper-evident identity; 7 malformed-plan classes fail closed "
        "typed",
    )


def case_02_interchange_drill_through_machinery() -> Result:
    name = "case_02_interchange_drill_through_machinery"
    fixture = _interchange_fixture()
    result = fixture["result"]
    contract = fixture["contract"]
    store = fixture["store"]
    session = fixture["session"]
    problems: List[str] = []
    # (a) every hop driven through the ACCEPTED machinery: adopted,
    # LOCK-108 verbatim constraint equality, the explicit reconnect
    # pair, the ACTIVE landing on the new refs
    previous_route = "m024:wireline-eth"
    previous_path = "path:m024:wireline-eth"
    for hop_result in result.hop_results:
        if hop_result.state_after != "ACTIVE":
            problems.append("hop %d did not land ACTIVE" % hop_result.position)
        if hop_result.old_route_decision_id != previous_route:
            problems.append("hop %d lost the OLD route reference" % hop_result.position)
        if hop_result.old_path_id != previous_path:
            problems.append("hop %d lost the OLD path reference" % hop_result.position)
        hop = fixture["plan"].hops[hop_result.position]
        if hop_result.new_route_decision_id != hop.new_route_decision_id:
            problems.append("hop %d lost the NEW route reference" % hop_result.position)
        if hop_result.new_path_id != hop.new_path_id:
            problems.append("hop %d lost the NEW path reference" % hop_result.position)
        if hop_result.reconnect_instant != hop.reconnect_instant:
            problems.append("hop %d reconnect instant drifted" % hop_result.position)
        # LOCK-108: the decision's constraint fingerprint IS the
        # contract's own (verbatim equality across every technology
        # handover), re-verified through the consumed cross-authority
        # gate on the LIVE decision record
        if hop_result.constraint_fingerprint != contract.hard_constraint_fingerprint():
            problems.append("hop %d fingerprint is not the contract's own"
                            % hop_result.position)
        try:
            verify_decision_preserves_contract(hop_result.live_decision, contract)
        except Exception as error:  # noqa: BLE001
            problems.append(
                "hop %d failed the consumed gate: %s" % (
                    hop_result.position, str(error)[:70]
                )
            )
        # WORK-012: the journal ends with the explicit reconnect pair
        events = store.events(session.runtime_id)
        kinds = [event.kind for event in events]
        if "reconnect-initiated" not in kinds or "reconnect-completed" not in kinds:
            problems.append("the journal carries no reconnect pair")
        previous_route = hop.new_route_decision_id
        previous_path = hop.new_path_id
    # (b) the reconnect evidence records: exactly one per declared hop,
    # derived from the journal, chained old->new
    evidence = store.reconnect_evidence(session.runtime_id)
    if len(evidence) != len(fixture["plan"].hops):
        problems.append(
            "reconnect evidence count %d != the declared hops %d"
            % (len(evidence), len(fixture["plan"].hops))
        )
    for record, hop in zip(evidence, fixture["plan"].hops):
        if record.new_route_decision_id != hop.new_route_decision_id:
            problems.append("evidence order does not match the plan")
            break
    # (c) the session's final realization is the last hop's refs; the
    # contract realizes continuity (the same contract, never touched)
    after = store.session(session.runtime_id)
    if (after.route_decision_id, after.path_id) != (
        fixture["plan"].hops[-1].new_route_decision_id,
        fixture["plan"].hops[-1].new_path_id,
    ):
        problems.append("the session did not land on the final hop refs")
    if after.contract_id != contract.contract_id:
        problems.append("the drill broke contract continuity")
    # (d) the drill result: canonical, content-derived, round-trips
    first = result.to_canonical_bytes()
    rebuilt = acv.InterchangeDrillResult(
        drill_id=result.drill_id,
        contract_id=result.contract_id,
        runtime_id=result.runtime_id,
        trigger_kind=result.trigger_kind,
        hop_results=result.hop_results,
        lock108_verified=True,
        drill_result_id=result.drill_result_id,
    )
    if rebuilt.to_canonical_bytes() != first:
        problems.append("the drill result round-trip drifted")
    if result.lock108_verified is not True:
        problems.append("the LOCK-108 verification flag drifted")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "all 3 interchange hops driven through the accepted resilience/ "
        "machinery: LOCK-108 verbatim constraint equality at every step "
        "(the fingerprint IS the contract's own; the consumed "
        "cross-authority gate green on every live decision), the EXPLICIT "
        "reconnect pair naming BOTH old AND new references at the declared "
        "instants, every landing ACTIVE, the journal reconnect evidence "
        "chained, contract continuity preserved, the result canonical and "
        "tamper-evident",
    )


def case_03_interchange_fail_closed() -> Result:
    name = "case_03_interchange_fail_closed"
    fixture = _interchange_fixture()
    contract = fixture["contract"]
    registry = fixture["registry"]
    problems: List[str] = []
    # (a) LOCK-108 at the machinery seam: a WEAKENED candidate
    # constraint set is rejected with the typed kind-citing reason (the
    # raising gate and the verdict twin), and the machinery NEVER
    # adopts it — the EXPLICIT FAILED state, no silent reconnect
    weakened = (
        HardConstraint(
            kind="latency-bound",
            params={"max_ms": 600},
            provenance=_prov("prov:converge-one"),
        ),
    )
    outcome = expect_resilience_error(
        name,
        "resilience-constraint-weakened",
        lambda: validate_handover_preserves_contract(weakened, contract),
    )
    if not outcome[1]:
        return fail(name, "the weakened candidate gate: %s" % outcome[2])
    weak_candidate = handover_candidate(
        contract,
        route_decision_id="m024:weak-candidate",
        path_id="path:m024:weak-candidate",
        hard_constraints=weakened,
    )
    verdict = handover_verdict(weak_candidate, contract)
    if verdict.accepted:
        return fail(name, "the verdict twin accepted the weakening candidate")
    if "availability-floor" not in verdict.detail:
        return fail(name, "the verdict does not cite the weakened kind")
    _store2, contract2 = _mature_contract()
    store2, session2 = _runtime_session(contract2, "m024:wireline-eth")
    weak_result = perform_handover(
        store2,
        session2.runtime_id,
        contract2,
        (weak_candidate,),
        trigger_kind="route-expiry",
        recorded_at=_T_HOP1,
    )
    if weak_result.decision.decision == "adopt-alternative":
        return fail(name, "the machinery adopted the weakening candidate")
    if weak_result.session.state != "FAILED":
        return fail(
            name,
            "the impossible handover did not land FAILED explicitly (%s)"
            % weak_result.session.state,
        )
    if store2.reconnect_evidence(session2.runtime_id):
        return fail(name, "a weakening candidate silently reconnected")
    # (b) the engine's typed gates: an unregistered class — the plan
    # covers the full domain circle but names a technology class no
    # registration carries (the registry's own typed rejection)
    outcome = expect_typed(
        name,
        "accesstech-registration-rejected",
        lambda: acv.run_interchange_drill(
            acv.InterchangeDrillPlan(
                contract_id=contract.contract_id,
                runtime_id="sha256:" + "6" * 64,
                trigger_kind="route-expiry",
                hops=(
                    acv.InterchangeHop(
                        position=0, from_domain="wireline",
                        to_domain="radio-family",
                        from_class=WIRELINE_TECHNOLOGY_CLASS,
                        to_class="access.unknown.absent",
                        new_route_decision_id="m024:x",
                        new_path_id="path:m024:x",
                        reconnect_instant=_T_HOP1,
                    ),
                    acv.InterchangeHop(
                        position=1, from_domain="radio-family",
                        to_domain="non-terrestrial",
                        from_class="access.unknown.absent",
                        to_class=NONTERRESTRIAL_TECHNOLOGY_CLASS,
                        new_route_decision_id="m024:y",
                        new_path_id="path:m024:y",
                        reconnect_instant=_T_HOP2,
                    ),
                    acv.InterchangeHop(
                        position=2, from_domain="non-terrestrial",
                        to_domain="wireline",
                        from_class=NONTERRESTRIAL_TECHNOLOGY_CLASS,
                        to_class=WIRELINE_TECHNOLOGY_CLASS,
                        new_route_decision_id="m024:z",
                        new_path_id="path:m024:z",
                        reconnect_instant=_T_HOP3,
                    ),
                ),
            ),
            registry,
            fixture["store"],
            contract,
            fixture["session"].runtime_id,
        ),
    )
    if not outcome[1]:
        return fail(name, "the unregistered-class gate: %s" % outcome[2])
    # an undeclared cross-technology kind: a registry whose wireline
    # registration declares NO cross kind — the drill rejects the hop
    # (an undeclared handover shape never participates)
    undeclared_session_store, _sid = ads._established_session()
    undeclared_store, undeclared_session = _runtime_session(
        contract, "m024:wireline-eth"
    )
    undeclared_registry = TechnologyRegistry()
    # the wireline registration WITHOUT the cross-technology kind (the
    # undeclared-kind carrier); the radio-family and non-terrestrial
    # registrations WITH the kind — the hop's FROM side fails the
    # declared-kind gate before anything else fires
    bridge, descriptor, requirements = wbs.wire.mount_reference(
        ads._backhaul_session_reader(undeclared_session_store), now=_T0
    )
    undeclared_registry.register(
        register_access_technology(
            envelope=wbs.wl.WIRELINE_ENVELOPES["ethernet"],
            ladder=wbs.wl.WIRELINE_LADDERS["ethernet"],
            handovers=(declare_handover_kind("intra-technology"),),
            implementation=bridge,
            descriptor=descriptor,
            binding_requirements=requirements,
            mechanisms=wbs.wire.STANDARD_MECHANISMS,
            session_store=undeclared_session_store,
            now=_T0,
        )
    )
    undeclared_radio_impl, undeclared_radio_desc, _u_req = (
        ranref.mount_reference(now=_T0)
    )
    undeclared_registry.register(
        register_access_technology(
            envelope=_RADIO_ENVELOPE,
            ladder=_RADIO_LADDER,
            handovers=(
                declare_handover_kind("intra-technology"),
                declare_handover_kind("cross-technology"),
            ),
            implementation=undeclared_radio_impl,
            descriptor=undeclared_radio_desc,
            binding_requirements={},
            mechanisms=ranref.STANDARD_MECHANISMS,
            session_store=undeclared_session_store,
            now=_T0,
        )
    )
    undeclared_nt_registration, _u_wiring = sbs._register_family(
        undeclared_session_store, "ngso"
    )
    undeclared_registry.register(undeclared_nt_registration)
    outcome = expect_typed(
        name,
        "accesstech-handover-illegal",
        lambda: acv.run_interchange_drill(
            acv.InterchangeDrillPlan(
                contract_id=contract.contract_id,
                runtime_id=undeclared_session.runtime_id,
                trigger_kind="route-expiry",
                hops=_INTERCHANGE_HOPS,
            ),
            undeclared_registry,
            undeclared_store,
            contract,
            undeclared_session.runtime_id,
        ),
    )
    if not outcome[1]:
        return fail(name, "the undeclared-kind gate: %s" % outcome[2])
    # (c) the wrong-contract gate: the drill realizes exactly its
    # owning contract
    outcome = expect_typed(
        name,
        "accesstech-identity-mismatch",
        lambda: acv.run_interchange_drill(
            acv.InterchangeDrillPlan(
                contract_id="sha256:" + "7" * 64,
                runtime_id=fixture["session"].runtime_id,
                trigger_kind="route-expiry",
                hops=_INTERCHANGE_HOPS,
            ),
            registry,
            fixture["store"],
            contract,
            fixture["session"].runtime_id,
        ),
    )
    if not outcome[1]:
        return fail(name, "the wrong-contract gate: %s" % outcome[2])
    # (d) the WORK-012 no-silent-swap gate: a reconnect completion
    # WITHOUT an in-progress initiation is the machinery's typed
    # SILENT_REPLACEMENT rejection (a route change without the
    # explicit pair naming old AND new references never lands)
    outcome = expect_resilience_error(
        name,
        "resilience-silent-replacement",
        lambda: fixture["store"].complete_reconnect(
            fixture["session"].runtime_id,
            recorded_at=_LATER,
            provenance=_prov(_BATTERY_ISSUER),
        ),
    )
    if not outcome[1]:
        return fail(name, "the silent-completion gate: %s" % outcome[2])
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "the machinery's weakened-candidate discipline (typed kind-citing "
        "rejection, EXPLICIT FAILED landing, zero silent reconnects) and "
        "silent-completion gate intact; the drill's own gates typed "
        "(unregistered class, undeclared cross-technology kind, "
        "wrong-contract)",
    )


# ---------------------------------------------------------------------------
# (b) the technology replacement drill
# ---------------------------------------------------------------------------


def case_04_replacement_drill() -> Result:
    name = "case_04_replacement_drill"
    fixture = _replacement_fixture()
    record = fixture["record"]
    contract = fixture["contract"]
    store = fixture["store"]
    session = fixture["session"]
    problems: List[str] = []
    # (a) the replacement is a LIVE technology replaced by ANOTHER
    # technology: old radio -> new future-IMT, the classes differ
    if record.old_class != RADIO_TECHNOLOGY_CLASS:
        problems.append("the old class drifted")
    if record.new_class != FUTURE_TECHNOLOGY_CLASS:
        problems.append("the new class drifted")
    # (b) contract continuity: the record asserts it, the session
    # realizes the SAME contract before and after, the contract store
    # state is unchanged (the replacement never touched the contract
    # core)
    if record.contract_continuity is not True:
        problems.append("the record broke contract continuity")
    if record.contract_id != contract.contract_id:
        problems.append("the record names a foreign contract")
    after = store.session(session.runtime_id)
    if after.contract_id != contract.contract_id:
        problems.append("the session broke contract continuity")
    if after.state != "ACTIVE":
        problems.append("the replacement did not land ACTIVE (%s)" % after.state)
    if (after.route_decision_id, after.path_id) != (
        "m024:future-imt", "path:m024:future-imt"
    ):
        problems.append("the replacement did not land on the new refs")
    if fixture["contract_store"].contract(contract.contract_id).state != (
        "EXECUTION_ACTIVE"
    ):
        problems.append("the contract state drifted through the replacement")
    # (c) the explicit recorded reconnect: BOTH the old AND the new
    # references named, the declared instant, the journal evidence
    if (record.old_route_decision_id, record.old_path_id) != (
        "m024:radio-live", "path:m024:radio-live"
    ):
        problems.append("the record lost the OLD references")
    if (record.new_route_decision_id, record.new_path_id) != (
        "m024:future-imt", "path:m024:future-imt"
    ):
        problems.append("the record lost the NEW references")
    if record.reconnect_instant != _T_REPLACE:
        problems.append("the reconnect instant drifted")
    evidence = store.reconnect_evidence(session.runtime_id)
    if len(evidence) != 1:
        problems.append("the journal carries %d reconnect records" % len(evidence))
    elif evidence[0].new_route_decision_id != "m024:future-imt":
        problems.append("the journal evidence lost the new reference")
    # (d) LOCK-108: the decision's fingerprint IS the contract's own,
    # re-verified through the consumed gate on the LIVE decision
    if record.constraint_fingerprint != contract.hard_constraint_fingerprint():
        problems.append("the replacement fingerprint is not the contract's own")
    try:
        verify_decision_preserves_contract(record.live_decision, contract)
    except Exception as error:  # noqa: BLE001
        problems.append("the replacement failed the consumed gate: %s" % str(error)[:70])
    # (e) the record: canonical, content-derived, round-trips
    first = record.to_canonical_bytes()
    rebuilt = acv.ReplacementRecord(
        contract_id=record.contract_id,
        runtime_id=record.runtime_id,
        old_class=record.old_class,
        new_class=record.new_class,
        old_route_decision_id=record.old_route_decision_id,
        old_path_id=record.old_path_id,
        new_route_decision_id=record.new_route_decision_id,
        new_path_id=record.new_path_id,
        reconnect_instant=record.reconnect_instant,
        decision_id=record.decision_id,
        constraint_fingerprint=record.constraint_fingerprint,
        state_after=record.state_after,
        contract_continuity=True,
        replacement_id=record.replacement_id,
    )
    if rebuilt.to_canonical_bytes() != first:
        problems.append("the replacement record round-trip drifted")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "the live radio technology replaced by the future-IMT technology "
        "under the active contract: contract continuity (the session "
        "realizes the SAME contract before and after; the contract store "
        "state unchanged), the EXPLICIT recorded reconnect naming BOTH "
        "the old AND the new references at the declared instant, the "
        "journal evidence present, LOCK-108 verbatim (the fingerprint IS "
        "the contract's own; the consumed gate green), the record "
        "canonical and tamper-evident",
    )


def case_05_replacement_fail_closed() -> Result:
    name = "case_05_replacement_fail_closed"
    fixture = _replacement_fixture()
    record = fixture["record"]
    contract = fixture["contract"]
    registry = fixture["registry"]
    store = fixture["store"]
    session = fixture["session"]
    # (a) the silent-swap record shape: a replacement record missing
    # either side of the reconnect pair is the typed failure (never a
    # silent swap)
    blank = dict(record.to_dict())
    blank["new_route_decision_id"] = ""
    outcome = expect_typed(
        name,
        "accesstech-invalid-input",
        lambda: acv.ReplacementRecord(**blank),
    )
    if not outcome[1]:
        return fail(name, "the blank-reconnect record: %s" % outcome[2])
    # (b) a replacement that changes nothing is not a replacement
    outcome = expect_typed(
        name,
        "accesstech-handover-illegal",
        lambda: acv.replace_technology(
            registry,
            store,
            session.runtime_id,
            contract,
            old_class=RADIO_TECHNOLOGY_CLASS,
            new_class=RADIO_TECHNOLOGY_CLASS,
            new_route_decision_id="m024:noop",
            new_path_id="path:m024:noop",
            reconnect_instant=_LATER,
        ),
    )
    if not outcome[1]:
        return fail(name, "the no-op replacement: %s" % outcome[2])
    # (c) an undeclared replacement kind: the wireline registration
    # (ethernet declares intra + cross only) never participates in a
    # replacement — typed
    outcome = expect_typed(
        name,
        "accesstech-handover-illegal",
        lambda: acv.replace_technology(
            registry,
            store,
            session.runtime_id,
            contract,
            old_class=WIRELINE_TECHNOLOGY_CLASS,
            new_class=FUTURE_TECHNOLOGY_CLASS,
            new_route_decision_id="m024:wire-to-future",
            new_path_id="path:m024:wire-to-future",
            reconnect_instant=_LATER,
        ),
    )
    if not outcome[1]:
        return fail(name, "the undeclared replacement kind: %s" % outcome[2])
    # (d) a weakened replacement candidate is NEVER adopted: the
    # machinery-level probe (weakened constraints -> EXPLICIT FAILED,
    # zero reconnect evidence) — the engine itself can only pass the
    # contract's own constraints verbatim (LOCK-108 by construction)
    weakened = (
        HardConstraint(
            kind="latency-bound",
            params={"max_ms": 900},
            provenance=_prov("prov:converge-one"),
        ),
    )
    weak_candidate = handover_candidate(
        contract,
        route_decision_id="m024:weak-replace",
        path_id="path:m024:weak-replace",
        hard_constraints=weakened,
    )
    weak_result = perform_handover(
        store,
        session.runtime_id,
        contract,
        (weak_candidate,),
        trigger_kind="route-expiry",
        recorded_at=_LATER,
    )
    if weak_result.decision.decision == "adopt-alternative":
        return fail(name, "the machinery adopted the weakening replacement")
    if weak_result.session.state != "FAILED":
        return fail(
            name,
            "the impossible replacement did not land FAILED explicitly (%s)"
            % weak_result.session.state,
        )
    if len(store.reconnect_evidence(session.runtime_id)) != 1:
        return fail(name, "a weakening replacement silently reconnected")
    # (e) the contract-breaking record shape: contract_continuity
    # False is the typed failure
    broken = dict(record.to_dict())
    broken["contract_continuity"] = False
    broken["replacement_id"] = ""
    outcome = expect_typed(
        name,
        "accesstech-handover-illegal",
        lambda: acv.ReplacementRecord(**broken),
    )
    if not outcome[1]:
        return fail(name, "the contract-breaking record: %s" % outcome[2])
    # (f) the machinery's silent-completion gate (a route change
    # without the explicit pair never lands) — probed on a FRESH
    # ACTIVE session (the weakened drive's session above is terminal;
    # the terminal gate is a different typed rejection)
    _probe_store, _probe_session = _runtime_session(contract, "m024:probe")
    outcome = expect_resilience_error(
        name,
        "resilience-silent-replacement",
        lambda: _probe_store.complete_reconnect(
            _probe_session.runtime_id,
            recorded_at=_LATER,
            provenance=_prov(_BATTERY_ISSUER),
        ),
    )
    if not outcome[1]:
        return fail(name, "the silent-completion gate: %s" % outcome[2])
    return ok(
        name,
        "the silent-swap record shape, the no-op replacement, the "
        "undeclared replacement kind and the contract-breaking record all "
        "typed failures; the machinery's weakened-candidate and "
        "silent-completion disciplines intact (EXPLICIT FAILED, zero "
        "silent reconnects)",
    )


# ---------------------------------------------------------------------------
# (c) the converged-domain compatibility matrix over the R9 domains
# ---------------------------------------------------------------------------

#: The deterministic R9 domain version fixtures (local/peer).
_R9_LOCAL = (
    acv.R9DomainVersion(domain="accesstech", major=1, minor=2),
    acv.R9DomainVersion(domain="futureimt", major=1, minor=0),
    acv.R9DomainVersion(domain="satellite", major=1, minor=1),
    acv.R9DomainVersion(domain="wireline", major=1, minor=3),
)
_R9_PEER = (
    acv.R9DomainVersion(domain="accesstech", major=1, minor=2),
    acv.R9DomainVersion(domain="futureimt", major=1, minor=0),
    acv.R9DomainVersion(domain="satellite", major=1, minor=1),
    acv.R9DomainVersion(domain="wireline", major=1, minor=5),
)


def _r9_report():
    return acv.negotiate_r9_matrix(
        local_id="m024:local",
        peer_id="m024:peer",
        local_versions=_R9_LOCAL,
        peer_versions=_R9_PEER,
    )


def _substrate_report():
    """The accepted upgrade engine's OWN R7-substrate report (the
    battery drives the accepted engine over the frozen
    CONVERGED_DOMAIN_SET — the composed matrix consumes that engine's
    own serialized verdicts, never re-classified here)."""
    local = tuple(
        DomainVersion(domain=domain, major=1, minor=index + 1)
        for index, domain in enumerate(CONVERGED_DOMAIN_SET)
    )
    peer = tuple(
        DomainVersion(domain=domain, major=1, minor=index)
        for index, domain in enumerate(CONVERGED_DOMAIN_SET)
    )
    return negotiate_converged_compatibility(
        local_id="m024:local",
        peer_id="m024:peer",
        local_versions=local,
        peer_versions=peer,
    )


def _r8_report():
    """The accepted M019 R8 matrix report (the battery drives the
    accepted M019 surface over the R8 domain labels)."""
    local = tuple(
        ConvergenceDomainVersion(domain=domain, major=1, minor=0)
        for domain in R8_CONVERGENCE_DOMAINS
    )
    peer = tuple(
        ConvergenceDomainVersion(domain=domain, major=1, minor=0)
        for domain in R8_CONVERGENCE_DOMAINS
    )
    return negotiate_r8_matrix(
        local_id="m024:local",
        peer_id="m024:peer",
        local_versions=local,
        peer_versions=peer,
    )


def _composed_matrix():
    substrate = _substrate_report()
    r8 = _r8_report()
    r9 = _r9_report()
    return acv.compose_access_convergence_matrix(
        [verdict.to_dict() for verdict in substrate.verdicts],
        r8,
        r9,
        local_id="m024:local",
        peer_id="m024:peer",
    )


def case_06_r9_matrix_declarations() -> Result:
    name = "case_06_r9_matrix_declarations"
    problems: List[str] = []
    # (a) the frozen vocabulary equality: the R9 verdict vocabulary ==
    # the accepted upgrade engine's own set (sorted — the M019
    # by-reference drift-guard convention) == the accepted M019 values
    if tuple(acv.MATRIX_VERDICTS) != tuple(sorted(DOMAIN_COMPATIBILITY_VERDICTS)):
        problems.append("the R9 verdict vocabulary drifted from upgrade/")
    if tuple(acv.MATRIX_VERDICTS) != tuple(R8_MATRIX_VERDICTS):
        problems.append("the R9 verdict vocabulary drifted from M019")
    if set(acv.R9_CONVERGENCE_DOMAINS) & set(CONVERGED_DOMAIN_SET):
        problems.append("the R9 domains overlap the R7 substrate set")
    if set(acv.R9_CONVERGENCE_DOMAINS) & set(R8_CONVERGENCE_DOMAINS):
        problems.append("the R9 domains overlap the R8 set")
    # (b) the classification discipline: compatible / additive-gap /
    # major-mismatch, missing sides fail closed
    report = _r9_report()
    by_domain = report.by_domain()
    if by_domain["wireline"].verdict != "additive-gap":
        problems.append("the wireline additive gap was not disclosed")
    if by_domain["accesstech"].verdict != "compatible":
        problems.append("the accesstech pair was not compatible")
    if not report.compatible():
        problems.append("an additive-gap report must interoperate")
    major = acv.negotiate_r9_matrix(
        local_id="m024:local",
        peer_id="m024:peer",
        local_versions=_R9_LOCAL,
        peer_versions=(
            acv.R9DomainVersion(domain="accesstech", major=2, minor=0),
            acv.R9DomainVersion(domain="futureimt", major=1, minor=0),
            acv.R9DomainVersion(domain="satellite", major=1, minor=1),
            acv.R9DomainVersion(domain="wireline", major=1, minor=3),
        ),
    )
    if major.by_domain()["accesstech"].verdict != "major-mismatch":
        problems.append("the major mismatch did not fail closed")
    if major.compatible():
        problems.append("a major-mismatch report must refuse")
    missing = acv.negotiate_r9_matrix(
        local_id="m024:local",
        peer_id="m024:peer",
        local_versions=_R9_LOCAL,
        peer_versions=_R9_LOCAL[:3],
    )
    if missing.by_domain()["wireline"].verdict != "peer-missing":
        problems.append("the missing side did not fail closed")
    # (c) input-order independence + byte-stable digest
    first = _r9_report()
    shuffled = acv.negotiate_r9_matrix(
        local_id="m024:local",
        peer_id="m024:peer",
        local_versions=tuple(reversed(_R9_LOCAL)),
        peer_versions=tuple(reversed(_R9_PEER)),
    )
    if first.digest() != shuffled.digest():
        problems.append("the matrix digest is not input-order independent")
    if first.digest() != _r9_report().digest():
        problems.append("the matrix digest is not byte-stable")
    # (d) the typed rejections: duplicates, unknown domains, foreign
    # domain labels
    probes: List[Tuple[str, str, Callable[[], Any]]] = [
        ("duplicate local version", "accesstech-invalid-input",
         lambda: acv.negotiate_r9_matrix(
             local_id="a", peer_id="b",
             local_versions=(
                 acv.R9DomainVersion(domain="accesstech", major=1, minor=0),
                 acv.R9DomainVersion(domain="accesstech", major=1, minor=1),
             ),
             peer_versions=_R9_PEER,
         )),
        ("foreign domain label", "accesstech-vocabulary",
         lambda: acv.R9DomainVersion(domain="contracts", major=1, minor=0)),
        ("verdict outside vocabulary", "accesstech-vocabulary",
         lambda: acv.R9DomainVerdict(
             domain="accesstech", verdict="best-effort",
             local_major=1, local_minor=0, peer_major=1, peer_minor=0,
         )),
    ]
    for label, code, action in probes:
        outcome = expect_typed(name, code, action)
        if not outcome[1]:
            return fail(name, "%s: %s" % (label, outcome[2]))
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "the accepted upgrade/ matrix discipline extended onto the R9 "
        "domains: the verdict vocabulary pinned against the accepted "
        "engine's own set (and the M019 values); compatible/additive-gap/"
        "major-mismatch/missing-side classification green; input-order "
        "independent and byte-stable digests; 3 malformed classes typed",
    )


def case_07_composed_convergence_matrix() -> Result:
    name = "case_07_composed_convergence_matrix"
    matrix = _composed_matrix()
    problems: List[str] = []
    # (a) the composed row set: the R7 substrate rows + the R8 rows +
    # the R9 rows, exactly one row per domain, sorted iteration
    expected_domains = (
        set(CONVERGED_DOMAIN_SET)
        | set(R8_CONVERGENCE_DOMAINS)
        | set(acv.R9_CONVERGENCE_DOMAINS)
    )
    if {domain for domain, _, _ in matrix.rows} != expected_domains:
        problems.append("the composed row set drifted")
    if len(matrix.rows) != len(expected_domains):
        problems.append("the composed row count drifted")
    if [domain for domain, _, _ in matrix.rows] != sorted(
        domain for domain, _, _ in matrix.rows
    ):
        problems.append("the composed rows are not sorted by domain")
    # (b) the composed matrix is compatible (the additive gap on the
    # wireline line interoperate; every other row compatible)
    if not matrix.compatible():
        problems.append("the composed matrix refused a compatible state")
    by_domain = matrix.by_domain()
    if by_domain["wireline"] != "additive-gap":
        problems.append("the wireline row lost the additive gap")
    if by_domain["contracts"] != "compatible":
        problems.append("a substrate row drifted")
    # (c) input-order independence + byte-stable digest: shuffling the
    # substrate rows and the version inputs never changes the digest
    substrate = _substrate_report()
    shuffled = acv.compose_access_convergence_matrix(
        list(reversed([verdict.to_dict() for verdict in substrate.verdicts])),
        _r8_report(),
        _r9_report(),
        local_id="m024:local",
        peer_id="m024:peer",
    )
    if matrix.digest() != shuffled.digest():
        problems.append("the composed digest is not input-order independent")
    if matrix.digest() != _composed_matrix().digest():
        problems.append("the composed digest is not byte-stable")
    # (d) the fail-closed gates: a non-R7 label riding the substrate
    # rows, a member-drifted substrate row, missing R9 coverage,
    # overlapping rows
    good_rows = [verdict.to_dict() for verdict in substrate.verdicts]
    foreign = dict(good_rows[0])
    foreign["domain"] = "accesstech"
    outcome = expect_typed(
        name,
        "accesstech-invalid-input",
        lambda: acv.compose_access_convergence_matrix(
            [foreign], _r8_report(), _r9_report(),
            local_id="m024:local", peer_id="m024:peer",
        ),
    )
    if not outcome[1]:
        return fail(name, "the foreign substrate label: %s" % outcome[2])
    drifted = dict(good_rows[0])
    drifted["extra_member"] = 1
    outcome = expect_typed(
        name,
        "accesstech-invalid-input",
        lambda: acv.compose_access_convergence_matrix(
            [drifted], _r8_report(), _r9_report(),
            local_id="m024:local", peer_id="m024:peer",
        ),
    )
    if not outcome[1]:
        return fail(name, "the member-drifted substrate row: %s" % outcome[2])
    partial_r9 = acv.negotiate_r9_matrix(
        local_id="m024:local",
        peer_id="m024:peer",
        local_versions=_R9_LOCAL[:3],
        peer_versions=_R9_PEER[:3],
    )
    outcome = expect_typed(
        name,
        "accesstech-invalid-input",
        lambda: acv.compose_access_convergence_matrix(
            good_rows, _r8_report(), partial_r9,
            local_id="m024:local", peer_id="m024:peer",
        ),
    )
    if not outcome[1]:
        return fail(name, "the missing R9 coverage: %s" % outcome[2])
    # an R9 label duplicated onto the R8 report is impossible by
    # construction (different domain sets) — the overlap gate is
    # probed through a substrate row colliding with an R9 row
    colliding = dict(good_rows[0])
    colliding["domain"] = "wireline"
    outcome = expect_typed(
        name,
        "accesstech-invalid-input",
        lambda: acv.compose_access_convergence_matrix(
            [colliding] + good_rows[1:], _r8_report(), _r9_report(),
            local_id="m024:local", peer_id="m024:peer",
        ),
    )
    if not outcome[1]:
        return fail(name, "the overlapping rows: %s" % outcome[2])
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "the composed converged-domain matrix over %d domains (the "
        "accepted upgrade engine's own R7 substrate rows + the accepted "
        "M019 R8 rows + the R9 extension rows, one row per domain, "
        "sorted); input-order independent and byte-stable; 4 malformed "
        "classes typed" % len(expected_domains),
    )


# ---------------------------------------------------------------------------
# (d) the federation-scale convergence over the R9 domains
# ---------------------------------------------------------------------------


def _scale_fixture():
    """The R9 federation-scale convergence fixture: the drills' REAL
    material (the interchange and replacement handover decisions)
    cited through the accepted federation constructors, the accepted
    scale harness scenario over the citations with declared bounds,
    and the M024 verifier over the run."""
    interchange = _interchange_fixture()
    replacement = _replacement_fixture()
    citations = [
        cite_replan_decision(
            hop_result.live_decision,
            issuer="m024:convergence-battery",
            cited_at=_T_CITE,
        )
        for hop_result in interchange["result"].hop_results
    ]
    citations.append(
        cite_replan_decision(
            replacement["record"].live_decision,
            issuer="m024:convergence-battery",
            cited_at=_T_CITE,
        )
    )
    decision_citation = citations[0]
    spec = ConvergenceScenarioSpec(
        scenario_id="r9-convergence",
        seed=17,
        start_instant=_T_CITE,
        tick_seconds=60,
        horizon_ticks=12,
        domain_count=6,
        shape=TopologyShape.RING,
        citations=(
            # the R9 decision citations across the world (the M014
            # canonical holder shape: the propagation bound is the ring
            # distance to the farthest holder)
            ConvergenceCitationPlan(at_tick=0, domain_index=0, citation=citations[0]),
            ConvergenceCitationPlan(at_tick=0, domain_index=1, citation=citations[0]),
            ConvergenceCitationPlan(at_tick=2, domain_index=4, citation=citations[0]),
            # the remaining interchange decisions at one holder domain
            # each
            ConvergenceCitationPlan(at_tick=1, domain_index=2, citation=citations[1]),
            ConvergenceCitationPlan(at_tick=1, domain_index=3, citation=citations[2]),
            # the replacement decision citation at one holder domain
            ConvergenceCitationPlan(at_tick=2, domain_index=5, citation=citations[3]),
        ),
        revocations=(
            ConvergenceRevocationPlan(
                at_tick=4, domain_index=0,
                citation_id=decision_citation.citation_id,
                reason="m024-r9-material-revocation",
            ),
        ),
    )
    distances = delivery_distances(
        topology_edges(TopologyShape.RING, 6), 6, 0,
    )
    expected_rounds = max(distances[index] for index in (0, 1, 4))
    bounds = acv.AccessScaleBounds(
        domain_count=6,
        shape=TopologyShape.RING,
        tick_seconds=60,
        horizon_ticks=12,
        citation_rate_limit=8,
        planned_citations=6,
        revoked_citation_count=3,
        propagation_round_bounds=((decision_citation.citation_id, expected_rounds),),
    )
    run = run_convergence_scenario(spec)
    replay = run_convergence_scenario(spec)
    report = acv.verify_access_scale_convergence(
        bounds, run, replay,
        citation_ids=tuple(citation.citation_id for citation in citations),
    )
    return {
        "spec": spec,
        "bounds": bounds,
        "citations": citations,
        "run": run,
        "replay": replay,
        "report": report,
        "expected_rounds": expected_rounds,
        "interchange": interchange,
        "replacement": replacement,
    }


def case_08_federation_scale_convergence() -> Result:
    name = "case_08_federation_scale_convergence"
    fixture = _scale_fixture()
    report = fixture["report"]
    run = fixture["run"]
    citations = fixture["citations"]
    expected_rounds = fixture["expected_rounds"]
    problems: List[str] = []
    # (a) the R9 material citations: the 3 interchange decisions + the
    # replacement decision, all constructed through the ACCEPTED
    # cite-* constructors over the REAL R9 records
    if len(citations) != 4:
        problems.append("expected 4 R9 material citations; found %d" % len(citations))
    authorities = {citation.authority for citation in citations}
    if authorities != {"replan"}:
        problems.append("the R9 material citation authorities drifted: %s"
                        % sorted(authorities))
    # (b) the declared bounds verified: the citations, the revocation,
    # the topology-predicted propagation rounds (observed == declared)
    if report.citation_count != 6 or report.revoked_citation_count != 3:
        problems.append("the declared citation/revocation envelopes drifted")
    if report.propagation != (
        (citations[0].citation_id, expected_rounds, expected_rounds),
    ):
        problems.append("the propagation bound drifted: %r" % (report.propagation,))
    if not report.replay_verified:
        problems.append("the harness replay was not verified")
    if report.run_digest != run.run_digest:
        problems.append("the report does not carry the accepted run digest verbatim")
    # (c) the accepted harness's own replay verification agrees
    if not verify_convergence_replay(fixture["spec"], run):
        problems.append("the accepted harness replay verification diverged")
    # (d) the journal honesty: the R9 material admissions journaled
    # with their citation identities and authorities (the frozen
    # taxonomy)
    admissions = [
        event for event in run.journal
        if event.kind == ScaleEventType.OBSERVATION
        and event.payload.get("kind") == "convergence-citation-admitted"
    ]
    if len(admissions) != 6:
        problems.append("the R9 material admissions drifted: %d" % len(admissions))
    admitted_ids = {event.payload.get("citation_id") for event in admissions}
    if not all(citation.citation_id in admitted_ids for citation in citations):
        problems.append("an R9 material citation was never admitted")
    # (e) the verifier's composed report is byte-stable across a full
    # re-run
    second = _scale_fixture()
    if second["report"].canonical_bytes() != report.canonical_bytes():
        problems.append("the composed federation-scale report diverged across runs")
    # (f) a diverging declared bound fails closed (the
    # topology-predicted convergence bound is the contract)
    bad_bounds = acv.AccessScaleBounds(
        domain_count=6, shape=TopologyShape.RING, tick_seconds=60,
        horizon_ticks=12, citation_rate_limit=8, planned_citations=5,
        revoked_citation_count=3,
        propagation_round_bounds=(
            (citations[0].citation_id, expected_rounds + 1),
        ),
    )
    outcome = expect_typed(
        name,
        "accesstech-identity-mismatch",
        lambda: acv.verify_access_scale_convergence(
            bad_bounds, run, fixture["replay"],
            citation_ids=tuple(c.citation_id for c in citations),
        ),
    )
    if not outcome[1]:
        problems.append("a diverging declared round bound was accepted")
    # (g) a diverging replay fails closed
    class _DivergingReplay:
        run_digest = "sha256:" + "0" * 64
    outcome = expect_typed(
        name,
        "accesstech-identity-mismatch",
        lambda: acv.verify_access_scale_convergence(
            fixture["bounds"], run, _DivergingReplay(),
            citation_ids=tuple(c.citation_id for c in citations),
        ),
    )
    if not outcome[1]:
        problems.append("a diverging replay was accepted")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "4 R9 material citations (the 3 interchange decisions + the "
        "replacement decision) over the accepted 6-domain ring harness; "
        "the revocation confirmed in %d topology-predicted rounds; the "
        "replay byte-identical (the accepted harness's own verification "
        "agreeing); the composed report byte-stable; the diverging-bound "
        "and diverging-replay probes fail closed typed" % expected_rounds,
    )


# ---------------------------------------------------------------------------
# (e) the by-reference composition audit
# ---------------------------------------------------------------------------


def case_09_by_reference_composition_audit() -> Result:
    name = "case_09_by_reference_composition_audit"
    problems: List[str] = []
    module_path = REPO_ROOT / "accesstech" / "convergence.py"
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    # (a) the module's own import discipline: ONLY the accepted
    # one-way set (protocol/replan/resilience + the package's own
    # relative surface + stdlib) — zero contracts imports (the M020
    # zero-contract-import discipline preserved), no upgrade/scale/
    # federation imports (those surfaces are consumed through the
    # battery's composition root / duck-typed records), no legacy
    # reservoir
    allowed_roots = {
        "__future__", "hashlib", "re", "dataclasses", "typing",
        "protocol", "replan", "resilience",
    }
    imported_roots: set = set()
    contracts_names: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if node.level == 0 and root:
                imported_roots.add(root)
                if root == "contracts":
                    contracts_names.update(alias.name for alias in node.names)
    unexpected = sorted(imported_roots - allowed_roots)
    if unexpected:
        problems.append("the module imports %s" % unexpected)
    if contracts_names:
        problems.append(
            "the module imports contracts names %s (the M020 discipline: "
            "zero)" % sorted(contracts_names)
        )
    # (b) the module never references the M021/M022/M023 composition
    # modules (the composition happens through the accepted
    # registration surface — the leaf discipline)
    for token in ("wireline", "satellite", "futureimt"):
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == token:
                problems.append("the module names %r in code" % token)
            if isinstance(node, ast.Attribute) and node.attr == token:
                problems.append("the module references .%r in code" % token)
            if isinstance(node, ast.ImportFrom) and node.module and token in (
                node.module
            ):
                problems.append("the module imports %r" % token)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if token in alias.name:
                        problems.append("the module imports %r" % token)
    # (c) the one-way boundary: no accepted authority references the
    # new module (AST tokens, not docstrings)
    authorities = (
        "contracts", "replan", "executionplans", "evidence", "assurance",
        "offers", "eligibility", "policy", "adapters", "usage", "commercial",
        "allocation", "payment", "sharenet", "roamlink", "comos",
        "developerapi", "federation", "identity", "upgrade", "scale",
        "client", "resilience", "localfirst", "recovery", "credentials",
    )

    def _references_convergence(source_text: str) -> bool:
        try:
            authority_tree = ast.parse(source_text)
        except SyntaxError:
            return False
        for node in ast.walk(authority_tree):
            if isinstance(node, ast.ImportFrom) and node.module and (
                "accesstech.convergence" in node.module
            ):
                return True
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "accesstech.convergence" in alias.name:
                        return True
        return False

    for package in authorities:
        package_dir = REPO_ROOT / package
        if not package_dir.is_dir():
            continue
        for path in sorted(package_dir.glob("*.py")):
            source_text = path.read_text(encoding="utf-8")
            if "accesstech.convergence" in source_text and _references_convergence(
                source_text
            ):
                problems.append(
                    "%s/%s references the new module (one-way boundary)"
                    % (package, path.name)
                )
    # the frozen package initializer does not import the new module
    # (the accepted __init__ surface stays untouched)
    init_tree = ast.parse(
        (REPO_ROOT / "accesstech" / "__init__.py").read_text(encoding="utf-8")
    )
    for node in ast.walk(init_tree):
        if isinstance(node, ast.ImportFrom) and node.module and "convergence" in (
            node.module or ""
        ):
            problems.append("the frozen accesstech __init__ imports the module")
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "convergence" in alias.name:
                    problems.append("the frozen accesstech __init__ imports the module")
    # (d) the composition disclosed: the battery mounts the four
    # accepted R9 child compositions through their OWN public
    # factories and registers them through the accepted M020 surface
    fixture = _interchange_fixture()
    registry = fixture["registry"]
    if sorted(registry.technology_classes()) != sorted(
        (
            WIRELINE_TECHNOLOGY_CLASS,
            RADIO_TECHNOLOGY_CLASS,
            NONTERRESTRIAL_TECHNOLOGY_CLASS,
            FUTURE_TECHNOLOGY_CLASS,
        )
    ):
        problems.append("the composed registry drifted")
    for registration in registry.registrations():
        adapter = registration.resolve_capability_adapter()
        if not isinstance(adapter, CapabilityAdapter):
            problems.append("a registration resolves outside the seam")
        if registration.capability_adapter is not adapter:
            problems.append("the resolution is not identity-preserving")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "the module imports only the accepted one-way set (protocol/replan/"
        "resilience + relative, ZERO contracts imports); it never "
        "references the M021/M022/M023 composition modules (the leaf "
        "discipline — the composition flows through the accepted "
        "registration surface); no accepted authority references the "
        "module; the four R9 child compositions mounted through their own "
        "public factories and resolving identity-preserving through the "
        "accepted capability seam",
    )


# ---------------------------------------------------------------------------
# (f) LOCK-110 provider-SDK isolation
# ---------------------------------------------------------------------------


def case_10_lock110_provider_sdk_isolation() -> Result:
    name = "case_10_lock110_provider_sdk_isolation"
    interchange = _interchange_fixture()
    replacement = _replacement_fixture()
    matrix = _composed_matrix()
    scale = _scale_fixture()
    problems: List[str] = []
    # (a) every canonical record byte the convergence surface produces
    # carries NO opaque family technology reference (the drill refs
    # are the surface's own declared opaque realization references —
    # LOCK-117 execution-artifact data; the provider-SDK
    # link/bearer/route HANDLES stay behind the family runtimes)
    records = [
        interchange["plan"].to_canonical_bytes(),
        interchange["result"].to_canonical_bytes(),
        replacement["record"].to_canonical_bytes(),
        matrix.digest().encode("utf-8"),
        scale["report"].canonical_bytes(),
        scale["bounds"].canonical_bytes(),
    ]
    for blob in records:
        for token in (b"backhaul:", b"mesh:link:", b"bearer:", b"ran:", b"gpp:"):
            if token in blob:
                problems.append(
                    "an opaque family technology reference crossed into a "
                    "canonical record byte (%r)" % token
                )
                break
    # (b) no technology-branching in the module's own vocabulary (the
    # technology enters as declared DATA; the scan covers the module's
    # OWN declared/defined names — identifiers imported from the
    # accepted surfaces are the by-reference composition itself)
    module_path = REPO_ROOT / "accesstech" / "convergence.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
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
    for token in (
        "3gpp", "80211", "8023", "imt2020", "imt2030", "wifi", "wi-fi",
        "nr", "lte", "5g", "6g", "bluetooth", "microwave", "entangled",
        "ethernet", "g709", "iab",
    ):
        for code_name in own_names:
            if token in code_name.lower():
                problems.append(
                    "code name %r embeds %r (no tech branching)"
                    % (code_name, token)
                )
    # (c) the mediated boundary: every drill technology resolves
    # through the accepted CapabilityAdapter seam (LOCK-110) — the
    # drill never touches a family runtime
    for registration in interchange["registry"].registrations():
        if not isinstance(
            registration.resolve_capability_adapter(), CapabilityAdapter
        ):
            problems.append("a drill technology resolves outside the seam")
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "no opaque family technology reference crosses into any canonical "
        "record byte of the convergence surface; no technology-branching "
        "names in the module's own vocabulary; every drill technology "
        "resolves through the accepted mediated capability seam",
    )


# ---------------------------------------------------------------------------
# (g) LOCK-119 purity, typed errors, determinism
# ---------------------------------------------------------------------------


def case_11_lock119_purity() -> Result:
    name = "case_11_lock119_purity"
    module_path = REPO_ROOT / "accesstech" / "convergence.py"
    source = module_path.read_text(encoding="utf-8")
    problems: List[str] = []
    for forbidden in (
        "datetime.now", "time.time", "utcnow", "uuid", "random.",
        "socket.", "requests.", "urlopen", "time.monotonic", "time.sleep",
        "importlib", "__import__",
    ):
        if forbidden in source:
            problems.append("the module carries %r" % forbidden)
    tree = ast.parse(source)
    forbidden_imports = (
        "random", "socket", "urllib", "requests", "time", "secrets",
        "datetime", "uuid",
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in forbidden_imports:
                    problems.append("the module imports %s" % alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in forbidden_imports:
                problems.append("the module imports from %s" % node.module)
    # the secret-rejection guards: secret-shaped values rejected typed
    # at the construction boundaries
    outcome = expect_typed(
        name,
        "accesstech-invalid-input",
        lambda: acv.InterchangeHop(
            position=0, from_domain="wireline", to_domain="radio-family",
            from_class=WIRELINE_TECHNOLOGY_CLASS,
            to_class=RADIO_TECHNOLOGY_CLASS,
            new_route_decision_id="ghp_SecretTokenValue123",
            new_path_id="path:m024:x",
            reconnect_instant=_T_HOP1,
        ),
    )
    if not outcome[1]:
        problems.append("the secret-shaped ref probe: %s" % outcome[2])
    outcome = expect_typed(
        name,
        "accesstech-invalid-input",
        lambda: acv.R9MatrixReport(
            local_id="ghp_SecretShapedLocalId",
            peer_id="m024:peer",
            verdicts=(),
        ),
    )
    if not outcome[1]:
        problems.append("the secret-shaped matrix id probe: %s" % outcome[2])
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "no wall-clock/randomness/network constructs anywhere in the "
        "module; the secret-rejection guards fire typed at the "
        "construction boundaries (LOCK-119)",
    )


def case_12_typed_error_matrix() -> Result:
    name = "case_12_typed_error_matrix"
    fixture = _interchange_fixture()
    contract = fixture["contract"]
    registry = fixture["registry"]
    store = fixture["store"]
    session = fixture["session"]
    plan = fixture["plan"]
    probes: List[Tuple[str, str, Callable[[], Any]]] = [
        ("non-store input", "accesstech-invalid-input",
         lambda: acv.run_interchange_drill(plan, registry, object(), contract,
                                           session.runtime_id)),
        ("non-registry input", "accesstech-invalid-input",
         lambda: acv.run_interchange_drill(plan, object(), store, contract,
                                           session.runtime_id)),
        ("non-plan input", "accesstech-invalid-input",
         lambda: acv.run_interchange_drill("plan", registry, store, contract,
                                           session.runtime_id)),
        ("contract surface missing", "accesstech-invalid-input",
         lambda: acv.run_interchange_drill(
             plan, registry, store, object(), session.runtime_id
         )),
        ("replacement non-store input", "accesstech-invalid-input",
         lambda: acv.replace_technology(
             registry, object(), session.runtime_id, contract,
             old_class=RADIO_TECHNOLOGY_CLASS,
             new_class=FUTURE_TECHNOLOGY_CLASS,
             new_route_decision_id="m024:x", new_path_id="path:m024:x",
             reconnect_instant=_LATER,
         )),
        ("replacement unknown trigger kind", "accesstech-vocabulary",
         lambda: acv.replace_technology(
             registry, store, session.runtime_id, contract,
             old_class=RADIO_TECHNOLOGY_CLASS,
             new_class=FUTURE_TECHNOLOGY_CLASS,
             new_route_decision_id="m024:x", new_path_id="path:m024:x",
             reconnect_instant=_LATER,
             trigger_kind="sunset",
         )),
        ("replacement malformed instant", "accesstech-invalid-input",
         lambda: acv.replace_technology(
             registry, store, session.runtime_id, contract,
             old_class=RADIO_TECHNOLOGY_CLASS,
             new_class=FUTURE_TECHNOLOGY_CLASS,
             new_route_decision_id="m024:x", new_path_id="path:m024:x",
             reconnect_instant="2026-06-01 17:00:00",
         )),
        ("drill result fabricated pass", "accesstech-handover-illegal",
         lambda: acv.InterchangeDrillResult(
             drill_id=fixture["result"].drill_id,
             contract_id=fixture["result"].contract_id,
             runtime_id=fixture["result"].runtime_id,
             trigger_kind="route-expiry",
             hop_results=fixture["result"].hop_results,
             lock108_verified=False,
         )),
        ("scale bounds degenerate", "accesstech-invalid-input",
         lambda: acv.AccessScaleBounds(
             domain_count=0, shape="ring", tick_seconds=60, horizon_ticks=12,
             citation_rate_limit=8, planned_citations=5,
             revoked_citation_count=3,
             propagation_round_bounds=(),
         )),
        ("scale bounds duplicate bound", "accesstech-invalid-input",
         lambda: acv.AccessScaleBounds(
             domain_count=6, shape="ring", tick_seconds=60, horizon_ticks=12,
             citation_rate_limit=8, planned_citations=5,
             revoked_citation_count=3,
             propagation_round_bounds=(
                 ("m014:cite:sha256:" + "0" * 64, 3),
                 ("m014:cite:sha256:" + "0" * 64, 3),
             ),
         )),
        ("verdict vocabulary drift", "accesstech-vocabulary",
         lambda: acv.AccessConvergenceMatrix(
             local_id="a", peer_id="b",
             rows=(("accesstech", "silently-ignored", "x"),),
         )),
        ("duck-typed run surface missing", "accesstech-invalid-input",
         lambda: acv.verify_access_scale_convergence(
             _scale_good_bounds(), object(), object(),
             citation_ids=("m014:cite:sha256:" + "1" * 64,),
         )),
    ]
    for label, code, action in probes:
        outcome = expect_typed(name, code, action)
        if not outcome[1]:
            return fail(name, "%s: %s" % (label, outcome[2]))
    return ok(
        name,
        "12 typed fail-closed classes across the drills, the matrix and "
        "the scale surface (deterministic codes, never warnings, never raw "
        "consumer exceptions)",
    )


def _scale_good_bounds() -> acv.AccessScaleBounds:
    return acv.AccessScaleBounds(
        domain_count=6, shape="ring", tick_seconds=60, horizon_ticks=12,
        citation_rate_limit=8, planned_citations=5, revoked_citation_count=3,
        propagation_round_bounds=(("m014:cite:sha256:" + "2" * 64, 3),),
    )


def _drill_material() -> bytes:
    """The full M024 drill's canonical material (deterministic): the
    interchange plan + result, the replacement record, the composed
    matrix and the federation-scale report — every byte composed from
    fixed injected inputs."""
    interchange = _interchange_fixture()
    replacement = _replacement_fixture()
    matrix = _composed_matrix()
    scale = _scale_fixture()
    return b"".join(
        (
            interchange["plan"].to_canonical_bytes(),
            interchange["result"].to_canonical_bytes(),
            replacement["record"].to_canonical_bytes(),
            canonical_json_bytes(
                {"matrix_digest": matrix.digest()}
            ),
            scale["report"].canonical_bytes(),
        )
    )


def case_13_determinism_byte_identical() -> Result:
    name = "case_13_determinism_byte_identical"
    # (a) in-process rebuild: the whole drill surface rebuilt from
    # scratch -> byte-identical canonical material
    first = _drill_material()
    second = _drill_material()
    if first != second:
        return fail(
            name,
            "the drill material differs on in-process rebuild (%d vs %d bytes)"
            % (len(first), len(second)),
        )
    # (b) cross-process: the same material built in PYTHONHASHSEED
    # 0/1/42 subprocesses -> byte-identical digests
    probe = r"""
import sys
sys.path.insert(0, %r)
sys.path.insert(0, %r)
import hashlib
import accessconvergence_selftest as m024
print(hashlib.sha256(m024._drill_material()).hexdigest())
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
            "the drill material differs across PYTHONHASHSEED subprocesses "
            "(%d distinct outputs)" % len(outputs),
        )
    return ok(
        name,
        "in-process rebuild byte-identical (the interchange plan/result, "
        "the replacement record, the composed matrix digest and the "
        "federation-scale report); the full material byte-identical across "
        "PYTHONHASHSEED 0/1/42 subprocesses",
    )


# ---------------------------------------------------------------------------
# (h) zero contract-core delta + the evidence-doc honesty
# ---------------------------------------------------------------------------


def _origin_main_available() -> bool:
    probe = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/main"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    return probe.returncode == 0


def case_14_zero_contract_core_delta() -> Result:
    name = "case_14_zero_contract_core_delta"
    # (a) the contract store state is unchanged through the drills
    # (the contract core is never touched — the gate's own objective
    # constraint)
    fixture = _interchange_fixture()
    contract = fixture["contract"]
    before = canonical_json_bytes(contract.to_dict())
    state_before = fixture["contract_store"].contract(
        contract.contract_id
    ).state
    _replacement = _replacement_fixture()
    after = canonical_json_bytes(contract.to_dict())
    state_after = fixture["contract_store"].contract(
        contract.contract_id
    ).state
    if before != after or state_before != state_after:
        return fail(name, "the contract state drifted through the drills")
    if state_after != "EXECUTION_ACTIVE":
        return fail(name, "the contract is not EXECUTION_ACTIVE")
    # (b) the git-guarded PR delta: zero contracts/ files touched; the
    # delta confined to the authorization scope (the M024 files)
    if not _origin_main_available():
        return ok(
            name,
            "in-process audit green (the contract bytes and state "
            "unchanged); git delta check skipped (no origin/main ref; the "
            "CI provenance step enforces scope)",
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
        "the contract bytes and state unchanged through both drills; the "
        "PR delta (%d file(s)) touches no contract-core file and stays "
        "inside the R9-CORE-001 scope" % len(delta),
    )


def case_15_evidence_doc_honest() -> Result:
    name = "case_15_evidence_doc_honest"
    path = REPO_ROOT / "docs" / "M024-evidence.md"
    if not path.exists():
        return fail(name, "docs/M024-evidence.md is missing")
    text = path.read_text(encoding="utf-8")
    problems: List[str] = []
    if "SOFTWARE" not in text:
        problems.append("the evidence class is not disclosed")
    if "M024" not in text:
        problems.append("the evidence does not name M024")
    for lock in ("LOCK-108", "LOCK-110", "LOCK-109", "LOCK-112", "LOCK-119"):
        if lock not in text:
            problems.append("the %s mapping is not disclosed" % lock)
    for evid in ("EVID-002", "EVID-003", "EVID-008"):
        if evid not in text:
            problems.append("the open physical obligations are not disclosed")
    if "by reference" not in text.lower():
        problems.append("the by-reference composition is not disclosed")
    # the R9 gate completion review: the program_exit evaluation
    # recorded SOFTWARE-class (never a PHYSICAL PASS claim)
    if "stripe-of-connectivity" not in text:
        problems.append("the stripe-of-connectivity test is not evaluated")
    if "architecture test" not in text:
        problems.append("the architecture test is not evaluated")
    if "program_exit" not in text:
        problems.append("the program_exit evaluation is not recorded")
    for marker in ("DEC-0121", "DEC-0122", "DEC-0123", "DEC-0124"):
        if marker not in text:
            problems.append("the completion review does not cite %s" % marker)
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
        "open physical obligations and the program_exit completion review "
        "(both tests, SOFTWARE-class, the accepted decisions cited) "
        "disclosed; no affirmative physical claims",
    )


# ===========================================================================
# Main
# ===========================================================================


def main() -> int:
    results: List[Result] = []
    results.append(case_01_interchange_plan_declarations())
    results.append(case_02_interchange_drill_through_machinery())
    results.append(case_03_interchange_fail_closed())
    results.append(case_04_replacement_drill())
    results.append(case_05_replacement_fail_closed())
    results.append(case_06_r9_matrix_declarations())
    results.append(case_07_composed_convergence_matrix())
    results.append(case_08_federation_scale_convergence())
    results.append(case_09_by_reference_composition_audit())
    results.append(case_10_lock110_provider_sdk_isolation())
    results.append(case_11_lock119_purity())
    results.append(case_12_typed_error_matrix())
    results.append(case_13_determinism_byte_identical())
    results.append(case_14_zero_contract_core_delta())
    results.append(case_15_evidence_doc_honest())

    print("ADCOS access convergence self-test (M024 — Future Access Convergence)")
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
