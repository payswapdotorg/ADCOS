import type { Metadata } from "next";
import { AreaPlaceholder } from "@/components/shell/area-placeholder";

export const metadata: Metadata = {
  title: "Assurance",
};

/**
 * Assurance — placeholder surface for Worker 3.
 *
 * The frozen UX spec's assurance map: contract objectives tied to the
 * evidence that supports them and to any action they produced.
 */
export default function AssurancePage() {
  return (
    <AreaPlaceholder
      title="Assurance"
      intro="This area is being implemented (Worker 3 — evidence, developers, assurance)."
      map={[
        {
          title: "Contract objectives",
          description:
            "Supported contract objectives such as latency, availability, capacity and provider health, linked to underlying evidence and any resulting action.",
        },
      ]}
    />
  );
}
