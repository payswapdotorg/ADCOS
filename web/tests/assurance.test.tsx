/**
 * Assurance view tests — REAL captured shapes only, fetch mocked at the
 * global boundary (the station harness pattern: a router over REAL
 * fixture envelopes, the page rendered inside the REAL SessionProvider
 * with the real connect() flow). NO network, ever.
 *
 * Covers the work order's Part C2 demands:
 * - per contract, the OBLIGATION REFERENCES render VERBATIM (opaque
 *   refs + provenance) with the contract state and the honest notes;
 * - the evidence_class labels stay verbatim (sandbox-simulation, never
 *   re-badged);
 * - each obligation links to its contract and its evidence chain (the
 *   demo runs' attestation records by contract_ref), with honest empty
 *   chains when no attestation was captured;
 * - NO invented metric dashboards (the intro states objectives ARE the
 *   obligation references);
 * - honest empty state when no contracts exist, the connect gate, and
 *   the deeper-pagination disclosure.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import { useEffect, useState, type ReactNode } from "react";
import { SessionProvider, useSession } from "@/lib/session";
import {
  EVIDENCE_BADGE_TEST_IDS,
  STATUS_TEST_IDS,
} from "@/components/ui";
import { __resetRequestLogForTests } from "@/features/requests/request-log";
import { __resetRecorderForTests } from "@/features/requests/recorder";
import { __resetDemoRunsForTests, recordDemoRun } from "@/features/evidence/demo-runs";
import { __resetCommandRegistryForTests } from "@/features/search/command-registry";
import { AssuranceView } from "@/features/assurance/assurance-view";
import type {
  Application,
  Contract,
  ContractAssurance,
  DemoDocument,
  ListResponse,
} from "@/lib/api/types";

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

const DEMO_CONTRACT_ID =
  "sha256:78f563858281c8caad6c639df7a8109231f3546dbcff789fce43bfee22cfa7ba";
const CAPTURE_CONTRACT_ID =
  "sha256:8c925c7fe3bddc7d398e0b4bebd8151e5c682147a33043579f9ed778ea559c55";

/** The demonstration contract (as the contracts list returns it). */
const FIXTURE_DEMO_CONTRACT: Contract = {
  accepted_offers: [
    {
      provenance: {
        decision_refs: ["demo:offer:v1"],
        issuer: "provider:ran-reference",
      },
      ref_kind: "offer",
      value: "demo:offer:ran-reference:v1",
    },
  ],
  assurance_obligations: [
    {
      provenance: {
        decision_refs: ["demo:assurance:v1"],
        issuer: "assurance-authority",
      },
      ref_kind: "assurance-obligation",
      value: "demo:assurance-obligation:v1",
    },
  ],
  beneficiaries: [
    { beneficiary_kind: "DEVICE", beneficiary_ref: "demo:device:v1" },
  ],
  command_count: 4,
  contract_id: DEMO_CONTRACT_ID,
  environment: "sandbox",
  execution_artifacts: [
    {
      provenance: {
        decision_refs: ["demo:contract-fulfillment:v1"],
        issuer: "adcos:runtime:demo-planner",
      },
      ref_kind: "execution-artifact",
      value: "sha256:da58d8b9c09953f1d840fe30c86a92f31825e3363bb691476fc3aebaeb9ba5ec",
    },
  ],
  execution_scope: [
    { ref_kind: "execution-scope", value: "demo:execution-scope:v1" },
  ],
  hard_constraints: [
    { kind: "latency-bound", params: { ms: 100 } },
    { kind: "throughput-floor", params: { bps: 1000 } },
  ],
  id: DEMO_CONTRACT_ID,
  kind: "contract",
  principal: {
    principal_kind: "APPLICATION",
    principal_ref: "sha256:c20c5f90db52d8a89c5168fdb71f522ed9648d1264330357a9cdad98532f1f01",
  },
  provenance: {
    decision_refs: [
      "developerapi:sha256:cdcd478bf78c4283ebc66a9e81ca6558de4222cee43b3ba89fd5aca192d60596",
    ],
    issuer:
      "developerapi-application:sha256:c20c5f90db52d8a89c5168fdb71f522ed9648d1264330357a9cdad98532f1f01",
  },
  requirements: [
    {
      provenance: {
        decision_refs: ["demo:intent:v1"],
        issuer: "intent-authority",
      },
      ref_kind: "intent-requirements",
      value: "demo:intent-requirements:v1",
    },
  ],
  service_properties: [
    { ref_kind: "service-property", value: "demo:service-property:v1" },
  ],
  signature_refs: [{ ref_kind: "signature", value: "demo:signature:v1" }],
  state: "CONTRACT_ACTIVE",
  termination: {
    compensation: { ref_kind: "compensation", value: "demo:compensation:v1" },
    conditions: ["principal-requested", "validity-expired"],
  },
  usage_pricing_terms: {
    ref_kind: "usage-pricing-terms",
    value: "demo:usage-pricing:v1",
  },
  validity: {
    not_after: "2026-10-14T00:00:00Z",
    not_before: "2026-09-14T00:00:00Z",
  },
};

