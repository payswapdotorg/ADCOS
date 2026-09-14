/**
 * ObjectSection — the titled section card every Worker 2 object surface
 * composes (contract detail's lifecycle chain, the fulfillment chain, the
 * networks inspection). Fills Worker 1's `ObjectViewSection` contract
 * shape with a renderer: a section header (with an optional anchor id),
 * a property grid of `ObjectField` rows (canonical member names in mono),
 * free-form children, and an optional raw JSON payload through the
 * shared JsonViewer.
 */

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import type { ObjectField } from "@/lib/objects";
import { JsonViewer } from "@/components/ui/json-viewer";

export function ObjectFieldGrid({
  fields,
  columns = 1,
}: {
  fields: ObjectField[];
  columns?: 1 | 2;
}) {
  return (
    <dl
      className={cn(
        "grid gap-x-6 gap-y-2.5",
        columns === 2 ? "sm:grid-cols-2" : "grid-cols-1",
      )}
    >
      {fields.map((field) => (
        <div
          key={field.label}
          className="grid grid-cols-[minmax(10rem,auto)_1fr] items-baseline gap-x-3"
        >
          <dt className="break-all font-mono text-2xs text-ink-faint">
            {field.label}
          </dt>
          <dd className="min-w-0 break-all text-sm text-ink">
            {field.value}
            {field.hint ? (
              <p className="mt-0.5 text-xs leading-relaxed text-ink-faint">
                {field.hint}
              </p>
            ) : null}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function ObjectSection({
  id,
  title,
  description,
  fields,
  children,
  json,
  jsonName,
  actions,
  className,
}: {
  /** Anchor id (also the chain step identity on lifecycle pages). */
  id?: string;
  title: ReactNode;
  description?: ReactNode;
  fields?: ObjectField[];
  children?: ReactNode;
  /** Raw backend payload rendered under the section (JsonViewer). */
  json?: unknown;
  jsonName?: string;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <section
      id={id}
      aria-labelledby={id ? `${id}-heading` : undefined}
      className={cn(
        "rounded-md border border-line bg-surface",
        className,
      )}
    >
      <header className="flex flex-wrap items-start justify-between gap-2 border-b border-line px-4 py-3">
        <div className="min-w-0">
          <h2
            id={id ? `${id}-heading` : undefined}
            className="text-sm font-semibold text-ink"
          >
            {title}
          </h2>
          {description ? (
            <p className="mt-0.5 text-xs leading-relaxed text-ink-muted">
              {description}
            </p>
          ) : null}
        </div>
        {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
      </header>
      <div className="flex flex-col gap-3 px-4 py-3">
        {fields && fields.length > 0 ? (
          <ObjectFieldGrid fields={fields} />
        ) : null}
        {children}
        {json !== undefined ? (
          <details className="group rounded-md border border-line bg-raised">
            <summary className="cursor-pointer select-none px-3 py-1.5 text-xs text-ink-muted hover:text-ink">
              Raw JSON
            </summary>
            <div className="border-t border-line px-3 py-2">
              <JsonViewer value={json} name={jsonName} />
            </div>
          </details>
        ) : null}
      </div>
    </section>
  );
}
