# R9 — Future Access Technology — Implementation Charter

**Gate-specific Work Item contract (DEC-0120 governance-compression class, the DEC-0101/DEC-0114 precedent).**
**Authorization: R9-CORE-001 (bounded R9 program authorization, DEC-0120). Baseline: `ea4bb64e0d32cfe93384ece71ec0003f447e357f`.**
**Status: ACTIVE — the R9 gate is the current program gate (the terminal roadmap gate); M020 — Access Technology Capability Envelope is the current child. R8 — Resilience, Mobility and Scale is COMPLETE under DEC-0119 (all five children accepted; the R8-CORE-001 program authorization closed). Per-child acceptance decisions (DEC-0121+) are mandatory.**

## Objective

Add or replace access technologies through the adapter boundary without
altering the connectivity contract core — delivered as the gate-specific
execution units M020-M024 consuming the accepted R7 and R8 authorities BY
REFERENCE (the M014/M019 convergence discipline: no accepted authority
reimplemented, weakened, forked, or bypassed). R9 is the TERMINAL roadmap
gate: its completion (the M024 convergence child) evaluates the program_exit
conditions (the stripe-of-connectivity test and the architecture test).

## Purpose of this charter (governance compression)

This ONE charter replaces the per-work-item pre-implementation paperwork chain
for the R9 gate, exactly as the R7 and R8 charters did under DEC-0101 and
DEC-0114. Under DEC-0120:

- **One** R9 program authorization (`R9-CORE-001`,
  `spec/architect/authorizations/R9.yaml`) is active for the whole tranche,
  with **child work-item scopes** declared below.
- The **Tech Lead** may decompose, dispatch (≤3 direct workers, ≤3 subagents
  each, ≤9 descendants, depth 2 per `docs/tech-lead/dispatch-state.yaml`),
  branch, integrate, test and deliver PRs against any already-authorized child
  scope **without a new pre-implementation authorization ceremony**.
- **Per-M-item acceptance remains mandatory** and is the sole Architect-side
  gate: each child is accepted only from repository evidence (deterministic
  battery, lock conformance, provenance, review) via a durable acceptance
  decision (DEC-0121, DEC-0122, … — one per child).
- At most **one** implementation authorization is active at any time (the R9
  program authorization), preserving the standing authority-uniqueness invariant.
- The R9 children are **gate-specific execution units** introduced by this
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
adapter, provider, envelope, technology descriptor, or handover record may become
a second contract authority. Access technologies enter the system ONLY through
the accepted adapter boundary (`adapters/capability.py`, the M007 LOCK-110/LOCK-112
surface) and are named by the canonical execution bridge (`executionplans/`, the
M006 LOCK-109 surface) — never by the contract core. This is the gate's own
objective constraint, enforced as an acceptance criterion on every child.

## Consumption rule (the R9 access-technology discipline)

Every R9 child consumes the accepted R7/R8 authorities (`contracts/`, `offers/`,
`eligibility/`, `policy/`, `evidence/`, `assurance/`, `executionplans/`,
`adapters/`, `replan/`, `usage/`, `commercial/`, `allocation/`, `payment/`,
`sharenet/`, `roamlink/`, `comos/`, `developerapi/`, `federation/`, `identity/`,
`upgrade/`, `scale/`, `client/`, `resilience/`, `localfirst/`, `recovery/`,
`credentials/`) **BY REFERENCE** — import and compose, never reimplement,
weaken, fork, or bypass. Access-technology work adds technology descriptors,
envelopes, and reference adapter compositions AROUND those authorities; it
never edits them (a disclosed evolution of an accepted shared battery surface
follows the M019 `tools/scale_selftest.py` precedent — disclosed, append-only
in intent, never assertion-weakening). The accepted adapter family runtimes
(`adapters/backhaul/`, `adapters/fivegc/`, `adapters/ip/`, `adapters/mesh/`,
`adapters/ran/`, `adapters/wifi/`) are composition substrates for the new
reference modules, exactly as M007 composed them. The legacy 1.0 reservoir
(`imt/`, `transport/`, `topology/`, `networkpath/`, `resources/`, `services/`,
`edge/`, `appliance/`, `mobile/`, `management/`, `simulator/`) is harvest
material per the frozen migration classification matrix — never forward design
authority.

## Child work-item scopes and acceptance criteria

Each child carries: (a) its declared scope (the authorization covers exactly
these prefixes plus the shared battery surface), (b) acceptance criteria
evaluated at acceptance time, (c) a deterministic battery as SOFTWARE evidence.
Scope prefixes outside the declared list require a lightweight charter
**scope-amendment decision** recorded in the decisions registry — not a
re-authorization ceremony.

### M020 — Access Technology Capability Envelope — the current child

- **Scope:** `accesstech/` (NEW — the access-technology envelope domain),
  `tools/accesstech_selftest.py` (NEW battery), `docs/M020-evidence.md`, plus
  the shared battery surface (`tools/`, the authorization-aware consultation
  repairs).
