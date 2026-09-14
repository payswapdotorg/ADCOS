# ADCOS Developer Console (`web/`)

The web control surface for the ADCOS runtime: a developer workbench for
inspecting objects, traversing relationships, understanding failures,
performing supported actions, and reproducing UI actions as API requests.

**Worker 1 (console-foundation) delivered:** the app shell + routing, the
design system, the typed API client + coverage registry, the session store,
the command palette/search infrastructure, and the Vercel topology.
Workers 2 and 3 fill the feature areas on top of these contracts.

## Stack

- Next.js 15 (App Router) + TypeScript (strict) + Tailwind CSS 3.4
- Radix primitives ONLY where keyboard/focus behavior demands it
  (`@radix-ui/react-dialog`, `@radix-ui/react-dropdown-menu`)
- Vitest + Testing Library (deterministic; NO network — fetch is mocked at
  the module/global boundary)
- npm, Node 20+

No component library heavier than Radix headless primitives. No second
backend: **`web/` contains no route handlers under `app/api/` — the Python
runtime owns `/api/*`, `/healthz`, `/readyz`, `/demo/*` in every
environment.**

## Setup

```bash
cd web
npm ci            # installs from the committed lockfile
```

## The local backend (required for dev)

The console talks to the ADCOS runtime same-origin. In dev, Next rewrites
`/api/*`, `/healthz`, `/readyz`, `/demo/*` to
`ADCOS_BACKEND_URL` (default `http://127.0.0.1:8088`). Start the runtime
with the stdlib wrapper (kept OUTSIDE the repo — never commit it):

```bash
python3 /path/to/serve_adcos.py   # binds 127.0.0.1:8088, prints the demo credential
```

The sandbox server prints the demo application id + credential at startup.
Enter them via the session menu (**Connect application**) — they are held
IN MEMORY ONLY (a reload clears the session by design; the console never
persists credentials to any browser storage).

## Commands

```bash
npm run dev        # dev server (rewrites proxy API paths to the backend)
npm run build      # production build (must pass clean)
npm start          # serve the production build
npm run lint       # eslint (next lint) — must pass clean
npm test           # vitest in run mode — must pass
npm run test:watch # vitest in watch mode
```

## Tests

`tests/` — deterministic, no network:

- `client.test.ts` — every domain function's URL/method/headers/body
  contract, idempotency-key generation + passthrough, verbatim reason
  preservation (boundary + runtime envelopes), network-failure synthesis
- `coverage.test.ts` — the registry holds EXACTLY the 21 developer-API
  operations + 4 platform routes, no duplicates, mutations + examples
- `shell.test.tsx` — nav renders all areas; connect/disconnect flows with
  the exact auth headers; reason-verbatim failure display
  (`@radix-ui/react-dropdown-menu` is mocked with a deterministic stub —
  the real Radix DropdownMenu drives floating-ui `autoUpdate` while open,
  which starves the jsdom event loop for ~15s per open; the real Radix
  Dialog primitives run for real in the drawer/palette suites)
- `command-palette.test.tsx` — Cmd/Ctrl+K, filtering, arrow navigation,
  Enter execution, Escape close
- component suites for the design system primitives (status, evidence
  badge, error state, data table, json viewer, code block, drawer, api
  request panel)

## The API contract (summary)

Base: same-origin `/api/2.0/*`. Auth headers on every developer-API
request: `X-ADCOS-Application`, `X-ADCOS-Credential`, `X-ADCOS-API-Version:
2.0`. Mutations also require `X-ADCOS-Idempotency-Key` (the client
auto-generates one via `crypto.randomUUID()` unless supplied). Success is
always HTTP 200 with the envelope `{api_version, environment, request_id,
data, idempotency?, rate_limit}`; list operations carry `{items,
next_cursor, has_more}` as `data` and take pagination in the **GET JSON
body** (`{limit (1..100, default 20), cursor, filters}`). Errors carry
`error.reason` VERBATIM (`authentication-invalid`, `route-unknown`,
`invalid-input`, `resource-unknown`, `invalid-transition`, …) — the console
never replaces a backend reason with a generic message.

Full route table + typed surface: `src/lib/api/coverage.ts` (the registry)
and `src/lib/api/client.ts` (the transport).

## Vercel topology

