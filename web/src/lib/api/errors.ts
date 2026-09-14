/**
 * The ADCOS console error taxonomy.
 *
 * The backend's reason codes are the ONLY error vocabulary the console
 * displays (spec non-negotiable #6; charter #4: reason codes displayed
 * VERBATIM — never replaced with a generic message). `describeError`
 * maps a reason to presentation guidance (title / detail / next action)
 * WITHOUT rewriting the code itself.
 */

import type { AdcosErrorEnvelope, RuntimeErrorEnvelope } from "./types";

/** The descriptor of the request that failed (for reproduction UI). */
export interface FailedRequestDescriptor {
  method: string;
  path: string;
  /** The JSON body sent (or undefined for bodyless requests). */
  body?: unknown;
}

/**
 * The typed API error. Carries everything ErrorState needs: the verbatim
 * backend reason, the message, correlation id, retryability, and the
 * failed request descriptor for curl reproduction.
 */
export class AdcosApiError extends Error {
  readonly status: number;
  /** The VERBATIM backend `error.reason` (or runtime `reason_code`). */
  readonly reason: string;
  /** The canonical subsystem reason when the boundary adapted one. */
  readonly canonicalReason: string;
  readonly requestId: string;
  readonly retryable: boolean;
  readonly retryAfter: string;
  readonly resourceId: string;
  readonly environment: string;
  readonly request: FailedRequestDescriptor;

  constructor(init: {
    status: number;
    reason: string;
    message: string;
    canonicalReason?: string;
    requestId?: string;
    retryable?: boolean;
    retryAfter?: string;
    resourceId?: string;
    environment?: string;
    request: FailedRequestDescriptor;
  }) {
    super(init.message);
    this.name = "AdcosApiError";
    this.status = init.status;
    this.reason = init.reason;
    this.canonicalReason = init.canonicalReason ?? "";
    this.requestId = init.requestId ?? "";
    this.retryable = init.retryable ?? false;
    this.retryAfter = init.retryAfter ?? "";
    this.resourceId = init.resourceId ?? "";
    this.environment = init.environment ?? "";
    this.request = init.request;
  }
}

/** Type guard for the typed error. */
export function isAdcosApiError(value: unknown): value is AdcosApiError {
  return value instanceof AdcosApiError;
}

/**
 * Parse a non-2xx JSON body into the error fields, tolerating BOTH the
 * developer-boundary envelope ({error: {reason, ...}}) and the
 * runtime-level envelope ({error: {reason_code, message, backend}}).
 */
export function parseErrorBody(
  body: unknown,
): Pick<
  AdcosErrorEnvelope["error"],
  "reason" | "message" | "canonical_reason" | "request_id" | "resource_id" | "retryable" | "retry_after"
> & { environment: string } {
  const empty = {
    reason: "",
    message: "",
    canonical_reason: "",
    request_id: "",
    resource_id: "",
    retryable: false,
    retry_after: "",
    environment: "",
  };
  if (typeof body !== "object" || body === null) return empty;
  const error = (body as { error?: unknown }).error;
  if (typeof error !== "object" || error === null) return empty;
  const e = error as Record<string, unknown>;
  const runtime = e as unknown as RuntimeErrorEnvelope["error"];
  if (typeof runtime.reason_code === "string" && typeof e.reason !== "string") {
    return {
      ...empty,
      reason: runtime.reason_code,
      message: typeof runtime.message === "string" ? runtime.message : "",
    };
  }
  const str = (v: unknown): string => (typeof v === "string" ? v : "");
  return {
    reason: str(e.reason),
    message: str(e.message),
    canonical_reason: str(e.canonical_reason),
    request_id: str(e.request_id),
    resource_id: str(e.resource_id),
    retryable: e.retryable === true,
    retry_after: str(e.retry_after),
    environment: str(e.environment),
  };
}

/** Presentation guidance for an error (title/detail/next action). */
export interface ErrorPresentation {
  title: string;
  /** The verbatim reason code — ALWAYS surfaced as-is. */
  reasonCode: string;
  detail: string;
  nextAction: string;
}

/**
 * Presentation guidance per known reason code. UNKNOWN reasons get the
 * fallback row — the reason itself is still shown verbatim either way.
 */
