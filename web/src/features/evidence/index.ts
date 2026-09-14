/**
 * Evidence feature (Worker 3 — plan Task 8: evidence explorer + detail).
 *
 * Evidence is a first-class resource with source, timestamp, evidence
 * class, provenance and related objects. SOFTWARE evidence is visibly
 * distinct from physical/network evidence EVERYWHERE (badges, filters,
 * detail copy) — see `@/lib/design/tokens` → `evidenceClassKind` and the
 * `EvidenceBadge` primitive. The explorer lists the evidence of every
 * demonstration run this console session made (demo-runs store), and the
 * legend states the badge vocabulary: the physical/network family is
 * NOT-ACHIEVABLE-BY-THIS-DEPLOYMENT.
 */

export const EVIDENCE_FEATURE = {
  area: "evidence",
  route: "/evidence",
  owner: "worker-3",
  hardRule:
    "no UI state can transform software evidence into a physical acceptance",
} as const;

export { EvidenceExplorer, EVIDENCE_EXPLORER_TEST_IDS } from "./evidence-explorer";
export {
  EvidenceClassLegend,
  EVIDENCE_LEGEND_TEST_ID,
  NOT_ACHIEVABLE_BY_THIS_DEPLOYMENT,
} from "./evidence-class-legend";
export {
  EvidenceRecordCard,
  EVIDENCE_RECORD_TEST_IDS,
} from "./evidence-record-card";
export {
  EvidenceRecordDrawer,
  EVIDENCE_RECORD_DRAWER_TEST_ID,
} from "./evidence-record-drawer";
export {
  evidenceRecordView,
  evidenceRecordsOf,
  type EvidenceRecordView,
} from "./evidence-record";
export {
  recordDemoRun,
  getDemoRuns,
  subscribeDemoRuns,
  useDemoRuns,
  __resetDemoRunsForTests,
  type DemoRun,
} from "./demo-runs";
