import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
// the barrel is exercised here on purpose: Workers 2/3 import from "@/components/ui"
import { Status, STATUS_TEST_IDS } from "@/components/ui";
import { Status as StatusDirect } from "@/components/ui/status";

describe("Status", () => {
  it("renders backend state values VERBATIM with their tone", () => {
    const { rerender } = render(<Status value="CONTRACT_ACTIVE" />);
    expect(screen.getByText("CONTRACT_ACTIVE")).toBeInTheDocument();
    expect(screen.getByTestId(STATUS_TEST_IDS.root)).toHaveAttribute(
      "data-tone",
      "positive",
    );

    rerender(<Status value="renewed" />);
    expect(screen.getByText("renewed")).toBeInTheDocument();
    expect(screen.getByTestId(STATUS_TEST_IDS.root)).toHaveAttribute(
      "data-tone",
      "positive",
    );

    rerender(<Status value="revoked" />);
    expect(screen.getByText("revoked")).toBeInTheDocument();
    expect(screen.getByTestId(STATUS_TEST_IDS.root)).toHaveAttribute(
      "data-tone",
      "danger",
    );
  });

  it("renders INTENT as a neutral tone, still verbatim", () => {
    render(<Status value="INTENT" />);
    expect(screen.getByText("INTENT")).toBeInTheDocument();
    expect(screen.getByTestId(STATUS_TEST_IDS.root)).toHaveAttribute(
      "data-tone",
      "neutral",
    );
  });

  it("renders unknown values with a hollow dashed dot and the verbatim text", () => {
    render(<Status value="unknown-string" />);
    expect(screen.getByText("unknown-string")).toBeInTheDocument();
    expect(screen.getByTestId(STATUS_TEST_IDS.root)).toHaveAttribute(
      "data-tone",
      "unknown",
    );
    expect(screen.getByTestId(STATUS_TEST_IDS.dot).className).toContain(
      "border-dashed",
    );
  });

  it("renders null as the unknown tone with no label", () => {
    render(<Status value={null} />);
    expect(screen.getByTestId(STATUS_TEST_IDS.root)).toHaveAttribute(
      "data-tone",
      "unknown",
    );
    expect(
      screen.queryByTestId(STATUS_TEST_IDS.label),
    ).not.toBeInTheDocument();
  });

  it("is importable both directly and through the barrel", () => {
    render(<StatusDirect value="active" size="sm" />);
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByTestId(STATUS_TEST_IDS.root)).toHaveAttribute(
      "data-tone",
      "positive",
    );
  });
});
