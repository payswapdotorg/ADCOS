/**
 * The ONE typed transport over the ADCOS HTTP boundary (plan Task 3 —
 * THE critical interface consumed by Workers 2 and 3).
 *
 * CONTRACT (verified against the live backend — see web/README.md):
 * - Every developer-API request is same-origin relative (`/api/2.0/...`)
 *   with `X-ADCOS-Application` / `X-ADCOS-Credential` from the IN-MEMORY
 *   session (never persisted), `X-ADCOS-API-Version: 2.0`, and — for the
 *   8 durable mutations — an auto-generated `X-ADCOS-Idempotency-Key`
 *   (caller-supplied keys are honored; the same key + body replays the
 *   same response with `X-ADCOS-Idempotent-Replay: true`).
 * - Success is ALWAYS HTTP 200 (even creates) with the envelope
 *   `{api_version, environment, request_id, data, idempotency?, rate_limit?}`.
 * - Non-2xx responses throw `AdcosApiError` carrying the VERBATIM
 *   `error.reason` (developer boundary) or `error.reason_code`
 *   (runtime-level envelope), the canonical reason, the message,
 *   the request id, retryability — plus the failing request
 *   descriptor (credential masked with the `«credential»` sentinel)
 *   for the reproduction UI.
 * - List reads carry `{limit, cursor, filters}` in the request BODY
 *   (the boundary's pagination contract). Browsers forbid bodies on
 *   GET fetches, so the transport attempts the body and falls back to
 *   a bodyless GET when the runtime rejects it; the console filters
 *   client-side by default (see README "List filtering").
 * - The platform surfaces (`/healthz`, `/readyz`, `/demo/*`, the
 *   unversioned `/api/contracts/{id}` read) need NO session.
 */

import { AdcosApiError } from "./errors";
import type {
  ActivationInput,
  ApiEnvelope,
  ApiRequestDescriptor,
  Application,
  ContractAssuranceResource,
  ContractLifecycleResource,
  ContractResource,
  ContractUsageResource,
  DemoDocument,
  IdempotencyInfo,
  IntentCreateInput,
  LeaseGrantInput,
  LeaseRenewalInput,
  LeaseResource,
  LeaseRevocationInput,
  ListQuery,
  ListShape,
  LivenessDocument,
  OfferSelectionInput,
  PlatformContractDocument,
  RateLimitInfo,
  ReadinessDocument,
  TerminationInput,
  WebhookEndpointInput,
  WebhookEndpointResource,
} from "./types";

/** The in-memory session (application id + credential secret). */
export interface AdcosSession {
  applicationId: string;
  credential: string;
}

/** The result of one successful console-issued API request. */
export interface ApiResult<TData> {
  data: TData;
  requestId: string | null;
  replayed: boolean;
  rateLimit?: RateLimitInfo;
  idempotencyKey?: string;
  environment: string | null;
}

const API_PREFIX = "/api/2.0";
const API_VERSION = "2.0";

const APPLICATION_HEADER = "X-ADCOS-Application";
const CREDENTIAL_HEADER = "X-ADCOS-Credential";
const API_VERSION_HEADER = "X-ADCOS-API-Version";
const IDEMPOTENCY_KEY_HEADER = "X-ADCOS-Idempotency-Key";

/** The masked sentinel placed in every recorded request descriptor. */
export const CREDENTIAL_SENTINEL = "«credential»";

