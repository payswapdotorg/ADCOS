/**
 * The backend capability coverage REGISTRY (plan Task 3).
 *
 * EXACTLY the 21 accepted `/api/2.0/*` boundary operations (the frozen
 * route table in developerapi/gateway.py — LOCK-114) plus the 4
 * platform routes (`/healthz`, `/readyz`, `GET|POST
 * /demo/contract-fulfillment`, and the unversioned `/api/contracts/{id}`
 * platform-side read). NO invented endpoints: this registry is the
 * single source the API Explorer (Worker 3) renders from, so an
 * unsupported operation can never appear callable.
 *
 * `requiredCapability` uses the frozen Capability vocabulary
 * (`developerapi/credentials.py`); `""` means authentication only (or
 * no authentication for the platform routes). `uiLocation` is the
 * console route where the operation is surfaced. `example` carries the
 * canonical request body for mutations (validated shapes, lifted from
 * real accepted requests).
 */

import type {
  ActivationInput,
  IntentCreateInput,
  LeaseGrantInput,
  LeaseRenewalInput,
  LeaseRevocationInput,
  OfferSelectionInput,
  TerminationInput,
  WebhookEndpointInput,
} from "./types";

export interface CoverageRecord {
  /** The client method name (web/src/lib/api/client.ts). */
  operation: string;
  method: "GET" | "POST";
  /** The request path (route shape; `{id}` marks path parameters). */
  path: string;
  /** True for the durable mutations (idempotency key required). */
  mutation: boolean;
  /** The frozen capability the route requires ("" = authentication only / public). */
  requiredCapability: string;
  /** The console route that surfaces the operation. */
  uiLocation: string;
  description: string;
  /** The canonical request body for mutations (undefined for reads). */
  example?: unknown;
}

