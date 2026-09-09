# ADCOS Architecture History Archive

**ACTIVE — Historical Evidence (superseded, never rewritten)**

This directory preserves superseded architecture snapshots verbatim. Files
here are historical evidence only: they are authoritative for nothing
forward, but no historical acceptance record, verdict, or snapshot content
may ever be edited or deleted.

## Supersedence chain

| Snapshot | Status | Superseded by | Decision |
|---|---|---|---|
| `architecture-1.0.md` | SUPERSEDED (preserved verbatim) | `spec/architecture.md` (Architecture 1.1) | ACR-014 / DEC-0098 |
| `architecture-lock-1.0.md` | SUPERSEDED (preserved verbatim) | `spec/architecture-lock.md` (LOCK-101..LOCK-120) | ACR-014 / DEC-0098 |
| `work-items-1.0.md` | SUPERSEDED (preserved verbatim; the W001–W057 registry) | `spec/work-items.md` (M001–M014 registry) | ACR-014 / DEC-0098 |
| `dependency-graph-1.0.md` | SUPERSEDED (preserved verbatim) | `spec/dependency-graph.md` (1.1 dependency model) | ACR-014 / DEC-0098 |

## Rules

1. Archived files are byte-verbatim copies at their supersession point.
2. Lifecycle history for the W-item registry lives in
   `spec/architect/execution-ledger.yaml` and is the sole delivery-history
   authority; the archived registry is a content snapshot, not a ledger.
3. Any future architecture promotion (ACR-NNN) archives the then-current
   snapshot here under the same rules before the successor becomes
   normative.
