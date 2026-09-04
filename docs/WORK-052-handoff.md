# WORK-052 Architect Handoff — UsageLedger

**Issued by:** Architect  
**Work Item:** WORK-052  
**Implementer:** Z.ai  
**Status:** Architect work order issued; implementation is gated on the repository-local W051 acceptance → W052 activation transition.

## Objective

Implement the canonical UsageLedger layer of the ADCOS Commercial Connectivity Control Plane. The ledger must derive billable usage from authoritative delivered-traffic evidence, never from payment capture or reservation/lease state.

## Canonical responsibilities

Implement canonical records and deterministic state/reconciliation behavior for:

- usage observations;
- correlation to authorized delivery/path evidence;
- billable finality;
- reconciliation from observed delivery to billable quantity/amount;
- compensating refunds, reversals, and disputes.

## Required invariants

1. Payment capture never creates usage.
2. Reservation or lease state never creates usage.
3. Usage requires authorized delivery evidence.
4. Historical delivery observations are immutable.
5. Duplicate observations do not double-charge.
6. Delayed and out-of-order observations produce deterministic state.
7. Billable finality is explicit and cannot rewrite prior facts.
8. Corrections are append-only compensating records.
9. Commerce cannot mutate connectivity, session, path, routing, or transport authorities.
10. Unknown, fabricated, stale, or unauthorized evidence fails closed.
11. Provider/payment observations are data, not proof of delivery.
12. Restart and replay reproduce the same ledger projection byte-for-byte.

## Authority boundary

UsageLedger owns usage/economic ledger state only. It may consume authoritative references exposed by existing session, NetworkPath, delivery-evidence, and W051 CommercialCore interfaces, but must not create, mutate, or shadow those authorities.

W042 journal-first/recovery discipline must be reused where applicable. Payment-provider rails, custody, payout execution, KYC/KYB, jurisdiction policy, marketplace discovery, and developer SDKs remain out of scope.

## Determinism and replay

Use the repository's canonical JSON/id/digest conventions and the established WORK-033 clock seam. No randomness, wall-clock reads, vendor SDK coupling, or hidden mutable authority. Exact redelivery must be idempotent. Conflicting reuse of an observation identity must fail closed. Replay/recovery must reproduce the same ledger state and journal/evidence digests.

## Verification required from Z.ai

Provide a dedicated deterministic self-test and CI wiring covering at minimum:

- valid usage ingestion;
- missing/invalid delivery evidence rejection;
- duplicate ingestion with zero double-charge;
- delayed and out-of-order observations;
- immutable historical observations;
- explicit BillableFinal transition;
- reconciliation and audit trail;
- refund/reversal/dispute compensation;
- tamper detection;
- replay/recovery equivalence;
- payment→usage negative cases;
- reservation/lease→usage negative cases;
- authority-boundary/import discipline;
- deterministic two-run and hash-seed checks where applicable.

The delivery PR must include the implementation-level handoff and evidence manifest, exact reviewed SHA, CI results, and scope audit.

## Scope

The eventual W052 authorization is intended to permit only the UsageLedger implementation/test/evidence surfaces necessary to satisfy the WORK-052 contract. Do not modify frozen architecture semantics, unrelated Work Items, existing accepted networking authorities, payment rails, or other commercial Work Items.

## Delivery protocol

The repository-local `WORK-052-CORE-001` authorization will be created only by the Architect in the atomic governance transition that accepts W051 and supersedes `WORK-051-CORE-001`. Until that transition is merged to `main`, Z.ai must not create an implementation branch or open an implementation PR for W052.

After activation, Z.ai must branch from the authorized main baseline, preserve the authorization byte-identically, and open one implementation PR. The PR must identify the authorization id and baseline, changed files, authority boundaries, evidence manifest, test results, and SOFTWARE-only evidence classification. It must not modify `spec/architect/`.

The Architect will review the exact delivery head and either issue corrections or record acceptance. CI success alone is not acceptance.

## Evidence class

W052 is a SOFTWARE-class control-plane implementation. It must make no PHYSICAL claim and must not alter the independent W040 physical-evidence obligations.

---

# Implementation-level handoff (delivered on the W052 branch)

