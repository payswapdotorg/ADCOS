"use client";

/**
 * The demonstration run detail — the full fulfillment chain rendered from
 * the REAL demonstration document only (GET|POST /demo/contract-fulfillment).
 *
 * The chain Contract → Plan → Execution → Provider → Evidence → Assurance
 * (plus the boundary trace that drives it) is rendered verbatim from the
 * document, section by section, with the honest positions the frozen UX
 * spec demands:
 *
 * - evidence_class "SOFTWARE" renders through EvidenceBadge everywhere and
 *   is never presented as physical/network validation;
 * - determinism is stated plainly: identical instant → identical document;
 * - the deterministic execution records the segment-state chain, not
 *   per-state timestamps — no times are invented here;
 * - provider topology remains provider-owned (composition facts only).
 */

import { Fragment, type ReactNode } from "react";
import Link from "next/link";
import {
  ApiRequestPanel,
  ErrorState,
  EvidenceBadge,
  ObjectHeader,
  Status,
  Timeline,
} from "@/components/ui";
import type { ObjectField } from "@/lib/objects";
import { useSession } from "@/lib/session";
import {
  ObjectFieldGrid,
  ObjectSection,
  RefList,
  useAdcosRead,
} from "@/features/eligibility";
import type { DemoDocument, HardConstraint, Provenance } from "@/lib/api/types";
import { parseDemoDocument, type DemoEvidenceRecord } from "./demo-document";

/** The determinism position, stated identically wherever it appears. */
export const DEMO_DETERMINISM_NOTE =
  "Identical instant → identical document: the demonstration is a pure function of the instant (the boundary's durable idempotency ledger replays the same canonical execution; a different instant is a genuinely new demonstration contract).";

/** The chain steps, in order, each linking to its section anchor. */
const CHAIN_STEPS = [
  { id: "contract", label: "Contract" },
  { id: "plan", label: "Plan" },
  { id: "execution", label: "Execution" },
  { id: "provider", label: "Provider" },
  { id: "evidence", label: "Evidence" },
  { id: "assurance", label: "Assurance" },
] as const;

/* ------------------------------------------------------------------ *
 * Small presentation pieces (semantic classes only)
 * ------------------------------------------------------------------ */

function Mono({ children }: { children: ReactNode }) {
  return <span className="break-all font-mono text-xs text-ink">{children}</span>;
}

function ShortId({ value }: { value: string }) {
  const short = value.length > 24 ? `${value.slice(0, 24)}…` : value;
  return (
    <span className="font-mono text-xs text-ink" title={value}>
      {short}
    </span>
  );
}

function ChipList({ values }: { values: string[] }) {
  if (values.length === 0) {
    return <span className="font-mono text-xs text-ink-faint">—</span>;
  }
  return (
    <ul className="flex flex-wrap gap-1.5">
      {values.map((value) => (
        <li
          key={value}
          className="rounded border border-line bg-raised px-1.5 py-px font-mono text-2xs text-ink-muted"
        >
          {value}
        </li>
      ))}
    </ul>
  );
}

function ProvenanceLine({ provenance }: { provenance: Provenance | null }) {
  if (!provenance) {
    return <span className="font-mono text-xs text-ink-faint">—</span>;
  }
  return (
    <span className="break-all font-mono text-xs text-ink-muted">
      {`issuer ${provenance.issuer}`}
      {provenance.decision_refs.length > 0
        ? ` · decision_refs ${provenance.decision_refs.join(", ")}`
        : ""}
    </span>
  );
}

