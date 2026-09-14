"use client";

/**
 * ContractsSummaryCard — "what connectivity is managed".
 *
 * Authenticated read (GET /api/2.0/contracts, limit 100) gated on the
 * session: while disconnected the card NEVER fires the read — it shows
 * honest connect guidance instead. Counts are computed from the fetched
 * list (labeled "of N fetched", because that is exactly what was read —
 * no vanity totals), every state row links to the connectivity index,
 * and the latest contracts (backend order) link to their detail pages.
 */

import Link from "next/link";
import type { AdcosEnvelope, Contract, ListResponse } from "@/lib/api/types";
import type { AdcosReadState } from "@/features/eligibility";
import { ObjectSection } from "@/features/eligibility";
import { EmptyState, ErrorState, RefreshIcon, Status } from "@/components/ui";
import { truncateId } from "./format";

export function ContractsSummaryCard({
  read,
  connected,
  className,
}: {
  read: AdcosReadState<AdcosEnvelope<ListResponse<Contract>>>;
  connected: boolean;
  className?: string;
}) {
  const items = read.data?.data?.items ?? null;

  return (
    <ObjectSection
      id="home-contracts"
      title="What connectivity is managed"
      description="The application's connectivity contracts, by lifecycle state — each state and contract links to the resource behind it."
      actions={
        connected ? (
          <button
            type="button"
            onClick={read.refresh}
            disabled={read.loading}
            className="inline-flex h-7 items-center gap-1.5 rounded-md border border-line-strong bg-raised px-2.5 font-mono text-2xs text-ink-muted transition-colors hover:bg-surface hover:text-ink disabled:opacity-60"
          >
            <RefreshIcon size={12} />
            {read.loading ? "fetching…" : "Refresh"}
          </button>
        ) : null
      }
      className={className}
    >
      {!connected ? (
        <EmptyState
          title="Not connected"
          description={
            <>
              Connect an application to see the connectivity it manages. Use{" "}
              <strong>Connect application</strong> in the session menu (top
              right) — the credential lives in memory only, never in browser
              storage.
            </>
          }
        />
      ) : read.error ? (
        <ErrorState error={read.error} onRetry={read.refresh} compact />
      ) : !items ? (
        <div className="flex flex-col gap-2" aria-busy="true">
          <div className="h-3 w-2/3 animate-pulse rounded bg-raised" />
          <div className="h-3 w-1/2 animate-pulse rounded bg-raised" />
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          title="No contracts yet"
          description={
            <>
              Record your first connectivity intent (
              <Link
                href="/connectivity"
                className="text-accent transition-colors hover:text-ink"
              >
                New contract
              </Link>
              ) or run the{" "}
              <a
                href="#home-demo"
                className="text-accent transition-colors hover:text-ink"
              >
                fulfillment demonstration
              </a>{" "}
              below.
            </>
          }
        />
      ) : (
        <div className="flex flex-col gap-3">
          <div>
            <p className="text-2xs uppercase tracking-wide text-ink-faint">
              by state — of {items.length} fetched
            </p>
            <ul className="mt-1.5 flex flex-col gap-1.5">
              {stateCounts(items).map(([state, count]) => (
                <li key={state}>
                  <Link
                    href="/connectivity"
                    className="flex items-center justify-between gap-3 rounded-md border border-line bg-raised px-2.5 py-1.5 transition-colors hover:bg-surface"
                  >
                    <Status value={state} />
                    <span
                      data-testid={`state-count-${state}`}
                      className="font-mono text-xs text-ink-muted"
                    >
                      {count}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <p className="text-2xs uppercase tracking-wide text-ink-faint">
              latest contracts (backend order)
            </p>
            <ul className="mt-1.5 flex flex-col divide-y divide-line rounded-md border border-line bg-raised">
              {items.slice(0, 5).map((contract) => (
                <li key={contract.contract_id}>
                  <Link
                    href={`/connectivity/contracts/${contract.contract_id}`}
                    className="flex flex-wrap items-baseline gap-x-3 gap-y-1 px-3 py-2 transition-colors hover:bg-surface"
                  >
                    <span
                      className="font-mono text-xs text-ink"
                      title={contract.contract_id}
                    >
                      {truncateId(contract.contract_id)}
                    </span>
                    <Status value={contract.state} size="sm" />
                    <span
                      className="font-mono text-2xs text-ink-faint"
                      title={`${contract.validity.not_before} → ${contract.validity.not_after}`}
                    >
                      {contract.validity.not_before.slice(0, 10)} →{" "}
                      {contract.validity.not_after.slice(0, 10)}
                    </span>
                    <span className="font-mono text-2xs text-ink-faint">
                      command_count {contract.command_count}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </ObjectSection>
  );
}

/** Counts by lifecycle state, in order of first appearance (backend order). */
function stateCounts(items: Contract[]): [string, number][] {
  const counts: [string, number][] = [];
  for (const item of items) {
    const existing = counts.find(([state]) => state === item.state);
    if (existing) {
      existing[1] += 1;
    } else {
      counts.push([item.state, 1]);
    }
  }
  return counts;
}
