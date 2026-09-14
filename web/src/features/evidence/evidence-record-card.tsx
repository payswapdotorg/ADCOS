"use client";

/**
 * EvidenceRecordCard — one evidence record (observation or attestation)
 * from a demonstration run. Every member renders VERBATIM; the card is
 * the activation surface for the record's detail drawer.
 *
 * The record's type ("observation" | "attestation" — the backend's own
 * vocabulary) renders as a mono chip, never re-labeled. The contract
 * reference is a real link into the contract detail page (the record's
 * own contract_ref, not the run's).
 */

import Link from "next/link";
import type { ReactNode } from "react";
import type { KeyboardEvent } from "react";
import { cn } from "@/lib/utils";
import type { EvidenceRecordView } from "./evidence-record";

/** Stable test ids for the evidence suite. */
export const EVIDENCE_RECORD_TEST_IDS = {
  root: "evidence-record",
  type: "evidence-record-type",
} as const;

function Field({
  label,
  children,
  mono = true,
}: {
  label: string;
  children: ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="grid grid-cols-[max-content_1fr] items-baseline gap-x-2">
      <span className="whitespace-nowrap font-mono text-2xs text-ink-faint">
        {label}
      </span>
      <span className={cn("min-w-0 text-xs text-ink", mono && "font-mono")}>
        {children}
      </span>
    </div>
  );
}

function Truncated({ value }: { value: string }) {
  return (
    <span className="block truncate" title={value}>
      {value}
    </span>
  );
}

export function EvidenceRecordCard({
  view,
  onOpen,
}: {
  view: EvidenceRecordView;
  onOpen: () => void;
}) {
  function handleKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onOpen();
    }
  }

  const isObservation = view.record_type === "observation";
  const isAttestation = view.record_type === "attestation";

  return (
    <article
      data-testid={EVIDENCE_RECORD_TEST_IDS.root}
      data-record-type={view.record_type ?? "unknown"}
      role="button"
      tabIndex={0}
      aria-label={`Evidence record ${view.record_id ?? ""} (${view.record_type ?? "unknown record type"}) — open details`}
      onClick={onOpen}
      onKeyDown={handleKeyDown}
      className="flex cursor-pointer flex-col gap-2 rounded-md border border-line bg-surface px-3 py-2.5 transition-colors hover:bg-raised/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span
          data-testid={EVIDENCE_RECORD_TEST_IDS.type}
          className={cn(
            "inline-flex items-center rounded border px-1.5 py-px font-mono text-2xs",
            isObservation && "border-line-strong text-ink-muted",
            isAttestation && "border-line-strong text-ink-muted",
            !isObservation && !isAttestation && "border-dashed border-line text-ink-faint",
          )}
        >
          {view.record_type ?? "unknown"}
        </span>
        <span
          className="min-w-0 flex-1 truncate font-mono text-xs text-ink"
          title={view.record_id ?? ""}
        >
          {view.record_id ?? "no record_id"}
        </span>
        <span className="whitespace-nowrap font-mono text-2xs text-ink-faint">
          {view.instant ?? ""}
        </span>
      </div>

      <div className="flex flex-col gap-1">
        {view.subject_ref ? (
          <Field label="subject_ref">
            <Truncated value={view.subject_ref} />
          </Field>
        ) : null}

        {view.contract_ref ? (
          <div className="grid grid-cols-[max-content_1fr] items-baseline gap-x-2">
            <span className="whitespace-nowrap font-mono text-2xs text-ink-faint">
              contract_ref
            </span>
            <span className="min-w-0">
              <Link
                href={`/connectivity/contracts/${view.contract_ref}`}
                onClick={(event) => event.stopPropagation()}
                className="block truncate font-mono text-xs text-accent hover:underline"
                title={view.contract_ref}
              >
                {view.contract_ref}
              </Link>
            </span>
          </div>
        ) : null}

        {view.producer ? (
          <Field label="producer">
            <Truncated value={view.producer} />
          </Field>
        ) : null}

        {isObservation ? (
          <>
            {view.metric ? (
              <Field label="metric">
                <span className="text-ink">
                  {view.metric}
                  {view.value !== null ? ` = ${view.value}` : ""}
                </span>
              </Field>
            ) : null}
            {view.confidence_basis_points !== null ? (
              <Field label="confidence">
                <span>{view.confidence_basis_points} bps</span>
              </Field>
            ) : null}
            {view.freshness_until ? (
              <Field label="freshness_until">
                <Truncated value={view.freshness_until} />
              </Field>
            ) : null}
          </>
        ) : null}

        {isAttestation ? (
          <>
            {view.attestation_kind ? (
              <Field label="attestation_kind">
                <span className="text-ink">
                  {view.attestation_kind}
                  {view.attested_value !== null
                    ? ` = ${view.attested_value}`
                    : ""}
                </span>
              </Field>
            ) : null}
            {view.valid_until ? (
              <Field label="valid_until">
                <Truncated value={view.valid_until} />
              </Field>
            ) : null}
          </>
        ) : null}

        {view.source_refs.length > 0 ? (
          <Field label={`source_refs (${view.source_refs.length})`}>
            <span className="block truncate" title={view.source_refs.join("\n")}>
              {view.source_refs[0]}
              {view.source_refs.length > 1
                ? ` + ${view.source_refs.length - 1} more`
                : ""}
            </span>
          </Field>
        ) : null}
      </div>
    </article>
  );
}
