"use client";

/**
 * The route-level error boundary (NOT global-error — it renders INSIDE
 * the root layout, so the shell survives). Shows the error through the
 * shared ErrorState presentation (reason codes stay verbatim), a
 * "Try again" affordance wired to Next's reset, and the digest Next
 * attaches for server-side correlation when present.
 */

import { ErrorState } from "@/components/ui";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="mx-auto w-full max-w-workbench px-gutter py-rhythm">
      <h1 className="text-xl font-semibold">This view failed to render</h1>
      <p className="mt-1 text-sm text-ink-muted">
        The console hit an unexpected error while rendering this route.
      </p>

      <div className="mt-4">
        <ErrorState error={error} />
      </div>

      <div className="mt-4 flex items-center gap-3">
        <button
          type="button"
          onClick={reset}
          className="rounded bg-accent px-3 py-1.5 text-sm font-medium text-accent-ink hover:bg-accent-strong"
        >
          Try again
        </button>
        {error.digest ? (
          <p className="font-mono text-2xs text-ink-faint">digest {error.digest}</p>
        ) : null}
      </div>
    </div>
  );
}
