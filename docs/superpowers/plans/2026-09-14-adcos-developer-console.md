# ADCOS Developer Console Implementation Plan

> For agentic workers: implement this plan task-by-task. Use the existing ADCOS Tech Lead worker model: at most 3 direct workers, each at most 3 subagents. Workers must read the frozen UX spec before touching frontend code.

**Goal:** Add a production-quality developer console that exposes the accepted ADCOS backend through intuitive workflows, object inspection, operational visibility, API reproduction and developer tooling.

**Architecture:** A dedicated React/TypeScript web application sits beside the existing Python runtime and calls the canonical ADCOS HTTP boundary through a typed client. The browser owns presentation and navigation only; backend authorities remain canonical. Vercel explicitly separates web routes from `/api/...` backend routes.

**Tech Stack:** React/TypeScript; use a mature React framework compatible with the existing Vercel deployment model; typed API client; accessible component system; browser-side query/cache library only where needed; no new persistence authority.

**Spec:** `docs/superpowers/specs/2026-09-14-adcos-developer-console-design.md`

## Global Constraints

- `ConnectivityContract` remains the sole durable contract authority.
- Provider-native topology/routing/subscriber authority remains provider-owned.
- Browser code MUST NOT import Python/domain internals.
- Every meaningful UI mutation MUST map to a supported backend operation.
- Backend reason codes MUST remain visible in developer errors.
- SOFTWARE evidence MUST NOT be presented as physical/network validation.
- No fake production network/provider data.
- No frontend business rules that silently weaken hard contract constraints.
- The web console MUST expose `/api/...` without changing canonical API semantics.
- Maximum Tech Lead fan-out: 3 direct workers; 3 subagents per worker.

## Repository map before implementation

The current backend has a thin Vercel `api/index.py` entrypoint, a runtime ASGI boundary, canonical contract/developer/evidence services, and existing domains for offers/capabilities, eligibility/policy, execution plans, adapters, evidence/assurance, replan and resilience. The current Vercel configuration rewrites the entire site to the API; this plan replaces that topology with explicit web/API routing.

Expected new surface:

- `web/` — console application
- `web/src/app/` or equivalent route tree — pages
- `web/src/components/` — shared UI primitives
- `web/src/lib/api/` — typed backend client and domain queries
- `web/src/lib/objects/` — canonical object views/serializers
- `web/src/lib/design/` — design tokens and component contracts
- frontend tests under the framework's established test location

Backend changes should be limited to missing read/mutation endpoints and stable typed payloads discovered during coverage analysis; do not duplicate domain semantics in the UI.

## Worker dispatch

### Worker 1 — Console foundation + routing

Owns shell, routing, design system, API client, global search/command palette, environment state, object inspector primitives and Vercel topology.

### Worker 2 — Connectivity workflows

Owns Home, Contracts, contract builder/detail, Networks, Fulfillment, plan/eligibility presentation, replanning and activity timeline.

### Worker 3 — Developer + trust tooling

Owns Developers, credentials/capabilities, API Explorer, request inspector, Errors, Evidence, Assurance, health/readiness and backend capability coverage UI.

Workers may proceed in parallel after Worker 1 publishes the API/client contracts. Worker 2 and Worker 3 must use Worker 1's typed client interfaces rather than inventing transport code.

## Task 1: Freeze web application boundary

**Files:**
- Create: `web/` application scaffold and its framework configuration.
- Modify: `vercel.json` routing/build configuration.
- Modify: deployment docs describing web/API routing.
- Test: web route smoke tests and Vercel production route tests.

**Interfaces:**
- Produces: `GET /` console entry; `/connectivity/*`, `/networks/*`, `/fulfillment/*`, `/evidence/*`, `/developers/*`, `/assurance/*`, `/settings/*`; API remains under `/api/*`.

Steps:
- [ ] Add the frontend application using the existing repository's simplest Vercel-compatible React framework; do not add a second backend.
- [ ] Add a root application shell and a deterministic health indicator sourced from `/readyz`.
- [ ] Replace the current catch-all rewrite with explicit frontend/API routing.
- [ ] Add route-level 404 and backend-error boundaries that preserve canonical error information.
- [ ] Add an end-to-end test that loads `/` and verifies the console shell, and an API test that loads `/healthz` and remains on the backend runtime.
- [ ] Verify Vercel builds the web surface and Python API together without changing backend semantics.

