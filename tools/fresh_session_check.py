#!/usr/bin/env python3
"""Verify that an ADCOS checkout is self-consistent enough for a fresh agent.

This is an offline checker. It validates repository-local handoff mechanics;
it does not grant implementation authority and it never replaces the normal
Architect/ACR acceptance process.

Live-main reconciliation semantics (the standing reconciliation convention,
as documented in execution-state.yaml main_sha_semantics): the persisted
snapshot must equal live ``origin/main`` OR be one of its ancestors with
ONLY control-plane-classified deltas in between (the drift-guard
classification, single source of truth). Governance commits may sit beyond
the reconciled baseline between reconciliations; any implementation-domain
movement on main beyond the snapshot fails closed. This repairs the exact-
equality defect that structurally blocked implementation PRs: a commit can
never contain its own future SHA, so an implementation branch (forbidden by
the drift guard from touching spec/architect/) inherits a pin that always
points strictly before its branch point.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from architecture_drift_guard import CONTROL_FILES, CONTROL_PREFIXES  # type: ignore  # noqa: E402


def _is_control(path: str) -> bool:
    return path.startswith(CONTROL_PREFIXES) or path in CONTROL_FILES


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
        "spec/architect/work-items/R7-charter.md",
        "spec/architect/dependency-overlays/R7.yaml",
        "spec/architect/authorizations/M001.yaml",
        "spec/architect/authorizations/R7.yaml",
        "spec/architect/decisions/DEC-0098-m001-activation.yaml",
        "spec/architect/decisions/DEC-0099-m001-battery-reconciliation.yaml",
        "spec/architect/decisions/DEC-0100-m001-acceptance.yaml",
        "spec/architect/decisions/DEC-0101-r7-activation.yaml",
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
        (roadmap, "next_gate: R7_UNIVERSAL_CONNECTIVITY_COMMERCE", "roadmap must put R7 as the active gate"),
        (roadmap, 'roadmap_version: "1.9"', "roadmap must be advanced to the post-M002-acceptance version 1.9"),
        (roadmap, "program_state: R7_UNIVERSAL_CONNECTIVITY_COMMERCE_ACTIVE", "roadmap must record the R7-active program state"),
    ]
    for text, marker, message in required_markers:
        if marker.lower() not in text.lower():
            failures.append(message)

    for marker in ["R6 Provider Onboarding & Federation", "M001 — Architecture 1.1 Freeze", "the sole active implementation authorization", "Architecture 1.0 is preserved historical evidence", "R7 — Universal Connectivity Commerce", "M002 — Connectivity Contract Core", "M003 — Offers and Provider Capability Exchange"]:
        if marker.lower() not in current.lower():
            failures.append(f"current-state.md missing R7-active checkpoint marker: {marker}")

    for marker in ['roadmap_version: "1.9"', "program_state: R7_UNIVERSAL_CONNECTIVITY_COMMERCE_ACTIVE", "execution_mode: implementing", "active_work_item: M003", "active_authorization: R7-CORE-001", "next_gate: R7_UNIVERSAL_CONNECTIVITY_COMMERCE", "completion_decision: DEC-0100", "activation_decision: DEC-0101"]:
        if marker not in roadmap:
            failures.append(f"roadmap.yaml missing current authoritative marker: {marker}")

    for marker in ["mode: implementing", "active_work_item: M003", "active_authorization: R7-CORE-001", "current_child_work_item: M003", "program_authorization: R7-CORE-001", "R7-CORE-001"]:
        if marker not in execution:
            failures.append(f"execution-state.yaml missing R7-active marker: {marker}")

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

    # post-acceptance closure: M001-CORE-001 is closed by DEC-0100 (fail
    # closed against the pre-acceptance M001-ACTIVE markers)
    m001_auth = ROOT / "spec/architect/authorizations/M001.yaml"
    if m001_auth.is_file():
        m001_text = m001_auth.read_text(encoding="utf-8")
        if not re.search(r"^status:\s*accepted\s*$", m001_text, re.MULTILINE):
            failures.append("M001 authorization must be status accepted after the DEC-0100 acceptance")
        if not re.search(r"^authorized:\s*false\s*$", m001_text, re.MULTILINE):
            failures.append("M001 authorization must be authorized false after the DEC-0100 acceptance")
        if "acceptance_decision: DEC-0100" not in m001_text:
            failures.append("M001 authorization acceptance gate must record DEC-0100")
        if "acceptance_merge_sha: 80292c24502200f84d11491ed12e9cec5e5baf11" not in m001_text:
            failures.append("M001 authorization acceptance gate must record the exact acceptance merge")

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
        else:
            # the single active authorization must carry the declared
            # authorization id and bind the declared active work item —
            # either directly (work_item: <item>, the historical per-item
            # model) or as the current child of a bounded program
            # authorization (current_child_work_item: <item>, the DEC-0101
            # R7 program model)
            atext = (auth_root / active_files[0]).read_text(encoding="utf-8")
            if f'authorization_id: "{declared}"' not in atext:
                failures.append(f"the active authorization {active_files[0]} does not carry authorization_id {declared}")
            awi_declared = None
            m2 = re.search(r"^\s*active_work_item:\s*(\S+)", roadmap, re.MULTILINE)
            if m2:
                awi_declared = m2.group(1)
            if awi_declared and awi_declared != "null":
                if not (f"work_item: {awi_declared}" in atext or f"current_child_work_item: {awi_declared}" in atext):
                    failures.append(
                        f"the active authorization {active_files[0]} does not bind work item {awi_declared} "
                        "(directly or as the current program child)"
                    )

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
        # Standing reconciliation convention: the snapshot may lag live main
        # only through governance-only commits. Fail closed on any
        # implementation-domain movement beyond the snapshot, on a snapshot
        # that is not an ancestor of live main, and on git failures.
        reconciled, problem = _governance_only_range(persisted, actual)
        if not reconciled and problem is not None:
            failures.append(problem)

    if failures:
        for item in failures:
            fail(item)
        print(f"fresh-session check: FAIL ({len(failures)} issue(s))")
        return 1

    print("fresh-session check: PASS")
    print("repository contains the 1.1 forward-target routing, Tech Lead bootstrap, 3x3 worker rules, machine-readable dispatch state, current roadmap checkpoint, and governance authority chain")
    if actual:
        print(f"origin/main verified against the execution-state snapshot: {actual}")
    else:
        print("origin/main SHA not available locally; rerun with --actual-main-sha for live reconciliation")
    return 0


def _git(args: list[str]) -> str | None:
    try:
        p = subprocess.run(
            ["git", *args], cwd=ROOT, text=True, capture_output=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return p.stdout


def _governance_only_range(persisted: str, actual: str) -> tuple[bool, str | None]:
    """True when every commit in (persisted..actual] is control-plane only."""
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", persisted, actual],
        cwd=ROOT, capture_output=True,
    )
    if ancestor.returncode != 0:
        return False, (
            f"live origin/main {actual} does not descend from the execution-state "
            f"snapshot {persisted}; the snapshot is not a valid baseline — reconcile "
            "before implementation"
        )
    revs = _git(["rev-list", "--reverse", f"{persisted}..{actual}"])
    if revs is None:
        return False, (
            f"cannot enumerate the reconciliation range {persisted[:8]}..{actual[:8]}; "
            "fail closed"
        )
    for rev in [line.strip() for line in revs.splitlines() if line.strip()]:
        files = _git(["diff", "--name-only", f"{rev}^", rev])
        if files is None:
            return False, (
                f"cannot classify the delta of {rev[:8]} in the reconciliation range; "
                "fail closed"
            )
        offending = [f for f in files.splitlines() if f.strip() and not _is_control(f.strip())]
        if offending:
            return False, (
                f"main advanced beyond the snapshot {persisted[:8]} with "
                f"implementation-domain changes ({rev[:8]}: {offending[0]}); "
                "reconcile the execution-state snapshot before implementation"
            )
    return True, None


if __name__ == "__main__":
    sys.exit(main())
