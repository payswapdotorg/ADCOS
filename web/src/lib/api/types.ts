/**
 * TypeScript types for every ADCOS envelope and resource (plan Task 3).
 *
 * EVERY field below was derived from REAL captured responses of the
 * local ADCOS sandbox backend (see the verification captures referenced
 * in web/README.md) or from the frozen backend route/error tables.
 * No field is invented; optional members are exactly the members the
 * backend may omit (`undefined`/`null`-able in practice).
 */

// ---------------------------------------------------------------------------
// The success/error envelopes
// ---------------------------------------------------------------------------

/** The rate-limit surface every `/api/2.0/*` response carries. */
export interface RateLimitInfo {
  limit: number;
  remaining: number;
  reset_at: string;
}

/** The idempotency surface mutations carry. */
export interface IdempotencyInfo {
  key: string;
  replayed: boolean;
}

/**
 * The developer-boundary success envelope (HTTP 200 — even creates).
 * `data` is the resource or the list shape.
 */
export interface ApiEnvelope<TData> {
  api_version: string;
  environment: string;
  request_id: string;
  data: TData;
  idempotency?: IdempotencyInfo;
  rate_limit?: RateLimitInfo;
}

/** The list shape: `data: { items, next_cursor, has_more }`. */
export interface ListShape<TItem> {
  items: TItem[];
  next_cursor: string;
  has_more: boolean;
}

/**
 * The typed error body inside `{"error": {...}}` of the developer
 * boundary envelope. `reason` is the boundary vocabulary (displayed
 * VERBATIM in the UI); `canonical_reason` carries the domain reason
 * when a canonical authority rejected the request (also verbatim).
 */
export interface ApiErrorBody {
  http_status: number;
  reason: string;
  canonical_reason: string;
  message: string;
  resource_id: string;
  retry_after: string;
  retryable: boolean;
  environment: string;
  request_id: string;
}

/** The error envelope of `/api/2.0/*` failures. */
export interface ApiErrorEnvelope {
  api_version: string;
  environment: string;
  request_id: string;
  error: ApiErrorBody;
}

/**
 * The runtime-level error envelope (malformed JSON, payload caps,
 * unknown routes on the platform surface): `reason_code` + `message`
 * + `backend` (null when not backend-attributable).
 */
export interface RuntimeErrorEnvelope {
  error: {
    reason_code: string;
    message: string;
    backend: string | null;
  };
}

// ---------------------------------------------------------------------------
// Readiness / liveness (platform surfaces)
// ---------------------------------------------------------------------------

export interface BackendState {
  state: string;
  detail: string;
}

/** `GET /readyz` — 200 when ready, 503 with per-backend detail when not. */
export interface ReadinessDocument {
  ok: boolean;
  service: string;
  mode: string;
  environment: string;
  backends: Record<string, BackendState>;
  delegated_backends?: Record<string, BackendState>;
}

/** `GET /healthz` — liveness. */
export interface LivenessDocument {
  ok: boolean;
  service: string;
}

// ---------------------------------------------------------------------------
// Shared canonical value objects (verbatim from real contract responses)
// ---------------------------------------------------------------------------

export interface Provenance {
  issuer: string;
  decision_refs: string[];
}

/**
 * A typed, provenance-carrying opaque reference (LOCK-117): the contract
 * stores the reference; the console never interprets it.
 */
export interface OpaqueReference {
  ref_kind: string;
  value: string;
  provenance?: Provenance;
}

/** A hard contract constraint (LOCK-108: immutable, never weakened). */
export interface HardConstraint {
  kind: string;
  params: Record<string, string>;
  provenance?: Provenance;
}

export interface ValidityInterval {
  not_before: string;
  not_after: string;
}

export interface TerminationRules {
  conditions: string[];
  compensation: OpaqueReference;
}

export interface BeneficiaryScope {
  beneficiary_kind: string;
  beneficiary_ref: string;
}

export interface ConnectivityPrincipal {
  principal_kind: string;
  principal_ref: string;
}

// ---------------------------------------------------------------------------
// The developer API resources
// ---------------------------------------------------------------------------

/**
 * `GET /api/2.0/application` — the authenticated application self view.
 * `capabilities` uses the frozen vocabulary (`intents:read`, `intents:write`,
 * `leases:read`, `leases:write`, `usage:read`, `assurance:read`,
 * `webhooks:read`, `webhooks:write`). `evidence_class` classifies the
 * environment honestly (`sandbox-simulation` | `production-commercial`).
 */
export interface Application {
  application_id: string;
  application_name: string;
  capabilities: string[];
  developer_id: string;
  environment: string;
  evidence_class: string;
  issued_at: string;
  kind: "application";
  status: string;
  valid_until: string;
}

/**
 * The contract resource (`/api/2.0/intents*`, `/api/2.0/contracts*`):
 * the canonical `ConnectivityContract` serialization, verbatim in
 * meaning, plus the boundary members (`id`, `kind`, `environment`,
 * `command_count`).
 */
export interface ContractResource {
  id: string;
  contract_id: string;
  kind: "contract";
  environment: string;
  command_count: number;
  state: string;
  principal: ConnectivityPrincipal;
  beneficiaries: BeneficiaryScope[];
  requirements: OpaqueReference[];
  hard_constraints: HardConstraint[];
  validity: ValidityInterval;
  termination: TerminationRules;
  service_properties: OpaqueReference[];
  usage_pricing_terms: OpaqueReference | null;
  assurance_obligations: OpaqueReference[];
  execution_scope: OpaqueReference[];
  execution_artifacts: OpaqueReference[];
  accepted_offers: OpaqueReference[];
  signature_refs: OpaqueReference[];
  provenance: Provenance;
}

