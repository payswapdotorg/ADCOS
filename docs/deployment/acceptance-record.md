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

---

# The Developer Console deployment acceptance (DEC-0127 program close)

**Date**: 2026-09-14 (UTC) · **Authority**: DEC-0127 (the developer
console implementation program) via `docs/tech-lead/ADCOS-DEVELOPER-CONSOLE-HANDOFF.md`
§Deployment acceptance · **Operator directive**: the Vercel deployment
token supplied 2026-09-14 (the one credential this step awaited).

This section is the runbook §10 evidence collection for the console
deployment. The acceptance is **SOFTWARE-CLASS ONLY** (the statement
in §8 carries forward unchanged).

## C1. The accepted implementation SHA

`a04b3ee` — `console(deploy): the catch-all route continues into the
builder's routing phases` on `main`, on top of the merged console
delivery line (PRs #55/#56/#57/#58 — the DEC-0127 program — RECON-pinned
through LEDGER-RECON-049) plus the deployment-session commits:

- `e4dd80c` the home checked-at test determinism repair (test-side)
- `aab5182`/`c5a8b78` the Vercel station-link gitignore hygiene
- `8764e4e` the `[...unmatched]` catch-all + the T8 check-8 console-topology
  amendment (the disclosed reconciliation, same class as `de1a220`)
- `a04b3ee` **the accepted head** (the one-word routing repair:
  `"continue": true` on the legacy catch-all route)

## C2. The console production deployments

- **D1c (the first console deployment)**:
  `dpl_7jiHPEJGSLCSw4hjCTdDTUGunxBu` @ the tree of `8764e4e` —
  https://adcos.vercel.app served the console at `GET /` for the first
  time; T8 7/8 (check 8 FAIL exposed the routing defect, below).
- **D2c (the catch-all attempt)**: `adcos-4xigagf86…` @ the same tree —
  proved the catch-all alone does NOT reach the Next function for
  unmatched paths (the platform static 404 persisted).
- **D3c (the routing-repair deployment)**: `adcos-p6bu2hlhu…`
  (`dpl_2N438DE5Aj9Jx89CXCkBudFtTMfT`) @ the tree of `a04b3ee`
  (uploaded from a working tree byte-identical to the `a04b3ee`
  commit; the repair was committed immediately after). T8 **8/8 PASS**
  (§C4) — the first fully-green console deployment.
- **D4c (THE ACCEPTED CONSOLE DEPLOYMENT, final)**:
  `adcos-ivgdapdec…` (`dpl_6v6CPeoiBLw2Bxkn44wAQm4YeZT4`) @ the clean
  committed checkout of `eaa2c77` (this record + the progress entry;
  runtime content identical to `a04b3ee`) — https://adcos.vercel.app
  (READY, PROMOTED; the production alias routes here). T8 re-run
  **8/8 PASS** against it; the browser acceptance (§C5) was performed
  against the same content.

## C3. The routing defect and the disclosed repair (integration
forensics)

The legacy `builds`+`routes` catch-all
`{"src": "/(.*)", "dest": "/web/$1"}` **terminates at literal filesystem
resolution**: every path with no static build output — the console's
dynamic routes (`/connectivity/contracts/[id]`,
`/fulfillment/run/[instant]`), the `[...unmatched]` not-found funnel,
and every RSC payload request for them — was answered by the platform's
static 404 before any function was consulted. `GET /connectivity/contracts/<id>`
→ platform 404 in D1c/D2c while `/web/connectivity/contracts/<id>`
(direct, prefixed) → 200 proved the builder's own routing phases worked
and only the user-route delegation was broken. The repair —
`"continue": true` on that one route — lets the rewritten path flow into
the @vercel/next builder's routing phases (filesystem checkpoints, RSC
variant rewrites, dynamic function addressing). Verified live: the
dynamic contract detail, the not-found boundary, RSC client navigation
(`text/x-component` payloads), and the Python runtime surface all serve
correctly on the production alias.

## C4. The T8 harness (the amended check 8)

`python3 deploy/verify.py --base-url https://adcos.vercel.app
--expect-mode production` → **PASS 8/8** on D3c:

1. healthz — 200 ok=true service=adcos-runtime
2. readyz — 200 mode=production; postgres=ready, evidence_store=ready,
   upstash=degraded-ok (the unchanged honest disclosure; §3 of the prior
   record carries the operator action item)
3. demo-fulfillment — 200 evidence_class=SOFTWARE, chain non-empty
4. determinism — byte-identical (sha256:577e24cfd361 — the same digest
   as the prior acceptance: the demo contract is unchanged by the
   console deployment)
5. persistence — the canonical contract round-trip across serverless
   invocations (Neon holds it)
