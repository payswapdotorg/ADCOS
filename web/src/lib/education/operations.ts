/**
 * The Console V2 education registry — the OPERATION LEARNING records.
 *
 * The DEC-0128 program, Task 1 of the frozen plan: one education record
 * for EVERY operation of the accepted coverage registry (the design
 * §16 coverage rule — a supported canonical operation may lack
 * education only when explicitly marked internal-only / not
 * user-actionable; none is, so this is 25 of 25). The `operation` ids
 * and the mutation example fields come from `@/lib/api/coverage`
 * verbatim — this file never defines a second endpoint catalog, and
 * the module-load guard below throws at import time if an education
 * record names an operation the coverage registry does not carry.
 * `relatedErrors` uses only the canonical reason codes of
 * `@/lib/api/errors` — verbatim, never synonyms.
 */

import { COVERAGE } from "@/lib/api/coverage";
import type { OperationLearningDefinition } from "./types";

/** The operation-learning registry — one record per coverage operation. */
export const OPERATION_EDUCATION: OperationLearningDefinition[] = [
  /* -------- platform surfaces (4) -------- */
  {
    operation: "healthz",
    purpose: "Runtime liveness probe — always 200 while the process is serving.",
    prerequisites: "None — an unauthenticated platform surface.",
    lifecyclePosition: "Diagnose: the first check when anything looks wrong.",
    typicalSequence:
      "Run healthz first; if the request itself fails, the runtime is unreachable from here (the browser surfaces that as backend-unreachable). Follow with readyz to see per-backend state.",
    fieldExplanations: [
      {
        field: "request body",
        explanation:
          "None — a bodyless GET. The response is the liveness document: ok and the service name.",
      },
    ],
    relatedConcepts: [],
    relatedErrors: ["backend-unreachable"],
    nextOperation: "readyz",
    userActionable: true,
  },
  {
    operation: "readyz",
    purpose:
      "Runtime readiness: mode, environment and every consumed backend's state — 200 when all are ready, 503 with per-backend detail when not.",
    prerequisites: "None — an unauthenticated platform surface.",
    lifecyclePosition:
      "Operate / Diagnose: separates liveness from readiness — a live runtime can still be degraded by a consumed backend.",
    typicalSequence:
      "Run after healthz. The shell's environment indicator polls this same route; the per-backend detail locates a degraded dependency before you touch contracts.",
    fieldExplanations: [
      {
        field: "request body",
        explanation:
          "None — a bodyless GET. The response carries mode, environment and a backends map with state and detail per consumed backend.",
      },
    ],
    relatedConcepts: [],
    relatedErrors: ["backend-unreachable"],
    nextOperation: "application_self",
    userActionable: true,
  },
  {
    operation: "demo_contract_fulfillment",
    purpose:
      "The deterministic full-chain demonstration document — the boundary trace, contract, plan, execution and evidence for one instant.",
    prerequisites: "None — the unauthenticated demonstration context (no capability grant).",
    lifecyclePosition: "Understand: the canonical first run for learning the model end to end.",
    typicalSequence:
      "GET runs at the default instant; POST the same route with an instant for a specific one. Inspect the chain on the run page, then read the demonstration's contract through the platform contract read.",
    fieldExplanations: [
      {
        field: "instant",
        explanation:
          "The RFC 3339 UTC instant the demonstration runs at — a different instant is a genuinely new demonstration contract. The GET form sends no body and uses the default instant.",
      },
      {
        field: "request body",
        explanation:
          "GET: none. POST: a JSON object whose only member is instant.",
      },
    ],
    relatedConcepts: [
      "demo-fulfillment-journey",
      "connectivity-contract",
      "execution-plan",
      "fulfillment",
      "evidence",
      "assurance",
    ],
    relatedErrors: ["backend-unreachable", "malformed-json", "invalid-request-body"],
    nextOperation: "platform_contract_read",
    userActionable: true,
  },
  {
    operation: "platform_contract_read",
    purpose:
      "The unversioned platform-side contract read — the raw canonical contract dict for a contract id, with no authentication.",
    prerequisites:
      "A contract id. The demonstration document's contract id works without a credential.",
    lifecyclePosition:
      "Understand / Integrate: the platform mirror used where the versioned, authenticated read is not available.",
    typicalSequence:
      "Run after the demonstration (its document carries the contract id), or whenever the raw canonical dict is wanted without the 2.0 envelope. An unknown id returns the typed 404 envelope with resource-unknown.",
    fieldExplanations: [
      {
        field: "request body",
        explanation: "None — a bodyless GET. contract_id rides the path.",
      },
      {
        field: "contract_id",
        explanation:
          "The contract id from a list, a demonstration document or a versioned contract read — the raw canonical contract dict (or the typed 404 envelope) is returned for it.",
      },
    ],
    relatedConcepts: ["connectivity-contract"],
    relatedErrors: ["resource-unknown", "backend-unreachable"],
    nextOperation: "contract_get",
    userActionable: true,
  },

  /* -------- developer API (21) -------- */
  {
    operation: "application_self",
    purpose:
      "The authenticated application: identity, environment, capabilities, status and validity.",
    prerequisites:
      "A connected application credential (the session menu). No capability grant is required.",
    lifecyclePosition: "Integrate: the first authenticated call — every later call runs as this principal.",
    typicalSequence:
      "Connect or verify the session, read the application to see the granted capabilities, then see what already exists (contracts_list) or record your first intent (intent_create). The Developers workspace and the Explorer both start here.",
    fieldExplanations: [
      {
        field: "request body",
        explanation:
          "None — a bodyless authenticated GET. The response is the application resource: application_id, capabilities, environment, status and valid_until.",
      },
    ],
    relatedConcepts: ["application-capability", "policy"],
    relatedErrors: [
      "authentication-invalid",
      "authentication-expired",
      "environment-mismatch",
      "version-unsupported",
      "rate-limited",
      "backend-unreachable",
    ],
    nextOperation: "contracts_list",
    userActionable: true,
  },
  {
    operation: "intent_create",
    purpose:
      "Record a connectivity intent — the contract creation core. The principal is derived from the authenticated application.",
    prerequisites:
      "The intents:write capability, plus the canonical material: requirements, validity and termination are required; hard constraints and the referenced terms are optional.",
    lifecyclePosition: "Build: the first mutation of every contract — describe the requirement, reach INTENT.",
    typicalSequence:
      "The builder on the contracts workspace composes this body. POST it (an idempotency key is required for mutations), then read the intent back (intent_get) or accept offers (offers_accept).",
    fieldExplanations: [
      {
        field: "recorded_at",
        explanation: "The RFC 3339 UTC instant the material was recorded.",
      },
      {
        field: "requirements",
        explanation:
          "Opaque typed references to the requirement material — the issuer and decision refs stay attached, passing through verbatim, never interpreted.",
      },
      {
        field: "hard_constraints",
        explanation:
          "Optional constraint bounds ({kind, params} — for example latency-bound or throughput-floor). Immutable after creation; a replan re-verifies against them, never weakens them.",
      },
      {
        field: "validity",
        explanation: "The not_before / not_after window within which the contract is answerable.",
      },
      {
        field: "termination",
        explanation:
          "Required — the conditions that may terminate the contract (for example principal-requested, validity-expired) plus the compensation reference.",
      },
      {
        field: "beneficiaries",
        explanation:
          "Optional beneficiary scope ({beneficiary_kind, beneficiary_ref}) — who the connectivity is for.",
      },
      {
        field: "service_properties",
        explanation: "Optional opaque references to the requested service properties.",
      },
      {
        field: "usage_pricing_terms",
        explanation:
          "Optional opaque reference to the usage/pricing terms — referenced, never interpreted.",
      },
      {
        field: "assurance_obligations",
        explanation:
          "Optional opaque references to the obligations that must hold for assurance.",
      },
      {
        field: "execution_scope",
        explanation: "Optional opaque references scoping where execution may happen.",
      },
    ],
    relatedConcepts: ["connectivity-contract"],
    relatedErrors: [
      "capability-denied",
      "invalid-input",
      "temporal-invalid",
      "secret-rejected",
      "vocabulary",
      "idempotency-key-required",
      "sequence-conflict",
      "malformed-json",
      "invalid-request-body",
      "payload-too-large",
    ],
    nextOperation: "offers_accept",
    userActionable: true,
  },
  {
    operation: "intents_list",
    purpose:
      "Contracts still in the INTENT state — the queue of recorded-but-not-yet-selected requirements.",
    prerequisites: "The intents:read capability.",
    lifecyclePosition: "Build: survey what is awaiting offer selection.",
    typicalSequence:
      "List intents after recording one, or on landing in the connectivity workspace. Open one with intent_get to review its full canonical material.",
    fieldExplanations: [
      {
        field: "request body",
        explanation:
          "Pagination rides the GET request's JSON body — {limit (1..100, default 20), cursor, filters}. No other body members are sent.",
      },
      {
        field: "limit",
        explanation: "Page size, 1 to 100, default 20.",
      },
      {
        field: "cursor",
        explanation: "The opaque pagination cursor carried by the previous response.",
      },
      {
        field: "filters",
        explanation: "The declared filter members for this list context.",
      },
    ],
    relatedConcepts: ["connectivity-contract"],
    relatedErrors: [
      "pagination-invalid",
      "filter-invalid",
      "capability-denied",
      "authentication-expired",
      "rate-limited",
    ],
    nextOperation: "intent_get",
    userActionable: true,
  },
  {
    operation: "intent_get",
    purpose: "One intent's canonical contract resource — the full canonical material, verbatim.",
    prerequisites: "The intents:read capability and an intent id.",
    lifecyclePosition: "Build: review what was recorded before accepting offers.",
    typicalSequence:
      "Arrive from intents_list or a detail page. Review the requirements, constraints, validity and termination, then observe the lifecycle (intent_lifecycle) or accept offers (offers_accept).",
    fieldExplanations: [
      {
        field: "request body",
        explanation: "None — a bodyless GET. intent_id rides the path.",
      },
      {
        field: "intent_id",
        explanation: "The intent id from intents_list or the create response.",
      },
    ],
    relatedConcepts: ["connectivity-contract"],
    relatedErrors: ["resource-unknown", "unknown-contract", "capability-denied"],
    nextOperation: "intent_lifecycle",
    userActionable: true,
  },
  {
    operation: "intent_lifecycle",
    purpose:
      "The honest lifecycle observation for one contract: state machine position, statements and execution status — physical connectivity is never claimed by API success.",
    prerequisites: "The intents:read capability and an intent id.",
    lifecyclePosition:
      "Build / Operate / Diagnose: the canonical what-is-ADCOS-doing read, rendered by the contract detail page's Eligibility section.",
    typicalSequence:
      "Read it after any state change (offer acceptance, activation) and whenever behavior is unexpected. The observation reports contract_state, execution_status, evidence_class, physical_connectivity_observed and the backend's note and statements.",
    fieldExplanations: [
      {
        field: "request body",
        explanation: "None — a bodyless GET. intent_id rides the path.",
      },
      {
        field: "intent_id",
        explanation: "The intent id whose lifecycle observation is requested.",
      },
    ],
    relatedConcepts: ["eligibility", "fulfillment", "connectivity-contract"],
    relatedErrors: ["resource-unknown", "unknown-contract", "capability-denied"],
    nextOperation: "contract_get",
    userActionable: true,
  },
  {
    operation: "offers_accept",
    purpose:
      "Accept opaque typed offer references onto the intent — the contract moves to OFFER_SELECTED.",
    prerequisites:
      "The intents:write capability, an intent in the INTENT state, and the offer references to accept.",
    lifecyclePosition: "Build: eligibility → offer selection — the bridge from requirement to plan.",
    typicalSequence:
      "After reviewing the intent (intent_get), accept the chosen offer references. The contract records them as accepted_offers, and activation (contract_activate) becomes possible.",
    fieldExplanations: [
      {
        field: "recorded_at",
        explanation: "The RFC 3339 UTC instant the selection was recorded.",
      },
      {
        field: "offers",
        explanation:
          "The opaque typed offer references being accepted — each carries ref_kind, value and provenance (issuer plus decision refs), passing through verbatim.",
      },
    ],
    relatedConcepts: ["offer", "connectivity-contract"],
    relatedErrors: [
      "resource-unknown",
      "unknown-contract",
      "invalid-transition",
      "capability-denied",
      "invalid-input",
      "vocabulary",
      "idempotency-key-required",
    ],
    nextOperation: "contract_activate",
    userActionable: true,
  },
  {
    operation: "contract_activate",
    purpose:
      "Activate the contract — the move to CONTRACT_ACTIVE, recording the activation instant and signature references.",
    prerequisites:
      "The intents:write capability and a contract in OFFER_SELECTED — offers must be accepted first.",
    lifecyclePosition: "Build → Operate: the contract becomes active and fulfillment work begins.",
    typicalSequence:
      "Run after offers_accept. POST the activation instant and signature references, then observe the lifecycle (intent_lifecycle) to see the active state and execution status.",
    fieldExplanations: [
      {
        field: "activated_at",
        explanation: "The RFC 3339 UTC instant of activation.",
      },
      {
        field: "signature_refs",
        explanation:
          "Opaque typed references to the activation signatures — recorded verbatim with their provenance.",
      },
    ],
    relatedConcepts: ["connectivity-contract", "fulfillment"],
    relatedErrors: [
      "invalid-transition",
      "not-yet-valid",
      "temporal-invalid",
      "capability-denied",
      "resource-unknown",
      "idempotency-key-required",
    ],
    nextOperation: "intent_lifecycle",
    userActionable: true,
  },
  {
    operation: "contracts_list",
    purpose:
      "All the application's contracts — the portfolio view, filterable by lifecycle state.",
    prerequisites: "The intents:read capability.",
    lifecyclePosition: "Operate: the contracts workspace's backing read.",
    typicalSequence:
      "Land here from the connectivity workspace. Filter by state to find active or degraded contracts, then open one with contract_get.",
    fieldExplanations: [
      {
        field: "request body",
        explanation:
          "Pagination rides the GET request's JSON body — {limit (1..100, default 20), cursor, filters}. No other body members are sent.",
      },
      {
        field: "limit",
        explanation: "Page size, 1 to 100, default 20.",
      },
      {
        field: "cursor",
        explanation: "The opaque pagination cursor carried by the previous response.",
      },
      {
        field: "filters",
        explanation: "Contracts filter by state ({state: <lifecycle state>}).",
      },
    ],
    relatedConcepts: ["connectivity-contract"],
    relatedErrors: ["pagination-invalid", "filter-invalid", "capability-denied", "rate-limited"],
    nextOperation: "contract_get",
    userActionable: true,
  },
  {
    operation: "contract_get",
    purpose:
      "One canonical contract resource with the complete lifecycle material — requirements, constraints, accepted offers, the plan binding and referenced terms.",
    prerequisites: "The intents:read capability and a contract id.",
    lifecyclePosition: "Operate: the contract detail page's core read.",
    typicalSequence:
      "Arrive from contracts_list. The detail page then reads the lifecycle observation (intent_lifecycle), the usage terms (contract_usage) and the assurance obligations (contract_assurance) alongside this resource.",
    fieldExplanations: [
      {
        field: "request body",
        explanation: "None — a bodyless GET. contract_id rides the path.",
      },
      {
        field: "contract_id",
        explanation: "The contract id from contracts_list, a lease or the demonstration document.",
      },
    ],
    relatedConcepts: ["connectivity-contract", "execution-plan"],
    relatedErrors: ["resource-unknown", "unknown-contract", "capability-denied"],
    nextOperation: "contract_usage",
    userActionable: true,
  },
  {
    operation: "contract_usage",
    purpose:
      "The contract's referenced usage/pricing semantics — referenced, never interpreted.",
    prerequisites: "The usage:read capability and a contract id.",
    lifecyclePosition: "Operate: the usage half of the contract's referenced terms.",
    typicalSequence:
      "Read from the contract detail page — the Eligibility section renders the usage_pricing_terms reference with the backend's note verbatim.",
    fieldExplanations: [
      {
        field: "request body",
        explanation: "None — a bodyless GET. contract_id rides the path.",
      },
      {
        field: "contract_id",
        explanation: "The contract whose referenced usage semantics are requested.",
      },
    ],
    relatedConcepts: ["connectivity-contract"],
    relatedErrors: ["resource-unknown", "unknown-contract", "capability-denied"],
    nextOperation: "contract_assurance",
    userActionable: true,
  },
  {
    operation: "contract_assurance",
    purpose:
      "The contract's referenced assurance obligations — referenced, never evaluated here.",
    prerequisites: "The assurance:read capability and a contract id.",
    lifecyclePosition: "Operate: the assurance read behind the Assurance workspace.",
    typicalSequence:
      "Read from the contract detail page or the Assurance workspace. The obligations render verbatim with provenance, and the honest empty attestation state shows when nothing is recorded.",
    fieldExplanations: [
      {
        field: "request body",
        explanation: "None — a bodyless GET. contract_id rides the path.",
      },
      {
        field: "contract_id",
        explanation: "The contract whose referenced assurance obligations are requested.",
      },
    ],
    relatedConcepts: ["assurance", "connectivity-contract"],
    relatedErrors: ["resource-unknown", "unknown-contract", "capability-denied"],
    nextOperation: "lease_grant",
    userActionable: true,
  },
  {
    operation: "contract_terminate",
    purpose:
      "Terminate the contract — a terminal state, recorded with a condition and a reason.",
    prerequisites:
      "The intents:write capability, a non-terminal contract, and the termination condition and reason to record.",
    lifecyclePosition: "Operate: the end of the lifecycle — nothing follows a terminal contract.",
    typicalSequence:
      "A deliberate end-of-life step. POST the recorded instant, condition and reason; the lifecycle observation then shows the terminal state, and contract-terminal guards any further command.",
    fieldExplanations: [
      {
        field: "recorded_at",
        explanation: "The RFC 3339 UTC instant the termination was recorded.",
      },
      {
        field: "condition",
        explanation:
          "The termination condition — for example principal-requested or validity-expired, from the conditions the contract declared.",
      },
      {
        field: "reason",
        explanation: "The reason recorded alongside the condition — shown verbatim.",
      },
    ],
    relatedConcepts: ["connectivity-contract"],
    relatedErrors: [
      "contract-terminal",
      "invalid-transition",
      "capability-denied",
      "resource-unknown",
      "unknown-contract",
      "idempotency-key-required",
    ],
    nextOperation: "contracts_list",
    userActionable: true,
  },
  {
    operation: "lease_grant",
    purpose:
      "Grant a lease on the contract — a bounded access window over the fulfilled connectivity.",
    prerequisites:
      "The leases:write capability, an active contract, and the window instants.",
    lifecyclePosition: "Operate: consuming the contract — access is granted in windows, not forever.",
    typicalSequence:
      "Once the contract is active, grant a lease for a validity window. Read the lease back (lease_get) and renew it (lease_renew) as the window closes.",
    fieldExplanations: [
      {
        field: "granted_at",
        explanation: "The RFC 3339 UTC instant the grant was recorded.",
      },
      {
        field: "not_before",
        explanation: "The instant the lease window opens.",
      },
      {
        field: "not_after",
        explanation: "The instant the lease window closes.",
      },
    ],
    relatedConcepts: ["connectivity-contract"],
    relatedErrors: [
      "not-yet-valid",
      "expired",
      "temporal-invalid",
      "invalid-transition",
      "capability-denied",
      "resource-unknown",
    ],
    nextOperation: "lease_get",
    userActionable: true,
  },
  {
    operation: "leases_list",
    purpose: "The application's leases, filterable by lease state.",
    prerequisites: "The leases:read capability.",
    lifecyclePosition: "Operate: surveying the granted access windows.",
    typicalSequence:
      "List leases to find windows needing attention, then open one with lease_get.",
    fieldExplanations: [
      {
        field: "request body",
        explanation:
          "Pagination rides the GET request's JSON body — {limit (1..100, default 20), cursor, filters}. No other body members are sent.",
      },
      {
        field: "limit",
        explanation: "Page size, 1 to 100, default 20.",
      },
      {
        field: "cursor",
        explanation: "The opaque pagination cursor carried by the previous response.",
      },
      {
        field: "filters",
        explanation: "Leases filter by state ({state: <lease state>}).",
      },
    ],
    relatedConcepts: ["connectivity-contract"],
    relatedErrors: ["pagination-invalid", "filter-invalid", "capability-denied"],
    nextOperation: "lease_get",
    userActionable: true,
  },
  {
    operation: "lease_get",
    purpose: "One lease resource: its contract, window and state.",
    prerequisites: "The leases:read capability and a lease id.",
    lifecyclePosition: "Operate: inspecting one access window.",
    typicalSequence:
      "Arrive from leases_list or a grant/renewal response. Check the window and state before renewing (lease_renew) or revoking (lease_revoke).",
    fieldExplanations: [
      {
        field: "request body",
        explanation: "None — a bodyless GET. lease_id rides the path.",
      },
      {
        field: "lease_id",
        explanation: "The lease id from leases_list or a grant/renewal response.",
      },
    ],
    relatedConcepts: ["connectivity-contract"],
    relatedErrors: ["resource-unknown", "capability-denied"],
    nextOperation: "lease_renew",
    userActionable: true,
  },
  {
    operation: "lease_renew",
    purpose:
      "Renew a lease for a new validity window — the prior lease enters renewed.",
    prerequisites:
      "The leases:write capability, a renewable lease, and the new window instants.",
    lifecyclePosition: "Operate: keeping access continuous as windows close.",
    typicalSequence:
      "Before not_after passes, POST the new window. The response is the new lease, and the prior lease records the renewed state.",
    fieldExplanations: [
      {
        field: "granted_at",
        explanation: "The RFC 3339 UTC instant the renewal was recorded.",
      },
      {
        field: "not_before",
        explanation: "The instant the new lease window opens.",
      },
      {
        field: "not_after",
        explanation: "The instant the new lease window closes.",
      },
    ],
    relatedConcepts: ["connectivity-contract"],
    relatedErrors: [
      "expired",
      "temporal-invalid",
      "invalid-transition",
      "capability-denied",
      "resource-unknown",
    ],
    nextOperation: "leases_list",
    userActionable: true,
  },
  {
    operation: "lease_revoke",
    purpose: "Revoke a lease — terminal, with a recorded reason.",
    prerequisites: "The leases:write capability and a lease to revoke.",
    lifecyclePosition: "Operate: deliberately ending one access window.",
    typicalSequence:
      "POST the recorded instant and reason. The lease records the revocation reason, and no further commands apply to it.",
    fieldExplanations: [
      {
        field: "recorded_at",
        explanation: "The RFC 3339 UTC instant the revocation was recorded.",
      },
      {
        field: "reason",
        explanation:
          "The recorded reason — for example operator-requested-revocation; shown verbatim.",
      },
    ],
    relatedConcepts: ["connectivity-contract"],
    relatedErrors: ["invalid-transition", "capability-denied", "resource-unknown"],
    nextOperation: "leases_list",
    userActionable: true,
  },
  {
    operation: "endpoints_list",
    purpose: "The application's registered webhook endpoints.",
    prerequisites: "The webhooks:read capability.",
    lifecyclePosition: "Integrate: surveying where events are delivered.",
    typicalSequence:
      "List endpoints to find the one whose deliveries to inspect, then open it with endpoint_get.",
    fieldExplanations: [
      {
        field: "request body",
        explanation:
          "Pagination rides the GET request's JSON body — {limit (1..100, default 20), cursor, filters}. No other body members are sent.",
      },
      {
        field: "limit",
        explanation: "Page size, 1 to 100, default 20.",
      },
      {
        field: "cursor",
        explanation: "The opaque pagination cursor carried by the previous response.",
      },
      {
        field: "filters",
        explanation: "The declared filter members for this list context.",
      },
    ],
    relatedConcepts: ["webhook"],
    relatedErrors: ["pagination-invalid", "capability-denied"],
    nextOperation: "endpoint_get",
    userActionable: true,
  },
  {
    operation: "endpoint_register",
    purpose: "Register a webhook endpoint for observation event types.",
    prerequisites:
      "The webhooks:write capability, an HTTPS URL, and the event types to observe — from the backend's frozen vocabulary.",
    lifecyclePosition: "Integrate: wiring your backend into ADCOS events.",
    typicalSequence:
      "Register the URL and event types; the response carries the endpoint resource with a key id and no secret material. Then watch the delivery attempts (deliveries_list).",
    fieldExplanations: [
      {
        field: "url",
        explanation: "The HTTPS URL events are delivered to.",
      },
      {
        field: "event_types",
        explanation:
          "The observation event types to subscribe to — from the frozen vocabulary (for example connectivity_intent.created, webhook_endpoint.registered).",
      },
    ],
    relatedConcepts: ["webhook", "application-capability"],
    relatedErrors: [
      "invalid-input",
      "secret-rejected",
      "vocabulary",
      "capability-denied",
      "idempotency-key-required",
      "malformed-json",
    ],
    nextOperation: "endpoints_list",
    userActionable: true,
  },
  {
    operation: "endpoint_get",
    purpose: "One webhook endpoint resource: url, event types and key id.",
    prerequisites: "The webhooks:read capability and an endpoint id.",
    lifecyclePosition: "Integrate: verifying one delivery target.",
    typicalSequence:
      "Arrive from endpoints_list. Confirm the URL and event types, then inspect the delivery attempts (deliveries_list).",
    fieldExplanations: [
      {
        field: "request body",
        explanation: "None — a bodyless GET. endpoint_id rides the path.",
      },
      {
        field: "endpoint_id",
        explanation: "The endpoint id from endpoints_list or the registration response.",
      },
    ],
    relatedConcepts: ["webhook"],
    relatedErrors: ["resource-unknown", "capability-denied"],
    nextOperation: "deliveries_list",
    userActionable: true,
  },
  {
    operation: "deliveries_list",
    purpose:
      "The endpoint's delivery attempts — event, status, retries and next-attempt instants.",
    prerequisites: "The webhooks:read capability and an endpoint id.",
    lifecyclePosition: "Integrate / Operate: confirming events actually arrive.",
    typicalSequence:
      "Read after events should have fired. Each record carries the event type and resource, the attempts, the last status and the next attempt instant.",
    fieldExplanations: [
      {
        field: "request body",
        explanation:
          "Pagination rides the GET request's JSON body — {limit (1..100, default 20), cursor, filters}. No other body members are sent.",
      },
      {
        field: "limit",
        explanation: "Page size, 1 to 100, default 20.",
      },
      {
        field: "cursor",
        explanation: "The opaque pagination cursor carried by the previous response.",
      },
      {
        field: "filters",
        explanation: "The declared filter members for this list context.",
      },
    ],
    relatedConcepts: ["webhook"],
    relatedErrors: ["pagination-invalid", "resource-unknown", "capability-denied"],
    userActionable: true,
  },
];

/* ------------------------------------------------------------------ *
 * The module-load guard (duplicated as a test in
 * tests/education-registry.test.ts)
 * ------------------------------------------------------------------ */

/**
 * The coverage registry is the ONLY operation authority: every
 * education record's `operation` must exist there, exactly once. This
 * throws at import time so drift fails before any UI renders.
 */
const COVERAGE_OPERATION_IDS = new Set(COVERAGE.map((record) => record.operation));
const seenOperations = new Set<string>();
for (const entry of OPERATION_EDUCATION) {
  if (seenOperations.has(entry.operation)) {
    throw new Error(
      `education registry duplicates operation "${entry.operation}" — one education record per coverage operation`,
    );
  }
  seenOperations.add(entry.operation);
  if (!COVERAGE_OPERATION_IDS.has(entry.operation)) {
    throw new Error(
      `education registry references unknown operation "${entry.operation}" — the coverage registry is the only operation authority`,
    );
  }
}
