"use client";

/**
 * AttentionCard — "what needs attention", from real data only:
 *
 * - contracts the lifecycle itself says are awaiting a decision (INTENT
 *   → awaiting offer selection, OFFER_SELECTED → awaiting activation),
 *   each linked to its detail page where the decision is made;
 * - backends the runtime reports as not ready (state !== "ready") with
 *   the runtime's own detail line.
 *
 * When nothing needs attention the card says so with a calm line —
 * never a fake green metric. While disconnected it says honestly that
 * contract attention states require a connected session (backend
 * readiness is platform data and still shown).
 */

import Link from "next/link";
import type { Contract, Readiness } from "@/lib/api/types";
import { ObjectSection } from "@/features/eligibility";
import { Status } from "@/components/ui";
import { truncateId } from "./format";

/** The honest action phrase per attention state (UI words, not backend vocabulary). */
const ATTENTION_PHRASES: Record<string, string> = {
  INTENT: "awaiting offer selection",
  OFFER_SELECTED: "awaiting activation",
};

export function AttentionCard({
  contracts,
  readiness,
  connected,
  className,
}: {
  contracts: Contract[] | null;
  readiness: Readiness | null;
  connected: boolean;
  className?: string;
}) {
  const attentionContracts = (contracts ?? []).filter((contract) =>
    Boolean(ATTENTION_PHRASES[contract.state]),
  );
  const attentionBackends = readiness
    ? Object.entries(readiness.backends ?? {}).filter(
        ([, backend]) => backend.state !== "ready",
      )
    : [];

  return (
    <ObjectSection
      id="home-attention"
      title="What needs attention"
      description="From real data only: contracts awaiting a decision, and backends the runtime itself reports as not ready."
      className={className}
    >
      <div className="flex flex-col gap-3">
        {attentionContracts.length > 0 ? (
          <ul className="flex flex-col gap-1.5">
            {attentionContracts.map((contract) => (
              <li key={contract.contract_id}>
                <Link
                  href={`/connectivity/contracts/${contract.contract_id}`}
                  className="flex flex-wrap items-baseline gap-x-3 gap-y-1 rounded-md border border-line bg-raised px-3 py-2 transition-colors hover:bg-surface"
                >
                  <span
                    className="font-mono text-xs text-ink"
                    title={contract.contract_id}
                  >
                    {truncateId(contract.contract_id)}
                  </span>
                  <Status value={contract.state} size="sm" />
                  <span className="text-xs text-ink-muted">
                    {ATTENTION_PHRASES[contract.state]}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        ) : null}

        {attentionBackends.length > 0 ? (
          <ul className="flex flex-col gap-1.5">
            {attentionBackends.map(([name, backend]) => (
              <li
                key={name}
                className="flex flex-wrap items-baseline gap-x-3 gap-y-1 rounded-md border border-line bg-raised px-3 py-2"
              >
                <span className="font-mono text-xs text-ink">{name}</span>
                <Status value={backend.state} size="sm" />
                <span className="min-w-0 flex-1 break-all text-xs text-ink-faint">
                  {backend.detail}
                </span>
              </li>
            ))}
          </ul>
        ) : null}

        {!connected ? (
          <p className="text-sm text-ink-faint">
            Attention states for contracts require a connected session —
            backend readiness is platform data and is checked either way.
          </p>
        ) : attentionContracts.length === 0 &&
          attentionBackends.length === 0 ? (
          <p className="text-sm text-ink-muted">Nothing needs attention.</p>
        ) : null}
      </div>
    </ObjectSection>
  );
}
