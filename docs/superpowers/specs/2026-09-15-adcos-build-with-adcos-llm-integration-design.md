# ADCOS — Build with ADCOS & LLM Integration Experience

**Status:** APPROVED / FROZEN FOR IMPLEMENTATION  
**Date:** 2026-09-15  
**Scope:** Extension of Console V2 learning product

## 1. Purpose

ADCOS must be understandable and integrable by both human developers and coding/architect LLMs without requiring access to internal architecture documents or conversation history.

The console therefore gains a first-class **Build with ADCOS** experience plus a canonical **LLM Integration Pack**. Both are generated from the same capability, operation and education metadata used by the developer console.

The experience must answer one architectural question completely:

> **I am building a product that needs connectivity. Exactly how should ADCOS fit into my architecture?**

## 2. Relationship to Console V2

This work extends the frozen Console V2 product model:

`Understand → Build → Integrate → Operate → Diagnose`

Build with ADCOS becomes the principal integration-design surface inside **Build** and **Integrate**. It does not replace the V1 expert workbench, Quickstart, Docs, Playbooks or API Explorer.

## 3. Non-negotiable architecture rules

1. `ConnectivityContract` remains the sole durable ADCOS contract authority.
2. A consuming application is not allowed to create a second connectivity-contract authority.
3. ADCOS sells/allocates connectivity outcomes, not provider-specific access technology.
4. Provider-native topology, routing and subscriber authority remain with providers.
5. Browser examples call the canonical HTTP developer boundary only.
6. Provider SDKs and provider-native network objects must never appear in application-facing integration examples.
7. ADCOS API success is never represented as proof of physical connectivity success.
8. Software/deployment evidence must remain distinct from physical/network validation.
9. Webhooks are observations; they do not become a second source of canonical business state.
10. A ShareNet-style offline application must remain able to operate its local/P2P data plane when ADCOS is unreachable.
11. Examples must correspond to real accepted operations or be explicitly labeled conceptual.
12. No new backend/domain authority is introduced by the documentation or learning layer.

## 4. Canonical integration model

```text
Application / Platform
        |
        | technology-neutral connectivity requirement
        v
Connectivity Intent
        |
        v
ADCOS Eligibility / Policy
        |
        v
Provider Offers
        |
        v
ConnectivityContract
        |
        v
Execution Plan
        |
        v
Provider realization
        |
        v
Evidence + Assurance
        |
        v
Application operational view
```

Applications own their product domain, device context, content, user experience, application economics and local operational decisions. ADCOS owns the connectivity contract lifecycle and the exchange/orchestration of connectivity outcomes. Providers own provider-native realization and topology.

## 5. Integration patterns

The first release documents these patterns:

### A. Application consumes connectivity

For an application that requires connectivity for itself, a service, or an endpoint cohort.

### B. Gateway / relay platform

For a system such as ShareNet that needs backhaul/connectivity to gateway or relay infrastructure while keeping its own device-to-device distribution plane authoritative.

### C. Fleet / subscriber connectivity

For an application that purchases or allocates connectivity for a defined device or subscriber cohort.

### D. Provider / adapter integration

For a provider or network operator exposing capabilities into ADCOS without exporting provider-native topology into the application layer.

### E. Connectivity marketplace / orchestration product

For higher-level products that need multiple connectivity options while allowing ADCOS to remain the connectivity exchange authority.

Every pattern page answers:

- What the application owns
- What ADCOS owns
- What providers own
- What crosses the boundary
- Which operations are required
- Which webhooks are useful
- What evidence is available
- What happens during degradation/failover
- What must not be implemented in the application

## 6. Build with ADCOS UI

Add a first-class console route:

`/build`

The route has these sections:

1. **Choose your architecture** — pattern cards above.
2. **Design the boundary** — interactive ownership map.
3. **Choose capabilities** — select outcomes needed by the product.
4. **See the lifecycle** — Intent → Eligibility → Offer → Contract → Execution → Assurance.
5. **Get the integration plan** — ordered API operations, webhooks and required application objects.
6. **See implementation examples** — conceptual plus real API examples where supported.
7. **Review anti-patterns** — explicit things the consuming application must not build.
8. **Production checklist** — authentication, versioning, idempotency, error handling, evidence and degradation behavior.
9. **Export for an LLM** — links to machine-readable and human-readable context assets.

The primary CTA on each pattern is **Design this integration** and produces an on-screen integration blueprint. It must not fabricate credentials or claim that deployment configuration has been completed.

## 7. Integration blueprint

The blueprint is presentation state, not a new domain authority.

It contains:

