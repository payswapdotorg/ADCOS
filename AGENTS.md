# ADCOS Agent Entry Point

ADCOS is self-describing. A new Architect, Tech Lead, worker, or implementation agent MUST derive authority from the repository and live GitHub state, never from chat history.

## Role bootstrap

- **Architect:** read `spec/architect/resume-protocol.md`, then reconstruct authority and govern sequencing, authorization, review, acceptance and merge.
- **Tech Lead:** read `docs/tech-lead/ADCOS-TECH-LEAD-HANDOFF.md` and `docs/tech-lead/worker-model.md` after this file; coordinate authorized implementation work and independently verify workers.
- **Worker:** read the Tech Lead handoff, the exact authorized Work Item, its dependency overlay and the applicable architecture/locks before changing code.

## Resume order

1. Read `README.md` and this file.
2. Read `spec/architect/resume-protocol.md`.
3. Read `spec/mission.md`.
4. Read the current frozen `spec/architecture.md` and `spec/architecture-lock.md`.
5. Read `spec/work-items.md` and `spec/dependency-graph.md`.
6. Read `spec/architect/roadmap.yaml`, `spec/architect/current-state.md`, and `spec/architect/execution-state.yaml`.
7. Read `spec/architect/authority-order.md` and `spec/architect/governance-autonomy.md`.
8. Identify the current active Work Item and repository-local authorization, if any.
9. Inspect actual GitHub `main` and recent commits before acting.

## Live-main rule

Always compare the actual `main` SHA with `spec/architect/execution-state.yaml`. If they differ, inspect the intervening commits and reconcile the persistent Architect snapshot before implementation resumes. A newer mainline always supersedes an older snapshot.

## Authorization

No active repository-local authorization means implementation MUST stop. Roadmap membership, an issue, a PR, a handoff, or a chat instruction never grants implementation permission.

At most one implementation authorization may be active at a time.

## Tech Lead dispatch limit

The Tech Lead may dispatch at most 3 direct workers. Each direct worker may dispatch at most 3 subagents. Maximum active descendants: 9.

Parallel work is permitted only when dependency and authority boundaries are independent. The Tech Lead remains responsible for integration and verification.

## Frozen architecture

Never modify frozen architecture documents from an ordinary implementation PR. Architecture changes require the repository's ACR/change-control process.

`spec/architecture-1.1-proposed.md` is a proposal until formally promoted by an accepted ACR. Do not treat proposal files as authority merely because they exist.

## Evidence

Never convert software/emulated evidence into physical PASS by inference. Never treat an agent report, test count, PR description, or generated audit as authoritative without repository verification.

## Working practice

Prefer a local Git clone and ordinary Git history for multi-file changes. Do not write directly to `main` for implementation or governance transitions that require review.

## Verification

Before acting from a fresh session, run:

```bash
python3 tools/spec_check.py
```

If the persistent governance package fails its checks, repair governance through the proper review mechanism; never weaken the invariant to make a task pass.

## Fresh-session guarantee

A clean clone of `main` plus GitHub access, without conversation history, MUST be sufficient to determine mission, authoritative architecture, roadmap state, current execution state, next gate, implementation authorization, worker limits, and acceptance requirements.
