# ADCOS Agent Entry Point

ADCOS is self-describing. A new Architect, Tech Lead, worker, or implementation agent MUST derive authority from the repository and live GitHub state, never from chat history.

## Role bootstrap

- **Architect:** read `spec/architect/resume-protocol.md`, then reconstruct authority and govern sequencing, authorization, review, acceptance and merge.
- **Tech Lead:** read `docs/tech-lead/ADCOS-TECH-LEAD-HANDOFF.md` and `docs/tech-lead/worker-model.md` after this file; coordinate authorized implementation work against the **Architecture 1.1 target**, not the legacy 1.0 model.
- **Worker:** read the Tech Lead handoff, the exact authorized Work Item, its dependency overlay and the applicable Architecture 1.1 target/locks before changing code.

## Resume order

1. Read `README.md` and this file.
2. Read `spec/architect/resume-protocol.md`.
3. Read `spec/mission.md`.
4. Read the Architecture 1.1 target package and transition state.
5. Read the preserved Architecture 1.0 baseline only for migration/compatibility context.
6. Read `spec/work-items.md` and `spec/dependency-graph.md` for historical constraints, then the 1.1 work/dependency artifacts for forward implementation.
7. Read `spec/architect/roadmap.yaml`, `spec/architect/current-state.md`, and `spec/architect/execution-state.yaml`.
8. Read `spec/architect/authority-order.md` and `spec/architect/governance-autonomy.md`.
9. Identify the current active Work Item and repository-local authorization, if any.
10. Inspect actual GitHub `main` and recent commits before acting.

## Implementation-target rule

**Architecture 1.1 is the mandatory forward implementation target.** Architecture 1.0 is a preserved legacy baseline only.

New APIs, domain models, authority boundaries, Work Items, migrations and
acceptance criteria MUST trace to Architecture 1.1 locks and target artifacts.
No agent may use Architecture 1.0 to invent new behavior merely because 1.0 is
currently present in the repository.

