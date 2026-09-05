# ADCOS Authoritative Roadmap

**FROZEN — Roadmap Version 1.2**

`spec/architect/roadmap.yaml` is the sole canonical program roadmap. This document is its human-readable projection. Neither this file nor the roadmap grants implementation authority.

## Current repository state

Canonical reconciled `main` checkpoint: `338af793923e1267ff3523de4310be273d75a2cd`.

R0 mainline restoration is complete at `7fb47bb312708d06f3b3c1ba0496104362c7d135`. R1 governance reconciliation is complete under `DEC-0083`; the reconciled snapshot is the `338af793` checkpoint.

## Current execution gate

**R2 — System Composition Conformance: READY.**

R1 is closed. W044-W049 lifecycle records are reconciled to their durable accepted delivery history, W050 is accepted by DEC-0083 on its exact final delivery head with the permanent 76/76 SOFTWARE battery, governance projections are aligned, and no implementation authorization is active.

No Work Item is active. No implementation authorization is active. Product implementation is gated only by creation and authorization of the next repository-local R2 Work Item.

## Frozen execution roadmap

### R0 — Canonical accepted-mainline restoration — COMPLETE

Restore accepted W044-W049 artifacts without unrelated ancestry or frozen semantic changes.

Completion: PR #157 merged as `7fb47bb312708d06f3b3c1ba0496104362c7d135`.

### R1 — Governance reconciliation — COMPLETE

Bring durable lifecycle and decision projections into one coherent state. Preserve every previous decision and reconciliation. Do not manufacture acceptance from implementation, CI, issue prose, or chat.

Closure: `DEC-0083` and `LEDGER-RECON-024`. Exactly zero active implementation authorizations at the reconciled checkpoint.

### R2 — System composition conformance — CURRENT PRODUCT GATE

Prove:

`intent → offer → eligibility → reservation/lease → candidate selection → NetworkPath validation → containment → session → delivered traffic → usage → BILLABLE_FINAL → allocation → external payment reference → reconciliation`

Mandatory negative proofs prevent payment, reservation, discovery, capability declaration, client state, or API/webhook observations from becoming unauthorized connectivity or canonical authority.

R2 requires a fresh repository-local Work Item and exactly one active implementation authorization. Roadmap status alone never authorizes implementation.

### R3 — Protocol production conformance

Complete canonicalization, encoding, signature coverage, version negotiation, extension behavior, replay/idempotency, schema evolution, migration compatibility, and deterministic digest conformance before production wire compatibility is declared.

### R4 — Physical connectivity validation

Continue W040 independently on real hardware/network environments. Software evidence never closes physical evidence obligations.

### R5 — Developer Connectivity Platform

Use accepted W046 as the foundation for a production developer surface analogous to Stripe: third-party applications request, manage, and observe connectivity through APIs/webhooks without requiring an ADCOS UI or knowledge of provider/access/path/payment internals.

### R6 — Provider onboarding and federation

Enable independently operated networks, ISPs, carriers, enterprises, satellite systems, hotspots, mesh operators, and infrastructure owners to expose capacity while retaining infrastructure authority.

### R7 — Universal connectivity commerce

Normalize heterogeneous connectivity resources into programmable offers selected by intent, policy, evidence, availability, geography, quality, and price.

### R8 — Resilience, mobility and scale

Harden failover, multipath, mobility, local-first operation, offline/reconnect, reconciliation, disaster recovery, key rotation/revocation, upgrades, rollback, federation scale, and observability.

### R9 — Future access technology

Add or replace access technologies strictly through the adapter boundary without modifying core connectivity authority semantics.

## Stripe-of-connectivity exit criterion

ADCOS succeeds when an external application can request connectivity by API; ADCOS can evaluate policy and eligible offers, reserve capacity, select and validate a path, establish controlled connectivity, meter delivered usage, finalize billing, allocate economic value, integrate with an external payment provider, reconcile provider events, and expose canonical status — without the application needing an ADCOS UI or knowledge of the underlying access technology/provider.

## Source-of-truth rule

A clean clone of `main` is sufficient to reconstruct ADCOS. Conversation history is never required or authoritative.

Authority chain:

`mission → frozen architecture/locks → frozen Work Item contract + dependency graph → frozen roadmap.yaml → durable decisions + execution ledger/state → active authorization → implementation/evidence`

`roadmap.md` is a projection only. Issues, PR discussions, old handoffs, external planning documents, prompts, model memory, and chat cannot override `roadmap.yaml`.
