#!/usr/bin/env python3
"""ADCOS schema/registry compatibility self-test (WORK-002).

Deterministic, offline tests for tools/schema_check.py and the
spec/schemas/ registry model, covering the frozen compatibility
requirements of the WORK-002 handoff (spec/prompts/WORK-002.md §8):

1.  a known registry entry validates successfully;
2.  a new additive registry entry can be added without invalidating
    unrelated existing entries;
3.  an unknown future identifier can be represented/encountered without
    corrupting known fields;
4.  an unknown identifier is not silently coerced into another identifier;
5.  a malformed identifier is rejected distinctly from a well-formed but
    unknown identifier;
6.  a technology/profile addition does not require a change to the core
    domain object list;
7.  a future IMT/6G-style access profile can be added without changing
    the core object schemas;
8.  version metadata is validated consistently across schema and registry
    artifacts.

Tree-mutating cases copy the specification tree into a temporary
directory, apply exactly one change, and run the checker there; no
repository file is ever modified.

Invocation (Python 3.8+, standard library only, no network access):

    python3 tools/schema_selftest.py

Exit codes: 0 all cases passed; 1 at least one case failed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from schema_check import (  # noqa: E402
    canonical_json_bytes,
    classify_id,
    load_json,
    validate_instance,
)

COPY_ITEMS: List[str] = ["spec", "tools", ".github", "README.md", ".gitignore"]
FAIL_LINE_RE = __import__("re").compile(r"^\[FAIL    \] (\S+)", __import__("re").MULTILINE)

# ---------------------------------------------------------------------------
# Golden fixtures — valid instances of every domain-object schema
# ---------------------------------------------------------------------------

NODE_FIXTURE: Dict[str, Any] = {
    "node_id": "node:fixture-1",
    "protocol_versions": ["1.0"],
    "software_build_id": "build-fixture",
    "roles": ["endpoint", "relay"],
    "adapters": ["adapter:fixture-a"],
    "capabilities": ["capability.core.multipath"],
    "resource_state": {},
    "trust_state": {},
    "administrative_domains": ["domain:fixture"],
    "hardware_class": "commodity",
}

IDENTITY_FIXTURE: Dict[str, Any] = {
    "node_id": "node:fixture-1",
    "credential_references": ["credential-ref:opaque"],
}

# Compatibility case 3: the containing object carries unknown future
# identifiers (well-formed but unregistered) in its open reference fields
# and must still validate, with the unknown identifiers preserved verbatim.
ADAPTER_FIXTURE: Dict[str, Any] = {
    "adapter_id": "adapter:fixture-a",
    "access_technology_id": "access.3gpp.nr.imt2050",
    "supported_profile_versions": ["1"],
    "capabilities": [
        "capability.core.multipath",
        "capability.core.holographic-relay",
    ],
    "link_metrics": {},
    "lifecycle_controls": {},
    "security_state": {},
    "resource_mapping": {},
    "session_bearer_mapping": {},
    "health": {},
}

CAPABILITY_FIXTURE: Dict[str, Any] = {
    "capability_id": "capability.core.multipath",
    "schema_version": "1.0",
    "provider_identity": "node:fixture-1",
    "validity": {},
    "parameters": {},
    "constraints": {},
    "evidence_references": ["evidence:fixture-1"],
    "signature": "opaque-signature-reference",
}

LINK_FIXTURE: Dict[str, Any] = {
    "link_id": "link:fixture-1",
    "adapters": ["adapter:fixture-a", "adapter:fixture-b"],
    "direction": "bidirectional",
    "state": "up",
}

PATH_FIXTURE: Dict[str, Any] = {
    "path_id": "path:fixture-1",
    "links": ["link:fixture-1"],
    "metrics": {},
    "policy_score": {},
    "confidence": {},
    "expiry": "opaque",
    "failover_options": [],
}

SESSION_FIXTURE: Dict[str, Any] = {
    "session_id": "session:fixture-1",
    "path_bindings": ["path:fixture-1"],
}

RESOURCE_FIXTURE: Dict[str, Any] = {
    "resource_id": "resource:fixture-1",
    "kind": "bandwidth",
    "quantity": {},
    "availability": "reservation-based",
}

INTENT_FIXTURE: Dict[str, Any] = {
    "intent_id": "intent:fixture-1",
    "constraints": [
        {"metric": "bandwidth", "operator": ">=", "value": "20 Mbps"},
        {"metric": "latency", "operator": "<=", "value": "30 ms"},
        {"metric": "privacy", "operator": "=", "value": "end_to_end"},
    ],
}

FEDERATION_FIXTURE: Dict[str, Any] = {
    "federation_id": "federation:fixture-1",
    "peer_identities": ["domain:peer"],
    "trust_policy": {},
    "shared_capabilities": ["capability.core.store-and-forward"],
    "route_policy": {},
    "service_exposure": {},
    "resource_exposure": {},
    "settlement_policy": {},
    "audit_requirements": {},
    "revocation_semantics": {},
}

EVIDENCE_FIXTURE: Dict[str, Any] = {
    "evidence_id": "evidence:fixture-1",
    "evidence_type": "peer-observed",
    "claim": "claim:fixture-1",
    "observer": "node:fixture-1",
}

GOLDEN_FIXTURES: Dict[str, Dict[str, Any]] = {
    "node.schema.json": NODE_FIXTURE,
    "identity.schema.json": IDENTITY_FIXTURE,
    "adapter.schema.json": ADAPTER_FIXTURE,
    "capability.schema.json": CAPABILITY_FIXTURE,
    "link.schema.json": LINK_FIXTURE,
    "path.schema.json": PATH_FIXTURE,
    "session.schema.json": SESSION_FIXTURE,
    "resource.schema.json": RESOURCE_FIXTURE,
    "intent.schema.json": INTENT_FIXTURE,
    "federation.schema.json": FEDERATION_FIXTURE,
    "evidence.schema.json": EVIDENCE_FIXTURE,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_repo_registries() -> Dict[str, Dict[str, Any]]:
    registries: Dict[str, Dict[str, Any]] = {}
    for path in sorted((REPO_ROOT / "spec" / "schemas" / "registries").glob("*.json")):
        value = load_json(path.read_text(encoding="utf-8"))
        registries[value["registry"]] = value
    return registries


def load_repo_schema(name: str) -> Dict[str, Any]:
    return load_json((REPO_ROOT / "spec" / "schemas" / name).read_text(encoding="utf-8"))


def make_copy() -> Path:
    root = Path(tempfile.mkdtemp(prefix="adcos-schema-selftest-"))
    for item in COPY_ITEMS:
        source = REPO_ROOT / item
        destination = root / item
        if source.is_dir():
            shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(source, destination)
    return root


def run_checker(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(root / "tools" / "schema_check.py")],
        capture_output=True,
        text=True,
        cwd=str(root),
    )


def edit_registry(root: Path, registry_file: str, mutate) -> None:
    """Load a registry from the temp tree, apply mutate(value), rewrite canonically."""
    path = root / "spec" / "schemas" / "registries" / registry_file
    value = load_json(path.read_text(encoding="utf-8"))
    mutate(value)
    path.write_bytes(canonical_json_bytes(value))


def edit_json_file(root: Path, rel_path: str, mutate) -> None:
    path = root / rel_path
    value = load_json(path.read_text(encoding="utf-8"))
    mutate(value)
    path.write_bytes(canonical_json_bytes(value))


# ---------------------------------------------------------------------------
# In-process cases (no tree mutation)
# ---------------------------------------------------------------------------

def case_golden_fixtures(results: List[tuple]) -> None:
    ok = True
    detail = ""
    for schema_name, fixture in sorted(GOLDEN_FIXTURES.items()):
        errors = validate_instance(fixture, load_repo_schema(schema_name))
        if errors:
            ok = False
            detail = "%s: %s" % (schema_name, errors[0])
            break
    # Compatibility case 3: unknown identifiers survive verbatim.
    if ok:
        if ADAPTER_FIXTURE["access_technology_id"] != "access.3gpp.nr.imt2050":
            ok = False
            detail = "unknown identifier was not preserved verbatim"
    # Compatibility case 1: a known entry classifies as known.
    if ok:
        registries = load_repo_registries()
        access = registries["adcos.access-profile-registry"]
        if classify_id(access["id_grammar"], access["entries"], "access.ieee.80211") != "known":
            ok = False
            detail = "registered access ID did not classify as known"
    results.append(("golden-fixtures-validate-known-entries", ok, detail or "11/11 schemas, known IDs classify known"))


def case_schema_validation_negatives(results: List[tuple]) -> None:
    node_schema = load_repo_schema("node.schema.json")
    resource_schema = load_repo_schema("resource.schema.json")
    capability_schema = load_repo_schema("capability.schema.json")
    link_schema = load_repo_schema("link.schema.json")
    checks = [
        ("missing-required", validate_instance(
            {k: v for k, v in NODE_FIXTURE.items() if k != "node_id"}, node_schema)),
        ("wrong-type", validate_instance(
            dict(NODE_FIXTURE, protocol_versions="1.0"), node_schema)),
        ("enum-violation", validate_instance(
            dict(RESOURCE_FIXTURE, kind="warp-drive"), resource_schema)),
        ("pattern-violation", validate_instance(
            dict(CAPABILITY_FIXTURE, schema_version="1"), capability_schema)),
        ("enum-case-sensitive", validate_instance(
            dict(LINK_FIXTURE, state="UP"), link_schema)),
    ]
    ok = all(errors for _, errors in checks)
    detail = ", ".join(name for name, errors in checks if not errors) or "all 5 rejected"
    results.append(("invalid-instances-rejected", ok, "rejected: " + detail if ok else "failed to reject: " + detail))


def case_unknown_vs_malformed(results: List[tuple]) -> None:
    registries = load_repo_registries()
    access = registries["adcos.access-profile-registry"]
    capability = registries["adcos.capability-registry"]

    unknown_ids = [
        "access.3gpp.nr.imt2050",
        "access.vendor.private-network",
        "access.itu.imt2035",
    ]
    malformed_ids = [
        "Access.3GPP.NR",
        "access..bad",
        "access.",
        "adcos.node",
        "",
        "access.ieee.80211 ",
    ]
    ok = True
    detail = ""
    for identifier in unknown_ids:
        if classify_id(access["id_grammar"], access["entries"], identifier) != "unknown":
            ok, detail = False, "well-formed ID %r did not classify as unknown" % identifier
            break
    if ok:
        for identifier in malformed_ids:
            if classify_id(access["id_grammar"], access["entries"], identifier) != "invalid":
                ok, detail = False, "malformed ID %r did not classify as invalid" % identifier
                break
    if ok:
        if classify_id(capability["id_grammar"], capability["entries"], "capability.core.quantum-relay") != "unknown":
            ok, detail = False, "unknown capability ID misclassified"
    results.append(("unknown-distinct-from-malformed", ok, detail or "3 unknown + 6 invalid correctly distinguished"))


def case_no_coercion(results: List[tuple]) -> None:
    registries = load_repo_registries()
    access = registries["adcos.access-profile-registry"]
    capability = registries["adcos.capability-registry"]
    ok = True
    detail = ""
    near_misses = [
        (access, "access.3gpp.nr.imt2020x"),   # one char off a registered ID
        (access, "access.3gpp.nr.imt20200"),   # digit extension of a registered ID
        (access, "access.generic.future-unknown"),
        (capability, "capability.core.multipath2"),
    ]
    for registry, identifier in near_misses:
        classification = classify_id(registry["id_grammar"], registry["entries"], identifier)
        if classification != "unknown":
            ok, detail = False, "%r classified %r instead of unknown" % (identifier, classification)
            break
        if identifier in registry["entries"]:
            ok, detail = False, "%r was silently registered" % identifier
            break
    results.append(("unknown-identifiers-not-coerced", ok, detail or "4 near-miss IDs remain unknown, never coerced"))


# ---------------------------------------------------------------------------
# Tree-mutating cases
# ---------------------------------------------------------------------------

def tree_case(results: List[tuple], name: str, mutate, expect_exit: int, expect_check=None, post=None) -> None:
    root = make_copy()
    try:
        mutate(root)
        process = run_checker(root)
        exit_code = process.returncode
        failed = FAIL_LINE_RE.findall(process.stdout + process.stderr)
        ok = exit_code == expect_exit
        detail = "exit %d" % exit_code
        if expect_check is not None and expect_check not in failed:
            ok = False
        if expect_check is not None:
            detail += ", failed checks: %s" % (", ".join(failed) or "none")
        if ok and post is not None:
            post_error = post(root)
            if post_error:
                ok = False
                detail += ", post: " + post_error
        results.append((name, ok, detail))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main() -> int:
    results: List[tuple] = []

    # Baseline: unmutated tree passes.
    tree_case(results, "baseline-unmutated-tree", lambda root: None, 0)

    # In-process cases.
    case_golden_fixtures(results)
    case_schema_validation_negatives(results)
    case_unknown_vs_malformed(results)
    case_no_coercion(results)

    # Compatibility case 2: additive access entry, existing entries unaffected.
    def add_access_entry(root: Path) -> None:
        def mutate(value: Dict[str, Any]) -> None:
            assert "access.example.hyperspectral" not in value["entries"]
            value["entries"]["access.example.hyperspectral"] = {
                "description": "Additive test entry.",
                "status": "active",
            }
        edit_registry(root, "access-profile-registry.json", mutate)
    tree_case(
        results,
        "additive-access-entry-accepted",
        add_access_entry,
        0,
        post=lambda root: None if len(load_json((root / "spec/schemas/registries/access-profile-registry.json").read_text(encoding="utf-8"))["entries"]) == 12 else "entry count changed unexpectedly",
    )

    # Compatibility case 2: additive core-scoped capability entry.
    def add_core_capability(root: Path) -> None:
        def mutate(value: Dict[str, Any]) -> None:
            value["entries"]["capability.core.reliable-latency"] = {
                "description": "Additive test entry.",
                "scope": "core",
                "status": "active",
            }
        edit_registry(root, "capability-registry.json", mutate)
    tree_case(results, "additive-core-capability-accepted", add_core_capability, 0)

    # Additive profile-scoped capability with resolving profile_ref (SCHEMA-06 positive path).
    def add_profile_capability(root: Path) -> None:
        def mutate(value: Dict[str, Any]) -> None:
            value["entries"]["capability.profile.imt2020.sub6-bandwidth"] = {
                "description": "Additive profile-scoped test entry.",
                "scope": "profile",
                "status": "active",
                "profile_ref": "access.3gpp.nr.imt2020",
            }
        edit_registry(root, "capability-registry.json", mutate)
    tree_case(results, "additive-profile-capability-resolves", add_profile_capability, 0)

    # Negative: profile-scoped entry with non-resolving profile_ref.
    def add_bad_profile_capability(root: Path) -> None:
        def mutate(value: Dict[str, Any]) -> None:
            value["entries"]["capability.profile.imt2020.broken"] = {
                "description": "Broken reference.",
                "scope": "profile",
                "status": "active",
                "profile_ref": "access.does.not.exist",
            }
        edit_registry(root, "capability-registry.json", mutate)
    tree_case(results, "profile-capability-unresolved-ref-rejected", add_bad_profile_capability, 1, "SCHEMA-06")

    # Compatibility cases 6+7: future profile addition requires no core change.
    def add_future_profile(root: Path) -> None:
        def mutate(value: Dict[str, Any]) -> None:
            value["entries"]["access.3gpp.nr.imt2035"] = {
                "description": "Future-generation additive test entry.",
                "status": "active",
            }
        edit_registry(root, "access-profile-registry.json", mutate)

    def core_unchanged(root: Path) -> Optional[str]:
        for rel in ["spec/schemas/registries/domain-object-registry.json"] + [
            "spec/schemas/%s" % name for name in GOLDEN_FIXTURES
        ]:
            if (root / rel).read_bytes() != (REPO_ROOT / rel).read_bytes():
                return "%s changed" % rel
        return None

    tree_case(
        results,
        "future-profile-added-without-core-change",
        add_future_profile,
        0,
        post=core_unchanged,
    )

    # Negative: malformed registry ID rejected distinctly (SCHEMA-03).
    def add_malformed_access_id(root: Path) -> None:
        def mutate(value: Dict[str, Any]) -> None:
            value["entries"]["Access..Bad"] = {
                "description": "Malformed ID.",
                "status": "active",
            }
        edit_registry(root, "access-profile-registry.json", mutate)
    tree_case(results, "malformed-registry-id-rejected", add_malformed_access_id, 1, "SCHEMA-03")

    # Negative: technology token in a core identifier rejected (SCHEMA-04).
    def add_tech_core_capability(root: Path) -> None:
        def mutate(value: Dict[str, Any]) -> None:
            value["entries"]["capability.core.5g-fastpath"] = {
                "description": "Non-neutral core capability.",
                "scope": "core",
                "status": "active",
            }
        edit_registry(root, "capability-registry.json", mutate)
    tree_case(results, "core-id-technology-token-rejected", add_tech_core_capability, 1, "SCHEMA-04")

    # Negative: silently adding a core noun rejected (SCHEMA-05).
    def add_extra_core_noun(root: Path) -> None:
        def mutate(value: Dict[str, Any]) -> None:
            value["entries"]["adcos.baseband-unit"] = {
                "description": "Not a frozen noun.",
                "noun": "BasebandUnit",
                "schema_id": "urn:adcos:schema:baseband-unit",
                "schema_ref": "spec/schemas/node.schema.json",
                "schema_version": "1.0",
                "source_sections": ["test"],
                "status": "active",
            }
        edit_registry(root, "domain-object-registry.json", mutate)
    tree_case(results, "extra-core-noun-rejected", add_extra_core_noun, 1, "SCHEMA-05")

    # Compatibility case 8: version metadata consistency negatives.
    def bad_schema_version(root: Path) -> None:
        def mutate(value: Dict[str, Any]) -> None:
            value["schema_version"] = "1"
        edit_json_file(root, "spec/schemas/node.schema.json", mutate)
    tree_case(results, "malformed-schema-version-rejected", bad_schema_version, 1, "SCHEMA-02")

    def future_architecture_version(root: Path) -> None:
        def mutate(value: Dict[str, Any]) -> None:
            value["architecture_version"] = "2.0"
        edit_json_file(root, "spec/schemas/node.schema.json", mutate)
    tree_case(results, "future-architecture-version-rejected", future_architecture_version, 1, "SCHEMA-02")

    def mismatched_entry_version(root: Path) -> None:
        def mutate(value: Dict[str, Any]) -> None:
            value["entries"]["adcos.node"]["schema_version"] = "9.9"
        edit_registry(root, "domain-object-registry.json", mutate)
    tree_case(results, "registry-schema-version-mismatch-rejected", mismatched_entry_version, 1, "SCHEMA-05")

    # Negative: non-canonical formatting rejected (SCHEMA-01).
    def non_canonical(root: Path) -> None:
        path = root / "spec/schemas/registries/capability-registry.json"
        value = load_json(path.read_text(encoding="utf-8"))
        path.write_text(json.dumps(value, indent=4, sort_keys=False) + "\n", encoding="utf-8")
    tree_case(results, "non-canonical-formatting-rejected", non_canonical, 1, "SCHEMA-01")

    # Negative: duplicate JSON keys rejected (SCHEMA-01).
    def duplicate_keys(root: Path) -> None:
        path = root / "spec/schemas/registries/capability-registry.json"
        text = path.read_text(encoding="utf-8")
        text = text.replace(
            '"schema_version": "1.0",',
            '"schema_version": "1.0",\n  "schema_version": "1.0",',
            1,
        )
        path.write_text(text, encoding="utf-8")
    tree_case(results, "duplicate-json-keys-rejected", duplicate_keys, 1, "SCHEMA-01")

    # WORK-003 negatives (SCHEMA-07: protocol artifact consistency).
    def broken_envelope_ref(root: Path) -> None:
        def mutate(value: Dict[str, Any]) -> None:
            value["envelope"]["schema_ref"] = "spec/schemas/missing.schema.json"
        edit_json_file(root, "spec/schemas/protocol.json", mutate)
    tree_case(results, "protocol-envelope-ref-broken-rejected", broken_envelope_ref, 1, "SCHEMA-07")

    def grammar_mismatch(root: Path) -> None:
        def mutate(value: Dict[str, Any]) -> None:
            value["message_type_grammar"] = "^z[a-z.]*$"
        edit_json_file(root, "spec/schemas/protocol.json", mutate)
    tree_case(results, "protocol-grammar-mismatch-rejected", grammar_mismatch, 1, "SCHEMA-07")

    def premature_codec_status(root: Path) -> None:
        def mutate(value: Dict[str, Any]) -> None:
            value["codecs"]["compact-deterministic-cbor"]["status"] = "normative"
        edit_json_file(root, "spec/schemas/protocol.json", mutate)
    tree_case(results, "compact-codec-prematurely-normative-rejected", premature_codec_status, 1, "SCHEMA-07")

    # Output.
    print("ADCOS schema/registry compatibility self-test")
    print("=" * 72)
    for name, ok, detail in results:
        print("[%s] %-46s %s" % ("ok  " if ok else "FAIL", name, detail))
    print("-" * 72)
    passed = sum(1 for _, ok, _ in results if ok)
    if passed == len(results):
        print("Result: PASS (%d/%d cases)" % (passed, len(results)))
        return 0
    print("Result: FAIL (%d/%d cases passed)" % (passed, len(results)))
    return 1


if __name__ == "__main__":
    sys.exit(main())
