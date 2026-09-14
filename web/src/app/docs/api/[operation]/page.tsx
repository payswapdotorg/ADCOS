import type { Metadata } from "next";
import { OperationPage } from "@/features/docs";

export const metadata: Metadata = {
  title: "Operation",
  description:
    "One ADCOS API operation: purpose, prerequisites, lifecycle position, field explanations, related concepts and reason codes.",
};

/**
 * One operation's page — GENERATED from the coverage registry (the
 * REAL method/path/capability, verbatim) joined with the operation
 * education; an unknown operation id renders the honest not-found
 * state. No execution control here — the API Explorer owns execution.
 *
 * Next 15: params is a Promise — await it, then hand the decoded id to
 * the feature component (the contract-detail convention).
 */
export default async function DocsApiOperationPage({
  params,
}: {
  params: Promise<{ operation: string }>;
}) {
  const { operation } = await params;
  return <OperationPage operationId={decodeURIComponent(operation)} />;
}
