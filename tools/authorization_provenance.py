#!/usr/bin/env python3
"""Current-era implementation-PR authorization provenance gate (ARCH-08 successor).

Replaces the legacy ``tools/spec_check.py --provenance`` CI invocation for
implementation PRs. The legacy checker stays the frozen non-blocking
compatibility audit (its WORK-* glob and frozen schema cannot see M-item or
R7 program authorizations, and its ARCH-02 parse debt is recorded as blocking
in provenance mode — structurally unsatisfiable for post-M001 implementation
PRs). This checker carries ARCH-08's semantics forward, evolved for the
DEC-0101 R7 program-authorization model:

- the PR delta (committed working-tree diff + untracked files) vs origin/main;
- implementation files = delta minus the drift-guard control-plane
  classification (single source of truth via architecture_drift_guard);
- no implementation delta -> PASS trivially (governance/meta-only PR);
- implementation PRs must not modify the persistent Architect package
  (spec/architect/);
- exactly ONE active authorization (status: active + authorized: true);
- every implementation file covered by its declared scope (exact path or
  prefix), including the direct and program (current-child) authorization
  models;
- the authorization baseline must equal the branch execution-state snapshot,
  or precede it through governance-only commits only (the standing
  reconciliation convention, same range logic as fresh_session_check), or —
  the bounded program-authorization generalization (DEC-0101, recorded by the
  DEC-0102-era repair) — precede it through a range whose aggregate delta is
  exclusively control-plane files or files covered by the active
  authorization's own declared scope (authorized child deliveries plus the
  governance transitions between them); fail closed otherwise;
- the authorization file must be inherited byte-identically from origin/main
  (no self-authorization, no in-PR modification).

This module is also the shared authority for the batteries'
authorization-aware delta-shape consultation (the docs/M001-evidence.md
section-4 duty for the post-M001 implementation era): ``active_authorization()``
and ``covers()`` are importable by the battery selftests so their PR-delta
shape cases validate deltas against the ACTIVE repository-local
authorization scope instead of frozen historical per-battery scopes.
Fail-closed everywhere: no/single active authorization ambiguity, git
failures, and out-of-scope paths all fail.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from architecture_drift_guard import CONTROL_FILES, CONTROL_PREFIXES  # type: ignore  # noqa: E402

AUTH_ROOT = ROOT / "spec/architect" / "authorizations"
DECISIONS_ROOT = ROOT / "spec/architect" / "decisions"

#: The decision-borne path surface: each accepted decision record that
#: carries an ``authorized_scope`` block (the repository-local
#: decision-borne authorization class founded by DEC-0126 — authority
#: recorded in the DECISIONS registry itself, OUTSIDE the
#: authorizations/ gate machinery, exactly as the decision's own
#: rejected_scope declares) maps to the concrete implementation path
#: prefixes its bounded program authorizes.  The mapping is the
#: checker's machine knowledge of the decision's declared prose scope
#: (the worker-allocation surface of the recorded handoff and the
#: T1-T6 delivery it governs).  A decision-borne record whose id is
#: absent here fails CLOSED: the checker must be taught its scope
#: before its implementation may proceed (no implicit coverage, ever).
_DECISION_BORNE_PATH_SURFACE = {
    "DEC-0126": (
        "runtime/",
        "backends/",
        "api/",
        "deploy/",
        "docs/deployment/",
        "docs/tech-lead/",
        "tools/runtime_selftest.py",
        "tools/persistence_selftest.py",
        "tools/coordination_selftest.py",
        "tools/artifact_selftest.py",
        "docs/superpowers/specs/2026-09-13-adcos-free-tier-deployment-design.md",
        "docs/superpowers/plans/2026-09-13-adcos-free-tier-deployment.md",
        "vercel.json",
        "requirements.txt",
        ".vercelignore",
    ),
    # DEC-0127 (2026-09-14): the bounded ADCOS developer console program —
    # the successor of the COMPLETED DEC-0126 deployment program (retired to
    # status SUPERSEDED by the same reconciliation that registers this
    # record). The surface is the console program's declared scope: the web
    # console application, the runtime boundary widening onto the accepted
    # developerapi gateway route table (asgi.py only — the wiring/sandbox/
    # services/health/demo modules stay at their accepted deployment-era
    # semantics), the runtime battery extension, the explicit web/API Vercel
    # routing, the deployment verification/runbook extension, and the
    # console planning/handoff documents. Fail closed on everything else.
    "DEC-0127": (
        "web/",
        "runtime/asgi.py",
        "tools/runtime_selftest.py",
        "docs/superpowers/specs/2026-09-14-adcos-developer-console-design.md",
        "docs/superpowers/plans/2026-09-14-adcos-developer-console.md",
        "docs/tech-lead/",
        "vercel.json",
        ".vercelignore",
        "deploy/verify.py",
        "docs/deployment/",
    ),
    # DEC-0128 (2026-09-14): the bounded ADCOS Console V2 learning-first
    # product experience program — the successor of the COMPLETED DEC-0127
    # developer console program (implementation + production deployment +
    # acceptance; retired to status SUPERSEDED by the same reconciliation
    # that registers this record). The surface is the V2 program's declared
    # scope: the Console V2 learning layer inside the web console
    # application (the education model and concept/operation/guide
    # registries, the learning primitives, the user-facing documentation
    # system and its routes, the first-run product experience, the Quickstart
    # and the interactive fulfillment tour, the Playbooks, the API-learning
    # integration in the API Explorer, the troubleshooting education, the
    # expert-handoff context links, and the V2/V1 frontend tests), the V2
    # planning documents delivered by PR #59, the Tech Lead dispatch state
    # during the program, the deployment verification/acceptance records for
    # the V2 release, and the explicit web/API deployment routing if needed.
    # Fail closed on everything else.
    "DEC-0128": (
        "web/",
        "docs/superpowers/specs/2026-09-14-adcos-console-v2-learning-experience-design.md",
        "docs/superpowers/plans/2026-09-14-adcos-console-v2-learning-experience.md",
        "docs/tech-lead/",
        "deploy/verify.py",
        "docs/deployment/",
        "vercel.json",
        ".vercelignore",
    ),
}


def _is_control(path: str) -> bool:
    return path.startswith(CONTROL_PREFIXES) or path in CONTROL_FILES


def _git(args: list[str]) -> Optional[str]:
    try:
        p = subprocess.run(
            ["git", *args], cwd=ROOT, text=True, capture_output=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return p.stdout


def _scope_from_text(text: str) -> list[str]:
    """Extract the block-list scope entries from an authorization file."""
    scope: list[str] = []
    in_scope = False
    for line in text.splitlines():
        if in_scope:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            entry = re.match(r"^\s+-\s+(.+?)\s*$", line)
            if entry:
                value = entry.group(1).strip()
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                scope.append(value)
                continue
            # any non-list, non-comment line ends the scope block
            in_scope = False
        elif re.match(r"^scope:\s*(\[\]\s*)?(#.*)?$", line):
            in_scope = True
    return scope


def _field(text: str, key: str) -> Optional[str]:
    m = re.search(r"^\s*%s:\s*[\"']?([^\"'\s#]+)" % re.escape(key), text, re.MULTILINE)
    return m.group(1) if m else None


def _decision_borne_authorization() -> tuple[Optional[dict], Optional[str]]:
    """The single accepted decision-borne authorization, or a fail-closed reason.

    The post-program class (founded by DEC-0126, the bounded ADCOS
    software deployment authorization): a decision record whose own
    ``authorized_scope`` block creates repository-local implementation
    authority recorded in the DECISIONS registry — outside the
    authorizations/ gate machinery — while the gate sequence R0-R9
    stays COMPLETE and halted (DEC-0125, execution mode
    awaiting-architect-decisions).  Exactly one such record may be
    accepted at a time: the same single-active-authorization invariant,
    extended to the decision registry.  Records without an
    ``authorized_scope`` block are ordinary decisions and never count.
    Fail closed on ambiguity and on unmapped scopes alike.

    The baseline is the decision's own recorded live-main issuance
    provenance (the first full 40-hex SHA in its ``review_basis``) —
    frozen, never rewritten; the standing reconciliation convention
    and the bounded program-range generalization reconcile it to the
    execution-state snapshot exactly as a gate authorization's
    baseline_sha would be.
    """
    if not DECISIONS_ROOT.is_dir():
        return None, None
    accepted: list[tuple[str, str]] = []
    for path in sorted(DECISIONS_ROOT.glob("DEC-*.y*ml")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if not re.search(r"^authorized_scope:\s*$", text, re.MULTILINE):
            continue
        if not (
            re.search(r"^status:\s*ACCEPTED\s*$", text, re.MULTILINE)
            and re.search(r"^decision:\s*ACCEPTED\s*$", text, re.MULTILINE)
        ):
            continue
        accepted.append((path.name, text))
    if not accepted:
        return None, None
    if len(accepted) > 1:
        return None, (
            "multiple accepted decision-borne authorizations (%s); exactly "
            "one may be active" % ", ".join(n for n, _ in accepted)
        )
    name, text = accepted[0]
    decision_id = _field(text, "decision_id") or ""
    surface = _DECISION_BORNE_PATH_SURFACE.get(decision_id)
    if not surface:
        return None, (
            "decision-borne authorization %s carries no path-surface mapping; "
            "the checker must be taught its scope before its implementation "
            "may proceed" % decision_id
        )
    baseline: Optional[str] = None
    # the review_basis is a long single-line quoted value: extract the
    # decision's own recorded live-main SHA (the first full 40-hex on
    # that line — the issuance provenance, frozen at decision time)
    m = re.search(r"^review_basis:.*?\b([0-9a-f]{40})\b", text, re.MULTILINE)
    if m:
        baseline = m.group(1)
    record = {
        "file": name,
        "relpath": "spec/architect/decisions/%s" % name,
        "authorization_id": "DECISION-BORNE:%s" % decision_id,
        "decision_id": decision_id,
        "work_item": None,
        "current_child_work_item": None,
        "baseline_sha": baseline,
        "scope": list(surface),
        "text": text,
    }
    return record, None


def active_authorization() -> tuple[Optional[dict], Optional[str]]:
    """The single active repository-local authorization, or a fail-closed reason.

    Returns (record, None) when exactly one authorization file declares
    status: active + authorized: true; otherwise (None, reason). The record
    carries the parsed identity fields and the declared scope list.
    """
    if not AUTH_ROOT.is_dir():
        return None, "spec/architect/authorizations/ is missing"
    active: list[tuple[str, str]] = []
    for path in sorted(AUTH_ROOT.glob("*.y*ml")):
        text = path.read_text(encoding="utf-8")
        if re.search(r"^status:\s*active\s*$", text, re.MULTILINE) and re.search(
            r"^authorized:\s*true\s*$", text, re.MULTILINE
        ):
            active.append((path.name, text))
    if not active:
        # the post-program decision-borne class (DEC-0126): when no gate
        # authorization is active (the halted post-R9 state under
        # DEC-0125), the accepted decision-borne record is the active
        # repository-local implementation authority — the SAME single-
        # active invariant, the decision registry as the source
        record, reason = _decision_borne_authorization()
        if record is not None:
            return record, None
        if reason is not None:
            return None, reason
        return None, "no repository-local authorization is active — NO CURRENT AUTHORIZATION = IMPLEMENTATION MUST STOP"
    if len(active) > 1:
        return None, "multiple active authorizations (%s); exactly one may be active" % ", ".join(n for n, _ in active)
    name, text = active[0]
    record = {
        "file": name,
        "authorization_id": _field(text, "authorization_id"),
        "work_item": _field(text, "work_item"),
        "current_child_work_item": _field(text, "current_child_work_item"),
        "baseline_sha": _field(text, "baseline_sha"),
        "scope": _scope_from_text(text),
        "text": text,
    }
    return record, None


def covers(path: str) -> bool:
    """True when the single active authorization's scope covers the path.

    Fail-closed: no unique active authorization means nothing is covered.
    """
    record, _ = active_authorization()
    if record is None:
        return False
    scope = record.get("scope") or []
    return any(path == entry or path.startswith(entry) for entry in scope)


def _governance_only_range(persisted: str, actual: str) -> tuple[bool, Optional[str]]:
    """True when every commit in (persisted..actual] is control-plane only."""
    try:
        from fresh_session_check import _governance_only_range as _range  # type: ignore
    except Exception:  # pragma: no cover - same-repo import always available
        return False, "cannot import the reconciliation range logic; fail closed"
    return _range(persisted, actual)


def _authorized_program_range(
    persisted: str, actual: str, record: dict
) -> tuple[bool, Optional[str]]:
    """The bounded program-authorization baseline generalization.

    True when the AGGREGATE delta of (persisted..actual] is exclusively
    control-plane files or files covered by the active authorization's own
    declared scope - i.e. the range contains authorized child deliveries
    (implementation files inside the declared scope) plus the governance
    transitions between them, and nothing else. This is the honest range
    semantics for a program authorization whose children are progressively
    delivered and accepted: its issuance baseline (frozen provenance, never
    rewritten) legitimately precedes the reconciled snapshot by the exact
    deliveries it authorized. Fail closed on any path outside both classes.
    """
    if not re.fullmatch(r"[0-9a-f]{40}", str(persisted)) or not re.fullmatch(
        r"[0-9a-f]{40}", str(actual)
    ):
        return False, "invalid range endpoints"
    ancestor = _git(["merge-base", "--is-ancestor", persisted, actual])
    if ancestor is None:
        return False, "cannot inspect the baseline range; fail closed"
    diff = _git(["diff", "--name-only", "%s..%s" % (persisted, actual)])
    if diff is None:
        return False, "cannot diff the baseline range; fail closed"
    scope = record.get("scope") or []
    outside = [
        p
        for p in (line.strip() for line in diff.splitlines())
        if p
        and not _is_control(p)
        and not any(p == s or p.startswith(s) for s in scope)
    ]
    if outside:
        return False, (
            "baseline range contains paths outside both the control plane and the "
            "active authorization's declared scope: %s" % ", ".join(outside[:5])
        )
    return True, None


def check() -> int:
    problems: list[str] = []

    base = _git(["rev-parse", "--verify", "origin/main"])
    if base is None:
        print("[FAIL] provenance verification requires the origin/main ref (fetch the PR base first); none is available")
        print("authorization provenance: FAIL")
        return 1
    base = base.strip()

    delta: set[str] = set()
    diff = _git(["diff", "--name-only", "origin/main"])
    if diff is not None:
        delta |= {line.strip() for line in diff.splitlines() if line.strip()}
    untracked = _git(["ls-files", "--others", "--exclude-standard"])
    if untracked is not None:
        delta |= {line.strip() for line in untracked.splitlines() if line.strip()}

    implementation = sorted(p for p in delta if not _is_control(p))
    package_changes = sorted(p for p in delta if p.startswith("spec/architect/"))

    if not implementation:
        print("authorization provenance: PASS")
        print("governance/meta-only delta (%d control-plane file(s)); no implementation authorization required" % len(delta))
        return 0

    if package_changes:
        problems.append(
            "implementation PR must not modify the persistent Architect package (%s)"
            % ", ".join(package_changes[:5])
        )

    record, reason = active_authorization()
    if record is None:
        problems.append(
            "implementation delta present (%d file(s)) but %s"
            % (len(implementation), reason)
        )
        problems.append(
            "an in-review ledger entry is descriptive only and is never authorization "
            "(PA-001, DEC-0045); the Architect must record an active authorization on "
            "main (spec/architect/authorizations/) before any implementation delta may proceed"
        )
    else:
        auth_rel = record.get("relpath") or (
            "spec/architect/authorizations/%s" % record["file"]
        )
        scope = record.get("scope") or []
        uncovered = [p for p in implementation if not any(p == s or p.startswith(s) for s in scope)]
        if uncovered:
            problems.append(
                "implementation files outside the authorized scope of %s (%s): %s"
                % (record.get("authorization_id"), auth_rel, ", ".join(uncovered[:5]))
            )
        # the exact baseline of the persistent state: equal to the branch
        # execution-state snapshot, or an ancestor of it through
        # governance-only commits (the standing reconciliation convention)
        execution = (ROOT / "spec/architect/execution-state.yaml").read_text(encoding="utf-8")
        pin = _field(execution, "main_sha")
        baseline = record.get("baseline_sha")
        if baseline is None or not re.fullmatch(r"[0-9a-f]{40}", str(baseline)):
            problems.append("%s: baseline_sha missing/invalid" % auth_rel)
        elif pin is None or not re.fullmatch(r"[0-9a-f]{40}", str(pin)):
            problems.append("execution-state.yaml: repository.main_sha missing/invalid")
        elif baseline != pin:
            ok, problem = _governance_only_range(baseline, pin)
            if not ok and problem is not None:
                # the bounded program-authorization generalization: the range
                # may also consist of authorized child deliveries (files
                # inside the active authorization's own declared scope) plus
                # the governance transitions between them
                ok, problem = _authorized_program_range(baseline, pin, record)
            if not ok and problem is not None:
                problems.append(
                    "%s: authorization baseline %s is not the reconciled main snapshot "
                    "%s and does not precede it through governance-only commits or "
                    "scope-covered program deliveries (%s)"
                    % (auth_rel, baseline, pin, problem)
                )
        # the active authorization must bind the execution-state work item
        awi = None
        m = re.search(r"^\s*active_work_item:\s*(\S+)", execution, re.MULTILINE)
        if m:
            awi = m.group(1)
        if awi and awi != "null":
            work_item = record.get("work_item")
            child = record.get("current_child_work_item")
            if awi != work_item and awi != child:
                problems.append(
                    "%s: the active authorization binds work item %s (current child %s) "
                    "but the execution state declares %s"
                    % (auth_rel, work_item, child, awi)
                )
        # byte-identical inheritance from the base: no self-authorization,
        # no in-PR modification
        base_content = _git(["show", "origin/main:%s" % auth_rel])
        if base_content is None:
            problems.append(
                "%s was added by this PR (self-authorization): the authorization "
                "must be inherited from main, recorded there by the Architect first" % auth_rel
            )
        else:
            current = (ROOT / auth_rel).read_text(encoding="utf-8")
            if base_content != current:
                problems.append(
                    "%s differs from origin/main (authorization modified by this PR)" % auth_rel
                )

    if problems:
        for problem in problems:
            print("[FAIL] %s" % problem)
        print("authorization provenance: FAIL")
        return 1
    print("authorization provenance: PASS")
    print(
        "implementation delta (%d file(s)) fully covered by the active authorization %s "
        "(baseline %s, byte-identical inheritance from origin/main)"
        % (len(implementation), record.get("authorization_id"), str(record.get("baseline_sha"))[:8])
    )
    return 0


def main() -> int:
    return check()


if __name__ == "__main__":
    sys.exit(main())
