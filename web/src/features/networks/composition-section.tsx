"use client";

/**
 * CompositionSection — the execution composition facts this deployment
 * ACTUALLY exposes, taken verbatim from the default demonstration
 * document (GET /demo/contract-fulfillment — a platform route, no
 * session): the provider the deterministic runtime composes, the
 * adapter and access technology identities, the standard mechanisms,
 * the sandbox position (stated plainly: the deterministic reference
 * adapters ARE the sandbox providers — no provider claim is made) and
 * the evidence class through EvidenceBadge. Nothing is invented beyond
 * what the document carries.
 */

import Link from "next/link";
import type { DemoDocument } from "@/lib/api/types";
import type { AdcosReadState } from "@/features/eligibility";
import { ObjectSection } from "@/features/eligibility";
import { ErrorState, EvidenceBadge, RefreshIcon } from "@/components/ui";

export function CompositionSection({
  read,
}: {
  read: AdcosReadState<DemoDocument>;
}) {
  return (
    <ObjectSection
      id="networks-composition"
      title="Execution composition"
      description={
        <>
          The provider and adapter facts this deployment exposes, from the
          default demonstration document (
          <span className="font-mono">GET /demo/contract-fulfillment</span>).
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
          {read.loading ? "fetching…" : "Refresh"}
        </button>
      }
    >
      {read.error ? (
        <ErrorState error={read.error} onRetry={read.refresh} compact />
      ) : !read.data ? (
        <div className="flex flex-col gap-2" aria-busy="true">
          <div className="h-3 w-1/2 animate-pulse rounded bg-raised" />
          <div className="h-3 w-2/3 animate-pulse rounded bg-raised" />
          <div className="h-3 w-1/3 animate-pulse rounded bg-raised" />
        </div>
      ) : (
        <CompositionFacts document={read.data} />
      )}
    </ObjectSection>
  );
}

/** One member of the execution record, rendered verbatim (missing → "—"). */
function member(document: DemoDocument, key: string): string {
  const value = document.execution[key];
  if (value === undefined || value === null) return "—";
  return String(value);
}

function CompositionFacts({ document }: { document: DemoDocument }) {
  const sandboxLine =
    typeof document.execution.sandbox === "boolean"
      ? `sandbox: ${String(document.execution.sandbox)}`
      : "—";
  const mechanisms = Array.isArray(document.execution.standard_mechanisms)
    ? document.execution.standard_mechanisms.map((value) => String(value))
    : [];
  const contractId = String(document.contract.contract_id ?? "");

  return (
    <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
      <div className="grid grid-cols-[minmax(10rem,auto)_1fr] items-baseline gap-x-3">
        <dt className="font-mono text-2xs text-ink-faint">provider</dt>
        <dd className="min-w-0 break-all font-mono text-xs text-ink">
          {member(document, "provider")}
        </dd>
      </div>
      <div className="grid grid-cols-[minmax(10rem,auto)_1fr] items-baseline gap-x-3">
        <dt className="font-mono text-2xs text-ink-faint">adapter_id</dt>
        <dd className="min-w-0 break-all font-mono text-xs text-ink">
          {member(document, "adapter_id")}
        </dd>
      </div>
      <div className="grid grid-cols-[minmax(10rem,auto)_1fr] items-baseline gap-x-3">
        <dt className="font-mono text-2xs text-ink-faint">
          access_technology_id
        </dt>
        <dd className="min-w-0 break-all font-mono text-xs text-ink">
          {member(document, "access_technology_id")}
        </dd>
      </div>
      <div className="grid grid-cols-[minmax(10rem,auto)_1fr] items-baseline gap-x-3">
        <dt className="font-mono text-2xs text-ink-faint">sandbox</dt>
        <dd className="min-w-0">
          <span className="break-all font-mono text-xs text-ink">
            {sandboxLine}
          </span>
          <p className="mt-0.5 text-xs leading-relaxed text-ink-faint">
            the deterministic reference adapters ARE the sandbox providers —
            no provider claim is made
          </p>
        </dd>
      </div>
      <div className="grid grid-cols-[minmax(10rem,auto)_1fr] items-baseline gap-x-3">
        <dt className="font-mono text-2xs text-ink-faint">
          standard_mechanisms
        </dt>
        <dd className="min-w-0">
          {mechanisms.length === 0 ? (
            <span className="font-mono text-xs text-ink-faint">—</span>
          ) : (
            <ul className="flex flex-wrap gap-1.5">
              {mechanisms.map((mechanism) => (
                <li
                  key={mechanism}
                  className="rounded border border-line bg-raised px-1.5 py-px font-mono text-2xs text-ink-muted"
                >
                  {mechanism}
                </li>
              ))}
            </ul>
          )}
        </dd>
      </div>
      <div className="grid grid-cols-[minmax(10rem,auto)_1fr] items-baseline gap-x-3">
        <dt className="font-mono text-2xs text-ink-faint">evidence_class</dt>
        <dd className="flex min-w-0 flex-wrap items-center gap-2">
          <EvidenceBadge evidenceClass={document.evidence_class} />
          <span className="text-xs text-ink-muted">
            software-side — the demonstration never claims physical/network
            validation
          </span>
        </dd>
      </div>
      <div className="grid grid-cols-[minmax(10rem,auto)_1fr] items-baseline gap-x-3 sm:col-span-2">
        <dt className="font-mono text-2xs text-ink-faint">
          current contract use
        </dt>
        <dd className="min-w-0">
          <Link
            href={`/connectivity/contracts/${contractId}`}
            title={contractId}
            className="break-all font-mono text-xs text-accent transition-colors hover:text-ink"
          >
            {contractId}
          </Link>
        </dd>
      </div>
    </dl>
  );
}
