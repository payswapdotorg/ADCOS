# WORK-053 Evidence Record (EconomicAllocation)

**Status: delivered for review under authorization `WORK-053-CORE-001`
(DEC-0061, baseline `bcaf0d0677437d1ffca8f5e493cab516c87e7194`).
SOFTWARE-class evidence only. NO PHYSICAL claim is made (the
economic-allocation layer is a pure software control-plane model;
EVID-007 PARTIAL and EVID-008 NOT-TESTABLE remain OPEN and
W040-owned; W040 stays in-review and NOT accepted).**

## 1. Authorization and provenance

- Authorization: `spec/architect/authorizations/WORK-053.yaml` —
  `WORK-053-CORE-001`, `status: active`, `authorized: true`,
  `authorization_decision: DEC-0061`, inherited **byte-identically
  from main** (unmodified; the authorization record is durable
  provenance and is never touched by this PR — battery case_57
  pins it byte-identical to `origin/main`).
- Architecture basis: ACR-009 — Commercial Connectivity Control
  Plane (ACCEPTED, DEC-0050), the "Economic allocation" section
  and the revenue-share/payment-boundary invariants.
- Authorization baseline (recorded, preserved exactly):
  `bcaf0d0677437d1ffca8f5e493cab516c87e7194` — the W052 merge
  commit (PR #149 merged at the exact reviewed head
  `7d883b227e9792b98efdbc1916d413491d20d458`, accepted by
  DEC-0061; verified live from the GitHub API before branching:
  `merged: True`, `merge_commit_sha: bcaf0d0...`).
