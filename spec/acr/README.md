# ADCOS Architecture Change Requests

## Status

**ACTIVE — Change-Control Records Location**

Architecture Change Requests (ACRs) are recorded in this directory as:

```text
spec/acr/ACR-NNN-<short-title>.md
```

with sequential zero-padded numbering starting at `ACR-001`.

The ACR process, its eight required elements, and the record template are defined in `spec/change-control.md`. A normal implementation PR is never allowed to silently become an architecture change.

Current ACRs:

- `ACR-001-work-014-dependency-correction.md` — resolves the historical WORK-014 / WORK-017 dependency ambiguity; WORK-014 does not depend on WORK-017.
- `ACR-002-roadmap-readiness-and-dependency-reconciliation.md` — reconciles W008/W007 and W021/W019 DAG omissions and establishes separate DAG/execution/evidence readiness semantics.
- `ACR-003-w032-adapter-conformance-dependency.md` — reconciles the W032 declaration of W016 as a hard dependency with the missing frozen DAG edge `W016 → W032`.

Frozen specification changes require an accepted ACR and synchronized updates to the affected frozen documents before implementation proceeds.
