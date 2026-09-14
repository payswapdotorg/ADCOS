"use client";

/**
 * NextStep / NextSteps — the "where to go next" affordances (V2 design
 * §13: goal-oriented entry points; §8: the learning model's typed links).
 *
 * The Console V2 learning primitives — DEC-0128, Task 2 of the frozen
 * plan. PURE PRESENTATION over the Task-1 education registry: a
 * LearningLink is registry DATA, and these primitives only render its
 * kind-aware affordance — no fetch, no stores, no invented labels.
 *
 * Kind conventions (the id's vocabulary decides the href):
 * - concept  → a "Learn: <label>" chip opening the ConceptExplainer
 *   drawer (education without leaving the current task);
 * - operation→ an "API: <label>" link to the V1 API Explorer's own
 *   ?operation= deep link (the existing sanctioned convention);
 * - guide    → a "Guide: <label>" link to the docs feature's guide page
 *   (/docs/guides/<id> — W1-c owns the routes);
 * - route    → a plain <label> link to the link's id AS the href;
 * - docs     → a "Docs: <label>" link: /docs/concepts/<id> when the id
 *   is a concept id (the mandated convention), /docs/<id> for the
 *   registry's docs-IA slugs ("errors", "api/authentication") that are
 *   not concept ids — again W1-c's routes, this primitive only builds
 *   the href.
 */

import Link from "next/link";
import { getConcept } from "@/lib/education";
import type { LearningLink } from "@/lib/education";
import {
  EvidenceIcon,
  ExternalLinkIcon,
  SearchIcon,
  TerminalIcon,
} from "@/components/ui";
import { ConceptExplainer } from "./concept-explainer";
import { UnknownConceptAffordance } from "./concept-link";

/** Stable test id for the rendered "where to go next" list. */
export const NEXT_STEPS_TEST_ID = "next-steps";

/** The drawer-opening chip presentation (concept kind). */
const BUTTON_CLASSES =
  "inline-flex min-h-11 items-center gap-2 rounded-md border border-line-strong " +
  "bg-raised px-3 text-sm text-ink transition-colors hover:bg-surface";

/** The quiet navigation-row presentation (link kinds). */
const LINK_CLASSES =
  "inline-flex min-h-11 items-center gap-2 rounded-md px-2 text-sm text-ink " +
  "underline decoration-line-strong underline-offset-2 transition-colors hover:decoration-ink";

/**
 * Build the href for a docs-kind link. Concept ids keep the mandated
 * /docs/concepts/<id> shape; the registry's docs-IA slugs (which are not
 * concept ids) resolve to /docs/<slug>. The docs feature (W1-c) owns the
 * actual routes — this helper only builds the href, honestly, from the
 * registry's own vocabulary.
 */
export function docsHref(id: string): string {
  return getConcept(id) ? `/docs/concepts/${id}` : `/docs/${id}`;
}

/**
 * Resolve a route-kind link's id onto a REAL navigable href. Route
 * templates (`/connectivity/contracts/[id]`) are registry vocabulary for
 * per-object pages — the app router forbids dynamic hrefs in <Link>, so a
 * template de-resolves to its static workspace ancestor (the same
 * de-templating contract the docs feature's consoleRouteHref applies).
 */
export function routeHref(route: string): string {
  if (!route.includes("[")) return route;
  const segments = route.split("/").filter(Boolean);
  while (segments.length > 0) {
    const candidate = `/${segments.join("/")}`;
    if (CONSOLE_ROUTES.has(candidate)) return candidate;
    segments.pop();
  }
  return "/";
}

/** The console's static routes (the de-templating targets). */
const CONSOLE_ROUTES = new Set([
  "/",
  "/connectivity",
  "/networks",
  "/fulfillment",
  "/evidence",
  "/developers",
  "/developers/explorer",
  "/developers/requests",
  "/assurance",
  "/settings",
  "/settings/errors",
  "/quickstart",
  "/tour",
  "/playbooks",
  "/docs",
]);

/**
 * NextStep — one kind-aware "where to go next" affordance. Every href is
 * derived from the link's own id; every label from the link's own label.
 * An unknown concept id renders the honest compact unknown state (the
 * disabled affordance of concept-link's convention), never a fabricated
 * destination.
 */
export function NextStep({ link }: { link: LearningLink }) {
  switch (link.kind) {
    case "concept": {
      if (!getConcept(link.id)) {
        return <UnknownConceptAffordance id={link.id} mode="chip" />;
      }
      return (
        <ConceptExplainer
          id={link.id}
          mode="drawer"
          trigger={({ ref, open, onToggle }) => (
            <button
              ref={ref}
              type="button"
              onClick={onToggle}
              aria-haspopup="dialog"
              aria-expanded={open}
              className={BUTTON_CLASSES}
            >
              <SearchIcon size={14} className="shrink-0 text-ink-faint" />
              Learn: {link.label}
            </button>
          )}
        />
      );
    }
    case "operation":
      return (
        <Link
          href={`/developers/explorer?operation=${link.id}`}
          className={LINK_CLASSES}
        >
          <TerminalIcon size={14} className="shrink-0 text-ink-faint" />
          API: {link.label}
        </Link>
      );
    case "guide":
      return (
        <Link href={`/docs/guides/${link.id}`} className={LINK_CLASSES}>
          <EvidenceIcon size={14} className="shrink-0 text-ink-faint" />
          Guide: {link.label}
        </Link>
      );
    case "docs":
      return (
        <Link href={docsHref(link.id)} className={LINK_CLASSES}>
          <ExternalLinkIcon size={14} className="shrink-0 text-ink-faint" />
          Docs: {link.label}
        </Link>
      );
    case "route":
      return (
        <Link href={routeHref(link.id)} className={LINK_CLASSES}>
          <ExternalLinkIcon size={14} className="shrink-0 text-ink-faint" />
          {link.label}
        </Link>
      );
  }
}

/**
 * NextSteps — the "where to go next" list: every LearningLink rendered
 * as its kind-aware affordance, announced as one labelled group. An
 * empty/absent list renders nothing (honest absence — no filler).
 */
export function NextSteps({
  links,
  label = "Where to go next",
}: {
  links?: LearningLink[];
  label?: string;
}) {
  if (!links || links.length === 0) {
    return null;
  }
  return (
    <ul
      data-testid={NEXT_STEPS_TEST_ID}
      aria-label={label}
      className="flex flex-col gap-1"
    >
      {links.map((link) => (
        <li key={`${link.kind}:${link.id}`} className="flex items-center">
          <NextStep link={link} />
        </li>
      ))}
    </ul>
  );
}
