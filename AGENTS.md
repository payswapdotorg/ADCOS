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
executionplan battery is CI-wired; the current child advances to M007).
M007 — Path Segments is the current child. Implementation proceeds only within the active authorization's declared
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
