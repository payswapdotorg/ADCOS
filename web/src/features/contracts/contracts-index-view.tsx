"use client";

/**
 * ContractsIndexView — the Connectivity landing surface (Worker 2, plan
 * Task 5): the application's contracts with a REAL backend state filter,
 * client-side free-text + validity-overlap narrowing, cursor pagination
 * through the frozen list discipline (pagination rides the GET request's
 * JSON body), and row activation into the contract detail chain.
 *
 * Truth discipline: every rendered row comes from the backend through
 * useAdcosRead; "Load more" grows the page target so the WHOLE visible
 * chain is always freshly fetched (refresh re-fetches truth — the backend
 * is the single authority, React state holds no cached truth).
 */

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { AdcosClient } from "@/lib/api/client";
import type { Contract } from "@/lib/api/types";
import {
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

const PAGE_LIMIT = 100;

/** The backend states the developer API actually returns (verbatim vocabulary). */
const STATE_FILTER_OPTIONS = ["INTENT", "OFFER_SELECTED", "CONTRACT_ACTIVE", "TERMINATED"];

/** The freshly-fetched page chain (no cached pages — see fetchContractsChain). */
interface ContractsChain {
  items: Contract[];
  hasMore: boolean;
}

/**
 * Fetch `pageTarget` pages of the contracts list through the typed client.
 * Growing the target re-fetches from page 1, so nothing shown is ever a
 * cached page: the rendered list is always exactly what the backend just
 * returned.
 */
async function fetchContractsChain(
  client: AdcosClient,
  stateFilter: string,
  pageTarget: number,
): Promise<ContractsChain> {
  let items: Contract[] = [];
  let cursor: string | undefined;
  let hasMore = true;
  for (let page = 0; page < pageTarget && hasMore; page += 1) {
    const envelope = await client.listContracts({
      limit: PAGE_LIMIT,
      ...(cursor ? { cursor } : {}),
      ...(stateFilter ? { filters: { state: stateFilter } } : {}),
    });
    items = items.concat(envelope.data.items);
    hasMore = envelope.data.has_more;
    cursor = envelope.data.next_cursor;
  }
  return { items, hasMore };
}

export function ContractsIndexView() {
  const { status, client } = useSession();
  const router = useRouter();
  const connected = status === "connected";

  const [search, setSearch] = useState("");
  const [stateFilter, setStateFilter] = useState("");
  const [overlapDate, setOverlapDate] = useState("");
  const [pageTarget, setPageTarget] = useState(1);

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

  const read = useAdcosRead(
    connected ? () => fetchContractsChain(client, stateFilter, pageTarget) : null,
    [client, stateFilter, pageTarget],
  );
  const chain = read.data ?? null;

  // client-side narrowing over the freshly fetched chain
  const rows = useMemo(() => {
    const items = chain?.items ?? [];
    const needle = search.trim().toLowerCase();
    return items.filter((contract) => {
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
  }, [chain, search, overlapDate]);

  const fetchedCount = chain?.items.length ?? 0;
  const clientNarrowing = search.trim() !== "" || overlapDate !== "";

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
              onChange: (value) => {
                setStateFilter(value);
                setPageTarget(1);
              },
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

        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs text-ink-faint" data-testid="contracts-count">
            {read.loaded
              ? clientNarrowing
                ? `${rows.length} of ${fetchedCount} fetched contracts shown`
                : `${fetchedCount} contracts`
              : "loading…"}
          </p>
          {chain?.hasMore ? (
            <button
              type="button"
              onClick={() => setPageTarget((target) => target + 1)}
              disabled={read.loading}
              className="inline-flex h-8 items-center rounded-md border border-line-strong bg-raised px-3 text-sm text-ink transition-colors hover:bg-surface disabled:cursor-not-allowed disabled:opacity-50"
            >
              {read.loading ? "Loading…" : "Load more"}
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
