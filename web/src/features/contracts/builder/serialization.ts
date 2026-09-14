/**
 * The builder serialization seam — PURE functions (no React, no client).
 *
 * These are the constraint-preservation invariants the tests assert
 * byte-equality on:
 * - guided fields map 1:1 to canonical members (the builder never invents
 *   a UI-only schema);
 * - hard-constraint params serialize EXACTLY as entered — never a dropped
 *   key, never a coerced type beyond the documented number heuristic
 *   (a value that matches /^-?\d+(\.\d+)?$/ becomes a number, everything
 *   else stays a string);
 * - unknown members edited in advanced mode are PRESERVED in a
 *   side-channel and merged back on submit — the builder never silently
 *   drops canonical material.
 */

import type {
  BeneficiaryScope,
  CreateIntentInput,
  HardConstraint,
  OpaqueReference,
} from "@/lib/api/types";

/* ------------------------------------------------------------------ */
/* The guided editing state                                            */
/* ------------------------------------------------------------------ */

/** A requirement / assurance-obligation draft (typed ref + provenance). */
export interface GuidedRefDraft {
  value: string;
  issuer: string;
  /** Comma-separated decision_refs (edited as raw text). */
  decisionRefs: string;
}

/** One typed-ref draft without provenance (service properties, scope). */
export interface GuidedValueDraft {
  value: string;
}

/** One hard-constraint param row (free-form typed mapping). */
export interface GuidedParamRow {
  key: string;
  value: string;
}

/** One hard-constraint draft. */
export interface GuidedConstraintDraft {
  kind: string;
  /** True when the kind came from the free-text "custom…" option. */
  kindIsCustom: boolean;
  params: GuidedParamRow[];
}

/** The complete guided form state (all values are editable strings). */
export interface GuidedBuilderState {
  requirements: GuidedRefDraft[];
  validityNotBefore: string;
  validityNotAfter: string;
  terminationConditions: string;
  compensationValue: string;
  hardConstraints: GuidedConstraintDraft[];
  beneficiaries: { beneficiary_kind: string; beneficiary_ref: string }[];
  serviceProperties: GuidedValueDraft[];
  usagePricingValue: string;
  assuranceObligations: GuidedRefDraft[];
  executionScope: GuidedValueDraft[];
  recordedAt: string;
}

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

/** Split a comma-separated list into trimmed non-empty strings. */
export function splitCommaList(raw: string): string[] {
  return raw
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
}

const NUMBER_LIKE = /^-?\d+(\.\d+)?$/;

/**
 * The documented number heuristic: numeric-looking values serialize as
 * numbers, everything else stays a string — byte-exactly as entered.
 */
export function parseParamValue(raw: string): number | string {
  return NUMBER_LIKE.test(raw) ? Number(raw) : raw;
}

function refDraftsToRefs(
  drafts: GuidedRefDraft[],
  refKind: string,
): OpaqueReference[] {
  return drafts
    .filter((draft) => draft.value.trim().length > 0)
    .map((draft) => ({
      ref_kind: refKind,
      value: draft.value,
      provenance: {
        issuer: draft.issuer,
        decision_refs: splitCommaList(draft.decisionRefs),
      },
    }));
}

function valueDraftsToRefs(
  drafts: GuidedValueDraft[],
  refKind: string,
): OpaqueReference[] {
  return drafts
    .filter((draft) => draft.value.trim().length > 0)
    .map((draft) => ({ ref_kind: refKind, value: draft.value }));
}

/** A constraint draft participates when it carries ANY entered material. */
function constraintHasMaterial(draft: GuidedConstraintDraft): boolean {
  if (draft.kind.trim().length > 0) return true;
  return draft.params.some((row) => row.key.trim().length > 0);
}

/* ------------------------------------------------------------------ */
/* Defaults (seeded from the canonical demo body)                      */
/* ------------------------------------------------------------------ */

