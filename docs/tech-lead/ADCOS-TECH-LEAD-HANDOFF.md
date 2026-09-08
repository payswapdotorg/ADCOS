# ADCOS Tech Lead Handoff — Architecture 1.1

## Mission

Turn ADCOS into the programmable connectivity exchange and orchestration layer
for heterogeneous connectivity.

## Non-negotiable rule

Never trust another agent's report. Inspect the actual repository, diff, tests,
workflow logs and persisted evidence before accepting any claim that a blocker
is fixed, a migration is sufficient, an API is wired, a test count is correct,
architecture is implemented, or production readiness exists.

## Authority order

1. Frozen normative architecture.
2. Architecture locks.
3. Change-control/ACR rules.
4. Current architecture state and active authorization.
5. Dependency graph.
6. Work-item acceptance criteria.
7. Implementation code.
8. Agent reports.

Tests provide evidence; tests alone do not define architecture.

## Bootstrap sequence

1. Read `README.md`.
2. Read mission and the current authoritative architecture.
3. Read Architecture 1.1 proposal and proposed locks.
4. Read governance and change-control.
5. Read architect handoff/current state.
6. Read dependency graph and work-items.
7. Inspect actual source tree and dependency boundaries.
8. Classify existing implementation using RETAIN / REFACTOR / DEMOTE / REPLACE / ARCHIVE.
9. Reproduce baseline tests.
10. Select only dependency-ready work.
11. Define executable acceptance evidence.
12. Dispatch workers.
13. Review worker outputs against repository state.
14. Integrate only architecture-compliant changes.
15. Run verification.
16. Update architect state/ledger only from verified facts.
17. Advance only after acceptance.

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
- no silent contract weakening.
