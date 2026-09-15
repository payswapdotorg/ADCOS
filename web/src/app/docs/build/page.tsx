import type { Metadata } from "next";
import { BuildSectionHub } from "@/features/docs";

export const metadata: Metadata = {
  title: "Build with ADCOS",
  description:
    "Choose an integration pattern: the five ways a product fits ADCOS into its architecture, with the boundary, lifecycle and production checklist behind each.",
};

/**
 * /docs/build — the Build with ADCOS section hub ("Choose an integration
 * pattern"). Part of the Build with ADCOS & LLM Integration experience
 * (the frozen design §8, plan Task 4); the section pages live at
 * /docs/build/[id] and the interactive surface at /build.
 */
export default function DocsBuildPage() {
  return <BuildSectionHub />;
}
