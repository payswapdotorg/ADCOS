/**
 * Contract detail tests — REAL captured shapes only (tests/fixtures.ts),
 * fetch mocked at the global boundary through the shared harness.
 *
 * Covers the work order's detail demands:
 * - the lifecycle chain sections render from the real demo contract,
 *   lifecycle, usage and assurance reads (usage/assurance notes and the
 *   evidence class VERBATIM; hard constraints with exact params);
 * - the state-advancing card appears for INTENT (accept offers) with the
 *   canonical POST preview;
 * - the termination drawer offers EXACTLY the contract's own termination
 *   conditions, previews POST /api/2.0/contracts/{id}/termination live,
 *   and surfaces the backend's VERBATIM reason on rejection;
 * - the leases block filters by contract_id and the grant drawer explains
 *   the validity-window rule with the contract's own bounds;
 * - a failed contract read surfaces resource-unknown verbatim.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { ContractDetailView } from "@/features/contracts";
import { __resetRequestLogForTests } from "@/features/requests/request-log";
import { ERROR_REASON_TEST_ID } from "@/components/ui";
import type { Lease } from "@/lib/api/types";
import {
  FIXTURE_ASSURANCE,
  FIXTURE_CONTRACT_INTENT,
  FIXTURE_DEMO_CONTRACT,
  FIXTURE_DEMO_LIFECYCLE,
  FIXTURE_ERROR_NOT_FOUND,
  FIXTURE_ERROR_TERMINAL,
  FIXTURE_LEASE_ACTIVE,
  FIXTURE_LEASE_REVOKED,
  FIXTURE_LIFECYCLE_INTENT,
  FIXTURE_USAGE,
} from "./fixtures";
import {
  APPLICATION_ROUTE,
  envelope,
  renderWithSession,
  routeFetch,
} from "./harness";

vi.mock("next/navigation", () => ({
  usePathname: () => "/connectivity",
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
 * A REAL captured lease ON THE DEMONSTRATION CONTRACT — granted live
 * against the local sandbox runtime (POST /api/2.0/contracts/
 * sha256:78f5…/leases with a window inside the demo contract validity,
 * 2026-09-14) so the client-side contract_id filter can be exercised with
 * a real backend shape. The other captured leases belong to the capture
 * contract (sha256:8c92…) and must be filtered OUT of the demo
 * contract's table.
 */
const DEMO_CONTRACT_LEASE: Lease = {
  contract_id: FIXTURE_DEMO_CONTRACT.contract_id,
  environment: "sandbox",
  granted_at: "2026-09-14T01:00:00Z",
  id: "sha256:aa0c5f3b73f29238d1a35114518e9242eec0de25a6302ed41b262a4e7531fe35",
  kind: "contract_lease",
  lease_id: "sha256:aa0c5f3b73f29238d1a35114518e9242eec0de25a6302ed41b262a4e7531fe35",
  not_after: "2026-09-14T02:00:00Z",
  not_before: "2026-09-14T01:00:00Z",
  state: "active",
};

const DEMO_ID = FIXTURE_DEMO_CONTRACT.id;

/** The full demo-contract read surface (five authenticated reads). */
function demoContractRoutes(
  extra: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    ...APPLICATION_ROUTE,
    [`GET /api/2.0/contracts/${DEMO_ID}`]: envelope(FIXTURE_DEMO_CONTRACT),
    [`GET /api/2.0/intents/${DEMO_ID}/lifecycle`]: envelope(FIXTURE_DEMO_LIFECYCLE),
    [`GET /api/2.0/contracts/${DEMO_ID}/usage`]: envelope(FIXTURE_USAGE),
    [`GET /api/2.0/contracts/${DEMO_ID}/assurance`]: envelope(FIXTURE_ASSURANCE),
    "GET /api/2.0/leases": envelope({
      items: [DEMO_CONTRACT_LEASE, FIXTURE_LEASE_ACTIVE, FIXTURE_LEASE_REVOKED],
      next_cursor: "",
      has_more: false,
    }),
    ...extra,
  };
}

beforeEach(() => {
  __resetRequestLogForTests();
});

