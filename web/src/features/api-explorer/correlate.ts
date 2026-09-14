/**
 * Correlation between an executed operation and the request log.
 *
 * `executeOperation` (frozen) returns the request descriptor and the
 * parsed outcome, but NOT the response headers — the recorder owns
 * those (features/requests). Every execution through the session client
 * flows through the recorded transport, so by the time the executor
 * resolves, the request log already holds the enriched entry. This
 * helper finds the NEWEST log entry matching the descriptor — the same
 * deterministic correlation the request log itself uses (method + path
 * + status + serialized body). No match → null → the response pane
 * renders its honest "not captured" note; nothing is fabricated.
 */

import { getRequests, type LoggedRequest } from "@/features/requests/request-log";

/** Find the newest logged request matching an executed descriptor. */
export function correlateLoggedRequest(match: {
  method: string;
  path: string;
  body?: unknown;
  status: number;
}): LoggedRequest | null {
  for (const entry of getRequests()) {
    if (
      entry.method === match.method.toUpperCase() &&
      entry.path === match.path &&
      entry.status === match.status &&
      sameBody(entry.body, match.body)
    ) {
      return entry;
    }
  }
  return null;
}

function sameBody(left: unknown, right: unknown): boolean {
  if (left === undefined && right === undefined) return true;
  if (left === undefined || right === undefined) return false;
  return JSON.stringify(left) === JSON.stringify(right);
}
