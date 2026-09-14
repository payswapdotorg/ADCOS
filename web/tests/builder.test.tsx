/**
 * Builder tests — the constraint-preservation seam and the exact request
 * discipline, against REAL captured shapes (tests/fixtures.ts) with fetch
 * mocked at the global boundary through the shared harness.
 *
 * Covers the work order's builder demands:
 * - CONSTRAINT PRESERVATION: params serialize byte-equal (the documented
 *   number heuristic only); all constraints survive; removal in the UI is
 *   an explicit user action that updates the body;
 * - guided → advanced round-trip: the textarea carries the serialized
 *   canonical body;
 * - advanced unknown-member preservation: a member the guided form does
 *   not represent survives the switch and rides the submit body;
 * - invalid JSON in advanced mode blocks submit with an inline error;
 * - the pre-submit panel shows POST /api/2.0/intents with the exact body
 *   and the idempotency key that will be sent;
 * - a successful submit routes to the new contract's detail page and the
 *   sent request matches the preview byte-for-byte;
 * - a rejected submit surfaces the backend's VERBATIM reason code.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { BuilderView } from "@/features/contracts";
import {
  buildIntentBody,
  canonicalIntentBody,
  defaultGuidedState,
} from "@/features/contracts/builder/serialization";
import { __resetRequestLogForTests } from "@/features/requests/request-log";
import { ERROR_REASON_TEST_ID } from "@/components/ui";
import { FIXTURE_APPLICATION, FIXTURE_CONTRACT_INTENT } from "./fixtures";
import {
  APPLICATION_ROUTE,
  envelope,
  renderWithSession,
  routeFetch,
} from "./harness";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/connectivity/new",
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
 * 400 — the real boundary rejection for a body missing `termination`
 * (verified live against the sandbox runtime; the reason vocabulary is
 * the backend's own).
 */
const INTENT_ERROR_MISSING_TERMINATION = {
  api_version: "2.0",
  environment: "sandbox",
  request_id: "sha256:harness_missing_termination",
  error: {
    canonical_reason: "",
    environment: "sandbox",
    http_status: 400,
    message: "request body is missing required member 'termination'",
    reason: "invalid-input",
    request_id: "sha256:harness_missing_termination",
    resource_id: "",
    retry_after: "",
    retryable: false,
  },
} as const;

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;



/** The exact body the pre-submit panel displays (the `<code>` payload). */
function displayedIntentBody(): Record<string, unknown> {
  const code = screen
    .getByTestId("intent-body-json")
    .querySelector("code");
  return JSON.parse(code?.textContent ?? "") as Record<string, unknown>;
}

function trackedFetch(routes: Record<string, unknown>) {
  const routed = routeFetch(routes);
  return vi.fn((path: string, init?: RequestInit) => routed(path, init));
}

beforeEach(() => {
  __resetRequestLogForTests();
  pushMock.mockClear();
});

