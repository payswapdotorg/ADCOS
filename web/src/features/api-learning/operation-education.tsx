"use client";

/**
 * OperationEducationPanel — the "About this operation" education block
 * the V1 API Explorer composes around each operation (V2 design §12:
 * developer education inside the API Explorer).
 *
 * The DEC-0128 program, Task 6 of the frozen plan. PURE PRESENTATION
 * over the Task-1 operation-education registry (`@/lib/education`) and
 * the accepted coverage registry (`@/lib/api/coverage`): purpose,
 * prerequisites, lifecycle position, typical sequence, the request
 * fields, related concepts, the canonical reason codes and the next
 * operation — every string comes from the registries, nothing is
 * invented here.
 *
 * Progressive disclosure (design §15 — V1's calm expert density stays):
 * the education COLLAPSES by default into one compact
 * "About this operation" affordance (aria-expanded + aria-controls);
 * the collapsed state renders NO panel content at all, so the expert
 * density and every V1 execution surface are byte-identical until the
 * learner opts in per operation.
 *
 * The request-language example is a curl derived ONLY from the
 * operation's own registry metadata (method, path template, example
 * body) with the SAME masked-credential convention the V1 curl surface
 * uses (`maskedRequestHeaders`: the session's actual application id
 * when known, the credential always the masked placeholder). No
 * language SDK examples are invented — the SDK page already states none
 * exist.
 *
 * This module adds education ONLY. It never renders execution controls
 * and never touches the Explorer's execution semantics (§20).
 */

import { useId, useState } from "react";
import Link from "next/link";
import type { CoverageRecord } from "@/lib/api/coverage";
import { getOperationEducation } from "@/lib/education";
import { ApiRequestPanel } from "@/components/ui";
import { ConceptLink } from "@/features/learning";
import { maskedRequestHeaders } from "@/features/api-explorer/executor";

/** Stable test ids for the education affordance and its panel. */
export const OPERATION_EDUCATION_TEST_IDS = {
  trigger: "operation-education-trigger",
  panel: "operation-education-panel",
} as const;

/** The masked idempotency-key placeholder (the workbench's convention). */
const MASKED_IDEMPOTENCY_KEY = "<fresh-idempotency-key>";

/** One labelled fact row (the anatomy's quiet dl shape). */
function FactRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[minmax(9.5rem,auto)_1fr] items-baseline gap-x-3 gap-y-1">
      <dt className="font-mono text-2xs text-ink-faint">{label}</dt>
      <dd className="min-w-0 break-words text-sm leading-relaxed text-ink-muted">{children}</dd>
    </div>
  );
}

/**
 * OperationEducationPanel — renders nothing when the operation has no
 * education record (honest absence: the coverage registry guarantees one
 * per operation today, but the registry is the authority, not this
 * component).
 */
