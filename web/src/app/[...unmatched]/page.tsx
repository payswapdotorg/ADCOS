import { notFound } from "next/navigation";

/**
 * The production-routing catch-all — the console owns EVERY path the
 * deployment's routing table does not reserve for the Python runtime
 * (`/api/*`, `/healthz`, `/readyz`, `/demo/*` — root `vercel.json`).
 *
 * In local dev the Next dev server renders `not-found.tsx` for unknown
 * paths natively. In the deployed legacy `builds`+`routes` topology the
 * routing layer only invokes the Next function for paths that MATCH a
 * built route — without this catch-all, unknown root paths (e.g.
 * `/nonexistent`) are answered by the PLATFORM's static 404 and the
 * console's delivered not-found boundary never renders. This route
 * exists solely to funnel every unmatched console-space path into that
 * boundary, which presents the miss with the backend's own unknown-route
 * reason vocabulary (`route-unknown`) — never an invented surface.
 */
export default function UnmatchedPage() {
  notFound();
}
