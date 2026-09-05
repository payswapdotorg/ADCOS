# ADCOS Authoritative Roadmap

**FROZEN — Roadmap Version 1.1**

`spec/architect/roadmap.yaml` is the sole canonical program roadmap. This document is its human-readable projection. Neither this file nor the roadmap grants implementation authority. The roadmap version advanced from 1.0 to 1.1 by DEC-0084 (the R1 governance reconciliation after the accepted R0 restoration) — a governance/version transition only; Architecture Version 1.0 and Protocol Version 1.0 are unchanged.

## Current repository state

Actual `main` at this reconciliation: `a3391e86851e06032de848e6eb0b4267fa33310a` (repository: `github.com/payswapdotorg/ADCOS`).

**R0 is complete**: the canonical mainline restoration was accepted and merged as PR #8 on the exact frozen main `3bdfb6daf50f7c000d29a027584c0de5b376d8a8` (merge `a3391e86851e06032de848e6eb0b4267fa33310a`, tree `1d16c241`, byte-identical to the historical restoration tree `7fb47bb`). The previously accepted W044–W049 implementation packages, evidence/handoff records, deterministic selftest batteries, and CI invocation wiring are present on current main. Their original acceptance provenance (reviewed SHAs and accepted merge SHAs) is unchanged; the restoration merge is not the original Work Item acceptance merge.

**R1 is complete**: the durable governance projections (roadmap, current-state, execution-state, execution-ledger, decisions) are reconciled to the restored mainline by DEC-0084. W050–W053 remain accepted. W040 remains independent, in-review, and unaccepted; EVID-007 and EVID-008 remain open and W040-owned.

The immediate order is now:

`R2 system composition → R3 protocol production conformance → R4/R5 physical + developer platform → R6 provider federation → R7 universal connectivity commerce → R8 resilience/scale → R9 future access adapters`

Execution is **ready but fail-closed**: exactly zero implementation authorizations are active. R2 requires a fresh Work Item and exactly one implementation authorization issued by a new Architect decision before any implementation may start.

## Frozen execution roadmap

### R0 — Canonical accepted-mainline restoration — COMPLETE

Restore the exact accepted W044–W049 implementation packages, evidence manifests, handoffs, and required CI battery wiring onto the current authoritative mainline. The restoration must be additive and provenance-preserving: no unrelated later ancestry, no frozen semantic changes, no fabricated acceptance, no historical rewrite.

Exit gate: the accepted W044–W050/W051–W053 implementation set is physically present in one mainline and the Architect has verified exact file scope, accepted-head provenance, no unauthorized semantic delta, and deterministic batteries.

**Complete**: accepted and merged as PR #8 (merge `a3391e86851e06032de848e6eb0b4267fa33310a` on the exact frozen main `3bdfb6d`, tree `1d16c24` byte-identical to the historical restoration state `7fb47bb`; single-commit source head `69f1bec`; 58,500 insertions / 0 deletions / 79 files, additive only).

### R1 — Governance reconciliation — COMPLETE

Synchronize `execution-state.yaml`, `execution-ledger.yaml`, `current-state.md`, roadmap projections, decisions, authorizations, and evidence references to the restored mainline. Preserve all previous decisions and reconciliations. No historical record is deleted or rewritten.

Exit gate: a fresh clone of `main` reconstructs the same state without conversation access; zero contradictory active-authorization/status projections remain.

**Complete**: DEC-0084 reconciled the durable governance projections on the restored mainline `a3391e86851e06032de848e6eb0b4267fa33310a`. The historical R1 decision records in Git history (on the former repository lineage, checkpoint `338af793`) remain discoverable history and are not the current baseline; the current authoritative R1 reconciliation is DEC-0084 alone.

### R2 — System composition conformance — NEXT IMPLEMENTATION GATE

Prove the complete connectivity-commercial chain:

`intent → offer → eligibility → reservation/lease → candidate selection → NetworkPath validation → containment → session → delivered traffic → usage → BILLABLE_FINAL → allocation → external payment reference → reconciliation`

