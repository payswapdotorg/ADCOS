/**
 * Evidence feature (Worker 3 — plan Task 8: evidence explorer + detail).
 *
 * Evidence is a first-class resource with source, timestamp, evidence
 * class, provenance and related objects. SOFTWARE evidence is visibly
 * distinct from physical/network evidence EVERYWHERE (badges, filters,
 * detail copy) — see `@/lib/design/tokens` → `evidenceClassKind` and the
 * `EvidenceBadge` primitive. Placeholder barrel.
 */

export const EVIDENCE_FEATURE = {
  area: "evidence",
  route: "/evidence",
  owner: "worker-3",
  hardRule:
    "no UI state can transform software evidence into a physical acceptance",
} as const;
