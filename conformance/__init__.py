"""ADCOS conformance suite -- WORK-032: protocol/adapter conformance.

A deterministic verifier and evidence classifier over the frozen
ADCOS contracts.  The suite composes the accepted authority
implementations (WORK-003/004/005/007/011/012/015/016/017) through
their public contracts, runs known-good and known-bad vectors, and
classifies conformance results into architecture conformance,
automated verification, and external evidence -- never minting
external interoperability evidence from in-repo vectors.

The suite is NOT a protocol authority: it defines no protocol
vocabulary, mints no authoritative protocol objects, and never
re-decides an authority verdict (see conformance/README.md).

Deterministic: injected instants only, no wall clock, no runtime
randomness, no network; results are reproducible across processes
and hash seeds by content digest.
"""

from __future__ import annotations

from conformance.evidence import (
    EXTERNAL_EVIDENCE_STATEMENT,
    assert_no_external_claim,
    build_evidence_report,
    coverage_matrix,
)
from conformance.harness import compare_outcomes, run_matrix, run_vector
from conformance.model import (
    AREA_AUTHORITY,
    ConformanceReport,
    ConformanceVector,
    EvidenceClass,
    ExpectedOutcome,
    ExternalEvidenceRecord,
    ObservedOutcome,
    Polarity,
    ReasonClass,
    REASON_VALUES,
    RegistryError,
    REQUIRED_AREAS,
    REQUIRED_DISCRIMINATION_TAGS,
    REQUIRED_NEGATIVE_TAGS,
    REQUIRED_RECOVERY_TAGS,
    VectorResult,
    Verdict,
)
from conformance.registry import VectorRegistry, build_default_registry
from conformance.serialization import (
    report_canonical_bytes,
    report_digest,
    report_from_mapping,
    report_to_dict,
)
from conformance.world import ConformanceWorld

__all__ = [
    # model
    "Verdict",
    "EvidenceClass",
    "Polarity",
    "ReasonClass",
    "REASON_VALUES",
    "ExpectedOutcome",
    "ObservedOutcome",
    "ConformanceVector",
    "VectorResult",
    "ExternalEvidenceRecord",
    "ConformanceReport",
    "RegistryError",
    "REQUIRED_AREAS",
    "AREA_AUTHORITY",
    "REQUIRED_NEGATIVE_TAGS",
    "REQUIRED_RECOVERY_TAGS",
    "REQUIRED_DISCRIMINATION_TAGS",
    # registry
    "VectorRegistry",
    "build_default_registry",
    # harness
    "run_vector",
    "run_matrix",
    "compare_outcomes",
    # world (fixture composition + sabotage surfaces)
    "ConformanceWorld",
    # evidence
    "build_evidence_report",
    "coverage_matrix",
    "assert_no_external_claim",
    "EXTERNAL_EVIDENCE_STATEMENT",
    # serialization
    "report_to_dict",
    "report_from_mapping",
    "report_canonical_bytes",
    "report_digest",
]

#: The frozen public API surface of the conformance family (checked by
#: tools/conformance_selftest.py).
API_SURFACE = frozenset(__all__)
