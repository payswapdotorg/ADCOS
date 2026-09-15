/**
 * Cross-surface consistency tests — the anti-drift battery of the Build
 * with ADCOS & LLM Integration program (design §12 "Registry
 * architecture — no second endpoint catalog is permitted" + §14
 * acceptance points 2/4/7; plan Tasks 5/6 —
 * docs/superpowers/specs|plans/2026-09-15-adcos-build-with-adcos-llm-
 * integration*).
 *
 * The one architectural question this file answers mechanically: do the
 * integration registry, the public LLM assets, the docs API surface and
 * the coverage registry agree on the SAME operation ids? Drift between
 * any two of them fails HERE (never in the UI). Pure data-contract
 * tests in the education-registry style: no network, fetch is never
 * called, public assets are read with node:fs via import.meta.url-
 * relative paths, everything is deterministic.
 *
 * The battery:
 * 1. every operation id INTEGRATION_PATTERNS references exists in
 *    COVERAGE (the registry cannot invent a second endpoint catalog);
 * 2. the public JSON assets agree with the coverage registry —
 *    adcos-operations.json projects EXACTLY the coverage set (both
 *    directions — the design's "human docs and LLM assets agree"
 *    acceptance), adcos-capabilities.json references only coverage
 *    operations, and adcos-integration-context.json's operations
 *    section (a design §10 mandatory section) references only coverage
 *    operations;
 * 3. the docs API surface renders EXACTLY the coverage registry's
 *    operation set (no invented docs operations, none missing);
 * 4. llms-full.txt carries the ShareNet authority boundary sentences
 *    (design §13) and the §11 anti-drift rules (pinned phrases);
 * 5. the provider-SDK leak scan — none of the deny-listed provider SDK
 *    tokens appears in the application-facing integration surfaces or
 *    the public LLM assets;
 * 6. patternsUsingOperation — the W1 lookup contract (known operation →
 *    its patterns; bogus id → []).
 *
 * Plus the plan-Task-5 component check: the "Build context" block
 * mounted inside the About-this-operation disclosure renders the
 * pattern links, the lifecycle position and the PUBLIC machine-readable
 * context pointer (the copy affordance writes the public asset URL and
 * nothing else), with the honest empty state and the coverage guard.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import { createElement } from "react";
import type { HTMLAttributes, ReactNode } from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { renderBare } from "./harness";
import { COVERAGE } from "@/lib/api/coverage";
import { getOperationEducation } from "@/lib/education";
import { INTEGRATION_PATTERNS } from "@/lib/integration/patterns";
import { patternsUsingOperation } from "@/lib/integration";
import { API_HUB_TEST_IDS, ApiHub } from "@/features/docs";
import {
  BUILD_CONTEXT_TEST_IDS,
  BuildContextBlock,
  INTEGRATION_CONTEXT_HREF,
  OPERATION_EDUCATION_TEST_IDS,
  OperationEducationPanel,
} from "@/features/api-learning";

/* ------------------------------------------------------------------ *
 * The hoisted module mocks (the docs-system harness discipline)
 * ------------------------------------------------------------------ */

vi.mock("next/navigation", () => ({
  usePathname: () => "/docs/api",
  useParams: () => ({}),
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/link", () => ({
  default: ({ children, ...rest }: Record<string, unknown>) =>
    createElement(
      "a",
      rest as unknown as HTMLAttributes<HTMLAnchorElement>,
      children as ReactNode,
    ),
}));

/* ------------------------------------------------------------------ *
 * The public-asset / source reader (node:fs, import.meta.url-relative)
 *
 * NOTE: `new URL(<relative>, import.meta.url)` is rewritten by vite's
 * asset transform under vitest (it resolves against the dev-server
 * origin, not the file scheme), so the path is derived through
 * `dirname(fileURLToPath(import.meta.url))` instead — still strictly
 * import.meta.url-relative to this test file.
 * ------------------------------------------------------------------ */

const TESTS_DIR = dirname(fileURLToPath(import.meta.url));
const PUBLIC_DIR = join(TESTS_DIR, "..", "public");
const SRC_DIR = join(TESTS_DIR, "..", "src");

