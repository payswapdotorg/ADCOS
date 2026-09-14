"use client";

/**
 * AssuranceView — the assurance surface (Worker 3, plan Task 8).
 *
 * Per contract (list contracts, then read assurance per contract): the
 * OBLIGATION REFERENCES VERBATIM (opaque refs with their provenance —
 * the objectives the backend actually returns), the contract state, the
 * honest notes, and each obligation linked to its contract and its
 * evidence chain (the demonstration runs&apos; attestation records by
 * contract_ref).
 *
 * Honesty rules:
 * - NO invented metric dashboards: objectives are the opaque obligation
 *   references the backend returns, nothing more — semantics are
 *   referenced, never evaluated here;
 * - every note and evidence_class renders VERBATIM (sandbox-simulation
 *   stays exactly what the backend said);
 * - the contracts list is the BODYLESS browser form of the GET-body list
 *   discipline (fetch forbids GET bodies) — deeper pagination is
 *   disclosed honestly with the canonical curl form;
 * - the evidence chain shows only what THIS console session captured
 *   (in-memory demonstration runs) — honest empty states when none.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import type {
  Contract,
  ContractAssurance,
  ListResponse,
} from "@/lib/api/types";
import {
  ApiRequestPanel,
  EmptyState,
  EvidenceBadge,
  ObjectHeader,
  RefreshIcon,
  Status,
} from "@/components/ui";
import { ensureRequestRecorder } from "@/features/requests/recorder";
import { ConsoleSearchProviders } from "@/features/search/providers";
import { useSession } from "@/lib/session";
import { LinkedErrorState } from "@/features/errors/link";
import { useDemoRuns } from "@/features/evidence/demo-runs";
import { evidenceRecordView } from "@/features/evidence/evidence-record";
import { ObligationRef } from "./obligation-ref";
import { VerbatimNote } from "./verbatim-note";

/** Stable test ids for the assurance suite. */
export const ASSURANCE_VIEW_TEST_IDS = {
  root: "assurance-view",
  connectGate: "assurance-connect-gate",
  contractSection: "contract-assurance",
  evidenceChain: "assurance-evidence-chain",
  empty: "assurance-empty",
} as const;

interface AssuranceReadState {
  assurance: ContractAssurance | null;
  error: unknown;
}

