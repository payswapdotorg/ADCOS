# ADCOS Deployment — Tech Lead Handoff

## Authority

Deployment architecture was approved by the product owner and bounded repository-local authority is recorded as `DEC-0126` on the isolated deployment branch.

The Architect's job is complete at this boundary. **The Tech Lead owns all implementation and deployment execution from here.**

## Entry artifacts

Read these before dispatching any worker:

1. `AGENTS.md`
2. `spec/architect/resume-protocol.md`
3. `spec/architect/roadmap.yaml`
4. `spec/architect/execution-state.yaml`
5. `spec/architect/decisions/DEC-0126.md`
6. `docs/superpowers/specs/2026-09-13-adcos-free-tier-deployment-design.md`
7. `docs/superpowers/plans/2026-09-13-adcos-free-tier-deployment.md`
8. `docs/tech-lead/worker-model.md`

## Execution ownership

The Tech Lead MUST perform or dispatch all implementation work. The Architect must not directly implement the runtime, provision cloud resources, deploy to Vercel, run production migrations, or accept deployment evidence.

The Tech Lead may dispatch at most 3 direct workers, each at most 3 subagents, subject to the existing ADCOS dependency and authority rules.

## Recommended worker allocation

### Worker 1 — Runtime + persistence

Own:
- runtime inventory verification;
- HTTP/API boundary;
- Neon durable persistence;
- focused and full test integration.

### Worker 2 — Coordination + evidence storage

Own:
- Upstash Redis adapter;
- Cloudflare R2 evidence/artifact adapter;
- failure/degradation tests;
- credential/env contracts.

### Worker 3 — Deployment + operations

Own:
- Vercel runtime/deployment configuration;
- deployment automation;
- production environment wiring;
- live smoke tests;
- rollback proof;
- deployment runbook/evidence.

Worker 3 must not deploy until Workers 1 and 2 have delivered the interfaces required by the plan and the Tech Lead has integrated and verified them.

## Dependency graph

```text
T1 Runtime inventory
 ├──> T2 HTTP/runtime boundary
 ├──> T3 Neon durable persistence
 ├──> T4 Upstash coordination
 └──> T5 R2 evidence storage
              |
              v
       T6 Vercel configuration
              |
              v
        T7 Provision + deploy
              |
              v
        T8 Live acceptance
```

T2/T3/T4/T5 may be parallelized after T1 establishes the real seams. T6 depends on the real runtime shape. T7 depends on the integrated result of T2-T6. T8 depends on T7.

## Mandatory deployment constraints

- Do not introduce Next.js merely to obtain Vercel hosting.
- Do not fork or rewrite accepted ADCOS domain authorities.
- `ConnectivityContract` remains canonical durable authority.
- Redis is never canonical state.
- Provider SDKs remain behind adapter boundaries.
- Hard contract constraints may not be silently weakened by infrastructure failure.
- Software deployment evidence must not be presented as physical connectivity evidence.
- EVID-002..EVID-008 remain outside software deployment acceptance.
- No secrets or credentials may be committed or printed.
- Free-tier exhaustion must fail explicitly and observably.

## Provider stack

- Vercel: runtime/hosting.
- Neon PostgreSQL: durable state.
- Upstash Redis: ephemeral coordination.
- Cloudflare R2: artifacts/evidence.
- Apify: optional external discovery/automation only; never a correctness dependency.

## Deployment target

The first production deployment is **software-only** and uses deterministic sandbox/emulator provider adapters where physical provider access is unavailable. Success means the deployed control plane can demonstrate the accepted contract → plan → execution → evidence flow with durable persistence and operational rollback.

This does not close the independent physical-validation track.

## Required final evidence

Before declaring deployment complete, the Tech Lead must provide:

- exact merged implementation SHA;
- exact Vercel production deployment identifier/URL;
- environment/provider resources used (names/IDs only, never secrets);
- health/readiness results;
- end-to-end contract-fulfillment result;
- Neon persistence verification;
- Upstash coordination verification;
- R2 artifact verification;
- rollback verification;
- full repository verification results;
- explicit statement that physical obligations EVID-002..EVID-008 remain unproven.
