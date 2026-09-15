"use client";

/**
 * BuildContextBlock — the "Build context" education block (the Build with
 * ADCOS & LLM Integration program, Task 5 of the frozen plan —
 * docs/superpowers/plans/2026-09-15-adcos-build-with-adcos-llm-
 * integration.md; design §5/§12/§14). Composed INTO the
 * collapsed-by-default "About this operation" disclosure
 * (operation-education.tsx mounts it after the existing education
 * content), it teaches WHERE an operation fits an INTEGRATION:
 *
 * 1. "Used by integration patterns" — `patternsUsingOperation` from the
 *    W1 integration registry (`@/lib/integration` — the SAME registry the
 *    /build experience renders); each pattern title links to
 *    `/build?pattern={pattern.id}` (the W2 deep-link contract). No
 *    pattern → the honest empty state; an empty registry → the honest
 *    unknown state; pattern membership is never invented.
 * 2. "Lifecycle position" — the operation-learning registry's own
 *    lifecyclePosition (found by operation id); no record → the honest
 *    no-record note, never a guess.
 * 3. "Machine-readable context" — the PUBLIC LLM asset pointer: the
 *    console's SHARED CopyButton (the exact mechanism the request
 *    inspector's curl copy uses — ONE clipboard implementation, with its
 *    built-in graceful degradation when navigator.clipboard is absent in
 *    non-secure contexts) copying the absolute-path URL
 *    `/adcos-integration-context.json`, plus a "View machine-readable
 *    context" link to the same public asset. A public-asset pointer
 *    ONLY: no credentials, no tokens, no fabricated state, no telemetry.
 *
 * Non-negotiables enforced structurally:
 * - NO second endpoint catalog: the block renders NOTHING for an
 *   operation id the coverage registry (`@/lib/api/coverage`) does not
 *   carry — that registry is the only operation authority this feature
 *   consults.
 * - LINKS ONLY: no execution control is rendered here, and no unsupported
 *   operation can become executable through this block.
 *
 * Accessibility: the copy affordance's success feedback (the shared
 * CopyButton's "Copy LLM context link" → "Copied" label swap) sits inside
 * a polite aria-live region — the same announcement pattern the
 * Quickstart step body uses.
 */

import Link from "next/link";
import { CopyButton } from "@/components/ui";
import { coverageByOperation } from "@/lib/api/coverage";
import { getOperationEducation } from "@/lib/education";
import { patternsUsingOperation } from "@/lib/integration";
import { INTEGRATION_PATTERNS } from "@/lib/integration/patterns";

/** Stable test ids for the build-context block and its sections. */
export const BUILD_CONTEXT_TEST_IDS = {
  root: "build-context-block",
  patterns: "build-context-patterns",
  lifecycle: "build-context-lifecycle",
  machineReadable: "build-context-machine-readable",
} as const;

/**
 * The PUBLIC machine-readable integration-context asset — an
 * absolute-path URL, served from web/public. It is the ONLY value the
 * copy affordance ever writes; it is a public pointer, never a secret.
 */
export const INTEGRATION_CONTEXT_HREF = "/adcos-integration-context.json";

/** The inline link style the education panel's own links use. */
const INLINE_LINK_CLASS =
  "text-accent underline decoration-line-strong underline-offset-2 transition-colors hover:decoration-ink";