/** A second contract (the captured-lifecycle one). */
const FIXTURE_CAPTURE_CONTRACT: Contract = {
  accepted_offers: [
    {
      provenance: {
        decision_refs: ["capture:offer:v1"],
        issuer: "provider:ran-reference",
      },
      ref_kind: "offer",
      value: "capture:offer:v1",
    },
  ],
  assurance_obligations: [
    {
      provenance: {
        decision_refs: ["capture:assurance:v1"],
        issuer: "assurance-authority",
      },
      ref_kind: "assurance-obligation",
      value: "capture:assurance:v1",
    },
  ],
  beneficiaries: [
    { beneficiary_kind: "DEVICE", beneficiary_ref: "capture:device:v1" },
  ],
  command_count: 5,
  contract_id: CAPTURE_CONTRACT_ID,
  environment: "sandbox",
  execution_artifacts: [],
  execution_scope: [
    { ref_kind: "execution-scope", value: "capture:execution-scope:v1" },
  ],
  hard_constraints: [
    { kind: "latency-bound", params: { ms: 100 } },
    { kind: "throughput-floor", params: { bps: 1000 } },
  ],
  id: CAPTURE_CONTRACT_ID,
  kind: "contract",
  principal: {
    principal_kind: "APPLICATION",
    principal_ref: "sha256:c20c5f90db52d8a89c5168fdb71f522ed9648d1264330357a9cdad98532f1f01",
  },
  provenance: {
    decision_refs: [
      "developerapi:sha256:b5ef7adc447b70294f076dc1921439b79ed9e8b10e35b8288f5d75635eaf2d47",
    ],
    issuer:
      "developerapi-application:sha256:c20c5f90db52d8a89c5168fdb71f522ed9648d1264330357a9cdad98532f1f01",
  },
  requirements: [
    {
      provenance: {
        decision_refs: ["capture:intent:v1"],
        issuer: "intent-authority",
      },
      ref_kind: "intent-requirements",
      value: "capture:requirements:v1",
    },
  ],
  service_properties: [
    { ref_kind: "service-property", value: "capture:service-property:v1" },
  ],
  signature_refs: [{ ref_kind: "signature", value: "capture:signature:v1" }],
  state: "CONTRACT_ACTIVE",
  termination: {
    compensation: { ref_kind: "compensation", value: "capture:compensation:v1" },
    conditions: ["principal-requested", "validity-expired"],
  },
  usage_pricing_terms: {
    ref_kind: "usage-pricing-terms",
    value: "capture:usage-pricing:v1",
  },
  validity: {
    not_after: "2026-10-14T00:00:00Z",
    not_before: "2026-09-14T00:00:00Z",
  },
};

const FIXTURE_CONTRACTS_LIST: ListResponse<Contract> = {
  items: [FIXTURE_DEMO_CONTRACT, FIXTURE_CAPTURE_CONTRACT],
  next_cursor: "",
  has_more: false,
};

/** GET /api/2.0/contracts/{capture}/assurance — VERBATIM capture. */
const FIXTURE_ASSURANCE: ContractAssurance = {
  assurance_obligations: [
    {
      provenance: {
        decision_refs: ["capture:assurance:v1"],
        issuer: "assurance-authority",
      },
      ref_kind: "assurance-obligation",
      value: "capture:assurance:v1",
    },
  ],
  contract_state: "CONTRACT_ACTIVE",
  environment: "sandbox",
  evidence_class: "sandbox-simulation",
  id: CAPTURE_CONTRACT_ID,
  kind: "contract_assurance",
  note: "assurance semantics are referenced, never evaluated: the assurance authority owns the obligations; the contract state machine records the evaluation outcomes (ASSURED/DEGRADED/FAILED per the frozen 1.1 \u00a79 vocabulary)",
};

