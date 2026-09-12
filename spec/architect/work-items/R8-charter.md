# R8 — Resilience, Mobility and Scale — Implementation Charter

**Gate-specific Work Item contract (DEC-0114 governance-compression class, the DEC-0101 precedent).**
**Authorization: R8-CORE-001 (bounded R8 program authorization, DEC-0114). Baseline: `28b31500a928f2f75582bfb79039e315187d72b2`.**
**Status: ACTIVE — the R8 implementation tranche M015-M019 is open; M015 — Execution Resilience Runtime is ACCEPTED (DEC-0115; head 95a65a5, merge d77a561 — the current-child pointer advances to M016); M016 — Local-First and Offline Operation is ACCEPTED (DEC-0116; head 0d5cfb7, merge a0ebd019 — the current-child pointer advances to M017); M017 — Disaster Recovery and State Reconciliation is the current child.**

## Objective

Harden failover, multipath, mobility, local-first operation, offline/reconnect,
reconciliation, disaster recovery, key rotation/revocation, upgrades, federation
scale, and operational resilience under the accepted Architecture 1.1 contract
model — delivered as the gate-specific execution units M015-M019 consuming the
accepted R7 authorities BY REFERENCE (the M014 convergence discipline: no accepted
child reimplemented, weakened, or bypassed).

## Purpose of this charter (governance compression)

This ONE charter replaces the per-work-item pre-implementation paperwork chain
for the R8 gate, exactly as the R7 charter did for the R7 gate under DEC-0101.
Under DEC-0114:

- **One** R8 program authorization (`R8-CORE-001`,
  `spec/architect/authorizations/R8.yaml`) is active for the whole tranche, with
  **child work-item scopes** declared below.
- The **Tech Lead** may decompose, dispatch (≤3 direct workers, ≤3 subagents
  each, ≤9 descendants, depth 2 per `docs/tech-lead/dispatch-state.yaml`),
  branch, integrate, test and deliver PRs against any already-authorized child
  scope **without a new pre-implementation authorization ceremony**.
- **Per-M-item acceptance remains mandatory** and is the sole Architect-side
  gate: each child is accepted only from repository evidence (deterministic
  battery, lock conformance, provenance, review) via a durable acceptance
  decision (DEC-0115, DEC-0116, … — one per child).
- At most **one** implementation authorization is active at any time (the R8
  program authorization), preserving the standing authority-uniqueness invariant.
- The R8 children are **gate-specific execution units** introduced by this
  roadmap gate under the governance-autonomy Post-snapshot rule (durable
  contract, explicit dependencies against accepted history, exact authorization
  before implementation, explicit acyclic overlay, no frozen semantic changed
  implicitly, no historical record rewritten). They extend the M-series
  numbering beyond the frozen 1.1 successor registry (M001-M014) without
  modifying it.

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
adapter, provider, resilience, recovery, or credential record may become a second
contract authority. Execution artifacts may change while the contract remains
stable — the R8 surfaces are execution/runtime capabilities in the classification
matrix's sense (Session/Multipath/Mobility RETAIN; Transport/Routing/Topology
DEMOTE), never contract authorities.

## Consumption rule (the R8 hardening discipline)

Every R8 child consumes the accepted R7 authorities (`contracts/`, `offers/`,
`eligibility/`, `policy/`, `evidence/`, `assurance/`, `executionplans/`,
`adapters/`, `replan/`, `usage/`, `commercial/`, `allocation/`, `payment/`,
`sharenet/`, `roamlink/`, `comos/`, `developerapi/`, `federation/`, `identity/`,
`upgrade/`, `scale/`, `client/`) **BY REFERENCE** — import and compose, never
reimplement, weaken, fork, or bypass. Resilience hardening adds the
failure-mode machinery (failover orchestration, offline operation, recovery,
credential lifecycle drills, convergence drills) AROUND those authorities.
The legacy 1.0 reservoir (`sessions/`, `mobility/`, `multipath/`, `edge/`,
`appliance/`, `mobile/`, `management/`, `routing/`, `transport/`, `topology/`,
`networkpath/`, `resources/`, `services/`, `simulator/`) is harvest material
per the frozen migration classification matrix — never forward design
authority; the M008 docstring-only disclosures in `sessions/`, `mobility/`,
`multipath/` stay exactly as accepted.

## Child work-item scopes and acceptance criteria

Each child carries: (a) its declared scope (the authorization covers exactly
these prefixes plus the shared battery surface), (b) acceptance criteria
evaluated at acceptance time, (c) a deterministic battery as SOFTWARE evidence.
Scope prefixes outside the declared list require a lightweight charter
**scope-amendment decision** recorded in the decisions registry — not a
re-authorization ceremony.

