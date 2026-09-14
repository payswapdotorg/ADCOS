/**
 * The request RECORDER — the thin transport wrapper Worker 3 owns in
 * features/requests (work order §3.3: "hook its transport if it exposes
 * an interceptor, otherwise … a thin wrapper you own in features/requests").
 *
 * Worker 1's client exposes an `onRequest` interceptor, but it carries
 * only the base entry (method/path/body/status/requestId/reason) — no
 * duration, no response body, no response headers. The recorder closes
 * that gap WITHOUT touching the client (Worker 1's file surface):
 *
 * - `ensureRequestRecorder()` installs a ONE-TIME wrapper around
 *   `globalThis.fetch` (guarded by a global symbol). Every request the
 *   console makes through ANY AdcosClient (they all resolve fetch
 *   lazily at call time) flows through it.
 * - The wrapper measures duration, clones the response to capture the
 *   body (truncated) and the response headers the console surfaces
 *   (X-ADCOS-*, rate-limit, content-type), and pushes a completion
 *   record into a small pending queue.
 * - `recordRequest` (request-log.ts) merges the oldest matching
 *   completion into each new entry — correlation is deterministic
 *   (method + path + status + serialized body) and never fabricates
 *   data: an entry without a match simply renders without the extra
 *   fields.
 *
 * NO secrets are ever recorded: request headers are NOT captured (the
 * credential header would flow through them). Curl reproductions are
 * built from the entry with the credential masked by the rendering
 * layer.
 *
 * Determinism in tests: installing the wrapper captures the CURRENT
 * `globalThis.fetch` as the delegate, so `vi.stubGlobal("fetch", …)`
 * BEFORE a mount wraps the stub (recording works against it), while a
 * stub installed AFTER replaces the wrapper wholesale (no recording —
 * the test stays in control). `__resetRecorderForTests()` unwinds both.
 */

/** One captured response completion (pending merge into the log). */
export interface RequestCompletion {
  method: string;
  path: string;
  /** The serialized request body exactly as sent (undefined when none). */
  requestBody?: string;
  status: number;
  durationMs: number;
  /** Truncated response body text (never parsed here). */
  responseBody: string;
  /** The surfaced response headers (X-ADCOS-*, rate-limit, content-type). */
  responseHeaders: { name: string; value: string }[];
}

/** Response bodies are truncated hard — the inspector expands honestly. */
export const MAX_RESPONSE_BODY_CHARS = 4000;
/** Pending completions await their base entry; a small ring is plenty. */
const MAX_PENDING = 16;

interface InstalledRecorder {
  pending: RequestCompletion[];
  uninstall: () => void;
}

const RECORDER_KEY = Symbol.for("adcos.console.requestRecorder");

function installed(): InstalledRecorder | undefined {
  return (globalThis as Record<symbol, unknown>)[RECORDER_KEY] as
    | InstalledRecorder
    | undefined;
}

/** The interesting response headers (X-ADCOS-…, rate-limit, content-type). */
function captureHeaders(headers: Headers): { name: string; value: string }[] {
  const captured: { name: string; value: string }[] = [];
  headers.forEach((value, name) => {
    const lower = name.toLowerCase();
    const interesting =
      lower.startsWith("x-adcos-") ||
      lower.startsWith("x-ratelimit") ||
      lower.startsWith("ratelimit-") ||
      lower === "content-type";
    if (interesting) {
      captured.push({ name, value });
    }
  });
  captured.sort((a, b) => a.name.localeCompare(b.name));
  return captured;
}

function truncateBody(text: string): string {
  if (text.length <= MAX_RESPONSE_BODY_CHARS) return text;
  return `${text.slice(0, MAX_RESPONSE_BODY_CHARS)}\n… (truncated — ${text.length} chars total)`;
}

function nowMs(): number {
  if (typeof performance !== "undefined" && typeof performance.now === "function") {
    return performance.now();
  }
  return Date.now();
}

function safeStringify(value: unknown): string | undefined {
  try {
    return JSON.stringify(value) ?? undefined;
  } catch {
    return undefined;
  }
}

/**
 * Install the global fetch wrapper (idempotent — safe under StrictMode
 * double-effects and repeated mounts). The wrapper records completions
 * and delegates to the fetch implementation captured at install time.
 */
export function ensureRequestRecorder(): void {
  if (installed() !== undefined) return;
  if (typeof globalThis.fetch !== "function") return; // nothing to wrap (yet)

  const realFetch: typeof fetch = globalThis.fetch.bind(globalThis);
  const record: InstalledRecorder = {
    pending: [],
    uninstall: () => {
      // restore the pre-wrapper fetch (tests) — best effort, never throws
      try {
        (globalThis as { fetch: typeof fetch }).fetch = realFetch;
      } catch {
        /* non-writable global — leave as-is */
      }
      delete (globalThis as Record<symbol, unknown>)[RECORDER_KEY];
    },
  };

  const wrapper = async function adcosRecordingFetch(
    input: RequestInfo | URL,
    init?: RequestInit,
  ): Promise<Response> {
    const started = nowMs();
    const response = await realFetch(input, init);

    let method = init?.method ?? "GET";
    let path = "";
    if (typeof input === "string") {
      path = input;
    } else if (input instanceof URL) {
      path = input.toString();
    } else if (input instanceof Request) {
      path = input.url;
      if (!init?.method) method = input.method;
    }

    const completion: RequestCompletion = {
      method: String(method).toUpperCase(),
      path,
      requestBody: typeof init?.body === "string" ? init.body : undefined,
      status: response.status,
      durationMs: Math.round((nowMs() - started) * 10) / 10,
      responseBody: "",
      responseHeaders: captureHeaders(response.headers),
    };

    try {
      const cloned = response.clone();
      if (typeof cloned?.text === "function") {
        completion.responseBody = truncateBody(await cloned.text());
      }
    } catch {
      // a body that cannot be cloned/read is simply not recorded —
      // the entry stays honest (no fabricated response text)
    }

    record.pending.push(completion);
    if (record.pending.length > MAX_PENDING) {
      record.pending.splice(0, record.pending.length - MAX_PENDING);
    }
    return response;
  };

  (globalThis as Record<symbol, unknown>)[RECORDER_KEY] = record;
  (globalThis as { fetch: typeof fetch }).fetch = wrapper;
}

/**
 * Take the OLDEST pending completion matching a base log entry
 * (method + path + status + serialized body). Returns null when no
 * completion matches — the caller must treat that as "not captured".
 */
export function matchRequestCompletion(match: {
  method: string;
  path: string;
  body?: unknown;
  status: number;
}): RequestCompletion | null {
  const record = installed();
  if (record === undefined) return null;
  const serialized =
    match.body === undefined
      ? undefined
      : typeof match.body === "string"
        ? match.body
        : safeStringify(match.body);
  for (let index = 0; index < record.pending.length; index += 1) {
    const candidate = record.pending[index];
    if (
      candidate.method === match.method.toUpperCase() &&
      candidate.path === match.path &&
      candidate.status === match.status &&
      (candidate.requestBody ?? undefined) === (serialized ?? undefined)
    ) {
      record.pending.splice(index, 1);
      return candidate;
    }
  }
  return null;
}

/** Test helper — clear pending completions and uninstall the wrapper. */
export function __resetRecorderForTests(): void {
  installed()?.uninstall();
}