**Appended by the W052 implementation PR under `WORK-052-CORE-001`
(the W041/W042/W051 precedent: the governance-level handoff above
stays on main; this section records what was actually built).
Updated in the correction round responding to the architectural
REQUEST-CHANGES review of the first head: the two P0
replay-integrity corrections (complete causal fact-identity
re-derivation on load/replay; sealed-bill re-binding to the
injected W051 tariff snapshot) and the three P1 corrections
(walk-valid recomputed-chain tamper battery; arrival-order claim
narrowed to the economic fold; refunded/reversed quantity views
separated). The journaled history and every admitted identity
are byte-unchanged across the correction.**

## Package / API surface

```
usage/
  errors.py       UsageError + UsageReasonCode (23-reason frozen vocabulary)
  evidence.py     the external evidence boundary: DeliveryEvidence
                  (kinds: delivered / provider-observed /
                  payment-observed), QuantityClass (reserved /
                  attempted / delivered), CommercialTransactionSnapshot
                  (W051 public-read citation + tariff), UsageEvidenceIndex
                  (the injected immutable snapshot, fail-closed resolution)
  model.py        UsageTransactionState (OBSERVING / BILLABLE_FINAL),
                  UsageAction (observe-usage / seal-billable /
                  record-refund / record-reversal / record-dispute),
                  the frozen 5-edge transition table, UsageCommand,
                  UsageEvent, UsageObservationRecord,
                  SealedBillableStatement, CompensationRecord,
                  UsageTransaction (the fold projection),
                  content-derived ids/digests (WORK-003 canonical JSON)
  validation.py   admission rules: strict payload shapes, the evidence
                  kind table (PAYMENT_NOT_DELIVERY / PROVIDER_NOT_DELIVERY),
                  correlation, window/quantity bounds, delivery
                  eligibility (RESERVATION_NOT_USAGE /
                  TRANSACTION_NOT_DELIVERING), finality and compensation
                  gates
  journal.py      AppendOnlyUsageJournal (hash-chained, append-only,
                  persist-then-ack) + UsageStore / MemoryUsageStore /
                  FileUsageStore (usage-journal.jsonl)
  digest.py       state_digest, command_ledger_digest,
                  evidence_index_digest, assemble_digest_stream
  ledger.py       UsageLedger (the public surface) + the SINGLE fold
                  (apply_record / fold_state) — which is also the SINGLE
                  causal-verification function: replay re-derives every
                  fact identity, event identity, command/fact binding,
                  walk edge, the sealed statement against the injected
                  W051 tariff snapshot, and DELIVERED evidence citations
                  against the injected index (fail-closed JOURNAL_CORRUPT)
```

Public API: 57 frozen names (battery case_39 pins them exactly).
The typed command surface: `observe_usage`, `seal_billable`,
`record_refund`, `record_reversal`, `record_dispute`; the read
surface: `transaction`, `transactions`, `usage_record_ids`,
`reconciliation_statement`, `command_ledger`, `journal_records`,
`journal_digest`, `state_digest`, `digest_stream`, `verify_replay`;
recovery: `UsageLedger.load`.

## The usage model

1. The CALLER builds a `UsageEvidenceIndex` from public reads
   only (the W051 CommercialCore transaction projection for state
   + tariff; the delivery plane's evidence records — the battery
   derives them from the platform journal's cumulative rx/tx
   interface-observation time series) and injects it with the
   WORK-033 clock seam and a store.
2. `observe_usage` admits one observation. DELIVERED-class
   observations cite the authoritative evidence (id + window),
   bounded by the evidence quantity (single and cumulative) and
   window; RESERVED/ATTEMPTED-class observations are DATA (no
   evidence citation, never billable). Two dedup layers
   (command id; evidence-window identity) make duplicates
   idempotent no-ops and conflicting reuse fail closed.
3. `seal_billable` performs the explicit BILLABLE_FINAL
   transition: the statement distinguishes the ACR-009 quantity
   classes, computes amount = billable_quantity ×
   unit_price_micros exactly (integers only), and freezes the
   transaction (late observations fail closed; the zero-bill
   seal is supported).
4. `record_refund` / `record_reversal` / `record_dispute` append
   compensating records against the sealed statement (bounded,
   append-only, disputes non-monetary).
5. `reconciliation_statement` is the deterministic pure read:
   observed -> billable -> compensated -> net + full audit trail
   + projection digest.

## Reference boundaries

The ledger cites W051 transaction ids, W012 session ids, W041
NetworkPath ids, and delivery-plane evidence ids as DATA inside
the injected index records; it never constructs, queries, or
mutates any authority (AST-audited: only `protocol.` and
`agent.clock` imports are sanctioned). Payment and provider
observations enter the index as DATA-only kinds and are
structurally ineligible as usage evidence (the kind table).

