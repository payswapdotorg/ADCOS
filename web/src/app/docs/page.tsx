import type { Metadata } from "next";
import { DocsHome } from "@/features/docs";

export const metadata: Metadata = {
  title: "Docs",
  description:
    "The ADCOS documentation home — Start here, Concepts, Guides, API, SDKs, Errors, Troubleshooting and Reference.",
};

/**
 * The docs home — the documentation information architecture itself
 * (the frozen V2 design §9 tree) with the route-local search. Part of
 * the Console V2 documentation system (DEC-0128, Task 3).
 */
export default function DocsHomePage() {
  return <DocsHome />;
}
