/**
 * The session's demonstration runs — display DATA only, never authority.
 *
 * The evidence explorer surfaces (a) the platform's demonstration
 * document (GET /demo/contract-fulfillment, the default instant — a
 * platform route that needs no session) and (b) every demonstration
 * run THIS console session made (POST /demo/contract-fulfillment with
 * an instant, recorded here at run time). Each run carries its full
 * document (boundary, contract, plan, execution, evidence) so the
 * evidence records, the contract reference and the honest
 * evidence_class ("SOFTWARE") stay exactly as the backend returned
 * them — VERBATIM, never re-badged.
 *
 * In-memory only (like the request log and the session itself): a
 * reload clears it by design, and nothing here is ever persisted.
 */

import { useSyncExternalStore } from "react";
import type { DemoDocument } from "@/lib/api/types";

export interface DemoRun {
  /** The run's request instant (the demo document's `instant`). */
  instant: string;
  /** The demonstration contract id (the document's contract_id). */
  contractId: string;
  /** The full document exactly as returned. */
  document: DemoDocument;
  /** When this console recorded the run (ISO). */
  recordedAt: string;
}

const MAX_RUNS = 12;

let runs: DemoRun[] = [];
const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) listener();
}

/** Record a demonstration run (newest first; re-recording an instant replaces it). */
export function recordDemoRun(document: DemoDocument, recordedAt?: string): void {
  const contract = document.contract as { contract_id?: string } | null;
  const run: DemoRun = {
    instant: document.instant,
    contractId: typeof contract?.contract_id === "string" ? contract.contract_id : "",
    document,
    recordedAt: recordedAt ?? new Date().toISOString(),
  };
  runs = [run, ...runs.filter((entry) => entry.instant !== run.instant)].slice(0, MAX_RUNS);
  emit();
}

/** The current runs (newest first). */
export function getDemoRuns(): DemoRun[] {
  return runs;
}

/** Subscribe to run changes (useSyncExternalStore contract). */
export function subscribeDemoRuns(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** React binding for the demo-runs store. */
export function useDemoRuns(): DemoRun[] {
  return useSyncExternalStore(subscribeDemoRuns, getDemoRuns, getDemoRuns);
}

/** Test helper — reset the store between suites. */
export function __resetDemoRunsForTests(): void {
  runs = [];
  emit();
}
