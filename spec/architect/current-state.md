# ADCOS Current State

**BLOCKED — R0 complete; R1 governance reconciliation remains open.**

## Repository

- Repository: `github.com/pectoraux/ADCOS`
- Canonical mainline after R0: `7fb47bb312708d06f3b3c1ba0496104362c7d135`
- Roadmap: `spec/architect/roadmap.yaml` — **FROZEN, Version 1.1, sole program-roadmap authority**
- Architecture: `1.0` frozen
- Protocol: `1.0`

## Governance state

- R0: `COMPLETED` — PR #157
- R1: `BLOCKED`
- Governing corrections: `DEC-0081`, `DEC-0082`
- Active Work Item: none
- Active authorization: none
- Active implementation authorization count: zero
- Architect: sole review/acceptance/merge authority

## R0 result

The accepted W044-W049 implementation packages, deterministic selftests, evidence surfaces, handoffs where historically present, and required CI invocation wiring are restored on the current mainline. The restoration was isolated from unrelated historical ancestry and changed no frozen architecture/protocol semantics or `spec/architect/` governance state.

## R1 remaining blockers

### W044-W049 lifecycle reconciliation

The current execution ledger still carries the pre-restoration registered-only representation for W044-W049 even though durable repository history contains their accepted reviewed heads and merges. Those lifecycle facts must be reconciled explicitly without deleting or rewriting prior records.

### W050 acceptance provenance

W050 implementation-stage artifacts and its permanent deterministic battery are present, but no discrete durable W050 acceptance decision is corroborated in the current authoritative decision registry/execution ledger. `DEC-0082` therefore changes the frozen roadmap to record W050 as `implementation-present_acceptance-unresolved` rather than infer acceptance.

No implementation authorization may be issued until both blockers are resolved.

## Independent physical evidence

W040 remains `in-review`, unaccepted, and independent. Its physical evidence obligations remain open and W040-owned. Software evidence cannot promote these obligations to PASS.

## Source of truth

A clean clone of `main` must be sufficient to reconstruct ADCOS. Chat history, model memory, prompts, issue prose, PR discussion, external roadmaps, and stale handoff documents have zero authority.

Authority chain:

`mission → frozen architecture/locks → frozen Work Item contract + dependency graph → frozen roadmap.yaml → durable decisions + execution ledger/state → active authorization → implementation/evidence`

The roadmap controls program order. The ledger controls lifecycle history. Execution state controls current execution. Repository-local authorizations control implementation permission.
