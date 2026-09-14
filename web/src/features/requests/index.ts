/**
 * Requests feature — the in-memory request log (Worker 3 renders it in
 * the request inspector / API explorer; Worker 1 owns the store).
 */
export {
  recordRequest,
  getRequests,
  clearRequests,
  subscribeRequests,
  useRequestLog,
  isFailedRequest,
  requestLabel,
  __resetRequestLogForTests,
} from "./request-log";
export type { LoggedRequest } from "./request-log";
