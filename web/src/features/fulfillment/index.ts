/**
 * Fulfillment feature (Worker 2 — plan Task 7: fulfillment + execution).
 *
 * The chain Contract → Plan → Execution → Provider → Evidence → Assurance
 * rendered from the deterministic demonstration document (the only
 * execution leg this deployment has — SOFTWARE evidence, never physical
 * connectivity), plus the in-memory demonstration-run registry.
 */

export const FULFILLMENT_FEATURE = {
  area: "fulfillment",
  route: "/fulfillment",
  owner: "worker-2",
  chain: ["Contract", "Plan", "Execution", "Provider", "Evidence", "Assurance"],
} as const;

// the shared in-memory run registry (presentation data only — re-exported
// so Home and Fulfillment can import from one place)
export {
  DEFAULT_DEMO_INSTANT,
  __resetDemoRunsForTests,
  getDemoRuns,
  registerDemoRun,
  subscribeDemoRuns,
  useDemoRuns,
  type DemoRunRecord,
} from "./demo-runs";

export { FulfillmentOverview } from "./overview-view";
export {
  DEMO_DETERMINISM_NOTE,
  RunDetailView,
} from "./run-detail-view";
export {
  parseDemoDocument,
  type DemoDocumentView,
} from "./demo-document";
