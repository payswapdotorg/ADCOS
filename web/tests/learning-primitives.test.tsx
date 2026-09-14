/**
 * Learning primitives tests — the Task-2 presentation layer over the
 * REAL Task-1 education registry (the station harness discipline: the
 * hoisted next/navigation + next/link mocks, the REAL SessionProvider,
 * NO network — these primitives are pure presentation, fetch is never
 * called anywhere in this suite).
 *
 * Covers the work order's demands:
 * - ConceptLink renders the concept's term and opens the documentation
 *   drawer carrying the concept's REAL registry content (asserting the
 *   eligibility concept's own whyItMatters text reaches the UI);
 * - the inline mode's disclosure toggling: aria-expanded false → click →
 *   true → content visible, keyboard Enter/Space on the trigger, Escape
 *   in drawer mode closing and RETURNING FOCUS to the trigger
 *   (document.activeElement), and the drawer's tab-cycle focus trap;
 * - the honest UNKNOWN state for both primitives: never throws, shows
 *   the raw id, no fabricated content;
 * - NextStep: every LearningLink kind renders its kind-aware label and
 *   href (route → the route, docs → the docs convention);
 * - ObjectEducation: the intro renders BEFORE the structured children,
 *   and the ConceptLink slot renders when conceptId is provided;
 * - prerequisites render as ConceptLink chips inside the explainer with
 *   the REAL registry data (execution-plan's two prerequisites).
 */

