/**
 * Build with ADCOS tests — the /build experience (the frozen Build-with-
 * ADCOS design §6) at the FEATURE-COMPONENT level (the station harness
 * discipline: hoisted vi.mock("next/navigation") + vi.mock("next/link"),
 * the feature component rendered inside the REAL SessionProvider, NO
 * network — the builder is pure registry data, fetch is never called).
 *
 * Covers:
 * - the NINE design-§6 sections render (choose architecture / design the
 *   boundary / choose capabilities / see the lifecycle / get the
 *   integration plan / see implementation examples / review anti-patterns
 *   / production checklist / export for an LLM);
 * - pattern selection via card click, with aria-pressed following;
 * - capability selection defaults to the pattern's recommended set and
 *   toggling changes it (and follows a pattern switch);
 * - "Design this integration" produces the blueprint: the required
 *   operations render with links to /docs/api/{operation_id}, the three
 *   owned-object columns render, boundary rules + failure modes + next
 *   steps render, and the presentation-state disclosure is present;
 * - the ?pattern= deep link pre-selects a valid pattern and falls back
 *   to the default for invalid values;
 * - keyboard: the card buttons and the capability toggles are buttons
 *   reachable by Tab, and aria-pressed reflects the selection;
 * - the public LLM asset links and the /docs and /developers/explorer
 *   surfaces are linked.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderBare } from "./harness";
import {
  INTEGRATION_CAPABILITIES,
  INTEGRATION_PATTERNS,
  buildIntegrationBlueprint,
  integrationPatternById,
} from "@/lib/integration";
import {
  BuildWithAdcos,
  BUILD_TEST_IDS,
} from "@/features/integration/build-with-adcos";
import {
  BLUEPRINT_TEST_IDS,
} from "@/features/integration/integration-blueprint";

/* ------------------------------------------------------------------ *
 * The hoisted module mocks (the harness pattern)
 * ------------------------------------------------------------------ */

/** The search params the mocked useSearchParams returns (per-test). */
let mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  usePathname: () => "/build",
  useParams: () => ({}),
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  useSearchParams: () => mockSearchParams,
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: Record<string, unknown>) => (
    <a href={href as string} {...props}>
      {children as never}
    </a>
  ),
}));

beforeEach(() => {
  mockSearchParams = new URLSearchParams();
});

/** The card element for a pattern id (or undefined). */
function patternCard(patternId: string): HTMLElement | undefined {
  return screen
    .getAllByTestId(BUILD_TEST_IDS.patternCard)
    .find((card) => card.getAttribute("data-pattern") === patternId);
}

/** The capability toggle element for a capability id. */
function capabilityToggle(capabilityId: string): HTMLElement | undefined {
  return screen
    .getAllByTestId(BUILD_TEST_IDS.capabilityToggle)
    .find((toggle) => toggle.getAttribute("data-capability") === capabilityId);
}

/* ------------------------------------------------------------------ *
 * 1. The nine design-§6 sections
 * ------------------------------------------------------------------ */

describe("the nine §6 sections", () => {
  it("renders every section heading, the honest example labels and the production checklist items", () => {
    renderBare(<BuildWithAdcos />);

    for (const heading of [
      "Choose your architecture",
      "Design the boundary",
      "Choose capabilities",
      "See the lifecycle",
      "Get the integration plan",
      "See implementation examples",
      "Review anti-patterns",
      "Production checklist",
      "Export for an LLM",
    ]) {
      expect(screen.getByRole("heading", { name: heading }), heading).toBeDefined();
    }

    // the implementation examples: ONE real captured request + ONE
    // explicitly-labeled conceptual example
    expect(
      screen.getByText(/real captured request shape from the coverage registry/i),
    ).toBeDefined();
    expect(
      screen.getByText(/^Conceptual — not an executable API call/),
    ).toBeDefined();

    // the production checklist: the six honest items with check icons
    for (const item of [
      "Authentication",
      "Versioning",
      "Idempotency",
      "Error handling",
      "Evidence",
      "Degradation",
    ]) {
      expect(screen.getAllByText(new RegExp(`^${item}:`)).length).toBeGreaterThanOrEqual(1);
    }
    expect(screen.getAllByTestId(BUILD_TEST_IDS.checklistItem)).toHaveLength(6);

    // the default selection is the gateway-relay pattern (the current
    // surface's default) — five pattern cards render from the registry
    expect(screen.getAllByTestId(BUILD_TEST_IDS.patternCard)).toHaveLength(
      INTEGRATION_PATTERNS.length,
    );
    expect(patternCard("gateway-relay")?.getAttribute("data-selected")).toBe("true");
  });
});

