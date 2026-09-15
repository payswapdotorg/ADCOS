/**
 * The Build with ADCOS integration registry — the PATTERNS.
 *
 * The 2026-09-15 program, Task 1 of the frozen plan: the five supported
 * integration patterns (design §5) with explicit application/ADCOS/
 * provider ownership, the real operations/concepts/capabilities each
 * pattern is built from, and the design-§4 canonical lifecycle mapping
 * (Connectivity Intent → Eligibility/Policy → Provider Offers →
 * ConnectivityContract → Execution Plan → Provider realization →
 * Evidence + Assurance).
 *
 * The no-second-authority rule: every `operationIds` entry is a real
 * coverage-registry operation id (`@/lib/api/coverage`) verbatim, every
 * `conceptIds` entry belongs to the education concept registry, every
 * `capabilityIds` entry belongs to ./capabilities, and every lifecycle
 * step's `operationId` (when a stage maps onto one) is BOTH in coverage
 * and in that pattern's own operation set. The module-load guard below
 * throws at import time on any drift — this file can never quietly
 * become a second endpoint catalog. Stages with no operation of their
 * own (Execution Plan, Provider realization, and Eligibility/Policy on
 * patterns without intent_lifecycle) carry an honest note instead of an
 * invented endpoint.
 */

import { COVERAGE } from "@/lib/api/coverage";
import { CONCEPTS } from "@/lib/education/concepts";
import { INTEGRATION_CAPABILITIES } from "./capabilities";
import type { IntegrationPattern, IntegrationPatternId } from "./types";

// The typed contracts live in ./types (the frozen interface contract);
// re-exported here so existing `@/lib/integration/patterns` consumers
// (the Build UI) keep resolving them from this module.
export type { IntegrationPattern, IntegrationPatternId } from "./types";