- **Acceptance criteria:** the typed technology-envelope surface on the
  canonical authority — declared capability envelopes per technology class
  (typed deterministic ranges over the capability dimensions: bandwidth,
  latency, jitter, availability windows; canonical-JSON serializable,
  content-derived identities per LOCK-106), degradation ladders composed from
  the accepted `resilience/` realization-state vocabulary (the M008-owned
  `REALIZING/DEGRADED/FAILED/SUPERSEDED` kernel extended without redefining
  it), handover characteristic declarations consumed BY REFERENCE from the
  accepted `resilience/` handover machinery (LOCK-108 constraint preservation
  declared per handover kind), deterministic fail-closed envelope validation
  (inconsistent, degenerate, or contradictory envelopes are typed rejections,
  never warnings), and the technology-extension registration surface: the exact
  declared path by which a new access technology (envelope + reference adapter
  composition + capability statement) registers through the accepted
  `adapters/capability.py` seam and the `executionplans/` bridge with ZERO
  contract-core delta (LOCK-101/LOCK-105/LOCK-109/LOCK-110/LOCK-112). The
  extension surface MUST be proven by registering the EXISTING accepted
  families (the M007 six) through it. Deterministic, offline, seeded; no wall
  clock, no randomness, no network; secrets never stored (LOCK-119);
  canonical-JSON round-trips; battery green; evidence doc records the
  verification matrix. Imports flow one way: `accesstech/` may import the
  accepted authorities; no accepted authority imports `accesstech/`.

### M021 — Wireline Access Adapters (chain child: requires M020)

- **Scope:** `adapters/reference/wireline.py` (NEW — the wireline reference
  compositions), `tools/wireline_selftest.py` (NEW battery),
  `docs/M021-evidence.md`, plus envelope declarations under `accesstech/`
  (the M020-owned shared prefix).
- **Acceptance criteria:** Ethernet/fiber and enterprise-WAN access families
  as reference adapter compositions on the M020 envelope — composing the
  accepted `adapters/backhaul/` family runtime (the IEEE 802.3/802.1Q/ITU-T
  G.709 standards base) BY REFERENCE through the accepted
  `adapters/capability.py` seam (LOCK-112: the families model the standard
  mechanisms; LOCK-110: provider-SDK types never enter the core); wireline
  capability envelopes with static-availability semantics (no mobility;
  degradation ladders are declared capacity steps, each an explicit
  evidence-visible transition); deterministic reserve/activate/measure flows
  through the nine WORK-016 operations with the deterministic re-bind
  translation for mid-session reconfiguration; declared enterprise-WAN
  site-topology expressed as declared data only (LOCK-105 — never global
  topology). Battery green; evidence doc records the verification matrix.

### M022 — Non-Terrestrial Access Adapters (chain child: requires M020, M021)

- **Scope:** `adapters/reference/satellite.py` (NEW — the non-terrestrial
  reference compositions), `tools/satellite_selftest.py` (NEW battery),
  `docs/M022-evidence.md`, plus envelope declarations under `accesstech/`
  (the M020-owned shared prefix).
- **Acceptance criteria:** satellite (GSO/NGSO/LEO) and mesh/IAB non-terrestrial
  access families as reference adapter compositions on the M020 envelope —
  deterministic coverage windows (declared availability intervals, injected
  instants, never wall clock), propagation-delay envelopes as typed declared
  ranges, NGSO pass-handover geometry as deterministic declared events composed
  through the accepted `resilience/` handover machinery (LOCK-108: verbatim
  constraint-set equality across every pass handover; the WORK-012 explicit
  recorded reconnect discipline — every pass transition an explicit recorded
  reconnect event naming old AND new references), the mesh/IAB extension
  composing the accepted `adapters/mesh/` family runtime BY REFERENCE
  (sidelink relay + DTN store-and-forward semantics on the envelope), and
  degradation ladders with propagation-aware declared margin steps. Battery
  green; evidence doc records the verification matrix.

### M023 — Future Technology Extension Drill (chain-independent: from the accepted R8-complete state)

- **Scope:** `adapters/reference/futureimt.py` (NEW — the synthetic
  future-IMT/6G-class reference composition), `tools/futureimt_selftest.py`
  (NEW battery), `docs/M023-evidence.md`.
- **Acceptance criteria:** the extension drill — a synthetic future-IMT/6G-class
  access technology the 1.1 architecture never named, added ENTIRELY through
  the accepted public extension surface: the composition registers through the
  accepted `adapters/capability.py` seam, is bridged by the accepted
  `executionplans/` LOCK-109 surface, is offered through the accepted
  `offers/`/`capabilities/` exchange, and is admitted by the accepted
  `eligibility/`/`policy/` gates — with ZERO contract-core delta (the diff
  touches only the declared scope). The drill harvests the legacy `imt/`
  reservoir as SOURCE MATERIAL ONLY (per the frozen migration matrix),
  re-expressing its future-IMT capability semantics on the accepted authority;
  it MUST NOT import 1.0 material as forward design authority. Chain-independent:
  branches from the accepted R8-complete state (the DEC-0119 acceptance head
  `ea4bb64`), not from the M020-M022 chain; may be accepted in any order
  relative to them (the M013/M018 precedent class). Its battery MUST include
  the zero-core-delta assertion (the contract core's bytes unchanged by the
  registration).

