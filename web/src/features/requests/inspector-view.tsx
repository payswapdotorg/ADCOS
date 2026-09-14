"use client";

/**
 * RequestInspectorView — the /developers/requests surface.
 *
 * The global request log: every request this console session made
 * through the typed client (method, path, status, request_id, duration),
 * filterable (free text + a failures-only toggle over `isFailedRequest`),
 * inspectable per row in a detail drawer (masked request headers, request
 * body, captured response headers/body, the copyable curl reproduction,
 * and the registry operation that produced the request), and clearable
 * with an explicit confirmation.
 *
 * Deep-link contract (the object-linking affordance): 
 * `/developers/requests?request=<sequence>` opens the inspector with that
 * captured request preselected in the drawer — `requestsHref(sequence)`
 * (features/requests) builds the link other surfaces adopt.
 *
 * In-memory display data only: a reload clears the log by design, and no
 * secret is ever recorded (the recorder captures no request headers).
 */

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useSession } from "@/lib/session";
import { ConsoleSearchProviders } from "@/features/search/providers";
import { DataTable, FilterBar, type Column } from "@/components/ui";
import {
  clearRequests,
  isFailedRequest,
  requestLabel,
  useRequestLog,
  type LoggedRequest,
} from "./request-log";
import { ensureRequestRecorder } from "./recorder";
import { RequestDetailDrawer } from "./request-detail";

function timeOfDay(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toISOString().slice(11, 19);
}

