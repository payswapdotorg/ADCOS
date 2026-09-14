"use client";

/**
 * OperationBrowser — the registry-driven operation list of the API
 * Explorer. EVERY row comes from `COVERAGE` (the single source of
 * truth): an operation outside the registry never renders as callable,
 * and the row count is pinned by tests against the registry size.
 *
 * Honest search: a query that looks like a concrete method+path (or a
 * bare path) is resolved through `matchOperationForPath`. A match
 * offers the operation (with its path parameters prefilled from the
 * query); NO match renders the explicit "not a supported operation"
 * notice — never a guess, never a silent empty list.
 */

import { useMemo } from "react";
import {
  COVERAGE,
  type CoverageRecord,
} from "@/lib/api/coverage";
import { DESTRUCTIVE_OPERATIONS, matchOperationForPath } from "./executor";

/** Grouping by area (the registry's own uiLocation vocabulary). */
const GROUPS: { id: string; label: string; test: (record: CoverageRecord) => boolean }[] = [
  { id: "platform", label: "Platform surfaces", test: (record) => record.platform },
  {
    id: "connectivity",
    label: "Connectivity",
    test: (record) => !record.platform && record.uiLocation === "/connectivity",
  },
  {
    id: "developers",
    label: "Developers",
    test: (record) => !record.platform && record.uiLocation === "/developers",
  },
  {
    id: "assurance",
    label: "Assurance",
    test: (record) => !record.platform && record.uiLocation === "/assurance",
  },
];

/** A query is operation-shaped when it is a bare path or METHOD + path. */
function parseOperationQuery(query: string): { method: string; path: string } | null {
  const trimmed = query.trim();
  const withMethod = /^([A-Za-z]+)\s+(\/\S*)$/.exec(trimmed);
  if (withMethod) {
    return { method: withMethod[1].toUpperCase(), path: withMethod[2] };
  }
  if (trimmed.startsWith("/")) {
    return { method: "GET", path: trimmed };
  }
  return null;
}

function MethodChip({ method }: { method: string }) {
  const read = method === "GET";
  return (
    <span
      className={
        read
          ? "inline-flex shrink-0 items-center rounded border border-line-strong px-1.5 py-px font-mono text-2xs uppercase tracking-wide text-ink-muted"
          : "inline-flex shrink-0 items-center rounded border border-accent bg-accent px-1.5 py-px font-mono text-2xs uppercase tracking-wide text-accent-ink"
      }
    >
      {method}
    </span>
  );
}

function OperationRow({
  record,
  selected,
  onSelect,
}: {
  record: CoverageRecord;
  selected: boolean;
  onSelect: (record: CoverageRecord) => void;
}) {
  const destructive = DESTRUCTIVE_OPERATIONS.has(record.operation);
  return (
    <li>
      <button
        type="button"
        data-testid="explorer-operation-row"
        data-operation={record.operation}
        aria-pressed={selected}
        aria-label={`${record.method} ${record.path} — ${record.operation}`}
        title={record.description}
        onClick={() => onSelect(record)}
        className={`flex w-full flex-col gap-1 rounded-md border px-2.5 py-2 text-left transition-colors ${
          selected
            ? "border-accent bg-raised"
            : "border-transparent hover:border-line hover:bg-raised/40"
        }`}
      >
        <span className="flex min-w-0 items-center gap-2">
          <MethodChip method={record.method} />
          <span className="min-w-0 flex-1 truncate font-mono text-xs text-ink">
            {record.path}
          </span>
        </span>
        <span className="flex flex-wrap items-center gap-1.5">
          <span className="font-mono text-2xs text-ink-faint">{record.operation}</span>
          {record.mutation ? (
            <span className="rounded border border-accent/60 px-1 py-px font-mono text-2xs text-accent">
              mutation
            </span>
          ) : null}
          {destructive ? (
            <span className="rounded border border-danger/60 px-1 py-px font-mono text-2xs text-danger">
              destructive
            </span>
          ) : null}
          {record.requiredCapability ? (
            <span className="rounded border border-line px-1 py-px font-mono text-2xs text-ink-muted">
              {record.requiredCapability}
            </span>
          ) : null}
          {record.platform ? (
            <span className="rounded border border-line px-1 py-px font-mono text-2xs text-ink-faint">
              platform
            </span>
          ) : null}
        </span>
        <span className="truncate text-xs text-ink-muted">{record.description}</span>
      </button>
    </li>
  );
}

