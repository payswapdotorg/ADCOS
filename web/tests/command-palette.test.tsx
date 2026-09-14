/**
 * Command palette tests — the palette against the REAL providers, with
 * next/navigation, next/link and fetch mocked. NO network, ever.
 *
 * Covers:
 * - Cmd+K toggles the palette open (combobox appears)
 * - the top-bar trigger opens the SAME palette state
 * - fuzzy filtering ("netw" → Networks, others excluded)
 * - ArrowDown + Enter executes the active item (router.push "/networks")
 *   and closes the palette
 * - Escape closes
 * - seeded recent objects render under the "Recent" section
 * - executing a navigation command self-feeds the recents store
 */

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/shell/app-shell";
import { SessionProvider } from "@/lib/session";
import { ThemeProvider } from "@/lib/design/theme";
import {
  __resetCommandRegistryForTests,
  __resetRecentObjectsForTests,
  addRecent,
} from "@/features/search";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({
    push: pushMock,
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

const READYZ = {
  ok: true,
  service: "adcos-runtime",
  mode: "sandbox",
  environment: "sandbox",
  backends: {},
};

function jsonResponse(body: unknown, status = 200) {
  return {
    status,
    ok: status >= 200 && status < 300,
    headers: {
      get: (name: string) =>
        name.toLowerCase() === "content-type" ? "application/json" : null,
    },
    text: async () => JSON.stringify(body),
  };
}

const fetchMock = vi.fn(async (input: unknown) => jsonResponse(READYZ));

function renderShell() {
  return render(
    <ThemeProvider>
      <SessionProvider>
        <AppShell>
          <p>shell content</p>
        </AppShell>
      </SessionProvider>
    </ThemeProvider>,
  );
}

async function openPalette(): Promise<HTMLInputElement> {
  fireEvent.keyDown(window, { key: "k", metaKey: true });
  return screen.findByRole("combobox", {
    name: "Search commands and objects",
  }) as Promise<HTMLInputElement>;
}

beforeAll(() => {
  Object.defineProperty(window.Element.prototype, "scrollIntoView", {
    value: vi.fn(),
    configurable: true,
  });
  Object.defineProperty(window.Element.prototype, "hasPointerCapture", {
    value: vi.fn(() => false),
    configurable: true,
  });
  Object.defineProperty(window.Element.prototype, "releasePointerCapture", {
    value: vi.fn(),
    configurable: true,
  });
});

beforeEach(() => {
  pushMock.mockClear();
  fetchMock.mockClear();
  fetchMock.mockImplementation(async (input: unknown) => jsonResponse(READYZ));
  vi.stubGlobal("fetch", fetchMock);
  __resetCommandRegistryForTests();
  __resetRecentObjectsForTests();
});

afterEach(() => {
  cleanup();
});

describe("CommandPalette", () => {
  it("opens on Cmd+K, filters with the fuzzy matcher, and executes with ArrowDown + Enter", async () => {
    const user = userEvent.setup();
    renderShell();

    const input = await openPalette();
    expect(input).toBeInTheDocument();

    // empty query: all eight navigation commands are visible
    const listbox = screen.getByRole("listbox", { name: "Results" });
    expect(within(listbox).getByRole("option", { name: "Home" })).toBeInTheDocument();
    expect(within(listbox).getByRole("option", { name: "Networks" })).toBeInTheDocument();
    expect(within(listbox).getAllByRole("option")).toHaveLength(8);

    // type a fuzzy query
    await user.type(input, "netw");

    // only Networks survives the filter
    expect(within(listbox).getByRole("option", { name: "Networks" })).toBeInTheDocument();
    expect(within(listbox).queryByRole("option", { name: "Home" })).toBeNull();
    expect(within(listbox).getAllByRole("option")).toHaveLength(1);

    // keyboard execution: ArrowDown (wraps onto the single item) + Enter
    await user.keyboard("{ArrowDown}");
    await user.keyboard("{Enter}");

    expect(pushMock).toHaveBeenCalledWith("/networks");
    await waitFor(() => {
      expect(screen.queryByRole("combobox")).toBeNull();
    });
  });

  it("self-feeds the recents store after executing a navigation command", async () => {
    const user = userEvent.setup();
    renderShell();

    const input = await openPalette();
    await user.type(input, "netw");
    await user.keyboard("{Enter}");

    expect(pushMock).toHaveBeenCalledWith("/networks");

    // reopen: the executed route now appears under "Recent"
    const reopened = await openPalette();
    const listbox = screen.getByRole("listbox", { name: "Results" });
    expect(within(listbox).getByText("Recent")).toBeInTheDocument();
    const networksRows = within(listbox).getAllByText("Networks");
    expect(networksRows).toHaveLength(2); // the command + the recent route

    // Escape closes the palette
    await user.type(reopened, "{Escape}");
    await waitFor(() => {
      expect(screen.queryByRole("combobox")).toBeNull();
    });
  });

  it("opens from the top-bar trigger through the shared open state", async () => {
    const user = userEvent.setup();
    renderShell();

    await user.click(screen.getByRole("button", { name: "Open command palette" }));

    const input = await screen.findByRole("combobox", {
      name: "Search commands and objects",
    });
    expect(input).toBeInTheDocument();
    expect(screen.getByRole("listbox", { name: "Results" })).toBeInTheDocument();
  });

  it("shows a seeded recent object under the Recent section with an empty query", async () => {
    addRecent({
      kind: "route",
      id: "/evidence",
      label: "Evidence",
      href: "/evidence",
      at: "2026-09-14T00:00:00Z",
    });

    renderShell();
    await openPalette();

    const listbox = screen.getByRole("listbox", { name: "Results" });
    expect(within(listbox).getByText("Recent")).toBeInTheDocument();
    // the navigation command AND the seeded recent both carry the label
    expect(within(listbox).getAllByRole("option", { name: "Evidence" })).toHaveLength(2);
    expect(within(listbox).getAllByRole("option")).toHaveLength(9);

    // the recent row navigates to its href: walk the keyboard down to it
    // (the eight commands come first, the recent row is ninth)
    const input = screen.getByRole("combobox", {
      name: "Search commands and objects",
    });
    for (let step = 0; step < 8; step += 1) {
      fireEvent.keyDown(input, { key: "ArrowDown" });
    }
    fireEvent.keyDown(input, { key: "Enter" });

    expect(pushMock).toHaveBeenCalledWith("/evidence");
    await waitFor(() => {
      expect(screen.queryByRole("combobox")).toBeNull();
    });
  });

  it("shows the No matches line when nothing matches", async () => {
    const user = userEvent.setup();
    renderShell();

    const input = await openPalette();
    await user.type(input, "zzzz");

    expect(screen.getByText("No matches")).toBeInTheDocument();
    expect(screen.queryByRole("option")).toBeNull();
  });
});
