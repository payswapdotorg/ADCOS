/**
 * REAL captured backend shapes for Worker 2's feature tests.
 *
 * Every fixture below is transcribed VERBATIM from the local sandbox
 * runtime (captures taken 2026-09-14 against the deterministic sandbox
 * composition — content-derived ids, so the values are stable). These
 * are the exact envelopes/resources the pages render; no field is
 * invented. Where a shape repeats, the fixture carries the canonical
 * member set observed on the wire.
 *
 * Deterministic, no network: tests mock fetch and return these.
 */

import type {
  Application,
  Contract,
  ContractAssurance,
  ContractLifecycle,
  ContractUsage,
  DemoDocument,
  Lease,
  ListResponse,
  Readiness,
} from "@/lib/api/types";

/* ------------------------------------------------------------------ *
 * The connected application (GET /api/2.0/application)
 * ------------------------------------------------------------------ */

export const FIXTURE_APPLICATION: Application = {
  application_id: "sha256:c20c5f90db52d8a89c5168fdb71f522ed9648d1264330357a9cdad98532f1f01",
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

export const FIXTURE_SESSION = {
  applicationId: FIXTURE_APPLICATION.application_id,
  credential: "dasec_6f0a61f4d683e1b7a06859649217ac1714552b64c93ea25509e0e7dfa0ed5b60",
};

/* ------------------------------------------------------------------ *
 * Platform surfaces
 * ------------------------------------------------------------------ */

/** GET /readyz — the sandbox shape (200, no durable backends). */
export const FIXTURE_READINESS: Readiness = {
  ok: true,
  service: "adcos-runtime",
  mode: "sandbox",
  environment: "sandbox",
  backends: {},
};

/** A degraded readiness variant (200 + ok=false, one backend down). */
export const FIXTURE_READINESS_DEGRADED: Readiness = {
  ok: false,
  service: "adcos-runtime",
  mode: "production",
  environment: "production",
  backends: {
    "neon-postgres": { state: "ready", detail: "wired" },
    "upstash-redis": {
      state: "unavailable",
      detail: "connection refused (degraded — ephemeral coordination only)",
    },
  },
};

/* ------------------------------------------------------------------ *
 * Contracts (POST /api/2.0/intents and reads)
 * ------------------------------------------------------------------ */

/** A contract in INTENT (the freshly recorded intent). */
export const FIXTURE_CONTRACT_INTENT: Contract = {
  "accepted_offers": [],
  "assurance_obligations": [
    {
      "provenance": {
        "decision_refs": [
          "capture:assurance:v1",
        ],
        "issuer": "assurance-authority",
      },
      "ref_kind": "assurance-obligation",
      "value": "capture:assurance:v1",
    },
  ],
  "beneficiaries": [
    {
      "beneficiary_kind": "DEVICE",
      "beneficiary_ref": "capture:device:v1",
    },
  ],
  "command_count": 1,
  "contract_id": "sha256:8c925c7fe3bddc7d398e0b4bebd8151e5c682147a33043579f9ed778ea559c55",
  "environment": "sandbox",
  "execution_artifacts": [],
  "execution_scope": [
    {
      "ref_kind": "execution-scope",
      "value": "capture:execution-scope:v1",
    },
  ],
  "hard_constraints": [
    {
      "kind": "latency-bound",
      "params": {
        "ms": 100,
      },
    },
    {
      "kind": "throughput-floor",
      "params": {
        "bps": 1000,
      },
    },
  ],
  "id": "sha256:8c925c7fe3bddc7d398e0b4bebd8151e5c682147a33043579f9ed778ea559c55",
  "kind": "contract",
  "principal": {
    "principal_kind": "APPLICATION",
    "principal_ref": "sha256:c20c5f90db52d8a89c5168fdb71f522ed9648d1264330357a9cdad98532f1f01",
  },
  "provenance": {
    "decision_refs": [
      "developerapi:sha256:b5ef7adc447b70294f076dc1921439b79ed9e8b10e35b8288f5d75635eaf2d47",
    ],
    "issuer": "developerapi-application:sha256:c20c5f90db52d8a89c5168fdb71f522ed9648d1264330357a9cdad98532f1f01",
  },
  "requirements": [
    {
      "provenance": {
        "decision_refs": [
          "capture:intent:v1",
        ],
        "issuer": "intent-authority",
      },
      "ref_kind": "intent-requirements",
      "value": "capture:requirements:v1",
    },
  ],
  "service_properties": [
    {
      "ref_kind": "service-property",
      "value": "capture:service-property:v1",
    },
  ],
  "signature_refs": [],
  "state": "INTENT",
  "termination": {
    "compensation": {
      "ref_kind": "compensation",
      "value": "capture:compensation:v1",
    },
    "conditions": [
      "principal-requested",
      "validity-expired",
    ],
  },
  "usage_pricing_terms": {
    "ref_kind": "usage-pricing-terms",
    "value": "capture:usage-pricing:v1",
  },
  "validity": {
    "not_after": "2026-10-14T00:00:00Z",
    "not_before": "2026-09-14T00:00:00Z",
  },
};

/** The same contract after offer acceptance (OFFER_SELECTED). */
export const FIXTURE_CONTRACT_OFFER_SELECTED: Contract = {
  "accepted_offers": [
    {
      "provenance": {
        "decision_refs": [
          "capture:offer:v1",
        ],
        "issuer": "provider:ran-reference",
      },
      "ref_kind": "offer",
      "value": "capture:offer:v1",
    },
  ],
  "assurance_obligations": [
    {
      "provenance": {
        "decision_refs": [
          "capture:assurance:v1",
        ],
        "issuer": "assurance-authority",
      },
      "ref_kind": "assurance-obligation",
      "value": "capture:assurance:v1",
    },
  ],
  "beneficiaries": [
    {
      "beneficiary_kind": "DEVICE",
      "beneficiary_ref": "capture:device:v1",
    },
  ],
  "command_count": 2,
  "contract_id": "sha256:8c925c7fe3bddc7d398e0b4bebd8151e5c682147a33043579f9ed778ea559c55",
  "environment": "sandbox",
  "execution_artifacts": [],
  "execution_scope": [
    {
      "ref_kind": "execution-scope",
      "value": "capture:execution-scope:v1",
    },
  ],
  "hard_constraints": [
    {
      "kind": "latency-bound",
      "params": {
        "ms": 100,
      },
    },
    {
      "kind": "throughput-floor",
      "params": {
        "bps": 1000,
      },
    },
  ],
  "id": "sha256:8c925c7fe3bddc7d398e0b4bebd8151e5c682147a33043579f9ed778ea559c55",
  "kind": "contract",
  "principal": {
    "principal_kind": "APPLICATION",
    "principal_ref": "sha256:c20c5f90db52d8a89c5168fdb71f522ed9648d1264330357a9cdad98532f1f01",
  },
  "provenance": {
    "decision_refs": [
      "developerapi:sha256:b5ef7adc447b70294f076dc1921439b79ed9e8b10e35b8288f5d75635eaf2d47",
    ],
    "issuer": "developerapi-application:sha256:c20c5f90db52d8a89c5168fdb71f522ed9648d1264330357a9cdad98532f1f01",
  },
  "requirements": [
    {
      "provenance": {
        "decision_refs": [
          "capture:intent:v1",
        ],
        "issuer": "intent-authority",
      },
      "ref_kind": "intent-requirements",
      "value": "capture:requirements:v1",
    },
  ],
  "service_properties": [
    {
      "ref_kind": "service-property",
      "value": "capture:service-property:v1",
    },
  ],
  "signature_refs": [],
  "state": "OFFER_SELECTED",
  "termination": {
    "compensation": {
      "ref_kind": "compensation",
      "value": "capture:compensation:v1",
    },
    "conditions": [
      "principal-requested",
      "validity-expired",
    ],
  },
  "usage_pricing_terms": {
    "ref_kind": "usage-pricing-terms",
    "value": "capture:usage-pricing:v1",
  },
  "validity": {
    "not_after": "2026-10-14T00:00:00Z",
    "not_before": "2026-09-14T00:00:00Z",
  },
};

/** The same contract after activation (CONTRACT_ACTIVE). */
export const FIXTURE_CONTRACT_ACTIVE: Contract = {
  "accepted_offers": [
    {
      "provenance": {
        "decision_refs": [
          "capture:offer:v1",
        ],
        "issuer": "provider:ran-reference",
      },
      "ref_kind": "offer",
      "value": "capture:offer:v1",
    },
  ],
  "assurance_obligations": [
    {
      "provenance": {
        "decision_refs": [
          "capture:assurance:v1",
        ],
        "issuer": "assurance-authority",
      },
      "ref_kind": "assurance-obligation",
      "value": "capture:assurance:v1",
    },
  ],
  "beneficiaries": [
    {
      "beneficiary_kind": "DEVICE",
      "beneficiary_ref": "capture:device:v1",
    },
  ],
  "command_count": 3,
  "contract_id": "sha256:8c925c7fe3bddc7d398e0b4bebd8151e5c682147a33043579f9ed778ea559c55",
  "environment": "sandbox",
  "execution_artifacts": [],
  "execution_scope": [
    {
      "ref_kind": "execution-scope",
      "value": "capture:execution-scope:v1",
    },
  ],
  "hard_constraints": [
    {
      "kind": "latency-bound",
      "params": {
        "ms": 100,
      },
    },
    {
      "kind": "throughput-floor",
      "params": {
        "bps": 1000,
      },
    },
  ],
  "id": "sha256:8c925c7fe3bddc7d398e0b4bebd8151e5c682147a33043579f9ed778ea559c55",
  "kind": "contract",
  "principal": {
    "principal_kind": "APPLICATION",
    "principal_ref": "sha256:c20c5f90db52d8a89c5168fdb71f522ed9648d1264330357a9cdad98532f1f01",
  },
  "provenance": {
    "decision_refs": [
      "developerapi:sha256:b5ef7adc447b70294f076dc1921439b79ed9e8b10e35b8288f5d75635eaf2d47",
    ],
    "issuer": "developerapi-application:sha256:c20c5f90db52d8a89c5168fdb71f522ed9648d1264330357a9cdad98532f1f01",
  },
  "requirements": [
    {
      "provenance": {
        "decision_refs": [
          "capture:intent:v1",
        ],
        "issuer": "intent-authority",
      },
      "ref_kind": "intent-requirements",
      "value": "capture:requirements:v1",
    },
  ],
  "service_properties": [
    {
      "ref_kind": "service-property",
      "value": "capture:service-property:v1",
    },
  ],
  "signature_refs": [
    {
      "ref_kind": "signature",
      "value": "capture:signature:v1",
    },
  ],
  "state": "CONTRACT_ACTIVE",
  "termination": {
    "compensation": {
      "ref_kind": "compensation",
      "value": "capture:compensation:v1",
    },
    "conditions": [
      "principal-requested",
      "validity-expired",
    ],
  },
  "usage_pricing_terms": {
    "ref_kind": "usage-pricing-terms",
    "value": "capture:usage-pricing:v1",
  },
  "validity": {
    "not_after": "2026-10-14T00:00:00Z",
    "not_before": "2026-09-14T00:00:00Z",
  },
};

/**
 * The contract after termination (TERMINATED — terminal). The REAL
 * capture carries one member beyond the client's `Contract` type:
 * `termination_reason` (the reason recorded with the termination
 * command — the backend owns the vocabulary; the type is extended
 * LOCALLY here rather than editing Worker 1's frozen client surface).
 */
export const FIXTURE_CONTRACT_TERMINATED: Contract & {
  termination_reason: string;
} = {
  "accepted_offers": [
    {
      "provenance": {
        "decision_refs": [
          "capture:offer:v1",
        ],
        "issuer": "provider:ran-reference",
      },
      "ref_kind": "offer",
      "value": "capture:offer:v1",
    },
  ],
  "assurance_obligations": [
    {
      "provenance": {
        "decision_refs": [
          "capture:assurance:v1",
        ],
        "issuer": "assurance-authority",
      },
      "ref_kind": "assurance-obligation",
      "value": "capture:assurance:v1",
    },
  ],
  "beneficiaries": [
    {
      "beneficiary_kind": "DEVICE",
      "beneficiary_ref": "capture:device:v1",
    },
  ],
  "command_count": 7,
  "contract_id": "sha256:8c925c7fe3bddc7d398e0b4bebd8151e5c682147a33043579f9ed778ea559c55",
  "environment": "sandbox",
  "execution_artifacts": [],
  "execution_scope": [
    {
      "ref_kind": "execution-scope",
      "value": "capture:execution-scope:v1",
    },
  ],
  "hard_constraints": [
    {
      "kind": "latency-bound",
      "params": {
        "ms": 100,
      },
    },
    {
      "kind": "throughput-floor",
      "params": {
        "bps": 1000,
      },
    },
  ],
  "id": "sha256:8c925c7fe3bddc7d398e0b4bebd8151e5c682147a33043579f9ed778ea559c55",
  "kind": "contract",
  "principal": {
    "principal_kind": "APPLICATION",
    "principal_ref": "sha256:c20c5f90db52d8a89c5168fdb71f522ed9648d1264330357a9cdad98532f1f01",
  },
  "provenance": {
    "decision_refs": [
      "developerapi:sha256:b5ef7adc447b70294f076dc1921439b79ed9e8b10e35b8288f5d75635eaf2d47",
    ],
    "issuer": "developerapi-application:sha256:c20c5f90db52d8a89c5168fdb71f522ed9648d1264330357a9cdad98532f1f01",
  },
  "requirements": [
    {
      "provenance": {
        "decision_refs": [
          "capture:intent:v1",
        ],
        "issuer": "intent-authority",
      },
      "ref_kind": "intent-requirements",
      "value": "capture:requirements:v1",
    },
  ],
  "service_properties": [
    {
      "ref_kind": "service-property",
      "value": "capture:service-property:v1",
    },
  ],
  "signature_refs": [
    {
      "ref_kind": "signature",
      "value": "capture:signature:v1",
    },
  ],
  "state": "TERMINATED",
  "termination": {
    "compensation": {
      "ref_kind": "compensation",
      "value": "capture:compensation:v1",
    },
    "conditions": [
      "principal-requested",
      "validity-expired",
    ],
  },
  "termination_reason": "capture-termination",
  "usage_pricing_terms": {
    "ref_kind": "usage-pricing-terms",
    "value": "capture:usage-pricing:v1",
  },
  "validity": {
    "not_after": "2026-10-14T00:00:00Z",
    "not_before": "2026-09-14T00:00:00Z",
  },
};

/** The demonstration contract as the developer API sees it (CONTRACT_ACTIVE,
 * one bound execution-artifact reference — the plan). */
export const FIXTURE_DEMO_CONTRACT: Contract = {
  "accepted_offers": [
    {
      "provenance": {
        "decision_refs": [
          "demo:offer:v1",
        ],
        "issuer": "provider:ran-reference",
      },
      "ref_kind": "offer",
      "value": "demo:offer:ran-reference:v1",
    },
  ],
  "assurance_obligations": [
    {
      "provenance": {
        "decision_refs": [
          "demo:assurance:v1",
        ],
        "issuer": "assurance-authority",
      },
      "ref_kind": "assurance-obligation",
      "value": "demo:assurance-obligation:v1",
    },
  ],
  "beneficiaries": [
    {
      "beneficiary_kind": "DEVICE",
      "beneficiary_ref": "demo:device:v1",
    },
  ],
  "command_count": 4,
  "contract_id": "sha256:78f563858281c8caad6c639df7a8109231f3546dbcff789fce43bfee22cfa7ba",
  "environment": "sandbox",
  "execution_artifacts": [
    {
      "provenance": {
        "decision_refs": [
          "demo:contract-fulfillment:v1",
        ],
        "issuer": "adcos:runtime:demo-planner",
      },
      "ref_kind": "execution-artifact",
      "value": "sha256:da58d8b9c09953f1d840fe30c86a92f31825e3363bb691476fc3aebaeb9ba5ec",
    },
  ],
  "execution_scope": [
    {
      "ref_kind": "execution-scope",
      "value": "demo:execution-scope:v1",
    },
  ],
  "hard_constraints": [
    {
      "kind": "latency-bound",
      "params": {
        "ms": 100,
      },
    },
    {
      "kind": "throughput-floor",
      "params": {
        "bps": 1000,
      },
    },
  ],
  "id": "sha256:78f563858281c8caad6c639df7a8109231f3546dbcff789fce43bfee22cfa7ba",
  "kind": "contract",
  "principal": {
    "principal_kind": "APPLICATION",
    "principal_ref": "sha256:c20c5f90db52d8a89c5168fdb71f522ed9648d1264330357a9cdad98532f1f01",
  },
  "provenance": {
    "decision_refs": [
      "developerapi:sha256:cdcd478bf78c4283ebc66a9e81ca6558de4222cee43b3ba89fd5aca192d60596",
    ],
    "issuer": "developerapi-application:sha256:c20c5f90db52d8a89c5168fdb71f522ed9648d1264330357a9cdad98532f1f01",
  },
  "requirements": [
    {
      "provenance": {
        "decision_refs": [
          "demo:intent:v1",
        ],
        "issuer": "intent-authority",
      },
      "ref_kind": "intent-requirements",
      "value": "demo:intent-requirements:v1",
    },
  ],
  "service_properties": [
    {
      "ref_kind": "service-property",
      "value": "demo:service-property:v1",
    },
  ],
  "signature_refs": [
    {
      "ref_kind": "signature",
      "value": "demo:signature:v1",
    },
  ],
  "state": "CONTRACT_ACTIVE",
  "termination": {
    "compensation": {
      "ref_kind": "compensation",
      "value": "demo:compensation:v1",
    },
    "conditions": [
      "principal-requested",
      "validity-expired",
    ],
  },
  "usage_pricing_terms": {
    "ref_kind": "usage-pricing-terms",
    "value": "demo:usage-pricing:v1",
  },
  "validity": {
    "not_after": "2026-10-14T00:00:00Z",
    "not_before": "2026-09-14T00:00:00Z",
  },
};

/* ------------------------------------------------------------------ *
 * Lifecycle projection (GET /api/2.0/intents/{id}/lifecycle)
 * ------------------------------------------------------------------ */

/** The lifecycle observation in INTENT. */
export const FIXTURE_LIFECYCLE_INTENT: ContractLifecycle = {
  "assurance_obligation_refs": [
    {
      "provenance": {
        "decision_refs": [
          "capture:assurance:v1",
        ],
        "issuer": "assurance-authority",
      },
      "ref_kind": "assurance-obligation",
      "value": "capture:assurance:v1",
    },
  ],
  "command_count": 1,
  "contract_state": "INTENT",
  "entered_at": "2026-09-14T00:00:00Z",
  "environment": "sandbox",
  "evidence_class": "sandbox-simulation",
  "execution_artifact_refs": [],
  "execution_scope_refs": [
    {
      "ref_kind": "execution-scope",
      "value": "capture:execution-scope:v1",
    },
  ],
  "execution_status": "not-started",
  "id": "sha256:8c925c7fe3bddc7d398e0b4bebd8151e5c682147a33043579f9ed778ea559c55",
  "kind": "contract_lifecycle",
  "note": "API success never implies physical connectivity success: this observation reports the canonical contract state machine only (the frozen 1.1 reference lifecycle); execution material appears as opaque typed references and physical connectivity evidence is never fabricated or promoted by the developer API.",
  "physical_connectivity_observed": false,
  "physical_evidence": "not-claimed",
  "statements": [
    "api_request_accepted",
    "contract_intent_recorded",
    "contract_offers_selected",
    "contract_active",
    "execution_status_reported_from_contract_state",
    "assurance_reported_from_contract_recorded_outcomes",
    "physical_connectivity_not_claimed",
  ],
  "validity": {
    "not_after": "2026-10-14T00:00:00Z",
    "not_before": "2026-09-14T00:00:00Z",
  },
};

/** The lifecycle observation in CONTRACT_ACTIVE. */
export const FIXTURE_LIFECYCLE_ACTIVE: ContractLifecycle = {
  "assurance_obligation_refs": [
    {
      "provenance": {
        "decision_refs": [
          "capture:assurance:v1",
        ],
        "issuer": "assurance-authority",
      },
      "ref_kind": "assurance-obligation",
      "value": "capture:assurance:v1",
    },
  ],
  "command_count": 3,
  "contract_state": "CONTRACT_ACTIVE",
  "entered_at": "2026-09-14T00:20:00Z",
  "environment": "sandbox",
  "evidence_class": "sandbox-simulation",
  "execution_artifact_refs": [],
  "execution_scope_refs": [
    {
      "ref_kind": "execution-scope",
      "value": "capture:execution-scope:v1",
    },
  ],
  "execution_status": "permitted",
  "id": "sha256:8c925c7fe3bddc7d398e0b4bebd8151e5c682147a33043579f9ed778ea559c55",
  "kind": "contract_lifecycle",
  "note": "API success never implies physical connectivity success: this observation reports the canonical contract state machine only (the frozen 1.1 reference lifecycle); execution material appears as opaque typed references and physical connectivity evidence is never fabricated or promoted by the developer API.",
  "physical_connectivity_observed": false,
  "physical_evidence": "not-claimed",
  "statements": [
    "api_request_accepted",
    "contract_intent_recorded",
    "contract_offers_selected",
    "contract_active",
    "execution_status_reported_from_contract_state",
    "assurance_reported_from_contract_recorded_outcomes",
    "physical_connectivity_not_claimed",
  ],
  "validity": {
    "not_after": "2026-10-14T00:00:00Z",
    "not_before": "2026-09-14T00:00:00Z",
  },
};

/** The demonstration contract's lifecycle (execution artifact bound). */
export const FIXTURE_DEMO_LIFECYCLE: ContractLifecycle = {
  "assurance_obligation_refs": [
    {
      "provenance": {
        "decision_refs": [
          "demo:assurance:v1",
        ],
        "issuer": "assurance-authority",
      },
      "ref_kind": "assurance-obligation",
      "value": "demo:assurance-obligation:v1",
    },
  ],
  "command_count": 4,
  "contract_state": "CONTRACT_ACTIVE",
  "entered_at": "2026-09-14T00:25:00Z",
  "environment": "sandbox",
  "evidence_class": "sandbox-simulation",
  "execution_artifact_refs": [
    {
      "provenance": {
        "decision_refs": [
          "demo:contract-fulfillment:v1",
        ],
        "issuer": "adcos:runtime:demo-planner",
      },
      "ref_kind": "execution-artifact",
      "value": "sha256:da58d8b9c09953f1d840fe30c86a92f31825e3363bb691476fc3aebaeb9ba5ec",
    },
  ],
  "execution_scope_refs": [
    {
      "ref_kind": "execution-scope",
      "value": "demo:execution-scope:v1",
    },
  ],
  "execution_status": "permitted",
  "id": "sha256:78f563858281c8caad6c639df7a8109231f3546dbcff789fce43bfee22cfa7ba",
  "kind": "contract_lifecycle",
  "note": "API success never implies physical connectivity success: this observation reports the canonical contract state machine only (the frozen 1.1 reference lifecycle); execution material appears as opaque typed references and physical connectivity evidence is never fabricated or promoted by the developer API.",
  "physical_connectivity_observed": false,
  "physical_evidence": "not-claimed",
  "statements": [
    "api_request_accepted",
    "contract_intent_recorded",
    "contract_offers_selected",
    "contract_active",
    "execution_status_reported_from_contract_state",
    "assurance_reported_from_contract_recorded_outcomes",
    "physical_connectivity_not_claimed",
  ],
  "validity": {
    "not_after": "2026-10-14T00:00:00Z",
    "not_before": "2026-09-14T00:00:00Z",
  },
};

/* ------------------------------------------------------------------ *
 * Usage + assurance reads (notes are rendered VERBATIM)
 * ------------------------------------------------------------------ */

export const FIXTURE_USAGE: ContractUsage = {
  "contract_state": "CONTRACT_ACTIVE",
  "environment": "sandbox",
  "evidence_class": "sandbox-simulation",
  "id": "sha256:8c925c7fe3bddc7d398e0b4bebd8151e5c682147a33043579f9ed778ea559c55",
  "kind": "contract_usage_terms",
  "note": "usage semantics are referenced, never interpreted: the usage/pricing authority (the commercial reconciliation track) owns the referenced material; this API exposes the contract's opaque typed reference only",
  "usage_pricing_terms": {
    "ref_kind": "usage-pricing-terms",
    "value": "capture:usage-pricing:v1",
  },
};

export const FIXTURE_ASSURANCE: ContractAssurance = {
  "assurance_obligations": [
    {
      "provenance": {
        "decision_refs": [
          "capture:assurance:v1",
        ],
        "issuer": "assurance-authority",
      },
      "ref_kind": "assurance-obligation",
      "value": "capture:assurance:v1",
    },
  ],
  "contract_state": "CONTRACT_ACTIVE",
  "environment": "sandbox",
  "evidence_class": "sandbox-simulation",
  "id": "sha256:8c925c7fe3bddc7d398e0b4bebd8151e5c682147a33043579f9ed778ea559c55",
  "kind": "contract_assurance",
  "note": "assurance semantics are referenced, never evaluated: the assurance authority owns the obligations; the contract state machine records the evaluation outcomes (ASSURED/DEGRADED/FAILED per the frozen 1.1 \u00a79 vocabulary)",
};

/* ------------------------------------------------------------------ *
 * Leases
 * ------------------------------------------------------------------ */

export const FIXTURE_LEASE_ACTIVE: Lease = {
  "contract_id": "sha256:8c925c7fe3bddc7d398e0b4bebd8151e5c682147a33043579f9ed778ea559c55",
  "environment": "sandbox",
  "granted_at": "2026-09-14T01:00:00Z",
  "id": "sha256:7f94f8b5c5e20fd6d00b8dbee8373d46b06f27f9518dc1e58a5cd068d8084ba8",
  "kind": "contract_lease",
  "lease_id": "sha256:7f94f8b5c5e20fd6d00b8dbee8373d46b06f27f9518dc1e58a5cd068d8084ba8",
  "not_after": "2026-09-14T02:00:00Z",
  "not_before": "2026-09-14T01:00:00Z",
  "state": "active",
};

export const FIXTURE_LEASE_REVOKED: Lease = {
  "contract_id": "sha256:8c925c7fe3bddc7d398e0b4bebd8151e5c682147a33043579f9ed778ea559c55",
  "environment": "sandbox",
  "granted_at": "2026-09-14T02:00:00Z",
  "id": "sha256:c2335a6328a00dcfc5c57f6a9bb1ac81a4a48dadee7feea494d946380a1b6fad",
  "kind": "contract_lease",
  "lease_id": "sha256:c2335a6328a00dcfc5c57f6a9bb1ac81a4a48dadee7feea494d946380a1b6fad",
  "not_after": "2026-09-14T03:00:00Z",
  "not_before": "2026-09-14T02:00:00Z",
  "revocation_reason": "capture-revocation",
  "state": "revoked",
};

/* ------------------------------------------------------------------ *
 * List shapes (GET + JSON body discipline)
 * ------------------------------------------------------------------ */

export const FIXTURE_CONTRACTS_LIST: ListResponse<Contract> = {
  "has_more": false,
  "items": [
    {
      "accepted_offers": [
        {
          "provenance": {
            "decision_refs": [
              "demo:offer:v1",
            ],
            "issuer": "provider:ran-reference",
          },
          "ref_kind": "offer",
          "value": "demo:offer:ran-reference:v1",
        },
      ],
      "assurance_obligations": [
        {
          "provenance": {
            "decision_refs": [
              "demo:assurance:v1",
            ],
            "issuer": "assurance-authority",
          },
          "ref_kind": "assurance-obligation",
          "value": "demo:assurance-obligation:v1",
        },
      ],
      "beneficiaries": [
        {
          "beneficiary_kind": "DEVICE",
          "beneficiary_ref": "demo:device:v1",
        },
      ],
      "command_count": 4,
      "contract_id": "sha256:78f563858281c8caad6c639df7a8109231f3546dbcff789fce43bfee22cfa7ba",
      "environment": "sandbox",
      "execution_artifacts": [
        {
          "provenance": {
            "decision_refs": [
              "demo:contract-fulfillment:v1",
            ],
            "issuer": "adcos:runtime:demo-planner",
          },
          "ref_kind": "execution-artifact",
          "value": "sha256:da58d8b9c09953f1d840fe30c86a92f31825e3363bb691476fc3aebaeb9ba5ec",
        },
      ],
      "execution_scope": [
        {
          "ref_kind": "execution-scope",
          "value": "demo:execution-scope:v1",
        },
      ],
      "hard_constraints": [
        {
          "kind": "latency-bound",
          "params": {
            "ms": 100,
          },
        },
        {
          "kind": "throughput-floor",
          "params": {
            "bps": 1000,
          },
        },
      ],
      "id": "sha256:78f563858281c8caad6c639df7a8109231f3546dbcff789fce43bfee22cfa7ba",
      "kind": "contract",
      "principal": {
        "principal_kind": "APPLICATION",
        "principal_ref": "sha256:c20c5f90db52d8a89c5168fdb71f522ed9648d1264330357a9cdad98532f1f01",
      },
      "provenance": {
        "decision_refs": [
          "developerapi:sha256:cdcd478bf78c4283ebc66a9e81ca6558de4222cee43b3ba89fd5aca192d60596",
        ],
        "issuer": "developerapi-application:sha256:c20c5f90db52d8a89c5168fdb71f522ed9648d1264330357a9cdad98532f1f01",
      },
      "requirements": [
        {
          "provenance": {
            "decision_refs": [
              "demo:intent:v1",
            ],
            "issuer": "intent-authority",
          },
          "ref_kind": "intent-requirements",
          "value": "demo:intent-requirements:v1",
        },
      ],
      "service_properties": [
        {
          "ref_kind": "service-property",
          "value": "demo:service-property:v1",
        },
      ],
      "signature_refs": [
        {
          "ref_kind": "signature",
          "value": "demo:signature:v1",
        },
      ],
      "state": "CONTRACT_ACTIVE",
      "termination": {
        "compensation": {
          "ref_kind": "compensation",
          "value": "demo:compensation:v1",
        },
        "conditions": [
          "principal-requested",
          "validity-expired",
        ],
      },
      "usage_pricing_terms": {
        "ref_kind": "usage-pricing-terms",
        "value": "demo:usage-pricing:v1",
      },
      "validity": {
        "not_after": "2026-10-14T00:00:00Z",
        "not_before": "2026-09-14T00:00:00Z",
      },
    },
    {
      "accepted_offers": [
        {
          "provenance": {
            "decision_refs": [
              "capture:offer:v1",
            ],
            "issuer": "provider:ran-reference",
          },
          "ref_kind": "offer",
          "value": "capture:offer:v1",
        },
      ],
      "assurance_obligations": [
        {
          "provenance": {
            "decision_refs": [
              "capture:assurance:v1",
            ],
            "issuer": "assurance-authority",
          },
          "ref_kind": "assurance-obligation",
          "value": "capture:assurance:v1",
        },
      ],
      "beneficiaries": [
        {
          "beneficiary_kind": "DEVICE",
          "beneficiary_ref": "capture:device:v1",
        },
      ],
      "command_count": 5,
      "contract_id": "sha256:8c925c7fe3bddc7d398e0b4bebd8151e5c682147a33043579f9ed778ea559c55",
      "environment": "sandbox",
      "execution_artifacts": [],
      "execution_scope": [
        {
          "ref_kind": "execution-scope",
          "value": "capture:execution-scope:v1",
        },
      ],
      "hard_constraints": [
        {
          "kind": "latency-bound",
          "params": {
            "ms": 100,
          },
        },
        {
          "kind": "throughput-floor",
          "params": {
            "bps": 1000,
          },
        },
      ],
      "id": "sha256:8c925c7fe3bddc7d398e0b4bebd8151e5c682147a33043579f9ed778ea559c55",
      "kind": "contract",
      "principal": {
        "principal_kind": "APPLICATION",
        "principal_ref": "sha256:c20c5f90db52d8a89c5168fdb71f522ed9648d1264330357a9cdad98532f1f01",
      },
      "provenance": {
        "decision_refs": [
          "developerapi:sha256:b5ef7adc447b70294f076dc1921439b79ed9e8b10e35b8288f5d75635eaf2d47",
        ],
        "issuer": "developerapi-application:sha256:c20c5f90db52d8a89c5168fdb71f522ed9648d1264330357a9cdad98532f1f01",
      },
      "requirements": [
        {
          "provenance": {
            "decision_refs": [
              "capture:intent:v1",
            ],
            "issuer": "intent-authority",
          },
          "ref_kind": "intent-requirements",
          "value": "capture:requirements:v1",
        },
      ],
      "service_properties": [
        {
          "ref_kind": "service-property",
          "value": "capture:service-property:v1",
        },
      ],
      "signature_refs": [
        {
          "ref_kind": "signature",
          "value": "capture:signature:v1",
        },
      ],
      "state": "CONTRACT_ACTIVE",
      "termination": {
        "compensation": {
          "ref_kind": "compensation",
          "value": "capture:compensation:v1",
        },
        "conditions": [
          "principal-requested",
          "validity-expired",
        ],
      },
      "usage_pricing_terms": {
        "ref_kind": "usage-pricing-terms",
        "value": "capture:usage-pricing:v1",
      },
      "validity": {
        "not_after": "2026-10-14T00:00:00Z",
        "not_before": "2026-09-14T00:00:00Z",
      },
    },
  ],
  "next_cursor": "",
};

/* ------------------------------------------------------------------ *
 * The deterministic fulfillment demonstration
 * (GET|POST /demo/contract-fulfillment — the full-chain document)
 * ------------------------------------------------------------------ */

export const FIXTURE_DEMO_DOCUMENT: DemoDocument = {
  "boundary": [
    {
      "method": "POST",
      "request_id": "sha256:9efd1daa89f6d37d809c6a9727af1326cb6b8d970fbb24f0ee748aaab4f9cb59",
      "route": "/api/2.0/intents",
      "status": 200,
    },
  ],
  "contract": {
    "accepted_offers": [
      {
        "provenance": {
          "decision_refs": [
            "demo:offer:v1",
          ],
          "issuer": "provider:ran-reference",
        },
        "ref_kind": "offer",
        "value": "demo:offer:ran-reference:v1",
      },
    ],
    "assurance_obligations": [
      {
        "provenance": {
          "decision_refs": [
            "demo:assurance:v1",
          ],
          "issuer": "assurance-authority",
        },
        "ref_kind": "assurance-obligation",
        "value": "demo:assurance-obligation:v1",
      },
    ],
    "beneficiaries": [
      {
        "beneficiary_kind": "DEVICE",
        "beneficiary_ref": "demo:device:v1",
      },
    ],
    "contract_id": "sha256:78f563858281c8caad6c639df7a8109231f3546dbcff789fce43bfee22cfa7ba",
    "execution_artifacts": [
      {
        "provenance": {
          "decision_refs": [
            "demo:contract-fulfillment:v1",
          ],
          "issuer": "adcos:runtime:demo-planner",
        },
        "ref_kind": "execution-artifact",
        "value": "sha256:da58d8b9c09953f1d840fe30c86a92f31825e3363bb691476fc3aebaeb9ba5ec",
      },
    ],
    "execution_scope": [
      {
        "ref_kind": "execution-scope",
        "value": "demo:execution-scope:v1",
      },
    ],
    "hard_constraints": [
      {
        "kind": "latency-bound",
        "params": {
          "ms": 100,
        },
      },
      {
        "kind": "throughput-floor",
        "params": {
          "bps": 1000,
        },
      },
    ],
    "principal": {
      "principal_kind": "APPLICATION",
      "principal_ref": "sha256:c20c5f90db52d8a89c5168fdb71f522ed9648d1264330357a9cdad98532f1f01",
    },
    "provenance": {
      "decision_refs": [
        "developerapi:sha256:cdcd478bf78c4283ebc66a9e81ca6558de4222cee43b3ba89fd5aca192d60596",
      ],
      "issuer": "developerapi-application:sha256:c20c5f90db52d8a89c5168fdb71f522ed9648d1264330357a9cdad98532f1f01",
    },
    "requirements": [
      {
        "provenance": {
          "decision_refs": [
            "demo:intent:v1",
          ],
          "issuer": "intent-authority",
        },
        "ref_kind": "intent-requirements",
        "value": "demo:intent-requirements:v1",
      },
    ],
    "service_properties": [
      {
        "ref_kind": "service-property",
        "value": "demo:service-property:v1",
      },
    ],
    "signature_refs": [
      {
        "ref_kind": "signature",
        "value": "demo:signature:v1",
      },
    ],
    "state": "CONTRACT_ACTIVE",
    "termination": {
      "compensation": {
        "ref_kind": "compensation",
        "value": "demo:compensation:v1",
      },
      "conditions": [
        "principal-requested",
        "validity-expired",
      ],
    },
    "usage_pricing_terms": {
      "ref_kind": "usage-pricing-terms",
      "value": "demo:usage-pricing:v1",
    },
    "validity": {
      "not_after": "2026-10-14T00:00:00Z",
      "not_before": "2026-09-14T00:00:00Z",
    },
  },
  "environment": "sandbox",
  "evidence": [
    {
      "confidence_basis_points": 10000,
      "contract_ref": "sha256:78f563858281c8caad6c639df7a8109231f3546dbcff789fce43bfee22cfa7ba",
      "freshness_until": "2026-09-14T02:00:00Z",
      "instant": "2026-09-14T01:00:00Z",
      "metric": "link-up",
      "producer": "provider:ran-reference",
      "record_id": "evidence:observation:7e6e275466ed7559cfce3768b83cb9ee0230ec3d52b21d87375609ed7db5b1f7",
      "record_type": "observation",
      "source_refs": [
        "sha256:35cfdec9219b152ba7bd8ed9dbfc7153ea14dd12a870c1945350328c0e5dab89",
      ],
      "subject_ref": "sha256:a958a4bacec50cc3670788e45309f820c87d7c06b28d6d288cb93c7b7c9512f2",
      "value": 1,
    },
    {
      "attestation_kind": "controller-verified",
      "attested_value": 1,
      "contract_ref": "sha256:78f563858281c8caad6c639df7a8109231f3546dbcff789fce43bfee22cfa7ba",
      "instant": "2026-09-14T02:00:00Z",
      "producer": "adcos:runtime:demo-attestor",
      "record_id": "evidence:attestation:8bf42deca4011e0cb230ca0a7980eae09dc007063faaca5e59c918fb497572e0",
      "record_type": "attestation",
      "source_refs": [
        "sha256:da58d8b9c09953f1d840fe30c86a92f31825e3363bb691476fc3aebaeb9ba5ec",
        "sha256:a958a4bacec50cc3670788e45309f820c87d7c06b28d6d288cb93c7b7c9512f2",
      ],
      "subject_ref": "sha256:da58d8b9c09953f1d840fe30c86a92f31825e3363bb691476fc3aebaeb9ba5ec",
      "valid_until": "2026-09-15T02:00:00Z",
    },
  ],
  "evidence_class": "SOFTWARE",
  "execution": {
    "access_technology_id": "access.3gpp.nr.imt2020",
    "activation_id": "sha256:a958a4bacec50cc3670788e45309f820c87d7c06b28d6d288cb93c7b7c9512f2",
    "adapter_id": "adcos:adapter:access.3gpp.nr.imt2020:bfa54a8cddce72a6",
    "binding_id": "sha256:d329a36778181f2aa1af2d20c231f00147893be137c93c7d54dfb989c04dd990",
    "measurement_id": "sha256:35cfdec9219b152ba7bd8ed9dbfc7153ea14dd12a870c1945350328c0e5dab89",
    "provider": "deterministic-reference-adapter",
    "release_id": "sha256:d983ab4093d92b7d1bcf000bb2f58e080eab9930acfba12cf151d90ba7352d0d",
    "released_kinds": [
      "activation",
      "reservation",
    ],
    "reservation_id": "sha256:4fafbaa9815877e760f24fde5d9e012e557436dd38996060f4c82faa359f7b18",
    "samples": [
      {
        "metric": "link-up",
        "observed_at": "2026-09-14T01:00:00Z",
        "value": 1,
      },
      {
        "metric": "rx-bytes-total",
        "observed_at": "2026-09-14T01:00:00Z",
        "value": 3000,
      },
      {
        "metric": "tx-bytes-total",
        "observed_at": "2026-09-14T01:00:00Z",
        "value": 3000,
      },
      {
        "metric": "rx-error-count",
        "observed_at": "2026-09-14T01:00:00Z",
        "value": 0,
      },
      {
        "metric": "tx-error-count",
        "observed_at": "2026-09-14T01:00:00Z",
        "value": 0,
      },
      {
        "metric": "retransmit-count",
        "observed_at": "2026-09-14T01:00:00Z",
        "value": 0,
      },
    ],
    "sandbox": true,
    "segment_states": [
      "PLANNED",
      "RESERVED",
      "ACTIVATED",
      "MEASURED",
      "RELEASED",
    ],
    "session_id": "sha256:d385a360eea2dc466eb492020b69e9884b73c70aadcee0efb017c5f8a980a432",
    "standard_mechanisms": [
      "3gpp-nr",
      "oran-fronthaul-split",
    ],
  },
  "instant": "2026-09-14T00:00:00Z",
  "mode": "sandbox",
  "plan": {
    "constraint_fingerprint": "sha256:5d1178e5b556a1545a8140f9ccdd89ca5299d308608386a36ba1d0c355abdf62",
    "contract_id": "sha256:78f563858281c8caad6c639df7a8109231f3546dbcff789fce43bfee22cfa7ba",
    "hard_constraints": [
      {
        "kind": "latency-bound",
        "params": {
          "ms": 100,
        },
      },
      {
        "kind": "throughput-floor",
        "params": {
          "bps": 1000,
        },
      },
    ],
    "plan_id": "sha256:da58d8b9c09953f1d840fe30c86a92f31825e3363bb691476fc3aebaeb9ba5ec",
    "provenance": {
      "decision_refs": [
        "demo:contract-fulfillment:v1",
      ],
      "issuer": "adcos:runtime:demo-planner",
    },
    "segments": [
      {
        "contract_id": "sha256:78f563858281c8caad6c639df7a8109231f3546dbcff789fce43bfee22cfa7ba",
        "offer_reference": {
          "provenance": {
            "decision_refs": [
              "demo:offer:v1",
            ],
            "issuer": "provider:ran-reference",
          },
          "ref_kind": "offer",
          "value": "demo:offer:ran-reference:v1",
        },
        "operations": [
          "reserve",
          "activate",
          "measure",
          "release",
        ],
        "provenance": {
          "decision_refs": [
            "demo:segment:v1",
          ],
          "issuer": "adcos:runtime:demo-optimizer",
        },
        "role": "primary",
        "segment_id": "sha256:2fef7e706639dc9c180fe15cd8d2880e9c341bc01385c952d912f6af905821f0",
        "state": "RELEASED",
      },
    ],
    "tie_break": [
      "role",
      "offer",
      "segment-id",
    ],
    "validity": {
      "not_after": "2026-10-14T00:00:00Z",
      "not_before": "2026-09-14T00:00:00Z",
    },
  },
};

/* ------------------------------------------------------------------ *
 * Error envelopes (VERBATIM backend reasons for failure surfaces)
 * ------------------------------------------------------------------ */

/** 422 — lease window outside contract validity (canonical: invalid-state). */
export const FIXTURE_ERROR_LEASE_WINDOW = {
  api_version: "2.0",
  environment: "sandbox",
  request_id: "sha256:8274b481fd1a5c0bda3c87f711ba1c03427748c0b6dfbc74e5faa2228e5532d4",
  error: {
    canonical_reason: "invalid-state",
    environment: "sandbox",
    http_status: 422,
    message: "lease window must lie inside the contract validity window",
    reason: "invalid-input",
    request_id: "sha256:8274b481fd1a5c0bda3c87f711ba1c03427748c0b6dfbc74e5faa2228e5532d4",
    resource_id: "",
    retry_after: "",
    retryable: false,
  },
} as const;

/** 422 — revoking a renewed lease (canonical: invalid-transition). */
export const FIXTURE_ERROR_LEASE_RENEWED = {
  api_version: "2.0",
  environment: "sandbox",
  request_id: "sha256:f7dcf3f2eb668f0cf3bb3247bbd1d2471a9b535429fc5449cdd8457c62cc3520",
  error: {
    canonical_reason: "invalid-transition",
    environment: "sandbox",
    http_status: 422,
    message: "only granted/active leases revoke (found renewed)",
    reason: "invalid-input",
    request_id: "sha256:f7dcf3f2eb668f0cf3bb3247bbd1d2471a9b535429fc5449cdd8457c62cc3520",
    resource_id: "",
    retry_after: "",
    retryable: false,
  },
} as const;

/** 422 — terminating a terminal contract (canonical: contract-terminal). */
export const FIXTURE_ERROR_TERMINAL = {
  api_version: "2.0",
  environment: "sandbox",
  request_id: "sha256:1c0d9e6e5f00c4a279a45646a58f3dfe69a5be12f0c0f9f28c9fb9b0a37f5021",
  error: {
    canonical_reason: "contract-terminal",
    environment: "sandbox",
    http_status: 422,
    message: "contract is terminal in TERMINATED; commands are rejected",
    reason: "invalid-input",
    request_id: "sha256:1c0d9e6e5f00c4a279a45646a58f3dfe69a5be12f0c0f9f28c9fb9b0a37f5021",
    resource_id: "",
    retry_after: "",
    retryable: false,
  },
} as const;

/** 404 — resource-unknown. */
export const FIXTURE_ERROR_NOT_FOUND = {
  api_version: "2.0",
  environment: "sandbox",
  request_id: "sha256:deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
  error: {
    canonical_reason: "",
    environment: "sandbox",
    http_status: 404,
    message: "contract sha256:deadbeef is unknown",
    reason: "resource-unknown",
    request_id: "sha256:deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
    resource_id: "",
    retry_after: "",
    retryable: false,
  },
} as const;