export function OperationBrowser({
  query,
  onQueryChange,
  selectedOperation,
  onSelect,
}: {
  query: string;
  onQueryChange: (query: string) => void;
  selectedOperation: string | null;
  onSelect: (record: CoverageRecord, pathParams?: Record<string, string>) => void;
}) {
  const trimmed = query.trim();
  const needle = trimmed.toLowerCase();

  const filtered = useMemo(() => {
    if (!needle) return COVERAGE;
    return COVERAGE.filter((record) =>
      [
        record.operation,
        record.method,
        record.path,
        record.description,
        record.requiredCapability,
        record.uiLocation,
      ]
        .join(" ")
        .toLowerCase()
        .includes(needle),
    );
  }, [needle]);

  const operationQuery = parseOperationQuery(trimmed);
  const resolved = operationQuery
    ? matchOperationForPath(operationQuery.method, operationQuery.path)
    : null;
  const showUnsupported =
    operationQuery !== null && resolved === null && filtered.length === 0;

  const groups = useMemo(
    () =>
      GROUPS.map((group) => ({
        ...group,
        records: filtered.filter(group.test),
      })).filter((group) => group.records.length > 0),
    [filtered],
  );
  const otherRecords = useMemo(
    () => filtered.filter((record) => !GROUPS.some((group) => group.test(record))),
    [filtered],
  );

  return (
    <section
      aria-label="Operation browser"
      className="flex min-w-0 flex-col gap-2 rounded-md border border-line bg-surface p-3"
    >
      <div className="relative flex items-center">
        <input
          type="search"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Search operations or paste a path…"
          aria-label="Search operations"
          data-testid="explorer-operation-search"
          className="h-8 w-full rounded-md border border-line bg-raised px-3 text-sm text-ink placeholder:text-ink-faint"
        />
      </div>

      <p className="font-mono text-2xs text-ink-faint" data-testid="explorer-operation-count">
        {filtered.length} of {COVERAGE.length} registry operations
      </p>

      {showUnsupported ? (
        <div
          data-testid="unsupported-operation-notice"
          className="rounded-md border border-dashed border-warning/60 bg-warning/5 px-3 py-2"
          role="note"
        >
          <p className="text-sm text-ink">
            <span className="font-mono">{`${operationQuery?.method} ${operationQuery?.path}`}</span>{" "}
            is not a supported operation.
          </p>
          <p className="mt-1 text-xs text-ink-muted">
            The coverage registry is the single source of truth — only its
            operations render as callable. Adjust the query or pick an
            operation from the list.
          </p>
        </div>
      ) : null}

      {resolved && needle ? (
        <div className="rounded-md border border-line bg-raised px-2.5 py-2">
          <p className="text-2xs text-ink-faint">Resolved from the path</p>
          <button
            type="button"
            data-testid="resolved-operation"
            onClick={() => onSelect(resolved.record, resolved.params)}
            className="mt-1 flex min-w-0 items-center gap-2 text-left"
          >
            <MethodChip method={resolved.record.method} />
            <span className="truncate font-mono text-xs text-accent hover:underline">
              {resolved.record.operation}
            </span>
          </button>
        </div>
      ) : null}

      <div className="flex max-h-[32rem] flex-col gap-3 overflow-y-auto pr-1">
        {groups.map((group) => (
          <div key={group.id} className="flex flex-col gap-1">
            <p className="px-1 text-2xs uppercase tracking-wide text-ink-faint">
              {group.label}
            </p>
            <ul className="flex flex-col gap-1">
              {group.records.map((record) => (
                <OperationRow
                  key={record.operation}
                  record={record}
                  selected={record.operation === selectedOperation}
                  onSelect={(selected) => onSelect(selected)}
                />
              ))}
            </ul>
          </div>
        ))}
        {otherRecords.length > 0 ? (
          <div className="flex flex-col gap-1">
            <p className="px-1 text-2xs uppercase tracking-wide text-ink-faint">Other areas</p>
            <ul className="flex flex-col gap-1">
              {otherRecords.map((record) => (
                <OperationRow
                  key={record.operation}
                  record={record}
                  selected={record.operation === selectedOperation}
                  onSelect={(selected) => onSelect(selected)}
                />
              ))}
            </ul>
          </div>
        ) : null}
        {!showUnsupported && filtered.length === 0 ? (
          <div className="px-3 py-6 text-center text-sm text-ink-faint">
            No operations match the current search.
          </div>
        ) : null}
      </div>
    </section>
  );
}
