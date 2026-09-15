/**
 * Build docs tests — the "Build with ADCOS" documentation section (the
 * frozen Build-with-ADCOS design §8, plan Task 4) at the FEATURE-
 * COMPONENT level (the station harness discipline: hoisted
 * vi.mock("next/navigation") + vi.mock("next/link"), the pages rendered
 * inside the REAL SessionProvider, NO network — the pages are registry
 * data plus curated prose).
 *
 * Covers:
 * - the SEVEN section pages render (the hub, the four pattern pages, the
 *   lifecycle implementation and the production checklist), through both
 *   the direct components and the [id] dispatcher;
 * - the ShareNet boundary teaching (design §13) appears VERBATIM on the
 *   gateway/relay reference page, with the explicit anti-patterns;
 * - every /docs/api/{id} href the pages render resolves to a REAL
 *   coverage-registry operation (import COVERAGE in the test and assert
 *   it — no second endpoint catalog);
 * - every page links back to /docs/build;
 * - the docs home IA shows the Build section BETWEEN Guides and API with
 *   its seven-page entries and the /build console CTA;
 * - the hub lists the five patterns from the registry and links the four
 *   pattern pages plus the console deep link for the fifth;
 * - an unknown slug renders the honest not-found state;
 * - the ?from= contextual return path renders on a build docs page.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import { renderBare } from "./harness";
import { COVERAGE } from "@/lib/api/coverage";
import { INTEGRATION_PATTERNS } from "@/lib/integration";
import {
  BUILD_DOCS_SECTION,
  BUILD_PAGE_TEST_IDS,
  BUILD_PAGES,
  BuildApplicationPage,
  BuildChecklistPage,
  BuildFleetSubscriberPage,
  BuildGatewayRelayPage,
  BuildLifecyclePage,
  BuildPatternDocPage,
  BuildProviderPage,
  BuildSectionHub,
  DOCS_HOME_TEST_IDS,
  DocsHome,
  DOCS_RETURN_PATH_TEST_ID,
  SHARENET_ADCOS_AUTHORITY,
  SHARENET_APPLICATION_AUTHORITY,
  SHARENET_OFFLINE_RULE,
  SHARENET_P2P_TRANSFER_RULE,
  SHARENET_PROVIDER_AUTHORITY,
} from "@/features/docs";

/* ------------------------------------------------------------------ *
 * The hoisted module mocks (the harness pattern)
 * ------------------------------------------------------------------ */

/** The search params the mocked useSearchParams returns (per-test). */
let mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  usePathname: () => "/docs/build",
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

/** The operation ids the coverage registry actually carries. */
const COVERAGE_IDS = new Set(COVERAGE.map((record) => record.operation));

/**
 * Every /docs/api/{id} href inside the container resolves to a REAL
 * coverage-registry operation — the no-second-endpoint-catalog rule,
 * asserted from the rendered output itself.
 */
function assertOperationLinksResolve(container: HTMLElement): number {
  const apiLinks = within(container)
    .getAllByRole("link")
    .filter((link) => (link.getAttribute("href") ?? "").startsWith("/docs/api/"));
  expect(apiLinks.length, "the page links at least one operation").toBeGreaterThan(0);
  for (const link of apiLinks) {
    const operationId = (link.getAttribute("href") as string)
      .replace("/docs/api/", "")
      .split("#")[0];
    expect(
      COVERAGE_IDS.has(operationId),
      `operation "${operationId}" exists in the coverage registry`,
    ).toBe(true);
  }
  return apiLinks.length;
}

/** The page links back to /docs/build (the section's return path). */
function assertLinksBackToBuildSection(container: HTMLElement): void {
  const links = within(container).getAllByRole("link");
  expect(
    links.some((link) => link.getAttribute("href") === "/docs/build"),
    "links back to /docs/build",
  ).toBe(true);
}

