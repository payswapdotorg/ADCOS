/**
 * Replan feature (Worker 2 — plan Task 7: replan/failover explanation).
 *
 * Makes autonomous changes explicit: violated requirement/threshold,
 * observed vs required value, detection time, candidates, eligibility/
 * policy reasoning, proposed action and supporting evidence. A provider
 * handoff is NEVER presented as an unexplained side effect.
 *
 * This deployment exposes no replan decisions — the page is an honest
 * explainable surface (what replanning is, what would trigger it, the
 * current truth, and the card shape ready for when the backend exposes
 * them). No events are fabricated.
 */

export const REPLAN_FEATURE = {
  area: "replan",
  route: "/fulfillment/replan",
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

export {
  REPLAN_CURRENT_TRUTH,
  REPLAN_WIREFRAME_LABEL,
  ReplanView,
} from "./replan-view";
