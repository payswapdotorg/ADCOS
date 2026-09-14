import type { Metadata } from "next";
import { FirstContractPage } from "@/features/docs";

export const metadata: Metadata = {
  title: "First connectivity contract",
  description:
    "The first contract walkthrough — from recording an intent to inspecting evidence, honest about the demonstration context.",
};

/**
 * First connectivity contract — the curated walkthrough, honest about
 * the supported demo context (the frozen V2 design §6: the journey
 * must never fabricate a production capability). Part of the Console
 * V2 documentation system (DEC-0128, Task 3).
 */
export default function DocsFirstContractPage() {
  return <FirstContractPage />;
}
