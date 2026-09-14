"use client";

/**
 * ContractsIndexView — the Connectivity landing surface (Worker 2, plan
 * Task 5): the application's contracts with state / free-text /
 * validity-overlap narrowing (client-side over the fetched list, per the
 * frozen work order) and row activation into the contract detail chain.
 *
 * BROWSER/LIST DISCIPLINE (a real console constraint, disclosed in the
 * completion report): the developer API's list operations carry their
 * pagination and filters in the GET request's JSON body — a form browsers
 * categorically refuse to send (fetch/XHR forbid GET bodies). The console
 * therefore performs the BODYLESS list read (the backend's default page,
 * 20 items) and narrows client-side; when the backend reports more pages,
 * the honest "deeper pagination" notice surfaces the canonical API form
 * (reproducible outside the browser) instead of pretending to page.
 *
 * Truth discipline: every rendered row comes from the backend through
 * useAdcosRead (refresh re-fetches truth — the backend is the single
 * authority, React state holds no cached truth).
 */

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { Contract, ListResponse } from "@/lib/api/types";
import {
  ApiRequestPanel,
  DataTable,
  FilterBar,
  RefreshIcon,
  Status,
  type Column,
} from "@/components/ui";
import { useAdcosRead } from "@/features/eligibility";
import { registerCommand } from "@/features/search";
import { useSession } from "@/lib/session";
import { ConnectGuidance } from "./connect-guidance";

/** The backend states the developer API actually returns (verbatim vocabulary). */
const STATE_FILTER_OPTIONS = ["INTENT", "OFFER_SELECTED", "CONTRACT_ACTIVE", "TERMINATED"];

