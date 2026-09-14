"use client";

/**
 * PlaybookPage — one guide's stepped walkthrough at /playbooks/<id>,
 * GENERATED from the Task-1 guide registry (`@/lib/education`): the
 * title and purpose, every step with its title, its verbatim detail and
 * its typed link rendered as a REAL affordance, the client-side step
 * progress, the related concepts (ConceptLink chips) and the related
 * operations (Explorer deep-links).
 *
 * The DEC-0128 program, Task 6 of the frozen plan (V2 design §11).
 * Honesty rules:
 * - the step details are the registry's OWN wording, rendered verbatim
 *   — where a step names a capability this deployment does not expose,
 *   the record's honest wording stands, never softened;
 * - every step link that names a console route renders the explicit
 *   "Open in workbench" handoff carrying `?from=<this playbook's path>`
 *   (the docs' contextual return-path convention mirrored — Task 7);
 * - the progress is CLIENT STATE ONLY (a checklist for this visit);
 *   nothing is persisted and no session state is invented;
 * - an unknown guide id renders the honest not-found state naming the
 *   missing slug — never fabricated steps.
 */

import { useState } from "react";
import Link from "next/link";
import { getConcept, getGuide, getOperationEducation } from "@/lib/education";
import { EmptyState, SearchIcon } from "@/components/ui";
import { ConceptLink } from "@/features/learning";
import { PlaybookContextSlot } from "./playbook-context";
import { OperationDeepLink, StepLinkAffordance, playbookPath } from "./playbook-links";

/** Stable test ids for the playbook page. */
export const PLAYBOOK_PAGE_TEST_IDS = {
  root: "playbook-page",
  step: "playbook-step",
  stepToggle: "playbook-step-toggle",
  progress: "playbook-progress",
  unknown: "playbook-unknown",
} as const;

/** The honest not-found state for an unknown guide slug. */
function PlaybookUnknownState({ guideId }: { guideId: string }) {
  return (
    <div
      data-testid={PLAYBOOK_PAGE_TEST_IDS.unknown}
      className="mx-auto w-full max-w-3xl px-gutter py-rhythm"
    >
      <PlaybookContextSlot />
      <div className="rounded-md border border-line bg-surface">
        <EmptyState
          icon={<SearchIcon size={16} />}
          title="No playbook matches this slug"
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
              href="/playbooks"
              className="rounded border border-line-strong bg-raised px-3 py-1.5 text-sm text-ink transition-colors hover:bg-surface"
            >
              Browse all playbooks
            </Link>
          }
        />
      </div>
    </div>
  );
}

