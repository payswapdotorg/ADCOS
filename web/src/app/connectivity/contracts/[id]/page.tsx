import type { Metadata } from "next";
import { ContractDetailView } from "@/features/contracts";

export const metadata: Metadata = {
  title: "Contract detail",
};

/**
 * Contract detail — the full lifecycle chain (Requirements → Eligibility →
 * Plan → Execution → Assurance → Continuous fulfillment) with every
 * supported mutation (accept offers, activate, terminate, grant/renew/
 * revoke lease), the activity timeline and the raw contract JSON.
 *
 * Next 15: params is a Promise — await it, then hand the decoded id to
 * the client view.
 */
export default async function ContractDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ContractDetailView contractId={decodeURIComponent(id)} />;
}