- Actual implementation branch point (live main at branch cut):
  `cdf451ffcc876b0a4b6577072e0d69bbca2f14c0` — re-read live and
  verified immediately before branching (git ls-remote + the
  GitHub branches API; commit message "governance: reconcile W053
  active state after DEC-0061"), exactly as the WORK-053
  activation (issue #85, execution-state `main_sha_semantics`)
  instructs: "a W053 implementation branch must re-read exact
  live main and inherit that authorization byte-identically."
  The change beyond the recorded baseline is governance-only
  (the DEC-0061 state reconciliation); `tools/spec_check.py`
  ARCH-03/ARCH-08 compare the authorization `baseline_sha`
  against the recorded `execution-state.yaml` provenance and
  verify the authorization is inherited byte-identically from the
  base — satisfied by branching from the actual live main (the
  established W44/W51/W52 branch-point convention).
- Delivery: branch `work-053-economic-allocation` (the name the
  activation packet specifies), single atomic commit, PR against
  main (this PR; the exact head SHA is in the PR body).
- Governance state at dispatch (verified live): W052
  accepted/merged, `WORK-052-CORE-001` superseded; the sole
  active authorization is `WORK-053-CORE-001`; W053 dependencies
  (WORK-051, WORK-052) accepted-merged; the historical PR #124 /
  merge `c9a1f858` lineage NOT reused (superseded; this
  implementation is fresh on the authorized cycle).

## 2. Delivered scope (exactly the authorized scope)

| Path | Content |
|---|---|
| `allocation/` | The EconomicAllocation package (8 modules) |
| `tools/allocation_selftest.py` | The deterministic battery (60 cases) |
| `docs/WORK-053-handoff.md` | Governance handoff (main) + implementation-level append (this PR) |
| `docs/WORK-053-evidence.md` | This evidence record |

Plus the sanctioned **additive-only CI wiring** (the accepted
W042/W051/W052 precedent): one new step `Run economic allocation
tests` (`python3 tools/allocation_selftest.py`) directly after
the usage-ledger battery step in
`.github/workflows/spec-check.yml`. `.github/` is mechanically
governance-classified (`GOVERNANCE_PREFIXES` in
`tools/spec_check.py`), so it is not an implementation delta; the
battery (case_58) verifies the wiring is purely additive and
weakens no step.

Package layout:

```
allocation/
  __init__.py      frozen 75-name public API
  errors.py        typed error model (27-reason vocabulary)
  evidence.py      the external evidence boundary
                   (AllocationEvidenceIndex; billable usage
                   snapshots; external payment/settlement
                   reference citations as DATA-only identity)
  model.py         the value model: subject states, 9 actions,
                   the 10-edge transition table, the rounding
                   vocabulary + exact split arithmetic,
                   command, event, policy-version/allocation-
                   snapshot/settlement-acknowledgement/payment-
                   reference/compensation facts, the fold
                   projection, content-derived ids
  validation.py    admission rules (the payment/settlement/usage
                   kind table, usage finality + statement binding,
                   policy resolution/effective window/split
                   bounds, distribution discipline, reference
                   correlation, finality/compensation/callback
                   gates)
  journal.py       the append-only hash-chained journal +
                   injectable store seam (FileAllocationStore =
                   the only filesystem-write site)
  ledger.py        AllocationLedger public surface + the SINGLE
                   fold (live == replay by construction, full
                   causal re-verification)
  digest.py        the deterministic digest stream
```

**Zero changes under `spec/`** (including `spec/architect/` — the
authorization is inherited, never re-authored); zero changes to
the UsageLedger implementation, any networking authority, W040
physical evidence, payment rails, KYC/KYB, jurisdiction policy,
marketplace discovery, or developer/client runtime surfaces.

## 3. Billable-final-only admission (invariant 1)

Allocation consumes **only** billable-final UsageLedger facts:

- The ONLY allocation-creating action is `ALLOCATE`, and its
  subject citation must resolve in the injected W052 snapshot to
  a `BILLABLE_FINAL` usage transaction (`USAGE_NOT_FINAL` —
  battery case_13 drives a REAL W052 transaction to OBSERVING and
  proves the rejection; case_46 proves the admission/replay
  symmetry with a walk-valid fully-recomputed forgery journal
  over the OBSERVING transaction, with an honest-shaped control
  that loads cleanly against a final snapshot, pinning the
  rejection to the finality gate alone).
- The kind table (case_11 / case_12): a payment reference cited
  as a usage transaction fails closed `PAYMENT_NOT_USAGE`; a
  settlement reference fails closed `SETTLEMENT_NOT_USAGE` —
  payment success, reservation state, offer state, or provider
  callbacks have NO allocation-creating path at all: payment
  references are DATA records that never transition state
  (case_23/case_24), and reservation/offer state produces no
  sealed usage statement to allocate (the W052 layer itself
  requires delivery evidence before BILLABLE_FINAL).

## 4. Immutable policy versions + exact arithmetic (invariants 2-3)

- Every allocation references **exactly one immutable policy
  version** (resolution from the folded registry:
  `POLICY_UNKNOWN` case_15; effective-window selection:
  `POLICY_NOT_EFFECTIVE` case_16; journal-order registration
  requirement: the case_44 variant-D forgery) **and exactly one
  billable-final usage record** (statement binding:
  `USAGE_MISMATCH` case_14; the closed 1:1 usage↔allocation
  identity: `ALLOCATION_ALREADY_EXISTS` case_21 — a second
  ALLOCATE for one usage record is a fail-closed conflict, never
  a second allocation).
- Policy version ids are content-derived over the TERMS ONLY
  (case_37): identical terms always mean the identical immutable
  version (re-registration is the idempotent no-op with no clock
  read and no journal growth); any term change derives a
  genuinely new version id.
- Allocation arithmetic is deterministic, idempotent, and exact:
  integer-only micro amounts (no floats anywhere — the canonical
  JSON subset forbids them), explicit declared rounding (floor /
  half-up / half-even; case_09 pins 19 hand-computed values and
  sweeps 450 distributable × bps × mode combinations for exact
  conservation), idempotency at THREE layers (command id
  case_19; policy-version identity case_37; provider-callback
  identity case_22 — all no-ops with no clock read and no journal
  growth), and conflicting-identity rejection (`COMMAND_CONFLICT`
  case_20, `ALLOCATION_ALREADY_EXISTS` case_21).

## 5. Settled-history immutability + compensations (invariant 4)

- The allocation snapshot is immutable by construction (no
  rewrite/removal API exists; case_35 proves the settled
  snapshot, acknowledgement, and earlier reference history stay
  byte-identical across later append-only facts).
- The settlement acknowledgement happens exactly once
  (`SETTLEMENT_IMMUTABLE` case_30) and cites an external
  settlement reference as DATA.
- Corrections are append-only compensating events for refunds,
  reversals, disputes, chargebacks, and payout failures
  (case_31/case_32/case_33/case_34): they require the SETTLED
  state, are bounded by the distributable amount (the net never
  goes negative), allow one open dispute, and the dispute record
  is non-monetary (amount pinned to 0).

## 6. Exact three-way conservation (invariant 5)

- `adcos + provider + developer == distributable` ALWAYS
  (mechanical model invariant, re-verified by the full replay
  re-derivation — case_43 proves a walk-valid
  split-consistent-but-repriced fact with a fully recomputed
  outer chain still fails closed).
- `distributable + fee + tax + adjustment == gross` ALWAYS
  (explicitly modeled fees/taxes/adjustments; case_18 pins the
  distribution discipline; case_08 pins the golden
  conservations: 930 = 850 + 30 + 57 − 7 → (128, 361, 361); 48 →
  (7, 27, 14); the honest zero-bill → (0, 0, 0) over the REAL
  W052 zero-observation seal).
- The gross re-binds to the **injected W052 usage snapshot** at
  replay (case_43 variant B: a walk-valid internally-consistent
  gross reprice fails closed — a recomputed outer chain cannot
  reprice the allocation fact, exactly mirroring the W052 sealed-
  bill tariff re-binding lesson).
- Payment references remain DATA and never feed arithmetic; no
  regulated funds are moved, custodied, or minted by this Work
  Item.

## 7. External payment boundary (invariants 6-8)

- Payment-provider references identify external movement only:
  the `ExternalReferenceSnapshot` carries the identity, kind, and
  provenance label — deliberately NO amount, counterparty,
  currency, rail, or provider semantics; the ledger never
  computes from them (identity citations only).
- The kind table (case_26/case_27): a settlement acknowledgement
  cannot cite a payment reference (`PAYMENT_NOT_SETTLEMENT`); a
  payment callback cannot cite a settlement reference
  (`SETTLEMENT_NOT_PAYMENT`) — both admission-symmetric at replay
  (case_47: the walk-valid fully-recomputed settlement-kind
  forgery fails closed, with an honest control that loads).
- Correlation (case_29): an external reference whose declared
  usage-transaction correlation disagrees with the cited
  allocation fails closed `REFERENCE_MISMATCH`; fabricated
  citations fail closed `REFERENCE_UNKNOWN` (case_28).
- No payment-provider-specific concept exists in the canonical
  allocation model: the vendor/payment-provider token AST audit
  (case_51) over the whole allocation family; provider-neutral
  kinds and provenance labels only.

## 8. No authority mutation (invariant 9)

The EconomicAllocation layer owns allocation/economic-policy
state only. Structural audits (case_51/case_52/case_55):

- Sanctioned imports ONLY (`protocol.canonicalization` +
  `agent.clock` beyond stdlib value types; AST-audited): the
  usage, commercial, session, path, routing, transport, identity,
  policy, federation, and platform packages are unreachable — no
  shadow authority is constructible, and no authority
  construction/mutation token exists in the family.
- No authority parameters on the public constructors (store +
  clock seam + evidence index only; case_55 pins the
  non-index rejection).
- The frozen public API is pinned at 75 names (case_53).
- Frozen surfaces byte-identical to `origin/main` (case_57):
  architecture, lock, mission, governance, change-control,
  workflow, work-items, dependency-graph, protocol schema, the
  canonical roadmap (yaml + md), and the WORK-053 authorization
  itself.

## 9. Callback determinism (invariant 10)

Failed, duplicate, delayed, and out-of-order provider callbacks
cannot corrupt canonical allocation state (case_22/case_23/
case_24/case_48):

- duplicates are idempotent no-ops (the external reference
  identity is the idempotency key; no journal growth, no clock
  read);
- the duplicate-callback JOURNAL forgery (two walk-valid
  fully-recomputed callback records citing the same external
  identity) fails closed at replay;
- the reference-id multiset, state, and snapshot are
  arrival-order independent while the record identities are
  honestly admission-attributed (the battery PROVES the record-id
  divergence rather than claiming stronger determinism — the W052
  round-1 correction lesson, inherited);
- delayed callbacks after settlement are recorded as
  state-preserving DATA;
- callbacks before any allocation fail closed
  (`ALLOCATION_UNKNOWN`).

## 10. Determinism

- The ONLY time source is the injected WORK-033 clock seam:
  duplicates consume no read; every other submission consumes
  exactly one (case_49 pins 13 golden reads, the three duplicate
  layers, and the gate-rejected read).
- All ids and digests are content-derived over WORK-003 canonical
  JSON; sorted iteration everywhere; integer-only money math with
  explicit declared rounding; no randomness, no UUIDs, no
  wall-clock module, no network access, no vendor API.
- The golden scenario's whole digest stream (journal, state,
  command ledger, event list, evidence index — 6 digest keys) is
  byte-identical across two fresh in-process runs, across fresh
  coexisting worlds (case_59: no cross-world contamination), and
  across PYTHONHASHSEED 0/1/7919/unset subprocesses (case_60).

## 11. Durability and replay integrity

- One append-only hash-chained journal
  (`allocation-journal.jsonl`): atomic command+fact records,
  contiguous sequence, hash-chain ids, persist-then-ack
  (`STORE_FAILED` leaves no phantom state — case_42).
- Load verifies every record id, chain link, sequence, command
  digest, and duplicate command id; byte tamper, line reorder,
  tail truncation, sequence gap, digest edit, and event-id edit
  all fail closed `JOURNAL_CORRUPT` (case_38).
- Journal-first recovery (case_39): reload == live byte-identical
  (state digest + full digest stream); durable idempotency
  survives restart.
- Replay verification (case_40): fold == live for every
  allocation and policy.
- Inserted/out-of-order records fail closed at the walk-linkage
  gate — the replay verifies the WALK, not merely the chain and
  each edge (case_41).
- **The full replay integrity boundary** (the W052 hard-won
  lessons, made structural from the start): the single
  `apply_record` fold re-derives and verifies every
  content-derived fact identity (policy version / allocation
  snapshot / settlement acknowledgement / payment reference /
  compensation), every event identity, every
  command/fact/attribution binding, the walk linkage, the
  allocation's re-binding to the injected W052 usage snapshot
  (gross, statement, BILLABLE_FINAL finality) and to the folded
  immutable policy version (resolution, bounds, effective
  window), the external-reference kind/correlation re-resolution,
  and the FULL allocation arithmetic re-derivation
  (`compute_split` under the declared rounding mode) — so
  WALK-VALID, FULLY-RECOMPUTED-CHAIN fact tampering (cases
  43/44/45/46/47/48: repriced shares, repriced gross, repriced
  policy terms, repriced compensation amounts, forged non-final
  usage consumption, forged settlement-kind citations, and
  duplicated callback identities) all fail closed
  `JOURNAL_CORRUPT`, each with an honest-shaped control journal
  that loads cleanly, pinning the rejection to the exact gate.
- Model-level failures during replay re-derivation map to
  `JOURNAL_CORRUPT` (never crash-open, never admission-shaped
  leak — the `_derive_or_corrupt` boundary).

## 12. Mandated negative cases (the contract's verification list)

| Required negative | Battery case |
|---|---|
| allocation rejects OBSERVED/non-final usage | case_13 (real OBSERVING transaction), case_46 (replay forgery) |
| payment reference cannot create allocation | case_11, case_46 control symmetry |
| settlement reference cannot create allocation | case_12 |
| reservation/offer state cannot create allocation | structurally: no sealed usage statement exists pre-finality (W052 delivery-evidence gate); the finality gate carries the boundary (case_13) |
| fabricated usage citation | case_10 |
| statement mismatch | case_14 |
| unknown policy | case_15 |
| policy not effective | case_16 (expired + not-yet) |
| split out of platform bounds | case_17 |
| distribution invalid | case_18 |
| conflicting command redelivery | case_20 |
| second allocation for one usage record | case_21 |
| payment cited as settlement | case_26, case_47 (replay forgery) |
| settlement cited as payment | case_27 |
| fabricated reference | case_28 |
| correlation mismatch | case_29 |
| re-acknowledgement | case_30 |
| compensation before settlement | case_32 |
| over-compensation | case_33, case_45 (maximal-cascade replay forgery) |
| second dispute | case_34, case_45 |
| callback before allocation | case_24 |
| duplicate callback conflict | case_22 (no-op), case_48 (journal forgery) |
| tampered journal (6 vector classes) | case_38 |
| inserted out-of-order record | case_41 |
| malformed clock | case_54 (`INSTANT_INVALID`) |
| every one of the 27 frozen reasons | case_54 (full vocabulary coverage) |

## 13. Test results

- `python3 tools/allocation_selftest.py`: **PASS 60/60** (two
  consecutive runs byte-identical; the determinism cases are
  in-process two-run and four-subprocess-hash-seed proofs).
- `python3 tools/spec_check.py`: **17/17 PASS** on this head.
- `python3 tools/spec_check.py --provenance`: **ARCH-08 PASS** —
  "implementation delta covered by the active authorization
  inherited from the base" (allocation/** implementation files
  covered by the `allocation/` scope entry; the battery, evidence,
  and handoff docs covered by their exact scope entries;
  `tools/` and `docs/` deltas are governance-classified; zero
  `spec/architect/` changes; the authorization is inherited
  byte-identically).
