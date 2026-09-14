"use client";

/**
 * ObligationRef — one assurance obligation rendered VERBATIM: the opaque
 * typed reference exactly as the backend returned it (ref_kind, value)
 * plus its provenance (issuer, decision_refs).
 *
 * Assurance obligations are OPAQUE REFERENCES — the assurance authority
 * owns the semantics and the backend never expands them into metrics.
 * This component therefore renders the reference and NEVER an invented
 * metric dashboard; each obligation links to its contract and its
 * evidence chain (the demonstration runs&apos; attestation records by
 * contract_ref).
 */

import Link from "next/link";
import type { OpaqueReference } from "@/lib/api/types";
import { CopyButton } from "@/components/ui";

/** Stable test id for the assurance suite. */
export const OBLIGATION_REF_TEST_ID = "assurance-obligation";

export function ObligationRef({
  obligation,
  contractId,
}: {
  obligation: OpaqueReference;
  /** The owning contract — the obligation links back to it. */
  contractId: string;
}) {
  const decisionRefs = obligation.provenance?.decision_refs ?? [];
  return (
    <li
      data-testid={OBLIGATION_REF_TEST_ID}
      className="flex flex-col gap-1.5 rounded-md border border-line bg-raised px-3 py-2"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center rounded border border-line-strong px-1.5 py-px font-mono text-2xs text-ink-muted">
          {obligation.ref_kind}
        </span>
        <span
          className="min-w-0 flex-1 break-all font-mono text-xs text-ink"
          title={obligation.value}
        >
          {obligation.value}
        </span>
        <CopyButton
          value={obligation.value}
          ariaLabel="Copy obligation reference"
          label="Copy"
        />
      </div>
      {obligation.provenance ? (
        <div className="flex flex-col gap-0.5">
          <span className="font-mono text-2xs text-ink-faint">
            provenance.issuer:{" "}
            <span className="text-ink-muted">
              {obligation.provenance.issuer}
            </span>
          </span>
          {decisionRefs.length > 0 ? (
            <span className="font-mono text-2xs text-ink-faint">
              provenance.decision_refs:
            </span>
          ) : null}
          {decisionRefs.length > 0 ? (
            <ul className="flex flex-wrap gap-1.5 pl-1">
              {decisionRefs.map((ref) => (
                <li
                  key={ref}
                  className="rounded border border-line bg-surface px-1.5 py-px font-mono text-2xs text-ink-muted"
                >
                  {ref}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : (
        <span className="font-mono text-2xs text-ink-faint">
          no provenance on this reference
        </span>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Link
          href={`/connectivity/contracts/${contractId}`}
          className="text-xs text-accent hover:underline"
        >
          contract →
        </Link>
        <Link
          href="/evidence"
          className="text-xs text-accent hover:underline"
        >
          evidence chain →
        </Link>
      </div>
    </li>
  );
}
