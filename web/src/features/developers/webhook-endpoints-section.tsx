"use client";

/**
 * WebhookEndpointsSection — the webhook endpoints collection (work
 * order deliverable #4, list): a DataTable over the bodyless list
 * read (GET /api/2.0/webhook-endpoints), client-side narrowing by
 * free text and by the frozen event-type vocabulary, row activation
 * into the detail drawer, and the register entry point (gated on the
 * `webhooks:write` capability — named verbatim when missing).
 *
 * LIST DISCIPLINE (the console-wide constraint Worker 2 disclosed):
 * the developer API's list operations carry pagination in the GET
 * request's JSON body — a form browsers categorically refuse to send.
 * The console performs the bodyless default-page read and narrows
 * client-side; when the backend reports more pages the honest
 * "deeper pagination" notice reproduces the canonical API form.
 *
 * Capability gating is permission-aware: when `webhooks:read` is not
 * granted the authenticated reads are never fired — an inline notice
 * names the capability verbatim and states the verbatim backend
 * rejection (`capability-denied`) instead of hiding it.
 */

import { useMemo, useState } from "react";
import type {
  AdcosEnvelope,
  ListResponse,
  WebhookEndpoint,
} from "@/lib/api/types";
import { useSession } from "@/lib/session";
import {
  ApiRequestPanel,
  DataTable,
  FilterBar,
  RefreshIcon,
  type Column,
} from "@/components/ui";
import { WEBHOOK_EVENT_TYPES } from "./webhook-event-types";
import { useDevelopersRead } from "./use-developers-read";
import { WebhookDetailDrawer } from "./webhook-detail-drawer";
import { WebhookRegisterDrawer } from "./webhook-register-drawer";

