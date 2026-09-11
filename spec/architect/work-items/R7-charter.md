# R7 — Universal Connectivity Commerce — Implementation Charter

**Gate-specific Work Item contract (DEC-0101 governance-compression class).**
**Authorization: R7-CORE-001 (bounded R7 program authorization, DEC-0101). Baseline: `1e5c55f9916ff964d3bfc0761d04a8d5fd02c41b`.**
**Status: COMPLETE (DEC-0109) — ALL THIRTEEN children accepted: M002 (DEC-0102, 0ffdf47), M003 (DEC-0103, 4090e03), M004 (DEC-0104, a52e1ee), M005 (DEC-0105, ccae488), M006 (DEC-0106, 1f9f509), M007 (DEC-0107, cc93bb4), M008 (DEC-0108, ce65c88), M009 (DEC-0109, c985b88), M010 (DEC-0110, d0d26d3), M011 (DEC-0111, c0f23c8), M012 (DEC-0112, 6e3d09f), M013 (DEC-0113, 8f4d58a2), M014 (DEC-0109, 344cd64 — the convergence child). The R7-CORE-001 program authorization is CLOSED with the gate completion.**

## Objective

Normalize heterogeneous connectivity resources into programmable offers selected by
intent, policy, evidence, availability, geography, quality, and price under the accepted
Architecture 1.1 contract model — delivered through the successor Work Items M002–M014
of the frozen 1.1 dependency model.

## Purpose of this charter (governance compression)

This ONE charter replaces the per-work-item pre-implementation paperwork chain
(per-item gate contract + overlay + evidence-obligation package + authorization
issuance) that historically serialized each work item behind a new governance
ceremony. Under DEC-0101:

- **One** R7 program authorization (`R7-CORE-001`, `spec/architect/authorizations/R7.yaml`)
  is active for the whole tranche, with **child work-item scopes** declared below.
- The **Tech Lead** may decompose, dispatch (≤3 direct workers, ≤3 subagents each,
  ≤9 descendants, depth 2 per `docs/tech-lead/dispatch-state.yaml`), branch, integrate,
  test and deliver PRs against any already-authorized child scope **without a new
  pre-implementation authorization ceremony**.
- **Per-M-item acceptance remains mandatory** and is the sole Architect-side gate:
  each child is accepted only from repository evidence (deterministic battery, lock
  conformance, provenance, review) via a durable acceptance decision
  (DEC-0102, DEC-0103, … — one per child).
- At most **one** implementation authorization is active at any time (the R7 program
  authorization), preserving the standing authority-uniqueness invariant.

## Architectural invariants (non-negotiable, from the FROZEN 1.1 locks)

LOCK-101 canonical contract · LOCK-102 intent independence · LOCK-103 application
purchasing · LOCK-104 provider sovereignty · LOCK-105 no global topology ·
LOCK-106 evidence typing · LOCK-107 closed-loop assurance · LOCK-108 no silent
contract weakening · LOCK-109 execution bridge · LOCK-110 adapter isolation ·
LOCK-111 optimizer replaceability · LOCK-112 standard leverage · LOCK-113
commercial separation · LOCK-114 developer semantics · LOCK-115 simple-system
validity · LOCK-116 complex-system composition · LOCK-117 authority uniqueness ·
LOCK-118 provenance · LOCK-119 secrets · LOCK-120 vertical proof boundaries.

Canonical authority: `ConnectivityContract` is the durable authority for acquired
connectivity. No `Path`, `Session`, `Tunnel`, `Bearer`, `AdapterBinding`, `eSIM`,
adapter or provider record may become a second contract authority. Execution
artifacts may change while the contract remains stable.

## Child work-item scopes and acceptance criteria

Each child carries: (a) its declared scope (the authorization covers exactly these
prefixes plus the shared battery surface), (b) acceptance criteria evaluated at
acceptance time, (c) a deterministic battery (or an authorized amendment to an
existing battery) as SOFTWARE evidence. Scope prefixes outside the declared list
require a lightweight charter **scope-amendment decision** recorded in the decisions
registry — not a re-authorization ceremony.

### M002 — Connectivity Contract Core (current child)

- **Scope:** `contracts/` (new canonical domain), `tools/contract_selftest.py`,
  `docs/M002-evidence.md`, plus the shared authorization-aware battery-scope
  consultation repairs across the existing battery surface (the duty pre-recorded in
  `docs/M001-evidence.md` §4 for the post-M001 implementation era).
