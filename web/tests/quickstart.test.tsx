/**
 * Quickstart tests — the guided nine-step journey (plan Task 5, the
 * frozen design §6): the step sequence with Back/Continue, the REAL
 * intent fields with the registry's explanations (step 2), the real
 * object slices (steps 3-7), the curl reproduction (step 8), the
 * honest run + retry behavior (step 6), the read failure recovery and
 * the next paths (step 9).
 *
 * Station harness discipline: fetch mocked at the GLOBAL boundary with
 * the REAL demonstration document fixture; the journey renders inside
 * the REAL SessionProvider (disconnected — the journey is honest about
 * the demo context); NO network. Registry-content expectations are
 * hard-coded on purpose (the W1 registry's own strings reaching the UI).
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QuickstartView, QUICKSTART_BACK_TEST_ID, QUICKSTART_CONTINUE_TEST_ID } from "@/features/playbooks/quickstart";
import {
  QUICKSTART_DOC_MISSING_TEST_ID,
  QUICKSTART_RUN_ERROR_TEST_ID,
} from "@/features/playbooks/quickstart-steps";
import {
  __resetDemoRunsForTests,
  getDemoRuns,
} from "@/features/fulfillment/demo-runs";
import { __resetRequestLogForTests } from "@/features/requests/request-log";
import {
  ERROR_REASON_TEST_ID,
  EVIDENCE_BADGE_TEST_IDS,
} from "@/components/ui";
import { NEXT_STEPS_TEST_ID } from "@/features/learning";
import { FIXTURE_DEMO_DOCUMENT } from "./fixtures";
import { renderBare, routeFetch } from "./harness";

vi.mock("next/navigation", () => ({
  usePathname: () => "/quickstart",
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
 * routeFetch returns a plain routing function; wrap in vi.fn so the
 * exact requests (method, path, body) are assertable.
 */
function trackedFetch(routes: Record<string, unknown>) {
  const routed = routeFetch(routes);
  return vi.fn((path: string, init?: RequestInit) => routed(path, init));
}

/** The journey's standard routes (the demonstration document read). */
function journeyRoutes(): Record<string, unknown> {
  return {
    "GET /demo/contract-fulfillment": FIXTURE_DEMO_DOCUMENT,
  };
}

type User = ReturnType<typeof userEvent.setup>;

/**
 * A stateful stepper: walks the journey to the target step from wherever
 * it currently stands (Continue forward, Back backward).
 */
function makeStepper(user: User) {
  let current = 1;
  return {
    async to(target: number): Promise<void> {
      while (current < target) {
        await user.click(screen.getByTestId(QUICKSTART_CONTINUE_TEST_ID));
        current += 1;
      }
      while (current > target) {
        await user.click(screen.getByTestId(QUICKSTART_BACK_TEST_ID));
        current -= 1;
      }
    },
  };
}

beforeEach(() => {
  __resetRequestLogForTests();
  __resetDemoRunsForTests();
});

