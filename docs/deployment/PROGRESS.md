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
- T7 (provision + deploy) and T8 (live acceptance) PENDING: await the
  provider credentials, the integrated T2–T6 result, and the Tech Lead's
  execution of docs/deployment/runbook.md.

## TODO.txt

T6 complete (w3: Vercel config, runbook, verify harness). T7/T8: run the
runbook with provider credentials after T2–T6 integration.
