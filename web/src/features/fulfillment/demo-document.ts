/**
 * Typed presentation views over the raw demonstration document.
 *
 * `DemoDocument` types the contract/plan/execution members as the raw
 * records the backend sends (the backend owns the vocabulary). These
 * parsers are PRESENTATION reads only — safe member extraction with
 * honest fallbacks (empty string / empty list / null) when a member is
 * absent or ill-typed. They never invent or transform domain semantics,
 * and the raw record is always rendered alongside (ObjectSection `json`),
 * so nothing these views skip is hidden from the developer.
 */

import type {
  DemoDocument,
  HardConstraint,
  OpaqueReference,
  Provenance,
} from "@/lib/api/types";

/* ------------------------------------------------------------------ *
 * View types (what the chain sections render)
 * ------------------------------------------------------------------ */

export interface DemoValidity {
  not_before: string;
  not_after: string;
}

/** The demonstration's contract member (carries contract_id, NOT id). */
export interface DemoContractView {
  contract_id: string;
  state: string;
  validity: DemoValidity | null;
  principal: { principal_kind: string; principal_ref: string } | null;
  hard_constraints: HardConstraint[];
  accepted_offers: OpaqueReference[];
  assurance_obligations: OpaqueReference[];
}

/** One plan segment (the segment-state kernel). */
export interface DemoSegment {
  segment_id: string;
  contract_id: string;
  role: string;
  state: string;
  operations: string[];
  offer_reference: OpaqueReference | null;
  provenance: Provenance | null;
}

export interface DemoPlanView {
  plan_id: string;
  contract_id: string;
  constraint_fingerprint: string;
  tie_break: string[];
  validity: DemoValidity | null;
  hard_constraints: HardConstraint[];
  segments: DemoSegment[];
  provenance: Provenance | null;
}

/** One execution sample: {metric, observed_at, value}. */
export interface DemoSample {
  metric: string;
  observed_at: string;
  value: number | string | null;
}

export interface DemoExecutionView {
  sandbox: boolean | null;
  provider: string;
  adapter_id: string;
  access_technology_id: string;
  standard_mechanisms: string[];
  session_id: string;
  reservation_id: string;
  activation_id: string;
  binding_id: string;
  measurement_id: string;
  release_id: string;
  released_kinds: string[];
  segment_states: string[];
  samples: DemoSample[];
}

/** One evidence record (observation or attestation — backend vocabulary). */
export interface DemoEvidenceRecord {
  record_type: string;
  record_id: string;
  subject_ref: string;
  contract_ref: string;
  instant: string;
  producer: string;
  metric: string | null;
  value: number | string | null;
  confidence_basis_points: number | null;
  freshness_until: string | null;
  attestation_kind: string | null;
  attested_value: number | string | null;
  valid_until: string | null;
  source_refs: string[];
}

export interface DemoDocumentView {
  contract: DemoContractView;
  plan: DemoPlanView;
  execution: DemoExecutionView;
  evidence: DemoEvidenceRecord[];
}

