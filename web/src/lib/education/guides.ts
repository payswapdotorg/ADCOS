/**
 * The Console V2 education registry — the GUIDES (playbooks).
 *
 * The DEC-0128 program, Task 1 of the frozen plan: the design §11
 * playbook list as registry records. Each step is composed from REAL
 * console operations, routes and docs sections — the links resolve
 * against the frozen concept / operation / guide / route / docs
 * vocabularies (machine-checked by the education-registry test), and
 * each `detail` is honest about what the current deployment supports.
 * These are data for the playbook surfaces (Task 6 builds the UIs);
 * nothing here fabricates a capability the HTTP boundary lacks.
 */

import type { GuideDefinition } from "./types";

/** The guide registry — the console's playbook vocabulary authority. */
export const GUIDES: GuideDefinition[] = [
  {
    id: "first-connectivity-application",
    title: "Build my first connectivity application",
    purpose:
      "Take an application from zero to an active, understood connectivity contract — the canonical beginner journey.",
    steps: [
      {
        title: "Understand the model first",
        detail:
          "Read what ADCOS does and the lifecycle — requirement → eligibility → plan → fulfillment → assurance → continuous fulfillment — before touching the machinery. The mental model makes every later screen legible.",
        link: { kind: "docs", id: "how-adcos-works", label: "How ADCOS works" },
      },
      {
        title: "Connect your application — or enter the demo context",
        detail:
          "Connect an issued application credential to call the authenticated API, or use the deterministic demonstration as the supported demo context (no authentication). Both are honest starting points; the demonstration is SOFTWARE evidence only.",
        link: { kind: "route", id: "/developers", label: "The Developers workspace" },
      },
      {
        title: "See your identity and capabilities",
        detail:
          "application_self shows the application, its environment and the capability grants that unlock operations. Check you hold intents:write before building.",
        link: { kind: "operation", id: "application_self", label: "Read the authenticated application" },
      },
      {
        title: "Describe the connectivity you need",
        detail:
          "Record an intent: requirements, hard constraints (immutable once recorded), validity and termination. The builder in the contracts workspace composes the canonical body.",
        link: { kind: "operation", id: "intent_create", label: "Record a connectivity intent" },
      },
      {
        title: "Review the canonical contract",
        detail:
          "Read the intent back — every reference and constraint, verbatim with provenance. This is the material ADCOS will honor.",
        link: { kind: "operation", id: "intent_get", label: "Read the intent's canonical material" },
      },
      {
        title: "Accept an offer",
        detail:
          "Accept the opaque typed offer references onto the intent — the contract moves to OFFER_SELECTED, the bridge from requirement to plan.",
        link: { kind: "operation", id: "offers_accept", label: "Accept offer references" },
      },
      {
        title: "Activate and observe",
        detail:
          "Activate the contract, then read the lifecycle observation: state, execution status and statements. Physical connectivity is never claimed by API success.",
        link: { kind: "operation", id: "intent_lifecycle", label: "Read the lifecycle observation" },
      },
      {
        title: "Reproduce through the API Explorer",
        detail:
          "Re-run any step as a real HTTP request in the Explorer and read the envelope, the response headers and the verbatim reason codes. The same requests your integration will make.",
        link: { kind: "route", id: "/developers/explorer", label: "The API Explorer" },
      },
    ],
    relatedConcepts: ["application-capability", "connectivity-contract", "offer", "demo-fulfillment-journey"],
    relatedOperations: [
      "application_self",
      "intent_create",
      "intent_get",
      "offers_accept",
      "contract_activate",
      "intent_lifecycle",
    ],
  },
  {
    id: "understand-connectivity-contract",
    title: "Understand a connectivity contract",
    purpose:
      "Read any contract like an operator: what was requested, why the state is what it is, and what ADCOS is doing about it.",
    steps: [
      {
        title: "Open the contracts workspace",
        detail:
          "Every contract the application owns, filterable by lifecycle state. The workspace is the portfolio view behind the connectivity area.",
        link: { kind: "route", id: "/connectivity", label: "The contracts workspace" },
      },
      {
        title: "Open the contract's detail page",
        detail:
          "The detail page teaches the object before exposing its fields: identity, what was requested, why the flow state is what it is, the plan binding, evidence and assurance, the full representation, and API reproduction.",
        link: { kind: "route", id: "/connectivity/contracts/[id]", label: "A contract's detail page" },
      },
      {
        title: "Read what was requested",
        detail:
          "Requirements and hard constraints render verbatim — opaque typed references with provenance, and constraint kinds with their params. Hard constraints are immutable after creation.",
        link: { kind: "concept", id: "connectivity-contract", label: "The connectivity contract" },
      },
      {
        title: "Read the eligibility reasoning",
        detail:
          "The lifecycle observation reports the state, the execution status, the evidence class and the statements — the honest software-side projection, with the backend's note verbatim.",
        link: { kind: "operation", id: "intent_lifecycle", label: "The lifecycle observation" },
      },
      {
        title: "Read the plan binding",
        detail:
          "The plan binds as execution_scope and execution_artifacts references — the execution-artifact reference IS the plan binding; the console renders it verbatim rather than interpreting it.",
        link: { kind: "concept", id: "execution-plan", label: "The execution plan" },
      },
      {
        title: "Reproduce the reads",
        detail:
          "Every read on the page is a real operation: re-run it in the Explorer with the same path and body to see the exact envelope your integration receives.",
        link: { kind: "route", id: "/developers/explorer", label: "The API Explorer" },
      },
    ],
    relatedConcepts: ["connectivity-contract", "eligibility", "execution-plan", "assurance"],
    relatedOperations: [
      "contracts_list",
      "contract_get",
      "intent_lifecycle",
      "contract_usage",
      "contract_assurance",
    ],
  },
  {
    id: "understand-provider-selection",
    title: "Understand why a provider was selected",
    purpose:
      "Understand why a provider was — or would be — selected, and exactly what this deployment exposes about that reasoning.",
    steps: [
      {
        title: "Start from the accepted offers",
        detail:
          "Provider selection shows up on the contract as the accepted offer references: opaque typed material with provenance, never interpreted by the console.",
        link: { kind: "concept", id: "offer", label: "The offer" },
      },
      {
        title: "Read the plan binding",
        detail:
          "The execution plan is what got composed over the accepted offer. On the contract it binds as execution_scope and execution_artifacts references.",
        link: { kind: "concept", id: "execution-plan", label: "The execution plan" },
      },
      {
        title: "See the provider/adapter facts that are exposed",
        detail:
          "The Networks page shows the deterministic runtime composition — provider, adapter, access technology, standard — and states the provider-owned boundary explicitly.",
        link: { kind: "route", id: "/networks", label: "The Networks page" },
      },
      {
        title: "Know the honest limit",
        detail:
          "Provider eligibility decisions are not exposed by this deployment — no provider list, ranking or selection-decision operation exists on the accepted boundary. What you can inspect is the recorded outcome (accepted offers, plan composition), not the provider-side deliberation.",
        link: { kind: "concept", id: "eligibility", label: "Eligibility — what is exposed" },
      },
      {
        title: "Run the demonstration to see composition end to end",
        detail:
          "The deterministic demonstration shows the full chain including the composition facts the execution leg records — the closest honest view of a selection actually at work.",
        link: { kind: "operation", id: "demo_contract_fulfillment", label: "Run the demonstration" },
      },
    ],
    relatedConcepts: [
      "offer",
      "provider-capability",
      "execution-plan",
      "eligibility",
      "provider-adapter-boundary",
    ],
    relatedOperations: ["intent_get", "contract_get", "demo_contract_fulfillment"],
  },
  {
    id: "diagnose-fulfillment-failure",
    title: "Diagnose a failed fulfillment",
    purpose:
      "Work a failed fulfillment from symptom to verbatim reason code to next action — without inventing a cause.",
    steps: [
      {
        title: "Check the runtime is healthy",
        detail:
          "Readiness distinguishes a live runtime from a degraded one — consumed backends report their state and detail. The shell's indicator polls it; Settings shows the full document.",
        link: { kind: "operation", id: "readyz", label: "Read the runtime readiness" },
      },
      {
        title: "Read the lifecycle observation",
        detail:
          "contract_state, execution_status, statements and the note — the honest software-side projection. A FAILED state is reported, never explained away.",
        link: { kind: "operation", id: "intent_lifecycle", label: "The lifecycle observation" },
      },
      {
        title: "Inspect the evidence",
        detail:
          "The records behind the position: observations and attestations with producer, confidence and sources. In this deployment they are SOFTWARE class, honestly labeled.",
        link: { kind: "route", id: "/evidence", label: "The Evidence page" },
      },
      {
        title: "Find the verbatim reason code",
        detail:
          "The error workbench shows the backend's reason verbatim with title, detail and next-action guidance, plus the reproducible request. Unknown reasons stay unknown — no invented semantics.",
        link: { kind: "route", id: "/settings/errors", label: "The error workbench" },
      },
      {
        title: "Reproduce the failing request",
        detail:
          "Re-run the exact operation in the Explorer with the same body and see the typed error envelope first-hand — the fastest way to a precise diagnosis.",
        link: { kind: "route", id: "/developers/explorer", label: "The API Explorer" },
      },
      {
        title: "Learn the canonical failures",
        detail:
          "The canonical vocabulary — resource-unknown, invalid-transition, capability-denied, contract-terminal, not-yet-valid, expired — maps to human guidance without replacing the code.",
        link: { kind: "docs", id: "errors", label: "The canonical reason codes" },
      },
    ],
    relatedConcepts: ["fulfillment", "eligibility", "evidence"],
    relatedOperations: ["readyz", "intent_lifecycle", "contract_get"],
  },
  {
    id: "handle-degraded-connectivity",
    title: "Handle degraded connectivity",
    purpose:
      "Know what DEGRADED means for a contract, what the console can honestly show today, and what to do next.",
    steps: [
      {
        title: "See which contracts are degraded",
        detail:
          "Filter the contracts list by state — DEGRADED is a lifecycle state with its own visible tone in the console, never a silent condition.",
        link: { kind: "operation", id: "contracts_list", label: "List contracts by state" },
      },
      {
        title: "Read the honest lifecycle position",
        detail:
          "The lifecycle observation reports the degraded state with its statements and the backend's note — a reported position, never a fabricated cause.",
        link: { kind: "operation", id: "intent_lifecycle", label: "The lifecycle observation" },
      },
      {
        title: "Understand what replanning would do",
        detail:
          "Replanning is the explicit re-composition over the same hard constraints, with the reasoning and evidence presented — never an unexplained provider handoff.",
        link: { kind: "concept", id: "replan-failover", label: "Replan / failover" },
      },
      {
        title: "Know the current exposure limit",
        detail:
          "Replan events are not currently exposed by this deployment — the backend capability exists in the architecture, but this console cannot inspect live replan events until the HTTP surface exposes them. The Replanning surface in the Fulfillment area states this plainly and shows only a labeled structure preview.",
        link: { kind: "route", id: "/fulfillment", label: "The Fulfillment workspace" },
      },
      {
        title: "Check the platform side",
        detail:
          "Readiness shows whether a consumed backend degraded — sometimes the contract state and the platform state tell one story together.",
        link: { kind: "operation", id: "readyz", label: "Read the runtime readiness" },
      },
      {
        title: "Decide the terminal path if needed",
        detail:
          "If the contract should end, termination is the honest terminal command — recorded with a condition and a reason, visible thereafter in the lifecycle.",
        link: { kind: "operation", id: "contract_terminate", label: "Terminate the contract" },
      },
    ],
    relatedConcepts: ["replan-failover", "fulfillment", "eligibility"],
    relatedOperations: ["contracts_list", "intent_lifecycle", "readyz", "contract_terminate"],
  },
  {
    id: "integrate-adcos-api",
    title: "Integrate the ADCOS API",
    purpose:
      "Wire your own backend into the ADCOS HTTP API — authentication, the operation surface, errors and events.",
    steps: [
      {
        title: "Authenticate as your application",
        detail:
          "Every developer-API call runs as the authenticated application; the contract principal is derived from it. Credentials follow backend issuance and reveal rules and are never persisted in the browser.",
        link: { kind: "concept", id: "application-capability", label: "Application and capability" },
      },
      {
        title: "Learn the operation surface",
        detail:
          "Exactly 25 operations — 21 developer-API operations plus 4 platform routes — from the coverage registry. Unsupported operations never appear callable: the Explorer is generated from the same registry.",
        link: { kind: "route", id: "/developers/explorer", label: "The API Explorer" },
      },
      {
        title: "Understand envelopes, idempotency and limits",
        detail:
          "Responses carry typed envelopes with request ids, rate-limit surfaces and idempotency information; mutations require an idempotency key (the console's client sends one automatically).",
        link: { kind: "docs", id: "api", label: "The API documentation" },
      },
      {
        title: "Handle errors by verbatim reason",
        detail:
          "The backend's reason codes are the only error vocabulary — map them to guidance, never replace them. The error workbench shows the full anatomy live.",
        link: { kind: "route", id: "/settings/errors", label: "The error workbench" },
      },
      {
        title: "Register webhooks for events",
        detail:
          "Register an endpoint for observation event types and watch the delivery attempts — push instead of polling. The response carries a key id only; no secret material.",
        link: { kind: "operation", id: "endpoint_register", label: "Register a webhook endpoint" },
      },
      {
        title: "Inspect your own requests",
        detail:
          "The request inspector captures the console-made requests with reproducible curl — the fastest way to turn a console action into your integration's code.",
        link: { kind: "route", id: "/developers/requests", label: "The request inspector" },
      },
    ],
    relatedConcepts: ["application-capability", "webhook", "policy"],
    relatedOperations: ["application_self", "endpoint_register", "endpoints_list", "deliveries_list"],
  },
  {
    id: "integrate-provider-adapter",
    title: "Build or integrate a provider adapter",
    purpose:
      "Understand the provider/adapter seam and what integrating a provider into ADCOS involves — honestly scoped to what this console exposes.",
    steps: [
      {
        title: "Understand the boundary",
        detail:
          "Providers supply capabilities through adapters; ADCOS composes them without owning provider-native topology, routing or subscriber authority. No universal topology graph exists or is implied.",
        link: { kind: "concept", id: "provider-adapter-boundary", label: "The provider/adapter boundary" },
      },
      {
        title: "See a working (deterministic) adapter",
        detail:
          "The deterministic reference adapters ARE the sandbox providers — no provider claim is made. The composition facts they report (provider, adapter, access technology, standard) are the shape a real adapter reports.",
        link: { kind: "route", id: "/networks", label: "The Networks page" },
      },
      {
        title: "Trace an adapter through the chain",
        detail:
          "The demonstration's execution leg records the composition facts — the adapter's contribution to a fulfilled contract, visible end to end in one deterministic document.",
        link: { kind: "operation", id: "demo_contract_fulfillment", label: "Run the demonstration" },
      },
      {
        title: "Know what is not exposed here",
        detail:
          "No adapter registration, provider management or provider-health operation exists on the accepted boundary — integrating a provider is a backend/architecture concern this console does not gate. The console's role is inspecting what composed adapters report.",
        link: { kind: "concept", id: "provider-capability", label: "Provider capability" },
      },
      {
        title: "Verify constraints survive composition",
        detail:
          "Whatever an adapter offers, the plan-verification gate re-verifies that every candidate plan preserves the contract's hard constraints — a provider can never weaken them.",
        link: { kind: "concept", id: "connectivity-contract", label: "The connectivity contract" },
      },
    ],
    relatedConcepts: ["provider-adapter-boundary", "provider-capability", "execution-plan"],
    relatedOperations: ["demo_contract_fulfillment"],
  },
];
