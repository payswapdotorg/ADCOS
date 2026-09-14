import type { Metadata } from "next";
import { AssuranceView } from "@/features/assurance";

export const metadata: Metadata = {
  title: "Assurance",
};

/**
 * Assurance — the assurance view (Worker 3, Part C): per contract, the
 * OBLIGATION REFERENCES verbatim (opaque refs with their provenance),
 * the contract state, the honest notes, and each obligation linked to
 * its contract and its evidence chain. No invented metric dashboards.
 */
export default function AssurancePage() {
  return <AssuranceView />;
}
