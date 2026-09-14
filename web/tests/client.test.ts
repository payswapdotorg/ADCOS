/**
 * Client contract tests — every domain function of AdcosClient against a
 * mocked fetch: exact URL, method, headers (auth + version + idempotency)
 * and JSON body, per the verified backend contract. NO network.
 *
 * Envelope/error fixtures are the REAL captured shapes
 * (/home/z/adcos-captures — never invented).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AdcosClient } from "@/lib/api/client";
import { AdcosApiError } from "@/lib/api/errors";
import type { Application, Contract, Readiness } from "@/lib/api/types";

const SESSION = {
  applicationId: "sha256:c20c5f90db52d8a89c5168fdb71f522ed9648d1264330357a9cdad98532f1f01",
  credential: "dasec_6f0a61f4d683e1b7a06859649217ac1714552b64c93ea25509e0e7dfa0ed5b60",
};

const CONTRACT_ID = "sha256:d5522ff10aeffa286bb3c30bd887587a40659480d2338c8b7847d3f398e6c0b7";
const LEASE_ID = "sha256:3998ee4f7c87b99362c2ed6b4d05e2757a4087089cde4b78f50f81bfa851d420";
const ENDPOINT_ID = "sha256:339aad04332444655e42307bb0ffaf2c3bb47ccb4e4aa41e3fef6b877522cac8";

function envelope<T>(data: T) {
  return {
    api_version: "2.0",
    environment: "sandbox",
    request_id: "sha256:fixed_request_id",
    data,
    idempotency: { key: "idem", replayed: false },
    rate_limit: { limit: 1000, remaining: 999, reset_at: "2026-09-13T00:00:01Z" },
  };
}

const APPLICATION_DATA: Application = {
  application_id: SESSION.applicationId,
  application_name: "adcos:runtime:contract-fulfillment-demo",
  capabilities: [
    "assurance:read",
    "intents:read",
    "intents:write",
    "leases:read",
    "leases:write",
    "usage:read",
    "webhooks:read",
    "webhooks:write",
  ],
  developer_id: "adcos:runtime:demo-developer",
  environment: "sandbox",
  evidence_class: "sandbox-simulation",
  issued_at: "2026-09-13T00:00:00Z",
  kind: "application",
  status: "active",
  valid_until: "2036-09-13T00:00:00Z",
};

const CONTRACT_DATA: Contract = {
  accepted_offers: [],
  assurance_obligations: [],
  beneficiaries: [],
  command_count: 1,
  contract_id: CONTRACT_ID,
  environment: "sandbox",
  execution_artifacts: [],
  execution_scope: [],
  hard_constraints: [],
  id: CONTRACT_ID,
  kind: "contract",
  principal: { principal_kind: "APPLICATION", principal_ref: SESSION.applicationId },
  provenance: { issuer: "developerapi-application:" + SESSION.applicationId, decision_refs: [] },
  requirements: [{ ref_kind: "intent-requirements", value: "demo:intent-requirements:v1" }],
  service_properties: [],
  signature_refs: [],
  state: "INTENT",
  termination: {
    conditions: ["principal-requested"],
    compensation: { ref_kind: "compensation", value: "demo:compensation:v1" },
  },
  usage_pricing_terms: { ref_kind: "usage-pricing-terms", value: "demo:usage-pricing:v1" },
  validity: { not_before: "2026-09-13T00:00:00Z", not_after: "2026-10-13T00:00:00Z" },
};

const READYZ_DATA: Readiness = {
  ok: true,
  service: "adcos-runtime",
  mode: "sandbox",
  environment: "sandbox",
  backends: {},
};

const fetchMock = vi.fn();

function okResponse(body: unknown, status = 200) {
  return {
    status,
    ok: status >= 200 && status < 300,
    headers: {
      get: (name: string) =>
        name.toLowerCase() === "x-adcos-request-id" ? "sha256:fixed_request_id" : null,
    },
    text: async () => JSON.stringify(body),
  };
}

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockResolvedValue(okResponse(envelope({})));
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

/** The single fetch call the client made. */
function lastCall(): [string, RequestInit] {
  expect(fetchMock).toHaveBeenCalledTimes(1);
  return fetchMock.mock.calls[0] as [string, RequestInit];
}

