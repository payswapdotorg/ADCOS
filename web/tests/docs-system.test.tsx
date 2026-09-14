/**
 * Docs system tests — the Console V2 documentation system (DEC-0128,
 * Task 3 of the frozen plan) at the FEATURE-COMPONENT level (the
 * station harness discipline: hoisted vi.mock("next/navigation") +
 * vi.mock("next/link"), feature components rendered inside the REAL
 * SessionProvider, NO network — the docs are pure registry data, fetch
 * is never called).
 *
 * Covers the work order's demands:
 * - the concept index renders ALL 14 registry concepts (term + summary);
 * - a REAL concept page (eligibility) renders the six question sections
 *   with the registry's own content and links to its prerequisite
 *   concept pages;
 * - the guide index + a real guide page render steps with their links;
 * - the API hub renders the 25 registry operations grouped by lifecycle
 *   area, each linking to its operation page; an operation page renders
 *   the method/path VERBATIM from the coverage registry + the education
 *   fields;
 * - the errors page renders the canonical reason codes VERBATIM (each
 *   pinned code validated against the canonical describeError module);
 * - the SDK page is honest (the disclosure phrase present, no invented
 *   SDK install surface);
 * - the unknown slug renders the honest not-found state (no crash, no
 *   fabricated content);
 * - the `?from=` contextual return path renders and links back;
 * - the route-local search filters the concept index by term.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { renderBare } from "./harness";
import { COVERAGE, coverageByOperation } from "@/lib/api/coverage";
import { AdcosApiError, describeError } from "@/lib/api/errors";
import { CONCEPTS, GUIDES, getConcept, getGuide, getOperationEducation } from "@/lib/education";
import { STATUS_TONES } from "@/lib/design/tokens";
import {
  API_HUB_TEST_IDS,
  ApiHub,
  CONCEPT_INDEX_TEST_IDS,
  CONCEPT_PAGE_TEST_IDS,
  CONCEPT_SIX_QUESTIONS,
  ConceptIndex,
  ConceptPage,
  DOCS_RETURN_PATH_TEST_ID,
  DOCS_SECTIONS,
  DocsHome,
  ErrorsPage,
  FirstContractPage,
  GUIDE_INDEX_TEST_IDS,
  GUIDE_PAGE_TEST_IDS,
  GuideIndex,
  GuidePage,
  HowAdcosWorksPage,
  OperationPage,
  OPERATION_PAGE_TEST_IDS,
  PINNED_REASON_CODES,
  REPLAN_EVENTS_DISCLOSURE,
  REPLAN_EVENTS_NOT_EXPOSED,
  ReferencePage,
  StartHereHub,
  SdkPage,
  SDK_DISCLOSURE,
  TroubleshootingPage,
  WhatIsAdcosPage,
} from "@/features/docs";

/* ------------------------------------------------------------------ *
 * The hoisted module mocks (the harness pattern)
 * ------------------------------------------------------------------ */

/** The search params the mocked useSearchParams returns (per-test). */
let mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  usePathname: () => "/docs",
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

/* ------------------------------------------------------------------ *
 * Helpers
 * ------------------------------------------------------------------ */

/** The canonical presentation of a reason code, via errors.ts itself. */
function canonicalPresentation(code: string) {
  return describeError(
    new AdcosApiError({
      status: 400,
      reason: code,
      message: "",
      request: { method: "GET", path: "(test)" },
    }),
  );
}

/* ------------------------------------------------------------------ *
 * 1. The concept index — every registry concept, term + summary
 * ------------------------------------------------------------------ */

describe("the concept index (generated from the concept registry)", () => {
  it("renders ALL 14 concepts with their registry term and summary, each linking to its concept page", () => {
    renderBare(<ConceptIndex />);

    expect(CONCEPTS).toHaveLength(14);
    const rows = screen.getAllByTestId(CONCEPT_INDEX_TEST_IDS.row);
    expect(rows).toHaveLength(CONCEPTS.length);

    for (const concept of CONCEPTS) {
      const row = rows.find((candidate) => candidate.getAttribute("data-concept") === concept.id);
      expect(row, `row for concept "${concept.id}"`).toBeDefined();
      const scoped = within(row as HTMLElement);
      expect(scoped.getByText(concept.term), `term of "${concept.id}"`).toBeDefined();
      expect(scoped.getByText(concept.summary), `summary of "${concept.id}"`).toBeDefined();
      expect(scoped.getByRole("link")).toHaveAttribute("href", `/docs/concepts/${concept.id}`);
    }
  });
});