- Accepted batteries on this branch (the documented PR-context
  scope-guard class, disclosed exactly as the W052 delivery
  disclosed the identical class for the W051 battery):
  `tools/usage_selftest.py` runs **49/49 in the CI context** (its
  case_43/case_44 frozen-surface/PR-delta guards SKIP without the
  `origin/main` ref — CI fetches it only for the final provenance
  step, after the batteries run) and 48/49 in a local strict
  context where case_44 reports the W053 delta outside the W052
  scope — the same documented class that fires for ANY
  non-own-scope pre-merge delta locally; verified in both
  contexts this session (the simulated CI context returns
  49/49). `tools/commercial_selftest.py` likewise runs 38/38 in
  the CI context (case_35 SKIPs) and 37/38 locally (the W051
  scope guard, the exact class the W052 evidence record
  documented). `tools/platformcaps_selftest.py` (the W050
  exact-head CI job) runs **76/76** in both contexts (it never
  fetches origin/main by design). The authoritative check is CI
  on the exact head.
- No local claim of any PHYSICAL result: this environment cannot
  exercise physical devices (W040's obligations remain untouched
  and W040-owned).

## 14. Authority-ownership audit

- The allocation family imports ONLY `protocol.canonicalization`
  (WORK-003) and `agent.clock` (WORK-033) beyond stdlib value
  types (AST-audited, case_52); the WORK-052 UsageLedger, W051
  CommercialCore, W041 NetworkPath, W042 platform, W012 sessions,
  W004 identity, W011 routing, W017 transport, W010 policy, and
  W015 federation packages are unreachable — no shadow authority
  is constructible and the usage family is not even importable
  from `allocation/`.
