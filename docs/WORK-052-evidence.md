# WORK-052 Evidence Record (UsageLedger)

**Status: delivered for review under authorization `WORK-052-CORE-001`
(DEC-0059; baseline reconciled to the post-PR-#146 mainline by
DEC-0060 / LEDGER-RECON-009). SOFTWARE-class evidence only. NO
PHYSICAL claim is made (the usage ledger is a pure software
control-plane model; EVID-007 PARTIAL and EVID-008 NOT-TESTABLE
remain OPEN and W040-owned; W040 stays in-review and NOT
accepted).**

## 1. Authorization and provenance

- Authorization: `spec/architect/authorizations/WORK-052.yaml` —
  `WORK-052-CORE-001`, `status: active`, `authorized: true`,
  `authorization_decision: DEC-0059`, inherited **byte-identically
  from main** (unmodified; the authorization record is durable
  provenance and is never touched by this PR — battery case_43
  pins it byte-identical to `origin/main`).
- Architecture basis: ACR-009 — Commercial Connectivity Control
  Plane (ACCEPTED, **DEC-0050**, proposal merged by PR #82),
  specifically the "Usage integrity" section and required
  invariants 3, 6, 7, 10 (usage rules, append-only monetary
  mutations, compensating events, immutable usage history).
- Authorization baseline (recorded, preserved exactly):
  `39d40b752f9129ac898fb74da1e485c20c6fbdc6` — the post-PR-#146
  governance mainline, reconciled by DEC-0060 / LEDGER-RECON-009
  (PR #147, merge `2e87cb35643b72a94be39aa3eb96ceed1a3e18da`).
- Actual implementation branch point (live main at branch cut):
  `058901d74d8fa61cdf023209a94cb155ebb942c0` — the post-PR-#148
  (authoritative roadmap) mainline, re-read live and verified
  immediately before branching, exactly as the WORK-052
  activation dispatch (issue #84 comment 5545861892) instructs.
  The intervening change is governance-only (the canonical roadmap
  installation); `tools/spec_check.py` ARCH-03/ARCH-08 compare the
  authorization `baseline_sha` against the RECORDED
  `execution-state.yaml.repository.main_sha` (`39d40b7` — they
  match), never against the live git SHA; ARCH-08 additionally
  verifies the authorization is inherited byte-identically from
  the base (satisfied by branching from the actual live main).
  This is the established W44/W51 branch-point convention.
- Delivery: branch `work-052-usage-ledger`, single atomic commit,
  PR against main (this PR; the exact head SHA is in the PR body).

## 2. Delivered scope (exactly the authorized scope)

| Path | Content |
|---|---|
| `usage/` | The UsageLedger package (8 modules) |
| `tools/usage_selftest.py` | The deterministic battery (49 cases) |
| `docs/WORK-052-handoff.md` | Governance handoff (main) + implementation-level append (this PR) |
| `docs/WORK-052-evidence.md` | This evidence record |

Plus the sanctioned **additive-only CI wiring** (the accepted
W042/W051 precedent): one new step `Run usage ledger tests`
(`python3 tools/usage_selftest.py`) after the commercial battery
step in `.github/workflows/spec-check.yml`. `.github/` is
mechanically governance-classified (`GOVERNANCE_PREFIXES` in
`tools/spec_check.py`), so it is not an implementation delta; the
battery (case_44) verifies the wiring is purely additive and
weakens no step.

This PR also resolves the ARCH-07 known-fail that PR #148
introduced on main: `spec/architect/roadmap.md` forward-references
`tools/usage_selftest.py` and `docs/WORK-052-evidence.md`; both
now exist (both are in the authorized scope), so ARCH-07 returns
to PASS and `tools/spec_check.py` reaches 17/17 on this head.

Package layout:

```
usage/
  __init__.py      frozen 57-name public API
  errors.py        typed error model (23-reason vocabulary)
  evidence.py      the external evidence boundary (UsageEvidenceIndex,
                   delivery evidence kinds, quantity classes,
                   commercial transaction snapshots)
  model.py         the value model: states/actions/transition table,
                   command, event, observation/statement/compensation
                   facts, transaction projection, content-derived ids
  validation.py    admission rules (kind table, correlation, windows,
                   quantities, finality and compensation gates)
  journal.py       append-only hash-chained journal + store seam
  digest.py        deterministic digest stream (evidence chain)
  ledger.py        UsageLedger public surface + the single fold
```

## 3. Usage integrity: evidence-derived billing (criterion 1)

Usage is created ONLY by OBSERVE_USAGE commands of the DELIVERED
quantity class citing authoritative delivery evidence:

- The injected `UsageEvidenceIndex` is an immutable snapshot BUILT
  BY THE CALLER from public reads only (the W041/W042/W051
  composition precedent): the W051 `CommercialCore` public
  transaction projection (state + offer tariff) and the W042
  platform journal's delivery-plane interface-observation time
  series (the battery derives evidence windows from consecutive
  cumulative rx/tx counter deltas — public journal reads).
- The evidence **kind table** is structural, not caller-honor: a
  payment observation cited as delivery evidence fails closed
  `PAYMENT_NOT_DELIVERY`; a provider observation fails closed
  `PROVIDER_NOT_DELIVERY` (provider/payment observations are DATA,
  never proof of delivery). The kind is carried by the index
  record, so a caller cannot "honor" a payment observation into
  usage.
- **Payment capture never creates usage** (battery case_10,
  case_14): payment-observation evidence is rejected at the kind
  table, and the sealed statement's billable derivation provably
  draws only from delivered-kind evidence citations.
- **Reservation/lease state never creates usage** (case_13,
  case_49): a DELIVERED observation against a transaction whose
  cited W051 state is `RESERVATION_HELD` fails closed
  `RESERVATION_NOT_USAGE`; any other pre-delivery phase fails
  closed `TRANSACTION_NOT_DELIVERING`. The reserved and attempted
  quantity classes (ACR-009: usage records distinguish reserved /
  attempted / delivered / billable / disputed / refunded /
  reversed quantities) are recorded as DATA for reconciliation and
  structurally never contribute to billable quantity. The
  delivery-eligibility gate binds **admission and replay
  symmetrically** (case_49, the second architectural review
  round): a walk-valid, fully-recomputed journal claiming a
  DELIVERED observation against a pre-delivery authority snapshot
  with otherwise-valid matching delivered evidence fails closed
  `JOURNAL_CORRUPT` at load/fold — the journal cannot contain an
  observation admission would have rejected.
- Fabricated evidence ids and fabricated transaction citations
  fail closed `EVIDENCE_UNKNOWN` / `TRANSACTION_UNKNOWN` (case_09);
  cross-transaction evidence fails closed `EVIDENCE_MISMATCH`
  (case_11); overstatement of the authoritative delivered quantity
  (single-observation or cumulative windowed sub-metering) fails
  closed `QUANTITY_EXCEEDED` (case_12, case_18); window overreach
  or inversion fails closed `WINDOW_INVALID` (case_12).

## 4. Idempotency and no-double-charge (criterion 2)

Two dedup layers, both journal-free no-ops (no clock read, no
state change):

- **Command-level** (case_15, case_16): exact redelivery of an
  admitted command id + content digest is a DUPLICATE no-op
  returning the recorded event; the same command id with different
  content fails closed `COMMAND_CONFLICT` (conflicting reuse of an
  observation identity fails closed).
- **Evidence-window level** (case_17, the named no-double-charge
  layer): a NEW command reporting the SAME (evidence_id, window)
  with the SAME quantity is an idempotent DUPLICATE returning the
  recorded observation (a restarted collector shard cannot
  double-charge); the same evidence-window with a DIFFERENT
  quantity fails closed `EVIDENCE_MISMATCH` (the same delivered
  fact cannot carry two quantities). The cumulative per-evidence
  cap bounds disjoint windowed sub-metering to the authoritative
  delivered quantity exactly (case_18).
- Both layers are **durable**: they survive restart (case_29
  verifies command AND evidence-window idempotency after
  journal-first recovery).

## 5. Out-of-order and delayed observations (criterion 2)

- **Arrival-order-independent ECONOMIC fold; admission-attributed
  audit identity** (case_19, narrowed to exactly what is
  proven): the same admitted observation set sealed in any
  arrival order (including the delayed earliest-window-last
  permutation) produces the SAME sealed billable quantity,
  amount, contributing-evidence multiset, observation count, and
  net — the per-transaction projection is sorted by observation
  id and the billable derivation is a commutative sum. The
  observation identities, the `contributing_observations` audit
  list, and the statement id are honestly **admission-attributed**
  (they bind the causal command id and the admission instant),
  so different arrival orders produce DIFFERENT ids and audit
  lists — case_19 PROVES this divergence rather than claiming
  order-independent audit identity. The journal honestly records
  admission order (the history); the economic billable fact is
  the order-independent surface, and the evidence record claims
  exactly that.
- **Delayed observations after finality fail closed** (case_20):
  once BILLABLE_FINAL, both delivered and data-class observations
  are rejected `USAGE_SEALED` (the sealed fact is immutable;
  corrections are compensations only).
- **Out-of-order event injection fails closed at every layer**
  (case_07 admission; case_04 model; case_31 replay): a fully
  recomputed, chain-valid, table-legal journal record whose
  declared `from_state` does not connect to the folded walk is
  rejected at load — the replay verifies the WALK, not merely
  the chain and each edge, and the causal identity
  re-derivation (§ 10) gates fabricated identities even before
  the walk linkage is reached.

## 6. Billable finality (criterion 3)

- The SEAL_BILLABLE transition is **explicit** (case_21): the
  statement carries the class-distinguished quantities
  (reserved/attempted/delivered), billable == delivered exactly
  (no silent write-up/down), the integer tariff
  (`billable_quantity * unit_price_micros`, exact arithmetic — no
  floats anywhere: the canonical JSON subset forbids them), the
  tariff provenance, and the sorted audit trail (contributing
  observation ids + evidence ids). The honest
  zero-observation seal (explicit zero bill) is supported and
  verified.
- **Immutable** (case_22, case_20): re-seal fails closed
  `FINAL_IMMUTABLE`; late observations fail closed `USAGE_SEALED`;
  no rewrite/removal API exists anywhere on the ledger surface
  (case_27 audits it); frozen records reject ordinary attribute
  writes; the sealed statement survives all compensations
  byte-identically.
- **Corrections are append-only compensating records** (case_23,
  case_24, case_25): refunds and reversals adjust the net against
  the sealed amount (bounded: cumulative compensation can never
  exceed the sealed amount — the net never goes negative; the
  exact-cap compensation legitimately nets to zero); disputes are
  non-monetary flags (amount pinned to 0) citing the sealed
  statement; every compensation cites the immutable statement id.
  Dispute resolution is explicitly out of W052's boundary
  (settlement-layer concern; the second open dispute fails closed
  `DISPUTE_ALREADY_OPEN`).

## 7. Correlation and audit (criterion 4)

- Every usage observation correlates its delivered quantity to the
  authoritative delivery-evidence record (evidence id + window +
  the evidence's own transaction/session/path citations enforced
  at admission).
- The sealed statement carries the full audit trail: sorted
  contributing observation ids, sorted contributing evidence ids,
  the tariff provenance, and the sealed instant.
- The **reconciliation statement** (case_26) is a deterministic
  pure read (no journal growth, no clock consumption): observed
  delivery -> billable quantity/amount -> compensations -> net,
  with the complete ACR-009 class distinction (reserved /
  attempted / delivered / billable / disputed / refunded /
  reversed) and the projection digest — byte-identical across
  re-reads, restarts, and replay.

## 8. No authority mutation (criterion 5)

- The UsageLedger owns usage/economic ledger state ONLY. It
  REFERENCES W051 commercial transaction ids, W041 NetworkPath
  ids, W012 logical session ids, and delivery-plane evidence ids
  through the injected immutable index; it never queries,
  instantiates, or mutates any authority (battery case_37 audits
  constructor/load signatures take no authority objects; case_38
  AST-audits the sanctioned import allowlist — `protocol.` and
  `agent.clock` only; the W051 commercial core, sessions,
  NetworkPath, identity, routing, transport, policy, federation,
  platform, and payment code are unreachable from the usage
  family).
- No vendor/payment-provider tokens anywhere in the family
  (case_38; technology- and provider-neutral).
- The battery itself composes the REAL public production chain
  only (case_41): the ordinary AgentRuntime session handshake, the
  NetworkPathManager public lifecycle, the PlatformIntegrator
  public journal, the W051 CommercialCore public typed surface
  driven to DELIVERY_COMPLETED — and builds the injected index
  from those public reads. No private method is called to
  manufacture a PASS (case_37 audits the battery text).

## 9. Determinism

- The ONLY time source is the injected WORK-033 `AgentClock` seam:
  duplicates (both layers) consume NO clock read; every other
  submission consumes exactly ONE (including state-gate
  rejections — the read count is a pure function of the command
  sequence; case_35 with the CountingClock fixture; no public
  method accepts an instant parameter; no wall-clock module is
  importable in the family).
- All identities and digests are content-derived over WORK-003
  canonical JSON (`sha256:<hex>` fingerprints; never NodeIDs,
  never trust). Sorted iteration everywhere.
- Integer-only money math (quantities, prices, amounts; no floats,
  no rounding).
- **Two-run proof** (case_33): the golden scenario (full authority
  composition -> 9-command usage lifecycle: 3 delivered
  observations + reserved/attempted DATA observations -> seal ->
  refund -> reversal -> dispute) run twice fresh produces
  byte-identical digests (journal, state, command ledger, event
  list, evidence index).
- **Hash-seed proof** (case_34): `PYTHONHASHSEED=0 / 1 / 7919 /
  unset` subprocesses all reproduce the baseline digest stream
  byte-identically.
- **Fresh-world independence** (case_45): every vector builds its
  own fixture world; structurally different worlds produce
  distinct streams; interleaved coexisting worlds reproduce their
  isolated baselines byte-for-byte (no shared mutable usage
  state).

## 10. Durability and replay integrity

- The journal is append-only and hash-chained (W042/W051
  discipline): byte tamper, line reorder, tail truncation,
  sequence gap, command-digest edit, event-id edit, and
  non-canonical (float) payload content all fail closed
  `JOURNAL_CORRUPT` at load (case_28).
- **The complete causal identity web is re-derived and verified
  on every replay/load** (the P0 replay-integrity boundary): the
  single `apply_record` fold — used by BOTH the live manager and
  replay — verifies, for every journal record, that
  (a) the event attribution equals the admitted command's
  attribution; (b) the fact kind matches the action (the
  action/fact table); (c) each content-derived fact identity
  (`observation_id` / `statement_id` / `compensation_id`)
  re-derives from the fact's OWN content; (d) the `event_id`
  re-derives from the event's content and the fact's identity;
  (e) the fact is EXACTLY the deterministic derivation of its
  causal command, the folded walk state, and the event instant;
  (f) the walk linkage and frozen transition table hold; and
  (g) the external authority anchors re-bind: the sealed
  statement is re-derived against the **injected W051
  transaction snapshot** (tariff unit price, billable unit,
  provenance, and the exact amount
  `billable_quantity * unit_price_micros`), the cited W051
  transaction snapshot must resolve and pass the **SAME
  delivery-eligibility gate admission applies**
  (`validate_delivery_eligibility` — reservation/lease and every
  other pre-delivery state never creates usage, at admission OR
  at replay; admission/replay symmetry), the DELIVERED
  observations' evidence citations re-resolve against the
  **injected evidence index** (kind table, correlation, window,
  static and cumulative quantity bounds), and compensations
  re-verify the bounded-net discipline (cumulative compensation
  ≤ the sealed amount; one open dispute). Any mismatch fails
  closed `JOURNAL_CORRUPT`.
- **Walk-valid, fully-recomputed-chain fact tampering is
  rejected** (cases 46/47/48, the adversarial class the
  architectural review required): an observation mutated with a
  fully recomputed identity cascade and outer chain fails the
  causal command→fact binding, and a MAXIMAL cascade (mutated
  command + recomputed digest, re-derived seal and
  compensations, internally self-consistent quantities/amount at
  the honest tariff) still fails the injected evidence authority
  (the cumulative quantity cap); a chain-recomputed **tariff
  tamper** on the sealed bill (internally arithmetic-consistent
  repricing) fails the W051 snapshot re-binding — including on
  the honest zero-bill seal; a compensation payload tamper fails
  the command→fact binding, and its maximal cascade fails the
  bounded-net discipline. An event **attribution swap** (forged
  actor on a chain-recomputed event) fails the event/command
  attribution binding, and an action/**fact-kind swap** fails the
  action/fact table. A recomputed outer hash chain cannot make a
  modified economic fact acceptable.
- **The admission/replay delivery-eligibility asymmetry is
  closed** (case_49, the second review round's P0): the exact
  forged construction the architectural review specified — a
  `RESERVATION_HELD` (or `OFFER_SELECTED`) authority snapshot +
  VALID matching DELIVERED evidence + a walk-valid,
  fully-recomputed command/fact/event/record chain (creation
  observation → seal → refund, every identity and the entire
  outer chain recomputed, tariff- and bound-consistent) — is
  **rejected fail-closed `JOURNAL_CORRUPT` at replay** while the
  identical journal against a delivery-eligible snapshot loads
  cleanly (the control proves the rejection is the eligibility
  gate alone), and a downgraded authority snapshot (the
  byte-unmodified honest journal replayed against an index whose
  golden transaction state is `RESERVATION_HELD`, tariff
  untouched) also fails closed — fail-closed, never fail-open.
  Red/green proof: on the pre-correction head the three forgeries
  were accepted at replay (the battery FAILed); on this head they
  fail closed (49/49 PASS).
- **Persist-then-ack** (case_32): a store failure leaves no
  phantom in-memory state (no journal record, no transaction).
- **Journal-first recovery** (case_29): `UsageLedger.load` ==
  live byte-identical (journal digest, state digest, command
  ledger, per-transaction projections, reconciliation statement);
  the recovered ledger accepts new commands and both idempotency
  layers survive restart. `FileUsageStore`
  (`usage-journal.jsonl`) is the only filesystem-write site in
  the usage family. Load requires the injected index to resolve
  every transaction/evidence citation the journal carries (the
  caller injects an index at least as complete as
  admission-time; an unresolvable citation at replay is
  `JOURNAL_CORRUPT` — fail closed).
- **Replay verification** (case_30): `fold(journal) == live`
  byte-identical by construction (the same single
  `apply_record`); the fold is a pure function.
- **Honest tamper-boundary disclosure**: the replay gates above
  verify the journal against itself (the complete internal
  causal web) and against the injected authority snapshots (the
  W051 tariff and the delivery evidence). A hypothetical
  adversary who rewrites the journal AND every cascaded identity
  AND stays within every authority bound (e.g. a quantity
  under-statement that remains inside the evidence caps, with a
  fully re-derived seal and compensations) produces a journal
  that is indistinguishable from an honest alternative admission
  history BY THE JOURNAL ALONE; detecting that class is exactly
  what the externally published digest stream
  (`journal_digest` / `digest_stream`) is for — operators
  compare the digest stream against their own out-of-band
  record. No in-journal mechanism can anchor against a full
  self-consistent rewrite, and this evidence record does not
  claim one.

## 11. Mandated negative cases

| Negative case | Result |
|---|---|
| missing delivery evidence (no citation) | PASS — `OBSERVATION_REJECTED` at shape |
| fabricated evidence id | PASS — `EVIDENCE_UNKNOWN` |
| fabricated/unregistered transaction | PASS — `TRANSACTION_UNKNOWN` |
| unauthorized evidence (payment observation) | PASS — `PAYMENT_NOT_DELIVERY` |
| unauthorized evidence (provider observation) | PASS — `PROVIDER_NOT_DELIVERY` |
| reservation/lease state as usage source | PASS — `RESERVATION_NOT_USAGE` + DATA-only classes |
| other pre-delivery transaction state | PASS — `TRANSACTION_NOT_DELIVERING` |
| cross-transaction evidence correlation | PASS — `EVIDENCE_MISMATCH` |
| quantity overstatement (single) | PASS — `QUANTITY_EXCEEDED` |
| cumulative sub-metering overstatement | PASS — `QUANTITY_EXCEEDED` |
| window overreach / inversion | PASS — `WINDOW_INVALID` |
| duplicate command redelivery | PASS — DUPLICATE no-op, zero double-charge |
| conflicting command redelivery | PASS — `COMMAND_CONFLICT` |
| duplicate evidence-window report | PASS — DUPLICATE no-op, zero double-charge |
| conflicting evidence-window quantity | PASS — `EVIDENCE_MISMATCH` |
| late observation after BILLABLE_FINAL | PASS — `USAGE_SEALED` |
| re-seal | PASS — `FINAL_IMMUTABLE` |
| compensation before seal | PASS — `COMPENSATION_REQUIRES_FINAL` |
| over-compensation (net < 0) | PASS — `COMPENSATION_EXCEEDED` |
| second open dispute | PASS — `DISPUTE_ALREADY_OPEN` |
| inserted out-of-order journal record | PASS — `JOURNAL_CORRUPT` (causal identity + walk linkage) |
| journal tamper (7 vectors) | PASS — `JOURNAL_CORRUPT` |
| walk-valid fact-only tamper w/ recomputed chain (observation) | PASS — `JOURNAL_CORRUPT` (command→fact binding) |
| walk-valid maximal-cascade observation tamper | PASS — `JOURNAL_CORRUPT` (evidence authority cap) |
| walk-valid chain-recomputed tariff tamper (incl. zero-bill seal) | PASS — `JOURNAL_CORRUPT` (W051 snapshot binding) |
| walk-valid fact-only compensation tamper | PASS — `JOURNAL_CORRUPT` (command→fact binding) |
| walk-valid maximal-cascade compensation tamper | PASS — `JOURNAL_CORRUPT` (bounded net) |
| walk-valid event attribution swap (recomputed chain) | PASS — `JOURNAL_CORRUPT` (attribution binding) |
| walk-valid action/fact kind swap (recomputed chain) | PASS — `JOURNAL_CORRUPT` (action/fact table) |
| walk-valid pre-delivery forgery (RESERVATION_HELD + valid evidence + recomputed chain) | PASS — `JOURNAL_CORRUPT` (eligibility re-application) |
| walk-valid pre-delivery forgery (OFFER_SELECTED + valid evidence + recomputed chain) | PASS — `JOURNAL_CORRUPT` (eligibility re-application) |
| honest journal against a downgraded (pre-delivery) authority snapshot | PASS — `JOURNAL_CORRUPT` (fail-closed, never fail-open) |
| store failure phantom state | PASS — none (persist-then-ack) |
| reserved/attempted class billed | PASS — never (DATA-only) |
| payment capture creating usage | PASS — never (kind table) |

All 23 frozen reason codes are exercised (battery case_40).

## 12. Test results

- `python3 tools/usage_selftest.py`: **PASS 49/49** (two
  consecutive runs byte-identical; the determinism cases are
  in-process two-run and four-subprocess-hash-seed proofs).
- `python3 tools/spec_check.py`: **17/17 PASS** on this head (the
  PR-#148-introduced ARCH-07 forward-reference to
  `tools/usage_selftest.py` and `docs/WORK-052-evidence.md` is
  resolved by this delivery — both files are in the authorized
  scope).
- `python3 tools/spec_check.py --provenance`: **ARCH-08 PASS** —
  "implementation delta (8 file(s)) covered by the active
  authorization inherited from the base" (usage/** implementation
  files covered by the `usage/` scope entry; `tools/` and `docs/`
  deltas are governance-classified; zero `spec/architect/`
  changes; the authorization is inherited byte-identically).
- Accepted batteries on this branch (the documented PR-context
  scope-guard class): `tools/commercial_selftest.py` runs 38/38 in
  the CI context (the case_35 PR-delta scope guard SKIPs without
  the `origin/main` ref — CI fetches it only for the final
  provenance step) and 37/38 in a local strict context where
  case_35 reports the delta outside the W051 scope — the same
  documented class the reconciliation session recorded for any
  non-W051 pre-merge delta; the post-merge simulation (synthetic
  repository with `origin/main` == this branch's tree) returns
  38/38. `tools/platformcaps_selftest.py` (the W050 exact-head CI
  job runs it without `origin/main`, deliberately) behaves
  identically to the reconciliation session's documented
  on-branch/simulation pair. The authoritative check is CI on the
  exact head.
- No local claim of any PHYSICAL result: this environment cannot
  exercise physical devices (W040's obligations remain untouched
  and W040-owned).

## 13. Authority-ownership audit

- The usage family imports ONLY `protocol.canonicalization`
  (WORK-003) and `agent.clock` (WORK-033) beyond stdlib value
  types (AST-audited, case_38); the W051 CommercialCore, W041
  NetworkPath, W042 platform, W012 sessions, W004 identity, W011
  routing, W017 transport, W010 policy, and W015 federation
  packages are unreachable — no shadow authority is constructible.
- No authority construction/mutation tokens (case_37); no
  authority parameters on `UsageLedger.__init__` / `UsageLedger.load`
  (store + clock seam + evidence index only).
- The frozen public API is pinned at 57 names (case_39).
- Frozen surfaces byte-identical to `origin/main` (case_43):
  architecture, lock, mission, governance, change-control,
  workflow, work-items, dependency-graph, protocol schema, the
  canonical roadmap (yaml + md), and the WORK-052 authorization
  itself.

## 14. Scope audit (PR delta)

The delta is confined to the WORK-052-CORE-001 scope (case_44):

- `usage/` (8 modules — new),
- `tools/usage_selftest.py` (new),
- `docs/WORK-052-handoff.md` (implementation-level append only),
- `docs/WORK-052-evidence.md` (this record),
- `.github/workflows/spec-check.yml` (one purely additive battery
  step; no step removed or weakened — audited).

Zero changes under `spec/` (including `spec/architect/`), zero
changes to any other Work Item's surface, zero changes to frozen
architecture. `spec_check.py --provenance` ARCH-08 PASS.

## 15. Honest evidence disclosure

- W052 is a SOFTWARE-class control-plane implementation. All
  verification above is deterministic, offline, stdlib-only
  software verification. No PHYSICAL evidence is claimed or
  implied: EVID-007 (real users/devices) and EVID-008 (real 5G
  access path) remain OPEN, PARTIAL/NOT-TESTABLE, and W040-owned;
  W040 remains in-review and NOT accepted, independent of this
  delivery.
- CI success is not acceptance: the Architect's exact-head review
  of this PR is the acceptance gate (DEC-0053 single-Architect
  authority). This head is the **second correction round** on the
  same PR lineage. Round 1 (REQUEST CHANGES on the first head)
  corrected the two P0 replay-integrity defects (fact-identity
  re-derivation; sealed-bill tariff re-binding) and the three P1
  findings (walk-valid recomputed-chain tamper battery;
  arrival-order claim narrowed to what is proven; refunded /
  reversed quantity views separated). Round 2 (the re-review's
  remaining P0) closed the admission/replay delivery-eligibility
  asymmetry: replay now re-applies the authoritative W051
  delivery-eligibility gate for every DELIVERED observation,
  fail-closed `JOURNAL_CORRUPT`, with the `RESERVATION_HELD` and
  `OFFER_SELECTED` walk-valid fully-recomputed adversarial
  vectors (case_49) added to the battery. The journaled history
  and every admitted identity remain byte-unchanged across both
  correction rounds (the golden digest stream is identical —
  the corrections add verification, they change no admitted
  fact).
- The replay-integrity boundary is stated honestly (§ 10): the
  journal verifies itself plus the injected authority anchors;
  a fully self-consistent within-bounds rewrite is detectable
  only against the externally published digest stream — no
  stronger claim is made.
- W053 (EconomicAllocation) is NOT activated by this delivery;
  roadmap placement never authorizes downstream work. The usage
  ledger exposes exactly the billable-final facts and
  reconciliation statements W053 is specified to consume, and the
  advisory extension points are documented in the implementation
  handoff (advisory only — not authorized scope).
