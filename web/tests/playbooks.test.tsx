/**
 * Playbooks tests — the Console V2 guided paths (DEC-0128, Task 6 of
 * the frozen plan) at the FEATURE-COMPONENT level (the station harness
 * discipline: hoisted vi.mock("next/navigation") + vi.mock("next/link"),
 * feature components rendered inside the REAL SessionProvider, NO
 * network — playbooks are pure registry data, fetch is never called).
 *
 * Covers the work order's demands:
 * - the index renders EXACTLY the seven registry playbooks, grouped by
 *   experience goal (Build / Understand / Integrate / Diagnose), each
 *   with its registry title, purpose and concept chips;
 * - a REAL playbook page renders its steps with the registry's own
 *   titles/details and REAL link affordances: docs links, concept
 *   links, Explorer deep-links and the "Open in workbench" handoff —
 *   every one carrying the mirrored `?from=<playbook path>` context;
 * - the step checklist progresses (client state only);
 * - the route-local search filters the index (and the honest empty
 *   state for a term nothing matches);
 * - an unknown guide id renders the honest not-found state (no
 *   fabricated steps);
 * - the mirrored `?from=` return bar renders when a workflow opened the
 *   playbook with a linkable context.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { renderBare } from "./harness";
import { GUIDES, getGuide } from "@/lib/education";
import { coverageByOperation } from "@/lib/api/coverage";
import {
  PLAYBOOK_INDEX_TEST_IDS,
  PLAYBOOK_PAGE_TEST_IDS,
  PLAYBOOK_RETURN_PATH_TEST_ID,
  PlaybookIndex,
  PlaybookPage,
} from "@/features/playbooks";

/* ------------------------------------------------------------------ *
 * The hoisted module mocks (the harness pattern)
 * ------------------------------------------------------------------ */

/** The search params the mocked useSearchParams returns (per-test). */
let mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  usePathname: () => "/playbooks",
  useParams: () => ({}),
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  useSearchParams: () => mockSearchParams,
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: Record<string, unknown>) => (
    <a href={href as string} {...props}>
      {children as never}
    </a>
  ),
}));

beforeEach(() => {
  mockSearchParams = new URLSearchParams();
});

/* ------------------------------------------------------------------ */

describe("PlaybookIndex — the registry-driven guided-path index", () => {
  it("renders EXACTLY the seven registry playbooks, grouped by experience goal", () => {
    renderBare(<PlaybookIndex />);

    const rows = screen.getAllByTestId(PLAYBOOK_INDEX_TEST_IDS.row);
    expect(rows).toHaveLength(GUIDES.length);
    expect(GUIDES).toHaveLength(7);

    // the row set IS the registry (no invented playbook)
    const rendered = rows.map((row) => (row as HTMLElement).dataset.guide);
    const registry = GUIDES.map((guide) => guide.id);
    expect([...rendered].sort()).toEqual([...registry].sort());

    // the four experience-goal groups (design §4), with the exact
    // registry counts per group
    const groups = screen.getAllByTestId(PLAYBOOK_INDEX_TEST_IDS.group);
    expect(groups.map((group) => (group as HTMLElement).dataset.group)).toEqual([
      "build",
      "understand",
      "integrate",
      "diagnose",
    ]);
    const rowsIn = (group: string) =>
      screen
        .getAllByTestId(PLAYBOOK_INDEX_TEST_IDS.row)
        .filter((row) => {
          const section = row.closest("section");
          return section?.getAttribute("data-group") === group;
        });
    expect(rowsIn("build")).toHaveLength(1);
    expect(rowsIn("understand")).toHaveLength(2);
    expect(rowsIn("integrate")).toHaveLength(2);
    expect(rowsIn("diagnose")).toHaveLength(2);

    // a real row carries the registry's own title, purpose and step count
    const firstRow = rowsIn("build")[0];
    expect(firstRow).toHaveAttribute("data-guide", "first-connectivity-application");
    const guide = getGuide("first-connectivity-application");
    expect(guide).toBeDefined();
    expect(within(firstRow).getByText(guide!.title)).toBeInTheDocument();
    expect(within(firstRow).getByText(guide!.purpose)).toBeInTheDocument();
    expect(within(firstRow).getByText(`${guide!.steps.length} steps`)).toBeInTheDocument();
    expect(
      within(firstRow).getByRole("link", { name: new RegExp(guide!.title) }),
    ).toHaveAttribute("href", "/playbooks/first-connectivity-application");

    // the related-concept chips render the registry's own terms
    expect(within(firstRow).getByRole("button", { name: /What is: Offer/ })).toBeInTheDocument();
  });

  it("filters the index by the route-local search term (and the honest empty state)", () => {
    renderBare(<PlaybookIndex />);

    const search = screen.getByLabelText("Filter playbooks");
    expect(search).toBeInTheDocument();

    fireEvent.change(search as HTMLElement, { target: { value: "degraded" } });

    // only the degradation playbook matches — one row, still real
    const rows = screen.getAllByTestId(PLAYBOOK_INDEX_TEST_IDS.row);
    expect(rows).toHaveLength(1);
    expect(rows[0]).toHaveAttribute("data-guide", "handle-degraded-connectivity");

    // nothing matches a nonsense term: the honest empty state
    fireEvent.change(search as HTMLElement, { target: { value: "zzzz-no-match" } });
    expect(screen.queryAllByTestId(PLAYBOOK_INDEX_TEST_IDS.row)).toHaveLength(0);
    expect(screen.getByTestId(PLAYBOOK_INDEX_TEST_IDS.empty)).toBeInTheDocument();
    expect(screen.getByText("No playbook matches")).toBeInTheDocument();
    expect(screen.getByText(/nothing is invented to fill a match/i)).toBeInTheDocument();
  });
});