- **Acceptance criteria:** canonical `ConnectivityContract` domain model implementing
  contract identity; principal and beneficiary scope; normalized requirements;
  accepted offer references; hard constraints; committed service properties; validity
  interval; usage and pricing terms; assurance obligations; permitted execution scope;
  termination and compensation rules; provenance; and signature references (frozen 1.1
  §3) — with lease/expiry semantics, the contract-level lifecycle state machine
  (frozen 1.1 §9/§11), hard-constraint immutability (LOCK-108), and structural
  authority uniqueness (LOCK-117: execution artifacts ride as opaque references,
  never as authorities). Deterministic, offline, seeded; no wall clock, no randomness,
  no network; secrets never stored (LOCK-119); canonical-JSON round-trips; journal
  fold with idempotency; battery green; evidence doc records the verification matrix.

### M003 — Offers and Provider Capability Exchange

- **Scope:** `offers/` (new), `capabilities/`, `discovery/`, `marketplace/`
  (harvest + refactor per the migration matrix), `tools/offer_selftest.py`,
  `docs/M003-evidence.md`.
- **Acceptance:** provider-domain capability advertisements, offers, validity,
  commitments and provenance under LOCK-118; no global topology (LOCK-105).

### M004 — Eligibility and Policy — ACCEPTED (DEC-0104: PR #34 head 92f293b, merge a52e1ee — the current-child pointer advances to M005)

- **Scope:** `policy/`, `eligibility/`, `tools/policy_selftest.py`,
  `tools/eligibility_selftest.py` (era-superseded battery re-baseline may land here
  or under M009 per its disclosure), `docs/M004-evidence.md`.
- **Acceptance:** deterministic eligibility and policy evaluation around the canonical
  contract; zero provider-SDK leakage (LOCK-110 discipline at the policy boundary).

### M005 — Evidence and Assurance — ACCEPTED (DEC-0105: PR #33 head a0c4aff, merge ccae488 — the current-child pointer advances to M006)

- **Scope:** `assurance/`, `evidence/` (new), `telemetry/` (harvest),
  `tools/assurance_selftest.py`, `docs/M005-evidence.md`.
- **Acceptance:** typed evidence records (claim/observation/commitment/attestation,
  LOCK-106) and contract-level closed-loop assurance evaluation (LOCK-107) with the
  frozen assurance state vocabulary.

### M006 — Execution Plan — ACCEPTED (DEC-0106: PR #35 head 764007b, merge 1f9f509 — the current-child pointer advances to M007)

- **Scope:** `executionplans/` (new), `composition/` (harvest),
  `tools/executionplan_selftest.py`, `docs/M006-evidence.md`.
- **Acceptance:** contract-to-execution-plan translation (LOCK-109) and execution
  segments; plans may not weaken hard constraints (LOCK-108).

### M007 — Provider/Standard Adapters — ACCEPTED (DEC-0107: PR #36 head 1636b15, merge cc93bb4 — the current-child pointer advances to M008)

- **Scope:** `adapters/` (harvest + refactor), `tools/adapter_selftest.py`,
  `docs/M007-evidence.md`.
- **Acceptance:** reference adapters around existing standard/provider mechanisms
  (LOCK-112) behind the capability-oriented boundary; SDK isolation (LOCK-110).

### M008 — Replan and Failover — ACCEPTED (DEC-0108: PR #37 head 8c7d685, merge ce65c88 — the current-child pointer advances to M014)

- **Scope:** `replan/` (new), `mobility/`, `multipath/`, `sessions/` (harvest),
  `tools/replan_selftest.py`, `docs/M008-evidence.md`.
- **Acceptance:** closed-loop replan preserving hard contract constraints (LOCK-108);
  impossible realizations enter explicit degraded/failed states or explicit
  renegotiation.

### M009 — Usage and Commercial Reconciliation — ACCEPTED (DEC-0109: PR #29 head 5a807cd, merge c985b88)

- **Scope:** `usage/`, `commercial/`, `allocation/`, `payment/` (harvest + re-bind),
  the era-superseded battery re-baselines assigned to the M009/M014 commercial track
  by the DEC-0099 disclosure (`tools/payment_selftest.py`,
  `tools/eligibility_selftest.py`), `tools/usage_selftest.py`,
  `tools/commercial_selftest.py`, `tools/allocation_selftest.py`,
  `docs/M009-evidence.md`.
- **Acceptance:** usage records and settlement references bound to the canonical
  contract (LOCK-113); payment movement stays external; no commercial authority
  migration into networking.

### M010 / M011 / M012 — Vertical Proofs (ShareNet / RoamLink / COMOS) — M010 ACCEPTED (DEC-0110: PR #30 head d5be84e, merge d0d26d3); M011 ACCEPTED (DEC-0111: PR #31 head fb4a921, merge c0f23c8); M012 ACCEPTED (DEC-0112: PR #32 head 201ceb8e, merge 6e3d09f) — the vertical-proof tranche is complete

