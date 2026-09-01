# ACR-011: Extend the Work Item Registry Through the Canonical Commercial Phase

## Status

PROPOSED — awaiting Architect review (`spec/change-control.md` §7; approval is
never implied by silence, inaction, or a passing CI run).

This ACR and its synchronized updates travel in one governance PR as the
atomic proposal vehicle (`spec/change-control.md` §3 element 8): the frozen
registry extension, the machine-checked expectation updates, and the
persistent-state synchronization take effect only when the Architect merges
the PR. Until that merge, the current architecture snapshot remains
authoritative and unchanged on `main`. Proposal vehicle: PR #111.

## Motivating experience / research

The limitation is machine-checked, durable, and reproducible from the
repository alone:

1. **WORK-042 is delivered and merged but unrepresentable.** The W042
   implementation PR #110 is MERGED (head `708a432`, merge `207d70e`,
   authoritative CI run 33444952103 SUCCESS on the head, merged by the
   Architect 2026-08-31T22:54:17Z; the push-run on the merge commit,
   33448347826, also SUCCESS). Yet WORK-042 is absent from the frozen
   registry: `spec/work-items.md` terminates at `### WORK-041`, and the
   repository's own persistent state records — in `execution-state.yaml`,
   `current-state.md`, the Phase 9 narrative of `spec/work-items.md`, and
   `WORK-042-CORE-001`'s authorization record itself — that "WORK-042 is NOT
   registered in the frozen backlog (its own governance registration issues
   separately)".
2. **The validator couples acceptance to registration.** `BACKLOG-01`
   requires the backlog to be exactly `WORK-001..WORK-041` gap-free; the
   execution-ledger validation requires the ledger Work Item set to equal
   `{"WORK-001".."WORK-041"}` exactly; `DEPS-01` requires every DAG node to
   resolve to a known Work Item; and the expected count is synchronized in
   `tools/spec_check.py`. A future WORK-042 acceptance decision
   (`DEC-NNNN`) therefore cannot be recorded — the required ledger entry
   would be rejected as an unknown Work Item until the registry is extended
   first.
