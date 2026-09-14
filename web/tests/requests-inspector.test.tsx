/**
 * Request Inspector tests — the global request log against a mocked
 * GLOBAL fetch boundary (real Response objects so the recorder captures
 * headers/bodies/duration exactly as in a browser), rendered inside the
 * REAL SessionProvider with the real connect() flow.
 *
 * Deterministic request sequence per connected render: the connect flow
 * (entry 1, recorded BEFORE the recorder installs — hence un-enriched),
 * the search providers' reads (entries 2–3, fired after the session
 * CONNECTS — the recorder is installed by then, so they ARE enriched),
 * then the user-triggered probe requests (also enriched with
 * duration + captured response headers/body).
 *
 * Covers the work order's inspector demands:
 * - requests the console makes are recorded (status, request id,
 *   duration — the enrichment distinction rendered honestly);
 * - the table narrows via the failures-only toggle (isFailedRequest)
 *   with the backend reason traveling VERBATIM;
 * - the detail drawer shows the request headers (credential ALWAYS
 *   masked), the request body, the captured response headers/body
 *   (truncated with expand), and the copyable CURL reproduction;
 * - the reproducible journey: a recorded mutation's exact curl carries
 *   the masked credential + the idempotency-key placeholder;
 * - the registry operation that produced the request links into the
 *   API Explorer;
 * - pre-recorder entries render honestly WITHOUT the captured fields;
 * - clearRequests requires an explicit confirmation;
 * - the ?request=<sequence> deep link preselects the captured request
 *   (the requestsHref object-linking affordance other pages adopt).
 */

