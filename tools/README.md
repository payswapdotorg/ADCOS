# ADCOS Specification Tooling

## spec_check.py

Deterministic, offline consistency checks for the ADCOS specification repository. Introduced by WORK-001.

### Invocation

```bash
python3 tools/spec_check.py
```

Requirements: Python 3.8+ standard library only. No network access, no external services, no third-party packages, no environment-specific absolute paths. The command may be run from any working directory; paths resolve relative to the repository root.

Exit codes:

- `0` — all blocking checks passed (advisories may be present);
- `1` — at least one blocking check failed.

CI runs the same command on every push and pull request (`.github/workflows/spec-check.yml`), followed by the checker negative tests (`tools/spec_check_selftest.py`).

### Check catalog

| ID | Blocking | Verifies |
|---|---|---|
| `FILES-01` | yes | The four authoritative specification documents exist; `spec/prompts/` exists with correctly named `WORK-XXX.md` handoff prompts. |
| `FILES-02` | yes | Governance artifacts exist (governance/change-control/workflow documents, schema and ACR locations, tooling) and the CI workflow invokes the checker. |
| `MARK-01` | yes | Every registered document carries its exact H1 title and a Status section identifying its role (frozen architecture vs. process authority). |
| `MARK-02` | yes | The four architecture-authority documents carry `FROZEN` status markers. |
| `VERS-01` | yes | Version-kind distinction and the single architecture-version declaration site. **Declaration vs reference**: a *declaration* is the Architecture Version statement in a document's Status section or an explicit declaration field (line-leading `Architecture Version: X.Y`); declarations are legal only in the Status section of `spec/architecture.md`, which must carry exactly one. Every Markdown document's Status section and declaration fields are scanned; no other document may declare. Ordinary prose references (e.g. "written against Architecture Version 1.0") are unrestricted. Also verifies no frozen document's status section declares a Protocol Version and that `spec/governance.md` defines all four version kinds with the non-conflation rule. |
| `BACKLOG-01` | yes | Work Item backlog integrity: unique, gap-free `WORK-001..WORK-040`, with `Objective:` and `Dependencies:` lines per item. |
| `DEPS-01` | yes | All dependency references (declared dependencies, DAG nodes and edges, execution-phase members, critical-path members) resolve to known Work Item IDs. |
| `DEPS-02` | yes | The dependency graph (DAG edges ∪ declared dependencies) is acyclic. |
| `DEPS-03` | yes | Execution phases cover every Work Item, are numbered sequentially, and every DAG edge respects phase ordering and intra-phase ordering; the critical path never places an item before its dependency. |
| `ADV-01` | no (advisory) | Declared dependencies not reflected in the DAG, and DAG edges not declared in `spec/work-items.md`, are reported. Advisories do not change the exit code; they are specification-consistency findings for the Architect to resolve (directly or via an ACR). |

### Determinism

Output is fully deterministic: no timestamps, no network, sorted iteration everywhere, identical output for identical repository content. Re-running the tool on the same tree produces byte-identical results.

### Scope

This tool validates repository structure and specification mechanics only. It is not a protocol semantic compiler and does not attempt to validate the meaning of prose in the frozen documents.

## spec_check_selftest.py

Deterministic, offline negative and positive tests for the checker itself, introduced by WORK-001 correction cycles 2 and 3 (Architect reviews of PR #1). Each case copies the specification tree into a temporary directory, applies exactly one change, runs the checker, and asserts the expected exit code and failing check. No repository file is ever modified; temporary directories are always removed.

### Invocation

```bash
python3 tools/spec_check_selftest.py
```

Exit codes: `0` all cases pass; `1` at least one case fails.

### Case catalog

Negative cases (injected violations must fail):

| Case | Injected violation | Expected failing check |
|---|---|---|
| `missing-frozen-document` | delete `spec/architecture-lock.md` | `FILES-01` |
| `dependency-cycle-injected` | WORK-001 declares dependency on WORK-040 | `DEPS-02` |
| `unknown-work-item-reference` | dependency points to WORK-099 | `DEPS-01` |
| `protocol-version-in-architecture-status` | Protocol Version declared in `spec/architecture.md` Status | `VERS-01` |
| `architecture-version-declared-in-process-doc` | architecture-version **declaration** injected into `spec/workflow.md` Status (the declaration form from the correction cycle 2 review) | `VERS-01` |
| `architecture-version-declared-in-status-of-new-doc` | new prompt document declaring the architecture version in its Status section | `VERS-01` |
| `architecture-version-declaration-field-in-new-doc` | new document with an explicit `Architecture Version: 1.0` declaration field | `VERS-01` |
| `frozen-marker-removed` | FROZEN marker replaced with DRAFT | `MARK-02` |
| `execution-phase-order-violation` | W001 appended to Phase 8 sequence | `DEPS-03` |

Positive cases (legitimate content must pass — proving the checker distinguishes declarations from references):

| Case | Added content | Expected outcome |
|---|---|---|
| `baseline-unmutated-tree` | none (control) | exit 0 |
| `architecture-version-reference-in-process-doc-body` | prose reference in `spec/governance.md` body: “written against Architecture Version 1.0” | exit 0 |
| `architecture-version-reference-in-readme` | prose reference sentence in `README.md` | exit 0 |
| `architecture-version-reference-in-new-prompt` | new `spec/prompts/WORK-002.md` referencing the architecture version in ordinary prose | exit 0 |

Mutation anchors are asserted to match exactly once; if frozen text drifts, the self-test fails loudly and must be updated deliberately. Output is fully deterministic (temporary paths are never printed).
