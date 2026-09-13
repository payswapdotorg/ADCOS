# ADCOS runtime surface notes (T2 + T3 — Worker 1 delivery)

The deployment runtime surface delivered under the DEC-0126 bounded
authorization: a pure-stdlib ASGI application + the injected-services
carrier + the deterministic sandbox builder + the env-based assembly +
the Neon PostgreSQL durable adapter. Everything here is a THIN
composition AROUND the ACCEPTED ADCOS 1.1 domains (consumed BY REFERENCE
— no accepted file was modified, no domain semantics were re-implemented;
see `docs/deployment/runtime-inventory.md` for the verified seam map).

## Modules

| module | role |
|---|---|
| `runtime/__init__.py` | package docstring / exports list |
| `runtime/asgi.py` | the pure-stdlib ASGI app (`app`, `build_app(services)`) |
| `runtime/services.py` | `RuntimeServices` — the one injected-services carrier |
| `runtime/sandbox.py` | `build_sandbox_services()` — deterministic in-memory runtime |
| `runtime/health.py` | liveness/readiness handlers |
| `runtime/demo.py` | the deterministic contract-fulfillment demonstration |
| `runtime/wiring.py` | `build_app_from_env()` — the env-based assembly |
| `backends/postgres.py` | the Neon durable adapter (stdlib at import; lazy `pg8000`) |
| `tools/runtime_selftest.py` | the runtime battery (24 cases) |
| `tools/persistence_selftest.py` | the persistence battery (24 cases) |

## HTTP surface (canonical JSON in/out; `content-type: application/json`)

| route | behavior |
|---|---|
| `GET /healthz` | liveness — always `200` `{"ok":true,"service":"adcos-runtime"}` |
| `GET /readyz` | readiness — `200` when every consumed backend is ready, `503` with per-backend detail otherwise; carries `"mode": "sandbox"\|"production"`, the environment name, the per-backend probe states, and the delegated (worker-2) backend notes |
| `POST /demo/contract-fulfillment` | the deterministic demonstration; optional JSON body member `"instant"` (RFC 3339 UTC; default the fixed `2026-09-13T00:00:00Z`) |
| `GET /demo/contract-fulfillment` | the same demonstration, idempotently — byte-identical body to the default `POST` |
| `GET /api/contracts/{contract_id}` | the canonical contract read. With `X-ADCOS-Application` + `X-ADCOS-Credential` (+ optional `X-ADCOS-API-Version`) headers the request rides the accepted `developerapi` boundary (its own canonical envelope, verbatim); without them the platform-side public store read is served |
| anything else | `404` `{"error":{"reason_code":"not-found",...}}` |

Error discipline: EVERY error is the typed envelope
`{"error": {"reason_code", "message", "backend"}}`. Domain errors keep
their frozen reason codes verbatim (the developerapi canonical-reason
table is reused BY REFERENCE for status mapping); request bodies are
capped at 1 MiB (`413 payload-too-large`); malformed JSON is `400
malformed-json`; no stack trace or raw exception text ever escapes
(unexpected failures collapse to a bare `internal-error`).

## `build_app_from_env()` — the environment contract

| variable | role |
|---|---|
| `ADCOS_DATABASE_URL` | PRESENT → production mode (Neon-backed durable authorities). ABSENT → deterministic sandbox mode |
| `ADCOS_ENVIRONMENT` | the environment name bound at the gateway (`sandbox`\|`production`; default `sandbox`). `production` REQUIRES the database URL |
| `ADCOS_ISSUANCE_KEY` | hex-encoded issuance key material. REQUIRED in production (fail closed, never a default). In sandbox: honored when present; when absent the documented DEMO-ONLY key is derived and a warning is logged to stderr |
| `ADCOS_REDIS_REST_URL` + `ADCOS_REDIS_REST_TOKEN` | BOTH present → worker 2's `backends.upstash.UpstashRateLimiter(rest_url=..., rest_token=...)`, imported LAZILY inside the wiring function only (a missing module → typed `upstash-unavailable` error); otherwise the accepted deterministic in-process `RateLimiter` |
| `ADCOS_R2_ACCOUNT_ID` / `ADCOS_R2_ACCESS_KEY_ID` / `ADCOS_R2_SECRET_ACCESS_KEY` / `ADCOS_R2_BUCKET` | worker 2's consumption — validated all-or-none (a partial set fails closed `config-invalid`) and reported in readiness as DELEGATED; never probed by this surface |

