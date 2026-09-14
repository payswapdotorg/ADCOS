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

## Non-negotiables enforced here

1. No alternate authority: React state holds presentation only; refresh
   re-fetches truth from the backend.
2. Credentials in memory only — never localStorage/sessionStorage/cookies.
3. Backend reason codes displayed verbatim (`ErrorState`).
4. SOFTWARE evidence visibly distinct from physical/network evidence
   (`EvidenceBadge`).
5. No fake production data — empty states when the backend is empty.
6. Same-origin API calls only; dev via the Next rewrite proxy.
