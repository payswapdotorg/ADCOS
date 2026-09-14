/**
 * Settings page tests — REAL captured shapes only, fetch mocked at the
 * global boundary (the station harness pattern: a router over REAL
 * fixture envelopes, the page rendered inside the REAL ThemeProvider +
 * SessionProvider with the real connect() flow). NO network, ever.
 *
 * Covers the work order's Part C3 demands:
 * - the FULL /readyz document renders (mode, environment, every backend
 *   state + detail, delegated backends) plus /healthz;
 * - the honest liveness-vs-readiness semantics are explained on the
 *   page (liveness says NOTHING about backends; readiness names them);
 * - the session summary renders the application profile (evidence_class
 *   VERBATIM) with Disconnect and the credential-policy note;
 * - the About boundary statement + the error workbench link render;
 * - the health reads fire while disconnected (unauthenticated platform
 *   surfaces).
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useEffect, useState, type ReactNode } from "react";
import { SessionProvider, useSession } from "@/lib/session";
import { ThemeProvider } from "@/lib/design/theme";
import { EVIDENCE_BADGE_TEST_IDS } from "@/components/ui";
import { __resetRequestLogForTests } from "@/features/requests/request-log";
import { __resetRecorderForTests } from "@/features/requests/recorder";
import { __resetCommandRegistryForTests } from "@/features/search/command-registry";
import SettingsPage from "@/app/settings/page";
import type { Application, Readiness } from "@/lib/api/types";

/* ------------------------------------------------------------------ *
 * Fixtures (transcribed VERBATIM from the captured sandbox shapes)
 * ------------------------------------------------------------------ */

const FIXTURE_APPLICATION: Application = {
  application_id: "sha256:c20c5f90db52d8a89c5168fdb71f522ed9648d1264330357a9cdad98532f1f01",
  application_name: "adcos:runtime:contract-fulfillment-demo",
  capabilities: [
    "assurance:read",
    "intents:read",
    "intents:write",
    "leases:read",
    "leases:write",
    "usage:read",
    "webhooks:read",
    "webhooks:write",
  ],
  developer_id: "adcos:runtime:demo-developer",
  environment: "sandbox",
  evidence_class: "sandbox-simulation",
  issued_at: "2026-09-13T00:00:00Z",
  kind: "application",
  status: "active",
  valid_until: "2036-09-13T00:00:00Z",
};

const FIXTURE_SESSION = {
  applicationId: FIXTURE_APPLICATION.application_id,
  credential: "dasec_6f0a61f4d683e1b7a06859649217ac1714552b64c93ea25509e0e7dfa0ed5b60",
};

/** GET /readyz — the sandbox shape (200, no durable backends). */
const FIXTURE_READINESS: Readiness = {
  ok: true,
  service: "adcos-runtime",
  mode: "sandbox",
  environment: "sandbox",
  backends: {},
};

/** A degraded readiness variant (200 + ok=false, two named backends). */
const FIXTURE_READINESS_DEGRADED: Readiness = {
  ok: false,
  service: "adcos-runtime",
  mode: "production",
  environment: "production",
  backends: {
    "neon-postgres": { state: "ready", detail: "wired" },
    "upstash-redis": {
      state: "unavailable",
      detail: "connection refused (degraded — ephemeral coordination only)",
    },
  },
};

/** A readiness variant with a delegated backend. */
const FIXTURE_READINESS_DELEGATED: Readiness = {
  ok: true,
  service: "adcos-runtime",
  mode: "production",
  environment: "production",
  backends: {
    "neon-postgres": { state: "ready", detail: "wired" },
  },
  delegated_backends: {
    "upstash-redis": {
      state: "wired",
      detail: "delegated to the platform integration",
    },
  },
};

const FIXTURE_HEALTHZ = { ok: true, service: "adcos-runtime" };

/* ------------------------------------------------------------------ *
 * The local harness (fetch mocked at the global boundary)
 * ------------------------------------------------------------------ */

function okResponse(body: unknown, status = 200): Response {
  const text = JSON.stringify(body);
  return {
    status,
    ok: status >= 200 && status < 300,
    headers: {
      get: (name: string) =>
        name.toLowerCase() === "x-adcos-request-id"
          ? "sha256:harness_request_id"
          : null,
      forEach: (callback: (value: string, name: string) => void) => {
        callback("sha256:harness_request_id", "X-ADCOS-Request-Id");
      },
    },
    clone: () => ({ text: async () => text }),
    text: async () => text,
  } as unknown as Response;
}

