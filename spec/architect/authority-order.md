# ADCOS Authority Order

**ACTIVE — Persistent Governance Authority**

This document defines precedence. Repository artifacts outrank chat and external context.

## Precedence

1. `spec/mission.md` — permanent mission authority.
2. Accepted architecture/lock snapshot produced by the Architecture Change Request process.
3. During the Architecture 1.1 transition: the accepted transition decision plus the `spec/architecture-1.1-proposed.md` / lock package as the mandatory forward design target; `spec/architecture.md` / `spec/architecture-lock.md` remain the preserved 1.0 baseline.
4. accepted ACRs and their frozen successor snapshots.
5. `spec/dependency-graph.md` plus accepted 1.1 successor/dependency snapshots when promoted.
6. `spec/work-items.md` plus accepted 1.1 successor Work Item contracts when promoted.
7. `spec/architect/roadmap.yaml` — canonical, frozen execution/program roadmap.
8. accepted durable decisions in `spec/architect/decisions/` and the lifecycle history in `spec/architect/execution-ledger.yaml`.
9. `spec/architect/execution-state.yaml` and `current-state.md` — current-state projections; they must agree with the higher authorities and actual main.
10. `spec/architect/authorizations/` — implementation permission only. An authorization cannot change architecture, roadmap, Work Item contract, or dependency semantics.
11. implementation evidence and CI results.
12. narrative documentation, issues, PR prose, handoffs, and worklogs.
13. **Chat history has zero authority at every level.**

## Forward-implementation rule

Architecture 1.1 is the mandatory forward target for new ADCOS behavior.
Architecture 1.0 is retained as a migration/compatibility baseline and historical
evidence. A Tech Lead or worker MUST NOT design new APIs, domain models,
authority boundaries, or capabilities from 1.0 semantics.

M001 — Architecture 1.1 Freeze is the controlled promotion gate. Before M001 is
accepted, only explicitly authorized transition/migration work may modify code.
After M001 acceptance, the accepted 1.1 snapshot and locks become the sole
normative architecture for forward implementation.

## Roadmap rule

`spec/architect/roadmap.yaml` is the sole roadmap authority. `roadmap.md` is its human projection. No other document may create a competing implementation order, milestone, priority, status, or dependency interpretation.

The current roadmap is **Version 1.5**. Any roadmap change requires a new durable governance decision and a new roadmap version. A chat proposal cannot change it.

## Current-state rule

Actual `main` is always checked first. If actual main differs from the persisted execution snapshot, the Architect must reconcile the snapshot against the newer main before implementation resumes. The repository is not allowed to remain internally contradictory after reconciliation.

## Permission rule

Roadmap membership, Work Item status, GitHub issues, PRs, prior handoffs, and chat designations never authorize implementation. Only a current repository-local authorization with `status: active` and `authorized: true`, inherited by the implementation branch from `main`, does.

## Historical integrity

Accepted historical delivery facts remain true even if a later mainline regresses or omits their artifacts. Such an omission is a mainline-integrity defect. The remedy is explicit restoration and reconciliation, not historical rewriting.

## Fresh-session rule

A new Architect, Tech Lead, worker, or implementation agent must be able to clone `main` and determine the 1.1 forward target, preserved 1.0 baseline, mission, roadmap, current execution state, accepted history, evidence state, next action, and whether implementation is authorized without access to any prior conversation.
