"use client";

/**
 * EvidenceExplorer — the evidence surface (Worker 3, plan Task 8).
 *
 * Evidence is a first-class resource: source, timestamp, evidence class,
 * provenance, related objects. The ONLY evidence surface the backend
 * exposes today is the deterministic fulfillment demonstration document
 * (GET|POST /demo/contract-fulfillment) — so the explorer lists the
 * evidence of EVERY demonstration run this console session made
 * (`useDemoRuns`, newest first), including the run this page itself
 * makes on load (the current document, recorded via `recordDemoRun`).
 *
 * Honesty rules:
 * - every record member and the document's evidence_class ("SOFTWARE")
 *   render VERBATIM — never re-badged;
 * - SOFTWARE never becomes a physical PASS (the legend states the
 *   physical/network family is NOT-ACHIEVABLE-BY-THIS-DEPLOYMENT);
 * - the run action is a REAL platform read through the typed client
 *   (GET /demo/contract-fulfillment needs no session);
 * - no runs yet → the honest empty state explains how to make one.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import type { DemoDocument } from "@/lib/api/types";
import {
  EmptyState,
  EvidenceBadge,
  RefreshIcon,
} from "@/components/ui";
import { ensureRequestRecorder } from "@/features/requests/recorder";
import { registerCommand } from "@/features/search";
import { ConsoleSearchProviders } from "@/features/search/providers";
import { useSession } from "@/lib/session";
import { LinkedErrorState } from "@/features/errors/link";
import { recordDemoRun, useDemoRuns } from "./demo-runs";
import { EvidenceClassLegend } from "./evidence-class-legend";
import { EvidenceRecordCard } from "./evidence-record-card";
import { EvidenceRecordDrawer } from "./evidence-record-drawer";
import {
  evidenceRecordsOf,
  type EvidenceRecordView,
} from "./evidence-record";

/** Stable test ids for the evidence suite. */
export const EVIDENCE_EXPLORER_TEST_IDS = {
  root: "evidence-explorer",
  runDemo: "evidence-run-demo",
  runGroup: "demo-run-group",
  empty: "evidence-empty",
} as const;

interface DemoReadState {
  loading: boolean;
  error: unknown;
  lastAt: string | null;
}

