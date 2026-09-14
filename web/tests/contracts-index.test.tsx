/**
 * Connectivity contracts index tests — REAL captured shapes only
 * (tests/fixtures.ts), fetch mocked at the global boundary through the
 * shared harness.
 *
 * Covers the work order's index demands:
 * - rows render from FIXTURE_CONTRACTS_LIST with states VERBATIM, and row
 *   activation routes into the contract detail chain;
 * - the lifecycle-state filter is a REAL backend filter (the GET
 *   /api/2.0/contracts JSON body carries filters.state);
 * - free-text search and the validity-overlapping date narrow CLIENT-SIDE
 *   (no additional fetch);
 * - a disconnected session shows connect guidance and fires NO
 *   authenticated read;
 * - an empty list shows the honest fresh-account guidance with the
 *   builder link.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { ContractsIndexView } from "@/features/contracts";
import { __resetRequestLogForTests } from "@/features/requests/request-log";
import { STATUS_TEST_IDS } from "@/components/ui";
import { FIXTURE_CONTRACTS_LIST } from "./fixtures";
import {
  APPLICATION_ROUTE,
  envelope,
  renderBare,
  renderWithSession,
  routeFetch,
} from "./harness";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/connectivity",
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
  pushMock.mockClear();
});

describe("Connectivity — contracts index", () => {
  it("renders both fixture contracts with states verbatim and routes row activation to the detail page", async () => {
    const fetchMock = routeFetch({
      ...APPLICATION_ROUTE,
      "GET /api/2.0/contracts": envelope(FIXTURE_CONTRACTS_LIST),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<ContractsIndexView />, fetchMock);

    const [first, second] = FIXTURE_CONTRACTS_LIST.items;
    await waitFor(() => {
      expect(screen.getByText(first.id)).toBeInTheDocument();
    });
    expect(screen.getByText(second.id)).toBeInTheDocument();

    // the backend state vocabulary, VERBATIM (one Status per row)
    const activeStatuses = screen
      .getAllByTestId(STATUS_TEST_IDS.root)
      .filter((node) => node.getAttribute("data-value") === "CONTRACT_ACTIVE");
    expect(activeStatuses).toHaveLength(2);

    // the honest count line
    expect(screen.getByTestId("contracts-count")).toHaveTextContent(
      "2 contracts",
    );

    // the builder entry point is reachable from the header
    expect(
      screen
        .getAllByRole("link")
        .some((link) => link.getAttribute("href") === "/connectivity/new"),
    ).toBe(true);

    // row activation routes into the lifecycle chain
    fireEvent.click(screen.getByText(first.id));
    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith(
        `/connectivity/contracts/${first.contract_id}`,
      );
    });
  });

  it("sends the REAL backend state filter in the GET body when a lifecycle state is selected", async () => {
    const fetchMock = trackedFetch({
      ...APPLICATION_ROUTE,
      "GET /api/2.0/contracts": envelope(FIXTURE_CONTRACTS_LIST),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(
      <ContractsIndexView />,
      fetchMock as unknown as ReturnType<typeof routeFetch>,
    );

    await waitFor(() => {
      expect(screen.getByText(FIXTURE_CONTRACTS_LIST.items[0].id)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("Lifecycle state"), {
      target: { value: "CONTRACT_ACTIVE" },
    });

    await waitFor(() => {
      const contractsCalls = fetchMock.mock.calls.filter(
        ([path]) => path === "/api/2.0/contracts",
      );
      expect(contractsCalls.length).toBeGreaterThanOrEqual(2);
    });

    // the filter rides the GET request's JSON body — the backend's frozen
    // list discipline — alongside the page limit
    const calls = fetchMock.mock.calls.filter(
      ([path]) => path === "/api/2.0/contracts",
    );
    const body = JSON.parse(String(calls[calls.length - 1][1]?.body));
    expect(body).toEqual({
      limit: 100,
      filters: { state: "CONTRACT_ACTIVE" },
    });
  });

  it("narrows client-side by free-text search and by the validity-overlapping date (no extra fetch)", async () => {
    const fetchMock = trackedFetch({
      ...APPLICATION_ROUTE,
      "GET /api/2.0/contracts": envelope(FIXTURE_CONTRACTS_LIST),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(
      <ContractsIndexView />,
      fetchMock as unknown as ReturnType<typeof routeFetch>,
    );

    const [first, second] = FIXTURE_CONTRACTS_LIST.items;
    await waitFor(() => {
      expect(screen.getByText(first.id)).toBeInTheDocument();
    });
    expect(screen.getByText(second.id)).toBeInTheDocument();

    // free-text search narrows to the matching id
    fireEvent.change(screen.getByPlaceholderText("Search contract id…"), {
      target: { value: first.id.slice(0, 23) },
    });
    expect(screen.getByText(first.id)).toBeInTheDocument();
    expect(screen.queryByText(second.id)).toBeNull();

    // clearing the search restores both rows
    fireEvent.change(screen.getByPlaceholderText("Search contract id…"), {
      target: { value: "" },
    });
    expect(screen.getByText(second.id)).toBeInTheDocument();

    // a date inside both validity windows keeps both rows…
    fireEvent.change(screen.getByLabelText("Validity overlapping date"), {
      target: { value: "2026-09-20" },
    });
    expect(screen.getByText(first.id)).toBeInTheDocument();
    expect(screen.getByText(second.id)).toBeInTheDocument();

    // …a date after every window narrows to none (honest empty state)
    fireEvent.change(screen.getByLabelText("Validity overlapping date"), {
      target: { value: "2026-10-15" },
    });
    expect(screen.queryByText(first.id)).toBeNull();
    expect(screen.queryByText(second.id)).toBeNull();
    expect(
      screen.getByText("No contracts match the current filters"),
    ).toBeInTheDocument();

    // both narrowings stayed CLIENT-SIDE: still exactly one list read
    const contractsCalls = fetchMock.mock.calls.filter(
      ([path]) => path === "/api/2.0/contracts",
    );
    expect(contractsCalls).toHaveLength(1);
  });

  it("fires NO authenticated contracts read while disconnected and shows connect guidance", async () => {
    const fetchMock = trackedFetch({});
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<ContractsIndexView />);

    // the honest gate: the list is an authenticated developer-API read
    expect(screen.getByTestId("connect-guidance")).toBeInTheDocument();
    expect(screen.getByText("Connect application")).toBeInTheDocument();

    // the authenticated read was NEVER fired
    const contractsCalls = fetchMock.mock.calls.filter(
      ([path]) => path === "/api/2.0/contracts",
    );
    expect(contractsCalls).toHaveLength(0);

    // the header (and its builder link) still render
    expect(screen.getByText("Connectivity")).toBeInTheDocument();
    expect(
      screen
        .getAllByRole("link")
        .some((link) => link.getAttribute("href") === "/connectivity/new"),
    ).toBe(true);
  });

  it("shows the fresh-account guidance with the builder link when the list is empty", async () => {
    const fetchMock = routeFetch({
      ...APPLICATION_ROUTE,
      "GET /api/2.0/contracts": envelope({
        items: [],
        next_cursor: "",
        has_more: false,
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<ContractsIndexView />, fetchMock);

    await waitFor(() => {
      expect(screen.getByText("No contracts yet")).toBeInTheDocument();
    });
    expect(
      screen.getByText(/Record your first connectivity intent/),
    ).toBeInTheDocument();

    // the guidance links into the builder and mentions the demonstration
    const links = screen.getAllByRole("link");
    expect(
      links.some((link) => link.getAttribute("href") === "/connectivity/new"),
    ).toBe(true);
    expect(
      links.some((link) => link.getAttribute("href") === "/fulfillment"),
    ).toBe(true);
  });
});
