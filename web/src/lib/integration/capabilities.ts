/**
 * The Build with ADCOS integration registry — the CAPABILITIES.
 *
 * The 2026-09-15 program, Task 1 of the frozen plan: the four supported
 * integration capabilities, ported from the operator's hand-authored
 * `web/public/adcos-capabilities.json` into typed registry records
 * (same ids, titles, descriptions and operation lists). This file is
 * now the capability authority the JSON asset is GENERATED from — the
 * public file is an artifact of this module, never a second catalog.
 *
 * The no-second-authority rule: every `operationIds` entry is a real
 * coverage-registry operation id (`@/lib/api/coverage`) verbatim — the
 * module-load guard below throws at import time if a capability names
 * an operation the coverage registry does not carry. A capability is an
 * outcome bundle over EXISTING operations; it can never introduce an
 * endpoint the accepted boundary does not expose.
 */

import { COVERAGE } from "@/lib/api/coverage";
import type { IntegrationCapability } from "./types";

/**
 * The capability registry — the outcomes a product can select in the
 * Build experience. Exactly the operator's four, byte-ported.
 */
export const INTEGRATION_CAPABILITIES: IntegrationCapability[] = [
  {
    id: "application-connectivity",
    title: "Application connectivity",
    description:
      "Describe and manage technology-neutral connectivity outcomes for an application or service.",
    operationIds: [
      "application_self",
      "intent_create",
      "intents_list",
      "intent_get",
      "intent_lifecycle",
      "offers_accept",
      "contract_activate",
      "contracts_list",
      "contract_get",
      "contract_usage",
      "contract_assurance",
      "contract_terminate",
    ],
  },
  {
    id: "leases",
    title: "Bounded connectivity leases",
    description:
      "Grant, inspect, renew and revoke bounded validity windows over active connectivity contracts.",
    operationIds: ["lease_grant", "leases_list", "lease_get", "lease_renew", "lease_revoke"],
  },
  {
    id: "webhook-observations",
    title: "Signed webhook observations",
    description:
      "Receive asynchronous observations about developer-platform events without treating them as a second authority.",
    operationIds: ["endpoints_list", "endpoint_register", "endpoint_get", "deliveries_list"],
  },
  {
    id: "deterministic-reference-demo",
    title: "Deterministic contract fulfillment reference",
    description:
      "Inspect the accepted reference chain from contract boundary through plan, execution and evidence without claiming physical connectivity.",
    operationIds: ["demo_contract_fulfillment"],
  },
];

/** Look up one capability by id — `undefined` for unknown ids (honest unknown state). */
export function integrationCapabilityById(id: string): IntegrationCapability | undefined {
  return INTEGRATION_CAPABILITIES.find((capability) => capability.id === id);
}

/** The capability ids whose operation list includes the operation (derived, never hand-maintained). */
export function capabilitiesUsingOperation(operationId: string): IntegrationCapability[] {
  return INTEGRATION_CAPABILITIES.filter((capability) => capability.operationIds.includes(operationId));
}

/* ------------------------------------------------------------------ *
 * The module-load guard (duplicated as a test in
 * tests/integration-registry.test.ts)
 * ------------------------------------------------------------------ */

/**
 * The coverage registry is the ONLY operation authority: every
 * capability's `operationIds` must exist there. This throws at import
 * time so drift fails before any UI renders or any public asset is
 * generated.
 */
const COVERAGE_OPERATION_IDS = new Set(COVERAGE.map((record) => record.operation));
const seenCapabilityIds = new Set<string>();
for (const capability of INTEGRATION_CAPABILITIES) {
  if (seenCapabilityIds.has(capability.id)) {
    throw new Error(
      `integration capability registry duplicates id "${capability.id}" — one record per capability`,
    );
  }
  seenCapabilityIds.add(capability.id);
  for (const operationId of capability.operationIds) {
    if (!COVERAGE_OPERATION_IDS.has(operationId)) {
      throw new Error(
        `integration capability "${capability.id}" references unknown operation "${operationId}" — the coverage registry is the only operation authority`,
      );
    }
  }
}
