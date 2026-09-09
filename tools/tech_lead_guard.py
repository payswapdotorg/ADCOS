#!/usr/bin/env python3
"""Validate the repository's machine-readable Tech Lead dispatch contract."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from spec_check import yaml_subset_load  # type: ignore  # noqa: E402

STATE = ROOT / "docs/tech-lead/dispatch-state.yaml"


def fail(message: str) -> int:
    print(f"[FAIL] {message}")
    print("tech-lead guard: FAIL")
    return 1


def main() -> int:
    if not STATE.is_file():
        return fail("missing docs/tech-lead/dispatch-state.yaml")

    data = yaml_subset_load(STATE.read_text(encoding="utf-8"), str(STATE))
    if not isinstance(data, dict):
        return fail("dispatch-state.yaml must be a mapping")

    expected_caps = {
        "max_direct_workers": 3,
        "max_subagents_per_worker": 3,
        "max_active_descendants": 9,
        "max_depth": 2,
    }
    for key, expected in expected_caps.items():
        if data.get(key) != expected:
            return fail(f"{key} must be exactly {expected}, got {data.get(key)!r}")

    workers = data.get("active_workers")
    if not isinstance(workers, list):
        return fail("active_workers must be a list")

    if len(workers) > 3:
        return fail(f"Tech Lead has {len(workers)} active direct workers; maximum is 3")

    ids: set[str] = set()
    subagent_total = 0
    for worker in workers:
        if not isinstance(worker, dict):
            return fail("each active worker entry must be a mapping")
        worker_id = worker.get("id")
        if not isinstance(worker_id, str) or not worker_id:
            return fail("each active worker must have a non-empty id")
        if worker_id in ids:
            return fail(f"duplicate active worker id: {worker_id}")
        ids.add(worker_id)

        subagents = worker.get("subagents", [])
        if not isinstance(subagents, list):
            return fail(f"worker {worker_id}: subagents must be a list")
        if len(subagents) > 3:
            return fail(f"worker {worker_id} has {len(subagents)} active subagents; maximum is 3")
        subagent_total += len(subagents)

        sub_ids: set[str] = set()
        for subagent in subagents:
            if not isinstance(subagent, dict):
                return fail(f"worker {worker_id}: each subagent entry must be a mapping")
            sub_id = subagent.get("id")
            if not isinstance(sub_id, str) or not sub_id:
                return fail(f"worker {worker_id}: each subagent must have a non-empty id")
            if sub_id in sub_ids:
                return fail(f"worker {worker_id}: duplicate subagent id: {sub_id}")
            sub_ids.add(sub_id)
            if "subagents" in subagent:
                return fail(f"subagent {sub_id} cannot dispatch a third hierarchy level")

    if subagent_total > 9:
        return fail(f"dispatch state declares {subagent_total} active subagents; maximum is 9")

    if data.get("status") not in {"IDLE", "ACTIVE"}:
        return fail(f"dispatch state has invalid status: {data.get('status')!r}")

    if data.get("status") == "IDLE" and workers:
        return fail("status IDLE cannot contain active workers")
    if workers and data.get("status") != "ACTIVE":
        return fail("non-empty active_workers requires status ACTIVE")

    rules = data.get("rules")
    if not isinstance(rules, list) or len(rules) < 5:
        return fail("dispatch-state.yaml must retain the repository dispatch safety rules")

    print("tech-lead guard: PASS")
    print("direct workers <= 3; subagents per worker <= 3; active subagents <= 9; hierarchy depth <= 2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
