/**
 * The ADCOS console design-token registry (plan Task 2).
 *
 * This module is the programmatic mirror of the CSS custom properties
 * declared in `src/app/globals.css` (Tailwind `@theme inline`). The CSS
 * file is the rendering source of truth; this registry is the contract
 * Workers 2/3 (and JS-driven components) consume so that spacing,
 * typography, z-layers, focus behavior and — critically — the STATUS
 * VOCABULARY (backend state values -> tone) stay frozen in exactly one
 * place.
 *
 * RULE: status values are BACKEND state values, displayed verbatim.
 * The console never renames, capitalizes-away or substitutes frontend
 * synonyms. Unknown values render with the `neutral` tone and their
 * verbatim label.
 */

export const TOKENS = {
  spacing: {
    /** 12/16/24px workbench rhythm (4px base grid). */
    unit: 4,
    xs: 4,
    sm: 8,
    md: 12,
    lg: 16,
    xl: 24,
    xxl: 32,
  },
  radius: {
    sm: 4,
    md: 6,
    lg: 8,
    full: 9999,
  },
  typography: {
    sans: "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
    mono: "ui-monospace, 'SF Mono', SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace",
    scale: {
      "2xs": 11,
      xs: 12,
      sm: 13,
      base: 14,
      md: 16,
      lg: 18,
      xl: 20,
      "2xl": 24,
    },
  },
  focus: {
    width: 2,
    offset: 2,
    /** The CSS variable every visible focus ring uses. */
    colorVar: "--c-focus",
  },
  zIndex: {
    base: 0,
    sticky: 10,
    overlay: 100,
    palette: 110,
  },
} as const;

/** The semantic color roles and the CSS variables backing them. */
export const COLOR_ROLES = [
  { name: "canvas", cssVar: "--c-canvas", utility: "bg-canvas" },
  { name: "surface", cssVar: "--c-surface", utility: "bg-surface" },
  { name: "raised", cssVar: "--c-raised", utility: "bg-raised" },
  { name: "sunken", cssVar: "--c-sunken", utility: "bg-sunken" },
  { name: "line", cssVar: "--c-line", utility: "border-line" },
  { name: "line-strong", cssVar: "--c-line-strong", utility: "border-line-strong" },
  { name: "ink", cssVar: "--c-ink", utility: "text-ink" },
  { name: "ink-secondary", cssVar: "--c-ink-secondary", utility: "text-ink-secondary" },
  { name: "ink-muted", cssVar: "--c-ink-muted", utility: "text-ink-muted" },
  { name: "accent", cssVar: "--c-accent", utility: "text-accent" },
  { name: "accent-strong", cssVar: "--c-accent-strong", utility: "text-accent-strong" },
  { name: "accent-soft", cssVar: "--c-accent-soft", utility: "bg-accent-soft" },
  { name: "focus", cssVar: "--c-focus", utility: "focus-ring" },
  { name: "positive", cssVar: "--c-positive", utility: "text-positive" },
  { name: "positive-soft", cssVar: "--c-positive-soft", utility: "bg-positive-soft" },
  { name: "warning", cssVar: "--c-warning", utility: "text-warning" },
  { name: "warning-soft", cssVar: "--c-warning-soft", utility: "bg-warning-soft" },
  { name: "danger", cssVar: "--c-danger", utility: "text-danger" },
  { name: "danger-soft", cssVar: "--c-danger-soft", utility: "bg-danger-soft" },
  { name: "info", cssVar: "--c-info", utility: "text-info" },
  { name: "info-soft", cssVar: "--c-info-soft", utility: "bg-info-soft" },
] as const;

export type StatusTone = "positive" | "info" | "warning" | "danger" | "neutral";

/** Tailwind utility fragments per tone ( fg / soft background ). */
export const TONE_CLASSES: Record<StatusTone, { text: string; soft: string; dot: string; border: string }> = {
  positive: { text: "text-positive", soft: "bg-positive-soft", dot: "bg-positive", border: "border-positive" },
  info: { text: "text-info", soft: "bg-info-soft", dot: "bg-info", border: "border-info" },
  warning: { text: "text-warning", soft: "bg-warning-soft", dot: "bg-warning", border: "border-warning" },
  danger: { text: "text-danger", soft: "bg-danger-soft", dot: "bg-danger", border: "border-danger" },
  neutral: { text: "text-ink-secondary", soft: "bg-sunken", dot: "bg-ink-muted", border: "border-line-strong" },
};

/**
 * The frozen STATUS VOCABULARY: backend state values -> tone.
 * Keys are matched case-insensitively; the displayed label is always
 * the verbatim backend value.
 *
 * Sources (verified against the live backend):
 * - contract states (contracts/model.py CONTRACT_STATES)
 * - lease states (LEASE_STATES: granted/active/expired/revoked/renewed)
 * - lifecycle execution_status values (_EXECUTION_STATUS_BY_STATE)
 * - readiness/degradation and evidence-class values
 * - the evidence phase vocabulary named in the console charter
 */
export const STATUS_TONES: Record<string, StatusTone> = {
  // lease states
  granted: "positive",
  active: "positive",
  renewed: "positive",
  revoked: "danger",
  expired: "neutral",
  // evidence phases (the plan -> reserve -> activate -> measure -> release chain)
  planned: "info",
  reserved: "info",
  activated: "positive",
  measured: "info",
  released: "positive",
  // contract states
  intent: "info",
  offer_selected: "info",
  contract_active: "positive",
  execution_active: "positive",
  delivery: "info",
  delivering: "info",
  executing: "info",
  permitted: "info",
  assured: "positive",
  delivered_assured: "positive",
  degraded: "warning",
  usage_final: "info",
  usage_accounted: "info",
  settlement_pending: "info",
  settled: "positive",
  terminated: "danger",
  failed: "danger",
  closed: "neutral",
  not_started: "neutral",
  notstarted: "neutral",
  // execution status
  unknown: "neutral",
  // readiness
  ok: "positive",
  ready: "positive",
  unavailable: "danger",
  down: "danger",
  // evidence classes
  software: "info",
  "sandbox-simulation": "warning",
  "production-commercial": "warning",
};

/** Resolve the tone for a backend state value (verbatim, case-insensitive). */
export function statusTone(value: string | null | undefined): StatusTone {
  if (!value) return "neutral";
  const key = String(value).toLowerCase();
  return STATUS_TONES[key] ?? "neutral";
}

/**
 * EVIDENCE CLASS FAMILIES — SOFTWARE evidence must never visually pass
 * as physical/network evidence (spec non-negotiable #7).
 * `software` family: SOFTWARE, sandbox-simulation (never physical).
 * `physical` family: everything else observed from a physical/network
 * measurement authority. The verbatim value is always displayed.
 */
export type EvidenceFamily = "software" | "physical";

export function evidenceFamily(evidenceClass: string | null | undefined): EvidenceFamily {
  const value = String(evidenceClass ?? "").toLowerCase();
  if (value === "software" || value === "sandbox-simulation" || value === "software-validation") {
    return "software";
  }
  return "physical";
}
