"""Golden-vector loading for the ADCOS envelope.

Golden vectors live in ``protocol/vectors/`` as canonical-form JSON
files (the loader mechanically asserts canonical formatting). Every
vector declares its provisional/normative status explicitly: none of
them freeze a production wire profile — the production canonicalization
profile is declared only by later conformance work
(spec/architecture.md section 7).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
VECTORS_DIR = Path(__file__).resolve().parent / "vectors"


class VectorError(ValueError):
    """Raised when a golden-vector file is missing, malformed, or
    non-canonical."""


@dataclass(frozen=True)
class ExpectedBytes:
    canonical_json: str
    canonical_cbor_hex: str
    signature_input_json: str


@dataclass(frozen=True)
class VectorExpectation:
    accepted: bool
    classification: str
    validation_time: str
    unknown_type_policy: str  # "reject" | "forward-opaque"


@dataclass(frozen=True)
class GoldenVector:
    name: str
    description: str
    status: str
    envelope: Dict[str, Any]
    expected: Optional[ExpectedBytes]
    expect: VectorExpectation


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise VectorError("duplicate key %r in vector file" % key)
        result[key] = value
    return result


def _repository_canonical_bytes(value: Any) -> bytes:
    """Repository canonical form for JSON artifacts (sorted keys, 2-space
    indent, trailing newline — the spec/schemas convention established by
    WORK-001/002). Note this is distinct from the WIRE canonical JSON
    form implemented in protocol.canonicalization, which the vectors'
    ``expected`` blocks reference."""
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def load_vectors(vectors_dir: Optional[Path] = None) -> List[GoldenVector]:
    """Load all golden vectors in deterministic (name-sorted) order."""
    directory = vectors_dir or VECTORS_DIR
    if not directory.is_dir():
        raise VectorError("missing vectors directory: %s" % directory)
    vectors: List[GoldenVector] = []
    for path in sorted(directory.glob("*.json")):
        raw = path.read_bytes()
        try:
            data = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise VectorError("%s is not valid JSON: %s" % (path.name, error)) from error
        if not isinstance(data, dict):
            raise VectorError("%s must contain a JSON object" % path.name)
        if raw != _repository_canonical_bytes(data):
            raise VectorError("%s is not in canonical form" % path.name)

        try:
            name = data["name"]
            description = data["description"]
            status = data["status"]
            envelope = data["envelope"]
            expect_block = data["expect"]
        except KeyError as error:
            raise VectorError("%s is missing required field %s" % (path.name, error)) from error

        expected: Optional[ExpectedBytes] = None
        if "expected" in data:
            block = data["expected"]
            expected = ExpectedBytes(
                canonical_json=block["canonical_json"],
                canonical_cbor_hex=block["canonical_cbor_hex"],
                signature_input_json=block["signature_input_json"],
            )
        policy = expect_block.get("policy", {})
        vectors.append(
            GoldenVector(
                name=name,
                description=description,
                status=status,
                envelope=envelope,
                expected=expected,
                expect=VectorExpectation(
                    accepted=expect_block["accepted"],
                    classification=expect_block["classification"],
                    validation_time=expect_block["validation_time"],
                    unknown_type_policy=policy.get("unknown_type", "forward-opaque"),
                ),
            )
        )
    if not vectors:
        raise VectorError("no golden vectors found in %s" % directory)
    return vectors