The root `vercel.json` builds both surfaces and routes explicitly — the
invariant: `/api/*`, `/healthz`, `/readyz`, `/demo/*` ALWAYS go to the
Python function (`api/index.py`); every other path serves the console;
there is no catch-all rewrite to the function:

```json
"routes": [
  { "src": "/api/(.*)", "dest": "/api/index.py" },
  { "src": "/(healthz|readyz)", "dest": "/api/index.py" },
  { "src": "/demo/(.*)", "dest": "/api/index.py" },
  { "src": "/(.*)", "dest": "/web/$1" }
]
```

### `.vercelignore` decision

The pre-existing `.vercelignore` (governance/spec/operator exclusions) does
NOT exclude anything the web build needs — `web/` itself is included, and
the `@vercel/next` build installs its own dependencies from
`web/package.json`. The ONLY additions made for the console are python
bundle hygiene entries (local build/test artifacts that must never ship in
the serverless bundle): `web/node_modules`, `web/.next`, `web/tests`,
`web/coverage`. Nothing else was added — `web/src` stays included.

## Published interfaces (for Workers 2/3)

Import with the `@/` alias (→ `web/src/`).

| Surface | Import | Notes |
| --- | --- | --- |
| Client | `@/lib/api/client` | `AdcosClient` / `createAdcosClient`; 21 domain functions + 4 platform functions; auto idempotency keys |
| Types | `@/lib/api/types` | every envelope + resource shape, derived from REAL responses |
| Errors | `@/lib/api/errors` | `AdcosApiError`, `describeError`, `isAdcosApiError`, `parseErrorBody` |
| Coverage | `@/lib/api/coverage` | `COVERAGE` (25 entries), lookups, mutations/reads/platform helpers |
| Session | `@/lib/session` | `useSession()` → `{status, application, error, client, connect, disconnect}` — memory only |
| Theme | `@/lib/design/theme` | `useTheme()`, `ThemeProvider`, `themeInitScript` |
| Tokens | `@/lib/design/tokens` | `statusToneFor`, `STATUS_TONES`, `evidenceClassKind` |
| Design system | `@/components/ui` | barrel: `Status`, `DataTable`, `ObjectHeader`, `Drawer`, `Timeline`, `JsonViewer`, `CodeBlock`, `EmptyState`, `ErrorState`, `FilterBar`, `CommandPalette`, `ApiRequestPanel` (+ `buildCurl`), `EvidenceBadge`, icons |
| Shell | `@/components/shell/*` | `AppShell`, `Sidebar`, `TopBar`, `EnvironmentIndicator`, `SessionMenu`, `ConnectDialog`, `AreaPlaceholder` |
| Search | `@/features/search` | `registerCommand`, `useCommands`, `addRecent`, `useRecentObjects`, `fuzzyMatch`, `CommandPaletteMount` |
| Requests | `@/features/requests` | `useRequestLog` (in-memory log the client feeds) |
| Object views | `@/lib/objects` | `ObjectViewSection`/`ObjectField`/`ObjectReference`/`ObjectActivityEntry` contracts |

Conventions: Tailwind semantic classes only (`bg-surface`, `text-ink`,
`border-line`, `text-positive`… — see `src/app/globals.css`); backend state
values and reason codes VERBATIM; SOFTWARE vs physical evidence always
through `EvidenceBadge`; every mutation surface embeds `ApiRequestPanel`;
secrets never persisted (memory only).

## Worker 2 surfaces (console/connectivity)

Routes (all thin server pages rendering client feature views):

