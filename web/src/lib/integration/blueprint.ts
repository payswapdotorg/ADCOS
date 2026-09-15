/**
 * The Build with ADCOS integration registry — the BLUEPRINT builder.
 *
 * The 2026-09-15 program, design §7: the integration blueprint is
 * PRESENTATION STATE, not a new domain authority. This function is pure
 * — no persistence, no side effects, no fabricated credentials or
 * deployment claims: it projects a pattern + the selected capabilities
 * into the on-screen plan the Build UI renders.
 *
 * The no-second-authority rule: `requiredOperationIds` is always a
 * subset of the pattern's own operation set (which the pattern
 * registry's load guard already pins to coverage); unknown capability
 * ids are filtered out, never thrown (the caller may pass anything the
 * UI hands it); `recommendedWebhookEventIds` is derived from the frozen
 * webhook vocabulary (`@/features/developers/webhook-event-types`) via
 * the operation→event map below — an event id can never be invented
 * here because the map's values are load-guarded against the frozen
 * vocabulary.
 */

import { COVERAGE } from "@/lib/api/coverage";
import { WEBHOOK_EVENT_TYPES } from "@/features/developers/webhook-event-types";
import { integrationCapabilityById } from "./capabilities";
import { integrationPatternById } from "./patterns";
import type { IntegrationBlueprint, IntegrationPatternId } from "./types";

/**
 * The canonical lifecycle order every blueprint's operation list is
 * sorted by: identity first (where the pattern includes it), then
 * intent → eligibility observation → offers → contract → referenced
 * terms → assurance → termination → leases → webhook observations,
 * with the platform surfaces last. It enumerates EXACTLY the coverage
 * registry's operations — the load guard below fails loudly if the two
 * sets ever diverge, so a new coverage operation can never silently
 * lack an ordering.
 */
const LIFECYCLE_ORDER: readonly string[] = [
  "application_self",
  "intent_create",
  "intents_list",
  "intent_get",
  "intent_lifecycle",
  "offers_accept",
  "contract_activate",
  "contracts_list",
  "contract_get",
  "contract_usage",
  "contract_assurance",
  "contract_terminate",
  "lease_grant",
  "leases_list",
  "lease_get",
  "lease_renew",
  "lease_revoke",
  "endpoints_list",
  "endpoint_register",
  "endpoint_get",
  "deliveries_list",
  "healthz",
  "readyz",
  "demo_contract_fulfillment",
  "platform_contract_read",
];

/**
 * Which frozen webhook event types are relevant to an operation the
 * pattern actually carries (lifecycle and observation events only).
 * The values are members of the frozen vocabulary — load-guarded below
 * — so a recommendation can never name an event the backend would
 * reject. Operations absent from this map simply recommend nothing.
 */
const OPERATION_WEBHOOK_EVENTS: ReadonlyArray<readonly [string, readonly string[]]> = [
  ["intent_create", ["connectivity_intent.created"]],
  ["intent_lifecycle", ["connectivity_contract.state_changed"]],
  ["offers_accept", ["connectivity_contract.offers_selected"]],
  ["contract_activate", ["connectivity_contract.activated"]],
  ["contracts_list", ["connectivity_contract.state_changed"]],
  ["contract_get", ["connectivity_contract.state_changed"]],
  ["contract_terminate", ["connectivity_contract.terminated"]],
  ["lease_grant", ["connectivity_lease.granted"]],
  ["lease_renew", ["connectivity_lease.renewed"]],
  ["lease_revoke", ["connectivity_lease.revoked"]],
  ["endpoint_register", ["webhook_endpoint.registered"]],
];

/** The standing boundary rules (design §3) every blueprint restates, whatever the pattern. */
const STANDING_BOUNDARY_RULES: readonly string[] = [
  "The ConnectivityContract is the sole durable ADCOS contract authority — never create a second contract authority in the application.",
  "Provider SDK types and provider-native topology must never appear in application-facing integration content or logic.",
  "Webhooks are observations, never canonical business state — reconcile against canonical contract reads.",
  "ADCOS API success is never proof of physical connectivity success.",
  "Software/deployment evidence and physical/network evidence remain distinct evidence classes.",
];

/** The canonical degradation honesty every blueprint restates, whatever the pattern. */
const DEGRADATION_FAILURE_MODES: readonly string[] = [
  "Degradation honesty: when the ADCOS control plane is unreachable, contract reads stay canonical — cache the accepted contract reference, fail explicitly on new control actions, and never fabricate connectivity state.",
  "Canonical reason codes drive retry and repair decisions — preserve them verbatim; unknown codes stay unknown.",
];

function lifecycleRank(operationId: string): number {
  const index = LIFECYCLE_ORDER.indexOf(operationId);
  return index === -1 ? Number.MAX_SAFE_INTEGER : index;
}

/**
 * Order operation ids by the canonical lifecycle order (identity first,
 * then intent → eligibility observation → offers → contract → assurance
 * → leases → webhook observations). Unknown ids sort last,
 * alphabetically. Shared by the blueprint builder and the LLM pack's
 * renderers so both enumerate operations in the SAME canonical order —
 * never two orderings of the same registry.
 */
export function operationsInLifecycleOrder(operationIds: readonly string[]): string[] {
  return [...operationIds].sort(
    (a, b) => lifecycleRank(a) - lifecycleRank(b) || a.localeCompare(b),
  );
}

