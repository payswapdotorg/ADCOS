# Build with ADCOS & LLM Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-class `/build` integration-design experience and canonical public LLM Integration Pack while preserving the existing Console V2 workbench.

**Architecture:** Extend the existing Next.js/React Console V2. Add one canonical integration registry that references existing coverage, education, concept, guide, webhook and error metadata; render human-facing Build/Docs surfaces from it; generate public machine-readable assets from it. No new backend authority and no second API catalog.

**Tech Stack:** Existing Next.js, React, TypeScript, Tailwind, Vitest/Testing Library, existing coverage/education registries.

**Spec:** `docs/superpowers/specs/2026-09-15-adcos-build-with-adcos-llm-integration-design.md`

## Global Constraints

- `ConnectivityContract` remains the sole durable ADCOS contract authority.
- Applications request technology-neutral connectivity outcomes.
- Provider-native topology, routing and subscriber authority stay provider-owned.
- Browser examples use the canonical HTTP developer boundary only.
- Examples are real accepted operations or explicitly conceptual.
- Webhooks remain observations, not canonical business state.
- Software and physical/network evidence remain distinct.
- No fake provider state, telemetry, credentials or unsupported API operations.
- ShareNet's local/P2P data plane remains independent of ADCOS control-plane availability.
- The integration registry must reference existing operation/concept identifiers; it cannot create a second endpoint catalog.
- Max Tech Lead fan-out: 3 direct workers × 3 subagents.

## Worker allocation

**W1 — Knowledge model and generated assets**  
Own the integration registry, consistency tests, LLM JSON projections and public text assets.

**W2 — Build experience and documentation**  
Own `/build`, integration blueprint UI, Docs Build section, architecture-pattern pages and contextual links.

**W3 — API/LLM education + release acceptance**  
Own API-learning links, ShareNet reference pattern, production checklist, cross-surface tests and browser acceptance. W3 consumes W1 registry contracts and W2 route contracts; it does not invent a second catalog.

---

### Task 1 — Integration registry

**Files:**
- Create: `web/src/lib/integration/types.ts`
- Create: `web/src/lib/integration/patterns.ts`
- Create: `web/src/lib/integration/capabilities.ts`
- Create: `web/src/lib/integration/workflows.ts`
- Create: `web/src/lib/integration/index.ts`
- Test: `web/src/lib/integration/integration-registry.test.ts`

**Interfaces:**
- Produces `IntegrationPattern`, `IntegrationBlueprint`, `IntegrationCapability`, `IntegrationWorkflow` and registry lookup functions.
- Consumes existing `@/lib/api/coverage`, `@/lib/education`, guide/concept metadata and webhook/error identifiers.

- [ ] Define stable IDs and explicit ownership fields for application, ADCOS and provider domains.
- [ ] Encode five supported patterns: application, gateway/relay, fleet/subscriber, provider/adapter, marketplace/orchestration.
- [ ] Encode lifecycle sequences with existing operation IDs only.
- [ ] Add the ShareNet gateway/relay pattern using its accepted vertical-proof boundary.
- [ ] Test duplicate IDs, dangling operation/concept IDs, unsupported executable references and contradictory ownership.
- [ ] Commit the registry contract.

### Task 2 — Machine-readable LLM assets

**Files:**
- Create: `web/src/lib/integration/llm-pack.ts`
- Create: `web/public/llms.txt`
- Create: `web/public/llms-full.txt`
- Create: `web/public/adcos-integration-context.json`
- Create: `web/public/adcos-capabilities.json`
- Create: `web/public/adcos-operations.json`
- Test: `web/src/lib/integration/llm-pack.test.ts`

**Interfaces:**
- `buildLlmContext()` returns the canonical machine-readable context object.
- `buildLlmOperations()` returns operation metadata projected from the existing coverage/education registries.

- [ ] Generate stable context sections: mission, mental_model, architecture, authority_boundaries, integration_patterns, capabilities, operations, workflow_sequences, webhooks, errors, versioning, security_rules, evidence_rules, anti_patterns, production_checklist.
- [ ] Include ShareNet as the reference integration pattern.
- [ ] Ensure every operation ID maps to the existing API coverage registry and has education metadata or an explicit internal-only/non-user-actionable classification.
- [ ] Generate canonical text assets from the same context builder content; do not maintain conflicting hand-written endpoint lists.
- [ ] Test JSON validity, stable required keys, operation-ID equality with coverage registry and forbidden anti-pattern omission.

