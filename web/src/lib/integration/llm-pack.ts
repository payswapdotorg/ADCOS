/**
 * The Build with ADCOS LLM Integration Pack — THE ANTI-DRIFT CORE.
 *
 * The 2026-09-15 program, Task 2 of the frozen plan (design §9/§10/§11):
 * the canonical machine-readable LLM context, the per-operation
 * projection, and the renderers for the five PUBLIC assets
 * (`/llms.txt`, `/llms-full.txt`, `/adcos-integration-context.json`,
 * `/adcos-capabilities.json`, `/adcos-operations.json`). The operator's
 * hand-authored first assets are PORTED here — their prose is the
 * canonical starting content, preserved in meaning and honesty — and
 * the public files are now GENERATED artifacts of this module: every
 * enumeration of operations, patterns, capabilities, lifecycle stages,
 * webhook event types or reason codes is DERIVED from the real
 * registries at render time, never hand-maintained.
 *
 * The no-second-authority rule (design §12): operation ids come ONLY
 * from `@/lib/api/coverage` (all of them — the operator's static
 * operations file listed fewer; derivation is the point), concept ids
 * from the education registry, capability ids from ./capabilities,
 * webhook event ids from the frozen vocabulary, and reason codes from
 * the canonical error taxonomy. The module-load guards below throw at
 * import time on any drift. Provider SDK types/names never appear in
 * application-facing content; software evidence and physical/network
 * evidence stay distinct; API success is never stated as physical
 * connectivity success.
 */

import { COVERAGE, coverageByOperation } from "@/lib/api/coverage";
import { CONCEPTS } from "@/lib/education/concepts";
import { OPERATION_EDUCATION } from "@/lib/education/operations";
import type { OperationLearningDefinition } from "@/lib/education/types";
import { WEBHOOK_EVENT_TYPES } from "@/features/developers/webhook-event-types";
import { operationsInLifecycleOrder } from "./blueprint";
import { INTEGRATION_CAPABILITIES } from "./capabilities";
import { INTEGRATION_PATTERNS } from "./patterns";
import { INTEGRATION_WORKFLOWS } from "./workflows";
import type { IntegrationPatternId } from "./types";

/* ------------------------------------------------------------------ *
 * The ported operator content (llms-full.txt + adcos-integration-
 * context.json) — the canonical starting prose, preserved exactly in
 * meaning and honesty. Registry-derived data is injected only where
 * the operator's files enumerated operations / patterns / lifecycle.
 * ------------------------------------------------------------------ */

/** The mission section (llms-full.txt §Mission + the context.json product object). */
const MISSION = {
  name: "ADCOS",
  statement:
    "ADCOS is an Adaptive Distributed Connectivity Operating System and programmable connectivity exchange/orchestration layer.",
  product_promise: "One connectivity contract, many networks, continuous fulfillment.",
  composition_rule:
    "ADCOS composes heterogeneous provider capabilities without taking ownership of provider-native radio/core/topology/routing authority.",
  audience:
    "Both human developers and coding/architect LLMs can integrate ADCOS from this context without access to internal architecture documents or conversation history.",
  published_assets: {
    llms_txt: "/llms.txt",
    llms_full_txt: "/llms-full.txt",
    integration_context: "/adcos-integration-context.json",
    capabilities: "/adcos-capabilities.json",
    operations: "/adcos-operations.json",
    human_entry: "/build",
    human_docs: "/docs",
    api_explorer: "/developers/explorer",
  },
} as const;

/** The mental-model paragraph and lifecycle stages (llms-full.txt §The mental model). */
const MENTAL_MODEL_DESCRIPTION =
  "A consuming application describes the connectivity outcome it needs. ADCOS records that requirement as a canonical connectivity intent/contract, evaluates the accepted policy/eligibility path, composes provider offers into an execution plan, and continuously observes fulfillment with evidence and assurance references.";

/** The mental-model diagram (llms-full.txt, verbatim). */
const MENTAL_MODEL_DIAGRAM = `Application
  ↓ technology-neutral requirement
Connectivity Intent
  ↓
Eligibility / Policy
  ↓
Provider Offers
  ↓
ConnectivityContract
  ↓
Execution Plan
  ↓
Provider realization
  ↓
Evidence + Assurance
  ↓
Continuous fulfillment / observation`;

/** The authority-model notes (llms-full.txt §Authority model, verbatim). */
const AUTHORITY_MODEL = {
  application:
    "The application owns its product domain, customer/user context, device context, content, product UX, application economics and domain-specific data-plane semantics.",
  adcos:
    "ADCOS owns the durable connectivity contract lifecycle and connectivity exchange/orchestration: recording intent, accepting typed offer references, activation/termination, bounded leases, execution/assurance references and developer-facing lifecycle observation.",
  provider:
    "Providers retain provider-native topology, routing, subscriber authority, physical network realization and provider APIs. Those details belong behind ADCOS adapters, not in consuming product domains.",
} as const;