/* ------------------------------------------------------------------ *
 * 2. A real concept page — the six questions, registry content,
 *    prerequisite links, no return affordance without ?from=
 * ------------------------------------------------------------------ */

describe("the concept page (generated from the concept registry)", () => {
  it("renders the six question sections in order with the registry's real content and the prerequisite concept links", () => {
    const concept = getConcept("eligibility");
    expect(concept).toBeDefined();
    if (!concept) return;

    renderBare(<ConceptPage conceptId="eligibility" />);

    // the six questions, in the frozen §9 order
    CONCEPT_SIX_QUESTIONS.forEach((question) => {
      expect(screen.getByRole("heading", { name: question }), question).toBeDefined();
    });

    // the registry's real content: the summary (lede + What is it?),
    // the why/when/what-happens paragraphs
    expect(screen.getAllByText(concept.summary).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(concept.whyItMatters)).toBeDefined();
    expect(screen.getByText(concept.whenToUse)).toBeDefined();
    expect(screen.getByText(concept.whatHappens)).toBeDefined();

    // prerequisites render as links to the other concept pages
    expect(concept.prerequisites).toEqual(["connectivity-contract"]);
    const prerequisiteLink = screen.getByRole("link", { name: "Connectivity contract" });
    expect(prerequisiteLink).toHaveAttribute("href", "/docs/concepts/connectivity-contract");

    // the API look: every related operation links to its operation page
    for (const operationId of concept.relatedOperations) {
      expect(screen.getByRole("link", { name: operationId })).toHaveAttribute(
        "href",
        `/docs/api/${operationId}`,
      );
    }

    // related guides link to their guide pages (the same guide may also
    // appear in nextSteps — every occurrence must carry the correct href)
    const guideLinks = screen.getAllByRole("link", { name: getGuide("diagnose-fulfillment-failure")?.title });
    expect(guideLinks.length).toBeGreaterThan(0);
    for (const link of guideLinks) {
      expect(link).toHaveAttribute("href", "/docs/guides/diagnose-fulfillment-failure");
    }

    // no ?from= → no return affordance
    expect(screen.queryByTestId(DOCS_RETURN_PATH_TEST_ID)).toBeNull();
  });

  it("renders the honest unknown state for a bogus concept slug (no crash, no fabricated content)", () => {
    renderBare(<ConceptPage conceptId="nonexistent-concept" />);

    const unknown = screen.getByTestId(CONCEPT_PAGE_TEST_IDS.unknown);
    expect(unknown).toBeDefined();
    expect(screen.getByText("nonexistent-concept")).toBeDefined();
    expect(screen.getByText(/No concept matches this slug/i)).toBeDefined();
    // the six questions never render for an unknown slug
    for (const question of CONCEPT_SIX_QUESTIONS) {
      expect(screen.queryByRole("heading", { name: question })).toBeNull();
    }
    // the honest way back
    expect(screen.getByRole("link", { name: /Browse all concepts/i })).toHaveAttribute(
      "href",
      "/docs/concepts",
    );
  });

  it("renders the ?from= contextual return path linking back to the console route it came from", () => {
    mockSearchParams = new URLSearchParams("from=/connectivity");
    renderBare(<ConceptPage conceptId="eligibility" />);

    const affordance = screen.getByTestId(DOCS_RETURN_PATH_TEST_ID);
    expect(affordance).toBeDefined();
    expect(affordance.getAttribute("data-from")).toBe("/connectivity");
    const returnLink = within(affordance).getByRole("link", { name: /Return to \/connectivity/ });
    expect(returnLink).toHaveAttribute("href", "/connectivity");
  });
});

/* ------------------------------------------------------------------ *
 * 3. The guide index + a real guide page
 * ------------------------------------------------------------------ */

