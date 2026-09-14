import type { Metadata } from "next";
import { BuilderView } from "@/features/contracts";

export const metadata: Metadata = {
  title: "New connectivity intent",
};

/**
 * The contract builder — guided fields that map 1:1 to the canonical
 * members, advanced canonical-JSON editing with unknown-member
 * preservation, and the exact POST /api/2.0/intents request visible
 * before submit.
 */
export default function NewContractPage() {
  return <BuilderView />;
}
