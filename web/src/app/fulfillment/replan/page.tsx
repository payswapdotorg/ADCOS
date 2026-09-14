import type { Metadata } from "next";
import { ReplanView } from "@/features/replan";

export const metadata: Metadata = {
  title: "Replanning",
};

/**
 * Replanning — an honest explainable surface: what replanning is, what
 * would trigger it, the current truth about this deployment (no replan
 * decisions exposed yet), and the card shape ready for when they are.
 */
export default function ReplanPage() {
  return <ReplanView />;
}
