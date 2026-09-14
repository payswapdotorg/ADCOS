/**
 * Evidence explorer tests — REAL captured shapes only, fetch mocked at
 * the global boundary (the station harness pattern: a router over REAL
 * fixture envelopes, the page rendered inside the REAL SessionProvider
 * with the real connect() flow). NO network, ever.
 *
 * Covers the work order's Part C1 demands:
 * - the current demo document is fetched and recorded on load (when a
 *   session is connected), and every record renders with its members
 *   VERBATIM (record ids, subject/contract refs, producer, instant,
 *   metric/value, confidence bps, freshness, source_refs);
 * - the badge vocabulary renders VERBATIM: SOFTWARE on every run group,
 *   the legend's NOT-ACHIEVABLE-BY-THIS-DEPLOYMENT phrase for the
 *   physical/network family — and NO badge anywhere is ever physical
 *   (SOFTWARE never becomes a physical PASS);
 * - the detail drawer carries the full record, provenance, source_refs,
 *   the related contract (live read) and the JSON view;
 * - the honest empty state when no runs exist, and the page's own
 *   run-demo action (the unauthenticated platform read).
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { useEffect, useState, type ReactNode } from "react";
import { render } from "@testing-library/react";
import { SessionProvider, useSession } from "@/lib/session";
import { EVIDENCE_BADGE_TEST_IDS } from "@/components/ui";
import { __resetRequestLogForTests } from "@/features/requests/request-log";
import { __resetRecorderForTests } from "@/features/requests/recorder";
import { __resetDemoRunsForTests } from "@/features/evidence/demo-runs";
import { __resetCommandRegistryForTests } from "@/features/search/command-registry";
import { EvidenceExplorer } from "@/features/evidence/evidence-explorer";
import type { Application, Contract, DemoDocument } from "@/lib/api/types";

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

/** The demonstration document exactly as GET /demo/contract-fulfillment returns it. */
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
      {
        beneficiary_kind: "DEVICE",
        beneficiary_ref: "demo:device:v1",
      },
    ],
    contract_id: DEMO_CONTRACT_ID,
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
      {
        ref_kind: "execution-scope",
        value: "demo:execution-scope:v1",
      },
    ],
    hard_constraints: [
      { kind: "latency-bound", params: { ms: 100 } },
      { kind: "throughput-floor", params: { bps: 1000 } },
    ],
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
        "sha256:a958a4bacec50cc3670788e45309f820c87d7c06b28d6d288cb93c7b7c9512f2",
      ],
      subject_ref:
        "sha256:da58d8b9c09953f1d840fe30c86a92f31825e3363bb691476fc3aebaeb9ba5ec",
      valid_until: "2026-09-15T02:00:00Z",
    },
  ],
  evidence_class: "SOFTWARE",
  execution: {
    access_technology_id: "access.3gpp.nr.imt2020",
    activation_id:
      "sha256:a958a4bacec50cc3670788e45309f820c87d7c06b28d6d288cb93c7b7c9512f2",
    adapter_id: "adcos:adapter:access.3gpp.nr.imt2020:bfa54a8cddce72a6",
    binding_id:
      "sha256:d329a36778181f2aa1af2d20c231f00147893be137c93c7d54dfb989c04dd990",
    measurement_id:
      "sha256:35cfdec9219b152ba7bd8ed9dbfc7153ea14dd12a870c1945350328c0e5dab89",
    provider: "deterministic-reference-adapter",
    release_id:
      "sha256:d983ab4093d92b7d1bcf000bb2f58e080eab9930acfba12cf151d90ba7352d0d",
    released_kinds: ["activation", "reservation"],
    reservation_id:
      "sha256:4fafbaa9815877e760f24fde5d9e012e557436dd38996060f4c82faa359f7b18",
    samples: [
      { metric: "link-up", observed_at: "2026-09-14T01:00:00Z", value: 1 },
      {
        metric: "rx-bytes-total",
        observed_at: "2026-09-14T01:00:00Z",
        value: 3000,
      },
    ],
    sandbox: true,
    segment_states: ["PLANNED", "RESERVED", "ACTIVATED", "MEASURED", "RELEASED"],
    session_id:
      "sha256:d385a360eea2dc466eb492020b69e9884b73c70aadcee0efb017c5f8a980a432",
    standard_mechanisms: ["3gpp-nr", "oran-fronthaul-split"],
  },
  instant: "2026-09-14T00:00:00Z",
  mode: "sandbox",
  plan: {
    constraint_fingerprint:
      "sha256:5d1178e5b556a1545a8140f9ccdd89ca5299d308608386a36ba1d0c355abdf62",
    contract_id: DEMO_CONTRACT_ID,
    hard_constraints: [
      { kind: "latency-bound", params: { ms: 100 } },
      { kind: "throughput-floor", params: { bps: 1000 } },
    ],
    plan_id:
      "sha256:da58d8b9c09953f1d840fe30c86a92f31825e3363bb691476fc3aebaeb9ba5ec",
    provenance: {
      decision_refs: ["demo:contract-fulfillment:v1"],
      issuer: "adcos:runtime:demo-planner",
    },
    segments: [
      {
        contract_id: DEMO_CONTRACT_ID,
        offer_reference: {
          provenance: {
            decision_refs: ["demo:offer:v1"],
            issuer: "provider:ran-reference",
          },
          ref_kind: "offer",
          value: "demo:offer:ran-reference:v1",
        },
        operations: ["reserve", "activate", "measure", "release"],
        provenance: {
          decision_refs: ["demo:segment:v1"],
          issuer: "adcos:runtime:demo-optimizer",
        },
        role: "primary",
        segment_id:
          "sha256:2fef7e706639dc9c180fe15cd8d2820e9c341bc01385c952d912f6af905821f0",
        state: "RELEASED",
      },
    ],
    tie_break: ["role", "offer", "segment-id"],
    validity: {
      not_after: "2026-10-14T00:00:00Z",
      not_before: "2026-09-14T00:00:00Z",
    },
  },
};