/** Generate a fresh idempotency key (crypto.randomUUID with fallback). */
export function newIdempotencyKey(): string {
  const cryptoRef = globalThis.crypto;
  if (cryptoRef && typeof cryptoRef.randomUUID === "function") {
    return cryptoRef.randomUUID();
  }
  return `adcos-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Read the envelope's error fields, handling BOTH envelope shapes. */
function parseErrorBody(status: number, body: unknown): {
  reason: string;
  canonicalReason: string | null;
  message: string;
  requestId: string | null;
  retryable: boolean;
  retryAfter: string | null;
  resourceId: string | null;
  environment: string | null;
} {
  const error = isRecord(body) ? (body.error as unknown) : null;
  if (isRecord(error)) {
    const runtimeReason = typeof error.reason_code === "string" ? error.reason_code : null;
    const boundaryReason = typeof error.reason === "string" ? error.reason : null;
    const reason = boundaryReason ?? runtimeReason ?? "unknown-error";
    return {
      reason,
      canonicalReason:
        typeof error.canonical_reason === "string" && error.canonical_reason
          ? error.canonical_reason
          : null,
      message:
        typeof error.message === "string"
          ? error.message
          : "the backend returned a typed error without a message",
      requestId: typeof error.request_id === "string" ? error.request_id : null,
      retryable: error.retryable === true,
      retryAfter: typeof error.retry_after === "string" ? error.retry_after : null,
      resourceId: typeof error.resource_id === "string" ? error.resource_id : null,
      environment: typeof error.environment === "string" ? error.environment : null,
    };
  }
  return {
    reason: status === 404 ? "not-found" : "invalid-response",
    canonicalReason: null,
    message: `the backend returned HTTP ${status} without a typed error envelope`,
    requestId: null,
    retryable: status >= 500,
    retryAfter: null,
    resourceId: null,
    environment: null,
  };
}

/**
 * The typed client factory. `session` may be `null` — the platform
 * surfaces stay callable; developer-API operations then fail closed
 * with the backend's own verbatim 401 reason.
 */
export function createAdcosClient(session: AdcosSession | null) {
  function descriptor(
    method: "GET" | "POST",
    path: string,
    body: unknown,
    idempotencyKey?: string,
  ): ApiRequestDescriptor {
    const headers: Record<string, string> = {};
    if (method === "POST") headers["Content-Type"] = "application/json";
    if (session) {
      headers[APPLICATION_HEADER] = session.applicationId;
      // NEVER place the secret in a descriptor — masked sentinel only.
      headers[CREDENTIAL_HEADER] = CREDENTIAL_SENTINEL;
    }
    headers[API_VERSION_HEADER] = API_VERSION;
    if (idempotencyKey) headers[IDEMPOTENCY_KEY_HEADER] = idempotencyKey;
    return { method, path, headers, body };
  }

  async function rawRequest(
    method: "GET" | "POST",
    path: string,
    options: {
      body?: unknown;
      idempotencyKey?: string;
      auth?: boolean;
      platform?: boolean;
    } = {},
  ): Promise<Response> {
    const { body, idempotencyKey, auth = true, platform = false } = options;
    const headers: Record<string, string> = { Accept: "application/json" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (auth && session) {
      headers[APPLICATION_HEADER] = session.applicationId;
      headers[CREDENTIAL_HEADER] = session.credential;
    }
    if (!platform) headers[API_VERSION_HEADER] = API_VERSION;
    if (idempotencyKey) headers[IDEMPOTENCY_KEY_HEADER] = idempotencyKey;

    const init: RequestInit = { method, headers };
    if (body !== undefined) init.body = JSON.stringify(body);

    try {
      return await fetch(path, init);
    } catch (transportError) {
      if (
        method === "GET" &&
        body !== undefined &&
        transportError instanceof TypeError
      ) {
        // Browser runtimes forbid bodies on GET fetches; the boundary
        // then serves the default page (limit 20, no filters).
        const { ["Content-Type"]: _dropped, ...bodylessHeaders } = headers;
        return await fetch(path, { method, headers: bodylessHeaders });
      }
      throw transportError;
    }
  }

  async function request<TData>(
    method: "GET" | "POST",
    path: string,
    options: { body?: unknown; idempotencyKey?: string } = {},
  ): Promise<ApiResult<TData>> {
    const { body, idempotencyKey } = options;
    const response = await rawRequest(method, path, { body, idempotencyKey });
    const requestId = response.headers.get("X-ADCOS-Request-Id");
    const replayed = response.headers.get("X-ADCOS-Idempotent-Replay") === "true";

    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      throw new AdcosApiError({
        status: response.status,
        reason: "invalid-response",
        message: `the backend returned a non-JSON response (HTTP ${response.status})`,
        requestId,
        request: descriptor(method, path, body, idempotencyKey),
      });
    }

    if (!response.ok) {
      const parsed = parseErrorBody(response.status, payload);
      throw new AdcosApiError({
        status: response.status,
        reason: parsed.reason,
        canonicalReason: parsed.canonicalReason,
        message: parsed.message,
        requestId: requestId ?? parsed.requestId,
        retryable: parsed.retryable,
        retryAfter: parsed.retryAfter,
        resourceId: parsed.resourceId,
        environment: parsed.environment,
        request: descriptor(method, path, body, idempotencyKey),
      });
    }

    const envelope = payload as ApiEnvelope<TData>;
    return {
      data: envelope.data,
      requestId: requestId ?? envelope.request_id ?? null,
      replayed,
      rateLimit: envelope.rate_limit,
      idempotencyKey: envelope.idempotency?.key ?? idempotencyKey,
      environment: envelope.environment ?? null,
    };
  }

  /** Platform read: no auth headers, no version header, no envelope. */
  async function platformRequest<TData>(
    method: "GET" | "POST",
    path: string,
    body?: unknown,
  ): Promise<{ data: TData; requestId: string | null }> {
    const response = await rawRequest(method, path, { body, auth: false, platform: true });
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      throw new AdcosApiError({
        status: response.status,
        reason: "invalid-response",
        message: `the platform surface returned a non-JSON response (HTTP ${response.status})`,
        request: { method, path, headers: {}, body },
      });
    }
    if (!response.ok) {
      const parsed = parseErrorBody(response.status, payload);
      throw new AdcosApiError({
        status: response.status,
        reason: parsed.reason,
        canonicalReason: parsed.canonicalReason,
        message: parsed.message,
        requestId: parsed.requestId,
        request: { method, path, headers: {}, body },
      });
    }
    const envelope = payload as { request_id?: string };
    return {
      data: payload as TData,
      requestId:
        response.headers.get("X-ADCOS-Request-Id") ?? envelope.request_id ?? null,
    };
  }

  const id = (value: string) => encodeURIComponent(value);

  return {
    /** The authenticated application self view (`GET /api/2.0/application`). */
    async applicationSelf(): Promise<ApiResult<Application>> {
      return request<Application>("GET", `${API_PREFIX}/application`);
    },

    /** Create a connectivity intent (`POST /api/2.0/intents`). */
    async createIntent(
      input: IntentCreateInput,
      options: { idempotencyKey?: string } = {},
    ): Promise<ApiResult<ContractResource>> {
      return request<ContractResource>("POST", `${API_PREFIX}/intents`, {
        body: input,
        idempotencyKey: options.idempotencyKey ?? newIdempotencyKey(),
      });
    },

    /** List intents (`GET /api/2.0/intents` — contracts in INTENT state). */
    async listIntents(query: ListQuery = {}): Promise<ApiResult<ListShape<ContractResource>>> {
      return request("GET", `${API_PREFIX}/intents`, { body: query });
    },

    /** Get one intent (`GET /api/2.0/intents/{id}`). */
    async getIntent(intentId: string): Promise<ApiResult<ContractResource>> {
      return request<ContractResource>("GET", `${API_PREFIX}/intents/${id(intentId)}`);
    },

    /** The intent's canonical lifecycle (`GET /api/2.0/intents/{id}/lifecycle`). */
    async getIntentLifecycle(intentId: string): Promise<ApiResult<ContractLifecycleResource>> {
      return request<ContractLifecycleResource>(
        "GET",
        `${API_PREFIX}/intents/${id(intentId)}/lifecycle`,
      );
    },

    /** Accept offers (`POST /api/2.0/intents/{id}/offers`). */
    async acceptOffers(
      intentId: string,
      input: OfferSelectionInput,
      options: { idempotencyKey?: string } = {},
    ): Promise<ApiResult<ContractResource>> {
      return request<ContractResource>(
        "POST",
        `${API_PREFIX}/intents/${id(intentId)}/offers`,
        { body: input, idempotencyKey: options.idempotencyKey ?? newIdempotencyKey() },
      );
    },

    /** Activate the contract (`POST /api/2.0/intents/{id}/activation`). */
    async activateContract(
      intentId: string,
      input: ActivationInput,
      options: { idempotencyKey?: string } = {},
    ): Promise<ApiResult<ContractResource>> {
      return request<ContractResource>(
        "POST",
        `${API_PREFIX}/intents/${id(intentId)}/activation`,
        { body: input, idempotencyKey: options.idempotencyKey ?? newIdempotencyKey() },
      );
    },

    /** List contracts (`GET /api/2.0/contracts`, filterable by state). */
    async listContracts(query: ListQuery = {}): Promise<ApiResult<ListShape<ContractResource>>> {
      return request("GET", `${API_PREFIX}/contracts`, { body: query });
    },

    /** Get one contract (`GET /api/2.0/contracts/{id}`). */
    async getContract(contractId: string): Promise<ApiResult<ContractResource>> {
      return request<ContractResource>("GET", `${API_PREFIX}/contracts/${id(contractId)}`);
    },

    /** The contract's referenced usage terms (`GET /api/2.0/contracts/{id}/usage`). */
    async getContractUsage(contractId: string): Promise<ApiResult<ContractUsageResource>> {
      return request<ContractUsageResource>(
        "GET",
        `${API_PREFIX}/contracts/${id(contractId)}/usage`,
      );
    },

    /** The contract's referenced assurance obligations (`GET /api/2.0/contracts/{id}/assurance`). */
    async getContractAssurance(contractId: string): Promise<ApiResult<ContractAssuranceResource>> {
      return request<ContractAssuranceResource>(
        "GET",
        `${API_PREFIX}/contracts/${id(contractId)}/assurance`,
      );
    },

    /** Terminate the contract (`POST /api/2.0/contracts/{id}/termination`). */
    async terminateContract(
      contractId: string,
      input: TerminationInput,
      options: { idempotencyKey?: string } = {},
    ): Promise<ApiResult<ContractResource>> {
      return request<ContractResource>(
        "POST",
        `${API_PREFIX}/contracts/${id(contractId)}/termination`,
        { body: input, idempotencyKey: options.idempotencyKey ?? newIdempotencyKey() },
      );
    },

    /** Grant a lease (`POST /api/2.0/contracts/{id}/leases`). */
    async grantLease(
      contractId: string,
      input: LeaseGrantInput,
      options: { idempotencyKey?: string } = {},
    ): Promise<ApiResult<LeaseResource>> {
      return request<LeaseResource>(
        "POST",
        `${API_PREFIX}/contracts/${id(contractId)}/leases`,
        { body: input, idempotencyKey: options.idempotencyKey ?? newIdempotencyKey() },
      );
    },

    /** List leases (`GET /api/2.0/leases`, filterable by state). */
    async listLeases(query: ListQuery = {}): Promise<ApiResult<ListShape<LeaseResource>>> {
      return request("GET", `${API_PREFIX}/leases`, { body: query });
    },

    /** Get one lease (`GET /api/2.0/leases/{id}`). */
    async getLease(leaseId: string): Promise<ApiResult<LeaseResource>> {
      return request<LeaseResource>("GET", `${API_PREFIX}/leases/${id(leaseId)}`);
    },

    /** Renew a lease (`POST /api/2.0/leases/{id}/renewal`). */
    async renewLease(
      leaseId: string,
      input: LeaseRenewalInput,
      options: { idempotencyKey?: string } = {},
    ): Promise<ApiResult<LeaseResource>> {
      return request<LeaseResource>(
        "POST",
        `${API_PREFIX}/leases/${id(leaseId)}/renewal`,
        { body: input, idempotencyKey: options.idempotencyKey ?? newIdempotencyKey() },
      );
    },

    /** Revoke a lease (`POST /api/2.0/leases/{id}/revocation`). */
    async revokeLease(
      leaseId: string,
      input: LeaseRevocationInput,
      options: { idempotencyKey?: string } = {},
    ): Promise<ApiResult<LeaseResource>> {
      return request<LeaseResource>(
        "POST",
        `${API_PREFIX}/leases/${id(leaseId)}/revocation`,
        { body: input, idempotencyKey: options.idempotencyKey ?? newIdempotencyKey() },
      );
    },

    /** List webhook endpoints (`GET /api/2.0/webhook-endpoints`). */
    async listWebhookEndpoints(
      query: ListQuery = {},
    ): Promise<ApiResult<ListShape<WebhookEndpointResource>>> {
      return request("GET", `${API_PREFIX}/webhook-endpoints`, { body: query });
    },

    /** Register a webhook endpoint (`POST /api/2.0/webhook-endpoints`). */
    async registerWebhookEndpoint(
      input: WebhookEndpointInput,
      options: { idempotencyKey?: string } = {},
    ): Promise<ApiResult<WebhookEndpointResource>> {
      return request<WebhookEndpointResource>(
        "POST",
        `${API_PREFIX}/webhook-endpoints`,
        { body: input, idempotencyKey: options.idempotencyKey ?? newIdempotencyKey() },
      );
    },

    /** Get one webhook endpoint (`GET /api/2.0/webhook-endpoints/{id}`). */
    async getWebhookEndpoint(endpointId: string): Promise<ApiResult<WebhookEndpointResource>> {
      return request<WebhookEndpointResource>(
        "GET",
        `${API_PREFIX}/webhook-endpoints/${id(endpointId)}`,
      );
    },

    /** List an endpoint's deliveries (`GET /api/2.0/webhook-endpoints/{id}/deliveries`). */
    async listDeliveries(
      endpointId: string,
      query: ListQuery = {},
    ): Promise<ApiResult<ListShape<Record<string, unknown>>>> {
      return request(
        "GET",
        `${API_PREFIX}/webhook-endpoints/${id(endpointId)}/deliveries`,
        { body: query },
      );
    },

    // -- the platform / health surfaces (NO session required) --------------

    /** Liveness (`GET /healthz`). */
    async healthz(): Promise<{ data: LivenessDocument; requestId: string | null }> {
      return platformRequest<LivenessDocument>("GET", "/healthz");
    },

    /**
     * Readiness (`GET /readyz`). Returns the document for BOTH 200 and
     * 503 (the 503 body is the degraded-state document, not an error).
     */
    async readyz(): Promise<{ data: ReadinessDocument; requestId: string | null }> {
      const response = await rawRequest("GET", "/readyz", { auth: false, platform: true });
      let payload: unknown;
      try {
        payload = await response.json();
      } catch {
        throw new AdcosApiError({
          status: response.status,
          reason: "invalid-response",
          message: "/readyz returned a non-JSON response",
          request: { method: "GET", path: "/readyz", headers: {} },
        });
      }
      if (!isRecord(payload)) {
        throw new AdcosApiError({
          status: response.status,
          reason: "invalid-response",
          message: "/readyz returned an unexpected document",
          request: { method: "GET", path: "/readyz", headers: {} },
        });
      }
      return { data: payload as ReadinessDocument, requestId: response.headers.get("X-ADCOS-Request-Id") };
    },

    /**
     * The deterministic full-chain demonstration. GET (idempotent form)
     * by default; POST with `{instant}` when an explicit instant is given.
     */
    async demoContractFulfillment(
      instant?: string,
    ): Promise<{ data: DemoDocument; requestId: string | null }> {
      if (instant === undefined) {
        return platformRequest<DemoDocument>("GET", "/demo/contract-fulfillment");
      }
      return platformRequest<DemoDocument>("POST", "/demo/contract-fulfillment", { instant });
    },

    /**
     * The UNVERSIONED platform-side contract read (no auth):
     * the raw canonical contract dict (200) or the typed 404 envelope.
     */
    async platformContractRead(
      contractId: string,
    ): Promise<{ data: PlatformContractDocument; requestId: string | null }> {
      return platformRequest<PlatformContractDocument>(
        "GET",
        `/api/contracts/${id(contractId)}`,
      );
    },
  };
}

export type AdcosClient = ReturnType<typeof createAdcosClient>;