/* ------------------------------------------------------------------ *
 * 2. Pattern selection + capability selection
 * ------------------------------------------------------------------ */

describe("pattern selection and capabilities", () => {
  it("selects a pattern by card click (aria-pressed follows) and the boundary section shows the pattern", async () => {
    const user = userEvent.setup();
    renderBare(<BuildWithAdcos />);

    const applicationCard = patternCard("application");
    expect(applicationCard).toBeDefined();
    if (!applicationCard) return;

    const selectButton = within(applicationCard).getByRole("button", {
      name: /Application consumes connectivity/,
    });
    expect(selectButton).toHaveAttribute("aria-pressed", "false");

    await user.click(selectButton);

    expect(selectButton).toHaveAttribute("aria-pressed", "true");
    expect(patternCard("application")?.getAttribute("data-selected")).toBe("true");
    expect(patternCard("gateway-relay")?.getAttribute("data-selected")).toBe("false");

    // the boundary section renders the newly selected pattern's title
    expect(
      screen.getByRole("heading", { level: 3, name: "Application consumes connectivity" }),
    ).toBeDefined();
  });

  it("defaults capabilities to the pattern's recommended set; toggling changes the selection and a pattern switch resets it", async () => {
    const user = userEvent.setup();
    renderBare(<BuildWithAdcos />);

    // the registry's capability list renders in full
    expect(screen.getAllByTestId(BUILD_TEST_IDS.capabilityToggle)).toHaveLength(
      INTEGRATION_CAPABILITIES.length,
    );

    // gateway-relay defaults to exactly its capabilityIds
    const gatewayRelay = integrationPatternById("gateway-relay");
    expect(gatewayRelay).toBeDefined();
    if (!gatewayRelay) return;
    for (const capability of INTEGRATION_CAPABILITIES) {
      const toggle = capabilityToggle(capability.id);
      expect(toggle, `toggle for ${capability.id}`).toBeDefined();
      const expected = gatewayRelay.capabilityIds.includes(capability.id);
      expect(toggle).toHaveAttribute("aria-pressed", expected ? "true" : "false");
    }

    // toggling changes the selected set (aria-pressed flips)
    const leasesToggle = capabilityToggle("leases");
    if (!leasesToggle) return;
    expect(leasesToggle).toHaveAttribute("aria-pressed", "false");
    await user.click(leasesToggle);
    expect(leasesToggle).toHaveAttribute("aria-pressed", "true");

    // selecting the fleet-subscriber pattern resets the set to ITS
    // recommended capabilities (application-connectivity + leases)
    const fleetCard = patternCard("fleet-subscriber");
    if (!fleetCard) return;
    await user.click(
      within(fleetCard).getByRole("button", { name: /Fleet \/ subscriber connectivity/ }),
    );
    const fleet = integrationPatternById("fleet-subscriber");
    expect(fleet).toBeDefined();
    if (!fleet) return;
    for (const capability of INTEGRATION_CAPABILITIES) {
      const toggle = capabilityToggle(capability.id);
      expect(toggle, `toggle for ${capability.id}`).toBeDefined();
      const expected = fleet.capabilityIds.includes(capability.id);
      expect(toggle).toHaveAttribute("aria-pressed", expected ? "true" : "false");
    }
  });
});

/* ------------------------------------------------------------------ *
 * 3. "Design this integration" — the integration blueprint
 * ------------------------------------------------------------------ */

