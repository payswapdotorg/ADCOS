# ADCOS Console V2 — Product & Learning Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ADCOS self-teaching while preserving the V1 expert workbench.

**Architecture:** Keep the existing Next.js/React console and Python HTTP runtime. Add typed education metadata, user-facing docs, guided playbooks, an interactive fulfillment tour, contextual explanations, and API-learning metadata. No new persistence authority or frontend business engine.

**Tech Stack:** Existing Next.js 15, React 19, TypeScript, Tailwind, Vitest, Testing Library.

**Spec:** `docs/superpowers/specs/2026-09-14-adcos-console-v2-learning-experience-design.md`

## Global Constraints

- `ConnectivityContract` remains canonical.
- Browser code calls HTTP APIs only; no Python/domain imports.
- Examples must be real backend operations or explicitly conceptual.
- Canonical reason codes remain verbatim.
- SOFTWARE evidence never becomes physical/network PASS.
- No fake provider/network/production telemetry data.
- Hard constraints cannot be weakened by UI/examples.
- All V1 capabilities remain regression-protected.
- Docs/UI/API vocabulary share stable identifiers.
- Max Tech Lead fan-out: 3 direct workers × 3 subagents.

## Worker allocation

**W1:** education registry, contextual explainers, docs IA/content, cross-links.

**W2:** first-run product surface, mental model, Quickstart, fulfillment tour, visual hierarchy.

**W3:** playbooks, API-learning integration, troubleshooting education, V1→V2 handoff.

W2/W3 consume W1's registry contracts; they do not invent duplicate endpoint/term catalogs.

---

### Task 1 — Education model

**Files:** `web/src/lib/education/{types,concepts,operations,guides,index}.ts` + tests.

**Interface:** `ConceptDefinition`, `OperationLearningDefinition`, `GuideDefinition`, `LearningLink` and typed registries.

- [ ] Define stable IDs, summaries, why/when text, prerequisites, related objects/operations/guides.
- [ ] Populate core concepts: contract, capability, offer, eligibility, policy, plan, fulfillment, assurance, evidence, replan, adapter, application/capability, webhook.
- [ ] Reference existing coverage-registry operation IDs; never define a second endpoint catalog.
- [ ] Add tests for duplicate IDs, unknown links, and missing education for user-actionable operations.
- [ ] Commit.

### Task 2 — Learning primitives

**Files:** `web/src/features/learning/*` + tests.

**Interface:** `ConceptExplainer`, `ConceptLink`, `NextStep`, `ObjectEducation`.

- [ ] Add accessible inline “What is this?” explanations.
- [ ] Add drawer/block modes with focus management.
- [ ] Add “why it matters”, “when to use”, “next step”.
- [ ] Add object-level explanatory headers before raw fields.
- [ ] Test keyboard, focus, screen-reader labels and unknown concept failure.

### Task 3 — Documentation

**Files:** `web/src/features/docs/*`, `web/src/app/docs/*` + tests/content.

**Interface:** docs consume the education/guide registries.

- [ ] Add Start here, Concepts, Guides, API, SDKs, Errors, Troubleshooting, Reference.
- [ ] Write human-facing pages for What is ADCOS?, How ADCOS works, Quickstart, and all core concepts.
- [ ] Every concept page answers what/why/when/ADCOS behavior/API/next step.
- [ ] Add route-local documentation search; do not add a backend search service.
- [ ] Link docs to real console objects and API operations.
- [ ] Test deep links, missing slugs and contextual return paths.

### Task 4 — First-run product experience

**Files:** `web/src/features/home/*`, existing `getting-started-card.tsx`, route tests.

**Interface:** fresh/disconnected state explains ADCOS; returning users retain expert dashboard.

- [ ] Replace the current procedural three-step starter with product education.
- [ ] Explain “one connectivity contract, many networks, continuous fulfillment”.
- [ ] Add clickable lifecycle: Requirement → Eligibility → Plan → Fulfillment → Assurance → Continuous fulfillment.
- [ ] Add “I want to…” goals: get connectivity, understand connectivity, connect app, integrate API, monitor, understand decision, diagnose, integrate provider.
- [ ] Ensure every primary action has an obvious next step.
- [ ] Test fresh, connected-empty, connected-nonempty and degraded states.

### Task 5 — Quickstart + interactive tour

**Files:** `web/src/features/playbooks/quickstart*`, `web/src/features/tour/*`, `web/src/app/quickstart/page.tsx`, demo integration + tests.

**Interface:** guided journey uses the existing typed client and deterministic demo response.

- [ ] Build the nine-step Quickstart: connect/demo context, requirement, contract, eligibility, plan, fulfillment, evidence/assurance, API reproduction, next path.
- [ ] Add progress, back/forward, retry, explain/view object/view API actions.
- [ ] Transform the deterministic fulfillment demo into Requirement → Eligibility → Plan → Execution → Evidence → Assurance.
- [ ] At each step show the real object and API representation.
- [ ] Preserve software-vs-physical evidence honesty.
- [ ] Add determinism and workflow tests.

### Task 6 — Playbooks + API learning

**Files:** `web/src/features/playbooks/*`, `web/src/features/api-learning/*`, existing API Explorer + tests.

**Interface:** playbooks and Explorer reference the same concept/operation registries.

- [ ] Add playbooks: first application, understand contract, understand provider choice, diagnose fulfillment failure, handle degradation, integrate API, integrate provider adapter.
- [ ] Add Explorer purpose, prerequisites, lifecycle position, field explanations, related concepts/errors, next operation.
- [ ] Preserve current execution, headers, curl, canonical reason and destructive confirmation behavior.
- [ ] Add deterministic request-language examples only when derivable from existing operation metadata.
- [ ] Test that unsupported operations cannot be invented/executed.

### Task 7 — Troubleshooting + expert handoff

**Files:** existing error workbench, `web/src/features/docs/troubleshooting*`, shell/search/context links + tests.

- [ ] Map known canonical reason codes to human guidance without replacing the verbatim backend reason.
- [ ] Structure failures as what happened / why / affected resource / next action / API reproduction / learn more.
- [ ] Preserve unknown reason codes without invented semantics.
- [ ] Add “Open in workbench” from learning/docs/playbooks with object/operation context preserved.
- [ ] Keep direct expert routes and command-palette access.

### Task 8 — Release acceptance

**Files:** existing deployment/browser tests + V2 acceptance tests.

- [ ] Run backend spec/fresh-session checks, all V1 batteries and V1 frontend tests.
- [ ] Run education registry consistency/coverage tests.
- [ ] Browser-test: first visit → product explanation → mental model → Quickstart → tour → API Explorer → docs → expert workbench.
- [ ] Browser-test canonical error and degraded/unavailable backend education.
- [ ] Verify keyboard/accessibility and compact-width behavior.
- [ ] Preview deploy, inspect runtime/build logs, run exact browser suite, then promote only when all gates pass.
- [ ] Production acceptance must prove `/` is the V2 learning-first product while `/api/*`, `/healthz`, `/readyz` and V1 routes remain functional.

## Final acceptance

- [ ] New developer understands ADCOS without outside explanation.
- [ ] New developer completes a real guided workflow.
- [ ] Every primary concept has documentation.
- [ ] Every user-actionable API operation has educational metadata.
- [ ] V1 expert capabilities remain accessible.
- [ ] No fake data or semantic fork exists.
- [ ] Software evidence remains distinct from physical validation.
- [ ] Existing backend and frontend gates remain green.
