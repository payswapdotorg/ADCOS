/**
 * The console error taxonomy (plan Task 3) + the `describeError` helper
 * that feeds `ErrorState`.
 *
 * DISCIPLINE: backend reason codes are surfaced VERBATIM — this module
 * only attaches presentation metadata (title/next-action guidance)
 * around the verbatim value; it NEVER rewrites, translates or replaces
 * the reason the backend returned. Unknown reasons keep their verbatim
 * label with generic guidance.
 */

import type { ApiRequestDescriptor } from "./types";

/** The typed console error for every non-2xx backend response. */
export class AdcosApiError extends Error {
  /** The HTTP status the backend returned. */
  readonly status: number;
  /** The VERBATIM boundary reason (`error.reason`, or the runtime-level `error.reason_code`). */
  readonly reason: string;
  /** The VERBATIM canonical domain reason when a canonical authority rejected the request. */
  readonly canonicalReason: string | null;
  /** The backend's deterministic human message. */
  readonly message: string;
  /** The correlation id (`X-ADCOS-Request-Id` / envelope `request_id`). */
  readonly requestId: string | null;
  /** The backend's retryability classification. */
  readonly retryable: boolean;
  /** The backend's retry hint (RFC 3339 instant) when present. */
  readonly retryAfter: string | null;
  /** The affected resource id when the backend names one. */
  readonly resourceId: string | null;
  /** The failing request, for the reproduction UI (credential masked). */
  readonly request: ApiRequestDescriptor;
  /** The environment the boundary reported. */
  readonly environment: string | null;

  constructor(init: {
    status: number;
    reason: string;
    message: string;
    requestId?: string | null;
    retryable?: boolean;
    retryAfter?: string | null;
    canonicalReason?: string | null;
    resourceId?: string | null;
    environment?: string | null;
    request: ApiRequestDescriptor;
  }) {
    super(`[${init.status}] ${init.reason}: ${init.message}`);
    this.name = "AdcosApiError";
    this.status = init.status;
    this.reason = init.reason;
    this.canonicalReason = init.canonicalReason ?? null;
    this.message = init.message;
    this.requestId = init.requestId ?? null;
    this.retryable = init.retryable ?? false;
    this.retryAfter = init.retryAfter ?? null;
    this.resourceId = init.resourceId ?? null;
    this.environment = init.environment ?? null;
    this.request = init.request;
  }
}

/** Narrow an unknown thrown value to an AdcosApiError. */
export function isAdcosApiError(value: unknown): value is AdcosApiError {
  return value instanceof AdcosApiError;
}

/**
 * Presentation guidance per KNOWN boundary reason (the frozen
 * `DeveloperApiReasonCode` vocabulary + the canonical contract reasons
 * observed in the wild). The reason itself is ALWAYS displayed
 * verbatim — this table only adds the next-action hint.
 */
const NEXT_ACTIONS: Record<string, string> = {
  "authentication-invalid":
    "Check the application id and credential in Settings → Connect application; a credential is bound to exactly one environment and can be revoked or expired.",
  "authentication-expired":
    "The credential's validity window has ended; obtain a fresh credential from the platform and reconnect in Settings.",
  "environment-mismatch":
    "The credential belongs to the other environment (sandbox vs production); connect with a credential issued for this environment.",
  "capability-denied":
    "The connected application lacks the capability this operation requires; check the application's capabilities in Settings.",
  "rate-limited":
    "The application hit its rate limit; retry after the reset instant shown above.",
  "idempotency-key-required":
    "This mutation requires an idempotency key; the console sends one automatically — retry the action.",
  "idempotency-conflict":
    "This idempotency key was already used with a different request body; retry with the original body or start a new action.",
  "route-unknown":
    "The console requested a route the backend does not declare; this is a console defect — report it with the request id.",
  "version-unsupported":
    "The route version and the X-ADCOS-API-Version header disagreed; the console pins 2.0 — report this as a console defect.",
  "invalid-input":
    "The backend rejected the request payload; check the field-level detail above and adjust the form values.",
  "pagination-invalid":
    "The page request was out of bounds (limit must be 1..100); go back and retry the listing.",
  "filter-invalid":
    "The filter key is not one of the filterable members; use the declared filters only.",
  "resource-unknown":
    "No such resource exists (or it belongs to another developer); re-open the list and pick a current object.",
  "unknown-contract":
    "No contract with this id exists in the canonical authority; re-open the contracts list.",
  "invalid-transition":
    "The canonical state machine rejected this command; inspect the object's current lifecycle state and the legal transitions.",
  "invalid-state":
    "The object is not in a state that accepts this command; inspect the lifecycle view.",
  "contract-terminal":
    "The contract is in a terminal state (SETTLED / TERMINATED / EXPIRED / FAILED) and accepts no further commands.",
  "constraint-immutable":
    "Hard constraints are frozen at construction and cannot be weakened or edited.",
  "malformed-json":
    "The request body was not valid JSON; this is a console transport defect — report it with the request id.",
  "payload-too-large":
    "The request body exceeded the 1 MiB cap; reduce the payload size.",
  "not-found":
    "No route matched this request on the platform surface; check the path.",
  "internal-error":
    "The backend collapsed an unexpected failure to a typed internal error; report the request id to the operator.",
  "store-failed":
    "The durable API journal failed to admit the request; retry with the same idempotency key.",
  "journal-corrupt":
    "The durable journal is inconsistent; escalate to the operator with the request id.",
};

/** A human title per error family (never replaces the verbatim reason). */
function titleFor(status: number, reason: string): string {
  if (status === 401 || status === 403) return "The request was not authorized";
  if (status === 404) return "The request targeted something that does not exist";
  if (status === 422) return "The canonical authority rejected the command";
  if (status === 429) return "The request was rate limited";
  if (status === 409) return "The request conflicted with prior state";
  if (status >= 500) return "The backend failed to serve the request";
  return `The request was rejected (${reason})`;
}

export interface ErrorDescription {
  title: string;
  /** The VERBATIM reason code (boundary reason; canonical reason appended when present). */
  reasonCode: string;
  detail: string;
  nextAction: string;
}

/**
 * Describe any console failure for `ErrorState`. Unknown reason codes
 * keep their verbatim value; nothing is ever replaced with a generic
 * message.
 */
export function describeError(error: unknown): ErrorDescription {
  if (isAdcosApiError(error)) {
    const reasonCode = error.canonicalReason
      ? `${error.reason} → ${error.canonicalReason}`
      : error.reason;
    return {
      title: titleFor(error.status, error.reason),
      reasonCode,
      detail: error.message,
      nextAction:
        NEXT_ACTIONS[error.canonicalReason ?? error.reason] ??
        NEXT_ACTIONS[error.reason] ??
        (error.retryable
          ? "The backend marked this failure retryable; retry the action."
          : "Inspect the verbatim reason code above; the backend's own message carries the authoritative explanation."),
    };
  }
  if (error instanceof Error) {
    return {
      title: "The console could not complete the request",
      reasonCode: "transport-error",
      detail: error.message,
      nextAction:
        "The request never reached a typed backend response; check that the backend is reachable (the environment indicator polls /readyz).",
    };
  }
  return {
    title: "The console could not complete the request",
    reasonCode: "unknown-error",
    detail: String(error),
    nextAction: "Retry the action; if it persists, report it with the request id.",
  };
}
