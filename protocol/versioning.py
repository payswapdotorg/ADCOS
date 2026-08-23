"""Protocol versioning and compatibility classification.

The single source of truth for the protocol version line, known major
versions, message-type grammar, and registered message types is
``spec/schemas/protocol.json`` (loaded at runtime, never duplicated in
code). The Protocol Version is an independent version line — it is not
the Architecture Version, not a Schema Version, and not an Implementation
Version (spec/governance.md section 3).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, FrozenSet, Mapping, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_ARTIFACT = REPO_ROOT / "spec" / "schemas" / "protocol.json"


class ProtocolArtifactError(RuntimeError):
    """Raised when the protocol artifact is missing or malformed."""


def _load_json_no_duplicates(text: str) -> object:
    def hook(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ProtocolArtifactError("duplicate key %r in protocol artifact" % key)
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=hook)


class Classification:
    """Deterministic compatibility dispositions.

    The values mirror the frozen future-version behavior table of
    spec/prompts/WORK-003.md section 4 and the compatibility_rules block
    of spec/schemas/protocol.json.
    """

    KNOWN_COMPATIBLE = "known_compatible"
    KNOWN_ADDITIVE = "known_additive"
    UNKNOWN_OPTIONAL_FORWARDED = "unknown_optional_forwarded"
    REJECTED_INCOMPATIBLE_MAJOR = "rejected_incompatible_major"
    REJECTED_UNKNOWN_REQUIRED = "rejected_unknown_required"
    REJECTED_UNKNOWN_TYPE = "rejected_unknown_type"
    REJECTED_TEMPORAL = "rejected_temporal"
    REJECTED_REPLAY = "rejected_replay"
    REJECTED_MALFORMED = "rejected_malformed"

    REJECTED_VALUES = frozenset(
        {
            REJECTED_INCOMPATIBLE_MAJOR,
            REJECTED_UNKNOWN_REQUIRED,
            REJECTED_UNKNOWN_TYPE,
            REJECTED_TEMPORAL,
            REJECTED_REPLAY,
            REJECTED_MALFORMED,
        }
    )

    ALL_VALUES = frozenset(
        {
            KNOWN_COMPATIBLE,
            KNOWN_ADDITIVE,
            UNKNOWN_OPTIONAL_FORWARDED,
        }
    ) | REJECTED_VALUES


@dataclass(frozen=True)
class ProtocolVersion:
    """A MAJOR.MINOR protocol version on the protocol version line."""

    major: int
    minor: int

    @classmethod
    def parse(cls, value: str) -> "ProtocolVersion":
        parts = value.split(".")
        if len(parts) != 2 or not all(part.isdigit() for part in parts):
            raise ProtocolArtifactError("protocol version %r is not MAJOR.MINOR" % value)
        return cls(major=int(parts[0]), minor=int(parts[1]))

    def __str__(self) -> str:  # pragma: no cover - trivial
        return "%d.%d" % (self.major, self.minor)


@dataclass(frozen=True)
class ProtocolMetadata:
    """Machine-loaded view of spec/schemas/protocol.json."""

    protocol_version: ProtocolVersion
    known_major_versions: FrozenSet[int]
    message_type_grammar: re.Pattern
    message_types: Mapping[str, Mapping]
    codecs: Mapping[str, Mapping]
    compact_codec_provisional: bool

    def is_known_major(self, major: int) -> bool:
        return major in self.known_major_versions

    def is_known_message_type(self, message_type: str) -> bool:
        return message_type in self.message_types


@lru_cache(maxsize=1)
def protocol_metadata() -> ProtocolMetadata:
    """Load and cache the protocol artifact (single source of truth)."""
    if not PROTOCOL_ARTIFACT.is_file():
        raise ProtocolArtifactError("missing protocol artifact: %s" % PROTOCOL_ARTIFACT)
    data = _load_json_no_duplicates(PROTOCOL_ARTIFACT.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ProtocolArtifactError("protocol artifact must be a JSON object")
    try:
        version = ProtocolVersion.parse(data["protocol_version"])
        known = frozenset(data["known_major_versions"])
        grammar = re.compile(data["message_type_grammar"])
        message_types: Dict[str, Mapping] = dict(data.get("message_types", {}))
        codecs: Dict[str, Mapping] = dict(data.get("codecs", {}))
    except (KeyError, TypeError) as error:
        raise ProtocolArtifactError("protocol artifact is malformed: %s" % error) from error
    compact = codecs.get("compact-deterministic-cbor", {})
    return ProtocolMetadata(
        protocol_version=version,
        known_major_versions=known,
        message_type_grammar=grammar,
        message_types=message_types,
        codecs=codecs,
        compact_codec_provisional=compact.get("status") == "provisional",
    )


def classify_major(major: int, metadata: Optional[ProtocolMetadata] = None) -> str:
    """Classify a protocol major version as known or incompatible."""
    meta = metadata or protocol_metadata()
    if major in meta.known_major_versions:
        return Classification.KNOWN_COMPATIBLE
    return Classification.REJECTED_INCOMPATIBLE_MAJOR
