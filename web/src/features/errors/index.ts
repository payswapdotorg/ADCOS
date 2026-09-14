/**
 * Errors feature (Worker 3 — plan Task 10: error workbench).
 *
 * Every failure answers: what happened, why, affected resource, next
 * action, canonical reason code (VERBATIM — never replaced with a generic
 * message), and a reproducible API form. The presentation taxonomy lives
 * in `@/lib/api/errors` (describeError); the `ErrorState` primitive
 * renders it.
 */

export { describeError, isAdcosApiError } from "@/lib/api/errors";
export { AdcosApiError } from "@/lib/api/errors";

export const ERRORS_FEATURE = {
  area: "errors",
  route: "/developers",
  owner: "worker-3",
} as const;
