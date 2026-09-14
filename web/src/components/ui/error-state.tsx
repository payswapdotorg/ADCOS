/**
 * ErrorState — THE canonical error presentation for the console.
 *
 * The backend's reason code is displayed VERBATIM in a mono chip
 * (never replaced by a generic message); `describeError` supplies the
 * presentation guidance around it. When the failed request is known
 * (from the AdcosApiError or the `request` prop) a compact
 * ApiRequestPanel reproduces it, and retry hints travel with the
 * error when the backend sent them.
 */

import { describeError, isAdcosApiError } from "@/lib/api/errors";
import { cn } from "@/lib/utils";
import { AlertIcon, RefreshIcon } from "./icons";
import { ApiRequestPanel } from "./api-request-panel";

/** Stable test id for the verbatim reason chip. */
export const ERROR_REASON_TEST_ID = "error-reason";

export function ErrorState({
  error,
  onRetry,
  request,
  compact,
}: {
  error: unknown;
  onRetry?: () => void;
  request?: { method: string; path: string; body?: unknown };
  compact?: boolean;
}) {
  const described = describeError(error);
  const apiError = isAdcosApiError(error) ? error : null;
  const failedRequest = apiError?.request ?? request;
  const retryable = apiError?.retryable ?? false;
  const retryAfter = apiError?.retryAfter ?? "";
  const requestId = apiError?.requestId ?? "";
  const canonicalReason = apiError?.canonicalReason ?? "";

  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col gap-3",
        compact ? "p-3" : "p-4",
      )}
    >
      <div className="flex items-start gap-2.5">
        <AlertIcon size={16} className="mt-0.5 shrink-0 text-danger" />
        <div className="flex min-w-0 flex-col gap-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-ink">
              {described.title}
            </span>
            <code
              data-testid={ERROR_REASON_TEST_ID}
              className="rounded border border-line bg-raised px-1.5 py-px font-mono text-2xs text-ink-muted"
            >
              {described.reasonCode}
            </code>
            {canonicalReason && canonicalReason !== described.reasonCode ? (
              <code className="font-mono text-2xs text-ink-faint">
                canonical_reason: {canonicalReason}
              </code>
            ) : null}
          </div>
          {described.detail ? (
            <p className="text-sm text-ink-muted">{described.detail}</p>
          ) : null}
          <p className="text-sm text-ink-muted">
            <span className="text-ink-faint">Next:</span>{" "}
            {described.nextAction}
          </p>
          {retryable || retryAfter ? (
            <p className="font-mono text-2xs text-ink-faint">
              {retryable ? <span>retryable: true</span> : null}
              {retryable && retryAfter ? " · " : null}
              {retryAfter ? <span>retry_after: {retryAfter}</span> : null}
            </p>
          ) : null}
          {requestId ? (
            <p className="font-mono text-2xs text-ink-faint">
              request_id: {requestId}
            </p>
          ) : null}
        </div>
      </div>
      {failedRequest ? (
        <ApiRequestPanel
          variant="compact"
          method={failedRequest.method}
          path={failedRequest.path}
          body={failedRequest.body}
        />
      ) : null}
      {onRetry ? (
        <div>
          <button
            type="button"
            onClick={onRetry}
            className="inline-flex h-8 items-center gap-1.5 rounded-md border border-line-strong bg-raised px-3 text-sm text-ink transition-colors hover:bg-surface"
          >
            <RefreshIcon size={14} />
            Retry
          </button>
        </div>
      ) : null}
    </div>
  );
}
