/**
 * The in-memory request log — display DATA only, never authority.
 *
 * Records the requests the console itself made (method, path, body,
 * status, request id, reason when failed). It holds NO response payloads
 * (refresh always re-fetches truth from the backend) and NO secrets
 * beyond what the UI already shows. Worker 3's request inspector / API
 * explorer renders this via `useRequestLog`.
 */

import { useCallback, useSyncExternalStore } from "react";
import type { RequestLogEntry } from "@/lib/api/client";

export interface LoggedRequest extends RequestLogEntry {
  /** Monotonic sequence for stable rendering. */
  sequence: number;
}

const MAX_ENTRIES = 50;
let sequence = 0;
let entries: LoggedRequest[] = [];
const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) listener();
}

/** Record one completed request attempt (success or failure). */
export function recordRequest(entry: RequestLogEntry): void {
  sequence += 1;
  entries = [{ ...entry, sequence }, ...entries].slice(0, MAX_ENTRIES);
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
