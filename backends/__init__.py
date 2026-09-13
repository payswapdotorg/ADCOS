"""ADCOS deployment infrastructure adapters (DEC-0126 bounded scope).

Provider-backed implementations at the verified persistence/coordination/
object-storage seams — composed BY REFERENCE with the accepted domain
authorities, never replacing them:

- ``postgres``: Neon PostgreSQL durable persistence (the ApiStore seam +
  the contract-journal round-trip; the ContractStore fold stays the sole
  state authority).
- ``upstash``: ephemeral coordination over the Upstash Redis REST API (the
  RateLimiter seam + cross-instance serialization locks; never canonical
  state).
- ``r2``: Cloudflare R2 evidence/artifact storage (S3-compatible REST,
  hand-rolled SigV4; canonical metadata stays in durable state).

Every adapter fails explicitly and observably on backend trouble — a
backend outage never silently becomes in-memory canonical state and never
weakens a hard contract constraint (free-tier exhaustion included).
"""
