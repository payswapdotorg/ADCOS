import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  EVIDENCE_BADGE_TEST_IDS,
  EvidenceBadge,
} from "@/components/ui/evidence-badge";

const badge = () => screen.getByTestId(EVIDENCE_BADGE_TEST_IDS.root);

describe("EvidenceBadge", () => {
  it("renders SOFTWARE with the dashed software treatment and verbatim label", () => {
    render(<EvidenceBadge evidenceClass="SOFTWARE" />);
    const element = badge();
    expect(element).toHaveAttribute("data-kind", "software");
    expect(element.className).toContain("border-dashed");
    expect(element.className).toContain("border-warning");
    // SOFTWARE must never carry the physical marker styling
    expect(element.className).not.toContain("border-solid");
    expect(element.className).not.toContain("border-line-strong");
    expect(screen.getByText("SOFTWARE")).toBeInTheDocument();
    expect(element.querySelector("svg")).toBeInTheDocument(); // TerminalIcon
  });

  it("renders a physical/network class with the SOLID physical treatment", () => {
    render(<EvidenceBadge evidenceClass="network-probe" />);
    const element = badge();
    expect(element).toHaveAttribute("data-kind", "physical");
    expect(element.className).toContain("border-solid");
    expect(element.className).toContain("border-line-strong");
    expect(element.className).not.toContain("border-dashed");
    expect(element.className).not.toContain("border-warning");
    expect(screen.getByText("network-probe")).toBeInTheDocument();
    expect(element.querySelector("svg")).toBeInTheDocument(); // ShieldIcon
  });

  it("classifies sandbox-simulation as the software family (never physical)", () => {
    render(<EvidenceBadge evidenceClass="sandbox-simulation" />);
    const element = badge();
    expect(element).toHaveAttribute("data-kind", "software");
    expect(element.className).toContain("border-dashed");
    expect(element.className).toContain("border-warning");
    // the physical marker is absent — the distinction is glanceable
    expect(element.className).not.toContain("border-solid");
    expect(element.getAttribute("data-kind")).not.toBe("physical");
    expect(screen.getByText("sandbox-simulation")).toBeInTheDocument();
  });

  it("renders unrecognized classes as unknown (muted dashed, question mark)", () => {
    render(<EvidenceBadge evidenceClass="not-claimed" />);
    const element = badge();
    expect(element).toHaveAttribute("data-kind", "unknown");
    expect(element.className).toContain("border-dashed");
    expect(element.className).toContain("border-line");
    expect(element.className).not.toContain("border-warning");
    expect(screen.getByText("not-claimed")).toBeInTheDocument();
    expect(screen.getByText("?")).toBeInTheDocument();
  });

  it("explains the class family in a title attribute", () => {
    render(<EvidenceBadge evidenceClass="SOFTWARE" />);
    const title = badge().getAttribute("title") ?? "";
    expect(title).toContain("Software");
    expect(title).toContain("SOFTWARE");
  });

  it("hides the label but keeps the family distinction when showLabel is false", () => {
    render(<EvidenceBadge evidenceClass="SOFTWARE" showLabel={false} />);
    expect(screen.queryByText("SOFTWARE")).not.toBeInTheDocument();
    expect(badge()).toHaveAttribute("data-kind", "software");
  });
});