- No authority construction/mutation tokens (case_51); no
  authority parameters on `AllocationLedger.__init__` /
  `AllocationLedger.load` (store + clock seam + evidence index
  only).
- The battery's authority composition (case_55) drives the REAL
  public production chain only: AgentRuntime session
  establishment, NetworkPathManager lifecycle, PlatformIntegrator
  journal reads, W051 CommercialCore typed commands to
  DELIVERY_COMPLETED, W052 UsageLedger typed commands to
  BILLABLE_FINAL (including the honest zero-observation seal) —
  the allocation's gross 930 is the REAL 310 delivered bytes ×
  the REAL W051 offer price 3, and the allocation cites the REAL
  W052 public statement id.
- Secret hygiene (case_50): journal/digest/index bytes carry no
  key material or credential-like tokens.

## 15. Scope audit (PR delta)

Battery case_58 (plus the CI provenance step, which is the
authoritative enforcement): the PR delta is confined exactly to
the `WORK-053-CORE-001` scope —

- `allocation/` (8 modules), `tools/allocation_selftest.py`,
  `docs/WORK-053-handoff.md` (implementation-level append; the
  governance handoff above stays byte-identical),
  `docs/WORK-053-evidence.md`;
- the single sanctioned additive CI-wiring step (verified purely
  additive: no step removed, no unrelated step added);
