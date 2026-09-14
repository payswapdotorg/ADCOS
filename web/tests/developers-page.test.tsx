/**
 * Developers page tests — the workspace surface (station A):
 *
 * - the application identity card renders from the session profile
 *   and the page's own re-fetch (request reproduced in place, the
 *   envelope's request_id and API version surfaced);
 * - the credentials view states the handling/issuance/rotate rules
 *   AS THEY ARE and NEVER echoes credential material;
 * - the disconnected state shows connect guidance and fires NO
 *   authenticated read (never fake application data);
 * - a failed applicationSelf renders the backend reason VERBATIM
 *   while the connect-time profile stays labeled honestly.
 *
 * Deterministic, no network: fetch mocked at the global boundary over
 * real fixture shapes; rendered inside the REAL SessionProvider with
 * the real connect() flow.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { DevelopersWorkspace } from "@/features/developers";
import { __resetRequestLogForTests } from "@/features/requests/request-log";
import {
  FIXTURE_APPLICATION,
  FIXTURE_ENDPOINTS_LIST,
  FIXTURE_SESSION,
} from "./developers-fixtures";
import {
  APPLICATION_ROUTE,
  envelope,
  errorEnvelope,
  renderBare,
  renderWithSession,
  routeFetch,
  trackedFetch,
} from "./developers-harness";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/developers",
  useParams: () => ({}),
  useRouter: () => ({
    push: pushMock,
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
  pushMock.mockClear();
});

describe("Developers — the workspace page", () => {
  it("renders the application identity card from the page's own re-fetch (every member verbatim)", async () => {
    const fetchMock = routeFetch({
      ...APPLICATION_ROUTE,
      "GET /api/2.0/webhook-endpoints": envelope(FIXTURE_ENDPOINTS_LIST),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<DevelopersWorkspace />, fetchMock);

    // the identity card (instant paint from the session profile, then
    // the page's own re-fetch)
    const card = await screen.findByTestId("application-identity-card");
    expect(card).toBeInTheDocument();
    expect(screen.getByText(FIXTURE_APPLICATION.application_name)).toBeInTheDocument();
    expect(screen.getByText(FIXTURE_APPLICATION.application_id)).toBeInTheDocument();
    expect(screen.getByText(FIXTURE_APPLICATION.developer_id)).toBeInTheDocument();
    expect(screen.getByText("sandbox")).toBeInTheDocument();
    // issued_at / valid_until render in BOTH the identity card and the
    // credentials view — both occurrences are backend truth
    expect(
      screen.getAllByText(FIXTURE_APPLICATION.issued_at).length,
    ).toBeGreaterThanOrEqual(2);
    expect(
      screen.getAllByText(FIXTURE_APPLICATION.valid_until).length,
    ).toBeGreaterThanOrEqual(2);
    // the application status renders through the Status vocabulary
    expect(
      screen
        .getAllByTestId("status-root")
        .some((node) => node.getAttribute("data-value") === "active"),
    ).toBe(true);

    // the page's own re-fetch resolved: fresh-truth labeling with the
    // envelope's request_id, and the API version from the envelope
    await waitFor(() => {
      expect(
        screen.getByText(/request_id: sha256:harness_request_id/),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("API version")).toBeInTheDocument();
    expect(screen.getByText("2.0")).toBeInTheDocument();

    // the request is reproduced in place (path + curl form)
    expect(
      screen.getAllByText("/api/2.0/application").length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByText("curl -X GET '/api/2.0/application'"),
    ).toBeInTheDocument();

    // the connect-time snapshot notice is GONE once fresh truth landed
    expect(
      screen.queryByText(/Session profile \(loaded at connect time\)/),
    ).toBeNull();
  });

  it("states the credential rules as they are and never echoes credential material", async () => {
    const fetchMock = routeFetch({
      ...APPLICATION_ROUTE,
      "GET /api/2.0/webhook-endpoints": envelope(FIXTURE_ENDPOINTS_LIST),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<DevelopersWorkspace />, fetchMock);

    await screen.findByTestId("credentials-state");

    // masked — the secret is never displayed after connection
    const masked = screen.getByTestId("credential-masked");
    expect(masked).toHaveTextContent(/never displayed after connection/);

    // the issuance/reveal rules AS THEY ARE (in-memory only, cleared
    // on reload; out-of-band sandbox issuance; no rotate/revoke
    // endpoints in the accepted surface)
    const rules = screen.getByTestId("credential-rules");
    expect(rules).toHaveTextContent(/in memory only/i);
    expect(rules).toHaveTextContent(/cleared on reload/i);
    expect(rules).toHaveTextContent(/out-of-band/i);
    expect(rules).toHaveTextContent(
      /No credential rotate or revoke endpoints exist/i,
    );

    // the session credential NEVER renders anywhere on the page
    expect(document.body.textContent).not.toContain(FIXTURE_SESSION.credential);
    expect(document.body.textContent).not.toContain("dasec_");
  });

  it("shows connect guidance while disconnected and fires NO authenticated read", async () => {
    const fetchMock = trackedFetch({});
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<DevelopersWorkspace />);

    // the honest gate: connect guidance, never fake application data
    expect(screen.getByTestId("connect-guidance")).toBeInTheDocument();
    expect(screen.getByText("Connect application")).toBeInTheDocument();
    // the guidance reproduces the request the connect flow validates against
    expect(screen.getByText("/api/2.0/application")).toBeInTheDocument();
    expect(
      screen.queryByText(FIXTURE_APPLICATION.application_name),
    ).toBeNull();
    expect(
      screen.queryByTestId("application-identity-card"),
    ).toBeNull();

    // NOTHING was fetched while disconnected
    await waitFor(() => {
      expect(fetchMock).not.toHaveBeenCalled();
    });
  });

  it("renders a failed applicationSelf with the reason VERBATIM and the profile labeled honestly", async () => {
    let applicationCalls = 0;
    const fetchMock = routeFetch({
      // the connect() call succeeds; the page's OWN re-fetch fails —
      // the exact shape of a credential expiring mid-session
      "GET /api/2.0/application": () => {
        applicationCalls += 1;
        if (applicationCalls === 1) {
          return envelope(FIXTURE_APPLICATION);
        }
        return {
          __status: 401,
          body: errorEnvelope(
            "authentication-invalid",
            "the credential is no longer accepted",
            401,
          ),
        };
      },
      "GET /api/2.0/webhook-endpoints": envelope(FIXTURE_ENDPOINTS_LIST),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<DevelopersWorkspace />, fetchMock);

    // the connect-time profile still paints (real data, honestly labeled)
    await screen.findByText(FIXTURE_APPLICATION.application_name);

    // the re-fetch failure renders with the reason code VERBATIM
    await waitFor(() => {
      expect(screen.getByTestId("error-reason")).toHaveTextContent(
        "authentication-invalid",
      );
    });
    expect(
      screen.getByText(/the credential is no longer accepted/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Session profile \(loaded at connect time\)/),
    ).toBeInTheDocument();

    // retry re-fires the read through the typed client
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => {
      expect(applicationCalls).toBeGreaterThanOrEqual(3);
    });
  });
});
