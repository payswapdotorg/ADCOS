# ADCOS Authority Order

**ACTIVE — Persistent Governance Authority**

This document defines precedence. Repository artifacts outrank chat and external context.

## Precedence

1. `spec/mission.md` — permanent mission authority.
2. `spec/architecture.md` — current frozen architecture semantics.
3. `spec/architecture-lock.md` — architecture locks.
4. accepted ACRs and their frozen successor snapshots.
5. `spec/dependency-graph.md` — dependency semantics and hard/advisory edges.
6. `spec/work-items.md` — Work Item contract registry.
7. `spec/architect/roadmap.yaml` — canonical, frozen execution/program roadmap.
8. accepted durable decisions in `spec/architect/decisions/` and the lifecycle history in `spec/architect/execution-ledger.yaml`.
9. `spec/architect/execution-state.yaml` and `current-state.md` — current-state projections; they must agree with the higher authorities and actual main.
10. `spec/architect/authorizations/` — implementation permission only. An authorization cannot change the roadmap, architecture, Work Item contract, or dependency graph.
11. implementation evidence and CI results.
12. narrative documentation, issues, PR prose, handoffs, and worklogs.
13. **Chat history has zero authority at every level.**

## Roadmap rule

`spec/architect/roadmap.yaml` is the sole roadmap authority. `roadmap.md` is its human projection. No other document may create a competing implementation order, milestone, priority, status, or dependency interpretation.

The roadmap is frozen at Version 1.0. Any change requires a new durable governance decision and a new roadmap version. A chat proposal cannot change it.

## Current-state rule

Actual `main` is always checked first. If actual main differs from the persisted execution snapshot or roadmap state cannot be reconciled with the durable decision/ledger record, implementation fails closed. The Architect must persist the reconciliation before any implementation resumes.

## Permission rule

Roadmap membership, Work Item status, GitHub issues, PRs, prior handoffs, and chat designations never authorize implementation. Only a current repository-local authorization with `status: active` and `authorized: true`, inherited by the implementation branch from `main`, does.

## Historical integrity

Accepted historical delivery facts remain true even if a later mainline regresses or omits their artifacts. Such an omission is a mainline-integrity defect. The remedy is explicit restoration and reconciliation, not historical rewriting.

## Fresh-session rule

A new Architect or implementation agent must be able to clone `main` and determine mission, architecture, roadmap, current execution state, accepted history, evidence state, and next action without access to any prior conversation.
