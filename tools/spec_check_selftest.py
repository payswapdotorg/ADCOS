#!/usr/bin/env python3
"""ADCOS specification checker self-test.

Deterministic, offline negative tests for tools/spec_check.py, introduced
by WORK-001 correction cycle 2. Each case copies the repository's
specification tree into a temporary directory, applies exactly one
violation, runs the checker, and asserts the expected outcome. Temporary
directories are always removed; no repository file is ever modified.

Invocation (Python 3.8+, standard library only, no network access):

    python3 tools/spec_check_selftest.py

Exit codes:
    0  all cases passed
    1  at least one case failed

Cases include the negative test required by the Architect review of
PR #1 (correction cycle 2): injecting an `Architecture Version 1.0`
declaration into a process document must cause VERS-01 to fail.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]

# Tracked tree items required for the checker to be representative.
COPY_ITEMS: List[str] = ["spec", "tools", ".github", "README.md", ".gitignore"]

FAIL_LINE_RE = re.compile(r"^\[FAIL    \] (\S+)", re.MULTILINE)

# (name, target path, mutation, expected exit, expected failing check)
# mutation None -> delete the target file; otherwise (old, new) exactly-once
# string replacement.
Case = Tuple[str, str, Optional[Tuple[str, str]], int, Optional[str]]

CASES: List[Case] = [
    (
        "baseline-unmutated-tree",
        "",
        None,
        0,
        None,
    ),
    (
        "missing-frozen-document",
        "spec/architecture-lock.md",
        None,
        1,
        "FILES-01",
    ),
    (
        "dependency-cycle-injected",
        "spec/work-items.md",
        ("Dependencies: none", "Dependencies: WORK-040"),
        1,
        "DEPS-02",
    ),
    (
        "unknown-work-item-reference",
        "spec/work-items.md",
        ("Dependencies: WORK-002", "Dependencies: WORK-099"),
        1,
        "DEPS-01",
    ),
    (
        "protocol-version-in-architecture-status",
        "spec/architecture.md",
        (
            "**FROZEN — Architecture Version 1.0**",
            "**FROZEN — Architecture Version 1.0, Protocol Version 1.0**",
        ),
        1,
        "VERS-01",
    ),
    (
        "architecture-version-declared-in-process-doc",
        "spec/workflow.md",
        (
            "**ACTIVE — Process Authority**",
            "**ACTIVE — Process Authority (Architecture Version 1.0)**",
        ),
        1,
        "VERS-01",
    ),
    (
        "architecture-version-declared-in-readme",
        "README.md",
        ("## Specification governance", "## Specification governance (Architecture Version 1.0)"),
        1,
        "VERS-01",
    ),
    (
        "frozen-marker-removed",
        "spec/architecture-lock.md",
        ("**FROZEN**", "**DRAFT**"),
        1,
        "MARK-02",
    ),
    (
        "execution-phase-order-violation",
        "spec/dependency-graph.md",
        ("`W038 → W039 → W040`", "`W038 → W039 → W040 → W001`"),
        1,
        "DEPS-03",
    ),
]


def make_copy() -> Path:
    root = Path(tempfile.mkdtemp(prefix="adcos-selftest-"))
    for item in COPY_ITEMS:
        source = REPO_ROOT / item
        destination = root / item
        if source.is_dir():
            shutil.copytree(
                source, destination, ignore=shutil.ignore_patterns("__pycache__")
            )
        else:
            shutil.copy2(source, destination)
    return root


def apply_mutation(root: Path, target: str, mutation: Optional[Tuple[str, str]]) -> None:
    path = root / target
    if mutation is None:
        path.unlink()
        return
    old, new = mutation
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise AssertionError(
            "mutation anchor %r found %d time(s) in %s (expected exactly 1); "
            "frozen text may have drifted — update the self-test deliberately"
            % (old, count, target)
        )
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def run_checker(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(root / "tools" / "spec_check.py")],
        capture_output=True,
        text=True,
        cwd=str(root),
    )


def main() -> int:
    results: List[Tuple[str, bool, str]] = []
    for name, target, mutation, expected_exit, expected_check in CASES:
        root = make_copy()
        try:
            if target:
                apply_mutation(root, target, mutation)
            process = run_checker(root)
            exit_code = process.returncode
            output = process.stdout + process.stderr
            failed_checks = FAIL_LINE_RE.findall(output)
            ok = exit_code == expected_exit
            detail = "exit %d" % exit_code
            if expected_check is not None:
                if expected_check not in failed_checks:
                    ok = False
                detail += ", failed checks: %s" % (", ".join(failed_checks) or "none")
            results.append((name, ok, detail))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    print("ADCOS specification checker self-test")
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
