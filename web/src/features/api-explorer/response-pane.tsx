"use client";

/**
 * ResponsePane — what the boundary actually answered for one execution.
 *
 * The status chip, the recorder-captured response headers (X-ADCOS-*,
 * rate-limit, content-type), the parsed body in the JsonViewer, the
 * envelope surface (request id, api version, environment, rate limit,
 * the idempotent-replay marker), and the CURL reproduction (copyable;
 * credential masked as `<your-credential>` — never the real value).
 *
 * Errors render through the shared ErrorState: the backend's reason
 * code VERBATIM, the message verbatim, retryable / retry_after when
 * present — never a generic replacement. The captured response body
 * text (what the recorder read off the wire) is shown alongside, with
 * the honest truncation marker when the capture was cut at the limit.
 */

import { useState } from "react";
import { MAX_RESPONSE_BODY_CHARS } from "@/features/requests/recorder";
import {
  ApiRequestPanel,
  CodeBlock,
  ErrorState,
  JsonViewer,
} from "@/components/ui";
import { maskedRequestHeaders } from "./executor";
import type { ExplorerExecution } from "./explorer-history";

/** The captured-body preview length before the expand toggle kicks in. */
const BODY_PREVIEW_CHARS = 800;

/** The envelope's request_id member, when the payload carries one. */
function envelopeRequestId(payload: unknown): string {
  if (typeof payload !== "object" || payload === null) return "";
  const value = (payload as Record<string, unknown>).request_id;
  return typeof value === "string" ? value : "";
}

function StatusChip({ status }: { status: number | null }) {
  if (status === null) {
    return (
      <span
        data-testid="response-status"
        className="inline-flex items-center rounded border border-danger/60 px-2 py-px font-mono text-xs text-danger"
      >
        NOT SENT — invalid request
      </span>
    );
  }
  const success = status >= 200 && status < 300;
  return (
    <span
      data-testid="response-status"
      className={`inline-flex items-center rounded border px-2 py-px font-mono text-xs ${
        success
          ? "border-positive/60 text-positive"
          : "border-danger/60 text-danger"
      }`}
    >
      {`HTTP ${status}`}
    </span>
  );
}

