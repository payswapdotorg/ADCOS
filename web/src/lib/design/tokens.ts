/**
 * The ADCOS console design tokens (TypeScript mirror).
 *
 * Single source of truth for anything that must reason about the design
 * system in code rather than CSS: tone names shared by the `Status` /
 * `EvidenceBadge` primitives, the status vocabulary mapping (BACKEND state
 * values, never frontend synonyms), evidence class distinctions, and the
 * tone→CSS variable wiring. The visual values themselves live in
 * `src/app/globals.css`; this module never hardcodes pixel values.
 */

/** Semantic tones available to status-like primitives. */
export type Tone =
  | "positive"
  | "warning"
  | "danger"
  | "info"
  | "neutral"
  | "unknown";

/** The tone a backend state value renders with (backend vocabulary ONLY). */
export const STATUS_TONES: Record<string, Tone> = {
  // lease lifecycle states (contracts domain vocabulary)
  planned: "neutral",
  reserved: "info",
  granted: "positive",
  active: "positive",
  renewed: "positive",
  revoked: "danger",
  measured: "info",
  released: "neutral",

  // contract lifecycle states (the frozen 1.1 reference lifecycle)
  INTENT: "neutral",
  OFFER_SELECTED: "info",
  CONTRACT_ACTIVE: "positive",
  EXECUTION_ACTIVE: "positive",
  DELIVERY: "info",
  ASSURED: "positive",
  DEGRADED: "warning",
  USAGE_FINAL: "neutral",
  SETTLEMENT_PENDING: "neutral",
  SETTLED: "neutral",
  TERMINATED: "danger",
  EXPIRED: "neutral",
  FAILED: "danger",

  // environment/readiness vocabulary surfaced by the shell
  degraded: "warning",
  unknown: "unknown",

  // application status vocabulary
  revoked_application: "danger",
};

/** Resolve the tone for ANY backend state value (unknown → `unknown`). */
export function statusToneFor(value: string | null | undefined): Tone {
  if (!value) return "unknown";
  return STATUS_TONES[value] ?? "unknown";
}

/** Tone → CSS custom property segment (must match globals.css). */
export const TONE_VAR: Record<Tone, string> = {
  positive: "--c-positive",
  warning: "--c-warning",
  danger: "--c-danger",
  info: "--c-info",
  neutral: "--c-ink-muted",
  unknown: "--c-ink-faint",
};

/**
 * The evidence class distinction (spec non-negotiable #7 / charter #5):
 * SOFTWARE evidence must never pass as physical/network evidence.
 * `SOFTWARE` (and the sandbox's `sandbox-simulation` class, which the
 * backend itself labels as software-side simulation) render with a
 * visibly distinct treatment from physical/network classes.
 */
export type EvidenceClassKind = "software" | "physical" | "unknown";

export function evidenceClassKind(evidenceClass: string | null | undefined): EvidenceClassKind {
  if (!evidenceClass) return "unknown";
  const value = String(evidenceClass).toUpperCase();
  if (value === "SOFTWARE" || value === "SANDBOX-SIMULATION") return "software";
  if (value === "UNKNOWN" || value === "" || value === "NOT-CLAIMED") return "unknown";
  // every other backend class (physical observations, network probes,
  // direct measurements) belongs to the physical/network family
  return "physical";
}

/** Design rhythm constants (documentation-grade; CSS is authoritative). */
export const RHYTHM = { tight: 12, base: 16, loose: 24 } as const;

/** The command palette hotkey label (Cmd on macOS, Ctrl elsewhere). */
export const COMMAND_PALETTE_HINT =
  typeof navigator !== "undefined" && /Mac|iPod|iPhone|iPad/.test(navigator.platform)
    ? "⌘K"
    : "Ctrl K";
