/**
 * DocsShared — the local helpers every docs surface composes: the docs IA
 * map, the LearningLink → href resolution, the console-route template
 * resolution, the section/frame chrome and the term filter.
 *
 * The Console V2 documentation system — the DEC-0128 program, Task 3 of
 * the frozen plan (docs/superpowers/plans/2026-09-14-adcos-console-v2-
 * learning-experience.md). This module is a VIEW over the Task-1
 * education registry (`@/lib/education`) and the accepted coverage
 * registry (`@/lib/api/coverage`) — never a second authority; the docs
 * are user-facing documentation, distinct from the internal
 * architecture/evidence records (design §9/§19). Pure render + pure
 * functions only: works from both server and client components.
 */

import Link from "next/link";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import type { LearningLink } from "@/lib/education";
import { ExternalLinkIcon } from "@/components/ui";
import { DocsContextSlot } from "./docs-context";

/* ------------------------------------------------------------------ *
 * The docs IA (design §9) — the sections the docs home lists and every
 * breadcrumb walks. Route hrefs are THIS feature's own route list.
 * ------------------------------------------------------------------ */

export interface DocsSectionMeta {
  id: string;
  label: string;
  href: string;
  description: string;
}

export const DOCS_SECTIONS: DocsSectionMeta[] = [
  {
    id: "start",
    label: "Start here",
    href: "/docs/start",
    description:
      "What ADCOS is, how it works, and your first connectivity contract.",
  },
  {
    id: "concepts",
    label: "Concepts",
    href: "/docs/concepts",
    description:
      "The first-class concepts — what each one is, why it matters, and where it appears in the API.",
  },
  {
    id: "guides",
    label: "Guides",
    href: "/docs/guides",
    description:
      "Goal-oriented playbooks composed from real console operations, routes and docs.",
  },
  {
    id: "api",
    label: "API",
    href: "/docs/api",
    description:
      "Every operation of the accepted boundary, grouped by lifecycle area, with its education.",
  },
  {
    id: "sdk",
    label: "SDKs",
    href: "/docs/sdk",
    description: "The honest state of SDKs — and the API-first surface today.",
  },
  {
    id: "errors",
    label: "Errors",
    href: "/docs/errors",
    description:
      "The canonical reason codes, verbatim, with human guidance that explains but never replaces them.",
  },
  {
    id: "troubleshooting",
    label: "Troubleshooting",
    href: "/docs/troubleshooting",
    description:
      "Diagnosis paths for connect failures, unknown routes, degraded coordination and replanning.",
  },
  {
    id: "reference",
    label: "Reference",
    href: "/docs/reference",
    description:
      "The frozen vocabularies: lifecycle states, evidence classes, capability grants and objects.",
  },
];

/** Look up one docs section by id. */
export function getDocsSection(id: string): DocsSectionMeta | undefined {
  return DOCS_SECTIONS.find((section) => section.id === id);
}

/* ------------------------------------------------------------------ *
 * Link resolution — LearningLink → href
 *
 * The registries' LearningLink `kind` selects the vocabulary: concept /
 * operation / guide ids belong to the Task-1 registry, routes belong to
 * the frozen console route list, docs ids belong to the frozen docs IA
 * slug vocabulary (pinned by the education-registry test). This map
 * resolves those ids onto THIS feature's real routes.
 * ------------------------------------------------------------------ */

/**
 * The frozen docs IA slugs → the docs routes this feature owns. The
 * `quickstart` slug is the Quickstart journey route owned by the V2
 * first-run wave (plan Task 5) — linked here by href only.
 */
const DOCS_LINK_HREFS: Record<string, string> = {
  "what-is-adcos": "/docs/start/what-is-adcos",
  quickstart: "/quickstart",
  "how-adcos-works": "/docs/start/how-it-works",
  "first-connectivity-contract": "/docs/start/first-contract",
  concepts: "/docs/concepts",
  guides: "/docs/guides",
  api: "/docs/api",
  "api/authentication": "/docs/api#group-application",
  "api/contracts": "/docs/api#group-contracts",
  "api/offers": "/docs/api#group-offers",
  "api/plans": "/docs/api#group-contracts",
  "api/fulfillment": "/docs/api#group-platform",
  "api/evidence": "/docs/api#group-platform",
  "api/assurance": "/docs/api#group-contracts",
  "api/webhooks": "/docs/api#group-webhooks",
  sdks: "/docs/sdk",
  errors: "/docs/errors",
  troubleshooting: "/docs/troubleshooting",
  reference: "/docs/reference",
};

/**
 * The frozen console route list (the vocabulary the education registry's
 * route links resolve against — see tests/education-registry.test.ts).
 * Templates carry a `[id]`-shaped segment; a docs link to a template
 * route lands on the real surface that owns the object instead.
 */
const CONSOLE_ROUTE_SET = new Set([
  "/",
  "/connectivity",
  "/connectivity/contracts/[id]",
  "/networks",
  "/fulfillment",
  "/evidence",
  "/assurance",
  "/developers",
  "/developers/explorer",
  "/developers/requests",
  "/settings",
  "/settings/errors",
]);

/**
 * Resolve a console route (possibly a `[id]` template) to the real
 * route a docs link can target: walk up the path until a segment list
 * matches a known console route (`/connectivity/contracts/[id]` →
 * `/connectivity` — the workspace where the object is picked).
 */
export function consoleRouteHref(route: string): string {
  if (!route.includes("[")) return route;
  const segments = route.split("/").filter(Boolean);
  while (segments.length > 0) {
    const candidate = `/${segments.join("/")}`;
    if (CONSOLE_ROUTE_SET.has(candidate)) return candidate;
    segments.pop();
  }
  return "/";
}

