import type { Metadata } from "next";
import { FulfillmentTourView } from "@/features/tour/fulfillment-tour";

export const metadata: Metadata = {
  title: "The fulfillment tour",
};

/**
 * The fulfillment tour — the deterministic demonstration as a teaching
 * surface (plan Task 5, the frozen V2 design §7): Requirement →
 * Eligibility → Plan → Execution → Evidence → Assurance, with the
 * Explain-this / View-object / View-API-request / View-API-response
 * affordances at every stage. Thin server file; the interactive tour is
 * the client feature.
 */
export default function TourPage() {
  return <FulfillmentTourView />;
}
