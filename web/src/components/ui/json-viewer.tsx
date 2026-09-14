"use client";

/**
 * JsonViewer — a syntax-safe recursive JSON renderer.
 *
 * NO dangerouslySetInnerHTML, no eval-ish highlighting: pure React
 * recursion over the value. Objects and arrays collapse at every
 * level (chevron button with aria-expanded); keys render as faint
 * mono, strings as ink, numbers as accent, booleans/null as warning.
 */

import { useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import { ChevronRightIcon } from "./icons";
import { CopyButton } from "./copy-button";

/** Leaves indent past the chevron column so values line up. */
const LEAF_INDENT = "pl-5";

function safeStringify(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2) ?? "undefined";
  } catch {
    return String(value);
  }
}

function PrimitiveValue({ value }: { value: unknown }) {
  if (value === null) {
    return <span className="text-warning">null</span>;
  }
  if (typeof value === "string") {
    return <span className="break-all text-ink">{`"${value}"`}</span>;
  }
  if (typeof value === "number") {
    return <span className="text-accent">{String(value)}</span>;
  }
  if (typeof value === "boolean") {
    return <span className="text-warning">{String(value)}</span>;
  }
  return <span className="text-ink-muted">{String(value)}</span>;
}

function KeyLabel({ name }: { name: string }) {
  return <span className="text-ink-faint">{name}:</span>;
}

function JsonNode({
  name,
  value,
  depth,
  defaultExpandedDepth,
}: {
  name?: string;
  value: unknown;
  depth: number;
  defaultExpandedDepth: number;
}) {
  const [expanded, setExpanded] = useState(depth < defaultExpandedDepth);
  const isContainer =
    value !== null && typeof value === "object";
  const isEmptyContainer =
    isContainer &&
    (Array.isArray(value) ? value.length === 0 : Object.keys(value).length === 0);

  if (!isContainer || isEmptyContainer) {
    return (
      <div className={cn("flex items-baseline gap-1", depth > 0 && LEAF_INDENT)}>
        {name !== undefined ? <KeyLabel name={name} /> : null}
        {isContainer ? (
          <span className="text-ink-faint">
            {Array.isArray(value) ? "[]" : "{}"}
          </span>
        ) : (
          <PrimitiveValue value={value} />
        )}
      </div>
    );
  }

  const isArray = Array.isArray(value);
  const open = isArray ? "[" : "{";
  const close = isArray ? "]" : "}";
  const entries: [string, unknown][] = isArray
    ? (value as unknown[]).map((item, index) => [String(index), item])
    : Object.entries(value as Record<string, unknown>);

  let children: ReactNode;
  if (isArray) {
    children = (value as unknown[]).map((item, index) => (
      <JsonNode
        key={String(index)}
        value={item}
        depth={depth + 1}
        defaultExpandedDepth={defaultExpandedDepth}
      />
    ));
  } else {
    children = entries.map(([key, child]) => (
      <JsonNode
        key={key}
        name={key}
        value={child}
        depth={depth + 1}
        defaultExpandedDepth={defaultExpandedDepth}
      />
    ));
  }

  return (
    <div>
      <div className="flex items-start gap-1">
        <button
          type="button"
          aria-expanded={expanded}
          aria-label={`Toggle ${name ?? "value"}`}
          onClick={() => setExpanded((current) => !current)}
          className="mt-0.5 flex h-3.5 w-4 shrink-0 items-center justify-center rounded-sm text-ink-faint hover:text-ink"
        >
          <ChevronRightIcon
            size={12}
            className={cn("transition-transform", expanded && "rotate-90")}
          />
        </button>
        <div className="min-w-0 flex-1">
          <div className="break-all">
            {name !== undefined ? <KeyLabel name={name} /> : null}
            <span className="text-ink-faint">{open}</span>
            {expanded ? null : (
              <span className="text-ink-faint"> … {close}</span>
            )}
          </div>
          {expanded ? (
            <div className="ml-1 border-l border-line pl-2">{children}</div>
          ) : null}
          {expanded ? (
            <div className="pl-5 text-ink-faint">{close}</div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export function JsonViewer({
  value,
  name,
  defaultExpandedDepth = 2,
  className,
}: {
  value: unknown;
  name?: string;
  /** Container nodes at depth < N start expanded (default 2). */
  defaultExpandedDepth?: number;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-1 font-mono text-xs", className)}>
      <div className="flex justify-end">
        <CopyButton
          value={safeStringify(value)}
          ariaLabel="Copy JSON"
          label="Copy"
        />
      </div>
      <JsonNode
        name={name}
        value={value}
        depth={0}
        defaultExpandedDepth={defaultExpandedDepth}
      />
    </div>
  );
}
