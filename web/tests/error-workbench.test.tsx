/**
 * Error workbench tests — REAL captured shapes only, fetch mocked at the
 * global boundary (the station harness pattern: a router over REAL
 * fixture envelopes, the workbench rendered inside the REAL
 * SessionProvider with the real connect() flow, plus a driver component
 * that fires the requests whose failures land in the captured log).
 * NO network, ever.
 *
 * Covers the work order's Part C4 demands:
 * - the full anatomy renders: what happened (message), why (reason
 *   VERBATIM), the affected resource, the guidance (KNOWN dictionary +
 *   the honest generic fallback for unknown codes), and the
 *   reproducible API form (curl, credential masked);
 * - the Retry button re-issues through the typed client when the
 *   backend marked the error retryable (and reports the outcome);
 * - the deep-link preselection (?request=<sequence>) expands exactly
 *   the linked captured request, with the honest stale-link note;
 * - synthesized client-side codes (backend-unreachable) are labeled as
 *   such — never presented as backend reasons;
 * - the honest empty state when every request succeeded.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useEffect, useState, type ReactNode } from "react";
import { SessionProvider, useSession } from "@/lib/session";
import { ensureRequestRecorder, __resetRecorderForTests } from "@/features/requests/recorder";
import { __resetRequestLogForTests } from "@/features/requests/request-log";
import { ErrorWorkbench } from "@/features/errors/workbench";
import type { Application } from "@/lib/api/types";

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

const UNKNOWN_CONTRACT_ID =
  "sha256:000000000000000000000000000000000000000000000000000000000000dead";

/** 404 — resource-unknown carrying the canonical unknown-contract (a KNOWN code;
 * the shape client.test.ts pins for an unknown contract read). */
const NOT_FOUND_ERROR = {
  api_version: "2.0",
  environment: "sandbox",
  request_id: "sha256:deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
  error: {
    canonical_reason: "unknown-contract",
    environment: "sandbox",
    http_status: 404,
    message: `contract ${UNKNOWN_CONTRACT_ID} is unknown`,
    reason: "resource-unknown",
    request_id: "sha256:deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
    resource_id: "",
    retry_after: "",
    retryable: false,
  },
} as const;

/** 401 — authentication-invalid (a KNOWN code, distinct guidance). */
const AUTH_ERROR = {
  api_version: "2.0",
  environment: "sandbox",
  request_id: "sha256:1111111111111111111111111111111111111111111111111111111111111111",
  error: {
    canonical_reason: "",
    environment: "sandbox",
    http_status: 401,
    message: "the credential was rejected for this application",
    reason: "authentication-invalid",
    request_id: "sha256:1111111111111111111111111111111111111111111111111111111111111111",
    resource_id: "",
    retry_after: "",
    retryable: false,
  },
} as const;

/** 429 — rate-limited (retryable TRUE — an unknown-to-the-dictionary code). */
const RATE_LIMITED_ERROR = {
  api_version: "2.0",
  environment: "sandbox",
  request_id: "sha256:2222222222222222222222222222222222222222222222222222222222222222",
  error: {
    canonical_reason: "",
    environment: "sandbox",
    http_status: 429,
    message: "rate limit exceeded for this application",
    reason: "rate-limited",
    request_id: "sha256:2222222222222222222222222222222222222222222222222222222222222222",
    resource_id: "",
    retry_after: "2026-09-14T01:00:01Z",
    retryable: true,
  },
} as const;

/** 422 — a code OUTSIDE the known dictionary (the honest fallback path). */
const MYSTERY_ERROR = {
  api_version: "2.0",
  environment: "sandbox",
  request_id: "sha256:3333333333333333333333333333333333333333333333333333333333333333",
  error: {
    canonical_reason: "",
    environment: "sandbox",
    http_status: 422,
    message: "something odd happened on the backend",
    reason: "mystery-code",
    request_id: "sha256:3333333333333333333333333333333333333333333333333333333333333333",
    resource_id: "sha256:affected-resource",
    retry_after: "",
    retryable: false,
  },
} as const;

const EMPTY_CONTRACTS_LIST = { items: [], next_cursor: "", has_more: false };

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

function errorResponse(body: unknown, status: number): Response {
  return okResponse(body, status);
}

