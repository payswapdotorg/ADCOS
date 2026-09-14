/**
 * Education registry tests — the registry is the console's education
 * contract hub (V2 design §16): 14 concepts, education for EVERY one of
 * the coverage registry's 25 operations, and 7 guides, whose
 * cross-links resolve ONLY against frozen vocabularies — the concept /
 * guide ids of this registry, the operation ids of the coverage
 * registry, the console's route list, the docs IA slugs, the canonical
 * reason codes and the object vocabulary. Drift (an unknown reference,
 * a duplicate id, an operation without education, an invented field)
 * fails HERE, never in the UI. Pure data-contract tests: no network,
 * fetch is never called, everything is deterministic.
 */

import { describe, expect, it } from "vitest";
import { COVERAGE } from "@/lib/api/coverage";
import {
  CONCEPTS,
  EDUCATION_REGISTRY,
  GUIDES,
  OPERATION_EDUCATION,
  getConcept,
  getGuide,
  getOperationEducation,
} from "@/lib/education";
import type { LearningLink } from "@/lib/education";

/** The 14 core concept ids — the frozen V2 design §8 list plus the demo context. */
const CORE_CONCEPT_IDS: string[] = [
  "connectivity-contract",
  "provider-capability",
  "offer",
  "eligibility",
  "policy",
  "execution-plan",
  "fulfillment",
  "assurance",
  "evidence",
  "replan-failover",
  "provider-adapter-boundary",
  "application-capability",
  "webhook",
  "demo-fulfillment-journey",
];

/** The 7 guide ids — the frozen V2 design §11 playbook list. */
const GUIDE_IDS: string[] = [
  "first-connectivity-application",
  "understand-connectivity-contract",
  "understand-provider-selection",
  "diagnose-fulfillment-failure",
  "handle-degraded-connectivity",
  "integrate-adcos-api",
  "integrate-provider-adapter",
];

/**
 * The console routes a LearningLink may target (the frozen console
 * surface — every entry is a real app route).
 */
const CONSOLE_ROUTES: string[] = [
  "/",
  "/connectivity",
  "/connectivity/contracts/[id]",
  "/networks",
  "/fulfillment",
  "/evidence",
  "/assurance",
  "/developers",
  "/developers/explorer",
  "/developers/requests",
  "/settings",
  "/settings/errors",
];

/**
 * The docs IA slugs (the frozen V2 design §9 tree) a docs link may
 * target. The docs surfaces (plan Task 3) consume the same IA.
 */
const DOCS_IDS: string[] = [
  "what-is-adcos",
  "quickstart",
  "how-adcos-works",
  "first-connectivity-contract",
  "concepts",
  "guides",
  "api",
  "api/authentication",
  "api/contracts",
  "api/offers",
  "api/plans",
  "api/fulfillment",
  "api/evidence",
  "api/assurance",
  "api/webhooks",
  "sdks",
  "errors",
  "troubleshooting",
  "reference",
];

/**
 * The canonical reason-code vocabulary — extracted verbatim from the
 * REASON_PRESENTATION map in src/lib/api/errors.ts (the module keeps
 * the map private; this frozen table pins the vocabulary the education
 * registry's relatedErrors / relatedTroubleshooting may use).
 */
const REASON_CODES: string[] = [
  "authentication-invalid",
  "authentication-expired",
  "environment-mismatch",
  "capability-denied",
  "version-unsupported",
  "rate-limited",
  "idempotency-key-required",
  "idempotency-conflict",
  "pagination-invalid",
  "filter-invalid",
  "resource-unknown",
  "route-unknown",
  "invalid-input",
  "invalid-transition",
  "invalid-state",
  "unknown-contract",
  "contract-terminal",
  "constraint-immutable",
  "not-yet-valid",
  "expired",
  "temporal-invalid",
  "secret-rejected",
  "vocabulary",
  "sequence-conflict",
  "replay-stale",
  "journal-tamper",
  "store-failed",
  "payload-too-large",
  "malformed-json",
  "invalid-request-body",
  "backend-unreachable",
  "internal-error",
];

/**
 * The backend object vocabulary — the exported resource/interface
 * names of src/lib/api/types.ts, the only object names a concept's
 * relatedObjects may carry.
 */