describe("Quickstart — the nine-step journey", () => {
  it("renders step 1 and walks the whole sequence with Continue, Back returns", async () => {
    const user = userEvent.setup();
    const fetchMock = trackedFetch(journeyRoutes());
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<QuickstartView />);

    // step 1: the connect affordance + the honest demo context
    expect(
      screen.getByRole("heading", { level: 2, name: "Connect or enter the demo context" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Connect application" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/deterministic full-chain demonstration document/),
    ).toBeInTheDocument();
    expect(screen.getByText(/step 1 of 9/)).toBeInTheDocument();

    // the journey's single demonstration read — the GET form
    await waitFor(() => {
      expect(
        fetchMock.mock.calls.filter(
          ([path, init]) =>
            path === "/demo/contract-fulfillment" &&
            (init?.method ?? "GET").toUpperCase() === "GET",
        ),
      ).toHaveLength(1);
    });

    // the full sequence — every step title in order
    const titles = [
      "Connect or enter the demo context",
      "Describe a connectivity requirement",
      "Review the canonical contract representation",
      "Explain eligibility and provider/policy reasoning",
      "Show the generated fulfillment plan",
      "Run or observe fulfillment",
      "Inspect evidence and assurance",
      "Reproduce an operation through the API Explorer",
      "Where to go next",
    ];
    for (let step = 2; step <= 9; step += 1) {
      await user.click(screen.getByTestId(QUICKSTART_CONTINUE_TEST_ID));
      expect(
        screen.getByRole("heading", { level: 2, name: titles[step - 1] }),
      ).toBeInTheDocument();
      expect(screen.getByText(`step ${step} of 9`)).toBeInTheDocument();
    }

    // Back returns to the previous step
    await user.click(screen.getByTestId(QUICKSTART_BACK_TEST_ID));
    expect(
      screen.getByRole("heading", {
        level: 2,
        name: "Reproduce an operation through the API Explorer",
      }),
    ).toBeInTheDocument();

    // step 9 ends with the next paths (no dead end)
    await user.click(screen.getByTestId(QUICKSTART_CONTINUE_TEST_ID));
    expect(screen.getByTestId(NEXT_STEPS_TEST_ID)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Back to the workbench/ }),
    ).toHaveAttribute("href", "/");
  });

  it("step 2 renders the REAL intent fields with the registry's explanations", async () => {
    const user = userEvent.setup();
    const fetchMock = trackedFetch(journeyRoutes());
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<QuickstartView />);
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { level: 2, name: "Connect or enter the demo context" }),
      ).toBeInTheDocument();
    });
    const stepper = makeStepper(user);
    await stepper.to(2);

    // the W1 operation-education registry's own field explanations
    expect(screen.getByText("recorded_at")).toBeInTheDocument();
    expect(
      screen.getByText(/The RFC 3339 UTC instant the material was recorded/),
    ).toBeInTheDocument();
    expect(screen.getByText("hard_constraints")).toBeInTheDocument();
    expect(screen.getByText(/Immutable after creation/)).toBeInTheDocument();
    expect(screen.getByText("validity")).toBeInTheDocument();
    expect(
      screen.getByText(/not_before \/ not_after window/),
    ).toBeInTheDocument();
    expect(screen.getByText("termination")).toBeInTheDocument();
    expect(screen.getByText("requirements")).toBeInTheDocument();

    // the coverage registry's REAL intent example body renders verbatim
    expect(
      screen.getAllByText(/demo:intent-requirements:v1/).length,
    ).toBeGreaterThan(0);
    // (the constraint kinds appear in both the example body and the
    // registry's own field explanation — both are real content)
    expect(screen.getAllByText(/latency-bound/).length).toBeGreaterThan(
      0,
    );
    expect(screen.getAllByText(/throughput-floor/).length).toBeGreaterThan(
      0,
    );

    // the ConceptLink to the connectivity-contract concept
    expect(
      screen.getByRole("button", { name: "What is: Connectivity contract" }),
    ).toBeInTheDocument();
  });

  it("steps 3-7 render the real object slices from the demonstration document", async () => {
    const user = userEvent.setup();
    const fetchMock = trackedFetch(journeyRoutes());
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<QuickstartView />);
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { level: 2, name: "Connect or enter the demo context" }),
      ).toBeInTheDocument();
    });
    const stepper = makeStepper(user);

    // step 3 — the canonical contract (ObjectEducation + the registry's
    // own summary as the intro + the raw record)
    await stepper.to(3);
    expect(
      screen.getByText(
        /durable record of the connectivity an application asks ADCOS/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText(/78f563858281c8ca/).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("CONTRACT_ACTIVE")).toBeInTheDocument();
    expect(screen.getByText(/1 requirement reference/)).toBeInTheDocument();

    // step 4 — eligibility education + the REAL boundary entries
    await stepper.to(4);
    expect(
      screen.getByRole("button", { name: /What is: Eligibility\?/ }),
    ).toBeInTheDocument();
    expect(screen.getByText("/api/2.0/intents")).toBeInTheDocument();
    expect(screen.getByText("200")).toBeInTheDocument();
    // the §17 honesty position (it legitimately appears in both the
    // step prose and the registry education rendered on this step)
    expect(
      screen.getAllByText(/not exposed by this deployment/).length,
    ).toBeGreaterThan(0);

    // step 5 — the real plan
    await stepper.to(5);
    expect(
      screen.getAllByText(/da58d8b9c09953f1/).length,
    ).toBeGreaterThan(0);
    // (the member appears in both the field grid and the raw record)
    expect(
      screen.getAllByText(/constraint_fingerprint/).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText(/primary · reserve → activate → measure → release/)).toBeInTheDocument();

    // step 6 — the observed document + the run affordance
    await stepper.to(6);
    expect(
      screen.getByRole("button", { name: "Run the demonstration" }),
    ).toBeInTheDocument();
    expect(screen.getByText("RELEASED")).toBeInTheDocument();
    // the observed summary AND the honesty note each carry a badge —
    // every one of them SOFTWARE
    const badges = screen.getAllByTestId(EVIDENCE_BADGE_TEST_IDS.root);
    expect(badges.length).toBeGreaterThan(0);
    for (const badge of badges) {
      expect(badge).toHaveAttribute("data-kind", "software");
    }

    // step 7 — the real evidence records + the assurance obligations
    await stepper.to(7);
    expect(screen.getByText("observation")).toBeInTheDocument();
    expect(screen.getByText("attestation")).toBeInTheDocument();
    expect(
      screen.getAllByText(/evidence:observation:7e6e275466ed7559/).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByText(/evidence:attestation:8bf42deca4011e0c/).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByText(/demo:assurance-obligation:v1/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /What is: Assurance\?/ }),
    ).toBeInTheDocument();
  });

  it("step 8 shows the curl for the demo POST and links the Explorer", async () => {
    const user = userEvent.setup();
    const fetchMock = trackedFetch(journeyRoutes());
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<QuickstartView />);
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { level: 2, name: "Connect or enter the demo context" }),
      ).toBeInTheDocument();
    });
    const stepper = makeStepper(user);
    await stepper.to(8);

    // the masked-curl convention: the POST form with the observed instant
    expect(
      screen.getByText(/curl -X POST '\/demo\/contract-fulfillment'/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/--data-raw '\{"instant":"2026-09-14T00:00:00Z"\}'/),
    ).toBeInTheDocument();
    // the Explorer deep link (the sanctioned ?operation= convention)
    expect(
      screen.getByRole("link", {
        name: /Open it in the API Explorer/,
      }),
    ).toHaveAttribute(
      "href",
      "/developers/explorer?operation=demo_contract_fulfillment",
    );
  });

  it("step 9 composes the next paths from the registries", async () => {
    const user = userEvent.setup();
    const fetchMock = trackedFetch(journeyRoutes());
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<QuickstartView />);
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { level: 2, name: "Connect or enter the demo context" }),
      ).toBeInTheDocument();
    });
    const stepper = makeStepper(user);
    await stepper.to(9);

    expect(screen.getByTestId(NEXT_STEPS_TEST_ID)).toBeInTheDocument();
    const hrefs = screen
      .getAllByRole("link")
      .map((link) => link.getAttribute("href"));
    for (const nextHref of [
      "/docs/guides/first-connectivity-application",
      "/docs/api",
      "/connectivity",
      "/docs/concepts",
      "/docs/troubleshooting",
      "/",
      "/tour",
    ]) {
      expect(hrefs).toContain(nextHref);
    }
  });
});

