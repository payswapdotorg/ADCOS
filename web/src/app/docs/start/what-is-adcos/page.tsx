import type { Metadata } from "next";
import { WhatIsAdcosPage } from "@/features/docs";

export const metadata: Metadata = {
  title: "What is ADCOS?",
  description:
    "The product explanation: what ADCOS does, what it deliberately is not, and the mental model in one line.",
};

/**
 * What is ADCOS? — the curated product explanation (the frozen V2
 * design §5/§6 anchor paragraph). Part of the Console V2 documentation
 * system (DEC-0128, Task 3).
 */
export default function DocsWhatIsAdcosPage() {
  return <WhatIsAdcosPage />;
}
