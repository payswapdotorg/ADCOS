/**
 * The Console V2 education model — the typed contracts.
 *
 * The DEC-0128 program, Task 1 of the frozen plan (the V2 learning
 * experience design §8/§16): a structured concept registry, an
 * operation-education registry and a guide registry whose cross-links
 * are machine-checkable. Every identifier here references a STABLE
 * authority — concept ids and guide ids are this registry's own frozen
 * vocabulary, operation ids mirror the accepted coverage registry
 * (`@/lib/api/coverage`) verbatim — never a second endpoint catalog.
 * Drift is meant to fail the education-registry test, not reach the UI.
 */

/* ------------------------------------------------------------------ *
 * Identifier types (the frozen vocabularies)
 * ------------------------------------------------------------------ */

/**
 * The core first-class concept ids (the V2 design §8 list, kebab-case)
 * plus the deterministic demonstration context. This union IS the
 * concept vocabulary: no concept exists outside it.
 */
export type ConceptId =
  | "connectivity-contract"
  | "provider-capability"
  | "offer"
  | "eligibility"
  | "policy"
  | "execution-plan"
  | "fulfillment"
  | "assurance"
  | "evidence"
  | "replan-failover"
  | "provider-adapter-boundary"
  | "application-capability"
  | "webhook"
  | "demo-fulfillment-journey";

/**
 * The backend's own operation ids — the EXACT 25 of the coverage
 * registry, mirrored verbatim. The operations registry carries a
 * module-load guard against `COVERAGE` and the education-registry test
 * pins the lockstep, so this union can never quietly fork the catalog.
 */
export type OperationId =
  // platform surfaces (4)
  | "healthz"
  | "readyz"
  | "demo_contract_fulfillment"
  | "platform_contract_read"
  // developer API (21)
  | "application_self"
  | "intent_create"
  | "intents_list"
  | "intent_get"
  | "intent_lifecycle"
  | "offers_accept"
  | "contract_activate"
  | "contracts_list"
  | "contract_get"
  | "contract_usage"
  | "contract_assurance"
  | "contract_terminate"
  | "lease_grant"
  | "leases_list"
  | "lease_get"
  | "lease_renew"
  | "lease_revoke"
  | "endpoints_list"
  | "endpoint_register"
  | "endpoint_get"
  | "deliveries_list";

/**
 * The guide (playbook) ids — the V2 design §11 playbook list, kebab-case.
 */
export type GuideId =
  | "first-connectivity-application"
  | "understand-connectivity-contract"
  | "understand-provider-selection"
  | "diagnose-fulfillment-failure"
  | "handle-degraded-connectivity"
  | "integrate-adcos-api"
  | "integrate-provider-adapter";

/* ------------------------------------------------------------------ *
 * The cross-reference link
 * ------------------------------------------------------------------ */

/**
 * A typed cross-reference to another education surface. The `kind`
 * selects the id vocabulary the `id` belongs to:
 * - "concept"  → a ConceptId of this registry;
 * - "operation"→ an operation id of the coverage registry;
 * - "guide"    → a GuideId of this registry;
 * - "route"    → an existing console route (the frozen route list);
 * - "docs"     → a slug of the frozen docs IA (V2 design §9).
 *
 * The id stays a plain string so the link is data, but the education
 * test resolves every link against its vocabulary and fails on the
 * first unknown id — the machine-checkable contract of design §16.
 */
export interface LearningLink {
  kind: "concept" | "operation" | "guide" | "route" | "docs";
  id: string;
  label: string;
}

/* ------------------------------------------------------------------ *
 * The registries' record shapes
 * ------------------------------------------------------------------ */

/**
 * One first-class concept definition (V2 design §8/§9): what it is,
 * why it matters, when to use it, and what actually happens in ADCOS —
 * concise by construction (summary ≤ 2 sentences; the long fields stay
 * short and the UI layer handles progressive disclosure).
 */
export interface ConceptDefinition {
  id: ConceptId;
  /** The human term, as the console's vocabulary renders it. */
  term: string;
  /** What it is — at most ~2 sentences. */
  summary: string;
  /** Why it matters to a developer. */
  whyItMatters: string;
  /** When to use / consult it. */
  whenToUse: string;
  /** What actually happens in ADCOS — including the honest exposure limits of this deployment. */
  whatHappens: string;
  /** Concept ids that should be understood first (only ids of this registry). */
  prerequisites: ConceptId[];
  /** Backend objects/resources this concept surfaces (the canonical types vocabulary). */
  relatedObjects: string[];
  /** Coverage-registry operation ids that expose this concept. */
  relatedOperations: OperationId[];
  /** Guides of this registry that walk through the concept. */
  relatedGuides: GuideId[];
  /** The API shape to show for the concept, when one applies. */
  apiLook?: { operationId: OperationId; note: string };
  /** A real runnable operation that demonstrates the concept, when one exists. */
  runnableExample?: { operationId: OperationId; label: string };
  /** Canonical reason codes that anchor this concept's troubleshooting. */
  relatedTroubleshooting: string[];
  /** Where to go next — typed links, all machine-checked. */
  nextSteps: LearningLink[];
}

/**
 * One operation's education record (V2 design §12): the Explorer
 * framing — purpose, prerequisites, lifecycle position, typical
 * sequence, the request shape's field explanations (the coverage
 * registry's OWN example fields for mutations, and the honest no-body
 * note for bodyless GETs — never invented fields), related concepts,
 * related canonical reason codes, and the next operation.
 */
export interface OperationLearningDefinition {
  /** The backend's own operation id (verbatim, from the coverage registry). */
  operation: OperationId;
  purpose: string;
  prerequisites: string;
  /** Where the operation sits in the Understand → Build → Integrate → Operate → Diagnose lifecycle. */
  lifecyclePosition: string;
  /** Where it typically falls in a working sequence of operations. */
  typicalSequence: string;
  /** Field-by-field explanations of the operation's request shape. */
  fieldExplanations: { field: string; explanation: string }[];
  relatedConcepts: ConceptId[];
  /** Canonical backend reason codes this operation can realistically produce (verbatim). */
  relatedErrors: string[];
  /** The natural next operation in the typical sequence, when one exists. */
  nextOperation?: OperationId;
  /** False only when the operation is honestly not a user action (see design §16). */
  userActionable: boolean;
  /** True only when the operation is explicitly internal-only / not-user-actionable. */
  internalOnly?: boolean;
}

/**
 * One guide (playbook) definition (V2 design §11): a goal-oriented path
 * composed from real console operations, routes and docs — registry
 * data only; the interactive playbook UIs are built on top of this.
 */
export interface GuideDefinition {
  id: GuideId;
  title: string;
  purpose: string;
  /** The path's steps; each may carry one typed link to the surface it uses. */
  steps: { title: string; detail: string; link?: LearningLink }[];
  relatedConcepts: ConceptId[];
  relatedOperations: OperationId[];
}

/**
 * The aggregated education registry — the single object the V2 learning
 * surfaces consume. It is a VIEW over the three registries, never a
 * second authority: the arrays are the same exports.
 */
export interface EDUCATION_REGISTRY {
  concepts: ConceptDefinition[];
  operations: OperationLearningDefinition[];
  guides: GuideDefinition[];
}
