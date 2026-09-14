/**
 * Fulfillment tests — the overview + the demonstration run detail against
 * the REAL captured demonstration document (FIXTURE_DEMO_DOCUMENT, routed
 * RAW — the /demo platform route does not use the developer-API envelope):
 *
 * - the overview lists the default demonstration run and the honest
 *   scope note (no backend run registry);
 * - a run registered in this browser session appears in the list;
 * - "Run demonstration" POSTs {"instant"} to /demo/contract-fulfillment
 *   and renders the compact summary (contract link, SOFTWARE badge);
 * - disconnected: NO authenticated contracts fetch; connect guidance;
 * - connected: GET /api/2.0/contracts (bodyless default page) with auth headers and
 *   the contract rows link into /connectivity/contracts/{id};
 * - the run detail renders the FULL chain verbatim (boundary trace, plan
 *   with constraint_fingerprint/segment state/operations/tie_break,
 *   execution milestones, samples, evidence cards, SOFTWARE badges, the
 *   determinism note, the contract link);
 * - the run detail renders a malformed-instant failure VERBATIM
 *   (invalid-input).
 */

import { describe, expect, it, vi, beforeEach, type Mock } from "vitest";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FulfillmentOverview, RunDetailView } from "@/features/fulfillment";
import {
  DEFAULT_DEMO_INSTANT,
  __resetDemoRunsForTests,
  registerDemoRun,
} from "@/features/fulfillment/demo-runs";
import type { DemoDocument } from "@/lib/api/types";
import {
  FIXTURE_CONTRACTS_LIST,
  FIXTURE_DEMO_DOCUMENT,
  FIXTURE_SESSION,
} from "./fixtures";
import {
  APPLICATION_ROUTE,
  envelope,
  renderBare,
  renderWithSession,
  routeFetch,
} from "./harness";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
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

/* ---- typed reads over the fixture's raw members (the demo document's
 * contract/plan/execution members are Record<string, unknown> on the wire;
 * these casts are the captured shapes, not inventions) ---- */

const doc = FIXTURE_DEMO_DOCUMENT as DemoDocument & {
  contract: {
    contract_id: string;
    state: string;
  };
  plan: {
    plan_id: string;
    constraint_fingerprint: string;
    tie_break: string[];
  };
  execution: {
    reservation_id: string;
    activation_id: string;
    binding_id: string;
    measurement_id: string;
    release_id: string;
  };
};

const DEMO_ROUTE: Record<string, unknown> = {
  "POST /demo/contract-fulfillment": FIXTURE_DEMO_DOCUMENT,
};

/** The harness router wrapped in a spy so the tests can assert on calls. */
function makeFetcher(
  routes: Record<string, unknown>,
): Mock & ((path: string, init?: RequestInit) => Promise<Response>) {
  return vi.fn(routeFetch(routes)) as unknown as Mock &
    ((path: string, init?: RequestInit) => Promise<Response>);
}

/** The recorded (path, init) calls a spy fetcher saw. */
function fetchCalls(
  fetchMock: Mock,
): [string, (RequestInit & { headers?: unknown }) | undefined][] {
  return fetchMock.mock.calls as [string, (RequestInit & { headers?: unknown }) | undefined][];
}

beforeEach(() => {
  __resetDemoRunsForTests();
  pushMock.mockClear();
});

function section(id: string): HTMLElement {
  const element = document.getElementById(id);
  expect(element).not.toBeNull();
  return element as HTMLElement;
}

function linksTo(href: string): HTMLElement[] {
  return screen
    .getAllByRole("link")
    .filter((link) => link.getAttribute("href") === href);
}

/* ------------------------------------------------------------------ */

