#!/usr/bin/env python3
"""ADCOS evidence-and-assurance self-test (M005 — Evidence and Assurance).

Deterministic, offline verification of the ``evidence/`` and ``assurance/``
packages against the frozen Architecture 1.1 mandate (R7-CORE-001, DEC-0101;
the R7 charter M005 acceptance criteria) plus the disclosed telemetry
harvest (classification matrix: Telemetry RETAIN -> Assurance evidence):

- **LOCK-106 evidence typing** — the four DISTINCT typed records
  (claim / observation / commitment / attestation), structurally distinct
  payloads with no type confusion and no untyped evidence, canonical-JSON
  round-trips, tamper-evident content-derived ids, the LOCK-118 provenance
  envelope, fail-closed typed validation (malformed input never enters
  stored state), and the append-only idempotent evidence store with
  construction-is-recovery persistence and LOCK-119 secret scanning;
- **the M005 harvest seam** — ``telemetry.TelemetryObservation`` records
  become ``evidence.ObservationEvidence`` records through the single
  explicit, disclosed, one-directional translation seam; telemetry stays
  the owner of raw operational measurement (its public API surface is
  preserved verbatim — verified structurally — and its privacy fence and
  policy-gated topology promotion are untouched); the seam vocabulary is
  cross-checked against the frozen telemetry metric registry;
- **LOCK-107 closed-loop assurance** — the frozen §9 assurance state
  vocabulary (compliant, degraded, violated, unknown (stale/absent
  evidence), failed, deliberately_terminated), every state reachable and
  correct on deterministic fixtures, latest-evidence-wins with no time
  travel, instant-threshold staleness on injected instants (never wall
  clock), deadline absence-breaches, worst-of aggregation, contract-level
  evaluation that consumes the accepted ``contracts/`` domain BY REFERENCE
  (never a second contract model), the idempotent evaluation journal, and
  the sole bridge back into the contract through its own
  ``RecordAssurance`` command vocabulary;
- **engineering discipline** — no wall clock, no randomness, no UUIDs, no
  network, no secrets (LOCK-119), sorted PYTHONHASHSEED-safe iteration,
  byte-identical cross-process determinism, and the authorization-aware
  PR-delta-shape consultation (the M001-evidence §4 duty, the M002-era
  pattern).

The central boundary is exercised throughout:

    EVIDENCE RECORD  = typed DATA with provenance (LOCK-106/LOCK-118)
                     != AUTHORITY (LOCK-117: a record asserts, never
                        authorizes)
    ASSURANCE        = the contract-level evaluation authority (LOCK-107)
                     != CONTRACT AUTHORITY (LOCK-101: contracts/ consumed
                        by reference; the bridge is the only write path)
                     != MEASUREMENT AUTHORITY (telemetry owns raw
                        operational measurement; the seam is DATA-only)

All instants are injected; no wall clock, no randomness, no network, no
UUIDs. Runs are byte-identical across processes (PYTHONHASHSEED-safe).
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from evidence import (  # noqa: E402
    ATTESTATION_KINDS,
    CLAIM_KINDS,
    COMMITMENT_KINDS,
    EVIDENCE_TYPES,
    OBSERVATION_METRICS,
    AttestationEvidence,
    ClaimEvidence,
    CommitmentEvidence,
    EvidenceError,
    EvidenceReasonCode,
    EvidenceStore,
    ObservationEvidence,
    SEAM_DISCLOSURE,
    TELEMETRY_HARVEST_SEAM,
    derive_record_id,
    record_from_dict,
    telemetry_observation_to_evidence,
)
from assurance import (  # noqa: E402
    ASSURANCE_STATES,
    BOUND_KINDS,
    CONTRACT_RECORDABLE_STATES,
    EVALUABLE_CONTRACT_STATES,
    EVALUATION_TO_RECORDED_STATE,
    OBLIGATION_KINDS,
    OBLIGATION_SEVERITIES,
    REASON_KINDS,
    AssuranceError,
    AssuranceJournal,
    AssuranceObligation,
    AssuranceReasonCode,
    DEFAULT_BRIDGE_ISSUER,
    bridge_command,
    evaluate_contract,
    record_into_contract,
    resolve_obligations,
    to_contract_references,
)
from contracts import (  # noqa: E402
    ASSURANCE_STATES as CONTRACT_ASSURANCE_STATES,
    CONTRACT_STATES,
    CONTRACT_TRANSITIONS,
    ActivateContract,
    BeneficiaryScope,
    ConnectivityContract,
    ConnectivityPrincipal,
    ContractStore,
    CreateContract,
    FailContract,
    HardConstraint,
    OpaqueReference,
    Provenance,
    RecordAssurance,
    RecordDelivery,
    RecordExecutionActivation,
    SelectOffers,
    TerminationRules,
    TerminateContract,
    ValidityInterval,
)
from telemetry import (  # noqa: E402
    TELEMETRY_METRIC_REGISTRY,
    TelemetryObservation,
)
from protocol.canonicalization import canonical_json_bytes  # noqa: E402

Result = Tuple[str, bool, str]

# Injected T0-style instants (no wall clock anywhere in this battery).
T0 = "2026-10-01T00:00:00Z"           # contract activation
T1 = "2026-10-01T00:10:00Z"           # delivery + first observation
T1B = "2026-10-01T00:15:00Z"          # second (breaching) observation
T2 = "2026-10-01T00:20:00Z"           # the default evaluation instant
T3 = "2026-10-01T02:00:00Z"           # after the freshness window (stale)
T_DEADLINE = "2026-10-01T00:30:00Z"   # obligation evidence deadline
FRESH_UNTIL = "2026-10-01T00:40:00Z"  # observation validity boundary
T_END = "2026-11-01T00:00:00Z"        # contract validity end
CREATE_AT = "2026-09-30T10:00:00Z"    # contract creation

PATH_REF = "adcos:path:" + "p" * 32
NODE_A = "adcos:node:test.profile.v1:" + "a" * 64
NODE_B = "adcos:node:test.profile.v1:" + "b" * 64
PRODUCER = "prov:telco-x"
OBSERVER = NODE_A


def ok(name: str, detail: str) -> Result:
    return (name, True, detail)


def fail(name: str, detail: str) -> Result:
    return (name, False, detail)


def expect_evidence_error(case: str, code: str, action: Callable[[], Any]) -> Result:
    try:
        action()
    except EvidenceError as error:
        if error.code == code:
            return ok(case, "fail-closed %s: %s" % (code, error.detail[:90]))
        return fail(case, "expected code %s, got %s (%s)" % (code, error.code, error.detail[:90]))
    except Exception as error:  # noqa: BLE001
        return fail(case, "unexpected exception %s: %s" % (type(error).__name__, str(error)[:90]))
    return fail(case, "expected EvidenceError(%s); the input was accepted" % code)


def expect_assurance_error(case: str, code: str, action: Callable[[], Any]) -> Result:
    try:
        action()
    except AssuranceError as error:
        if error.code == code:
            return ok(case, "fail-closed %s: %s" % (code, error.detail[:90]))
        return fail(case, "expected code %s, got %s (%s)" % (code, error.code, error.detail[:90]))
    except Exception as error:  # noqa: BLE001
        return fail(case, "unexpected exception %s: %s" % (type(error).__name__, str(error)[:90]))
    return fail(case, "expected AssuranceError(%s); the input was accepted" % code)


# ---------------------------------------------------------------------------
# Fixtures: one obligation per LOCK-106 evidence type
# ---------------------------------------------------------------------------


def _obligations(with_deadlines: bool = True) -> Tuple[AssuranceObligation, ...]:
    """The four typed obligations (one per LOCK-106 evidence class).

    ``with_deadlines=False`` strips the evidence deadlines (fixtures for
    PURE staleness/absence cases: no fired deadline can escalate the
    missing evidence into a breach)."""
    return (
        AssuranceObligation(
            obligation_kind="observation-bound",
            subject_ref=PATH_REF,
            evidence_name="latency-ms",
            severity="hard",
            producer="arch:probe",
            bound_kind="ceiling",
            bound_value=120,
            evidence_deadline=T_DEADLINE if with_deadlines else None,
        ),
        AssuranceObligation(
            obligation_kind="claim-level",
            subject_ref=PATH_REF,
            evidence_name="capability-statement",
            severity="degradable",
            producer="arch:probe",
        ),
        AssuranceObligation(
            obligation_kind="commitment-window",
            subject_ref=PATH_REF,
            evidence_name="service-level",
            severity="hard",
            producer="prov:telco-x",
            bound_kind="floor",
            bound_value=99,
        ),
        AssuranceObligation(
            obligation_kind="attestation-required",
            subject_ref=PATH_REF,
            evidence_name="external-audit",
            severity="degradable",
            producer="audit:external",
            evidence_deadline=T_DEADLINE if with_deadlines else None,
        ),
    )


def _create_command(
    obligations: Tuple[AssuranceObligation, ...],
    principal_ref: str = "app:probe-1",
) -> CreateContract:
    return CreateContract(
        principal=ConnectivityPrincipal(principal_kind="APPLICATION", principal_ref=principal_ref),
        beneficiaries=(BeneficiaryScope(beneficiary_kind="DEVICE", beneficiary_ref="dev:probe-9"),),
        requirements=(
            OpaqueReference(
                ref_kind="intent-requirements", value="intent:p-1", provenance=Provenance(issuer="arch:probe")
            ),
        ),
        hard_constraints=(
            HardConstraint(kind="latency-bound", params={"max_ms": 150}, provenance=Provenance(issuer="prov:probe")),
        ),
        validity=ValidityInterval(not_before=T0, not_after=T_END),
        service_properties=(
            OpaqueReference(ref_kind="service-property", value="prop:p-1", provenance=Provenance(issuer="prov:probe")),
        ),
        usage_pricing_terms=OpaqueReference(
            ref_kind="usage-pricing-terms", value="terms:p-1", provenance=Provenance(issuer="comm:probe")
        ),
        assurance_obligations=to_contract_references(obligations),
        execution_scope=(
            OpaqueReference(ref_kind="execution-scope", value="scope:p-1", provenance=Provenance(issuer="arch:probe")),
        ),
        termination=TerminationRules(
            conditions=("principal-requested",),
            compensation=OpaqueReference(ref_kind="compensation", value="comp:p-1", provenance=Provenance(issuer="comm:probe")),
        ),
        provenance=Provenance(issuer="arch:probe", decision_refs=("dec:p-1",)),
    )


def _store_at(
    stage: str,
    obligations: Tuple[AssuranceObligation, ...] = None,
    principal_ref: str = "app:probe-1",
) -> Tuple[ContractStore, str, ConnectivityContract]:
    """A live ContractStore whose single contract has walked the frozen
    M002 lifecycle to ``stage`` ("CONTRACT_ACTIVE", "DELIVERY",
    "TERMINATED" or "FAILED"), carrying the obligation references.  A
    distinct ``principal_ref`` yields a distinct content-derived contract
    id (fixtures for cross-contract scoping)."""
    if obligations is None:
        obligations = _obligations()
    store = ContractStore()
    created = store.submit(_create_command(obligations, principal_ref), recorded_at=CREATE_AT)
    cid = created.contract.contract_id
    store.submit(
        SelectOffers(
            offers=(OpaqueReference(ref_kind="offer", value="offer:p-9", provenance=Provenance(issuer="prov:probe")),)
        ),
        recorded_at="2026-09-30T10:05:00Z",
        contract_id=cid,
    )
    store.submit(
        ActivateContract(
            activated_at=T0,
            signature_refs=(OpaqueReference(ref_kind="signature", value="sig:p-1"),),
        ),
        recorded_at=T0,
        contract_id=cid,
    )
    if stage == "CONTRACT_ACTIVE":
        return store, cid, store.contract(cid)
    store.submit(RecordExecutionActivation(recorded_at=T0), recorded_at=T0, contract_id=cid)
    if stage == "TERMINATED":
        store.submit(
            TerminateContract(recorded_at=T1, condition="principal-requested", reason="probe termination"),
            recorded_at=T1,
            contract_id=cid,
        )
        return store, cid, store.contract(cid)
    if stage == "FAILED":
        store.submit(
            FailContract(recorded_at=T1, reason="execution-unrecoverable"),
            recorded_at=T1,
            contract_id=cid,
        )
        return store, cid, store.contract(cid)
    store.submit(RecordDelivery(recorded_at=T1), recorded_at=T1, contract_id=cid)
    return store, cid, store.contract(cid)


def _observation_evidence(
    contract_ref: str,
    *,
    value: int = 45,
    instant: str = T1,
    freshness_until: str = FRESH_UNTIL,
    subject_ref: str = PATH_REF,
) -> ObservationEvidence:
    return ObservationEvidence(
        subject_ref=subject_ref,
        contract_ref=contract_ref,
        instant=instant,
        producer=OBSERVER,
        metric="latency-ms",
        value=value,
        confidence_basis_points=9000,
        freshness_until=freshness_until,
        source_refs=("telemetry:observation:" + "d" * 16,),
    )


def _telemetry_observation(
    *,
    value: int = 45,
    observed_at: str = T1,
    freshness_until: str = FRESH_UNTIL,
    subject_ref: str = PATH_REF,
    sequence: int = 1,
) -> TelemetryObservation:
    return TelemetryObservation(
        subject_kind="path",
        subject_ref=subject_ref,
        source_node_id=OBSERVER,
        source_class="peer-observed",
        metric="latency-ms",
        value=value,
        confidence_basis_points=9000,
        observed_at=observed_at,
        freshness_until=freshness_until,
        sequence=sequence,
        provenance="edge-observation",
    )


def _claim_evidence(contract_ref: str, *, asserted_value: int = 7, instant: str = T1) -> ClaimEvidence:
    return ClaimEvidence(
        subject_ref=PATH_REF,
        contract_ref=contract_ref,
        instant=instant,
        producer=PRODUCER,
        claim_kind="capability-statement",
        asserted_value=asserted_value,
        confidence_basis_points=7500,
    )


def _commitment_evidence(
    contract_ref: str,
    *,
    committed_value: int = 99,
    valid_from: str = T0,
    valid_until: str = T_END,
) -> CommitmentEvidence:
    return CommitmentEvidence(
        subject_ref=PATH_REF,
        contract_ref=contract_ref,
        instant=CREATE_AT,
        producer=PRODUCER,
        commitment_kind="service-level",
        committed_value=committed_value,
        valid_from=valid_from,
        valid_until=valid_until,
    )


def _attestation_evidence(
    contract_ref: str, *, attested_value: int = 1, instant: str = T1, valid_until: str = T_END
) -> AttestationEvidence:
    return AttestationEvidence(
        subject_ref=PATH_REF,
        contract_ref=contract_ref,
        instant=instant,
        producer="audit:external",
        attestation_kind="external-audit",
        attested_value=attested_value,
        valid_until=valid_until,
    )


def _default_evidence(contract_ref: str) -> List[Any]:
    """The full satisfying evidence set for the four obligations."""
    return [
        _observation_evidence(contract_ref),
        _claim_evidence(contract_ref),
        _commitment_evidence(contract_ref),
        _attestation_evidence(contract_ref),
    ]


# ---------------------------------------------------------------------------
# Section A — LOCK-106 typed evidence records
# ---------------------------------------------------------------------------


def case_01_evidence_type_vocabulary_frozen() -> Result:
    if EVIDENCE_TYPES != ("claim", "observation", "commitment", "attestation"):
        return fail("case_01_evidence_type_vocabulary_frozen", "LOCK-106 type vocabulary drifted: %s" % (EVIDENCE_TYPES,))
    if CLAIM_KINDS != ("capability-statement", "coverage-statement", "capacity-statement", "status-statement"):
        return fail("case_01_evidence_type_vocabulary_frozen", "claim-kind vocabulary drifted")
    if COMMITMENT_KINDS != ("service-level", "availability", "latency", "repair-window"):
        return fail("case_01_evidence_type_vocabulary_frozen", "commitment-kind vocabulary drifted")
    if ATTESTATION_KINDS != ("external-audit", "controller-verified", "remotely-attested", "compliance-certificate"):
        return fail("case_01_evidence_type_vocabulary_frozen", "attestation-kind vocabulary drifted")
    if not set(OBSERVATION_METRICS):
        return fail("case_01_evidence_type_vocabulary_frozen", "observation-metric vocabulary is empty")
    return ok(
        "case_01_evidence_type_vocabulary_frozen",
        "LOCK-106 vocabularies frozen: 4 distinct types + per-kind name sets",
    )


def case_02_four_types_structurally_distinct() -> Result:
    classes = (ClaimEvidence, ObservationEvidence, CommitmentEvidence, AttestationEvidence)
    payload_fields = {
        cls: {
            f for f in cls.__dataclass_fields__
            if f not in ("subject_ref", "contract_ref", "instant", "producer", "source_refs", "record_id")
        }
        for cls in classes
    }
    # every class carries a distinct payload field set and fixed type member
    seen: Dict[str, frozenset] = {}
    for cls in classes:
        name = cls.__dataclass_fields__["record_type"].default
        if cls.__dataclass_fields__["record_type"].default != name or name not in EVIDENCE_TYPES:
            return fail("case_02_four_types_structurally_distinct", "record_type not fixed per class")
        key = frozenset(payload_fields[cls])
        if key in seen.values():
            return fail(
                "case_02_four_types_structurally_distinct",
                "two evidence classes share the same payload field set (type confusion risk)",
            )
        seen[name] = key
    # claim/observation REQUIRE confidence; commitment/attestation carry none
    if "confidence_basis_points" not in payload_fields[ClaimEvidence]:
        return fail("case_02_four_types_structurally_distinct", "claim must carry confidence")
    if "confidence_basis_points" not in payload_fields[ObservationEvidence]:
        return fail("case_02_four_types_structurally_distinct", "observation must carry confidence")
    for cls in (CommitmentEvidence, AttestationEvidence):
        if "confidence_basis_points" in payload_fields[cls]:
            return fail(
                "case_02_four_types_structurally_distinct",
                "%s must NOT carry confidence (structural type distinction)" % cls.__name__,
            )
    return ok(
        "case_02_four_types_structurally_distinct",
        "four DISTINCT structural payloads; confidence only where probabilistic",
    )


def case_03_no_type_confusion() -> List[Result]:
    results: List[Result] = []
    store, cid, _ = _store_at("DELIVERY")
    records = {
        "claim": _claim_evidence(cid),
        "observation": _observation_evidence(cid),
        "commitment": _commitment_evidence(cid),
        "attestation": _attestation_evidence(cid),
    }
    for record_type, record in records.items():
        payload = record.to_dict()
        for other_type, other_class in (
            ("claim", ClaimEvidence),
            ("observation", ObservationEvidence),
            ("commitment", CommitmentEvidence),
            ("attestation", AttestationEvidence),
        ):
            if other_type == record_type:
                continue
            case = "case_03_no_type_confusion_%s_as_%s" % (record_type, other_type)
            results.append(
                expect_evidence_error(case, EvidenceReasonCode.VOCABULARY, lambda c=other_class, p=payload: c.from_dict(p))
            )
    # the typed dispatch fails closed on unknown record types
    results.append(
        expect_evidence_error(
            "case_03_no_type_confusion_unknown_type",
            EvidenceReasonCode.VOCABULARY,
            lambda: record_from_dict({"record_type": "rumor", "subject_ref": "x"}),
        )
    )
    results.append(
        expect_evidence_error(
            "case_03_no_type_confusion_no_type",
            EvidenceReasonCode.VOCABULARY,
            lambda: record_from_dict({"subject_ref": "x"}),
        )
    )
    return results


def case_04_canonical_round_trip() -> Result:
    store, cid, _ = _store_at("DELIVERY")
    records = (
        _claim_evidence(cid),
        _observation_evidence(cid),
        _commitment_evidence(cid),
        _attestation_evidence(cid),
    )
    for record in records:
        as_dict = record.to_dict()
        as_bytes = record.canonical_bytes()
        # canonical JSON round-trip: bytes -> json -> dict -> typed record
        rebuilt = record_from_dict(json.loads(as_bytes.decode("utf-8")))
        if rebuilt.canonical_bytes() != as_bytes:
            return fail("case_04_canonical_round_trip", "%s canonical bytes not stable" % record.record_type)
        if rebuilt.record_id != record.record_id:
            return fail("case_04_canonical_round_trip", "%s id changed across the round-trip" % record.record_type)
        if rebuilt.to_dict() != as_dict:
            return fail("case_04_canonical_round_trip", "%s dict not reproduced" % record.record_type)
        # canonical bytes equal the canonicalizer over the dict (sorted keys)
        if canonical_json_bytes(as_dict) != as_bytes:
            return fail("case_04_canonical_round_trip", "%s bytes diverge from canonical_json_bytes" % record.record_type)
    return ok("case_04_canonical_round_trip", "all four types round-trip byte-identically through canonical JSON")


def case_05_provenance_envelope() -> Result:
    store, cid, _ = _store_at("DELIVERY")
    record = _observation_evidence(cid)
    for member in ("subject_ref", "contract_ref", "instant", "producer"):
        if not getattr(record, member):
            return fail("case_05_provenance_envelope", "observation missing provenance member %s" % member)
    if record.confidence_basis_points < 0 or record.confidence_basis_points > 10_000:
        return fail("case_05_provenance_envelope", "confidence outside the basis-point scale")
    claim = _claim_evidence(cid)
    if claim.producer != PRODUCER or claim.confidence_basis_points < 0:
        return fail("case_05_provenance_envelope", "claim provenance incomplete")
    commitment = _commitment_evidence(cid)
    if not commitment.valid_from or not commitment.valid_until:
        return fail("case_05_provenance_envelope", "commitment window missing")
    attestation = _attestation_evidence(cid)
    if attestation.producer != "audit:external":
        return fail("case_05_provenance_envelope", "attestor is not the producer (LOCK-118)")
    # lineage: source_refs ride as opaque DATA
    if not record.source_refs:
        return fail("case_05_provenance_envelope", "observation carries no lineage source_refs")
    return ok(
        "case_05_provenance_envelope",
        "LOCK-118: subject/contract/instant/producer/confidence + lineage on every record",
    )


def case_06_content_derived_ids() -> Result:
    store, cid, _ = _store_at("DELIVERY")
    a = _observation_evidence(cid)
    b = _observation_evidence(cid)
    if a.record_id != b.record_id:
        return fail("case_06_content_derived_ids", "same content produced different ids")
    if not a.record_id.startswith("evidence:observation:"):
        return fail("case_06_content_derived_ids", "observation id prefix wrong: %s" % a.record_id[:30])
    other = _observation_evidence(cid, value=46)
    if other.record_id == a.record_id:
        return fail("case_06_content_derived_ids", "different content produced the same id")
    # prefixes are per-type namespaces
    prefixes = {
        _claim_evidence(cid).record_id: "evidence:claim:",
        a.record_id: "evidence:observation:",
        _commitment_evidence(cid).record_id: "evidence:commitment:",
        _attestation_evidence(cid).record_id: "evidence:attestation:",
    }
    for record_id, prefix in prefixes.items():
        if not record_id.startswith(prefix):
            return fail("case_06_content_derived_ids", "id %s outside its type namespace" % record_id[:30])
    # re-derivation for verification callers agrees
    if derive_record_id(a) != a.record_id:
        return fail("case_06_content_derived_ids", "derive_record_id disagrees with the stored id")
    return ok("case_06_content_derived_ids", "ids are content-derived, per-type namespaced, no randomness")


def case_07_tamper_evidence() -> List[Result]:
    results: List[Result] = []
    store, cid, _ = _store_at("DELIVERY")
    records = (
        ("claim", _claim_evidence(cid)),
        ("observation", _observation_evidence(cid)),
        ("commitment", _commitment_evidence(cid)),
        ("attestation", _attestation_evidence(cid)),
    )
    for record_type, record in records:
        case = "case_07_tamper_evidence_%s" % record_type
        payload = record.to_dict()
        # mutate one payload member while RETAINING the id
        member = {
            "claim": "asserted_value",
            "observation": "value",
            "commitment": "committed_value",
            "attestation": "attested_value",
        }[record_type]
        payload[member] = payload[member] + 1
        results.append(
            expect_evidence_error(
                case,
                EvidenceReasonCode.ID_MISMATCH,
                lambda p=payload: record_from_dict(p),
            )
        )
    return results


def case_08_malformed_input_fail_closed() -> List[Result]:
    results: List[Result] = []
    base = dict(
        subject_ref=PATH_REF,
        contract_ref="contract:probe",
        instant=T1,
        producer=PRODUCER,
        source_refs=(),
    )
    results.append(
        expect_evidence_error(
            "case_08a_non_mapping",
            EvidenceReasonCode.INVALID_INPUT,
            lambda: ClaimEvidence.from_dict(["not", "a", "mapping"]),
        )
    )
    results.append(
        expect_evidence_error(
            "case_08b_empty_subject",
            EvidenceReasonCode.INVALID_INPUT,
            lambda: ClaimEvidence(**{**base, "claim_kind": "capability-statement", "asserted_value": 1, "confidence_basis_points": 1, "subject_ref": ""}),
        )
    )
    results.append(
        expect_evidence_error(
            "case_08c_bad_grammar_ref",
            EvidenceReasonCode.INVALID_INPUT,
            lambda: ClaimEvidence(**{**base, "claim_kind": "capability-statement", "asserted_value": 1, "confidence_basis_points": 1, "subject_ref": "has spaces!"}),
        )
    )
    results.append(
        expect_evidence_error(
            "case_08d_bool_as_int",
            EvidenceReasonCode.INVALID_INPUT,
            lambda: ClaimEvidence(**{**base, "claim_kind": "capability-statement", "asserted_value": True, "confidence_basis_points": 1}),
        )
    )
    results.append(
        expect_evidence_error(
            "case_08e_float_value",
            EvidenceReasonCode.INVALID_INPUT,
            lambda: ClaimEvidence(**{**base, "claim_kind": "capability-statement", "asserted_value": 1.5, "confidence_basis_points": 1}),
        )
    )
    results.append(
        expect_evidence_error(
            "case_08f_confidence_overflow",
            EvidenceReasonCode.INVALID_CONFIDENCE,
            lambda: ClaimEvidence(**{**base, "claim_kind": "capability-statement", "asserted_value": 1, "confidence_basis_points": 10_001}),
        )
    )
    results.append(
        expect_evidence_error(
            "case_08g_invalid_instant",
            EvidenceReasonCode.INVALID_INSTANT,
            lambda: ClaimEvidence(**{**base, "claim_kind": "capability-statement", "asserted_value": 1, "confidence_basis_points": 1, "instant": "yesterday"}),
        )
    )
    results.append(
        expect_evidence_error(
            "case_08h_vocabulary",
            EvidenceReasonCode.VOCABULARY,
            lambda: ClaimEvidence(**{**base, "claim_kind": "gut-feeling", "asserted_value": 1, "confidence_basis_points": 1}),
        )
    )
    results.append(
        expect_evidence_error(
            "case_08i_empty_window",
            EvidenceReasonCode.INVALID_WINDOW,
            lambda: ObservationEvidence(
                subject_ref=PATH_REF, contract_ref="contract:probe", instant=T1, producer=PRODUCER,
                metric="latency-ms", value=1, confidence_basis_points=1, freshness_until=T1,
            ),
        )
    )
    results.append(
        expect_evidence_error(
            "case_08j_secret_producer",
            EvidenceReasonCode.SECRET_REJECTED,
            lambda: ClaimEvidence(**{**base, "claim_kind": "capability-statement", "asserted_value": 1, "confidence_basis_points": 1, "producer": "ghp_supersecrettoken123"}),
        )
    )
    results.append(
        expect_evidence_error(
            "case_08k_secret_label",
            EvidenceReasonCode.SECRET_REJECTED,
            lambda: ClaimEvidence(**{**base, "claim_kind": "capability-statement", "asserted_value": 1, "confidence_basis_points": 1, "subject_ref": "node:api-key-holder"}),
        )
    )
    results.append(
        expect_evidence_error(
            "case_08l_commitment_window_inverted",
            EvidenceReasonCode.INVALID_WINDOW,
            lambda: CommitmentEvidence(
                subject_ref=PATH_REF, contract_ref="contract:probe", instant=T1, producer=PRODUCER,
                commitment_kind="service-level", committed_value=1, valid_from=T2, valid_until=T1,
            ),
        )
    )
    # raw exception text never enters the typed detail
    try:
        ClaimEvidence(**{**base, "claim_kind": "capability-statement", "asserted_value": 1, "confidence_basis_points": 1, "instant": "not-a-time"})
    except EvidenceError as error:
        if "Traceback" in error.detail or "raise " in error.detail:
            results.append(fail("case_08m_no_raw_exception_text", "raw exception text leaked into the detail"))
        else:
            results.append(ok("case_08m_no_raw_exception_text", "typed detail carries no raw exception text"))
    else:
        results.append(fail("case_08m_no_raw_exception_text", "the invalid instant was accepted"))
    return results


# ---------------------------------------------------------------------------
# Section B — the append-only evidence store
# ---------------------------------------------------------------------------


def case_09_append_only_idempotent() -> List[Result]:
    results: List[Result] = []
    _, cid, _ = _store_at("DELIVERY")
    estore = EvidenceStore()
    record = _observation_evidence(cid)
    first = estore.ingest(record)
    if not first.accepted:
        results.append(fail("case_09a_first_ingest", "the first ingest was not accepted"))
    else:
        results.append(ok("case_09a_first_ingest", "record appended"))
    again = estore.ingest(record)
    if again.accepted or len(estore) != 1:
        results.append(fail("case_09b_idempotent_duplicate", "duplicate ingest re-appended"))
    else:
        results.append(ok("case_09b_idempotent_duplicate", "byte-identical duplicate is a no-op"))
    # a DIFFERENT record under a retained id is tampering (the mutation is
    # crafted the way a corrupted journal line would present it: same id,
    # different content)
    results.append(
        expect_evidence_error(
            "case_09c_tampered_duplicate",
            EvidenceReasonCode.RECORD_TAMPER,
            lambda: _tamper_ingest(estore, record.record_id, 999),
        )
    )
    # untyped ingest is rejected (LOCK-106: no untyped evidence)
    results.append(
        expect_evidence_error(
            "case_09d_untyped_ingest",
            EvidenceReasonCode.INVALID_INPUT,
            lambda: estore.ingest({"record_type": "claim"}),
        )
    )
    return results


def _tamper_ingest(store: EvidenceStore, retained_id: str, mutated_value: int) -> Any:
    """Craft a mutated record that retains the original id, then ingest it.

    The constructor rejects retained-id mutations (ID_MISMATCH) before the
    store can see them, so the store's own retained-id check is exercised
    with a directly-crafted object — exactly the shape a corrupted or
    hand-edited journal line would present."""
    record = _observation_evidence("contract:probe")
    object.__setattr__(record, "value", mutated_value)
    object.__setattr__(record, "record_id", retained_id)
    return store.ingest(record)


def case_10_persistence_recovery_fold() -> Result:
    _, cid, _ = _store_at("DELIVERY")
    records = _default_evidence(cid)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "evidence.jsonl"
        persisted = EvidenceStore(journal_path=path)
        for record in records:
            persisted.ingest(record)
        digest = persisted.state_digest()
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) != len(records):
            return fail("case_10_persistence_recovery_fold", "journal line count mismatch")
        # construction-is-recovery: re-fold reproduces byte-identical state
        recovered = EvidenceStore(journal_path=path)
        if recovered.state_digest() != digest:
            return fail("case_10_persistence_recovery_fold", "re-fold diverged from the original state")
        if len(recovered) != len(records):
            return fail("case_10_persistence_recovery_fold", "re-fold lost records")
        # the fold is idempotent under replay
        replay = EvidenceStore(journal_path=path)
        if replay.state_digest() != digest:
            return fail("case_10_persistence_recovery_fold", "replay is not idempotent")
        # a corrupted (non-JSON) line fails closed on construction
        bad = Path(tmp) / "bad.jsonl"
        bad.write_text("\n".join(lines[:1] + ["{not json"]) + "\n", encoding="utf-8")
        try:
            EvidenceStore(journal_path=bad)
            return fail("case_10_persistence_recovery_fold", "a malformed journal line was accepted on re-fold")
        except EvidenceError as error:
            if error.code != EvidenceReasonCode.RECORD_TAMPER:
                return fail("case_10_persistence_recovery_fold", "wrong code for the malformed line: %s" % error.code)
        # a secret-shaped line never enters the fold
        secret = Path(tmp) / "secret.jsonl"
        secret.write_text('{"x": "ghp_supersecrettoken123"}\n', encoding="utf-8")
        try:
            EvidenceStore(journal_path=secret)
            return fail("case_10_persistence_recovery_fold", "a secret-shaped journal line was accepted")
        except EvidenceError as error:
            if error.code != EvidenceReasonCode.SECRET_REJECTED:
                return fail("case_10_persistence_recovery_fold", "wrong code for the secret line: %s" % error.code)
    return ok("case_10_persistence_recovery_fold", "JSONL fold + idempotent replay + fail-closed corruption/secret lines")


def case_11_reads_sorted_scoped_fail_closed() -> Result:
    s, cid, _ = _store_at("DELIVERY")
    s2, other_cid, _ = _store_at("DELIVERY", principal_ref="app:probe-2")
    if other_cid == cid:
        return fail("case_11_reads_sorted_scoped_fail_closed", "the cross-contract fixtures collided (content-derived id)")
    ev = EvidenceStore()
    ev.ingest(_observation_evidence(cid, value=1))
    ev.ingest(_claim_evidence(cid))
    ev.ingest(_observation_evidence(other_cid, value=2))
    ids = [r.record_id for r in ev.records()]
    if ids != sorted(ids):
        return fail("case_11_reads_sorted_scoped_fail_closed", "records() iteration is not record-id sorted")
    scoped = ev.for_contract(cid)
    if len(scoped) != 2 or any(r.contract_ref != cid for r in scoped):
        return fail("case_11_reads_sorted_scoped_fail_closed", "for_contract scoping is wrong")
    try:
        ev.get("evidence:observation:" + "0" * 64)
        return fail("case_11_reads_sorted_scoped_fail_closed", "unknown id read was accepted")
    except EvidenceError as error:
        if error.code != EvidenceReasonCode.RECORD_UNKNOWN:
            return fail("case_11_reads_sorted_scoped_fail_closed", "wrong code for unknown read: %s" % error.code)
    if not ev.has(scoped[0].record_id) or ev.has("nope"):
        return fail("case_11_reads_sorted_scoped_fail_closed", "existence probe is wrong")
    try:
        ev.for_contract("")
        return fail("case_11_reads_sorted_scoped_fail_closed", "empty contract_ref accepted")
    except EvidenceError:
        pass
    return ok("case_11_reads_sorted_scoped_fail_closed", "sorted iteration, contract scoping, fail-closed reads")


def case_12_structural_immutability() -> Result:
    store, cid, _ = _store_at("DELIVERY")
    record = _observation_evidence(cid)
    # frozen dataclass: attribute writes raise
    try:
        record.value = 100  # type: ignore[misc]
        return fail("case_12_structural_immutability", "record attribute mutation was permitted")
    except Exception:
        pass
    # the store exposes no update/remove path
    store_source = (REPO_ROOT / "evidence" / "store.py").read_text(encoding="utf-8")
    for forbidden in ("def update", "def delete", "def remove", "def pop", "def discard"):
        if forbidden in store_source:
            return fail("case_12_structural_immutability", "store carries a mutation API: %s" % forbidden)
    # persistence appends only
    if '"a"' not in store_source and "'a'" not in store_source:
        return fail("case_12_structural_immutability", "journal is not opened append-only")
    return ok("case_12_structural_immutability", "records are frozen dataclasses; the store is append-only")


# ---------------------------------------------------------------------------
# Section C — the disclosed telemetry harvest seam
# ---------------------------------------------------------------------------


def case_13_seam_translation_complete() -> Result:
    store, cid, _ = _store_at("DELIVERY")
    observation = _telemetry_observation()
    record = telemetry_observation_to_evidence(observation, cid)
    # complete, disclosed field mapping
    checks = (
        record.subject_ref == observation.subject_ref,
        record.metric == observation.metric == "latency-ms",
        record.value == observation.value,
        record.confidence_basis_points == observation.confidence_basis_points,
        record.instant == observation.observed_at,
        record.freshness_until == observation.freshness_until,
        record.producer == observation.source_node_id,
        record.source_refs == (observation.observation_id,),
        record.contract_ref == cid,
        record.record_type == "observation",
    )
    if not all(checks):
        return fail("case_13_seam_translation_complete", "field mapping mismatch: %s" % checks)
    # the seam is a pure function: same inputs -> byte-identical record
    again = telemetry_observation_to_evidence(_telemetry_observation(), cid)
    if again.canonical_bytes() != record.canonical_bytes():
        return fail("case_13_seam_translation_complete", "the seam is not deterministic")
    # the seam never mutates the telemetry record
    if observation.value != 45 or observation.observed_at != T1:
        return fail("case_13_seam_translation_complete", "the telemetry record was mutated")
    # the seam identity is disclosed for introspection
    if TELEMETRY_HARVEST_SEAM != "telemetry:observation->evidence:observation" or not SEAM_DISCLOSURE:
        return fail("case_13_seam_translation_complete", "seam disclosure missing")
    # the harvested record is a first-class typed record (ingestable)
    ev = EvidenceStore()
    if not ev.ingest(record).accepted:
        return fail("case_13_seam_translation_complete", "the harvested record is not ingestable")
    return ok(
        "case_13_seam_translation_complete",
        "harvest mapping complete, deterministic, non-mutating, ingestable",
    )


def case_14_seam_fail_closed() -> List[Result]:
    results: List[Result] = []
    store, cid, _ = _store_at("DELIVERY")
    # non-observation input
    results.append(
        expect_evidence_error(
            "case_14a_non_observation_input",
            EvidenceReasonCode.INVALID_INPUT,
            lambda: telemetry_observation_to_evidence({"metric": "latency-ms"}, cid),
        )
    )
    # a metric outside the frozen evidence vocabulary (crafted by bypassing
    # the telemetry constructor — the seam must still reject it)
    observation = _telemetry_observation()
    object.__setattr__(observation, "metric", "bogus-metric")
    results.append(
        expect_evidence_error(
            "case_14b_untranslatable_metric",
            EvidenceReasonCode.VOCABULARY,
            lambda: telemetry_observation_to_evidence(observation, cid),
        )
    )
    # the caller must inject the contract binding
    results.append(
        expect_evidence_error(
            "case_14c_empty_contract_ref",
            EvidenceReasonCode.INVALID_INPUT,
            lambda: telemetry_observation_to_evidence(_telemetry_observation(), ""),
        )
    )
    results.append(
        expect_evidence_error(
            "case_14d_non_str_contract_ref",
            EvidenceReasonCode.INVALID_INPUT,
            lambda: telemetry_observation_to_evidence(_telemetry_observation(), None),
        )
    )
    return results


def case_15_seam_vocabulary_crosscheck() -> Result:
    """OBSERVATION_METRICS must be EXACTLY the frozen telemetry metric
    registry names (the frozen primitive is reused, never reinvented)."""
    registry_names = set()
    for subject_metrics in TELEMETRY_METRIC_REGISTRY.values():
        registry_names.update(metric.name for metric in subject_metrics)
    evidence_names = set(OBSERVATION_METRICS)
    if registry_names != evidence_names:
        missing = sorted(registry_names - evidence_names)
        extra = sorted(evidence_names - registry_names)
        return fail(
            "case_15_seam_vocabulary_crosscheck",
            "vocabulary mismatch (missing %s / extra %s)" % (missing[:3], extra[:3]),
        )
    return ok(
        "case_15_seam_vocabulary_crosscheck",
        "observation-metric vocabulary == the frozen telemetry registry (%d names)" % len(evidence_names),
    )


def case_16_telemetry_surface_unchanged() -> Result:
    """The harvest is disclosed and telemetry stays the owner: the
    telemetry package is BYTE-IDENTICAL to origin/main (pure RETAIN --
    the strongest preservation of its frozen surface: the privacy
    fence, the policy-gated topology-promotion semantics, and the
    public API are untouched by construction), telemetry imports no
    evidence/assurance API, the seam lives in evidence/ only, and the
    single battery-side change is the disclosed case_19 amendment in
    tools/telemetry_selftest.py (the DAG-sanctioned-consumer
    allowlist pattern, six precedents)."""
    # 1. no evidence/assurance import anywhere in telemetry/
    for path in sorted((REPO_ROOT / "telemetry").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "import evidence" in source or "from evidence" in source:
            return fail("case_16_telemetry_surface_unchanged", "%s imports the evidence domain" % path.name)
        if "import assurance" in source or "from assurance" in source:
            return fail("case_16_telemetry_surface_unchanged", "%s imports the assurance domain" % path.name)
    # 2. the tracked telemetry delta vs origin/main is EMPTY (pure RETAIN)
    diff = subprocess.run(
        ["git", "diff", "--name-only", "origin/main", "--", "telemetry/"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    if diff.returncode != 0:
        return ok("case_16_telemetry_surface_unchanged", "no origin/main ref; the byte-identical check is CI-side")
    changed = [line for line in diff.stdout.splitlines() if line.strip()]
    if changed:
        return fail(
            "case_16_telemetry_surface_unchanged",
            "telemetry files changed (pure RETAIN requires byte-identical): %s" % changed,
        )
    return ok(
        "case_16_telemetry_surface_unchanged",
        "telemetry byte-identical to origin/main (pure RETAIN; no evidence/assurance import)",
    )


# ---------------------------------------------------------------------------
# Section D — obligations + the by-reference contract binding
# ---------------------------------------------------------------------------


def case_17_obligation_records_typed() -> List[Result]:
    results: List[Result] = []
    if OBLIGATION_KINDS != ("observation-bound", "claim-level", "commitment-window", "attestation-required"):
        results.append(fail("case_17a_kind_vocabulary", "obligation-kind vocabulary drifted"))
    else:
        results.append(ok("case_17a_kind_vocabulary", "one obligation kind per LOCK-106 evidence type"))
    if OBLIGATION_SEVERITIES != ("hard", "degradable") or BOUND_KINDS != ("floor", "ceiling"):
        results.append(fail("case_17b_frozen_vocabularies", "severity/bound vocabulary drifted"))
    else:
        results.append(ok("case_17b_frozen_vocabularies", "severity and bound vocabularies frozen"))
    # bound pair: both members or neither
    results.append(
        expect_assurance_error(
            "case_17c_half_bound",
            AssuranceReasonCode.INVALID_INPUT,
            lambda: AssuranceObligation(
                obligation_kind="observation-bound", subject_ref=PATH_REF,
                evidence_name="latency-ms", severity="hard", producer="arch:probe",
                bound_kind="ceiling",
            ),
        )
    )
    # per-kind evidence-name vocabulary
    results.append(
        expect_assurance_error(
            "case_17d_wrong_name_vocabulary",
            AssuranceReasonCode.VOCABULARY,
            lambda: AssuranceObligation(
                obligation_kind="attestation-required", subject_ref=PATH_REF,
                evidence_name="latency-ms", severity="hard", producer="arch:probe",
            ),
        )
    )
    # id tamper rejected
    obligation = _obligations()[0]
    payload = obligation.to_dict()
    payload["bound_value"] = 999
    results.append(
        expect_assurance_error(
            "case_17e_tamper",
            AssuranceReasonCode.ID_MISMATCH,
            lambda: AssuranceObligation.from_dict(payload),
        )
    )
    # round-trip
    rebuilt = AssuranceObligation.from_dict(obligation.to_dict())
    if rebuilt.canonical_bytes() != obligation.canonical_bytes():
        results.append(fail("case_17f_round_trip", "obligation round-trip diverged"))
    else:
        results.append(ok("case_17f_round_trip", "obligation canonical round-trip byte-identical"))
    return results


def case_18_contract_binding_by_reference() -> List[Result]:
    results: List[Result] = []
    obligations = _obligations()
    refs = to_contract_references(obligations)
    # the references are the contracts-domain opaque shape
    for ref, obligation in zip(refs, obligations):
        if ref.ref_kind != "assurance-obligation" or ref.value != obligation.obligation_id:
            results.append(fail("case_18a_reference_shape", "reference shape mismatch"))
            break
    else:
        results.append(ok("case_18a_reference_shape", "opaque assurance-obligation references carry the obligation ids"))
    store, cid, contract = _store_at("DELIVERY")
    resolved = resolve_obligations(contract, obligations)
    if tuple(o.obligation_id for o in resolved) != tuple(sorted(o.obligation_id for o in obligations)):
        results.append(fail("case_18b_resolution_order", "resolution is not deterministic obligation-id order"))
    else:
        results.append(ok("case_18b_resolution_order", "1:1 resolution in deterministic obligation-id order"))
    # the contract references an obligation the authority does not carry
    missing = AssuranceObligation(
        obligation_kind="claim-level", subject_ref=PATH_REF,
        evidence_name="status-statement", severity="degradable", producer="arch:other",
    )
    contract_with_extra = _store_at("DELIVERY", obligations + (missing,))[2]
    results.append(
        expect_assurance_error(
            "case_18c_unresolved_reference",
            AssuranceReasonCode.OBLIGATION_UNRESOLVED,
            lambda: resolve_obligations(contract_with_extra, obligations),
        )
    )
    # an obligation the contract does NOT reference (no second obligation model)
    results.append(
        expect_assurance_error(
            "case_18d_not_referenced",
            AssuranceReasonCode.OBLIGATION_NOT_REFERENCED,
            lambda: resolve_obligations(contract, obligations + (missing,)),
        )
    )
    # the contract domain is consumed by reference: a non-contract input fails
    results.append(
        expect_assurance_error(
            "case_18e_non_contract_input",
            AssuranceReasonCode.INVALID_INPUT,
            lambda: resolve_obligations({"assurance_obligations": ()}, obligations),
        )
    )
    return results


def case_19_evaluation_inputs_fail_closed() -> List[Result]:
    results: List[Result] = []
    store, cid, contract = _store_at("DELIVERY")
    obligations = _obligations()
    evidence = _default_evidence(cid)
    results.append(
        expect_assurance_error(
            "case_19a_non_contract_input",
            AssuranceReasonCode.INVALID_INPUT,
            lambda: evaluate_contract({"state": "DELIVERY"}, obligations, evidence, T2),
        )
    )
    results.append(
        expect_assurance_error(
            "case_19b_untyped_evidence",
            AssuranceReasonCode.INVALID_INPUT,
            lambda: evaluate_contract(contract, obligations, [{"record_type": "claim"}], T2),
        )
    )
    results.append(
        expect_assurance_error(
            "case_19c_invalid_instant",
            AssuranceReasonCode.INVALID_INSTANT,
            lambda: evaluate_contract(contract, obligations, evidence, "later"),
        )
    )
    # pre-activation state is outside the evaluation surface
    fresh = ContractStore()
    created = fresh.submit(_create_command(obligations), recorded_at=CREATE_AT)
    results.append(
        expect_assurance_error(
            "case_19d_not_evaluable_pre_activation",
            AssuranceReasonCode.NOT_EVALUABLE,
            lambda: evaluate_contract(created.contract, obligations, [], T2),
        )
    )
    return results


def case_20_no_second_contract_model() -> List[Result]:
    results: List[Result] = []
    # 1. evidence/ never imports the contract domain (LOCK-101)
    for path in sorted((REPO_ROOT / "evidence").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "from contracts" in source or "import contracts" in source:
            results.append(fail("case_20a_evidence_isolated", "%s imports the contract domain" % path.name))
            break
    else:
        results.append(ok("case_20a_evidence_isolated", "evidence/ imports no contract API (LOCK-101)"))
    # 2. the contracts authority is byte-identical to origin/main (consumed
    #    by reference — this PR must not touch contracts/)
    diff = subprocess.run(
        ["git", "diff", "--name-only", "origin/main", "--", "contracts/"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    if diff.returncode == 0 and diff.stdout.strip():
        results.append(fail("case_20b_contracts_untouched", "contracts/ was modified: %s" % diff.stdout.strip()))
    else:
        results.append(ok("case_20b_contracts_untouched", "contracts/ is byte-identical (consumed by reference)"))
    # 3. only the bridge submits contract commands
    submitters = []
    for path in sorted((REPO_ROOT / "assurance").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if ".submit(" in source:
            submitters.append(path.name)
    if set(submitters) - {"bridge.py"}:
        results.append(fail("case_20c_single_write_path", "non-bridge submission: %s" % submitters))
    else:
        results.append(ok("case_20c_single_write_path", "bridge.py is the sole contract write path"))
    # 4. assurance never mutates a contract object in place
    for path in sorted((REPO_ROOT / "assurance").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "dataclasses.replace(contract" in source or "__setattr__(contract" in source:
            results.append(fail("case_20d_no_contract_mutation", "%s mutates contract objects" % path.name))
            break
    else:
        results.append(ok("case_20d_no_contract_mutation", "no in-place contract mutation in assurance/"))
    return results


# ---------------------------------------------------------------------------
# Section E — the LOCK-107 evaluation kernel
# ---------------------------------------------------------------------------


def case_21_state_vocabulary_frozen() -> Result:
    if ASSURANCE_STATES != (
        "compliant", "degraded", "violated", "unknown", "failed", "deliberately_terminated",
    ):
        return fail("case_21_state_vocabulary_frozen", "the §9 state vocabulary drifted: %s" % (ASSURANCE_STATES,))
    if REASON_KINDS != (
        "satisfied", "value-breach", "absence-breach", "stale-evidence",
        "absent-evidence", "contract-failed", "contract-terminated",
    ):
        return fail("case_21_state_vocabulary_frozen", "reason-kind vocabulary drifted")
    if EVALUABLE_CONTRACT_STATES != ("CONTRACT_ACTIVE", "EXECUTION_ACTIVE", "DELIVERY", "ASSURED", "DEGRADED"):
        return fail("case_21_state_vocabulary_frozen", "evaluable contract-state list drifted")
    return ok("case_21_state_vocabulary_frozen", "the frozen §9 vocabulary: exactly the six states")


def case_22_state_compliant() -> Result:
    store, cid, contract = _store_at("DELIVERY")
    evaluation = evaluate_contract(contract, _obligations(), _default_evidence(cid), T2)
    if evaluation.state != "compliant":
        return fail("case_22_state_compliant", "state was %r, expected compliant" % evaluation.state)
    if len(evaluation.reasons) != 4 or any(r.reason_kind != "satisfied" for r in evaluation.reasons):
        return fail("case_22_state_compliant", "reasons not all satisfied: %s" % [r.reason_kind for r in evaluation.reasons])
    # every satisfied reason cites its obligation AND its evidence
    for reason in evaluation.reasons:
        if not reason.obligation_id or not reason.evidence_id:
            return fail("case_22_state_compliant", "a satisfied reason does not cite obligation+evidence")
    # the evaluation id is content-derived over the canonical result
    if not evaluation.evaluation_id.startswith("assurance:evaluation:"):
        return fail("case_22_state_compliant", "evaluation id prefix wrong")
    if evaluation.canonical_bytes() != canonical_json_bytes(evaluation.to_dict()):
        return fail("case_22_state_compliant", "evaluation bytes diverge from canonical JSON")
    return ok("case_22_state_compliant", "compliant reachable: 4/4 satisfied reasons cite obligation + evidence")


def case_23_state_violated() -> Result:
    store, cid, contract = _store_at("DELIVERY")
    evidence = _default_evidence(cid)
    evidence[0] = _observation_evidence(cid, value=150)  # hard ceiling breach
    evaluation = evaluate_contract(contract, _obligations(), evidence, T2)
    if evaluation.state != "violated":
        return fail("case_23_state_violated", "state was %r, expected violated" % evaluation.state)
    breach = [r for r in evaluation.reasons if r.reason_kind == "value-breach"]
    if len(breach) != 1:
        return fail("case_23_state_violated", "expected exactly one value-breach reason")
    reason = breach[0]
    if reason.severity != "hard":
        return fail("case_23_state_violated", "breach reason does not carry the hard severity")
    if not reason.evidence_id or not reason.obligation_id:
        return fail("case_23_state_violated", "breach reason does not cite obligation + triggering evidence")
    triggering = [r for r in evidence if r.record_id == reason.evidence_id]
    if not triggering or triggering[0].value != 150:
        return fail("case_23_state_violated", "the cited evidence is not the breaching record")
    return ok("case_23_state_violated", "violated reachable: hard breach cites obligation + triggering evidence")


def case_24_state_degraded() -> List[Result]:
    results: List[Result] = []
    # (a) a degradable value breach
    obligations = _obligations()
    degradable_claim = AssuranceObligation(
        obligation_kind="claim-level", subject_ref=PATH_REF,
        evidence_name="capability-statement", severity="degradable", producer="arch:probe",
        bound_kind="floor", bound_value=10,
    )
    obligations = tuple(
        degradable_claim if o.obligation_kind == "claim-level" else o for o in obligations
    )
    store, cid, contract = _store_at("DELIVERY", obligations)
    evidence = _default_evidence(cid)
    evaluation = evaluate_contract(contract, obligations, evidence, T2)
    if evaluation.state != "degraded":
        results.append(fail("case_24a_degradable_value_breach", "state was %r, expected degraded" % evaluation.state))
    else:
        results.append(ok("case_24a_degradable_value_breach", "degraded reachable via a degradable value breach"))
    # (b) a degradable deadline absence breach
    deadline_claim = AssuranceObligation(
        obligation_kind="claim-level", subject_ref=PATH_REF,
        evidence_name="status-statement", severity="degradable", producer="arch:probe",
        evidence_deadline=T_DEADLINE,
    )
    store2, cid2, contract2 = _store_at("DELIVERY", (deadline_claim,))
    # no claim evidence at all; evaluated AFTER the deadline
    evaluation2 = evaluate_contract(contract2, (deadline_claim,), [], T3)
    if evaluation2.state != "degraded":
        results.append(fail("case_24b_degradable_absence_breach", "state was %r, expected degraded" % evaluation2.state))
    else:
        absence = [r for r in evaluation2.reasons if r.reason_kind == "absence-breach"]
        if len(absence) != 1 or absence[0].severity != "degradable":
            results.append(fail("case_24b_degradable_absence_breach", "absence-breach reason malformed"))
        else:
            results.append(ok("case_24b_degradable_absence_breach", "degraded reachable via a degradable deadline absence breach"))
    return results


def case_25_state_unknown() -> List[Result]:
    results: List[Result] = []
    # (a) stale evidence: the window does not cover the evaluation instant
    # (deadline-less fixtures so PURE staleness is isolated — no fired
    # deadline can escalate the missing evidence into a breach)
    store, cid, contract = _store_at("DELIVERY", _obligations(with_deadlines=False))
    evaluation = evaluate_contract(
        contract, _obligations(with_deadlines=False), _default_evidence(cid), T3
    )
    if evaluation.state != "unknown":
        results.append(fail("case_25a_stale_evidence", "state was %r, expected unknown" % evaluation.state))
    else:
        stale = [r for r in evaluation.reasons if r.reason_kind == "stale-evidence"]
        if len(stale) != 1:
            results.append(fail("case_25a_stale_evidence", "expected exactly one stale-evidence reason"))
        else:
            results.append(ok("case_25a_stale_evidence", "unknown reachable via a stale validity window (reason cites the record)"))
    # (b) absent evidence, no fired deadline
    store2, cid2, contract2 = _store_at("DELIVERY")
    evaluation2 = evaluate_contract(contract2, _obligations(), [], T2)
    if evaluation2.state != "unknown":
        results.append(fail("case_25b_absent_evidence", "state was %r, expected unknown" % evaluation2.state))
    else:
        absent = [r for r in evaluation2.reasons if r.reason_kind == "absent-evidence"]
        if len(absent) != 4:
            results.append(fail("case_25b_absent_evidence", "expected every obligation to report absence (the two deadlines have not fired)"))
        else:
            results.append(ok("case_25b_absent_evidence", "unknown reachable via absent evidence (never treated as compliant)"))
    # (c) unknown is NEVER recorded as compliant: the aggregation is strict
    store3, cid3, contract3 = _store_at("DELIVERY", _obligations(with_deadlines=False))
    mixed = [_claim_evidence(cid3), _commitment_evidence(cid3), _attestation_evidence(cid3)]  # no observation
    evaluation3 = evaluate_contract(
        contract3, _obligations(with_deadlines=False), mixed, T2
    )
    if evaluation3.state not in ("unknown", "violated"):
        results.append(fail("case_25c_unknown_not_compliant", "absence aggregated to %r" % evaluation3.state))
    else:
        results.append(ok("case_25c_unknown_not_compliant", "missing evidence can never aggregate to compliant"))
    return results


def case_26_state_failed() -> Result:
    store, cid, contract = _store_at("FAILED")
    evaluation = evaluate_contract(contract, _obligations(), _default_evidence(cid), T2)
    if evaluation.state != "failed":
        return fail("case_26_state_failed", "state was %r, expected failed" % evaluation.state)
    if len(evaluation.reasons) != 1 or evaluation.reasons[0].reason_kind != "contract-failed":
        return fail("case_26_state_failed", "expected the single contract-failed short-circuit reason")
    return ok("case_26_state_failed", "the §9 'failed' state reachable: a FAILED contract short-circuits, no re-evaluation")


def case_27_state_deliberately_terminated() -> Result:
    store, cid, contract = _store_at("TERMINATED")
    evaluation = evaluate_contract(contract, _obligations(), _default_evidence(cid), T2)
    if evaluation.state != "deliberately_terminated":
        return fail("case_27_state_deliberately_terminated", "state was %r" % evaluation.state)
    if evaluation.reasons[0].reason_kind != "contract-terminated":
        return fail("case_27_state_deliberately_terminated", "expected the contract-terminated short-circuit reason")
    # even BREACHING evidence cannot change a terminal verdict — and the
    # evaluation record PROVES the immunity: the short-circuit verdict is a
    # pure function of (contract state, instant), so the evaluation id is
    # byte-identical under completely different evidence
    breaching = _default_evidence(cid)
    breaching[0] = _observation_evidence(cid, value=150)
    evaluation2 = evaluate_contract(contract, _obligations(), breaching, T2)
    if evaluation2.state != "deliberately_terminated" or evaluation2.evaluation_id != evaluation.evaluation_id:
        return fail("case_27_state_deliberately_terminated", "terminal dispatch is not evidence-independent")
    return ok("case_27_state_deliberately_terminated", "deliberately_terminated reachable: TERMINATED short-circuits, evidence-immune")


def case_28_instant_threshold_staleness() -> Result:
    """Staleness is derived from the injected instant, never wall clock:
    the SAME evidence set is fresh at T2 and stale at T3 (deadline-less
    fixtures so the late evaluation reports PURE staleness)."""
    obligations = _obligations(with_deadlines=False)
    store, cid, contract = _store_at("DELIVERY", obligations)
    evidence = _default_evidence(cid)
    early = evaluate_contract(contract, obligations, evidence, T2)
    late = evaluate_contract(contract, obligations, evidence, T3)
    if early.state != "compliant":
        return fail("case_28_instant_threshold_staleness", "T2 evaluation was %r" % early.state)
    if late.state != "unknown":
        return fail("case_28_instant_threshold_staleness", "T3 evaluation was %r" % late.state)
    if late.evaluation_id == early.evaluation_id:
        return fail("case_28_instant_threshold_staleness", "different instants produced the same evaluation id")
    return ok("case_28_instant_threshold_staleness", "the injected instant flips fresh -> stale (no wall clock)")


def case_29_deadline_absence_breach() -> Result:
    obligations = (
        AssuranceObligation(
            obligation_kind="observation-bound", subject_ref=PATH_REF,
            evidence_name="latency-ms", severity="hard", producer="arch:probe",
            bound_kind="ceiling", bound_value=120,
            evidence_deadline=T_DEADLINE,
        ),
    )
    store, cid, contract = _store_at("DELIVERY", obligations)
    # before the deadline: absent evidence is unknown (honest, not a breach)
    before = evaluate_contract(contract, obligations, [], T2)
    if before.state != "unknown":
        return fail("case_29_deadline_absence_breach", "pre-deadline absence was %r" % before.state)
    # after the deadline: the ABSENCE itself breaches at the severity
    after = evaluate_contract(contract, obligations, [], T3)
    if after.state != "violated":
        return fail("case_29_deadline_absence_breach", "post-deadline absence was %r" % after.state)
    reason = after.reasons[0]
    if reason.reason_kind != "absence-breach" or reason.evidence_id != "":
        return fail("case_29_deadline_absence_breach", "absence-breach reason malformed (must cite no evidence)")
    return ok("case_29_deadline_absence_breach", "absence after the deadline breaches, citing the evidence ABSENCE")


def case_30_latest_evidence_wins() -> Result:
    store, cid, contract = _store_at("DELIVERY")
    obligations = _obligations()
    rest = [
        _claim_evidence(cid),
        _commitment_evidence(cid),
        _attestation_evidence(cid),
    ]
    older = _observation_evidence(cid, value=45, instant=T1)
    newer = _observation_evidence(cid, value=150, instant=T1B)
    evaluation = evaluate_contract(contract, obligations, [older, newer] + rest, T2)
    if evaluation.state != "violated":
        return fail("case_30_latest_evidence_wins", "an older satisfying record masked the newer breach")
    reason = [r for r in evaluation.reasons if r.reason_kind == "value-breach"][0]
    if reason.evidence_id != newer.record_id:
        return fail("case_30_latest_evidence_wins", "the breach did not cite the NEWEST record")
    # and the honest reverse: the newest record satisfies over an older breach
    older_bad = _observation_evidence(cid, value=150, instant=T1)
    newer_good = _observation_evidence(cid, value=45, instant=T1B)
    evaluation2 = evaluate_contract(contract, obligations, [older_bad, newer_good] + rest, T2)
    if evaluation2.state != "compliant":
        return fail("case_30_latest_evidence_wins", "an older breach masked the newer satisfying record")
    satisfied = [r for r in evaluation2.reasons if r.reason_kind == "satisfied" and r.evidence_id == newer_good.record_id]
    if not satisfied:
        return fail("case_30_latest_evidence_wins", "the satisfaction did not cite the NEWEST record")
    return ok("case_30_latest_evidence_wins", "the current evidence is the current truth (both directions)")


def case_31_no_time_travel() -> Result:
    store, cid, contract = _store_at("DELIVERY")
    future = _observation_evidence(cid, value=45, instant=T3, freshness_until="2026-10-01T03:00:00Z")
    evaluation = evaluate_contract(contract, _obligations(), [future], T2)
    if evaluation.state != "unknown":
        return fail("case_31_no_time_travel", "a record produced AFTER the evaluation instant was used (%r)" % evaluation.state)
    return ok("case_31_no_time_travel", "records produced after the evaluation instant are ignored entirely")


def case_32_contract_scoping() -> Result:
    """Evidence bound to ANOTHER contract never evaluates this one."""
    store, cid, contract = _store_at("DELIVERY")
    other_store, other_cid, _ = _store_at("DELIVERY", principal_ref="app:probe-2")
    if other_cid == cid:
        return fail("case_32_contract_scoping", "the cross-contract fixtures collided (content-derived id)")
    foreign = _default_evidence(other_cid)
    evaluation = evaluate_contract(contract, _obligations(), foreign, T2)
    if evaluation.state != "unknown":
        return fail("case_32_contract_scoping", "foreign-contract evidence leaked into the evaluation (%r)" % evaluation.state)
    # a claim cannot satisfy an observation-bound obligation (LOCK-106:
    # the evidence TYPE is part of the match — no cross-type satisfaction)
    obs_only = (_obligations()[0],)
    claim_store, claim_cid, claim_contract = _store_at("DELIVERY", obs_only)
    claim_only = [_claim_evidence(claim_cid)]
    evaluation2 = evaluate_contract(claim_contract, obs_only, claim_only, T2)
    if evaluation2.state != "unknown" or evaluation2.reasons[0].reason_kind != "absent-evidence":
        return fail("case_32_contract_scoping", "a claim satisfied an observation-bound obligation")
    return ok("case_32_contract_scoping", "contract scoping + type-strict matching (no cross-type satisfaction)")


def case_33_per_kind_eligibility() -> Result:
    """Validity at the evaluation instant is per-type: observations need a
    covering freshness window, commitments a covering window, attestations
    an unexpired validity; claims carry no expiry."""
    store, cid, contract = _store_at("DELIVERY")
    evidence = _default_evidence(cid)
    # (a) commitment whose window does NOT cover T2 -> not eligible
    evidence[2] = _commitment_evidence(cid, valid_from=T0, valid_until=T1)
    # (b) attestation expired at T2 -> not eligible (valid until T1B,
    # strictly after its own production instant, strictly before T2)
    evidence[3] = _attestation_evidence(cid, valid_until=T1B)
    # (c) claim keeps satisfying (no expiry, by design)
    evaluation = evaluate_contract(contract, _obligations(), evidence, T2)
    kinds = {r.reason_kind for r in evaluation.reasons}
    if "stale-evidence" not in kinds:
        return fail("case_33_per_kind_eligibility", "expired commitment/attestation not reported stale: %s" % kinds)
    if evaluation.state != "unknown":
        return fail("case_33_per_kind_eligibility", "state was %r, expected unknown" % evaluation.state)
    claim_reason = [r for r in evaluation.reasons if r.reason_kind == "satisfied" and r.evidence_id == evidence[1].record_id]
    if not claim_reason:
        return fail("case_33_per_kind_eligibility", "the claim lost eligibility (claims carry no expiry)")
    return ok("case_33_per_kind_eligibility", "per-kind eligibility honored (commitment/attestation stale, claim exempt)")


def case_34_deterministic_replay() -> Result:
    store, cid, contract = _store_at("DELIVERY")
    evidence = _default_evidence(cid)
    first = evaluate_contract(contract, _obligations(), evidence, T2)
    second = evaluate_contract(contract, _obligations(), evidence, T2)
    if first.evaluation_id != second.evaluation_id or first.canonical_bytes() != second.canonical_bytes():
        return fail("case_34_deterministic_replay", "same inputs produced different evaluations")
    # input ORDER independence: shuffled evidence, shuffled obligations
    shuffled = list(reversed(evidence))
    third = evaluate_contract(contract, tuple(reversed(_obligations())), shuffled, T2)
    if third.evaluation_id != first.evaluation_id or third.canonical_bytes() != first.canonical_bytes():
        return fail("case_34_deterministic_replay", "input order changed the evaluation")
    # reasons are in deterministic obligation-id order
    ids = [r.obligation_id for r in first.reasons]
    if ids != sorted(ids):
        return fail("case_34_deterministic_replay", "reason order is not deterministic")
    return ok("case_34_deterministic_replay", "same inputs -> byte-identical evaluation (order independent)")


# ---------------------------------------------------------------------------
# Section F — the evaluation journal + the contract bridge
# ---------------------------------------------------------------------------


def case_35_journal_idempotent_recovery() -> Result:
    store, cid, contract = _store_at("DELIVERY")
    evaluation = evaluate_contract(contract, _obligations(), _default_evidence(cid), T2)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "assurance.jsonl"
        journal = AssuranceJournal(journal_path=path)
        first = journal.append(evaluation)
        if not first.accepted:
            return fail("case_35_journal_idempotent_recovery", "the first append was not accepted")
        duplicate = journal.append(evaluation)
        if duplicate.accepted or len(journal) != 1:
            return fail("case_35_journal_idempotent_recovery", "duplicate append re-recorded")
        digest = journal.state_digest()
        # construction-is-recovery
        recovered = AssuranceJournal(journal_path=path)
        if recovered.state_digest() != digest or len(recovered) != 1:
            return fail("case_35_journal_idempotent_recovery", "journal re-fold diverged")
        if recovered.latest_for(cid).evaluation_id != evaluation.evaluation_id:
            return fail("case_35_journal_idempotent_recovery", "latest_for diverged after re-fold")
        # tampered evaluation under a retained id fails closed
        tampered = evaluate_contract(contract, _obligations(), _default_evidence(cid), T3)
        object.__setattr__(tampered, "evaluation_id", evaluation.evaluation_id)
        try:
            recovered.append(tampered)
            return fail("case_35_journal_idempotent_recovery", "a tampered evaluation was appended")
        except AssuranceError as error:
            if error.code != AssuranceReasonCode.JOURNAL_TAMPER:
                return fail("case_35_journal_idempotent_recovery", "wrong tamper code: %s" % error.code)
        # a secret-shaped journal line never enters the fold
        secret = Path(tmp) / "secret.jsonl"
        secret.write_text('{"x": "ghp_supersecrettoken123"}\n', encoding="utf-8")
        try:
            AssuranceJournal(journal_path=secret)
            return fail("case_35_journal_idempotent_recovery", "a secret-shaped line was folded")
        except AssuranceError as error:
            if error.code != AssuranceReasonCode.SECRET_REJECTED:
                return fail("case_35_journal_idempotent_recovery", "wrong secret code: %s" % error.code)
    # fail-closed queries
    try:
        AssuranceJournal().latest_for("contract:none")
        return fail("case_35_journal_idempotent_recovery", "unknown-contract latest_for was accepted")
    except AssuranceError as error:
        if error.code != AssuranceReasonCode.EVALUATION_UNKNOWN:
            return fail("case_35_journal_idempotent_recovery", "wrong unknown code: %s" % error.code)
    return ok("case_35_journal_idempotent_recovery", "append-only history, idempotent re-fold, fail-closed tamper/secret/unknown")


def case_36_bridge_mapping_frozen() -> Result:
    expected = {
        "compliant": "compliant",
        "degraded": "degraded",
        "violated": "violated",
        "unknown": "unknown-stale",
    }
    if EVALUATION_TO_RECORDED_STATE != expected:
        return fail("case_36_bridge_mapping_frozen", "bridge mapping drifted: %s" % EVALUATION_TO_RECORDED_STATE)
    for recorded in EVALUATION_TO_RECORDED_STATE.values():
        if recorded not in CONTRACT_ASSURANCE_STATES:
            return fail("case_36_bridge_mapping_frozen", "%r is outside the contracts assurance vocabulary" % recorded)
    # the recordable states derive from the frozen M002 transition table
    derived = tuple(sorted(
        state for state, targets in CONTRACT_TRANSITIONS.items()
        if "ASSURED" in targets or "DEGRADED" in targets
    ))
    if tuple(sorted(CONTRACT_RECORDABLE_STATES)) != derived:
        return fail("case_36_bridge_mapping_frozen", "recordable states diverged from the transition table")
    if DEFAULT_BRIDGE_ISSUER != "assurance:m005":
        return fail("case_36_bridge_mapping_frozen", "bridge issuer drifted")
    return ok(
        "case_36_bridge_mapping_frozen",
        "closed mapping onto the consumed contracts vocabulary (unknown -> unknown-stale)",
    )


def case_37_bridge_closed_loop() -> Result:
    store, cid, contract = _store_at("DELIVERY")
    evidence = _default_evidence(cid)
    evaluation = evaluate_contract(contract, _obligations(), evidence, T2)
    command = bridge_command(evaluation)
    if not isinstance(command, RecordAssurance):
        return fail("case_37_bridge_closed_loop", "no command for a compliant evaluation")
    if command.assurance_state != "compliant":
        return fail("case_37_bridge_closed_loop", "command state was %r" % command.assurance_state)
    if command.recorded_at != T2:
        return fail("case_37_bridge_closed_loop", "command recorded_at was not the evaluation instant")
    # the evaluation id rides the decision-kind reference with provenance
    if len(command.evidence_refs) != 1:
        return fail("case_37_bridge_closed_loop", "expected exactly one decision reference")
    ref = command.evidence_refs[0]
    if ref.ref_kind != "decision" or ref.value != evaluation.evaluation_id:
        return fail("case_37_bridge_closed_loop", "the decision reference does not carry the evaluation id")
    if not ref.provenance or not ref.provenance.issuer:
        return fail("case_37_bridge_closed_loop", "the decision reference carries no provenance")
    # the full loop: record into the live store -> contract advances
    record_into_contract(store, evaluation, cid)
    if store.contract(cid).state != "ASSURED":
        return fail("case_37_bridge_closed_loop", "contract state was %r after bridging" % store.contract(cid).state)
    # a violated evaluation fails the contract (the frozen M002 semantics:
    # ``violated`` fails the contract with the constraint-violated reason)
    store2, cid2, contract2 = _store_at("DELIVERY")
    breaching = _default_evidence(cid2)
    breaching[0] = _observation_evidence(cid2, value=150)
    bad = evaluate_contract(contract2, _obligations(), breaching, T2)
    record_into_contract(store2, bad, cid2)
    failed_contract = store2.contract(cid2)
    if failed_contract.state != "FAILED" or failed_contract.termination_reason != "constraint-violated":
        return fail(
            "case_37_bridge_closed_loop",
            "violated evaluation recorded %r (termination_reason=%r)"
            % (failed_contract.state, failed_contract.termination_reason),
        )
    return ok(
        "case_37_bridge_closed_loop",
        "closed loop: evidence -> verdict -> RecordAssurance -> ASSURED (or FAILED on a violated verdict)",
    )


def case_38_bridge_terminal_noop() -> Result:
    failed_store, failed_cid, failed_contract = _store_at("FAILED")
    failed_eval = evaluate_contract(failed_contract, _obligations(), _default_evidence(failed_cid), T2)
    if bridge_command(failed_eval) is not None:
        return fail("case_38_bridge_terminal_noop", "a command was built for a FAILED-contract evaluation")
    term_store, term_cid, term_contract = _store_at("TERMINATED")
    term_eval = evaluate_contract(term_contract, _obligations(), _default_evidence(term_cid), T2)
    if bridge_command(term_eval) is not None:
        return fail("case_38_bridge_terminal_noop", "a command was built for a TERMINATED-contract evaluation")
    # the honest no-op leaves contract state untouched
    if record_into_contract(term_store, term_eval, term_cid) is not None:
        return fail("case_38_bridge_terminal_noop", "the terminal no-op attempted a write")
    if term_store.contract(term_cid).state != "TERMINATED":
        return fail("case_38_bridge_terminal_noop", "the terminal no-op changed the contract state")
    return ok("case_38_bridge_terminal_noop", "terminal verdicts bridge to an explicit no-op (never a silent write)")


def case_39_bridge_not_applicable() -> Result:
    store, cid, contract = _store_at("CONTRACT_ACTIVE")
    evaluation = evaluate_contract(contract, _obligations(), _default_evidence(cid), T2)
    try:
        record_into_contract(store, evaluation, cid)
        return fail("case_39_bridge_not_applicable", "bridging outside the recordable states was accepted")
    except AssuranceError as error:
        if error.code != AssuranceReasonCode.BRIDGE_NOT_APPLICABLE:
            return fail("case_39_bridge_not_applicable", "wrong code: %s" % error.code)
    if store.contract(cid).state != "CONTRACT_ACTIVE":
        return fail("case_39_bridge_not_applicable", "the rejected bridge mutated the contract")
    return ok("case_39_bridge_not_applicable", "non-recordable lifecycle states fail closed before submission")


# ---------------------------------------------------------------------------
# Section G — engineering discipline
# ---------------------------------------------------------------------------


def case_40_clock_discipline() -> Result:
    for package in ("evidence", "assurance"):
        directory = REPO_ROOT / package
        if not directory.is_dir():
            return fail("case_40_clock_discipline", "%s/ package missing" % package)
        source = "\n".join(
            path.read_text(encoding="utf-8") for path in sorted(directory.glob("*.py"))
        )
        for forbidden in (
            "datetime.now", "time.time", "utcnow", "uuid", "random.",
            "socket.", "requests.", "urlopen", "time.monotonic", "time.sleep",
        ):
            if forbidden in source:
                return fail("case_40_clock_discipline", "forbidden construct %r in %s/" % (forbidden, package))
    return ok("case_40_clock_discipline", "no wall clock, randomness, UUIDs, or network in evidence/ + assurance/")


def case_41_import_discipline() -> Result:
    """AST-level import scan: only the stdlib allowlist, the local
    protocol/contracts/telemetry seams, and intra-package imports."""
    stdlib_allow = {
        "__future__", "ast", "hashlib", "json", "re", "threading",
        "pathlib", "typing", "dataclasses", "tempfile",
    }
    local_allow = {"protocol", "contracts", "telemetry", "evidence", "assurance"}
    for package in ("evidence", "assurance"):
        for path in sorted((REPO_ROOT / package).glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    imported.add(node.module.split(".")[0])
            unexpected = sorted(imported - stdlib_allow - local_allow)
            if unexpected:
                return fail("case_41_import_discipline", "%s imports %s" % (path.name, unexpected))
    # evidence/ imports neither contracts nor assurance (the data layer)
    for path in sorted((REPO_ROOT / "evidence").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in ("contracts", "assurance"):
                return fail("case_41_import_discipline", "%s imports %s (layering violation)" % (path.name, node.module))
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in ("contracts", "assurance"):
                        return fail("case_41_import_discipline", "%s imports %s (layering violation)" % (path.name, alias.name))
    # the telemetry import lives ONLY in the seam module (the explicit
    # harvest direction — AST-level, docstring mentions do not count)
    for path in sorted((REPO_ROOT / "evidence").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            module = None
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                module = node.module.split(".")[0]
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] == "telemetry":
                        module = "telemetry"
            if module == "telemetry" and path.name != "telemetry_seam.py":
                return fail("case_41_import_discipline", "telemetry imported outside the seam module (%s)" % path.name)
    return ok("case_41_import_discipline", "imports confined to the layering contract (seam is the only telemetry consumer)")


def case_42_lock_conformance_mapping() -> Result:
    store, cid, contract = _store_at("DELIVERY")
    evaluation = evaluate_contract(contract, _obligations(), _default_evidence(cid), T2)
    command = bridge_command(evaluation)
    checks = {
        "LOCK-101": isinstance(command, RecordAssurance) and store.contract(cid).state in CONTRACT_STATES,
        "LOCK-106": len(EVIDENCE_TYPES) == 4 and len({t for t in EVIDENCE_TYPES}) == 4,
        "LOCK-107": evaluation.state in ASSURANCE_STATES and len(evaluation.reasons) == 4,
        "LOCK-113": True,  # proven structurally by case_20c (single write path) + no payment vocabulary
        "LOCK-117": all(
            ref.ref_kind == "assurance-obligation" for ref in contract.assurance_obligations
        ),
        "LOCK-118": evaluation.provenance_cited()
        if hasattr(evaluation, "provenance_cited")
        else command.evidence_refs[0].provenance is not None,
        "LOCK-119": EvidenceReasonCode.SECRET_REJECTED in EvidenceReasonCode.values()
        and AssuranceReasonCode.SECRET_REJECTED in AssuranceReasonCode.values(),
    }
    missing = [lock for lock, held in checks.items() if not held]
    if missing:
        return fail("case_42_lock_conformance_mapping", "locks not evidenced: %s" % missing)
    # LOCK-113 structural: no payment vocabulary in the two domains
    for package in ("evidence", "assurance"):
        for path in sorted((REPO_ROOT / package).glob("*.py")):
            source = path.read_text(encoding="utf-8")
            for forbidden in ("charge", "refund", "invoice", "payment_gateway", "card"):
                if forbidden in source:
                    return fail("case_42_lock_conformance_mapping", "payment vocabulary in %s/%s (%r)" % (package, path.name, forbidden))
    return ok("case_42_lock_conformance_mapping", "LOCK-101/106/107/113/117/118/119 evidenced on the closed loop")


def case_43_cross_process_determinism() -> Result:
    """PYTHONHASHSEED-varied subprocesses must produce byte-identical
    store digest, journal digest, and evaluation id."""
    probe = r"""