/** The most recent fetch call (multi-call tests). */
function latestCall(): [string, RequestInit] {
  expect(fetchMock.mock.calls.length).toBeGreaterThan(0);
  return fetchMock.mock.calls[fetchMock.mock.calls.length - 1] as [
    string,
    RequestInit,
  ];
}

function headersOf(call: [string, RequestInit]): Record<string, string> {
  return (call[1].headers ?? {}) as Record<string, string>;
}

describe("AdcosClient transport", () => {
  it("sends the auth + version headers on every /api/2.0 request", async () => {
    const client = new AdcosClient(SESSION);
    fetchMock.mockResolvedValue(okResponse(envelope(APPLICATION_DATA)));
    await client.applicationSelf();
    const call = lastCall();
    expect(call[0]).toBe("/api/2.0/application");
    expect(call[1].method).toBe("GET");
    const headers = headersOf(call);
    expect(headers["X-ADCOS-Application"]).toBe(SESSION.applicationId);
    expect(headers["X-ADCOS-Credential"]).toBe(SESSION.credential);
    expect(headers["X-ADCOS-API-Version"]).toBe("2.0");
    expect(call[1].body).toBeUndefined();
  });

  it("sends no auth headers on platform surfaces", async () => {
    const client = new AdcosClient(SESSION);
    fetchMock.mockResolvedValue(okResponse({ ok: true, service: "adcos-runtime" }));
    await client.healthz();
    const call = lastCall();
    expect(call[0]).toBe("/healthz");
    const headers = headersOf(call);
    expect(headers["X-ADCOS-Application"]).toBeUndefined();
    expect(headers["X-ADCOS-Credential"]).toBeUndefined();
  });

  it("auto-generates a UUID idempotency key for mutations", async () => {
    const client = new AdcosClient(SESSION);
    fetchMock.mockResolvedValue(okResponse(envelope(CONTRACT_DATA)));
    await client.createIntent({
      recorded_at: "2026-09-13T00:00:00Z",
      requirements: [{ ref_kind: "intent-requirements", value: "demo:intent-requirements:v1" }],
      validity: { not_before: "2026-09-13T00:00:00Z", not_after: "2026-10-13T00:00:00Z" },
      termination: {
        conditions: ["principal-requested"],
        compensation: { ref_kind: "compensation", value: "demo:compensation:v1" },
      },
    });
    const headers = headersOf(lastCall());
    expect(headers["X-ADCOS-Idempotency-Key"]).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
    );
    expect(headers["Content-Type"]).toBe("application/json");
  });

  it("uses a caller-supplied idempotency key verbatim", async () => {
    const client = new AdcosClient(SESSION);
    fetchMock.mockResolvedValue(okResponse(envelope(CONTRACT_DATA)));
    await client.terminateContract(
      CONTRACT_ID,
      { recorded_at: "2026-09-13T03:00:00Z", condition: "principal-requested", reason: "test" },
      { idempotencyKey: "console-fixed-key" },
    );
    const headers = headersOf(lastCall());
    expect(headers["X-ADCOS-Idempotency-Key"]).toBe("console-fixed-key");
  });

  it("sends list pagination as the GET request's JSON body", async () => {
    const client = new AdcosClient(SESSION);
    fetchMock.mockResolvedValue(
      okResponse(envelope({ items: [CONTRACT_DATA], next_cursor: "", has_more: false })),
    );
    await client.listContracts({ limit: 50, cursor: "cursor-1", filters: { state: "INTENT" } });
    const call = lastCall();
    expect(call[0]).toBe("/api/2.0/contracts");
    expect(call[1].method).toBe("GET");
    expect(headersOf(call)["Content-Type"]).toBe("application/json");
    expect(JSON.parse(call[1].body as string)).toEqual({
      limit: 50,
      cursor: "cursor-1",
      filters: { state: "INTENT" },
    });
  });

  it("omits the body entirely for bare GETs", async () => {
    const client = new AdcosClient(SESSION);
    fetchMock.mockResolvedValue(okResponse(envelope(CONTRACT_DATA)));
    await client.getContract(CONTRACT_ID);
    const call = lastCall();
    expect(call[1].body).toBeUndefined();
    expect(headersOf(call)["Content-Type"]).toBeUndefined();
  });

  it("returns the full envelope with rate_limit and idempotency surfaces", async () => {
    const client = new AdcosClient(SESSION);
    fetchMock.mockResolvedValue(okResponse(envelope(APPLICATION_DATA)));
    const result = await client.applicationSelf();
    expect(result.api_version).toBe("2.0");
    expect(result.environment).toBe("sandbox");
    expect(result.request_id).toBe("sha256:fixed_request_id");
    expect(result.rate_limit).toEqual({ limit: 1000, remaining: 999, reset_at: "2026-09-13T00:00:01Z" });
    expect(result.data.application_name).toBe(APPLICATION_DATA.application_name);
  });
});

