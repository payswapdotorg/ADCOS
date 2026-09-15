import type { Metadata } from "next";
import { BuildWithAdcos } from "@/features/integration/build-with-adcos";

export const metadata: Metadata = {
  title: "Build with ADCOS",
  description: "Design an application integration with ADCOS and retrieve the canonical LLM integration context.",
};

export default function BuildWithAdcosPage() {
  return <BuildWithAdcos />;
}
