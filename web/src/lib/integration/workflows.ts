/**
 * The Build with ADCOS integration registry — the WORKFLOWS.
 *
 * The 2026-09-15 program, Task 1 of the frozen plan: the ordered
 * lifecycle sequence per pattern — the design-§4 canonical stages with
 * their real operation mappings — as the lookup surface the Build UI
 * (W2) and the API/LLM education surfaces (W3) consume.
 *
 * The no-second-authority rule: this is a VIEW over
 * `INTEGRATION_PATTERNS[i].lifecycle` (the very same step objects), not
 * a second workflow registry. It exists only so consumers can key the
 * lifecycle by pattern id; the pattern registry remains the authority.
 */

import { INTEGRATION_PATTERNS } from "./patterns";
import type { IntegrationLifecycleStep, IntegrationPatternId } from "./types";

/**
 * The ordered lifecycle steps per pattern id — the same step objects the
 * pattern registry carries (a view, never a second authority).
 */
export const INTEGRATION_WORKFLOWS: Record<IntegrationPatternId, IntegrationLifecycleStep[]> =
  Object.fromEntries(
    INTEGRATION_PATTERNS.map((pattern) => [pattern.id, pattern.lifecycle]),
  ) as Record<IntegrationPatternId, IntegrationLifecycleStep[]>;

/** Look up one pattern's lifecycle by pattern id — `undefined` for unknown ids (honest unknown state). */
export function integrationWorkflowById(id: string): IntegrationLifecycleStep[] | undefined {
  return INTEGRATION_WORKFLOWS[id as IntegrationPatternId];
}
