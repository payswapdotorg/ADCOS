## Current deployment progress

- Deployment design recorded.
- Implementation plan recorded.
- Bounded deployment authorization recorded as DEC-0126 on the isolated deployment branch.
- Runtime inventory verified against the actual source tree and populated
  (T1 COMPLETE at the post-PR-#49 implementation base): pure-stdlib Python,
  no manifest, no HTTP entrypoint today; the composition seams verified —
  ContractStore journal, ApiStore persistence ABC, RateLimiter coordination
  seam, the developerapi gateway request boundary, executionplans bridge,
  EvidenceStore, the ShareNet vertical composition, the M007 adapter seam.
- T2 (HTTP/runtime boundary), T3 (Neon persistence), T4 (Upstash
  coordination), T5 (R2 evidence storage) IN FLIGHT (workers w1/w2,
  DEC-0126 limits).
- T6 (Vercel configuration + operations) COMPLETE (worker w3, branch
  `deployment/w3-vercel`): delivered `api/index.py` (the thinnest ASGI
  entry — zero-config Vercel Python detection of the top-level `app`
  export), `vercel.json` (framework:null; the single function with
  maxDuration 60; the site-traffic rewrite keeping `/api/*` direct),
  `requirements.txt` (pg8000==1.31.2 — the ONLY third-party dependency,
  lazily imported), `.vercelignore` (bundle exclusions: governance/CI/
  operator files out, import-traced domain graph in), `deploy/verify.py`
  (the T8 live-acceptance harness: health/readiness/mode, the
  contract→plan→execution→evidence demo with evidence_class=SOFTWARE,
  byte-determinism, durable persistence round-trip, coordination/artifact
  readiness sub-checks, typed 404 error surface; mode-conditional skips;
  stdlib-only urllib with timeouts and visible retry-once), and
  `docs/deployment/runbook.md` (the T7/T8 operational manual: Neon/Upstash/
  R2 provisioning, the 9-variable env contract, Vercel project setup and
  deploy, per-key vercel.json documentation, first-deploy gotchas
  including the `/api/*` routing caveat with fallbacks, verification,
  Hobby-constrained rollback proof, free-tier posture, evidence
  collection). One integration-reconciliation item is documented in the
  runbook: the locked rewrite excludes `/api/*`, so
  `/api/contracts/<id>` needs the Option A/B/C reconciliation at
  integration (verify.py check 5 is the canary).
- T2-T5 COMPLETE: worker w1 delivered the DEC-0126 deployment runtime +
  Neon durable adapter (branch `deployment/w1-runtime`: runtime/{asgi,demo,
  health,sandbox,services,wiring}.py + backends/postgres.py + the runtime
  and persistence batteries 24/24 + 24/24 + runtime-notes.md); worker w2
  delivered the Upstash coordination + R2 artifact adapters (branch
  `deployment/w2-coord`: backends/{upstash,r2}.py + the coordination and
  artifact batteries 21/21 + 15/15 + coordination-notes.md, one disclosed
  adapter repair — the missing R2 delete seam).
- INTEGRATION COMPLETE on branch `deployment/integration-20260913`
  (merge base 8de8706, the shared runtime-20260913 base): the three worker
  deliveries merged (w1 T2+T3, w2 T4+T5, w3 T6); the runbook 6.4 routing
  caveat RECONCILED with Option A (the vercel.json rewrite widened to
  "/(.*)" so worker 1's canonical `GET /api/contracts/{id}` read route
  reaches the app; filesystem routes still win for the function's own
  path); all four deployment batteries green at the integrated head
  (runtime 24/24, persistence 24/24, coordination 21/21, artifact 15/15)
  plus the three governance gates (current_spec_check PASS,
  tech_lead_guard PASS, architecture_drift_guard PASS —
  implementation-only delta: 28 files) and an end-to-end in-process
  smoke of the assembled ASGI surface (healthz/readyz/demo/read/404
  determinism all green in sandbox mode).
- INTEGRATION VERIFICATION COMPLETE (the pre-merge full-suite pass):
  all four deployment batteries green at the integrated head after the
  Tech Lead's REAL-Neon pre-verification repairs (the stdlib-platform
  shadowing pin + the DB-API conditional fetch; the R2 delete seam and
  the Upstash readiness probe from the worker batteries); the three
  governance gates PASS; the production-mode smoke against the REAL
  provisioned Neon database green (readyz 200 with postgres +
  evidence_store backends ready; the demo evidence_class=SOFTWARE with
  the canonical contract read round-trip and byte-determinism).