import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderBare } from "./harness";
import {
  CONCEPT_EDUCATION_TEST_ID,
  CONCEPT_EXPLAINER_TRIGGER_TEST_ID,
  ConceptExplainer,
  ConceptLink,
  NEXT_STEPS_TEST_ID,
  NextStep,
  NextSteps,
  OBJECT_EDUCATION_TEST_ID,
  ObjectEducation,
  UNKNOWN_CONCEPT_TEST_ID,
  docsHref,
} from "@/features/learning";
import type { LearningLink } from "@/lib/education";

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
 * REAL registry content expectations (hard-coded on purpose: proving
 * the registry's own strings reach the UI, not a circular lookup)
 * ------------------------------------------------------------------ */

const ELIGIBILITY_SUMMARY =
  /The reasoning for why a contract's flow state is what it is/;
const ELIGIBILITY_WHY =
  /Eligibility explains the system's behavior instead of leaving you to guess/;
const OFFER_SUMMARY = /An opaque typed reference to a provider's proposed terms/;

/* ------------------------------------------------------------------ *
 * ConceptLink — the inline "What is this?" affordance
 * ------------------------------------------------------------------ */

describe("learning primitives", () => {
  it("ConceptLink renders the concept's term and opens the drawer carrying the REAL registry content", async () => {
    const user = userEvent.setup();
    renderBare(<ConceptLink id="eligibility" />);

    const affordance = screen.getByRole("button", {
      name: "What is: Eligibility",
    });
    expect(affordance).toHaveTextContent("Eligibility");
    expect(affordance).toHaveAttribute("aria-haspopup", "dialog");
    expect(affordance).toHaveAttribute("aria-expanded", "false");

    await user.click(affordance);
    const dialog = await screen.findByRole("dialog", {
      name: "Concept: Eligibility",
    });

    // the registry's own summary rides along as the drawer description
    expect(within(dialog).getByText(ELIGIBILITY_SUMMARY)).toBeInTheDocument();

    // progressively-disclosed registry sections: expand "Why it matters"
    const why = within(dialog).getByRole("button", {
      name: "Why it matters",
    });
    await user.click(why);
    expect(within(dialog).getByText(ELIGIBILITY_WHY)).toBeVisible();

    // focus moved INTO the drawer on open
    expect(dialog.contains(document.activeElement)).toBe(true);
  });

  it("ConceptLink renders custom children while keeping the term as the accessible name", () => {
    renderBare(
      <ConceptLink id="eligibility">the eligibility reasoning</ConceptLink>,
    );
    const affordance = screen.getByRole("button", {
      name: "What is: Eligibility",
    });
    expect(affordance).toHaveTextContent("the eligibility reasoning");
  });

  /* ---------------------------------------------------------------- *
   * ConceptExplainer — the three modes and their focus contracts
   * ---------------------------------------------------------------- */

  it("inline mode: the disclosure toggles by mouse and by Enter/Space, managing aria-expanded and content visibility", async () => {
    const user = userEvent.setup();
    renderBare(<ConceptExplainer id="eligibility" mode="inline" />);

    const toggle = screen.getByTestId(CONCEPT_EXPLAINER_TRIGGER_TEST_ID);
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(toggle).toHaveAttribute("aria-controls");

    const summary = screen.getByText(ELIGIBILITY_SUMMARY);
    expect(summary).not.toBeVisible();

    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(summary).toBeVisible();

    // keyboard: Space collapses (buttons activate on Space)
    toggle.focus();
    await user.keyboard(" ");
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(summary).not.toBeVisible();

    // keyboard: Enter expands again
    await user.keyboard("{Enter}");
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(summary).toBeVisible();

    // Escape collapses the inline expansion, focus stays on the trigger
    await user.keyboard("{Escape}");
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(document.activeElement).toBe(toggle);
  });

  it("drawer mode: Escape closes the drawer and focus returns to the trigger; the tab cycle stays trapped inside", async () => {
    const user = userEvent.setup();
    renderBare(<ConceptExplainer id="eligibility" mode="drawer" />);

    const trigger = screen.getByTestId(CONCEPT_EXPLAINER_TRIGGER_TEST_ID);
    await user.click(trigger);
    const dialog = await screen.findByRole("dialog", {
      name: "Concept: Eligibility",
    });
    expect(trigger).toHaveAttribute("aria-expanded", "true");

    // the focus trap holds the tab cycle inside the dialog
    await user.tab();
    expect(dialog.contains(document.activeElement)).toBe(true);
    await user.tab();
    expect(dialog.contains(document.activeElement)).toBe(true);

    await user.keyboard("{Escape}");
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
    expect(document.activeElement).toBe(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });

  it("block mode: renders the term heading, the summary, and the progressively-disclosed registry sections", async () => {
    const user = userEvent.setup();
    renderBare(<ConceptExplainer id="execution-plan" />);

    const education = screen.getByTestId(CONCEPT_EDUCATION_TEST_ID);
    expect(
      within(education).getByRole("heading", { name: "Execution plan" }),
    ).toBeInTheDocument();
    expect(
      within(education).getByText(
        /The composition of provider capabilities that fulfills an accepted contract/,
      ),
    ).toBeInTheDocument();

    const why = within(education).getByRole("button", {
      name: "Why it matters",
    });
    expect(why).toHaveAttribute("aria-expanded", "false");
    await user.click(why);
    expect(why).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByText(
        /The plan is the step between what you asked for and what actually happens/,
      ),
    ).toBeVisible();
  });

  it("the explainer renders prerequisites as ConceptLink chips from the REAL registry (execution-plan)", async () => {
    const user = userEvent.setup();
    renderBare(<ConceptExplainer id="execution-plan" />);

    const education = screen.getByTestId(CONCEPT_EDUCATION_TEST_ID);
    expect(within(education).getByText("Prerequisites")).toBeInTheDocument();
    const contractChip = within(education).getByRole("button", {
      name: "What is: Connectivity contract",
    });
    const offerChip = within(education).getByRole("button", {
      name: "What is: Offer",
    });
    expect(contractChip).toBeInTheDocument();
    expect(offerChip).toBeInTheDocument();

    // a chip opens the prerequisite's own drawer with ITS real content
    await user.click(offerChip);
    const drawer = await screen.findByRole("dialog", {
      name: "Concept: Offer",
    });
    expect(within(drawer).getByText(OFFER_SUMMARY)).toBeInTheDocument();
  });

  /* ---------------------------------------------------------------- *
   * The honest unknown state (design §17 — never fabricated, never a crash)
   * ---------------------------------------------------------------- */

  it("ConceptLink with an unknown id renders the honest unknown state (disabled, raw id, no fabricated content)", () => {
    renderBare(<ConceptLink id="not-a-real-concept" />);

    const unknown = screen.getByTestId(UNKNOWN_CONCEPT_TEST_ID);
    expect(unknown).toBeDisabled();
    expect(unknown).toHaveAccessibleName(
      "Unknown concept: not-a-real-concept",
    );
    expect(unknown).toHaveTextContent("not-a-real-concept");
    expect(unknown).toHaveAttribute(
      "title",
      expect.stringContaining("Unknown concept"),
    );
    // nothing from any real concept leaks into the unknown state
    expect(screen.queryByText(ELIGIBILITY_WHY)).not.toBeInTheDocument();
    expect(screen.queryByText(ELIGIBILITY_SUMMARY)).not.toBeInTheDocument();
  });

  it("ConceptExplainer with an unknown id renders the honest unknown disclosure in every mode", () => {
    const { unmount } = renderBare(<ConceptExplainer id="bogus-concept" />);
    const block = screen.getByTestId(UNKNOWN_CONCEPT_TEST_ID);
    expect(block).toHaveTextContent("Unknown concept");
    expect(block).toHaveTextContent("bogus-concept");
    expect(screen.queryByText(ELIGIBILITY_WHY)).not.toBeInTheDocument();
    unmount();

    const inline = renderBare(
      <ConceptExplainer id="bogus-concept" mode="inline" />,
    );
    expect(screen.getByTestId(UNKNOWN_CONCEPT_TEST_ID)).toHaveTextContent(
      "bogus-concept",
    );
    inline.unmount();

    const drawer = renderBare(
      <ConceptExplainer id="bogus-concept" mode="drawer" />,
    );
    expect(screen.getByTestId(UNKNOWN_CONCEPT_TEST_ID)).toHaveTextContent(
      "bogus-concept",
    );
    drawer.unmount();
  });

  /* ---------------------------------------------------------------- *
   * NextStep / NextSteps — the kind-aware "where to go next" affordances
   * ---------------------------------------------------------------- */

  it("NextStep renders every LearningLink kind with its kind-aware label and href", async () => {
    const user = userEvent.setup();
    // REAL registry links (offer's and connectivity-contract's and
    // policy's own nextSteps entries — transcribed verbatim)
    const links: LearningLink[] = [
      {
        kind: "concept",
        id: "execution-plan",
        label: "Execution plan — what the offer becomes",
      },
      {
        kind: "operation",
        id: "contract_activate",
        label: "Activate the contract",
      },
      {
        kind: "guide",
        id: "understand-provider-selection",
        label: "Understand why a provider was selected",
      },
      {
        kind: "route",
        id: "/connectivity",
        label: "Open the contracts workspace",
      },
      {
        kind: "docs",
        id: "errors",
        label: "The canonical reason codes",
      },
    ];
    renderBare(
      <ul>
        {links.map((link) => (
          <li key={`${link.kind}:${link.id}`}>
            <NextStep link={link} />
          </li>
        ))}
      </ul>,
    );

    // operation → the API Explorer's own deep link
    expect(
      screen.getByRole("link", { name: "API: Activate the contract" }),
    ).toHaveAttribute("href", "/developers/explorer?operation=contract_activate");

    // guide → the docs feature's guide page
    expect(
      screen.getByRole("link", {
        name: "Guide: Understand why a provider was selected",
      }),
    ).toHaveAttribute("href", "/docs/guides/understand-provider-selection");

    // route → the link's own id as the href, no label prefix
    expect(
      screen.getByRole("link", { name: "Open the contracts workspace" }),
    ).toHaveAttribute("href", "/connectivity");

    // docs → the docs-IA slug resolves under /docs/
    expect(
      screen.getByRole("link", { name: "Docs: The canonical reason codes" }),
    ).toHaveAttribute("href", "/docs/errors");

    // concept → a "Learn:" chip that opens the concept's own drawer
    const learn = screen.getByRole("button", {
      name: "Learn: Execution plan — what the offer becomes",
    });
    await user.click(learn);
    expect(
      await screen.findByRole("dialog", { name: "Concept: Execution plan" }),
    ).toBeInTheDocument();
  });

  it("docs links keep the /docs/concepts/<id> convention for concept ids (docsHref)", () => {
    expect(docsHref("eligibility")).toBe("/docs/concepts/eligibility");
    expect(docsHref("errors")).toBe("/docs/errors");

    renderBare(
      <NextStep
        link={{ kind: "docs", id: "eligibility", label: "Read the concept page" }}
      />,
    );
    expect(
      screen.getByRole("link", { name: "Docs: Read the concept page" }),
    ).toHaveAttribute("href", "/docs/concepts/eligibility");
  });

  it("NextSteps renders the links as one labelled list and renders nothing without links", () => {
    const links: LearningLink[] = [
      {
        kind: "concept",
        id: "execution-plan",
        label: "Execution plan — what the offer becomes",
      },
      {
        kind: "operation",
        id: "contract_activate",
        label: "Activate the contract",
      },
      {
        kind: "guide",
        id: "understand-provider-selection",
        label: "Understand why a provider was selected",
      },
    ];
    renderBare(<NextSteps links={links} />);

    const list = screen.getByTestId(NEXT_STEPS_TEST_ID);
    expect(list).toHaveAccessibleName("Where to go next");
    expect(within(list).getAllByRole("button")).toHaveLength(1);
    expect(within(list).getAllByRole("link")).toHaveLength(2);

    const { container } = renderBare(<NextSteps links={[]} />);
    expect(
      container.querySelector(`[data-testid="${NEXT_STEPS_TEST_ID}"]`),
    ).toBeNull();
  });

  /* ---------------------------------------------------------------- *
   * ObjectEducation — the object-level explanatory header (design §14)
   * ---------------------------------------------------------------- */

  it("ObjectEducation renders the intro and education rows BEFORE the raw children, with the ConceptLink slot", () => {
    renderBare(
      <ObjectEducation
        title="Connectivity contract"
        intro="A connectivity contract describes the connectivity your application asks ADCOS to continuously fulfill."
        lifecyclePosition="CONTRACT_ACTIVE — an active contract with fulfillment observed"
        whatUserRequested="Private connectivity to the demonstration provider"
        whyItMatters="The contract is the anchor every other object references."
        sections={[
          {
            heading: "Evidence and assurance",
            body: "SOFTWARE evidence class; assurance obligations referenced verbatim.",
          },
        ]}
        conceptId="connectivity-contract"
      >
        <div data-testid="raw-fields">the raw structured representation</div>
      </ObjectEducation>,
    );

    expect(
      screen.getByRole("heading", { level: 2, name: "Connectivity contract" }),
    ).toBeInTheDocument();

    // the ConceptLink slot: the inline "What is this?" affordance
    expect(
      screen.getByRole("button", { name: "What is: Connectivity contract" }),
    ).toBeInTheDocument();

    const intro = screen.getByText(
      "A connectivity contract describes the connectivity your application asks ADCOS to continuously fulfill.",
    );
    const fields = screen.getByTestId("raw-fields");
    // the education renders BEFORE the raw structured representation
    expect(
      intro.compareDocumentPosition(fields) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBe(Node.DOCUMENT_POSITION_FOLLOWING);

    expect(
      screen.getByText("CONTRACT_ACTIVE — an active contract with fulfillment observed"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Private connectivity to the demonstration provider"),
    ).toBeInTheDocument();
    expect(screen.getByText("Evidence and assurance")).toBeInTheDocument();
    expect(
      screen.getByText(
        "SOFTWARE evidence class; assurance obligations referenced verbatim.",
      ),
    ).toBeInTheDocument();
  });

  it("ObjectEducation without conceptId renders no concept affordance and honors the heading level", () => {
    renderBare(
      <ObjectEducation title="Lease" intro="A lease grants a bounded access window." headingLevel="h3">
        <div>raw</div>
      </ObjectEducation>,
    );
    expect(screen.getByRole("heading", { level: 3, name: "Lease" })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /^What is:/ }),
    ).not.toBeInTheDocument();
  });

  it("the object-education test id is stable for composing surfaces", () => {
    renderBare(
      <ObjectEducation title="Contract" intro="An intro.">
        <div>raw</div>
      </ObjectEducation>,
    );
    expect(screen.getByTestId(OBJECT_EDUCATION_TEST_ID)).toBeInTheDocument();
  });
});

/* ------------------------------------------------------------------ *
 * Regression: route-kind links de-template dynamic hrefs
 *
 * The app router forbids dynamic hrefs (`/connectivity/contracts/[id]`)
 * in <Link> — a template route link must resolve to its static workspace
 * ancestor, never pass the template through (the eligibility drawer
 * crashed on exactly this before the repair).
 * ------------------------------------------------------------------ */
describe("route template de-templating (the app-router dynamic-href rule)", () => {
  it("a route template resolves to its static workspace ancestor, never the raw template", async () => {
    const { NextStep } = await import("@/features/learning/next-step");
    render(<NextStep link={{ kind: "route", id: "/connectivity/contracts/[id]", label: "A contract detail page" }} />);
    const link = screen.getByRole("link", { name: /A contract detail page/i });
    expect(link).toHaveAttribute("href", "/connectivity");
    expect(link.getAttribute("href")).not.toContain("[");
  });

  it("a static route passes through unchanged", async () => {
    const { NextStep } = await import("@/features/learning/next-step");
    render(<NextStep link={{ kind: "route", id: "/developers/explorer", label: "API Explorer" }} />);
    expect(screen.getByRole("link", { name: /API Explorer/i })).toHaveAttribute("href", "/developers/explorer");
  });
});