6. coordination-backend — configured-healthy (degraded-ok)
7. artifact-backend — configured-healthy (ready)
8. error-surface (the console-topology amendment, disclosed in the
   harness docstring): **(a)** API space — `GET /api/nonexistent` → the
   runtime's typed envelope `reason_code=not-found` (the boundary the
   runtime owns; the handoff's "API errors retain canonical reason
   codes" holds); **(b)** console space — `GET /nonexistent` → 404
   rendered by the console's not-found boundary (the `[...unmatched]`
   funnel presenting the backend's own `route-unknown` vocabulary —
   developerapi/errors.py ROUTE_UNKNOWN — never an invented surface).

## C5. The console handoff's deployment acceptance — item by item

1. **`GET /` returns the actual ADCOS console** — VERIFIED (browser:
   the workbench renders; title `Home`; the full nav, the session menu,
   the command palette).
2. **`/healthz` and `/readyz` semantics intact** — VERIFIED (T8 checks
   1–2 unchanged; the Settings page renders the live documents; the
   Home system-health card shows mode/environment VERBATIM with the
   per-backend states).
3. **Core resource journeys work in the deployed environment** —
   VERIFIED (browser: the demo create journey on Fulfillment →
   "Demonstration complete", evidence_class SOFTWARE; the demo-run read
   journey `/fulfillment/run/2026-09-14T15:00:00Z` with the full record
   anatomy; the evidence read journey with the verbatim class
   vocabulary; the contract detail page honestly discloses its reads
   are authenticated developer-API reads; zero page errors across the
   whole browser session).
4. **A create/mutation journey reproducible through the displayed API
   request** — VERIFIED (the Fulfillment demo card displays
   `POST /demo/contract-fulfillment` with the body AND the copyable
   curl; the Request Inspector captured the console-made POST with the
   per-request drawer's curl reproduction — screenshot
   `scripts/logs/prod-request-drawer.png` at the station).
5. **API errors retain canonical reason codes** — VERIFIED (§C4 item 8a;
   plus the console's not-found boundary renders `route-unknown`
   VERBATIM with the request descriptor).
6. **R0–R9 governance and deployment checks green** — VERIFIED (the
   governance trio at `a04b3ee`: current_spec_check PASS,
   tech_lead_guard PASS, architecture_drift_guard PASS; the web suite
   212/212 incl. the 2 new not-found-boundary tests; T8 8/8).
7. **No physical evidence obligations claimed** — VERIFIED (the
   evidence-class legend renders `physical / network` as
   NOT-ACHIEVABLE-BY-THIS-DEPLOYMENT verbatim; the demo evidence is
   SOFTWARE and the page states "SOFTWARE evidence never becomes a
   physical PASS").

## C6. Rollback posture

The rollback PATH was proven end-to-end in the prior acceptance (§2:
the D1/D2 alias switch, instant, state preserved). The same
routing-layer mechanism applies to the console deployments; the app
remains stateless (Neon journal rows and R2 artifacts persist through
any alias switch). No new rollback drill was required by the console
handoff's acceptance list; the operator can exercise
`vercel rollback` against D1c/D2c at will.

## C7. Deviations and disclosures (console deployment)

- The routing repair (`a04b3ee`) is a deployment-topology fix, not an
  implementation-domain change (vercel.json only).
- The T8 check-8 amendment is disclosed in the harness docstring and
  this record (the same class as the `de1a220` widening).
- The console-space not-found boundary (`[...unmatched]` → not-found)
  presents the backend's `route-unknown` reason with a locally-authored
  message ("No console route matches this path.") — the reason code is
  backend vocabulary VERBATIM; the message is the boundary's own
  framing, disclosed here.
- The Upstash degraded-ok state is UNCHANGED from the prior acceptance
  (the operator action item — the REST hostname of record — still
  stands; one env change + redeploy activates the distributed limiter).
- The production demo credential remains out-of-band by design (the
  issuance key is encrypted in the Vercel project env; the console's
  session journeys that need it were accepted locally against the
  sandbox runtime and are exercisable in production the moment an
  operator connects a real issued credential).

## C8. Software-class-only statement (carried forward)

The console deployment acceptance is **SOFTWARE-CLASS ONLY**. It does
not prove physical connectivity and does not satisfy or modify the
physical evidence obligations EVID-002..EVID-008 — the independent
physical-validation track (the R4/W040 hardware batteries) is untouched
by this deployment and remains governed by its own accepted
authorities.

## Verdict (console program)

**THE ADCOS DEVELOPER CONSOLE IS DEPLOYED.** The production service at
https://adcos.vercel.app serves the console at `GET /`, the runtime's
health/readiness/error semantics are intact at their boundaries, the
core resource journeys work in the deployed environment, the mutation
journey is reproducible through displayed API requests, and the
governance gates are green. DEC-0127's deployment step is COMPLETE.

---

# D. The Console V2 learning-first product experience (DEC-0128)

## D1. The program and the frozen direction

The operator delivered the frozen Console V2 direction via PR #59
(branch `console/v2-learning-experience`, docs-only +492/-0): the
product, learning & documentation design
(`docs/superpowers/specs/2026-09-14-adcos-console-v2-learning-experience-design.md`,
APPROVED / FROZEN FOR IMPLEMENTATION) and the eight-task implementation
plan
(`docs/superpowers/plans/2026-09-14-adcos-console-v2-learning-experience.md`).
DEC-0128 registered the bounded program (repository-local,
decision-borne, outside the halted gate sequence) with the authorized
surface: the V2 learning layer inside `web/`, the planning documents,
the Tech Lead dispatch state, the deployment verification records and
the routing. DEC-0127 was retired to SUPERSEDED with the same
reconciliation (RECON-051).

## D2. The implementation waves (all merged, all RECON-pinned)

- **PR #60 — the W1 education wave** (merge `e12ff83`, pin
  LEDGER-RECON-053): the education model (`web/src/lib/education/` — 14
  concepts, 25/25 operation-learning records referencing the accepted
  coverage-registry operation ids verbatim, 7 playbook guides, 449
  machine-checked cross-references with the coverage test failing on
  unknown links), the learning primitives (`ConceptLink`,
  `ConceptExplainer` with full focus management, `NextStep(s)`,
  `ObjectEducation`; honest unknown states everywhere), and the
  documentation system (15 `app/docs` routes: Start here, the
  registry-generated Concepts/Guides/API pages with the real
  method/path VERBATIM, the honest no-SDK page, Errors VERBATIM,
  Troubleshooting with the §17 replan-events disclosure stated
  verbatim, Reference, route-local search, contextual return paths).
