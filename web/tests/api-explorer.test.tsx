/**
 * API Explorer tests — the registry-driven surface against a mocked
 * GLOBAL fetch boundary (real Response objects so the request recorder
 * captures headers/bodies exactly as the browser would), rendered
 * inside the REAL SessionProvider with the real connect() flow.
 *
 * Covers the work order's explorer demands:
 * - the REGISTRY drives the operation list (25 rows — 21 developer + 4
 *   platform, zero invented; grouped by area; badges verbatim);
 * - an execute flow with the mocked fetch asserting the exact headers
 *   and body the boundary contract mandates (auth + version +
 *   idempotency + content-type);
 * - the GET-with-body discipline (list reads execute BODYLESS — fetch
 *   forbids GET bodies — with the honest canonical-form notice);
 * - the error path shows the backend reason VERBATIM with
 *   retryable/retry_after surfaced;
 * - destructive operations are gated behind an explicit confirmation
 *   (no request fires until confirmed);
 * - the replayable execution history (mutations replay with the SAME
 *   idempotency key);
 * - honest search: an unknown path/method query yields "not a
 *   supported operation"; a resolvable path prefills its parameters;
 * - the ?operation= deep link (and its honest unknown-operation notice);
 * - disconnected sessions gate authenticated execution (platform
 *   surfaces stay executable);
 * - the credential NEVER renders (masked in every reproduction).
 */

import { useEffect, useState, type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import {
  COVERAGE,
  DEVELOPER_OPERATION_COUNT,
  PLATFORM_OPERATION_COUNT,
} from "@/lib/api/coverage";
import type { Application, Contract, ListResponse } from "@/lib/api/types";
import { SessionProvider, useSession } from "@/lib/session";
import { ERROR_REASON_TEST_ID } from "@/components/ui";
import { ApiExplorerView } from "@/features/api-explorer";
import { __resetExplorerHistoryForTests } from "@/features/api-explorer/explorer-history";
import { __resetRequestLogForTests } from "@/features/requests/request-log";
import { __resetRecorderForTests } from "@/features/requests/recorder";
import { __resetCommandRegistryForTests } from "@/features/search/command-registry";

const pushMock = vi.fn();
let searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  usePathname: () => "/developers/explorer",
  useParams: () => ({}),
  useRouter: () => ({
    push: pushMock,
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  useSearchParams: () => searchParams,
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: Record<string, unknown>) => (
    <a href={href as string} {...props}>
      {children as never}
    </a>
  ),
}));

/* ------------------------------------------------------------------ *
 * Fixtures — REAL captured shapes (client.test.ts / station captures)
 * ------------------------------------------------------------------ */

const SESSION = {
  applicationId:
    "sha256:c20c5f90db52d8a89c5168fdb71f522ed9648d1264330357a9cdad98532f1f01",
  credential:
    "dasec_6f0a61f4d683e1b7a06859649217ac1714552b64c93ea25509e0e7dfa0ed5b60",
};

const APPLICATION: Application = {
  application_id: SESSION.applicationId,
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

const CONTRACT: Contract = {
  accepted_offers: [],
  assurance_obligations: [],
  beneficiaries: [],
  command_count: 1,
  contract_id:
    "sha256:d5522ff10aeffa286bb3c30bd887587a40659480d2338c8b7847d3f398e6c0b7",
  environment: "sandbox",
  execution_artifacts: [],
  execution_scope: [],
  hard_constraints: [],
  id: "sha256:d5522ff10aeffa286bb3c30bd887587a40659480d2338c8b7847d3f398e6c0b7",
  kind: "contract",
  principal: { principal_kind: "APPLICATION", principal_ref: SESSION.applicationId },
  provenance: {
    issuer: `developerapi-application:${SESSION.applicationId}`,
    decision_refs: [],
  },
  requirements: [{ ref_kind: "intent-requirements", value: "demo:intent-requirements:v1" }],
  service_properties: [],
  signature_refs: [],
  state: "INTENT",
  termination: {
    conditions: ["principal-requested"],
    compensation: { ref_kind: "compensation", value: "demo:compensation:v1" },
  },
  usage_pricing_terms: { ref_kind: "usage-pricing-terms", value: "demo:usage-pricing-terms:v1" },
  validity: { not_before: "2026-09-13T00:00:00Z", not_after: "2026-10-13T00:00:00Z" },
};

const EMPTY_LIST: ListResponse<Contract> = {
  items: [],
  next_cursor: "",
  has_more: false,
};

/* ------------------------------------------------------------------ *
 * The fetch boundary mock (real Response objects — the recorder
 * captures headers/bodies through clone()/text() exactly as in a browser)
 * ------------------------------------------------------------------ */

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json",
      "x-adcos-request-id": "sha256:harness_request_id",
      "x-adcos-environment": "sandbox",
    },
  });
}