Mandatory negative proofs include: payment cannot create connectivity; reservation cannot imply reachability; marketplace discovery cannot activate paths; W050 capability declarations cannot enforce containment; W049/client state cannot become canonical truth; API/webhooks cannot become a second authority; software evidence cannot close physical evidence.

R2 awaits a fresh Work Item and exactly one implementation authorization issued by a new Architect decision; exactly zero are active now.

Exit gate: deterministic end-to-end composition and negative-proof battery passes from fresh state and across restart/replay.

### R3 — Protocol production conformance

Complete the production conformance layer required before declaring wire compatibility. This includes canonicalization and canonical encoding profiles, signature coverage, version negotiation, unknown-extension behavior, idempotency/replay, schema evolution, migration compatibility, and deterministic digest stability.

Exit gate: protocol conformance is executable, versioned, deterministic, and compatible with the frozen Architecture Version 1.0 / Protocol Version 1.0 contract.

### R4 — Physical connectivity validation

Continue W040 independently. Produce real hardware/network evidence for the open physical obligations. Software evidence never closes this track.

Exit gate: the relevant evidence obligations are actually demonstrated and accepted through the repository evidence process.

### R5 — Developer Connectivity Platform

Use accepted W046 as the foundation for a production developer surface. ADCOS becomes usable like Stripe: an external application requests connectivity through stable APIs and webhooks without adopting an ADCOS UI or knowing provider, access technology, route implementation, or payment-rail internals.

Required capabilities include intent creation, offer/quote access, reservation/lease, activation/status, termination, usage/finalization projections, webhook delivery, idempotency, scoped credentials, sandbox/production separation, and canonical reason-code exposure.

Exit gate: a third-party application can complete the full connectivity lifecycle through the API without an ADCOS-specific UI dependency.

### R6 — Provider onboarding and federation

Enable independently operated networks, ISPs, carriers, enterprises, satellite systems, hotspots, mesh operators, and infrastructure owners to expose connectivity through ADCOS. Provider infrastructure remains provider-controlled.

Required capabilities include adapter certification, capability declarations, commercial contracts/profiles, policy boundaries, service terms, settlement configuration, observability, and federation trust.

Exit gate: at least two independently controlled connectivity providers can interoperate through the same canonical ADCOS interfaces without a shared vendor control plane.

### R7 — Universal connectivity commerce

Normalize heterogeneous connectivity resources into programmable offers selected by intent, policy, evidence, availability, geography, quality, and price. ADCOS coordinates the transaction and lifecycle; it does not need to own the underlying network.

Exit gate: materially different access resources can be exposed, selected, reserved, consumed, measured, and commercially reconciled through the same stable abstraction.

### R8 — Resilience, mobility and scale

Harden failover, multipath, mobility, local-first operation, offline/reconnect, reconciliation, disaster recovery, key rotation/revocation, upgrades, rollback, federation scale, and operational observability.

Exit gate: the fabric remains correct under provider/path changes, partial failure, disconnected operation, replay, and node replacement.

### R9 — Future access technology

Add new access technologies strictly through the adapter boundary without changing the protocol core. Examples include 5G, Wi-Fi, Ethernet/fiber, satellite, mesh/IAB, enterprise WAN, and future IMT/6G systems.

Exit gate: a new access adapter can be certified without modifying core connectivity authority semantics.

## The Stripe-of-connectivity exit criterion

ADCOS is successful when an external application can request connectivity by API; ADCOS can evaluate policy and eligible offers, reserve capacity, select and validate a path, establish controlled connectivity, meter delivered usage, finalize billing, allocate economic value, integrate with an external payment provider, reconcile provider events, and expose canonical status through API/webhooks — while the application remains independent of the underlying access technology, network operator, and payment rail.

## Source-of-truth rule

A clean clone of `main` is the starting point for every new Architect, implementation agent, or recovery operation. Conversation history is never required to discover what to build or whether building is permitted.

The authority chain is:

`mission → frozen architecture/locks → frozen Work Item contract + dependency graph → frozen roadmap.yaml → accepted decisions + execution ledger/state → active authorization → implementation evidence`

`roadmap.md` is only a projection. Issues, PR discussions, chat messages, old handoffs, and external planning documents cannot override `roadmap.yaml`.
