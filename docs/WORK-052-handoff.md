# WORK-052 Architect Handoff — UsageLedger

**Issued by:** Architect
**Work Item:** WORK-052
**Authorization:** WORK-052-CORE-001
**Decision:** DEC-0059
**Baseline:** fe6e6e35a49cb2113315d0ec1569f7e93a3cf200
**Implementer:** Z.ai

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

The authorization permits changes only to the UsageLedger implementation/test/evidence surfaces necessary to satisfy the WORK-052 contract. Do not modify frozen architecture semantics, unrelated Work Items, existing accepted networking authorities, payment rails, or other commercial Work Items.

## Acceptance gate

This handoff does not accept the implementation. Z.ai must deliver a PR from a branch cut from this authorized baseline. The Architect will review the exact PR head against the nine invariants, dependency readiness, authority ownership, provenance, replay/recovery, failure semantics, deterministic verification, and evidence-class rules before acceptance.

**No authorization for WORK-053 or any W044–W050 item is granted by this handoff.**