| Route | Feature | What it renders |
| --- | --- | --- |
| `/` | `@/features/home` | system health (real `/readyz`), contracts summary by state (linked), recent activity (latest contracts + this session's request log), action-required (INTENT/OFFER_SELECTED + degraded backends), the fulfillment-demonstration affordance — no vanity KPIs |
| `/connectivity` | `@/features/contracts` | the contracts DataTable; state / free-text / validity-overlap narrowing (client-side over the fetched list) |
| `/connectivity/new` | `@/features/contracts/builder` | the intent builder: guided fields 1:1 with the canonical members + advanced canonical-JSON mode; unknown members preserved; byte-equal constraint serialization; exact `POST /api/2.0/intents` preview |
| `/connectivity/contracts/[id]` | `@/features/contracts` | the lifecycle chain Requirements → Eligibility → Plan → Execution → Assurance → Continuous fulfillment; next-step cards (accept offers / activate); termination drawer (the contract's OWN condition vocabulary); leases (grant/renew/revoke with the validity-window rule); raw JSON |
| `/networks` | `@/features/networks` | the execution composition (provider/adapter/access technology/standard mechanisms, SOFTWARE badge), the provider-topology boundary notice, consumed backends — no invented metrics |
| `/fulfillment` | `@/features/fulfillment` | run the demonstration (custom instant), the session run registry (honest scope note), the contracts list, the replan link |
| `/fulfillment/run/[instant]` | `@/features/fulfillment` | the full chain: boundary trace (with API reproduction), contract, plan (constraint_fingerprint, segments, state chain), execution milestones + samples, provider, evidence records, assurance, determinism note |
| `/fulfillment/replan` | `@/features/replan` | the honest replan surface — no replan decisions are exposed by this deployment; the future card shape renders as a labeled wireframe |

Worker 2's published interfaces (on top of Worker 1's):

| Surface | Import | Notes |
| --- | --- | --- |
| Eligibility presentation | `@/features/eligibility` | `useAdcosRead` (the shared read discipline — refresh re-fetches, no cache), `FlowStatePanel` / `VerbatimNote` / `RefValue` / `RefList` (backend reason data VERBATIM), `ObjectSection` / `ObjectFieldGrid` (the section-card composition primitives) |
| Demo-run registry | `@/features/fulfillment/demo-runs` | `useDemoRuns`, `registerDemoRun`, `DEFAULT_DEMO_INSTANT` — in-memory, session-scoped (the backend exposes no run registry) |
| Builder serialization | `@/features/contracts/builder/serialization` | `buildIntentBody`, `parseAdvancedToGuided`, `validateGuidedState` — the pure constraint-preservation seam the tests pin byte-equality on |
| Test fixtures | `web/tests/fixtures.ts` | every shape transcribed VERBATIM from captured runtime responses |
| Test harness | `web/tests/harness.tsx` | `routeFetch` / `envelope` / `renderWithSession` — the real `SessionProvider` with the real connect() flow over a stubbed fetch boundary |

### Two browser-reality findings (foundation; disclosed, worked around within Worker 2's surface)

1. **`AdcosClient`'s detached fetch reference throws in every real
   browser.** `this.doFetch(...)` (a prototype getter returning
   `globalThis.fetch`) invokes the native fetch with `this` = the client
   instance → `TypeError: Failed to execute 'fetch' on 'Window': Illegal
   invocation` → every call surfaces as `backend-unreachable`. Tests never
   caught it (they inject `fetchImpl`). Workaround on this branch:
   `src/features/eligibility/fetch-binding-shim.ts` (idempotent, documented,
   DELETE when the client binds its fetch).
2. **The list discipline (pagination/filters in the GET request's JSON
   body) is unsendable from browsers** — fetch/XHR forbid GET bodies. The
   console performs the BODYLESS list read (the backend's default page,
   20 items) and narrows client-side; when `has_more` is true the surface
   shows the honest deeper-pagination notice with the canonical API form.
   A query-string or POST list form is a Tech-Lead gap-closure candidate.

## Non-negotiables enforced here

1. No alternate authority: React state holds presentation only; refresh
   re-fetches truth from the backend.
2. Credentials in memory only — never localStorage/sessionStorage/cookies.
3. Backend reason codes displayed verbatim (`ErrorState`).
4. SOFTWARE evidence visibly distinct from physical/network evidence
   (`EvidenceBadge`).
5. No fake production data — empty states when the backend is empty.
6. Same-origin API calls only; dev via the Next rewrite proxy.

## Worker 3 (console-developers) — Part C: evidence, assurance, settings, error workbench

Completed at the integration station (Worker 3's session was rate-limited
mid-delivery; Part C surfaces were delivered by the station subagent).
Files: `src/app/{evidence,assurance,settings}/page.tsx`,
`src/app/settings/errors/page.tsx` (the FROZEN workbench path), and the
features under `src/features/{evidence,assurance,settings,errors}`.

### /evidence — the evidence explorer

Evidence is a first-class resource: source, timestamp, evidence class,
provenance, related objects. The backend's only evidence surface today is
the deterministic fulfillment demonstration (`GET|POST
/demo/contract-fulfillment`), so the explorer lists the evidence of EVERY
demonstration run this console session made (`features/evidence/demo-runs`
— in-memory, newest first), including the run the page itself records on
load (the current document, via `recordDemoRun`). Each record renders its
members VERBATIM (type, record_id, subject_ref, contract_ref → the
contract page, producer, instant, metric/value, confidence bps,
freshness/valid-until, source_refs); a detail drawer carries the full
record, the provenance (producer, source_refs, the run's boundary entry),
the related contract (live read when connected) and the JSON view. The
badge legend states the vocabulary explicitly: `SOFTWARE` and
`sandbox-simulation` verbatim through `EvidenceBadge`; the physical/network
family renders as **NOT-ACHIEVABLE-BY-THIS-DEPLOYMENT** — no UI state can
transform a SOFTWARE record into a physical PASS.

### /assurance — the assurance view

Per contract (list contracts, then read `GET
/api/2.0/contracts/{id}/assurance` per contract): the OBLIGATION
REFERENCES VERBATIM — opaque typed refs with their provenance (the
objectives the backend actually returns), the contract state, the honest
notes, and each obligation linked to its contract and its evidence chain
(the demonstration runs' attestation records by contract_ref). NO
invented metric dashboards: semantics are referenced, never evaluated
here. The contracts list is the bodyless browser form of the GET-body
list discipline (fetch forbids GET bodies); deeper pagination is
disclosed with the canonical curl form.

### /settings — the settings page

- **Environment & health**: the full `/readyz` document (mode,
  environment, every backend state + detail, delegated backends) plus
  `/healthz`, with the honest semantics stated: liveness says NOTHING
  about backends; readiness names them. Both are unauthenticated platform
  reads through the typed client.
- **Session**: the connected application summary (including its
  `evidence_class`, verbatim) + Disconnect, and the credential policy:
  memory only, cleared on reload by design, never echoed in full.
- **About**: the console's boundary statement — no second authority; the
  canonical backend owns all state.
- Links to the error workbench.

### /settings/errors — the error workbench

The session's captured errors (from `useRequestLog` + `isFailedRequest`
— the in-memory request log, display data only) with the full anatomy:
what happened (message), why (reason VERBATIM), the affected resource
(resource_id / request path), next action (a Retry button that re-issues
through the typed client via the coverage-registry executor when the
backend marked the error retryable — or when the request never reached
the runtime; guidance per reason code from the KNOWN dictionary with an
honest generic fallback for unknown codes), and the reproducible API
form (curl, copyable, credential ALWAYS masked). Deep-links one captured
request via `?request=<sequence>` (`workbenchHref`); a stale sequence
renders an honest note (the log is in-memory). Honest empty state: "no
captured errors — every request succeeded".

### Part C test suites (deterministic, no network)

`tests/evidence.test.tsx`, `tests/assurance.test.tsx`,
`tests/settings.test.tsx`, `tests/error-workbench.test.tsx` — each
self-contained (a local fetch-boundary router over REAL captured shapes,
rendered inside the real SessionProvider through the real `connect()`
flow): evidence records render with the badge vocabulary verbatim
(SOFTWARE never physical), the assurance obligations render verbatim
with the honest empty evidence chain, the settings readiness/liveness
documents render with the semantics note, and the workbench renders the
full anatomy + known-code guidance + retry + deep-link preselection.

## Worker 3 (console-developers) — Part B: the developers tooling (API Explorer, Request Inspector, search)

Completed at the integration station (Worker 3's session was rate-limited
mid-delivery; Part B surfaces were delivered by the station subagent).
Files: `src/app/developers/explorer/page.tsx`,
`src/app/developers/requests/page.tsx`, and the features under
`src/features/{api-explorer,requests}` plus the real providers in
`src/features/search/providers.tsx`. The Part A core
(`/developers` itself — identity, capabilities, credentials, webhook
endpoints) is documented in the station A delivery and renders the same
workspace composition.

### /developers/explorer — the API Explorer

Built ENTIRELY from the coverage registry (`@/lib/api/coverage` — the
boundary's own frozen surface; 25 rows: 21 developer + 4 platform, zero
invented): a grouped, searchable operation browser (method chip, path,
mutation/destructive badges, required capability — grouped by area), and
an operation detail with the boundary headers (the session's ACTUAL
application id when connected; the credential ALWAYS masked via
`maskedRequestHeaders`), path parameters for templated routes, the JSON
body editor seeded from the registry's own `example` (locally validated —
a local problem is reported as LOCAL, never fabricated as a backend
reason), and the idempotency-key field for mutations.

- Executions are REAL requests through the typed client
  (`features/api-explorer/executor.ts` — `executeOperation`); the
  response pane renders the status chip, the recorder-captured response
  headers (X-ADCOS-*, rate-limit), the parsed body, the envelope surface
  (request id, api version, environment, rate limit, idempotent-replay
  marker), reason codes VERBATIM with retryable/retry_after on errors,
  and the copyable curl reproduction (credential masked as
  `<your-credential>`).
- Destructive operations (`DESTRUCTIVE_OPERATIONS` — termination, lease
  revocation) require an explicit confirmation step before any request
  fires; cancelling disarms without a request.
- The GET-body list discipline: pagination/filters ride the developer
  API list reads' GET JSON body — unsendable from a browser (fetch
  forbids GET bodies) — so executing a list read performs the bodyless
  default-page read and the canonical curl form is reproduced for
  out-of-browser use.