function envelope<T>(data: T): unknown {
  return {
    api_version: "2.0",
    environment: "sandbox",
    request_id: "sha256:harness_request_id",
    data,
  };
}

function routeFetch(routes: Record<string, unknown>) {
  return vi.fn((path: string, init?: RequestInit) => {
    const method = (init?.method ?? "GET").toUpperCase();
    const key = `${method} ${path}`;
    if (!(key in routes)) {
      return Promise.resolve(
        okResponse(
          { error: { reason: "route-unknown", message: `no route for ${key}` } },
          404,
        ),
      );
    }
    return Promise.resolve(okResponse(routes[key]));
  });
}

/** The settings page needs BOTH providers (theme + session). */
function Providers({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider>
      <SessionProvider>{children}</SessionProvider>
    </ThemeProvider>
  );
}

function renderWithSession(ui: ReactNode) {
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
    <Providers>
      <Connector />
      {ui}
    </Providers>,
  );
}

function renderBare(ui: ReactNode) {
  return render(<Providers>{ui}</Providers>);
}

vi.mock("next/navigation", () => ({
  usePathname: () => "/settings",
  useParams: () => ({}),
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: Record<string, unknown>) => (
    <a href={href as string} {...props}>
      {children as never}
    </a>
  ),
}));

beforeEach(() => {
  __resetRequestLogForTests();
  __resetRecorderForTests();
  __resetCommandRegistryForTests();
});

