"use client";

/**
 * ConceptIndex — the Concepts index, GENERATED from the Task-1 concept
 * registry (`@/lib/education`): every one of the 14 first-class
 * concepts with its term and summary, linked to its concept page, with
 * the route-local search filtering the index by term (browser-only —
 * no backend search service, per the frozen V2 design §9).
 *
 * The Console V2 documentation system — the DEC-0128 program, Task 3 of
 * the frozen plan. The row set IS the registry: a concept outside the
 * registry can never appear here, and the count derives at render time.
 */

import { useState } from "react";
import Link from "next/link";
import { CONCEPTS } from "@/lib/education";
import { EmptyState } from "@/components/ui";
import { DocsContextSlot } from "./docs-context";
import { matchesDocsTerm } from "./docs-shared";
import { DocsSearch } from "./docs-search";

/** Stable test ids for the concepts index. */
export const CONCEPT_INDEX_TEST_IDS = {
  root: "concept-index",
  row: "concept-index-row",
  empty: "concept-index-empty",
} as const;

export function ConceptIndex() {
  const [term, setTerm] = useState("");
  const filtered = CONCEPTS.filter((concept) =>
    matchesDocsTerm(term, [concept.term, concept.id, concept.summary]),
  );

  return (
    <div data-testid={CONCEPT_INDEX_TEST_IDS.root} className="mx-auto w-full max-w-3xl px-gutter py-rhythm">
      <DocsContextSlot />
      <h1 className="text-xl font-semibold text-ink">Concepts</h1>
      <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-muted">
        Every first-class concept of the console, each documented with the same
        six questions: what it is, why it matters, when to use it, what happens
        in ADCOS, what the API looks like, and where to go next.
      </p>
      <div className="mt-5">
        <DocsSearch
          value={term}
          onChange={setTerm}
          placeholder="Filter concepts"
          hint={
            term.trim().length > 0
              ? `${filtered.length}/${CONCEPTS.length}`
              : `${CONCEPTS.length} concepts`
          }
        />
      </div>
      <div className="mt-6 flex flex-col">
        {filtered.length === 0 ? (
          <div data-testid={CONCEPT_INDEX_TEST_IDS.empty}>
            <EmptyState
              title="No concept matches"
              description={
                <>
                  No concept in the registry matches{" "}
                  <span className="font-mono text-ink">{term.trim()}</span>.
                  Clear the filter to see all {CONCEPTS.length} concepts.
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
            {filtered.map((concept) => (
              <li key={concept.id} data-testid={CONCEPT_INDEX_TEST_IDS.row} data-concept={concept.id}>
                <Link
                  href={`/docs/concepts/${concept.id}`}
                  className="flex flex-col gap-1 px-4 py-3 transition-colors hover:bg-raised/40"
                >
                  <span className="flex flex-wrap items-baseline gap-2">
                    <span className="text-sm font-medium text-accent">{concept.term}</span>
                    <span className="font-mono text-2xs text-ink-faint">{concept.id}</span>
                  </span>
                  <span className="text-sm leading-relaxed text-ink-muted">{concept.summary}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