describe("the guides (generated from the guide registry)", () => {
  it("renders the guide index: all 7 playbooks with title, purpose and links", () => {
    renderBare(<GuideIndex />);

    expect(GUIDES).toHaveLength(7);
    const rows = screen.getAllByTestId(GUIDE_INDEX_TEST_IDS.row);
    expect(rows).toHaveLength(GUIDES.length);

    for (const guide of GUIDES) {
      const row = rows.find((candidate) => candidate.getAttribute("data-guide") === guide.id);
      expect(row, `row for guide "${guide.id}"`).toBeDefined();
      const scoped = within(row as HTMLElement);
      expect(scoped.getByText(guide.title)).toBeDefined();
      expect(scoped.getByText(guide.purpose)).toBeDefined();
      expect(scoped.getByRole("link")).toHaveAttribute("href", `/docs/guides/${guide.id}`);
    }
  });

  it("renders a real guide page: the steps with their links, the related concepts and operations", () => {
    const guide = getGuide("first-connectivity-application");
    expect(guide).toBeDefined();
    if (!guide) return;

    renderBare(<GuidePage guideId="first-connectivity-application" />);

    expect(screen.getByRole("heading", { level: 1, name: guide.title })).toBeDefined();
    expect(screen.getByText(guide.purpose)).toBeDefined();

    const steps = screen.getAllByTestId(GUIDE_PAGE_TEST_IDS.step);
    expect(steps).toHaveLength(guide.steps.length);
    steps.forEach((step, index) => {
      expect(within(step).getByText(`${index + 1}. ${guide.steps[index].title}`)).toBeDefined();
      expect(within(step).getByText(guide.steps[index].detail)).toBeDefined();
    });

    // step links resolve onto real docs surfaces
    expect(screen.getByRole("link", { name: "How ADCOS works" })).toHaveAttribute(
      "href",
      "/docs/start/how-it-works",
    );
    expect(screen.getByRole("link", { name: "application_self" })).toHaveAttribute(
      "href",
      "/docs/api/application_self",
    );

    // related concepts resolve their registry terms and link to the concept pages
    for (const conceptId of guide.relatedConcepts) {
      const term = getConcept(conceptId)?.term ?? conceptId;
      expect(screen.getByRole("link", { name: term })).toHaveAttribute(
        "href",
        `/docs/concepts/${conceptId}`,
      );
    }
  });
});

/* ------------------------------------------------------------------ *
 * 4. The API hub + an operation page
 * ------------------------------------------------------------------ */

describe("the API documentation (generated from coverage + education)", () => {
  it("renders the hub: all 25 operations grouped by lifecycle area, each linking to its operation page", () => {
    renderBare(<ApiHub />);

    expect(COVERAGE).toHaveLength(25);
    const rows = screen.getAllByTestId(API_HUB_TEST_IDS.row);
    expect(rows).toHaveLength(COVERAGE.length);

    for (const record of COVERAGE) {
      const row = rows.find((candidate) => candidate.getAttribute("data-operation") === record.operation);
      expect(row, `row for operation "${record.operation}"`).toBeDefined();
      const scoped = within(row as HTMLElement);
      expect(scoped.getByText(record.path), `path of "${record.operation}"`).toBeDefined();
      expect(scoped.getByRole("link")).toHaveAttribute("href", `/docs/api/${record.operation}`);
    }

    const groups = screen.getAllByTestId(API_HUB_TEST_IDS.group);
    const groupIds = groups.map((group) => group.getAttribute("data-group"));
    expect(groupIds).toEqual(
      expect.arrayContaining(["application", "offers", "contracts", "leases", "webhooks", "platform"]),
    );
    expect(groups).toHaveLength(6);
  });

  it("renders a real operation page: method/path VERBATIM from the coverage registry + the education fields", () => {
    const record = coverageByOperation("contract_get");
    const education = getOperationEducation("contract_get");
    expect(record).toBeDefined();
    expect(education).toBeDefined();
    if (!record || !education) return;

    renderBare(<OperationPage operationId="contract_get" />);

    // the REAL method and path, verbatim from the coverage registry
    expect(screen.getByText("GET")).toBeDefined();
    expect(screen.getByText(record.path)).toBeDefined();

    // the education fields
    expect(screen.getByText(education.purpose)).toBeDefined();
    expect(screen.getByText(education.prerequisites)).toBeDefined();
    expect(screen.getByText(education.lifecyclePosition)).toBeDefined();
    expect(screen.getByText(education.typicalSequence)).toBeDefined();
    for (const field of education.fieldExplanations) {
      expect(screen.getByText(field.field, { exact: true })).toBeDefined();
      expect(screen.getByText(field.explanation)).toBeDefined();
    }

    // related concepts and reason codes link to their docs surfaces
    for (const conceptId of education.relatedConcepts) {
      const term = getConcept(conceptId)?.term ?? conceptId;
      expect(screen.getByRole("link", { name: term })).toHaveAttribute(
        "href",
        `/docs/concepts/${conceptId}`,
      );
    }
    for (const code of education.relatedErrors) {
      expect(screen.getByRole("link", { name: code })).toHaveAttribute(
        "href",
        `/docs/errors#code-${code}`,
      );
    }

    // the next operation links onward; the Explorer owns execution
    expect(screen.getByRole("link", { name: "contract_usage" })).toHaveAttribute(
      "href",
      "/docs/api/contract_usage",
    );
    expect(screen.getByRole("link", { name: "API Explorer" })).toHaveAttribute(
      "href",
      "/developers/explorer",
    );
  });

  it("renders the honest unknown state for an operation id outside the coverage registry", () => {
    renderBare(<OperationPage operationId="offer_publish" />);

    expect(screen.getByTestId(OPERATION_PAGE_TEST_IDS.unknown)).toBeDefined();
    expect(screen.getByText("offer_publish")).toBeDefined();
    // no method/path is documented into existence for an unknown operation
    expect(screen.queryByText("GET")).toBeNull();
    expect(screen.queryByText("POST")).toBeNull();
  });
});