const REASON_PRESENTATION: Record<string, { title: string; nextAction: string }> = {
  "authentication-invalid": {
    title: "Authentication failed",
    nextAction: "Check the application ID and credential in the session menu, then reconnect.",
  },
  "authentication-expired": {
    title: "Credential expired",
    nextAction: "Obtain a freshly issued credential and reconnect.",
  },
  "environment-mismatch": {
    title: "Environment mismatch",
    nextAction:
      "The credential is not valid in this environment. Use a credential issued for it.",
  },
  "capability-denied": {
    title: "Capability not granted",
    nextAction:
      "This application lacks the capability this operation requires. Inspect capabilities in Developers.",
  },
  "version-unsupported": {
    title: "API version not supported",
    nextAction: "The route version and X-ADCOS-API-Version must agree (2.0).",
  },
  "rate-limited": {
    title: "Rate limited",
    nextAction: "Wait for the reset instant in rate_limit.reset_at, then retry.",
  },
  "idempotency-key-required": {
    title: "Idempotency key required",
    nextAction:
      "Mutations require X-ADCOS-Idempotency-Key (the client sends one automatically — retry).",
  },
  "idempotency-conflict": {
    title: "Idempotency conflict",
    nextAction: "This key was used with a different body. Use a new key for a new mutation.",
  },
  "pagination-invalid": {
    title: "Invalid pagination",
    nextAction: "The cursor/limit is invalid for this list context. Reload the list.",
  },
  "filter-invalid": {
    title: "Invalid filter",
    nextAction: "Use a declared filter member (contracts and leases filter by state).",
  },
  "resource-unknown": {
    title: "Resource not found",
    nextAction: "The resource does not exist (or is not owned by this application).",
  },
  "route-unknown": {
    title: "Unknown API route",
    nextAction: "The console requested a route the runtime does not expose.",
  },
  "invalid-input": {
    title: "Invalid input",
    nextAction: "Fix the highlighted fields and retry.",
  },
  "invalid-transition": {
    title: "Invalid state transition",
    nextAction:
      "The object is not in a state that allows this operation. Refresh to see its current state.",
  },
  "invalid-state": {
    title: "Invalid state",
    nextAction: "Refresh to see the object's current state.",
  },
  "unknown-contract": {
    title: "Contract not found",
    nextAction: "The contract does not exist or is not visible to this application.",
  },
  "contract-terminal": {
    title: "Contract is terminal",
    nextAction: "Terminal contracts accept no further commands.",
  },
  "constraint-immutable": {
    title: "Constraints are immutable",
    nextAction: "Hard constraints cannot be changed after creation.",
  },
  "not-yet-valid": {
    title: "Not yet valid",
    nextAction: "The validity window has not opened yet.",
  },
  expired: {
    title: "Expired",
    nextAction: "The validity window has closed.",
  },
  "temporal-invalid": {
    title: "Temporal values invalid",
    nextAction: "Check the instants (RFC 3339 UTC) and their ordering.",
  },
  "secret-rejected": {
    title: "Secret rejected",
    nextAction: "The backend's secret scan rejected the material. Remove secret-like values.",
  },
  vocabulary: {
    title: "Vocabulary rejected",
    nextAction: "Use the backend's frozen vocabularies for this member.",
  },
  "sequence-conflict": {
    title: "Creation conflict",
    nextAction: "An identical creation core already exists; inspect the current state.",
  },
  "replay-stale": {
    title: "Replay is stale",
    nextAction: "The journal rejected this sequence; refresh and inspect current state.",
  },
  "journal-tamper": {
    title: "Journal integrity failure",
    nextAction: "The durable journal failed verification. Escalate to the platform operator.",
  },
  "store-failed": {
    title: "Store failure",
    nextAction: "The durable store failed. Retry; if it persists, escalate.",
  },
  "payload-too-large": {
    title: "Payload too large",
    nextAction: "The request body exceeds the 1 MiB cap.",
  },
  "malformed-json": {
    title: "Malformed JSON",
    nextAction: "The request body was not valid JSON.",
  },
  "invalid-request-body": {
    title: "Invalid request body",
    nextAction: "The request body must be a JSON object.",
  },
  "backend-unreachable": {
    title: "Backend unreachable",
    nextAction: "The console could not reach the ADCOS runtime. Check /readyz in Connectivity.",
  },
  "internal-error": {
    title: "Internal error",
    nextAction: "The runtime failed unexpectedly. Retry; if it persists, escalate.",
  },
};

/** describeError — presentation guidance for any thrown value. */
export function describeError(error: unknown): ErrorPresentation {
  if (isAdcosApiError(error)) {
    const known = REASON_PRESENTATION[error.reason];
    return {
      title: known?.title ?? "Request failed",
      reasonCode: error.reason,
      detail:
        error.message ||
        (known?.nextAction ?? "The backend rejected this request."),
      nextAction: known?.nextAction ?? "Inspect the request below and retry.",
    };
  }
  if (error instanceof TypeError) {
    // fetch() network failure (backend down / DNS / proxy) — synthesized
    // client-side code, clearly labeled as such (never a backend reason)
    return {
      title: "Backend unreachable",
      reasonCode: "backend-unreachable",
      detail:
        "The request never reached the ADCOS runtime (network failure). Same-origin only; in dev the Next rewrite proxies to ADCOS_BACKEND_URL.",
      nextAction: "Verify the runtime is up (the environment indicator polls /readyz).",
    };
  }
  if (error instanceof Error) {
    return {
      title: "Unexpected error",
      reasonCode: "ui-error",
      detail: error.message,
      nextAction: "Retry the action; if it persists, inspect the browser console.",
    };
  }
  return {
    title: "Unexpected error",
    reasonCode: "ui-error",
    detail: String(error),
    nextAction: "Retry the action.",
  };
}
