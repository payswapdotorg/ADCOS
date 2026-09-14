/**
 * API Explorer feature (Worker 3 — plan Task 9; station B completion).
 *
 * BUILT FROM the coverage registry (`@/lib/api/coverage`): supported
 * endpoints only — an unsupported operation never appears callable.
 * Each explorer entry shows method, path, headers, body, response, status,
 * canonical reason code and the curl reproduction (via the
 * `ApiRequestPanel` primitive).
 *
 * - `executor` (frozen): the operation executor + path matcher +
 *   masked-header builder — every execution is a REAL typed request.
 * - `explorer-history`: the replayable in-memory execution history.
 * - `explorer-view`: the /developers/explorer surface composition.
 */

export { COVERAGE, coverageByOperation, isCoverageOperation } from "@/lib/api/coverage";

export {
  executeOperation,
  matchOperationForPath,
  pathParameterNames,
  renderPath,
  maskedRequestHeaders,
  DESTRUCTIVE_OPERATIONS,
  type ExecuteInput,
  type ExecuteOutcome,
  type RequestDescriptor,
} from "./executor";

export {
  appendExplorerExecution,
  getExplorerExecutions,
  subscribeExplorerExecutions,
  useExplorerExecutions,
  __resetExplorerHistoryForTests,
  type ExplorerExecution,
} from "./explorer-history";

export { correlateLoggedRequest } from "./correlate";
export { ApiExplorerView } from "./explorer-view";

export const API_EXPLORER_FEATURE = {
  area: "api-explorer",
  route: "/developers/explorer",
  owner: "worker-3",
} as const;
