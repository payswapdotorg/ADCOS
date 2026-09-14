"use client";

/**
 * The explorer EXECUTION HISTORY — display data only, never authority.
 *
 * Every real execution through `executeOperation` (success or typed error)
 * appends one entry here: the request as actually sent (the descriptor),
 * the outcome, and — when the request recorder captured it — the response
 * headers/duration/body correlated from the request log. Local validation
 * failures (`kind: "invalid"`) never reach this store: no request was
 * made, so there is no request/response pair to replay.
 *
 * In-memory, newest first, capped at 20 (a workbench scrolling window,
 * not a journal — the backend owns durability). Replay re-runs the entry
 * through `executeOperation` with the SAME inputs; a mutation replays
 * with the SAME idempotency key, which the boundary answers with the
 * SAME response byte-identically (the frozen replay semantics).
 */

import { useSyncExternalStore } from "react";
import type { CoverageRecord } from "@/lib/api/coverage";
import type { ExecuteOutcome, RequestDescriptor } from "./executor";

/** One replayable request/response pair from this console session. */
export interface ExplorerExecution {
  /** Monotonic sequence for stable rendering. */
  sequence: number;
  /** ISO timestamp of the execution. */
  at: string;
  /** The registry record that was executed (verbatim operation id). */
  coverage: CoverageRecord;
  /** The request as actually sent (effective method/path/body/key). */
  request: RequestDescriptor;
  /** The path parameter values used (replay input). */
  pathParams: Record<string, string>;
  /** The body editor's raw text at execution time (replay input). */
  bodyText: string;
  /** The pinned idempotency key (mutations; replay input). */
  idempotencyKey?: string;
  /** The outcome — success or a TYPED backend error (never invalid). */
  outcome: ExecuteOutcome;
  /** Recorder-captured response headers (absent when not captured). */
  responseHeaders?: { name: string; value: string }[];
  /** Recorder-captured duration in ms (absent when not captured). */
  durationMs?: number;
  /** Recorder-captured response body text, truncated (absent when not captured). */
  responseBody?: string;
}

const MAX_EXECUTIONS = 20;
let sequence = 0;
let executions: ExplorerExecution[] = [];
const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) listener();
}

/** Record one real execution (newest first, capped). */
export function appendExplorerExecution(
  execution: Omit<ExplorerExecution, "sequence" | "at">,
): ExplorerExecution {
  sequence += 1;
  const entry: ExplorerExecution = {
    ...execution,
    sequence,
    at: new Date().toISOString(),
  };
  executions = [entry, ...executions].slice(0, MAX_EXECUTIONS);
  emit();
  return entry;
}

/** The current executions (newest first). */
export function getExplorerExecutions(): ExplorerExecution[] {
  return executions;
}

/** Subscribe to history changes (useSyncExternalStore contract). */
export function subscribeExplorerExecutions(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** React binding for the execution history. */
export function useExplorerExecutions(): ExplorerExecution[] {
  return useSyncExternalStore(
    subscribeExplorerExecutions,
    getExplorerExecutions,
    getExplorerExecutions,
  );
}

/** Test helper — reset the store between suites. */
export function __resetExplorerHistoryForTests(): void {
  sequence = 0;
  executions = [];
  emit();
}
