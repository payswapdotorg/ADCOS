import type { Metadata } from "next";
import { PlaybookPage } from "@/features/playbooks";

export const metadata: Metadata = {
  title: "Playbook",
  description:
    "One ADCOS playbook: its purpose, its steps with their real links, and the related concepts and operations.",
};

/**
 * One playbook's page — GENERATED from the Task-1 guide registry; an
 * unknown slug renders the honest not-found state.
 *
 * Next 15: params is a Promise — await it, then hand the decoded id to
 * the feature component (the docs guide-page convention).
 *
 * The Console V2 learning experience — DEC-0128, Task 6.
 */
export default async function PlaybookGuidePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <PlaybookPage guideId={decodeURIComponent(id)} />;
}
