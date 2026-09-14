"use client";

/**
 * DocsHome — the documentation home: the docs information architecture
 * itself (the frozen V2 design §9 tree — Start here, Concepts, Guides,
 * API, SDKs, Errors, Troubleshooting, Reference) with the route-local
 * search filtering the IA by term in the browser.
 *
 * The Console V2 documentation system — the DEC-0128 program, Task 3 of
 * the frozen plan. The counts on the IA entries are derived from the
 * Task-1 registries and the coverage registry at render time — never
 * hand-maintained. The Quickstart entry links the `/quickstart` route
 * owned by the V2 first-run wave (plan Task 5): the href is linked
 * only, this feature does not create it.
 */

import { useState } from "react";
import Link from "next/link";
import { COVERAGE } from "@/lib/api/coverage";
import { CONCEPTS, GUIDES } from "@/lib/education";
import { EmptyState, ExternalLinkIcon } from "@/components/ui";
import { DocsContextSlot } from "./docs-context";
import { DOCS_SECTIONS, matchesDocsTerm } from "./docs-shared";
import { DocsSearch } from "./docs-search";

/** Stable test ids for the docs home. */
export const DOCS_HOME_TEST_IDS = {
  root: "docs-home",
  group: "docs-home-group",
  entry: "docs-home-entry",
  empty: "docs-home-empty",
} as const;

/** One addressable docs surface in the IA. */
interface DocsHomeEntry {
  title: string;
  href: string;
  description: string;
  meta?: string;
  /** The entry leaves documentation (console/quickstart surface). */
  leaves?: boolean;
}

/** The Start here sub-pages (curated — the only hand-written IA leaf text). */
const START_ENTRIES: DocsHomeEntry[] = [
  {
    title: "What is ADCOS?",
    href: "/docs/start/what-is-adcos",
    description:
      "The product explanation: what ADCOS does, what it deliberately is not, and the mental model in one line.",
  },
  {
    title: "How ADCOS works",
    href: "/docs/start/how-it-works",
    description:
      "The mental model lifecycle, stage by stage — describe requirement, eligibility, plan, fulfillment, assurance, continuous fulfillment.",
  },
  {
    title: "First connectivity contract",
    href: "/docs/start/first-contract",
    description:
      "The first contract walkthrough — from recording an intent to inspecting evidence, honest about the demonstration context.",
  },
  {
    title: "Quickstart",
    href: "/quickstart",
    description:
      "The guided first journey through a real contract lifecycle, step by step in the console.",
    leaves: true,
  },
];

/** Registry-derived metadata for the IA section entries. */
function sectionMeta(sectionId: string): string | undefined {
  switch (sectionId) {
    case "concepts":
      return `${CONCEPTS.length} concepts`;
    case "guides":
      return `${GUIDES.length} playbooks`;
    case "api":
      return `${COVERAGE.length} operations`;
    case "errors":
      return "canonical reason codes";
    default:
      return undefined;
  }
}

/** The full IA as renderable entries (section groups in §9 order). */
function docsIaEntries(): {
  sectionId: string;
  sectionLabel: string;
  sectionHref: string;
  entries: DocsHomeEntry[];
}[] {
  const groups = DOCS_SECTIONS.map((section) => ({
    sectionId: section.id,
    sectionLabel: section.label,
    sectionHref: section.href,
    entries:
      section.id === "start"
        ? START_ENTRIES
        : [
            {
              title: section.label,
              href: section.href,
              description: section.description,
              meta: sectionMeta(section.id),
            },
          ],
  }));
  return groups;
}

export function DocsHome() {
  const [term, setTerm] = useState("");
  const groups = docsIaEntries();

  const filtered = groups
    .map((group) => ({
      ...group,
      entries: group.entries.filter((entry) =>
        matchesDocsTerm(term, [entry.title, entry.description, entry.meta]),
      ),
    }))
    .filter((group) => group.entries.length > 0);

  const totalEntries = groups.reduce((sum, group) => sum + group.entries.length, 0);
  const shownEntries = filtered.reduce((sum, group) => sum + group.entries.length, 0);

  return (
    <div data-testid={DOCS_HOME_TEST_IDS.root} className="mx-auto w-full max-w-3xl px-gutter py-rhythm">
      <DocsContextSlot />
      <h1 className="text-xl font-semibold text-ink">ADCOS documentation</h1>
      <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-muted">
        Documentation for developers using the console and the ADCOS API — what
        the system is, the concepts behind it, every operation of the accepted
        boundary, and how to diagnose what goes wrong. It is written for you,
        the developer, and is deliberately distinct from the repository&apos;s
        internal architecture records.
      </p>
      <div className="mt-5">
        <DocsSearch
          value={term}
          onChange={setTerm}
          placeholder="Search the documentation"
          hint={term.trim().length > 0 ? `${shownEntries}/${totalEntries}` : `${totalEntries} pages`}
        />
      </div>
      <div className="mt-6 flex flex-col gap-5">
        {filtered.length === 0 ? (
          <div data-testid={DOCS_HOME_TEST_IDS.empty}>
            <EmptyState
              title="No documentation matches"
              description={
                <>
                  Nothing in the documentation index matches{" "}
                  <span className="font-mono text-ink">{term.trim()}</span>.
                  Clear the search to browse the full index.
                </>
              }
              action={
                <button
                  type="button"
                  onClick={() => setTerm("")}
                  className="rounded border border-line-strong bg-raised px-3 py-1.5 text-sm text-ink transition-colors hover:bg-surface"
                >
                  Clear search
                </button>
              }
            />
          </div>
        ) : (
          filtered.map((group) => (
            <section
              key={group.sectionId}
              data-testid={DOCS_HOME_TEST_IDS.group}
              data-section={group.sectionId}
              aria-labelledby={`docs-home-${group.sectionId}`}
            >
              <h2
                id={`docs-home-${group.sectionId}`}
                className="text-2xs font-normal uppercase tracking-wide text-ink-faint"
              >
                <Link href={group.sectionHref} className="rounded hover:text-ink">
                  {group.sectionLabel}
                </Link>
              </h2>
              <ul className="mt-2 flex flex-col divide-y divide-line rounded-md border border-line bg-surface">
                {group.entries.map((entry) => (
                  <li key={entry.href} data-testid={DOCS_HOME_TEST_IDS.entry}>
                    <Link
                      href={entry.href}
                      className="flex flex-col gap-1 px-4 py-3 transition-colors hover:bg-raised/40"
                    >
                      <span className="flex items-center gap-2 text-sm font-medium text-accent">
                        {entry.title}
                        {entry.leaves ? (
                          <ExternalLinkIcon size={10} className="text-ink-faint" />
                        ) : null}
                      </span>
                      <span className="text-sm leading-relaxed text-ink-muted">
                        {entry.description}
                      </span>
                      {entry.meta ? (
                        <span className="font-mono text-2xs text-ink-faint">{entry.meta}</span>
                      ) : null}
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          ))
        )}
      </div>
    </div>
  );
}