const OBJECT_VOCABULARY: string[] = [
  "Application",
  "Contract",
  "ContractLifecycle",
  "ContractUsage",
  "ContractAssurance",
  "Lease",
  "WebhookEndpoint",
  "WebhookDelivery",
  "DemoDocument",
  "DemoBoundaryEntry",
  "OpaqueReference",
  "HardConstraint",
];

/* ------------------------------------------------------------------ *
 * The cross-reference walker (shared by the resolution tests)
 * ------------------------------------------------------------------ */

const CONCEPT_IDS = new Set(CORE_CONCEPT_IDS);
const GUIDE_ID_SET = new Set(GUIDE_IDS);
const ROUTE_SET = new Set(CONSOLE_ROUTES);
const DOCS_ID_SET = new Set(DOCS_IDS);
const OPERATION_IDS = new Set(COVERAGE.map((record) => record.operation));
const REASON_SET = new Set(REASON_CODES);
const OBJECT_SET = new Set(OBJECT_VOCABULARY);

const VOCABULARIES: Record<LearningLink["kind"], Set<string>> = {
  concept: CONCEPT_IDS,
  operation: OPERATION_IDS,
  guide: GUIDE_ID_SET,
  route: ROUTE_SET,
  docs: DOCS_ID_SET,
};

const unresolved: string[] = [];
let checkedCount = 0;

function checkRef(where: string, kind: LearningLink["kind"], id: string): void {
  checkedCount += 1;
  if (!VOCABULARIES[kind].has(id)) {
    unresolved.push(`${where}: unknown ${kind} reference "${id}"`);
  }
}

function checkLink(where: string, link: LearningLink): void {
  checkRef(where, link.kind, link.id);
}

function checkMember(where: string, vocabulary: Set<string>, kind: string, id: string): void {
  checkedCount += 1;
  if (!vocabulary.has(id)) {
    unresolved.push(`${where}: unknown ${kind} "${id}"`);
  }
}

for (const concept of CONCEPTS) {
  concept.prerequisites.forEach((id, index) =>
    checkMember(`concept "${concept.id}" prerequisites[${index}]`, CONCEPT_IDS, "concept id", id),
  );
  concept.relatedObjects.forEach((id, index) =>
    checkMember(
      `concept "${concept.id}" relatedObjects[${index}]`,
      OBJECT_SET,
      "object vocabulary member",
      id,
    ),
  );
  concept.relatedOperations.forEach((id, index) =>
    checkMember(
      `concept "${concept.id}" relatedOperations[${index}]`,
      OPERATION_IDS,
      "operation id",
      id,
    ),
  );
  concept.relatedGuides.forEach((id, index) =>
    checkMember(`concept "${concept.id}" relatedGuides[${index}]`, GUIDE_ID_SET, "guide id", id),
  );
  if (concept.apiLook) {
    checkRef(`concept "${concept.id}" apiLook.operationId`, "operation", concept.apiLook.operationId);
  }
  if (concept.runnableExample) {
    checkRef(
      `concept "${concept.id}" runnableExample.operationId`,
      "operation",
      concept.runnableExample.operationId,
    );
  }
  concept.nextSteps.forEach((link, index) =>
    checkLink(`concept "${concept.id}" nextSteps[${index}]`, link),
  );
  concept.relatedTroubleshooting.forEach((code, index) =>
    checkMember(
      `concept "${concept.id}" relatedTroubleshooting[${index}]`,
      REASON_SET,
      "reason code",
      code,
    ),
  );
}

for (const entry of OPERATION_EDUCATION) {
  checkRef(`operation education "${entry.operation}" .operation`, "operation", entry.operation);
  entry.relatedConcepts.forEach((id, index) =>
    checkMember(
      `operation "${entry.operation}" relatedConcepts[${index}]`,
      CONCEPT_IDS,
      "concept id",
      id,
    ),
  );
  if (entry.nextOperation) {
    checkRef(`operation "${entry.operation}" nextOperation`, "operation", entry.nextOperation);
  }
  entry.relatedErrors.forEach((code, index) =>
    checkMember(`operation "${entry.operation}" relatedErrors[${index}]`, REASON_SET, "reason code", code),
  );
}

for (const guide of GUIDES) {
  guide.steps.forEach((step, index) => {
    if (step.link) {
      checkLink(`guide "${guide.id}" steps[${index}].link`, step.link);
    }
  });
  guide.relatedConcepts.forEach((id, index) =>
    checkMember(`guide "${guide.id}" relatedConcepts[${index}]`, CONCEPT_IDS, "concept id", id),
  );
  guide.relatedOperations.forEach((id, index) =>
    checkMember(
      `guide "${guide.id}" relatedOperations[${index}]`,
      OPERATION_IDS,
      "operation id",
      id,
    ),
  );
}

