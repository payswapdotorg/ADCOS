import type { Metadata } from "next";
import { AreaPlaceholder } from "@/components/shell/area-placeholder";

export const metadata: Metadata = {
  title: "Fulfillment",
};

/**
 * Fulfillment — placeholder surface for Worker 2.
 *
 * The frozen UX spec's fulfillment map: the chain Contract → Plan →
 * Execution → Provider → Evidence → Assurance, and replan/failover that
 * is always explained (never an unexplained provider handoff).
 */
export default function FulfillmentPage() {
  return (
    <AreaPlaceholder
      title="Fulfillment"
      intro="This area is being implemented (Worker 2 — fulfillment & replanning)."
      map={[
        {
          title: "The fulfillment chain",
          description:
            "Contract → Plan → Execution → Provider → Evidence → Assurance; detail pages answer what ADCOS actually did — status, timeline, plan, execution milestones, errors, replans and supporting evidence.",
        },
        {
          title: "Replan / failover",
          description:
            "Violated requirement or threshold, observed versus required value, detection time, candidates, eligibility/policy reasoning, proposed action/state and supporting evidence; never an unexplained provider handoff.",
        },
      ]}
    />
  );
}
