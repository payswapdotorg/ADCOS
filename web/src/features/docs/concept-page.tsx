/**
 * ConceptPage — one concept's documentation, GENERATED from the Task-1
 * concept registry (`@/lib/education`): the six questions every concept
 * page answers, in the frozen order (V2 design §9) — What is it? Why
 * does it matter? When do I use it? What happens in ADCOS? What does
 * the API look like? Where do I go next? — plus the prerequisites as
 * links to the other concept pages, the related guides and the
 * canonical reason codes that anchor the concept's troubleshooting.
 *
 * The Console V2 documentation system — the DEC-0128 program, Task 3 of
 * the frozen plan. Every word of ADCOS semantics renders from the
 * registry verbatim; an unknown concept id renders the honest
 * not-found state (naming the missing slug — the V1 empty/error-state
 * register), never fabricated content.
 */

import Link from "next/link";
import { EmptyState } from "@/components/ui";
import { getConcept, getGuide, type ConceptDefinition, type LearningLink } from "@/lib/education";
import { coverageByOperation } from "@/lib/api/coverage";
import { DocsLink, DocsPageFrame, DocsSection } from "./docs-shared";

/** Stable test ids for the concept page. */
export const CONCEPT_PAGE_TEST_IDS = {
  root: "docs-concept-page",
  question: "docs-concept-question",
  unknown: "docs-concept-unknown",
} as const;

/** The six questions, in the frozen §9 order (also the section order). */
const SIX_QUESTIONS = [
  "What is it?",
  "Why does it matter?",
  "When do I use it?",
  "What happens in ADCOS?",
  "What does the API look like?",
  "Where do I go next?",
] as const;

/** An operation link labeled with the backend's own operation id (mono). */
function opLink(operationId: string): LearningLink {
  return { kind: "operation", id: operationId, label: operationId };
}

/** The honest not-found state for an unknown concept slug. */
function ConceptUnknownState({ conceptId }: { conceptId: string }) {
  return (
    <DocsPageFrame sectionId="concepts" pageLabel="Concept not found" title="Concept not found">
      <div data-testid={CONCEPT_PAGE_TEST_IDS.unknown}>
        <div className="rounded-md border border-line bg-surface">
          <EmptyState
            title="No concept matches this slug"
            description={
              <>
                The concept registry has no concept with id{" "}
                <span className="font-mono text-ink">{conceptId}</span>. The
                registry is the console&apos;s only concept vocabulary — an
                unknown id never renders invented documentation.
              </>
            }
            action={
              <Link
                href="/docs/concepts"
                className="rounded border border-line-strong bg-raised px-3 py-1.5 text-sm text-ink transition-colors hover:bg-surface"
              >
                Browse all concepts
              </Link>
            }
          />
        </div>
      </div>
    </DocsPageFrame>
  );
}

function ConceptPrerequisites({ concept }: { concept: ConceptDefinition }) {
  if (concept.prerequisites.length === 0) {
    return (
      <p className="text-sm text-ink-muted">
        This concept has no prerequisites — it is an entry point into the
        model.
      </p>
    );
  }
  return (
    <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm leading-relaxed">
      <span className="text-ink-muted">Understand first:</span>
      {concept.prerequisites.map((prerequisiteId) => {
        const prerequisite = getConcept(prerequisiteId);
        return (
          <DocsLink
            key={prerequisiteId}
            link={{
              kind: "concept",
              id: prerequisiteId,
              label: prerequisite ? prerequisite.term : prerequisiteId,
            }}
          />
        );
      })}
    </p>
  );
}

