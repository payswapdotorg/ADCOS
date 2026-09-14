import type { Metadata } from "next";
import { Suspense } from "react";
import { RequestInspectorView } from "@/features/requests";

export const metadata: Metadata = {
  title: "Request Inspector",
};

/**
 * /developers/requests — the global Request Inspector.
 *
 * The Suspense boundary covers useSearchParams (the ?request=<sequence>
 * deep link other surfaces build via requestsHref()); the view itself is
 * the client composition in features/requests.
 */
export default function DevelopersRequestsPage() {
  return (
    <Suspense fallback={null}>
      <RequestInspectorView />
    </Suspense>
  );
}