/** The demonstration contract as the developer API sees it (for the drawer's live read). */
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

/* ------------------------------------------------------------------ *
 * The local harness (fetch mocked at the global boundary)
 * ------------------------------------------------------------------ */

/** Recorder-safe response fake (headers.forEach + clone.text). */
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

/** The enveloped success shape every /api/2.0 read returns. */
function envelope<T>(data: T): unknown {
  return {
    api_version: "2.0",
    environment: "sandbox",
    request_id: "sha256:harness_request_id",
    data,
  };
}

/**
 * Route fetch by `METHOD path` (exact keys only; unmatched fails loudly).
 * A vi.fn so assertions can inspect the exact requests the page made.
 */
function routeFetch(routes: Record<string, unknown>) {
  return vi.fn((path: string, init?: RequestInit) => {
    const method = (init?.method ?? "GET").toUpperCase();
    const key = `${method} ${path}`;
    if (!(key in routes)) {
      return Promise.resolve(
        errorResponse(
          {
            error: {
              reason: "route-unknown",
              message: `harness has no route for ${key}`,
            },
          },
          404,
        ),
      );
    }
    return Promise.resolve(okResponse(routes[key]));
  });
}

/** Renders inside the REAL SessionProvider with a real connect() flow. */
function renderWithSession(ui: ReactNode, _fetchImpl?: unknown) {
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

/** Renders inside the SessionProvider WITHOUT connecting. */
function renderBare(ui: ReactNode) {
  return render(<SessionProvider>{ui}</SessionProvider>);
}

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/evidence",
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
  __resetRecorderForTests();
  __resetDemoRunsForTests();
  __resetCommandRegistryForTests();
  pushMock.mockClear();
});

