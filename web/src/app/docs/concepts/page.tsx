import type { Metadata } from "next";
import { ConceptIndex } from "@/features/docs";

export const metadata: Metadata = {
  title: "Concepts",
  description:
    "Every first-class ADCOS concept, documented with the same six questions.",
};

/**
 * The Concepts index — GENERATED from the Task-1 concept registry
 * (every concept with its term and summary) with the route-local
 * search. Part of the Console V2 documentation system (DEC-0128,
 * Task 3).
 */
export default function DocsConceptsPage() {
  return <ConceptIndex />;
}
