"""WORK-055 production conformance layer -- the golden-vector corpus.

A deterministic corpus of golden vectors that pin the frozen
protocol's production-relevant behavior with byte-exact expectations:

- canonical encoding (accepted encodings -> exact canonical bytes,
  exact compact-CBOR bytes);
- encoding convergence (differently formatted encodings of one
  semantic value -> the pinned canonical form);
- signature-input material (exact covered-byte basis per envelope);
- codec cross-agreement (the JSON and compact codecs represent the
  same value semantically).

The WORK-029 surfaces (version negotiation, schema migration) are
covered from tools/conformance_selftest.py -- the sanctioned
composition root -- rather than from this family, because the frozen
dependency graph and the WORK-029 family's own import discipline
(tools/upgrade_selftest.py case_33) do not carry a W055 family-level
DAG edge; amending them is Architect-owned (see
docs/WORK-055-handoff.md).

Authority discipline (frozen):

- The corpus is TEST DATA for behavior ALREADY REQUIRED by the frozen
  protocol (spec/schemas/protocol.json, protocol/, upgrade/).  It is
  never a protocol definition and never authoritative over the frozen
  specification: every expected value is a recording of what the
  genuine frozen authority produces, attributed to that authority.
- The verifier only CALLS the frozen public APIs
  (protocol.canonicalization/codec_cbor/envelope/signature,
  upgrade.compatibility/migrations) and compares observed with
  recorded; it never re-decides an outcome.
- The migration corpus rides a fixture schema line (a harness label,
  never a real artifact id) whose steps are pure functions supplied
  to the genuine WORK-029 registry.

Determinism: files are loaded in sorted name order, parsed with
duplicate-key rejection, asserted to be in repository canonical form,
validated against the frozen corpus vocabulary, and verified in
canonical (vector-id) order.  The corpus digest is byte-stable across
runs, subprocesses, and hash seeds.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, List, Mapping, Optional, Tuple

from protocol import (
    CanonicalizationError,
    cbor_bytes,
    canonical_json_bytes,
    envelope_from_mapping,
    signature_input_bytes,
)
from protocol.codec_cbor import cbor_value

__all__ = [
    "GoldenCorpusEntry",
    "GoldenVectorResult",
    "CorpusError",
    "CORPUS_CATEGORIES",
    "CATEGORY_AUTHORITY",
    "OUTCOME_CLASSES",
    "load_corpus",
    "corpus_from_entries",
    "verify_corpus",
    "verify_entry",
    "corpus_digest",
    "corpus_vector_ids",
]


class CorpusError(ValueError):
    """Raised when the golden corpus is inconsistent (fail closed)."""


#: The frozen corpus category vocabulary.  Each category's outcomes are
#: decided by the authority named in CATEGORY_AUTHORITY.
CORPUS_CATEGORIES: Tuple[str, ...] = (
    "canonical-encoding",
    "encoding-convergence",
    "signature-input",
    "codec-cross-agreement",
)

#: The owning frozen authority for each corpus category.
CATEGORY_AUTHORITY: Dict[str, str] = {
    "canonical-encoding": "WORK-003",
    "encoding-convergence": "WORK-003",
    "signature-input": "WORK-003",
    "codec-cross-agreement": "WORK-003",
}

#: The stable outcome-class vocabulary: the WORK-003 Classification
#: values for compatibility dispositions, loaded from the frozen
#: authority, never restated locally.
def _outcome_classes() -> FrozenSet[str]:
    from protocol.versioning import Classification

    return frozenset(Classification.ALL_VALUES)


OUTCOME_CLASSES: FrozenSet[str] = _outcome_classes()

_CORPUS_DIR = Path(__file__).resolve().parent / "vectors" / "data"

#: The migration fixture schema line: a harness label, never a real
#: artifact identifier.  The registry (the WORK-029 authority) owns the
#: walk; these fixture step functions are pure caller-supplied inputs.
FIXTURE_SCHEMA_ID = "conformance.fixture-state"


@dataclass(frozen=True)
class GoldenCorpusEntry:
    """One golden vector: test data plus its frozen expectation."""

    vector_id: str
    description: str
    category: str
    authority: str
    contract: str
    outcome_class: str
    invariant: str
    input: Any
    input_equivalent: Optional[Any]
    expected: Mapping[str, Any]

    def content_dict(self) -> Dict[str, Any]:
        return {
            "vector_id": self.vector_id,
            "description": self.description,
            "category": self.category,
            "authority": self.authority,
            "contract": self.contract,
            "outcome_class": self.outcome_class,
            "invariant": self.invariant,
            "input": self.input,
            "input_equivalent": self.input_equivalent,
            "expected": dict(self.expected),
        }


@dataclass(frozen=True)
class GoldenVectorResult:
    """The verification outcome of one corpus entry."""

    vector_id: str
    category: str
    authority: str
    outcome_class: str
    verified: bool
    detail: str

    def content_dict(self) -> Dict[str, Any]:
        return {
            "vector_id": self.vector_id,
            "category": self.category,
            "authority": self.authority,
            "outcome_class": self.outcome_class,
            "verified": self.verified,
            "detail": self.detail,
        }


# ---------------------------------------------------------------------------
# Corpus loading
# ---------------------------------------------------------------------------


def _reject_duplicate_keys(pairs) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CorpusError("duplicate key %r in corpus file" % key)
        result[key] = value
    return result


def _repository_canonical_bytes(value: Any) -> bytes:
    """Repository canonical form for corpus data files (sorted keys,
    2-space indent, trailing newline -- the spec/schemas convention)."""
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _entry_from_mapping(data: Mapping[str, Any], source: str) -> GoldenCorpusEntry:
    try:
        entry = GoldenCorpusEntry(
            vector_id=data["vector_id"],
            description=data["description"],
            category=data["category"],
            authority=data["authority"],
            contract=data["contract"],
            outcome_class=data["outcome_class"],
            invariant=data["invariant"],
            input=data["input"],
            input_equivalent=data.get("input_equivalent"),
            expected=data["expected"],
        )
    except KeyError as error:
        raise CorpusError("%s is missing required field %s" % (source, error)) from error
    if entry.category not in CORPUS_CATEGORIES:
        raise CorpusError(
            "%s has unknown category %r" % (source, entry.category)
        )
    if entry.authority != CATEGORY_AUTHORITY[entry.category]:
        raise CorpusError(
            "%s category %r is not owned by authority %r"
            % (source, entry.category, entry.authority)
        )
    if entry.outcome_class not in OUTCOME_CLASSES:
        raise CorpusError(
            "%s outcome_class %r is outside the frozen vocabulary"
            % (source, entry.outcome_class)
        )
    if not entry.vector_id.startswith("W055-GLD-"):
        raise CorpusError(
            "%s vector_id %r is outside the W055 golden-vector namespace"
            % (source, entry.vector_id)
        )
    if entry.category == "encoding-convergence":
        if not isinstance(entry.input, str):
            raise CorpusError(
                "%s convergence vector input must be raw JSON text" % source
            )
        if "canonical_json" not in entry.expected:
            raise CorpusError(
                "%s convergence vector requires expected.canonical_json" % source
            )
    return entry


def _load_directory(directory: Path) -> Tuple[GoldenCorpusEntry, ...]:
    if not directory.is_dir():
        raise CorpusError("missing corpus directory: %s" % directory)
    entries: List[GoldenCorpusEntry] = []
    seen: Dict[str, str] = {}
    for path in sorted(directory.glob("*.json")):
        raw = path.read_bytes()
        try:
            data = json.loads(
                raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CorpusError("%s is not valid JSON: %s" % (path.name, error)) from error
        if not isinstance(data, dict):
            raise CorpusError("%s must contain a JSON object" % path.name)
        if raw != _repository_canonical_bytes(data):
            raise CorpusError("%s is not in canonical form" % path.name)
        entry = _entry_from_mapping(data, path.name)
        if entry.vector_id in seen:
            raise CorpusError(
                "duplicate corpus vector id %s (%s and %s)"
                % (entry.vector_id, seen[entry.vector_id], path.name)
            )
        seen[entry.vector_id] = path.name
        entries.append(entry)
    if not entries:
        raise CorpusError("no golden vectors found in %s" % directory)
    return tuple(sorted(entries, key=lambda e: e.vector_id))


def load_corpus(directory: Optional[Path] = None) -> Tuple[GoldenCorpusEntry, ...]:
    """Load the golden corpus in canonical (vector-id sorted) order."""
    return _load_directory(directory or _CORPUS_DIR)


def corpus_from_entries(
    entries: Tuple[GoldenCorpusEntry, ...],
) -> Tuple[GoldenCorpusEntry, ...]:
    """Canonicalize an entry sequence (sorted by vector id).

    Registration/file order never affects the corpus: the canonical
    order is the sorted vector-id order (mirrors the W032 registry
    discipline).
    """
    return tuple(sorted(entries, key=lambda e: e.vector_id))


def corpus_vector_ids(corpus: Tuple[GoldenCorpusEntry, ...]) -> Tuple[str, ...]:
    return tuple(entry.vector_id for entry in corpus)


# ---------------------------------------------------------------------------
# Verification (calls frozen public APIs; compares observed vs recorded)
# ---------------------------------------------------------------------------


def _result(entry: GoldenCorpusEntry, verified: bool, detail: str) -> GoldenVectorResult:
    return GoldenVectorResult(
        vector_id=entry.vector_id,
        category=entry.category,
        authority=entry.authority,
        outcome_class=entry.outcome_class,
        verified=verified,
        detail=detail,
    )


def _verify_canonical_encoding(entry: GoldenCorpusEntry) -> GoldenVectorResult:
    value = entry.input
    expected_json = entry.expected.get("canonical_json")
    expected_cbor = entry.expected.get("canonical_cbor_hex")
    try:
        observed_json = canonical_json_bytes(value)
        observed_cbor = cbor_bytes(value)
    except CanonicalizationError as error:
        return _result(entry, False, "canonicalization rejected: %s" % error)
    if expected_json is None or observed_json != expected_json.encode("utf-8"):
        return _result(
            entry, False,
            "canonical JSON mismatch: %r vs %r"
            % (observed_json[:96], (expected_json or "")[:96]),
        )
    if expected_cbor is None or observed_cbor != bytes.fromhex(expected_cbor):
        return _result(entry, False, "canonical CBOR mismatch")
    return _result(entry, True, "canonical JSON and CBOR bytes exact")


def _verify_convergence(entry: GoldenCorpusEntry) -> GoldenVectorResult:
    """Raw-text convergence: differently formatted encodings of one
    semantic value (key order, whitespace, \\u escape forms) must
    converge to exactly the pinned canonical bytes."""
    expected_json = entry.expected.get("canonical_json")
    try:
        value = json.loads(
            entry.input, object_pairs_hook=_reject_duplicate_keys
        )
        observed = canonical_json_bytes(value)
    except (json.JSONDecodeError, CorpusError) as error:
        return _result(entry, False, "input text rejected: %s" % error)
    except CanonicalizationError as error:
        return _result(entry, False, "canonicalization rejected: %s" % error)
    if expected_json is None or observed != expected_json.encode("utf-8"):
        return _result(
            entry, False,
            "converged bytes differ from the recorded golden form: %r"
            % observed[:96],
        )
    return _result(
        entry, True,
        "differently formatted input converges to the pinned canonical form",
    )


def _verify_signature_input(entry: GoldenCorpusEntry) -> GoldenVectorResult:
    expected = entry.expected.get("signature_input_json")
    try:
        envelope = envelope_from_mapping(entry.input)
    except Exception as error:  # EnvelopeError: the authority's verdict
        return _result(entry, False, "envelope rejected: %s" % error)
    observed = signature_input_bytes(envelope)
    if expected is None or observed != expected.encode("utf-8"):
        return _result(
            entry, False,
            "signature-input mismatch: %r vs %r"
            % (observed[:96], (expected or "").encode("utf-8")[:96]),
        )
    return _result(entry, True, "covered-byte basis exact")


def _verify_codec_cross(entry: GoldenCorpusEntry) -> GoldenVectorResult:
    value = entry.input
    expected_json = entry.expected.get("canonical_json")
    expected_cbor = entry.expected.get("canonical_cbor_hex")
    try:
        observed_json = canonical_json_bytes(value)
        observed_cbor = cbor_bytes(value)
        json_roundtrip = json.loads(
            observed_json.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys
        )
        cbor_roundtrip = cbor_value(observed_cbor)
    except (CanonicalizationError, ValueError) as error:
        return _result(entry, False, "codec failure: %s" % error)
    problems = []
    if expected_json is None or observed_json != expected_json.encode("utf-8"):
        problems.append("canonical JSON mismatch")
    if expected_cbor is None or observed_cbor != bytes.fromhex(expected_cbor):
        problems.append("canonical CBOR mismatch")
    if json_roundtrip != value:
        problems.append("JSON round-trip diverged semantically")
    if cbor_roundtrip != value:
        problems.append("CBOR round-trip diverged semantically")
    if problems:
        return _result(entry, False, "; ".join(problems))
    return _result(entry, True, "both codecs agree semantically and byte-exactly")


_VERIFIERS: Dict[str, Callable[[GoldenCorpusEntry], GoldenVectorResult]] = {
    "canonical-encoding": _verify_canonical_encoding,
    "encoding-convergence": _verify_convergence,
    "signature-input": _verify_signature_input,
    "codec-cross-agreement": _verify_codec_cross,
}


def verify_entry(entry: GoldenCorpusEntry) -> GoldenVectorResult:
    """Verify one corpus entry against its owning frozen authority."""
    verifier = _VERIFIERS.get(entry.category)
    if verifier is None:  # unreachable: loader validated the category
        return _result(entry, False, "no verifier for category %r" % entry.category)
    try:
        return verifier(entry)
    except Exception as error:  # noqa: BLE001 - fail-closed boundary
        return _result(
            entry, False, "unexpected %s: %s" % (type(error).__name__, error)
        )


def verify_corpus(
    corpus: Tuple[GoldenCorpusEntry, ...],
) -> Tuple[GoldenVectorResult, ...]:
    """Verify every entry in canonical (vector-id) order."""
    return tuple(verify_entry(entry) for entry in corpus_from_entries(corpus))


def corpus_digest(
    corpus: Tuple[GoldenCorpusEntry, ...],
    results: Optional[Tuple[GoldenVectorResult, ...]] = None,
) -> str:
    """The deterministic digest of the corpus and its verification.

    Covers the entry content (test data + expectations) and the
    verification outcomes, so a corpus whose data OR whose observed
    behavior changes yields a different digest.  Byte-stable across
    processes and hash seeds (sorted canonical serialization).
    """
    import hashlib

    canonical = corpus_from_entries(corpus)
    verified = results if results is not None else verify_corpus(canonical)
    document = {
        "entries": [entry.content_dict() for entry in canonical],
        "results": [result.content_dict() for result in verified],
        "all_verified": all(result.verified for result in verified),
    }
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes(document)
    ).hexdigest()
