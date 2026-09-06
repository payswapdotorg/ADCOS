# ADCOS Authoritative Roadmap

**FROZEN — Roadmap Version 1.5**

`spec/architect/roadmap.yaml` is the sole canonical program roadmap. This document is its human-readable projection. Neither this file nor the roadmap grants implementation authority. The roadmap version is 1.5 under DEC-0097; Architecture Version 1.0 and Protocol Version 1.0 are unchanged.

## Current repository state

R3 is complete. R5 is complete under DEC-0094. R6 is now complete under DEC-0097: WORK-057 was accepted at `58eced2` and guarded-merged as PR #23 (`a08ce85`). Its sole implementation authorization `WORK-057-CORE-001` is closed. R7 is the next unlocked program gate but is not activated. W040 remains an independent R4 physical track in-review.

**R0 is complete**: the canonical mainline restoration was accepted and merged as PR #8 on the exact frozen main `3bdfb6d` (merge `a3391e8`, tree `1d16c24`, byte-identical to the historical restoration tree `7fb47bb`). W048 remains explicitly accepted-but-not-restored.

**R1 is complete**: the durable governance projections were reconciled by DEC-0084 and merged as PR #9 (`13bfbda`).

**R2 is complete**: WORK-054 proved the complete connectivity-commercial chain and seven mandatory negative proofs. The strict chain remains `BLOCKED_MISSING_AUTHORITY` at W048 because W048 is accepted-not-restored; no W048 implementation was recreated or substituted.

**R3 is complete**: WORK-055 established the production conformance layer over the WORK-032 foundation. Its final delivery `0fc86aa` was accepted after adversarial review and merged as `7801549c`. In-repo conformance evidence does not constitute independent external interoperability evidence.

**R5 is complete**: DEC-0094 accepted WORK-056 — Developer Connectivity Platform Production Hardening — after the 56/56 developer battery, 55/55 W054 composition battery including the real CI `case_51`, repeat/determinism evidence, scope/ancestry proof, and architecture-preservation review.

**R6 is complete**: DEC-0097 accepted the corrected WORK-057 delivery. Round 1 had two P0 blockers under DEC-0096: adapter certification authority bypass and proposer self-acceptance of federation. Round 2 corrected both, added targeted adversarial coverage through case 80, and was accepted at exact head `58eced2` and merged as `a08ce85`. The cross-network PR CI path remained `action_required`, so worker-local test evidence was not represented as CI evidence.

## Frozen execution roadmap

### R0 — Canonical accepted-mainline restoration — COMPLETE

Restore the exact accepted W044–W049 implementation packages, evidence manifests, handoffs, and required CI battery wiring onto the authoritative mainline without importing unrelated later ancestry or changing frozen semantics.

### R1 — Governance reconciliation — COMPLETE

Synchronize the durable governance projections to the restored mainline while preserving prior decisions and provenance.

### R2 — System composition conformance — COMPLETE

WORK-054 proved the complete connectivity-commercial chain:

`intent → offer → eligibility → reservation/lease → candidate selection → NetworkPath validation → containment → session → delivered traffic → usage → BILLABLE_FINAL → allocation → external payment reference → reconciliation`

The seven mandatory negative proofs passed. The containment edge correctly failed closed because W048 is absent from current mainline; downstream stages were not entered and no production-composition claim was made.

### R3 — Protocol production conformance — COMPLETE

WORK-055 completed the production conformance layer required before declaring wire compatibility: canonicalization and canonical encoding profiles, golden vectors, signature coverage, version negotiation and downgrade resistance, unknown-field/extension behavior, replay/idempotency, schema evolution and migration compatibility, compatibility vectors, deterministic digest stability, and strict evidence/authority separation.

R3 remains bounded to verification. It did not modify frozen protocol semantics or wire schemas. External interoperability is still a separate evidence obligation.

### R4 — Physical connectivity validation — PARALLEL AFTER R3

Continue W040 and the open physical-evidence obligations on real hardware/network environments. R4 is independently collected, classified, and accepted. Software evidence never closes this track. R4 does **not** block downstream software sequencing.

### R5 — Developer Connectivity Platform — COMPLETE