/** Render one page and return its container (unmounted by the caller). */
function renderPage(ui: React.ReactElement) {
  const view = renderBare(ui);
  return view;
}

/* ------------------------------------------------------------------ *
 * 1. The seven pages render
 * ------------------------------------------------------------------ */

describe("the seven Build with ADCOS pages", () => {
  it("renders the hub (Choose an integration pattern) with the five registry patterns and the right links", () => {
    const view = renderPage(<BuildSectionHub />);

    expect(screen.getByRole("heading", { level: 1, name: "Choose an integration pattern" })).toBeDefined();
    expect(
      screen.getByText(/exactly how should ADCOS fit into my architecture/i),
    ).toBeDefined();

    // the five patterns from the integration registry, with summaries
    const rows = screen.getAllByTestId(BUILD_PAGE_TEST_IDS.patternRow);
    expect(rows).toHaveLength(INTEGRATION_PATTERNS.length);
    for (const pattern of INTEGRATION_PATTERNS) {
      const row = rows.find((candidate) => candidate.getAttribute("data-pattern") === pattern.id);
      expect(row, `row for pattern "${pattern.id}"`).toBeDefined();
      const scoped = within(row as HTMLElement);
      expect(scoped.getByText(pattern.title)).toBeDefined();
      expect(scoped.getByText(pattern.summary)).toBeDefined();
      expect(scoped.getByRole("link")).toHaveAttribute(
        "href",
        pattern.id === "marketplace-orchestration"
          ? "/build?pattern=marketplace-orchestration"
          : `/docs/build/${
              pattern.id === "provider-adapter" ? "provider" : pattern.id
            }`,
      );
    }

    // the /build console CTA
    const links = screen.getAllByRole("link");
    expect(links.some((link) => link.getAttribute("href") === "/build")).toBe(true);

    // the hub is the section root itself: its breadcrumb links /docs
    expect(links.some((link) => link.getAttribute("href") === "/docs")).toBe(true);

    view.unmount();
  });

  it("renders each section page through the [id] dispatcher with its heading, real operation links and the section return path", () => {
    for (const page of BUILD_PAGES) {
      const view = renderPage(<BuildPatternDocPage pageId={page.id} />);
      expect(
        screen.getByRole("heading", { level: 1, name: page.title }),
        `heading of "${page.id}"`,
      ).toBeDefined();
      assertOperationLinksResolve(view.container);
      assertLinksBackToBuildSection(view.container);
      view.unmount();
    }
  });

  it("renders the four pattern pages directly, each with the registry's ownership facts and anti-patterns", () => {
    const patternPages = [
      { id: "application", Component: BuildApplicationPage },
      { id: "gateway-relay", Component: BuildGatewayRelayPage },
      { id: "fleet-subscriber", Component: BuildFleetSubscriberPage },
      { id: "provider-adapter", Component: BuildProviderPage },
    ];
    for (const { id, Component } of patternPages) {
      const view = renderPage(<Component />);
      const pattern = INTEGRATION_PATTERNS.find((candidate) => candidate.id === id);
      expect(pattern, `registry pattern "${id}"`).toBeDefined();
      if (!pattern) {
        view.unmount();
        continue;
      }

      // the three-way ownership map renders the registry's own lists
      for (const owned of pattern.applicationOwns) {
        expect(screen.getAllByText(owned, { exact: true }).length).toBeGreaterThanOrEqual(1);
      }
      for (const owned of pattern.adcosOwns) {
        expect(screen.getAllByText(owned, { exact: true }).length).toBeGreaterThanOrEqual(1);
      }
      for (const owned of pattern.providerOwns) {
        expect(screen.getAllByText(owned, { exact: true }).length).toBeGreaterThanOrEqual(1);
      }

      // the anti-patterns render explicitly
      for (const antiPattern of pattern.antiPatterns) {
        expect(screen.getAllByText(antiPattern).length).toBeGreaterThanOrEqual(1);
      }

      // the forward /build deep link for this pattern
      const links = screen.getAllByRole("link");
      expect(
        links.some((link) => link.getAttribute("href") === `/build?pattern=${id}`),
        `"${id}" links its /build?pattern= deep link`,
      ).toBe(true);

      assertOperationLinksResolve(view.container);
      assertLinksBackToBuildSection(view.container);
      view.unmount();
    }
  });

  it("renders the lifecycle page: the canonical stages mapped to real operations, with idempotency and versioning notes", () => {
    const view = renderPage(<BuildLifecyclePage />);

    for (const stage of [
      "1. Intent",
      "2. Eligibility",
      "3. Offer",
      "4. Contract",
      "5. Execution",
      "6. Provider realization",
      "7. Evidence + Assurance",
    ]) {
      expect(screen.getByRole("heading", { name: stage }), stage).toBeDefined();
    }

    // the stage operations link to their operation documentation
    for (const operationId of [
      "intent_create",
      "intent_lifecycle",
      "offers_accept",
      "contract_activate",
      "contract_get",
      "contract_assurance",
    ]) {
      expect(screen.getAllByRole("link", { name: operationId }).length).toBeGreaterThanOrEqual(1);
    }

    // the idempotency + versioning notes
    expect(screen.getByText(/Every mutation request carries an idempotency key/i)).toBeDefined();
    expect(screen.getByText(/\/api\/2\.0/)).toBeDefined();

    assertOperationLinksResolve(view.container);
    assertLinksBackToBuildSection(view.container);
    view.unmount();
  });

  it("renders the production checklist page with the six items in full", () => {
    const view = renderPage(<BuildChecklistPage />);

    for (const item of [
      "Authentication",
      "Versioning",
      "Idempotency",
      "Error handling",
      "Evidence",
      "Degradation",
    ]) {
      expect(screen.getByRole("heading", { name: item }), item).toBeDefined();
    }

    // the honest operating contract, stated
    expect(screen.getByText(/never the HTTP status alone/i)).toBeDefined();
    expect(screen.getByText(/NOT-ACHIEVABLE-BY-THIS-DEPLOYMENT/i)).toBeDefined();
    expect(screen.getByText(/local data plane keeps operating when ADCOS is unreachable/i)).toBeDefined();

    assertLinksBackToBuildSection(view.container);
    view.unmount();
  });

  it("renders the honest not-found state for an unknown build slug", () => {
    const view = renderPage(<BuildPatternDocPage pageId="not-a-build-page" />);

    expect(screen.getByTestId(BUILD_PAGE_TEST_IDS.unknown)).toBeDefined();
    expect(screen.getByText("not-a-build-page")).toBeDefined();
    expect(
      screen.getByRole("link", { name: /Back to Build with ADCOS/i }),
    ).toHaveAttribute("href", "/docs/build");
    view.unmount();
  });
});

