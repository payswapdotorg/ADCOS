# ADCOS Authoritative Roadmap

**FROZEN — Roadmap Version 1.1**

`spec/architect/roadmap.yaml` is the sole canonical program roadmap. This document is its human-readable projection. Neither this file nor the roadmap grants implementation authority.

## Current repository state

Canonical mainline after R0 restoration: `7fb47bb312708d06f3b3c1ba0496104362c7d135`.

R0 mainline restoration is complete. The accepted W044-W049 implementation packages, evidence surfaces, selftests, and CI invocation wiring are present on the canonical mainline.

## Current execution gate

**R1 — Governance Reconciliation: BLOCKED.**

Two governance conditions remain:

1. Reconcile the execution ledger's W044-W049 lifecycle records to the durable accepted history without rewriting prior history.
2. Resolve W050 acceptance provenance. W050 implementation-stage evidence and its permanent deterministic battery are present, but the current authoritative decision/ledger chain does not contain a discrete corroborated W050 acceptance decision. Acceptance is therefore not inferred.

No Work Item is active. No implementation authorization is active. Implementation remains stopped.

## Frozen execution roadmap

### R0 — Canonical accepted-mainline restoration — COMPLETE

Restore accepted W044-W049 artifacts without unrelated ancestry or frozen semantic changes.

Completion: PR #157 merged as `7fb47bb312708d06f3b3c1ba0496104362c7d135`.

### R1 — Governance reconciliation — CURRENT BLOCKING GATE

Bring the durable lifecycle and decision projections into one coherent state. Preserve every previous decision and reconciliation. Do not manufacture acceptance from implementation, CI, issue prose, or chat.

Exit gate: fresh-clone sufficiency, ledger/current-state/roadmap agreement on the exact mainline, W044-W049 lifecycle records reconciled, W050 acceptance disposition explicit, and exactly zero active implementation authorizations.

### R2 — System composition conformance

Prove:

`intent → offer → eligibility → reservation/lease → candidate selection → NetworkPath validation → containment → session → delivered traffic → usage → BILLABLE_FINAL → allocation → external payment reference → reconciliation`

Mandatory negative proofs prevent payment, reservation, discovery, capability declaration, client state, or API/webhook observations from becoming unauthorized connectivity or canonical authority.

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
