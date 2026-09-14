/**
 * Coverage registry tests — the registry is the console's coverage
 * authority: EXACTLY the 21 developer-API operations + the 4 platform
 * routes, no duplicates, no invented endpoints.
 */

import { describe, expect, it } from "vitest";
import {
  COVERAGE,
  COVERAGE_COUNT,
  DEVELOPER_OPERATION_COUNT,
  PLATFORM_OPERATION_COUNT,
  coverageByOperation,
  coverageMutations,
  coverageReads,
  developerOperations,
  isCoverageOperation,
  platformOperations,
} from "@/lib/api/coverage";

/** The frozen 21-operation boundary table (verified against the gateway ROUTES). */
const DEVELOPER_API_OPERATIONS: [string, string, string][] = [
  ["application_self", "GET", "/api/2.0/application"],
  ["intent_create", "POST", "/api/2.0/intents"],
  ["intents_list", "GET", "/api/2.0/intents"],
  ["intent_get", "GET", "/api/2.0/intents/{intent_id}"],
  ["intent_lifecycle", "GET", "/api/2.0/intents/{intent_id}/lifecycle"],
  ["offers_accept", "POST", "/api/2.0/intents/{intent_id}/offers"],
  ["contract_activate", "POST", "/api/2.0/intents/{intent_id}/activation"],
  ["contracts_list", "GET", "/api/2.0/contracts"],
  ["contract_get", "GET", "/api/2.0/contracts/{contract_id}"],
  ["contract_usage", "GET", "/api/2.0/contracts/{contract_id}/usage"],
  ["contract_assurance", "GET", "/api/2.0/contracts/{contract_id}/assurance"],
  ["contract_terminate", "POST", "/api/2.0/contracts/{contract_id}/termination"],
  ["lease_grant", "POST", "/api/2.0/contracts/{contract_id}/leases"],
  ["leases_list", "GET", "/api/2.0/leases"],
  ["lease_get", "GET", "/api/2.0/leases/{lease_id}"],
  ["lease_renew", "POST", "/api/2.0/leases/{lease_id}/renewal"],
  ["lease_revoke", "POST", "/api/2.0/leases/{lease_id}/revocation"],
  ["endpoints_list", "GET", "/api/2.0/webhook-endpoints"],
  ["endpoint_register", "POST", "/api/2.0/webhook-endpoints"],
  ["endpoint_get", "GET", "/api/2.0/webhook-endpoints/{endpoint_id}"],
  ["deliveries_list", "GET", "/api/2.0/webhook-endpoints/{endpoint_id}/deliveries"],
];

/** The 4 platform routes. */
const PLATFORM_OPERATIONS_SET: [string, string, string][] = [
  ["healthz", "GET", "/healthz"],
  ["readyz", "GET", "/readyz"],
  ["demo_contract_fulfillment", "GET", "/demo/contract-fulfillment"],
  ["platform_contract_read", "GET", "/api/contracts/{contract_id}"],
];

describe("the backend capability coverage registry", () => {
  it("contains EXACTLY the 21 developer operations + 4 platform routes", () => {
    expect(COVERAGE).toHaveLength(COVERAGE_COUNT);
    expect(COVERAGE_COUNT).toBe(25);
    expect(developerOperations()).toHaveLength(DEVELOPER_OPERATION_COUNT);
    expect(developerOperations()).toHaveLength(21);
    expect(platformOperations()).toHaveLength(PLATFORM_OPERATION_COUNT);
    expect(platformOperations()).toHaveLength(4);
  });

  it("has no duplicate operations, methods+paths, or paths", () => {
    const operations = COVERAGE.map((entry) => entry.operation);
    expect(new Set(operations).size).toBe(operations.length);

    const routeKeys = COVERAGE.map((entry) => `${entry.method} ${entry.path}`);
    expect(new Set(routeKeys).size).toBe(routeKeys.length);
  });

  it("matches the frozen developer-API boundary table exactly", () => {
    const registered = new Map(
      developerOperations().map((entry) => [entry.operation, entry]),
    );
    for (const [operation, method, path] of DEVELOPER_API_OPERATIONS) {
      const entry = registered.get(operation);
      expect(entry, `operation ${operation} must be registered`).toBeDefined();
      expect(entry?.method).toBe(method);
      expect(entry?.path).toBe(path);
      expect(entry?.platform).toBe(false);
    }
    expect(registered.size).toBe(DEVELOPER_API_OPERATIONS.length);
  });

  it("matches the platform surfaces exactly", () => {
    const registered = new Map(
      platformOperations().map((entry) => [entry.operation, entry]),
    );
    for (const [operation, method, path] of PLATFORM_OPERATIONS_SET) {
      const entry = registered.get(operation);
      expect(entry, `platform route ${operation} must be registered`).toBeDefined();
      expect(entry?.method).toBe(method);
      expect(entry?.path).toBe(path);
      expect(entry?.platform).toBe(true);
      expect(entry?.requiredCapability).toBe("");
    }
    expect(registered.size).toBe(PLATFORM_OPERATIONS_SET.length);
  });

  it("marks exactly the 8 mutations and gives each an example body", () => {
    const mutations = coverageMutations();
    expect(mutations.map((entry) => entry.operation).sort()).toEqual(
      [
        "intent_create",
        "offers_accept",
        "contract_activate",
        "contract_terminate",
        "lease_grant",
        "lease_renew",
        "lease_revoke",
        "endpoint_register",
      ].sort(),
    );
    for (const entry of mutations) {
      expect(entry.example, `${entry.operation} needs an example body`).toBeDefined();
      expect(Object.keys(entry.example ?? {})).not.toHaveLength(0);
    }
    // every mutation requires a capability grant
    for (const entry of mutations) {
      expect(entry.requiredCapability).not.toBe("");
    }
  });

  it("reads never carry an example requirement and are non-mutating", () => {
    for (const entry of coverageReads()) {
      expect(entry.mutation).toBe(false);
    }
    expect(coverageReads()).toHaveLength(25 - 8);
  });

  it("every entry carries a uiLocation and a description", () => {
    for (const entry of COVERAGE) {
      expect(entry.uiLocation.startsWith("/")).toBe(true);
      expect(entry.description.length).toBeGreaterThan(10);
    }
  });

  it("lookup helpers resolve and reject correctly", () => {
    expect(coverageByOperation("intent_create")?.method).toBe("POST");
    expect(coverageByOperation("nope")).toBeUndefined();
    expect(isCoverageOperation("application_self")).toBe(true);
    expect(isCoverageOperation("offer_publish")).toBe(false); // W046-era, demoted
    expect(isCoverageOperation("reservations")).toBe(false);
  });
});
