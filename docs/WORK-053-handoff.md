# WORK-053 Architect Handoff — EconomicAllocation

**Issued by:** Architect
**Work Item:** WORK-053
**Implementer:** Z.ai
**Status:** Architect work order issued; implementation remains gated on the repository-local W052 acceptance -> W053 activation transition.

## Objective

Implement the canonical EconomicAllocation layer of the ADCOS Commercial Connectivity Control Plane. It converts **billable-final UsageLedger facts** into immutable developer/provider/ADCOS allocation records under a versioned economic policy, while keeping actual payment movement outside ADCOS behind an explicit provider boundary.

## Canonical responsibilities

- versioned economic policy records;
- developer/provider/ADCOS revenue allocation;
- exact arithmetic, currency precision, and declared rounding;
- immutable allocation snapshots;
- external payment-provider intent/transfer/reference data as DATA only;
- settlement acknowledgements and reconciliation references;
- compensating allocation events for refunds, reversals, disputes, chargebacks, and payout failures.

## Required invariants

1. Allocation consumes only billable-final UsageLedger facts; payment success, reservation state, offer state, or provider callbacks never create allocation.
2. Every allocation references exactly one immutable economic-policy version and exactly one billable-final usage record.
3. Allocation arithmetic is deterministic and idempotent, including explicit currency precision and rounding.
4. Settled historical allocations are immutable; corrections are append-only compensating events.
5. Provider + developer + ADCOS allocations sum exactly to the declared billable amount after explicitly modeled fees, taxes, and adjustments.
6. Payment-provider references identify external movement only; they are never commercial truth.
7. This Work Item does not custody, mint, or directly move regulated funds.
8. No payment-provider-specific concepts leak into the canonical allocation model.
9. Economic state cannot mutate identity, session, routing, NetworkPath, transport, or packet authorities.
10. Failed, duplicate, delayed, and out-of-order provider callbacks remain deterministic and cannot corrupt canonical allocation state.

## Authority boundary

EconomicAllocation owns allocation/economic-policy state only. It consumes public UsageLedger billable-final projections and public commercial references as DATA. It must not create, mutate, or shadow UsageLedger, connectivity/session/path/routing/transport authorities, or payment-provider authority.

W052 is the economic source of usage truth. Payment adapters (W044) remain a later external movement boundary; W053 must not become a payment integration.

## Determinism and replay

Use the repository's canonical JSON/id/digest conventions and the WORK-033 clock seam where time is needed. No wall-clock reads, randomness, UUIDs, vendor SDKs, or hidden mutable authority. Exact command redelivery must be idempotent. Conflicting identities, stale/unknown usage, and invalid policy references fail closed. Replay/recovery must reproduce the same allocation projection and audit/digest stream byte-for-byte.

## Verification required from Z.ai

Provide a dedicated deterministic self-test covering at minimum:

- immutable policy versions and effective-date selection;
- developer-selected provider/developer split within platform constraints;
- exact arithmetic and explicit rounding/currency precision;
- allocation idempotency and conflicting identity rejection;
- allocation requires BILLABLE_FINAL usage and rejects OBSERVED/RECONCILED usage;
- payment/reservation/offer negative cases;
- exact three-way sum conservation after fees/taxes/adjustments;
- external payment reference correlation as DATA only;
- settlement acknowledgement and reconciliation;
- duplicate, delayed, and out-of-order callbacks;
- refund/reversal/dispute/chargeback/payout-failure compensations;
- tamper detection, journal integrity, and replay/recovery;
- authority-boundary/import discipline and no provider coupling;
- two-run and hash-seed determinism proofs where applicable.

The delivery PR must contain an implementation-level evidence manifest, exact reviewed SHA, authorization id/baseline, scope audit, CI results, and SOFTWARE-only evidence classification.

## Scope

The eventual `WORK-053-CORE-001` authorization is intended to permit only the EconomicAllocation implementation, deterministic battery, evidence/handoff documentation, and sanctioned additive CI wiring required to satisfy this contract.

Do not modify frozen architecture semantics, the UsageLedger implementation, networking authorities, W040 physical evidence, payment rails, KYC/KYB, jurisdiction policy, marketplace discovery, or developer/client runtime work.

Do not modify `spec/architect/` from the implementation PR.

