/**
 * The shared component-test harness for Worker 2's feature suites.
 *
 * Pattern (from Worker 1's shell suite): fetch is mocked at the GLOBAL
 * boundary with a router over REAL fixture envelopes; the page under
 * test renders inside the REAL SessionProvider, and `renderWithSession`
 * drives the real connect() flow (GET /api/2.0/application) so the
 * session's client carries the exact auth headers the backend expects.
 * NO network, ever.
 *
 * Each test file additionally hoists these module mocks:
 *
 *   vi.mock("next/navigation", () => ({
 *     usePathname: () => "/",
 *     useParams: () => ({}),
 *     useRouter: () => ({ push: pushMock, replace: vi.fn(), back: vi.fn(),
 *                         forward: vi.fn(), refresh: vi.fn(), prefetch: vi.fn() }),
 *     useSearchParams: () => new URLSearchParams(),
 *   }));
 *   vi.mock("next/link", () => ({
 *     default: ({ href, children, ...props }: Record<string, unknown>) => (
 *       <a href={href as string} {...props}>{children as never}</a>
 *     ),
 *   }));
 */

import { useEffect, useState, type ReactNode } from "react";
import { render } from "@testing-library/react";
import type { Mock } from "vitest";
import { SessionProvider, useSession } from "@/lib/session";
import { FIXTURE_APPLICATION, FIXTURE_SESSION } from "./fixtures";

/* ------------------------------------------------------------------ *
 * The fetch boundary mock
 * ------------------------------------------------------------------ */

export function okResponse(body: unknown, status = 200): Response {
  return {
    status,
    ok: status >= 200 && status < 300,
    headers: {
      get: (name: string) =>
        name.toLowerCase() === "x-adcos-request-id"
          ? "sha256:harness_request_id"
          : null,
    },
    text: async () => JSON.stringify(body),
  } as unknown as Response;
}

export function errorResponse(body: unknown, status: number): Response {
  return okResponse(body, status);
}

/** The enveloped success shape every /api/2.0 read returns. */
export function envelope<T>(data: T): unknown {
  return {
    api_version: "2.0",
    environment: "sandbox",
    request_id: "sha256:harness_request_id",
    data,
    idempotency: { key: "harness", replayed: false },
    rate_limit: { limit: 1000, remaining: 999, reset_at: "2026-09-13T00:00:01Z" },
  };
}

/**
 * Route fetch by `METHOD path` (path matching is exact OR prefix when the
 * route key ends with `*`). Handlers return the raw body; the harness
 * wraps successes automatically. Unmatched routes fail the test loudly.
 */
export function routeFetch(
  routes: Record<string, unknown>,
): Mock & { calls: [string, RequestInit][] } {
  const fn = ((path: string, init?: RequestInit) => {
    const method = (init?.method ?? "GET").toUpperCase();
    const key = `${method} ${path}`;
    const match =
      key in routes
        ? key
        : Object.keys(routes)
            .filter((candidate) => candidate.endsWith("*"))
            .find((candidate) => key.startsWith(candidate.slice(0, -1)));
    if (match === undefined) {
      return Promise.resolve(
        errorResponse(
          {
            api_version: "2.0",
            environment: "sandbox",
            request_id: "sha256:harness_unmatched",
            error: {
              canonical_reason: "",
              environment: "sandbox",
              http_status: 404,
              message: `harness has no route for ${key}`,
              reason: "route-unknown",
              request_id: "sha256:harness_unmatched",
              resource_id: "",
              retry_after: "",
              retryable: false,
            },
          },
          404,
        ),
      );
    }
    const body = routes[match];
    // function handlers compute the body/response per call (counters, ...)
    const resolved =
      typeof body === "function" ? (body as () => unknown)() : body;
    if (resolved instanceof Response) {
      return Promise.resolve(resolved);
    }
    if (
      typeof resolved === "object" &&
      resolved !== null &&
      "__status" in (resolved as Record<string, unknown>)
    ) {
      const wrapper = resolved as { __status: number; body: unknown };
      return Promise.resolve(errorResponse(wrapper.body, wrapper.__status));
    }
    return Promise.resolve(okResponse(resolved));
  }) as unknown as Mock & { calls: [string, RequestInit][] };
  return fn;
}

/** The application envelope every connected session needs first. */
export const APPLICATION_ROUTE: Record<string, unknown> = {
  "GET /api/2.0/application": envelope(FIXTURE_APPLICATION),
};

/* ------------------------------------------------------------------ *
 * The provider renderers
 * ------------------------------------------------------------------ */

/** Renders inside the REAL SessionProvider with a real connect() flow. */
export function renderWithSession(
  ui: ReactNode,
  fetchImpl: ReturnType<typeof routeFetch>,
) {
  function Connector() {
    const { connect, status } = useSession();
    const [started, setStarted] = useState(false);
    useEffect(() => {
      if (started || status !== "disconnected") return;
      setStarted(true);
      void connect(FIXTURE_SESSION.applicationId, FIXTURE_SESSION.credential);
    }, [started, status, connect]);
    return null;
  }
  return render(
    <SessionProvider>
      <Connector />
      {ui}
    </SessionProvider>,
  );
}

/** Renders inside the SessionProvider WITHOUT connecting (platform-only). */
export function renderBare(ui: ReactNode) {
  return render(<SessionProvider>{ui}</SessionProvider>);
}