Use accepted W046 as the foundation for a production developer surface. WORK-056 hardened the existing `developerapi/` boundary so external applications can request and manage connectivity through stable APIs and webhooks without adopting an ADCOS UI or acquiring direct authority over canonical identity, session, NetworkPath, routing, transport, usage, allocation, eligibility, marketplace, or payment state.

W056 was accepted under DEC-0094 and merged as `b11cf44`. Its successor gate R6 was activated under DEC-0095 and is now complete.

### R6 — Provider onboarding and federation — COMPLETE

Enable independently operated networks, ISPs, carriers, enterprises, satellite systems, hotspots, mesh operators, and infrastructure owners to expose connectivity through ADCOS while retaining infrastructure authority.

WORK-057 governs the lifecycle:

`registration → operator/domain identity binding → scoped credential issuance → adapter declaration/certification → capability/resource declaration → service/commercial profile binding → eligibility/policy evaluation → federation proposal → explicit acceptance → active federated membership → suspension/revocation/offboarding`

R6 is deliberately an integration/orchestration layer. It consumes existing identity, trust, capability, resource, federation, policy, routing, session, transport, telemetry, and commercial authorities and does not create substitutes for them.

The sole implementation authorization `WORK-057-CORE-001` is closed by DEC-0097. Adapter certification admission is bound to the existing adapter authority, including content-derived identity and evidence/attestation validation. Federation acceptance is bound to the relationship peer domain's registered operator and peer key proof; proposer self-acceptance fails closed. Federation scope narrowing remains owned by WORK-015.

The W056/W057 cross-era oracle condition remains handled as an Architect-owned historical scope matter and was not used to mutate accepted W056 history during W057 correction. WORK-048 remains accepted-not-restored and W040 remains an independent physical evidence track.

### R7 — Universal connectivity commerce — AFTER R6

Normalize heterogeneous connectivity resources into programmable offers selected by intent, policy, evidence, availability, geography, quality, and price. ADCOS coordinates the transaction and lifecycle; it does not need to own the underlying network.

R7 is **unlocked but not activated**. Its implementation requires a fresh gate-specific Work Item, dependency overlay, authorization, and sole-Architect acceptance under the post-snapshot governance model.

### R8 — Resilience, mobility and scale — AFTER R7

Harden failover, multipath, mobility, local-first operation, offline/reconnect, reconciliation, disaster recovery, key rotation/revocation, upgrades, rollback, federation scale, and operational observability.

### R9 — Future access technology — AFTER R8

Add new access technologies strictly through the adapter boundary without changing the protocol core.

## Canonical program sequence

`R0 → R1 → R2 → R3 → R4/R5 → R6 → R7 → R8 → R9`

R4 remains a parallel physical-evidence track. R5 is complete. R6 is complete. No implementation authorization is active. R7 is the next unlocked software gate but is not activated until its own gate-specific authorization is issued.

Routine sequencing of these gates is owned by the sole Architect. User prompting is not a governance dependency. The repository-local governance records, not this document or conversation history, determine implementation permission.

## The Stripe-of-connectivity exit criterion

ADCOS is successful when an external application can request connectivity by API; ADCOS can evaluate policy and eligible offers, reserve capacity, select and validate a path, establish controlled connectivity, meter delivered usage, finalize billing, allocate economic value, integrate with an external payment provider, reconcile provider events, and expose canonical status through API/webhooks — while the application remains independent of the underlying access technology, network operator, and payment rail.

## Source-of-truth rule

A clean clone of `main` is the starting point for every new Architect, implementation agent, or recovery operation. Conversation history is never required to discover what to build or whether building is permitted.

The authority chain is:

`mission → frozen architecture/locks → frozen Work Item contract + dependency graph → frozen roadmap.yaml → accepted decisions + execution ledger/state → active authorization → implementation evidence`

For Work Items created after the original frozen snapshot, the accepted post-snapshot governance model uses canonical contracts under `spec/architect/work-items/` and explicit dependency overlays under `spec/architect/dependency-overlays/`, as established by ACR-013 / DEC-0095.

`roadmap.md` is only a projection. Issues, PR discussions, chat messages, old handoffs, and external planning documents cannot override `roadmap.yaml`.
