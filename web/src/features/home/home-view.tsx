"use client";

/**
 * HomeView — the entry surface that adapts to who is looking (the V2
 * learning-experience design §5/§13/§15; plan Task 4), while keeping the
 * V1 workbench fully intact for returning experts:
 *
 * - DISCONNECTED (fresh visitor): the product-education surface — what
 *   ADCOS does, the clickable lifecycle, one-contract/many-networks, the
 *   eight goal paths — mounted FIRST, before any operational card, with
 *   the obvious next action (Quickstart / demonstration / connect);
 * - CONNECTED-AND-EMPTY: the same education plus the obvious "create
 *   your first contract" path;
 * - CONNECTED-WITH-CONTRACTS: the V1 expert dashboard, unchanged — the
 *   education surface does not mount at all;
 * - DEGRADED coordination (readyz): the education surface carries the
 *   honest degraded note (V1 system-health vocabulary) — education
 *   describes the product, never the current runtime state.
 *
 * The operational answers stay exactly as V1 built them: readiness
 * (platform read, no session), managed connectivity (authenticated read
 * gated on the session — never fired while disconnected), what is
 * changing, what needs attention, and the deterministic demonstration.
 * NO vanity KPIs: every number and row links to the underlying resource.
 * React state holds presentation only — refresh re-fetches truth through
 * useAdcosRead; there is deliberately no cache.
 *
 * The DEC-0128 program, Tasks 4-5 wave, Task 4 of the frozen plan.
 */

import { useEffect } from "react";
import { useSession } from "@/lib/session";
import type { Contract, Readiness } from "@/lib/api/types";
import { useAdcosRead } from "@/features/eligibility";
import { registerCommand } from "@/features/search";
import { SystemHealthCard } from "./system-health-card";
import { ContractsSummaryCard } from "./contracts-summary-card";
import { ActivityCard } from "./activity-card";
import { AttentionCard } from "./attention-card";
import { DemoCard } from "./demo-card";
import { FirstRunCard } from "./first-run-card";

export function HomeView() {
  const { status, client } = useSession();
  const connected = status === "connected";

  // platform read — works without a session (GET /readyz)
  const readinessRead = useAdcosRead<Readiness>(() => client.readyz(), [
    client,
  ]);

  // authenticated read — suspended (null fetcher) until a session exists,
  // so the contracts route is NEVER called while disconnected. The
  // BODYLESS list form (the backend's default page) is the only one a
  // browser can send: the API's list pagination rides the GET request's
  // JSON body, which fetch refuses to transmit (disclosed in the report).
  const contractsRead = useAdcosRead(
    connected ? () => client.listContracts() : null,
    [client, connected],
  );
  const contracts: Contract[] | null =
    contractsRead.data?.data?.items ?? null;

  // one palette entry: the demonstration is one command away
  useEffect(
    () =>
      registerCommand({
        id: "home-run-demo",
        title: "Run the fulfillment demonstration",
        group: "Actions",
        href: "/fulfillment",
      }),
    [],
  );

  // The V1 fresh-account logic, evolved honestly (plan Task 4): the
  // education surface shows for disconnected visitors AND for connected
  // sessions whose contract list has genuinely loaded EMPTY — a failed
  // or still-loading list never claims emptiness. Connected sessions
  // with contracts keep the expert workbench primary (design §2/§20).
  const freshAccount =
    connected && contractsRead.loaded && contracts !== null && contracts.length === 0;
  const showEducation = !connected || freshAccount;

  return (
    <div className="mx-auto w-full max-w-workbench px-gutter py-rhythm">
      {showEducation ? (
        <header className="mb-6">
          <h1 className="text-xl font-semibold">Welcome to ADCOS</h1>
          <p className="mt-1 text-sm text-ink-muted">
            The product, the mental model, and where you want to go next —
            no prior ADCOS knowledge assumed. Experts: the workbench cards
            below stay, and the navigation keeps every V1 surface one click
            away.
          </p>
        </header>
      ) : (
        <header className="mb-6">
          <h1 className="text-xl font-semibold">Home</h1>
          <p className="mt-1 text-sm text-ink-muted">
            The ADCOS workbench at a glance — runtime health, managed
            connectivity, what is changing and what needs attention. Every
            number links to the resource behind it.
          </p>
        </header>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {showEducation ? (
          <FirstRunCard
            connected={connected}
            hasContracts={contracts !== null && contracts.length > 0}
            readiness={readinessRead.data}
            readinessError={readinessRead.error}
            className="md:col-span-2"
          />
        ) : null}
        <SystemHealthCard read={readinessRead} className="md:col-span-2" />
        <ContractsSummaryCard read={contractsRead} connected={connected} />
        <ActivityCard contracts={contracts} connected={connected} />
        <AttentionCard
          contracts={contracts}
          readiness={readinessRead.data}
          connected={connected}
        />
        <DemoCard />
      </div>
    </div>
  );
}
