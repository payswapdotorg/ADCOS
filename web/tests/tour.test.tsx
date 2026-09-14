/**
 * Interactive fulfillment-tour tests (plan Task 5, the frozen design
 * §7): the stage sequence Requirement → Eligibility → Plan → Execution
 * → Evidence → Assurance with the four affordances at every stage
 * (Explain this / View object / View API request / View API response),
 * the real document slices, the evidence-class honesty note, the
 * determinism position and the honest read-failure state.
 *
 * Station harness discipline: fetch mocked at the GLOBAL boundary with
 * the REAL demonstration document fixture; the tour renders inside the
 * REAL SessionProvider (the tour's read is the unauthenticated platform
 * GET); NO network. Registry-content expectations are hard-coded on
 * purpose (the W1 registry's own strings reaching the UI).
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  FulfillmentTourView,
  TOUR_BACK_TEST_ID,
  TOUR_CONTINUE_TEST_ID,
  TOUR_END_TEST_ID,
  TOUR_OBJECT_PANEL_TEST_ID,
  TOUR_REQUEST_PANEL_TEST_ID,
  TOUR_RESPONSE_PANEL_TEST_ID,
  TOUR_STAGE_TEST_ID,
} from "@/features/tour/fulfillment-tour";
import { __resetRequestLogForTests } from "@/features/requests/request-log";
import {
  ERROR_REASON_TEST_ID,
  EVIDENCE_BADGE_TEST_IDS,
} from "@/components/ui";
import { NEXT_STEPS_TEST_ID } from "@/features/learning";
import { FIXTURE_DEMO_DOCUMENT } from "./fixtures";
import { renderBare, routeFetch } from "./harness";

vi.mock("next/navigation", () => ({
  usePathname: () => "/tour",
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

/** The tour's standard routes (the single demonstration read). */
function tourRoutes(): Record<string, unknown> {
  return {
    "GET /demo/contract-fulfillment": FIXTURE_DEMO_DOCUMENT,
  };
}

function trackedFetch(routes: Record<string, unknown>) {
  const routed = routeFetch(routes);
  return vi.fn((path: string, init?: RequestInit) => routed(path, init));
}

type User = ReturnType<typeof userEvent.setup>;

/** Wait for the tour to load and stand on the Requirement stage. */
async function waitForTour(): Promise<void> {
  await waitFor(() => {
    expect(screen.getByTestId(TOUR_STAGE_TEST_ID)).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 2, name: "Requirement" }),
    ).toBeInTheDocument();
  });
}

beforeEach(() => {
  __resetRequestLogForTests();
});

