"use client";
import "@/features/eligibility/fetch-binding-shim";

/**
 * ContractDetailView — the full lifecycle chain (Worker 2, plan Task 5):
 * Requirements → Eligibility → Plan → Execution → Assurance → Continuous
 * fulfillment, plus the state-advancing action cards (accept offers /
 * activate), the termination drawer, the leases block (grant / renew /
 * revoke), an activity timeline derived from backend facts only, and the
 * raw contract JSON.
 *
 * Honesty rules baked in:
 * - every state value, note, evidence class and reason code renders
 *   VERBATIM (Status / EvidenceBadge / VerbatimNote / ErrorState);
 * - all five reads (contract, lifecycle, usage, assurance, leases) go
 *   through useAdcosRead — refresh re-fetches truth, and every mutation
 *   ends by refreshing ALL of them;
 * - hard constraints render exactly as the backend sent them (immutable,
 *   never editable here);
 * - physical connectivity is never claimed (the lifecycle's own
 *   physical_* members are rendered verbatim);
 * - "you performed X" timeline entries are clearly labeled as this
 *   console session's presentation, never as backend history.
 */

import { useState } from "react";
import Link from "next/link";
import type { AdcosEnvelope, Contract, Lease } from "@/lib/api/types";
import {
  DataTable,
  ErrorState,
  EvidenceBadge,
  ObjectHeader,
  RefreshIcon,
  Status,
  Timeline,
  type Column,
} from "@/components/ui";
import {
  FlowStatePanel,
  ObjectSection,
  RefList,
  RefValue,
  VerbatimNote,
  useAdcosRead,
} from "@/features/eligibility";
import { useSession } from "@/lib/session";
import { ConnectGuidance } from "./connect-guidance";
import {
  LeaseWindowDrawer,
  RevokeLeaseDrawer,
  TerminateDrawer,
} from "./contract-mutation-drawers";
import { AcceptOffersCard, ActivateCard } from "./next-step-cards";
import { nowRfc3339 } from "./mutation-form";

/** The terminal contract states (terminate/lease actions hide for these). */
const TERMINAL_CONTRACT_STATES = new Set(["TERMINATED", "EXPIRED", "FAILED"]);

/** Lease states that accept renew/revoke (backend vocabulary). */
const LEASE_ACTIONABLE_STATES = new Set(["granted", "active"]);

interface SessionAction {
  id: string;
  title: string;
  time: string;
}

type LeaseDrawerState =
  | { mode: "grant" }
  | { mode: "renew"; lease: Lease }
  | { mode: "revoke"; lease: Lease }
  | null;

