"use client";

/**
 * The in-memory demonstration-run registry (presentation data ONLY).
 *
 * The backend exposes NO registry of demonstration runs — the
 * demonstration is a deterministic, idempotent function of the instant
 * (identical instant → byte-identical document, replayed through the
 * boundary's own idempotency ledger). This module remembers the runs
 * performed in THIS browser session so Home and Fulfillment can link to
 * them; it is explicitly NOT backend truth (a reload clears it — the
 * Fulfillment page says so honestly next to the list).
 */

import { useSyncExternalStore } from "react";

/** One remembered demonstration run (all values from the real response). */
export interface DemoRunRecord {
  /** The RFC 3339 instant the demonstration was run at. */
  instant: string;
  /** When this browser session ran it (wall clock, presentation only). */
  ranAt: string;
  /** The demonstration contract's id (the response's contract.contract_id). */
  contractId: string;
  /** The plan id (the response's plan.plan_id). */
  planId: string;
}

/**
 * The fixed default demonstration instant (the backend's own constant —
 * GET /demo/contract-fulfillment runs at exactly this instant; the
 * response's `instant` member carries it back).
 */
export const DEFAULT_DEMO_INSTANT = "2026-09-13T00:00:00Z";

let runs: DemoRunRecord[] = [];
const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) listener();
}

/** Record one run (replaces any record with the same instant). */
export function registerDemoRun(record: DemoRunRecord): void {
  runs = [record, ...runs.filter((run) => run.instant !== record.instant)];
  emit();
}

/** The current session's runs (newest first). */
export function getDemoRuns(): DemoRunRecord[] {
  return runs;
}

/** Subscribe (useSyncExternalStore contract). */
export function subscribeDemoRuns(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** React binding for the registry. */
export function useDemoRuns(): DemoRunRecord[] {
  return useSyncExternalStore(subscribeDemoRuns, getDemoRuns, getDemoRuns);
}

/** Test helper — reset the registry between suites. */
export function __resetDemoRunsForTests(): void {
  runs = [];
  emit();
}