describe("PlaybookPage — one guide's stepped walkthrough", () => {
  it("renders the steps with their REAL link affordances, every one carrying ?from=<this playbook>", () => {
    renderBare(<PlaybookPage guideId="first-connectivity-application" />);

    const guide = getGuide("first-connectivity-application");
    expect(guide).toBeDefined();
    const fromParam = "from=%2Fplaybooks%2Ffirst-connectivity-application";

    // every step renders with the registry's own title and detail
    const steps = screen.getAllByTestId(PLAYBOOK_PAGE_TEST_IDS.step);
    expect(steps).toHaveLength(guide!.steps.length);
    for (const step of guide!.steps) {
      expect(screen.getByText(step.title, { exact: false })).toBeInTheDocument();
    }
    // the honest deployment wording renders VERBATIM (never softened)
    expect(
      screen.getByText(/Both are honest starting points; the demonstration is SOFTWARE evidence only/),
    ).toBeInTheDocument();

    // a docs-kind step link resolves to the docs route with the context
    const docsLink = screen.getByTestId("playbook-docs-link");
    expect(docsLink).toHaveAttribute("data-docs", "how-adcos-works");
    expect(docsLink.getAttribute("href")).toBe(`/docs/start/how-it-works?${fromParam}`);

    // an operation-kind step link is the Explorer deep link with the
    // context (the guide carries five operation steps; the first is
    // application_self)
    const operationLinks = screen.getAllByTestId("playbook-operation-link");
    expect(operationLinks.length).toBe(
      guide!.steps.filter((step) => step.link?.kind === "operation").length,
    );
    expect(operationLinks[0]).toHaveAttribute("data-operation", "application_self");
    expect(operationLinks[0].getAttribute("href")).toBe(
      `/developers/explorer?operation=application_self&${fromParam}`,
    );

    // a route-kind step renders the explicit "Open in workbench" handoff
    const workbenchLinks = screen.getAllByTestId("playbook-workbench-link");
    expect(workbenchLinks.length).toBe(2); // /developers + /developers/explorer
    expect(workbenchLinks[0].textContent).toContain("Open in workbench");
    expect(workbenchLinks[0].getAttribute("href")).toBe(`/developers?${fromParam}`);
    expect(workbenchLinks[1].getAttribute("href")).toBe(
      `/developers/explorer?${fromParam}`,
    );

    // the related operations are Explorer deep-links (registry ids)
    const related = screen.getAllByTestId("playbook-related-operation");
    expect(related.length).toBe(guide!.relatedOperations.length);
    for (const link of related) {
      const operationId = link.getAttribute("data-operation");
      const record = coverageByOperation(operationId ?? "");
      expect(record).toBeDefined(); // a REAL registry operation, never invented
      expect(link.getAttribute("href")).toContain(
        `/developers/explorer?operation=${operationId}`,
      );
    }

    // the related concepts render as chips (the W1 drawer primitive)
    expect(screen.getAllByRole("button", { name: /What is: / }).length).toBeGreaterThan(0);

    // the documentation twin is linked
    expect(
      screen.getByRole("link", { name: new RegExp("Docs → Guides") }),
    ).toHaveAttribute("href", "/docs/guides/first-connectivity-application");
  });

  it("renders a concept-kind step link to the concept's documentation page", () => {
    renderBare(<PlaybookPage guideId="understand-connectivity-contract" />);

    // the guide carries two concept steps; the first is the contract
    const conceptLinks = screen.getAllByTestId("playbook-concept-link");
    expect(conceptLinks.length).toBe(
      getGuide("understand-connectivity-contract")!.steps.filter(
        (step) => step.link?.kind === "concept",
      ).length,
    );
    expect(conceptLinks[0]).toHaveAttribute("data-concept", "connectivity-contract");
    expect(conceptLinks[0].getAttribute("href")).toBe(
      "/docs/concepts/connectivity-contract?from=%2Fplaybooks%2Funderstand-connectivity-contract",
    );
    expect(conceptLinks[1]).toHaveAttribute("data-concept", "execution-plan");
    expect(conceptLinks[1].getAttribute("href")).toBe(
      "/docs/concepts/execution-plan?from=%2Fplaybooks%2Funderstand-connectivity-contract",
    );
  });

  it("keeps the registry's honest deployment-exposure wording verbatim (never softened)", () => {
    renderBare(<PlaybookPage guideId="handle-degraded-connectivity" />);

    expect(
      screen.getByText(/Replan events are not currently exposed by this deployment/),
    ).toBeInTheDocument();
  });

  it("progresses the step checklist (client state only)", () => {
    renderBare(<PlaybookPage guideId="diagnose-fulfillment-failure" />);

    const guide = getGuide("diagnose-fulfillment-failure");
    expect(guide).toBeDefined();

    // the honest starting progress
    expect(screen.getByTestId(PLAYBOOK_PAGE_TEST_IDS.progress)).toHaveTextContent(
      `0 of ${guide!.steps.length} steps marked complete`,
    );

    // complete the first two steps
    const toggles = screen.getAllByTestId(PLAYBOOK_PAGE_TEST_IDS.stepToggle);
    expect(toggles).toHaveLength(guide!.steps.length);
    expect(toggles[0]).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(toggles[0]);
    fireEvent.click(toggles[1]);

    expect(screen.getByTestId(PLAYBOOK_PAGE_TEST_IDS.progress)).toHaveTextContent(
      `2 of ${guide!.steps.length} steps marked complete`,
    );
    expect(screen.getAllByTestId(PLAYBOOK_PAGE_TEST_IDS.step)[0]).toHaveAttribute(
      "data-complete",
      "true",
    );
    expect(toggles[0]).toHaveAttribute("aria-pressed", "true");

    // undo works
    fireEvent.click(toggles[0]);
    expect(screen.getByTestId(PLAYBOOK_PAGE_TEST_IDS.progress)).toHaveTextContent(
      `1 of ${guide!.steps.length} steps marked complete`,
    );
  });

  it("renders the honest not-found state for an unknown guide id", () => {
    renderBare(<PlaybookPage guideId="definitely-not-a-playbook" />);

    expect(screen.getByTestId(PLAYBOOK_PAGE_TEST_IDS.unknown)).toBeInTheDocument();
    expect(screen.getByText("No playbook matches this slug")).toBeInTheDocument();
    expect(screen.getByText("definitely-not-a-playbook")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Browse all playbooks" }),
    ).toHaveAttribute("href", "/playbooks");
    // no fabricated steps render
    expect(screen.queryAllByTestId(PLAYBOOK_PAGE_TEST_IDS.step)).toHaveLength(0);
  });

  it("renders the mirrored ?from= return bar when a workflow opened the playbook", () => {
    mockSearchParams = new URLSearchParams("from=/connectivity");

    renderBare(<PlaybookPage guideId="understand-connectivity-contract" />);

    const bar = screen.getByTestId(PLAYBOOK_RETURN_PATH_TEST_ID);
    expect(bar).toHaveAttribute("data-from", "/connectivity");
    expect(screen.getByRole("link", { name: /Return to \/connectivity/ })).toHaveAttribute(
      "href",
      "/connectivity",
    );
  });

  it("renders no return bar without a linkable ?from= (honest absence)", () => {
    renderBare(<PlaybookPage guideId="integrate-adcos-api" />);
    expect(screen.queryByTestId(PLAYBOOK_RETURN_PATH_TEST_ID)).toBeNull();
  });
});