- LEDGER-RECON-041 recorded on main (3d80235 + the companion checker
  evolution 71e06b5): the snapshot baseline advanced 4045ef0 -> 2d69418
  and tools/authorization_provenance.py taught the DEC-0126
  decision-borne authorization class — the simulated GitHub-direction
  merge passes the provenance gate (the 28-file delta fully covered)
  and the payment battery 44/44 (case_38 authorization-aware).

- THE FIRST PRODUCTION DEPLOYMENT (D1 = dpl_2f5XFNxb3XfLsXLRYX4dfhBY1QJ7
  at https://adcos.vercel.app, from main 5a06833): healthz/artifacts/
  error-surface green; the Upstash coordinates proved unreachable from
  every network (recorded for the operator); the design-authorized
  coordination fallback delivered on this branch (the accepted
  in-process limiter with the degraded-ok disclosure); the T8
  acceptance re-run follows this merge.
- T7 (provision + deploy) IN FLIGHT: the operator supplied the provider
  credential set (GitHub PAT, Composio gateway with connected vercel/neon/
  cloudflare/github toolkits, the Upstash REST coordinates); provisioning
  via the Composio channel per the runbook order Neon -> Upstash -> R2 ->
  app secrets -> Vercel project -> deploy.

- T7 (provision + deploy) and T8 (live acceptance) PENDING: await the
  provider credentials, the integrated T2–T6 result, and the Tech Lead's
  execution of docs/deployment/runbook.md.

- THE BUILD-FALLBACK SEQUENCE (the lost-window record, reconstructed
  from the repository): the first healthy production build took the
  runbook 6.4 builds fallback (dc2399d: .vercelignore/build cache) and
  the registry-starved demonstration repair (6067147: spec/schemas/ is
  runtime data — the domain authorities machine-load the protocol
  schema and the capability/access-profile/identity registries at
  request time, so the wholesale spec/ exclusion starved the demo
  path); the T8 harness's persistence check needed the disclosed
  contract-id key-path widening (de1a220). First full T8 PASS 8/8 at
  dpl_BxadefSr1CUqHwgp3CARi5RpE5a3 @ 6067147.
- THE STALE-SOCKET FAILURE AND REPAIR (73856f1, the accepted head):
  minutes after that 8/8, readyz reported postgres/evidence_store
  "network error" on EVERY probe while Neon itself was healthy — the
  adapter's cached connection was a corpse (Neon free-tier idle
  suspend) that the failure path never dropped, so the warm instance
  failed permanently until a cold start. The surgical repair: drop +
  ONE bounded retry only on PROVEN connection death (socket-family
  failure or undeliverable rollback); deterministic failures raise
  exactly as before. Battery case_25 (25/25 x3); REAL-Neon repro:
  ready → 390s idle → READY in 2.03s; production suspend-recovery
  proven (3 consecutive ready probes + a live demo round-trip after
  the suspend window).
- THE OPERATOR'S REFRESHED UPSTASH TOKEN deployed encrypted to the
  Vercel production env — and the REST host remains unreachable from
  the Vercel network too (URLError at assembly; the sandbox DNS for
  *.upstash.io is sinkholed so only the Vercel-side probe is
  authoritative). The disclosed coordination fallback stays active
  (degraded-ok). Operator action item recorded: the hostname of record
  does not resolve publicly; supply the REST URL matching the refreshed
  token to activate the distributed limiter (one env change + one
  redeploy, no code change).
- THE DEPLOYMENT ACCEPTANCE (runbook §8 + §10; full record in
  docs/deployment/acceptance-record.md): D1 =
  dpl_JE6EuY6evcYfHxKP4S6N1fecKdFf @ 73856f1 (T8 PASS 8/8;
  suspend-recovery proof; readyz ok=true with postgres ready for the
  first time in production); D2 = dpl_BsNvPRSBHDnCTQdkxwcDgTvTN7mG @
  6b84d1b (the docstring-only marker build, deployed + promoted); the
  routing-layer rollback D2 -> D1 (instant alias switch); the
  post-rollback T8 re-verify PASS 8/8 (byte-identical determinism
  sha256 577e24cfd361…). All deployment batteries + the three
  governance gates green at the accepted head. Software-class-only
  acceptance; the physical-validation track untouched.
- **T7 AND T8 COMPLETE — ADCOS IS DEPLOYED at https://adcos.vercel.app.**

## TODO.txt

T6 complete (w3: Vercel config, runbook, verify harness). T7/T8: run the
runbook with provider credentials after T2–T6 integration.
