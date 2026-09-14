/**
 * The evidence-record projection — a typed view over the demo document's
 * `evidence[]` members (`Record<string, unknown>` on the wire).
 *
 * PURE PROJECTION: every field renders exactly as the backend sent it or
 * is null (absent members are simply not rendered — never fabricated).
 * Observations carry metric / value / confidence_basis_points /
 * freshness_until; attestations carry attestation_kind / attested_value /
 * valid_until. The full record always stays one JSON view away.
 */

import type { DemoDocument } from "@/lib/api/types";

/** One captured evidence record, projected for rendering. */
export interface EvidenceRecordView {
  record_type: string | null;
  record_id: string | null;
  subject_ref: string | null;
  contract_ref: string | null;
  instant: string | null;
  producer: string | null;
  /** observation-only */
  metric: string | null;
  /** observation-only */
  value: string | null;
  /** observation-only (basis points) */
  confidence_basis_points: string | null;
  /** observation-only */
  freshness_until: string | null;
  /** attestation-only */
  attestation_kind: string | null;
  /** attestation-only */
  attested_value: string | null;
  /** attestation-only */
  valid_until: string | null;
  source_refs: string[];
}

const str = (value: unknown): string | null =>
  typeof value === "string" && value.length > 0 ? value : null;

/** Project one evidence record (nothing invented; absent → null). */
export function evidenceRecordView(
  record: Record<string, unknown>,
): EvidenceRecordView {
  const sources = Array.isArray(record.source_refs)
    ? record.source_refs.filter(
        (ref): ref is string => typeof ref === "string" && ref.length > 0,
      )
    : [];
  return {
    record_type: str(record.record_type),
    record_id: str(record.record_id),
    subject_ref: str(record.subject_ref),
    contract_ref: str(record.contract_ref),
    instant: str(record.instant),
    producer: str(record.producer),
    metric: str(record.metric),
    value:
      record.value === undefined || record.value === null
        ? null
        : String(record.value),
    confidence_basis_points:
      record.confidence_basis_points === undefined ||
      record.confidence_basis_points === null
        ? null
        : String(record.confidence_basis_points),
    freshness_until: str(record.freshness_until),
    attestation_kind: str(record.attestation_kind),
    attested_value:
      record.attested_value === undefined || record.attested_value === null
        ? null
        : String(record.attested_value),
    valid_until: str(record.valid_until),
    source_refs: sources,
  };
}

/** The records of one demo run's document, projected. */
export function evidenceRecordsOf(document: DemoDocument): {
  record: Record<string, unknown>;
  view: EvidenceRecordView;
}[] {
  return (document.evidence ?? []).map((record) => ({
    record,
    view: evidenceRecordView(record),
  }));
}
