/**
 * Integration registry tests — the registry is the console's Build with
 * ADCOS contract hub (the 2026-09-15 design §12): 5 integration
 * patterns, 4 capabilities and the canonical per-pattern workflows,
 * whose every cross-reference resolves ONLY against frozen
 * vocabularies — the operation ids of the coverage registry, the
 * concept ids of the education registry, the capability ids of the
 * integration capability registry, and the frozen webhook event-type
 * vocabulary. Drift (an unknown reference, a duplicate id, a lifecycle
 * stage mapped outside its pattern, a contradictory ownership entry)
 * fails HERE and at module load, never in the UI. The blueprint is
 * presentation state only: its required operations are always a subset
 * of the pattern's own registry-pinned operation set. Pure data-contract
 * tests: no network, fetch is never called, everything is deterministic.
 */

import { describe, expect, it } from "vitest";
import { COVERAGE } from "@/lib/api/coverage";
import { CONCEPTS } from "@/lib/education/concepts";
import { WEBHOOK_EVENT_TYPES } from "@/features/developers/webhook-event-types";
import { INTEGRATION_PATTERNS, patternsUsingOperation } from "@/lib/integration/patterns";
import {
  INTEGRATION_CAPABILITIES,
  integrationCapabilityById,
} from "@/lib/integration/capabilities";
import { INTEGRATION_WORKFLOWS } from "@/lib/integration/workflows";
import { buildIntegrationBlueprint } from "@/lib/integration/blueprint";
import type { IntegrationPatternId } from "@/lib/integration/types";

/** The 5 pattern ids — the frozen design §5 pattern vocabulary. */
const PATTERN_IDS: IntegrationPatternId[] = [
  "application",
  "gateway-relay",
  "fleet-subscriber",
  "provider-adapter",
  "marketplace-orchestration",
];

/** The canonical design-§4 lifecycle stages, in order. */
const CANONICAL_STAGES: string[] = [
  "Connectivity Intent",
  "Eligibility / Policy",
  "Provider Offers",
  "ConnectivityContract",
  "Execution Plan",
  "Provider realization",
  "Evidence + Assurance",
];

/* ------------------------------------------------------------------ *
 * The cross-reference walker (shared by the resolution tests)
 * ------------------------------------------------------------------ */

const COVERAGE_OPERATION_IDS = new Set(COVERAGE.map((record) => record.operation));
const CONCEPT_IDS = new Set(CONCEPTS.map((concept) => concept.id));
const CAPABILITY_IDS = new Set(INTEGRATION_CAPABILITIES.map((capability) => capability.id));
const WEBHOOK_EVENT_SET = new Set<string>(WEBHOOK_EVENT_TYPES);

const unresolved: string[] = [];
let checkedCount = 0;

function checkMember(where: string, vocabulary: Set<string>, kind: string, id: string): void {
  checkedCount += 1;
  if (!vocabulary.has(id)) {
    unresolved.push(`${where}: unknown ${kind} "${id}"`);
  }
}

for (const pattern of INTEGRATION_PATTERNS) {
  pattern.operationIds.forEach((id, index) =>
    checkMember(`pattern "${pattern.id}" operationIds[${index}]`, COVERAGE_OPERATION_IDS, "operation id", id),
  );
  pattern.conceptIds.forEach((id, index) =>
    checkMember(`pattern "${pattern.id}" conceptIds[${index}]`, CONCEPT_IDS, "concept id", id),
  );
  pattern.capabilityIds.forEach((id, index) =>
    checkMember(`pattern "${pattern.id}" capabilityIds[${index}]`, CAPABILITY_IDS, "capability id", id),
  );
  for (const step of pattern.lifecycle) {
    if (step.operationId !== undefined) {
      checkMember(
        `pattern "${pattern.id}" lifecycle stage "${step.stage}"`,
        COVERAGE_OPERATION_IDS,
        "operation id",
        step.operationId,
      );
      checkedCount += 1;
      if (!pattern.operationIds.includes(step.operationId)) {
        unresolved.push(
          `pattern "${pattern.id}" lifecycle stage "${step.stage}" maps to operation "${step.operationId}" outside the pattern's own operation set`,
        );
      }
    }
  }
}