/* ------------------------------------------------------------------ *
 * 2. The ShareNet reference page (design §13)
 * ------------------------------------------------------------------ */

describe("the gateway/relay page — the ShareNet reference integration", () => {
  it("states the canonical boundary diagram and the authority sentences VERBATIM", () => {
    const view = renderPage(<BuildGatewayRelayPage />);

    // the boundary diagram nodes (structured markup, not an image)
    expect(screen.getByText("ShareNet content/P2P plane")).toBeDefined();
    expect(screen.getByText("ADCOS Connectivity Contract")).toBeDefined();
    expect(screen.getByText("Provider realization")).toBeDefined();
    expect(screen.getByText(/technology-neutral gateway\/relay connectivity need/i)).toBeDefined();

    // the §13 authority sentences — the exported constants AND the
    // literal hard-coded text (they must agree)
    expect(screen.getByText(SHARENET_APPLICATION_AUTHORITY)).toBeDefined();
    expect(screen.getByText(SHARENET_ADCOS_AUTHORITY)).toBeDefined();
    expect(screen.getByText(SHARENET_PROVIDER_AUTHORITY)).toBeDefined();
    expect(screen.getByText(SHARENET_P2P_TRANSFER_RULE)).toBeDefined();
    expect(screen.getByText(SHARENET_OFFLINE_RULE)).toBeDefined();
    expect(
      screen.getByText(
        "ShareNet keeps authority over content, P2P distribution, publisher trust, delivery receipts and application economics.",
      ),
    ).toBeDefined();

    view.unmount();
  });

  it("names the explicit anti-patterns", () => {
    const view = renderPage(<BuildGatewayRelayPage />);

    expect(screen.getByText(/Second contract authority/)).toBeDefined();
    expect(screen.getByText(/Provider coupling/)).toBeDefined();
    expect(screen.getByText(/Webhook-as-authority/)).toBeDefined();
    expect(screen.getByText(/API-success-as-physical-success/)).toBeDefined();
    expect(screen.getByText(/Routing local P2P transfers through ADCOS/)).toBeDefined();

    view.unmount();
  });
});

