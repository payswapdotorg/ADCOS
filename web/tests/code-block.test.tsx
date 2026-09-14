import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CodeBlock } from "@/components/ui/code-block";

/**
 * userEvent.setup() installs its own navigator.clipboard stub which
 * displaces any earlier vi.fn — so the fresh mock is installed AFTER
 * setup, right before render.
 */
function stubClipboardWriteText(behavior: "resolve" | "reject") {
  const writeText =
    behavior === "resolve"
      ? vi.fn().mockResolvedValue(undefined)
      : vi.fn().mockRejectedValue(new Error("denied"));
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText },
    configurable: true,
  });
  return writeText;
}

describe("CodeBlock", () => {
  it("renders the code with the language label", () => {
    render(<CodeBlock code={'curl -X GET "/healthz"'} language="bash" />);
    expect(screen.getByText('curl -X GET "/healthz"')).toBeInTheDocument();
    expect(screen.getByText("bash")).toBeInTheDocument();
  });

  it("renders the filename when provided", () => {
    render(<CodeBlock code="x" filename="request.json" />);
    expect(screen.getByText("request.json")).toBeInTheDocument();
  });

  it("copies the code via the clipboard", async () => {
    const user = userEvent.setup();
    const writeText = stubClipboardWriteText("resolve");
    render(<CodeBlock code={'{"a":1}'} language="json" />);
    await user.click(screen.getByRole("button", { name: "Copy code" }));
    expect(writeText).toHaveBeenCalledWith('{"a":1}');
  });

  it("does not throw when the clipboard is unavailable", async () => {
    const user = userEvent.setup();
    const writeText = stubClipboardWriteText("reject");
    render(<CodeBlock code="abc" />);
    await user.click(screen.getByRole("button", { name: "Copy code" }));
    expect(writeText).toHaveBeenCalledWith("abc");
  });
});
