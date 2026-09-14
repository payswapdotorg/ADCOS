/**
 * ObjectHeader — the dense header for object surfaces (contract,
 * lease, webhook endpoint…): mono kind chip, title with copy affordance,
 * verbatim Status, meta grid and right-aligned actions.
 */

import type { ReactNode } from "react";
import { CopyButton } from "./copy-button";
import { Status } from "./status";

export function ObjectHeader({
  kind,
  title,
  subtitle,
  status,
  meta,
  actions,
  copyValue,
}: {
  kind: string;
  title: string;
  subtitle?: ReactNode;
  status?: string | null;
  meta?: { label: string; value: ReactNode }[];
  actions?: ReactNode;
  copyValue?: string;
}) {
  return (
    <header className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center rounded border border-line-strong px-1.5 py-px font-mono uppercase tracking-wide text-2xs text-ink-muted">
              {kind}
            </span>
            <h2 className="min-w-0 break-all text-lg font-semibold text-ink">
              {title}
            </h2>
            {copyValue ? (
              <CopyButton
                value={copyValue}
                ariaLabel="Copy identifier"
                label="Copy"
              />
            ) : null}
            {status ? <Status value={status} size="sm" /> : null}
          </div>
          {subtitle ? (
            <div className="text-sm text-ink-muted">{subtitle}</div>
          ) : null}
          {meta && meta.length > 0 ? (
            <dl className="mt-1 flex flex-col gap-1">
              {meta.map((entry) => (
                <div
                  key={entry.label}
                  className="grid grid-cols-[minmax(80px,auto)_1fr] gap-x-3"
                >
                  <dt className="text-xs text-ink-faint">{entry.label}</dt>
                  <dd className="min-w-0 break-all text-xs text-ink">
                    {entry.value}
                  </dd>
                </div>
              ))}
            </dl>
          ) : null}
        </div>
        {actions ? (
          <div className="flex shrink-0 items-center gap-2">{actions}</div>
        ) : null}
      </div>
    </header>
  );
}
