/**
 * Replan tests — the honest explainable surface:
 *
 * - the current-truth statement renders VERBATIM (this deployment exposes
 *   no replan decisions yet);
 * - the card-shape wireframe lists the seven fields with placeholder
 *   em-dashes only, behind the explicit "Structure preview" label;
 * - NO fabricated event data: no "failed over" / "handoff completed"
 *   claims, no timestamps and no Status dots inside the wireframe.
 */

import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { ReplanView } from "@/features/replan";

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

const WIREFRAME_LABELS = [
  "violated requirement",
  "observed vs required value",
  "detection time",
  "candidates",
  "eligibility/policy reasoning",
  "proposed action/state",
  "evidence links",
] as const;

describe("Replan view", () => {
  it("states the current truth VERBATIM", () => {
    render(<ReplanView />);
    expect(
      screen.getByText(
        "No replan decisions are exposed by this deployment yet. When the backend exposes them they will appear here.",
      ),
    ).toBeInTheDocument();
  });

  it("shows the card-shape wireframe: seven labeled fields, em-dashes only, behind the explicit preview label", () => {
    render(<ReplanView />);

    // the explicit label — this can never be mistaken for data
    expect(
      screen.getByText(
        "Structure preview — no replan events exist to render",
      ),
    ).toBeInTheDocument();

    const wireframe = screen.getByTestId("replan-wireframe");
    for (const label of WIREFRAME_LABELS) {
      expect(within(wireframe).getByText(label)).toBeInTheDocument();
    }
    // placeholder values are em-dashes (and the observed/required pair)
    expect(within(wireframe).getAllByText("—")).toHaveLength(6);
    expect(within(wireframe).getByText("— / —")).toBeInTheDocument();
  });

  it("fabricates NO event data anywhere on the page", () => {
    render(<ReplanView />);

    expect(screen.queryByText(/failed over/i)).toBeNull();
    expect(screen.queryByText(/handoff completed/i)).toBeNull();

    const wireframe = screen.getByTestId("replan-wireframe");
    // no timestamps inside the wireframe (em-dashes only)
    expect(
      within(wireframe).queryByText(/\d{4}-\d{2}-\d{2}T/),
    ).toBeNull();
    // no Status dots with real state values inside the wireframe
    expect(within(wireframe).queryByTestId("status-root")).toBeNull();
    expect(within(wireframe).queryByTestId("status-dot")).toBeNull();
    expect(
      within(wireframe).queryByText(
        /PLANNED|RESERVED|ACTIVATED|MEASURED|RELEASED|DEGRADED|CONTRACT_ACTIVE/,
      ),
    ).toBeNull();
  });

  it("explains what replanning is and what would trigger it (spec vocabulary)", () => {
    render(<ReplanView />);
    expect(screen.getByText("What replanning is")).toBeInTheDocument();
    expect(screen.getByText("What would trigger it")).toBeInTheDocument();
    expect(
      screen.getByText("A violated requirement or threshold"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Provider unavailability or degradation"),
    ).toBeInTheDocument();
    expect(screen.getByText("Validity-driven change")).toBeInTheDocument();
    // every trigger mentions the detection vocabulary honestly
    expect(screen.getAllByText(/detection time/i).length).toBeGreaterThan(0);
    // the way back to Fulfillment
    expect(screen.getByRole("link", { name: /← fulfillment/i })).toHaveAttribute(
      "href",
      "/fulfillment",
    );
  });
});
