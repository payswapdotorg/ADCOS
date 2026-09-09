#!/usr/bin/env python3
"""Mutation self-tests for tools/spec_check.py.

Baseline-relative mutation testing: every case copies the repository tree
(minus .git), applies exactly one change, runs the checker, and asserts the
effect of that change RELATIVE TO the unmutated baseline of the same tree.

Why baseline-relative: tools/spec_check.py is the legacy frozen-specification
compatibility audit. Under the Architecture 1.1 transition the live governance
state has legitimately evolved beyond the legacy checker's frozen historical
model (post-snapshot gate Work Items per ACR-013, evolved DEC record shapes),
so the legacy checker may legitimately FAIL on the live repository — CI runs
it as a non-blocking compatibility audit for exactly that reason. The
self-test therefore must not require a globally clean repository. It verifies
the property that actually matters: the checker still DETECTS and still ALLOWS
exactly the mutations each case describes.

  - positive case: the mutation introduces NO new failing check (no check may
    transition PASS -> FAIL, SKIP -> FAIL, or absent -> FAIL vs baseline);
  - negative case: the named check must be PASS at baseline and FAIL after
    the mutation — a genuine detection caused by the mutation, never a
    pre-existing failure masquerading as detection.

When authoritative prose changes, update the mutation anchor deliberately
rather than weakening spec_check itself. The fixture copier mirrors the full
repository tree so nested authoritative paths remain executable in an
isolated temporary checkout.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]

COPY_IGNORE = shutil.ignore_patterns(".git", "__pycache__")

CHECK_LINE_RE = re.compile(r"^\[(PASS|FAIL|SKIP)\s*\]\s+(\S+)")


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


CASES: List[dict] = [
    {
        "name": "missing-required-frozen-document",
        "ops": [("delete", "spec/architecture.md")],
        "expect_check": "FILES-01",
    },
    {
        "name": "missing-persistent-architect-artifact",
        "ops": [("delete", "spec/architect/review-protocol.md")],
        "expect_check": "ARCH-01",
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
    },
    {
        "name": "architecture-version-reference-in-new-prompt",
        "ops": [("create", "spec/prompts/WORK-000.md", PROMPT_WITH_REFERENCE)],
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
    },
    {
        "name": "frozen-marker-removed",
        "ops": [
            # anchor updated for the Architecture 1.1 promotion (M001): the
            # canonical lock file now carries its freeze status in a
            # '## Status' section; the mutation removes the FROZEN marker.
            (
                "replace",
                "spec/architecture-lock.md",
                "FROZEN — Architecture Version 1.1 locks.",
                "DRAFT — Architecture Version 1.1 locks.",
            )
        ],
        "expect_check": "MARK-02",
    },
    {
        # Retired-with-reason (M001 promotion): the legacy DEPS-03
        # execution-phase parser targets the 1.0 '### Phase N' structure,
        # which now lives only in the archived
        # spec/history/dependency-graph-1.0.md. On the promoted 1.1
        # successor graph the phase check passes vacuously, so a phase-order
        # mutation can no longer prove detection. The slot is replaced with
        # an equivalent detection case on the other canonical FROZEN
        # document, preserving the MARK-02 detection proof.
        "name": "canonical-architecture-frozen-marker-removed",
        "ops": [
            (
                "replace",
                "spec/architecture.md",
                "FROZEN — Architecture Version 1.1.",
                "DRAFT — Architecture Version 1.1.",
            )
        ],
        "expect_check": "MARK-02",
    },
]


def make_copy() -> Path:
    root = Path(tempfile.mkdtemp(prefix="adcos-selftest-"))
    shutil.copytree(REPO_ROOT, root / "repo", ignore=COPY_IGNORE)
    return root / "repo"


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


def run_checker(root: Path) -> Tuple[int, Dict[str, str], str]:
    result = subprocess.run(
        [sys.executable, str(root / "tools" / "spec_check.py")],
        capture_output=True,
        text=True,
        cwd=str(root),
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    output = (result.stdout or "") + (result.stderr or "")
    checks: Dict[str, str] = {}
    for line in output.splitlines():
        m = CHECK_LINE_RE.match(line)
        if m:
            checks[m.group(2)] = m.group(1)
    return result.returncode, checks, output


def new_failures(baseline: Dict[str, str], mutated: Dict[str, str]) -> List[str]:
    """Check ids that are FAIL after the mutation but were not FAIL before."""
    return sorted(
        check
        for check, verdict in mutated.items()
        if verdict == "FAIL" and baseline.get(check) != "FAIL"
    )


def main() -> int:
    baseline_root = make_copy()
    try:
        baseline_rc, baseline_checks, _ = run_checker(baseline_root)
    finally:
        shutil.rmtree(baseline_root.parent, ignore_errors=True)

    passed = 0
    failures: List[str] = []
    for case in CASES:
        root = make_copy()
        try:
            apply_ops(root, case["ops"])
            rc, checks, output = run_checker(root)
            expected_check: Optional[str] = case.get("expect_check")

            if expected_check is not None:
                # Negative case: the named check must genuinely flip.
                if baseline_checks.get(expected_check) != "PASS":
                    raise AssertionError(
                        "%s: baseline must have %s PASS for the mutation to prove "
                        "detection (baseline says %r); the case no longer tests "
                        "what it claims"
                        % (case["name"], expected_check, baseline_checks.get(expected_check))
                    )
                if checks.get(expected_check) != "FAIL":
                    raise AssertionError(
                        "%s: expected check %s to FAIL after the mutation, got %r\n%s"
                        % (case["name"], expected_check, checks.get(expected_check), output)
                    )
                if rc == 0:
                    raise AssertionError(
                        "%s: checker must exit nonzero when %s fails"
                        % (case["name"], expected_check)
                    )
            else:
                # Positive case: the mutation must introduce no new failure.
                regressed = new_failures(baseline_checks, checks)
                if regressed:
                    raise AssertionError(
                        "%s: mutation introduced new failing check(s): %s\n%s"
                        % (case["name"], ", ".join(regressed), output)
                    )
                if rc != baseline_rc:
                    raise AssertionError(
                        "%s: exit code changed without any check transition "
                        "(baseline %d, mutated %d)\n%s"
                        % (case["name"], baseline_rc, rc, output)
                    )
            passed += 1
        except AssertionError as exc:
            failures.append(str(exc))
        finally:
            shutil.rmtree(root.parent, ignore_errors=True)

    for failure in failures:
        print("[FAIL    ] selftest   %s" % failure.splitlines()[0])
        for line in failure.splitlines()[1:]:
            print("          %s" % line)
    print(
        "spec_check selftest: %d/%d PASS (baseline: %d/%s clean, rc=%d)"
        % (
            passed,
            len(CASES),
            sum(1 for v in baseline_checks.values() if v == "PASS"),
            len(baseline_checks),
            baseline_rc,
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