### Task 3 — Build with ADCOS experience

**Files:**
- Create: `web/src/features/integration/build-with-adcos.tsx`
- Create: `web/src/features/integration/integration-pattern-card.tsx`
- Create: `web/src/features/integration/integration-blueprint.tsx`
- Create: `web/src/app/build/page.tsx`
- Modify: `web/src/components/shell/app-shell.tsx`
- Modify: `web/src/components/shell/sidebar.tsx`
- Test: `web/src/features/integration/build-with-adcos.test.tsx`

**Interfaces:**
- Consumes integration registry + existing Docs/Explorer links.
- Produces presentation-only `IntegrationBlueprint`; no persistence authority.

- [ ] Add `/build` with a clear statement of where ADCOS fits in an application architecture.
- [ ] Add pattern selection and Design this integration CTA.
- [ ] Render ownership map: application vs ADCOS vs provider.
- [ ] Render lifecycle: Intent → Eligibility → Offer → Contract → Execution → Assurance.
- [ ] Render required API operations, webhooks, failure modes and next steps from registry IDs.
- [ ] Add links to `/docs`, relevant Explorer operation pages and public LLM assets.
- [ ] Add Build with ADCOS to the Learn navigation and command palette without removing existing V1/V2 routes.
- [ ] Test keyboard navigation, mobile/compact layout, route deep linking and pattern selection.

### Task 4 — Build documentation and contextual ShareNet guide

**Files:**
- Create or extend: `web/src/features/docs/build-pages.tsx`
- Modify: `web/src/features/docs/index.ts`
- Modify: `web/src/app/docs/*` only where required by existing routing conventions
- Test: docs tests covering Build section and ShareNet pattern

- [ ] Add Choose an integration pattern, Application integration, Gateway/relay integration, Fleet/subscriber integration, Provider integration, Lifecycle implementation and Production checklist.
- [ ] Add the canonical ShareNet explanation: ShareNet keeps content/P2P authority; ADCOS manages gateway/relay connectivity; provider-native realization remains provider-owned.
- [ ] Explain the exact anti-patterns: second contract authority, provider coupling, webhook-as-authority, API-success-as-physical-success.
- [ ] Link every operation reference to the existing API learning/Explorer surface.
- [ ] Test deep links and contextual return paths.

### Task 5 — Cross-surface API/LLM education

**Files:**
- Modify: existing API-learning operation page/metadata integration points
- Modify: existing coverage/education tests only where needed
- Test: operation education and registry cross-reference tests

- [ ] Add a Build context block to relevant API operation pages showing pattern/lifecycle position and why the operation exists.
- [ ] Add "Used by integration patterns" references sourced from the integration registry.
- [ ] Add download/copy actions for machine-readable LLM context without embedding secrets.
- [ ] Verify unsupported operations cannot become executable through the Build experience.

### Task 6 — Release verification and production handoff

**Files:**
- Add V2 integration tests under existing web test structure.
- Update Tech Lead acceptance handoff.

- [ ] Run `python3 tools/spec_check.py` and `python3 tools/fresh_session_check.py`.
- [ ] Run all backend batteries and all existing frontend tests.
- [ ] Run registry/LLM-pack consistency tests.
- [ ] Browser-test: `/build` → pattern → blueprint → operation → docs → LLM asset.
- [ ] Browser-test ShareNet pattern specifically and verify no provider-native terminology leaks into the application boundary.
- [ ] Verify `/llms.txt`, `/llms-full.txt`, `/adcos-integration-context.json`, `/adcos-capabilities.json`, `/adcos-operations.json` return HTTP 200 and valid content.
- [ ] Verify existing `/docs`, `/quickstart`, `/playbooks`, `/tour`, `/developers` remain reachable.
- [ ] Production browser acceptance proves `adcos.vercel.app/build` and public LLM assets are live before promotion.

## Final acceptance

- [ ] A new developer can choose an integration pattern and understand the boundary completely.
- [ ] A ShareNet architect can derive the correct ADCOS integration without provider-specific APIs.
- [ ] An LLM with only the published context can construct a compliant integration plan.
- [ ] Human docs, Build UI, API Explorer and machine assets agree on stable operation IDs.
- [ ] No second API or contract authority exists.
- [ ] No fake state or physical-evidence claim exists.
- [ ] All pre-existing Console V2 capability remains accessible.
