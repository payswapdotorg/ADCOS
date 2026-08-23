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

CI runs the same command on every push and pull request (`.github/workflows/spec-check.yml`).

### Check catalog

| ID | Blocking | Verifies |
|---|---|---|
| `FILES-01` | yes | The four authoritative specification documents exist; `spec/prompts/` exists with correctly named `WORK-XXX.md` handoff prompts. |
| `FILES-02` | yes | Governance artifacts exist (governance/change-control/workflow documents, schema and ACR locations, tooling) and the CI workflow invokes the checker. |
| `MARK-01` | yes | Every registered document carries its exact H1 title and a Status section identifying its role (frozen architecture vs. process authority). |
| `MARK-02` | yes | The four architecture-authority documents carry `FROZEN` status markers. |
| `VERS-01` | yes | Architecture/protocol/schema/implementation version kinds are distinct: the Architecture Version is declared exactly once (in `spec/architecture.md`), no frozen status section declares a Protocol Version, and `spec/governance.md` defines all four version kinds with the non-conflation rule. |
| `BACKLOG-01` | yes | Work Item backlog integrity: unique, gap-free `WORK-001..WORK-040`, with `Objective:` and `Dependencies:` lines per item. |
| `DEPS-01` | yes | All dependency references (declared dependencies, DAG nodes and edges, execution-phase members, critical-path members) resolve to known Work Item IDs. |
| `DEPS-02` | yes | The dependency graph (DAG edges ∪ declared dependencies) is acyclic. |
| `DEPS-03` | yes | Execution phases cover every Work Item, are numbered sequentially, and every DAG edge respects phase ordering and intra-phase ordering; the critical path never places an item before its dependency. |
| `ADV-01` | no (advisory) | Declared dependencies not reflected in the DAG, and DAG edges not declared in `spec/work-items.md`, are reported. Advisories do not change the exit code; they are specification-consistency findings for the Architect to resolve (directly or via an ACR). |

### Determinism

Output is fully deterministic: no timestamps, no network, sorted iteration everywhere, identical output for identical repository content. Re-running the tool on the same tree produces byte-identical results.

### Scope

This tool validates repository structure and specification mechanics only. It is not a protocol semantic compiler and does not attempt to validate the meaning of prose in the frozen documents.
