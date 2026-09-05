# ADCOS Authoritative Roadmap

**FROZEN — Roadmap Version 1.2**

`spec/architect/roadmap.yaml` is the sole canonical program roadmap. This document is its human-readable projection. Neither this file nor the roadmap grants implementation authority. The roadmap version advanced from 1.1 to 1.2 by DEC-0085 (R2 activation after completion of R1) — a governance/version transition only; Architecture Version 1.0 and Protocol Version 1.0 are unchanged.

## Current repository state

Actual `main` at R2 activation: `13bfbda54eece391306ddb774e0700c9d862339a` (repository: `github.com/payswapdotorg/ADCOS`).

**R0 is complete**: the canonical mainline restoration was accepted and merged as PR #8 on the exact frozen main `3bdfb6d` (merge `a3391e8`, tree `1d16c24`, byte-identical to the historical restoration tree `7fb47bb`). The previously accepted W044–W049 implementation packages, evidence/handoff records, deterministic selftest batteries, and CI invocation wiring are present as defined by the accepted restoration. W048 remains explicitly accepted-but-not-restored.

**R1 is complete**: the durable governance projections were reconciled to the restored mainline by DEC-0084 and merged as PR #9 (`13bfbda`). Historical R1 records remain history only and are not the current baseline.

**R2 is active**: DEC-0085 activates WORK-054 — System Composition Conformance — from exact main `13bfbda` with the sole active implementation authorization `WORK-054-CORE-001`.

## Frozen execution roadmap

### R0 — Canonical accepted-mainline restoration — COMPLETE

Restore the exact accepted W044–W049 implementation packages, evidence manifests, handoffs, and required CI battery wiring onto the current authoritative mainline. The restoration must be additive and provenance-preserving: no unrelated later ancestry, no frozen semantic changes, no fabricated acceptance, no historical rewrite.

**Complete**: accepted and merged as PR #8 (merge `a3391e8` on the exact frozen main `3bdfb6d`; tree `1d16c24` byte-identical to `7fb47bb`).

### R1 — Governance reconciliation — COMPLETE

Synchronize `execution-state.yaml`, `execution-ledger.yaml`, `current-state.md`, roadmap projections, decisions, authorizations, and evidence references to the restored mainline. Preserve all previous decisions and reconciliations.

**Complete**: DEC-0084 reconciled the durable governance projections on the restored mainline; PR #9 merged as `13bfbda`.

### R2 — System composition conformance — ACTIVE

WORK-054 is the single active implementation Work Item under DEC-0085 and authorization `WORK-054-CORE-001`.

Prove the complete connectivity-commercial chain:

`intent → offer → eligibility → reservation/lease → candidate selection → NetworkPath validation → containment → session → delivered traffic → usage → BILLABLE_FINAL → allocation → external payment reference → reconciliation`

Mandatory negative proofs include: payment cannot create connectivity; reservation cannot imply reachability; marketplace discovery cannot activate paths; W050 capability declarations cannot enforce containment; W049/client state cannot become canonical truth; API/webhooks cannot become a second authority; software evidence cannot close physical evidence.

**Additional fail-closed requirement:** W048 is historically accepted but its implementation artifacts are explicitly absent from the accepted restoration tree. WORK-054 must detect that absence and must not recreate, bypass, or silently substitute W048 authority.

Exit gate: deterministic end-to-end composition and negative-proof battery passes from fresh state and across restart/replay, or produces an explicit fail-closed result for any unavailable authority without claiming complete production composition.

### R3 — Protocol production conformance — AFTER R2

Complete the production conformance layer required before declaring wire compatibility. This includes canonicalization and canonical encoding profiles, signature coverage, version negotiation, unknown-extension behavior, idempotency/replay, schema evolution, migration compatibility, and deterministic digest stability.

### R4 — Physical connectivity validation

Continue W040 independently. Produce real hardware/network evidence for the open physical obligations. Software evidence never closes this track.

### R5 — Developer Connectivity Platform — AFTER R2

Use accepted W046 as the foundation for a production developer surface. ADCOS becomes usable like Stripe: an external application requests connectivity through stable APIs and webhooks without adopting an ADCOS UI or knowing provider, access technology, route implementation, or payment-rail internals.

### R6 — Provider onboarding and federation — AFTER R5

Enable independently operated networks, ISPs, carriers, enterprises, satellite systems, hotspots, mesh operators, and infrastructure owners to expose connectivity through ADCOS. Provider infrastructure remains provider-controlled.

### R7 — Universal connectivity commerce — AFTER R6

Normalize heterogeneous connectivity resources into programmable offers selected by intent, policy, evidence, availability, geography, quality, and price. ADCOS coordinates the transaction and lifecycle; it does not need to own the underlying network.

### R8 — Resilience, mobility and scale — AFTER R7

Harden failover, multipath, mobility, local-first operation, offline/reconnect, reconciliation, disaster recovery, key rotation/revocation, upgrades, rollback, federation scale, and operational observability.

### R9 — Future access technology — AFTER R8

Add new access technologies strictly through the adapter boundary without changing the protocol core.

## The Stripe-of-connectivity exit criterion

ADCOS is successful when an external application can request connectivity by API; ADCOS can evaluate policy and eligible offers, reserve capacity, select and validate a path, establish controlled connectivity, meter delivered usage, finalize billing, allocate economic value, integrate with an external payment provider, reconcile provider events, and expose canonical status through API/webhooks — while the application remains independent of the underlying access technology, network operator, and payment rail.

## Source-of-truth rule

A clean clone of `main` is the starting point for every new Architect, implementation agent, or recovery operation. Conversation history is never required to discover what to build or whether building is permitted.

The authority chain is:

`mission → frozen architecture/locks → frozen Work Item contract + dependency graph → frozen roadmap.yaml → accepted decisions + execution ledger/state → active authorization → implementation evidence`

`roadmap.md` is only a projection. Issues, PR discussions, chat messages, old handoffs, and external planning documents cannot override `roadmap.yaml`.
