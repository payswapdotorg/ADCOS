"use client";

/**
 * DocsSearch — the route-local documentation search (the frozen V2
 * design §9: "route-local documentation search; do not add a backend
 * search service"). A controlled input over the V1 FilterBar primitive;
 * every docs index composes it with its own registry-driven filter —
 * the filtering happens in the browser over registry data only, no
 * network, no new API surface.
 *
 * The Console V2 documentation system — the DEC-0128 program, Task 3 of
 * the frozen plan.
 */

import type { ReactNode } from "react";
import { FilterBar } from "@/components/ui";

/** Stable test id for the docs search box. */
export const DOCS_SEARCH_TEST_ID = "docs-search";

export function DocsSearch({
  value,
  onChange,
  placeholder,
  hint,
}: {
  value: string;
  onChange: (value: string) => void;
  /** doubles as the input's accessible name. */
  placeholder: string;
  /** the right-aligned hint (typically the live result count). */
  hint?: ReactNode;
}) {
  return (
    <div data-testid={DOCS_SEARCH_TEST_ID}>
      <FilterBar
        search={{ value, onChange, placeholder }}
        right={
          hint ? (
            <span className="font-mono text-2xs text-ink-faint" data-testid="docs-search-hint">
              {hint}
            </span>
          ) : undefined
        }
      />
    </div>
  );
}
