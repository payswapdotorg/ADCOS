import type { Metadata } from "next";
import { GuideIndex } from "@/features/docs";

export const metadata: Metadata = {
  title: "Guides",
  description:
    "Goal-oriented ADCOS playbooks composed from real console operations, routes and documentation.",
};

/**
 * The Guides index — GENERATED from the Task-1 guide registry (every
 * playbook with its title, purpose and step count) with the
 * route-local search. Part of the Console V2 documentation system
 * (DEC-0128, Task 3).
 */
export default function DocsGuidesPage() {
  return <GuideIndex />;
}
