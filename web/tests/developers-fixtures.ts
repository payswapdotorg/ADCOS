/**
 * REAL backend shapes for the Developers-area feature tests.
 *
 * The application + session fixtures are transcribed VERBATIM from the
 * local sandbox runtime captures (the same deterministic sandbox
 * composition Worker 2's fixtures documented — content-derived ids,
 * stable values). The webhook fixtures are derived from the backend's
 * OWN serializers (developerapi/gateway.py `_endpoint_register` and
 * `_delivery_resource`) and the runtime battery's real registration
 * request (tools/runtime_selftest.py case 29: url
 * https://console.example/adcos/webhook, event_types
 * connectivity_intent.created / connectivity_lease.granted /
 * webhook_endpoint.registered) — member sets and value formats (the
 * `whk-<16 hex>-whv1` key_id derivation, sha256 resource ids, the
 * sorted event_types) follow the backend exactly; no field is
 * invented beyond the deterministic ids themselves.
 *
 * `FIXTURE_APPLICATION_PARTIAL_CAPS` is a TEST VARIANT of the captured
 * application with three registry-required grants removed — it exists
 * to exercise the denied-capability presentation, and says so.
 *
 * Deterministic, no network: tests mock fetch and return these.
 */

import type {
  Application,
  ListResponse,
  WebhookDelivery,
  WebhookEndpoint,
} from "@/lib/api/types";

/* ------------------------------------------------------------------ *
 * The connected application (GET /api/2.0/application)
 * ------------------------------------------------------------------ */

export const FIXTURE_APPLICATION: Application = {
  application_id: "sha256:c20c5f90db52d8a89c5168fdb71f522ed9648d1264330357a9cdad98532f1f01",
  application_name: "adcos:runtime:contract-fulfillment-demo",
  capabilities: [
    "assurance:read",
    "intents:read",
    "intents:write",
    "leases:read",
    "leases:write",
    "usage:read",
    "webhooks:read",
    "webhooks:write",
  ],
  developer_id: "adcos:runtime:demo-developer",
  environment: "sandbox",
  evidence_class: "sandbox-simulation",
  issued_at: "2026-09-13T00:00:00Z",
  kind: "application",
  status: "active",
  valid_until: "2036-09-13T00:00:00Z",
};

export const FIXTURE_SESSION = {
  applicationId: FIXTURE_APPLICATION.application_id,
  credential: "dasec_6f0a61f4d683e1b7a06859649217ac1714552b64c93ea25509e0e7dfa0ed5b60",
};

/** TEST VARIANT: three registry-required grants removed (denied-state coverage). */
export const FIXTURE_APPLICATION_PARTIAL_CAPS: Application = {
  ...FIXTURE_APPLICATION,
  capabilities: [
    "assurance:read",
    "intents:read",
    "intents:write",
    "leases:read",
    "leases:write",
  ],
};

/* ------------------------------------------------------------------ *
 * Webhook endpoints (POST /api/2.0/webhook-endpoints + reads)
 * ------------------------------------------------------------------ */

/** The battery's real registration, shaped by the backend serializer. */
export const FIXTURE_ENDPOINT: WebhookEndpoint = {
  api_version: "2.0",
  created_at: "2026-09-14T04:50:00Z",
  developer_id: "adcos:runtime:demo-developer",
  environment: "sandbox",
  // the backend stores event_types sorted
  event_types: [
    "connectivity_intent.created",
    "connectivity_lease.granted",
    "webhook_endpoint.registered",
  ],
  id: "sha256:9f31a4d20c8b57e61f2a90d4c7b83e5a46d1c0f8e92b4a7d5c3e6f0a1b8d4273",
  // whk-<endpoint id's first 16 hex chars>-<key version>
  key_id: "whk-9f31a4d20c8b57e6-whv1",
  kind: "webhook_endpoint",
  url: "https://console.example/adcos/webhook",
};

/** A second endpoint (the contract-state family). */
export const FIXTURE_ENDPOINT_SECOND: WebhookEndpoint = {
  api_version: "2.0",
  created_at: "2026-09-14T05:10:00Z",
  developer_id: "adcos:runtime:demo-developer",
  environment: "sandbox",
  event_types: [
    "connectivity_contract.activated",
    "connectivity_contract.state_changed",
    "connectivity_contract.terminated",
  ],
  id: "sha256:4c8d1e2f3a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d",
  key_id: "whk-4c8d1e2f3a5b6c7d-whv1",
  kind: "webhook_endpoint",
  url: "https://ops.example.net/hooks/adcos-status",
};

export const FIXTURE_ENDPOINTS_LIST: ListResponse<WebhookEndpoint> = {
  items: [FIXTURE_ENDPOINT, FIXTURE_ENDPOINT_SECOND],
  next_cursor: "",
  has_more: false,
};

/* ------------------------------------------------------------------ *
 * The delivery journal (GET /api/2.0/webhook-endpoints/{id}/deliveries)
 * ------------------------------------------------------------------ */

/** A delivered registration event. */
export const FIXTURE_DELIVERY_DELIVERED: WebhookDelivery = {
  attempts: 1,
  delivery_sequence: 1,
  endpoint_id: FIXTURE_ENDPOINT.id,
  environment: "sandbox",
  event_id: "sha256:5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b0a9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c",
  event_type: "webhook_endpoint.registered",
  id: "sha256:1a2b3c4d5e6f70819a2b3c4d5e6f70819a2b3c4d5e6f70819a2b3c4d5e6f7081",
  kind: "webhook_delivery",
  last_attempt_at: "2026-09-14T04:50:00Z",
  last_status: "delivered",
  next_attempt_at: "",
  occurred_at: "2026-09-14T04:50:00Z",
  resource_id: FIXTURE_ENDPOINT.id,
  resource_kind: "webhook_endpoint",
  status: "delivered",
};

/** A failed activation event awaiting its retry (backoff visible). */
export const FIXTURE_DELIVERY_FAILED: WebhookDelivery = {
  attempts: 2,
  delivery_sequence: 2,
  endpoint_id: FIXTURE_ENDPOINT.id,
  environment: "sandbox",
  event_id: "sha256:0f1e2d3c4b5a69788796a5b4c3d2e1f0a1b2c3d4e5f60718293a4b5c6d7e8f90",
  event_type: "connectivity_contract.activated",
  id: "sha256:9c8b7a6f5e4d3c2b1a0f9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2f1e0d9c8b",
  kind: "webhook_delivery",
  last_attempt_at: "2026-09-14T05:20:00Z",
  last_status: "failed",
  next_attempt_at: "2026-09-14T05:25:00Z",
  occurred_at: "2026-09-14T05:19:00Z",
  // the real captured demo contract id (Worker 2's fixture)
  resource_id: "sha256:8c925c7fe3bddc7d398e0b4bebd8151e5c682147a33043579f9ed778ea559c55",
  resource_kind: "contract",
  status: "failed",
};

export const FIXTURE_DELIVERIES: ListResponse<WebhookDelivery> = {
  items: [FIXTURE_DELIVERY_DELIVERED, FIXTURE_DELIVERY_FAILED],
  next_cursor: "",
  has_more: false,
};
