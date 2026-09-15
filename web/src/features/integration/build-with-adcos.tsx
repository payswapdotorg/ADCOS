"use client";

/**
 * BuildWithAdcos — the /build experience (the frozen Build-with-ADCOS
 * design §6): the NINE sections that answer "I am building a product
 * that needs connectivity — exactly how should ADCOS fit into my
 * architecture?"
 *
 *   1. Choose your architecture   (the integration registry's pattern cards)
 *   2. Design the boundary        (the application/ADCOS/provider ownership map)
 *   3. Choose capabilities        (registry capabilities, defaulted to the
 *                                  pattern's recommended set)
 *   4. See the lifecycle          (Intent → … → Evidence + Assurance)
 *   5. Get the integration plan   ("Design this integration" → the on-screen
 *                                  blueprint via buildIntegrationBlueprint)
 *   6. See implementation examples (ONE real captured request + ONE
 *                                  explicitly-labeled conceptual example)
 *   7. Review anti-patterns       (what the application must NOT build)
 *   8. Production checklist       (auth / versioning / idempotency / errors /
 *                                  evidence / degradation)
 *   9. Export for an LLM          (the public LLM Integration Pack assets)
 *
 * Honest limits, by construction: every operation reference comes from
 * `@/lib/api/coverage` via the integration registry (`@/lib/integration`)
 * — there is no second endpoint catalog; the blueprint is presentation
 * state only (never persisted, never claimed as deployment
 * configuration); provider SDKs never appear in examples; webhooks stay
 * observations; API success never claims physical connectivity.
 *
 * The `?pattern={id}` deep link (validated against the registry;
 * invalid/missing falls back to the default selection) lets the docs
 * pages and other surfaces link straight into a pre-selected pattern.
 * The search-param read sits behind its own Suspense boundary (the
 * DocsContextSlot discipline) so static prerender of /build stays legal.
 */

import Link from "next/link";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { coverageByOperation, type CoverageRecord } from "@/lib/api/coverage";
import { CONCEPTS } from "@/lib/education/concepts";
import {
  INTEGRATION_CAPABILITIES,
  INTEGRATION_PATTERNS,
  buildIntegrationBlueprint,
  integrationPatternById,
  type IntegrationPatternId,
} from "@/lib/integration";
import { CodeBlock } from "@/components/ui";
import { IntegrationPatternCard } from "./integration-pattern-card";
import { IntegrationBlueprintView } from "./integration-blueprint";

/** Stable test ids for the /build experience. */
export const BUILD_TEST_IDS = {
  root: "build-with-adcos",
  patternCard: "build-pattern-card",
  capabilityToggle: "build-capability-toggle",
  checklistItem: "build-checklist-item",
  planGuidance: "build-plan-guidance",
} as const;

/** The default selection (an invalid/missing ?pattern= falls back here). */
const DEFAULT_PATTERN_ID: IntegrationPatternId = "gateway-relay";

/** The §6.8 production checklist — the same items the docs page teaches. */
const PRODUCTION_CHECKLIST: { title: string; detail: string }[] = [
  {
    title: "Authentication",
    detail:
      "Every call authenticates as your application with credentials issued through the developers workspace; provider credentials never appear in the application.",
  },
  {
    title: "Versioning",
    detail:
      "The API version rides the request path prefix (/api/2.0) — preserve it and honor the API's compatibility rules instead of pinning response shapes.",
  },
  {
    title: "Idempotency",
    detail:
      "Every mutation request carries an idempotency key; retries reuse the same key rather than creating duplicate records.",
  },
  {
    title: "Error handling",
    detail:
      "Canonical reason codes drive retry and repair decisions — never the HTTP status alone.",
  },
  {
    title: "Evidence",
    detail:
      "Software evidence and physical/network evidence stay distinct; an API success is never represented as proof of physical connectivity.",
  },
  {
    title: "Degradation",
    detail:
      "Contract reads stay canonical, webhook observations are advisory, and the local data plane keeps operating when ADCOS is unreachable — the ShareNet-class tradeoff, chosen explicitly by the product.",
  },
];

