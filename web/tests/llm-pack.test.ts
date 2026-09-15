/**
 * LLM pack tests — the pack is the ANTI-DRIFT CORE of the Build with
 * ADCOS program (the 2026-09-15 design §10/§11/§12): the machine-
 * readable context carries EXACTLY the 15 canonical sections; the
 * operation projection carries ONE record for EVERY coverage-registry
 * operation (the generator's whole point — no hand-maintained endpoint
 * list can drift); the five PUBLIC assets under web/public are
 * byte-pinned to the renderers' output (a checked-in file that drifts
 * from its generator fails HERE); and every enumerated id — operations,
 * concepts, capabilities, webhook events, reason codes — resolves
 * against the real registries. The 11 design-§11 anti-drift rules and
 * the ShareNet boundary must be present verbatim in meaning. Pure
 * data-contract tests: no network, fetch is never called, everything is
 * deterministic.
 */

import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { COVERAGE } from "@/lib/api/coverage";
import { CONCEPTS } from "@/lib/education/concepts";
import { WEBHOOK_EVENT_TYPES } from "@/features/developers/webhook-event-types";
import { INTEGRATION_CAPABILITIES } from "@/lib/integration/capabilities";
import {
  buildLlmContext,
  buildLlmOperations,
  renderCapabilitiesJson,
  renderIntegrationContextJson,
  renderLlmsFullTxt,
  renderLlmsTxt,
  renderOperationsJson,
} from "@/lib/integration/llm-pack";

/** The 15 design-§10 context sections — the complete top-level vocabulary. */
const CONTEXT_SECTIONS: string[] = [
  "mission",
  "mental_model",
  "architecture",
  "authority_boundaries",
  "integration_patterns",
  "capabilities",
  "operations",
  "workflow_sequences",
  "webhooks",
  "errors",
  "versioning",
  "security_rules",
  "evidence_rules",
  "anti_patterns",
  "production_checklist",
];

/** The 11 design-§11 LLM safety / anti-drift rules, verbatim. */
const SAFETY_RULES: string[] = [
  "Do not create a second contract authority.",
  "Do not encode provider-specific topology into application domain logic.",
  "Do not treat webhook observations as canonical state.",
  "Do not equate API success with physical connectivity success.",
  "Do not invent unavailable endpoints.",
  "Do not invent provider capabilities.",
  "Do not make application data-plane availability depend on ADCOS control-plane availability unless the product explicitly chooses that tradeoff.",
  "Preserve canonical reason codes.",
  "Preserve API version and compatibility rules.",
  "Use idempotency and declared request semantics as defined by the API.",
  "Distinguish software evidence from physical/network evidence.",
];

/** The §10 per-operation minimum fields every projected record must carry. */
const OPERATION_MINIMUM_FIELDS: string[] = [
  "operation_id",
  "method",
  "path",
  "purpose",
  "prerequisites",
  "lifecycle_position",
  "capability_ids",
  "concept_ids",
  "example_request",
  "example_response",
  "error_reason_codes",
  "next_operation_ids",
];

/** The shape of one projected operation record (the §10 minimum fields, typed). */
interface LlmOperationRecord {
  operation_id: string;
  method: string;
  path: string;
  purpose: string;
  prerequisites: string;
  lifecycle_position: string;
  capability_ids: string[];
  concept_ids: string[];
  example_request: unknown;
  example_response: string;
  error_reason_codes: string[];
  next_operation_ids: string[];
}

/** The shape of the parsed public context JSON (the sections the tests inspect). */
interface LlmContextJson {
  anti_patterns: string[];
  operations: { operation_id: string }[];
  integration_patterns: {
    patterns: { id: string; operation_ids: string[] }[];
    reference_integration: { critical_rule: string; pattern_id: string };
  };
  webhooks: { frozen_event_types: string[] };
  errors: { reason_codes: string[] };
  workflow_sequences: { patterns: { pattern_id: string; steps: { stage: string }[] }[] };
}

/**
 * Reads a file from web/public regardless of the runner's cwd.
 *
 * NOTE: this deliberately does NOT use the `new URL(name,
 * import.meta.url)` form — vite's test transform rewrites that exact
 * asset-reference pattern against the jsdom document location
 * (http://localhost:3000) instead of the real file URL. Resolving
 * through fileURLToPath(import.meta.url) (a bare reference, which the
 * transform leaves alone) keeps the path cwd-independent AND
 * transform-proof.
 */
const WEB_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function readPublic(name: string): string {
  return readFileSync(path.join(WEB_ROOT, "public", name), "utf8");
}

/** Non-emptiness for any section value (object, array, string or other). */
function isEmptyValue(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === "object") return Object.keys(value as Record<string, unknown>).length === 0;
  if (typeof value === "string") return value.trim().length === 0;
  return false;
}

const context = buildLlmContext();
const operations = buildLlmOperations() as unknown as LlmOperationRecord[];
const coverageIds = COVERAGE.map((record) => record.operation);
const conceptIds = new Set<string>(CONCEPTS.map((concept) => concept.id));
const capabilityIds = new Set<string>(INTEGRATION_CAPABILITIES.map((capability) => capability.id));