- **zero** `spec/` changes, **zero** UsageLedger/networking/
  payment-rail changes, **zero** frozen-architecture changes,
  **zero** changes to any other Work Item's surface.

## 16. Honest evidence disclosure

- This is SOFTWARE-class control-plane/economic evidence only.
  W053 makes **no PHYSICAL claim**: EVID-007 (PARTIAL) and
  EVID-008 (NOT-TESTABLE) remain OPEN and W040-owned; W040
  remains in-review and NOT accepted; nothing here modifies the
  W040 physical-evidence obligations.
- The local test environment cannot run the GitHub CI runner;
  the local results above are honest local executions of the
  exact commands (both strict and simulated-CI contexts
  disclosed). CI success alone is not acceptance — the
  Architect's exact-head review is the gate.
- The replay-integrity boundary is honestly scoped: it re-binds
  every fact to its causal command, the folded policy registry,
  and the injected external index (usage snapshot + reference
  kinds/correlations), and it rejects every walk-valid
  fully-recomputed forgery the battery constructs. Ledger-owned
  caller-declared inputs (fees, policy terms, compensation
  amounts/reasons) are pinned to their causal commands — a
  fully-consistent rewrite of the ENTIRE journal (commands
  included) is the append-only file-discipline adversary
  (W042), outside any hash-chained replay gate's power; this is
  the same trust boundary the accepted W052 battery documents for
  its command-owned amounts.
