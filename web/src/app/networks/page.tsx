import type { Metadata } from "next";
import { AreaPlaceholder } from "@/components/shell/area-placeholder";

export const metadata: Metadata = {
  title: "Networks",
};

/**
 * Networks — placeholder surface for Worker 2.
 *
 * The frozen UX spec's provider/network map. Provider-owned topology
 * data is labeled explicitly — it is provider claims, not ADCOS truth.
 */
export default function NetworksPage() {
  return (
    <AreaPlaceholder
      title="Networks"
      intro="This area is being implemented (Worker 2 — provider & network surface)."
      map={[
        {
          title: "Provider identity",
          description:
            "Provider identity, adapter identity/version, supported capabilities, and eligibility-relevant facts.",
        },
        {
          title: "Observed health & use",
          description:
            "Observed health/performance where available, current contract use, and provider limitations.",
        },
        {
          title: "Evidence & activity",
          description:
            "Evidence and activity for the provider and its adapter.",
        },
        {
          title: "Provider-owned topology",
          description:
            "Provider-owned topology data labeled explicitly as such (provider claims, not ADCOS-verified truth).",
        },
      ]}
    />
  );
}