/* ------------------------------------------------------------------ *
 * 5. The errors page — the canonical reason codes, verbatim
 * ------------------------------------------------------------------ */

describe("the errors page (the canonical reason codes, verbatim)", () => {
  it("renders every pinned reason code VERBATIM, and every pinned code is canonical (validated against errors.ts itself)", () => {
    renderBare(<ErrorsPage />);

    expect(PINNED_REASON_CODES.length).toBe(32);
    for (const code of PINNED_REASON_CODES) {
      // the code text renders verbatim
      expect(screen.getByText(code), `code "${code}" renders verbatim`).toBeDefined();
      // and it is a REAL canonical code of errors.ts, not an invention
      const presentation = canonicalPresentation(code);
      expect(presentation.reasonCode).toBe(code);
      expect(presentation.title, `code "${code}" must be known to errors.ts`).not.toBe("Request failed");
    }
  });

  it("renders at least three real codes' exact text with the canonical presentation's guidance", () => {
    renderBare(<ErrorsPage />);

    for (const code of ["capability-denied", "route-unknown", "invalid-transition", "backend-unreachable"]) {
      expect(screen.getByText(code)).toBeDefined();
      const presentation = canonicalPresentation(code);
      expect(screen.getByText(presentation.title)).toBeDefined();
      expect(screen.getByText(new RegExp(presentation.nextAction))).toBeDefined();
    }
  });
});

/* ------------------------------------------------------------------ *
 * 6. The SDK page — honest
 * ------------------------------------------------------------------ */

