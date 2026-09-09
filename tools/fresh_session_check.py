#!/usr/bin/env python3
"""Verify that an ADCOS checkout is self-consistent enough for a fresh agent.

This is an offline checker. It validates repository-local handoff mechanics;
it does not grant implementation authority and it never replaces the normal
Architect/ACR acceptance process.
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


def normalize_markdown(text: str) -> str:
    """Normalize cosmetic Markdown markers so governance checks test semantics."""
    return re.sub(r"[*_`]+", "", text)


def fail(message: str) -> None:
    print(f"[FAIL] {message}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--actual-main-sha", help="Live main SHA; if omitted, try git rev-parse origin/main")
    args = parser.parse_args()

    failures: list[str] = []

    required = [
        "AGENTS.md",
        "README.md",
        "spec/mission.md",
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
        "spec/work-items.md",
        "spec/dependency-graph.md",
        "spec/architect/resume-protocol.md",
        "spec/architect/current-state.md",
        "spec/architect/authority-order.md",
        "spec/architect/governance-autonomy.md",
        "spec/architect/roadmap.yaml",
        "spec/architect/execution-state.yaml",
        "spec/architect/execution-ledger.yaml",
        "spec/architect/work-items/M001.md",
        "spec/architect/authorizations/M001.yaml",
        "spec/architect/decisions/DEC-0098-m001-activation.yaml",
        "spec/architect/decisions/DEC-0099-m001-battery-reconciliation.yaml",
        "spec/acr/ACR-014-architecture-1.1-freeze.md",
        "spec/history/README.md",
        "spec/history/architecture-1.0.md",
        "spec/history/architecture-lock-1.0.md",
        "spec/history/work-items-1.0.md",
        "spec/history/dependency-graph-1.0.md",
        "docs/M001-evidence.md",
        "docs/tech-lead/ADCOS-TECH-LEAD-HANDOFF.md",
        "docs/tech-lead/worker-model.md",
        "docs/tech-lead/dispatch-state.yaml",
        "tools/tech_lead_guard.py",
    ]
    for rel in required:
        if not (ROOT / rel).is_file():
            failures.append(f"missing required handoff/governance file: {rel}")

    agents = normalize_markdown(read("AGENTS.md"))
    handoff = normalize_markdown(read("docs/tech-lead/ADCOS-TECH-LEAD-HANDOFF.md"))
    worker_model = normalize_markdown(read("docs/tech-lead/worker-model.md"))
    roadmap = read("spec/architect/roadmap.yaml")
    current = normalize_markdown(read("spec/architect/current-state.md"))
    execution = read("spec/architect/execution-state.yaml")
    resume = normalize_markdown(read("spec/architect/resume-protocol.md"))

    required_markers = [
        (agents, "Architecture 1.1 is the mandatory forward implementation target", "AGENTS.md must bind forward implementation to Architecture 1.1"),
        (handoff, "Single-agent mode", "Tech Lead handoff must support single-agent execution"),
        (handoff, "Architecture 1.1 is the target architecture", "Tech Lead handoff must bind implementation to 1.1"),
        (handoff, "at most 3 workers", "Tech Lead handoff must record direct-worker limit"),
        (worker_model, "maximum active descendant", "worker model must record the active descendant limit"),
        (resume, "Fresh-session guarantee", "resume protocol must define fresh-session sufficiency"),
        (resume, "M001 — Architecture 1.1 Freeze", "resume protocol must identify the 1.1 transition gate"),
        (roadmap, "mandatory_forward_target: \"Architecture 1.1\"", "roadmap must declare 1.1 as mandatory forward target"),
        (roadmap, "next_gate: M001_ARCHITECTURE_1_1_FREEZE", "roadmap must put the 1.1 promotion gate before R7"),
    ]
    for text, marker, message in required_markers:
        if marker.lower() not in text.lower():
            failures.append(message)

    for marker in ["R6 Provider Onboarding & Federation", "M001 — Architecture 1.1 Freeze", "Exactly one implementation authorization is active", "Architecture 1.0 is preserved historical evidence"]:
        if marker.lower() not in current.lower():
            failures.append(f"current-state.md missing transition checkpoint marker: {marker}")

    for marker in ["roadmap_version: \"1.6\"", "program_state: M001_ARCHITECTURE_1_1_FREEZE_ACTIVE", "active_work_item: M001", "active_authorization: M001-CORE-001", "next_gate: M001_ARCHITECTURE_1_1_FREEZE"]:
        if marker not in roadmap:
            failures.append(f"roadmap.yaml missing current authoritative marker: {marker}")

    for marker in ["mode: implementing", "active_work_item: M001", "active_authorization: M001-CORE-001", "M001 — Architecture 1.1 Freeze", "R7 requires its own gate-specific Work Item authorization"]:
        if marker not in execution:
            failures.append(f"execution-state.yaml missing current transition marker: {marker}")

    proposal = ROOT / "spec/architecture-1.1-proposed.md"
    if proposal.exists() and "mandatory forward implementation target" not in agents.lower():
        failures.append("agent bootstrap must identify Architecture 1.1 as the mandatory forward implementation target")

    # post-freeze invariants: Architecture 1.1 is the canonical normative snapshot
    arch = read("spec/architecture.md")
    lock = read("spec/architecture-lock.md")
    for marker in ("Architecture Version 1.1", "FROZEN", "ACR-014"):
        if marker not in arch:
            failures.append(f"spec/architecture.md missing the Architecture 1.1 freeze marker: {marker}")
    for marker in ("LOCK-101", "LOCK-120"):
        if marker not in lock:
            failures.append(f"spec/architecture-lock.md missing the 1.1 lock marker: {marker}")
    hist = ROOT / "spec/history/architecture-1.0.md"
    if not hist.is_file():
        failures.append("the preserved Architecture 1.0 snapshot is missing from spec/history/")
    acr14 = read("spec/acr/ACR-014-architecture-1.1-freeze.md")
    if "## Status\nACCEPTED" not in acr14:
        failures.append("ACR-014 must record its ACCEPTED status")

    auth_root = ROOT / "spec/architect" / "authorizations"
    active = 0
    active_files: list[str] = []
    if auth_root.exists():
        for path in auth_root.glob("*.y*ml"):
            auth_text = path.read_text(encoding="utf-8")
            if re.search(r"^status:\s*active\s*$", auth_text, re.MULTILINE) and re.search(r"^authorized:\s*true\s*$", auth_text, re.MULTILINE):
                active += 1
                active_files.append(path.name)
    declared = None
    m = re.search(r"^\s*active_authorization:\s*(\S+)", roadmap, re.MULTILINE)
    if m:
        declared = m.group(1)
    if declared == "null":
        if active > 0:
            failures.append(f"roadmap says no active authorization but {active} authorization file(s) declare active=true")
    elif declared is not None:
        if active != 1:
            failures.append(f"roadmap declares active authorization {declared} but {active} authorization file(s) declare active=true ({', '.join(active_files) or 'none'})")
        elif "M001.yaml" not in active_files:
            failures.append(f"roadmap declares {declared} but the active authorization file is not M001.yaml")
        else:
            m001_auth = (auth_root / "M001.yaml").read_text(encoding="utf-8")
            if "authorization_id: \"M001-CORE-001\"" not in m001_auth or "work_item: M001" not in m001_auth:
                failures.append("M001.yaml does not bind work_item M001 to authorization_id M001-CORE-001")

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
    print("repository contains the 1.1 forward-target routing, Tech Lead bootstrap, 3x3 worker rules, machine-readable dispatch state, current roadmap checkpoint, and governance authority chain")
    if actual:
        print(f"origin/main verified against execution-state snapshot: {actual}")
    else:
        print("origin/main SHA not available locally; rerun with --actual-main-sha for live reconciliation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
