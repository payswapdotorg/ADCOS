/**
 * API Explorer feature (Worker 3 — plan Task 9).
 *
 * BUILT FROM the coverage registry (`@/lib/api/coverage`): supported
 * endpoints only — an unsupported operation never appears callable.
 * Each explorer entry shows method, path, headers, body, response, status,
 * canonical reason code and the curl reproduction (via the
 * `ApiRequestPanel` primitive).
 */

export { COVERAGE, coverageByOperation, isCoverageOperation } from "@/lib/api/coverage";

export const API_EXPLORER_FEATURE = {
  area: "api-explorer",
  route: "/developers",
  owner: "worker-3",
} as const;