describe("the LLM context — the 15 canonical sections", () => {
  it("contains EXACTLY the 15 design-§10 sections (no more, no fewer)", () => {
    expect(Object.keys(context).sort()).toEqual([...CONTEXT_SECTIONS].sort());
  });

  it("carries non-empty content in every section", () => {
    for (const section of CONTEXT_SECTIONS) {
      const value = context[section];
      expect(value, `section "${section}"`).toBeDefined();
      expect(isEmptyValue(value), `section "${section}" is empty`).toBe(false);
    }
  });

  it("projects the integration patterns and capabilities from the registries (no second catalog)", () => {
    const patterns = context.integration_patterns as {
      patterns: { id: string; operation_ids: string[]; concept_ids: string[] }[];
    };
    expect(patterns.patterns).toHaveLength(5);
    for (const pattern of patterns.patterns) {
      for (const operationId of pattern.operation_ids) {
        expect(coverageIds).toContain(operationId);
      }
      for (const conceptId of pattern.concept_ids) {
        expect(conceptIds.has(conceptId), `pattern concept "${conceptId}"`).toBe(true);
      }
    }
    const capabilities = context.capabilities as { id: string; operation_ids: string[] }[];
    expect(capabilities).toHaveLength(INTEGRATION_CAPABILITIES.length);
    for (const capability of capabilities) {
      expect(capabilityIds.has(capability.id), `capability "${capability.id}"`).toBe(true);
      for (const operationId of capability.operation_ids) {
        expect(coverageIds).toContain(operationId);
      }
    }
  });

  it("carries the frozen webhook vocabulary and the observations-not-authority rule", () => {
    const webhooks = context.webhooks as { frozen_event_types: string[]; rule: string };
    expect(webhooks.frozen_event_types).toEqual([...WEBHOOK_EVENT_TYPES]);
    expect(webhooks.rule).toContain("observations");
    expect(webhooks.rule).toContain("never become a second source of canonical business state");
  });

  it("carries all 11 design-§11 anti-drift rules in anti_patterns", () => {
    const antiPatterns = context.anti_patterns as string[];
    for (const rule of SAFETY_RULES) {
      expect(
        antiPatterns.some((entry) => entry.includes(rule)),
        `anti_patterns must state: ${rule}`,
      ).toBe(true);
    }
  });

  it("carries the ShareNet reference integration with its critical boundary rule", () => {
    const reference = (context.integration_patterns as LlmContextJson["integration_patterns"])
      .reference_integration;
    expect(reference.pattern_id).toBe("gateway-relay");
    expect(reference.critical_rule).toContain(
      "Ordinary device-to-device ShareNet transfers remain inside ShareNet",
    );
    expect(reference.critical_rule).toContain("do not become ADCOS connectivity transactions");
  });
});

describe("the LLM operation projection — one record per coverage operation", () => {
  it("projects EVERY coverage operation (the generator's point: no hand-maintained list)", () => {
    expect(operations).toHaveLength(COVERAGE.length);
    const projectedIds = operations.map((operation) => operation.operation_id);
    expect(projectedIds.sort()).toEqual([...coverageIds].sort());
  });

  it("carries method and path VERBATIM from the coverage registry", () => {
    const byOperation = new Map(COVERAGE.map((record) => [record.operation, record]));
    for (const operation of operations) {
      const record = byOperation.get(operation.operation_id);
      expect(record, `${operation.operation_id} exists in COVERAGE`).toBeDefined();
      if (!record) continue;
      expect(operation.method).toBe(record.method);
      expect(operation.path).toBe(record.path);
    }
  });

  it("carries the §10 minimum fields with registry-derived values only", () => {
    for (const operation of operations) {
      for (const field of OPERATION_MINIMUM_FIELDS) {
        expect(
          operation[field as keyof LlmOperationRecord],
          `${operation.operation_id} field "${field}"`,
        ).toBeDefined();
      }
      for (const capabilityId of operation.capability_ids) {
        expect(capabilityIds.has(capabilityId), `${operation.operation_id} capability "${capabilityId}"`).toBe(true);
      }
      for (const conceptId of operation.concept_ids) {
        expect(conceptIds.has(conceptId), `${operation.operation_id} concept "${conceptId}"`).toBe(true);
      }
      for (const code of operation.error_reason_codes) {
        expect(
          (context.errors as { reason_codes: string[] }).reason_codes.includes(code),
          `${operation.operation_id} reason code "${code}"`,
        ).toBe(true);
      }
      for (const nextId of operation.next_operation_ids) {
        expect(coverageIds).toContain(nextId);
      }
      // example responses reference the canonical docs page, never a fabricated body
      expect(operation.example_response).toContain(`/docs/api/${operation.operation_id}`);
    }
  });

  it("uses the coverage registry's real example bodies as example requests (or the honest no-body note)", () => {
    const byOperation = new Map(COVERAGE.map((record) => [record.operation, record]));
    for (const operation of operations) {
      const record = byOperation.get(operation.operation_id);
      if (!record) continue;
      if (record.example !== undefined) {
        expect(operation.example_request).toEqual(record.example);
      } else {
        // the honest fallback: a string note, never an invented body
        expect(typeof operation.example_request).toBe("string");
        expect((operation.example_request as string).length).toBeGreaterThan(0);
      }
    }
  });
});