export const COVERAGE: CoverageRecord[] = [
  // -- the developer API boundary (21 accepted operations) ----------------
  {
    operation: "applicationSelf",
    method: "GET",
    path: "/api/2.0/application",
    mutation: false,
    requiredCapability: "",
    uiLocation: "/settings",
    description:
      "The authenticated application self view: identity, environment, capabilities, status and validity.",
  },
  {
    operation: "createIntent",
    method: "POST",
    path: "/api/2.0/intents",
    mutation: true,
    requiredCapability: "intents:write",
    uiLocation: "/connectivity",
    description:
      "Create a connectivity intent: normalized requirements, hard constraints, validity, termination rules.",
    example: {
      requirements: [
        {
          ref_kind: "intent-requirements",
          value: "intent-req:example:normalized-requirements",
          provenance: { issuer: "adcos-console", decision_refs: ["example-1"] },
        },
      ],
      hard_constraints: [{ kind: "latency-bound", params: { max_ms: "50" } }],
      validity: { not_before: "2026-09-13T00:00:00Z", not_after: "2027-09-13T00:00:00Z" },
      termination: {
        conditions: ["principal-requested"],
        compensation: { ref_kind: "compensation", value: "compensation:example:standard" },
      },
      recorded_at: "2026-09-13T00:00:00Z",
    } satisfies IntentCreateInput,
  },
  {
    operation: "listIntents",
    method: "GET",
    path: "/api/2.0/intents",
    mutation: false,
    requiredCapability: "intents:read",
    uiLocation: "/connectivity",
    description: "List the developer's contracts in the INTENT state (paginated).",
  },
  {
    operation: "getIntent",
    method: "GET",
    path: "/api/2.0/intents/{id}",
    mutation: false,
    requiredCapability: "intents:read",
    uiLocation: "/connectivity",
    description: "Get one intent's canonical contract record.",
  },
  {
    operation: "getIntentLifecycle",
    method: "GET",
    path: "/api/2.0/intents/{id}/lifecycle",
    mutation: false,
    requiredCapability: "intents:read",
    uiLocation: "/connectivity",
    description:
      "The canonical contract lifecycle projection: state, execution status, evidence class, physical-evidence stance.",
  },
  {
    operation: "acceptOffers",
    method: "POST",
    path: "/api/2.0/intents/{id}/offers",
    mutation: true,
    requiredCapability: "intents:write",
    uiLocation: "/connectivity",
    description: "Accept provider offers (opaque typed references) for the intent.",
    example: {
      offers: [
        {
          ref_kind: "offer",
          value: "offer:example:reference-provider",
          provenance: { issuer: "adcos-console", decision_refs: ["example-2"] },
        },
      ],
      recorded_at: "2026-09-13T00:00:00Z",
    } satisfies OfferSelectionInput,
  },
  {
    operation: "activateContract",
    method: "POST",
    path: "/api/2.0/intents/{id}/activation",
    mutation: true,
    requiredCapability: "intents:write",
    uiLocation: "/connectivity",
    description: "Activate the contract (from OFFER_SELECTED) with activation instant and signature references.",
    example: {
      activated_at: "2026-09-13T00:00:00Z",
      signature_refs: [{ ref_kind: "signature", value: "signature:example:activation" }],
    } satisfies ActivationInput,
  },
  {
    operation: "listContracts",
    method: "GET",
    path: "/api/2.0/contracts",
    mutation: false,
    requiredCapability: "intents:read",
    uiLocation: "/connectivity",
    description: "List the developer's contracts (paginated, filterable by state).",
  },
  {
    operation: "getContract",
    method: "GET",
    path: "/api/2.0/contracts/{id}",
    mutation: false,
    requiredCapability: "intents:read",
    uiLocation: "/connectivity",
    description: "Get one contract's canonical record.",
  },
  {
    operation: "getContractUsage",
    method: "GET",
    path: "/api/2.0/contracts/{id}/usage",
    mutation: false,
    requiredCapability: "usage:read",
    uiLocation: "/connectivity",
    description: "The contract's referenced usage/pricing terms (opaque reference, never interpreted).",
  },
  {
    operation: "getContractAssurance",
    method: "GET",
    path: "/api/2.0/contracts/{id}/assurance",
    mutation: false,
    requiredCapability: "assurance:read",
    uiLocation: "/assurance",
    description: "The contract's referenced assurance obligations (opaque references, never evaluated here).",
  },
  {
    operation: "terminateContract",
    method: "POST",
    path: "/api/2.0/contracts/{id}/termination",
    mutation: true,
    requiredCapability: "intents:write",
    uiLocation: "/connectivity",
    description: "Terminate the contract deliberately (condition from the frozen termination vocabulary).",
    example: {
      recorded_at: "2026-09-13T12:00:00Z",
      condition: "principal-requested",
      reason: "console: no longer needed",
    } satisfies TerminationInput,
  },
  {
    operation: "grantLease",
    method: "POST",
    path: "/api/2.0/contracts/{id}/leases",
    mutation: true,
    requiredCapability: "leases:write",
    uiLocation: "/networks",
    description: "Grant a connectivity lease against an active contract.",
    example: {
      granted_at: "2026-09-13T00:00:00Z",
      not_before: "2026-09-13T00:00:01Z",
      not_after: "2026-10-13T00:00:00Z",
    } satisfies LeaseGrantInput,
  },
  {
    operation: "listLeases",
    method: "GET",
    path: "/api/2.0/leases",
    mutation: false,
    requiredCapability: "leases:read",
    uiLocation: "/networks",
    description: "List the developer's leases (paginated, filterable by state).",
  },
  {
    operation: "getLease",
    method: "GET",
    path: "/api/2.0/leases/{id}",
    mutation: false,
    requiredCapability: "leases:read",
    uiLocation: "/networks",
    description: "Get one lease's canonical record.",
  },
  {
    operation: "renewLease",
    method: "POST",
    path: "/api/2.0/leases/{id}/renewal",
    mutation: true,
    requiredCapability: "leases:write",
    uiLocation: "/networks",
    description: "Renew a lease with a new validity window.",
    example: {
      granted_at: "2026-09-13T00:00:00Z",
      not_before: "2026-10-12T00:00:00Z",
      not_after: "2026-11-13T00:00:00Z",
    } satisfies LeaseRenewalInput,
  },
  {
    operation: "revokeLease",
    method: "POST",
    path: "/api/2.0/leases/{id}/revocation",
    mutation: true,
    requiredCapability: "leases:write",
    uiLocation: "/networks",
    description: "Revoke a lease (only granted/active leases revoke).",
    example: {
      recorded_at: "2026-09-13T12:00:00Z",
      reason: "console: lease no longer needed",
    } satisfies LeaseRevocationInput,
  },
  {
    operation: "listWebhookEndpoints",
    method: "GET",
    path: "/api/2.0/webhook-endpoints",
    mutation: false,
    requiredCapability: "webhooks:read",
    uiLocation: "/developers",
    description: "List the developer's webhook endpoints (paginated).",
  },
  {
    operation: "registerWebhookEndpoint",
    method: "POST",
    path: "/api/2.0/webhook-endpoints",
    mutation: true,
    requiredCapability: "webhooks:write",
    uiLocation: "/developers",
    description: "Register a webhook endpoint for the frozen event-type vocabulary.",
    example: {
      url: "https://example.com/adcos/webhook",
      event_types: ["connectivity_intent.created", "connectivity_contract.activated"],
    } satisfies WebhookEndpointInput,
  },
  {
    operation: "getWebhookEndpoint",
    method: "GET",
    path: "/api/2.0/webhook-endpoints/{id}",
    mutation: false,
    requiredCapability: "webhooks:read",
    uiLocation: "/developers",
    description: "Get one webhook endpoint with its observational delivery health.",
  },
  {
    operation: "listDeliveries",
    method: "GET",
    path: "/api/2.0/webhook-endpoints/{id}/deliveries",
    mutation: false,
    requiredCapability: "webhooks:read",
    uiLocation: "/developers",
    description: "List one endpoint's signed webhook deliveries (paginated).",
  },

  // -- the platform surfaces (4 routes) ------------------------------------
  {
    operation: "healthz",
    method: "GET",
    path: "/healthz",
    mutation: false,
    requiredCapability: "",
    uiLocation: "/",
    description: "Liveness: always 200 with {ok, service}.",
  },
  {
    operation: "readyz",
    method: "GET",
    path: "/readyz",
    mutation: false,
    requiredCapability: "",
    uiLocation: "/",
    description:
      "Readiness: mode, environment and every consumed backend's state; 503 with per-backend detail when degraded.",
  },
  {
    operation: "demoContractFulfillment",
    method: "GET",
    path: "/demo/contract-fulfillment",
    mutation: false,
    requiredCapability: "",
    uiLocation: "/fulfillment",
    description:
      "The deterministic full-chain demonstration document (boundary, contract, plan, execution, SOFTWARE evidence). The POST form accepts an optional {instant} RFC 3339 body; the GET form is the idempotent default.",
  },
  {
    operation: "platformContractRead",
    method: "GET",
    path: "/api/contracts/{id}",
    mutation: false,
    requiredCapability: "",
    uiLocation: "/connectivity",
    description:
      "The UNVERSIONED platform-side contract read (no auth): the raw canonical contract dict — the operator's diagnostic view.",
  },
];

/** The count invariant the coverage tests pin (21 + 4 = 25 records). */
export const COVERAGE_SIZE = COVERAGE.length;

/** Look up one operation's coverage record (by client method name). */
export function findCoverage(operation: string): CoverageRecord | undefined {
  return COVERAGE.find((record) => record.operation === operation);
}

/** All coverage records surfaced by a console route. */
export function coverageForRoute(uiLocation: string): CoverageRecord[] {
  return COVERAGE.filter((record) => record.uiLocation === uiLocation);
}

/** Every mutation (the durable idempotency-gated operations). */
export function coverageMutations(): CoverageRecord[] {
  return COVERAGE.filter((record) => record.mutation);
}

/** The frozen capability vocabulary the boundary enforces. */
export const CAPABILITY_VOCABULARY = [
  "intents:read",
  "intents:write",
  "leases:read",
  "leases:write",
  "usage:read",
  "assurance:read",
  "webhooks:read",
  "webhooks:write",
] as const;
