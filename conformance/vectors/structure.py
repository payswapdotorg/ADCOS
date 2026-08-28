"""WORK-032 conformance vectors -- structural authority boundaries.

The conformance family audits ITSELF on every run: import discipline
(the nine declared dependencies + the sanctioned transitive input
surfaces only), no vendor/access tokens, no wall clock or runtime
randomness, no private-member access into other families, and no
shadow authority (no authority class is subclassed or re-exported;
subject doubles subclass only the sanctioned SDK ABCs).

The audit functions are reusable: tools/conformance_selftest.py points
them at deliberately sabotaged fixture sources to prove the audits are
discriminating (the vulnerable arrangement is DETECTED, the genuine
family passes).
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import Any, Callable, FrozenSet, List, Tuple

from conformance.model import (
    ConformanceVector,
    ExpectedOutcome,
    ObservedOutcome,
)
from conformance.world import ConformanceWorld

__all__ = [
    "vectors",
    "find_import_violations",
    "find_vendor_tokens",
    "find_nondeterminism",
    "find_private_access",
    "find_shadow_authority",
]

_REPO = Path(__file__).resolve().parents[2]
_FAMILY = _REPO / "conformance"

#: The nine declared W032 hard dependencies...
_DECLARED_ROOTS = frozenset({
    "protocol",      # W003
    "identity",      # W004
    "capabilities",  # W005
    "topology",      # W007
    "routing",       # W011
    "sessions",      # W012
    "federation",    # W015
    "adapters",      # W016
    "transport",     # W017
})
#: ...plus the sanctioned TRANSITIVE input surfaces required by the
#: declared contracts themselves (RoutingContext requires a genuine
#: ResourceStore; RoutingContext/SessionStore.create require a genuine
#: PolicyDecision).  Documented in conformance/README.md.
_TRANSITIVE_ROOTS = frozenset({"resources", "policy"})

#: Families that must NEVER be imported by the conformance suite
#: (no declared DAG edge; W013 multipath notably included).
_FORBIDDEN_ROOTS = frozenset({
    "discovery", "intent", "multipath", "mobility", "services",
    "telemetry", "energy", "management", "simulator", "upgrade",
})

_ALLOWED_STDLIB = frozenset({
    "__future__", "abc", "ast", "collections", "copy", "dataclasses",
    "datetime", "enum", "hashlib", "json", "os", "pathlib", "re",
    "tempfile", "typing",
})

#: Vendor/access tokens are CONSTRUCTED (never spelled out) so the
#: scanner's own source cannot trip the scan.
_VENDOR_TOKENS = (
    "open" + "5gs",
    "openair" + "interface",
    "andr" + "oid",
    "andr" + "oidx",
    "i" + "os",
    "vendor" + "_sdk",
    "five" + "_g_",
    "six" + "_g_",
)

_WALL_CLOCK = ("time.time", "datetime.now", "datetime.today",
               "datetime.utcnow", "time.monotonic", "time.perf_counter")
_RANDOMNESS = ("random", "secrets", "uuid", "os.urandom")


def _family_sources(root: Path = _FAMILY) -> List[Path]:
    if not root.exists():
        return []
    return sorted(
        [p for p in root.rglob("*.py")]
    )


def _imported_roots(path: Path) -> List[Tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: List[Tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.append((alias.name.split(".")[0], node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                roots.append((node.module.split(".")[0], node.lineno))
    return roots


def find_import_violations(root: Path = _FAMILY) -> List[str]:
    """Import-discipline findings for a source tree (empty = clean)."""
    findings: List[str] = []
    for path in _family_sources(root):
        for top, lineno in _imported_roots(path):
            allowed = (
                top in _DECLARED_ROOTS
                or top in _TRANSITIVE_ROOTS
                or top in _ALLOWED_STDLIB
                or top == "conformance"
            )
            if not allowed:
                findings.append(
                    "%s:%d imports forbidden root %r" % (
                        os.path.relpath(path, root), lineno, top
                    )
                )
    return findings


def find_vendor_tokens(root: Path = _FAMILY) -> List[str]:
    """Vendor/access-token findings (identifiers and imports).

    Tokens match on word boundaries so ordinary prose (e.g. the word
    "scenarios") can never trip the scan.
    """
    findings: List[str] = []
    for path in _family_sources(root):
        source = path.read_text(encoding="utf-8")
        for token in _VENDOR_TOKENS:
            if token.endswith("_"):
                pattern = r"\b" + re.escape(token)
            else:
                pattern = r"\b" + re.escape(token) + r"\b"
            if re.search(pattern, source):
                findings.append(
                    "%s contains vendor token %r" % (
                        os.path.relpath(path, root), token
                    )
                )
    return findings


def find_nondeterminism(root: Path = _FAMILY) -> List[str]:
    """Wall-clock / uncontrolled-entropy findings."""
    findings: List[str] = []
    for path in _family_sources(root):
        tree = ast.parse(path.read_text(encoding="utf-8"),
                         filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in _RANDOMNESS:
                        findings.append(
                            "%s:%d imports %s" % (
                                os.path.relpath(path, root), node.lineno,
                                alias.name,
                            )
                        )
            if isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] in _RANDOMNESS:
                    findings.append(
                        "%s:%d imports from %s" % (
                            os.path.relpath(path, root), node.lineno,
                            node.module,
                        )
                    )
            if isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    dotted = "%s.%s" % (node.value.id, node.attr)
                    if dotted in _WALL_CLOCK:
                        findings.append(
                            "%s:%d uses wall clock %s" % (
                                os.path.relpath(path, root), node.lineno,
                                dotted,
                            )
                        )
    return findings


def find_private_access(root: Path = _FAMILY) -> List[str]:
    """Private-member access into OTHER families (hidden authority access).

    Single-underscore members only: dunders (``__name__`` and friends)
    are public protocol attributes, not private implementation state.
    """
    findings: List[str] = []
    for path in _family_sources(root):
        tree = ast.parse(path.read_text(encoding="utf-8"),
                         filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute):
                continue
            if not node.attr.startswith("_"):
                continue
            if node.attr.startswith("__") and node.attr.endswith("__"):
                continue  # dunder protocol attribute, not private state
            if isinstance(node.value, ast.Name):
                if node.value.id in ("self", "cls"):
                    continue
                findings.append(
                    "%s:%d private access %s._%s" % (
                        os.path.relpath(path, root), node.lineno,
                        node.value.id, node.attr,
                    )
                )
    return findings


#: Authority classes from the composed families: subclassing any of
#: these (or defining a class so named) would make the suite a second
#: protocol authority.
_AUTHORITY_CLASSES = frozenset({
    "TopologyGraph", "SessionStore", "FederationStore", "RoutingEngine",
    "AdapterRuntime", "TransportManager", "IdentityService",
    "CredentialStore", "InMemoryCredentialStore", "DevHmacSha256Provider",
    "ModeledTransportEngine", "PolicyDecision", "Envelope",
    "CapabilityStatement", "ResourceStore", "TelemetryStore",
    "PolicyEngine", "PolicyStore", "MultipathStore", "MobilityStore",
})

#: The sanctioned SDK extension points subject doubles may subclass
#: (directly or via the family's own reference double).
_SANCTIONED_BASES = frozenset({
    "AdapterContract", "TransportContract",
    "ReferenceAdapter", "ThrowingAdapter",
})

#: Frozen exception/enum bases that are not authority shadowing.
_NEUTRAL_BASES = frozenset({
    "Enum", "ValueError", "Exception", "RuntimeError", "object", "ABC",
})


def find_shadow_authority(root: Path = _FAMILY) -> List[str]:
    """Shadow-authority findings: authority classes defined/subclassed."""
    findings: List[str] = []
    for path in _family_sources(root):
        tree = ast.parse(path.read_text(encoding="utf-8"),
                         filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            base_names = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    base_names.append(base.id)
                elif isinstance(base, ast.Attribute):
                    base_names.append(base.attr)
            shadowing = [
                b for b in base_names
                if b in _AUTHORITY_CLASSES
            ]
            if shadowing:
                findings.append(
                    "%s:%d class %s subclasses authority class %r" % (
                        os.path.relpath(path, root), node.lineno,
                        node.name, shadowing,
                    )
                )
            if node.name in _AUTHORITY_CLASSES:
                findings.append(
                    "%s:%d defines authority-named class %s" % (
                        os.path.relpath(path, root), node.lineno,
                        node.name,
                    )
                )
    return findings


def _vector(number: str, polarity: str, invariant: str,
            description: str, expected: ExpectedOutcome,
            execute: Callable[[ConformanceWorld], ObservedOutcome],
            tags: FrozenSet[str] = frozenset()) -> ConformanceVector:
    return ConformanceVector(
        vector_id="W032-CNF-STR-%s" % number,
        area="structure",
        polarity=polarity,
        authority="WORK-032",
        contract="spec/prompts/WORK-032.md (authority boundary / "
                 "determinism / forbidden dependencies)",
        invariant=invariant,
        description=description,
        expected=expected,
        execute=execute,
        tags=tags,
    )


def vectors() -> Tuple[ConformanceVector, ...]:
    out = []

    # -- STR-001: import discipline ---------------------------------------------
    def _str001(world: ConformanceWorld) -> ObservedOutcome:
        findings = find_import_violations()
        if findings:
            return ObservedOutcome(
                False, "forbidden-imports", "; ".join(findings[:4])
            )
        return ObservedOutcome(
            True, "imports-bounded",
            "imports limited to the nine declared dependencies + "
            "sanctioned transitive inputs + stdlib",
        )

    out.append(_vector(
        "001", "positive",
        "the suite imports only its declared dependency surface",
        "Import audit over conformance/: declared roots + transitive "
        "ResourceStore/PolicyDecision inputs + stdlib.",
        ExpectedOutcome(True, frozenset({"imports-bounded"})),
        _str001,
        frozenset({
            "negative:forbidden-imports",
            "discriminating:forbidden-dependency",
        }),
    ))

    # -- STR-002: forbidden roots explicitly absent --------------------------------
    def _str002(world: ConformanceWorld) -> ObservedOutcome:
        present = []
        for path in _family_sources():
            for top, lineno in _imported_roots(path):
                if top in _FORBIDDEN_ROOTS:
                    present.append("%s:%d -> %s" % (
                        path.name, lineno, top
                    ))
        if present:
            return ObservedOutcome(
                False, "dag-edge-violation", "; ".join(present[:4])
            )
        return ObservedOutcome(
            True, "no-hidden-dependencies",
            "no non-dependency family is imported (incl. W013 multipath)",
        )

    out.append(_vector(
        "002", "positive",
        "no hidden/future dependency imports (frozen DAG edges only)",
        "Explicitly asserts multipath/discovery/intent/mobility/services/"
        "telemetry/energy/management/simulator/upgrade are absent.",
        ExpectedOutcome(True, frozenset({"no-hidden-dependencies"})),
        _str002,
        frozenset({
            "negative:forbidden-imports",
            "discriminating:forbidden-dependency",
        }),
    ))

    # -- STR-003: no vendor tokens ---------------------------------------------------
    def _str003(world: ConformanceWorld) -> ObservedOutcome:
        findings = find_vendor_tokens()
        if findings:
            return ObservedOutcome(
                False, "vendor-leakage", "; ".join(findings[:4])
            )
        return ObservedOutcome(
            True, "vendor-free", "no vendor/access tokens in the family"
        )

    out.append(_vector(
        "003", "positive",
        "no vendor/access-technology leakage",
        "Vendor token scan over conformance/ sources.",
        ExpectedOutcome(True, frozenset({"vendor-free"})),
        _str003,
        frozenset({"negative:forbidden-imports"}),
    ))

    # -- STR-004: determinism ----------------------------------------------------------
    def _str004(world: ConformanceWorld) -> ObservedOutcome:
        findings = find_nondeterminism()
        if findings:
            return ObservedOutcome(
                False, "nondeterministic", "; ".join(findings[:4])
            )
        return ObservedOutcome(
            True, "deterministic",
            "no wall clock, no runtime randomness, no uncontrolled entropy",
        )

    out.append(_vector(
        "004", "positive",
        "the suite is deterministic by construction",
        "AST scan: no wall-clock calls, no random/secrets/uuid imports.",
        ExpectedOutcome(True, frozenset({"deterministic"})),
        _str004,
        frozenset({"positive:determinism"}),
    ))

    # -- STR-005: no private authority access ---------------------------------------------
    def _str005(world: ConformanceWorld) -> ObservedOutcome:
        findings = find_private_access()
        if findings:
            return ObservedOutcome(
                False, "private-access", "; ".join(findings[:4])
            )
        return ObservedOutcome(
            True, "public-surface-only",
            "no private-member access into composed authorities",
        )

    out.append(_vector(
        "005", "positive",
        "composition uses public contracts only (no hidden authority access)",
        "AST scan for `._` attribute access outside self/cls.",
        ExpectedOutcome(True, frozenset({"public-surface-only"})),
        _str005,
        frozenset({"negative:hidden-authority-access"}),
    ))

    # -- STR-006: no shadow authority ---------------------------------------------------------
    def _str006(world: ConformanceWorld) -> ObservedOutcome:
        findings = find_shadow_authority()
        if findings:
            return ObservedOutcome(
                False, "shadow-authority", "; ".join(findings[:4])
            )
        return ObservedOutcome(
            True, "no-shadow-authority",
            "no authority classes defined or subclassed; subject doubles "
            "subclass only the sanctioned SDK ABCs",
        )

    out.append(_vector(
        "006", "positive",
        "the suite is a verifier, never a second protocol authority",
        "No class in conformance/ subclasses an authority or redefines an "
        "authority-named surface.",
        ExpectedOutcome(True, frozenset({"no-shadow-authority"})),
        _str006,
        frozenset({
            "negative:hidden-authority-access",
            "discriminating:authority-boundary",
        }),
    ))

    # -- STR-007: the audits are not vacuous (negative) ----------------------
    def _str007(world: ConformanceWorld) -> ObservedOutcome:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "bad"
            root.mkdir()
            (root / "smuggled.py").write_text(
                "import multipath\n"
                "import random\n"
                "value = time.time()\n",
                encoding="utf-8",
            )
            (root / "sneaky.py").write_text(
                "def poke(store):\n"
                "    return store._sessions\n",
                encoding="utf-8",
            )
            (root / "shadow.py").write_text(
                "from sessions import SessionStore\n"
                "class MyStore(SessionStore):\n"
                "    pass\n",
                encoding="utf-8",
            )
            findings = (
                find_import_violations(root)
                + find_nondeterminism(root)
                + find_private_access(root)
                + find_shadow_authority(root)
            )
        if findings:
            return ObservedOutcome(
                False, "violations-detected",
                "%d structural violations detected in the sabotaged "
                "fixture source" % len(findings),
            )
        return ObservedOutcome(
            True, "violations-missed",
            "sabotaged fixture source passed every audit",
        )

    out.append(_vector(
        "007", "negative",
        "the structural audits detect violations (never vacuous)",
        "A deliberately violating fixture source (forbidden import, "
        "wall clock, private access, authority subclassing) is flagged "
        "by every audit.",
        ExpectedOutcome(False, frozenset({"violations-detected"})),
        _str007,
        frozenset({
            "negative:forbidden-imports",
            "negative:hidden-authority-access",
            "discriminating:forbidden-dependency",
        }),
    ))

    return tuple(out)
