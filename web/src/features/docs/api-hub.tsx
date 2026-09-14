"use client";

/**
 * ApiHub — the API documentation hub, GENERATED from the accepted
 * coverage registry (`@/lib/api/coverage`) joined with the Task-1
 * operation education (`@/lib/education`): every one of the 25
 * operations of the accepted boundary, grouped by lifecycle area
 * (application, contracts, offers, leases, webhooks, platform —
 * grouping by the registry's own route/uiLocation vocabulary, the
 * Explorer's own style), each linking to its operation page.
 *
 * The Console V2 documentation system — the DEC-0128 program, Task 3 of
 * the frozen plan. An operation outside the registry can never appear
 * here (no invented endpoints); execution belongs to the API Explorer —
 * these pages document, the Explorer executes.
 */

import { useState } from "react";
import Link from "next/link";
import {
  COVERAGE,
  developerOperations,
  platformOperations,
  type CoverageRecord,
} from "@/lib/api/coverage";
import { EmptyState } from "@/components/ui";
import { DocsContextSlot } from "./docs-context";
import { matchesDocsTerm, MethodChip } from "./docs-shared";
import { DocsSearch } from "./docs-search";

/** Stable test ids for the API hub. */
export const API_HUB_TEST_IDS = {
  root: "api-hub",
  group: "api-hub-group",
  row: "api-hub-row",
  empty: "api-hub-empty",
} as const;

/** Grouping by lifecycle area (registry-derived tests, first match wins). */
const API_GROUPS: {
  id: string;
  label: string;
  description: string;
  test: (record: CoverageRecord) => boolean;
}[] = [
  {
    id: "application",
    label: "Application & authentication",
    description:
      "The authenticated application — identity, environment and the capability grants that unlock operations. The first authenticated call.",
    test: (record) => !record.platform && record.operation === "application_self",
  },
  {
    id: "offers",
    label: "Offers",
    description:
      "Accepting opaque typed offer references onto an intent — the bridge from requirement to plan (OFFER_SELECTED).",
    test: (record) => !record.platform && record.operation === "offers_accept",
  },
  {
    id: "contracts",
    label: "Contracts",
    description:
      "The contract lifecycle — recording intents, activation, the canonical reads (including usage and assurance), and termination.",
    test: (record) =>
      !record.platform &&
      (record.path.startsWith("/api/2.0/intents") ||
        record.path.startsWith("/api/2.0/contracts")),
  },
  {
    id: "leases",
    label: "Leases",
    description: "Bounded access windows granted over an active contract.",
    test: (record) => !record.platform && record.path.startsWith("/api/2.0/leases"),
  },
  {
    id: "webhooks",
    label: "Webhooks",
    description:
      "Webhook endpoint registration and the per-endpoint delivery attempts.",
    test: (record) =>
      !record.platform && record.path.startsWith("/api/2.0/webhook-endpoints"),
  },
  {
    id: "platform",
    label: "Platform surfaces",
    description:
      "The unauthenticated platform routes — liveness, readiness, the deterministic demonstration and the platform-side contract read.",
    test: (record) => record.platform,
  },
];

function ApiHubRow({ record }: { record: CoverageRecord }) {
  return (
    <li data-testid={API_HUB_TEST_IDS.row} data-operation={record.operation}>
      <Link
        href={`/docs/api/${record.operation}`}
        className="flex flex-col gap-1 px-4 py-2.5 transition-colors hover:bg-raised/40"
      >
        <span className="flex min-w-0 items-center gap-2">
          <MethodChip method={record.method} />
          <span className="min-w-0 break-all font-mono text-xs text-ink">{record.path}</span>
          <span className="ml-auto hidden shrink-0 font-mono text-2xs text-ink-faint sm:inline">
            {record.operation}
          </span>
        </span>
        <span className="text-sm leading-relaxed text-ink-muted">{record.description}</span>
      </Link>
    </li>
  );
}

