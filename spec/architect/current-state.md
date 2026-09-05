# ADCOS Current State

**READY — R1 governance reconciliation complete; R2 system-composition Work Item pending.**

## Repository

- Repository: `github.com/payswapdotorg/ADCOS`
- Canonical live `main`: `09d77dae84b430ad4a6bb22a6f01c2b7d8533cdd`
- Lifecycle ledger snapshot: `7fb47bb312708d06f3b3c1ba0496104362c7d135` (R0 restoration checkpoint)
- Roadmap: `spec/architect/roadmap.yaml` — **FROZEN, Version 1.1, sole program-roadmap authority**
- Architecture: `1.0` frozen
- Protocol: `1.0`

## Governance state

- R0: `COMPLETED` — PR #157
- R1: `COMPLETED` — DEC-0083
- Governing decisions: `DEC-0081`, `DEC-0082`, `DEC-0083`
- Active Work Item: none
- Active authorization: none
- Active implementation authorization count: zero
- Architect: sole review/acceptance/merge authority

## R0 result

The accepted W044-W049 implementation packages, deterministic selftests, evidence surfaces, historical handoffs, and required CI invocation wiring are restored on the canonical mainline. The clean restoration was isolated from unrelated historical ancestry and changed no frozen architecture/protocol semantics.

## R1 result

R1 is complete under `DEC-0083`. W044-W049 lifecycle records now match their durable accepted delivery history; W050 is accepted on its exact final delivery head with the permanent 76/76 SOFTWARE battery; historical records remain preserved; no implementation authorization is active.

The next governed gate is R2 system composition conformance. It requires a fresh repository-local Work Item and authorization.

## Independent physical evidence

W040 remains `in-review`, unaccepted, and independent. Its physical evidence obligations remain open and W040-owned. Software evidence cannot promote these obligations to PASS.

## Source of truth

A clean clone of `main` is sufficient to reconstruct ADCOS. Chat history, model memory, prompts, issue prose, PR discussion, external roadmaps, and stale handoff documents have zero authority.

Authority chain:

`mission → frozen architecture/locks → frozen Work Item contract + dependency graph → frozen roadmap.yaml → durable decisions + execution ledger/state → active authorization → implementation/evidence`

The roadmap controls program order. The ledger controls lifecycle history. Execution state controls current execution. Repository-local authorizations control implementation permission.
