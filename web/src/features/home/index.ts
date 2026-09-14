/**
 * Home feature (Worker 2 — plan Task 4: Home + system health).
 *
 * Publishes the intended content map (from the frozen UX spec) so the
 * placeholder page and, later, the real dashboard share one vocabulary.
 */

export interface HomeContentEntry {
  title: string;
  description: string;
}

export const HOME_CONTENT_MAP: HomeContentEntry[] = [
  {
    title: "Contract health",
    description:
      "Managed connectivity contracts by lifecycle state, each row linked to the contract detail.",
  },
  {
    title: "Active fulfillment",
    description:
      "Currently executing contract→plan→execution chains with their latest milestones.",
  },
  {
    title: "Degraded providers / backends",
    description:
      "Backend and provider states from /readyz and observed health, with degraded states visible.",
  },
  {
    title: "Recent activity",
    description:
      "Latest API activity linked to the underlying resource and request inspector.",
  },
  {
    title: "Action-required items",
    description:
      "Attention-worthy states (degraded, failed, revoked, expiring) linked to their objects.",
  },
  {
    title: "Environment state",
    description:
      "Mode and environment from backend readiness — never a local assumption.",
  },
];
