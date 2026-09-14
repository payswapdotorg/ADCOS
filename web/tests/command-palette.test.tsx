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
 * - the V2 Learn surfaces (DEC-0128, Task 7): the four new commands
 *   (nav-docs / nav-quickstart / nav-playbooks / nav-tour) appear in
 *   the palette alongside the eight V1 entries, and the sidebar renders
 *   the same entries in its Learn group — additions only, the expert
 *   V1 routes stay direct
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

    // empty query: all TWELVE navigation commands are visible — the
    // eight V1 expert entries plus the four V2 Learn entries
    const listbox = screen.getByRole("listbox", { name: "Results" });
    expect(within(listbox).getByRole("option", { name: "Home" })).toBeInTheDocument();
    expect(within(listbox).getByRole("option", { name: "Networks" })).toBeInTheDocument();
    expect(within(listbox).getAllByRole("option")).toHaveLength(12);

    // the four V2 Learn surfaces appear in the palette
    expect(within(listbox).getByRole("option", { name: "Docs" })).toBeInTheDocument();
    expect(within(listbox).getByRole("option", { name: "Quickstart" })).toBeInTheDocument();
    expect(within(listbox).getByRole("option", { name: "Playbooks" })).toBeInTheDocument();
    expect(within(listbox).getByRole("option", { name: "The tour" })).toBeInTheDocument();

    // typing a fuzzy Learn query isolates the new entry
    await user.type(input, "playb");
    expect(within(listbox).getAllByRole("option")).toHaveLength(1);
    expect(within(listbox).getByRole("option", { name: "Playbooks" })).toBeInTheDocument();
    expect(within(listbox).queryByRole("option", { name: "Home" })).toBeNull();

    // back to the empty query (every command visible again), then the
    // classic fuzzy filter
    await user.clear(input);
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
    expect(within(listbox).getAllByRole("option")).toHaveLength(13);

    // the recent row navigates to its href: walk the keyboard down to it
    // (the twelve commands come first, the recent row is thirteenth)
    const input = screen.getByRole("combobox", {
      name: "Search commands and objects",
    });
    for (let step = 0; step < 12; step += 1) {
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

  it("executes a V2 Learn command through the palette (Playbooks → /playbooks)", async () => {
    const user = userEvent.setup();
    renderShell();

    const input = await openPalette();
    await user.type(input, "playb");
    await user.keyboard("{Enter}");

    expect(pushMock).toHaveBeenCalledWith("/playbooks");
    await waitFor(() => {
      expect(screen.queryByRole("combobox")).toBeNull();
    });
  });
});

describe("Shell navigation — the V2 Learn surfaces (DEC-0128, Task 7)", () => {
  it("renders the Learn group in the sidebar with the four new entries", () => {
    renderShell();

    const nav = screen.getByRole("navigation", { name: "Primary" });

    // the eight V1 expert entries stay exactly where they were
    for (const label of [
      "Home",
      "Connectivity",
      "Networks",
      "Fulfillment",
      "Evidence",
      "Developers",
      "Assurance",
      "Settings",
    ]) {
      expect(within(nav).getByRole("link", { name: label })).toBeInTheDocument();
    }

    // the Learn group renders its label and the four new entries
    expect(within(nav).getByText("Learn")).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Docs" })).toHaveAttribute("href", "/docs");
    expect(within(nav).getByRole("link", { name: "Quickstart" })).toHaveAttribute(
      "href",
      "/quickstart",
    );
    expect(within(nav).getByRole("link", { name: "Playbooks" })).toHaveAttribute(
      "href",
      "/playbooks",
    );
    expect(within(nav).getByRole("link", { name: "The tour" })).toHaveAttribute(
      "href",
      "/tour",
    );

    // twelve nav links total — additions only, nothing removed
    expect(within(nav).getAllByRole("link")).toHaveLength(12);

    // no forced onboarding: at "/" only Home is the current page
    const current = within(nav)
      .getAllByRole("link")
      .filter((link) => link.getAttribute("aria-current") === "page");
    expect(current).toHaveLength(1);
    expect(current[0]).toHaveAccessibleName("Home");
  });
});
