# ADCOS Current State

**BLOCKED — R0 complete; R1 governance reconciliation remains open.**

## Repository

- Repository: `github.com/pectoraux/ADCOS`
- Canonical live `main`: `09d77dae84b430ad4a6bb22a6f01c2b7d8533cdd`
- Lifecycle ledger snapshot: `7fb47bb312708d06f3b3c1ba0496104362c7d135` (R0 restoration checkpoint)
- Roadmap: `spec/architect/roadmap.yaml` — **FROZEN, Version 1.1, sole program-roadmap authority**
- Architecture: `1.0` frozen
- Protocol: `1.0`

## Governance state

- R0: `COMPLETED` — PR #157
- R1: `BLOCKED`
- Governing decisions: `DEC-0081`, `DEC-0082`
- Active Work Item: none
- Active authorization: none
- Active implementation authorization count: zero
- Architect: sole review/acceptance/merge authority

## R0 result

The accepted W044-W049 implementation packages, deterministic selftests, evidence surfaces, historical handoffs, and required CI invocation wiring are restored on the canonical mainline. The clean restoration was isolated from unrelated historical ancestry and changed no frozen architecture/protocol semantics.

## R1 remaining blockers

### W044-W049 lifecycle reconciliation

The authoritative execution ledger still contains the earlier registered-only W044-W049 lifecycle representation even though durable repository history records their accepted reviewed heads and merges. This must be reconciled explicitly, preserving every previous reconciliation and every historical field that is not deliberately superseded.

### W050 acceptance provenance

W050 implementation-stage artifacts and its permanent deterministic battery are present. However, the current authoritative decision registry and execution ledger do not contain a discrete corroborated Work Item acceptance decision. DEC-0082 therefore requires fail-closed treatment: W050 is implementation-present but acceptance-unresolved until the repository evidence is sufficient.

No implementation authorization may be issued while either condition remains unresolved.

## Independent physical evidence

W040 remains `in-review`, unaccepted, and independent. Its physical evidence obligations remain open and W040-owned. Software evidence cannot promote these obligations to PASS.

## Source of truth

A clean clone of `main` is sufficient to reconstruct ADCOS. Chat history, model memory, prompts, issue prose, PR discussion, external roadmaps, and stale handoff documents have zero authority.

Authority chain:

`mission → frozen architecture/locks → frozen Work Item contract + dependency graph → frozen roadmap.yaml → durable decisions + execution ledger/state → active authorization → implementation/evidence`

The roadmap controls program order. The ledger controls lifecycle history. Execution state controls current execution. Repository-local authorizations control implementation permission.