export function ApiHub() {
  const [term, setTerm] = useState("");

  const filtered = COVERAGE.filter((record) =>
    matchesDocsTerm(term, [
      record.operation,
      record.method,
      record.path,
      record.description,
    ]),
  );

  // First match wins (the documented grouping contract): a record joins the
  // FIRST group whose test it satisfies, so an operation can never be listed
  // twice (offers_accept lives under /api/2.0/intents/.../offers but belongs
  // to the Offers group, not Contracts).
  const groups = API_GROUPS.map((group, index) => ({
    ...group,
    records: filtered.filter(
      (record) =>
        group.test(record) &&
        !API_GROUPS.slice(0, index).some((earlier) => earlier.test(record)),
    ),
  })).filter((group) => group.records.length > 0);

  const otherRecords = filtered.filter(
    (record) => !API_GROUPS.some((group) => group.test(record)),
  );

  return (
    <div data-testid={API_HUB_TEST_IDS.root} className="mx-auto w-full max-w-5xl px-gutter py-rhythm">
      <DocsContextSlot />
      <h1 className="text-xl font-semibold text-ink">API documentation</h1>
      <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-muted">
        Every operation of the accepted boundary — {COVERAGE.length} in all:{" "}
        {developerOperations().length} developer-API operations (versioned,
        authenticated, capability-gated) and {platformOperations().length}{" "}
        platform surfaces (unauthenticated) — generated from the coverage
        registry, so an unsupported operation can never appear here. Each
        operation page carries its education: purpose, prerequisites,
        lifecycle position, field explanations and the canonical reason codes
        it can produce.
      </p>
      <p className="mt-2 text-sm leading-relaxed text-ink-muted">
        Execution belongs to the{" "}
        <Link href="/developers/explorer" className="text-accent hover:underline">
          API Explorer
        </Link>{" "}
        — the docs document; the Explorer runs the real requests.
      </p>
      <div className="mt-5">
        <DocsSearch
          value={term}
          onChange={setTerm}
          placeholder="Filter operations"
          hint={
            term.trim().length > 0
              ? `${filtered.length}/${COVERAGE.length}`
              : `${COVERAGE.length} operations`
          }
        />
      </div>
      <div className="mt-6 flex flex-col gap-5">
        {filtered.length === 0 ? (
          <div data-testid={API_HUB_TEST_IDS.empty}>
            <EmptyState
              title="No operation matches"
              description={
                <>
                  No operation in the coverage registry matches{" "}
                  <span className="font-mono text-ink">{term.trim()}</span>.
                  The registry is the accepted boundary — an operation outside
                  it does not exist to document.
                </>
              }
              action={
                <button
                  type="button"
                  onClick={() => setTerm("")}
                  className="rounded border border-line-strong bg-raised px-3 py-1.5 text-sm text-ink transition-colors hover:bg-surface"
                >
                  Clear filter
                </button>
              }
            />
          </div>
        ) : (
          <>
            {groups.map((group) => (
              <section
                key={group.id}
                id={`group-${group.id}`}
                data-testid={API_HUB_TEST_IDS.group}
                data-group={group.id}
                aria-labelledby={`group-${group.id}-heading`}
              >
                <h2
                  id={`group-${group.id}-heading`}
                  className="text-2xs font-normal uppercase tracking-wide text-ink-faint"
                >
                  {group.label}
                  <span className="ml-2 font-mono normal-case">
                    {group.records.length}
                  </span>
                </h2>
                <p className="mt-1 max-w-2xl text-sm leading-relaxed text-ink-muted">
                  {group.description}
                </p>
                <ul className="mt-2 flex flex-col divide-y divide-line rounded-md border border-line bg-surface">
                  {group.records.map((record) => (
                    <ApiHubRow key={record.operation} record={record} />
                  ))}
                </ul>
              </section>
            ))}
            {otherRecords.length > 0 ? (
              <section aria-label="Other areas">
                <h2 className="text-2xs font-normal uppercase tracking-wide text-ink-faint">
                  Other areas
                </h2>
                <ul className="mt-2 flex flex-col divide-y divide-line rounded-md border border-line bg-surface">
                  {otherRecords.map((record) => (
                    <ApiHubRow key={record.operation} record={record} />
                  ))}
                </ul>
              </section>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}
