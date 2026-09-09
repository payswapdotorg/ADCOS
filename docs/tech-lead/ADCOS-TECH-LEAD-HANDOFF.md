# ADCOS Tech Lead Handoff — Architecture 1.1

## Mission

Turn ADCOS into the programmable connectivity exchange and orchestration layer
for heterogeneous connectivity.

## Single-agent mode

A single autonomous LLM MAY act as both **Architect and Tech Lead**. In this mode
it inherits the same repository-local authorization, ACR, worker, evidence,
review, acceptance and merge constraints as separate roles. It must not use role
combination as a reason to bypass a governance gate.

## Implementation-target rule

**Architecture 1.1 is the target architecture for all new ADCOS design and implementation.**

Architecture 1.0 is the legacy/frozen baseline that must be preserved only while
migrating existing implementation and historical evidence. It MUST NOT be used
to define new product semantics, new Work Items, new authority boundaries, or new
APIs except where an explicit migration requirement says to preserve 1.0 behavior.

`spec/architecture-1.1-proposed.md`, `spec/architecture-lock-1.1-proposed.md`,
`spec/application-model.md`, `spec/work-items-1.1.md`, and the 1.1 dependency/
migration/vertical-proof artifacts define the target to be formally promoted.
The first transition Work Item is **M001 — Architecture 1.1 Freeze**. Until M001
is accepted through the repository ACR process, no feature Work Item may silently
revert to designing from Architecture 1.0; feature work must either be blocked
or explicitly limited to migration-preserving behavior.

After M001 is accepted, the 1.1 architecture and locks become the sole normative
architecture for forward implementation, while Architecture 1.0 remains only as
historical/superseded evidence.

## Non-negotiable rule

Never trust another agent's report. Inspect the actual repository, diff, tests,
workflow logs and persisted evidence before accepting any claim that a blocker
is fixed, a migration is sufficient, an API is wired, a test count is correct,
architecture is implemented, or production readiness exists.

## Authority order

1. Accepted Architecture Change Requests and the active normative architecture snapshot.
2. Active architecture locks.
3. Change-control/ACR rules.
4. Current architecture-transition state and active authorization.
5. Dependency graph and gate-specific dependency overlays.
6. Work-item acceptance criteria.
7. Implementation code.
8. Agent reports.

During the transition, `spec/architecture.md` is the preserved 1.0 baseline;
1.1 target artifacts control all forward design choices until formally replaced
by their accepted frozen successor snapshot. Tests provide evidence; tests alone
do not define architecture.

## Bootstrap sequence

1. Read `README.md` and `AGENTS.md`.
2. Read the mission and the architecture-transition state.
3. Read the Architecture 1.1 target package: architecture, locks, application model, work-items, dependency graph, migration matrix and vertical proof.
4. Read the preserved Architecture 1.0 baseline only to understand existing behavior that must be retained, migrated, demoted, replaced or archived.
5. Read governance and change-control.
6. Read architect handoff/current state/execution state.
7. Read dependency graph, roadmap and the exact next gate-specific Work Item.
8. Inspect actual source tree and dependency boundaries.
9. Classify existing implementation using RETAIN / REFACTOR / DEMOTE / REPLACE / ARCHIVE against Architecture 1.1.
10. Reproduce baseline tests.
11. Select only dependency-ready work.
12. Define executable acceptance evidence.
13. Dispatch workers.
14. Review worker outputs against repository state and Architecture 1.1.
15. Integrate only architecture-compliant changes.
16. Run verification.
17. Update architect state/ledger only from verified facts.
18. Advance only after acceptance.

## Architectural center

The canonical durable object is `ConnectivityContract`.

Path, session, tunnel, bearer, eSIM and adapter state are execution artifacts.

## Application model

An authorized application may buy or sponsor connectivity for its users or
devices. Application ownership does not grant network-provider authority.

## Worker hierarchy

The Tech Lead may dispatch at most 3 workers. Each worker may dispatch at most 3
subagents. Maximum active descendant workers = 9.

Recommended allocation:

- Worker A: contracts, offers, policy, evidence.
- Worker B: execution plans, adapters, provider boundaries.
- Worker C: API, usage/commercial, vertical proofs, conformance and adversarial verification.

Workers may work in parallel only when their dependency/authority boundaries are
independent. Normative integration remains Tech Lead controlled.

## Completion rule

Do not report a work item complete until repository evidence demonstrates:

- acceptance criteria;
- invariant compliance;
- authority uniqueness;
- migration compatibility;
- deterministic tests where required;
- no provider SDK leakage;
- no hidden topology assumptions;
- no silent contract weakening;
- explicit conformance to the Architecture 1.1 target and its locks.
