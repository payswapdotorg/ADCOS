import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  ApiRequestPanel,
  buildCurl,
} from "@/components/ui/api-request-panel";

describe("buildCurl", () => {
  it("renders a bodyless GET exactly", () => {
    expect(buildCurl({ method: "GET", path: "/api/2.0/intents" })).toBe(
      "curl -X GET '/api/2.0/intents'",
    );
  });

  it("includes every header on its own -H line plus the compact body", () => {
    const curl = buildCurl({
      method: "POST",
      path: "/api/2.0/contracts/c1/intents",
      headers: [
        { name: "X-ADCOS-Application", value: "sha256:abc" },
        { name: "Content-Type", value: "application/json" },
      ],
      body: { a: 1 },
    });
    expect(curl).toContain("curl -X POST '/api/2.0/contracts/c1/intents'");
    expect(curl).toContain("-H 'Content-Type: application/json'");
    expect(curl).toContain("-H 'X-ADCOS-Application: sha256:abc'");
    expect(curl).toContain(`--data-raw '{"a":1}'`);
    // Content-Type is pinned first, the rest sorted by name
    expect(curl.indexOf("Content-Type")).toBeLessThan(
      curl.indexOf("X-ADCOS-Application"),
    );
  });

  it("adds Content-Type when a body is present without one", () => {
    const curl = buildCurl({
      method: "POST",
      path: "/api/2.0/leases",
      body: { b: 2 },
    });
    expect(curl).toContain("-H 'Content-Type: application/json'");
    expect(curl).toContain(`--data-raw '{"b":2}'`);
  });

  it("escapes single quotes inside the serialized body", () => {
    const curl = buildCurl({
      method: "POST",
      path: "/api/2.0/intents",
      body: { note: "it's" },
    });
    expect(curl).toContain(`--data-raw '{"note":"it\\'s"}'`);
  });
});

describe("ApiRequestPanel", () => {
  it("renders the method chip, path, headers grid, body and curl block", () => {
    render(
      <ApiRequestPanel
        method="POST"
        path="/api/2.0/contracts/c1/intents"
        headers={[{ name: "X-ADCOS-Application", value: "sha256:abc" }]}
        body={{ a: 1 }}
        description="Record a new intent"
      />,
    );
    expect(screen.getByText("POST")).toBeInTheDocument();
    expect(screen.getByText("/api/2.0/contracts/c1/intents")).toBeInTheDocument();
    expect(screen.getByText("X-ADCOS-Application")).toBeInTheDocument();
    expect(screen.getByText("sha256:abc")).toBeInTheDocument();
    expect(screen.getByText("Record a new intent")).toBeInTheDocument();
    // body renders through JsonViewer
    expect(screen.getByText("a:")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
    // curl reproduction block with its copy affordance
    expect(screen.getByText("bash")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy code" })).toBeInTheDocument();
  });

  it("renders a string body through CodeBlock instead of JsonViewer", () => {
    render(
      <ApiRequestPanel method="POST" path="/api/2.0/echo" body="raw-payload" />,
    );
    expect(screen.getByText("raw-payload")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Copy JSON" })).not.toBeInTheDocument();
  });

  it("compact variant renders method, path and the copy-curl button", async () => {
    const user = userEvent.setup();
    // fresh clipboard mock installed AFTER setup (userEvent installs
    // its own navigator.clipboard stub during setup())
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    render(
      <ApiRequestPanel variant="compact" method="GET" path="/api/2.0/intents" />,
    );
    expect(screen.getByText("GET")).toBeInTheDocument();
    expect(screen.getByText("/api/2.0/intents")).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Copy curl command" }),
    );
    expect(writeText).toHaveBeenCalledWith(
      "curl -X GET '/api/2.0/intents'",
    );
  });

  it("compact variant hides headers, body and the curl block", () => {
    render(
      <ApiRequestPanel
        variant="compact"
        method="POST"
        path="/api/2.0/leases"
        headers={[{ name: "X-ADCOS-Application", value: "sha256:abc" }]}
        body={{ a: 1 }}
      />,
    );
    expect(screen.queryByText("X-ADCOS-Application")).not.toBeInTheDocument();
    expect(screen.queryByText("bash")).not.toBeInTheDocument();
    expect(screen.queryByText("a:")).not.toBeInTheDocument();
  });
});