export function RequestInspectorView() {
  const { application } = useSession();
  const applicationId = application?.application_id ?? null;
  const entries = useRequestLog();

  // the recorder enriches every future request with duration, the
  // captured response body and the surfaced response headers
  useEffect(() => {
    ensureRequestRecorder();
  }, []);

  const searchParams = useSearchParams();
  const requestParam = searchParams?.get("request") ?? "";

  const [search, setSearch] = useState("");
  const [failuresOnly, setFailuresOnly] = useState(false);
  const [selectedSequence, setSelectedSequence] = useState<number | null>(null);
  const [clearArmed, setClearArmed] = useState(false);

  // the deep link: ?request=<sequence> preselects the captured request
  useEffect(() => {
    if (requestParam === "") return;
    const sequence = Number.parseInt(requestParam, 10);
    if (Number.isNaN(sequence)) return;
    if (entries.some((entry) => entry.sequence === sequence)) {
      setSelectedSequence(sequence);
    }
    // apply once per param value; the entries dependency lets a link
    // that arrives before its entry (a rare race) still resolve
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestParam, entries.length]);

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return entries.filter((entry) => {
      if (failuresOnly && !isFailedRequest(entry)) return false;
      if (!needle) return true;
      return (
        entry.method.toLowerCase().includes(needle) ||
        entry.path.toLowerCase().includes(needle) ||
        (entry.requestId ?? "").toLowerCase().includes(needle) ||
        (entry.reason ?? "").toLowerCase().includes(needle)
      );
    });
  }, [entries, search, failuresOnly]);

  const selected = useMemo(
    () =>
      selectedSequence === null
        ? null
        : (entries.find((entry) => entry.sequence === selectedSequence) ?? null),
    [entries, selectedSequence],
  );

  const failureCount = useMemo(
    () => entries.filter(isFailedRequest).length,
    [entries],
  );

  const columns: Column<LoggedRequest>[] = [
    {
      key: "time",
      header: "Time",
      sortable: true,
      accessor: (row) => row.at,
      render: (row) => (
        <span className="whitespace-nowrap font-mono text-xs text-ink-faint">
          {timeOfDay(row.at)}
        </span>
      ),
    },
    {
      key: "method",
      header: "Method",
      sortable: true,
      accessor: (row) => row.method,
      render: (row) => (
        <span className="font-mono text-xs text-ink">{row.method}</span>
      ),
    },
    {
      key: "path",
      header: "Path",
      sortable: true,
      accessor: (row) => row.path,
      render: (row) => (
        <span
          className="block max-w-[24rem] truncate font-mono text-xs text-ink"
          title={row.path}
        >
          {row.path}
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      sortable: true,
      accessor: (row) => row.status,
      render: (row) => (
        <span
          className={`inline-flex items-center rounded border px-1.5 py-px font-mono text-2xs ${
            isFailedRequest(row)
              ? "border-danger/60 text-danger"
              : "border-positive/60 text-positive"
          }`}
        >
          {row.status}
        </span>
      ),
    },
    {
      key: "request_id",
      header: "Request id",
      sortable: false,
      accessor: (row) => row.requestId,
      render: (row) => (
        <span
          className="block max-w-[14rem] truncate font-mono text-2xs text-ink-muted"
          title={row.requestId}
        >
          {row.requestId || "—"}
        </span>
      ),
    },
    {
      key: "duration",
      header: "Duration",
      sortable: true,
      align: "right",
      accessor: (row) => row.durationMs ?? null,
      render: (row) =>
        typeof row.durationMs === "number" ? (
          <span className="whitespace-nowrap font-mono text-2xs text-ink-muted">
            {`${row.durationMs} ms`}
          </span>
        ) : (
          <span className="text-ink-faint">—</span>
        ),
    },
  ];

  return (
    <div className="mx-auto w-full max-w-workbench px-gutter py-rhythm">
      <ConsoleSearchProviders />
      <div className="flex flex-col gap-4">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-ink">Request Inspector</h1>
            <p className="mt-1 text-sm text-ink-muted">
              Every request this console session made through the typed client,
              in memory only — a reload clears it by design. Select a row to
              inspect the exact request, the captured response and the curl
              reproduction (the credential is always masked).
            </p>
          </div>
        </header>

        <FilterBar
          search={{
            value: search,
            onChange: setSearch,
            placeholder: "Search method, path, request id…",
          }}
          filters={[
            {
              id: "failures",
              label: "Failures only",
              value: failuresOnly ? "failures" : "all",
              options: [
                { value: "all", label: "All requests" },
                { value: "failures", label: `Failures only (${failureCount})` },
              ],
              onChange: (value) => setFailuresOnly(value === "failures"),
            },
          ]}
          right={
            <>
              <span
                className="font-mono text-2xs text-ink-faint"
                data-testid="requests-count"
              >
                {filtered.length} of {entries.length} captured requests
              </span>
              {entries.length > 0 ? (
                clearArmed ? (
                  <span className="flex items-center gap-1.5">
                    <button
                      type="button"
                      data-testid="confirm-clear-requests"
                      onClick={() => {
                        clearRequests();
                        setSelectedSequence(null);
                        setClearArmed(false);
                      }}
                      className="inline-flex h-8 items-center rounded-md bg-danger px-3 text-sm font-medium text-white transition-colors hover:opacity-90"
                    >
                      Confirm clear
                    </button>
                    <button
                      type="button"
                      data-testid="cancel-clear-requests"
                      onClick={() => setClearArmed(false)}
                      className="inline-flex h-8 items-center rounded-md border border-line-strong bg-raised px-3 text-sm text-ink transition-colors hover:bg-surface"
                    >
                      Cancel
                    </button>
                  </span>
                ) : (
                  <button
                    type="button"
                    data-testid="clear-requests"
                    onClick={() => setClearArmed(true)}
                    className="inline-flex h-8 items-center rounded-md border border-line-strong bg-raised px-3 text-sm text-ink transition-colors hover:bg-surface"
                  >
                    Clear log
                  </button>
                )
              ) : null}
            </>
          }
        />

        <DataTable
          rows={filtered}
          columns={columns}
          getRowKey={(row) => `request-${row.sequence}`}
          emptyTitle={
            failuresOnly
              ? "No failed requests in this session"
              : "No requests captured yet"
          }
          emptyDescription={
            failuresOnly ? (
              "Every captured request in this session succeeded (status 2xx/3xx)."
            ) : (
              <>
                Interact with any console surface — every request through the
                typed client lands here with its status, request id and duration.
                The log is in-memory only; nothing is persisted.
              </>
            )
          }
          onRowActivate={(row) => setSelectedSequence(row.sequence)}
          rowAriaLabel={(row) => `${requestLabel(row)}, status ${row.status}`}
        />

        <p className="text-xs text-ink-faint">
          Entries recorded before an inspector-capable page mounted carry no
          duration or captured response — the enrichment is best-effort and
          nothing is ever fabricated.
        </p>
      </div>

      <RequestDetailDrawer
        entry={selected}
        open={selected !== null}
        onOpenChange={(open) => {
          if (!open) setSelectedSequence(null);
        }}
        applicationId={applicationId}
      />
    </div>
  );
}
