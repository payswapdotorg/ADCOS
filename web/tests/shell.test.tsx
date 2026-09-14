/**
 * Shell tests — the app shell against the REAL providers (theme, session)
 * with next/navigation, next/link, and fetch mocked at the module/global
 * boundary. NO network, ever.
 *
 * @radix-ui/react-dropdown-menu is mocked with a deterministic stub:
 * the real Radix DropdownMenu drives floating-ui `autoUpdate` while open,
 * which starves jsdom's event loop for ~15s per open (measured; the REAL
 * Radix Dialog primitives — Drawer, ConnectDialog, CommandPalette — run
 * fast and are exercised for real in their own suites). The stub keeps
 * the SessionMenu semantics under test: trigger → items → onSelect.
 *
 * Covers:
 * - all 8 primary nav entries render
 * - the environment indicator surfaces the REAL /readyz values
 * - the connect flow: dialog → GET /api/2.0/application with the exact
 *   auth headers (X-ADCOS-Application / X-ADCOS-Credential /
 *   X-ADCOS-API-Version "2.0") → the application name in the trigger
 * - disconnect clears the session
 * - the failure flow: 401 authentication-invalid shown VERBATIM
 */

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { AppShell } from "@/components/shell/app-shell";
import { SessionProvider } from "@/lib/session";
import { ThemeProvider } from "@/lib/design/theme";
import { __resetRequestLogForTests } from "@/features/requests/request-log";

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

vi.mock("@radix-ui/react-dropdown-menu", async () => {
  const React = await import("react");
  const { createContext, cloneElement, useContext, useState } = React;
  type MenuState = { open: boolean; setOpen: (open: boolean) => void };
  const MenuContext = createContext<MenuState>({ open: false, setOpen: () => {} });

  const Root = ({ children }: { children?: ReactNode }) => {
    const [open, setOpen] = useState(false);
    return <MenuContext.Provider value={{ open, setOpen }}>{children}</MenuContext.Provider>;
  };

  const Trigger = ({ children }: { children?: ReactNode }) => {
    const { setOpen } = useContext(MenuContext);
    const child = Array.isArray(children) ? children[0] : children;
    if (!React.isValidElement(child)) return <>{children}</>;
    return cloneElement(child as React.ReactElement<Record<string, unknown>>, {
      onClick: (event: React.MouseEvent) => {
        (child.props as { onClick?: (e: React.MouseEvent) => void }).onClick?.(event);
        setOpen(true);
      },
    });
  };

  const Portal = ({ children }: { children?: ReactNode }) => <>{children}</>;

  const Content = ({ children }: { children?: ReactNode }) => {
    const { open } = useContext(MenuContext);
    if (!open) return null;
    return <div role="menu">{children}</div>;
  };

  const Item = ({
    children,
    onSelect,
    className,
  }: {
    children?: ReactNode;
    onSelect?: (event: unknown) => void;
    className?: string;
  }) => {
    const { setOpen } = useContext(MenuContext);
    return (
      <div
        role="menuitem"
        className={className}
        onClick={(event) => {
          onSelect?.(event);
          setOpen(false); // the real menu closes on select
        }}
      >
        {children}
      </div>
    );
  };

  const Separator = () => <div className="radix-separator" />;

  return {
    Root,
    Trigger,
    Portal,
    Content,
    Item,
    Separator,
  };
});

/* ------------------------------------------------------------------ */
/* fixtures (shapes from the REAL captures — never invented)          */
/* ------------------------------------------------------------------ */

const APPLICATION = {
  application_id: "sha256:c20c5f90db52d8a89c5168fdb71f522ed9648d1264330357a9cdad98532f1f01",
  application_name: "Sandbox Demo Application",
  capabilities: ["contracts:read", "contracts:write", "leases:read", "leases:write"],
  developer_id: "dev_demo",
  environment: "sandbox",
  evidence_class: "sandbox-simulation",
  issued_at: "2026-09-14T00:00:00Z",
  kind: "application",
  status: "active",
  valid_until: "2027-01-01T00:00:00Z",
} as const;

const APPLICATION_ENVELOPE = {
  api_version: "2.0",
  environment: "sandbox",
  request_id: "req_application_self",
  data: APPLICATION,
  idempotency: { key: "idem_1", replayed: false },
  rate_limit: { limit: 60, remaining: 59, reset_at: "2026-09-14T12:00:00Z" },
};

const READYZ = {
  ok: true,
  service: "adcos-runtime",
  mode: "sandbox",
  environment: "sandbox",
  backends: {},
};

const AUTHENTICATION_INVALID = {
  api_version: "2.0",
  environment: "sandbox",
  request_id: "req_failed_auth",
  error: {
    canonical_reason: "",
    environment: "sandbox",
    http_status: 401,
    message: "The application credential was rejected by the boundary",
    reason: "authentication-invalid",
    request_id: "req_failed_auth",
    resource_id: "",
    retry_after: "",
    retryable: false,
  },
};

/* ------------------------------------------------------------------ */
/* fetch mock — routed, no network                                     */
/* ------------------------------------------------------------------ */

/** Minimal Response stand-in (jsdom has no fetch/Response). */
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

let applicationStatus = 200;
let applicationBody: unknown = APPLICATION_ENVELOPE;

const fetchMock = vi.fn();

async function routeFetch(input: unknown): Promise<unknown> {
  const url = typeof input === "string" ? input : String(input);
  if (url === "/readyz") return jsonResponse(READYZ);
  if (url === "/api/2.0/application") {
    return jsonResponse(applicationBody, applicationStatus);
  }
  return jsonResponse(
    { error: { reason: "route-unknown", message: `unexpected fetch ${url}` } },
    404,
  );
}

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

