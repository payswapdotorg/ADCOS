# ADCOS Console V2 — Product, Learning & Documentation Experience

Status: APPROVED / FROZEN FOR IMPLEMENTATION
Date: 2026-09-14

## 1. Purpose

Console V1 established a technically strong browser surface over the accepted ADCOS backend: typed API access, contract workflows, fulfillment, networks, evidence, assurance, developer tooling, request inspection and truthful error handling. V2 does not replace those capabilities. It changes the product experience around them.

V2 makes ADCOS self-teaching. A developer with no prior ADCOS knowledge must be able to understand what ADCOS is, understand its core mental model, complete a real guided workflow, learn the relevant API concepts, inspect the resulting objects, and know where to go next without consulting repository-internal architecture documents.

The target quality bar is: Stripe-level developer-product clarity and Apple-level product education, expressed through ADCOS's own visual identity and architecture—not a visual copy of either company.

## 2. Product principle

**Teach the mental model before exposing the machinery.**

The console must progressively move a developer through:

`Understand → Build → Integrate → Operate → Diagnose`

Expert users retain direct access to the V1 workbench. New users receive goal-oriented guidance, contextual definitions, interactive demonstrations, learning paths and documentation.

## 3. V2 non-negotiables

1. `ConnectivityContract` remains the sole durable contract authority.
2. V2 creates no second authority for contracts, offers, plans, execution, evidence, assurance, provider state, credentials, policy or eligibility.
3. Browser code calls the canonical HTTP boundary only; it never imports Python/domain internals.
4. Provider-native topology, routing and subscriber authority remain provider-owned; V2 must never imply a universal ADCOS topology graph.
5. Every interactive example and API example must correspond to a real accepted backend operation or be explicitly labeled conceptual.
6. Documentation must distinguish conceptual explanation from current implementation truth.
7. Backend reason codes remain canonical; teaching layers may explain them but must not replace them.
8. Software evidence and physical/network evidence remain visibly distinct.
9. Hard contract constraints cannot be silently weakened by forms, examples or learning flows.
10. Secrets follow backend issuance/reveal rules and are never persisted in browser storage.
11. No fake provider, network, fulfillment, assurance, performance or production telemetry data.
12. V2 must preserve all working V1 developer capabilities while adding the learning layer.
13. A first-time developer must have an obvious next action on every onboarding/learning screen.
14. Documentation, UI terminology and API examples must share a canonical concept/operation vocabulary so drift is detectable.

## 4. Information architecture

Primary experience groups:

### Understand
- What is ADCOS?
- How ADCOS works
- 5-minute product tour
- Core concepts
- Terminology

### Build
- Create first connectivity contract
- Test a requirement
- Run fulfillment
- Inspect the contract lifecycle

### Integrate
- Quickstart
- Authentication/application connection
- API concepts
- API Explorer
- SDK examples
- Webhooks
- API reference

### Operate
- Contracts
- Networks
- Fulfillment
- Evidence
- Assurance

### Diagnose
- Requests
- Errors
- Replanning
- Troubleshooting

Expert navigation must remain available without forcing an onboarding path after completion.

## 5. First-run experience

A new developer lands on a product-oriented entry state, not an operations dashboard. The first screen explains:

**What ADCOS does**

ADCOS lets an application describe the connectivity it needs as a durable contract and continuously works to fulfill that contract across available connectivity capabilities.

Then the interface presents the mental model:

`Describe requirement → Eligibility → Plan → Fulfillment → Assurance → Continuous fulfillment`

Each stage is clickable and opens a short explanation containing:
- what the stage means;
- why it exists;
- what ADCOS actually does;
- the relevant object;
- the relevant API operation(s);
- a Try it / See example action when supported.

## 6. Quickstart journey

The canonical beginner journey is a real, guided workflow. It must be completable without prior architecture knowledge.

Steps:

1. Connect an application or enter the supported demo context.
2. Describe a connectivity requirement in human terms.
3. Review the resulting canonical contract representation.
4. Explain eligibility and provider/policy reasoning.
5. Show the generated fulfillment plan.
6. Run or observe fulfillment where the accepted backend permits it.
7. Inspect evidence and assurance.
8. Reproduce an operation through the API Explorer.
9. Finish with clear next paths: build with the API, operate contracts, read concepts, or diagnose.

The journey must never fabricate a production capability. If the current deployment only supports a deterministic demonstration, the UI must say so.

## 7. Interactive product tour

The existing deterministic fulfillment demonstration becomes a teaching surface rather than a passive dashboard card.

The tour presents a realistic requirement, then reveals the system step by step:

`Requirement → Eligibility → Plan → Execution → Evidence → Assurance`

At every step the user can open:
- Explain this;
- View object;
- View API request;
- View API response;
- Continue.

The tour must use the same typed client and canonical backend output used elsewhere in the console.

## 8. Learning system

Create a reusable learning model with:

- concept definition;
- why-it-matters explanation;
- prerequisite concepts;
- related backend objects;
- related API operations;
- runnable example where supported;
- related guide/playbook;
- troubleshooting links.

Core first-class concepts:
- Connectivity contract
- Provider capability
- Offer
- Eligibility
- Policy
- Execution plan
- Fulfillment
- Assurance
- Evidence
- Replan/failover
- Provider/adapter boundary
- Application and capability
- Webhook