## Task 2: Build the ADCOS design system

**Files:**
- Create: `web/src/components/ui/*`.
- Create: `web/src/lib/design/*`.
- Test: component and accessibility tests.

**Interfaces:**
- Produces reusable `Status`, `DataTable`, `ObjectHeader`, `Drawer`, `Timeline`, `JsonViewer`, `CodeBlock`, `EmptyState`, `ErrorState`, `FilterBar`, `CommandPalette`, `ApiRequestPanel` and `EvidenceBadge` components.

Steps:
- [ ] Define typography, spacing, surface, border, focus and status tokens.
- [ ] Implement keyboard-accessible navigation and command palette.
- [ ] Implement status vocabulary using backend state values rather than frontend synonyms.
- [ ] Implement object header, property grid, tabs, drawers and timeline primitives.
- [ ] Implement JSON/API panels with copy actions and syntax-safe rendering.
- [ ] Test keyboard navigation, focus states and responsive layout at desktop and compact widths.

## Task 3: Typed API client and coverage registry

**Files:**
- Create: `web/src/lib/api/client.*`.
- Create: `web/src/lib/api/types.*`.
- Create: `web/src/lib/api/errors.*`.
- Create: `web/src/lib/api/coverage.*`.
- Test: contract tests against the live/local API boundary.

**Interfaces:**
- Produces typed functions for every supported backend operation used by the console and a backend capability registry recording method/path, read/write support, UI location, error vocabulary and API example metadata.

Steps:
- [ ] Inventory actual backend endpoints, schemas and typed errors from source before writing client methods.
- [ ] Implement one transport layer with consistent auth, JSON decoding, status handling and canonical error parsing.
- [ ] Implement domain queries/mutations as thin typed wrappers over the transport.
- [ ] Add coverage metadata for contracts, developer API, fulfillment, evidence, assurance, providers/adapters, eligibility/policy, replan and resilience surfaces actually exposed by the backend.
- [ ] Add tests proving every registered operation is callable through the typed boundary and that backend reason codes survive unchanged.

## Task 4: Home + system health

**Files:**
- Create: `web/src/app/page.*`.
- Create: `web/src/features/home/*`.
- Test: dashboard states against fixture/live API responses.

Steps:
- [ ] Render contract health, active fulfillment, degraded backends/providers and action-required items from real data.
- [ ] Add recent activity with links to underlying objects.
- [ ] Show production/sandbox/environment state from backend readiness rather than local assumptions.
- [ ] Provide meaningful empty states for a new account and degraded states for unavailable optional backends.
- [ ] Test that no card renders fake production values.

## Task 5: Connectivity contracts + builder

**Files:**
- Create: `web/src/features/contracts/*`.
- Create: `web/src/app/connectivity/*`.
- Test: builder validation, contract list/detail, API request reproduction.

Steps:
- [ ] Build searchable/filterable contract index using canonical contract fields.
- [ ] Build contract detail with lifecycle, requirements, eligibility, plan, execution, assurance, evidence, replan and related objects.
- [ ] Build guided contract creation using canonical backend semantics.
- [ ] Add advanced mode that exposes the canonical contract schema and field names.
- [ ] Add pre-submit API request preview and post-submit API reproduction.
- [ ] Test hard constraints cannot be dropped or weakened by form serialization.

## Task 6: Networks + eligibility + policy

**Files:**
- Create: `web/src/features/networks/*`.
- Create: `web/src/features/eligibility/*`.
- Test: provider/network inspection and eligibility explanation states.

Steps:
- [ ] Render provider/adapter identity, capabilities, health/performance facts and provider-owned boundaries.
- [ ] Render why a provider is eligible/ineligible using backend reason data.
- [ ] Surface policy constraints without recreating the policy engine in TypeScript.
- [ ] Link provider objects to contracts, plans, executions and evidence.
- [ ] Test provider-state unknown/degraded cases explicitly.

## Task 7: Fulfillment + execution + replan

**Files:**
- Create: `web/src/features/fulfillment/*`.
- Create: `web/src/features/replan/*`.
- Test: lifecycle timeline, state transitions, replan explanation.

Steps:
- [ ] Build fulfillment detail as Contract -> Plan -> Execution -> Provider -> Evidence -> Assurance.
- [ ] Render actual execution milestones and typed failures.
- [ ] Render replans with violated threshold, observed value, candidate alternatives, eligibility/policy reasoning and evidence.
- [ ] Provide deep links from replan decisions to underlying objects.
- [ ] Verify that the UI never implies a provider handoff occurred silently.