function lookupConcept(id: string): string {
  return CONCEPTS.find((concept) => concept.id === id)?.term ?? id;
}

/** Validate a ?pattern= value against the registry (invalid → default). */
function resolvePatternParam(param: string | null): IntegrationPatternId {
  if (!param) return DEFAULT_PATTERN_ID;
  return integrationPatternById(param)?.id ?? DEFAULT_PATTERN_ID;
}

export function BuildWithAdcos() {
  return (
    <Suspense fallback={<BuildLoadingState />}>
      <BuildExperience />
    </Suspense>
  );
}

function BuildLoadingState() {
  return (
    <div data-testid={BUILD_TEST_IDS.root} className="mx-auto w-full max-w-6xl px-4 py-8 lg:px-8">
      <BuildHeader />
      <p className="mt-10 text-sm text-ink-muted">Loading the integration builder…</p>
    </div>
  );
}

function BuildHeader() {
  return (
    <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div className="max-w-3xl">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-accent">
          Build with ADCOS
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
          Put ADCOS in the right place in your architecture.
        </h1>
        <p className="mt-4 text-base leading-7 text-ink-muted sm:text-lg">
          ADCOS is the connectivity exchange and orchestration layer. Your product keeps authority
          over its domain; providers keep authority over their networks. Choose the integration
          pattern that matches your product and ADCOS will show the boundary, lifecycle and API
          surface you actually need.
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <a className="rounded-lg border border-line px-3 py-2 text-sm text-ink hover:bg-raised" href="/llms.txt">
          Open LLM guide
        </a>
        <a className="rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-slate-950 hover:opacity-90" href="/adcos-integration-context.json">
          Machine-readable context
        </a>
      </div>
    </header>
  );
}

function SectionLabel({ children }: { children: string }) {
  return (
    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ink-faint">{children}</p>
  );
}

