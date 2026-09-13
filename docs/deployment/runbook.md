# ADCOS Deployment Runbook — T6/T7/T8 (Vercel + operations)

Operational manual for deploying the ADCOS control plane to the free-tier
provider stack authorized by `spec/architect/decisions/DEC-0126-deployment-authorization.yaml`
(Vercel runtime, Neon durable persistence, Upstash ephemeral coordination,
Cloudflare R2 evidence storage). Executed by the Tech Lead with real
credentials. **Never commit or print secret values.**

Worker-3 delivered files (this runbook's subject):

- `api/index.py` — the Vercel Python function entry (ASGI `app` export)
- `vercel.json` — the Vercel project configuration
- `requirements.txt` — the single deployment dependency (`pg8000`)
- `.vercelignore` — serverless bundle exclusions
- `deploy/verify.py` — the T8 live-acceptance harness
- `docs/deployment/runbook.md` — this document

The runtime itself (`runtime/wiring.py`, `backends/postgres.py`,
`backends/upstash.py`, `backends/r2.py`) is delivered by workers 1 and 2 and
integrated by the Tech Lead before T7. This runbook assumes the integrated
implementation branch.

**Hard constraints carried through every step below** (DEC-0126 /
handoff): Architecture 1.1 stays normative; `ConnectivityContract` stays the
canonical durable authority; Redis is never canonical state; provider SDKs
stay behind adapter boundaries; free-tier exhaustion fails explicitly and
observably; software evidence is never presented as physical evidence
(EVID-002..EVID-008 stay open); no Next.js or any framework is introduced
merely to obtain hosting — the deployment target is the ACTUAL repository
runtime: a pure-stdlib Python ASGI app.

---

## 1. Prerequisites

Operator-provided (already provisioned or provisionable on free tiers):

- **Vercel**: a Hobby-team account, a personal access token with deployment
  scope (`VERCEL_TOKEN` — used only as a CLI env var, never committed), and
  the GitHub repository linked/importable.
- **Neon**: account (free tier), able to create one project + database.
  Console or API key — either works.
- **Upstash**: the already-provisioned Redis database (free tier) — its REST
  URL and REST token are the credentials.
- **Cloudflare**: account with R2 enabled; ability to create a bucket and an
  API token with **R2 edit** permission (account-scoped); the account ID.
- **The repository** at the integrated implementation branch (T2–T6 merged),
  clean working tree, with `python3 tools/current_spec_check.py`,
  `tools/tech_lead_guard.py`, and `tools/architecture_drift_guard.py`
  passing locally.

Provision order: **Neon → Upstash → R2 → app secrets → Vercel project →
deploy → verify → rollback proof.** Each backend is verified independently
before the next so a failed step never leaves a half-configured deployment.

## 2. Neon PostgreSQL provisioning (durable state)

1. Console: create a project (e.g. `adcos`) → a database (e.g. `adcos`);
   or via API (`POST /projects`). Free tier is sufficient (0.5 compute units).
2. Copy the **pooled** connection string — the `-pooler` host with
   `pgbouncer=true` (Neon's pooled endpoint, port 6543, plus
   `sslmode=require`). Serverless functions open many short-lived
   connections; the pooled endpoint is the correct endpoint for them.
   The direct (unpooled) endpoint works but risks connection-limit
   exhaustion under burst load.
3. Set it as `ADCOS_DATABASE_URL` (section 5/6). Treat it as a secret.

**Schema: no manual migrations.** The expected schema is created lazily by
the adapter (`backends/postgres.py`, worker 1) on first use. Two tables:

- `adcos_api_journal` — the developer-API persistence seam (the `ApiStore`
  boundary): the idempotency ledger + webhook admission/obligation records.
- `adcos_contract_journal` — the contract command-journal round trip: each
  `ContractStore` journal line is a durable row. **The `ContractStore` fold
  stays the sole state authority** — the adapter round-trips journal bytes
  and materializes them for the fold; it never computes state itself.

First-use bootstrap happens on the first readiness probe or demo call (the
lazy DDL is why `maxDuration` is 60s). Neon free-tier compute auto-suspend
(cold compute) adds a few seconds to the first query after idle — expected,
observable in `deploy/verify.py` as a slightly slower first run, never as a
silent degradation.

## 3. Upstash Redis provisioning (ephemeral coordination)

1. Use the already-provisioned Upstash database (free tier).
2. From its dashboard copy the **REST URL** and the **REST token**.
3. Set `ADCOS_REDIS_REST_URL` and `ADCOS_REDIS_REST_TOKEN`.

The adapter (`backends/upstash.py`, worker 2) speaks the Upstash REST API
over stdlib `urllib` — no SDK, no connection pooling. It implements ONLY
ephemeral coordination: the `RateLimiter` seam and cross-instance
append-serialization locks. **Redis is never canonical state**; a Redis
outage never weakens a hard contract constraint — it surfaces as a typed
backend error.

## 4. Cloudflare R2 provisioning (evidence/artifact storage)

1. R2 → create a bucket, e.g. `adcos-evidence` (any region/auto).
2. R2 → "Manage API Tokens" → create a token from the **"Object Storage:
   Edit"** template (R2 edit permission, account-scoped). This yields an
   Access Key ID + Secret Access Key.
3. Note the Cloudflare **Account ID** (dashboard right sidebar).
4. Set `ADCOS_R2_ACCOUNT_ID`, `ADCOS_R2_ACCESS_KEY_ID`,
   `ADCOS_R2_SECRET_ACCESS_KEY`, `ADCOS_R2_BUCKET`.

The adapter (`backends/r2.py`, worker 2) uses the S3-compatible REST API
with hand-rolled AWS SigV4 signing (stdlib `hmac`/`hashlib` only — no
boto3). Only artifacts/object data live in R2; **canonical metadata and
integrity records stay in durable state** (Neon).

## 5. Application secrets

| Variable | Value | Class |
|---|---|---|
| `ADCOS_ISSUANCE_KEY` | 32-byte hex string for HMAC issuance | secret |
| `ADCOS_ENVIRONMENT` | e.g. `production` | config |

Generate the issuance key without echoing it into shell history files if
your policy requires:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

(64 hex chars = 32 bytes.) `ADCOS_ENVIRONMENT` is the environment name
bound at the developer-API gateway.

## 6. Vercel project setup and deploy

### 6.1 Create the project

1. Dashboard → **Add New → Project → Import** the `payswapdotorg/ADCOS`
   repository, linked to the Hobby team.
2. Framework preset: **Other** (no framework). `vercel.json` already pins
   `"framework": null`. Root directory: repository root. Build command,
   output directory: none (zero-config Python).
3. Do NOT enable any "deploy hook"/CDN features; the ADCOS surface is the
   single Python function.

### 6.2 Environment variables (Production environment)

Set every variable below as a Project Environment Variable, environment
**Production** (values are secrets — names only are ever recorded):

| Variable | Source (section) |
|---|---|
| `ADCOS_DATABASE_URL` | Neon pooled connection string (§2) |
| `ADCOS_REDIS_REST_URL` | Upstash REST URL (§3) |
| `ADCOS_REDIS_REST_TOKEN` | Upstash REST token (§3) |
| `ADCOS_R2_ACCOUNT_ID` | Cloudflare account ID (§4) |
| `ADCOS_R2_ACCESS_KEY_ID` | R2 access key ID (§4) |
| `ADCOS_R2_SECRET_ACCESS_KEY` | R2 secret access key (§4) |
| `ADCOS_R2_BUCKET` | R2 bucket name (§4) |
| `ADCOS_ISSUANCE_KEY` | 32-byte hex HMAC key (§5) |
| `ADCOS_ENVIRONMENT` | e.g. `production` (§5) |

That 9-variable set is the complete production env-var contract
(`docs/deployment/runtime-inventory.md`). Nothing else is required;
nothing else may be assumed by the runtime.

### 6.3 Deploy

From the integrated branch (CLI form — `.vercelignore` is unambiguously
honored for CLI deploys):

```bash
VERCEL_TOKEN=<token>   # export for the command only; never echo/commit
vercel --prod --token "$VERCEL_TOKEN"
```

Or deploy via the dashboard's Git integration. Build behavior: the Python
runtime pip-installs `requirements.txt` (pg8000 only), import-traces
`api/index.py`'s top-level import of `runtime.wiring`, and bundles the
stdlib-only domain graph. There is no build step, no output directory, no
framework install — the core runtime is stdlib-only by design.

Python version: the runtime default (3.12 today; 3.13/3.14 available) —
the pure-stdlib code is version-portable, no pin needed.

### 6.4 `vercel.json` — every key documented

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "framework": null,
  "functions": { "api/index.py": { "maxDuration": 60 } },
  "rewrites": [{ "source": "/((?!api/).*)", "destination": "/api/index.py" }]
}
```

- **`$schema`** — editor/validation schema reference (openapi.vercel.sh);
  inert at deploy time.
- **`framework: null`** — no framework build pipeline. This is the
  "do-not-introduce-Next.js" boundary made explicit: Vercel deploys the raw
  repository (files + the Python function) rather than any framework's
  build output. Zero-config Python detection then serves `api/index.py`.
- **`functions["api/index.py"].maxDuration: 60`** — the per-function
  timeout in seconds. For Python functions, duration is configurable ONLY
  through the `functions` object in `vercel.json` (per current Vercel
  docs). 60s was the Hobby fluid-compute ceiling at design time; the
  current Hobby limit is 300s (fluid compute, enabled by default), so 60s
  is safely within limits and leaves headroom for cold starts, Neon
  cold-compute and the lazy schema bootstrap. If a legacy project rejects
  `maxDuration: 60` (fluid compute disabled), either enable Fluid Compute
  in project settings or lower the value to 10.
- **`rewrites`** — one transparent rewrite: every request path that does
  NOT start with `api/` (`/`, `/healthz`, `/readyz`,
  `/demo/contract-fulfillment`, `/nonexistent`, …) is routed internally to
  the Python function; `/api/*` stays direct. Vercel's routing order is
  **filesystem first, rewrites second**, so the function's own route
  (`/api/index`, the extension-stripped file route) is never shadowed by
  the rewrite, and the ASGI app receives the ORIGINAL request path (the
  rewrite is transparent), which is how the app routes `/healthz` etc.

**Known routing caveat (integration-reconciliation item).** With the
locked rewrite, `/api/*` subpaths OTHER than the function's own route do
not reach the app: the filesystem has no `api/contracts/` file and the
rewrite intentionally excludes `api/`, so e.g.
`GET /api/contracts/<id>` is answered by a platform-level (non-JSON) 404
before the app sees it. `deploy/verify.py` detects exactly this case and
prints a pointer back to this note. If worker 1's canonical contract-read
route is `/api/contracts/<id>` (the T8 harness's expectation), reconcile
ONE of these ways at integration:

- **Option A (recommended — zero-config preserved):** widen the rewrite to
  `"source": "/(.*)"` (destination unchanged). Filesystem routes still win
  for the function's own path, and `/api/contracts/<id>` reaches the app
  with the original path preserved.
- **Option B:** add a second function file `api/contracts/[id].py` that
  re-exports the same `app` (Vercel dynamic function routes) — heavier.
- **Option C:** worker 1 serves the canonical read route outside the
  `/api/` prefix (e.g. `/contracts/<id>`) and the harness path is updated.

Relatedly: if the destination form `"/api/index.py"` is not resolved at
first deploy, switch it to `"/api/index"` — the extension-stripped route
(the form used in Vercel's own Python/Flask rewrite examples). Both forms
are accepted in practice; verify at first deploy.

**`builds` fallback.** If zero-config Python detection ever fails at deploy
time (error like "No Output Directory named public found" or the function
is not detected), add the legacy explicit builder instead:

```json
"builds": [{ "src": "api/index.py", "use": "@vercel/python" }]
```

Prefer zero-config; add `builds` only on an actual detection failure, and
remove `functions`/`rewrites` conflicts as Vercel reports them.

### 6.5 `.vercelignore` and `requirements.txt`

`.vercelignore` EXCLUDES patterns only — everything unlisted ships in the
bundle, which keeps the import-traced domain graph (`runtime/`,
`backends/`, `contracts/`, `developerapi/`, `agent/`, `protocol/`,
`evidence/`, `executionplans/`, `adapters/`, `offers/`, `capabilities/`,
`policy/`, `eligibility/`, `assurance/`, `replan/`, `resilience/`) inside
the deployment. Excluded: `spec/`, `docs/`, `tools/`, `.github/`,
`deploy/`, `worker-charters/`, root `*.md` (README/AGENTS — no governance
files in production; `.git/` and `__pycache__` are excluded
automatically). Result: a smaller, faster bundle with no accidental
governance/CI/operator files. For Git-integration deploys, confirm the
exclusions in the build logs; the runtime-native alternative (if needed)
is `"functions": {"api/index.py": {"excludeFiles": "{spec,docs,tools,deploy}/**"}}`.

`requirements.txt` pins exactly one dependency — `pg8000==1.31.2`, the
pure-Python PostgreSQL driver — the ONLY third-party dependency, lazily
imported by `backends/postgres.py` when `ADCOS_DATABASE_URL` is set; the
core runtime is stdlib-only. Vercel pip-installs it at build time.

### 6.6 First-deploy gotchas (expected, all benign)

1. **Cold start on first request** — the domain graph import takes a
   moment; `deploy/verify.py` allows 20s per request and retries transient
   network errors once (retries are printed).
2. **Neon cold compute** — the first readiness/demo call after idle pays
   compute-wake + lazy schema bootstrap seconds (within the 60s budget).
3. **Deployment Protection** — preview deployments may be protected; the
   production domain must have Vercel Authentication disabled (project →
   Settings → Deployment Protection) for the harness to reach it.
4. **`maxDuration` validation** — see §6.4 (60 is within current limits).
5. **The `/api/*` routing caveat** — see §6.4; check 5 of the harness is
   the canary for it.
6. **`readyz` 503 on first call** — if a backend env var is missing or a
   provider rejected the credentials, readiness fails CLOSED with the
   per-backend detail (the harness captures it). Fix the env var, redeploy
   (env-var changes require a redeploy to take effect on existing
   instances).

## 7. Verification (T8 live acceptance)

From the integrated repository checkout:

```bash
python3 deploy/verify.py --base-url https://<production-domain> --expect-mode production
```

Eight checks (each one table row `[ok]/[FAIL]/[skip] name — detail`; exit 0
only when every executed check passes):

1. `GET /healthz` — 200, `ok:true`, service name reported.
2. `GET /readyz` — 200 (a 503 is captured with its per-backend detail and
   FAILs acceptance); reported mode matches `--expect-mode`.
3. `POST /demo/contract-fulfillment` — 200, `evidence_class == "SOFTWARE"`,
   contract/plan/execution/evidence chain non-empty.
4. **Determinism** — the demo run twice produces byte-identical bodies
   (sha256 reported).
5. **Persistence** (production only) — `GET /api/contracts/<id-from-demo>`
   → 200 with the same canonical contract: a durable round-trip across
   separate serverless invocations (cold-start-spanning proof that state
   survived the process, i.e. Neon is actually holding it).
6. **Coordination** (production only) — `/readyz` sub-check: the
   coordination backend (Upstash) is configured-healthy in the readiness
   payload.
7. **Artifacts** (production only) — `/readyz` sub-check: the artifact
   backend (R2) is configured-healthy.
8. **Error surfaces** — `GET /nonexistent` → 404 typed envelope
   `{"error": {"reason_code": "not-found", ...}}`.

With `--expect-mode sandbox` (preview/deterministic-demo deployments)
checks 5–7 print `[skip]` rows and the pass count excludes them. The
harness is stdlib-only (`urllib`), sets a 20s timeout per request, and
retries transient network errors once per request with the retry visible
in the output. Rollback verification is deliberately NOT automated here —
it is the Vercel-side procedure in §8.

Also run the repository verification suite at the integrated SHA
(`tools/current_spec_check.py`, `tools/tech_lead_guard.py`,
`tools/architecture_drift_guard.py`, and the domain batteries per
`.github/workflows/spec-check.yml`) — deployment acceptance requires the
full repository verification results, not only the live checks.

## 8. Rollback (must be exercised once in production as acceptance evidence)

Vercel rollback is an **instant routing-layer alias switch** — no rebuild,
effective within seconds. **Hobby-plan constraint (current Vercel docs):
rollback can target only the immediately previous production deployment**
(Pro/Enterprise can target any). The proof procedure must therefore be
staged:

1. Deploy the accepted build **D1** (§6.3); run `deploy/verify.py` → all
   green; record output + deployment ID.
2. Deploy a deliberately distinguishable but harmless **D2** (e.g. a
   docstring-only change); confirm the production domain serves D2
   (deployment URL/ID differs).
3. Roll back: `vercel rollback` (or `vercel rollback <d1-deployment-url>`
   where supported), or dashboard → Deployments → D1 → ⋯ → Rollback.
4. Re-run `python3 deploy/verify.py --base-url <production-domain>
   --expect-mode production` → all green again; record output.

The app is stateless: **Neon journal rows and R2 artifacts persist through
rollback** (nothing is deleted or rewound). D2-era journal records remain
by design — the journal is append-only and never rewritten; the fold is
re-derived from the durable journal, which is precisely the recovery
discipline being proven. Expected duration: seconds.

## 9. Free-tier posture

- Quota exhaustion (Vercel function invocations/duration, Neon compute or
  storage, Upstash requests/day, R2 storage/Class-A operations) surfaces as
  **typed backend errors** — e.g. `reason_code: backend-unavailable`-class
  envelopes and a 503 readiness with the failing backend named — **never
  silent degradation and never a fallback to in-memory canonical state**.
- `GET /readyz` is the always-accurate aggregate: 200 only when every
  configured backend is configured-healthy; otherwise 503 + per-backend
  detail (the harness captures and prints it).
- Monitor the four provider dashboards (Vercel Usage; Neon project metrics;
  Upstash database metrics; Cloudflare R2 metrics). Free tiers are
  sufficient for acceptance-scale traffic; they are not assumed permanent
  or sufficient for production load.
- Hard contract constraints are never weakened by infrastructure failure:
  a backend outage fails closed with an explicit error surface.

## 10. Evidence collection (deployment acceptance artifacts)

Record exactly these (and nothing containing secret VALUES):

1. The exact merged implementation SHA (post-integration).
2. The exact Vercel production deployment identifier + URL (D1), and the
   rollback pair (D2 + the rollback to D1).
3. Provider resources used — **names/IDs only**: Neon project/database
   name, Upstash database name, R2 bucket name, Vercel project/team name.
4. The full `deploy/verify.py` production output (all green) — captured
   verbatim, including the retry lines if any occurred.
5. The rollback proof: D1/D2 deployment IDs + the verify outputs before
   and after rollback.
6. The env-var NAMES ONLY (the 9-variable contract in §6.2).
7. The full repository verification results at the integrated SHA.
8. The explicit statement: **deployment acceptance is software-class
   only** — it does not prove physical connectivity and does not satisfy
   or modify physical evidence obligations EVID-002..EVID-008 (the
   independent physical-validation track is untouched).
