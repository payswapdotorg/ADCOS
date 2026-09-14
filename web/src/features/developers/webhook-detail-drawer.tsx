"use client";

/**
 * WebhookDetailDrawer — secondary inspection of one webhook endpoint
 * (work order deliverable #4, detail + deliveries): the endpoint
 * record re-read through the typed client (GET /api/2.0/webhook-
 * endpoints/{id} — its request is reproduced in the drawer), the raw
 * record JSON, and the endpoint's delivery journal (GET
 * /api/2.0/webhook-endpoints/{id}/deliveries) as a data table.
 *
 * Every state value renders VERBATIM: the delivery journal's status
 * column shows `last_status` exactly as the backend reports it
 * (`delivered` / `failed` / `pending`), the event types are the
 * backend's frozen vocabulary, and failures render through
 * LinkedErrorState with the reason code verbatim.
 */

import type {
  AdcosEnvelope,
  ListResponse,
  WebhookDelivery,
  WebhookEndpoint,
} from "@/lib/api/types";
import { useSession } from "@/lib/session";
import { LinkedErrorState } from "@/features/errors/link";
import {
  ApiRequestPanel,
  DataTable,
  Drawer,
  ObjectHeader,
  RefreshIcon,
  Status,
  type Column,
} from "@/components/ui";
import { useDevelopersRead } from "./use-developers-read";

