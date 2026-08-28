"""WORK-032 conformance suite -- canonical serialization.

Reports (and their evidence sections) serialize to canonical JSON and
round-trip byte-identically, so conformance evidence is reproducible
by content digest.
"""

from __future__ import annotations

from typing import Any, Dict

from protocol import CanonicalizationError, canonical_json_bytes

from conformance.model import (
    ConformanceReport,
    ConformanceVector,
    ExpectedOutcome,
    ExternalEvidenceRecord,
    ObservedOutcome,
    VectorResult,
    Verdict,
)

__all__ = [
    "report_to_dict",
    "report_from_mapping",
    "report_canonical_bytes",
    "report_digest",
]


def report_to_dict(report: ConformanceReport) -> Dict[str, Any]:
    return report.content_dict()


def _expected_from_mapping(data: Dict[str, Any]) -> ExpectedOutcome:
    return ExpectedOutcome(
        accepted=bool(data["accepted"]),
        result_classes=frozenset(data.get("result_classes") or ()),
    )


def _observed_from_mapping(data: Dict[str, Any]) -> ObservedOutcome:
    return ObservedOutcome(
        accepted=bool(data["accepted"]),
        result_class=str(data["result_class"]),
        detail=str(data["detail"]),
    )


def report_from_mapping(data: Dict[str, Any]) -> ConformanceReport:
    """Rebuild a report from its canonical mapping (fail closed)."""
    results = []
    for entry in data["results"]:
        results.append(VectorResult(
            vector_id=entry["vector_id"],
            area=entry["area"],
            authority=entry["authority"],
            contract=entry["contract"],
            invariant=entry["invariant"],
            polarity=entry["polarity"],
            expected=_expected_from_mapping(entry["expected"]),
            observed=_observed_from_mapping(entry["observed"]),
            verdict=Verdict(entry["verdict"]),
            reason_class=entry["reason_class"],
            tags=frozenset(entry.get("tags") or ()),
        ))
    external = [
        ExternalEvidenceRecord(
            source=entry["source"],
            scope=entry["scope"],
            description=entry["description"],
        )
        for entry in data.get("external_evidence") or ()
    ]
    report = ConformanceReport(
        results=tuple(results),
        external_evidence=tuple(external),
    )
    _validate_consistency(report, data)
    return report


def _validate_consistency(report: ConformanceReport,
                          data: Dict[str, Any]) -> None:
    if report.verdict.value != data["verdict"]:
        raise CanonicalizationError(
            "verdict mismatch: %s vs %s"
            % (report.verdict.value, data["verdict"])
        )
    if report.total != data["total"]:
        raise CanonicalizationError("total mismatch")
    if report.conformant != data["conformant"]:
        raise CanonicalizationError("conformant count mismatch")
    if report.nonconformant != data["nonconformant"]:
        raise CanonicalizationError("nonconformant count mismatch")


def report_canonical_bytes(report: ConformanceReport) -> bytes:
    return canonical_json_bytes(report_to_dict(report))


def report_digest(report: ConformanceReport) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(
        report_canonical_bytes(report)
    ).hexdigest()