describe("Settings", () => {
  it("renders the FULL readiness document (every backend state + detail, delegated backends) and healthz, with the honest semantics note", async () => {
    const fetchMock = routeFetch({
      "GET /api/2.0/application": envelope(FIXTURE_APPLICATION),
      "GET /readyz": FIXTURE_READINESS_DELEGATED,
      "GET /healthz": FIXTURE_HEALTHZ,
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<SettingsPage />);

    const readiness = await waitFor(() => {
      return screen.getByTestId("readyz-document");
    });
    // mode + environment render from the document
    expect(within(readiness).getAllByText("production").length).toBeGreaterThanOrEqual(2);
    expect(within(readiness).getByText("adcos-runtime")).toBeInTheDocument();
    expect(within(readiness).getAllByText("true").length).toBeGreaterThan(0);

    // every backend state + detail, VERBATIM — the delegated backend is a
    // row of the FULL document too, so 2 rows carry the backend testid
    const backends = within(readiness).getAllByTestId("readyz-backend");
    expect(backends).toHaveLength(2);
    const postgres = backends.find((backend) =>
      backend.textContent?.includes("neon-postgres"),
    );
    expect(postgres).toBeDefined();
    expect(within(postgres as HTMLElement).getByText("ready")).toBeInTheDocument();
    expect(within(postgres as HTMLElement).getByText("wired")).toBeInTheDocument();

    // delegated backends render with their own state + detail
    const upstash = backends.find((backend) =>
      backend.textContent?.includes("upstash-redis"),
    );
    expect(upstash).toBeDefined();
    expect(within(upstash as HTMLElement).getByText("wired")).toBeInTheDocument();
    expect(within(readiness).getByText("delegated to the platform integration")).toBeInTheDocument();

    // healthz renders its own document
    const liveness = screen.getByTestId("healthz-document");
    expect(within(liveness).getByText("adcos-runtime")).toBeInTheDocument();
    expect(within(liveness).getAllByText("true").length).toBeGreaterThan(0);
    expect(within(liveness).getByText(/carries no backend detail/)).toBeInTheDocument();
  });

  it("renders a degraded readiness with the unavailable backend's detail and the honest empty backends note in sandbox", async () => {
    const fetchMock = routeFetch({
      "GET /readyz": FIXTURE_READINESS_DEGRADED,
      "GET /healthz": FIXTURE_HEALTHZ,
    });
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<SettingsPage />);

    const readiness = await waitFor(() => {
      return screen.getByTestId("readyz-document");
    });
    // degraded: ok false renders and the unavailable backend is named
    expect(within(readiness).getAllByText("false").length).toBeGreaterThan(0);
    const backends = within(readiness).getAllByTestId("readyz-backend");
    expect(backends).toHaveLength(2);
    const upstash = backends.find((backend) =>
      backend.textContent?.includes("upstash-redis"),
    );
    expect(upstash).toBeDefined();
    expect(within(upstash as HTMLElement).getByText("unavailable")).toBeInTheDocument();
    expect(
      within(upstash as HTMLElement).getByText(
        "connection refused (degraded — ephemeral coordination only)",
      ),
    ).toBeInTheDocument();

    // the honest semantics: liveness vs readiness, stated on the page
    const semantics = screen.getByTestId("health-semantics");
    expect(semantics.textContent).toContain("nothing about backends");
    expect(semantics.textContent).toContain("every backend and its state");
    expect(semantics.textContent).toContain("Liveness ≠ readiness");
  });

  it("states the honest sandbox empty-backends case", async () => {
    const fetchMock = routeFetch({
      "GET /readyz": FIXTURE_READINESS,
      "GET /healthz": FIXTURE_HEALTHZ,
    });
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("readyz-document")).toBeInTheDocument();
    });
    expect(
      screen.getByText(/No backends reported in the readiness document/),
    ).toBeInTheDocument();
    expect(screen.getByText(/named none/)).toBeInTheDocument();
  });

  it("renders the session summary with the evidence_class VERBATIM, the credential policy, and a working Disconnect", async () => {
    const fetchMock = routeFetch({
      "GET /api/2.0/application": envelope(FIXTURE_APPLICATION),
      "GET /readyz": FIXTURE_READINESS,
      "GET /healthz": FIXTURE_HEALTHZ,
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<SettingsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("adcos:runtime:contract-fulfillment-demo"),
      ).toBeInTheDocument();
    });

    const session = screen.getByTestId("settings-session");
    // the application profile, verbatim
    expect(within(session).getByText("sandbox")).toBeInTheDocument();
    expect(within(session).getByText("active")).toBeInTheDocument();
    expect(within(session).getByText("intents:read")).toBeInTheDocument();

    // the application's evidence_class renders VERBATIM (software family)
    const badge = within(session).getByTestId(EVIDENCE_BADGE_TEST_IDS.root);
    expect(badge.getAttribute("data-kind")).toBe("software");
    expect(badge).toHaveTextContent("sandbox-simulation");

    // the credential-policy note (memory only, cleared on reload — by design)
    const policy = screen.getByTestId("settings-credential-policy");
    expect(policy.textContent).toContain("memory only");
    expect(policy.textContent).toContain("cleared on reload");
    expect(policy.textContent).toContain("never displayed after connect");

    // the credential VALUE never renders anywhere on the page
    expect(document.body.textContent).not.toContain(FIXTURE_SESSION.credential);

    // Disconnect works (the reconnect affordance appears)
    fireEvent.click(within(session).getByText("Disconnect"));
    await waitFor(() => {
      expect(screen.getByText("Connect application…")).toBeInTheDocument();
    });
  });

  it("renders the About boundary statement and the link to the error workbench", async () => {
    const fetchMock = routeFetch({
      "GET /readyz": FIXTURE_READINESS,
      "GET /healthz": FIXTURE_HEALTHZ,
    });
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("settings-about")).toBeInTheDocument();
    });
    const about = screen.getByTestId("settings-about");
    expect(about.textContent).toContain("not a second authority");
    expect(about.textContent).toContain("owns all state");

    expect(
      screen
        .getAllByRole("link")
        .some((link) => link.getAttribute("href") === "/settings/errors"),
    ).toBe(true);
  });

  it("reads health while disconnected (unauthenticated platform surfaces)", async () => {
    const fetchMock = routeFetch({
      "GET /readyz": FIXTURE_READINESS_DEGRADED,
      "GET /healthz": FIXTURE_HEALTHZ,
    });
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("readyz-document")).toBeInTheDocument();
    });
    const readyzCalls = fetchMock.mock.calls.filter(([path]) => path === "/readyz");
    const healthzCalls = fetchMock.mock.calls.filter(([path]) => path === "/healthz");
    expect(readyzCalls).toHaveLength(1);
    expect(healthzCalls).toHaveLength(1);
  });
});
