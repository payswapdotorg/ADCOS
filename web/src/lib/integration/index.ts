/**
 * The Build with ADCOS integration registry — the barrel.
 *
 * The 2026-09-15 program: the canonical integration registry (types,
 * patterns, capabilities, workflows, the blueprint builder) plus the
 * LLM Integration Pack (the context builder, the operation projection
 * and the five public-asset renderers). This is the ONE surface W2
 * (the Build experience) and W3 (API/LLM education) consume — a frozen
 * interface contract; the underlying modules enforce the
 * no-second-authority rule at load time: every operation id resolves in
 * `@/lib/api/coverage`, every concept id in `@/lib/education`, every
 * webhook event id in the frozen vocabulary, and every reason code in
 * the canonical error taxonomy.
 */

export type {
  IntegrationBlueprint,
  IntegrationCapability,
  IntegrationLifecycleStep,
  IntegrationPattern,
  IntegrationPatternId,
} from "./types";

export {
  INTEGRATION_PATTERNS,
  integrationPatternById,
  patternsUsingOperation,
} from "./patterns";

export {
  INTEGRATION_CAPABILITIES,
  capabilitiesUsingOperation,
  integrationCapabilityById,
} from "./capabilities";

export { INTEGRATION_WORKFLOWS, integrationWorkflowById } from "./workflows";

export { buildIntegrationBlueprint } from "./blueprint";

export {
  buildLlmContext,
  buildLlmOperations,
  renderCapabilitiesJson,
  renderIntegrationContextJson,
  renderLlmsFullTxt,
  renderLlmsTxt,
  renderOperationsJson,
} from "./llm-pack";
