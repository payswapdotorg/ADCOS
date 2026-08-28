"""WORK-032 conformance suite -- the deterministic execution harness.

The harness runs one vector against one freshly built candidate world,
maps the observed outcome against the vector's frozen expectation, and
classifies the result with a stable reason class.  It never defines
protocol semantics: the vector maps observation, the expectation
decides conformance.

Fail-closed rules:

- an exception ESCAPING a vector's execute (not caught by the vector's
  own expected-error mapping) is an unmodeled behavior -- the harness
  classifies it NONCONFORMANT with reason ``unexpected-exception``
  rather than guessing;
- no outcome is ever collapsed into a generic pass/fail: every result
  carries the authority's own stable result class.
"""

from __future__ import annotations

from typing import Callable, Iterable, Optional, Tuple

from conformance.model import (
    AREA_AUTHORITY,
    ConformanceReport,
    ConformanceVector,
    ExpectedOutcome,
    ObservedOutcome,
    ReasonClass,
    VectorResult,
    Verdict,
)
from conformance.world import ConformanceWorld

__all__ = ["run_vector", "run_matrix", "compare_outcomes"]


def compare_outcomes(expected: ExpectedOutcome,
                     observed: ObservedOutcome) -> Tuple[Verdict, str]:
    """Compare an observed outcome with the frozen expectation.

    Returns ``(verdict, reason_class)``.
    """
    if observed.accepted != expected.accepted:
        return (
            Verdict.NONCONFORMANT,
            ReasonClass.OUTCOME_MISMATCH,
        )
    if expected.result_classes and observed.result_class not in \
            expected.result_classes:
        return (
            Verdict.NONCONFORMANT,
            ReasonClass.RESULT_CLASS_MISMATCH,
        )
    return Verdict.CONFORMANT, ReasonClass.CONFORMANT


def run_vector(vector: ConformanceVector,
               world: ConformanceWorld) -> VectorResult:
    """Run one vector against one candidate world (fail closed)."""
    try:
        observed = vector.execute(world)
    except Exception as error:  # noqa: BLE001 - fail-closed boundary
        observed = ObservedOutcome(
            accepted=False,
            result_class=ReasonClass.UNEXPECTED_EXCEPTION,
            detail="%s: %s" % (type(error).__name__, error),
        )
    verdict, reason = compare_outcomes(vector.expected, observed)
    return VectorResult(
        vector_id=vector.vector_id,
        area=vector.area,
        authority=vector.authority,
        contract=vector.contract,
        invariant=vector.invariant,
        polarity=vector.polarity,
        expected=vector.expected,
        observed=observed,
        verdict=verdict,
        reason_class=reason,
        tags=vector.tags,
    )


def run_matrix(
    vectors: Iterable[ConformanceVector],
    world_factory: Callable[[], ConformanceWorld],
    *,
    progress: Optional[Callable[[str], None]] = None,
) -> ConformanceReport:
    """Run the conformance matrix in canonical (vector-id) order.

    One fresh world per vector: vectors never share mutable state, so
    results are independent of ordering and reproducible across
    processes.
    """
    ordered = tuple(sorted(vectors, key=lambda v: v.vector_id))
    results = []
    for vector in ordered:
        if progress is not None:
            progress(vector.vector_id)
        results.append(run_vector(vector, world_factory()))
    return ConformanceReport(results=tuple(results))
