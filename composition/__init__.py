"""ADCOS composition package (WORK-054): the System Composition
Conformance layer.

WORK-054 is strictly a CONFORMANCE / ORCHESTRATION / EVIDENCE layer
over the accepted authorities of the commercial connectivity
control plane.  It composes the existing Work Items through their
public module boundaries and produces deterministic, replayable
conformance evidence for the canonical chain

    intent -> offer -> eligibility -> reservation/lease ->
    candidate selection -> NetworkPath validation -> containment ->
    session -> delivered traffic -> usage -> BILLABLE_FINAL ->
    allocation -> external payment reference -> reconciliation

without creating a second authority.

Frozen authority rules (the WORK-054 contract, DEC-0085/DEC-0086):

- This package creates NO canonical business state store, NO
  connectivity state store, NO payment/eligibility/marketplace/
  developer-platform/client authority, NO session/path/routing/
  transport/policy authority, and NO substitute for an absent
  authority.  Every composed object is an instance of an EXISTING
  accepted authority constructed through its own public
  constructor over its own injected seams (the W032
  ``ConformanceWorld`` precedent); every cross-authority input is
  an immutable caller-built snapshot derived from PUBLIC reads
  only (the W051/W052/W053/W044 injection contracts).
- WORK-048 (Provider Connectivity Sharing Runtime) is historically
  accepted but ``accepted-not-restored`` on the current mainline:
  the sharing runtime package is absent.  This package DETECTS the
  absence explicitly and FAILS CLOSED wherever W048 authority is
  required (the containment edge of the chain and every
  containment-dependent admission).  It never restores, recreates,
  mocks, or silently substitutes W048, and the strict full-chain
  verdict never counts the absence as a passing production
  composition.
- WORK-046 (Developer API/SDK/Webhook platform) is accepted but
  its restored artifacts carry an inherited import defect on the
  current mainline (a stale cross-import against the evolved
  usage surface).  The defect is detected, recorded, and
  disclosed; it is never repaired here and never silently
  bypassed.  API/webhook observation classification is proven
  through the RECEIVING authorities' public boundaries (W052
  usage kind table, W044 callback observation fold, W053 external
  reference kinds), which exist and are importable.
- W040 and EVID-007/EVID-008 remain independent physical
  obligations: this package mints SOFTWARE evidence only and can
  never close physical evidence.

Determinism: no wall clock, no randomness, no UUIDs, no network,
no filesystem writes.  Every injected clock is the WORK-033
``StepClock``/``FixedClock`` seam; every digest is the WORK-003
canonical-JSON SHA-256 convention; every report is byte-stable
under PYTHONHASHSEED variation.
"""

from __future__ import annotations

from .authority import (
    AUTHORITY_PROBES,
    AuthorityAvailability,
    AuthorityProbe,
    W046_DEFECT_DETAIL,
    W048_ABSENT_DETAIL,
    probe_authorities,
    w048_runtime_absent,
)
from .chain import (
    CHAIN_EDGES,
    CHAIN_STAGE_NAMES,
    EdgeOutcome,
    EdgeSpec,
    NEGATIVE_PROOF_STATEMENTS,
    OutcomeReason,
    StageOutcome,
    CompositionTrace,
    chain_edge,
)
from .evidence import (
    EVIDENCE_CLASS_SOFTWARE,
    CompositionEvidenceError,
    SoftwareEvidenceRecord,
    build_evidence_document,
    classify_evidence,
    composition_digest,
    physical_obligations_open,
)
from .world import (
    CompositionWorld,
    build_allocation_evidence_index,
    build_delivery_evidence,
    build_payment_snapshot,
    build_reference_index,
    build_usage_evidence_index,
    derive_tariff,
)
from .orchestrator import (
    ScenarioStream,
    compose_scenario_stream,
    run_available_segments,
    run_full_chain,
    segment_conformance_allowed,
)

__all__ = [
    # authority availability
    "AUTHORITY_PROBES",
    "AuthorityAvailability",
    "AuthorityProbe",
    "W046_DEFECT_DETAIL",
    "W048_ABSENT_DETAIL",
    "probe_authorities",
    "w048_runtime_absent",
    # chain model
    "CHAIN_EDGES",
    "CHAIN_STAGE_NAMES",
    "EdgeOutcome",
    "EdgeSpec",
    "NEGATIVE_PROOF_STATEMENTS",
    "OutcomeReason",
    "StageOutcome",
    "CompositionTrace",
    "chain_edge",
    # evidence discipline
    "EVIDENCE_CLASS_SOFTWARE",
    "CompositionEvidenceError",
    "SoftwareEvidenceRecord",
    "build_evidence_document",
    "classify_evidence",
    "composition_digest",
    "physical_obligations_open",
    # composed world
    "CompositionWorld",
    "build_allocation_evidence_index",
    "build_delivery_evidence",
    "build_payment_snapshot",
    "build_reference_index",
    "build_usage_evidence_index",
    "derive_tariff",
    # orchestration
    "ScenarioStream",
    "compose_scenario_stream",
    "run_available_segments",
    "run_full_chain",
    "segment_conformance_allowed",
]