for (const capability of INTEGRATION_CAPABILITIES) {
  capability.operationIds.forEach((id, index) =>
    checkMember(
      `capability "${capability.id}" operationIds[${index}]`,
      COVERAGE_OPERATION_IDS,
      "operation id",
      id,
    ),
  );
}

describe("the integration registry — ids and shapes", () => {
  it("contains exactly the 5 patterns and the 4 capabilities, with no duplicate ids", () => {
    expect(INTEGRATION_PATTERNS).toHaveLength(5);
    expect(INTEGRATION_CAPABILITIES).toHaveLength(4);

    const patternIds = INTEGRATION_PATTERNS.map((pattern) => pattern.id);
    expect(new Set(patternIds).size).toBe(patternIds.length);
    expect([...patternIds].sort()).toEqual([...PATTERN_IDS].sort());

    const capabilityIds = INTEGRATION_CAPABILITIES.map((capability) => capability.id);
    expect(new Set(capabilityIds).size).toBe(capabilityIds.length);
  });

  it("gives every pattern a non-empty summary, ownership lists, webhook/failure notes and anti-patterns", () => {
    for (const pattern of INTEGRATION_PATTERNS) {
      expect(pattern.title.trim().length, `${pattern.id} title`).toBeGreaterThan(5);
      expect(pattern.summary.trim().length, `${pattern.id} summary`).toBeGreaterThan(20);
      expect(pattern.applicationOwns.length, `${pattern.id} applicationOwns`).toBeGreaterThan(0);
      expect(pattern.adcosOwns.length, `${pattern.id} adcosOwns`).toBeGreaterThan(0);
      expect(pattern.providerOwns.length, `${pattern.id} providerOwns`).toBeGreaterThan(0);
      expect(pattern.operationIds.length, `${pattern.id} operationIds`).toBeGreaterThan(0);
      expect(pattern.capabilityIds.length, `${pattern.id} capabilityIds`).toBeGreaterThan(0);
      expect(pattern.webhookNote.trim().length, `${pattern.id} webhookNote`).toBeGreaterThan(10);
      expect(pattern.failureNote.trim().length, `${pattern.id} failureNote`).toBeGreaterThan(10);
      expect(pattern.antiPatterns.length, `${pattern.id} antiPatterns`).toBeGreaterThan(0);
    }
  });
});

describe("the integration registry — cross-link integrity", () => {
  it("resolves every pattern operation/concept/capability reference, every capability operation reference and every lifecycle mapping", () => {
    expect(
      unresolved,
      unresolved.length > 0
        ? `first unresolved reference: ${unresolved[0]}`
        : "every reference resolves",
    ).toEqual([]);
  });

  it("pins the number of machine-checked references (the contract hub's size)", () => {
    expect(checkedCount).toBe(138);
  });

  it("maps each pattern's lifecycle onto EXACTLY the canonical design-§4 stages, in order", () => {
    for (const pattern of INTEGRATION_PATTERNS) {
      expect(
        pattern.lifecycle.map((step) => step.stage),
        `${pattern.id} lifecycle stages`,
      ).toEqual(CANONICAL_STAGES);
      for (const step of pattern.lifecycle) {
        expect(step.note.trim().length, `${pattern.id} stage "${step.stage}" note`).toBeGreaterThan(20);
      }
    }
  });

  it("keeps ownership exclusive — no string appears under two authorities in a pattern", () => {
    for (const pattern of INTEGRATION_PATTERNS) {
      const lists = [pattern.applicationOwns, pattern.adcosOwns, pattern.providerOwns];
      for (let i = 0; i < lists.length; i += 1) {
        for (let j = i + 1; j < lists.length; j += 1) {
          const clash = lists[i].find((entry) => lists[j].includes(entry));
          expect(
            clash,
            `${pattern.id} lists "${clash}" under two authorities — ownership is exclusive`,
          ).toBeUndefined();
        }
      }
    }
  });

  it("is the workflow lookup surface: INTEGRATION_WORKFLOWS carries each pattern's own lifecycle (a view, never a second authority)", () => {
    for (const pattern of INTEGRATION_PATTERNS) {
      expect(INTEGRATION_WORKFLOWS[pattern.id]).toBe(pattern.lifecycle);
    }
    expect(Object.keys(INTEGRATION_WORKFLOWS).sort()).toEqual([...PATTERN_IDS].sort());
  });
});

