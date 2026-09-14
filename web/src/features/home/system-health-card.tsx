"use client";

/**
 * SystemHealthCard — the first thing Home answers: is ADCOS healthy?
 *
 * Everything renders from the platform readiness payload (GET /readyz —
 * no session required): mode/environment VERBATIM in mono, an honest
 * state word derived ONLY from the payload (`ok` is a boolean, not
 * backend state vocabulary, so it is never pushed through `Status`),
 * and the per-backend list with the runtime's own state values
 * (`ready`, `unavailable`, …) rendered verbatim through `Status`.
 * When the runtime reports no backends, the card says so in the same
 * honest words the shell uses.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import type { Readiness, ReadinessBackend } from "@/lib/api/types";
import type { AdcosReadState } from "@/features/eligibility";
import { ObjectSection } from "@/features/eligibility";
import { ErrorState, RefreshIcon, Status } from "@/components/ui";
import { cn } from "@/lib/utils";

export function SystemHealthCard({
  read,
  className,
}: {
  read: AdcosReadState<Readiness>;
  className?: string;
}) {
  // when the last check completed (client clock, labeled as such)
  const [checkedAt, setCheckedAt] = useState<string | null>(null);

  useEffect(() => {
    if (read.loaded && !read.loading) {
      setCheckedAt(new Date().toISOString());
    }
  }, [read.loaded, read.loading, read.data, read.error]);

  return (
    <ObjectSection
      id="home-system-health"
      title="System health"
      description={
        <>
          Readiness as reported by the platform (GET{" "}
          <span className="font-mono">/readyz</span>) — mode and environment
          are the runtime&apos;s own words, never a local assumption.
        </>
      }
      actions={
        <button
          type="button"
          onClick={read.refresh}
          disabled={read.loading}
          className="inline-flex h-7 items-center gap-1.5 rounded-md border border-line-strong bg-raised px-2.5 font-mono text-2xs text-ink-muted transition-colors hover:bg-surface hover:text-ink disabled:opacity-60"
        >
          <RefreshIcon size={12} />
          {read.loading ? "checking…" : "Refresh"}
        </button>
      }
      className={className}
    >
      {read.error ? (
        <div className="flex flex-col gap-3">
          <span className="inline-flex items-center gap-2">
            <span
              aria-hidden="true"
              className="h-2 w-2 rounded-full bg-warning"
            />
            <span className="text-sm font-medium text-ink">
              degraded readiness
            </span>
          </span>
          <ErrorState error={read.error} onRetry={read.refresh} compact />
        </div>
      ) : !read.data ? (
        <div className="flex flex-col gap-2" aria-busy="true">
          <div className="h-3 w-1/3 animate-pulse rounded bg-raised" />
          <div className="h-3 w-2/3 animate-pulse rounded bg-raised" />
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <span className="inline-flex items-center gap-2">
              <span
                aria-hidden="true"
                className={cn(
                  "h-2 w-2 rounded-full",
                  read.data.ok ? "bg-positive" : "bg-warning",
                )}
              />
              <span className="text-sm font-medium text-ink">
                {read.data.ok ? "all backends ready" : "degraded readiness"}
              </span>
            </span>
            {checkedAt ? (
              <span className="font-mono text-2xs text-ink-faint">
                checked at {checkedAt} (client clock)
              </span>
            ) : null}
          </div>

          <dl className="grid grid-cols-[minmax(9rem,auto)_1fr] items-baseline gap-x-4 gap-y-1.5">
            <dt className="font-mono text-2xs text-ink-faint">mode</dt>
            <dd className="font-mono text-xs text-ink">{read.data.mode}</dd>
            <dt className="font-mono text-2xs text-ink-faint">environment</dt>
            <dd className="font-mono text-xs text-ink">
              {read.data.environment}
            </dd>
          </dl>

          <BackendsList
            backends={read.data.backends ?? {}}
            mode={read.data.mode}
          />
          {read.data.delegated_backends &&
          Object.keys(read.data.delegated_backends).length > 0 ? (
            <div className="flex flex-col gap-1.5">
              <p className="text-2xs uppercase tracking-wide text-ink-faint">
                delegated backends
              </p>
              <BackendsList
                backends={read.data.delegated_backends}
                mode={read.data.mode}
              />
            </div>
          ) : null}

          <Link
            href="/networks"
            className="text-sm text-accent transition-colors hover:text-ink"
          >
            Provider &amp; adapter inspection (Networks) →
          </Link>
        </div>
      )}
    </ObjectSection>
  );
}

function BackendsList({
  backends,
  mode,
}: {
  backends: Record<string, ReadinessBackend>;
  mode: string;
}) {
  const rows = Object.entries(backends);
  if (rows.length === 0) {
    return (
      <p className="text-sm text-ink-faint">
        {mode === "sandbox"
          ? "no durable backends (sandbox mode)"
          : "no backends reported"}
      </p>
    );
  }
  return (
    <ul className="flex flex-col divide-y divide-line rounded-md border border-line bg-raised">
      {rows.map(([name, backend]) => (
        <li
          key={name}
          className="flex flex-wrap items-baseline gap-x-3 gap-y-1 px-3 py-2"
        >
          <span className="font-mono text-xs text-ink">{name}</span>
          <Status value={backend.state} size="sm" />
          <span className="min-w-0 flex-1 break-all text-xs text-ink-faint">
            {backend.detail}
          </span>
        </li>
      ))}
    </ul>
  );
}
