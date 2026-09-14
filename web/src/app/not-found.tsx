import Link from "next/link";
import { ErrorState } from "@/components/ui";
import { AdcosApiError } from "@/lib/api/errors";

/**
 * The not-found boundary. The console has exactly ONE error vocabulary —
 * the backend's — so an unknown console route is presented as the
 * backend would present an unknown API route: reason "route-unknown",
 * VERBATIM, with the request descriptor that "failed".
 */

export default function NotFound() {
  const error = new AdcosApiError({
    status: 404,
    reason: "route-unknown",
    message: "No console route matches this path.",
    request: { method: "GET", path: "this route" },
  });

  return (
    <div className="mx-auto w-full max-w-workbench px-gutter py-rhythm">
      <h1 className="text-xl font-semibold">Page not found</h1>
      <p className="mt-1 text-sm text-ink-muted">No console route matches this path.</p>

      <div className="mt-4">
        <ErrorState error={error} />
      </div>

      <div className="mt-4">
        <Link
          href="/"
          className="rounded bg-accent px-3 py-1.5 text-sm font-medium text-accent-ink hover:bg-accent-strong"
        >
          Home
        </Link>
      </div>
    </div>
  );
}
