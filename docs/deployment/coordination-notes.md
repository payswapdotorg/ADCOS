# ADCOS coordination + artifact storage surface notes (T4 + T5 — Worker 2 delivery)

The ephemeral-coordination and artifact-storage surface delivered
under the DEC-0126 bounded authorization: the Upstash Redis REST
coordination adapter (the RateLimiter seam + cross-instance
serialization locks) and the Cloudflare R2 evidence/artifact
storage adapter (S3-compatible REST with hand-rolled SigV4).
Everything here is a THIN provider boundary at the verified
seams (consumed BY REFERENCE with the accepted ADCOS 1.1
authorities — no accepted file was modified, no domain semantics
re-implemented; see `docs/deployment/runtime-inventory.md` for
the verified seam map and `docs/deployment/runtime-notes.md` for
worker 1's runtime surface that consumes these adapters through
`build_app_from_env`).

## Modules

| module | role |
|---|---|
| `backends/upstash.py` | the Upstash Redis REST coordination adapter (stdlib + the sanctioned in-repo seams) |
| `backends/r2.py` | the Cloudflare R2 artifact-storage adapter (pure stdlib; hand-rolled SigV4) |
| `tools/coordination_selftest.py` | the T4 coordination battery (21 cases) |
| `tools/artifact_selftest.py` | the T5 artifact-storage battery (15 cases) |

## The two invariants

**RedisNeverCanonical** (`backends/upstash.py`): the Upstash
adapter stores ONLY ephemeral coordination state — per-application
rate-limit counters and cross-instance serialization locks. NO
canonical ADCOS state may live behind it: the ConnectivityContract
journal (ContractStore over durable persistence) remains the sole
canonical authority; a Redis/Upstash outage can never become
canonical state and never silently weakens a hard contract
constraint (backend failure NEVER silently allows — every failure
is the typed `UpstashCoordinationError`).

**The R2 metadata boundary** (`backends/r2.py`): R2 holds ONLY
object bytes. Canonical metadata — artifact references, integrity
checksums, evidence records — lives in DURABLE state (the
Neon-backed persistence seams behind the accepted authorities).
`R2ArtifactStore.put` returns the ArtifactRef the durable side
records and carries no state authority beyond it; `get_verified`
closes the loop by verifying the object bytes against the
durable-side checksum (a divergence is the typed
`integrity-mismatch` failure — never a silent substitution).
Key allocation stays durable-side: `put` REQUIRES an explicit
key (the adapter takes no key-minting authority).

## The adapters' surfaces

### `backends/upstash.py`

- `UpstashRateLimiter(rest_url, rest_token, transport=None,
  key_prefix, limit, window_seconds, clock=None)` — the
  `developerapi.ratelimit.RateLimiter` seam implemented over the
  Upstash REST API: `check(application_id)` returns the REAL
  `RateDecision` while under the limit, and the blocked outcome
  MIRRORS the accepted in-process limiter outcome-for-outcome
  (the `rate-limited` `DeveloperApiError` with truthful
  `retry_after` — an unmodified `DeveloperGateway` translates it
  into the same canonical 429 with `Retry-After`). Fixed-window
  discipline: one counter key per application
  (`<key_prefix>:<application_id>`), `INCR` + `TTL`, the expiry
  anchored ONCE at the first increment of a window (never
  refreshed — the window boundary cannot drift). Free-tier
  exhaustion (HTTP 429 from Upstash) is the explicit
  `explicit-limit` failure, never a silent allow.
- `UpstashLock(rest_url, rest_token, key, ttl_ms, transport=None,
  token=None)` — cross-instance append serialization over
  `SET key token NX PX ttl`: atomic acquire (a duplicate
  acquisition by ANYONE returns `False` — never a takeover),
  owner-only release/extend (GET must equal the instance's own
  derived token), TTL observation (`-1` no expiry, missing →
  `None`). The ownership token is deterministic and never
  appears in any error surface.
