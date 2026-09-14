"use client";

/**
 * PlaybookIndex — the /playbooks surface: the seven goal-oriented
 * playbooks, GENERATED from the Task-1 guide registry (`@/lib/education`
 * GUIDES) and grouped by experience goal (the frozen V2 design §4's
 * Build / Understand / Integrate / Diagnose groups), with the
 * route-local search filtering the registry data in the browser only
 * (design §9: no backend search service).
 *
 * The DEC-0128 program, Task 6 of the frozen plan. The row set IS the
 * registry — a playbook outside the guide registry can never appear
 * here, and an unknown search term gets the honest empty state (never
 * a fabricated match). Each row carries the guide's own title, purpose
 * and step count, plus its related concepts as ConceptLink chips (the
 * W1 primitive — the "What is this?" drawer, no page leave).
 */

import { useState } from "react";
import Link from "next/link";
import { GUIDES, getConcept, type GuideDefinition } from "@/lib/education";
import { EmptyState, FilterBar } from "@/components/ui";
import { ConceptLink } from "@/features/learning";
import { matchesDocsTerm } from "@/features/docs/docs-shared";
import { PlaybookContextSlot } from "./playbook-context";

/** Stable test ids for the playbooks index. */
export const PLAYBOOK_INDEX_TEST_IDS = {
  root: "playbook-index",
  group: "playbook-index-group",
  row: "playbook-index-row",
  empty: "playbook-index-empty",
  search: "playbook-index-search",
} as const;

/**
 * The experience-goal groups (the design §4 Build / Understand /
 * Integrate / Diagnose groups the §11 playbook list sorts into). The
 * grouping is THIS surface's presentation choice; the playbooks
 * themselves are registry data.
 */
const PLAYBOOK_GROUPS: { id: string; label: string; intro: string; guideIds: string[] }[] = [
  {
    id: "build",
    label: "Build",
    intro: "Take an application from zero to an active, understood connectivity contract.",
    guideIds: ["first-connectivity-application"],
  },
  {
    id: "understand",
    label: "Understand",
    intro: "Read the objects and the reasoning behind them like an operator.",
    guideIds: ["understand-connectivity-contract", "understand-provider-selection"],
  },
  {
    id: "integrate",
    label: "Integrate",
    intro: "Wire your own backend — or a provider adapter — into the ADCOS boundary.",
    guideIds: ["integrate-adcos-api", "integrate-provider-adapter"],
  },
  {
    id: "diagnose",
    label: "Diagnose",
    intro: "Work failures and degradation from symptom to verbatim reason code.",
    guideIds: ["diagnose-fulfillment-failure", "handle-degraded-connectivity"],
  },
];

/* The module-load guard: every registry guide lands in EXACTLY one group. */
{
  const grouped = PLAYBOOK_GROUPS.flatMap((group) => group.guideIds);
  const registry = GUIDES.map((guide) => guide.id);
  for (const id of registry) {
    const hits = grouped.filter((candidate) => candidate === id);
    if (hits.length === 0) {
      throw new Error(`playbook index: guide "${id}" is in no experience-goal group`);
    }
    if (hits.length > 1) {
      throw new Error(`playbook index: guide "${id}" is in more than one group`);
    }
  }
}

/** Does this guide match the search term (title, purpose, concepts)? */
function guideMatches(guide: GuideDefinition, term: string): boolean {
  const conceptTerms = guide.relatedConcepts.map(
    (conceptId) => getConcept(conceptId)?.term ?? conceptId,
  );
  return matchesDocsTerm(term, [guide.title, guide.id, guide.purpose, ...conceptTerms]);
}

