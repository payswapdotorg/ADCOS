/**
 * Webhook endpoints tests (station A, deliverable #4):
 *
 * - the list renders backend truth; row activation opens the detail
 *   drawer (the endpoint record + key_id + created_at + url + event
 *   types) with the delivery journal table;
 * - the register form offers EXACTLY the frozen event-type vocabulary
 *   as checkboxes — a free-text event type is IMPOSSIBLE (there is no
 *   text input for event types at all);
 * - the register flow sends the real request through the typed client
 *   (auth headers + an auto-generated idempotency key), renders the
 *   record outcome (key_id, no secret material — stated honestly) and
 *   refreshes the list;
 * - a backend rejection renders the reason VERBATIM (the
 *   vocabulary-drift case);
 * - the delivery journal's honest empty state and deeper-pagination
 *   notice.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import {
  DevelopersWorkspace,
  WEBHOOK_EVENT_TYPES,
  WEBHOOK_EVENT_TYPE_COUNT,
} from "@/features/developers";
import type { WebhookEndpoint } from "@/lib/api/types";
import { __resetRequestLogForTests } from "@/features/requests/request-log";
import {
  FIXTURE_DELIVERIES,
  FIXTURE_DELIVERY_DELIVERED,
  FIXTURE_ENDPOINT,
  FIXTURE_ENDPOINTS_LIST,
  FIXTURE_SESSION,
} from "./developers-fixtures";
import {
  APPLICATION_ROUTE,
  envelope,
  errorEnvelope,
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

/** The routes a connected page with the detail drawer needs. */
function detailRoutes(overrides?: Record<string, unknown>): Record<string, unknown> {
  return {
    ...APPLICATION_ROUTE,
    "GET /api/2.0/webhook-endpoints": envelope(FIXTURE_ENDPOINTS_LIST),
    [`GET /api/2.0/webhook-endpoints/${FIXTURE_ENDPOINT.id}`]: envelope(FIXTURE_ENDPOINT),
    [`GET /api/2.0/webhook-endpoints/${FIXTURE_ENDPOINT.id}/deliveries`]:
      envelope(FIXTURE_DELIVERIES),
    ...overrides,
  };
}

function checkboxFor(eventType: string): HTMLInputElement {
  const option = screen
    .getAllByTestId("webhook-event-type-option")
    .find((node) => (node as HTMLInputElement).value === eventType);
  if (!option) {
    throw new Error(`no checkbox for ${eventType}`);
  }
  return option as HTMLInputElement;
}