function BuildExperience() {
  const searchParams = useSearchParams();
  const patternParam = searchParams.get("pattern");

  const [selectedId, setSelectedId] = useState<IntegrationPatternId>(() =>
    resolvePatternParam(patternParam),
  );
  const [designed, setDesigned] = useState(false);

  const pattern = useMemo(
    () => integrationPatternById(selectedId) ?? INTEGRATION_PATTERNS[0],
    [selectedId],
  );

  // capability selection starts from (and follows) the selected pattern's
  // recommended set; the user's toggles then shape the blueprint live
  const [selectedCapabilityIds, setSelectedCapabilityIds] = useState<string[]>(() =>
    pattern.capabilityIds,
  );
  useEffect(() => {
    setSelectedCapabilityIds(pattern.capabilityIds);
  }, [pattern]);

  // a valid ?pattern= deep link selects that pattern, both on mount and
  // when the parameter changes in-app; invalid/missing keeps the selection
  useEffect(() => {
    if (!patternParam) return;
    const found = integrationPatternById(patternParam);
    if (found) setSelectedId(found.id);
  }, [patternParam]);

  const blueprint = useMemo(
    () =>
      designed ? buildIntegrationBlueprint(pattern.id, selectedCapabilityIds) : undefined,
    [designed, pattern.id, selectedCapabilityIds],
  );

  const operations = pattern.operationIds
    .map((id) => coverageByOperation(id))
    .filter((item): item is CoverageRecord => Boolean(item));

  // ONE real example: the canonical intent_create capture, or the
  // pattern's first mutation operation that carries an example body
  const realExample = useMemo(() => {
    const intentCreate = coverageByOperation("intent_create");
    if (intentCreate?.example) return intentCreate;
    return (
      pattern.operationIds
        .map((id) => coverageByOperation(id))
        .filter((item): item is CoverageRecord => Boolean(item))
        .find((item) => item.mutation && item.example) ?? undefined
    );
  }, [pattern.operationIds]);

  function selectPattern(id: IntegrationPatternId): void {
    setSelectedId(id);
  }

  function designPattern(id: IntegrationPatternId): void {
    setSelectedId(id);
    setDesigned(true);
  }

  function toggleCapability(capabilityId: string): void {
    setSelectedCapabilityIds((previous) =>
      previous.includes(capabilityId)
        ? previous.filter((id) => id !== capabilityId)
        : [...previous, capabilityId],
    );
  }

  return (
    <div data-testid={BUILD_TEST_IDS.root} className="mx-auto w-full max-w-6xl px-4 py-8 lg:px-8">
      <BuildHeader />

      {/* §6.1 — Choose your architecture */}
      <section className="mt-10" aria-labelledby="build-choose-architecture">
        <SectionLabel>1 · Choose your architecture</SectionLabel>
        <h2 id="build-choose-architecture" className="mt-2 text-2xl font-semibold text-ink">
          Choose your architecture
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-muted">
          Five integration patterns cover how a product fits ADCOS into its architecture. Select a
          card to explore it here, or read the{" "}
          <Link href="/docs/build" className="text-accent hover:underline">
            Build with ADCOS documentation
          </Link>{" "}
          for the full pattern pages.
        </p>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {INTEGRATION_PATTERNS.map((item) => (
            <IntegrationPatternCard
              key={item.id}
              pattern={item}
              selected={item.id === pattern.id}
              onSelect={selectPattern}
              onDesign={designPattern}
              testId={BUILD_TEST_IDS.patternCard}
            />
          ))}
        </div>
      </section>

      {/* §6.2 — Design the boundary */}
      <section className="mt-10" aria-labelledby="build-design-boundary">
        <SectionLabel>2 · Design the boundary</SectionLabel>
        <h2 id="build-design-boundary" className="mt-2 text-2xl font-semibold text-ink">
          Design the boundary
        </h2>
        <div className="mt-4 rounded-2xl border border-line bg-surface p-6 lg:p-8">
          <div className="border-b border-line pb-6">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ink-faint">
              Selected architecture
            </p>
            <h3 className="mt-2 text-xl font-semibold text-ink">{pattern.title}</h3>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-muted">{pattern.summary}</p>
          </div>
          <div className="mt-6 grid gap-5 lg:grid-cols-3">
            <BoundaryColumn title="Your application owns" items={pattern.applicationOwns} />
            <BoundaryColumn title="ADCOS owns" items={pattern.adcosOwns} accent />
            <BoundaryColumn title="Provider owns" items={pattern.providerOwns} />
          </div>
        </div>
      </section>

      {/* §6.3 — Choose capabilities */}
      <section className="mt-10" aria-labelledby="build-choose-capabilities">
        <SectionLabel>3 · Choose capabilities</SectionLabel>
        <h2 id="build-choose-capabilities" className="mt-2 text-2xl font-semibold text-ink">
          Choose capabilities
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-muted">
          Select the connectivity outcomes your product needs. The list starts from the selected
          pattern&apos;s recommended set, and your changes shape the integration plan below.
        </p>
        <ul className="mt-4 grid gap-3 md:grid-cols-2">
          {INTEGRATION_CAPABILITIES.map((capability) => {
            const active = selectedCapabilityIds.includes(capability.id);
            return (
              <li key={capability.id}>
                <button
                  type="button"
                  data-testid={BUILD_TEST_IDS.capabilityToggle}
                  data-capability={capability.id}
                  onClick={() => toggleCapability(capability.id)}
                  aria-pressed={active}
                  className={`w-full rounded-xl border p-4 text-left transition ${
                    active
                      ? "border-accent/70 bg-raised"
                      : "border-line bg-surface hover:bg-raised/60"
                  }`}
                >
                  <span className="flex items-center gap-2 text-sm font-semibold text-ink">
                    <span
                      aria-hidden="true"
                      className={`inline-flex h-4 w-4 shrink-0 items-center justify-center rounded border text-2xs ${
                        active ? "border-accent bg-accent text-slate-950" : "border-line text-transparent"
                      }`}
                    >
                      ✓
                    </span>
                    {capability.title}
                  </span>
                  <span className="mt-1.5 block text-sm leading-6 text-ink-muted">
                    {capability.description}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </section>

      {/* §6.4 — See the lifecycle */}
      <section className="mt-10" aria-labelledby="build-see-lifecycle">
        <SectionLabel>4 · See the lifecycle</SectionLabel>
        <h2 id="build-see-lifecycle" className="mt-2 text-2xl font-semibold text-ink">
          See the lifecycle
        </h2>
        <div className="mt-4 rounded-2xl border border-line bg-surface p-6 lg:p-8">
          <div className="rounded-xl border border-line bg-base/40 p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ink-faint">
              Canonical lifecycle
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-2 text-sm font-medium text-ink">
              {[
                "Connectivity Intent",
                "Eligibility / Policy",
                "Provider Offers",
                "ConnectivityContract",
                "Execution Plan",
                "Provider realization",
                "Evidence + Assurance",
              ].map((stage, index, all) => (
                <span key={stage} className="contents">
                  <span className="rounded-lg border border-line bg-surface px-3 py-2">{stage}</span>
                  {index < all.length - 1 ? <span className="text-ink-faint">→</span> : null}
                </span>
              ))}
            </div>
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            <div>
              <h3 className="text-sm font-semibold text-ink">Relevant ADCOS operations</h3>
              <div className="mt-3 space-y-2">
                {operations.map((operation) => (
                  <Link
                    key={operation.operation}
                    href={`/docs/api/${operation.operation}`}
                    className="block rounded-lg border border-line bg-base/30 p-3 hover:bg-raised/60"
                  >
                    <span className="font-mono text-xs text-accent">{operation.method} {operation.path}</span>
                    <span className="mt-1 block text-sm text-ink">{operation.description}</span>
                  </Link>
                ))}
              </div>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-ink">Concepts to understand</h3>
              <div className="mt-3 flex flex-wrap gap-2">
                {pattern.conceptIds.map((id) => (
                  <Link
                    key={id}
                    href={`/docs/concepts/${id}`}
                    className="rounded-full border border-line bg-base/30 px-3 py-1.5 text-xs text-ink-muted hover:bg-raised hover:text-ink"
                  >
                    {lookupConcept(id)}
                  </Link>
                ))}
              </div>

              <h3 className="mt-7 text-sm font-semibold text-ink">Failure behavior</h3>
              <p className="mt-2 text-sm leading-6 text-ink-muted">{pattern.failureNote}</p>
            </div>
          </div>
        </div>
      </section>

      {/* §6.5 — Get the integration plan */}
      <section className="mt-10" aria-labelledby="build-integration-plan">
        <SectionLabel>5 · Get the integration plan</SectionLabel>
        <h2 id="build-integration-plan" className="mt-2 text-2xl font-semibold text-ink">
          Get the integration plan
        </h2>
        {designed ? (
          blueprint ? (
            <div className="mt-4">
              <IntegrationBlueprintView blueprint={blueprint} />
            </div>
          ) : (
            <div className="mt-4 rounded-2xl border border-line bg-surface p-6">
              <p className="text-sm leading-6 text-ink-muted">
                The registry could not compose a blueprint for this selection — nothing is invented
                to fill the gap. Adjust the selected capabilities or choose another pattern.
              </p>
            </div>
          )
        ) : (
          <div
            data-testid={BUILD_TEST_IDS.planGuidance}
            className="mt-4 rounded-2xl border border-line bg-surface p-6"
          >
            <p className="text-sm leading-6 text-ink-muted">
              Select{" "}
              <span className="font-semibold text-ink">Design this integration</span> on a pattern
              card above to compose the on-screen integration plan: the ordered operations,
              recommended webhook events, the application/ADCOS/provider ownership split, boundary
              rules, failure modes and next steps for your architecture.
            </p>
          </div>
        )}
      </section>

      {/* §6.6 — See implementation examples */}
      <section className="mt-10" aria-labelledby="build-examples">
        <SectionLabel>6 · See implementation examples</SectionLabel>
        <h2 id="build-examples" className="mt-2 text-2xl font-semibold text-ink">
          See implementation examples
        </h2>
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <div className="rounded-2xl border border-line bg-surface p-6">
            <h3 className="text-sm font-semibold text-ink">
              A real request, from the coverage registry
            </h3>
            {realExample?.example ? (
              <>
                <p className="mt-2 text-xs leading-5 text-ink-muted">
                  {realExample.operation} — a real captured request shape from the coverage
                  registry (the accepted boundary, not an invented endpoint).
                </p>
                <div className="mt-3">
                  <CodeBlock
                    language="json"
                    filename={`${realExample.method} ${realExample.path}`}
                    code={JSON.stringify(realExample.example, null, 2)}
                  />
                </div>
              </>
            ) : (
              <p className="mt-2 text-sm leading-6 text-ink-muted">
                No captured request example exists for this pattern&apos;s operations yet — none is
                invented here.
              </p>
            )}
          </div>
          <div className="rounded-2xl border border-line bg-surface p-6">
            <h3 className="text-sm font-semibold text-ink">
              The conceptual sequence — not an executable API call
            </h3>
            <p className="mt-2 text-sm leading-6 text-ink-muted">
              Conceptual — not an executable API call: your application records a connectivity
              intent describing what it needs; provider offers are accepted onto that intent as
              opaque typed references; activation turns the accepted material into a contract; and
              execution, realization and evidence follow under ADCOS&apos;s orchestration. The
              request shape beside this is the real API surface — this paragraph is the
              architecture story, not an endpoint.
            </p>
            <p className="mt-3 text-xs leading-5 text-ink-muted">
              Provider SDKs and provider-native network objects never appear in application-facing
              integration examples: providers realize connectivity behind their adapters, and the
              application speaks only the canonical HTTP developer boundary.
            </p>
          </div>
        </div>
      </section>

      {/* §6.7 — Review anti-patterns */}
      <section className="mt-10" aria-labelledby="build-anti-patterns">
        <SectionLabel>7 · Review anti-patterns</SectionLabel>
        <h2 id="build-anti-patterns" className="mt-2 text-2xl font-semibold text-ink">
          Review anti-patterns
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-muted">
          Explicit things a consuming application must not build.
        </p>
        <ul className="mt-4 grid gap-2 md:grid-cols-2">
          {pattern.antiPatterns.map((item) => (
            <li key={item} className="rounded-lg border border-line bg-base/30 px-3 py-2 text-sm leading-6 text-ink-muted">
              {item}
            </li>
          ))}
        </ul>
      </section>

      {/* §6.8 — Production checklist */}
      <section className="mt-10" aria-labelledby="build-checklist">
        <SectionLabel>8 · Production checklist</SectionLabel>
        <h2 id="build-checklist" className="mt-2 text-2xl font-semibold text-ink">
          Production checklist
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-muted">
          The honest operating contract before you ship an integration — presented as a checklist
          for planning; nothing here is tracked or persisted.
        </p>
        <ul className="mt-4 grid gap-2 md:grid-cols-2">
          {PRODUCTION_CHECKLIST.map((item) => (
            <li
              key={item.title}
              data-testid={BUILD_TEST_IDS.checklistItem}
              className="flex items-start gap-2.5 rounded-lg border border-line bg-base/30 px-3 py-2"
            >
              <span aria-hidden="true" className="mt-0.5 text-accent">
                ✓
              </span>
              <span className="text-sm leading-6 text-ink-muted">
                <strong className="font-semibold text-ink">{item.title}:</strong> {item.detail}
              </span>
            </li>
          ))}
        </ul>
      </section>

      {/* §6.9 — Export for an LLM */}
      <section className="mt-10" aria-labelledby="build-llm-export">
        <SectionLabel>9 · Export for an LLM</SectionLabel>
        <h2 id="build-llm-export" className="mt-2 text-2xl font-semibold text-ink">
          Export for an LLM
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-muted">
          The same registries that render this page generate the public LLM Integration Pack — a
          coding or architect LLM can build a compliant ADCOS integration from these assets alone.
        </p>
        <div className="mt-4 grid gap-2 md:grid-cols-2">
          <a href="/llms.txt" className="rounded-xl border border-line bg-surface p-4 hover:bg-raised/60">
            <span className="font-mono text-sm text-accent">/llms.txt</span>
            <span className="mt-1 block text-sm leading-6 text-ink-muted">
              The concise machine-oriented overview with links.
            </span>
          </a>
          <a href="/llms-full.txt" className="rounded-xl border border-line bg-surface p-4 hover:bg-raised/60">
            <span className="font-mono text-sm text-accent">/llms-full.txt</span>
            <span className="mt-1 block text-sm leading-6 text-ink-muted">
              The complete architectural and integration context.
            </span>
          </a>
          <a href="/adcos-integration-context.json" className="rounded-xl border border-line bg-surface p-4 hover:bg-raised/60">
            <span className="font-mono text-sm text-accent">/adcos-integration-context.json</span>
            <span className="mt-1 block text-sm leading-6 text-ink-muted">
              The canonical machine-readable context.
            </span>
          </a>
          <a href="/adcos-capabilities.json" className="rounded-xl border border-line bg-surface p-4 hover:bg-raised/60">
            <span className="font-mono text-sm text-accent">/adcos-capabilities.json</span>
            <span className="mt-1 block text-sm leading-6 text-ink-muted">
              The capability registry projection.
            </span>
          </a>
          <a href="/adcos-operations.json" className="rounded-xl border border-line bg-surface p-4 hover:bg-raised/60">
            <span className="font-mono text-sm text-accent">/adcos-operations.json</span>
            <span className="mt-1 block text-sm leading-6 text-ink-muted">
              The operation registry projection with educational metadata.
            </span>
          </a>
        </div>
      </section>

      <section className="mt-10 grid gap-4 md:grid-cols-3">
        <ResourceCard href="/docs" title="Human documentation" copy="Concepts, guides, API reference, errors and troubleshooting in the same vocabulary as this builder." />
        <ResourceCard href="/developers/explorer" title="API Explorer" copy="Execute supported operations, inspect canonical headers and reproduce requests without inventing endpoints." />
        <ResourceCard href="/llms-full.txt" title="LLM Integration Pack" copy="A complete architecture-oriented context package for coding and architect LLMs." />
      </section>
    </div>
  );
}

function BoundaryColumn({ title, items, accent = false }: { title: string; items: string[]; accent?: boolean }) {
  return (
    <div className="rounded-xl border border-line bg-base/30 p-5">
      <h3 className={`text-sm font-semibold ${accent ? "text-accent" : "text-ink"}`}>{title}</h3>
      <ul className="mt-3 space-y-2 text-sm leading-6 text-ink-muted">
        {items.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </div>
  );
}

function ResourceCard({ href, title, copy }: { href: string; title: string; copy: string }) {
  return (
    <Link href={href} className="rounded-xl border border-line bg-surface p-5 hover:bg-raised/60">
      <span className="text-sm font-semibold text-ink">{title}</span>
      <span className="mt-2 block text-sm leading-6 text-ink-muted">{copy}</span>
    </Link>
  );
}