export function WebhookEndpointsSection({
  canRead,
  canWrite,
  registerOpen,
  onRegisterOpenChange,
}: {
  /** Is `webhooks:read` granted? (gates the list/detail reads) */
  canRead: boolean;
  /** Is `webhooks:write` granted? (gates registration) */
  canWrite: boolean;
  /** The register drawer's open state (owned by the workspace for the palette command). */
  registerOpen: boolean;
  onRegisterOpenChange: (open: boolean) => void;
}) {
  const { client } = useSession();
  const [search, setSearch] = useState("");
  const [eventTypeFilter, setEventTypeFilter] = useState("");
  const [detailId, setDetailId] = useState<string | null>(null);

  // the BODYLESS list read (browser-compatible form of the frozen
  // list discipline); suspended unless webhooks:read is granted
  const read = useDevelopersRead<AdcosEnvelope<ListResponse<WebhookEndpoint>>>(
    canRead ? () => client.listWebhookEndpoints() : null,
    [client, canRead],
  );
  const chain: ListResponse<WebhookEndpoint> | null = read.data?.data ?? null;

  // client-side narrowing over the fetched default page
  const rows = useMemo(() => {
    const items = chain?.items ?? [];
    const needle = search.trim().toLowerCase();
    return items.filter((endpoint) => {
      if (
        needle &&
        !endpoint.id.toLowerCase().includes(needle) &&
        !endpoint.url.toLowerCase().includes(needle) &&
        !endpoint.key_id.toLowerCase().includes(needle)
      ) {
        return false;
      }
      if (
        eventTypeFilter &&
        !endpoint.event_types.includes(eventTypeFilter)
      ) {
        return false;
      }
      return true;
    });
  }, [chain, search, eventTypeFilter]);

  const fetchedCount = chain?.items.length ?? 0;
  const clientNarrowing = search.trim() !== "" || eventTypeFilter !== "";

  const columns: Column<WebhookEndpoint>[] = [
    {
      key: "endpoint",
      header: "Endpoint",
      sortable: true,
      accessor: (row) => row.id,
      render: (row) => (
        <span
          className="block max-w-[16rem] truncate font-mono text-xs text-ink"
          title={row.id}
        >
          {row.id}
        </span>
      ),
    },
    {
      key: "url",
      header: "URL",
      sortable: true,
      accessor: (row) => row.url,
      render: (row) => (
        <span
          className="block max-w-[18rem] truncate font-mono text-xs text-ink-muted"
          title={row.url}
        >
          {row.url}
        </span>
      ),
    },
    {
      key: "event_types",
      header: "Event types",
      sortable: true,
      accessor: (row) => row.event_types.length,
      render: (row) => (
        <span
          className="block max-w-[18rem] truncate font-mono text-xs text-ink-muted"
          title={row.event_types.join(", ")}
        >
          {row.event_types.length > 0 ? row.event_types.join(", ") : "—"}
        </span>
      ),
    },
    {
      key: "key_id",
      header: "Key id",
      sortable: true,
      accessor: (row) => row.key_id,
      render: (row) => (
        <span
          className="block max-w-[12rem] truncate font-mono text-xs text-ink-muted"
          title={row.key_id}
        >
          {row.key_id}
        </span>
      ),
    },
    {
      key: "created_at",
      header: "Created",
      sortable: true,
      accessor: (row) => row.created_at,
      render: (row) => (
        <span className="whitespace-nowrap font-mono text-xs text-ink-muted">
          {row.created_at}
        </span>
      ),
    },
  ];

  return (
    <section
      data-testid="webhook-endpoints-section"
      className="flex flex-col gap-3 rounded-md border border-line bg-surface p-4"
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-ink">Webhook endpoints</h2>
          <p className="mt-0.5 text-sm text-ink-muted">
            The application&apos;s registered endpoints and their delivery
            journals — every row is backend truth from{" "}
            <span className="font-mono text-2xs">
              GET /api/2.0/webhook-endpoints
            </span>
            . Select a row to inspect the endpoint record and its deliveries.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            aria-label="Refresh webhook endpoints"
            onClick={() => read.refresh()}
            disabled={!canRead}
            className="inline-flex h-8 items-center gap-1.5 rounded-md border border-line-strong bg-raised px-3 text-sm text-ink transition-colors hover:bg-surface disabled:cursor-not-allowed disabled:opacity-60"
          >
            <RefreshIcon size={14} />
            Refresh
          </button>
          <button
            type="button"
            onClick={() => onRegisterOpenChange(true)}
            data-testid="webhook-register-open"
            title={
              canWrite
                ? "Register a webhook endpoint"
                : "webhooks:write is not granted — the form explains what is missing"
            }
            className="inline-flex h-8 items-center rounded-md bg-accent px-3 text-sm text-accent-ink transition-colors hover:bg-accent-strong"
          >
            Register endpoint
          </button>
        </div>
      </header>

      {!canRead ? (
        <p
          data-testid="webhooks-read-denied"
          className="rounded-md border border-dashed border-danger/60 bg-danger/5 px-3 py-2 text-xs leading-relaxed text-ink-muted"
        >
          This application lacks{" "}
          <span className="font-mono text-danger">webhooks:read</span>{" "}
          (required by the operation registry for the endpoint list, endpoint
          detail and delivery journal). The reads are suspended — the backend
          would reject them with{" "}
          <span className="font-mono text-ink">capability-denied</span> naming
          that capability verbatim.
        </p>
      ) : (
        <>
          <FilterBar
            search={{
              value: search,
              onChange: setSearch,
              placeholder: "Search id, url or key id…",
            }}
            filters={[
              {
                id: "event-type",
                label: "Event type",
                value: eventTypeFilter,
                options: [
                  { value: "", label: "All event types" },
                  ...WEBHOOK_EVENT_TYPES.map((eventType) => ({
                    value: eventType,
                    label: eventType,
                  })),
                ],
                onChange: setEventTypeFilter,
              },
            ]}
          />

          <DataTable
            rows={rows}
            columns={columns}
            getRowKey={(row) => row.id}
            loading={read.loading && !chain}
            error={read.error}
            onRetry={read.refresh}
            emptyTitle={
              clientNarrowing
                ? "No endpoints match the current filters"
                : "No webhook endpoints yet"
            }
            emptyDescription={
              clientNarrowing ? (
                "Adjust the search text or the event-type filter."
              ) : (
                "Register an endpoint to receive signed lifecycle events — the form offers exactly the backend's frozen event-type vocabulary (checkboxes, no free text)."
              )
            }
            onRowActivate={(row) => setDetailId(row.id)}
            rowAriaLabel={(row) => `Webhook endpoint ${row.id}, ${row.url}`}
          />

          <p className="text-xs text-ink-faint" data-testid="endpoints-count">
            {read.loaded
              ? clientNarrowing
                ? `${rows.length} of ${fetchedCount} fetched endpoints shown`
                : `${fetchedCount} webhook endpoints`
              : "loading…"}
          </p>

          {chain?.has_more ? (
            <div
              data-testid="endpoints-deeper-pagination-notice"
              className="rounded-md border border-dashed border-warning/60 bg-warning/5 px-3 py-2"
            >
              <p className="text-sm text-ink-muted">
                The backend reports more pages than shown. List pagination
                rides the developer API&apos;s GET request JSON body — a form
                browsers cannot send (fetch forbids GET bodies), so the console
                shows the bodyless default page. Page through the API directly:
              </p>
              <div className="mt-2">
                <ApiRequestPanel
                  variant="compact"
                  method="GET"
                  path="/api/2.0/webhook-endpoints"
                  body={{
                    limit: 20,
                    cursor: chain.next_cursor || "<next_cursor>",
                  }}
                />
              </div>
            </div>
          ) : null}
        </>
      )}

      {registerOpen ? (
        <WebhookRegisterDrawer
          canWrite={canWrite}
          onClose={() => onRegisterOpenChange(false)}
          onRegistered={() => read.refresh()}
        />
      ) : null}

      {detailId ? (
        <WebhookDetailDrawer
          endpointId={detailId}
          onClose={() => setDetailId(null)}
        />
      ) : null}
    </section>
  );
}
