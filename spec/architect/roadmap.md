# ADCOS Authoritative Roadmap

**FROZEN — Roadmap Version 1.3**

`spec/architect/roadmap.yaml` is the sole canonical program roadmap. This document is its human-readable projection. Neither this file nor the roadmap grants implementation authority. The roadmap version advanced from 1.2 to 1.3 by DEC-0087 — a sequencing/governance transition only; Architecture Version 1.0 and Protocol Version 1.0 are unchanged.

## Current repository state

R2 is active under WORK-054. The live implementation baseline was reconciled by DEC-0086; the sequencing correction in DEC-0087 does not change the active Work Item or authorization.

**R0 is complete**: the canonical mainline restoration was accepted and merged as PR #8 on the exact frozen main `3bdfb6d` (merge `a3391e8`, tree `1d16c24`, byte-identical to the historical restoration tree `7fb47bb`). W048 remains explicitly accepted-but-not-restored.

**R1 is complete**: the durable governance projections were reconciled by DEC-0084 and merged as PR #9 (`13bfbda`).

**R2 is active**: DEC-0085 activates WORK-054 — System Composition Conformance — with the sole active implementation authorization `WORK-054-CORE-001`; DEC-0086 reconciles its live implementation baseline.

## Frozen execution roadmap

### R0 — Canonical accepted-mainline restoration — COMPLETE

Restore the exact accepted W044–W049 implementation packages, evidence manifests, handoffs, and required CI battery wiring onto the authoritative mainline without importing unrelated later ancestry or changing frozen semantics.

### R1 — Governance reconciliation — COMPLETE

Synchronize the durable governance projections to the restored mainline while preserving prior decisions and provenance.

### R2 — System composition conformance — ACTIVE

WORK-054 proves the complete connectivity-commercial chain:

`intent → offer → eligibility → reservation/lease → candidate selection → NetworkPath validation → containment → session → delivered traffic → usage → BILLABLE_FINAL → allocation → external payment reference → reconciliation`

The seven mandatory negative proofs and explicit W048 fail-closed behavior remain controlling acceptance conditions.

### R3 — Protocol production conformance — NEXT GATE

R3 is the **sole next sequential gate after R2**. Complete the production conformance layer required before declaring wire compatibility: canonicalization and canonical encoding profiles, signature coverage, version negotiation, unknown-extension behavior, idempotency/replay, schema evolution, migration compatibility, and deterministic digest stability.

### R4 — Physical connectivity validation — PARALLEL AFTER R3

Continue W040 and the open physical-evidence obligations on real hardware/network environments. R4 is independently collected, classified, and accepted. Software evidence never closes this track. R4 does **not** block R5 or the later R6 gate.

### R5 — Developer Connectivity Platform — PARALLEL AFTER R3

Use accepted W046 as the foundation for a production developer surface. External applications request connectivity through stable APIs and webhooks without adopting an ADCOS UI or knowing provider, access technology, route implementation, or payment-rail internals. R5 begins only after R3; R4 completion is not required.

### R6 — Provider onboarding and federation — AFTER R5

Enable independently operated networks, ISPs, carriers, enterprises, satellite systems, hotspots, mesh operators, and infrastructure owners to expose connectivity through ADCOS while retaining infrastructure authority. R6 requires accepted R5; R4 completion is not a prerequisite unless a future durable decision explicitly changes the sequence.

### R7 — Universal connectivity commerce — AFTER R6

Normalize heterogeneous connectivity resources into programmable offers selected by intent, policy, evidence, availability, geography, quality, and price. ADCOS coordinates the transaction and lifecycle; it does not need to own the underlying network.

### R8 — Resilience, mobility and scale — AFTER R7

Harden failover, multipath, mobility, local-first operation, offline/reconnect, reconciliation, disaster recovery, key rotation/revocation, upgrades, rollback, federation scale, and operational observability.

### R9 — Future access technology — AFTER R8

Add new access technologies strictly through the adapter boundary without changing the protocol core.

## Canonical program sequence

`R0 → R1 → R2 → R3 → R4/R5 → R6 → R7 → R8 → R9`

R4 and R5 are parallel tracks after R3. R6 waits for R5, not R4.

## The Stripe-of-connectivity exit criterion

ADCOS is successful when an external application can request connectivity by API; ADCOS can evaluate policy and eligible offers, reserve capacity, select and validate a path, establish controlled connectivity, meter delivered usage, finalize billing, allocate economic value, integrate with an external payment provider, reconcile provider events, and expose canonical status through API/webhooks — while the application remains independent of the underlying access technology, network operator, and payment rail.

## Source-of-truth rule

A clean clone of `main` is the starting point for every new Architect, implementation agent, or recovery operation. Conversation history is never required to discover what to build or whether building is permitted.

The authority chain is:

`mission → frozen architecture/locks → frozen Work Item contract + dependency graph → frozen roadmap.yaml → accepted decisions + execution ledger/state → active authorization → implementation evidence`

`roadmap.md` is only a projection. Issues, PR discussions, chat messages, old handoffs, and external planning documents cannot override `roadmap.yaml`.
