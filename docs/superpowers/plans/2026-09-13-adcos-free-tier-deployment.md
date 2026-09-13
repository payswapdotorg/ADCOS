# ADCOS Free-Tier Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Deploy the accepted ADCOS 1.1 software control plane on a free-tier-oriented stack without changing domain authority.

**Architecture:** Preserve existing ADCOS domain modules. Add only the minimum runtime/API boundary and infrastructure adapters required for durable state, ephemeral coordination, artifact storage, and hosting.

**Tech Stack:** Existing ADCOS runtime; Vercel; Neon PostgreSQL; Upstash Redis; Cloudflare R2.

**Spec:** `docs/superpowers/specs/2026-09-13-adcos-free-tier-deployment-design.md`

## Global Constraints

- Architecture 1.1 remains normative.
- `ConnectivityContract` remains canonical durable authority.
- Redis is never canonical state.
- Provider SDKs remain behind adapters.
- Hard constraints are never silently weakened.
- Software deployment evidence never satisfies physical EVID-002..EVID-008.
- No secrets in Git.

## Work Graph

```text
T1 runtime inventory
 ├──> T2 HTTP/runtime boundary
 ├──> T3 Neon durable persistence
 ├──> T4 Upstash coordination
 └──> T5 R2 evidence storage
             |
             v
      T6 Vercel configuration
             |
             v
       T7 provision/deploy
             |
             v
      T8 live acceptance
```

### T1 Runtime inventory

Inspect actual manifests, entrypoints, persistence seams, evidence seams and CI. Run the repository specification and fresh-session checks. Record exact findings in `docs/deployment/runtime-inventory.md`.

### T2 HTTP/runtime boundary

Write focused tests first. Expose health, readiness and a deterministic contract-fulfillment demonstration through the thinnest adapter that calls existing accepted services. Keep domain rules outside HTTP code.

### T3 Neon durable persistence

Add a durable contract round-trip test, implement the PostgreSQL adapter at the existing persistence seam, and ensure database failure does not silently become in-memory canonical state.

### T4 Upstash coordination

Test acquisition, release, expiry, duplicate acquisition and backend failure. Implement only ephemeral coordination with explicit bounded failure semantics.

### T5 R2 evidence storage

Test put/get/checksum/missing-object behavior. Keep canonical metadata in durable state and store only artifacts/object data in R2.

### T6 Vercel configuration

Configure Vercel for the actual repository runtime rather than introducing an unrelated framework. Document environment-variable names, build, health/readiness and rollback behavior.

### T7 Provision and deploy

Link the repository to the Vercel Hobby team, connect Neon, Upstash and R2, verify environment keys before database bootstrap, deploy, then run live smoke checks.

### T8 Acceptance

Exercise rollback and backend degradation. Run repository verification plus live smoke tests. Record software deployment acceptance separately from physical-network evidence.
