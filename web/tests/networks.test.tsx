/**
 * Networks tests — REAL captured shapes only (tests/fixtures.ts), fetch
 * mocked at the global boundary through the shared harness. The demo
 * GET returns the RAW document (no envelope) — routed as the plain body.
 *
 * Covers the frozen UX spec's provider-boundary demands:
 * - the execution composition facts VERBATIM from the demonstration
 *   document (provider, adapter, access technology, standard
 *   mechanisms, sandbox position, SOFTWARE evidence class);
 * - the provider-topology boundary notice, with NO invented graph
 *   (no canvas, no oversized svg, no invented node names);
 * - the current-contract-use link to the demonstration contract;
 * - consumed backends with VERBATIM states/details (degraded variant)
 *   and the honest sandbox empty-backends note;
 * - the honest "not shown" section (no invented health metrics, no
 *   exposed eligibility lists).
 */

import { describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { NetworksView } from "@/features/networks";
import { EVIDENCE_BADGE_TEST_IDS } from "@/components/ui";
import {
  FIXTURE_DEMO_DOCUMENT,
  FIXTURE_READINESS,
  FIXTURE_READINESS_DEGRADED,
} from "./fixtures";
import { renderBare, routeFetch } from "./harness";

vi.mock("next/navigation", () => ({
  usePathname: () => "/networks",
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

describe("Networks — execution composition", () => {
  it("renders the composition facts VERBATIM from the demo document", async () => {
    const fetchMock = routeFetch({
      "GET /demo/contract-fulfillment": FIXTURE_DEMO_DOCUMENT,
      "GET /readyz": FIXTURE_READINESS,
    });
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<NetworksView />);

    await waitFor(() => {
      expect(
        screen.getByText("deterministic-reference-adapter"),
      ).toBeInTheDocument();
    });
    expect(
      screen.getByText("adcos:adapter:access.3gpp.nr.imt2020:bfa54a8cddce72a6"),
    ).toBeInTheDocument();
    expect(screen.getByText("access.3gpp.nr.imt2020")).toBeInTheDocument();
    // standard mechanisms, verbatim chips
    expect(screen.getByText("3gpp-nr")).toBeInTheDocument();
    expect(screen.getByText("oran-fronthaul-split")).toBeInTheDocument();
    // the sandbox position, stated plainly
    expect(screen.getByText("sandbox: true")).toBeInTheDocument();
    // the document's evidence class, visibly software-side
    const badge = screen.getByTestId(EVIDENCE_BADGE_TEST_IDS.root);
    expect(badge).toHaveTextContent("SOFTWARE");
    expect(badge).toHaveAttribute("data-kind", "software");
  });

  it("links the demonstration contract as current contract use", async () => {
    const fetchMock = routeFetch({
      "GET /demo/contract-fulfillment": FIXTURE_DEMO_DOCUMENT,
      "GET /readyz": FIXTURE_READINESS,
    });
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<NetworksView />);

    const contractId = String(FIXTURE_DEMO_DOCUMENT.contract.contract_id);
    await waitFor(() => {
      expect(screen.getByText(contractId)).toBeInTheDocument();
    });
    const link = screen
      .getAllByRole("link")
      .find(
        (candidate) =>
          candidate.getAttribute("href") === `/connectivity/contracts/${contractId}`,
      );
    expect(link).toBeDefined();
  });
});

describe("Networks — the provider-topology boundary", () => {
  it("states the boundary and renders NO invented graph", async () => {
    const fetchMock = routeFetch({
      "GET /demo/contract-fulfillment": FIXTURE_DEMO_DOCUMENT,
      "GET /readyz": FIXTURE_READINESS,
    });
    vi.stubGlobal("fetch", fetchMock);

    const { container } = renderBare(<NetworksView />);

    await waitFor(() => {
      expect(
        screen.getByText("deterministic-reference-adapter"),
      ).toBeInTheDocument();
    });

    // the boundary notice, in plain words
    expect(screen.getByText(/remains provider-owned/)).toBeInTheDocument();
    expect(
      screen.getByText(/does not expose a topology graph/),
    ).toBeInTheDocument();

    // NO fake graph: no canvas, and every svg on the page is a small
    // icon glyph (a topology graph would need far more than 16px)
    expect(container.querySelector("canvas")).toBeNull();
    const svgs = container.querySelectorAll("svg");
    expect(svgs.length).toBeGreaterThan(0); // icons are present…
    for (const svg of Array.from(svgs)) {
      expect(Number(svg.getAttribute("width"))).toBeLessThanOrEqual(16);
      expect(svg.getAttribute("aria-hidden")).toBe("true");
    }
    // no invented node names
    expect(screen.queryByText(/node-\d/)).toBeNull();
  });
});

describe("Networks — consumed backends", () => {
  it("renders the degraded readiness backends with VERBATIM states and details", async () => {
    const fetchMock = routeFetch({
      "GET /demo/contract-fulfillment": FIXTURE_DEMO_DOCUMENT,
      "GET /readyz": FIXTURE_READINESS_DEGRADED,
    });
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<NetworksView />);

    await waitFor(() => {
      expect(screen.getByText("neon-postgres")).toBeInTheDocument();
    });
    expect(screen.getByText("upstash-redis")).toBeInTheDocument();
    // the runtime's own state vocabulary, verbatim
    expect(screen.getByText("ready")).toBeInTheDocument();
    expect(screen.getByText("unavailable")).toBeInTheDocument();
    // the runtime's own detail lines, verbatim
    expect(screen.getByText("wired")).toBeInTheDocument();
    expect(
      screen.getByText(
        "connection refused (degraded — ephemeral coordination only)",
      ),
    ).toBeInTheDocument();
  });

  it("notes the sandbox empty-backends honestly when none are reported", async () => {
    const fetchMock = routeFetch({
      "GET /demo/contract-fulfillment": FIXTURE_DEMO_DOCUMENT,
      "GET /readyz": FIXTURE_READINESS,
    });
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<NetworksView />);

    await waitFor(() => {
      expect(
        screen.getByText("no durable backends (sandbox mode)"),
      ).toBeInTheDocument();
    });
  });
});

describe("Networks — honest absences", () => {
  it("keeps the not-shown section honest about metrics and eligibility", async () => {
    const fetchMock = routeFetch({
      "GET /demo/contract-fulfillment": FIXTURE_DEMO_DOCUMENT,
      "GET /readyz": FIXTURE_READINESS,
    });
    vi.stubGlobal("fetch", fetchMock);

    renderBare(<NetworksView />);

    await waitFor(() => {
      expect(screen.getByText("What this page does not show")).toBeInTheDocument();
    });
    expect(
      screen.getByText(
        /No provider health or performance metrics are exposed by this deployment/,
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/none are invented here/)).toBeInTheDocument();
    expect(
      screen.getByText(
        /the eligibility presentation for contracts lives on each contract's detail page/,
      ),
    ).toBeInTheDocument();
  });
});