3. **W041 already exposed this once.** The identical boundary appeared at
   W041 completion: ACR-010 (PR #108) was proposed to extend the registry
   from 40 to 41 and was then superseded by the DEC-0054/DEC-0055 transition
   (LEDGER-RECON-006), which applied the registry extension directly as the
   mechanical prerequisite of recording the W041 acceptance. The pattern is
   now established: **every** future Work Item acceptance hits the same wall
   and needs its own registry change first.
4. **The whole next phase is already durably planned.** The canonical
   commercial dependency model (`docs/roadmap/commercial-dependency-model.md`,
   reconciled by LEDGER-RECON-005 under DEC-0050/0051/0052/0053) defines the
   complete post-W042 phase: the commercial chain W051 → W052 → W053, the
   commercial periphery W044–W047, the capability/isolation matrix W050, the
   sharing runtime W048, and the client runtime W049 — with WORK-043 retired
   from commercial use and left unassigned. `execution-state.yaml`'s
   `planned_work_items` already carries every one of these as a
   ready-candidate with `authorization: "none"`.
5. **W043's retirement is the first intentional ID gap.** The registry
   convention (LEDGER-RECON-005 §4) retires WORK-043 permanently — never
   reused, never renumbered — so no future reader can bind the superseded
   commercial-era "W043" label to a live artifact. The current `BACKLOG-01`
   gap-free semantics cannot represent a retired slot at all: registering
   WORK-042 and WORK-044..WORK-053 without WORK-043 would fail every
   gap-integrity check. Representing retirement deliberately requires an
   explicit, machine-checked retired-slot mechanism — not a weakening of the
   gap checks.

This is precisely the situation `spec/change-control.md` §4 rule 3 requires
to be resolved by an ACR: the frozen registry and the machine-checking
system are internally consistent at 41 items, but they cannot represent the
duly delivered W042, the durably planned commercial phase, or the recorded
W043 retirement. Weakening the checks or creating an out-of-band
representation path would be the wrong response.

## Proposed change

Authorize a synchronized, deliberate extension of the architectural Work
Item registry from 41 to **52 registered items** — `WORK-001..WORK-042` plus
`WORK-044..WORK-053`, with `WORK-043` retired (slot vacant by record) — so
the next architectural/program phase is machine-representable **without a
new registry ACR after every Work Item**. The extension is additive: every
existing `WORK-001..WORK-041` definition, edge, phase membership, and ledger
entry is preserved byte-identically, and no Work Item authorization is
created, activated, superseded, or modified. The synchronized changes
carried by this ACR's proposal vehicle are:

1. `spec/work-items.md` — register `WORK-042 — Event-Driven Platform
   Integration and Journal-First Recovery` in Phase 9 (definition taken from
   the canonical W042 contract `spec/architect/work-items/WORK-042.md`,
   authorization `WORK-042-CORE-001`, tracking issue #69, ACR-006/DEC-0048),
   and register the canonical commercial phase under a new
   `# Phase 10 — Canonical commercial phase`:
   `WORK-051`, `WORK-052`, `WORK-053`, `WORK-044`, `WORK-045`, `WORK-046`,
   `WORK-047`, `WORK-050`, `WORK-048`, `WORK-049` (definitions taken from
   the canonical commercial dependency model and the tracking issues
   #83/#84/#85/#88/#89/#90/#91/#92/#96/#98). WORK-043 is NOT registered: it
   remains retired from commercial use and unassigned per LEDGER-RECON-005.
   `WORK-001..WORK-041` blocks are byte-identical.
2. `spec/dependency-graph.md` — add the nodes `W042`, `W044..W053` and the
   canonical dependency edges derived from
   `docs/roadmap/commercial-dependency-model.md` §2 (listed exhaustively in
   the Work-item and dependency impact section below); extend Phase 9 with
   `W042`; add `### Phase 10 — Canonical commercial phase`; and synchronize
   the §8 completion-criterion wording from "all 41 Work Items" to "all 52
   Work Items". The critical path is unchanged.
3. `tools/spec_check.py` — synchronized machine-checked expectations, with
   every existing check's semantics preserved:
   - `EXPECTED_WORK_ITEM_COUNT` 41 → 52 (the registered-item count) and a
     new explicit `RETIRED_WORK_ITEM_IDS = {"WORK-043"}` constant: the ONLY
     sanctioned gap in the WORK-NNN sequence, recorded durably so that any
     other gap, duplicate, count drift, or revival of WORK-043 still fails
     closed exactly as before;
   - the execution-ledger lifecycle vocabulary gains one value,
     `registered`, for frozen-registry Work Items with **no delivery yet** —
     fail-closed rules require branch/pr and every delivery/review field to
     be null for `registered` entries (a fabricated delivery can never enter
     the ledger as a "registered" item), while every delivery lifecycle
     keeps requiring branch/pr exactly as before;
   - the ledger set-equality is preserved (not weakened to a subset): the
     ledger must account for exactly the 52 registered items.
4. `spec/architect/execution-ledger.yaml` — append the WORK-042 delivery
   entry (lifecycle `implemented`: PR #110 merged facts recorded;
   `acceptance_decision: null`, `reviewed_sha: null`) exactly per the
   LEDGER-RECON-004/006 convention (a ledger entry is added once the Work
   Item has a delivery PR and is registered in the frozen registry), and
   append `registered` entries for WORK-044..WORK-053 (no delivery facts;
   authorization none). This makes the W042 delivery and the whole
   commercial phase machine-representable WITHOUT accepting anything.
5. `spec/architect/execution-state.yaml` — open ACRs list gains ACR-011
   (PROPOSED, vehicle PR #111), the halted_reason records the W042 delivery
   merge and this ACR, next_required_decisions is refreshed (decide ACR-011;
   render the W042 acceptance review; evaluate the next authorization), and
   the planned WORK-042 entry records its delivery facts. The snapshot
   baseline `main_sha` is deliberately NOT moved by this ACR (ACR-010
   precedent); the next reconciliation moves it per the standing RECON
   convention.
6. `spec/architect/current-state.md` and `spec/acr/README.md` — narrative
   reconciliation and registry listing only.
7. `docs/governance/ACR-011-commercial-phase-registry-reconciliation.md` —
   the evidence/reconciliation document (validation results, byte-identity
   proofs, DAG audit, negative tests, authority audit).

No acceptance, no authorization, no supersession, and no W042 lifecycle
transition beyond `implemented` is performed by this ACR: WORK-042's
acceptance remains a separate future Architect decision per
review-protocol §5, and WORK-051..WORK-053, WORK-044..WORK-050 remain
ready-candidates with `authorization: "none"` until their own
repository-local authorizations issue.

Alternatives considered and rejected:

- **Weaken or bypass the count/ledger/gap checks** (e.g., relax the ledger
  set-equality to a subset, or drop the gap check): rejected because it
  would weaken ARCH-02/03/04/05/08 discipline, silently redefine the frozen
  register, and convert a governance boundary into a checker bug. The
  retired-slot mechanism below is additive and fail-closed, not a bypass.
- **Register WORK-042 only** (the literal W041/ACR-010 pattern): rejected
  because the very next phase (W051 CommercialCore authorization and
  acceptance) would hit the identical wall, requiring yet another registry
  ACR — the compounding the user of this change wants ended — and because
  W043's retirement would still be unrepresentable.
- **Revive WORK-043** (renumber EconomicAllocation back into the 43 slot):
  rejected because LEDGER-RECON-005 deliberately retired the label so no
  future reader can bind the superseded commercial-era "W043" to a live
  artifact; reviving it would rewrite decided history and violate the
  no-renumber registry convention.
- **Declare WORK-050 a hard dependency of WORK-048/WORK-049**: rejected
  because the canonical model records W050 as "capability declarations
  constrain sharing modes; advisory input, **not a gate**". Declaring it in
  the `Dependencies:` lines would invent a hard gate (a W048/W049 review
  could be blocked on W050's acceptance through ARCH-05's in-review
  dependency readiness). The W050 → W048/W049 edges are represented in the
  DAG with their advisory semantics stated in the Phase 10 narrative, and
  the resulting ADV-01 advisory lines (DAG edge not declared as a hard
  dependency) are explicitly sanctioned by this ACR.
- **Accept W042 or activate W051 inside this ACR**: rejected as scope creep;
  acceptance and authorization are separate Architect decisions with their
  own decision records (this ACR registers representation only).
- **Record W042 delivery out-of-band** (chat acceptance without a ledger
  entry or registration): rejected because PA-001/DEC-0045 and the
  persistent Architect package exist precisely so durable state never
  depends on ephemeral chat; an unrepresentable acceptance is not an
  acceptance.

## Mission consistency

The registry extension preserves the permanent Mission Authority
(`spec/mission.md`) untouched. The registered commercial Work Items
implement the already-accepted ACR-009 commercial control-plane direction
(DEC-0050) — economic/commercial mechanisms are an explicitly
mission-revisable layer ("What is intentionally revisable …
economic/commercial mechanisms"), and registering them changes only how the
repository's frozen planning documents represent architectural execution
units the Architect has already accepted the *direction* of. WORK-042
implements the already-accepted ACR-006 direction. Nothing below the mission
is redefined: the architecture snapshot's semantics, the 25 locks, the
dependency semantics, and the authority ownership are all preserved.

## Affected architecture sections and locks

- `spec/architecture.md` sections: **none** — the document is not modified
  (consistent with ACR-005/006/007/009/010, which record accepted direction
  in `spec/acr/` without altering the architecture snapshot).
- `LOCK-XXX` identifiers: **none modified** — `LOCK-001..LOCK-025` are
  preserved unchanged. In particular LOCK-016/LOCK-017 (provider isolation,
  no vendor authority — the commercial phase's contracts honor them),
  LOCK-023 (no secret leakage), LOCK-005/LOCK-006 (identity/session
  independence), LOCK-021 (mobility is session-level) are unaffected.
- Frozen documents modified (additive registration only):
  `spec/work-items.md`, `spec/dependency-graph.md`.
- Machine-checked tooling: `tools/spec_check.py` (count 41 → 52; explicit
  retired-slot set; `registered` ledger lifecycle with fail-closed rules).
- Persistent governance state (synchronization, not semantics):
  `spec/architect/execution-ledger.yaml`, `spec/architect/execution-state.yaml`,
  `spec/architect/current-state.md`, `spec/acr/README.md`.
- Supporting evidence document (new):
  `docs/governance/ACR-011-commercial-phase-registry-reconciliation.md`.

## Compatibility analysis

- **Wire compatibility**: no change. No protocol message, schema, envelope,
  or registry file under `spec/schemas/` is touched.
- **Persisted state / live sessions / federation**: no change. The ACR
  modifies governance documents and checker expectations only; no runtime
  code is modified (verified by the PR diff: no implementation files
  change; ARCH-08 classifies the delta as governance/meta-only).
- **Existing deployments and mixed-version operation**: no impact. The
  repository remains checkable offline by the same commands; a pre-ACR-011
  clone simply reports the old 41-item expectation, which is historical,
  not a compatibility break.
- **Machine-check effects** (the discriminating verification for this ACR):
  `BACKLOG-01` now expects exactly the 52 registered IDs with exactly the
  recorded WORK-043 gap and rejects every other gap, duplicate, or revival;
  the execution-ledger set-equality now requires the WORK-042 entry
  (present, lifecycle `implemented`) and the ten `registered` entries;
  `DEPS-01..03` still pass (all references resolve, the graph is acyclic
  with the 30 new edges, phases remain sequential 0–10, the critical path is
  coherent); `ADV-01` gains exactly two ACR-sanctioned advisory lines for
  the deliberately undeclared W050 advisory edges; `ARCH-02` parses the
  extended ledger; `ARCH-03`'s single-active-authorization invariant is
  untouched (`WORK-042-CORE-001` remains the sole active authorization,
  baseline `96db8aa` matching the recorded snapshot baseline, and its
  dependency list matches WORK-042's frozen declaration exactly);
  `ARCH-04/05/06/07` hold; `ARCH-08` fail-closed provenance is unchanged
  (governance-only deltas still pass; implementation deltas still require an
  inherited active authorization).
- **Acceptance semantics**: unchanged for every Work Item. W042 is
  registered as delivered-and-merged but NOT accepted
  (`acceptance_decision: null`, `reviewed_sha: null`, lifecycle
  `implemented`); its acceptance remains a separate future Architect
  decision recorded per review-protocol §5. W001–W039 remain
  accepted-merged; W041 remains accepted-merged; W040 remains in-review
  with EVID-007/EVID-008 OPEN and W040-owned. W044–W053 are registered with
  `authorization: "none"` — registration is not authorization, and the
  one-active-Work-Item rule is untouched.

## Work-item and dependency impact

- Registered Work Items (11 new; all definitions additive):
  - `WORK-042 — Event-Driven Platform Integration and Journal-First
    Recovery` (Phase 9) — ACR-006/DEC-0048, contract
    `spec/architect/work-items/WORK-042.md`, tracking issue #69,
    authorization WORK-042-CORE-001 (the currently active one), delivery
    merged by PR #110. Declared dependencies (exactly the authorization
    record's list, so ARCH-03's frozen-declaration match holds):
    `WORK-012`, `WORK-013`, `WORK-014`, `WORK-033`, `WORK-035`,
    `WORK-041` — all Architect-accepted and merged.
  - `WORK-051 — CommercialCore: connectivity intent, offers, reservation,
    lease, and transaction lifecycle` (Phase 10) — ACR-009/DEC-0050, issue
    #83. Dependencies: none (chain head; ACR-009 accepted is its
    architectural precondition, not a Work Item dependency).
  - `WORK-052 — UsageLedger: delivered-usage metering, billable finality,
    and append-only reconciliation` (Phase 10) — issue #84. Dependencies:
    `WORK-051` (interfaces consumed).
  - `WORK-053 — EconomicAllocation: developer/provider/ADCOS revenue-share
    policy and external payment boundary` (Phase 10) — issue #85.
    Dependencies: `WORK-052` (billable-final facts consumed).
  - `WORK-044 — Payment Provider Adapters & Settlement Gateway`
    (Phase 10) — issue #88. Dependencies: `WORK-051`, `WORK-053`
    (settlement states interfaced).
  - `WORK-045 — Connectivity Eligibility, Provider Trust & Jurisdiction
    Policy` (Phase 10) — issue #89. Dependencies: `WORK-051`, `WORK-053`,
    `WORK-044` (commercial + payment capability boundaries consumed).
  - `WORK-046 — Developer Connectivity API, SDK & Webhook Platform`
    (Phase 10) — issue #90. Dependencies: `WORK-051`, `WORK-052`,
    `WORK-053`, `WORK-044`, `WORK-045` (surfaces the commercial plane).
  - `WORK-047 — Connectivity Marketplace Discovery, Proximity & Path
    Selection` (Phase 10) — issue #91. Dependencies: `WORK-051`, `WORK-044`,
    `WORK-045`, `WORK-046` (presents paid, eligible, API-visible offers).
  - `WORK-050 — Platform Connectivity Sharing Capability & Isolation
    Matrix` (Phase 10) — issue #96. Dependencies: none (capability model
    consumed BY W048/W049; not an implementation vehicle for W048).
  - `WORK-048 — Provider Connectivity Sharing Runtime, Isolation & Quota
    Enforcement` (Phase 10) — issue #92 (design-only PR #97 exists).
    Dependencies: `WORK-041`, `WORK-042`, `WORK-051` (the hard interface
    dependencies the canonical model records: NetworkPath lifecycle,
    usage/journal discipline, commercial Lease authority). W050 is NOT
    declared: its capability declarations are advisory input, not a gate.
  - `WORK-049 — Provider & Buyer Connectivity Client Runtime` (Phase 10) —
    issue #98 (canonical; issue #95 is the superseded duplicate
    definition). Dependencies: `WORK-046`, `WORK-047`, `WORK-048`
    (handoffs to each canonical authority). W050 is NOT declared, same
    advisory rule.
  - `WORK-043`: NOT registered — retired from commercial use and left
    unassigned (LEDGER-RECON-005 §4); its slot is represented by the
    machine-checked retired set in `tools/spec_check.py`.
- Dependency graph recalculation (`spec/dependency-graph.md` rule 5) —
  30 edges added, all derived from the canonical commercial dependency
  model §2 ("Genuine interface dependencies"):
  - WORK-042 (6): `W012 → W042`, `W013 → W042`, `W014 → W042`,
    `W033 → W042`, `W035 → W042`, `W041 → W042`.
  - Commercial chain (2): `W051 → W052`, `W052 → W053`.
  - Commercial periphery, hard (17): `W051 → W044`, `W053 → W044`,
    `W051 → W045`, `W053 → W045`, `W044 → W045`, `W051 → W046`,
    `W052 → W046`, `W053 → W046`, `W044 → W046`, `W045 → W046`,
    `W051 → W047`, `W044 → W047`, `W045 → W047`, `W046 → W047`,
    `W051 → W048`, `W041 → W048`, `W042 → W048`.
  - Client runtime (3): `W046 → W049`, `W047 → W049`, `W048 → W049`.
  - Advisory capability input (2, deliberately NOT declared as hard
    dependencies): `W050 → W048`, `W050 → W049`.
  The graph remains acyclic (verified mechanically: DEPS-02 on the union of
  DAG edges and declared dependencies). W042 is a new sink of Phase ≤ 9
  items; the commercial nodes form the Phase 10 stratum; no edge is removed
  or relabeled.
- Execution phases: Phase 9 gains `W042` (after `W041`); a new
  `### Phase 10 — Canonical commercial phase` is appended with the member
  order `W051, W052, W053, W044, W045, W046, W047, W050, W048, W049` — a
  topological order of the Phase 10 subgraph, so `DEPS-03`'s intra-phase
  ordering holds for every new edge. Phases remain sequential 0–10.
- Critical path: unchanged (terminating at W040). Phase 9 and Phase 10 are
  governed-evolution/commercial tracks, not dependencies of any
  critical-path member.
- Declaration/DAG consistency: WORK-042's declared dependencies equal its
  DAG edges; the commercial items' declared dependencies equal their hard
  DAG edges. The only divergences are the two sanctioned W050 advisory
  edges, which ADV-01 reports as non-blocking advisories and this ACR
  records as deliberate (advisory input, not a gate).

## Migration / rollback plan

- Migration: none required beyond the synchronized documents themselves.
  In-flight state transitions atomically with the merge: at merge, the
  registry, the DAG, the checker expectations, the ledger entries, and the
  persistent-state narrative all become consistent in one commit series.
  The persistent snapshot baseline (`main_sha: 96db8aa`, LEDGER-RECON-006)
  is deliberately NOT moved by this ACR; the next reconciliation records
  the post-PR-#110 mainline `207d70e` per the standing RECON convention.
- Rollback: revert the merge commit. All changed artifacts are
  repository-local; no data, wire format, or deployment migration is
  involved. Historical integrity is preserved either way: WORK-001..WORK-041
  blocks are byte-identical before and after (proven mechanically in the
  reconciliation document), and this ACR record itself is never rewritten
  (a later ACR may supersede it).

## Architect decision

PENDING. This section must be completed by the Architect: render the
decision (ACCEPTED / REJECTED) as a durable decision record
(`spec/architect/decisions/DEC-NNNN-*.yaml`, type governance, `acr:
ACR-011`) and merge or close PR #111 accordingly. Until that decision is
recorded, this ACR is PROPOSED and creates no authorization, no acceptance,
and no architectural effect on `main`.

## Resulting architecture version

Unchanged — `1.0`. This ACR is an additive registry synchronization: it
registers Work Items whose architectural directions (ACR-006 for W042,
ACR-009 for the commercial phase) are already accepted without an
architecture-version bump, and it alters no protocol or authority semantics
of the current snapshot. This follows the established convention of
ACR-005/006/007/009 and the ACR-010 proposal; `spec/architecture.md` remains
byte-identical and remains the single architecture-version declaration
site.
