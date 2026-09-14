"use client";

/**
 * CapturedErrorCard — one failed request's full anatomy (the spec's
 * Errors contract): what happened, why, the affected resource, the next
 * action, and the reproducible API form.
 *
 * Honesty rules:
 * - the reason code renders VERBATIM in a mono chip (never replaced);
 * - guidance comes from the KNOWN reason-code dictionary (the boundary
 *   reason first, the backend-adapted canonical reason when the boundary
 *   code is outside it) with an honest generic fallback for unknown
 *   codes (`reasonGuidanceForCodes`);
 * - synthesized client-side codes (backend-unreachable) are labeled as
 *   such — never presented as backend reasons;
 * - the curl reproduction masks the credential ALWAYS (the real value
 *   never leaves the session store);
 * - fields the recorder did not capture render as honest "not captured"
 *   notes, never as fabricated values;
 * - the Retry button re-issues the request through the typed client (via
 *   the coverage-registry executor) — only when the backend marked the
 *   error retryable (or the request never reached the runtime).
 */

import { useMemo, useState } from "react";
import type { LoggedRequest } from "@/features/requests/request-log";
import {
  DESTRUCTIVE_OPERATIONS,
  executeOperation,
  matchOperationForPath,
  maskedRequestHeaders,
  type ExecuteOutcome,
} from "@/features/api-explorer/executor";
import { ApiRequestPanel, RefreshIcon } from "@/components/ui";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";
import { parseCapturedError } from "./captured-response";
import {
  isSynthesizedClientCode,
  reasonGuidanceForCodes,
} from "./reason-guidance";

/** Stable test ids for the workbench suite. */
export const CAPTURED_ERROR_TEST_IDS = {
  root: "captured-error",
  reason: "workbench-reason",
  retry: "workbench-retry",
  curl: "workbench-curl",
} as const;

function StatusChip({ status }: { status: number }) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded border px-1.5 py-px font-mono text-2xs",
        status === 0
          ? "border-danger/60 bg-danger/5 text-danger"
          : "border-danger/60 text-danger",
      )}
    >
      {status === 0 ? "unreachable" : `HTTP ${status}`}
    </span>
  );
}

function FieldRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-[9rem_1fr] items-baseline gap-x-4 gap-y-1">
      <dt className="font-mono text-2xs text-ink-faint">{label}</dt>
      <dd className="min-w-0 break-all text-sm text-ink">{children}</dd>
    </div>
  );
}

