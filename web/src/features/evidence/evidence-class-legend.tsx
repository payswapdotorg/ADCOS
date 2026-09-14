"use client";

/**
 * EvidenceClassLegend — the badge vocabulary rendered explicitly, so the
 * SOFTWARE vs physical/network distinction (spec non-negotiable #7) is
 * stated on the evidence surface itself:
 *
 * - SOFTWARE and sandbox-simulation render VERBATIM through EvidenceBadge
 *   (the software family — dashed treatment, terminal glyph);
 * - the physical/network family renders as NOT-ACHIEVABLE-BY-THIS-
 *   DEPLOYMENT: this deployment (the deterministic sandbox composition)
 *   produces software-side evidence only, and NO UI state can ever
 *   transform a SOFTWARE record into a physical PASS.
 *
 * The third row deliberately does NOT pass a fabricated class value
 * through EvidenceBadge — it labels the physical/network FAMILY, never
 * inventing a backend class the runtime never sent.
 */

import { EvidenceBadge, ShieldIcon } from "@/components/ui";

/** Stable test id for the legend. */
export const EVIDENCE_LEGEND_TEST_ID = "evidence-class-legend";

/** The exact phrase the physical/network family renders as. */
export const NOT_ACHIEVABLE_BY_THIS_DEPLOYMENT =
  "NOT-ACHIEVABLE-BY-THIS-DEPLOYMENT";

export function EvidenceClassLegend({ className }: { className?: string }) {
  return (
    <section
      data-testid={EVIDENCE_LEGEND_TEST_ID}
      aria-label="Evidence class vocabulary"
      className={className ?? "rounded-md border border-line bg-surface px-4 py-3"}
    >
      <h2 className="text-sm font-semibold text-ink">Evidence classes</h2>
      <ul className="mt-2 flex flex-col gap-2">
        <li className="flex flex-wrap items-baseline gap-2">
          <EvidenceBadge evidenceClass="SOFTWARE" />
          <span className="text-sm text-ink-muted">
            deterministic software-side evidence — what the demonstration
            document carries (its own value, rendered verbatim)
          </span>
        </li>
        <li className="flex flex-wrap items-baseline gap-2">
          <EvidenceBadge evidenceClass="sandbox-simulation" />
          <span className="text-sm text-ink-muted">
            simulation-class evidence — the label the sandbox composition
            itself puts on lifecycle, usage and assurance reads
          </span>
        </li>
        <li className="flex flex-wrap items-baseline gap-2">
          <span className="inline-flex items-center gap-1 rounded-md border border-solid border-line-strong px-1.5 py-0.5 font-mono text-xs text-ink">
            <ShieldIcon size={12} />
            physical / network
          </span>
          <span className="text-sm text-ink-muted">
            <span className="font-mono text-xs text-ink">
              {NOT_ACHIEVABLE_BY_THIS_DEPLOYMENT}
            </span>{" "}
            — physical/network evidence classes can only come from real
            provider observations or direct measurements; this deployment
            produces none, and SOFTWARE evidence never becomes a physical
            PASS.
          </span>
        </li>
      </ul>
    </section>
  );
}