/** GET /api/2.0/contracts/{demo}/assurance — the demo contract's obligations. */
const FIXTURE_DEMO_ASSURANCE: ContractAssurance = {
  assurance_obligations: [
    {
      provenance: {
        decision_refs: ["demo:assurance:v1"],
        issuer: "assurance-authority",
      },
      ref_kind: "assurance-obligation",
      value: "demo:assurance-obligation:v1",
    },
  ],
  contract_state: "CONTRACT_ACTIVE",
  environment: "sandbox",
  evidence_class: "sandbox-simulation",
  id: DEMO_CONTRACT_ID,
  kind: "contract_assurance",
  note: "assurance semantics are referenced, never evaluated: the assurance authority owns the obligations; the contract state machine records the evaluation outcomes (ASSURED/DEGRADED/FAILED per the frozen 1.1 \u00a79 vocabulary)",
};

/** The demonstration document (the attestation-record source for the evidence chain). */
const FIXTURE_DEMO_DOCUMENT: DemoDocument = {
  boundary: [
    {
      method: "POST",
      request_id: "sha256:9efd1daa89f6d37d809c6a9727af1326cb6b8d970fbb24f0ee748aaab4f9cb59",
      route: "/api/2.0/intents",
      status: 200,
    },
  ],
  contract: {
    contract_id: DEMO_CONTRACT_ID,
    state: "CONTRACT_ACTIVE",
  },
  environment: "sandbox",
  evidence: [
    {
      confidence_basis_points: 10000,
      contract_ref: DEMO_CONTRACT_ID,
      freshness_until: "2026-09-14T02:00:00Z",
      instant: "2026-09-14T01:00:00Z",
      metric: "link-up",
      producer: "provider:ran-reference",
      record_id:
        "evidence:observation:7e6e275466ed7559cfce3768b83cb9ee0230ec3d52b21d87375609ed7db5b1f7",
      record_type: "observation",
      source_refs: [
        "sha256:35cfdec9219b152ba7bd8ed9dbfc7153ea14dd12a870c1945350328c0e5dab89",
      ],
      subject_ref:
        "sha256:a958a4bacec50cc3670788e45309f820c87d7c06b28d6d288cb93c7b7c9512f2",
      value: 1,
    },
    {
      attestation_kind: "controller-verified",
      attested_value: 1,
      contract_ref: DEMO_CONTRACT_ID,
      instant: "2026-09-14T02:00:00Z",
      producer: "adcos:runtime:demo-attestor",
      record_id:
        "evidence:attestation:8bf42deca4011e0cb230ca0a7980eae09dc007063faaca5e59c918fb497572e0",
      record_type: "attestation",
      source_refs: [
        "sha256:da58d8b9c09953f1d840fe30c86a92f31825e3363bb691476fc3aebaeb9ba5ec",
      ],
      subject_ref:
        "sha256:da58d8b9c09953f1d840fe30c86a92f31825e3363bb691476fc3aebaeb9ba5ec",
      valid_until: "2026-09-15T02:00:00Z",
    },
  ],
  evidence_class: "SOFTWARE",
  execution: { sandbox: true },
  instant: "2026-09-14T00:00:00Z",
  mode: "sandbox",
  plan: {},
};

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
    <SessionProvider>
      <Connector />
      {ui}
    </SessionProvider>,
  );
}

function renderBare(ui: ReactNode) {
  return render(<SessionProvider>{ui}</SessionProvider>);
}

