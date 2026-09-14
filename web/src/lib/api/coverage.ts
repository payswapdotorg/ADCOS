/**
 * The backend capability coverage REGISTRY.
 *
 * EXACTLY the 21 developer-API boundary operations (the gateway's frozen
 * ROUTES table, verified against the live runtime) plus the 4 platform
 * routes (healthz, readyz, demo GET/POST, platform contract read).
 * NO invented endpoints — an unsupported operation must never appear
 * callable. This registry drives the API Explorer (Worker 3) and the
 * coverage matrix (spec: "every accepted backend surface → a UI location").
 */

export interface CoverageRecord {
  /** The backend's own operation id (verbatim — never a frontend synonym). */
  operation: string;
  method: "GET" | "POST";
  /** Route template; `{…}` marks a path parameter. */
  path: string;
  /** True when the operation mutates (idempotency key required). */
  mutation: boolean;
  /** Required capability grant ("" = none; platform routes never need one). */
  requiredCapability: string;
  /** True for the unauthenticated platform surfaces. */
  platform: boolean;
  /** The console route where the operation is surfaced. */
  uiLocation: string;
  description: string;
  /** Canonical body shape for mutations (from REAL captured requests). */
  example?: Record<string, unknown>;
}

const INTENT_EXAMPLE: Record<string, unknown> = {
  recorded_at: "2026-09-13T00:00:00Z",
  requirements: [
    {
      ref_kind: "intent-requirements",
      value: "demo:intent-requirements:v1",
      provenance: { issuer: "intent-authority", decision_refs: ["demo:intent:v1"] },
    },
  ],
  hard_constraints: [
    { kind: "latency-bound", params: { ms: 100 } },
    { kind: "throughput-floor", params: { bps: 1000 } },
  ],
  validity: { not_before: "2026-09-13T00:00:00Z", not_after: "2026-10-13T00:00:00Z" },
  termination: {
    conditions: ["principal-requested", "validity-expired"],
    compensation: { ref_kind: "compensation", value: "demo:compensation:v1" },
  },
  beneficiaries: [{ beneficiary_kind: "DEVICE", beneficiary_ref: "demo:device:v1" }],
  service_properties: [{ ref_kind: "service-property", value: "demo:service-property:v1" }],
  usage_pricing_terms: { ref_kind: "usage-pricing-terms", value: "demo:usage-pricing:v1" },
  assurance_obligations: [
    {
      ref_kind: "assurance-obligation",
      value: "demo:assurance-obligation:v1",
      provenance: { issuer: "assurance-authority", decision_refs: ["demo:assurance:v1"] },
    },
  ],
  execution_scope: [{ ref_kind: "execution-scope", value: "demo:execution-scope:v1" }],
};

const OFFER_EXAMPLE: Record<string, unknown> = {
  recorded_at: "2026-09-13T00:10:00Z",
  offers: [
    {
      ref_kind: "offer",
      value: "demo:offer:ran-reference:v1",
      provenance: {
        issuer: "provider:ran-reference",
        decision_refs: ["demo:offer:v1"],
      },
    },
  ],
};

const ACTIVATION_EXAMPLE: Record<string, unknown> = {
  activated_at: "2026-09-13T00:20:00Z",
  signature_refs: [{ ref_kind: "signature", value: "demo:signature:v1" }],
};

const TERMINATION_EXAMPLE: Record<string, unknown> = {
  recorded_at: "2026-09-13T03:00:00Z",
  condition: "principal-requested",
  reason: "operator-requested-termination",
};

const LEASE_WINDOW_EXAMPLE: Record<string, unknown> = {
  granted_at: "2026-09-13T01:00:00Z",
  not_before: "2026-09-13T01:00:00Z",
  not_after: "2026-09-13T02:00:00Z",
};

const REVOCATION_EXAMPLE: Record<string, unknown> = {
  recorded_at: "2026-09-13T02:10:00Z",
  reason: "operator-requested-revocation",
};

const WEBHOOK_EXAMPLE: Record<string, unknown> = {
  url: "https://example.com/hooks/adcos",
  event_types: ["connectivity_intent.created", "webhook_endpoint.registered"],
};

const LIST_NOTE =
  "Pagination rides the GET request's JSON body: {limit (1..100, default 20), cursor, filters}.";