function EnvelopeSurface({ payload }: { payload: unknown }) {
  if (typeof payload !== "object" || payload === null) return null;
  const envelope = payload as Record<string, unknown>;
  const rows: { label: string; value: string }[] = [];
  const push = (label: string, value: unknown): void => {
    if (typeof value === "string" && value.length > 0) {
      rows.push({ label, value });
    }
  };
  push("X-ADCOS-Request-Id", envelope.request_id);
  push("X-ADCOS-API-Version", envelope.api_version);
  push("X-ADCOS-Environment", envelope.environment);
  const rate = envelope.rate_limit as Record<string, unknown> | undefined;
  if (typeof rate === "object" && rate !== null) {
    rows.push({
      label: "rate_limit",
      value: `limit ${String(rate.limit ?? "—")} · remaining ${String(rate.remaining ?? "—")} · reset_at ${String(rate.reset_at ?? "—")}`,
    });
  }
  const idempotency = envelope.idempotency as Record<string, unknown> | undefined;
  if (typeof idempotency === "object" && idempotency !== null) {
    rows.push({
      label: "idempotency",
      value: `key ${String(idempotency.key ?? "—")} · ${idempotency.replayed === true ? "REPLAYED (idempotent replay marker)" : "first execution"}`,
    });
  }
  if (rows.length === 0) return null;
  return (
    <div className="flex flex-col gap-1.5">
      <p className="text-2xs uppercase tracking-wide text-ink-faint">Envelope surface</p>
      <dl className="flex flex-col gap-1 rounded-md border border-line bg-raised px-2.5 py-2">
        {rows.map((row) => (
          <div key={row.label} className="grid grid-cols-[minmax(11rem,auto)_1fr] gap-x-3">
            <dt className="truncate font-mono text-2xs text-ink-faint" title={row.label}>
              {row.label}
            </dt>
            <dd className="break-all font-mono text-xs text-ink">{row.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function CapturedBody({ body }: { body: string }) {
  const [expanded, setExpanded] = useState(false);
  const truncated = body.length > MAX_RESPONSE_BODY_CHARS;
  const visible = expanded ? body : body.slice(0, BODY_PREVIEW_CHARS);
  const clipped = !expanded && body.length > BODY_PREVIEW_CHARS;
  return (
    <div className="flex flex-col gap-1.5">
      <p className="text-2xs uppercase tracking-wide text-ink-faint">
        Captured response body
      </p>
      <CodeBlock code={clipped ? `${visible}\n…` : visible} filename="response" />
      {clipped || truncated ? (
        <div className="flex flex-wrap items-center gap-2">
          {clipped ? (
            <button
              type="button"
              onClick={() => setExpanded(true)}
              data-testid="expand-captured-body"
              className="inline-flex h-7 items-center rounded-md border border-line-strong bg-raised px-2.5 text-xs text-ink transition-colors hover:bg-surface"
            >
              Show the full captured body
            </button>
          ) : null}
          {truncated ? (
            <p className="text-2xs text-ink-faint">
              The capture itself is truncated at {MAX_RESPONSE_BODY_CHARS} chars
              (recorder limit) — the full body is on the wire, not in memory.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function ResponsePane({
  execution,
  applicationId,
}: {
  execution: ExplorerExecution;
  applicationId: string | null;
}) {
  const { request, outcome, coverage } = execution;
  const status =
    outcome.kind === "success"
      ? outcome.status
      : outcome.kind === "error"
        ? outcome.error.status
        : null;
  const error = outcome.kind === "error" ? outcome.error : null;
  const requestId =
    outcome.kind === "error"
      ? outcome.error.requestId
      : envelopeRequestId(outcome.kind === "success" ? outcome.payload : null);

  const curlHeaders = maskedRequestHeaders({
    platform: coverage.platform,
    mutation: coverage.mutation,
    applicationId,
    idempotencyKey: request.idempotencyKey ?? null,
  });

  return (
    <section
      aria-label="Execution response"
      className="flex flex-col gap-4 rounded-md border border-line bg-surface p-4"
    >
      <div className="flex flex-wrap items-center gap-2">
        <StatusChip status={status} />
        <span className="min-w-0 break-all font-mono text-xs text-ink">
          {`${request.method} ${request.path}`}
        </span>
        {typeof execution.durationMs === "number" ? (
          <span className="font-mono text-2xs text-ink-faint">
            {`${execution.durationMs} ms`}
          </span>
        ) : null}
        <span className="ml-auto font-mono text-2xs text-ink-faint">
          {execution.at}
        </span>
      </div>

      {requestId ? (
        <p className="font-mono text-2xs text-ink-faint">request_id: {requestId}</p>
      ) : null}

      <div className="flex flex-col gap-1.5">
        <p className="text-2xs uppercase tracking-wide text-ink-faint">Response headers</p>
        {execution.responseHeaders && execution.responseHeaders.length > 0 ? (
          <dl className="flex flex-col gap-1 rounded-md border border-line bg-raised px-2.5 py-2">
            {execution.responseHeaders.map((header) => (
              <div
                key={header.name}
                className="grid grid-cols-[minmax(11rem,auto)_1fr] gap-x-3"
              >
                <dt
                  className="truncate font-mono text-2xs text-ink-faint"
                  title={header.name}
                >
                  {header.name}
                </dt>
                <dd className="break-all font-mono text-xs text-ink">{header.value}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="text-xs text-ink-muted" data-testid="response-headers-not-captured">
            Not captured for this execution (the recorder enriches requests made
            while an inspector-capable page is mounted). Nothing is fabricated.
          </p>
        )}
      </div>

      {outcome.kind === "success" ? (
        <EnvelopeSurface payload={outcome.payload} />
      ) : null}

      {outcome.kind === "error" ? (
        <div className="rounded-md border border-line" data-testid="explorer-error-state">
          <ErrorState error={outcome.error} />
        </div>
      ) : (
        <div className="flex flex-col gap-1.5">
          <p className="text-2xs uppercase tracking-wide text-ink-faint">Response body</p>
          {outcome.kind === "success" ? (
            <JsonViewer value={outcome.payload} name="response" defaultExpandedDepth={1} />
          ) : null}
        </div>
      )}

      {execution.responseBody ? <CapturedBody body={execution.responseBody} /> : null}

      <div className="flex flex-col gap-1.5">
        <p className="text-2xs uppercase tracking-wide text-ink-faint">
          Reproduce this request (curl)
        </p>
        <ApiRequestPanel
          method={request.method}
          path={request.path}
          headers={curlHeaders}
          body={request.body}
          description="The credential is masked — substitute your own to replay outside the console."
        />
      </div>
    </section>
  );
}