describe("Design this integration — the blueprint", () => {
  it("produces the blueprint: operations linked to /docs/api/{id}, owned columns, rules, failure modes, next steps and the disclosure", async () => {
    const user = userEvent.setup();
    renderBare(<BuildWithAdcos />);

    // before the CTA: the guidance panel, no blueprint
    expect(screen.getByTestId(BUILD_TEST_IDS.planGuidance)).toBeDefined();
    expect(screen.queryByTestId(BLUEPRINT_TEST_IDS.root)).toBeNull();

    // the primary CTA on the first pattern card
    const firstPattern = INTEGRATION_PATTERNS[0];
    const firstCard = patternCard(firstPattern.id);
    expect(firstCard).toBeDefined();
    if (!firstCard) return;
    await user.click(
      within(firstCard).getByRole("button", { name: "Design this integration" }),
    );

    // the blueprint rendered, driven by the SAME registry function
    const blueprintRoot = screen.getByTestId(BLUEPRINT_TEST_IDS.root);
    expect(blueprintRoot.getAttribute("data-pattern")).toBe(firstPattern.id);

    const expected = buildIntegrationBlueprint(
      firstPattern.id,
      firstPattern.capabilityIds,
    );
    expect(expected).toBeDefined();
    if (!expected) return;

    // the honest disclosure: presentation state, not deployment
    // configuration, not persisted
    const disclosure = screen.getByTestId(BLUEPRINT_TEST_IDS.disclosure);
    expect(disclosure).toHaveTextContent(/presentation state/i);
    expect(disclosure).toHaveTextContent(/not deployment configuration/i);
    expect(disclosure).toHaveTextContent(/not persisted/i);

    // every required operation links to its operation documentation
    expect(expected.requiredOperationIds.length).toBeGreaterThan(0);
    for (const operationId of expected.requiredOperationIds) {
      const row = screen
        .getAllByTestId(BLUEPRINT_TEST_IDS.operation)
        .find((element) => element.getAttribute("data-operation") === operationId);
      expect(row, `operation row for ${operationId}`).toBeDefined();
      const link = within(row as HTMLElement).getByRole("link");
      expect(link).toHaveAttribute("href", `/docs/api/${operationId}`);
    }

    // the three owned-object columns
    const ownedColumns = screen.getAllByTestId(BLUEPRINT_TEST_IDS.ownedColumn);
    expect(ownedColumns).toHaveLength(3);
    expect(
      ownedColumns.some((column) => column.getAttribute("data-owner") === "Your application owns"),
    ).toBe(true);
    expect(ownedColumns.some((column) => column.getAttribute("data-owner") === "ADCOS owns")).toBe(
      true,
    );
    expect(
      ownedColumns.some((column) => column.getAttribute("data-owner") === "Provider owns"),
    ).toBe(true);

    // boundary rules + failure modes render (verbatim registry strings)
    for (const rule of expected.boundaryRules) {
      expect(screen.getAllByText(rule).length).toBeGreaterThanOrEqual(1);
    }
    for (const mode of expected.failureModes) {
      expect(screen.getAllByText(mode).length).toBeGreaterThanOrEqual(1);
    }

    // next steps render, with their /docs, /docs/api/{id} and
    // /developers/explorer paths as links
    expect(screen.getByText(/Next steps/)).toBeDefined();
    const blueprintLinks = within(blueprintRoot).getAllByRole("link");
    expect(
      blueprintLinks.some((link) => link.getAttribute("href") === "/docs"),
      "the /docs next step links",
    ).toBe(true);
    expect(
      blueprintLinks.some(
        (link) => link.getAttribute("href") === `/docs/api/${expected.requiredOperationIds[0]}`,
      ),
      "the first-operation next step links",
    ).toBe(true);
    expect(
      blueprintLinks.some((link) => link.getAttribute("href") === "/developers/explorer"),
      "the Explorer next step links",
    ).toBe(true);
  });

  it("live-updates the blueprint when capabilities are toggled", async () => {
    const user = userEvent.setup();
    renderBare(<BuildWithAdcos />);

    // design the fleet-subscriber pattern — the pattern whose default
    // capabilities actually change the required-operation set
    const fleet = integrationPatternById("fleet-subscriber");
    expect(fleet).toBeDefined();
    if (!fleet) return;
    const fleetCard = patternCard("fleet-subscriber");
    expect(fleetCard).toBeDefined();
    if (!fleetCard) return;
    await user.click(
      within(fleetCard).getByRole("button", { name: "Design this integration" }),
    );

    const withDefaults = buildIntegrationBlueprint("fleet-subscriber", fleet.capabilityIds);
    expect(withDefaults).toBeDefined();
    if (!withDefaults) return;
    expect(withDefaults.requiredOperationIds).toContain("lease_grant");
    expect(screen.getAllByTestId(BLUEPRINT_TEST_IDS.operation).length).toBe(
      withDefaults.requiredOperationIds.length,
    );

    // toggling the leases capability OFF shrinks the plan live (the lease
    // operations drop out of the required set)
    const leasesToggle = capabilityToggle("leases");
    if (!leasesToggle) return;
    expect(leasesToggle).toHaveAttribute("aria-pressed", "true");
    await user.click(leasesToggle);
    expect(leasesToggle).toHaveAttribute("aria-pressed", "false");

    const withoutLeases = buildIntegrationBlueprint("fleet-subscriber", [
      "application-connectivity",
    ]);
    expect(withoutLeases).toBeDefined();
    if (!withoutLeases) return;
    expect(withoutLeases.requiredOperationIds).not.toContain("lease_grant");
    expect(withoutLeases.requiredOperationIds.length).toBeLessThan(
      withDefaults.requiredOperationIds.length,
    );
    expect(screen.getAllByTestId(BLUEPRINT_TEST_IDS.operation).length).toBe(
      withoutLeases.requiredOperationIds.length,
    );
    expect(
      screen
        .getAllByTestId(BLUEPRINT_TEST_IDS.operation)
        .some((row) => row.getAttribute("data-operation") === "lease_grant"),
    ).toBe(false);
  });
});