/** The authority-boundary lists (adcos-integration-context.json, verbatim). */
const AUTHORITY_BOUNDARY_LISTS = {
  application: [
    "product domain",
    "user/device context",
    "application UX",
    "content/data plane",
    "application economics",
  ],
  adcos: [
    "connectivity intent",
    "ConnectivityContract lifecycle",
    "offer acceptance as typed references",
    "execution/assurance references",
    "bounded leases",
    "developer API boundary",
  ],
  provider: [
    "provider-native topology",
    "routing",
    "subscriber authority",
    "physical/network realization",
    "provider APIs",
  ],
} as const;

/** The rules every integration must preserve (llms-full.txt, verbatim). */
const INTEGRATION_RULES: readonly string[] = [
  "Never build a second connectivity-contract authority.",
  "Never create a second offer/provider-selection authority inside the application.",
  "Request connectivity outcomes rather than provider technology.",
  "Do not encode `provider X`, `wlan0`, `gNB`, tunnel implementation or equivalent provider internals into the application contract.",
  "Browser and application examples use the canonical HTTP developer boundary only.",
  "Webhooks are observations. They do not replace canonical contract reads.",
  "API success is not proof of physical connectivity success.",
  "Software/deployment evidence and physical/network evidence are different evidence classes.",
  "Preserve canonical ADCOS reason codes.",
  "Respect API versioning and compatibility rules.",
  "Use mutation/idempotency semantics exactly as defined by the API.",
  "Do not invent endpoints, provider capabilities or telemetry.",
  "Do not create a global provider topology graph in an application.",
  "A product can keep operating its own local/data plane when ADCOS is unavailable if its business design permits it; ADCOS reachability should not silently become a dependency of unrelated local behavior.",
];

/** The absolute rules (adcos-integration-context.json, verbatim). */
const ABSOLUTE_RULES: readonly string[] = [
  "ConnectivityContract is the sole durable ADCOS connectivity-contract authority.",
  "Applications consume technology-neutral connectivity outcomes, not provider-native topology or APIs.",
  "Provider-native topology, routing and subscriber authority remain provider-owned.",
  "Webhooks are observations, not canonical business state.",
  "API success is not physical connectivity proof.",
  "Software evidence and physical/network evidence remain distinct.",
  "Preserve canonical reason codes.",
  "Do not invent unsupported endpoints, capabilities or telemetry.",
  "Do not expose secrets in public documentation or LLM context.",
  "Use the published operation registry as the current API surface and preserve API-version rules.",
];

/** The per-pattern primary rules (adcos-integration-context.json, verbatim). */
const PATTERN_PRIMARY_RULES: Record<IntegrationPatternId, string> = {
  application:
    "Request technology-neutral connectivity outcomes; keep product authority in the application.",
  "gateway-relay":
    "Use ADCOS for gateway/backhaul connectivity while keeping the product's local/data plane independent.",
  "fleet-subscriber":
    "ADCOS owns connectivity contract/lease lifecycle; the application owns cohort semantics.",
  "provider-adapter":
    "Keep provider SDKs and topology behind the ADCOS adapter boundary.",
  "marketplace-orchestration":
    "Build commercial/product UX around ADCOS without creating a second connectivity authority.",
};

/** The pattern prose (llms-full.txt §Integration patterns, verbatim). */
const PATTERN_PROSE: Record<IntegrationPatternId, string> = {
  application:
    "Use when an application needs connectivity for itself, a service endpoint or a bounded cohort.\n\nThe application owns product behavior. ADCOS owns connectivity contract state. Providers own realization.",
  "gateway-relay":
    "Use when a platform has its own application/data plane and needs backhaul or gateway/relay connectivity.\n\nImportant design rule: ADCOS manages the gateway/relay connectivity outcome, not the application's internal content/data routing. A local or P2P transfer inside the platform does not become an ADCOS connectivity transaction simply because ADCOS provides backhaul connectivity.",
  "fleet-subscriber":
    "Use when a product purchases/allocates connectivity for devices or subscribers. The product retains cohort membership and business semantics; ADCOS owns the connectivity contract and bounded lease lifecycle; provider subscriber/network mechanics remain provider-owned.",
  "provider-adapter":
    "Use when a network provider exposes capabilities to ADCOS. Provider SDK/API objects stay behind the adapter. Consuming applications see technology-neutral offers and contract/execution outcomes.",
  "marketplace-orchestration":
    "A higher-level marketplace may own commercial UX and customer context while delegating actual connectivity orchestration to ADCOS. Do not turn the marketplace into a second connectivity ledger or reinterpret opaque provider references.",
};

/** The API-model prose (llms-full.txt §API model — the grouping text is operator prose; the operation list below is derived). */
const API_MODEL_PROSE = {
  boundary_includes:
    "The public boundary includes operations for:\n- application identity/capabilities\n- connectivity intent creation/list/get/lifecycle\n- offer acceptance\n- contract activation/list/get/usage/assurance/termination\n- lease grant/list/get/renew/revoke\n- webhook endpoint registration/list/get/deliveries",
  authoritative_list:
    "The console coverage registry is the authoritative list of executable developer operations. Use /adcos-operations.json for the current published projection.",
  mutation_rule:
    "Mutations require the capabilities and idempotency semantics defined by the API. Do not create client-side business rules that silently weaken hard contract constraints.",
} as const;

