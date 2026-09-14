/**
 * Errors feature (Worker 3 — plan Task 10: error workbench).
 *
 * Every failure answers: what happened, why, affected resource, next
 * action, canonical reason code (VERBATIM — never replaced with a generic
 * message), and a reproducible API form. The presentation taxonomy lives
 * in `@/lib/api/errors` (describeError); the `ErrorState` primitive
 * renders it. The workbench itself lives at the FROZEN path
 * /settings/errors (features/errors/link.tsx) and deep-links one captured
 * request via ?request=<sequence>.
 */

export { describeError, isAdcosApiError } from "@/lib/api/errors";
export { AdcosApiError } from "@/lib/api/errors";

export {
  ERROR_WORKBENCH_PATH,
  workbenchHref,
  LinkedErrorState,
  ErrorWorkbenchLink,
} from "./link";
export { ErrorWorkbench, ERROR_WORKBENCH_TEST_IDS } from "./workbench";
export {
  CapturedErrorCard,
  CAPTURED_ERROR_TEST_IDS,
} from "./captured-error-card";
export {
  KNOWN_REASON_CODES,
  reasonGuidance,
  reasonGuidanceForCodes,
  isSynthesizedClientCode,
  type ReasonGuidance,
} from "./reason-guidance";
export {
  parseCapturedError,
  type CapturedErrorDetails,
} from "./captured-response";

export const ERRORS_FEATURE = {
  area: "errors",
  route: "/settings/errors",
  owner: "worker-3",
} as const;
