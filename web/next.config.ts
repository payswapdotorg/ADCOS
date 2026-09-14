import type { NextConfig } from "next";

/**
 * The console owns NO backend. `/api/*`, `/healthz`, `/readyz` and `/demo/*`
 * are proxied to the Python ADCOS runtime in development (same-origin only —
 * there are deliberately NO route handlers under src/app/api/). In production
 * (Vercel) the `vercel.json` routes array performs the same split: every
 * backend path goes to the Python function, everything else serves this
 * console. See web/README.md.
 */
const backend = process.env.ADCOS_BACKEND_URL ?? "http://127.0.0.1:8088";

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