/** The object semantics (llms-full.txt §Object semantics, verbatim). */
const OBJECT_SEMANTICS: ReadonlyArray<readonly [string, string]> = [
  [
    "ConnectivityContract",
    "The canonical durable record of the connectivity an application asks ADCOS to continuously fulfill. Requirements and hard constraints are part of the canonical material. Plans, execution artifacts, evidence and assurance are referenced against the contract.",
  ],
  [
    "Offer",
    "Opaque typed provider offer reference. The consuming application should preserve its declared structure and provenance; it should not reinterpret provider-internal semantics.",
  ],
  [
    "Eligibility / Policy",
    "Reasoning and authorization that determine which lifecycle operations are admitted. The application consumes backend statements/reason codes rather than reimplementing the policy engine in frontend code.",
  ],
  [
    "Execution plan",
    "Composition of provider capabilities that realizes the accepted contract. Replanning must preserve hard contract constraints.",
  ],
  [
    "Fulfillment",
    "The continuous process of honoring an active contract. Operational observation reports execution state; it does not automatically prove physical success.",
  ],
  [
    "Evidence / Assurance",
    "Evidence records support statements about what happened and where it came from. Assurance obligations describe what should hold for a contract to count as assured. Do not turn software deployment evidence into physical-network proof.",
  ],
  [
    "Lease",
    "A bounded validity window over a contract. Lease mutations are separate lifecycle operations and should not be confused with creating a new connectivity authority.",
  ],
  [
    "Webhook",
    "Signed observation delivery. Use it to react asynchronously, but maintain canonical state from authoritative API reads.",
  ],
];

/** The error-handling steps (llms-full.txt §Error handling, verbatim). */
const ERROR_HANDLING_STEPS: readonly string[] = [
  "Preserve the exact backend reason code.",
  "Identify the affected resource.",
  "Determine whether the error is retryable according to API metadata.",
  "Read the canonical resource before issuing a state-dependent retry.",
  "Never hide an unavailable deployment capability behind a fake result.",
];

const ERROR_UNKNOWN_RULE =
  "Unknown reason codes must remain unknown; the client must not invent semantics.";

/**
 * The canonical reason-code vocabulary — the FROZEN PIN, transcribed
 * verbatim from the console error taxonomy (`@/lib/api/errors`' private
 * REASON_PRESENTATION map — the only error vocabulary the console
 * displays; the same pin the errors documentation page and the
 * education-registry tests carry). Codes are ids, never synonyms; the
 * module-load guard below fails loudly if any education record's
 * relatedErrors falls outside this pin.
 */
const CANONICAL_REASON_CODES: readonly string[] = [
  "authentication-invalid",
  "authentication-expired",
  "environment-mismatch",
  "capability-denied",
  "version-unsupported",
  "rate-limited",
  "idempotency-key-required",
  "idempotency-conflict",
  "pagination-invalid",
  "filter-invalid",
  "resource-unknown",
  "route-unknown",
  "invalid-input",
  "invalid-transition",
  "invalid-state",
  "unknown-contract",
  "contract-terminal",
  "constraint-immutable",
  "not-yet-valid",
  "expired",
  "temporal-invalid",
  "secret-rejected",
  "vocabulary",
  "sequence-conflict",
  "replay-stale",
  "journal-tamper",
  "store-failed",
  "payload-too-large",
  "malformed-json",
  "invalid-request-body",
  "backend-unreachable",
  "internal-error",
];

/** The versioning rule (llms-full.txt §Versioning, verbatim). */
const VERSIONING = {
  rule: "The API uses explicit versioning. Route version and X-ADCOS-API-Version must agree.",
  compatibility:
    "Compatible versions allow additive optional fields; breaking field changes require a new major version. Consumers must not depend on deprecated/retired behavior as if it were current.",
} as const;

/** The security rules (llms-full.txt §Security and secrets + design §3, verbatim). */
const SECURITY_RULES = {
  secrets:
    "Never place API credentials or webhook signing secrets into public docs, examples, browser local storage, or LLM context assets. Public examples may show header names and synthetic non-secret placeholders only.",
  boundary: "Browser and application examples use the canonical HTTP developer boundary only.",
  provider_isolation:
    "Provider SDKs and provider-native network objects must never appear in application-facing integration examples.",
} as const;

/** The evidence rules (llms-full.txt rules 7-8 + object semantics, verbatim in meaning). */
const EVIDENCE_RULES = {
  api_success: "ADCOS API success is never represented as proof of physical connectivity success.",
  evidence_classes:
    "Software/deployment evidence and physical/network evidence are different evidence classes; never turn software deployment evidence into physical-network proof.",
  evidence_semantics:
    "Evidence records support statements about what happened and where it came from. Assurance obligations describe what should hold for a contract to count as assured.",
  fulfillment_observation:
    "Operational observation reports execution state; it does not automatically prove physical success.",
} as const;