export function BuildContextBlock({
  operationId,
  omitLifecycle = false,
}: {
  operationId: string;
  /**
   * The docs operation pages render their own "Lifecycle position"
   * DocsSection; mounting there passes true so the position statement is
   * never duplicated on one page. The Explorer mount keeps the full block.
   */
  omitLifecycle?: boolean;
}) {
  // Non-negotiable #1 — no second endpoint catalog: build context exists
  // only for an operation the coverage registry actually carries. An id
  // outside the registry renders the honest absence (the education
  // panel's own convention for unknown ids), never invented content.
  const record = coverageByOperation(operationId);
  if (!record) return null;

  const education = getOperationEducation(operationId);
  const patterns = patternsUsingOperation(operationId);
  const registryEmpty = INTEGRATION_PATTERNS.length === 0;

  return (
    <div
      data-testid={BUILD_CONTEXT_TEST_IDS.root}
      className="flex flex-col gap-4 border-t border-dashed border-line pt-3"
    >
      <div className="flex flex-col gap-1">
        <p className="text-2xs uppercase tracking-wide text-ink-faint">Build context</p>
        <p className="text-sm leading-relaxed text-ink-muted">
          Where this operation fits a real integration — the documented
          patterns that use it, its lifecycle position, and the
          machine-readable context an LLM can consume.
        </p>
      </div>

      {/* 1 — the documented integration patterns using this operation -- */}
      <div
        className="flex flex-col gap-1.5"
        data-testid={BUILD_CONTEXT_TEST_IDS.patterns}
      >
        <p className="text-2xs uppercase tracking-wide text-ink-faint">
          Used by integration patterns
        </p>
        {registryEmpty ? (
          <p className="text-sm leading-relaxed text-ink-muted">
            The integration-pattern registry is empty right now — whether
            this operation belongs to a documented pattern cannot be
            determined from it, and no pattern membership is invented here.
          </p>
        ) : patterns.length === 0 ? (
          <p className="text-sm leading-relaxed text-ink-muted">
            This operation is not part of a documented integration pattern
            yet — see{" "}
            <Link
              href="/build"
              className={`font-mono text-xs ${INLINE_LINK_CLASS}`}
            >
              /build
            </Link>{" "}
            for the current patterns.
          </p>
        ) : (
          <ul className="flex flex-col gap-1">
            {patterns.map((pattern) => (
              <li key={pattern.id}>
                <Link
                  href={`/build?pattern=${pattern.id}`}
                  className={`text-sm ${INLINE_LINK_CLASS}`}
                >
                  {pattern.title}
                </Link>
              </li>
            ))}
          </ul>
        )}
        {patterns.length > 0 ? (
          <p className="text-2xs text-ink-faint">
            The documented patterns whose operation sequences include{" "}
            <span className="font-mono">{operationId}</span> — each opens the
            Build experience with that pattern selected. Registry data
            only; the patterns, not this page, define membership.
          </p>
        ) : null}
      </div>

      {/* 2 — the lifecycle position (the registry's own statement) ------ */}
      {omitLifecycle ? null : (
      <div
        className="flex flex-col gap-1"
        data-testid={BUILD_CONTEXT_TEST_IDS.lifecycle}
      >
        <p className="text-2xs uppercase tracking-wide text-ink-faint">
          Lifecycle position
        </p>
        {education ? (
          <p className="text-sm leading-relaxed text-ink-muted">
            {education.lifecyclePosition} (the operation-learning
            registry&rsquo;s own position statement).
          </p>
        ) : (
          <p className="text-sm leading-relaxed text-ink-muted">
            No operation-education record exists for this operation — its
            lifecycle position is not stated by any registry, and none is
            guessed here.
          </p>
        )}
      </div>
      )}

      {/* 3 — the public machine-readable context pointer (LLM hand-off) - */}
      <div
        className="flex flex-col gap-1.5"
        data-testid={BUILD_CONTEXT_TEST_IDS.machineReadable}
      >
        <p className="text-2xs uppercase tracking-wide text-ink-faint">
          Machine-readable context
        </p>
        <div className="flex flex-wrap items-center gap-2">
          {/* the polite live region announces the shared CopyButton's
              success feedback ("Copy LLM context link" → "Copied") */}
          <span aria-live="polite">
            <CopyButton
              value={INTEGRATION_CONTEXT_HREF}
              ariaLabel="Copy LLM context link"
              label="Copy LLM context link"
            />
          </span>
          <a
            href={INTEGRATION_CONTEXT_HREF}
            className={`text-sm ${INLINE_LINK_CLASS}`}
          >
            View machine-readable context
          </a>
        </div>
        <p className="text-2xs text-ink-faint">
          The canonical machine-readable integration context for LLMs — a
          public asset URL only; it carries no credentials, no tokens and
          no application state.
        </p>
      </div>

      <p className="text-2xs text-ink-faint">
        Composed from the integration-pattern registry, the
        operation-learning registry and the public LLM assets — the same
        authorities the whole console uses. Links only; nothing here
        executes a request.
      </p>
    </div>
  );
}
