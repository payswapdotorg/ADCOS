import type { Metadata } from "next";
import { AreaPlaceholder } from "@/components/shell/area-placeholder";

export const metadata: Metadata = {
  title: "Connectivity",
};

/**
 * Connectivity — placeholder surface for Worker 2.
 *
 * The frozen UX spec's connectivity map: contracts list/search, contract
 * detail (the full lifecycle chain), and the guided contract builder.
 */
export default function ConnectivityPage() {
  return (
    <AreaPlaceholder
      title="Connectivity"
      intro="This area is being implemented (Worker 2 — contracts & connectivity)."
      map={[
        {
          title: "Contracts",
          description:
            "Search/filter by status, geography, capability, provider, assurance state, validity, created/updated; rows show contract ID, lifecycle state, current fulfillment/provider, assurance state, last activity.",
        },
        {
          title: "Contract detail",
          description:
            "Identity, lifecycle (Requirements → Eligibility → Plan → Execution → Assurance → Continuous fulfillment), requirements/constraints, eligibility result, current plan, execution, provider/network relationship, assurance, evidence lineage, replanning history, related developer application, API/JSON inspector, activity timeline.",
        },
        {
          title: "Contract builder",
          description:
            "Guided fields first, advanced canonical fields second, inline constraint explanation, canonical API field names, backend validation, “View API request” before submit.",
        },
      ]}
    />
  );
}
