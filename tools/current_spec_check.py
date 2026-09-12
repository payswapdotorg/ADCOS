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
    "spec/architect/authorizations/M001.yaml",
    "spec/architect/authorizations/R7.yaml",
    "spec/architect/authorizations/R8.yaml",
    "spec/architect/decisions/DEC-0098-m001-activation.yaml",
    "spec/architect/decisions/DEC-0099-m001-battery-reconciliation.yaml",
    "spec/architect/decisions/DEC-0100-m001-acceptance.yaml",
    "spec/architect/decisions/DEC-0101-r7-activation.yaml",
    "spec/architect/decisions/DEC-0114-r8-activation.yaml",
    "spec/architect/work-items/R7-charter.md",
    "spec/architect/work-items/R8-charter.md",
    "spec/architect/dependency-overlays/R7.yaml",
    "spec/architect/dependency-overlays/R8.yaml",
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
        'roadmap_version: "2.13"',
        'status: FROZEN_AUTHORITATIVE',
        'source_of_truth: repository_only',
        'mandatory_forward_target: "Architecture 1.1"',
        'promotion_gate: "M001 — Architecture 1.1 Freeze"',
        'promotion_completed_by: "DEC-0100',
        'id: M001_ARCHITECTURE_1_1_FREEZE',
        'status: COMPLETE',
        'completion_decision: DEC-0100',
        'completion_merge_sha: 80292c24502200f84d11491ed12e9cec5e5baf11',
        'id: R7_UNIVERSAL_CONNECTIVITY_COMMERCE',
        'status: COMPLETE',
        'completion_decision: DEC-0109',
        'activation_decision: DEC-0101',
        'authorization: "R7-CORE-001"',
        'work_item_contract: "spec/architect/work-items/R7-charter.md"',
        'prerequisite: M001_ARCHITECTURE_1_1_FREEZE',
        'id: R8_RESILIENCE_MOBILITY_AND_SCALE',
        'status: ACTIVE',
        'activation_decision: DEC-0114',
        'authorization: "R8-CORE-001"',
        'work_item_contract: "spec/architect/work-items/R8-charter.md"',
        'prerequisite: R7_UNIVERSAL_CONNECTIVITY_COMMERCE',
        'work_item: M019',
        'work_item_chain: [M015, M016, M017, M018, M019]',
        'program_state: R8_RESILIENCE_MOBILITY_AND_SCALE_ACTIVE',
        'execution_mode: implementing',
        'active_work_item: M017',
        'active_authorization: R8-CORE-001',
        'next_gate: R9_FUTURE_ACCESS_TECHNOLOGY',
    ):
        if marker not in roadmap_text:
            fail(errors, f"roadmap.yaml missing mandatory post-acceptance marker: {marker}")

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
                # post-R8-completion halt state: no active item, the halted
                # reason explains the next gate (R9) authorization requirement
                if execution.get("active_work_item") is not None:
                    fail(errors, "execution-state.yaml active_work_item must be null while halted awaiting architect decisions")
                if execution.get("active_authorization") is not None:
                    fail(errors, "execution-state.yaml active_authorization must be null while halted awaiting architect decisions")
                halted = execution.get("halted_reason")
                if not isinstance(halted, str) or not halted or "R9" not in halted:
                    fail(errors, "execution-state.yaml halted_reason must explain the R9 gate authorization requirement")
            elif mode == "implementing":
                # post-acceptance implementing state: exactly one active
                # authorization file matching the declared work item — either
                # a direct work-item authorization (work_item: <item>) or a
                # bounded program authorization whose current child is the
                # declared work item (current_child_work_item: <item>, the
                # DEC-0101 R7 program model); M001 itself can never return to
                # implementing (accepted/closed)
                awi = execution.get("active_work_item")
                aaz = execution.get("active_authorization")
                if not isinstance(awi, str) or not awi:
                    fail(errors, "execution-state.yaml implementing mode requires an active work item")
                if not isinstance(aaz, str) or not aaz:
                    fail(errors, "execution-state.yaml implementing mode requires an active authorization")
                if awi == "M001":
                    fail(errors, "M001 is accepted (DEC-0100); it can never return to the active implementing state")
                if awi == "M002":
                    fail(errors, "M002 is accepted (DEC-0102); it can never return to the active implementing state")
                if awi == "M003":
                    fail(errors, "M003 is accepted (DEC-0103); it can never return to the active implementing state")
                if awi == "M013":
                    fail(errors, "M013 is accepted (DEC-0113); it can never return to the active implementing state")
                if awi == "M009":
                    fail(errors, "M009 is accepted (DEC-0109); it can never return to the active implementing state")
                if awi == "M010":
                    fail(errors, "M010 is accepted (DEC-0110); it can never return to the active implementing state")
                if awi == "M011":
                    fail(errors, "M011 is accepted (DEC-0111); it can never return to the active implementing state")
                if awi == "M012":
                    fail(errors, "M012 is accepted (DEC-0112); it can never return to the active implementing state")
                if awi == "M004":
                    fail(errors, "M004 is accepted (DEC-0104); it can never return to the active implementing state")
                if awi == "M005":
                    fail(errors, "M005 is accepted (DEC-0105); it can never return to the active implementing state")
                if awi == "M006":
                    fail(errors, "M006 is accepted (DEC-0106); it can never return to the active implementing state")
                if awi == "M007":
                    fail(errors, "M007 is accepted (DEC-0107); it can never return to the active implementing state")
                if awi == "M008":
                    fail(errors, "M008 is accepted (DEC-0108); it can never return to the active implementing state")
                if awi == "M014":
                    fail(errors, "M014 is accepted (DEC-0109, completing the R7 gate); it can never return to the active implementing state")
                if awi == "M015":
                    fail(errors, "M015 is accepted (DEC-0115, the first R8 chain-child acceptance); it can never return to the active implementing state")
                if awi == "M016":
                    fail(errors, "M016 is accepted (DEC-0116, the second R8 chain-child acceptance); it can never return to the active implementing state")
                if execution.get("halted_reason") is not None:
                    fail(errors, "execution-state.yaml halted_reason must be null while implementing")
                auth_root = ROOT / "spec/architect/authorizations"
                active_texts: list[tuple[str, str]] = []
                if auth_root.is_dir():
                    for apath in auth_root.glob("*.y*ml"):
                        atext = apath.read_text(encoding="utf-8")
                        if re.search(r"^status:\s*active\s*$", atext, re.MULTILINE) and re.search(r"^authorized:\s*true\s*$", atext, re.MULTILINE):
                            active_texts.append((apath.name, atext))
                if len(active_texts) != 1:
                    fail(errors, f"exactly one active authorization file is required while implementing, found {len(active_texts)}")
                else:
                    fname, atext = active_texts[0]
                    if not (f"work_item: {awi}" in atext or f"current_child_work_item: {awi}" in atext):
                        fail(errors, f"the active authorization {fname} does not bind work item {awi} (directly or as the current program child)")
                    if f"authorization_id: \"{aaz}\"" not in atext:
                        fail(errors, f"the active authorization {fname} does not carry authorization_id {aaz}")
                    base = re.search(r"^baseline_sha:\s*([0-9a-f]{40})\s*$", atext, re.MULTILINE)
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
                                fail(errors, f"the active authorization baseline is neither the reconciled main snapshot nor its ancestor")
            else:
                fail(errors, f"execution-state.yaml execution.mode must be awaiting-architect-decisions or implementing, got {mode!r}")
            decisions_text = "\n".join(str(x) for x in execution.get("next_required_decisions", []))
            if "R8" not in decisions_text:
                fail(errors, "execution-state.yaml does not identify R8 as the immediate next gate")
            if not isinstance(state.get("open_acrs"), list):
                fail(errors, "execution-state.yaml open_acrs must be a list")
            if not isinstance(state.get("open_architectural_questions"), list):
                fail(errors, "execution-state.yaml open_architectural_questions must be a list")
            if "ACR-014" in state.get("open_acrs", []):
                fail(errors, "ACR-014 is ACCEPTED (DEC-0100) and must not remain in open_acrs")

        # M001 acceptance closure invariants (independent of mode: fail
        # closed against the pre-acceptance M001-ACTIVE markers)
        m001_auth = ROOT / "spec/architect/authorizations/M001.yaml"
        if not m001_auth.is_file():
            fail(errors, "M001-CORE-001 authorization file missing")
        else:
            ma = m001_auth.read_text(encoding="utf-8")
            if not re.search(r"^status:\s*accepted\s*$", ma, re.MULTILINE):
                fail(errors, "M001 authorization must be status accepted after the DEC-0100 acceptance")
            if not re.search(r"^authorized:\s*false\s*$", ma, re.MULTILINE):
                fail(errors, "M001 authorization must be authorized false after the DEC-0100 acceptance")
            if "acceptance_decision: DEC-0100" not in ma:
                fail(errors, "M001 authorization acceptance gate must record DEC-0100")
            if "accepted_delivery_sha: 36bfd8e636feafb531ef551a2e15793b57cc2f00" not in ma:
                fail(errors, "M001 authorization acceptance gate must record the exact accepted delivery head")
            if "acceptance_merge_sha: 80292c24502200f84d11491ed12e9cec5e5baf11" not in ma:
                fail(errors, "M001 authorization acceptance gate must record the exact acceptance merge")

        # R7 program-authorization closure invariants (independent of mode:
        # fail closed against the pre-completion ACTIVE markers)
        r7_auth = ROOT / "spec/architect/authorizations/R7.yaml"
        if not r7_auth.is_file():
            fail(errors, "R7-CORE-001 authorization file missing")
        else:
            ra = r7_auth.read_text(encoding="utf-8")
            if not re.search(r"^status:\s*accepted\s*$", ra, re.MULTILINE):
                fail(errors, "R7 authorization must be status accepted after the DEC-0109 gate completion")
            if not re.search(r"^authorized:\s*false\s*$", ra, re.MULTILINE):
                fail(errors, "R7 authorization must be authorized false after the DEC-0109 gate completion")
            if "acceptance_decision: DEC-0109" not in ra:
                fail(errors, "R7 authorization acceptance gate must record DEC-0109")
            if "accepted_delivery_sha: 689035e3803e308f2bb89cd11bc373d897b77416" not in ra:
                fail(errors, "R7 authorization acceptance gate must record the exact accepted delivery head")
            if "acceptance_merge_sha: 344cd64e8396c7e388e31a50635ddff16bb4ea14" not in ra:
                fail(errors, "R7 authorization acceptance gate must record the exact acceptance merge")
            if "current_child_work_item: M014" in ra:
                fail(errors, "R7 authorization current_child_work_item must be null after the gate completion")

        # R8 program-authorization ACTIVE invariants (independent of mode:
        # fail closed against the pre-activation halted markers)
        r8_auth = ROOT / "spec/architect/authorizations/R8.yaml"
        if not r8_auth.is_file():
            fail(errors, "R8-CORE-001 authorization file missing")
        else:
            r8a = r8_auth.read_text(encoding="utf-8")
            if not re.search(r"^status:\s*active\s*$", r8a, re.MULTILINE):
                fail(errors, "R8 authorization must be status active after the DEC-0114 activation")
            if not re.search(r"^authorized:\s*true\s*$", r8a, re.MULTILINE):
                fail(errors, "R8 authorization must be authorized true after the DEC-0114 activation")
            if "authorization_decision: DEC-0114" not in r8a:
                fail(errors, "R8 authorization must record the DEC-0114 issuance decision")
            if "baseline_sha: 28b31500a928f2f75582bfb79039e315187d72b2" not in r8a:
                fail(errors, "R8 authorization must record the exact activation baseline (the DEC-0109 head)")
            if "current_child_work_item: M017" not in r8a:
                fail(errors, "R8 authorization must bind M017 as the current child work item after the DEC-0116 M016 acceptance")
            for child in ("M015", "M016", "M017", "M018", "M019"):
                if f"  - {child}" not in r8a:
                    fail(errors, f"R8 authorization child_work_items must declare {child}")

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
            m001_entry = next((e for e in items if isinstance(e, dict) and e.get("work_item") == "M001"), None)
            if not isinstance(m001_entry, dict):
                fail(errors, "execution-ledger.yaml must contain the M001 acceptance entry")
            else:
                if m001_entry.get("lifecycle") != "accepted-merged":
                    fail(errors, "execution-ledger.yaml M001 entry must be lifecycle accepted-merged")
                if m001_entry.get("acceptance_decision") != "DEC-0100":
                    fail(errors, "execution-ledger.yaml M001 entry must record acceptance decision DEC-0100")
                if m001_entry.get("merge_sha") != "80292c24502200f84d11491ed12e9cec5e5baf11":
                    fail(errors, "execution-ledger.yaml M001 entry must record the exact acceptance merge SHA")
                if m001_entry.get("reviewed_sha") != "36bfd8e636feafb531ef551a2e15793b57cc2f00":
                    fail(errors, "execution-ledger.yaml M001 entry must record the exact reviewed delivery head")
            m002_entry = next((e for e in items if isinstance(e, dict) and e.get("work_item") == "M002"), None)
            if not isinstance(m002_entry, dict):
                fail(errors, "execution-ledger.yaml must contain the M002 acceptance entry")
            else:
                if m002_entry.get("lifecycle") != "accepted-merged":
                    fail(errors, "execution-ledger.yaml M002 entry must be lifecycle accepted-merged")
                if m002_entry.get("acceptance_decision") != "DEC-0102":
                    fail(errors, "execution-ledger.yaml M002 entry must record acceptance decision DEC-0102")
                if m002_entry.get("merge_sha") != "0ffdf4775112c0b71b71f47f3688a50347ab4371":
                    fail(errors, "execution-ledger.yaml M002 entry must record the exact acceptance merge SHA")
                if m002_entry.get("reviewed_sha") != "0112943c99c7fd3215bf7c8d2b0ebb740a282132":
                    fail(errors, "execution-ledger.yaml M002 entry must record the exact reviewed delivery head")
            m003_entry = next((e for e in items if isinstance(e, dict) and e.get("work_item") == "M003"), None)
            if not isinstance(m003_entry, dict):
                fail(errors, "execution-ledger.yaml must contain the M003 acceptance entry")
            else:
                if m003_entry.get("lifecycle") != "accepted-merged":
                    fail(errors, "execution-ledger.yaml M003 entry must be lifecycle accepted-merged")
                if m003_entry.get("acceptance_decision") != "DEC-0103":
                    fail(errors, "execution-ledger.yaml M003 entry must record acceptance decision DEC-0103")
                if m003_entry.get("merge_sha") != "4090e032324fc4fa5fcc6ffe81a85c22eca331a3":
                    fail(errors, "execution-ledger.yaml M003 entry must record the exact acceptance merge SHA")
                if m003_entry.get("reviewed_sha") != "eace14349cbfae06235712778c578fbda0d4cffb":
                    fail(errors, "execution-ledger.yaml M003 entry must record the exact reviewed delivery head")
            m010_entry = next((e for e in items if isinstance(e, dict) and e.get("work_item") == "M010"), None)
            if not isinstance(m010_entry, dict):
                fail(errors, "execution-ledger.yaml must contain the M010 acceptance entry")
            else:
                if m010_entry.get("lifecycle") != "accepted-merged":
                    fail(errors, "execution-ledger.yaml M010 entry must be lifecycle accepted-merged")
                if m010_entry.get("acceptance_decision") != "DEC-0110":
                    fail(errors, "execution-ledger.yaml M010 entry must record acceptance decision DEC-0110")
                if m010_entry.get("merge_sha") != "d0d26d330b3101b963e8eadca01f164fb48c3fb9":
                    fail(errors, "execution-ledger.yaml M010 entry must record the exact acceptance merge SHA")
                if m010_entry.get("reviewed_sha") != "d5be84ed93674dc6d5001e27472baf596198f812":
                    fail(errors, "execution-ledger.yaml M010 entry must record the exact reviewed delivery head")
            m011_entry = next((e for e in items if isinstance(e, dict) and e.get("work_item") == "M011"), None)
            if not isinstance(m011_entry, dict):
                fail(errors, "execution-ledger.yaml must contain the M011 acceptance entry")
            else:
                if m011_entry.get("lifecycle") != "accepted-merged":
                    fail(errors, "execution-ledger.yaml M011 entry must be lifecycle accepted-merged")
                if m011_entry.get("acceptance_decision") != "DEC-0111":
                    fail(errors, "execution-ledger.yaml M011 entry must record acceptance decision DEC-0111")
                if m011_entry.get("merge_sha") != "c0f23c813ea98742316863f21532c4ce2fe5398a":
                    fail(errors, "execution-ledger.yaml M011 entry must record the exact acceptance merge SHA")
                if m011_entry.get("reviewed_sha") != "fb4a921092e114f74bf8d4c54c2d32c230425911":
                    fail(errors, "execution-ledger.yaml M011 entry must record the exact reviewed delivery head")
            m012_entry = next((e for e in items if isinstance(e, dict) and e.get("work_item") == "M012"), None)
            if not isinstance(m012_entry, dict):
                fail(errors, "execution-ledger.yaml must contain the M012 acceptance entry")
            else:
                if m012_entry.get("lifecycle") != "accepted-merged":
                    fail(errors, "execution-ledger.yaml M012 entry must be lifecycle accepted-merged")
                if m012_entry.get("acceptance_decision") != "DEC-0112":
                    fail(errors, "execution-ledger.yaml M012 entry must record acceptance decision DEC-0112")
                if m012_entry.get("merge_sha") != "6e3d09f4f860371437e6f819466a8c177dfadde4":
                    fail(errors, "execution-ledger.yaml M012 entry must record the exact acceptance merge SHA")
                if m012_entry.get("reviewed_sha") != "201ceb8e8e8bab0b1f2643e1e69a2ac29666c988":
                    fail(errors, "execution-ledger.yaml M012 entry must record the exact reviewed delivery head")
            m004_entry = next((e for e in items if isinstance(e, dict) and e.get("work_item") == "M004"), None)
            if not isinstance(m004_entry, dict):
                fail(errors, "execution-ledger.yaml must contain the M004 acceptance entry")
            else:
                if m004_entry.get("lifecycle") != "accepted-merged":
                    fail(errors, "execution-ledger.yaml M004 entry must be lifecycle accepted-merged")
                if m004_entry.get("acceptance_decision") != "DEC-0104":
                    fail(errors, "execution-ledger.yaml M004 entry must record acceptance decision DEC-0104")
                if m004_entry.get("merge_sha") != "a52e1eefd352f4636ef368ff97b92682ff11c100":
                    fail(errors, "execution-ledger.yaml M004 entry must record the exact acceptance merge SHA")
                if m004_entry.get("reviewed_sha") != "92f293bfcdf7794a1dcd090d2545db28e7bc0f96":
                    fail(errors, "execution-ledger.yaml M004 entry must record the exact reviewed delivery head")
            m005_entry = next((e for e in items if isinstance(e, dict) and e.get("work_item") == "M005"), None)
            if not isinstance(m005_entry, dict):
                fail(errors, "execution-ledger.yaml must contain the M005 acceptance entry")
            else:
                if m005_entry.get("lifecycle") != "accepted-merged":
                    fail(errors, "execution-ledger.yaml M005 entry must be lifecycle accepted-merged")
                if m005_entry.get("acceptance_decision") != "DEC-0105":
                    fail(errors, "execution-ledger.yaml M005 entry must record acceptance decision DEC-0105")
                if m005_entry.get("merge_sha") != "ccae48809bff22a973f6c3fba7a5b6345ede2c4c":
                    fail(errors, "execution-ledger.yaml M005 entry must record the exact acceptance merge SHA")
                if m005_entry.get("reviewed_sha") != "a0c4aff3663a2a5ea1b13cc6a26a6bcde97c34b0":
                    fail(errors, "execution-ledger.yaml M005 entry must record the exact reviewed delivery head")
            m006_entry = next((e for e in items if isinstance(e, dict) and e.get("work_item") == "M006"), None)
            if not isinstance(m006_entry, dict):
                fail(errors, "execution-ledger.yaml must contain the M006 acceptance entry")
            else:
                if m006_entry.get("lifecycle") != "accepted-merged":
                    fail(errors, "execution-ledger.yaml M006 entry must be lifecycle accepted-merged")
                if m006_entry.get("acceptance_decision") != "DEC-0106":
                    fail(errors, "execution-ledger.yaml M006 entry must record acceptance decision DEC-0106")
                if m006_entry.get("merge_sha") != "1f9f509eda02b6c98dc624a321caa125586d05e0":
                    fail(errors, "execution-ledger.yaml M006 entry must record the exact acceptance merge SHA")
                if m006_entry.get("reviewed_sha") != "764007bb6ec068628a861e0d3f1fe5eec53a1eae":
                    fail(errors, "execution-ledger.yaml M006 entry must record the exact reviewed delivery head")
            m007_entry = next((e for e in items if isinstance(e, dict) and e.get("work_item") == "M007"), None)
            if not isinstance(m007_entry, dict):
                fail(errors, "execution-ledger.yaml must contain the M007 acceptance entry")
            else:
                if m007_entry.get("lifecycle") != "accepted-merged":
                    fail(errors, "execution-ledger.yaml M007 entry must be lifecycle accepted-merged")
                if m007_entry.get("acceptance_decision") != "DEC-0107":
                    fail(errors, "execution-ledger.yaml M007 entry must record acceptance decision DEC-0107")
                if m007_entry.get("merge_sha") != "cc93bb4992151ba01b6c892e2bbf1c277d7716a4":
                    fail(errors, "execution-ledger.yaml M007 entry must record the exact acceptance merge SHA")
                if m007_entry.get("reviewed_sha") != "1636b15f8d639f0896b2b42567d6e2da99b53678":
                    fail(errors, "execution-ledger.yaml M007 entry must record the exact reviewed delivery head")
            m008_entry = next((e for e in items if isinstance(e, dict) and e.get("work_item") == "M008"), None)
            if not isinstance(m008_entry, dict):
                fail(errors, "execution-ledger.yaml must contain the M008 acceptance entry")
            else:
                if m008_entry.get("lifecycle") != "accepted-merged":
                    fail(errors, "execution-ledger.yaml M008 entry must be lifecycle accepted-merged")
                if m008_entry.get("acceptance_decision") != "DEC-0108":
                    fail(errors, "execution-ledger.yaml M008 entry must record acceptance decision DEC-0108")
                if m008_entry.get("merge_sha") != "ce65c88fd5fe632613be1cedf3c8c1519990a825":
                    fail(errors, "execution-ledger.yaml M008 entry must record the exact acceptance merge SHA")
                if m008_entry.get("reviewed_sha") != "8c7d685d5eacea66c71b1a8aa706bd05c809c78c":
                    fail(errors, "execution-ledger.yaml M008 entry must record the exact reviewed delivery head")
            m014_entry = next((e for e in items if isinstance(e, dict) and e.get("work_item") == "M014"), None)
            if not isinstance(m014_entry, dict):
                fail(errors, "execution-ledger.yaml must contain the M014 acceptance entry")
            else:
                if m014_entry.get("lifecycle") != "accepted-merged":
                    fail(errors, "execution-ledger.yaml M014 entry must be lifecycle accepted-merged")
                if m014_entry.get("acceptance_decision") != "DEC-0109":
                    fail(errors, "execution-ledger.yaml M014 entry must record acceptance decision DEC-0109")
                if m014_entry.get("merge_sha") != "344cd64e8396c7e388e31a50635ddff16bb4ea14":
                    fail(errors, "execution-ledger.yaml M014 entry must record the exact acceptance merge SHA")
                if m014_entry.get("reviewed_sha") != "689035e3803e308f2bb89cd11bc373d897b77416":
                    fail(errors, "execution-ledger.yaml M014 entry must record the exact reviewed delivery head")
            m015_entry = next((e for e in items if isinstance(e, dict) and e.get("work_item") == "M015"), None)
            if not isinstance(m015_entry, dict):
                fail(errors, "execution-ledger.yaml must contain the M015 acceptance entry")
            else:
                if m015_entry.get("lifecycle") != "accepted-merged":
                    fail(errors, "execution-ledger.yaml M015 entry must be lifecycle accepted-merged")
                if m015_entry.get("acceptance_decision") != "DEC-0115":
                    fail(errors, "execution-ledger.yaml M015 entry must record acceptance decision DEC-0115")
                if m015_entry.get("merge_sha") != "d77a56197b0450ee04c61b356389cf8800aac288":
                    fail(errors, "execution-ledger.yaml M015 entry must record the exact acceptance merge SHA")
                if m015_entry.get("reviewed_sha") != "95a65a54076b1401ea8ca414faa49a383ee2eb5f":
                    fail(errors, "execution-ledger.yaml M015 entry must record the exact reviewed delivery head")
            m016_entry = next((e for e in items if isinstance(e, dict) and e.get("work_item") == "M016"), None)
            if not isinstance(m016_entry, dict):
                fail(errors, "execution-ledger.yaml must contain the M016 acceptance entry")
            else:
                if m016_entry.get("lifecycle") != "accepted-merged":
                    fail(errors, "execution-ledger.yaml M016 entry must be lifecycle accepted-merged")
                if m016_entry.get("acceptance_decision") != "DEC-0116":
                    fail(errors, "execution-ledger.yaml M016 entry must record acceptance decision DEC-0116")
                if m016_entry.get("merge_sha") != "a0ebd019a03238d089f03f006e9364e5c03cde51":
                    fail(errors, "execution-ledger.yaml M016 entry must record the exact acceptance merge SHA")
                if m016_entry.get("reviewed_sha") != "0d5cfb742d14bf3f257008593f7b0a22d98cc971":
                    fail(errors, "execution-ledger.yaml M016 entry must record the exact reviewed delivery head")
            m009_entry = next((e for e in items if isinstance(e, dict) and e.get("work_item") == "M009"), None)
            if not isinstance(m009_entry, dict):
                fail(errors, "execution-ledger.yaml must contain the M009 acceptance entry")
            else:
                if m009_entry.get("lifecycle") != "accepted-merged":
                    fail(errors, "execution-ledger.yaml M009 entry must be lifecycle accepted-merged")
                if m009_entry.get("acceptance_decision") != "DEC-0109":
                    fail(errors, "execution-ledger.yaml M009 entry must record acceptance decision DEC-0109")
                if m009_entry.get("merge_sha") != "c985b8876b7d215a7af6a2fdaca5f78eb51fdf58":
                    fail(errors, "execution-ledger.yaml M009 entry must record the exact acceptance merge SHA")
                if m009_entry.get("reviewed_sha") != "5a807cdfc0c402ffa88818faf1127c708f7fd1c9":
                    fail(errors, "execution-ledger.yaml M009 entry must record the exact reviewed delivery head")
            m013_entry = next((e for e in items if isinstance(e, dict) and e.get("work_item") == "M013"), None)
            if not isinstance(m013_entry, dict):
                fail(errors, "execution-ledger.yaml must contain the M013 acceptance entry")
            else:
                if m013_entry.get("lifecycle") != "accepted-merged":
                    fail(errors, "execution-ledger.yaml M013 entry must be lifecycle accepted-merged")
                if m013_entry.get("acceptance_decision") != "DEC-0113":
                    fail(errors, "execution-ledger.yaml M013 entry must record acceptance decision DEC-0113")
                if m013_entry.get("merge_sha") != "8f4d58a23966a3af5242f37bab293a114cf5085a":
                    fail(errors, "execution-ledger.yaml M013 entry must record the exact acceptance merge SHA")
                if m013_entry.get("reviewed_sha") != "69ef8dee1adcf8c8a6f5855c9056d0364a0fd7b9":
                    fail(errors, "execution-ledger.yaml M013 entry must record the exact reviewed delivery head")

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