function readAsset(relativePath: string): string {
  return readFileSync(join(PUBLIC_DIR, relativePath), "utf8");
}

function readSource(relativePath: string): string {
  return readFileSync(join(SRC_DIR, relativePath), "utf8");
}

/* ------------------------------------------------------------------ *
 * Strict JSON narrowing helpers (no `any`)
 * ------------------------------------------------------------------ */

function asRecord(value: unknown, where: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${where}: expected a JSON object`);
  }
  return value as Record<string, unknown>;
}

function asString(value: unknown, where: string): string {
  if (typeof value !== "string" || value.length === 0) {
    throw new Error(`${where}: expected a non-empty string`);
  }
  return value;
}

/**
 * Extract an operation id from a projected entry. The id-bearing key is
 * tolerant (`operation_id` per design §10, `id` per the current
 * adcos-operations.json projection, `operation` as the registry's own
 * spelling) — the CONTRACT under test is the id set, never the key
 * spelling; an entry carrying none of them fails loudly.
 */
function operationIdOf(entry: unknown, where: string): string {
  const record = asRecord(entry, where);
  for (const key of ["operation_id", "id", "operation"]) {
    const value = record[key];
    if (typeof value === "string" && value.length > 0) return value;
  }
  throw new Error(`${where}: no operation id (operation_id / id / operation)`);
}

/** The coverage registry's operation ids — the single operation authority. */
const COVERAGE_IDS: ReadonlySet<string> = new Set(
  COVERAGE.map((record) => record.operation),
);

/* ------------------------------------------------------------------ *
 * 1 — the integration-pattern registry ↔ the coverage registry
 * ------------------------------------------------------------------ */

describe("the integration-pattern registry ↔ the coverage registry (no second endpoint catalog)", () => {
  it("references ONLY operations the coverage registry carries", () => {
    expect(INTEGRATION_PATTERNS.length).toBeGreaterThan(0);
    for (const pattern of INTEGRATION_PATTERNS) {
      expect(
        pattern.operationIds.length,
        `pattern "${pattern.id}" references no operations`,
      ).toBeGreaterThan(0);
      for (const operationId of pattern.operationIds) {
        expect(
          COVERAGE_IDS.has(operationId),
          `pattern "${pattern.id}" references operation "${operationId}" outside COVERAGE`,
        ).toBe(true);
      }
    }
  });
});

/* ------------------------------------------------------------------ *
 * 2 — the public JSON assets ↔ the coverage registry
 * ------------------------------------------------------------------ */

describe("the public JSON assets ↔ the coverage registry (design §14 acceptance 4)", () => {
  it("adcos-operations.json projects EXACTLY the coverage registry's operations (both directions)", () => {
    const parsed: unknown = JSON.parse(readAsset("adcos-operations.json"));
    const root = asRecord(parsed, "adcos-operations.json");
    expect(
      Array.isArray(root.operations),
      "adcos-operations.json must carry an operations array",
    ).toBe(true);
    const operations: unknown[] = Array.isArray(root.operations)
      ? root.operations
      : [];
    expect(operations.length).toBeGreaterThan(0);

    const assetIds = new Set<string>();
    operations.forEach((entry, index) => {
      assetIds.add(operationIdOf(entry, `adcos-operations.json operations[${index}]`));
    });

    // forward: every projected id is a coverage operation (no invented ids)
    const outsideCoverage = [...assetIds].filter((id) => !COVERAGE_IDS.has(id));
    expect(
      outsideCoverage,
      "operations the coverage registry does not carry",
    ).toEqual([]);

    // reverse (the anti-drift contract): every coverage operation is projected
    const missing = COVERAGE.map((record) => record.operation).filter(
      (id) => !assetIds.has(id),
    );
    expect(
      missing,
      "coverage operations missing from the public asset (the human docs and LLM assets must agree)",
    ).toEqual([]);

    expect(assetIds.size).toBe(COVERAGE.length);
  });

  it("adcos-capabilities.json references only coverage operations", () => {
    const parsed: unknown = JSON.parse(readAsset("adcos-capabilities.json"));
    const root = asRecord(parsed, "adcos-capabilities.json");
    expect(
      Array.isArray(root.capabilities),
      "adcos-capabilities.json must carry a capabilities array",
    ).toBe(true);
    const capabilities: unknown[] = Array.isArray(root.capabilities)
      ? root.capabilities
      : [];
    expect(capabilities.length).toBeGreaterThan(0);

    for (const capability of capabilities) {
      const record = asRecord(capability, "adcos-capabilities.json capability");
      const capabilityId = asString(record.id, "capability id");
      expect(
        Array.isArray(record.operation_ids),
        `capability "${capabilityId}" must carry an operation_ids array`,
      ).toBe(true);
      const operationIds: unknown[] = Array.isArray(record.operation_ids)
        ? record.operation_ids
        : [];
      for (const entry of operationIds) {
        const operationId = asString(entry, `capability "${capabilityId}" operation id`);
        expect(
          COVERAGE_IDS.has(operationId),
          `capability "${capabilityId}" references operation "${operationId}" outside COVERAGE`,
        ).toBe(true);
      }
    }
  });

  it("adcos-integration-context.json carries an operations section referencing only coverage operations", () => {
    const parsed: unknown = JSON.parse(readAsset("adcos-integration-context.json"));
    const root = asRecord(parsed, "adcos-integration-context.json");

    // design §10: the machine-readable context's mandatory top-level
    // sections include `operations` — the section must exist as an array
    expect(
      Array.isArray(root.operations),
      "design §10: adcos-integration-context.json must carry an operations array",
    ).toBe(true);
    const operations: unknown[] = Array.isArray(root.operations)
      ? root.operations
      : [];
    expect(operations.length).toBeGreaterThan(0);

    operations.forEach((entry, index) => {
      const operationId = operationIdOf(
        entry,
        `adcos-integration-context.json operations[${index}]`,
      );
      expect(
        COVERAGE_IDS.has(operationId),
        `integration context references operation "${operationId}" outside COVERAGE`,
      ).toBe(true);
    });
  });
});

/* ------------------------------------------------------------------ *
 * 3 — the docs API surface ↔ the coverage registry
 * ------------------------------------------------------------------ */

describe("the docs API surface ↔ the coverage registry (design §12)", () => {
  it("renders EXACTLY the coverage registry's operation set — no invented docs operations, none missing", () => {
    renderBare(createElement(ApiHub));

    const rows = screen.getAllByTestId(API_HUB_TEST_IDS.row);
    const renderedIds = new Set<string>();
    for (const row of rows) {
      const operation = row.getAttribute("data-operation");
      expect(operation, "an api-hub row without data-operation").toBeTruthy();
      renderedIds.add(operation ?? "");
    }

    // no invented docs operations
    const outsideCoverage = [...renderedIds].filter((id) => !COVERAGE_IDS.has(id));
    expect(outsideCoverage, "docs operations outside COVERAGE").toEqual([]);

    // no missing docs operations
    const missing = COVERAGE.map((record) => record.operation).filter(
      (id) => !renderedIds.has(id),
    );
    expect(missing, "coverage operations missing from the docs API hub").toEqual([]);

    expect(renderedIds.size).toBe(COVERAGE.length);
    expect(COVERAGE).toHaveLength(25);
  });
});

/* ------------------------------------------------------------------ *
 * 4 — llms-full.txt: the ShareNet boundary + the §11 anti-drift rules
 * ------------------------------------------------------------------ */

describe("llms-full.txt — the ShareNet boundary (design §13) and the §11 anti-drift rules", () => {
  const full = readAsset("llms-full.txt");

  it("carries the ShareNet reference section with the content/P2P/gateway authority sentences", () => {
    expect(full).toContain("ShareNet");
    // the section itself exists
    expect(full).toContain("## ShareNet reference architecture");
    // the canonical boundary: the content/P2P plane, the gateway/relay need
    expect(full).toContain("ShareNet content + P2P data plane");
    expect(full).toContain("technology-neutral gateway/relay connectivity need");
    // the authority sentences
    expect(full).toContain("ShareNet retains authority over:");
  });

  it("states the §11 anti-drift rules (pinned phrases from the current asset)", () => {
    // no second contract authority
    expect(full).toContain("second connectivity-contract authority");
    // webhooks are observations, not canonical state
    expect(full).toContain("Webhooks are observations");
    // API success is never physical connectivity success
    expect(full).toContain("API success is not proof of physical connectivity success");
    // software evidence stays distinct from physical/network evidence
    expect(full).toContain(
      "Software/deployment evidence and physical/network evidence are different evidence classes",
    );
    // no invented endpoints / capabilities / telemetry
    expect(full).toContain("Do not invent endpoints, provider capabilities or telemetry");
    // canonical reason codes are preserved
    expect(full).toContain("Preserve canonical ADCOS reason codes");
  });
});

/* ------------------------------------------------------------------ *
 * 5 — the provider-SDK leak scan
 * ------------------------------------------------------------------ */

describe("the provider-SDK leak scan (application-facing surfaces stay provider-neutral)", () => {
  const DENY_TOKENS = [
    "twilio",
    "vonage",
    "aws-sdk",
    "boto3",
    "stripe-sdk",
    "gmail-sdk",
  ];

  const SCANNED: { label: string; content: string }[] = [
    {
      label: "the Build experience component (features/integration)",
      content: readSource("features/integration/build-with-adcos.tsx"),
    },
    {
      label: "the integration-pattern card (features/integration)",
      content: readSource("features/integration/integration-pattern-card.tsx"),
    },
    {
      label: "the integration-blueprint renderer (features/integration)",
      content: readSource("features/integration/integration-blueprint.tsx"),
    },
    {
      label: "the docs Build section pages (features/docs)",
      content: readSource("features/docs/build-pages.tsx"),
    },
    {
      label: "the docs home IA (features/docs)",
      content: readSource("features/docs/docs-home.tsx"),
    },
    {
      label: "the integration-pattern registry (lib/integration)",
      content: readSource("lib/integration/patterns.ts"),
    },
    {
      label: "the operation-education build-context block (features/api-learning)",
      content: readSource("features/api-learning/build-context-block.tsx"),
    },
    {
      label: "the full LLM context asset (public)",
      content: readAsset("llms-full.txt"),
    },
    {
      label: "the concise LLM overview asset (public)",
      content: readAsset("llms.txt"),
    },
  ];

  it("contains none of the deny-listed provider-SDK tokens (case-insensitive)", () => {
    for (const file of SCANNED) {
      const content = file.content.toLowerCase();
      for (const token of DENY_TOKENS) {
        expect(
          content.includes(token),
          `${file.label} leaks the provider-SDK token "${token}"`,
        ).toBe(false);
      }
    }
  });
});

/* ------------------------------------------------------------------ *
 * 6 — patternsUsingOperation: the W1 lookup contract
 * ------------------------------------------------------------------ */

describe("patternsUsingOperation — the W1 lookup contract", () => {
  it("returns the patterns whose operationIds include the operation", () => {
    const patterns = patternsUsingOperation("intent_create");
    expect(patterns.length).toBeGreaterThanOrEqual(1);
    for (const pattern of patterns) {
      expect(pattern.operationIds).toContain("intent_create");
      expect(pattern.title.length).toBeGreaterThan(0);
    }
  });

  it("returns [] for a bogus operation id (never invented membership)", () => {
    expect(patternsUsingOperation("definitely_not_an_operation")).toEqual([]);
    expect(patternsUsingOperation("")).toEqual([]);
    expect(patternsUsingOperation("offer_publish")).toEqual([]); // W046-era, demoted
  });
});

/* ------------------------------------------------------------------ *
 * 7 — the Build context block (plan Task 5), mounted in the education
 *     panel — component level, the api-learning house style
 * ------------------------------------------------------------------ */

describe("the Build context block — mounted inside the About-this-operation disclosure", () => {
  beforeEach(() => {
    // jsdom has no clipboard of its own; stub the primitives this suite
    // asserts against (the setup-file stub is shared, so re-own it here)
    Object.defineProperty(navigator, "clipboard", {
      value: {
        writeText: vi.fn().mockResolvedValue(undefined),
        readText: vi.fn().mockResolvedValue(""),
      },
      configurable: true,
    });
  });

  it("stays collapsed with the disclosure; expanding shows the REAL pattern links, lifecycle position and the PUBLIC context pointer", async () => {
    const record = COVERAGE.find((entry) => entry.operation === "intent_create");
    if (!record) throw new Error("intent_create is not in the coverage registry");
    const education = getOperationEducation("intent_create");
    if (!education) throw new Error("intent_create has no education record");
    const patterns = patternsUsingOperation("intent_create");

    render(
      createElement(OperationEducationPanel, { record, applicationId: null }),
    );

    // collapsed by default: no build context in the DOM until opted into
    expect(screen.queryByTestId(BUILD_CONTEXT_TEST_IDS.root)).toBeNull();

    fireEvent.click(screen.getByTestId(OPERATION_EDUCATION_TEST_IDS.trigger));
    const panel = screen.getByTestId(OPERATION_EDUCATION_TEST_IDS.panel);
    const block = within(panel).getByTestId(BUILD_CONTEXT_TEST_IDS.root);
    expect(block).toBeInTheDocument();

    // the registry's own pattern list, as /build?pattern= deep links
    expect(patterns.length).toBeGreaterThanOrEqual(1);
    for (const pattern of patterns) {
      const link = within(block).getByRole("link", { name: pattern.title });
      expect(link).toHaveAttribute("href", `/build?pattern=${pattern.id}`);
    }

    // the lifecycle position comes from the operation-learning registry
    const lifecycle = within(panel).getByTestId(BUILD_CONTEXT_TEST_IDS.lifecycle);
    expect(lifecycle.textContent).toContain(education.lifecyclePosition);

    // the machine-readable context pointer: the copy affordance (inside a
    // polite live region) plus the public asset link
    const copyButton = within(block).getByRole("button", {
      name: "Copy LLM context link",
    });
    expect(copyButton.closest('[aria-live="polite"]')).not.toBeNull();
    const viewLink = within(block).getByRole("link", {
      name: "View machine-readable context",
    });
    expect(viewLink).toHaveAttribute("href", INTEGRATION_CONTEXT_HREF);

    // LINKS ONLY: the block's single button is the copy affordance — no
    // execution control, no request trigger
    expect(within(block).getAllByRole("button")).toHaveLength(1);

    // the copy affordance writes the PUBLIC asset URL and nothing else —
    // no credential, no token, no fabricated state
    fireEvent.click(copyButton);
    await waitFor(() => expect(screen.getByText("Copied")).toBeInTheDocument());
    const writeText = navigator.clipboard.writeText as unknown as Mock;
    expect(writeText).toHaveBeenCalledTimes(1);
    expect(writeText).toHaveBeenCalledWith(INTEGRATION_CONTEXT_HREF);
  });

  it("renders the honest empty state for an operation no documented pattern uses", () => {
    const record = COVERAGE.find((entry) => entry.operation === "healthz");
    if (!record) throw new Error("healthz is not in the coverage registry");

    render(
      createElement(OperationEducationPanel, { record, applicationId: null }),
    );
    fireEvent.click(screen.getByTestId(OPERATION_EDUCATION_TEST_IDS.trigger));
    const panel = screen.getByTestId(OPERATION_EDUCATION_TEST_IDS.panel);
    const block = within(panel).getByTestId(BUILD_CONTEXT_TEST_IDS.root);

    // the honest empty state, with the /build link
    const patterns = within(block).getByTestId(BUILD_CONTEXT_TEST_IDS.patterns);
    expect(
      within(patterns).getByText(/not part of a documented integration pattern yet/),
    ).toBeInTheDocument();
    expect(within(patterns).getByRole("link", { name: "/build" })).toHaveAttribute(
      "href",
      "/build",
    );

    // no pattern deep links were invented for a patternless operation
    const deepLinks = within(block)
      .queryAllByRole("link")
      .filter((link) => (link.getAttribute("href") ?? "").startsWith("/build?pattern="));
    expect(deepLinks).toEqual([]);

    // the lifecycle + machine-readable sections still render
    expect(
      within(block).getByTestId(BUILD_CONTEXT_TEST_IDS.machineReadable),
    ).toBeInTheDocument();
  });

  it("renders nothing for an operation id outside the coverage registry (no second catalog)", () => {
    const { container } = render(
      createElement(BuildContextBlock, { operationId: "not_a_registry_operation" }),
    );
    expect(container.textContent).toBe("");
  });
});
