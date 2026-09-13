# The ADCOS deployment acceptance record (T7/T8 complete)

**Date**: 2026-09-13 (UTC) · **Authority**: DEC-0126 (the bounded
deployment authorization; the Tech Lead owns ALL implementation and
deployment execution) · **Operator directive**: "Time to deploy".

This is the runbook §10 evidence collection for the deployment
acceptance. The acceptance is **SOFTWARE-CLASS ONLY** (item 8 below).

## 1. The accepted implementation SHA

`73856f1` — `fix(backends): the stale-socket drop-and-retry repair —
the warm-instance permanent failure (DISCLOSED)` on
`deployment/build-fallback`, on top of the merged delivery line:

- `5a06833` Merge PR #51 (the integrated T2–T6 delivery, DEC-0126 scope)
- `aaacadc`/`124b599`/`dd1778c` the coordination fallback (PR #52; the
  unreachable-Upstash disclosure)
- `dc2399d` the runbook 6.4 builds fallback + the build-cache bust
- `6067147` spec/schemas is runtime data (the registry-starved
  demonstration repair)
- `de1a220` the T8 harness contract-id key paths (the disclosed shape
  reconciliation)
- `73856f1` **the accepted head** (the stale-socket repair — see §4a)
- `6b84d1b` the D2 rollback-proof marker (docstring-only; NOT part of
  the accepted semantics — identical code to 73856f1)

## 2. The Vercel production deployments + the rollback pair

- **D1 (THE ACCEPTED PRODUCTION DEPLOYMENT)**:
  `dpl_JE6EuY6evcYfHxKP4S6N1fecKdFf` @ `73856f1` —
  https://adcos.vercel.app (READY, PROMOTED; the production alias
  routes here).
- **D2 (the rollback-proof build)**: `dpl_BsNvPRSBHDnCTQdkxwcDgTvTN7mG`
  @ `6b84d1b` (docstring-only marker; deployed and promoted, then
  rolled back).
- **Rollback**: the routing-layer alias switch (Vercel alias
  `adcos.vercel.app` reassigned D2 → D1; instant, no rebuild). The
  post-rollback re-verify is green (§4b).
- Historical: the first-ever production deployment was
  `dpl_2f5XFNxb3XfLsXLRYX4dfhBY1QJ7` @ main `5a06833`; the first
  healthy build-fallback production build was
  `dpl_BxadefSr1CUqHwgp3CARi5RpE5a3` @ `6067147` (the stale-socket
  failure was observed on it — §4a).

## 3. Provider resources (names/IDs ONLY — no secret values)

- **Neon**: project `adcos` / `late-term-67047167` (org
  `org-shy-shadow-21570034`, free_v3, `aws-us-east-1`, pg16,
  pooled endpoint; `suspend_timeout` on the free tier — the compute
  auto-suspends on idle, the reality the §4a repair addresses).
- **Upstash**: the operator-supplied REST coordinate pair. The REST
  token was REFRESHED by the operator (2026-09-13) and deployed
  encrypted to the Vercel production env (`ADCOS_REDIS_REST_TOKEN`).
  The REST **host remains unreachable from every network tested** —
  the sandbox (all of `*.upstash.io` DNS-sinkholed there) AND the
  Vercel production network (`transport raised URLError` at assembly).
  The design-authorized coordination fallback is therefore ACTIVE and
  DISCLOSED (readiness `upstash: degraded-ok`; the in-process
  RateLimiter, single-instance scope). OPERATOR ACTION ITEM: the
  hostname of record does not resolve publicly; if the refreshed token
  belongs to a different (newer) Upstash database, supplying its REST
  URL activates the distributed limiter with one env-var change + one
  redeploy — no code change.
- **Cloudflare R2**: NOT available — the operator's Cloudflare account
  has R2 not enabled (error 10042; enabling it is a Dashboard action,
  not an API action). The all-four-or-none artifact contract honestly
  zero-sets the R2 keys; the production artifact backend is the
  Neon-durable evidence store (probed, ready).
- **Vercel**: project `adcos` (`prj_ZWSPQ0raftGehNNRJ9C5mXiRrtYb`,
  Hobby team `team_4KOoA5CgtYaOF85yFXPeMXLt`, fluid compute, region
  `iad1`). The Composio gateway was the provisioning/deployment
  channel (toolkits: vercel, neon, cloudflare, github — the
  operator-connected accounts).

## 4a. The stale-socket failure and its repair (the disclosed
integration repair at the accepted head)

Observed live on `dpl_BxadefSr1CUqHwgp3CARi5RpE5a3` minutes after the
T8 acceptance passed on it: `readyz` reported `postgres` +
`evidence_store` `unavailable: network error` on EVERY subsequent
probe and the demo failed (`contract demo is unknown`) while the Neon
project was healthy. ROOT CAUSE: the postgres adapter cached ONE
lazily-opened connection and its failure path never dropped it — the
Neon free-tier suspend killed the cached TCP connection and the warm
process reused the corpse forever (pg8000 `InterfaceError: network
error`; only a cold start recovered).