export function WebhookDetailDrawer({
  endpointId,
  onClose,
}: {
  endpointId: string;
  onClose: () => void;
}) {
  const { client } = useSession();

  const endpointRead = useDevelopersRead<AdcosEnvelope<WebhookEndpoint>>(
    () => client.getWebhookEndpoint(endpointId),
    [client, endpointId],
  );
  const deliveriesRead = useDevelopersRead<
    AdcosEnvelope<ListResponse<WebhookDelivery>>
  >(() => client.listDeliveries(endpointId), [client, endpointId]);

  const endpoint = endpointRead.data?.data ?? null;
  const deliveries = deliveriesRead.data?.data ?? null;

  const deliveryColumns: Column<WebhookDelivery>[] = [
    {
      key: "event_type",
      header: "Event type",
      sortable: true,
      accessor: (row) => row.event_type,
      render: (row) => (
        <span
          className="block max-w-[15rem] truncate font-mono text-xs text-ink"
          title={row.event_type}
        >
          {row.event_type}
        </span>
      ),
    },
    {
      key: "event_id",
      header: "Event id",
      sortable: true,
      accessor: (row) => row.event_id,
      render: (row) => (
        <span
          className="block max-w-[14rem] truncate font-mono text-xs text-ink-muted"
          title={row.event_id}
        >
          {row.event_id}
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      sortable: true,
      accessor: (row) => row.last_status,
      render: (row) => <Status value={row.last_status} size="sm" />,
    },
    {
      key: "attempts",
      header: "Attempts",
      sortable: true,
      align: "right",
      accessor: (row) => row.attempts,
    },
    {
      key: "occurred_at",
      header: "Occurred",
      sortable: true,
      accessor: (row) => row.occurred_at,
      render: (row) => (
        <span className="whitespace-nowrap font-mono text-xs text-ink-muted">
          {row.occurred_at}
        </span>
      ),
    },
    {
      key: "last_attempt_at",
      header: "Last attempt",
      sortable: true,
      accessor: (row) => row.last_attempt_at,
      render: (row) => (
        <span className="whitespace-nowrap font-mono text-xs text-ink-muted">
          {row.last_attempt_at || "—"}
        </span>
      ),
    },
    {
      key: "next_attempt_at",
      header: "Next attempt",
      sortable: true,
      accessor: (row) => row.next_attempt_at,
      render: (row) => (
        <span className="whitespace-nowrap font-mono text-xs text-ink-muted">
          {row.next_attempt_at || "—"}
        </span>
      ),
    },
  ];

  return (
    <Drawer
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title="Webhook endpoint"
      description={`GET /api/2.0/webhook-endpoints/{id} on ${endpointId}`}
    >
      <div className="flex flex-col gap-4">
        {endpoint ? (
          <>
            <ObjectHeader
              kind={endpoint.kind}
              title={endpoint.id}
              copyValue={endpoint.id}
              meta={[
                {
                  label: "url",
                  value: (
                    <span className="break-all font-mono text-xs text-ink">
                      {endpoint.url}
                    </span>
                  ),
                },
                {
                  label: "key_id",
                  value: (
                    <span className="break-all font-mono text-xs text-ink">
                      {endpoint.key_id}
                    </span>
                  ),
                },
                {
                  label: "created_at",
                  value: (
                    <span className="font-mono text-xs text-ink">
                      {endpoint.created_at}
                    </span>
                  ),
                },
                {
                  label: "event_types",
                  value: (
                    <span className="break-all font-mono text-xs text-ink">
                      {endpoint.event_types.join(", ")}
                    </span>
                  ),
                },
                {
                  label: "developer_id",
                  value: (
                    <span className="break-all font-mono text-xs text-ink">
                      {endpoint.developer_id}
                    </span>
                  ),
                },
                {
                  label: "environment",
                  value: (
                    <span className="chip text-ink-muted">
                      {endpoint.environment}
                    </span>
                  ),
                },
                {
                  label: "api_version",
                  value: (
                    <span className="font-mono text-xs text-ink">
                      {endpoint.api_version}
                    </span>
                  ),
                },
              ]}
            />
            <ApiRequestPanel
              variant="compact"
              method="GET"
              path={`/api/2.0/webhook-endpoints/${endpointId}`}
            />
            <p className="text-xs leading-relaxed text-ink-muted">
              The <span className="font-mono text-2xs">key_id</span> identifies
              the platform-side signing key — the signing secret itself is
              derived platform-side and never exposed through the boundary.
            </p>
          </>
        ) : endpointRead.error ? (
          <LinkedErrorState
            error={endpointRead.error}
            onRetry={endpointRead.refresh}
            request={{
              method: "GET",
              path: `/api/2.0/webhook-endpoints/${endpointId}`,
            }}
          />
        ) : (
          <div aria-busy="true" className="flex flex-col gap-2">
            <div className="h-6 w-64 animate-pulse rounded bg-raised" />
            <div className="h-4 w-48 animate-pulse rounded bg-raised" />
            <div className="h-20 w-full animate-pulse rounded bg-raised" />
          </div>
        )}

        <section className="flex flex-col gap-3">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-ink">
              Delivery journal
            </h3>
            <button
              type="button"
              aria-label="Refresh deliveries"
              onClick={() => deliveriesRead.refresh()}
              className="inline-flex h-8 items-center gap-1.5 rounded-md border border-line-strong bg-raised px-3 text-sm text-ink transition-colors hover:bg-surface"
            >
              <RefreshIcon size={14} />
              Refresh
            </button>
          </div>
          <p className="text-xs text-ink-muted">
            The delivery attempts the platform recorded for this endpoint —
            observational only: delivery success or failure never changes
            canonical contract or lease state.
          </p>
          <ApiRequestPanel
            variant="compact"
            method="GET"
            path={`/api/2.0/webhook-endpoints/${endpointId}/deliveries`}
          />
          <DataTable
            rows={deliveries?.items ?? []}
            columns={deliveryColumns}
            getRowKey={(row) => row.id}
            loading={deliveriesRead.loading && !deliveries}
            error={deliveriesRead.error}
            onRetry={deliveriesRead.refresh}
            emptyTitle="No deliveries yet"
            emptyDescription="Events this endpoint subscribes to appear here when the platform emits them — drive a contract lifecycle (intent, offers, activation, leases) to generate events."
            rowAriaLabel={(row) =>
              `Delivery ${row.id}, ${row.event_type}, ${row.last_status}`
            }
          />
          <p className="text-xs text-ink-faint">
            {deliveriesRead.loaded
              ? `${deliveries?.items.length ?? 0} deliveries`
              : "loading…"}
          </p>
          {deliveries?.has_more ? (
            <div
              data-testid="deliveries-deeper-pagination-notice"
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
                  path={`/api/2.0/webhook-endpoints/${endpointId}/deliveries`}
                  body={{
                    limit: 20,
                    cursor: deliveries.next_cursor || "<next_cursor>",
                  }}
                />
              </div>
            </div>
          ) : null}
        </section>
      </div>
    </Drawer>
  );
}
