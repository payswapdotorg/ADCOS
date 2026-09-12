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

The latest reconciled software baseline is the M016 acceptance merge
`a0ebd019a03238d089f03f006e9364e5c03cde51` (the DEC-0109 R7-completion
acceptance head `28b3150`, the DEC-0114 R8-activation commit `b0145f1`, the
M015 acceptance merge `d77a561` and the DEC-0115 acceptance commit `6b96438`
precede it on main — the m016-localfirst delivery branch rooted at `6b96438`;
the delivery merged as `a0ebd019` completing the second R8 child); the
DEC-0116 acceptance transition sits beyond it per the standing reconciliation
convention.

- R6 Provider Onboarding & Federation is complete under `DEC-0097`.
- M001 — Architecture 1.1 Freeze is complete under `DEC-0100`: Architecture 1.1
  is the sole normative forward architecture (`spec/architecture.md` FROZEN v1.1,
  LOCK-101..LOCK-120); Architecture 1.0 is preserved historical evidence at
  `spec/history/`; ACR-014 is ACCEPTED.
- `M001-CORE-001` is closed. **R8 — Resilience, Mobility and Scale is ACTIVE
  under DEC-0114** (the DEC-0101 governance-compression precedent) as a bounded
  program authorization: `R8-CORE-001`
  (`spec/architect/authorizations/R8.yaml`, baseline `28b3150`) with the R8
  charter (`spec/architect/work-items/R8-charter.md`) declaring the
  gate-specific child work-item scopes M015-M019 (M017 Disaster Recovery and
  State Reconciliation — the CURRENT child, implementing; M018 Credential and
  Key Lifecycle Operations, chain-independent; M019 Resilience Convergence
  and Scale Hardening — the convergence child whose acceptance COMPLETES the
  R8 gate and unlocks R9) and
  the overlay (`spec/architect/dependency-overlays/R8.yaml`: M015 -> M016 ->
  M017 -> M019, M018 chain-independent, M019 converges all four, R7 the sole
  hard dependency). **M015 — Execution Resilience Runtime is ACCEPTED
  (DEC-0115; head 95a65a5, merge d77a561; the resilience/ runtime domain —
  session-runtime lifecycle with the WORK-012 explicit-reconnect discipline
  mechanically enforced, mobility handover with LOCK-108 per-kind
  weakened-constraint rejection, multipath failover with LOCK-111 declared
  recorded tie-breaking over the accepted executionplans/replan kernels, the
  M008 realization-state vocabulary consumed additively; the 36/36 battery
  CI-wired and green at the accepted head; delivered across two worker sessions
  on the append-only branch under the continuation charter — the GLM-5.3
  capacity peak destroyed 8+ sessions during the delivery window — with two
  disclosed in-scope resilience/ defect fixes) — the FIRST R8 chain-child
  acceptance: the current-child pointer advances M015 -> M016 and the
  R8-CORE-001 authorization stays ACTIVE.** **M016 — Local-First and Offline
  Operation is ACCEPTED (DEC-0116; head 0d5cfb7, merge a0ebd019; the
  localfirst/ domain — deterministic offline operation journals with
  idempotent position-independent content identities, partition-tolerant
  admission with fail-closed stale-authority rejection (never a silent allow
  past the declared freshness window — the fold mechanically rejects the
  forged silent-allow shape), LOCK-108 across the offline boundary (all 12
  constraint kinds x DROP/RELAX/REINTERPRET rejected with typed reasons at
  admission and re-verified at resynchronization — the wire-forged journaled
  admitted record rejected), explicit reconnect/resynchronization with
  divergence detection and LOCK-111 declared recorded deterministic
  convergence (same inputs byte-identical, both rule directions, never
  dropped, never duplicated), journaled degraded-mode operation, the M015
  runtime consumed BY REFERENCE as the composition substrate (the RuntimeStore
  lifecycle driven by reference for every offline transition); the 35/35
  battery CI-wired and green at the accepted head; delivered in ONE worker
  session on the append-only branch — a clean single-session delivery with
  zero disclosed defect fixes) — the SECOND R8 chain-child acceptance: the
  current-child pointer advances M016 -> M017 and the R8-CORE-001
  authorization stays ACTIVE.** The R8 charter consumption rule:
  every accepted R7 authority consumed BY REFERENCE — never reimplemented,
  weakened, forked, or bypassed; the legacy resilience reservoir
  (sessions/mobility/multipath/edge/appliance) is harvest material per the
  frozen migration classification matrix.
- `M001-CORE-001` is closed. **R7 — Universal Connectivity Commerce is COMPLETE
  under DEC-0101/DEC-0109**
- `M001-CORE-001` is closed. **R7 — Universal Connectivity Commerce was
  ACTIVATED under DEC-0101** as a bounded program authorization: `R7-CORE-001`
  (`spec/architect/authorizations/R7.yaml`) with the R7 charter
  (`spec/architect/work-items/R7-charter.md`) declaring the child work-item
  scopes M002-M014 (the authorization is now CLOSED by the DEC-0109 gate
  completion). **M002 — Connectivity Contract Core is ACCEPTED
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
  authorization is CLOSED). R8 — Resilience, Mobility and Scale is now ACTIVE
  under DEC-0114 (the R8 charter + overlay + the R8-CORE-001 program
  authorization above); M015 — Execution Resilience Runtime is ACCEPTED
  (DEC-0115), M016 — Local-First and Offline Operation is ACCEPTED (DEC-0116),
  and M017 — Disaster Recovery and State Reconciliation is the current
  child (implementing).
  Per-child acceptance decisions (DEC-0117 onward for the R8 children) are the
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