## Task 8: Evidence + assurance

**Files:**
- Create: `web/src/features/evidence/*`.
- Create: `web/src/features/assurance/*`.
- Test: evidence lineage and assurance visualization.

Steps:
- [ ] Implement evidence explorer and evidence detail with provenance and related objects.
- [ ] Implement assurance state for supported contract objectives and observed values.
- [ ] Link threshold breaches to the evidence and resulting action.
- [ ] Distinguish SOFTWARE evidence from physical/network evidence in badges, filters and detail copy.
- [ ] Test that no UI state can transform software evidence into a physical acceptance.

## Task 9: Developer workspace

**Files:**
- Create: `web/src/features/developers/*`.
- Create: `web/src/features/api-explorer/*`.
- Create: `web/src/features/requests/*`.
- Test: API explorer request/response and credential/capability workflows.

Steps:
- [ ] Build application list/detail, credentials state and capability visibility.
- [ ] Implement API Explorer from the coverage registry; unsupported endpoints cannot appear as callable controls.
- [ ] Show method, path, headers, body, response, status, canonical reason code and curl representation.
- [ ] Build request inspector linking object JSON to the API operation.
- [ ] Ensure secret material follows backend issuance/reveal rules and never persists in browser storage.
- [ ] Add useful examples that developers can copy without editing placeholders that the system can already fill.

## Task 10: Search, activity and error workbench

**Files:**
- Create: `web/src/features/search/*`.
- Create: `web/src/features/errors/*`.
- Test: global navigation/search and canonical error display.

Steps:
- [ ] Search resource identifiers across contracts, providers, executions, evidence and developer objects using backend-supported queries.
- [ ] Implement contextual commands with permission-aware action visibility.
- [ ] Implement error pages that show what happened, why, affected object, next action, reason code and API reproduction.
- [ ] Add request/activity linkage where backend request identifiers exist.
- [ ] Test 4xx, 5xx, backend-degraded and validation errors with canonical reason preservation.

## Task 11: Backend gap closure

**Files:**
- Modify: only existing API/runtime/domain files proven necessary by the coverage audit.
- Test: backend contract and regression tests for each added endpoint.

Steps:
- [ ] Compare the frozen coverage registry with actual backend endpoints and accepted domain authorities.
- [ ] Identify capabilities that cannot currently be represented through a stable HTTP contract.
- [ ] Add only the smallest missing read/mutation endpoints required for developer workflows.
- [ ] Keep domain logic in existing authorities; runtime handlers remain translations only.
- [ ] Add deterministic/error-conformance tests for each new route.

## Task 12: Integration + browser acceptance

**Files:**
- Modify: integration/deployment tests and runbook.
- Create: browser acceptance suite.

Steps:
- [ ] Run backend specification/fresh-session checks.
- [ ] Run all existing batteries and frontend tests.
- [ ] Start the full application and execute browser tests for Home, contract creation/inspection, network inspection, fulfillment, evidence, assurance, Developers/API Explorer, global search and error flows.
- [ ] Verify API reproduction from at least one create/read/mutation operation.
- [ ] Verify keyboard-only navigation for the primary workflows.
- [ ] Deploy to a preview, run the browser acceptance suite, inspect runtime logs, then promote only after all gates pass.
- [ ] Verify production `/` is the console, `/api/healthz` is still the backend, and existing software-only deployment acceptance remains green.

## Acceptance checklist

- [ ] Root URL serves a real ADCOS console, not an API 404.
- [ ] All primary navigation areas are functional.
- [ ] Contract lifecycle is fully inspectable.
- [ ] Supported backend mutations are reachable through safe UI workflows.
- [ ] API Explorer covers the same supported operations and generates reproducible requests.
- [ ] Object JSON and relationships are inspectable.
- [ ] Provider/adapter boundaries are represented accurately.
- [ ] Fulfillment and replanning are explainable.
- [ ] Evidence and assurance are first-class and provenance-aware.
- [ ] Developer credentials/capabilities are understandable and safe.
- [ ] Canonical reason codes survive into UI errors.
- [ ] No frontend authority or semantic fork exists.
- [ ] No fake production network data is present.
- [ ] Existing backend tests/governance gates stay green.
- [ ] Browser acceptance passes against deployed preview and production.
