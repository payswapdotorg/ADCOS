# ADCOS Free-Tier Deployment Design

## Goal
Deploy the accepted ADCOS 1.1 software control plane as a real, reproducible service using predominantly free-tier infrastructure while preserving the frozen architecture and separating software evidence from physical-network validation.

## Scope
This deployment is an infrastructure/runtime composition around the accepted ADCOS 1.1 software. It does not redefine Architecture 1.1, restore Architecture 1.0, or claim that physical obligations EVID-002..EVID-008 are satisfied.

## Target topology

```text
Vercel
  -> ADCOS HTTP/API runtime
  -> Neon PostgreSQL (durable state)
  -> Upstash Redis (ephemeral coordination, locks, cache, queues)
  -> Cloudflare R2 (evidence/artifacts/object storage)
  -> provider adapters / sandbox providers

Optional:
  Apify -> external discovery/automation only
```

## Provider roles

- Vercel: stateless public control/API runtime and deployment automation.
- Neon PostgreSQL: durable ADCOS state and authoritative persisted records.
- Upstash Redis: ephemeral coordination only; no canonical authority may live solely in Redis.
- Cloudflare R2: evidence and large-object storage; database stores references and integrity metadata.
- Apify: optional external discovery/browser automation accelerator; never a correctness dependency for the connectivity contract core.

## Architectural constraints

1. `ConnectivityContract` remains the canonical durable authority.
2. Provider SDKs remain isolated behind ADCOS adapters.
3. No global provider topology is required or introduced.
4. Applications may buy/sponsor connectivity without taking provider topology authority.
5. Hard contract constraints MUST NOT be silently weakened during degradation or failover.
6. Software/emulated evidence MUST NOT be converted into physical PASS by inference.
7. External payment movement remains distinct from ADCOS connectivity/commercial references.
8. The deployment must support simple single-provider operation and multi-provider composition without requiring different core semantics.
9. Infrastructure credentials are secrets and must never be committed or echoed.
10. Existing accepted R7/R8/R9 authorities are consumed by reference; deployment work must not fork or duplicate those domain authorities.

## Initial runtime mode

The first production deployment is software-only. Provider integrations use deterministic sandbox/emulator adapters where real provider credentials or physical network access are unavailable. The deployed surface must expose health/readiness and a deterministic end-to-end contract-fulfillment demonstration over the accepted software path.

## Acceptance boundary

Deployment acceptance proves:

- the service is deployed and reachable;
- durable state is persisted in Neon;
- ephemeral coordination works through Upstash;
- evidence/artifact persistence works through R2;
- provider adapters are resolved through their existing boundary;
- a contract can be created, planned, executed and evidenced through the deployed control plane;
- a deployment can be reproduced from repository instructions and locked dependencies.

Deployment acceptance does NOT prove physical connectivity or satisfy EVID-002..EVID-008.

## Files expected from implementation

The implementation should first inspect the existing Python packaging and runtime entrypoints and then add only the minimum deployment surface required. Expected additions are limited to deployment configuration, a thin HTTP/API adapter around existing accepted application services, provider-backed persistence/coordination/object-storage implementations where missing, health/readiness endpoints, deployment verification tests, and operational documentation. Existing domain modules remain authoritative.

## Security

Use provider-managed environment variables/secrets. Minimum production secret set should include database connection details, Redis URL/token, R2 endpoint/access credentials, and application signing/cryptographic material only where existing ADCOS runtime contracts require them. Never commit secret values.

## Free-tier posture

The design intentionally avoids paid-only managed services. It does not assume that provider free tiers are permanent, sufficient for arbitrary load, or suitable for physical-network production traffic. Quota exhaustion must fail explicitly and observably rather than silently changing contract semantics.

## Rollout order

1. Repository/runtime inspection and local reproducibility.
2. Deployment authorization and machine-readable work-item registration.
3. API/runtime surface.
4. Neon persistence.
5. Upstash coordination.
6. R2 evidence/object storage.
7. Vercel deployment.
8. Sandbox provider integration.
9. End-to-end production verification.
10. Operational hardening and rollback documentation.