describe("the SDK page (honest by construction)", () => {
  it("states the honest disclosure and claims no SDK exists", () => {
    renderBare(<SdkPage />);

    // the honest disclosure phrase, verbatim
    expect(screen.getByText(SDK_DISCLOSURE)).toBeDefined();
    expect(screen.getByText(/will list real SDKs when real SDKs exist/i)).toBeDefined();

    // no invented SDK install surface anywhere on the page
    expect(screen.queryByText(/npm install|pip install|yarn add|gem install|go get|@adcos\//i)).toBeNull();
    expect(screen.queryByText(/download the SDK|install the SDK|the SDK supports/i)).toBeNull();

    // the real surfaces it documents instead
    expect(screen.getByRole("link", { name: /API documentation pages/i })).toHaveAttribute(
      "href",
      "/docs/api",
    );
    expect(screen.getByRole("link", { name: /request inspector/i })).toHaveAttribute(
      "href",
      "/developers/requests",
    );
  });
});

/* ------------------------------------------------------------------ *
 * 7. The route-local search filters the concept index
 * ------------------------------------------------------------------ */

describe("the route-local documentation search", () => {
  it("filters the concept index by term: 'elig' keeps the eligibility row and filters the rest", () => {
    renderBare(<ConceptIndex />);

    const input = screen.getByPlaceholderText("Filter concepts");
    expect(screen.getAllByTestId(CONCEPT_INDEX_TEST_IDS.row)).toHaveLength(14);

    fireEvent.change(input, { target: { value: "elig" } });

    const rows = screen.getAllByTestId(CONCEPT_INDEX_TEST_IDS.row);
    expect(rows).toHaveLength(1);
    expect(rows[0].getAttribute("data-concept")).toBe("eligibility");
    expect(within(rows[0]).getByText("Eligibility")).toBeDefined();

    // the other concepts are filtered out
    expect(screen.queryByText("Connectivity contract")).toBeNull();
    expect(screen.queryByText("Webhook")).toBeNull();
    expect(screen.queryByText("Policy")).toBeNull();

    // the live count hint
    expect(screen.getByTestId("docs-search-hint")).toHaveTextContent("1/14");

    // clearing restores the full index
    fireEvent.change(input, { target: { value: "" } });
    expect(screen.getAllByTestId(CONCEPT_INDEX_TEST_IDS.row)).toHaveLength(14);
  });

  it("filters the docs home IA and the API hub the same way (no backend search service involved)", () => {
    renderBare(<DocsHome />);
    fireEvent.change(screen.getByPlaceholderText("Search the documentation"), {
      target: { value: "errors" },
    });
    expect(screen.getAllByTestId("docs-home-entry").length).toBeGreaterThan(0);
    expect(screen.queryByRole("link", { name: "Concepts" })).toBeNull();
    fireEvent.change(screen.getByPlaceholderText("Search the documentation"), {
      target: { value: "" },
    });

    renderBare(<ApiHub />);
    fireEvent.change(screen.getByPlaceholderText("Filter operations"), {
      target: { value: "lease" },
    });
    const rows = screen.getAllByTestId(API_HUB_TEST_IDS.row);
    expect(rows).toHaveLength(5);
    for (const row of rows) {
      const operation = row.getAttribute("data-operation") ?? "";
      expect(operation.startsWith("lease")).toBe(true);
    }
  });
});

/* ------------------------------------------------------------------ *
 * 8. The docs home IA + the curated Start here pages
 * ------------------------------------------------------------------ */

describe("the docs home and the curated Start here pages", () => {
  it("renders the full docs IA with every section route and the Quickstart href", () => {
    renderBare(<DocsHome />);

    const links = screen.getAllByRole("link");
    for (const section of DOCS_SECTIONS) {
      expect(
        links.some((link) => link.getAttribute("href") === section.href),
        `the IA links ${section.href}`,
      ).toBe(true);
    }
    // the Start here sub-pages
    for (const href of [
      "/docs/start/what-is-adcos",
      "/docs/start/how-it-works",
      "/docs/start/first-contract",
    ]) {
      expect(links.some((link) => link.getAttribute("href") === href), href).toBe(true);
    }
    // the Quickstart href (the first-run wave's route — linked, not created here)
    expect(links.some((link) => link.getAttribute("href") === "/quickstart")).toBe(true);
  });

  it("renders the Start here hub with the three pages and the Quickstart", () => {
    renderBare(<StartHereHub />);
    expect(screen.getByRole("heading", { level: 1, name: "Start here" })).toBeDefined();
    const links = screen.getAllByRole("link");
    for (const href of [
      "/docs/start/what-is-adcos",
      "/docs/start/how-it-works",
      "/docs/start/first-contract",
      "/quickstart",
    ]) {
      expect(links.some((link) => link.getAttribute("href") === href), href).toBe(true);
    }
  });

  it("renders What is ADCOS? with the design's anchor paragraph and the honest evidence disclosure", () => {
    renderBare(<WhatIsAdcosPage />);
    expect(
      screen.getByText(
        "ADCOS lets an application describe the connectivity it needs as a durable contract and continuously works to fulfill that contract across available connectivity capabilities.",
      ),
    ).toBeDefined();
    expect(screen.getByText("NOT-ACHIEVABLE-BY-THIS-DEPLOYMENT")).toBeDefined();
  });

  it("renders How ADCOS works: the six lifecycle stages, each linked to its concepts, with the §17 replan disclosure", () => {
    renderBare(<HowAdcosWorksPage />);
    const stageTitles = [
      "1. Describe requirement",
      "2. Eligibility",
      "3. Plan",
      "4. Fulfillment",
      "5. Assurance",
      "6. Continuous fulfillment",
    ];
    for (const title of stageTitles) {
      expect(screen.getByRole("heading", { name: title }), title).toBeDefined();
    }
    expect(screen.getByText(REPLAN_EVENTS_DISCLOSURE)).toBeDefined();
    // the stage concept links resolve onto the concept pages
    expect(screen.getByRole("link", { name: "Connectivity contract" })).toHaveAttribute(
      "href",
      "/docs/concepts/connectivity-contract",
    );
  });

  it("renders First connectivity contract: the walkthrough steps, honest about the demonstration context", () => {
    renderBare(<FirstContractPage />);
    expect(screen.getByRole("heading", { level: 1, name: "First connectivity contract" })).toBeDefined();
    expect(screen.getByText(/a demonstration, not production telemetry/i)).toBeDefined();
    expect(screen.getByRole("link", { name: "intent_create" })).toHaveAttribute(
      "href",
      "/docs/api/intent_create",
    );
    expect(screen.getByRole("link", { name: "offers_accept" })).toHaveAttribute(
      "href",
      "/docs/api/offers_accept",
    );
  });
});

/* ------------------------------------------------------------------ *
 * 9. The Troubleshooting hub + the Reference vocabularies
 * ------------------------------------------------------------------ */

describe("the troubleshooting hub and the reference vocabularies", () => {
  it("renders the four curated topics with the §17 replan-events disclosure stated verbatim", () => {
    renderBare(<TroubleshootingPage />);
    for (const topic of [
      "The console cannot connect",
      "A request returns 404 route-unknown",
      "Degraded coordination",
      "No visible replan events",
    ]) {
      expect(screen.getByRole("heading", { name: topic }), topic).toBeDefined();
    }
    expect(screen.getByText(REPLAN_EVENTS_NOT_EXPOSED)).toBeDefined();
    // reason-code chips link to the errors page anchors (a code may appear
    // in several topics — every chip carries the same anchor href)
    for (const code of ["backend-unreachable", "route-unknown"]) {
      const chips = screen.getAllByRole("link", { name: code });
      expect(chips.length).toBeGreaterThan(0);
      for (const chip of chips) {
        expect(chip).toHaveAttribute("href", `/docs/errors#code-${code}`);
      }
    }
  });

  it("renders the reference vocabularies from the real registries (states, evidence classes, capability grants)", () => {
    renderBare(<ReferencePage />);

    // lifecycle states render VERBATIM through the canonical Status renderer
    for (const state of ["INTENT", "OFFER_SELECTED", "CONTRACT_ACTIVE", "SETTLED"]) {
      expect(screen.getByText(state), `state "${state}"`).toBeDefined();
      expect(state in STATUS_TONES, `state "${state}" is real vocabulary`).toBe(true);
    }
    // DEGRADED renders both as vocabulary and as the honest marker it is
    expect(screen.getAllByText("DEGRADED").length).toBeGreaterThanOrEqual(2);
    for (const state of ["granted", "planned", "measured"]) {
      expect(screen.getByText(state)).toBeDefined();
      expect(state in STATUS_TONES).toBe(true);
    }

    // evidence classes render through the canonical badge, with the §17 disclosure
    expect(screen.getByText("SOFTWARE")).toBeDefined();
    expect(screen.getByText("sandbox-simulation")).toBeDefined();
    expect(screen.getByText("NOT-ACHIEVABLE-BY-THIS-DEPLOYMENT")).toBeDefined();

    // capability grants are derived from the coverage registry: every
    // required grant renders, and every operation is linked from its grant
    const grants = new Set(COVERAGE.map((record) => record.requiredCapability).filter(Boolean));
    for (const grant of grants) {
      expect(screen.getByText(grant, { exact: true }), `grant "${grant}"`).toBeDefined();
    }
    for (const record of COVERAGE) {
      if (!record.requiredCapability) continue;
      expect(
        screen.getByRole("link", { name: record.operation }),
        `${record.operation} links from its grant`,
      ).toHaveAttribute("href", `/docs/api/${record.operation}`);
    }
  });
});