/** Resolve any LearningLink onto a real href (docs-internal or console). */
export function docsLinkHref(link: LearningLink): string {
  switch (link.kind) {
    case "concept":
      return `/docs/concepts/${link.id}`;
    case "operation":
      return `/docs/api/${link.id}`;
    case "guide":
      return `/docs/guides/${link.id}`;
    case "route":
      return consoleRouteHref(link.id);
    case "docs":
      return DOCS_LINK_HREFS[link.id] ?? "/docs";
  }
}

/** True when the link leaves documentation for a console surface. */
export function linkLeavesDocs(link: LearningLink): boolean {
  return link.kind === "route";
}

/* ------------------------------------------------------------------ *
 * Render helpers
 * ------------------------------------------------------------------ */

/**
 * DocsLink — renders one registry LearningLink as a calm link. Console
 * routes carry the external-link glyph so leaving the docs is visible;
 * the label always comes from the registry verbatim.
 */
export function DocsLink({
  link,
  className,
  showGlyph = true,
}: {
  link: LearningLink;
  className?: string;
  showGlyph?: boolean;
}) {
  const leaves = linkLeavesDocs(link);
  return (
    <Link
      href={docsLinkHref(link)}
      className={cn(
        "rounded text-accent transition-colors hover:text-accent-strong hover:underline",
        className,
      )}
    >
      {link.label}
      {leaves && showGlyph ? (
        <ExternalLinkIcon size={10} className="ml-1 inline-block align-baseline" />
      ) : null}
    </Link>
  );
}

/**
 * DocsSection — the titled section card the docs surfaces compose
 * (modeled on the V1 object surfaces' section card; local to this
 * feature by the house rule — a shared helper lives in the feature
 * that owns it).
 */
export function DocsSection({
  id,
  title,
  description,
  children,
  className,
}: {
  id?: string;
  title: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <section
      id={id}
      aria-labelledby={id ? `${id}-heading` : undefined}
      className={cn("rounded-md border border-line bg-surface", className)}
    >
      <header className="border-b border-line px-4 py-3">
        <h2 id={id ? `${id}-heading` : undefined} className="text-sm font-semibold text-ink">
          {title}
        </h2>
        {description ? (
          <p className="mt-0.5 text-xs leading-relaxed text-ink-muted">{description}</p>
        ) : null}
      </header>
      <div className="flex flex-col gap-3 px-4 py-4">{children}</div>
    </section>
  );
}

/**
 * DocsPageFrame — the shared page chrome every docs surface renders
 * inside: the contextual return slot (the `?from=` workflow context,
 * design §10), the docs breadcrumb, the editorial heading block and
 * the content column. Docs default to a calm reading width; `wide`
 * widens the column for table-like surfaces (API hub, errors,
 * reference).
 */
export function DocsPageFrame({
  sectionId,
  pageLabel,
  title,
  lede,
  aside,
  wide = false,
  children,
}: {
  /** The docs section this page belongs to (breadcrumb + section link). */
  sectionId?: string;
  /** The page's own breadcrumb label (defaults to the title). */
  pageLabel?: string;
  title: ReactNode;
  lede?: ReactNode;
  aside?: ReactNode;
  wide?: boolean;
  children: ReactNode;
}) {
  const section = sectionId ? getDocsSection(sectionId) : undefined;
  return (
    <div
      className={cn(
        "mx-auto w-full px-gutter py-rhythm",
        wide ? "max-w-5xl" : "max-w-3xl",
      )}
    >
      <DocsContextSlot />
      <nav aria-label="Docs" className="flex flex-wrap items-center gap-1.5 text-xs text-ink-faint">
        <Link href="/docs" className="rounded text-ink-muted hover:text-ink">
          Docs
        </Link>
        {section ? (
          <>
            <span aria-hidden="true">›</span>
            <Link href={section.href} className="rounded text-ink-muted hover:text-ink">
              {section.label}
            </Link>
          </>
        ) : null}
        <span aria-hidden="true">›</span>
        <span aria-current="page" className="text-ink-muted">
          {pageLabel ?? title}
        </span>
      </nav>
      <header className="mt-3 flex flex-col gap-2">
        <h1 className="text-xl font-semibold text-ink">{title}</h1>
        {lede ? <p className="max-w-2xl text-sm leading-relaxed text-ink-muted">{lede}</p> : null}
        {aside ? <div className="text-sm text-ink-muted">{aside}</div> : null}
      </header>
      <div className="mt-6 flex flex-col gap-4">{children}</div>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * The route-local term filter (design §9: no backend search service —
 * indexes filter the registry data in the browser only)
 * ------------------------------------------------------------------ */

/** Case-insensitive containment across the given fields. */
export function matchesDocsTerm(
  term: string,
  fields: (string | null | undefined)[],
): boolean {
  const needle = term.trim().toLowerCase();
  if (needle.length === 0) return true;
  return fields.some((field) => field?.toLowerCase().includes(needle) ?? false);
}

/**
 * MethodChip — the GET/POST chip (the Explorer's own styling, kept
 * local): reads render muted, mutations render with the accent family.
 */
export function MethodChip({ method }: { method: string }) {
  const read = method === "GET";
  return (
    <span
      className={
        read
          ? "inline-flex shrink-0 items-center rounded border border-line-strong px-1.5 py-px font-mono text-2xs uppercase tracking-wide text-ink-muted"
          : "inline-flex shrink-0 items-center rounded border border-accent bg-accent px-1.5 py-px font-mono text-2xs uppercase tracking-wide text-accent-ink"
      }
    >
      {method}
    </span>
  );
}
