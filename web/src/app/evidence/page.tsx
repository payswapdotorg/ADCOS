import type { Metadata } from "next";
import { AreaPlaceholder } from "@/components/shell/area-placeholder";

export const metadata: Metadata = {
  title: "Evidence",
};

/**
 * Evidence — placeholder surface for Worker 3.
 *
 * The frozen UX spec's evidence map: evidence as a first-class resource,
 * with the SOFTWARE vs physical/network class distinction rendered
 * visibly apart (spec non-negotiable #7).
 */
export default function EvidencePage() {
  return (
    <AreaPlaceholder
      title="Evidence"
      intro="This area is being implemented (Worker 3 — evidence, developers, assurance)."
      map={[
        {
          title: "Evidence as a first-class resource",
          description:
            "Evidence with source, timestamp, evidence class (SOFTWARE vs physical/network — visibly distinct), provenance and related objects.",
        },
      ]}
    />
  );
}
