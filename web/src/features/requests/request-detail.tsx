"use client";

/**
 * RequestDetailDrawer — the per-request inspection drawer: the request
 * exactly as it was sent (headers reconstructed from the matched
 * registry operation + the session, the credential ALWAYS masked — the
 * recorder never captures request headers precisely so no secret can
 * leak), the request body, the response headers and the captured
 * response body (truncated, expandable), the copyable CURL
 * reproduction, and the registry operation that produced the request
 * ("which API operation produced or changed this object").
 */

import { useState } from "react";
import Link from "next/link";
import {
  ApiRequestPanel,
  CodeBlock,
  Drawer,
  JsonViewer,
} from "@/components/ui";
import type { LoggedRequest } from "./request-log";
import { MAX_RESPONSE_BODY_CHARS } from "./recorder";
import { matchOperationForPath, maskedRequestHeaders } from "@/features/api-explorer/executor";

/** The captured-body preview length before the expand toggle kicks in. */
const BODY_PREVIEW_CHARS = 800;

/**
 * The headers a logged request carried — reconstructed honestly:
 * - the matched registry operation decides the boundary header set
 *   (platform surfaces carry none; mutations carry the idempotency key);
 * - the application id is the session's ACTUAL value;
 * - the credential is ALWAYS the masked placeholder;
 * - the idempotency key is NOT recorded (secrets discipline), so the
 *   reproduction shows the explicit placeholder instead of guessing.
 */
function requestHeadersFor(
  entry: LoggedRequest,
  applicationId: string | null,
): { name: string; value: string }[] {
  const matched = matchOperationForPath(entry.method, entry.path);
  const record = matched?.record ?? null;
  const headers: { name: string; value: string }[] = record
    ? maskedRequestHeaders({
        platform: record.platform,
        mutation: record.mutation,
        applicationId,
        idempotencyKey: record.mutation ? "<idempotency-key>" : null,
      })
    : [];
  if (entry.body !== undefined && entry.body !== null) {
    headers.push({ name: "Content-Type", value: "application/json" });
  }
  return headers;
}

function CapturedBody({ body }: { body: string }) {
  const [expanded, setExpanded] = useState(false);
  const clipped = !expanded && body.length > BODY_PREVIEW_CHARS;
  const visible = expanded ? body : body.slice(0, BODY_PREVIEW_CHARS);
  return (
    <div className="flex flex-col gap-1.5">
      <p className="text-2xs uppercase tracking-wide text-ink-faint">
        Captured response body
      </p>
      <CodeBlock code={clipped ? `${visible}\n…` : visible} filename="response" />
      {clipped ? (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          data-testid="expand-captured-body"
          className="inline-flex h-7 w-fit items-center rounded-md border border-line-strong bg-raised px-2.5 text-xs text-ink transition-colors hover:bg-surface"
        >
          Show the full captured body
        </button>
      ) : null}
      {body.length > MAX_RESPONSE_BODY_CHARS ? (
        <p className="text-2xs text-ink-faint">
          The capture itself is truncated at the recorder&apos;s limit ({MAX_RESPONSE_BODY_CHARS} chars)
          — the full body is on the wire, not in memory.
        </p>
      ) : null}
    </div>
  );
}

