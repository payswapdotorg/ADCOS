import type { Metadata } from "next";
import { BuildPatternDocPage } from "@/features/docs";

export const metadata: Metadata = {
  title: "Build with ADCOS",
  description:
    "One Build with ADCOS page: an integration pattern, the lifecycle implementation, or the production checklist.",
};

/**
 * One Build with ADCOS section page — the curated page for a known slug
 * (application / gateway-relay / fleet-subscriber / provider / lifecycle
 * / production-checklist); an unknown slug renders the honest not-found
 * state.
 *
 * Next 15: params is a Promise — await it, then hand the decoded id to
 * the feature component (the guide-page convention).
 */
export default async function DocsBuildIdPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <BuildPatternDocPage pageId={decodeURIComponent(id)} />;
}
