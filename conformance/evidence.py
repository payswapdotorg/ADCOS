"""WORK-032 conformance suite -- the evidence model.

Every conformance result classifies into exactly three evidence
classes (spec/prompts/WORK-032.md, "Evidence model"):

- ``architecture-conformance``: WHAT frozen contract surface the
  matrix covers (the coverage map: area -> vectors -> contracts ->
  owning authority);
- ``automated-verification``: WHAT the deterministic in-repo run
  observed (the report digest, counts, verdict);
- ``external-evidence``: evidence gathered OUTSIDE this repository
  (real independent implementations / environments).

In-repo vectors can NEVER mint external evidence: the suite's run
entry points accept no external records, and this module refuses to
classify automated vector results as external.  External records may
only be attached explicitly by an operator-side caller, and they are
kept strictly separate from automated verification.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from conformance.model import (
    AREA_AUTHORITY,
    ConformanceReport,
    ExternalEvidenceRecord,
    EvidenceClass,
    VectorResult,
    Verdict,
)

__all__ = [
    "build_evidence_report",
    "coverage_matrix",
    "EXTERNAL_EVIDENCE_STATEMENT",
]

#: The fixed statement recorded whenever no external evidence exists.
EXTERNAL_EVIDENCE_STATEMENT = (
    "No external interoperability evidence is established by in-repo "
    "conformance vectors. Automated verification and architecture "
    "conformance are recorded separately below; external evidence "
    "requires an independent implementation/environment supplied by "
    "the operator side."
)


def coverage_matrix(report: ConformanceReport) -> Dict[str, Dict[str, Any]]:
    """The architecture-conformance section: coverage per area.

    Maps each area to its owning authority, the vectors covering it,
    and the distinct contracts/invariants exercised -- i.e., WHICH
    frozen surface the matrix touches.
    """
    matrix: Dict[str, Dict[str, Any]] = {}
    for area in report.areas():
        results = report.results_for_area(area)
        matrix[area] = {
            "authority": AREA_AUTHORITY.get(area, ""),
            "evidence_class": EvidenceClass.ARCHITECTURE_CONFORMANCE.value,
            "vector_count": len(results),
            "vectors": [r.vector_id for r in results],
            "invariants": sorted({r.invariant for r in results}),
            "positive": sum(
                1 for r in results if r.polarity == "positive"
            ),
            "negative": sum(
                1 for r in results if r.polarity == "negative"
            ),
        }
    return matrix


def build_evidence_report(
    report: ConformanceReport,
    *,
    external: Tuple[ExternalEvidenceRecord, ...] = (),
) -> Dict[str, Any]:
    """Assemble the three-class evidence report (deterministic)."""
    if report.external_evidence and external:
        raise ValueError(
            "external evidence supplied twice; the report already carries "
            "operator-supplied records"
        )
    records = external or report.external_evidence
    automated: Dict[str, object] = {
        "evidence_class": EvidenceClass.AUTOMATED_VERIFICATION.value,
        "verdict": report.verdict.value,
        "total_vectors": report.total,
        "conformant": report.conformant,
        "nonconformant": report.nonconformant,
        "positive_vectors": report.positive_count,
        "negative_vectors": report.negative_count,
        "scope": (
            "in-repo automated conformance vectors against the accepted "
            "authority implementations"
        ),
    }
    external_section: Dict[str, object] = {
        "evidence_class": EvidenceClass.EXTERNAL_EVIDENCE.value,
        "records": [record.content_dict() for record in records],
        "statement": EXTERNAL_EVIDENCE_STATEMENT
        if not records
        else "operator-supplied external evidence records",
    }
    return {
        "architecture_conformance": coverage_matrix(report),
        "automated_verification": automated,
        "external_evidence": external_section,
    }


def assert_no_external_claim(report: ConformanceReport) -> None:
    """Fail closed if any automated result claims external evidence.

    Vector results are automated verification by construction; this
    guard makes the separation mechanically checkable.
    """
    for result in report.results:  # type: VectorResult
        claimed = getattr(result, "evidence_class", None)
        if claimed is not None and claimed == \
                EvidenceClass.EXTERNAL_EVIDENCE.value:
            raise ValueError(
                "vector %r claimed external evidence; automated results "
                "can never establish external interoperability"
                % result.vector_id
            )
