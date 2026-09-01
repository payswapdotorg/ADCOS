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