/** The registry — the single coverage authority for the console. */
export const COVERAGE: CoverageRecord[] = [
  /* -------- platform surfaces (4) -------- */
  {
    operation: "healthz",
    method: "GET",
    path: "/healthz",
    mutation: false,
    requiredCapability: "",
    platform: true,
    uiLocation: "/",
    description: "Runtime liveness (always 200). The shell's environment indicator also derives readiness from /readyz.",
  },
  {
    operation: "readyz",
    method: "GET",
    path: "/readyz",
    mutation: false,
    requiredCapability: "",
    platform: true,
    uiLocation: "/",
    description: "Runtime readiness: mode, environment and every consumed backend's state; 200 when all ready, 503 with per-backend detail when not.",
  },
  {
    operation: "demo_contract_fulfillment",
    method: "GET",
    path: "/demo/contract-fulfillment",
    mutation: false,
    requiredCapability: "",
    platform: true,
    uiLocation: "/developers",
    description: "The deterministic full-chain demo document (boundary, contract, plan, execution, evidence). POST with {\"instant\": RFC3339} for a specific instant.",
    example: { instant: "2026-09-13T01:30:00Z" },
  },
  {
    operation: "platform_contract_read",
    method: "GET",
    path: "/api/contracts/{contract_id}",
    mutation: false,
    requiredCapability: "",
    platform: true,
    uiLocation: "/connectivity",
    description: "The UNVERSIONED platform-side contract read (no auth): the raw canonical contract dict, or the typed 404 envelope.",
  },

  /* -------- developer API (21) -------- */
  {
    operation: "application_self",
    method: "GET",
    path: "/api/2.0/application",
    mutation: false,
    requiredCapability: "",
    platform: false,
    uiLocation: "/developers",
    description: "The authenticated application: identity, environment, capabilities, status and validity.",
  },
  {
    operation: "intent_create",
    method: "POST",
    path: "/api/2.0/intents",
    mutation: true,
    requiredCapability: "intents:write",
    platform: false,
    uiLocation: "/connectivity",
    description: "Record a connectivity intent (the contract creation core; the principal is derived from the authenticated application).",
    example: INTENT_EXAMPLE,
  },
  {
    operation: "intents_list",
    method: "GET",
    path: "/api/2.0/intents",
    mutation: false,
    requiredCapability: "intents:read",
    platform: false,
    uiLocation: "/connectivity",
    description: `Contracts still in the INTENT state. ${LIST_NOTE}`,
  },
  {
    operation: "intent_get",
    method: "GET",
    path: "/api/2.0/intents/{intent_id}",
    mutation: false,
    requiredCapability: "intents:read",
    platform: false,
    uiLocation: "/connectivity",
    description: "One intent's canonical contract resource (full canonical material).",
  },
  {
    operation: "intent_lifecycle",
    method: "GET",
    path: "/api/2.0/intents/{intent_id}/lifecycle",
    mutation: false,
    requiredCapability: "intents:read",
    platform: false,
    uiLocation: "/connectivity",
    description: "The honest lifecycle observation: contract state machine, statements, execution status — physical connectivity is never claimed by API success.",
  },
  {
    operation: "offers_accept",
    method: "POST",
    path: "/api/2.0/intents/{intent_id}/offers",
    mutation: true,
    requiredCapability: "intents:write",
    platform: false,
    uiLocation: "/connectivity",
    description: "Accept opaque typed offer references onto the intent (OFFER_SELECTED).",
    example: OFFER_EXAMPLE,
  },
  {
    operation: "contract_activate",
    method: "POST",
    path: "/api/2.0/intents/{intent_id}/activation",
    mutation: true,
    requiredCapability: "intents:write",
    platform: false,
    uiLocation: "/connectivity",
    description: "Activate the contract (CONTRACT_ACTIVE) with the activation instant and signature references.",
    example: ACTIVATION_EXAMPLE,
  },
  {
    operation: "contracts_list",
    method: "GET",
    path: "/api/2.0/contracts",
    mutation: false,
    requiredCapability: "intents:read",
    platform: false,
    uiLocation: "/connectivity",
    description: `All the application's contracts. ${LIST_NOTE} Filters: {state: <lifecycle state>}.`,
  },
  {
    operation: "contract_get",
    method: "GET",
    path: "/api/2.0/contracts/{contract_id}",
    mutation: false,
    requiredCapability: "intents:read",
    platform: false,
    uiLocation: "/connectivity",
    description: "One canonical contract resource with the complete lifecycle material.",
  },
  {
    operation: "contract_usage",
    method: "GET",
    path: "/api/2.0/contracts/{contract_id}/usage",
    mutation: false,
    requiredCapability: "usage:read",
    platform: false,
    uiLocation: "/connectivity",
    description: "The contract's referenced usage/pricing semantics (referenced, never interpreted).",
  },
  {
    operation: "contract_assurance",
    method: "GET",
    path: "/api/2.0/contracts/{contract_id}/assurance",
    mutation: false,
    requiredCapability: "assurance:read",
    platform: false,
    uiLocation: "/assurance",
    description: "The contract's referenced assurance obligations (referenced, never evaluated here).",
  },
  {
    operation: "contract_terminate",
    method: "POST",
    path: "/api/2.0/contracts/{contract_id}/termination",
    mutation: true,
    requiredCapability: "intents:write",
    platform: false,
    uiLocation: "/connectivity",
    description: "Terminate the contract (terminal state) with a condition and reason.",
    example: TERMINATION_EXAMPLE,
  },
  {
    operation: "lease_grant",
    method: "POST",
    path: "/api/2.0/contracts/{contract_id}/leases",
    mutation: true,
    requiredCapability: "leases:write",
    platform: false,
    uiLocation: "/connectivity",
    description: "Grant a lease on the contract for a validity window.",
    example: LEASE_WINDOW_EXAMPLE,
  },
  {
    operation: "leases_list",
    method: "GET",
    path: "/api/2.0/leases",
    mutation: false,
    requiredCapability: "leases:read",
    platform: false,
    uiLocation: "/connectivity",
    description: `The application's leases. ${LIST_NOTE} Filters: {state: <lease state>}.`,
  },
  {
    operation: "lease_get",
    method: "GET",
    path: "/api/2.0/leases/{lease_id}",
    mutation: false,
    requiredCapability: "leases:read",
    platform: false,
    uiLocation: "/connectivity",
    description: "One lease resource: contract, window and state.",
  },
  {
    operation: "lease_renew",
    method: "POST",
    path: "/api/2.0/leases/{lease_id}/renewal",
    mutation: true,
    requiredCapability: "leases:write",
    platform: false,
    uiLocation: "/connectivity",
    description: "Renew a lease for a new validity window (the prior lease enters `renewed`).",
    example: LEASE_WINDOW_EXAMPLE,
  },
  {
    operation: "lease_revoke",
    method: "POST",
    path: "/api/2.0/leases/{lease_id}/revocation",
    mutation: true,
    requiredCapability: "leases:write",
    platform: false,
    uiLocation: "/connectivity",
    description: "Revoke a lease (terminal) with a recorded reason.",
    example: REVOCATION_EXAMPLE,
  },
  {
    operation: "endpoints_list",
    method: "GET",
    path: "/api/2.0/webhook-endpoints",
    mutation: false,
    requiredCapability: "webhooks:read",
    platform: false,
    uiLocation: "/developers",
    description: `The application's webhook endpoints. ${LIST_NOTE}`,
  },
  {
    operation: "endpoint_register",
    method: "POST",
    path: "/api/2.0/webhook-endpoints",
    mutation: true,
    requiredCapability: "webhooks:write",
    platform: false,
    uiLocation: "/developers",
    description: "Register a webhook endpoint for observation event types.",
    example: WEBHOOK_EXAMPLE,
  },
  {
    operation: "endpoint_get",
    method: "GET",
    path: "/api/2.0/webhook-endpoints/{endpoint_id}",
    mutation: false,
    requiredCapability: "webhooks:read",
    platform: false,
    uiLocation: "/developers",
    description: "One webhook endpoint resource (url, event types, key id).",
  },
  {
    operation: "deliveries_list",
    method: "GET",
    path: "/api/2.0/webhook-endpoints/{endpoint_id}/deliveries",
    mutation: false,
    requiredCapability: "webhooks:read",
    platform: false,
    uiLocation: "/developers",
    description: `The endpoint's delivery attempts (event, status, retries). ${LIST_NOTE}`,
  },
];

/** The exact expected sizes (pinned by tests). */
export const DEVELOPER_OPERATION_COUNT = 21;
export const PLATFORM_OPERATION_COUNT = 4;
export const COVERAGE_COUNT = DEVELOPER_OPERATION_COUNT + PLATFORM_OPERATION_COUNT;

/** Lookup by the backend's operation id. */
export function coverageByOperation(operation: string): CoverageRecord | undefined {
  return COVERAGE.find((entry) => entry.operation === operation);
}

/** Membership check (an unsupported operation is never callable). */
export function isCoverageOperation(operation: string): boolean {
  return coverageByOperation(operation) !== undefined;
}

/** All mutating operations (idempotency-key required). */
export function coverageMutations(): CoverageRecord[] {
  return COVERAGE.filter((entry) => entry.mutation);
}

/** All read operations. */
export function coverageReads(): CoverageRecord[] {
  return COVERAGE.filter((entry) => !entry.mutation);
}

/** The developer-API boundary operations only. */
export function developerOperations(): CoverageRecord[] {
  return COVERAGE.filter((entry) => !entry.platform);
}

/** The platform surfaces only. */
export function platformOperations(): CoverageRecord[] {
  return COVERAGE.filter((entry) => entry.platform);
}
