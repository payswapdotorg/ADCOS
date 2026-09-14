/**
 * Requests feature — the in-memory request log (Worker 1's store,
 * enriched by Worker 3's recorder) and the recorder itself. The request
 * inspector (/developers/requests) renders this data; the API explorer
 * correlates response headers through it.
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
export {
  ensureRequestRecorder,
  matchRequestCompletion,
  __resetRecorderForTests,
  MAX_RESPONSE_BODY_CHARS,
} from "./recorder";
export type { RequestCompletion } from "./recorder";
