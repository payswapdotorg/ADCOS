/**
 * Status — the canonical renderer for backend state values.
 *
 * The backend's state vocabulary is law: the label is the VERBATIM
 * value (`CONTRACT_ACTIVE`, `renewed`, `revoked`…), never a frontend
 * synonym. The tone comes from `statusToneFor`; values outside the
 * known vocabulary render with a hollow dashed dot and the verbatim
 * text, so unrecognized states stay visible instead of being masked.
 */

import { cn } from "@/lib/utils";
import { statusToneFor, type Tone } from "@/lib/design/tokens";

/** Stable test ids (the tone also travels as `data-tone`). */
export const STATUS_TEST_IDS = {
  root: "status-root",
  dot: "status-dot",
  label: "status-label",
} as const;

/**
 * Dot treatment per tone. Exported so Timeline (and only the design
 * system) can reuse the exact same tone → dot mapping.
 */
export const TONE_DOT_CLASSES: Record<Tone, string> = {
  positive: "bg-positive",
  warning: "bg-warning",
  danger: "bg-danger",
  info: "bg-info",
  neutral: "bg-ink-muted",
  unknown: "border border-dashed border-ink-faint",
};

export function Status({
  value,
  size = "md",
  className,
}: {
  value: string | null | undefined;
  size?: "sm" | "md";
  className?: string;
}) {
  const tone = statusToneFor(value);
  const hasLabel = typeof value === "string" && value.length > 0;
  return (
    <span
      data-testid={STATUS_TEST_IDS.root}
      data-tone={tone}
      data-value={hasLabel ? value : undefined}
      title={hasLabel ? value : undefined}
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap font-mono",
        size === "sm" ? "text-2xs" : "text-xs",
        className,
      )}
    >
      <span
        data-testid={STATUS_TEST_IDS.dot}
        aria-hidden="true"
        className={cn(
          "shrink-0 rounded-full",
          size === "sm" ? "h-1.5 w-1.5" : "h-2 w-2",
          TONE_DOT_CLASSES[tone],
        )}
      />
      {hasLabel && (
        <span
          data-testid={STATUS_TEST_IDS.label}
          className={tone === "unknown" ? "text-ink-muted" : "text-ink"}
        >
          {value}
        </span>
      )}
    </span>
  );
}