export function PlaybookIndex() {
  const [term, setTerm] = useState("");

  const groups = PLAYBOOK_GROUPS.map((group) => ({
    ...group,
    guides: GUIDES.filter(
      (guide) => group.guideIds.includes(guide.id) && guideMatches(guide, term),
    ),
  })).filter((group) => group.guides.length > 0);

  const matchCount = GUIDES.filter((guide) => guideMatches(guide, term)).length;

  return (
    <div
      data-testid={PLAYBOOK_INDEX_TEST_IDS.root}
      className="mx-auto w-full max-w-3xl px-gutter py-rhythm"
    >
      <PlaybookContextSlot />
      <h1 className="text-xl font-semibold text-ink">Playbooks</h1>
      <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-muted">
        Goal-oriented guided paths, generated from the console&apos;s guide
        registry — every step is a real console operation, route or
        documentation page, and every step keeps its honest wording about
        what this deployment exposes.
      </p>

      <div className="mt-5" data-testid={PLAYBOOK_INDEX_TEST_IDS.search}>
        <FilterBar
          search={{
            value: term,
            onChange: setTerm,
            placeholder: "Filter playbooks",
          }}
          right={
            <span className="font-mono text-2xs text-ink-faint">
              {term.trim().length > 0
                ? `${matchCount}/${GUIDES.length}`
                : `${GUIDES.length} playbooks`}
            </span>
          }
        />
      </div>

      <div className="mt-6 flex flex-col gap-6">
        {groups.length === 0 ? (
          <div data-testid={PLAYBOOK_INDEX_TEST_IDS.empty}>
            <div className="rounded-md border border-line bg-surface">
              <EmptyState
                title="No playbook matches"
                description={
                  <>
                    No playbook in the guide registry matches{" "}
                    <span className="font-mono text-ink">{term.trim()}</span>.
                    The registry is the console&apos;s only playbook
                    vocabulary — nothing is invented to fill a match.
                  </>
                }
                action={
                  <button
                    type="button"
                    onClick={() => setTerm("")}
                    className="rounded border border-line-strong bg-raised px-3 py-1.5 text-sm text-ink transition-colors hover:bg-surface"
                  >
                    Clear filter
                  </button>
                }
              />
            </div>
          </div>
        ) : (
          groups.map((group) => (
            <section
              key={group.id}
              id={`group-${group.id}`}
              data-testid={PLAYBOOK_INDEX_TEST_IDS.group}
              data-group={group.id}
              aria-labelledby={`group-${group.id}-heading`}
            >
              <h2
                id={`group-${group.id}-heading`}
                className="text-2xs font-normal uppercase tracking-wide text-ink-faint"
              >
                {group.label}
                <span className="ml-2 font-mono normal-case">{group.guides.length}</span>
              </h2>
              <p className="mt-1 text-sm leading-relaxed text-ink-muted">{group.intro}</p>
              <ul className="mt-2 flex flex-col divide-y divide-line rounded-md border border-line bg-surface">
                {group.guides.map((guide) => (
                  <li
                    key={guide.id}
                    data-testid={PLAYBOOK_INDEX_TEST_IDS.row}
                    data-guide={guide.id}
                    className="flex flex-col gap-1.5 px-4 py-3"
                  >
                    <Link
                      href={`/playbooks/${guide.id}`}
                      className="flex flex-col gap-1 rounded transition-colors hover:bg-raised/40"
                    >
                      <span className="flex flex-wrap items-baseline gap-2">
                        <span className="text-sm font-medium text-accent">{guide.title}</span>
                        <span className="font-mono text-2xs text-ink-faint">
                          {guide.steps.length} steps
                        </span>
                      </span>
                      <span className="text-sm leading-relaxed text-ink-muted">
                        {guide.purpose}
                      </span>
                    </Link>
                    {guide.relatedConcepts.length > 0 ? (
                      <span className="flex flex-wrap gap-1.5">
                        {guide.relatedConcepts.map((conceptId) => (
                          <ConceptLink key={conceptId} id={conceptId} mode="chip" />
                        ))}
                      </span>
                    ) : null}
                  </li>
                ))}
              </ul>
            </section>
          ))
        )}
      </div>

      <p className="mt-6 text-xs text-ink-faint">
        The playbooks&apos; documentation twins live under{" "}
        <Link
          href="/docs/guides"
          className="text-accent underline decoration-line-strong underline-offset-2 hover:decoration-ink"
        >
          Docs → Guides
        </Link>
        .
      </p>
    </div>
  );
}
