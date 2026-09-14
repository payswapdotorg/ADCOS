"use client";

/**
 * DemoCard — the deterministic full-chain demonstration affordance.
 *
 * POST /demo/contract-fulfillment {"instant"} — a PLATFORM route: no
 * authentication, no idempotency ceremony, and (by decision) no
 * ApiRequestPanel: this is an unauthenticated platform demonstration,
 * not a developer-API mutation. The outcome is shown honestly: the
 * document's own mode/environment verbatim, its evidence class through
 * EvidenceBadge ("SOFTWARE" stays visibly software-side), the final
 * segment state, the evidence record count — and the determinism note
 * (identical instant → identical document). Successful runs are
 * registered in the shared in-memory demo-run registry so Fulfillment
 * can list and link them.
 */

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useSession } from "@/lib/session";
import type { DemoDocument } from "@/lib/api/types";
import { ObjectSection } from "@/features/eligibility";
import {
  DEFAULT_DEMO_INSTANT,
  registerDemoRun,
} from "@/features/fulfillment/demo-runs";
import { ErrorState, EvidenceBadge } from "@/components/ui";

export function DemoCard({
  id = "home-demo",
  className,
}: {
  id?: string;
  className?: string;
}) {
  const { client } = useSession();
  const [instant, setInstant] = useState<string>(DEFAULT_DEMO_INSTANT);
  const [running, setRunning] = useState(false);
  const [document, setDocument] = useState<DemoDocument | null>(null);
  const [error, setError] = useState<unknown>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (running) return;
    setRunning(true);
    setError(null);
    try {
      const doc = await client.demoContractFulfillment(instant.trim());
      setDocument(doc);
      registerDemoRun({
        instant: doc.instant,
        ranAt: new Date().toISOString(),
        contractId: String(doc.contract.contract_id ?? ""),
        planId: String(doc.plan.plan_id ?? ""),
      });
    } catch (caught) {
      setDocument(null);
      setError(caught);
    } finally {
      setRunning(false);
    }
  }

  const segmentStates = document
    ? Array.isArray(document.execution.segment_states)
      ? document.execution.segment_states.map((value) => String(value))
      : []
    : [];
  const finalSegmentState =
    segmentStates.length > 0
      ? segmentStates[segmentStates.length - 1]
      : "—";

  return (
    <ObjectSection
      id={id}
      title="The fulfillment demonstration"
      description={
        <>
          The deterministic full-chain demonstration: contract → plan →
          execution → evidence (
          <span className="font-mono">
            POST /demo/contract-fulfillment
          </span>, no authentication). Identical instant → identical
          document.
        </>
      }
      className={className}
    >
      <div className="flex flex-col gap-3">
        <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-2">
          <div className="flex min-w-56 flex-1 flex-col gap-1 sm:max-w-sm">
            <label
              htmlFor={`${id}-instant`}
              className="text-2xs uppercase tracking-wide text-ink-faint"
            >
              instant (RFC 3339 UTC)
            </label>
            <input
              id={`${id}-instant`}
              value={instant}
              onChange={(event) => setInstant(event.target.value)}
              disabled={running}
              autoComplete="off"
              spellCheck={false}
              placeholder={DEFAULT_DEMO_INSTANT}
              className="h-8 w-full rounded-md border border-line bg-raised px-2 font-mono text-sm text-ink placeholder:text-ink-faint"
            />
          </div>
          <button
            type="submit"
            disabled={running}
            className="inline-flex h-8 shrink-0 items-center rounded-md bg-accent px-3 text-sm font-medium text-accent-ink transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-60"
          >
            {running ? "running…" : "Run demonstration"}
          </button>
        </form>

        {error ? <ErrorState error={error} compact /> : null}

        {document ? (
          <div
            data-testid="demo-summary"
            className="flex flex-col gap-3 rounded-md border border-line bg-raised px-3 py-2.5"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium text-ink">
                Demonstration document
              </span>
              <EvidenceBadge evidenceClass={document.evidence_class} />
            </div>
            <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
              <div className="flex flex-col gap-0.5">
                <dt className="font-mono text-2xs text-ink-faint">mode</dt>
                <dd className="font-mono text-xs text-ink">
                  {document.mode}
                </dd>
              </div>
              <div className="flex flex-col gap-0.5">
                <dt className="font-mono text-2xs text-ink-faint">
                  environment
                </dt>
                <dd className="font-mono text-xs text-ink">
                  {document.environment}
                </dd>
              </div>
              <div className="flex flex-col gap-0.5">
                <dt className="font-mono text-2xs text-ink-faint">contract</dt>
                <dd>
                  <Link
                    href={`/connectivity/contracts/${String(
                      document.contract.contract_id,
                    )}`}
                    title={String(document.contract.contract_id)}
                    className="break-all font-mono text-xs text-accent transition-colors hover:text-ink"
                  >
                    {String(document.contract.contract_id)}
                  </Link>
                </dd>
              </div>
              <div className="flex flex-col gap-0.5">
                <dt className="font-mono text-2xs text-ink-faint">plan</dt>
                <dd className="break-all font-mono text-xs text-ink">
                  {String(document.plan.plan_id)}
                </dd>
              </div>
              <div className="flex flex-col gap-0.5">
                <dt className="font-mono text-2xs text-ink-faint">
                  final segment state
                </dt>
                <dd className="font-mono text-xs text-ink">
                  {finalSegmentState}
                </dd>
              </div>
              <div className="flex flex-col gap-0.5">
                <dt className="font-mono text-2xs text-ink-faint">
                  evidence records
                </dt>
                <dd className="font-mono text-xs text-ink">
                  {document.evidence.length}
                </dd>
              </div>
            </dl>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="max-w-md text-xs text-ink-faint">
                Registered in this session&apos;s demonstration runs
                (in-memory). The demonstration contract is readable through
                the developer API.
              </p>
              <Link
                href="/fulfillment"
                className="text-sm text-accent transition-colors hover:text-ink"
              >
                Open Fulfillment →
              </Link>
            </div>
          </div>
        ) : null}
      </div>
    </ObjectSection>
  );
}