/* ------------------------------------------------------------------ *
 * 4. The ?pattern= deep link
 * ------------------------------------------------------------------ */

describe("the ?pattern= deep link", () => {
  it("pre-selects a valid pattern id", () => {
    mockSearchParams = new URLSearchParams("pattern=application");
    renderBare(<BuildWithAdcos />);

    expect(patternCard("application")?.getAttribute("data-selected")).toBe("true");
    expect(patternCard("gateway-relay")?.getAttribute("data-selected")).toBe("false");
    expect(
      screen.getByRole("heading", { level: 3, name: "Application consumes connectivity" }),
    ).toBeDefined();
  });

  it("falls back to the default selection for an invalid pattern id", () => {
    mockSearchParams = new URLSearchParams("pattern=not-a-real-pattern");
    renderBare(<BuildWithAdcos />);

    expect(patternCard("gateway-relay")?.getAttribute("data-selected")).toBe("true");
    expect(patternCard("application")?.getAttribute("data-selected")).toBe("false");
  });
});

/* ------------------------------------------------------------------ *
 * 5. Keyboard access
 * ------------------------------------------------------------------ */

describe("keyboard access", () => {
  it("the pattern-card select buttons and the capability toggles are reachable by Tab, and aria-pressed reflects selection", async () => {
    const user = userEvent.setup();
    renderBare(<BuildWithAdcos />);

    // every card's select control is a button carrying aria-pressed
    const selectButtons = screen
      .getAllByRole("button")
      .filter(
        (button) =>
          button.getAttribute("aria-pressed") !== null &&
          button.closest(`[data-testid="${BUILD_TEST_IDS.patternCard}"]`) !== null,
      );
    expect(selectButtons).toHaveLength(INTEGRATION_PATTERNS.length);

    // Tab reaches the first card's select button…
    let reachedCard = false;
    for (let step = 0; step < 80 && !reachedCard; step += 1) {
      await user.tab();
      reachedCard = document.activeElement === selectButtons[0];
    }
    expect(reachedCard, "Tab reaches the first pattern card's select button").toBe(true);

    // …and Enter selects the pattern (aria-pressed follows)
    expect(selectButtons[0]).toHaveAttribute("aria-pressed", "false");
    await user.keyboard("{Enter}");
    expect(selectButtons[0]).toHaveAttribute("aria-pressed", "true");

    // Tab continues to the capability toggles, which are buttons too
    const toggles = screen.getAllByTestId(BUILD_TEST_IDS.capabilityToggle);
    expect(toggles).toHaveLength(INTEGRATION_CAPABILITIES.length);
    let reachedToggle = false;
    for (let step = 0; step < 120 && !reachedToggle; step += 1) {
      await user.tab();
      reachedToggle = document.activeElement === toggles[0];
    }
    expect(reachedToggle, "Tab reaches the first capability toggle").toBe(true);

    // Enter activates the toggle (aria-pressed flips)
    const pressedBefore = toggles[0].getAttribute("aria-pressed");
    await user.keyboard("{Enter}");
    expect(toggles[0].getAttribute("aria-pressed")).not.toBe(pressedBefore);
  });
});

/* ------------------------------------------------------------------ *
 * 6. The LLM export and the cross-surface links
 * ------------------------------------------------------------------ */

describe("the LLM export and cross-surface links", () => {
  it("links to every public LLM asset plus /docs and /developers/explorer", () => {
    renderBare(<BuildWithAdcos />);

    const links = screen.getAllByRole("link");
    for (const href of [
      "/llms.txt",
      "/llms-full.txt",
      "/adcos-integration-context.json",
      "/adcos-capabilities.json",
      "/adcos-operations.json",
      "/docs",
      "/developers/explorer",
    ]) {
      expect(links.some((link) => link.getAttribute("href") === href), `links ${href}`).toBe(true);
    }
  });
});
