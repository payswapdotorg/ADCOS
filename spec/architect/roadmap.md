# ADCOS Authoritative Roadmap

**FROZEN — Roadmap Version 1.0**

`spec/architect/roadmap.yaml` is the sole canonical program roadmap. This document is its human-readable projection. Neither this file nor the roadmap grants implementation authority.

## Current repository state

Actual and reconciled `main`: `7fb47bb312708d06f3b3c1ba0496104362c7d135`.

R0 mainline restoration is complete. The accepted W044-W049 implementation packages, evidence surfaces, selftests, and CI invocation wiring are present on the canonical mainline. The restoration did not modify `spec/architect/`, frozen architecture, or protocol semantics.

## Current execution gate

**R1 — Governance Reconciliation: BLOCKED pending ledger normalization.**

The execution ledger still contains the older W044-W050 lifecycle representation. That historical record will not be silently rewritten. R1 must explicitly reconcile it using the live ledger as its source document, preserve all prior reconciliation records, and preserve historical acceptance provenance.

No Work Item is active. No implementation authorization is active. Therefore no implementation may begin.

## Frozen execution roadmap

### R0 — Canonical accepted-mainline restoration — COMPLETE

Restore the exact accepted W044-W049 implementation packages, evidence manifests, handoffs, and required CI battery wiring onto the authoritative mainline without unrelated ancestry or frozen semantic changes.

Completion: PR #157 merged as `7fb47bb312708d06f3b3c1ba0496104362c7d135`.

### R1 — Governance reconciliation — CURRENT BLOCKING GATE

Synchronize the roadmap/current-state/execution-state with the durable lifecycle ledger and decision history. Preserve every prior decision and reconciliation; do not downgrade or invent Work Item history.

Required end state: a fresh clone of `main` gives one coherent program state, zero active implementation authorizations, no contradictory status projections, and a ledger snapshot reconciled to the same canonical mainline.

### R2 — System composition conformance

Prove the complete connectivity-commercial chain:

`intent → offer → eligibility → reservation/lease → candidate selection → NetworkPath validation → containment → session → delivered traffic → usage → BILLABLE_FINAL → allocation → external payment reference → reconciliation`

Mandatory negative proofs prevent payment, reservation, discovery, capability declaration, client state, or API/webhook observations from becoming unauthorized connectivity or canonical authorities.

### R3 — Protocol production conformance

Complete the production conformance layer required before declaring wire compatibility: canonicalization, canonical encodings, signature coverage, version negotiation, extension behavior, replay/idempotency, schema evolution, migration compatibility, and deterministic digest stability.

### R4 — Physical connectivity validation

Continue W040 independently on real hardware/network environments. Software evidence never closes physical evidence obligations.

### R5 — Developer Connectivity Platform

Use the accepted W046 foundation to expose ADCOS as a connectivity platform analogous to Stripe: third-party applications request, manage, and observe connectivity through stable APIs/webhooks without requiring an ADCOS UI or knowledge of provider/access/path/payment internals.

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