vi.mock("next/navigation", () => ({
  usePathname: () => "/assurance",
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
  __resetDemoRunsForTests();
  __resetCommandRegistryForTests();
});

describe("Assurance view", () => {
  it("renders every contract's obligation references VERBATIM with provenance, state and the honest notes", async () => {
    const fetchMock = routeFetch({
      "GET /api/2.0/application": envelope(FIXTURE_APPLICATION),
      "GET /api/2.0/contracts": envelope(FIXTURE_CONTRACTS_LIST),
      [`GET /api/2.0/contracts/${DEMO_CONTRACT_ID}/assurance`]: envelope(
        FIXTURE_DEMO_ASSURANCE,
      ),
      [`GET /api/2.0/contracts/${CAPTURE_CONTRACT_ID}/assurance`]: envelope(
        FIXTURE_ASSURANCE,
      ),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<AssuranceView />);

    // one section per contract, once both assurance reads land
    await waitFor(() => {
      expect(screen.getAllByTestId("contract-assurance")).toHaveLength(2);
    });
    // the per-contract assurance reads are in flight while the sections
    // render — wait for the obligations themselves before asserting
    await waitFor(() => {
      expect(screen.getAllByTestId("assurance-obligation")).toHaveLength(2);
    });

    // the OBLIGATION REFERENCES verbatim — the opaque values exactly as sent
    expect(screen.getAllByText("demo:assurance-obligation:v1").length).toBeGreaterThan(0);
    expect(screen.getAllByText("capture:assurance:v1").length).toBeGreaterThan(0);

    // ref_kind verbatim + provenance (issuer + decision_refs)
    const obligations = screen.getAllByTestId("assurance-obligation");
    expect(obligations).toHaveLength(2);
    for (const obligation of obligations) {
      expect(within(obligation).getAllByText("assurance-obligation").length).toBeGreaterThan(0);
      expect(within(obligation).getAllByText("assurance-authority").length).toBeGreaterThan(0);
    }
    expect(screen.getAllByText("demo:assurance:v1").length).toBeGreaterThan(0);
    expect(screen.getAllByText("capture:assurance:v1").length).toBeGreaterThan(0);

    // the contract states, verbatim
    const activeStates = screen
      .getAllByTestId(STATUS_TEST_IDS.root)
      .filter((node) => node.getAttribute("data-value") === "CONTRACT_ACTIVE");
    expect(activeStates.length).toBeGreaterThanOrEqual(2);

    // the honest notes, verbatim (both contracts carry the same note)
    const notes = screen.getAllByTestId("verbatim-note");
    expect(notes).toHaveLength(2);
    expect(notes[0]).toHaveTextContent(
      "assurance semantics are referenced, never evaluated",
    );

    // the evidence_class labels stay VERBATIM (sandbox-simulation, software kind)
    const badges = screen.getAllByTestId(EVIDENCE_BADGE_TEST_IDS.root);
    expect(badgesSoftwareOnly(badges)).toBe(true);
    expect(
      badges.some((badge) => badge.textContent?.includes("sandbox-simulation")),
    ).toBe(true);

    // NO invented metric dashboards — the intro states objectives ARE the
    // obligation references the backend returns
    expect(screen.getByText(/OBLIGATION REFERENCES the backend returns/)).toBeInTheDocument();
  });

  it("links each obligation to its contract and its evidence chain, rendering the runs' attestation records by contract_ref", async () => {
    // the session captured one demonstration run (the attestation source)
    recordDemoRun(FIXTURE_DEMO_DOCUMENT, "2026-09-14T00:05:00Z");

    const fetchMock = routeFetch({
      "GET /api/2.0/application": envelope(FIXTURE_APPLICATION),
      "GET /api/2.0/contracts": envelope(FIXTURE_CONTRACTS_LIST),
      [`GET /api/2.0/contracts/${DEMO_CONTRACT_ID}/assurance`]: envelope(
        FIXTURE_DEMO_ASSURANCE,
      ),
      [`GET /api/2.0/contracts/${CAPTURE_CONTRACT_ID}/assurance`]: envelope(
        FIXTURE_ASSURANCE,
      ),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<AssuranceView />);

    await waitFor(() => {
      expect(screen.getAllByTestId("contract-assurance")).toHaveLength(2);
    });
    // wait for the obligations (the per-contract reads land after the list)
    await waitFor(() => {
      expect(screen.getAllByTestId("assurance-obligation")).toHaveLength(2);
    });

    // every obligation links to its contract page AND to the evidence surface
    for (const obligation of screen.getAllByTestId("assurance-obligation")) {
      expect(
        within(obligation).getAllByRole("link").some((link) =>
          link.getAttribute("href")?.startsWith("/connectivity/contracts/"),
        ),
      ).toBe(true);
      expect(
        within(obligation).getAllByRole("link").some((link) => link.getAttribute("href") === "/evidence"),
      ).toBe(true);
    }

    // the demo contract's evidence chain carries the captured attestation
    const demoSection = screen
      .getAllByTestId("contract-assurance")
      .find((section) => section.getAttribute("data-contract-id") === DEMO_CONTRACT_ID);
    expect(demoSection).toBeDefined();
    const demoChain = within(demoSection as HTMLElement).getByTestId(
      "assurance-evidence-chain",
    );
    expect(
      within(demoChain).getAllByText(
        "evidence:attestation:8bf42deca4011e0cb230ca0a7980eae09dc007063faaca5e59c918fb497572e0",
      ).length,
    ).toBeGreaterThan(0);
    expect(within(demoChain).getAllByText("controller-verified").length).toBeGreaterThan(0);
    // the attestation renders with its run's evidence_class VERBATIM
    const chainBadges = within(demoChain).getAllByTestId(EVIDENCE_BADGE_TEST_IDS.root);
    expect(badgesSoftwareOnly(chainBadges)).toBe(true);
    expect(
      chainBadges.some((badge) => badge.textContent?.includes("SOFTWARE")),
    ).toBe(true);

    // the capture contract's chain is honestly empty (with the way to fill it)
    const captureSection = screen
      .getAllByTestId("contract-assurance")
      .find((section) => section.getAttribute("data-contract-id") === CAPTURE_CONTRACT_ID);
    const captureChain = within(captureSection as HTMLElement).getByTestId(
      "assurance-evidence-chain",
    );
    expect(
      within(captureChain).getByText(/No attestation records captured/),
    ).toBeInTheDocument();
    expect(
      within(captureChain).getAllByRole("link").some((link) => link.getAttribute("href") === "/fulfillment"),
    ).toBe(true);
  });

  it("shows the honest empty state when no contracts exist", async () => {
    const fetchMock = routeFetch({
      "GET /api/2.0/application": envelope(FIXTURE_APPLICATION),
      "GET /api/2.0/contracts": envelope({
        items: [],
        next_cursor: "",
        has_more: false,
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<AssuranceView />);

    await waitFor(() => {
      expect(screen.getByTestId("assurance-empty")).toBeInTheDocument();
    });
    expect(screen.getByText("No contracts yet")).toBeInTheDocument();
    expect(
      screen.getAllByRole("link").some((link) => link.getAttribute("href") === "/connectivity/new"),
    ).toBe(true);
    expect(
      screen.getAllByRole("link").some((link) => link.getAttribute("href") === "/fulfillment"),
    ).toBe(true);
  });

  it("fires NO authenticated read while disconnected and shows connect guidance", async () => {
    const fetchMock = routeFetch({});
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<AssuranceView />);

    expect(screen.getByTestId("assurance-connect-gate")).toBeInTheDocument();
    expect(screen.getByText("Connect an application to continue")).toBeInTheDocument();

    const contractsCalls = fetchMock.mock.calls.filter(
      ([path]) => path === "/api/2.0/contracts",
    );
    expect(contractsCalls).toHaveLength(0);
  });

  it("discloses deeper pagination honestly when the backend reports more pages", async () => {
    const fetchMock = routeFetch({
      "GET /api/2.0/application": envelope(FIXTURE_APPLICATION),
      "GET /api/2.0/contracts": envelope({
        ...FIXTURE_CONTRACTS_LIST,
        has_more: true,
        next_cursor: "cursor-2",
      }),
      [`GET /api/2.0/contracts/${DEMO_CONTRACT_ID}/assurance`]: envelope(
        FIXTURE_DEMO_ASSURANCE,
      ),
      [`GET /api/2.0/contracts/${CAPTURE_CONTRACT_ID}/assurance`]: envelope(
        FIXTURE_ASSURANCE,
      ),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<AssuranceView />);

    await waitFor(() => {
      expect(
        screen.getByTestId("assurance-deeper-pagination-notice"),
      ).toBeInTheDocument();
    });
    expect(screen.getByText(/fetch forbids GET bodies/)).toBeInTheDocument();
  });
});

/** No badge in the list is ever physical-kind (SOFTWARE never physical). */
function badgesSoftwareOnly(badges: HTMLElement[]): boolean {
  return badges.every((badge) => badge.getAttribute("data-kind") !== "physical");
}
