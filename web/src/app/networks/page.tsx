import type { Metadata } from "next";
import { NetworksView } from "@/features/networks";

export const metadata: Metadata = {
  title: "Networks",
};

/**
 * Networks — provider and adapter facts as exposed by this deployment
 * (plan Task 6). Thin server file; the interactive view is the client
 * feature.
 */
export default function NetworksPage() {
  return <NetworksView />;
}
