/**
 * The API-learning feature (the DEC-0128 program, Tasks 6-7 of the
 * frozen plan — docs/superpowers/plans/2026-09-14-adcos-console-v2-
 * learning-experience.md).
 *
 * The reusable EDUCATION sections composed AROUND the V1 API Explorer's
 * operations and the V1 error workbench's captured failures:
 * - `operation-education` — the "About this operation" progressive-
 *   disclosure block (purpose / prerequisites / lifecycle position /
 *   typical sequence / fields / curl from registry metadata / related
 *   concepts / related reason codes / next operation);
 * - `reason-guidance` — the canonical reason-code troubleshooting table
 *   (the six-part anatomy: what happened / why / affected resource /
 *   next action / API reproduction / learn more).
 *
 * Both are VIEWS over the W1 registries (`@/lib/education`), the
 * coverage registry (`@/lib/api/coverage`) and the canonical error
 * taxonomy (`@/lib/api/errors`) — never a second authority. They ADD
 * education only: the Explorer's execution semantics and the workbench's
 * V1 anatomy stay regression-protected (§20).
 */

export {
  OperationEducationPanel,
  OPERATION_EDUCATION_TEST_IDS,
} from "./operation-education";
export {
  REASON_TROUBLESHOOTING,
  getReasonTroubleshooting,
  reasonTroubleshootingForCodes,
  reasonLearnMoreHrefs,
  isCanonicalReasonCode,
  canonicalReasonTitle,
  type ReasonTroubleshootingGuidance,
} from "./reason-guidance";

export const API_LEARNING_FEATURE = {
  area: "api-learning",
  owner: "w3-expert-handoff",
  planTasks: "Tasks 6-7 — API education + troubleshooting guidance",
  hardRule:
    "education additions only — the Explorer's execution semantics and the workbench's V1 anatomy stay byte-identical",
} as const;