### M015 — Execution Resilience Runtime — ACCEPTED (DEC-0115: PR #39 head 95a65a5, merge d77a561 — the current-child pointer advances to M016)

- **Scope:** `resilience/` (NEW — the execution-runtime resilience domain),
  `tools/resilience_selftest.py` (NEW battery), `docs/M015-evidence.md`, plus
  the shared battery surface (`tools/`, the authorization-aware consultation
  repairs).
- **Acceptance criteria:** the runtime resilience surface on the canonical
  authority — session-runtime lifecycle with explicit reconnect transitions
  (the WORK-012 discipline functionally enforced: every route change an
  explicit recorded reconnect event naming old AND new references, never a
  silent replacement), mobility handover with hard-constraint preservation
  (LOCK-108: verbatim constraint-set equality across every handover/failover
  transition, typed weakened-constraint rejection), multipath failover
  orchestration with deterministic declared recorded tie-breaking (LOCK-111)
  over the accepted `executionplans/`/`replan/` surfaces, the realization-state
  vocabulary (`REALIZING/DEGRADED/FAILED/SUPERSEDED`, the M008-owned kernel)
  extended without redefining it, degraded-mode entry that is explicit and
  evidence-visible, and execution artifacts as opaque references (LOCK-117).
  Deterministic, offline, seeded; no wall clock, no randomness, no network;
  secrets never stored (LOCK-119); canonical-JSON round-trips; battery green;
  evidence doc records the verification matrix. Imports flow one way:
  `resilience/` may import the accepted authorities; no accepted authority
  imports `resilience/`.

### M016 — Local-First and Offline Operation — ACCEPTED (DEC-0116: PR #40 head 0d5cfb7, merge a0ebd019 — the current-child pointer advances to M017)

- **Scope:** `localfirst/` (NEW), `tools/localfirst_selftest.py` (NEW battery),
  `docs/M016-evidence.md`.
- **Acceptance criteria:** local-first operation over the canonical contract
  state — deterministic offline operation journals (ordered, idempotent,
  replayable), partition-tolerant admission with fail-closed stale-authority
  rejection (a local state past its declared freshness bound never silently
  authorizes), explicit reconnect and resynchronization with divergence
  detection and deterministic convergence (conflicting offline operations
  resolve by declared recorded rules, never silently dropped or duplicated),
  no silent contract weakening during partition or resynchronization
  (LOCK-108 across the offline boundary), and degraded-mode operation that is
  explicit and journaled. The M015 runtime is the composition substrate
  (dependency: M015).

### M017 — Disaster Recovery and State Reconciliation (current child)

- **Scope:** `recovery/` (NEW), `tools/recovery_selftest.py` (NEW battery),
  `docs/M017-evidence.md`.
- **Acceptance criteria:** deterministic disaster-recovery drills over the
  journal-bearing state planes (the M015 runtime journals and the M016 offline
  journals): snapshot/recovery-point construction, restore verification
  (recovered state equals the pre-failure state byte-exactly, or the divergence
  is explicitly disclosed and reconciled), recovery-time bounds as declared
  deterministic operation counts (no wall clock), cross-plane reconciliation
  (contracts/journal/evidence planes converge with typed divergence records),
  recovery never fabricates history (recovered records preserve their original
  content-derived identities — LOCK-106; no historical record rewritten), and
  fail-closed recovery (an unverifiable snapshot is rejected, never partially
  trusted). Dependencies: M015, M016.

### M018 — Credential and Key Lifecycle Operations

- **Scope:** `credentials/` (NEW), `tools/credential_selftest.py` (NEW
  battery), `docs/M018-evidence.md`.
- **Acceptance criteria:** the operational credential-lifecycle domain over
  the accepted M014 identity/federation authorities BY REFERENCE — rotation
  drills with zero coverage gaps (no operation window in which a revoked
  credential is still admitted; the admitted-set transition is atomic and
  journaled), revocation propagation as deterministic rounds with declared
  convergence bounds, emergency revocation paths that are explicit and
  evidence-visible, credential inventory verification (every admitted
  credential traces to a valid lifecycle record), key material never stored,
  logged, or echoed (LOCK-119 — fixtures assembled from fragments), and the
  admission gate consumed BY REFERENCE from the accepted `client/`/`federation/`
  surfaces (no second authorization runtime — LOCK-117). Chain-independent:
  branches from the accepted R7 state (M014), not from the M015-M017 chain.

