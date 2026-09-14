import type { Metadata } from "next";
import { EvidenceExplorer } from "@/features/evidence";

export const metadata: Metadata = {
  title: "Evidence",
};

/**
 * Evidence — the evidence explorer (Worker 3, Part C): every
 * demonstration run's evidence records with the evidence_class VERBATIM
 * and the SOFTWARE vs physical/network distinction carried visibly
 * (spec non-negotiable #7 — SOFTWARE never becomes a physical PASS).
 */
export default function EvidencePage() {
  return <EvidenceExplorer />;
}
