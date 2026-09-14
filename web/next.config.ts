import type { NextConfig } from "next";

/**
 * The console's web boundary configuration.
 *
 * CRITICAL INVARIANT (plan Task 1): the Next.js app owns presentation ONLY.
 * There are NO route handlers under `src/app/api/` — the Python backend owns
 * `/api/*` (plus `/healthz`, `/readyz`, `/demo/*`) in every environment:
 *
 * - local development: the rewrites below proxy those paths to the local
 *   sandbox runtime (`ADCOS_BACKEND_URL`, default http://127.0.0.1:8088);
 * - production (Vercel): the root `vercel.json` routes them to the Python
 *   function before the console is ever consulted (these rewrites are then
 *   unreachable, which is exactly the intended fail-safe shape).
 *
 * All console API calls therefore use RELATIVE, same-origin URLs only —
 * no CORS assumptions anywhere.
 */
const backend = process.env.ADCOS_BACKEND_URL || "http://127.0.0.1:8088";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${backend}/api/:path*` },
      { source: "/healthz", destination: `${backend}/healthz` },
      { source: "/readyz", destination: `${backend}/readyz` },
      { source: "/demo/:path*", destination: `${backend}/demo/:path*` },
    ];
  },
};

export default nextConfig;
