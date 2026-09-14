"use client";

/**
 * EvidenceRecordDrawer — the full record: every member VERBATIM, the
 * provenance (producer + source_refs + the run's boundary entry), the
 * related objects (the linked contract — best-effort live read when a
 * session is connected), and the JSON view of the record exactly as the
 * backend returned it.
 *
 * The contract read is REAL (through the typed client) or honestly
 * absent: disconnected shows the link with an explanatory note; a failed
 * read renders the reason VERBATIM through the linked error state.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import type { Contract, DemoBoundaryEntry, DemoDocument } from "@/lib/api/types";
import {
  Drawer,
  EvidenceBadge,
  JsonViewer,
  ObjectHeader,
  Status,
} from "@/components/ui";
import { useSession } from "@/lib/session";
import { LinkedErrorState } from "@/features/errors/link";
import type { EvidenceRecordView } from "./evidence-record";

/** Stable test id for the drawer surface. */
export const EVIDENCE_RECORD_DRAWER_TEST_ID = "evidence-record-drawer";

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[10rem_1fr] items-baseline gap-x-3">
      <dt className="font-mono text-2xs text-ink-faint">{label}</dt>
      <dd className="min-w-0 break-all font-mono text-xs text-ink">
        {value}
      </dd>
    </div>
  );
}

