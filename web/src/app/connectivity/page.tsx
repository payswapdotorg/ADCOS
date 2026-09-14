import type { Metadata } from "next";
import { ContractsIndexView } from "@/features/contracts";

export const metadata: Metadata = {
  title: "Connectivity",
};

/**
 * Connectivity — the contracts workbench (Worker 2, plan Task 5): the
 * contracts index (search, the REAL backend state filter, validity
 * overlap), the contract detail lifecycle chain, and the builder (linked
 * here and from the command palette). The server page is a thin shell;
 * the view is the client surface that reads through the session client.
 */
export default function ConnectivityPage() {
  return <ContractsIndexView />;
}
