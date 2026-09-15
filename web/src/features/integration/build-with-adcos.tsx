"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { COVERAGE, coverageByOperation } from "@/lib/api/coverage";
import { CONCEPTS } from "@/lib/education/concepts";
import { INTEGRATION_PATTERNS, type IntegrationPatternId } from "@/lib/integration/patterns";

function lookupConcept(id: string): string {
  return CONCEPTS.find((concept) => concept.id === id)?.term ?? id;
}

export function BuildWithAdcos() {
  const [selectedId, setSelectedId] = useState<IntegrationPatternId>("gateway-relay");
  const pattern = useMemo(
    () => INTEGRATION_PATTERNS.find((item) => item.id === selectedId) ?? INTEGRATION_PATTERNS[0],
    [selectedId],
  );

  const operations = pattern.operationIds
    .map((id) => coverageByOperation(id))
    .filter((item): item is NonNullable<typeof item> => Boolean(item));

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8 lg:px-8">
      <header className="max-w-3xl">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-accent">Build with ADCOS</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
          Put ADCOS in the right place in your architecture.
        </h1>
        <p className="mt-4 text-base leading-7 text-ink-muted sm:text-lg">
          ADCOS is the connectivity exchange and orchestration layer. Your product keeps authority over its domain;
          providers keep authority over their networks. Choose the integration pattern that matches your product and
          ADCOS will show the boundary, lifecycle and API surface you actually need.
        </p>
      </header>

      <section className="mt-10 grid gap-3 md:grid-cols-2 xl:grid-cols-3" aria-label="Integration patterns">
        {INTEGRATION_PATTERNS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setSelectedId(item.id)}
            aria-pressed={item.id === selectedId}
            className={`rounded-xl border p-5 text-left transition ${
              item.id === selectedId
                ? "border-accent/70 bg-raised shadow-[0_0_0_1px_rgba(45,212,191,0.12)]"
                : "border-line bg-surface hover:bg-raised/60"
            }`}
          >
            <span className="text-sm font-semibold text-ink">{item.title}</span>
            <span className="mt-2 block text-sm leading-6 text-ink-muted">{item.summary}</span>
          </button>
        ))}
      </section>

      <section className="mt-8 rounded-2xl border border-line bg-surface p-6 lg:p-8">
        <div className="flex flex-col gap-3 border-b border-line pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ink-faint">Selected architecture</p>
            <h2 className="mt-2 text-2xl font-semibold text-ink">{pattern.title}</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-muted">{pattern.summary}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <a className="rounded-lg border border-line px-3 py-2 text-sm text-ink hover:bg-raised" href="/llms.txt">
              Open LLM guide
            </a>
            <a className="rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-slate-950 hover:opacity-90" href="/adcos-integration-context.json">
              Machine-readable context
            </a>
          </div>
        </div>

        <div className="mt-6 grid gap-5 lg:grid-cols-3">
          <BoundaryColumn title="Your application owns" items={pattern.applicationOwns} />
          <BoundaryColumn title="ADCOS owns" items={pattern.adcosOwns} accent />
          <BoundaryColumn title="Provider owns" items={pattern.providerOwns} />
        </div>

        <div className="mt-8 rounded-xl border border-line bg-base/40 p-5">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ink-faint">Canonical lifecycle</p>
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

        <div className="mt-8 grid gap-6 lg:grid-cols-2">
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

            <h3 className="mt-7 text-sm font-semibold text-ink">Do not build these</h3>
            <ul className="mt-2 space-y-2 text-sm leading-6 text-ink-muted">
              {pattern.antiPatterns.map((item) => (
                <li key={item} className="rounded-lg border border-line bg-base/30 px-3 py-2">{item}</li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <section className="mt-8 grid gap-4 md:grid-cols-3">
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