describe("Developers — webhook endpoints", () => {
  it("lists the endpoints and opens the detail drawer with the endpoint record and delivery journal", async () => {
    const fetchMock = routeFetch(detailRoutes());
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<DevelopersWorkspace />, fetchMock);

    // the list renders backend truth (both fixture endpoints)
    await screen.findByText(FIXTURE_ENDPOINT.id);
    expect(
      screen.getByText("https://ops.example.net/hooks/adcos-status"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("endpoints-count")).toHaveTextContent(
      "2 webhook endpoints",
    );

    // row activation opens the detail drawer: the endpoint record…
    fireEvent.click(screen.getByText(FIXTURE_ENDPOINT.id));
    await screen.findByText("Delivery journal");
    // (url / key_id / created_at / event types render in BOTH the table
    // row and the drawer record — assert both occurrences)
    expect(screen.getAllByText(FIXTURE_ENDPOINT.url).length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText(FIXTURE_ENDPOINT.key_id).length).toBeGreaterThanOrEqual(2);
    expect(
      screen.getAllByText(FIXTURE_ENDPOINT.created_at).length,
    ).toBeGreaterThanOrEqual(2);
    expect(
      screen.getAllByText(FIXTURE_ENDPOINT.event_types.join(", ")).length,
    ).toBeGreaterThanOrEqual(2);

    // …and the delivery journal table (states VERBATIM; queried within
    // the dialog so the page's event-type filter options never collide)
    const dialog = screen.getByRole("dialog");
    expect(
      within(dialog).getByText("webhook_endpoint.registered"),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByText("connectivity_contract.activated"),
    ).toBeInTheDocument();
    const statuses = screen
      .getAllByTestId("status-root")
      .map((node) => node.getAttribute("data-value"));
    expect(statuses).toContain("delivered");
    expect(statuses).toContain("failed");
    expect(screen.getByText("2026-09-14T05:25:00Z")).toBeInTheDocument(); // next retry
    expect(screen.getByText("2 deliveries")).toBeInTheDocument();

    // the reads are reproduced in place
    expect(
      screen.getAllByText(
        `/api/2.0/webhook-endpoints/${FIXTURE_ENDPOINT.id}/deliveries`,
      ).length,
    ).toBeGreaterThan(0);

    // closing the drawer returns to the list
    fireEvent.click(screen.getByRole("button", { name: "Close panel" }));
    await waitFor(() => {
      expect(screen.queryByText("Delivery journal")).toBeNull();
    });
  });

  it("offers EXACTLY the frozen event-type vocabulary as checkboxes — free text is impossible", async () => {
    const fetchMock = routeFetch(detailRoutes());
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<DevelopersWorkspace />, fetchMock);
    await screen.findByText(FIXTURE_ENDPOINT.id);

    // the vocabulary module is pinned: the frozen nine, nothing else
    expect(WEBHOOK_EVENT_TYPE_COUNT).toBe(9);
    expect([...WEBHOOK_EVENT_TYPES]).toEqual([
      "connectivity_intent.created",
      "connectivity_contract.offers_selected",
      "connectivity_contract.activated",
      "connectivity_contract.terminated",
      "connectivity_contract.state_changed",
      "connectivity_lease.granted",
      "connectivity_lease.renewed",
      "connectivity_lease.revoked",
      "webhook_endpoint.registered",
    ]);

    fireEvent.click(screen.getByTestId("webhook-register-open"));
    const fieldset = await screen.findByTestId("webhook-event-types");

    // ONLY checkbox inputs — there is no text input for event types,
    // so a free-text event type is impossible by construction
    const inputs = Array.from(fieldset.querySelectorAll("input"));
    expect(inputs).toHaveLength(9);
    for (const input of inputs) {
      expect(input.getAttribute("type")).toBe("checkbox");
    }
    expect(inputs.map((input) => input.value)).toEqual([...WEBHOOK_EVENT_TYPES]);

    // the ONLY non-checkbox input in the whole dialog is the url field
    const dialog = screen.getByRole("dialog");
    const nonCheckbox = Array.from(dialog.querySelectorAll("input")).filter(
      (input) => input.type !== "checkbox",
    );
    expect(nonCheckbox).toHaveLength(1);
    expect(nonCheckbox[0]).toBe(screen.getByLabelText("url"));

    // the checkbox labels render the event types VERBATIM
    for (const eventType of WEBHOOK_EVENT_TYPES) {
      expect(within(fieldset).getByText(eventType)).toBeInTheDocument();
    }
  });

  it("registers an endpoint through the typed client (auth + idempotency headers), shows the record outcome, and refreshes the list", async () => {
    const newEndpoint: WebhookEndpoint = {
      api_version: "2.0",
      created_at: "2026-09-14T06:00:00Z",
      developer_id: "adcos:runtime:demo-developer",
      environment: "sandbox",
      event_types: ["connectivity_intent.created", "webhook_endpoint.registered"],
      id: "sha256:77a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f",
      key_id: "whk-77a1b2c3d4e5f607-whv1",
      kind: "webhook_endpoint",
      url: "https://new.example/hook",
    };
    const registered: WebhookEndpoint[] = [];
    const fetchMock = trackedFetch({
      ...APPLICATION_ROUTE,
      "GET /api/2.0/webhook-endpoints": () =>
        envelope({
          items: [...FIXTURE_ENDPOINTS_LIST.items, ...registered],
          next_cursor: "",
          has_more: false,
        }),
      "POST /api/2.0/webhook-endpoints": () => {
        registered.push(newEndpoint);
        return envelope(newEndpoint);
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<DevelopersWorkspace />, fetchMock);
    await screen.findByText(FIXTURE_ENDPOINT.id);

    fireEvent.click(screen.getByTestId("webhook-register-open"));
    await screen.findByTestId("webhook-event-types");

    // fill the form (checkboxes in NON-vocabulary order — the sent
    // body carries the canonical order)
    fireEvent.click(checkboxFor("webhook_endpoint.registered"));
    fireEvent.click(checkboxFor("connectivity_intent.created"));
    fireEvent.change(screen.getByLabelText("url"), {
      target: { value: "https://new.example/hook" },
    });

    // the preview shows the request BEFORE submit
    expect(
      screen.getAllByText(/https:\/\/new\.example\/hook/).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByText("/api/2.0/webhook-endpoints").length,
    ).toBeGreaterThan(0);

    // local validation holds the submit until the form is valid
    expect(screen.getByTestId("webhook-register-submit")).toBeEnabled();

    fireEvent.click(screen.getByTestId("webhook-register-submit"));

    // the outcome renders the endpoint record with its key_id and the
    // honest no-secret statement
    const outcome = await screen.findByTestId("webhook-registered-outcome");
    expect(within(outcome).getByText(newEndpoint.id)).toBeInTheDocument();
    expect(within(outcome).getByText(newEndpoint.key_id)).toBeInTheDocument();
    expect(within(outcome).getByText(newEndpoint.url)).toBeInTheDocument();
    expect(outcome.textContent).toContain(
      "No signing secret is returned by this API",
    );

    // the request went through the typed client: auth headers, an
    // auto-generated idempotency key, and the canonical body
    const postCall = fetchMock.mock.calls.find(
      ([path, init]) =>
        path === "/api/2.0/webhook-endpoints" &&
        (init?.method ?? "GET").toUpperCase() === "POST",
    );
    expect(postCall).toBeDefined();
    const headers = postCall![1]?.headers as Record<string, string>;
    expect(headers["X-ADCOS-Application"]).toBe(FIXTURE_SESSION.applicationId);
    expect(headers["X-ADCOS-Credential"]).toBe(FIXTURE_SESSION.credential);
    expect(headers["X-ADCOS-API-Version"]).toBe("2.0");
    expect(headers["X-ADCOS-Idempotency-Key"]).toMatch(/^[0-9a-f-]{16,}$/);
    const sentBody = JSON.parse(postCall![1]?.body as string) as {
      url: string;
      event_types: string[];
    };
    expect(sentBody).toEqual({
      url: "https://new.example/hook",
      event_types: ["connectivity_intent.created", "webhook_endpoint.registered"],
    });

    // Done closes the drawer and refreshes the list — the new row appears
    fireEvent.click(screen.getByTestId("webhook-register-done"));
    await waitFor(() => {
      expect(screen.getByText(newEndpoint.id)).toBeInTheDocument();
    });
    const listCalls = fetchMock.mock.calls.filter(
      ([path]) => path === "/api/2.0/webhook-endpoints",
    );
    expect(listCalls.length).toBeGreaterThanOrEqual(2);
  });

  it("renders a backend rejection of the registration with the reason VERBATIM", async () => {
    const fetchMock = routeFetch({
      ...APPLICATION_ROUTE,
      "GET /api/2.0/webhook-endpoints": envelope(FIXTURE_ENDPOINTS_LIST),
      "POST /api/2.0/webhook-endpoints": {
        __status: 400,
        // the vocabulary-drift case: a backend whose frozen vocabulary
        // no longer contains a type the console still offers
        body: errorEnvelope(
          "invalid-input",
          "event type 'connectivity_intent.created' is not in the frozen vocabulary",
          400,
        ),
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<DevelopersWorkspace />, fetchMock);
    await screen.findByText(FIXTURE_ENDPOINT.id);

    fireEvent.click(screen.getByTestId("webhook-register-open"));
    await screen.findByTestId("webhook-event-types");

    fireEvent.click(checkboxFor("connectivity_intent.created"));
    fireEvent.change(screen.getByLabelText("url"), {
      target: { value: "https://new.example/hook" },
    });
    fireEvent.click(screen.getByTestId("webhook-register-submit"));

    // the reason code and the backend's own message, VERBATIM
    await waitFor(() => {
      expect(screen.getByTestId("error-reason")).toHaveTextContent("invalid-input");
    });
    expect(
      screen.getByText(/is not in the frozen vocabulary/),
    ).toBeInTheDocument();

    // the form survives the failure (retry is possible)
    expect(screen.getByLabelText("url")).toHaveValue("https://new.example/hook");
    expect(screen.getByTestId("webhook-register-submit")).toBeEnabled();
  });

  it("shows the honest empty state for an endpoint with no deliveries yet", async () => {
    const fetchMock = routeFetch(
      detailRoutes({
        [`GET /api/2.0/webhook-endpoints/${FIXTURE_ENDPOINT.id}/deliveries`]:
          envelope({ items: [], next_cursor: "", has_more: false }),
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<DevelopersWorkspace />, fetchMock);
    await screen.findByText(FIXTURE_ENDPOINT.id);

    fireEvent.click(screen.getByText(FIXTURE_ENDPOINT.id));
    await screen.findByText("No deliveries yet");
    expect(screen.getByText(/drive a contract lifecycle/i)).toBeInTheDocument();
    expect(screen.getByText("0 deliveries")).toBeInTheDocument();
  });

  it("surfaces the deeper-pagination notice when the delivery journal has more pages", async () => {
    const fetchMock = routeFetch(
      detailRoutes({
        [`GET /api/2.0/webhook-endpoints/${FIXTURE_ENDPOINT.id}/deliveries`]:
          envelope({
            items: [FIXTURE_DELIVERY_DELIVERED],
            next_cursor: "cursor-2",
            has_more: true,
          }),
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<DevelopersWorkspace />, fetchMock);
    await screen.findByText(FIXTURE_ENDPOINT.id);

    fireEvent.click(screen.getByText(FIXTURE_ENDPOINT.id));
    await screen.findByTestId("deliveries-deeper-pagination-notice");
    expect(
      screen.getByText(/fetch forbids GET bodies/),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText(
        `/api/2.0/webhook-endpoints/${FIXTURE_ENDPOINT.id}/deliveries`,
      ).length,
    ).toBeGreaterThan(0);
  });
});
