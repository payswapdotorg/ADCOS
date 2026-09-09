# ADCOS Resume Protocol

**ACTIVE — Persistent Governance Authority**

A brand-new Architect, Tech Lead, worker, or implementation agent must resume from the repository and live GitHub state alone. Conversation history is never an authority and never a required input.

## Deterministic resume procedure

1. Read `README.md` and `AGENTS.md`.
2. Identify your role. If you are the Tech Lead, read `docs/tech-lead/ADCOS-TECH-LEAD-HANDOFF.md` and `docs/tech-lead/worker-model.md` before dispatching work.
3. Read `spec/mission.md`.
4. Read the Architecture 1.1 target package and transition state.
5. Read the preserved Architecture 1.0 architecture/lock only for migration and compatibility context.
6. Read the historical `spec/work-items.md` / `spec/dependency-graph.md`, then the Architecture 1.1 forward Work Item/dependency artifacts.
7. Read `spec/architect/roadmap.yaml`; it is the sole canonical program roadmap. Record the program state and next gate.
8. Read `spec/architect/current-state.md` and `spec/architect/execution-state.yaml`.
9. Read `spec/architect/authority-order.md` and `spec/architect/governance-autonomy.md`.
10. Verify the actual `main` commit SHA against the persisted execution snapshot. If they differ, inspect the intervening repository commits and reconcile the snapshot through the repository-local governance process before implementation.
11. Read relevant accepted decisions and `spec/architect/execution-ledger.yaml`.
12. If implementation is active, read exactly the single active authorization and its gate-specific Work Item/overlay.
13. Verify every hard dependency against accepted history.
14. Inspect the actual source tree and current diff before trusting any implementation report.
15. Continue only from the exact repository-local state declared by the authoritative artifacts.

## Current checkpoint

The latest reconciled software baseline is the pre-activation head
`1e5c55f9916ff964d3bfc0761d04a8d5fd02c41b` (DEC-0100 acceptance head `4168f73`
plus the fresh-session reconciliation repair); the DEC-0101 activation sits
beyond it per the standing reconciliation convention.

- R6 Provider Onboarding & Federation is complete under `DEC-0097`.
- M001 — Architecture 1.1 Freeze is complete under `DEC-0100`: Architecture 1.1
  is the sole normative forward architecture (`spec/architecture.md` FROZEN v1.1,
  LOCK-101..LOCK-120); Architecture 1.0 is preserved historical evidence at
  `spec/history/`; ACR-014 is ACCEPTED.
- `M001-CORE-001` is closed. **R7 — Universal Connectivity Commerce is ACTIVE
  under DEC-0101** as a bounded program authorization: `R7-CORE-001`
  (`spec/architect/authorizations/R7.yaml`) with the R7 charter
  (`spec/architect/work-items/R7-charter.md`) declaring the child work-item
  scopes M002-M014. The current child is **M002 — Connectivity Contract Core**
  (implementing). Per-child acceptance decisions (DEC-0102 onward) are the
  serialization points.
- R4/W040 remains an independent physical-validation track and is not replaced by the software roadmap.
- W048 remains accepted-not-restored and MUST NOT be recreated, mocked, or substituted implicitly.

## Architecture transition rule

Architecture 1.0 is the preserved legacy baseline. It is not the design source for
new ADCOS capabilities.

Architecture 1.1 is the mandatory forward implementation target. Before M001 is
accepted, the Tech Lead may implement only explicitly authorized transition/
migration work. M001 must formally promote the 1.1 architecture/locks and their
successor Work Item/dependency snapshots through the repository ACR process.

After M001 acceptance, the accepted Architecture 1.1 snapshot is the sole
normative architecture for forward implementation; Architecture 1.0 becomes
historical/superseded evidence.

## Fail-closed conditions

STOP implementation when:

- an active Work Item or authorization is required but absent;
- actual `main` differs from persisted state and no repository reconciliation exists;
- more than one implementation authorization exists;
- a required hard dependency is not accepted-merged;
- a Work Item conflicts with the Architecture 1.1 target or accepted successor architecture;
- a change would alter frozen architecture/protocol semantics without the required ACR;
- required facts exist only in chat, memory, issues, PR prose, or agent reports;
- worker outputs cannot be independently verified from the repository;
- a proposed implementation would create a second source of truth or authority;
- a new feature is justified only by Architecture 1.0 semantics rather than the 1.1 target.

## Implementation rule

A normal implementation worker may implement exactly one authorized Work Item from its exact baseline. Implementation PRs MUST NOT modify normative architecture documents unless the repository-local governance model explicitly authorizes a governance transition. The Tech Lead coordinates workers but does not invent permission.

## Worker model

The Tech Lead may dispatch at most 3 direct workers. Each direct worker may dispatch at most 3 subagents. Maximum active descendant workers: 9.

Parallelism is permitted only for dependency-independent scopes. The Tech Lead owns integration and must independently verify worker claims.

## Acceptance rule

Acceptance is durable only when the sole Architect persists the exact reviewed SHA, verdict, evidence disposition, and merge SHA. CI success does not substitute for architecture acceptance.

## Recovery rule

When accepted implementation artifacts are missing from `main`, recover them from Git history and accepted delivery evidence. Never rewrite historical acceptance facts or import unrelated ancestry.

## Source-of-truth rule

`spec/mission.md` -> architecture transition / accepted architecture+locks -> dependency/work-item contracts -> `spec/architect/roadmap.yaml` -> accepted decisions/ledger -> execution state -> active authorization -> implementation evidence.

Narrative documents, issues, PR prose and conversation history cannot override this chain.

## Fresh-session guarantee

A clean clone plus live GitHub access must be sufficient to determine:

- what ADCOS is;
- what Architecture 1.1 means for forward implementation;
- what Architecture 1.0 artifacts are preserved for migration/history;
- what the next roadmap gate is;
- whether implementation is authorized;
- what exact Work Item may be implemented;
- how workers may be dispatched;
- what evidence is required for acceptance;
- what historical constraints must not be disturbed.