function envelope<T>(data: T): unknown {
  return {
    api_version: "2.0",
    environment: "sandbox",
    request_id: "sha256:harness_request_id",
    data,
  };
}

type RouteValue = unknown;

/**
 * Route fetch by `METHOD path`. Handlers may be a raw body, a
 * `{__status, body}` wrapper (non-2xx), or a function computing either
 * per call. Unmatched routes fail loudly with route-unknown.
 */
function routeFetch(routes: Record<string, RouteValue>) {
  return vi.fn((path: string, init?: RequestInit) => {
    const method = (init?.method ?? "GET").toUpperCase();
    const key = `${method} ${path}`;
    if (!(key in routes)) {
      return Promise.resolve(
        errorResponse(
          { error: { reason: "route-unknown", message: `no route for ${key}` } },
          404,
        ),
      );
    }
    const resolved =
      typeof routes[key] === "function"
        ? (routes[key] as () => unknown)()
        : routes[key];
    if (
      typeof resolved === "object" &&
      resolved !== null &&
      "__status" in (resolved as Record<string, unknown>)
    ) {
      const wrapper = resolved as { __status: number; body: unknown };
      return Promise.resolve(errorResponse(wrapper.body, wrapper.__status));
    }
    return Promise.resolve(okResponse(resolved));
  });
}

/** The mutable search params the mocked next/navigation returns. */
const mockSearchParams = { current: new URLSearchParams() };

vi.mock("next/navigation", () => ({
  usePathname: () => "/settings/errors",
  useParams: () => ({}),
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  useSearchParams: () => mockSearchParams.current,
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: Record<string, unknown>) => (
    <a href={href as string} {...props}>
      {children as never}
    </a>
  ),
}));

/** Fires the contracts list read once a session is connected. */
function ListContractsDriver() {
  const { status, client } = useSession();
  useEffect(() => {
    if (status !== "connected") return;
    void client.listContracts().catch(() => undefined);
  }, [status, client]);
  return null;
}

/** Fires the contracts list read, then a doomed contract read (sequential). */
function TwoFailuresDriver() {
  const { status, client } = useSession();
  useEffect(() => {
    if (status !== "connected") return;
    void (async () => {
      await client.listContracts().catch(() => undefined);
      await client.getContract(UNKNOWN_CONTRACT_ID).catch(() => undefined);
    })();
  }, [status, client]);
  return null;
}

