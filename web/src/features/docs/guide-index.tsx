"use client";

/**
 * GuideIndex — the Guides index, GENERATED from the Task-1 guide
 * registry (`@/lib/education`): every playbook with its title, purpose
 * and step count, linked to its guide page, with the route-local
 * search filtering the index by term (browser-only).
 *
 * The Console V2 documentation system — the DEC-0128 program, Task 3 of
 * the frozen plan. The row set IS the registry — a guide outside the
 * registry can never appear here.
 */

import { useState } from "react";
import Link from "next/link";
import { GUIDES } from "@/lib/education";
import { EmptyState } from "@/components/ui";
import { DocsContextSlot } from "./docs-context";
import { matchesDocsTerm } from "./docs-shared";
import { DocsSearch } from "./docs-search";

/** Stable test ids for the guides index. */
export const GUIDE_INDEX_TEST_IDS = {
  root: "guide-index",
  row: "guide-index-row",
  empty: "guide-index-empty",
} as const;

export function GuideIndex() {
  const [term, setTerm] = useState("");
  const filtered = GUIDES.filter((guide) =>
    matchesDocsTerm(term, [guide.title, guide.id, guide.purpose]),
  );

  return (
    <div data-testid={GUIDE_INDEX_TEST_IDS.root} className="mx-auto w-full max-w-3xl px-gutter py-rhythm">
      <DocsContextSlot />
      <h1 className="text-xl font-semibold text-ink">Guides</h1>
      <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-muted">
        Goal-oriented playbooks composed from real console operations, routes
        and documentation — every step links to the surface it uses.
      </p>
      <div className="mt-5">
        <DocsSearch
          value={term}
          onChange={setTerm}
          placeholder="Filter guides"
          hint={
            term.trim().length > 0
              ? `${filtered.length}/${GUIDES.length}`
              : `${GUIDES.length} guides`
          }
        />
      </div>
      <div className="mt-6 flex flex-col">
        {filtered.length === 0 ? (
          <div data-testid={GUIDE_INDEX_TEST_IDS.empty}>
            <EmptyState
              title="No guide matches"
              description={
                <>
                  No playbook in the registry matches{" "}
                  <span className="font-mono text-ink">{term.trim()}</span>.
                </>
              }
              action={
                <button
                  type="button"
                  onClick={() => setTerm("")}
                  className="rounded border border-line-strong bg-raised px-3 py-1.5 text-sm text-ink transition-colors hover:bg-surface"
                >
                  Clear filter
                </button>
              }
            />
          </div>
        ) : (
          <ul className="flex flex-col divide-y divide-line rounded-md border border-line bg-surface">
            {filtered.map((guide) => (
              <li key={guide.id} data-testid={GUIDE_INDEX_TEST_IDS.row} data-guide={guide.id}>
                <Link
                  href={`/docs/guides/${guide.id}`}
                  className="flex flex-col gap-1 px-4 py-3 transition-colors hover:bg-raised/40"
                >
                  <span className="flex flex-wrap items-baseline gap-2">
                    <span className="text-sm font-medium text-accent">{guide.title}</span>
                    <span className="font-mono text-2xs text-ink-faint">
                      {guide.steps.length} steps
                    </span>
                  </span>
                  <span className="text-sm leading-relaxed text-ink-muted">{guide.purpose}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
