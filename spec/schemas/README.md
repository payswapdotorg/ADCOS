# ADCOS Machine-Readable Schemas

## Status

**ACTIVE — Canonical Schema Location**

This directory is the canonical location for ADCOS machine-readable protocol schemas and registries, established by WORK-001 (`spec/work-items.md`, Phase 0).

## What lives here

```text
spec/schemas/
  registries/<name>.json      machine-readable registries (technology IDs, capability IDs, ...)
  <name>.schema.json          JSON Schema definitions for protocol objects
```

## Conventions

- Files are UTF-8 JSON, one schema or registry per file.
- Every file declares a top-level `schema_version` string (the file's own version, `MAJOR.MINOR`).
- Every file declares the `architecture_version` it is written against.
- Protocol-level registries additionally declare the `protocol_version` they belong to.
- The four version kinds are distinct and are never conflated (`spec/governance.md` §3).
- Registries are additive: appending new entries is a minor `schema_version` bump; removing, renaming, or reinterpreting entries is a breaking change (major bump) and requires an Architecture Change Request (`spec/change-control.md`).
- Unknown future entries must be handled safely by conformant implementations (`spec/architecture.md` §2 P4, §8).

## Current contents

None. WORK-001 deliberately defines **no protocol vocabulary, identifiers, or wire schemas**; it establishes only this location and these conventions.

The first machine-readable registries are introduced by **WORK-002 — Core protocol vocabulary and registry model**, and the versioned envelope schemas by **WORK-003 — Versioned protocol envelope and serialization**. WORK-002 must treat this directory as its unambiguous starting point.
