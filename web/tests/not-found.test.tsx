import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ERROR_REASON_TEST_ID } from "@/components/ui/error-state";
import NotFound from "@/app/not-found";
import UnmatchedPage from "@/app/[...unmatched]/page";

/**
 * The console-space not-found contract.
 *
 * The deployed routing topology (root vercel.json: the Python runtime owns
 * `/api/*`, `/healthz`, `/readyz`, `/demo/*`; the console owns everything
 * else) funnels every unmatched console-space path through the
 * `[...unmatched]` catch-all into the not-found boundary. That boundary
 * presents the miss with the backend's OWN unknown-route reason
 * (`route-unknown` — developerapi/errors.py ROUTE_UNKNOWN), VERBATIM — the
 * console's one-vocabulary discipline: no invented error surfaces.
 */

// notFound() throws Next's internal boundary signal; the mock makes the
// signal observable without the Next router machinery. (The not-found
// boundary itself imports next/navigation nowhere, so the mock is inert
// for the first describe block.)
const NOT_FOUND_BOUNDARY_SIGNAL = "NOT_FOUND_BOUNDARY_SIGNAL";
vi.mock("next/navigation", () => ({
  notFound: () => {
    throw new Error(NOT_FOUND_BOUNDARY_SIGNAL);
  },
}));

describe("not-found boundary", () => {
  it("renders the miss with the backend's route-unknown reason VERBATIM", () => {
    render(<NotFound />);

    expect(screen.getByText("Page not found")).toBeInTheDocument();
    // the miss is stated in the boundary's own words (intro + error detail)
    expect(
      screen.getAllByText("No console route matches this path.").length,
    ).toBeGreaterThanOrEqual(1);
    // the reason chip is the backend vocabulary, verbatim, in mono
    const chip = screen.getByTestId(ERROR_REASON_TEST_ID);
    expect(chip).toHaveTextContent(/^route-unknown$/);
    expect(chip.className).toContain("font-mono");
    // the way home is one link away
    expect(
      screen.getByRole("link", { name: "Home" }).getAttribute("href"),
    ).toBe("/");
  });
});

describe("[...unmatched] catch-all route", () => {
  it("triggers the not-found boundary — it renders nothing of its own", () => {
    expect(() => render(<UnmatchedPage />)).toThrow(
      NOT_FOUND_BOUNDARY_SIGNAL,
    );
  });
});
