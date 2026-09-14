"use client";

/**
 * The in-memory request log — display DATA only, never authority.
 *
 * Records the requests the console itself made (method, path, body,
 * status, request id, reason when failed). It holds NO secrets beyond
 * what the UI already shows. Worker 3's request inspector / API
 * explorer renders this via `useRequestLog`.
 *
 * Worker 3 extension (charter §3.3 — the request inspector): entries
 * are ENRICHED from the recorder (features/requests/recorder.ts) with
 * duration, the truncated response body and the surfaced response
 * headers WHENEVER the recorder captured them. Enrichment is
 * best-effort and honest: an entry recorded without the recorder
 * (e.g. before any inspector-capable page mounted) simply carries no
 * extra fields — nothing is ever fabricated.
 */

import { useCallback, useSyncExternalStore } from "react";
import type { RequestLogEntry } from "@/lib/api/client";
import { matchRequestCompletion } from "./recorder";

export interface LoggedRequest extends RequestLogEntry {
  /** Monotonic sequence for stable rendering. */
  sequence: number;
  /** Wall-clock duration of the request (recorder-captured, ms). */
  durationMs?: number;
  /** The response body text, truncated (recorder-captured). */
  responseBody?: string;
  /** The surfaced response headers (X-ADCOS-*, rate-limit, content-type). */
  responseHeaders?: { name: string; value: string }[];
}

const MAX_ENTRIES = 50;
let sequence = 0;
let entries: LoggedRequest[] = [];
const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) listener();
}

/**
 * Record one completed request attempt (success or failure). The base
 * entry comes from the typed client's interceptor; when the recorder
 * captured the matching completion, its richer fields are merged in.
 */
export function recordRequest(entry: RequestLogEntry): void {
  sequence += 1;
  const completion = matchRequestCompletion({
    method: entry.method,
    path: entry.path,
    body: entry.body,
    status: entry.status,
  });
  entries = [
    {
      ...entry,
      sequence,
      ...(completion
        ? {
            durationMs: completion.durationMs,
            responseBody: completion.responseBody,
            responseHeaders: completion.responseHeaders,
          }
        : {}),
    },
    ...entries,
  ].slice(0, MAX_ENTRIES);
  emit();
}

/** The current log (newest first). */
export function getRequests(): LoggedRequest[] {
  return entries;
}

/** Clear the log. */
export function clearRequests(): void {
  entries = [];
  emit();
}

/** Subscribe to log changes (useSyncExternalStore contract). */
export function subscribeRequests(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** React binding for the request log. */
export function useRequestLog(): LoggedRequest[] {
  return useSyncExternalStore(subscribeRequests, getRequests, getRequests);
}

/** Test helper — reset the module state between suites. */
export function __resetRequestLogForTests(): void {
  sequence = 0;
  entries = [];
  emit();
}

/** Convenience: is an entry a failure? */
export function isFailedRequest(entry: LoggedRequest): boolean {
  return entry.status < 200 || entry.status >= 400;
}

/** The copyable label for an entry (used by ApiRequestPanel consumers). */
export function requestLabel(entry: LoggedRequest): string {
  return `${entry.method} ${entry.path}`;
}
