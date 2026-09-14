"use client";
import "@/features/eligibility/fetch-binding-shim";

/**
 * The Fulfillment overview — run the deterministic demonstration, revisit
 * the runs performed in this browser session, and inspect the contracts
 * visible to the connected application.
 *
 * Honesty positions baked in:
 * - the demonstration is the ONLY execution leg this deployment has
 *   (software-only, evidence_class SOFTWARE — rendered through
 *   EvidenceBadge, never as physical connectivity);
 * - the runs list is a browser-session memory, NOT backend truth (the
 *   backend exposes no run registry — a reload clears it);
 * - the contracts list is an authenticated developer-API read — gated on
 *   the session with honest connect guidance when disconnected;
 * - the demonstration itself needs no session (/demo/* is a platform
 *   route) and is deterministic: identical instant → identical document.
 */

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ApiRequestPanel,
  DataTable,
  EmptyState,
  ErrorState,
  EvidenceBadge,
  Status,
  type Column,
} from "@/components/ui";
import { useSession } from "@/lib/session";
import type { Contract, DemoDocument } from "@/lib/api/types";
import { ObjectSection, useAdcosRead } from "@/features/eligibility";
import {
  DEFAULT_DEMO_INSTANT,
  registerDemoRun,
  useDemoRuns,
} from "./demo-runs";
import { parseDemoDocument } from "./demo-document";
import { DEMO_DETERMINISM_NOTE } from "./run-detail-view";

const CONTRACT_COLUMNS: Column<Contract>[] = [
  {
    key: "id",
    header: "id",
    sortable: true,
    accessor: (row) => row.contract_id,
    render: (row) => (
      <Link
        href={`/connectivity/contracts/${row.contract_id}`}
        onClick={(event) => event.stopPropagation()}
        className="break-all font-mono text-xs text-accent hover:underline"
      >
        {row.contract_id}
      </Link>
    ),
  },
  {
    key: "state",
    header: "state",
    sortable: true,
    accessor: (row) => row.state,
    render: (row) => <Status value={row.state} size="sm" />,
  },
  {
    key: "validity",
    header: "validity",
    sortable: true,
    accessor: (row) => row.validity.not_before,
    render: (row) => (
      <span className="whitespace-nowrap font-mono text-2xs text-ink-muted">
        {`${row.validity.not_before} → ${row.validity.not_after}`}
      </span>
    ),
  },
  {
    key: "constraints",
    header: "hard constraints",
    sortable: true,
    align: "right",
    accessor: (row) => row.hard_constraints.length,
  },
  {
    key: "command_count",
    header: "command_count",
    sortable: true,
    align: "right",
    accessor: (row) => row.command_count,
  },
];

function shortId(value: string): string {
  return value.length > 24 ? `${value.slice(0, 24)}…` : value;
}

