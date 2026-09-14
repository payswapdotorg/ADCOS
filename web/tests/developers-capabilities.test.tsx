/**
 * Capability chips tests (station A, deliverable #2):
 *
 * - every capability on the application record renders with its
 *   registry-derived explanation (granted style);
 * - a capability REQUIRED by the registry but MISSING from the record
 *   gets the distinct denied style, names what it unlocks, and states
 *   the verbatim `capability-denied` consequence;
 * - the denied state gates the webhook surfaces honestly (reads
 *   suspended, the register submit disabled) without firing doomed
 *   requests.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { DevelopersWorkspace } from "@/features/developers";
import { __resetRequestLogForTests } from "@/features/requests/request-log";
import {
  FIXTURE_APPLICATION,
  FIXTURE_APPLICATION_PARTIAL_CAPS,
  FIXTURE_ENDPOINTS_LIST,
} from "./developers-fixtures";
import {
  envelope,
  renderWithSession,
  routeFetch,
  trackedFetch,
} from "./developers-harness";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/developers",
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

beforeEach(() => {
  __resetRequestLogForTests();
  pushMock.mockClear();
});

describe("Developers — capability chips", () => {
  it("renders every granted capability with its registry-derived explanation", async () => {
    const fetchMock = routeFetch({
      "GET /api/2.0/application": envelope(FIXTURE_APPLICATION),
      "GET /api/2.0/webhook-endpoints": envelope(FIXTURE_ENDPOINTS_LIST),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<DevelopersWorkspace />, fetchMock);

    await screen.findByTestId("capability-chips");

    // all 8 registry-required capabilities granted — no denied chips
    const chips = screen.getAllByTestId("capability-chip");
    expect(chips).toHaveLength(8);
    for (const chip of chips) {
      expect(chip.getAttribute("data-granted")).toBe("true");
    }

    // the capability names render VERBATIM with human labels
    expect(screen.getByText("intents:write")).toBeInTheDocument();
    expect(screen.getByText("Create intents & drive the lifecycle")).toBeInTheDocument();
    expect(screen.getByText("webhooks:read")).toBeInTheDocument();

    // each explanation is the registry's own operation list
    const intentsRead = chips.find(
      (chip) => chip.getAttribute("data-capability") === "intents:read",
    );
    expect(intentsRead?.textContent).toContain("GET /api/2.0/intents");
    const webhooksWrite = chips.find(
      (chip) => chip.getAttribute("data-capability") === "webhooks:write",
    );
    expect(webhooksWrite?.textContent).toContain(
      "POST /api/2.0/webhook-endpoints",
    );
  });

  it("gives missing capabilities the denied style, gates the webhook surfaces, and fires no doomed read", async () => {
    const fetchMock = trackedFetch({
      "GET /api/2.0/application": envelope(FIXTURE_APPLICATION_PARTIAL_CAPS),
      "GET /api/2.0/webhook-endpoints": envelope(FIXTURE_ENDPOINTS_LIST),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<DevelopersWorkspace />, fetchMock);

    await screen.findByTestId("capability-chips");

    // 5 granted + 3 denied (exactly the registry-required set minus
    // the fixture variant's grants)
    const chips = screen.getAllByTestId("capability-chip");
    expect(chips).toHaveLength(8);
    const granted = chips.filter((chip) => chip.getAttribute("data-granted") === "true");
    const denied = chips.filter((chip) => chip.getAttribute("data-granted") === "false");
    expect(granted.map((chip) => chip.getAttribute("data-capability"))).toEqual([
      "assurance:read",
      "intents:read",
      "intents:write",
      "leases:read",
      "leases:write",
    ]);
    expect(denied.map((chip) => chip.getAttribute("data-capability"))).toEqual([
      "usage:read",
      "webhooks:read",
      "webhooks:write",
    ]);

    // the denied chip names what it unlocks AND the verbatim consequence
    const webhooksRead = denied.find(
      (chip) => chip.getAttribute("data-capability") === "webhooks:read",
    );
    expect(webhooksRead?.textContent).toContain("GET /api/2.0/webhook-endpoints");
    expect(webhooksRead?.textContent).toContain("capability-denied");
    expect(webhooksRead?.textContent).toContain("not granted");

    // the webhook section states the suspended reads honestly…
    expect(await screen.findByTestId("webhooks-read-denied")).toHaveTextContent(
      /webhooks:read/,
    );

    // …and NEVER fired the list read it knows is unauthorized
    const listCalls = fetchMock.mock.calls.filter(
      ([path]) => path === "/api/2.0/webhook-endpoints",
    );
    expect(listCalls).toHaveLength(0);

    // the register form opens, explains the missing webhooks:write
    // verbatim, and disables the submit
    fireEvent.click(screen.getByTestId("webhook-register-open"));
    await waitFor(() => {
      expect(screen.getByTestId("webhooks-write-denied")).toBeInTheDocument();
    });
    expect(screen.getByTestId("webhooks-write-denied")).toHaveTextContent(
      /webhooks:write/,
    );
    expect(screen.getByTestId("webhook-register-submit")).toBeDisabled();
  });
});
