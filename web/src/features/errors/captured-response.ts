/**
 * Best-effort parsing of a captured request's response body into the
 * error-workbench anatomy fields (what happened / why / affected
 * resource / retryability).
 *
 * HONESTY CONTRACT: nothing is fabricated. When the recorder captured no
 * response body (or the body carries no error member), every field is
 * null and the workbench says so — the anatomy still renders from the
 * base log entry (status, method, path, reason, request id, instant).
 */

import type { LoggedRequest } from "@/features/requests/request-log";

/** The parsed anatomy of one captured error. */
export interface CapturedErrorDetails {
  /** The backend's message (error.message / error.reason_code envelope). */
  message: string | null;
  /** The canonical subsystem reason when the boundary adapted one. */
  canonicalReason: string | null;
  /** The affected resource id, when the backend sent one. */
  resourceId: string | null;
  /** retryable exactly as the backend marked it (null = not captured). */
  retryable: boolean | null;
  /** The envelope's request id, when captured. */
  requestId: string | null;
  /** The raw captured body text (truncated by the recorder), if any. */
  rawBody: string | null;
}

interface ErrorMember {
  message?: unknown;
  canonical_reason?: unknown;
  resource_id?: unknown;
  retryable?: unknown;
  request_id?: unknown;
  reason?: unknown;
  reason_code?: unknown;
}

const str = (value: unknown): string | null =>
  typeof value === "string" && value.length > 0 ? value : null;

/**
 * Parse the captured response body of a FAILED request. Tolerates both
 * envelope shapes (the developer boundary's `error.reason` member and
 * the runtime-level `error.reason_code` member); returns all-null when
 * nothing was captured.
 */
export function parseCapturedError(entry: LoggedRequest): CapturedErrorDetails {
  const empty: CapturedErrorDetails = {
    message: null,
    canonicalReason: null,
    resourceId: null,
    retryable: null,
    requestId: null,
    rawBody: null,
  };
  const text = entry.responseBody;
  if (typeof text !== "string" || text.trim().length === 0) return empty;

  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    return { ...empty, rawBody: text };
  }
  if (typeof parsed !== "object" || parsed === null) {
    return { ...empty, rawBody: text };
  }

  const error = (parsed as { error?: unknown }).error;
  if (typeof error !== "object" || error === null) {
    return { ...empty, rawBody: text };
  }
  const member = error as ErrorMember;
  return {
    message: str(member.message),
    canonicalReason: str(member.canonical_reason),
    resourceId: str(member.resource_id),
    retryable: typeof member.retryable === "boolean" ? member.retryable : null,
    requestId: str(member.request_id),
    rawBody: text,
  };
}
