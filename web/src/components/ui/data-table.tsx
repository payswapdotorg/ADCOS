"use client";

/**
 * DataTable — the dense, keyboard-first table for console surfaces.
 *
 * - sticky header, sortable columns (click or Enter/Space on the
 *   focused header button; `aria-sort` travels on the th);
 * - rows are focusable (tabIndex 0) with `aria-selected`; ArrowUp/
 *   ArrowDown move focus between rows, Enter/Space (or click)
 *   activates the row via onRowActivate;
 * - loading renders 6 skeleton rows under `aria-busy`; error renders
 *   the shared ErrorState (verbatim reason codes) with retry; empty
 *   renders the shared EmptyState.
 */

import {
  useCallback,
  useMemo,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from "react";
import { cn } from "@/lib/utils";
import { ChevronDownIcon, ChevronUpIcon } from "./icons";
import { EmptyState } from "./empty-state";
import { ErrorState } from "./error-state";

export interface Column<T> {
  key: string;
  header: ReactNode;
  sortable?: boolean;
  /** Value used for sorting (and as the cell fallback text). */
  accessor?: (row: T) => string | number | null | undefined;
  /** Custom cell content; mono for id-ish cells is the caller's choice. */
  render?: (row: T) => ReactNode;
  align?: "left" | "right";
  className?: string;
}

type SortDir = "asc" | "desc";

const SKELETON_WIDTHS = ["w-1/3", "w-2/3", "w-1/2", "w-4/5"];
const SKELETON_ROWS = 6;

function CellFallback<T>({ row, column }: { row: T; column: Column<T> }) {
  const value = column.accessor?.(row);
  if (value === null || value === undefined || value === "") {
    return <span className="text-ink-faint">—</span>;
  }
  return <>{String(value)}</>;
}

export function DataTable<T>({
  rows,
  columns,
  getRowKey,
  loading = false,
  error,
  onRetry,
  emptyTitle = "Nothing to show",
  emptyDescription,
  onRowActivate,
  rowAriaLabel,
  className,
}: {
  rows: T[];
  columns: Column<T>[];
  getRowKey: (row: T) => string;
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  emptyTitle?: string;
  emptyDescription?: ReactNode;
  onRowActivate?: (row: T) => void;
  rowAriaLabel?: (row: T) => string;
  className?: string;
}) {
  const [sort, setSort] = useState<{ key: string; dir: SortDir } | null>(null);
  const [activeKey, setActiveKey] = useState<string | null>(null);

  const sortedRows = useMemo(() => {
    if (!sort) return rows;
    const column = columns.find((candidate) => candidate.key === sort.key);
    const accessor = column?.accessor;
    if (!accessor) return rows;
    const direction = sort.dir === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const left = accessor(a);
      const right = accessor(b);
      // nullish values sort last regardless of direction
      if (left == null && right == null) return 0;
      if (left == null) return 1;
      if (right == null) return -1;
      if (typeof left === "number" && typeof right === "number") {
        return (left - right) * direction;
      }
      return String(left).localeCompare(String(right)) * direction;
    });
  }, [rows, columns, sort]);

  const toggleSort = useCallback((key: string) => {
    setSort((previous) => {
      if (previous?.key !== key) return { key, dir: "asc" };
      return { key, dir: previous.dir === "asc" ? "desc" : "asc" };
    });
  }, []);

  const activateRow = useCallback(
    (row: T) => {
      setActiveKey(getRowKey(row));
      onRowActivate?.(row);
    },
    [getRowKey, onRowActivate],
  );

  const handleRowKeyDown = useCallback(
    (
      event: ReactKeyboardEvent<HTMLTableRowElement>,
      row: T,
      index: number,
    ) => {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        const tableRows = Array.from(
          event.currentTarget.parentElement?.querySelectorAll<HTMLTableRowElement>(
            "tr[data-row-index]",
          ) ?? [],
        );
        if (tableRows.length === 0) return;
        const delta = event.key === "ArrowDown" ? 1 : -1;
        const next = Math.max(0, Math.min(index + delta, tableRows.length - 1));
        tableRows[next]?.focus();
        return;
      }
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        activateRow(row);
      }
    },
    [activateRow],
  );

  let body: ReactNode;
  if (error !== undefined && error !== null) {
    body = (
      <tr>
        <td colSpan={columns.length} className="p-0">
          <ErrorState error={error} onRetry={onRetry} />
        </td>
      </tr>
    );
  } else if (loading) {
    body = Array.from({ length: SKELETON_ROWS }, (_, rowIndex) => (
      <tr key={`skeleton-${rowIndex}`} aria-hidden="true">
        {columns.map((column, columnIndex) => (
          <td key={column.key} className="h-9 border-b border-line px-3">
            <div
              className={cn(
                "h-3 animate-pulse rounded bg-raised",
                SKELETON_WIDTHS[(rowIndex + columnIndex) % SKELETON_WIDTHS.length],
              )}
            />
          </td>
        ))}
      </tr>
    ));
  } else if (sortedRows.length === 0) {
    body = (
      <tr>
        <td colSpan={columns.length} className="p-0">
          <EmptyState title={emptyTitle} description={emptyDescription} />
        </td>
      </tr>
    );
  } else {
    body = sortedRows.map((row, index) => {
      const key = getRowKey(row);
      const isActive = key === activeKey;
      return (
        <tr
          key={key}
          data-row-key={key}
          data-row-index={index}
          tabIndex={0}
          aria-selected={isActive}
          aria-label={rowAriaLabel?.(row)}
          onClick={() => activateRow(row)}
          onKeyDown={(event) => handleRowKeyDown(event, row, index)}
          className={cn(
            "h-9 border-b border-line text-sm text-ink transition-colors hover:bg-raised/40",
            onRowActivate ? "cursor-pointer" : null,
            isActive ? "bg-raised/60" : null,
          )}
        >
          {columns.map((column) => (
            <td
              key={column.key}
              className={cn(
                "px-3 py-1.5 align-middle",
                column.align === "right" && "text-right",
                column.className,
              )}
            >
              {column.render ? column.render(row) : (
                <CellFallback row={row} column={column} />
              )}
            </td>
          ))}
        </tr>
      );
    });
  }

  return (
    <div
      className={cn(
        "w-full overflow-x-auto rounded-md border border-line bg-surface",
        className,
      )}
    >
      {/* border-separate keeps header borders glued to the sticky thead */}
      <table
        className="w-full border-separate border-spacing-0 text-sm"
        aria-busy={loading ? "true" : undefined}
      >
        <thead className="sticky top-0 z-10 bg-surface">
          <tr>
            {columns.map((column) => {
              const sortable = Boolean(column.sortable && column.accessor);
              const sortState =
                sort && sort.key === column.key ? sort : null;
              const ariaSort = sortable
                ? sortState
                  ? sortState.dir === "asc"
                    ? "ascending"
                    : "descending"
                  : "none"
                : undefined;
              return (
                <th
                  key={column.key}
                  scope="col"
                  aria-sort={ariaSort}
                  className={cn(
                    "border-b border-line px-3 py-1.5 text-left text-xs font-normal text-ink-faint",
                    column.align === "right" && "text-right",
                    column.className,
                  )}
                >
                  {sortable ? (
                    <button
                      type="button"
                      onClick={() => toggleSort(column.key)}
                      className={cn(
                        "inline-flex w-full items-center gap-1 text-xs font-normal hover:text-ink",
                        column.align === "right" && "justify-end",
                      )}
                    >
                      {column.header}
                      {sortState ? (
                        <span aria-hidden="true" className="text-ink-faint">
                          {sortState.dir === "asc" ? (
                            <ChevronUpIcon size={12} />
                          ) : (
                            <ChevronDownIcon size={12} />
                          )}
                        </span>
                      ) : null}
                    </button>
                  ) : (
                    column.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>{body}</tbody>
      </table>
    </div>
  );
}