export function defaultGuidedState(): GuidedBuilderState {
  return {
    requirements: [
      {
        value: "demo:intent-requirements:v1",
        issuer: "intent-authority",
        decisionRefs: "demo:intent:v1",
      },
    ],
    validityNotBefore: "2026-09-14T00:00:00Z",
    validityNotAfter: "2026-10-14T00:00:00Z",
    terminationConditions: "principal-requested, validity-expired",
    compensationValue: "demo:compensation:v1",
    hardConstraints: [
      { kind: "latency-bound", kindIsCustom: false, params: [{ key: "ms", value: "100" }] },
      {
        kind: "throughput-floor",
        kindIsCustom: false,
        params: [{ key: "bps", value: "1000" }],
      },
    ],
    beneficiaries: [{ beneficiary_kind: "DEVICE", beneficiary_ref: "demo:device:v1" }],
    serviceProperties: [{ value: "demo:service-property:v1" }],
    usagePricingValue: "demo:usage-pricing:v1",
    assuranceObligations: [
      {
        value: "demo:assurance-obligation:v1",
        issuer: "assurance-authority",
        decisionRefs: "demo:assurance:v1",
      },
    ],
    executionScope: [{ value: "demo:execution-scope:v1" }],
    recordedAt: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
  };
}

/* ------------------------------------------------------------------ */
/* Guided state → canonical intent body                                */
/* ------------------------------------------------------------------ */

export function guidedToIntentBody(state: GuidedBuilderState): CreateIntentInput {
  const body: CreateIntentInput = {
    recorded_at: state.recordedAt,
    requirements: refDraftsToRefs(state.requirements, "intent-requirements"),
    validity: {
      not_before: state.validityNotBefore,
      not_after: state.validityNotAfter,
    },
    termination: {
      conditions: splitCommaList(state.terminationConditions),
      compensation: { ref_kind: "compensation", value: state.compensationValue },
    },
  };

  // Hard constraints: params pass through EXACTLY as entered — the only
  // transformation is the documented number heuristic on VALUES; keys are
  // never dropped, reordered semantically, or renamed.
  const hardConstraints: HardConstraint[] = state.hardConstraints
    .filter(constraintHasMaterial)
    .map((draft) => {
      const params: Record<string, number | string> = {};
      for (const row of draft.params) {
        if (row.key.trim().length === 0) continue; // an unnamed row cannot be a JSON member
        params[row.key] = parseParamValue(row.value);
      }
      return { kind: draft.kind, params };
    });
  if (hardConstraints.length > 0) body.hard_constraints = hardConstraints;

  const beneficiaries: BeneficiaryScope[] = state.beneficiaries.filter(
    (beneficiary) => beneficiary.beneficiary_ref.trim().length > 0,
  );
  if (beneficiaries.length > 0) body.beneficiaries = beneficiaries;

  const serviceProperties = valueDraftsToRefs(state.serviceProperties, "service-property");
  if (serviceProperties.length > 0) body.service_properties = serviceProperties;

  if (state.usagePricingValue.trim().length > 0) {
    body.usage_pricing_terms = {
      ref_kind: "usage-pricing-terms",
      value: state.usagePricingValue,
    };
  }

  const assuranceObligations = refDraftsToRefs(
    state.assuranceObligations,
    "assurance-obligation",
  );
  if (assuranceObligations.length > 0) body.assurance_obligations = assuranceObligations;

  const executionScope = valueDraftsToRefs(state.executionScope, "execution-scope");
  if (executionScope.length > 0) body.execution_scope = executionScope;

  return body;
}

/* ------------------------------------------------------------------ */
/* Unknown-member preservation                                         */
/* ------------------------------------------------------------------ */

/**
 * Merge members the guided form does not represent back onto the
 * canonical body — advanced-mode material rides along untouched.
 */
export function mergePreservedMembers(
  known: CreateIntentInput,
  preserved: Record<string, unknown>,
): CreateIntentInput & Record<string, unknown> {
  return { ...known, ...preserved };
}

/** Guided state (+ preserved members) → the exact submit body. */
export function buildIntentBody(
  state: GuidedBuilderState,
  preserved: Record<string, unknown> = {},
): CreateIntentInput & Record<string, unknown> {
  return mergePreservedMembers(guidedToIntentBody(state), preserved);
}

