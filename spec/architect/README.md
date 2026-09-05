# ADCOS Persistent Architect Package

## Status

**ACTIVE — Persistent Governance Authority**

The repository is the persistent Architect. A brand-new Architect or implementation agent must be able to clone `main`, read this package, and reconstruct ADCOS without access to any prior conversation.

## Canonical authority model

- `spec/mission.md` — permanent Mission Authority.
- `spec/architecture.md` — frozen Architecture Version 1.0.
- `spec/architecture-lock.md` — frozen architecture constraints.
- `spec/work-items.md` — frozen Work Item contracts.
- `spec/dependency-graph.md` — frozen dependency authority.
- `spec/architect/roadmap.yaml` — **sole canonical, frozen execution/program roadmap**.
- `spec/architect/roadmap.md` — human-readable projection only; never an independent authority.
- `spec/architect/decisions/` — durable Architect decisions.
- `spec/architect/execution-ledger.yaml` — authoritative lifecycle and reconciliation history.
- `spec/architect/execution-state.yaml` — authoritative current execution snapshot.
- `spec/architect/authorizations/` — sole implementation-permission source.
- `spec/architect/evidence-obligations.yaml` — durable external-evidence state.
- `spec/architect/resume-protocol.md` — deterministic fresh-session procedure.

## Non-negotiable source-of-truth rules

1. **Chat is not authority.** A chat message, prior prompt, memory, handoff, or model recollection has zero authority unless its consequence is persisted in this repository by the Architect.
2. **Roadmap authority is singular.** `roadmap.yaml` is the only roadmap. `roadmap.md`, issue prose, PR prose, external roadmaps, and conversation plans cannot override it.
3. **Execution permission is singular.** Only an active repository-local authorization permits implementation. The roadmap never authorizes implementation.
4. **History is immutable.** Old decisions, accepted-delivery facts, accidental commits, and reconciliations remain in Git history. They are superseded by durable records, never silently rewritten.
5. **Mismatch fails closed.** If actual `main` differs from the persisted execution snapshot, or authority projections disagree, implementation stops until the Architect persists an explicit reconciliation.
6. **Fresh-clone sufficiency.** The next LLM must not need this conversation to know what ADCOS is, what is accepted, what is blocked, what may be implemented, or what comes next.
7. **Evidence classes stay separate.** SOFTWARE evidence never satisfies PHYSICAL evidence.
8. **Single Architect.** The Architect is the sole review/acceptance/merge authority; a separate reviewer is not required.

## Current canonical state

At the repository audit on 2026-09-05, actual `main` is `a7d913385f866df6da890093c26539ad876f3ee4`. The prior persisted snapshot is `bb29c11c8bba6c9db5b87f85b1d62faad0bf7825`. This mismatch is intentionally represented as a blocking integrity condition under `DEC-0080`.

The first program gate is therefore `R0_MAINLINE_RESTORATION` in `roadmap.yaml`. No Work Item is currently authorized.

## Fresh-session reading order

Read, in order:

1. `spec/mission.md`
2. `spec/architecture.md`
3. `spec/architecture-lock.md`
4. `spec/work-items.md`
5. `spec/dependency-graph.md`
6. `spec/architect/roadmap.yaml`
7. `spec/architect/current-state.md`
8. `spec/architect/authority-order.md`
9. `spec/architect/execution-state.yaml`
10. `spec/architect/execution-ledger.yaml`
11. open/accepted decision records referenced by the current state
12. the active authorization, only if the roadmap/state say implementation is active
13. `spec/architect/resume-protocol.md`

A fresh session must verify the actual `main` SHA before acting. A blocked roadmap/state means STOP.
