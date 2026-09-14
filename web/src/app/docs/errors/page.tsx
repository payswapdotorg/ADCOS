import type { Metadata } from "next";
import { ErrorsPage } from "@/features/docs";

export const metadata: Metadata = {
  title: "Errors",
  description:
    "The canonical ADCOS reason codes, verbatim, with human guidance that explains but never replaces them.",
};

/**
 * The Errors reference — the canonical reason codes VERBATIM from the
 * error taxonomy, with guidance derived through the canonical
 * presentation module. Part of the Console V2 documentation system
 * (DEC-0128, Task 3).
 */
export default function DocsErrorsPage() {
  return <ErrorsPage />;
}
