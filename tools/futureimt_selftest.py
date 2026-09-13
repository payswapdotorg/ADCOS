#!/usr/bin/env python3
"""ADCOS future-IMT extension drill self-test (M023).

Deterministic, offline verification of the M023 delivery — the
``adapters/reference/futureimt.py`` synthetic future-IMT/6G-class
reference composition through the ACCEPTED public extension surface —
against the R9 charter M023 scope (R9-CORE-001, DEC-0120; the
chain-independent Future Technology Extension Drill):

- (a) case_01..case_03 — the composition registers through the
  accepted ``adapters/capability.py`` seam (LOCK-110/LOCK-112: the
  core imports nothing from the module and branches on no technology
  name) and drives the frozen 1.1 section 6 capability operations
  (name-equal to the accepted M006 ``executionplans``
  ADAPTER_OPERATIONS vocabulary, never imported between the two
  domains) with typed, canonical, provider-neutral records; the
  declared future-technology capability surface (terahertz-carrier
  bandwidth range, holographic-latency bound, AI-native adaptive-beam
  classes) is declared DATA — the observable surface stays the
  generic link-metric vocabulary;
- (b) case_04 — the deterministic re-bind translation for
  mid-session reconfiguration (the accepted seam's disclosed
  ``unbind_session``/``bind_session`` pair: the previous binding
  released first, the same session and preserved reservation, the
  new requirements applied, typed Reconfiguration records, the
  idempotent RECONFIGURED edge);
- (c) case_05..case_07 — the offer/executionplan/eligibility
  composition: REAL accepted objects composed BY REFERENCE inside
  the drill — real WORK-005 capability statements and real M003
  offer/advertisement records grounding the composition's capability
  surface, a real M002 contract carried to CONTRACT_ACTIVE, the real
  M006 LOCK-109 bridge translating it to an ExecutionPlan whose
  segment operation references drive the composition, and the real
  M004 eligibility/policy gates admitting the offer (with the
  deterministic denial edges as decision DATA);
- (d) case_08..case_11 — LOCK-110 provider-SDK isolation (no opaque
  technology reference crosses into any 1.1 record's canonical
  bytes; adapter identity stays the WORK-016 grammar), the typed
  fail-closed matrix (declared-surface rejections, capacity
  exhaustion, unknown/terminal ids, secret-shaped material), the
  open-world proof (a composition under an UNKNOWN_BUT_WELL_FORMED
  technology id registers and drives identically; the accepted seam
  surface carries no technology token; the registry entry stays
  reserved — registration is never activation), and the ZERO
  CONTRACT-CORE DELTA proof (the AST import audit — the module
  imports no ``contracts/`` surface at all; the module surface is
  registration + operations only; the git-guarded delta touches no
  contract-core file and stays inside the R9-CORE-001 scope);
- (e) case_12..case_14 — the one-way import audit (no accepted
  module imports the new module; the module never imports the legacy
  ``imt/`` domain — the frozen migration matrix: 1.0 material is
  source material only, never a forward dependency), determinism
  (in-process rebuild byte-identical; the whole drill byte-identical
  across PYTHONHASHSEED 0/1/42 subprocesses), and the evidence-doc
  honesty (SOFTWARE class only; EVID-002..EVID-008 stay open —
  never a PHYSICAL PASS claim).

The central boundary is exercised throughout:

    FUTURE-IMT ACCESS TECHNOLOGY (the drill's synthetic technology)
        = a reference adapter composition carrying its OWN
          deterministic reference engine (no accepted family runtime
          exists for future-IMT) registered through the accepted
          adapters/capability.py seam
        = offered through the accepted offers/capabilities exchange,
          bridged by the accepted executionplans/ LOCK-109 surface,
          admitted by the accepted eligibility/policy gates — all
          composed BY REFERENCE, never re-decided, never duplicated
        != CONTRACT AUTHORITY (contracts/ stays the sole authority —
          ZERO contract-core delta)
        != REGISTRY ACTIVATION (the reserved WORK-002 path stays
          reserved; the technology enters as DATA)

All instants are injected (T0-style constants); no wall clock, no
randomness, no network, no real sockets, no secrets (LOCK-119).  The
WORK-012 SessionStore is used only through the accepted battery
fixture (``tools/adapter_selftest._established_session`` — imported
BY REFERENCE, the M021 wireline battery precedent) to prove the
read-only session-verification boundary holds end-to-end.
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

import adapter_selftest as ads  # noqa: E402  (the accepted battery fixtures, by reference)

from adapters import (  # noqa: E402
    AdapterError,
    AdapterRuntime,
    CAPABILITY_OPERATIONS,
    CapabilityAdapter,
    parse_adapter_id,
)
from adapters.capability import (  # noqa: E402
    CAPABILITY_TRANSLATION_MAP,
    activation_from_mapping,
    measurement_from_mapping,
    release_receipt_from_mapping,
    reconfiguration_from_mapping,
)

from adapters.reference.futureimt import (  # noqa: E402
    CARRIER_BANDWIDTH_RANGE_GBPS,
    CREDENTIAL_SLOT_NAME,
    HOLOGRAPHIC_LATENCY_BOUND_US,
    REFERENCE_BEAM_ASSOCIATIONS,
    REFERENCE_BEAM_CLASS,
    REFERENCE_BEAM_CLASSES,
    REFERENCE_CAPABILITIES,
    REFERENCE_CARRIER_GBPS,
    REFERENCE_LABEL,
    REFERENCE_TECHNOLOGY_ID,
    STANDARD_MECHANISMS,
    UNKNOWN_FUTURE_TECHNOLOGY_ID,
    mount_reference,
    reference_descriptor,
)
from adapters.reference.futureimt import ReferenceFutureImtEngine  # noqa: E402

from capabilities.classification import (  # noqa: E402
    CapabilityIdClass,
    classify_capability_id,
)
from capabilities.model import CapabilityStatement  # noqa: E402
from capabilities.serialization import statement_to_bytes  # noqa: E402

from contracts import (  # noqa: E402
    COMMAND_KINDS,
    TERMINAL_STATES,
    ActivateContract,
    BeneficiaryScope,
    ConnectivityPrincipal,
    ContractStore,
    CreateContract,
    HardConstraint,
    OpaqueReference,
    Provenance,
    SelectOffers,
    TerminationRules,
    ValidityInterval,
)

from executionplans import (  # noqa: E402
    ADAPTER_OPERATIONS,
    SegmentInput,
    apply_segment_transition,
    plan_reference,
    translate_contract,
    verify_plan_preserves_contract,
)

from eligibility.contract_constraints import (  # noqa: E402
    ContractConstraintContext,
    ContractConstraintDecisionCode,
    ContractConstraintEffect,
    ContractConstraintRule,
    ContractConstraintSet,
    ValidityWindow,
    evaluate_contract_constraints,
)
from eligibility.contract_eligibility import (  # noqa: E402
    ContractEligibilityReason,
    ContractEligibilityRuleset,
    ContractReferenceFacts,
    OfferReferenceEligibilityFacts,
    evaluate_contract_reference_eligibility,
    evaluate_offer_reference_eligibility,
)

from offers import (  # noqa: E402
    OfferExchange,
    build_advertisement,
    build_offer,
    offer_reference,
)
from offers.model import (  # noqa: E402
    AdvertisementEntry,
    AdvertisementRef,
    OfferCommitment,
    OfferPricing,
    ServiceBoundary,
)

from protocol.canonicalization import canonical_json_bytes  # noqa: E402
from protocol.temporal import parse_instant  # noqa: E402

from identity.node_id import NodeIdError, parse_node_id  # noqa: E402

Result = Tuple[str, bool, str]


def ok(name: str, detail: str = "") -> Result:
    return (name, True, detail)


def fail(name: str, detail: str) -> Result:
    return (name, False, detail)


# ---------------------------------------------------------------------------
# Injected instants (LOCK-119 — no wall clock anywhere in the drill)
# ---------------------------------------------------------------------------

_T_REG = "2026-10-01T09:00:00Z"      # the registration instant
_T_OPEN = "2026-10-01T09:30:00Z"     # the open instant
_T_INSPECT = "2026-10-01T09:45:00Z"  # the inspection instant
_T_RESERVE = "2026-10-01T10:00:00Z"  # the reserve instant
_T_ACTIVATE = "2026-10-01T10:05:00Z"  # the activate instant
_T_MEASURE = "2026-10-01T11:00:00Z"  # the measure instant
_T_RECONFIGURE = "2026-10-01T11:30:00Z"  # the reconfigure instant
_T_REMEASURE = "2026-10-01T11:45:00Z"  # the idempotent re-measure instant
_T_RELEASE = "2026-10-01T12:00:00Z"  # the release instant
_T_CONTRACT = "2026-10-01T08:00:00Z"  # the contract walk instant (inside validity)
_T_VALID_FROM = "2026-10-01T00:00:00Z"
_T_VALID_END = "2026-11-01T00:00:00Z"
_T_EVAL = "2026-10-02T00:00:00Z"     # the eligibility/policy evaluation instant

#: The drill's provider domain identity (a canonical WORK-004 NodeID —
#: the offers/capabilities authorities require it; a TEST identity of
#: the accepted battery grammar, never trust).
_PROVIDER = "adcos:node:identity.sha256-hmac-dev.v1:" + "7" * 64

#: The drill's offer listing key (the provider's own id for the
#: listing — DATA, never a NodeID).
_OFFER_KEY = "offer:futureimt-thz-1"

#: The guarded action for the policy gate (the canonical projection of
#: contracts.COMMAND_KINDS — computed at the composition boundary, the
#: accepted M004 discipline).
_CONTRACT_ACTIONS = tuple("contract.%s" % kind for kind in COMMAND_KINDS)


def _prov(issuer: str, *refs: str) -> Provenance:
    return Provenance(issuer=issuer, decision_refs=tuple(refs))


def _mount(
    store=None,
    *,
    technology_id: str = REFERENCE_TECHNOLOGY_ID,
    label: str = REFERENCE_LABEL,
):
    """Wire the future-IMT composition through the ACCEPTED seam.

    Returns ``(capability, runtime, descriptor, requirements)``: the
    1.1 CapabilityAdapter, the WORK-016 runtime, the reference
    descriptor, and the canonical binding requirements map.
    """
    if store is None:
        store, _sid = ads._established_session()
    implementation, descriptor, requirements = mount_reference(
        now=_T_REG, label=label, technology_id=technology_id
    )
    runtime = AdapterRuntime(session_store=store)
    runtime.register(descriptor, implementation, now=_T_REG)
    opened = runtime.open_adapter(descriptor.adapter_id, now=_T_OPEN)
    assert opened.ok, "future-IMT reference open failed"
    capability = CapabilityAdapter(
        runtime, descriptor.adapter_id, standard_mechanisms=STANDARD_MECHANISMS
    )
    return capability, runtime, descriptor, requirements


def _full_lifecycle(capability, sid, requirements):
    """Drive the full 1.1 capability operation sequence on one mounted
    composition.  Returns the ordered (operation, result) pairs."""
    outcomes = []

    def record(operation: str, result) -> None:
        outcomes.append((operation, result))
        if not result.ok:
            raise AssertionError(
                "%s failed: %s" % (operation, result.failure)
            )

    record(
        "inspect-capabilities",
        capability.inspect_capabilities(now=_T_INSPECT),
    )
    record("inspect-offers", capability.inspect_offers(now=_T_INSPECT))
    record(
        "reserve",
        capability.reserve(
            kind="bandwidth",
            quantity=10,
            unit="gbps",
            purpose="m023-drill",
            now=_T_RESERVE,
        ),
    )
    record(
        "activate",
        capability.activate(
            reservation_id=outcomes[-1][1].value.allocation_id,
            session_id=sid,
            requirements=requirements,
            now=_T_ACTIVATE,
        ),
    )
    record(
        "measure",
        capability.measure(
            activation_id=outcomes[-1][1].value.activation_id,
            now=_T_MEASURE,
        ),
    )
    record(
        "reconfigure",
        capability.reconfigure(
            activation_id=outcomes[3][1].value.activation_id,
            requirements={"beam_class": "thz-focused", "carrier_gbps": 40},
            now=_T_RECONFIGURE,
        ),
    )
    record(
        "health",
        capability.health(now=_T_RECONFIGURE),
    )
    record(
        "release",
        capability.release(
            activation_id=outcomes[3][1].value.activation_id,
            now=_T_RELEASE,
        ),
    )
    return outcomes


# ---------------------------------------------------------------------------
# The offer/plan/eligibility composition fixtures (real accepted objects)
# ---------------------------------------------------------------------------


def _capability_statements() -> Tuple[CapabilityStatement, ...]:
    """Real WORK-005 capability statements for the composition's four
    declared capability references (the offers exchange grounding)."""
    return tuple(
        CapabilityStatement(
            capability_id=capability_id,
            schema_version="1.2",
            provider_identity=_PROVIDER,
            valid_from=_T_VALID_FROM,
            expires_at=_T_VALID_END,
        )
        for capability_id in REFERENCE_CAPABILITIES
    )


def _exchange() -> Tuple[OfferExchange, Any]:
    """A real M003 offer exchange carrying the future-IMT offer.

    The composition's capability surface grounds the offer's
    advertisement entries: REAL capability statements (WORK-005),
    their digests, and the classification the capabilities authority
    itself produced (``unknown_but_well_formed`` — carried verbatim
    as DATA, never re-decided here).  The offer's commitments express
    the declared surface in the frozen commitment vocabulary: the
    holographic-latency-class bound (<= 1 ms) and the terahertz
    carrier floor (100 Gbps).
    """
    exchange = OfferExchange()
    statements = _capability_statements()
    entries = tuple(
        AdvertisementEntry(
            capability_id=statement.capability_id,
            schema_version="1.2",
            statement_digest="sha256:"
            + hashlib.sha256(statement_to_bytes(statement)).hexdigest(),
            classification=classify_capability_id(statement.capability_id),
        )
        for statement in statements
    )
    advertisement = build_advertisement(
        provider=_PROVIDER,
        entries=entries,
        validity=ValidityInterval(not_before=_T_VALID_FROM, not_after=_T_VALID_END),
        provenance=_prov("prov:futureimt-thz"),
    )
    offer = build_offer(
        provider=_PROVIDER,
        provider_offer_key=_OFFER_KEY,
        schema_version=1,
        advertisements=(
            AdvertisementRef(
                advertisement_id=advertisement.advertisement_id,
                provenance=_prov("prov:futureimt-thz"),
            ),
        ),
        commitments=(
            OfferCommitment(
                kind="latency-bound-ms",
                params={"max_ms": 1},
                window=ValidityInterval(
                    not_before=_T_VALID_FROM, not_after=_T_VALID_END
                ),
                provenance=_prov("prov:futureimt-thz"),
            ),
            OfferCommitment(
                kind="throughput-floor-kbps",
                params={"min_kbps": 10_000_000},
                window=ValidityInterval(
                    not_before=_T_VALID_FROM, not_after=_T_VALID_END
                ),
                provenance=_prov("prov:futureimt-thz"),
            ),
        ),
        pricing=OfferPricing(
            currency="USD",
            price_minor=900,
            price_exponent=2,
            billing_mode="flat",
            provenance=_prov("comm:futureimt-ops"),
        ),
        service_boundaries=(
            ServiceBoundary(
                jurisdiction="GH",
                geography_refs=("mpcell:v1:coarse-50000m:12:-1",),
                provenance=_prov("prov:futureimt-thz"),
            ),
        ),
        validity=ValidityInterval(not_before=_T_VALID_FROM, not_after=_T_VALID_END),
        provenance=_prov("prov:futureimt-thz"),
    )
    exchange.register_advertisement(advertisement)
    exchange.register_offer(offer)
    return exchange, offer


def _mature_contract(offer) -> Any:
    """A real M002 contract carried to CONTRACT_ACTIVE with the
    future-IMT offer as its single accepted offer.

    The CONTRACT STORE is driven by the drill CALLER (this battery —
    the accepted composition discipline); the future-IMT module never
    touches it (the zero-core-delta proof, case_11).
    """
    store = ContractStore()
    created = store.submit(
        CreateContract(
            principal=ConnectivityPrincipal(
                principal_kind="APPLICATION", principal_ref="app:futureimt-drill-01"
            ),
            beneficiaries=(
                BeneficiaryScope(
                    beneficiary_kind="DEVICE", beneficiary_ref="dev:thz-probe-1"
                ),
            ),
            requirements=(
                OpaqueReference(
                    ref_kind="intent-requirements",
                    value="intent:m023-drill",
                    provenance=_prov("arch:drill"),
                ),
            ),
            hard_constraints=(
                HardConstraint(
                    kind="latency-bound",
                    params={"max_ms": 150},
                    provenance=_prov("prov:futureimt-thz"),
                ),
            ),
            validity=ValidityInterval(
                not_before=_T_VALID_FROM, not_after=_T_VALID_END
            ),
            service_properties=(
                OpaqueReference(
                    ref_kind="service-property",
                    value="prop:thz-committed-1",
                    provenance=_prov("prov:futureimt-thz"),
                ),
            ),
            usage_pricing_terms=OpaqueReference(
                ref_kind="usage-pricing-terms",
                value="terms:thz-comm-42",
                provenance=_prov("comm:futureimt-ops"),
            ),
            assurance_obligations=(
                OpaqueReference(ref_kind="assurance-obligation", value="oblig:thz-7"),
            ),
            execution_scope=(
                OpaqueReference(ref_kind="execution-scope", value="scope:thz-exec-1"),
            ),
            termination=TerminationRules(
                conditions=("principal-requested", "constraint-violated"),
                compensation=OpaqueReference(
                    ref_kind="compensation",
                    value="comp:thz-rule-9",
                    provenance=_prov("comm:futureimt-ops"),
                ),
            ),
            provenance=_prov("arch:drill", "dec:m023-drill"),
        ),
        recorded_at=_T_CONTRACT,
    )
    cid = created.contract.contract_id
    store.submit(
        SelectOffers(offers=(offer_reference(offer),)),
        recorded_at=_T_CONTRACT,
        contract_id=cid,
    )
    store.submit(
        ActivateContract(
            activated_at=_T_CONTRACT,
            signature_refs=(
                OpaqueReference(ref_kind="signature", value="sig:thz-ed25519-1"),
            ),
        ),
        recorded_at=_T_CONTRACT,
        contract_id=cid,
    )
    return store.contract(cid)


# ===========================================================================
# (a) registration + the frozen 1.1 operation vocabulary + typed records
# ===========================================================================


def case_01_registration_through_accepted_seam() -> Result:
    name = "case_01_registration_through_accepted_seam"
    store, sid = ads._established_session()
    capability, runtime, descriptor, _requirements = _mount(store)

    # (a) the registration went through the ACCEPTED seam: the runtime
    # recorded the REGISTERED event with the technology as DATA, and
    # the adapter id is the WORK-016 grammar (never a NodeID).
    events = runtime.events(adapter_id=descriptor.adapter_id)
    registered = [e for e in events if e.event_type == "registered"]
    if not registered:
        return fail(name, "no registered event through the accepted seam")
    details = registered[0].details
    if details.get("access_technology_id") != REFERENCE_TECHNOLOGY_ID:
        return fail(
            name,
            "registered event carries the wrong technology DATA: %r"
            % details.get("access_technology_id"),
        )
    parsed = parse_adapter_id(descriptor.adapter_id)
    if parsed.access_technology_id != REFERENCE_TECHNOLOGY_ID:
        return fail(name, "adapter id technology segment mismatch")
    try:
        parse_node_id(descriptor.adapter_id)
        return fail(name, "adapter id parses as a NodeID (identity leak)")
    except NodeIdError:
        pass

    # (b) the technology id is KNOWN through the reserved WORK-002
    # future path (classified BY REFERENCE through the accepted
    # classifier — the registry's own reserved entry, never activated).
    from adapters.validation import classify_access_technology_id

    classification = classify_access_technology_id(REFERENCE_TECHNOLOGY_ID)
    if classification != "known":
        return fail(
            name,
            "the reserved future path classifies %r, expected known" % classification,
        )

    # (c) the frozen 1.1 section 6 vocabulary: the seam's operation
    # names are NAME-EQUAL to the accepted M006 ADAPTER_OPERATIONS (the
    # domains never import each other's vocabulary — the composition
    # seam is by name; this battery imports both and compares).
    if tuple(CAPABILITY_OPERATIONS) != tuple(ADAPTER_OPERATIONS):
        return fail(
            name,
            "the 1.1 operation vocabulary drifted from the M006 frozen set",
        )
    if len(CAPABILITY_OPERATIONS) != 8:
        return fail(
            name,
            "the frozen 1.1 section 6 vocabulary has %d members" % len(CAPABILITY_OPERATIONS),
        )

    # (d) the seam's disclosed translation map covers every operation
    # (the re-bind translation is asserted case_04).
    translated = {op for op, _pairs in CAPABILITY_TRANSLATION_MAP}
    if translated != set(CAPABILITY_OPERATIONS):
        return fail(name, "the translation map does not cover the vocabulary")

    # (e) the composition is DRIVEN through the seam (the full
    # lifecycle runs green on the mounted composition).
    try:
        outcomes = _full_lifecycle(capability, sid, {"beam_class": REFERENCE_BEAM_CLASS, "carrier_gbps": REFERENCE_CARRIER_GBPS})
    except AssertionError as exc:
        return fail(name, str(exc)[:200])
    if len(outcomes) != 8:
        return fail(name, "expected 8 composed operations, drove %d" % len(outcomes))
    return ok(
        name,
        "registered through the accepted seam (technology as DATA; adapter "
        "id grammar distinct from NodeID); the reserved future path "
        "classifies known; the 8-operation vocabulary name-equal to the "
        "accepted M006 set; the full lifecycle drove green",
    )


def case_02_declared_capability_surface() -> Result:
    name = "case_02_declared_capability_surface"
    capability, _runtime, descriptor, _requirements = _mount()

    # (a) every declared capability reference classifies
    # UNKNOWN_BUT_WELL_FORMED through the CAPABILITIES AUTHORITY (by
    # reference — classification never re-decided here), and is
    # preserved verbatim on the descriptor.
    for capability_id in REFERENCE_CAPABILITIES:
        classification = classify_capability_id(capability_id)
        if classification != CapabilityIdClass.UNKNOWN_BUT_WELL_FORMED:
            return fail(
                name,
                "%s classifies %r (expected unknown_but_well_formed)"
                % (capability_id, classification),
            )
    if tuple(descriptor.capabilities) != REFERENCE_CAPABILITIES:
        return fail(name, "the descriptor did not preserve the declared references")

    # (b) the mediated capability view: the live exposure is the
    # declared set (filtered by the descriptor declaration), the
    # LOCK-112 mechanism tags are citation DATA, lifecycle OPEN.
    view = capability.inspect_capabilities(now=_T_INSPECT)
    if not view.ok:
        return fail(name, "inspect_capabilities failed")
    if tuple(view.value.capability_references) != REFERENCE_CAPABILITIES:
        return fail(
            name,
            "the mediated exposure is not the declared set: %r"
            % (view.value.capability_references,),
        )
    if tuple(view.value.standard_mechanisms) != STANDARD_MECHANISMS:
        return fail(name, "the mechanism tags drifted")
    if view.value.lifecycle != "OPEN":
        return fail(name, "lifecycle is %r" % view.value.lifecycle)

    # (c) the inspect_offers views mirror the declared resource
    # mapping (the provider-local LOCK-105-safe inventory slice).
    offers = capability.inspect_offers(now=_T_INSPECT)
    if not offers.ok:
        return fail(name, "inspect_offers failed")
    by_resource = {view.technology_resource: view for view in offers.value}
    expected = {
        "imt2030:terahertz-carrier-bandwidth": ("bandwidth", "gbps", REFERENCE_CARRIER_GBPS),
        "imt2030:adaptive-beam-associations": ("coverage", "count", REFERENCE_BEAM_ASSOCIATIONS),
    }
    if set(by_resource) != set(expected):
        return fail(
            name,
            "the offer views do not mirror the declared mapping: %s" % sorted(by_resource),
        )
    for resource, (kind, unit, quantity) in expected.items():
        view = by_resource[resource]
        if (view.kind, view.unit, view.quantity) != (kind, unit, quantity):
            return fail(
                name,
                "%s mapping drifted: %r" % (resource, (view.kind, view.unit, view.quantity)),
            )
        if tuple(view.capability_references) != REFERENCE_CAPABILITIES:
            return fail(name, "%s view lost the capability references" % resource)

    # (d) LOCK-110: the observable surface is the GENERIC link-metric
    # vocabulary only — the declared technology specifics (the
    # carrier range, the latency bound, the beam classes) are module
    # DATA, never boundary metrics.
    measure = capability.measure(now=_T_INSPECT)
    if not measure.ok:
        return fail(name, "adapter-level measure failed")
    from adapters import LinkMetricName

    observed_metrics = {sample["metric"] for sample in measure.value.samples}
    if observed_metrics != set(LinkMetricName.values()):
        return fail(
            name,
            "the observable metrics drifted from the generic vocabulary: %s"
            % sorted(observed_metrics),
        )

    # (e) the declared surface constants are coherent module DATA:
    # the carrier range bounds the reference carrier; the declared
    # beam classes and the holographic latency bound are fixed.
    low, high = CARRIER_BANDWIDTH_RANGE_GBPS
    if not (low <= REFERENCE_CARRIER_GBPS <= high):
        return fail(name, "the reference carrier is outside the declared range")
    if REFERENCE_BEAM_CLASS not in REFERENCE_BEAM_CLASSES:
        return fail(name, "the reference beam class is not in the declared vocabulary")
    if HOLOGRAPHIC_LATENCY_BOUND_US <= 0:
        return fail(name, "the declared latency bound is not positive")
    if CREDENTIAL_SLOT_NAME in ("private_key", "password", "token"):
        return fail(name, "the credential slot names secret material")
    return ok(
        name,
        "4 declared references preserved verbatim (unknown_but_well_formed via "
        "the capabilities authority); the views mirror the declared mapping; "
        "LOCK-110 generic-metric observability; the declared surface is "
        "coherent module DATA",
    )


def case_03_nine_operations_typed_records() -> Result:
    name = "case_03_nine_operations_typed_records"
    store, sid = ads._established_session()
    capability, runtime, descriptor, requirements = _mount(store)
    requirements = dict(requirements)

    # The typed record sequence with canonical round-trips through the
    # ACCEPTED reconstruction functions (tamper evidence at load).
    reserved = capability.reserve(
        kind="bandwidth", quantity=10, unit="gbps",
        purpose="m023-drill", now=_T_RESERVE,
    )
    if not reserved.ok:
        return fail(name, "reserve failed: %s" % reserved.failure)
    allocation = reserved.value
    if (allocation.kind, allocation.unit, allocation.quantity) != ("bandwidth", "gbps", 10):
        return fail(name, "the Allocation record drifted from the request")
    if allocation.quantity_base != 10_000_000_000:
        return fail(name, "quantity_base is not the integer base-unit translation")

    activated = capability.activate(
        reservation_id=allocation.allocation_id, session_id=sid,
        requirements=requirements, now=_T_ACTIVATE,
    )
    if not activated.ok:
        return fail(name, "activate failed: %s" % activated.failure)
    activation = activated.value
    if activation.state != "ACTIVE" or activation.session_id != sid:
        return fail(name, "the Activation record is not the typed ACTIVE shape")
    if dict(activation.requirements) != requirements:
        return fail(name, "the requirements snapshot was not preserved verbatim")

    measured = capability.measure(
        activation_id=activation.activation_id, now=_T_MEASURE
    )
    if not measured.ok:
        return fail(name, "measure failed: %s" % measured.failure)
    if measured.value.activation_id != activation.activation_id:
        return fail(name, "the Measurement is not attributed to the activation")

    reconfigured = capability.reconfigure(
        activation_id=activation.activation_id,
        requirements={"beam_class": "thz-focused", "carrier_gbps": 40},
        now=_T_RECONFIGURE,
    )
    if not reconfigured.ok:
        return fail(name, "reconfigure failed: %s" % reconfigured.failure)
    if dict(reconfigured.value.applied_requirements) != {
        "beam_class": "thz-focused", "carrier_gbps": 40,
    }:
        return fail(name, "the applied requirements snapshot drifted")

    health = capability.health(now=_T_RECONFIGURE)
    if not health.ok:
        return fail(name, "health failed")
    # deterministic adaptive-beam occupancy: the outstanding beam
    # grant degrades the effective health (reported DATA, computed by
    # the runtime — LOCK-017)
    if health.value.state != "DEGRADED":
        return fail(name, "expected DEGRADED with an outstanding beam grant")

    released = capability.release(
        activation_id=activation.activation_id, now=_T_RELEASE
    )
    if not released.ok:
        return fail(name, "release failed: %s" % released.failure)
    if tuple(released.value.released_kinds) != ("activation", "reservation"):
        return fail(name, "the ReleaseReceipt did not disclose both kinds")

    healthy_after = capability.health(now=_T_RELEASE)
    if healthy_after.value.state != "HEALTHY":
        return fail(name, "expected HEALTHY after the beam grant was released")

    # Canonical round-trips: every typed record reconstructs through
    # the accepted capability.py constructors, byte-identically, and
    # a tampered record fails closed (identity recomputed at load).
    constructors = (
        ("activation", activation_from_mapping, activation),
        ("measurement", measurement_from_mapping, measured.value),
        ("reconfiguration", reconfiguration_from_mapping, reconfigured.value),
        ("release-receipt", release_receipt_from_mapping, released.value),
    )
    for label, constructor, record in constructors:
        document = record.to_dict()
        try:
            rebuilt = constructor(document)
        except AdapterError as exc:
            return fail(name, "%s round-trip rejected: %s" % (label, exc.detail))
        if canonical_json_bytes(rebuilt.to_dict()) != canonical_json_bytes(document):
            return fail(name, "%s round-trip is not byte-identical" % label)
        tampered = dict(document)
        tampered["sequence"] = document["sequence"] + 1
        try:
            constructor(tampered)
            return fail(name, "%s tamper evidence missing" % label)
        except AdapterError:
            pass

    # The deterministic engine counters: the measured traffic is the
    # pure function of the engine's grant/bearer counters (one grant +
    # one bearer at the measured instant -> 2e9 bytes each direction).
    traffic = measured.value.samples
    by_metric = {sample["metric"]: sample["value"] for sample in traffic}
    if by_metric.get("rx-bytes-total") != 2_000_000_000:
        return fail(
            name,
            "rx-bytes-total %r is not the deterministic counter value"
            % by_metric.get("rx-bytes-total"),
        )
    if by_metric.get("retransmit-count") != 0:
        return fail(name, "retransmit-count drifted from the reference shape")

    # Failed operations never advance the activation ledger: a typed
    # failure (undeclared beam class) creates no activation.
    before_ledger = len(capability.activations())
    reserved2 = capability.reserve(
        kind="bandwidth", quantity=1, unit="gbps",
        purpose="m023-ledger-probe", now=_T_RELEASE,
    )
    rejected = capability.activate(
        reservation_id=reserved2.value.allocation_id, session_id=sid,
        requirements={"beam_class": "undeclared-beam", "carrier_gbps": 40},
        now=_T_RELEASE,
    )
    if rejected.ok:
        return fail(name, "the undeclared beam class was accepted")
    if rejected.failure.reason != "invalid-input":
        return fail(
            name, "wrong typed rejection reason: %r" % rejected.failure.reason
        )
    if len(capability.activations()) != before_ledger:
        return fail(name, "a failed activate advanced the activation ledger")
    return ok(
        name,
        "typed Allocation/Activation/Measurement/Reconfiguration/"
        "ReleaseReceipt/HealthReport sequence with byte-identical canonical "
        "round-trips + tamper evidence; deterministic counters; failed ops "
        "never advance the ledger",
    )


# ===========================================================================
# (b) the deterministic re-bind translation
# ===========================================================================


def case_04_rebind_translation_mid_session() -> Result:
    name = "case_04_rebind_translation_mid_session"
    store, sid = ads._established_session()
    capability, runtime, _descriptor, requirements = _mount(store)
    requirements = dict(requirements)

    # (a) the disclosed translation: reconfigure composes onto the
    # deterministic (unbind_session, bind_session) pair — the frozen
    # map declares it (imported by reference from the accepted seam).
    translation = dict(CAPABILITY_TRANSLATION_MAP)
    if translation.get("reconfigure") != ("unbind_session", "bind_session"):
        return fail(
            name,
            "the re-bind translation drifted: %r" % translation.get("reconfigure"),
        )

    reserved = capability.reserve(
        kind="bandwidth", quantity=10, unit="gbps",
        purpose="m023-rebind", now=_T_RESERVE,
    )
    activated = capability.activate(
        reservation_id=reserved.value.allocation_id, session_id=sid,
        requirements=requirements, now=_T_ACTIVATE,
    )
    activation = activated.value
    previous_binding_id = activation.binding_id
    if runtime.binding(previous_binding_id).state != "BOUND":
        return fail(name, "the initial binding is not BOUND")

    # (b) the re-bind: the PREVIOUS binding is released first (the
    # runtime records the explicit teardown), the new binding is
    # created with the new requirements, the reservation is preserved,
    # and the session is the SAME session.
    new_requirements = {"beam_class": "thz-focused", "carrier_gbps": 40}
    reconf = capability.reconfigure(
        activation_id=activation.activation_id,
        requirements=new_requirements, now=_T_RECONFIGURE,
    )
    if not reconf.ok:
        return fail(name, "reconfigure failed: %s" % reconf.failure)
    record = reconf.value
    if record.previous_binding_id != previous_binding_id:
        return fail(name, "the previous binding id was not preserved on the record")
    if record.binding_id == previous_binding_id:
        return fail(name, "the re-bind did not create a NEW binding")
    if record.session_id != sid or record.reservation_id != reserved.value.allocation_id:
        return fail(name, "the re-bind changed the session or the reservation")
    if runtime.binding(previous_binding_id).state != "RELEASED":
        return fail(name, "the previous binding was not released first")
    if runtime.binding(record.binding_id).state != "BOUND":
        return fail(name, "the new binding is not BOUND")

    # (c) the activation ledger: ACTIVE -> RECONFIGURED with the new
    # requirements snapshot and the reconfiguration instant.
    updated = capability.activation(activation.activation_id)
    if updated.state != "RECONFIGURED":
        return fail(name, "the activation did not transition to RECONFIGURED")
    if dict(updated.requirements) != new_requirements:
        return fail(name, "the activation requirements snapshot was not replaced")
    if updated.last_reconfigured_instant != _T_RECONFIGURE:
        return fail(name, "last_reconfigured_instant was not recorded")

    # (d) the idempotent edge: RECONFIGURED -> RECONFIGURED (repeated
    # reconfigurations are the reference semantics of standards-native
    # steering/beam reweighting updates).
    second = capability.reconfigure(
        activation_id=activation.activation_id,
        requirements=dict(requirements), now=_T_REMEASURE,
    )
    if not second.ok:
        return fail(name, "the idempotent re-reconfigure failed")
    if second.value.previous_binding_id != record.binding_id:
        return fail(name, "the second re-bind did not chain from the new binding")
    if capability.activation(activation.activation_id).state != "RECONFIGURED":
        return fail(name, "the re-reconfigure left the wrong state")

    # (e) the measurement trail survives the re-bind (the activation's
    # attributed measurements accumulate deterministically).
    measured = capability.measure(
        activation_id=activation.activation_id, now=_T_REMEASURE
    )
    if not measured.ok:
        return fail(name, "measure after re-bind failed")
    trail = capability.measurements(activation.activation_id)
    if len(trail) != 1 or trail[0].measurement_id != measured.value.measurement_id:
        return fail(name, "the measurement trail was not preserved across the re-bind")

    # (f) the reservation is still held by the activation: the
    # reservation-only release fails closed until the activation is
    # released first (no silent dangling capacity).
    try:
        capability.release(reservation_id=reserved.value.allocation_id, now=_T_RELEASE)
        return fail(name, "the reservation-only release bypassed the live activation")
    except AdapterError as exc:
        if exc.reason != "allocation-state":
            return fail(name, "wrong typed reason: %r" % exc.reason)

    released = capability.release(
        activation_id=activation.activation_id, now=_T_RELEASE
    )
    if not released.ok:
        return fail(name, "release after re-bind failed")
    return ok(
        name,
        "the disclosed (unbind, bind) translation: previous binding released "
        "first, new binding BOUND, same session + preserved reservation; "
        "ACTIVE->RECONFIGURED with the replaced snapshot; idempotent "
        "re-reconfigure; trail preserved; reservation guarded",
    )


# ===========================================================================
# (c) the offer/executionplan/eligibility composition — BY REFERENCE
# ===========================================================================


def case_05_offer_exchange_composition() -> Result:
    name = "case_05_offer_exchange_composition"
    exchange, offer = _exchange()

    # (a) the offer is a REAL M003 record: content-derived identity,
    # provider domain, grounding advertisements, commitments, pricing,
    # service boundaries, provenance (LOCK-118).
    if not offer.offer_id.startswith("sha256:"):
        return fail(name, "the offer id is not content-derived")
    if offer.provider != _PROVIDER:
        return fail(name, "the offer provider domain drifted")

    # (b) the grounding advertisement carries the composition's four
    # declared capability references with the classification the
    # CAPABILITIES AUTHORITY itself produced (by reference, verbatim
    # DATA — never re-decided here).
    advertisement = exchange.advertisements()[0] if exchange.advertisements() else None
    if advertisement is None:
        return fail(name, "the advertisement did not register")
    entries = advertisement.entries
    if tuple(entry.capability_id for entry in entries) != REFERENCE_CAPABILITIES:
        return fail(name, "the advertisement entries drifted from the declared surface")
    for entry in entries:
        if entry.classification != "unknown_but_well_formed":
            return fail(
                name,
                "entry classification %r is not the authority's own verdict"
                % entry.classification,
            )
        expected_digest = "sha256:" + hashlib.sha256(
            statement_to_bytes(
                next(
                    statement
                    for statement in _capability_statements()
                    if statement.capability_id == entry.capability_id
                )
            )
        ).hexdigest()
        if entry.statement_digest != expected_digest:
            return fail(name, "the statement digest drifted for %s" % entry.capability_id)

    # (c) the offer's commitments express the declared surface in the
    # FROZEN commitment vocabulary: the holographic-latency-class
    # bound (<= 1 ms) and the terahertz carrier floor (100 Gbps).
    commitments = {commitment.kind: commitment for commitment in offer.commitments}
    if commitments.get("latency-bound-ms").params.get("max_ms") != 1:
        return fail(name, "the latency commitment drifted from the declared bound")
    if commitments.get("throughput-floor-kbps").params.get("min_kbps") != 10_000_000:
        return fail(name, "the throughput commitment drifted from the declared carrier")

    # (d) the contract-shaped reference resolves through the exchange
    # (the M003 authority's own usability verdict — by reference).
    reference = offer_reference(offer)
    if reference.ref_kind != "offer":
        return fail(name, "the offer reference kind drifted")
    try:
        resolved = exchange.resolve(reference, at_instant=_T_EVAL)
    except Exception as exc:  # noqa: BLE001
        return fail(name, "resolve failed: %s" % exc)
    if resolved.offer_id != offer.offer_id:
        return fail(name, "resolve returned a different offer")
    jurisdictions = tuple(
        boundary.jurisdiction for boundary in resolved.service_boundaries
    )
    if jurisdictions != ("GH",):
        return fail(name, "the service-boundary jurisdictions drifted")
    return ok(
        name,
        "real WORK-005 statements + M003 advertisement/offer composed by "
        "reference (the 4 declared references with the authority's own "
        "classification); the declared surface expressed in the frozen "
        "commitment vocabulary; the reference resolves usable",
    )


def case_06_executionplan_bridge_lock109() -> Result:
    name = "case_06_executionplan_bridge_lock109"
    exchange, offer = _exchange()
    contract = _mature_contract(offer)

    # (a) the real M002 contract is CONTRACT_ACTIVE (plannable) with
    # the future-IMT offer accepted (the CALLER drove the store — the
    # module never touched it).
    if contract.state != "CONTRACT_ACTIVE":
        return fail(name, "the contract is %r, expected CONTRACT_ACTIVE" % contract.state)
    if contract.state in TERMINAL_STATES:
        return fail(name, "the contract is terminal")
    if len(contract.accepted_offers) != 1:
        return fail(name, "the contract did not accept exactly one offer")

    # (b) the LOCK-109 bridge: translate the contract to a REAL
    # ExecutionPlan whose ONE primary segment references the
    # future-IMT offer and engages the FULL frozen operation
    # vocabulary.
    future_ref = offer_reference(offer)
    plan = translate_contract(
        contract,
        (
            SegmentInput(
                offer_reference=future_ref,
                role="primary",
                operations=ADAPTER_OPERATIONS,
                provenance=_prov("optimizer:futureimt-v1", "dec:m023-drill"),
            ),
        ),
        provenance=_prov("optimizer:futureimt-v1", "dec:m023-plan"),
    )
    segment = plan.segments[0]
    if tuple(segment.operations) != tuple(CAPABILITY_OPERATIONS):
        return fail(
            name,
            "the segment operations are not the frozen vocabulary in "
            "canonical order: %r" % (segment.operations,),
        )
    if segment.offer_reference.value != future_ref.value:
        return fail(name, "the segment does not reference the future-IMT offer")
    fingerprint_before = plan.constraint_fingerprint
    constraints_before = [c.to_dict() for c in plan.hard_constraints]

    # (c) DRIVE the segment's operations through the composition (the
    # case_66 discipline: the real M006 transition kernel advances the
    # segment; the composition executes behind the seam).
    store, sid = ads._established_session()
    capability, _runtime, _descriptor, requirements = _mount(store)
    requirements = dict(requirements)

    reserved = capability.reserve(
        kind="bandwidth", quantity=10, unit="gbps",
        purpose="segment-%s" % segment.segment_id[:18], now=_T_RESERVE,
    )
    if not reserved.ok:
        return fail(name, "segment reserve failed")
    plan = apply_segment_transition(plan, segment.segment_id, "RESERVED", at_instant=_T_RESERVE)
    segment = plan.segments[0]

    activated = capability.activate(
        reservation_id=reserved.value.allocation_id, session_id=sid,
        requirements=requirements, now=_T_ACTIVATE,
    )
    if not activated.ok:
        return fail(name, "segment activate failed")
    plan = apply_segment_transition(plan, segment.segment_id, "ACTIVATED", at_instant=_T_ACTIVATE)
    segment = plan.segments[0]

    measured = capability.measure(
        activation_id=activated.value.activation_id, now=_T_MEASURE
    )
    if not measured.ok:
        return fail(name, "segment measure failed")
    plan = apply_segment_transition(plan, segment.segment_id, "MEASURED", at_instant=_T_MEASURE)
    segment = plan.segments[0]

    reconf = capability.reconfigure(
        activation_id=activated.value.activation_id,
        requirements={"beam_class": "thz-focused", "carrier_gbps": 40},
        now=_T_RECONFIGURE,
    )
    if not reconf.ok:
        return fail(name, "segment reconfigure failed")
    # reconfigure does NOT move the segment state (the M006 vocabulary
    # owns segment states and has no RECONFIGURED state — the
    # adapter-side typed transition is the realization-level truth).
    if segment.state != "MEASURED":
        return fail(name, "reconfigure moved the segment state")
    if capability.activation(activated.value.activation_id).state != "RECONFIGURED":
        return fail(name, "the activation record did not transition")

    # idempotent re-measurement (the M006 MEASURED -> MEASURED edge)
    again = capability.measure(
        activation_id=activated.value.activation_id, now=_T_REMEASURE
    )
    if not again.ok:
        return fail(name, "segment re-measure failed")
    plan = apply_segment_transition(plan, segment.segment_id, "MEASURED", at_instant=_T_REMEASURE)
    segment = plan.segments[0]

    # the remaining vocabulary members (inspections + health)
    for inspection in (
        capability.inspect_capabilities(now=_T_REMEASURE),
        capability.inspect_offers(now=_T_REMEASURE),
        capability.health(now=_T_REMEASURE),
    ):
        if not inspection.ok:
            return fail(name, "a segment inspection member failed")

    released = capability.release(
        activation_id=activated.value.activation_id, now=_T_RELEASE
    )
    if not released.ok:
        return fail(name, "segment release failed")
    plan = apply_segment_transition(plan, segment.segment_id, "RELEASED", at_instant=_T_RELEASE)
    segment = plan.segments[0]
    if segment.state != "RELEASED" or not segment.is_terminal():
        return fail(name, "the segment did not reach terminal RELEASED")

    # (d) LOCK-108 + attribution: execution never touched the plan's
    # constraint truth; the pure cross-authority gate still passes.
    if plan.constraint_fingerprint != fingerprint_before:
        return fail(name, "the constraint fingerprint changed")
    if [c.to_dict() for c in plan.hard_constraints] != constraints_before:
        return fail(name, "the constraint set changed")
    verify_plan_preserves_contract(plan, contract)

    # (e) the plan rides as an opaque execution-artifact reference
    # (LOCK-109/LOCK-117 — never a second contract authority).
    reference = plan_reference(plan)
    if reference.ref_kind != "execution-artifact":
        return fail(name, "the plan reference kind drifted: %r" % reference.ref_kind)
    return ok(
        name,
        "the real LOCK-109 bridge translated the CONTRACT_ACTIVE contract to a "
        "plan whose segment (all 8 operations, the future-IMT offer) drove the "
        "composition PLANNED->...->RELEASED; constraints + fingerprint "
        "unchanged; the plan rides as an opaque execution artifact",
    )


def case_07_eligibility_policy_admission() -> Result:
    name = "case_07_eligibility_policy_admission"
    exchange, offer = _exchange()
    contract = _mature_contract(offer)

    # (a) compose the offer reference facts by resolving the accepted
    # offer reference through the M003 exchange (BY REFERENCE — the
    # exchange owns usability; the composition carries the verdict as
    # DATA).
    resolved = exchange.resolve(offer_reference(offer), at_instant=_T_EVAL)
    offer_facts = (
        OfferReferenceEligibilityFacts(
            value=offer_reference(offer).value,
            offer_id=resolved.offer_id,
            provider=resolved.provider,
            jurisdictions=tuple(
                boundary.jurisdiction for boundary in resolved.service_boundaries
            ),
            usable=True,
        ),
    )

    # (b) the eligibility gate: a REAL ContractEligibilityRuleset
    # admitting the future-IMT provider + jurisdiction -> the offer
    # reference and the contract reference set are ELIGIBLE.
    ruleset = ContractEligibilityRuleset(
        ruleset_id="rs-m023-drill",
        version=1,
        issuer="ops:platform-eligibility",
        permitted_providers=(_PROVIDER,),
        permitted_jurisdictions=("GH",),
        valid_from=_T_VALID_FROM,
        valid_until=_T_VALID_END,
        decision_refs=("decision:platform-eligibility-m023",),
    )
    offer_eligibility = evaluate_offer_reference_eligibility(
        offer_facts[0], ruleset, at_instant=_T_EVAL
    )
    if not offer_eligibility.eligible:
        return fail(
            name,
            "the future-IMT offer was denied: %s" % (offer_eligibility.reasons,),
        )
    contract_facts = ContractReferenceFacts(
        contract_id=contract.contract_id,
        state=contract.state,
        state_is_terminal=contract.state in TERMINAL_STATES,
        validity=ValidityWindow(
            not_before=contract.validity.not_before,
            not_after=contract.validity.not_after,
        ),
        offer_facts=offer_facts,
    )
    contract_eligibility = evaluate_contract_reference_eligibility(
        contract_facts, ruleset, at_instant=_T_EVAL
    )
    if not contract_eligibility.eligible:
        return fail(
            name,
            "the contract reference set was denied: %s"
            % (contract_eligibility.reasons,),
        )

    # (c) the denial edge is decision DATA (never an exception): a
    # ruleset that does not permit the provider denies with the typed
    # reason code — the gate stays fail-closed.
    other_ruleset = ContractEligibilityRuleset(
        ruleset_id="rs-m023-other",
        version=1,
        issuer="ops:platform-eligibility",
        permitted_providers=("adcos:node:identity.sha256-hmac-dev.v1:" + "9" * 64,),
        permitted_jurisdictions=("GH",),
        valid_from=_T_VALID_FROM,
        valid_until=_T_VALID_END,
        decision_refs=("decision:platform-eligibility-m023",),
    )
    denial = evaluate_offer_reference_eligibility(
        offer_facts[0], other_ruleset, at_instant=_T_EVAL
    )
    if denial.eligible or denial.reasons != (
        ContractEligibilityReason.PROVIDER_NOT_PERMITTED,
    ):
        return fail(
            name,
            "the unpermitted provider was not denied with the typed reason: %r"
            % (denial.reasons,),
        )

    # (d) the policy gate: a REAL ContractConstraintRule (ALLOW on the
    # canonical guarded action) + set + context composed from the real
    # contract -> the ALLOW decision (deterministic evaluation).
    if "contract.select-offers" not in _CONTRACT_ACTIONS:
        return fail(name, "the guarded action is not in the canonical projection")
    rule = ContractConstraintRule(
        rule_id="allow-m023-select",
        action="contract.select-offers",
        effect=ContractConstraintEffect.ALLOW,
        subjects=(),
        conditions=(),
        specificity=1,
        priority=0,
        valid_from=_T_VALID_FROM,
        valid_until=_T_VALID_END,
        issuer="ops:platform-constraints",
        decision_refs=("decision:platform-constraints-m023",),
    )
    constraint_set = ContractConstraintSet(
        set_id="cps-m023-drill",
        version=1,
        rules=(rule,),
        issuer="ops:platform-constraints",
        valid_from=_T_VALID_FROM,
        valid_until=_T_VALID_END,
    )
    context = ContractConstraintContext(
        action="contract.select-offers",
        principal_kind=contract.principal.principal_kind,
        principal_ref=contract.principal.principal_ref,
        beneficiary_kinds=tuple(
            beneficiary.beneficiary_kind for beneficiary in contract.beneficiaries
        ),
        contract_state=contract.state,
        hard_constraint_kinds=tuple(
            constraint.kind for constraint in contract.hard_constraints
        ),
        validity=ValidityWindow(
            not_before=contract.validity.not_before,
            not_after=contract.validity.not_after,
        ),
        accepted_offer_values=tuple(
            reference.value for reference in contract.accepted_offers
        ),
        offer_facts=offer_facts,
        evaluation_instant=_T_EVAL,
    )
    outcome = evaluate_contract_constraints(constraint_set, context)
    if not outcome.ok or outcome.decision is None:
        return fail(name, "the policy evaluation failed: %s" % outcome.detail[:150])
    if outcome.decision.code != ContractConstraintDecisionCode.ALLOW:
        return fail(
            name,
            "the policy decision is %r, expected ALLOW" % outcome.decision.code,
        )

    # (e) the deny edge: an equal-precedence DENY rule beats the allow
    # (the harvested deny-wins conflict resolution — deterministic).
    deny_rule = ContractConstraintRule(
        rule_id="deny-m023-select",
        action="contract.select-offers",
        effect=ContractConstraintEffect.DENY,
        subjects=(),
        conditions=(),
        specificity=1,
        priority=0,
        valid_from=_T_VALID_FROM,
        valid_until=_T_VALID_END,
        issuer="ops:platform-constraints",
        decision_refs=("decision:platform-constraints-m023",),
    )
    mixed_set = ContractConstraintSet(
        set_id="cps-m023-drill",
        version=1,
        rules=(rule, deny_rule),
        issuer="ops:platform-constraints",
        valid_from=_T_VALID_FROM,
        valid_until=_T_VALID_END,
    )
    denied = evaluate_contract_constraints(mixed_set, context)
    if not denied.ok or denied.decision is None:
        return fail(name, "the mixed evaluation failed: %s" % denied.detail[:150])
    if denied.decision.code != ContractConstraintDecisionCode.DENY:
        return fail(
            name,
            "the deny-wins resolution drifted: %r" % denied.decision.code,
        )
    return ok(
        name,
        "the offer + contract reference sets ELIGIBLE under a real ruleset; "
        "the unpermitted provider denied as decision DATA; the policy gate "
        "ALLOW on the canonical guarded action; deny-wins deterministic",
    )


# ===========================================================================
# (d) LOCK-110 isolation, typed failures, the open world, zero core delta
# ===========================================================================


def case_08_lock110_provider_neutral_records() -> Result:
    name = "case_08_lock110_provider_neutral_records"
    store, sid = ads._established_session()
    capability, runtime, _descriptor, requirements = _mount(store)
    requirements = dict(requirements)

    # (a) drive the lifecycle and collect EVERY 1.1 boundary record's
    # canonical bytes.
    view = capability.inspect_capabilities(now=_T_INSPECT)
    offers = capability.inspect_offers(now=_T_INSPECT)
    reserved = capability.reserve(
        kind="bandwidth", quantity=10, unit="gbps",
        purpose="m023-isolation", now=_T_RESERVE,
    )
    activated = capability.activate(
        reservation_id=reserved.value.allocation_id, session_id=sid,
        requirements=requirements, now=_T_ACTIVATE,
    )
    measured = capability.measure(
        activation_id=activated.value.activation_id, now=_T_MEASURE
    )
    reconf = capability.reconfigure(
        activation_id=activated.value.activation_id,
        requirements={"beam_class": "thz-focused", "carrier_gbps": 40},
        now=_T_RECONFIGURE,
    )
    health = capability.health(now=_T_RECONFIGURE)
    released = capability.release(
        activation_id=activated.value.activation_id, now=_T_RELEASE
    )
    def _canonical(record: Any) -> bytes:
        if hasattr(record, "to_canonical_bytes"):
            return record.to_canonical_bytes()
        return canonical_json_bytes(record.to_dict())

    documents = [
        _canonical(view.value),
        _canonical(offers.value[0]),
        _canonical(offers.value[1]),
        _canonical(reserved.value),
        _canonical(activated.value),
        _canonical(measured.value),
        _canonical(reconf.value),
        _canonical(health.value),
        _canonical(released.value),
    ]
    # (b) NO opaque technology reference crosses into any record's
    # canonical bytes (LOCK-110: they stay behind the runtime).
    for index, payload in enumerate(documents):
        if b"imt2030:beam" in payload:
            return fail(name, "document %d leaks an opaque beam reference" % index)
        if b"imt2030:beam-grant" in payload:
            return fail(name, "document %d leaks an opaque beam-grant reference" % index)

    # (c) the opacity discipline: the runtime's OWN binding record
    # carries the opaque bearer ref (data behind the boundary — passed
    # back on unbind, never a key or authority source).
    # (the binding was released by the release() above; the opacity
    # check ran on the record captured below before teardown)
    binding = runtime.binding(activated.value.binding_id)
    if not binding.bearer_ref.startswith("imt2030:beam:"):
        return fail(name, "the bearer ref grammar drifted: %r" % binding.bearer_ref[:24])
    if binding.state != "RELEASED":
        return fail(name, "the binding was not released by the teardown")

    # (d) the view bytes carry the mechanism tags as citation DATA and
    # the technology id (declared DATA), never a provider-native type.
    if b"itu-r-m2160-imt2030-framework" not in view.value.to_canonical_bytes():
        return fail(name, "the LOCK-112 citation tags are not carried in the view")
    if b"access.3gpp.nr.imt2030" not in view.value.to_canonical_bytes():
        return fail(name, "the technology id is not carried as declared DATA")
    return ok(
        name,
        "every 1.1 record canonical byte-set is provider-neutral (no opaque "
        "beam/beam-grant reference crosses); the bearer ref stays opaque "
        "behind the runtime; the tags + technology id ride as DATA",
    )


def case_09_typed_errors_fail_closed() -> Result:
    name = "case_09_typed_errors_fail_closed"
    store, sid = ads._established_session()
    capability, _runtime, _descriptor, requirements = _mount(store)
    requirements = dict(requirements)

    def expect_isolated(label, action, reason) -> Optional[Result]:
        result = action()
        if result.ok:
            return fail(name, "%s was accepted" % label)
        if result.failure is None or result.failure.reason != reason:
            return fail(
                name,
                "%s rejected with %r (expected %r)"
                % (label, result.failure and result.failure.reason, reason),
            )
        return None

    def expect_raised(label, action, reason) -> Optional[Result]:
        try:
            action()
        except AdapterError as exc:
            if exc.reason != reason:
                return fail(
                    name,
                    "%s raised %r (expected %r)" % (label, exc.reason, reason),
                )
            return None
        return fail(name, "%s was accepted (expected %s)" % (label, reason))

    # (a) the declared-surface rejections (the module's own typed
    # discipline — isolated failure VALUES through the sandbox, never
    # exceptions into core state).
    reserved = capability.reserve(
        kind="bandwidth", quantity=10, unit="gbps",
        purpose="m023-typed-errors", now=_T_RESERVE,
    )
    allocation_id = reserved.value.allocation_id
    for label, bad_requirements in (
        ("undeclared beam class", {"beam_class": "undeclared-beam", "carrier_gbps": 40}),
        ("carrier below the declared range", {"beam_class": "thz-focused", "carrier_gbps": 5}),
        ("carrier above the declared range", {"beam_class": "thz-focused", "carrier_gbps": 500}),
        ("non-integer carrier", {"beam_class": "thz-focused", "carrier_gbps": True}),
        ("missing beam class", {"carrier_gbps": 40}),
        ("absent requirements", None),
    ):
        outcome = expect_isolated(
            label,
            lambda bad=bad_requirements: capability.activate(
                reservation_id=allocation_id, session_id=sid,
                requirements=bad, now=_T_ACTIVATE,
            ),
            "invalid-input",
        )
        if outcome is not None:
            return outcome

    # (b) the LOCK-119 secret-material rejection (the accepted seam's
    # own caller-side discipline).
    outcome = expect_raised(
        "secret-shaped requirements",
        lambda: capability.activate(
            reservation_id=allocation_id, session_id=sid,
            requirements={"password": "hunter2"}, now=_T_ACTIVATE,
        ),
        "invalid-input",
    )
    if outcome is not None:
        return outcome

    # (c) the runtime-level rejections (typed, deterministic).
    outcome = expect_raised(
        "unmapped resource kind",
        lambda: capability.reserve(
            kind="compute", quantity=1, unit="millicores",
            purpose="m023-unmapped", now=_T_RESERVE,
        ),
        "mapping-invalid",
    )
    if outcome is not None:
        return outcome
    outcome = expect_isolated(
        "capacity exhaustion",
        lambda: capability.reserve(
            kind="bandwidth", quantity=200, unit="gbps",
            purpose="m023-exhaustion", now=_T_RESERVE,
        ),
        "capacity-exhausted",
    )
    if outcome is not None:
        return outcome
    outcome = expect_raised(
        "unknown reservation",
        lambda: capability.activate(
            reservation_id="sha256:" + "0" * 64, session_id=sid,
            requirements=requirements, now=_T_ACTIVATE,
        ),
        "allocation-unknown",
    )
    if outcome is not None:
        return outcome
    outcome = expect_raised(
        "unknown activation reconfigure",
        lambda: capability.reconfigure(
            activation_id="sha256:" + "1" * 64,
            requirements=requirements, now=_T_RECONFIGURE,
        ),
        "allocation-unknown",
    )
    if outcome is not None:
        return outcome
    outcome = expect_raised(
        "release with no ids",
        lambda: capability.release(now=_T_RELEASE),
        "invalid-input",
    )
    if outcome is not None:
        return outcome

    # (d) the terminal-state rejections: release, then the terminal
    # edges fail closed.
    activated = capability.activate(
        reservation_id=allocation_id, session_id=sid,
        requirements=requirements, now=_T_ACTIVATE,
    )
    if not activated.ok:
        return fail(name, "the clean activation failed")
    activation_id = activated.value.activation_id
    released = capability.release(activation_id=activation_id, now=_T_RELEASE)
    if not released.ok:
        return fail(name, "the clean release failed")
    for label, reason, action in (
        ("reconfigure a RELEASED activation", "state-conflict",
         lambda: capability.reconfigure(
             activation_id=activation_id, requirements=requirements,
             now=_T_RECONFIGURE)),
        ("measure a RELEASED activation", "state-conflict",
         lambda: capability.measure(activation_id=activation_id, now=_T_MEASURE)),
        ("double release", "state-conflict",
         lambda: capability.release(activation_id=activation_id, now=_T_RELEASE)),
    ):
        outcome = expect_raised(label, action, reason)
        if outcome is not None:
            return outcome
    return ok(
        name,
        "the declared-surface matrix (6 typed isolated rejections), the "
        "LOCK-119 secret rejection, the runtime rejections (mapping/capacity/"
        "unknown ids), and the terminal-state edges — all fail closed with "
        "precise typed reasons",
    )


def case_10_open_world_no_technology_branching() -> Result:
    name = "case_10_open_world_no_technology_branching"

    # (a) the open-world composition: a technology id ABSENT from the
    # registry (UNKNOWN_BUT_WELL_FORMED — architecture section 8's own
    # example, harvested vocabulary) registers and drives through the
    # SAME seam identically.
    from adapters.validation import classify_access_technology_id

    classification = classify_access_technology_id(UNKNOWN_FUTURE_TECHNOLOGY_ID)
    if classification != "unknown_but_well_formed":
        return fail(
            name,
            "the open-world probe id classifies %r" % classification,
        )
    store, sid = ads._established_session()
    capability, _runtime, descriptor, requirements = _mount(
        store, technology_id=UNKNOWN_FUTURE_TECHNOLOGY_ID, label="futureimt-openworld-0"
    )
    if descriptor.access_technology_id != UNKNOWN_FUTURE_TECHNOLOGY_ID:
        return fail(name, "the unknown technology id was not preserved verbatim")
    view = capability.inspect_capabilities(now=_T_INSPECT)
    if not view.ok:
        return fail(name, "inspect_capabilities failed on the open-world id")
    if view.value.access_technology_id != UNKNOWN_FUTURE_TECHNOLOGY_ID:
        return fail(name, "the view did not preserve the unknown id verbatim")
    try:
        outcomes = _full_lifecycle(capability, sid, dict(requirements))
    except AssertionError as exc:
        return fail(name, "the open-world lifecycle failed: %s" % str(exc)[:160])
    if len(outcomes) != 8:
        return fail(name, "the open-world lifecycle drove %d operations" % len(outcomes))

    # (b) the accepted seam surface carries NO technology token (the
    # core imports nothing from the composition and branches on no
    # technology name — the structural probe).
    seam_files = (
        "adapters/__init__.py",
        "adapters/capability.py",
        "adapters/runtime.py",
        "adapters/sandbox.py",
        "adapters/contract.py",
        "adapters/model.py",
        "adapters/validation.py",
        "adapters/errors.py",
        "adapters/reference/__init__.py",
    )
    tokens = ("imt2030", "futureimt", "terahertz", "holographic")
    for rel in seam_files:
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        for token in tokens:
            if token in text.lower():
                return fail(
                    name,
                    "the accepted seam surface %s carries the technology token %r"
                    % (rel, token),
                )

    # (c) the registry is untouched: the reserved future path stays
    # RESERVED (registration is never activation — the open-world
    # classifier's design; the registry is read-only DATA here).
    registry = json.loads(
        (REPO_ROOT / "spec/schemas/registries/access-profile-registry.json")
        .read_text(encoding="utf-8")
    )
    entry = registry["entries"][REFERENCE_TECHNOLOGY_ID]
    if entry["status"] != "reserved":
        return fail(
            name,
            "the reserved future path was activated by the drill: %r" % entry["status"],
        )
    if UNKNOWN_FUTURE_TECHNOLOGY_ID in registry["entries"]:
        return fail(name, "the open-world probe id was somehow registered")
    return ok(
        name,
        "the UNKNOWN_BUT_WELL_FORMED id composed identically through the same "
        "seam (preserved verbatim; full lifecycle green); the accepted seam "
        "surface carries no technology token; the registry path stays "
        "reserved (registration is never activation)",
    )


def case_11_zero_contract_core_delta() -> Result:
    name = "case_11_zero_contract_core_delta"
    module_path = REPO_ROOT / "adapters" / "reference" / "futureimt.py"

    # (a) the AST import audit: the module imports NO contracts
    # surface AT ALL (and no other authority mutator — no store, no
    # journal, no ledger handle).
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])
            # relative imports (..contract etc.) carry no root; collect
            # their level-1 targets
            if node.level:
                imported_roots.add("." * node.level + (node.module or ""))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported_roots.add(alias.name.split(".")[0])
    forbidden = {
        "contracts", "offers", "capabilities", "executionplans",
        "eligibility", "policy", "imt", "sessions", "resources",
        "identity", "credentials", "resilience", "localfirst", "recovery",
        "accesstech",
    }
    leaked = imported_roots & forbidden
    if leaked:
        return fail(
            name,
            "the module imports authority surfaces: %s" % sorted(leaked),
        )

    # (b) the module's public surface is registration + operations
    # ONLY: the frozen closed ``__all__`` set (no contract-mutation
    # path, no store handles, no authority types), and nothing
    # re-exported beyond it.
    import adapters.reference.futureimt as module

    expected_surface = {
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
    }
    if set(module.__all__) != expected_surface:
        return fail(
            name,
            "the module __all__ drifted: unexpected %s; missing %s"
            % (
                sorted(set(module.__all__) - expected_surface),
                sorted(expected_surface - set(module.__all__)),
            ),
        )
    # every name visible beyond __all__ must be an IMPORTED
    # implementation dependency of the accepted adapter package (the
    # module's own composition imports — never an authority surface,
    # never a mutator).
    allowed_imports = {
        "AdapterContract", "AdapterDescriptor", "AdapterError",
        "AdapterReasonCode", "AdapterSecurityState", "ResourceMappingEntry",
        "derive_adapter_id", "Any", "Mapping", "Optional", "Sequence",
        "Tuple", "annotations",
    }
    visible = {
        name_ for name_ in dir(module) if not name_.startswith("_")
    } - expected_surface
    leaked = visible - allowed_imports
    if leaked:
        return fail(
            name,
            "the module exposes names beyond the declared surface and its "
            "composition imports: %s" % sorted(leaked),
        )
    # the engine's method surface is exactly the frozen nine-op
    # AdapterContract surface (plus the informational ``label``) —
    # no authority-reaching method beyond the contract.
    method_surface = {
        name_ for name_ in dir(ReferenceFutureImtEngine)
        if not name_.startswith("_")
    }
    if method_surface != {
        "open", "capabilities", "observe", "allocate", "release",
        "bind_session", "unbind_session", "health", "close", "label",
    }:
        return fail(
            name,
            "the engine exposes a non-contract public method surface: %s"
            % sorted(method_surface),
        )

    # (c) the git-guarded PR delta: zero contracts/ files touched; the
    # delta confined to the R9-CORE-001 authorization scope.  The
    # classification is the drift guard's own CONTROL surface (the
    # single source of truth, consumed BY REFERENCE through
    # ``authorization_provenance``'s import of ``architecture_drift_guard``)
    # and the scope coverage is the provenance gate's own ``covers``
    # (BY REFERENCE) — control-plane files are governance-classified,
    # never implementation scope violations.
    try:
        subprocess.run(
            ["git", "rev-parse", "--verify", "origin/main"],
            capture_output=True, cwd=str(REPO_ROOT), check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ok(
            name,
            "AST audit green (zero authority imports; the closed module "
            "surface); git delta check skipped (no origin/main ref; the CI "
            "provenance step enforces scope)",
        )
    delta: set = set()
    diff = subprocess.run(
        ["git", "diff", "--name-only", "origin/main"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    if diff.returncode == 0:
        delta |= {line for line in diff.stdout.splitlines() if line.strip()}
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    if untracked.returncode == 0:
        delta |= {line for line in untracked.stdout.splitlines() if line.strip()}
    if not delta:
        return ok(name, "AST audit green; no delta (clean main)")
    from architecture_drift_guard import is_control  # type: ignore

    try:
        from authorization_provenance import covers  # type: ignore
    except Exception:  # noqa: BLE001
        covers = None  # type: ignore
    problems: List[str] = []
    implementation_count = 0
    for path in sorted(delta):
        if is_control(path):
            continue  # governance-classified (the drift guard's own surface)
        if path.startswith("contracts/"):
            problems.append("the delivery delta touches the contract core: %s" % path)
            continue
        implementation_count += 1
        if covers is None or not covers(path):
            problems.append("delta outside the authorization scope: %s" % path)
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "AST audit green (zero authority imports in the new module); the "
        "closed registration+operations surface; the delta (%d control-plane-"
        "classified file(s) excluded) touches no contract-core file and stays "
        "inside the R9-CORE-001 scope" % implementation_count,
    )


# ===========================================================================
# (e) the one-way import audit + determinism + evidence honesty
# ===========================================================================


def case_12_one_way_import_and_purity_audit() -> Result:
    name = "case_12_one_way_import_and_purity_audit"

    # (a) NO accepted module imports the new composition (the one-way
    # boundary: the module is a leaf; only the delivery battery and the
    # module itself reference it).
    allowed_referencers = {
        "tools/futureimt_selftest.py",
        "adapters/reference/futureimt.py",
    }
    offenders: List[str] = []
    for path in sorted(REPO_ROOT.rglob("*.py")):
        rel = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        if rel in allowed_referencers:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.ImportFrom) and node.module:
                targets = [node.module]
            elif isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            for target in targets:
                if "futureimt" in target:
                    offenders.append("%s imports %s" % (rel, target))
    if offenders:
        return fail(name, "; ".join(offenders[:5]))

    # (b) the module never imports the legacy 1.0 imt/ domain (the
    # frozen migration matrix: harvest material is source material
    # only, never a forward dependency — the vocabulary was
    # re-expressed, not imported).
    module_source = (REPO_ROOT / "adapters" / "reference" / "futureimt.py").read_text(
        encoding="utf-8"
    )
    for token in ("from imt", "import imt", "from ..imt", "from ...imt"):
        if token in module_source:
            return fail(name, "the module imports the legacy imt/ domain (%r)" % token)

    # (c) the purity discipline (LOCK-119): no wall clock, no
    # randomness, no network anywhere in the drill — the AST import
    # audit on BOTH files (the battery's own subprocess/hashlib use is
    # the accepted battery convention: determinism-only), plus the
    # raw-source token audit on the delivered MODULE.
    forbidden_imports = (
        "random", "socket", "urllib", "requests", "time", "secrets",
        "datetime", "uuid",
    )
    for rel in ("adapters/reference/futureimt.py", "tools/futureimt_selftest.py"):
        source = (REPO_ROOT / rel).read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in forbidden_imports:
                        return fail(name, "%s imports %s" % (rel, alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] in forbidden_imports:
                    return fail(name, "%s imports from %s" % (rel, node.module))
    for token in (
        "datetime" + ".now", "time" + ".time", "utc" + "now",
        "random" + ".", "uuid" + "4",
    ):
        if token in module_source:
            return fail(
                name, "the module carries the impurity token %r" % token
            )
    return ok(
        name,
        "no accepted module imports the composition (one-way leaf); the "
        "module never imports the legacy imt/ domain (harvest = vocabulary "
        "only); no wall clock / randomness / network anywhere in the drill",
    )


def _drill_material() -> bytes:
    """The full drill's canonical material (deterministic): the
    composition lifecycle records, the offer/advertisement records, the
    translated plan, and the eligibility/policy decision records —
    every byte composed from fixed injected inputs."""
    store, sid = ads._established_session()
    capability, _runtime, _descriptor, requirements = _mount(store)
    outcomes = _full_lifecycle(capability, sid, dict(requirements))
    material = b"".join(
        result.value.to_canonical_bytes()
        for _operation, result in outcomes
        if hasattr(result.value, "to_canonical_bytes")
    )
    exchange, offer = _exchange()
    material += offer.canonical_bytes()
    material += exchange.advertisements()[0].canonical_bytes()
    contract = _mature_contract(offer)
    plan = translate_contract(
        contract,
        (
            SegmentInput(
                offer_reference=offer_reference(offer),
                role="primary",
                operations=ADAPTER_OPERATIONS,
                provenance=_prov("optimizer:futureimt-v1", "dec:m023-drill"),
            ),
        ),
        provenance=_prov("optimizer:futureimt-v1", "dec:m023-plan"),
    )
    material += plan.canonical_bytes() if hasattr(plan, "canonical_bytes") else b""
    resolved = exchange.resolve(offer_reference(offer), at_instant=_T_EVAL)
    offer_facts = (
        OfferReferenceEligibilityFacts(
            value=offer_reference(offer).value,
            offer_id=resolved.offer_id,
            provider=resolved.provider,
            jurisdictions=tuple(
                boundary.jurisdiction for boundary in resolved.service_boundaries
            ),
            usable=True,
        ),
    )
    ruleset = ContractEligibilityRuleset(
        ruleset_id="rs-m023-drill",
        version=1,
        issuer="ops:platform-eligibility",
        permitted_providers=(_PROVIDER,),
        permitted_jurisdictions=("GH",),
        valid_from=_T_VALID_FROM,
        valid_until=_T_VALID_END,
        decision_refs=("decision:platform-eligibility-m023",),
    )
    eligibility = evaluate_contract_reference_eligibility(
        ContractReferenceFacts(
            contract_id=contract.contract_id,
            state=contract.state,
            state_is_terminal=contract.state in TERMINAL_STATES,
            validity=ValidityWindow(
                not_before=contract.validity.not_before,
                not_after=contract.validity.not_after,
            ),
            offer_facts=offer_facts,
        ),
        ruleset,
        at_instant=_T_EVAL,
    )
    material += canonical_json_bytes(eligibility.to_dict())
    return material


def case_13_determinism_byte_identical() -> Result:
    name = "case_13_determinism_byte_identical"

    # (a) in-process rebuild: the whole drill re-composed from scratch
    # -> byte-identical canonical material.
    first = _drill_material()
    second = _drill_material()
    if first != second:
        return fail(
            name,
            "the drill material differs on in-process rebuild (%d vs %d bytes)"
            % (len(first), len(second)),
        )

    # (b) cross-process: the drill material composed in PYTHONHASHSEED
    # 0/1/42 subprocesses -> byte-identical digests.
    probe = (
        "import sys\n"
        "sys.path.insert(0, %r)\n"
        "sys.path.insert(0, %r)\n"
        "import hashlib\n"
        "import futureimt_selftest as m023\n"
        "print(hashlib.sha256(m023._drill_material()).hexdigest())\n"
    ) % (str(REPO_ROOT), str(REPO_ROOT / "tools"))
    outputs: set = set()
    for seed in ("0", "1", "42"):
        env = {"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"}
        run = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True, text=True, env=env, cwd=str(REPO_ROOT),
        )
        if run.returncode != 0:
            return fail(
                name,
                "seed %s subprocess failed: %s" % (seed, run.stderr[-200:]),
            )
        outputs.add(run.stdout.strip())
    if len(outputs) != 1:
        return fail(
            name,
            "the drill material differs across PYTHONHASHSEED subprocesses "
            "(%d distinct digests)" % len(outputs),
        )
    digest = hashlib.sha256(first).hexdigest()
    if outputs.pop() != digest:
        return fail(name, "the cross-process digest differs from the in-process digest")
    return ok(
        name,
        "in-process rebuild byte-identical; the full drill material "
        "byte-identical across PYTHONHASHSEED 0/1/42 (digest %s...)"
        % digest[:12],
    )


def case_14_evidence_doc_honest() -> Result:
    name = "case_14_evidence_doc_honest"
    path = REPO_ROOT / "docs" / "M023-evidence.md"
    if not path.exists():
        return fail(name, "docs/M023-evidence.md is missing")
    text = path.read_text(encoding="utf-8")
    problems: List[str] = []
    if "SOFTWARE" not in text:
        problems.append("the evidence class is not disclosed")
    if "M023" not in text:
        problems.append("the evidence does not name M023")
    for lock in (
        "LOCK-101", "LOCK-105", "LOCK-109", "LOCK-110",
        "LOCK-112", "LOCK-117", "LOCK-118", "LOCK-119",
    ):
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
            window = normalized[max(0, index - 90):index]
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
    results: List[Result] = []
    results.append(case_01_registration_through_accepted_seam())
    results.append(case_02_declared_capability_surface())
    results.append(case_03_nine_operations_typed_records())
    results.append(case_04_rebind_translation_mid_session())
    results.append(case_05_offer_exchange_composition())
    results.append(case_06_executionplan_bridge_lock109())
    results.append(case_07_eligibility_policy_admission())
    results.append(case_08_lock110_provider_neutral_records())
    results.append(case_09_typed_errors_fail_closed())
    results.append(case_10_open_world_no_technology_branching())
    results.append(case_11_zero_contract_core_delta())
    results.append(case_12_one_way_import_and_purity_audit())
    results.append(case_13_determinism_byte_identical())
    results.append(case_14_evidence_doc_honest())

    print("ADCOS future-IMT extension drill self-test (M023)")
    print("=" * 72)
    for name_, ok_flag, detail in results:
        print("[%s] %-52s %s" % ("ok  " if ok_flag else "FAIL", name_, detail))
    print("-" * 72)
    passed = sum(1 for _, ok_flag, _ in results if ok_flag)
    if passed == len(results):
        print("Result: PASS (%d/%d cases)" % (passed, len(results)))
        return 0
    print("Result: FAIL (%d/%d cases passed)" % (passed, len(results)))
    return 1


if __name__ == "__main__":
    sys.exit(main())
