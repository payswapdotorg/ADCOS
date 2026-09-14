import type { Metadata } from "next";
import { StartHereHub } from "@/features/docs";

export const metadata: Metadata = {
  title: "Start here",
  description:
    "The docs on-ramp: What is ADCOS?, How ADCOS works, First connectivity contract, and the Quickstart.",
};

/**
 * The Start here hub — the three curated on-ramp pages plus the
 * Quickstart link. Part of the Console V2 documentation system
 * (DEC-0128, Task 3).
 */
export default function DocsStartPage() {
  return <StartHereHub />;
}
