"use client";

/**
 * IntegrationPatternCard — one pattern card of the /build "Choose your
 * architecture" grid (the frozen Build-with-ADCOS design §6.1).
 *
 * The card carries the integration registry's OWN title and summary
 * (`@/lib/integration` — never a second authority) on a keyboard-
 * selectable button (aria-pressed reflects the selection), plus the
 * primary CTA **Design this integration** (design §6.5): clicking it
 * selects the pattern AND asks the parent to compose the on-screen
 * integration blueprint through the registry's
 * `buildIntegrationBlueprint`. The blueprint itself stays presentation
 * state — this card never claims configuration was deployed.
 *
 * The Build with ADCOS experience — the frozen plan Task 3
 * (docs/superpowers/plans/2026-09-15-adcos-build-with-adcos-llm-
 * integration.md).
 */

import type { IntegrationPattern, IntegrationPatternId } from "@/lib/integration";

/** The primary CTA label (design §6.5 — asserted by the feature tests). */
export const DESIGN_THIS_INTEGRATION_LABEL = "Design this integration";

export function IntegrationPatternCard({
  pattern,
  selected,
  onSelect,
  onDesign,
  testId,
}: {
  pattern: IntegrationPattern;
  /** Is this pattern the current selection? */
  selected: boolean;
  /** Select the pattern (card body activation). */
  onSelect: (patternId: IntegrationPatternId) => void;
  /** Select the pattern AND produce the integration plan (the CTA). */
  onDesign: (patternId: IntegrationPatternId) => void;
  testId?: string;
}) {
  return (
    <article
      data-testid={testId}
      data-pattern={pattern.id}
      data-selected={selected ? "true" : "false"}
      className={`flex flex-col rounded-xl border transition ${
        selected
          ? "border-accent/70 bg-raised shadow-[0_0_0_1px_rgba(45,212,191,0.12)]"
          : "border-line bg-surface hover:bg-raised/60"
      }`}
    >
      <button
        type="button"
        onClick={() => onSelect(pattern.id)}
        aria-pressed={selected}
        className="flex-1 p-5 text-left"
      >
        <span className="text-sm font-semibold text-ink">{pattern.title}</span>
        <span className="mt-2 block text-sm leading-6 text-ink-muted">{pattern.summary}</span>
      </button>
      <div className="border-t border-line px-5 py-3">
        <button
          type="button"
          onClick={() => onDesign(pattern.id)}
          className="rounded-lg bg-accent px-3 py-1.5 text-sm font-semibold text-slate-950 transition hover:opacity-90"
        >
          {DESIGN_THIS_INTEGRATION_LABEL}
        </button>
      </div>
    </article>
  );
}