/** The pattern registry — the console's integration-pattern authority. */
export const INTEGRATION_PATTERNS: IntegrationPattern[] = [
  {
    id: "application",
    title: "Application consumes connectivity",
    summary: "Your application asks ADCOS for a technology-neutral connectivity outcome and operates from the resulting contract and observations.",
    applicationOwns: ["product domain", "user/device context", "application UX"],
    adcosOwns: ["connectivity intent", "contract lifecycle", "fulfillment orchestration"],
    providerOwns: ["provider realization", "provider-native topology", "routing and subscriber authority"],
    operationIds: ["application_self", "intent_create", "intent_lifecycle", "offers_accept", "contract_activate", "contract_get", "contract_assurance"],
    conceptIds: ["application-capability", "connectivity-contract", "eligibility", "execution-plan", "fulfillment", "assurance"],
    capabilityIds: ["application-connectivity"],
    lifecycle: [
      {
        stage: "Connectivity Intent",
        operationId: "intent_create",
        note: "Record the technology-neutral connectivity requirement — requirements, hard constraints, validity, termination and referenced terms. The principal is derived from the authenticated application.",
      },
      {
        stage: "Eligibility / Policy",
        operationId: "intent_lifecycle",
        note: "ADCOS evaluates the accepted policy/eligibility path internally; the lifecycle observation surfaces the resulting statements. The application consumes them — it never reimplements the policy engine.",
      },
      {
        stage: "Provider Offers",
        operationId: "offers_accept",
        note: "Accept the opaque typed offer references onto the intent (OFFER_SELECTED). Offers stay opaque: the application never interprets provider-internal semantics.",
      },
      {
        stage: "ConnectivityContract",
        operationId: "contract_activate",
        note: "Activate the contract — from here the ConnectivityContract is the sole durable contract authority for this connectivity.",
      },
      {
        stage: "Execution Plan",
        note: "ADCOS composes the accepted offers into an execution plan and references it against the contract. No separate plan operation exists on the developer boundary — read the contract for the referenced execution material.",
      },
      {
        stage: "Provider realization",
        note: "Realization happens provider-side behind the ADCOS adapter. The application observes execution status through lifecycle reads; provider internals never cross the boundary.",
      },
      {
        stage: "Evidence + Assurance",
        operationId: "contract_assurance",
        note: "Read the referenced assurance obligations. Evidence and assurance are referenced, never fabricated — software evidence and physical/network evidence stay distinct.",
      },
    ],
    webhookNote: "Use signed webhook observations for asynchronous lifecycle awareness; never replace canonical contract reads with webhook state.",
    failureNote: "Treat canonical reason codes as the source for retry/repair decisions; do not infer physical connectivity success from an HTTP success.",
    antiPatterns: ["second connectivity contract database", "provider SDK in product domain", "API success treated as physical proof"],
  },
  {
    id: "gateway-relay",
    title: "Gateway / relay platform",
    summary: "Use ADCOS for gateway or relay connectivity while your platform retains control of its own application and data plane.",
    applicationOwns: ["gateway/relay identity", "content/data plane", "local/offline behavior", "application economics"],
    adcosOwns: ["gateway connectivity requirement", "contract", "provider orchestration", "assurance references"],
    providerOwns: ["access realization", "network topology", "provider routing"],
    operationIds: ["application_self", "intent_create", "intent_lifecycle", "offers_accept", "contract_activate", "contract_get", "contract_assurance", "contracts_list"],
    conceptIds: ["connectivity-contract", "provider-capability", "offer", "execution-plan", "fulfillment", "assurance"],
    capabilityIds: ["application-connectivity"],
    lifecycle: [
      {
        stage: "Connectivity Intent",
        operationId: "intent_create",
        note: "Record the technology-neutral gateway/relay connectivity requirement. The requirement describes the backhaul outcome needed — never the platform's internal content/data routing.",
      },
      {
        stage: "Eligibility / Policy",
        operationId: "intent_lifecycle",
        note: "ADCOS evaluates the accepted policy/eligibility path internally; the lifecycle observation surfaces the resulting statements for the gateway controller to consume.",
      },
      {
        stage: "Provider Offers",
        operationId: "offers_accept",
        note: "Accept the opaque typed offer references onto the intent (OFFER_SELECTED). Provider-internal access technology never crosses into the platform's domain.",
      },
      {
        stage: "ConnectivityContract",
        operationId: "contract_activate",
        note: "Activate the contract. The gateway/relay connectivity outcome is now governed by the ConnectivityContract — the platform's local data plane remains its own authority.",
      },
      {
        stage: "Execution Plan",
        note: "ADCOS composes the accepted offers into an execution plan and references it against the contract. No separate plan operation exists on the developer boundary.",
      },
      {
        stage: "Provider realization",
        note: "Access realization happens provider-side behind the ADCOS adapter; the platform observes execution status, never provider topology. Local/P2P transfers never route through ADCOS merely because backhaul does.",
      },
      {
        stage: "Evidence + Assurance",
        operationId: "contract_assurance",
        note: "Read the referenced assurance obligations; contracts_list tracks the platform's backhaul contracts. Evidence is referenced, never fabricated.",
      },
    ],
    webhookNote: "Subscribe to lifecycle observations that matter to the gateway controller; keep the local data plane independent where the product is designed to operate offline.",
    failureNote: "ADCOS reachability can degrade without invalidating already-local application behavior. Cache the accepted contract reference and fail explicitly when new connectivity control actions cannot be submitted.",
    antiPatterns: ["route every local P2P transfer through ADCOS", "make local content availability depend on the ADCOS API", "import provider-native transport APIs into the core domain"],
  },
  {
    id: "fleet-subscriber",
    title: "Fleet / subscriber connectivity",
    summary: "Allocate connectivity for a device or subscriber cohort without taking provider-native subscriber authority into your product domain.",
    applicationOwns: ["cohort membership", "product policy", "device/user context"],
    adcosOwns: ["connectivity intent and contract", "offer acceptance", "contract/lease lifecycle"],
    providerOwns: ["subscriber/network realization", "provider-native identity and routing"],
    operationIds: ["application_self", "intent_create", "offers_accept", "contract_activate", "contracts_list", "contract_get", "lease_grant", "leases_list", "lease_renew", "lease_revoke"],
    conceptIds: ["application-capability", "connectivity-contract", "offer", "policy"],
    capabilityIds: ["application-connectivity", "leases"],
    lifecycle: [
      {
        stage: "Connectivity Intent",
        operationId: "intent_create",
        note: "Record the technology-neutral connectivity requirement for the device or subscriber cohort — beneficiaries ride the intent; cohort membership itself stays application-owned.",
      },
      {
        stage: "Eligibility / Policy",
        note: "Policy and eligibility are evaluated inside ADCOS; this pattern observes the outcome through the contract state machine rather than a dedicated lifecycle operation.",
      },
      {
        stage: "Provider Offers",
        operationId: "offers_accept",
        note: "Accept the opaque typed offer references onto the intent (OFFER_SELECTED). Provider subscriber/network mechanics never enter the product domain.",
      },
      {
        stage: "ConnectivityContract",
        operationId: "contract_activate",
        note: "Activate the contract — ADCOS owns the contract and bounded lease lifecycle from here.",
      },
      {
        stage: "Execution Plan",
        note: "ADCOS composes the accepted offers into an execution plan and references it against the contract. No separate plan operation exists on the developer boundary.",
      },
      {
        stage: "Provider realization",
        note: "Subscriber and network realization stay provider-owned; the application sees contract and lease state only — never provider-native identity or routing.",
      },
      {
        stage: "Evidence + Assurance",
        note: "Assurance obligations are referenced at intent creation and read back through the canonical contract material; bounded leases (grant/renew/revoke) carry the cohort's validity windows.",
      },
    ],
    webhookNote: "Use observation events to reconcile application views; contract reads remain canonical.",
    failureNote: "Handle capability-denied, invalid-transition and contract-terminal failures explicitly before retrying mutations.",
    antiPatterns: ["provider-specific subscriber database as the contract authority", "implicit contract mutation from webhook receipt"],
  },
  {
    id: "provider-adapter",
    title: "Provider / adapter integration",
    summary: "Expose provider capabilities through the ADCOS adapter boundary while keeping topology and routing authority with the provider.",
    applicationOwns: ["consumer product requirements"],
    adcosOwns: ["capability exchange", "contract orchestration", "adapter boundary"],
    providerOwns: ["provider APIs", "topology", "routing", "subscriber/network operations"],
    operationIds: ["intent_create", "offers_accept", "contract_activate", "contract_get", "contract_assurance"],
    conceptIds: ["provider-capability", "provider-adapter-boundary", "offer", "execution-plan"],
    capabilityIds: ["application-connectivity"],
    lifecycle: [
      {
        stage: "Connectivity Intent",
        operationId: "intent_create",
        note: "A consuming application records its technology-neutral requirement; the adapter side never writes provider-specific technology into the intent.",
      },
      {
        stage: "Eligibility / Policy",
        note: "Policy and eligibility are evaluated inside ADCOS behind the adapter boundary — provider authorization is translated into ADCOS outcomes, never exported.",
      },
      {
        stage: "Provider Offers",
        operationId: "offers_accept",
        note: "Provider capabilities enter as opaque typed offer references (OFFER_SELECTED) — the consumer sees technology-neutral offers, not provider APIs.",
      },
      {
        stage: "ConnectivityContract",
        operationId: "contract_activate",
        note: "Activate the contract — the exchange/orchestration authority over this connectivity outcome.",
      },
      {
        stage: "Execution Plan",
        note: "ADCOS composes accepted offers into an execution plan; the adapter translates provider-native realization into ADCOS typed execution material without exposing a global topology model.",
      },
      {
        stage: "Provider realization",
        note: "Realization runs on the provider's own network and APIs, entirely behind the ADCOS adapter boundary.",
      },
      {
        stage: "Evidence + Assurance",
        operationId: "contract_assurance",
        note: "Read the referenced assurance obligations. Provider realization failures surface as typed ADCOS outcomes — never as leaked provider SDK types.",
      },
    ],
    webhookNote: "The developer boundary exposes observations; provider internals remain behind the adapter.",
    failureNote: "Surface provider realization failures as typed ADCOS outcomes; never leak provider SDK types into the application-facing API.",
    antiPatterns: ["provider-specific API in consumer code", "global ADCOS topology graph", "second provider-selection authority"],
  },
  {
    id: "marketplace-orchestration",
    title: "Connectivity marketplace / orchestration",
    summary: "Build a higher-level product around connectivity outcomes while ADCOS remains the contract and orchestration authority.",
    applicationOwns: ["commercial/product experience", "customer context", "marketplace UX"],
    adcosOwns: ["technology-neutral contract", "offer references", "fulfillment", "assurance references"],
    providerOwns: ["provider capability and realization"],
    operationIds: ["application_self", "intent_create", "intents_list", "offers_accept", "contract_activate", "contracts_list", "contract_get", "contract_usage", "contract_assurance", "contract_terminate", "endpoint_register"],
    conceptIds: ["connectivity-contract", "offer", "policy", "execution-plan", "assurance", "webhook"],
    capabilityIds: ["application-connectivity", "webhook-observations"],
    lifecycle: [
      {
        stage: "Connectivity Intent",
        operationId: "intent_create",
        note: "Record the customer's technology-neutral connectivity requirement; commercial semantics stay in the marketplace, connectivity semantics in the intent.",
      },
      {
        stage: "Eligibility / Policy",
        note: "Policy and eligibility are evaluated inside ADCOS; the marketplace observes the outcome through the contract state machine and the intent list (intents_list) rather than reimplementing the policy engine.",
      },
      {
        stage: "Provider Offers",
        operationId: "offers_accept",
        note: "Accept the opaque typed offer references onto the intent (OFFER_SELECTED); opaque references are preserved verbatim, never reinterpreted.",
      },
      {
        stage: "ConnectivityContract",
        operationId: "contract_activate",
        note: "Activate the contract — ADCOS remains the connectivity contract authority; the marketplace never becomes a second connectivity ledger.",
      },
      {
        stage: "Execution Plan",
        note: "ADCOS composes the accepted offers into an execution plan and references it against the contract. No separate plan operation exists on the developer boundary.",
      },
      {
        stage: "Provider realization",
        note: "Provider capability and realization stay provider-owned; the marketplace consumes referenced usage and assurance material (contract_usage, contract_assurance), never provider internals.",
      },
      {
        stage: "Evidence + Assurance",
        operationId: "contract_assurance",
        note: "Read the referenced assurance obligations; endpoint_register subscribes signed observations for customer-facing activity feeds while contract reads stay canonical. contract_terminate ends the lifecycle when a customer cancels.",
      },
    ],
    webhookNote: "Use signed observations for customer-facing activity feeds, while keeping ADCOS contract reads canonical.",
    failureNote: "Keep payment/commercial semantics separate from connectivity authority; consume referenced terms rather than creating a second connectivity ledger.",
    antiPatterns: ["turning the marketplace into a second connectivity authority", "reinterpreting opaque provider references", "inventing unsupported commercial endpoints"],
  },
];