```text
pattern_id
selected_capability_ids
required_operation_ids
recommended_webhook_event_ids
application_owned_objects
adcos_owned_objects
provider_owned_objects
boundary_rules
failure_modes
next_steps
```

Every identifier resolves into the canonical operation/education registry.

## 8. Human documentation

Extend `/docs` with a Build section:

```text
Docs
├── Start here
├── Concepts
├── Guides
├── Build with ADCOS
│   ├── Choose an integration pattern
│   ├── Application integration
│   ├── Gateway / relay integration
│   ├── Fleet / subscriber integration
│   ├── Provider integration
│   ├── Lifecycle implementation
│   └── Production checklist
├── API
├── SDKs
├── Errors
├── Troubleshooting
└── Reference
```

Human docs remain concise by default and progressively disclose implementation details.

## 9. LLM Integration Pack

Publish these stable public assets from the deployed site:

- `/llms.txt` — concise machine-oriented overview and links
- `/llms-full.txt` — complete architectural/integration context
- `/adcos-integration-context.json` — machine-readable canonical context
- `/adcos-capabilities.json` — capability registry projection
- `/adcos-operations.json` — operation registry projection with educational metadata

The JSON assets are generated from the same frontend registries used by the UI and must not duplicate backend semantics manually.

## 10. LLM context model

The machine-readable context must contain these top-level sections:

```text
mission
mental_model
architecture
authority_boundaries
integration_patterns
capabilities
operations
workflow_sequences
webhooks
errors
versioning
security_rules
evidence_rules
anti_patterns
production_checklist
```

Each operation entry includes at minimum:

```text
operation_id
method
path
purpose
prerequisites
lifecycle_position
capability_ids
concept_ids
example_request
example_response
error_reason_codes
next_operation_ids
```

Examples must come from current operation metadata wherever possible. Unsupported executable operations must never be invented.

## 11. LLM safety / anti-drift rules

The LLM pack must explicitly state:

- do not create a second contract authority;
- do not encode provider-specific topology into application domain logic;
- do not treat webhook observations as canonical state;
- do not equate API success with physical connectivity success;
- do not invent unavailable endpoints;
- do not invent provider capabilities;
- do not make application data-plane availability depend on ADCOS control-plane availability unless the product explicitly chooses that tradeoff;
- preserve canonical reason codes;
- preserve API version and compatibility rules;
- use idempotency and declared request semantics as defined by the API;
- distinguish software evidence from physical/network evidence.

## 12. Registry architecture

The knowledge flow is:

```text
Accepted API coverage
        +
Education registry
        +
Concept registry
        +
Guide registry
        +
Webhook/error metadata
        |
        v
Canonical integration registry
        |
   ┌────┴──────────────┐
   v                   v
Build UI          LLM assets
```

No second endpoint catalog is permitted.

## 13. ShareNet reference integration

The documentation must contain a concrete ShareNet example because ShareNet is an accepted ADCOS vertical proof.

Canonical ShareNet boundary:

```text
ShareNet content/P2P plane
        |
        | technology-neutral gateway/relay connectivity need
        v
ADCOS
        |
        v
provider execution
```

ShareNet remains authoritative for content, P2P distribution, publisher trust, delivery receipts and application economics. ADCOS remains authoritative for connectivity contracts and connectivity fulfillment. A local ShareNet P2P transfer must not be routed through ADCOS merely because ADCOS is used for gateway/backhaul connectivity.

## 14. Acceptance

The feature is accepted only when:

1. A developer can choose an integration pattern and obtain a complete boundary explanation.
2. The console can enumerate the relevant supported capabilities and operations without inventing them.
3. The generated blueprint identifies application/ADCOS/provider ownership explicitly.
4. The human docs and LLM assets agree on operation IDs and rules.
5. `/llms.txt`, `/llms-full.txt`, `/adcos-integration-context.json`, `/adcos-capabilities.json`, and `/adcos-operations.json` are deployed and internally consistent.
6. An LLM given only the LLM pack can produce a compliant architecture for the ShareNet pattern without importing provider-specific APIs or creating a second connectivity authority.
7. Existing Console V2 Docs, Quickstart, Playbooks and API Explorer remain accessible.
8. No fake credentials, fake telemetry, fake provider state or false physical-evidence claims are introduced.
9. Production browser acceptance proves `/build` and the LLM assets are reachable on `adcos.vercel.app`.

## 15. Non-goals

- Replacing the ADCOS backend.
- Creating a new SDK runtime as part of the console.
- Creating a second API specification.
- Generating or storing secrets in public documentation.
- Automatically modifying an application's architecture or codebase.
