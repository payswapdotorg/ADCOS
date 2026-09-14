import type { Metadata } from "next";
import { Suspense } from "react";
import { ApiExplorerView } from "@/features/api-explorer";

export const metadata: Metadata = {
  title: "API Explorer",
};

/**
 * /developers/explorer — the registry-driven API Explorer.
 *
 * The Suspense boundary covers useSearchParams (the ?operation= deep
 * link the search providers use); the view itself is the client
 * composition in features/api-explorer.
 */
export default function DevelopersExplorerPage() {
  return (
    <Suspense fallback={null}>
      <ApiExplorerView />
    </Suspense>
  );
}
