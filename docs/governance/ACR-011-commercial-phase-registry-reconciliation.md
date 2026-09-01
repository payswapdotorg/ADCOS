# ACR-011 — Commercial Phase Registry Extension Reconciliation

**Status: companion evidence/reconciliation document for ACR-011 (PROPOSED, vehicle PR #111).**

This document records the machine-checked contradiction that motivates ACR-011, the
exact synchronized changes carried by the proposal, the historical-integrity proofs,
the validation evidence, and the scope/authority audit. It is documentation of the
proposal, not a second authority: `spec/acr/ACR-011-commercial-phase-registry-extension.md`
is the ACR record, and the frozen documents it extends remain governed by
`spec/change-control.md`.

---

## 1. The registry boundary (the machine-check contradiction)

The contradiction is machine-checked, durable, and reproducible from the repository
alone (`main` at `207d70e`, the merge of PR #110):

1. **WORK-042 is delivered and merged.** PR #110 (branch
   `work-042-platform-journal-core`) is MERGED: head `708a432`, merge `207d70e`,
   authoritative CI run 33444952103 (spec-check, pull_request) SUCCESS on the head —
   the platform battery step ran and passed 32/32 — merged by the Architect
   2026-08-31T22:54:17Z. The delivery is covered by the active authorization
   `WORK-042-CORE-001` (DEC-0055; baseline `96db8aa` = the LEDGER-RECON-006 snapshot
   baseline; the implementation branch was cut from the post-PR-#109 mainline
   `1909479`, which carries the authorization record byte-identically; ARCH-08
   provenance verified on the PR).
2. **WORK-042 is unrepresentable.** `spec/work-items.md` terminates at
   `### WORK-041`; `spec/dependency-graph.md` carries exactly the 134 pre-extension
   edges over `W001..W041`; `tools/spec_check.py` (pre-extension) defines
   `EXPECTED_WORK_ITEM_COUNT = 41`, `BACKLOG-01` requires the backlog to be exactly
   `WORK-001..WORK-041` gap-free, and the execution-ledger validation requires the
   ledger Work Item set to equal `{"WORK-001".."WORK-041"}` exactly. The repository's
   own persistent state records the boundary: "WORK-042 is NOT registered in the
   frozen backlog (its own governance registration issues separately)".
3. **Acceptance is structurally blocked.** A future WORK-042 acceptance decision
   (review-protocol §5) cannot be recorded: the required ledger transition would be
   rejected as an unknown Work Item until the registry is extended first.
   LEDGER-RECON-004 established the convention — a ledger entry is added once the
   Work Item has a delivery PR **and is registered in the frozen registry** — and
   the second precondition is impossible without an architecture change.
4. **The W041 precedent.** The identical boundary appeared at W041 completion:
   ACR-010 (PR #108) was proposed to extend the registry 40 → 41 and was superseded
   by the DEC-0054/DEC-0055 transition, which applied the registry extension
   directly as the mechanical prerequisite of recording the W041 acceptance. The
   pattern is established: **every** future Work Item acceptance hits the same wall
   and needs a registry change first. ACR-011 ends the compounding for the entire
   canonical commercial phase.
5. **The retired slot is unrepresentable.** LEDGER-RECON-005 §4 retired WORK-043
   from commercial use (never reused or renumbered). The pre-extension gap-free
   `BACKLOG-01` semantics cannot represent a retired slot at all: registering
   `WORK-042` and `WORK-044..WORK-053` without `WORK-043` would fail every
   gap-integrity check. Representing retirement deliberately requires an explicit,
   machine-checked retired-slot mechanism — an addition to the checker, not a
   weakening of it.
6. **The whole next phase is durably planned.** The canonical commercial dependency
   model (`docs/roadmap/commercial-dependency-model.md`, LEDGER-RECON-005; ACR-009
   accepted by DEC-0050) defines the complete post-W042 phase, and
   `execution-state.yaml`'s `planned_work_items` already carries every item as a
   ready-candidate with `authorization: "none"`. The direction is accepted; only
   the registry representation is missing.

This is precisely the situation `spec/change-control.md` §4 rule 3 requires to be
resolved by an ACR. Weakening ARCH-02/03/04/05/08, adding out-of-band ledger
entries, silently changing frozen semantics, or allowing Work Item acceptance to
bypass the registry would all be the wrong response; the registry itself must
evolve through the accepted ACR mechanism (ACR-007).

## 2. Why ACR-011 registers the whole commercial phase (scope decision)

The scope was derived from the live repository, not assumed:

- **Frozen registry constraints:** the registry is a frozen architecture document
  (`spec/governance.md` §1); every extension is an ACR-priced change. Registering
  only WORK-042 (the literal ACR-010 pattern) would leave the very next phase
  (W051 CommercialCore — the chain head the canonical model and the standing
  `next_required_decisions` both point at) unrepresentable, requiring yet another
  registry ACR immediately: the exact compounding the W041/W042 transitions
  exposed.
- **Current roadmap:** the canonical commercial dependency model is complete and
  durable (§1.6): the chain W051 → W052 → W053, the periphery W044–W047, the
  capability matrix W050, the sharing runtime W048, and the client runtime W049,
  with WORK-043 retired.
- **Current dependency graph and ACRs/decisions:** ACR-009 (DEC-0050) accepted the
  commercial control-plane architecture; DEC-0051 decoupled W040 as advisory;
  LEDGER-RECON-005 reconciled the planning surface; DEC-0054/DEC-0055 established
  the direct-application precedent for registry extensions.
- **spec_check.py invariants:** the extension preserves set-equality (the ledger
  must account for exactly the registered items), gap-integrity (only the recorded
  retirement may leave a vacant slot), count synchronization, and every
  fail-closed semantic (§5).
- **Actual Work Item contracts:** the registered definitions are taken from the
  live tracking issues (#83, #84, #85, #88–#92, #96, #98) and the canonical model;
  WORK-042's registry definition is taken from the canonical contract
  `spec/architect/work-items/WORK-042.md` and the authorization record
  `WORK-042.yaml` (dependency list identical, so ARCH-03's frozen-declaration
  match holds).

Rejected alternatives are recorded in the ACR record (§ Proposed change): weakening
checks, W042-only registration, reviving WORK-043, declaring W050 a hard gate,
accepting W042 or activating W051 inside this ACR, and out-of-band delivery
recording.

## 3. Exact synchronized changes (the proposal vehicle)

All changes take effect only when the Architect merges PR #111; until then `main`
is unchanged (change-control §3 element 8; ACR-010 precedent).

| File | Change |
|---|---|
| `spec/acr/ACR-011-commercial-phase-registry-extension.md` | new ACR record (PROPOSED) |
| `spec/acr/README.md` | registry listing gains the ACR-011 entry |
| `spec/work-items.md` | Phase 9 prose synchronized (W042 registration); `### WORK-042` registered; new `# Phase 10 — Canonical commercial phase` with `WORK-051`, `WORK-052`, `WORK-053`, `WORK-044`, `WORK-045`, `WORK-046`, `WORK-047`, `WORK-050`, `WORK-048`, `WORK-049`; `WORK-001..WORK-041` blocks byte-identical; WORK-043 not registered (retired) |
| `spec/dependency-graph.md` | 11 new nodes; 30 new edges (§4); Phase 9 gains `W042`; new Phase 10; §8 completion criterion synchronized to "all 52 registered Work Items" (WORK-043 retired, slot vacant); critical path unchanged |
| `tools/spec_check.py` | `EXPECTED_WORK_ITEM_COUNT` 41 → 52 (registered items); new `RETIRED_WORK_ITEM_IDS = {"WORK-043"}` (the only sanctioned gap); `EXPECTED_WORK_ITEM_IDS` derived; ledger lifecycle vocabulary gains `registered` with fail-closed null-delivery rules; `BACKLOG-01`/ledger set-equality/`CHECK_TITLES` synchronized |
| `tools/spec_check_selftest.py` | two mutation anchors re-scoped to unique contexts (W001 dependency line; W040 merge fields) — deliberate self-test maintenance required by the registry extension, with unchanged mutation semantics |
| `spec/architect/execution-ledger.yaml` | WORK-042 delivery entry appended (lifecycle `implemented`: PR #110 merged facts; `acceptance_decision: null`, `reviewed_sha: null`); ten `registered` entries appended (WORK-044..WORK-053, all delivery fields null); no existing entry rewritten |
| `spec/architect/execution-state.yaml` | `open_acrs` gains ACR-011 (PROPOSED, vehicle PR #111); `halted_reason` records the W042 delivery merge and the ACR; `next_required_decisions` refreshed (decide ACR-011; render the W042 acceptance review; evaluate the next authorization); planned WORK-042 entry records the delivery facts; snapshot baseline deliberately NOT moved |
| `spec/architect/current-state.md` | narrative synchronization: main = `207d70e` (PR #110 merged); W042 delivered-not-accepted; ACR-011 PROPOSED; W043 retired-slot representation; commercial entries registered-only |
| `docs/governance/ACR-011-commercial-phase-registry-reconciliation.md` | this document |

## 4. Exact Work Items registered and dependency edges

Registered (11; all additive):

- `WORK-042 — Event-Driven Platform Integration and Journal-First Recovery` (Phase 9)
- `WORK-051 — CommercialCore: connectivity intent, offers, reservation, lease, and transaction lifecycle` (Phase 10; dependencies: none)
- `WORK-052 — UsageLedger: delivered-usage metering, billable finality, and append-only reconciliation` (Phase 10; dependencies: WORK-051)
- `WORK-053 — EconomicAllocation: developer/provider/ADCOS revenue-share policy and external payment boundary` (Phase 10; dependencies: WORK-052)
- `WORK-044 — Payment Provider Adapters & Settlement Gateway` (Phase 10; dependencies: WORK-051, WORK-053)
- `WORK-045 — Connectivity Eligibility, Provider Trust & Jurisdiction Policy` (Phase 10; dependencies: WORK-051, WORK-053, WORK-044)
- `WORK-046 — Developer Connectivity API, SDK & Webhook Platform` (Phase 10; dependencies: WORK-051, WORK-052, WORK-053, WORK-044, WORK-045)
- `WORK-047 — Connectivity Marketplace Discovery, Proximity & Path Selection` (Phase 10; dependencies: WORK-051, WORK-044, WORK-045, WORK-046)
- `WORK-050 — Platform Connectivity Sharing Capability & Isolation Matrix` (Phase 10; dependencies: none)
- `WORK-048 — Provider Connectivity Sharing Runtime, Isolation & Quota Enforcement` (Phase 10; dependencies: WORK-041, WORK-042, WORK-051)
- `WORK-049 — Provider & Buyer Connectivity Client Runtime` (Phase 10; dependencies: WORK-046, WORK-047, WORK-048)

Dependency edges added (30; derived from the canonical model §2 and the WORK-042
contract/authorization declaration):

- WORK-042 (6): `W012→W042`, `W013→W042`, `W014→W042`, `W033→W042`, `W035→W042`, `W041→W042`
- commercial chain (2): `W051→W052`, `W052→W053`
- commercial periphery, hard (17): `W051→W044`, `W053→W044`, `W051→W045`, `W053→W045`, `W044→W045`, `W051→W046`, `W052→W046`, `W053→W046`, `W044→W046`, `W045→W046`, `W051→W047`, `W044→W047`, `W045→W047`, `W046→W047`, `W051→W048`, `W041→W048`, `W042→W048`
- client runtime (3): `W046→W049`, `W047→W049`, `W048→W049`
- advisory capability input (2, deliberately NOT declared as hard dependencies): `W050→W048`, `W050→W049`

DAG audit (mechanical): pre-extension 134 edges; post-extension 164; added 30;
removed 0; duplicates 0; **acyclic** (DEPS-02 union graph of DAG edges and declared
dependencies). The Phase 10 member order
(`W051, W052, W053, W044, W045, W046, W047, W050, W048, W049`) is a topological
order of the Phase 10 subgraph, so DEPS-03's intra-phase ordering holds. Phases
remain sequential 0–10. The critical path is unchanged (terminating at W040).

## 5. Checker semantics preserved (fail-closed audit)

- `BACKLOG-01` remains a set-exactness check: the registered IDs must be exactly
  `WORK-001..WORK-053` minus the recorded retired set. The retired slot is the
  **only** sanctioned gap; any other gap, any duplicate, any count drift, and any
  revival of WORK-043 still fails closed exactly as before. The mechanism is an
  additive constant (`RETIRED_WORK_ITEM_IDS`) recording the LEDGER-RECON-005
  retirement — not a relaxation of the gap rule.
- The execution-ledger set-equality is preserved (not weakened to a subset): the
  ledger must account for exactly the 52 registered items.
- The new `registered` lifecycle is fail-closed: a registered-only entry must NOT
  claim branch, PR, PR head, reviewed SHA, merge SHA, merge timestamp, CI run,
  review rounds, acceptance decision, or correction decisions — a fabricated
  delivery can never enter the ledger disguised as registration. Delivery
  lifecycles keep requiring branch and PR exactly as before.
- `ARCH-02/03/04/05/06/07/08` semantics are untouched: ARCH-03 still enforces
  exactly-one-active authorization with baseline and frozen-declaration match
  (`WORK-042-CORE-001` remains the sole active authorization; its dependency list
  matches the newly registered WORK-042 declaration exactly); ARCH-05 lifecycle
  coherence holds; ARCH-08 provenance classifies this PR's delta as
  governance/meta-only (no implementation authorization required).
- `spec_check_selftest.py` retains all 32 cases with unchanged expected outcomes;
  two mutation anchors were re-scoped to unique contexts because the registry
  extension legitimately added text that made the bare anchors ambiguous
  (W001's `Dependencies: none`; W040's null merge fields). The mutations
  themselves are semantically identical (the same lines are mutated in the same
  entries).

## 6. Historical integrity proof

Mechanical proof (git-based, reproducible):

- `spec/mission.md`, `spec/architecture.md`, `spec/architecture-lock.md`,
  `spec/architect/authorizations/WORK-042.yaml`,
  `spec/architect/work-items/WORK-041.md`,
  `spec/architect/work-items/WORK-042.md`: **byte-identical to `origin/main`**
  (full-file sha256 equality; they are absent from the PR diff).
- `spec/work-items.md`: every `### WORK-001` .. `### WORK-041` block is
  byte-identical (per-block sha256 equality pre/post; the only intra-file edits
  are the Phase 9 prose sentence recording W042's registration and the appended
  blocks). No block is rewritten, renumbered, or removed; WORK-043 is not added.
- `spec/dependency-graph.md`: the 134 pre-existing edges are byte-identical
  (sha256 equality of the extracted edge set); 30 edges are appended; no edge is
  removed or relabeled; the W001..W041 node declarations are unchanged.
- `spec/architect/execution-ledger.yaml`: every W001..W041 entry is
  byte-identical (per-entry equality with `origin/main`, including the W041
  acceptance note and all reconciliations LEDGER-RECON-001..006); the W042
  delivery entry and the ten registered-only entries are appended after WORK-041;
  `main_sha` remains `96db8aa` (the snapshot baseline is deliberately not moved
  by this ACR; the next reconciliation records the post-PR-#110 mainline
  `207d70e` per the standing RECON convention — ACR-010 precedent).
- No old commercial-era definitions are revived: WORK-043 stays retired and
  unregistered; the superseded labels (#83/#84/#85 original titles, PR #49/PR #100
  lineages) remain history only.

## 7. Why no authorization is created

- ACR-011 changes no file under `spec/architect/authorizations/`: `WORK-042.yaml`
  remains the single `status: active` record (byte-identical), and no
  `WORK-044..WORK-053`, `WORK-048`, or `WORK-051` authorization file exists before
  or after this change.
- Registration is representation only: the ledger's `registered` lifecycle and the
  execution-state `planned_work_items` entries all record `authorization: "none"`
  (review-protocol §3.1: an in-review/registered ledger entry is descriptive only
  and never authorizes anything; ARCH-08 enforces the authorization gate
  mechanically).
- No acceptance is performed: WORK-042's ledger entry stays at lifecycle
  `implemented` with `acceptance_decision: null` and `reviewed_sha: null`; the
  acceptance review is the next separate Architect decision (review-protocol §5),
  as is any supersession of `WORK-042-CORE-001`.
- The one-active-authorization invariant is untouched: `WORK-042-CORE-001` remains
  the sole active authorization (ARCH-03 PASS on this branch).

## 8. Why W043 remains retired and W040 remains independent

- **WORK-043** is retired from commercial use and left unassigned (LEDGER-RECON-005
  §4: never reused or renumbered, so no future reader can bind the superseded
  commercial-era "W043" label to a live artifact). ACR-011 does not register it and
  represents the retirement as the machine-checked retired slot (§5).
- **WORK-040** remains the independent physical validation / evidence track: no DAG
  edge to or from W040 is added (the pre-existing edge set is unchanged); its
  ledger entry remains `in-review` with `acceptance_decision: null`; EVID-007
  (PARTIAL) and EVID-008 (NOT-TESTABLE) remain OPEN and W040-owned; per DEC-0051
  its findings are advisory experience input to future commercial authorization
  reviews, NOT a hard execution prerequisite for any Phase 10 item.

## 9. Validation evidence (this branch)

- `python3 tools/spec_check.py` — PASS 17/17 blocking checks (FILES-01/02,
  MARK-01/02, VERS-01, BACKLOG-01 "52 registered items; retired slots: WORK-043",
  DEPS-01/02/03, ARCH-01..08) with exactly the two ACR-sanctioned ADV-01 advisory
  lines for the deliberately undeclared `W050→W048`/`W050→W049` advisory edges.
- `python3 tools/spec_check.py --provenance` — PASS 2/2 (ARCH-02, ARCH-08: the
  delta is governance/meta-only; no implementation authorization required).
- `python3 tools/spec_check_selftest.py` — PASS 32/32 (fail-closed battery:
  injected cycle, unknown reference, version-declaration, package-integrity,
  authorization-provenance, ledger-claim, evidence-honesty, and reference
  resolution mutations all still fail closed).
- Implementation batteries (`networkpath`, `platform`, `agent`, `mobile`,
  `session`, `adapter`, `transport`, `ipintegration`, `schema`): no
  implementation file changes in this PR, so every substantive case passes. The
  batteries' frozen-doc-intact / PR-delta-shape guard cases fail **only** in the
  local branch context (working tree with `origin/main` fetched): each compares
  the tree against `origin/main` or flags uncommitted `spec/` changes, and this
  governance proposal deliberately extends the frozen registry files. That is
  the documented W041/W042-precedent class: in CI pull_request context the
  `origin/main` ref is absent (the guards skip or see no diff) and the checkout
  is a clean commit (the uncommitted-change guards pass); on merged `main` there
  is no delta (the guards pass). A base-less single-branch PR-context
  verification (§9.1) proves the CI outcome.
- `python3 tools/schema_selftest.py` — PASS 25/25 (no origin/main dependency).

### 9.1 CI PR-context proof (base-less clone)

A fresh clone of this branch without any `origin/main` ref (the exact ref
situation of an actions/checkout pull_request run) was exercised with the full
workflow tool sequence: every step passed by exit code, including all battery
frozen-doc guards (skipped/no-diff as designed) and the spec-check/provenance
pair (17/17 and 2/2). The results are the CI-predicted outcomes recorded in
§9.

## 10. Authority and scope audit (the boundary)

- Implementation code: **none** (`platform/`, `networkpath/`, and every other
  implementation area absent from the diff).
- Authorizations: **none created, activated, superseded, or modified**.
- Active execution-slot changes: **none** (`WORK-042-CORE-001` stays the single
  active authorization).
- W040 changes: **none** (ledger entry, evidence obligations, and PRs untouched).
- W042/W041 implementation code: **untouched**.
- Frozen specification semantics: additive registration only; no LOCK-001..025
  identifier is modified; `spec/architecture.md` is byte-identical and remains the
  single architecture-version declaration site (version stays `1.0`).
- Secrets: **none** (no credentials, tokens, or private operational data in the
  diff).
- Mission: **unchanged** (byte-identical; economic/commercial mechanisms are
  explicitly mission-revisable).

## 11. Repository-state observation (honesty record)

During proposal preparation, four empty "noop" commits (a97dd02, d61c402, a77d824,
1702220, 2026-09-01T00:33Z) were observed on GitHub as short-lived `branch=main`
push events; they are **not reachable from `main`** (verified: `main` =
`207d70e` = the legitimate PR #110 merge; `git merge-base --is-ancestor` is false
for each; the only "noop" in history, 9d47fcd, dates from 2026-08-27 and is
unrelated). No repository artifact of this proposal depends on or references those
objects; they are recorded here solely for review transparency. Six
`governance/acr-011-*` proposal branches from the interrupted drafting session
also exist on the remote; this PR supersedes them all (they contain earlier
proposal-only drafts and no PR was ever opened for them).

## 12. Post-acceptance obligations (not performed here)

If the Architect accepts ACR-011 (durable decision record `DEC-NNNN`, type
governance, `acr: ACR-011`), the synchronized changes take effect with the merge.
The next governance steps remain, in order:

1. render the WORK-042 acceptance review (separate decision record identifying the
   exact reviewed SHA; ledger transition `implemented → accepted-merged`);
2. evaluate the next authorization (W051 CommercialCore is the canonical chain
   head; W048 requires W041+W042+W051 where consumed);
3. disposition the superseded PR #108 (ACR-010), PR #100, and PR #102;
4. move the snapshot baseline to the post-PR-#110 mainline in the next recorded
   reconciliation, per the standing RECON convention.