describe("Fulfillment overview", () => {
  it("lists the default demonstration run and the honest scope note", () => {
    const fetchMock = makeFetcher({ ...DEMO_ROUTE });
    vi.stubGlobal("fetch", fetchMock);
    renderBare(<FulfillmentOverview />);

    // the default demonstration row always links to its run detail
    const defaultLink = screen.getByRole("link", {
      name: /the default demonstration/i,
    });
    expect(defaultLink).toHaveAttribute(
      "href",
      `/fulfillment/run/${encodeURIComponent(DEFAULT_DEMO_INSTANT)}`,
    );

    // the honest scope note: the backend exposes no run registry
    expect(screen.getAllByText(/no run registry/i).length).toBeGreaterThan(0);

    // the honest empty state before any session run
    expect(
      screen.getByText("No demonstration runs in this session yet"),
    ).toBeInTheDocument();
  });

  it("shows a run registered in this browser session", async () => {
    const fetchMock = makeFetcher({ ...DEMO_ROUTE });
    vi.stubGlobal("fetch", fetchMock);
    renderBare(<FulfillmentOverview />);

    await act(async () => {
      registerDemoRun({
        instant: doc.instant,
        ranAt: "2026-09-14T00:05:00Z",
        contractId: doc.contract.contract_id,
        planId: doc.plan.plan_id,
      });
    });

    // the run row links to its run detail and its contract detail
    const runLink = screen.getByRole("link", { name: doc.instant });
    expect(runLink).toHaveAttribute(
      "href",
      `/fulfillment/run/${encodeURIComponent(doc.instant)}`,
    );
    const contractLink = screen.getByTitle(doc.contract.contract_id);
    expect(contractLink).toHaveAttribute(
      "href",
      `/connectivity/contracts/${doc.contract.contract_id}`,
    );

    // the honest empty state is gone once a session run exists
    expect(
      screen.queryByText("No demonstration runs in this session yet"),
    ).toBeNull();
  });

  it("POSTs {instant} to /demo/contract-fulfillment and shows the summary", async () => {
    const fetchMock = makeFetcher({ ...DEMO_ROUTE });
    vi.stubGlobal("fetch", fetchMock);
    renderBare(<FulfillmentOverview />);

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Run demonstration" }));

    await waitFor(() => {
      expect(screen.getByTestId("demo-run-summary")).toBeInTheDocument();
    });

    // the exact request: method + path + body (the RAW document route —
    // no developer-API envelope on /demo/*)
    const demoCalls = fetchCalls(fetchMock).filter(
      ([path]) => path === "/demo/contract-fulfillment",
    );
    expect(demoCalls).toHaveLength(1);
    const [, init] = demoCalls[0];
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toEqual({
      instant: DEFAULT_DEMO_INSTANT,
    });

    // the compact summary: mode/environment verbatim, SOFTWARE badge,
    // contract link, plan id, final segment state
    expect(screen.getByText("Demonstration complete")).toBeInTheDocument();
    expect(screen.getAllByText("sandbox").length).toBeGreaterThanOrEqual(2);
    const badges = screen
      .getAllByTestId("evidence-badge")
      .filter((badge) => badge.textContent === "SOFTWARE");
    expect(badges.length).toBeGreaterThan(0);
    expect(
      linksTo(`/connectivity/contracts/${doc.contract.contract_id}`).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText(doc.plan.plan_id)).toBeInTheDocument();
    expect(screen.getAllByText("RELEASED").length).toBeGreaterThan(0);

    // the prominent link to the run detail
    expect(
      screen.getByRole("link", { name: /open the demonstration run/i }),
    ).toHaveAttribute(
      "href",
      `/fulfillment/run/${encodeURIComponent(DEFAULT_DEMO_INSTANT)}`,
    );

    // the run was registered in the browser-session list
    expect(
      screen.getByRole("link", { name: DEFAULT_DEMO_INSTANT }),
    ).toHaveAttribute(
      "href",
      `/fulfillment/run/${encodeURIComponent(DEFAULT_DEMO_INSTANT)}`,
    );
  });

  it("disconnected: fires no authenticated contracts read and shows connect guidance", () => {
    const fetchMock = makeFetcher({ ...DEMO_ROUTE });
    vi.stubGlobal("fetch", fetchMock);
    renderBare(<FulfillmentOverview />);

    // nothing was fetched at all on mount (the demo only runs on click;
    // the contracts read is suspended without a session)
    expect(fetchMock).not.toHaveBeenCalled();

    // the honest connect guidance
    expect(
      screen.getByText(/connect an application to read the contract list/i),
    ).toBeInTheDocument();
  });

  it("connected: reads GET /api/2.0/contracts (bodyless default page, authed) and links rows to the contract detail", async () => {
    const fetchMock = makeFetcher({
      ...APPLICATION_ROUTE,
      "GET /api/2.0/contracts": envelope(FIXTURE_CONTRACTS_LIST),
      ...DEMO_ROUTE,
    });
    vi.stubGlobal("fetch", fetchMock);
    renderWithSession(
      <FulfillmentOverview />,
      fetchMock as unknown as ReturnType<typeof routeFetch>,
    );

    const first = FIXTURE_CONTRACTS_LIST.items[0];
    await waitFor(() => {
      expect(screen.getByText(first.contract_id)).toBeInTheDocument();
    });

    // the authenticated list read: the BODYLESS GET (browsers cannot send
    // the API's GET-body list discipline) with the auth headers
    const contractsCalls = fetchCalls(fetchMock).filter(
      ([path]) => path === "/api/2.0/contracts",
    );
    expect(contractsCalls.length).toBeGreaterThanOrEqual(1);
    const [, init] = contractsCalls[0];
    expect(init?.method).toBe("GET");
    expect(init?.body).toBeUndefined();
    const headers = init?.headers as Record<string, string>;
    expect(headers["X-ADCOS-Application"]).toBe(FIXTURE_SESSION.applicationId);
    expect(headers["X-ADCOS-Credential"]).toBe(FIXTURE_SESSION.credential);

    // both captured rows render; no connect guidance while connected
    const second = FIXTURE_CONTRACTS_LIST.items[1];
    expect(screen.getByText(second.contract_id)).toBeInTheDocument();
    expect(
      screen.queryByText(/connect an application to read the contract list/i),
    ).toBeNull();

    // the id cell links into the contract detail; activating the row does too
    expect(
      linksTo(`/connectivity/contracts/${first.contract_id}`).length,
    ).toBeGreaterThan(0);
    const user = userEvent.setup();
    await user.click(screen.getByText(first.contract_id).closest("tr")!);
    expect(pushMock).toHaveBeenCalledWith(
      `/connectivity/contracts/${first.contract_id}`,
    );
  });
});