export function ContractDetailView({ contractId }: { contractId: string }) {
  const { status, client } = useSession();
  const connected = status === "connected";

  const contractRead = useAdcosRead(
    connected ? () => client.getContract(contractId).then((envelope) => envelope.data) : null,
    [client, contractId],
  );
  const lifecycleRead = useAdcosRead(
    connected
      ? () => client.getIntentLifecycle(contractId).then((envelope) => envelope.data)
      : null,
    [client, contractId],
  );
  const usageRead = useAdcosRead(
    connected
      ? () => client.getContractUsage(contractId).then((envelope) => envelope.data)
      : null,
    [client, contractId],
  );
  const assuranceRead = useAdcosRead(
    connected
      ? () => client.getContractAssurance(contractId).then((envelope) => envelope.data)
      : null,
    [client, contractId],
  );
  const leasesRead = useAdcosRead(
    // bodyless list read (the browser-compatible form; filtered
    // client-side by contract_id below)
    connected ? () => client.listLeases().then((envelope) => envelope.data) : null,
    [client, contractId],
  );

  const contract = contractRead.data ?? null;
  const lifecycle = lifecycleRead.data ?? null;
  const usage = usageRead.data ?? null;
  const assurance = assuranceRead.data ?? null;

  function refreshAll() {
    contractRead.refresh();
    lifecycleRead.refresh();
    usageRead.refresh();
    assuranceRead.refresh();
    leasesRead.refresh();
  }

  // presentation-only: the mutations THIS console session performed
  const [sessionActions, setSessionActions] = useState<SessionAction[]>([]);
  function recordAction(title: string) {
    setSessionActions((previous) => [
      ...previous,
      { id: `session-action-${previous.length}`, title, time: nowRfc3339() },
    ]);
  }

  const [terminateOpen, setTerminateOpen] = useState(false);
  const [leaseDrawer, setLeaseDrawer] = useState<LeaseDrawerState>(null);

  /* ---------------------------------------------------------------- */

  if (!connected) {
    return (
      <div className="mx-auto w-full max-w-workbench px-gutter py-rhythm">
        <div className="flex flex-col gap-4">
          <Link href="/connectivity" className="text-sm text-accent hover:underline">
            ← Connectivity
          </Link>
          <ConnectGuidance lead="The contract detail reads (contract, lifecycle, usage, assurance, leases) are authenticated developer-API reads." />
        </div>
      </div>
    );
  }

  if (!contract) {
    if (contractRead.error) {
      return (
        <div className="mx-auto w-full max-w-workbench px-gutter py-rhythm">
          <div className="flex flex-col gap-3">
            <Link href="/connectivity" className="text-sm text-accent hover:underline">
              ← Connectivity
            </Link>
            <div className="rounded-md border border-line bg-surface">
              <ErrorState error={contractRead.error} onRetry={contractRead.refresh} />
              <div className="px-4 pb-4">
                <Link href="/connectivity" className="text-sm text-accent hover:underline">
                  Back to Connectivity
                </Link>
              </div>
            </div>
          </div>
        </div>
      );
    }
    return (
      <div
        className="mx-auto w-full max-w-workbench px-gutter py-rhythm"
        data-testid="contract-detail-loading"
        aria-busy="true"
      >
        <div className="flex flex-col gap-3">
          <div className="h-6 w-72 animate-pulse rounded bg-raised" />
          <div className="h-4 w-52 animate-pulse rounded bg-raised" />
          <div className="h-24 w-full animate-pulse rounded bg-raised" />
          <div className="h-24 w-full animate-pulse rounded bg-raised" />
        </div>
      </div>
    );
  }

  const isTerminal = TERMINAL_CONTRACT_STATES.has(contract.state);

  // leases are listed application-wide and filtered client-side by
  // contract_id (the leases list discipline has no contract filter)
  const leases = (leasesRead.data?.items ?? []).filter(
    (lease) => lease.contract_id === contract.id,
  );

  const leaseColumns: Column<Lease>[] = [
    {
      key: "lease",
      header: "Lease",
      accessor: (lease) => lease.id,
      render: (lease) => (
        <span
          className="block max-w-[16rem] truncate font-mono text-xs text-ink"
          title={lease.id}
        >
          {lease.id}
        </span>
      ),
    },
    {
      key: "state",
      header: "State",
      accessor: (lease) => lease.state,
      render: (lease) => (
        <span className="flex items-center gap-2">
          <Status value={lease.state} />
          {lease.revocation_reason ? (
            <span className="font-mono text-2xs text-ink-faint">
              reason {lease.revocation_reason}
            </span>
          ) : null}
        </span>
      ),
    },
    {
      key: "window",
      header: "Window",
      accessor: (lease) => lease.not_before,
      render: (lease) => (
        <span className="whitespace-nowrap font-mono text-xs text-ink-muted">
          {lease.not_before} → {lease.not_after}
        </span>
      ),
    },
    {
      key: "granted",
      header: "Granted",
      accessor: (lease) => lease.granted_at,
      render: (lease) => (
        <span className="whitespace-nowrap font-mono text-xs text-ink-muted">
          {lease.granted_at}
        </span>
      ),
    },
    {
      key: "actions",
      header: "Actions",
      render: (lease) =>
        LEASE_ACTIONABLE_STATES.has(lease.state) ? (
          <span className="flex items-center justify-end gap-1.5">
            <button
              type="button"
              onClick={() => setLeaseDrawer({ mode: "renew", lease })}
              className="inline-flex h-7 items-center rounded-md border border-line px-2 text-xs text-ink-muted transition-colors hover:text-ink"
            >
              Renew
            </button>
            <button
              type="button"
              onClick={() => setLeaseDrawer({ mode: "revoke", lease })}
              className="inline-flex h-7 items-center rounded-md border border-danger px-2 text-xs text-danger transition-colors hover:bg-danger/10"
            >
              Revoke
            </button>
          </span>
        ) : (
          <span className="text-xs text-ink-faint">—</span>
        ),
      align: "right",
    },
  ];

  const timelineItems = [
    ...(lifecycle
      ? [
          {
            id: "lifecycle-entered",
            time: lifecycle.entered_at,
            title: `Entered ${lifecycle.contract_state}`,
            tone: lifecycle.contract_state,
          },
        ]
      : []),
    {
      id: "command-count",
      title: `${contract.command_count} commands recorded`,
    },
    ...sessionActions.map((action) => ({
      id: action.id,
      time: action.time,
      title: action.title,
      description: "you performed this from the console session (presentation only)",
    })),
  ];

  return (
    <div className="mx-auto w-full max-w-workbench px-gutter py-rhythm">
      <div className="flex flex-col gap-6">
        <Link href="/connectivity" className="text-sm text-accent hover:underline">
          ← Connectivity
        </Link>

        {contractRead.error ? (
          <ErrorState error={contractRead.error} onRetry={contractRead.refresh} compact />
        ) : null}

        <ObjectHeader
          kind="contract"
          title={contract.id}
          copyValue={contract.id}
          status={contract.state}
          subtitle={
            <span className="font-mono text-xs">
              validity {contract.validity.not_before} → {contract.validity.not_after}
            </span>
          }
          meta={[
            {
              label: "environment",
              value: <span className="font-mono text-xs">{contract.environment}</span>,
            },
            {
              label: "principal",
              value: (
                <span className="font-mono text-xs">
                  {contract.principal.principal_kind} · {contract.principal.principal_ref}
                </span>
              ),
            },
            {
              label: "command_count",
              value: <span className="font-mono text-xs">{contract.command_count}</span>,
            },
            {
              label: "contract_id",
              value: <span className="font-mono text-xs">{contract.contract_id}</span>,
            },
          ]}
          actions={
            <button
              type="button"
              onClick={refreshAll}
              className="inline-flex h-8 items-center gap-1.5 rounded-md border border-line-strong bg-raised px-3 text-sm text-ink transition-colors hover:bg-surface"
            >
              <RefreshIcon size={14} />
              Refresh
            </button>
          }
        />

        {contract.state === "INTENT" ? (
          <AcceptOffersCard
            contract={contract}
            onDone={(envelope: AdcosEnvelope<Contract>) => {
              recordAction(`You accepted offers (${envelope.data.state})`);
              refreshAll();
            }}
          />
        ) : null}
        {contract.state === "OFFER_SELECTED" ? (
          <ActivateCard
            contract={contract}
            onDone={(envelope: AdcosEnvelope<Contract>) => {
              recordAction(`You activated the contract (${envelope.data.state})`);
              refreshAll();
            }}
          />
        ) : null}

        {/* 1 · Requirements ------------------------------------------- */}
        <ObjectSection
          id="requirements"
          title="1 · Requirements"
          description="The recorded intent material: requirement references, beneficiaries, and the immutable hard constraints."
          json={{
            requirements: contract.requirements,
            hard_constraints: contract.hard_constraints,
          }}
        >
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <p className="font-mono text-2xs text-ink-faint">requirements</p>
              <RefList references={contract.requirements} />
            </div>
            <div className="flex flex-col gap-1.5">
              <p className="font-mono text-2xs text-ink-faint">beneficiaries</p>
              {contract.beneficiaries.length === 0 ? (
                <p className="text-sm text-ink-faint">none recorded</p>
              ) : (
                <ul className="flex flex-wrap gap-1.5">
                  {contract.beneficiaries.map((beneficiary, index) => (
                    <li
                      key={`${beneficiary.beneficiary_kind}:${beneficiary.beneficiary_ref}:${index}`}
                      className="rounded border border-line bg-raised px-2 py-1 font-mono text-2xs text-ink"
                    >
                      {beneficiary.beneficiary_kind} · {beneficiary.beneficiary_ref}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="flex flex-col gap-1.5">
              <p className="font-mono text-2xs text-ink-faint">hard_constraints</p>
              {contract.hard_constraints.length === 0 ? (
                <p className="text-sm text-ink-faint">none recorded</p>
              ) : (
                <div className="overflow-x-auto rounded-md border border-line">
                  <table className="w-full text-sm" data-testid="hard-constraints-table">
                    <thead>
                      <tr className="border-b border-line bg-raised text-left">
                        <th
                          scope="col"
                          className="px-3 py-1.5 text-xs font-normal text-ink-faint"
                        >
                          kind
                        </th>
                        <th
                          scope="col"
                          className="px-3 py-1.5 text-xs font-normal text-ink-faint"
                        >
                          params
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {contract.hard_constraints.map((constraint, index) => (
                        <tr
                          key={`${constraint.kind}:${index}`}
                          className="border-b border-line last:border-b-0"
                        >
                          <td className="px-3 py-1.5 align-top">
                            {/* verbatim kind — no text-transform so the
                                backend vocabulary renders exactly as sent */}
                            <span className="inline-flex items-center rounded border border-line-strong px-1.5 py-px font-mono text-2xs text-ink-muted">
                              {constraint.kind}
                            </span>
                          </td>
                          <td className="px-3 py-1.5 align-top">
                            <div className="flex flex-wrap gap-x-4 gap-y-1">
                              {Object.entries(constraint.params).map(([key, value]) => (
                                <span
                                  key={key}
                                  data-testid="constraint-param"
                                  className="font-mono text-xs text-ink"
                                >
                                  {key}: {String(value)}
                                </span>
                              ))}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <p className="text-xs text-ink-faint">
                Hard constraints are immutable after creation and pass through the API
                unchanged.
              </p>
            </div>
          </div>
        </ObjectSection>

        {/* 2 · Eligibility --------------------------------------------- */}
        <ObjectSection
          id="eligibility"
          title="2 · Eligibility"
          description="Why the flow state is what it is — the lifecycle projection's own statements, and the referenced usage semantics."
        >
          <div className="flex flex-col gap-4">
            {lifecycleRead.error ? (
              <ErrorState error={lifecycleRead.error} onRetry={lifecycleRead.refresh} compact />
            ) : null}
            {lifecycle ? (
              <FlowStatePanel lifecycle={lifecycle} />
            ) : (
              <p className="text-sm text-ink-faint">Loading the lifecycle observation…</p>
            )}
            {usageRead.error ? (
              <ErrorState error={usageRead.error} onRetry={usageRead.refresh} compact />
            ) : null}
            {usage ? (
              <div className="flex flex-col gap-2">
                <p className="text-xs text-ink-faint">
                  usage semantics are referenced, never interpreted
                </p>
                <p className="font-mono text-2xs text-ink-faint">
                  usage_pricing_terms
                </p>
                <RefValue reference={usage.usage_pricing_terms} />
                <VerbatimNote note={usage.note} label="usage note" />
              </div>
            ) : (
              <p className="text-sm text-ink-faint">Loading the usage terms…</p>
            )}
          </div>
        </ObjectSection>

        {/* 3 · Plan ---------------------------------------------------- */}
        <ObjectSection
          id="plan"
          title="3 · Plan"
          description="Plan material binds as opaque typed references — the execution-artifact reference IS the plan binding."
        >
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <p className="font-mono text-2xs text-ink-faint">execution_scope</p>
              <RefList references={contract.execution_scope} />
            </div>
            <div className="flex flex-col gap-1.5">
              <p className="font-mono text-2xs text-ink-faint">execution_artifacts</p>
              <RefList
                references={contract.execution_artifacts}
                emptyLabel="no execution artifact bound yet — no plan is bound"
              />
              {contract.execution_artifacts.length > 0 ? (
                <p className="text-xs text-ink-muted">
                  The bound artifact reference is the plan.
                </p>
              ) : null}
            </div>
          </div>
        </ObjectSection>

        {/* 4 · Execution ------------------------------------------------ */}
        <ObjectSection
          id="execution"
          title="4 · Execution"
          description="The execution observation from the lifecycle projection — physical connectivity is never claimed by API success."
        >
          {lifecycle ? (
            <div className="flex flex-col gap-3">
              <dl className="grid grid-cols-[minmax(13rem,auto)_1fr] items-baseline gap-x-4 gap-y-2">
                <dt className="font-mono text-2xs text-ink-faint">execution_status</dt>
                <dd className="font-mono text-xs text-ink">
                  {lifecycle.execution_status}
                </dd>
                <dt className="font-mono text-2xs text-ink-faint">evidence_class</dt>
                <dd>
                  <EvidenceBadge evidenceClass={lifecycle.evidence_class} />
                </dd>
                <dt className="font-mono text-2xs text-ink-faint">
                  physical_connectivity_observed
                </dt>
                <dd className="font-mono text-xs text-ink">
                  {String(lifecycle.physical_connectivity_observed)}
                </dd>
                <dt className="font-mono text-2xs text-ink-faint">physical_evidence</dt>
                <dd className="font-mono text-xs text-ink">
                  {lifecycle.physical_evidence}
                </dd>
              </dl>
              <div className="flex flex-col gap-1.5">
                <p className="font-mono text-2xs text-ink-faint">
                  execution_artifact_refs
                </p>
                <RefList references={lifecycle.execution_artifact_refs} />
              </div>
              <p className="text-xs text-ink-faint">
                Rendered verbatim from the lifecycle observation — physical
                connectivity is never claimed here.
              </p>
              <div>
                <Link href="/fulfillment" className="text-sm text-accent hover:underline">
                  See the fulfillment demonstration for the full execution chain
                </Link>
              </div>
            </div>
          ) : (
            <p className="text-sm text-ink-faint">
              Loading the execution observation…
            </p>
          )}
        </ObjectSection>

        {/* 5 · Assurance ------------------------------------------------ */}
        <ObjectSection
          id="assurance"
          title="5 · Assurance"
          description="Referenced assurance obligations — semantics are referenced, never evaluated here; the state machine records the outcomes."
        >
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <p className="font-mono text-2xs text-ink-faint">
                assurance_obligations (from the contract)
              </p>
              <RefList references={contract.assurance_obligations} />
            </div>
            {assuranceRead.error ? (
              <ErrorState
                error={assuranceRead.error}
                onRetry={assuranceRead.refresh}
                compact
              />
            ) : null}
            {assurance ? (
              <div className="flex flex-col gap-2">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-2xs text-ink-faint">
                    contract_state
                  </span>
                  <Status value={assurance.contract_state} />
                </div>
                <VerbatimNote note={assurance.note} label="assurance note" />
              </div>
            ) : (
              <p className="text-sm text-ink-faint">
                Loading the assurance observation…
              </p>
            )}
          </div>
        </ObjectSection>

        {/* 6 · Continuous fulfillment ----------------------------------- */}
        <ObjectSection
          id="continuous-fulfillment"
          title="6 · Continuous fulfillment"
          description="The validity window, the termination rules, and the leases that hold connectivity within the window."
          actions={
            isTerminal ? null : (
              <button
                type="button"
                onClick={() => setTerminateOpen(true)}
                className="inline-flex h-8 items-center rounded-md border border-danger px-3 text-sm text-danger transition-colors hover:bg-danger/10"
              >
                Terminate contract
              </button>
            )
          }
        >
          <div className="flex flex-col gap-4">
            <dl className="grid grid-cols-[minmax(10rem,auto)_1fr] items-baseline gap-x-4 gap-y-2">
              <dt className="font-mono text-2xs text-ink-faint">
                validity.not_before
              </dt>
              <dd className="font-mono text-xs text-ink">
                {contract.validity.not_before}
              </dd>
              <dt className="font-mono text-2xs text-ink-faint">
                validity.not_after
              </dt>
              <dd className="font-mono text-xs text-ink">
                {contract.validity.not_after}
              </dd>
            </dl>
            <div className="flex flex-col gap-1.5">
              <p className="font-mono text-2xs text-ink-faint">
                termination.conditions (the contract&apos;s own vocabulary)
              </p>
              <ul className="flex flex-wrap gap-1.5">
                {contract.termination.conditions.map((condition) => (
                  <li
                    key={condition}
                    className="rounded border border-line bg-raised px-1.5 py-px font-mono text-2xs text-ink-muted"
                  >
                    {condition}
                  </li>
                ))}
              </ul>
            </div>
            <div className="flex flex-col gap-1.5">
              <p className="font-mono text-2xs text-ink-faint">
                termination.compensation
              </p>
              <RefValue reference={contract.termination.compensation} />
            </div>

            <div
              className="flex flex-col gap-3 rounded-md border border-line bg-raised px-3 py-3"
              data-testid="leases-block"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-sm font-semibold text-ink">Leases</h3>
                {!isTerminal ? (
                  <button
                    type="button"
                    onClick={() => setLeaseDrawer({ mode: "grant" })}
                    className="inline-flex h-8 items-center rounded-md border border-line-strong bg-surface px-3 text-sm text-ink transition-colors hover:bg-surface"
                  >
                    Grant lease
                  </button>
                ) : null}
              </div>
              <p className="text-xs leading-relaxed text-ink-faint">
                Renew and Revoke apply to granted/active leases only — the backend
                rejects others with <span className="font-mono">invalid-input</span>{" "}
                (&quot;only granted/active leases revoke (found renewed)&quot;). Lease
                windows must lie inside the contract validity window.
              </p>
              <DataTable
                rows={leases}
                columns={leaseColumns}
                getRowKey={(lease) => lease.id}
                loading={leasesRead.loading}
                error={leasesRead.error}
                onRetry={leasesRead.refresh}
                emptyTitle="No leases on this contract"
                emptyDescription="Grant a lease to hold connectivity within the contract validity window."
              />
            </div>
          </div>
        </ObjectSection>

        {/* Activity ------------------------------------------------------ */}
        <ObjectSection
          id="activity"
          title="Activity"
          description="Derived from backend facts only: the lifecycle projection and the command count the backend recorded."
        >
          <Timeline items={timelineItems} />
        </ObjectSection>

        {/* Raw contract -------------------------------------------------- */}
        <ObjectSection
          id="raw-contract"
          title="Raw contract"
          description="The canonical contract resource exactly as GET /api/2.0/contracts/{id} returned it."
          json={contract}
          jsonName="contract"
        />
      </div>

      {terminateOpen ? (
        <TerminateDrawer
          contract={contract}
          onClose={() => setTerminateOpen(false)}
          onDone={(envelope: AdcosEnvelope<Contract>) => {
            recordAction(`You terminated the contract (${envelope.data.state})`);
            refreshAll();
          }}
        />
      ) : null}
      {leaseDrawer?.mode === "grant" ? (
        <LeaseWindowDrawer
          mode="grant"
          contract={contract}
          onClose={() => setLeaseDrawer(null)}
          onDone={(envelope: AdcosEnvelope<Lease>) => {
            recordAction(`You granted a lease (${envelope.data.state})`);
            refreshAll();
          }}
        />
      ) : null}
      {leaseDrawer?.mode === "renew" ? (
        <LeaseWindowDrawer
          mode="renew"
          contract={contract}
          lease={leaseDrawer.lease}
          onClose={() => setLeaseDrawer(null)}
          onDone={(envelope: AdcosEnvelope<Lease>) => {
            recordAction(`You renewed a lease (${envelope.data.state})`);
            refreshAll();
          }}
        />
      ) : null}
      {leaseDrawer?.mode === "revoke" ? (
        <RevokeLeaseDrawer
          lease={leaseDrawer.lease}
          onClose={() => setLeaseDrawer(null)}
          onDone={(envelope: AdcosEnvelope<Lease>) => {
            recordAction(`You revoked a lease (${envelope.data.state})`);
            refreshAll();
          }}
        />
      ) : null}
    </div>
  );
}
