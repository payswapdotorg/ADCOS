# WORK-051 Evidence Record (CommercialCore)

**Status: delivered for review under authorization `WORK-051-CORE-001`
(DEC-0058). SOFTWARE-class evidence only. NO PHYSICAL claim is made
(the commercial core is a pure software control-plane model; EVID-007
PARTIAL and EVID-008 NOT-TESTABLE remain OPEN and W040-owned; W040
stays in-review and NOT accepted).**

## 1. Authorization and provenance

- Authorization: `spec/architect/authorizations/WORK-051.yaml` —
  `WORK-051-CORE-001`, `status: active`, `authorization_decision:
  DEC-0058`, inherited **byte-identically from main** (unmodified; the
  authorization record is durable provenance and is never touched by
  this PR).
- Architecture basis: ACR-009 — Commercial Connectivity Control Plane
  (ACCEPTED, **DEC-0050**, proposal merged by PR #82); ACR-005
  (DEC-0047), ACR-006 (DEC-0048), ACR-007 (DEC-0049) accepted.
- Authorization baseline (historical, preserved exactly):
  `fe6e6e35a49cb2113315d0ec1569f7e93a3cf200` (the LEDGER-RECON-007
  snapshot baseline).
- Actual implementation branch point (current main at branch cut):
  `9f0ebfc7ecaac6cc12c1ccb27b60c9ea7e69dce8`.
- **Baseline reconciliation analysis (repository-derived, no chat
  reliance):** `tools/spec_check.py` ARCH-03 and ARCH-08 compare the
  authorization `baseline_sha` against the RECORDED
  `execution-state.yaml.repository.main_sha` (`fe6e6e3` — they match),
  never against the live git SHA; ARCH-08 additionally requires the
  authorization inherited byte-identically from the base (satisfied by
  branching from the actual main). This is exactly the W041/W042
  branch-cut convention (W042: authorization baseline `96db8aa` while
  the implementation branch was cut from main `1909479`, one governance
  merge ahead of the recorded snapshot; the reconciliation
  LEDGER-RECON-007 happened at the NEXT acceptance transition).
  Therefore NO pre-implementation reconciliation was performed, the
  durable authorization is preserved exactly, and the next snapshot
  reconciliation (from `fe6e6e3` to the then-current main) belongs to
  the future W051 acceptance transition per the standing
  RECON-002..007 convention. ARCH-03 was NOT weakened.
- Delivery: branch `work-051-commercial-core`, single atomic commit,
  PR against main (this PR; the exact head SHA is in the PR body).

## 2. Delivered scope (exactly the authorized scope)

| Path | Content |
|---|---|
| `commercial/` | The CommercialCore package (8 modules, 3,972 lines) |
| `tools/commercial_selftest.py` | The deterministic battery (35 cases) |
| `docs/WORK-051-handoff.md` | Governance handoff (main) + implementation-level append (this PR) |
| `docs/WORK-051-evidence.md` | This evidence record |

Plus the sanctioned **additive-only CI wiring** (the accepted W042
precedent, PR #110 / DEC-0057): one new step
`Run commercial core tests` (`python3 tools/commercial_selftest.py`)
after the platform battery step in `.github/workflows/spec-check.yml`.
`.github/` is mechanically governance-classified
(`GOVERNANCE_PREFIXES` in `tools/spec_check.py`), so it is not an
implementation delta; the battery (case_35) verifies the wiring is
purely additive and weakens no step.

Package layout:

```
commercial/
  __init__.py      frozen 52-name public API
  errors.py        typed error model (20-reason vocabulary)
  model.py         states/actions/transition table, command, event,
                   transaction projection, content-derived ids
  references.py    the external reference boundary (ReferenceIndex)
  validation.py    admission rules (family table, expiry, settlement)
  journal.py       append-only hash-chained journal + store seam
  digest.py        deterministic digest stream (evidence chain)
  lifecycle.py     CommercialCore public surface + the single fold
```

## 3. The canonical commercial lifecycle (criterion 1)

The full canonical chain is representable, append-only, deterministic,
idempotent, and attributable:

```
CONNECTIVITY_INTENT -> OFFER_SELECTED -> RESERVATION_HELD ->
SESSION_AUTHORIZED -> PATH_ACTIVE -> DELIVERY_STARTED ->
USAGE_ACCRUING -> DELIVERY_COMPLETED -> BILLABLE_FINAL ->
SETTLEMENT_PENDING -> SETTLED
```

with the four compensating terminal states
`CANCELLED / EXPIRED / PATH_FAILED / NON_DELIVERED` (criterion 2).

The frozen transition table has 25 edges (battery case_02 pins it
exactly; case_06 drives EVERY edge to its exact target state; case_07
rejects all 130 illegal (state, action) pairs). Every event carries
full attribution: previous state, new state, action, causal command
id, resolved causal references, actor, source, instant, and a
content-derived event id (case_05).

Attribution model: every journal record is ONE atomic
(admitted-command + resulting-event) append (persist-then-ack); the
command carries the caller's idempotency key and a content-derived
digest, the event carries the transition with its resolved causal
references.

## 4. Determinism (criterion 1)

- The ONLY time source is the injected WORK-033 `AgentClock` seam:
  duplicate redeliveries consume NO clock read; every other
  submission consumes exactly ONE (case_05, case_12; case_18 audits
  that no public method accepts an instant parameter and that the only
  `now()` call site is the clock seam).
- All identities and digests are content-derived over WORK-003
  canonical JSON (`sha256:<hex>` fingerprints; never NodeIDs, never
  trust).
- No randomness, no UUIDs, no wall-clock, no `datetime`/`time`/`os`
  imports anywhere in `commercial/` (case_28 AST audit); iteration is
  sorted.
- **Two-run proof:** the golden scenario (full authority composition ->
  11-command lifecycle -> SETTLED) run twice in-process produces
  byte-identical digests (case_24).
- **Hash-seed proof:** `PYTHONHASHSEED=0 / 1 / 7919 / unset`
  subprocesses agree byte-for-byte on the whole digest stream
  (case_25; verified directly in this session).

Canonical digest stream (golden scenario):

```
journal_digest          sha256:b8e2c16f0a2c41fa6a28c2d10a5c51bb63efee1f9c0bba5bac438695febc3fe4
state_digest            sha256:598fb6c9f9a6a1a70b82f1bd3446d620e0f24d40b1454054a130d50723b95ece
command_ledger_digest   sha256:7dd34898ba55976cabacef87fbc3426f5e115eecf626fa743447dfe238f61b11
event_list_digest       sha256:fd6fc8bd7f44642f30d520c79cfef6cad35a0e1528ded5370b6bce011706687f
digest_stream_sha256    e347b02d75b92410cd70c59580dceb92dd0d29ae924bd1f27bccda9207885f0a
```

## 5. Idempotency and durability

- Command idempotency is DURABLE: the command ledger is journaled with
  each record, so redelivery after restart is a no-op (case_22 proves
  a redelivered command is a `DUPLICATE` on the recovered core).
- Exact duplicate redeliveries: no journal growth, no clock read, no
  state change (case_12).
- Conflicting redeliveries (same command id, different content): fail
  closed `COMMAND_CONFLICT` (case_13).
- The journal is append-only and hash-chained: byte flip, line
  reorder, half-line truncation, sequence gap, command-digest edit,
  and event-id edit all fail closed `JOURNAL_CORRUPT` at load
  (case_20).
- Persist-then-ack: a store failure leaves no phantom journal record
  and no phantom transaction (case_21).
- Journal-first recovery: `CommercialCore.load` reproduces the live
  state byte-identically (journal digest, state digest, command
  ledger, per-transaction projections) and accepts new commands
  (case_22).
- Replay verification: `fold_state(journal) == live state`
  byte-identical for the golden, compensating, and cancellation
  scenarios; the fold is the SINGLE state-derivation function used by
  both the live manager and replay (case_23).

## 6. Compensating families and immutable history (criterion 2)

- **Cancellation**: from every cancellable state
  (ConnectivityIntent..PathActive); terminal; post-cancel commands
  fail closed (case_08).
- **Expiry**: honestly deadline-gated — premature expiry fails closed
  `EXPIRY_NOT_DUE`; authorization/activation past the deadline fails
  closed `RESERVATION_EXPIRED` (the caller must record the explicit
  compensating expire event); wrong-state expiry fails closed
  (case_09; case_06 drives both expiry edges with per-thread
  deadlines).
- **Path failure** and **non-delivery**: compensating records from the
  path/delivery states only (cases 10, 11).
- **Immutable history**: `SETTLED` and every compensating state is
  terminal with NO outgoing table edges; EVERY command on a settled
  transaction (including a fresh settle) fails closed
  `HISTORY_IMMUTABLE` with zero journal/state drift; no public
  mutation API exists on the journal or store (case_15).

## 7. Authority references, never ownership (criterion 3)

- The golden lifecycle runs over REAL authority references: a real
  logical session id from the public WORK-012 session handshake, a
  real ACTIVE NetworkPath id from the WORK-041 manager's public
  reads, real delivery-evidence ids from the WORK-042 platform
  journal's public records, a usage-plane citation, an external
  settlement confirmation, and an external payment observation
  (case_31; case_05 asserts the recorded references).
- The `ReferenceIndex` is an immutable snapshot BUILT BY THE CALLER
  from the authorities' PUBLIC interfaces and injected; the core never
  queries, instantiates, or mutates any authority (no authority object
  ever crosses the boundary).
- Fabricated citations (unknown session / NetworkPath / delivery /
  settlement ids) fail closed `REFERENCE_UNKNOWN`; wrong-family roles
  fail closed (case_17).
- Structural audits: no authority construction/mutation tokens in
  `commercial/`; no authority parameters in the constructor or load;
  the battery itself uses only public surfaces (case_27); sanctioned
  imports only — `protocol.` (canonical JSON) and `agent.clock` (the
  WORK-033 seam); NO authority family is importable in the package
  (case_28).

## 8. Payment / delivery separation (criterion 4)

- Payment-family references can NEVER justify a delivery command:
  `PAYMENT_NOT_DELIVERY` (payment-only and mixed payment+evidence
  citations both rejected; case_16, case_30-11).
- Payment observations are recorded DATA (attachable to
  hold/initiate) and are never settlement confirmations:
  `PAYMENT_NOT_SETTLEMENT` (case_14, case_30).
- Reservation NEVER implies delivery: the table admits
  `DELIVERY_STARTED` only from `PATH_ACTIVE`, and the direct command
  attempt from `RESERVATION_HELD` fails closed (case_16).
- Settlement NEVER implies delivery and is never confused with it:
  `SETTLED` is terminal (no outgoing edges); delivery from settled
  fails `HISTORY_IMMUTABLE` (case_16).
- Settlement integrity: settle requires `SETTLEMENT_PENDING` (the
  BillableFinal chain), a settlement-family confirmation citation, and
  the INTACT recorded delivery-evidence chain — an index that evicted
  the delivery citations fails closed `SETTLEMENT_REJECTED`
  (case_14).
- Delivery facts cannot be rewritten by later commercial events: the
  journal is append-only, the transaction projection is a pure fold,
  and settled history is immutable (cases 15, 20, 23).
- The family-rules table (`ACTION_FAMILY_RULES`) is machine-checked:
  payment is forbidden for every delivery command and for settle;
  delivery evidence is required only for delivery commands; settlement
  confirmations are required only for settle (case_16 audits the
  table).

## 9. No authority mutation, no provider assumptions (criterion 5)

- Commerce cannot mutate connectivity/session/path/routing/transport
  authorities: no authority module is importable in `commercial/`
  (case_28), no authority construction/mutation tokens appear
  (case_27), and the only injected dependencies are the store, the
  clock seam, and the reference index.
- No payment-provider assumptions leak into the core: the vendor token
  scan (case_28) rejects provider names (payment rails, custody,
  payout, KYC/KYB, jurisdiction, discovery, and SDKs are explicitly
  out of scope per the W051 contract; they belong to W044-W049 under
  their own authorizations).
- Secret hygiene: journal, state, and digest-stream bytes carry no key
  material, credentials, or secret-like tokens (case_26).

## 10. Mandated negative cases (16/16)

| # | Negative case | Result (battery case) |
|---|---|---|
| 1 | illegal lifecycle transition | fail closed `LIFECYCLE_ILLEGAL` — all 130 pairs (case_07; case_30-1) |
| 2 | duplicate command | idempotent no-op, zero drift (case_12; case_30-2) |
| 3 | conflicting duplicate | `COMMAND_CONFLICT`, zero drift (case_13; case_30-3) |
| 4 | expired reservation | `RESERVATION_EXPIRED` + honest `EXPIRED` compensating record (case_09; case_30-4) |
| 5 | cancelled reservation | post-cancel commands `LIFECYCLE_ILLEGAL` (case_08; case_30-5) |
| 6 | path failure | compensating record, gated to delivery states (case_10; case_30-6) |
| 7 | non-delivery | compensating record, gated to delivery states (case_11; case_30-7) |
| 8 | settlement before BillableFinal | `LIFECYCLE_ILLEGAL` (case_14; case_30-8) |
| 9 | settlement without delivery evidence | `SETTLEMENT_REJECTED` (case_14; case_30-9) |
| 10 | mutation of settled history | `HISTORY_IMMUTABLE`, zero drift, no mutation API (case_15; case_30-10) |
| 11 | payment success treated as delivery | `PAYMENT_NOT_DELIVERY` (case_16; case_30-11) |
| 12 | fabricated NetworkPath reference | `REFERENCE_UNKNOWN` (case_17; case_30-12) |
| 13 | fabricated session reference | `REFERENCE_UNKNOWN` (case_17; case_30-13) |
| 14 | non-deterministic timestamp | no public instant parameter; malformed instants `INSTANT_INVALID`; clock seam is the only time source (case_18; case_30-14) |
| 15 | malformed commercial event | `EVENT_INVALID` at the model gate (case_19; case_30-15) |
| 16 | tampered commercial record digest | `JOURNAL_CORRUPT` at load (case_20; case_30-16) |

case_30 runs all sixteen in one fail-closed battery with zero journal
drift after every rejection.

## 11. Test results

- `python3 tools/commercial_selftest.py`: **PASS (35/35 cases)**.
- Determinism: two in-process runs byte-identical; PYTHONHASHSEED
  0/1/7919/unset subprocesses byte-identical (md5 of the digest
  stream: `2266999aa72fe2c489d4ea98a8d1ba19` for all four).
- `python3 tools/spec_check.py`: **PASS (17/17)** (2 pre-existing
  ADV-01 advisory lines = the ACR-011-sanctioned W050 advisory edges).
- `python3 tools/spec_check.py --provenance`: **PASS (2/2)** —
  implementation delta (8 files: `commercial/`) covered by the active
  authorization inherited byte-identically from the base.
- `python3 tools/spec_check_selftest.py`: **PASS (32/32)**.
- Mandated sibling batteries: agent 45/45, mobile 45/45, session
  55/55, adapter 56/56, transport 69/69, ipintegration 45/45, schema
  25/25.
- networkpath/platform batteries: all substantive cases pass; the one
  delta-shape guard case per battery (networkpath case_35, platform
  case_30) fails closed in LOCAL branch context on the successor
  files (`commercial/`, the additive CI step) — the documented
  W041/W042 successor-file scope class. Proven to pass in CI
  PR-context via the base-less single-branch clone (below) and to
  pass post-merge via the merged-main simulation (below).
- CI-equivalent proof (the W042 method): a base-less single-branch
  PR-context clone (no `origin/main` ref) runs ALL workflow battery
  steps by exit code; with `origin/main` fetched, the final provenance
  step PASSes (the results are recorded in the PR body / CI evidence
  comment).

## 12. Authority-ownership audit

| Authority | Owner | W051 relationship |
|---|---|---|
| Identity | WORK-004 | untouched; ids are fingerprints, never NodeIDs/trust |
| Logical sessions | WORK-012 | referenced via injected index (public reads); never owned/mutated |
| Routing / policy | WORK-011 / WORK-010 | untouched, not importable |
| NetworkPath | WORK-041 (accepted, DEC-0054) | referenced (public manager reads); never owned/mutated |
| Transport / adapters | WORK-017 / WORK-016 | untouched, not importable |
| Platform / journal discipline | WORK-042 (accepted, DEC-0057) | delivery-evidence citations from its public journal; journal-first discipline referenced, never re-owned |
| Payment rails / custody / KYC | external (W044+ future) | outside ADCOS/W051; payment observations are DATA only |
| Commercial lifecycle | **WORK-051 (this PR)** | the ONE thing the core owns |

No new authority is created: the CommercialCore is a control-plane
authority for commercial state only, exactly as ACR-009 boundary 4-5
and the W051 contract require.

## 13. Scope audit (PR delta)

- Delta confined to `commercial/`, `tools/commercial_selftest.py`,
  `docs/WORK-051-handoff.md`, `docs/WORK-051-evidence.md` (the exact
  WORK-051-CORE-001 scope) plus the sanctioned additive-only
  `.github/workflows/spec-check.yml` CI step (case_35; the W042
  precedent).
- W040 untouched (in-review, NOT accepted; EVID-007/EVID-008 OPEN and
  W040-owned). W041/W042 implementation surfaces byte-identical
  (consumed read-only). W043 retired slot untouched. W044-W050, W052,
  W053 untouched (no code, no authorization).
- No changes in `spec/` (ARCH-08 mechanically enforces; the frozen
  spec set is byte-identical to origin/main — case_34).
- No wire-schema changes. No secrets. No private-method access (the
  battery's public-path discipline is itself audited — case_27).

## 14. Honest evidence disclosure

- This record claims SOFTWARE-class conformance only.
- No PHYSICAL PASS claim is made or implied. W040's physical
  obligations (EVID-007 PARTIAL, EVID-008 NOT-TESTABLE) remain OPEN
  and W040-owned; W040 remains in-review and NOT accepted.
- CI results (spec-check run on the PR head) are authoritative for
  the acceptance gate; this record's local results were produced with
  the same tooling on the same tree.

## 15. Conformance-completion delivery (the W050 merge-isolation era)

Appended by the WORK-051-CORE-001 conformance-completion session. The
sections above are the original PR #117 delivery record, preserved
byte-identically; this section is the second delivery under the same
authorization, appended per the W041/W042 delivery-record convention.

### 15.1 Context and reconnaissance findings

The Architect's W050 merge-isolation directive reconstructed the
accepted WORK-050 delivery onto the authoritative mainline
`fc3ace9c45b77bae36fe757a5629bc197fd906e4` (retaining exactly the four
accepted W050 stages, none of the 129-commit unrelated commercial
ancestry) and merged it: the resulting mainline is
`815f4febbc64d55d3576386e65adaa6244c4f7cb`. WORK-051 execution then
resumed from that exact SHA under WORK-051-CORE-001 (the authorization
present on that mainline, byte-identically inherited).

Reconnaissance against `815f4fe` found:

- The canonical CommercialCore implementation (the eight-module
  `commercial/` package, this battery, and these two documents) is
  ALREADY ON that mainline: it was delivered on branch
  `work-051-commercial-core` (head `9474328`) and merged by PR #117
  into the `fc3ace9` ancestry. Its battery passed 35/35 on the
  post-W050 mainline; `tools/spec_check.py` passes 17/17 there; the
  lifecycle, boundary, and determinism semantics conform to the
  directive's frozen contract (verified section by section below).
- The governance ledger still records WORK-051 as `registered`/active
  with no accepted delivery (the PR #117 merge predates any acceptance
  transition record); per the standing convention the acceptance
  transition is the Architect's, not this delivery's. This delivery
  therefore changes no governance record.

### 15.2 The out-of-order replay finding and the correction

The directive's permanent-battery obligations include the named
category **out-of-order events**. Building that vector empirically
exposed a real gap in the ORIGINAL core, demonstrated before the fix
by a constructed probe: a journal record whose event is table-legal,
action-coherent, family-correct, and fully recomputed (event_id,
command digest, hash chain, contiguous sequences all valid) but whose
declared `from_state` does not connect to the folded walk — e.g.
`activate_path SESSION_AUTHORIZED -> PATH_ACTIVE` inserted while the
walk is at `OFFER_SELECTED` — was **ACCEPTED** by
`CommercialCore.load`; the folded history silently skipped states.
The existing integrity checks (chain, sequence, digests, per-edge
table legality, command/event pairing) verified the CHAIN and each
EDGE but never the WALK.

The correction (fail-closed only, no API change, no behavior change
for honest journals, which are contiguous walks by construction
because admission emits `from_state` = the live transaction state):

1. `commercial/lifecycle.py` — `apply_record` now verifies the
   walk linkage at replay: the event's declared `from_state` MUST be
   the folded current state (`JOURNAL_CORRUPT` otherwise), and the
   creation record must be the `CONNECTIVITY_INTENT` self-edge.
2. `commercial/model.py` — `CommercialEvent` now enforces
   action-target coherence at the model gate: an event claiming
   action A must land in `ACTION_TARGET_STATE[A]` (an incoherent
   attribution such as a settle event landing in `OFFER_SELECTED`
   fails closed `EVENT_INVALID`, at construction AND at
   deserialization, whatever the chain integrity).

The replay now verifies the WALK, not merely the chain and each edge.
All 35 original cases pass unchanged on the corrected core (the
golden digest stream is byte-identical: `e347b02d75b92410cd70c595`).

### 15.3 The fourteen-category permanent-battery mapping

| Directive category | Covering battery vectors |
|---|---|
| lifecycle completeness | case_02, case_05, case_06 |
| transition legality | case_02, case_06, case_07 (all 130 illegal pairs) |
| idempotency | case_12, case_22 (durable across restart) |
| duplicate events | case_12, case_13, case_20 (duplicate command ids at load/append) |
| out-of-order events | **case_36** (admission, model gate, replay walk-linkage) + case_07 + case_20 (byte-level disorder) |
| compensating events | case_08, case_09, case_10, case_11 |
| reservation/payment ≠ delivery | case_16, case_02 (table structure), case_14 |
| delivery immutability | **case_37** + case_15, case_02, case_10/11 gates |
| cross-authority reference integrity | case_17, case_31, case_32 |
| authority/import boundaries | case_27, case_28, case_34 |
| determinism | case_24, case_18, case_03/04 (content-derived ids) |
| hash-seed independence | case_25 |
| fresh-world independence | **case_38** + per-vector fresh `_world()` fixtures |
| replay/recovery integrity | case_22, case_23, case_21, case_36(3) |

The three bolded vectors are this delivery's additions (case_36,
case_37, case_38); the remaining eleven categories were already
explicitly covered by the original battery and are unchanged.

### 15.4 Test results (this delivery, on the delivery branch)

- `python3 tools/commercial_selftest.py`: **PASS (38/38 cases)**.
- Determinism: two consecutive in-process runs byte-identical;
  PYTHONHASHSEED=0/1/7919/unset full-battery subprocess runs all
  byte-identical to the in-process baseline.
- `python3 tools/spec_check.py`: **PASS (17/17)** — the delivery
  delta is confined to the WORK-051-CORE-001 scope
  (`commercial/lifecycle.py`, `commercial/model.py`,
  `tools/commercial_selftest.py`, this document, and the handoff
  append), covered by the active authorization inherited
  byte-identically from the base.
- `python3 tools/spec_check.py --provenance`: **PASS (2/2)**.
- The platformcaps battery (the merged WORK-050 delivery) passes
  76/76 on this branch, byte-identical output.
- Known sibling-battery conditions (inherited, disclosed, the
  documented successor-file/PR-context guard class — the same class
  the original delivery disclosed in §11): on this delivery branch,
  six sibling batteries fail exactly ONE guard case each, every one
  of them a delta-shape/frozen-spec guard correctly reacting to
  ANOTHER work item's delivery files on the branch:
  `energy` case_26 and `telemetry` case_24 (frozen-docs whitelist:
  this delivery's two documents are W051 files), `networkpath`
  case_35 and `platform` case_30 (delta outside THEIR authorized
  scopes), `management` case_32 and `simulator` case_38 (PR-delta
  expectations vacuous outside their own delivery PR). All six pass
  on the base mainline for energy/networkpath/platform/telemetry
  (measured: the 815f4fe mainline runs them green) and resolve on
  merge; management/simulator remain the chronic main-checkout
  artifacts documented above. No substantive case fails anywhere:
  every failing case is a scope guard, and the delivery's own
  battery plus every substantive sibling case passes.

### 15.5 Honest disclosure

- This delivery makes NO governance change: no ACR, no decision
  record, no ledger/state edit, no spec/ change (case_34 enforces
  byte-identity of the frozen surfaces against the base). The WORK-051
  acceptance transition remains the Architect's.
- The §15.2 finding is disclosed as a correction to the PR #117
  delivery's core (two fail-closed checks added; nothing rewritten,
  no historical journal invalidated — every honest journal ever
  produced by the original core remains a contiguous walk and loads
  unchanged).
- SOFTWARE-class evidence only; no PHYSICAL claim. W040 stays
  in-review, NOT accepted; EVID-007/EVID-008 remain OPEN and
  W040-owned.