describe("The fulfillment tour — the stage sequence", () => {
  it("reveals the six stages in order with Continue, and Back returns", async () => {
    const user = userEvent.setup();
    const fetchMock = trackedFetch(tourRoutes());
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<FulfillmentTourView />);
    await waitForTour();

    const stages = ["Eligibility", "Plan", "Execution", "Evidence", "Assurance"];
    for (const stage of stages) {
      await user.click(screen.getByTestId(TOUR_CONTINUE_TEST_ID));
      expect(
        screen.getByRole("heading", { level: 2, name: stage }),
      ).toBeInTheDocument();
    }

    // the last stage finishes the tour — the end screen
    expect(
      screen.getByRole("button", { name: "Finish the tour" }),
    ).toBeInTheDocument();
    await user.click(screen.getByTestId(TOUR_CONTINUE_TEST_ID));
    expect(screen.getByTestId(TOUR_END_TEST_ID)).toBeInTheDocument();

    // Back from the end returns to the Assurance stage
    await user.click(screen.getByTestId(TOUR_BACK_TEST_ID));
    expect(
      screen.getByRole("heading", { level: 2, name: "Assurance" }),
    ).toBeInTheDocument();

    // the tour's read: ONE unauthenticated GET, never re-fetched while
    // walking the stages
    const getCalls = fetchMock.mock.calls.filter(
      ([path, init]) =>
        path === "/demo/contract-fulfillment" &&
        (init?.method ?? "GET").toUpperCase() === "GET",
    );
    expect(getCalls).toHaveLength(1);
  });

  it("renders the real stage facts from the demonstration document", async () => {
    const user = userEvent.setup();
    const fetchMock = trackedFetch(tourRoutes());
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<FulfillmentTourView />);
    await waitForTour();

    // Requirement — the contract's own members, verbatim
    expect(screen.getByText("CONTRACT_ACTIVE")).toBeInTheDocument();
    expect(screen.getByText(/latency-bound/)).toBeInTheDocument();
    expect(screen.getByText(/throughput-floor/)).toBeInTheDocument();

    // Eligibility — the boundary trace
    await user.click(screen.getByTestId(TOUR_CONTINUE_TEST_ID));
    expect(screen.getByText("/api/2.0/intents")).toBeInTheDocument();
    expect(screen.getByText(/capability reasoning/)).toBeInTheDocument();

    // Plan — the real plan id and composition
    await user.click(screen.getByTestId(TOUR_CONTINUE_TEST_ID));
    expect(
      screen.getAllByText(/da58d8b9c09953f1/).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText(/primary: reserve → activate → measure → release/)).toBeInTheDocument();

    // Execution — the provider facts and the segment-state chain
    await user.click(screen.getByTestId(TOUR_CONTINUE_TEST_ID));
    expect(
      screen.getByText("deterministic-reference-adapter"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/PLANNED → RESERVED → ACTIVATED → MEASURED → RELEASED/),
    ).toBeInTheDocument();

    // Evidence — the record types, SOFTWARE-badged (the concept's own
    // education also uses the word "observations" — both are real)
    await user.click(screen.getByTestId(TOUR_CONTINUE_TEST_ID));
    expect(screen.getAllByText(/observation/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/attestation/).length).toBeGreaterThan(0);
    expect(
      screen.getByTestId(EVIDENCE_BADGE_TEST_IDS.root),
    ).toBeInTheDocument();

    // Assurance — the referenced obligations, honestly unevaluated
    await user.click(screen.getByTestId(TOUR_CONTINUE_TEST_ID));
    expect(
      screen.getByText(/demo:assurance-obligation:v1/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Referenced material, never evaluated here/),
    ).toBeInTheDocument();
  });
});

describe("The fulfillment tour — the four affordances", () => {
  it("Explain this opens the stage's concept education with REAL registry content", async () => {
    const user = userEvent.setup();
    const fetchMock = trackedFetch(tourRoutes());
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<FulfillmentTourView />);
    await waitForTour();

    await user.click(screen.getByTestId("tour-explain"));
    const dialog = await screen.findByRole("dialog", {
      name: "Concept: Connectivity contract",
    });
    expect(
      within(dialog).getByText(
        /durable record of the connectivity an application asks ADCOS/,
      ),
    ).toBeInTheDocument();
  });

  it("View object shows the stage's real DemoDocument slice", async () => {
    const user = userEvent.setup();
    const fetchMock = trackedFetch(tourRoutes());
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<FulfillmentTourView />);
    await waitForTour();

    const toggle = screen.getByTestId("tour-view-object");
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");

    // the contract slice — the real contract_id, verbatim
    const panel = screen.getByTestId(TOUR_OBJECT_PANEL_TEST_ID);
    expect(
      within(panel).getAllByText(/78f563858281c8ca/).length,
    ).toBeGreaterThan(0);
    expect(within(panel).getByText(/contract:/)).toBeInTheDocument();
  });

  it("View API request and View API response show the REAL request/response pair", async () => {
    const user = userEvent.setup();
    const fetchMock = trackedFetch(tourRoutes());
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<FulfillmentTourView />);
    await waitForTour();

    // the request the tour actually made — the read-only GET
    await user.click(screen.getByTestId("tour-view-request"));
    const requestPanel = screen.getByTestId(TOUR_REQUEST_PANEL_TEST_ID);
    expect(
      within(requestPanel).getByText(
        /curl -X GET '\/demo\/contract-fulfillment'/,
      ),
    ).toBeInTheDocument();
    expect(within(requestPanel).getByText("GET")).toBeInTheDocument();

    // the response that came back — the full document (top-level
    // members visible at the default expansion depth: the leaves and
    // every container one expand away — the collapse is the viewer's,
    // never a hidden value)
    await user.click(screen.getByTestId("tour-view-response"));
    const responsePanel = screen.getByTestId(TOUR_RESPONSE_PANEL_TEST_ID);
    expect(
      within(responsePanel).getAllByText(/2026-09-14T00:00:00Z/).length,
    ).toBeGreaterThan(0);
    expect(
      within(responsePanel).getAllByText(/evidence/).length,
    ).toBeGreaterThan(0);
    expect(
      within(responsePanel).getAllByText(/plan/).length,
    ).toBeGreaterThan(0);
    // the evidence_class leaf, verbatim (JSON string value)
    expect(within(responsePanel).getByText(/SOFTWARE/)).toBeInTheDocument();
  });
});

