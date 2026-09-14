/**
 * Contracts feature (Worker 2 — plan Task 5: connectivity contracts + builder).
 *
 * Consumes Worker 1's typed client (`@/lib/api/client`) — never a private
 * transport. Placeholder barrel until Worker 2 lands list/detail/builder.
 */

export const CONTRACTS_FEATURE = {
  area: "contracts",
  route: "/connectivity",
  owner: "worker-2",
  clientSurface: [
    "createIntent",
    "listIntents",
    "getIntent",
    "getIntentLifecycle",
    "acceptOffers",
    "activateContract",
    "listContracts",
    "getContract",
    "getContractUsage",
    "getContractAssurance",
    "terminateContract",
  ],
} as const;
