"use client";

/**
 * HomeView — the dashboard that answers, immediately and honestly:
 *
 * 1. is ADCOS healthy (platform readiness, no session required);
 * 2. what connectivity is managed (authenticated contracts read, gated
 *    on the session — never fired while disconnected);
 * 3. what is changing (latest contracts + this session's API log);
 * 4. what needs attention (contracts awaiting a decision, backends the
 *    runtime reports as not ready);
 * 5. the deterministic fulfillment demonstration.
 *
 * NO vanity KPIs: every number and row links to the underlying resource.
 * React state holds presentation only — refresh re-fetches truth through
 * useAdcosRead; there is deliberately no cache.
 */

import { useEffect } from "react";
import { useSession } from "@/lib/session";
import type {
  AdcosEnvelope,
  ListResponse,
  Contract,
  Readiness,
} from "@/lib/api/types";
import { useAdcosRead } from "@/features/eligibility";
import { registerCommand } from "@/features/search";
import { SystemHealthCard } from "./system-health-card";
import { ContractsSummaryCard } from "./contracts-summary-card";
import { ActivityCard } from "./activity-card";
import { AttentionCard } from "./attention-card";
import { DemoCard } from "./demo-card";
import { GettingStartedCard } from "./getting-started-card";

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

  const freshAccount =
    connected && contractsRead.loaded && contracts !== null && contracts.length === 0;

  return (
    <div className="mx-auto w-full max-w-workbench px-gutter py-rhythm">
      <header className="mb-6">
        <h1 className="text-xl font-semibold">Home</h1>
        <p className="mt-1 text-sm text-ink-muted">
          The ADCOS workbench at a glance — runtime health, managed
          connectivity, what is changing and what needs attention. Every
          number links to the resource behind it.
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-2">
        <SystemHealthCard read={readinessRead} className="md:col-span-2" />
        {freshAccount ? <GettingStartedCard className="md:col-span-2" /> : null}
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
