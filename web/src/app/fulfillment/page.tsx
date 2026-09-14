import type { Metadata } from "next";
import { FulfillmentOverview } from "@/features/fulfillment";

export const metadata: Metadata = {
  title: "Fulfillment",
};

/**
 * Fulfillment — the chain Contract → Plan → Execution → Provider →
 * Evidence → Assurance, realized in this deployment through the
 * deterministic contract-fulfillment demonstration (SOFTWARE evidence),
 * the browser-session run registry, and the authenticated contract list.
 */
export default function FulfillmentPage() {
  return <FulfillmentOverview />;
}