/** Sentence count for the summary length guard (splits after . ! ? followed by whitespace). */
function sentenceCount(text: string): number {
  return text
    .split(/(?<=[.!?])\s+/)
    .filter((part) => part.trim().length > 0).length;
}

describe("the education registry — ids and aggregation", () => {
  it("contains exactly the 14 core concepts, 25 operation records and 7 guides", () => {
    expect(CONCEPTS).toHaveLength(14);
    expect(OPERATION_EDUCATION).toHaveLength(25);
    expect(GUIDES).toHaveLength(7);
  });

  it("has no duplicate concept ids, guide ids or operation entries", () => {
    const conceptIds = CONCEPTS.map((concept) => concept.id);
    expect(new Set(conceptIds).size).toBe(conceptIds.length);

    const guideIds = GUIDES.map((guide) => guide.id);
    expect(new Set(guideIds).size).toBe(guideIds.length);

    const operationIds = OPERATION_EDUCATION.map((entry) => entry.operation);
    expect(new Set(operationIds).size).toBe(operationIds.length);
  });

  it("carries EXACTLY the fourteen core concept ids (the frozen §8 list + the demo context)", () => {
    expect([...CONCEPTS.map((concept) => concept.id)].sort()).toEqual([...CORE_CONCEPT_IDS].sort());
  });

  it("carries EXACTLY the seven guide ids (the frozen §11 playbook list)", () => {
    expect([...GUIDES.map((guide) => guide.id)].sort()).toEqual([...GUIDE_IDS].sort());
  });

  it("aggregates the same three registries (a view, never a second authority)", () => {
    expect(EDUCATION_REGISTRY.concepts).toBe(CONCEPTS);
    expect(EDUCATION_REGISTRY.operations).toBe(OPERATION_EDUCATION);
    expect(EDUCATION_REGISTRY.guides).toBe(GUIDES);
  });
});

describe("the education registry — cross-link integrity", () => {
  it("resolves every prerequisite, relatedOperations, relatedGuides, relatedConcepts, nextOperation, apiLook, runnableExample and LearningLink reference", () => {
    expect(
      unresolved,
      unresolved.length > 0
        ? `first unresolved reference: ${unresolved[0]}`
        : "every reference resolves",
    ).toEqual([]);
  });

  it("pins the number of machine-checked references (the contract hub's size)", () => {
    expect(checkedCount).toBe(449);
  });

  it("targets only existing console routes", () => {
    const routeLinks: string[] = [];
    for (const concept of CONCEPTS) {
      for (const link of concept.nextSteps) {
        if (link.kind === "route") routeLinks.push(`${concept.id} → ${link.id}`);
      }
    }
    for (const guide of GUIDES) {
      for (const step of guide.steps) {
        if (step.link?.kind === "route") routeLinks.push(`${guide.id} → ${step.link.id}`);
      }
    }
    expect(routeLinks.length).toBeGreaterThan(0);
    const bad = routeLinks.filter((ref) => !ROUTE_SET.has(ref.split(" → ")[1] ?? ""));
    expect(bad, `unknown route links: ${bad.join(", ")}`).toEqual([]);
    for (const link of routeLinks) {
      expect(CONSOLE_ROUTES).toContain(link.split(" → ")[1]);
    }
  });
});

