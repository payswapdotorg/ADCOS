import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { JsonViewer } from "@/components/ui/json-viewer";

const value = {
  name: "intent-1",
  params: { limit: 20, cursor: null },
  items: ["a", "b"],
};

describe("JsonViewer", () => {
  it("renders nested objects as collapsible nodes", async () => {
    const user = userEvent.setup();
    render(<JsonViewer value={value} name="payload" defaultExpandedDepth={0} />);

    // root starts collapsed: nested members are absent
    const rootToggle = screen.getByRole("button", { name: "Toggle payload" });
    expect(rootToggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("name:")).not.toBeInTheDocument();

    await user.click(rootToggle);
    expect(rootToggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("name:")).toBeInTheDocument();
    expect(screen.getByText('"intent-1"')).toBeInTheDocument();

    // the nested object is itself collapsed until toggled
    expect(screen.queryByText("limit:")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Toggle params" }));
    expect(screen.getByText("limit:")).toBeInTheDocument();
    expect(screen.getByText("20")).toBeInTheDocument();
    expect(screen.getByText("null")).toBeInTheDocument();

    // arrays collapse too
    await user.click(screen.getByRole("button", { name: "Toggle items" }));
    expect(screen.getByText('"a"')).toBeInTheDocument();
    expect(screen.getByText('"b"')).toBeInTheDocument();
  });

  it("copies the pretty-printed JSON from the top-level button", async () => {
    const user = userEvent.setup();
    // fresh clipboard mock installed AFTER setup (userEvent installs
    // its own navigator.clipboard stub during setup())
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    render(<JsonViewer value={value} />);
    await user.click(screen.getByRole("button", { name: "Copy JSON" }));
    expect(writeText).toHaveBeenCalledWith(JSON.stringify(value, null, 2));
  });

  it("colors primitives by kind while staying calm", () => {
    render(
      <JsonViewer
        value={{ n: 20, b: true, z: null, s: "x" }}
        defaultExpandedDepth={2}
      />,
    );
    expect(screen.getByText("20").className).toContain("text-accent");
    expect(screen.getByText("true").className).toContain("text-warning");
    expect(screen.getByText("null").className).toContain("text-warning");
    expect(screen.getByText('"x"').className).toContain("text-ink");
    expect(screen.getByText("n:").className).toContain("text-ink-faint");
  });

  it("renders empty containers inline and primitives at the root", () => {
    const { rerender } = render(<JsonViewer value={{ empty: {} }} />);
    expect(screen.getByText("{}")).toBeInTheDocument();
    rerender(<JsonViewer value={42} name="count" />);
    expect(screen.getByText("42")).toBeInTheDocument();
  });
});