/* ------------------------------------------------------------------ *
 * Honest member readers (no invented defaults)
 * ------------------------------------------------------------------ */

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function str(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function strOrNull(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function strList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function num(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}

function scalar(value: unknown): number | string | null {
  return typeof value === "number" || typeof value === "string" ? value : null;
}

function asValidity(value: unknown): DemoValidity | null {
  const record = asRecord(value);
  const notBefore = str(record.not_before);
  const notAfter = str(record.not_after);
  if (notBefore.length === 0 && notAfter.length === 0) return null;
  return { not_before: notBefore, not_after: notAfter };
}

function asProvenance(value: unknown): Provenance | null {
  const record = asRecord(value);
  const issuer = str(record.issuer);
  if (issuer.length === 0) return null;
  return { issuer, decision_refs: strList(record.decision_refs) };
}

function asOpaqueRef(value: unknown): OpaqueReference | null {
  const record = asRecord(value);
  const refKind = str(record.ref_kind);
  const refValue = str(record.value);
  if (refKind.length === 0 && refValue.length === 0) return null;
  const provenance = asProvenance(record.provenance);
  return provenance
    ? { ref_kind: refKind, value: refValue, provenance }
    : { ref_kind: refKind, value: refValue };
}

function asRefList(value: unknown): OpaqueReference[] {
  return Array.isArray(value)
    ? value.map(asOpaqueRef).filter((ref): ref is OpaqueReference => ref !== null)
    : [];
}

function asHardConstraints(value: unknown): HardConstraint[] {
  return Array.isArray(value)
    ? value
        .map((item) => {
          const record = asRecord(item);
          const params: Record<string, number | string> = {};
          for (const [key, param] of Object.entries(asRecord(record.params))) {
            if (typeof param === "number" || typeof param === "string") {
              params[key] = param;
            }
          }
          return { kind: str(record.kind), params };
        })
        .filter((constraint) => constraint.kind.length > 0)
    : [];
}

/* ------------------------------------------------------------------ *
 * The parser
 * ------------------------------------------------------------------ */

export function parseDemoDocument(doc: DemoDocument): DemoDocumentView {
  const contract = asRecord(doc.contract);
  const plan = asRecord(doc.plan);
  const execution = asRecord(doc.execution);

  const principalRecord = asRecord(contract.principal);

  const samples: DemoSample[] = Array.isArray(execution.samples)
    ? execution.samples
        .map((item) => {
          const record = asRecord(item);
          return {
            metric: str(record.metric),
            observed_at: str(record.observed_at),
            value: scalar(record.value),
          };
        })
        .filter((sample) => sample.metric.length > 0)
    : [];

  const evidence: DemoEvidenceRecord[] = Array.isArray(doc.evidence)
    ? doc.evidence
        .map((item) => {
          const record = asRecord(item);
          return {
            record_type: str(record.record_type),
            record_id: str(record.record_id),
            subject_ref: str(record.subject_ref),
            contract_ref: str(record.contract_ref),
            instant: str(record.instant),
            producer: str(record.producer),
            metric: strOrNull(record.metric),
            value: scalar(record.value),
            confidence_basis_points: num(record.confidence_basis_points),
            freshness_until: strOrNull(record.freshness_until),
            attestation_kind: strOrNull(record.attestation_kind),
            attested_value: scalar(record.attested_value),
            valid_until: strOrNull(record.valid_until),
            source_refs: strList(record.source_refs),
          } satisfies DemoEvidenceRecord;
        })
        .filter(
          (record) => record.record_id.length > 0 || record.record_type.length > 0,
        )
    : [];

  const segments: DemoSegment[] = Array.isArray(plan.segments)
    ? plan.segments
        .map((item) => {
          const record = asRecord(item);
          return {
            segment_id: str(record.segment_id),
            contract_id: str(record.contract_id),
            role: str(record.role),
            state: str(record.state),
            operations: strList(record.operations),
            offer_reference: asOpaqueRef(record.offer_reference),
            provenance: asProvenance(record.provenance),
          } satisfies DemoSegment;
        })
        .filter((segment) => segment.segment_id.length > 0)
    : [];

  return {
    contract: {
      contract_id: str(contract.contract_id),
      state: str(contract.state),
      validity: asValidity(contract.validity),
      principal: {
        principal_kind: str(principalRecord.principal_kind),
        principal_ref: str(principalRecord.principal_ref),
      },
      hard_constraints: asHardConstraints(contract.hard_constraints),
      accepted_offers: asRefList(contract.accepted_offers),
      assurance_obligations: asRefList(contract.assurance_obligations),
    },
    plan: {
      plan_id: str(plan.plan_id),
      contract_id: str(plan.contract_id),
      constraint_fingerprint: str(plan.constraint_fingerprint),
      tie_break: strList(plan.tie_break),
      validity: asValidity(plan.validity),
      hard_constraints: asHardConstraints(plan.hard_constraints),
      segments,
      provenance: asProvenance(plan.provenance),
    },
    execution: {
      sandbox: typeof execution.sandbox === "boolean" ? execution.sandbox : null,
      provider: str(execution.provider),
      adapter_id: str(execution.adapter_id),
      access_technology_id: str(execution.access_technology_id),
      standard_mechanisms: strList(execution.standard_mechanisms),
      session_id: str(execution.session_id),
      reservation_id: str(execution.reservation_id),
      activation_id: str(execution.activation_id),
      binding_id: str(execution.binding_id),
      measurement_id: str(execution.measurement_id),
      release_id: str(execution.release_id),
      released_kinds: strList(execution.released_kinds),
      segment_states: strList(execution.segment_states),
      samples,
    },
    evidence,
  };
}
