/**
 * OperationPage — one operation's documentation, GENERATED from the
 * accepted coverage registry (`@/lib/api/coverage` — the REAL method,
 * path, capability and example body, verbatim) joined with the Task-1
 * operation education (`@/lib/education`): purpose, prerequisites,
 * lifecycle position, typical sequence, field explanations, related
 * concepts, the canonical reason codes it can produce and the next
 * operation.
 *
 * The Console V2 documentation system — the DEC-0128 program, Task 3 of
 * the frozen plan. NO execution control lives here — the API Explorer
 * owns execution; this page links to it. An operation id outside the
 * coverage registry renders the honest not-found state (naming the
 * missing slug): an unsupported operation is never documented into
 * existence.
 */

import Link from "next/link";
import { CodeBlock, EmptyState } from "@/components/ui";
import { getConcept, getOperationEducation } from "@/lib/education";
import { coverageByOperation, type CoverageRecord } from "@/lib/api/coverage";
import {
  DocsLink,
  DocsPageFrame,
  DocsSection,
  MethodChip,
  consoleRouteHref,
} from "./docs-shared";

/** Stable test ids for the operation page. */
export const OPERATION_PAGE_TEST_IDS = {
  root: "docs-operation-page",
  requestLine: "docs-operation-request-line",
  unknown: "docs-operation-unknown",
} as const;

/** The honest not-found state for an unknown operation slug. */
function OperationUnknownState({ operationId }: { operationId: string }) {
  return (
    <DocsPageFrame sectionId="api" pageLabel="Operation not found" title="Operation not found">
      <div data-testid={OPERATION_PAGE_TEST_IDS.unknown}>
        <div className="rounded-md border border-line bg-surface">
          <EmptyState
            title="No operation matches this slug"
            description={
              <>
                The coverage registry — the accepted boundary — has no
                operation with id{" "}
                <span className="font-mono text-ink">{operationId}</span>. An
                operation outside the registry does not exist to document, and
                can never appear as executable either.
              </>
            }
            action={
              <Link
                href="/docs/api"
                className="rounded border border-line-strong bg-raised px-3 py-1.5 text-sm text-ink transition-colors hover:bg-surface"
              >
                Browse the API documentation
              </Link>
            }
          />
        </div>
      </div>
    </DocsPageFrame>
  );
}

function OperationRequestFacts({ record }: { record: CoverageRecord }) {
  return (
    <div className="flex flex-col gap-2">
      <div
        data-testid={OPERATION_PAGE_TEST_IDS.requestLine}
        className="flex flex-wrap items-center gap-2"
      >
        <MethodChip method={record.method} />
        <span className="min-w-0 break-all font-mono text-sm text-ink">{record.path}</span>
        <span className="font-mono text-2xs text-ink-faint">{record.operation}</span>
      </div>
      <div className="flex flex-wrap items-center gap-2 text-2xs">
        {record.platform ? (
          <span className="rounded border border-line px-1.5 py-px font-mono text-ink-muted">
            platform · no authentication
          </span>
        ) : (
          <span className="rounded border border-line px-1.5 py-px font-mono text-ink-muted">
            authenticated
          </span>
        )}
        {record.requiredCapability ? (
          <span className="rounded border border-line px-1.5 py-px font-mono text-ink-muted">
            capability: {record.requiredCapability}
          </span>
        ) : null}
        {record.mutation ? (
          <span className="rounded border border-accent/60 px-1.5 py-px font-mono text-accent">
            mutation · idempotency key required
          </span>
        ) : (
          <span className="rounded border border-line px-1.5 py-px font-mono text-ink-muted">
            read
          </span>
        )}
        <span className="rounded border border-line px-1.5 py-px font-mono text-ink-muted">
          surfaced in{" "}
          <Link
            href={consoleRouteHref(record.uiLocation)}
            className="text-accent hover:underline"
          >
            {record.uiLocation}
          </Link>
        </span>
      </div>
    </div>
  );
}

export function OperationPage({ operationId }: { operationId: string }) {
  const record = coverageByOperation(operationId);
  const education = getOperationEducation(operationId);
  if (!record || !education) {
    return <OperationUnknownState operationId={operationId} />;
  }

  const nextOperationRecord = education.nextOperation
    ? coverageByOperation(education.nextOperation)
    : undefined;

  return (
    <DocsPageFrame
      sectionId="api"
      pageLabel={record.operation}
      title={record.operation}
      lede={education.purpose}
      wide
    >
      <div className="rounded-md border border-line bg-surface px-4 py-3">
        <OperationRequestFacts record={record} />
        {record.description !== education.purpose ? (
          <p className="mt-2 text-sm leading-relaxed text-ink-muted">{record.description}</p>
        ) : null}
      </div>

      <DocsSection id="prerequisites" title="Prerequisites">
        <p className="text-sm leading-relaxed text-ink-muted">{education.prerequisites}</p>
      </DocsSection>

      <DocsSection id="lifecycle-position" title="Lifecycle position">
        <p className="text-sm leading-relaxed text-ink-muted">{education.lifecyclePosition}</p>
      </DocsSection>

      <DocsSection id="typical-sequence" title="Typical sequence">
        <p className="text-sm leading-relaxed text-ink-muted">{education.typicalSequence}</p>
        {nextOperationRecord ? (
          <p className="text-sm leading-relaxed">
            <span className="text-ink-faint">Next operation:</span>{" "}
            <DocsLink
              link={{
                kind: "operation",
                id: nextOperationRecord.operation,
                label: nextOperationRecord.operation,
              }}
              className="font-mono text-xs"
            />
          </p>
        ) : null}
      </DocsSection>

      <DocsSection
        id="request-fields"
        title="Request fields"
        description="The operation's request shape, field by field — the coverage registry's own example fields for mutations, the honest no-body note for bodyless GETs."
      >
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
        {record.example ? (
          <div className="mt-1">
            <p className="mb-1.5 text-xs text-ink-faint">
              Example request body (the registry&apos;s canonical shape, captured from real
              requests):
            </p>
            <CodeBlock
              language="json"
              filename={`${record.method} ${record.path}`}
              code={JSON.stringify(record.example, null, 2)}
            />
          </div>
        ) : null}
      </DocsSection>

      {education.relatedConcepts.length > 0 ? (
        <DocsSection id="related-concepts" title="Related concepts">
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm leading-relaxed">
            {education.relatedConcepts.map((conceptId) => {
              const concept = getConcept(conceptId);
              return (
                <DocsLink
                  key={conceptId}
                  link={{
                    kind: "concept",
                    id: conceptId,
                    label: concept ? concept.term : conceptId,
                  }}
                />
              );
            })}
          </p>
        </DocsSection>
      ) : null}

      {education.relatedErrors.length > 0 ? (
        <DocsSection
          id="related-errors"
          title="Related reason codes"
          description="Canonical reason codes this operation can realistically produce — verbatim, with guidance on the Errors page."
        >
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
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
        </DocsSection>
      ) : null}

      <DocsSection
        id="run-it"
        title="Run it"
        description="This page documents the operation — the API Explorer owns execution."
      >
        <p className="text-sm leading-relaxed text-ink-muted">
          Re-run this operation as a real HTTP request in the{" "}
          <DocsLink
            link={{ kind: "route", id: "/developers/explorer", label: "API Explorer" }}
          />{" "}
          — the same typed client, the same envelope, the same verbatim reason
          codes. The request inspector keeps the reproducible curl of every
          request the console makes.
        </p>
      </DocsSection>
    </DocsPageFrame>
  );
}