/** The 11 LLM safety / anti-drift rules (design §11, verbatim). */
const LLM_SAFETY_RULES: readonly string[] = [
  "Do not create a second contract authority.",
  "Do not encode provider-specific topology into application domain logic.",
  "Do not treat webhook observations as canonical state.",
  "Do not equate API success with physical connectivity success.",
  "Do not invent unavailable endpoints.",
  "Do not invent provider capabilities.",
  "Do not make application data-plane availability depend on ADCOS control-plane availability unless the product explicitly chooses that tradeoff.",
  "Preserve canonical reason codes.",
  "Preserve API version and compatibility rules.",
  "Use idempotency and declared request semantics as defined by the API.",
  "Distinguish software evidence from physical/network evidence.",
];

/** The never-list (llms-full.txt §Anti-patterns, verbatim). */
const ANTI_PATTERN_NEVER_LIST: readonly string[] = [
  "add `AdcosContract` as a second source of truth for connectivity contracts;",
  "copy ADCOS contract state into a second mutable ledger and let both authorities change it;",
  "make an app call provider APIs directly for the same capability ADCOS is orchestrating;",
  "interpret webhooks as authoritative state mutations without a canonical read;",
  "claim physical availability based only on an API 2xx response;",
  "build a global ADCOS topology map from provider data;",
  "invent an endpoint because the product story seems to require one;",
  "use a fake provider/network result in a production-status surface;",
  "route every local/P2P ShareNet data transfer through ADCOS;",
  "expose public secrets in generated LLM context.",
];

/** The production checklist (llms-full.txt §Production checklist, verbatim). */
const PRODUCTION_CHECKLIST: readonly string[] = [
  "Application identity and required capability grants are understood.",
  "API version is explicit and route/header versions agree.",
  "Mutations use required idempotency semantics.",
  "Contract hard constraints are treated as immutable after creation.",
  "Error handling preserves canonical reason codes.",
  "Webhook signature verification and replay protections are implemented where webhooks are used.",
  "Provider implementation is isolated behind the appropriate ADCOS boundary.",
  "Software vs physical/network evidence is represented honestly.",
  "Degraded ADCOS control-plane behavior is explicit.",
  "No second connectivity contract authority exists.",
  "No provider-native APIs leak into the product domain.",
  "The integration has been tested through the actual ADCOS HTTP boundary.",
];

/** The LLM implementation workflow (llms-full.txt §LLM implementation workflow, verbatim). */
const LLM_IMPLEMENTATION_WORKFLOW: readonly string[] = [
  "Identify the product's connectivity outcome and integration pattern.",
  "Mark application/ADCOS/provider authorities explicitly.",
  "Choose only capabilities and operations present in the published registry.",
  "Define the application-side connectivity port/client.",
  "Map the product lifecycle to the ADCOS contract lifecycle.",
  "Add webhook observations only where asynchronous awareness is needed.",
  "Keep ADCOS control-plane failures separate from unrelated product/data-plane behavior.",
  "Implement typed error handling and idempotent mutations.",
  "Preserve hard constraints exactly.",
  "Test provider-independence and authority boundaries.",
  "Validate examples against the live Developer API/Explorer before claiming integration completeness.",
];

/** The provider adapter rule (llms-full.txt §Provider adapter rule, verbatim). */
const PROVIDER_ADAPTER_RULE =
  "A provider adapter is an ADCOS integration boundary. It may translate provider-native capability/realization details into ADCOS typed capability/offer/execution material. That translation must not become a globally visible provider-topology model.";

/** The ShareNet reference (design §13 + llms-full.txt §ShareNet reference architecture + context.json shareNet_reference, ported verbatim in meaning). */
const SHARENET_REFERENCE = {
  name: "ShareNet",
  pattern_id: "gateway-relay",
  status: "ShareNet is an accepted ADCOS vertical proof and is the canonical gateway/relay example.",
  boundary:
    "ShareNet content/P2P plane -> technology-neutral gateway/relay connectivity requirement -> ADCOS -> provider realization",
  sharenet_owns: [
    "content addressing and distribution",
    "Nearby/P2P transport",
    "publisher trust and catalog semantics",
    "delivery receipts / local attestation",
    "contribution/corpus/training semantics",
    "application economics",
  ],
  adcos_owns: [
    "connectivity intent/contract lifecycle",
    "offer acceptance and provider orchestration",
    "execution and assurance references",
    "bounded connectivity leases",
    "asynchronous observations",
  ],
  provider_owns: [
    "topology",
    "access technology realization",
    "routing",
    "subscriber/network authority",
  ],
  critical_rule:
    "Ordinary device-to-device ShareNet transfers remain inside ShareNet and do not become ADCOS connectivity transactions.",
  integration_shape:
    "Introduce an application-level ADCOS connectivity port/client for gateway/backhaul needs; do not put ADCOS inside ShareNet core-transport.",
  sdk_note:
    "ShareNet's current repository includes an SDK whose intended public surface owns publish/subscribe/fetch/local availability/contribution submission/sync observation, plus core crypto/content/catalog/transport/attest modules. Integrate ADCOS above those modules rather than creating direct provider dependencies in them.",
} as const;

