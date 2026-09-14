"use client";

/**
 * FilterBar — the dense single-row toolbar for list surfaces: search
 * input, native styled selects, and a right slot. All controls are
 * controlled; accessible names come from the placeholder / filter
 * label so the row stays visually dense.
 */

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { SearchIcon } from "./icons";

export interface FilterSelect {
  id: string;
  /** Visible to AT as the select's accessible name. */
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
}

export function FilterBar({
  search,
  filters,
  right,
  className,
}: {
  search?: {
    value: string;
    onChange: (value: string) => void;
    placeholder?: string;
  };
  filters?: FilterSelect[];
  right?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      {search ? (
        <div className="relative flex items-center">
          <SearchIcon
            size={14}
            className="pointer-events-none absolute left-2.5 text-ink-faint"
          />
          <input
            type="search"
            value={search.value}
            placeholder={search.placeholder}
            aria-label={search.placeholder ?? "Search"}
            onChange={(event) => search.onChange(event.target.value)}
            className="h-8 w-56 rounded-md border border-line bg-raised pl-8 pr-3 text-sm text-ink placeholder:text-ink-faint"
          />
        </div>
      ) : null}
      {filters?.map((filter) => (
        <select
          key={filter.id}
          value={filter.value}
          aria-label={filter.label}
          onChange={(event) => filter.onChange(event.target.value)}
          className="h-8 max-w-[12rem] rounded-md border border-line bg-raised px-2 text-sm text-ink"
        >
          {filter.options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      ))}
      {right ? (
        <div className="ml-auto flex items-center gap-2">{right}</div>
      ) : null}
    </div>
  );
}
