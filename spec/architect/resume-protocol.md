# ADCOS Resume Protocol

**ACTIVE — Persistent Governance Authority**

A brand-new Architect or implementation agent must resume from the repository alone. Conversation history is never an authority and never a required input.

## Deterministic resume procedure

1. Read `README.md`, then `spec/mission.md`.
2. Read the frozen architecture and lock: `spec/architecture.md`, `spec/architecture-lock.md`.
3. Read the frozen Work Item contract and dependency graph: `spec/work-items.md`, `spec/dependency-graph.md`.
4. Read `spec/architect/roadmap.yaml`. This is the **sole canonical program roadmap**. Record its program state and current gate.
5. Read `spec/architect/current-state.md` and `spec/architect/execution-state.yaml`.
6. Read `spec/architect/authority-order.md` and apply its precedence rules.
7. Verify the actual `main` commit SHA against the repository snapshot. If they differ, treat the state as stale and STOP unless the repository itself contains an explicit reconciliation decision covering the new mainline.
8. Read the relevant durable decision records and `spec/architect/execution-ledger.yaml` for lifecycle provenance.
9. If implementation is active, read the single active authorization in `spec/architect/authorizations/` and its repository-local handoff.
10. Verify every hard dependency against the ledger's accepted-merged state.
11. Continue only from the exact repository-local state declared by roadmap + execution state + authorization.

## Fail-closed conditions

STOP implementation when any of the following is true:

- `roadmap.yaml` says blocked or has no active implementation gate;
- actual `main` differs from the persisted execution snapshot without an explicit reconciliation;
- more than one active implementation authorization exists;
- an active authorization is absent, malformed, not inherited from `main`, or its baseline does not match the reconciled mainline;
- a required hard dependency is not accepted-merged;
- a Work Item contract conflicts with the frozen registry or dependency graph;
- a proposed change would alter frozen architecture/protocol semantics without an accepted ACR;
- a required fact exists only in chat, memory, an issue, or a PR conversation and is not persisted in the repository.

## Implementation rule

An implementation agent may implement exactly one Work Item, only under a repository-local active authorization, from its exact baseline, with no `spec/architect/` changes. The agent opens one implementation PR and stops for Architect review. The Architect is the sole review/acceptance/merge authority.

## Review rule

Acceptance is durable only when the Architect persists the exact reviewed SHA, verdict, evidence disposition, and merge SHA into the repository. CI success does not substitute for acceptance.

## Recovery rule

When accepted implementation artifacts are missing from `main`, do not infer that they were never accepted. Treat the condition as mainline integrity debt. Recover only from repository Git history and accepted delivery evidence, verify exact scope/provenance, and persist the reconciliation. Never import unrelated later ancestry.

## Source-of-truth rule

`spec/architect/roadmap.yaml` controls program order. `spec/architect/execution-ledger.yaml` controls lifecycle history. `spec/architect/execution-state.yaml` controls current execution state. `spec/architect/authorizations/` controls permission. Frozen specification files control contracts and architecture. Everything else is subordinate.

## Current checkpoint

At the 2026-09-05 audit, actual `main` is `a7d913385f866df6da890093c26539ad876f3ee4`, while the last persisted snapshot was `bb29c11c8bba6c9db5b87f85b1d62faad0bf7825`. `DEC-0080` records the mismatch and freezes implementation. The next permitted program gate is `R0_MAINLINE_RESTORATION`.