export function PlaybookPage({ guideId }: { guideId: string }) {
  const guide = getGuide(guideId);
  // the step checklist — client state for THIS visit only
  const [completed, setCompleted] = useState<number[]>([]);

  if (!guide) {
    return <PlaybookUnknownState guideId={guideId} />;
  }

  const from = playbookPath(guide.id);

  function toggleStep(index: number): void {
    setCompleted((current) =>
      current.includes(index)
        ? current.filter((value) => value !== index)
        : [...current, index],
    );
  }

  return (
    <div
      data-testid={PLAYBOOK_PAGE_TEST_IDS.root}
      className="mx-auto w-full max-w-3xl px-gutter py-rhythm"
    >
      <PlaybookContextSlot />
      <nav aria-label="Playbooks" className="flex items-center gap-1.5 text-xs text-ink-faint">
        <Link href="/playbooks" className="rounded text-ink-muted hover:text-ink">
          Playbooks
        </Link>
        <span aria-hidden="true">›</span>
        <span aria-current="page" className="text-ink-muted">
          {guide.title}
        </span>
      </nav>

      <header className="mt-3 flex flex-col gap-2">
        <h1 className="text-xl font-semibold text-ink">{guide.title}</h1>
        <p className="max-w-2xl text-sm leading-relaxed text-ink-muted">{guide.purpose}</p>
        <p className="font-mono text-2xs text-ink-faint">
          playbook · {guide.id} · {guide.steps.length} steps
        </p>
      </header>

      <p
        data-testid={PLAYBOOK_PAGE_TEST_IDS.progress}
        aria-live="polite"
        className="mt-4 font-mono text-2xs text-ink-faint"
      >
        {completed.length} of {guide.steps.length} steps marked complete — the
        checklist lives in this visit only (nothing is persisted)
      </p>

      <ol className="mt-4 flex flex-col gap-3">
        {guide.steps.map((step, index) => {
          const done = completed.includes(index);
          return (
            <li
              key={`${index}-${step.title}`}
              data-testid={PLAYBOOK_PAGE_TEST_IDS.step}
              data-step={index}
              data-complete={done ? "true" : "false"}
              className={`flex flex-col gap-2 rounded-md border bg-surface px-4 py-3.5 ${
                done ? "border-positive/40" : "border-line"
              }`}
            >
              <div className="flex flex-wrap items-baseline gap-2">
                <span
                  className={`inline-flex h-6 min-w-6 items-center justify-center rounded-full border px-1.5 font-mono text-2xs ${
                    done
                      ? "border-positive/60 bg-positive/10 text-positive"
                      : "border-line-strong bg-raised text-ink-muted"
                  }`}
                  aria-hidden="true"
                >
                  {done ? "✓" : index + 1}
                </span>
                <h2 className="text-sm font-semibold text-ink">
                  {index + 1}. {step.title}
                </h2>
              </div>

              {/* the registry's own wording, verbatim — never softened */}
              <p className="text-sm leading-relaxed text-ink-muted">{step.detail}</p>

              {step.link ? (
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  <StepLinkAffordance link={step.link} from={from} />
                </div>
              ) : null}

              <div className="mt-1">
                <button
                  type="button"
                  data-testid={PLAYBOOK_PAGE_TEST_IDS.stepToggle}
                  data-step={index}
                  aria-pressed={done}
                  onClick={() => toggleStep(index)}
                  className={`inline-flex min-h-9 items-center rounded-md border px-3 text-xs transition-colors ${
                    done
                      ? "border-positive/60 bg-positive/10 text-positive hover:bg-positive/20"
                      : "border-line-strong bg-raised text-ink hover:bg-surface"
                  }`}
                >
                  {done ? "Completed — undo" : "Mark this step complete"}
                </button>
              </div>
            </li>
          );
        })}
      </ol>

      {guide.relatedConcepts.length > 0 ? (
        <section aria-label="Concepts on this path" className="mt-6">
          <h2 className="text-sm font-semibold text-ink">Concepts on this path</h2>
          <ul className="mt-2 flex flex-wrap gap-2">
            {guide.relatedConcepts.map((conceptId) => (
              <li key={conceptId}>
                <ConceptLink id={conceptId} mode="chip" />
              </li>
            ))}
          </ul>
          <p className="mt-2 text-2xs text-ink-faint">
            The chips open the concept&apos;s education in a drawer — the
            current step stays put underneath.
          </p>
        </section>
      ) : null}

      {guide.relatedOperations.length > 0 ? (
        <section aria-label="Operations on this path" className="mt-6">
          <h2 className="text-sm font-semibold text-ink">Operations on this path</h2>
          <ul className="mt-2 flex flex-col gap-1.5">
            {guide.relatedOperations.map((operationId) => (
              <OperationDeepLink
                key={operationId}
                operationId={operationId}
                from={from}
                note={getOperationEducation(operationId)?.purpose}
              />
            ))}
          </ul>
          <p className="mt-2 text-2xs text-ink-faint">
            Every link opens the operation preselected in the API Explorer —
            real requests, the same typed client.
          </p>
        </section>
      ) : null}

      <section aria-label="After this playbook" className="mt-6">
        <h2 className="text-sm font-semibold text-ink">After this playbook</h2>
        <p className="mt-1 text-sm leading-relaxed text-ink-muted">
          The documentation twin of this path lives under{" "}
          <Link
            href={`/docs/guides/${guide.id}`}
            className="text-accent underline decoration-line-strong underline-offset-2 hover:decoration-ink"
          >
            Docs → Guides → {guide.title}
          </Link>
          ; the concept pages behind the chips above carry the deeper
          explanations
          {guide.relatedConcepts.length > 0
            ? ` (start with ${getConcept(guide.relatedConcepts[0])?.term ?? guide.relatedConcepts[0]})`
            : ""}
          .
        </p>
      </section>
    </div>
  );
}
