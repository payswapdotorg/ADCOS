"use client";

/**
 * DocsContext — the contextual return path (the frozen V2 design §10
 * pattern "open docs in a preserved workflow context").
 *
 * Every docs page honors the `?from=` search parameter: when a console
 * workflow opened the docs, the page renders a "Return to <path>"
 * affordance at the top linking straight back to that console route,
 * so the workflow context survives the documentation detour. Client
 * component by necessity (search params); the server surfaces embed it
 * through the Suspense-wrapped `DocsContextSlot` so static prerender
 * stays legal.
 *
 * The Console V2 documentation system — the DEC-0128 program, Task 3 of
 * the frozen plan. Pure navigation affordance: no session, no network.
 */

import { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ExternalLinkIcon } from "@/components/ui";

/** Stable test id for the return affordance. */
export const DOCS_RETURN_PATH_TEST_ID = "docs-return-path";

/**
 * A `from` value is linkable when it is an internal console path: it
 * starts with a single `/` and carries no protocol or `//` prefix
 * (the same-origin discipline the console's client itself follows).
 */
export function isLinkableFromPath(value: string | null): value is string {
  if (typeof value !== "string" || value.length === 0) return false;
  if (!value.startsWith("/")) return false;
  if (value.startsWith("//")) return false;
  if (value.includes("://")) return false;
  return true;
}

/**
 * DocsContextBar — the return affordance itself. Renders nothing when
 * no linkable `?from=` value is present (the default, context-free
 * docs visit).
 */
export function DocsContextBar() {
  const searchParams = useSearchParams();
  const from = searchParams.get("from");
  if (!isLinkableFromPath(from)) return null;
  return (
    <div
      data-testid={DOCS_RETURN_PATH_TEST_ID}
      data-from={from}
      className="mb-4 flex items-center gap-1.5"
    >
      <Link
        href={from}
        className="inline-flex items-center gap-1.5 rounded-md border border-line bg-raised px-2.5 py-1 font-mono text-xs text-ink-muted transition-colors hover:border-line-strong hover:text-ink"
      >
        <span aria-hidden="true">←</span>
        Return to {from}
        <ExternalLinkIcon size={10} className="ml-0.5" />
      </Link>
    </div>
  );
}

/**
 * DocsContextSlot — how every docs surface (server or client) embeds
 * the return affordance: a client component wrapped in its own
 * Suspense boundary, so `useSearchParams` stays legal under static
 * prerender and the bar renders nothing when no `?from=` is present.
 */
export function DocsContextSlot() {
  return (
    <Suspense fallback={null}>
      <DocsContextBar />
    </Suspense>
  );
}
