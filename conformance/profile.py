"""WORK-055 production conformance layer -- the canonicalization profile.

spec/schemas/protocol.json deliberately left the PRODUCTION
canonicalization profile to "later conformance work before production
wire compatibility is declared".  WORK-055 is that conformance work.

This module makes the production canonicalization profile EXPLICIT:
it names the profile, enumerates every rule as an attributed
statement, and derives a deterministic profile digest over the
canonical form of the whole statement.

Authority discipline (frozen):

- Every rule RESTATES behavior already frozen in WORK-003
  (``protocol/canonicalization.py``, ``protocol/codec_json.py``, and
  the ``codecs`` block of ``spec/schemas/protocol.json``).  Nothing
  here mints new protocol semantics, new vocabulary, or a second
  canonicalization authority: the single authority remains WORK-003,
  and every rule cites the frozen source it restates.
- The profile statement is CONFORMANCE EVIDENCE, not protocol state:
  it can never accept, reject, sign, or derive any protocol object.
- The rules are mechanically verified by the W055 wire vectors
  (``conformance/vectors/wire.py``) against the genuine WORK-003
  implementation, and a deliberately sabotaged canonicalizer (one
  that violates a profile rule) makes the paired vector NONCONFORMANT
  (discrimination proof in ``tools/conformance_selftest.py``).

Determinism: the profile statement is a frozen tuple of frozen
mappings; the digest is the SHA-256 of its canonical JSON bytes --
byte-stable across processes, runs, and hash seeds.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, FrozenSet, Tuple

from protocol import canonical_json_bytes

__all__ = [
    "CANONICALIZATION_PROFILE_ID",
    "CANONICALIZATION_PROFILE_RULES",
    "PROFILE_RULE_IDS",
    "profile_statement",
    "profile_digest",
    "profile_rule_sources",
]

#: The stable identifier of the production canonicalization profile
#: declared by WORK-055 for ADCOS Protocol Version 1.0.  It names the
#: WORK-003 canonical JSON form; it does not create a second one.
CANONICALIZATION_PROFILE_ID = "adcos.canonical-json.production.v1"

#: The profile rule statement: every rule of the production
#: canonicalization profile, each attributed to the WORK-003 authority
#: whose frozen implementation decides it.  Rules are restatements of
#: frozen behavior (see protocol/canonicalization.py docstring and
#: spec/schemas/protocol.json codecs."json-debug".description); the
#: pairing rule_id -> mechanical verification lives in
#: conformance/vectors/wire.py.
CANONICALIZATION_PROFILE_RULES: Tuple[Dict[str, str], ...] = (
    {
        "rule_id": "CP-01",
        "authority": "WORK-003",
        "statement": (
            "Object keys are sorted by UTF-16 code-unit order (the sort "
            "key is the key encoded as UTF-16 big-endian), matching RFC "
            "8785 (JCS) for the supported subset."
        ),
        "source": (
            "protocol/canonicalization.py (_utf16_sort_key); "
            "spec/schemas/protocol.json codecs.json-debug.description"
        ),
    },
    {
        "rule_id": "CP-02",
        "authority": "WORK-003",
        "statement": (
            "No insignificant whitespace: JSON tokens are separated only "
            "by ',' and ':'."
        ),
        "source": (
            "protocol/canonicalization.py (_write); "
            "spec/schemas/protocol.json codecs.json-debug.description"
        ),
    },
    {
        "rule_id": "CP-03",
        "authority": "WORK-003",
        "statement": (
            "Strings use minimal JSON escaping: '\"' and '\\' are "
            "escaped; the five control characters with short escapes use "
            "them; other characters below U+0020 use \\u00xx with "
            "lowercase hexadecimal digits."
        ),
        "source": "protocol/canonicalization.py (_canonical_string)",
    },
    {
        "rule_id": "CP-04",
        "authority": "WORK-003",
        "statement": (
            "All other characters are emitted literally and the output "
            "encoding is UTF-8."
        ),
        "source": (
            "protocol/canonicalization.py (_canonical_string, "
            "canonical_json_bytes)"
        ),
    },
    {
        "rule_id": "CP-05",
        "authority": "WORK-003",
        "statement": (
            "Booleans and null use their JSON literals; booleans are "
            "checked before integers (Python booleans are integer "
            "subclasses) so True is never emitted as 1."
        ),
        "source": "protocol/canonicalization.py (_write ordering)",
    },
    {
        "rule_id": "CP-06",
        "authority": "WORK-003",
        "statement": (
            "Integers are emitted in shortest decimal form, including "
            "negative integers; a JSON float literal never survives "
            "canonicalization as a float."
        ),
        "source": (
            "protocol/canonicalization.py (_write int branch); "
            "spec/schemas/protocol.json codecs.json-debug.description"
        ),
    },
    {
        "rule_id": "CP-07",
        "authority": "WORK-003",
        "statement": (
            "Floating-point values are OUTSIDE the canonical subset and "
            "raise CanonicalizationError (fail safely) rather than being "
            "formatted with platform-specific float rules."
        ),
        "source": (
            "protocol/canonicalization.py (_write float branch); "
            "spec/schemas/protocol.json codecs.json-debug.description"
        ),
    },
    {
        "rule_id": "CP-08",
        "authority": "WORK-003",
        "statement": (
            "Object keys must be strings; non-string keys raise "
            "CanonicalizationError."
        ),
        "source": "protocol/canonicalization.py (_write dict branch)",
    },
    {
        "rule_id": "CP-09",
        "authority": "WORK-003",
        "statement": (
            "Values nested deeper than MAX_CANONICAL_DEPTH (64) levels "
            "raise CanonicalizationError."
        ),
        "source": "protocol/canonicalization.py (MAX_CANONICAL_DEPTH)",
    },
    {
        "rule_id": "CP-10",
        "authority": "WORK-003",
        "statement": (
            "Text that cannot be encoded as UTF-8 (lone surrogates) and "
            "object keys that cannot be encoded to UTF-16 raise "
            "CanonicalizationError."
        ),
        "source": (
            "protocol/canonicalization.py (canonical_json_bytes, "
            "_utf16_sort_key)"
        ),
    },
    {
        "rule_id": "CP-11",
        "authority": "WORK-003",
        "statement": (
            "Absent optional members are omitted, never emitted as null "
            "(the envelope serializer omits None correlation_id and "
            "unknown members are preserved verbatim, not re-stamped)."
        ),
        "source": (
            "protocol/envelope.py (Envelope.to_dict); "
            "spec/schemas/protocol.json description"
        ),
    },
    {
        "rule_id": "CP-12",
        "authority": "WORK-003",
        "statement": (
            "Canonicalization is idempotent: the canonical form of a "
            "value parsed back from canonical text is byte-identical "
            "(canonical(canonical(x)) == canonical(x))."
        ),
        "source": "protocol/canonicalization.py (deterministic form)",
    },
)

#: The frozen rule-id set (asserted complete by the wire vectors).
PROFILE_RULE_IDS: FrozenSet[str] = frozenset(
    rule["rule_id"] for rule in CANONICALIZATION_PROFILE_RULES
)


def profile_statement() -> Dict[str, Any]:
    """The canonical profile statement (deterministic content dict).

    Includes the profile identifier, the owning authority, the frozen
    Protocol Version the profile applies to (read from the WORK-003
    artifact -- never restated locally), and the full rule list.
    """
    from protocol import protocol_metadata

    metadata = protocol_metadata()
    return {
        "profile_id": CANONICALIZATION_PROFILE_ID,
        "owning_authority": "WORK-003",
        "protocol_version": str(metadata.protocol_version),
        "declared_by": "WORK-055 (WORK-055-CORE-001, DEC-0088)",
        "rules": [dict(rule) for rule in CANONICALIZATION_PROFILE_RULES],
    }


def profile_rule_sources() -> Tuple[str, ...]:
    """Every frozen source cited by the profile rules (sorted)."""
    sources = set()
    for rule in CANONICALIZATION_PROFILE_RULES:
        sources.add(rule["source"])
    return tuple(sorted(sources))


def profile_digest() -> str:
    """The deterministic digest of the canonical profile statement.

    Byte-stable across processes and hash seeds (the statement is a
    frozen structure serialized with the WORK-003 canonical form).
    """
    return "sha256:" + hashlib.sha256(
        canonical_json_bytes(profile_statement())
    ).hexdigest()