## Delivery protocol

This document is the Architect's handoff only. It **does not authorize implementation**.

The Architect has persisted W052 acceptance and this governance transition activates exactly one `WORK-053-CORE-001` repository-local authorization on `main`. Z.ai may now create the single W053 implementation branch from the exact live mainline carrying that authorization.

After activation, Z.ai must branch from the authorized main baseline, preserve the authorization record byte-identically, implement only the authorized scope, and open one implementation PR. The Architect reviews the exact delivery head; CI success alone is not acceptance.

## Evidence class

W053 is SOFTWARE-only control-plane/economic evidence. It must not make or imply a PHYSICAL claim and must not modify W040's independent evidence obligations.

## Current activation packet

**Activation decision:** `DEC-0061` (atomic W052 acceptance → W053 activation).
**Authorized main baseline:** `bcaf0d0677437d1ffca8f5e493cab516c87e7194`.
**Work Item:** `WORK-053`.
**Authorization:** `WORK-053-CORE-001`.
**Dependencies:** `WORK-052` (accepted/merged at this transition).
**Implementation branch:** `work-053-economic-allocation`.
**Implementation PR:** one PR only.
**Historical note:** former PR #124 / merge `c9a1f858` belongs to a superseded lineage and is not current implementation state.

---

# Implementation-level handoff (delivered on the W053 branch)

**Appended by the W053 implementation PR under `WORK-053-CORE-001`
(the W041/W042/W051/W052 precedent: the governance-level handoff
above stays on main; this section records what was actually
built).**

## Package / API surface

```
allocation/
  errors.py       AllocationError + AllocationReasonCode (27-reason
                  frozen vocabulary)
  evidence.py     the external evidence boundary: BillableUsageSnapshot
                  (the W052 public usage-transaction citation: state,
                  sealed statement, gross, W052-side compensation DATA),
                  ExternalReferenceSnapshot (payment / settlement kinds;
                  identity citations only -- no amounts, no provider
                  semantics), AllocationEvidenceIndex (the injected
                  immutable snapshot, fail-closed resolution)
  model.py        PolicySubjectState (REGISTERED) /
                  AllocationSubjectState (PLANNED / SETTLED),
                  AllocationAction (9 actions), the frozen 10-edge
                  transition table, RoundingMode (floor / half-up /
                  half-even) + apply_rounding + compute_split (the
                  exact integer three-way split), AllocationCommand,
                  AllocationEvent, PolicyVersion (terms-derived
                  immutable version identity), AllocationSnapshot (the
                  immutable three-way fact with MECHANICAL conservation
                  invariants), SettlementAcknowledgement,
                  PaymentReferenceRecord (DATA), AllocationCompensationRecord
                  (refund / reversal / chargeback / payout-failure /
                  dispute), AllocationTransaction (the fold projection),
                  content-derived ids/digests (WORK-003 canonical JSON)
  validation.py   admission rules: strict payload shapes, the
                  payment/settlement/usage kind table
                  (PAYMENT_NOT_USAGE / SETTLEMENT_NOT_USAGE /
                  PAYMENT_NOT_SETTLEMENT / SETTLEMENT_NOT_PAYMENT),
                  usage finality + statement binding, policy resolution
                  / effective window / split bounds, distribution
                  discipline, reference correlation, finality and
                  compensation gates, callback duplicate detection
  journal.py      AppendOnlyAllocationJournal (hash-chained,
                  append-only, persist-then-ack) + AllocationStore /
                  MemoryAllocationStore / FileAllocationStore
                  (allocation-journal.jsonl)
  digest.py       state_digest (policy registry + sorted allocation
                  projections), command_ledger_digest,
                  evidence_index_digest, assemble_digest_stream
  ledger.py       AllocationLedger (the public surface) + the SINGLE
                  fold (apply_record / fold_state over the
                  AllocationFoldState: policies + allocations) -- which
                  is also the SINGLE causal-verification function:
                  replay re-derives every fact identity, event
                  identity, command/fact binding, walk edge, the
                  allocation against the injected W052 usage snapshot
                  (gross / statement / BILLABLE_FINAL) and the folded
                  policy version (resolution / bounds / effective
                  window) with the FULL arithmetic re-derivation, and
                  the external-reference kind/correlation re-resolution
                  (fail-closed JOURNAL_CORRUPT)
```