import { useEffect, useState, type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type {
  Application,
  Contract,
  CreateIntentInput,
  ListResponse,
} from "@/lib/api/types";
import { SessionProvider, useSession } from "@/lib/session";
import { RequestInspectorView, requestsHref } from "@/features/requests";
import { __resetRequestLogForTests } from "@/features/requests/request-log";
import { __resetRecorderForTests } from "@/features/requests/recorder";
import { __resetCommandRegistryForTests } from "@/features/search/command-registry";

const pushMock = vi.fn();
let searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  usePathname: () => "/developers/requests",
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
 * Fixtures — REAL captured shapes
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

/** Bulked with real-shaped canonical material so the envelope body is deterministic and long. */
const CONTRACT: Contract = {
  accepted_offers: [],
  assurance_obligations: [
    {
      ref_kind: "assurance-obligation",
      value: "demo:assurance-obligation:v1",
      provenance: { issuer: "assurance-authority", decision_refs: ["demo:assurance:v1"] },
    },
  ],
  beneficiaries: [
    { beneficiary_kind: "DEVICE", beneficiary_ref: "demo:device:v1" },
    { beneficiary_kind: "DEVICE", beneficiary_ref: "demo:device:v2" },
    { beneficiary_kind: "DEVICE", beneficiary_ref: "demo:device:v3" },
  ],
  command_count: 1,
  contract_id:
    "sha256:d5522ff10aeffa286bb3c30bd887587a40659480d2338c8b7847d3f398e6c0b7",
  environment: "sandbox",
  execution_artifacts: [
    {
      ref_kind: "execution-artifact",
      value:
        "sha256:da58d8b9c09953f1d840fe30c86a92f31825e3363bb691476fc3aebaeb9ba5ec",
      provenance: {
        issuer: "adcos:runtime:demo-planner",
        decision_refs: ["demo:contract-fulfillment:v1"],
      },
    },
  ],
  execution_scope: [
    { ref_kind: "execution-scope", value: "demo:execution-scope:v1" },
    { ref_kind: "execution-scope", value: "demo:execution-scope:v2" },
    { ref_kind: "execution-scope", value: "demo:execution-scope:v3" },
  ],
  hard_constraints: [
    { kind: "latency-bound", params: { ms: 100 } },
    { kind: "throughput-floor", params: { bps: 1000 } },
    { kind: "latency-bound", params: { ms: 120 } },
    { kind: "throughput-floor", params: { bps: 2000 } },
    { kind: "latency-bound", params: { ms: 140 } },
  ],
  id: "sha256:d5522ff10aeffa286bb3c30bd887587a40659480d2338c8b7847d3f398e6c0b7",
  kind: "contract",
  principal: { principal_kind: "APPLICATION", principal_ref: SESSION.applicationId },
  provenance: {
    issuer: `developerapi-application:${SESSION.applicationId}`,
    decision_refs: [],
  },
  requirements: [
    { ref_kind: "intent-requirements", value: "demo:intent-requirements:v1" },
    { ref_kind: "intent-requirements", value: "demo:intent-requirements:v2" },
    { ref_kind: "intent-requirements", value: "demo:intent-requirements:v3" },
    { ref_kind: "intent-requirements", value: "demo:intent-requirements:v4" },
    { ref_kind: "intent-requirements", value: "demo:intent-requirements:v5" },
  ],
  service_properties: [
    { ref_kind: "service-property", value: "demo:service-property:v1" },
    { ref_kind: "service-property", value: "demo:service-property:v2" },
  ],
  signature_refs: [],
  state: "INTENT",
  termination: {
    conditions: ["principal-requested", "validity-expired"],
    compensation: { ref_kind: "compensation", value: "demo:compensation:v1" },
  },
  usage_pricing_terms: { ref_kind: "usage-pricing-terms", value: "demo:usage-pricing-terms:v1" },
  validity: { not_before: "2026-09-13T00:00:00Z", not_after: "2026-10-13T00:00:00Z" },
};

const EMPTY_LIST: ListResponse<Contract> = { items: [], next_cursor: "", has_more: false };

const PROBE_INTENT: CreateIntentInput = {
  recorded_at: "2026-09-14T00:00:00Z",
  requirements: [{ ref_kind: "intent-requirements", value: "demo:intent-requirements:v1" }],
  validity: { not_before: "2026-09-13T00:00:00Z", not_after: "2026-10-13T00:00:00Z" },
  termination: {
    conditions: ["principal-requested"],
    compensation: { ref_kind: "compensation", value: "demo:compensation:v1" },
  },
};

/* ------------------------------------------------------------------ *
 * The fetch boundary mock (real Responses — recorder-compatible)
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
 * The provider renderers + the request probe
 * ------------------------------------------------------------------ */

function Probe() {
  const { client } = useSession();
  return (
    <div>
      <button
        type="button"
        data-testid="probe-list"
        onClick={() => {
          void client.listContracts().catch(() => {});
        }}
      >
        Fire list read
      </button>
      <button
        type="button"
        data-testid="probe-mutation"
        onClick={() => {
          void client.createIntent(PROBE_INTENT, { idempotencyKey: "probe-key-1" }).catch(() => {});
        }}
      >
        Fire mutation
      </button>
      <button
        type="button"
        data-testid="probe-failure"
        onClick={() => {
          void client.getContract("sha256:missing").catch(() => {});
        }}
      >
        Fire failing read
      </button>
    </div>
  );
}

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

function rowBySequence(sequence: number): HTMLElement {
  const row = document.querySelector(`tr[data-row-key="request-${sequence}"]`);
  if (!row) {
    throw new Error(`request row not rendered: ${sequence}`);
  }
  return row as HTMLElement;
}

/** Waits for the mount-time requests (connect + the providers' two reads). */
async function waitForMountRequests(): Promise<void> {
  await waitFor(() => {
    expect(screen.getByTestId("requests-count")).toHaveTextContent(
      "3 of 3 captured requests",
    );
  });
}

beforeEach(() => {
  searchParams = new URLSearchParams();
  pushMock.mockClear();
  __resetRecorderForTests();
  __resetRequestLogForTests();
  __resetCommandRegistryForTests();
});

/* ------------------------------------------------------------------ */

describe("Request Inspector — recording and inspection", () => {
  it("records the console's requests, with the enrichment distinction rendered honestly", async () => {
    const fetchMock = routeFetch(connectedRoutes({ "POST /api/2.0/intents": envelope(CONTRACT) }));
    vi.stubGlobal("fetch", fetchMock);
    renderWithSession(
      <>
        <RequestInspectorView />
        <Probe />
      </>,
    );

    // entry 1: the connect flow (recorded BEFORE the recorder installed)
    await waitForMountRequests();
    expect(rowBySequence(1).textContent).toContain("GET");
    expect(rowBySequence(1).textContent).toContain("/api/2.0/application");
    expect(rowBySequence(1).textContent).toContain("sha256:harness_request_id");
    // pre-recorder entries carry no duration — stated, not invented
    expect(rowBySequence(1).textContent).toContain("—");

    // a user-triggered request through the session client (entry 4) IS
    // enriched: duration + captured response material
    fireEvent.click(screen.getByTestId("probe-list"));
    await waitFor(() => {
      expect(screen.getByTestId("requests-count")).toHaveTextContent(
        "4 of 4 captured requests",
      );
    });
    expect(rowBySequence(4).textContent).toContain("/api/2.0/contracts");
    expect(rowBySequence(4).textContent).toMatch(/\d+(\.\d+)? ms/);
  });

  it("inspects one request: masked request headers, captured response headers/body (with expand), the copyable curl, and the producing operation", async () => {
    const fetchMock = routeFetch(connectedRoutes({ "POST /api/2.0/intents": envelope(CONTRACT) }));
    vi.stubGlobal("fetch", fetchMock);
    renderWithSession(
      <>
        <RequestInspectorView />
        <Probe />
      </>,
    );

    await waitForMountRequests();
    fireEvent.click(screen.getByTestId("probe-mutation"));
    await waitFor(() => {
      expect(screen.getByTestId("requests-count")).toHaveTextContent(
        "4 of 4 captured requests",
      );
    });

    // the reproducible journey: select the recorded mutation (entry 4)
    fireEvent.click(rowBySequence(4));
    const dialog = await waitFor(() => {
      const found = screen.getByRole("dialog");
      expect(found).toBeInTheDocument();
      return found;
    });
    expect(within(dialog).getByText(/Captured request #4/)).toBeInTheDocument();
    expect(within(dialog).getByText("POST /api/2.0/intents")).toBeInTheDocument();
    expect(within(dialog).getByTestId("request-detail-status")).toHaveTextContent(
      "HTTP 200",
    );

    // the request headers: the session's ACTUAL application id, the
    // credential ALWAYS masked, the idempotency-key placeholder
    expect(within(dialog).getAllByText(SESSION.applicationId).length).toBeGreaterThan(0);
    expect(within(dialog).getAllByText("<your-credential>").length).toBeGreaterThan(0);
    expect(within(dialog).getAllByText("<idempotency-key>").length).toBeGreaterThan(0);
    // the header name renders in BOTH the request-headers table and the
    // curl reproduction — both honest, so query for at least one
    expect(within(dialog).getAllByText("X-ADCOS-API-Version").length).toBeGreaterThan(
      0,
    );

    // the recorder-captured response headers
    expect(within(dialog).getByText("x-adcos-request-id")).toBeInTheDocument();

    // the captured response body is clipped with an explicit expand; the
    // tail (validity.not_after + idempotency + rate_limit) sits far past
    // the preview clip, so its presence proves the expansion
    const expand = within(dialog).getByTestId("expand-captured-body");
    fireEvent.click(expand);
    const fullBody = Array.from(document.querySelectorAll("code")).find((element) =>
      element.textContent?.includes("rate_limit"),
    );
    expect(fullBody?.textContent).toContain("not_after");
    expect(fullBody?.textContent).toContain("validity");

    // the exact curl reproduction (copyable, masked) — the full ApiRequestPanel
    // renders the curl inside a CodeBlock whose copy button copies it verbatim
    const curlCode = Array.from(document.querySelectorAll("code")).find((element) =>
      element.textContent?.includes("curl -X POST '/api/2.0/intents'"),
    );
    expect(curlCode?.textContent).toContain("X-ADCOS-Credential: <your-credential>");
    expect(curlCode?.textContent).toContain("X-ADCOS-Idempotency-Key: <idempotency-key>");
    const curlBlockRoot = curlCode?.parentElement?.parentElement ?? null;
    expect(curlBlockRoot).not.toBeNull();
    expect(
      within(curlBlockRoot as HTMLElement).getByRole("button", { name: "Copy code" }),
    ).toBeInTheDocument();

    // the REAL credential never renders anywhere in the document
    expect(document.body.textContent).not.toContain(SESSION.credential);

    // the registry operation that produced the request, linked to the explorer
    expect(within(dialog).getByText("intent_create")).toBeInTheDocument();
    expect(
      within(dialog)
        .getAllByRole("link")
        .some(
          (link) =>
            link.getAttribute("href") === "/developers/explorer?operation=intent_create",
        ),
    ).toBe(true);
  });

  it("renders pre-recorder entries honestly WITHOUT the captured fields (nothing fabricated)", async () => {
    const fetchMock = routeFetch(connectedRoutes());
    vi.stubGlobal("fetch", fetchMock);
    renderWithSession(<RequestInspectorView />);

    await waitForMountRequests();
    // entry 1 (the connect read) was recorded BEFORE the recorder
    // installed — its row honestly carries no duration (nothing invented)
    expect(rowBySequence(1).textContent).toContain("—");
    // entries 2–3 (the providers' reads) fire after the session CONNECTS,
    // which is after the recorder installed — they honestly carry the
    // recorder-captured duration
    expect(rowBySequence(2).textContent).toMatch(/\d+(\.\d+)? ms/);

    fireEvent.click(rowBySequence(1));
    const dialog = await waitFor(() => {
      const found = screen.getByRole("dialog");
      expect(found).toBeInTheDocument();
      return found;
    });
    expect(within(dialog).getByTestId("drawer-headers-not-captured")).toBeInTheDocument();
    expect(within(dialog).getByText("application_self")).toBeInTheDocument();
  });

  it("narrows to failures only via isFailedRequest (the backend reason travels verbatim)", async () => {
    const fetchMock = routeFetch(
      connectedRoutes({
        "GET /api/2.0/contracts/sha256:missing": {
          __status: 404,
          body: {
            api_version: "2.0",
            environment: "sandbox",
            request_id: "sha256:harness_missing",
            error: {
              canonical_reason: "",
              environment: "sandbox",
              http_status: 404,
              message:
                "The contract does not exist or is not visible to this application",
              reason: "unknown-contract",
              request_id: "sha256:harness_missing",
              resource_id: "sha256:missing",
              retry_after: "",
              retryable: false,
            },
          },
        },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderWithSession(
      <>
        <RequestInspectorView />
        <Probe />
      </>,
    );

    await waitForMountRequests();
    fireEvent.click(screen.getByTestId("probe-failure"));
    await waitFor(() => {
      expect(screen.getByTestId("requests-count")).toHaveTextContent(
        "4 of 4 captured requests",
      );
    });

    fireEvent.change(screen.getByLabelText("Failures only"), {
      target: { value: "failures" },
    });

    // only the failed request remains
    await waitFor(() => {
      expect(document.querySelector('tr[data-row-key="request-1"]')).toBeNull();
    });
    expect(rowBySequence(4).textContent).toContain("/api/2.0/contracts/sha256:missing");
    expect(screen.getByTestId("requests-count")).toHaveTextContent(
      "1 of 4 captured requests",
    );

    // the reason renders VERBATIM in the drawer
    fireEvent.click(rowBySequence(4));
    const dialog = await waitFor(() => {
      const found = screen.getByRole("dialog");
      expect(found).toBeInTheDocument();
      return found;
    });
    expect(within(dialog).getByText("unknown-contract")).toBeInTheDocument();
    expect(within(dialog).getByTestId("request-detail-status")).toHaveTextContent(
      "HTTP 404",
    );
  });
});

describe("Request Inspector — clearing and deep links", () => {
  it("clears the log only after an explicit confirmation", async () => {
    const fetchMock = routeFetch(connectedRoutes());
    vi.stubGlobal("fetch", fetchMock);
    renderWithSession(<RequestInspectorView />);

    await waitForMountRequests();

    fireEvent.click(screen.getByTestId("clear-requests"));
    expect(screen.getByTestId("confirm-clear-requests")).toBeInTheDocument();

    // cancelling keeps every entry
    fireEvent.click(screen.getByTestId("cancel-clear-requests"));
    expect(rowBySequence(1)).toBeInTheDocument();

    // confirming clears — with the honest empty state after
    fireEvent.click(screen.getByTestId("clear-requests"));
    fireEvent.click(screen.getByTestId("confirm-clear-requests"));
    await waitFor(() => {
      expect(screen.getByText("No requests captured yet")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("clear-requests")).toBeNull();
    expect(screen.getByTestId("requests-count")).toHaveTextContent(
      "0 of 0 captured requests",
    );
  });

  it("deep-links ?request=<sequence> with the entry preselected (the requestsHref affordance)", async () => {
    expect(requestsHref(7)).toBe("/developers/requests?request=7");
    expect(requestsHref()).toBe("/developers/requests");

    searchParams = new URLSearchParams("request=4");
    const fetchMock = routeFetch(connectedRoutes());
    vi.stubGlobal("fetch", fetchMock);
    renderWithSession(
      <>
        <RequestInspectorView />
        <Probe />
      </>,
    );

    // entries 1–3 arrive at mount; entry 4 (the probe) arrives after —
    // the deep-link effect re-applies when it lands and preselects it
    await waitForMountRequests();
    fireEvent.click(screen.getByTestId("probe-list"));
    await waitFor(() => {
      expect(screen.getByTestId("requests-count")).toHaveTextContent(
        "4 of 4 captured requests",
      );
    });

    const dialog = await waitFor(() => {
      const found = screen.getByRole("dialog");
      expect(found).toBeInTheDocument();
      return found;
    });
    expect(within(dialog).getByText(/Captured request #4/)).toBeInTheDocument();
    expect(within(dialog).getByText("GET /api/2.0/contracts")).toBeInTheDocument();
  });
});
