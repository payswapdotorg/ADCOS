#!/usr/bin/env python3
"""Verify that an ADCOS checkout is self-consistent enough for a fresh agent.

This is an offline checker. It validates repository-local handoff mechanics;
it does not grant implementation authority and it never replaces the normal
Architect/ACR acceptance process.

Usage:
    python3 tools/fresh_session_check.py
    python3 tools/fresh_session_check.py --actual-main-sha <sha>
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def fail(message: str) -> None:
    print(f"[FAIL] {message}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--actual-main-sha", help="Live origin/main SHA; if omitted, try git rev-parse origin/main")
    args = parser.parse_args()

    failures: list[str] = []

    required = [
        "AGENTS.md",
        "README.md",
        "spec/mission.md",
        "spec/architecture.md",
        "spec/architecture-lock.md",
        "spec/work-items.md",
        "spec/dependency-graph.md",
        "spec/architect/resume-protocol.md",
        "spec/architect/current-state.md",
        "spec/architect/authority-order.md",
        "spec/architect/governance-autonomy.md",
        "spec/architect/roadmap.yaml",
        "spec/architect/execution-state.yaml",
        "spec/architect/execution-ledger.yaml",
        "docs/tech-lead/ADCOS-TECH-LEAD-HANDOFF.md",
        "docs/tech-lead/worker-model.md",
    ]
    for rel in required:
        if not (ROOT / rel).exists():
            failures.append(f"missing required handoff/governance file: {rel}")

    agents = read("AGENTS.md")
    handoff = read("docs/tech-lead/ADCOS-TECH-LEAD-HANDOFF.md")
    worker_model = read("docs/tech-lead/worker-model.md")
    roadmap = read("spec/architect/roadmap.yaml")
    current = read("spec/architect/current-state.md")
    execution = read("spec/architect/execution-state.yaml")
    resume = read("spec/architect/resume-protocol.md")

    required_markers = [
        (agents, "Tech Lead", "AGENTS.md must define the Tech Lead role"),
        (handoff, "Single-agent mode", "Tech Lead handoff must support single-agent execution"),
        (handoff, "up to 3 workers", "Tech Lead handoff must record direct-worker limit"),
        (worker_model, "Maximum active descendants: 9", "worker model must record 3x3 descendant limit"),
        (resume, "Fresh-session guarantee", "resume protocol must define fresh-session sufficiency"),
        (resume, "R7 Universal Connectivity Commerce", "resume protocol must identify the current next gate"),
    ]
    for text, marker, message in required_markers:
        if marker not in text:
            failures.append(message)

    # Current state must agree on the program checkpoint.
    for marker in ["R6 Provider Onboarding & Federation", "R7", "no active implementation authorization"]:
        if marker.lower() not in current.lower():
            failures.append(f"current-state.md missing current checkpoint marker: {marker}")
    for marker in ["roadmap_version: \"1.5\"", "program_state: R6_PROVIDER_ONBOARDING_AND_FEDERATION_COMPLETE", "active_work_item: null", "active_authorization: null", "next_gate: R7_AFTER_R6"]:
        if marker not in roadmap:
            failures.append(f"roadmap.yaml missing current authoritative marker: {marker}")
    for marker in ["active_work_item: null", "active_authorization: null", "R6 complete under DEC-0097", "R7 requires its own gate-specific Work Item authorization"]:
        if marker not in execution:
            failures.append(f"execution-state.yaml missing current marker: {marker}")

    # Architecture proposal must not masquerade as current frozen authority.
    proposal = ROOT / "spec/architecture-1.1-proposed.md"
    if proposal.exists() and "NOT current architecture authority" not in current:
        failures.append("current-state.md must explicitly distinguish Architecture 1.1 proposal from current frozen authority")

    # Exactly-one authorization invariant as a repository-local static sanity check.
    auth_root = ROOT / "spec/architect" / "authorizations"
    active = 0
    if auth_root.exists():
        for path in auth_root.glob("*.y*ml"):
            text = path.read_text(encoding="utf-8")
            if re.search(r"^status:\s*active\s*$", text, re.MULTILINE) and re.search(r"^authorized:\s*true\s*$", text, re.MULTILINE):
                active += 1
    if "active_authorization: null" in roadmap and active > 0:
        failures.append(f"roadmap says no active authorization but {active} authorization file(s) declare active=true")

    actual = args.actual_main_sha
    if not actual:
        try:
            actual = subprocess.check_output(
                ["git", "rev-parse", "origin/main"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            actual = None

    persisted_match = re.search(r"^\s*main_sha:\s*([0-9a-f]{40})\s*$", execution, re.MULTILINE)
    persisted = persisted_match.group(1) if persisted_match else None
    if actual and persisted and actual != persisted:
        failures.append(
            f"live origin/main {actual} differs from execution-state snapshot {persisted}; reconcile before implementation"
        )

    if failures:
        for item in failures:
            fail(item)
        print(f"fresh-session check: FAIL ({len(failures)} issue(s))")
        return 1

    print("fresh-session check: PASS")
    print("repository contains the Tech Lead bootstrap, 3x3 worker rules, current roadmap checkpoint, and governance authority chain")
    if actual:
        print(f"origin/main verified against execution-state snapshot: {actual}")
    else:
        print("origin/main SHA not available locally; rerun with --actual-main-sha for live reconciliation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