export function CapturedErrorCard({
  entry,
  expanded,
  onToggle,
  onPin,
}: {
  entry: LoggedRequest;
  expanded: boolean;
  onToggle: () => void;
  /** Pins this card expanded (used when a retry's outcome must stay visible). */
  onPin?: () => void;
}) {
  const { client, application } = useSession();
  const details = useMemo(() => parseCapturedError(entry), [entry]);
  // the guidance follows the error's OWN codes — the boundary reason
  // first, the backend-adapted canonical reason when the boundary code is
  // outside the KNOWN dictionary (both codes render verbatim regardless)
  const guidance = reasonGuidanceForCodes(
    entry.reason ?? "",
    details.canonicalReason,
  );

  const match = useMemo(
    () => matchOperationForPath(entry.method, entry.path),
    [entry.method, entry.path],
  );

  const [retryState, setRetryState] = useState<{
    phase: "idle" | "running" | "done";
    outcome: ExecuteOutcome | null;
  }>({ phase: "idle", outcome: null });

  const retryable = details.retryable === true || entry.status === 0;
  const canRetry = retryable && match !== null;

  async function retry(): Promise<void> {
    if (match === null) return;
    // pin this card expanded — a re-issued failure lands as a NEW captured
    // error at the top of the list, and the outcome must stay visible HERE
    onPin?.();
    setRetryState({ phase: "running", outcome: null });
    const outcome = await executeOperation(client, {
      operation: match.record.operation,
      pathParams: match.params,
      body: entry.body,
    });
    setRetryState({ phase: "done", outcome });
  }

  const mutation = match?.record.mutation ?? false;
  const platform = match?.record.platform ?? false;
  const reproductionHeaders = maskedRequestHeaders({
    platform,
    mutation,
    applicationId: application?.application_id ?? null,
    idempotencyKey: mutation ? "<fresh-idempotency-key>" : null,
  });

  return (
    <li
      data-testid={CAPTURED_ERROR_TEST_IDS.root}
      data-sequence={entry.sequence}
      className={cn(
        "rounded-md border bg-surface",
        expanded ? "border-line-strong" : "border-line",
      )}
      aria-current={expanded ? "true" : undefined}
    >
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="flex w-full flex-wrap items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-raised/40"
      >
        <span className="font-mono text-2xs text-ink-faint">
          #{entry.sequence}
        </span>
        <StatusChip status={entry.status} />
        {entry.reason ? (
          <code
            data-testid={CAPTURED_ERROR_TEST_IDS.reason}
            className="rounded border border-line bg-raised px-1.5 py-px font-mono text-2xs text-ink-muted"
          >
            {entry.reason}
          </code>
        ) : (
          <span className="font-mono text-2xs text-ink-faint">
            no reason captured
          </span>
        )}
        <span
          className="min-w-0 flex-1 truncate font-mono text-xs text-ink"
          title={`${entry.method} ${entry.path}`}
        >
          {entry.method} {entry.path}
        </span>
        <span className="whitespace-nowrap font-mono text-2xs text-ink-faint">
          {entry.at}
        </span>
      </button>

      {expanded ? (
        <div className="flex flex-col gap-4 border-t border-line px-3 py-3">
          {/* the anatomy ------------------------------------------------ */}
          <dl className="flex flex-col gap-2">
            <FieldRow label="what happened">
              {details.message ? (
                <span className="text-ink">{details.message}</span>
              ) : entry.status === 0 ? (
                <span className="text-ink-muted">
                  The request never reached the ADCOS runtime (network
                  failure) — no backend response to describe.
                </span>
              ) : (
                <span className="text-ink-faint">
                  no message captured — the recorder did not capture this
                  response body (the request was made before an
                  inspector-capable page mounted)
                </span>
              )}
            </FieldRow>

            <FieldRow label="why">
              <span className="flex flex-wrap items-center gap-2">
                {entry.reason ? (
                  <code
                    data-testid={CAPTURED_ERROR_TEST_IDS.reason}
                    className="rounded border border-line bg-raised px-1.5 py-px font-mono text-xs text-ink"
                  >
                    {entry.reason}
                  </code>
                ) : (
                  <span className="text-ink-faint">no reason code captured</span>
                )}
                {details.canonicalReason ? (
                  <span className="font-mono text-2xs text-ink-faint">
                    canonical_reason: {details.canonicalReason}
                  </span>
                ) : null}
                {entry.reason && isSynthesizedClientCode(entry.reason) ? (
                  <span className="rounded border border-dashed border-line px-1.5 py-px font-mono text-2xs text-ink-faint">
                    synthesized client-side — not a backend reason code
                  </span>
                ) : null}
              </span>
              <span className="mt-1 flex flex-col gap-0.5">
                <span className="text-sm font-medium text-ink">
                  {guidance.title}
                  {guidance.known ? null : (
                    <span className="ml-2 font-mono text-2xs font-normal text-ink-faint">
                      (not in the known-code dictionary)
                    </span>
                  )}
                </span>
                <span className="text-sm text-ink-muted">
                  <span className="text-ink-faint">Next:</span>{" "}
                  {guidance.nextAction}
                </span>
              </span>
            </FieldRow>

            <FieldRow label="affected resource">
              <span className="flex flex-col gap-0.5">
                {details.resourceId ? (
                  <span className="font-mono text-xs break-all text-ink">
                    resource_id: {details.resourceId}
                  </span>
                ) : null}
                <span className="font-mono text-xs break-all text-ink">
                  {entry.method} {entry.path}
                  {entry.body !== undefined ? " (with request body)" : ""}
                </span>
                {details.requestId || entry.requestId ? (
                  <span className="font-mono text-2xs break-all text-ink-faint">
                    request_id: {details.requestId || entry.requestId}
                  </span>
                ) : null}
              </span>
            </FieldRow>

            <FieldRow label="when">
              <span className="font-mono text-xs text-ink-muted">
                {entry.at}
                {typeof entry.durationMs === "number"
                  ? ` · ${entry.durationMs} ms`
                  : ""}
              </span>
            </FieldRow>

            <FieldRow label="next action">
              <span className="flex flex-col gap-2">
                {retryable ? (
                  match ? (
                    <span className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        data-testid={CAPTURED_ERROR_TEST_IDS.retry}
                        onClick={() => void retry()}
                        disabled={retryState.phase === "running"}
                        className="inline-flex h-8 items-center gap-1.5 rounded-md border border-line-strong bg-raised px-3 text-sm text-ink transition-colors hover:bg-surface disabled:opacity-50"
                      >
                        <RefreshIcon size={14} />
                        {retryState.phase === "running"
                          ? "Re-issuing…"
                          : "Retry request"}
                      </button>
                      <span className="text-xs text-ink-faint">
                        re-issued through the typed client
                        {mutation ? " with a fresh idempotency key" : ""}
                        {DESTRUCTIVE_OPERATIONS.has(match.record.operation)
                          ? " (this operation is destructive — the original request failed before any effect)"
                          : ""}
                      </span>
                    </span>
                  ) : (
                    <span className="text-sm text-ink-muted">
                      The backend marked this error retryable, but the captured
                      path resolves to no registry operation — the console
                      cannot re-issue it. Reproduce it manually below.
                    </span>
                  )
                ) : (
                  <span className="text-sm text-ink-muted">
                    {details.retryable === null
                      ? "Retryability was not captured (no response body). "
                      : "The backend marked this error NOT retryable. "}
                    Reproduce the request below against the API to investigate
                    outside the console.
                  </span>
                )}

                {retryState.phase === "done" && retryState.outcome ? (
                  retryState.outcome.kind === "success" ? (
                    <span className="rounded border border-positive/40 bg-positive/5 px-2 py-1 text-xs text-ink-muted">
                      Re-issued — HTTP {retryState.outcome.status}: the request
                      succeeded. The captured failure above stays for
                      reference.
                    </span>
                  ) : retryState.outcome.kind === "error" ? (
                    <span className="rounded border border-danger/40 bg-danger/5 px-2 py-1 text-xs text-ink-muted">
                      Re-issued — failed again with reason{" "}
                      <code className="font-mono text-ink">
                        {retryState.outcome.error.reason}
                      </code>
                      : {retryState.outcome.error.message}
                    </span>
                  ) : (
                    <span className="rounded border border-line px-2 py-1 text-xs text-ink-muted">
                      Re-issue rejected locally:{" "}
                      {retryState.outcome.message}
                    </span>
                  )
                ) : null}
              </span>
            </FieldRow>
          </dl>

          {/* the reproducible API form ---------------------------------- */}
          <div className="flex flex-col gap-2" data-testid={CAPTURED_ERROR_TEST_IDS.curl}>
            <p className="text-xs text-ink-faint">
              Reproducible API form — copyable, credential masked (substitute
              your own application id and credential).
            </p>
            <ApiRequestPanel
              variant="full"
              method={entry.method}
              path={entry.path}
              headers={reproductionHeaders}
              body={entry.body}
              description={
                match
                  ? `${match.record.operation} — ${match.record.method} ${match.record.path}`
                  : undefined
              }
            />
          </div>

          {/* the captured response -------------------------------------- */}
          {details.rawBody ? (
            <div className="flex flex-col gap-1.5">
              <p className="text-xs text-ink-faint">
                Captured response body (as returned, truncated by the
                recorder) — the backend&apos;s own message, verbatim:
              </p>
              <pre className="max-h-64 overflow-auto whitespace-pre rounded-md border border-line bg-raised p-3 font-mono text-2xs leading-relaxed text-ink">
                <code>{details.rawBody}</code>
              </pre>
            </div>
          ) : (
            <p className="text-xs text-ink-faint">
              No response body was captured for this request — the request
              predated the recorder (nothing is fabricated here).
            </p>
          )}
        </div>
      ) : null}
    </li>
  );
}
