/**
 * The capability dictionary — what each capability grant UNLOCKS,
 * derived from the coverage REGISTRY (the single source of truth), plus
 * the human label shown on the capability chips.
 *
 * A capability that appears on the application but not in the registry
 * (a future backend grant) still renders — with the honest fallback
 * copy, never an invented explanation. A capability the registry
 * requires but the application lacks is surfaced by the API Explorer /
 * error surfaces VERBATIM (`capability-denied` names it).
 */

import {
  COVERAGE,
  type CoverageRecord,
} from "@/lib/api/coverage";

/** Short human labels for the known capability vocabulary. */
export const CAPABILITY_LABELS: Record<string, string> = {
  "intents:read": "Read intents & contracts",
  "intents:write": "Create intents & drive the lifecycle",
  "usage:read": "Read usage & pricing terms",
  "assurance:read": "Read assurance obligations",
  "leases:read": "Read leases",
  "leases:write": "Grant, renew & revoke leases",
  "webhooks:read": "Read webhook endpoints & deliveries",
  "webhooks:write": "Register webhook endpoints",
};

/** The registry operations a capability unlocks (in registry order). */
export function operationsForCapability(capability: string): CoverageRecord[] {
  return COVERAGE.filter((entry) => entry.requiredCapability === capability);
}

/**
 * The one-line explanation of what a capability unlocks — derived from
 * the registry (method + path list), with an honest fallback for
 * unknown grants.
 */
export function explainCapability(capability: string): string {
  const operations = operationsForCapability(capability);
  if (operations.length === 0) {
    return "No registered console operation requires this capability yet — granted by the platform, not consumed by this console surface.";
  }
  return operations
    .map((entry) => `${entry.method} ${entry.path}`)
    .join(" · ");
}

/** The display label for a capability (verbatim value as fallback). */
export function capabilityLabel(capability: string): string {
  return CAPABILITY_LABELS[capability] ?? capability;
}

/** Is a capability granted to the connected application? */
export function capabilityGranted(
  capability: string,
  capabilities: string[] | null | undefined,
): boolean | null {
  if (!capabilities) return null; // unknown (no application profile)
  if (capability === "") return true; // no capability required
  return capabilities.includes(capability);
}

/** Every capability the registry knows an operation needs. */
export function requiredCapabilities(): string[] {
  const seen: string[] = [];
  for (const entry of COVERAGE) {
    if (entry.requiredCapability && !seen.includes(entry.requiredCapability)) {
      seen.push(entry.requiredCapability);
    }
  }
  return seen.sort();
}
