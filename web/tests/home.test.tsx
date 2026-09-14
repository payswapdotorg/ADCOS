/**
 * Home dashboard tests — REAL captured shapes only (tests/fixtures.ts),
 * fetch mocked at the global boundary through the shared harness.
 *
 * Covers the frozen UX spec's Home demands:
 * - readiness mode/environment VERBATIM + honest degraded presentation;
 * - the contracts summary (state counts "of N fetched", detail links);
 * - the session gate: NO authenticated contracts read while
 *   disconnected, honest connect guidance instead;
 * - fresh-account guidance when the list is empty;
 * - the demonstration affordance: exact POST body/method/path, honest
 *   summary (SOFTWARE evidence badge, verbatim mode/environment,
 *   RELEASED final segment state), registration in the shared
 *   demo-run registry, and verbatim reason display on rejection.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { HomeView } from "@/features/home";
import {
  __resetDemoRunsForTests,
  getDemoRuns,
} from "@/features/fulfillment/demo-runs";
import { __resetRequestLogForTests } from "@/features/requests/request-log";
import {
  ERROR_REASON_TEST_ID,
  EVIDENCE_BADGE_TEST_IDS,
} from "@/components/ui";
import {
  FIXTURE_CONTRACTS_LIST,
  FIXTURE_CONTRACT_INTENT,
  FIXTURE_DEMO_DOCUMENT,
  FIXTURE_READINESS,
  FIXTURE_READINESS_DEGRADED,
} from "./fixtures";
import {
  APPLICATION_ROUTE,
  envelope,
  renderBare,
  renderWithSession,
  routeFetch,
} from "./harness";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
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

/**
 * A rejected demonstration instant (POST /demo/contract-fulfillment) —
 * the platform runtime's error envelope shape ({error: {reason_code,
 * message, backend}}) with the invalid-input reason. The message text
 * is a local test scaffold; the assertion targets the VERBATIM reason.
 */
const DEMO_INVALID_INSTANT = {
  error: {
    reason_code: "invalid-input",
    message: "instant must be an RFC 3339 UTC timestamp",
    backend: null,
  },
} as const;

/**
 * routeFetch returns a plain routing function (its cast carries no real
 * call log); wrap it in a vi.fn so assertions can inspect the exact
 * requests the page made — method, path and body.
 */
function trackedFetch(routes: Record<string, unknown>) {
  const routed = routeFetch(routes);
  return vi.fn((path: string, init?: RequestInit) => routed(path, init));
}

beforeEach(() => {
  __resetRequestLogForTests();
  __resetDemoRunsForTests();
});

