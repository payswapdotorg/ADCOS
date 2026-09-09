#!/usr/bin/env python3
"""Validate the current ADCOS governance/transition model.

This checker complements tools/spec_check.py. The older checker validates the
original frozen specification schema and deliberately preserves historical
compatibility; this checker validates the post-snapshot Architect model,
including Architecture 1.1 transition routing, reconciled lifecycle state,
and repository-local handoff sufficiency.

Standard library only; no network access.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from spec_check import yaml_subset_load  # type: ignore  # noqa: E402


REQUIRED_FILES = [
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
    "spec/history/README.md",
    "spec/history/architecture-1.0.md",
    "spec/history/architecture-lock-1.0.md",
    "spec/history/work-items-1.0.md",
    "spec/history/dependency-graph-1.0.md",
    "spec/architect/LLM-ARCHITECT-HANDOFF.md",
    "spec/architect/resume-protocol.md",
    "spec/architect/current-state.md",
    "spec/architect/authority-order.md",
    "spec/architect/governance-autonomy.md",
    "spec/architect/roadmap.yaml",
    "spec/architect/execution-state.yaml",
    "spec/architect/execution-ledger.yaml",
    "spec/architect/evidence-obligations.yaml",
    "docs/tech-lead/ADCOS-TECH-LEAD-HANDOFF.md",
    "docs/tech-lead/worker-model.md",
    "docs/tech-lead/dispatch-state.yaml",
    "tools/fresh_session_check.py",
    "tools/tech_lead_guard.py",
    "tools/architecture_drift_guard.py",
]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def sha(value: Any) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{40}", value))


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def main() -> int:
    errors: list[str] = []

    for rel in REQUIRED_FILES:
        if not (ROOT / rel).is_file():
            fail(errors, f"missing required current-governance file: {rel}")

    if errors:
        for error in errors:
            print(f"[FAIL] {error}")
        print(f"current-spec check: FAIL ({len(errors)} issue(s))")
        return 1

    agents = text("AGENTS.md")
    tl = text("docs/tech-lead/ADCOS-TECH-LEAD-HANDOFF.md")
    workers = text("docs/tech-lead/worker-model.md")
    resume = text("spec/architect/resume-protocol.md")
    current = text("spec/architect/current-state.md")
    authority = text("spec/architect/authority-order.md")
    autonomy = text("spec/architect/governance-autonomy.md")
    roadmap_text = text("spec/architect/roadmap.yaml")
    execution_text = text("spec/architect/execution-state.yaml")
    state = yaml_subset_load(execution_text, "spec/architect/execution-state.yaml")
    ledger = yaml_subset_load(text("spec/architect/execution-ledger.yaml"), "spec/architect/execution-ledger.yaml")
    evidence = yaml_subset_load(text("spec/architect/evidence-obligations.yaml"), "spec/architect/evidence-obligations.yaml")

    def norm(value: str) -> str:
        # marker alignment repair: authoritative prose carries markdown
        # emphasis; normalize exactly like fresh_session_check so the
        # enforced markers match the authoritative wording verbatim
        # (the pre-repair markers never matched and were dead code)
        return re.sub(r"[*_`]+", "", value)

    markers = [
        (norm(agents), "Architecture 1.1 is the mandatory forward implementation target", "AGENTS.md is not 1.1-forward"),
        (norm(tl), "Architecture 1.1 is the target architecture", "Tech Lead handoff is not 1.1-forward"),
        (norm(tl), "at most 3 workers", "Tech Lead direct-worker limit is missing"),
        (norm(workers), "maximum active descendant", "worker model does not record the active descendant limit"),
        (norm(resume), "Fresh-session guarantee", "resume protocol lacks fresh-session guarantee"),
        (norm(resume), "M001 — Architecture 1.1 Freeze", "resume protocol does not route through M001"),
        (norm(current), "sole normative forward architecture", "current-state does not declare 1.1 the sole normative forward architecture"),
        (norm(authority), "Architecture 1.1", "authority-order does not mention the 1.1 transition target"),
        (norm(autonomy), "Single-agent execution", "governance-autonomy does not support a combined Architect/Tech Lead"),
    ]
    for haystack, marker, message in markers:
        if marker.lower() not in haystack.lower():
            fail(errors, message)

    dispatch = yaml_subset_load(text("docs/tech-lead/dispatch-state.yaml"), "docs/tech-lead/dispatch-state.yaml")
    if not isinstance(dispatch, dict):
        fail(errors, "dispatch-state.yaml is not a mapping")
    else:
        for key, expected in {
            "max_direct_workers": 3,
            "max_subagents_per_worker": 3,
            "max_active_descendants": 9,
            "max_depth": 2,
        }.items():
            if dispatch.get(key) != expected:
                fail(errors, f"dispatch-state.yaml {key} must be {expected}")
        active_workers = dispatch.get("active_workers")
        if not isinstance(active_workers, list) or len(active_workers) > 3:
            fail(errors, "dispatch-state.yaml active_workers must be a list of at most 3 direct workers")
        else:
            subagent_total = 0
            worker_ids: set[str] = set()
            for worker in active_workers:
                if not isinstance(worker, dict):
                    fail(errors, "dispatch-state.yaml contains a non-mapping worker")
                    continue
                wid = worker.get("id")
                if not isinstance(wid, str) or not wid or wid in worker_ids:
                    fail(errors, "dispatch-state.yaml worker ids must be non-empty and unique")
                if isinstance(wid, str):
                    worker_ids.add(wid)
                subs = worker.get("subagents", [])
                if not isinstance(subs, list) or len(subs) > 3:
                    fail(errors, f"dispatch-state.yaml worker {wid!r} must have at most 3 subagents")
                else:
                    subagent_total += len(subs)
            if subagent_total > 9:
                fail(errors, "dispatch-state.yaml cannot declare more than 9 active subagents")

    for marker in (
        'roadmap_version: "1.6"',
        'status: FROZEN_AUTHORITATIVE',
        'source_of_truth: repository_only',
        'mandatory_forward_target: "Architecture 1.1"',
        'promotion_gate: "M001 — Architecture 1.1 Freeze"',
        'id: M001_ARCHITECTURE_1_1_FREEZE',
        'status: ACTIVE',
        'program_state: M001_ARCHITECTURE_1_1_FREEZE_ACTIVE',
        'active_work_item: M001',
        'active_authorization: M001-CORE-001',
        'id: R7_UNIVERSAL_CONNECTIVITY_COMMERCE',
        'prerequisite: M001_ARCHITECTURE_1_1_FREEZE',
    ):
        if marker not in roadmap_text:
            fail(errors, f"roadmap.yaml missing mandatory transition marker: {marker}")

    if not isinstance(state, dict):
        fail(errors, "execution-state.yaml is not a mapping")
    else:
        repository = state.get("repository")
        execution = state.get("execution")
        if not isinstance(repository, dict) or not sha(repository.get("main_sha")):
            fail(errors, "execution-state.yaml repository.main_sha is missing/invalid")
        if not isinstance(execution, dict):
            fail(errors, "execution-state.yaml execution section missing")
        else:
            mode = execution.get("mode")
            if mode == "awaiting-architect-decisions":
                # pre-M001 halt state: no active item, halted reason explains the gate
                if execution.get("active_work_item") is not None:
                    fail(errors, "execution-state.yaml active_work_item must be null before M001 activation")
                if execution.get("active_authorization") is not None:
                    fail(errors, "execution-state.yaml active_authorization must be null before M001 activation")
                if not isinstance(execution.get("halted_reason"), str) or not execution.get("halted_reason"):
                    fail(errors, "execution-state.yaml halted_reason must explain the M001 gate")
            elif mode == "implementing":
                # M001-active state: exactly one transition Work Item + authorization
                if execution.get("active_work_item") != "M001":
                    fail(errors, "execution-state.yaml implementing mode is only valid for M001 before its acceptance")
                if execution.get("active_authorization") != "M001-CORE-001":
                    fail(errors, "execution-state.yaml active_authorization must be M001-CORE-001 while M001 is active")
                if execution.get("halted_reason") is not None:
                    fail(errors, "execution-state.yaml halted_reason must be null while M001 is active")
                auth_path = ROOT / "spec/architect/authorizations/M001.yaml"
                if not auth_path.is_file():
                    fail(errors, "M001-CORE-001 authorization file missing while M001 is active")
                else:
                    auth_text = auth_path.read_text(encoding="utf-8")
                    if not re.search(r"^status:\s*active\s*$", auth_text, re.MULTILINE):
                        fail(errors, "M001 authorization must have status active while M001 is active")
                    if not re.search(r"^authorized:\s*true\s*$", auth_text, re.MULTILINE):
                        fail(errors, "M001 authorization must have authorized true while M001 is active")
                    base = re.search(r"^baseline_sha:\s*([0-9a-f]{40})\s*$", auth_text, re.MULTILINE)
                    main_sha = repository.get("main_sha") if isinstance(repository, dict) else None
                    if base and main_sha:
                        # the authorization baseline must be the recorded main
                        # snapshot or one of its ancestors (governance commits
                        # may intervene between activation and delivery)
                        if base.group(1) != main_sha:
                            anc = subprocess.run(
                                ["git", "merge-base", "--is-ancestor", base.group(1), main_sha],
                                cwd=ROOT, capture_output=True,
                            )
                            if anc.returncode != 0:
                                fail(errors, "M001 authorization baseline is neither the reconciled main snapshot nor its ancestor")
            else:
                fail(errors, f"execution-state.yaml execution.mode must be awaiting-architect-decisions or implementing, got {mode!r}")
            if "M001 — Architecture 1.1 Freeze" not in "\n".join(str(x) for x in execution.get("next_required_decisions", [])):
                fail(errors, "execution-state.yaml does not identify M001 as the immediate gate")
            if not isinstance(state.get("open_acrs"), list):
                fail(errors, "execution-state.yaml open_acrs must be a list")
            if not isinstance(state.get("open_architectural_questions"), list):
                fail(errors, "execution-state.yaml open_architectural_questions must be a list")
            if mode == "implementing" and "ACR-014" not in state.get("open_acrs", []):
                fail(errors, "execution-state.yaml open_acrs must track ACR-014 while M001 is active")

    wi_dir = ROOT / "spec/architect/work-items"
    if not wi_dir.is_dir():
        fail(errors, "spec/architect/work-items/ missing")
    else:
        for wid in ("WORK-054", "WORK-055", "WORK-056", "WORK-057", "M001"):
            if not (wi_dir / f"{wid}.md").is_file():
                fail(errors, f"post-snapshot Work Item contract missing: {wid}")

    acr_dir = ROOT / "spec/acr"
    if not (acr_dir / "ACR-014-architecture-1.1-freeze.md").is_file():
        fail(errors, "ACR-014 (Architecture 1.1 freeze) record missing")
    else:
        acr_text = (acr_dir / "ACR-014-architecture-1.1-freeze.md").read_text(encoding="utf-8")
        if "DEC-0098" not in acr_text:
            fail(errors, "ACR-014 must record the DEC-0098 Architect approval")
        if not re.search(r"^## Status\nACCEPTED", acr_text, re.MULTILINE):
            fail(errors, "ACR-014 must be ACCEPTED after the M001 delivery")

    # post-freeze invariants: Architecture 1.1 is the canonical normative snapshot
    arch_text = text("spec/architecture.md")
    for marker in ("Architecture Version 1.1", "FROZEN", "ACR-014", "ConnectivityContract"):
        if marker not in arch_text:
            fail(errors, f"spec/architecture.md missing the Architecture 1.1 freeze marker: {marker}")
    lock_text = text("spec/architecture-lock.md")
    for marker in ("LOCK-101", "LOCK-120", "Architecture Version 1.1"):
        if marker not in lock_text:
            fail(errors, f"spec/architecture-lock.md missing the 1.1 lock marker: {marker}")
    wi_text = text("spec/work-items.md")
    for wid in ("M001", "M007", "M014"):
        if f"## {wid} " not in wi_text:
            fail(errors, f"spec/work-items.md missing the successor registry entry: {wid}")
    if "spec/history/work-items-1.0.md" not in wi_text:
        fail(errors, "spec/work-items.md must point at the preserved 1.0 registry")

    # verbatim archive proof: each archived 1.0 file must be byte-identical to
    # its blob at the M001 delivery branch point recorded in the roadmap
    branch_point = re.search(
        r"^\s*delivery_branch_point:\s*([0-9a-f]{40})\s*$",
        roadmap_text, re.MULTILINE,
    )
    if branch_point is None:
        fail(errors, "roadmap.yaml must record the M001 delivery branch point")
    else:
        bp = branch_point.group(1)
        for orig, archived in (
            ("spec/architecture.md", "spec/history/architecture-1.0.md"),
            ("spec/architecture-lock.md", "spec/history/architecture-lock-1.0.md"),
            ("spec/work-items.md", "spec/history/work-items-1.0.md"),
            ("spec/dependency-graph.md", "spec/history/dependency-graph-1.0.md"),
        ):
            try:
                blob = subprocess.run(
                    ["git", "show", f"{bp}:{orig}"], cwd=ROOT,
                    capture_output=True, check=True,
                ).stdout
            except (OSError, subprocess.CalledProcessError):
                fail(errors, f"cannot read {orig} at the delivery branch point {bp[:8]}")
                continue
            archived_bytes = (ROOT / archived).read_bytes()
            if blob != archived_bytes:
                fail(errors, f"{archived} is not byte-identical to {orig} at the branch point (verbatim archive violated)")

    if isinstance(ledger, dict):
        items = ledger.get("work_items")
        if not isinstance(items, list):
            fail(errors, "execution-ledger.yaml work_items must be a list")
        else:
            by_id = {e.get("work_item"): e for e in items if isinstance(e, dict)}
            w050 = by_id.get("WORK-050")
            if isinstance(w050, dict):
                if w050.get("lifecycle") == "accepted-merged" and (w050.get("branch") is not None or w050.get("pr") is not None):
                    fail(errors, "W050 must preserve its documented staged-reconstruction null branch/pr representation")
                note = str(w050.get("note", ""))
                if "No single delivery PR exists" not in note:
                    fail(errors, "W050 accepted reconstruction is missing its no-single-PR provenance disclosure")
            elif w050 is None:
                fail(errors, "execution-ledger.yaml is missing WORK-050")
            if not any(e.get("work_item") == "WORK-057" for e in items if isinstance(e, dict)):
                fail(errors, "execution-ledger.yaml must contain the current W057 acceptance projection")

    if isinstance(evidence, dict):
        obligations = evidence.get("obligations")
        if not isinstance(obligations, list):
            fail(errors, "evidence-obligations.yaml obligations must be a list")
        else:
            open_ids = {
                e.get("obligation_id") for e in obligations
                if isinstance(e, dict) and e.get("status") in {"OPEN", "PARTIAL", "NOT-TESTABLE"}
            }
            mentioned = set(re.findall(r"EVID-\d{3}", current))
            missing = sorted(x for x in open_ids if x not in mentioned)
            if missing:
                fail(errors, "current-state.md hides open evidence obligations: " + ", ".join(missing))

    # FAIL CLOSED: every accumulated error is terminal. The original
    # aggregation defect (errors collected after the missing-files gate but
    # never checked before the PASS print) made every marker, ledger,
    # authorization, and archive invariant dead code — this gate is the
    # repair; the checker now actually fails closed.
    if errors:
        for error in errors:
            print(f"[FAIL] {error}")
        print(f"current-spec check: FAIL ({len(errors)} issue(s))")
        return 1

    print("current-spec check: PASS")
    print("Architecture 1.1 routing, M001 gate, 3x3 worker hierarchy, machine-checked dispatch state, post-snapshot Work Items, reconstructed W050 provenance, and evidence visibility are consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
