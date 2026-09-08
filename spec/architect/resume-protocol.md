# ADCOS Resume Protocol

**ACTIVE — Persistent Governance Authority**

A brand-new Architect, Tech Lead, worker, or implementation agent must resume from the repository and live GitHub state alone. Conversation history is never an authority and never a required input.

## Deterministic resume procedure

1. Read `README.md` and `AGENTS.md`.
2. Identify your role. If you are the Tech Lead, read `docs/tech-lead/ADCOS-TECH-LEAD-HANDOFF.md` and `docs/tech-lead/worker-model.md` before dispatching work.
3. Read `spec/mission.md`.
4. Read the current frozen architecture and lock: `spec/architecture.md`, `spec/architecture-lock.md`.
5. Read `spec/work-items.md` and `spec/dependency-graph.md`.
6. Read `spec/architect/roadmap.yaml`; it is the sole canonical program roadmap. Record the program state and next gate.
7. Read `spec/architect/current-state.md` and `spec/architect/execution-state.yaml`.
8. Read `spec/architect/authority-order.md` and `spec/architect/governance-autonomy.md`.
9. Verify the actual `main` commit SHA against the persisted execution snapshot. If they differ, inspect the intervening repository commits and reconcile the snapshot through the repository-local governance process before implementation.
10. Read relevant accepted decisions and `spec/architect/execution-ledger.yaml`.
11. If implementation is active, read exactly the single active authorization and its gate-specific Work Item/overlay.
12. Verify every hard dependency against accepted history.
13. Inspect the actual source tree and current diff before trusting any implementation report.
14. Continue only from the exact repository-local state declared by the authoritative artifacts.

## Current checkpoint

The latest reconciled software mainline is `88a73720d8ff28e95728a03e13db631ffdf9688f`.

- R6 Provider Onboarding & Federation is complete under `DEC-0097`.
- `WORK-057-CORE-001` is closed.
- No implementation authorization is active.
- R7 Universal Connectivity Commerce is the next unlocked software gate but is not activated.
- R4/W040 remains an independent physical-validation track and is not replaced by the software roadmap.
- W048 remains accepted-not-restored and MUST NOT be recreated, mocked, or substituted implicitly.
- Architecture 1.0 and Protocol 1.0 remain the current frozen authority until a formal accepted ACR promotes a successor architecture.

## Fail-closed conditions

STOP implementation when:

- an active Work Item or authorization is required but absent;
- actual `main` differs from persisted state and no repository reconciliation exists;
- more than one implementation authorization exists;
- a required hard dependency is not accepted-merged;
- a Work Item conflicts with frozen architecture/registry/dependency semantics;
- a change would alter frozen architecture/protocol semantics without an accepted ACR;
- required facts exist only in chat, memory, issues, PR prose, or agent reports;
- worker outputs cannot be independently verified from the repository;
- a proposed implementation would create a second source of truth or authority.

## Implementation rule

A normal implementation worker may implement exactly one authorized Work Item from its exact baseline. Implementation PRs MUST NOT modify `spec/architect/` unless the repository-local governance model explicitly authorizes a governance transition. The Tech Lead coordinates workers but does not invent permission.

## Worker model

The Tech Lead may dispatch at most 3 direct workers. Each direct worker may dispatch at most 3 subagents. Maximum active descendant workers: 9.

Parallelism is permitted only for dependency-independent scopes. The Tech Lead owns integration and must independently verify worker claims.

## Architecture 1.1 transition rule

`spec/architecture-1.1-proposed.md` and related `*-1.1-proposed.md` artifacts are proposals until an accepted Architecture Change Request promotes them. Do not implement against them as if they were already frozen.

When the 1.1 transition is accepted, the successor frozen documents must be updated together and the old 1.0 documents archived as historical evidence. No historical acceptance record may be rewritten.

## Acceptance rule

Acceptance is durable only when the sole Architect persists the exact reviewed SHA, verdict, evidence disposition, and merge SHA. CI success does not substitute for architecture acceptance.

## Recovery rule

When accepted implementation artifacts are missing from `main`, recover them from Git history and accepted delivery evidence. Never rewrite historical acceptance facts or import unrelated ancestry.

## Source-of-truth rule

`spec/mission.md` -> frozen architecture/locks -> dependency/work-item contracts -> `spec/architect/roadmap.yaml` -> accepted decisions/ledger -> execution state -> active authorization -> implementation evidence.

Narrative documents, issues, PR prose and conversation history cannot override this chain.

## Fresh-session guarantee

A clean clone plus live GitHub access must be sufficient to determine:

- what ADCOS is;
- what architecture is currently authoritative;
- what the next roadmap gate is;
- whether implementation is authorized;
- what exact Work Item may be implemented;
- how workers may be dispatched;
- what evidence is required for acceptance;
- what historical constraints must not be disturbed.