describe("Quickstart — honesty under failure", () => {
  it("step 6: the run POSTs the observed instant; a failure renders ErrorState and the retry works, registering the run", async () => {
    const user = userEvent.setup();
    let postCalls = 0;
    const fetchMock = trackedFetch({
      ...journeyRoutes(),
      "POST /demo/contract-fulfillment": () => {
        postCalls += 1;
        if (postCalls === 1) {
          return {
            __status: 500,
            body: {
              error: {
                reason_code: "internal-error",
                message: "the demonstration runtime failed",
                backend: null,
              },
            },
          };
        }
        return FIXTURE_DEMO_DOCUMENT;
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<QuickstartView />);
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { level: 2, name: "Connect or enter the demo context" }),
      ).toBeInTheDocument();
    });
    const stepper = makeStepper(user);
    await stepper.to(6);

    // the run fails honestly — the verbatim reason, no summary
    await user.click(screen.getByRole("button", { name: "Run the demonstration" }));
    await waitFor(() => {
      expect(
        screen.getByTestId(QUICKSTART_RUN_ERROR_TEST_ID),
      ).toBeInTheDocument();
    });
    expect(screen.getByTestId(ERROR_REASON_TEST_ID)).toHaveTextContent(
      "internal-error",
    );
    expect(screen.queryByTestId("quickstart-run-summary")).toBeNull();

    // the retry works — the same POST, now succeeding
    await user.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => {
      expect(screen.getByTestId("quickstart-run-summary")).toBeInTheDocument();
    });
    expect(screen.getByTestId("quickstart-run-summary")).toHaveTextContent(
      "2026-09-14T00:00:00Z",
    );

    // the exact POST the run made: the observed instant
    const postBodies = fetchMock.mock.calls
      .filter(
        ([path, init]) =>
          path === "/demo/contract-fulfillment" &&
          init?.method === "POST",
      )
      .map(([, init]) => JSON.parse(String(init?.body)));
    expect(postBodies).toEqual([
      { instant: "2026-09-14T00:00:00Z" },
      { instant: "2026-09-14T00:00:00Z" },
    ]);

    // the successful run registered in the shared demo-run registry
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

  it("a failed journey read shows the ErrorState with retry and recovers on the document-backed step", async () => {
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

    renderBare(<QuickstartView />);

    // step 1 renders regardless (it needs no document)
    expect(
      screen.getByRole("heading", { level: 2, name: "Connect or enter the demo context" }),
    ).toBeInTheDocument();

    // step 3 is document-backed: honest ErrorState + retry, no content
    const stepper = makeStepper(user);
    await stepper.to(3);
    await waitFor(() => {
      expect(
        screen.getByTestId(QUICKSTART_DOC_MISSING_TEST_ID),
      ).toBeInTheDocument();
    });
    expect(screen.getByTestId(ERROR_REASON_TEST_ID)).toHaveTextContent(
      "backend-unreachable",
    );

    // retry re-runs the read and the real content renders
    await user.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => {
      expect(
        screen.getAllByText(/78f563858281c8ca/).length,
      ).toBeGreaterThan(0);
    });
    expect(
      screen.queryByTestId(QUICKSTART_DOC_MISSING_TEST_ID),
    ).toBeNull();
  });
});