export function ContractsIndexView() {
  const { status, client } = useSession();
  const router = useRouter();
  const connected = status === "connected";

  const [search, setSearch] = useState("");
  const [stateFilter, setStateFilter] = useState("");
  const [overlapDate, setOverlapDate] = useState("");

  // the palette entry for the builder (registered on mount, cleaned up)
  useEffect(
    () =>
      registerCommand({
        id: "go-contract-builder",
        title: "New contract",
        group: "Actions",
        href: "/connectivity/new",
      }),
    [],
  );

  // the BODYLESS list read — the browser-compatible form of the list
  // discipline (see the module docstring); filtering is client-side
  const read = useAdcosRead(
    connected ? () => client.listContracts() : null,
    [client],
  );
  const chain: ListResponse<Contract> | null = read.data?.data ?? null;

  // client-side narrowing over the fetched default page (state, free
  // text, validity overlap — all presentation-only, per the work order)
  const rows = useMemo(() => {
    const items = chain?.items ?? [];
    const needle = search.trim().toLowerCase();
    return items.filter((contract) => {
      if (stateFilter && contract.state !== stateFilter) {
        return false;
      }
      if (
        needle &&
        !contract.id.toLowerCase().includes(needle) &&
        !contract.contract_id.toLowerCase().includes(needle)
      ) {
        return false;
      }
      if (overlapDate) {
        // a day overlaps the validity window when the window starts at or
        // before the day's end and ends at or after the day's start
        const dayStart = `${overlapDate}T00:00:00Z`;
        const dayEnd = `${overlapDate}T23:59:59Z`;
        if (
          !(
            contract.validity.not_before <= dayEnd &&
            contract.validity.not_after >= dayStart
          )
        ) {
          return false;
        }
      }
      return true;
    });
  }, [chain, search, overlapDate, stateFilter]);

  const fetchedCount = chain?.items.length ?? 0;
  const clientNarrowing =
    search.trim() !== "" || overlapDate !== "" || stateFilter !== "";

  const columns: Column<Contract>[] = [
    {
      key: "contract",
      header: "Contract",
      sortable: true,
      accessor: (row) => row.id,
      render: (row) => (
        <span
          className="block max-w-[18rem] truncate font-mono text-xs text-ink"
          title={row.id}
        >
          {row.id}
        </span>
      ),
    },
    {
      key: "state",
      header: "State",
      sortable: true,
      accessor: (row) => row.state,
      render: (row) => <Status value={row.state} />,
    },
    {
      key: "principal",
      header: "Principal",
      sortable: true,
      accessor: (row) => row.principal.principal_ref,
      render: (row) => (
        <span
          className="block max-w-[14rem] truncate font-mono text-xs text-ink-muted"
          title={row.principal.principal_ref}
        >
          {row.principal.principal_ref}
        </span>
      ),
    },
    {
      key: "validity",
      header: "Validity",
      sortable: true,
      accessor: (row) => row.validity.not_before,
      render: (row) => (
        <span className="whitespace-nowrap font-mono text-xs text-ink-muted">
          {row.validity.not_before} → {row.validity.not_after}
        </span>
      ),
    },
    {
      key: "constraints",
      header: "Constraints",
      sortable: true,
      align: "right",
      accessor: (row) => row.hard_constraints.length,
    },
    {
      key: "commands",
      header: "Commands",
      sortable: true,
      align: "right",
      accessor: (row) => row.command_count,
    },
  ];

  const header = (
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold text-ink">Connectivity</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Connectivity contracts — record intents, follow the lifecycle chain,
          and manage leases. Every row is backend truth from GET /api/2.0/contracts.
        </p>
      </div>
      <Link
        href="/connectivity/new"
        className="inline-flex h-8 items-center rounded-md bg-accent px-3 text-sm text-accent-ink hover:bg-accent-strong"
      >
        New contract
      </Link>
    </header>
  );

  if (!connected) {
    return (
      <div className="mx-auto w-full max-w-workbench px-gutter py-rhythm">
        <div className="flex flex-col gap-4">
          {header}
          <ConnectGuidance lead="The contracts list is an authenticated developer-API read (GET /api/2.0/contracts with the session headers)." />
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-workbench px-gutter py-rhythm">
      <div className="flex flex-col gap-4">
        {header}

        <FilterBar
          search={{
            value: search,
            onChange: setSearch,
            placeholder: "Search contract id…",
          }}
          filters={[
            {
              id: "state",
              label: "Lifecycle state",
              value: stateFilter,
              options: [
                { value: "", label: "All states" },
                ...STATE_FILTER_OPTIONS.map((state) => ({ value: state, label: state })),
              ],
              onChange: setStateFilter,
            },
          ]}
          right={
            <>
              <input
                type="date"
                aria-label="Validity overlapping date"
                value={overlapDate}
                onChange={(event) => setOverlapDate(event.target.value)}
                className="h-8 rounded-md border border-line bg-raised px-2 text-sm text-ink"
              />
              <button
                type="button"
                aria-label="Refresh contracts"
                onClick={() => read.refresh()}
                className="inline-flex h-8 items-center gap-1.5 rounded-md border border-line-strong bg-raised px-3 text-sm text-ink transition-colors hover:bg-surface"
              >
                <RefreshIcon size={14} />
                Refresh
              </button>
            </>
          }
        />

        <DataTable
          rows={rows}
          columns={columns}
          getRowKey={(row) => row.id}
          loading={read.loading}
          error={read.error}
          onRetry={read.refresh}
          emptyTitle={clientNarrowing ? "No contracts match the current filters" : "No contracts yet"}
          emptyDescription={
            clientNarrowing ? (
              "Adjust the search text, the lifecycle state filter, or the validity-overlapping date."
            ) : (
              <>
                Record your first connectivity intent with the{" "}
                <Link href="/connectivity/new" className="text-accent hover:underline">
                  builder
                </Link>
                . The{" "}
                <Link href="/fulfillment" className="text-accent hover:underline">
                  fulfillment demonstration
                </Link>{" "}
                creates one too.
              </>
            )
          }
          onRowActivate={(row) => router.push(`/connectivity/contracts/${row.id}`)}
          rowAriaLabel={(row) => `Contract ${row.id}, state ${row.state}`}
        />

        <div className="flex flex-col gap-2">
          <p className="text-xs text-ink-faint" data-testid="contracts-count">
            {read.loaded
              ? clientNarrowing
                ? `${rows.length} of ${fetchedCount} fetched contracts shown`
                : `${fetchedCount} contracts`
              : "loading…"}
          </p>
          {chain?.has_more ? (
            <div
              data-testid="deeper-pagination-notice"
              className="rounded-md border border-dashed border-warning/60 bg-warning/5 px-3 py-2"
            >
              <p className="text-sm text-ink-muted">
                The backend reports more pages than shown. List pagination
                and filters ride the developer API&apos;s GET request JSON
                body — a form browsers cannot send (fetch forbids GET
                bodies), so the console shows the bodyless default page.
                Page through the API directly:
              </p>
              <div className="mt-2">
                <ApiRequestPanel
                  variant="compact"
                  method="GET"
                  path="/api/2.0/contracts"
                  body={{ limit: 20, cursor: chain.next_cursor || "<next_cursor>", filters: { state: "<state>" } }}
                />
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
