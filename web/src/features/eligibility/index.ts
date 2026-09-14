/**
 * Eligibility feature (Worker 2 — plan Task 6: eligibility/policy presentation).
 *
 * Renders WHY a provider is eligible/ineligible using backend reason data;
 * never recreates the policy engine in TypeScript. Placeholder barrel.
 */

export const ELIGIBILITY_FEATURE = {
  area: "eligibility",
  route: "/networks",
  owner: "worker-2",
  notes: [
    "surface policy constraints without a TypeScript policy engine",
    "backend reason data drives eligibility explanations",
  ],
} as const;
