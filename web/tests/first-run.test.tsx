/**
 * First-run education tests — the V2 product-education surface of Home
 * (plan Task 4, the frozen design §5/§13/§17): the fresh/disconnected
 * state, the clickable lifecycle, the eight goal paths, the
 * connected-empty first-contract path, the connected-nonempty expert
 * dashboard, and the honest degraded note.
 *
 * Station harness discipline: fetch mocked at the GLOBAL boundary with
 * REAL fixture envelopes; the page renders inside the REAL
 * SessionProvider; NO network. Registry-content expectations are
 * hard-coded on purpose (proving the W1 registry's own strings reach
 * the UI, not a circular lookup) — the same convention as
 * learning-primitives.test.tsx.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HomeView } from "@/features/home";
import {
  ADCOS_ANCHOR_SENTENCE,
  FIRST_CONTRACT_PATH_TEST_ID,
  FIRST_RUN_DEGRADED_TEST_ID,
  FIRST_RUN_TEST_ID,
  GOAL_PATH_TEST_ID,
  LIFECYCLE_STAGE_TEST_ID,
} from "@/features/home/first-run-card";
import { __resetRequestLogForTests } from "@/features/requests/request-log";
import {
  FIXTURE_CONTRACTS_LIST,
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

/* ------------------------------------------------------------------ *
 * REAL registry content expectations (hard-coded on purpose)
 * ------------------------------------------------------------------ */

const ELIGIBILITY_SUMMARY =
  /The reasoning for why a contract's flow state is what it is/;
const REPLAN_TERM = "Replan / failover";

beforeEach(() => {
  __resetRequestLogForTests();
});

describe("First-run education — the fresh (disconnected) state", () => {
  it("shows the education surface: the §5 anchor sentence verbatim, the six lifecycle stages and the eight goal paths", async () => {
    const fetchMock = routeFetch({
      "GET /readyz": FIXTURE_READINESS,
    });
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<HomeView />);

    // the education surface is the FIRST thing mounted (V1 cards stay
    // below with their honest disconnected states)
    expect(screen.getByTestId(FIRST_RUN_TEST_ID)).toBeInTheDocument();

    // the frozen anchor sentence — VERBATIM, one text node
    expect(screen.getByText(ADCOS_ANCHOR_SENTENCE)).toBeInTheDocument();

    // the mental model as a clickable lifecycle — six stages, in order
    const stages = screen.getAllByTestId(LIFECYCLE_STAGE_TEST_ID);
    expect(stages).toHaveLength(6);
    expect(stages.map((stage) => stage.textContent?.replace(/\s*\?\s*$/, ""))).toEqual([
      "Describe requirement",
      "Eligibility",
      "Plan",
      "Fulfillment",
      "Assurance",
      "Continuous fulfillment",
    ]);
    for (const stage of stages) {
      expect(stage).toHaveAttribute("aria-haspopup", "dialog");
      expect(stage).toHaveAttribute("aria-expanded", "false");
    }

    // the one-contract visual: the line + the provider-boundary honesty
    expect(
      screen.getByText(
        "One connectivity contract, many networks, continuous fulfillment.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/the console never draws a provider graph/),
    ).toBeInTheDocument();

    // the eight §13 goal paths — every one a REAL link, no dead ends
    const goals = screen.getAllByTestId(GOAL_PATH_TEST_ID);
    expect(goals).toHaveLength(8);
    const hrefs = screen
      .getAllByRole("link")
      .map((link) => link.getAttribute("href"));
    for (const goalHref of [
      "/quickstart",
      "/docs/start/what-is-adcos",
      "/docs/concepts/connectivity-contract",
      "/developers",
      "/docs/api",
      "/fulfillment",
      "/connectivity",
      "/settings/errors",
      "/docs/troubleshooting",
      "/docs/guides/integrate-provider-adapter",
    ]) {
      expect(hrefs).toContain(goalHref);
    }

    // the goal labels (the frozen §13 list, verbatim)
    for (const goal of [
      "Get connectivity",
      "Understand my connectivity",
      "Connect my application",
      "Integrate the API",
      "Monitor fulfillment",
      "Understand a decision",
      "Diagnose a failure",
      "Add or integrate a provider",
    ]) {
      expect(screen.getByText(goal)).toBeInTheDocument();
    }

    // the obvious next action while disconnected: the Quickstart
    expect(
      screen.getByRole("link", { name: /Start the Quickstart/ }),
    ).toHaveAttribute("href", "/quickstart");

    // the platform read still works; the authenticated one never fires
    await waitFor(() => {
      expect(screen.getByText("all backends ready")).toBeInTheDocument();
    });
  });

  it("clicking a lifecycle stage opens its explanation carrying the REAL registry content", async () => {
    const user = userEvent.setup();
    const fetchMock = routeFetch({
      "GET /readyz": FIXTURE_READINESS,
    });
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<HomeView />);

    // the Eligibility stage opens the eligibility concept's education
    const eligibilityStage = screen
      .getAllByTestId(LIFECYCLE_STAGE_TEST_ID)
      .find((stage) => stage.textContent?.startsWith("Eligibility"));
    expect(eligibilityStage).toBeDefined();
    await user.click(eligibilityStage as HTMLElement);

    const dialog = await screen.findByRole("dialog", {
      name: "Concept: Eligibility",
    });
    // the registry's own summary reaches the drawer
    expect(within(dialog).getByText(ELIGIBILITY_SUMMARY)).toBeInTheDocument();
    // the registry's related API operations reach the drawer verbatim
    expect(within(dialog).getByText("intent_lifecycle")).toBeInTheDocument();
    expect(within(dialog).getByText("contract_get")).toBeInTheDocument();
    // the drawer links the concept's full documentation
    expect(
      within(dialog)
        .getAllByRole("link")
        .some((link) => link.getAttribute("href") === "/docs/concepts/eligibility"),
    ).toBe(true);
  });

  it("the Continuous fulfillment stage opens the replan/failover concept education", async () => {
    const user = userEvent.setup();
    const fetchMock = routeFetch({
      "GET /readyz": FIXTURE_READINESS,
    });
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<HomeView />);

    const continuousStage = screen
      .getAllByTestId(LIFECYCLE_STAGE_TEST_ID)
      .find((stage) => stage.textContent?.startsWith("Continuous fulfillment"));
    await user.click(continuousStage as HTMLElement);

    const dialog = await screen.findByRole("dialog", {
      name: `Concept: ${REPLAN_TERM}`,
    });
    // the registry's own summary rides along as the drawer description
    expect(
      within(dialog).getByText(
        /The explicit re-composition of an accepted contract's fulfillment/,
      ),
    ).toBeInTheDocument();
  });
});