### M019 — Resilience Convergence and Scale Hardening (the convergence child)

- **Scope:** `resilience/` (the convergence module — the M015-owned prefix,
  shared), `tools/scale_selftest.py` (disclosed evolution, the M014 precedent),
  `docs/M019-evidence.md`.
- **Acceptance criteria:** the R8 convergence surface — every R8 child
  authority consumed BY REFERENCE (the M014 discipline), the end-to-end
  resilience drill (deterministic fault injection across the full accepted
  surface: fault → detect → replan/failover → recover → reconcile, with every
  hard constraint preserved at each step and every transition evidence-
  visible), the converged-domain compatibility matrix extended over the R8
  domains (the accepted `upgrade/` matrix discipline extended, input-order
  independent, byte-stable digests), federation-scale convergence over the R8
  domains (the accepted `scale/` harness discipline extended), and the R8 gate
  completion review composed from repository evidence. Acceptance is blocked
  until M015-M018 are accepted; parallel preparation is permitted but never
  falsely claimed as acceptance.

## Migration policy

Architecture 1.0 material is a migration reservoir, never forward design
authority. The frozen classification matrix governs RETAIN / REFACTOR / DEMOTE /
REPLACE / ARCHIVE per area; the R8 children harvest the reservoir's resilience
disciplines (WORK-012 explicit reconnect, WORK-035 handover, multipath failover,
edge/appliance operational patterns) as SOURCE MATERIAL only, re-expressing them
on the accepted 1.1 authorities. Historical acceptance evidence is never
rewritten. W048 stays accepted-not-restored (its surfaces are forbidden
dependencies). The era-superseded batteries are re-baselined under their
assigned children, visibly, never silently.

## Evidence policy

Per-child acceptance requires deterministic, offline, reproducible SOFTWARE
evidence (the child battery plus lock-conformance assertions in the evidence
doc). Simulation and emulation are SOFTWARE-class. No battery or evidence doc
may convert software evidence into PHYSICAL PASS. The open physical obligations
EVID-002..EVID-008 are unaffected by this charter and remain visible in every
current-state projection. Acceptance decisions record the exact reviewed
delivery head and merge SHA.

## Worker policy

The Tech Lead owns decomposition, dispatch, branching, integration, testing and
verification, bounded by `docs/tech-lead/worker-model.md` and the
machine-checked `docs/tech-lead/dispatch-state.yaml` (≤3 direct workers; ≤3
subagents per worker; ≤9 active descendants; depth ≤2). Recommended R8
allocation: Worker A — the M015 → M016 → M017 resilience chain; Worker B — M018
(chain-independent); Worker C — M019 convergence preparation. Parallelism only
across dependency- and authority-independent scopes; integration and normative
conformance remain Tech Lead controlled.

## Acceptance rules (Architect side, per child)

1. The delivery PR classifies as implementation-only under
   `tools/architecture_drift_guard.py` (no control-plane mixing).
2. Every implementation file in the delta is covered by the active R8-CORE-001
   scope (`tools/authorization_provenance.py`, the current-era ARCH-08
   successor gate).
3. The child battery and the full existing battery suite are green on the
   delivery head (implementation-only deltas run the blocking battery set).
4. The evidence doc (`docs/M01x-evidence.md`) records the verification matrix,
   lock-conformance mapping, and any disclosed deviations.
5. The sole Architect reviews the exact head against this charter and records a
   durable acceptance decision (exact reviewed SHA + merge SHA); execution-state,
   roadmap and ledger are reconciled to the merge; the child advances the
   dependency chain.

## Out of scope (whole tranche)

- Any control-plane surface (`spec/`, `.github/`, `AGENTS.md`, `README.md`,
  `docs/tech-lead/`, the drift-guard CONTROL_FILES) — those change only through
  governance decisions, never through implementation PRs.
- `spec/mission.md`, protocol/wire semantics (Protocol Version 1.0 frozen
  without an accepted ACR), `containment/`/`sharing/` (WORK-048
  accepted-not-restored), `pilot/` (WORK-040 physical track).
- Rewriting or deleting historical acceptance records, ledger entries, or
  archived 1.0 content; modifying the frozen 1.1 successor registry
  (`spec/work-items.md`) or dependency graph.
- Converting SOFTWARE evidence into PHYSICAL PASS; disturbing EVID-001 closure
  or EVID-002..EVID-008 visibility.
- Any R9 (Future Access Technology) surface — access-technology additions stay
  behind the adapter boundary and are the next gate's scope, not this
  tranche's.
