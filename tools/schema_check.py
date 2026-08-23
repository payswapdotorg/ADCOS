#!/usr/bin/env python3
"""ADCOS schema/registry consistency checker (WORK-002).

Deterministic, offline, zero-dependency validation of the machine-readable
vocabulary and registry layer under spec/schemas/. Introduced by WORK-002.

Invocation (Python 3.8+, standard library only, no network access):

    python3 tools/schema_check.py

Exit codes:
    0  all blocking checks passed
    1  at least one blocking check failed

This module also exports reusable primitives consumed by
tools/schema_selftest.py:

- canonical_json_bytes / load_json: canonical formatting (sorted keys,
  2-space indent, trailing newline) and duplicate-key-detecting parsing;
- classify_id: the known / unknown / invalid identifier classification
  that implements the registries' unknown_id_policy;
- validate_instance: a minimal deterministic validator for the JSON Schema
  subset used by the ADCOS schema files (type, properties, required,
  additionalProperties, items, enum, pattern, minLength, minItems).

The .schema.json files are standard JSON Schema draft 2020-12 documents;
the built-in validator deliberately covers only the subset the ADCOS
schemas use, keeping the toolchain free of third-party dependencies.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "spec" / "schemas"
REGISTRY_DIR = SCHEMA_DIR / "registries"

ARCH_VERSION_DECL_RE = re.compile(r"Architecture Version (\d+)\.(\d+)")
SCHEMA_VERSION_RE = re.compile(r"^\d+\.\d+$")

# The 11 frozen architecture nouns (spec/architecture.md §6) and their
# technology-neutral registry identifiers.
FROZEN_DOMAIN_OBJECTS: Dict[str, str] = {
    "Node": "adcos.node",
    "Identity": "adcos.identity",
    "Adapter": "adcos.adapter",
    "Capability": "adcos.capability",
    "Link": "adcos.link",
    "Path": "adcos.path",
    "Session": "adcos.session",
    "Resource": "adcos.resource",
    "Intent": "adcos.intent",
    "Federation": "adcos.federation",
    "Evidence": "adcos.evidence",
}

# The frozen access-technology identifiers (spec/architecture.md §8).
FROZEN_ACCESS_IDS: List[str] = [
    "access.3gpp.nr.imt2020",
    "access.3gpp.lte.imtadvanced",
    "access.ieee.80211",
    "access.ieee.8023",
    "access.satellite",
    "access.microwave",
    "access.bluetooth",
    "access.3gpp.sidelink",
    "access.3gpp.iab",
]

# Tokens that must never appear in core (technology-neutral) identifiers:
# access technologies, radio generations, standards bodies, vendors.
FORBIDDEN_CORE_TOKENS: List[str] = [
    "3gpp", "5g", "6g", "802", "bluetooth", "ethernet", "ieee", "imt",
    "lte", "microwave", "nr", "o-ran", "oran", "satellite", "wifi",
]


class DuplicateKeyError(ValueError):
    """Raised when a JSON document contains a duplicate object key."""


def canonical_json_bytes(value: Any) -> bytes:
    """Canonical serialization: sorted keys, 2-space indent, trailing newline."""
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _no_duplicate_keys(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError("duplicate object key: %r" % key)
        result[key] = value
    return result


def load_json(text: str) -> Any:
    """Parse JSON text, rejecting duplicate object keys deterministically."""
    return json.loads(text, object_pairs_hook=_no_duplicate_keys)


def declared_architecture_version() -> Optional[Tuple[int, int]]:
    """The Architecture Version declared in spec/architecture.md Status."""
    path = REPO_ROOT / "spec" / "architecture.md"
    if not path.is_file():
        return None
    match = ARCH_VERSION_DECL_RE.search(path.read_text(encoding="utf-8"))
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)))


def parse_version(value: str) -> Tuple[int, int]:
    major, minor = value.split(".")
    return (int(major), int(minor))


def classify_id(grammar: str, entries: Dict[str, Any], candidate: str) -> str:
    """Classify an identifier against a registry.

    Returns "known" (registered), "unknown" (well-formed but not
    registered — must be preserved, never coerced), or "invalid"
    (malformed — rejected by validators).
    """
    if not isinstance(candidate, str):
        return "invalid"
    if candidate in entries:
        return "known"
    if re.fullmatch(grammar, candidate) is not None:
        return "unknown"
    return "invalid"


def validate_instance(instance: Any, schema: Dict[str, Any], path: str = "$") -> List[str]:
    """Validate an instance against the ADCOS JSON Schema subset.

    Supported keywords: type, properties, required, additionalProperties
    (boolean), items, enum, const, anyOf, pattern, minLength, maxLength,
    minItems, minimum. Returns a list of human-readable error strings
    (empty when valid).
    """
    errors: List[str] = []

    if "const" in schema:
        if instance != schema["const"] or type(instance) is not type(schema["const"]):
            errors.append("%s: %r is not the constant %r" % (path, instance, schema["const"]))
        return errors

    if "anyOf" in schema:
        branches = schema["anyOf"]
        if not any(not validate_instance(instance, branch, path) for branch in branches):
            errors.append("%s: %r does not satisfy any branch of anyOf" % (path, instance))
        return errors

    if "enum" in schema:
        if instance not in schema["enum"]:
            errors.append("%s: %r is not one of %r" % (path, instance, schema["enum"]))
        return errors

    expected_type = schema.get("type")
    if expected_type is not None:
        type_checks = {
            "object": lambda v: isinstance(v, dict),
            "array": lambda v: isinstance(v, list),
            "string": lambda v: isinstance(v, str),
            "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
            "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
            "boolean": lambda v: isinstance(v, bool),
            "null": lambda v: v is None,
        }
        check = type_checks.get(expected_type)
        if check is not None and not check(instance):
            errors.append("%s: expected %s, got %s" % (path, expected_type, type(instance).__name__))
            return errors

    if isinstance(instance, str):
        pattern = schema.get("pattern")
        if pattern is not None and re.search(pattern, instance) is None:
            errors.append("%s: %r does not match pattern %r" % (path, instance, pattern))
        min_length = schema.get("minLength")
        if min_length is not None and len(instance) < min_length:
            errors.append("%s: shorter than minLength %d" % (path, min_length))
        max_length = schema.get("maxLength")
        if max_length is not None and len(instance) > max_length:
            errors.append("%s: longer than maxLength %d" % (path, max_length))

    if isinstance(instance, int) and not isinstance(instance, bool):
        minimum = schema.get("minimum")
        if minimum is not None and instance < minimum:
            errors.append("%s: %r is less than minimum %r" % (path, instance, minimum))

    if isinstance(instance, list):
        min_items = schema.get("minItems")
        if min_items is not None and len(instance) < min_items:
            errors.append("%s: fewer than minItems %d" % (path, min_items))
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(instance):
                errors.extend(validate_instance(item, item_schema, "%s[%d]" % (path, index)))

    if isinstance(instance, dict):
        properties = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in instance:
                errors.append("%s: missing required property %r" % (path, name))
        for name, value in instance.items():
            child_schema = properties.get(name)
            if child_schema is not None:
                errors.extend(validate_instance(value, child_schema, "%s.%s" % (path, name)))
            elif schema.get("additionalProperties") is False:
                errors.append("%s: additional property %r is not allowed" % (path, name))

    return errors


# --------------------------------------------------------------------------
# Repository discovery
# --------------------------------------------------------------------------

def registry_files() -> List[Path]:
    return sorted(REGISTRY_DIR.glob("*.json")) if REGISTRY_DIR.is_dir() else []


def schema_files() -> List[Path]:
    return sorted(SCHEMA_DIR.glob("*.schema.json")) if SCHEMA_DIR.is_dir() else []


def protocol_artifact_file() -> Optional[Path]:
    candidate = SCHEMA_DIR / "protocol.json"
    return candidate if candidate.is_file() else None


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

class Report:
    def __init__(self) -> None:
        self.results: List[Tuple[str, str, List[str]]] = []

    def record(self, status: str, check_id: str, details: Optional[List[str]] = None) -> None:
        self.results.append((status, check_id, details or []))

    def blocking_failed(self) -> int:
        return sum(1 for status, _, _ in self.results if status == "FAIL")


def check_format(report: Report, loaded: Dict[str, Tuple[Path, Any]]) -> None:
    """SCHEMA-01: JSON artifacts parse (duplicate keys rejected) and are
    canonically formatted (sorted keys, 2-space indent, trailing newline)."""
    problems: List[str] = []
    for rel_path in sorted(loaded):
        path, value = loaded[rel_path]
        raw = path.read_bytes()
        if raw != canonical_json_bytes(value):
            problems.append(
                "%s: not in canonical form (sorted keys, 2-space indent, trailing newline)"
                % rel_path
            )
    if problems:
        report.record("FAIL", "SCHEMA-01", problems)
    else:
        report.record("PASS", "SCHEMA-01")


def check_metadata(report: Report, loaded: Dict[str, Tuple[Path, Any]]) -> None:
    """SCHEMA-02: every artifact carries consistent version metadata.

    schema_version must be MAJOR.MINOR; architecture_version must be
    MAJOR.MINOR and no greater than the Architecture Version declared in
    spec/architecture.md (an artifact is written *against* an architecture
    version and can never precede the declaration)."""
    problems: List[str] = []
    declared = declared_architecture_version()
    if declared is None:
        problems.append("cannot determine the declared Architecture Version")
    for rel_path in sorted(loaded):
        _, value = loaded[rel_path]
        if not isinstance(value, dict):
            problems.append("%s: expected a JSON object at top level" % rel_path)
            continue
        for field in ("schema_version", "architecture_version"):
            field_value = value.get(field)
            if not isinstance(field_value, str) or SCHEMA_VERSION_RE.fullmatch(field_value) is None:
                problems.append(
                    "%s: %s must be a MAJOR.MINOR string (found %r)"
                    % (rel_path, field, field_value)
                )
        if declared is not None:
            arch = value.get("architecture_version")
            if isinstance(arch, str) and SCHEMA_VERSION_RE.fullmatch(arch) is not None:
                if parse_version(arch) > declared:
                    problems.append(
                        "%s: architecture_version %s is greater than the declared "
                        "Architecture Version %d.%d" % (rel_path, arch, declared[0], declared[1])
                    )
    if problems:
        report.record("FAIL", "SCHEMA-02", problems)
    else:
        report.record("PASS", "SCHEMA-02")


def check_id_grammar(report: Report, registries: Dict[str, Dict[str, Any]]) -> None:
    """SCHEMA-03: registry IDs are well-formed per the registry's own
    id_grammar and unique (duplicate keys are rejected at parse time)."""
    problems: List[str] = []
    for name in sorted(registries):
        registry = registries[name]
        grammar = registry.get("id_grammar")
        if not isinstance(grammar, str) or not grammar:
            problems.append("%s: missing id_grammar" % name)
            continue
        entries = registry.get("entries")
        if not isinstance(entries, dict) or not entries:
            problems.append("%s: missing or empty entries" % name)
            continue
        for entry_id, entry in sorted(entries.items()):
            if re.fullmatch(grammar, entry_id) is None:
                problems.append(
                    "%s: entry %r does not match the registry id_grammar %r"
                    % (name, entry_id, grammar)
                )
            if not isinstance(entry, dict) or "status" not in entry:
                problems.append("%s: entry %r must be an object with a status" % (name, entry_id))
            elif entry.get("status") not in ("active", "reserved", "deprecated"):
                problems.append(
                    "%s: entry %r has invalid status %r (active|reserved|deprecated)"
                    % (name, entry_id, entry.get("status"))
                )
    if problems:
        report.record("FAIL", "SCHEMA-03", problems)
    else:
        report.record("PASS", "SCHEMA-03")


def check_technology_neutrality(
    report: Report, registries: Dict[str, Dict[str, Any]]
) -> None:
    """SCHEMA-04: core identifiers are technology/generation neutral.

    Domain-object IDs and core-scoped capability IDs must not contain
    access-technology, radio-generation, standards-body, or vendor tokens.
    Access technologies live only in the access-profile registry."""
    problems: List[str] = []

    def scan(identifier: str, where: str) -> None:
        segments = identifier.lower().replace("-", "").split(".")
        for token in FORBIDDEN_CORE_TOKENS:
            for segment in segments:
                if token in segment:
                    problems.append(
                        "%s: identifier %r contains forbidden technology token %r "
                        "(core IDs must be technology/generation neutral — LOCK-001..003)"
                        % (where, identifier, token)
                    )

    domain = registries.get("adcos.domain-object-registry")
    if domain is not None:
        for entry_id in sorted(domain.get("entries", {})):
            scan(entry_id, "domain-object-registry")
    capability = registries.get("adcos.capability-registry")
    if capability is not None:
        for entry_id, entry in sorted(capability.get("entries", {}).items()):
            if isinstance(entry, dict) and entry.get("scope") == "core":
                scan(entry_id, "capability-registry (core scope)")
    if problems:
        report.record("FAIL", "SCHEMA-04", problems)
    else:
        report.record("PASS", "SCHEMA-04")


def check_completeness(
    report: Report,
    registries: Dict[str, Dict[str, Any]],
    loaded: Dict[str, Tuple[Path, Any]],
) -> None:
    """SCHEMA-05: every frozen noun has a versioned machine-readable
    definition; every frozen access ID is registered; schema references
    resolve with matching $id and schema_version; no orphan schemas."""
    problems: List[str] = []
    domain = registries.get("adcos.domain-object-registry")
    if domain is None:
        report.record("FAIL", "SCHEMA-05", ["domain-object-registry.json is missing"])
        return
    entries = domain.get("entries", {})

    expected_by_id = {identifier: noun for noun, identifier in FROZEN_DOMAIN_OBJECTS.items()}
    for identifier, noun in sorted(expected_by_id.items()):
        entry = entries.get(identifier)
        if entry is None:
            problems.append(
                "domain-object-registry: frozen noun %s (%s) is not registered" % (noun, identifier)
            )
            continue
        if entry.get("noun") != noun:
            problems.append(
                "domain-object-registry: %r noun is %r, expected %r"
                % (identifier, entry.get("noun"), noun)
            )
    for identifier, entry in sorted(entries.items()):
        if identifier not in expected_by_id:
            problems.append(
                "domain-object-registry: %r is not one of the frozen architecture nouns "
                "(silently adding core nouns is not permitted)" % identifier
            )
            continue
        schema_ref = entry.get("schema_ref")
        schema_id = entry.get("schema_id")
        schema_version = entry.get("schema_version")
        if not isinstance(schema_ref, str):
            problems.append("%s: missing schema_ref" % identifier)
            continue
        target = REPO_ROOT / schema_ref
        if not target.is_file():
            problems.append("%s: schema_ref %r does not resolve to a file" % (identifier, schema_ref))
            continue
        pair = loaded.get(target.relative_to(REPO_ROOT).as_posix())
        if pair is None:
            problems.append("%s: schema_ref %r is not a tracked schema artifact" % (identifier, schema_ref))
            continue
        schema_doc = pair[1]
        if schema_doc.get("$id") != schema_id:
            problems.append(
                "%s: schema $id %r does not match registry schema_id %r"
                % (identifier, schema_doc.get("$id"), schema_id)
            )
        if schema_doc.get("schema_version") != schema_version:
            problems.append(
                "%s: registry schema_version %r does not match schema file version %r"
                % (identifier, schema_version, schema_doc.get("schema_version"))
            )

    access = registries.get("adcos.access-profile-registry")
    if access is None:
        problems.append("access-profile-registry.json is missing")
    else:
        access_entries = access.get("entries", {})
        for frozen_id in FROZEN_ACCESS_IDS:
            entry = access_entries.get(frozen_id)
            if entry is None:
                problems.append("access-profile-registry: frozen ID %r is not registered" % frozen_id)
            elif entry.get("status") != "active":
                problems.append(
                    "access-profile-registry: frozen ID %r must have status 'active' (found %r)"
                    % (frozen_id, entry.get("status"))
                )

    referenced = {
        (REPO_ROOT / entry.get("schema_ref", "")).resolve().as_posix()
        for entry in entries.values()
        if isinstance(entry, dict) and isinstance(entry.get("schema_ref"), str)
    }
    protocol = loaded.get("spec/schemas/protocol.json")
    if protocol is not None:
        envelope_ref = protocol[1].get("envelope", {}).get("schema_ref")
        if isinstance(envelope_ref, str):
            referenced.add((REPO_ROOT / envelope_ref).resolve().as_posix())
    for rel_path in sorted(loaded):
        if rel_path.endswith(".schema.json"):
            absolute = (REPO_ROOT / rel_path).resolve().as_posix()
            if absolute not in referenced:
                problems.append("%s: schema file is not referenced by the domain-object or protocol registry" % rel_path)

    if problems:
        report.record("FAIL", "SCHEMA-05", problems)
    else:
        report.record("PASS", "SCHEMA-05")


def check_cross_references(report: Report, registries: Dict[str, Dict[str, Any]]) -> None:
    """SCHEMA-06: cross-registry references resolve; profile-scoped
    capability entries point at registered access profiles; registries
    with extension semantics document an unknown_id_policy."""
    problems: List[str] = []
    access = registries.get("adcos.access-profile-registry")
    capability = registries.get("adcos.capability-registry")
    if access is None or capability is None:
        report.record("FAIL", "SCHEMA-06", ["required registry missing"])
        return

    access_entries = access.get("entries", {})
    for name in (
        "adcos.access-profile-registry",
        "adcos.capability-registry",
        "adcos.identity-profile-registry",
    ):
        if name in registries and "unknown_id_policy" not in registries[name]:
            problems.append("%s: missing unknown_id_policy" % name)

    for entry_id, entry in sorted(capability.get("entries", {}).items()):
        scope = entry.get("scope")
        if scope not in ("core", "profile"):
            problems.append(
                "capability-registry: %r has invalid scope %r (core|profile)" % (entry_id, scope)
            )
            continue
        profile_ref = entry.get("profile_ref")
        if scope == "profile":
            if not isinstance(profile_ref, str):
                problems.append(
                    "capability-registry: profile-scoped %r must carry profile_ref" % entry_id
                )
            elif profile_ref not in access_entries:
                problems.append(
                    "capability-registry: %r profile_ref %r does not resolve in the "
                    "access-profile registry" % (entry_id, profile_ref)
                )
        elif profile_ref is not None:
            problems.append(
                "capability-registry: core-scoped %r must not carry profile_ref" % entry_id
            )

    if problems:
        report.record("FAIL", "SCHEMA-06", problems)
    else:
        report.record("PASS", "SCHEMA-06")


def check_protocol_artifact(report: Report, loaded: Dict[str, Tuple[Path, Any]]) -> None:
    """SCHEMA-07: WORK-003 protocol artifact (spec/schemas/protocol.json):
    protocol version line, envelope reference, message-type grammar
    consistency, registered message types, and codec status — including the
    guard that the compact codec must not claim normative/production status
    before the production canonicalization profile is frozen."""
    problems: List[str] = []
    key = "spec/schemas/protocol.json"
    if key not in loaded:
        report.record("FAIL", "SCHEMA-07", ["%s is missing (WORK-003 protocol artifact)" % key])
        return
    value = loaded[key][1]

    if value.get("artifact") != "adcos.protocol":
        problems.append("%s: artifact must be 'adcos.protocol'" % key)

    protocol_version = value.get("protocol_version")
    if not isinstance(protocol_version, str) or SCHEMA_VERSION_RE.fullmatch(protocol_version) is None:
        problems.append("%s: protocol_version must be a MAJOR.MINOR string" % key)
        protocol_version = None

    known = value.get("known_major_versions")
    if not isinstance(known, list) or not known or not all(
        isinstance(item, int) and not isinstance(item, bool) and item >= 1 for item in known
    ):
        problems.append("%s: known_major_versions must be a non-empty list of positive integers" % key)
    elif protocol_version is not None:
        major = int(protocol_version.split(".")[0])
        if major not in known:
            problems.append(
                "%s: protocol_version major %d is not in known_major_versions %r" % (key, major, known)
            )

    envelope = value.get("envelope")
    envelope_schema: Optional[Dict[str, Any]] = None
    if not isinstance(envelope, dict):
        problems.append("%s: missing envelope reference block" % key)
    else:
        schema_ref = envelope.get("schema_ref")
        schema_id = envelope.get("schema_id")
        schema_version = envelope.get("schema_version")
        if not isinstance(schema_ref, str):
            problems.append("%s: envelope.schema_ref must be a string" % key)
        else:
            target = REPO_ROOT / schema_ref
            if not target.is_file():
                problems.append("%s: envelope.schema_ref %r does not resolve to a file" % (key, schema_ref))
            else:
                rel_path = target.relative_to(REPO_ROOT).as_posix()
                pair = loaded.get(rel_path)
                if pair is None:
                    problems.append("%s: envelope.schema_ref %r is not a tracked schema artifact" % (key, schema_ref))
                else:
                    envelope_schema = pair[1]
                    if envelope_schema.get("$id") != schema_id:
                        problems.append(
                            "%s: envelope schema $id %r does not match protocol schema_id %r"
                            % (key, envelope_schema.get("$id"), schema_id)
                        )
                    if envelope_schema.get("schema_version") != schema_version:
                        problems.append(
                            "%s: envelope schema_version %r does not match protocol declaration %r"
                            % (key, envelope_schema.get("schema_version"), schema_version)
                        )

    grammar = value.get("message_type_grammar")
    if not isinstance(grammar, str) or not grammar:
        problems.append("%s: message_type_grammar must be a non-empty string" % key)
    elif envelope_schema is not None:
        schema_pattern = (
            envelope_schema.get("properties", {}).get("message_type", {}).get("pattern")
        )
        if schema_pattern != grammar:
            problems.append(
                "%s: message_type_grammar does not match the envelope schema message_type pattern "
                "(single source of truth violated: %r vs %r)" % (key, grammar, schema_pattern)
            )

    message_types = value.get("message_types")
    if not isinstance(message_types, dict):
        problems.append("%s: message_types must be an object" % key)
    else:
        for type_id, entry in sorted(message_types.items()):
            if isinstance(grammar, str) and re.fullmatch(grammar, type_id) is None:
                problems.append("%s: message type %r does not match the message_type_grammar" % (key, type_id))
            if not isinstance(entry, dict) or entry.get("status") != "active":
                problems.append("%s: message type %r must be an entry with status 'active'" % (key, type_id))

    compatibility = value.get("compatibility_rules")
    required_rules = {
        "known_compatible",
        "known_additive",
        "unknown_optional",
        "unknown_required",
        "incompatible_major",
        "malformed",
        "expired_or_replayed",
    }
    if not isinstance(compatibility, dict) or not required_rules.issubset(compatibility):
        problems.append(
            "%s: compatibility_rules must declare all frozen dispositions %s"
            % (key, sorted(required_rules))
        )

    codecs = value.get("codecs")
    if not isinstance(codecs, dict):
        problems.append("%s: codecs must be an object" % key)
    else:
        json_codec = codecs.get("json-debug")
        if not isinstance(json_codec, dict) or json_codec.get("status") != "normative":
            problems.append("%s: the json-debug codec must be declared with status 'normative'" % key)
        compact = codecs.get("compact-deterministic-cbor")
        if not isinstance(compact, dict):
            problems.append("%s: the compact-deterministic-cbor codec must be declared" % key)
        elif compact.get("status") != "provisional":
            problems.append(
                "%s: the compact-deterministic-cbor codec must keep status 'provisional' — "
                "the production canonicalization profile is frozen only by later conformance "
                "work (spec/architecture.md section 7)" % key
            )

    if problems:
        report.record("FAIL", "SCHEMA-07", problems)
    else:
        report.record("PASS", "SCHEMA-07")


def check_identity_profiles(report: Report, registries: Dict[str, Dict[str, Any]]) -> None:
    """SCHEMA-08: identity-profile registry (WORK-004): every profile entry
    structurally declares a known derivation rule, non-empty unique key
    roles matching the role grammar, and non-empty unique signing
    algorithms matching the algorithm grammar; the registry declares the
    grammars and at least one derivation rule."""
    problems: List[str] = []
    name = "adcos.identity-profile-registry"
    registry = registries.get(name)
    if registry is None:
        report.record("FAIL", "SCHEMA-08", ["%s registry is missing (WORK-004)" % name])
        return

    algorithm_grammar = registry.get("algorithm_id_grammar")
    if not isinstance(algorithm_grammar, str) or not algorithm_grammar:
        problems.append("%s: missing algorithm_id_grammar" % name)
    role_grammar = registry.get("key_role_grammar")
    if not isinstance(role_grammar, str) or not role_grammar:
        problems.append("%s: missing key_role_grammar" % name)
    derivation_rules = registry.get("derivation_rules")
    if not isinstance(derivation_rules, dict) or not derivation_rules:
        problems.append("%s: derivation_rules must be a non-empty object" % name)
    else:
        for rule_id, rule in sorted(derivation_rules.items()):
            if not isinstance(rule, dict) or "domain_separation" not in rule or "description" not in rule:
                problems.append(
                    "%s: derivation rule %r must declare domain_separation and description" % (name, rule_id)
                )

    entries = registry.get("entries", {})
    if not isinstance(entries, dict) or not entries:
        problems.append("%s: missing or empty entries" % name)
    else:
        active_seen = False
        for profile_id, entry in sorted(entries.items()):
            where = "%s entry %r" % (name, profile_id)
            if not isinstance(entry, dict):
                problems.append("%s: must be an object" % where)
                continue
            derivation = entry.get("derivation")
            if not isinstance(derivation, str) or derivation not in (
                derivation_rules if isinstance(derivation_rules, dict) else {}
            ):
                problems.append("%s: derivation %r is not a declared derivation rule" % (where, derivation))
            roles = entry.get("key_roles")
            if (
                not isinstance(roles, list)
                or not roles
                or len(set(roles)) != len(roles)
                or not all(isinstance(role, str) for role in roles)
            ):
                problems.append("%s: key_roles must be a non-empty list of unique strings" % where)
            elif isinstance(role_grammar, str) and role_grammar:
                for role in roles:
                    if re.fullmatch(role_grammar, role) is None:
                        problems.append("%s: key role %r does not match key_role_grammar" % (where, role))
            algorithms = entry.get("signing_algorithms")
            if (
                not isinstance(algorithms, list)
                or not algorithms
                or len(set(algorithms)) != len(algorithms)
                or not all(isinstance(alg, str) for alg in algorithms)
            ):
                problems.append("%s: signing_algorithms must be a non-empty list of unique strings" % where)
            elif isinstance(algorithm_grammar, str) and algorithm_grammar:
                for alg in algorithms:
                    if re.fullmatch(algorithm_grammar, alg) is None:
                        problems.append(
                            "%s: algorithm %r does not match algorithm_id_grammar" % (where, alg)
                        )
            if entry.get("status") == "active":
                active_seen = True
        if not active_seen:
            problems.append("%s: no active profile entry" % name)

    if problems:
        report.record("FAIL", "SCHEMA-08", problems)
    else:
        report.record("PASS", "SCHEMA-08")


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

CHECK_TITLES: Dict[str, str] = {
    "SCHEMA-01": "Canonical JSON formatting and duplicate-key rejection",
    "SCHEMA-02": "Consistent schema/registry version metadata",
    "SCHEMA-03": "Registry ID grammar and entry status validity",
    "SCHEMA-04": "Technology-neutrality of core identifiers",
    "SCHEMA-05": "Frozen-noun completeness and schema reference resolution",
    "SCHEMA-06": "Cross-registry references and unknown-ID policies",
    "SCHEMA-07": "Protocol artifact: version line, envelope reference, codec status",
    "SCHEMA-08": "Identity-profile registry: derivation rules, key roles, algorithm grammar",
}


def load_all() -> Dict[str, Tuple[Path, Any]]:
    loaded: Dict[str, Tuple[Path, Any]] = {}
    paths = registry_files() + schema_files()
    protocol_artifact = protocol_artifact_file()
    if protocol_artifact is not None:
        paths.append(protocol_artifact)
    for path in paths:
        rel_path = path.relative_to(REPO_ROOT).as_posix()
        loaded[rel_path] = (path, load_json(path.read_text(encoding="utf-8")))
    return loaded


def main() -> int:
    report = Report()
    try:
        loaded = load_all()
    except (DuplicateKeyError, json.JSONDecodeError) as error:
        print("ADCOS schema/registry consistency checks")
        print("=" * 72)
        print("[FAIL    ] SCHEMA-01  %s" % error)
        print("-" * 72)
        print("Result: FAIL (1 blocking check failed)")
        return 1
    if not loaded:
        print("ADCOS schema/registry consistency checks")
        print("=" * 72)
        print("[FAIL    ] no schema/registry artifacts found under spec/schemas/")
        return 1

    registries: Dict[str, Dict[str, Any]] = {}
    try:
        for rel_path in sorted(loaded):
            if rel_path.startswith("spec/schemas/registries/"):
                value = loaded[rel_path][1]
                registries.setdefault(value.get("registry", rel_path), value)

        check_format(report, loaded)
        check_metadata(report, loaded)
        check_id_grammar(report, registries)
        check_technology_neutrality(report, registries)
        check_completeness(report, registries, loaded)
        check_cross_references(report, registries)
        check_protocol_artifact(report, loaded)
        check_identity_profiles(report, registries)
    except (DuplicateKeyError, json.JSONDecodeError) as error:
        print("ADCOS schema/registry consistency checks")
        print("=" * 72)
        print("[FAIL    ] SCHEMA-01  %s" % error)
        print("-" * 72)
        print("Result: FAIL (1 blocking check failed)")
        return 1

    print("ADCOS schema/registry consistency checks")
    print("=" * 72)
    for status, check_id, details in report.results:
        print("[%s] %s  %s" % (status.ljust(8), check_id.ljust(10), CHECK_TITLES.get(check_id, "")))
        for detail in details:
            print("         - %s" % detail)
    print("-" * 72)
    blocking_failed = report.blocking_failed()
    if blocking_failed:
        print("Result: FAIL (%d blocking check(s) failed)" % blocking_failed)
        return 1
    print("Result: PASS (%d/%d blocking checks passed)" % (len(report.results), len(report.results)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
