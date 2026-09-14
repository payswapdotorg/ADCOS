import type { Metadata } from "next";
import { PlaybookIndex } from "@/features/playbooks";

export const metadata: Metadata = {
  title: "Playbooks",
  description:
    "Goal-oriented ADCOS guided paths — every step a real console operation, route or documentation page.",
};

/**
 * The Playbooks index — GENERATED from the guide registry (the seven
 * playbooks grouped by experience goal) with the route-local search.
 * The Console V2 learning experience — DEC-0128, Task 6.
 */
export default function PlaybooksPage() {
  return <PlaybookIndex />;
}