/**
 * `GET /api/2.0/intents/{id}/lifecycle` — the canonical state machine
 * projection. Note `physical_evidence` is never claimed by the API.
 */
export interface ContractLifecycleResource {
  id: string;
  kind: "contract_lifecycle";
  environment: string;
  evidence_class: string;
  contract_state: string;
  entered_at: string;
  command_count: number;
  validity: ValidityInterval;
  execution_status: string;
  execution_scope_refs: OpaqueReference[];
  execution_artifact_refs: OpaqueReference[];
  assurance_obligation_refs: OpaqueReference[];
  physical_connectivity_observed: boolean;
  physical_evidence: string;
  statements: string[];
  note: string;
}

/** `GET /api/2.0/contracts/{id}/usage` — the referenced usage terms. */
export interface ContractUsageResource {
  id: string;
  kind: "contract_usage_terms";
  environment: string;
  evidence_class: string;
  contract_state: string;
  usage_pricing_terms: OpaqueReference | null;
  note: string;
}

/** `GET /api/2.0/contracts/{id}/assurance` — the referenced obligations. */
export interface ContractAssuranceResource {
  id: string;
  kind: "contract_assurance";
  environment: string;
  evidence_class: string;
  contract_state: string;
  assurance_obligations: OpaqueReference[];
  note: string;
}

/**
 * The lease resource (`/api/2.0/leases*`): canonical `ContractLease`
 * serialization plus the boundary members. `state` uses the frozen
 * lease vocabulary: granted | active | expired | revoked | renewed.
 */
export interface LeaseResource {
  id: string;
  lease_id: string;
  kind: "contract_lease";
  environment: string;
  contract_id: string;
  state: string;
  granted_at: string;
  not_before: string;
  not_after: string;
}

/**
 * The webhook endpoint resource (`/api/2.0/webhook-endpoints*`).
 * `health.last_status` uses the delivery-observation vocabulary
 * (e.g. `idle`); delivery health is observational only.
 */
export interface WebhookEndpointResource {
  id: string;
  kind: "webhook_endpoint";
  environment: string;
  developer_id: string;
  api_version: string;
  url: string;
  event_types: string[];
  key_id: string;
  created_at: string;
  health: {
    deliveries: number;
    delivered: number;
    undelivered: number;
    last_status: string;
    observational_only: boolean;
    note: string;
  };
}

// ---------------------------------------------------------------------------
// The platform / demo surfaces
// ---------------------------------------------------------------------------

/**
 * `GET|POST /demo/contract-fulfillment` — the deterministic full-chain
 * demonstration document (boundary steps, contract, plan, execution,
 * evidence array with `evidence_class: "SOFTWARE"`).
 */
export interface DemoDocument {
  mode: string;
  environment: string;
  evidence_class: string;
  instant: string;
  boundary: Array<{
    method: string;
    route: string;
    status: number;
    request_id: string;
  }>;
  contract: Record<string, unknown>;
  plan: Record<string, unknown>;
  execution: Record<string, unknown>;
  evidence: Array<Record<string, unknown>>;
}

/**
 * `GET /api/contracts/{contract_id}` (NO auth) — the UNVERSIONED
 * platform-side read: the raw canonical contract dict (no envelope).
 * `termination_reason` appears after termination.
 */
export interface PlatformContractDocument extends Record<string, unknown> {
  contract_id: string;
  state: string;
  termination_reason?: string;
}

// ---------------------------------------------------------------------------
// Request inputs (mutation body shapes, verbatim from the gateway schema)
// ---------------------------------------------------------------------------

export interface IntentCreateInput {
  requirements: OpaqueReference[];
  hard_constraints?: HardConstraint[];
  validity: ValidityInterval;
  termination?: TerminationRules;
  beneficiaries?: BeneficiaryScope[];
  service_properties?: OpaqueReference[];
  usage_pricing_terms?: OpaqueReference;
  assurance_obligations?: OpaqueReference[];
  execution_scope?: OpaqueReference[];
  superseded_contract?: OpaqueReference;
  recorded_at: string;
}

export interface OfferSelectionInput {
  offers: OpaqueReference[];
  recorded_at: string;
}

export interface ActivationInput {
  activated_at: string;
  signature_refs: OpaqueReference[];
}

export interface TerminationInput {
  recorded_at: string;
  condition: string;
  reason: string;
}

export interface LeaseGrantInput {
  granted_at: string;
  not_before: string;
  not_after: string;
}

export interface LeaseRenewalInput {
  granted_at: string;
  not_before: string;
  not_after: string;
}

export interface LeaseRevocationInput {
  recorded_at: string;
  reason: string;
}

export interface WebhookEndpointInput {
  url: string;
  event_types: string[];
}

/** List-read options — the boundary carries them in the request body. */
export interface ListQuery {
  limit?: number;
  cursor?: string;
  filters?: Record<string, string>;
}

// ---------------------------------------------------------------------------
// The request descriptor (API reproduction surface)
// ---------------------------------------------------------------------------

/**
 * The descriptor of ONE console-issued API request, carried on
 * `AdcosApiError` and rendered by `ApiRequestPanel` for reproduction.
 *
 * SECURITY: the credential secret is NEVER placed in a descriptor —
 * `X-ADCOS-Credential` rides as the masked sentinel `"«credential»"`
 * and the curl reproduction substitutes `$ADCOS_CREDENTIAL`.
 */
export interface ApiRequestDescriptor {
  method: "GET" | "POST";
  path: string;
  headers: Record<string, string>;
  body?: unknown;
}
