/**
 * ConsoleSearchProviders tests — the real search providers against a
 * mocked GLOBAL fetch boundary, rendered inside the REAL SessionProvider
 * with the real connect() flow.
 *
 * Covers the work order's provider demands:
 * - the registry operations register as commands (reads always navigate
 *   to /developers/explorer?operation=<operation>);
 * - MUTATION commands appear ONLY when a session is connected AND the
 *   required capability is granted (the application's capability list
 *   is the gate — absent when disconnected, absent when the grant is
 *   missing, present when granted);
 * - destructive operations (termination, lease revocation) require an
 *   EXPLICIT confirmation before even navigating — never a silent run;
 * - contracts (fetched list; id/state/principal match), webhook
 *   endpoints (fetched list) and the session's demonstration runs
 *   register with real routes;
 * - every command unregisters on unmount.
 */

import { useEffect, useState, type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type {
  Application,
  Contract,
  DemoDocument,
  ListResponse,
  WebhookEndpoint,
} from "@/lib/api/types";
import { COVERAGE } from "@/lib/api/coverage";
import { SessionProvider, useSession } from "@/lib/session";
import { ConsoleSearchProviders } from "@/features/search/providers";
import {
  getCommands,
  __resetCommandRegistryForTests,
} from "@/features/search/command-registry";
import {
  __resetDemoRunsForTests,
  recordDemoRun,
} from "@/features/evidence/demo-runs";

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

/* ------------------------------------------------------------------ *
 * Fixtures — REAL captured shapes
 * ------------------------------------------------------------------ */

const SESSION = {
  applicationId:
    "sha256:c20c5f90db52d8a89c5168fdb71f522ed9648d1264330357a9cdad98532f1f01",
  credential:
    "dasec_6f0a61f4d683e1b7a06859649217ac1714552b64c93ea25509e0e7dfa0ed5b60",
};

const FULL_CAPABILITIES = [
  "assurance:read",
  "intents:read",
  "intents:write",
  "leases:read",
  "leases:write",
  "usage:read",
  "webhooks:read",
  "webhooks:write",
];

const PARTIAL_CAPABILITIES = [
  "assurance:read",
  "intents:read",
  "leases:read",
  "leases:write",
  "usage:read",
  "webhooks:read",
];

function applicationWith(capabilities: string[]): Application {
  return {
    application_id: SESSION.applicationId,
    application_name: "adcos:runtime:contract-fulfillment-demo",
    capabilities,
    developer_id: "adcos:runtime:demo-developer",
    environment: "sandbox",
    evidence_class: "sandbox-simulation",
    issued_at: "2026-09-13T00:00:00Z",
    kind: "application",
    status: "active",
    valid_until: "2036-09-13T00:00:00Z",
  };
}

const CONTRACT_A_ID =
  "sha256:8c925c7fe3bddc7d398e0b4bebd8151e5c682147a33043579f9ed778ea559c55";
const CONTRACT_B_ID =
  "sha256:78f563858281c8caad6c639df7a8109231f3546dbcff789fce43bfee22cfa7ba";

function contract(id: string, state: string): Contract {
  return {
    accepted_offers: [],
    assurance_obligations: [],
    beneficiaries: [],
    command_count: 1,
    contract_id: id,
    environment: "sandbox",
    execution_artifacts: [],
    execution_scope: [],
    hard_constraints: [],
    id,
    kind: "contract",
    principal: { principal_kind: "APPLICATION", principal_ref: SESSION.applicationId },
    provenance: { issuer: `developerapi-application:${SESSION.applicationId}`, decision_refs: [] },
    requirements: [{ ref_kind: "intent-requirements", value: "demo:intent-requirements:v1" }],
    service_properties: [],
    signature_refs: [],
    state,
    termination: {
      conditions: ["principal-requested"],
      compensation: { ref_kind: "compensation", value: "demo:compensation:v1" },
    },
    usage_pricing_terms: { ref_kind: "usage-pricing-terms", value: "demo:usage-pricing-terms:v1" },
    validity: { not_before: "2026-09-13T00:00:00Z", not_after: "2026-10-13T00:00:00Z" },
  };
}

const CONTRACTS_LIST: ListResponse<Contract> = {
  items: [contract(CONTRACT_A_ID, "INTENT"), contract(CONTRACT_B_ID, "CONTRACT_ACTIVE")],
  next_cursor: "",
  has_more: false,
};

const ENDPOINT_ID =
  "sha256:339aad04332444655e42307bb0ffaf2c3bb47ccb4e4aa41e3fef6b877522cac8";

const ENDPOINT: WebhookEndpoint = {
  api_version: "2.0",
  created_at: "2026-09-13T00:00:00Z",
  developer_id: "adcos:runtime:demo-developer",
  environment: "sandbox",
  event_types: ["connectivity_intent.created", "webhook_endpoint.registered"],
  id: ENDPOINT_ID,
  key_id: "sha256:endpoint_key",
  kind: "webhook_endpoint",
  url: "https://example.com/hooks/adcos",
};

const ENDPOINTS_LIST: ListResponse<WebhookEndpoint> = {
  items: [ENDPOINT],
  next_cursor: "",
  has_more: false,
};

const DEMO_DOCUMENT: DemoDocument = {
  mode: "sandbox",
  environment: "sandbox",
  evidence_class: "sandbox-simulation",
  instant: "2026-09-14T01:00:00Z",
  boundary: [
    {
      method: "POST",
      route: "/api/2.0/intents",
      status: 200,
      request_id: "sha256:9efd1daa89f6d37d809c6a9727af1326cb6b8d970fbb24f0ee748aaab4f9cb59",
    },
  ],
  contract: { contract_id: CONTRACT_B_ID },
  plan: {},
  execution: {},
  evidence: [
    {
      record_id:
        "evidence:observation:7e6e275466ed7559cfce3768b83cb9ee0230ec3d52b21d87375609ed7db5b1f7",
      record_type: "observation",
      metric: "link-up",
      value: 1,
      instant: "2026-09-14T01:00:00Z",
    },
  ],
};

/* ------------------------------------------------------------------ *
 * The fetch boundary mock
 * ------------------------------------------------------------------ */

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function envelope<T>(data: T): unknown {
  return {
    api_version: "2.0",
    environment: "sandbox",
    request_id: "sha256:harness_request_id",
    data,
  };
}

function routeFetch(routes: Record<string, unknown>): Mock {
  return vi.fn((path: string, init?: RequestInit) => {
    const method = (init?.method ?? "GET").toUpperCase();
    const key = `${method} ${path}`;
    const body = routes[key];
    if (body === undefined) {
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
    return Promise.resolve(jsonResponse(body));
  });
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

function operationCommands() {
  return getCommands().filter((command) => command.id.startsWith("search-operation-"));
}

function mutationCommands() {
  return getCommands().filter((command) => command.title.startsWith("Run "));
}

function commandById(id: string) {
  return getCommands().find((command) => command.id === id);
}

beforeEach(() => {
  pushMock.mockClear();
  __resetCommandRegistryForTests();
  __resetDemoRunsForTests();
});

/* ------------------------------------------------------------------ */

describe("ConsoleSearchProviders — permission-aware operation commands", () => {
  it("registers ONLY the read operations while disconnected (mutation commands absent)", () => {
    const fetchMock = routeFetch({});
    vi.stubGlobal("fetch", fetchMock);
    renderBare(<ConsoleSearchProviders />);

    // the registry's 17 read operations navigate to the explorer; the 8
    // mutation operations are absent without a connected session
    expect(operationCommands()).toHaveLength(17);
    expect(mutationCommands()).toHaveLength(0);
    expect(commandById("search-operation-healthz")?.href).toBe(
      "/developers/explorer?operation=healthz",
    );
    expect(commandById("search-operation-intent_get")?.href).toBe(
      "/developers/explorer?operation=intent_get",
    );
    // the destructive operations are mutations — absent here
    expect(commandById("search-operation-contract_terminate")).toBeUndefined();
    expect(commandById("search-operation-lease_revoke")).toBeUndefined();

    // no object fetch fired while disconnected
    expect(fetchMock.mock.calls).toHaveLength(0);
  });

  it("registers every registry operation when connected with the capabilities granted", async () => {
    const fetchMock = routeFetch({
      "GET /api/2.0/application": envelope(applicationWith(FULL_CAPABILITIES)),
      "GET /api/2.0/contracts": envelope(CONTRACTS_LIST),
      "GET /api/2.0/webhook-endpoints": envelope(ENDPOINTS_LIST),
    });
    vi.stubGlobal("fetch", fetchMock);
    renderWithSession(<ConsoleSearchProviders />);

    await waitFor(() => {
      expect(operationCommands()).toHaveLength(COVERAGE.length);
    });
    expect(mutationCommands()).toHaveLength(8);

    // the mutation commands navigate into the explorer (run → inspect there)
    expect(commandById("search-operation-intent_create")?.href).toBe(
      "/developers/explorer?operation=intent_create",
    );
    expect(commandById("search-operation-intent_create")?.title).toContain(
      "Run POST /api/2.0/intents",
    );

    // the destructive operations never navigate directly — they carry an
    // explicit confirmation step instead
    const terminate = commandById("search-operation-contract_terminate");
    expect(terminate?.title).toContain("(destructive)");
    expect(terminate?.href).toBeUndefined();
    expect(typeof terminate?.run).toBe("function");
    const revoke = commandById("search-operation-lease_revoke");
    expect(revoke?.title).toContain("(destructive)");
    expect(revoke?.href).toBeUndefined();
  });

  it("gates mutation commands on the granted capability (missing grants register nothing)", async () => {
    // intents:write and webhooks:write are NOT granted
    const fetchMock = routeFetch({
      "GET /api/2.0/application": envelope(applicationWith(PARTIAL_CAPABILITIES)),
      "GET /api/2.0/contracts": envelope(CONTRACTS_LIST),
    });
    vi.stubGlobal("fetch", fetchMock);
    renderWithSession(<ConsoleSearchProviders />);

    await waitFor(() => {
      expect(operationCommands()).toHaveLength(20); // 17 reads + 3 leases:write mutations
    });

    // intents:write / webhooks:write mutations are absent
    expect(commandById("search-operation-intent_create")).toBeUndefined();
    expect(commandById("search-operation-offers_accept")).toBeUndefined();
    expect(commandById("search-operation-contract_activate")).toBeUndefined();
    expect(commandById("search-operation-contract_terminate")).toBeUndefined();
    expect(commandById("search-operation-endpoint_register")).toBeUndefined();

    // leases:write mutations are present (the grant IS held)
    expect(commandById("search-operation-lease_grant")?.title).toContain(
      "Run POST /api/2.0/contracts/{contract_id}/leases",
    );
    expect(commandById("search-operation-lease_revoke")).toBeDefined();

    // contracts registered (intents:read granted); endpoints NOT (webhooks:read
    // granted but the list read ran — the endpoint fixture route is absent,
    // so the honest absence holds: no endpoint commands)
    expect(commandById(`search-contract-${CONTRACT_A_ID}`)).toBeDefined();
    expect(commandById(`search-contract-${CONTRACT_B_ID}`)).toBeDefined();
    expect(getCommands().some((command) => command.id.startsWith("search-endpoint-"))).toBe(
      false,
    );
  });
});

describe("ConsoleSearchProviders — object search", () => {
  it("registers the fetched contracts (id/state/principal match) with real routes", async () => {
    const fetchMock = routeFetch({
      "GET /api/2.0/application": envelope(applicationWith(FULL_CAPABILITIES)),
      "GET /api/2.0/contracts": envelope(CONTRACTS_LIST),
      "GET /api/2.0/webhook-endpoints": envelope(ENDPOINTS_LIST),
    });
    vi.stubGlobal("fetch", fetchMock);
    renderWithSession(<ConsoleSearchProviders />);

    await waitFor(() => {
      expect(commandById(`search-contract-${CONTRACT_A_ID}`)).toBeDefined();
    });

    const first = commandById(`search-contract-${CONTRACT_A_ID}`);
    // the palette-sized id label is the registry id truncated at 16 chars
    expect(first?.title).toContain("Contract sha256:8c925c7fe…");
    expect(first?.href).toBe(`/connectivity/contracts/${CONTRACT_A_ID}`);
    // the FULL id, the state and the principal all match in the palette
    expect(first?.keywords).toEqual(
      expect.arrayContaining([CONTRACT_A_ID, "INTENT", SESSION.applicationId]),
    );

    const second = commandById(`search-contract-${CONTRACT_B_ID}`);
    expect(second?.href).toBe(`/connectivity/contracts/${CONTRACT_B_ID}`);
    expect(second?.keywords).toEqual(
      expect.arrayContaining([CONTRACT_B_ID, "CONTRACT_ACTIVE"]),
    );
  });

  it("registers the fetched webhook endpoints into the explorer with the id prefilled", async () => {
    const fetchMock = routeFetch({
      "GET /api/2.0/application": envelope(applicationWith(FULL_CAPABILITIES)),
      "GET /api/2.0/contracts": envelope({ items: [], next_cursor: "", has_more: false }),
      "GET /api/2.0/webhook-endpoints": envelope(ENDPOINTS_LIST),
    });
    vi.stubGlobal("fetch", fetchMock);
    renderWithSession(<ConsoleSearchProviders />);

    await waitFor(() => {
      expect(commandById(`search-endpoint-${ENDPOINT_ID}`)).toBeDefined();
    });
    const endpointCommand = commandById(`search-endpoint-${ENDPOINT_ID}`);
    expect(endpointCommand?.title).toContain("Webhook endpoint");
    expect(endpointCommand?.href).toBe(
      `/developers/explorer?operation=endpoint_get&endpoint_id=${ENDPOINT_ID}`,
    );
    expect(endpointCommand?.keywords).toEqual(
      expect.arrayContaining([ENDPOINT_ID, ENDPOINT.url, "connectivity_intent.created"]),
    );
  });

  it("registers the session's demonstration runs as evidence records", () => {
    recordDemoRun(DEMO_DOCUMENT);
    const fetchMock = routeFetch({});
    vi.stubGlobal("fetch", fetchMock);
    renderBare(<ConsoleSearchProviders />);

    const runCommand = commandById("search-demo-run-2026-09-14T01:00:00Z");
    expect(runCommand).toBeDefined();
    expect(runCommand?.title).toBe("Demo run 2026-09-14T01:00:00Z");
    expect(runCommand?.href).toBe("/evidence");
    expect(runCommand?.keywords).toEqual(
      expect.arrayContaining([CONTRACT_B_ID, "sandbox-simulation", "evidence"]),
    );
  });
});

describe("ConsoleSearchProviders — destructive confirmation", () => {
  it("requires an explicit confirmation before navigating to a destructive operation", async () => {
    const fetchMock = routeFetch({
      "GET /api/2.0/application": envelope(applicationWith(FULL_CAPABILITIES)),
      "GET /api/2.0/contracts": envelope({ items: [], next_cursor: "", has_more: false }),
      "GET /api/2.0/webhook-endpoints": envelope({ items: [], next_cursor: "", has_more: false }),
    });
    vi.stubGlobal("fetch", fetchMock);
    renderWithSession(<ConsoleSearchProviders />);

    await waitFor(() => {
      expect(commandById("search-operation-contract_terminate")).toBeDefined();
    });

    // invoking the destructive command opens the confirmation drawer —
    // nothing navigates yet
    commandById("search-operation-contract_terminate")?.run?.();
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
    expect(screen.getByText("Destructive operation")).toBeInTheDocument();
    // the drawer names the exact operation (the registry's own description
    // for the termination — a unique match; the request path also carries
    // "termination", so a bare /termination|Terminate/i query is ambiguous)
    expect(
      screen.getByText(/Terminate the contract \(terminal state\)/),
    ).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();

    // cancelling closes without navigating
    fireEvent.click(screen.getByTestId("destructive-cancel"));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });
    expect(pushMock).not.toHaveBeenCalled();

    // re-invoking and confirming navigates to the explorer with the
    // operation preselected (the explorer confirms again before executing)
    commandById("search-operation-contract_terminate")?.run?.();
    await waitFor(() => {
      expect(screen.getByTestId("destructive-continue")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("destructive-continue"));
    expect(pushMock).toHaveBeenCalledWith(
      "/developers/explorer?operation=contract_terminate",
    );
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });
  });
});

describe("ConsoleSearchProviders — lifecycle", () => {
  it("unregisters every command on unmount", async () => {
    const fetchMock = routeFetch({
      "GET /api/2.0/application": envelope(applicationWith(FULL_CAPABILITIES)),
      "GET /api/2.0/contracts": envelope(CONTRACTS_LIST),
      "GET /api/2.0/webhook-endpoints": envelope(ENDPOINTS_LIST),
    });
    vi.stubGlobal("fetch", fetchMock);
    const view = renderWithSession(<ConsoleSearchProviders />);

    await waitFor(() => {
      expect(getCommands().length).toBeGreaterThan(0);
    });
    view.unmount();
    expect(getCommands()).toHaveLength(0);
  });
});
