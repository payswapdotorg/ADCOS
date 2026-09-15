export type IntegrationPatternId =
  | "application"
  | "gateway-relay"
  | "fleet-subscriber"
  | "provider-adapter"
  | "marketplace-orchestration";

export interface IntegrationPattern {
  id: IntegrationPatternId;
  title: string;
  summary: string;
  applicationOwns: string[];
  adcosOwns: string[];
  providerOwns: string[];
  operationIds: string[];
  conceptIds: string[];
  webhookNote: string;
  failureNote: string;
  antiPatterns: string[];
}

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
    webhookNote: "Use signed observations for customer-facing activity feeds, while keeping ADCOS contract reads canonical.",
    failureNote: "Keep payment/commercial semantics separate from connectivity authority; consume referenced terms rather than creating a second connectivity ledger.",
    antiPatterns: ["turning the marketplace into a second connectivity authority", "reinterpreting opaque provider references", "inventing unsupported commercial endpoints"],
  },
];

export function integrationPatternById(id: string): IntegrationPattern | undefined {
  return INTEGRATION_PATTERNS.find((pattern) => pattern.id === id);
}