function renderWorkbench(ui: ReactNode) {
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

beforeEach(() => {
  __resetRequestLogForTests();
  __resetRecorderForTests();
  mockSearchParams.current = new URLSearchParams();
});

describe("Error workbench", () => {
  it("renders the full anatomy: message, reason VERBATIM, known-code guidance, affected resource, and the masked curl reproduction", async () => {
    const fetchMock = routeFetch({
      "GET /api/2.0/application": envelope(FIXTURE_APPLICATION),
      "GET /api/2.0/contracts": { __status: 404, body: NOT_FOUND_ERROR },
    });
    vi.stubGlobal("fetch", fetchMock);
    ensureRequestRecorder();

    renderWorkbench(
      <>
        <ListContractsDriver />
        <ErrorWorkbench />
      </>,
    );

    const card = await waitFor(() => {
      return screen.getByTestId("captured-error");
    });

    // what happened — the backend's own message, verbatim
    expect(
      within(card).getByText(`contract ${UNKNOWN_CONTRACT_ID} is unknown`),
    ).toBeInTheDocument();

    // why — the reason code VERBATIM (chip in the header and the anatomy)
    const reasons = within(card).getAllByTestId("workbench-reason");
    expect(reasons.length).toBeGreaterThanOrEqual(1);
    for (const reason of reasons) {
      expect(reason).toHaveTextContent("resource-unknown");
    }

    // guidance from the KNOWN dictionary (title + next action)
    expect(within(card).getByText("Contract not found")).toBeInTheDocument();
    expect(
      within(card).getByText(/The contract does not exist or is not visible/),
    ).toBeInTheDocument();

    // the affected resource + correlation id
    expect(
      within(card).getAllByText(/request_id: sha256:deadbeef/).length,
    ).toBeGreaterThan(0);
    expect(
      within(card).getAllByText(/GET \/api\/2\.0\/contracts/).length,
    ).toBeGreaterThan(0);

    // the captured response body renders (the backend's own words)
    expect(within(card).getByText(/Captured response body/)).toBeInTheDocument();

    // NOT retryable — honestly stated, no retry button
    expect(within(card).queryByTestId("workbench-retry")).toBeNull();
    expect(within(card).getByText(/NOT retryable/)).toBeInTheDocument();

    // the reproducible API form: copyable curl, credential ALWAYS masked
    expect(within(card).getByTestId("workbench-curl")).toBeInTheDocument();
    expect(document.body.textContent).toContain("<your-credential>");
    expect(document.body.textContent).toContain("X-ADCOS-Credential");
    // the real credential never appears anywhere
    expect(document.body.textContent).not.toContain(FIXTURE_SESSION.credential);
    // the application id IS the session's real value
    expect(document.body.textContent).toContain(FIXTURE_APPLICATION.application_id);
  });

  it("retries through the typed client when the backend marked the error retryable, and reports the outcome", async () => {
    let contractsCalls = 0;
    const fetchMock = routeFetch({
      "GET /api/2.0/application": envelope(FIXTURE_APPLICATION),
      "GET /api/2.0/contracts": () => {
        contractsCalls += 1;
        return contractsCalls === 1
          ? { __status: 429, body: RATE_LIMITED_ERROR }
          : envelope(EMPTY_CONTRACTS_LIST);
      },
    });
    vi.stubGlobal("fetch", fetchMock);
    ensureRequestRecorder();

    renderWorkbench(
      <>
        <ListContractsDriver />
        <ErrorWorkbench />
      </>,
    );

    const card = await waitFor(() => {
      return screen.getByTestId("captured-error");
    });

    // the reason is verbatim and honest about the dictionary (unknown code)
    expect(within(card).getAllByTestId("workbench-reason")[0]).toHaveTextContent(
      "rate-limited",
    );
    expect(within(card).getByText(/not in the known-code dictionary/)).toBeInTheDocument();

    // retryable → the Retry button
    const retryButton = within(card).getByTestId("workbench-retry");
    expect(retryButton).toBeInTheDocument();

    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(within(card).getByText(/Re-issued — HTTP 200/)).toBeInTheDocument();
    });
    expect(within(card).getByText(/the request succeeded/)).toBeInTheDocument();

    // the re-issue went through the typed client (a second contracts read)
    const contractsReads = fetchMock.mock.calls.filter(
      ([path]) => path === "/api/2.0/contracts",
    );
    expect(contractsReads).toHaveLength(2);
  });

  it("gives unknown reason codes the honest generic fallback — never invented guidance", async () => {
    const fetchMock = routeFetch({
      "GET /api/2.0/application": envelope(FIXTURE_APPLICATION),
      "GET /api/2.0/contracts": { __status: 422, body: MYSTERY_ERROR },
    });
    vi.stubGlobal("fetch", fetchMock);
    ensureRequestRecorder();

    renderWorkbench(
      <>
        <ListContractsDriver />
        <ErrorWorkbench />
      </>,
    );

    const card = await waitFor(() => {
      return screen.getByTestId("captured-error");
    });

    // the code renders VERBATIM, with the honest fallback around it
    expect(within(card).getAllByTestId("workbench-reason")[0]).toHaveTextContent(
      "mystery-code",
    );
    expect(
      within(card).getByText("Reason code not in the known dictionary"),
    ).toBeInTheDocument();
    expect(within(card).getByText(/no specific guidance for this code/)).toBeInTheDocument();
    expect(within(card).getByText(/\(not in the known-code dictionary\)/)).toBeInTheDocument();

    // the affected resource id from the captured body
    expect(within(card).getAllByText(/resource_id: sha256:affected-resource/).length).toBeGreaterThan(0);

    // not retryable — no retry button, honest line
    expect(within(card).queryByTestId("workbench-retry")).toBeNull();
  });

  it("preselects the deep-linked request (?request=N) and keeps the others collapsed", async () => {
    mockSearchParams.current = new URLSearchParams("request=3");

    const fetchMock = routeFetch({
      "GET /api/2.0/application": envelope(FIXTURE_APPLICATION),
      "GET /api/2.0/contracts": { __status: 401, body: AUTH_ERROR },
      [`GET /api/2.0/contracts/${UNKNOWN_CONTRACT_ID}`]: {
        __status: 404,
        body: NOT_FOUND_ERROR,
      },
    });
    vi.stubGlobal("fetch", fetchMock);
    ensureRequestRecorder();

    renderWorkbench(
      <>
        <TwoFailuresDriver />
        <ErrorWorkbench />
      </>,
    );

    await waitFor(() => {
      expect(screen.getAllByTestId("captured-error")).toHaveLength(2);
    });

    // sequence 3 (the doomed contract read) is the preselected, expanded card
    const linked = screen
      .getAllByTestId("captured-error")
      .find((node) => node.getAttribute("data-sequence") === "3");
    expect(linked).toBeDefined();
    expect(linked?.getAttribute("aria-current")).toBe("true");
    expect(
      within(linked as HTMLElement).getByText(`contract ${UNKNOWN_CONTRACT_ID} is unknown`),
    ).toBeInTheDocument();
    expect(
      within(linked as HTMLElement).getByText("Contract not found"),
    ).toBeInTheDocument();

    // sequence 2 (the authentication failure) stays collapsed: no message,
    // no guidance body — only its collapsed header line
    const other = screen
      .getAllByTestId("captured-error")
      .find((node) => node.getAttribute("data-sequence") === "2");
    expect(other).toBeDefined();
    expect(
      within(other as HTMLElement).queryByText(
        "the credential was rejected for this application",
      ),
    ).toBeNull();
    expect(
      within(other as HTMLElement).queryByText("Authentication failed"),
    ).toBeNull();
    // …but its reason chip IS visible in the collapsed header (verbatim)
    expect(
      within(other as HTMLElement).getAllByTestId("workbench-reason").length,
    ).toBeGreaterThan(0);
  });

  it("labels synthesized client-side codes as such (backend-unreachable) and offers the retry", async () => {
    // the application read succeeds; the contracts read never reaches a
    // backend — the transport itself rejects
    const fetchMock = vi.fn((path: string) => {
      if (path === "/api/2.0/contracts") {
        return Promise.reject(new TypeError("fetch failed"));
      }
      return Promise.resolve(okResponse(envelope(FIXTURE_APPLICATION)));
    });
    vi.stubGlobal("fetch", fetchMock);
    ensureRequestRecorder();

    renderWorkbench(
      <>
        <ListContractsDriver />
        <ErrorWorkbench />
      </>,
    );

    const card = await waitFor(() => {
      return screen.getByTestId("captured-error");
    });

    // the synthesized status + reason render, clearly labeled client-side
    expect(within(card).getByText("unreachable")).toBeInTheDocument();
    expect(within(card).getAllByTestId("workbench-reason")[0]).toHaveTextContent(
      "backend-unreachable",
    );
    expect(
      within(card).getByText(/synthesized client-side — not a backend reason code/),
    ).toBeInTheDocument();

    // status 0 → the retry is offered (the classic "backend came back" case)
    const retryButton = within(card).getByTestId("workbench-retry");
    fireEvent.click(retryButton);

    // the transport still rejects → the honest re-issue failure line
    await waitFor(() => {
      expect(within(card).getByText(/Re-issued — failed again/)).toBeInTheDocument();
    });
  });

  it("shows the honest empty state when every request succeeded, and the honest note for a stale deep link", async () => {
    mockSearchParams.current = new URLSearchParams("request=99");

    const fetchMock = routeFetch({
      "GET /api/2.0/application": envelope(FIXTURE_APPLICATION),
      "GET /api/2.0/contracts": envelope(EMPTY_CONTRACTS_LIST),
    });
    vi.stubGlobal("fetch", fetchMock);
    ensureRequestRecorder();

    renderWorkbench(
      <>
        <ListContractsDriver />
        <ErrorWorkbench />
      </>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("workbench-empty")).toBeInTheDocument();
    });
    expect(screen.getByText("No captured errors")).toBeInTheDocument();
    expect(screen.getByText(/every request this console session made succeeded/i)).toBeInTheDocument();

    // the stale deep link is disclosed honestly
    expect(screen.getByTestId("workbench-deep-link-note")).toBeInTheDocument();
    expect(screen.getByText(/#99, which is not in the captured log/)).toBeInTheDocument();
  });
});
