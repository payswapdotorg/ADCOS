/**
 * TypeScript types for every ADCOS envelope and resource.
 *
 * DERIVED FROM REAL RESPONSES (the local sandbox runtime, captures in
 * /home/z/adcos-captures — never invented fields). Where the backend may
 * add members (it owns the vocabulary), types stay permissive-but-honest:
 * required members are exactly what every observed response carries.
 */

/* ------------------------------------------------------------------ *
 * Envelopes
 * ------------------------------------------------------------------ */

/** The rate-limit surface every /api/2.0 response carries. */
export interface RateLimit {
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
 * The canonical success envelope (HTTP 200 — even for creates).
 */
export interface AdcosEnvelope<T> {
  api_version: string;
  environment: string;
  request_id: string;
  data: T;
  idempotency?: IdempotencyInfo;
  rate_limit?: RateLimit;
}

/** The list shape every list operation returns as `data`. */
export interface ListResponse<T> {
  items: T[];
  next_cursor: string;
  has_more: boolean;
}

/** List request parameters — sent as the GET request's JSON BODY. */
export interface ListParams {
  /** Page size; 1..100, default 20 (backend-frozen bounds). */
  limit?: number;
  /** Opaque cursor from a previous page (context-scoped). */
  cursor?: string;
  /** Equality filters over declared members (contracts/leases: `state`). */
  filters?: Record<string, string>;
}

/** The typed error envelope member of a non-2xx response. */
export interface AdcosErrorEnvelope {
  api_version: string;
  environment: string;
  request_id: string;
  error: {
    canonical_reason: string;
    environment: string;
    http_status: number;
    message: string;
    reason: string;
    request_id: string;
    resource_id: string;
    retry_after: string;
    retryable: boolean;
  };
}

/** The runtime-level envelope (malformed JSON, unknown routes, ...). */
export interface RuntimeErrorEnvelope {
  error: {
    reason_code: string;
    message: string;
    backend: string | null;
  };
}

/* ------------------------------------------------------------------ *
 * Shared canonical material
 * ------------------------------------------------------------------ */

/** Provenance of canonical material (issuer + decision references). */
export interface Provenance {
  issuer: string;
  decision_refs: string[];
}

/** The canonical opaque typed reference: {ref_kind, value, provenance?}. */
export interface OpaqueReference {
  ref_kind: string;
  value: string;
  provenance?: Provenance;
}

/** A hard constraint: {kind, params}. */
export interface HardConstraint {
  kind: string;
  params: Record<string, number | string>;
}

/** The validity window. */
export interface ValidityInterval {
  not_before: string;
  not_after: string;
}

/** Termination rules: {conditions, compensation ref}. */
export interface TerminationRules {
  conditions: string[];
  compensation: OpaqueReference;
}

/** A beneficiary scope: {beneficiary_kind, beneficiary_ref}. */
export interface BeneficiaryScope {
  beneficiary_kind: string;
  beneficiary_ref: string;
}

/** The contract principal (derived from the authenticated application). */
export interface ConnectivityPrincipal {
  principal_kind: string;
  principal_ref: string;
}

/* ------------------------------------------------------------------ *
 * Resources
 * ------------------------------------------------------------------ */

/** GET /api/2.0/application — the authenticated application. */
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
 * The contract resource (intent reads and contract reads share one shape:
 * a contract in state INTENT is "the intent").
 */
export interface Contract {
  accepted_offers: OpaqueReference[];
  assurance_obligations: OpaqueReference[];
  beneficiaries: BeneficiaryScope[];
  command_count: number;
  contract_id: string;
  environment: string;
  execution_artifacts: OpaqueReference[];
  execution_scope: OpaqueReference[];
  hard_constraints: HardConstraint[];
  id: string;
  kind: "contract";
  principal: ConnectivityPrincipal;
  provenance: Provenance;
  requirements: OpaqueReference[];
  service_properties: OpaqueReference[];
  signature_refs: OpaqueReference[];
  state: string;
  termination: TerminationRules;
  usage_pricing_terms: OpaqueReference;
  validity: ValidityInterval;
}

/** GET /api/2.0/intents/{id}/lifecycle — the lifecycle observation. */
export interface ContractLifecycle {
  assurance_obligation_refs: OpaqueReference[];
  command_count: number;
  contract_state: string;
  entered_at: string;
  environment: string;
  evidence_class: string;
  execution_artifact_refs: OpaqueReference[];
  execution_scope_refs: OpaqueReference[];
  execution_status: string;
  id: string;
  kind: "contract_lifecycle";
  note: string;
  physical_connectivity_observed: boolean;
  physical_evidence: string;
  statements: string[];
  validity: ValidityInterval;
}

/** Lease resources (grant/renewal responses and lease reads). */
export interface Lease {
  contract_id: string;
  environment: string;
  granted_at: string;
  id: string;
  kind: "contract_lease";
  lease_id: string;
  not_after: string;
  not_before: string;
  state: string;
  revocation_reason?: string;
}

/** GET /api/2.0/contracts/{id}/usage — referenced usage semantics. */
export interface ContractUsage {
  contract_state: string;
  environment: string;
  evidence_class: string;
  id: string;
  kind: "contract_usage_terms";
  note: string;
  usage_pricing_terms: OpaqueReference;
}

/** GET /api/2.0/contracts/{id}/assurance — referenced assurance obligations. */
export interface ContractAssurance {
  assurance_obligations: OpaqueReference[];
  contract_state: string;
  environment: string;
  evidence_class: string;
  id: string;
  kind: "contract_assurance";
  note: string;
}

/** Webhook endpoint resources. */
export interface WebhookEndpoint {
  api_version: string;
  created_at: string;
  developer_id: string;
  environment: string;
  event_types: string[];
  id: string;
  key_id: string;
  kind: "webhook_endpoint";
  url: string;
}

/** One webhook delivery attempt record. */
export interface WebhookDelivery {
  attempts: number;
  delivery_sequence: number;
  endpoint_id: string;
  environment: string;
  event_id: string;
  event_type: string;
  id: string;
  kind: "webhook_delivery";
  last_attempt_at: string;
  last_status: string;
  next_attempt_at: string;
  occurred_at: string;
  resource_id: string;
  resource_kind: string;
  status: string;
}

/* ------------------------------------------------------------------ *
 * Platform surfaces (unauthenticated / unversioned)
 * ------------------------------------------------------------------ */

/** GET /healthz */
export interface Healthz {
  ok: boolean;
  service: string;
}

/** One backend state entry inside readiness. */
export interface ReadinessBackend {
  state: string;
  detail: string;
}

/** GET /readyz — 200 when all ready, 503 (with detail) when not. */
export interface Readiness {
  ok: boolean;
  service: string;
  mode: string;
  environment: string;
  backends: Record<string, ReadinessBackend>;
  delegated_backends?: Record<string, ReadinessBackend>;
}

/** GET|POST /demo/contract-fulfillment — the deterministic demo document. */
export interface DemoBoundaryEntry {
  method: string;
  route: string;
  status: number;
  request_id: string;
}

export interface DemoDocument {
  mode: string;
  environment: string;
  evidence_class: string;
  instant: string;
  boundary: DemoBoundaryEntry[];
  contract: Record<string, unknown>;
  plan: Record<string, unknown>;
  execution: Record<string, unknown>;
  evidence: Record<string, unknown>[];
}

/* ------------------------------------------------------------------ *
 * Mutation request bodies (schema roles — canonical material only)
 * ------------------------------------------------------------------ */

/**
 * POST /api/2.0/intents (intent_request).
 *
 * `termination` is REQUIRED — verified live: the boundary rejects a body
 * without it with `invalid-input` "request body is missing required member
 * 'termination'". `beneficiaries`/`service_properties`/
 * `usage_pricing_terms`/`assurance_obligations`/`execution_scope`/
 * `superseded_contract` are genuinely optional (verified live with a
 * minimal body).
 */
export interface CreateIntentInput {
  recorded_at: string;
  requirements: OpaqueReference[];
  hard_constraints?: HardConstraint[];
  validity: ValidityInterval;
  termination: TerminationRules;
  beneficiaries?: BeneficiaryScope[];
  service_properties?: OpaqueReference[];
  usage_pricing_terms?: OpaqueReference;
  assurance_obligations?: OpaqueReference[];
  execution_scope?: OpaqueReference[];
  superseded_contract?: OpaqueReference;
}

/** POST /api/2.0/intents/{id}/offers (offer_selection). */
export interface AcceptOffersInput {
  recorded_at: string;
  offers: OpaqueReference[];
}

/** POST /api/2.0/intents/{id}/activation (activation_request). */
export interface ActivateContractInput {
  activated_at: string;
  signature_refs: OpaqueReference[];
}

/** POST /api/2.0/contracts/{id}/termination (termination_request). */
export interface TerminateContractInput {
  recorded_at: string;
  condition: string;
  reason: string;
}

/** POST /api/2.0/contracts/{id}/leases and /api/2.0/leases/{id}/renewal. */
export interface LeaseWindowInput {
  granted_at: string;
  not_before: string;
  not_after: string;
}

/** POST /api/2.0/leases/{id}/revocation (lease_revocation). */
export interface RevokeLeaseInput {
  recorded_at: string;
  reason: string;
}

/** POST /api/2.0/webhook-endpoints (webhook_endpoint). */
export interface RegisterWebhookEndpointInput {
  url: string;
  event_types: string[];
}