describe("Home — system health", () => {
  it("renders readiness mode/environment verbatim with the sandbox empty-backends note", async () => {
    const fetchMock = routeFetch({
      ...APPLICATION_ROUTE,
      "GET /readyz": FIXTURE_READINESS,
      "GET /api/2.0/contracts": envelope(FIXTURE_CONTRACTS_LIST),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<HomeView />, fetchMock);

    await waitFor(() => {
      expect(screen.getByText("all backends ready")).toBeInTheDocument();
    });
    // mode + environment, verbatim from the payload, in mono fields
    expect(screen.getAllByText("sandbox").length).toBeGreaterThanOrEqual(2);
    // the honest sandbox wording (mirrors the shell)
    expect(
      screen.getByText("no durable backends (sandbox mode)"),
    ).toBeInTheDocument();
    // the check is labeled with a client-side timestamp — set in an effect
    // on the commit AFTER the data lands, so the assertion must wait for
    // that second commit (deterministic under full-suite event-loop load)
    await waitFor(() => {
      expect(screen.getByText(/checked at/)).toBeInTheDocument();
    });
    // provider/adapter inspection is one link away
    expect(
      screen
        .getAllByRole("link")
        .some((link) => link.getAttribute("href") === "/networks"),
    ).toBe(true);
  });

  it("shows the degraded presentation and the unavailable backend with its detail", async () => {
    const fetchMock = routeFetch({
      ...APPLICATION_ROUTE,
      "GET /readyz": FIXTURE_READINESS_DEGRADED,
      "GET /api/2.0/contracts": envelope(FIXTURE_CONTRACTS_LIST),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<HomeView />, fetchMock);

    await waitFor(() => {
      expect(screen.getByText("degraded readiness")).toBeInTheDocument();
    });
    // mode + environment verbatim from the degraded payload
    expect(screen.getAllByText("production").length).toBeGreaterThanOrEqual(2);
    // both backends with their VERBATIM states and details (the not-ready
    // backend also appears under "needs attention" — hence getAllByText)
    expect(screen.getByText("neon-postgres")).toBeInTheDocument();
    expect(screen.getAllByText("upstash-redis").length).toBeGreaterThan(0);
    expect(screen.getByText("ready")).toBeInTheDocument();
    expect(screen.getAllByText("unavailable").length).toBeGreaterThan(0);
    expect(
      screen.getAllByText(
        "connection refused (degraded — ephemeral coordination only)",
      ).length,
    ).toBeGreaterThan(0);
  });
});

describe("Home — what connectivity is managed", () => {
  it("renders both fixture contracts with computed state counts and detail links", async () => {
    const fetchMock = routeFetch({
      ...APPLICATION_ROUTE,
      "GET /readyz": FIXTURE_READINESS,
      "GET /api/2.0/contracts": envelope(FIXTURE_CONTRACTS_LIST),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<HomeView />, fetchMock);

    await waitFor(() => {
      expect(screen.getByText(/of 2 fetched/)).toBeInTheDocument();
    });
    // state counts computed from the fetched list (2 × CONTRACT_ACTIVE)
    expect(screen.getByTestId("state-count-CONTRACT_ACTIVE")).toHaveTextContent(
      "2",
    );
    // each fixture contract links to its detail page
    for (const item of FIXTURE_CONTRACTS_LIST.items) {
      const href = `/connectivity/contracts/${item.contract_id}`;
      expect(
        screen
          .getAllByRole("link")
          .some((link) => link.getAttribute("href") === href),
      ).toBe(true);
    }
    // state rows link to the connectivity index
    expect(
      screen
        .getAllByRole("link")
        .some((link) => link.getAttribute("href") === "/connectivity"),
    ).toBe(true);
  });

  it("surfaces INTENT contracts under needs attention with the honest phrase", async () => {
    const fetchMock = routeFetch({
      ...APPLICATION_ROUTE,
      "GET /readyz": FIXTURE_READINESS,
      "GET /api/2.0/contracts": envelope({
        items: [FIXTURE_CONTRACT_INTENT],
        next_cursor: "",
        has_more: false,
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<HomeView />, fetchMock);

    await waitFor(() => {
      expect(screen.getByText("awaiting offer selection")).toBeInTheDocument();
    });
    const href = `/connectivity/contracts/${FIXTURE_CONTRACT_INTENT.contract_id}`;
    expect(
      screen
        .getAllByRole("link")
        .some((link) => link.getAttribute("href") === href),
    ).toBe(true);
    // attention states are real data — the calm line is not shown
    expect(screen.queryByText("Nothing needs attention.")).toBeNull();
  });

  it("fires NO authenticated contracts read while disconnected and shows connect guidance", async () => {
    const fetchMock = trackedFetch({
      "GET /readyz": FIXTURE_READINESS,
    });
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<HomeView />);

    // the platform read still works without a session
    await waitFor(() => {
      expect(screen.getByText("all backends ready")).toBeInTheDocument();
    });
    // the authenticated read was NEVER fired
    const contractsCalls = fetchMock.mock.calls.filter(
      ([path]) => path === "/api/2.0/contracts",
    );
    expect(contractsCalls).toHaveLength(0);
    // honest connect guidance (the session menu's own action name)
    expect(screen.getByText("Connect application")).toBeInTheDocument();
    // the session's platform activity is still shown honestly
    expect(screen.getByText(/in-memory/)).toBeInTheDocument();
  });

  it("shows the fresh-account guidance with the builder link when no contracts exist", async () => {
    const fetchMock = routeFetch({
      ...APPLICATION_ROUTE,
      "GET /readyz": FIXTURE_READINESS,
      "GET /api/2.0/contracts": envelope({
        items: [],
        next_cursor: "",
        has_more: false,
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<HomeView />, fetchMock);

    await waitFor(() => {
      expect(screen.getByText("No contracts yet")).toBeInTheDocument();
    });
    const builder = screen
      .getAllByRole("link")
      .find(
        (link) =>
          link.getAttribute("href") === "/connectivity" &&
          /New contract/.test(link.textContent ?? ""),
      );
    expect(builder).toBeDefined();
  });
});

describe("Home — the fulfillment demonstration", () => {
  it("POSTs the demonstration and renders the honest summary, registering the run", async () => {
    const fetchMock = trackedFetch({
      ...APPLICATION_ROUTE,
      "GET /readyz": FIXTURE_READINESS,
      "GET /api/2.0/contracts": envelope(FIXTURE_CONTRACTS_LIST),
      "POST /demo/contract-fulfillment": FIXTURE_DEMO_DOCUMENT,
    });
    vi.stubGlobal("fetch", fetchMock);

    // renderWithSession's second parameter is decorative (the session
    // reads the stubbed global fetch); the tracked vi.fn carries the
    // call log the assertions below inspect.
    renderWithSession(
      <HomeView />,
      fetchMock as unknown as ReturnType<typeof routeFetch>,
    );

    await waitFor(() => {
      expect(screen.getByText(/of 2 fetched/)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Run demonstration" }));

    await waitFor(() => {
      expect(screen.getByTestId("demo-summary")).toBeInTheDocument();
    });

    // the exact request: method, path, body (default instant)
    const demoCalls = fetchMock.mock.calls.filter(
      ([path, init]) =>
        path === "/demo/contract-fulfillment" && init?.method === "POST",
    );
    expect(demoCalls).toHaveLength(1);
    expect(JSON.parse(String(demoCalls[0][1]?.body))).toEqual({
      instant: "2026-09-13T00:00:00Z",
    });

    // the honest summary: SOFTWARE evidence, verbatim mode/environment,
    // final segment state, plan id, evidence record count
    const summary = screen.getByTestId("demo-summary");
    const badge = screen.getByTestId(EVIDENCE_BADGE_TEST_IDS.root);
    expect(badge).toHaveTextContent("SOFTWARE");
    expect(badge).toHaveAttribute("data-kind", "software");
    expect(summary).toHaveTextContent("sandbox");
    expect(summary).toHaveTextContent("RELEASED");
    expect(summary).toHaveTextContent(String(FIXTURE_DEMO_DOCUMENT.plan.plan_id));
    expect(screen.getByText("evidence records")).toBeInTheDocument();
    // the demonstration contract links to its detail (readable via the API)
    const contractHref = `/connectivity/contracts/${String(
      FIXTURE_DEMO_DOCUMENT.contract.contract_id,
    )}`;
    expect(
      screen
        .getAllByRole("link")
        .some((link) => link.getAttribute("href") === contractHref),
    ).toBe(true);
    // the overview link (the run detail route belongs to Fulfillment)
    expect(
      screen
        .getAllByRole("link")
        .some((link) => link.getAttribute("href") === "/fulfillment"),
    ).toBe(true);

    // the run was registered in the shared in-memory registry
    const runs = getDemoRuns();
    expect(
      runs.some(
        (run) =>
          run.instant === FIXTURE_DEMO_DOCUMENT.instant &&
          run.contractId === String(FIXTURE_DEMO_DOCUMENT.contract.contract_id) &&
          run.planId === String(FIXTURE_DEMO_DOCUMENT.plan.plan_id),
      ),
    ).toBe(true);
  });

  it("shows the verbatim backend reason when the instant is rejected", async () => {
    const fetchMock = routeFetch({
      ...APPLICATION_ROUTE,
      "GET /readyz": FIXTURE_READINESS,
      "GET /api/2.0/contracts": envelope(FIXTURE_CONTRACTS_LIST),
      "POST /demo/contract-fulfillment": {
        __status: 400,
        body: DEMO_INVALID_INSTANT,
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<HomeView />, fetchMock);

    await waitFor(() => {
      expect(screen.getByText(/of 2 fetched/)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/instant/i), {
      target: { value: "not-a-date" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run demonstration" }));

    await waitFor(() => {
      expect(screen.getByTestId(ERROR_REASON_TEST_ID)).toHaveTextContent(
        "invalid-input",
      );
    });
    // no summary is rendered for a failed run
    expect(screen.queryByTestId("demo-summary")).toBeNull();
  });
});
