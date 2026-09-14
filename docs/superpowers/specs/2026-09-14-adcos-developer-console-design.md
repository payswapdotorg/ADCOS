# ADCOS Developer Console — UX Architecture

Status: APPROVED / FROZEN FOR IMPLEMENTATION
Date: 2026-09-14

## Product intent
ADCOS must expose the existing backend as a coherent developer product, not merely as an HTTP runtime. The console is the human-facing control surface for the programmable connectivity exchange. It should feel like a developer workbench: inspect objects, traverse relationships, understand failures, perform supported actions, and reproduce UI actions as API requests.

## Non-negotiables
1. ConnectivityContract remains the canonical durable authority.
2. The console creates no alternate authority for contracts, plans, execution, evidence, assurance, provider state, credentials, policy, or eligibility.
3. Browser code talks to the canonical HTTP boundary; it does not import domain implementation internals.
4. Provider-native topology/routing/subscriber authority remains provider-owned; the UI must never imply ADCOS owns a universal topology graph.
5. Every meaningful UI mutation maps to a backend operation and exposes an API representation.
6. Backend reason codes remain visible and searchable in developer troubleshooting.
7. Software evidence and physical/network evidence remain visibly distinct.
8. Hard contract constraints are never silently weakened in the UI.
9. Secrets obey backend issuance/reveal semantics and are never persisted in browser state.
10. The console is presentation/control, not a second execution engine.

## Information architecture
Primary navigation: Home, Connectivity, Networks, Fulfillment, Evidence, Developers, Assurance, Settings.
Global controls: command/search palette, environment indicator, contextual object search, API/JSON inspector, session menu.

## Home
Answer immediately: what connectivity is managed, whether ADCOS is healthy, what is changing, and what needs attention. Show contract health, active fulfillment, degraded providers/backends, recent activity, and action-required items. Avoid vanity KPIs; every summary is linked to an underlying resource or evidence chain.

## Connectivity
### Contracts
Search/filter by status, geography, capability, provider, assurance state, validity, created/updated. Rows show contract ID, lifecycle state, current fulfillment/provider, assurance state and last activity.

### Contract detail
Expose identity, lifecycle, requirements/constraints, eligibility result, current plan, execution, provider/network relationship, assurance, evidence lineage, replanning history, related developer application, API/JSON inspector, and activity timeline. Present the lifecycle as Requirements -> Eligibility -> Plan -> Execution -> Assurance -> Continuous fulfillment.

### Contract builder
Guided fields first; advanced canonical fields second. Explain constraints inline. Show canonical API field names where useful. Validate using backend semantics. Before submit, provide View API request. The builder must not invent a UI-only contract schema.

## Networks
Expose provider identity, adapter identity/version, supported capabilities, eligibility-relevant facts, observed health/performance where available, current contract use, provider limitations, evidence and activity. Label provider-owned topology data explicitly.

## Fulfillment
Expose the chain Contract -> Plan -> Execution -> Provider -> Evidence -> Assurance. Detail pages answer what ADCOS actually did, with status, timeline, plan, execution milestones, errors, replans and supporting evidence.

## Replan/failover
Make autonomous changes explicit. Show violated requirement or threshold, observed versus required value, detection time, candidates, eligibility/policy reasoning, proposed action/state and supporting evidence. Never present a provider handoff as an unexplained side effect.

## Evidence and Assurance
Evidence is a first-class resource with source, timestamp, evidence class, provenance and related objects. Assurance shows supported contract objectives such as latency, availability, capacity and provider health, linked to underlying evidence and any resulting action. SOFTWARE evidence never becomes a physical PASS.

## Developers
Applications: identity, environment, credential state, capabilities, API version and recent activity.
Credentials: issuance state, masked value/state, one-time reveal where supported, revoke/rotate where supported.
Capabilities: effective grants and clear explanations for missing capability.
API Explorer: supported endpoints only; show method, path, headers, body/schema, response, status, canonical reason code, curl, and language example where available.
Request Inspector: show resource JSON and the API operation that produced or changed it.

## Search and command palette
Search identifiers and meaningful resource fields globally. Commands are contextual and permission-aware. Destructive commands require explicit confirmation and never bypass backend authorization.

## Errors
Every failure answers: what happened, why, affected resource, next action, canonical reason code, and reproducible API form. Never replace domain/backend errors with generic messages.

## Design language
Calm, dense, highly scannable expert UI. Strong typography hierarchy, predictable spacing, keyboard-first navigation, data tables for collections, drawers for secondary inspection, full pages for primary objects/workflows, sticky contextual actions, progressive disclosure, and no decorative chart without an operational interpretation. Desktop developer workflows are the optimization target; accessibility and responsive behavior remain required.

## Technical shape
Create a dedicated web surface using the repository's existing deployment model. Use TypeScript/React, a typed API client, route-level composition, separated data/query hooks, and reusable object inspector, activity, status, evidence, JSON and API-request components. Keep the current Python API runtime. Replace the catch-all web rewrite with explicit web/API routing so / serves the console and /api/... remains the backend.

## Backend coverage requirement
Maintain a capability coverage matrix mapping every accepted backend surface to a UI location, read experience, supported mutation experience, validation/error state, API reproduction path, permission/auth behavior and acceptance test. Backend capabilities unsuitable for human mutation must still be explainable/inspectable when safe.

## Non-goals
No replacement of domain authorities, no frontend semantic fork, no universal topology model, no fake production network data, no unrelated marketing site, no chat-first replacement for resource workflows, no silent provider failover, and no conversion of software validation into physical connectivity claims.

## Acceptance
The console is accepted only when a developer can discover, understand, perform, inspect, debug and reproduce every meaningful backend capability exposed by the accepted implementation while all canonical authorities and architecture locks remain intact.