describe("the public assets — the anti-drift byte pins", () => {
  it("renders llms.txt exactly as the checked-in public/llms.txt", () => {
    expect(renderLlmsTxt()).toBe(readPublic("llms.txt"));
  });

  it("renders llms-full.txt exactly as the checked-in public/llms-full.txt", () => {
    expect(renderLlmsFullTxt()).toBe(readPublic("llms-full.txt"));
  });

  it("renders adcos-integration-context.json exactly as the checked-in public file", () => {
    expect(renderIntegrationContextJson()).toBe(readPublic("adcos-integration-context.json"));
  });

  it("renders adcos-capabilities.json exactly as the checked-in public file", () => {
    expect(renderCapabilitiesJson()).toBe(readPublic("adcos-capabilities.json"));
  });

  it("renders adcos-operations.json exactly as the checked-in public file", () => {
    expect(renderOperationsJson()).toBe(readPublic("adcos-operations.json"));
  });
});

describe("the public JSON assets — validity and operation-id equality with the coverage registry", () => {
  it("parses as valid JSON and carries the coverage registry's operation ids", () => {
    const contextJson = JSON.parse(readPublic("adcos-integration-context.json")) as LlmContextJson;
    const operationsJson = JSON.parse(readPublic("adcos-operations.json")) as {
      operations: { operation_id: string }[];
    };
    const capabilitiesJson = JSON.parse(readPublic("adcos-capabilities.json")) as {
      capabilities: { id: string; operation_ids: string[] }[];
    };

    // the two operation-carrying assets enumerate EXACTLY the coverage registry
    expect(operationsJson.operations.map((operation) => operation.operation_id).sort()).toEqual(
      [...coverageIds].sort(),
    );
    expect(contextJson.operations.map((operation) => operation.operation_id).sort()).toEqual(
      [...coverageIds].sort(),
    );

    // the capability projection resolves against the registries (a
    // capability bundles a SUBSET — the platform surfaces healthz,
    // readyz and platform_contract_read honestly belong to no capability)
    expect(capabilitiesJson.capabilities).toHaveLength(INTEGRATION_CAPABILITIES.length);
    for (const capability of capabilitiesJson.capabilities) {
      expect(capabilityIds.has(capability.id), `capability "${capability.id}"`).toBe(true);
      for (const operationId of capability.operation_ids) {
        expect(coverageIds).toContain(operationId);
      }
    }
  });

  it("carries the 11 safety rules and the ShareNet boundary inside the rendered context", () => {
    const rendered = renderIntegrationContextJson();
    for (const rule of SAFETY_RULES) {
      expect(rendered.includes(rule), `the context JSON must state: ${rule}`).toBe(true);
    }
    const contextJson = JSON.parse(rendered) as LlmContextJson;
    expect(contextJson.webhooks.frozen_event_types).toEqual([...WEBHOOK_EVENT_TYPES]);
    expect(contextJson.workflow_sequences.patterns).toHaveLength(5);
  });
});

describe("the text renderings — operator content preserved, ShareNet boundary verbatim", () => {
  it("llms.txt keeps the ShareNet pattern section and its boundary rule", () => {
    const txt = renderLlmsTxt();
    expect(txt).toContain("ShareNet pattern:");
    expect(txt).toContain(
      "ShareNet keeps authority over content, P2P distribution, publisher trust, delivery receipts and application economics",
    );
    expect(txt).toContain("do not become ADCOS connectivity transactions");
    // the honest authority boundaries of the operator's index survive
    expect(txt).toContain("Webhooks are observations, not canonical business state.");
    expect(txt).toContain("API success does not prove physical connectivity success.");
    expect(txt).toContain("Do not invent endpoints or capabilities; use the published operation registry.");
  });

  it("llms-full.txt keeps the ShareNet reference architecture and its boundary verbatim in meaning", () => {
    const full = renderLlmsFullTxt();
    expect(full).toContain("## ShareNet reference architecture");
    expect(full).toContain(
      "Ordinary device-to-device content transfers remain within ShareNet",
    );
    expect(full).toContain("not put ADCOS into its local `core-transport`");
    expect(full).toContain("Integrate ADCOS above those modules rather than creating direct provider dependencies");
    // the operator's never-list and the §11 safety rules both survive
    expect(full).toContain("## Anti-patterns");
    for (const rule of SAFETY_RULES) {
      expect(full.includes(rule), `llms-full.txt must state: ${rule}`).toBe(true);
    }
    // complete operation coverage: every coverage operation appears with its verbatim path
    const byOperation = new Map(COVERAGE.map((record) => [record.operation, record]));
    for (const [operationId, record] of byOperation) {
      expect(full.includes(`(${operationId})`), `llms-full.txt must enumerate ${operationId}`).toBe(true);
      expect(full.includes(record.path), `llms-full.txt must carry ${operationId}'s path`).toBe(true);
    }
  });
});