- Execution history: the replayable in-memory list of this session's
  request/response pairs (mutations replay with the SAME idempotency key
  — byte-identical replay semantics).
- Honest search: an unknown path/method query (or `?operation=` deep
  link) renders "is not a supported operation" — never a guess; a
  concrete known path resolves through the registry and prefills its
  path parameters. Deep link: `/developers/explorer?operation=<id>`
  (+ any path-parameter names as query params prefill them).

### /developers/requests — the Request Inspector

The global request log surface: a table of the requests this console
session made through the typed client (time, method, path, status,
request id, duration) with free-text search and a failures-only toggle
(`isFailedRequest`), and a per-request detail drawer: the request
headers reconstructed from the matched registry operation + session
(credential ALWAYS masked, the idempotency key shown as a placeholder —
never recorded), the request body, the recorder-captured response
headers/body (truncated with an explicit expand — nothing fabricated;
entries recorded before any inspector-capable page mounted honestly
render without the captured fields), the copyable curl reproduction, and
the registry operation that produced the request, linked into the API
Explorer.

- Object-linking affordance: `requestsHref(sequence)` (and the
  `RequestsLink` component, `@/features/requests`) deep-links to
  `/developers/requests?request=<sequence>` with the entry preselected —
  other object pages adopt this to link "the request that produced this
  object".
