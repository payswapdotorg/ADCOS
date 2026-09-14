import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AdcosApiError } from "@/lib/api/errors";
import {
  ERROR_REASON_TEST_ID,
  ErrorState,
} from "@/components/ui/error-state";

function makeError(
  reason: string,
  message: string,
  request: { method: string; path: string; body?: unknown } = {
    method: "GET",
    path: "/api/2.0/application",
  },
) {
  return new AdcosApiError({
    status: 400,
    reason,
    message,
    request,
  });
}

describe("ErrorState", () => {
  it("shows the backend reason code VERBATIM in a mono chip", () => {
    render(
      <ErrorState
        error={makeError(
          "authentication-invalid",
          "credential rejected by the boundary",
        )}
      />,
    );
    const chip = screen.getByTestId(ERROR_REASON_TEST_ID);
    expect(chip).toHaveTextContent(/^authentication-invalid$/);
    expect(chip.className).toContain("font-mono");
    expect(screen.getByText("Authentication failed")).toBeInTheDocument();
    expect(
      screen.getByText("credential rejected by the boundary"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Check the application ID and credential/),
    ).toBeInTheDocument();
    expect(screen.getByText("Next:")).toBeInTheDocument();
  });

  it("shows invalid-transition verbatim with its next action", () => {
    render(
      <ErrorState
        error={makeError(
          "invalid-transition",
          "contract is not in a state that allows this command",
          { method: "POST", path: "/api/2.0/contracts/c1/termination" },
        )}
      />,
    );
    expect(screen.getByTestId(ERROR_REASON_TEST_ID)).toHaveTextContent(
      /^invalid-transition$/,
    );
    expect(screen.getByText("Invalid state transition")).toBeInTheDocument();
    expect(
      screen.getByText(/Refresh to see its current state/),
    ).toBeInTheDocument();
  });

  it("renders the failed request descriptor and a working Retry button", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(
      <ErrorState
        error={makeError("resource-unknown", "no such contract", {
          method: "GET",
          path: "/api/2.0/contracts/missing",
        })}
        onRetry={onRetry}
      />,
    );
    expect(screen.getByText("/api/2.0/contracts/missing")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /retry/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("uses the request prop when the error is not an AdcosApiError", () => {
    render(
      <ErrorState
        error={new Error("boom")}
        request={{ method: "POST", path: "/api/2.0/leases" }}
      />,
    );
    expect(screen.getByText("/api/2.0/leases")).toBeInTheDocument();
    expect(screen.getByTestId(ERROR_REASON_TEST_ID)).toHaveTextContent(
      /^ui-error$/,
    );
  });

  it("surfaces retryable / retry_after hints when the backend sent them", () => {
    const error = new AdcosApiError({
      status: 429,
      reason: "rate-limited",
      message: "too many requests",
      retryable: true,
      retryAfter: "2026-01-01T00:00:05Z",
      requestId: "req-123",
      request: { method: "GET", path: "/api/2.0/contracts" },
    });
    render(<ErrorState error={error} />);
    expect(screen.getByText(/retryable: true/)).toBeInTheDocument();
    expect(screen.getByText(/retry_after: 2026-01-01T00:00:05Z/)).toBeInTheDocument();
    expect(screen.getByText(/request_id: req-123/)).toBeInTheDocument();
  });
});