export function OperationEducationPanel({
  record,
  applicationId,
}: {
  record: CoverageRecord;
  /** The session's actual application id (masked-credential curl uses it). */
  applicationId: string | null;
}) {
  const education = getOperationEducation(record.operation);
  const [open, setOpen] = useState(false);
  const panelId = useId();

  if (!education) return null;

  const nextOperation = education.nextOperation;
  const nextEducation = nextOperation ? getOperationEducation(nextOperation) : undefined;

  const curlHeaders = maskedRequestHeaders({
    platform: record.platform,
    mutation: record.mutation,
    applicationId,
    idempotencyKey: record.mutation ? MASKED_IDEMPOTENCY_KEY : null,
  });

  return (
    <div className="rounded-md border border-dashed border-line bg-surface">
      <button
        type="button"
        data-testid={OPERATION_EDUCATION_TEST_IDS.trigger}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
        className="flex min-h-9 w-full items-center gap-2 rounded-md px-3 py-1.5 text-left text-xs text-ink-muted transition-colors hover:bg-raised/40"
      >
        <span aria-hidden="true">{open ? "▾" : "▸"}</span>
        <span className="font-medium">About this operation</span>
        <span className="text-ink-faint">
          — purpose, prerequisites, lifecycle position, fields, related
          concepts and errors{open ? " (collapse)" : ""}
        </span>
      </button>

      {open ? (
        <div
          id={panelId}
          data-testid={OPERATION_EDUCATION_TEST_IDS.panel}
          className="flex flex-col gap-4 border-t border-dashed border-line px-3 pb-3 pt-3"
        >
          {/* the purpose — the registry's own lede ---------------------- */}
          <div className="flex flex-col gap-1">
            <p className="text-2xs uppercase tracking-wide text-ink-faint">Purpose</p>
            <p className="text-sm leading-relaxed text-ink">{education.purpose}</p>
          </div>

          <dl className="flex flex-col gap-2">
            <FactRow label="prerequisites">{education.prerequisites}</FactRow>
            <FactRow label="lifecycle position">{education.lifecyclePosition}</FactRow>
            <FactRow label="typical sequence">{education.typicalSequence}</FactRow>
            <FactRow label="user-actionable">
              {education.userActionable
                ? education.internalOnly
                  ? "No — explicitly internal-only / not user-actionable."
                  : "Yes — this is a user-actionable operation."
                : "No — not a user action."}
            </FactRow>
          </dl>

          {/* the request fields ------------------------------------------ */}
          <div className="flex flex-col gap-1.5">
            <p className="text-2xs uppercase tracking-wide text-ink-faint">Request fields</p>
            <dl className="flex flex-col gap-2.5">
              {education.fieldExplanations.map((field) => (
                <div
                  key={field.field}
                  className="grid grid-cols-[minmax(10rem,auto)_1fr] items-baseline gap-x-3"
                >
                  <dt className="break-all font-mono text-xs text-ink">{field.field}</dt>
                  <dd className="text-sm leading-relaxed text-ink-muted">{field.explanation}</dd>
                </div>
              ))}
            </dl>
          </div>

          {/* the request-language example (curl, registry metadata only) -- */}
          <div className="flex flex-col gap-1.5">
            <p className="text-2xs uppercase tracking-wide text-ink-faint">
              Request example (curl — from the operation&apos;s own metadata)
            </p>
            <ApiRequestPanel
              variant="full"
              method={record.method}
              path={record.path}
              headers={curlHeaders}
              body={record.example}
              description={`${record.operation} — the registry's own method, path template${
                record.example !== undefined ? " and example body" : ""
              }; substitute your path parameters${record.mutation ? " and a fresh idempotency key" : ""}.`}
            />
            <p className="text-2xs text-ink-faint">
              The only request language the console derives today is curl —
              from this operation&apos;s own registry metadata, with the
              credential masked. No language SDK examples exist to show (see
              the SDK documentation for that honest state).
            </p>
          </div>

          {/* related concepts -------------------------------------------- */}
          {education.relatedConcepts.length > 0 ? (
            <div className="flex flex-col gap-1.5">
              <p className="text-2xs uppercase tracking-wide text-ink-faint">Related concepts</p>
              <ul className="flex flex-wrap gap-2">
                {education.relatedConcepts.map((conceptId) => (
                  <li key={conceptId}>
                    <ConceptLink id={conceptId} mode="chip" />
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {/* related reason codes ---------------------------------------- */}
          {education.relatedErrors.length > 0 ? (
            <div className="flex flex-col gap-1.5">
              <p className="text-2xs uppercase tracking-wide text-ink-faint">
                Related reason codes
              </p>
              <p className="flex flex-wrap items-center gap-1.5">
                {education.relatedErrors.map((code) => (
                  <Link
                    key={code}
                    href={`/docs/errors#code-${code}`}
                    className="rounded border border-line bg-raised px-1.5 py-px font-mono text-2xs text-ink-muted transition-colors hover:border-line-strong hover:text-ink"
                  >
                    {code}
                  </Link>
                ))}
              </p>
              <p className="text-2xs text-ink-faint">
                Canonical reason codes this operation can realistically
                produce — verbatim, linking to their guidance.
              </p>
            </div>
          ) : null}

          {/* the next operation ------------------------------------------ */}
          {nextOperation ? (
            <div className="flex flex-col gap-1">
              <p className="text-2xs uppercase tracking-wide text-ink-faint">Next operation</p>
              <p className="text-sm leading-relaxed text-ink-muted">
                <Link
                  href={`/developers/explorer?operation=${nextOperation}`}
                  className="font-mono text-xs text-accent underline decoration-line-strong underline-offset-2 transition-colors hover:decoration-ink"
                >
                  {nextOperation}
                </Link>
                {nextEducation ? ` — ${nextEducation.purpose}` : null}
              </p>
            </div>
          ) : (
            <p className="text-2xs text-ink-faint">
              No next operation is recorded for this operation — it ends its
              typical sequence.
            </p>
          )}

          <p className="text-2xs text-ink-faint">
            Education composed from the operation-learning registry and the
            coverage registry — the same authorities the whole console uses.
          </p>
        </div>
      ) : null}
    </div>
  );
}