- `clearRequests` requires an explicit confirmation (arm → confirm /
  cancel); the log is in-memory only — a reload clears it by design.

### The real search providers (`features/search/providers.tsx`)

`ConsoleSearchProviders` (mounted on the developers-surface pages)
registers commands into the palette infrastructure on mount and
unregisters every one on unmount:

- CONTRACTS from the fetched list (connected + `intents:read`): the full
  id, the state and the principal all match; rows navigate to the
  contract detail.
- WEBHOOK ENDPOINTS from the fetched list (connected + `webhooks:read`):
  rows navigate into the API Explorer with `endpoint_get` preselected and
  the endpoint id prefilled.
- EVIDENCE RECORDS from this session's demonstration runs (`useDemoRuns`):
  rows navigate to the Evidence surface.
- API EXPLORER OPERATIONS from the coverage registry: read commands
  always navigate to `/developers/explorer?operation=<operation>`;
  MUTATION commands appear ONLY when a session is connected AND the
  required capability is granted (`capabilityGranted` — the
  application's capability list is the gate); DESTRUCTIVE operations
  (termination, lease revocation) require an explicit confirmation step
  before even NAVIGATING (the explorer re-confirms before executing; the
  backend's own authorization is never bypassed).
- No provider ever fabricates objects: a failed or ungranted fetch
  registers nothing (honest absence).

### Part B test suites (deterministic, no network)

`tests/api-explorer.test.tsx`, `tests/requests-inspector.test.tsx`,
`tests/search-providers.test.tsx` — each self-contained (a fetch-boundary
router over REAL captured shapes with REAL `Response` objects so the
recorder captures headers/bodies exactly as in a browser, rendered inside
the real SessionProvider through the real `connect()` flow): the registry
drives the operation list (25 rows, zero invented — counted), an execute
flow asserting the exact boundary headers/body on the wire, the error
path showing the reason verbatim with retryable/retry_after, the
destructive confirmation gating (no request until confirmed), the
replayable history (same idempotency key), the bodyless GET list
discipline, the inspector recording + masked curl + deep-link
preselection + pre-recorder honesty, and the permission-aware provider
registration (mutation commands absent when disconnected or ungranted).
