"use client";

/**
 * PlaybookContext — the contextual return path, MIRRORED from the docs
 * convention (V2 design §10: "open docs in a preserved workflow
 * context"): when a console workflow or a docs page opened a playbook
 * with `?from=`, the playbook renders a "Return to <path>" affordance
 * linking straight back, so the learner's context survives the playbook
 * detour exactly as it survives a docs detour.
 *
 * The DEC-0128 program, Task 7 of the frozen plan. Client component by
 * necessity (search params); the surfaces embed it through the
 * Suspense-wrapped `PlaybookContextSlot` so static prerender stays legal
 * (the same discipline the docs feature's DocsContextSlot follows).
 * Pure navigation affordance: no session, no network, no new state.
 */

import { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ExternalLinkIcon } from "@/components/ui";
import { isLinkableFromPath } from "@/features/docs/docs-context";

/** Stable test id for the playbook return affordance. */
export const PLAYBOOK_RETURN_PATH_TEST_ID = "playbook-return-path";

function PlaybookContextBar() {
  const searchParams = useSearchParams();
  const from = searchParams.get("from");
  if (!isLinkableFromPath(from)) return null;
  return (
    <div
      data-testid={PLAYBOOK_RETURN_PATH_TEST_ID}
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
 * PlaybookContextSlot — how the playbook surfaces embed the return
 * affordance: a client component wrapped in its own Suspense boundary,
 * rendering nothing when no linkable `?from=` is present.
 */
export function PlaybookContextSlot() {
  return (
    <Suspense fallback={null}>
      <PlaybookContextBar />
    </Suspense>
  );
}