describe("the integration blueprint — presentation state only", () => {
  it("returns undefined for an unknown pattern id (honest unknown state)", () => {
    expect(
      buildIntegrationBlueprint("not-a-pattern" as IntegrationPatternId, []),
    ).toBeUndefined();
  });

  it("filters unknown capability ids out instead of throwing", () => {
    const strict = buildIntegrationBlueprint("application", ["application-connectivity"]);
    const noisy = buildIntegrationBlueprint("application", [
      "application-connectivity",
      "not-a-capability",
      "",
    ]);
    expect(strict).toBeDefined();
    expect(noisy).toBeDefined();
    expect(noisy?.selectedCapabilityIds).toEqual(["application-connectivity"]);
    expect(noisy?.requiredOperationIds).toEqual(strict?.requiredOperationIds);
  });

  it("derives requiredOperationIds as a subset of the pattern's own operation set, ordered by the canonical lifecycle", () => {
    for (const pattern of INTEGRATION_PATTERNS) {
      const blueprint = buildIntegrationBlueprint(pattern.id, pattern.capabilityIds);
      expect(blueprint, `${pattern.id} blueprint`).toBeDefined();
      if (!blueprint) continue;
      expect(blueprint.patternId).toBe(pattern.id);
      expect(blueprint.selectedCapabilityIds).toEqual(pattern.capabilityIds);
      for (const operationId of blueprint.requiredOperationIds) {
        expect(
          pattern.operationIds.includes(operationId),
          `${pattern.id} blueprint requires "${operationId}" outside the pattern's operation set`,
        ).toBe(true);
      }
      // the lifecycle-essential operations are always present
      for (const step of pattern.lifecycle) {
        if (step.operationId !== undefined) {
          expect(blueprint.requiredOperationIds).toContain(step.operationId);
        }
      }
      // canonical order: intent before offers before contract before assurance
      const ranks: Record<string, number> = {
        intent_create: 1,
        offers_accept: 2,
        contract_activate: 3,
        contract_assurance: 4,
      };
      const present = Object.keys(ranks).filter((id) => blueprint.requiredOperationIds.includes(id));
      for (let i = 1; i < present.length; i += 1) {
        expect(
          ranks[present[i]] - ranks[present[i - 1]],
          `${pattern.id} orders ${present[i - 1]} before ${present[i]}`,
        ).toBeGreaterThan(0);
      }
    }
  });

  it("recommends only frozen-vocabulary webhook event ids, derived from the pattern's own operations", () => {
    for (const pattern of INTEGRATION_PATTERNS) {
      const blueprint = buildIntegrationBlueprint(pattern.id, pattern.capabilityIds);
      expect(blueprint, `${pattern.id} blueprint`).toBeDefined();
      if (!blueprint) continue;
      expect(blueprint.recommendedWebhookEventIds.length, `${pattern.id} events`).toBeGreaterThan(0);
      for (const event of blueprint.recommendedWebhookEventIds) {
        expect(
          WEBHOOK_EVENT_SET.has(event),
          `${pattern.id} recommends webhook event "${event}" outside the frozen vocabulary`,
        ).toBe(true);
      }
    }
  });

  it("carries non-empty owned-object arrays, boundary rules (anti-patterns + standing rules), failure modes and 3-5 next steps", () => {
    for (const pattern of INTEGRATION_PATTERNS) {
      const blueprint = buildIntegrationBlueprint(pattern.id, pattern.capabilityIds);
      if (!blueprint) continue;
      expect(blueprint.applicationOwnedObjects.length).toBeGreaterThan(0);
      expect(blueprint.adcosOwnedObjects.length).toBeGreaterThan(0);
      expect(blueprint.providerOwnedObjects.length).toBeGreaterThan(0);
      expect(blueprint.applicationOwnedObjects).toEqual(pattern.applicationOwns);
      expect(blueprint.adcosOwnedObjects).toEqual(pattern.adcosOwns);
      expect(blueprint.providerOwnedObjects).toEqual(pattern.providerOwns);

      // the pattern's anti-patterns are restated as boundary rules
      for (const antiPattern of pattern.antiPatterns) {
        expect(
          blueprint.boundaryRules.some((rule) => rule.includes(antiPattern)),
          `${pattern.id} boundary rules must restate "${antiPattern}"`,
        ).toBe(true);
      }
      // the standing design-§3 rules are always present
      expect(blueprint.boundaryRules.some((rule) => /sole durable ADCOS contract authority/.test(rule))).toBe(true);
      expect(blueprint.boundaryRules.some((rule) => /never appear in application-facing/.test(rule))).toBe(true);
      expect(blueprint.boundaryRules.some((rule) => /observations, never canonical/.test(rule))).toBe(true);
      expect(blueprint.boundaryRules.some((rule) => /never proof of physical connectivity success/.test(rule))).toBe(true);
      expect(blueprint.boundaryRules.some((rule) => /distinct evidence classes/.test(rule))).toBe(true);

      expect(blueprint.failureModes[0]).toBe(pattern.failureNote);
      expect(blueprint.failureModes.length).toBeGreaterThanOrEqual(3);
      expect(blueprint.nextSteps.length).toBeGreaterThanOrEqual(3);
      expect(blueprint.nextSteps.length).toBeLessThanOrEqual(5);
      for (const step of blueprint.nextSteps) {
        expect(step.includes("/docs") || step.includes("/developers/explorer") || step.includes("/build")).toBe(true);
      }
    }
  });
});

