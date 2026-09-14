import type { Metadata } from "next";
import { ConceptPage } from "@/features/docs";

export const metadata: Metadata = {
  title: "Concept",
  description:
    "One ADCOS concept, documented with the six questions: what it is, why it matters, when to use it, what happens in ADCOS, what the API looks like, where to go next.",
};

/**
 * One concept's page — GENERATED from the Task-1 concept registry; an
 * unknown slug renders the honest not-found state.
 *
 * Next 15: params is a Promise — await it, then hand the decoded id to
 * the feature component (the contract-detail convention).
 */
export default async function DocsConceptPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ConceptPage conceptId={decodeURIComponent(id)} />;
}
