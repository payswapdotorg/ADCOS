/**
 * The Console V2 education registry — the CONCEPTS.
 *
 * The DEC-0128 program, Task 1 of the frozen plan: the design §8 core
 * first-class concepts plus the deterministic demonstration context.
 * Every `relatedOperations` id is an accepted coverage-registry
 * operation id (never a second endpoint catalog); every `prerequisites`
 * and `relatedGuides` id belongs to this registry; every `nextSteps`
 * link resolves against the frozen concept / operation / guide / route
 * / docs vocabularies — the education-registry test enforces all of it.
 *
 * Truth rules (design §17): where this HTTP deployment does not expose
 * a capability (replan events, provider eligibility lists, physical
 * evidence), `whatHappens` says so plainly instead of implying it.
 */

import type { ConceptDefinition } from "./types";

/** The concept registry — the console's concept vocabulary authority. */
export const CONCEPTS: ConceptDefinition[] = [
  {
    id: "connectivity-contract",
    term: "Connectivity contract",
    summary:
      "The durable record of the connectivity an application asks ADCOS to continuously fulfill. It is the sole contract authority: requirements, hard constraints, validity, termination rules and referenced terms live here, and every later stage composes over it.",
    whyItMatters:
      "The contract is the anchor every other object references — plans, executions, evidence, assurance obligations and leases all hang off a contract id. Because it is durable and canonical, you can always return to it to see exactly what was asked and what ADCOS is doing about it.",
    whenToUse:
      "Create one whenever your application needs connectivity. Read it whenever you need to know what was requested, why the flow state is what it is, or want to reproduce an operation against the same canonical material.",
    whatHappens:
      "You record an intent with requirements, hard constraints and a validity window; ADCOS keeps the canonical material verbatim (opaque typed references pass through unchanged). Offers are accepted onto the intent (OFFER_SELECTED), activation moves it to CONTRACT_ACTIVE, and the lifecycle observation reports state, execution status and statements honestly — physical connectivity is never claimed by API success. Termination is terminal, hard constraints are immutable after creation, and leases grant bounded access windows over the active contract.",
    prerequisites: ["application-capability"],
    relatedObjects: ["Contract", "ContractLifecycle", "OpaqueReference", "HardConstraint"],
    relatedOperations: [
      "intent_create",
      "intents_list",
      "intent_get",
      "intent_lifecycle",
      "offers_accept",
      "contract_activate",
      "contracts_list",
      "contract_get",
      "contract_terminate",
      "platform_contract_read",
      "lease_grant",
      "leases_list",
      "lease_get",
      "lease_renew",
      "lease_revoke",
    ],
    relatedGuides: ["first-connectivity-application", "understand-connectivity-contract"],
    apiLook: {
      operationId: "intent_create",
      note: "Recording an intent is the contract creation core — the principal is derived from the authenticated application.",
    },
    runnableExample: {
      operationId: "demo_contract_fulfillment",
      label: "Run the deterministic contract-to-fulfillment demonstration",
    },
    relatedTroubleshooting: [
      "unknown-contract",
      "invalid-transition",
      "constraint-immutable",
      "contract-terminal",
    ],
    nextSteps: [
      { kind: "concept", id: "offer", label: "Offer — what gets accepted onto an intent" },
      { kind: "guide", id: "first-connectivity-application", label: "Build my first connectivity application" },
      { kind: "route", id: "/connectivity", label: "Open the contracts workspace" },
    ],
  },
  {
    id: "provider-capability",
    term: "Provider capability",
    summary:
      "A connectivity capability a provider supplies through an adapter — the unit ADCOS composes into execution plans. Provider-native topology, routing and subscriber authority stay with the provider; ADCOS never owns a universal topology graph.",
    whyItMatters:
      "Plans and fulfillment are compositions of provider capabilities, not ADCOS-owned infrastructure. Understanding the unit keeps expectations honest: ADCOS composes and contracts; the provider delivers on its own terms behind its adapter.",
    whenToUse:
      "Read this when you want to know what a plan is composed of, or why provider selection looks the way it does. It is also the background for integrating a provider adapter.",
    whatHappens:
      "This deployment exposes provider/adapter facts through the deterministic demonstration document's composition material (provider, adapter, access technology, standard) and the Networks page's composition section. No provider registry, provider health metric or eligibility list operation exists on the accepted boundary — the deterministic reference adapters are the sandbox providers, and no provider claim is made beyond that.",
    prerequisites: [],
    relatedObjects: ["DemoDocument"],
    relatedOperations: ["demo_contract_fulfillment"],
    relatedGuides: ["understand-provider-selection", "integrate-provider-adapter"],
    apiLook: {
      operationId: "demo_contract_fulfillment",
      note: "The demonstration document's composition section carries the provider/adapter facts this deployment exposes.",
    },
    relatedTroubleshooting: [],
    nextSteps: [
      { kind: "concept", id: "provider-adapter-boundary", label: "The provider/adapter boundary" },
      { kind: "route", id: "/networks", label: "Open the Networks page" },
      { kind: "guide", id: "understand-provider-selection", label: "Understand why a provider was selected" },
    ],
  },
  {
    id: "offer",
    term: "Offer",
    summary:
      "An opaque typed reference to a provider's proposed terms for fulfilling a contract's requirements. Accepting offers onto an intent moves the contract to OFFER_SELECTED.",
    whyItMatters:
      "Offer acceptance is the bridge between what you asked for and the plan that gets composed: the accepted offer is the material the execution plan composes over. Because offers are opaque typed references, the console shows them verbatim with their provenance instead of interpreting them.",
    whenToUse:
      "After an intent exists and before activation — offers are accepted while the contract is in the INTENT state. Also whenever you want to understand which terms a provider actually proposed.",
    whatHappens:
      "You accept opaque offer references (each with ref_kind, value and provenance: issuer plus decision refs) onto the intent via offers_accept; the contract records them as accepted_offers and moves to OFFER_SELECTED. This deployment exposes no offer catalog and no provider-selection decision operation — offers enter through the API as canonical material and render verbatim.",
    prerequisites: ["connectivity-contract"],
    relatedObjects: ["Contract", "OpaqueReference"],
    relatedOperations: ["offers_accept", "intent_get"],
    relatedGuides: ["understand-provider-selection"],
    apiLook: {
      operationId: "offers_accept",
      note: "Accept opaque typed offer references onto an intent — the contract moves to OFFER_SELECTED.",
    },
    relatedTroubleshooting: ["invalid-transition", "resource-unknown"],
    nextSteps: [
      { kind: "concept", id: "execution-plan", label: "Execution plan — what the offer becomes" },
      { kind: "operation", id: "contract_activate", label: "Activate the contract" },
      { kind: "guide", id: "understand-provider-selection", label: "Understand why a provider was selected" },
    ],
  },
  {
    id: "eligibility",
    term: "Eligibility",
    summary:
      "The reasoning for why a contract's flow state is what it is — which requirements, constraints and policies shaped the current position. In this console it is presented from the lifecycle observation's own statements, never re-implemented in the browser.",
    whyItMatters:
      "Eligibility explains the system's behavior instead of leaving you to guess: the lifecycle projection states the contract state, execution status, evidence class and physical-connectivity position, with the backend's note and statements verbatim. The console never fabricates a policy engine in TypeScript — backend reasoning data is the only source.",
    whenToUse:
      "Whenever a contract is in a state you did not expect, or before choosing the next command. The contract detail page's Eligibility section is the canonical place to look.",
    whatHappens:
      "The lifecycle observation (intent_lifecycle) reports contract_state, execution_status, evidence_class, physical_connectivity_observed and statements — the honest software-side state-machine projection. Provider eligibility decisions as a list are not exposed by this deployment; what is exposed lives per contract in that lifecycle observation. Physical connectivity is never claimed by API success.",
    prerequisites: ["connectivity-contract"],
    relatedObjects: ["ContractLifecycle"],
    relatedOperations: ["intent_lifecycle", "intent_get", "contract_get"],
    relatedGuides: ["understand-provider-selection", "diagnose-fulfillment-failure"],
    relatedTroubleshooting: ["invalid-transition", "capability-denied"],
    nextSteps: [
      { kind: "concept", id: "policy", label: "Policy — the rules behind the reasoning" },
      { kind: "route", id: "/connectivity/contracts/[id]", label: "Open a contract's detail page" },
      { kind: "guide", id: "diagnose-fulfillment-failure", label: "Diagnose a failed fulfillment" },
    ],
  },
  {
    id: "policy",
    term: "Policy",
    summary:
      "The rules that govern what ADCOS and the console may do: capability grants that unlock operations, frozen vocabularies, state-machine transition rules and hard-constraint immutability. Policy is enforced by the backend boundary — the console presents it, never re-implements it.",
    whyItMatters:
      "Policy is why operations fail with specific reason codes instead of silently succeeding: capability-denied when a grant is missing, invalid-transition when the state machine forbids a command, constraint-immutable when hard constraints would change. Knowing where policy lives makes failures legible and retry decisions honest.",
    whenToUse:
      "Read this when a mutation fails with a policy-shaped reason code, or when planning which capabilities an application needs for the workflow you want.",
    whatHappens:
      "The authenticated application carries capability grants — intents, leases and webhooks read/write, usage and assurance read — checked per operation. The boundary validates frozen vocabularies and required members, enforces the contract state machine, and keeps hard constraints immutable after creation. Policy decisions themselves are not exposed as a resource — they surface as verbatim reason codes on the operations they govern.",
    prerequisites: ["application-capability"],
    relatedObjects: ["Application"],
    relatedOperations: ["application_self", "intent_lifecycle"],
    relatedGuides: ["integrate-adcos-api"],
    relatedTroubleshooting: [
      "capability-denied",
      "invalid-transition",
      "constraint-immutable",
      "vocabulary",
    ],
    nextSteps: [
      { kind: "concept", id: "application-capability", label: "Application and capability" },
      { kind: "route", id: "/settings/errors", label: "Open the error workbench" },
      { kind: "docs", id: "errors", label: "The canonical reason codes" },
    ],
  },
  {
    id: "execution-plan",
    term: "Execution plan",
    summary:
      "The composition of provider capabilities that fulfills an accepted contract — produced over the same canonical hard constraints, never weakening them. In the API it binds onto the contract as opaque execution-scope and execution-artifact references.",
    whyItMatters:
      "The plan is the step between what you asked for and what actually happens: it records how provider capabilities were composed, and every replan re-composes a new plan through the same verification gate. When you want to know what ADCOS is actually doing, the plan material is the core of the answer.",
    whenToUse:
      "After offer selection and activation, or whenever you read a contract detail page's Plan section. Also when a fulfillment looks wrong — the plan tells you what was composed.",
    whatHappens:
      "Plan material binds as opaque typed references (execution_scope, execution_artifacts) on the contract — the execution-artifact reference IS the plan binding, and the console renders it verbatim with provenance. The deterministic demonstration document exposes the full plan leg (plan id, validity, the segments composed over provider capabilities) so the shape is inspectable end to end.",
    prerequisites: ["connectivity-contract", "offer"],
    relatedObjects: ["Contract", "DemoDocument", "OpaqueReference"],
    relatedOperations: ["intent_get", "contract_get", "demo_contract_fulfillment"],
    relatedGuides: ["understand-connectivity-contract", "understand-provider-selection"],
    apiLook: {
      operationId: "contract_get",
      note: "The contract resource carries the plan binding as execution_scope and execution_artifacts references.",
    },
    relatedTroubleshooting: [],
    nextSteps: [
      { kind: "concept", id: "fulfillment", label: "Fulfillment — the plan in motion" },
      { kind: "concept", id: "replan-failover", label: "Replanning — re-composition when conditions change" },
      { kind: "route", id: "/connectivity/contracts/[id]", label: "Open a contract's detail page" },
    ],
  },
  {
    id: "fulfillment",
    term: "Fulfillment",
    summary:
      "The continuous work of honoring an active contract: executing the plan, recording what happened, and keeping the obligation alive across the validity window. Fulfillment is observed, never assumed — the lifecycle reports an execution status, and API success never claims physical connectivity.",
    whyItMatters:
      "Continuously working to fulfill the contract is ADCOS's core promise, and fulfillment is where that promise lives. Its honesty rules matter most here: software-side state transitions and evidence are labeled as such, and degraded or failed states are reported rather than hidden.",
    whenToUse:
      "Whenever a contract is active and you want to know what ADCOS is doing right now, or after running the demonstration to see the execution leg. Also when diagnosing a failed or degraded fulfillment.",
    whatHappens:
      "The lifecycle observation reports execution_status and statements per contract. This deployment exposes the execution leg in full through the deterministic demonstration: the segment-state chain the deterministic execution records, with the reference adapter as the sandbox provider. The backend's replan/failover machinery exists in the accepted architecture, but replan events are not currently exposed by this deployment.",
    prerequisites: ["execution-plan"],
    relatedObjects: ["ContractLifecycle", "DemoDocument"],
    relatedOperations: ["intent_lifecycle", "contract_get", "demo_contract_fulfillment"],
    relatedGuides: ["diagnose-fulfillment-failure", "handle-degraded-connectivity"],
    relatedTroubleshooting: ["invalid-state", "backend-unreachable"],
    nextSteps: [
      { kind: "concept", id: "evidence", label: "Evidence — the records behind the claims" },
      { kind: "concept", id: "replan-failover", label: "Replanning and failover" },
      { kind: "route", id: "/fulfillment", label: "Open the Fulfillment workspace" },
    ],
  },
  {
    id: "assurance",
    term: "Assurance",
    summary:
      "The obligations a contract references that describe what must hold for the connectivity to count as assured — carried as opaque assurance-obligation references. The console references them, never evaluates them.",
    whyItMatters:
      "Assurance is the difference between connectivity having existed once and connectivity being maintained as promised. Because obligations are referenced material, their meaning stays with the issuing authority — the console shows them verbatim with provenance rather than inventing an evaluation.",
    whenToUse:
      "When reading an active contract's Assurance section, or when you need to know which obligations are attached to a contract you operate.",
    whatHappens:
      "contract_assurance returns the referenced assurance obligations with the contract state and the backend's honest note; the demonstration document's assurance leg shows the same shape inside the deterministic chain. No attestation or evaluation operation exists on the accepted boundary — assurance reads are the exposed surface, and the honest empty attestation state is shown when nothing is recorded.",
    prerequisites: ["connectivity-contract"],
    relatedObjects: ["ContractAssurance", "Contract", "OpaqueReference"],
    relatedOperations: ["contract_assurance", "demo_contract_fulfillment"],
    relatedGuides: ["understand-connectivity-contract"],
    relatedTroubleshooting: ["capability-denied"],
    nextSteps: [
      { kind: "concept", id: "evidence", label: "Evidence — what backs the obligations" },
      { kind: "route", id: "/assurance", label: "Open the Assurance workspace" },
      { kind: "operation", id: "contract_assurance", label: "Read a contract's assurance obligations" },
    ],
  },
  {
    id: "evidence",
    term: "Evidence",
    summary:
      "The records that support what the system claims — observations and attestations with a producer, instant, subject, confidence and sources. Every record carries an evidence class, and SOFTWARE evidence is always visibly distinct from physical/network evidence.",
    whyItMatters:
      "Evidence is the difference between an assertion and a verifiable claim: each lifecycle position and execution step is backed by records you can inspect. The class distinction protects you from over-trusting — software-side determinism is honest about being software-side, and physical/network evidence is labeled NOT-ACHIEVABLE-BY-THIS-DEPLOYMENT where that is the truth.",
    whenToUse:
      "After fulfillment steps, when validating a claim, or when you need the grounds for a decision. The Evidence page and each demonstration run's evidence leg are the canonical places.",
    whatHappens:
      "This deployment's evidence surface is the deterministic demonstration document's evidence records (record type, producer, instant, subject, contract ref, metric or attested value, confidence, freshness, source refs) — all SOFTWARE class. The lifecycle observation carries an evidence_class per contract. No physical or network evidence is achievable by this deployment, and none is fabricated.",
    prerequisites: ["fulfillment"],
    relatedObjects: ["DemoDocument", "ContractLifecycle"],
    relatedOperations: ["demo_contract_fulfillment", "intent_lifecycle"],
    relatedGuides: ["diagnose-fulfillment-failure"],
    relatedTroubleshooting: [],
    nextSteps: [
      { kind: "concept", id: "assurance", label: "Assurance — the obligations evidence supports" },
      { kind: "route", id: "/evidence", label: "Open the Evidence page" },
      { kind: "operation", id: "demo_contract_fulfillment", label: "Run the demonstration and inspect its evidence" },
    ],
  },
  {
    id: "replan-failover",
    term: "Replan / failover",
    summary:
      "The explicit re-composition of an accepted contract's fulfillment when conditions change — a new execution plan over the same canonical hard constraints, with the reasoning and evidence presented, never an unexplained provider handoff.",
    whyItMatters:
      "Replanning is how ADCOS keeps a contract alive through degradation instead of failing silently: violated requirements, provider unavailability or validity changes trigger re-composition. The constraints are never weakened by a replan — the plan-verification gate re-verifies that every candidate plan preserves them.",
    whenToUse:
      "Read this to understand degradation handling and what a provider handoff should look like when it happens. The Replanning surface in the console presents this concept honestly today.",
    whatHappens:
      "The backend replan/failover machinery exists in the accepted architecture, but replan events are not currently exposed by this deployment — no replan decision can be inspected through the HTTP surface. The console's Replanning page states this plainly, explains the trigger vocabulary (a violated requirement or threshold with observed versus required value and detection time, provider unavailability or degradation, validity-driven change) and shows the card shape it will render — clearly labeled a structure preview, with no fabricated events.",
    prerequisites: ["execution-plan", "fulfillment"],
    relatedObjects: ["Contract"],
    relatedOperations: [],
    relatedGuides: ["handle-degraded-connectivity"],
    relatedTroubleshooting: [],
    nextSteps: [
      { kind: "route", id: "/fulfillment", label: "Open the Fulfillment workspace" },
      { kind: "concept", id: "fulfillment", label: "Fulfillment — what replanning protects" },
      { kind: "guide", id: "handle-degraded-connectivity", label: "Handle degraded connectivity" },
    ],
  },
  {
    id: "provider-adapter-boundary",
    term: "Provider / adapter boundary",
    summary:
      "The seam where providers join ADCOS: each provider supplies capabilities through an adapter, and ADCOS composes them without owning provider-native topology, routing or subscriber authority. Provider claims stop at what the adapter actually reports.",
    whyItMatters:
      "The boundary keeps responsibilities honest: ADCOS composes and contracts over capabilities; the provider remains authoritative for its own network. No universal ADCOS topology graph is implied or rendered — the console states this boundary explicitly wherever providers appear.",
    whenToUse:
      "Before integrating a provider, when reading composition facts, or whenever you are tempted to read a topology view into the console. The Networks page carries the boundary notice.",
    whatHappens:
      "The Networks page presents the provider/adapter facts from the deterministic runtime composition (provider, adapter, access technology, standard) with the explicit provider-owned boundary notice, and honestly lists what it does not show (no provider health or performance metrics, no eligibility lists). In the demonstration, the deterministic reference adapters ARE the sandbox providers — no provider claim is made. No adapter registration or provider management operation exists on the accepted boundary.",
    prerequisites: ["provider-capability"],
    relatedObjects: ["DemoDocument"],
    relatedOperations: ["demo_contract_fulfillment"],
    relatedGuides: ["integrate-provider-adapter"],
    relatedTroubleshooting: [],
    nextSteps: [
      { kind: "route", id: "/networks", label: "Open the Networks page" },
      { kind: "guide", id: "integrate-provider-adapter", label: "Build or integrate a provider adapter" },
      { kind: "concept", id: "provider-capability", label: "Provider capability" },
    ],
  },
  {
    id: "application-capability",
    term: "Application and capability",
    summary:
      "The authenticated application — its identity, environment and status — plus the capability grants that unlock API operations. Every developer-API call runs as this application, and the contract principal is derived from it.",
    whyItMatters:
      "Capabilities are the console's permission model: intents, leases and webhooks carry read/write grants, usage and assurance carry read grants, and an operation without its grant fails with capability-denied. Knowing your grants tells you which workflows you can actually run.",
    whenToUse:
      "At the start of any session (the Developers workspace shows identity and capabilities), and whenever an operation fails with capability-denied or an authentication reason code.",
    whatHappens:
      "application_self returns the application's id, name, developer, environment, status, validity and capability list. Credentials are masked in the console and follow backend issuance and reveal rules — the console shows no secret material and persists none. Capability grants map onto exactly the operations the coverage registry marks as requiring them.",
    prerequisites: [],
    relatedObjects: ["Application"],
    relatedOperations: ["application_self"],
    relatedGuides: ["integrate-adcos-api", "first-connectivity-application"],
    apiLook: {
      operationId: "application_self",
      note: "The authenticated application: identity, environment, capabilities, status and validity.",
    },
    relatedTroubleshooting: [
      "authentication-invalid",
      "authentication-expired",
      "environment-mismatch",
      "capability-denied",
    ],
    nextSteps: [
      { kind: "guide", id: "integrate-adcos-api", label: "Integrate the ADCOS API" },
      { kind: "route", id: "/developers", label: "Open the Developers workspace" },
      { kind: "docs", id: "api/authentication", label: "API authentication" },
    ],
  },
  {
    id: "webhook",
    term: "Webhook",
    summary:
      "A registered HTTPS endpoint that receives observation events for your application — registered with a URL and a frozen set of event types, with delivery attempts recorded per endpoint.",
    whyItMatters:
      "Webhooks turn polling into push: instead of re-reading lists to detect change, your integration reacts to events. The registration surface is deliberately narrow (URL plus event types from a frozen vocabulary) and returns a key id only — no secret material.",
    whenToUse:
      "When integrating the ADCOS API into a backend service that must react to contract or endpoint events. The Developers workspace registers and lists endpoints; deliveries are inspectable per endpoint.",
    whatHappens:
      "endpoint_register records the URL and event types; the response carries the endpoint resource with a key id (no secret material — the backend never returns one). endpoints_list and endpoint_get read them back, and deliveries_list records each delivery attempt with event, status, retries and next-attempt instants.",
    prerequisites: ["application-capability"],
    relatedObjects: ["WebhookEndpoint", "WebhookDelivery"],
    relatedOperations: ["endpoint_register", "endpoints_list", "endpoint_get", "deliveries_list"],
    relatedGuides: ["integrate-adcos-api"],
    apiLook: {
      operationId: "endpoint_register",
      note: "Register a webhook endpoint for observation event types.",
    },
    relatedTroubleshooting: ["invalid-input", "secret-rejected", "vocabulary"],
    nextSteps: [
      { kind: "route", id: "/developers", label: "Open the Developers workspace" },
      { kind: "guide", id: "integrate-adcos-api", label: "Integrate the ADCOS API" },
      { kind: "docs", id: "api/webhooks", label: "The webhooks API" },
    ],
  },
  {
    id: "demo-fulfillment-journey",
    term: "The deterministic demonstration",
    summary:
      "The deterministic full-chain demonstration this deployment exposes: one document carrying the boundary trace, contract, plan, execution and evidence for a given instant. Identical instant → identical document — it is a demonstration, not production telemetry.",
    whyItMatters:
      "It is the fastest honest way to see the whole mental model working: every stage of the chain appears with its canonical shape and the SOFTWARE evidence class visible throughout. Because it is a pure function of the instant you can reproduce and share it exactly — and because it is deterministic it never implies production network behavior.",
    whenToUse:
      "As the supported demo context when you have no issued credential, or as the first concrete thing to run when learning the model. The Home and Fulfillment surfaces run it, and the run page inspects the full chain.",
    whatHappens:
      "GET /demo/contract-fulfillment runs at the default instant; POST with an instant runs at a chosen one (a different instant is a genuinely new demonstration contract). The response is replayed through the boundary's own idempotency ledger — the same canonical execution every time. This is a deterministic demonstration with SOFTWARE evidence class only: physical/network evidence is NOT-ACHIEVABLE-BY-THIS-DEPLOYMENT, and no provider, production or telemetry claim is made.",
    prerequisites: [],
    relatedObjects: ["DemoDocument", "DemoBoundaryEntry"],
    relatedOperations: ["demo_contract_fulfillment"],
    relatedGuides: ["first-connectivity-application"],
    apiLook: {
      operationId: "demo_contract_fulfillment",
      note: "The deterministic full-chain demo document; POST with an instant for a specific one.",
    },
    runnableExample: {
      operationId: "demo_contract_fulfillment",
      label: "Run the deterministic demonstration (no authentication required)",
    },
    relatedTroubleshooting: ["backend-unreachable"],
    nextSteps: [
      { kind: "route", id: "/fulfillment", label: "Open the Fulfillment workspace" },
      { kind: "concept", id: "evidence", label: "Evidence — SOFTWARE class, honestly labeled" },
      { kind: "guide", id: "first-connectivity-application", label: "Build my first connectivity application" },
    ],
  },
];