describe("AdcosClient error paths", () => {
  it("carries the backend reason VERBATIM from the error envelope", async () => {
    const client = new AdcosClient(SESSION);
    fetchMock.mockResolvedValue(
      okResponse(
        {
          api_version: "2.0",
          environment: "sandbox",
          request_id: "sha256:auth",
          error: {
            canonical_reason: "",
            environment: "sandbox",
            http_status: 401,
            message: "application '' is not issued in environment 'sandbox'",
            reason: "authentication-invalid",
            request_id: "sha256:auth",
            resource_id: "",
            retry_after: "",
            retryable: false,
          },
        },
        401,
      ),
    );
    await expect(client.listContracts()).rejects.toSatisfy((error: unknown) => {
      const apiError = error as AdcosApiError;
      expect(apiError).toBeInstanceOf(AdcosApiError);
      expect(apiError.reason).toBe("authentication-invalid"); // VERBATIM
      expect(apiError.status).toBe(401);
      expect(apiError.requestId).toBe("sha256:auth");
      expect(apiError.retryable).toBe(false);
      expect(apiError.message).toContain("not issued in environment");
      expect(apiError.request).toEqual({ method: "GET", path: "/api/2.0/contracts" });
      return true;
    });
  });

  it("preserves canonical_reason and the resource_id from adapted domain errors", async () => {
    const client = new AdcosClient(SESSION);
    fetchMock.mockResolvedValue(
      okResponse(
        {
          api_version: "2.0",
          environment: "sandbox",
          request_id: "sha256:unknown",
          error: {
            canonical_reason: "unknown-contract",
            environment: "sandbox",
            http_status: 404,
            message: "contract sha256:deadbeef is unknown",
            reason: "resource-unknown",
            request_id: "sha256:unknown",
            resource_id: "sha256:deadbeef",
            retry_after: "",
            retryable: false,
          },
        },
        404,
      ),
    );
    await expect(client.getContract("sha256:deadbeef")).rejects.toSatisfy(
      (error: unknown) => {
        const apiError = error as AdcosApiError;
        expect(apiError.reason).toBe("resource-unknown"); // boundary reason verbatim
        expect(apiError.canonicalReason).toBe("unknown-contract"); // canonical reason verbatim
        expect(apiError.resourceId).toBe("sha256:deadbeef");
        expect(apiError.request.path).toBe("/api/2.0/contracts/sha256:deadbeef");
        return true;
      },
    );
  });

  it("parses the runtime-level envelope (reason_code) too", async () => {
    const client = new AdcosClient(null);
    fetchMock.mockResolvedValue(
      okResponse(
        {
          error: {
            reason_code: "unknown-contract",
            message: "contract sha256:nope is unknown",
            backend: null,
          },
        },
        404,
      ),
    );
    await expect(client.platformContractRead("sha256:nope")).rejects.toSatisfy(
      (error: unknown) => {
        const apiError = error as AdcosApiError;
        expect(apiError.reason).toBe("unknown-contract"); // runtime reason_code verbatim
        expect(apiError.status).toBe(404);
        return true;
      },
    );
  });

  it("collapses a network failure into the synthesized backend-unreachable error", async () => {
    const client = new AdcosClient(SESSION);
    fetchMock.mockRejectedValue(new TypeError("fetch failed"));
    await expect(client.applicationSelf()).rejects.toSatisfy((error: unknown) => {
      const apiError = error as AdcosApiError;
      expect(apiError).toBeInstanceOf(AdcosApiError);
      expect(apiError.reason).toBe("backend-unreachable");
      expect(apiError.status).toBe(0);
      return true;
    });
  });

  it("rejects malformed ids client-side before any request", async () => {
    const client = new AdcosClient(SESSION);
    // the guard throws synchronously before any transport work
    expect(() => client.getContract("../etc")).toThrow(AdcosApiError);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("AdcosClient domain surface — every operation's route contract", () => {
  const client = new AdcosClient(SESSION);

  async function verifyRoute(
    promise: Promise<unknown>,
    expected: { method: string; path: string; body?: unknown; idempotency?: boolean },
  ): Promise<void> {
    fetchMock.mockResolvedValueOnce(okResponse(envelope({})));
    await promise;
    const call = lastCall();
    expect(call[0]).toBe(expected.path);
    expect(call[1].method).toBe(expected.method);
    if (expected.body !== undefined) {
      expect(JSON.parse(call[1].body as string)).toEqual(expected.body);
    } else {
      expect(call[1].body).toBeUndefined();
    }
    const headers = headersOf(call);
    if (expected.idempotency) {
      expect(headers["X-ADCOS-Idempotency-Key"]).toMatch(/.+/);
    } else {
      expect(headers["X-ADCOS-Idempotency-Key"]).toBeUndefined();
    }
  }

  it("GET /api/2.0/application", () =>
    verifyRoute(client.applicationSelf(), { method: "GET", path: "/api/2.0/application" }));

  it("POST /api/2.0/intents", () =>
    verifyRoute(
      client.createIntent({
        recorded_at: "2026-09-13T00:00:00Z",
        requirements: [{ ref_kind: "intent-requirements", value: "r:v1" }],
        validity: { not_before: "2026-09-13T00:00:00Z", not_after: "2026-10-13T00:00:00Z" },
        termination: {
          conditions: ["principal-requested"],
          compensation: { ref_kind: "compensation", value: "demo:compensation:v1" },
        },
      }),
      {
        method: "POST",
        path: "/api/2.0/intents",
        idempotency: true,
        body: {
          recorded_at: "2026-09-13T00:00:00Z",
          requirements: [{ ref_kind: "intent-requirements", value: "r:v1" }],
          validity: { not_before: "2026-09-13T00:00:00Z", not_after: "2026-10-13T00:00:00Z" },
          termination: {
            conditions: ["principal-requested"],
            compensation: { ref_kind: "compensation", value: "demo:compensation:v1" },
          },
        },
      },
    ));

  it("GET /api/2.0/intents", () =>
    verifyRoute(client.listIntents(), { method: "GET", path: "/api/2.0/intents" }));

  it("GET /api/2.0/intents/{id}", () =>
    verifyRoute(client.getIntent(CONTRACT_ID), {
      method: "GET",
      path: `/api/2.0/intents/${CONTRACT_ID}`,
    }));

  it("GET /api/2.0/intents/{id}/lifecycle", () =>
    verifyRoute(client.getIntentLifecycle(CONTRACT_ID), {
      method: "GET",
      path: `/api/2.0/intents/${CONTRACT_ID}/lifecycle`,
    }));

  it("POST /api/2.0/intents/{id}/offers", () =>
    verifyRoute(
      client.acceptOffers(
        CONTRACT_ID,
        { recorded_at: "2026-09-13T00:10:00Z", offers: [{ ref_kind: "offer", value: "o:v1" }] },
      ),
      {
        method: "POST",
        path: `/api/2.0/intents/${CONTRACT_ID}/offers`,
        idempotency: true,
        body: {
          recorded_at: "2026-09-13T00:10:00Z",
          offers: [{ ref_kind: "offer", value: "o:v1" }],
        },
      },
    ));

  it("POST /api/2.0/intents/{id}/activation", () =>
    verifyRoute(
      client.activateContract(CONTRACT_ID, {
        activated_at: "2026-09-13T00:20:00Z",
        signature_refs: [{ ref_kind: "signature", value: "s:v1" }],
      }),
      {
        method: "POST",
        path: `/api/2.0/intents/${CONTRACT_ID}/activation`,
        idempotency: true,
        body: {
          activated_at: "2026-09-13T00:20:00Z",
          signature_refs: [{ ref_kind: "signature", value: "s:v1" }],
        },
      },
    ));

  it("GET /api/2.0/contracts", () =>
    verifyRoute(client.listContracts(), { method: "GET", path: "/api/2.0/contracts" }));

  it("GET /api/2.0/contracts/{id}", () =>
    verifyRoute(client.getContract(CONTRACT_ID), {
      method: "GET",
      path: `/api/2.0/contracts/${CONTRACT_ID}`,
    }));

  it("GET /api/2.0/contracts/{id}/usage", () =>
    verifyRoute(client.getContractUsage(CONTRACT_ID), {
      method: "GET",
      path: `/api/2.0/contracts/${CONTRACT_ID}/usage`,
    }));

  it("GET /api/2.0/contracts/{id}/assurance", () =>
    verifyRoute(client.getContractAssurance(CONTRACT_ID), {
      method: "GET",
      path: `/api/2.0/contracts/${CONTRACT_ID}/assurance`,
    }));

  it("POST /api/2.0/contracts/{id}/termination", () =>
    verifyRoute(
      client.terminateContract(CONTRACT_ID, {
        recorded_at: "2026-09-13T03:00:00Z",
        condition: "principal-requested",
        reason: "done",
      }),
      {
        method: "POST",
        path: `/api/2.0/contracts/${CONTRACT_ID}/termination`,
        idempotency: true,
        body: {
          recorded_at: "2026-09-13T03:00:00Z",
          condition: "principal-requested",
          reason: "done",
        },
      },
    ));

  it("POST /api/2.0/contracts/{id}/leases", () =>
    verifyRoute(
      client.grantLease(CONTRACT_ID, {
        granted_at: "2026-09-13T01:00:00Z",
        not_before: "2026-09-13T01:00:00Z",
        not_after: "2026-09-13T02:00:00Z",
      }),
      {
        method: "POST",
        path: `/api/2.0/contracts/${CONTRACT_ID}/leases`,
        idempotency: true,
        body: {
          granted_at: "2026-09-13T01:00:00Z",
          not_before: "2026-09-13T01:00:00Z",
          not_after: "2026-09-13T02:00:00Z",
        },
      },
    ));

  it("GET /api/2.0/leases", () =>
    verifyRoute(client.listLeases(), { method: "GET", path: "/api/2.0/leases" }));

  it("GET /api/2.0/leases/{id}", () =>
    verifyRoute(client.getLease(LEASE_ID), {
      method: "GET",
      path: `/api/2.0/leases/${LEASE_ID}`,
    }));

  it("POST /api/2.0/leases/{id}/renewal", () =>
    verifyRoute(
      client.renewLease(LEASE_ID, {
        granted_at: "2026-09-13T02:00:00Z",
        not_before: "2026-09-13T02:00:00Z",
        not_after: "2026-09-13T03:00:00Z",
      }),
      {
        method: "POST",
        path: `/api/2.0/leases/${LEASE_ID}/renewal`,
        idempotency: true,
        body: {
          granted_at: "2026-09-13T02:00:00Z",
          not_before: "2026-09-13T02:00:00Z",
          not_after: "2026-09-13T03:00:00Z",
        },
      },
    ));

  it("POST /api/2.0/leases/{id}/revocation", () =>
    verifyRoute(
      client.revokeLease(LEASE_ID, {
        recorded_at: "2026-09-13T02:10:00Z",
        reason: "rotation",
      }),
      {
        method: "POST",
        path: `/api/2.0/leases/${LEASE_ID}/revocation`,
        idempotency: true,
        body: { recorded_at: "2026-09-13T02:10:00Z", reason: "rotation" },
      },
    ));

  it("GET /api/2.0/webhook-endpoints", () =>
    verifyRoute(client.listWebhookEndpoints(), {
      method: "GET",
      path: "/api/2.0/webhook-endpoints",
    }));

  it("POST /api/2.0/webhook-endpoints", () =>
    verifyRoute(
      client.registerWebhookEndpoint({
        url: "https://example.com/hooks/adcos",
        event_types: ["connectivity_intent.created"],
      }),
      {
        method: "POST",
        path: "/api/2.0/webhook-endpoints",
        idempotency: true,
        body: {
          url: "https://example.com/hooks/adcos",
          event_types: ["connectivity_intent.created"],
        },
      },
    ));

  it("GET /api/2.0/webhook-endpoints/{id}", () =>
    verifyRoute(client.getWebhookEndpoint(ENDPOINT_ID), {
      method: "GET",
      path: `/api/2.0/webhook-endpoints/${ENDPOINT_ID}`,
    }));

  it("GET /api/2.0/webhook-endpoints/{id}/deliveries", () =>
    verifyRoute(client.listDeliveries(ENDPOINT_ID), {
      method: "GET",
      path: `/api/2.0/webhook-endpoints/${ENDPOINT_ID}/deliveries`,
    }));

  it("GET /healthz", async () => {
    fetchMock.mockResolvedValueOnce(okResponse({ ok: true, service: "adcos-runtime" }));
    await client.healthz();
    const call = lastCall();
    expect(call[0]).toBe("/healthz");
    expect(call[1].method).toBe("GET");
  });

  it("GET /readyz", async () => {
    fetchMock.mockResolvedValueOnce(okResponse(READYZ_DATA));
    await client.readyz();
    const call = lastCall();
    expect(call[0]).toBe("/readyz");
    expect(call[1].method).toBe("GET");
  });

  it("GET /demo/contract-fulfillment (default) and POST with an instant", async () => {
    fetchMock.mockResolvedValueOnce(okResponse({ mode: "sandbox" }));
    await client.demoContractFulfillment();
    expect(latestCall()[0]).toBe("/demo/contract-fulfillment");
    expect(latestCall()[1].method).toBe("GET");

    fetchMock.mockResolvedValueOnce(okResponse({ mode: "sandbox" }));
    await client.demoContractFulfillment("2026-09-13T01:30:00Z");
    const call = latestCall();
    expect(call[0]).toBe("/demo/contract-fulfillment");
    expect(call[1].method).toBe("POST");
    expect(JSON.parse(call[1].body as string)).toEqual({ instant: "2026-09-13T01:30:00Z" });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("GET /api/contracts/{id} (unversioned platform read)", async () => {
    fetchMock.mockResolvedValueOnce(okResponse(CONTRACT_DATA));
    await client.platformContractRead(CONTRACT_ID);
    const call = lastCall();
    expect(call[0]).toBe(`/api/contracts/${CONTRACT_ID}`);
    expect(call[1].method).toBe("GET");
    expect(headersOf(call)["X-ADCOS-Application"]).toBeUndefined();
  });
});