Mode switching is driven by `ADCOS_DATABASE_URL` alone: present →
`build_production_services` (schema bootstrap, journal materialization,
journal-first gateway recovery over the durable rows; any backend
failure raises the typed `PostgresBackendError` and ABORTS the assembly —
there is NO in-memory fallback for canonical state anywhere); absent →
`build_sandbox_services` (in-memory authorities, the fixed clock, the
documented demo-only issuance key).

The module-level `runtime.asgi.app` lazily assembles the env-wired
runtime on the first request (importing `runtime.asgi` is
side-effect-free; the Vercel entrypoint is `from runtime.asgi import
app`). A failed production assembly answers with the same typed error
envelope (the failing backend named); the failure is not cached, so a
recovered backend is picked up on the next request.

## The demonstration response (worker 3's verify-harness contract)

`POST`/`GET /demo/contract-fulfillment` returns:

```json
{
  "mode": "sandbox"|"production",
  "environment": "<name>",
  "evidence_class": "SOFTWARE",
  "instant": "<the request instant>",
  "boundary": [{"method": "POST", "route": "/api/2.0/intents", "status": 200, "request_id": "..."}],
  "contract": {"contract_id": "sha256:...", "state": "CONTRACT_ACTIVE", ...},
  "plan": {"plan_id": "...", "segments": [{"segment_id": "...", "state": "RELEASED", ...}]},
  "execution": {"sandbox": true, "activation_id": "...", "reservation_id": "...", "measurement_id": "...", "release_id": "...", ...},
  "evidence": [{"record_type": "observation", ...}, {"record_type": "attestation", ...}]
}
```

The integration-relevant invariants (all battery-pinned):

- the created contract id is at the stable top-level path
  `contract.contract_id`;
- the response is canonical-JSON-serializable (the response bytes ARE
  `canonical_json_bytes` of the parsed body);
- `evidence_class == "SOFTWARE"` — always; the demonstration never
  claims physical connectivity (EVID-002..EVID-008 stay open);
