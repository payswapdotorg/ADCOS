# ADCOS Current State

**READY — R2 W054 accepted; R3 production protocol conformance is next.**

## Repository

- Repository: `github.com/payswapdotorg/ADCOS`
- Canonical reconciled checkpoint: `ba3717fad3cc4a5894ff3fece4768e47e7db584c`
- R0 restoration: `7fb47bb312708d06f3b3c1ba0496104362c7d135`
- Roadmap: `spec/architect/roadmap.yaml` — **FROZEN, Version 1.4, sole program-roadmap authority**
- Architecture: `1.0` frozen
- Protocol: `1.0`

## Governance state

- R0: `COMPLETED` — PR #157
- R1: `COMPLETED` — DEC-0083 / LEDGER-RECON-024
- R2: `COMPLETED` — WORK-054 / DEC-0085
- Governing decisions: `DEC-0081`, `DEC-0082`, `DEC-0083`
- Active Work Item: none
- Active authorization: none
- Active implementation authorization count: zero
- Architect: sole review/acceptance/merge authority

## R0 result

The accepted W044-W049 implementation packages, deterministic selftests, evidence surfaces, historical handoffs, and required CI invocation wiring are restored on the canonical mainline. The clean restoration was isolated from unrelated historical ancestry and changed no frozen architecture/protocol semantics.

## R1 result

R1 is complete under `DEC-0083` and `LEDGER-RECON-024`. W044-W049 lifecycle records now match their durable accepted delivery history; W050 is accepted on its exact final delivery head with the permanent 76/76 SOFTWARE battery; historical records remain preserved; the lifecycle ledger snapshot is reconciled to the `338af793` canonical checkpoint; no implementation authorization is active.

R2 implementation is complete under DEC-0085. W054 established the composition/conformance seam across the accepted authorities without creating a second canonical authority.

## R2 product direction

R2 is not a new monolithic connectivity subsystem. It is composition proof across the already-accepted authorities:

`external application intent → Developer API → policy/eligibility → offer/reservation/lease → candidate selection → NetworkPath validation → containment → session → delivered usage → BILLABLE_FINAL → allocation → external payment reference/reconciliation → canonical API/webhook observation`

The implementation must preserve the frozen single-authority model and must prove that payment, reservation, discovery, capability declaration, client state, or API/webhook observation cannot become unauthorized connectivity or canonical authority.

## Next governed gate

R3 is the next product-development gate: production protocol conformance and wire-compatibility proof. It requires a fresh Work Item and exactly one implementation authorization.

## Independent physical evidence

W040 remains `in-review`, unaccepted, and independent. Its physical evidence obligations remain open and W040-owned. Software evidence cannot promote these obligations to PASS.

## Source of truth

A clean clone of the new canonical `main` is sufficient to reconstruct ADCOS. Chat history, model memory, prompts, issue prose, PR discussion, external roadmaps, and stale handoff documents have zero authority.

Authority chain:

`mission → frozen architecture/locks → frozen Work Item contract + dependency graph → frozen roadmap.yaml → durable decisions + execution ledger/state → active authorization → implementation/evidence`

The roadmap controls program order. The ledger controls lifecycle history. Execution state controls current execution. Repository-local authorizations control implementation permission.
