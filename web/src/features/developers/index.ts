/**
 * Developers feature (Worker 3 — plan Task 9: developer workspace;
 * station A: the developers-core surface).
 *
 * Application identity, capability chips (granted + missing), the
 * honest credentials state view, and the webhook endpoints section
 * (list / register / detail / deliveries). The frozen capability
 * dictionary lives in `capabilities.ts` (NEVER rewritten); the frozen
 * webhook event-type vocabulary lives in `webhook-event-types.ts`.
 */

export const DEVELOPERS_FEATURE = {
  area: "developers",
  route: "/developers",
  owner: "worker-3",
  clientSurface: [
    "applicationSelf",
    "listWebhookEndpoints",
    "registerWebhookEndpoint",
    "getWebhookEndpoint",
    "listDeliveries",
  ],
} as const;

export {
  CAPABILITY_LABELS,
  operationsForCapability,
  explainCapability,
  capabilityLabel,
  capabilityGranted,
  requiredCapabilities,
} from "./capabilities";
export {
  WEBHOOK_EVENT_TYPES,
  WEBHOOK_EVENT_TYPE_COUNT,
  isWebhookEventType,
  type WebhookEventType,
} from "./webhook-event-types";
export { useDevelopersRead } from "./use-developers-read";
export type { DevelopersReadState } from "./use-developers-read";
export { DevelopersWorkspace } from "./developers-workspace";
export { ApplicationIdentityCard } from "./application-identity-card";
export { CapabilityChips } from "./capability-chips";
export { CredentialsState } from "./credentials-state";
export { WebhookEndpointsSection } from "./webhook-endpoints-section";
export { WebhookRegisterDrawer } from "./webhook-register-drawer";
export { WebhookDetailDrawer } from "./webhook-detail-drawer";
export { ConnectGuidance } from "./connect-guidance";