/** The exact canonical demo body the advanced textarea seeds from. */
export function canonicalIntentBody(): CreateIntentInput {
  return guidedToIntentBody(defaultGuidedState());
}

/* ------------------------------------------------------------------ */
/* Advanced body → guided state                                        */
/* ------------------------------------------------------------------ */

/** The canonical members the guided form represents (everything else is preserved). */
export const GUIDED_MEMBER_NAMES = [
  "recorded_at",
  "requirements",
  "validity",
  "termination",
  "hard_constraints",
  "beneficiaries",
  "service_properties",
  "usage_pricing_terms",
  "assurance_obligations",
  "execution_scope",
] as const;

function blankGuidedState(): GuidedBuilderState {
  return {
    requirements: [],
    validityNotBefore: "",
    validityNotAfter: "",
    terminationConditions: "",
    compensationValue: "",
    hardConstraints: [],
    beneficiaries: [],
    serviceProperties: [],
    usagePricingValue: "",
    assuranceObligations: [],
    executionScope: [],
    recordedAt: "",
  };
}

interface UnknownRefShape {
  ref_kind?: unknown;
  value?: unknown;
  provenance?: unknown;
}

function isRefEntries(value: unknown): value is UnknownRefShape[] {
  return (
    Array.isArray(value) &&
    value.every(
      (entry) =>
        typeof entry === "object" &&
        entry !== null &&
        typeof (entry as UnknownRefShape).value === "string",
    )
  );
}

function refToDraft(entry: UnknownRefShape): GuidedRefDraft {
  const provenance = entry.provenance as
    | { issuer?: unknown; decision_refs?: unknown }
    | undefined;
  return {
    value: typeof entry.value === "string" ? entry.value : "",
    issuer:
      provenance !== null &&
      typeof provenance === "object" &&
      typeof provenance.issuer === "string"
        ? provenance.issuer
        : "",
    decisionRefs:
      provenance !== null &&
      typeof provenance === "object" &&
      Array.isArray(provenance.decision_refs)
        ? provenance.decision_refs
            .filter((item): item is string => typeof item === "string")
            .join(", ")
        : "",
  };
}

function isConstraintEntries(
  value: unknown,
): value is { kind: unknown; params: unknown }[] {
  return (
    Array.isArray(value) &&
    value.every(
      (entry) =>
        typeof entry === "object" &&
        entry !== null &&
        typeof (entry as { kind?: unknown }).kind === "string" &&
        typeof (entry as { params?: unknown }).params === "object" &&
        (entry as { params?: unknown }).params !== null &&
        // every param value must be a number or a string — the two types
        // the guided params editor can represent WITHOUT changing bytes.
        // Anything richer (boolean, nested object, ...) keeps the WHOLE
        // hard_constraints member in `preserved` so it rides along
        // untouched rather than being coerced by a guided roundtrip.
        Object.values((entry as { params: object }).params).every(
          (param) => typeof param === "number" || typeof param === "string",
        ),
    )
  );
}

function constraintToDraft(entry: {
  kind: unknown;
  params: unknown;
}): GuidedConstraintDraft {
  const params = entry.params as Record<string, unknown>;
  const kind = entry.kind as string;
  return {
    kind,
    kindIsCustom: kind !== "latency-bound" && kind !== "throughput-floor",
    params: Object.entries(params).map(([key, value]) => ({
      key,
      value: String(value),
    })),
  };
}

function isBeneficiaryEntries(
  value: unknown,
): value is { beneficiary_kind: unknown; beneficiary_ref: unknown }[] {
  return (
    Array.isArray(value) &&
    value.every(
      (entry) =>
        typeof entry === "object" &&
        entry !== null &&
        typeof (entry as { beneficiary_kind?: unknown }).beneficiary_kind === "string" &&
        typeof (entry as { beneficiary_ref?: unknown }).beneficiary_ref === "string",
    )
  );
}

function isRecordWithStringMembers(
  value: unknown,
  keys: [string, ...string[]],
): value is Record<string, string> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return false;
  }
  const record = value as Record<string, unknown>;
  return keys.every((key) => typeof record[key] === "string");
}

