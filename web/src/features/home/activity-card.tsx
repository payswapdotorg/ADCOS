"use client";

/**
 * ActivityCard — "what is changing", from two honest sources only:
 *
 * (a) the latest contracts (the same list the summary reads, in the
 *     backend's own order — no client-side re-dating);
 * (b) this browser session's API activity from the in-memory request
 *     log (method, path, status, request id, reason on failure). The
 *     log is display data only — no response bodies — and the card
 *     says so: a reload clears it.
 *
 * Log entries link to a detail page only when a backend-minted
 * identifier is extractable from the path; otherwise they stay plain
 * text (honest — no invented targets).
 */

import Link from "next/link";
import type { Contract } from "@/lib/api/types";
import { ObjectSection } from "@/features/eligibility";
import { useRequestLog } from "@/features/requests/request-log";
import { Status } from "@/components/ui";
import { cn } from "@/lib/utils";
import { detailHrefForPath, truncateId } from "./format";

const MAX_LOG_ENTRIES = 8;

export function ActivityCard({
  contracts,
  connected,
  className,
}: {
  contracts: Contract[] | null;
  connected: boolean;
  className?: string;
}) {
  const log = useRequestLog();

  return (
    <ObjectSection
      id="home-activity"
      title="What is changing"
      description="The latest contracts as the backend returns them, plus the API activity of this browser session — nothing else is inferred."
      className={className}
    >
      <div className="flex flex-col gap-3">
        <div>
          <p className="text-2xs uppercase tracking-wide text-ink-faint">
            latest contracts
          </p>
          {!connected ? (
            <p className="mt-1.5 text-sm text-ink-faint">
              Latest contracts are not shown while disconnected — the
              contracts list requires a connected session.
            </p>
          ) : !contracts ? (
            <div className="mt-1.5 flex flex-col gap-2" aria-busy="true">
              <div className="h-3 w-2/3 animate-pulse rounded bg-raised" />
              <div className="h-3 w-1/2 animate-pulse rounded bg-raised" />
            </div>
          ) : contracts.length === 0 ? (
            <p className="mt-1.5 text-sm text-ink-faint">
              no contracts yet — nothing to show
            </p>
          ) : (
            <ul className="mt-1.5 flex flex-col divide-y divide-line rounded-md border border-line bg-raised">
              {contracts.slice(0, 5).map((contract) => (
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
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div>
          <p className="text-2xs uppercase tracking-wide text-ink-faint">
            this session&apos;s API activity
          </p>
          {log.length === 0 ? (
            <p className="mt-1.5 text-sm text-ink-faint">
              no requests yet in this session
            </p>
          ) : (
            <ul className="mt-1.5 flex flex-col divide-y divide-line rounded-md border border-line bg-raised px-3">
              {log.slice(0, MAX_LOG_ENTRIES).map((entry) => {
                const href = detailHrefForPath(entry.path);
                return (
                  <li
                    key={entry.sequence}
                    className="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-2"
                  >
                    {href ? (
                      <Link
                        href={href}
                        className="break-all font-mono text-xs text-accent transition-colors hover:text-ink"
                      >
                        {entry.method} {entry.path}
                      </Link>
                    ) : (
                      <span className="break-all font-mono text-xs text-ink">
                        {entry.method} {entry.path}
                      </span>
                    )}
                    <span
                      className={cn(
                        "font-mono text-2xs",
                        entry.status >= 400
                          ? "text-danger"
                          : entry.status === 0
                            ? "text-warning"
                            : "text-ink-faint",
                      )}
                    >
                      {entry.status}
                    </span>
                    {entry.requestId ? (
                      <span
                        className="font-mono text-2xs text-ink-faint"
                        title={entry.requestId}
                      >
                        {truncateId(entry.requestId, 18)}
                      </span>
                    ) : null}
                    {entry.reason ? (
                      <span className="font-mono text-2xs text-warning">
                        {entry.reason}
                      </span>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          )}
          <p className="mt-1.5 text-2xs text-ink-faint">
            the request log is in-memory and session-scoped — a reload clears
            it (no response bodies are kept)
          </p>
        </div>
      </div>
    </ObjectSection>
  );
}