## Persistence model

One append-only hash-chained journal (`usage-journal.jsonl` via
`FileUsageStore`): one canonical-JSON line per admitted command +
its derived fact event; record ids bind (sequence, content,
prev-link); command digests are the durable idempotency ledger;
load verifies ids, chain, sequence, digests, duplicate command
ids, and fails closed on non-canonical payload content
(tamper/reorder/truncation/gap/float all fail closed
`JOURNAL_CORRUPT`).

## Replay / recovery behavior

`UsageLedger.load(store, clock, evidence_index)` is the only
continuation path: load, verify the full chain, fold with the
SAME `apply_record` the live manager uses, resume. Live state ==
replayed state byte-identically by construction; both idempotency
layers survive restart; the fold verifies the walk linkage (an
inserted table-legal record whose from_state does not connect to
the folded walk fails closed).

**The replay integrity boundary (the P0 corrections):** the fold
re-derives and verifies, for EVERY journal record —

- the event attribution equals the admitted command's
  attribution;
- the fact kind matches the action (the action/fact table);
- each content-derived fact identity (`observation_id` /
  `statement_id` / `compensation_id`) re-derives from the fact's
  OWN content;
- the `event_id` re-derives from the event's content + the fact
  identity;
- the fact is EXACTLY the deterministic derivation of its causal
  command, the folded state, and the event instant;
- the sealed statement re-derives against the INJECTED W051
  transaction snapshot: tariff unit price, billable unit,
  provenance, and the exact amount
  `billable_quantity * unit_price_micros` (the zero-bill seal is
  tariff-bound identically) — a recomputed chain cannot reprice
  the billable fact;
- DELIVERED observations' evidence citations re-resolve against
  the INJECTED index (kind table, correlation, window, static and
  cumulative quantity caps; duplicate evidence-window identities
  in the journal fail closed — admission de-duplicates, so the
  journal cannot carry both);
- compensations re-verify the bounded-net discipline (cumulative
  ≤ the sealed amount; one open dispute).

Any mismatch fails closed `JOURNAL_CORRUPT`. The battery proves
walk-valid, fully-recomputed-chain fact tampering (fact-only and
maximal-cascade variants for observations, seals, and
compensations) is still rejected (cases 46/47/48).

**Honest boundary:** the journal verifies itself plus the
injected authority anchors; a fully self-consistent
within-authority-bounds rewrite is detectable only against the
externally published digest stream (`journal_digest` /
`digest_stream`) — that is what the digest stream exists for.
No stronger claim is made.

Load requires the injected index to resolve every citation the
journal carries (an index at least as complete as
admission-time; an unresolvable citation at replay is
`JOURNAL_CORRUPT` — fail closed).

## Determinism contract

Injected clock seam only (duplicates: no read; every other
submission: exactly one); content-derived ids; sorted iteration;
integer money; no floats, randomness, wall clock, network, vendor
APIs, or filesystem writes outside the store seam. The golden
digest stream (journal/state/ledger/events/evidence index) is
byte-identical across two fresh runs and PYTHONHASHSEED
0/1/7919/unset.

## Extension points for W053 (advisory only — NOT authorized)

- `reconciliation_statement(transaction_id)` is the intended
  consumption surface for EconomicAllocation: one billable-final
  usage fact per statement (statement_id, billable_quantity,
  gross/net amounts, contributing evidence) with the projection
  digest for correlation.
- `SealedBillableStatement` is immutable and content-addressed;
  W053's allocation plans should reference statement ids exactly
  as compensations do today.
- `UsageReasonCode` and the public API are frozen; extensions
  require their own authorization.
- Dispute resolution (open -> resolved) is deliberately NOT in
  W052: the dispute flag is recorded and the settlement layer
  (W044/W053 boundary) owns resolution semantics.

## Explicit non-scope (unchanged)

W044-W051, W053, payment rails, custody, payout execution,
KYC/KYB, jurisdiction policy, marketplace discovery, developer
SDKs, physical validation (W040's obligations remain W040-owned),
wire-schema changes, frozen-spec modifications, and any change to
`spec/architect/`.

## Physical evidence boundary (unchanged)

W052 is SOFTWARE-class only. No physical claim is made or implied;
EVID-007/EVID-008 remain OPEN and W040-owned; W040 remains
in-review and NOT accepted.