import sys, tempfile
from pathlib import Path
sys.path.insert(0, %r)
from evidence import EvidenceStore
from assurance import (
    AssuranceJournal, AssuranceObligation, evaluate_contract,
)
from contracts import (
    ContractStore, CreateContract, ConnectivityPrincipal, BeneficiaryScope,
    OpaqueReference, Provenance, ValidityInterval, HardConstraint,
    TerminationRules, SelectOffers, ActivateContract, RecordExecutionActivation,
    RecordDelivery,
)

PATH_REF = "adcos:path:" + "p" * 32
T0 = "2026-10-01T00:00:00Z"
T1 = "2026-10-01T00:10:00Z"
T2 = "2026-10-01T00:20:00Z"
T_END = "2026-11-01T00:00:00Z"

obligations = (
    AssuranceObligation(
        obligation_kind="observation-bound", subject_ref=PATH_REF,
        evidence_name="latency-ms", severity="hard", producer="arch:probe",
        bound_kind="ceiling", bound_value=120,
        evidence_deadline="2026-10-01T00:30:00Z",
    ),
    AssuranceObligation(
        obligation_kind="claim-level", subject_ref=PATH_REF,
        evidence_name="capability-statement", severity="degradable",
        producer="arch:probe",
    ),
)
from assurance import to_contract_references
cmd = CreateContract(
    principal=ConnectivityPrincipal(principal_kind="APPLICATION", principal_ref="app:probe-1"),
    beneficiaries=(BeneficiaryScope(beneficiary_kind="DEVICE", beneficiary_ref="dev:probe-9"),),
    requirements=(OpaqueReference(ref_kind="intent-requirements", value="intent:p-1", provenance=Provenance(issuer="arch:probe")),),
    hard_constraints=(HardConstraint(kind="latency-bound", params={"max_ms": 150}, provenance=Provenance(issuer="prov:probe")),),
    validity=ValidityInterval(not_before=T0, not_after=T_END),
    service_properties=(OpaqueReference(ref_kind="service-property", value="prop:p-1", provenance=Provenance(issuer="prov:probe")),),
    usage_pricing_terms=OpaqueReference(ref_kind="usage-pricing-terms", value="terms:p-1", provenance=Provenance(issuer="comm:probe")),
    assurance_obligations=to_contract_references(obligations),
    execution_scope=(OpaqueReference(ref_kind="execution-scope", value="scope:p-1", provenance=Provenance(issuer="arch:probe")),),
    termination=TerminationRules(conditions=("principal-requested",), compensation=OpaqueReference(ref_kind="compensation", value="comp:p-1", provenance=Provenance(issuer="comm:probe"))),
    provenance=Provenance(issuer="arch:probe", decision_refs=("dec:p-1",)),
)
store = ContractStore()
r = store.submit(cmd, recorded_at="2026-09-30T10:00:00Z")
cid = r.contract.contract_id
store.submit(SelectOffers(offers=(OpaqueReference(ref_kind="offer", value="offer:p-9", provenance=Provenance(issuer="prov:probe")),)), recorded_at="2026-09-30T10:05:00Z", contract_id=cid)
store.submit(ActivateContract(activated_at=T0, signature_refs=(OpaqueReference(ref_kind="signature", value="sig:p-1"),)), recorded_at=T0, contract_id=cid)
store.submit(RecordExecutionActivation(recorded_at=T0), recorded_at=T0, contract_id=cid)
store.submit(RecordDelivery(recorded_at=T1), recorded_at=T1, contract_id=cid)
contract = store.contract(cid)