M001 — Architecture 1.1 Freeze has been accepted (DEC-0100): the promotion
(ACR-014) is complete, the canonical files `spec/architecture.md` and
`spec/architecture-lock.md` carry Architecture 1.1 and LOCK-101..LOCK-120 as
FROZEN, and Architecture 1.0 is preserved verbatim under `spec/history/` as
superseded historical evidence. Architecture 1.1 is permanently the sole
normative architecture for forward implementation. The current program gate is
R7 — Universal Connectivity Commerce, ACTIVE under DEC-0101 as a bounded
program authorization (`R7-CORE-001`, `spec/architect/authorizations/R7.yaml`)
with the R7 charter (`spec/architect/work-items/R7-charter.md`) declaring the
child work-item scopes M002-M014. M002 — Connectivity Contract Core is
ACCEPTED (DEC-0102; head 0112943, merge 0ffdf47; the canonical `contracts/`
domain is live). M003 — Offers and Provider Capability Exchange is ACCEPTED
(DEC-0103; head eace143, merge 4090e03; the provider-domain `offers/` model is
live with its 49/49 battery). M013 — Developer Connectivity API is ACCEPTED
(DEC-0113; head 69ef8de, merge 8f4d58a2; chain-independent). M009 — Usage
and Commercial Reconciliation is ACCEPTED (DEC-0109; head 5a807cd, merge
c985b88; usage/commercial/allocation/payment re-bound to the canonical
contracts/ domain; the payment 44/44 and eligibility 46/46 DEC-0099
re-baselines landed). M010 — Vertical Proof — ShareNet is ACCEPTED
(DEC-0110; head d5be84e, merge d0d26d3; the 33/33 sharenet battery is
CI-wired). M011 — Vertical Proof — RoamLink is ACCEPTED (DEC-0111; head
fb4a921, merge c0f23c8; the 56/56 roamlink battery is CI-wired). M012 —
Vertical Proof — COMOS is ACCEPTED (DEC-0112; head 201ceb8e, merge
6e3d09f; the 33/33 comos battery is CI-wired). M004 — Eligibility and
Policy is ACCEPTED (DEC-0104; head 92f293b, merge a52e1ee; the policy
battery evolved to 103/103; the current child advances to M005). M005 — Evidence and Assurance is
ACCEPTED (DEC-0105; head a0c4aff, merge ccae488; the 97/97 assurance
battery is CI-wired; the current child advances to M006). M006 — Execution
Plan is ACCEPTED (DEC-0106; head 764007b, merge 1f9f509; the 36/36
executionplan battery is CI-wired; the current child advances to M007). M007 —
Provider/Standard Adapters is ACCEPTED (DEC-0107; head 1636b15, merge
cc93bb4; the adapter battery expanded to 70/70 — already wired and green
at the merged head; one disclosed payment-battery frozen-family repair
ratified; the current child advances to M008). M008 — Replan and
Failover is ACCEPTED (DEC-0108; head 8c7d685, merge ce65c88; the 38/38
replan battery is CI-wired; the sessions/mobility/multipath harvest
disclosed docstring-only with the one-way seam; the current child advances
to M014 — the LAST chain child). M014 — Production Federation is ACCEPTED
(DEC-0109; head 689035e, merge 344cd64; the five convergence surfaces
consuming every accepted child authority BY REFERENCE; the client battery
DEC-0099 re-baseline 24/24 with W048 never restored; the scale battery
evolved 45/45). THE R7 GATE IS COMPLETE — all thirteen children accepted;
the R7-CORE-001 program authorization is CLOSED; R8 (Resilience, Mobility
and Scale) is ACTIVE under DEC-0114: the bounded R8 program authorization
R8-CORE-001 (spec/architect/authorizations/R8.yaml, baseline 28b3150, the R8
charter at spec/architect/work-items/R8-charter.md) covers the child scopes
M015-M019 with M015 — Execution Resilience Runtime ACCEPTED (DEC-0115; head
95a65a5, merge d77a561; the resilience/ runtime domain composing the accepted
contracts/, replan/, executionplans/, evidence/ authorities BY REFERENCE; the
36/36 battery CI-wired and green; delivered across two worker sessions under
the continuation charter with two disclosed in-scope resilience/ defect fixes),
M016 — Local-First and Offline Operation ACCEPTED (DEC-0116; head 0d5cfb7,
merge a0ebd019; the localfirst/ domain composing the accepted contracts/,
replan/, resilience/ authorities BY REFERENCE — the M015 runtime the
composition substrate; the 35/35 battery CI-wired and green; a clean
single-session delivery with zero disclosed defect fixes),
M017 — Disaster Recovery and State Reconciliation ACCEPTED (DEC-0117; head
f016124, merge 438acb66; the recovery/ domain composing the accepted
contracts/, resilience/, localfirst/, evidence/ authorities BY REFERENCE —
the M015 runtime journals and the M016 offline journals the drill substrate;
the 36/36 battery CI-wired and green; delivered through the site-side
destruction cycle — three sessions, the third completed the append-only
branch, zero disclosed implementation defect fixes),
M018 — Credential and Key Lifecycle Operations ACCEPTED (DEC-0118; head
dba0e9a, merge e037ca8d — the CHAIN-INDEPENDENT acceptance: the current-child
pointer does NOT move; the credentials/ domain composing the accepted M014
identity/federation/client convergence surfaces BY REFERENCE; the 32/32
battery CI-wired and green; the two-session continuation delivery with one
disclosed battery defect fix),
and M019 — Resilience Convergence and Scale Hardening ACCEPTED (DEC-0119; head
acf9e6c, merge 3fedfbc — the convergence child completing the R8 gate: the
resilience/convergence.py surface composing every accepted R8 child authority
BY REFERENCE; the evolved 53/53 scale battery green at the completed head;
delivered through the wedged-render turn — the git/PR channel the truth).
R8 — Resilience, Mobility and Scale is COMPLETE (all five children accepted;
the R8-CORE-001 program authorization CLOSED). R9 — Future Access Technology
is ACTIVE under DEC-0120: the bounded R9 program authorization R9-CORE-001
(spec/architect/authorizations/R9.yaml, baseline ea4bb64, the R9 charter at
spec/architect/work-items/R9-charter.md) covers the child scopes M020-M024
(M020 — Access Technology Capability Envelope ACCEPTED under DEC-0121 (PR #44
head 035242de, merge c75a7c70 — the current-child pointer advanced to M021); M021 Wireline
Access Adapters ACCEPTED under DEC-0122 (PR #45 head 8966693, merge
8ebdb21 — the current-child pointer advanced to M022); M022 Non-Terrestrial
Access Adapters ACCEPTED under DEC-0123 (PR #46 head 16eb274, merge
68060d9 — the current-child pointer advanced to M024 along the chain); M023
Future Technology Extension Drill ACCEPTED under DEC-0124 (PR #47 head
385be97, the station-resolved merge 67d99d1 — chain-independent, the
pointer does not move); M024 Future Access Convergence ACCEPTED under DEC-0125
(PR #48 head 5e7797a, merge d1dbe69 — the convergence child completing the R9
gate, the TERMINAL gate: the roadmap's gate sequence R0-R9 complete, the
R9-CORE-001 authorization CLOSED, the program_exit evaluation recorded
SOFTWARE-class; the execution mode awaiting-architect-decisions); M023 Future Technology
Extension Drill, chain-independent — the synthetic future-IMT/6G-class
technology added purely through the accepted public extension surface; M024
Future Access Convergence the convergence child). R9 is the TERMINAL roadmap
gate: the M024 acceptance completes the gate sequence R0-R9 and evaluates the
program_exit conditions (SOFTWARE-class only). Every accepted R7/R8 authority
is consumed BY REFERENCE (the R9 charter consumption rule). Implementation proceeds only within the active authorization's declared
scope; each child work item is accepted only from repository evidence per the
charter's acceptance rules.