describe("Contract detail — the lifecycle chain", () => {
  it("renders all six chain sections from the real reads with notes, evidence class and constraints verbatim", async () => {
    const fetchMock = routeFetch(demoContractRoutes());
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(
      <ContractDetailView contractId={DEMO_ID} />,
      fetchMock,
    );

    await waitFor(() => {
      expect(screen.getByText("1 · Requirements")).toBeInTheDocument();
    });
    for (const heading of [
      "2 · Eligibility",
      "3 · Plan",
      "4 · Execution",
      "5 · Assurance",
      "6 · Continuous fulfillment",
    ]) {
      expect(screen.getByText(heading)).toBeInTheDocument();
    }

    // the header carries the contract id (title + meta) and state
    expect(screen.getAllByText(DEMO_ID).length).toBeGreaterThanOrEqual(2);

    // the usage note and the assurance note, VERBATIM (the blockquote
    // carries the backend text exactly — the label is separate)
    const notes = screen.getAllByTestId("verbatim-note");
    const noteText = (note: HTMLElement): string =>
      note.querySelector("blockquote")?.textContent ?? "";
    const usageNote = notes.find(
      (node) => noteText(node) === FIXTURE_USAGE.note,
    );
    const assuranceNote = notes.find(
      (node) => noteText(node) === FIXTURE_ASSURANCE.note,
    );
    expect(usageNote).toBeDefined();
    expect(usageNote).toHaveTextContent(FIXTURE_USAGE.note);
    expect(assuranceNote).toBeDefined();
    expect(assuranceNote).toHaveTextContent(FIXTURE_ASSURANCE.note);

    // the lifecycle note is rendered too (FlowStatePanel), verbatim
    const lifecycleNote = notes.find(
      (node) => noteText(node) === FIXTURE_DEMO_LIFECYCLE.note,
    );
    expect(lifecycleNote).toBeDefined();

    // the evidence class, VERBATIM (FlowStatePanel + Execution section)
    expect(screen.getAllByText("sandbox-simulation").length).toBeGreaterThanOrEqual(2);

    // hard constraints render with their exact params
    expect(screen.getByText("latency-bound")).toBeInTheDocument();
    expect(screen.getByText("throughput-floor")).toBeInTheDocument();
    expect(screen.getByText("ms: 100")).toBeInTheDocument();
    expect(screen.getByText("bps: 1000")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Hard constraints are immutable after creation and pass through the API unchanged.",
      ),
    ).toBeInTheDocument();

    // requirements + usage pricing terms as opaque typed references
    expect(screen.getByText("demo:intent-requirements:v1")).toBeInTheDocument();
    expect(screen.getByText("capture:usage-pricing:v1")).toBeInTheDocument();

    // the execution position and the statements vocabulary, verbatim
    expect(screen.getAllByText("not-claimed").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("physical_connectivity_not_claimed")).toBeInTheDocument();
    expect(
      screen.getByText("See the fulfillment demonstration for the full execution chain"),
    ).toBeInTheDocument();

    // the activity timeline derives from backend facts only
    expect(screen.getByText("Entered CONTRACT_ACTIVE")).toBeInTheDocument();
    expect(screen.getByText("4 commands recorded")).toBeInTheDocument();
  });

  it("shows the accept-offers next step for an INTENT contract with the canonical POST preview", async () => {
    const intentId = FIXTURE_CONTRACT_INTENT.id;
    const fetchMock = routeFetch({
      ...APPLICATION_ROUTE,
      [`GET /api/2.0/contracts/${intentId}`]: envelope(FIXTURE_CONTRACT_INTENT),
      [`GET /api/2.0/intents/${intentId}/lifecycle`]: envelope(FIXTURE_LIFECYCLE_INTENT),
      [`GET /api/2.0/contracts/${intentId}/usage`]: envelope(FIXTURE_USAGE),
      [`GET /api/2.0/contracts/${intentId}/assurance`]: envelope(FIXTURE_ASSURANCE),
      "GET /api/2.0/leases": envelope({
        items: [],
        next_cursor: "",
        has_more: false,
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(
      <ContractDetailView contractId={intentId} />,
      fetchMock,
    );

    await waitFor(() => {
      expect(screen.getByText("Next step · Accept offers")).toBeInTheDocument();
    });
    expect(
      screen.getByText(
        "Accepting opaque typed offer references moves the contract INTENT → OFFER_SELECTED.",
      ),
    ).toBeInTheDocument();

    // the canonical defaults and the exact request preview
    expect(screen.getByLabelText("offer 1 value")).toHaveValue(
      "demo:offer:ran-reference:v1",
    );
    expect(
      screen.getByLabelText("offer 1 issuer"),
    ).toHaveValue("provider:ran-reference");
    expect(screen.getByText(`/api/2.0/intents/${intentId}/offers`)).toBeInTheDocument();

    // the activation card is for the NEXT state — not rendered here
    expect(screen.queryByText("Next step · Activate contract")).toBeNull();

    // INTENT is not terminal: the terminate action is available
    expect(
      screen.getByRole("button", { name: "Terminate contract" }),
    ).toBeInTheDocument();
  });
});

describe("Contract detail — termination", () => {
  it("offers exactly the contract's own conditions, previews the request live, and surfaces the verbatim reason on rejection", async () => {
    const fetchMock = routeFetch(
      demoContractRoutes({
        [`POST /api/2.0/contracts/${DEMO_ID}/termination`]: {
          __status: 422,
          body: FIXTURE_ERROR_TERMINAL,
        },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(
      <ContractDetailView contractId={DEMO_ID} />,
      fetchMock,
    );

    await waitFor(() => {
      expect(screen.getByText("1 · Requirements")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Terminate contract" }));

    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByText(/terminal, with a condition from the contract/),
    ).toBeInTheDocument();

    // the condition select offers EXACTLY the contract's own vocabulary
    const conditionSelect = within(dialog).getByLabelText(
      /condition \(from the contract's own termination vocabulary\)/,
    );
    const options = within(conditionSelect).getAllByRole("option");
    expect(options).toHaveLength(FIXTURE_DEMO_CONTRACT.termination.conditions.length);
    expect(options.map((option) => option.textContent)).toEqual(
      FIXTURE_DEMO_CONTRACT.termination.conditions,
    );
    expect(
      options.map((option) => (option as HTMLOptionElement).value),
    ).toEqual(FIXTURE_DEMO_CONTRACT.termination.conditions);

    // the preview shows the exact route; the chosen condition rides the
    // body and the preview updates live
    expect(dialog).toHaveTextContent(`/api/2.0/contracts/${DEMO_ID}/termination`);
    fireEvent.change(conditionSelect, { target: { value: "validity-expired" } });
    expect(conditionSelect).toHaveValue("validity-expired");
    expect(dialog).toHaveTextContent('"condition":"validity-expired"');

    // submitting against the 422 fixture surfaces the VERBATIM reason
    fireEvent.change(within(dialog).getByLabelText("reason"), {
      target: { value: "operator-requested-termination" },
    });
    fireEvent.click(
      within(dialog).getByRole("button", { name: "Terminate contract" }),
    );

    await waitFor(() => {
      expect(screen.getAllByTestId(ERROR_REASON_TEST_ID).length).toBeGreaterThanOrEqual(1);
    });
    const reasonChip = within(dialog).getByTestId(ERROR_REASON_TEST_ID);
    expect(reasonChip).toHaveTextContent("invalid-input");
    expect(within(dialog).getByText(/contract is terminal in TERMINATED/)).toBeInTheDocument();
  });
});

describe("Contract detail — leases", () => {
  it("lists only this contract's leases and the grant drawer explains the validity-window rule with the contract's bounds", async () => {
    const fetchMock = routeFetch(demoContractRoutes());
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(
      <ContractDetailView contractId={DEMO_ID} />,
      fetchMock,
    );

    // the demo contract's lease is listed; the capture contract's leases
    // are filtered out client-side by contract_id
    await waitFor(() => {
      expect(screen.getByText(DEMO_CONTRACT_LEASE.id)).toBeInTheDocument();
    });
    expect(screen.queryByText(FIXTURE_LEASE_ACTIVE.id)).toBeNull();
    expect(screen.queryByText(FIXTURE_LEASE_REVOKED.id)).toBeNull();

    // only granted/active leases renew/revoke — the rule is stated inline
    expect(
      screen.getByText(/only granted\/active leases revoke \(found renewed\)/),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Renew" })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "Revoke" })).toHaveLength(1);

    // the grant drawer
    fireEvent.click(screen.getByRole("button", { name: "Grant lease" }));
    const dialog = await screen.findByRole("dialog");

    // the validity-window rule callout mentions the contract's own bounds
    const rule = within(dialog).getByTestId("lease-validity-rule");
    expect(rule).toHaveTextContent(FIXTURE_DEMO_CONTRACT.validity.not_before);
    expect(rule).toHaveTextContent(FIXTURE_DEMO_CONTRACT.validity.not_after);
    expect(rule).toHaveTextContent("invalid-input");

    // the window fields are prefilled INSIDE the contract validity
    expect(within(dialog).getByLabelText("granted_at")).toHaveValue(
      FIXTURE_DEMO_CONTRACT.validity.not_before,
    );
    expect(within(dialog).getByLabelText("not_before")).toHaveValue(
      FIXTURE_DEMO_CONTRACT.validity.not_before,
    );
    expect(within(dialog).getByLabelText("not_after")).toHaveValue(
      FIXTURE_DEMO_CONTRACT.validity.not_after,
    );

    // the exact grant route is previewed
    expect(dialog).toHaveTextContent(`/api/2.0/contracts/${DEMO_ID}/leases`);
  });
});

describe("Contract detail — error path", () => {
  it("surfaces resource-unknown verbatim when the contract read 404s, with a way back", async () => {
    const unknownId = "sha256:unknown-contract-id";
    const fetchMock = routeFetch({
      ...APPLICATION_ROUTE,
      [`GET /api/2.0/contracts/${unknownId}*`]: {
        __status: 404,
        body: FIXTURE_ERROR_NOT_FOUND,
      },
      [`GET /api/2.0/intents/${unknownId}*`]: {
        __status: 404,
        body: FIXTURE_ERROR_NOT_FOUND,
      },
      "GET /api/2.0/leases": envelope({
        items: [],
        next_cursor: "",
        has_more: false,
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(
      <ContractDetailView contractId={unknownId} />,
      fetchMock,
    );

    await waitFor(() => {
      expect(screen.getByTestId(ERROR_REASON_TEST_ID)).toHaveTextContent(
        "resource-unknown",
      );
    });

    // the way back to the index
    expect(
      screen
        .getAllByRole("link")
        .some((link) => link.getAttribute("href") === "/connectivity"),
    ).toBe(true);
  });
});