- **Scope:** `sharenet/`, `roamlink/`, `comos/` (new vertical harnesses),
  `docs/M010-evidence.md`, `docs/M011-evidence.md`, `docs/M012-evidence.md`.
- **Acceptance:** application-funded connectivity and failure-recovery proof (M010);
  mobile/roaming acquisition proof (M011); communication-gateway connectivity proof
  (M012) — as SOFTWARE-class proofs (deterministic simulation/emulation batteries);
  vertical application semantics stay owned by the applications (LOCK-120). Requires
  M013 acceptance first.

### M013 — Developer Connectivity API

- **Scope:** `developerapi/` (harvest the W046-era API surface and translate onto the
  canonical 1.1 authority — a refactor, not a greenfield rewrite),
  `tools/developerapi_selftest.py`, `docs/M013-evidence.md`.
- **Acceptance:** technology-neutral contract/offers/assurance/usage semantics
  (LOCK-114); no network implementation objects in the API; no second domain model.

### M014 — Production Federation — ACCEPTED (DEC-0109: PR #38 head 689035e, merge 344cd64 — the convergence child completing the R7 gate)

- **Scope:** `federation/`, `scale/`, `upgrade/`, `identity/`, `client/` (harvest +
  harden; `tools/client_selftest.py` re-baseline per the DEC-0099 disclosure),
  `tools/scale_selftest.py`, `docs/M014-evidence.md`.
- **Acceptance:** production-hardened provider domains, authorization, evidence,
  compatibility, rate limits and revocation; convergence of M008+M009+M010+M011+
  M012+M013. Acceptance is blocked until those prerequisites are accepted; parallel
  preparation is permitted but never falsely claimed as acceptance.

## Migration policy

Architecture 1.0 material is a migration reservoir, never forward design authority.
The frozen classification matrix (`spec/migration/classification-matrix.md`) governs
RETAIN / REFACTOR / DEMOTE / REPLACE / ARCHIVE per area. Historical acceptance
evidence is never rewritten. W048 stays accepted-not-restored (its surfaces are
forbidden dependencies). The era-superseded batteries are re-baselined under their
assigned M-items, visibly, never silently.

## Evidence policy

Per-child acceptance requires deterministic, offline, reproducible SOFTWARE evidence
(the child battery plus lock-conformance assertions in the evidence doc). Simulation
and emulation are SOFTWARE-class. No battery or evidence doc may convert software
evidence into PHYSICAL PASS. The open physical obligations EVID-002..EVID-008 are
unaffected by this charter and remain visible in every current-state projection.
Acceptance decisions record the exact reviewed delivery head and merge SHA.

## Worker policy

The Tech Lead owns decomposition, dispatch, branching, integration, testing and
verification, bounded by `docs/tech-lead/worker-model.md` and the machine-checked
`docs/tech-lead/dispatch-state.yaml` (≤3 direct workers; ≤3 subagents per worker;
≤9 active descendants; depth ≤2). Recommended R7 allocation once M002 is accepted:
Worker A — the M003→M008 exchange/execution pipeline; Worker B — M013 then the
M010/M011/M012 verticals; Worker C — M009 then M014 convergence preparation.
Parallelism only across dependency- and authority-independent scopes; integration
and normative conformance remain Tech Lead controlled.

## Acceptance rules (Architect side, per child)

1. The delivery PR classifies as implementation-only under
   `tools/architecture_drift_guard.py` (no control-plane mixing).
2. Every implementation file in the delta is covered by the active R7-CORE-001 scope
   (`tools/authorization_provenance.py`, the current-era ARCH-08 successor gate).
3. The child battery and the full existing battery suite are green on the delivery
   head (implementation-only deltas run the blocking battery set).
4. The evidence doc (`docs/M00x-evidence.md`) records the verification matrix,
   lock-conformance mapping, and any disclosed deviations.
5. The sole Architect reviews the exact head against this charter and records a
   durable acceptance decision (exact reviewed SHA + merge SHA); execution-state,
   roadmap and ledger are reconciled to the merge; the child advances the
   dependency chain.

## Out of scope (whole tranche)

- Any control-plane surface (`spec/`, `.github/`, `AGENTS.md`, `README.md`,
  `docs/tech-lead/`, the drift-guard CONTROL_FILES) — those change only through
  governance decisions, never through implementation PRs.
- `spec/mission.md`, protocol/wire semantics (Protocol Version 1.0 frozen without an
  accepted ACR), `containment/`/`sharing/` (WORK-048 accepted-not-restored),
  `pilot/` (WORK-040 physical track).
- Rewriting or deleting historical acceptance records, ledger entries, or archived
  1.0 content.
- Converting SOFTWARE evidence into PHYSICAL PASS; disturbing EVID-001 closure or
  EVID-002..EVID-008 visibility.