function envelope<T>(data: T): unknown {
  return {
    api_version: "2.0",
    environment: "sandbox",
    request_id: "sha256:harness_request_id",
    data,
    idempotency: { key: "harness", replayed: false },
    rate_limit: { limit: 1000, remaining: 999, reset_at: "2026-09-13T00:00:01Z" },
  };
}

function routeFetch(routes: Record<string, unknown>): Mock {
  return vi.fn((path: string, init?: RequestInit) => {
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
        jsonResponse(
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
    const resolved = typeof body === "function" ? (body as () => unknown)() : body;
    if (resolved instanceof Response) {
      return Promise.resolve(resolved);
    }
    if (
      typeof resolved === "object" &&
      resolved !== null &&
      "__status" in (resolved as Record<string, unknown>)
    ) {
      const wrapper = resolved as { __status: number; body: unknown };
      return Promise.resolve(jsonResponse(wrapper.body, wrapper.__status));
    }
    return Promise.resolve(jsonResponse(resolved));
  });
}

/** The routes every connected render needs (connect + the providers' reads). */
function connectedRoutes(extra: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    "GET /api/2.0/application": envelope(APPLICATION),
    "GET /api/2.0/contracts": envelope(EMPTY_LIST),
    "GET /api/2.0/webhook-endpoints": envelope(EMPTY_LIST),
    ...extra,
  };
}

/* ------------------------------------------------------------------ *
 * The provider renderers
 * ------------------------------------------------------------------ */

