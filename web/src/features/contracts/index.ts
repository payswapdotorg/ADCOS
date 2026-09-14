/**
 * Contracts feature (Worker 2 — plan Task 5: connectivity contracts + builder).
 *
 * Consumes Worker 1's typed client (`@/lib/api/client`) — never a private
 * transport. The barrel publishes the three surfaces (index, detail,
 * builder), the shared mutation pattern, and the PURE serialization seam
 * the builder tests assert constraint preservation on.
 */

export { ContractsIndexView } from "./contracts-index-view";
export { ContractDetailView } from "./contract-detail-view";
export { BuilderView } from "./builder/builder-view";
export { ConnectGuidance } from "./connect-guidance";
export { MutationForm, StateOutcome, nowRfc3339 } from "./mutation-form";
export {
  AcceptOffersCard,
  ActivateCard,
} from "./next-step-cards";
export {
  LeaseWindowDrawer,
  RevokeLeaseDrawer,
  TerminateDrawer,
} from "./contract-mutation-drawers";
export {
  GUIDED_MEMBER_NAMES,
  buildIntentBody,
  canonicalIntentBody,
  defaultGuidedState,
  guidedToIntentBody,
  mergePreservedMembers,
  parseAdvancedToGuided,
  parseParamValue,
  splitCommaList,
  validateGuidedState,
  type GuidedBuilderState,
  type GuidedConstraintDraft,
  type GuidedParamRow,
  type GuidedRefDraft,
  type GuidedValueDraft,
} from "./builder/serialization";

/** Feature registry descriptor (from the foundation placeholder, kept current). */
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
    "grantLease",
    "listLeases",
    "renewLease",
    "revokeLease",
  ],
} as const;