describe("The fulfillment tour — the end and the honesty positions", () => {
  it("ends with the evidence-class honesty note and the next paths", async () => {
    const user = userEvent.setup();
    const fetchMock = trackedFetch(tourRoutes());
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<FulfillmentTourView />);
    await waitForTour();

    // walk to the end
    for (let stage = 0; stage < 6; stage += 1) {
      await user.click(screen.getByTestId(TOUR_CONTINUE_TEST_ID));
    }
    const end = screen.getByTestId(TOUR_END_TEST_ID);

    // SOFTWARE stays software — the dashed software badge
    const badge = within(end).getByTestId(EVIDENCE_BADGE_TEST_IDS.root);
    expect(badge).toHaveTextContent("SOFTWARE");
    expect(badge).toHaveAttribute("data-kind", "software");

    // the V1 legend vocabulary, verbatim
    expect(
      within(end).getByText("NOT-ACHIEVABLE-BY-THIS-DEPLOYMENT"),
    ).toBeInTheDocument();

    // the determinism note
    expect(
      within(end).getByText(/Identical instant → identical document/),
    ).toBeInTheDocument();

    // the next paths — real destinations only
    expect(within(end).getByTestId(NEXT_STEPS_TEST_ID)).toBeInTheDocument();
    // the concept-kind next step opens the education drawer (not a link)
    expect(
      within(end).getByRole("button", {
        name: /Learn: Evidence — SOFTWARE class, honestly labeled/,
      }),
    ).toBeInTheDocument();
    const hrefs = within(end)
      .getAllByRole("link")
      .map((link) => link.getAttribute("href"));
    for (const nextHref of [
      "/quickstart",
      "/fulfillment",
      "/evidence",
      "/",
    ]) {
      expect(hrefs).toContain(nextHref);
    }
  });

  it("is deterministic: the same document yields the same tour", async () => {
    const user = userEvent.setup();
    const fetchMock = trackedFetch(tourRoutes());
    vi.stubGlobal("fetch", fetchMock);

    async function walkCollecting(): Promise<string[]> {
      const { unmount } = renderBare(<FulfillmentTourView />);
      await waitForTour();
      const collected: string[] = [];
      for (let stage = 0; stage < 6; stage += 1) {
        const stageRegion = screen.getByTestId(TOUR_STAGE_TEST_ID);
        collected.push(
          within(stageRegion).getByRole("heading", { level: 2 }).textContent ??
            "",
        );
        // the stage's real identifier facts ride along (queryAll — some
        // stages' fact rows carry no sha256 values, honestly)
        collected.push(
          ...within(stageRegion)
            .queryAllByText(/sha256:[0-9a-f]{8}/)
            .map((node) => node.textContent ?? ""),
        );
        await user.click(screen.getByTestId(TOUR_CONTINUE_TEST_ID));
      }
      expect(screen.getByTestId(TOUR_END_TEST_ID)).toBeInTheDocument();
      unmount();
      return collected;
    }

    const first = await walkCollecting();
    const second = await walkCollecting();
    expect(second).toEqual(first);
  });
});

describe("The fulfillment tour — honest under failure", () => {
  it("shows the ErrorState with retry when the read fails, and recovers", async () => {
    const user = userEvent.setup();
    let getCalls = 0;
    const fetchMock = trackedFetch({
      "GET /demo/contract-fulfillment": () => {
        getCalls += 1;
        if (getCalls === 1) {
          return {
            __status: 503,
            body: {
              error: {
                reason_code: "backend-unreachable",
                message: "the runtime is not ready",
                backend: null,
              },
            },
          };
        }
        return FIXTURE_DEMO_DOCUMENT;
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<FulfillmentTourView />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    expect(screen.getByTestId(ERROR_REASON_TEST_ID)).toHaveTextContent(
      "backend-unreachable",
    );
    // no stage content is fabricated while the read is unavailable
    expect(screen.queryByTestId(TOUR_STAGE_TEST_ID)).toBeNull();

    await user.click(screen.getByRole("button", { name: "Retry" }));
    await waitForTour();
  });
});
