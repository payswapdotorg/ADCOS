#!/usr/bin/env python3
"""Fail closed when an implementation PR mixes delivery and architecture control-plane edits."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CONTROL_PREFIXES = (
    "spec/architect/",
    "docs/tech-lead/",
    ".github/",
)
CONTROL_FILES = {
    "AGENTS.md",
    "README.md",
    "spec/architecture.md",
    "spec/architecture-lock.md",
    "spec/architecture-1.1-proposed.md",
    "spec/architecture-lock-1.1-proposed.md",
    "spec/application-model.md",
    "spec/work-items-1.1.md",
    "spec/dependency-graph-1.1.md",
    "spec/migration/classification-matrix.md",
    "spec/integration/vertical-proof.md",
    "spec/research/standards-and-use-cases.md",
    "tools/README.md",
    "tools/spec_check.py",
    "tools/spec_check_selftest.py",
    "tools/current_spec_check.py",
    "tools/fresh_session_check.py",
    "tools/tech_lead_guard.py",
    "tools/architecture_drift_guard.py",
}


def git(*args: str) -> list[str]:
    try:
        p = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"[FAIL] unable to inspect origin/main: {exc}")
        raise SystemExit(1)
    return [line for line in p.stdout.splitlines() if line.strip()]


def is_control(path: str) -> bool:
    return path.startswith(CONTROL_PREFIXES) or path in CONTROL_FILES


def main() -> int:
    delta = git("diff", "--name-only", "origin/main...HEAD")
    control = sorted(p for p in delta if is_control(p))
    implementation = sorted(p for p in delta if not is_control(p))

    if control and implementation:
        print("[FAIL] PR mixes architecture/governance control-plane changes with implementation changes")
        print("[FAIL] implementation files:")
        for path in implementation:
            print(f"  - {path}")
        print("[FAIL] control-plane files:")
        for path in control:
            print(f"  - {path}")
        print("architecture drift guard: FAIL")
        return 1

    print("architecture drift guard: PASS")
    if control:
        print(f"governance-only delta: {len(control)} control-plane file(s)")
    else:
        print(f"implementation-only delta: {len(implementation)} implementation file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