/**
 * Parse an advanced-mode canonical body into the guided state. Members the
 * guided form does not represent — and known members whose shapes the form
 * cannot express — are returned in `preserved` so nothing is ever lost.
 * Returns null when the value is not a JSON object.
 */
export function parseAdvancedToGuided(
  value: unknown,
): { state: GuidedBuilderState; preserved: Record<string, unknown> } | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return null;
  }
  const source = value as Record<string, unknown>;
  const state = blankGuidedState();
  const preserved: Record<string, unknown> = {};

  for (const [member, raw] of Object.entries(source)) {
    switch (member) {
      case "recorded_at":
        if (typeof raw === "string") {
          state.recordedAt = raw;
        } else {
          preserved[member] = raw;
        }
        break;
      case "requirements":
        if (isRefEntries(raw)) {
          state.requirements = raw.map(refToDraft);
        } else {
          preserved[member] = raw;
        }
        break;
      case "validity":
        if (isRecordWithStringMembers(raw, ["not_before", "not_after"])) {
          state.validityNotBefore = raw.not_before;
          state.validityNotAfter = raw.not_after;
        } else {
          preserved[member] = raw;
        }
        break;
      case "termination": {
        if (
          typeof raw === "object" &&
          raw !== null &&
          !Array.isArray(raw) &&
          Array.isArray((raw as { conditions?: unknown }).conditions) &&
          isRecordWithStringMembers((raw as { compensation?: unknown }).compensation, [
            "value",
          ])
        ) {
          const termination = raw as {
            conditions: unknown[];
            compensation: { value: string };
          };
          state.terminationConditions = termination.conditions
            .filter((item): item is string => typeof item === "string")
            .join(", ");
          state.compensationValue = termination.compensation.value;
        } else {
          preserved[member] = raw;
        }
        break;
      }
      case "hard_constraints":
        if (isConstraintEntries(raw)) {
          state.hardConstraints = raw.map(constraintToDraft);
        } else {
          preserved[member] = raw;
        }
        break;
      case "beneficiaries":
        if (isBeneficiaryEntries(raw)) {
          state.beneficiaries = raw.map((entry) => ({
            beneficiary_kind: entry.beneficiary_kind as string,
            beneficiary_ref: entry.beneficiary_ref as string,
          }));
        } else {
          preserved[member] = raw;
        }
        break;
      case "service_properties":
        if (isRefEntries(raw)) {
          state.serviceProperties = raw.map((entry) => ({
            value: typeof entry.value === "string" ? entry.value : "",
          }));
        } else {
          preserved[member] = raw;
        }
        break;
      case "usage_pricing_terms":
        if (isRecordWithStringMembers(raw, ["value"])) {
          state.usagePricingValue = raw.value;
        } else {
          preserved[member] = raw;
        }
        break;
      case "assurance_obligations":
        if (isRefEntries(raw)) {
          state.assuranceObligations = raw.map(refToDraft);
        } else {
          preserved[member] = raw;
        }
        break;
      case "execution_scope":
        if (isRefEntries(raw)) {
          state.executionScope = raw.map((entry) => ({
            value: typeof entry.value === "string" ? entry.value : "",
          }));
        } else {
          preserved[member] = raw;
        }
        break;
      default:
        // a member the guided form does not represent — preserve it
        preserved[member] = raw;
        break;
    }
  }

  return { state, preserved };
}

/* ------------------------------------------------------------------ */
/* Client-side sanity checks (the backend stays the authority)         */
/* ------------------------------------------------------------------ */

/**
 * Convenience-only validation for guided mode. Returns an inline message
 * or null. The backend remains the validation authority — its verbatim
 * reason codes surface on rejection.
 */
export function validateGuidedState(state: GuidedBuilderState): string | null {
  if (state.requirements.every((draft) => draft.value.trim() === "")) {
    return "At least one requirement reference with a value is required (member “requirements”).";
  }
  if (state.validityNotBefore.trim() === "" || state.validityNotAfter.trim() === "") {
    return "Both validity instants are required (members “validity.not_before” / “validity.not_after”).";
  }
  if (!(state.validityNotBefore < state.validityNotAfter)) {
    return "validity.not_after must be later than validity.not_before.";
  }
  return null;
}