describe("Builder — constraint preservation (the serialization seam)", () => {
  it("serializes custom constraint params byte-equal and keeps every constraint", () => {
    const state = defaultGuidedState();
    state.hardConstraints = [
      { kind: "latency-bound", kindIsCustom: false, params: [{ key: "ms", value: "100" }] },
      {
        kind: "throughput-floor",
        kindIsCustom: false,
        params: [{ key: "bps", value: "1000" }],
      },
      {
        kind: "energy-ceiling",
        kindIsCustom: true,
        params: [
          { key: "millijoules", value: "100" },
          { key: "unit", value: "mJ" },
        ],
      },
    ];

    const body = buildIntentBody(state);
    const constraints = body.hard_constraints ?? [];

    // all three constraints survive
    expect(constraints).toHaveLength(3);
    expect(constraints.map((constraint) => constraint.kind)).toEqual([
      "latency-bound",
      "throughput-floor",
      "energy-ceiling",
    ]);

    // the custom params serialize byte-equal: numeric-looking values
    // become numbers, everything else stays a string — nothing dropped
    expect(JSON.stringify(constraints[2].params)).toBe(
      JSON.stringify({ millijoules: 100, unit: "mJ" }),
    );
    expect(JSON.stringify(constraints[0].params)).toBe(
      JSON.stringify({ ms: 100 }),
    );
    expect(JSON.stringify(constraints[1].params)).toBe(
      JSON.stringify({ bps: 1000 }),
    );
  });

  it("builds a custom constraint in the UI, then removal (an explicit user action) updates the body", async () => {
    const fetchMock = routeFetch({ ...APPLICATION_ROUTE });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<BuilderView />, fetchMock);

    await waitFor(() => {
      expect(screen.getByText("New connectivity intent")).toBeInTheDocument();
    });

    // the seeded defaults serialize into the pre-submit body
    expect(displayedIntentBody().hard_constraints).toEqual([
      { kind: "latency-bound", params: { ms: 100 } },
      { kind: "throughput-floor", params: { bps: 1000 } },
    ]);

    // add a custom constraint with free-form typed params
    fireEvent.click(screen.getByRole("button", { name: "Add constraint" }));
    fireEvent.change(screen.getByLabelText("Constraint 3 custom kind"), {
      target: { value: "energy-ceiling" },
    });
    fireEvent.change(screen.getByLabelText("Constraint 3 param 1 key"), {
      target: { value: "millijoules" },
    });
    fireEvent.change(screen.getByLabelText("Constraint 3 param 1 value"), {
      target: { value: "100" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Add param to constraint 3" }),
    );
    fireEvent.change(screen.getByLabelText("Constraint 3 param 2 key"), {
      target: { value: "unit" },
    });
    fireEvent.change(screen.getByLabelText("Constraint 3 param 2 value"), {
      target: { value: "mJ" },
    });

    let body = displayedIntentBody();
    const constraints = body.hard_constraints as {
      kind: string;
      params: Record<string, unknown>;
    }[];
    expect(constraints).toHaveLength(3);
    expect(constraints[2].kind).toBe("energy-ceiling");
    expect(JSON.stringify(constraints[2].params)).toBe(
      JSON.stringify({ millijoules: 100, unit: "mJ" }),
    );

    // removing a constraint is an explicit user action — the body updates
    fireEvent.click(screen.getByRole("button", { name: "Remove constraint 1" }));
    body = displayedIntentBody();
    const remaining = body.hard_constraints as {
      kind: string;
      params: Record<string, unknown>;
    }[];
    expect(remaining).toHaveLength(2);
    expect(remaining.map((constraint) => constraint.kind)).toEqual([
      "throughput-floor",
      "energy-ceiling",
    ]);
  });
});

describe("Builder — mode switching", () => {
  it("serializes the guided state into the advanced textarea", async () => {
    const fetchMock = routeFetch({ ...APPLICATION_ROUTE });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<BuilderView />, fetchMock);

    await waitFor(() => {
      expect(screen.getByText("New connectivity intent")).toBeInTheDocument();
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Advanced (canonical JSON)" }),
    );

    const textarea = screen.getByLabelText("Canonical intent JSON");
    const parsed = JSON.parse((textarea as HTMLTextAreaElement).value);
    expect(parsed.hard_constraints).toEqual([
      { kind: "latency-bound", params: { ms: 100 } },
      { kind: "throughput-floor", params: { bps: 1000 } },
    ]);
    // the guided defaults ride along as the canonical members
    expect(parsed.requirements).toEqual([
      {
        ref_kind: "intent-requirements",
        value: "demo:intent-requirements:v1",
        provenance: {
          issuer: "intent-authority",
          decision_refs: ["demo:intent:v1"],
        },
      },
    ]);
    expect(parsed.validity).toEqual({
      not_before: "2026-09-14T00:00:00Z",
      not_after: "2026-10-14T00:00:00Z",
    });
    expect(parsed.termination).toEqual({
      conditions: ["principal-requested", "validity-expired"],
      compensation: { ref_kind: "compensation", value: "demo:compensation:v1" },
    });
  });

  it("preserves an unknown advanced member across the switch to guided and into the submit body", async () => {
    const fetchMock = routeFetch({ ...APPLICATION_ROUTE });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<BuilderView />, fetchMock);

    await waitFor(() => {
      expect(screen.getByText("New connectivity intent")).toBeInTheDocument();
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Advanced (canonical JSON)" }),
    );

    const advancedBody = {
      ...canonicalIntentBody(),
      superseded_contract: { ref_kind: "contract", value: "sha256:abc" },
    };
    fireEvent.change(screen.getByLabelText("Canonical intent JSON"), {
      target: { value: JSON.stringify(advancedBody, null, 2) },
    });

    fireEvent.click(screen.getByRole("button", { name: "Guided" }));

    // the notice is visible while the member rides along
    const notice = screen.getByTestId("preserved-members-notice");
    expect(notice).toHaveTextContent(
      "1 unknown member(s) preserved from advanced mode",
    );

    // the submit body carries it byte-equal
    const body = displayedIntentBody();
    expect(JSON.stringify(body.superseded_contract)).toBe(
      JSON.stringify({ ref_kind: "contract", value: "sha256:abc" }),
    );
  });

  it("locks the guided constraint editor (nothing coerced or dropped) when advanced constraints carry types the editor cannot represent byte-exactly", async () => {
    const fetchMock = routeFetch({ ...APPLICATION_ROUTE });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<BuilderView />, fetchMock);

    await waitFor(() => {
      expect(screen.getByText("New connectivity intent")).toBeInTheDocument();
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Advanced (canonical JSON)" }),
    );

    // a constraint whose params include a BOOLEAN — beyond the guided
    // editor's number|string representation
    const advancedBody = {
      ...canonicalIntentBody(),
      hard_constraints: [
        { kind: "latency-bound", params: { ms: 100 } },
        { kind: "strict-mode", params: { enabled: true } },
      ],
    };
    fireEvent.change(screen.getByLabelText("Canonical intent JSON"), {
      target: { value: JSON.stringify(advancedBody, null, 2) },
    });

    fireEvent.click(screen.getByRole("button", { name: "Guided" }));

    // the editor is locked with the honest notice…
    expect(screen.getByTestId("constraints-locked-notice")).toBeInTheDocument();

    // …and the whole hard_constraints member rides along BYTE-EQUAL:
    // the boolean param survives the roundtrip untouched
    const body = displayedIntentBody();
    expect(JSON.stringify(body.hard_constraints)).toBe(
      JSON.stringify(advancedBody.hard_constraints),
    );
    expect(
      (body.hard_constraints as { params: { enabled: unknown } }[])[1].params
        .enabled,
    ).toBe(true);
  });

  it("blocks submit with an inline error while the advanced JSON is invalid", async () => {
    const fetchMock = trackedFetch({ ...APPLICATION_ROUTE });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(
      <BuilderView />,
      fetchMock as unknown as ReturnType<typeof routeFetch>,
    );

    await waitFor(() => {
      expect(screen.getByText("New connectivity intent")).toBeInTheDocument();
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Advanced (canonical JSON)" }),
    );
    fireEvent.change(screen.getByLabelText("Canonical intent JSON"), {
      target: { value: "{ not valid json" },
    });

    // the live parse feedback is the inline error
    expect(screen.getByText(/Invalid JSON/)).toBeInTheDocument();

    // and the submit is blocked
    expect(screen.getByRole("button", { name: "Record intent" })).toBeDisabled();

    // no intent mutation was fired (only the session connect read)
    const intentCalls = fetchMock.mock.calls.filter(
      ([path]) => path === "/api/2.0/intents",
    );
    expect(intentCalls).toHaveLength(0);
  });
});

describe("Builder — the exact request", () => {
  it("always shows the POST /api/2.0/intents preview with the exact body and the form's idempotency key", async () => {
    const fetchMock = routeFetch({ ...APPLICATION_ROUTE });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<BuilderView />, fetchMock);

    await waitFor(() => {
      expect(screen.getByText("View API request")).toBeInTheDocument();
    });

    // the exact route
    expect(screen.getAllByText("/api/2.0/intents").length).toBeGreaterThan(0);
    expect(screen.getByText("POST /api/2.0/intents")).toBeInTheDocument();

    // the reproducible headers (the credential is deliberately absent)
    expect(screen.getByText("X-ADCOS-Application")).toBeInTheDocument();
    expect(
      screen.getByText(FIXTURE_APPLICATION.application_id),
    ).toBeInTheDocument();
    expect(screen.getByText("X-ADCOS-API-Version")).toBeInTheDocument();
    expect(screen.getByText("2.0")).toBeInTheDocument();

    // the idempotency key generated ONCE for this form instance
    const keyNode = screen.getByText(UUID_RE);
    expect(keyNode.textContent ?? "").toMatch(UUID_RE);

    // the exact serialized body (the canonical demo members)
    const body = displayedIntentBody();
    expect(body.requirements).toEqual([
      {
        ref_kind: "intent-requirements",
        value: "demo:intent-requirements:v1",
        provenance: {
          issuer: "intent-authority",
          decision_refs: ["demo:intent:v1"],
        },
      },
    ]);
    expect(body.validity).toEqual({
      not_before: "2026-09-14T00:00:00Z",
      not_after: "2026-10-14T00:00:00Z",
    });
    expect(body.termination).toEqual({
      conditions: ["principal-requested", "validity-expired"],
      compensation: { ref_kind: "compensation", value: "demo:compensation:v1" },
    });
    expect(body.hard_constraints).toEqual([
      { kind: "latency-bound", params: { ms: 100 } },
      { kind: "throughput-floor", params: { bps: 1000 } },
    ]);
    expect(body.beneficiaries).toEqual([
      { beneficiary_kind: "DEVICE", beneficiary_ref: "demo:device:v1" },
    ]);
    expect(body.usage_pricing_terms).toEqual({
      ref_kind: "usage-pricing-terms",
      value: "demo:usage-pricing:v1",
    });
  });

  it("routes to the new contract on success and sends exactly the previewed request", async () => {
    const fetchMock = trackedFetch({
      ...APPLICATION_ROUTE,
      "POST /api/2.0/intents": envelope(FIXTURE_CONTRACT_INTENT),
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(
      <BuilderView />,
      fetchMock as unknown as ReturnType<typeof routeFetch>,
    );

    await waitFor(() => {
      expect(screen.getByText("View API request")).toBeInTheDocument();
    });

    // the previewed key — the sent request must carry the SAME one
    const previewedKey = screen.getByText(UUID_RE).textContent ?? "";

    const previewedBody = displayedIntentBody();
    fireEvent.click(screen.getByRole("button", { name: "Record intent" }));

    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith(
        `/connectivity/contracts/${FIXTURE_CONTRACT_INTENT.id}`,
      );
    });

    // the sent request: method, path, body and the previewed idempotency key
    const intentCalls = fetchMock.mock.calls.filter(
      ([path, init]) =>
        path === "/api/2.0/intents" && init?.method === "POST",
    );
    expect(intentCalls).toHaveLength(1);
    const [, init] = intentCalls[0];
    expect(JSON.parse(String(init?.body))).toEqual(previewedBody);
    const headers = (init?.headers ?? {}) as Record<string, string>;
    expect(headers["X-ADCOS-Idempotency-Key"]).toBe(previewedKey);
    expect(headers["X-ADCOS-Application"]).toBe(FIXTURE_APPLICATION.application_id);
    expect(headers["X-ADCOS-API-Version"]).toBe("2.0");
  });

  it("surfaces the verbatim reason when the boundary rejects the body", async () => {
    const fetchMock = routeFetch({
      ...APPLICATION_ROUTE,
      "POST /api/2.0/intents": {
        __status: 400,
        body: INTENT_ERROR_MISSING_TERMINATION,
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithSession(<BuilderView />, fetchMock);

    await waitFor(() => {
      expect(screen.getByText("View API request")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Record intent" }));

    await waitFor(() => {
      expect(screen.getByTestId(ERROR_REASON_TEST_ID)).toHaveTextContent(
        "invalid-input",
      );
    });
    expect(
      screen.getByText(/request body is missing required member 'termination'/),
    ).toBeInTheDocument();

    // the request panel stays for correction + reproduction
    expect(screen.getByText("View API request")).toBeInTheDocument();
    expect(screen.getAllByText("/api/2.0/intents").length).toBeGreaterThan(0);
  });
});
