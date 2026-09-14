/**
 * The ONE typed transport for the ADCOS backend.
 *
 * Contract (verified against the live sandbox runtime — see the captures
 * this client was derived from):
 * - every request is RELATIVE and same-origin (`/api/2.0/...`, `/healthz`,
 *   `/readyz`, `/demo/...`); in dev the Next rewrite proxies to
 *   ADCOS_BACKEND_URL, in production Vercel routes to the Python function.
 *   NO CORS assumptions, ever.
 * - auth headers on every /api/2.0/* request when a session is held:
 *   X-ADCOS-Application / X-ADCOS-Credential / X-ADCOS-API-Version: 2.0.
 * - mutations (the routes the backend marks idempotency-required) always
 *   send X-ADCOS-Idempotency-Key — auto-generated via crypto.randomUUID()
 *   unless the caller supplies one.
 * - list operations send their pagination as the GET request's JSON BODY
 *   ({limit, cursor, filters}) — the backend's frozen list discipline.
 * - non-2xx responses throw AdcosApiError carrying the VERBATIM
 *   `error.reason` (or the runtime envelope's `reason_code`) plus the
 *   failed request descriptor for reproduction UI.
 * - the session (application id + credential) is held IN MEMORY ONLY —
 *   it is never persisted to any browser storage.
 */

import {
  AdcosApiError,
  parseErrorBody,
  type FailedRequestDescriptor,
} from "./errors";
import type {
  AcceptOffersInput,
  ActivateContractInput,
  AdcosEnvelope,
  Application,
  Contract,
  ContractAssurance,
  ContractLifecycle,
  ContractUsage,
  CreateIntentInput,
  DemoDocument,
  Healthz,
  Lease,
  LeaseWindowInput,
  ListParams,
  ListResponse,
  Readiness,
  RegisterWebhookEndpointInput,
  RevokeLeaseInput,
  TerminateContractInput,
  WebhookDelivery,
  WebhookEndpoint,
} from "./types";

/* ------------------------------------------------------------------ */

/** An authenticated developer session (in-memory only). */
export interface AdcosSession {
  applicationId: string;
  credential: string;
}

/** Options for every mutation call. */
export interface MutationOptions {
  /** Caller-supplied idempotency key (replaying the SAME key + body
   * replays the SAME response byte-identically). */
  idempotencyKey?: string;
}

/** One entry in the (optional) request log the shell may surface. */
export interface RequestLogEntry {
  method: string;
  path: string;
  body?: unknown;
  status: number;
  requestId: string;
  reason?: string;
  at: string;
}

export interface AdcosClientOptions {
  /** Injectable fetch (tests mock here; production uses global fetch). */
  fetchImpl?: typeof fetch;
  /** Observation hook for the in-memory request log (no response bodies). */
  onRequest?: (entry: RequestLogEntry) => void;
}

const API_PREFIX = "/api/2.0";
const APPLICATION_HEADER = "X-ADCOS-Application";
const CREDENTIAL_HEADER = "X-ADCOS-Credential";
const API_VERSION_HEADER = "X-ADCOS-API-Version";
const IDEMPOTENCY_KEY_HEADER = "X-ADCOS-Idempotency-Key";
const API_VERSION = "2.0";

/** Ids the backend mints are matched literally in routes — keep them raw. */
function assertResourceId(id: string, label: string): string {
  if (!/^[A-Za-z0-9:_-]+$/.test(id)) {
    throw new AdcosApiError({
      status: 0,
      reason: "invalid-input",
      message: `${label} must be a backend-minted identifier`,
      request: { method: "GET", path: "" },
    });
  }
  return id;
}