- **PR #61 — the W2+W3 waves** (merge `9069714`, pin
  LEDGER-RECON-054): the first-run product surface (the frozen anchor
  sentence verbatim, the clickable mental-model lifecycle, the eight
  I-want-to goals; connected users keep the V1 expert dashboard), the
  nine-step Quickstart on the REAL typed client, the interactive
  fulfillment tour (Requirement → Eligibility → Plan → Execution →
  Evidence → Assurance with the Explain/View affordances), the seven
  Playbooks from the guide registry with the Open-in-workbench context
  preservation, the About-this-operation Explorer education (collapsed
  by default, zero execution-semantics regression), the
  canonical-reason troubleshooting guidance (the frozen anatomy, the
  verbatim backend reasons untouched, unknown codes keep the V1 honest
  treatment), and the shell nav/palette integration.
- **PR #62 — the Task-8 browser-acceptance repairs** (merge `f54cde5`,
  pinned with PR #63 by LEDGER-RECON-055): two dynamic-route-template
  defects the LIVE browser acceptance caught (both invisible to the
  mocked-Link unit suites): `next-step.tsx` passed route templates raw
  to `<Link>` (the eligibility lifecycle drawer crashed), and
  `CONSOLE_ROUTE_SET` contained the template string itself so the
  "de-templating" walk returned the raw template (the concept page
  crashed). Both render paths now de-template to the static workspace
  ancestor; regression tests added.
- **PR #63 — the .vercelignore anchoring repair** (merge `b687f42`):
  the unanchored `docs/` gitignore pattern matched
  `web/src/features/docs/` at EVERY level and silently excluded the
  entire V2 documentation system from the Vercel upload — the first
  production deploy attempt (dpl_HcZkjwFsa2ExZmhTMSnoJJN2b641, from
  f54cde5) failed `module-not-found` exactly there while every local
  gate passed (the upload, not the build, was the divergence). The
  root-level operator/CI excludes are now anchored
  (`/docs/`, `/tools/`, `/.github/`, `/deploy/`,
  `/worker-charters/`).
- **LEDGER-RECON-055** also records the disclosed process lesson: the
  PR-#62 merge closed without its immediate pin and the PR-#63 CI
  caught the stale pin failing closed exactly as designed; the
  merge-order mistake (a non-gated merge script) is recorded honestly
  and was repaired by that one reconciliation.

## D3. The production deployment

- **Deployed:** `dpl_ACsCcGbeewjWpqGF9KY1TYG7Bd6F`
  (`adcos-ao8hi4g5q-ekonplacidegmailcoms-projects.vercel.app`) from
  the clean committed checkout at `6a08487` (the RECON-055 head) —
  READY, aliased to https://adcos.vercel.app.
- The routing topology (the `"continue": true` catch-all + the
  `[...unmatched]` boundary) carries the V2 routes unchanged: `/`
  serves the V2 learning-first home; `/quickstart`, `/tour`, `/docs`,
  `/docs/*`, `/playbooks`, `/playbooks/*` all reachable; `/api/*`,
  `/healthz`, `/readyz`, `/demo/*` remain the Python runtime
  (`/healthz` → `{"ok":true,"service":"adcos-runtime"}` at the time of
  this record).

