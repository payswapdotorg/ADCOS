/**
 * Eligibility / policy presentation (Worker 2 — plan Task 6).
 *
 * The cross-cutting presentation layer for Worker 2's areas: WHY a flow
 * state is what it is, from backend reason data only (notes, reason
 * codes, evidence classes, statements vocabulary — all rendered
 * VERBATIM), plus the shared in-memory read discipline (`useAdcosRead`)
 * and the object-section composition primitives the feature pages are
 * built from. The console never re-implements policy in TypeScript.
 */

export {
  useAdcosRead,
  type AdcosReadState,
} from "./use-adcos-read";
export {
  FlowStatePanel,
  RefList,
  RefValue,
  VerbatimNote,
} from "./flow-state";
export { ObjectFieldGrid, ObjectSection } from "./object-section";
