/**
 * EvidenceBadge — renders an evidence class with the distinction the
 * spec demands (non-negotiable #7): SOFTWARE evidence can NEVER look
 * like physical/network evidence.
 *
 * - software (SOFTWARE, sandbox-simulation): DASHED amber treatment +
 *   terminal glyph;
 * - physical/network (every other concrete class): SOLID border +
 *   shield glyph;
 * - unknown/unclaimed: muted dashed + "?".
 *
 * The class value is always shown VERBATIM.
 */

import { evidenceClassKind, type EvidenceClassKind } from "@/lib/design/tokens";
import { cn } from "@/lib/utils";
import { ShieldIcon, TerminalIcon } from "./icons";

export const EVIDENCE_BADGE_TEST_IDS = {
  root: "evidence-badge",
} as const;

const KIND_STYLES: Record<EvidenceClassKind, string> = {
  software: "border-dashed border-warning/60 bg-warning/5 text-warning",
  physical: "border-solid border-line-strong text-ink",
  unknown: "border-dashed border-line text-ink-faint",
};

const KIND_TITLES: Record<EvidenceClassKind, string> = {
  software: "Software-side evidence class (simulated) — never treated as physical/network evidence",
  physical: "Physical/network evidence class (observed connectivity or direct measurement)",
  unknown: "Evidence class family not recognized or not claimed",
};

export function EvidenceBadge({
  evidenceClass,
  size = "md",
  showLabel = true,
}: {
  evidenceClass: string | null | undefined;
  size?: "sm" | "md";
  showLabel?: boolean;
}) {
  const kind = evidenceClassKind(evidenceClass);
  const label =
    typeof evidenceClass === "string" && evidenceClass.length > 0
      ? evidenceClass
      : null;

  return (
    <span
      data-testid={EVIDENCE_BADGE_TEST_IDS.root}
      data-kind={kind}
      title={
        label ? `${KIND_TITLES[kind]}: ${label}` : KIND_TITLES[kind]
      }
      className={cn(
        "inline-flex items-center gap-1 rounded-md border font-mono",
        size === "sm" ? "px-1 py-px text-2xs" : "px-1.5 py-0.5 text-xs",
        KIND_STYLES[kind],
      )}
    >
      {kind === "software" ? (
        <TerminalIcon size={size === "sm" ? 10 : 12} />
      ) : null}
      {kind === "physical" ? (
        <ShieldIcon size={size === "sm" ? 10 : 12} />
      ) : null}
      {kind === "unknown" ? (
        <span aria-hidden="true" className="font-bold leading-none">
          ?
        </span>
      ) : null}
      {showLabel && label ? <span>{label}</span> : null}
    </span>
  );
}
