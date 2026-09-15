/**
 * The Build with ADCOS integration registry — the typed contracts.
 *
 * The 2026-09-15 program (design §12): ONE canonical integration registry
 * that references the accepted coverage registry (`@/lib/api/coverage`),
 * the education registries (`@/lib/education`), the frozen webhook
 * vocabulary (`@/features/developers/webhook-event-types`) and the
 * canonical reason codes of `@/lib/api/errors` — never a second endpoint
 * catalog. These types are the FROZEN interface contract the Build UI
 * (W2) and the API/LLM education surfaces (W3) code against; the
 * registries themselves live in ./patterns, ./capabilities and
 * ./workflows, and every identifier they carry is machine-checked
 * against the real registries at module load.
 */

/** The five supported integration patterns (design §5) — the pattern id vocabulary. */
export type IntegrationPatternId =
  | "application"
  | "gateway-relay"
  | "fleet-subscriber"
  | "provider-adapter"
  | "marketplace-orchestration";

/**
 * One step of the canonical integration lifecycle (design §4):
 * Connectivity Intent → Eligibility/Policy → Provider Offers →
 * ConnectivityContract → Execution Plan → Provider realization →
 * Evidence + Assurance. The `operationId` (when present) is a real
 * coverage-registry operation id the stage maps onto — a stage that has
 * no operation of its own carries an honest note instead of an invented
 * endpoint.
 */
export interface IntegrationLifecycleStep {
  stage: string;
  operationId?: string;
  note: string;
}

/**
 * One supported integration pattern: what each authority owns, which
 * real operations/concepts/capabilities the pattern is built from, its
 * lifecycle mapping and its honest webhook/failure behavior.
 */
export interface IntegrationPattern {
  id: IntegrationPatternId;
  title: string;
  summary: string;
  applicationOwns: string[];
  adcosOwns: string[];
  providerOwns: string[];
  operationIds: string[];
  conceptIds: string[];
  capabilityIds: string[];
  lifecycle: IntegrationLifecycleStep[];
  webhookNote: string;
  failureNote: string;
  antiPatterns: string[];
}

/**
 * One supported integration capability — an outcome the product can
 * select. Its `operationIds` are coverage-registry operation ids
 * verbatim; a capability never invents an endpoint.
 */
export interface IntegrationCapability {
  id: string;
  title: string;
  description: string;
  operationIds: string[];
}

/**
 * The presentation-state integration blueprint (design §7): a pure
 * projection of the pattern + the selected capabilities. It is NOT a
 * domain authority — nothing is persisted, and every identifier
 * resolves into the canonical operation/education registries.
 */
export interface IntegrationBlueprint {
  patternId: IntegrationPatternId;
  selectedCapabilityIds: string[];
  requiredOperationIds: string[];
  recommendedWebhookEventIds: string[];
  applicationOwnedObjects: string[];
  adcosOwnedObjects: string[];
  providerOwnedObjects: string[];
  boundaryRules: string[];
  failureModes: string[];
  nextSteps: string[];
}