export function FulfillmentOverview() {
  const router = useRouter();
  const { status, client } = useSession();
  const connected = status === "connected";

  const runs = useDemoRuns();

  const [instantInput, setInstantInput] = useState(DEFAULT_DEMO_INSTANT);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<DemoDocument | null>(null);
  const [ranInstant, setRanInstant] = useState<string | null>(null);
  const [runError, setRunError] = useState<unknown>(null);

  // the contracts read is AUTHENTICATED — suspended (null fetcher) until a
  // session exists, with honest connect guidance in its place
  const contractsRead = useAdcosRead(
    // bodyless list read — the browser-compatible form (the API's list
    // pagination rides the GET JSON body, which browsers cannot send)
    connected ? () => client.listContracts() : null,
    [connected, client],
  );
  const contracts: Contract[] = contractsRead.data?.data.items ?? [];

  async function handleRun(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (running) return;
    const instant = instantInput.trim();
    if (instant.length === 0) return;
    setRunning(true);
    setRunError(null);
    setResult(null);
    try {
      const doc = await client.demoContractFulfillment(instant);
      const view = parseDemoDocument(doc);
      setResult(doc);
      setRanInstant(instant);
      registerDemoRun({
        instant,
        ranAt: new Date().toISOString(),
        contractId: view.contract.contract_id,
        planId: view.plan.plan_id,
      });
    } catch (caught) {
      setRunError(caught);
    } finally {
      setRunning(false);
    }
  }

  const resultView = result ? parseDemoDocument(result) : null;
  const finalSegmentState = resultView
    ? resultView.execution.segment_states.length > 0
      ? resultView.execution.segment_states[resultView.execution.segment_states.length - 1]
      : null
    : null;

  return (
    <div className="mx-auto w-full max-w-workbench px-gutter py-rhythm">
      <header className="mb-6">
        <h1 className="text-xl font-semibold">Fulfillment</h1>
        <p className="mt-1 text-sm text-ink-muted">
          The chain Contract → Plan → Execution → Provider → Evidence →
          Assurance. This deployment&apos;s execution leg exists in the
          deterministic demonstration (software-only).
        </p>
      </header>

      <div className="flex flex-col gap-4">
        {/* Run the demonstration */}
        <ObjectSection
          title="Run the demonstration"
          description="POST /demo/contract-fulfillment with an instant — the platform demonstration route (no session needed, no authentication). Deterministic: identical instant → identical document."
          actions={
            <span className="font-mono text-2xs text-ink-faint">
              POST /demo/contract-fulfillment
            </span>
          }
        >
          <form onSubmit={handleRun} className="flex flex-col gap-2">
            <div className="flex flex-wrap items-end gap-2">
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <label
                  htmlFor="demo-instant"
                  className="text-xs text-ink-muted"
                >
                  instant (RFC 3339 UTC)
                </label>
                <input
                  id="demo-instant"
                  name="instant"
                  autoComplete="off"
                  spellCheck={false}
                  value={instantInput}
                  onChange={(event) => setInstantInput(event.target.value)}
                  placeholder={DEFAULT_DEMO_INSTANT}
                  className="w-full rounded border border-line bg-raised px-2.5 py-1.5 font-mono text-sm text-ink placeholder:text-ink-faint"
                />
              </div>
              <button
                type="submit"
                disabled={running}
                className="inline-flex h-9 shrink-0 items-center rounded-md bg-accent px-3 text-sm font-medium text-accent-ink transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-60"
              >
                {running ? "Running…" : "Run demonstration"}
              </button>
            </div>
            <p className="text-xs leading-relaxed text-ink-faint">
              {DEMO_DETERMINISM_NOTE}
            </p>
          </form>

          <ApiRequestPanel
            method="POST"
            path="/demo/contract-fulfillment"
            body={{ instant: instantInput.trim() || DEFAULT_DEMO_INSTANT }}
            description="The request the button sends — a platform route outside the authenticated developer API."
          />

          {runError ? (
            <div className="rounded-md border border-line bg-surface">
              <ErrorState error={runError} compact />
            </div>
          ) : null}

          {result && resultView && ranInstant ? (
            <div
              data-testid="demo-run-summary"
              className="rounded-md border border-line bg-raised px-3 py-3"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-semibold text-ink">
                  Demonstration complete
                </span>
                <EvidenceBadge
                  evidenceClass={result.evidence_class}
                  size="sm"
                />
              </div>
              <dl className="mt-2 grid grid-cols-[minmax(9rem,auto)_1fr] items-baseline gap-x-3 gap-y-1.5">
                <dt className="font-mono text-2xs text-ink-faint">mode</dt>
                <dd className="font-mono text-xs text-ink">{result.mode}</dd>
                <dt className="font-mono text-2xs text-ink-faint">
                  environment
                </dt>
                <dd className="font-mono text-xs text-ink">
                  {result.environment}
                </dd>
                <dt className="font-mono text-2xs text-ink-faint">
                  contract_id
                </dt>
                <dd className="min-w-0">
                  <Link
                    href={`/connectivity/contracts/${resultView.contract.contract_id}`}
                    className="break-all font-mono text-xs text-accent hover:underline"
                  >
                    {resultView.contract.contract_id}
                  </Link>
                </dd>
                <dt className="font-mono text-2xs text-ink-faint">plan_id</dt>
                <dd className="break-all font-mono text-xs text-ink">
                  {resultView.plan.plan_id}
                </dd>
                <dt className="font-mono text-2xs text-ink-faint">
                  final segment state
                </dt>
                <dd>
                  {finalSegmentState ? (
                    <Status value={finalSegmentState} size="sm" />
                  ) : (
                    <span className="font-mono text-xs text-ink-faint">—</span>
                  )}
                </dd>
              </dl>
              <Link
                href={`/fulfillment/run/${encodeURIComponent(ranInstant)}`}
                className="mt-3 inline-flex text-sm font-medium text-accent transition-colors hover:underline"
              >
                Open the demonstration run →
              </Link>
            </div>
          ) : null}
        </ObjectSection>

        {/* Demonstration runs */}
        <ObjectSection
          title="Demonstration runs"
          description="This browser session's runs, newest first. The backend exposes no run registry — this list is in-memory presentation only (a reload clears it); the demonstration itself is deterministic and re-runnable at any instant."
        >
          {runs.length === 0 ? (
            <EmptyState
              title="No demonstration runs in this session yet"
              description="The backend exposes no run registry — runs performed in this browser session are remembered here (a reload clears this list); the demonstration itself is deterministic and re-runnable at any instant."
            />
          ) : null}
          <ul className="divide-y divide-line rounded-md border border-line bg-surface">
            <li data-testid="default-demo-run-row" className="px-4 py-3">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <div className="min-w-0">
                  <Link
                    href={`/fulfillment/run/${encodeURIComponent(DEFAULT_DEMO_INSTANT)}`}
                    className="text-sm font-medium text-accent hover:underline"
                  >
                    The default demonstration
                  </Link>
                  <p className="mt-0.5 font-mono text-xs text-ink-muted">
                    {DEFAULT_DEMO_INSTANT}
                  </p>
                </div>
                <p className="text-xs text-ink-faint">
                  the GET form runs at this fixed instant
                </p>
              </div>
            </li>
            {runs.map((run) => (
              <li
                key={run.instant}
                data-testid="session-demo-run-row"
                className="px-4 py-3"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                  <div className="min-w-0">
                    <Link
                      href={`/fulfillment/run/${encodeURIComponent(run.instant)}`}
                      className="break-all font-mono text-xs text-accent hover:underline"
                    >
                      {run.instant}
                    </Link>
                    <p className="mt-0.5 flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
                      <Link
                        href={`/connectivity/contracts/${run.contractId}`}
                        title={run.contractId}
                        className="font-mono text-xs text-ink-muted transition-colors hover:text-accent"
                      >
                        {shortId(run.contractId)}
                      </Link>
                      <span
                        title={run.planId}
                        className="font-mono text-xs text-ink-faint"
                      >
                        {shortId(run.planId)}
                      </span>
                    </p>
                  </div>
                  <p className="font-mono text-2xs text-ink-faint">
                    {`ran ${run.ranAt}`}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </ObjectSection>

        {/* Contracts (authenticated read) */}
        <ObjectSection
          title="Contracts"
          description="API-created contracts and demonstration contracts visible to this application — in sandbox the demo principal IS the connected application."
        >
          {connected ? (
            <DataTable
              rows={contracts}
              columns={CONTRACT_COLUMNS}
              getRowKey={(row) => row.contract_id}
              loading={contractsRead.loading && !contractsRead.loaded}
              error={contractsRead.error}
              onRetry={contractsRead.refresh}
              emptyTitle="No contracts visible to this application"
              emptyDescription="Create one through the contract builder in Connectivity, or run the demonstration above — demonstration contracts become visible to the connected application."
              onRowActivate={(row) =>
                router.push(`/connectivity/contracts/${row.contract_id}`)
              }
              rowAriaLabel={(row) => `Open contract ${row.contract_id}`}
            />
          ) : (
            <div className="rounded-md border border-dashed border-line px-4 py-6 text-sm leading-relaxed text-ink-muted">
              Connect an application to read the contract list —{" "}
              <span className="font-mono text-xs">
                GET /api/2.0/contracts
              </span>{" "}
              is an authenticated developer-API read. Open the session menu
              (top right) and use <span className="text-ink">Connect application</span>;
              the credential is held in memory only. The demonstration above
              needs no session: the /demo route is a platform surface.
            </div>
          )}
        </ObjectSection>

        {/* Replanning */}
        <ObjectSection
          title="Replanning"
          description="What replanning is, what would trigger it, and exactly what this deployment exposes today — never a fabricated event."
        >
          <Link
            href="/fulfillment/replan"
            className="text-sm font-medium text-accent transition-colors hover:underline"
          >
            Replanning — what it is and what this deployment exposes →
          </Link>
        </ObjectSection>
      </div>
    </div>
  );
}