/** A calm labeled mini-table (read-only collections on the chain). */
function MiniTable({
  label,
  head,
  rows,
}: {
  label: string;
  head: string[];
  rows: { key: string; cells: ReactNode[] }[];
}) {
  return (
    <div className="w-full overflow-x-auto rounded-md border border-line bg-surface">
      <table
        aria-label={label}
        className="w-full border-separate border-spacing-0 text-sm"
      >
        <thead>
          <tr>
            {head.map((column) => (
              <th
                key={column}
                scope="col"
                className="border-b border-line px-3 py-1.5 text-left text-xs font-normal text-ink-faint"
              >
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key} className="border-b border-line last:border-b-0">
              {row.cells.map((cell, index) => (
                <td key={index} className="px-3 py-1.5 align-middle">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** The hard constraints table (kind + params, all verbatim). */
function HardConstraintsTable({ constraints }: { constraints: HardConstraint[] }) {
  if (constraints.length === 0) {
    return <p className="text-sm text-ink-faint">none recorded</p>;
  }
  return (
    <MiniTable
      label="Hard constraints"
      head={["kind", "params"]}
      rows={constraints.map((constraint) => ({
        key: constraint.kind,
        cells: [
          <Mono key="kind">{constraint.kind}</Mono>,
          <ul key="params" className="flex flex-wrap gap-1.5">
            {Object.entries(constraint.params).map(([key, value]) => (
              <li
                key={key}
                className="rounded border border-line bg-raised px-1.5 py-px font-mono text-2xs text-ink-muted"
              >
                {`${key}=${String(value)}`}
              </li>
            ))}
          </ul>,
        ],
      }))}
    />
  );
}

/** One evidence record card — every member verbatim, SOFTWARE-badged. */
function EvidenceRecordCard({
  record,
  evidenceClass,
  contractHref,
}: {
  record: DemoEvidenceRecord;
  evidenceClass: string;
  contractHref: string;
}) {
  const isObservation = record.record_type === "observation";
  return (
    <article
      data-testid="evidence-record-card"
      className="rounded-md border border-line bg-raised px-3 py-2.5"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded border border-line-strong px-1 font-mono text-2xs text-ink-muted">
          {record.record_type}
        </span>
        <span
          className="min-w-0 flex-1 break-all font-mono text-2xs text-ink-faint"
          title={record.record_id}
        >
          {record.record_id}
        </span>
        <EvidenceBadge evidenceClass={evidenceClass} size="sm" />
      </div>
      <dl className="mt-2 grid grid-cols-[minmax(10rem,auto)_1fr] items-baseline gap-x-3 gap-y-1.5">
        <dt className="font-mono text-2xs text-ink-faint">producer</dt>
        <dd className="break-all font-mono text-xs text-ink">{record.producer}</dd>
        <dt className="font-mono text-2xs text-ink-faint">instant</dt>
        <dd className="font-mono text-xs text-ink">{record.instant}</dd>
        <dt className="font-mono text-2xs text-ink-faint">subject_ref</dt>
        <dd className="break-all font-mono text-xs text-ink">
          {record.subject_ref}
        </dd>
        <dt className="font-mono text-2xs text-ink-faint">contract_ref</dt>
        <dd className="min-w-0">
          <Link
            href={contractHref}
            className="break-all font-mono text-xs text-accent hover:underline"
          >
            {record.contract_ref}
          </Link>
        </dd>
        {isObservation ? (
          <>
            <dt className="font-mono text-2xs text-ink-faint">metric</dt>
            <dd className="font-mono text-xs text-ink">{record.metric ?? "—"}</dd>
            <dt className="font-mono text-2xs text-ink-faint">value</dt>
            <dd className="font-mono text-xs text-ink">
              {record.value ?? "—"}
            </dd>
          </>
        ) : (
          <>
            <dt className="font-mono text-2xs text-ink-faint">attestation_kind</dt>
            <dd className="font-mono text-xs text-ink">
              {record.attestation_kind ?? "—"}
            </dd>
            <dt className="font-mono text-2xs text-ink-faint">attested_value</dt>
            <dd className="font-mono text-xs text-ink">
              {record.attested_value ?? "—"}
            </dd>
          </>
        )}
        <dt className="font-mono text-2xs text-ink-faint">
          confidence_basis_points
        </dt>
        <dd className="font-mono text-xs text-ink">
          {record.confidence_basis_points ?? "—"}
        </dd>
        <dt className="font-mono text-2xs text-ink-faint">
          {isObservation ? "freshness_until" : "valid_until"}
        </dt>
        <dd className="font-mono text-xs text-ink">
          {isObservation
            ? (record.freshness_until ?? "—")
            : (record.valid_until ?? "—")}
        </dd>
        <dt className="font-mono text-2xs text-ink-faint">source_refs</dt>
        <dd>
          {record.source_refs.length === 0 ? (
            <span className="font-mono text-xs text-ink-faint">—</span>
          ) : (
            <ul className="flex flex-col gap-0.5">
              {record.source_refs.map((ref) => (
                <li
                  key={ref}
                  className="break-all font-mono text-xs text-ink-muted"
                >
                  {ref}
                </li>
              ))}
            </ul>
          )}
        </dd>
      </dl>
    </article>
  );
}

function LoadingChain() {
  return (
    <div className="flex flex-col gap-4" aria-busy="true">
      {[0, 1, 2].map((index) => (
        <div
          key={index}
          className="h-28 animate-pulse rounded-md border border-line bg-surface"
        />
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * The view
 * ------------------------------------------------------------------ */

export function RunDetailView({ instant }: { instant: string }) {
  const { client } = useSession();
  const read = useAdcosRead(
    // the demonstration is a deterministic function of the instant, so the
    // POST replay is safe and byte-identical — this read needs no session
    // (/demo/* is a platform route)
    () => client.demoContractFulfillment(instant),
    [instant, client],
  );

  return (
    <div className="mx-auto w-full max-w-workbench px-gutter py-rhythm">
      <h1 className="sr-only">Demonstration run</h1>
      <Link
        href="/fulfillment"
        className="mb-4 inline-flex text-sm text-ink-muted transition-colors hover:text-ink"
      >
        ← Fulfillment
      </Link>

      {read.loading && !read.data ? <LoadingChain /> : null}

      {read.error && !read.data ? (
        <section className="rounded-md border border-line bg-surface">
          <ErrorState error={read.error} onRetry={read.refresh} />
          <div className="border-t border-line px-4 py-3">
            <Link href="/fulfillment" className="text-sm text-accent hover:underline">
              Back to the fulfillment overview
            </Link>
          </div>
        </section>
      ) : null}

      {read.data ? (
        <DemoDocumentBody doc={read.data} staleError={read.error ? read.error : null} />
      ) : null}
    </div>
  );
}

function DemoDocumentBody({
  doc,
  staleError,
}: {
  doc: DemoDocument;
  staleError: unknown;
}) {
  const view = parseDemoDocument(doc);
  const contractHref = `/connectivity/contracts/${view.contract.contract_id}`;
  const finalSegmentState =
    view.execution.segment_states.length > 0
      ? view.execution.segment_states[view.execution.segment_states.length - 1]
      : null;

  const executionFields: ObjectField[] = [
    { label: "provider", value: <Mono>{view.execution.provider}</Mono> },
    {
      label: "sandbox",
      value: <Mono>{String(view.execution.sandbox ?? "—")}</Mono>,
      hint: "the deterministic reference adapters ARE the sandbox providers — no provider claim is made",
    },
    { label: "adapter_id", value: <Mono>{view.execution.adapter_id}</Mono> },
    {
      label: "access_technology_id",
      value: <Mono>{view.execution.access_technology_id}</Mono>,
    },
    {
      label: "standard_mechanisms",
      value: <ChipList values={view.execution.standard_mechanisms} />,
    },
    { label: "session_id", value: <Mono>{view.execution.session_id}</Mono> },
    {
      label: "reservation_id",
      value: <Mono>{view.execution.reservation_id}</Mono>,
    },
    { label: "activation_id", value: <Mono>{view.execution.activation_id}</Mono> },
    { label: "binding_id", value: <Mono>{view.execution.binding_id}</Mono> },
    {
      label: "measurement_id",
      value: <Mono>{view.execution.measurement_id}</Mono>,
    },
    { label: "release_id", value: <Mono>{view.execution.release_id}</Mono> },
    {
      label: "released_kinds",
      value: <ChipList values={view.execution.released_kinds} />,
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      {staleError ? (
        <section className="rounded-md border border-line bg-surface">
          <ErrorState error={staleError} compact />
        </section>
      ) : null}

      <ObjectHeader
        kind="demonstration"
        title={doc.instant}
        copyValue={doc.instant}
        status={view.contract.state}
        subtitle="The deterministic contract-fulfillment demonstration (SOFTWARE evidence — never physical connectivity)."
        meta={[
          { label: "instant", value: <Mono>{doc.instant}</Mono> },
          { label: "mode", value: <Mono>{doc.mode}</Mono> },
          { label: "environment", value: <Mono>{doc.environment}</Mono> },
          {
            label: "evidence_class",
            value: <EvidenceBadge evidenceClass={doc.evidence_class} size="sm" />,
          },
          {
            label: "contract_id",
            value: (
              <Link
                href={contractHref}
                className="break-all font-mono text-xs text-accent hover:underline"
              >
                {view.contract.contract_id}
              </Link>
            ),
          },
          { label: "plan_id", value: <Mono>{view.plan.plan_id}</Mono> },
        ]}
      />

      {/* The chain overview — each step links to its section anchor. */}
      <nav
        aria-label="The fulfillment chain"
        className="flex flex-wrap items-center gap-1.5"
      >
        {CHAIN_STEPS.map((step, index) => (
          <Fragment key={step.id}>
            {index > 0 ? (
              <span aria-hidden="true" className="text-ink-faint">
                →
              </span>
            ) : null}
            <a
              href={`#${step.id}`}
              className="rounded border border-line bg-raised px-2 py-0.5 text-sm text-ink-muted transition-colors hover:border-line-strong hover:text-ink"
            >
              {step.label}
            </a>
          </Fragment>
        ))}
      </nav>

      {/* The determinism position, stated plainly. */}
      <p className="rounded-md border border-dashed border-line bg-raised px-3 py-2 text-xs leading-relaxed text-ink-muted">
        <span className="font-medium text-ink">Determinism.</span>{" "}
        {DEMO_DETERMINISM_NOTE}
      </p>

      {/* 0 · Boundary trace */}
      <ObjectSection
        id="boundary"
        title="0 · Boundary trace"
        description="The boundary leg drives the canonical lifecycle the way an external application does (intent → offer → activation) through the durable idempotency discipline."
      >
        <MiniTable
          label="Boundary trace"
          head={["method", "route", "status", "request_id"]}
          rows={doc.boundary.map((entry) => ({
            key: `${entry.method}:${entry.request_id}`,
            cells: [
              <span key="method" className="font-mono text-xs text-ink">
                {entry.method}
              </span>,
              <span key="route" className="break-all font-mono text-xs text-ink">
                {entry.route}
              </span>,
              <span key="status" className="font-mono text-xs text-ink">
                {String(entry.status)}
              </span>,
              <ShortId key="request" value={entry.request_id} />,
            ],
          }))}
        />
        {doc.boundary.map((entry) => (
          <ApiRequestPanel
            key={entry.request_id}
            method={entry.method}
            path={entry.route}
            description={`the demonstration's boundary request — request_id ${entry.request_id}, status ${entry.status}`}
          />
        ))}
      </ObjectSection>

      {/* 1 · Contract */}
      <ObjectSection
        id="contract"
        title="1 · Contract"
        description="The demonstration's contract — the durable authority the whole chain fulfills."
        fields={[
          { label: "state", value: <Status value={view.contract.state} /> },
          {
            label: "contract_id",
            value: (
              <Link
                href={contractHref}
                className="break-all font-mono text-xs text-accent hover:underline"
              >
                {view.contract.contract_id}
              </Link>
            ),
          },
          {
            label: "validity",
            value: (
              <Mono>
                {view.contract.validity
                  ? `${view.contract.validity.not_before} → ${view.contract.validity.not_after}`
                  : "—"}
              </Mono>
            ),
          },
          {
            label: "principal",
            value: (
              <Mono>
                {view.contract.principal
                  ? `${view.contract.principal.principal_kind} · ${view.contract.principal.principal_ref}`
                  : "—"}
              </Mono>
            ),
          },
        ]}
        json={doc.contract}
        jsonName="contract"
      >
        <div>
          <p className="mb-1.5 text-2xs uppercase tracking-wide text-ink-faint">
            hard_constraints
          </p>
          <HardConstraintsTable constraints={view.contract.hard_constraints} />
        </div>
        <div>
          <p className="mb-1.5 text-2xs uppercase tracking-wide text-ink-faint">
            accepted_offers
          </p>
          <RefList
            references={view.contract.accepted_offers}
            emptyLabel="no accepted offers recorded"
          />
        </div>
        <Link
          href={contractHref}
          className="text-sm text-accent transition-colors hover:underline"
        >
          Open the contract detail →
        </Link>
      </ObjectSection>

      {/* 2 · Plan */}
      <ObjectSection
        id="plan"
        title="2 · Plan"
        description="The execution plan composed over the contract's canonical constraints."
        fields={[
          { label: "plan_id", value: <Mono>{view.plan.plan_id}</Mono> },
          {
            label: "contract_id",
            value: (
              <Link
                href={contractHref}
                className="break-all font-mono text-xs text-accent hover:underline"
              >
                {view.plan.contract_id}
              </Link>
            ),
          },
          {
            label: "constraint_fingerprint",
            value: <Mono>{view.plan.constraint_fingerprint}</Mono>,
            hint: "Binds the plan to the contract's hard constraints: the plan-verification gate re-verifies that the plan preserves the contract's constraints, and this fingerprint is the content-derived digest of those constraints.",
          },
          {
            label: "tie_break",
            value: <ChipList values={view.plan.tie_break} />,
          },
          {
            label: "validity",
            value: (
              <Mono>
                {view.plan.validity
                  ? `${view.plan.validity.not_before} → ${view.plan.validity.not_after}`
                  : "—"}
              </Mono>
            ),
          },
          {
            label: "provenance",
            value: <ProvenanceLine provenance={view.plan.provenance} />,
          },
        ]}
        json={doc.plan}
        jsonName="plan"
      >
        <div>
          <p className="mb-1.5 text-2xs uppercase tracking-wide text-ink-faint">
            hard_constraints
          </p>
          <HardConstraintsTable constraints={view.plan.hard_constraints} />
        </div>
        <div>
          <p className="mb-1.5 text-2xs uppercase tracking-wide text-ink-faint">
            segments
          </p>
          <MiniTable
            label="Plan segments"
            head={["segment_id", "role", "state", "operations", "offer_reference"]}
            rows={view.plan.segments.map((segment) => ({
              key: segment.segment_id,
              cells: [
                <ShortId key="segment" value={segment.segment_id} />,
                <span key="role" className="font-mono text-xs text-ink">
                  {segment.role}
                </span>,
                <Status key="state" value={segment.state} size="sm" />,
                <ChipList key="operations" values={segment.operations} />,
                segment.offer_reference ? (
                  <span
                    key="offer"
                    className="flex flex-wrap items-baseline gap-x-2"
                  >
                    <span className="rounded border border-line-strong px-1 font-mono text-2xs text-ink-muted">
                      {segment.offer_reference.ref_kind}
                    </span>
                    <span className="break-all font-mono text-xs text-ink">
                      {segment.offer_reference.value}
                    </span>
                  </span>
                ) : (
                  <span key="offer" className="font-mono text-xs text-ink-faint">
                    —
                  </span>
                ),
              ],
            }))}
          />
        </div>
        <div>
          <p className="mb-1.5 text-2xs uppercase tracking-wide text-ink-faint">
            segment state kernel
          </p>
          <Timeline
            items={view.execution.segment_states.map((state, index) => ({
              id: `segment-state-${index}`,
              title: state,
              tone: state,
            }))}
          />
          <p className="mt-1 text-xs leading-relaxed text-ink-faint">
            segment_states verbatim from the document, in recorded order — the
            deterministic execution records the state chain, not per-state
            timestamps.
          </p>
        </div>
      </ObjectSection>

      {/* 3 · Execution */}
      <ObjectSection
        id="execution"
        title="3 · Execution"
        description="The execution leg's milestones: reserve → activate → measure → release, each adapter operation mirrored by the plan's segment-state kernel."
        json={doc.execution}
        jsonName="execution"
      >
        <ObjectFieldGrid fields={executionFields} columns={2} />
        <div>
          <p className="mb-1.5 text-2xs uppercase tracking-wide text-ink-faint">
            samples
          </p>
          <MiniTable
            label="Execution samples"
            head={["metric", "observed_at", "value"]}
            rows={view.execution.samples.map((sample) => ({
              key: `${sample.metric}:${sample.observed_at}`,
              cells: [
                <Mono key="metric">{sample.metric}</Mono>,
                <Mono key="observed">{sample.observed_at}</Mono>,
                <Mono key="value">{String(sample.value ?? "—")}</Mono>,
              ],
            }))}
          />
          {finalSegmentState ? (
            <p className="mt-2 text-xs text-ink-faint">
              Final segment state: <Status value={finalSegmentState} size="sm" />
            </p>
          ) : null}
        </div>
      </ObjectSection>

      {/* 4 · Provider */}
      <ObjectSection
        id="provider"
        title="4 · Provider"
        description="The composition facts the execution leg records — the deterministic reference adapter."
        fields={[
          { label: "provider", value: <Mono>{view.execution.provider}</Mono> },
          { label: "adapter_id", value: <Mono>{view.execution.adapter_id}</Mono> },
          {
            label: "access_technology_id",
            value: <Mono>{view.execution.access_technology_id}</Mono>,
          },
          {
            label: "standard_mechanisms",
            value: <ChipList values={view.execution.standard_mechanisms} />,
          },
        ]}
      >
        <Link
          href="/networks"
          className="text-sm text-accent transition-colors hover:underline"
        >
          Open Networks for provider and adapter inspection →
        </Link>
        <p className="text-xs leading-relaxed text-ink-faint">
          Provider topology remains provider-owned: the demonstration exposes
          the composition facts above, never a provider-internal topology
          graph.
        </p>
      </ObjectSection>

      {/* 5 · Evidence */}
      <ObjectSection
        id="evidence"
        title="5 · Evidence"
        description="SOFTWARE evidence — a software deployment demonstration over the accepted domains; physical connectivity is never claimed (EVID-002..EVID-008 remain open)."
      >
        {view.evidence.length === 0 ? (
          <p className="text-sm text-ink-faint">no evidence records in the document</p>
        ) : (
          <div className="flex flex-col gap-3">
            {view.evidence.map((record) => (
              <EvidenceRecordCard
                key={record.record_id}
                record={record}
                evidenceClass={doc.evidence_class}
                contractHref={contractHref}
              />
            ))}
          </div>
        )}
      </ObjectSection>

      {/* 6 · Assurance */}
      <ObjectSection
        id="assurance"
        title="6 · Assurance"
        description="The assurance obligations the demonstration's contract references."
      >
        <RefList
          references={view.contract.assurance_obligations}
          emptyLabel="no assurance obligations referenced"
        />
        <p className="text-xs leading-relaxed text-ink-faint">
          Referenced, never evaluated here: this page exposes the obligations
          the contract carries; assurance semantics belong to the assurance
          surface, which this demonstration page does not call.
        </p>
      </ObjectSection>
    </div>
  );
}