function ConceptApiLook({ concept }: { concept: ConceptDefinition }) {
  const operations = concept.relatedOperations;
  const apiLook = concept.apiLook;
  const runnable = concept.runnableExample;

  if (!apiLook && operations.length === 0) {
    return (
      <p className="text-sm leading-relaxed text-ink-muted">
        No API operation of the accepted boundary exposes this concept
        directly — it is documented architecture, not an addressable resource
        of this deployment&apos;s HTTP surface.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {apiLook ? (
        <div className="rounded-md border border-line bg-raised px-3 py-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-2xs uppercase tracking-wide text-ink-faint">
              operation
            </span>
            <DocsLink
              link={opLink(apiLook.operationId)}
              className="font-mono text-xs"
            />
            {(() => {
              const record = coverageByOperation(apiLook.operationId);
              return record ? (
                <span className="font-mono text-xs text-ink-muted">
                  {record.method} {record.path}
                </span>
              ) : null;
            })()}
          </div>
          <p className="mt-1.5 text-sm leading-relaxed text-ink-muted">{apiLook.note}</p>
        </div>
      ) : null}
      {operations.length > 0 ? (
        <div>
          <p className="text-xs text-ink-faint">
            Operations that expose this concept
          </p>
          <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
            {operations.map((operationId) => (
              <DocsLink key={operationId} link={opLink(operationId)} className="font-mono text-xs" />
            ))}
          </p>
        </div>
      ) : null}
      {runnable ? (
        <p className="text-sm leading-relaxed text-ink-muted">
          Runnable: <DocsLink link={opLink(runnable.operationId)} /> —{" "}
          {runnable.label}. Execution belongs to the{" "}
          <DocsLink
            link={{ kind: "route", id: "/developers/explorer", label: "API Explorer" }}
          />
          .
        </p>
      ) : null}
    </div>
  );
}

function ConceptNextSteps({ concept }: { concept: ConceptDefinition }) {
  return (
    <div className="flex flex-col gap-3">
      {concept.nextSteps.length > 0 ? (
        <ul className="flex flex-col gap-1.5">
          {concept.nextSteps.map((link) => (
            <li key={`${link.kind}:${link.id}`} className="text-sm leading-relaxed">
              <DocsLink link={link} />
            </li>
          ))}
        </ul>
      ) : null}
      {concept.relatedGuides.length > 0 ? (
        <div>
          <p className="text-xs text-ink-faint">Guides that walk through this concept</p>
          <ul className="mt-1 flex flex-col gap-1.5">
            {concept.relatedGuides.map((guideId) => {
              const guide = getGuide(guideId);
              return (
                <li key={guideId} className="text-sm leading-relaxed">
                  <DocsLink
                    link={{ kind: "guide", id: guideId, label: guide ? guide.title : guideId }}
                  />
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
      {concept.relatedTroubleshooting.length > 0 ? (
        <div>
          <p className="text-xs text-ink-faint">
            Canonical reason codes that anchor this concept&apos;s troubleshooting
          </p>
          <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
            {concept.relatedTroubleshooting.map((code) => (
              <Link
                key={code}
                href={`/docs/errors#code-${code}`}
                className="rounded border border-line bg-raised px-1.5 py-px font-mono text-2xs text-ink-muted transition-colors hover:border-line-strong hover:text-ink"
              >
                {code}
              </Link>
            ))}
          </p>
        </div>
      ) : null}
    </div>
  );
}

export function ConceptPage({ conceptId }: { conceptId: string }) {
  const concept = getConcept(conceptId);
  if (!concept) {
    return <ConceptUnknownState conceptId={conceptId} />;
  }

  return (
    <DocsPageFrame
      sectionId="concepts"
      pageLabel={concept.term}
      title={concept.term}
      aside={
        <span className="font-mono text-xs text-ink-faint">
          concept · {concept.id}
        </span>
      }
      lede={concept.summary}
    >
      <div className="rounded-md border border-line bg-surface px-4 py-3">
        <ConceptPrerequisites concept={concept} />
      </div>

      <DocsSection id="what-is-it" title={SIX_QUESTIONS[0]}>
        <p className="text-sm leading-relaxed text-ink">{concept.summary}</p>
      </DocsSection>

      <DocsSection id="why-it-matters" title={SIX_QUESTIONS[1]}>
        <p className="text-sm leading-relaxed text-ink-muted">{concept.whyItMatters}</p>
      </DocsSection>

      <DocsSection id="when-to-use" title={SIX_QUESTIONS[2]}>
        <p className="text-sm leading-relaxed text-ink-muted">{concept.whenToUse}</p>
      </DocsSection>

      <DocsSection
        id="what-happens"
        title={SIX_QUESTIONS[3]}
        description={
          concept.relatedObjects.length > 0
            ? `Related objects: ${concept.relatedObjects.join(", ")}`
            : undefined
        }
      >
        <p className="text-sm leading-relaxed text-ink-muted">{concept.whatHappens}</p>
      </DocsSection>

      <DocsSection id="api-look" title={SIX_QUESTIONS[4]}>
        <ConceptApiLook concept={concept} />
      </DocsSection>

      <DocsSection id="next" title={SIX_QUESTIONS[5]}>
        <ConceptNextSteps concept={concept} />
      </DocsSection>
    </DocsPageFrame>
  );
}

export { SIX_QUESTIONS as CONCEPT_SIX_QUESTIONS };