describe("the integration registry — lookups", () => {
  it("patternsUsingOperation returns only patterns whose operationIds include the id", () => {
    expect(patternsUsingOperation("intent_create").map((pattern) => pattern.id).sort()).toEqual(
      [...PATTERN_IDS].sort(),
    );
    expect(patternsUsingOperation("lease_revoke").map((pattern) => pattern.id)).toEqual([
      "fleet-subscriber",
    ]);
    expect(patternsUsingOperation("endpoint_register").map((pattern) => pattern.id)).toEqual([
      "marketplace-orchestration",
    ]);
    // platform surfaces belong to no pattern
    expect(patternsUsingOperation("healthz")).toEqual([]);
    expect(patternsUsingOperation("readyz")).toEqual([]);
    expect(patternsUsingOperation("demo_contract_fulfillment")).toEqual([]);
    expect(patternsUsingOperation("platform_contract_read")).toEqual([]);
    // unknown ids resolve to nothing (honest unknown state)
    expect(patternsUsingOperation("offer_publish")).toEqual([]);
    expect(patternsUsingOperation("")).toEqual([]);
  });

  it("integrationCapabilityById resolves known ids and returns undefined for unknown ids", () => {
    for (const capability of INTEGRATION_CAPABILITIES) {
      expect(integrationCapabilityById(capability.id)?.id).toBe(capability.id);
    }
    expect(integrationCapabilityById("not-a-capability")).toBeUndefined();
    expect(integrationCapabilityById("")).toBeUndefined();
  });
});
