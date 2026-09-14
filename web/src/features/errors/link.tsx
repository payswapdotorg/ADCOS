/**
 * The error→workbench linkage (charter §3.6: "every ErrorState across
 * the console links here"). The shared ErrorState primitive belongs to
 * the design system (Worker 1's surface), so Worker 3's feature pages
 * render THIS composition instead: the canonical ErrorState (reason
 * VERBATIM) plus the "View in error workbench" link. The workbench
 * lives at /settings/errors and can focus one captured request via
 * ?request=<sequence>.
 */

import Link from "next/link";
import type { ReactNode } from "react";
import { ErrorState } from "@/components/ui";
import { cn } from "@/lib/utils";

/** The error workbench route (Worker 3's trust surface). */
export const ERROR_WORKBENCH_PATH = "/settings/errors";

/** The href that focuses one captured request in the workbench. */
export function workbenchHref(sequence?: number): string {
  return sequence === undefined
    ? ERROR_WORKBENCH_PATH
    : `${ERROR_WORKBENCH_PATH}?request=${sequence}`;
}

/**
 * The linked error surface — ErrorState (verbatim reason codes, retry,
 * request reproduction) with the workbench link underneath. Every
 * Worker 3 feature page renders failures through this so the error
 * workbench is always one click away.
 */
export function LinkedErrorState({
  error,
  onRetry,
  request,
  compact,
  sequence,
  className,
}: {
  error: unknown;
  onRetry?: () => void;
  request?: { method: string; path: string; body?: unknown };
  compact?: boolean;
  /** The captured request's sequence (deep-links the workbench entry). */
  sequence?: number;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col", className)}>
      <ErrorState error={error} onRetry={onRetry} request={request} compact={compact} />
      <div className={compact ? "px-3 pb-3" : "px-4 pb-4"}>
        <Link
          href={workbenchHref(sequence)}
          className="inline-flex items-center gap-1 text-xs text-ink-muted underline decoration-line-strong underline-offset-2 hover:text-ink"
        >
          View in error workbench
          {" →"}
        </Link>
      </div>
    </div>
  );
}

/** A compact inline link to the workbench (for non-error surfaces). */
export function ErrorWorkbenchLink({
  sequence,
  children,
}: {
  sequence?: number;
  children?: ReactNode;
}) {
  return (
    <Link
      href={workbenchHref(sequence)}
      className="inline-flex items-center gap-1 text-xs text-ink-muted underline decoration-line-strong underline-offset-2 hover:text-ink"
    >
      {children ?? "View in error workbench"}
      {" →"}
    </Link>
  );
}
