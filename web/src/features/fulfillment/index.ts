/**
 * Fulfillment feature (Worker 2 — plan Task 7: fulfillment + execution).
 *
 * The chain Contract → Plan → Execution → Provider → Evidence → Assurance
 * with actual milestones and typed failures. Placeholder barrel.
 */

export const FULFILLMENT_FEATURE = {
  area: "fulfillment",
  route: "/fulfillment",
  owner: "worker-2",
  chain: ["Contract", "Plan", "Execution", "Provider", "Evidence", "Assurance"],
} as const;
