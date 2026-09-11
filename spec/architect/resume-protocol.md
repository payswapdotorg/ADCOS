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

The latest reconciled software baseline is the M014 acceptance merge completing
the R7 gate `344cd64e8396c7e388e31a50635ddff16bb4ea14` (the M003 acceptance merge
`4090e03` and the M013 acceptance merge `8f4d58a2` precede it on main — the
3-worker pipeline's first parallel delivery round — with the DEC-0103/DEC-0113
acceptance record 9e16cb0 between them and the M009 branch point); the
DEC-0109 acceptance transition sits beyond it per the standing reconciliation
convention.

- R6 Provider Onboarding & Federation is complete under `DEC-0097`.
- M001 — Architecture 1.1 Freeze is complete under `DEC-0100`: Architecture 1.1
  is the sole normative forward architecture (`spec/architecture.md` FROZEN v1.1,
  LOCK-101..LOCK-120); Architecture 1.0 is preserved historical evidence at
  `spec/history/`; ACR-014 is ACCEPTED.
- `M001-CORE-001` is closed. **R7 — Universal Connectivity Commerce is ACTIVE
  under DEC-0101** as a bounded program authorization: `R7-CORE-001`
  (`spec/architect/authorizations/R7.yaml`) with the R7 charter
  (`spec/architect/work-items/R7-charter.md`) declaring the child work-item
  scopes M002-M014. **M002 — Connectivity Contract Core is ACCEPTED
  (DEC-0102; head 0112943, merge 0ffdf47). M003 — Offers and Provider
  Capability Exchange is ACCEPTED (DEC-0103; head eace143, merge 4090e03).**
  **M013 — Developer Connectivity API is ACCEPTED (DEC-0113; head 69ef8de,
  merge 8f4d58a2; chain-independent). M009 — Usage and Commercial
  Reconciliation is ACCEPTED (DEC-0109; head 5a807cd, merge c985b88). M010 —
  Vertical Proof — ShareNet is ACCEPTED (DEC-0110; head d5be84e, merge
  d0d26d3; the 8-step frozen flow harness with disclosed deterministic
  seams; the 33/33 battery CI-wired). M011 — Vertical Proof — RoamLink is
  ACCEPTED (DEC-0111; head fb4a921, merge c0f23c8; the 6-step frozen flow
  harness with disclosed deterministic seams; the 56/56 battery CI-wired;
  cohort.py the SDK-only application boundary — LOCK-120). M012 — Vertical
  Proof — COMOS is ACCEPTED (DEC-0112; head 201ceb8e, merge 6e3d09f; the
  6-step frozen flow harness with disclosed deterministic seams; the 33/33
  battery CI-wired; the COMOS external-application boundary — LOCK-120 —
  completing the M010/M011/M012 tranche). M004 — Eligibility and Policy is
  ACCEPTED (DEC-0104; head 92f293b, merge a52e1ee; the policy battery
  evolved 74/74 -> 103/103 disclosed; a CHAIN-CHILD acceptance — the
  pointer advances). M005 — Evidence and Assurance is ACCEPTED (DEC-0105;
  head a0c4aff, merge ccae488; the typed evidence-record domain — LOCK-106 —
  and the closed-loop assurance evaluation — LOCK-107 with the FROZEN §9
  state vocabulary; the telemetry harvest disclosed via the explicit seam;
  the 97/97 battery CI-wired; the second chain-pointer move). M006 —
  Execution Plan is ACCEPTED (DEC-0106; head 764007b, merge 1f9f509; the
  LOCK-109 canonical execution-plan translation; the composition/ harvest
  disclosed one-way; the 36/36 battery CI-wired; the third chain-pointer
  move). M007 — Provider/Standard Adapters is ACCEPTED (DEC-0107; head
  1636b15, merge cc93bb4; LOCK-112 reference adapters around existing
  standard/provider mechanisms; LOCK-110 provider-SDK isolation; the
  battery expanded 56 -> 70 cases, already wired and green at the merged
  head; one disclosed payment-battery frozen-family repair ratified — the
  DEC-0111 precedent; the fourth chain-pointer move). M008 — Replan and
  Failover is ACCEPTED (DEC-0108; head 8c7d685, merge ce65c88; replan/ eight
  modules — LOCK-108 the constraint-preservation core, LOCK-111 deterministic
  declared tie-breaking, the realization-state vocabulary; the sessions/
  mobility/ multipath harvest disclosed docstring-only with the one-way seam;
  the 38/38 battery CI-wired; the fifth chain-pointer move).** The current child
  is CLOSED. M014 — Production Federation is ACCEPTED (DEC-0109; head 689035e,
  merge 344cd64; the five convergence surfaces consuming every accepted child
  authority BY REFERENCE; the client battery DEC-0099 re-baseline 24/24 with
  W048 never restored; the scale battery evolved 45/45) — THE R7 GATE IS COMPLETE
  (all thirteen children M002-M014 accepted; the R7-CORE-001 program
  authorization is CLOSED). R8 — Resilience, Mobility and Scale is the next gate,
  UNLOCKED and NOT ACTIVATED: activation requires its own gate-specific Work
  Item contract, dependency overlay, evidence obligations, and repository-local
  implementation authorization (the DEC-0101 precedent); no implementation
  authorization is active.
  Per-child acceptance decisions (DEC-0104 onward) are the serialization points.
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