Definitions must remain concise by default and progressively disclose technical detail.

## 9. Documentation system

Introduce user-facing documentation distinct from internal architecture/evidence records.

Documentation IA:

```text
Docs
├── Start here
│   ├── What is ADCOS?
│   ├── 5-minute quickstart
│   ├── How ADCOS works
│   └── First connectivity contract
├── Concepts
├── Guides
├── API
│   ├── Authentication
│   ├── Contracts
│   ├── Offers
│   ├── Plans
│   ├── Fulfillment
│   ├── Evidence
│   ├── Assurance
│   └── Webhooks
├── SDKs
├── Errors
├── Troubleshooting
└── Reference
```

Every concept page must answer:
1. What is it?
2. Why does it matter?
3. When do I use it?
4. What happens in ADCOS?
5. What does the API look like?
6. Where do I go next?

## 10. Contextual education

Any unfamiliar or architecture-heavy term in a user-facing workflow must have an accessible explanation without leaving the current task.

Approved patterns:
- inline “What is this?” affordance;
- expandable explanation;
- documentation drawer;
- open docs in a preserved workflow context.

Do not use giant tooltip walls or force users into documentation for basic comprehension.

## 11. Playbooks

Provide goal-oriented guided paths:

- Build my first connectivity application
- Understand a connectivity contract
- Understand why a provider was selected
- Diagnose a failed fulfillment
- Handle degraded connectivity
- Integrate the ADCOS API
- Build/integrate a provider adapter

Each playbook must be composed from real console operations, documentation, API examples and underlying objects.

## 12. Developer education inside the API Explorer

The V1 API Explorer remains the execution tool. V2 adds educational framing around each operation:

- purpose;
- prerequisites;
- where it fits in the lifecycle;
- typical sequence position;
- field explanations;
- real request/response example;
- curl and language example;
- related concepts;
- related errors;
- next operation.

The Explorer must be generated from the accepted coverage registry; unsupported operations cannot appear as executable controls.

## 13. Goal-oriented entry points

The product should provide prominent “I want to…” paths:

- Get connectivity
- Understand my connectivity
- Connect my application
- Integrate the API
- Monitor fulfillment
- Understand a decision
- Diagnose a failure
- Add or integrate a provider

These are presentation-level entry points into the existing canonical workflows.

## 14. Object education

Object detail pages must teach the object before exposing its complete fields.

For example, a ConnectivityContract detail should begin with:

> A connectivity contract describes the connectivity your application asks ADCOS to continuously fulfill.

Then show:
- what the user requested;
- why it matters;
- lifecycle position;
- what ADCOS is doing;
- evidence and assurance;
- full structured representation;
- API reproduction.

The same model applies to plans, executions, evidence, assurance and provider objects.

## 15. Visual/product language

V2 must retain V1's calm, expert-friendly density but improve hierarchy and emotional clarity.

Requirements:
- strong editorial hierarchy;
- more generous introductory surfaces;
- fewer indiscriminate card grids;
- primary action visibly dominant;
- explanatory content grouped by intent;
- progressive disclosure for deep technical detail;
- lifecycle transitions shown as understandable stories;
- polished empty/onboarding states;
- excellent keyboard and accessibility behavior;
- responsive behavior that preserves information hierarchy;
- no decorative visualization without operational or educational meaning.

The result should feel like a product, not an internal operator console.

## 16. Documentation/data architecture

Create a structured concept registry and operation-education registry in the frontend. Each registry entry must reference stable backend/API identifiers rather than duplicate business semantics.

The registry should provide machine-checkable links:

`concept → object(s) → operation(s) → guide(s) → troubleshooting topic(s)`

A coverage test must fail when a supported canonical operation has no educational description unless explicitly marked `internal-only` or `not-user-actionable`.

## 17. Truth and disclosure

When a capability is not available in the current HTTP deployment, the UI must explain the actual state instead of presenting a dead button or a fabricated result.

Example:

> Replanning events are not currently exposed by this deployment. The backend capability exists in the architecture, but this console cannot inspect live replan events until the HTTP surface exposes them.

This pattern is preferable to fake functionality.

## 18. Acceptance standard

V2 is accepted only when a new developer can:

1. understand ADCOS's purpose without external explanation;
2. describe the core lifecycle in their own words after the quickstart;
3. complete the guided connectivity journey;
4. understand the important objects encountered;
5. find the relevant API operation from the workflow;
6. execute at least one supported API operation and understand the response;
7. locate documentation for every primary console concept;
8. find troubleshooting guidance for canonical errors;
9. move from beginner guidance into the expert V1 workbench without losing context;
10. complete the primary journey without encountering unexplained architecture jargon.

## 19. Non-goals

- Replacing the accepted ADCOS backend architecture.
- Replacing V1 API tooling with chat.
- Creating a fake sandbox that implies production network access.
- Inventing provider topology.
- Adding frontend-only business rules.
- Rewriting internal architecture/evidence documents as end-user documentation.
- Requiring users to read architecture documents before becoming productive.

## 20. V1 preservation rule

All currently accepted V1 capabilities remain regression-protected: contracts, builder, networks, eligibility/policy explanation, fulfillment, evidence, assurance, developer application/capability views, API Explorer, requests, settings, health/readiness, search and error workbench.
