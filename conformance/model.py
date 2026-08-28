"""WORK-032 conformance suite -- frozen vocabularies and data model.

This module defines the conformance-suite vocabulary: verdicts, evidence
classes, vector polarities, stable reason classes, and the immutable
vector/result/report dataclasses.  It deliberately contains no protocol
semantics: the suite is a verifier and evidence classifier, never a
second protocol authority (spec/prompts/WORK-032.md, authority boundary).

Design invariants (frozen):

- every vector carries an explicit expected outcome AND the authority /
  contract whose frozen semantics determine that outcome;
- ``integrity != provenance``: a structurally valid artifact with a
  forged identity-bearing digest, signature, or event identifier is a
  negative vector whenever provenance is authoritative;
- results classify into exactly three evidence classes; in-repo vectors
  can never mint external evidence;
- diagnostics are non-secret and identify contract, invariant, stable
  reason/result class, and non-secret canonical identifiers only.

Determinism: no wall clock, no language/runtime randomness, no network.
All identifiers are plain harness labels (``W032-CNF-*``); the suite
mints no authoritative protocol objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, FrozenSet, List, Mapping, Tuple

__all__ = [
    "Verdict",
    "EvidenceClass",
    "Polarity",
    "ReasonClass",
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
    "KNOWN_TAGS",
    "REASON_VALUES",
]


# ---------------------------------------------------------------------------
# Frozen vocabularies
# ---------------------------------------------------------------------------


class Verdict(Enum):
    """Per-vector and overall conformance verdict (never generic pass)."""

    CONFORMANT = "conformant"
    NONCONFORMANT = "nonconformant"


class EvidenceClass(Enum):
    """The three evidence classes required by the WORK-032 evidence model."""

    ARCHITECTURE_CONFORMANCE = "architecture-conformance"
    AUTOMATED_VERIFICATION = "automated-verification"
    EXTERNAL_EVIDENCE = "external-evidence"


class Polarity(Enum):
    """Vector polarity: known-good (positive) or known-bad (negative)."""

    POSITIVE = "positive"
    NEGATIVE = "negative"


#: Stable reason classes for vector results (frozen vocabulary).
REASON_VALUES: FrozenSet[str] = frozenset(
    {
        "conformant",
        "outcome-mismatch",
        "result-class-mismatch",
        "unexpected-exception",
        "fixture-error",
    }
)


class ReasonClass:
    """Namespace of stable reason-class constants (see ``REASON_VALUES``)."""

    CONFORMANT = "conformant"
    OUTCOME_MISMATCH = "outcome-mismatch"
    RESULT_CLASS_MISMATCH = "result-class-mismatch"
    UNEXPECTED_EXCEPTION = "unexpected-exception"
    FIXTURE_ERROR = "fixture-error"


#: The required conformance-matrix areas (spec/prompts/WORK-032.md,
#: "Required coverage").  The multipath/session-binding bullet rides the
#: session area: W012's frozen contract owns the session-path binding
#: surface (reconnect records old+new path ids).  W013 (multipath) is NOT
#: a declared W032 dependency and is therefore never imported.
REQUIRED_AREAS: Tuple[str, ...] = (
    "envelope",
    "identity",
    "capabilities",
    "topology",
    "routing",
    "sessions",
    "federation",
    "adapter",
    "transport",
    "structure",
)

#: The authority whose frozen semantics determine each area's outcomes.
AREA_AUTHORITY: Mapping[str, str] = {
    "envelope": "WORK-003",
    "identity": "WORK-004",
    "capabilities": "WORK-005",
    "topology": "WORK-007",
    "routing": "WORK-011",
    "sessions": "WORK-012",
    "federation": "WORK-015",
    "adapter": "WORK-016",
    "transport": "WORK-017",
    "structure": "WORK-032",
}

#: Negative/security categories that must each be covered by at least one
#: negative vector (spec/prompts/WORK-032.md, "Negative/security
#: requirements").
REQUIRED_NEGATIVE_TAGS: Tuple[str, ...] = (
    "negative:malformed-required-fields",
    "negative:invalid-versions",
    "negative:canonicalization-mismatch",
    "negative:expired-future-data",
    "negative:replay",
    "negative:forged-provenance",
    "negative:capability-inflation",
    "negative:topology-poisoning",
    "negative:binding-violation",
    "negative:scope-escalation",
    "negative:transport-downgrade",
    "negative:unknown-extensions",
    "negative:provider-exception",
    "negative:hidden-authority-access",
    "negative:forbidden-imports",
)

#: Failure/recovery categories that must each be covered ("Failure/recovery").
REQUIRED_RECOVERY_TAGS: Tuple[str, ...] = (
    "recovery:restart",
    "recovery:stale-future",
    "recovery:version-conflict",
    "recovery:provider-exception",
    "recovery:cleanup-failure",
    "recovery:replay-state",
    "recovery:cross-authority-injection",
)

#: Security properties requiring discriminating treatment (vulnerable
#: behavior must fail, corrected behavior must pass).  The discriminating
#: proofs themselves live in tools/conformance_selftest.py as
#: sabotaged-candidate runs against these same vectors.
REQUIRED_DISCRIMINATION_TAGS: Tuple[str, ...] = (
    "discriminating:provenance",
    "discriminating:replay",
    "discriminating:downgrade",
    "discriminating:capability-inflation",
    "discriminating:authority-boundary",
    "discriminating:adapter-isolation",
    "discriminating:forbidden-dependency",
)

#: The complete frozen tag vocabulary (coverage tags are asserted against
#: this set at registration time).
KNOWN_TAGS: FrozenSet[str] = frozenset(
    set(REQUIRED_NEGATIVE_TAGS)
    | set(REQUIRED_RECOVERY_TAGS)
    | set(REQUIRED_DISCRIMINATION_TAGS)
    | {
        "positive:core-behavior",
        "positive:determinism",
        "matrix:multipath-binding",
        "matrix:envelope-interop",
        "diagnostics:secret-free",
    }
)


class RegistryError(ValueError):
    """Raised when the vector registry is inconsistent (fail closed)."""


# ---------------------------------------------------------------------------
# Outcomes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExpectedOutcome:
    """The frozen expected outcome of one conformance vector.

    ``accepted`` is the authoritative acceptance decision the contract
    must produce.  ``result_classes`` is the optional set of stable
    result-class values (classification constants, reason codes, or
    exception codes) the observed outcome must carry; empty means "any
    class" (used only where the frozen contract deliberately does not
    pin a single class).
    """

    accepted: bool
    result_classes: FrozenSet[str] = frozenset()

    def content_dict(self) -> "dict[str, Any]":
        return {
            "accepted": self.accepted,
            "result_classes": tuple(sorted(self.result_classes)),
        }


@dataclass(frozen=True)
class ObservedOutcome:
    """What the candidate actually did (mapped by the vector itself).

    ``result_class`` is a stable machine-readable class: an authority
    reason code, classification constant, or exception code -- never a
    generic true/false.  ``detail`` is non-secret diagnostics.
    """

    accepted: bool
    result_class: str
    detail: str

    def content_dict(self) -> "dict[str, Any]":
        return {
            "accepted": self.accepted,
            "result_class": self.result_class,
            "detail": self.detail,
        }


# ---------------------------------------------------------------------------
# Vectors and results
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConformanceVector:
    """One conformance vector against one frozen contract interaction.

    ``execute`` receives a freshly built :class:`conformance.world.
    ConformanceWorld` (isolated per vector; the harness never shares
    mutable state across vectors) and maps the observed authority
    behavior to an :class:`ObservedOutcome`.  The vector -- never the
    harness -- defines what "observed acceptance" means for its
    contract, so no suite-side semantics shadow the authority.
    """

    vector_id: str
    area: str
    polarity: str
    authority: str
    contract: str
    invariant: str
    description: str
    expected: ExpectedOutcome
    execute: Callable[[Any], ObservedOutcome]
    tags: FrozenSet[str] = frozenset()

    def content_dict(self) -> "dict[str, Any]":
        return {
            "vector_id": self.vector_id,
            "area": self.area,
            "polarity": self.polarity,
            "authority": self.authority,
            "contract": self.contract,
            "invariant": self.invariant,
            "description": self.description,
            "expected": self.expected.content_dict(),
            "tags": tuple(sorted(self.tags)),
        }


@dataclass(frozen=True)
class VectorResult:
    """The result of running one vector against one candidate world."""

    vector_id: str
    area: str
    authority: str
    contract: str
    invariant: str
    polarity: str
    expected: ExpectedOutcome
    observed: ObservedOutcome
    verdict: Verdict
    reason_class: str
    tags: FrozenSet[str]

    def content_dict(self) -> "dict[str, Any]":
        return {
            "vector_id": self.vector_id,
            "area": self.area,
            "authority": self.authority,
            "contract": self.contract,
            "invariant": self.invariant,
            "polarity": self.polarity,
            "expected": self.expected.content_dict(),
            "observed": self.observed.content_dict(),
            "verdict": self.verdict.value,
            "reason_class": self.reason_class,
            "tags": tuple(sorted(self.tags)),
        }


@dataclass(frozen=True)
class ExternalEvidenceRecord:
    """An explicitly supplied external-evidence record.

    External evidence can ONLY exist outside the in-repo suite (a real
    independent implementation / environment).  The suite never mints
    these from vectors; an operator-side caller may attach them
    explicitly, and the evidence report keeps them strictly separate
    from automated verification.
    """

    source: str
    scope: str
    description: str

    def content_dict(self) -> "dict[str, Any]":
        return {
            "source": self.source,
            "scope": self.scope,
            "description": self.description,
        }


@dataclass(frozen=True)
class ConformanceReport:
    """Deterministic result of running the conformance matrix.

    Results are stored in canonical (vector-id sorted) order regardless
    of registration order.  No wall-clock timestamps: reproducibility is
    by content digest.
    """

    results: Tuple[VectorResult, ...]
    external_evidence: Tuple[ExternalEvidenceRecord, ...] = ()

    @property
    def verdict(self) -> Verdict:
        if any(r.verdict is Verdict.NONCONFORMANT for r in self.results):
            return Verdict.NONCONFORMANT
        return Verdict.CONFORMANT

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def conformant(self) -> int:
        return sum(1 for r in self.results if r.verdict is Verdict.CONFORMANT)

    @property
    def nonconformant(self) -> int:
        return sum(1 for r in self.results if r.verdict is Verdict.NONCONFORMANT)

    @property
    def positive_count(self) -> int:
        return sum(1 for r in self.results if r.polarity == Polarity.POSITIVE.value)

    @property
    def negative_count(self) -> int:
        return sum(1 for r in self.results if r.polarity == Polarity.NEGATIVE.value)

    def results_for_area(self, area: str) -> Tuple[VectorResult, ...]:
        return tuple(r for r in self.results if r.area == area)

    def areas(self) -> Tuple[str, ...]:
        seen: List[str] = []
        for r in self.results:
            if r.area not in seen:
                seen.append(r.area)
        return tuple(sorted(seen))

    def content_dict(self) -> "dict[str, Any]":
        return {
            "results": [r.content_dict() for r in self.results],
            "external_evidence": [e.content_dict() for e in self.external_evidence],
            "verdict": self.verdict.value,
            "total": self.total,
            "conformant": self.conformant,
            "nonconformant": self.nonconformant,
        }

    def nonconformant_results(self) -> Tuple[VectorResult, ...]:
        return tuple(r for r in self.results if r.verdict is Verdict.NONCONFORMANT)
