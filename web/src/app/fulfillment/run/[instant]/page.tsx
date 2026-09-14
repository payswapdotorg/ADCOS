import type { Metadata } from "next";
import { RunDetailView } from "@/features/fulfillment";

export const metadata: Metadata = {
  title: "Demonstration run",
};

/**
 * One demonstration run — the full fulfillment chain rendered from the
 * deterministic demonstration document. The instant is the run's identity:
 * identical instant → identical document (the POST replay is safe).
 */
export default async function DemonstrationRunPage({
  params,
}: {
  params: Promise<{ instant: string }>;
}) {
  const { instant } = await params;
  return <RunDetailView instant={decodeURIComponent(instant)} />;
}