function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  // deterministic fallback (should never fire in Node 20+ / browsers)
  return `adcos-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function listBody(params?: ListParams): Record<string, unknown> | undefined {
  if (!params) return undefined;
  const body: Record<string, unknown> = {};
  if (params.limit !== undefined) body.limit = params.limit;
  if (params.cursor !== undefined && params.cursor !== "") body.cursor = params.cursor;
  if (params.filters !== undefined) body.filters = params.filters;
  return Object.keys(body).length > 0 ? body : undefined;
}

/* ------------------------------------------------------------------ */

export class AdcosClient {
  private readonly session: AdcosSession | null;
  private readonly injectedFetch?: typeof fetch;
  private readonly onRequest?: (entry: RequestLogEntry) => void;

  constructor(session?: AdcosSession | null, options?: AdcosClientOptions) {
    this.session = session ?? null;
    // resolved LAZILY at call time so late-bound global fetch (tests,
    // environments) is honored
    this.injectedFetch = options?.fetchImpl;
    this.onRequest = options?.onRequest;
  }

  private get doFetch(): typeof fetch {
    return this.injectedFetch ?? globalThis.fetch;
  }

  /** The raw transport — one place for headers, decode, and errors.
   * Returns the parsed JSON payload (or throws AdcosApiError). */
  private async send(
    method: string,
    path: string,
    opts: {
      body?: unknown;
      auth?: boolean;
      idempotencyKey?: string;
    } = {},
  ): Promise<unknown> {
    const auth = opts.auth ?? path.startsWith(`${API_PREFIX}/`);
    const headers: Record<string, string> = {};
    let serialized: string | undefined;

    if (opts.body !== undefined) {
      serialized = JSON.stringify(opts.body);
      headers["Content-Type"] = "application/json";
    }
    if (auth && this.session) {
      headers[APPLICATION_HEADER] = this.session.applicationId;
      headers[CREDENTIAL_HEADER] = this.session.credential;
    }
    if (auth) {
      headers[API_VERSION_HEADER] = API_VERSION;
    }
    if (opts.idempotencyKey) {
      headers[IDEMPOTENCY_KEY_HEADER] = opts.idempotencyKey;
    }

    const descriptor: FailedRequestDescriptor = {
      method,
      path,
      body: opts.body,
    };

    let response: Response;
    try {
      response = await this.doFetch(path, {
        method,
        headers,
        body: serialized,
      });
    } catch {
      // network failure — a SYNTHESIZED client-side code (clearly labeled,
      // never presented as a backend reason)
      const error = new AdcosApiError({
        status: 0,
        reason: "backend-unreachable",
        message: "The ADCOS runtime could not be reached",
        request: descriptor,
      });
      this.onRequest?.({
        method,
        path,
        body: opts.body,
        status: 0,
        requestId: "",
        reason: error.reason,
        at: new Date().toISOString(),
      });
      throw error;
    }

    let payload: unknown = null;
    const text = await response.text();
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        payload = null;
      }
    }

    this.onRequest?.({
      method,
      path,
      body: opts.body,
      status: response.status,
      requestId:
        response.headers.get("X-ADCOS-Request-Id") ??
        (typeof payload === "object" && payload !== null
          ? String((payload as Record<string, unknown>).request_id ?? "")
          : ""),
      reason:
        !response.ok && typeof payload === "object" && payload !== null
          ? String(
              (payload as { error?: { reason?: unknown } }).error?.reason ??
                (payload as { error?: { reason_code?: unknown } }).error?.reason_code ??
                "",
            ) || undefined
          : undefined,
      at: new Date().toISOString(),
    });

    if (!response.ok) {
      const parsed = parseErrorBody(payload);
      throw new AdcosApiError({
        status: response.status,
        reason: parsed.reason || "internal-error",
        message: parsed.message || `HTTP ${response.status}`,
        canonicalReason: parsed.canonical_reason,
        requestId: parsed.request_id,
        retryable: parsed.retryable,
        retryAfter: parsed.retry_after,
        resourceId: parsed.resource_id,
        environment: parsed.environment,
        request: descriptor,
      });
    }

    return payload;
  }

  /** Enveloped request (the /api/2.0 success discipline). */
  private async request<T>(
    method: string,
    path: string,
    opts: {
      body?: unknown;
      auth?: boolean;
      idempotencyKey?: string;
    } = {},
  ): Promise<AdcosEnvelope<T>> {
    const descriptor: FailedRequestDescriptor = { method, path, body: opts.body };
    const payload = await this.send(method, path, opts);
    if (
      typeof payload !== "object" ||
      payload === null ||
      !("data" in (payload as Record<string, unknown>))
    ) {
      throw new AdcosApiError({
        status: 200,
        reason: "internal-error",
        message: "The response did not carry the canonical envelope",
        request: descriptor,
      });
    }
    return payload as AdcosEnvelope<T>;
  }

  /** Raw request (platform surfaces outside the envelope discipline). */
  private async requestRaw<T>(
    method: string,
    path: string,
    opts: {
      body?: unknown;
      auth?: boolean;
      idempotencyKey?: string;
    } = {},
  ): Promise<T> {
    return (await this.send(method, path, opts)) as T;
  }

  /* ---------------- developer API (the 21 operations) --------------- */

  /** GET /api/2.0/application */
  applicationSelf(): Promise<AdcosEnvelope<Application>> {
    return this.request<Application>("GET", `${API_PREFIX}/application`);
  }

  /** POST /api/2.0/intents */
  createIntent(
    input: CreateIntentInput,
    opts?: MutationOptions,
  ): Promise<AdcosEnvelope<Contract>> {
    return this.request<Contract>("POST", `${API_PREFIX}/intents`, {
      body: input,
      idempotencyKey: opts?.idempotencyKey ?? newIdempotencyKey(),
    });
  }

  /** GET /api/2.0/intents */
  listIntents(params?: ListParams): Promise<AdcosEnvelope<ListResponse<Contract>>> {
    return this.request<ListResponse<Contract>>("GET", `${API_PREFIX}/intents`, {
      body: listBody(params),
    });
  }

  /** GET /api/2.0/intents/{id} */
  getIntent(intentId: string): Promise<AdcosEnvelope<Contract>> {
    return this.request<Contract>(
      "GET",
      `${API_PREFIX}/intents/${assertResourceId(intentId, "intent id")}`,
    );
  }

  /** GET /api/2.0/intents/{id}/lifecycle */
  getIntentLifecycle(intentId: string): Promise<AdcosEnvelope<ContractLifecycle>> {
    return this.request<ContractLifecycle>(
      "GET",
      `${API_PREFIX}/intents/${assertResourceId(intentId, "intent id")}/lifecycle`,
    );
  }

  /** POST /api/2.0/intents/{id}/offers */
  acceptOffers(
    intentId: string,
    input: AcceptOffersInput,
    opts?: MutationOptions,
  ): Promise<AdcosEnvelope<Contract>> {
    return this.request<Contract>(
      "POST",
      `${API_PREFIX}/intents/${assertResourceId(intentId, "intent id")}/offers`,
      { body: input, idempotencyKey: opts?.idempotencyKey ?? newIdempotencyKey() },
    );
  }

  /** POST /api/2.0/intents/{id}/activation */
  activateContract(
    intentId: string,
    input: ActivateContractInput,
    opts?: MutationOptions,
  ): Promise<AdcosEnvelope<Contract>> {
    return this.request<Contract>(
      "POST",
      `${API_PREFIX}/intents/${assertResourceId(intentId, "intent id")}/activation`,
      { body: input, idempotencyKey: opts?.idempotencyKey ?? newIdempotencyKey() },
    );
  }

  /** GET /api/2.0/contracts */
  listContracts(params?: ListParams): Promise<AdcosEnvelope<ListResponse<Contract>>> {
    return this.request<ListResponse<Contract>>("GET", `${API_PREFIX}/contracts`, {
      body: listBody(params),
    });
  }

  /** GET /api/2.0/contracts/{id} */
  getContract(contractId: string): Promise<AdcosEnvelope<Contract>> {
    return this.request<Contract>(
      "GET",
      `${API_PREFIX}/contracts/${assertResourceId(contractId, "contract id")}`,
    );
  }

  /** GET /api/2.0/contracts/{id}/usage */
  getContractUsage(contractId: string): Promise<AdcosEnvelope<ContractUsage>> {
    return this.request<ContractUsage>(
      "GET",
      `${API_PREFIX}/contracts/${assertResourceId(contractId, "contract id")}/usage`,
    );
  }

  /** GET /api/2.0/contracts/{id}/assurance */
  getContractAssurance(contractId: string): Promise<AdcosEnvelope<ContractAssurance>> {
    return this.request<ContractAssurance>(
      "GET",
      `${API_PREFIX}/contracts/${assertResourceId(contractId, "contract id")}/assurance`,
    );
  }

  /** POST /api/2.0/contracts/{id}/termination */
  terminateContract(
    contractId: string,
    input: TerminateContractInput,
    opts?: MutationOptions,
  ): Promise<AdcosEnvelope<Contract>> {
    return this.request<Contract>(
      "POST",
      `${API_PREFIX}/contracts/${assertResourceId(contractId, "contract id")}/termination`,
      { body: input, idempotencyKey: opts?.idempotencyKey ?? newIdempotencyKey() },
    );
  }

  /** POST /api/2.0/contracts/{id}/leases */
  grantLease(
    contractId: string,
    input: LeaseWindowInput,
    opts?: MutationOptions,
  ): Promise<AdcosEnvelope<Lease>> {
    return this.request<Lease>(
      "POST",
      `${API_PREFIX}/contracts/${assertResourceId(contractId, "contract id")}/leases`,
      { body: input, idempotencyKey: opts?.idempotencyKey ?? newIdempotencyKey() },
    );
  }

  /** GET /api/2.0/leases */
  listLeases(params?: ListParams): Promise<AdcosEnvelope<ListResponse<Lease>>> {
    return this.request<ListResponse<Lease>>("GET", `${API_PREFIX}/leases`, {
      body: listBody(params),
    });
  }

  /** GET /api/2.0/leases/{id} */
  getLease(leaseId: string): Promise<AdcosEnvelope<Lease>> {
    return this.request<Lease>(
      "GET",
      `${API_PREFIX}/leases/${assertResourceId(leaseId, "lease id")}`,
    );
  }

  /** POST /api/2.0/leases/{id}/renewal */
  renewLease(
    leaseId: string,
    input: LeaseWindowInput,
    opts?: MutationOptions,
  ): Promise<AdcosEnvelope<Lease>> {
    return this.request<Lease>(
      "POST",
      `${API_PREFIX}/leases/${assertResourceId(leaseId, "lease id")}/renewal`,
      { body: input, idempotencyKey: opts?.idempotencyKey ?? newIdempotencyKey() },
    );
  }

  /** POST /api/2.0/leases/{id}/revocation */
  revokeLease(
    leaseId: string,
    input: RevokeLeaseInput,
    opts?: MutationOptions,
  ): Promise<AdcosEnvelope<Lease>> {
    return this.request<Lease>(
      "POST",
      `${API_PREFIX}/leases/${assertResourceId(leaseId, "lease id")}/revocation`,
      { body: input, idempotencyKey: opts?.idempotencyKey ?? newIdempotencyKey() },
    );
  }

  /** GET /api/2.0/webhook-endpoints */
  listWebhookEndpoints(
    params?: ListParams,
  ): Promise<AdcosEnvelope<ListResponse<WebhookEndpoint>>> {
    return this.request<ListResponse<WebhookEndpoint>>(
      "GET",
      `${API_PREFIX}/webhook-endpoints`,
      { body: listBody(params) },
    );
  }

  /** POST /api/2.0/webhook-endpoints */
  registerWebhookEndpoint(
    input: RegisterWebhookEndpointInput,
    opts?: MutationOptions,
  ): Promise<AdcosEnvelope<WebhookEndpoint>> {
    return this.request<WebhookEndpoint>("POST", `${API_PREFIX}/webhook-endpoints`, {
      body: input,
      idempotencyKey: opts?.idempotencyKey ?? newIdempotencyKey(),
    });
  }

  /** GET /api/2.0/webhook-endpoints/{id} */
  getWebhookEndpoint(endpointId: string): Promise<AdcosEnvelope<WebhookEndpoint>> {
    return this.request<WebhookEndpoint>(
      "GET",
      `${API_PREFIX}/webhook-endpoints/${assertResourceId(endpointId, "endpoint id")}`,
    );
  }

  /** GET /api/2.0/webhook-endpoints/{id}/deliveries */
  listDeliveries(
    endpointId: string,
    params?: ListParams,
  ): Promise<AdcosEnvelope<ListResponse<WebhookDelivery>>> {
    return this.request<ListResponse<WebhookDelivery>>(
      "GET",
      `${API_PREFIX}/webhook-endpoints/${assertResourceId(endpointId, "endpoint id")}/deliveries`,
      { body: listBody(params) },
    );
  }

  /* ---------------- platform surfaces (no envelope discipline) ------ */

  /** GET /healthz — liveness (always 200). */
  healthz(): Promise<Healthz> {
    return this.requestRaw<Healthz>("GET", "/healthz", { auth: false });
  }

  /** GET /readyz — readiness (200 ready / 503 degraded with detail). */
  readyz(): Promise<Readiness> {
    return this.requestRaw<Readiness>("GET", "/readyz", { auth: false });
  }

  /**
   * GET|POST /demo/contract-fulfillment — the deterministic full-chain
   * demo document. GET (byte-identical default) when no instant is given;
   * POST {"instant"} for a specific RFC 3339 instant.
   */
  demoContractFulfillment(instant?: string): Promise<DemoDocument> {
    if (instant === undefined) {
      return this.requestRaw<DemoDocument>("GET", "/demo/contract-fulfillment", {
        auth: false,
      });
    }
    return this.requestRaw<DemoDocument>("POST", "/demo/contract-fulfillment", {
      body: { instant },
      auth: false,
    });
  }

  /**
   * GET /api/contracts/{id} — the UNVERSIONED platform-side read (no
   * auth): the raw canonical contract dict (200) or the typed 404 envelope.
   */
  platformContractRead(contractId: string): Promise<unknown> {
    return this.requestRaw<unknown>(
      "GET",
      `/api/contracts/${assertResourceId(contractId, "contract id")}`,
      { auth: false },
    );
  }
}

/** Factory form (session-first construction). */
export function createAdcosClient(
  session?: AdcosSession | null,
  options?: AdcosClientOptions,
): AdcosClient {
  return new AdcosClient(session, options);
}
