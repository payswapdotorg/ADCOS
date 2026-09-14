/**
 * The Console V2 education registry — the barrel.
 *
 * The DEC-0128 program, Task 1 of the frozen plan: the typed contracts,
 * the three registries (concepts, operations, guides) and the lookup
 * helpers the V2 learning surfaces consume. The registries reference
 * the accepted coverage-registry operation ids and the canonical
 * backend vocabularies — never a second endpoint catalog. The lookup
 * helpers return `undefined` for unknown ids BY DESIGN: callers must
 * render honest unknown states, never a fabricated definition.
 */

import { CONCEPTS } from "./concepts";
import { GUIDES } from "./guides";
import { OPERATION_EDUCATION } from "./operations";
import type {
  ConceptDefinition,
  EDUCATION_REGISTRY as EducationRegistry,
  GuideDefinition,
  OperationLearningDefinition,
} from "./types";

export type {
  ConceptDefinition,
  ConceptId,
  GuideDefinition,
  GuideId,
  LearningLink,
  OperationId,
  OperationLearningDefinition,
} from "./types";
// The aggregating interface re-exports under the alias `EducationRegistry`
// because a barrel cannot re-export a type and declare a const of the same
// name (TS2323); the interface itself remains `EDUCATION_REGISTRY` in
// ./types, its mandated name.
export type { EducationRegistry };
export { CONCEPTS } from "./concepts";
export { GUIDES } from "./guides";
export { OPERATION_EDUCATION } from "./operations";

/**
 * The aggregated education registry — a VIEW over the three registries
 * (the very same array exports), not a second authority.
 */
export const EDUCATION_REGISTRY: EducationRegistry = {
  concepts: CONCEPTS,
  operations: OPERATION_EDUCATION,
  guides: GUIDES,
};

/** Look up one concept by id — `undefined` for unknown ids (render an honest unknown state). */
export function getConcept(id: string): ConceptDefinition | undefined {
  return CONCEPTS.find((concept) => concept.id === id);
}

/** Look up one operation's education by the backend's operation id — `undefined` for unknown ids. */
export function getOperationEducation(operation: string): OperationLearningDefinition | undefined {
  return OPERATION_EDUCATION.find((entry) => entry.operation === operation);
}

/** Look up one guide by id — `undefined` for unknown ids (render an honest unknown state). */
export function getGuide(id: string): GuideDefinition | undefined {
  return GUIDES.find((guide) => guide.id === id);
}