/* ------------------------------------------------------------------ */

describe("Demonstration run detail", () => {
  it("renders the full chain from the captured document, verbatim", async () => {
    const fetchMock = makeFetcher({ ...DEMO_ROUTE });
    vi.stubGlobal("fetch", fetchMock);
    renderBare(<RunDetailView instant={doc.instant} />);

    await waitFor(() => {
      expect(
        screen.getByRole("table", { name: "Boundary trace" }),
      ).toBeInTheDocument();
    });

    // the boundary trace: method, route, status, request_id
    const boundary = screen.getByRole("table", { name: "Boundary trace" });
    expect(within(boundary).getByText("POST")).toBeInTheDocument();
    expect(within(boundary).getByText("/api/2.0/intents")).toBeInTheDocument();
    expect(within(boundary).getByText("200")).toBeInTheDocument();
    const boundaryEntry = doc.boundary[0];
    expect(
      within(boundary).getByTitle(boundaryEntry.request_id),
    ).toBeInTheDocument();
    // the ApiRequestPanel reproduction of the boundary request
    expect(
      screen.getAllByTestId("api-method-chip").filter((chip) => {
        return chip.textContent === "POST";
      }).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByText(
        `the demonstration's boundary request — request_id ${boundaryEntry.request_id}, status ${boundaryEntry.status}`,
      ),
    ).toBeInTheDocument();

    // the plan: constraint_fingerprint verbatim, segment state RELEASED,
    // operations chips, tie_break
    const plan = section("plan");
    expect(
      within(plan).getByText(doc.plan.constraint_fingerprint),
    ).toBeInTheDocument();
    const statuses = within(plan)
      .getAllByTestId("status-root")
      .filter((status) => status.getAttribute("data-value") === "RELEASED");
    expect(statuses.length).toBeGreaterThan(0);
    for (const operation of ["reserve", "activate", "measure", "release"]) {
      expect(within(plan).getByText(operation)).toBeInTheDocument();
    }
    const tieBreakLabel = within(plan).getByText("tie_break");
    const tieBreakChips = tieBreakLabel.parentElement?.querySelector("ul");
    expect(tieBreakChips).not.toBeNull();
    for (const tieBreak of doc.plan.tie_break) {
      expect(
        within(tieBreakChips as HTMLElement).getByText(tieBreak),
      ).toBeInTheDocument();
    }
    // the segment-state kernel renders the document's segment_states chain
    for (const state of ["PLANNED", "RESERVED", "ACTIVATED", "MEASURED"]) {
      expect(within(plan).getByText(state)).toBeInTheDocument();
    }
    expect(within(plan).getAllByText("RELEASED").length).toBeGreaterThan(1);

    // the execution milestones (all verbatim from the document)
    const execution = section("execution");
    expect(
      within(execution).getByText(doc.execution.reservation_id),
    ).toBeInTheDocument();
    expect(
      within(execution).getByText(doc.execution.activation_id),
    ).toBeInTheDocument();
    expect(
      within(execution).getByText(doc.execution.binding_id),
    ).toBeInTheDocument();
    expect(
      within(execution).getByText(doc.execution.measurement_id),
    ).toBeInTheDocument();
    expect(
      within(execution).getByText(doc.execution.release_id),
    ).toBeInTheDocument();
    expect(within(execution).getByText("deterministic-reference-adapter")).toBeInTheDocument();

    // the samples table: metric, observed_at, value
    const samples = screen.getByRole("table", { name: "Execution samples" });
    expect(within(samples).getByText("link-up")).toBeInTheDocument();
    expect(within(samples).getByText("rx-bytes-total")).toBeInTheDocument();
    expect(within(samples).getByText("1")).toBeInTheDocument();
    expect(within(samples).getAllByText("3000").length).toBeGreaterThan(0);

    // the evidence cards: observation + attestation, producers, confidence,
    // metric — all verbatim, every card SOFTWARE-badged
    const evidence = section("evidence");
    expect(within(evidence).getByText("observation")).toBeInTheDocument();
    expect(within(evidence).getByText("attestation")).toBeInTheDocument();
    expect(within(evidence).getByText("provider:ran-reference")).toBeInTheDocument();
    expect(
      within(evidence).getByText("adcos:runtime:demo-attestor"),
    ).toBeInTheDocument();
    expect(within(evidence).getAllByText("10000").length).toBeGreaterThan(0);
    expect(within(evidence).getByText("link-up")).toBeInTheDocument();
    const softwareBadges = screen
      .getAllByTestId("evidence-badge")
      .filter((badge) => badge.textContent === "SOFTWARE");
    expect(softwareBadges.length).toBeGreaterThanOrEqual(2);

    // the determinism note, stated plainly
    expect(
      screen.getByText(/identical instant → identical document/i),
    ).toBeInTheDocument();

    // the contract link (header meta, contract section, evidence cards)
    expect(
      linksTo(`/connectivity/contracts/${doc.contract.contract_id}`).length,
    ).toBeGreaterThan(0);
  });

  it("renders a malformed-instant failure VERBATIM with a way back", async () => {
    const errorBody = {
      api_version: "2.0",
      environment: "sandbox",
      request_id: "sha256:demoerr",
      error: {
        canonical_reason: "",
        environment: "sandbox",
        http_status: 400,
        message: "the demo instant must be an RFC 3339 UTC string",
        reason: "invalid-input",
        request_id: "sha256:demoerr",
        resource_id: "",
        retry_after: "",
        retryable: false,
      },
    };
    const fetchMock = routeFetch({
      "POST /demo/contract-fulfillment": { __status: 400, body: errorBody },
    });
    vi.stubGlobal("fetch", fetchMock);
    renderBare(<RunDetailView instant="not-an-instant" />);

    await waitFor(() => {
      expect(screen.getByTestId("error-reason")).toBeInTheDocument();
    });
    expect(screen.getByTestId("error-reason")).toHaveTextContent(
      "invalid-input",
    );
    expect(
      screen.getByText("the demo instant must be an RFC 3339 UTC string"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /back to the fulfillment overview/i }),
    ).toHaveAttribute("href", "/fulfillment");
  });
});