/* ------------------------------------------------------------------ *
 * 3. The docs home IA wiring (§8 ordering: between Guides and API)
 * ------------------------------------------------------------------ */

describe("the docs home IA — the Build with ADCOS section", () => {
  it("shows the Build section between Guides and API, with its page entries and the /build console CTA", () => {
    const view = renderPage(<DocsHome />);

    const groups = screen.getAllByTestId(DOCS_HOME_TEST_IDS.group);
    const sectionIds = groups.map((group) => group.getAttribute("data-section"));
    const guidesIndex = sectionIds.indexOf("guides");
    const buildIndex = sectionIds.indexOf("build");
    const apiIndex = sectionIds.indexOf("api");

    expect(guidesIndex).toBeGreaterThanOrEqual(0);
    expect(buildIndex, "the Build section renders").toBeGreaterThanOrEqual(0);
    expect(apiIndex).toBeGreaterThanOrEqual(0);
    expect(buildIndex, "Build comes after Guides").toBeGreaterThan(guidesIndex);
    expect(apiIndex, "API comes after Build").toBeGreaterThan(buildIndex);

    // the section header links the hub route
    const buildGroup = groups[buildIndex] as HTMLElement;
    expect(
      within(buildGroup).getByRole("link", { name: BUILD_DOCS_SECTION.label }),
    ).toHaveAttribute("href", "/docs/build");

    // every section page is listed, plus the /build console CTA
    const buildLinks = within(buildGroup).getAllByRole("link");
    for (const page of BUILD_PAGES) {
      expect(
        buildLinks.some((link) => link.getAttribute("href") === `/docs/build/${page.id}`),
        `the IA lists ${page.id}`,
      ).toBe(true);
    }
    expect(buildLinks.some((link) => link.getAttribute("href") === "/build")).toBe(true);

    // the V2 sections all remain — additions only
    for (const section of ["start", "concepts", "guides", "api", "sdk", "errors", "troubleshooting", "reference"]) {
      expect(sectionIds, `the ${section} section remains`).toContain(section);
    }

    view.unmount();
  });
});

/* ------------------------------------------------------------------ *
 * 4. The contextual return path on a build docs page
 * ------------------------------------------------------------------ */

describe("the ?from= contextual return path", () => {
  it("renders on the gateway/relay page when a console workflow opened the docs", () => {
    mockSearchParams = new URLSearchParams("from=/build");
    const view = renderPage(<BuildGatewayRelayPage />);

    const affordance = screen.getByTestId(DOCS_RETURN_PATH_TEST_ID);
    expect(affordance.getAttribute("data-from")).toBe("/build");
    expect(
      within(affordance).getByRole("link", { name: /Return to \/build/ }),
    ).toHaveAttribute("href", "/build");

    view.unmount();
  });
});
