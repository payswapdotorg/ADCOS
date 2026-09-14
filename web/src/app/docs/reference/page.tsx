import type { Metadata } from "next";
import { ReferencePage } from "@/features/docs";

export const metadata: Metadata = {
  title: "Reference",
  description:
    "The frozen ADCOS vocabularies: lifecycle states, evidence classes, capability grants and canonical objects.",
};

/**
 * The Reference page — the vocabularies drawn from the real registries
 * (the state vocabulary of the design tokens, the evidence classes of
 * the canonical classifier, the capability grants derived from
 * coverage). Part of the Console V2 documentation system (DEC-0128,
 * Task 3).
 */
export default function DocsReferencePage() {
  return <ReferencePage />;
}
