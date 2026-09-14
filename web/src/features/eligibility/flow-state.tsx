/**
 * The eligibility / policy presentation — WHY a flow state is what it is,
 * from backend reason data ONLY.
 *
 * The console never re-implements policy in TypeScript: these components
 * present the backend's own statements (notes, reason codes, evidence
 * classes, statements vocabulary) VERBATIM, with the honest explanations
 * the frozen UX spec requires (SOFTWARE vs physical evidence visibly
 * distinct through EvidenceBadge; "sandbox-simulation" rendered as-is).
 */

import type { ContractLifecycle, OpaqueReference } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { EvidenceBadge } from "@/components/ui/evidence-badge";
import { Status } from "@/components/ui/status";

/* ------------------------------------------------------------------ *
 * Verbatim material renderers
 * ------------------------------------------------------------------ */

/**
 * VerbatimNote — a backend note rendered EXACTLY as the backend wrote it
 * (the usage note, the assurance note, the lifecycle note). The label
 * marks its origin; the text is never paraphrased.
 */
export function VerbatimNote({
  note,
  label = "backend note",
  className,
}: {
  note: string;
  label?: string;
  className?: string;
}) {
  return (
    <figure
      data-testid="verbatim-note"
      className={cn(
        "rounded-md border border-line bg-raised px-3 py-2",
        className,
      )}
    >
      <figcaption className="text-2xs uppercase tracking-wide text-ink-faint">
        {label} <span aria-hidden="true">(verbatim)</span>
      </figcaption>
      <blockquote className="mt-1 text-sm leading-relaxed text-ink-muted">
        {note}
      </blockquote>
    </figure>
  );
}

/** One canonical opaque typed reference with its provenance visible. */
export function RefValue({
  reference,
  className,
}: {
  reference: OpaqueReference;
  className?: string;
}) {
  const provenance = reference.provenance;
  return (
    <div
      data-testid="ref-value"
      className={cn(
        "flex flex-col gap-0.5 rounded-md border border-line bg-raised px-2.5 py-1.5",
        className,
      )}
    >
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <span className="rounded border border-line-strong px-1 font-mono text-2xs text-ink-muted">
          {reference.ref_kind}
        </span>
        <span className="min-w-0 break-all font-mono text-xs text-ink">
          {reference.value}
        </span>
      </div>
      {provenance ? (
        <div className="font-mono text-2xs text-ink-faint">
          issuer {provenance.issuer}
          {provenance.decision_refs.length > 0
            ? ` · decision_refs ${provenance.decision_refs.join(", ")}`
            : null}
        </div>
      ) : null}
    </div>
  );
}

/** A list of opaque typed references (or the honest empty label). */
export function RefList({
  references,
  emptyLabel = "none recorded",
}: {
  references: OpaqueReference[];
  emptyLabel?: string;
}) {
  if (references.length === 0) {
    return <p className="text-sm text-ink-faint">{emptyLabel}</p>;
  }
  return (
    <ul className="flex flex-col gap-1.5">
      {references.map((reference, index) => (
        <li key={`${reference.ref_kind}:${reference.value}:${index}`}>
          <RefValue reference={reference} />
        </li>
      ))}
    </ul>
  );
}

/* ------------------------------------------------------------------ *
 * The flow-state explanation panel
 * ------------------------------------------------------------------ */

/**
 * FlowStatePanel — presents the lifecycle projection's own explanation of
 * the current state: the contract_state (Status, backend vocabulary), the
 * evidence_class (EvidenceBadge — "sandbox-simulation" is software-side
 * and visibly distinct from physical evidence), the execution status and
 * the physical-connectivity position, each rendered VERBATIM with its
 * canonical member name, plus the backend's note and statements.
 */
export function FlowStatePanel({
  lifecycle,
  className,
}: {
  lifecycle: ContractLifecycle;
  className?: string;
}) {
  return (
    <div
      data-testid="flow-state-panel"
      className={cn("flex flex-col gap-3", className)}
    >
      <dl className="grid grid-cols-[minmax(11rem,auto)_1fr] items-baseline gap-x-4 gap-y-2">
        <dt className="font-mono text-2xs text-ink-faint">contract_state</dt>
        <dd>
          <Status value={lifecycle.contract_state} />
        </dd>
        <dt className="font-mono text-2xs text-ink-faint">evidence_class</dt>
        <dd className="flex flex-wrap items-center gap-2">
          <EvidenceBadge evidenceClass={lifecycle.evidence_class} />
          <span className="text-xs text-ink-muted">
            software-side state-machine projection — physical connectivity is
            never claimed by API success
          </span>
        </dd>
        <dt className="font-mono text-2xs text-ink-faint">execution_status</dt>
        <dd className="font-mono text-xs text-ink">{lifecycle.execution_status}</dd>
        <dt className="font-mono text-2xs text-ink-faint">
          physical_connectivity_observed
        </dt>
        <dd className="font-mono text-xs text-ink">
          {String(lifecycle.physical_connectivity_observed)}
        </dd>
        <dt className="font-mono text-2xs text-ink-faint">physical_evidence</dt>
        <dd className="font-mono text-xs text-ink">{lifecycle.physical_evidence}</dd>
        <dt className="font-mono text-2xs text-ink-faint">command_count</dt>
        <dd className="font-mono text-xs text-ink">{lifecycle.command_count}</dd>
        <dt className="font-mono text-2xs text-ink-faint">entered_at</dt>
        <dd className="font-mono text-xs text-ink">{lifecycle.entered_at}</dd>
      </dl>
      <VerbatimNote note={lifecycle.note} label="lifecycle note" />
      {lifecycle.statements.length > 0 ? (
        <div>
          <p className="text-2xs uppercase tracking-wide text-ink-faint">
            statements <span aria-hidden="true">(backend vocabulary)</span>
          </p>
          <ul className="mt-1 flex flex-wrap gap-1.5">
            {lifecycle.statements.map((statement) => (
              <li
                key={statement}
                className="rounded border border-line bg-raised px-1.5 py-px font-mono text-2xs text-ink-muted"
              >
                {statement}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
