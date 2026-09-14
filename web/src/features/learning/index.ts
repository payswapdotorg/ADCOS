/**
 * The Console V2 learning primitives — the barrel.
 *
 * The DEC-0128 program, Task 2 of the frozen plan (the V2 learning
 * experience design §8/§10/§13/§14): the reusable, prop-driven,
 * context-free presentation primitives that every V2 surface composes —
 * W2's home/quickstart/tour, W3's playbooks/explorer-education and the
 * object pages. They are PURE PRESENTATION over the Task-1 education
 * registry (`@/lib/education`): no fetch, no stores, never a second
 * authority — every rendered education string comes from the REAL
 * registries, and unknown ids render honest unknown states.
 */

export {
  ConceptLink,
  UnknownConceptAffordance,
  UNKNOWN_CONCEPT_TEST_ID,
} from "./concept-link";
export {
  ConceptExplainer,
  Disclosure,
  CONCEPT_EDUCATION_TEST_ID,
  CONCEPT_EXPLAINER_TRIGGER_TEST_ID,
} from "./concept-explainer";
export type { ConceptExplainerTriggerProps } from "./concept-explainer";
export {
  NextStep,
  NextSteps,
  docsHref,
  NEXT_STEPS_TEST_ID,
} from "./next-step";
export {
  ObjectEducation,
  OBJECT_EDUCATION_TEST_ID,
} from "./object-education";
export type { ObjectEducationSection } from "./object-education";
export type { LearningLink } from "@/lib/education";
