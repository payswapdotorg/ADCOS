import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Drawer } from "@/components/ui/drawer";

describe("Drawer", () => {
  it("renders title, description and body when open", () => {
    render(
      <Drawer
        open
        onOpenChange={() => {}}
        title="Contract details"
        description="The full contract record"
      >
        lease body
      </Drawer>,
    );
    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(screen.getByText("Contract details")).toBeInTheDocument();
    expect(screen.getByText("The full contract record")).toBeInTheDocument();
    expect(screen.getByText("lease body")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Close panel" }),
    ).toBeInTheDocument();
  });

  it("renders nothing when closed", () => {
    render(
      <Drawer open={false} onOpenChange={() => {}} title="Hidden">
        body
      </Drawer>,
    );
    expect(screen.queryByText("Hidden")).not.toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes on Escape by calling onOpenChange(false)", async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    render(
      <Drawer open onOpenChange={onOpenChange} title="Panel">
        content
      </Drawer>,
    );
    await user.keyboard("{Escape}");
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("focus lands inside the panel and stays trapped there", async () => {
    const user = userEvent.setup();
    render(
      <Drawer open onOpenChange={() => {}} title="Panel">
        content
      </Drawer>,
    );
    const dialog = screen.getByRole("dialog");
    // Radix focuses the first focusable element on open
    expect(dialog.contains(document.activeElement)).toBe(true);
    // tabbing cycles within the dialog (focus trap)
    await user.tab();
    expect(dialog.contains(document.activeElement)).toBe(true);
    await user.tab();
    expect(dialog.contains(document.activeElement)).toBe(true);
  });
});