Public API: 75 frozen names (battery case_53 pins them exactly).
The typed command surface: `register_policy`, `allocate`,
`acknowledge_settlement`, `record_payment_reference`,
`record_refund`, `record_reversal`, `record_chargeback`,
`record_payout_failure`, `record_dispute`; the read surface:
`policy`, `policies`, `allocation`, `allocations`,
`allocation_statement` (the deterministic reconciliation
statement), `command_ledger`, `journal_records`, `journal_digest`,
`state_digest`, `digest_stream`, `verify_replay`; recovery:
`AllocationLedger.load`.

## The allocation model

1. The CALLER builds an `AllocationEvidenceIndex` from public
   reads only (the WORK-052 UsageLedger transaction projection for
   the state + sealed statement + compensation DATA; the external
   settlement/payment planes for reference citations) and injects
   it with the WORK-033 clock seam and a store.
2. `register_policy` registers one immutable economic policy
   version. The version id is content-derived over the TERMS ONLY
   (the ADCOS platform share in basis points, the
   developer-selectable provider-share constraint bounds, the
   declared rounding mode, the currency and minor-unit precision,
   the effective window): identical terms always mean the
   identical version (re-registration is the idempotent no-op);
   any term change is a genuinely new version.
3. `allocate` consumes ONE billable-final usage fact (the ONLY
   allocation-creating action): the cited usage transaction must
   be BILLABLE_FINAL in the injected W052 snapshot (payment,
   reservation, offer, or provider-callback state never creates
   allocation), the cited sealed statement must match, the cited
   policy version must be folded and effective at the
   deterministic instant, and the developer-selected provider
   share must lie within the policy bounds. The three-way split
   is the exact integer derivation under the declared rounding
   mode: adcos = round(distributable x adcos_bps / 10^4); the
   post-ADCOS residual is split by the provider share; the
   developer share is the exact remainder -- conservation is
   mechanical (model invariant + full re-derivation at replay).
   Exactly one allocation exists per billable-final usage record.
4. `record_payment_reference` records one external
   payment-provider callback as DATA: never transitions state,
   never creates or reprices allocation, never carries amounts or
   provider semantics; duplicate callbacks are idempotent no-ops
   and failed/delayed/out-of-order callbacks cannot corrupt
   canonical allocation state.
5. `acknowledge_settlement` records the settlement
   acknowledgement citing an external settlement reference (the
   explicit PLANNED -> SETTLED transition, exactly once).
6. `record_refund` / `record_reversal` / `record_chargeback` /
   `record_payout_failure` / `record_dispute` append compensating
   allocation events against the settled allocation (bounded by
   the distributable amount, net never negative, one open
   dispute, disputes non-monetary).
7. `allocation_statement` is the deterministic pure read: usage
   citation -> policy citation -> exact split + conservation ->
   references -> settlement -> compensations -> net + full audit
   trail + projection digest.

## Reference boundaries

The ledger cites W052 usage transaction/statement ids, W051
commercial citations, and external payment/settlement reference
ids as DATA inside the injected index records; it never
constructs, queries, or mutates any authority (AST-audited: only
`protocol.` and `agent.clock` imports are sanctioned; the usage
family is not importable from allocation/). ADCOS neither
custodies nor moves regulated funds: the external reference model
records identity citations only, and no payment-provider-specific
concept exists anywhere in the canonical allocation model
(vendor-token AST audit).

## Persistence model

One append-only hash-chained journal
(`allocation-journal.jsonl` via `FileAllocationStore`): one
canonical-JSON line per admitted command + its derived fact
event; record ids bind (sequence, content, prev-link); command
digests are the durable idempotency ledger; load verifies ids,
chain, sequence, digests, duplicate command ids, and fails closed
on non-canonical payload content (tamper/reorder/truncation/
gap/digest-edit/event-id-edit all fail closed `JOURNAL_CORRUPT`).
Recovery is journal-first: `AllocationLedger.load` verifies the
full chain, folds with full causal re-verification (including
the admission/replay-symmetric usage-finality, policy, split,
distribution, reference-kind, bound, and duplicate gates), and
resumes; live state and replayed state are byte-identical by
construction (the same single `apply_record`).