export function RequestDetailDrawer({
  entry,
  open,
  onOpenChange,
  applicationId,
}: {
  entry: LoggedRequest | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  applicationId: string | null;
}) {
  const matched = entry ? matchOperationForPath(entry.method, entry.path) : null;
  const record = matched?.record ?? null;
  const headers = entry ? requestHeadersFor(entry, applicationId) : [];
  const failed = entry !== null && (entry.status < 200 || entry.status >= 400);

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title={entry ? `${entry.method} ${entry.path}` : "Request detail"}
      description={
        entry
          ? `Captured request #${entry.sequence}${entry.requestId ? ` · request_id ${entry.requestId}` : ""}`
          : undefined
      }
    >
      {entry ? (
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center rounded border px-2 py-px font-mono text-xs ${
                failed
                  ? "border-danger/60 text-danger"
                  : "border-positive/60 text-positive"
              }`}
              data-testid="request-detail-status"
            >
              {`HTTP ${entry.status}`}
            </span>
            {typeof entry.durationMs === "number" ? (
              <span className="font-mono text-2xs text-ink-faint">
                {`${entry.durationMs} ms`}
              </span>
            ) : null}
            <span className="font-mono text-2xs text-ink-faint">{entry.at}</span>
            {entry.reason ? (
              <span className="rounded border border-danger/60 px-1.5 py-px font-mono text-2xs text-danger">
                {entry.reason}
              </span>
            ) : null}
          </div>

          <div className="flex flex-col gap-1.5">
            <p className="text-2xs uppercase tracking-wide text-ink-faint">Request headers</p>
            <dl className="flex flex-col gap-1 rounded-md border border-line bg-raised px-2.5 py-2">
              {headers.length > 0 ? (
                headers.map((header) => (
                  <div
                    key={header.name}
                    className="grid grid-cols-[minmax(9rem,auto)_1fr] gap-x-3"
                  >
                    <dt
                      className="truncate font-mono text-2xs text-ink-faint"
                      title={header.name}
                    >
                      {header.name}
                    </dt>
                    <dd className="break-all font-mono text-xs text-ink">
                      {header.value}
                    </dd>
                  </div>
                ))
              ) : (
                <div className="text-xs text-ink-muted">
                  Reconstructed headers unavailable — the path is outside the
                  coverage registry.
                </div>
              )}
            </dl>
            <p className="text-2xs text-ink-faint">
              Reconstructed from the matched operation + session: the credential
              is always masked and the idempotency key is never recorded.
            </p>
          </div>

          <div className="flex flex-col gap-1.5">
            <p className="text-2xs uppercase tracking-wide text-ink-faint">Request body</p>
            {entry.body !== undefined && entry.body !== null ? (
              typeof entry.body === "object" ? (
                <JsonViewer value={entry.body} name="body" defaultExpandedDepth={1} />
              ) : (
                <CodeBlock code={String(entry.body)} filename="body" />
              )
            ) : (
              <p className="text-xs text-ink-muted">No request body was sent.</p>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <p className="text-2xs uppercase tracking-wide text-ink-faint">Response headers</p>
            {entry.responseHeaders && entry.responseHeaders.length > 0 ? (
              <dl className="flex flex-col gap-1 rounded-md border border-line bg-raised px-2.5 py-2">
                {entry.responseHeaders.map((header) => (
                  <div
                    key={header.name}
                    className="grid grid-cols-[minmax(9rem,auto)_1fr] gap-x-3"
                  >
                    <dt
                      className="truncate font-mono text-2xs text-ink-faint"
                      title={header.name}
                    >
                      {header.name}
                    </dt>
                    <dd className="break-all font-mono text-xs text-ink">
                      {header.value}
                    </dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p className="text-xs text-ink-muted" data-testid="drawer-headers-not-captured">
                Not captured (the recorder enriches requests made while an
                inspector-capable page is mounted). Nothing is fabricated.
              </p>
            )}
          </div>

          {entry.responseBody ? <CapturedBody body={entry.responseBody} /> : null}

          <div className="flex flex-col gap-1.5">
            <p className="text-2xs uppercase tracking-wide text-ink-faint">
              Reproduce this request (curl)
            </p>
            <ApiRequestPanel
              method={entry.method}
              path={entry.path}
              headers={headers}
              body={entry.body}
              description="The credential and the idempotency key are masked placeholders — substitute your own to replay outside the console."
            />
          </div>

          <div className="flex flex-col gap-1.5 border-t border-line pt-2">
            <p className="text-2xs uppercase tracking-wide text-ink-faint">
              API operation
            </p>
            {record ? (
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded border border-line-strong px-1.5 py-px font-mono text-2xs text-ink-muted">
                  {record.operation}
                </span>
                <Link
                  href={`/developers/explorer?operation=${record.operation}`}
                  className="text-sm text-accent hover:underline"
                >
                  View in the API Explorer
                </Link>
              </div>
            ) : (
              <p className="text-xs text-ink-muted">
                The path is outside the coverage registry — no operation is
                attributed (never a guess).
              </p>
            )}
          </div>
        </div>
      ) : null}
    </Drawer>
  );
}