export function AssuranceView() {
  const { status, client } = useSession();
  const connected = status === "connected";
  const runs = useDemoRuns();

  const [chain, setChain] = useState<ListResponse<Contract> | null>(null);
  const [chainError, setChainError] = useState<unknown>(null);
  const [chainLoading, setChainLoading] = useState(false);
  const [refreshTick, setRefreshTick] = useState(0);

  const [assuranceByContract, setAssuranceByContract] = useState<
    Record<string, AssuranceReadState>
  >({});

  useEffect(() => {
    ensureRequestRecorder();
  }, []);

  // the BODYLESS contracts list read (the browser-compatible form of the
  // frozen list discipline — pagination/filters ride the GET JSON body,
  // which browsers cannot send)
  useEffect(() => {
    if (!connected) return;
    let mounted = true;
    setChainLoading(true);
    setChainError(null);
    client
      .listContracts()
      .then((envelope) => {
        if (mounted) setChain(envelope.data);
      })
      .catch((error: unknown) => {
        if (mounted) {
          setChain(null);
          setChainError(error);
        }
      })
      .finally(() => {
        if (mounted) setChainLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [connected, client, refreshTick]);

  // one assurance read per listed contract (the reads are independent;
  // failures land per contract and never sink the whole page)
  useEffect(() => {
    if (!connected || chain === null) return;
    let mounted = true;
    const ids = chain.items.map((contract) => contract.id);
    void Promise.all(
      ids.map(async (id): Promise<[string, AssuranceReadState]> => {
        try {
          const envelope = await client.getContractAssurance(id);
          return [id, { assurance: envelope.data, error: null }];
        } catch (error) {
          return [id, { assurance: null, error }];
        }
      }),
    ).then((results) => {
      if (mounted) {
        setAssuranceByContract(Object.fromEntries(results));
      }
    });
    return () => {
      mounted = false;
    };
  }, [connected, client, chain]);

  const refresh = useCallback(() => {
    setRefreshTick((tick) => tick + 1);
  }, []);

  const contracts = chain?.items ?? [];

  // the demonstration runs' ATTESTATION records, keyed by contract_ref —
  // the evidence chain each obligation links to
  const attestationsByContract = new Map<string, {
    recordId: string;
    attestationKind: string;
    instant: string;
    producer: string;
    evidenceClass: string;
  }[]>();
  for (const run of runs) {
    for (const record of run.document.evidence ?? []) {
      const view = evidenceRecordView(record);
      if (view.record_type !== "attestation") continue;
      const key = view.contract_ref ?? "";
      const list = attestationsByContract.get(key) ?? [];
      list.push({
        recordId: view.record_id ?? "unknown record_id",
        attestationKind: view.attestation_kind ?? "unknown kind",
        instant: view.instant ?? "unknown instant",
        producer: view.producer ?? "unknown producer",
        evidenceClass: run.document.evidence_class,
      });
      attestationsByContract.set(key, list);
    }
  }

  const header = (
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold text-ink">Assurance</h1>
        <p className="mt-1 max-w-3xl text-sm text-ink-muted">
          Supported contract objectives — latency, throughput, availability,
          provider health — are the OBLIGATION REFERENCES the backend returns:
          opaque typed references with their provenance (GET
          /api/2.0/contracts/&#123;id&#125;/assurance). Semantics are
          referenced, never evaluated here — no metric dashboards are
          invented. The state machine records the outcomes; the assurance
          authority owns the obligations.
        </p>
      </div>
      {connected ? (
        <button
          type="button"
          onClick={refresh}
          disabled={chainLoading}
          className="inline-flex h-8 items-center gap-1.5 rounded-md border border-line-strong bg-raised px-3 text-sm text-ink transition-colors hover:bg-surface disabled:opacity-50"
        >
          <RefreshIcon size={14} />
          Refresh
        </button>
      ) : null}
    </header>
  );

  if (!connected) {
    return (
      <div
        className="mx-auto w-full max-w-workbench px-gutter py-rhythm"
        data-testid={ASSURANCE_VIEW_TEST_IDS.root}
      >
        <ConsoleSearchProviders />
        <div className="flex flex-col gap-4">
          {header}
          <div
            className="rounded-md border border-line bg-surface"
            data-testid={ASSURANCE_VIEW_TEST_IDS.connectGate}
          >
            <EmptyState
              title="Connect an application to continue"
              description={
                <span>
                  The assurance reads are authenticated developer-API reads
                  (GET /api/2.0/contracts and GET
                  /api/2.0/contracts/&#123;id&#125;/assurance with the session
                  headers). Open the session menu — or{" "}
                  <Link href="/settings" className="text-accent hover:underline">
                    Settings → Session
                  </Link>{" "}
                  — and connect with a backend-issued application id and
                  credential.
                </span>
              }
            />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className="mx-auto w-full max-w-workbench px-gutter py-rhythm"
      data-testid={ASSURANCE_VIEW_TEST_IDS.root}
    >
      <ConsoleSearchProviders />
      <div className="flex flex-col gap-4">
        {header}

        {chainError ? (
          <div className="rounded-md border border-line bg-surface">
            <LinkedErrorState
              error={chainError}
              onRetry={refresh}
              request={{ method: "GET", path: "/api/2.0/contracts" }}
            />
          </div>
        ) : null}

        {chainLoading && chain === null ? (
          <div aria-busy="true" className="flex flex-col gap-3">
            <div className="h-6 w-72 animate-pulse rounded bg-raised" />
            <div className="h-24 w-full animate-pulse rounded bg-raised" />
            <div className="h-24 w-full animate-pulse rounded bg-raised" />
          </div>
        ) : null}

        {!chainLoading && contracts.length === 0 && !chainError ? (
          <div
            className="rounded-md border border-line bg-surface"
            data-testid={ASSURANCE_VIEW_TEST_IDS.empty}
          >
            <EmptyState
              title="No contracts yet"
              description={
                <span>
                  Assurance is read per contract and this application has none.
                  Record your first connectivity intent with the{" "}
                  <Link
                    href="/connectivity/new"
                    className="text-accent hover:underline"
                  >
                    builder
                  </Link>{" "}
                  — or run the{" "}
                  <Link
                    href="/fulfillment"
                    className="text-accent hover:underline"
                  >
                    fulfillment demonstration
                  </Link>
                  , which creates one.
                </span>
              }
            />
          </div>
        ) : null}

        {contracts.map((contract) => {
          const read = assuranceByContract[contract.id];
          const assurance = read?.assurance ?? null;
          const attestations = attestationsByContract.get(contract.id) ?? [];
          return (
            <section
              key={contract.id}
              data-testid={ASSURANCE_VIEW_TEST_IDS.contractSection}
              data-contract-id={contract.id}
              className="rounded-md border border-line bg-surface"
            >
              <div className="border-b border-line px-4 py-3">
                <ObjectHeader
                  kind="contract"
                  title={contract.id}
                  copyValue={contract.id}
                  status={contract.state}
                  subtitle={
                    <span className="font-mono text-xs text-ink-muted">
                      assurance_obligations:{" "}
                      {assurance?.assurance_obligations.length ??
                        contract.assurance_obligations.length}{" "}
                      reference
                      {(assurance?.assurance_obligations.length ??
                        contract.assurance_obligations.length) === 1
                        ? ""
                        : "s"}
                    </span>
                  }
                  actions={
                    <Link
                      href={`/connectivity/contracts/${contract.id}`}
                      className="inline-flex h-8 items-center rounded-md border border-line-strong bg-raised px-3 text-sm text-ink transition-colors hover:bg-surface"
                    >
                      Open contract
                    </Link>
                  }
                />
              </div>

              <div className="flex flex-col gap-4 px-4 py-3">
                {read?.error ? (
                  <LinkedErrorState
                    error={read.error}
                    onRetry={refresh}
                    request={{
                      method: "GET",
                      path: `/api/2.0/contracts/${contract.id}/assurance`,
                    }}
                    compact
                  />
                ) : null}

                {assurance ? (
                  <>
                    <dl className="grid grid-cols-[max-content_1fr] items-baseline gap-x-4 gap-y-1.5">
                      <dt className="whitespace-nowrap font-mono text-2xs text-ink-faint">
                        contract_state
                      </dt>
                      <dd>
                        <Status value={assurance.contract_state} />
                      </dd>
                      <dt className="whitespace-nowrap font-mono text-2xs text-ink-faint">
                        evidence_class
                      </dt>
                      <dd className="flex items-center gap-2">
                        <EvidenceBadge evidenceClass={assurance.evidence_class} />
                        <span className="font-mono text-2xs text-ink-faint">
                          verbatim
                        </span>
                      </dd>
                      <dt className="whitespace-nowrap font-mono text-2xs text-ink-faint">
                        kind
                      </dt>
                      <dd className="font-mono text-xs text-ink-muted">
                        {assurance.kind}
                      </dd>
                    </dl>

                    <VerbatimNote note={assurance.note} label="assurance note" />

                    <div className="flex flex-col gap-2">
                      <p className="font-mono text-2xs text-ink-faint">
                        assurance_obligations (opaque references — VERBATIM)
                      </p>
                      {assurance.assurance_obligations.length === 0 ? (
                        <p className="text-sm text-ink-faint">
                          No obligation references on this contract.
                        </p>
                      ) : (
                        <ul className="grid gap-2 lg:grid-cols-2">
                          {assurance.assurance_obligations.map((obligation, index) => (
                            <ObligationRef
                              key={`${obligation.value}:${index}`}
                              obligation={obligation}
                              contractId={contract.id}
                            />
                          ))}
                        </ul>
                      )}
                    </div>
                  </>
                ) : (
                  <p className="text-sm text-ink-faint">
                    Loading the assurance observation…
                  </p>
                )}

                {/* the evidence chain ------------------------------------ */}
                <div
                  className="flex flex-col gap-2 rounded-md border border-line bg-raised px-3 py-3"
                  data-testid={ASSURANCE_VIEW_TEST_IDS.evidenceChain}
                  id={`evidence-chain-${contract.id}`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="text-sm font-semibold text-ink">
                      Evidence chain
                    </h3>
                    <Link
                      href="/evidence"
                      className="text-xs text-accent hover:underline"
                    >
                      open in Evidence →
                    </Link>
                  </div>
                  {attestations.length === 0 ? (
                    <p className="text-sm text-ink-muted">
                      No attestation records captured for this contract in this
                      console session yet — run the{" "}
                      <Link
                        href="/fulfillment"
                        className="text-accent hover:underline"
                      >
                        fulfillment demonstration
                      </Link>{" "}
                      to produce attestation evidence. Captured runs are
                      in-memory and cleared on reload.
                    </p>
                  ) : (
                    <ul className="flex flex-col gap-1.5">
                      {attestations.map((attestation) => (
                        <li
                          key={attestation.recordId}
                          className="flex flex-wrap items-center gap-2"
                        >
                          <span className="inline-flex items-center rounded border border-line-strong px-1.5 py-px font-mono text-2xs text-ink-muted">
                            attestation
                          </span>
                          <span
                            className="min-w-0 flex-1 truncate font-mono text-xs text-ink"
                            title={attestation.recordId}
                          >
                            {attestation.recordId}
                          </span>
                          <span className="font-mono text-2xs text-ink-muted">
                            {attestation.attestationKind}
                          </span>
                          <span className="font-mono text-2xs text-ink-faint">
                            {attestation.instant}
                          </span>
                          <EvidenceBadge
                            evidenceClass={attestation.evidenceClass}
                            size="sm"
                          />
                        </li>
                      ))}
                    </ul>
                  )}
                  <p className="text-xs text-ink-faint">
                    The demonstration runs&apos; attestation records whose
                    contract_ref matches this contract — display data from the
                    in-memory runs store, rendered with each run&apos;s
                    evidence_class verbatim.
                  </p>
                </div>
              </div>
            </section>
          );
        })}

        {chain?.has_more ? (
          <div
            data-testid="assurance-deeper-pagination-notice"
            className="rounded-md border border-dashed border-warning/60 bg-warning/5 px-3 py-2"
          >
            <p className="text-sm text-ink-muted">
              The backend reports more contract pages than shown. List
              pagination and filters ride the developer API&apos;s GET request
              JSON body — a form browsers cannot send (fetch forbids GET
              bodies), so the console shows the bodyless default page. Page
              through the API directly:
            </p>
            <div className="mt-2">
              <ApiRequestPanel
                variant="compact"
                method="GET"
                path="/api/2.0/contracts"
                body={{
                  limit: 20,
                  cursor: chain.next_cursor || "<next_cursor>",
                  filters: { state: "<state>" },
                }}
              />
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
