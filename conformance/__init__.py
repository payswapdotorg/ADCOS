"""ADCOS conformance suite -- WORK-032: protocol/adapter conformance,
extended by WORK-055: protocol production conformance (R3).

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

WORK-055 additions (additive/hardening-only, frozen WORK-032
behavior preserved): the production canonicalization profile
(conformance.profile), the golden-vector corpus and verifier
(conformance.golden, conformance/vectors/data/), and the wire vector
module (conformance/vectors/wire.py).  The WORK-029 surfaces are
consumed from tools/conformance_selftest.py -- the sanctioned
composition root -- never from this family (the frozen dependency
graph carries no W055 family-level edge).

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
from conformance.golden import (
    CORPUS_CATEGORIES,
    CATEGORY_AUTHORITY,
    CorpusError,
    GoldenCorpusEntry,
    GoldenVectorResult,
    OUTCOME_CLASSES,
    corpus_digest,
    corpus_from_entries,
    corpus_vector_ids,
    load_corpus,
    verify_corpus,
    verify_entry,
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
    W055_REQUIRED_DISCRIMINATION_TAGS,
    W055_REQUIRED_NEGATIVE_TAGS,
)
from conformance.profile import (
    CANONICALIZATION_PROFILE_ID,
    CANONICALIZATION_PROFILE_RULES,
    PROFILE_RULE_IDS,
    profile_digest,
    profile_rule_sources,
    profile_statement,
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
    # golden corpus (WORK-055)
    "CORPUS_CATEGORIES",
    "CATEGORY_AUTHORITY",
    "OUTCOME_CLASSES",
    "CorpusError",
    "GoldenCorpusEntry",
    "GoldenVectorResult",
    "load_corpus",
    "verify_corpus",
    "verify_entry",
    "corpus_from_entries",
    "corpus_vector_ids",
    "corpus_digest",
    # canonicalization profile (WORK-055)
    "CANONICALIZATION_PROFILE_ID",
    "CANONICALIZATION_PROFILE_RULES",
    "PROFILE_RULE_IDS",
    "profile_statement",
    "profile_digest",
    "profile_rule_sources",
]

#: The frozen public API surface of the conformance family (checked by
#: tools/conformance_selftest.py).  WORK-055 extended the surface
#: additively (the golden-corpus and profile sections); every WORK-032
#: symbol is unchanged.
API_SURFACE = frozenset(__all__)
