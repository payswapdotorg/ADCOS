# ACR-013: Autonomous Post-Snapshot Work Item Governance

## Status
ACCEPTED

## Motivating requirement
The ADCOS operating model requires the sole Architect to advance the repository through the authoritative roadmap without requiring user prompting for routine governance sequencing. W054, W055, and W056 already use gate-specific Architect contracts and authorization records beyond the original frozen Work Item snapshot.

## Proposed change
Formalize the existing post-snapshot execution pattern:

- `spec/work-items.md` remains the frozen architectural Work Item baseline.
- Later roadmap-gate Work Items are canonicalized by `spec/architect/work-items/WORK-NNN.md`.
- Their hard dependencies and ordering are recorded in a gate-specific dependency overlay under `spec/architect/`.
- A Work Item remains unauthorized until its contract, dependency overlay, scope, verification requirements, and acceptance gate are durable and mutually consistent.
- The sole Architect may issue the next repository-local authorization autonomously once the preceding gate is accepted and all readiness predicates are satisfied.
- Exactly one implementation authorization remains active.

This does not change any protocol or product semantic. It changes only the representation and execution of post-snapshot governance work.

## Mission consistency
This directly supports the immutable mission and the Stripe-of-connectivity program objective by removing a human prompting dependency from the governance loop while preserving single authority, evidence discipline, access-technology neutrality, and fail-closed execution.

## Affected architecture sections and locks
- `spec/work-items.md` registration/execution interpretation
- `spec/dependency-graph.md` relationship to later gate-specific overlays
- `spec/architect/roadmap.yaml` execution representation
- `LOCK-007`, `LOCK-008`, `LOCK-016`, `LOCK-017`, `LOCK-022`, `LOCK-023`, `LOCK-024`

No protocol semantic or wire-schema rule changes.

## Compatibility analysis
No wire-format, persisted-domain, session, federation, or deployment compatibility impact. Existing Work Items retain their historical identity. Gate-specific records are additive governance projections and do not replace or rewrite frozen architecture records.

## Work-item and dependency impact
- R6 Work Item: WORK-057
- Gate-specific dependency overlay: `spec/architect/dependency-overlays/R6-W057.yaml`
- Hard dependencies: WORK-015, WORK-016, WORK-026, WORK-029, WORK-039, WORK-044, WORK-045, WORK-046, WORK-047, WORK-050, WORK-051, WORK-052, WORK-053, WORK-055, WORK-056
- WORK-048 is explicitly not restored and is not a hard dependency.
- WORK-040 remains an independent physical-evidence track.

## Migration / rollback
No migration is required. If the governance representation proves unsound, future governance may supersede this ACR without altering historical decisions or product state. No implementation artifact depends on a new protocol semantic introduced here.

## Architect decision
ACCEPTED by the sole Architect on 2026-09-06 as a governance clarification and formalization of the already-used post-snapshot execution pattern. It authorizes repository-local autonomous sequencing; it does not authorize implementation by itself.

## Resulting architecture version
UNCHANGED — Architecture Version 1.0.
Protocol Version 1.0 unchanged.

## Supersession
This ACR supersedes the narrower registration interpretation in ACR-012 that required WORK-057 to be inserted into the original 52-item frozen snapshot before R6 could execute. ACR-012 remains historical and must not be rewritten; its execution interpretation is superseded by this accepted governance clarification.