- The injectable `clock` (an `AgentClock`) keeps every decision
  instant deterministic; the default is the sanctioned
  `SystemClock` (the module's sole OS-time site).

### `backends/r2.py`

- `R2ArtifactStore(account_id, access_key_id, secret_access_key,
  bucket, transport=None)` — `put(key, data, content_type)` /
  `get(key)` / `head(key)` / `delete(key)` /
  `get_verified(key, content_sha256)` over path-style object URLs
  (`https://<account_id>.r2.cloudflarestorage.com/<bucket>/<key>`,
  key segments preserved, remaining characters percent-encoded).
- The ArtifactRef (`put` return, the durable-side record):
  `{"key", "size", "content_sha256", "etag", "backend"}` — the
  checksum is the sha256 of the exact bytes, the ETag a
  pass-through from the response (unquoted). `delete` returns
  `{"key", "deleted": True, "backend"}` with S3 idempotent
  semantics (the deletion is observable through the follow-up
  read — the typed `missing-object` failure).
- AWS Signature V4 is implemented BY HAND (service `s3`, region
  `auto`; the frozen signed-header set
  `host;x-amz-content-sha256;x-amz-date`): no boto3, no
  requests. Signing is a pure function of
  (method, url, payload hash, amz_date) — deterministic when the
  stamp is pinned; the production default reads the OS clock
  ONCE for the `x-amz-date` stamp (the sole wall-clock site in
  the module).

## The typed failure vocabulary (both adapters frozen)

| reason code | upstash meaning | r2 meaning |
|---|---|---|
| `backend-unavailable` | transport exception / HTTP 5xx-class trouble (never a silent allow or a silent read) | transport exception / HTTP 400/409/429/5xx (never a silent success) |
| `config-invalid` | bad URL/token/limit/window/prefix/clock/key/ttl shapes; refused credentials (HTTP 401/403) | bad account id / access key id / secret / bucket shapes; malformed `put`/`get_verified` arguments; refused credentials (HTTP 401/403) |
| `protocol-error` | malformed REST response bodies | successful responses lacking the S3 response headers (ETag, Content-Length) or a non-numeric length |
| `explicit-limit` | free-tier exhaustion (HTTP 429 from Upstash) | — |
| `lock-not-held` | release/extend by a non-owner or on a missing key | — |
| `missing-object` | — | the object does not exist (HTTP 404; get-after-delete included) — never a silent empty read |
| `integrity-mismatch` | — | the object bytes diverge from the durable-side checksum — never a silent substitution |

Both error types carry `.reason_code`, `.detail`, and
`.backend` (`"upstash"` / `"r2"`); an out-of-vocabulary reason is
rejected at construction. Secret hygiene: the REST bearer token,
the lock ownership tokens, the R2 access key id and the secret
access key NEVER appear in any error surface or string
representation of a failure (the Authorization wire header is
their sole carrier — Bearer for Upstash, SigV4 Credential for
R2).

## The environment-variable contract (additions)

| variable | role |
|---|---|
| `ADCOS_REDIS_REST_URL` + `ADCOS_REDIS_REST_TOKEN` | BOTH present → `backends.upstash.UpstashRateLimiter(rest_url=..., rest_token=...)` at the gateway's rate-limiter seam (imported LAZILY by worker 1's `runtime/wiring.py` only when the pair is complete); otherwise the accepted deterministic in-process `RateLimiter` |
| `ADCOS_R2_ACCOUNT_ID` / `ADCOS_R2_ACCESS_KEY_ID` / `ADCOS_R2_SECRET_ACCESS_KEY` / `ADCOS_R2_BUCKET` | the `R2ArtifactStore` configuration, validated all-or-none by the runtime wiring (a partial set fails closed `config-invalid`) and reported in readiness as DELEGATED |

These are the only new environment members; the full production
contract is in `docs/deployment/runtime-notes.md`. No secret ever
rides in Git — the batteries run on synthetic constants against
in-memory fakes.

## The transport contracts (the injectable seams the batteries ride)

- **upstash** (2-tuple): `(method, url, headers, body) ->
  (status, body)`. `method` is always `POST` (commands ride the
  URL path, each segment URL-quoted), `headers` always carries
  `Authorization: Bearer <token>`, `body` is always empty. May
  raise on network trouble (mapped to the typed
  `backend-unavailable`); the default is `urllib` with a bounded
  timeout.
- **r2** (3-tuple, one member richer — S3 object metadata such
  as ETag and Content-Length lives in RESPONSE HEADERS):
  `(method, url, headers, body) -> (status, response-headers
  dict with LOWERCASED names, body)`. Same raise discipline; the
  default is `urllib` with a bounded timeout.

## Batteries

- `python3 tools/coordination_selftest.py` — 21 cases: the module
  surface (RedisNeverCanonical documented), config-invalid
  shapes, the RateLimiter seam (the real `RateDecision`, at-limit
  parity with the in-process limiter, window reset/anchoring,
  per-application scoping, the typed failure map incl. 429 →
  `explicit-limit`), the serialization lock (atomic acquire, no
  takeover, owner-only release/extend, expiry + reacquire, TTL
  semantics, fail-closed backend trouble), secret hygiene,
  determinism (identical traces; unique-per-instance auto
  tokens), and the unmodified `DeveloperApiService` gateway seam
  (a throttled mutation mints NOTHING canonical).
- `python3 tools/artifact_selftest.py` — 15 cases: the module
  surface (the metadata-boundary invariants documented),
  config-invalid shapes, put/reference shape, byte-identical get
  round trips, the verified-read success path, the checksum
  discipline (independent sha256 == the signed wire payload
  hash; the ETag a response pass-through), the typed
  missing-object, the typed integrity-mismatch, delete +
  get-after-delete, backend failure (dead transport, 5xx/4xx
  status mapping, credential refusal), protocol errors, SigV4
  signing (format pinned; byte-identity against an INDEPENDENT
  re-derivation over a pinned amz_date; stability and input
  binding), secret hygiene, determinism (unique-per-put keys),
  and the metadata-boundary contract (the reference carries
  exactly key/size/checksum/etag/backend).

Both print `Result: PASS (N/N cases)` and exit 0/1; both are
deterministic (byte-identical outputs across runs, verified x3
across `PYTHONHASHSEED` 0/1/7919), offline (in-memory fakes of
the two REST surfaces; no network), stdlib only.

## Disclosed repairs

- **The R2 delete seam** (worker 2, on its own module): the T5
  battery's delete case exposed that the committed
  `backends/r2.py` — the killed worker's uncommitted handoff —
  listed `DELETE` in its signed method vocabulary but exposed no
  `R2ArtifactStore.delete` (and `_send` mapped every non-200 to
  a failure, so the S3 no-content success HTTP 204 would have
  been misclassified as `backend-unavailable`). The repair added
  `delete(key)` returning the deletion reference, taught `_send`
  an `ok_statuses` widening (default `(200,)` unchanged for
  put/get/head; DELETE accepts 200/204), and documented the seam
  in the class docstring. No other behavior changed; the T4
  battery was untouched and stayed 21/21. No repair was needed
  in `backends/upstash.py` (the T4 battery verified it as
  committed).
