import type { Metadata } from "next";
import { ApiHub } from "@/features/docs";

export const metadata: Metadata = {
  title: "API",
  description:
    "Every operation of the accepted ADCOS boundary, grouped by lifecycle area, with its education.",
};

/**
 * The API documentation hub — GENERATED from the coverage registry
 * joined with the operation education (25 operations, grouped by
 * lifecycle area, each linking to its operation page) with the
 * route-local search. Part of the Console V2 documentation system
 * (DEC-0128, Task 3).
 */
export default function DocsApiPage() {
  return <ApiHub />;
}