function eventsForOperation(operationId: string): readonly string[] {
  const entry = OPERATION_WEBHOOK_EVENTS.find(([operation]) => operation === operationId);
  return entry ? entry[1] : [];
}

/**
 * Build the presentation-state blueprint for a pattern and a selection
 * of capability ids. Pure: no persistence, no side effects. Returns
 * `undefined` for an unknown pattern id; unknown capability ids are
 * filtered out (never thrown).
 */
export function buildIntegrationBlueprint(
  patternId: IntegrationPatternId,
  selectedCapabilityIds: string[],
): IntegrationBlueprint | undefined {
  const pattern = integrationPatternById(patternId);
  if (!pattern) return undefined;

  // Unknown capability ids are ignored — the caller's selection is
  // filtered against the capability registry, not validated fatally.
  const selectedCapabilities = selectedCapabilityIds
    .map((id) => integrationCapabilityById(id))
    .filter((capability): capability is NonNullable<typeof capability> => capability !== undefined);

  // (a) the selected capabilities' operation ids, (b) the pattern's
  // lifecycle-essential operation ids — unioned, then intersected with
  // the pattern's own operation set and ordered by the canonical
  // lifecycle order.
  const candidateIds = new Set<string>(pattern.lifecycle.flatMap((step) => (step.operationId ? [step.operationId] : [])));
  for (const capability of selectedCapabilities) {
    for (const operationId of capability.operationIds) {
      candidateIds.add(operationId);
    }
  }
  const requiredOperationIds = operationsInLifecycleOrder(
    pattern.operationIds.filter((operationId) => candidateIds.has(operationId)),
  );

  // Recommended webhook events: derived from the operations the pattern
  // actually carries, ordered by the frozen vocabulary's own order.
  const relevantEvents = WEBHOOK_EVENT_TYPES.filter((event) =>
    pattern.operationIds.some((operationId) => eventsForOperation(operationId).includes(event)),
  );

  // The pattern's anti-patterns restated as boundary rules, plus the
  // standing design-§3 rules.
  const boundaryRules = [
    ...pattern.antiPatterns.map((antiPattern) => `Do not implement: ${antiPattern}.`),
    ...STANDING_BOUNDARY_RULES,
  ];

  const failureModes = [pattern.failureNote, ...DEGRADATION_FAILURE_MODES];

  const firstOperation = requiredOperationIds[0] ?? pattern.operationIds[0] ?? "intent_create";
  const nextSteps = [
    "Read the human Build documentation at /docs — the integration patterns and the production checklist live in the Build with ADCOS section.",
    `Open the first operation's canonical reference at /docs/api/${firstOperation} — method, path, request shape, response anatomy and error codes.`,
    "Execute the operations against the real boundary in the API Explorer at /developers/explorer — no invented endpoints, verbatim reason codes.",
    "Export the machine-readable context for your coding/architect LLM from /build — llms.txt, llms-full.txt, adcos-integration-context.json, adcos-capabilities.json and adcos-operations.json are linked there.",
  ];

  return {
    patternId: pattern.id,
    selectedCapabilityIds: selectedCapabilities.map((capability) => capability.id),
    requiredOperationIds,
    recommendedWebhookEventIds: [...relevantEvents],
    applicationOwnedObjects: [...pattern.applicationOwns],
    adcosOwnedObjects: [...pattern.adcosOwns],
    providerOwnedObjects: [...pattern.providerOwns],
    boundaryRules,
    failureModes,
    nextSteps,
  };
}

/* ------------------------------------------------------------------ *
 * The module-load guard (duplicated as a test in
 * tests/integration-registry.test.ts)
 * ------------------------------------------------------------------ */

/**
 * The derivation tables are pinned to the real registries: the
 * lifecycle order enumerates EXACTLY the coverage registry's
 * operations, every operation→event mapping key is a coverage
 * operation, and every recommended event is a member of the frozen
 * webhook vocabulary. This throws at import time so drift fails before
 * any blueprint renders.
 */
const COVERAGE_OPERATION_IDS = new Set(COVERAGE.map((record) => record.operation));
const WEBHOOK_EVENT_SET = new Set<string>(WEBHOOK_EVENT_TYPES);
if (new Set(LIFECYCLE_ORDER).size !== LIFECYCLE_ORDER.length) {
  throw new Error("the integration blueprint lifecycle order contains duplicate operations");
}
for (const operationId of LIFECYCLE_ORDER) {
  if (!COVERAGE_OPERATION_IDS.has(operationId)) {
    throw new Error(
      `the integration blueprint lifecycle order references unknown operation "${operationId}" — the coverage registry is the only operation authority`,
    );
  }
}
for (const coverageId of COVERAGE_OPERATION_IDS) {
  if (!LIFECYCLE_ORDER.includes(coverageId)) {
    throw new Error(
      `coverage operation "${coverageId}" lacks a lifecycle-order entry — every accepted operation must have one`,
    );
  }
}
for (const [operationId, events] of OPERATION_WEBHOOK_EVENTS) {
  if (!COVERAGE_OPERATION_IDS.has(operationId)) {
    throw new Error(
      `the webhook recommendation map references unknown operation "${operationId}" — the coverage registry is the only operation authority`,
    );
  }
  for (const event of events) {
    if (!WEBHOOK_EVENT_SET.has(event)) {
      throw new Error(
        `the webhook recommendation map references event "${event}" outside the frozen webhook vocabulary`,
      );
    }
  }
}
