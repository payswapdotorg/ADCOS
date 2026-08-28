# ACR-003: W032 Adapter Conformance Dependency Reconciliation

## Status
ACCEPTED

## Proposed change

Reconcile a known inconsistency between the frozen Work Item declaration and the frozen dependency DAG for WORK-032.

`spec/work-items.md` declares WORK-032 (Conformance Suite) dependencies:

```text
WORK-003, WORK-004, WORK-005, WORK-007,
WORK-011, WORK-012, WORK-015, WORK-017, WORK-016
```

The frozen DAG already contains every declared edge except:

```text
WORK-016 → WORK-032
```

WORK-016 is the canonical Adapter SDK/runtime contract. WORK-032 explicitly exists to build protocol/adapter conformance tests and states that adapters must self-test against stable contracts. Therefore the W032 declaration is the authoritative dependency intent; the omission in the DAG is a documentation/ordering inconsistency.

The accepted correction is to add exactly:

```text
WORK-016 → WORK-032
```

to `spec/dependency-graph.md`.

No Work Item dependency is added to `spec/work-items.md`, because the dependency is already declared there. No runtime or protocol semantics change.

Alternatives considered:

- Leave the advisory unresolved. Rejected because the frozen backlog and frozen DAG would remain contradictory.
- Remove WORK-016 from WORK-032's declared dependencies. Rejected because W032 explicitly tests adapters against the stable Adapter SDK/runtime contract.
- Add hidden implementation coupling instead of a DAG edge. Rejected by the frozen dependency-graph rules.
- Reclassify W016 as merely optional. Rejected because adapter conformance is an explicit W032 acceptance concern, not an optional implementation detail.

## Affected architecture sections and locks

- `spec/architecture.md` sections: no semantic protocol/runtime architecture sections changed.
- `spec/architecture-lock.md` locks: no LOCK-001 … LOCK-025 semantics changed.
- Frozen ordering artifact affected: `spec/dependency-graph.md`.
- Frozen backlog: `spec/work-items.md` is authoritative as-is and is not rewritten.
- Process authority: no workflow semantics change.

## Compatibility analysis

- **Wire compatibility:** none.
- **Persisted state:** none.
- **Live sessions:** none.
- **Federation relationships:** none.
- **Deployments:** none.
- **Mixed-version operation:** none.
- **Implementation compatibility:** no runtime contract changes. The DAG is synchronized to an already-declared Work Item dependency.
- **Execution ordering:** W032 cannot be treated as dependency-complete until W016 is Architect-accepted, matching the existing W032 declaration.

## Work-item and dependency impact

Affected Work Items:

- `WORK-032` — DAG synchronized to its existing frozen declaration that WORK-016 is a hard dependency.
- `WORK-016` — no semantic change; its existing Adapter SDK/runtime authority becomes an explicit predecessor of W032 in the DAG.
- `WORK-033` and later downstream Work Items — readiness is recalculated transitively through the existing W032 dependency; no new direct dependencies are introduced.

Dependency graph recalculation:

```text
Added edge:
W016 → W032

Result:
- DAG remains acyclic.
- W032's DAG now exactly matches its frozen dependency declaration.
- W032 remains Phase 6.
- No critical-path inversion is introduced.
- No existing accepted dependency is removed or weakened.
```

## Migration / rollback plan

1. Add `W016 → W032` to the frozen dependency DAG.
2. Re-run specification consistency checks and DAG validation.
3. Recalculate W032 readiness and all downstream readiness according to the synchronized DAG.
4. Do not start W032 until W016 and every other frozen W032 dependency is Architect-accepted.
5. If later evidence shows W016 is not actually required for W032, open a new ACR rather than editing the graph ad hoc.
6. No runtime migration or rollback is required because this is a dependency-document consistency reconciliation.

## Architect decision

**ACCEPTED — 2026-08-28.**

The Architect accepts ACR-003 because WORK-016 is already an explicit hard dependency in the frozen WORK-032 declaration and is semantically necessary for adapter conformance. Adding the missing DAG edge reconciles the frozen ordering artifacts without introducing a new runtime or protocol dependency.

This decision supersedes the previously registered OAQ-001.

The frozen DAG is authorized to carry:

```text
W016 → W032
```

W032 execution readiness must be computed from the synchronized graph. No other dependency edges are changed by this ACR.

## Resulting architecture version

Unchanged. This is a dependency/document consistency reconciliation matching the precedent established by ACR-002; no core architecture semantics or protocol meaning change.