- identical inputs → byte-identical responses: `POST` (default body),
  `GET`, three fresh app instances, and `PYTHONHASHSEED` 0/1/7919
  subprocesses all produce the same bytes; the optional `instant`
  drives a genuinely new demonstration contract, and re-sending the
  same instant replays byte-identically (the boundary's durable
  idempotency ledger + the canonical journal's duplicate discipline);
- in production mode every write lands in the durable journals
  (`adcos_api_journal`, `adcos_contract_journal`,
  `adcos_evidence_journal`) and a SECOND assembly over the same rows
  recovers and re-runs the demonstration byte-identically.

## The composed chain (all accepted services, BY REFERENCE)

1. **request boundary leg** — `developerapi.gateway.DeveloperApiService.handle`
   (`developerapi/gateway.py:1752`): create intent → accept offer (opaque
   typed reference) → activate, driven with the platform-held demo
   credential (`issue_application_credential`, `gateway.py:761`);
2. **planning leg** — `executionplans.translation.translate_contract`
   (`executionplans/translation.py:176`) + `verify_plan_preserves_contract`
   (LOCK-108) + the store's public `BindExecutionArtifact` command
   (LOCK-117: the plan rides as an opaque `execution-artifact` reference);
3. **execution leg** — `adapters.capability.CapabilityAdapter`
   (`adapters/capability.py:797`) over the WORK-016 `AdapterRuntime` and
   the M007 RAN reference composition (`adapters/reference/ran.py:282`
   `mount_reference`) — the reference adapters ARE the deterministic
   sandbox providers (reserve → activate → measure → release, mirrored by
   `apply_segment_transition` PLANNED→RESERVED→ACTIVATED→MEASURED→RELEASED);
   a fresh composition is mounted per run over a deterministic WORK-012
   session (`sessions.SessionStore` walked REQUESTED→AUTHORIZED→ESTABLISHED
   over a `routing.RoutingEngine` decision);
4. **evidence leg** — `evidence.ObservationEvidence` (the adapter-reported
   `link-up` sample) + `evidence.AttestationEvidence` (the
   controller-verified released-segment count) ingested in the injected
   `evidence.EvidenceStore` (idempotent; LOCK-118 provenance).

The only time source is the injected `agent.clock` seam: the sandbox
world runs on `FixedClock`; the production service clock is the
sanctioned `SystemClock` (gateway-internal timestamps only — every
instant the demonstration SURFACES is request-declared).

## The Neon durable adapter (`backends/postgres.py`)

- `PostgresApiStore(ApiStore)` — the developer-API journal seam
  (`append_line`/`read_lines` exactly matching the ABC/file-store
  semantics; table `adcos_api_journal(seq BIGSERIAL PRIMARY KEY,
  line TEXT NOT NULL)`);
- `PostgresContractJournal` — `load_lines()`, `append_lines(lines)`
  (ONE transaction, all-or-nothing), `materialize_store(journal_path)`
  (writes the loaded lines to a local JSONL file and constructs the
  accepted `ContractStore` over it; subsequent appends persist to BOTH
  the live store's file and postgres). Table
  `adcos_contract_journal(namespace TEXT NOT NULL DEFAULT 'default',
  seq BIGSERIAL, line TEXT, PRIMARY KEY(namespace, seq))`;
- `PostgresEvidenceJournal` — the same discipline for the typed evidence
  journal (`adcos_evidence_journal`, same shape);
- every failure raises `PostgresBackendError` with
  `.reason_code` (`backend-unavailable` | `config-invalid` |
  `schema-error`) and `.backend = "postgres"` — free-tier quota
  exhaustion included; NEVER a silent in-memory fallback;
- `pg8000` is imported LAZILY inside the real connection factory only
  (the `service_selftest` optional-import pattern): importing
  `backends.postgres` (and the whole runtime wiring) never imports it —
  battery-pinned via `sys.modules` subprocess probes;
- the adapter moves JOURNAL BYTES, never state: the accepted folds
  (`ContractStore` construction-is-recovery, `EvidenceStore` fold,
  `AppendOnlyApiJournal` hash chain) stay the ONLY state authorities;
  LOCK-119 secret scanning fires in the ACCEPTED persist path BEFORE
  any durable row exists (battery-pinned);
- the batteries run the full adapter contract against deterministic
  fake DB-API connections (injectable `connection_factory`) — no
  Postgres, no network, no third-party imports.

## DEMO-ONLY issuance material (disclosed)

`runtime.sandbox.SANDBOX_ISSUANCE_KEY` is a fixed digest over a PUBLIC
constant — deliberately not a secret, deliberately never acceptable in
production mode (production requires the real `ADCOS_ISSUANCE_KEY`,
fail closed). When sandbox mode runs without `ADCOS_ISSUANCE_KEY` a
warning is logged to stderr naming the fallback explicitly.

## Batteries

- `python3 tools/runtime_selftest.py` — 24 cases: liveness shape,
  readiness per mode (incl. the 503 backend-unavailable path and the
  delegated R2 note), demo POST/GET byte-identity + three fresh
  instances + cross-`PYTHONHASHSEED` determinism, the evidence-chain
  shape (`evidence_class == "SOFTWARE"`, `contract.contract_id`), the
  canonical-JSON serialization contract, error envelopes
  (404/400/413/invalid-input), both contract read modes, the lifespan
  protocol, sandbox/production honesty invariants, and the
  production-mode demo over the fake durable backend;
- `python3 tools/persistence_selftest.py` — 24 cases: the ApiStore seam
  contract (byte-exact round-trip, seq ordering, newline discipline,
  file-store parity), the contract/evidence journal round-trips (single
  transaction all-or-nothing, namespace isolation, dual persistence,
  re-materialization byte-identity), journal-first gateway recovery,
  the fail-closed discipline (typed errors, never fallback), LOCK-119
  passthrough, the lazy-import guard, and the production
  assembly/recovery over durable rows.

Both print `Result: PASS (N/N cases)` and exit 0/1; both are
deterministic (byte-identical outputs across runs), offline, stdlib
only.
