#!/usr/bin/env python3
"""Mutation self-tests for tools/spec_check.py.

The suite deliberately mutates one authoritative fixture at a time and
asserts the checker fails/succeeds for the intended reason. When authoritative
prose changes, update the mutation anchor deliberately rather than weakening
spec_check itself.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parents[1]

COPY_ITEMS = [
    "README.md",
    "spec/architecture.md",
    "spec/architecture-lock.md",
    "spec/work-items.md",
    "spec/dependency-graph.md",
    "spec/governance.md",
    "spec/change-control.md",
    "spec/workflow.md",
    "spec/schemas",
    "spec/acr",
    "spec/prompts",
    "spec/architect",
    "tools/spec_check.py",
]

PROMPT_WITH_REFERENCE = """# WORK-000

## Status
PROPOSED

Reference fixture: this prompt is written against Architecture Version 1.0.

## Objective
Mutation-test fixture.
"""

PROMPT_WITH_STATUS_PROSE_REFERENCE = """# WORK-000

## Status
PROPOSED — follows the frozen Architecture Version 1.0 for historical context.

## Objective
Mutation-test fixture.
"""

PROMPT_WITH_STATUS_MARKER_REFERENCE = """# WORK-000

## Status
AUTHORITATIVE ARCHITECT HANDOFF — follows the frozen Architecture Version 1.0

## Objective
Mutation-test fixture.
"""


CASES = [
    {
        "name": "missing-required-frozen-document",
        "ops": [("delete", "spec/architecture.md")],
        "expect_exit": 1,
        "expect_check": "FILES-01",
    },
    {
        "name": "architecture-version-reference-in-process-doc-body",
        "ops": [
            (
                "replace",
                "spec/governance.md",
                "## 4. Terminology",
                "Reference fixture: this governance layer is written against "
                "Architecture Version 1.0.\n\n## 4. Terminology",
            )
        ],
        "expect_exit": 0,
        "expect_check": None,
    },
    {
        # Positive: an ordinary prose reference in the root README must be
        # allowed. This anchor is deliberately tied to the current canonical
        # README wording so a future README rewrite causes a transparent
        # self-test fixture failure rather than silently testing the wrong text.
        "name": "architecture-version-reference-in-readme",
        "ops": [
            (
                "replace",
                "README.md",
                "CI runs the specification consistency checks on every push and pull request.",
                "CI runs the specification consistency checks on every push and pull request.\n\n"
                "The WORK-001 implementation was reviewed against "
                "Architecture Version 1.0.",
            )
        ],
        "expect_exit": 0,
        "expect_check": None,
    },
    {
        "name": "architecture-version-reference-in-new-prompt",
        "ops": [("create", "spec/prompts/WORK-000.md", PROMPT_WITH_REFERENCE)],
        "expect_exit": 0,
        "expect_check": None,
    },
    {
        "name": "architecture-version-status-prose-reference-sentence",
        "ops": [
            (
                "create",
                "spec/prompts/WORK-000.md",
                PROMPT_WITH_STATUS_PROSE_REFERENCE,
            )
        ],
        "expect_exit": 0,
        "expect_check": None,
    },
    {
        "name": "architecture-version-status-prose-reference-marker-line",
        "ops": [
            (
                "create",
                "spec/prompts/WORK-000.md",
                PROMPT_WITH_STATUS_MARKER_REFERENCE,
            )
        ],
        "expect_exit": 0,
        "expect_check": None,
    },
    {
        "name": "frozen-marker-removed",
        "ops": [
            (
                "replace",
                "spec/architecture-lock.md",
                "**FROZEN**",
                "**DRAFT**",
            )
        ],
        "expect_exit": 1,
        "expect_check": "MARK-02",
    },
    {
        "name": "execution-phase-order-violation",
        "ops": [
            (
                "replace",
                "spec/dependency-graph.md",
                "`W038 → W039 → W040`",
                "`W038 → W039 → W040 → W001`",
            )
        ],
        "expect_exit": 1,
        "expect_check": "DEPS-03",
    },
]


def make_copy() -> Path:
    root = Path(tempfile.mkdtemp(prefix="adcos-selftest-"))
    for item in COPY_ITEMS:
        source = REPO_ROOT / item
        destination = root / item
        if source.is_dir():
            shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    return root


def apply_ops(root: Path, ops: List[tuple]) -> None:
    for op in ops:
        kind = op[0]
        path = root / op[1]
        if kind == "delete":
            path.unlink()
        elif kind == "replace":
            _, _, old, new = op
            text = path.read_text(encoding="utf-8")
            count = text.count(old)
            if count != 1:
                raise AssertionError(
                    "mutation anchor %r found %d time(s) in %s (expected exactly 1); "
                    "frozen text may have drifted — update the self-test deliberately"
                    % (old, count, op[1])
                )
            path.write_text(text.replace(old, new, 1), encoding="utf-8")
        elif kind == "create":
            _, _, content = op
            if path.exists():
                raise AssertionError("fixture %s already exists" % op[1])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        else:
            raise AssertionError("unknown operation %r" % (kind,))


def run_checker(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(root / "tools" / "spec_check.py")],
        capture_output=True,
        text=True,
        cwd=str(root),
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


def main() -> int:
    passed = 0
    for case in CASES:
        root = make_copy()
        try:
            apply_ops(root, case["ops"])
            result = run_checker(root)
            output = (result.stdout or "") + (result.stderr or "")
            if result.returncode != case["expect_exit"]:
                raise AssertionError(
                    "%s: expected exit %s, got %s\n%s"
                    % (case["name"], case["expect_exit"], result.returncode, output)
                )
            expected_check = case.get("expect_check")
            if expected_check is not None:
                if "[%s" % expected_check not in output:
                    raise AssertionError(
                        "%s: expected failing check %s not present\n%s"
                        % (case["name"], expected_check, output)
                    )
            passed += 1
        finally:
            shutil.rmtree(root, ignore_errors=True)

    print("spec_check selftest: %d/%d PASS" % (passed, len(CASES)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