function renderWithSession(ui: ReactNode) {
  function Connector() {
    const { connect, status } = useSession();
    const [started, setStarted] = useState(false);
    useEffect(() => {
      if (started || status !== "disconnected") return;
      setStarted(true);
      void connect(SESSION.applicationId, SESSION.credential);
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

function renderBare(ui: ReactNode) {
  return render(<SessionProvider>{ui}</SessionProvider>);
}

function operationRow(operation: string): HTMLElement {
  const row = screen
    .getAllByTestId("explorer-operation-row")
    .find((candidate) => (candidate as HTMLElement).dataset.operation === operation);
  if (!row) {
    throw new Error(`operation row not rendered: ${operation}`);
  }
  return row as HTMLElement;
}

async function selectOperation(operation: string): Promise<void> {
  fireEvent.click(operationRow(operation));
}

beforeEach(() => {
  searchParams = new URLSearchParams();
  pushMock.mockClear();
  __resetRecorderForTests();
  __resetRequestLogForTests();
  __resetExplorerHistoryForTests();
  __resetCommandRegistryForTests();
});

/* ------------------------------------------------------------------ */

describe("API Explorer — the registry-driven operation browser", () => {
  it("renders EXACTLY the registry's operations (none invented), grouped by area", async () => {
    const fetchMock = routeFetch(connectedRoutes());
    vi.stubGlobal("fetch", fetchMock);
    renderWithSession(<ApiExplorerView />);

    const rows = await waitFor(() => {
      const found = screen.getAllByTestId("explorer-operation-row");
      expect(found).toHaveLength(COVERAGE.length);
      return found;
    });

    // the registry is the single source of truth: 21 developer + 4 platform
    expect(COVERAGE).toHaveLength(DEVELOPER_OPERATION_COUNT + PLATFORM_OPERATION_COUNT);
    expect(DEVELOPER_OPERATION_COUNT).toBe(21);
    expect(PLATFORM_OPERATION_COUNT).toBe(4);

    const rendered = rows.map((row) => (row as HTMLElement).dataset.operation);
    const registry = COVERAGE.map((record) => record.operation);
    expect([...rendered].sort()).toEqual([...registry].sort());

    // grouped by area, mutation/destructive/capability badges verbatim
    expect(screen.getByText("Platform surfaces")).toBeInTheDocument();
    expect(screen.getByText("Connectivity")).toBeInTheDocument();
    expect(screen.getByText("Developers")).toBeInTheDocument();
    expect(screen.getByText("Assurance")).toBeInTheDocument();

    const termination = operationRow("contract_terminate");
    expect(termination.textContent).toContain("POST");
    expect(termination.textContent).toContain("/api/2.0/contracts/{contract_id}/termination");
    expect(termination.textContent).toContain("mutation");
    expect(termination.textContent).toContain("destructive");
    expect(termination.textContent).toContain("intents:write");

    expect(screen.getByTestId("explorer-operation-count")).toHaveTextContent(
      "25 of 25 registry operations",
    );
  });

  it("answers an unknown path/method query with the honest 'not a supported operation' notice", async () => {
    const fetchMock = routeFetch(connectedRoutes());
    vi.stubGlobal("fetch", fetchMock);
    renderWithSession(<ApiExplorerView />);

    await waitFor(() => {
      expect(screen.getAllByTestId("explorer-operation-row")).toHaveLength(COVERAGE.length);
    });

    fireEvent.change(screen.getByTestId("explorer-operation-search"), {
      target: { value: "POST /api/9.0/things" },
    });

    const notice = screen.getByTestId("unsupported-operation-notice");
    expect(notice.textContent).toContain("POST /api/9.0/things");
    expect(notice.textContent).toContain("is not a supported operation");
    expect(notice.textContent).toContain(
      "The coverage registry is the single source of truth",
    );

    // a bare unknown path gets the same honest answer
    fireEvent.change(screen.getByTestId("explorer-operation-search"), {
      target: { value: "/api/9.0/things" },
    });
    expect(screen.getByTestId("unsupported-operation-notice").textContent).toContain(
      "/api/9.0/things",
    );
  });

  it("resolves a concrete known path to its operation and prefills the path parameters", async () => {
    const fetchMock = routeFetch(connectedRoutes());
    vi.stubGlobal("fetch", fetchMock);
    renderWithSession(<ApiExplorerView />);

    await waitFor(() => {
      expect(screen.getAllByTestId("explorer-operation-row")).toHaveLength(COVERAGE.length);
    });

    fireEvent.change(screen.getByTestId("explorer-operation-search"), {
      target: { value: "GET /api/2.0/intents/sha256:abc123" },
    });

    fireEvent.click(screen.getByTestId("resolved-operation"));

    await waitFor(() => {
      expect(screen.getByText(/operation: intent_get/)).toBeInTheDocument();
    });
    expect(
      (screen.getByLabelText("Path parameter intent_id") as HTMLInputElement).value,
    ).toBe("sha256:abc123");
  });

  it("answers an unknown ?operation= deep link with the honest notice", async () => {
    searchParams = new URLSearchParams("operation=definitely_not_an_operation");
    const fetchMock = routeFetch(connectedRoutes());
    vi.stubGlobal("fetch", fetchMock);
    renderWithSession(<ApiExplorerView />);

    await waitFor(() => {
      expect(screen.getByTestId("unsupported-operation-notice")).toBeInTheDocument();
    });
    expect(screen.getByTestId("unsupported-operation-notice").textContent).toContain(
      "definitely_not_an_operation",
    );
  });
});

describe("API Explorer — execution through the real typed client", () => {
  it("executes a mutation with the boundary's exact headers and body, and masks the credential everywhere", async () => {
    const fetchMock = routeFetch(
      connectedRoutes({ "POST /api/2.0/intents": envelope(CONTRACT) }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderWithSession(<ApiExplorerView />);

    await selectOperation("intent_create");
    await waitFor(() => {
      expect(screen.getByTestId("execute-operation")).toBeEnabled();
    });

    // the required-headers table carries the session's ACTUAL application
    // id (the credential is the masked placeholder)
    expect(screen.getAllByText(SESSION.applicationId, { exact: false }).length).toBeGreaterThan(
      0,
    );
    expect(screen.getByText("<your-credential>")).toBeInTheDocument();

    // the body editor is seeded from the registry's own example
    const editor = screen.getByLabelText("Request body JSON") as HTMLTextAreaElement;
    expect(editor.value).toContain("demo:intent-requirements:v1");

    // edit the body (a minimal REAL intent_request core)
    const customBody = {
      recorded_at: "2026-09-14T00:00:00Z",
      requirements: [
        { ref_kind: "intent-requirements", value: "demo:intent-requirements:v1" },
      ],
      validity: { not_before: "2026-09-13T00:00:00Z", not_after: "2026-10-13T00:00:00Z" },
      termination: {
        conditions: ["principal-requested"],
        compensation: { ref_kind: "compensation", value: "demo:compensation:v1" },
      },
    };
    fireEvent.change(editor, { target: { value: JSON.stringify(customBody, null, 2) } });

    const keyValue = (
      screen.getByLabelText("Idempotency key") as HTMLInputElement
    ).value;
    expect(keyValue).toMatch(/.+/);

    fireEvent.click(screen.getByTestId("execute-operation"));

    await waitFor(() => {
      expect(screen.getByTestId("response-status")).toHaveTextContent("HTTP 200");
    });

    // the REAL request: exact path, method, headers and body
    const calls = fetchMock.mock.calls.filter(([path]) => path === "/api/2.0/intents");
    expect(calls).toHaveLength(1);
    const [, init] = calls[0];
    expect(init?.method).toBe("POST");
    const headers = (init?.headers ?? {}) as Record<string, string>;
    expect(headers["X-ADCOS-Application"]).toBe(SESSION.applicationId);
    expect(headers["X-ADCOS-Credential"]).toBe(SESSION.credential);
    expect(headers["X-ADCOS-API-Version"]).toBe("2.0");
    expect(headers["X-ADCOS-Idempotency-Key"]).toBe(keyValue);
    expect(headers["Content-Type"]).toBe("application/json");
    expect(init?.body).toBe(JSON.stringify(customBody));

    // the recorder-captured response headers + the envelope surface
    expect(screen.getByText("x-adcos-request-id")).toBeInTheDocument();
    expect(screen.getByText(/limit 1000/)).toBeInTheDocument();
    expect(screen.getByText(/first execution/)).toBeInTheDocument();

    // the curl reproduction masks the credential and carries the real key
    const curlCode = Array.from(document.querySelectorAll("code")).find((element) =>
      element.textContent?.includes("curl -X POST '/api/2.0/intents'"),
    );
    expect(curlCode?.textContent).toContain("X-ADCOS-Credential: <your-credential>");
    expect(curlCode?.textContent).toContain(`X-ADCOS-Idempotency-Key: ${keyValue}`);
    expect(curlCode?.textContent).toContain(`X-ADCOS-Application: ${SESSION.applicationId}`);

    // the REAL credential never renders anywhere in the document
    expect(document.body.textContent).not.toContain(SESSION.credential);

    // one replayable history entry exists
    expect(screen.getByTestId("explorer-history-count")).toHaveTextContent(
      "1 execution this session",
    );
  });

  it("replays a recorded mutation with the SAME idempotency key (byte-identical replay semantics)", async () => {
    const fetchMock = routeFetch(
      connectedRoutes({ "POST /api/2.0/intents": envelope(CONTRACT) }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderWithSession(<ApiExplorerView />);

    await selectOperation("intent_create");
    await waitFor(() => {
      expect(screen.getByTestId("execute-operation")).toBeEnabled();
    });
    fireEvent.click(screen.getByTestId("execute-operation"));
    await waitFor(() => {
      expect(screen.getByTestId("response-status")).toHaveTextContent("HTTP 200");
    });

    const historyRow = screen.getAllByTestId("explorer-history-row")[0];
    fireEvent.click(within(historyRow).getByText("Replay"));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.filter(([path]) => path === "/api/2.0/intents"),
      ).toHaveLength(2);
    });

    const [firstInit, secondInit] = fetchMock.mock.calls
      .filter(([path]) => path === "/api/2.0/intents")
      .map(([, init]) => init);
    const firstHeaders = (firstInit?.headers ?? {}) as Record<string, string>;
    const secondHeaders = (secondInit?.headers ?? {}) as Record<string, string>;
    expect(secondHeaders["X-ADCOS-Idempotency-Key"]).toBe(
      firstHeaders["X-ADCOS-Idempotency-Key"],
    );
    expect(secondInit?.body).toBe(firstInit?.body);

    expect(screen.getByTestId("explorer-history-count")).toHaveTextContent(
      "2 executions this session",
    );
  });

  it("executes list reads BODYLESS (the browser GET-body discipline) and shows the canonical-form notice", async () => {
    const fetchMock = routeFetch(
      connectedRoutes({ "GET /api/2.0/contracts": envelope(EMPTY_LIST) }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderWithSession(<ApiExplorerView />);

    await selectOperation("contracts_list");

    const notice = screen.getByTestId("list-body-discipline-notice");
    expect(notice.textContent).toContain("fetch forbids GET bodies");
    expect(notice.textContent).toContain("bodyless default-page read");

    // no body editor for a GET list read — the canonical form is the
    // reproduction, not an editable browser request
    expect(screen.queryByLabelText("Request body JSON")).toBeNull();

    await waitFor(() => {
      expect(screen.getByTestId("execute-operation")).toBeEnabled();
    });
    fireEvent.click(screen.getByTestId("execute-operation"));

    await waitFor(() => {
      expect(screen.getByTestId("response-status")).toHaveTextContent("HTTP 200");
    });

    // the console's own contracts read (the providers') has landed by now;
    // the EXECUTION is the newest call — and it is bodyless
    const contractsCalls = fetchMock.mock.calls.filter(
      ([path]) => path === "/api/2.0/contracts",
    );
    expect(contractsCalls.length).toBeGreaterThanOrEqual(1);
    const [lastPath, lastInit] = contractsCalls[contractsCalls.length - 1];
    expect(lastPath).toBe("/api/2.0/contracts");
    expect(lastInit?.body).toBeUndefined();
    expect(lastInit?.method).toBe("GET");
    const headers = (lastInit?.headers ?? {}) as Record<string, string>;
    expect(headers["Content-Type"]).toBeUndefined();
  });

  it("shows the backend's reason code VERBATIM with retryable/retry_after on errors", async () => {
    const fetchMock = routeFetch(
      connectedRoutes({
        "GET /api/2.0/intents/sha256:missing": {
          __status: 429,
          body: {
            api_version: "2.0",
            environment: "sandbox",
            request_id: "sha256:rate_limited_request",
            error: {
              canonical_reason: "",
              environment: "sandbox",
              http_status: 429,
              message: "The request exceeded the application's rate limit",
              reason: "rate-limited",
              request_id: "sha256:rate_limited_request",
              resource_id: "",
              retry_after: "2026-09-13T00:00:01Z",
              retryable: true,
            },
          },
        },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderWithSession(<ApiExplorerView />);

    await selectOperation("intent_get");
    await waitFor(() => {
      expect(screen.getByTestId("execute-operation")).toBeEnabled();
    });
    fireEvent.change(screen.getByLabelText("Path parameter intent_id"), {
      target: { value: "sha256:missing" },
    });
    fireEvent.click(screen.getByTestId("execute-operation"));

    await waitFor(() => {
      expect(screen.getByTestId("response-status")).toHaveTextContent("HTTP 429");
    });

    // the reason chip, VERBATIM — never a generic replacement
    expect(screen.getByTestId(ERROR_REASON_TEST_ID)).toHaveTextContent("rate-limited");
    // the backend's message VERBATIM inside the error anatomy (the captured
    // response body CodeBlock legitimately repeats it — scope to the anatomy)
    expect(
      within(screen.getByTestId("explorer-error-state")).getByText(
        /The request exceeded the application's rate limit/,
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/retryable: true/)).toBeInTheDocument();
    expect(screen.getByText(/retry_after: 2026-09-13T00:00:01Z/)).toBeInTheDocument();

    // the failed execution is replayable history too
    expect(screen.getByTestId("explorer-history-count")).toHaveTextContent(
      "1 execution this session",
    );
  });

  it("gates destructive operations behind an explicit confirmation (no request until confirmed)", async () => {
    const fetchMock = routeFetch(
      connectedRoutes({
        "POST /api/2.0/contracts/sha256:term/termination": envelope(CONTRACT),
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderWithSession(<ApiExplorerView />);

    await selectOperation("contract_terminate");
    // wait for the connected session (the arm button is disabled while
    // unauthenticated — an armed destructive request would be dishonest)
    await waitFor(() => {
      expect(screen.getByTestId("arm-destructive-execute")).toBeEnabled();
    });
    fireEvent.change(screen.getByLabelText("Path parameter contract_id"), {
      target: { value: "sha256:term" },
    });

    // the first click ARMS the confirmation — no request fires
    fireEvent.click(screen.getByTestId("arm-destructive-execute"));
    const confirmation = screen.getByTestId("destructive-confirmation");
    expect(confirmation.textContent).toContain("destructive and terminal");
    expect(confirmation.textContent).toContain(
      "POST /api/2.0/contracts/sha256:term/termination",
    );
    expect(
      fetchMock.mock.calls.filter(([path]) => path.includes("/termination")),
    ).toHaveLength(0);

    // cancelling disarms without any request
    fireEvent.click(screen.getByTestId("cancel-destructive-execute"));
    expect(screen.queryByTestId("destructive-confirmation")).toBeNull();
    expect(
      fetchMock.mock.calls.filter(([path]) => path.includes("/termination")),
    ).toHaveLength(0);

    // re-arm and CONFIRM — the real request fires with the idempotency key
    fireEvent.click(screen.getByTestId("arm-destructive-execute"));
    fireEvent.click(screen.getByTestId("confirm-destructive-execute"));

    await waitFor(() => {
      expect(screen.getByTestId("response-status")).toHaveTextContent("HTTP 200");
    });
    const calls = fetchMock.mock.calls.filter(
      ([path]) => path === "/api/2.0/contracts/sha256:term/termination",
    );
    expect(calls).toHaveLength(1);
    const headers = (calls[0][1]?.headers ?? {}) as Record<string, string>;
    expect(headers["X-ADCOS-Idempotency-Key"]).toMatch(/.+/);
    expect(headers["X-ADCOS-Credential"]).toBe(SESSION.credential);
  });

  it("blocks execution on invalid editor JSON with a LOCAL validation message (never a backend reason)", async () => {
    const fetchMock = routeFetch(connectedRoutes());
    vi.stubGlobal("fetch", fetchMock);
    renderWithSession(<ApiExplorerView />);

    await selectOperation("intent_create");
    await waitFor(() => {
      expect(screen.getByTestId("execute-operation")).toBeEnabled();
    });
    fireEvent.change(screen.getByLabelText("Request body JSON"), {
      target: { value: '{"recorded_at": not-json' },
    });

    expect(screen.getByTestId("body-validation-error").textContent).toContain(
      "Local validation",
    );
    expect(screen.getByTestId("execute-operation")).toBeDisabled();
    expect(
      fetchMock.mock.calls.filter(([path]) => path === "/api/2.0/intents"),
    ).toHaveLength(0);
  });

  it("gates authenticated operations on a connected session (platform surfaces stay executable)", async () => {
    const fetchMock = routeFetch({
      "GET /healthz": { ok: true, service: "adcos-runtime" },
    });
    vi.stubGlobal("fetch", fetchMock);
    renderBare(<ApiExplorerView />);

    // an authenticated developer operation: connect guidance, disabled execute
    await selectOperation("application_self");
    expect(screen.getByText(/Connect an application to execute/)).toBeInTheDocument();
    expect(screen.getByTestId("execute-operation")).toBeDisabled();
    expect(
      screen.getByText("<your-application-id>"),
    ).toBeInTheDocument();

    // a platform surface needs no session: it executes for real
    await selectOperation("healthz");
    expect(screen.queryByText(/Connect an application to execute/)).toBeNull();
    expect(screen.getByText(/No boundary headers/)).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("execute-operation"));

    await waitFor(() => {
      expect(screen.getByTestId("response-status")).toHaveTextContent("HTTP 200");
    });
    expect(fetchMock.mock.calls.filter(([path]) => path === "/healthz")).toHaveLength(1);

    // NO authenticated request ever fired while disconnected
    expect(
      fetchMock.mock.calls.filter(([path]) => path.startsWith("/api/2.0/")),
    ).toHaveLength(0);
  });

  it("preselects and prefills the operation from the ?operation= deep link", async () => {
    searchParams = new URLSearchParams("operation=intent_get&intent_id=sha256:xyz");
    const fetchMock = routeFetch(connectedRoutes());
    vi.stubGlobal("fetch", fetchMock);
    renderWithSession(<ApiExplorerView />);

    await waitFor(() => {
      expect(screen.getByText(/operation: intent_get/)).toBeInTheDocument();
    });
    expect(
      (screen.getByLabelText("Path parameter intent_id") as HTMLInputElement).value,
    ).toBe("sha256:xyz");
  });
});
