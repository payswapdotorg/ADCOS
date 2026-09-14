/**
 * The error-workbench reason-code guidance dictionary.
 *
 * The KNOWN dictionary below is the verified backend reason-code set the
 * console gives specific troubleshooting guidance for. The reason itself
 * is ALWAYS displayed VERBATIM next to the guidance — the guidance never
 * rewrites the code (spec non-negotiable #6), and an unknown code gets
 * the honest generic fallback (never an invented explanation).
 */

/** The KNOWN reason codes (verbatim backend vocabulary). */
export const KNOWN_REASON_CODES: readonly string[] = [
  "authentication-invalid",
  "route-unknown",
  "version-unsupported",
  "invalid-input",
  "invalid-transition",
  "unknown-contract",
  "idempotency-conflict",
];

/** Guidance for one reason code. */
export interface ReasonGuidance {
  /** True when the code is in the KNOWN dictionary. */
  known: boolean;
  title: string;
  nextAction: string;
}

const KNOWN_GUIDANCE: Record<string, { title: string; nextAction: string }> = {
  "authentication-invalid": {
    title: "Authentication failed",
    nextAction:
      "The application ID or credential was rejected. Reconnect with a freshly issued credential (Settings → Session → Connect application).",
  },
  "route-unknown": {
    title: "Unknown API route",
    nextAction:
      "The request targeted a route the runtime does not expose. The console only calls registry-backed routes — re-issue from the surface that made the request after a refresh.",
  },
  "version-unsupported": {
    title: "API version not supported",
    nextAction:
      "The route version and X-ADCOS-API-Version must agree (2.0). The typed client sends 2.0 on every developer-API request automatically.",
  },
  "invalid-input": {
    title: "Invalid input",
    nextAction:
      "The backend rejected a member of the request body — the captured message names the offending member. Fix the input and re-issue.",
  },
  "invalid-transition": {
    title: "Invalid state transition",
    nextAction:
      "The object is not in a state that allows this operation. Refresh the owning surface to see its current state before re-issuing.",
  },
  "unknown-contract": {
    title: "Contract not found",
    nextAction:
      "The contract does not exist or is not visible to this application. Re-check the identifier and re-issue the read.",
  },
  "idempotency-conflict": {
    title: "Idempotency conflict",
    nextAction:
      "This idempotency key was used with a DIFFERENT request body. Use a new key for a new mutation; replaying the same key with the same body returns the original response.",
  },
};

/**
 * The guidance for any captured reason code. Known codes get the
 * dictionary entry; everything else gets the honest generic fallback
 * (the code itself still renders verbatim either way).
 */
export function reasonGuidance(reason: string): ReasonGuidance {
  const known = KNOWN_REASON_CODES.includes(reason);
  if (known) {
    const entry = KNOWN_GUIDANCE[reason];
    return { known: true, title: entry.title, nextAction: entry.nextAction };
  }
  return {
    known: false,
    title: "Reason code not in the known dictionary",
    nextAction:
      "The console has no specific guidance for this code — it is shown VERBATIM as the backend sent it. Reproduce the request below against the API to investigate the backend's own message.",
  };
}

/**
 * The guidance for a captured error's OWN codes: the boundary `reason`
 * first (the primary vocabulary); when that is not in the KNOWN
 * dictionary but the backend adapted a `canonical_reason` that IS, the
 * canonical code selects the guidance. Both codes still render VERBATIM
 * wherever they appear — this lookup only picks the guidance entry and
 * never rewrites a code (the boundary's `resource-unknown` with the
 * canonical `unknown-contract` is the canonical example).
 */
export function reasonGuidanceForCodes(
  reason: string,
  canonicalReason: string | null,
): ReasonGuidance {
  const fromReason = reasonGuidance(reason);
  if (fromReason.known) return fromReason;
  if (canonicalReason && canonicalReason !== reason) {
    const fromCanonical = reasonGuidance(canonicalReason);
    if (fromCanonical.known) return fromCanonical;
  }
  return fromReason;
}

/**
 * The synthesized CLIENT-side codes (never presented as backend reasons).
 * `backend-unreachable` is produced by the typed client when the request
 * never reached the runtime — the workbench labels it as synthesized.
 */
export function isSynthesizedClientCode(reason: string): boolean {
  return reason === "backend-unreachable" || reason === "internal-error";
}
