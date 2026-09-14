import type { Metadata } from "next";
import { SdkPage } from "@/features/docs";

export const metadata: Metadata = {
  title: "SDKs",
  description:
    "The honest state of ADCOS SDKs — and the API-first surface, the typed client and curl available today.",
};

/**
 * The SDKs page — HONEST: no ADCOS SDK exists today, and the page says
 * so (the §17 pattern) instead of presenting fabricated packages.
 * Part of the Console V2 documentation system (DEC-0128, Task 3).
 */
export default function DocsSdkPage() {
  return <SdkPage />;
}
