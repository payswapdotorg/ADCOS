import type { Metadata } from "next";
import { GuidePage } from "@/features/docs";

export const metadata: Metadata = {
  title: "Guide",
  description:
    "One ADCOS playbook: its purpose, its steps with their links, and the related concepts and operations.",
};

/**
 * One guide's page — GENERATED from the Task-1 guide registry; an
 * unknown slug renders the honest not-found state.
 *
 * Next 15: params is a Promise — await it, then hand the decoded id to
 * the feature component (the contract-detail convention).
 */
export default async function DocsGuidePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <GuidePage guideId={decodeURIComponent(id)} />;
}
