/**
 * The FROZEN webhook event-type vocabulary (backend
 * `developerapi/webhooks.py` `EVENT_TYPES`, M013 re-targeting).
 *
 * This is the ONLY set the registration form can subscribe — it renders
 * as a selectable checkbox list and free text is IMPOSSIBLE by
 * construction (work order hard constraint #4: no text input for event
 * types exists anywhere in this feature). The backend rejects any
 * other value with `invalid-input` ("event type … is not in the frozen
 * vocabulary"), and at least one type is required.
 */

/** The frozen vocabulary, verbatim and complete. */
export const WEBHOOK_EVENT_TYPES = [
  "connectivity_intent.created",
  "connectivity_contract.offers_selected",
  "connectivity_contract.activated",
  "connectivity_contract.terminated",
  "connectivity_contract.state_changed",
  "connectivity_lease.granted",
  "connectivity_lease.renewed",
  "connectivity_lease.revoked",
  "webhook_endpoint.registered",
] as const;

/** One member of the frozen vocabulary. */
export type WebhookEventType = (typeof WEBHOOK_EVENT_TYPES)[number];

/** The vocabulary size (pinned by tests). */
export const WEBHOOK_EVENT_TYPE_COUNT = WEBHOOK_EVENT_TYPES.length;

/** Is a value a member of the frozen vocabulary? */
export function isWebhookEventType(value: string): value is WebhookEventType {
  return (WEBHOOK_EVENT_TYPES as readonly string[]).includes(value);
}