THE REPAIR (`73856f1`): a failure drops-and-retries ONLY when it
PROVES the cached connection dead (socket-family failure or an
undeliverable rollback); exactly ONE bounded retry on a fresh
connection; deterministic statement failures raise exactly as before.
Evidence: `tools/persistence_selftest.py` case_25 (battery now 25/25,
x3 byte-identical); all deployment batteries + the three governance
gates green at the head; a REAL-Neon reproduction (health#1 ready →
390 s idle with the connection held → health#2 READY in 2.03 s — the
drop, the reconnect waking the suspended compute, the retried probe);
and the production suspend-recovery proof below.

## 4b. The production proofs at D1

- **T8 live acceptance (before rollback)**: `python3 deploy/verify.py
  --base-url https://adcos.vercel.app --expect-mode production` →
  **PASS 8/8** (output §5, first block).
- **The suspend-recovery production proof**: after 390 s of production
  idle (the Neon suspend window), THREE consecutive `readyz` probes:
  `postgres=ready, evidence_store=ready, upstash=degraded-ok,
  ok=true` — the warm production instance recovered from the suspended
  database WITHOUT a cold start (the exact scenario that previously
  broke production permanently), followed by a live demo round-trip
  (`POST /demo/contract-fulfillment` → 200, `evidence_class:
  SOFTWARE`, full chain).
- **T8 re-verify after rollback**: **PASS 8/8** (output §5, second
  block).

## 5. The `deploy/verify.py` production outputs (verbatim)

```
ADCOS live acceptance — https://adcos.vercel.app (expect-mode: production)

[ok  ] healthz                  — 200 ok=true service=adcos-runtime
[ok  ] readyz                   — 200 mode=production; backends: {evidence_store=ready, postgres=ready, upstash=degraded-ok}
[ok  ] demo-fulfillment         — 200 evidence_class=SOFTWARE chain: contract/plan/execution/evidence non-empty
[ok  ] determinism              — two runs byte-identical (sha256:577e24cfd361, 6023 bytes)
[ok  ] persistence              — GET /api/contracts/sha256%3A224878b79fe24519ece798751ab04087d81d713ed2206d1ff1f73004c1d78333 → 200 canonical fields round-trip identically (read projection adds 0 envelope field(s))
[ok  ] coordination-backend     — configured-healthy (readiness[backends.upstash]: degraded-ok)
[ok  ] artifact-backend         — configured-healthy (readiness[backends.evidence_store]: ready)
[ok  ] error-surface            — 404 typed envelope reason_code=not-found; message='no route matches GET /nonexistent'

Result: PASS (8/8 checks)
```

(The same output, byte-for-byte in every field, was produced before the
rollback and after the rollback — both runs at D1. The determinism
sha256 `577e24cfd361…` is identical across both runs and across every
demo invocation of the day, including from the sandbox-mode
batteries' reference.)

## 6. The environment-variable NAMES (the §6.2 contract)

Production (Vercel, encrypted, target=production):
`ADCOS_ENVIRONMENT`, `ADCOS_DATABASE_URL` (the Neon pooled URI),
`ADCOS_REDIS_REST_URL`, `ADCOS_REDIS_REST_TOKEN` (the operator's
refreshed 2026-09-13 token), `ADCOS_ISSUANCE_KEY` (a generated 32-byte
hex). The R2 quartet is honestly zero-set (R2 unavailable — §3).

## 7. The repository verification at the accepted head

- `tools/persistence_selftest.py`: **25/25** (x3 byte-identical;
  case_25 is the stale-socket repair proof).
- `tools/runtime_selftest.py`: **25/25**.
- `tools/coordination_selftest.py`: **22/22**.
- `tools/adapter_selftest.py`: **70/70**.
- `tools/artifact_selftest.py`: **15/15**.
- `tools/current_spec_check.py`: **PASS**.
- `tools/tech_lead_guard.py`: **PASS** (≤3 workers discipline held
  throughout — every dispatch this day was ≤2 concurrent).
- `tools/architecture_drift_guard.py`: **PASS** (implementation-only
  delta).
- The full production-mode local smoke against the REAL Neon backend:
  mode=production, backends ready, demo `evidence_class=SOFTWARE`,
  byte-determinism IDENTICAL.

## 8. The software-class-only statement

**Deployment acceptance is SOFTWARE-CLASS ONLY.** It does not prove
physical connectivity and does not satisfy or modify the physical
evidence obligations EVID-002..EVID-008 — the independent
physical-validation track (the R4/W040 hardware batteries) is untouched
by this deployment and remains governed by its own accepted
authorities.

## Verdict

**ADCOS IS DEPLOYED.** The production service at
https://adcos.vercel.app serves the accepted build (D1), recovers from
provider idle-suspension without cold starts, holds its durable state
in Neon, discloses its one degraded backend honestly (Upstash, with
the operator action item recorded in §3), and has exercised the
rollback path end-to-end. T7 and T8 are COMPLETE.
