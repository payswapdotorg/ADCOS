import { Suspense } from "react";
import type { Metadata } from "next";
import { ErrorWorkbench } from "@/features/errors";

export const metadata: Metadata = {
  title: "Error workbench",
};

/**
 * The error workbench (Worker 3, Part C) — the FROZEN path
 * /settings/errors (features/errors/link.tsx): the session's captured
 * errors with the full anatomy, deep-linking one captured request via
 * ?request=<sequence>. The Suspense boundary satisfies useSearchParams
 * during static prerendering.
 */
export default function ErrorWorkbenchPage() {
  return (
    <Suspense
      fallback={
        <div
          aria-busy="true"
          className="mx-auto w-full max-w-workbench px-gutter py-rhythm"
        >
          <div className="flex flex-col gap-3">
            <div className="h-6 w-56 animate-pulse rounded bg-raised" />
            <div className="h-24 w-full animate-pulse rounded bg-raised" />
          </div>
        </div>
      }
    >
      <ErrorWorkbench />
    </Suspense>
  );
}