### M024 — Future Access Convergence (the convergence child: requires M020+M021+M022+M023 — its acceptance completes the R9 gate)

- **Scope:** `accesstech/` (the convergence module — the M020-owned prefix,
  shared), `tools/accessconvergence_selftest.py` (NEW battery — the CI step
  wired with a pre-delivery existence guard at the M023 acceptance, the
  DEC-0116/DEC-0117 wiring precedent), `docs/M024-evidence.md`.
- **Acceptance criteria:** the R9 convergence surface — every R9 child
  authority consumed BY REFERENCE (the M014/M019 discipline); the
  cross-technology interchange drill (deterministic technology handovers
  wireline ↔ radio-family ↔ non-terrestrial with LOCK-108 verbatim
  constraint-set equality at every step, driven through the accepted
  `resilience/` handover machinery); the technology REPLACEMENT drill (the
  "or replace" half of the gate objective: a live technology replaced by
  another under an active contract with contract continuity — every replacement
  an explicit recorded reconnect naming old AND new references, never a silent
  swap); the converged-domain compatibility matrix extended over the R9 domains
  (the accepted `upgrade/` matrix discipline extended, input-order independent,
  byte-stable digests); federation-scale convergence over the R9 domains (the
  accepted `scale/` harness discipline extended); and the R9 gate completion
  review composed from repository evidence, evaluating the program_exit
  conditions (the stripe-of-connectivity test and the architecture test)
  against the completed program state — SOFTWARE-class evaluation only, never
  converting software evidence into PHYSICAL PASS. Its acceptance as DEC-0124
  completes the R9 gate and the roadmap's gate sequence (the terminal gate).

## Migration policy

Architecture 1.0 material is a migration reservoir, never forward design
authority. The frozen classification matrix governs RETAIN / REFACTOR / DEMOTE /
REPLACE / ARCHIVE per area; the R9 children harvest the reservoir's
access-technology disciplines (the `imt/` future-technology modeling, the
`transport/`/`topology/` technology abstraction vocabulary, the WORK-018..023
standards boundaries) as SOURCE MATERIAL only, re-expressing them on the
accepted 1.1 authorities. Historical acceptance evidence is never rewritten.
W048 stays accepted-not-restored (its surfaces are forbidden dependencies).
The era-superseded batteries are re-baselined under their assigned children,
visibly, never silently.

## Evidence policy

Per-child acceptance requires deterministic, offline, reproducible SOFTWARE
evidence (the child battery plus lock-conformance assertions in the evidence
doc). Simulation and emulation are SOFTWARE-class. No battery or evidence doc
may convert software evidence into PHYSICAL PASS. The open physical obligations
EVID-002..EVID-008 are unaffected by this charter and remain visible in every
current-state projection (the M024 program-exit evaluation records them as
open, never satisfied). Acceptance decisions record the exact reviewed
delivery head and merge SHA.

## Worker policy

The Tech Lead owns decomposition, dispatch, branching, integration, testing and
verification, bounded by `docs/tech-lead/worker-model.md` and the
machine-checked `docs/tech-lead/dispatch-state.yaml` (≤3 direct workers; ≤3
subagents per worker; ≤9 active descendants; depth ≤2). Recommended R9
allocation: Worker A — the M020 → M021 → M022 envelope/adapter chain; Worker
B — M023 (chain-independent, dispatchable immediately from the accepted
baseline); Worker C — M024 convergence preparation (after its dependencies
land). Parallelism only across dependency- and authority-independent scopes;
integration and normative conformance remain Tech Lead controlled.

## Acceptance rules (Architect side, per child)

1. The delivery PR classifies as implementation-only under
   `tools/architecture_drift_guard.py` (no control-plane mixing).
2. Every implementation file in the delta is covered by the active R9-CORE-001
   scope (`tools/authorization_provenance.py`, the current-era ARCH-08
   successor gate).
3. The child battery and the full existing battery suite are green on the
   delivery head (implementation-only deltas run the blocking battery set).
4. The evidence doc (`docs/M02x-evidence.md`) records the verification matrix,
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
  or EVID-002..EVID-008 visibility; the M024 program-exit evaluation is
  SOFTWARE-class and records the open physical obligations as open.
- Any change to the contract core (`contracts/`) or any accepted authority —
  the gate's own objective constraint: access technologies are added or
  replaced through the adapter boundary WITHOUT altering the connectivity
  contract core. A delivery that must touch an accepted authority surfaces a
  lightweight scope-amendment decision FIRST (never a fait-accompli delta).
