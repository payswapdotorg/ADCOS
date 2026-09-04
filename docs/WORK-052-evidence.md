# WORK-052 Evidence Manifest — UsageLedger

**Status:** Architect-issued evidence obligation manifest; implementation results are recorded by Z.ai on the delivery PR and reviewed by the Architect.

## Evidence classification

All W052 implementation and automated verification evidence is SOFTWARE-class. No physical-device or production-network claim may be inferred from a software PASS. W040 remains the independent owner of open physical evidence obligations EVID-007/EVID-008.

## Required evidence

| Area | Required proof |
|---|---|
| Usage admission | Valid usage requires authoritative delivered-traffic evidence. Missing, stale, fabricated, malformed, or unauthorized evidence fails closed. |
| Non-derivation | Payment capture never creates usage. Reservation/lease state never creates usage. Provider/payment observations remain data, never delivery proof. |
| Identity/correlation | Usage observations correlate deterministically to the authorized delivery/path evidence identity and relevant commercial/session context without creating a second authority. |
| Idempotency | Exact duplicate observations do not double-charge; conflicting reuse of an observation identity fails closed. |
| Ordering | Delayed and out-of-order observations yield deterministic ledger state independent of arrival order where the frozen contract requires reconciliation. |
| Immutability | Historical delivery observations and prior usage facts are immutable; corrections append compensating records rather than rewriting history. |
| Finality | BillableFinal is explicit and cannot rewrite prior facts. |
| Reconciliation | Observed delivery reconciles deterministically to billable quantity/amount with a complete audit trail. |
| Compensation | Refunds, reversals, and disputes are represented as append-only compensating records. |
| Tamper resistance | Tampered observations, evidence bindings, digests, snapshots, and replay material fail closed. |
| Recovery | Restart/replay reproduces ledger projection and journal/evidence digests byte-for-byte. |
| Authority boundary | No identity, session, NetworkPath, routing, transport, payment, or delivery authority is created, mutated, or shadowed. |
| Determinism | Two consecutive battery runs are byte-identical; hash-seed checks are byte-identical where applicable; no wall clock/randomness/vendor SDK dependency. |
| Scope | Delivery delta is confined to the WORK-052-CORE-001 authorization; `spec/architect/` remains untouched by implementation. |

## Delivery evidence section

The implementation PR must append the exact reviewed SHA, CI results, test counts, deterministic digests, scope audit, authority-boundary findings, and correction-round history here. No result is implied before the Architect reviews the exact delivery SHA.