describe("the education registry — the §16 coverage rule", () => {
  it("gives EVERY coverage operation an education record (the module-load guard, duplicated as a test)", () => {
    const educated = new Set<string>(OPERATION_EDUCATION.map((entry) => entry.operation));
    for (const record of COVERAGE) {
      expect(
        educated.has(record.operation),
        `operation ${record.operation} lacks education`,
      ).toBe(true);
    }
    expect(educated.size).toBe(COVERAGE.length);
  });

  it("marks all 25 operations user-actionable — no internal-only escapes", () => {
    for (const entry of OPERATION_EDUCATION) {
      expect(entry.userActionable, `${entry.operation} must be user-actionable or marked internalOnly`).toBe(true);
      expect(entry.internalOnly ?? false).toBe(false);
    }
  });

  it("gives every user-actionable operation a purpose and field explanations", () => {
    for (const entry of OPERATION_EDUCATION) {
      expect(entry.purpose.trim().length, `${entry.operation} purpose`).toBeGreaterThan(10);
      expect(entry.prerequisites.trim().length, `${entry.operation} prerequisites`).toBeGreaterThan(5);
      expect(entry.lifecyclePosition.trim().length, `${entry.operation} lifecyclePosition`).toBeGreaterThan(5);
      expect(entry.typicalSequence.trim().length, `${entry.operation} typicalSequence`).toBeGreaterThan(10);
      expect(entry.fieldExplanations.length, `${entry.operation} fieldExplanations`).toBeGreaterThan(0);
    }
  });

  it("explains EXACTLY the coverage registry's example fields for every mutation (no invented fields)", () => {
    const byOperation = new Map(COVERAGE.map((record) => [record.operation, record]));
    for (const entry of OPERATION_EDUCATION) {
      const record = byOperation.get(entry.operation);
      expect(record, `${entry.operation} exists in COVERAGE`).toBeDefined();
      if (!record) continue;

      const exampleKeys = Object.keys(record.example ?? {});
      if (exampleKeys.length > 0) {
        const explained = new Set(entry.fieldExplanations.map((field) => field.field));
        for (const key of exampleKeys) {
          expect(
            explained.has(key),
            `${entry.operation} must explain example field "${key}"`,
          ).toBe(true);
        }
      }
      if (!record.mutation && exampleKeys.length === 0) {
        // the honest no-body case, noted in the data itself
        const fields = entry.fieldExplanations.map((field) => field.field);
        expect(
          fields.includes("request body"),
          `${entry.operation} (bodyless GET) must note the no-request-body case`,
        ).toBe(true);
      }
    }
  });
});

describe("the education registry — canonical vocabularies", () => {
  it("uses only canonical reason codes in relatedErrors and relatedTroubleshooting", () => {
    for (const entry of OPERATION_EDUCATION) {
      for (const code of entry.relatedErrors) {
        expect(REASON_SET.has(code), `${entry.operation} relatedErrors "${code}"`).toBe(true);
      }
    }
    for (const concept of CONCEPTS) {
      for (const code of concept.relatedTroubleshooting) {
        expect(REASON_SET.has(code), `${concept.id} relatedTroubleshooting "${code}"`).toBe(true);
      }
    }
  });
});

describe("the education registry — concision and lookup helpers", () => {
  it("keeps every concept summary within ~2 sentences (concise by construction)", () => {
    for (const concept of CONCEPTS) {
      const sentences = sentenceCount(concept.summary);
      expect(
        sentences,
        `concept "${concept.id}" summary has ${sentences} sentences`,
      ).toBeLessThanOrEqual(2);
      expect(concept.summary.trim().length).toBeGreaterThan(20);
      expect(concept.whyItMatters.trim().length).toBeGreaterThan(20);
      expect(concept.whenToUse.trim().length).toBeGreaterThan(20);
      expect(concept.whatHappens.trim().length).toBeGreaterThan(40);
    }
  });

  it("gives every guide step a title and an honest detail", () => {
    for (const guide of GUIDES) {
      expect(guide.title.trim().length).toBeGreaterThan(5);
      expect(guide.purpose.trim().length).toBeGreaterThan(20);
      expect(guide.steps.length).toBeGreaterThanOrEqual(5);
      for (const step of guide.steps) {
        expect(step.title.trim().length).toBeGreaterThan(3);
        expect(step.detail.trim().length).toBeGreaterThan(30);
      }
    }
  });

  it("resolves known ids and returns undefined for unknown ids (honest unknown states)", () => {
    // known ids resolve
    for (const id of CORE_CONCEPT_IDS) {
      expect(getConcept(id)?.id).toBe(id);
    }
    for (const record of COVERAGE) {
      expect(getOperationEducation(record.operation)?.operation).toBe(record.operation);
    }
    for (const id of GUIDE_IDS) {
      expect(getGuide(id)?.id).toBe(id);
    }
    // unknown ids are undefined — callers must render honest unknown states
    expect(getConcept("not-a-concept")).toBeUndefined();
    expect(getConcept("")).toBeUndefined();
    expect(getOperationEducation("offer_publish")).toBeUndefined(); // W046-era, demoted
    expect(getOperationEducation("reservations")).toBeUndefined();
    expect(getGuide("not-a-guide")).toBeUndefined();
    expect(getGuide("")).toBeUndefined();
  });
});
