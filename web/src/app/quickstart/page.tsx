import type { Metadata } from "next";
import { QuickstartView } from "@/features/playbooks/quickstart";

export const metadata: Metadata = {
  title: "Quickstart",
};

/**
 * Quickstart — the guided nine-step beginner journey (plan Task 5, the
 * frozen V2 design §6). Thin server file; the interactive journey is
 * the client feature (features/playbooks/quickstart*).
 */
export default function QuickstartPage() {
  return <QuickstartView />;
}
