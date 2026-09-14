"use client";

/**
 * ConsumedBackendsSection — the durable backends this deployment
 * reports through GET /readyz (platform route, no session). State
 * values are the runtime's own vocabulary rendered verbatim through
 * Status; details are the runtime's own words. When the runtime
 * reports no backends, the section says so with the same honest
 * wording as the shell ("no durable backends (sandbox mode)" — sandbox
 * only). A failing readiness check surfaces through the shared
 * ErrorState with the verbatim reason.
 */

import type { Readiness } from "@/lib/api/types";
import type { AdcosReadState } from "@/features/eligibility";
import { ObjectSection } from "@/features/eligibility";
import { DataTable, RefreshIcon, Status } from "@/components/ui";
import type { Column } from "@/components/ui";

interface BackendRow {
  name: string;
  state: string;
  detail: string;
}

const COLUMNS: Column<BackendRow>[] = [
  {
    key: "name",
    header: "backend",
    accessor: (row) => row.name,
    render: (row) => (
      <span className="font-mono text-xs text-ink">{row.name}</span>
    ),
  },
  {
    key: "state",
    header: "state",
    accessor: (row) => row.state,
    render: (row) => <Status value={row.state} />,
  },
  {
    key: "detail",
    header: "detail",
    accessor: (row) => row.detail,
  },
];

function toRows(
  backends: Record<string, { state: string; detail: string }>,
): BackendRow[] {
  return Object.entries(backends).map(([name, backend]) => ({
    name,
    state: backend.state,
    detail: backend.detail,
  }));
}

export function ConsumedBackendsSection({
  read,
}: {
  read: AdcosReadState<Readiness>;
}) {
  const readiness = read.data ?? null;
  const rows = readiness ? toRows(readiness.backends ?? {}) : [];
  const delegatedRows = readiness?.delegated_backends
    ? toRows(readiness.delegated_backends)
    : [];

  return (
    <ObjectSection
      id="networks-backends"
      title="Consumed backends"
      description="The durable backends this deployment reports through GET /readyz — state values and details are the runtime's own words."
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
    >
      <div className="flex flex-col gap-3">
        <DataTable
          rows={rows}
          columns={COLUMNS}
          getRowKey={(row) => row.name}
          loading={read.loading && !readiness}
          error={read.error}
          onRetry={read.refresh}
          emptyTitle={
            readiness?.mode === "sandbox"
              ? "no durable backends (sandbox mode)"
              : "no backends reported"
          }
        />
        {delegatedRows.length > 0 ? (
          <div className="flex flex-col gap-1.5">
            <p className="text-2xs uppercase tracking-wide text-ink-faint">
              delegated backends
            </p>
            <DataTable
              rows={delegatedRows}
              columns={COLUMNS}
              getRowKey={(row) => row.name}
            />
          </div>
        ) : null}
      </div>
    </ObjectSection>
  );
}