describe("First-run education — the connected states", () => {
  it("connected-and-empty shows the education surface plus the obvious first-contract path", async () => {
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

    expect(screen.getByTestId(FIRST_RUN_TEST_ID)).toBeInTheDocument();
    expect(
      screen.getByTestId(FIRST_CONTRACT_PATH_TEST_ID),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Create your first contract/ }),
    ).toHaveAttribute("href", "/connectivity");
    expect(
      screen.getByRole("link", { name: /Take the guided Quickstart/ }),
    ).toHaveAttribute("href", "/quickstart");
    // the education content is all still there
    expect(screen.getByText(ADCOS_ANCHOR_SENTENCE)).toBeInTheDocument();
    expect(screen.getAllByTestId(GOAL_PATH_TEST_ID)).toHaveLength(8);
  });

  it("connected-with-contracts keeps the expert workbench primary — no education surface", async () => {
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
    expect(screen.queryByTestId(FIRST_RUN_TEST_ID)).toBeNull();
    expect(
      screen.getByRole("heading", { level: 1, name: "Home" }),
    ).toBeInTheDocument();
    // the V1 workbench cards all stay
    expect(screen.getByText("System health")).toBeInTheDocument();
    expect(screen.getByText("What connectivity is managed")).toBeInTheDocument();
    expect(screen.getByText("What is changing")).toBeInTheDocument();
    expect(screen.getByText("What needs attention")).toBeInTheDocument();
    expect(screen.getByText("The fulfillment demonstration")).toBeInTheDocument();
  });
});

describe("First-run education — the degraded state is honest", () => {
  it("carries the V1 degraded vocabulary when readiness reports degraded coordination", async () => {
    const fetchMock = routeFetch({
      "GET /readyz": FIXTURE_READINESS_DEGRADED,
    });
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<HomeView />);

    // the education surface's own honest note (V1 vocabulary)
    await waitFor(() => {
      expect(
        screen.getByTestId(FIRST_RUN_DEGRADED_TEST_ID),
      ).toBeInTheDocument();
    });
    expect(screen.getByTestId(FIRST_RUN_DEGRADED_TEST_ID)).toHaveTextContent(
      "degraded readiness",
    );
    // the note points at the honest runtime state, not away from it
    expect(
      screen.getByTestId(FIRST_RUN_DEGRADED_TEST_ID),
    ).toHaveTextContent(/System health/);
    // the education content still renders (it describes the product)
    expect(screen.getByText(ADCOS_ANCHOR_SENTENCE)).toBeInTheDocument();
    // the V1 system health card carries the degraded state verbatim too
    expect(screen.getAllByText("degraded readiness").length).toBeGreaterThanOrEqual(
      2,
    );
  });
});
