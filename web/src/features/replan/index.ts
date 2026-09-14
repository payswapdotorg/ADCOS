/**
 * Replan feature (Worker 2 — plan Task 7: replan/failover explanation).
 *
 * Makes autonomous changes explicit: violated requirement/threshold,
 * observed vs required value, detection time, candidates, eligibility/
 * policy reasoning, proposed action and supporting evidence. A provider
 * handoff is NEVER presented as an unexplained side effect. Placeholder
 * barrel.
 */

export const REPLAN_FEATURE = {
  area: "replan",
  route: "/fulfillment",
  owner: "worker-2",
  mustShow: [
    "violated requirement or threshold",
    "observed versus required value",
    "detection time",
    "candidates",
    "eligibility/policy reasoning",
    "proposed action/state",
    "supporting evidence",
  ],
} as const;