beforeAll(() => {
  // jsdom gaps exercised by Radix portals
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
  applicationStatus = 200;
  applicationBody = APPLICATION_ENVELOPE;
  // re-armed every test (setup.ts restores mocks after each)
  fetchMock.mockImplementation(routeFetch);
  vi.stubGlobal("fetch", fetchMock);
  __resetRequestLogForTests();
});

afterEach(() => {
  cleanup();
});

// local import to keep the mock factories above self-contained
import { cleanup } from "@testing-library/react";

/* ------------------------------------------------------------------ */

describe("AppShell", () => {
  it("renders all eight primary navigation entries", () => {
    renderShell();

    const nav = screen.getByRole("navigation", { name: "Primary" });
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
      const link = within(nav).getByRole("link", { name: label });
      expect(link).toBeVisible();
    }
    expect(within(nav).getByRole("link", { name: "Home" })).toHaveAttribute("href", "/");
    expect(within(nav).getByRole("link", { name: "Home" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("marks the active route only on the matching entry", () => {
    renderShell();

    const nav = screen.getByRole("navigation", { name: "Primary" });
    const current = within(nav).getAllByRole("link").filter((link) =>
      link.getAttribute("aria-current") === "page",
    );
    expect(current).toHaveLength(1);
    expect(current[0]).toHaveAccessibleName("Home");
  });

  it("exposes the main region and the skip link", () => {
    renderShell();

    expect(screen.getByRole("main")).toHaveAttribute("id", "main");
    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveAttribute(
      "href",
      "#main",
    );
    expect(screen.getByText("shell content")).toBeInTheDocument();
  });

  it("surfaces the runtime environment from GET /readyz", async () => {
    renderShell();

    // the REAL readiness body: mode "sandbox", environment "sandbox"
    expect(await screen.findByText("sandbox · sandbox")).toBeInTheDocument();

    const status = screen.getByRole("status", { name: "Runtime environment" });
    expect(status).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/readyz", expect.anything());
  });

  it("connects a session through the real boundary headers and shows the application", async () => {
    const user = userEvent.setup();
    renderShell();

    // open the session menu (disconnected trigger)
    await user.click(screen.getByRole("button", { name: "Connect application" }));

    // open the connect dialog from the menu item
    fireEvent.click(await screen.findByText("Connect application…"));
    expect(
      await screen.findByRole("heading", { name: "Connect application" }),
    ).toBeInTheDocument();

    // fill the two labeled inputs
    await user.type(screen.getByLabelText("Application ID"), APPLICATION.application_id);
    await user.type(screen.getByLabelText("Credential"), "dasec_test_credential");

    // submit through the form's submit button (the form onSubmit also
    // makes Enter submit from either input)
    await user.click(screen.getByRole("button", { name: /^Connect$/ }));

    // the application call carried the exact auth headers
    await waitFor(() => {
      const call = fetchMock.mock.calls.find(
        ([url]) => url === "/api/2.0/application",
      );
      expect(call).toBeDefined();
    });
    const applicationCall = fetchMock.mock.calls.find(
      ([url]) => url === "/api/2.0/application",
    ) as unknown as [string, { headers: Record<string, string> }];
    expect(applicationCall[1].headers["X-ADCOS-Application"]).toBe(
      APPLICATION.application_id,
    );
    expect(applicationCall[1].headers["X-ADCOS-Credential"]).toBe("dasec_test_credential");
    expect(applicationCall[1].headers["X-ADCOS-API-Version"]).toBe("2.0");

    // the connected application name appears in the session trigger
    expect(await screen.findByText("Sandbox Demo Application")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Connect application" })).toBeNull();

    // disconnect clears the session
    await user.click(screen.getByRole("button", { name: /Application session/ }));
    fireEvent.click(await screen.findByText("Disconnect"));
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Connect application" }),
      ).toBeInTheDocument();
    });
    expect(screen.queryByText("Sandbox Demo Application")).toBeNull();
  });

  it("shows the backend failure reason VERBATIM when credentials are rejected", async () => {
    applicationStatus = 401;
    applicationBody = AUTHENTICATION_INVALID;

    const user = userEvent.setup();
    renderShell();

    await user.click(screen.getByRole("button", { name: "Connect application" }));
    fireEvent.click(await screen.findByText("Connect application…"));

    await user.type(screen.getByLabelText("Application ID"), "sha256:wrong");
    await user.type(screen.getByLabelText("Credential"), "dasec_wrong");
    await user.click(screen.getByRole("button", { name: /^Connect$/ }));

    // the reason code is displayed VERBATIM, never rewritten
    expect(await screen.findByText("authentication-invalid")).toBeInTheDocument();
    // the dialog stays open on failure
    expect(
      screen.getByRole("heading", { name: "Connect application" }),
    ).toBeInTheDocument();
  });

  it("labels the session menu trigger honestly in both states", async () => {
    const user = userEvent.setup();
    renderShell();

    const disconnected = screen.getByRole("button", { name: "Connect application" });
    expect(disconnected).toBeInTheDocument();

    await user.click(disconnected);
    fireEvent.click(await screen.findByText("Connect application…"));
    await user.type(screen.getByLabelText("Application ID"), APPLICATION.application_id);
    await user.type(screen.getByLabelText("Credential"), "dasec_test_credential");
    await user.click(screen.getByRole("button", { name: /^Connect$/ }));

    await screen.findByText("Sandbox Demo Application");
    expect(
      screen.getByRole("button", {
        name: "Application session: Sandbox Demo Application",
      }),
    ).toBeInTheDocument();
  });
});
