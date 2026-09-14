"use client";

/**
 * The playbook link affordances — how one guide step's typed
 * LearningLink becomes a REAL console/docs affordance (the DEC-0128
 * program, Tasks 6-7 of the frozen plan; V2 design §10's
 * open-in-preserved-context pattern and §13's goal-oriented entry
 * points).
 *
 * Kind conventions (W1's NextStep conventions, navigated rather than
 * drawer-opened so the walkthrough moves the learner):
 * - operation → the V1 API Explorer's own ?operation= deep link;
 * - concept   → /docs/concepts/<id>;
 * - guide     → /docs/guides/<id>;
 * - docs      → the docs-IA slug's route (W1's docsLinkHref);
 * - route     → the console route (W1's consoleRouteHref resolves the
 *   registry's [id] templates onto the owning surface).
 *
 * EVERY affordance carries `?from=<current playbook path>` — the docs'
 * contextual return-path convention mirrored: the destination knows
 * where the learner came from, so the workflow context survives the
 * detour (docs pages render their return bar from it; console routes
 * keep the parameter harmlessly). No session state is invented — the
 * href IS the context.
 *
 * The `route` kind renders the explicit "Open in workbench" handoff of
 * plan Task 7: a next/link straight into the expert console surface.
 */

import Link from "next/link";
import type { LearningLink } from "@/lib/education";
import {
  ExternalLinkIcon,
  SearchIcon,
  TerminalIcon,
  EvidenceIcon,
} from "@/components/ui";
import { consoleRouteHref, docsLinkHref } from "@/features/docs/docs-shared";

/** The explicit workbench handoff (route kind) — a real navigation pill. */
const WORKBENCH_CLASSES =
  "inline-flex min-h-11 items-center gap-2 rounded-md border border-line-strong " +
  "bg-raised px-3 text-sm text-ink transition-colors hover:bg-surface";

/** The quiet navigation-row presentation (link kinds). */
const LINK_CLASSES =
  "inline-flex min-h-11 items-center gap-2 rounded-md px-2 text-sm text-ink " +
  "underline decoration-line-strong underline-offset-2 transition-colors hover:decoration-ink";

/**
 * Append the contextual return path to an href. The `from` value is
 * URL-encoded (a path with slashes); the separator respects an existing
 * query string. An empty `from` returns the href untouched.
 */
export function withFrom(href: string, from: string): string {
  if (from.length === 0) return href;
  return `${href}${href.includes("?") ? "&" : "?"}from=${encodeURIComponent(from)}`;
}

/** The playbook page's own path — the `from` value its links carry. */
export function playbookPath(guideId: string): string {
  return `/playbooks/${guideId}`;
}

/**
 * StepLinkAffordance — one guide step's LearningLink rendered as its
 * kind-aware real affordance, carrying the preserved-context `?from=`.
 * The label always comes from the registry link's own label.
 */
export function StepLinkAffordance({ link, from }: { link: LearningLink; from: string }) {
  switch (link.kind) {
    case "route": {
      // the explicit expert handoff: straight into the console surface
      return (
        <Link
          href={withFrom(consoleRouteHref(link.id), from)}
          data-testid="playbook-workbench-link"
          data-route={link.id}
          className={WORKBENCH_CLASSES}
        >
          <ExternalLinkIcon size={14} className="shrink-0 text-ink-faint" />
          <span>
            Open in workbench: {link.label}
          </span>
        </Link>
      );
    }
    case "operation": {
      // the V1 Explorer's own deep-link convention (preselects the
      // operation; the path parameters can be prefilled by the caller)
      return (
        <Link
          href={withFrom(`/developers/explorer?operation=${link.id}`, from)}
          data-testid="playbook-operation-link"
          data-operation={link.id}
          className={LINK_CLASSES}
        >
          <TerminalIcon size={14} className="shrink-0 text-ink-faint" />
          <span>
            API: {link.label}{" "}
            <span className="font-mono text-xs text-ink-faint">({link.id})</span>
          </span>
        </Link>
      );
    }
    case "concept": {
      return (
        <Link
          href={withFrom(docsLinkHref({ kind: "concept", id: link.id, label: link.label }), from)}
          data-testid="playbook-concept-link"
          data-concept={link.id}
          className={LINK_CLASSES}
        >
          <SearchIcon size={14} className="shrink-0 text-ink-faint" />
          <span>Learn: {link.label}</span>
        </Link>
      );
    }
    case "guide": {
      return (
        <Link
          href={withFrom(docsLinkHref({ kind: "guide", id: link.id, label: link.label }), from)}
          data-testid="playbook-guide-link"
          data-guide={link.id}
          className={LINK_CLASSES}
        >
          <EvidenceIcon size={14} className="shrink-0 text-ink-faint" />
          <span>Guide: {link.label}</span>
        </Link>
      );
    }
    case "docs": {
      return (
        <Link
          href={withFrom(docsLinkHref(link), from)}
          data-testid="playbook-docs-link"
          data-docs={link.id}
          className={LINK_CLASSES}
        >
          <ExternalLinkIcon size={14} className="shrink-0 text-ink-faint" />
          <span>Docs: {link.label}</span>
        </Link>
      );
    }
  }
}

/**
 * OperationDeepLink — one related operation as an Explorer deep-link
 * (the backend's own operation id in mono, plus its registry purpose).
 * Used by the playbook page's related-operations group and shareable by
 * other learning surfaces.
 */
export function OperationDeepLink({
  operationId,
  from,
  note,
}: {
  operationId: string;
  from: string;
  note?: string;
}) {
  return (
    <li className="flex flex-col gap-0.5">
      <Link
        href={withFrom(`/developers/explorer?operation=${operationId}`, from)}
        data-testid="playbook-related-operation"
        data-operation={operationId}
        className="w-fit font-mono text-xs text-accent underline decoration-line-strong underline-offset-2 transition-colors hover:decoration-ink"
      >
        {operationId}
      </Link>
      {note ? <span className="text-sm leading-relaxed text-ink-muted">{note}</span> : null}
    </li>
  );
}