/* ------------------------------------------------------------------ *
 * The registry-derived data (ZERO hand-maintained endpoint lists)
 * ------------------------------------------------------------------ */

/** The current developer-API major line, derived from the coverage registry's own paths. */
const DEVELOPER_API_VERSION: string = (() => {
  for (const record of COVERAGE) {
    const match = record.path.match(/^\/api\/(\d+\.\d+)\//);
    if (match) return match[1];
  }
  return "";
})();

/** The education lookup — one record per coverage operation (load-guarded below). */
const EDUCATION_BY_OPERATION = new Map<string, OperationLearningDefinition>(
  OPERATION_EDUCATION.map((entry) => [entry.operation as string, entry]),
);

/** The canonical lifecycle line (design §4), derived from the registry's own stage names. */
const CANONICAL_LIFECYCLE_LINE = INTEGRATION_WORKFLOWS.application
  .map((step) => step.stage)
  .join(" → ");

/** One markdown line per operation — the derived complete operation registry. */
function operationLine(operationId: string): string {
  const record = coverageByOperation(operationId);
  const education = EDUCATION_BY_OPERATION.get(operationId);
  if (!record || !education) {
    throw new Error(`operation "${operationId}" lacks coverage or education — the registries are the only authority`);
  }
  return `- ${record.method} ${record.path} (${record.operation}) — ${education.purpose}`;
}

/** The developer-API operation lines, in canonical lifecycle order. */
const DEVELOPER_OPERATION_LINES = operationsInLifecycleOrder(
  COVERAGE.filter((record) => !record.platform).map((record) => record.operation),
).map(operationLine);

/** The platform-surface operation lines, in canonical lifecycle order. */
const PLATFORM_OPERATION_LINES = operationsInLifecycleOrder(
  COVERAGE.filter((record) => record.platform).map((record) => record.operation),
).map(operationLine);

/* ------------------------------------------------------------------ *
 * buildLlmOperations — ONE record per coverage operation (ALL of them)
 * ------------------------------------------------------------------ */

/**
 * The per-operation projection (design §10 minimum fields, plus the
 * registry's own mutation/capability/platform facts): one record for
 * EVERY coverage-registry operation — all 25 today, because the
 * generator derives the list from the registry instead of maintaining
 * it by hand. Example requests come from the coverage registry's real
 * captured example bodies (or the education record's honest no-body
 * note); example responses reference the canonical /docs/api page
 * rather than fabricating response bodies.
 */
export function buildLlmOperations(): Record<string, unknown>[] {
  return COVERAGE.map((record) => {
    const education = EDUCATION_BY_OPERATION.get(record.operation);
    if (!education) {
      throw new Error(
        `operation "${record.operation}" has no education record — every coverage operation must carry one`,
      );
    }
    const capabilityIds = INTEGRATION_CAPABILITIES.filter((capability) =>
      capability.operationIds.includes(record.operation),
    ).map((capability) => capability.id);
    const bodyNote = education.fieldExplanations.find((field) => field.field === "request body")
      ?.explanation;
    const exampleRequest: unknown =
      record.example !== undefined ? record.example : (bodyNote ?? "No request body.");
    return {
      operation_id: record.operation,
      method: record.method,
      path: record.path,
      description: record.description,
      purpose: education.purpose,
      prerequisites: education.prerequisites,
      lifecycle_position: education.lifecyclePosition,
      mutation: record.mutation,
      required_capability: record.requiredCapability,
      platform: record.platform,
      capability_ids: capabilityIds,
      concept_ids: [...education.relatedConcepts],
      example_request: exampleRequest,
      example_response: `See /docs/api/${record.operation} for the canonical response anatomy.`,
      error_reason_codes: [...education.relatedErrors],
      next_operation_ids: education.nextOperation ? [education.nextOperation] : [],
    };
  });
}

/* ------------------------------------------------------------------ *
 * buildLlmContext — the 15 design-§10 sections, EXACTLY these
 * ------------------------------------------------------------------ */

/**
 * The canonical machine-readable LLM context: EXACTLY the 15 top-level
 * sections of design §10 (mission, mental_model, architecture,
 * authority_boundaries, integration_patterns, capabilities, operations,
 * workflow_sequences, webhooks, errors, versioning, security_rules,
 * evidence_rules, anti_patterns, production_checklist). The prose
 * sections port the operator's hand-authored content; the enumerations
 * are registry-derived.
 */
export function buildLlmContext(): Record<string, unknown> {
  return {
    mission: { ...MISSION },
    mental_model: {
      description: MENTAL_MODEL_DESCRIPTION,
      lifecycle: [...INTEGRATION_WORKFLOWS.application.map((step) => step.stage)],
      diagram: MENTAL_MODEL_DIAGRAM,
    },
    architecture: {
      canonical_integration_model: CANONICAL_LIFECYCLE_LINE,
      api_model: {
        current_developer_api_major_line: DEVELOPER_API_VERSION,
        boundary_includes: API_MODEL_PROSE.boundary_includes,
        developer_operations: COVERAGE.filter((record) => !record.platform).map(
          (record) => record.operation,
        ),
        platform_surfaces: COVERAGE.filter((record) => record.platform).map(
          (record) => record.operation,
        ),
        authoritative_list: API_MODEL_PROSE.authoritative_list,
        mutation_rule: API_MODEL_PROSE.mutation_rule,
      },
      object_semantics: Object.fromEntries(OBJECT_SEMANTICS.map(([term, text]) => [term, text])),
      provider_adapter_rule: PROVIDER_ADAPTER_RULE,
    },
    authority_boundaries: {
      application: [...AUTHORITY_BOUNDARY_LISTS.application],
      adcos: [...AUTHORITY_BOUNDARY_LISTS.adcos],
      provider: [...AUTHORITY_BOUNDARY_LISTS.provider],
      application_authority: AUTHORITY_MODEL.application,
      adcos_authority: AUTHORITY_MODEL.adcos,
      provider_authority: AUTHORITY_MODEL.provider,
      absolute_rules: [...ABSOLUTE_RULES],
      integration_rules: [...INTEGRATION_RULES],
    },
    integration_patterns: {
      patterns: INTEGRATION_PATTERNS.map((pattern) => ({
        id: pattern.id,
        title: pattern.title,
        summary: pattern.summary,
        primary_rule: PATTERN_PRIMARY_RULES[pattern.id],
        application_owns: [...pattern.applicationOwns],
        adcos_owns: [...pattern.adcosOwns],
        provider_owns: [...pattern.providerOwns],
        operation_ids: [...pattern.operationIds],
        concept_ids: [...pattern.conceptIds],
      })),
      reference_integration: {
        name: SHARENET_REFERENCE.name,
        pattern_id: SHARENET_REFERENCE.pattern_id,
        status: SHARENET_REFERENCE.status,
        boundary: SHARENET_REFERENCE.boundary,
        sharenet_owns: [...SHARENET_REFERENCE.sharenet_owns],
        adcos_owns: [...SHARENET_REFERENCE.adcos_owns],
        provider_owns: [...SHARENET_REFERENCE.provider_owns],
        critical_rule: SHARENET_REFERENCE.critical_rule,
        integration_shape: SHARENET_REFERENCE.integration_shape,
        sdk_note: SHARENET_REFERENCE.sdk_note,
      },
    },
    capabilities: INTEGRATION_CAPABILITIES.map((capability) => ({
      id: capability.id,
      title: capability.title,
      description: capability.description,
      operation_ids: [...capability.operationIds],
    })),
    operations: buildLlmOperations(),
    workflow_sequences: {
      note: "The canonical integration lifecycle per pattern (design §4). Each step's operation_id, when present, is a real coverage-registry operation the stage maps onto; stages without one carry an honest note instead of an invented endpoint.",
      patterns: INTEGRATION_PATTERNS.map((pattern) => ({
        pattern_id: pattern.id,
        steps: INTEGRATION_WORKFLOWS[pattern.id].map((step) => ({
          stage: step.stage,
          operation_id: step.operationId ?? null,
          note: step.note,
        })),
      })),
    },
    webhooks: {
      rule: "Webhooks are observations. They do not replace canonical contract reads and never become a second source of canonical business state.",
      frozen_event_types: [...WEBHOOK_EVENT_TYPES],
      registration:
        "Register endpoints with endpoint_register (POST /api/2.0/webhook-endpoints). Event types come only from the frozen vocabulary above; the backend rejects any other value with invalid-input.",
      verification:
        "Implement webhook signature verification and replay protections where webhooks are used.",
    },
    errors: {
      handling: [...ERROR_HANDLING_STEPS],
      unknown_rule: ERROR_UNKNOWN_RULE,
      reason_codes: [...CANONICAL_REASON_CODES],
      reason_code_source:
        "The canonical reason-code vocabulary of the ADCOS developer boundary — transcribed verbatim from the console's canonical error taxonomy (the same frozen pin the errors documentation page and the registry tests carry). Codes are ids, never synonyms.",
    },
    versioning: {
      rule: VERSIONING.rule,
      current_major_line: DEVELOPER_API_VERSION,
      compatibility: VERSIONING.compatibility,
    },
    security_rules: { ...SECURITY_RULES },
    evidence_rules: { ...EVIDENCE_RULES },
    anti_patterns: [...LLM_SAFETY_RULES, ...ANTI_PATTERN_NEVER_LIST],
    production_checklist: {
      before_production: [...PRODUCTION_CHECKLIST],
      llm_implementation_workflow: [...LLM_IMPLEMENTATION_WORKFLOW],
    },
  };
}

/* ------------------------------------------------------------------ *
 * The public-asset renderers
 * ------------------------------------------------------------------ */

/** `/llms.txt` — the concise machine-oriented overview (the operator's content, lifecycle line registry-derived). */
export function renderLlmsTxt(): string {
  return `# ADCOS LLM Integration Context

ADCOS (Adaptive Distributed Connectivity Operating System) is a connectivity exchange and orchestration layer: one connectivity contract, many networks, continuous fulfillment.

Start here:
- /llms-full.txt — complete architect/developer context
- /adcos-integration-context.json — machine-readable integration model
- /adcos-capabilities.json — supported integration capabilities
- /adcos-operations.json — current developer API operations
- /build — interactive architecture/integration designer
- /docs — human documentation
- /developers/explorer — executable API Explorer

Core lifecycle:
${CANONICAL_LIFECYCLE_LINE}

Authority boundaries:
- The ConnectivityContract is the canonical ADCOS contract authority.
- Applications own their product domain, user/device context and product UX.
- ADCOS owns connectivity intent/contract lifecycle and orchestration.
- Providers own provider-native topology, routing, subscriber authority and physical realization.
- Webhooks are observations, not canonical business state.
- API success does not prove physical connectivity success.
- Provider SDKs and provider-native topology must not leak into consuming application domains.
- Do not invent endpoints or capabilities; use the published operation registry.

ShareNet pattern:
ShareNet keeps authority over content, P2P distribution, publisher trust, delivery receipts and application economics. It uses ADCOS for technology-neutral gateway/relay connectivity. Ordinary device-to-device content transfers remain in ShareNet's data plane and do not become ADCOS connectivity transactions.
`;
}

/** `/llms-full.txt` — the complete architect/developer context (operator prose + registry-derived enumerations). */
export function renderLlmsFullTxt(): string {
  const patternSections = INTEGRATION_PATTERNS.map((pattern) => {
    const sequence = operationsInLifecycleOrder(pattern.operationIds).join(" → ");
    return `### ${pattern.title}

${PATTERN_PROSE[pattern.id]}

Operations (from the integration registry): \`${sequence}\``;
  }).join("\n\n");

  const objectSemantics = OBJECT_SEMANTICS.map(
    ([term, text]) => `### ${term}\n\n${text}`,
  ).join("\n\n");

  const webhookEvents = WEBHOOK_EVENT_TYPES.map((event) => `- ${event}`).join("\n");

  return `# ADCOS — Complete Architect / Developer Context

## Mission

ADCOS is an Adaptive Distributed Connectivity Operating System and programmable connectivity exchange/orchestration layer. Its product promise is **one connectivity contract, many networks, continuous fulfillment**.

ADCOS composes heterogeneous provider capabilities without taking ownership of provider-native radio/core/topology/routing authority.

## The mental model

${MENTAL_MODEL_DESCRIPTION}

\`\`\`text
${MENTAL_MODEL_DIAGRAM}
\`\`\`

## Authority model

### Application authority

${AUTHORITY_MODEL.application}

### ADCOS authority

${AUTHORITY_MODEL.adcos}

### Provider authority

${AUTHORITY_MODEL.provider}

## Rules every integration must preserve

${INTEGRATION_RULES.map((rule, index) => `${index + 1}. ${rule}`).join("\n")}

## Integration patterns

${patternSections}

## API model

Current developer API major line: **${DEVELOPER_API_VERSION}**.

${API_MODEL_PROSE.boundary_includes}

Complete operation registry (${COVERAGE.length} operations, projected from the console coverage registry — the authoritative list):

${DEVELOPER_OPERATION_LINES.join("\n")}

Platform surfaces (unauthenticated):

${PLATFORM_OPERATION_LINES.join("\n")}

${API_MODEL_PROSE.authoritative_list}

${API_MODEL_PROSE.mutation_rule}

## Object semantics

${objectSemantics}

## Webhook observations

Webhooks are signed observations. Use them to react asynchronously, but maintain canonical state from authoritative API reads — they never become a second source of canonical business state.

The frozen event-type vocabulary (the backend rejects any other value):
${webhookEvents}

Register endpoints with endpoint_register (POST /api/2.0/webhook-endpoints); implement signature verification and replay protections where webhooks are used.

## Error handling

When an ADCOS operation fails:
${ERROR_HANDLING_STEPS.map((step, index) => `${index + 1}. ${step}`).join("\n")}

${ERROR_UNKNOWN_RULE}

The canonical reason-code vocabulary (verbatim — never synonyms):
${CANONICAL_REASON_CODES.join(", ")}

## Versioning

${VERSIONING.rule} ${VERSIONING.compatibility}

## ShareNet reference architecture

${SHARENET_REFERENCE.status}

\`\`\`text
ShareNet content + P2P data plane
            |
            | technology-neutral gateway/relay connectivity need
            v
        ADCOS contract
            |
            v
      provider realization
\`\`\`

ShareNet retains authority over:
${SHARENET_REFERENCE.sharenet_owns.map((item) => `- ${item}`).join("\n")}

ADCOS provides:
${SHARENET_REFERENCE.adcos_owns.map((item) => `- ${item}`).join("\n")}

Providers retain:
${SHARENET_REFERENCE.provider_owns.map((item) => `- ${item}`).join("\n")}

ShareNet must therefore introduce an \`AdcosConnectivityClient\`/equivalent application port at its control-plane boundary, not put ADCOS into its local \`core-transport\`. Ordinary device-to-device content transfers remain within ShareNet. ADCOS is used when ShareNet needs connectivity outcomes for gateway/relay/backhaul infrastructure.

${SHARENET_REFERENCE.sdk_note}

## Provider adapter rule

${PROVIDER_ADAPTER_RULE}

## Security and secrets

${SECURITY_RULES.secrets}

## LLM implementation workflow

When an LLM is asked to add ADCOS to a product:
${LLM_IMPLEMENTATION_WORKFLOW.map((step, index) => `${index + 1}. ${step}`).join("\n")}

## Anti-patterns

Never:
${ANTI_PATTERN_NEVER_LIST.map((item) => `- ${item}`).join("\n")}

LLM safety rules (mandatory):
${LLM_SAFETY_RULES.map((rule) => `- ${rule}`).join("\n")}

## Production checklist

Before production integration:
${PRODUCTION_CHECKLIST.map((item) => `- [ ] ${item}`).join("\n")}
`;
}

/** `/adcos-integration-context.json` — the machine-readable canonical context (the 15 design-§10 sections). */
export function renderIntegrationContextJson(): string {
  return `${JSON.stringify(buildLlmContext(), null, 2)}\n`;
}

/** `/adcos-capabilities.json` — the capability registry projection. */
export function renderCapabilitiesJson(): string {
  return `${JSON.stringify(
    {
      schema_version: "1",
      generated_for: "ADCOS Build with ADCOS",
      capabilities: INTEGRATION_CAPABILITIES.map((capability) => ({
        id: capability.id,
        title: capability.title,
        description: capability.description,
        operation_ids: capability.operationIds,
      })),
      rule: "This is a documentation projection of the canonical console coverage registry. It must not become a second executable endpoint catalog.",
    },
    null,
    2,
  )}\n`;
}

/** `/adcos-operations.json` — the operation registry projection with educational metadata. */
export function renderOperationsJson(): string {
  return `${JSON.stringify(
    {
      api_version: DEVELOPER_API_VERSION,
      operations: buildLlmOperations(),
      rule: "This is a documentation projection of the canonical console coverage registry. It must not become a second executable endpoint catalog.",
    },
    null,
    2,
  )}\n`;
}

/* ------------------------------------------------------------------ *
 * The module-load guards (duplicated as tests in tests/llm-pack.test.ts)
 * ------------------------------------------------------------------ */

/**
 * The real registries are the ONLY authorities here: every coverage
 * operation must carry an education record; every education
 * relatedConcepts / relatedErrors / nextOperation entry must resolve
 * against the concept registry / the canonical reason-code pin / the
 * coverage registry; every pattern id must have ported primary-rule
 * and prose content. This throws at import time so drift fails before
 * any public asset is generated.
 */
const CONCEPT_IDS = new Set<string>(CONCEPTS.map((concept) => concept.id));
const COVERAGE_OPERATION_IDS = new Set<string>(COVERAGE.map((record) => record.operation));
const REASON_CODE_SET = new Set(CANONICAL_REASON_CODES);
if (new Set(CANONICAL_REASON_CODES).size !== CANONICAL_REASON_CODES.length) {
  throw new Error("the canonical reason-code pin contains duplicate codes");
}
for (const record of COVERAGE) {
  if (!EDUCATION_BY_OPERATION.has(record.operation)) {
    throw new Error(
      `coverage operation "${record.operation}" has no education record — the LLM pack projects every operation`,
    );
  }
}
for (const entry of OPERATION_EDUCATION) {
  for (const conceptId of entry.relatedConcepts) {
    if (!CONCEPT_IDS.has(conceptId)) {
      throw new Error(
        `operation education "${entry.operation}" references unknown concept "${conceptId}"`,
      );
    }
  }
  for (const code of entry.relatedErrors) {
    if (!REASON_CODE_SET.has(code)) {
      throw new Error(
        `operation education "${entry.operation}" references reason code "${code}" outside the canonical vocabulary`,
      );
    }
  }
  if (entry.nextOperation && !COVERAGE_OPERATION_IDS.has(entry.nextOperation)) {
    throw new Error(
      `operation education "${entry.operation}" references unknown next operation "${entry.nextOperation}"`,
    );
  }
}
for (const pattern of INTEGRATION_PATTERNS) {
  if (!PATTERN_PRIMARY_RULES[pattern.id]) {
    throw new Error(`pattern "${pattern.id}" lacks its ported primary rule`);
  }
  if (!PATTERN_PROSE[pattern.id]) {
    throw new Error(`pattern "${pattern.id}" lacks its ported prose`);
  }
}