## D4. The V2 acceptance standard — verified item by item

The frozen design's ten-point acceptance standard (§18), verified over
production with the agent-browser (zero page errors across every
visited route):

1. **Understand ADCOS's purpose without external explanation** — the
   first-run home renders the frozen anchor sentence verbatim under
   "WHAT ADCOS DOES", with the honest expert note.
2. **Describe the core lifecycle after the quickstart** — the clickable
   mental model (Describe requirement → Eligibility → Plan →
   Fulfillment → Assurance → Continuous fulfillment) opens the real
   registry education per stage (verified: the Eligibility drawer on
   production).
3. **Complete the guided connectivity journey** — the Quickstart walked
   all nine steps end to end on production, finishing at the
   registry-composed next paths.
4. **Understand the important objects encountered** — steps 3-7 render
   the real contract/plan/execution/evidence objects (ObjectEducation +
   JSON views).
5. **Find the relevant API operation from the workflow** — step 8 shows
   the curl and links the Explorer deep-link; the tour's View-API
   affordances.
6. **Execute at least one supported operation and understand the
   response** — the demo POST on production:
   `POST /demo/contract-fulfillment {"instant":"2026-09-14T20:40:00Z"}`
   → `mode: production, evidence_class: SOFTWARE`, 2 evidence records;
   the Explorer's About-this-operation education renders for
   intent_create (collapsed by default).
7. **Locate documentation for every primary concept** —
   `/docs/concepts/<id>` for all 14 registry concepts; the eligibility
   page renders the six questions (What is it? / Why does it matter? /
   When do I use it? / What happens in ADCOS? / What does the API look
   like? / Where do I go next?).
8. **Find troubleshooting guidance for canonical errors** —
   `/docs/troubleshooting` with the §17 replan-events disclosure
   verbatim; the error workbench's guidance section.
9. **Move from beginner guidance into the expert V1 workbench without
   losing context** — the Quickstart's "Open the expert workbench", the
   Playbooks' Open-in-workbench affordances carrying `?from=`, the
   LEARN nav group beside the V1 primary nav; `/connectivity` (the V1
   workbench) verified alive on production.
10. **Complete the primary journey without unexplained jargon** — every
    architecture-heavy term in the V2 surfaces carries a ConceptLink /
    ConceptExplainer affordance (the W1 registry is the single
    vocabulary source; the coverage test fails on drift).

## D5. The release gate (the plan's Task 8)

- The V1 regression battery: **307/307 tests** (the V1 210 + 97 V2
  tests) at the acceptance head; tsc clean; lint clean; the production
  build green (31 static pages + the platform routes).
- The governance gates at every merge: current_spec_check,
  tech_lead_guard, drift_guard, fresh-session — green on every pinned
  head (the four failing-closed PR-#59 runs recorded at RECON-052 are
  the gates' own evidence trail).
- The browser acceptance over the local stack (13 routes, zero page
  errors — the acceptance that caught the two PR-#62 defects) AND over
  production (the D4 journey above).
- The CI runs: PR #60 (#34892352231-class green), PR #61 green, PR #62
  green (34891335584), the RECON pushes green.

## D6. Deviations and disclosures (V2)

- The W1-c station subagent was cut off by a tool-context deadline
  mid-test-fix pass; the station completed the remainder (three test
  assertions + the api-hub first-match-wins grouping repair). The
  W2/W3 station subagents' final reports were lost the same way — the
  work itself was complete on disk and verified by the station gate
  (304/304 at the wave head); the Tech Lead integration pass is the
  record of what was verified.
- The docs pages link `/quickstart` (W2's route) — the links landed
  with the W1 wave while the route arrived with W2; both waves merged
  within the program so the links were never dead on main.
- The first production deploy attempt failed (dpl_HcZkjwFsa…) — the
  `.vercelignore` anchoring defect (D2, PR #63); the failed deployment
  never served traffic (the alias never moved).
- The Upstash degraded-ok state and the production demo credential
  posture are UNCHANGED from §C7 (carried forward verbatim).

## Verdict (Console V2 program)

**THE CONSOLE V2 LEARNING-FIRST PRODUCT EXPERIENCE IS DEPLOYED AND
ACCEPTED.** https://adcos.vercel.app now serves a self-teaching console
at `GET /` — Understand → Build → Integrate → Operate → Diagnose —
with every V1 expert capability regression-protected (307/307), the
frozen acceptance standard verified item-by-item over production with
zero page errors, and the DEC-0128 program's eight tasks complete.
SOFTWARE-CLASS ONLY (§C8 carries forward unchanged): no physical
evidence obligation is claimed, EVID-002..EVID-008 stay open, and the
R4/W040 physical-validation track is untouched.