function RelatedContract({ contractRef }: { contractRef: string | null }) {
  const { status, client } = useSession();
  const connected = status === "connected";
  const [contract, setContract] = useState<Contract | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!connected || contractRef === null) return;
    let mounted = true;
    setLoading(true);
    setError(null);
    setContract(null);
    client
      .getContract(contractRef)
      .then((envelope) => {
        if (mounted) setContract(envelope.data);
      })
      .catch((caught: unknown) => {
        if (mounted) setError(caught);
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [connected, client, contractRef]);

  if (contractRef === null) {
    return (
      <p className="text-sm text-ink-faint">
        This record carries no contract_ref.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-2" data-testid="evidence-related-contract">
      <Link
        href={`/connectivity/contracts/${contractRef}`}
        className="break-all font-mono text-xs text-accent hover:underline"
      >
        {contractRef}
      </Link>
      {!connected ? (
        <p className="text-xs text-ink-faint">
          Connect an application to inspect the linked contract live; the
          link opens its detail page either way.
        </p>
      ) : loading ? (
        <div
          aria-busy="true"
          className="h-4 w-48 animate-pulse rounded bg-raised"
        />
      ) : error ? (
        <LinkedErrorState error={error} compact />
      ) : contract ? (
        <div className="flex flex-wrap items-center gap-2">
          <Status value={contract.state} />
          <span className="font-mono text-2xs text-ink-faint">
            {contract.command_count} commands · validity{" "}
            {contract.validity.not_before} → {contract.validity.not_after}
          </span>
        </div>
      ) : null}
    </div>
  );
}

export function EvidenceRecordDrawer({
  open,
  onOpenChange,
  view,
  record,
  document,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The projected record (for the header + field list). */
  view: EvidenceRecordView;
  /** The raw record exactly as returned (for the JSON view). */
  record: Record<string, unknown>;
  /** The run's document (for provenance: run instant + boundary). */
  document: DemoDocument | null;
}) {
  const boundary: DemoBoundaryEntry[] = Array.isArray(document?.boundary)
    ? (document?.boundary ?? [])
    : [];
  const producerBoundary =
    boundary.find((entry) => entry.status !== 200) ?? boundary[0] ?? null;

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title="Evidence record"
      description={view.record_id ?? "the full record, verbatim"}
    >
      <div
        data-testid={EVIDENCE_RECORD_DRAWER_TEST_ID}
        className="flex flex-col gap-5"
      >
        <ObjectHeader
          kind={view.record_type ?? "record"}
          title={view.record_id ?? "no record_id"}
          copyValue={view.record_id ?? undefined}
          subtitle={
            <span className="font-mono text-xs text-ink-muted">
              {view.producer ?? "unknown producer"} · {view.instant ?? "no instant"}
            </span>
          }
        />

        {document ? (
          <div className="flex flex-wrap items-center gap-2 rounded-md border border-line bg-raised px-3 py-2">
            <span className="font-mono text-2xs text-ink-faint">
              run evidence_class
            </span>
            <EvidenceBadge evidenceClass={document.evidence_class} />
            <span className="font-mono text-2xs text-ink-faint">
              the document&apos;s own value, rendered verbatim
            </span>
          </div>
        ) : null}

        {/* the full record ------------------------------------------------ */}
        <section aria-labelledby="evidence-record-fields">
          <h3
            id="evidence-record-fields"
            className="mb-2 text-sm font-semibold text-ink"
          >
            Record
          </h3>
          <dl className="flex flex-col gap-1.5">
            <Row label="record_type" value={view.record_type ?? "—"} />
            <Row label="record_id" value={view.record_id ?? "—"} />
            <Row label="subject_ref" value={view.subject_ref ?? "—"} />
            <Row label="contract_ref" value={view.contract_ref ?? "—"} />
            <Row label="producer" value={view.producer ?? "—"} />
            <Row label="instant" value={view.instant ?? "—"} />
            {view.metric !== null ? (
              <Row label="metric" value={view.metric} />
            ) : null}
            {view.value !== null ? <Row label="value" value={view.value} /> : null}
            {view.confidence_basis_points !== null ? (
              <Row
                label="confidence_basis_points"
                value={`${view.confidence_basis_points} bps`}
              />
            ) : null}
            {view.freshness_until !== null ? (
              <Row label="freshness_until" value={view.freshness_until} />
            ) : null}
            {view.attestation_kind !== null ? (
              <Row label="attestation_kind" value={view.attestation_kind} />
            ) : null}
            {view.attested_value !== null ? (
              <Row label="attested_value" value={view.attested_value} />
            ) : null}
            {view.valid_until !== null ? (
              <Row label="valid_until" value={view.valid_until} />
            ) : null}
            <Row
              label="source_refs"
              value={
                view.source_refs.length > 0 ? (
                  <ul className="flex flex-col">
                    {view.source_refs.map((ref) => (
                      <li key={ref} className="break-all">
                        {ref}
                      </li>
                    ))}
                  </ul>
                ) : (
                  "—"
                )
              }
            />
          </dl>
        </section>

        {/* provenance ------------------------------------------------------ */}
        <section aria-labelledby="evidence-record-provenance">
          <h3
            id="evidence-record-provenance"
            className="mb-2 text-sm font-semibold text-ink"
          >
            Provenance
          </h3>
          <p className="text-sm text-ink-muted">
            The record was produced by{" "}
            <span className="font-mono text-xs">{view.producer ?? "—"}</span>{" "}
            at instant{" "}
            <span className="font-mono text-xs">{view.instant ?? "—"}</span>
            {document
              ? `, inside the demonstration run for instant ${document.instant} (mode ${document.mode}, environment ${document.environment})`
              : ""}
            .
          </p>
          {producerBoundary ? (
            <p className="mt-1.5 font-mono text-2xs text-ink-faint">
              run boundary: {producerBoundary.method} {producerBoundary.route} →{" "}
              {producerBoundary.status} · request_id {producerBoundary.request_id}
            </p>
          ) : null}
        </section>

        {/* related objects ------------------------------------------------- */}
        <section aria-labelledby="evidence-record-related">
          <h3
            id="evidence-record-related"
            className="mb-2 text-sm font-semibold text-ink"
          >
            Related objects
          </h3>
          <RelatedContract contractRef={view.contract_ref} />
        </section>

        {/* the JSON view --------------------------------------------------- */}
        <section aria-labelledby="evidence-record-json">
          <h3
            id="evidence-record-json"
            className="mb-2 text-sm font-semibold text-ink"
          >
            JSON — the record exactly as returned
          </h3>
          <JsonViewer value={record} name="record" />
        </section>
      </div>
    </Drawer>
  );
}
