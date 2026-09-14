import type { Metadata } from "next";
import { HowAdcosWorksPage } from "@/features/docs";

export const metadata: Metadata = {
  title: "How ADCOS works",
  description:
    "The mental model lifecycle, stage by stage: describe requirement → eligibility → plan → fulfillment → assurance → continuous fulfillment.",
};

/**
 * How ADCOS works — the mental model lifecycle explained stage by
 * stage, each stage linked to its concepts and operations. Part of the
 * Console V2 documentation system (DEC-0128, Task 3).
 */
export default function DocsHowItWorksPage() {
  return <HowAdcosWorksPage />;
}