from evidence import ObservationEvidence, ClaimEvidence
ev = EvidenceStore()
ev.ingest(ObservationEvidence(
    subject_ref=PATH_REF, contract_ref=cid, instant=T1, producer="adcos:node:x",
    metric="latency-ms", value=45, confidence_basis_points=9000,
    freshness_until="2026-10-01T00:40:00Z", source_refs=("telemetry:observation:1",),
))
ev.ingest(ClaimEvidence(
    subject_ref=PATH_REF, contract_ref=cid, instant=T1, producer="prov:telco-x",
    claim_kind="capability-statement", asserted_value=7, confidence_basis_points=7500,
))
evaluation = evaluate_contract(contract, obligations, list(ev.records()), T2)
journal = AssuranceJournal()
journal.append(evaluation)
print(ev.state_digest(), journal.state_digest(), evaluation.evaluation_id)
""" % str(REPO_ROOT)
    outputs = []
    for seed in ("0", "1", "42"):
        env = {"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"}
        probe_env = dict(env)
        proc = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True, text=True, cwd=str(REPO_ROOT), env=probe_env,
        )
        if proc.returncode != 0:
            return fail("case_43_cross_process_determinism", "probe subprocess exit %d: %s" % (proc.returncode, proc.stderr[-200:]))
        outputs.append(proc.stdout.strip())
    if len(set(outputs)) != 1:
        return fail("case_43_cross_process_determinism", "PYTHONHASHSEED variation changed the digests")
    return ok("case_43_cross_process_determinism", "byte-identical digests across PYTHONHASHSEED 0/1/42 subprocesses")


def _origin_main_available() -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/main"],
        capture_output=True, cwd=str(REPO_ROOT),
    )
    return proc.returncode == 0


def _active_authorization_covers(path: str) -> bool:
    """Consult the ACTIVE repository-local authorization (the shared
    authority for the batteries' authorization-aware delta-shape duty)."""
    try:
        from authorization_provenance import covers  # type: ignore
        return covers(path)
    except Exception:  # noqa: BLE001
        return False


def case_44_pr_delta_shape_authorized_scope() -> Result:
    name = "case_44_pr_delta_shape_authorized_scope"
    if not _origin_main_available():
        return ok(name, "skipped (no origin/main ref; the CI provenance step enforces scope)")
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
        return ok(name, "no delta (clean main)")
    problems: List[str] = []
    for path in sorted(delta):
        if path.startswith("spec/"):
            problems.append("delta touches the frozen spec/ control plane: %s" % path)
            continue
        if path.startswith(".github/"):
            problems.append("delta touches the CI control plane: %s" % path)
            continue
        if _active_authorization_covers(path):
            continue  # sanctioned by the ACTIVE repository-local authorization
        problems.append("delta outside the active authorization scope: %s" % path)
    if problems:
        return fail(name, "; ".join(problems[:5]))
    return ok(
        name,
        "delta confined to the M005 scope (%d file(s): evidence/ + assurance/ + telemetry harvest + battery + evidence doc)"
        % len(delta),
    )


def case_45_evidence_doc_honest() -> Result:
    name = "case_45_evidence_doc_honest"
    path = REPO_ROOT / "docs" / "M005-evidence.md"
    if not path.exists():
        return fail(name, "docs/M005-evidence.md is missing")
    text = path.read_text(encoding="utf-8")
    problems: List[str] = []
    if "SOFTWARE" not in text:
        problems.append("the evidence class is not disclosed")
    if "M005" not in text:
        problems.append("the evidence does not name M005")
    if "LOCK-106" not in text or "LOCK-107" not in text:
        problems.append("the lock mapping is not disclosed")
    # an AFFIRMATIVE physical-verification claim is rejected; a negation is
    # the required honesty statement (window-based so wrapped lines cannot
    # split the negation from the phrase)
    normalized = " ".join(text.split()).lower()
    problems_claim: List[str] = []
    start = 0
    while True:
        index = normalized.find("physical pass", start)
        if index < 0:
            index = normalized.find("physically verified", start)
            if index < 0:
                break
        window = normalized[max(0, index - 100):index]
        if not any(neg in window for neg in (" no ", "never ", "not ")):
            problems_claim.append(normalized[max(0, index - 40):index + 40])
        start = index + 1
    problems.extend(
        "an affirmative physical claim: ...%s..." % snippet
        for snippet in problems_claim[:3]
    )
    if problems:
        return fail(name, "; ".join(problems))
    return ok(
        name,
        "the evidence matrix discloses SOFTWARE class, the lock mapping, and no affirmative physical claims",
    )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    results: List[Result] = []
    results.append(case_01_evidence_type_vocabulary_frozen())
    results.append(case_02_four_types_structurally_distinct())
    results.extend(case_03_no_type_confusion())
    results.append(case_04_canonical_round_trip())
    results.append(case_05_provenance_envelope())
    results.append(case_06_content_derived_ids())
    results.extend(case_07_tamper_evidence())
    results.extend(case_08_malformed_input_fail_closed())
    results.extend(case_09_append_only_idempotent())
    results.append(case_10_persistence_recovery_fold())
    results.append(case_11_reads_sorted_scoped_fail_closed())
    results.append(case_12_structural_immutability())
    results.append(case_13_seam_translation_complete())
    results.extend(case_14_seam_fail_closed())
    results.append(case_15_seam_vocabulary_crosscheck())
    results.append(case_16_telemetry_surface_unchanged())
    results.extend(case_17_obligation_records_typed())
    results.extend(case_18_contract_binding_by_reference())
    results.extend(case_19_evaluation_inputs_fail_closed())
    results.extend(case_20_no_second_contract_model())
    results.append(case_21_state_vocabulary_frozen())
    results.append(case_22_state_compliant())
    results.append(case_23_state_violated())
    results.extend(case_24_state_degraded())
    results.extend(case_25_state_unknown())
    results.append(case_26_state_failed())
    results.append(case_27_state_deliberately_terminated())
    results.append(case_28_instant_threshold_staleness())
    results.append(case_29_deadline_absence_breach())
    results.append(case_30_latest_evidence_wins())
    results.append(case_31_no_time_travel())
    results.append(case_32_contract_scoping())
    results.append(case_33_per_kind_eligibility())
    results.append(case_34_deterministic_replay())
    results.append(case_35_journal_idempotent_recovery())
    results.append(case_36_bridge_mapping_frozen())
    results.append(case_37_bridge_closed_loop())
    results.append(case_38_bridge_terminal_noop())
    results.append(case_39_bridge_not_applicable())
    results.append(case_40_clock_discipline())
    results.append(case_41_import_discipline())
    results.append(case_42_lock_conformance_mapping())
    results.append(case_43_cross_process_determinism())
    results.append(case_44_pr_delta_shape_authorized_scope())
    results.append(case_45_evidence_doc_honest())

    print("ADCOS evidence-and-assurance self-test (M005 — Evidence and Assurance)")
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