## Live-main rule

Always compare the actual `main` SHA with `spec/architect/execution-state.yaml`. If they differ, inspect the intervening commits and reconcile the persistent Architect snapshot before implementation resumes. A newer mainline always supersedes an older snapshot.

## Authorization

No active repository-local authorization means implementation MUST stop. Roadmap membership, an issue, a PR, a handoff, or a chat instruction never grants implementation permission.

At most one implementation authorization may be active at a time.

## Tech Lead dispatch limit

The Tech Lead may dispatch at most 3 direct workers. Each direct worker may dispatch at most 3 subagents. Maximum active descendants: 9.

Parallel work is permitted only when dependency and authority boundaries are independent. The Tech Lead remains responsible for integration and verification.

## Frozen architecture

The historical `spec/architecture.md` and `spec/architecture-lock.md` MUST NOT be silently rewritten by an ordinary implementation PR. Architecture 1.1 promotion requires the repository's ACR/change-control process.

The existence of `spec/architecture-1.1-proposed.md` is not by itself an authorization, but it IS the required target for all forward design during the transition.

## Evidence

Never convert software/emulated evidence into physical PASS by inference. Never treat an agent report, test count, PR description, or generated audit as authoritative without repository verification.

## Working practice

Prefer a local Git clone and ordinary Git history for multi-file changes. Do not write directly to `main` for implementation or governance transitions that require review.

## Verification

Before acting from a fresh session, run:

```bash
python3 tools/spec_check.py
python3 tools/fresh_session_check.py
```

If the persistent governance package fails its checks, repair governance through the proper review mechanism; never weaken the invariant to make a task pass.

## Fresh-session guarantee

A clean clone of `main` plus GitHub access, without conversation history, MUST be sufficient to determine mission, the Architecture 1.1 forward target, the preserved 1.0 baseline, roadmap state, current execution state, next gate, implementation authorization, worker limits, and acceptance requirements.
