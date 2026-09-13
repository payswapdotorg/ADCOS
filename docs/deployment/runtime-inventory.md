# ADCOS runtime inventory

Inventory populated from the live `main` tree at the DEC-0126 handoff merge
`2d69418` (the post-PR-#49 implementation base). Every field below was
verified against the actual manifests, entrypoints and seams — no
framework-specific runtime was assumed.

## Repository facts

- Repository: `github.com/payswapdotorg/ADCOS`; default branch `main`.
- Accepted software baseline: the R9/M024 terminal state `73908d1`
  (DEC-0125, roadmap v2.22, gate sequence R0-R9 COMPLETE) plus the
  deployment-authorization governance (DEC-0126 / LEDGER-RECON-040,
  snapshot baseline `4045ef0`, handoff merge `2d69418`).
- Execution state: `awaiting-architect-decisions` (roadmap halted at the
  terminal gate); the deployment authority is decision-borne
  (DEC-0126), repository-local, and outside the gate machinery.
- Language/runtime: pure Python 3, **standard library only**. Verified by
  AST scan over the whole tree: zero third-party runtime imports in every
  accepted domain module (the sole non-stdlib token is an OPTIONAL
  `import yaml` in `tools/service_selftest.py` guarded by
  `except ImportError: skip` — the established optional-dependency
  pattern, reused for the deployment adapters below).
- Package manifest: NONE (no `pyproject.toml` / `requirements.txt` /
  `setup.py`). CI executes the batteries directly
  (`python3 tools/*_selftest.py`) with the stdlib-only property
  load-bearing: no pip install anywhere in CI.
- HTTP entrypoint: NONE today. The accepted application-service boundary
  is the M013 `developerapi` gateway (below); the deployment adds the
  thinnest HTTP translation over it.

## The verified composition seams (consumed BY REFERENCE — never forked)

1. `contracts.store.ContractStore(journal_path=Path|None)` — THE canonical
   durable authority seam (LOCK-101/LOCK-117): append-only JSONL command
   journal + construction-is-recovery re-fold; idempotent duplicate
   commands; fail-closed replay/sequence-gap handling; LOCK-119 secret
   scanning on every persisted line. Public surface: `next_record` /
   `merge` (two-step submit), `contract` / `contracts` / `lease` /
   `leases` / `leases_for_contract` / `journal` reads.
2. `developerapi.gateway.DeveloperGateway(environment=, contracts=,
   store=ApiStore, clock=AgentClock, issuance_key=bytes, rate_limiter=
   RateLimiter|None, delivery_transports=)` — the accepted request
   admission boundary: authenticate (constant-time, environment-bound) →
   resolve API version → rate limit (per application, non-mutating) →
   authorize scoped capability → DURABLE write-ahead idempotency hold →
   adapt to the canonical `ContractStore` PUBLIC surface only → atomic
   journal record (persist-then-ack finality) → webhook
   admission/obligation records → canonical response envelope.
3. `developerapi.journal.ApiStore` — the developer-API persistence ABC
   with `MemoryApiStore` and `FileApiStore(path)` (JSONL). This is the
   durable-persistence seam for the idempotency ledger + webhook records.
4. `developerapi.ratelimit.RateLimiter.check(application_id) ->
   RateDecision` — the ephemeral coordination seam (deterministic
   in-process default implementation exists).
5. `agent.clock.AgentClock` — the injected clock seam (the boundary never
   reads a wall clock; determinism discipline).
6. `executionplans/` (M006, LOCK-109) — the canonical contract→plan
   translation bridge (typed `ExecutionPlan` / `ExecutionSegment`).
7. `evidence.EvidenceStore` (M005, LOCK-106/118/119) — append-only typed
   evidence records; construction-is-recovery JSONL persistence;
   content-derived tamper-evident ids.
8. `sharenet/` (M010) — the accepted 8-step ShareNet vertical proof
   harness: application boundary → SDK client → canonical authority →
   disclosed simulation seams → attributable evidence ledger → scenario
   driver. THE deterministic contract-fulfillment composition the demo
   endpoint mirrors.
9. `adapters/capability.py` + `adapters/reference/` (M007, LOCK-110/112)
   — the provider/standard adapter boundary the sandbox/emulator
   provider surface composes through.

## CI command

`.github/workflows/spec-check.yml`: governance checks
(`tools/current_spec_check.py`, `tools/tech_lead_guard.py`,
`tools/architecture_drift_guard.py`, legacy `tools/spec_check.py`
continue-on-error, `tools/fresh_session_check.py` PR-mode,
`tools/experience_check.py`) + the wired battery steps
(`python3 tools/*_selftest.py`, exact-head discipline).

## Deploy runtime (planned per the approved design)

- Vercel Python serverless functions: an ASGI application exported from
  `api/index.py` (`from runtime.asgi import app`); Vercel's Python
  runtime import-traces the pure-stdlib accepted domains into the bundle.
  No Next.js, no framework introduction.
- Neon PostgreSQL (durable): adapter at the `ApiStore` seam + the
  contract-journal round-trip. Journal lines are durable rows; the
  `ContractStore` fold stays the sole state authority (the adapter never
  computes state — it round-trips journal bytes and materializes for the
  fold). Real client: `pg8000` (pure-Python), imported lazily ONLY when a
  connection string is present (the `service_selftest` optional-import
  pattern); CI batteries run the adapter contract against deterministic
  fakes — no Postgres, no network.
- Upstash Redis (ephemeral coordination): the REST API over stdlib
  `urllib` (URL + token env vars). Implements the `RateLimiter` seam +
  a cross-instance append-serialization lock. Explicit bounded failure
  semantics: acquire/release/expiry/duplicate-acquisition/backend-failure
  tested; a Redis outage NEVER becomes canonical state and never
  silently weakens a hard contract constraint (fail closed + explicit
  error surfaces).
- Cloudflare R2 (evidence/artifacts): S3-compatible REST with hand-rolled
  AWS SigV4 signing (stdlib hmac/hashlib only — no boto3). put/get/
  checksum/missing-object semantics; canonical metadata + integrity
  records stay in durable state.
- Deterministic sandbox provider adapters: the execution leg of the
  contract→plan→execution→evidence demo composes the accepted adapter
  boundary in sandbox mode. SOFTWARE-class evidence only — never
  promoted, never presented as physical connectivity evidence
  (EVID-002..EVID-008 stay open).

## Required environment variables (production contract; values are secrets — never committed)

- `ADCOS_DATABASE_URL` — Neon PostgreSQL connection string (durable).
- `ADCOS_REDIS_REST_URL` / `ADCOS_REDIS_REST_TOKEN` — Upstash (ephemeral).
- `ADCOS_R2_ACCOUNT_ID` / `ADCOS_R2_ACCESS_KEY_ID` /
  `ADCOS_R2_SECRET_ACCESS_KEY` / `ADCOS_R2_BUCKET` — Cloudflare R2.
- `ADCOS_ISSUANCE_KEY` — the developer API issuance key material (the
  existing runtime contract; hex-encoded bytes).
- `ADCOS_ENVIRONMENT` — the environment name bound at the gateway.

Free-tier posture: quota exhaustion must fail explicitly and observably
(typed error surfaces with the failing backend named) — never a silent
fallback to in-memory canonical state.
