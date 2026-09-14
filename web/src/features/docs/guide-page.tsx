/**
 * GuidePage — one playbook's documentation, GENERATED from the Task-1
 * guide registry (`@/lib/education`): the title, the purpose, every
 * step with its detail and its typed link, then the related concepts
 * and operations. The steps' prose is the registry's own — honest
 * about what the current deployment supports.
 *
 * The Console V2 documentation system — the DEC-0128 program, Task 3 of
 * the frozen plan. An unknown guide id renders the honest not-found
 * state (naming the missing slug), never fabricated steps.
 */

import Link from "next/link";
import { EmptyState } from "@/components/ui";
import { getConcept, getGuide, type LearningLink } from "@/lib/education";
import { DocsLink, DocsPageFrame, DocsSection } from "./docs-shared";

/** Stable test ids for the guide page. */
export const GUIDE_PAGE_TEST_IDS = {
  root: "docs-guide-page",
  step: "docs-guide-step",
  unknown: "docs-guide-unknown",
} as const;

/** An operation link labeled with the backend's own operation id (mono). */
function opLink(operationId: string): LearningLink {
  return { kind: "operation", id: operationId, label: operationId };
}

/** The honest not-found state for an unknown guide slug. */
function GuideUnknownState({ guideId }: { guideId: string }) {
  return (
    <DocsPageFrame sectionId="guides" pageLabel="Guide not found" title="Guide not found">
      <div data-testid={GUIDE_PAGE_TEST_IDS.unknown}>
        <div className="rounded-md border border-line bg-surface">
          <EmptyState
            title="No guide matches this slug"
            description={
              <>
                The guide registry has no playbook with id{" "}
                <span className="font-mono text-ink">{guideId}</span>. The
                registry is the console&apos;s only playbook vocabulary — an
                unknown id never renders invented steps.
              </>
            }
            action={
              <Link
                href="/docs/guides"
                className="rounded border border-line-strong bg-raised px-3 py-1.5 text-sm text-ink transition-colors hover:bg-surface"
              >
                Browse all guides
              </Link>
            }
          />
        </div>
      </div>
    </DocsPageFrame>
  );
}

export function GuidePage({ guideId }: { guideId: string }) {
  const guide = getGuide(guideId);
  if (!guide) {
    return <GuideUnknownState guideId={guideId} />;
  }

  return (
    <DocsPageFrame
      sectionId="guides"
      pageLabel={guide.title}
      title={guide.title}
      aside={
        <span className="font-mono text-xs text-ink-faint">guide · {guide.id}</span>
      }
      lede={guide.purpose}
    >
      <ol className="flex flex-col gap-3">
        {guide.steps.map((step, index) => (
          <li key={`${index}-${step.title}`} data-testid={GUIDE_PAGE_TEST_IDS.step}>
            <DocsSection title={`${index + 1}. ${step.title}`}>
              <p className="text-sm leading-relaxed text-ink-muted">{step.detail}</p>
              {step.link ? (
                <p className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="text-ink-faint" aria-hidden="true">
                    →
                  </span>
                  <DocsLink
                    link={step.link}
                    className={
                      step.link.kind === "operation" ? "font-mono text-xs" : undefined
                    }
                  />
                </p>
              ) : null}
            </DocsSection>
          </li>
        ))}
      </ol>

      {guide.relatedConcepts.length > 0 ? (
        <DocsSection id="related-concepts" title="Concepts on this path">
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm leading-relaxed">
            {guide.relatedConcepts.map((conceptId) => {
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

      {guide.relatedOperations.length > 0 ? (
        <DocsSection id="related-operations" title="Operations on this path">
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
            {guide.relatedOperations.map((operationId) => (
              <DocsLink
                key={operationId}
                link={opLink(operationId)}
                className="font-mono text-xs"
              />
            ))}
          </p>
        </DocsSection>
      ) : null}
    </DocsPageFrame>
  );
}