export function EvidenceExplorer() {
  const { status, client } = useSession();
  const connected = status === "connected";
  const runs = useDemoRuns();

  const [demoRead, setDemoRead] = useState<DemoReadState>({
    loading: false,
    error: null,
    lastAt: null,
  });

  const [drawer, setDrawer] = useState<{
    view: EvidenceRecordView;
    record: Record<string, unknown>;
    document: DemoDocument | null;
  } | null>(null);

  // capture-eligible requests + the palette entry, from mount on
  useEffect(() => {
    ensureRequestRecorder();
    const unregister = registerCommand({
      id: "go-fulfillment-demo",
      title: "Run the fulfillment demonstration",
      group: "Actions",
      href: "/fulfillment",
    });
    return unregister;
  }, []);

  const runDemoRead = useCallback(async () => {
    setDemoRead((previous) => ({ ...previous, loading: true, error: null }));
    try {
      const document = await client.demoContractFulfillment();
      recordDemoRun(document);
      setDemoRead({ loading: false, error: null, lastAt: new Date().toISOString() });
    } catch (error) {
      setDemoRead((previous) => ({ ...previous, loading: false, error }));
    }
  }, [client]);

  // on load (when a session is connected): fetch the CURRENT demo
  // document and record it — re-recording the same instant replaces it
  // (the store's own discipline), so reloads do not pile runs up.
  useEffect(() => {
    if (!connected) return;
    void runDemoRead();
  }, [connected, runDemoRead]);

  return (
    <div
      className="mx-auto w-full max-w-workbench px-gutter py-rhythm"
      data-testid={EVIDENCE_EXPLORER_TEST_IDS.root}
    >
      <ConsoleSearchProviders />
      <div className="flex flex-col gap-4">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-ink">Evidence</h1>
            <p className="mt-1 max-w-3xl text-sm text-ink-muted">
              Evidence is a first-class resource: source, timestamp, evidence
              class, provenance and related objects. The backend&apos;s only
              evidence surface today is the deterministic fulfillment
              demonstration (GET|POST /demo/contract-fulfillment) — every
              demonstration run this console session made is listed below,
              newest first, with its records exactly as returned.
            </p>
          </div>
          <button
            type="button"
            data-testid={EVIDENCE_EXPLORER_TEST_IDS.runDemo}
            onClick={() => void runDemoRead()}
            disabled={demoRead.loading}
            className="inline-flex h-8 items-center gap-1.5 rounded-md border border-line-strong bg-raised px-3 text-sm text-ink transition-colors hover:bg-surface disabled:opacity-50"
          >
            <RefreshIcon size={14} />
            {demoRead.loading ? "Reading…" : "Run demo read"}
          </button>
        </header>

        <EvidenceClassLegend />

        {demoRead.error ? (
          <div className="rounded-md border border-line bg-surface">
            <LinkedErrorState
              error={demoRead.error}
              onRetry={() => void runDemoRead()}
              request={{ method: "GET", path: "/demo/contract-fulfillment" }}
            />
          </div>
        ) : null}

        {demoRead.lastAt ? (
          <p className="text-xs text-ink-faint" data-testid="evidence-last-read">
            Last demo read recorded at {demoRead.lastAt} (the current document,
            recorded as a run).
          </p>
        ) : null}

        {runs.length === 0 ? (
          <div
            className="rounded-md border border-line bg-surface"
            data-testid={EVIDENCE_EXPLORER_TEST_IDS.empty}
          >
            <EmptyState
              title="No demonstration runs yet"
              description={
                <span>
                  No evidence to show — this console session has not recorded a
                  demonstration run. Make one from the{" "}
                  <Link
                    href="/fulfillment"
                    className="text-accent hover:underline"
                  >
                    fulfillment demonstration
                  </Link>{" "}
                  (POST /demo/contract-fulfillment with an instant), or use this
                  page&apos;s own{" "}
                  <span className="font-mono text-xs">Run demo read</span>{" "}
                  action (the platform GET needs no session).
                </span>
              }
            />
          </div>
        ) : (
          runs.map((run) => {
            const records = evidenceRecordsOf(run.document);
            return (
              <section
                key={run.instant}
                data-testid={EVIDENCE_EXPLORER_TEST_IDS.runGroup}
                data-instant={run.instant}
                className="rounded-md border border-line bg-surface"
              >
                <div className="flex flex-col gap-2 border-b border-line px-4 py-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-sm font-semibold text-ink">
                      Demonstration run
                    </h2>
                    <span className="font-mono text-2xs text-ink-faint">
                      instant {run.instant}
                    </span>
                    <EvidenceBadge evidenceClass={run.document.evidence_class} />
                    <span className="font-mono text-2xs text-ink-faint">
                      mode {run.document.mode} · environment{" "}
                      {run.document.environment}
                    </span>
                    <span className="ml-auto font-mono text-2xs text-ink-faint">
                      recorded {run.recordedAt}
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                    {run.contractId ? (
                      <span className="flex min-w-0 items-baseline gap-1.5">
                        <span className="font-mono text-2xs text-ink-faint">
                          contract
                        </span>
                        <Link
                          href={`/connectivity/contracts/${run.contractId}`}
                          className="truncate font-mono text-xs text-accent hover:underline"
                          title={run.contractId}
                        >
                          {run.contractId}
                        </Link>
                      </span>
                    ) : null}
                    <span className="font-mono text-2xs text-ink-faint">
                      {records.length} evidence record
                      {records.length === 1 ? "" : "s"}
                    </span>
                  </div>
                  <p className="text-xs text-ink-faint">
                    evidence_class is the document&apos;s own value, rendered
                    VERBATIM — SOFTWARE is deterministic software-side evidence
                    and never becomes a physical PASS. Records are exactly the
                    backend returned them.
                  </p>
                </div>
                <div className="grid gap-3 px-4 py-3 md:grid-cols-2">
                  {records.map(({ record, view }) => (
                    <EvidenceRecordCard
                      key={view.record_id ?? JSON.stringify(record)}
                      view={view}
                      onOpen={() => setDrawer({ view, record, document: run.document })}
                    />
                  ))}
                </div>
              </section>
            );
          })
        )}
      </div>

      <EvidenceRecordDrawer
        open={drawer !== null}
        onOpenChange={(open) => {
          if (!open) setDrawer(null);
        }}
        view={drawer?.view ?? {
          record_type: null,
          record_id: null,
          subject_ref: null,
          contract_ref: null,
          instant: null,
          producer: null,
          metric: null,
          value: null,
          confidence_basis_points: null,
          freshness_until: null,
          attestation_kind: null,
          attested_value: null,
          valid_until: null,
          source_refs: [],
        }}
        record={drawer?.record ?? {}}
        document={drawer?.document ?? null}
      />
    </div>
  );
}
