import type { Metadata } from "next";
import { TroubleshootingPage } from "@/features/docs";

export const metadata: Metadata = {
  title: "Troubleshooting",
  description:
    "Diagnosis paths for connect failures, unknown routes, degraded coordination and replanning.",
};

/**
 * The Troubleshooting hub — curated diagnosis paths linking to the
 * related concepts, guides, operations and reason codes, honest about
 * the deployment's limits (§17). Part of the Console V2 documentation
 * system (DEC-0128, Task 3).
 */
export default function DocsTroubleshootingPage() {
  return <TroubleshootingPage />;
}
