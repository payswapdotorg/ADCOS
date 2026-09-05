# ADCOS Current State

**READY — R1 governance reconciliation complete; R2 system-composition Work Item pending.**

## Repository

- Repository: `github.com/payswapdotorg/ADCOS`
- Canonical reconciled checkpoint: `338af793923e1267ff3523de4310be273d75a2cd`
- R0 restoration: `7fb47bb312708d06f3b3c1ba0496104362c7d135`
- Roadmap: `spec/architect/roadmap.yaml` — **FROZEN, Version 1.2, sole program-roadmap authority**
- Architecture: `1.0` frozen
- Protocol: `1.0`

## Governance state

- R0: `COMPLETED` — PR #157
- R1: `COMPLETED` — DEC-0083 / LEDGER-RECON-024
- R2: `READY`
- Governing decisions: `DEC-0081`, `DEC-0082`, `DEC-0083`
- Active Work Item: none
- Active authorization: none
- Active implementation authorization count: zero
- Architect: sole review/acceptance/merge authority

## R0 result

The accepted W044-W049 implementation packages, deterministic selftests, evidence surfaces, historical handoffs, and required CI invocation wiring are restored on the canonical mainline. The clean restoration was isolated from unrelated historical ancestry and changed no frozen architecture/protocol semantics.

## R1 result

R1 is complete under `DEC-0083` and `LEDGER-RECON-024`. W044-W049 lifecycle records now match their durable accepted delivery history; W050 is accepted on its exact final delivery head with the permanent 76/76 SOFTWARE battery; historical records remain preserved; the lifecycle ledger snapshot is reconciled to the `338af793` canonical checkpoint; no implementation authorization is active.

The next governed gate is R2 system composition conformance. It requires a fresh repository-local Work Item and exactly one implementation authorization before implementation begins.

## R2 product direction

R2 is not a new monolithic connectivity subsystem. It is composition proof across the already-accepted authorities:

`external application intent → Developer API → policy/eligibility → offer/reservation/lease → candidate selection → NetworkPath validation → containment → session → delivered usage → BILLABLE_FINAL → allocation → external payment reference/reconciliation → canonical API/webhook observation`

The implementation must preserve the frozen single-authority model and must prove that payment, reservation, discovery, capability declaration, client state, or API/webhook observation cannot become unauthorized connectivity or canonical authority.

## Independent physical evidence

W040 remains `in-review`, unaccepted, and independent. Its physical evidence obligations remain open and W040-owned. Software evidence cannot promote these obligations to PASS.

## Source of truth

A clean clone of the new canonical `main` is sufficient to reconstruct ADCOS. Chat history, model memory, prompts, issue prose, PR discussion, external roadmaps, and stale handoff documents have zero authority.

Authority chain:

`mission → frozen architecture/locks → frozen Work Item contract + dependency graph → frozen roadmap.yaml → durable decisions + execution ledger/state → active authorization → implementation/evidence`

The roadmap controls program order. The ledger controls lifecycle history. Execution state controls current execution. Repository-local authorizations control implementation permission.