describe("Evidence explorer", () => {
  it("fetches the current demo document on load, records it, and renders every record member VERBATIM with the class carried visibly", async () => {
    const fetchMock = routeFetch({
      "GET /api/2.0/application": envelope(FIXTURE_APPLICATION),
      "GET /demo/contract-fulfillment": FIXTURE_DEMO_DOCUMENT,
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<EvidenceExplorer />, fetchMock);

    // the on-load demo read ran through the platform route
    await waitFor(() => {
      expect(
        fetchMock.mock.calls.filter(([path]) => path === "/demo/contract-fulfillment"),
      ).toHaveLength(1);
    });

    // both records render with their members verbatim
    const observationId =
      "evidence:observation:7e6e275466ed7559cfce3768b83cb9ee0230ec3d52b21d87375609ed7db5b1f7";
    const attestationId =
      "evidence:attestation:8bf42deca4011e0cb230ca0a7980eae09dc007063faaca5e59c918fb497572e0";
    await waitFor(() => {
      expect(screen.getByText(observationId)).toBeInTheDocument();
    });
    expect(screen.getByText(attestationId)).toBeInTheDocument();

    const observationCard = screen
      .getAllByTestId("evidence-record")
      .find((card) => card.getAttribute("data-record-type") === "observation");
    expect(observationCard).toBeDefined();
    expect(
      within(observationCard as HTMLElement).getByText("link-up = 1"),
    ).toBeInTheDocument();
    expect(
      within(observationCard as HTMLElement).getByText("10000 bps"),
    ).toBeInTheDocument();
    expect(
      within(observationCard as HTMLElement).getByText("2026-09-14T02:00:00Z"),
    ).toBeInTheDocument();
    expect(
      within(observationCard as HTMLElement).getByText("provider:ran-reference"),
    ).toBeInTheDocument();
    expect(
      within(observationCard as HTMLElement).getAllByText("observation").length,
    ).toBeGreaterThan(0);

    const attestationCard = screen
      .getAllByTestId("evidence-record")
      .find((card) => card.getAttribute("data-record-type") === "attestation");
    expect(
      within(attestationCard as HTMLElement).getByText("controller-verified = 1"),
    ).toBeInTheDocument();
    expect(
      within(attestationCard as HTMLElement).getByText("2026-09-15T02:00:00Z"),
    ).toBeInTheDocument();

    // the contract_ref links into the contract page
    expect(
      screen
        .getAllByRole("link")
        .some(
          (link) =>
            link.getAttribute("href") === `/connectivity/contracts/${DEMO_CONTRACT_ID}`,
        ),
    ).toBe(true);

    // the run group carries the document's evidence_class VERBATIM as SOFTWARE
    const runGroup = screen.getByTestId("demo-run-group");
    const runBadge = within(runGroup).getByTestId(EVIDENCE_BADGE_TEST_IDS.root);
    expect(runBadge.getAttribute("data-kind")).toBe("software");
    expect(runBadge).toHaveTextContent("SOFTWARE");

    // SOFTWARE never becomes physical: no badge anywhere is physical-kind
    const allBadges = screen.getAllByTestId(EVIDENCE_BADGE_TEST_IDS.root);
    expect(allBadges.length).toBeGreaterThan(0);
    for (const badge of allBadges) {
      expect(badge.getAttribute("data-kind")).not.toBe("physical");
    }
  });

  it("renders the badge legend: SOFTWARE / sandbox-simulation verbatim and the physical/network family as NOT-ACHIEVABLE-BY-THIS-DEPLOYMENT", async () => {
    const fetchMock = routeFetch({
      "GET /api/2.0/application": envelope(FIXTURE_APPLICATION),
      "GET /demo/contract-fulfillment": FIXTURE_DEMO_DOCUMENT,
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<EvidenceExplorer />, fetchMock);

    await waitFor(() => {
      expect(screen.getByTestId("demo-run-group")).toBeInTheDocument();
    });

    const legend = screen.getByTestId("evidence-class-legend");
    expect(within(legend).getByText("SOFTWARE")).toBeInTheDocument();
    expect(within(legend).getByText("sandbox-simulation")).toBeInTheDocument();
    expect(within(legend).getByText(/NOT-ACHIEVABLE-BY-THIS-DEPLOYMENT/)).toBeInTheDocument();
    // the legend's software rows stay software-kind (never physical)
    const legendBadges = within(legend).getAllByTestId(EVIDENCE_BADGE_TEST_IDS.root);
    for (const badge of legendBadges) {
      expect(badge.getAttribute("data-kind")).toBe("software");
    }
  });

  it("opens the detail drawer with the full record, the source_refs, the related contract (live read) and the JSON view", async () => {
    const fetchMock = routeFetch({
      "GET /api/2.0/application": envelope(FIXTURE_APPLICATION),
      "GET /demo/contract-fulfillment": FIXTURE_DEMO_DOCUMENT,
      [`GET /api/2.0/contracts/${DEMO_CONTRACT_ID}`]: envelope(FIXTURE_DEMO_CONTRACT),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<EvidenceExplorer />, fetchMock);

    const observationCard = await waitFor(() => {
      const card = screen
        .getAllByTestId("evidence-record")
        .find((node) => node.getAttribute("data-record-type") === "observation");
      expect(card).toBeDefined();
      return card as HTMLElement;
    });

    fireEvent.click(observationCard);

    const dialog = await waitFor(() => {
      return screen.getByRole("dialog");
    });
    const drawer = within(dialog);
    expect(
      drawer.getAllByText(
        "evidence:observation:7e6e275466ed7559cfce3768b83cb9ee0230ec3d52b21d87375609ed7db5b1f7",
      ).length,
    ).toBeGreaterThan(0);

    // the full source_ref renders in the drawer (it is truncated on the card)
    expect(
      drawer.getByText(
        "sha256:35cfdec9219b152ba7bd8ed9dbfc7153ea14dd12a870c1945350328c0e5dab89",
      ),
    ).toBeInTheDocument();

    // the related contract live read resolves and renders its state
    await waitFor(() => {
      expect(within(dialog).getAllByText("CONTRACT_ACTIVE").length).toBeGreaterThan(0);
    });

    // the provenance block carries the run's boundary entry
    expect(drawer.getByText(/run boundary/)).toBeInTheDocument();

    // the JSON view of the record is present
    expect(drawer.getByText("record:")).toBeInTheDocument();
  });

  it("shows the honest empty state when no runs exist (disconnected — no auto read fires)", async () => {
    const fetchMock = routeFetch({});
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<EvidenceExplorer />);

    expect(screen.getByTestId("evidence-empty")).toBeInTheDocument();
    expect(screen.getByText("No demonstration runs yet")).toBeInTheDocument();

    // the guidance names both ways to make a run (the button AND the copy)
    expect(screen.getByTestId("evidence-empty").textContent).toContain(
      "fulfillment demonstration",
    );
    expect(screen.getByTestId("evidence-empty").textContent).toContain(
      "Run demo read",
    );

    // the platform demo read NEVER fired while disconnected
    const demoCalls = fetchMock.mock.calls.filter(
      ([path]) => path === "/demo/contract-fulfillment",
    );
    expect(demoCalls).toHaveLength(0);
  });

  it("runs the platform demo read on demand (no session needed) and records the run", async () => {
    const fetchMock = routeFetch({
      "GET /demo/contract-fulfillment": FIXTURE_DEMO_DOCUMENT,
    });
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<EvidenceExplorer />);

    fireEvent.click(screen.getByTestId("evidence-run-demo"));

    await waitFor(() => {
      expect(screen.getByTestId("demo-run-group")).toBeInTheDocument();
    });
    expect(
      screen.getByText(
        "evidence:observation:7e6e275466ed7559cfce3768b83cb9ee0230ec3d52b21d87375609ed7db5b1f7",
      ),
    ).toBeInTheDocument();

    const demoCalls = fetchMock.mock.calls.filter(
      ([path]) => path === "/demo/contract-fulfillment",
    );
    expect(demoCalls).toHaveLength(1);
  });
});