export function integrationPatternById(id: string): IntegrationPattern | undefined {
  return INTEGRATION_PATTERNS.find((pattern) => pattern.id === id);
}

/** Every pattern whose operation set includes the operation (derived, never hand-maintained). */
export function patternsUsingOperation(operationId: string): IntegrationPattern[] {
  return INTEGRATION_PATTERNS.filter((pattern) => pattern.operationIds.includes(operationId));
}

/* ------------------------------------------------------------------ *
 * The module-load guard (duplicated as a test in
 * tests/integration-registry.test.ts)
 * ------------------------------------------------------------------ */

/**
 * The real registries are the ONLY authorities here: every operation id
 * must exist in coverage, every concept id in the education concept
 * registry, every capability id in ./capabilities, every lifecycle
 * operation in coverage AND in its own pattern's operation set, and no
 * ownership string may appear under two authorities at once. This
 * throws at import time so drift fails before any UI renders.
 */
const COVERAGE_OPERATION_IDS = new Set<string>(COVERAGE.map((record) => record.operation));
const CONCEPT_IDS = new Set<string>(CONCEPTS.map((concept) => concept.id));
const CAPABILITY_IDS = new Set(INTEGRATION_CAPABILITIES.map((capability) => capability.id));
const seenPatternIds = new Set<string>();
for (const pattern of INTEGRATION_PATTERNS) {
  if (seenPatternIds.has(pattern.id)) {
    throw new Error(
      `integration pattern registry duplicates id "${pattern.id}" — one record per pattern`,
    );
  }
  seenPatternIds.add(pattern.id);
  for (const operationId of pattern.operationIds) {
    if (!COVERAGE_OPERATION_IDS.has(operationId)) {
      throw new Error(
        `integration pattern "${pattern.id}" references unknown operation "${operationId}" — the coverage registry is the only operation authority`,
      );
    }
  }
  for (const conceptId of pattern.conceptIds) {
    if (!CONCEPT_IDS.has(conceptId)) {
      throw new Error(
        `integration pattern "${pattern.id}" references unknown concept "${conceptId}" — the education concept registry is the only concept authority`,
      );
    }
  }
  for (const capabilityId of pattern.capabilityIds) {
    if (!CAPABILITY_IDS.has(capabilityId)) {
      throw new Error(
        `integration pattern "${pattern.id}" references unknown capability "${capabilityId}" — the integration capability registry is the only capability authority`,
      );
    }
  }
  for (const step of pattern.lifecycle) {
    if (step.operationId !== undefined) {
      if (!COVERAGE_OPERATION_IDS.has(step.operationId)) {
        throw new Error(
          `integration pattern "${pattern.id}" lifecycle stage "${step.stage}" references unknown operation "${step.operationId}"`,
        );
      }
      if (!pattern.operationIds.includes(step.operationId)) {
        throw new Error(
          `integration pattern "${pattern.id}" lifecycle stage "${step.stage}" maps to operation "${step.operationId}" outside the pattern's own operation set`,
        );
      }
    }
  }
  // Contradictory ownership: the same string under two authorities is a
  // boundary contradiction, not a shared responsibility.
  const ownershipLists: [string, string[]][] = [
    ["applicationOwns", pattern.applicationOwns],
    ["adcosOwns", pattern.adcosOwns],
    ["providerOwns", pattern.providerOwns],
  ];
  for (let i = 0; i < ownershipLists.length; i += 1) {
    for (let j = i + 1; j < ownershipLists.length; j += 1) {
      const [nameA, listA] = ownershipLists[i];
      const [nameB, listB] = ownershipLists[j];
      const clash = listA.find((entry) => listB.includes(entry));
      if (clash !== undefined) {
        throw new Error(
          `integration pattern "${pattern.id}" lists "${clash}" under both ${nameA} and ${nameB} — ownership is exclusive`,
        );
      }
    }
  }
}
